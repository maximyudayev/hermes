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

import threading
import os
import yaml
import argparse

from hermes.base.broker.broker import Broker
from hermes.utils.argparse_utils import ParseExperimentKwargs, validate_path
from hermes.utils.mp_utils import launch_callable
from hermes.utils.time_utils import get_time
from hermes.utils.zmq_utils import PORT_BACKEND, PORT_FRONTEND, PORT_KILL, PORT_SYNC_HOST


# TODO: replace with HERMES-branded font
HERMES = r"""
______  ________________________  ___________________
___  / / /__  ____/__  __ \__   |/  /__  ____/_  ___/
__  /_/ /__  __/  __  /_/ /_  /|_/ /__  __/  _____ \ 
_  __  / _  /___  _  _, _/_  /  / / _  /___  ____/ / 
/_/ /_/  /_____/  /_/ |_| /_/  /_/  /_____/  /____/  
                                                     
"""
VERSION = 'v0.1.1'
DESCRIPTION = HERMES + \
              'Heterogeneous edge realtime measurement and execution system '\
              'for continual multimodal data acquisition and AI processing.'
EPILOG = 'Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab.\n' \
         'Created 2024-2025 at KU Leuven for the AidWear, AID-FOG, and RevalExo ' \
         'projects of prof. Bart Vanrumste, by Maxim Yudayev [https://yudayev.com].'

def define_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog='HERMES',
                                   description=DESCRIPTION,
                                   epilog=EPILOG,
                                   formatter_class=argparse.RawTextHelpFormatter)
  parser.add_argument('--verbose', '-v',
                      action='count',
                      default=0,
                      help='increase level of logging verbosity [0,3]')
  parser.add_argument('--version',
                      action='version',
                      version='%(prog)s ' + VERSION)

  parser.add_argument('--out_dir', '-o',
                      type=validate_path,
                      dest='out_dir',
                      required=True,
                      help='path to the output directory of the current host device')
  parser.add_argument('--experiment',
                      nargs='*',
                      action=ParseExperimentKwargs,
                      help='key-value pair tags detailing the experiment, used for '
                           'directory creation and metadata on files')
  parser.add_argument('--time', '-t',
                      type=float,
                      dest='log_time_s',
                      default=get_time(),
                      help='master start time of the system')
  parser.add_argument('--duration', '-d',
                      type=int,
                      dest='duration_s',
                      default=None,
                      help='duration in seconds, if using for recording only (to be used only by master)')
  parser.add_argument('--config_file',
                      type=validate_path,
                      default=None,
                      help='path to the configuration file for the current host device, '
                           'instead of the CLI arguments')

  # parser.add_argument('--host_ip',
  #                     type=validate_ip,
  #                     help='LAN IPv4 address of the host device')
  # parser.add_argument('--is_master',
  #                     dest='is_master_broker',
  #                     action='store_true',
  #                     help='flag to set host as Master Broker that others connect to')
  # parser.add_argument('--subscriber_ips',
  #                     nargs='*',
  #                     dest='remote_subscriber_ips',
  #                     type=validate_ip,
  #                     default=list(),
  #                     help='list of IPv4 devices listening to data of the host')
  # parser.add_argument('--publisher_ips',
  #                     nargs='*',
  #                     dest='remote_publisher_ips',
  #                     type=validate_ip,
  #                     default=list(),
  #                     help='list of IPv4 devices to listen to for their data')
  # parser.add_argument('--kill',
  #                     dest='is_remote_kill',
  #                     action='store_true',
  #                     help='flag to set host to listen to remote KILLSIG (only for slave devices)')
  # parser.add_argument('--kill_ip',
  #                     dest='remote_kill_ip',
  #                     type=validate_ip,
  #                     help='LAN IPv4 address of device delegating KILLSIG (only for slave devices)')


  # parser.add_argument('--logging_spec',
  #                     nargs='*',
  #                     action=ParseLoggingKwargs,
  #                     help='key-value pair tags configuring logging modules of each Node')

  # parser.add_argument('--producer_specs',
  #                     nargs='*',
  #                     action=ParseNodeKwargs,
  #                     default=list(),
  #                     help='key-value pair tags detailing local producer Nodes of the host')
  # parser.add_argument('--consumer_specs',
  #                     nargs='*',
  #                     action=ParseNodeKwargs,
  #                     default=list(),
  #                     help='key-value pair tags detailing local consumer Nodes of the host')
  # parser.add_argument('--pipeline_specs',
  #                     nargs='*',
  #                     action=ParseNodeKwargs,
  #                     default=list(),
  #                     help='key-value pair tags detailing local pipeline Nodes of the host')

  return parser


