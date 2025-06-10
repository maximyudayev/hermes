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
from plotly.tools import make_subplots
import plotly.express as px
import numpy as np


class LinePlotComponent(BaseComponent):
  def __init__(self,
               unique_id: str,
               legend_names: list[str],
               plot_duration_timesteps: int,
               col_width: int = 6):
    super().__init__(col_width=col_width)

    self._legend_names = legend_names
    self._plot_duration_timesteps = plot_duration_timesteps
    self._unique_id = unique_id

    self._figure = dcc.Graph(id="%s-fig"%(self._unique_id)),
    self._layout = dbc.Col([self._figure], width=self._col_width)
    self._activate_callbacks()


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to corresponding file. 
  def _activate_callbacks(self):
    @app.callback(
      Output("%s-fig"%(self._unique_id), component_property='figure'),
      Input(),
      State("%s-fig"%(self._unique_id), component_property='figure'),
      prevent_initial_call=True
    )
    def update_live_data(n, old_fig):
      # TODO: get the desired sample range from the HDF5 file.
      
      fig = make_subplots(rows=len(new_data),
                          cols=1,
                          shared_yaxes=True, 
                          shared_xaxes=True,
                          vertical_spacing=0.02,
                          subplot_titles=stream_names)

      # Create the line plot for each DOF.
      for i, stream_data in enumerate(new_data):
        arr = np.array(stream_data['data'])
        for j in range(arr.shape[1]):
          fig.add_trace(
            px.scatter(x=stream_data['time_s'],
                        y=arr[:,j],
                        mode="lines",
                        name=self._legend_names[j]),
            row=i+1,
            col=1)
      fig.update(title_text=device_name)
      return fig
