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
from multiprocessing import Process, set_start_method
from typing import Callable

import zmq

from utils.mp_utils import launch
from utils.time_utils import *
from utils.dict_utils import *
from utils.print_utils import *
from utils.zmq_utils import *


################################################################################
################################################################################
# PUB-SUB Broker to manage a collection of Node objects.
# Hosts control logic of interactive proxy/server.
# Will launch/destroy/connect to streamers on creation and ad-hoc.
# Will use a separate process for each streamer and consumer.
# Will use the main process to:
#   * route PUB-SUB messages;
#   * manage lifecycle of locally-connected Nodes;
#   * TODO: subscribe to stdin/stdout messages of all publishers and subscribers
# Each Node connects only to its local broker,
#   which then exposes its data to outside LAN subscribers.
################################################################################
################################################################################
class BrokerInterface(ABC):
  # Read-only property that every subclass must implement.
  @classmethod
  @abstractmethod
  def _log_source_tag(cls) -> str:
    pass

  @abstractmethod
  def _start(self) -> None:
    pass

  @abstractmethod
  def _set_state(self, state) -> None:
    pass

  @abstractmethod
  def _get_num_expected_connections(self) -> int:
    pass

  @abstractmethod
  def _get_start_time(self) -> float:
    pass

  @abstractmethod
  def _get_duration(self) -> float:
    pass

  @abstractmethod
  def _get_sync_socket(self) -> zmq.SyncSocket:
    pass

  @abstractmethod 
  def _set_node_addresses(self, nodes: dict[str, bytes]) -> None:
    pass

  @abstractmethod
  def _get_node_addresses(self) -> dict[str, bytes]:
    pass

  @abstractmethod
  def _activate_poller(self) -> None:
    pass

  @abstractmethod
  def _poll(self) -> tuple[list[zmq.SyncSocket], list[int]]:
    pass

  @abstractmethod
  def _broker_packets(self, 
                      poll_res: tuple[list[zmq.SyncSocket], list[int]],
                      on_data_received: Callable[[list[bytes]], None],
                      on_subscription_changed: Callable[[list[bytes]], None]) -> None:
    pass

  @abstractmethod
  def _check_for_kill(self, poll_res: tuple[list[zmq.SyncSocket], list[int]]) -> bool:
    pass

  @abstractmethod
  def _publish_kill(self):
    pass


class BrokerState(ABC):
  def __init__(self, context: BrokerInterface):
    self._context = context

  @abstractmethod
  def run(self) -> None:
    pass

  @abstractmethod
  def is_continue(self) -> bool:
    return True

  def kill(self) -> None:
    self._context._set_state(KillState(self._context))


# Activates broker poller sockets and goes in sync
class StartState(BrokerState):
  def run(self) -> None:
    self._context._activate_poller()
    self._context._start()
    self._context._set_state(SyncState(self._context))

  def is_continue(self) -> bool:
    return super().is_continue()


# Waits until all blocks of the system are initialized and ready to exchange data.
class SyncState(BrokerState):
  def run(self) -> None:
    num_expected_connections: int = self._context._get_num_expected_connections()
    sync_socket: zmq.SyncSocket = self._context._get_sync_socket()
    count = 0
    nodes = dict()
    while count < num_expected_connections:
      address, _, node_name = sync_socket.recv_multipart()
      count += 1
      node_name = node_name.decode('utf-8')
      nodes[node_name] = address
      print("%s connected to broker" % node_name, flush=True)

    for address in nodes.values():
      sync_socket.send_multipart([address, b'', CMD_GO.encode('utf-8')])

    self._context._set_node_addresses(nodes)
    self._context._set_state(RunningState(self._context))

  def is_continue(self) -> bool:
    return super().is_continue()


