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

import threading
import os
import yaml
import argparse
from inputimeout import inputimeout, TimeoutOccurred

from hermes.__version__ import __version__
from hermes.base.broker.broker import Broker
from hermes.utils.argparse_utils import ParseExperimentKwargs, validate_path
from hermes.utils.mp_utils import launch_callable
from hermes.utils.time_utils import get_ref_time, get_time
from hermes.utils.zmq_utils import (
    PORT_BACKEND,
    PORT_FRONTEND,
    PORT_KILL,
    PORT_SYNC_HOST,
)
from hermes.utils.types import LoggingSpec, VideoCodec, AudioCodec


# TODO: replace with HERMES-branded font
HERMES = r"""
______  ________________________  ___________________
___  / / /__  ____/__  __ \__   |/  /__  ____/_  ___/
__  /_/ /__  __/  __  /_/ /_  /|_/ /__  __/  _____ \ 
_  __  / _  /___  _  _, _/_  /  / / _  /___  ____/ / 
/_/ /_/  /_____/  /_/ |_| /_/  /_/  /_____/  /____/  
                                                     
"""
DESCRIPTION = (
    HERMES + "Heterogeneous edge realtime measurement and execution system "
    "for continual multimodal data acquisition and AI processing."
)
EPILOG = (
    "Copyright (c) 2024-2025 Maxim Yudayev and KU Leuven eMedia Lab.\n"
    "Created 2024-2025 at KU Leuven for the AidWear, AID-FOG, and RevalExo "
    "projects of prof. Bart Vanrumste, by Maxim Yudayev [https://yudayev.com]."
)


def define_parser() -> argparse.ArgumentParser:
    """Create and return the CLI argument parser for the HERMES application.

    Returns:
        argparse.ArgumentParser: Configured argument parser ready to parse
            command-line arguments for the application.
    """
    parser = argparse.ArgumentParser(
        prog="HERMES",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="increase level of logging verbosity [0,3]",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s v" + __version__
    )

    parser.add_argument(
        "--out_dir",
        "-o",
        type=validate_path,
        dest="out_dir",
        required=True,
        help="path to the output directory of the current host device",
    )
    parser.add_argument(
        "--experiment",
        nargs="*",
        action=ParseExperimentKwargs,
        help="key-value pair tags detailing the experiment, used for "
        "directory creation and metadata on files",
    )
    parser.add_argument(
        "--time",
        "-t",
        type=float,
        dest="log_time_s",
        default=get_time(),
        help="master start time of the system",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        dest="duration_s",
        default=None,
        help="duration in seconds, if using for recording only (to be used only by master)",
    )
    parser.add_argument(
        "--config_file",
        type=validate_path,
        default=None,
        help="path to the configuration file for the current host device, "
        "instead of the CLI arguments",
    )

    return parser


def parse_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """Parse CLI arguments and apply configuration file overrides.

    This function wraps `parser.parse_args()` to allow optional overriding
    of CLI defaults from a YAML config file (see `override_cli_args_with_config_file`)
    and to load codec specifications if required (see `load_codec_spec`).

    Args:
        parser (argparse.ArgumentParser): The parser created by `define_parser()`.

    Returns:
        argparse.Namespace: The fully-resolved CLI arguments namespace.
    """
    args = parser.parse_args()
    parser, args = override_cli_args_with_config_file(parser, args)
    args = load_codec_spec(args)
    print(HERMES)
    return args


