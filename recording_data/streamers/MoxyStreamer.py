from collections import OrderedDict, defaultdict
import queue

import numpy as np


from streamers.SensorStreamer import SensorStreamer
from streams.MoxyStream import MoxyStream

from utils.msgpack_utils import serialize
from utils.print_utils import *

from openant.easy.node import Node
from openant.devices.common import DeviceType, AntPlusDevice
from openant.devices.scanner import Scanner
from openant.devices.utilities import auto_create_device
from openant.devices import ANTPLUS_NETWORK_KEY

class CustomNode(Node):

    def __init__(self):
        super().__init__()

    def sample_devices(self):
        timer = 5
        start_time = time.time()
        self.devices = set()
        while time.time() - timer < start_time:
            try:
                (data_type, channel, data) = self._datas.get(True, 1.0)
                self._datas.task_done()
                if data_type == "broadcast":
                    byte_data = bytes(data)
                    id = f"{byte_data[8]}.{byte_data[9]}.{byte_data[10]}.{byte_data[11]}:{byte_data[12]}"
                    if id not in self.devices:
                        print(f"device: {id} found")
                        self.channels[channel].on_broadcast_data(data)
                        self.devices.add(id)
            except queue.Empty as _:
                pass
        if len(self.devices) == 3:
            return True
        else:
            return False


class MoxyStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = "moxy"

  ########################
  ###### INITIALIZE ######
  ########################

  def __init__(self, 
               devices: list[str] = [],
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               print_status: bool = True, 
               print_debug: bool = False):

    stream_info = {"devices": devices}

    super().__init__(port_pub=port_pub,
                        port_sync=port_sync,
                        port_killsig=port_killsig,
                        stream_info=stream_info,
                        print_status=print_status, 
                        print_debug=print_debug)
    
    self.devices = devices
   

  #def create_stream(argumets) -> AwindaStream:  
  #  return AwindaStream(argumets["device_mapping"], argumets["num_joints"], argumets["radio_channel"])
  @classmethod
  def create_stream(cls, stream_info: dict) -> MoxyStream:
    return MoxyStream(**stream_info)
  
  def connect(self) -> None:
    
    self.devices = []
    self.node = CustomNode()
    self.node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)
    self.node.sample_devices()


  # Acquire data from the sensors until signalled externally to quit
  def run(self) -> None:
    # While background process reads-out new data, can do something useful
    #   like poll for commands from the Broker to terminate, and block on the Queue 
    while self._running:
        counter_per_sensor = defaultdict(lambda: -1)
        try:
            (data_type, channel, data) = self.node._datas.get(True, 1.0)
            self.node._datas.task_done()
            if data_type == "broadcast":
                byte_data = bytes(data)
                if data[0] == 1:
                    time_s = time.time()
                    counter = data[1]
                    THb = ((int(data[4] >> 4) << 4) + (int(data[4] % 2**4)) + (int(data[5] % 2**4) << 8)) * 0.01
                    SmO2 = ((int(data[7] >> 4) << 6) + (int(data[7] % 2**4) << 2) + int(data[6] % 2**4)) * 0.1
                    device_id = f"{byte_data[8]}.{byte_data[9]}.{byte_data[10]}.{byte_data[11]}:{byte_data[12]}"
                    if counter_per_sensor[device_id] != counter:
                        self._stream.append_data(device_id, time_s, THb, SmO2, counter)
                        msg = serialize(time_s=time_s, device_id=device_id, THb=THb, SmO2=SmO2, counter=counter)
                        # Send the data packet on the PUB socket.
                        self._pub.send_multipart([("%s.data" % self._log_source_tag).encode('utf-8'), msg])
            else:
                  print("Unknown data type '%s': %r", data_type, data)
        except queue.Empty as _:
              pass        

  
  # Clean up and quit
  def quit(self) -> None:
    
    super().quit(self)