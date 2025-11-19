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

from nodes.producers.Producer import Producer
from streams import GlassesStream

from utils.print_utils import *
from utils.zmq_utils import *

import uvc


#######################################################
#######################################################
# A class for streaming videos from Pupil core cameras.
#######################################################
#######################################################

class GlassesStreamer(Producer):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'glasses'


  def __init__(self,
               host_ip: str,
               camera_mapping: dict,
               logging_spec: dict,
               video_image_format: str = "jpeg", # [bgr, jpeg, yuv]
               bandwidth_factor: float = 2.0,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC_HOST,
               port_killsig: str = PORT_KILL,
               transmit_delay_sample_period_s: float = float('nan'),
               timesteps_before_solidified: int = 0,
               **_):

    self._bandwidth_factor = bandwidth_factor
    self._camera_mapping = camera_mapping
    self._video_image_format = video_image_format
    self._captures: dict[str, uvc.Capture] = {}
    self._start_index: dict[str, int] = dict(map(lambda cam: (cam, None), camera_mapping.keys()))
    self._get_frame_fn = self._get_first_frame

    stream_info = {
      "camera_mapping": self._camera_mapping,
      "pixel_format": video_image_format,
      "timesteps_before_solidified": timesteps_before_solidified
    }

    super().__init__(host_ip=host_ip,
                     stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     transmit_delay_sample_period_s=transmit_delay_sample_period_s)


  @classmethod
  def create_stream(cls, stream_info: dict) -> GlassesStream:
    return GlassesStream(**stream_info)


  def _ping_device(self) -> None:
    return None


  def _connect(self) -> bool:
    devices = dict(map(lambda dev: (dev['name'], dev['uid']), uvc.device_list()))

    for camera_name, camera_spec in self._camera_mapping.items():
      try:
        self._captures[camera_name] = uvc.Capture(devices[camera_spec['name']])
        self._captures[camera_name].bandwidth_factor = self._bandwidth_factor

        for mode in self._captures[camera_name].available_modes:
          if (mode.width == camera_spec['resolution'][1] and
              mode.height == camera_spec['resolution'][0] and
              mode.fps == camera_spec['fps']):
            self._captures[camera_name].frame_mode = mode
            break

        # TODO: configure the controls on each `Capture` object (exposure, brightness, sharpness, etc)

      except Exception as err:
        print(f"[GlassesStreamer] Failed to open camera {camera_name}: {err}", flush=True)
        return False

    return True


  def _keep_samples(self) -> None:
    return None


  def _process_data(self) -> None:
    res = self._get_frame_fn()
    if res is not None:
      process_time_s = get_time()
      tag: str = "%s.data" % self._log_source_tag()
      self._publish(tag, process_time_s=process_time_s, data=res)
    elif not self._is_continue_capture:
      self._send_end_packet()


  def _get_first_frame(self) -> dict | None:
    output = {}
    for camera_name, cap in self._captures.items():
      try:
        frame = cap.get_frame(timeout=0.01) # TODO: will consume resources unnecessarily
        toa_s = get_time()
      except TimeoutError:
        continue
      except uvc.InitError as err:
        print(f"[GlassesStreamer] Failed to init {camera_name}: {err}", flush=True)
        continue
      except uvc.StreamError as err:
        print(f"[GlassesStreamer] Stream error for {camera_name}: {err}", flush=True)
        continue

      if self._start_index[camera_name] is None:
        self._start_index[camera_name] = frame.index
        frame_index = 0
      else:
        frame_index = frame.index - self._start_index[camera_name]

      if all(map(lambda camera_start_index: camera_start_index is not None, self._start_index.values())):
        self._get_frame_fn = self._get_frame

      output[camera_name] = {
        'frame_timestamp': frame.timestamp,
        'frame_index': frame_index,
        'frame_sequence_id': frame.index,
        'frame': (frame.bgr, False, frame_index),
        'toa_s': toa_s
      }

    if not not output:
      return output
    else:
      return None


  def _get_frame(self) -> dict | None:
    output = {}
    for camera_name, cap in self._captures.items():
      try:
        frame = cap.get_frame(timeout=0.01) # TODO: will consumer resources unnecessarily
        toa_s = get_time()
      except TimeoutError:
        continue
      except uvc.InitError as err:
        print(f"[GlassesStreamer] Failed to init {camera_name}: {err}", flush=True)
        continue
      except uvc.StreamError as err:
        print(f"[GlassesStreamer] Stream error for {camera_name}: {err}", flush=True)
        continue

      frame_index = frame.index - self._start_index[camera_name]

      output[camera_name] = {
        'frame_timestamp': frame.timestamp,
        'frame_index': frame_index,
        'frame_sequence_id': frame.index,
        'frame': (frame.bgr, False, frame_index),
        'toa_s': toa_s
      }

    if not not output:
      return output
    else:
      return None


  def _stop_new_data(self) -> None:
    self._get_frame_fn = lambda: None


  def _cleanup(self) -> None:
    for cap in self._captures.values():
      try:
        cap.close()
      except Exception:
        pass
    super()._cleanup()
