from producers.Producer import Producer
from streams.CyberlegStream import CyberlegStream

from utils.print_utils import *
from utils.zmq_utils import *
import socket
import time


##########################################################################################
##########################################################################################
# A class to inteface with AidWear Cyberleg to receive smartphone activity selection data.
##########################################################################################
##########################################################################################
class CyberlegStreamer(Producer):
  @property
  def _log_source_tag(self) -> str:
    return 'insole'

  def __init__(self,
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               print_status: bool = True, 
               print_debug: bool = False,
               **_):
    
    stream_info = {
    }

    super().__init__(stream_info=stream_info,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status,
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict) -> CyberlegStream:
    return CyberlegStream(**stream_info)


  def _connect(self) -> bool:
    try:
      self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self._sock.settimeout(0.5)
      self._sock.connect((IP_PROSTHESIS, PORT_PROSTHESIS))
      # TODO: Receive `HELLO` message to acknowledge proper conneciton.
      self._sock.recv(1024)
      self._sock.settimeout(None)
      return True
    except socket.timeout:
      return False


  def _process_data(self) -> None:
    if self._is_continue_capture:
      data, address = self._sock.recv(1024)
      time_s: float = time.time()
      tag: str = "%s.data" % self._log_source_tag
      self._publish(tag, time_s=time_s, data=data)
    else:
      self._send_end_packet()


  def _stop_new_data(self):
    self._sock.close()


  def _cleanup(self) -> None:
    super()._cleanup()
