from collections import OrderedDict
import os

import zmq
from handlers.BaslerHandler import ImageEventHandler
from producers.Producer import Producer
from streams.CameraStream import CameraStream
from utils.msgpack_utils import serialize

import pypylon.pylon as pylon

from utils.print_utils import *
from utils.zmq_utils import *


#######################################################
#######################################################
# A class for streaming videos from Basler PoE cameras.
#######################################################
#######################################################
class CameraStreamer(Producer):
  @property
  def _log_source_tag(self) -> str:
    return 'cameras'


  def __init__(self,
               camera_mapping: dict[str, str], # a dict mapping camera names to device indexes
               fps: float,
               resolution: tuple[int],
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               camera_config_filepath: str = None, # path to the pylon .pfs config file to reproduce desired camera setup
               print_status: bool = True,
               print_debug: bool = False,
               **_):

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


  def create_stream(cls, stream_info: dict) -> CameraStream:
    return CameraStream(**stream_info)


  def _connect(self) -> bool:
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
        time.sleep(10)

    # Instantiate callback handler
    self._image_handler = ImageEventHandler(cam_array=self._cam_array)

    # Start asynchronously capturing images with a background loop
    self._cam_array.StartGrabbing(pylon.GrabStrategy_LatestImages, pylon.GrabLoop_ProvidedByInstantCamera)
    return True


  def _process_data(self):
    if self._image_handler.is_data_available():
      time_s = time.time()
      for camera_id, frame, timestamp, sequence_id in self._image_handler.get_frame():
        # Store the data.
        self._stream.append_data(device_id=camera_id, time_s=time_s, frame=frame, timestamp=timestamp, sequence_id=sequence_id)
        # Get serialized object to send over ZeroMQ.
        msg = serialize(device_id=camera_id, time_s=time_s, frame=frame, timestamp=timestamp, sequence_id=sequence_id)
        # Send the data packet on the PUB socket.
        self._pub.send_multipart([("%s.%s.data" % (self._log_source_tag, self._camera_mapping[camera_id])).encode('utf-8'), msg])
    elif not self._is_continue_capture:
      # If triggered to stop and no more available data, send empty 'END' packet and join.
      self._send_end_packet()


  def _stop_new_data(self):
    # Stop capturing data
    self._cam_array.StopGrabbing()


  def _cleanup(self) -> None:
    # Remove background loop event listener
    for cam in self._cam_array: cam.DeregisterImageEventHandler(self._image_handler)
    # Disconnect from the camera
    self._cam_array.Close()
    super()._cleanup()


# TODO: update the unit test.
#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  from consumers.DataLogger import DataLogger
  camera_mapping = { # map camera names (usable as device names in the HDF5 file) to capture device indexes
    'basler_north' : '40478064',
    'basler_east'  : '40549960',
    'basler_south' : '40549975',
    'basler_west'  : '40549976',
  }
  fps = 20
  resolution = (1944, 2592) # Uses BayerRG8 format with colors encoded, which gets converted to RGB in visualization by the GUI thread
  camera_config_filepath = 'resources/pylon_20fps_maxres.pfs'

  ip = IP_LOOPBACK
  port_backend = PORT_BACKEND
  port_frontend = PORT_FRONTEND
  port_sync = PORT_SYNC
  port_killsig = PORT_KILL

  log_tag: str = 'aidWear-wearables'
  script_dir: str = os.path.dirname(os.path.realpath(__file__))
  (log_time_str, log_time_s) = get_time_str(return_time_s=True)
  log_dir_root: str = os.path.join(script_dir, '..', '..', 'data',
                              'test',
                              '{0}_S{1}_{2}'.format(get_time_str(format='%Y-%m-%d'), 
                                                    str(1).zfill(3), 
                                                    str(1).zfill(2)))
  log_subdir: str = '%s_%s' % (log_time_str, log_tag)
  log_dir: str = os.path.join(log_dir_root, log_subdir)
  # Initialize a file for writing the log history of all printouts/messages.
  log_history_filepath: str = os.path.join(log_dir, '%s_log_history.txt' % (log_time_str))
  os.makedirs(log_dir, exist_ok=True)

  datalogging_options = {
    'classes_to_log': ['CameraStreamer'],
    'log_dir': log_dir, 'log_tag': log_tag,
    'use_external_recording_sources': False,
    'videos_in_hdf5': False,
    'audio_in_hdf5': False,
    # Choose whether to periodically write data to files.
    'stream_hdf5' : True, # recommended over CSV since it creates a single file
    'stream_csv'  : False, # will create a CSV per stream
    'stream_video': True,
    'stream_audio': False,
    'stream_period_s': 5, # how often to save streamed data to disk
    'clear_logged_data_from_memory': True, # ignored if dumping is also enabled below
    # Choose whether to write all data at the end.
    'dump_csv'  : False,
    'dump_hdf5' : False,
    'dump_video': False,
    'dump_audio': False,
    # Additional configuration.
    'videos_format': 'avi', # mp4 occasionally gets openCV errors about a tag not being supported?
    'audio_format' : 'wav', # currently only supports WAV
  }

  streamer_specs_logger = [{
    'class': 'CameraStreamer',
    'camera_mapping': { # map camera names (usable as device names in the HDF5 file) to capture device indexes
      'basler_north' : '40478064',
      'basler_east'  : '40549960',
      'basler_south' : '40549975',
      'basler_west'  : '40549976',
    },
    'fps': 20,
    'resolution': (1944, 2592),
    'camera_config_filepath': 'resources/pylon_20fps_maxres.pfs'
  }]

  # Pass exactly one ZeroMQ context instance throughout the program
  ctx: zmq.Context = zmq.Context()

  # Exposes a known address and port to locally connected sensors to connect to.
  killsig: zmq.SyncSocket = ctx.socket(zmq.PUB)
  killsig.bind("tcp://%s:%s" % (ip, port_killsig))

  backend: zmq.SyncSocket = ctx.socket(zmq.XSUB)
  backend.bind("tcp://%s:%s" % (ip, port_backend))

  frontend: zmq.SyncSocket = ctx.socket(zmq.XPUB)
  frontend.bind("tcp://%s:%s" % (ip, port_frontend))

  streamer = CameraStreamer(camera_mapping=camera_mapping, 
                            fps=fps,
                            resolution=resolution,
                            port_pub=port_backend,
                            port_sync=port_sync,
                            port_killsig=port_killsig,
                            camera_config_filepath=camera_config_filepath)

  logger = DataLogger(**datalogging_options, 
                      streamer_specs=streamer_specs_logger, 
                      log_history_filepath=log_history_filepath,
                      port_sub=port_backend,
                      port_sync=port_sync,
                      port_killsig=port_killsig)

  zmq.device(zmq.FORWARDER, backend, frontend)

  # TODO: Run the one not being tested in a subprocess
  streamer()
  logger()

  # TODO: send killsig to both, join process, exit 
