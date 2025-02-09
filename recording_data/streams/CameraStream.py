from collections import OrderedDict
import numpy as np
from streams.Stream import Stream
from visualizers import VideoVisualizer


############################################
############################################
# A structure to store Camera stream's data.
############################################
############################################
class CameraStream(Stream):
  def __init__(self, 
               camera_mapping: dict[str, str],
               fps: float,
               resolution: tuple[int],
               color_format: int,
               **_) -> None:
    super().__init__()

    camera_names, camera_ids = tuple(zip(*(camera_mapping.items())))
    self._camera_mapping: OrderedDict[str, str] = OrderedDict(zip(camera_ids, camera_names))
    self._format = color_format

    self._define_data_notes()

    # Add a streams for each camera.
    for (camera_id, camera_name) in self._camera_mapping.items():
      self.add_stream(device_name=camera_name,
                      stream_name='frame',
                      is_video=True,
                      data_type='uint8',
                      sample_size=resolution,
                      sampling_rate_hz=fps,
                      is_measure_rate_hz=True,
                      data_notes=self._data_notes[camera_name]["frame"])
      self.add_stream(device_name=camera_name,
                      stream_name='timestamp',
                      is_video=False,
                      data_type='float64',
                      sample_size=(1),
                      sampling_rate_hz=fps,
                      data_notes=self._data_notes[camera_name]["timestamp"])
      self.add_stream(device_name=camera_name,
                      stream_name='frame_sequence',
                      is_video=False,
                      data_type='float64',
                      sample_size=(1),
                      sampling_rate_hz=fps,
                      data_notes=self._data_notes[camera_name]["frame_sequence"])


  def get_fps(self) -> dict[str, float]:
    return {camera_name: super(CameraStream, self)._get_fps(camera_name, 'frame') for camera_name in self._camera_mapping.values()}


  def _append_data(self,
                   device_id: str,
                   time_s: float, 
                   frame: np.ndarray, 
                   timestamp: np.uint64,
                   sequence_id: np.int64):
    self._append(self._camera_mapping[device_id], 'frame', time_s, frame)
    self._append(self._camera_mapping[device_id], 'timestamp', time_s, timestamp)
    self._append(self._camera_mapping[device_id], 'frame_sequence', time_s, sequence_id)


  def get_default_visualization_options(self):
    visualization_options = super().get_default_visualization_options()
    
    # Show frames from each camera as a video.
    for camera_id in self._camera_mapping.values():
      visualization_options[camera_id]['frame'] = {'class': VideoVisualizer,
                                                   'format': self._format}
    
    return visualization_options


  def _define_data_notes(self):
    self._data_notes = {}
    
    for (camera_id, camera_name) in self._camera_mapping.items():
      self._data_notes.setdefault(camera_name, {})
      self._data_notes[camera_name]["frame"] = OrderedDict([
        ('Serial Number', camera_id),
        (Stream.metadata_data_headings_key, camera_name),
        ('color_format', self._format)
      ])
      self._data_notes[camera_name]["timestamp"] = OrderedDict([
        ('Notes', 'Time of sampling of the frame w.r.t the camera onboard PTP clock')
      ])
      self._data_notes[camera_name]["frame_sequence"] = OrderedDict([
        ('Notes', ('Monotonically increasing index of the frame to track lost frames'))
      ])
