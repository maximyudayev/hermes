from pypylon import pylon
import numpy as np

from utils.print_utils import *

class ImageEventHandler(pylon.ImageEventHandler):
  def __init__(self, callback_fn: callable):
    super().__init__()
    self._callback_fn = callback_fn
      
  def OnImageGrabbed(self, camera, res: pylon.GrabResultData):
    # Gets called on every image.
    #   Runs in a pylon thread context, always wrap in the `try .. except`
    #   to capture errors inside the grabbing as this can't be properly 
    #   reported from the background thread to the foreground python code.
    try:
      # TODO: In our grab strategy, `res` can be multiple images 
      if res.GrabSucceeded():
        frame: np.ndarray = res.Array
        camera_id: int = res.GetCameraContext()
        timestamp: np.uint64 = res.GetTimeStamp()
        sequence_id: np.int64 = res.GetImageNumber()
        self._callback_fn(frame=frame, camera_id=camera_id, timestamp=timestamp, sequence_id=sequence_id)
      else:
        raise RuntimeError("Grab Failed")
    except Exception as e:
      pass

  def OnImagesSkipped(self, camera, countOfSkippedImages):
    msg = log_debug(f"{camera.GetDeviceInfo().GetSerialNumber()} skipped {countOfSkippedImages} images.")
