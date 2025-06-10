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

from typing import Any, Callable

import numpy as np
from annotation.components.BaseComponent import BaseComponent
from utils.gui_utils import app
from dash import Output, Input, State, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import cv2
import h5py
import ffmpeg


class VideoComponent(BaseComponent):
  def __init__(self,
               video_path: str,
               hdf5_path: str,
              #  TODO: add path inside HDF5 to data of interest
               unique_id: str,
               legend_name: str,
               color_format: int,
               col_width: int = 6):
    super().__init__(unique_id=unique_id,
                     col_width=col_width)

    self._legend_name = legend_name
    self._unique_id = unique_id
    self._color_format = color_format

    self._hdf5 = h5py.File(hdf5_path, 'r')
    self._video: Callable[[int], bytes] = lambda frame_id: (
      ffmpeg.input(video_path)
      .filter('select', 'gte(n,{})'.format(frame_id))
      .output('pipe:', vframes=1, format='rawvideo', pix_fmt='rgb24')
      .run(capture_stdout=True)
    )[0]

    self._image = dcc.Graph(id="%s-video"%(self._unique_id))
    self._layout = dbc.Col([self._image], width=self._col_width)
    self._activate_callbacks()


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to corresponding file.
  def _activate_callbacks(self):
    @app.callback(
      Output("%s-video"%(self._unique_id), component_property='figure'),
      Input("frame-id", component_property="value"), # TODO: trigger on click of the frame skip button or the slider drag.
      # State("%s-video"%(self._unique_id), component_property='figure'),
      prevent_initial_call=True
    )
    def update_live_data(n):
      # TODO: get the desired video frame from the MKV/MP4 file using ffmpeg.
      img_bytes = self._video(n)
      img = np.frombuffer(img_bytes, np.uint8).reshape([720,1280,3])
      # if self._color_format: 
      #   img = cv2.cvtColor(src=img, 
      #                       code=self._color_format)
      fig = px.imshow(img=img)
      # fig.update(title_text=self._legend_name)
      # fig.update_layout(coloraxis_showscale=False)
      # fig.update_xaxes(showticklabels=False)
      # fig.update_yaxes(showticklabels=False)
      return fig
