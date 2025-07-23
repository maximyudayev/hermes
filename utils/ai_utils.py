############
#
# Copyright (c) 2025 Vayalet Stefanova and KU Leuven eMedia Lab
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
# Created 2025 for AidWear, AidFOG, and RevalExo projects of KU Leuven.
#
# ############

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi 


def smooth(pred: int, state: tuple) -> tuple:
  in_fog, consec_ones, consec_zeros = state

  if not in_fog:
    consec_ones = consec_ones + 1 if pred == 1 else 0
    if consec_ones >= 3:
      in_fog, consec_zeros = True, 0
    return (1 if in_fog else 0), (in_fog, consec_ones, consec_zeros)

  else:
    consec_zeros = consec_zeros + 1 if pred == 0 else 0
    if consec_zeros >= 5:
      in_fog, consec_ones = False, 0
    return 1, (in_fog, consec_ones, consec_zeros)


def init_iir_filter(fs: float, cutoff_hz: float = 0.3, order: int = 4, num_channels: int = 6) -> tuple:
  nyquist = 0.5 * fs
  norm_cutoff = cutoff_hz / nyquist
  b, a = butter(order, norm_cutoff, btype='high', analog=False) # type: ignore
  zi = [lfilter_zi(b, a) * 0 for _ in range(num_channels)]
  return b, a, zi


def normalize(sensor_sample, b, a, zi, count, mean, var, eps=1e-3):
  # high-pass filter the accelerometer
  acc = sensor_sample[:3]
  filtered_acc = np.zeros_like(acc)
  for j in range(3):
    filtered_acc[j], zi[j] = lfilter(b, a, [acc[j]], zi=zi[j])

  sensor_sample = np.concatenate((filtered_acc, sensor_sample[3:]))

  # update running mean and variance (Welford's algorithm)
  count += 1
  delta = sensor_sample - mean
  mean += delta / count
  var += (delta * (sensor_sample - mean) - var) / count

  # Normalize: only center gyro (indices 3 to 5)
  sensor_sample = sensor_sample - np.concatenate([np.zeros(3), mean[3:]])
  std = np.sqrt(var)
  std = np.clip(std, eps, None)
  norm_sample = sensor_sample / std

  return norm_sample, zi, count, mean, var
