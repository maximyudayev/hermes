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
               **kwargs) -> None:
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
                    sample_size=[16],
                    sampling_rate_hz=sampling_rate_hz)
    
    self.add_stream(device_name=self._device_name,
                    stream_name='latency',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    
    self.add_stream(device_name=self._device_name,
                    stream_name='frame_count',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    
    self.record_mocap = False
    self.record_EMG = True


  def get_fps(self) -> dict[str, float]:
    return {self._device_name: super()._get_fps(self._device_name, 'breath')}
  

  def append_data(self, time_s: float, mocap, EMG, frame_number) -> None:
    if self.record_mocap:
      self.append_data_mocap(time_s, mocap)
    if self.record_EMG:
      self.append_data_EMG(time_s, EMG)
    
    self._append_data(self._device_name, 'frame_count', time_s, frame_number)


  def append_data_mocap(self,
                  time_s: float, 
                  mocap: ndarray) -> None:
    self._append_data(self._device_name, 'mocap', time_s, mocap)

  def append_data_EMG(self, 
                      time_s: float, 
                      emg: float):
    self._append_data(self._device_name, 'EMG', time_s, emg)



  def get_default_visualization_options(self) -> dict:
    return super().get_default_visualization_options()
