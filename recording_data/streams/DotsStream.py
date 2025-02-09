from collections import OrderedDict
from numpy import ndarray
from streams import Stream
from visualizers import LinePlotVisualizer
from streams.Stream import Stream


##########################################
##########################################
# A structure to store DOTs stream's data.
##########################################
##########################################
class DotsStream(Stream):
  def __init__(self, 
               num_joints: int = 5,
               sampling_rate_hz: int = 20,
               device_mapping: dict = None,
               **_) -> None:
    super().__init__()
    self._device_name = 'dots-imu'
    self._num_joints = num_joints
    self._sampling_rate_hz = sampling_rate_hz

    # Invert device mapping to map device_id -> joint_name
    (joint_names, device_ids) = tuple(zip(*(device_mapping.items())))
    self._device_mapping: OrderedDict[str, str] = OrderedDict(zip(device_ids, joint_names))

    self._define_data_notes()

    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration-x',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['dots-imu']['acceleration-x'])
    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration-y',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['dots-imu']['acceleration-y'])
    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration-z',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['dots-imu']['acceleration-z'])
    self.add_stream(device_name=self._device_name,
                    stream_name='orientation-w',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz, 
                    data_notes=self._data_notes['dots-imu']['orientation-w'])
    self.add_stream(device_name=self._device_name,
                    stream_name='orientation-x',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz, 
                    data_notes=self._data_notes['dots-imu']['orientation-x'])
    self.add_stream(device_name=self._device_name,
                    stream_name='orientation-y',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz, 
                    data_notes=self._data_notes['dots-imu']['orientation-y'])
    self.add_stream(device_name=self._device_name,
                    stream_name='orientation-z',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz, 
                    data_notes=self._data_notes['dots-imu']['orientation-z'])
    self.add_stream(device_name=self._device_name,
                    stream_name='timestamp',
                    data_type='uint32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['dots-time']['timestamp'])
    self.add_stream(device_name=self._device_name,
                    stream_name='counter',
                    data_type='uint16',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    is_measure_rate_hz=True,
                    data_notes=self._data_notes['dots-time']['counter'])


  def get_fps(self) -> dict[str, float]:
    return {self._device_name: super()._get_fps(self._device_name, 'counter')}


  def _append_data(self,
                   time_s: float, 
                   acceleration: ndarray, 
                   orientation: ndarray, 
                   timestamp: ndarray,
                   counter: ndarray) -> None:
    self._append(self._device_name, 'acceleration-x', time_s, acceleration[:,0])
    self._append(self._device_name, 'acceleration-y', time_s, acceleration[:,1])
    self._append(self._device_name, 'acceleration-z', time_s, acceleration[:,2])
    self._append(self._device_name, 'orientation-w', time_s, orientation[:,0])
    self._append(self._device_name, 'orientation-x', time_s, orientation[:,1])
    self._append(self._device_name, 'orientation-y', time_s, orientation[:,2])
    self._append(self._device_name, 'orientation-z', time_s, orientation[:,3])
    self._append(self._device_name, 'timestamp', time_s, timestamp)
    self._append(self._device_name, 'counter', time_s, counter)


  def get_default_visualization_options(self) -> dict:
    visualization_options = super().get_default_visualization_options()

    # Use a line plot to visualize the acceleration and orientation.
    visualization_options[self._device_name]['acceleration-x'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    visualization_options[self._device_name]['acceleration-y'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,
       'plot_duration_s': 15,
       'downsample_factor': 1,
      }
    visualization_options[self._device_name]['acceleration-z'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,
       'plot_duration_s': 15,
       'downsample_factor': 1,
      }
    # TODO: update orientation visualization to represent quaternion data (transform to Euler or plot as skeleton).
    visualization_options[self._device_name]['orientation-w'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,
       'plot_duration_s': 15,
       'downsample_factor': 1,
      }
    visualization_options[self._device_name]['orientation-x'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,
       'plot_duration_s': 15,
       'downsample_factor': 1,
      }
    visualization_options[self._device_name]['orientation-y'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,
       'plot_duration_s': 15,
       'downsample_factor': 1,
      }
    visualization_options[self._device_name]['orientation-z'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,
       'plot_duration_s': 15,
       'downsample_factor': 1,
      }

    return visualization_options


  def _define_data_notes(self) -> None:
    self._data_notes = {}
    self._data_notes.setdefault('dots-imu', {})
    self._data_notes.setdefault('dots-time', {})

    self._data_notes['dots-imu']['acceleration-x'] = OrderedDict([
      ('Description', 'Acceleration in the X direction'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-imu']['acceleration-y'] = OrderedDict([
      ('Description', 'Acceleration in the Y direction'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-imu']['acceleration-z'] = OrderedDict([
      ('Description', 'Acceleration in the Z direction'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    # TODO: update orientation description to quaternion components.
    self._data_notes['dots-imu']['orientation-w'] = OrderedDict([
      ('Description', 'Orientation in the Roll direction (around X axis)'),
      ('Units', 'degrees'),
      ('Range', '[-180, 180]'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-imu']['orientation-x'] = OrderedDict([
      ('Description', 'Orientation in the Roll direction (around X axis)'),
      ('Units', 'degrees'),
      ('Range', '[-180, 180]'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-imu']['orientation-y'] = OrderedDict([
      ('Description', 'Orientation in the Pitch direction (around Y axis)'),
      ('Units', 'degrees'),
      ('Range', '[-180, 180]'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-imu']['orientation-z'] = OrderedDict([
      ('Description', 'Orientation in the Yaw direction (around Z axis)'),
      ('Units', 'degrees'),
      ('Range', '[-180, 180]'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-time']['timestamp'] = OrderedDict([
      ('Description', 'Time of sampling of the packet at the device'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-time']['counter'] = OrderedDict([
      ('Description', 'Packet sequence ID incrementing from 0 and wrapping at 65536, clearing on startup'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
