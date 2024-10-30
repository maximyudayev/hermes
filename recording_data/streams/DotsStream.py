from numpy import ndarray
from streams import Stream
from visualizers import LinePlotVisualizer

################################################
################################################
# A structure to store DOTs stream's data.
################################################
################################################
class DotsStream(Stream):
  def __init__(self, 
               num_joints: int = 5,
               sampling_rate_hz: int = 20) -> None:
    super(DotsStream, self).__init__()
    self._device_name = 'dots-imu'
    self._num_joints = num_joints
    self._sampling_rate_hz = sampling_rate_hz
    self._data_notes_stream = {
      "dots-imu": {
        "acceleration-x": "AccX",
        "acceleration-y": "AccY",
        "acceleration-z": "AccZ",
        "gyroscope-x": "GyrX",
        "gyroscope-y": "GyrY",
        "gyroscope-z": "GyrZ",
      },
      "dots-time": {
        "device_timestamp_s": None
      }
    }

    # Add devices and streams to organize data from your sensor.
    #   Data is organized as devices and then streams.
    #   For example, a DOTs device may have streams for Gyro and Acceleration.
    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration-x',
                    data_type='float32',
                    sample_size=(self._num_joints),     # the size of data saved for each timestep
                    sampling_rate_hz=self._sampling_rate_hz, # the expected sampling rate for the stream
                    extra_data_info=None,
                    data_notes=self._data_notes_stream['dots-imu']['acceleration-x'])
    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration-y',
                    data_type='float32',
                    sample_size=(self._num_joints),     # the size of data saved for each timestep
                    sampling_rate_hz=self._sampling_rate_hz, # the expected sampling rate for the stream
                    extra_data_info=None,
                    data_notes=self._data_notes_stream['dots-imu']['acceleration-y'])
    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration-z',
                    data_type='float32',
                    sample_size=(self._num_joints),     # the size of data saved for each timestep
                    sampling_rate_hz=self._sampling_rate_hz, # the expected sampling rate for the stream
                    extra_data_info=None,
                    data_notes=self._data_notes_stream['dots-imu']['acceleration-z'])
    self.add_stream(device_name=self._device_name,
                    stream_name='gyroscope-x',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    extra_data_info=None, 
                    data_notes=self._data_notes_stream['dots-imu']['gyroscope-x'])
    self.add_stream(device_name=self._device_name,
                    stream_name='gyroscope-y',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    extra_data_info=None, 
                    data_notes=self._data_notes_stream['dots-imu']['gyroscope-y'])
    self.add_stream(device_name=self._device_name,
                    stream_name='gyroscope-z',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    extra_data_info=None, 
                    data_notes=self._data_notes_stream['dots-imu']['gyroscope-z'])
    self.add_stream(device_name=self._device_name,
                    stream_name='timestamp',
                    data_type='int64',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    extra_data_info=None,
                    data_notes=self._data_notes_stream['dots-time']['device_timestamp_s'])

  def append_data(self,
                  time_s: float, 
                  acceleration: ndarray, 
                  gyroscope: ndarray, 
                  timestamp: ndarray):
    self._append_data(self._device_name, 'acceleration-x', time_s, acceleration[:,0])
    self._append_data(self._device_name, 'acceleration-y', time_s, acceleration[:,1])
    self._append_data(self._device_name, 'acceleration-z', time_s, acceleration[:,2])
    self._append_data(self._device_name, 'gyroscope-x', time_s, gyroscope[:,0])
    self._append_data(self._device_name, 'gyroscope-y', time_s, gyroscope[:,1])
    self._append_data(self._device_name, 'gyroscope-z', time_s, gyroscope[:,2])
    self._append_data(self._device_name, 'timestamp', time_s, timestamp)


  ###########################
  ###### VISUALIZATION ######
  ###########################

  # Specify how the streams should be visualized.
  # Return a dict of the form options[device_name][stream_name] = stream_options
  #  Where stream_options is a dict with the following keys:
  #   'class': A subclass of Visualizer that should be used for the specified stream.
  #   Any other options that can be passed to the chosen class.
  def get_default_visualization_options(self):
    visualization_options = {}
    visualization_options[self._device_name] = {}

    # Use a line plot to visualize the acceleration.
    visualization_options[self._device_name]['acceleration-x'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    visualization_options[self._device_name]['acceleration-y'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    visualization_options[self._device_name]['acceleration-z'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    visualization_options[self._device_name]['gyroscope-x'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    visualization_options[self._device_name]['gyroscope-y'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    visualization_options[self._device_name]['gyroscope-z'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    
    # Don't visualize the other devices/streams.
    for (device_name, device_info) in self._streams_info.items():
      visualization_options.setdefault(device_name, {})
      for (stream_name, stream_info) in device_info.items():
        visualization_options[device_name].setdefault(stream_name, {'class': None})

    return visualization_options
