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
  """Interface for the Node components.
  """

  @classmethod
  @abstractmethod
  def _log_source_tag(cls) -> str:
    """Read-only property uniquely identifying the Node.

    Returns:
        str: Unique key identifying the Node in the data exchange.
    """
    pass

  @property
  @abstractmethod
  def _is_done(self) -> bool:
    """Read-only property identifying if the Node completed operation.

    Returns:
        bool: Whether the Node completed its function.
    """
    pass

  @abstractmethod
  def _set_state(self, state) -> None:
    """User-defined logic for FSM state transition.

    Args:
        state (Any): New state to transition to.
    """
    pass

  @abstractmethod
  def _initialize(self) -> None:
    """Node-specific initialization procedure.

    Pre-run setup of the backend specific to the Node implementaiton.
    Generic setup should be run first.
    """
    pass

  @abstractmethod
  def _get_sync_socket(self) -> zmq.SyncSocket:
    """Get reference to the socket used for synchronization of the Node to its master Broker.

    Returns:
        zmq.SyncSocket: ZeroMQ socket of the Node connected to the local master Broker.
    """
    pass

  @abstractmethod
  def _activate_kill_poller(self) -> None:
    """Start listening for the KILL signal on the special PUB/SUB socket that coordinates program termination.
    """
    pass

  @abstractmethod
  def _activate_data_poller(self) -> None:
    """Start listening for new data from other Nodes.
    """
    pass

  @abstractmethod
  def _deactivate_kill_poller(self) -> None:
    """Stop listening for the KILL signal.
    """
    pass

  @abstractmethod
  def _send_kill_to_broker(self) -> None:
    """Send a slave KILL signal to the local Broker in case program termination by the slave Node is recorded. 
    """
    pass

  @abstractmethod
  def _poll(self) -> tuple[list[zmq.SyncSocket], list[int]]:
    """Block for new ZeroMQ data to collect at the Poller.

    Listens for events when new data is received from or when new data can be written to sockets,
    based on the active Poller settings of the Node implementation.

    Returns:
        tuple[list[zmq.SyncSocket], list[int]]: Result of listening on the sockets registered by the Poller.
    """
    pass

  @abstractmethod
  def _on_poll(self, poll_res: tuple[list[zmq.SyncSocket], list[int]]) -> None:
    """Callback to perform some logic everytime some data transactions are received by the Poller.

    Generic entry-point for all types of Nodes, based on their active Poller settings.
    NOTE: if Node in JoinState, kill socket is no longer in the Poller and only higher-level logic is triggered.

    Args:
        poll_res (tuple[list[zmq.SyncSocket], list[int]]): Reference to the complete captured result of listening by the Poller.
    """
    pass

  @abstractmethod
  def _trigger_stop(self) -> None:
    """Trigger to the Node's internal procedures and background threads to gracefully wrap-up.

    Producer: stops sampling data, continue sending already captured until none is left, with last message labeled 'END'.
    Consumer: continues listening to data until each of subscribed Producers sent the last message.
    Pipeline: continues listening to data to produce results until each data sources sent the last message, and then labels the last message with 'END'.
    """
    pass

  @abstractmethod
  def _on_sync_complete(self) -> None:
    """Callback to perform some logic after synchronization of Nodes is completed and indicated by the Broker.
    """
    pass