def parse_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
  args = parser.parse_args()
  parser, args = override_cli_args_with_config_file(parser, args)
  args = load_codec_spec(args)
  print(HERMES)
  return args


def override_cli_args_with_config_file(parser: argparse.ArgumentParser, args: argparse.Namespace) -> tuple[argparse.ArgumentParser, argparse.Namespace]:
  if args.config_file is not None:
    with open(args.config_file, "r") as f:
      try:
        config: dict = yaml.safe_load(f)
        parser.set_defaults(**config)
      except yaml.YAMLError as e:
        print(e)
        exit('Error parsing CLI inputs.')
    args = parser.parse_args()
  return parser, args


def load_codec_spec(args: argparse.Namespace) -> argparse.Namespace:
  if 'stream_video' in args.logging_spec and args.logging_spec['stream_video']:
    with open(args.logging_spec['video_codec_config_filepath'], "r") as f:
      try:
        args.logging_spec['video_codec'] = yaml.safe_load(f)
      except yaml.YAMLError as e:
        print(e)
  if 'stream_audio' in args.logging_spec and args.logging_spec['stream_audio']:
    with open(args.logging_spec['audio_codec_config_filepath'], "r") as f:
      try:
        args.logging_spec['audio_codec'] = yaml.safe_load(f)
      except yaml.YAMLError as e:
        print(e)
  return args


def init_output_files(args: argparse.Namespace) -> tuple[float, str, str]:
  log_time_s = args.log_time_s if args.log_time_s is not None else get_time()
  log_dir: str = os.path.join(args.out_dir,
                              'data',
                              *map(lambda tup: '_'.join(tup), args.experiment.items()))
  log_history_filepath: str = os.path.join(log_dir, '%s.log'%args.host_ip)

  try:
    os.makedirs(log_dir)
  except OSError:
    exit("'%s' already exists. Update experiment YML file with correct data for this subject."%log_dir)

  return log_time_s, log_dir, log_history_filepath


def configure_specs(args: argparse.Namespace,
                    log_time_s: float,
                    log_dir: str,
                    log_history_filepath: str) -> tuple[argparse.Namespace, list[dict]]:
  args.logging_spec['log_dir'] = log_dir
  args.logging_spec['experiment'] = args.experiment
  args.logging_spec['log_time_s'] = log_time_s

  node_specs: list[dict] = args.producer_specs + args.consumer_specs + args.pipeline_specs
  for spec in node_specs:
    spec['settings']['logging_spec'] = args.logging_spec
    spec['settings']['log_history_filepath'] = log_history_filepath
    spec['settings']['host_ip'] = args.host_ip
    spec['settings']['port_pub'] = PORT_BACKEND
    spec['settings']['port_sub'] = PORT_FRONTEND
    spec['settings']['port_sync'] = PORT_SYNC_HOST
    spec['settings']['port_killsig'] = PORT_KILL

  return args, node_specs


def app():
  parser = define_parser()
  args = parse_args(parser)
  log_time_s, log_dir, log_history_filepath = init_output_files(args)
  args, node_specs = configure_specs(args, log_time_s, log_dir, log_history_filepath)

  # Create the broker and manage all the components of the experiment.
  local_broker: Broker = Broker(host_ip=args.host_ip,
                                node_specs=node_specs,
                                is_master_broker=args.is_master_broker)

  # Connect broker to remote publishers at the wearable PC to get data from the wearable sensors.
  for ip in args.remote_publisher_ips:
    local_broker.connect_to_remote_broker(addr=ip)

  # Expose local wearable data to remote subscribers (e.g. lab PC in AidFOG project).
  if args.remote_subscriber_ips:
    local_broker.expose_to_remote_broker(args.remote_subscriber_ips)

  # Subscribe to the KILL signal of a remote machine.
  if args.is_remote_kill:
    local_broker.subscribe_to_killsig(addr=args.remote_kill_ip)

  # Only the master broker can terminate the experiment via the terminal command.
  if args.is_master_broker:
    is_quit = False
    # Run broker's main until user exits in GUI or 'q' in terminal.
    t = threading.Thread(target=launch_callable, args=(local_broker, args.duration_s))
    t.start()
    while not is_quit:
      is_quit = input("Enter 'q' to exit: ") == 'q'
    local_broker.set_is_quit()
    t.join()
  else:
    local_broker()


if __name__ == '__main__':
  app()
