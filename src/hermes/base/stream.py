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
# Created 2024-2025 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Maxim Yudayev [https://yudayev.com].
#
# ############

from abc import ABC
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Optional, Dict, TypeAlias
import numpy as np

from hermes.datastructures.shared_memory import SharedMemoryCircularBuffer
from hermes.utils.time_utils import get_time
from hermes.utils.types import (
    SharedMemoryCircularBufferMetadata,
    StreamMetadataDictionary,
    VideoFormatEnum,
    ExtraDataInfoDict,
    NewDataDict,
    StreamInfoDict,
)

StreamFifoDict: TypeAlias = Dict[str, Dict[str, SharedMemoryCircularBuffer]]


@dataclass
class StreamReconstructor:
    module_name: str
    class_name: str
    stream_info: StreamInfoDict


class Stream(ABC):
    """An abstract class to hold data of a `Node`.

    Tree-like structure of circular shared memory FIFO buffers.
    May contain multiple sub-streams for a single device (e.g. acceleration and gyroscope of an IMU).

    Data for sub-streams under the same device tree arrives as a single packet (e.g. from sensor).
    Packets containing decoupled data (e.g. not guaranteed to be of equal length and consumed separately)
    are better treated as independent device trees.

    Uses multiprocessing `Lock` protected metadata for underlying circular FIFOs contained
    in a device tree, to coordinate non-blocking (when possible) thread-safe access to the FIFO ranges:
    ensures high-performance parallel acquisition, processing, and logging.

    Permanent storing is managed by the `Storage`: continuously flushes data to disk at specified intervals.
    will log the class name of each sensor in the files metadata.
    """

    metadata_class_name_key = "Stream class name"
    metadata_data_headings_key = "Data headings"

    _data: StreamFifoDict
    _streams_info: StreamInfoDict

    def __init__(self) -> None:
        self._data = dict()
        self._streams_info = dict()

    @classmethod
    def create_from_metadata(cls, streams_info_all: StreamInfoDict) -> Stream:
        stream = cls()
        stream._streams_info = streams_info_all
        for device_name, device_info in stream._streams_info.items():
            for stream_name, stream_info in device_info.items():
                stream._init_stream_data(
                    device_name=device_name,
                    stream_name=stream_name,
                    data_type=stream_info.metadata.data_type,
                    sample_size=stream_info.metadata.sample_size,
                    buf_len=stream_info.metadata.buf_len,
                    metadata=stream_info.metadata,
                )
        return stream

    ############################
    ###### INTERFACE FLOW ######
    ############################
    # @abstractmethod
    # def get_fps(self) -> dict[str, float | None]:
    #     """Get effective frame rate of this unique stream's captured data.

    #     Subject to expected transmission delay and throughput limitation.
    #     Computed based on how fast data becomes available to the data structure.
    #     Used to measure the performance of the system - local or remote nodes.

    #     Returns:
    #         dict[str, float | None]: Mapping of measured FPS to stream names.
    #     """
    #     pass

    #############################
    ###### GETTERS/SETTERS ######
    #############################
    def add_stream(
        self,
        device_name: str,
        stream_name: str,
        data_type: str,
        sample_size: Iterable[int],
        buf_len: int,
        sampling_rate_hz: Optional[float] = 0.0,
        is_measure_rate_hz: Optional[bool] = False,
        data_notes: Optional[Mapping[str, str]] = {},
        is_video: Optional[bool] = False,
        color_format: Optional[VideoFormatEnum] = None,
        is_audio: Optional[bool] = False,
        timesteps_before_solidified: Optional[int] = 0,
        extra_data_info: Optional[ExtraDataInfoDict] = {},
    ) -> None:
        """Add a new sub-stream to an existing device tree or creates new.

        Will by default add a stream for each device to mark each captured sample
        with the host's time-of-arrival.

        Args:
            device_name (str): Device tree name. Will autocreate if doesn't exist.
            stream_name (str): Unique sub-stream name under this device tree.
            data_type (str): Fixed data type expected in the sub-stream.
            sample_size (Iterable[int]): An interable of dimensions of given data type in each captured sample.
            buf_len (int): Size of the circular buffer to preallocate in the shared memory for the stream.
            sampling_rate_hz (float, optional): Expected sampling frequency of the signal. Defaults to `0.0`.
            is_measure_rate_hz (bool, optional): Whether to compute the effective sampling frequency. Defaults to `False`.
            data_notes (Mapping[str, str], optional): Mapping of streams to notes for Storage to use in file metadata. Defaults to `{}`.
            is_video (bool, optional): Whether it is a video stream. Defaults to `False`.
            color_format (VideoFormatEnum | None, optional): One of the supported identifiers (see `types.py`). Defaults to `None`.
            is_audio (bool, optional): Whether it is an audio stream. Defaults to `False`.
            timesteps_before_solidified (int, optional): How many most recent samples to keep in memory before flushing. Defaults to `0`.
            extra_data_info (ExtraDataInfoDict, optional): Additional mapping that will be streamed along with data,
                with at least 'data_type' and 'sample_size'. Defaults to `{}`.

        Raises:
            ValueError: If stream name is not unique or is reserved.
        """
        if stream_name in ["process_time_s", "count"]:
            raise ValueError(f"`{stream_name}` is reserved for `Stream` internal use.")

        self._add_stream(
            device_name=device_name,
            stream_name=stream_name,
            data_type=data_type,
            sample_size=sample_size,
            buf_len=buf_len,
            sampling_rate_hz=sampling_rate_hz,
            is_measure_rate_hz=is_measure_rate_hz,
            data_notes=data_notes,
            is_video=is_video,
            color_format=color_format,
            is_audio=is_audio,
            timesteps_before_solidified=timesteps_before_solidified,
            extra_data_info=extra_data_info,
        )
        if "process_time_s" not in self._data[device_name]:
            self._add_stream(
                device_name=device_name,
                stream_name="process_time_s",
                data_type="float64",
                sample_size=(1,),
                buf_len=buf_len,
                data_notes=OrderedDict(
                    [
                        (
                            "Description",
                            "Time of arrival of the data point to the host PC, "
                            "to be used for aligned idexing of data between distributed hosts.",
                        )
                    ]
                ),
            )
        if "count" not in self._data[device_name]:
            self._add_stream(
                device_name=device_name,
                stream_name="count",
                data_type="uint16",
                sample_size=(1,),
                buf_len=buf_len,
                data_notes=OrderedDict(
                    [
                        (
                            "Description",
                            "Number of samples pushed in a batch at the same `process_time_s`.",
                        )
                    ]
                ),
            )

    def _add_stream(
        self,
        device_name: str,
        stream_name: str,
        data_type: str,
        sample_size: Iterable[int],
        buf_len: int,
        metadata: Optional[SharedMemoryCircularBufferMetadata] = None,
        sampling_rate_hz: Optional[float] = 0.0,
        is_measure_rate_hz: Optional[bool] = False,
        data_notes: Optional[Mapping[str, str]] = {},
        is_video: Optional[bool] = False,
        color_format: Optional[VideoFormatEnum] = None,
        is_audio: Optional[bool] = False,
        timesteps_before_solidified: Optional[int] = 0,
        extra_data_info: Optional[ExtraDataInfoDict] = {},
    ) -> None:
        self._init_stream_data(
            device_name=device_name,
            stream_name=stream_name,
            data_type=data_type,
            sample_size=sample_size,
            buf_len=buf_len,
            metadata=metadata,
        )
        self._init_stream_info(
            device_name=device_name,
            stream_name=stream_name,
            sample_size=sample_size,
            sampling_rate_hz=sampling_rate_hz,
            is_measure_rate_hz=is_measure_rate_hz,
            data_notes=data_notes,
            is_video=is_video,
            color_format=color_format,
            is_audio=is_audio,
            timesteps_before_solidified=timesteps_before_solidified,
            extra_data_info=extra_data_info,
        )

    def _init_stream_data(
        self,
        device_name: str,
        stream_name: str,
        data_type: str,
        sample_size: Iterable[int],
        buf_len: int,
        metadata: Optional[SharedMemoryCircularBufferMetadata],
    ) -> None:
        self._data.setdefault(device_name, OrderedDict())
        if stream_name not in self._data[device_name]:
            self._data[device_name][stream_name] = SharedMemoryCircularBuffer(
                buf_len,
                sample_size,
                data_type,
                metadata,
            )

    def _init_stream_info(
        self,
        device_name: str,
        stream_name: str,
        sample_size: Iterable[int],
        sampling_rate_hz: Optional[float] = 0.0,
        is_measure_rate_hz: Optional[bool] = False,
        data_notes: Optional[Mapping[str, str]] = {},
        is_video: Optional[bool] = False,
        color_format: Optional[VideoFormatEnum] = None,
        is_audio: Optional[bool] = False,
        timesteps_before_solidified: Optional[int] = 0,
        extra_data_info: Optional[ExtraDataInfoDict] = {},
    ) -> None:
        buffer: SharedMemoryCircularBuffer = self._data[device_name][stream_name]

        if not isinstance(sample_size, Iterable):
            sample_size = [sample_size]

        self._streams_info.setdefault(device_name, dict())
        self._streams_info[device_name][stream_name] = StreamMetadataDictionary(
            metadata=buffer.get_metadata(),
            sampling_rate_hz="%.2f" % sampling_rate_hz,
            is_measure_rate_hz=is_measure_rate_hz,
            is_video=is_video,
            is_audio=is_audio,
            timesteps_before_solidified=timesteps_before_solidified,
            extra_data_info=extra_data_info,
            data_notes=data_notes,
        )

        # Record color formats to use by FFmpeg, for saving and displaying frames.
        if is_video:
            try:
                if color_format is not None:
                    self._streams_info[device_name][
                        stream_name
                    ].video_format = color_format.value.format
                    self._streams_info[device_name][
                        stream_name
                    ].video_color = color_format.value.color
                else:
                    raise KeyError
            except KeyError:
                print(
                    "Color format %s is not supported when specifying video frame pixel color format on Stream."
                    % color_format
                )

        # Some metadata to keep track of during running to measure the actual frame rate.
        if is_measure_rate_hz:
            # Set at start actual rate equal to desired sample rate
            self._streams_info[device_name][
                stream_name
            ].actual_rate_hz = sampling_rate_hz
            # Create a circular buffer of 1 second, w.r.t. desired sample rate
            circular_buffer_len: int = max(round(sampling_rate_hz), 1)
            self._streams_info[device_name][stream_name].dt_circular_buffer = list(
                [1 / sampling_rate_hz] * circular_buffer_len
            )
            self._streams_info[device_name][stream_name].dt_circular_index = 0
            self._streams_info[device_name][stream_name].dt_running_sum = 1.0
            self._streams_info[device_name][stream_name].old_toa = get_time()

    def push(self, process_time_s: float, data: NewDataDict) -> None:
        """Addition of a batch of new samples to the `Stream`.

        Shuffles keys inside the device-tree to limit collisions with `Storage`
        during flushes of data to disk.

        Args:
            process_time_s (float): Time-of-processing of the batch of samples.
            data (NewDataDict): Newly processed batch of samples.
        """
        for device_name, device_data in data.items():
            if device_data is not None:
                for stream_name, stream_data in device_data.items():
                    self._push(device_name, stream_name, stream_data)
                self._push(
                    device_name,
                    "process_time_s",
                    np.array([process_time_s], dtype=np.float64),
                )
                self._push(
                    device_name,
                    "count",
                    np.array([len(device_data["toa_s"])], dtype=np.uint16),
                )

    def _push(self, device_name: str, stream_name: str, data: np.ndarray) -> None:
        """[Internal] Underlying logic for adding new data to a stream.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
            data (np.ndarray): NumPy array of a batch of samples.
        """
        self._data[device_name][stream_name].push(data)

        # If stream set to measure actual fps
        if self._streams_info[device_name][stream_name].is_measure_rate_hz:
            # Make intermediate variables for current and previous samples' time-of-arrival
            new_toa = get_time()
            old_toa = self._streams_info[device_name][stream_name].old_toa
            # Record the new arrival time for the next iteration
            self._streams_info[device_name][stream_name].old_toa = new_toa
            # Update the running sum of time increments of the circular buffer
            oldest_dt = self._streams_info[device_name][stream_name].dt_circular_buffer[
                self._streams_info[device_name][stream_name].dt_circular_index
            ]
            newest_dt = new_toa - old_toa
            self._streams_info[device_name][stream_name].dt_running_sum += (
                newest_dt - oldest_dt
            )
            # Put current time increment in place of the oldest one in the circular buffer
            self._streams_info[device_name][stream_name].dt_circular_buffer[
                self._streams_info[device_name][stream_name].dt_circular_index
            ] = newest_dt
            # Move the index in the circular fashion
            self._streams_info[device_name][stream_name].dt_circular_index = (
                self._streams_info[device_name][stream_name].dt_circular_index + 1
            ) % len(self._streams_info[device_name][stream_name].dt_circular_buffer)
            # Refresh the actual frame rate information
            self._streams_info[device_name][stream_name].actual_rate_hz = (
                len(self._streams_info[device_name][stream_name].dt_circular_buffer)
                / self._streams_info[device_name][stream_name].dt_running_sum
            )

    def pop(
        self,
        device_name: str,
        stream_name: str,
        num_oldest_to_pop: Optional[int] = None,
        is_flush: Optional[bool] = False,
    ) -> Iterator[np.ndarray]:
        """Wrap all samples ready to be popped in views over shared memory NumPy arrays.

        Used by `Storage` to flush data to disk.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
            num_oldest_to_pop (int, optional): Number of samples to pop. Defaults to `None`.
            is_flush (bool, optional): Whether to pop all data in the stream, regardless of timesteps_before_solidified. Defaults to `False`.

        Yields:
            Iterator[np.ndarray]: Iterator over poppable views of samples (oldest->newest).
        """
        # O(1) complexity to check length of the `SharedMemoryCircularBuffer`.
        num_available: int = (
            self._data[device_name][stream_name].get_fill_level().num_samples
        )
        # Can pop all available data, except what must be kept peekable.
        num_poppable: int = (
            num_available
            - self._streams_info[device_name][stream_name].timesteps_before_solidified
        )
        # If experiment ended, flush all available data from the Stream.
        if is_flush:
            num_oldest_to_pop = num_available
        elif num_oldest_to_pop is None:
            num_oldest_to_pop = num_poppable
        else:
            num_oldest_to_pop = min(num_oldest_to_pop, num_poppable)

        views, num_popped = self._data[device_name][stream_name].pop(num_oldest_to_pop)
        for view in views:
            yield view
        self._data[device_name][stream_name].release(num_popped)

    def peek(
        self,
        device_name: str,
        stream_name: str,
        num_newest_to_peek: Optional[int],
    ) -> Iterator[Any]:
        """Wrap N newest samples to peek in views over shared memory NumPy arrays.

        Peeking and popping ranges are protected by `timesteps_before_solidified`.

        TODO: Adjust and test the method after introduction of the `SharedMemoryCircularBuffer`.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid stream name.
            num_newest_to_peek (int, optional): Number of samples to peek, if less than `timesteps_before_solidified`. Defaults to `None`.

        Yields:
            Iterator[np.ndarray]: Iterator over peekable views of newest samples.
        """
        num_peekable: int = min(
            self._streams_info[device_name][stream_name].timesteps_before_solidified,
            len(self._data[device_name][stream_name]),
        )
        if num_newest_to_peek is None:
            num_newest_to_peek = num_peekable
        else:
            num_newest_to_peek = min(
                num_newest_to_peek,
                self._streams_info[device_name][
                    stream_name
                ].timesteps_before_solidified,
            )

        views, num_peeked = self._data[device_name][stream_name].peek(
            num_newest_to_peek
        )
        for view in views:
            yield view
        self._data[device_name][stream_name].release()

    def clear_data(
        self,
        device_name: str,
        stream_name: str,
        num_oldest_to_clear: Optional[int] = None,
    ) -> None:
        """Clear all or N oldest samples in a stream.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
            num_oldest_to_clear (int): Number of oldest samples to clear. Defaults to `None`.
        """
        if num_oldest_to_clear is not None:
            # Clearing up to a point in the FIFO.
            # TODO: Wait until neither Node, nor GUI, append or peek newest data, respectively,
            #   only if clearing past their operating area.
            num_clearable: int = (
                self._data[device_name][stream_name].get_fill_level().num_samples
                - self._streams_info[device_name][
                    stream_name
                ].timesteps_before_solidified
            )
            _, num_cleared = self._data[device_name][stream_name].pop(num_clearable)
            self._data[device_name][stream_name].release(num_cleared)
        else:
            # Clearing the whole FIFO.
            # TODO: Wait until neither Node, nor GUI, append or peek newest data, respectively.
            self._data[device_name][stream_name].clear()

    def clear_data_all(self) -> None:
        """Clear all sub-streams from all device trees."""
        for device_name, device_info in self._streams_info.items():
            for stream_name, stream_info in device_info.items():
                self.clear_data(device_name, stream_name)

    def get_num_devices(self) -> int:
        """Get the number of asynchronous device trees.

        Returns:
            int: Number of device trees.
        """
        return len(self._streams_info)

    def get_device_names(self) -> list[str]:
        """Get the names of the asynchronous device trees.

        Returns:
            list[str]: Names of device trees.
        """
        return list(self._streams_info.keys())

    def get_stream_names(self, device_name: Optional[str] = None) -> list[str]:
        """Get the names of sub-streams in a device tree.

        If device_name is None, will assume streams are the same for every device.

        Args:
            device_name (str, optional): Name of the device tree to query. Defaults to `None`.

        Returns:
            list[str]: Names of sub-streams in a device tree.
        """
        if device_name is None:
            device_name = self.get_device_names()[0]
        return list(self._streams_info[device_name].keys())

    def get_stream_info(
        self, device_name: str, stream_name: str
    ) -> StreamMetadataDictionary:
        """Get metadata of a sub-stream.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.

        Returns:
            StreamMetadataDictionary: Metadata dictionary describing the sub-stream.
        """
        return self._streams_info[device_name][stream_name]

    def get_stream_info_all(self) -> StreamInfoDict:
        """Get metadata of all sub-streams.

        Returns:
            StreamInfoDict: Nested dictionary of metadata, with device trees and sub-streams as keys.
        """
        return self._streams_info

    def _get_fps(self, device_name: str, stream_name: str) -> float | None:
        """[Internal] Retrieve the effective sampling rate of a signal, if recorded.

        Records and refreshes rolling statistics on each data structure append over 1-second windows.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.

        Returns:
            float | None: Measured acquisition sampling rate of the sub-stream.
        """
        if self._streams_info[device_name][stream_name].is_measure_rate_hz:
            return self._streams_info[device_name][stream_name].actual_rate_hz
        else:
            return None