def override_cli_args_with_config_file(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    """Override parser defaults with values from a YAML config file.

    If `args.config_file` is set, this function reads the file, performs
    environment variable substitution for patterns like `${VAR}`, and uses
    the resulting YAML mapping to set default values on the provided
    `parser`. After applying defaults the parser is re-parsed so the
    returned `args` reflect any config-file-provided values.

    Args:
        parser (argparse.ArgumentParser): The argument parser to update.
        args (argparse.Namespace): The namespace produced by the initial
            `parse_args()` call.

    Returns:
        tuple[argparse.ArgumentParser, argparse.Namespace]: The parser (with
            updated defaults) and the re-parsed args namespace.

    Exits:
        Calls `exit()` with an error message if the YAML cannot be parsed.
    """
    if args.config_file is not None:
        with open(args.config_file, "r") as f:
            try:
                config_str = f.read()
                # Replace ${VAR} with environment variable values
                for key, value in os.environ.items():
                    config_str = config_str.replace(f"${{{key}}}", value)
                config: dict = yaml.safe_load(config_str)
                parser.set_defaults(**config)
            except yaml.YAMLError as e:
                print(e)
                exit("Error parsing CLI inputs.")
        args = parser.parse_args()
    return parser, args


def load_codec_spec(args: argparse.Namespace) -> argparse.Namespace:
    """Load codec configuration YAML files into the `args.logging_spec`.

    When video/audio streaming is enabled in `args.logging_spec`, this
    function opens the corresponding codec configuration files, parses the
    YAML and constructs `VideoCodec` / `AudioCodec` objects which are
    attached back to `args.logging_spec` under the keys
    `'video_codec'` and `'audio_codec'` respectively.

    Args:
        args (argparse.Namespace): Parsed CLI arguments containing a
            `logging_spec` mapping with codec filepaths.

    Returns:
        argparse.Namespace: The same `args` object with codec objects
            injected into `args.logging_spec` when applicable.
    """
    if "stream_video" in args.logging_spec and args.logging_spec["stream_video"]:
        with open(args.video_codec_config_filepath, "r") as f:
            try:
                args.logging_spec["video_codec"] = VideoCodec(**yaml.safe_load(f))
            except yaml.YAMLError as e:
                print(e)
    if "stream_audio" in args.logging_spec and args.logging_spec["stream_audio"]:
        with open(args.audio_codec_config_filepath, "r") as f:
            try:
                args.logging_spec["audio_codec"] = AudioCodec(**yaml.safe_load(f))
            except yaml.YAMLError as e:
                print(e)
    return args


def init_output_files(args: argparse.Namespace) -> tuple[float, str, str]:
    """Prepare output directories and return paths for logging files.

    This function computes the experiment `log_dir` using `args.out_dir`
    and `args.experiment`, creates the directory structure and returns the
    resolved master logging time, the log directory path and a path for a
    host-specific log history file.

    Args:
        args (argparse.Namespace): Parsed CLI arguments containing
            `out_dir`, `experiment` and `host_ip`.

    Returns:
        tuple[float, str, str]: A tuple containing `(log_time_s, log_dir,
            log_history_filepath)` where `log_time_s` is the master start time,
            `log_dir` is the directory created for logs and
            `log_history_filepath` is the per-host log filename.

    Exits:
        Calls `exit()` if the experiment directory already exists.
    """
    log_time_s = args.log_time_s if args.log_time_s is not None else get_time()
    log_dir: str = os.path.join(
        args.out_dir, *map(lambda tup: "_".join(tup), args.experiment.items())
    )
    log_history_filepath: str = os.path.join(log_dir, "%s.log" % args.host_ip)

    try:
        os.makedirs(log_dir)
    except OSError:
        exit(
            "'%s' already exists. Update experiment YML file with correct data for this subject."
            % log_dir
        )

    return log_time_s, log_dir, log_history_filepath


def configure_specs(
    args: argparse.Namespace, log_time_s: float, log_dir: str
) -> tuple[argparse.Namespace, list[dict]]:
    """Build logging specification and inject settings into node specs.

    Constructs a `LoggingSpec` object from provided arguments and updates
    each node spec in `args.producer_specs`, `args.consumer_specs` and
    `args.pipeline_specs` by populating the `settings` mapping with host
    information, ports and the `logging_spec` object. This prepares node
    specs for broker initialization.

    Args:
        args (argparse.Namespace): Parsed CLI arguments containing node
            spec lists and host information.
        log_time_s (float): Master logging start time.
        log_dir (str): Path to the directory where logs should be stored.

    Returns:
        tuple[argparse.Namespace, list[dict]]: The (possibly unchanged) args
            object and a flat list of node spec dictionaries ready to be
            consumed by the `Broker`.
    """
    logging_spec = LoggingSpec(
        log_dir=log_dir,
        log_time_s=log_time_s,
        ref_time_s=get_ref_time(),
        experiment=args.experiment,
        **args.logging_spec,
    )

    node_specs: list[dict] = (
        args.producer_specs + args.consumer_specs + args.pipeline_specs
    )
    for spec in node_specs:
        spec["settings"]["host_ip"] = args.host_ip
        spec["settings"]["logging_spec"] = logging_spec
        spec["settings"]["port_pub"] = PORT_BACKEND
        spec["settings"]["port_sub"] = PORT_FRONTEND
        spec["settings"]["port_sync"] = PORT_SYNC_HOST
        spec["settings"]["port_killsig"] = PORT_KILL

    return args, node_specs


def app():
    """Main entry point for the HERMES CLI application.

    This function wires together argument parsing, output directory
    creation, node specification configuration, and broker lifecycle
    management. When executed as the master broker it spawns the broker
    in a background thread and listens for a terminal 'q' input to
    gracefully terminate the experiment.
    """
    parser = define_parser()
    args = parse_args(parser)
    log_time_s, log_dir, log_history_filepath = init_output_files(args)
    args, node_specs = configure_specs(args, log_time_s, log_dir)

    # Create the broker and manage all the components of the experiment.
    local_broker: Broker = Broker(
        host_ip=args.host_ip,
        node_specs=node_specs,
        is_master_broker=args.is_master_broker,
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

    # Only the master broker can terminate the experiment via the terminal command.
    if args.is_master_broker:
        is_quit = False
        # Run broker's main until user exits in GUI or 'q' in terminal.
        t = threading.Thread(
            target=launch_callable, args=(local_broker, args.duration_s)
        )
        t.start()
        while not is_quit and not local_broker.is_done():
            try:
                is_quit = inputimeout(prompt="Enter 'q' to exit: ", timeout=5) == "q"
            except TimeoutOccurred:
                continue
        local_broker.set_is_quit()
        t.join()
    else:
        local_broker()


if __name__ == "__main__":
    app()
