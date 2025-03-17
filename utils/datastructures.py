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

from abc import ABC, abstractmethod
from collections import OrderedDict, deque
import copy
from threading import Lock
from typing import Any, Callable, Iterable


class BufferInterface(ABC):
  @abstractmethod
  def plop(self, key: str, data: dict) -> None:
    pass

  @abstractmethod
  def yeet(self) -> Any:
    pass


class TimestampToCounterConverter:
  def __init__(self,
               keys: Iterable,
               sampling_period: int, # NOTE: sampling period must be in the same units as timestamp limit and timestamps
               num_bits_timestamp: int): # NOTE:
    self._sampling_period = sampling_period
    self._timestamp_limit: int = 2**num_bits_timestamp
    self._counter_from_timestamp_fn: Callable = self._foo
    self._first_timestamps = OrderedDict([(k, None) for k in keys])
    self._previous_timestamps = OrderedDict([(k, None) for k in keys])
    self._counters = OrderedDict([(k, None) for k in keys])
    

  # Sets the start time according to the first received packet and switches
  #   to the monotone calculation routine after.
  def _foo(self, key, timestamp) -> int | None:
    # The sample is the very first in the buffer -> use as reference timestamp.
    #   Will return 0 start counter at the end of the function.
    if not any([v is not None for v in self._previous_timestamps.values()]):
      self._start_time = timestamp
      self._first_timestamps[key] = timestamp
      self._previous_timestamps[key] = timestamp
      self._counters[key] = 0
    # If it's not the very first packet, but first reading for this device.
    #   Record if the capture was during or after the start reference.
    #   NOTE: style is more verbose to preserve clarity.
    elif self._previous_timestamps[key] is None:
      # Measurement taken during or after the reference measurement and no chance for overflow.
      #   Will return 0 start counter at the end of the function.
      if timestamp >= self._start_time:
        self._first_timestamps[key] = timestamp
        self._previous_timestamps[key] = timestamp
        self._counters[key] = round(((timestamp - self._start_time) % self._timestamp_limit)/ self._sampling_period)
      # Measurement taken after the overflow of the on-sensor clock and effectively after the reference measurement.
      #   Will return 0 start counter at the end of the function.
      elif ((timestamp - self._start_time) % self._timestamp_limit) < (self._start_time - timestamp):
        self._first_timestamps[key] = timestamp
        self._previous_timestamps[key] = timestamp
        self._counters[key] = round(((timestamp - self._start_time) % self._timestamp_limit)/ self._sampling_period)
      # Otherwise it's a stale measurement to be discarded to ensure alignment. 
      else:
        return None
    # Not the first measurement of this device, use the monotone method to compute the counter.
    else:
      self._bar(key=key, timestamp=timestamp)
    # Switch the function call to the monotone routine once all crossed the start reference time.
    if all([v is not None for v in self._previous_timestamps.values()]):
      self._counter_from_timestamp_fn = self._bar
    return self._counters[key]


  def _bar(self, key, timestamp) -> int:
    # Measure the dt between 2 measurements w.r.t. sensor device time and the max value before overlow.
    #   dt > 0 always thanks to modulo, even if sensor on-board clock overflows.
    delta_ticks = (timestamp - self._previous_timestamps[key]) % self._timestamp_limit
    self._previous_timestamps[key] = timestamp
    # Convert to the number of sample periods in that time, allowing for slight instantaneous drift.
    # NOTE: counter measurement with sample rate, previous and current time is more accurate than averaging over whole timelife.
    delta_counter = round(delta_ticks / self._sampling_period)
    self._counters[key] += delta_counter
    return self._counters[key]


