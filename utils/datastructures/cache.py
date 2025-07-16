############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
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

import numpy as np

from utils.time_utils import get_time


@dataclass
class DataRequest:
  key: str
  timestamp: float


class FFmpegCache:
  def __init__(self, decode_fn: Callable[[Any], Dict[Any, bytes]]):
    self._cache: Dict[Any, bytes] = {}
    self._decode_fn = decode_fn
    self._request_queue: queue.Queue[DataRequest] = queue.Queue()
    # Events to notify when specific data becomes available
    self._data_events: Dict[Any, threading.Event] = defaultdict(threading.Event)


  def start(self):
    """Start the background cache management thread."""
    self._cache_task = threading.Thread(target=self._cache_manager)
    self._cache_task.start()


  def stop(self):
    """Stop the background cache management task."""
    if hasattr(self, 'cache_task'):
      self._cache_task.join()


  def _cache_manager(self):
    """
    Background continuous task: cache management.
    Processes requests from the GUI and predicts future needs.
    """
    while True:
      try:
        # Wait for user's requests
        request = self._request_queue.get(timeout=None)
        self._process_request(request)
      except queue.Empty:
        print(f"Timeout: no new cache fill request")
      except Exception as e:
        print(f"Error in cache manager: {e}")


  def _process_request(self, request: DataRequest):
    """Process data request"""
    # Only fetch if not already in cache or being fetched
    if request.key not in self._cache:
      # Update cache and notify waiters
      self._cache = self._fetch_data_from_source(request.key)
      # Notify all waiters for this key
      if request.key in self._data_events:
        self._data_events[request.key].set()


  def _fetch_data_from_source(self, key: Any) -> Dict[Any, bytes]:
    """
    Simulate fetching data from external source.
    Replace this with your actual data source (database, API, etc.)
    """
    # Call user-provided IO operation
    return self._decode_fn(key)


  def get_data(self, key: Any) -> bytes:
    """
    Request data from cache.
    Returns immediately if cached, otherwise waits for the background task to fetch.
    """
    # Check if data is already in cache
    if key in self._cache:
      return self._cache[key]

    # Add request to queue for background processing
    request = DataRequest(key, get_time())
    self._request_queue.put(request)

    # Wait for the data to become available in cache for the given key
    event = self._data_events[key]
    event.wait()
    del self._data_events[key]
    return self._cache[key]
