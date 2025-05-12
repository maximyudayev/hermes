############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Created 2024-2025 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Maxim Yudayev [https://yudayev.com].
#
# ############

import queue
import threading
from typing import Any, Callable, Iterable, Mapping, TypedDict
import movelladot_pc_sdk as mdda
from collections import OrderedDict

import numpy as np

from utils.datastructures import TimestampAlignedFifoBuffer
from utils.user_settings import *
from utils.time_utils import get_time

MovellaDataGetter = TypedDict('MovellaDataGetter', {'func': Callable[[mdda.XsDataPacket], Any], 'n_dim': int, 'dtype': type, 'type_str': str})
MovellaPayloadTuple = TypedDict('MovellaPayloadTuple', {'num_bytes': int, 'payload_mode': Any, 'methods': Mapping[str, MovellaDataGetter]})

MOVELLA_DATA_GET_METHODS = {
  "acceleration":         MovellaDataGetter(func=lambda packet: packet.calibratedAcceleration(),  n_dim=3, dtype=np.float32, type_str='float32'),
  "gyroscope":            MovellaDataGetter(func=lambda packet: packet.calibratedGyroscopeData(), n_dim=3, dtype=np.float32, type_str='float32'),
  "magnetometer":         MovellaDataGetter(func=lambda packet: packet.calibratedMagneticField(), n_dim=3, dtype=np.float32, type_str='float32'),
  "quaternion":           MovellaDataGetter(func=lambda packet: packet.orientationQuaternion(),   n_dim=4, dtype=np.float32, type_str='float32'),
  "euler":                MovellaDataGetter(func=lambda packet: packet.orientationEuler(),        n_dim=3, dtype=np.float32, type_str='float32'),
  "free_acceleration":    MovellaDataGetter(func=lambda packet: packet.freeAcceleration(),        n_dim=3, dtype=np.float32, type_str='float32'),
  "dq":                   MovellaDataGetter(func=lambda packet: packet.orientationIncrement(),    n_dim=4, dtype=np.float32, type_str='float32'),
  "dv":                   MovellaDataGetter(func=lambda packet: packet.velocityIncrement(),       n_dim=3, dtype=np.float32, type_str='float32'),
  "status":               MovellaDataGetter(func=lambda packet: packet.status(),                  n_dim=1, dtype=np.uint16,  type_str='unit32'),
}

foo: Callable[[Iterable[str]], Mapping[str, MovellaDataGetter]] = lambda l: {k:v for k,v in MOVELLA_DATA_GET_METHODS.items() if k in l}