# Normal brokerage state
# Will run until the the experiment is stopped or after a fixed period, if provided
# TODO (non-critical): verify subscribers subscribed to desired topics and publishers are ready to send non-dummy data
class RunningState(BrokerState):
  def run(self) -> None:
    poll_res: tuple[list[zmq.SyncSocket], list[int]] = self._context._poll()
    self._context._broker_packets(poll_res)
    if self._context._check_for_kill(poll_res): self.kill()

  def is_continue(self) -> bool:
    return (time.time() < (self._context._get_start_time() + self._context._get_duration())) if self._context._get_duration() is not None else True


# Received the KILL signal from an upstream broker or terminal, relay the KILL signals to all nodes and go to the JOIN state
class KillState(BrokerState):
  def run(self) -> None:
    self._context._publish_kill()
    self._context._set_state(JoinState(self._context))

  def is_continue(self) -> bool:
    return super().is_continue()

  # Override default kill function behavior because we are already in the killing process
  def kill(self) -> None:
    pass


# Waits until all nodes send final packets then quits
# NOTE: uses counter to keep track of local processes and remote proxies used for syncing,
#   but can also use the `_nodes` dictionary on the `_context` object, with 0MQ addresses.
class JoinState(BrokerState):
  def __init__(self, context: BrokerInterface):
    super().__init__(context)
    self._num_left_to_join: int = self._context._get_num_expected_connections()
    self._sync_socket: zmq.SyncSocket = self._context._get_sync_socket()

  # Wait for all processes (local and remote) to send the last messages before closing.
  #   Continue brokering packets until signalled by all publishers that there will be no more packets.
  #   Append a frame to the ZeroMQ message that indicates the last message from the sensor.
  def run(self) -> None:
    poll_res: tuple[list[zmq.SyncSocket], list[int]] = self._context._poll()
    self._context._broker_packets(poll_res, on_data_received=self._on_is_end_packet)

  def is_continue(self) -> bool:
    return not not self._num_left_to_join

  # Callback to decrement the number of publishers left to join.
  #   Will get trigerred at most once per publisher/backend, so not needed to keep track.
  #   Once the Broker registers arrival of 'END' packet from a Producer, it will signal 'BYE' to it to allow it to exit.
  def _on_is_end_packet(self, msg: list[bytes]) -> None:
    if CMD_END.encode('utf-8') in msg:
      self._num_left_to_join -= 1
      topic = msg[0].decode().split('.')[0]
      nodes = self._context._get_node_addresses()
      self._sync_socket.send_multipart([nodes[topic], b'', CMD_BYE.encode('utf-8')])
      del(nodes[topic])
      self._context._set_node_addresses(nodes)

  # Override default kill function behavior because we are already in the killing process
  def kill(self) -> None:
    pass


