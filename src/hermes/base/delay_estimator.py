############
#
# Copyright (c) 2024-2026 Maxim Yudayev and KU Leuven eMedia Lab
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

import time
from typing import Callable

from hermes.utils.sensor_utils import estimate_transmission_delay
from hermes.utils.time_utils import get_time


class DelayEstimator:
    """Functional callable class for periodic device-specific propagation delay estimation."""

    def __init__(self, sample_period_s: float):
        """Constructor of the DelayEstimator component for propagation delay estimation.

        Args:
            sample_period_s (float): Duration of periods over which to estimate propagation delay.
        """
        self._sample_period_s = sample_period_s
        self._is_continue = True

    def __call__(self, ping_fn: Callable, publish_fn: Callable):
        """Callable that runs periodic propagation delay estimation.

        Uses user-passed estimation and callback functions until termination.

        Args:
            ping_fn (Callable): Propagation delay estimation function pointer.
            publish_fn (Callable): Callback function pointer.
        """
        while self._is_continue:
            delay_s: float = estimate_transmission_delay(ping_fn=ping_fn)
            time_s = get_time()
            publish_fn(time_s, delay_s)
            time.sleep(self._sample_period_s)

    def cleanup(self):
        """Method for external trigger to terminate the delay estimator."""
        self._is_continue = False
