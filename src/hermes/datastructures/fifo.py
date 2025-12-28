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

from abc import ABC, abstractmethod
import queue
from typing import Any, Callable, Iterable
from collections import OrderedDict, deque


class BufferInterface(ABC):
    """Interface for the multi-channel FIFO buffer."""

    @abstractmethod
    def plop(self, key: str, data: dict) -> None:
        """Asynchronously adds an element to the specified channel of the buffer.

        Args:
            key (str): Unique identifier of the channel to add the data to.
            data (dict): Usecase-specific nested dictionary of data to add.
        """
        pass

    @abstractmethod
    def yeet(self) -> Any:
        """Synchronously retrieves the oldest set of samples from all channels of the buffer.

        Returns:
            Any: Multi-channel vector of the oldest sample.
        """
        pass


class NonOverflowingCounterConverter:
    """A counter value converter from overflowing fixed range to non-overflowing values, starting at 0 for the first received sample.

    Converts overflowing monotonically increasing counter from a sensor into a non-overflowing value,
    starting counting from 0, regardless of device's actual onboard counter.
    """

    def __init__(self, keys: Iterable[Any], num_bits_counter: int):
        """Constructor of the NonOverflowingCounterConverter.

        Args:
            keys (Iterable[Any]): Set of uniquely identifying channel keys.
            num_bits_counter (int): The fixed-width of the counter generating the data.
        """
        self._counter_limit = 2**num_bits_counter
        self._convert_fn: Callable[[Any, int], int | None] = self._foo
        self._start_counters: OrderedDict[Any, int | None] = OrderedDict(
            [(k, None) for k in keys]
        )
        self._previous_counters: OrderedDict[Any, int | None] = OrderedDict(
            [(k, None) for k in keys]
        )
        self._counters: OrderedDict[Any, int | None] = OrderedDict(
            [(k, None) for k in keys]
        )
        self._start_counter = None

    def _foo(self, key: Any, counter: int) -> int | None:
        """Startup multi-channel function that converts correlated over-flowing counter values from asynchronous sensors to a non-overflowing counter.

        Switches to the continuous function when all channels have provided a starting sample.
        Else, reuses this function with branch conditional logic.
        The branched version is not ideal for continuous use, because other conditions never happen after the first iteration of the module on the channel.

        Args:
            key (Any): The unique identifier of the channel.
            counter (int): Monotonically increasing overflowing integer from a sensor.

        Returns:
            int | None: Converted counter value starting at 0 counter value.
        """
        if self._start_counter is None:
            self._start_counter = counter
            self._start_counters[key] = counter
            self._previous_counters[key] = counter
            self._counters[key] = 0
        elif self._previous_counters[key] is None:
            self._start_counters[key] = counter
            self._previous_counters[key] = counter
            dc = (counter - self._start_counter) % self._counter_limit
            self._counters[key] = dc
        else:
            self._bar(key=key, counter=counter)
        if all([counter is not None for counter in self._start_counters.values()]):
            self._convert_fn = self._bar
        return self._counters[key]

    def _bar(self, key: Any, counter: int) -> int | None:
        """Optimized counter converter function for continuous steady-state operation.

        Previous counters are guaranteed to be non-0 after this function is activated.

        Args:
            key (Any): The unique identifier of the channel.
            counter (int): Monotonically increasing overflowing integer from a sensor.

        Returns:
            int | None: Converted counter value starting at 0 counter value.
        """
        dc = (counter - self._previous_counters[key]) % self._counter_limit  # type: ignore
        self._previous_counters[key] = counter
        self._counters[key] += dc
        return self._counters[key]


