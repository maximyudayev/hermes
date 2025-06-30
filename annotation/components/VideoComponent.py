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
               is_reference_camera: bool = False,
               is_highlight: bool = False,
               show_gaze_data: bool = False):
    super().__init__(unique_id=unique_id,
                     col_width=col_width)

    self._legend_name = legend_name
    self._color_format = color_format
    self._video_path = video_path
    self._hdf5_path = hdf5_path
    self._is_eye_camera = is_eye_camera
    self._is_reference_camera = is_reference_camera
    self._is_highlight = is_highlight
    self._show_gaze_data = show_gaze_data and is_eye_camera
    
    # Get video properties
    self._width, self._height, self._fps, self._total_frames = self._get_video_properties()
    
    # Read HDF5 metadata for synchronization
    self._read_sync_metadata()
    
    # Read gaze data if needed
    if self._show_gaze_data:
        self._read_gaze_data()
    
    # Initialize truncation points
    self._start_frame = 0
    self._end_frame = self._total_frames - 1
    self._truncated_frame_count = int(self._total_frames)
    
    # Lambda function for frame extraction
    self._video: Callable[[int], bytes] = lambda frame_id: self._get_frame_at_index(frame_id)

    # Create layout with timestamp display
    self._image = dcc.Graph(
        id="%s-video"%(self._unique_id), 
        config={'displayModeBar': False, 'responsive': True},
        clear_on_unhover=True,
        style={'height': '100%', 'width': '100%', 'cursor': 'pointer' if not is_highlight else 'default'}
    )
    self._timestamp_display = html.Div(
        id="%s-timestamp"%(self._unique_id), 
        className="text-center small text-muted",
        style={'fontSize': '11px', 'height': '20px', 'lineHeight': '20px'}
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
    
    # Seek to the timestamp because it is much faster than using frame index
    # TODO: IS THE FPS CONSTANT? If not, what is the solution? Convert toa/timestamps to video timestamps? 
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

  def _read_gaze_data(self):
    """Read eye gaze data from HDF5"""
    try:
        with h5py.File(self._hdf5_path, 'r') as hdf5:
            # Read gaze positions (normalized coordinates)
            gaze_position_path = '/eye/eye-gaze/position'
            gaze_timestamp_path = '/eye/eye-gaze/timestamp'
            
            if gaze_position_path in hdf5 and gaze_timestamp_path in hdf5:
                self._gaze_positions = hdf5[gaze_position_path][:]  # Shape: (N, 2) for x, y
                self._gaze_timestamps = hdf5[gaze_timestamp_path][:]
                print(f"Loaded {len(self._gaze_positions)} gaze data points")
            else:
                print("Gaze data paths not found in HDF5")
                self._show_gaze_data = False
                self._gaze_positions = None
                self._gaze_timestamps = None
    except Exception as e:
        print(f"Error reading gaze data: {e}")
        self._show_gaze_data = False
        self._gaze_positions = None
        self._gaze_timestamps = None

  def _get_gaze_for_frame(self, frame_index: int):
    """Get gaze position for a specific frame"""
    if not self._show_gaze_data or self._gaze_positions is None:
        return None
    
    # Get frame timestamp
    if frame_index >= len(self._timestamps):
        return None
        
    frame_timestamp = self._timestamps[frame_index]
    
    # Find closest gaze timestamp
    time_diffs = np.abs(self._gaze_timestamps - frame_timestamp)
    closest_idx = np.argmin(time_diffs)
    
    # Get normalized gaze position
    gaze_x, gaze_y = self._gaze_positions[closest_idx]
    
    # Convert from normalized [0,1] with origin at bottom-left to pixel coordinates
    # Image coordinates have origin at top-left, so we flip Y?
    pixel_x = int(gaze_x * self._width)
    pixel_y = int((1.0 - gaze_y) * self._height)  # Flip Y coordinate
    
    return (pixel_x, pixel_y)

  def get_frame_for_timestamp(self, target_timestamp: float) -> int:
    """Find the frame index closest to a given timestamp with offset"""
    if self._is_eye_camera and self._timestamps is not None:
        time_diffs = np.abs(self._timestamps - target_timestamp)
        closest_idx = np.argmin(time_diffs)
        # Apply offset for eye camera
        offset_idx = closest_idx + self._sync_offset
        # Ensure within bounds
        offset_idx = max(0, min(len(self._timestamps) - 1, offset_idx))
        return int(offset_idx)
    elif not self._is_eye_camera and self._toa_s is not None:
        time_diffs = np.abs(self._toa_s - target_timestamp)
        closest_idx = np.argmin(time_diffs)
        # No offset for regular cameras
        return int(closest_idx)
    return 0

  def get_timestamp_at_frame(self, frame_index: int) -> float:
    """Get the timestamp for a given frame"""
    if self._is_eye_camera and self._timestamps is not None and frame_index < len(self._timestamps):
        return self._timestamps[frame_index].item()
    elif not self._is_eye_camera and self._toa_s is not None and frame_index < len(self._toa_s):
        return self._toa_s[frame_index].item()
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
        # Using frame_sequence_id or toa_s for synchronization, could not find a drastic difference between the two, sticking with toa_s for now
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
      [Output("%s-video"%(self._unique_id), "figure"),
       Output("%s-timestamp"%(self._unique_id), "children")],
      [Input("frame-id", "data"),
       Input("sync-timestamp", "data"),
       Input("offset-update-trigger", "data")],  # Add trigger for offset updates
      prevent_initial_call=False
    )
    def update_live_data(slider_position, sync_timestamp, offset_trigger):
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
            
            # Create figure
            fig = px.imshow(img=img)
            
            # Add gaze marker if enabled and available
            if self._show_gaze_data and self._is_eye_camera:
                gaze_pos = self._get_gaze_for_frame(actual_frame)
                if gaze_pos is not None:
                    gaze_x, gaze_y = gaze_pos
                    
                    fig.add_shape(
                        type="circle",
                        x0=gaze_x - 15, y0=gaze_y - 15,
                        x1=gaze_x + 15, y1=gaze_y + 15,
                        line=dict(color="red", width=3),
                        fillcolor="rgba(255, 0, 0, 0.3)"
                    )
                    
                    fig.add_shape(
                        type="line",
                        x0=gaze_x - 25, y0=gaze_y,
                        x1=gaze_x + 25, y1=gaze_y,
                        line=dict(color="red", width=2)
                    )
                    fig.add_shape(
                        type="line",
                        x0=gaze_x, y0=gaze_y - 25,
                        x1=gaze_x, y1=gaze_y + 25,
                        line=dict(color="red", width=2)
                    )
            
            # Update layout
            title = self._legend_name
            if self._show_gaze_data and self._is_eye_camera:
                title += " (with gaze)"
            
            fig.update_layout(
                title_text=title,
                title_font_size=11,
                coloraxis_showscale=False,
                margin=dict(l=0, r=0, t=20, b=0),
                autosize=True,
                height=None
            )
            
            fig.update_xaxes(showticklabels=False, showgrid=False)
            fig.update_yaxes(showticklabels=False, showgrid=False)
            
            # Get timestamp for display
            timestamp = self.get_timestamp_at_frame(actual_frame)
            
            if self._is_eye_camera:
                timestamp_text = f"frame_timestamp: {timestamp:.5f} (frame: {actual_frame})"
                if self._sync_offset != 0:
                    timestamp_text += f" [offset: {self._sync_offset:+d}]"
            else:
                timestamp_text = f"toa_s: {timestamp:.5f} (frame: {actual_frame})"
            
            return fig, timestamp_text
        except Exception as e:
            print(f"Error loading frame: {e}")
            return {}, "Error"