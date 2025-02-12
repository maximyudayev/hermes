from collections import OrderedDict
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
               transmission_delay_period_s: int = 10,
               **_) -> None:
    super().__init__()
    self._sampling_rate_hz = sampling_rate_hz
    self._transmission_delay_period_s = transmission_delay_period_s

    self._define_data_notes()

    self.add_stream(device_name='insoles-data',
                    stream_name='timestamp',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=self._sampling_rate_hz,
                    is_measure_rate_hz=True)
    self.add_stream(device_name='insoles-data',
                    stream_name='foot_pressure_left',
                    data_type='float32',
                    sample_size=[16],
                    sampling_rate_hz=self._sampling_rate_hz)
    self.add_stream(device_name='insoles-data',
                    stream_name='foot_pressure_right',
                    data_type='float32',
                    sample_size=[16],
                    sampling_rate_hz=self._sampling_rate_hz)
    self.add_stream(device_name='insoles-data',
                    stream_name='acc_left',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=self._sampling_rate_hz)
    self.add_stream(device_name='insoles-data',
                    stream_name='acc_right',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=self._sampling_rate_hz)
    self.add_stream(device_name='insoles-data',
                    stream_name='gyro_left',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=self._sampling_rate_hz)
    self.add_stream(device_name='insoles-data',
                    stream_name='gyro_right',
                    data_type='float32',
                    sample_size=[3],
                    sampling_rate_hz=self._sampling_rate_hz)
    self.add_stream(device_name='insoles-data',
                    stream_name='total_force_left',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=self._sampling_rate_hz)
    self.add_stream(device_name='insoles-data',
                    stream_name='total_force_right',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=self._sampling_rate_hz)
    self.add_stream(device_name='insoles-data',
                    stream_name='center_of_pressure_left',
                    data_type='float32',
                    sample_size=[2],
                    sampling_rate_hz=self._sampling_rate_hz)
    self.add_stream(device_name='insoles-data',
                    stream_name='center_of_pressure_right',
                    data_type='float32',
                    sample_size=[2],
                    sampling_rate_hz=self._sampling_rate_hz)
    
    self.add_stream(device_name='insoles-connection',
                    stream_name='transmission_delay',
                    data_type='float32',
                    sample_size=(1),
                    sampling_rate_hz=1.0/self._transmission_delay_period_s,
                    data_notes=self._data_notes['insoles-connection']['transmission_delay'])


  def get_fps(self) -> dict[str, float]:
    return {'insoles-data': super()._get_fps('insoles-data', 'timestamp')}


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


  def _define_data_notes(self) -> None:
    self._data_notes = {}
    self._data_notes.setdefault('insoles-data', {})
    self._data_notes.setdefault('insoles-connection', {})

    self._data_notes['insoles-data']['timestamp'] = OrderedDict([
      ('Description', 'Device time of sampling of the insole data'),
    ])
    self._data_notes['insoles-data']['foot_pressure_left'] = OrderedDict([
      ('Description', 'Pressure across the 16 strain gauge grid across the left insole'),
    ])
    self._data_notes['insoles-data']['foot_pressure_right'] = OrderedDict([
      ('Description', 'Pressure across the 16 strain gauge grid across the right insole'),
    ])
    self._data_notes['insoles-data']['acc_left'] = OrderedDict([
      ('Description', 'Acceleration in the X direction'),
      (Stream.metadata_data_headings_key, ['x','y','z']),
    ])
    self._data_notes['insoles-data']['acc_right'] = OrderedDict([
      ('Description', 'Acceleration in the X direction'),
      (Stream.metadata_data_headings_key, ['x','y','z']),
    ])
    self._data_notes['insoles-data']['gyro_left'] = OrderedDict([
      ('Description', 'Acceleration in the X direction'),
      (Stream.metadata_data_headings_key, ['x','y','z']),
    ])
    self._data_notes['insoles-data']['gyro_right'] = OrderedDict([
      ('Description', 'Acceleration in the X direction'),
      (Stream.metadata_data_headings_key, ['x','y','z']),
    ])
    self._data_notes['insoles-data']['total_force_left'] = OrderedDict([
      ('Description', 'Total force on the left insole'),
    ])
    self._data_notes['insoles-data']['total_force_right'] = OrderedDict([
      ('Description', 'Total force on the right insole'),
    ])
    self._data_notes['insoles-data']['center_of_pressure_left'] = OrderedDict([
      ('Description', 'Point of pressure concentration on the left insole'),
      (Stream.metadata_data_headings_key, ['x','y']),
    ])
    self._data_notes['insoles-data']['center_of_pressure_right'] = OrderedDict([
      ('Description', 'Point of pressure concentration on the right insole'),
      (Stream.metadata_data_headings_key, ['x','y']),
    ])
    self._data_notes['insoles-connection']['transmission_delay'] = OrderedDict([
      ('Description', 'Periodic transmission delay estimate of the connection link to the sensor'),
      ('Units', 'seconds'),
      ('Sample period', self._transmission_delay_period_s),
    ])
