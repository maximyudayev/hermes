############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Created 2024-2025 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Maxim Yudayev [https://yudayev.com].
#
# ############

from collections import OrderedDict
import queue
from threading import Lock
from typing import Generator
from pypylon import pylon
import numpy as np
import cv2

from utils.print_utils import *

class ImageEventHandler(pylon.ImageEventHandler):
  def __init__(self, cam_array, buffer_size=0):
    super().__init__()
    self._cam_array = cam_array
    # Register with the pylon loop
    for cam in cam_array: cam.RegisterImageEventHandler(self, pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_None)
    self._buffers = OrderedDict([(cam.GetDeviceInfo().GetSerialNumber(), queue.Queue(maxsize=buffer_size)) for cam in cam_array])
    self._locks = OrderedDict([(cam.GetDeviceInfo().GetSerialNumber(), Lock()) for cam in cam_array])


  def OnImageGrabbed(self, camera, res: pylon.GrabResultData):
    # Gets called on every image.
    #   Runs in a pylon thread context, always wrap in the `try .. except`
    #   to capture errors inside the grabbing as this can't be properly 
    #   reported from the background thread to the foreground python code.
    try:
      if res.GrabSucceeded():
        frame = res.Array
        camera_id: str = camera.GetDeviceInfo().GetSerialNumber()
        timestamp: np.uint64 = res.GetTimeStamp()
        sequence_id: np.int64 = res.GetImageNumber()
        self._put_frame(camera_id=camera_id, frame=frame, timestamp=timestamp, sequence_id=sequence_id)
      else:
        raise RuntimeError("Grab Failed")
    except Exception as e:
      print(e)

  def OnImagesSkipped(self, camera, countOfSkippedImages):
    print(f"{camera.GetDeviceInfo().GetSerialNumber()} skipped {countOfSkippedImages} images.")

  # Pops the oldest value if the queue is full
  def _put_frame(self, camera_id: str, frame: np.ndarray, timestamp: np.uint64, sequence_id: np.int64) -> None:
    try:
      self._locks[camera_id].acquire()
      self._buffers[camera_id].put_nowait((camera_id, frame, timestamp, sequence_id))
    except queue.Full:
      _ = self._buffers[camera_id].get()
      self._buffers[camera_id].put((camera_id, frame, timestamp, sequence_id))
    finally:
      self._locks[camera_id].release()

  def get_frame(self) -> Generator[tuple[str, np.ndarray, np.uint64, np.int64], None, None]:
    for camera in self._cam_array:
      camera_id: str = camera.GetDeviceInfo().GetSerialNumber()
      try:
        self._locks[camera_id].acquire()
        oldest_frame = self._buffers[camera_id].get_nowait()
        self._locks[camera_id].release()
        yield oldest_frame
      except queue.Empty:
        self._locks[camera_id].release()
        continue

  # If at least one camera has a new frame
  def is_data_available(self) -> bool:
    for camera in self._cam_array:
      camera_id: str = camera.GetDeviceInfo().GetSerialNumber()
      if self._buffers[camera_id].qsize() > 0: return True
    return False
