from streamers.SensorStreamer import SensorStreamer
from streams.DotsStream import DotsStream

import numpy as np
import time
from collections import OrderedDict

from utils.msgpack_utils import serialize
from handlers.MovellaFacade import MovellaFacade

################################################
################################################
# A class for streaming Dots IMU data.
################################################
################################################
class DotsStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'dots'

  ########################
  ###### INITIALIZE ######
  ########################
  
  # Initialize the sensor streamer.
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

    # Initialize any state that your sensor needs.
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


  ######################################
  ###### INTERFACE IMPLEMENTATION ######
  ######################################

  # Factory class method called inside superclass's constructor to instantiate corresponding Stream object.
  def create_stream(cls, stream_info: dict) -> DotsStream:
    return DotsStream(**stream_info)

  # Connect to the sensor.
  def connect(self) -> True:
    timeout_s = 10

    self._handler = None

    # DOTs backend is annoying and doesn't always connect/discover devices from first try, 
    #   loop until success of all steps, start over if any step fails.
    while True:
      if self._handler is not None: self._handler.cleanup()
      time.sleep(5)
      self._handler = MovellaFacade()

      # Initialize SDK
      if not self._handler.initialize():
        self._handler.cleanup()
        continue

      # Scan for DOTs until all expected devices are found
      self._handler.scanForDots(timeout_s)
      if len(self._handler.detectedDots()) == 0:
        # self._log_error("No Movella DOT device(s) found. Aborting.")
        continue
      elif len(self._handler.detectedDots()) < self._num_joints:
        # self._log_error("Not all %s requested Movella DOT device(s) found. Aborting." % self._num_joints)
        continue

      # Connect to all discovered expected DOTs, attempt several times before starting over
      if not self._handler.connectDots(device_mapping=self._device_mapping, master_device=self._master_device, connectAttempts=10):
        continue

      # Make sure all connected devices have the same filter profile and output rate
      for device_id, device in self._handler.connectedDots().items():
        if device.setOnboardFilterProfile("General"):
          print("Successfully set profile to General for joint %s." % device_id)
          pass
        else:
          print("Setting filter profile for joint %s failed!" % device_id)
          continue

        if device.setOutputRate(self._sampling_rate_hz):
          print(f"Successfully set output rate for joint {device_id} to {self._sampling_rate_hz} Hz.")
          pass
        else:
          print("Setting output rate for joint %s failed!" % device_id)
          continue

      # Call facade sync function, not directly the backend manager proxy
      if not self._handler.sync(syncAttempts=3):
        continue

      print('Successfully connected to the dots streamer.')

      # Set dots to streaming mode and break out of the loop if successful
      if self._handler.stream(): break
    
    return True


  # Loop until self._running is False.
  # Acquire data from your sensor as desired, and for each timestep.
  def run(self) -> None:
    while self._running:
      if self._handler.packetsAvailable():
        time_s: float = time.time()
        for device_id, device in self._handler.connectedDots().items():
          # Retrieve a packet
          packet = self._handler.getNextPacket(device.portInfo().bluetoothAddress())
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
        self._pub.send_multipart(["%s.data"%self._log_source_tag, msg])


  # Clean up and quit
  def quit(self) -> None:
    for device in self._handler.connectedDots(): device.stopMeasurement()
    self._handler.manager().stopSync()
    self._handler.manager().close()
    super().quit()


if __name__ == "__main__":
  import zmq

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
