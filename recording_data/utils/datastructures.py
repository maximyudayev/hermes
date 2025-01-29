from collections import OrderedDict
from threading import Lock
from typing import Any, Iterable


class CircularBuffer:
  def __init__(self,
               size: int,
               keys: Iterable):
    self._lock = Lock()
    self._size = size
    self._buffer = OrderedDict([(k, [None]*size) for k in keys])
    self._read_tip = OrderedDict([(k, 0) for k in keys]) # where oldest data is available
    self._write_tip = OrderedDict([(k, 0) for k in keys]) # where next data will be written
    self._is_full = OrderedDict([(k, False) for k in keys]) # flag when writer tip loops over and points to one with read tip
    self._is_empty = OrderedDict([(k, True) for k in keys]) # flag when writer tip loops over and points to one with read tip


  def plop(self, key, data, counter) -> None:
    counter_tip = counter % self._size
    self._lock.acquire()
    # If all buffers are empty, set a starting point using the counter modulo.
    if all([self._is_empty[k] for k in self._buffer.keys()]):
      self._buffer[key][counter_tip] = data
      self._set_start_position(key, counter_tip)
    else:
      # Write None for all missing timesteps for current buffer until tip reaches location to write new data.
      while self._write_tip[key] != counter_tip:
        self._buffer[key][self._write_tip[key]] = None
        self._move_write_tip(key)
      # Write data into the right location of the current buffer.
      self._buffer[key][self._write_tip[key]] = data
      self._move_write_tip(key)
    self._lock.release()


  def yeet(self, is_running) -> dict[Any, dict | None] | None:
    self._lock.acquire()
    is_gt_1 = [self._len(k) > 1 for k in self._buffer.keys()]
    is_eq_0 = [self._len(k) == 0 for k in self._buffer.keys()]
    # More data is sampled and expected to be ploped.
    if is_running:
      # Current read position has valid data for all buffers 
      #   or it contains missing packet because new timeframe began in other buffers.
      if all(is_gt_1) or (any(is_gt_1) and any(is_eq_0)):
        snapshot = self._read_next()
        self._move_read_tip()
      # Some packet still missing, but no new timeframe began
      else:
        snapshot = None
    # No new data is expected.
    else:
      # All buffers are empty.
      if all(is_eq_0):
        snapshot = None
      # Some buffers still contain valid non-missing data.
      else:
        snapshot = self._read_next()
        self._move_read_tip()
    self._lock.release()
    return snapshot


  def _len(self, key) -> int:
    temp: int = self._write_tip[key] - self._read_tip[key]
    if temp == 0 and self._is_full[key]:
      return self._size
    elif temp < 0:
      return self._size + temp
    else:
      return temp


  # Synchronously read data from the same position in all buffers.
  #   Empty buffer returns None packet.
  def _read_next(self) -> dict[Any, dict | None]:
    return {k: (self._buffer[k][self._read_tip[k]] if not self._is_empty[k] else None) for k in self._buffer.keys()}


  # Increment the read tips synchronously for all sub-buffers.
  def _move_read_tip(self) -> None:
    for k in self._buffer.keys():
      # Reading full buffer -> reading tip moves, opens a spot for new data.
      if self._is_full[k]:
        self._read_tip[k] = (self._read_tip[k] + 1) % self._size
        self._is_full[k] = False
      # Reading empty buffer -> both tips move.
      elif self._is_empty[k]:
        self._read_tip[k] = (self._read_tip[k] + 1) % self._size
        self._write_tip[k] = (self._write_tip[k] + 1) % self._size
      # Reading may empty the buffer.
      else:
        self._read_tip[k] = (self._read_tip[k] + 1) % self._size
        if self._write_tip[k] == self._read_tip[k]:
          self._is_empty[k] = True 


  # Increments write tip of the current buffer AFTER writing data at that location
  #   and moves the read tips as necessary for others to preserve same timestep alignment 
  #   in the snapshot reading (albeit if with missing data due to sensor dropout).
  def _move_write_tip(self, key) -> None:
    # Write tip just overwrote oldest value.
    if self._write_tip[key] == self._read_tip[key] and not self._is_empty[key]:
      self._write_tip[key] = (self._write_tip[key] + 1) % self._size
      self._read_tip[key] = (self._read_tip[key] + 1) % self._size
      # Adjust other sub-buffers to the same read position.
      for k in self._buffer.keys():
        if k == key: continue
        # Buffer is full and not the one we are changing -> moving read tip opens a new spot.
        if self._is_full[k]:
          self._read_tip[k] = (self._read_tip[k] + 1) % self._size
          self._is_full[k] = False
        # Buffer is empty and not the one we are changing -> move both tips together.
        elif self._is_empty[k]:
          self._read_tip[k] = (self._read_tip[k] + 1) % self._size
          self._write_tip[k] = (self._write_tip[k] + 1) % self._size
        # Buffer has some data and not the one we are changing -> move only read tip.
        # Read tip may catch up to the write tip -> buffer becomes empty.
        else:
          self._read_tip[k] = (self._read_tip[k] + 1) % self._size
          if self._write_tip[k] == self._read_tip[k]:
            self._is_empty[k] = True
    else:
      self._write_tip[key] = (self._write_tip[key] + 1) % self._size
      # Set current buffer FULL if write tip catches up to the read tip.
      # Will overwrite the oldest value at next iteration.
      if self._write_tip[key] == self._read_tip[key]:
        self._is_full[key] = True
      else:
        self._is_empty[key] = False


  # Use index to choose start location in the ring buffer for all sub-buffers.
  def _set_start_position(self, key, index) -> None:
    for k in self._buffer.keys():
      self._read_tip[k] = index
      self._write_tip[k] = index
      self._is_empty[k] = True
    self._write_tip[key] = (index + 1) % self._size
    self._is_empty[key] = False


