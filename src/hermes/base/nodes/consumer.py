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

from multiprocessing import Event, Process
from abc import abstractmethod
from collections import OrderedDict
from typing import Optional
import zmq

from hermes.utils.mp_utils import launch_handler
from hermes.utils.time_utils import get_time
from hermes.utils.msgpack_utils import deserialize
from hermes.utils.di_utils import search_module_class
from hermes.utils.zmq_utils import (
    CMD_END,
    CMD_EXIT,
    DNS_LOCALHOST,
    PORT_FRONTEND,
    PORT_KILL,
    PORT_SYNC_HOST,
)
from hermes.utils.types import LoggingSpec

from hermes.base.nodes.node import Node
from hermes.base.data_container import DataContainer
from hermes.base.storage.storage import Storage
from hermes.base.nodes.consumer_interface import ConsumerInterface
from hermes.base.nodes.producer_interface import ProducerInterface
from hermes.base.nodes.pipeline_interface import PipelineInterface


class Consumer(ConsumerInterface, Node):
    """An abstract class to interface with a particular data consumer.

    Subscribes to the modalities specified in and parametrized by `stream_in_specs`.
    """

    def __init__(
        self,
        topic: str,
        host_ip: str,
        data_in_specs: list[dict],
        logging_spec: LoggingSpec,
        port_sub: Optional[str] = PORT_FRONTEND,
        port_sync: Optional[str] = PORT_SYNC_HOST,
        port_killsig: Optional[str] = PORT_KILL,
    ) -> None:
        """Constructor of the Consumer parent class.

        Args:
            topic (str): Uniquely identifying tag for the Consumer and its data.
            host_ip (str): IP address of the local master Broker.
            data_in_specs (list[dict]): List of mappings of user-configured incoming modalities.
            logging_spec (LoggingSpec): Specification of what and how to store.
            port_sub (str, optional): Local port to subscribe to for incoming relayed data from the local master Broker. Defaults to `PORT_FRONTEND`.
            port_sync (str, optional): Local port to listen to for local master Broker's startup coordination. Defaults to `PORT_SYNC_HOST`.
            port_killsig (str, optional): Local port to listen to for local master Broker's termination signal. Defaults to `PORT_KILL`.
        """
        super().__init__(
            topic=topic,
            host_ip=host_ip,
            port_sync=port_sync,
            port_killsig=port_killsig,
            ref_time=logging_spec.ref_time_s,
        )
        self._port_sub = port_sub
        self._is_producer_ended: OrderedDict[str, bool] = OrderedDict()
        self._poll_data_fn = self._poll_data_packets

        # Instantiate all desired `Streams` that the `Consumer` will subscribe to.
        self._data_containers: OrderedDict[str, DataContainer] = OrderedDict()
        for data_spec in data_in_specs:
            topic_name: str = data_spec["topic"]
            module_name: str = data_spec["package"]
            class_name: str = data_spec["class"]
            spec: dict = data_spec["settings"]
            # Create the stream datastructure.
            class_type: type[ProducerInterface] | type[PipelineInterface] = (
                search_module_class(module_name, class_name)
            )
            class_object: DataContainer = class_type.create_data_container(spec)
            # Store the streamer object.
            self._data_containers.setdefault(topic_name, class_object)
            self._is_producer_ended.setdefault(topic_name, False)

        # Create and spawn data storing subprocess with reference to the `Stream` objects, to save `Consumer`s inputs.
        self._is_cleanup_event = Event()
        self._storage_proc = Process(
            target=launch_handler,
            args=(Storage,),
            kwargs={
                "log_tag": self.topic,
                "spec": logging_spec,
                "data_containers": {
                    node_name: data_container.get_info_all()
                    for node_name, data_container in self._data_containers.items()
                },
                "is_cleanup_event": self._is_cleanup_event,
            },
        )
        self._storage_proc.start()

    def _initialize(self):
        super()._initialize()
        # Socket to subscribe to Producers
        self._sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
        self._sub.connect("tcp://%s:%s" % (DNS_LOCALHOST, self._port_sub))

        # Subscribe to topics for each mentioned local and remote Nodes
        for tag in self._data_containers.keys():
            self._sub.subscribe(tag)

    # Launch data receiving.
    def _activate_data_poller(self) -> None:
        self._poller.register(self._sub, zmq.POLLIN)

    # Process custom event first, then Node generic (killsig).
    def _on_poll(self, poll_res):
        if self._sub in poll_res[0]:
            self._poll_data_fn()
        super()._on_poll(poll_res)

    def _on_sync_complete(self) -> None:
        pass

    def _poll_data_packets(self) -> None:
        """Receive data packets in a steady state.

        Gets called every time one of the requestes modalities produced new data.
        In normal operation mode, all messages are 2-part.
        """
        topic, payload = self._sub.recv_multipart()
        receive_time = get_time()
        msg = deserialize(payload)
        topic_tree: list[str] = topic.decode("utf-8").split(".")
        self._data_containers[topic_tree[0]].push(process_time_s=receive_time, **msg)

    def _poll_ending_data_packets(self) -> None:
        """Receive data packets from producers and monitor for end-of-stream signal.

        When system triggered a safe exit, Pipeline gets a mix of normal 2-part messages
        and 3-part 'END' message from each Producer that safely exited.
        It's more efficient to dynamically switch the callback instead of checking every message.

        Processes packets on each modality until all data sources sent the 'END' packet.
        If triggered to stop and no more available data, sends empty 'END' packet and joins.
        """
        topic, payload = self._sub.recv_multipart()
        receive_time = get_time()
        # 'END' empty packet from a Producer.
        if CMD_END.encode("utf-8") in payload:
            topic_tree: list[str] = topic.decode("utf-8").split(".")
            self._is_producer_ended[topic_tree[0]] = True
            if all(list(self._is_producer_ended.values())):
                self._is_done = True
        # Regular data packets.
        else:
            msg = deserialize(payload)
            topic_tree: list[str] = topic.decode("utf-8").split(".")
            self._data_containers[topic_tree[0]].push(process_time_s=receive_time, **msg)

    def _trigger_stop(self):
        self._poll_data_fn = self._poll_ending_data_packets

    @abstractmethod
    def _cleanup(self):
        # Indicate to `Storage` subproc to wrap up and exit.
        self._is_cleanup_event.set()

        # Before closing the PUB socket, wait for the 'BYE' signal from the Broker.
        self._sync.send_multipart(
            [self.topic.encode("utf-8"), CMD_EXIT.encode("utf-8")]
        )
        host, cmd = (
            self._sync.recv_multipart()
        )  # no need to read contents of the message.
        print(
            "%s received %s from %s."
            % (self.topic, cmd.decode("utf-8"), host.decode("utf-8")),
            flush=True,
        )
        self._sub.close()

        # Join on the logging background process last, so that all things can finish in parallel.
        self._storage_proc.join()

        # Release allocated shared memory for the `Streams`.
        for stream in self._data_containers.values():
            stream.clear_all()
            stream.close_all()
            stream.unlink_all()

        super()._cleanup()
