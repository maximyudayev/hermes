from collections import OrderedDict

import zmq
from handlers.BaslerHandler import ImageEventHandler
from streamers.SensorStreamer import SensorStreamer
from streams.CameraStream import CameraStream
from utils.msgpack_utils import serialize

import pypylon.pylon as pylon

from utils.print_utils import *

######################################################
######################################################
# A class for streaming videos from Basler PoE cameras
######################################################
######################################################
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
    self._camera_mapping: OrderedDict[str, str] = OrderedDict(zip(camera_ids, camera_names))

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


  # Connect to the cameras
  def connect(self) -> bool:
    tlf: pylon.TlFactory = pylon.TlFactory.GetInstance()

    # Get Transport Layer for just the GigE Basler cameras
    self._tl: pylon.TransportLayer = tlf.CreateTl('BaslerGigE')

    # Filter discovered cameras by user-defined serial numbers
    devices: list[pylon.DeviceInfo] = [d for d in self._tl.EnumerateAllDevices() if d.GetSerialNumber() in self._camera_mapping.keys()]

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
        pylon.FeaturePersistence.Load(self._camera_config_filepath, cam.GetNodeMap())
      
      # Assign an ID to each grabbed frame, corresponding to the host device
      cam.SetCameraContext(idx)
      
      # Enable PTP to sync cameras between each other for Synchronous Free Running at the specified frame rate
      cam.PtpEnable.SetValue(True)

      # Verify that the slave device are sufficiently synchronized
      while cam.PtpServoStatus.GetValue() != "Locked":
        # Execute clock latch 
        cam.PtpDataSetLatch.Execute()
        time.sleep(1)

    # Instantiate callback handler
    self._image_handler = ImageEventHandler(cam_array=self._cam_array)

    return True


  # Register background grab loop with a callback responsible for sending frames over ZeroMQ
  def run(self) -> None:
    super().run()

    # Fetch some images with background loop
    self._cam_array.StartGrabbing(pylon.GrabStrategy_LatestImages, pylon.GrabLoop_ProvidedByInstantCamera)

    try:
      while self._running:
        poll_res: tuple[list[zmq.SyncSocket], list[int]] = tuple(zip(*(self._poller.poll())))
        if not poll_res: continue

        if self._pub in poll_res[0]:
          if self._image_handler.is_data_available():
            self._process_data()
            print(self._stream.get_fps())
        
        if self._killsig in poll_res[0]:
          self._running = False
          print("quitting %s"%self._log_source_tag, flush=True)
          self._killsig.recv_multipart()
          self._poller.unregister(self._killsig)
      self.quit()
    # Catch keyboard interrupts and other exceptions when module testing, for a clean exit
    except Exception as e:
      self.quit()


  def _process_data(self):
    time_s = time.time()
    for camera_id, frame, timestamp, sequence_id in self._image_handler.get_frame():
      # Store the data.
      # self._stream.append_data(device_id=camera_id, time_s=time_s, frame=frame, timestamp=timestamp, sequence_id=sequence_id)
      # Get serialized object to send over ZeroMQ.
      msg = serialize(device_id=camera_id, time_s=time_s, frame=frame, timestamp=timestamp, sequence_id=sequence_id)
      # Send the data packet on the PUB socket.
      self._pub.send_multipart([("%s.%s.data" % (self._log_source_tag, self._camera_mapping[camera_id])).encode('utf-8'), msg])


  # Clean up and quit
  def quit(self) -> None:
    # Stop capturing data
    self._cam_array.StopGrabbing()
    # Remove background loop event listener
    for cam in self._cam_array: cam.DeregisterImageEventHandler(self._image_handler)
    # Disconnect from the camera
    self._cam_array.Close()
    super().quit()


#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  camera_mapping = { # map camera names (usable as device names in the HDF5 file) to capture device indexes
    'basler_north' : '40478064',
    'basler_east'  : '40549960',
    'basler_south' : '40549975',
    'basler_west'  : '40549976',
  }
  fps = 20
  resolution = (1944, 2592) # Uses BayerRG8 format with colors encoded, which gets converted to RGB in visualization by the GUI thread
  camera_config_filepath = 'resources/pylon_20fps_maxres.pfs'

  ip = "127.0.0.1"
  port_backend = "42069"
  port_frontend = "42070"
  port_sync = "42071"
  port_killsig = "42066"

  # Pass exactly one ZeroMQ context instance throughout the program
  ctx: zmq.Context = zmq.Context()

  # Exposes a known address and port to locally connected sensors to connect to.
  local_backend: zmq.SyncSocket = ctx.socket(zmq.XSUB)
  local_backend.bind("tcp://127.0.0.1:%s" % (port_backend))
  backends: list[zmq.SyncSocket] = [local_backend]

  # Exposes a known address and port to broker data to local workers.
  local_frontend: zmq.SyncSocket = ctx.socket(zmq.XPUB)
  local_frontend.bind("tcp://127.0.0.1:%s" % (port_frontend))
  frontends: list[zmq.SyncSocket] = [local_frontend]

  streamer = CameraStreamer(camera_mapping=camera_mapping, 
                            fps=fps,
                            resolution=resolution,
                            port_pub=port_backend,
                            port_sync=port_sync,
                            port_killsig=port_killsig,
                            camera_config_filepath=camera_config_filepath)

  streamer()
