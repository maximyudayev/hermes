from streams import Stream
import dash_bootstrap_components as dbc


##########################################
##########################################
# A structure to store Moxy stream's data.
##########################################
##########################################
class MoxyStream(Stream):
  def __init__(self, 
               devices: list[str],
               sampling_rate_hz: float = 0.5,
               transmission_delay_period_s: int = None,
               **_) -> None:
    super().__init__()
    self._devices = devices
    self._sampling_rate_hz = sampling_rate_hz
    self._transmission_delay_period_s = transmission_delay_period_s

    for dev in devices:
      self.add_stream(device_name='moxy-%s-data'%dev,
                      stream_name='THb',
                      data_type='float32',
                      sample_size=[1],
                      sampling_rate_hz=sampling_rate_hz)
      self.add_stream(device_name='moxy-%s-data'%dev,
                      stream_name='SmO2',
                      data_type='float32',
                      sample_size=[1],
                      sampling_rate_hz=sampling_rate_hz)
      self.add_stream(device_name='moxy-%s-data'%dev,
                      stream_name='counter',
                      data_type='uint8',
                      sample_size=[1],
                      is_measure_rate_hz=True,
                      sampling_rate_hz=sampling_rate_hz)

      if self._transmission_delay_period_s:
        self.add_stream(device_name='moxy-%s-connection'%dev,
                        stream_name='transmission_delay',
                        data_type='float32',
                        sample_size=(1),
                        sampling_rate_hz=1.0/self._transmission_delay_period_s)

  
  def get_fps(self) -> dict[str, float]:
    return {device: super()._get_fps(device, 'counter') for device in self._devices}


  def build_visulizer(self) -> dbc.Row | None:
    return super().build_visulizer()
