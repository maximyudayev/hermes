############
#
# Copyright (c) 2024-2025 Maxim Yudayev and KU Leuven eMedia Lab
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

from argparse import Namespace
from multiprocessing import Event, Queue
from typing import Callable

from hermes.base.broker.broker import Broker


def launch_broker(
    args: Namespace,
    node_specs: list[dict],
    input_queue: "Queue[tuple[float, str]]",
    is_ready_event: Event,
    is_quit_event: Event,
    is_done_event: Event,
    ref_time_s: float,
):
    # Create the broker and manage all the components of the experiment.
    local_broker: Broker = Broker(
        host_ip=args.host_ip,
        node_specs=node_specs,
        is_ready_event=is_ready_event,
        is_quit_event=is_quit_event,
        is_done_event=is_done_event,
        input_queue=input_queue,
        is_master_broker=args.is_master_broker,
        ref_time_s=ref_time_s,
    )

    # Connect broker to remote publishers at the wearable PC to get data from the wearable sensors.
    for ip in args.remote_publisher_ips:
        local_broker.connect_to_remote_broker(addr=ip)

    # Expose local wearable data to remote subscribers (e.g. edge server).
    if args.remote_subscriber_ips:
        local_broker.expose_to_remote_broker(args.remote_subscriber_ips)

    # Subscribe to the KILL signal of a remote machine.
    if args.is_remote_kill:
        local_broker.subscribe_to_killsig(addr=args.remote_kill_ip)

    # Only master host runs with duration, others wait for commands.
    if args.is_master_broker:
        local_broker(args.duration_s)
    else:
        local_broker()


def launch_callable(obj: Callable, *args, **kwargs):
    obj(*args, **kwargs)
