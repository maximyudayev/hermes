import queue
from threading import Lock
from typing import Callable
import numpy as np
import xsensdeviceapi as xda
from collections import OrderedDict
import time
import copy

class AwindaDataCallback(xda.XsCallback):
  def __init__(self,
               on_all_packets_received: Callable[[float, list[object], list[object]], None]):
    super().__init__()
    self._on_all_packets_received = on_all_packets_received

  # How are interpolated packets for previous time steps provided?
  def onAllLiveDataAvailable(self, devices, packets):
    time_s: float = time.time()
    self._on_all_packets_received(time_s, devices, packets)


class AwindaConnectivityCallback(xda.XsCallback):
  def __init__(self,
               on_wireless_device_connected: Callable[[object], None]):
    super().__init__()
    self._on_wireless_device_connected = on_wireless_device_connected
  
  def onConnectivityChanged(self, dev, newState):
    # TODO: add additional logic in case devices disconnect, etc.
    if newState == xda.XCS_Wireless:
      self._on_wireless_device_connected(dev)


class XsensFacade:
  def __init__(self,
               device_mapping: dict[str, str],
               radio_channel: int,
               sampling_rate_hz: int,
               buffer_size: int = 100) -> None:
    # Queue used to synchronize current main thread and callback handler thread listening 
    #   to device connections when all expected devices connected before continuing
    self._is_all_connected_queue = queue.Queue(maxsize=1)
    self._device_connection_status = dict.fromkeys(list(device_mapping.values()), False)
    self._radio_channel = radio_channel
    self._sampling_rate_hz = sampling_rate_hz
    self._lock = Lock()
    self._buffer_size = buffer_size
    self._packet_buffer = queue.Queue(maxsize=buffer_size) # buffer of dictionaries -> has to be dictionary of buffers for onLiveDataAvailable + on_each_packet_received

  def initialize(self) -> bool:
    self._control = xda.XsControl.construct()
    port_info_array = xda.XsScanner.scanPorts()

    # Open the detected devices and pick the Awinda station
    try:
      master_port_info = next((port for port in port_info_array if port.deviceId().isWirelessMaster()))
    except Exception as _:
      return False

    if not self._control.openPort(master_port_info.portName(), master_port_info.baudrate()):
      return False
    
    # Get the device object
    self._master_device = self._control.device(master_port_info.deviceId())
    if not self._master_device:
      return False

    def on_wireless_device_connected(dev) -> None:
      device_id: str = str(dev.deviceId())
      self._device_connection_status[device_id] = True
      print(f"Device {device_id} connected...")
      if all(self._device_connection_status.values()): self._is_all_connected_queue.put(True)

    def on_all_packets_received(time_s, devices, packets) -> None:
      #self._lock.acquire()
      #while len(self._packet_buffer.queue) >= self._buffer_size:
      #  self._packet_buffer.get()
      '''  
      snapshot = OrderedDict([("time_s", time_s),
                              ("devices", devices), 
                              ("packets", copy.deepcopy(packets))])

      self._packet_buffer.put(snapshot)
      '''    
      packet_list = []
      #print(len(packets))
      flag_missing_data = False
      for idx, packet in enumerate(packets):
        if not packet.containsFreeAcceleration():
          continue
        
        acc = packet.freeAcceleration()
        euler = packet.orientationEuler()
        # Pick which timestamp information to use (also for DOTs)
        counter: np.uint16 = packet.packetCounter()
        timestamp = packet.utcTime()
        finetime: np.uint32 = packet.sampleTimeFine()
        timestamp_estimate = packet.estimatedTimeOfSampling()
        timestamp_arrival = packet.timeOfArrival()
        packet_list.append((str(packet.deviceId()),{
        "acceleration": (acc[0], acc[1], acc[2]),
        "orientation": (euler.x(), euler.y(), euler.z()),
        "counter": counter,
        "timestamp": finetime
        }))
      snapshot = OrderedDict([("time_s", time_s),
                              ("devices", devices), 
                              ("packets", packet_list)])
      
      self._packet_buffer.put(snapshot)
      #self._lock.release()

    # Register event handler on the main device
    self._conn_callback = AwindaConnectivityCallback(on_wireless_device_connected=on_wireless_device_connected)
    self._master_device.addCallbackHandler(self._conn_callback)
    
    # Enable radio to accept connections from the sensors
    if self._master_device.isRadioEnabled():
      if not self._master_device.disableRadio():
        return False
    if not self._master_device.enableRadio(self._radio_channel):
      return False
    
    # Will block the current thread until the Awinda onConnectivityChanged has changed to XCS_Wireless for all expected devices
    self._is_all_connected_queue.get()
    print("All Awindas connected")

    # Set sample rate
    if not self._master_device.setUpdateRate(self._sampling_rate_hz):
      return False

    # TODO: figure out how to request desired output configs
    # config_array = xda.XsOutputConfigurationArray()
    # # For data that accompanies every packet (timestamp, status, etc.), the selected sample rate will be ignored
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_PacketCounter, 0)) 
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_UtcTime, 0))
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_SampleTimeFine, 0))
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_Acceleration, self._sampling_rate_hz))
    # config_array.push_back(xda.XsOutputConfiguration(xda.XDI_EulerAngles, self._sampling_rate_hz))
    # if not self._master_device.setOutputConfiguration(config_array):
    #   raise RuntimeError("Could not configure the device. Aborting.")

    # Listen to new data for the full kit snapshot
    self._data_callback = AwindaDataCallback(on_all_packets_received=on_all_packets_received)
    self._master_device.addCallbackHandler(self._data_callback)

    # Put all devices connected to the Awinda station into measurement
    # NOTE: Will begin trigerring the callback and saving data, while awaiting the SYNC signal from the Broker
    self._master_device.gotoMeasurement()
    return True

  # Must be called after `packetsAvailable()`
  def get_next_snapshot(self):
    #self._lock.acquire()
    oldest_packet = self._packet_buffer.get()
    #self._lock.release()
    return oldest_packet

  def is_packets_available(self) -> bool:
    return self._packet_buffer.queue

  def cleanup(self) -> None:
    self._control.close()
