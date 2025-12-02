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

import time
import zmq

from hermes.utils.time_utils import get_time
from hermes.utils.types import ZMQResult
from hermes.utils.zmq_utils import (
    CMD_ACK,
    CMD_BYE,
    CMD_END,
    CMD_GO,
    CMD_HELLO,
    CMD_START_TIME,
    PORT_SYNC_REMOTE,
)

from hermes.base.broker.broker_interface import BrokerInterface
from hermes.base.state_interface import StateInterface


class AbstractBrokerState(StateInterface):
    """Abstract class for the Broker FSM.

    Can be externally triggered into the KILL state from any child State class.
    """

    def __init__(self, context: BrokerInterface):
        """Constructor of the AbstractBrokerState class.

        Args:
            context (BrokerInterface): Reference to the Broker object.
        """
        self._context = context

    def is_continue(self) -> bool:
        return True

    def kill(self) -> None:
        self._context._set_state(KillState(self._context))


class InitState(AbstractBrokerState):
    """Initialization state of the Broker to launch local Nodes.

    Activates broker poller sockets and goes in sync to wait for local Nodes to start up.
    """

    def run(self) -> None:
        self._context._activate_pubsub_poller()
        self._context._start_local_nodes()
        self._context._set_state(SyncNodeBarrierState(self._context))


class SyncNodeBarrierState(AbstractBrokerState):
    """Synchronization state of the Broker that waits until all local Nodes setup.

    Waits until all local Nodes signalled that they are initialized and ready to go.
    """

    def run(self) -> None:
        host_ip: str = self._context._get_host_ip()
        sync_host_socket: zmq.SyncSocket = self._context._get_sync_host_socket()
        num_left_to_sync: int = self._context._get_num_local_nodes()
        node_addresses = dict()
        while num_left_to_sync:
            address, _, node_name, cmd = sync_host_socket.recv_multipart()
            num_left_to_sync -= 1
            node_name = node_name.decode("utf-8")
            node_addresses[node_name] = address
            print(
                "%s connected to %s with %s message."
                % (node_name, host_ip, cmd.decode("utf-8")),
                flush=True,
            )
        self._context._set_node_addresses(node_addresses)
        self._context._set_state(SyncBrokerBarrierState(self._context))


class SyncBrokerBarrierState(AbstractBrokerState):
    """Synchronization state of the Broker that waits until all remote Brokers setup.

    Communicate to other Brokers that every local device is ready.
    """

    def __init__(self, context: BrokerInterface):
        super().__init__(context)
        self._host_ip: str = self._context._get_host_ip()
        self._sync_remote_socket: zmq.SyncSocket = (
            self._context._get_sync_remote_socket()
        )

        self._remote_sub_brokers = self._context._get_remote_sub_brokers()
        self._remote_pub_brokers = self._context._get_remote_pub_brokers()
        self._brokers = dict()

        self._brokers_left_to_acknowledge = set(self._remote_sub_brokers)
        self._brokers_left_to_checkin = set(self._remote_pub_brokers)
        for ip in self._remote_sub_brokers:
            self._sync_remote_socket.connect("tcp://%s:%s" % (ip, PORT_SYNC_REMOTE))
        # Register remote SYNC socket to receive requests from remote publishers,
        #   and responses from remote subscribers.
        self._poller = zmq.Poller()
        self._poller.register(self._sync_remote_socket, zmq.POLLIN)

    def run(self) -> None:
        # I am remote publishing Broker, I must notify subscribing Brokers that I am ready.
        for ip in self._remote_sub_brokers:
            self._sync_remote_socket.send_multipart(
                [
                    ("%s:%s" % (ip, PORT_SYNC_REMOTE)).encode("utf-8"),
                    b"",
                    self._host_ip.encode("utf-8"),
                    CMD_HELLO.encode("utf-8"),
                ]
            )

        # Check every 5 seconds if other Brokers completed their setup and responded back.
        # Could be that no other Brokers exist.
        poll_res: list[tuple[zmq.SyncSocket, zmq.PollEvent]]
        if poll_res := self._poller.poll(5000):  # type: ignore
            socket, _ = poll_res[0]
            address, _, broker_name, cmd = socket.recv_multipart()
            broker_name = broker_name.decode("utf-8")
            print(
                "%s sent %s to %s response"
                % (broker_name, cmd.decode("utf-8"), self._host_ip),
                flush=True,
            )
            if broker_name in self._brokers_left_to_acknowledge:
                # Remote publisher received ACK from remote subscriber.
                self._brokers_left_to_acknowledge.remove(broker_name)
                self._brokers[broker_name] = address
            elif broker_name in self._brokers_left_to_checkin:
                self._brokers_left_to_checkin.remove(broker_name)
                self._brokers[broker_name] = address
                # Remote subscriber responds with ACK to remote publisher.
                self._sync_remote_socket.send_multipart(
                    [
                        address,
                        b"",
                        self._host_ip.encode("utf-8"),
                        CMD_ACK.encode("utf-8"),
                    ]
                )

        # Proceed to the next state to agree on the common time once all Brokers synchronized.
        if not self._brokers_left_to_acknowledge and not self._brokers_left_to_checkin:
            self._poller.unregister(self._sync_remote_socket)
            self._context._set_remote_broker_addresses(self._brokers)
            self._context._set_state(StartState(self._context))


