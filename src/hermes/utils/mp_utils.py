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

from argparse import Namespace
from multiprocessing import Queue
from multiprocessing.synchronize import Event as _Event
from typing import Callable

from hermes.base.broker.broker import Broker


def launch_broker(
    args: Namespace,
    node_specs: list[dict],
    input_queue: "Queue[tuple[float, str]]",
    is_ready_event: _Event,
    is_quit_event: _Event,
    is_done_event: _Event,
    ref_time_s: float,
) -> None:
    """Builds the `Broker` using provided configurations and manage all the components of the experiment.

    Meant to be used as a target for a spawned Process or Thread.

    Args:
        args (argparse.Namespace): HERMES top-level user input arguments for the experiment definition.
        node_specs (list[dict]): Configuration dictionaries of the Broker's locally managed `Node`s.
        input_queue (Queue[tuple[float, str]]): Multiprocessing queue to fan-out user keyboard inputs to all `Broker`s locally managed `Node`s.
        is_ready_event (Event): Multiprocessing synchronization primitive indicating completion of `Broker`s setup and handshaking with `Node`s.
        is_quit_event (Event): Multiprocessing synchronization primitive triggering to the `Broker` to gracefully wrap up and end.
        is_done_event (Event): Multiprocessing synchronization primitive indicating that the `Broker` is finished and experiment ended.
        ref_time_s (float): Main process reference system time obtained with `get_ref_time()` to use in all child processes for syncing the data.
    """
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


def launch_callable(obj: Callable, *args, **kwargs) -> None:
    """Launches a callable object with the user-provided inputs.

    Args:
        args (list): Ordered unnamed inputs to provide to the callable object.
        kwargs (dict): Named key-value inputs to provide to the callable object.
    """
    obj(*args, **kwargs)


def launch_handler(module: type, *args, **kwargs) -> None:
    """Used as a target to instantiate a runnable object as a subprocess.

    Args:
        args (list): Ordered unnamed arguments to instantiate the object with.
        kwargs (dict): Named key-value arguments to instantiate the object with.
    """
    obj = module(*args, **kwargs)
    obj()
