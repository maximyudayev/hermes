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
import zmq


class NodeInterface(ABC):
  # Read-only property that every subclass must implement.
  @classmethod
  @abstractmethod
  def _log_source_tag(cls) -> str:
    pass

  @property
  @abstractmethod
  def _is_done(self) -> bool:
    pass

  @abstractmethod
  def _set_state(self, state) -> None:
    pass

  @abstractmethod
  def _initialize(self) -> None:
    pass

  @abstractmethod
  def _get_sync_socket(self) -> zmq.SyncSocket:
    pass

  @abstractmethod
  def _activate_kill_poller(self) -> None:
    pass

  @abstractmethod
  def _activate_data_poller(self) -> None:
    pass

  @abstractmethod
  def _deactivate_kill_poller(self) -> None:
    pass

  @abstractmethod
  def _send_kill_to_broker(self) -> None:
    pass

  @abstractmethod
  def _poll(self) -> tuple[list[zmq.SyncSocket], list[int]]:
    pass

  @abstractmethod
  def _on_poll(self, poll_res: tuple[list[zmq.SyncSocket], list[int]]) -> None:
    pass

  @abstractmethod
  def _trigger_stop(self) -> None:
    pass

  @abstractmethod
  def _on_sync_complete(self) -> None:
    pass
