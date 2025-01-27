from collections import defaultdict
import queue

import zmq

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
        self._datas.qsize()
        (data_type, channel, data) = self._datas.get(True, 1.0)
        self._datas.task_done()
        if data_type == "broadcast":
          byte_data = bytes(data)
          id = str(byte_data[9] + (byte_data[10] << 8))
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

  def __init__(self, 
               devices: list[str],
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               print_status: bool = True, 
               print_debug: bool = False):

    self._devices = devices
    stream_info = {"devices": devices}

    super().__init__(port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     stream_info=stream_info,
                     print_status=print_status, 
                     print_debug=print_debug)

    self.counter_per_sensor = defaultdict(lambda: -1)


  def create_stream(cls, stream_info: dict) -> MoxyStream:
    return MoxyStream(**stream_info)


  def connect(self) -> bool:   

    self.node = CustomNode()
    self.node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)


    self.scanner = Scanner(self.node, device_id=0, device_type=0)
    def on_update(device_tuple, common):
      device_id = device_tuple[0]
      print(f"Device #{device_id} common data update: {common}")

    # local function to call when device update device speific page data
    def on_device_data(device, page_name, data):
      print(f"Device: {device}, broadcast: {page_name}, data: {data}")

    # local function to call when a device is found - also does the auto-create if enabled
    def on_found(device_tuple):
        print("device found")
        return

    self.scanner.on_found = on_found
    self.scanner.on_update = on_update
    return self.node.sample_devices()
  


  def run(self) -> None:
    super().run()
    try:
      counter = -1
      while self._running:
        poll_res: tuple[list[zmq.SyncSocket], list[int]] = tuple(zip(*(self._poller.poll())))
        if not poll_res: continue

        if self._pub in poll_res[0]:
          counter += 1
          self._process_data()
          if counter % 10 == 0:
            print("Print processed 10 Moxy packets")        
        if self._killsig in poll_res[0]:
          self._running = False
          print("quitting %s"%self._log_source_tag, flush=True)
          self._killsig.recv_multipart()
          self._poller.unregister(self._killsig)
      self.quit()
    # Catch keyboard interrupts and other exceptions when module testing, for a clean exit
    except Exception as _:
      self.quit()


  def _process_data(self):

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
          device_id = str(byte_data[9] + (byte_data[10] << 8))
          if self.counter_per_sensor[device_id] != counter:
            self._stream.append_data(device_id, time_s, THb, SmO2, counter)
            msg = serialize(time_s=time_s, device_id=device_id, THb=THb, SmO2=SmO2, counter=counter)
            self._pub.send_multipart([("%s.data" % self._log_source_tag).encode('utf-8'), msg])
            self.counter_per_sensor[device_id] = counter
          
      else:
        print("Unknown data type '%s': %r", data_type, data)
    except Exception as _:
        pass        

  
  # Clean up and quit
  def quit(self) -> None:
    super().quit()


#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  devices = [
    "128.69.31.31:5",
    "128.68.31.31:5"]
    # "128.67.31.31:5"

  ip = "127.0.0.1"
  port_backend = "42069"
  port_frontend = "42070"
  port_sync = "42071"
  port_killsig = "42066"

  # Pass exactly one ZeroMQ context instance throughout the program
  ctx: zmq.Context = zmq.Context()

  # Exposes a known address and port to locally connected sensors to connect to.
  local_backend: zmq.SyncSocket = ctx.socket(zmq.XSUB)
  local_backend.bind("tcp://127.0.0.1:%s" % (port_backend))
  backends: list[zmq.SyncSocket] = [local_backend]

  # Exposes a known address and port to broker data to local workers.
  local_frontend: zmq.SyncSocket = ctx.socket(zmq.XPUB)
  local_frontend.bind("tcp://127.0.0.1:%s" % (port_frontend))
  frontends: list[zmq.SyncSocket] = [local_frontend]

  streamer = MoxyStreamer(devices=devices,
                          port_pub=port_backend,
                          port_sync=port_sync,
                          port_killsig=port_killsig)

  streamer()
