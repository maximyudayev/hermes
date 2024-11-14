import time
from typing import Callable
import xsensdeviceapi as xda

class AwindaDataCallback(xda.XsCallback):
  def __init__(self,
               on_all_packets_received: Callable[[float, list[xda.XsDevice], list[xda.XsDataPacket]], None]):
    super(AwindaDataCallback, self).__init__()
    self._on_all_packets_received = on_all_packets_received

  # How are interpolated packets for previous time steps provided?
  def onAllLiveDataAvailable(self, devices, packets):
    time_s: float = time.time()
    self._on_all_packets_received(time_s, devices, packets)


class AwindaConnectivityCallback(xda.XsCallback):
  def __init__(self,
               on_wireless_device_connected: Callable[[xda.XsDevice], None]):
    super(AwindaConnectivityCallback, self).__init__()
    self._on_wireless_device_connected = on_wireless_device_connected
  
  def onConnectivityChanged(self, dev: xda.XsDevice, newState):
    # TODO: add additional logic in case devices disconnect, etc.
    if newState == xda.XCS_Wireless:
      self._on_wireless_device_connected(dev)
