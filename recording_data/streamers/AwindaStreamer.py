from streamers.SensorStreamer import SensorStreamer
from streams.AwindaStream import AwindaStream

import numpy as np
import time
from collections import OrderedDict
import zmq

from utils.msgpack_utils import serialize
from handlers.XsensHandler import XsensFacade

#######################################
#######################################
# A class for streaming Awinda IMU data
#######################################
#######################################
class AwindaStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'awinda'

  def __init__(self, 
               device_mapping: dict[str, str],
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               sampling_rate_hz: int = 100,
               num_joints: int = 7,
               radio_channel: int = 15,
               print_status: bool = True, 
               print_debug: bool = False):

    self._num_joints = num_joints
    self._sampling_rate_hz = sampling_rate_hz
    self._radio_channel = radio_channel
    self._device_mapping = device_mapping

    joint_names, device_ids = tuple(zip(*(self._device_mapping.items())))
    self._packet = OrderedDict(zip(device_ids, [{}]*len(joint_names)))

    stream_info = {
      "num_joints": self._num_joints,
      "sampling_rate_hz": self._sampling_rate_hz,
      "device_mapping": self._device_mapping
    }

    super().__init__(port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     stream_info=stream_info,
                     print_status=print_status, 
                     print_debug=print_debug)


  def create_stream(self, stream_info: dict) -> AwindaStream:  
    return AwindaStream(**stream_info)


  def connect(self) -> bool:
    self._handler = XsensFacade(device_mapping=self._device_mapping,
                                radio_channel=self._radio_channel,
                                sampling_rate_hz=self._sampling_rate_hz)
    # Keep reconnecting until success
    while not self._handler.initialize(): 
      self._handler.cleanup()

    return True


  # Acquire data from the sensors until signalled externally to quit
  def run(self) -> None:
    super().run()
    try:
      while self._running:
        poll_res: tuple[list[zmq.SyncSocket], list[int]] = tuple(zip(*(self._poller.poll())))
        if not poll_res: continue

        if self._pub in poll_res[0]:
          if self._handler.is_packets_available():
            self._process_all_data()
        
        if self._killsig in poll_res[0]:
          self._running = False
          print("quitting %s"%self._log_source_tag, flush=True)
          self._killsig.recv_multipart()
          self._poller.unregister(self._killsig)
      self.quit()
    # Catch keyboard interrupts and other exceptions when module testing, for a clean exit
    except Exception as _:
      self.quit()


  def _process_all_data(self) -> None:
    time_s = time.time()
    # TODO: validate if contents are ever array of arrays of packets (i.e. multiple timesteps for lost interpolated data)
    snapshot = self._handler.get_next_snapshot()
    time_s = snapshot['time_s']
    for packet in snapshot['packets']:
      acc = packet.freeAcceleration()
      euler = packet.orientationEuler()

      # Pick which timestamp information to use (also for DOTs)
      counter: np.uint16 = packet.packetCounter()
      timestamp = packet.utcTime()
      finetime: np.uint32 = packet.sampleTimeFine()
      timestamp_estimate = packet.estimatedTimeOfSampling()
      timestamp_arrival = packet.timeOfArrival()

      self._packet[str(packet.deviceId())] = {
        "acceleration": (acc[0], acc[1], acc[2]),
        "orientation": (euler.x(), euler.y(), euler.z()),
        "counter": counter,
        "timestamp": finetime
      }

    acceleration = np.array([v['acceleration'] for v in self._packet.values()])
    orientation = np.array([v['orientation'] for v in self._packet.values()])
    counter = np.array([v['counter'] for v in self._packet.values()])
    timestamp = np.array([v['timestamp'] for v in self._packet.values()])

    # Store the captured data into the data structure.
    # self._stream.append_data(time_s=time_s, acceleration=acceleration, orientation=orientation, timestamp=timestamp, counter=counter)
    # Get serialized object to send over ZeroMQ.
    msg = serialize(time_s=time_s, acceleration=acceleration, orientation=orientation, timestamp=timestamp, counter=counter)
    # Send the data packet on the PUB socket.
    self._pub.send_multipart([("%s.data" % self._log_source_tag).encode('utf-8'), msg])


  # Clean up and quit
  def quit(self) -> None:
    # Clean up the SDK
    self._control.close()
    self._control.destruct()
    super().quit()


#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  device_mapping = {
    'pelvis'         : '00B4D3E4',
    'upper_leg_right': '00B4D3D7',
    'lower_leg_right': '00B4D3E2',
    'foot_right'     : '00B4D3DD',
    'upper_leg_left' : '00B4D3E7',
    'lower_leg_left' : '00B4D3D4',
    'foot_left'      : '00B4D3D8',
  }
  num_joints = 7
  sampling_rate_hz = 100
  radio_channel = 15

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

  streamer = AwindaStreamer(device_mapping=device_mapping, 
                            port_pub=port_backend,
                            port_sync=port_sync,
                            port_killsig=port_killsig,
                            sampling_rate_hz=sampling_rate_hz,
                            num_joints=num_joints,
                            radio_channel=radio_channel)

  streamer()
