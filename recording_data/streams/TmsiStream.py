from numpy import ndarray
from streams.Stream import Stream


###############################################
###############################################
# A structure to store TMSi SAGA stream's data.
###############################################
###############################################
class TmsiStream(Stream):
  def __init__(self, 
               sampling_rate_hz: int = 20,
               **_) -> None:
    super().__init__()

    self._device_name = 'tmsi'

    self.add_stream(device_name=self._device_name,
                    stream_name='breath',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz,
                    is_measure_rate_hz=True)
    self.add_stream(device_name=self._device_name,
                    stream_name='GSR',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='SPO2',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='BIP-01',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='BIP-02',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)


  def get_fps(self) -> dict[str, float]:
    return {self._device_name: super()._get_fps(self._device_name, 'breath')}


  def _append_data(self,
                   time_s: float, 
                   column: ndarray) -> None:
    self._append(self._device_name, 'BIP-01', time_s, column[0])
    self._append(self._device_name, 'BIP-02', time_s, column[1])
    self._append(self._device_name, 'breath', time_s, column[2])
    self._append(self._device_name, 'GSR',    time_s, column[3])
    self._append(self._device_name, 'SPO2',   time_s, column[4])


  def get_default_visualization_options(self) -> dict:
    return super().get_default_visualization_options()
