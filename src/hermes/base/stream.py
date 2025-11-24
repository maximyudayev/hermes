############
#
# Copyright (c) 2024-2025 Maxim Yudayev and KU Leuven eMedia Lab
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

from abc import ABC, abstractmethod

import copy
from collections import OrderedDict, deque
from typing import Any, Dict, Iterable, Iterator, Mapping
from threading import Lock

from hermes.utils.time_utils import get_time
from hermes.utils.types import (
    VideoFormatEnum,
    DataFifoDict,
    DeviceLockDict,
    ExtraDataInfoDict,
    NewDataDict,
    StreamInfoDict,
)


class Stream(ABC):
    """An abstract class to store data of a Node.

    Tree-like structure of FIFO buffers. May contain multiple sub-streams
    for a single device, e.g. acceleration and gyroscope of an IMU.

    Data for sub-streams under the same device tree arrives as a single packet.
    Packets containing decoupled data are better treated as independent device trees.

    Uses a lock for each device tree to delegate access to the start of the FIFO:
    ensures high performance from parallel acquisition, processing, and logging blocks.
    This allows the end of the FIFO to be saved and discarded by the Storage.

    Will store the class name of each sensor in HDF5 metadata.

    Can periodically clear old data (if needed).
    """

    metadata_class_name_key = "Stream class name"
    metadata_data_headings_key = "Data headings"

    _data: DataFifoDict
    _streams_info: StreamInfoDict
    _locks: DeviceLockDict

    def __init__(self) -> None:
        self._data = dict()
        self._streams_info = dict()
        self._locks = dict()

    ############################
    ###### INTERFACE FLOW ######
    ############################
    @abstractmethod
    def get_fps(self) -> dict[str, float | None]:
        """Get effective frame rate of this unique stream's captured data.

        Subject to expected transmission delay and throughput limitation.
        Computed based on how fast data becomes available to the data structure.
        Used to measure the performance of the system - local or remote nodes.

        Returns:
            dict[str, float | None]: Mapping of measured FPS to stream names.
        """
        pass

    #############################
    ###### GETTERS/SETTERS ######
    #############################
    def add_stream(
        self,
        device_name: str,
        stream_name: str,
        data_type: str,
        sample_size: Iterable[int],
        sampling_rate_hz: float = 0.0,
        is_measure_rate_hz: bool = False,
        data_notes: Mapping[str, str] = {},
        is_video: bool = False,
        color_format: VideoFormatEnum | None = None,
        is_audio: bool = False,
        timesteps_before_solidified: int = 0,
        extra_data_info: ExtraDataInfoDict = {},
    ) -> None:
        """Add a new sub-stream to an existing device tree or creates new.

        Will by default add a stream for each device to mark each captured sample
        with the host's time-of-arrival.

        Args:
            device_name (str): Device tree name. Will autocreate if doesn't exist.
            stream_name (str): Unique sub-stream name under this device tree.
            data_type (str): Fixed data type expected in the sub-stream.
            sample_size (Iterable[int]): An interable of dimensions of given data type in each captured sample.
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
        if stream_name == "process_time_s":
            raise ValueError("'process_time_s' is reserved for Stream internal use.")
        self._add_stream(
            device_name=device_name,
            stream_name=stream_name,
            data_type=data_type,
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
        if "process_time_s" not in self._data[device_name]:
            self._add_stream(
                device_name=device_name,
                stream_name="process_time_s",
                data_type="float64",
                sample_size=(1,),
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

    def _add_stream(
        self,
        device_name: str,
        stream_name: str,
        data_type: str,
        sample_size: Iterable[int],
        sampling_rate_hz: float = 0.0,
        is_measure_rate_hz: bool = False,
        data_notes: Mapping[str, str] = {},
        is_video: bool = False,
        color_format: VideoFormatEnum | None = None,
        is_audio: bool = False,
        timesteps_before_solidified: int = 0,
        extra_data_info: ExtraDataInfoDict = {},
    ) -> None:
        """[Internal] Underlying logic for adding a stream.

        Raises:
            KeyError: If supplied color format is not supported or misspelled.
        """
        self._locks.setdefault(device_name, Lock())
        self._streams_info.setdefault(device_name, dict())
        if not isinstance(sample_size, Iterable):
            sample_size = [sample_size]
        self._streams_info[device_name][stream_name] = dict(
            [
                ("data_type", data_type),
                ("sample_size", sample_size),
                ("data_notes", data_notes),
                ("sampling_rate_hz", "%.2f" % sampling_rate_hz),
                ("is_measure_rate_hz", is_measure_rate_hz),
                ("is_video", is_video),
                ("is_audio", is_audio),
                ("timesteps_before_solidified", timesteps_before_solidified),
                ("extra_data_info", extra_data_info),
            ]
        )
        # Record color formats to use by FFmpeg, for saving and displaying frames.
        if is_video:
            try:
                if color_format is not None:
                    self._streams_info[device_name][stream_name][
                        "format"
                    ] = color_format.value.format
                    self._streams_info[device_name][stream_name][
                        "color"
                    ] = color_format.value.color
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
            self._streams_info[device_name][stream_name][
                "actual_rate_hz"
            ] = sampling_rate_hz
            # Create a circular buffer of 1 second, w.r.t. desired sample rate
            circular_buffer_len: int = max(round(sampling_rate_hz), 1)
            self._streams_info[device_name][stream_name]["dt_circular_buffer"] = list(
                [1 / sampling_rate_hz] * circular_buffer_len
            )
            self._streams_info[device_name][stream_name]["dt_circular_index"] = 0
            self._streams_info[device_name][stream_name]["dt_running_sum"] = 1.0
            self._streams_info[device_name][stream_name]["old_toa"] = get_time()
        self.clear_data(device_name, stream_name)

    def append_data(self, process_time_s: float, data: NewDataDict) -> None:
        """Thread-safe append of new sample to the stream.

        Locks the device tree of the sub-stream, to avoid immutability error
        in reverse iterator of the GUI thread when trying to peek N newest
        samples of the stream while new are written.

        Args:
            process_time_s (float): Time-of-processing of the sample.
            data (NewDataDict): Newly processed sample.
        """
        for device_name, streams_data in data.items():
            if streams_data is not None:
                self._locks[device_name].acquire()
                for stream_name, stream_data in streams_data.items():
                    self._append(device_name, stream_name, stream_data)
                self._append(device_name, "process_time_s", process_time_s)
                self._locks[device_name].release()

    def _append(self, device_name: str, stream_name: str, data: Any) -> None:
        """[Internal] Non thread-safe append of new sample."""
        self._data[device_name][stream_name].append(data)

        # If stream set to measure actual fps
        # TODO: cleanup to use a fixed-length Deque instead.
        if self._streams_info[device_name][stream_name]["is_measure_rate_hz"]:
            # Make intermediate variables for current and previous samples' time-of-arrival
            new_toa = get_time()
            old_toa = self._streams_info[device_name][stream_name]["old_toa"]
            # Record the new arrival time for the next iteration
            self._streams_info[device_name][stream_name]["old_toa"] = new_toa
            # Update the running sum of time increments of the circular buffer
            oldest_dt = self._streams_info[device_name][stream_name][
                "dt_circular_buffer"
            ][self._streams_info[device_name][stream_name]["dt_circular_index"]]
            newest_dt = new_toa - old_toa
            self._streams_info[device_name][stream_name]["dt_running_sum"] += (
                newest_dt - oldest_dt
            )
            # Put current time increment in place of the oldest one in the circular buffer
            self._streams_info[device_name][stream_name]["dt_circular_buffer"][
                self._streams_info[device_name][stream_name]["dt_circular_index"]
            ] = newest_dt
            # Move the index in the circular fashion
            self._streams_info[device_name][stream_name]["dt_circular_index"] = (
                self._streams_info[device_name][stream_name]["dt_circular_index"] + 1
            ) % len(self._streams_info[device_name][stream_name]["dt_circular_buffer"])
            # Refresh the actual frame rate information
            self._streams_info[device_name][stream_name]["actual_rate_hz"] = (
                len(self._streams_info[device_name][stream_name]["dt_circular_buffer"])
                / self._streams_info[device_name][stream_name]["dt_running_sum"]
            )

    def pop_data(
        self,
        device_name: str,
        stream_name: str,
        num_oldest_to_pop: int | None = None,
        is_flush: bool = False,
    ) -> Iterator[Any]:
        """Wrap all samples ready to be popped in an iterator oldest->newest.

        Used by Storage to flush data to disk.
        Popped data is cleared from memory.
        Thread-safe without locks while appending new data.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
            num_oldest_to_pop (int | None, optional): Number of samples to pop. Defaults to `None`.
            is_flush (bool, optional): Whether to pop all data in the stream, regardless of timesteps_before_solidified. Defaults to `False`.

        Yields:
            Iterator[Any]: Iterator over poppable oldest->newest samples.
        """
        # O(1) complexity to check length of a Deque.
        num_available: int = len(self._data[device_name][stream_name])
        # Can pop all available data, except what must be kept peekable.
        num_poppable: int = (
            num_available
            - self._streams_info[device_name][stream_name][
                "timesteps_before_solidified"
            ]
        )
        # If experiment ended, flush all available data from the Stream.
        if is_flush:
            num_oldest_to_pop = num_available
        elif num_oldest_to_pop is None:
            num_oldest_to_pop = num_poppable
        else:
            num_oldest_to_pop = min(num_oldest_to_pop, num_poppable)
        # Iterate through the doubly-linked list, clearing popped data, while new data is added to it.
        num_popped: int = 0
        while num_popped < num_oldest_to_pop:
            yield self._data[device_name][stream_name].popleft()
            num_popped += 1

    def peek_data_new(
        self, device_name: str, stream_name: str, num_newest_to_peek: int | None = None
    ) -> Iterator[Any]:
        """Wrap N newest samples in an iterator to peek.

        Will lock the device tree of the sub-stream to prevent appends muttating the iterator.
        Will allow popping of the oldest data (e.g. for Storage to flush).
        Peeking and popping ranges are protected by `timesteps_before_solidified`.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
            num_newest_to_peek (int | None, optional): Number of samples to peek, if less than `timesteps_before_solidified`. Defaults to `None`.

        Yields:
            Iterator[Any]: Iterator over peekable newest samples.
        """
        self._locks[device_name].acquire()
        num_peekable: int = min(
            self._streams_info[device_name][stream_name]["timesteps_before_solidified"],
            len(self._data[device_name][stream_name]),
        )
        if num_newest_to_peek is None:
            num_newest_to_peek = num_peekable
        else:
            num_newest_to_peek = min(
                num_newest_to_peek,
                self._streams_info[device_name][stream_name][
                    "timesteps_before_solidified"
                ],
            )
        num_peeked: int = 0
        # Get an iterator to traverse the linked list from the write end (newest data) -> O(1).
        stream_reversed = reversed(self._data[device_name][stream_name])
        while num_peeked < num_newest_to_peek:
            yield next(stream_reversed)
            num_peeked += 1
        self._locks[device_name].release()

    def clear_data(
        self, device_name: str, stream_name: str, num_oldest_to_clear: int | None = None
    ) -> None:
        """Clear data in a stream.

        Initializes the sub-stream if it doesn't exist.
        Optionally can clear N oldest samples.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
            num_oldest_to_clear (int | None, optional): Number of oldest samples to clear. Defaults to `None`.
        """
        # Create the device/stream entry if it doesn't exist, else clear it.
        self._data.setdefault(device_name, OrderedDict())
        if stream_name not in self._data[device_name]:
            self._data[device_name][stream_name] = deque()
        elif num_oldest_to_clear is not None:
            # Clearing up to a point in the Deque.
            # Wait until neither Node, nor GUI, append or peek newest data, respectively,
            #   only if clearing past their operating area.
            num_clearable: int = (
                len(self._data[device_name][stream_name])
                - self._streams_info[device_name][stream_name][
                    "timesteps_before_solidified"
                ]
            )
            is_to_lock: bool = not (num_oldest_to_clear < num_clearable)
            num_cleared: int = 0
            if is_to_lock:
                self._locks[device_name].acquire()
            while num_cleared < num_oldest_to_clear:
                self._data[device_name][stream_name].popleft()
                num_cleared += 1
            if is_to_lock:
                self._locks[device_name].release()
        else:
            # Clearing the whole Deque.
            # Wait until neither Node, nor GUI, append or peek newest data, respectively.
            self._locks[device_name].acquire()
            self._data[device_name][stream_name].clear()
            self._locks[device_name].release()

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

    def get_stream_names(self, device_name: str | None = None) -> list[str]:
        """Get the names of sub-streams in a device tree.

        If device_name is None, will assume streams are the same for every device.

        Args:
            device_name (str | None, optional): Name of the device tree to query. Defaults to `None`.

        Returns:
            list[str]: Names of sub-streams in a device tree.
        """
        if device_name is None:
            device_name = self.get_device_names()[0]
        return list(self._streams_info[device_name].keys())

    def get_stream_info(self, device_name: str, stream_name: str) -> Dict[str, Any]:
        """Get metadata of a sub-stream.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.

        Returns:
            Dict[str, Any]: Metadata dictionary with keys:
                data_type
                is_video
                is_audio
                sample_size
                sampling_rate_hz
                timesteps_before_solidified
                extra_data_info
                data_notes
                if is_measure_rate_hz:
                actual_rate_hz
                dt_circular_buffer
                dt_circular_index
                dt_running_sum
                old_toa
        """
        return self._streams_info[device_name][stream_name]

    def get_stream_info_all(self) -> StreamInfoDict:
        """Get metadata of all sub-streams.

        Returns:
            StreamInfoDict: Nested dictionary of metadata, with device trees and sub-streams as keys.
        """
        return copy.deepcopy(self._streams_info)

    def _get_fps(self, device_name: str, stream_name: str) -> float | None:
        """[Internal] Retrieve the effective sampling rate of a signal, if recorded.

        Records and refreshes rolling statistics on each data structure append over 1-second windows.

        Args:
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.

        Returns:
            float | None: Measured acquisition sampling rate of the sub-stream.
        """
        if self._streams_info[device_name][stream_name]["is_measure_rate_hz"]:
            return self._streams_info[device_name][stream_name]["actual_rate_hz"]
        else:
            return None
