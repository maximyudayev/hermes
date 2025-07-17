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

from typing import Dict, Tuple
import numpy as np

from utils.datastructures.cache import FFmpegCache
from .BaseComponent import BaseComponent
from utils.gui_utils import app
from dash import Output, Input, dcc, html, Patch
import dash_bootstrap_components as dbc
import plotly.express as px
import base64
import h5py
import ffmpeg

# JPEG End of Image marker
EOI = b'\xFF\xD9'


class VideoComponent(BaseComponent):
  def __init__(self,
               video_path: str,
               hdf5_path: str,
               unique_id: str,
               legend_name: str,
               col_width: int = 6,
               is_reference_camera: bool = False,
               is_highlight: bool = False):
    super().__init__(unique_id=unique_id,
                     col_width=col_width)

    self._legend_name = legend_name
    self._video_path = video_path
    self._hdf5_path = hdf5_path
    self._is_reference_camera = is_reference_camera

    # Get video properties
    self._width, self._height, self._fps, self._total_frames = self._get_video_properties()
    self._width_scaled = 720
    self._height_scaled = 405
    self._frame_buf_size = self._width_scaled*self._height_scaled*3

    # Read HDF5 metadata for synchronization
    self._read_sync_metadata()

    # Initialize truncation points
    self._start_frame = 0
    self._end_frame = self._total_frames - 1
    self._truncated_frame_count = int(self._total_frames)

    # Create FFmpeg decode cache, will prefetch a window, centered 1/3 of requested cache miss frame
    self._prefetch_window_s = 5.0
    self._num_prefetch_frames = round(self._fps*self._prefetch_window_s)
    self._cache = FFmpegCache(decode_fn=self._decode, decode_fetch_offset=round(self._num_prefetch_frames/3))
    self._cache.start()

    # Create image placeholder
    self._fig = px.imshow(img=np.zeros([self._height_scaled, self._width_scaled, 3], np.uint8), binary_string=True)
    self._fig.update_layout(
      title_text=self._legend_name,
      title_font_size=11,
      coloraxis_showscale=False,
      margin=dict(l=0, r=0, t=20, b=0),
      autosize=True,
      height=None
    )
    self._fig.update_xaxes(showticklabels=False, showgrid=False)
    self._fig.update_yaxes(showticklabels=False, showgrid=False)

    # Create layout with timestamp display
    self._image = dcc.Graph(
      figure=self._fig,
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
      dcc.Loading(
        id="%s-loader"%(self._unique_id),
        children=[
          self._image,
          self._timestamp_display
        ],
        type="default",
        # target_components={"%s-video"%(self._unique_id): "figure"}
      )
    ], width=self._col_width)

    self._activate_callbacks()


  def _decode(self, frame_id: int) -> Dict[int, bytes]:
    # Seek to the timestamp because it is much faster than using frame index
    # TODO: get the timestamp from the HDF5? Now assumes no video frames lost
    timestamp_start = frame_id / self._fps
    # Get multiple frames for caching, to mask decoding latency
    buf, _ = (
      ffmpeg.input(
        filename=self._video_path,
        ss=timestamp_start,
      )
      .output(
        'pipe:',
        format='image2pipe',
        vframes=self._num_prefetch_frames,
      )
      .run(capture_stdout=True, quiet=True)
    )
    # Split continuous images buffer of jpeg-encoded frames by known end-of-image delimeter
    new_cache = dict(zip(range(frame_id, frame_id+self._num_prefetch_frames), map(lambda frame: frame+EOI, buf.split(EOI)[:-1])))
    return new_cache


  def _get_frame(self, frame_id: int) -> bytes:
    """Get frame at specific index"""
    # Ensure we don't go beyond bounds
    if frame_id < 0:
      frame_id = 0
    elif frame_id >= self._total_frames:
      frame_id = self._total_frames - 1

    # Get the frame from the cache manager
    try:
      img = self._cache.get_data(frame_id)
      return img
    except Exception as e:
      print(f"Error getting frame {frame_id}: {e}")
      return np.zeros((self._height_scaled*self._width_scaled*3), dtype=np.uint8).tobytes()


  def _get_video_properties(self) -> Tuple[int, int, float, int]:
    """Get video width, height, fps, and total frames using cv2"""
    probe = ffmpeg.probe(self._video_path)
    video_stream = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
    width = int(video_stream['width'])
    height = int(video_stream['height'])
    fps_num, fps_denum = map(lambda x: float(x), video_stream['r_frame_rate'].split('/'))
    fps = fps_num/fps_denum
    num_frames = round(float(probe['format']['duration']) * fps)

    return width, height, fps, num_frames


  def get_frame_for_timestamp(self, target_timestamp: float) -> int:
    """Find the frame index closest to a given timestamp with offset"""
    if self._toa_s is not None:
      time_diffs = np.abs(self._toa_s - target_timestamp)
      closest_idx = np.argmin(time_diffs)
      # No offset for regular cameras
      return int(closest_idx)
    else:
      return 0


  def get_timestamp_at_frame(self, frame_index: int) -> float:
    """Get the timestamp for a given frame"""
    if self._toa_s is not None and frame_index < len(self._toa_s):
      return self._toa_s[frame_index].item()
    else:
      return 0.0


  def _read_sync_metadata(self):
    """Reads synchronization metadata from HDF5 file"""
    with h5py.File(self._hdf5_path, 'r') as hdf5:
      # Using frame_sequence_id or toa_s for synchronization, could not find a drastic difference between the two, sticking with toa_s for now
      seq_path = f'/cameras/{self._unique_id}/frame_sequence_id'
      toa_path = f'/cameras/{self._unique_id}/toa_s'

      try:
        self._frame_sequence_ids = hdf5[seq_path][:]
        self._toa_s = hdf5[toa_path][:]
      except Exception as e:
        print(f"Error reading timestamps for cameras: {e}")


  def get_sync_info(self):
    """Return synchronization info for this component"""
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
      Output("%s-video"%(self._unique_id), "figure"),
      Output("%s-timestamp"%(self._unique_id), "children"),
      Input("frame-id", "data"),
      Input("sync-timestamp", "data"),
      Input("offset-update-trigger", "data"),
      # prevent_initial_call=False,
    )
    def update_camera(slider_position, sync_timestamp, offset_trigger):
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
        fig = Patch()
        fig["data"][0]["source"] = "data:image/jpeg;base64,%s"%base64.b64encode(img).decode('utf-8')

        # Get timestamp for display
        timestamp = self.get_timestamp_at_frame(frame_id)
        timestamp_text = f"toa_s: {timestamp:.5f} (frame: {frame_id})"

        return fig, timestamp_text
      except Exception as e:
        print(f"Error loading frame for {self._unique_id}: {e}")
        return Patch(), "Error"
