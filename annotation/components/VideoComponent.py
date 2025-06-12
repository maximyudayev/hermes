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

from typing import Any, Callable, Tuple
import numpy as np
from annotation.components.BaseComponent import BaseComponent
from utils.gui_utils import app
from dash import Output, Input, State, dcc, html
import dash_bootstrap_components as dbc
import plotly.express as px
import cv2
import h5py
import ffmpeg


class VideoComponent(BaseComponent):
  def __init__(self,
               video_path: str,
               hdf5_path: str,
               unique_id: str,
               legend_name: str,
               color_format: int,
               col_width: int = 6,
               is_eye_camera: bool = False,
               is_reference_camera: bool = False):
    super().__init__(unique_id=unique_id,
                     col_width=col_width)

    self._legend_name = legend_name
    self._unique_id = unique_id
    self._color_format = color_format
    self._video_path = video_path
    self._hdf5_path = hdf5_path
    self._is_eye_camera = is_eye_camera
    self._is_reference_camera = is_reference_camera
    
    # Get video properties
    self._width, self._height, self._fps, self._total_frames = self._get_video_properties()
    
    # Read HDF5 metadata for synchronization
    self._read_sync_metadata()
    
    # Initialize truncation points (will be set later)
    self._start_frame = 0
    self._end_frame = self._total_frames - 1
    self._truncated_frame_count = int(self._total_frames)
    
    # Lambda function for frame extraction
    self._video: Callable[[int], bytes] = lambda frame_id: self._get_frame_at_index(frame_id)

    # Create layout with timestamp display
    self._image = dcc.Graph(id="%s-video"%(self._unique_id), config={'displayModeBar': False})
    self._timestamp_display = html.Div(
        id="%s-timestamp"%(self._unique_id), 
        className="text-center small text-muted",
        style={'fontSize': '12px'}
    )
    
    self._layout = dbc.Col([
        self._image,
        self._timestamp_display
    ], width=self._col_width)
    
    self._activate_callbacks()

  def _get_frame_at_index(self, frame_index: int) -> bytes:
    """Get frame at specific index"""
    # Ensure we don't go beyond bounds
    if frame_index < 0:
        frame_index = 0
    elif frame_index >= self._total_frames:
        frame_index = self._total_frames - 1
    
    # Seek to the timestamp
    timestamp = frame_index / self._fps
    
    try:
        out, _ = (
            ffmpeg.input(self._video_path, ss=timestamp)
            .output('pipe:', vframes=1, format='rawvideo', pix_fmt='rgb24')
            .run(capture_stdout=True, quiet=True)
        )
        return out
    except Exception as e:
        print(f"Error getting frame {frame_index}: {e}")
        return np.zeros((self._height * self._width * 3), dtype=np.uint8).tobytes()

  def get_frame_for_timestamp(self, target_timestamp: float) -> int:
    """Find the frame index closest to a given timestamp"""
    if self._is_eye_camera and self._timestamps is not None:
        time_diffs = np.abs(self._timestamps - target_timestamp)
        closest_idx = np.argmin(time_diffs)
        return int(closest_idx)
    elif not self._is_eye_camera and self._toa_s is not None:
        time_diffs = np.abs(self._toa_s - target_timestamp)
        closest_idx = np.argmin(time_diffs)
        return int(closest_idx)
    return 0

  def get_timestamp_at_frame(self, frame_index: int) -> float:
    """Get the timestamp for a given frame"""
    if self._is_eye_camera and self._timestamps is not None and frame_index < len(self._timestamps):
        return float(self._timestamps[frame_index])
    elif not self._is_eye_camera and self._toa_s is not None and frame_index < len(self._toa_s):
        return float(self._toa_s[frame_index])
    return 0.0

  def _get_video_properties(self) -> Tuple[int, int, float, int]:
    """Get video width, height, fps, and total frames using cv2"""
    cap = cv2.VideoCapture(self._video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {self._video_path}")
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    return width, height, fps, total_frames

  def _read_sync_metadata(self):
    """Reads synchronization metadata from HDF5 file"""
    with h5py.File(self._hdf5_path, 'r') as hdf5:
      if self._is_eye_camera:
        path = f'/eye/eye-video-world/frame_timestamp'
        try:
          self._timestamps = hdf5[path][:]
        except Exception as e:
            print(f"Error reading timestamps for eye video from {path}: {e}")

      else:
        seq_path = f'/cameras/{self._unique_id}/frame_sequence_id'
        toa_path = f'/cameras/{self._unique_id}/toa_s'
        
        try:
          self._frame_sequence_ids = hdf5[seq_path][:]
          self._toa_s = hdf5[toa_path][:]
        except Exception as e:
            print(f"Error reading timestamps for cameras from {path}: {e}")

  def get_sync_info(self):
    """Return synchronization info for this component"""
    if self._is_eye_camera:
      return {
        'type': 'eye',
        'timestamps': self._timestamps # frame_timestamp
      }
    else:
      return {
        'type': 'camera',
        'unique_id': self._unique_id,
        'toa_s': self._toa_s,
        'frame_sequence_ids': self._frame_sequence_ids
      }

  def set_truncation_points(self, start_frame: int, end_frame: int):
    """Set truncation points for this video"""
    self._start_frame = int(max(0, start_frame))
    self._end_frame = int(min(self._total_frames - 1, end_frame))
    self._truncated_frame_count = self._end_frame - self._start_frame + 1
    print(f"{self._legend_name}: Start frame = {self._start_frame}")

  def get_truncated_frame_count(self):
    """Get number of frames after truncation"""
    return int(self._truncated_frame_count)

  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to corresponding file.
  def _activate_callbacks(self):
    @app.callback(
      [Output("%s-video"%(self._unique_id), component_property='figure'),
       Output("%s-timestamp"%(self._unique_id), component_property='children')],
      [Input("frame-id", component_property="value"),
       Input("sync-timestamp", component_property="data")],
      prevent_initial_call=True
    )
    def update_live_data(slider_position, sync_timestamp):
      try:
          # Determine which frame to show
          if self._is_reference_camera:
              # Reference camera: direct mapping from slider
              actual_frame = self._start_frame + slider_position
          else:
              # Other cameras and eye: find frame matching sync timestamp
              if sync_timestamp is not None:
                  actual_frame = self.get_frame_for_timestamp(sync_timestamp)
              else:
                  actual_frame = self._start_frame + slider_position
          
          # Get the frame
          img_bytes = self._video(actual_frame)
          img = np.frombuffer(img_bytes, np.uint8).reshape([self._height, self._width, 3])
          
          fig = px.imshow(img=img)
          fig.update_layout(
              title_text=self._legend_name,
              coloraxis_showscale=False
          )
          fig.update_xaxes(showticklabels=False)
          fig.update_yaxes(showticklabels=False)
          
          # Get timestamp for display
          timestamp = self.get_timestamp_at_frame(actual_frame)
          
          if self._is_eye_camera:
              timestamp_text = f"frame_timestamp: {timestamp} (frame: {actual_frame})"
          else:
              timestamp_text = f"toa_s: {timestamp} (frame: {actual_frame})"
          
          return fig, timestamp_text
      except Exception as e:
          print(f"Error loading frame: {e}")
          return {}, "Error"