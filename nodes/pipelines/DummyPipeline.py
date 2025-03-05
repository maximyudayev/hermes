from nodes.pipelines.Pipeline import Pipeline
from streams import DummyStream
from handlers.LoggingHandler import Logger

import threading
import time
from utils.zmq_utils import *


class DummyPipeline(Pipeline):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'dummy-pipeline'


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

    # Abstract class will call concrete implementation's creation methods
    #   to build the data structure of the sensor
    super().__init__(stream_info=stream_info,
                     logging_spec=logging_spec,
                     stream_specs=stream_specs,
                     port_pub=port_pub,
                     port_sub=port_sub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status, 
                     print_debug=print_debug)
    
    # Inherits the datalogging functionality.
    self._in_logger = Logger(**logging_spec)

    # Launch datalogging thread with reference to the Stream object.
    self._in_logger_thread = threading.Thread(target=self._logger, args=(self._in_streams,))
    self._in_logger_thread.start()


  def create_stream(cls, stream_info: dict) -> DummyStream:
    return DummyStream(**stream_info)


  def _process_data(self) -> None:
    if self._is_continue_produce:
      process_time_s: float = time.time()
      tag: str = "%s.data" % self._log_source_tag()
      self._publish(tag, time_s=process_time_s, data=process_time_s)
    elif not self._is_continue_produce:
      # If triggered to stop and no more available data, send empty 'END' packet and join.
      self._send_end_packet()


  def _stop_new_data(self):
    pass
  

  def _cleanup(self) -> None:
    # Finish up the file saving before exitting.
    self._in_logger.cleanup()
    self._in_logger_thread.join()
    super()._cleanup()
