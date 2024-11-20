from numpy import ndarray
from streams.Stream import Stream

#########################################
#########################################
# A structure to store DOTs stream's data
#########################################
#########################################
class ViconStream(Stream):
  def __init__(self, 
               sampling_rate_hz: int = 20,
               **_) -> None:
    super().__init__()
    self._device_name = 'vicon'

    self.add_stream(device_name=self._device_name,
                    stream_name='mocap',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=sampling_rate_hz,
                    is_measure_rate_hz=True)
    self.add_stream(device_name=self._device_name,
                    stream_name='EMG',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)


  def get_fps(self) -> dict[str, float]:
    return {self._device_name: super()._get_fps(self._device_name, 'breath')}


  def append_data_mocap(self,
                  time_s: float, 
                  mocap: ndarray) -> None:
    self._append_data(self._device_name, 'mocap', time_s, mocap)

  def append_data_EMG(self, time_s: float, 
                  emg: float):
    self._append_data(self._device_name, 'EMG', time_s, emg)



  def get_default_visualization_options(self) -> dict:
    return super().get_default_visualization_options()
