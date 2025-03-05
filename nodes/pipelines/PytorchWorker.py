from pipelines.Pipeline import Pipeline

import numpy as np
import time
from collections import OrderedDict
import zmq

from utils.zmq_utils import *


######################################################
######################################################
# A class for processing sensor data with an AI model.
######################################################
######################################################
class PytorchWorker(Pipeline):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'ai'


  def __init__(self,
               stream_info: dict,
               logging_spec: dict,
               stream_specs: list[dict],
               port_pub: str = PORT_BACKEND,
               port_sub: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               print_status: bool = True,
               print_debug: bool = False,
               **_):

    # Initialize any state that the sensor needs.
    stream_info = {
      
    }

    super().__init__(stream_info=stream_info,
                     logging_spec=logging_spec,
                     stream_specs=stream_specs,
                     port_pub=port_pub,
                     port_sub=port_sub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status, 
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict):
    pass


  def _process_data(self) -> None:
    # NOTE: time-of-arrival available with each packet.
    process_time_s: float = time.time()
    if self._is_continue_produce: # TODO: have a meaningful check condition
      # TODO: Do AI processing here.

      tag: str = "%s.data" % self._log_source_tag()
      self._publish(tag, time_s=process_time_s)
    elif not self._is_continue_produce:
      # If triggered to stop and no more available data, send empty 'END' packet and join.
      self._send_end_packet()


  def _stop_new_data(self):
    pass
  

  def _cleanup(self) -> None:
    super()._cleanup()
