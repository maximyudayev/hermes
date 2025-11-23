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
import random

from hermes.utils.time_utils import get_time
from hermes.utils.zmq_utils import PORT_BACKEND, PORT_KILL, PORT_SYNC_HOST
from hermes.utils.types import LoggingSpec

from hermes.dummy.stream import DummyStream
from hermes.base.nodes.producer import Producer


class DummyProducer(Producer):
    """A Node showcasing the Producer behavior, generating new data relayed to the Broker for consumers."""

    @classmethod
    def _log_source_tag(cls) -> str:
        return "dummy-producer"

    def __init__(
        self,
        host_ip: str,
        logging_spec: LoggingSpec,
        sampling_rate_hz: int = 1,
        payload_num_bytes: int = 100,
        port_pub: str = PORT_BACKEND,
        port_sync: str = PORT_SYNC_HOST,
        port_killsig: str = PORT_KILL,
        transmit_delay_sample_period_s: float = float("nan"),
        **_,
    ):
        """Constructor of the DummyProducer Node.

        Args:
            host_ip (str): IP address of the local master Broker.
            logging_spec (LoggingSpec): Specification of what and how to store.
            sampling_rate_hz (int, optional): Expected sample rate of the device. Defaults to 1.
            payload_num_bytes (int, optional): Size of the messages in bytes to generate. Defaults to 100.
            port_pub (str, optional): Local port to publish to for local master Broker to relay. Defaults to PORT_BACKEND.
            port_sync (str, optional): Local port to listen to for local master Broker's startup coordination. Defaults to PORT_SYNC_HOST.
            port_killsig (str, optional): Local port to listen to for local master Broker's termination signal. Defaults to PORT_KILL.
            transmit_delay_sample_period_s (float, optional): Duration of the period over which to estimate propagation delay of measurements from the corresponding device. Defaults to float('nan').
        """

        sampling_rate_hz = (
            sampling_rate_hz
            if isinstance(sampling_rate_hz, (int, float))
            else int(sampling_rate_hz)
        )
        payload_num_bytes = (
            payload_num_bytes
            if isinstance(payload_num_bytes, (int))
            else int(payload_num_bytes)
        )

        self._period = 1 / sampling_rate_hz
        self._payload_num_bytes = payload_num_bytes
        self._sequence = 0
        self._data = random.randbytes(self._payload_num_bytes)
        self._tag: str = "%s.data" % self._log_source_tag()
        self._next_period: float

        stream_out_spec = {
            "sampling_rate_hz": sampling_rate_hz,
            "payload_num_bytes": payload_num_bytes,
        }

        super().__init__(
            host_ip=host_ip,
            stream_out_spec=stream_out_spec,
            logging_spec=logging_spec,
            port_pub=port_pub,
            port_sync=port_sync,
            port_killsig=port_killsig,
            transmit_delay_sample_period_s=transmit_delay_sample_period_s,
        )

    @classmethod
    def create_stream(cls, stream_spec: dict) -> DummyStream:
        return DummyStream(**stream_spec)

    def _ping_device(self) -> None:
        return None

    def _connect(self) -> bool:
        return True

    def _keep_samples(self) -> None:
        self._next_period = get_time() + self._period

    def _process_data(self) -> None:
        if self._is_continue_capture:
            process_time_s = get_time()
            time_to_wait = self._next_period - process_time_s

            if time_to_wait > 0:
                time.sleep(time_to_wait * 0.9)
                while (process_time_s := get_time()) < self._next_period:
                    pass

            self._publish(
                self._tag,
                process_time_s=process_time_s,
                data={
                    "sensor-emulator": {"data": self._data, "sequence": self._sequence}
                },
            )
            self._sequence += 1
            self._next_period += self._period
        else:
            self._send_end_packet()

    def _stop_new_data(self):
        pass

    def _cleanup(self) -> None:
        super()._cleanup()
