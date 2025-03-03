from collections import OrderedDict
from streams import Stream
from visualizers import VideoVisualizer
import dash_bootstrap_components as dbc


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
               timesteps_before_solidified: int = 0,
               update_interval_ms: int = 100,
               **_) -> None:
    super().__init__()

    camera_names, camera_ids = tuple(zip(*(camera_mapping.items())))
    self._camera_mapping: OrderedDict[str, str] = OrderedDict(zip(camera_ids, camera_names))
    self._color_format = color_format
    self._update_interval_ms = update_interval_ms
    self._timesteps_before_solidified = timesteps_before_solidified

    self._define_data_notes()

    # Add a streams for each camera.
    for camera_id, camera_name in self._camera_mapping.items():
      self.add_stream(device_name=camera_id,
                      stream_name='frame',
                      is_video=True,
                      data_type='uint8',
                      sample_size=resolution,
                      sampling_rate_hz=fps,
                      is_measure_rate_hz=True,
                      data_notes=self._data_notes[camera_id]["frame"],
                      timesteps_before_solidified=self._timesteps_before_solidified)
      self.add_stream(device_name=camera_id,
                      stream_name='timestamp',
                      is_video=False,
                      data_type='float64',
                      sample_size=(1),
                      sampling_rate_hz=fps,
                      data_notes=self._data_notes[camera_id]["timestamp"])
      self.add_stream(device_name=camera_id,
                      stream_name='frame_sequence',
                      is_video=False,
                      data_type='float64',
                      sample_size=(1),
                      sampling_rate_hz=fps,
                      data_notes=self._data_notes[camera_id]["frame_sequence"])


  def get_fps(self) -> dict[str, float]:
    return {camera_name: super()._get_fps(camera_name, 'frame') for camera_name in self._camera_mapping.values()}


  def build_visulizer(self) -> dbc.Row:
    camera_plots = [VideoVisualizer(stream=self,
                                    device_name=camera_id,
                                    data_path='frame',
                                    legend_name=camera_name,
                                    update_interval_ms=self._update_interval_ms,
                                    color_format=self._color_format,
                                    col_width=6)
                    for camera_id, camera_name in self._camera_mapping.items()]
    return dbc.Row([camera_plot.layout for camera_plot in camera_plots])


  def _define_data_notes(self):
    self._data_notes = {}
    
    for camera_id, camera_name in self._camera_mapping.items():
      self._data_notes.setdefault(camera_id, {})
      self._data_notes[camera_id]["frame"] = OrderedDict([
        ('Serial Number', camera_id),
        (Stream.metadata_data_headings_key, camera_name),
        ('color_format', self._color_format),
      ])
      self._data_notes[camera_id]["timestamp"] = OrderedDict([
        ('Notes', 'Time of sampling of the frame w.r.t the camera onboard PTP clock'),
      ])
      self._data_notes[camera_id]["frame_sequence"] = OrderedDict([
        ('Notes', ('Monotonically increasing index of the frame to track lost frames')),
      ])