MOVELLA_PAYLOAD_MODE = {
  "ExtendedQuaternion":     MovellaPayloadTuple(num_bytes=36, payload_mode=mdda.XsPayloadMode_ExtendedQuaternion,    methods=foo(["quaternion",
                                                                                                                                  "free_acceleration",
                                                                                                                                  "status"])),
  "CompleteQuaternion":     MovellaPayloadTuple(num_bytes=32, payload_mode=mdda.XsPayloadMode_CompleteQuaternion,    methods=foo(["quaternion",
                                                                                                                                  "free_acceleration"])),
  "ExtendedEuler":          MovellaPayloadTuple(num_bytes=32, payload_mode=mdda.XsPayloadMode_ExtendedEuler,         methods=foo(["euler",
                                                                                                                                  "free_acceleration",
                                                                                                                                  "status"])),
  "CompleteEuler":          MovellaPayloadTuple(num_bytes=28, payload_mode=mdda.XsPayloadMode_CompleteEuler,         methods=foo(["quaternion",
                                                                                                                                  "free_acceleration"])),
  "OrientationQuaternion":  MovellaPayloadTuple(num_bytes=20, payload_mode=mdda.XsPayloadMode_OrientationQuaternion, methods=foo(["quaternion"])),
  "OrientationEuler":       MovellaPayloadTuple(num_bytes=16, payload_mode=mdda.XsPayloadMode_OrientationEuler,      methods=foo(["euler"])),
  "FreeAcceleration":       MovellaPayloadTuple(num_bytes=16, payload_mode=mdda.XsPayloadMode_FreeAcceleration,      methods=foo(["free_acceleration"])),
  "MFM":                    MovellaPayloadTuple(num_bytes=16, payload_mode=mdda.XsPayloadMode_MFM,                   methods=foo(["magnetometer"])),
  "RateQuantitieswMag":     MovellaPayloadTuple(num_bytes=34, payload_mode=mdda.XsPayloadMode_RateQuantitieswMag,    methods=foo(["acceleration",
                                                                                                                                  "gyroscope",
                                                                                                                                  "magnetometer"])),
  "RateQuantities":         MovellaPayloadTuple(num_bytes=28, payload_mode=mdda.XsPayloadMode_RateQuantities,        methods=foo(["acceleration",
                                                                                                                                  "gyroscope"])),
  "DeltaQuantitieswMag":    MovellaPayloadTuple(num_bytes=38, payload_mode=mdda.XsPayloadMode_DeltaQuantitieswMag,   methods=foo(["dq",
                                                                                                                                  "dv",
                                                                                                                                  "magnetometer"])),
  "DeltaQuantities":        MovellaPayloadTuple(num_bytes=32, payload_mode=mdda.XsPayloadMode_DeltaQuantities,       methods=foo(["dq",
                                                                                                                                  "dv"])),
  "HighFidelitywMag":       MovellaPayloadTuple(num_bytes=35, payload_mode=mdda.XsPayloadMode_HighFidelitywMag,      methods=foo(["acceleration",
                                                                                                                                  "gyroscope",
                                                                                                                                  "magnetometer"])),
  "HighFidelity":           MovellaPayloadTuple(num_bytes=29, payload_mode=mdda.XsPayloadMode_HighFidelity,          methods=foo(["acceleration",
                                                                                                                                  "gyroscope"])),
  "CustomMode1":            MovellaPayloadTuple(num_bytes=40, payload_mode=mdda.XsPayloadMode_CustomMode1,           methods=foo(["euler",
                                                                                                                                  "free_acceleration",
                                                                                                                                  "gyroscope"])),
  "CustomMode2":            MovellaPayloadTuple(num_bytes=34, payload_mode=mdda.XsPayloadMode_CustomMode2,           methods=foo(["euler",
                                                                                                                                  "free_acceleration",
                                                                                                                                  "magnetometer"])),
  "CustomMode3":            MovellaPayloadTuple(num_bytes=32, payload_mode=mdda.XsPayloadMode_CustomMode3,           methods=foo(["quaternion",
                                                                                                                                  "gyroscope"])),
  "CustomMode4":            MovellaPayloadTuple(num_bytes=51, payload_mode=mdda.XsPayloadMode_CustomMode4,           methods=foo(["quaternion",
                                                                                                                                  "acceleration",
                                                                                                                                  "gyroscope",
                                                                                                                                  "magnetometer",
                                                                                                                                  "status"])),
  "CustomMode5":            MovellaPayloadTuple(num_bytes=44, payload_mode=mdda.XsPayloadMode_CustomMode5,           methods=foo(["quaternion",
                                                                                                                                  "acceleration",
                                                                                                                                  "gyroscope"])),
}

MOVELLA_PAYLOAD_MODE["ExtendedQuaternion"]["methods"]
# NOTE: Movella sets different internal low-pass filter for different activities:
#         'General' - general human daily activities.
#         'Dynamic' - high-pace activities (e.g. sprints).
MOVELLA_LOGGING_MODE = {
  "Euler":        mdda.XsLogOptions_Euler,
  "Quaternion":   mdda.XsLogOptions_Quaternion
}
MOVELLA_STATUS_MASK = {
  0x0001: "Accelerometer out of range in x-axis",
  0x0002: "Accelerometer out of range in y-axis",
  0x0004: "Accelerometer out of range in z-axis",
  0x0008: "Gyroscope out of range in x-axis",
  0x0010: "Gyroscope out of range in y-axis",
  0x0020: "Gyroscope out of range in z-axis",
  0x0040: "Magnetometer out of range in x-axis",
  0x0080: "Magnetometer out of range in y-axis",
  0x0100: "Magnetometer out of range in z-axis",
}


