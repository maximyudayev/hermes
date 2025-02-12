from streams.Stream import Stream


###############################################
###############################################
# A structure to store TMSi SAGA stream's data.
###############################################
###############################################
class TmsiStream(Stream):
  def __init__(self, 
               sampling_rate_hz: int = 20,
               transmission_delay_period_s: int = 10,
               **_) -> None:
    super().__init__()
    self._sampling_rate_hz = sampling_rate_hz
    self._transmission_delay_period_s = transmission_delay_period_s

    self.add_stream(device_name='tmsi-data',
                    stream_name='breath',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz,
                    is_measure_rate_hz=True)
    self.add_stream(device_name='tmsi-data',
                    stream_name='GSR',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name='tmsi-data',
                    stream_name='SPO2',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name='tmsi-data',
                    stream_name='BIP-01',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name='tmsi-data',
                    stream_name='BIP-02',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)

    self.add_stream(device_name='tmsi-connection',
                    stream_name='transmission_delay',
                    data_type='float32',
                    sample_size=(1),
                    sampling_rate_hz=1.0/self._transmission_delay_period_s)


  def get_fps(self) -> dict[str, float]:
    return {'tmsi-data': super()._get_fps('tmsi-data', 'breath')}


  def get_default_visualization_options(self) -> dict:
    return super().get_default_visualization_options()
