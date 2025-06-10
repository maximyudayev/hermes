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

import time

from annotation.components.BaseComponent import BaseComponent
from utils.gui_utils import app

from dash import Output, Input, State, dcc, html
import dash_bootstrap_components as dbc


class ExperimentControlComponent(BaseComponent):
  def __init__(self,
               activities: list[str],
               col_width: int = 6):
    super().__init__(col_width=col_width)

    self._layout = dbc.Col([
        html.Div([
          html.Span(id="current-activity-indicator", style={"verticalAlign": "middle"}),
          dcc.RadioItems(
            activities,
            activities[0],
            id="activity-radio"
          ),
          dbc.Button("Mark Activity Start", 
                     id="activity-mark-btn", 
                     color="primary", 
                     className="me-1"
          )
        ]),
        dbc.Button(
          "Capturing",
          id="eye-toggle-btn",
          color="primary",
          className="me-1"
        ),
        dbc.Button("Stop Experiment", 
                   id="experiment-stop-btn", 
                   color="danger", 
                   className="me-1"
        ),
        html.Span(id="experiment-status-indicator", style={"verticalAlign": "middle"}),
      ],
      width=self._col_width)
    self._activate_callbacks()


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to corresponding file. 
  def _activate_callbacks(self):
    @app.callback(
      Output("experiment-stop-btn", "disabled"),
      Output("eye-toggle-btn", "disabled"),
      Input("experiment-stop-btn", "n_clicks"),
      prevent_initial_call=True
    )
    def stop_experiment(n):
      return True, True


    @app.callback(
      Output("current-activity-indicator", "children"),
      Input("activity-mark-btn", "n_clicks"),
      State("activity-radio", "value"),
      prevent_initial_call=True
    )
    def mark_activity(n, activity):
      self._stream.append_data(time_s=time.time(), data={"experiment": {"activity": activity}})
      return activity
