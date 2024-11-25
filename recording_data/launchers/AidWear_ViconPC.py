import os
import sys
sys.path.append('C:\\Users\\Vicon\\LiveStream Vicon\\AidWear\\recording_data')

from utils.time_utils import *
from handlers.StreamBroker import StreamBroker

# Note that multiprocessing requires the __main__ check.
if __name__ == '__main__':
  ###########################
  ###### CONFIGURATION ######
  ###########################
  # TODO (non-critical): move all configuration into config.py file w/o __name__=='__main__'.
  # Configure printing and logging.
  print_status: bool = True
  print_debug: bool = True

  # Configure trial.
  subject_id: int = 1 # UID of the subject
  trial_id: int = 1 # UID of the trial
  is_real: bool = False # Data collection from actual trials

  # Configure network topology.
  ip_wearablePC: str = "192.168.69.101"
  ip_labPC: str = "10.244.21.115"

  # Define locally connected streamers.
  sensor_streamers = dict([
    ('ViconStreamer',       True),
  ])
  # Configure settings for each streamer.
  sensor_streamer_specs = [
     # TMSi SAGA stream
    {'class': 'ViconStreamer',
     'print_debug': print_debug, 'print_status': print_status
     },
  ]
  # Remove disabled streamers.
  streamer_specs = [spec for spec in sensor_streamer_specs 
                      if spec['class'] in sensor_streamers
                      and sensor_streamers[spec['class']]]

  # Define local workers/consumers of data.
  workers = dict([
    ('DataLogger',        True),
  ])
  # Configure where and how to save sensor data.
  #   Adjust log_tag, and log_dir_root as desired.
  trial_type: str = 'real' if is_real else 'test' # recommend 'tests' and 'experiments' for testing vs "real" data
  log_tag: str = 'aidWear-wearables'

  script_dir: str = os.path.dirname(os.path.realpath(__file__))
  (log_time_str, log_time_s) = get_time_str(return_time_s=True)
  log_dir_root: str = os.path.join(script_dir, '..', '..', 'data',
                              trial_type,
                              '{0}_S{1}_{2}'.format(get_time_str(format='%Y-%m-%d'), 
                                                    str(subject_id).zfill(3), 
                                                    str(trial_id).zfill(2)))
  log_subdir: str = '%s_%s' % (log_time_str, log_tag)
  log_dir: str = os.path.join(log_dir_root, log_subdir)
  # Initialize a file for writing the log history of all printouts/messages.
  log_history_filepath: str = os.path.join(log_dir, '%s_log_history.txt' % (log_time_str))
  os.makedirs(log_dir, exist_ok=True)

  datalogging_options = {
    'classes_to_log': [
      'ViconStreamer'
      ],
    'log_dir': log_dir, 'log_tag': log_tag,
    'use_external_recording_sources': False,
    'videos_in_hdf5': False,
    'audio_in_hdf5': False,
    # Choose whether to periodically write data to files.
    'stream_hdf5' : True, # recommended over CSV since it creates a single file
    'stream_csv'  : False, # will create a CSV per stream
    'stream_video': False,
    'stream_audio': False,
    'stream_period_s': 10, # how often to save streamed data to disk
    'clear_logged_data_from_memory': True, # ignored if dumping is also enabled below
    # Choose whether to write all data at the end.
    'dump_csv'  : False,
    'dump_hdf5' : True,
    'dump_video': False,
    'dump_audio': False,
    # Additional configuration.
    'videos_format': 'avi', # mp4 occasionally gets openCV errors about a tag not being supported?
    'audio_format' : 'wav', # currently only supports WAV
  }



  # For now pass streamer specs (local and remote) to subscribers manually.
  # TODO (non-critical): switch to REQ-REP model where subscribers ask details about available streams and their configurations to the broker.
  streamer_specs_logger = [spec for spec in sensor_streamer_specs 
                            if spec['class'] in datalogging_options['classes_to_log']]


  # Configure settings for each worker/consumer of data.
  worker_specs = [
    {'class': 'DataLogger',
     **datalogging_options,
     'streamer_specs': streamer_specs_logger,
     'log_history_filepath': log_history_filepath,
     'print_debug': print_debug, 'print_status': print_status
     },
  ]
  worker_specs = [spec for spec in worker_specs
                    if spec['class'] in workers
                    and workers[spec['class']]]

  ############################
  ###### PROCESS LAUNCH ######
  ############################
  # Create the broker and manage all the components of the experiment.
  stream_broker: StreamBroker = StreamBroker(ip=ip_labPC,
                                             streamer_specs=streamer_specs,
                                             worker_specs=worker_specs,
                                             print_status=print_status, 
                                             print_debug=print_debug)
  # Connect broker to remote publishers at the wearable PC to get data from the wearable sensors.
  stream_broker.connect_to_remote_pub(addr=ip_wearablePC)
  # Start all subprocesses
  stream_broker.start()
  # Run broker's main until user exits in GUI or Ctrl+C in terminal.
  stream_broker.run(duration_s=None)