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
from typing import Any
from streams import Stream
from visualizers import VideoVisualizer
import dash_bootstrap_components as dbc
import cv2


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
               color_format: str,
               timesteps_before_solidified: int = 0,
               update_interval_ms: int = 100,
               **_) -> None:
    super().__init__()

    camera_names, camera_ids = tuple(zip(*(camera_mapping.items())))
    self._camera_mapping: OrderedDict[str, str] = OrderedDict(zip(camera_ids, camera_names))
    self._color_format = getattr(cv2, color_format)
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
                                    unique_id=camera_id,
                                    data_path={camera_id: 'frame'},
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


  # Override the thread-locking wrapper methods to safely access the data (we are responsible)
  #   between cameras independently, without locking other threads.
  # !!! 'data' must contain only 1 device's data. Can do this, because these streams are async,
  #   may want to align them like DOTs if using a multi-angle (3D) recognition, pose estimation, etc.
  # NOTE: simpler solution to current code, cleaner than alternatives,
  #   may be less performant than individual Logger per camera device.
  def append_data(self, time_s: float, data: dict) -> None:
    self._append_data(time_s=time_s, data=data)


  def get_data(self, 
               device_name: str, 
               stream_name: str,
               starting_index: int = None, 
               ending_index: int = None,
               starting_time_s: float = None, 
               ending_time_s: float = None,
               return_deepcopy: bool = True) -> dict[str, list[Any]]:
    return self._get_data(device_name=device_name,
                          stream_name=stream_name,
                          starting_index=starting_index,
                          ending_index=ending_index,
                          starting_time_s=starting_time_s,
                          ending_time_s=ending_time_s,
                          return_deepcopy=return_deepcopy)
