from streams.Stream import Stream

################################################
################################################
# A structure to store DOTs stream's data.
################################################
################################################
class AwindaIMUStream(Stream):
  def __init__(self, 
               sampling_rate_hz: int = 100,
               device_name_list: list[str] = None) -> None:
    super(AwindaIMUStream, self).__init__()
    self._device_name = 'Awinda-IMU'
    self._sampling_rate_hz = sampling_rate_hz
    self._data_notes_stream = {
      "awinda-imu": {
        "acceleration-x": "AccX",
        "acceleration-y": "AccY",
        "acceleration-z": "AccZ",
        "gyroscope-x": "GyrX",
        "gyroscope-y": "GyrY",
        "gyroscope-z": "GyrZ",
      },
      "awinda-counter": {
        "counter": None
      }
    }

    # Add devices and streams to organize data from your sensor.
    #   Data is organized as devices and then streams.
    #   For example, a DOTs device may have streams for Gyro and Acceleration.
    for name in device_name_list:
        self.add_stream(device_name=name,
                        stream_name='acceleration-x',
                        data_type='float32',
                        sample_size=(1),     # the size of data saved for each timestep
                        sampling_rate_hz=sampling_rate_hz, # the expected sampling rate for the stream
                        extra_data_info=None,
                        data_notes=self._data_notes_stream['awinda-imu']['acceleration-x'])
        self.add_stream(device_name=name,
                        stream_name='acceleration-y',
                        data_type='float32',
                        sample_size=(1),     # the size of data saved for each timestep
                        sampling_rate_hz=sampling_rate_hz, # the expected sampling rate for the stream
                        extra_data_info=None,
                        data_notes=self._data_notes_stream['awinda-imu']['acceleration-y'])
        self.add_stream(device_name=name,
                        stream_name='acceleration-z',
                        data_type='float32',
                        sample_size=(1),     # the size of data saved for each timestep
                        sampling_rate_hz=sampling_rate_hz, # the expected sampling rate for the stream
                        extra_data_info=None,
                        data_notes=self._data_notes_stream['awinda-imu']['acceleration-z'])
        self.add_stream(device_name=name,
                        stream_name='gyroscope-x',
                        data_type='float32',
                        sample_size=(1),
                        sampling_rate_hz=sampling_rate_hz,
                        extra_data_info=None, 
                        data_notes=self._data_notes_stream['awinda-imu']['gyroscope-x'])
        self.add_stream(device_name=name,
                        stream_name='gyroscope-y',
                        data_type='float32',
                        sample_size=(1),
                        sampling_rate_hz=sampling_rate_hz,
                        extra_data_info=None, 
                        data_notes=self._data_notes_stream['awinda-imu']['gyroscope-y'])
        self.add_stream(device_name=name,
                        stream_name='gyroscope-z',
                        data_type='float32',
                        sample_size=(1),
                        sampling_rate_hz=sampling_rate_hz,
                        extra_data_info=None, 
                        data_notes=self._data_notes_stream['awinda-imu']['gyroscope-z'])
        self.add_stream(device_name=name,
                        stream_name='counter',
                        data_type='uint16',
                        sample_size=(1),
                        sampling_rate_hz=sampling_rate_hz,
                        extra_data_info=None,
                        data_notes=self._data_notes_stream['awinda-counter']['counter'])

  def append_data(self,
                  name,
                  time_s: float, 
                  packet,):
            
        #print("data")
        self._append_data(name, 'acceleration-x', time_s, packet.acceleration[0])
        self._append_data(name, 'acceleration-y',    time_s, packet.acceleration[1])
        self._append_data(name, 'acceleration-z',   time_s, packet.acceleration[2])

        self._append_data(name, 'gyroscope-x', time_s, packet.rotation[0])
        self._append_data(name, 'gyroscope-y',    time_s, packet.rotation[1])
        self._append_data(name, 'gyroscope-z',   time_s, packet.rotation[2])

        self._append_data(name, 'counter',   time_s, packet.counter)

  def get_default_visualization_options(self):
       return super().get_default_visualization_options()