from visualizers import Visualizer
from streams import Stream
from utils.gui_utils import app
from dash import Output, Input, dcc
import dash_bootstrap_components as dbc
import plotly.express as px


class InsolePressureVisualizer(Visualizer):
  def __init__(self,
               stream: Stream,
               data_path: dict[str, list[str]],
               legend_names: list[str],
               update_interval_ms: int,
               col_width: int = 6):
    super().__init__(stream=stream,
                     col_width=col_width)

    self._data_path = data_path
    self._legend_names = legend_names
    self._update_interval_ms = update_interval_ms

    self._pressure_figure = dcc.Graph()
    self._interval = dcc.Interval(interval=self._update_interval_ms, n_intervals=0)
    self._layout = dbc.Col([
        self._pressure_figure, 
        self._interval],
      width=self._col_width)
    self._activate_callbacks()


  # Callback definition must be wrapped inside an object method 
  #   to get access to the class instance object with reference to `Stream`. 
  def _activate_callbacks(self):
    @app.callback(
        Output(self._pressure_figure, component_property='figure'),
        Input(self._interval, component_property='n_intervals'),
        prevent_initial_call=True
    )
    def update_live_data(n):
      device_name, stream_names = self._data_path.items()[0]
      data = self._stream.get_data_multiple_streams(device_name=device_name,
                                                    stream_names=stream_names,
                                                    starting_index=-1)['data']
      # TODO: implement custom shape for the pressure heatmap
      fig = px.choropleth(

      )
      fig.update(title_text=device_name)
      return fig
