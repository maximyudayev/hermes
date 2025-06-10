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

from annotation.components.BaseComponent import BaseComponent
from utils.gui_utils import app
from dash import Output, Input, State, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import cv2


class GazeVisualizer(BaseComponent):
  def __init__(self,
               video_path: str,
               hdf5_path: str,
               unique_id: str,
               legend_name: str,
               color_format: int,
               col_width: int = 6):
    super().__init__(col_width=col_width)

    self._legend_name = legend_name
    self._color_format = color_format
    self._unique_id = unique_id

    self._image = dcc.Graph(id="%s-gaze"%(self._unique_id))
    self._layout = dbc.Col([self._image], width=self._col_width)
    self._activate_callbacks()


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to `Stream`. 
  def _activate_callbacks(self):
    @app.callback(
      Output("%s-gaze"%(self._unique_id), component_property='figure'),
      Input(),
      State("%s-gaze"%(self._unique_id), component_property='figure'),
      prevent_initial_call=True
    )
    def update_live_data(n, old_fig):
      # TODO: get the desired video frame from the MKV/MP4 file using ffmpeg.
      if new_data is not None:
        world_data = new_data['data']
        if self._color_format: 
          world_data = cv2.cvtColor(src=world_data, 
                                    code=self._color_format)
        fig = px.imshow(img=world_data)
        fig.update(title_text=self._legend_name)
        fig.update_layout(coloraxis_showscale=False)
        fig.update_xaxes(showticklabels=False)
        fig.update_yaxes(showticklabels=False)
        # Overlay scene gaze point onto the image.
        # TODO: get the desired gaze data from the HDF5 file.
        if new_gaze_data is not None:
          gaze_data = new_gaze_data['data']
          fig.add_trace(go.Scatter(x=gaze_data[0],
                                   y=gaze_data[1],
                                   marker=dict(color='red', size=16)))
        return fig
      else:
        return old_fig
