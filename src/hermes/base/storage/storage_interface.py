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
from collections import OrderedDict

from hermes.base.stream import Stream


class StorageInterface(ABC):
  """Interface for the AsyncIO Storage component.
  """

  @abstractmethod
  def _set_state(self, state) -> None:
    """User defined logic for FSM state transition.

    Args:
        state (Any): New state to transition to.
    """
    pass

  @abstractmethod
  def _initialize(self, streams: OrderedDict[str, Stream]) -> None:
    """Initializes files and indices for write pointer tracking.

    Args:
        streams (OrderedDict[str, Stream]): Reference to the Stream objects to flush to disk.
    """
    pass

  @abstractmethod
  async def _log_data(self) -> None:
    """Main AsyncIO loop for Storage to write files concurrentlyto disk.
    """
    pass

  @abstractmethod
  def _is_to_stream(self) -> bool:
    """Check if any streams were configured to stream.

    Returns:
        bool: Whether there are any streams configured to stream data.
    """
    pass

  @abstractmethod
  def _is_to_dump(self) -> bool:
    """Check if any streams were configured to record.

    Returns:
        bool: Whether there are any streams configured to dump record data.
    """
    pass

  @abstractmethod
  def _start_stream_logging(self) -> None:
    """Set up AV/HDF5 file writers for stream-logging, if desired.
    """
    pass

  @abstractmethod
  def _stop_stream_logging(self) -> None:
    """Trigger termination and flushing of accumulated streamed data.

    Will wait for the thread to finish before returning.
    """
    pass

  @abstractmethod
  def _start_dump_logging(self) -> None:
    """Initialize passive recording until terminated to dump data once.
    """
    pass

  @abstractmethod
  def _wait_till_flush(self) -> None:
    """Sleep until the Storage is triggered to terminate after flushing.
    """
    pass

  @abstractmethod
  def _release_thread_pool(self) -> None:
    """Trigger release of AsyncIO resources used for writing files.
    """
    pass