class StartState(AbstractBrokerState):
    """Start state of the Broker that waits or initiates distributed launch.

    Trigger local Nodes to start logging when the agreed start time arrives.
    """

    def run(self) -> None:
        # If current Broker is not Master, wait for the SYNC signal with time when to start.
        host_ip: str = self._context._get_host_ip()
        sync_remote_socket: zmq.SyncSocket = self._context._get_sync_remote_socket()
        sync_host_socket: zmq.SyncSocket = self._context._get_sync_host_socket()
        nodes: dict[str, bytes] = self._context._get_node_addresses()
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
        # Slave Brokers block on the reeceive socket, waiting for the time.
        else:
            address, _, cmd, start_time_bytes = sync_remote_socket.recv_multipart()
            start_time_s = int.from_bytes(start_time_bytes, byteorder="big")

        # Each Broker waits until that time comes to trigger start of logging, with 1ms precision.
        while (current_time_s := get_time()) < start_time_s:
            time.sleep(min(0.001, start_time_s - current_time_s))

        # Trigget local Nodes to start logging.
        for name, address in list(nodes.items()):
            sync_host_socket.send_multipart(
                [address, b"", host_ip.encode("utf-8"), CMD_GO.encode("utf-8")]
            )
            print("%s sending %s to %s" % (host_ip, CMD_GO, name), flush=True)

        self._context._set_state(RunningState(self._context))


class RunningState(AbstractBrokerState):
    """Stead-state capturing or streaming state of the Broker.

    Will run until the the experiment is stopped or after a fixed period, if provided.
    """

    def __init__(self, context: BrokerInterface):
        super().__init__(context)
        context._set_broker_ready()
        if (duration_s := self._context._get_duration()) is not None:
            self._is_continue_fn = lambda: get_time() < (
                self._context._get_start_time() + duration_s
            )
        else:
            self._is_continue_fn = lambda: True

    def run(self) -> None:
        poll_res: ZMQResult = self._context._poll(1000)
        self._context._broker_packets(
            poll_res, on_subscription_changed=self._on_subscription_added
        )
        if self._context._check_for_kill(poll_res):
            self.kill()

    def is_continue(self) -> bool:
        return self._is_continue_fn()

    def _on_subscription_added(self, msg: list[bytes]) -> None:
        """Update a list on the Broker that keeps track of which Nodes are being brokered for."""
        topic: str = msg[0].decode("utf-8").split("\x01")[1]
        self._context._add_brokered_node(topic=topic)


class KillState(AbstractBrokerState):
    """Received 1 of 3 possible KILL signals to terminate.

    Relay it to all Nodes and Brokers and wrap up gracefully.
        from the local Keyboard Interrupt;
        from the Master Broker;
        from the GUI;
    """

    def run(self) -> None:
        self._context._publish_kill()
        self._context._set_state(JoinNodeBarrierState(self._context))

    # Override default kill function behavior because we are already in the killing process
    def kill(self) -> None:
        pass


