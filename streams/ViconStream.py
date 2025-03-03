from streams import Stream
import dash_bootstrap_components as dbc


##########################################################
##########################################################
# A structure to store data streams from the Vicon system.
##########################################################
##########################################################
class ViconStream(Stream):
  def __init__(self, 
               sampling_rate_hz: int = 20,
               record_mocap: bool = False,
               record_emg: bool = True,
               **_) -> None:
    super().__init__()
    self._sampling_rate_hz = sampling_rate_hz
    self._record_mocap = record_mocap
    self._record_emg = record_emg
    
    self.add_stream(device_name='vicon-data',
                    stream_name='frame_count',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz,
                    is_measure_rate_hz=True)
    self.add_stream(device_name='vicon-data',
                    stream_name='mocap',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name='vicon-data',
                    stream_name='EMG',
                    data_type='float32',
                    sample_size=[16],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name='vicon-data',
                    stream_name='latency',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)


  def get_fps(self) -> dict[str, float]:
    return {'vicon-data': super()._get_fps('vicon-data', 'frame_count')}


  def build_visulizer(self) -> dbc.Row | None:
    return super().build_visulizer()
