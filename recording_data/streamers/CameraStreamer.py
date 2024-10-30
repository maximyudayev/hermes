from streamers import SensorStreamer
from streams import CameraStream
from utils.msgpack_utils import serialize

import cv2

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
               cameras_to_stream: dict = {'default': 0}, # a dict mapping camera names to device indexes
               log_history_filepath: str | None = None,
               print_status: bool = True,
               print_debug: bool = False):

    # Initialize general state.
    self._cameras_to_stream = cameras_to_stream
    
    # TODO: estimate fps and pass to the Stream object?
    # TODO: launch each camera in a separate streamer object
    stream_info = {
      "cameras_to_stream": cameras_to_stream
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
  def connect(self):
    # Connect to each camera and estimate its frame rate.
    # Add devices and streams for each camera.
    for (camera_name, device_index) in self._cameras_to_stream.items():
      # Connect to the camera.
      self._capture = cv2.VideoCapture(device_index)
      (success, frame) = self._capture.read()
      if not success:
        self._log_error('\n\n***ERROR CameraStreamer could not connect to camera %s at device index %d' % (camera_name, device_index))
        return False
      # Get the frame rate.
      fps = self._capture.get(cv2.CAP_PROP_FPS)

    return True

  # TODO: Will start a new process for each camera, so they do not slow each other down.
  def run(self):
    while self._running:
      # Read a frame from the camera.
      (success, frame) = self._captures[self._camera_name].read()
      # Timestamp the frame.
      time_s = time.time()

      # Store the data.
      self._stream.append_data(time_s=time_s, frame=frame, timestamp=timestamp)

      # Get serialized object to send over ZeroMQ.
      msg = serialize(time_s=time_s, frame=frame, timestamp=timestamp)

      # Send the data packet on the PUB socket.
      self._pub.send_multipart([b"%s.%s.data"%(self._log_source_tag, self._camera_name), msg])

  # Clean up and quit
  def quit(self):
    self._captures[camera_name].release()
    # Join the threads to wait until all are done.
    for camera_name in self._cameras_to_stream:
      self._run_threads[camera_name].join()

#####################
###### HELPERS ######
#####################
  
# Try to discover cameras and display a frame from each one,
#  to help identify device indexes.
def discover_cameras(display_frames=True):
  device_indexes = []
  for device_index in range(0, 100):
    capture = cv2.VideoCapture(device_index)
    # Try to get a frame to check if the camera exists.
    (success, frame) = capture.read()
    if success:
      device_indexes.append(device_index)
      if display_frames:
        cv2.imshow('Device %d' % device_index, frame)
        cv2.waitKey(1)
    capture.release()
  if display_frames:
    cv2.waitKey(0)
  return device_indexes
