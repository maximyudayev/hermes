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

from multiprocessing import Event, set_start_method
from multiprocessing.synchronize import Event as _EventClass
import subprocess
import threading
import os
import sys
import yaml
import json
import argparse
import platform

from hermes.__version__ import __version__
from hermes.base.broker.broker import Broker
from hermes.utils.argparse_utils import ParseExperimentKwargs, validate_path
from hermes.utils.time_utils import get_ref_time, get_time
from hermes.utils.zmq_utils import (
    PORT_BACKEND,
    PORT_FRONTEND,
    PORT_KILL,
    PORT_SYNC_HOST,
)
from hermes.utils.types import LoggingSpec, VideoCodec, AudioCodec, VideoFormatEnum


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
    "Copyright (c) 2024-2026 Maxim Yudayev and KU Leuven eMedia Lab.\n"
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
        "-e",
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
        "-f",
        type=validate_path,
        default=None,
        help="path to the configuration file for the current host device, "
        "instead of the CLI arguments",
    )
    parser.add_argument(
        "--json",
        "-j",
        default=None,
        help="serialized JSON configuration for slave host setup by master over SSH",
    )

    return parser


def parse_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """Parse CLI arguments and apply configuration file overrides.

    This function wraps `parser.parse_args()` to allow optional provision
    of configuration from a YAML config file (see `parse_config_file`)
    or from a JSON string (see `parse_json_string`),
    and to load codec specifications if required (see `load_codec_spec`).
    It also validates the parsed configuration for completeness of required fields.

    Args:
        parser (argparse.ArgumentParser): The parser created by `define_parser()`.

    Returns:
        argparse.Namespace: The fully-resolved CLI arguments namespace.

    Raises:
        Exception: If neither `--config_file` nor `--json` is provided.
    """
    args = parser.parse_args()

    if args.config_file is not None:
        parser, args = parse_config_file(parser, args)
    elif args.json is not None:
        parser, args = parse_json_string(parser, args)
    else:
        raise Exception("Either `--config_file` or `--json` must be provided.", "Got: \n", vars(args))

    # TODO: use pydantic to validate args here

    args = load_codec_spec(args)
    print(HERMES, flush=True)
    return args


