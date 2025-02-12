from producers.Producer import Producer
from streams.DummyStream import DummyStream

from utils.print_utils import *
from utils.zmq_utils import *
import time


class DummyProducer(Producer):
  @property
  def _log_source_tag(self) -> str:
    return 'dummy-producer'


  def __init__(self,
               sampling_rate_hz: int = 100,
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               print_status: bool = True, 
               print_debug: bool = False,
               **_):
    
    stream_info = {
      "sampling_rate_hz": sampling_rate_hz
    }

    super().__init__(stream_info=stream_info,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status,
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict) -> DummyStream:
    return DummyStream(**stream_info)


  def _connect(self) -> bool:
    return True


  def _process_data(self) -> None:
    if self._is_continue_capture:
      time_s: float = time.time()
      tag: str = "%s.data" % self._log_source_tag
      self._publish(tag, time_s=time_s, data={'dummy-data': time_s})
    else:
      self._send_end_packet()


  def _stop_new_data(self):
    pass


  def _cleanup(self) -> None:
    super()._cleanup()


# TODO: update the unit test.
#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  pass
