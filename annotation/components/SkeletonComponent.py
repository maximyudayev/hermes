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
from dash import Output, Input, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go


class SkeletonComponent(BaseComponent):
  def __init__(self, 
               legend_name: str,
               col_width: int = 6):
    super().__init__(col_width=col_width)

    self._legend_name = legend_name

    self._figure = dcc.Graph()
    self._layout = dbc.Col([self._figure], width=self._col_width)
    self._activate_callbacks()


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to corresponding file. 
  def _activate_callbacks(self):
    @app.callback(
        Output(self._figure, component_property='figure'),
        Input(), # TODO: trigger on click of the frame skip button or the slider drag.
        prevent_initial_call=True
    )
    def update_live_data(n):
      # TODO: get the desired skeleton frame from the HDF5 file.
      # TODO: convert Quaternion orientation to 3D coordinates using x-IMU MOCAP repo if raw IMU data.

      # To plot discontinuous limb segments, separate each line segment in each DOF with `None`.
      fig = go.Scatter3d(x=[-0.013501551933586597, -0.14018067717552185, None, 
                            0.03889404982328415, -0.01468866690993309, None],
                         y=[],
                         z=[],
                         mode='lines',
                         line_width=2)
      fig.update(title_text=device_name)
      return fig
