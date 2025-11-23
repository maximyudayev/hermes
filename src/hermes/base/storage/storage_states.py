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

from abc import abstractmethod
import asyncio
from collections import OrderedDict

from hermes.base.state_interface import StateInterface
from hermes.base.stream import Stream
from hermes.base.storage.storage_interface import StorageInterface


class AbstractStorageState(StateInterface):
    """Abstract class for the Storage component."""

    def __init__(self, context: StorageInterface):
        """Constructor of the AbstractStorageState.

        Args:
            context (StorageInterface): Reference to the Storage object.
        """
        self._context = context
        self._is_continue_fsm = True

    @abstractmethod
    def run(self) -> None:
        pass

    def is_continue(self) -> bool:
        return self._is_continue_fsm

    def kill(self) -> None:
        pass


class StartState(AbstractStorageState):
    """Startup state that initializes Storage.

    Will immediately transition into `StreamState` after initialization.
    """

    def __init__(self, context: StorageInterface, streams: OrderedDict[str, Stream]):
        """Constructor of the StartState.

        Args:
            context (StorageInterface): Reference to the Storage object.
            streams (OrderedDict[str, Stream]): Reference to the mapping between uniquly identifying Node keys and the corresponding Stream datastructures.
        """
        super().__init__(context)
        self._context._initialize(streams)

    def run(self) -> None:
        self._context._set_state(StreamState(self._context))


class StreamState(AbstractStorageState):
    """Streaming state of the Storage component.

    Will periodically flush data to disk, to clear memory,
    if any streams were specified to stream.

    Will flush remaining data to disk on exit.

    Using some streams in stream and others in dump has undefined behavior.
    """

    def __init__(self, context: StorageInterface):
        """Constructor of the StreamState.

        Args:
            context (StorageInterface): Reference to the Storage object.
        """
        super().__init__(context)
        # Prepare stream-logging.
        if self._context._is_to_stream():
            self._context._start_stream_logging()

    def run(self) -> None:
        asyncio.run(self._context._log_data())
        self._context._release_thread_pool()
        self._is_continue_fsm = False
        # self._context._set_state(DumpState(self._context))


class DumpState(AbstractStorageState):
    """Passive recording state of the Storage component.

    Will flush data to disk once upon system termination.

    May run out of memory if the recording is long or
    user doesn't provision sufficient data.

    Using some streams in stream and others in dump has undefined behavior.
    """

    def __init__(self, context: StorageInterface):
        """Constructor of the DumpState.

        Args:
            context (StorageInterface): Reference to the Storage object.
        """
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
