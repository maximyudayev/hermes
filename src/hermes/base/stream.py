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
from typing import Generator, Iterable, Iterator, Mapping, Optional, Dict, Tuple
import numpy as np

from hermes.datastructures.shared_memory import SharedMemoryCircularBuffer
from hermes.utils.time_utils import get_time
from hermes.utils.types import (
    DataContainerInfo,
    DataBundleInfo,
    SharedMemoryCircularBufferMetadata,
    DataChannelInfo,
    VideoFormatEnum,
    ExtraDataInfoDict,
    NewData,
)


@dataclass
class DataContainerReconstructor:
    module_name: str
    class_name: str
    container_info: DataContainerInfo


class DataBundle:
    _name: str
    _data: Dict[str, SharedMemoryCircularBuffer]
    _bundle_info: DataBundleInfo

    def __init__(
        self,
        name: str,
        bundle_info: Optional[DataBundleInfo] = None,
    ) -> None:
        self._name = name
        self._data = dict()
        self._bundle_info = bundle_info or DataBundleInfo()

    def add_channel(
        self,
        channel_name: str,
        data_type: str,
        sample_size: Iterable[int],
        buf_len: int,
        shm_buffer_metadata: Optional[SharedMemoryCircularBufferMetadata] = None,
        sampling_rate_hz: Optional[float] = 0.0,
        is_measure_rate_hz: Optional[bool] = False,
        data_notes: Optional[Mapping[str, str]] = {},
        is_video: Optional[bool] = False,
        color_format: Optional[VideoFormatEnum] = None,
        is_audio: Optional[bool] = False,
        timesteps_before_solidified: Optional[int] = 0,
        extra_data_info: Optional[ExtraDataInfoDict] = {},
    ) -> None:
        """Add a new channel to the data bundle.

        Will by default add a time-of-processing channel for the bundle to mark each
        captured batch of samples with the host's handling time: will have fewer samples
        than the rest of the data for cases when batches of samples are pushed by `Node`.

        Args:
            channel_name (str): Unique channel name under this data bundle.
            data_type (str): Fixed data type expected in the channel.
            sample_size (Iterable[int]): An interable of dimensions of given data type in each captured sample.
            buf_len (int): Size of the underlying circular buffer to preallocate in the shared memory for the channel.
            shm_buffer_metadata (SharedMemoryCircularBufferMetadata, optional): Metadata for binding datastructure to
                an underlying allocated shared memory. Defaults to `None`.
            sampling_rate_hz (float, optional): Expected sampling frequency of the signal. Defaults to `0.0`.
            is_measure_rate_hz (bool, optional): Whether to compute the effective sampling frequency. Defaults to `False`.
            data_notes (Mapping[str, str], optional): Mapping of channels to notes for `Storage` to use in file metadata. Defaults to `{}`.
            is_video (bool, optional): Whether it is a video channel. Defaults to `False`.
            color_format (VideoFormatEnum, optional): One of the supported identifiers (see `types.py`). Defaults to `None`.
            is_audio (bool, optional): Whether it is an audio channel. Defaults to `False`.
            timesteps_before_solidified (int, optional): How many most recent samples to keep in memory before flushing. Defaults to `0`.
            extra_data_info (ExtraDataInfoDict, optional): Additional mapping that will be streamed along with data,
                with at least `data_type` and `sample_size`. Defaults to `{}`.

        Raises:
            ValueError: If channel name is not unique or is reserved.
        """
        if channel_name in ["process_time_s", "count"]:
            raise ValueError(f"`{channel_name}` is reserved for `DataContainer` internal use.")

        self._add_channel(
            channel_name=channel_name,
            data_type=data_type,
            sample_size=sample_size,
            buf_len=buf_len,
            shm_buffer_metadata=shm_buffer_metadata,
            sampling_rate_hz=sampling_rate_hz,
            is_measure_rate_hz=is_measure_rate_hz,
            data_notes=data_notes,
            is_video=is_video,
            color_format=color_format,
            is_audio=is_audio,
            timesteps_before_solidified=timesteps_before_solidified,
            extra_data_info=extra_data_info,
        )

        if "process_time_s" not in self.get_channel_names():
            self._add_channel(
                channel_name="process_time_s",
                data_type="float64",
                sample_size=[1],
                buf_len=buf_len,
                sampling_rate_hz=sampling_rate_hz,
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
        if "count" not in self.get_channel_names():
            self._add_channel(
                channel_name="count",
                data_type="uint16",
                sample_size=[1],
                buf_len=buf_len,
                sampling_rate_hz=sampling_rate_hz,
                data_notes=OrderedDict(
                    [
                        (
                            "Description",
                            "Number of samples pushed in a batch at the same `process_time_s`.",
                        )
                    ]
                ),
            )

    def _add_channel(
        self,
        channel_name: str,
        data_type: str,
        sample_size: Iterable[int],
        buf_len: int,
        shm_buffer_metadata: Optional[SharedMemoryCircularBufferMetadata] = None,
        sampling_rate_hz: Optional[float] = 0.0,
        is_measure_rate_hz: Optional[bool] = False,
        data_notes: Optional[Mapping[str, str]] = {},
        is_video: Optional[bool] = False,
        color_format: Optional[VideoFormatEnum] = None,
        is_audio: Optional[bool] = False,
        timesteps_before_solidified: Optional[int] = 0,
        extra_data_info: Optional[ExtraDataInfoDict] = {},
    ) -> None:
        self._alloc_channel(
            channel_name=channel_name,
            data_type=data_type,
            sample_size=sample_size,
            buf_len=buf_len,
            shm_buffer_metadata=shm_buffer_metadata,
        )
        self._init_channel_info(
            channel_name=channel_name,
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

    def _alloc_channel(
        self,
        channel_name: str,
        data_type: str,
        sample_size: Iterable[int],
        buf_len: int,
        shm_buffer_metadata: Optional[SharedMemoryCircularBufferMetadata],
    ) -> None:
        if channel_name not in self._data:
            self._data[channel_name] = SharedMemoryCircularBuffer(
                buf_len,
                sample_size,
                data_type,
                shm_buffer_metadata,
            )

    def _init_channel_info(
        self,
        channel_name: str,
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
        buffer: SharedMemoryCircularBuffer = self._data[channel_name]

        if not isinstance(sample_size, Iterable):
            sample_size = [sample_size]

        self._bundle_info.channels[channel_name] = DataChannelInfo(
            sampling_rate_hz="%.2f" % sampling_rate_hz,
            shm_buffer_metadata=buffer.get_metadata(),
            is_video=is_video,
            is_audio=is_audio,
            timesteps_before_solidified=timesteps_before_solidified,
            extra_data_info=extra_data_info,
            data_notes=data_notes,
            is_measure_rate_hz=is_measure_rate_hz,
        )

        # Record color formats to use by FFmpeg, for saving and displaying frames.
        if is_video:
            try:
                if color_format is not None:
                    self._bundle_info.channels[channel_name].video_format = color_format.value.format
                    self._bundle_info.channels[channel_name].video_color = color_format.value.color
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
            self._bundle_info.channels[channel_name].actual_rate_hz = sampling_rate_hz
            # Create a circular buffer of 1 second, w.r.t. desired sample rate
            circular_buffer_len: int = max(round(sampling_rate_hz), 1)
            self._bundle_info.channels[channel_name].dt_circular_buffer = list(
                [1 / sampling_rate_hz] * circular_buffer_len
            )
            self._bundle_info.channels[channel_name].dt_circular_index = 0
            self._bundle_info.channels[channel_name].dt_running_sum = 1.0
            self._bundle_info.channels[channel_name].old_toa = get_time()

    def push(self, process_time_s: float, data: Dict[str, np.ndarray]) -> None:
        """Atomic addition of a batch of new samples to the channels of the data bundle.

        Atomically checks if all the channels in the bundle can accommodate the new data.
        If a channel would overlap and drop incoming data - a channel with 
        `BytesSharedMemoryCircularBuffer` underlying data structure - then the samples in the batch
        are symmetrically truncated (preserving the newest samples) for ALL channels in the bundle
        to maintain atomic access and perfect one-to-one relational mapping.

        NOTE: currently not suitable for `BytesSharedMemoryCircularBuffer`.

        Args:
            process_time_s (float): Time-of-processing of the batch of samples.
            data (Dict[str, np.ndarray]): Newly processed batch of samples in the `[N, *sample_size]` shape.
        """
        # Augment the device data dictionary.
        data["process_time_s"] = np.array([[process_time_s]], dtype=np.float64)
        num_elements = data["toa_s"].shape[0]
        data["count"] = np.array([[num_elements]], dtype=np.uint16)

        metadata = self._bundle_info.metadata
        with metadata.lock:
            # Calculate the free space in the bundle.
            metadata.is_writing.value = True
            buf = self._data["toa_s"]
            write_tail = metadata.write_head.value
            
            free_space = (metadata.read_tail.value - write_tail - 1) % buf.buf_len
            if num_elements > free_space:
                num_elements = free_space
            
            write_head = (write_tail + num_elements) % buf.buf_len

        if num_elements == 0:
            with metadata.lock:
                metadata.is_writing.value = False
            return

        # Execute atomic write for all streams, trimming all arrays identically if circular buffer's head cathes onto the tail.
        for channel_name, channel_data in data.items():
            self._data[channel_name].push_unprotected(
                bundle_name=self._name,
                channel_name=channel_name,
                new_data=channel_data[-num_elements:],
                write_tail=write_tail,
                write_head=write_head,
                num_elements=num_elements,
            )

            # If stream set to measure actual fps.
            if self._bundle_info.channels[channel_name].is_measure_rate_hz:
                # Make intermediate variables for current and previous samples' time-of-arrival.
                new_toa = get_time()
                old_toa = self._bundle_info.channels[channel_name].old_toa
                # Record the new arrival time for the next iteration.
                self._bundle_info.channels[channel_name].old_toa = new_toa
                # Update the running sum of time increments of the circular buffer.
                oldest_dt = self._bundle_info.channels[channel_name].dt_circular_buffer[
                    self._bundle_info.channels[channel_name].dt_circular_index
                ]
                newest_dt = new_toa - old_toa
                self._bundle_info.channels[channel_name].dt_running_sum += (
                    newest_dt - oldest_dt
                )
                # Put current time increment in place of the oldest one in the circular buffer
                self._bundle_info.channels[channel_name].dt_circular_buffer[
                    self._bundle_info.channels[channel_name].dt_circular_index
                ] = newest_dt
                # Move the index in the circular fashion
                self._bundle_info.channels[channel_name].dt_circular_index = (
                    self._bundle_info.channels[channel_name].dt_circular_index + 1
                ) % len(self._bundle_info.channels[channel_name].dt_circular_buffer)
                # Refresh the actual frame rate information
                self._bundle_info.channels[channel_name].actual_rate_hz = (
                    len(self._bundle_info.channels[channel_name].dt_circular_buffer)
                    / self._bundle_info.channels[channel_name].dt_running_sum
                )
        with metadata.lock:
            metadata.write_head.value = write_head
            metadata.is_writing.value = False

    def pop(
        self,
        num_oldest_to_pop: Optional[int] = None,
        is_flush: Optional[bool] = False,
    ) -> Generator[Tuple[str, np.ndarray]]:
        """Wrap all samples ready to be popped in views over shared memory NumPy arrays.

        Args:
            num_oldest_to_pop (int, optional): Number of samples to pop. Defaults to `None`.
            is_flush (bool, optional): Whether to pop all data in the stream, regardless of timesteps_before_solidified. Defaults to `False`.

        Returns:
            Generator[Tuple[str, np.ndarray]]: Generator over poppable views of samples (oldest->newest) of each stream.
        """
        metadata = self._bundle_info.metadata
        # Reserve the current unread data range.
        with metadata.lock:
            metadata.is_reading.value = True
            metadata.read_head.value = metadata.write_head.value
            num_available = (
                metadata.read_head.value - metadata.read_tail.value
            ) % self._data["toa_s"].buf_len
            start = metadata.read_tail.value

        # Can pop all available data, except what must be kept peekable.
        num_poppable: int = max(0,
            num_available
            - self._bundle_info.channels["toa_s"].timesteps_before_solidified
        )
        # If experiment ended, flush all available data from the `DataContainer`.
        if is_flush:
            num_oldest_to_pop = num_available
        elif num_oldest_to_pop is None:
            num_oldest_to_pop = num_poppable
        else:
            num_oldest_to_pop = min(num_oldest_to_pop, num_poppable)

        end = (start + num_oldest_to_pop) % self._data["toa_s"].buf_len

        def _generator() -> Iterator[Tuple[str, np.ndarray]]:
            try:
                # Create an iterator of views over the data.
                if num_oldest_to_pop > 0:
                    for channel_name, channel in self._data.items():
                        for view in channel.pop_unprotected(start, end):
                            yield channel_name, view
            finally:
                # Release read reservations on buffer ranges, to allow `Node` to overwrite it.
                with metadata.lock:
                    if num_oldest_to_pop > 0:
                        metadata.read_tail.value = (
                            metadata.read_tail.value + num_oldest_to_pop
                        ) % self._data["toa_s"].buf_len
                    metadata.is_reading.value = False

        return _generator()

    def clear(
        self,
        num_oldest_to_clear: Optional[int] = None,
    ) -> None:
        """Clear all or N oldest samples in the bundle.

        NOTE: Only changes metadata.

        Args:
            num_oldest_to_clear (int): Number of oldest samples to clear. Defaults to `None`.
        """
        metadata = self._bundle_info.metadata
        with metadata.lock:
            metadata.read_head.value = metadata.write_head.value
            num_available = (
                metadata.read_head.value - metadata.read_tail.value
            ) % self._data["toa_s"].buf_len

            if num_oldest_to_clear is None:
                num_oldest_to_clear = num_available
            else:
                num_oldest_to_clear = min(num_oldest_to_clear, num_available)

            if num_oldest_to_clear > 0:
                metadata.read_tail.value = (
                    metadata.read_tail.value + num_oldest_to_clear
                ) % self._data["toa_s"].buf_len

    def close(self) -> None:
        for channel_name, channel in self._data.items():
            channel.close()

    def unlink(self) -> None:
        for channel_name, channel in self._data.items():
            channel.unlink()

    def get_channel_names(self) -> list[str]:
        """Get the names of channels in the atomic data bundle.

        Returns:
            list[str]: Names of data channels in the bundle.
        """
        return list(self._data.keys())

    def get_info(
        self,
        channel_name: str,
    ) -> DataChannelInfo:
        """Get metadata of a data channel.

        Args:
            channel_name (str): Valid data channel name.

        Returns:
            ChannelInfo: Metadata dictionary describing the data channel.
        """
        return self._bundle_info.channels[channel_name]
    
    def get_info_all(self) -> DataBundleInfo:
        return self._bundle_info


class DataContainer(ABC):
    """An abstract hierarchical container for holding data of a `Node`.

    Tree-like structure of bundles of channels of circular shared memory FIFO buffers.
    May contain multiple channels for a single bundle (e.g. acceleration and gyroscope of an IMU).

    Channels under the same bundle are atomic to preserve one-to-one mapping of data
    arriving as a single packet (e.g. from a sensor).
    Packets containing decoupled data (e.g. not guaranteed to be of equal length and consumed separately)
    are better split into independent bundles.

    Uses multiprocessing `Lock` protected metadata for atomic access to the underlying circular FIFOs contained
    in a bundle, to coordinate non-blocking (when possible) thread-safe access to the FIFO ranges:
    ensures high-performance parallel acquisition, processing, and logging.

    Permanent storing is managed by the `Storage`: continuously flushes data to disk at specified intervals.
    Will log the class name of the parent data logging component in the files metadata.

    TODO: run validator after construction to check that each bundle contains a `toa_s` channel.
    """

    metadata_class_name_key = "Container class name"
    metadata_data_headings_key = "Data headings"

    _data: Dict[str, DataBundle]
    _container_info: DataContainerInfo

    def __init__(self) -> None:
        self._data = dict()
        self._container_info = dict()

    @classmethod
    def create_from_metadata(cls, container_info: DataContainerInfo):
        container = cls()
        for bundle_name, bundle_info in container_info.items():
            for channel_name, channel_info in bundle_info.channels.items():
                container.set_channel(
                    bundle_name=bundle_name,
                    channel_name=channel_name,
                    data_type=channel_info.shm_buffer_metadata.data_type,
                    sample_size=channel_info.shm_buffer_metadata.sample_size,
                    buf_len=channel_info.shm_buffer_metadata.buf_len,
                    shm_buffer_metadata=channel_info.shm_buffer_metadata,
                    bundle_info=bundle_info,
                )
        return container

    def add_channel(
        self,
        bundle_name: str,
        channel_name: str,
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
        """Add a new data channel to the container, creating a bundle if it does not exist.

        Args:
            bundle_name (str): Data bundle name. Will be auto-created if it does not exist.
            channel_name (str): Unique channel name under this data bundle.
            data_type (str): Fixed data type expected in the channel.
            sample_size (Iterable[int]): An interable of dimensions of given data type in each captured sample.
            buf_len (int): Size of the underlying circular buffer to preallocate in the shared memory for the channel.
            sampling_rate_hz (float, optional): Expected sampling frequency of the signal. Defaults to `0.0`.
            is_measure_rate_hz (bool, optional): Whether to compute the effective sampling frequency. Defaults to `False`.
            data_notes (Mapping[str, str], optional): Mapping of channels to notes for `Storage` to use in file metadata. Defaults to `{}`.
            is_video (bool, optional): Whether it is a video channel. Defaults to `False`.
            color_format (VideoFormatEnum, optional): One of the supported identifiers (see `types.py`). Defaults to `None`.
            is_audio (bool, optional): Whether it is an audio channel. Defaults to `False`.
            timesteps_before_solidified (int, optional): How many most recent samples to keep in memory before flushing. Defaults to `0`.
            extra_data_info (ExtraDataInfoDict, optional): Additional mapping that will be streamed along with data,
                with at least 'data_type' and 'sample_size'. Defaults to `{}`.
        """
        if bundle_name not in self._data:
            self._data[bundle_name] = DataBundle(bundle_name)
        self._data[bundle_name].add_channel(
            channel_name=channel_name,
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

    def set_channel(
        self,
        bundle_name: str,
        channel_name: str,
        data_type: str,
        sample_size: Iterable[int],
        buf_len: int,
        shm_buffer_metadata: SharedMemoryCircularBufferMetadata,
        bundle_info: DataBundleInfo,
    ) -> None:
        if bundle_name not in self._data:
            self._data[bundle_name] = DataBundle(bundle_name, bundle_info)
        self._data[bundle_name]._alloc_channel(
            channel_name=channel_name,
            data_type=data_type,
            sample_size=sample_size,
            buf_len=buf_len,
            shm_buffer_metadata=shm_buffer_metadata,
        )

    def push(self, process_time_s: float, data: NewData) -> None:
        """Addition (of bundles) of a batch of new samples to the data container.

        Args:
            process_time_s (float): Time-of-processing of the batch of samples.
            data (NewDataDict): Newly processed batch of samples for (multiple) bundles.
        """
        for bundle_name, bundle_data in data.items():
            if bundle_data is not None:
                self._data[bundle_name].push(process_time_s, bundle_data)

    def pop(
        self,
        bundle_name: str,
        num_oldest_to_pop: Optional[int] = None,
        is_flush: Optional[bool] = False,
    ) -> Generator[Tuple[str, np.ndarray]]:
        """Wrap all samples ready to be popped in views over shared memory.

        Used by `Storage` to flush data to disk.

        Args:
            bundle_name (str): Valid data bundle name.
            num_oldest_to_pop (int, optional): Number of samples to pop. Defaults to `None`.
            is_flush (bool, optional): Whether to pop all data in the atomic bundle, regardless of `timesteps_before_solidified`. Defaults to `False`.

        Returns:
            Generator[Tuple[str, np.ndarray]]: Generator over poppable views of samples (oldest->newest) of each named data channel.
        """
        return self._data[bundle_name].pop(num_oldest_to_pop, is_flush)

    def clear(self, bundle_name: str, num_oldest_to_clear: Optional[int] = None) -> None:
        self._data[bundle_name].clear(num_oldest_to_clear)

    def clear_all(self) -> None:
        """Clear all chanenls from all atomic data bundles."""
        for bundle_name, bundle in self._data.items():
            bundle.clear()

    def close_all(self) -> None:
        """Close access to all channels' `SharedMemoryCircularBuffer`s from all bundles."""
        for bundle_name, bundle in self._data.items():
            bundle.close()

    def unlink_all(self) -> None:
        """Free allocated memory from all channels of all atomic data bundles.
        
        NOTE: Must be called only once, from the corresponding `Node`,
            after all subprocesses closed shared access to it.
        """
        for bundle_name, bundle in self._data.items():
            bundle.unlink()

    def get_num_bundles(self) -> int:
        """Get the number of atomic data bundles.

        Returns:
            int: Number of data bundles.
        """
        return len(self._data.keys())

    def get_bundle_names(self) -> list[str]:
        """Get the names of atomic data bundles.

        Returns:
            list[str]: Names of data bundles.
        """
        return list(self._data.keys())

    def get_channel_names(self, bundle_name: str) -> list[str]:
        """Get the names of channels in a data bundle.

        Args:
            bundle_name (str): Name of the data bundle to query.

        Returns:
            list[str]: Names of data channels in a bundle.
        """
        return list(self._data[bundle_name].get_channel_names())

    def get_info(
        self,
        bundle_name: str,
        channel_name: str,
    ) -> DataChannelInfo:
        """Get metadata of a data channel.

        Args:
            bundle_name (str): Valid data bundle name.
            channel_name (str): Valid data channel name.

        Returns:
            DataContainerMetadata: Metadata dictionary describing the sub-stream.
        """
        return self._data[bundle_name].get_info(channel_name)

    def get_info_all(self) -> DataContainerInfo:
        """Get metadata of all bundle-channel pairs.

        Returns:
            DataContainerInfo: Nested dictionary of metadata, with bundle and channel names as keys.
        """
        return {bundle_name: bundle.get_info_all() for bundle_name, bundle in self._data.items()}

    # def _get_fps(
    #     self,
    #     bundle_name: str,
    #     channel_name: str
    # ) -> float | None:
    #     """Retrieve the effective sampling rate of a channel, if recorded.

    #     Args:
    #         bundle_name (str): Valid data bundle name.
    #         channel_name (str): Valid data channel name.

    #     Returns:
    #         float | None: Measured acquisition sampling rate of the channel.
    #     """
    #     if self._container_info[bundle_name][channel_name].is_measure_rate_hz:
    #         return self._container_info[bundle_name][channel_name].actual_rate_hz
    #     else:
    #         return None

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
