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

from abc import abstractmethod
from collections import OrderedDict
import threading
import zmq
import math

from hermes.utils.msgpack_utils import serialize
from hermes.utils.zmq_utils import (
    CMD_END,
    CMD_EXIT,
    DNS_LOCALHOST,
    PORT_BACKEND,
    PORT_KILL,
    PORT_SYNC_HOST,
)
from hermes.utils.types import LoggingSpec

from hermes.base.stream import Stream
from hermes.base.storage.storage import Storage
from hermes.base.delay_estimator import DelayEstimator
from hermes.base.nodes.node import Node
from hermes.base.nodes.producer_interface import ProducerInterface


class Producer(ProducerInterface, Node):
    """An abstract class wrapping an interface with a particular device into a Producer Node."""

    def __init__(
        self,
        host_ip: str,
        stream_out_spec: dict,
        logging_spec: LoggingSpec,
        sampling_rate_hz: float = float("nan"),
        port_pub: str = PORT_BACKEND,
        port_sync: str = PORT_SYNC_HOST,
        port_killsig: str = PORT_KILL,
        transmit_delay_sample_period_s: float = float("nan"),
    ) -> None:
        """Constructor of the Producer parent class.

        Args:
            host_ip (str): IP address of the local master Broker.
            stream_out_spec (dict): Mapping of corresponding Stream object parameters to user-defined configuration values.
            logging_spec (LoggingSpec): Specification of what and how to store.
            sampling_rate_hz (float, optional): Expected sample rate of the device. Defaults to `float('nan')`.
            port_pub (str, optional): Local port to publish to for local master Broker to relay. Defaults to `PORT_BACKEND`.
            port_sync (str, optional): Local port to listen to for local master Broker's startup coordination. Defaults to `PORT_SYNC_HOST`.
            port_killsig (str, optional): Local port to listen to for local master Broker's termination signal. Defaults to `PORT_KILL`.
            transmit_delay_sample_period_s (float, optional): Duration of the period over which to estimate propagation delay of measurements from the corresponding device. Defaults to `float('nan')`.
        """
        super().__init__(
            host_ip=host_ip,
            port_sync=port_sync,
            port_killsig=port_killsig,
            ref_time=logging_spec.log_time_s,
        )
        self._sampling_rate_hz = sampling_rate_hz
        self._sampling_period = 1 / sampling_rate_hz
        self._port_pub = port_pub
        self._is_continue_capture = True
        self._transmit_delay_sample_period_s = transmit_delay_sample_period_s
        self._publish_fn = lambda tag, **kwargs: None

        # Data structure for keeping track of data
        self._stream: Stream = self.create_stream(stream_out_spec)

        # Create the DataLogger object
        self._logger = Storage(self._log_source_tag(), logging_spec)

        # Launch datalogging thread with reference to the Stream object.
        self._logger_thread = threading.Thread(
            target=self._logger,
            args=(OrderedDict([(self._log_source_tag(), self._stream)]),),
        )
        self._logger_thread.start()

        # Conditional creation of the transmission delay estimate thread.
        if not math.isnan(self._transmit_delay_sample_period_s):
            self._delay_estimator = DelayEstimator(self._transmit_delay_sample_period_s)
            self._delay_thread = threading.Thread(
                target=self._delay_estimator,
                kwargs={
                    "ping_fn": self._ping_device,
                    "publish_fn": lambda time_s, delay_s: self._publish(
                        tag="%s.connection" % self._log_source_tag(),
                        time_s=time_s,
                        data={
                            "%s-connection"
                            % self._log_source_tag(): {"transmission_delay": delay_s}
                        },
                    ),
                },
            )
            self._delay_thread.start()

    def _publish(self, tag: str, **kwargs) -> None:
        """Common method to save and publish the captured sample.

        Best to deal with data structure (threading primitives) AFTER handing off packet to ZeroMQ.
        That way network thread can already start processing the packet.

        Args:
            tag (str): Uniquely identifying key for the modality to label data for message exchange.
        """
        self._publish_fn(tag, **kwargs)

    def _initialize(self):
        super()._initialize()
        # Socket to publish sensor data and log
        self._pub: zmq.SyncSocket = self._ctx.socket(zmq.PUB)
        self._pub.connect("tcp://%s:%s" % (DNS_LOCALHOST, self._port_pub))
        self._connect()

    def _activate_data_poller(self) -> None:
        self._poller.register(self._pub, zmq.POLLOUT)

    def _on_poll(self, poll_res):
        # Process custom event first, then Node generic (killsig).
        if self._pub in poll_res[0]:
            self._process_data()
        super()._on_poll(poll_res)

    def _on_sync_complete(self) -> None:
        self._publish_fn = self._store_and_broadcast
        self._keep_samples()

    def _store_and_broadcast(self, tag: str, process_time_s: float, **kwargs) -> None:
        """Place captured data into the corresponding Stream datastructure and transmit serialized ZeroMQ packets to subscribers.

        Args:
            tag (str): Uniquely identifying key for the modality to label data for message exchange.
        """
        msg = serialize(**kwargs)
        self._pub.send_multipart([tag.encode("utf-8"), msg])
        self._stream.append_data(process_time_s=process_time_s, **kwargs)

    def _trigger_stop(self):
        self._is_continue_capture = False
        self._stop_new_data()

    def _send_end_packet(self) -> None:
        """Send 'END' empty packet and label Node as done to safely finish and exit the process and its threads."""
        self._pub.send_multipart(
            [
                ("%s.data" % self._log_source_tag()).encode("utf-8"),
                CMD_END.encode("utf-8"),
            ]
        )
        self._is_done = True

    @abstractmethod
    def _cleanup(self) -> None:
        # Indicate to Logger to wrap up and exit.
        self._logger.cleanup()
        if not math.isnan(self._transmit_delay_sample_period_s):
            self._delay_estimator.cleanup()
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
        self._pub.close()
        # Join on the logging background thread last, so that all things can finish in parallel.
        self._logger_thread.join()
        if not math.isnan(self._transmit_delay_sample_period_s):
            self._delay_thread.join()
        super()._cleanup()
