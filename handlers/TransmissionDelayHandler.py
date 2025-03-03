import time
from typing import Callable
from utils.sensor_utils import estimate_transmission_delay


class DelayEstimator:
  def __init__(self,
               sample_period_s: float):
    self._sample_period_s = sample_period_s
    self._is_continue = True


  def __call__(self,
               ping_fn: Callable,
               publish_fn: Callable):
    while self._is_continue:
      delay_s: float = estimate_transmission_delay(ping_fn=ping_fn)
      time_s = time.time()
      publish_fn(time_s, delay_s)
      time.sleep(self._sample_period_s)


  def cleanup(self):
    self._is_continue = False