class Broker(BrokerInterface):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'manager'


  # Initializes all broker logic and launches nodes
  def __init__(self,
               host_ip: str,
               node_specs: list[dict],
               port_backend: str = PORT_BACKEND,
               port_frontend: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               print_status: bool = True,
               print_debug: bool = False) -> None:

    # Record various configuration options.
    self._host_ip = host_ip
    self._port_backend = port_backend
    self._port_frontend = port_frontend
    self._port_sync = port_sync
    self._port_killsig = port_killsig
    self._print_status = print_status
    self._print_debug = print_debug
    self._node_specs = node_specs

    # FSM for the broker
    self._state = StartState(self)

    ###########################
    ###### CONFIGURATION ######
    ###########################
    # NOTE: We don't want streamers to share memory, each is a separate process communicating and sharing data over sockets
    #   ActionSense used multiprocessing.Manager and proxies to access streamers' data from the main process.
    # NOTE: Lab PC needs to receive packets on 2 interfaces - internally (own loopback) and over the network from the wearable PC.
    #   It then brokers data to its workers (data logging, visualization) in an abstract way so they don't have to know sensor topology.
    # NOTE: Wearable PC needs to send packets on 2 interfaces - internally (own loopback) and over the network to the lab PC.
    #   To wearable PC, lab PC looks just like another subscriber.
    # NOTE: Loopback and LAN can use the same port of the device because different interfaces are treated as independent connections.
    # NOTE: Loopback is faster than the network interface of the same device because it doesn't have to go through routing tables.

    # Pass exactly one ZeroMQ context instance throughout the program
    self._ctx: zmq.Context = zmq.Context()

    # Exposes a known address and port to locally connected sensors to connect to.
    local_backend: zmq.SyncSocket = self._ctx.socket(zmq.XSUB)
    local_backend.bind("tcp://%s:%s" % (IP_LOOPBACK, self._port_backend))
    self._backends: list[zmq.SyncSocket] = [local_backend]

    # Exposes a known address and port to broker data to local workers.
    local_frontend: zmq.SyncSocket = self._ctx.socket(zmq.XPUB)
    local_frontend.bind("tcp://%s:%s" % (IP_LOOPBACK, self._port_frontend))
    self._frontends: list[zmq.SyncSocket] = [local_frontend]

    # Listener endpoint to receive signals of streamers' readiness
    self._sync: zmq.SyncSocket = self._ctx.socket(zmq.ROUTER)
    self._sync.bind("tcp://%s:%s" % (self._host_ip, self._port_sync))

    # Termination control socket to command publishers and subscribers to finish and exit.
    killsig_pub: zmq.SyncSocket = self._ctx.socket(zmq.PUB)
    killsig_pub.bind("tcp://*:%s" % (self._port_killsig))
    self._killsigs: list[zmq.SyncSocket] = [killsig_pub]

    # Socket to listen to kill command from the GUI.
    self._gui_btn_kill: zmq.SyncSocket = self._ctx.socket(zmq.REP)
    self._gui_btn_kill.bind("tcp://*:%s" % (PORT_KILL_BTN))

    # Poll object to listen to sockets without blocking
    self._poller: zmq.Poller = zmq.Poller()


  # Exposes a known address and port to remote networked subscribers if configured.
  def expose_to_remote_sub(self) -> None:
    frontend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XPUB)
    frontend_remote.bind("tcp://%s:%s" % (self._host_ip, self._port_frontend))
    self._frontends.append(frontend_remote)


  # Connects to a known address and port of external LAN data broker.
  def connect_to_remote_pub(self, addr: str, port_pub: str = PORT_FRONTEND) -> None:
    backend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XSUB)
    backend_remote.connect("tcp://%s:%s" % (addr, port_pub))
    self._backends.append(backend_remote)


  # Subscribes to external kill signal (e.g. lab PC in AidFOG project).
  def subscribe_to_killsig(self, addr: str, port_killsig: str = PORT_KILL) -> None:
    killsig_sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    killsig_sub.connect("tcp://%s:%s" % (addr, port_killsig))
    killsig_sub.subscribe(TOPIC_KILL)
    self._poller.register(killsig_sub, zmq.POLLIN)
    self._killsigs.append(killsig_sub)


  #####################
  ###### RUNNING ######
  #####################
  # The main run method
  #   Runs continuously until the user ends the experiment or after the specified duration.
  #   The duration start to count only after all Nodes established communication and synced.
  def __call__(self, duration_s: float = None) -> None:
    self._duration_s = duration_s
    try:
      while self._state.is_continue():
        self._state.run()
      self._state.kill()
    except KeyboardInterrupt:
      print("Keyboard interrupt signalled, quitting...", flush=True)
      self._state.kill()
    finally:
      while self._state.is_continue():
        try:
          self._state.run()
        except KeyboardInterrupt:
          print("Safely closing and saving, have some patience...", flush=True)
      print("Experiment ended, thank you for using our system <3", flush=True)


  #############################
  ###### GETTERS/SETTERS ######
  #############################
  def _set_state(self, state: BrokerState) -> None:
    self._state = state
    self._state_start_time_s = time.time()


  def _set_node_addresses(self, nodes: dict[str, bytes]) -> None:
    self._nodes = nodes


  def _get_node_addresses(self) -> dict[str, bytes]:
    return self._nodes


  # Start time of the current state - useful for measuring run time of the experiment, excluding the lengthy setup process
  def _get_start_time(self) -> float:
    return self._state_start_time_s


  # User-requested run time of the experiment 
  def _get_duration(self) -> float | None:
    return self._duration_s


  # Locally running processes and remote backends
  def _get_num_expected_connections(self):
    return len(self._processes) + (len(self._backends)-1) + (len(self._frontends)-1)


  # Reference to the RCV socket for syncing
  def _get_sync_socket(self) -> zmq.SyncSocket:
    return self._sync


  # Register PUB-SUB sockets on both interfaces for polling.
  def _activate_poller(self) -> None:
    for s in self._backends:
      self._poller.register(s, zmq.POLLIN)
    for s in self._frontends:
      self._poller.register(s, zmq.POLLIN)
    # Register KILL_BTN port REP socket with POLLIN event.
    self._poller.register(self._gui_btn_kill, zmq.POLLIN)


  # Spawn local producers and consumers in separate processes
  def _start(self) -> None:
    # Make sure that the child processes are spawned and not forked.
    set_start_method('spawn')
    # Start each publisher-subscriber in its own process (e.g. local sensors, data logger, visualizer, AI worker).
    self._processes: list[Process] = [Process(target=launch,
                                              args=(spec,
                                                    self._host_ip,
                                                    self._port_backend,
                                                    self._port_frontend,
                                                    self._port_sync,
                                                    self._port_killsig)) for spec in self._node_specs]
    for p in self._processes: p.start()


  # Block until new packets are available
  def _poll(self) -> tuple[list[zmq.SyncSocket], list[int]]:
    return tuple(zip(*(self._poller.poll())))


  # Move packets between publishers and subscribers
  def _broker_packets(self, 
                      poll_res: tuple[list[zmq.SyncSocket], list[int]],
                      on_data_received: Callable[[list[bytes]], None] = lambda _: None,
                      on_subscription_changed: Callable[[list[bytes]], None] = lambda _: None) -> None:
    for recv_socket in poll_res[0]:
      # Forwards data packets from publishers to subscribers.
      if recv_socket in self._backends:
        msg = recv_socket.recv_multipart()
        on_data_received(msg)
        for send_socket in self._frontends:
          send_socket.send_multipart(msg)
      # Forwards subscription packets from subscribers to publishers.
      if recv_socket in self._frontends:
        msg = recv_socket.recv_multipart()
        on_subscription_changed(msg)
        for send_socket in self._backends:
          send_socket.send_multipart(msg)


  # Check if packets contain a kill signal from downstream a broker
  def _check_for_kill(self, poll_res: tuple[list[zmq.SyncSocket], list[int]]) -> bool:
    # Receives KILL from the GUI.
    if self._gui_btn_kill in poll_res[0]:
      return True
    for socket in poll_res[0]:
      # Receives KILL signal from another broker.
      if socket in self._killsigs:
        return True
    return False


  # Send kill signals to upstream brokers and local publishers
  def _publish_kill(self) -> None:
    for i in range(1, len(self._killsigs)):
      # Ignore any more KILL signals, enter the wrap-up routine.
      self._poller.unregister(self._killsigs[i])
    # Ignore poll events from the GUI and the same socket if used by child processes to indicate keyboard interrupt.
    self._poller.unregister(self._gui_btn_kill)
    # Send kill signals to own locally connected devices.
    self._killsigs[0].send(TOPIC_KILL.encode('utf-8'))


  def _stop(self) -> None:
    # Wait for all the local subprocesses to gracefully exit before terminating the main process.
    for p in self._processes: p.join()

    # Release all used local sockets.
    for s in self._backends: s.close()
    for s in self._frontends: s.close()
    for s in self._killsigs: s.close()
    self._sync.close()
    self._gui_btn_kill.close()

    # Destroy ZeroMQ context.
    self._ctx.term()
