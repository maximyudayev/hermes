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

import queue
from typing import Dict, Any, Callable
from dataclasses import dataclass
from collections import defaultdict
import threading

from hermes.utils.time_utils import get_time


@dataclass
class DataRequest:
    """Object wrapping user's element of interest into a fetch request."""

    key: str
    timestamp: float


class Cache:
    """Caching module prefetches segments of data that has long IO, for more responsive experience."""

    def __init__(self, fetch_fn: Callable[[Any], Dict[Any, Any]], fetch_offset: int):
        """Constructor of the Cache component for long IO prefetching to mask latency behind wide bandwidth.

        Args:
            fetch_fn (Callable[[Any], Dict[Any, Any]]): User-provided function with long IO to use for asynchronous prefetching (database operation, API call, FFmpeg decoding, etc.).
            fetch_offset (int): How many elements before the requested to cache in case of jumping backwards during playback.
        """
        self._cache: Dict[Any, Any] = {}
        self._fetch_fn = fetch_fn
        self._fetch_offset = fetch_offset
        self._request_queue: queue.Queue[DataRequest] = queue.Queue()
        self._data_events: Dict[Any, threading.Event] = defaultdict(threading.Event)

    def start(self):
        """Start the background cache management thread."""
        self._cache_task = threading.Thread(target=self._run_cache_manager)
        self._cache_task.start()

    def join(self):
        """Wait on the background cache management thread."""
        if hasattr(self, "cache_task"):
            self._cache_task.join()

    def get_data(self, key: Any) -> Any:
        """Request data from the cache.

        Checks if data is already in the cache.
        Adds a request to the queue for background processing.
        Returns immediately if requested data is cached, otherwise waits for the background task to fetch it.
        Stalls until the data is available in the cache for the given key.

        Args:
            key (Any): Unique key correctly identifying the element of interest in the user-provided fetch function.

        Returns:
            Any: The requested element of interest.
        """
        if key in self._cache:
            return self._cache[key]

        request = DataRequest(key, get_time())
        self._request_queue.put(request)

        event = self._data_events[key]
        event.wait()
        del self._data_events[key]
        return self._cache[key]

    def _run_cache_manager(self):
        """Main loop of the background continuous cache management thread.

        Processes requests from the user and prefetches most likely used next segment of elements.
        """
        while True:
            try:
                request = self._request_queue.get(timeout=None)
                self._process_request(request)
            except queue.Empty:
                print(f"Timeout: no new cache fill request")
            except Exception as e:
                print(f"Error in cache manager: {e}")

    def _process_request(self, request: DataRequest):
        """Process user request for the next element of interest.

        Runs user-provided long-IO fetch procedure if the data is not immediately available in cache or isn't already being fetched.
        Updates the cache and notifies all watchers waiting for this element.

        Args:
            request (DataRequest): User-requested element of interest.
        """
        if request.key not in self._cache:
            self._cache = self._fetch(request.key)
            if request.key in self._data_events:
                self._data_events[request.key].set()

    def _fetch(self, key: Any) -> Dict[Any, Any]:
        """Fetches data from an external source using user-defined IO function.

        Returns:
            Dict[Any, Any]: Mapping from a unique key to the element of interest.
        """
        if (window_start_frame := key - self._fetch_offset) > 0:
            return self._fetch_fn(window_start_frame)
        else:
            return self._fetch_fn(0)
