from handlers.BaslerHandler import ImageEventHandler
from streamers import SensorStreamer
from streams import CameraStream
from utils.msgpack_utils import serialize

import pypylon.pylon as pylon

from utils.print_utils import *

################################################
################################################
# A class for streaming videos from USB cameras.
################################################
################################################
class CameraStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'cameras'

  ########################
  ###### INITIALIZE ######
  ########################
  
  # Initialize the sensor streamer.
  def __init__(self,
               port_pub: str | None = None,
               port_sync: str | None = None,
               port_killsig: str | None = None,
               cameras_to_stream: dict = {}, # a dict mapping camera names to device indexes
               fps: float = 30.0,
               log_history_filepath: str | None = None,
               print_status: bool = True,
               print_debug: bool = False):

    # Initialize general state.
    self._cameras_to_stream = cameras_to_stream

    stream_info = {
      "cameras_to_stream": cameras_to_stream,
      "fps": fps
    }

    super(CameraStreamer, self).__init__(self,
                                         port_pub=port_pub,
                                         port_sync=port_sync,
                                         port_killsig=port_killsig,
                                         stream_info=stream_info,
                                         log_history_filepath=log_history_filepath,
                                         print_status=print_status,
                                         print_debug=print_debug)

  ######################################
  ###### INTERFACE IMPLEMENTATION ######
  ######################################

  # Factory class method called inside superclass's constructor to instantiate corresponding Stream object.
  def create_stream(cls, stream_info: dict | None = None) -> CameraStream:
    return CameraStream(**stream_info)

  # Connect to the sensor.
  # TODO: if running background grab loop for multiple cameras impacts bandwidth, switch to per-process instantiation for each camera
  #   In this case, use each entry of the camera names dictionary to use filters on the device info objects for enumeration
  def connect(self):
    tlf: pylon.TlFactory = pylon.TlFactory.GetInstance()
    # Get Transport Layer for just the GigE Basler cameras
    self._tl: pylon.TransportLayer = tlf.CreateTl(pylon.TLTypeGigE)

    # di = pylon.DeviceInfo()
    # di.SetUserDefinedName("")
    # di.SetSerialNumber("")
    # self._cam = pylon.InstantCamera(tlf.CreateDevice(di))

    # Filter discovered cameras by user-defined serial numbers
    devices: list[pylon.DeviceInfo] = [d for d in self._tl.EnumerateDevices() if d.GetSerialNumber() in self._cameras_to_stream.values()]

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
      # TODO: Preload persistent feature configurations saved to a file (easier configuration of all cameras)
      # pylon.FeaturePersistence().Load("", cam.GetNodeMap())
      # Assign an ID to each grabbed frame, corresponding to the host device
      cam.SetCameraContext(idx)
      #####################################################
      # https://github.com/basler/pypylon/issues/482
      # Enable PTP
      cam.GevIEEE1588.SetValue(True)
      # Make sure the frame trigger is set to Off to enable free run
      cam.TriggerSelector.SetValue('FrameStart')
      cam.TriggerMode.SetValue('Off')
      # Let the free run start immediately without a specific start time
      cam.SyncFreeRunTimerStartTimeLow.SetValue(0)
      cam.SyncFreeRunTimerStartTimeHigh.SetValue(0)
      # Set the trigger rate to 10 frames per second
      cam.SyncFreeRunTimerTriggerRateAbs.SetValue(10)
      # Apply the changes
      cam.SyncFreeRunTimerUpdate.Execute()
      # Start the synchronous free run
      cam.SyncFreeRunTimerEnable.SetValue(True)
      ######################################################

  # Register background grab loop with a callback responsible for sending frames over ZeroMQ
  def run(self):
    def callback(frame: np.ndarray, camera_id: int, timestamp: np.uint64, sequence_id: np.int64) -> None:
      time_s = time.time()
      # Store the data.
      self._stream.append_data(time_s=time_s, frame=frame, timestamp=timestamp, sequence_id=sequence_id)

      # Get serialized object to send over ZeroMQ.
      msg = serialize(time_s=time_s, frame=frame, timestamp=timestamp, sequence_id=sequence_id)

      # Send the data packet on the PUB socket.
      self._pub.send_multipart([b"%s.%s.data"%(self._log_source_tag, camera_id), msg])
    
    # Instantiate callback handler
    handler = ImageEventHandler(callback)
    # Register with the pylon loop
    self._cam_array.RegisterImageEventHandler(handler, pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_None)

    # Fetch some images with background loop
    # TODO: how will this interact with the synchronous free running in the `connect`
    self._cam_array.StartGrabbing(pylon.GrabStrategy_LatestImages, pylon.GrabLoop_ProvidedByInstantCamera)
    
    # While background process reads-out news frames can do something useful
    #   like poll for commands from the Broker to terminate
    while self._cam_array.IsGrabbing():
      # TODO:
      pass
    
    # Stop capturing data
    self._cam_array.StopGrabbing()
    # Remove background loop event listener
    self._cam_array.DeregisterCameraEventHandler()  

  # Clean up and quit
  def quit(self):
    # Stop capturing data
    self._cam_array.StopGrabbing()
    # Remove background loop event listener
    self._cam_array.DeregisterCameraEventHandler()
    # Disconnect from the camera
    self._cam_array.Close()