#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  class TestCircularBuffer(CircularBuffer):
    def __str__(self) -> str:
      pad_char = " "
      width = 7
      res = ""
      R = "R"
      W = "W"
      for key in self._buffer.keys():
        res += f'{key}: |'
        for el in range(self._size):
          s = str(self._buffer[key][el])
          res += f'{s:{pad_char}^{width}}|'
        res += " -> FULL\n" if self._is_full[key] else (" -> EMPTY\n" if self._is_empty[key] else "\n")
        
        if self._write_tip[key] > self._read_tip[key]:
          res += pad_char*(4 + self._read_tip[key]*(1+width)) + f'{R:{pad_char}^{width}} '
          res += pad_char*((self._write_tip[key] - self._read_tip[key] - 1)*(1+width)) + f'{W:{pad_char}^{width}} '
        elif self._write_tip[key] < self._read_tip[key]:
          res += pad_char*(4 + self._write_tip[key]*(1+width)) + f'{W:{pad_char}^{width}} '
          res += pad_char*((self._read_tip[key] - self._write_tip[key] - 1)*(1+width)) + f'{R:{pad_char}^{width}} '
        else:
          res += pad_char*(4 + self._write_tip[key]*(1+width)) + f'{R+W:{pad_char}^{width}} '
        res += "\n"
      return res
  # a: | None  |   2   |   ?   |   ?   |   ?   | -> FULL
  #        R               W      
  # b: |   1   | None  | None  |   ?   |   ?   |
  #        R                       W
  # c: |   1   |   2   |   3   |   ?   |   ?   |
  #        R                       W
 
  a = "a"
  b = "b"
  c = "c"

  buffer = TestCircularBuffer(size=5, 
                              keys=[a, b, c])

  print(buffer)
  buffer.plop(a, 4, 4)
  print(buffer)
  buffer.plop(a, 5, 5)
  print(buffer)
  buffer.plop(b, 6, 6)
  print(buffer)
  buffer.plop(b, 7, 7)
  print(buffer)
  buffer.plop(b, 8, 8)
  print(buffer)
  buffer.plop(b, 9, 9)
  print(buffer)
  buffer.plop(b, 10, 10)
  print(buffer)
  buffer.plop(b, 11, 11)
  print(buffer)
  buffer.yeet(True)
  print(buffer)
  buffer.yeet(True)
  print(buffer)
  buffer.yeet(True)
  print(buffer)
  buffer.yeet(True)
  print(buffer)
  print(buffer.yeet(True))
  print(buffer)
  print(buffer.yeet(False))
  print(buffer)

