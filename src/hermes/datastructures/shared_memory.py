############
#
# Copyright (c) 2024-2026 Maxim Yudayev and KU Leuven eMedia Lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Created 2026 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Maxim Yudayev [https://yudayev.com].
#
# ############

from functools import reduce
from multiprocessing import shared_memory
from typing import Iterable, List, Optional
import numpy as np

from hermes.utils.types import SharedMemoryCircularBufferMetadata, StreamFifoFillLevel


class SharedMemoryCircularBuffer:
    """Zero-copy circular FIFO buffer of `Node` data in shared memory,
    for thread-safe multiprocess multicore access.

    NOTE: It's the responsibility of the upstream module to allocate sufficient
    space for the buffer to avoid contention, akin to ping-pong writing.

    TODO: Add Terminal UI that prints memory usage per stream (pid, name, fill level, node name).
    """

    def __init__(
        self,
        buf_len: int,
        sample_size: Iterable[int],
        dtype_str: str,
        metadata: Optional[SharedMemoryCircularBufferMetadata],
    ):
        """Constructor of a shared memory circular buffer.

        If `metadata` is provided, will attach the buffer instance to the specified underlying shared memory.

        Args:
            buf_len (int): Length of the circular buffer.
            sample_size (Iterable[int]): Size of each sample.
            dtype_str (str): Data type of each data element.
            metadata (SharedMemoryCircularBufferMetadata, optional): Datastructure metadata
                for multiprocessing access to underlying shared memory data. Defaults to `None`.
        """
        if metadata is None:
            element_size = (
                reduce(lambda x, y: x * y, sample_size) * np.dtype(dtype_str).itemsize
            )
            self.shared_memory = shared_memory.SharedMemory(
                create=True, size=buf_len * element_size
            )
            self.metadata = SharedMemoryCircularBufferMetadata(
                buf_len=buf_len,
                data_type=dtype_str,
                sample_size=sample_size,
                element_size=element_size,
                shm_id=self.shared_memory.name,
            )
        else:
            self.shared_memory = shared_memory.SharedMemory(name=metadata.shm_id)
            self.metadata = metadata

        self.buf_len = buf_len
        self.buffer = np.ndarray(
            shape=[buf_len, *sample_size],
            dtype=dtype_str,
            buffer=self.shared_memory.buf,
        )

    def get_metadata(self) -> SharedMemoryCircularBufferMetadata:
        """Gets the datastructure metadata for multiprocess access to underlying shared memory.

        Returns:
            SharedMemoryCircularBufferMetadata: Datastructure metadata.
        """
        return self.metadata

    def get_fill_level(self) -> StreamFifoFillLevel:
        """Estimates the current usage level of the allocated data structure.

        Returns:
            DataFifoFillLevel: Overview of the current FIFO usage level.
        """
        with self.metadata.lock:
            num_samples = (
                self.metadata.write_head.value - self.metadata.read_tail.value
            ) % self.buf_len

        return StreamFifoFillLevel(
            num_samples=num_samples,
            sample_num_bytes=self.metadata.element_size,
            buf_len=self.buf_len,
        )

    def is_write_overlap_read(
        self,
        read_tail: int,
        read_head: int,
        write_tail: int,
        write_head: int,
    ) -> bool:
        """Predicate for write-during-read condition of overlapping memory ranges.

        Both, read and write, ranges are treated as half-open intervals [tail, head)
        on the circular buffer of length `self.buf_len`.
        Overlap means the selected write range extends past the currently being read
        elements of the read range.

        Args:
            read_tail (int): Index of the oldest sample in the current read range.
            read_head (int): Index of the newest sample in the current read range.
            write_tail (int): Index of the oldest sample in the new write range.
            write_head (int): Index of the newest sample in the new write range.

        Returns:
            bool: Whether the write range overlaps the read range.
        """

        def _intervals(start: int, end: int) -> list[tuple[int, int]]:
            if start == end:
                return []
            elif start < end:
                return [(start, end)]
            else:
                return [(start, self.buf_len), (0, end)]

        read_intervals = _intervals(read_tail, read_head)
        write_intervals = _intervals(write_tail, write_head)

        for rs, re in read_intervals:
            for ws, we in write_intervals:
                if ws < re and rs < we:
                    return True
        return False

    def push(self, device_name: str, stream_name: str, new_data: np.ndarray) -> None:
        """In-place update of the shared circular buffer.

        Args:
            new_data (np.ndarray): NumPy array of new data.
        """
        num_elements = new_data.shape[0]

        # Check which ranges we are allowed to write to in a thread-safe way.
        with self.metadata.lock:
            self.metadata.is_writing.value = True
            write_tail = self.metadata.write_head.value
            write_head = (self.metadata.write_head.value + num_elements) % self.buf_len
            # In case reading is in progress, fill at most up to the reading tail, dropping oldest of newest samples that would overlap.
            if self.metadata.is_reading.value and self.is_write_overlap_read(
                self.metadata.read_tail.value,
                self.metadata.read_head.value,
                write_tail,
                write_head,
            ):
                write_head = self.metadata.read_tail.value
                num_elements = (write_head - write_tail) % self.buf_len
                new_data = new_data[-num_elements:]

        # Nothing to write (write range bumps into the tail of the read region, with no empty slots for new data).
        if num_elements == 0:
            with self.metadata.lock:
                self.metadata.is_writing.value = False
            return

        if write_tail < write_head:
            self.buffer[write_tail:write_head] = new_data
        else:
            first_part = self.buf_len - write_tail
            self.buffer[write_tail:] = new_data[:first_part]
            if num_elements > 1:
                self.buffer[: num_elements - first_part] = new_data[first_part:]

        # Update the datastructures metadata in a thread-safe way.
        with self.metadata.lock:
            self.metadata.is_writing.value = False
            self.metadata.write_head.value = write_head

    def _reserve(self) -> tuple[int, int, int]:
        """Reserves the current unread data range for thread-safe access.

        Returns:
            tuple[int, int, int]: Pointers to the start (oldest unread) and the end (newest unread) of the valid data window, and the number of available samples.
        """
        with self.metadata.lock:
            self.metadata.is_reading.value = True
            self.metadata.read_head.value = self.metadata.write_head.value
            available = (
                self.metadata.read_head.value - self.metadata.read_tail.value
            ) % self.buf_len
            return (
                self.metadata.read_tail.value,
                self.metadata.read_head.value,
                available,
            )

    def release(self, num_read: int = 0) -> None:
        """Releases the read reservation. If `num_read` > 0, updates the metadata pointers to mark
        oldest samples as read and available for overwriting.

        NOTE: It's the responsibility of the upstream block to pass the right number of samples
        that doesn't violate the number of available samples.

        Args:
            num_read (int): Number of oldest samples to permanently mark as read (consumed). Defaults to `0`.
        """
        with self.metadata.lock:
            if num_read > 0:
                self.metadata.read_tail.value = (
                    self.metadata.read_tail.value + num_read
                ) % self.buf_len
            self.metadata.is_reading.value = False

    def peek(self, num_samples: int) -> tuple[List[np.ndarray], int]:
        """Provides a view over the N newest samples without updating metadata permanently.

        NOTE: Must call `.release()` after peeking the data to release metadata lock.

        Args:
            num_samples (int): Number of newest samples to retrieve.

        Returns:
            List[np.ndarray]: List of views over the requested newest samples.
            int: Number of samples being peeked, contained in the views.
        """
        read_tail, read_head, num_available = self._reserve()
        num_samples = min(num_samples, num_available)

        if num_samples == 0:
            self.release()
            return [], 0

        start = (read_head - num_samples) % self.buf_len
        end = read_head

        if start < end:
            views = [self.buffer[start:end]]
        else:
            views = [self.buffer[start:], self.buffer[:end]]

        return views, num_samples

    def pop(self, num_samples: int) -> tuple[List[np.ndarray], int]:
        """Provides a view over the N oldest or all the available samples,
        whichever is smaller, and marks them as read.

        NOTE: Must call `.release(num_samples)` after "popping" the data
        to mark the samples as read.

        Args:
            num_samples (int): Number of oldest samples to pop.

        Returns:
            List[np.ndarray]: List of views over the being popped samples.
            int: Number of samples being popped, contained in the views.
        """
        read_tail, read_head, num_available = self._reserve()
        num_samples = min(num_samples, num_available)

        if num_samples == 0:
            self.release()
            return [], 0

        start = read_tail
        end = (read_tail + num_samples) % self.buf_len

        if start < end:
            views = [self.buffer[start:end]]
        else:
            views = [self.buffer[start:], self.buffer[:end]]

        return views, num_samples

    def clear(self) -> None:
        read_tail, read_head, available = self._reserve()
        self.release(available)

    def close(self) -> None:
        self.shared_memory.close()

    def unlink(self) -> None:
        self.shared_memory.unlink()
