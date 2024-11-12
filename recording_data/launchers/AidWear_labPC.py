import os
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
  ip_labPC: str = "192.168.69.100"

  # Define locally connected streamers.
  sensor_streamers = dict([
    # Use one of the following to control the experiment (enter notes, quit, etc)
    ('ExperimentControlStreamer', False),  # A GUI to label activities/calibrations and enter notes
    # Sensors!
    ('AwindaStreamer',     False),  # The Awinda body tracking system (includes the Manus finger-tracking gloves if connected to Xsens)
    ('DotsStreamer',       False),  # The Dots lower limb tracking system
    ('EyeStreamer',        False),  # The Pupil Labs eye-tracking headset
    ('MicrophoneStreamer', False),  # One or more microphones
    ('CameraStreamer',     True),  # One or more cameras
    ('InsoleStreamer',     False),  # The Moticon pressure insoles
    ('TmsiStreamer',       False),
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
      "device_mapping": {
        "pelvis"         : "11850724",
        "upper_leg_right": "11850711",
        "lower_leg_right": "11850722",
        "foot_right"     : "11850717",
        "upper_leg_left" : "11850727",
        "lower_leg_left" : "11850708",
        "foot_left"      : "11850712",
      },
     'num_joints'        : 7,
     'sampling_rate_hz'  : 100,
     "radio_channel"     : 15,
     'print_debug': print_debug, 'print_status': print_status
     },
     # TMSi SAGA stream
    {'class': 'TmsiStreamer',
     'print_debug': print_debug, 'print_status': print_status
     },
    # Stream from the Dots lower limb tracking.
    {'class': 'DotsStreamer',
     "device_mapping": {
        "knee_right"  : "0",
        "foot_right"  : "1",
        "pelvis"      : "2",
        "knee_left"   : "3",
        "foot_left"   : "4",
      },
     'num_joints'      : 5,
     'sampling_rate_hz': 20,
     'print_debug': print_debug, 'print_status': print_status
     },
    # Stream from the Pupil Labs eye tracker, including gaze and video data.
    {'class': 'EyeStreamer',
     'pupil_capture_ip'      : 'localhost',
     'pupil_capture_port'    : '50020',
     'video_image_format'    : 'bgr',
     'gaze_estimate_stale_s' : 0.2,
     'stream_video_world'    : False, # the world video
     'stream_video_worldGaze': True, # the world video with gaze indication overlayed
     'stream_video_eye'      : False, # video of the eye
     'is_binocular'          : True, # uses both eyes for gaze data and for video
     'shape_video_world'     : (1080,720,3),
     'shape_video_eye0'      : (192,192,3),
     'shape_video_eye1'      : (192,192,3),
     'fps_video_world'       : 30.0,
     'fps_video_eye0'        : 120.0,
     'fps_video_eye1'        : 120.0,
     'print_debug': print_debug, 'print_status': print_status
     },
    # Stream from one or more cameras.
    {'class': 'CameraStreamer',
     'cameras_to_stream': { # map camera names (usable as device names in the HDF5 file) to capture device indexes
       'basler_north' : "40478064",
       'basler_east'  : "40549960",
       'basler_south' : "40549975",
       'basler_west'  : "40549976",
     },
     'camera_config_filepath': 'resources/pylon_20fps_maxres.pfs',
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
     }
  ]
  # Remove disabled streamers.
  streamer_specs = [spec for spec in sensor_streamer_specs 
                      if spec['class'] in sensor_streamers
                      and sensor_streamers[spec['class']]]

  # Define local workers/consumers of data.
  workers = dict([
    ('DataLogger',        True),
    ('DataVisualizer',    True),
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
    'classes_to_log': ['ExperimentControlStreamer', 
                       'DotsStreamer', 
                       'AwindaStreamer', 
                       'EyeStreamer', 
                       'CameraStreamer'],
    'log_dir': log_dir, 'log_tag': log_tag,
    'use_external_recording_sources': False,
    'videos_in_hdf5': False,
    'audio_in_hdf5': False,
    # Choose whether to periodically write data to files.
    'stream_hdf5' : True, # recommended over CSV since it creates a single file
    'stream_csv'  : False, # will create a CSV per stream
    'stream_video': True,
    'stream_audio': True,
    'stream_period_s': 10, # how often to save streamed data to disk
    'clear_logged_data_from_memory': True, # ignored if dumping is also enabled below
    # Choose whether to write all data at the end.
    'dump_csv'  : False,
    'dump_hdf5' : True,
    'dump_video': True,
    'dump_audio': False,
    # Additional configuration.
    'videos_format': 'avi', # mp4 occasionally gets openCV errors about a tag not being supported?
    'audio_format' : 'wav', # currently only supports WAV
  }

  # Find the camera names for future use.
  camera_streamer_index: int = ['CameraStreamer' in spec['class'] for spec in sensor_streamer_specs].index(True)
  camera_names: list[str] = list(sensor_streamer_specs[camera_streamer_index]['cameras_to_stream'].keys())

  # Configure visualization.
  composite_frame_size = (1920, 1080) # screen resolution
  composite_col_width_quarter = int(composite_frame_size[0]/4)
  composite_row_height = int(composite_frame_size[1]/5)
  visualization_options = {
    'visualize_streaming_data'       : True,
    'visualize_all_data_when_stopped': True,
    'wait_while_visualization_windows_open': False,
    'update_period_s': 0.2,
    'classes_to_visualize': ['DotsStreamer', 
                             'AwindaStreamer', 
                             'EyeStreamer', 
                             'CameraStreamer'],
    'use_composite_video': True,
    'composite_video_filepath': os.path.join(log_dir, 'composite_visualization') if log_dir is not None else None,
    'composite_video_layout': [ # first 3 rows of IMU data, next 2 of video data with Pupil Core spanning 2x2 cell and 4 PoE cameras around it
      [ # row  0
        {'device_name':'dots-imu', 'stream_name':'acceleration-x', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'dots-imu', 'stream_name':'orientation-x', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'awinda-imu', 'stream_name':'acceleration-x', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'awinda-imu', 'stream_name':'orientation-x', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
      ],
      [ # row  1
        {'device_name':'dots-imu', 'stream_name':'acceleration-y', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'dots-imu', 'stream_name':'orientation-y', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'awinda-imu', 'stream_name':'acceleration-y', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'awinda-imu', 'stream_name':'orientation-y', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
      ],
      [ # row  2
        {'device_name':'dots-imu', 'stream_name':'acceleration-z', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'dots-imu', 'stream_name':'orientation-z', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'awinda-imu', 'stream_name':'acceleration-z', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'awinda-imu', 'stream_name':'orientation-z', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
      ],
      [ # row  3 
        {'device_name':camera_names[0], 'stream_name':'frame', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':'eye-tracking-video-worldGaze', 'stream_name':'frame', 'rowspan':2, 'colspan':2, 'width':2*composite_col_width_quarter, 'height':2*composite_row_height},
        {'device_name':camera_names[1], 'stream_name':'frame', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
      ],
      [ # row  4
        {'device_name':camera_names[2], 'stream_name':'frame', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
        {'device_name':None, 'stream_name':None, 'rowspan':0, 'colspan':0, 'width':0, 'height':0},
        {'device_name':camera_names[3], 'stream_name':'frame', 'rowspan':1, 'colspan':1, 'width':composite_col_width_quarter, 'height':composite_row_height},
      ],
    ]
  }

  # For now pass streamer specs (local and remote) to subscribers manually.
  # TODO (non-critical): switch to REQ-REP model where subscribers ask details about available streams and their configurations to the broker.
  streamer_specs_logger = [spec for spec in sensor_streamer_specs 
                            if spec['class'] in datalogging_options['classes_to_log']]
  streamer_specs_visualizer = [spec for spec in sensor_streamer_specs 
                                if spec['class'] in visualization_options['classes_to_visualize']]

  # Configure settings for each worker/consumer of data.
  worker_specs = [
    {'class': 'DataLogger',
     **datalogging_options,
     'streamer_specs': streamer_specs_logger,
     'log_history_filepath': log_history_filepath,
     'print_debug': print_debug, 'print_status': print_status
     },
    {'class': 'DataVisualizer',
     **visualization_options,
     'streamer_specs': streamer_specs_visualizer,
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
