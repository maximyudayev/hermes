import time
from typing import Callable
import xsensdeviceapi as xda


class AwindaDataCallback(xda.XsCallback):
  def __init__(self,
               on_all_packets_received: Callable[[float, list[xda.XsDevice], list[xda.XsDataPacket]], None]):
    super().__init__()
    self._on_all_packets_received = on_all_packets_received

  # def onLiveDataAvailable(self, dev: xda.XsDevice, packet: xda.XsDataPacket):
  #   print("Live data...")
  #   time_s: float = time.time()
  #   self._on_packet_received(time_s, dev, packet)

  # How are interpolated packets for previous time steps provided?
  def onAllLiveDataAvailable(self, devices, packets):
    time_s: float = time.time()
    self._on_all_packets_received(time_s, devices, packets)

  def onError(self, dev: xda.XsDevice, error):
    print(xda.XsResultValueToString(error))


class AwindaConnectivityCallback(xda.XsCallback):
  def __init__(self,
               on_wireless_device_connected: Callable[[xda.XsDevice], None]):
    super().__init__()
    self._on_wireless_device_connected = on_wireless_device_connected

  def onConnectivityChanged(self, dev: xda.XsDevice, newState):
    # TODO: add additional logic in case devices disconnect, etc.
    if newState == xda.XCS_Wireless:
      self._on_wireless_device_connected(dev)
