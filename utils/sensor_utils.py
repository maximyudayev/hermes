import time
from typing import Callable
import numpy as np


def estimate_transmission_delay(ping_fn: Callable, 
                                num_samples: int = 100):
  # Estimate the network delay when sending the set-time command.
  transmit_delays_s: list[float] = []
  for i in range(num_samples):
    local_time_before = time.time()
    ping_fn()
    local_time_after = time.time()
    # Assume symmetric delays.
    transmit_delays_s.append((local_time_after - local_time_before)/2.0)
  # TODO: remove outliers before averaging.
  transmit_delay_s = np.mean(transmit_delays_s)
  return transmit_delay_s