class TimestampToCounterConverter:
    """A counter value converter from overflowing fixed range timestamp to non-overflowing counter values, starting at 0 for the first received sample.

    Converts overflowing monotonically increasing timestamp of a certain sample rate from a sensor into a non-overflowing counter value,
    starting counting from 0, regardless of device's actual onboard timestamp.
    """

    def __init__(self, keys: Iterable[Any], sampling_period: int, counter_limit: int):
        """Constructor of the TimestampToCounterConverter.

        Args:
            keys (Iterable[Any]): Set of uniquely identifying channel keys.
            sampling_period (int): Sampling period in the same units as timestamp limit and timestamps.
            counter_limit (int): The upper counting limit of the sensor's timestamp.
        """
        self._sampling_period = sampling_period
        self._timestamp_limit: int = counter_limit
        self._counter_from_timestamp_fn: Callable[
            [Any, int | float], int | float | None
        ] = self._foo
        self._first_timestamps: OrderedDict[Any, int | float | None] = OrderedDict(
            [(k, None) for k in keys]
        )
        self._previous_timestamps: OrderedDict[Any, int | float | None] = OrderedDict(
            [(k, None) for k in keys]
        )
        self._counters: OrderedDict[Any, int | None] = OrderedDict(
            [(k, None) for k in keys]
        )

    def _foo(self, key: Any, timestamp: int | float) -> int | float | None:
        """Startup multi-channel function that converts correlated over-flowing timestamp values from asynchronous sensors to a non-overflowing counter.

        Sets the start time according to the first received packet and switches to the monotone calculation routine after.
        Has some tolerance to temporally skewed samples, when the skew is less than hald a sampling period.
        If the channel sample is the first in the overall buffer, will use it as reference starting point onward.
        Will return 0 start counter at the end of the function.

        If it's not the very first packet, but first reading for this device, records if the capture was during or after the start reference.
        If the measurement taken during or after the reference measurement and no chance for overflow, will return 0 start counter at the end of the function.
        If the measurement taken after the overflow of the on-sensor clock and effectively after the reference measurement,
        will return 0 start counter at the end of the function.
        Will discard the sample as stale to ensure alignment otherwise.

        Args:
            key (Any): The unique identifier of the channel.
            timestamp (int): Monotonically increasing overflowing integer from a sensor.

        Returns:
            int | None: Converted counter value starting at 0 counter value.
        """
        if not any([v is not None for v in self._previous_timestamps.values()]):
            self._start_time = timestamp
            self._first_timestamps[key] = timestamp
            self._previous_timestamps[key] = timestamp
            self._counters[key] = 0
        elif self._previous_timestamps[key] is None:
            if timestamp >= self._start_time:
                self._first_timestamps[key] = timestamp
                self._previous_timestamps[key] = timestamp
                self._counters[key] = round(
                    ((timestamp - self._start_time) % self._timestamp_limit)
                    / self._sampling_period
                )
            elif ((timestamp - self._start_time) % self._timestamp_limit) < (
                self._start_time - timestamp
            ):
                self._first_timestamps[key] = timestamp
                self._previous_timestamps[key] = timestamp
                self._counters[key] = round(
                    ((timestamp - self._start_time) % self._timestamp_limit)
                    / self._sampling_period
                )
            else:
                return None
        else:
            self._bar(key=key, timestamp=timestamp)
        if all([v is not None for v in self._previous_timestamps.values()]):
            self._counter_from_timestamp_fn = self._bar
        return self._counters[key]

    def _bar(self, key: Any, timestamp: int | float) -> int | float | None:
        """Optimized counter converter function for continuous steady-state operation.

        Measures the change in time between 2 measurements w.r.t. sensor device time and the max value before overlow.
        dt > 0 always thanks to modulo, even if sensor on-board clock overflows.
        Converts to the number of sample periods in the measured time delta window, allowing for slight skew.
        Rolling correlation using sample rate, previous and current time is more accurate than averaging over whole timelife.

        Args:
            key (Any): The unique identifier of the channel.
            timestamp (int): Monotonically increasing overflowing integer from a sensor.

        Returns:
            int | None: Converted counter value starting at 0 counter value.
        """
        delta_ticks = (timestamp - self._previous_timestamps[key]) % self._timestamp_limit  # type: ignore
        self._previous_timestamps[key] = timestamp
        delta_counter = round(delta_ticks / self._sampling_period)
        self._counters[key] += delta_counter  # type: ignore
        return self._counters[key]


