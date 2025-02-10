from producers.Producer import Producer
from streams.InsoleStream import InsoleStream

from utils.print_utils import *
from utils.zmq_utils import *
import socket
import time


##################################################
##################################################
# A class to inteface with Moticon insole sensors.
##################################################
##################################################
class InsoleStreamer(Producer):
  @property
  def _log_source_tag(self) -> str:
    return 'insole'


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


  def create_stream(cls, stream_info: dict) -> InsoleStream:
    return InsoleStream(**stream_info)


  def _connect(self) -> bool:
    try:
      self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      self._sock.settimeout(0.5)
      self._sock.bind((IP_LOOPBACK, PORT_MOTICON))
      self._sock.recv(1024)
      self._sock.settimeout(None)
      return True
    except socket.timeout:
      return False


  def _process_data(self) -> None:
    if self._is_continue_capture:
      data, address = self._sock.recvfrom(1024) # data is whitespace-separated byte string
      time_s: float = time.time()
      tag: str = "%s.data" % self._log_source_tag
      self._publish(tag, time_s=time_s, data=data)
    else:
      self._send_end_packet()


  def _stop_new_data(self):
    self._sock.close()


  def _cleanup(self) -> None:
    super()._cleanup()


# TODO: update the unit test.
#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  pass
