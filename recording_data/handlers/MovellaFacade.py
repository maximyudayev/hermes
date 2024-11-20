#  Copyright (c) 2003-2023 Movella Technologies B.V. or subsidiaries worldwide.
#  All rights reserved.
#  
#  Redistribution and use in source and binary forms, with or without modification,
#  are permitted provided that the following conditions are met:
#  
#  1.	Redistributions of source code must retain the above copyright notice,
#  	this list of conditions and the following disclaimer.
#  
#  2.	Redistributions in binary form must reproduce the above copyright notice,
#  	this list of conditions and the following disclaimer in the documentation
#  	and/or other materials provided with the distribution.
#  
#  3.	Neither the names of the copyright holders nor the names of their contributors
#  	may be used to endorse or promote products derived from this software without
#  	specific prior written permission.
#  
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
#  EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
#  THE COPYRIGHT HOLDERS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
#  OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
#  HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY OR
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import movelladot_pc_sdk as mdda
from collections import OrderedDict, defaultdict
from threading import Lock
from utils.user_settings import *
import time

class MovellaFacade(mdda.XsDotCallback):
  def __init__(self, max_buffer_size=5):
    super().__init__()

    self.__manager = 0

    self.__lock = Lock()
    self.__errorReceived = False
    self.__updateDone = False
    self.__recordingStopped = False
    self.__exportDone = False
    self.__closing = False
    self.__progressCurrent = 0
    self.__progressTotal = 0
    self.__packetsReceived = 0

    self.__detectedDots = list()
    self.__connectedDots = dict()
    self.__masterDotId = 0
    self.__maxNumberOfPacketsInBuffer = max_buffer_size
    self.__packetBuffer = defaultdict(list)
    self.__progress = dict()

  def initialize(self):
    """
    Initialize the PC SDK

    - Prints the used PC SDK version to show we connected to XDPC
    - Constructs the connection manager used for discovering and connecting to DOTs
    - Connects this class as callback handler to the XDPC

    Returns:
        False if there was a problem creating a connection manager.
    """

    # Print SDK version
    version = mdda.XsVersion()
    mdda.xsdotsdkDllVersion(version)
    # self._log_debug(f"Using Movella DOT SDK version: {version.toXsString()}")

    # Create connection manager
    self.__manager = mdda.XsDotConnectionManager()
    if self.__manager is None:
      # self._log_error("Movella backend manager could not be constructed, exiting.")
      return False

    # Attach callback handler (self) to connection manager
    self.__manager.addXsDotCallbackHandler(self)
    return True

  def cleanup(self):
    """
    Close connections to any Movella DOT devices and destructs the connection manager created in initialize
    """
    # self._log_debug("Closing Movella backend ports...")
    self.__closing = True
    self.__manager.close()

    # self._log_status("Successful exit Movella backend.")

  def scanForDots(self, timeout_s=20) -> int:
    """
    Scan if any Movella DOT devices can be detected via Bluetooth

    Enables device detection in the connection manager and uses the
    onAdvertisementFound callback to detect active Movella DOT devices
    Disables device detection when done

    """
    # Start a scan and wait until we have found one or more DOT Devices
    # self._log_status("Scanning for devices...")
    self.__manager.enableDeviceDetection()

    connectedDOTCount = 0
    self.__detectedDots = list()
    startTime = mdda.XsTimeStamp_nowMs()
    while not self.errorReceived() and mdda.XsTimeStamp_nowMs() - startTime <= timeout_s*1000:
      time.sleep(0.1)

      nextCount = len(self.detectedDots())
      if nextCount != connectedDOTCount:
        connectedDOTCount = nextCount

    self.__manager.disableDeviceDetection()
    # self._log_status("Stopped scanning for devices.")
    return connectedDOTCount

  def connectDots(self, device_mapping: dict[str, str], master_device: str, connectAttempts=2) -> bool:
    """
    Connects to Movella DOTs found via either USB or Bluetooth connection

    Uses the isBluetooth function of the XsPortInfo to determine if the device was detected
    via Bluetooth or via USB. Then connects to the device accordingly
    When using Bluetooth, a retry has been built in, since wireless connection sometimes just fails the 1st time
    Connected devices can be retrieved using either connectedDots() or connectedUsbDots()

    USB and Bluetooth devices should not be mixed in the same session!
    """
    self.setMasterDot(device_mapping[master_device])
    self.__connectedDots = OrderedDict([(v, None) for v in device_mapping.values()])
    for portInfo in self.detectedDots():
      if portInfo.isBluetooth():
        address = portInfo.bluetoothAddress()
        attempts = 0
        connected = False
        # self._log_debug(f"Opening DOT with address: @ {address}")
        while not connected and attempts < connectAttempts:
          attempts += 1
          connected = self.__manager.openPort(portInfo)
          if not connected: print(f"Connection to {address} failed. Retrying {attempts}/{connectAttempts}. Reason: {self.__manager.lastResultText()}.")

        if not connected:
          print(f"Could not connect to {address}.")
          return False

        device = self.__manager.device(portInfo.deviceId())
        if device is None:
          return False

        # self._log_debug(f"Found a device with Tag: {device.deviceTagName()} @ address: {address}")
        self.__connectedDots[str(portInfo.deviceId())] = device
    # Return success if all devices were instantiated by the SDK
    return all(self.__connectedDots.values())

  def setMasterDot(self, dotId):
    self.__masterDotId = dotId

  def sync(self, syncAttempts=1) -> bool:
    if len(self.connectedDots()) == 1:
      # self._log_debug("Only 1 DOT device connected, sync not needed...")
      return True
    else:
      attempts = 0
      while attempts < syncAttempts:
        if self.__manager.startSync(self.__connectedDots[self.__masterDotId].bluetoothAddress()):
          return True
        else:
          attempts += 1
          self.__manager.stopSync()
      return False

  def stream(self) -> bool:
    # Start live data output. Make sure root node is last to go to measurement.
    # self._log_status("Putting devices into measurement mode.")
    for joint, device in [*[(device_id, device) for device_id, device in self.__connectedDots.items() if device_id != self.__masterDotId], (self.__masterDotId, self.__connectedDots[self.__masterDotId])]:
      if not device.startMeasurement(mdda.XsPayloadMode_ExtendedEuler):
        # self._log_error(f"Could not put {device.bluetoothAddress()} into measurement mode. Reason: {device.lastResultText()}")
        return False
      time.sleep(1)
    # self._log_debug("Successfully put all devices into measurement mode.")
    # self._log_debug("Resetting device headings, don't move the sensors.")
    time.sleep(5)
    for joint, device in [*[(device_id, device) for device_id, device in self.__connectedDots.items() if device_id != self.__masterDotId], (self.__masterDotId, self.__connectedDots[self.__masterDotId])]:
      # self._log_debug(f"Resetting heading for device {device.bluetoothAddress()}: ")
      if not device.resetOrientation(mdda.XRM_Heading):
        return False
      time.sleep(1)
    
    return True

  def manager(self):
    """
    Returns:
          A pointer to the XsDotConnectionManager
    """
    return self.__manager

  def detectedDots(self):
    """
    Returns:
          An XsPortInfoArray containing information on detected Movella DOT devices
    """
    return self.__detectedDots

  def connectedDots(self):
    """
    Returns:
        A list containing an XsDotDevice pointer for each Movella DOT device connected via Bluetooth
    """
    return self.__connectedDots
  
  def masterDot(self):
    return self.__masterDotId

  def errorReceived(self):
    """
    Returns:
          True if an error was received through the onError callback
    """
    return self.__errorReceived

  def exportDone(self):
    """
    True if the export has finished
    """
    return self.__exportDone

  def updateDone(self):
    """
    Returns:
          Whether update done was received through the onDeviceUpdateDone callback
    """
    return self.__updateDone

  def resetUpdateDone(self):
    """
    Resets the update done member variable to be ready for a next device update
    """
    self.__updateDone = False

  def recordingStopped(self):
    """
    Returns:
          True if the device indicated the recording has stopped
    """
    return self.__recordingStopped

  def resetRecordingStopped(self):
    """
    Resets the recording stopped member variable to be ready for a next recording
    """
    self.__recordingStopped = False

  def packetsAvailable(self):
    """
    Returns:
          True if a data packet is available for each of the connected Movella DOT devices
    """
    for device_id, device in self.__connectedDots.items():
      if self.packetAvailable(device.bluetoothAddress()) == 0:
        return False
    return True

  def packetAvailable(self, bluetoothAddress):
    """
    Parameters:
        bluetoothAddress: The bluetooth address of the Movella DOT to check for a ready data packet
    Returns:
        True if a data packet is available for the Movella DOT with the provided bluetoothAddress
    """
    self.__lock.acquire()
    res = len(self.__packetBuffer[bluetoothAddress]) > 0
    self.__lock.release()
    return res

  def packetsReceived(self):
    """
    Returns:
          The number of packets received during data export
    """
    return self.__packetsReceived

  def getNextPacket(self, bluetoothAddress):
    """
    Parameters:
        bluetoothAddress: The bluetooth address of the Movella DOT to get the next packet for
    Returns:
          The next available data packet for the Movella DOT with the provided bluetoothAddress
    """
    if len(self.__packetBuffer[bluetoothAddress]) == 0:
      return None
    self.__lock.acquire()
    oldest_packet = mdda.XsDataPacket(self.__packetBuffer[bluetoothAddress].pop(0))
    self.__lock.release()
    return oldest_packet

  def addDeviceToProgressBuffer(self, bluetoothAddress):
    """
    Initialize internal progress buffer for an Movella DOT device

    Parameters:
        bluetoothAddress: The bluetooth address of the Movella DOT
    """
    self.__progress[bluetoothAddress] = 0

  def progress(self):
    """
    Returns:
          The current progress indication of the connected Movella DOT devices
    """
    return self.__progress

  def _outputDeviceProgress(self):
    """
    Helper function for printing file export info to the command line.
    """
    line = '\rExporting... '
    if self.__exportDone:
      line += 'done!'
    elif self.__progressTotal != 0xffff:
      line += '{:.1f}%'.format(100.0 * self.__progressCurrent / self.__progressTotal)
    else:
      line += f'{self.__progressCurrent}'
    if self.__exportDone:
      print(line)
    else:
      print(line, end='', flush=True)

  ##############################
  ##### Callback Overrides #####
  ##############################
  def onAdvertisementFound(self, port_info):
    """
    Called when an Movella DOT device advertisement was received. Updates m_detectedDots.
    Parameters:
        port_info: The XsPortInfo of the discovered information
    """
    if not whitelist or port_info.bluetoothAddress() in whitelist:
      self.__detectedDots.append(port_info)
    else:
      # print(f"Ignoring {port_info.bluetoothAddress()}")
      pass

  def onBatteryUpdated(self, device, batteryLevel, chargingStatus):
    """
    Called when a battery status update is available. Prints to screen.
    Parameters:
        device: The device that initiated the callback. This may be 0 in some cases
        batteryLevel: The battery level in percentage
        chargingStatus: The charging status of the battery. 0: Not charging, 1: charging
    """
    # print(device.deviceTagName() + f" BatteryLevel: {batteryLevel} Charging status: {chargingStatus}")
    pass

  def onError(self, result, errorString):
    """
    Called when an internal error has occurred. Prints to screen.
    Parameters:
        result: The XsResultValue related to this error
        errorString: The error string with information on the problem that occurred
    """
    # print(f"{mdda.XsResultValueToString(result)}")
    # print(f"Error received: {errorString}")
    self.__errorReceived = True

  def onLiveDataAvailable(self, device, packet):
    """
    Called when new data has been received from a device
    Adds the new packet to the device's packet buffer
    Monitors buffer size, removes oldest packets if the size gets too big

    Parameters:
        device: The device that initiated the callback.
        packet: The data packet that has been received (and processed).
    """
    self.__lock.acquire()
    while len(self.__packetBuffer[device.portInfo().bluetoothAddress()]) >= self.__maxNumberOfPacketsInBuffer:
      self.__packetBuffer[device.portInfo().bluetoothAddress()].pop()
    self.__packetBuffer[device.portInfo().bluetoothAddress()].append(mdda.XsDataPacket(packet))
    self.__lock.release()

  def onProgressUpdated(self, device, current, total, identifier):
    """
    Called when a long-duration operation has made some progress or has completed.
    When device is an XsDotUsbDevice, the progress applies to data export progress
    When device is an XsDotDevice, the progress applies to OTA and Magnetic Field Mapping progress
    Parameters:
        device: The device that initiated the callback.
        current: The current progress.
        total: The total work to be done. When current equals total, the task is completed.
        identifier: An identifier for the task. This may for example be a filename for file read operations.
    """
    if isinstance(device, mdda.XsDotUsbDevice):
      self.__progressCurrent = current
      self.__progressTotal = total
      self._outputDeviceProgress()
    else:
      address = device.bluetoothAddress()
      if address not in self.__progress:
        self.__progress[address] = current
      if current > self.__progress[address]:
        self.__progress[address] = current
        # if identifier:
        #   print(f"\rUpdate: {current} Total: {total} Remark: {identifier}", end="", flush=True)
        # else:
        #   print(f"\rUpdate: {current} Total: {total}", end="", flush=True)

  def onDeviceUpdateDone(self, portInfo, result):
    """
    Called when the firmware update process has completed. Prints to screen.
    Parameters:
        portInfo: The XsPortInfo of the updated device
        result: The XsDotFirmwareUpdateResult of the firmware update
    """
    # print(f"\n{portInfo.bluetoothAddress()}  Firmware Update done. Result: {mdda.XsDotFirmwareUpdateResultToString(result)}")
    self.__updateDone = True

  def onRecordingStopped(self, device):
    """
    Called when a recording has stopped. Prints to screen.
    Parameters:
        device: The device that initiated the callback.
    """
    # print(f"\n{device.deviceTagName()} Recording stopped")
    self.__recordingStopped = True

  def onDeviceStateChanged(self, updatedDevice, newState, oldState):
    """
    Called when the device state has changed.
    Used for removing/disconnecting the device when it indicates a power down.
    Parameters:
        device: The device that initiated the callback.
        newState: The new device state.
        oldState: The old device state.
    """
    if newState == mdda.XDS_Destructing and not self.__closing:
      # print(f"\n{updatedDevice.deviceTagName()} Device powered down")
      for device_id, device in self.__connectedDots:
        if device.bluetoothAddress() == updatedDevice.bluetoothAddress():
          del self.__connectedDots[device_id]

  def onButtonClicked(self, device, timestamp):
    """
    Called when the device's button has been clicked. Prints to screen.
    Parameters:
        device: The device that initiated the callback.
        timestamp: The timestamp at which the button was clicked
    """
    # print(f"\n{device.deviceTagName()} Button clicked at {timestamp}")
    pass

  def onRecordedDataAvailable(self, device, packet):
    """
    Called when new data has been received from a device that is exporting a recording

    The callback rate will be as fast as the data comes in and not necessarily reflect real-time. For
    timing information, please refer to the SampletimeFine which is available when the Timestamp field is exported.
    Parameters:
        device: The device that initiated the callback.
        packet: The data packet that has been received.
    """
    self.__packetsReceived += 1

  def onRecordedDataDone(self, device):
    """
    Called when a device that is exporting a recording is finished with exporting.

    This callback will occur in any sitation that stops the export of the recording, such as
    the export being completed, the export being stopped by request or an internal failure.
    Parameters:
        device: The device that initiated the callback.
    """
    self.__exportDone = True
    self._outputDeviceProgress()
