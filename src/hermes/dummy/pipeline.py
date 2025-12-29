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

import random
import string
from hermes.utils.time_utils import get_time
from hermes.utils.zmq_utils import (
    PORT_BACKEND,
    PORT_FRONTEND,
    PORT_KILL,
    PORT_SYNC_HOST,
)
from hermes.utils.types import LoggingSpec

from hermes.dummy.stream import DummyPipeStream
from hermes.base.nodes.pipeline import Pipeline


class DummyPipeline(Pipeline):
    """A Node showcasing the Pipeline behavior, consuming external data and generating new data relayed back to the Broker."""

    @classmethod
    def _log_source_tag(cls) -> str:
        return "dummy-pipeline"

    def __init__(
        self,
        host_ip: str,
        stream_out_spec: dict,
        stream_in_specs: list[dict],
        logging_spec: LoggingSpec,
        is_async_generate: bool = False,
        port_pub: str = PORT_BACKEND,
        port_sub: str = PORT_FRONTEND,
        port_sync: str = PORT_SYNC_HOST,
        port_killsig: str = PORT_KILL,
        **_,
    ):
        """Constructor of the DummyPipeline Node.

        Args:
            host_ip (str): IP address of the local master Broker.
            stream_out_spec (dict): Mapping of corresponding Stream object parameters to user-defined configuration values.
            stream_in_specs (list[dict]): List of mappings of user-configured incoming modalities.
            logging_spec (LoggingSpec): Specification of what and how to store.
            is_async_generate (bool, optional): Whether the Pipeline produces data asynchronously, in parallel to what is fed into it. Defaults to `False`.
            port_pub (str, optional): Local port to publish to for local master Broker to relay. Defaults to `PORT_BACKEND`.
            port_sub (str, optional): Local port to subscribe to for incoming relayed data from the local master Broker. Defaults to `PORT_FRONTEND`.
            port_sync (str, optional): Local port to listen to for local master Broker's startup coordination. Defaults to `PORT_SYNC_HOST`.
            port_killsig (str, optional): Local port to listen to for local master Broker's termination signal. Defaults to `PORT_KILL`.
        """
        self._is_continue_generate = True
        self._is_keep_samples = False
        self._sequence = 0
        self._period = 1 / stream_out_spec["sampling_rate_hz"]
        self._next_period: float

        super().__init__(
            host_ip=host_ip,
            stream_out_spec=stream_out_spec,
            stream_in_specs=stream_in_specs,
            logging_spec=logging_spec,
            is_async_generate=is_async_generate,
            port_pub=port_pub,
            port_sub=port_sub,
            port_sync=port_sync,
            port_killsig=port_killsig,
        )

    @classmethod
    def create_stream(cls, stream_spec: dict) -> DummyPipeStream:
        return DummyPipeStream(**stream_spec)

    def _keep_samples(self) -> None:
        self._is_keep_samples = True
        self._next_period = get_time() + self._period

    def _process_data(self, topic: str, msg: dict) -> None:
        process_time_s: float = get_time()
        tag: str = "%s.data" % self._log_source_tag()
        data = msg["data"]["sensor-emulator"]
        data["flag"] = 1
        self._publish(tag, process_time_s=process_time_s, data={"sensor-emulator-processed": data})

    def _generate_data(self) -> None:
        if self._is_keep_samples and self._is_continue_generate:
            process_time_s = get_time()
            if self._next_period <= process_time_s:
                tag: str = "%s.data" % self._log_source_tag()
                data = {
                    "data": ''.join([random.choice(string.printable) for _ in range(random.randint(1, 100))]).encode("ascii"),
                    "sequence": self._sequence,
                }
                self._publish(tag, process_time_s=process_time_s, data={"sensor-emulator-internal": data})
                self._sequence += 1
                self._next_period += self._period
        elif self._is_keep_samples and not self._is_continue_generate:
            self._notify_no_more_data_out()

    def _stop_new_data(self):
        self._is_continue_generate = False

    def _cleanup(self) -> None:
        super()._cleanup()