# Uses dynamic lists for the buffer, approprate for the sample rate of IMUs.
#   Switch to a defined-length ring buffer to avoid unnecessary memory allocation for higher performance.
class AlignedFifoBuffer(BufferInterface):
  def __init__(self,
               keys: Iterable,
               timesteps_before_stale: int): # NOTE: allows yeeting from buffer if some keys have been empty for a while (disconnection or out of range), while others continue producing
    self._lock = Lock()
    self._buffer = OrderedDict([(k, deque()) for k in keys])
    self._counter_snapshot = 0 # Updated only on yeet to discard stale sample that arrived too late.
    self._timesteps_before_stale = timesteps_before_stale


  def plop(self, key: str, data: dict, counter: int):
    self._lock.acquire()
    self._plop(key=key, data=data, counter=counter)
    self._lock.release()


  # Adding packets to the datastructure is asynchronous for each key.
  def _plop(self, key: str, data: dict, counter: int):
    # Add counter into the data payload to retreive on the reader. (Useful for time->counter converted buffer).
    data["counter"] = counter
    # The snapshot had not been read yet, even if measurement is stale (arrived later than specified), 
    #   there's still time to add it.
    if counter >= self._counter_snapshot:
      # Empty pad if some intermediate timesteps did not recieve a packet for this key.
      while len(self._buffer[key]) < (counter - self._counter_snapshot):
        self._buffer[key].append(None)
      self._buffer[key].append(data)


  # Getting packets from the datastructure is synchronous for all keys.
  def yeet(self, is_running: bool) -> Any | None:
    self._lock.acquire()
    is_every_key_has_data = all([len(buf) for buf in self._buffer])
    is_some_key_exceeds_stale_period = any([len(buf) >= self._timesteps_before_stale for buf in self._buffer])
    is_some_key_empty = any([not len(buf) for buf in self._buffer])
    if (is_every_key_has_data or
        (is_some_key_exceeds_stale_period and is_some_key_empty)):
      oldest_packet = copy.deepcopy({k: (buf.popleft() if len(buf) else None) for k, buf in self._buffer.items()})
      # Update frame counter to keep track of removed data to discard stale late arrivals.
      self._counter_snapshot += 1
    else:
      # No more new data will be captured, can evict all present data.
      if is_running:
        oldest_packet = copy.deepcopy({k: (buf.popleft() if len(buf) else None) for k, buf in self._buffer.items()})
        self._counter_snapshot += 1
      else:
        oldest_packet = None
    self._lock.release()
    return oldest_packet


class TimestampAlignedFifoBuffer(AlignedFifoBuffer):
  def __init__(self,
               keys: Iterable,
               timesteps_before_stale: int, # NOTE: allows yeeting from buffer if some keys have been empty for a while, while others continue producing
               sampling_period: int, # NOTE: sampling period must be in the same units as timestamp limit and timestamps
               num_bits_timestamp: int): # NOTE:
    super().__init__(keys=keys,
                     timesteps_before_stale=timesteps_before_stale)
    self._converter = TimestampToCounterConverter(keys=keys,
                                                  sampling_period=sampling_period,
                                                  num_bits_timestamp=num_bits_timestamp)


  # Override parent method.
  def plop(self, key, data, timestamp) -> None:
    # Calculate counter from timestamp and local datastructure to avoid race condition.
    self._lock.acquire()
    counter = self._converter._counter_from_timestamp_fn(key, timestamp)
    if counter is not None:
      self._plop(key=key, data=data, counter=counter)
    self._lock.release()


# # TODO (non-critical): simplify using modulo of pos/neg difference between tips?
# class AlignedRingBuffer(BufferInterface):
#   def __init__(self,
#                size: int,
#                keys: Iterable):
#     self._lock = Lock()
#     self._size = size
#     self._buffer = OrderedDict([(k, [None]*size) for k in keys])
#     self._read_tip = OrderedDict([(k, 0) for k in keys]) # where oldest data is available
#     self._write_tip = OrderedDict([(k, 0) for k in keys]) # where next data will be written
#     self._is_full = OrderedDict([(k, False) for k in keys]) # flag when writer tip loops over and points to one with read tip
#     self._is_empty = OrderedDict([(k, True) for k in keys]) # flag when writer tip loops over and points to one with read tip


