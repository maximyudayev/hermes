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

from abc import abstractmethod

from hermes.base.nodes.node_interface import NodeInterface
from hermes.base.stream import Stream


class ProducerInterface(NodeInterface):
  """Interface for the Producer Node component.
  """

  @classmethod
  @abstractmethod
  def create_stream(cls, stream_spec: dict) -> Stream:
    """Instantiate Stream datastructure object specific to this Pipeline.

    Should also be a class method to create Stream objects on consumers.

    Args:
        stream_spec (dict): Mapping of corresponding Stream object parameters to user-defined configuration values.

    Returns:
        Stream: Datastructure object of the corresponding Node, configured according to the user-provided specification.
    """
    pass

  @abstractmethod
  def _ping_device(self) -> None:
    """Device-specific procedure for round-trip time estimation.

    Concrete implementation of Producer must override the method if required to measure transmission delay
      for realtime/post-processing alignment of modalities that don't support system clock sync.
    """
    pass

  @abstractmethod
  def _connect(self) -> bool:
    """Connect to device via its corresponding backend.

    Returns:
        bool: Whether connection to the device succeeded.
    """
    pass

  @abstractmethod
  def _keep_samples(self) -> None:
    """Node-specific externally triggered function to start keeping in memory streamed data.
    """
    pass

  @abstractmethod
  def _process_data(self) -> None:
    """Main iteration loop logic for the Node during its running phase.

    Acquire data from your sensor as desired, and for each timestep.
    SDK thread pushes data into shared memory space, this thread pulls data and does all the processing,
    ensuring that lost packets are responsibility of the slow consumer.
    """
    pass

  @abstractmethod
  def _stop_new_data(self) -> None:
    """Stop sampling data, continue sending already captured until none is left.
    """
    pass
