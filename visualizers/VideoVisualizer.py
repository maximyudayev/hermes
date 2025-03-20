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
from dash import Output, Input, State, dcc
import dash_bootstrap_components as dbc
import plotly.express as px
import cv2


class VideoVisualizer(Visualizer):
  def __init__(self,
               stream: Stream,
               unique_id: str,
               data_path: dict[str, str],
               legend_name: str,
               update_interval_ms: int,
               color_format: int,
               col_width: int = 6):
    super().__init__(stream=stream,
                     col_width=col_width)

    self._data_path = data_path
    self._legend_name = legend_name
    self._update_interval_ms = update_interval_ms
    self._unique_id = unique_id
    self._color_format = color_format

    self._image = dcc.Graph(id="%s-video"%(self._unique_id))
    self._interval = dcc.Interval(id="%s-video-interval"%(self._unique_id), interval=self._update_interval_ms, n_intervals=0)
    self._layout = dbc.Col([
        self._image,
        self._interval],
      width=self._col_width)
    self._activate_callbacks()


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to `Stream`. 
  def _activate_callbacks(self):
    @app.callback(
      Output("%s-video"%(self._unique_id), component_property='figure'),
      Input("%s-video-interval"%(self._unique_id), component_property='n_intervals'),
      State("%s-video"%(self._unique_id), component_property='figure'),
      prevent_initial_call=True
    )
    def update_live_data(n, old_fig):
      device_name, stream_name = list(self._data_path.items())[0]
      new_data = self._stream.get_data(device_name=device_name,
                                       stream_name=stream_name,
                                       starting_index=-1)
      if new_data is not None:
        img = new_data['data'][0]
        if self._color_format: 
          img = cv2.cvtColor(src=img, 
                             code=self._color_format)
        fig = px.imshow(img=img)
        # fig.update(title_text=self._legend_name)
        fig.update_layout(coloraxis_showscale=False)
        fig.update_xaxes(showticklabels=False)
        fig.update_yaxes(showticklabels=False)
        return fig
      else:
        return old_fig
