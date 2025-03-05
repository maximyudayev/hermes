from consumers.Consumer import Consumer
from handlers.LoggingHandler import Logger

import threading
from wsgiref.simple_server import make_server
import dash_bootstrap_components as dbc

from utils.gui_utils import server, app
from utils.print_utils import *
from utils.zmq_utils import *


######################################
######################################
# A class to visualize streaming data.
######################################
######################################
class DataVisualizer(Consumer):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'visualizer'


  def __init__(self, 
               stream_specs: list[dict],
               logging_spec: dict,
               log_history_filepath: str = None,
               port_sub: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               print_status: bool = True, 
               print_debug: bool = False, 
               **_):

    super().__init__(stream_specs=stream_specs,
                     port_sub=port_sub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     log_history_filepath=log_history_filepath,
                     print_status=print_status,
                     print_debug=print_debug)

    # Inherits the datalogging functionality.
    self._logger = Logger(**logging_spec)

    # Init all Dash widgets before launching the server and the GUI thread.
    # NOTE: order Dash widgets in the order of streamer specs provided upstream.
    self._layout = dbc.Container([
      *[visualizer := stream.build_visulizer() for stream in self._streams.values() if visualizer],
    ])

    # Launch datalogging thread with reference to the Stream object.
    self._logger_thread = threading.Thread(target=self._logger, args=(self._streams,))
    self._logger_thread.start()

    # Launch Dash GUI thread.
    self._flask_server = make_server(DNS_LOCALHOST, PORT_GUI, server)
    self._flask_server_thread = threading.Thread(target=self._flask_server.serve_forever)
    self._flask_server_thread.start()

    self._dash_app_thread = threading.Thread(target=app.run, kwargs={'debug': True})
    self._dash_app_thread.start()


  def _cleanup(self):
    self._logger.cleanup()
    self._flask_server.shutdown()
    self._logger_thread.join()
    self._flask_server_thread.join()
    self._dash_app_thread.join()
    super()._cleanup()