#   def __str__(self) -> str:
#         pad_char = " "
#         width = 7
#         res = ""
#         R = "R"
#         W = "W"
#         for key in self._buffer.keys():
#           res += f'{key}: |'
#           for el in range(self._size):
#             s = str(self._buffer[key][el])
#             res += f'{s:{pad_char}^{width}}|'
#           res += " -> FULL\n" if self._is_full[key] else (" -> EMPTY\n" if self._is_empty[key] else "\n")
          
#           if self._write_tip[key] > self._read_tip[key]:
#             res += pad_char*(4 + self._read_tip[key]*(1+width)) + f'{R:{pad_char}^{width}} '
#             res += pad_char*((self._write_tip[key] - self._read_tip[key] - 1)*(1+width)) + f'{W:{pad_char}^{width}} '
#           elif self._write_tip[key] < self._read_tip[key]:
#             res += pad_char*(4 + self._write_tip[key]*(1+width)) + f'{W:{pad_char}^{width}} '
#             res += pad_char*((self._read_tip[key] - self._write_tip[key] - 1)*(1+width)) + f'{R:{pad_char}^{width}} '
#           else:
#             res += pad_char*(4 + self._write_tip[key]*(1+width)) + f'{R+W:{pad_char}^{width}} '
#           res += "\n"
#         return res
      
#     # a: | None  |   2   |   ?   |   ?   |   ?   | -> FULL
#     #        R               W      
#     # b: |   1   | None  | None  |   ?   |   ?   |
#     #        R                       W
#     # c: |   1   |   2   |   3   |   ?   |   ?   |
#     #        R                       W
  

#   def plop(self, key, data, counter) -> None:
#     self._lock.acquire()
#     self._plop(key=key, data=data, counter=counter)
#     self._lock.release()


#   def _plop(self, key, data, counter):
#     counter_tip = counter % self._size
#     # If all buffers are empty, set a starting point using the counter modulo.
#     if all([self._is_empty[k] for k in self._buffer.keys()]):
#       self._buffer[key][counter_tip] = data
#       self._set_start_position(key, counter_tip)
#     else:
#       # Write None for all missing timesteps for current buffer until tip reaches location to write new data.
#       while self._write_tip[key] != counter_tip:
#         self._buffer[key][self._write_tip[key]] = None
#         self._move_write_tip(key)
#       # Write data into the right location of the current buffer.
#       self._buffer[key][self._write_tip[key]] = data
#       self._move_write_tip(key)


#   def yeet(self, is_running) -> dict[Any, dict | None] | None:
#     self._lock.acquire()
#     is_gt_1 = [self._len(k) > 1 for k in self._buffer.keys()]
#     is_eq_0 = [self._len(k) == 0 for k in self._buffer.keys()]
#     # More data is sampled and expected to be ploped.
#     if is_running:
#       # Current read position has valid data for all buffers 
#       #   or it contains missing packet because new timeframe began in other buffers.
#       if all(is_gt_1) or (any(is_gt_1) and any(is_eq_0)):
#         snapshot = self._read_next()
#         self._move_read_tip()
#       # Some packet still missing, but no new timeframe began
#       else:
#         snapshot = None
#     # No new data is expected.
#     else:
#       # All buffers are empty.
#       if all(is_eq_0):
#         snapshot = None
#       # Some buffers still contain valid non-missing data.
#       else:
#         snapshot = self._read_next()
#         self._move_read_tip()
#     if snapshot is not None:
#       snapshot = copy.deepcopy(snapshot)
#     self._lock.release()
#     return snapshot


#   def _len(self, key) -> int:
#     temp: int = self._write_tip[key] - self._read_tip[key]
#     if temp == 0 and self._is_full[key]:
#       return self._size
#     elif temp < 0:
#       return self._size + temp
#     else:
#       return temp


#   # Synchronously read data from the same position in all buffers.
#   #   Empty buffer returns None packet.
#   def _read_next(self) -> dict[Any, dict | None]:
#     return {k: (self._buffer[k][self._read_tip[k]] if not self._is_empty[k] else None) for k in self._buffer.keys()}


