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

from multiprocessing import Process, set_start_method
from typing import Callable
import zmq

from hermes.base.nodes import Node
from hermes.utils.mp_utils import launch_callable
from hermes.utils.node_utils import launch_node
from hermes.utils.types import ZMQResult
from hermes.utils.time_utils import *
from hermes.utils.zmq_utils import *

from hermes.base.broker.broker_interface import BrokerInterface
from hermes.base.broker.broker_states import AbstractBrokerState, InitState

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
               port_sync_host: str = PORT_SYNC_HOST,
               port_sync_remote: str = PORT_SYNC_REMOTE,
               port_killsig: str = PORT_KILL,
               is_master_broker: bool = False) -> None:

    # Record various configuration options.
    self._host_ip = host_ip
    self._is_master_broker = is_master_broker
    self._port_backend = port_backend
    self._port_frontend = port_frontend
    self._port_sync_host = port_sync_host
    self._port_sync_remote = port_sync_remote
    self._port_killsig = port_killsig
    self._node_specs = node_specs
    self._is_quit = False

    self._remote_pub_brokers: list[str] = []
    self._remote_sub_brokers: list[str] = []
    self._brokered_nodes: set[str] = set()

    # FSM for the broker
    self._state = InitState(self)

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
    self._sync_host: zmq.SyncSocket = self._ctx.socket(zmq.ROUTER)
    self._sync_host.bind("tcp://%s:%s" % (self._host_ip, self._port_sync_host))

    # Socket to connect to remote Brokers
    self._sync_remote: zmq.SyncSocket = self._ctx.socket(zmq.ROUTER)
    self._sync_remote.setsockopt_string(zmq.IDENTITY, "%s:%s"%(self._host_ip, self._port_sync_remote))
    self._sync_remote.bind("tcp://%s:%s" % (self._host_ip, self._port_sync_remote))

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
  def expose_to_remote_broker(self, addr: list[str]) -> None:
    frontend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XPUB)
    frontend_remote.bind("tcp://%s:%s" % (self._host_ip, self._port_frontend))
    self._remote_sub_brokers.extend(addr)
    self._frontends.append(frontend_remote)


  # Connects to a known address and port of external LAN data broker.
  def connect_to_remote_broker(self, addr: str, port_pub: str = PORT_FRONTEND) -> None:
    backend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XSUB)
    backend_remote.connect("tcp://%s:%s" % (addr, port_pub))
    self._remote_pub_brokers.append(addr)
    self._backends.append(backend_remote)


  # Subscribes to external kill signal (e.g. lab PC in AidFOG project).
  def subscribe_to_killsig(self, addr: str, port_killsig: str = PORT_KILL) -> None:
    killsig_sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    killsig_sub.connect("tcp://%s:%s" % (addr, port_killsig))
    killsig_sub.subscribe(TOPIC_KILL)
    self._poller.register(killsig_sub, zmq.POLLIN)
    self._killsigs.append(killsig_sub)


  def set_is_quit(self) -> None:
    self._is_quit = True


  #####################
  ###### RUNNING ######
  #####################
  # The main run method
  #   Runs continuously until the user ends the experiment or after the specified duration.
  #   The duration start to count only after all Nodes established communication and synced.
  def __call__(self, duration_s: float | None = None) -> None:
    self._duration_s = duration_s
    while self._state.is_continue() and not self._is_quit:
      self._state.run()
    if self._is_quit:
      print("Keyboard exit signalled. Safely closing and saving, have some patience...", flush=True)
    self._state.kill()
    # Continue with the FSM until it gracefully wraps up.
    while self._state.is_continue():
      self._state.run()
    self._stop()
    print("Experiment ended, thank you for using our system <3", flush=True)


  #############################
  ###### GETTERS/SETTERS ######
  #############################
  def _set_state(self, state: AbstractBrokerState) -> None:
    self._state = state
    self._state_start_time_s = get_time()


  def _set_node_addresses(self, node_addresses: dict[str, bytes]) -> None:
    self._node_addresses = node_addresses


  def _get_node_addresses(self) -> dict[str, bytes]:
    return self._node_addresses


  def _set_remote_broker_addresses(self, remote_brokers: dict[str, bytes]) -> None:
    self._remote_brokers = remote_brokers


  def _get_remote_broker_addresses(self) -> dict[str, bytes]:
    return self._remote_brokers


  # Start time of the current state - useful for measuring run time of the experiment, excluding the lengthy setup process
  def _get_start_time(self) -> float:
    return self._state_start_time_s


  # User-requested run time of the experiment 
  def _get_duration(self) -> float | None:
    return self._duration_s


  def _get_num_local_nodes(self) -> int:
    return len(self._processes)


  def _get_num_frontends(self) -> int:
    return len(self._frontends)


  def _get_num_backends(self) -> int:
    return len(self._backends)


  def _get_remote_pub_brokers(self) -> list[str]:
    return self._remote_pub_brokers


  def _get_remote_sub_brokers(self) -> list[str]:
    return self._remote_sub_brokers


  def _get_is_master_broker(self) -> bool:
    return self._is_master_broker


  def _get_brokered_nodes(self) -> set[str]:
    return self._brokered_nodes


  def _add_brokered_node(self, topic: str) -> None:
    self._brokered_nodes.add(topic)


  def _remove_brokered_node(self, topic: str) -> None:
    self._brokered_nodes.remove(topic)


  def _get_host_ip(self) -> str:
    return self._host_ip


  # Reference to the RCV socket for syncing
  def _get_sync_host_socket(self) -> zmq.SyncSocket:
    return self._sync_host
  
  
  def _get_sync_remote_socket(self) -> zmq.SyncSocket:
    return self._sync_remote


  def _get_poller(self) -> zmq.Poller:
    return self._poller


  # Register PUB-SUB sockets on both interfaces for polling.
  def _activate_pubsub_poller(self) -> None:
    for s in self._backends:
      self._poller.register(s, zmq.POLLIN)
    for s in self._frontends:
      self._poller.register(s, zmq.POLLIN)
    # Register KILL_BTN port REP socket with POLLIN event.
    self._poller.register(self._gui_btn_kill, zmq.POLLIN)


  def _deactivate_pubsub_poller(self) -> None:
    for s in self._backends:
      self._poller.unregister(s)
    for s in self._frontends:
      self._poller.unregister(s)


  # Spawn local producers and consumers in separate processes
  def _start_local_nodes(self) -> None:
    # Make sure that the child processes are spawned and not forked.
    set_start_method('spawn')
    # Start each publisher-subscriber in its own process (e.g. local sensors, data logger, visualizer, AI worker).
    self._processes: list[Process] = [Process(target=launch_node, args=(node_spec,)) for node_spec in self._node_specs]
    for p in self._processes: p.start()


  # Block until new packets are available.
  def _poll(self, timeout_ms: int) -> ZMQResult:
    return self._poller.poll(timeout=timeout_ms)


  # Move packets between publishers and subscribers.
  def _broker_packets(self, 
                      poll_res: ZMQResult,
                      on_data_received: Callable[[list[bytes]], None] = lambda _: None,
                      on_subscription_changed: Callable[[list[bytes]], None] = lambda _: None) -> None:
    for recv_socket, _ in poll_res:
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
  def _check_for_kill(self, poll_res: ZMQResult) -> bool:
    for sock, _ in poll_res:
      # Receives KILL from the GUI.
      if sock == self._gui_btn_kill:
        return True
      # Receives KILL signal from another broker.
      elif sock in self._killsigs:
        return True
    return False


  # Send kill signals to upstream brokers and local publishers
  def _publish_kill(self) -> None:
    for kill_socket in self._killsigs[1:]:
      # Ignore any more KILL signals, enter the wrap-up routine.
      self._poller.unregister(kill_socket)
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
    self._sync_host.close()
    self._sync_remote.close()
    self._gui_btn_kill.close()

    # Destroy ZeroMQ context.
    self._ctx.term()
