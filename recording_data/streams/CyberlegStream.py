from streams.Stream import Stream


###############################################
###############################################
# A structure to store Cyberleg FSM state data.
###############################################
###############################################
class CyberlegStream(Stream):
  def __init__(self, 
               sampling_rate_hz: int = 0,
               **_) -> None:
    super().__init__()

    self._device_name = 'cyberleg'

    self.add_stream(device_name=self._device_name,
                    stream_name='activity',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz,
                    is_measure_rate_hz=True)
    self.add_stream(device_name=self._device_name,
                    stream_name='timestamp',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)


  def get_fps(self) -> dict[str, float]:
    return {self._device_name: super()._get_fps(self._device_name, 'activity')}


  def _append_data(self,
                   time_s: float, 
                   data: bytes) -> None:
    # TODO: interpret smartphone bytes correctly from the prosthesis
    data = [float(word) for word in data.split()] # splits byte string into array of (multiple) bytes, removing whitespace separators between measurements
    self._append(self._device_name, 'activity',   time_s, data[0])
    self._append(self._device_name, 'timestamp',  time_s, data[1])


  def get_default_visualization_options(self) -> dict:
    return super().get_default_visualization_options()
