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

from multiprocessing import Process, set_start_method
from typing import Callable
import zmq

from hermes.utils.node_utils import launch_node
from hermes.utils.time_utils import get_time
from hermes.utils.types import ZMQResult
from hermes.utils.zmq_utils import (
    IP_LOOPBACK,
    PORT_BACKEND,
    PORT_FRONTEND,
    PORT_KILL,
    PORT_KILL_BTN,
    PORT_SYNC_HOST,
    PORT_SYNC_REMOTE,
    TOPIC_KILL,
)

from hermes.base.broker.broker_interface import BrokerInterface
from hermes.base.broker.broker_states import AbstractBrokerState, InitState


class Broker(BrokerInterface):
    """Manager of the lifecycle of all connected local Nodes and data broker.

    Facilitates high-performance message exchange using ZeroMQ zero-copy
    communication across distributed sensing and computing hosts.
    Passes data over sockets to external Brokers or over shared memory
    for local Nodes.

    Hosts control logic of interactive proxy/server.
    Will launch/destroy/connect to Nodes on creation and ad-hoc.
    Will use a separate process for each streamer and consumer.
    Each Node connects only to its local Broker,
        which then exposes its data to outside LAN subscribers.

    Uses fixed ports for communication under `zmq_utils.py`.
    Use of other ports is discouraged.

    Macro-defined ports are preferred for consistency in a
    distributed, multi-host setup.

    Uses hierarchical coordination of distributed host synchronization/setup.
    Each Broker first starts up and sync local Nodes.
    Then syncs with all expected remote hosts, until all are ready.
    After all are ready, master Broker communicates trigger signal to start streaming.
    """

    @classmethod
    def _log_source_tag(cls) -> str:
        return "manager"

    def __init__(
        self,
        host_ip: str,
        node_specs: list[dict],
        port_backend: str = PORT_BACKEND,
        port_frontend: str = PORT_FRONTEND,
        port_sync_host: str = PORT_SYNC_HOST,
        port_sync_remote: str = PORT_SYNC_REMOTE,
        port_killsig: str = PORT_KILL,
        is_master_broker: bool = False,
    ) -> None:
        """Constructor of the Broker component responsible for the lifecycle of all local Nodes and for message exchange across them and distributed hosts.

        Args:
            host_ip (str): Public LAN IP address of this host.
            node_specs (list[dict]): List of to-be-created Node specification dictionaries.
            port_backend (str, optional): XSUB port of the Broker. Defaults to `PORT_BACKEND`.
            port_frontend (str, optional): XPUB port of the Broker. Defaults to `PORT_FRONTEND`.
            port_sync_host (str, optional): Port for SYNC socket to coordinate startup of local Nodes. Defaults to `PORT_SYNC_HOST`.
            port_sync_remote (str, optional): Port for SYNC socket to coordinate startup across remote hosts. Defaults to `PORT_SYNC_REMOTE`.
            port_killsig (str, optional): Port of the KILL signal this Broker announces from. Defaults to `PORT_KILL`.
            is_master_broker (bool, optional): Whether this Broker is the master in the distributed host setup. Defaults to `False`.
        """
        self._host_ip = host_ip
        self._is_master_broker = is_master_broker
        self._port_backend = port_backend
        self._port_frontend = port_frontend
        self._port_sync_host = port_sync_host
        self._port_sync_remote = port_sync_remote
        self._port_killsig = port_killsig
        self._node_specs = node_specs
        self._is_quit = False
        self._is_done = False

        self._remote_pub_brokers: list[str] = []
        self._remote_sub_brokers: list[str] = []
        self._brokered_nodes: set[str] = set()

        # FSM for the broker
        self._state = InitState(self)

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
        self._sync_remote.setsockopt_string(
            zmq.IDENTITY, "%s:%s" % (self._host_ip, self._port_sync_remote)
        )
        self._sync_remote.bind("tcp://%s:%s" % (self._host_ip, self._port_sync_remote))

        # Termination control socket to command publishers and subscribers to finish and exit.
        killsig_pub: zmq.SyncSocket = self._ctx.socket(zmq.PUB)
        killsig_pub.bind("tcp://*:%s" % (self._port_killsig))
        self._killsigs: list[zmq.SyncSocket] = [killsig_pub]

        # Socket to listen to kill command from the GUI.
        self._gui_btn_kill: zmq.SyncSocket = self._ctx.socket(zmq.REP)
        self._gui_btn_kill.bind("tcp://*:%s" % PORT_KILL_BTN)

        # Poll object to listen to sockets without blocking
        self._poller: zmq.Poller = zmq.Poller()

    def expose_to_remote_broker(self, addr: list[str]) -> None:
        """Exposes a known address and port to remote networked subscribers if configured.

        Args:
            addr (list[str]): List of IP addresses of remote hosts (other Brokers).
        """
        frontend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XPUB)
        frontend_remote.bind("tcp://%s:%s" % (self._host_ip, self._port_frontend))
        self._remote_sub_brokers.extend(addr)
        self._frontends.append(frontend_remote)

    def connect_to_remote_broker(
        self, addr: str, port_pub: str = PORT_FRONTEND
    ) -> None:
        """Connects to a known address and port of external LAN data broker.

        Args:
            addr (str): Remote host IP to connect to as a listener.
            port_pub (str, optional): Port number on which remote host publishes local Nodes' data. Defaults to `PORT_FRONTEND`.
        """
        backend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XSUB)
        backend_remote.connect("tcp://%s:%s" % (addr, port_pub))
        self._remote_pub_brokers.append(addr)
        self._backends.append(backend_remote)

    def subscribe_to_killsig(self, addr: str, port_killsig: str = PORT_KILL) -> None:
        """Subscribes to external kill signal of another host as master.

        Args:
            addr (str): IP address of the master Broker in a distributed setting.
            port_killsig (str, optional): Port of the remote Broker to listen to for the termination signal. Defaults to `PORT_KILL`.
        """
        killsig_sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
        killsig_sub.connect("tcp://%s:%s" % (addr, port_killsig))
        killsig_sub.subscribe(TOPIC_KILL)
        self._poller.register(killsig_sub, zmq.POLLIN)
        self._killsigs.append(killsig_sub)

    def set_is_quit(self) -> None:
        """External asynchronous trigger to indicate termination to the Broker."""
        self._is_quit = True

    def is_done(self) -> bool:
        """External check for Broker's completion."""
        return self._is_done

    #####################
    ###### RUNNING ######
    #####################
    def __call__(self, duration_s: float | None = None) -> None:
        """The main FSM loop of the Broker.

        Runs continuously until the user ends the experiment or after the specified duration.
        The duration start to count only after all Nodes established communication and synced.

        Args:
            duration_s (float | None, optional): Duration of data capturing/streaming. Defaults to `None`.
        """
        self._duration_s = duration_s
        while self._state.is_continue() and not self._is_quit:
            self._state.run()
        if self._is_quit:
            print(
                "Keyboard exit signalled. Safely closing and saving, have some patience...",
                flush=True,
            )
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

    def _get_start_time(self) -> float:
        return self._state_start_time_s

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

    def _get_sync_host_socket(self) -> zmq.SyncSocket:
        return self._sync_host

    def _get_sync_remote_socket(self) -> zmq.SyncSocket:
        return self._sync_remote

    def _get_poller(self) -> zmq.Poller:
        return self._poller

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

    def _start_local_nodes(self) -> None:
        set_start_method("spawn")
        self._processes: list[Process] = [
            Process(target=launch_node, args=(node_spec,))
            for node_spec in self._node_specs
        ]
        for p in self._processes:
            p.start()

    def _poll(self, timeout_ms: int) -> ZMQResult:
        return self._poller.poll(timeout=timeout_ms)

    def _broker_packets(
        self,
        poll_res: ZMQResult,
        on_data_received: Callable[[list[bytes]], None] = lambda _: None,
        on_subscription_changed: Callable[[list[bytes]], None] = lambda _: None,
    ) -> None:
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

    def _check_for_kill(self, poll_res: ZMQResult) -> bool:
        for sock, _ in poll_res:
            # Receives KILL from the GUI.
            if sock == self._gui_btn_kill:
                return True
            # Receives KILL signal from another broker.
            elif sock in self._killsigs:
                return True
        return False

    def _publish_kill(self) -> None:
        for kill_socket in self._killsigs[1:]:
            # Ignore any more KILL signals, enter the wrap-up routine.
            self._poller.unregister(kill_socket)
        # Ignore poll events from the GUI and the same socket if used by child processes to indicate keyboard interrupt.
        self._poller.unregister(self._gui_btn_kill)
        # Send kill signals to own locally connected devices.
        self._killsigs[0].send(TOPIC_KILL.encode("utf-8"))

    def _stop(self) -> None:
        """Gracefully exit after all local subprocesses terminate, and cleanup."""
        for p in self._processes:
            p.join()

        # Release all used local sockets.
        for s in self._backends:
            s.close()
        for s in self._frontends:
            s.close()
        for s in self._killsigs:
            s.close()
        self._sync_host.close()
        self._sync_remote.close()
        self._gui_btn_kill.close()

        # Destroy ZeroMQ context.
        self._ctx.term()
        self._is_done = True
