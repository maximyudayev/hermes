import numpy as np
from streams.Stream import Stream

#########################################
#########################################
# A structure to store Moxy stream's data
#########################################
#########################################
class MoxyStream(Stream):
  def __init__(self, devices, **kwargs) -> None:
    super().__init__()

    self._devices = devices

    for dev in devices:
        self.add_stream(device_name=dev,
                        stream_name='THb',
                        data_type='float32',
                        sample_size=[1],
                        sampling_rate_hz=0.5)
        self.add_stream(device_name=dev,
                        stream_name='SmO2',
                        data_type='float32',
                        sample_size=[1],
                        sampling_rate_hz=0.5)
        self.add_stream(device_name=dev,
                        stream_name='counter',
                        data_type='uint8',
                        sample_size=[1],
                        is_measure_rate_hz=True,
                        sampling_rate_hz=0.5)

  
  def get_fps(self) -> dict[str, float]:
    pass
    # return {device: super()._get_fps(device, 'counter') for device in self._devices}


  def append_data(self,
                  device_id: str,
                  time_s: float,
                  THb: np.ndarray,
                  SmO2: np.ndarray,
                  counter: np.ndarray):
    self._append_data(device_id, 'THb', time_s, THb)
    self._append_data(device_id, 'SmO2', time_s, SmO2)
    self._append_data(device_id, 'counter', time_s, counter)


  def get_default_visualization_options(self):
    return super().get_default_visualization_options()
