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

import time as _time
from time import perf_counter
from threading import Lock
from datetime import datetime, timezone
from dateutil import tz


class SingletonMeta(type):
    _instances = {}
    _lock: Lock = Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class SystemTime(metaclass=SingletonMeta):
    """Highly accurate system time Singleton that uses performance counters of the host device.

    Performance counters of the host devices are not Unix float numbers since epoch,
    but a float starting from 0 on the boot-up of the device. This Singleton uses less accurate system time
    with the `time.time()` call and combines with the performance counters, to get highly accurate time of the host device.

    This Singleton's methods should not be called directly. Use the global methods instead.

    Each subprocess of the application must be initialized via `init_time(...)`
    with a reference time obtained in the parent process via `get_ref_time()`.
    """

    def __init__(self):
        rough_time = _time.time()
        counter = perf_counter()
        self._ref_time = rough_time - counter
        # print(
        #     f"Reference time: {self._ref_time}, rough: {rough_time}, counter: {counter}",
        #     flush=True,
        # )

    def time(self) -> float:
        return self._ref_time + perf_counter()

    def _get_ref_time(self) -> float:
        return self._ref_time

    def _set_ref_time(self, ref_time: float) -> None:
        self._ref_time = ref_time


def init_time(ref_time: float) -> None:
    """Initialize the current process's `SystemTime` Singleton with a common reference time.

    Args:
        ref_time (float): Time obtained via `get_ref_time()` in the parent process to use as a reference for performance counters in the current process.
    """
    SystemTime()._set_ref_time(ref_time)
    # print(
    #     f"Initialized system time with ref time: {ref_time} at {get_time()}", flush=True
    # )


def get_ref_time() -> float:
    """Gets the current process's `SystemTime` Singleton reference time."""
    return SystemTime()._get_ref_time()


def get_time() -> float:
    """Gets the highly accurate current system time."""
    return SystemTime().time()


def get_time_str(time_s: float = get_time(), format: str = "%Y-%m-%d_%H-%M-%S") -> str:
    """Gets a date string from seconds since epoch.

    Args:
        time_s (float, optional): Time since epoch to convert to the human-readable string. Defaults to the current system time.
        format (str, optional): Format to construct the date string. Default to `%Y-%m-%d_%H-%M-%S`.
    
    Returns:
        str: Formatted date string corresponding to the provided time since epoch. 
    """
    time_datetime = datetime.fromtimestamp(time_s)
    time_str = time_datetime.strftime(format)
    return time_str


def get_time_s_from_utc_time_no_date_str(
    time_utc_str: str,
    input_time_format: str = "%H:%M:%S.%f",
    date_utc_str: str | None = None,
    input_date_format: str = "%Y-%m-%d",
) -> float:
    """Gets local time in seconds since epoch from provided UTC time strings.
    
    Args:
        time_utc_str (str): UTC time string to convert to seconds.
        input_time_format (str, optional): Time string format of the provided time. Defaults to `%H:%M:%S.%f`.
        date_utc_str (str, optional): UTC date to convert to seconds. Defaults to `None`.
        input_date_format (str, optional): Date string format of the provided date. Defaults to `%Y-%m-%d`.

    Returns:
        float: Seconds count since epoch, corresponding to the provided UTC time strings.
    """
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()

    # Get the current UTC date if no date was provided.
    if date_utc_str is None:
        now_utc_datetime = datetime.now(timezone.utc)
        date_utc_str = now_utc_datetime.strftime(input_date_format)

    # Combine the date and time.
    utc_str = "%s %s" % (date_utc_str, time_utc_str)
    utc_datetime = datetime.strptime(
        utc_str, input_date_format + " " + input_time_format
    )

    # Convert to local time, then to seconds since epoch.
    utc_datetime = utc_datetime.replace(tzinfo=from_zone)
    local_datetime = utc_datetime.astimezone(to_zone)
    return local_datetime.timestamp()


def get_time_s_from_local_str(
    time_local_str: str,
    input_time_format: str = "%H:%M:%S.%f",
    date_local_str: str | None = None,
    input_date_format: str = "%Y-%m-%d",
) -> float:
    """Gets seconds since epoch from provided local time string.
    
    Args:
        time_local_str (str): local time string to convert to seconds.
        input_time_format (str, optional): Time string format of the provided time. Defaults to `%H:%M:%S.%f`.
        date_local_str (str, optional): local date string to convert to seconds. Defaults to `None`.
        input_date_format (str, optional): Date string format of the provided date. Defaults to `%Y-%m-%d`.

    Returns:
        float: Seconds count since epoch, corresponding to the provided local time strings.
    """
    # Get the current local date if no date was provided.
    if date_local_str is None:
        now_local_datetime = datetime.now()
        date_local_str = now_local_datetime.strftime(input_date_format)

    # Combine the date and time.
    local_str = "%s %s" % (date_local_str, time_local_str)
    local_datetime = datetime.strptime(
        local_str, input_date_format + " " + input_time_format
    )

    return local_datetime.timestamp()
