from producers.Producer import Producer
from streams import CyberlegStream

from utils.print_utils import *
from utils.zmq_utils import *
import socket
import time
import struct


######################################################
######################################################
# A class to inteface with AidWear Cyberleg to receive 
#   smartphone activity selection data.
# At the moment consists of 3 bytes:
#   - 0-9 - main task
#   - 0-9 - subtask
#   - o/f - boolean for both motors ON
######################################################
######################################################
class CyberlegStreamer(Producer):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'cyberleg'


  def __init__(self,
               logging_spec: dict,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               print_status: bool = True, 
               print_debug: bool = False,
               **_):

    self._num_packet_bytes = 3
    stream_info = {
    }

    super().__init__(stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status,
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict) -> CyberlegStream:
    return CyberlegStream(**stream_info)


  def _ping_device(self) -> None:
    return None


  def _connect(self) -> bool:
    try:
      self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self._sock.connect((IP_PROSTHESIS, PORT_PROSTHESIS))
      self._sock.recv(self._num_packet_bytes)
      return True
    except socket.timeout:
      return False


  def _process_data(self) -> None:
    if self._is_continue_capture:
      payload = self._sock.recv(self._num_packet_bytes) 
      time_s: float = time.time()
      # Interpret smartphone bytes correctly from the prosthesis.
      msg = struct.unpack('ccc', payload) # TODO: unpack the packet.
      data = {
        'activity':     msg[0],
        'subactivity':  msg[1],
        'motor_state':  msg[2], 
        # 'timestamp':    msg[3],
      }
      tag: str = "%s.data" % self._log_source_tag()
      self._publish(tag, time_s=time_s, data={'cyberleg-data': data})
    else:
      self._send_end_packet()


  def _stop_new_data(self):
    self._sock.close()


  def _cleanup(self) -> None:
    super()._cleanup()
