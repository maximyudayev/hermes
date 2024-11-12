from numpy import ndarray
from streams.Stream import Stream
from visualizers import VideoVisualizer

################################################
################################################
# A structure to store DOTs stream's data.
################################################
################################################
class CameraStream(Stream):
  def __init__(self, 
               cameras_to_stream: dict,
               fps: float) -> None:
    super(CameraStream, self).__init__()

    self._data_notes_stream = {
      "frame": "Frames are in BGR format",
      "sequence_id": "Frame index",
      "frame_timestamp": None
    }

    # Add devices and streams to organize data from your sensor.
    #   Data is organized as devices and then streams.
    #   For example, a DOTs device may have streams for Gyro and Acceleration.
    for (camera_name, device_index) in cameras_to_stream.items():
      self.add_stream(device_name=camera_name,
                      stream_name='frame',
                      is_video=True,
                      data_type='uint8',
                      sample_size=frame.shape, # the size of data saved for each timestep; here, we expect a 2-element vector per timestep
                      sampling_rate_hz=fps,    # the expected sampling rate for the stream
                      extra_data_info=None,    # can add extra information beyond the data and the timestamp if needed (probably not needed, but see MyoStreamer for an example if desired)
                      # Notes can add metadata about the stream,
                      #  such as an overall description, data units, how to interpret the data, etc.
                      # The SensorStreamer.metadata_data_headings_key is special, and is used to
                      #  describe the headings for each entry in a timestep's data.
                      #  For example - if the data was saved in a spreadsheet with a row per timestep, what should the column headings be.
                      data_notes=self._data_notes_stream["frame"])
      # Add a stream for the frames.
      self.add_stream(device_name=camera_name,
                      stream_name='frame_timestamp',
                      is_video=False,
                      data_type='float64',
                      sample_size=[1],         # the size of data saved for each timestep; here, we expect a 2-element vector per timestep
                      sampling_rate_hz=fps,    # the expected sampling rate for the stream
                      extra_data_info=None,    # can add extra information beyond the data and the timestamp if needed (probably not needed, but see MyoStreamer for an example if desired)
                      # Notes can add metadata about the stream,
                      #  such as an overall description, data units, how to interpret the data, etc.
                      # The SensorStreamer.metadata_data_headings_key is special, and is used to
                      #  describe the headings for each entry in a timestep's data.
                      #  For example - if the data was saved in a spreadsheet with a row per timestep, what should the column headings be.
                      data_notes=self._data_notes_stream["frame_timestamp"])

  def append_data(self,
                  time_s: float, 
                  frame: ndarray, 
                  timestamp: ndarray):
    self._append_data(camera_name, 'frame', time_s, frame)
    self._append_data(camera_name, 'frame_timestamp', time_s, timestamp)


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
    processed_options = {}
    for (device_name, device_info) in self._streams_info.items():
      processed_options.setdefault(device_name, {})
      for (stream_name, stream_info) in device_info.items():
        processed_options[device_name].setdefault(stream_name, {'class': None})
    
    # Show frames from each camera as a video.
    for camera_name in self._cameras_to_stream:
      processed_options[camera_name]['frame'] = {'class': VideoVisualizer}
    
    # Override the above defaults with any provided options.
    if isinstance(visualization_options, dict):
      for (device_name, device_info) in self._streams_info.items():
        if device_name in visualization_options:
          device_options = visualization_options[device_name]
          # Apply the provided options for this device to all of its streams.
          for (stream_name, stream_info) in device_info.items():
            for (k, v) in device_options.items():
              processed_options[device_name][stream_name][k] = v
    
    return processed_options
