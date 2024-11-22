from collections import OrderedDict
import queue
from threading import Lock
from typing import Callable, Generator
from pypylon import pylon
import numpy as np

from utils.print_utils import *

class ImageEventHandler(pylon.ImageEventHandler):
  def __init__(self, cam_array, buffer_size=5):
    super().__init__()
    self._cam_array = cam_array
    # Register with the pylon loop
    self._cam_array.RegisterImageEventHandler(self, pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_None)
    self._buffers = OrderedDict([(cam.GetDeviceInfo().GetSerialNumber(), queue.Queue(maxsize=buffer_size)) for cam in cam_array])
    self._lock = Lock()

  def OnImageGrabbed(self, camera, res: pylon.GrabResultData):
    # Gets called on every image.
    #   Runs in a pylon thread context, always wrap in the `try .. except`
    #   to capture errors inside the grabbing as this can't be properly 
    #   reported from the background thread to the foreground python code.
    try:
      # TODO: In our grab strategy, `res` can be multiple images 
      if res.GrabSucceeded():
        frame: np.ndarray = res.Array
        camera_id: str = camera.GetDeviceInfo().GetSerialNumber()
        timestamp: np.uint64 = res.GetTimeStamp()
        sequence_id: np.int64 = res.GetImageNumber()
        self._put_frame(camera_id=camera_id, frame=frame, timestamp=timestamp, sequence_id=sequence_id)
      else:
        raise RuntimeError("Grab Failed")
    except Exception as e:
      pass

  def OnImagesSkipped(self, camera, countOfSkippedImages):
    msg = log_debug(f"{camera.GetDeviceInfo().GetSerialNumber()} skipped {countOfSkippedImages} images.")
    print(msg)

  def _put_frame(self, camera_id: str, frame: np.ndarray, timestamp: np.uint64, sequence_id: np.int64) -> None:
    self._buffers[camera_id].put()

  def get_frame() -> Generator[tuple[str, np.ndarray, np.uint64, np.int64]]:
    yield

  def is_data_available() -> bool:
    pass