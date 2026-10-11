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

from typing import Optional
import zmq
from statemachine import StateMachine, State

from hermes.utils.zmq_utils import CMD_HELLO, CMD_IS_START

from hermes.base.nodes.node_interface import NodeInterface
from hermes.base.state_interface import StateInterface


class NodeStateMachine(StateMachine):
    """State machine managing the lifecycle and transitions of a Node."""

    allow_event_without_transition = True

    start = State("Start", value="start", initial=True)
    subscribe = State("Subscribe", value="subscribe")
    sync = State("Sync", value="sync")
    running = State("Running", value="running")
    kill_state = State("Kill", value="kill")
    join = State("Join", value="join")
    done = State("Done", value="done", final=True)

    to_subscribe = start.to(subscribe)
    to_sync = subscribe.to(sync)
    to_running = sync.to(running)
    to_kill = (
        start.to(kill_state)
        | subscribe.to(kill_state)
        | sync.to(kill_state)
        | running.to(kill_state)
    )
    to_join = kill_state.to(join)
    to_done = join.to(done)

    def __init__(self, context: NodeInterface):
        """Constructor of the NodeStateMachine.

        Args:
            context (NodeInterface): Reference to the Node object.
        """
        self._context = context
        self._sync: Optional[zmq.SyncSocket] = None
        self._sync_poller: Optional[zmq.Poller] = None
        super().__init__()

    def on_enter_subscribe(self) -> None:
        """Hook when entering Subscribe state: register sync socket and send HELLO."""
        self._sync = self._context._get_sync_socket()
        self._sync_poller = zmq.Poller()
        self._sync_poller.register(self._sync, zmq.POLLIN)
        self._sync.send_multipart(
            [self._context.node_id.encode("utf-8"), CMD_HELLO.encode("utf-8")]
        )

    def on_exit_subscribe(self) -> None:
        """Hook when exiting Subscribe state: unregister sync socket from sync poller."""
        if self._sync_poller is not None and self._sync is not None:
            try:
                self._sync_poller.unregister(self._sync)
            except Exception:
                pass

    def on_enter_running(self) -> None:
        """Hook when entering Running state: activate data & kill pollers and notify sync complete."""
        self._context._activate_data_poller()
        self._context._activate_kill_poller()
        self._context._on_sync_complete()

    def on_enter_kill_state(self) -> None:
        """Hook when entering Kill state: deactivate kill poller and trigger graceful stop."""
        self._context._deactivate_kill_poller()
        self._context._trigger_stop()

    def run(self) -> None:
        if self.start.is_active:
            self._context._initialize()
            self._context._activate_subscription_poller()
            self.to_subscribe()

        elif self.subscribe.is_active:
            poll_res = self._context._poll(500)
            if poll_res:
                self._context._on_poll(poll_res)

            if self._sync_poller is not None and self._sync is not None:
                sync_res = self._sync_poller.poll(500)
                if sync_res:
                    host, cmd = self._sync.recv_multipart()
                    print(
                        "%s received %s from %s"
                        % (
                            self._context.node_id,
                            cmd.decode("utf-8") if isinstance(cmd, bytes) else cmd,
                            host.decode("utf-8") if isinstance(host, bytes) else host,
                        ),
                        flush=True,
                    )
                    self.to_sync()

        elif self.sync.is_active:
            sync = self._context._get_sync_socket()
            sync.send_multipart(
                [self._context.node_id.encode("utf-8"), CMD_IS_START.encode("utf-8")]
            )
            host, cmd = sync.recv_multipart()
            print(
                "%s received %s from %s."
                % (
                    self._context.node_id,
                    cmd.decode("utf-8") if isinstance(cmd, bytes) else cmd,
                    host.decode("utf-8") if isinstance(host, bytes) else host,
                ),
                flush=True,
            )
            self.to_running()

        elif self.running.is_active:
            poll_res: tuple[list[zmq.SyncSocket], list[int]] = self._context._poll()
            self._context._on_poll(poll_res)

        elif self.kill_state.is_active:
            self.to_join()

        elif self.join.is_active:
            poll_res = self._context._poll(1000)
            self._context._on_poll(poll_res)
            if self._context._is_done:
                self.to_done()

    def is_continue(self) -> bool:
        return not self.is_terminated

    def kill(self) -> None:
        self.send("to_kill")

StateInterface.register(NodeStateMachine)
