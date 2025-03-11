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
from visualizers import Visualizer
from streams import Stream

from utils.zmq_utils import *
from utils.gui_utils import app

from dash import Output, Input, State, dcc, html
import dash_bootstrap_components as dbc
import zmq


class ExperimentControlVisualizer(Visualizer):
  def __init__(self,
               stream: Stream,
               activities: list[str],
               col_width: int = 6):
    super().__init__(stream=stream,
                     col_width=col_width)

    self._ctx: zmq.Context = zmq.Context.instance()
    self._eye_pause: zmq.SyncSocket = self._ctx.socket(zmq.REQ)
    self._eye_pause.connect("tcp://%s:%s" % (IP_BACKPACK, PORT_PAUSE))

    self._gui_btn_kill: zmq.SyncSocket = self._ctx.socket(zmq.REQ)
    self._gui_btn_kill.connect("tcp://%s:%s" % (DNS_LOCALHOST, PORT_KILL_BTN))

    # TODO: setup layout conditionally, some streams may be unused in an experiment (e.g. pupil).
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
  #   to get access to the class instance object with reference to `Stream`. 
  def _activate_callbacks(self):
    @app.callback(
      Output("experiment-stop-btn", "disabled"),
      Output("eye-toggle-btn", "disabled"),
      Input("experiment-stop-btn", "n_clicks")
    )
    def stop_experiment(n):
      return True, True


    @app.callback(
      Output("experiment-status-indicator", "children"),
      Input("experiment-stop-btn", "disabled")
    )
    def on_stop_experiment(is_end):
      if is_end:
        self._gui_btn_kill.send_string(MSG_OK)
        self._gui_btn_kill.recv_string()
        self._gui_btn_kill.close()
        self._eye_pause.close()
        return "Experiment Closing"
      else:
        return "Experiment Running"


    @app.callback(
      Output("eye-toggle-btn", "children"),
      Output("eye-toggle-btn", "color"),
      Input("eye-toggle-btn", "n_clicks")
    )
    def toggle_eye(n):
      self._eye_pause.send_string(MSG_OK)
      res = self._eye_pause.recv_string()
      if res == MSG_ON:
        return "Capturing", "primary"
      else:
        return "Paused", "disabled"


    @app.callback(
      Output("current-activity-indicator", "children"),
      Input("activity-mark-btn", "n_clicks"),
      State("activity-radio", "value")
    )
    def mark_activity(n, activity):
      self._stream.append_data(time_s=time.time(), data={"experiment": {"activity": activity}})
      return activity
