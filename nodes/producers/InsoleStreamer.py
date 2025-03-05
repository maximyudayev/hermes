from producers.Producer import Producer
from streams import InsoleStream

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
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'insoles'


  def __init__(self,
               logging_spec: dict,
               sampling_rate_hz: int = 100,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               transmit_delay_sample_period_s: float = None,
               print_status: bool = True, 
               print_debug: bool = False,
               **_):
    
    stream_info = {
      "sampling_rate_hz": sampling_rate_hz
    }

    super().__init__(stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     transmit_delay_sample_period_s=transmit_delay_sample_period_s,
                     print_status=print_status,
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict) -> InsoleStream:
    return InsoleStream(**stream_info)


  def _ping_device(self) -> None:
    return None


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
      payload, address = self._sock.recvfrom(1024) # data is whitespace-separated byte string
      time_s: float = time.time()
      payload = [float(word) for word in payload.split()] # splits byte string into array of (multiple) bytes, removing whitespace separators between measurements

      data = {
        'timestamp': payload[0],
        'foot_pressure_left': payload[9:25],
        'foot_pressure_right': payload[34:50],
        'acc_left': payload[1:4],
        'acc_right': payload[26:29],
        'gyro_left': payload[4:7],
        'gyro_right': payload[29:32],
        'total_force_left': payload[25],
        'total_force_right': payload[50],
        'center_of_pressure_left': payload[7:9],
        'center_of_pressure_right': payload[32:34],
      }

      tag: str = "%s.data" % self._log_source_tag()
      self._publish(tag, time_s=time_s, data={'insoles-data': data})
    else:
      self._send_end_packet()


  def _stop_new_data(self):
    self._sock.close()


  def _cleanup(self) -> None:
    super()._cleanup()
