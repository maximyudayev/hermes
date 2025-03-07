from collections import OrderedDict
import copy
from streams import Stream
from visualizers import LinePlotVisualizer, SkeletonVisualizer
from streams.Stream import Stream
import dash_bootstrap_components as dbc


##########################################
##########################################
# TODO:
##########################################
##########################################
class MvnAnalyzeStream(Stream):
  def __init__(self,
               is_pose_euler: bool = False,
               is_pose_quaternion: bool = False,
               is_joint_angles: bool = False,
               is_center_of_mass: bool = False,
               is_timestamp: bool = False,
               num_joints: int = 5,
               num_segments: int = 5,
               num_fingers: int = 5,
               sampling_rate_hz: int = 20,
               timesteps_before_solidified: int = 0,
               update_interval_ms: int = 100,
               transmission_delay_period_s: int = None,
               **_) -> None:

    super().__init__()
    self._num_joints = num_joints
    self._num_segments = num_segments
    self._num_fingers = num_fingers
    self._sampling_rate_hz = sampling_rate_hz

    self._transmission_delay_period_s = transmission_delay_period_s
    self._timesteps_before_solidified = timesteps_before_solidified
    self._update_interval_ms = update_interval_ms

    # Define headings for each stream; will populate self._headings.
    self._define_data_headings()
    self._define_data_notes()
    
    # All streams will have the Xsens sample counter and time code added.
    extra_data_info = {
      'xsens_sample_number'     : {'data_type': 'int32',   'sample_size': [1]},
      'xsens_time_since_start_s': {'data_type': 'float32', 'sample_size': [1]}}
    
    # TODO: add raw 9-DOF data.

    # Segment positions and orientations
    if is_pose_euler or is_pose_quaternion:
      self.add_stream(device_name='xsens-segments',
                      stream_name='position_cm',
                      data_type='float32',
                      sample_size=(self._num_segments + self._num_fingers, 3),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info,
                      data_notes=self._data_notes_stream['xsens-segments']['position_cm'])
    if is_pose_euler:
      self.add_stream(device_name='xsens-segments',
                      stream_name='orientation_euler',
                      data_type='float32',
                      sample_size=(self._num_segments + self._num_fingers, 3),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info,
                      data_notes=self._data_notes_stream['xsens-segments']['orientation_euler'])
    if is_pose_quaternion:
      self.add_stream(device_name='xsens-segments',
                      stream_name='orientation_quaternion',
                      data_type='float32',
                      sample_size=(self._num_segments + self._num_fingers, 4),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info,
                      data_notes=self._data_notes_stream['xsens-segments']['orientation_quaternion'])

    # Joint angles
    if is_joint_angles:
      self.add_stream(device_name='xsens-joints',
                      stream_name='rotation_deg',
                      data_type='float32',
                      sample_size=(self._num_joints, 3),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info,
                      data_notes=self._data_notes_stream['xsens-joints']['rotation_deg'])
      self.add_stream(device_name='xsens-joints',
                      stream_name='parent',
                      data_type='float32',
                      sample_size=(self._num_joints),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info,
                      data_notes=self._data_notes_stream['xsens-joints']['parent'])
      self.add_stream(device_name='xsens-joints',
                      stream_name='child',
                      data_type='float32',
                      sample_size=(self._num_joints),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info,
                      data_notes=self._data_notes_stream['xsens-joints']['child'])

    # Center of mass dynamics
    if is_center_of_mass:
      self.add_stream(device_name='xsens-com',
                      stream_name='position_cm',
                      data_type='float32',
                      sample_size=(3),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info,
                      data_notes=self._data_notes_stream['xsens-com']['position_cm'])
      self.add_stream(device_name='xsens-com',
                      stream_name='velocity_cm_s',
                      data_type='float32',
                      sample_size=(3),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info,
                      data_notes=self._data_notes_stream['xsens-com']['velocity_cm_s'])
      self.add_stream(device_name='xsens-com',
                      stream_name='acceleration_cm_ss',
                      data_type='float32',
                      sample_size=(3),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info,
                      data_notes=self._data_notes_stream['xsens-com']['acceleration_cm_ss'])

    # Time codes sent from the Xsens device
    if is_timestamp:
      extra_data_info_time = extra_data_info.copy()
      extra_data_info_time['device_time_utc_str']  = {'data_type': 'S12', 'sample_size': [1]}
      extra_data_info_time['device_timestamp_str'] = {'data_type': 'S26', 'sample_size': [1]}
      self.add_stream(device_name='xsens-time',
                      stream_name='device_timestamp_s',
                      data_type='float64',
                      sample_size=(1),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info_time,
                      data_notes=self._data_notes_stream['xsens-time']['device_timestamp_s'])


  def get_fps(self) -> dict[str, float]:
    return {'vicon-data': super()._get_fps('vicon-data', 'frame_count')}


  def build_visulizer(self) -> dbc.Row:
    skeleton_plot = SkeletonVisualizer(stream=self,
                                       data_path={'dots-imu': [
                                                   'acceleration-x',
                                                   'acceleration-y',
                                                   'acceleration-z']},
                                       plot_duration_timesteps=self._timesteps_before_solidified,
                                       update_interval_ms=self._update_interval_ms,
                                       col_width=6)
    return super().build_visulizer()


  def _define_data_notes(self):
    self._define_data_headings()
    
    self._data_notes_stream = {}
    self._data_notes_stream.setdefault('xsens-segments', {})
    self._data_notes_stream.setdefault('xsens-joints', {})
    self._data_notes_stream.setdefault('xsens-com', {})
    self._data_notes_stream.setdefault('xsens-time', {})
    
    # Segments
    self._data_notes_stream['xsens-segments']['position_cm'] = OrderedDict([
      ('Units', 'cm'),
      ('Coordinate frame', 'A Y-up right-handed frame if Euler data is streamed, otherwise a Z-up right-handed frame'),
      ('Matrix ordering', 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][1][0], ...' \
       + '   | And if no fingers were included in the data, only use the first 69 data headings (the first 23 segments)'),
      (Stream.metadata_data_headings_key, self._headings['xsens-segments']['position_cm'])
    ])
    self._data_notes_stream['xsens-segments']['orientation_euler_deg'] = OrderedDict([
      ('Units', 'degrees'),
      ('Coordinate frame', 'A Y-Up, right-handed coordinate system'),
      ('Matrix ordering', 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][1][0], ...' \
       + '   | And if no fingers were included in the data, only use the first 69 data headings (the first 23 segments)'),
      (Stream.metadata_data_headings_key, self._headings['xsens-segments']['orientation_euler_deg']),
      # ('Developer note', 'Streamed data did not seem to match Excel data exported from Xsens; on recent tests it was close, while on older tests it seemed very different.'),
    ])
    self._data_notes_stream['xsens-segments']['orientation_quaternion'] = OrderedDict([
      ('Coordinate frame', 'A Z-Up, right-handed coordinate system'),
      ('Normalization', 'Normalized but not necessarily positive-definite'),
      ('Matrix ordering', 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][0][3], data[frame_index][1][0], ...' \
       + '   | And if no fingers were included in the data, only use the first 92 data headings (the first 23 segments)'),
      (Stream.metadata_data_headings_key, self._headings['xsens-segments']['orientation_quaternion'])
    ])
    # Joints
    self._data_notes_stream['xsens-joints']['rotation_deg'] = OrderedDict([
      ('Units', 'degrees'),
      ('Coordinate frame', 'A Z-Up, right-handed coordinate system'),
      ('Matrix ordering', 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][1][0], ...'),
      ('Joint parents - segment IDs',    self._headings['xsens-joints']['joint_rotation_streamed_parents_segmentIDs']['streamed']),
      ('Joint parents - segment Names',  self._headings['xsens-joints']['joint_rotation_streamed_parents_segmentNames']['streamed']),
      ('Joint parents - point IDs',      self._headings['xsens-joints']['joint_rotation_streamed_parents_pointIDs']['streamed']),
      ('Joint children - segment IDs',   self._headings['xsens-joints']['joint_rotation_streamed_children_segmentIDs']['streamed']),
      ('Joint children - segment Names', self._headings['xsens-joints']['joint_rotation_streamed_children_segmentNames']['streamed']),
      ('Joint children - point IDs',     self._headings['xsens-joints']['joint_rotation_streamed_children_pointIDs']['streamed']),
      ('Segment ID to Name mapping', self._headings['xsens-joints']['segmentIDsToNames']),
      (Stream.metadata_data_headings_key, self._headings['xsens-joints']['joint_rotation_names_streamed'])
    ])
    self._data_notes_stream['xsens-joints']['parent'] = OrderedDict([
      ('Format', 'segmentID.pointID'),
      ('Segment ID to Name mapping', self._headings['xsens-joints']['segmentIDsToNames']),
      (Stream.metadata_data_headings_key, self._headings['xsens-joints']['joint_names_streamed'])
    ])
    self._data_notes_stream['xsens-joints']['child'] = OrderedDict([
      ('Format', 'segmentID.pointID'),
      ('Segment ID to Name mapping', self._headings['xsens-joints']['segmentIDsToNames']),
      (Stream.metadata_data_headings_key, self._headings['xsens-joints']['joint_names_streamed'])
    ])
    # Center of mass
    self._data_notes_stream['xsens-com']['position_cm'] = OrderedDict([
      ('Units', 'cm'),
      ('Coordinate frame', 'A Z-up, right-handed coordinate system'),
      (Stream.metadata_data_headings_key, self._headings['xsens-com']['position_cm'])
    ])
    self._data_notes_stream['xsens-com']['velocity_cm_s'] = OrderedDict([
      ('Units', 'cm/s'),
      ('Coordinate frame', 'A Z-up, right-handed coordinate system'),
      (Stream.metadata_data_headings_key, self._headings['xsens-com']['velocity_cm_s'])
    ])
    self._data_notes_stream['xsens-com']['acceleration_cm_ss'] = OrderedDict([
      ('Units', 'cm/s/s'),
      ('Coordinate frame', 'A Z-up, right-handed coordinate system'),
      (Stream.metadata_data_headings_key, self._headings['xsens-com']['acceleration_cm_ss'])
    ])
    # Time
    self._data_notes_stream['xsens-time']['device_timestamp_s'] = OrderedDict([
      ('Description', 'The timestamp recorded by the Xsens device, which is more precise than the system time when the data was received (the time_s field)'),
    ])


    self._data_notes_excel = {}
    self._data_notes_excel.setdefault('xsens-segments', {})
    self._data_notes_excel.setdefault('xsens-joints', {})
    self._data_notes_excel.setdefault('xsens-ergonomic-joints', {})
    self._data_notes_excel.setdefault('xsens-com', {})
    self._data_notes_excel.setdefault('xsens-sensors', {})
    self._data_notes_excel.setdefault('xsens-time', {})

    # Segments
    self._data_notes_excel['xsens-segments']['position_cm'] = self._data_notes_stream['xsens-segments']['position_cm'].copy()
    self._data_notes_excel['xsens-segments']['position_cm']['Coordinate frame'] = 'A Z-up right-handed frame'
    
    self._data_notes_excel['xsens-segments']['velocity_cm_s'] = self._data_notes_excel['xsens-segments']['position_cm'].copy()
    self._data_notes_excel['xsens-segments']['velocity_cm_s']['Units'] = 'cm/s'
    self._data_notes_excel['xsens-segments']['velocity_cm_s']['Matrix ordering'] = 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][1][0], ...' \
     + '   | And only use the first 69 data headings (the first 23 segments)'
    
    self._data_notes_excel['xsens-segments']['acceleration_cm_ss'] = self._data_notes_excel['xsens-segments']['velocity_cm_s'].copy()
    self._data_notes_excel['xsens-segments']['acceleration_cm_ss']['Units'] = 'cm/s/s'
    
    self._data_notes_excel['xsens-segments']['angular_velocity_deg_s'] = self._data_notes_excel['xsens-segments']['velocity_cm_s'].copy()
    self._data_notes_excel['xsens-segments']['angular_velocity_deg_s']['Units'] = 'degrees/s'
    
    self._data_notes_excel['xsens-segments']['angular_acceleration_deg_ss'] = self._data_notes_excel['xsens-segments']['velocity_cm_s'].copy()
    self._data_notes_excel['xsens-segments']['angular_acceleration_deg_ss']['Units'] = 'degrees/s/s'

    self._data_notes_excel['xsens-segments']['orientation_euler_deg'] = self._data_notes_stream['xsens-segments']['orientation_euler_deg'].copy()
    self._data_notes_excel['xsens-segments']['orientation_quaternion'] = self._data_notes_stream['xsens-segments']['orientation_quaternion'].copy()
    
    # Joints
    self._data_notes_excel['xsens-joints']['rotation_zxy_deg'] = self._data_notes_stream['xsens-joints']['rotation_deg'].copy()
    self._data_notes_excel['xsens-joints']['rotation_zxy_deg'][Stream.metadata_data_headings_key] = self._headings['xsens-joints']['joint_rotation_names_bodyFingers']
    self._data_notes_excel['xsens-joints']['rotation_zxy_deg']['Matrix ordering'] = 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][1][0], ...' \
            + '   | And if no fingers were included in the data, only use the first 66 data headings (the first 22 joints)'
    self._data_notes_excel['xsens-joints']['rotation_zxy_deg']['Joint parents - segment IDs']    = self._headings['xsens-joints']['joint_rotation_streamed_parents_segmentIDs']['body']
    self._data_notes_excel['xsens-joints']['rotation_zxy_deg']['Joint parents - segment Names']  = self._headings['xsens-joints']['joint_rotation_streamed_parents_segmentNames']['body']
    self._data_notes_excel['xsens-joints']['rotation_zxy_deg']['Joint parents - point IDs']      = self._headings['xsens-joints']['joint_rotation_streamed_parents_pointIDs']['body']
    self._data_notes_excel['xsens-joints']['rotation_zxy_deg']['Joint children - segment IDs']   = self._headings['xsens-joints']['joint_rotation_streamed_children_segmentIDs']['body']
    self._data_notes_excel['xsens-joints']['rotation_zxy_deg']['Joint children - segment Names'] = self._headings['xsens-joints']['joint_rotation_streamed_children_segmentNames']['body']
    self._data_notes_excel['xsens-joints']['rotation_zxy_deg']['Joint children - point IDs']     = self._headings['xsens-joints']['joint_rotation_streamed_children_pointIDs']['body']

    self._data_notes_excel['xsens-joints']['rotation_xzy_deg'] = self._data_notes_excel['xsens-joints']['rotation_zxy_deg'].copy()
    
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg'] = self._data_notes_excel['xsens-joints']['rotation_zxy_deg'].copy()
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg']['Matrix ordering'] = 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][1][0], ...'
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg'][Stream.metadata_data_headings_key] = self._headings['xsens-joints']['joint_rotation_names_ergonomic']
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg']['Joint parents - segment IDs']    = self._headings['xsens-joints']['joint_rotation_streamed_parents_segmentIDs']['ergonomic']
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg']['Joint parents - segment Names']  = self._headings['xsens-joints']['joint_rotation_streamed_parents_segmentNames']['ergonomic']
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg']['Joint parents - point IDs']      = self._headings['xsens-joints']['joint_rotation_streamed_parents_pointIDs']['ergonomic']
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg']['Joint children - segment IDs']   = self._headings['xsens-joints']['joint_rotation_streamed_children_segmentIDs']['ergonomic']
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg']['Joint children - segment Names'] = self._headings['xsens-joints']['joint_rotation_streamed_children_segmentNames']['ergonomic']
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg']['Joint children - point IDs']     = self._headings['xsens-joints']['joint_rotation_streamed_children_pointIDs']['ergonomic']
    
    self._data_notes_excel['xsens-ergonomic-joints']['rotation_xzy_deg'] = self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg'].copy()
    
    # Center of mass
    self._data_notes_excel['xsens-com']['position_cm'] = self._data_notes_stream['xsens-com']['position_cm'].copy()
    self._data_notes_excel['xsens-com']['velocity_cm_s'] = self._data_notes_stream['xsens-com']['velocity_cm_s'].copy()
    self._data_notes_excel['xsens-com']['acceleration_cm_ss'] = self._data_notes_stream['xsens-com']['acceleration_cm_ss'].copy()
    
    # Sensors
    self._data_notes_excel['xsens-sensors']['free_acceleration_cm_ss'] = self._data_notes_stream['xsens-segments']['position_cm'].copy()
    self._data_notes_excel['xsens-sensors']['free_acceleration_cm_ss']['Matrix ordering'] = 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][1][0], ...' \
        + '   | And only use data headings for which the data is not all 0 or all NaN'
    self._data_notes_excel['xsens-sensors']['free_acceleration_cm_ss']['Units'] = 'cm/s/s'
    del self._data_notes_excel['xsens-sensors']['free_acceleration_cm_ss']['Coordinate frame']
    self._data_notes_excel['xsens-sensors']['magnetic_field'] = self._data_notes_excel['xsens-sensors']['free_acceleration_cm_ss'].copy()
    self._data_notes_excel['xsens-sensors']['magnetic_field']['Units'] = 'a.u. according to the manual, but more likely gauss based on the magnitudes'
    
    self._data_notes_excel['xsens-sensors']['orientation_quaternion'] = self._data_notes_stream['xsens-segments']['orientation_quaternion'].copy()
    self._data_notes_excel['xsens-sensors']['orientation_quaternion']['Matrix ordering'] = 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][0][3], data[frame_index][1][0], ...' \
        + '   | And only use data headings for which the data is not all 0 or all NaN'
    del self._data_notes_excel['xsens-sensors']['orientation_quaternion']['Coordinate frame']
    
    self._data_notes_excel['xsens-sensors']['orientation_euler_deg'] = self._data_notes_stream['xsens-segments']['orientation_euler_deg'].copy()
    self._data_notes_excel['xsens-sensors']['orientation_euler_deg']['Matrix ordering'] = 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][1][0], ...' \
        + '   | And only use data headings for which the data is not all 0 or all NaN'
    del self._data_notes_excel['xsens-sensors']['orientation_euler_deg']['Coordinate frame']
    
    # Time
    self._data_notes_excel['xsens-time']['stream_receive_time_s'] = OrderedDict([
      ('Description', 'The estimated system time at which each frame was received by Python during live streaming'),
    ])


    self._data_notes_mvnx = copy.deepcopy(self._data_notes_excel)
    
    # Update the data headings for the sensors.
    #  The Excel file contains all segment names and has hidden columns of 0 for ones that don't have sensors,
    #  while the MVNX only lists actual sensor locations.
    for sensors_key in self._data_notes_mvnx['xsens-sensors'].keys():
      if 'quaternion' in sensors_key:
        self._data_notes_mvnx['xsens-sensors'][sensors_key][Stream.metadata_data_headings_key] = self._headings['xsens-sensors']['sensors-quaternion']
        self._data_notes_mvnx['xsens-sensors'][sensors_key]['Matrix ordering'] = 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][0][3], data[frame_index][1][0], ...'
      else:
        self._data_notes_mvnx['xsens-sensors'][sensors_key][Stream.metadata_data_headings_key] = self._headings['xsens-sensors']['sensors-xyz']
        self._data_notes_mvnx['xsens-sensors'][sensors_key]['Matrix ordering'] = 'To align with data headings, unwrap a frame\'s matrix as data[frame_index][0][0], data[frame_index][0][1], data[frame_index][0][2], data[frame_index][1][0], ...'

    # Foot contacts
    self._data_notes_mvnx.setdefault('xsens-foot-contacts', {})
    self._data_notes_mvnx['xsens-foot-contacts']['foot-contacts'] = OrderedDict([
      ('Description', 'Which points of the foot are estimated to be in contact with the ground'),
      (Stream.metadata_data_headings_key, self._headings['xsens-foot-contacts']['foot-contacts']),
    ])


  def _define_data_headings(self):
    segment_names_body = [
      # Main-body segments
      'Pelvis', 'L5', 'L3', 'T12', 'T8', 'Neck', 'Head',
      'Right Shoulder',  'Right Upper Arm', 'Right Forearm', 'Right Hand',
      'Left Shoulder',   'Left Upper Arm',  'Left Forearm',  'Left Hand',
      'Right Upper Leg', 'Right Lower Leg', 'Right Foot',    'Right Toe',
      'Left Upper Leg',  'Left Lower Leg',  'Left Foot',     'Left Toe',
      ]
      # Note: props 1-4 would be between body and fingers here if there are any
    segment_names_fingers = [
      # Fingers of left hand
      'Left Carpus',            'Left First Metacarpal',         'Left First Proximal Phalange', 'Left First Distal Phalange',
      'Left Second Metacarpal', 'Left Second Proximal Phalange', 'Left Second Middle Phalange',  'Left Second Distal Phalange',
      'Left Third Metacarpal',  'Left Third Proximal Phalange',  'Left Third Middle Phalange',   'Left Third Distal Phalange',
      'Left Fourth Metacarpal', 'Left Fourth Proximal Phalange', 'Left Fourth Middle Phalange',  'Left Fourth Distal Phalange',
      'Left Fifth Metacarpal',  'Left Fifth Proximal Phalange',  'Left Fifth Middle Phalange',   'Left Fifth Distal Phalange',
      # Fingers of right hand
      'Right Carpus',            'Right First Metacarpal',         'Right First Proximal Phalange', 'Right First Distal Phalange',
      'Right Second Metacarpal', 'Right Second Proximal Phalange', 'Right Second Middle Phalange',  'Right Second Distal Phalange',
      'Right Third Metacarpal',  'Right Third Proximal Phalange',  'Right Third Middle Phalange',   'Right Third Distal Phalange',
      'Right Fourth Metacarpal', 'Right Fourth Proximal Phalange', 'Right Fourth Middle Phalange',  'Right Fourth Distal Phalange',
      'Right Fifth Metacarpal',  'Right Fifth Proximal Phalange',  'Right Fifth Middle Phalange',   'Right Fifth Distal Phalange',
    ]
    sensor_names = segment_names_body[0:1] + segment_names_body[4:5] + segment_names_body[6:18] + segment_names_body[19:22]
    joint_rotation_names_body = [
      'L5S1 Lateral Bending',    'L5S1 Axial Bending',     'L5S1 Flexion/Extension',
      'L4L3 Lateral Bending',    'L4L3 Axial Rotation',    'L4L3 Flexion/Extension',
      'L1T12 Lateral Bending',   'L1T12 Axial Rotation',   'L1T12 Flexion/Extension',
      'T9T8 Lateral Bending',    'T9T8 Axial Rotation',    'T9T8 Flexion/Extension',
      'T1C7 Lateral Bending',    'T1C7 Axial Rotation',    'T1C7 Flexion/Extension',
      'C1 Head Lateral Bending', 'C1 Head Axial Rotation', 'C1 Head Flexion/Extension',
      'Right T4 Shoulder Abduction/Adduction', 'Right T4 Shoulder Internal/External Rotation', 'Right T4 Shoulder Flexion/Extension',
      'Right Shoulder Abduction/Adduction',    'Right Shoulder Internal/External Rotation',    'Right Shoulder Flexion/Extension',
      'Right Elbow Ulnar Deviation/Radial Deviation', 'Right Elbow Pronation/Supination', 'Right Elbow Flexion/Extension',
      'Right Wrist Ulnar Deviation/Radial Deviation', 'Right Wrist Pronation/Supination', 'Right Wrist Flexion/Extension',
      'Left T4 Shoulder Abduction/Adduction', 'Left T4 Shoulder Internal/External Rotation', 'Left T4 Shoulder Flexion/Extension',
      'Left Shoulder Abduction/Adduction',    'Left Shoulder Internal/External Rotation',    'Left Shoulder Flexion/Extension',
      'Left Elbow Ulnar Deviation/Radial Deviation', 'Left Elbow Pronation/Supination', 'Left Elbow Flexion/Extension',
      'Left Wrist Ulnar Deviation/Radial Deviation', 'Left Wrist Pronation/Supination', 'Left Wrist Flexion/Extension',
      'Right Hip Abduction/Adduction',       'Right Hip Internal/External Rotation',       'Right Hip Flexion/Extension',
      'Right Knee Abduction/Adduction',      'Right Knee Internal/External Rotation',      'Right Knee Flexion/Extension',
      'Right Ankle Abduction/Adduction',     'Right Ankle Internal/External Rotation',     'Right Ankle Dorsiflexion/Plantarflexion',
      'Right Ball Foot Abduction/Adduction', 'Right Ball Foot Internal/External Rotation', 'Right Ball Foot Flexion/Extension',
      'Left Hip Abduction/Adduction',        'Left Hip Internal/External Rotation',        'Left Hip Flexion/Extension',
      'Left Knee Abduction/Adduction',       'Left Knee Internal/External Rotation',       'Left Knee Flexion/Extension',
      'Left Ankle Abduction/Adduction',      'Left Ankle Internal/External Rotation',      'Left Ankle Dorsiflexion/Plantarflexion',
      'Left Ball Foot Abduction/Adduction',  'Left Ball Foot Internal/External Rotation',  'Left Ball Foot Flexion/Extension',
      ]
    joint_rotation_names_fingers = [
      'Left First CMC Abduction/Adduction',  'Left First CMC Internal/External Rotation',  'Left First CMC Flexion/Extension',
      'Left First MCP Abduction/Adduction',  'Left First MCP Internal/External Rotation',  'Left First MCP Flexion/Extension',
      'Left IP Abduction/Adduction', 'Left IP Internal/External Rotation', 'Left IP Flexion/Extension',
      'Left Second CMC Abduction/Adduction', 'Left Second CMC Internal/External Rotation', 'Left Second CMC Flexion/Extension',
      'Left Second MCP Abduction/Adduction', 'Left Second MCP Internal/External Rotation', 'Left Second MCP Flexion/Extension',
      'Left Second PIP Abduction/Adduction', 'Left Second PIP Internal/External Rotation', 'Left Second PIP Flexion/Extension',
      'Left Second DIP Abduction/Adduction', 'Left Second DIP Internal/External Rotation', 'Left Second DIP Flexion/Extension',
      'Left Third CMC Abduction/Adduction',  'Left Third CMC Internal/External Rotation',  'Left Third CMC Flexion/Extension',
      'Left Third MCP Abduction/Adduction',  'Left Third MCP Internal/External Rotation',  'Left Third MCP Flexion/Extension',
      'Left Third PIP Abduction/Adduction',  'Left Third PIP Internal/External Rotation',  'Left Third PIP Flexion/Extension',
      'Left Third DIP Abduction/Adduction',  'Left Third DIP Internal/External Rotation',  'Left Third DIP Flexion/Extension',
      'Left Fourth CMC Abduction/Adduction', 'Left Fourth CMC Internal/External Rotation', 'Left Fourth CMC Flexion/Extension',
      'Left Fourth MCP Abduction/Adduction', 'Left Fourth MCP Internal/External Rotation', 'Left Fourth MCP Flexion/Extension',
      'Left Fourth PIP Abduction/Adduction', 'Left Fourth PIP Internal/External Rotation', 'Left Fourth PIP Flexion/Extension',
      'Left Fourth DIP Abduction/Adduction', 'Left Fourth DIP Internal/External Rotation', 'Left Fourth DIP Flexion/Extension',
      'Left Fifth CMC Abduction/Adduction',  'Left Fifth CMC Internal/External Rotation',  'Left Fifth CMC Flexion/Extension',
      'Left Fifth MCP Abduction/Adduction',  'Left Fifth MCP Internal/External Rotation',  'Left Fifth MCP Flexion/Extension',
      'Left Fifth PIP Abduction/Adduction',  'Left Fifth PIP Internal/External Rotation',  'Left Fifth PIP Flexion/Extension',
      'Left Fifth DIP Abduction/Adduction',  'Left Fifth DIP Internal/External Rotation',  'Left Fifth DIP Flexion/Extension',
      'Right First CMC Abduction/Adduction', 'Right First CMC Internal/External Rotation', 'Right First CMC Flexion/Extension',
      'Right First MCP Abduction/Adduction', 'Right First MCP Internal/External Rotation', 'Right First MCP Flexion/Extension',
      'Right IP Abduction/Adduction',         'Right IP Internal/External Rotation',         'Right IP Flexion/Extension',
      'Right Second CMC Abduction/Adduction', 'Right Second CMC Internal/External Rotation', 'Right Second CMC Flexion/Extension',
      'Right Second MCP Abduction/Adduction', 'Right Second MCP Internal/External Rotation', 'Right Second MCP Flexion/Extension',
      'Right Second PIP Abduction/Adduction', 'Right Second PIP Internal/External Rotation', 'Right Second PIP Flexion/Extension',
      'Right Second DIP Abduction/Adduction', 'Right Second DIP Internal/External Rotation', 'Right Second DIP Flexion/Extension',
      'Right Third CMC Abduction/Adduction',  'Right Third CMC Internal/External Rotation',  'Right Third CMC Flexion/Extension',
      'Right Third MCP Abduction/Adduction',  'Right Third MCP Internal/External Rotation',  'Right Third MCP Flexion/Extension',
      'Right Third PIP Abduction/Adduction',  'Right Third PIP Internal/External Rotation',  'Right Third PIP Flexion/Extension',
      'Right Third DIP Abduction/Adduction',  'Right Third DIP Internal/External Rotation',  'Right Third DIP Flexion/Extension',
      'Right Fourth CMC Abduction/Adduction', 'Right Fourth CMC Internal/External Rotation', 'Right Fourth CMC Flexion/Extension',
      'Right Fourth MCP Abduction/Adduction', 'Right Fourth MCP Internal/External Rotation', 'Right Fourth MCP Flexion/Extension',
      'Right Fourth PIP Abduction/Adduction', 'Right Fourth PIP Internal/External Rotation', 'Right Fourth PIP Flexion/Extension',
      'Right Fourth DIP Abduction/Adduction', 'Right Fourth DIP Internal/External Rotation', 'Right Fourth DIP Flexion/Extension',
      'Right Fifth CMC Abduction/Adduction',  'Right Fifth CMC Internal/External Rotation',  'Right Fifth CMC Flexion/Extension',
      'Right Fifth MCP Abduction/Adduction',  'Right Fifth MCP Internal/External Rotation',  'Right Fifth MCP Flexion/Extension',
      'Right Fifth PIP Abduction/Adduction',  'Right Fifth PIP Internal/External Rotation',  'Right Fifth PIP Flexion/Extension',
      'Right Fifth DIP Abduction/Adduction',  'Right Fifth DIP Internal/External Rotation',  'Right Fifth DIP Flexion/Extension',
    ]
    joint_rotation_names_ergonomic = [
      'T8_Head Lateral Bending',          'T8_Head Axial Bending',          'T8_Head Flexion/Extension',
      'T8_LeftUpperArm Lateral Bending',  'T8_LeftUpperArm Axial Bending',  'T8_LeftUpperArm Flexion/Extension',
      'T8_RightUpperArm Lateral Bending', 'T8_RightUpperArm Axial Bending', 'T8_RightUpperArm Flexion/Extension',
      'Pelvis_T8 Lateral Bending',        'Pelvis_T8 Axial Bending',        'Pelvis_T8 Flexion/Extension',
      'Vertical_Pelvis Lateral Bending',  'Vertical_Pelvis Axial Bending',  'Vertical_Pelvis Flexion/Extension',
      'Vertical_T8 Lateral Bending',      'Vertical_T8 Axial Bending',      'Vertical_T8 Flexion/Extension',
    ]
    joint_names_body = [
      'L5S1', 'L4L3', 'L1T12', 'T9T8', 'T1C7', 'C1 Head',
      'Right T4 Shoulder', 'Right Shoulder', 'Right Elbow', 'Right Wrist',
      'Left T4 Shoulder',  'Left Shoulder',  'Left Elbow',  'Left Wrist',
      'Right Hip', 'Right Knee', 'Right Ankle', 'Right Ball Foot',
      'Left Hip',  'Left Knee',  'Left Ankle',  'Left Ball Foot',
      ]
    joint_names_fingers = [
      'Left First CMC',   'Left First MCP',   'Left IP',
      'Left Second CMC',  'Left Second MCP',  'Left Second PIP',  'Left Second DIP',
      'Left Third CMC',   'Left Third MCP',   'Left Third PIP',   'Left Third DIP',
      'Left Fourth CMC',  'Left Fourth MCP',  'Left Fourth PIP',  'Left Fourth DIP',
      'Left Fifth CMC',   'Left Fifth MCP',   'Left Fifth PIP',   'Left Fifth DIP',
      'Right First CMC',  'Right First MCP',  'Right IP',
      'Right Second CMC', 'Right Second MCP', 'Right Second PIP', 'Right Second DIP',
      'Right Third CMC',  'Right Third MCP',  'Right Third PIP',  'Right Third DIP',
      'Right Fourth CMC', 'Right Fourth MCP', 'Right Fourth PIP', 'Right Fourth DIP',
      'Right Fifth CMC',  'Right Fifth MCP',  'Right Fifth PIP',  'Right Fifth DIP',
    ]
    joint_names_ergonomic = [
      'T8_Head',
      'T8_LeftUpperArm',
      'T8_RightUpperArm',
      'Pelvis_T8',
      'Vertical_Pelvis',
      'Vertical_T8',
    ]
    # Record the parent/child segment and point for each streamed joint.
    # The long lists were copied from a test data stream.
    joint_parents_segmentIDsPointIDs = [1.002, 2.002, 3.002, 4.002, 5.002, 6.002, 5.003, 8.002, 9.002, 10.002, 5.004, 12.002, 13.002, 14.002, 1.003, 16.002, 17.002, 18.002, 1.004, 20.002, 21.002, 22.002, 5.0, 5.0, 5.0, 1.0, 1.0, 1.0]
    joint_parents_segmentIDs = [int(x) for x in joint_parents_segmentIDsPointIDs]
    joint_parents_pointIDs = [round((x - int(x))*1000) for x in joint_parents_segmentIDsPointIDs]
    joint_children_segmentIDsPointIDs = [2.001, 3.001, 4.001, 5.001, 6.001, 7.001, 8.001, 9.001, 10.001, 11.001, 12.001, 13.001, 14.001, 15.001, 16.001, 17.001, 18.001, 19.001, 20.001, 21.001, 22.001, 23.001, 7.0, 13.0, 9.0, 5.0, 1.0, 5.0]
    joint_children_segmentIDs = [int(x) for x in joint_children_segmentIDsPointIDs]
    joint_children_pointIDs = [round((x - int(x))*1000) for x in joint_children_segmentIDsPointIDs]
    # Convert to dictionaries mapping joint names to segment names and point IDs.
    #  to avoid dealing with orderings and indexes.
    # Note that the segment IDs are 1-indexed.
    joint_parents_segmentIDs = OrderedDict(
        [(joint_names_body[i], joint_parent_segmentID)
          for (i, joint_parent_segmentID) in enumerate(joint_parents_segmentIDs[0:22])]
      + [(joint_names_ergonomic[i], joint_parent_segmentID)
          for (i, joint_parent_segmentID) in enumerate(joint_parents_segmentIDs[22:])]
    )
    joint_parents_segmentNames = OrderedDict(
        [(joint_name, segment_names_body[segmentID-1])
          for (joint_name, segmentID) in joint_parents_segmentIDs.items()]
    )
    joint_parents_pointIDs = OrderedDict(
        [(joint_names_body[i], joint_parent_pointID)
          for (i, joint_parent_pointID) in enumerate(joint_parents_pointIDs[0:22])]
      + [(joint_names_ergonomic[i], joint_parent_pointID)
          for (i, joint_parent_pointID) in enumerate(joint_parents_pointIDs[22:])]
    )
    joint_children_segmentIDs = OrderedDict(
        [(joint_names_body[i], joint_child_segmentID)
          for (i, joint_child_segmentID) in enumerate(joint_children_segmentIDs[0:22])]
      + [(joint_names_ergonomic[i], joint_child_segmentID)
          for (i, joint_child_segmentID) in enumerate(joint_children_segmentIDs[22:])]
    )
    joint_children_segmentNames = OrderedDict(
        [(joint_name, segment_names_body[segmentID-1])
          for (joint_name, segmentID) in joint_children_segmentIDs.items()]
    )
    joint_children_pointIDs = OrderedDict(
        [(joint_names_body[i], joint_child_pointID)
          for (i, joint_child_pointID) in enumerate(joint_children_pointIDs[0:22])]
      + [(joint_names_ergonomic[i], joint_child_pointID)
          for (i, joint_child_pointID) in enumerate(joint_children_pointIDs[22:])]
    )
    # Foot contact points
    foot_contact_names = ['LeftFoot_Heel', 'LeftFoot_Toe', 'RightFoot_Heel', 'RightFoot_Toe']

    self._headings = {}
    # Center of Mass
    self._headings.setdefault('xsens-com', {})
    self._headings['xsens-com']['position_cm'] = ['x', 'y', 'z']
    self._headings['xsens-com']['velocity_cm_s'] = ['x', 'y', 'z']
    self._headings['xsens-com']['acceleration_cm_ss'] = ['x', 'y', 'z']
    # Segment orientation - quaternion
    self._headings.setdefault('xsens-segments', {})
    quaternion_elements = ['q0_re', 'q1_i', 'q2_j', 'q3_k']
    self._headings['xsens-segments']['orientation_quaternion'] = \
      ['%s (%s)' % (name, element) for name in (segment_names_body + segment_names_fingers)
                                   for element in quaternion_elements]
    # Segment orientation - Euler
    self._headings.setdefault('xsens-segments', {})
    euler_elements = ['x', 'y', 'z']
    self._headings['xsens-segments']['orientation_euler_deg'] = \
      ['%s (%s)' % (name, element) for name in (segment_names_body + segment_names_fingers)
                                   for element in euler_elements]
    # Segment positions
    self._headings.setdefault('xsens-segments', {})
    position_elements = ['x', 'y', 'z']
    self._headings['xsens-segments']['position_cm'] = \
      ['%s (%s)' % (name, element) for name in (segment_names_body + segment_names_fingers)
                                   for element in position_elements]
    # Sensors
    self._headings.setdefault('xsens-sensors', {})
    sensor_elements = ['x', 'y', 'z']
    self._headings['xsens-sensors']['sensors-xyz'] = \
      ['%s (%s)' % (name, element) for name in (sensor_names)
                                   for element in sensor_elements]
    sensor_elements = ['q0_re', 'q1_i', 'q2_j', 'q3_k']
    self._headings['xsens-sensors']['sensors-quaternion'] = \
      ['%s (%s)' % (name, element) for name in (sensor_names)
                                   for element in sensor_elements]
    # Joint rotation names
    self._headings.setdefault('xsens-joints', {})
    self._headings['xsens-joints']['joint_rotation_names_body'] = joint_rotation_names_body
    self._headings['xsens-joints']['joint_rotation_names_fingers'] = joint_rotation_names_fingers
    self._headings['xsens-joints']['joint_rotation_names_ergonomic'] = joint_rotation_names_ergonomic
    self._headings['xsens-joints']['joint_rotation_names_streamed'] = joint_rotation_names_body + joint_rotation_names_ergonomic
    self._headings['xsens-joints']['joint_rotation_names_bodyFingers'] = joint_rotation_names_body + joint_rotation_names_fingers
    # Joint names (used within the rotation names above)
    self._headings['xsens-joints']['joint_names_body'] = joint_names_body
    self._headings['xsens-joints']['joint_names_fingers'] = joint_names_fingers
    self._headings['xsens-joints']['joint_names_ergonomic'] = joint_names_ergonomic
    self._headings['xsens-joints']['joint_names_streamed'] = joint_names_body + joint_names_ergonomic
    # Joint parent/child segment/point IDs/names
    self._headings.setdefault('xsens-joints', {})
    self._headings['xsens-joints']['joint_rotation_streamed_parents_segmentIDs'] = {
      'streamed' : joint_parents_segmentIDs,
      'body'     : OrderedDict(list(joint_parents_segmentIDs.items())[0:22]),
      'ergonomic': OrderedDict(list(joint_parents_segmentIDs.items())[22:])}
    self._headings['xsens-joints']['joint_rotation_streamed_parents_segmentNames'] = {
      'streamed' : joint_parents_segmentNames,
      'body'     : OrderedDict(list(joint_parents_segmentNames.items())[0:22]),
      'ergonomic': OrderedDict(list(joint_parents_segmentNames.items())[22:])}
    self._headings['xsens-joints']['joint_rotation_streamed_parents_pointIDs'] = {
      'streamed' : joint_parents_pointIDs,
      'body'     : OrderedDict(list(joint_parents_pointIDs.items())[0:22]),
      'ergonomic': OrderedDict(list(joint_parents_pointIDs.items())[22:])}
    self._headings['xsens-joints']['joint_rotation_streamed_children_segmentIDs'] = {
      'streamed' : joint_children_segmentIDs,
      'body'     : OrderedDict(list(joint_children_segmentIDs.items())[0:22]),
      'ergonomic': OrderedDict(list(joint_children_segmentIDs.items())[22:])}
    self._headings['xsens-joints']['joint_rotation_streamed_children_segmentNames'] = {
      'streamed' : joint_children_segmentNames,
      'body'     : OrderedDict(list(joint_children_segmentNames.items())[0:22]),
      'ergonomic': OrderedDict(list(joint_children_segmentNames.items())[22:])}
    self._headings['xsens-joints']['joint_rotation_streamed_children_pointIDs'] = {
      'streamed' : joint_children_pointIDs,
      'body'     : OrderedDict(list(joint_children_pointIDs.items())[0:22]),
      'ergonomic': OrderedDict(list(joint_children_pointIDs.items())[22:])}
    self._headings['xsens-joints']['segmentIDsToNames'] = OrderedDict([(i+1, name) for (i, name) in enumerate(segment_names_body + segment_names_fingers)])
    # Foot contacts
    self._headings.setdefault('xsens-foot-contacts', {})
    self._headings['xsens-foot-contacts']['foot-contacts'] = foot_contact_names
