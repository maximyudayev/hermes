from nodes.consumers.Consumer import Consumer

from utils.zmq_utils import *


########################################################################
########################################################################
# A class to log streaming data to one or more files.
# Producer instances are passed to the class, and the data
#   that they stream are written to disk periodically and/or at the end.
########################################################################
########################################################################
class DataLogger(Consumer):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'logger'


  def __init__(self,
               stream_specs: list[dict],
               logging_spec: dict,
               port_sub: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               log_history_filepath: str = None,
               print_status: bool = True,
               print_debug: bool = False,
               **_):

    # Inherits FSM and Consumer ZeroMQ functionality.
    super().__init__(stream_specs=stream_specs,
                     logging_spec=logging_spec,
                     port_sub=port_sub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     log_history_filepath=log_history_filepath,
                     print_status=print_status,
                     print_debug=print_debug)


  def _cleanup(self):
    super()._cleanup()
