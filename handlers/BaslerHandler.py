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

from utils.print_utils import *


# Does not align video streams according to timestamps, 
#   they are captured synchronously on independent PoE interfaces -> no need.
#   That's why alignment is not necessary unlike IMUs.
#   Grabbed images from several devices pushed into single buffer, arbitrarily overlapping images.
# NOTE: may be interesting to actually align them in a snapshot buffer, similar to IMUs,
#   To make multi-angle computer vision algorithms possible. 
class ImageEventHandler(pylon.ImageEventHandler):
  def __init__(self, cam_array):
    super().__init__()
    self._cam_array = cam_array
    for cam in cam_array: 
      # Register with the pylon loop, specify strategy for frame grabbing.
      cam.RegisterImageEventHandler(self, pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_None)
    self._buffer = queue.Queue()


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
        self._buffer.put((camera_id, frame, timestamp, sequence_id))
      else:
        raise RuntimeError("Grab Failed")
    except Exception as e:
      pass

  def OnImagesSkipped(self, camera, num_images_skipped):
    print(f"{camera.GetDeviceInfo().GetSerialNumber()} skipped {num_images_skipped} images.")


  def get_frame(self) -> tuple[str, np.ndarray, np.uint64, np.int64] | None:
    try:
      oldest_frame = self._buffer.get_nowait()
      return oldest_frame
    except queue.Empty:
      return None
