from producers import Producer
from streams import DotsStream

from handlers.MovellaHandler import MovellaFacade
from utils.zmq_utils import *

import numpy as np
import time
from collections import OrderedDict
import zmq


######################################
######################################
# A class for streaming Dots IMU data.
######################################
######################################
class DotsStreamer(Producer):
  @property
  def _log_source_tag(self) -> str:
    return 'dots'


  def __init__(self,
               logging_spec: dict,
               device_mapping: dict[str, str],
               master_device: str,
               sampling_rate_hz: int = 20,
               num_joints: int = 5,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               print_status: bool = True,
               print_debug: bool = False,
               **_):

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
    super().__init__(stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status, 
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict) -> DotsStream:
    return DotsStream(**stream_info)


  def _connect(self) -> bool:
    self._handler = MovellaFacade(device_mapping=self._device_mapping, 
                                  master_device=self._master_device,
                                  sampling_rate_hz=self._sampling_rate_hz)
    # Keep reconnecting until success
    while not self._handler.initialize(): 
      self._handler.cleanup()
    return True


  def _process_data(self) -> None:
    # Stamps full-body snapshot with system time of start of processing, not time-of-arrival.
    # NOTE: time-of-arrival available with each packet.
    process_time_s: float = time.time()
    # Retrieve the oldest enqueued packet for each sensor.
    snapshot = self._handler.get_snapshot()
    if snapshot:
      for device, packet in snapshot.items():
        if packet:
          acc = packet["acc"]
          gyr = packet["gyr"]
          mag = packet["mag"]
          quaternion = packet["quaternion"]
          timestamp_fine: np.uint32 = packet["timestamp_fine"]
          counter: np.uint16 = packet["counter"]
        else:
          acc = (None, None, None)
          gyr = (None, None, None)
          mag = (None, None, None)
          quaternion = (None, None, None, None)
          timestamp_fine = None
          counter = None

        self._packet[device] = {
          "acceleration": acc,
          "gyroscope": gyr,
          "magnetometer": mag,
          "orientation": quaternion,
          "timestamp": timestamp_fine,
          "counter": counter,
        }

      acceleration = np.array([v['acceleration'] for v in self._packet.values()])
      gyroscope = np.array([v['gyroscope'] for v in self._packet.values()])
      magnetometer = np.array([v['magnetometer'] for v in self._packet.values()])
      orientation = np.array([v['orientation'] for v in self._packet.values()])
      timestamp = np.array([v['timestamp'] for v in self._packet.values()])
      counter = np.array([v['counter'] for v in self._packet.values()])

      data = {
        'acceleration-x': acceleration[:,0],
        'acceleration-y': acceleration[:,1],
        'acceleration-z': acceleration[:,2],
        'gyroscope-x': gyroscope[:,0],
        'gyroscope-y': gyroscope[:,1],
        'gyroscope-z': gyroscope[:,2],
        'magnetometer-x': magnetometer[:,0],
        'magnetometer-y': magnetometer[:,1],
        'magnetometer-z': magnetometer[:,2],
        'orientation': orientation,
        'timestamp': timestamp,
        'counter': counter,
      }

      tag: str = "%s.data" % self._log_source_tag
      self._publish(tag, time_s=process_time_s, data={'dots-imu': data})
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
    'knee_right'  : '40195BFC800B01F2',
    'foot_right'  : '40195BFC800B003B',
    'pelvis'      : '40195BFD80C20052',
    'knee_left'   : '40195BFC800B017A',
    'foot_left'   : '40195BFD80C200D1',
  }
  master_device = 'pelvis' # wireless dot relaying messages, must match a key in the `device_mapping`

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

  streamer = DotsStreamer(device_mapping=device_mapping, 
                          master_device=master_device,
                          port_pub=port_backend,
                          port_sync=port_sync,
                          port_killsig=port_killsig,
                          sampling_rate_hz=20,
                          num_joints=5)

  streamer()
