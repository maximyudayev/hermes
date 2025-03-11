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

from streams import Stream
from visualizers import Visualizer
from utils.gui_utils import app
from dash import Output, Input, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import cv2


class GazeVisualizer(Visualizer):
  def __init__(self,
               stream: Stream,
               world_data_path: dict[str, str],
               gaze_data_path: dict[str, str],
               legend_name: str,
               update_interval_ms: int, # TODO: have 2 update intervals (for video and for gaze overlay)
               color_format: int,
               col_width: int = 6):
    super().__init__(stream=stream,
                     col_width=col_width)

    self._world_data_path = world_data_path
    self._gaze_data_path = gaze_data_path
    self._legend_name = legend_name
    self._update_interval_ms = update_interval_ms
    self._color_format = color_format

    self._image = dcc.Graph()
    self._interval = dcc.Interval(interval=self._update_interval_ms, n_intervals=0)
    self._layout = dbc.Col([
        self._image,
        self._interval],
      width=self._col_width)
    self._activate_callbacks()


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to `Stream`. 
  def _activate_callbacks(self):
    @app.callback(
        Output(self._image, component_property='figure'),
        Input(self._interval, component_property='n_intervals'),
        prevent_initial_call=True
    )
    def update_live_data(n):
      # Display the captured image.
      world_device_name, world_stream_name = self._world_data_path.items()[0]
      world_data = self._stream.get_data(device_name=world_device_name,
                                         stream_name=world_stream_name,
                                         starting_index=-1)['data']
      fig = px.imshow(img=cv2.cvtColor(src=world_data, 
                                       code=self._color_format))
      fig.update(title_text=self._legend_name)
      fig.update_layout(coloraxis_showscale=False)
      fig.update_xaxes(showticklabels=False)
      fig.update_yaxes(showticklabels=False)
      # Overlay scene gaze point onto the image.
      gaze_device_name, gaze_stream_name = self._gaze_data_path.items()[0]
      gaze_data = self._stream.get_data(device_name=gaze_device_name,
                                        stream_name=gaze_stream_name,
                                        starting_index=-1)['data']
      fig.add_trace(go.Scatter(x=gaze_data[0],
                               y=gaze_data[1],
                               marker=dict(color='red', size=16)))
      return fig
