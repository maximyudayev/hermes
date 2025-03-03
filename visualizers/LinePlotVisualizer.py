from visualizers import Visualizer
from streams import Stream
from utils.gui_utils import app
from dash import Output, Input, dcc
import dash_bootstrap_components as dbc
from plotly.tools import make_subplots
import plotly.express as px
import numpy as np


class LinePlotVisualizer(Visualizer):
  def __init__(self,
               stream: Stream,
               data_path: dict[str, list[str]],
               legend_names: list[str],
               plot_duration_timesteps: int,
               update_interval_ms: int,
               col_width: int = 6):
    super().__init__(stream=stream,
                     col_width=col_width)
    self._data_path = data_path
    self._legend_names = legend_names
    self._plot_duration_timesteps = plot_duration_timesteps
    self._update_interval_ms = update_interval_ms

    self._figure = dcc.Graph(),
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
      device_name, stream_names = self._data_path.items()[0]
      data = self._stream.get_data_multiple_streams(device_name=device_name,
                                                    stream_names=stream_names,
                                                    starting_index=-self._plot_duration_timesteps)
      fig = make_subplots(rows=len(data), 
                          cols=1, 
                          shared_yaxes=True, 
                          shared_xaxes=True,
                          vertical_spacing=0.02,
                          subplot_titles=stream_names)

      # Create the line plot for each DOF.
      for i, stream_data in enumerate(data):
        arr = np.array(stream_data['data'])
        for j in range(arr.shape[1]):
          fig.add_trace(px.scatter(x=stream_data['time_s'],
                                   y=arr[:,j], 
                                   mode="lines",
                                   name=self._legend_names[j]), 
                        row=i+1,
                        col=1)
      fig.update(title_text=device_name)
      return fig


#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  import threading
  from utils.zmq_utils import *
  from utils.gui_utils import server
  from wsgiref.simple_server import make_server

  # TODO: instantiate the Stream object with data and pass to the Visualizer
  lineplot = LinePlotVisualizer(stream=stream,
                                device_name='dots-imu',
                                stream_names=['acceleration-x',
                                              'acceleration-y',
                                              'acceleration-z'],
                                plot_duration_timesteps=timesteps_before_solidified,
                                col_width=6)
  
  app.layout = dbc.Container([lineplot])
  
  # Launch Dash GUI thread.
  flask_server = make_server(DNS_LOCALHOST, PORT_GUI, server)
  flask_server_thread = threading.Thread(target=flask_server.serve_forever)
  flask_server_thread.start()

  dash_app_thread = threading.Thread(target=app.run, kwargs={'debug': True})
  dash_app_thread.start()

  input("Press any key to stop the test.")

  flask_server.shutdown()
  flask_server_thread.join()
  dash_app_thread.join()
