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

from collections import OrderedDict
from typing import Optional
import asyncio
from statemachine import StateMachine, State

from hermes.base.data_container import DataContainer
from hermes.base.state_interface import StateInterface
from hermes.base.storage.storage_interface import StorageInterface


class StorageStateMachine(StateMachine):
    """State machine managing the Storage component logging lifecycle and transitions."""

    allow_event_without_transition = True

    start = State("Start", value="start", initial=True)
    stream = State("Stream", value="stream")
    dump = State("Dump", value="dump")
    done = State("Done", value="done", final=True)

    to_stream = start.to(stream)
    to_dump = start.to(dump) | stream.to(dump)
    to_done = stream.to(done) | dump.to(done)

    def __init__(
        self,
        context: StorageInterface,
        data_containers: Optional[OrderedDict[str, DataContainer]] = None,
    ):
        """Constructor of the StorageStateMachine.

        Args:
            context (StorageInterface): Reference to the Storage object.
            data_containers (OrderedDict[str, DataContainer], optional): Mapping of node IDs to DataContainers.
        """
        self._context = context
        self._data_containers = data_containers
        super().__init__()

    def on_enter_stream(self) -> None:
        """Hook when entering Stream state: prepare stream logging writers."""
        if self._context._is_to_stream():
            self._context._start_stream_logging()

    def on_enter_dump(self) -> None:
        """Hook when entering Dump state: prepare dump logging writers."""
        if self._context._is_to_dump():
            self._context._start_dump_logging()

    def run(self) -> None:
        if self.start.is_active:
            if self._data_containers is not None:
                self._context._initialize(self._data_containers)
            self.to_stream()

        elif self.stream.is_active:
            asyncio.run(self._context._log_data())
            self._context._release_thread_pool()
            self.to_done()

        elif self.dump.is_active:
            self._context._wait_till_flush()
            asyncio.run(self._context._log_data())
            self._context._release_thread_pool()
            self.to_done()

    def is_continue(self) -> bool:
        return not self.is_terminated

    def kill(self) -> None:
        # No-op for storage termination.
        pass

StateInterface.register(StorageStateMachine)
