############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Created 2024-2025 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Maxim Yudayev [https://yudayev.com].
#
# ############

from collections import OrderedDict
from streams import Stream
from visualizers import VideoVisualizer
import dash_bootstrap_components as dbc


####################################################
####################################################
# A structure to store UVC smartglasses stream data.
####################################################
####################################################
class GlassesStream(Stream):
  def __init__(self, 
               camera_mapping: dict[str, str],
               pixel_format: str, # [jpeg]
               timesteps_before_solidified: int = 0,
               update_interval_ms: int = 100,
               **_) -> None:
    super().__init__()

    self._camera_mapping = camera_mapping
    self._pixel_format = pixel_format
    self._update_interval_ms = update_interval_ms
    self._timesteps_before_solidified = timesteps_before_solidified

    self._define_data_notes()

    # Add a streams for each camera.
    for camera_name, camera_spec in self._camera_mapping.items():
      self.add_stream(device_name=camera_name,
                      stream_name='frame',
                      data_type='uint8', 
                      sample_size=camera_spec['resolution'],
                      sampling_rate_hz=camera_spec['fps'], 
                      data_notes=self._data_notes[camera_name]['frame'],
                      is_measure_rate_hz=True,
                      is_video=True,
                      color_format=self._pixel_format, # bgr, yuv, jpeg
                      timesteps_before_solidified=self._timesteps_before_solidified)
      self.add_stream(device_name=camera_name,
                      stream_name='frame_timestamp',
                      data_type='float64',
                      sample_size=[1],
                      sampling_rate_hz=camera_spec['fps'],
                      data_notes=self._data_notes[camera_name]["frame_timestamp"])
      self.add_stream(device_name=camera_name,
                      stream_name='frame_index',
                      data_type='float64',
                      sample_size=[1],
                      sampling_rate_hz=camera_spec['fps'],
                      data_notes=self._data_notes[camera_name]["frame_index"])
      self.add_stream(device_name=camera_name,
                      stream_name='frame_sequence_id',
                      data_type='float64',
                      sample_size=[1],
                      sampling_rate_hz=camera_spec['fps'],
                      data_notes=self._data_notes[camera_name]["frame_sequence_id"])
      self.add_stream(device_name=camera_name,
                      stream_name='toa_s',
                      data_type='float64',
                      sample_size=[1],
                      sampling_rate_hz=camera_spec['fps'],
                      data_notes=self._data_notes[camera_name]['toa_s'])


  def get_fps(self) -> dict[str, float | None]:
    return {camera_name: super()._get_fps(camera_name, 'frame') for camera_name in self._camera_mapping.keys()}


  def build_visulizer(self) -> dbc.Row:
    camera_plots = [VideoVisualizer(stream=self,
                                    unique_id=camera_id,
                                    data_path={camera_id: 'frame'},
                                    legend_name=camera_name,
                                    update_interval_ms=self._update_interval_ms,
                                    color_format=self._streams_info[camera_id]['frame']['color_format']['cv2'],
                                    col_width=6)
                    for camera_id, camera_name in self._camera_mapping.items()]
    return dbc.Row([camera_plot.layout for camera_plot in camera_plots])


  def _define_data_notes(self):
    self._data_notes = {}
    
    for camera_name, camera_spec in self._camera_mapping.items():
      self._data_notes.setdefault(camera_name, {})
      self._data_notes[camera_name]["frame"] = OrderedDict([
        ('Serial Number', camera_name),
        (Stream.metadata_data_headings_key, camera_name),
      ])
      self._data_notes[camera_name]["frame_timestamp"] = OrderedDict([
        ('Notes', 'Time of sampling of the frame w.r.t the camera onboard PTP clock.'),
      ])
      self._data_notes[camera_name]["frame_index"] = OrderedDict([
        ('Notes', 'Monotonically increasing index of the frame to track lost frames, '
                  'starting from 0 when the recording started.'),
      ])
      self._data_notes[camera_name]["frame_sequence_id"] = OrderedDict([
        ('Notes', 'Monotonically increasing index of the frame to track lost frames.'),
      ])
      self._data_notes[camera_name]['toa_s'] = OrderedDict([
        ('Notes', 'Time of arrival of the packet w.r.t. system clock.'),
      ])
