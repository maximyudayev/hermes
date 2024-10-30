from streams import Stream
from visualizers import HeatmapVisualizer, LinePlotVisualizer

################################################
################################################
# A structure to store DOTs stream's data.
################################################
################################################
class InsoleStream(Stream):
  def __init__(self, 
               sampling_rate_hz: int = 100) -> None:
    super(InsoleStream, self).__init__()

    # Add devices and streams to organize data from your sensor.
    #   Data is organized as devices and then streams.
    #   For example, a DOTs device may have streams for Gyro and Acceleration.
    self._device_name = 'moticon'
    self.add_stream(device_name=self._device_name,
                    stream_name='timestamp',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)
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

  def append_data(self,
                  time_s: float, 
                  data: bytes):
    data = [float(word) for word in data.split()] # splits byte string into array of bytes, removing whitespace separators
    self._append_data(self._device_name, 'timestamp', time_s, data[0])
    self._append_data(self._device_name, 'foot_pressure_left', time_s, data[9: 25])
    self._append_data(self._device_name, 'foot_pressure_right', time_s, data[34: 50])
    self._append_data(self._device_name, 'acc_left', time_s, data[1:4])
    self._append_data(self._device_name, 'acc_right', time_s, data[26:29] )
    self._append_data(self._device_name, 'gyro_left', time_s, data[4:7])
    self._append_data(self._device_name, 'gyro_right', time_s, data[29:32])
    self._append_data(self._device_name, 'total_force_left', time_s, data[25] )
    self._append_data(self._device_name, 'total_force_right', time_s, data[50])
    self._append_data(self._device_name, 'center_of_pressure_left', time_s, data[7:9])
    self._append_data(self._device_name, 'center_of_pressure_right', time_s, data[32:34])


  ###########################
  ###### VISUALIZATION ######
  ###########################

  # Specify how the streams should be visualized.
  # Return a dict of the form options[device_name][stream_name] = stream_options
  #  Where stream_options is a dict with the following keys:
  #   'class': A subclass of Visualizer that should be used for the specified stream.
  #   Any other options that can be passed to the chosen class.
  def get_default_visualization_options(self, visualization_options=None):
    # Start by not visualizing any streams.
    visualization_options = {}
    for (device_name, device_info) in self._streams_info.items():
      visualization_options.setdefault(device_name, {})
      for (stream_name, stream_info) in device_info.items():
        visualization_options[device_name].setdefault(stream_name, {'class': None})

    # Use a line plot to visualize the weight.
    visualization_options[self._device_name]['stream_1'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,  # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1,  # Can optionally downsample data before visualizing to improve performance.
       }
    visualization_options[self._device_name]['stream_2'] = \
      {'class': HeatmapVisualizer,
       'colorbar_levels': 'auto',  # The range of the colorbar.
       # Can be a 2-element list [min, max] to use hard-coded bounds,
       # or 'auto' to determine them dynamically based on a buffer of the data.
       }

    # Override the above defaults with any provided options.
    if isinstance(visualization_options, dict):
      for (device_name, device_info) in self._streams_info.items():
        if device_name in visualization_options:
          device_options = visualization_options[device_name]
          # Apply the provided options for this device to all of its streams.
          for (stream_name, stream_info) in device_info.items():
            for (k, v) in device_options.items():
              visualization_options[device_name][stream_name][k] = v

    return visualization_options
