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
from typing import Callable
import numpy as np
import xsensdeviceapi as xda
import time

from utils.datastructures import CircularBuffer


class AwindaDataCallback(xda.XsCallback):
  def __init__(self,
               on_each_packet_received: Callable[[float, object, object], None]):
    super().__init__()
    self._on_each_packet_received = on_each_packet_received


  # How are interpolated packets for previous time steps provided?
  def onLiveDataAvailable(self, device, packet):
    time_s: float = time.time()
    self._on_each_packet_received(time_s, device, packet)


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
               buffer_size: int = 5) -> None:
    # Queue used to synchronize current main thread and callback handler thread listening 
    #   to device connections when all expected devices connected before continuing
    self._is_all_connected_queue = queue.Queue(maxsize=1)
    self._device_connection_status = dict.fromkeys(list(device_mapping.values()), False)
    self._radio_channel = radio_channel
    self._sampling_rate_hz = sampling_rate_hz
    self._buffer = CircularBuffer(size=buffer_size,
                                  keys=device_mapping.values())


  def initialize(self) -> bool:
    self._is_measuring = True
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
      if all(self._device_connection_status.values()): self._is_all_connected_queue.put(True)

    def on_each_packet_received(toa_s, device, packet) -> None:
      device_id: str = str(device.deviceId())
      acc = packet.calibratedAcceleration()
      gyr = packet.calibratedGyroscopeData()
      mag = packet.calibratedMagneticField()
      quaternion = packet.orientationQuaternion()
      timestamp_fine = packet.sampleTimeFine()
      counter = packet.packetCounter()
      data = {
        "device_id":            device_id,                          # str
        "acc":                  acc,
        "gyr":                  gyr,
        "mag":                  mag,
        "quaternion":           quaternion, 
        "toa_s":                toa_s,                              # float
        "timestamp_fine":       timestamp_fine,                     # uint32
        "counter":              counter,                            # uint16
      }
      self._buffer.plop(key=device_id, data=data, counter=counter)

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

    # Put devices in Config Mode and request desired data and rate
    self._master_device.gotoConfig()
    config_array = xda.XsOutputConfigurationArray()
    # For data that accompanies every packet (timestamp, status, etc.), the selected sample rate will be ignored
    config_array.push_back(xda.XsOutputConfiguration(xda.XDI_PacketCounter, 0)) 
    config_array.push_back(xda.XsOutputConfiguration(xda.XDI_SampleTimeFine, 0))
    config_array.push_back(xda.XsOutputConfiguration(xda.XDI_Acceleration, self._sampling_rate_hz))
    config_array.push_back(xda.XsOutputConfiguration(xda.XDI_RateOfTurn, self._sampling_rate_hz))
    config_array.push_back(xda.XsOutputConfiguration(xda.XDI_MagneticField, self._sampling_rate_hz)) # NOTE: also has XDI_MagneticFieldCorrected
    config_array.push_back(xda.XsOutputConfiguration(xda.XDI_Quaternion, self._sampling_rate_hz))
    
    if not self._master_device.setOutputConfiguration(config_array):
      print("Could not configure the Awinda master device. Aborting.")
      return False

    # Register listener of new data
    self._data_callback = AwindaDataCallback(on_each_packet_received=on_each_packet_received)
    self._master_device.addCallbackHandler(self._data_callback)

    # Put all devices connected to the Awinda station into Measurement Mode
    # NOTE: Will begin trigerring the callback and saving data, while awaiting the SYNC signal from the Broker
    return self._master_device.gotoMeasurement()


  def get_snapshot(self) -> dict[str, dict | None] | None:
    return self._buffer.yeet(is_running=self._is_measuring)


  def cleanup(self) -> None:
    self._control.close()
    self._control.destruct()
    self._is_measuring = False
