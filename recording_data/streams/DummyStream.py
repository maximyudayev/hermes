from numpy import ndarray
from streams.Stream import Stream


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


  def _append_data(self,
                   time_s: float, 
                   data: ndarray) -> None:
    self._append(self._device_name, 'toa', time_s, data)


  def get_default_visualization_options(self) -> dict:
    return super().get_default_visualization_options()
