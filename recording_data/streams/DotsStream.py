from collections import OrderedDict
from streams import Stream
from visualizers import SkeletonVisualizer, LinePlotVisualizer
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
               transmission_delay_period_s: int = 10,
               device_mapping: dict = None,
               **_) -> None:
    super().__init__()
    self._num_joints = num_joints
    self._sampling_rate_hz = sampling_rate_hz
    self._transmission_delay_period_s = transmission_delay_period_s

    # Invert device mapping to map device_id -> joint_name
    (joint_names, device_ids) = tuple(zip(*(device_mapping.items())))
    self._device_mapping: OrderedDict[str, str] = OrderedDict(zip(device_ids, joint_names))

    self._define_data_notes()

    self.add_stream(device_name='dots-imu',
                    stream_name='acceleration-x',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['dots-imu']['acceleration-x'])
    self.add_stream(device_name='dots-imu',
                    stream_name='acceleration-y',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['dots-imu']['acceleration-y'])
    self.add_stream(device_name='dots-imu',
                    stream_name='acceleration-z',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['dots-imu']['acceleration-z'])
    self.add_stream(device_name='dots-imu',
                    stream_name='orientation',
                    data_type='float32',
                    sample_size=(self._num_joints, 4),
                    sampling_rate_hz=self._sampling_rate_hz, 
                    data_notes=self._data_notes['dots-imu']['orientation'])
    self.add_stream(device_name='dots-imu',
                    stream_name='timestamp',
                    data_type='uint32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['dots-imu']['timestamp'])
    self.add_stream(device_name='dots-imu',
                    stream_name='counter',
                    data_type='uint16',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    is_measure_rate_hz=True,
                    data_notes=self._data_notes['dots-imu']['counter'])

    self.add_stream(device_name='dots-connection',
                    stream_name='transmission_delay',
                    data_type='float32',
                    sample_size=(1),
                    sampling_rate_hz=1.0/self._transmission_delay_period_s,
                    data_notes=self._data_notes['dots-connection']['transmission_delay'])


  def get_fps(self) -> dict[str, float]:
    return {'dots-imu': super()._get_fps('dots-imu')}


  def get_default_visualization_options(self) -> dict:
    visualization_options = super().get_default_visualization_options()

    # Use a line plot to visualize the acceleration and orientation.
    visualization_options['dots-imu']['acceleration-x'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    visualization_options['dots-imu']['acceleration-y'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,
       'plot_duration_s': 15,
       'downsample_factor': 1,
      }
    visualization_options['dots-imu']['acceleration-z'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,
       'plot_duration_s': 15,
       'downsample_factor': 1,
      }
    visualization_options['dots-imu']['orientation'] = \
      {'class': SkeletonVisualizer,
      }

    return visualization_options


  def _define_data_notes(self) -> None:
    self._data_notes = {}
    self._data_notes.setdefault('dots-imu', {})
    self._data_notes.setdefault('dots-connection', {})

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
    self._data_notes['dots-imu']['orientation'] = OrderedDict([
      ('Description', 'Quaternion rotation vector [W,X,Y,Z]'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-imu']['timestamp'] = OrderedDict([
      ('Description', 'Time of sampling of the packet at the device'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-imu']['counter'] = OrderedDict([
      ('Description', 'Packet sequence ID incrementing from 0 and wrapping at 65536, clearing on startup'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['dots-connection']['transmission_delay'] = OrderedDict([
      ('Description', 'Periodic transmission delay estimate of the connection link to the sensor'),
      ('Units', 'seconds'),
      ('Sample period', self._transmission_delay_period_s),
    ])
