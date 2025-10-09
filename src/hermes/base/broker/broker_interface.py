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
from typing import Callable

import zmq

from hermes.utils.types import ZMQResult


class BrokerInterface(ABC):
  # Read-only property that every subclass must implement.
  @classmethod
  @abstractmethod
  def _log_source_tag(cls) -> str:
    pass

  @abstractmethod
  def _start_local_nodes(self) -> None:
    pass

  @abstractmethod
  def _set_state(self, state) -> None:
    pass

  @abstractmethod
  def _get_num_local_nodes(self) -> int:
    pass

  @abstractmethod
  def _get_num_frontends(self) -> int:
    pass
  
  @abstractmethod
  def _get_num_backends(self) -> int:
    pass

  @abstractmethod
  def _get_remote_pub_brokers(self) -> list[str]:
    pass
  
  @abstractmethod
  def _get_remote_sub_brokers(self) -> list[str]:
    pass

  @abstractmethod
  def _get_is_master_broker(self) -> bool:
    pass

  @abstractmethod
  def _get_brokered_nodes(self) -> set[str]:
    pass

  @abstractmethod
  def _add_brokered_node(self, topic: str) -> None:
    pass

  @abstractmethod
  def _remove_brokered_node(self, topic: str) -> None:
    pass

  @abstractmethod
  def _get_start_time(self) -> float:
    pass

  @abstractmethod
  def _get_duration(self) -> float | None:
    pass

  @abstractmethod
  def _get_sync_host_socket(self) -> zmq.SyncSocket:
    pass

  @abstractmethod
  def _get_sync_remote_socket(self) -> zmq.SyncSocket:
    pass

  @abstractmethod 
  def _set_node_addresses(self, node_addresses: dict[str, bytes]) -> None:
    pass

  @abstractmethod 
  def _set_remote_broker_addresses(self, remote_brokers: dict[str, bytes]) -> None:
    pass

  @abstractmethod
  def _get_remote_broker_addresses(self) -> dict[str, bytes]:
    pass

  @abstractmethod
  def _get_host_ip(self) -> str:
    pass

  @abstractmethod
  def _get_node_addresses(self) -> dict[str, bytes]:
    pass

  @abstractmethod
  def _activate_pubsub_poller(self) -> None:
    pass

  @abstractmethod
  def _deactivate_pubsub_poller(self) -> None:
    pass

  @abstractmethod
  def _get_poller(self) -> zmq.Poller:
    pass

  @abstractmethod
  def _poll(self, timeout_ms: int) -> ZMQResult:
    pass

  @abstractmethod
  def _broker_packets(self,
                      poll_res: ZMQResult,
                      on_data_received: Callable[[list[bytes]], None] = lambda _: None,
                      on_subscription_changed: Callable[[list[bytes]], None] = lambda _: None) -> None:
    pass

  @abstractmethod
  def _check_for_kill(self, poll_res: ZMQResult) -> bool:
    pass

  @abstractmethod
  def _publish_kill(self):
    pass