class DotDataCallback(mdda.XsDotCallback):
  def __init__(self,
               on_packet_received: Callable[[float, Any, Any], None]):
    super().__init__()
    self._on_packet_received = on_packet_received


  def onLiveDataAvailable(self, device, packet):
    self._on_packet_received(get_time(), device, packet)


class DotConnectivityCallback(mdda.XsDotCallback):
  def __init__(self,
               on_advertisement_found: Callable,
               on_device_disconnected: Callable):
    super().__init__()
    self._on_advertisement_found = on_advertisement_found
    self._on_device_disconnected = on_device_disconnected


  def onAdvertisementFound(self, port_info):
    self._on_advertisement_found(port_info)


  def onDeviceStateChanged(self, device, new_state, old_state):
    if new_state == mdda.XDS_Destructing:
      self._on_device_disconnected(device)


  def onError(self, result, error):
    print(error)


class MovellaFacade:
  def __init__(self,
               device_mapping: dict[str, str],
               master_device: str,
               sampling_rate_hz: int,
               payload_mode: str = 'RateQuantitieswMag',
               logging_mode: str = 'Euler',
               filter_profile: str = 'General',
               is_sync_devices: bool = True,
               is_enable_logging: bool = False,
               timesteps_before_stale: int = 100) -> None:
    self._is_all_discovered_queue = queue.Queue(maxsize=1)
    self._device_mapping = device_mapping
    self._discovered_devices = list()
    self._connected_devices: OrderedDict[str, Any] = OrderedDict([(v, None) for v in device_mapping.values()])
    sampling_period = round(1/sampling_rate_hz * 10000)
    self._buffer = TimestampAlignedFifoBuffer(keys=device_mapping.values(),
                                              timesteps_before_stale=timesteps_before_stale,
                                              sampling_period=sampling_period,
                                              num_bits_timestamp=32)
    self._packet_queue = queue.Queue()
    self._master_device_id = device_mapping[master_device]
    self._sampling_rate_hz = sampling_rate_hz
    self._is_sync_devices = is_sync_devices
    self._is_enable_logging = is_enable_logging
    self._is_keep_data = False
    self._filter_profile = filter_profile
    self._payload_mode = MOVELLA_PAYLOAD_MODE[payload_mode]
    self._logging_mode = MOVELLA_LOGGING_MODE[logging_mode]


  def initialize(self) -> bool:
    self._is_more = True
    # Create connection manager
    self._manager = mdda.XsDotConnectionManager()
    if self._manager is None:
      return False

    def on_advertisement_found(port_info) -> None:
      if not port_info.isBluetooth(): return
      self._discovered_devices.append(port_info)
      if len(self._discovered_devices) == len(self._device_mapping): self._is_all_discovered_queue.put(True)
      print("discovered %s"%port_info.bluetoothAddress(), flush=True)

    def on_packet_received(toa_s, device, packet):
      if self._is_keep_data:
        device_id: str = str(device.deviceId())
        timestamp = packet.sampleTimeFine()
        data = dict([("device_id", device_id),
                     ("timestamp", timestamp),
                     ("toa_s", toa_s)])
        for data_name, data_getter in self._payload_mode["methods"].items():
          data[data_name] = data_getter["func"](packet)
        self._packet_queue.put({"key": device_id, "data": data, "timestamp": timestamp})

    def on_device_disconnected(device):
      device_id: str = str(device.deviceId())
      print("%s disconnected"%device_id)
      self._connected_devices[device_id] = None

    # Attach callback handler to connection manager
    self._conn_callback = DotConnectivityCallback(on_advertisement_found=on_advertisement_found,
                                                  on_device_disconnected=on_device_disconnected)
    self._manager.addXsDotCallbackHandler(self._conn_callback)

    # Start a scan and wait until we have found all devices
    self._manager.enableDeviceDetection()
    self._is_all_discovered_queue.get()
    self._manager.disableDeviceDetection()

    for port_info in self._discovered_devices:
      if not self._manager.openPort(port_info): 
        print("failed to connect to %s"%port_info.bluetoothAddress(), flush=True)
        return False
      device = self._manager.device(port_info.deviceId())
      device_id: str = str(port_info.deviceId())
      self._connected_devices[device_id] = device
      print("connected to %s"%port_info.bluetoothAddress(), flush=True)

    # Make sure all connected devices have the same filter profile and output rate
    for device_id, device in self._connected_devices.items():
      if not device.setOnboardFilterProfile(self._filter_profile):
        return False
      if not device.setOutputRate(self._sampling_rate_hz):
        return False

    # Call facade sync function, not directly the backend manager proxy
    if self._is_sync_devices:
      if not self._sync(attempts=3):
        return False

    if self._is_enable_logging:
      for device_id, device in self._connected_devices.items():
        device.setLogOptions(self._logging_mode)
        logFileName = "logfile_" + device.bluetoothAddress().replace(':', '-') + ".csv"
        print(f"Enable logging to: {logFileName}")
        if not device.enableLogging(logFileName):
          print(f"Failed to enable logging. Reason: {device.lastResultText()}")
          return False

    # Set dots to streaming mode and break out of the loop if successful.
    if not self._stream():
      return False

    # Funnels packets from the background thread-facing interleaved Queue of async packets, 
    #   into aligned Deque datastructure.
    def funnel_packets(packet_queue: queue.Queue, timeout: float = 5.0):
      while True:
        try:
          next_packet = packet_queue.get(timeout=timeout)
          self._buffer.plop(**next_packet)
        except queue.Empty:
          if self._is_more:
            continue
          else:
            print("No more packets from Movella SDK, flush buffers into the output Queue.")
            self._buffer.flush()
            break

    self._packet_funneling_thread = threading.Thread(target=funnel_packets, args=(self._packet_queue,))

    self._data_callback = DotDataCallback(on_packet_received=on_packet_received)
    self._manager.addXsDotCallbackHandler(self._data_callback)
    self._packet_funneling_thread.start()

    return True


  def _sync(self, attempts=1) -> bool:
    # NOTE: Syncing may not work on some devices due to poor BT drivers.
    while attempts > 0:
      print(f"{attempts} attempts left to sync DOTs.")
      if self._manager.startSync(self._connected_devices[self._master_device_id].bluetoothAddress()):
        return True
      else:
        attempts -= 1
        self._manager.stopSync()
    return False


  def _stream(self) -> bool:
    # Start live data output. Make sure root node is last to go to measurement.
    # NOTE: orientation reset works only in 'yaw' direction on DOTs -> no reason to use, turn on flat on the table, then attach to body and start program.
    ordered_device_list: list[tuple[str, Any]] = [*[(device_id, device) for device_id, device in self._connected_devices.items()
                                                        if device_id != self._master_device_id], 
                                                    (self._master_device_id, self._connected_devices[self._master_device_id])]
    for (joint, device) in ordered_device_list:
      if not device.startMeasurement(self._payload_mode["payload_mode"]):
        return False
    return True


  def keep_data(self) -> None:
    self._is_keep_data = True


  def get_snapshot(self) -> dict[str, dict | None] | None:
    return self._buffer.yeet()


  def cleanup(self) -> None:
    for device_id, device in self._connected_devices.items():
      if device is not None:
        if not device.stopMeasurement():
          print("Failed to stop measurement.")
        if self._is_enable_logging and not device.disableLogging():
          print("Failed to disable logging.")
        self._connected_devices[device_id] = None
    self._is_more = False
    self._discovered_devices = list()
    if self._is_sync_devices:
      self._manager.stopSync()


  def close(self) -> None:
    self._manager.close()
    self._packet_funneling_thread.join()
