from producers.Producer import Producer
from streams.AwindaStream import AwindaStream

import numpy as np
import time
from collections import OrderedDict
import zmq

from handlers.XsensHandler import XsensFacade
from utils.zmq_utils import *


########################################
########################################
# A class for streaming Awinda IMU data.
########################################
########################################
class AwindaStreamer(Producer):
  @property
  def _log_source_tag(self) -> str:
    return 'awinda'


  def __init__(self, 
               device_mapping: dict[str, str],
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               sampling_rate_hz: int = 100,
               num_joints: int = 7,
               radio_channel: int = 15,
               print_status: bool = True, 
               print_debug: bool = False,
               **_):

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


  def _connect(self) -> bool:
    self._handler = XsensFacade(device_mapping=self._device_mapping,
                                radio_channel=self._radio_channel,
                                sampling_rate_hz=self._sampling_rate_hz)
    # Keep reconnecting until success
    while not self._handler.initialize(): 
      self._handler.cleanup()
    return True


  def _process_data(self) -> None:
    process_time_s = time.time()
    snapshot = self._handler.get_snapshot()
    if snapshot:
      for device, packet in snapshot.items():
        if packet:
          acc = packet["acc"]
          quaternion = packet["quaternion"]

          # Pick which timestamp information to use (also for DOTs)
          counter: np.uint16 = packet["counter"]
          toa_s: float = packet["toa_s"] # TODO: use the average clock of the valid samples in a snapshot
          timestamp_fine: np.uint32 = packet["timestamp_fine"]
        else:
          acc = (None, None, None)
          quaternion = (None, None, None)
          counter = None
          timestamp_fine = None

        self._packet[device] = {
          "acceleration": acc,
          "orientation": quaternion,
          "counter": counter,
          "timestamp": timestamp_fine
        }

      acceleration = np.array([v['acceleration'] for v in self._packet.values()])
      orientation = np.array([v['orientation'] for v in self._packet.values()])
      counter = np.array([v['counter'] for v in self._packet.values()])
      timestamp = np.array([v['timestamp'] for v in self._packet.values()])

      data = {
        'acceleration-x': acceleration[:,0],
        'acceleration-y': acceleration[:,1],
        'acceleration-z': acceleration[:,2],
        'orientation': orientation,
        'timestamp': timestamp,
        'counter': counter
      }

      tag: str = "%s.data" % self._log_source_tag
      self._publish(tag, time_s=process_time_s, data={'awinda-imu': data})
    elif not self._is_continue_capture:
      # If triggered to stop and no more available data, send empty 'END' packet and join.
      self._send_end_packet()


  def _stop_new_data(self):
    self._handler.cleanup()


  def _cleanup(self) -> None:
    super()._cleanup()


# TODO: update the unit test.
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

  ip = IP_LOOPBACK
  port_backend = PORT_BACKEND
  port_frontend = PORT_FRONTEND
  port_sync = PORT_SYNC
  port_killsig = PORT_KILL

  # Pass exactly one ZeroMQ context instance throughout the program
  ctx: zmq.Context = zmq.Context()

  # Exposes a known address and port to locally connected sensors to connect to.
  local_backend: zmq.SyncSocket = ctx.socket(zmq.XSUB)
  local_backend.bind("tcp://%s:%s" % (IP_LOOPBACK, port_backend))
  backends: list[zmq.SyncSocket] = [local_backend]

  # Exposes a known address and port to broker data to local workers.
  local_frontend: zmq.SyncSocket = ctx.socket(zmq.XPUB)
  local_frontend.bind("tcp://%s:%s" % (IP_LOOPBACK, port_frontend))
  frontends: list[zmq.SyncSocket] = [local_frontend]

  streamer = AwindaStreamer(device_mapping=device_mapping, 
                            port_pub=port_backend,
                            port_sync=port_sync,
                            port_killsig=port_killsig,
                            sampling_rate_hz=sampling_rate_hz,
                            num_joints=num_joints,
                            radio_channel=radio_channel)

  streamer()
