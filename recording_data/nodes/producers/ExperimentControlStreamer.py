from producers import Producer
from streams import ExperimentControlStream

from utils.print_utils import *
from utils.zmq_utils import *


#####################################################################
#####################################################################
# A class to create a GUI that can record experiment events.
# Includes calibration periods, activities, and arbitrary user input.
# TODO: allow it to work from CLI, without dependence on GUI.
#####################################################################
#####################################################################
class ExperimentControlStreamer(Producer):
  @property
  def _log_source_tag(self) -> str:
    return 'control'

  
  def __init__(self,
               logging_spec: dict,
               activities: list[str],

               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               print_status: bool = True, 
               print_debug: bool = False,
               **_):
    
    stream_info = {
      "activities": activities
    }

    super().__init__(stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status, 
                     print_debug=print_debug)


  # Instantiate Stream datastructure object specific to this Streamer.
  #   Should also be a class method to create Stream objects on consumers. 
  def create_stream(cls, stream_info: dict) -> ExperimentControlStream:
    return ExperimentControlStream(**stream_info)


  # Connect to the sensor device(s).
  def _connect(self) -> bool:
    return True


  # Clean up and quit
  def _cleanup(self) -> None:
    super()._cleanup()

  
# TODO:
#####################
###### TESTING ######
#####################
