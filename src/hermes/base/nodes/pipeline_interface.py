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

from abc import abstractmethod

from hermes.base.nodes.node_interface import NodeInterface
from hermes.base.stream import Stream


class PipelineInterface(NodeInterface):
    """Interface for the Pipeline Node component."""

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
    def _process_data(self, topic: str, msg: dict) -> None:
        """Main iteration loop logic for the Node during its running phase.

        Contained logic has to deal with async multiple modalities.
        Must end with calling `_send_end_packet`.

        Args:
            topic (str): Uniquely identified modality of the contained data.
            msg (dict): Received data of the corresponding modality.
        """
        pass

    @abstractmethod
    def _keep_samples(self) -> None:
        """Node-specific externally triggered function to start keeping in memory streamed data."""
        pass

    @abstractmethod
    def _generate_data(self) -> None:
        """Main iteration loop logic to process and distribute internal asynchronously generated data.
        
        Contained logic must deal with sending internally generated data packets until external termination
        signal is received, in a non-deadlocking way to the rest of the Pipeline processing.
        """
        pass

    @abstractmethod
    def _stop_new_data(self) -> None:
        """Stop sampling data, continue sending already captured until none is left."""
        pass
