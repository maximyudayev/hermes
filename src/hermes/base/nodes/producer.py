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

from abc import abstractmethod
from multiprocessing import Process, Event
import threading
from typing import Optional
import zmq
import math

from hermes.utils.mp_utils import launch_handler
from hermes.utils.msgpack_utils import serialize
from hermes.utils.zmq_utils import (
    CMD_END,
    CMD_EXIT,
    DNS_LOCALHOST,
    PORT_BACKEND,
    PORT_KILL,
    PORT_SYNC_HOST,
)
from hermes.utils.types import LoggingSpec, NewData

from hermes.base.data_container import DataContainer
from hermes.base.storage.storage import Storage
from hermes.base.delay_estimator import DelayEstimator
from hermes.base.nodes.node import Node
from hermes.base.nodes.producer_interface import ProducerInterface


class Producer(ProducerInterface, Node):
    """An abstract class wrapping an interface with a particular device into a Producer Node."""

    def __init__(
        self,
        node_id: str,
        host_ip: str,
        data_out_spec: dict,
        logging_spec: LoggingSpec,
        sampling_rate_hz: Optional[float] = float("nan"),
        port_pub: Optional[str] = PORT_BACKEND,
        port_sync: Optional[str] = PORT_SYNC_HOST,
        port_killsig: Optional[str] = PORT_KILL,
        transmit_delay_sample_period_s: Optional[float] = float("nan"),
    ) -> None:
        """Constructor of the Producer parent class.

        Args:
            node_id (str): Uniquely identifying tag for the Producer and its data.
            host_ip (str): IP address of the local master Broker.
            data_out_spec (dict): Mapping of corresponding `DataContainer` object parameters to user-defined configuration values.
            logging_spec (LoggingSpec): Specification of what and how to store.
            sampling_rate_hz (float, optional): Expected sample rate of the device. Defaults to `float('nan')`.
            port_pub (str, optional): Local port to publish to for local master Broker to relay. Defaults to `PORT_BACKEND`.
            port_sync (str, optional): Local port to listen to for local master Broker's startup coordination. Defaults to `PORT_SYNC_HOST`.
            port_killsig (str, optional): Local port to listen to for local master Broker's termination signal. Defaults to `PORT_KILL`.
            transmit_delay_sample_period_s (float, optional): Duration of the period over which to estimate propagation delay of measurements from the corresponding device. Defaults to `float('nan')`.
        """
        super().__init__(
            node_id=node_id,
            host_ip=host_ip,
            port_sync=port_sync,
            port_killsig=port_killsig,
            ref_time=logging_spec.ref_time_s,
        )
        self._sampling_rate_hz = sampling_rate_hz
        self._sampling_period = 1 / sampling_rate_hz
        self._port_pub = port_pub
        self._is_continue_capture = True
        self._transmit_delay_sample_period_s = transmit_delay_sample_period_s
        self._publish_fn = lambda process_time_s, new_data: None
        self._active_subscriptions: set[str] = set()

        # Data structure for keeping track of data.
        self._data_container: DataContainer = self.create_data_container(data_out_spec)

        # Create and spawn data storing subprocess with reference to the `Stream` object, to save `Producer`s outputs.
        self._is_cleanup_event = Event()

        self._is_storage_enabled = (
            logging_spec.stream_hdf5 or
            logging_spec.stream_csv or
            logging_spec.stream_video or
            logging_spec.stream_audio
        )
        if self._is_storage_enabled:
            self._storage_proc = Process(
                target=launch_handler,
                args=(Storage,),
                kwargs={
                    "log_tag": self.node_id,
                    "spec": logging_spec,
                    "data_containers": {
                        self.node_id: self._data_container.get_info_all(),
                    },
                    "is_cleanup_event": self._is_cleanup_event,
                },
            )
            self._storage_proc.start()

        # Conditional creation of the transmission delay estimate thread.
        if not math.isnan(self._transmit_delay_sample_period_s):
            self._delay_estimator = DelayEstimator(self._transmit_delay_sample_period_s)
            self._delay_thread = threading.Thread(
                target=self._delay_estimator,
                kwargs={
                    "ping_fn": self._ping_device,
                    "publish_fn": lambda time_s, delay_s: self._publish(
                        node_id="%s.connection" % self.node_id,
                        time_s=time_s,
                        data={
                            "%s_connection" % self.node_id: {
                                "transmission_delay": delay_s
                            }
                        },
                    ),
                },
            )
            self._delay_thread.start()

    def _publish(self, process_time_s: float, new_data: NewData) -> None:
        """Common method to save and publish the captured sample.

        Pass generated data to the ZeroMQ message exchange layer.
        Best to deal with data structure (threading primitives) AFTER handing off packet to ZeroMQ.
        That way network thread can already start processing the packet.

        Args:
            process_time_s (float): Time when the new data was processed by the foreground thread and relayed to the middleware.
            new_data (NewData): Data to be published to the middleware and to be locally stored.
        """
        self._publish_fn(process_time_s, new_data)

    def _initialize(self):
        super()._initialize()
        # Socket to publish sensor data and log
        self._pub: zmq.SyncSocket = self._ctx.socket(zmq.XPUB)
        self._pub.connect("tcp://%s:%s" % (DNS_LOCALHOST, self._port_pub))
        while not self._connect():
            print(f"Reconnecting {self.node_id}", flush=True)

    def _activate_subscription_poller(self) -> None:
        self._poller.register(self._pub, zmq.POLLIN)

    def _activate_data_poller(self) -> None:
        self._poller.register(self._pub, zmq.POLLOUT)

    def _update_subscriptions(self) -> None:
        msg = self._pub.recv_multipart()
        msg_decoded = msg[0].decode("utf-8")
        topic = msg_decoded[1:].split(".")[1]
        if topic in self._data_container.get_bundle_names():
            if "\x01" == msg_decoded[0]:
                self._active_subscriptions.add(topic)
            elif "\x00" == msg_decoded[0]:
                self._active_subscriptions.discard(topic)

    def _is_bundle_requested(self, bundle_name: str) -> bool:
        return bundle_name in self._active_subscriptions

    def _on_poll(self, poll_res: tuple[list[zmq.SyncSocket], list[int]]):
        # Process custom event first, then Node generic (killsig).
        if self._pub in poll_res[0]:
            idx = poll_res[0].index(self._pub)
            if poll_res[1][idx] & zmq.POLLOUT:
                self._process_data()
            if poll_res[1][idx] & zmq.POLLIN:
                self._update_subscriptions()
        super()._on_poll(poll_res)

    def _on_sync_complete(self) -> None:
        self._publish_fn = self._store_and_broadcast
        self._keep_samples()

    def _store_and_broadcast(self, process_time_s: float, new_data: NewData) -> None:
        """Place captured data into the corresponding DataContainer datastructure and transmit serialized ZeroMQ packets to subscribers.

        Args:
            process_time_s (float): Time of consumption of the captured samples by the `HERMES` middleware.
            new_data (NewData): Data in bundles to be serialized and sent, and stored locally.
        """
        for bundle_name, bundle_data in new_data.items():
            if self._is_bundle_requested(bundle_name):
                comp_topic = f"{self.node_id}.{bundle_name}"
                msg = serialize({bundle_name: bundle_data})
                self._pub.send_multipart([comp_topic.encode("utf-8"), msg])
        self._data_container.push(process_time_s=process_time_s, data=new_data)

    def _trigger_stop(self):
        self._is_continue_capture = False
        self._stop_new_data()

    def _send_end_packet(self) -> None:
        """Send 'END' empty packet and label Node as done to safely finish and exit the process and its threads."""
        self._pub.send_multipart(
            [
                ("%s.notify" % self.node_id).encode("utf-8"),
                CMD_END.encode("utf-8"),
            ]
        )
        self._is_done = True

    @abstractmethod
    def _cleanup(self) -> None:
        # Indicate to `Storage` subproc to wrap up and exit.
        self._is_cleanup_event.set()

        if not math.isnan(self._transmit_delay_sample_period_s):
            self._delay_estimator.cleanup()

        # Before closing the PUB socket, wait for the 'BYE' signal from the Broker.
        self._sync.send_multipart(
            [self.node_id.encode("utf-8"), CMD_EXIT.encode("utf-8")]
        )
        host, cmd = (
            self._sync.recv_multipart()
        )  # no need to read contents of the message.
        print(
            "%s received %s from %s."
            % (self.node_id, cmd.decode("utf-8"), host.decode("utf-8")),
            flush=True,
        )
        self._pub.close()

        # Join on the logging background process last, so that all things can finish in parallel.
        if self._is_storage_enabled:
            self._storage_proc.join()

        if not math.isnan(self._transmit_delay_sample_period_s):
            self._delay_thread.join()

        # Release allocated shared memory for the `Stream`.
        self._data_container.clear_all()
        self._data_container.close_all()
        self._data_container.unlink_all()

        super()._cleanup()
