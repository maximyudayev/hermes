from streamers.SensorStreamer import SensorStreamer
from streams.DotsStream import DotsStream

import numpy as np
import time
from collections import OrderedDict
import zmq

from utils.msgpack_utils import serialize
from handlers.MovellaHandler import MovellaFacade

#####################################
#####################################
# A class for streaming Dots IMU data
#####################################
#####################################
class DotsStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'dots'

  def __init__(self,
               device_mapping: dict[str, str],
               master_device: str,
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               sampling_rate_hz: int = 20,
               num_joints: int = 5,
               print_status: bool = True,
               print_debug: bool = False):

    # Initialize any state that the sensor needs.
    self._sampling_rate_hz = sampling_rate_hz
    self._num_joints = num_joints
    self._master_device = master_device
    self._device_mapping = device_mapping
    self._packet = OrderedDict([(id, None) for name, id in self._device_mapping.items()])

    stream_info = {
      "num_joints": self._num_joints,
      "sampling_rate_hz": self._sampling_rate_hz,
      "device_mapping": device_mapping
    }

    # Abstract class will call concrete implementation's creation methods
    #   to build the data structure of the sensor
    super().__init__(port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     stream_info=stream_info,
                     print_status=print_status, 
                     print_debug=print_debug)


  # Factory class method called inside superclass's constructor to instantiate corresponding Stream object.
  def create_stream(cls, stream_info: dict) -> DotsStream:
    return DotsStream(**stream_info)


  # Connect to the sensor.
  def connect(self) -> bool:
    self._handler = MovellaFacade(device_mapping=self._device_mapping, 
                                  master_device=self._master_device,
                                  sampling_rate_hz=self._sampling_rate_hz)
    # Keep reconnecting until success
    while not self._handler.initialize(): 
      self._handler.cleanup()
    return True


  # Loop until self._running is False.
  # Acquire data from your sensor as desired, and for each timestep.
  # SDK thread pushes data into shared memory space, this thread does pulls data and does all the processing,
  #   ensuring that lost packets are responsibility of the slow consumer.
  def run(self) -> None:
    super().run()
    try:
      while self._running:
        poll_res: tuple[list[zmq.SyncSocket], list[int]] = tuple(zip(*(self._poller.poll())))
        if not poll_res: continue

        if self._pub in poll_res[0]:
          if self._handler.is_packets_available():
            self._process_data()
        
        if self._killsig in poll_res[0]:
          self._running = False
          print("quitting %s"%self._log_source_tag, flush=True)
          self._killsig.recv_multipart()
          self._poller.unregister(self._killsig)
      self.quit()
    # Catch keyboard interrupts and other exceptions when module testing, for a clean exit
    except Exception as _:
      self.quit()


  def _process_data(self) -> None:
    time_s: float = time.time()
    # Retrieve the oldest enqueued packet for each sensor 
    for packet in self._handler.get_next_packet():
      device_id: str = str(packet.deviceId())
      euler = packet.orientationEuler()
      acc = packet.freeAcceleration()
      self._packet[device_id] = {
        'timestamp': packet.sampleTimeFine(),
        'counter': packet.packetCounter(),
        'acceleration': (acc[0], acc[1], acc[2]),
        'orientation': (euler.x(), euler.y(), euler.z()),
      }

    acceleration = np.array([v['acceleration'] for (_,v) in self._packet.items()])
    orientation = np.array([v['orientation'] for (_,v) in self._packet.items()])
    timestamp = np.array([v['timestamp'] for (_,v) in self._packet.items()])
    counter = np.array([v['counter'] for (_,v) in self._packet.items()])

    # Store the captured data into the data structure.
    self._stream.append_data(time_s=time_s, acceleration=acceleration, orientation=orientation, timestamp=timestamp, counter=counter)

    # Get serialized object to send over ZeroMQ.
    msg = serialize(time_s=time_s, acceleration=acceleration, orientation=orientation, timestamp=timestamp, counter=counter)

    # Send the data packet on the PUB socket.
    self._pub.send_multipart([("%s.data" % self._log_source_tag).encode('utf-8'), msg])


  # Clean up and quit
  def quit(self) -> None:
    self._handler.cleanup()
    super().quit()


#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  device_mapping = {
    'knee_right'  : '40195BFC800B01F2',
    'foot_right'  : '40195BFC800B003B',
    'pelvis'      : '40195BFD80C20052',
    'knee_left'   : '40195BFC800B017A',
    'foot_left'   : '40195BFD80C200D1',
  }
  master_device = 'pelvis' # wireless dot relaying messages, must match a key in the `device_mapping`

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

  streamer = DotsStreamer(device_mapping=device_mapping, 
                          master_device=master_device,
                          port_pub=port_backend,
                          port_sync=port_sync,
                          port_killsig=port_killsig,
                          sampling_rate_hz=20,
                          num_joints=5)

  streamer()
