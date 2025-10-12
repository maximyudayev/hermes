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
  """Interface for the Broker component.
  """

  @classmethod
  @abstractmethod
  def _log_source_tag(cls) -> str:
    """Read-only class property identifying the component.

    Returns:
        str: Unique identifier.
    """
    pass

  @abstractmethod
  def _start_local_nodes(self) -> None:
    """Spawn specified locally hosted Nodes, each in a separate process.
    """
    pass

  @abstractmethod
  def _set_state(self, state) -> None:
    """User defined logic for FSM state transition.

    Args:
        state (Any): New state to transition to.
    """
    pass

  @abstractmethod
  def _get_num_local_nodes(self) -> int:
    """Get the number of Nodes hosted and managed by this Broker.

    Returns:
        int: Number of locally attached Nodes.
    """
    pass

  @abstractmethod
  def _get_num_frontends(self) -> int:
    """Get the number of XPUB interfaces to remote hosts, listening to the Broker.

    Returns:
        int: Number of sockets.
    """
    pass
  
  @abstractmethod
  def _get_num_backends(self) -> int:
    """Get the number of XSUB interfaces to remote hosts, the Broker listens to.

    Returns:
        int: Number of sockets.
    """
    pass

  @abstractmethod
  def _get_remote_pub_brokers(self) -> list[str]:
    """Get the list of remote publishing Brokers' IPs. 

    Returns:
        list[str]: List of IP addresses.
    """
    pass
  
  @abstractmethod
  def _get_remote_sub_brokers(self) -> list[str]:
    """Get the list of remote subscribing Brokers' IPs. 

    Returns:
        list[str]: List of IP addresses.
    """
    pass

  @abstractmethod
  def _get_is_master_broker(self) -> bool:
    """Get the master status of this Broker in a distributed setup.

    Returns:
        bool: Whether this Broker is the master.
    """
    pass

  @abstractmethod
  def _get_brokered_nodes(self) -> set[str]:
    """Get the set of unique local Node identifiers that Broker manages.

    Returns:
        set[str]: Set of unique identifiers.
    """
    pass

  @abstractmethod
  def _add_brokered_node(self, topic: str) -> None:
    """Add a unique local Node identifier joining the exchange via the Broker.

    Noes uniquely self-identify by the data topic they produce.

    Args:
        topic (str): Unique identifier of the Node.
    """
    pass

  @abstractmethod
  def _remove_brokered_node(self, topic: str) -> None:
    """Remove the existing local Node identifier from the exchange via the Broker.

    Args:
        topic (str): Unique identifier of the Node.
    """
    pass

  @abstractmethod
  def _get_start_time(self) -> float:
    """Get the start time when the Broker set everything up and started streaming.
    
    Useful for measuring run time of the experiment,
    excluding the lengthy setup process.

    Returns:
        float: Time in seconds since epoch.
    """
    pass

  @abstractmethod
  def _get_duration(self) -> float | None:
    """Get the user-requested active duration of the capture/streaming. 

    Returns:
        float | None: Time in seconds, if specified on Broker launch.
    """
    pass

  @abstractmethod
  def _get_sync_host_socket(self) -> zmq.SyncSocket:
    """Get the reference to the RCV socket for syncing local Nodes.

    Returns:
        zmq.SyncSocket: ZeroMQ socket used to communicate SYNC process.
    """
    pass

  @abstractmethod
  def _get_sync_remote_socket(self) -> zmq.SyncSocket:
    """Get the reference to the RCV socket for syncing remote Brokers.

    Returns:
        zmq.SyncSocket: ZeroMQ socket used to communicate SYNC process.
    """
    pass

  @abstractmethod 
  def _set_node_addresses(self, node_addresses: dict[str, bytes]) -> None:
    """Bulk-set socket identifiers and unique Node identifiers for Broker's local Nodes.

    Args:
        node_addresses (dict[str, bytes]): Mapping of unique Node topics and their ZeroMQ socket identifiers.
    """
    pass

  @abstractmethod
  def _get_node_addresses(self) -> dict[str, bytes]:
    """Bulk-get socket identifiers and unique Node identifiers for Broker's local Nodes.

    Returns:
        dict[str, bytes]: Mapping of unique Node topics and their ZeroMQ socket identifiers.
    """
    pass

  @abstractmethod 
  def _set_remote_broker_addresses(self, remote_brokers: dict[str, bytes]) -> None:
    """Bulk-set socket identifiers and IP addresses of remote Brokers for this Broker.

    Args:
        remote_brokers (dict[str, bytes]): Mapping of remote IPs and their ZeroMQ socket identifiers.
    """
    pass

  @abstractmethod
  def _get_remote_broker_addresses(self) -> dict[str, bytes]:
    """Bulk-get socket identifiers and IP addresses of remote Brokers.

    Returns:
        dict[str, bytes]: Mapping of remote IPs and their ZeroMQ socket identifiers.
    """
    pass

  @abstractmethod
  def _get_host_ip(self) -> str:
    """Get the Broker's host machine LAN IP address.

    Returns:
        str: Host's IP address.
    """
    pass

  @abstractmethod
  def _activate_pubsub_poller(self) -> None:
    """Register PUB-SUB sockets on both Broker interfaces for polling.
    """
    pass

  @abstractmethod
  def _deactivate_pubsub_poller(self) -> None:
    """Stop listening on the PUB or SUB interfaces for new data packets.
    """
    pass

  @abstractmethod
  def _get_poller(self) -> zmq.Poller:
    """Get the ZeroMQ Poller object responsible for socket management.

    Returns:
        zmq.Poller: ZeroMQ poller to (de)activate listening on an interface.
    """
    pass

  @abstractmethod
  def _poll(self, timeout_ms: int) -> ZMQResult:
    """Block until any new packets are available on PUB or SUB Broker interfaces.

    Args:
        timeout_ms (int): Polling timeout duration to re-evaluate check for manual CLI termination.

    Returns:
        ZMQResult: New ZeroMQ packets from PUB or SUB interfaces. 
    """
    pass

  @abstractmethod
  def _broker_packets(self,
                      poll_res: ZMQResult,
                      on_data_received: Callable[[list[bytes]], None] = lambda _: None,
                      on_subscription_changed: Callable[[list[bytes]], None] = lambda _: None) -> None:
    """Move packets between publishers and subscribers, local and remote.

    Args:
        poll_res (ZMQResult): New ZeroMQ packets from PUB or SUB interfaces.
        on_data_received (_type_, optional): Callback for data packets. Defaults to lambda_:None.
        on_subscription_changed (_type_, optional): Callback for subscription status packets. Defaults to lambda_:None.
    """
    pass

  @abstractmethod
  def _check_for_kill(self, poll_res: ZMQResult) -> bool:
    """Check if received packets contain a kill signal from a downstream Broker.

    Args:
        poll_res (ZMQResult): New ZeroMQ packets from PUB or SUB interfaces.

    Returns:
        bool: Whether a KILL message is contained in messages.
    """
    pass

  @abstractmethod
  def _publish_kill(self):
    """Send kill signals to upstream Brokers and local Nodes.
    """
    pass