class JoinNodeBarrierState(AbstractBrokerState):
    """Waits until all local Nodes send final packets then quits itself.

    Wait for all processes (local and remote) to send the last messages before closing.
    Continue brokering packets until signalled by all publishers that there will be no more packets.
    Append a frame to the ZeroMQ message that indicates the last message from the sensor.
    """

    def __init__(self, context: BrokerInterface):
        super().__init__(context)
        self._host_ip = self._context._get_host_ip()
        self._nodes = self._context._get_node_addresses()
        self._nodes_waiting_to_exit: set[str] = set()
        self._nodes_expected_end_pub_packet: set[str] = (
            self._context._get_brokered_nodes()
        )
        self._sync_host_socket: zmq.SyncSocket = self._context._get_sync_host_socket()
        self._poller = self._context._get_poller()
        self._poller.register(self._sync_host_socket, zmq.POLLIN)

    def run(self) -> None:
        poll_res: ZMQResult = self._context._poll(1000)
        # Brokers packets and releases local Producer Nodes in a callback once it published the end packet.
        self._context._broker_packets(poll_res, on_data_received=self._on_is_end_packet)
        # Checks if poll event was triggered by a local Node initiating closing.
        self._check_host_sync_socket(poll_res)
        # Proceed to exiting once all local Nodes finished.
        if self._is_finished():
            self._poller.unregister(self._sync_host_socket)
            self._context._deactivate_pubsub_poller()
            self._context._set_state(JoinBrokerBarrierState(self._context))

    def _on_is_end_packet(self, msg: list[bytes]) -> None:
        """Callback to track brokering of last packets of local Producers and Pipelines.

        Will get trigerred at most once per Node because publishing Nodes send it only once.
        """
        #   Once the Broker registers arrival of 'END' packet from a local Producer/Pipeline,
        #     it will signal 'BYE' to it to allow it to exit.
        if CMD_END.encode("utf-8") in msg:
            # Check if the END packet came from the Broker's scope, (one of the Broker's local Nodes).
            #   Continue brokering packets if just proxing it (not Broker's local Nodes).
            topic = msg[0].decode().split(".")[0]
            if self._nodes_expected_end_pub_packet:
                self._nodes_expected_end_pub_packet.remove(topic)
                # Allow local Producer/Pipeline to exit.
                self._release_local_node(topic)

    def _check_host_sync_socket(self, poll_res: ZMQResult) -> None:
        """Check if a local Node sent a request on the SYNC socket to indicate its closure.

        Can be triggered by all local Nodes: Producer, Consumer, or Pipeline, sending 'EXIT?' request.
        """
        for sock, _ in poll_res:
            if sock == self._sync_host_socket:
                address, _, node_name, cmd = self._sync_host_socket.recv_multipart()
                topic = node_name.decode("utf-8")
                print(
                    "%s received %s from %s" % (self._host_ip, cmd, topic), flush=True
                )
                self._nodes_waiting_to_exit.add(topic)
                self._release_local_node(topic)

    def _release_local_node(self, topic: str) -> None:
        """Release the local Node from the list of active Nodes of the Broker."""
        if (
            topic in self._nodes_waiting_to_exit
            and topic not in self._nodes_expected_end_pub_packet
        ):
            self._sync_host_socket.send_multipart(
                [
                    self._nodes[topic],
                    b"",
                    self._host_ip.encode("utf-8"),
                    CMD_BYE.encode("utf-8"),
                ]
            )
            del self._nodes[topic]
            self._nodes_waiting_to_exit.remove(topic)

    def _is_finished(self) -> bool:
        """Convenience method indicating if any local Nodes remain active.

        Will wait until all local Nodes finish.

        Returns:
            bool: Whether all local Nodes gracefully terminated.
        """
        return not self._nodes

    def kill(self) -> None:
        pass


class JoinBrokerBarrierState(AbstractBrokerState):
    """Waits until all remote Brokers, if any, have their local Nodes gracefully terminated.

    Wait for all dependent remote Brokers to send the acknowledgement messages that they
    no longer dependend on this Broker's data.

    Continue brokering packets until signalled by all remote hosts that there will be no more packets.
    Use the remote SYNC socket to coordinate when every Broker can exit.
    """

    def __init__(self, context: BrokerInterface):
        super().__init__(context)
        self._host_ip = self._context._get_host_ip()
        self._brokers = self._context._get_remote_broker_addresses()
        self._sync_remote_socket: zmq.SyncSocket = (
            self._context._get_sync_remote_socket()
        )

        self._remote_sub_brokers = self._context._get_remote_sub_brokers()
        self._remote_pub_brokers = self._context._get_remote_pub_brokers()

        self._brokers_left_to_acknowledge = set(self._remote_sub_brokers)
        self._brokers_left_to_checkin = set(self._remote_pub_brokers)

        self._poller = zmq.Poller()
        self._poller.register(self._sync_remote_socket, zmq.POLLIN)

    def run(self):
        # Notify Brokers that listen to our data that we are done and ready to exit as soon as they received all last data from us.
        for ip in self._remote_sub_brokers:
            self._sync_remote_socket.send_multipart(
                [
                    ("%s:%s" % (ip, PORT_SYNC_REMOTE)).encode("utf-8"),
                    b"",
                    self._host_ip.encode("utf-8"),
                    CMD_HELLO.encode("utf-8"),
                ]
            )

        # Check every 5 seconds if other Brokers completed their cleanup and responded back ready to exit.
        poll_res: list[tuple[zmq.SyncSocket, zmq.PollEvent]]
        if poll_res := self._poller.poll(5000):  # type: ignore
            socket, _ = poll_res[0]
            address, _, broker_name, cmd = socket.recv_multipart()
            broker_name = broker_name.decode("utf-8")
            print(
                "%s sent %s to %s." % (broker_name, cmd.decode("utf-8"), self._host_ip),
                flush=True,
            )

            if broker_name in self._brokers_left_to_acknowledge:
                # Remote subscriber responded with ACK to us.
                self._brokers_left_to_acknowledge.remove(broker_name)
                self._brokers.pop(broker_name)
            elif broker_name in self._brokers_left_to_checkin:
                # Remote publisher sent a BYE request, respond with an ACK.
                self._brokers_left_to_checkin.remove(broker_name)
                self._brokers.pop(broker_name)
                self._sync_remote_socket.send_multipart(
                    [
                        address,
                        b"",
                        self._host_ip.encode("utf-8"),
                        CMD_BYE.encode("utf-8"),
                    ]
                )

    def is_continue(self) -> bool:
        return not not self._brokers

    def kill(self) -> None:
        pass
