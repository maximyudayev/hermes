from streamers.SensorStreamer import SensorStreamer
from streams import InsoleStream
from utils.msgpack_utils import serialize

import time

from utils.print_utils import *

import socket

################################################
################################################
# A class to inteface with Moticon insole sensors.
################################################
################################################
class InsoleStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'insole'

  ########################
  ###### INITIALIZE ######
  ########################

  # Initialize the sensor streamer.
  def __init__(self,
               sampling_rate_hz: int = 100,
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               print_status: bool = True, 
               print_debug: bool = False):
    
    stream_info = {
      "sampling_rate_hz": sampling_rate_hz
    }

    super().__init__(self, 
                     stream_info=stream_info,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status,
                     print_debug=print_debug)
    
    input_ip = "127.0.0.1"
    port = 8888
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.sock.settimeout(0.5)
    self.sock.bind((input_ip, port))


  # Factory class method called inside superclass's constructor to instantiate corresponding Stream object.
  def create_stream(cls, stream_info: dict) -> InsoleStream:
    return InsoleStream(**stream_info)


  # Connect to the sensor.
  def connect(self) -> bool:
    try:
      self.sock.recv(1024)
    except socket.timeout:
      time.sleep(1)
    return True


  def run(self) -> None:
    while self._running:
      data, address = self.sock.recvfrom(1024) # data is whitespace-separated byte string
      time_s: float = time.time()

      # Store the captured data into the data structure.
      self._stream.append_data(time_s=time_s, data=data)

      # Get serialized object to send over ZeroMQ.
      msg = serialize(time_s=time_s, data=data)

      # Send the data packet on the PUB socket.
      self._pub.send_multipart(["%s.data"%self._log_source_tag, msg])


  # Clean up and quit
  def quit(self) -> None:
    self.sock.close()
    super().quit()
