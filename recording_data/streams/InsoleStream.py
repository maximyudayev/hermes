from streams.Stream import Stream
from visualizers import HeatmapVisualizer


####################################################
####################################################
# A structure to store Moticon Insole stream's data.
####################################################
####################################################
class InsoleStream(Stream):
  def __init__(self, 
               sampling_rate_hz: int = 100,
               **_) -> None:
    super().__init__()

    self._device_name = 'moticon'

    self.add_stream(device_name=self._device_name,
                    stream_name='timestamp',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz,
                    is_measure_rate_hz=True)
    self.add_stream(device_name=self._device_name,
                    stream_name='foot_pressure_left',
                    data_type='float32',
                    sample_size=[16],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='foot_pressure_right',
                    data_type='float32',
                    sample_size=[16],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='acc_left',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='acc_right',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='gyro_left',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='gyro_right',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='total_force_left',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='total_force_right',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='center_of_pressure_left',
                    data_type='float32',
                    sample_size=[2],
                    sampling_rate_hz=sampling_rate_hz)
    self.add_stream(device_name=self._device_name,
                    stream_name='center_of_pressure_right',
                    data_type='float32',
                    sample_size=[2],
                    sampling_rate_hz=sampling_rate_hz)


  def get_fps(self) -> dict[str, float]:
    return {self._device_name: super()._get_fps(self._device_name, 'timestamp')}


  def _append_data(self,
                   time_s: float, 
                   data: bytes) -> None:
    # unpacked_tuple = struct.unpack('fx3fx3fx3fx16fxfx3fx3fx3fx16f', data)
    data = [float(word) for word in data.split()] # splits byte string into array of (multiple) bytes, removing whitespace separators between measurements
    self._append(self._device_name, 'timestamp',                 time_s, data[0])
    self._append(self._device_name, 'foot_pressure_left',        time_s, data[9:25])
    self._append(self._device_name, 'foot_pressure_right',       time_s, data[34:50])
    self._append(self._device_name, 'acc_left',                  time_s, data[1:4])
    self._append(self._device_name, 'acc_right',                 time_s, data[26:29])
    self._append(self._device_name, 'gyro_left',                 time_s, data[4:7])
    self._append(self._device_name, 'gyro_right',                time_s, data[29:32])
    self._append(self._device_name, 'total_force_left',          time_s, data[25])
    self._append(self._device_name, 'total_force_right',         time_s, data[50])
    self._append(self._device_name, 'center_of_pressure_left',   time_s, data[7:9])
    self._append(self._device_name, 'center_of_pressure_right',  time_s, data[32:34])


  def get_default_visualization_options(self) -> dict:
    visualization_options = super().get_default_visualization_options()

    # TODO: visualize the foot pressure data from the 16 sensors per side
    # https://moticon.com/wp-content/uploads/2021/09/OpenGo-Sensor-Insole-Specification-A4-RGB-EN-03.03.pdf (p.4)
    # visualization_options[self._device_name]['foot_pressure_left'] = \
    #   {'class': HeatmapVisualizer,
    #    'colorbar_levels': 'auto',  # The range of the colorbar.
    #    # Can be a 2-element list [min, max] to use hard-coded bounds,
    #    # or 'auto' to determine them dynamically based on a buffer of the data.
    #    }
    # visualization_options[self._device_name]['foot_pressure_right'] = \
    #   {'class': HeatmapVisualizer,
    #    'colorbar_levels': 'auto',  # The range of the colorbar.
    #    # Can be a 2-element list [min, max] to use hard-coded bounds,
    #    # or 'auto' to determine them dynamically based on a buffer of the data.
    #    }

    return visualization_options