#   # Increment the read tips synchronously for all sub-buffers.
#   def _move_read_tip(self) -> None:
#     for k in self._buffer.keys():
#       # Reading full buffer -> reading tip moves, opens a spot for new data.
#       if self._is_full[k]:
#         self._read_tip[k] = (self._read_tip[k] + 1) % self._size
#         self._is_full[k] = False
#       # Reading empty buffer -> both tips move.
#       elif self._is_empty[k]:
#         self._read_tip[k] = (self._read_tip[k] + 1) % self._size
#         self._write_tip[k] = (self._write_tip[k] + 1) % self._size
#       # Reading may empty the buffer.
#       else:
#         self._read_tip[k] = (self._read_tip[k] + 1) % self._size
#         if self._write_tip[k] == self._read_tip[k]:
#           self._is_empty[k] = True 


#   # Increments write tip of the current buffer AFTER writing data at that location
#   #   and moves the read tips as necessary for others to preserve same timestep alignment 
#   #   in the snapshot reading (albeit if with missing data due to sensor dropout).
#   def _move_write_tip(self, key) -> None:
#     # Write tip just overwrote oldest value.
#     if self._write_tip[key] == self._read_tip[key] and not self._is_empty[key]:
#       self._write_tip[key] = (self._write_tip[key] + 1) % self._size
#       self._read_tip[key] = (self._read_tip[key] + 1) % self._size
#       # Adjust other sub-buffers to the same read position.
#       for k in self._buffer.keys():
#         if k == key: continue
#         # Buffer is full and not the one we are changing -> moving read tip opens a new spot.
#         if self._is_full[k]:
#           self._read_tip[k] = (self._read_tip[k] + 1) % self._size
#           self._is_full[k] = False
#         # Buffer is empty and not the one we are changing -> move both tips together.
#         elif self._is_empty[k]:
#           self._read_tip[k] = (self._read_tip[k] + 1) % self._size
#           self._write_tip[k] = (self._write_tip[k] + 1) % self._size
#         # Buffer has some data and not the one we are changing -> move only read tip.
#         # Read tip may catch up to the write tip -> buffer becomes empty.
#         else:
#           self._read_tip[k] = (self._read_tip[k] + 1) % self._size
#           if self._write_tip[k] == self._read_tip[k]:
#             self._is_empty[k] = True
#     else:
#       self._write_tip[key] = (self._write_tip[key] + 1) % self._size
#       # Set current buffer FULL if write tip catches up to the read tip.
#       # Will overwrite the oldest value at next iteration.
#       if self._write_tip[key] == self._read_tip[key]:
#         self._is_full[key] = True
#       else:
#         self._is_empty[key] = False


#   # Use index to choose start location in the ring buffer for all sub-buffers.
#   def _set_start_position(self, key, index) -> None:
#     for k in self._buffer.keys():
#       self._read_tip[k] = index
#       self._write_tip[k] = index
#       self._is_empty[k] = True
#     self._write_tip[key] = (index + 1) % self._size
#     self._is_empty[key] = False


# class TimestampAlignedRingBuffer(AlignedRingBuffer):
#   def __init__(self,
#                size: int,
#                keys: Iterable,
#                sampling_period: int, # NOTE: sampling period must be in the same units as timestamp limit and timestamps
#                num_bits_timestamp: int): # NOTE:
#     super().__init__(size=size,
#                      keys=keys)
#     self._converter = TimestampToCounterConverter(keys=keys,
#                                                   sampling_period=sampling_period,
#                                                   num_bits_timestamp=num_bits_timestamp)


#   # Override parent method.
#   def plop(self, key, data, timestamp) -> None:
#     # Calculate counter from timestamp and local datastructure to avoid race condition.
#     self._lock.acquire()
#     counter = self._converter._counter_from_timestamp_fn(key, timestamp)
#     if counter is not None:
#       self._plop(key=key, data=data, counter=counter)
#     self._lock.release()
