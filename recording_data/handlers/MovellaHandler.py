import queue
from threading import Lock
from typing import Callable
import movelladot_pc_sdk as mdda
from collections import OrderedDict
from utils.user_settings import *
import time


class DotCallback(mdda.XsDotCallback):
  def __init__(self,
               on_advertisement_found: Callable,
               on_device_disconnected: Callable,
               on_packet_received: Callable):
    super().__init__()
    self._on_advertisement_found = on_advertisement_found
    self._on_device_disconnected = on_device_disconnected
    self._on_packet_received = on_packet_received

  def onAdvertisementFound(self, portInfo):
    self._on_advertisement_found(portInfo)

  def onLiveDataAvailable(self, device, packet):
    time_s: float = time.time()
    self._on_packet_received(device, packet)

  def onDeviceStateChanged(self, device, newState, oldState):
    if newState == mdda.XDS_Destructing:
      self._on_device_disconnected(device)

  def onError(self, result, error):
    print(error)


class MovellaFacade:
  def __init__(self, 
               device_mapping: dict[str, str], 
               master_device: str,
               sampling_rate_hz: int,
               buffer_size: int = 5) -> None:
    self._is_all_connected_queue = queue.Queue(maxsize=1)
    self._connected_devices = OrderedDict([(v, None) for v in device_mapping.values()])
    self._packet_buffer = OrderedDict([(v, queue.Queue(maxsize=buffer_size)) for v in device_mapping.values()]) # dictionary of buffers
    self._lock = Lock() # TODO: Use a smarter multi-threaded data sharing strategy than locking all the packet buffers

    self._buffer_size = buffer_size
    self._master_device_id = master_device
    self._sampling_rate_hz = sampling_rate_hz

  def initialize(self) -> bool:
    # Create connection manager
    self._manager = mdda.XsDotConnectionManager()
    if self._manager is None:
      return False

    def on_advertisement_found(portInfo) -> None:
      if not portInfo.isBluetooth(): return
      if not self._manager.openPort(portInfo): 
        print("failed to connect to %s"%portInfo.bluetoothAddress())
      device = self._manager.device(portInfo.deviceId())
      device_id: str = str(portInfo.deviceId())
      self._connected_devices[device_id] = device
      if all(self._connected_devices.values()): self._is_all_connected_queue.put(True)

    def on_packet_received(device, packet):
      # TODO: actually, no guarantee that DOTs won't drift from each other if some are consumed slower
      device_id: str = str(device.deviceId())
      self._lock.acquire()
      while len(self._packet_buffer[device_id]) >= self._buffer_size:
        self._packet_buffer[device_id].pop()
      self._packet_buffer[device_id].append(packet)
      self._lock.release()

    def on_device_disconnected(device):
      device_id: str = str(device.deviceId())
      self._connected_devices[device_id] = None

    # Attach callback handler to connection manager
    self._callback = DotCallback(on_advertisement_found=on_advertisement_found,
                                 on_packet_received=on_packet_received,
                                 on_device_disconnected=on_device_disconnected)
    self._manager.addXsDotCallbackHandler(self._callback)

    # Start a scan and wait until we have found all devices
    self._manager.enableDeviceDetection()
    self._is_all_connected_queue.get()
    self._manager.disableDeviceDetection()

    # Make sure all connected devices have the same filter profile and output rate
    for device_id, device in self._connected_devices.items():
      if not device.setOnboardFilterProfile("General"):
        return False
      if not device.setOutputRate(self._sampling_rate_hz):
        return False

    # Call facade sync function, not directly the backend manager proxy
    if not self._sync(attempts=3):
      return False

    # Set dots to streaming mode and break out of the loop if successful
    return self._stream()

  def _sync(self, attempts=1) -> bool:
    while attempts > 0:
      if self._manager.startSync(self._connected_devices[self._master_device_id].bluetoothAddress()):
        return True
      else:
        attempts -= 1
        self._manager.stopSync()
    return False

  def _stream(self) -> bool:
    # Start live data output. Make sure root node is last to go to measurement.
    ordered_device_list: list[tuple[str, object]] = [*[(device_id, device) for device_id, device in self._connected_devices.items() if device_id != self._master_device_id], 
     (self._master_device_id, self._connected_devices[self._master_device_id])]

    for (joint, device) in ordered_device_list:
      if not device.startMeasurement(mdda.XsPayloadMode_ExtendedEuler):
        return False
    for (joint, device) in ordered_device_list:
      if not device.resetOrientation(mdda.XRM_Heading):
        return False
    return True

  def is_packets_available(self) -> bool:
    for device_id, device in self._connected_devices.items():
      if self.is_packet_available(device_id) == 0:
        return False
    return True

  def is_packet_available(self, device_id: str) -> bool:
    self._lock.acquire()
    res = len(self._packet_buffer[device_id]) > 0
    self._lock.release()
    return res

  # Must be called after `packetsAvailable()`
  def get_next_packet(self):
    for device_id in self._connected_devices.keys():
      self._lock.acquire()
      oldest_packet = self._packet_buffer[device_id].pop(0)
      self._lock.release()
      yield oldest_packet

  def cleanup(self) -> None:
    for device in self._connected_devices.values():
      if device is not None:
        device.stopMeasurement()
    self._manager.stopSync()
    self._manager.close()
