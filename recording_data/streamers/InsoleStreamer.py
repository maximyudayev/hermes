import pickle
import struct
from streamers import SensorStreamer
from streams import InsoleStream
from utils.msgpack_utils import serialize

import time

from utils.print_utils import *

import socket

# TODO: insole data has this structure, it needs to be parsed parsed into an object. 
# timestamp 
# left.acceleration[0] 
# left.acceleration[1] 
# left.acceleration[2] 
# left.angular[0] 
# left.angular[1] 
# left.angular[2] 
# left.cop[0] 
# left.cop[1] 
# left.pressure[0] 
# left.pressure[1] 
# left.pressure[2] 
# left.pressure[3] 
# left.pressure[4] 
# left.pressure[5] 
# left.pressure[6] 
# left.pressure[7] 
# left.pressure[8] 
# left.pressure[9] 
# left.pressure[10] 
# left.pressure[11] 
# left.pressure[12] 
# left.pressure[13] 
# left.pressure[14] 
# left.pressure[15] 
# left.total_force 
# right.acceleration[0] 
# right.acceleration[1] 
# right.acceleration[2] 
# right.angular[0] 
# right.angular[1] 
# right.angular[2] 
# right.cop[0] 
# right.cop[1] 
# right.pressure[0] 
# right.pressure[1] 
# right.pressure[2] 
# right.pressure[3] 
# right.pressure[4] 
# right.pressure[5] 
# right.pressure[6] 
# right.pressure[7] 
# right.pressure[8] 
# right.pressure[9] 
# right.pressure[10] 
# right.pressure[11] 
# right.pressure[12] 
# right.pressure[13] 
# right.pressure[14] 
# right.pressure[15] 
# right.total_force

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
               log_player_options=None, visualization_options=None,
               print_status=True, print_debug=False, log_history_filepath=None):
    SensorStreamer.__init__(self, streams_info=None,
                            visualization_options=visualization_options,
                            log_player_options=log_player_options,
                            print_status=print_status, print_debug=print_debug,
                            log_history_filepath=log_history_filepath)
    
    input_ip = "127.0.0.1"
    port = 8888
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.sock.settimeout(0.5)
    self.sock.bind((input_ip, port))

  # Factory class method called inside superclass's constructor to instantiate corresponding Stream object.
  def create_stream(cls, stream_info: dict | None = None) -> InsoleStream:
    return InsoleStream(**stream_info)

  # Connect to the sensor.
  def connect(self):
    while True:
      try:
        self.sock.recv(1024)
      except socket.timeout:
        time.sleep(1)
      return True

  def run(self):
    while self._running:
      data, address = self.sock.recvfrom(1024) # data is whitespace-separated byte string
      time_s: float = time.time()

      # Store the captured data into the data structure.
      self._stream.append_data(time_s=time_s, data=data)

      # Get serialized object to send over ZeroMQ.
      msg = serialize(time_s=time_s, data=data)

      # Send the data packet on the PUB socket.
      self._pub.send_multipart([b"%s.data"%self._log_source_tag, msg])

  # Clean up and quit
  def quit(self):
    self.sock.close()
