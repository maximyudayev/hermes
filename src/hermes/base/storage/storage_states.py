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

from abc import abstractmethod
import asyncio
from collections import OrderedDict

from hermes.base.state_interface import StateInterface
from hermes.base.stream import Stream
from hermes.base.storage.storage_interface import StorageInterface


class AbstractLoggerState(StateInterface):
  def __init__(self, context: StorageInterface):
    self._context = context
    self._is_continue_fsm = True

  @abstractmethod
  def run(self) -> None:
    pass

  def is_continue(self) -> bool:
    return self._is_continue_fsm
  
  def kill(self) -> None:
    pass


class StartState(AbstractLoggerState):
  def __init__(self, context, streams: OrderedDict[str, Stream]):
    super().__init__(context)
    self._context._initialize(streams)

  def run(self) -> None:
    self._context._set_state(StreamState(self._context))


class StreamState(AbstractLoggerState):
  def __init__(self, context):
    super().__init__(context)
    # Prepare stream-logging.
    if self._context._is_to_stream():
      self._context._start_stream_logging()

  def run(self) -> None:
    asyncio.run(self._context._log_data())
    self._context._release_thread_pool()
    self._is_continue_fsm = False
    # self._context._set_state(DumpState(self._context))


class DumpState(AbstractLoggerState):
  def __init__(self, context):
    super().__init__(context)
    # Dump write files at the end of the trial for data that hadn't been streamed.
    #   Assumes all intermediate recorded data can fit in memory.
    if self._context._is_to_dump():
      self._context._start_dump_logging()

  def run(self) -> None:
    # Until top-level module's main thread indicated that it finished producing data,
    #   periodically sleep the thread to yield the CPU.
    self._context._wait_till_flush()
    # TODO: When experiment ended, write data once and wrap up.
    #   Use the end log time to not overwrite written streamed data with empty dumped files?
    asyncio.run(self._context._log_data())
    # Release Thread Pool used for AsyncIO for file writing.
    self._context._release_thread_pool()
    self._is_continue_fsm = False
