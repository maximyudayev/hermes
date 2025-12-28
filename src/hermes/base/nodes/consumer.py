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

import threading
from abc import abstractmethod
from collections import OrderedDict
import zmq

from hermes.utils.time_utils import get_time
from hermes.utils.msgpack_utils import deserialize
from hermes.utils.node_utils import search_node_class
from hermes.utils.zmq_utils import (
    CMD_END,
    CMD_EXIT,
    DNS_LOCALHOST,
    PORT_FRONTEND,
    PORT_KILL,
    PORT_SYNC_HOST,
)
from hermes.utils.types import LoggingSpec

from hermes.base.stream import Stream
from hermes.base.storage.storage import Storage
from hermes.base.nodes.node import Node
from hermes.base.nodes.consumer_interface import ConsumerInterface
from hermes.base.nodes.producer_interface import ProducerInterface
from hermes.base.nodes.pipeline_interface import PipelineInterface


class Consumer(ConsumerInterface, Node):
    """An abstract class to interface with a particular data consumer.

    Subscribes to the modalities specified in and parametrized by `stream_in_specs`.
    """

    def __init__(
        self,
        host_ip: str,
        stream_in_specs: list[dict],
        logging_spec: LoggingSpec,
        port_sub: str = PORT_FRONTEND,
        port_sync: str = PORT_SYNC_HOST,
        port_killsig: str = PORT_KILL,
    ) -> None:
        """Constructor of the Consumer parent class.

        Args:
            host_ip (str): IP address of the local master Broker.
            stream_in_specs (list[dict]): List of mappings of user-configured incoming modalities.
            logging_spec (LoggingSpec): Specification of what and how to store.
            port_sub (str, optional): Local port to subscribe to for incoming relayed data from the local master Broker. Defaults to `PORT_FRONTEND`.
            port_sync (str, optional): Local port to listen to for local master Broker's startup coordination. Defaults to `PORT_SYNC_HOST`.
            port_killsig (str, optional): Local port to listen to for local master Broker's termination signal. Defaults to `PORT_KILL`.
        """
        super().__init__(
            host_ip=host_ip,
            port_sync=port_sync,
            port_killsig=port_killsig,
            ref_time=logging_spec.ref_time_s,
        )
        self._port_sub = port_sub
        self._is_producer_ended: OrderedDict[str, bool] = OrderedDict()
        self._poll_data_fn = self._poll_data_packets

        # Instantiate all desired Streams that the Consumer will subscribe to.
        self._streams: OrderedDict[str, Stream] = OrderedDict()
        for stream_spec in stream_in_specs:
            module_name: str = stream_spec["package"]
            class_name: str = stream_spec["class"]
            specs: dict = stream_spec["settings"]
            # Create the stream datastructure.
            class_type: type[ProducerInterface] | type[PipelineInterface] = search_node_class(module_name, class_name)  # type: ignore
            class_object: Stream = class_type.create_stream(specs)
            # Store the streamer object.
            self._streams.setdefault(class_type._log_source_tag(), class_object)
            self._is_producer_ended.setdefault(class_type._log_source_tag(), False)

        # Create the data storing object.
        self._storage = Storage(self._log_source_tag(), logging_spec)
        # Launch datalogging thread with reference to the Stream object.
        self._storage_thread = threading.Thread(
            target=self._storage, args=(self._streams,)
        )
        self._storage_thread.start()

    def _initialize(self):
        super()._initialize()
        # Socket to subscribe to Producers
        self._sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
        self._sub.connect("tcp://%s:%s" % (DNS_LOCALHOST, self._port_sub))

        # Subscribe to topics for each mentioned local and remote Nodes
        for tag in self._streams.keys():
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
        self._streams[topic_tree[0]].append_data(process_time_s=receive_time, **msg)

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
            self._streams[topic_tree[0]].append_data(process_time_s=receive_time, **msg)

    def _trigger_stop(self):
        self._poll_data_fn = self._poll_ending_data_packets

    @abstractmethod
    def _cleanup(self):
        self._storage.cleanup()
        self._storage_thread.join()
        # Before closing the PUB socket, wait for the 'BYE' signal from the Broker.
        self._sync.send_multipart(
            [self._log_source_tag().encode("utf-8"), CMD_EXIT.encode("utf-8")]
        )
        host, cmd = (
            self._sync.recv_multipart()
        )  # no need to read contents of the message.
        print(
            "%s received %s from %s."
            % (self._log_source_tag(), cmd.decode("utf-8"), host.decode("utf-8")),
            flush=True,
        )
        self._sub.close()
        super()._cleanup()
