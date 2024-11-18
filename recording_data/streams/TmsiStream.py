from numpy import ndarray
from streams.Stream import Stream
from visualizers import LinePlotVisualizer

################################################
################################################
# A structure to store DOTs stream's data.
################################################
################################################
class TmsiStream(Stream):
  def __init__(self, **kwargs) -> None:
    super().__init__()
    self._device_name = 'Tmsi-SAGA'
    self._data_notes_stream = {
      
    }

    # Add devices and streams to organize data from your sensor.
    #   Data is organized as devices and then streams.
    #   For example, a DOTs device may have streams for Gyro and Acceleration.
    self.add_stream(device_name=self._device_name,
                    stream_name='breath',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")
    
    self.add_stream(device_name=self._device_name,
                    stream_name='GSR',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")
    
    self.add_stream(device_name=self._device_name,
                    stream_name='SPO2',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")
    
    self.add_stream(device_name=self._device_name,
                    stream_name='BIP01',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")
    
    self.add_stream(device_name=self._device_name,
                    stream_name='BIP02',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")

  def append_data(self,
                  time_s: float, 
                  column: ndarray,):
            self._append_data(self._device_name, 'BIP01', time_s, column[0])
            self._append_data(self._device_name, 'BIP02', time_s, column[1])
            self._append_data(self._device_name, 'breath', time_s, column[2])
            self._append_data(self._device_name, 'GSR',    time_s, column[3])
            self._append_data(self._device_name, 'SPO2',   time_s, column[4])

  def get_default_visualization_options(self):
       return super().get_default_visualization_options()