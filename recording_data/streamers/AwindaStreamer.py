from collections import OrderedDict
import queue

import numpy as np

from streamers.SensorStreamer import SensorStreamer
from streams.AwindaStream import AwindaStream

from utils.msgpack_utils import serialize
from utils.print_utils import *

from handlers.AwindaCallback import AwindaConnectivityCallback, AwindaDataCallback
import xsensdeviceapi as xda

import zmq

################################################
################################################
# A class for streaming Awinda IMU data.
################################################
################################################
class AwindaStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'awinda'

  ########################
  ###### INITIALIZE ######
  ########################

  def __init__(self, 
               device_mapping: dict[str, str],
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               sampling_rate_hz: int = 100,
               num_joints: int = 7,
               radio_channel: int = 15,
               queue_size: int = 0,
               print_status: bool = True, 
               print_debug: bool = False):

    self._num_joints = num_joints
    self._sampling_rate_hz = sampling_rate_hz
    self._radio_channel = radio_channel
    self._queue_size = queue_size
    self._device_mapping = device_mapping

    joint_names, device_ids = tuple(zip(*(self._device_mapping.items())))
    self._packet = OrderedDict(zip(device_ids, [{}]*len(joint_names)))

    stream_info = {
      "num_joints": self._num_joints,
      "sampling_rate_hz": self._sampling_rate_hz,
      "device_mapping": self._device_mapping
    }

    super(AwindaStreamer, self).__init__(self, 
                                         port_pub=port_pub,
                                         port_sync=port_sync,
                                         port_killsig=port_killsig,
                                         stream_info=stream_info,
                                         print_status=print_status, 
                                         print_debug=print_debug)

  def create_stream(self, stream_info: dict) -> AwindaStream:  
    return AwindaStream(**stream_info)


  def connect(self) -> None:
    self._control = xda.XsControl.construct()
    port_info_array = xda.XsScanner.scanPorts()

    # Open the detected devices and pick the Awinda station
    master_port_info = next((port for port in port_info_array if port.deviceId().isWirelessMaster()))

    if not self._control.openPort(master_port_info.portName(), master_port_info.baudrate()):
      raise RuntimeError(f"Failed to open port {master_port_info}")
    
    # Get the device object
    self._master_device = self._control.device(master_port_info.deviceId())
    if not self._master_device:
      raise RuntimeError(f"Failed to construct XsDevice instance: {master_port_info}")

    # NOTE: if sending data over the socket throttles the callback thread,
    #   only put packets into shared queue object and have the parent thread do this instead
    def process_packet(time_s: float, dev: xda.XsDevice, packet: xda.XsPacket) -> None:
      counter: np.uint16 = packet.packetCounter()
      acc = packet.freeAcceleration()
      euler = packet.orientationEuler()
      acceleration = np.array((acc[0], acc[1], acc[2]))
      orientation = np.array((euler.x(), euler.y(), euler.z()))

      # Pick which timestamp information to use (also for DOTs)
      timestamp: xda.XsTimeInfo = packet.utcTime()
      finetime: np.uint32 = packet.sampleTimeFine()
      timestamp_estimate: xda.XsTimeStamp = packet.estimatedTimeOfSampling()
      timestamp_arrival: xda.XsTimeStamp = packet.timeOfArrival()

      # Store the captured data into the data structure.
      device_id: str = str(dev.deviceId())
      self._stream.append_data(time_s=time_s, device_id=device_id, acceleration=acceleration, orientation=orientation, timestamp=finetime, counter=counter)
      # Get serialized object to send over ZeroMQ.
      msg = serialize(time_s=time_s, device_id=device_id, acceleration=acceleration, orientation=orientation, timestamp=finetime, counter=counter)
      # Send the data packet on the PUB socket.
      self._pub.send_multipart(["%s.%s" % (self._log_source_tag, device_id), msg])

    def process_all_packets(time_s: float, devices: list[xda.XsDevice], packets: list[xda.XsPacket]) -> None:
      for dev, packet in zip(devices, packets):
        acc = packet.freeAcceleration()
        euler = packet.orientationEuler()

        # Pick which timestamp information to use (also for DOTs)
        counter: np.uint16 = packet.packetCounter()
        timestamp: xda.XsTimeInfo = packet.utcTime()
        finetime: np.uint32 = packet.sampleTimeFine()
        timestamp_estimate: xda.XsTimeStamp = packet.estimatedTimeOfSampling()
        timestamp_arrival: xda.XsTimeStamp = packet.timeOfArrival()

        self._packet[str(dev.deviceId())] = {
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
      self._stream.append_data(time_s=time_s, acceleration=acceleration, orientation=orientation, timestamp=timestamp, counter=counter)
      # Get serialized object to send over ZeroMQ.
      msg = serialize(time_s=time_s, acceleration=acceleration, orientation=orientation, timestamp=timestamp, counter=counter)
      # Send the data packet on the PUB socket.
      self._pub.send_multipart(["%s.data" % self._log_source_tag, msg])

    # Queue used to synchronize current main thread and callback handler thread listening 
    #   to device connections when all expected devices connected before continuing
    connection_sync_queue = queue.Queue(maxsize=1)
    device_connection_status = dict.fromkeys(list(self._device_mapping.values()), False)
    def mark_device_connected(dev: xda.XsDevice) -> None:
      id: str = str(dev.deviceId())
      device_connection_status[id] = True
      if all(list(device_connection_status.values())): connection_sync_queue.put(True)

    # Register event handler on the main device
    self._conn_handler = AwindaConnectivityCallback(on_wireless_device_connected=mark_device_connected)
    self._master_device.addCallbackHandler(self._conn_handler)
    # Enable radio to accept connections from the sensors
    if self._master_device.isRadioEnabled():
      if not self._master_device.disableRadio():
        raise RuntimeError(f"Failed to disable radio channel: {self._master_device}")
    if not self._master_device.enableRadio(self._radio_channel):
      raise RuntimeError(f"Failed to set radio channel: {self._master_device}")
    
    # Set sample rate
    if not self._master_device.setUpdateRate(self._sampling_rate_hz):
      raise RuntimeError("Could not configure the device. Aborting.")
    
    # config_array = xda.XsOutputConfigurationArray()
    # # For data that accompanies every packet (timestamp, status, etc.), the selected sample rate will be ignored
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_PacketCounter, 0)) 
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_UtcTime, 0))
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_SampleTimeFine, 0))
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_Acceleration, self._sampling_rate_hz))
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_EulerAngles, self._sampling_rate_hz))
    
    # if not self._master_device.setOutputConfiguration(config_array):
    #   raise RuntimeError("Could not configure the device. Aborting.")

    # Will block the current thread until the Awinda onConnectivityChanged has changed to XCS_Wireless for all expected devices
    connection_sync_queue.get()

    self._data_handler = AwindaDataCallback(on_packet_received=process_all_packets)
    self._master_device.addCallbackHandler(self._data_handler)
    # Put all devices connected to the Awinda station into measurement
    # NOTE: Will begin trigerring the callback and saving data, while awaiting the SYNC signal from the Broker
    self._master_device.gotoMeasurement()


  # Acquire data from the sensors until signalled externally to quit
  def run(self) -> None:
    # While background process reads-out new data, can do something useful
    #   like poll for commands from the Broker to terminate, and block on the Queue 
    while self._running:
      poll_res: tuple[list[zmq.SyncSocket], list[int]] = tuple(zip(*(self._poller.poll())))
      if not poll_res: continue
      if self._killsig in poll_res[0]:
        print("quitting publisher", flush=True)
        self._killsig.recv_multipart()
        self._poller.unregister(self._killsig)
        self._running = False

  
  # Clean up and quit
  def quit(self) -> None:
    # Clean up the SDK
    self._control.close()
    self._control.destruct()
    
    super(AwindaStreamer, self).quit(self)


#####################
###### TESTING ######
#####################
