from collections import OrderedDict
from streams.Stream import Stream
from visualizers import LinePlotVisualizer, SkeletonVisualizer


##################################################
##################################################
# A structure to store Awinda MTws' stream's data.
##################################################
##################################################
class AwindaStream(Stream):
  def __init__(self, 
               device_mapping: dict[str, str],
               num_joints: int = 7,
               sampling_rate_hz: int = 100,
               transmission_delay_period_s: int = 10,
               **_) -> None:
    super().__init__()
    
    self._num_joints = num_joints
    self._sampling_rate_hz = sampling_rate_hz
    self._transmission_delay_period_s = transmission_delay_period_s
    
    # Invert device mapping to map device_id -> joint_name
    joint_names, device_ids = tuple(zip(*(device_mapping.items())))
    self._device_mapping: OrderedDict[str, str] = OrderedDict(zip(device_ids, joint_names))

    self._define_data_notes()

    # When using onLiveDataAvailable, every immediately available packet from each MTw is pushed in its own corresponding Stream.
    # When using onAllLiveDataAvailable, packets are packaged all at once (potentially for multiple timesteps)
    #   with interpolation of data for steps where some of sensors missed a measurement.
    # Choose the desired behavior for the system later. (currently onAllLiveDataAvailable).
    self.add_stream(device_name='awinda-imu',
                    stream_name='acceleration-x',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['awinda-imu']['acceleration-x'])
    self.add_stream(device_name='awinda-imu',
                    stream_name='acceleration-y',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['awinda-imu']['acceleration-y'])
    self.add_stream(device_name='awinda-imu',
                    stream_name='acceleration-z',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['awinda-imu']['acceleration-z'])
    self.add_stream(device_name='awinda-imu',
                    stream_name='orientation',
                    data_type='float32',
                    sample_size=(self._num_joints, 4),
                    sampling_rate_hz=self._sampling_rate_hz, 
                    data_notes=self._data_notes['awinda-imu']['orientation'])
    self.add_stream(device_name='awinda-imu',
                    stream_name='timestamp',
                    data_type='uint32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    data_notes=self._data_notes['awinda-imu']['timestamp'])
    self.add_stream(device_name='awinda-imu',
                    stream_name='counter',
                    data_type='uint16',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=self._sampling_rate_hz,
                    is_measure_rate_hz=True, # only 1 stream per device needs to be marked `True` if all streams get new data at a time
                    data_notes=self._data_notes['awinda-imu']['counter'])
    
    self.add_stream(device_name='awinda-connection',
                    stream_name='transmission_delay',
                    data_type='float32',
                    sample_size=(1),
                    sampling_rate_hz=1.0/self._transmission_delay_period_s,
                    data_notes=self._data_notes['awinda-connection']['transmission_delay'])


  def get_fps(self) -> dict[str, float]:
    return {'awinda-imu': super()._get_fps('awinda-imu', 'counter')}


  def get_default_visualization_options(self) -> dict:
    visualization_options = super().get_default_visualization_options()

    # Use a line plot to visualize the acceleration.
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
    self._data_notes.setdefault('awinda-imu', {})
    self._data_notes.setdefault('awinda-connection', {})

    self._data_notes['awinda-imu']['acceleration-x'] = OrderedDict([
      ('Description', 'Acceleration in the X direction'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['awinda-imu']['acceleration-y'] = OrderedDict([
      ('Description', 'Acceleration in the Y direction'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['awinda-imu']['acceleration-z'] = OrderedDict([
      ('Description', 'Acceleration in the Z direction'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['awinda-imu']['orientation'] = OrderedDict([
      ('Description', 'Quaternion rotation vector [W,X,Y,Z]'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['awinda-imu']['counter'] = OrderedDict([
      ('Description', 'Index of the sampled packet per device, starting from 0 on turn-on and wrapping around after 65535.'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['awinda-imu']['timestamp'] = OrderedDict([
      ('Description', 'Time of sampling of the packet at the device. \
                      If one of the device measurement is missed for timestep `i`, \
                      data will be interpolated on the next timestep.Acceleration in the X direction'),
      (Stream.metadata_data_headings_key, list(self._device_mapping.values())),
    ])
    self._data_notes['awinda-connection']['transmission_delay'] = OrderedDict([
      ('Description', 'Periodic transmission delay estimate of the connection link to the sensor'),
      ('Units', 'seconds'),
      ('Sample period', self._transmission_delay_period_s),
    ])
