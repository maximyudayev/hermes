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

import zmq

from hermes.utils.zmq_utils import CMD_HELLO

from hermes.base.nodes.node_interface import NodeInterface
from hermes.base.state_interface import StateInterface


class AbstractNodeState(StateInterface):
  def __init__(self, context: NodeInterface):
    self._context = context

  def is_continue(self) -> bool:
    return True

  def kill(self) -> None:
    self._context._set_state(KillState(self._context))


class StartState(AbstractNodeState):
  def run(self):
    self._context._initialize()
    # Activate data poller in case Node goes into KillState.
    self._context._activate_data_poller()
    self._context._set_state(SyncState(self._context))


class SyncState(AbstractNodeState):
  def __init__(self, context: NodeInterface):
    super().__init__(context)
    self._sync = context._get_sync_socket()

  def run(self):
    self._sync.send_multipart([self._context._log_source_tag().encode('utf-8'), CMD_HELLO.encode('utf-8')])
    host, cmd = self._sync.recv_multipart()
    print("%s received %s from %s." % (self._context._log_source_tag(),
                                       cmd.decode('utf-8'),
                                       host.decode('utf-8')),
                                       flush=True)
    self._context._set_state(RunningState(self._context))


class RunningState(AbstractNodeState):
  def __init__(self, context):
    super().__init__(context)
    self._context._activate_kill_poller()
    self._context._on_sync_complete()

  def run(self):
    poll_res: tuple[list[zmq.SyncSocket], list[int]] = self._context._poll()
    self._context._on_poll(poll_res)


class KillState(AbstractNodeState):
  def run(self):
    self._context._deactivate_kill_poller()
    self._context._send_kill_to_broker()
    self._context._trigger_stop()
    self._context._set_state(JoinState(self._context))

  # Override to ignore more kill calls because we are already ending process.
  def kill(self):
    pass


class JoinState(AbstractNodeState):
  def run(self):
    poll_res: tuple[list[zmq.SyncSocket], list[int]] = self._context._poll()
    self._context._on_poll(poll_res)

  def is_continue(self):
    return not self._context._is_done
  
  # Override to ignore more kill calls because we are already ending process.
  def kill(self):
    pass
