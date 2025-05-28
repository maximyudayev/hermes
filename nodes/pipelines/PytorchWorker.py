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

from nodes.pipelines.Pipeline import Pipeline

import time
import numpy as np
from typing import cast

from streams.PytorchStream import PytorchStream
from utils.zmq_utils import *

import torch
from torch import nn
from collections import deque
from pytorch_tcn import TCN


######################################################
######################################################
# A class for processing sensor data with an AI model.
######################################################
######################################################
class PytorchWorker(Pipeline):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'ai'


  def __init__(self,
               host_ip: str,
               #stream_info: dict,
               logging_spec: dict,
               model_path: str,
               #stream_specs: list[dict],
               port_pub: str = PORT_BACKEND,
               port_sub: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC_HOST,
               port_killsig: str = PORT_KILL,
               **_):

    # Initialize any state that the sensor needs.
    stream_info = {
      
    }

    super().__init__(host_ip=host_ip,
                     stream_info=stream_info,
                     logging_spec=logging_spec,
                     #stream_specs=stream_specs,
                     port_pub=port_pub,
                     port_sub=port_sub,
                     port_sync=port_sync,
                     port_killsig=port_killsig)

    self.model = self._load_model(model_path)
    self.valid_buffer = deque(maxlen=1)  # to store the recent IMUs TODO: calculate receptive field size 
    self.pred_stream = 'prediction'

  @classmethod
  def create_stream(cls, stream_info: dict) -> PytorchStream:
    return PytorchStream(**stream_info)

  def _load_model(self, model_path: str) -> nn.Module:
    model = TCN(
        num_inputs=30,
        num_channels=[16, 32, 32, 32, 16],
        kernel_size=3,
        dropout=0.1,
        output_projection=2,
        output_activation=None,
        causal=True
    )
    model.load_state_dict(torch.load(model_path, map_location='cpu', weights_only=True))
    model.eval()
    
    return model
  
  def _generate_prediction(self) -> int | None:
        try:
          if not self.valid_buffer:
              return None

          latest_sample = self.valid_buffer[-1]  # Shape (5, 6)
          data_array = latest_sample.reshape(1, -1)  # Shape (1, 30)
          input_tensor = torch.tensor(data_array, dtype=torch.float32).unsqueeze(0).permute(0, 2, 1)  # Shape (1, 30, 1)

          with torch.no_grad():
              output = self.model(input_tensor, inference=True)
          
          return output.squeeze().argmax().item()
        except Exception as e:
            print(f"[PytorchWorker] Prediction error: {e}")
            return None

  def _process_data(self) -> None:
    # NOTE: time-of-arrival available with each packet.
    process_time_s: float = time.time()
    if self._is_continue_produce: # TODO: have a meaningful check condition
      
      imu_sample = None if np.random.rand() < 0.1 else np.random.randn(5, 6).astype(np.float32) # Dummy data for testing
      if imu_sample is not None and imu_sample.shape == (5, 6) and not np.isnan(imu_sample).any():
        self.valid_buffer.append(imu_sample)
  
      prediction = self._generate_prediction()

      tag: str = "%s.data" % self._log_source_tag()
      #self._publish(tag, time_s=process_time_s)
    elif not self._is_continue_produce:
      # If triggered to stop and no more available data, send empty 'END' packet and join.
      self._send_end_packet()


  def _stop_new_data(self):
    pass
  

  def _cleanup(self) -> None:
    super()._cleanup()
