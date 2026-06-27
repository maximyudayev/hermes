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

from hermes.utils.types import RawBytesSharedMemoryCircularBufferMetadata
from functools import reduce
from multiprocessing import shared_memory
from typing import Iterable, List, Optional
import numpy as np

from hermes.utils.types import SharedMemoryCircularBufferMetadata


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

    def push_unprotected(
        self,
        bundle_name: str,
        channel_name: str,
        new_data: np.ndarray,
        write_tail: int,
        write_head: int,
        num_elements: int,
    ) -> None:
        """In-place update of the shared circular buffer.

        NOTE: Assumes external synchronization is provided.

        Args:
            bundle_name (str): Valid data bundle name.
            channel_name (str): Valid data channel name.
            new_data (np.ndarray): NumPy array of new data with shape `[N, *sample_size]`.
            write_tail (int): Pointer to the bottom address (start) of the write region in the circular buffer.
            write_head (int): Pointer to the top address (end) of the write region in the circular buffer.
            num_elements (int): Total number of elements of `sample_size` being written.
        """
        if write_tail < write_head:
            self.buffer[write_tail:write_head] = new_data
        else:
            first_part = self.buf_len - write_tail
            self.buffer[write_tail:] = new_data[:first_part]
            if num_elements > 1:
                self.buffer[: num_elements - first_part] = new_data[first_part:]

    def pop_unprotected(self, start: int, end: int) -> List[np.ndarray]:
        """Provides contiguous views over the requested sample range.

        Args:
            start (int): Index of the oldest sample to pop.
            end (int): Index of the newest sample to pop.

        Returns:
            List[np.ndarray]: List of views over the requested sample range.
        """
        if start < end:
            return [self.buffer[start:end]]
        else:
            return [self.buffer[start:], self.buffer[:end]]

    def close(self) -> None:
        self.shared_memory.close()

    def unlink(self) -> None:
        self.shared_memory.unlink()


class RawBytesSharedMemoryCircularBuffer(SharedMemoryCircularBuffer):
    """Zero-copy circular FIFO buffer of flat bytes in shared memory (e.g. MJPEG video),
    with a helper index array to keep track of frames.
    """

    def __init__(
        self,
        buf_len: int,
        mem_size: int,
        sample_size: Iterable[int],
        metadata: Optional[RawBytesSharedMemoryCircularBufferMetadata],
    ):
        """Constructor of a bytes shared memory circular buffer.

        Args:
            buf_len (int): Length of the index array, mapping one-to-one to other channels and pointing to start/end of frames.
            mem_size (int): Number of bytes to allocate for video frames. Does not map one-to-one to other channels.
            sample_size (Iterable[int]): Size of each sample.
            metadata (RawBytesSharedMemoryCircularBufferMetadata, optional): Datastructure metadata. Defaults to `None`.
        """
        if metadata is None:
            element_size = np.dtype("uint8").itemsize
            frame_buf_num_bytes = mem_size * element_size
            index_num_bytes = buf_len * 2 * np.dtype("uint64").itemsize

            self.shared_memory = shared_memory.SharedMemory(
                create=True, size=frame_buf_num_bytes + index_num_bytes
            )
            self.metadata = RawBytesSharedMemoryCircularBufferMetadata(
                buf_len=buf_len,
                mem_size=mem_size,
                data_type="uint8",
                sample_size=sample_size,
                element_size=element_size,
                shm_id=self.shared_memory.name,
            )
        else:
            self.shared_memory = shared_memory.SharedMemory(name=metadata.shm_id)
            self.metadata = metadata

        # Flat byte buffer.
        self.mem_size = mem_size
        self.buffer = np.ndarray(
            shape=[self.mem_size],
            dtype="uint8",
            buffer=self.shared_memory.buf,
        )

        # Index buffer mapping frames to offsets and sizes, bound at an offset past the flat buffer.
        self.buf_len = buf_len
        self.index_buffer = np.ndarray(
            shape=[self.buf_len, 2],
            dtype="uint64",
            buffer=self.shared_memory.buf,
            offset=self.mem_size,
        )

    def push_unprotected(
        self,
        bundle_name: str,
        channel_name: str,
        new_data: bytes,
        write_tail: int,
        write_head: int,
        num_elements: int,
    ) -> None:
        """In-place update of the shared circular buffer of raw variable-length bytes.

        Args:
            bundle_name (str): Valid data bundle name.
            channel_name (str): Valid data channel name.
            new_data (bytes): Raw bytes for the new data frame.
            write_tail (int): Pointer to the bottom address (start) of the write region in the circular buffer (index array).
            write_head (int): Pointer to the top address (end) of the write region in the circular buffer (index array).
            num_elements (int): Total number of samples being written.
        """
        # Retrieve the previous frame's end offset to know where to start writing.
        num_bytes = len(new_data)
        oldest_index = (write_tail - 1) % self.buf_len
        oldest_offset, oldest_num_bytes = self.index_buffer[oldest_index]

        write_tail_buf = (oldest_offset.item() + oldest_num_bytes.item()) % self.mem_size
        write_head_buf = (write_tail_buf + num_bytes) % self.mem_size

        # Update index with pointers for each added frame, respecting the wrap-around of the index array.
        # TODO: make work in case `new_data` contains more than a single frame.
        if num_elements > 1:
            raise NotImplementedError("Pushing more than 1 frame of raw bytes.")
        else:
            self.index_buffer[write_tail] = [write_tail_buf, num_bytes]

        # Write target data, respecting the wrap-around of the raw bytes buffer.
        if write_tail_buf < write_head_buf:
            self.buffer[write_tail_buf:write_head_buf] = np.frombuffer(new_data, dtype=np.uint8)
        else:
            first_part = self.mem_size - write_tail_buf
            self.buffer[write_tail_buf:] = np.frombuffer(new_data[:first_part], dtype=np.uint8)
            self.buffer[:write_head_buf] = np.frombuffer(new_data[first_part:], dtype=np.uint8)

    def pop_unprotected(self, start: int, end: int) -> List[np.ndarray]:
        """Provides contiguous views over the requested sample range.

        Args:
            start (int): Index of the oldest sample to pop.
            end (int): Index of the newest sample to pop.

        Returns:
            List[np.ndarray]: List of 1D views over the requested frames. Wrap-around frames will be 2 contiguous views.
        """
        start_pointer = self.index_buffer[start, 0].item()
        end_pointer = np.sum(self.index_buffer[(end - 1) % self.buf_len]).item() % self.mem_size

        if start_pointer < end_pointer:
            return [self.buffer[start_pointer:end_pointer]]
        else:
            return [self.buffer[start_pointer:], self.buffer[:end_pointer]]

    def close(self) -> None:
        self.shared_memory.close()

    def unlink(self) -> None:
        self.shared_memory.unlink()
