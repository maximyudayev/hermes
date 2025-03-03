from streams import Stream
import dash_bootstrap_components as dbc

###############################################
###############################################
# A structure to store TMSi SAGA stream's data.
###############################################
###############################################
class DummyStream(Stream):
  def __init__(self, 
               sampling_rate_hz: int = 100,
               **_) -> None:
    super().__init__()

    self._device_name = 'sensor-emulator'

    self.add_stream(device_name=self._device_name,
                    stream_name='toa',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz,
                    is_measure_rate_hz=True)


  def get_fps(self) -> dict[str, float]:
    return {self._device_name: super()._get_fps(self._device_name, 'toa')}


  def build_visulizer(self) -> dbc.Row | None:
    return super().build_visulizer()
