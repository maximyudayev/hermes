from collections import OrderedDict

import numpy as np
from streams.Stream import Stream
import numpy as np

###############################################
###############################################
# A structure to store Experiment stream's data
###############################################
###############################################
class ExperimentControlStream(Stream):
  def __init__(self, 
               activities: list[str],
               **_) -> None:
    super().__init__()

    self._wait_after_stopping = False
    self._tkinter_root = None
    
    # Define state for the current status.
    self._experiment_is_running = False
    self._calibrating = False
    self._performing_activity = False
    
    # Define lists of environment targets, poses, activities, etc.
    self._target_positions_cm = OrderedDict([
      ('Right heel at origin, facing +x', (0, 0)),
      ('Right heel at target, facing -x', (100, 150)),
      ('Gaze Calibration Stance', ((154.6 + 183.2)/2, -((28.5-5) + (57.0-5))/2)),
      ('Gaze Calibration Screen', (243, -107)),
      ])
    self._target_names = list(self._target_positions_cm.keys())
    self._arm_poses = [
      'Upper arm down, forearm straight out, palm facing in',
      'Straight down, palms inward (N pose)',
      'Straight out, palms downward (T pose)',
      'Straight up, palms inward',
      ]
    self._thirdparty_calibrations = [
      'Xsens: N-Pose with Walking',
      'Xsens: T-Pose with Walking',
      'Xsens: N-Pose without Walking',
      'Xsens: T-Pose without Walking',
      'PupilLabs: Target Grid',
      'PupilLabs: Single Target',
      ]
    
    self._activities = activities
    
    # Define the calibration data streams and their corresponding GUI inputs.
    # The input names will be updated later once they are added to the GUI.
    max_notes_length = 75
    self._calibration_device_name = 'experiment-calibration'
    self._calibration_streams = OrderedDict([
      ('body', {
        'description': 'Periods when the person assumed a known '
                       'body pose, location, and orientation.  '
                       'Useful for calibrating IMU-based orientations such as the Xsens.',
        'data_type': 'S%d' % ((int(max([len(x) for x in self._target_names] + [max_notes_length])/10)+1)*10),
        'tab_label': 'Body',
        'inputs': [
          {'label': 'Location', 'type': 'combo', 'values': self._target_names,   'name': None},
          {'label': 'Facing',   'type': 'combo', 'values': self._target_names,   'name': None},
          {'label': 'Pose',     'type': 'combo', 'values': ['T-Pose', 'N-Pose'], 'name': None},
        ]}),
      ('arms', {
        'description': 'Periods when the person assumed a known '
                       'arm pose and pointing direction orientation.  '
                       'Useful for calibrating IMU-based orientations such as the Myos.',
        'data_type': 'S%d' % ((int(max([len(x) for x in self._target_names+self._arm_poses] + [max_notes_length])/10)+1)*10),
        'tab_label': 'Arms',
        'inputs': [
          {'label': 'Body location',             'type': 'combo', 'values': self._target_names, 'name': None},
          {'label': 'Left arm pose',             'type': 'combo', 'values': self._arm_poses,    'name': None},
          {'label': 'Left forearm pointing at',  'type': 'combo', 'values': self._target_names, 'name': None},
          {'label': 'Right arm pose',            'type': 'combo', 'values': self._arm_poses,    'name': None},
          {'label': 'Right forearm pointing at', 'type': 'combo', 'values': self._target_names, 'name': None},
        ]}),
      ('gaze', {
        'description': 'Periods when the person assumed a known '
                       'body position and gazed at a known target.  '
                       'Useful for calibrating the eye tracking.',
        'data_type': 'S%d' % ((int(max([len(x) for x in self._target_names] + [max_notes_length])/10)+1)*10),
        'tab_label': 'Gaze',
        'inputs': [
          {'label': 'Body location', 'type': 'combo', 'values': self._target_names, 'name': None},
          {'label': 'Gazing at',     'type': 'combo', 'values': self._target_names, 'name': None},
        ]}),
      ('third_party', {
        'description': 'Periods when calibration routines from '
                       'third-party software was running, such as '
                       'Xsens or PupilLabs.',
        'data_type': 'S%d' % ((int(max([len(x) for x in self._thirdparty_calibrations+self._target_names] + [max_notes_length])/10)+1)*10),
        'tab_label': 'Third-Party',
        'inputs': [
          {'label': 'Calibration Type',                  'type': 'combo', 'values': self._thirdparty_calibrations, 'name': None},
          {'label': 'Body starting location',            'type': 'combo', 'values': self._target_names,            'name': None},
          {'label': 'Body ending location',              'type': 'combo', 'values': self._target_names,            'name': None},
          {'label': 'Screen location with gaze targets', 'type': 'combo', 'values': self._target_names,            'name': None},
        ]}),
    ])
    self._last_calibration_times_s = OrderedDict([(calibration_type, None) for calibration_type in self._calibration_streams])

    # Create the streams unless an existing log is being replayed
    #  (in which case SensorStreamer will create the streams automatically).
    for (stream_name, info) in self._calibration_streams.items():
      self.add_stream(device_name=self._calibration_device_name, 
                      stream_name=stream_name,
                      data_type=info['data_type'], 
                      sample_size=[3+len(info['inputs'])], 
                      sampling_rate_hz=None,
                      timesteps_before_solidified=2, # will update the start and stop entries with valid status and notes
                      data_notes=OrderedDict([
                        ('Description', info['description']),
                        (Stream.metadata_data_headings_key,
                          ['Start/Stop', 'Valid', 'Notes']
                          + [input['label'] for input in info['inputs']])
                        ]))

    # Define the activity stream.
    # Data in each entry will be: activity, start/stop, good/maybe/bad, notes
    self._activities_device_name = 'experiment-activities'
    self._activities_stream_name = 'activities'
    self.add_stream(device_name=self._activities_device_name, 
                    stream_name=self._activities_stream_name,
                    data_type='S500', 
                    sample_size=[4], 
                    sampling_rate_hz=None,
                    timesteps_before_solidified=2, # will update the start and stop entries with valid status and notes
                    data_notes=OrderedDict([
                      ('Description', 'The activity being performed.'),
                      (Stream.metadata_data_headings_key,
                        ['Activity', 'Start/Stop', 'Valid', 'Notes']),
                      ]))

    self._activities_counts = OrderedDict([
      (activity, {'Good':0, 'Maybe':0, 'Bad':0}) for activity in self._activities
    ])
    
    # Define the notes stream.
    self._notes_device_name = 'experiment-notes'
    self._notes_stream_name = 'notes'
    self.add_stream(device_name=self._notes_device_name, 
                    stream_name=self._notes_stream_name,
                    data_type='S500', 
                    sample_size=[1], 
                    sampling_rate_hz=None,
                    data_notes=OrderedDict([
                      ('Description', 'Notes that the experimenter entered '
                                      'during the trial, timestamped to '
                                      'align with collected data'),
                    ]))

    # Add to the metadata.
    self._metadata.setdefault(self._calibration_device_name, {})
    self._metadata.setdefault(self._activities_device_name, {})
    self._metadata[self._calibration_device_name]['Target Locations [cm]'] = self._target_positions_cm
    self._metadata[self._calibration_device_name]['Arm Poses'] = self._arm_poses
    self._metadata[self._calibration_device_name]['Third-Party Calibrations'] = self._thirdparty_calibrations
    self._metadata[self._activities_device_name]['Activities'] = self._activities
    self._metadata[self._activities_device_name]['Target Locations [cm]'] = self._target_positions_cm


  def get_fps(self) -> dict[str, float]:
    return None


  # TODO:
  def append_data(self,
                  device_id: str,
                  time_s: float, 
                  frame: np.ndarray, 
                  timestamp: np.uint64,
                  sequence_id: np.int64):
    self._append_data(self._camera_mapping[device_id], 'frame', time_s, frame)
    self._append_data(self._camera_mapping[device_id], 'timestamp', time_s, timestamp)
    self._append_data(self._camera_mapping[device_id], 'frame_sequence', time_s, sequence_id)
