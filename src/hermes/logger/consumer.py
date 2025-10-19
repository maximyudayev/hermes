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

from hermes.utils.zmq_utils import PORT_FRONTEND, PORT_KILL, PORT_SYNC_HOST

from hermes.base.nodes.consumer import Consumer


class DataLogger(Consumer):
  """A Node to centrally log streaming data of all specified modalities to one or more files.

  May be redundant because each Node has a local Storage component that manages safe disk flushing of the acquired data.
  Producer and Pipeline specifications mapping is passed to the class, 
  and the data they stream are written to disk periodically and/or at the end.
  """
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'logger'


  def __init__(self,
               host_ip: str,
               stream_specs: list[dict],
               logging_spec: dict,
               port_sub: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC_HOST,
               port_killsig: str = PORT_KILL,
               log_history_filepath: str | None = None,
               **_):
    """Constructor of the centralized Storage Node.

    Args:
        host_ip (str): IP address of the local master Broker.
        stream_specs (list[dict]): List of mappings of user-configured incoming modalities.
        logging_spec (dict): Mapping of Storage object parameters to user-defined configuration values.
        port_sub (str, optional): Local port to subscribe to for incoming relayed data from the local master Broker. Defaults to PORT_FRONTEND.
        port_sync (str, optional): Local port to listen to for local master Broker's startup coordination. Defaults to PORT_SYNC_HOST.
        port_killsig (str, optional): Local port to listen to for local master Broker's termination signal. Defaults to PORT_KILL.
        log_history_filepath (str | None, optional): File path to the system log file. Defaults to None.
    """
    super().__init__(host_ip=host_ip,
                     stream_in_specs=stream_specs,
                     logging_spec=logging_spec,
                     port_sub=port_sub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     log_history_filepath=log_history_filepath)


  def _cleanup(self):
    super()._cleanup()
