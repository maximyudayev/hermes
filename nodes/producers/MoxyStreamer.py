from producers import Producer
from streams import MoxyStream

from openant.easy.node import Node as AntNode
from openant.devices.scanner import Scanner
from openant.devices import ANTPLUS_NETWORK_KEY

from collections import defaultdict
import queue
from utils.print_utils import *
from utils.zmq_utils import *


class CustomAntNode(AntNode):
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


class MoxyStreamer(Producer):
  @property
  def _log_source_tag(self) -> str:
    return 'moxy'


  def __init__(self,
               logging_spec: dict,
               devices: list[str],
               sampling_rate_hz: float = 0.5,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               print_status: bool = True, 
               print_debug: bool = False,
               **_):

    self._devices = devices
    stream_info = {
      "devices": devices,
      "sampling_rate_hz": sampling_rate_hz
    }

    super().__init__(stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status, 
                     print_debug=print_debug)

    self.counter_per_sensor = defaultdict(lambda: -1)


  def create_stream(cls, stream_info: dict) -> MoxyStream:
    return MoxyStream(**stream_info)


  def _connect(self) -> bool:   
    self.node = CustomAntNode()
    self.node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

    self.scanner = Scanner(self.node, device_id=0, device_type=0)
    def on_update(device_tuple, common):
      device_id = device_tuple[0]
      print(f"Device #{device_id} common data update: {common}")

    # local function to call when device update device specific page data
    def on_device_data(device, page_name, data):
      print(f"Device: {device}, broadcast: {page_name}, data: {data}")

    # local function to call when a device is found - also does the auto-create if enabled
    def on_found(device_tuple):
        print("device found")
        return

    self.scanner.on_found = on_found
    self.scanner.on_update = on_update
    return self.node.sample_devices()
  

  def _process_data(self):
    if self._is_continue_capture:
      try:
        data_type, channel, data = self.node._datas.get(True, 1.0)
        time_s = time.time()
        self.node._datas.task_done()
        if data_type == "broadcast":
          byte_data = bytes(data)
          if data[0] == 1:
            counter = data[1]
            THb = ((int(data[4] >> 4) << 4) + (int(data[4] % 2**4)) + (int(data[5] % 2**4) << 8)) * 0.01
            SmO2 = ((int(data[7] >> 4) << 6) + (int(data[7] % 2**4) << 2) + int(data[6] % 2**4)) * 0.1
            device_id = str(byte_data[9] + (byte_data[10] << 8))
            if self.counter_per_sensor[device_id] != counter:
              tag: str = "%s.%s.data" % (self._log_source_tag, device_id)
              data = {
                'THb': THb,
                'SmO2': SmO2,
                'counter': counter,
              }
              self._publish(tag=tag, time_s=time_s, data={'moxy-%s-data'%device_id: data})
              self.counter_per_sensor[device_id] = counter
        else:
          print("Unknown data type '%s': %r", data_type, data)
      except Exception as _:
        pass
    else:
      self._send_end_packet()


  def _stop_new_data(self):
    pass

  
  def _cleanup(self) -> None:
    super()._cleanup()


# TODO:
#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  import zmq
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
