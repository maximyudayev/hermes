import os
from utils.time_utils import *
from utils.print_utils import *
from sensor_streamer_handlers import StreamerManager

# Note that multiprocessing requires the __main__ check.
if __name__ == '__main__':
  #################
  # CONFIGURATION #
  #################

  # Configure printing and logging.
  print_status: bool = True
  print_debug: bool = True

  # Configure trial
  subject_id: int = 1 # UID of the subject
  trial_id: int = 1 # UID of the trial
  is_real: bool = False # Data collection from actual trials

  # Configure network topology
  ip_wearablePC: str = "192.168.69.101"
  ip_labPC: str = "192.168.69.100"

  # Define all the streamers in the experiment.
  sensor_streamers_local = dict([
    # Use one of the following to control the experiment (enter notes, quit, etc)
    ('ExperimentControlStreamer', False),  # A GUI to label activities/calibrations and enter notes
    # Sensors!
    ('AwindaStreamer',     True),  # The Awinda body tracking system (includes the Manus finger-tracking gloves if connected to Xsens)
    ('DotsStreamer',       True),   # The Dots lower limb tracking system
    ('EyeStreamer',        True),  # The Pupil Labs eye-tracking headset
    ('MicrophoneStreamer', False),  # One or more microphones
    ('CameraStreamer',     False),  # One or more cameras
    ('InsoleStreamer',     True),  # The Moticon pressure insoles 
    ('DummyStreamer',      False),  # Dummy data (no hardware required)
  ])
  # Configure settings for each streamer.
  sensor_streamer_specs = [
    # Allow the experimenter to label data and enter notes.
    {'class': 'ExperimentControlStreamer',
     'activities': [ # Cybathlon activities that you want to label
       'Balance beam',
       'Stairs',
       'Step over',
       'Slopes',
       'Bench and table',
       'Wobbly steps',
       'High step',
       'Ladder',
       'Cross country',
       'Hurdles',
     ],
     'print_debug': print_debug, 'print_status': print_status
     },
    # Stream from the Awinda body tracking and Manus gloves.
    {'class': 'AwindaStreamer',
     'print_debug': print_debug, 'print_status': print_status
     },
    # Stream from the Dots lower limb tracking.
    {'class': 'DotsStreamer',
     'print_debug': print_debug, 'print_status': print_status
     },
    # Stream from the Pupil Labs eye tracker, including gaze and video data.
    {'class': 'EyeStreamer',
     'stream_video_world'    : False, # the world video
     'stream_video_worldGaze': True, # the world video with gaze indication overlayed
     'stream_video_eye'      : False, # video of the eye
     'is_binocular'          : True, # uses both eyes for gaze data and for video
     'print_debug': print_debug, 'print_status': print_status
     },
    # Stream from one or more cameras.
    {'class': 'CameraStreamer',
     'cameras_to_stream': { # map camera names (usable as device names in the HDF5 file) to capture device indexes
       'basler_north': 0,
       'basler_south': 1,
       'basler_east': 2,
       'basler_west': 3,
     },
     'print_debug': print_debug, 'print_status': print_status
     },
     # Insole pressure sensor.
    {'class': 'InsoleStreamer',
     'print_debug': print_debug, 'print_status': print_status
     },
    # Stream from one or more microphones.
    {'class': 'MicrophoneStreamer',
     'device_names_withAudioKeywords': {'microphone_conference': 'USB audio CODEC'},
     'print_debug': print_debug, 'print_status': print_status
     },
    # Dummy data.
    {'class': 'DummyStreamer',
     'update_period_s': 0.1,
     'print_debug': print_debug, 'print_status': print_status
     },
  ]
  # Remove disabled streamers.
  sensor_streamer_specs_local = [spec for spec in sensor_streamer_specs
                                if spec['class'] in sensor_streamers_local
                                and sensor_streamers_local[spec['class']]]

  # Define localworkers.
  workers = dict([
    ('DataLogger',        True),
    ('DataVisualizer',    False),
  ])

  # Configure where and how to save sensor data.
  #   Adjust enable_data_logging, log_tag, and log_dir_root as desired.
  trial_type: str = 'real' if is_real else 'test' # recommend 'tests' and 'experiments' for testing vs "real" data
  script_dir: str = os.path.dirname(os.path.realpath(__file__))
  (log_time_str, log_time_s) = get_time_str(return_time_s=True)
  log_tag: str = 'aidWear-wearables'
  log_dir_root: str = os.path.join(script_dir, '..', '..', 'data',
                              trial_type,
                              '{0}_S{1}_{2}'.format(get_time_str(format='%Y-%m-%d'), str(subject_id).zfill(3), str(trial_id).zfill(2)))
  log_subdir: str = '%s_%s' % (log_time_str, log_tag)
  log_dir: str = os.path.join(log_dir_root, log_subdir)
  datalogging_options = {
    'log_dir': log_dir, 'log_tag': log_tag,
    'use_external_recording_sources': False,
    'videos_in_hdf5': False,
    'audio_in_hdf5': False,
    # Choose whether to periodically write data to files.
    'stream_hdf5' : True, # recommended over CSV since it creates a single file
    'stream_csv'  : False, # will create a CSV per stream
    'stream_video': True,
    'stream_audio': True,
    'stream_period_s': 5, # how often to save streamed data to disk
    'clear_logged_data_from_memory': True, # ignored if dumping is also enabled below
    # Choose whether to write all data at the end.
    'dump_csv'  : False,
    'dump_hdf5' : True,
    'dump_video': True,
    'dump_audio': False,
    # Additional configuration.
    'videos_format': 'avi', # mp4 occasionally gets openCV errors about a tag not being supported?
    'audio_format' : 'wav', # currently only supports WAV
    'print_status': print_status, 'print_debug': print_debug
  }
  # Initialize a file for writing the log history of all printouts/messages.
  log_history_filepath: str = os.path.join(log_dir, '%s_log_history.txt' % log_time_str)
  os.makedirs(log_dir, exist_ok=True)
  
  # Find the camera names for future use.
  camera_streamer_index: int = ['CameraStreamer' in spec['class'] for spec in sensor_streamer_specs].index(True)
  camera_names: list[str] = list(sensor_streamer_specs[camera_streamer_index]['cameras_to_stream'].keys())

  # Configure visualization.
  composite_frame_size = (1800, 3000)
  composite_col_width_quater = int(composite_frame_size[1]/4)
  composite_col_width_third = int(composite_frame_size[1]/3)
  composite_row_height = int(composite_frame_size[0]/6)
  visualization_options = {
    'visualize_streaming_data'       : True,
    'visualize_all_data_when_stopped': True,
    'wait_while_visualization_windows_open': False,
    'update_period_s': 0.2,
    'classes_to_visualize': ['DotsStreamer', 'AwindaStreamer', 'EyeStreamer', 'CameraStreamer'],
    'use_composite_video': True,
    'composite_video_filepath': os.path.join(log_dir, 'composite_visualization') if log_dir is not None else None,
    'composite_video_layout': [
      [ # row  0
        {'device_name':'dots-imu', 'stream_name':'acceleration-x', 'rowspan':1, 'colspan':1, 'width':composite_col_width_third, 'height':composite_row_height},
        {'device_name':'dots-imu', 'stream_name':'acceleration-y', 'rowspan':1, 'colspan':1, 'width':composite_col_width_third, 'height':composite_row_height},
        {'device_name':'dots-imu', 'stream_name':'acceleration-z', 'rowspan':1, 'colspan':1, 'width':composite_col_width_third, 'height':composite_row_height},
      ],
      [ # row  1
        {'device_name':'dots-imu', 'stream_name':'gyroscope-x', 'rowspan':1, 'colspan':1, 'width':composite_col_width_third, 'height':composite_row_height},
        {'device_name':'dots-imu', 'stream_name':'gyroscope-y', 'rowspan':1, 'colspan':1, 'width':composite_col_width_third, 'height':composite_row_height},
        {'device_name':'dots-imu', 'stream_name':'gyroscope-z', 'rowspan':1, 'colspan':1, 'width':composite_col_width_third, 'height':composite_row_height},
      ],
      [ # row  2 a column for each 4 cameras
        {'device_name':camera_name, 'stream_name':'frame', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quater, 'height':composite_row_height} for camera_name in camera_names
      ],
    ]
  }
  visualization_options['print_debug'] = print_debug
  visualization_options['print_status'] = print_status
  visualization_options['log_history_filepath'] = log_history_filepath

  ##################
  # PROCESS LAUNCH #
  ##################
  # Create all desired locally connected producers.
  # Create requested SensorStreamers.
  streamer_manager = StreamerManager(ip=ip_wearablePC,
                                     sensor_streamer_specs_local=sensor_streamer_specs_local,
                                     sensor_streamer_specs_all=sensor_streamer_specs_local,
                                     workers=workers,
                                     log_history_filepath=log_history_filepath,
                                     datalogging_options=datalogging_options)

  # Expose local wearable data to remote subscribers like lab PC
  streamer_manager.expose_to_remote_sub()

  # Run proxy/server's main
  StreamerManager.run(duration_s=None)