class AlignedFifoBuffer(BufferInterface):
    """Multichannel first-in first-out buffer that aligns asynchronous temporally-lossy samples across channels.

    Receives asynchronous samples for each channel, aligns them, and returns to the user an aligned snapshot across all channels.
    Allows yeeting from buffer if some keys have been empty for a while (disconnection or out of range),
    while others continue producing.

    By default uses dynamically-growing Deque for the buffer, approprate for the sample rate of IMUs.
    `maxlen` offers possibility to turn into a fixed-length ring buffer, to avoid unnecessary memory allocations for higher performance,
    at the cost of lost data in case of slow consumers.

    Updates only on yeet to discard stale sample that arrived too late.
    Adds counter into the data payload to retreive on the reader. (Useful for time->counter converted buffer).
    If the snapshot had not been read, even if the measurement is stale (arrived later than specified), still adds it to the buffer.
    Empty pads if some intermediate timesteps did not recieve a packet for a specific key.
    If buffer contents are valid, moves snapshot into the output Queue.
    Update the frame counter to keep track of removed data to discard stale late arrivals.
    """

    def __init__(
        self, keys: Iterable, timesteps_before_stale: int, maxlen: int | None = None
    ):
        """Constructor of the AlignedFifoBuffer.

        Args:
            keys (Iterable): Set of uniquely identifying channel keys.
            timesteps_before_stale (int): The number of samples in other channels after which a missing sample in a channel is marked missing.
            maxlen (int | None): Fixed length of preallocated ring buffer. Defaults to None.
        """
        self._buffer = OrderedDict([(k, deque(maxlen=maxlen)) for k in keys])
        self._output_queue: queue.Queue[dict] = queue.Queue()
        self._counter_snapshot = 0
        self._timesteps_before_stale = timesteps_before_stale

    def plop(self, key: str, data: dict, **kwargs):
        counter: int = kwargs["counter"]
        data["counter"] = counter
        if counter >= self._counter_snapshot:
            while len(self._buffer[key]) < (counter - self._counter_snapshot):
                self._buffer[key].append(None)
            self._buffer[key].append(data)
        else:
            print("%d packet of %s arrived too late." % (counter, key), flush=True)
        is_every_key_has_data = all([len(buf) for buf in self._buffer.values()])
        is_some_key_exceeds_stale_period = any(
            [len(buf) >= self._timesteps_before_stale for buf in self._buffer.values()]
        )
        is_some_key_empty = any([not len(buf) for buf in self._buffer.values()])
        if is_every_key_has_data:
            oldest_packet = {k: buf.popleft() for k, buf in self._buffer.items()}
            self._put_output_queue(oldest_packet)
        elif is_some_key_exceeds_stale_period and is_some_key_empty:
            oldest_packet = {
                k: (buf.popleft() if len(buf) else None)
                for k, buf in self._buffer.items()
            }
            self._put_output_queue(oldest_packet)

    def _put_output_queue(self, packet: dict) -> None:
        """Places a ready to consume complete snapshot onto the output queue.

        Args:
            packet (dict): Temporally aligned snapshot mapping unique channel-identifying keys to the corresponding sample.
        """
        self._counter_snapshot += 1
        self._output_queue.put(packet)

    def flush(self) -> None:
        """Allow to evict all present data because no new samples will be captured."""
        while is_any_key_not_empty := any([len(buf) for buf in self._buffer.values()]):
            oldest_packet = {
                k: (buf.popleft() if len(buf) else None)
                for k, buf in self._buffer.items()
            }
            self._put_output_queue(oldest_packet)

    def yeet(self, timeout: float = 10.0) -> dict | None:
        """Attempts to synchronously retrieve the oldest set of samples from all channels of the buffer with a timeout.

        Args:
            timeout (float, optional): How long to wait for new snapshot. Defaults to `10.0`.

        Returns:
            dict | None: Multi-channel vector of the oldest sample or None if no new data became available until timeout.
        """
        try:
            return self._output_queue.get(timeout=timeout)
        except queue.Empty:
            print("Timed out on no more snapshots in the output Queue.")
            return None


class TimestampAlignedFifoBuffer(AlignedFifoBuffer):
    """Multichannel first-in first-out buffer that aligns asynchronous temporally-lossy samples across channels by supplied correlated timestamps.

    Allows yeeting from buffer if some keys have been empty for a while, while others continue producing.
    """

    def __init__(
        self,
        keys: Iterable,
        timesteps_before_stale: int,
        sampling_period: int,
        counter_limit: int,
        maxlen: int | None = None,
    ):
        """Constructor of the TimestampAlignedFifoBuffer.

        Args:
            keys (Iterable): Set of uniquely identifying channel keys.
            timesteps_before_stale (int): The number of samples in other channels after which a missing sample in a channel is marked missing.
            sampling_period (int): Sampling period in the same units as timestamp limit and timestamps.
            counter_limit (int): The upper counting limit of the sensor's timestamp.
            maxlen (int | None): Fixed length of preallocated ring buffer. Defaults to `None`.
        """
        super().__init__(
            keys=keys, timesteps_before_stale=timesteps_before_stale, maxlen=maxlen
        )
        self._converter = TimestampToCounterConverter(
            keys=keys, sampling_period=sampling_period, counter_limit=counter_limit
        )

    def plop(self, key: str, data: dict, **kwargs) -> None:
        timestamp: float = kwargs["timestamp"]
        counter = self._converter._counter_from_timestamp_fn(key, timestamp)
        if counter is not None:
            super().plop(key=key, data=data, counter=counter)


class NonOverflowingCounterAlignedFifoBuffer(AlignedFifoBuffer):
    """Multichannel first-in first-out buffer that aligns asynchronous temporally-lossy samples across channels by supplied correlated overflowing counter."""

    def __init__(
        self,
        keys: Iterable,
        timesteps_before_stale: int,
        num_bits_timestamp: int,
        maxlen: int | None = None,
    ):
        """Constructor of the NonOverflowingCounterAlignedFifoBuffer.

        Args:
            keys (Iterable): Set of uniquely identifying channel keys.
            timesteps_before_stale (int): The number of samples in other channels after which a missing sample in a channel is marked missing.
            num_bits_timestamp (int): The fixed-width of the counter generating the data.
            maxlen (int | None): Fixed length of preallocated ring buffer. Defaults to `None`.
        """
        super().__init__(
            keys=keys, timesteps_before_stale=timesteps_before_stale, maxlen=maxlen
        )
        self._converter = NonOverflowingCounterConverter(
            keys=keys, num_bits_counter=num_bits_timestamp
        )

    def plop(self, key: str, data: dict, **kwargs) -> None:
        raw_counter: int = kwargs["counter"]
        counter = self._converter._convert_fn(key, raw_counter)
        if counter is not None:
            super().plop(key=key, data=data, counter=counter)
