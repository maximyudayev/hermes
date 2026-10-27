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

from typing import Callable, Optional
import time
import zmq
from statemachine import StateMachine, State

from hermes.utils.time_utils import get_time
from hermes.utils.types import ZMQResult
from hermes.utils.zmq_utils import (
    CMD_ACK,
    CMD_BROKER_READY,
    CMD_BYE,
    CMD_END,
    CMD_GO,
    CMD_HELLO,
    CMD_IS_START,
    CMD_START,
    CMD_START_TIME,
    PORT_SYNC_REMOTE,
)

from hermes.base.broker.broker_interface import BrokerInterface
from hermes.base.state_interface import StateInterface


class BrokerStateMachine(StateMachine):
    """State machine managing the Broker lifecycle and transitions."""

    allow_event_without_transition = True

    init = State("Init", value="init", initial=True)
    sync_node_barrier = State("SyncNodeBarrier", value="sync_node_barrier")
    sync_broker_barrier = State("SyncBrokerBarrier", value="sync_broker_barrier")
    subscribe = State("Subscribe", value="subscribe")
    ready_barrier = State("ReadyBarrier", value="ready_barrier")
    start = State("Start", value="start")
    running = State("Running", value="running")
    kill_state = State("Kill", value="kill")
    join_node_barrier = State("JoinNodeBarrier", value="join_node_barrier")
    join_broker_barrier = State("JoinBrokerBarrier", value="join_broker_barrier")
    done = State("Done", value="done", final=True)

    to_sync_node_barrier = init.to(sync_node_barrier)
    to_sync_broker_barrier = sync_node_barrier.to(sync_broker_barrier)
    to_subscribe = sync_broker_barrier.to(subscribe)
    to_ready_barrier = subscribe.to(ready_barrier)
    to_start = ready_barrier.to(start)
    to_running = start.to(running)
    to_kill = (
        init.to(kill_state)
        | sync_node_barrier.to(kill_state)
        | sync_broker_barrier.to(kill_state)
        | subscribe.to(kill_state)
        | ready_barrier.to(kill_state)
        | start.to(kill_state)
        | running.to(kill_state)
    )
    to_join_node_barrier = kill_state.to(join_node_barrier)
    to_join_broker_barrier = join_node_barrier.to(join_broker_barrier)
    to_done = join_broker_barrier.to(done)

    def __init__(self, context: BrokerInterface):
        """Constructor of the BrokerStateMachine.

        Args:
            context (BrokerInterface): Reference to the Broker object.
        """
        self._context = context
        self._is_running = True
        self._is_continue_fn: Callable[[], bool] = lambda: True

        # SyncBrokerBarrier state variables
        self._sync_remote_socket: Optional[zmq.SyncSocket] = None
        self._sync_broker_poller: Optional[zmq.Poller] = None
        self._remote_sub_brokers: list[str] = []
        self._remote_pub_brokers: list[str] = []
        self._brokers: dict[str, bytes] = {}
        self._brokers_left_to_acknowledge: set[str] = set()
        self._brokers_left_to_checkin: set[str] = set()
        self._start_time_s: Optional[int] = None
        self._ready_brokers: set[str] = set()
        self._nodes_left_to_start: set[str] = set()
        self._ready_announced = False

        # JoinNodeBarrier state variables
        self._join_nodes: dict[str, bytes] = {}
        self._nodes_waiting_to_exit: set[str] = set()
        self._nodes_expected_end_pub_packet: set[str] = set()
        self._join_node_sync_socket: Optional[zmq.SyncSocket] = None
        self._join_node_poller: Optional[zmq.Poller] = None

        # JoinBrokerBarrier state variables
        self._join_remote_brokers: dict[str, bytes] = {}
        self._join_remote_sub_brokers: list[str] = []
        self._join_remote_pub_brokers: list[str] = []
        self._join_broker_left_to_acknowledge: set[str] = set()
        self._join_broker_left_to_checkin: set[str] = set()
        self._join_broker_sync_remote_socket: Optional[zmq.SyncSocket] = None
        self._join_broker_poller: Optional[zmq.Poller] = None

        super().__init__()

    def _on_subscription_changed(self, msg: list[bytes]) -> None:
        """Update a list on the Broker that keeps track of which Nodes are being brokered for."""
        msg_decoded = msg[0].decode("utf-8")
        if "\x01" in msg_decoded:
            topic: str = msg_decoded.split("\x01")[1]
            self._context._add_brokered_node(node_id=topic.split(".")[0])
        elif "\x00" in msg_decoded:
            topic: str = msg_decoded.split("\x00")[1]

    def on_enter_sync_broker_barrier(self) -> None:
        """Hook when entering SyncBrokerBarrier state."""
        self._sync_remote_socket = self._context._get_sync_remote_socket()
        self._remote_sub_brokers = self._context._get_remote_sub_brokers()
        self._remote_pub_brokers = self._context._get_remote_pub_brokers()
        self._brokers = dict()

        self._brokers_left_to_acknowledge = set(self._remote_sub_brokers)
        self._brokers_left_to_checkin = set(self._remote_pub_brokers)
        for ip in self._remote_sub_brokers:
            self._sync_remote_socket.connect("tcp://%s:%s" % (ip, PORT_SYNC_REMOTE))

        self._sync_broker_poller = zmq.Poller()
        self._sync_broker_poller.register(self._sync_remote_socket, zmq.POLLIN)

    def _on_broker_sync_message(self, msg: list[bytes]) -> None:
        """Handle startup messages even when peers have reached different states."""
        address, _, broker_name, cmd = msg
        # START_TIME uses a different envelope: its last frame is binary time,
        # not a command. A master can finish its barrier before this host does.
        if broker_name == CMD_START_TIME.encode("utf-8"):
            if not self._context._get_is_master_broker():
                self._start_time_s = int.from_bytes(cmd, byteorder="big")
            return

        broker_name = broker_name.decode("utf-8")
        host_ip = self._context._get_host_ip()
        print(
            "%s sent %s to %s" % (broker_name, cmd.decode("utf-8"), host_ip),
            flush=True,
        )
        if (
            cmd == CMD_ACK.encode("utf-8")
            and broker_name in self._brokers_left_to_acknowledge
        ):
            self._brokers_left_to_acknowledge.remove(broker_name)
            self._brokers[broker_name] = address
        elif cmd == CMD_HELLO.encode("utf-8") and broker_name in self._remote_pub_brokers:
            # HELLO is retried until ACK arrives. Always acknowledge a known
            # publisher, while counting its check-in only once.
            self._brokers_left_to_checkin.discard(broker_name)
            self._brokers[broker_name] = address
            if self._sync_remote_socket is not None:
                self._sync_remote_socket.send_multipart(
                    [address, b"", host_ip.encode("utf-8"), CMD_ACK.encode("utf-8")]
                )
        elif cmd == CMD_BROKER_READY.encode("utf-8") and broker_name in (
            set(self._remote_pub_brokers) | set(self._remote_sub_brokers)
        ):
            # A peer may finish setup while we are still in the HELLO barrier.
            # This check-in must not count as a HELLO or an ACK.
            self._ready_brokers.add(broker_name)

    def on_enter_ready_barrier(self) -> None:
        """Collect local readiness while continuing to relay subscriptions."""
        self._nodes_left_to_start = set(self._context._get_node_addresses())
        poller = self._context._get_poller()
        poller.register(self._context._get_sync_host_socket(), zmq.POLLIN)
        poller.register(self._context._get_sync_remote_socket(), zmq.POLLIN)

    def on_exit_ready_barrier(self) -> None:
        poller = self._context._get_poller()
        poller.unregister(self._context._get_sync_host_socket())
        poller.unregister(self._context._get_sync_remote_socket())

    def on_enter_running(self) -> None:
        """Hook when entering Running state."""
        self._context._set_broker_ready()
        self._context._set_state(self)
        print("\n\n### %s ###\n\n" % (CMD_GO), flush=True)
        self._is_running = True
        duration_s = self._context._get_duration()
        if duration_s is not None:
            self._is_continue_fn = lambda: (
                get_time() < (self._context._get_start_time() + duration_s)
            )
        else:
            self._is_continue_fn = lambda: True

    def on_enter_join_node_barrier(self) -> None:
        """Hook when entering JoinNodeBarrier state."""
        self._join_nodes = self._context._get_node_addresses().copy()
        self._nodes_waiting_to_exit = set()
        self._nodes_expected_end_pub_packet = set(self._context._get_brokered_nodes())
        self._join_node_sync_socket = self._context._get_sync_host_socket()
        self._join_node_poller = self._context._get_poller()
        self._join_node_poller.register(self._join_node_sync_socket, zmq.POLLIN)

    def on_enter_join_broker_barrier(self) -> None:
        """Hook when entering JoinBrokerBarrier state."""
        self._join_remote_brokers = self._context._get_remote_broker_addresses().copy()
        self._join_broker_sync_remote_socket = self._context._get_sync_remote_socket()
        self._join_remote_sub_brokers = self._context._get_remote_sub_brokers()
        self._join_remote_pub_brokers = self._context._get_remote_pub_brokers()
        self._join_broker_left_to_acknowledge = set(self._join_remote_sub_brokers)
        self._join_broker_left_to_checkin = set(self._join_remote_pub_brokers)
        self._join_broker_poller = zmq.Poller()
        self._join_broker_poller.register(
            self._join_broker_sync_remote_socket, zmq.POLLIN
        )

    def run(self) -> None:
        if self.init.is_active:
            self._context._activate_pubsub_poller()
            self._context._start_local_nodes()
            self.send("to_sync_node_barrier")

        elif self.sync_node_barrier.is_active:
            host_ip: str = self._context._get_host_ip()
            sync_host_socket: zmq.SyncSocket = self._context._get_sync_host_socket()
            node_addresses = dict()
            num_left_to_sync: int = self._context._get_num_local_nodes()
            while num_left_to_sync:
                address, _, node_name, cmd = sync_host_socket.recv_multipart()
                cmd = cmd.decode("utf-8")
                node_name = node_name.decode("utf-8")
                if cmd == CMD_HELLO:
                    num_left_to_sync -= 1
                    node_addresses[node_name] = address
                    print(
                        "%s connected to %s with %s message."
                        % (node_name, host_ip, cmd),
                        flush=True,
                    )
            self._context._set_node_addresses(node_addresses)
            self.send("to_sync_broker_barrier")

        elif self.sync_broker_barrier.is_active:
            host_ip = self._context._get_host_ip()
            if self._sync_remote_socket is not None:
                for ip in self._brokers_left_to_acknowledge:
                    self._sync_remote_socket.send_multipart(
                        [
                            ("%s:%s" % (ip, PORT_SYNC_REMOTE)).encode("utf-8"),
                            b"",
                            host_ip.encode("utf-8"),
                            CMD_HELLO.encode("utf-8"),
                        ]
                    )

            # Check every 5 seconds if other Brokers completed their setup and responded back.
            # Could be that no other Brokers exist.
            if self._sync_broker_poller is not None and self._sync_remote_socket is not None:
                poll_res: list[tuple[zmq.SyncSocket, zmq.PollEvent]] = self._sync_broker_poller.poll(5000)  # type: ignore
                if poll_res:
                    socket, _ = poll_res[0]
                    self._on_broker_sync_message(socket.recv_multipart())

            if not self._brokers_left_to_acknowledge and not self._brokers_left_to_checkin:
                if self._sync_broker_poller is not None and self._sync_remote_socket is not None:
                    try:
                        self._sync_broker_poller.unregister(self._sync_remote_socket)
                    except Exception:
                        pass
                self._context._set_remote_broker_addresses(self._brokers)
                self.send("to_subscribe")

        elif self.subscribe.is_active:
            sync_host_socket = self._context._get_sync_host_socket()
            while True:
                poll_res = self._context._poll(5000)
                if not poll_res:
                    break
                self._context._broker_packets(
                    poll_res, on_subscription_changed=self._on_subscription_changed
                )

            host_ip = self._context._get_host_ip()
            nodes: dict[str, bytes] = self._context._get_node_addresses()
            # Prepare local Nodes; GO is sent only after global readiness.
            for name, address in list(nodes.items()):
                sync_host_socket.send_multipart(
                    [address, b"", host_ip.encode("utf-8"), CMD_START.encode("utf-8")]
                )
                print("%s sending %s to %s" % (host_ip, CMD_START, name), flush=True)

            self.send("to_ready_barrier")

        elif self.ready_barrier.is_active:
            host_ip = self._context._get_host_ip()
            sync_host_socket = self._context._get_sync_host_socket()
            sync_remote_socket = self._context._get_sync_remote_socket()
            poll_res = self._context._poll(1000)
            self._context._broker_packets(
                poll_res, on_subscription_changed=self._on_subscription_changed
            )
            for socket, _ in poll_res:
                if socket == sync_remote_socket:
                    self._on_broker_sync_message(socket.recv_multipart())
                elif socket == sync_host_socket:
                    _, _, node_name, cmd = socket.recv_multipart()
                    node_name = node_name.decode("utf-8")
                    if cmd == CMD_IS_START.encode("utf-8"):
                        self._nodes_left_to_start.discard(node_name)
                        print(
                            "%s responded to %s with %s message."
                            % (node_name, host_ip, CMD_IS_START),
                            flush=True,
                        )
            if self._context._check_for_kill(poll_res):
                self.kill()
                return

            # Announce before waiting for peer readiness, avoiding circular waits.
            # Reaching this state already guarantees our HELLO/ACK barrier passed.
            if not self._nodes_left_to_start and not self._ready_announced:
                for address in self._brokers.values():
                    sync_remote_socket.send_multipart(
                        [
                            address,
                            b"",
                            host_ip.encode("utf-8"),
                            CMD_BROKER_READY.encode("utf-8"),
                        ]
                    )
                self._ready_announced = True

            peers = set(self._remote_pub_brokers) | set(self._remote_sub_brokers)
            if self._ready_announced and peers <= self._ready_brokers:
                self.send("to_start")

        elif self.start.is_active:
            host_ip = self._context._get_host_ip()
            sync_remote_socket: zmq.SyncSocket = self._context._get_sync_remote_socket()
            sync_host_socket = self._context._get_sync_host_socket()
            nodes = self._context._get_node_addresses()
            brokers: dict[str, bytes] = self._context._get_remote_broker_addresses()

            # Master Broker selects start time as 5 seconds from now and distributes across Brokers.
            if self._context._get_is_master_broker():
                start_time_s: int = round(get_time()) + 5
                for address in brokers.values():
                    sync_remote_socket.send_multipart(
                        [
                            address,
                            b"",
                            CMD_START_TIME.encode("utf-8"),
                            start_time_s.to_bytes(length=4, byteorder="big"),
                        ]
                    )
            # Slave Brokers may have received the time while still syncing peers.
            else:
                while self._start_time_s is None:
                    self._on_broker_sync_message(sync_remote_socket.recv_multipart())
                start_time_s = self._start_time_s

            # Each Broker waits until that time comes to trigger.
            while True:
                current_time_s = get_time()
                if current_time_s >= start_time_s:
                    break
                time.sleep(min(0.0001, start_time_s - current_time_s))

            # Trigger local Nodes to start logging.
            for name, address in list(nodes.items()):
                sync_host_socket.send_multipart(
                    [address, b"", host_ip.encode("utf-8"), CMD_GO.encode("utf-8")]
                )
                print("%s sending %s to %s" % (host_ip, CMD_GO, name), flush=True)

            self.send("to_running")

        elif self.running.is_active:
            poll_res: ZMQResult = self._context._poll(1000)
            self._context._broker_packets(
                poll_res, on_subscription_changed=self._on_subscription_changed
            )
            if self._context._check_for_kill(poll_res):
                self._is_running = False
                self.kill()

        elif self.kill_state.is_active:
            self._context._publish_kill()
            self.send("to_join_node_barrier")

        elif self.join_node_barrier.is_active:
            poll_res = self._context._poll(1000)
            self._context._broker_packets(
                poll_res, on_data_received=self._on_is_end_packet
            )
            self._check_host_sync_socket(poll_res)
            if not self._join_nodes:
                if self._join_node_poller is not None and self._join_node_sync_socket is not None:
                    try:
                        self._join_node_poller.unregister(self._join_node_sync_socket)
                    except Exception:
                        pass
                self._context._deactivate_pubsub_poller()
                self.send("to_join_broker_barrier")

        elif self.join_broker_barrier.is_active:
            host_ip = self._context._get_host_ip()
            if self._join_broker_sync_remote_socket is not None:
                for ip in self._join_broker_left_to_acknowledge:
                    self._join_broker_sync_remote_socket.send_multipart(
                        [
                            ("%s:%s" % (ip, PORT_SYNC_REMOTE)).encode("utf-8"),
                            b"",
                            host_ip.encode("utf-8"),
                            CMD_BYE.encode("utf-8"),
                        ]
                    )

            if (
                self._join_broker_poller is not None
                and self._join_broker_sync_remote_socket is not None
            ):
                poll_res: list[tuple[zmq.SyncSocket, zmq.PollEvent]] = self._join_broker_poller.poll(5000)  # type: ignore
                if poll_res:
                    socket, _ = poll_res[0]
                    address, _, broker_name, cmd = socket.recv_multipart()
                    broker_name = broker_name.decode("utf-8")
                    print(
                        "%s sent %s to %s."
                        % (broker_name, cmd.decode("utf-8"), host_ip),
                        flush=True,
                    )

                    if broker_name in self._join_broker_left_to_acknowledge:
                        self._join_broker_left_to_acknowledge.remove(broker_name)
                        self._join_remote_brokers.pop(broker_name, None)
                    elif broker_name in self._join_broker_left_to_checkin:
                        self._join_broker_left_to_checkin.remove(broker_name)
                        self._join_remote_brokers.pop(broker_name, None)
                        self._join_broker_sync_remote_socket.send_multipart(
                            [
                                address,
                                b"",
                                host_ip.encode("utf-8"),
                                CMD_BYE.encode("utf-8"),
                            ]
                        )

            if not self._join_remote_brokers:
                if (
                    self._join_broker_poller is not None
                    and self._join_broker_sync_remote_socket is not None
                ):
                    try:
                        self._join_broker_poller.unregister(
                            self._join_broker_sync_remote_socket
                        )
                    except Exception:
                        pass
                self.send("to_done")

    def is_continue(self) -> bool:
        """Check whether the Broker state machine should continue running.

        Returns:
            bool: Whether the state machine should stay in its loop.
        """
        if self.is_terminated:
            return False
        if self.running.is_active:
            return self._is_running and self._is_continue_fn()
        return True

    def kill(self) -> None:
        # Received 1 of 3 possible KILL signals to terminate.

        # Relay it to all Nodes and Brokers and wrap up gracefully.
        #     from the local Keyboard Interrupt;
        #     from the Master Broker;
        #     from the GUI;
        self.send("to_kill")

    def _on_is_end_packet(self, msg: list[bytes]) -> None:
        """Callback to track brokering of last packets of local Producers and Pipelines.

        Will get trigerred at most once per Node because publishing Nodes send it only once.
        """
        # Once the Broker registers arrival of 'END' packet from a local Producer/Pipeline,
        #   it will signal 'BYE' to it to allow it to exit.
        if CMD_END.encode("utf-8") in msg:
            # Check if the END packet came from the Broker's scope, (one of the Broker's local Nodes).
            #   Continue brokering packets if just proxing it (not Broker's local Nodes).
            topic = msg[0].decode().split(".")[0]
            if topic in self._nodes_expected_end_pub_packet:
                self._nodes_expected_end_pub_packet.remove(topic)
                # Allow local Producer/Pipeline to exit.
                self._release_local_node(topic)

    def _check_host_sync_socket(self, poll_res: ZMQResult) -> None:
        """Check if a local Node sent a request on the SYNC socket to indicate its closure.

        Can be triggered by all local Nodes: Producer, Consumer, or Pipeline, sending 'EXIT?' request.
        """
        if self._join_node_sync_socket is None:
            return
        host_ip = self._context._get_host_ip()
        for sock, _ in poll_res:
            if sock == self._join_node_sync_socket:
                address, _, node_name, cmd = self._join_node_sync_socket.recv_multipart()
                topic = node_name.decode("utf-8")
                print(
                    "%s received %s from %s" % (host_ip, cmd, topic), flush=True
                )
                self._nodes_waiting_to_exit.add(topic)
                self._release_local_node(topic)

    def _release_local_node(self, topic: str) -> None:
        """Release the local Node from the list of active Nodes of the Broker."""
        if (
            topic in self._nodes_waiting_to_exit
            and topic not in self._nodes_expected_end_pub_packet
            and self._join_node_sync_socket is not None
        ):
            host_ip = self._context._get_host_ip()
            self._join_node_sync_socket.send_multipart(
                [
                    self._join_nodes[topic],
                    b"",
                    host_ip.encode("utf-8"),
                    CMD_BYE.encode("utf-8"),
                ]
            )
            del self._join_nodes[topic]
            self._nodes_waiting_to_exit.remove(topic)

StateInterface.register(BrokerStateMachine)
