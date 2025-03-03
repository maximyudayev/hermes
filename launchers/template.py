from utils.time_utils import *
from nodes.Broker import Broker
from utils.zmq_utils import *
from sensor_configs.AidWear import *

# Note that multiprocessing requires the __main__ check.
if __name__ == '__main__':
  # Define locally connected streamers.
  producers = dict([
    # Use one of the following to control the experiment (enter notes, quit, etc)
    ('ExperimentControlStreamer', False),  # A GUI to label activities/calibrations and enter notes
    # Sensors!
    ('AwindaStreamer',     False),  # The Awinda body tracking system (includes the Manus finger-tracking gloves if connected to Xsens)
    ('DotsStreamer',       False),  # The Dots lower limb tracking system
    ('EyeStreamer',        False),  # The Pupil Labs eye-tracking headset
    ('MicrophoneStreamer', False),  # One or more microphones
    ('CameraStreamer',     False),  # One or more cameras
    ('InsoleStreamer',     False),  # The Moticon pressure insoles
    ('TmsiStreamer',       False),
  ])
  # Remove disabled streamers.
  local_producer_specs = [spec for spec in producer_specs 
                          if spec['class'] in producers
                          and producers[spec['class']]]

  # Define local workers/consumers of data.
  consumers = dict([
    ('DataLogger',        False), # NOTE: Use logger and visualizer mutually exclusively, both contain a Logger inside.
    ('DataVisualizer',    False),
  ])

  classes_to_log = [
    'DotsStreamer', 
    'EyeStreamer', 
    'InsoleStreamer', 
    'CameraStreamer',
    ]
  classes_to_visualize = [
    'DotsStreamer',
    'EyeStreamer',
    'InsoleStreamer',
    'CameraStreamer',
    ]

  # For now pass streamer specs (local and remote) to subscribers manually.
  producer_specs_logger = [spec for spec in producer_specs 
                            if spec['class'] in classes_to_log]
  producer_specs_visualizer = [spec for spec in producer_specs 
                                if spec['class'] in classes_to_visualize]

  # Configure settings for each worker/consumer of data.
  local_consumer_specs = [
    {'class': 'DataLogger',
     'streamer_specs': producer_specs_logger,
     **logging_spec,
     'log_history_filepath': log_history_filepath,
     'print_debug': print_debug, 'print_status': print_status 
     },
    {'class': 'DataVisualizer',
     'streamer_specs': producer_specs_visualizer,
     **logging_spec,
     **visualization_spec,
     'log_history_filepath': log_history_filepath,
     'print_debug': print_debug, 'print_status': print_status
     },
  ]
  local_consumer_specs = [spec for spec in local_consumer_specs
                          if spec['class'] in consumers
                          and consumers[spec['class']]]

  # TODO: add Pipeline nodes (e.g. AI worker).
  local_pipeline_specs = []

  ############################
  ###### PROCESS LAUNCH ######
  ############################
  # Create the broker and manage all the components of the experiment.
  stream_broker: Broker = Broker(ip=IP_STATION,
                                 node_specs=local_producer_specs+local_consumer_specs+local_pipeline_specs,
                                 print_status=print_status, 
                                 print_debug=print_debug)
  # Run broker's main until user exits in GUI or Ctrl+C in terminal.
  stream_broker(duration_s=None)