def parse_config_file(
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
    with open(args.config_file, "r") as f:
        try:
            config_str = f.read()
            config_str = inject_env_vars(config_str)
            config: dict = yaml.safe_load(config_str)
            parser.set_defaults(**config)
        except yaml.YAMLError as e:
            print(e, flush=True)
            exit("Error parsing YAML file.")
    args = parser.parse_args()
    return parser, args


def parse_json_string(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    """Override parser defaults with values from a JSON config string.

    If `args.json` is set, this function reads the JSON string, performs
    environment variable substitution for patterns like `${VAR}`, and uses
    the resulting JSON mapping to set default values on the provided
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
        Calls `exit()` with an error message if the JSON cannot be parsed.
    """
    try:
        config_str = args.json
        config_str = inject_env_vars(config_str)
        config: dict = json.loads(config_str)
        parser.set_defaults(**config)
    except json.JSONDecodeError as e:
        print(e, flush=True)
        exit("Error parsing JSON string.")
    args = parser.parse_args()
    return parser, args


def inject_env_vars(config_str: str) -> str:
    """Replace environment variable placeholders with corresponding values.

    This function searches for patterns like `${VAR}` in the provided configuration
    string and replaces them with the corresponding environment variable values.

    Args:
        config_str (str): The configuration string potentially containing
            environment variable patterns.

    Returns:
        str: The same configuration string with environment variables injected in place of placeholders.
    """
    for key, value in os.environ.items():
        config_str = config_str.replace(f"${{{key}}}", value)
    return config_str


def replace_video_format_nested(config: dict) -> dict:
    """Recursively replace `video_image_format` strings with enum values.

    Args:
        config (dict): A node specification dictionary potentially containing the key.
    """
    if "video_image_format" in config:
        config["video_image_format"] = VideoFormatEnum[config["video_image_format"]]
        return config

    for key, value in config.items():
        if isinstance(value, dict):
            config[key] = replace_video_format_nested(value)

    return config


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
            # Replace `video_image_format` with appropriate enum value
            args.producer_specs = [
                replace_video_format_nested(spec) for spec in args.producer_specs
            ]
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
        tuple[argparse.Namespace, list[dict], float]: The (possibly unchanged)
            args object, a flat list of node spec dictionaries ready to be
            consumed by the `Broker`, host device's reference time for performance
            counters.
    """
    ref_time_s = get_ref_time()
    logging_spec = LoggingSpec(
        log_dir=log_dir,
        log_time_s=log_time_s,
        ref_time_s=ref_time_s,
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

    return args, node_specs, ref_time_s


def parse_stdin(
    broker: Broker,
    is_master: bool,
    is_ready_event: _EventClass,
    is_done_event: _EventClass,
    is_quit_event: _EventClass
) -> None:
    """Parse user keyboard inputs into a fanout queue for HERMES nodes.
    
    Blocking stdin capture loop as a daemon, that fans out keyboard inputs
    to Broker's subprocesses and all the Nodes.
    On Windows, daemon threads get cleaned up automatically on Python interpreter exit.
    On Linux/Mac, uses select on the system stdin to avoid blocking indefinitely. 

    Args:
        broker (Broker): Host's only HERMES instance. 
        is_master (bool): Whether the Broker is the master in the setup.
        is_ready_event (Event): Synchronization flag whether the Broker and its subprocesses finished setting up.
        is_done_event (Event): Synchronization flag whether the Broker is done and gracefully wrapped up.
        is_quit_event (Event): Synchronization flag to indicate to the Broker to start the graceful quit procedure.
    """
    user_input = ""
    termination_char = "Q"
    # is_ready_event.wait()  # NOTE: deadlocks if a Node requires user input during the bring-up process.
    if platform.system() == 'Windows':
        while not is_done_event.is_set():
            user_input = input(">> ")
            if is_master and user_input == termination_char:
                is_quit_event.set()
            elif len(user_input):
                broker._fanout_user_input((get_time(), user_input))
    else:
        import select
        while not is_done_event.is_set():
            ready, _, _ = select.select([sys.stdin], [], [], 5.0)
            if ready:
                user_input = sys.stdin.readline().strip()
                if is_master and user_input == termination_char:
                    is_quit_event.set()
                elif len(user_input):
                    broker._fanout_user_input((get_time(), user_input))


def launch_slave_hosts(
    connections: list[dict], log_time_s: float, experiment: dict[str, str]
) -> list[subprocess.Popen]:
    """Launch slave HERMES hosts over SSH, each in a new interactive terminal window.

    This function constructs SSH commands to connect to each slave host
    specified in `connections` of the master's YAML config file.
    It parses slave config YAML files of each listed host, constructs the corresponding command that
    activates the remote host's Python virtual environment on each slave host,
    and runs `hermes-cli` with appropriate arguments in an interactive shell to accept user keyboard inputs.

    Args:
        connections (list[dict]): List of connection specifications for
            each slave host, including SSH credentials and paths.
        log_time_s (float): Master logging start time to pass to slaves.
        experiment (dict[str, str]): Experiment key-value pairs to pass to slaves.

    Returns:
        list[subprocess.Popen]: List of subprocess handles for the launched slave hosts.
    """

    experiment_str = ' '.join([f"{k}={v}" for k,v in experiment.items()])
    cmds = []
    for conn in connections:
        with open(conn["config_filepath"], "r") as f:
            try:
                config_str = f.read()
                config: dict = yaml.safe_load(config_str)
                cmds.append([
                    f"{conn['ssh_username']}@{conn['ssh_host_ip']}",
                    f"cd {'/d' if conn['platform'] == 'Windows' else ''} {conn['project_dir']} &&",
                    'call .venv\\Scripts\\activate.bat' if conn['platform'] == 'Windows' else '. .venv/bin/activate', " &&",
                    f"hermes-cli -o {conn['output_dir']} -t {log_time_s} -e {experiment_str} -j {json.dumps(config)} &&",
                    "exit",
                ])
            except yaml.YAMLError as e:
                print(e, flush=True)
                exit("Error parsing slave YAML files.")

    if platform.system() == "Windows":
        prog = "cmd /k"
    elif platform.system() == "Linux":
        prog = "gnome-terminal --"
    elif platform.system() == "Darwin":
        prog = "open -a Terminal"

    procs = []
    for cmd in cmds:
        procs.append(
            subprocess.Popen([
                prog,
                "ssh", "-tt",
                "-o", "TCPKeepAlive=no",
                "-o", "ServerAliveInterval=30",
                cmd
            ], creationflags=subprocess.CREATE_NEW_CONSOLE)
        )
    return procs


def app():
    """Main entry point for the HERMES CLI application.

    This function wires together argument parsing, output directory
    creation, node specification configuration, and broker lifecycle
    management. When executed as the master broker it spawns the broker
    in a background thread and listens for a terminal 'Q' input to
    gracefully terminate the experiment.
    """
    parser = define_parser()
    args = parse_args(parser)
    log_time_s, log_dir, log_history_filepath = init_output_files(args)
    args, node_specs, ref_time_s = configure_specs(args, log_time_s, log_dir)

    set_start_method("spawn")

    # Launch slave hosts over SSH if the current broker is master and any connections are specified.
    if args.is_master_broker and args.connections:
        slave_procs = launch_slave_hosts(args.connections, log_time_s, args.experiment)

    is_ready_event = Event()
    is_quit_event = Event()
    is_done_event = Event()

    # Create the broker and manage all the components of the experiment.
    local_broker: Broker = Broker(
        host_ip=args.host_ip,
        node_specs=node_specs,
        is_ready_event=is_ready_event,
        is_quit_event=is_quit_event,
        is_done_event=is_done_event,
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

    stdin_thread = threading.Thread(
        target=parse_stdin,
        args=(
            local_broker,
            args.is_master_broker,
            is_ready_event,
            is_done_event,
            is_quit_event,
        ),
        daemon=True
    )
    stdin_thread.start()

    # Only master host runs with duration, others wait for commands.
    if args.is_master_broker:
        local_broker(args.duration_s)
    else:
        local_broker()

    if args.is_master_broker and args.connections:
        for proc in slave_procs: proc.wait()


if __name__ == "__main__":
    app()
