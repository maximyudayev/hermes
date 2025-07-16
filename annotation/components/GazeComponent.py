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

import base64
from .VideoComponent import VideoComponent
import h5py
import numpy as np
from utils.gui_utils import app
from dash import Output, Input, State, Patch
import plotly.graph_objects as go
import plotly.express as px
import io
import base64
from PIL import Image


class GazeComponent(VideoComponent):
  def __init__(self,
               video_path: str,
               hdf5_path: str,
               unique_id: str,
               legend_name: str,
               col_width: int = 6,
               show_gaze_data: bool = True,
               is_highlight: bool = False):
    super().__init__(video_path=video_path,
                     hdf5_path=hdf5_path,
                     unique_id=unique_id,
                     legend_name=legend_name,
                     col_width=col_width,
                     is_reference_camera=False,
                     is_highlight=is_highlight)

    self._show_gaze_data = show_gaze_data

    # Read gaze data if needed
    if self._show_gaze_data:
      self._read_gaze_data()


  def _read_gaze_data(self):
    """Read eye gaze data from HDF5"""
    try:
      with h5py.File(self._hdf5_path, 'r') as hdf5:
        # Read gaze positions (normalized coordinates)
        gaze_position_path = '/eye/eye-gaze/position'
        gaze_timestamp_path = '/eye/eye-gaze/timestamp'

        if gaze_position_path in hdf5 and gaze_timestamp_path in hdf5:
          self._gaze_positions = hdf5[gaze_position_path][:] # Shape: (N, 2) for x, y
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
    if self._timestamps is not None:
      time_diffs = np.abs(self._timestamps - target_timestamp)
      closest_idx = np.argmin(time_diffs)
      # Apply offset for eye camera
      offset_idx = closest_idx + self._sync_offset
      # Ensure within bounds
      offset_idx = max(0, min(len(self._timestamps) - 1, offset_idx))
      return int(offset_idx)
    else:
      return 0


  def get_timestamp_at_frame(self, frame_index: int) -> float:
    """Get the timestamp for a given frame"""
    if self._timestamps is not None and frame_index < len(self._timestamps):
      return self._timestamps[frame_index].item()
    else:
      return 0.0


  def _read_sync_metadata(self):
    """Reads synchronization metadata from HDF5 file"""
    with h5py.File(self._hdf5_path, 'r') as hdf5:
      path = f'/eye/eye-video-world/frame_timestamp'
      try:
        self._timestamps = hdf5[path][:]
      except Exception as e:
        print(f"Error reading timestamps for eye video from {path}: {e}")


  def get_sync_info(self):
    """Return synchronization info for this component"""
    return {
      'type': 'eye',
      'timestamps': self._timestamps # frame_timestamp
    }


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to corresponding file.
  def _activate_callbacks(self):
    @app.callback(
      Output("%s-video"%(self._unique_id), "figure"),
      Output("%s-timestamp"%(self._unique_id), "children"),
      Input("frame-id", "data"),
      Input("sync-timestamp", "data"),
      Input("offset-update-trigger", "data"),
      State("%s-video"%(self._unique_id), "figure"),
      # prevent_initial_call=False
    )
    def update_vision(slider_position, sync_timestamp, offset_trigger, old_figure):
      try:
        # Determine which frame to show
        if self._is_reference_camera:
          # Reference camera: direct mapping from slider
          frame_id = self._start_frame + slider_position
        else:
          # Other cameras and eye: find frame matching sync timestamp
          if sync_timestamp is not None:
            frame_id = self.get_frame_for_timestamp(sync_timestamp)
          else:
            frame_id = self._start_frame + slider_position

        img = self._get_frame(frame_id)
        fig = px.imshow(img=np.frombuffer(img, np.uint8).reshape(self._height_scaled, self._width_scaled, 3), binary_string=True)

        # Convert bytes to PIL Image
        # pil_image = Image.frombytes('RGB', size=(self._width, self._height), data=img)
        
        # Save to bytes buffer
        # buffer = io.BytesIO()
        # pil_image.save(buffer, format='PNG')
        # buffer.seek(0)
        
        # Encode to base64
        # img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        # patched_figure = Patch()
        # old_figure["data"][0]["source"] = f"data:image/png;base64,{img_base64}"

        # Add gaze marker if enabled and available
        # if self._show_gaze_data:
        if self._show_gaze_data:
          gaze_pos = self._get_gaze_for_frame(frame_id)
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
        fig.update_layout(
          title_text=self._legend_name,
          title_font_size=11,
          coloraxis_showscale=False,
          margin=dict(l=0, r=0, t=20, b=0),
          autosize=True,
          height=None
        )

        fig.update_xaxes(showticklabels=False, showgrid=False)
        fig.update_yaxes(showticklabels=False, showgrid=False)

        # Get timestamp for display
        timestamp = self.get_timestamp_at_frame(frame_id)

        timestamp_text = f"frame_timestamp: {timestamp:.5f} (frame: {frame_id})"
        if self._sync_offset != 0:
          timestamp_text += f" [offset: {self._sync_offset:+d}]"

        return fig, timestamp_text
      except Exception as e:
        print(f"Error loading frame for {self._unique_id}: {e}")
        return {}, "Error"
