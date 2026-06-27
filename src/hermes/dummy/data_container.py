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

from typing import Optional

from hermes.base.data_container import DataContainer


class DummyDataContainer(DataContainer):
    """A Stream structure to store Dummy modality data."""

    def __init__(
        self,
        sampling_rate_hz: Optional[int] = 1,
        payload_num_bytes: Optional[int] = 100,
        buf_len: Optional[int] = 10000,
        **_,
    ) -> None:
        """Constructor of the DummyStream datastructure.

        Args:
            sampling_rate_hz (int, optional): Duration of the period over which new data becomes available. Defaults to `1`.
            payload_num_bytes (int, optional): Size of the messages to send. Defaults to `100`.
            buf_len (int, optional): Length of the circular buffer. Defaults to `10000`.
        """
        super().__init__()

        self.add_channel(
            bundle_name="sensor_emulator1",
            channel_name="sequence",
            data_type="uint32",
            sample_size=[1],
            buf_len=buf_len,
            sampling_rate_hz=int(sampling_rate_hz),
        )
        self.add_channel(
            bundle_name="sensor_emulator1",
            channel_name="toa_s",
            data_type="float64",
            sample_size=[1],
            buf_len=buf_len,
            sampling_rate_hz=int(sampling_rate_hz),
        )
        self.add_channel(
            bundle_name="sensor_emulator1",
            channel_name="data",
            data_type=f"V{payload_num_bytes}",
            sample_size=[1],
            buf_len=buf_len,
            sampling_rate_hz=int(sampling_rate_hz),
            is_measure_rate_hz=True,
        )

        self.add_channel(
            bundle_name="sensor_emulator2",
            channel_name="sequence",
            data_type="uint32",
            sample_size=[1],
            buf_len=buf_len,
            sampling_rate_hz=int(sampling_rate_hz),
        )
        self.add_channel(
            bundle_name="sensor_emulator2",
            channel_name="toa_s",
            data_type="float64",
            sample_size=[1],
            buf_len=buf_len,
            sampling_rate_hz=int(sampling_rate_hz),
        )
        self.add_channel(
            bundle_name="sensor_emulator2",
            channel_name="data",
            data_type=f"V{payload_num_bytes}",
            sample_size=[1],
            buf_len=buf_len,
            sampling_rate_hz=int(sampling_rate_hz),
            is_measure_rate_hz=True,
        )

    def get_fps(self) -> dict[str, float | None]:
        return {
            "sensor_emulator1": super()._get_fps("sensor_emulator1", "data"),
            "sensor_emulator2": super()._get_fps("sensor_emulator2", "data"),
        }


class DummyPipeDataContainer(DataContainer):
    """A Stream structure to store Dummy Pipeline modality data."""

    def __init__(
        self,
        sampling_rate_hz: Optional[int] = 1,
        incoming_payload_num_bytes: Optional[int] = 100,
        buf_len: Optional[int] = 10000,
        **_,
    ) -> None:
        """Constructor of the DummyStream datastructure.

        Args:
            sampling_rate_hz (int, optional): Number of times per second, monotonically spaced, that new data becomes available. Defaults to `1`.
            incoming_payload_num_bytes (int, optional): Size of the messages to send. Defaults to `100`.
            buf_len (int, optional): Length of the circular buffer. Defaults to `10000`.
        """
        super().__init__()

        self.add_channel(
            bundle_name="sensor_emulator_processed",
            channel_name="sequence",
            data_type="uint32",
            sample_size=[1],
            buf_len=buf_len,
        )
        self.add_channel(
            bundle_name="sensor_emulator_processed",
            channel_name="toa_s",
            data_type="float64",
            sample_size=[1],
            buf_len=buf_len,
        )
        self.add_channel(
            bundle_name="sensor_emulator_processed",
            channel_name="data",
            data_type=f"V{incoming_payload_num_bytes}",
            sample_size=[1],
            buf_len=buf_len,
        )
        self.add_channel(
            bundle_name="sensor_emulator_processed",
            channel_name="flag",
            data_type="uint8",
            sample_size=[1],
            buf_len=buf_len,
        )

        self.add_channel(
            bundle_name="sensor_emulator_internal",
            channel_name="sequence",
            data_type="uint32",
            sample_size=[1],
            buf_len=buf_len,
            sampling_rate_hz=int(sampling_rate_hz),
        )
        self.add_channel(
            bundle_name="sensor_emulator_internal",
            channel_name="toa_s",
            data_type="float64",
            sample_size=[1],
            buf_len=buf_len,
            sampling_rate_hz=int(sampling_rate_hz),
        )
        self.add_channel(
            bundle_name="sensor_emulator_internal",
            channel_name="data",
            data_type=f"V{incoming_payload_num_bytes}",
            sample_size=[1],
            buf_len=buf_len,
            sampling_rate_hz=int(sampling_rate_hz),
            is_measure_rate_hz=True,
        )

    def get_fps(self) -> dict[str, float | None]:
        return {
            "sensor_emulator_processed": super()._get_fps(
                "sensor_emulator_processed", "data"
            ),
            "sensor_emulator_internal": super()._get_fps(
                "sensor_emulator_internal", "data"
            ),
        }
