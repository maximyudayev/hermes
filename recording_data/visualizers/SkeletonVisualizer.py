from visualizers import Visualizer
from streams import Stream
from utils.gui_utils import app
from dash import Output, Input, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import numpy as np


class SkeletonVisualizer(Visualizer):
  def __init__(self, 
               stream: Stream,
               data_path: dict[str, str],
               legend_name: str,
               update_interval_ms: int,
               col_width: int = 6):
    super().__init__(stream=stream,
                     col_width=col_width)

    self._data_path = data_path
    self._legend_name = legend_name
    self._update_interval_ms = update_interval_ms

    self._figure = dcc.Graph()
    self._interval = dcc.Interval(interval=self._update_interval_ms, n_intervals=0)
    self._layout = dbc.Col([
        self._figure, 
        self._interval],
      width=self._col_width)
    self._activate_callbacks()


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to `Stream`. 
  def _activate_callbacks(self):
    @app.callback(
        Output(self._figure, component_property='figure'),
        Input(self._interval, component_property='n_intervals'),
        prevent_initial_call=True
    )
    def update_live_data(n):
      device_name, stream_name = self._data_path.items()[0]
      data = self._stream.get_data(device_name=device_name,
                                   stream_name=stream_name,
                                   starting_index=-1)['data']
      # TODO: convert Quaternion orientation to 3D coordinates using x-IMU MOCAP repo.

      # To plot discontinuous limb segments, separate each line segment in each DOF with `None`.
      fig = go.Scatter3d(x=[-0.013501551933586597, -0.14018067717552185, None, 
                            0.03889404982328415, -0.01468866690993309, None],
                         y=[],
                         z=[],
                         mode='lines',
                         line_width=2)
      fig.update(title_text=device_name)
      return fig
