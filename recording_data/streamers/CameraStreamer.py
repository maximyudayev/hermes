from collections import OrderedDict

import zmq
from handlers.BaslerHandler import ImageEventHandler
from streamers.SensorStreamer import SensorStreamer
from streams.CameraStream import CameraStream
from utils.msgpack_utils import serialize

import pypylon.pylon as pylon

from utils.print_utils import *

###############################################
###############################################
# A class for streaming videos from USB cameras
###############################################
###############################################
class CameraStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'cameras'

  def __init__(self,
               camera_mapping: dict[str, str], # a dict mapping camera names to device indexes
               fps: float,
               resolution: tuple[int],
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               camera_config_filepath: str = None, # path to the pylon .pfs config file to reproduce desired camera setup
               print_status: bool = True,
               print_debug: bool = False):

    # Initialize general state.
    camera_names, camera_ids = tuple(zip(*(camera_mapping.items())))
    self._camera_mapping = OrderedDict[str, str] = OrderedDict(zip(camera_ids, camera_names))

    self._camera_config_filepath = camera_config_filepath

    stream_info = {
      "camera_mapping": camera_mapping,
      "fps": fps,
      "resolution": resolution
    }

    super().__init__(port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     stream_info=stream_info,
                     print_status=print_status,
                     print_debug=print_debug)


  # Factory class method called inside superclass's constructor to instantiate corresponding Stream object.
  def create_stream(cls, stream_info: dict) -> CameraStream:
    return CameraStream(**stream_info)


  # Connect to the sensor.
  # NOTE: if running background grab loop for multiple cameras impacts bandwidth, switch to per-process instantiation for each camera
  #   In this case, use each entry of the camera names dictionary to use filters on the device info objects for enumeration
  def connect(self) -> bool:
    tlf: pylon.TlFactory = pylon.TlFactory.GetInstance()
    fp: pylon.FeaturePersistence = pylon.FeaturePersistence()

    # Get Transport Layer for just the GigE Basler cameras
    self._tl: pylon.TransportLayer = tlf.CreateTl(pylon.TLTypeGigE)
    # di = pylon.DeviceInfo()
    # di.SetUserDefinedName("")
    # di.SetSerialNumber("")
    # self._cam = pylon.InstantCamera(tlf.CreateDevice(di))

    # Filter discovered cameras by user-defined serial numbers
    devices: list[pylon.DeviceInfo] = [d for d in self._tl.EnumerateDevices() if d.GetSerialNumber() in self._camera_mapping.values()]

    # Instantiate cameras
    self._cam_array: pylon.InstantCameraArray = pylon.InstantCameraArray(len(devices))
    for idx, cam in enumerate(self._cam_array):
      cam.Attach(self._tl.CreateDevice(devices[idx]))

    # Connect to the cameras
    self._cam_array.Open()

    # Configure the cameras according to the user settings
    for idx, cam in enumerate(self._cam_array):
      # For consistency factory reset the devices
      cam.UserSetSelector = "Default"
      cam.UserSetLoad.Execute()

      # Preload persistent feature configurations saved to a file (easier configuration of all cameras)
      if self._camera_config_filepath is not None: 
        fp.Load(self._camera_config_filepath, cam.GetNodeMap())
      
      # Assign an ID to each grabbed frame, corresponding to the host device
      cam.SetCameraContext(idx)
      
      # Enable PTP to sync cameras between each other for Synchronous Free Running at the specified frame rate
      cam.PtpEnable.SetValue(True)
      
      # Verify status is no longer "Initializing"
      while cam.PtpStatus.GetValue() != "Initializing":
        time.sleep(1)

      # Verify that the slave device are sufficiently synchronized
      while cam.PtpServoStatus.GetValue() != "Locked":
        # Execute clock latch 
        cam.PtpDataSetLatch.Execute()
        time.sleep(1)

    # Instantiate callback handler
    self._image_handler = ImageEventHandler(cam_array=self._cam_array)

    return True
      #####################################################
      # https://github.com/basler/pypylon/issues/482
      # Make sure the frame trigger is set to Off to enable free run
      # cam.TriggerSelector.SetValue('FrameStart')
      # cam.TriggerMode.SetValue('Off')
      # # Let the free run start immediately without a specific start time
      # cam.SyncFreeRunTimerStartTimeLow.SetValue(0)
      # cam.SyncFreeRunTimerStartTimeHigh.SetValue(0)
      # # Set the trigger rate to 10 frames per second
      # cam.SyncFreeRunTimerTriggerRateAbs.SetValue(10)
      # # Apply the changes
      # cam.SyncFreeRunTimerUpdate.Execute()
      # # Start the synchronous free run
      # cam.SyncFreeRunTimerEnable.SetValue(True)
      ######################################################

  # Register background grab loop with a callback responsible for sending frames over ZeroMQ
  def run(self) -> None:
    super().run()
    
    
    
    

    # Fetch some images with background loop
    self._cam_array.StartGrabbing(pylon.GrabStrategy_LatestImages, pylon.GrabLoop_ProvidedByInstantCamera)
    
    # While background process reads-out new frames, can do something useful
    #   like poll for commands from the Broker to terminate
    super().run()
    try:
      while self._running:
        poll_res: tuple[list[zmq.SyncSocket], list[int]] = tuple(zip(*(self._poller.poll())))
        if not poll_res: continue

        if self._pub in poll_res[0]:
          if self._handler.is_packets_available():
            self._process_data()
        
        if self._killsig in poll_res[0]:
          self._running = False
          print("quitting %s"%self._log_source_tag, flush=True)
          self._killsig.recv_multipart()
          self._poller.unregister(self._killsig)
      self.quit()
    # Catch keyboard interrupts and other exceptions when module testing, for a clean exit
    except Exception as _:
      self.quit()
 

  def _process_data(self):
    time_s = time.time()
    # Store the data.
    self._stream.append_data(device_id=camera_id, time_s=time_s, frame=frame, timestamp=timestamp, sequence_id=sequence_id)

    # Get serialized object to send over ZeroMQ.
    msg = serialize(device_id=camera_id, time_s=time_s, frame=frame, timestamp=timestamp, sequence_id=sequence_id)

    # Send the data packet on the PUB socket.
    self._pub.send_multipart(["%s.%s.data"%(self._log_source_tag, self._camera_mapping[camera_id]), msg])


  # Clean up and quit
  def quit(self) -> None:
    # Stop capturing data
    self._cam_array.StopGrabbing()
    # Remove background loop event listener
    self._cam_array.DeregisterCameraEventHandler(self._image_handler)
    # Disconnect from the camera
    self._cam_array.Close()
    super().quit()
