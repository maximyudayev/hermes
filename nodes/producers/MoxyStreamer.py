from nodes.producers.Producer import Producer
from streams import MoxyStream

from openant.easy.node import Node as AntNode
from openant.devices.scanner import Scanner
from openant.devices import ANTPLUS_NETWORK_KEY

from collections import defaultdict
import queue
from utils.print_utils import *
from utils.zmq_utils import *


class CustomAntNode(AntNode):
  def __init__(self, devices: list[str]):
    super().__init__()
    self._expected_devices = devices


  def sample_devices(self):
    timer = 5
    start_time = time.time()
    self.devices = set()
    while time.time() - timer < start_time:
      try:
        self._datas.qsize()
        (data_type, channel, data) = self._datas.get(True)
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
    if len(self.devices) == len(self._expected_devices):
      return True
    else:
      return False


class MoxyStreamer(Producer):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'moxy'


  def __init__(self,
               logging_spec: dict,
               devices: list[str],
               sampling_rate_hz: float = 0.5,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               transmit_delay_sample_period_s: float = None,
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
                     transmit_delay_sample_period_s=transmit_delay_sample_period_s,
                     print_status=print_status,
                     print_debug=print_debug)

    self.counter_per_sensor = defaultdict(lambda: -1)


  def create_stream(cls, stream_info: dict) -> MoxyStream:
    return MoxyStream(**stream_info)


  def _ping_device(self) -> None:
    return None


  def _connect(self) -> bool:   
    self.node = CustomAntNode(self._devices)
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
        data_type, channel, data = self.node._datas.get(True)
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
              tag: str = "%s.%s.data" % (self._log_source_tag(), device_id)
              data = {
                'THb': THb,
                'SmO2': SmO2,
                'counter': counter,
              }
              self._publish(tag=tag, time_s=time_s, data={'moxy-%s-data'%device_id: data})
              self.counter_per_sensor[device_id] = counter
        else:
          print("Unknown data type '%s': %r", data_type, data)
      except Exception as e:
        print("Error: %s"%e)
    else:
      self._send_end_packet()


  def _stop_new_data(self):
    pass

  
  def _cleanup(self) -> None:
    super()._cleanup()
