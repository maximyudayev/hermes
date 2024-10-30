from collections import OrderedDict

import numpy as np
from streamers import SensorStreamer
from streams import Stream
from visualizers import VideoVisualizer

################################################
################################################
# A structure to store DOTs stream's data.
################################################
################################################
class EyeStream(Stream):
  def __init__(self,
               stream_video_world: bool,
               stream_video_worldGaze: bool,
               stream_video_eye: bool,
               is_binocular: bool,
               gaze_data: dict,
               pupil_data: dict,
               video_world_data: dict,
               video_eye0_data: dict,
               video_eye1_data: dict,
               fps_video_world: float,
               fps_video_eye0: float,
               fps_video_eye1: float) -> None:
    super(EyeStream, self).__init__()

    # Define data notes that will be associated with streams created below.
    self._define_data_notes()

    # Create a stream for the Pupil Core time, to help evaluate drift and offsets.
    # Note that core time is included with each other stream as well,
    #  but include a dedicated one too just in case there are delays in sending
    #  the other data payloads.
    self.add_stream(device_name='eye-tracking-time', stream_name='pupilCore_time_s',
                    data_type='float64', sample_size=[1],
                    sampling_rate_hz=None, extra_data_info=None,
                    data_notes=self._data_notes['eye-tracking-time']['pupilCore_time_s'])
    # Create streams for gaze data.
    for (stream_name, data) in gaze_data.items():
      sample_size = np.array(data).shape
      if len(sample_size) == 0: # it was probably a scalar
        sample_size = 1
      self.add_stream(device_name='eye-tracking-gaze', stream_name=stream_name,
                        data_type='float64', sample_size=sample_size,
                        sampling_rate_hz=None, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-gaze'][stream_name])
    # Create streams for pupil data.
    for (stream_name, data) in pupil_data.items():
      sample_size = np.array(data).shape
      if len(sample_size) == 0: # it was probably a scalar
        sample_size = 1
      self.add_stream(device_name='eye-tracking-pupil', stream_name=stream_name,
                        data_type='float64', sample_size=sample_size,
                        sampling_rate_hz=None, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-pupil'][stream_name])
    # Create streams for video data.
    if stream_video_world:
      self.add_stream(device_name='eye-tracking-video-world', stream_name='frame_timestamp',
                        data_type='float64', sample_size=(1),
                        sampling_rate_hz=fps_video_world, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-world']['frame_timestamp'])
      self.add_stream(device_name='eye-tracking-video-world', stream_name='frame_index',
                        data_type='uint64', sample_size=(1),
                        sampling_rate_hz=fps_video_world, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-world']['frame_index'])
      self.add_stream(device_name='eye-tracking-video-world', stream_name='frame',
                        data_type='uint8', sample_size=(video_world_data['frame'].shape),
                        sampling_rate_hz=fps_video_world, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-world']['frame'],
                        is_video=True)
    if stream_video_worldGaze:
      self.add_stream(device_name='eye-tracking-video-worldGaze', stream_name='frame_timestamp',
                        data_type='float64', sample_size=(1),
                        sampling_rate_hz=fps_video_world, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-worldGaze']['frame_timestamp'])
      self.add_stream(device_name='eye-tracking-video-worldGaze', stream_name='frame_index',
                        data_type='uint64', sample_size=(1),
                        sampling_rate_hz=fps_video_world, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-worldGaze']['frame_index'])
      self.add_stream(device_name='eye-tracking-video-worldGaze', stream_name='frame',
                        data_type='uint8', sample_size=(video_world_data['frame'].shape),
                        sampling_rate_hz=fps_video_world, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-worldGaze']['frame'],
                        is_video=True)
    if stream_video_eye:
      self.add_stream(device_name='eye-tracking-video-eye0', stream_name='frame_timestamp',
                        data_type='float64', sample_size=(1),
                        sampling_rate_hz=fps_video_eye0, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-eye0']['frame_timestamp'])
      self.add_stream(device_name='eye-tracking-video-eye0', stream_name='frame_index',
                        data_type='uint64', sample_size=(1),
                        sampling_rate_hz=fps_video_eye0, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-eye0']['frame_index'])
      self.add_stream(device_name='eye-tracking-video-eye0', stream_name='frame',
                        data_type='uint8', sample_size=(video_eye0_data['frame'].shape),
                        sampling_rate_hz=fps_video_eye0, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-eye0']['frame'],
                        is_video=True)
      if is_binocular:
        self.add_stream(device_name='eye-tracking-video-eye1', stream_name='frame_timestamp',
                        data_type='float64', sample_size=(1),
                        sampling_rate_hz=fps_video_eye1, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-eye1']['frame_timestamp'])
        self.add_stream(device_name='eye-tracking-video-eye1', stream_name='frame_index',
                        data_type='uint64', sample_size=(1),
                        sampling_rate_hz=fps_video_eye1, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-eye1']['frame_index'])
        self.add_stream(device_name='eye-tracking-video-eye1', stream_name='frame',
                        data_type='uint8', sample_size=(video_eye1_data['frame'].shape),
                        sampling_rate_hz=fps_video_eye1, extra_data_info=None,
                        data_notes=self._data_notes['eye-tracking-video-eye1']['frame'],
                        is_video=True)

  # Append processed data to the sensor streams.
  def append_data(self, time_s: float, processed_data: dict):
    for (device_name_key, streams_data) in processed_data.items():
      device_name = 'eye-tracking-%s' % device_name_key
      if streams_data is not None:
        for (stream_name, data) in streams_data.items():
          self._append_data(device_name, stream_name, time_s, data)


  ###########################
  ###### VISUALIZATION ######
  ###########################

  # Specify how the streams should be visualized.
  # visualization_options can have entries for 'video-worldGaze', 'video-eyeX', and 'video-world'.
  def get_default_visualization_options(self, visualization_options=None):
    # Specify default options.
    visualization_options = {
      'eye-tracking-video-worldGaze': {'frame': {'class': VideoVisualizer}},
      'eye-tracking-video-world':     {'frame': {'class': None}},
      'eye-tracking-video-eye0':      {'frame': {'class': None}},
      'eye-tracking-video-eye1':      {'frame': {'class': None}},
    }
    # Override with any provided options.
    if isinstance(visualization_options, dict):
      if 'video-worldGaze' in visualization_options:
        for (k, v) in visualization_options['video-worldGaze'].items():
          visualization_options['eye-tracking-video-worldGaze'][k] = v
      if 'video-world' in visualization_options:
        for (k, v) in visualization_options['video-world'].items():
          visualization_options['eye-tracking-video-world'][k] = v
      if 'video-eye0' in visualization_options:
        for (k, v) in visualization_options['video-eye0'].items():
          visualization_options['eye-tracking-video-eye0'][k] = v
      if 'video-eye1' in visualization_options:
        for (k, v) in visualization_options['video-eye1'].items():
          visualization_options['eye-tracking-video-eye1'][k] = v

    # Add default options for all other devices/streams.
    for (device_name, device_info) in self._streams_info.items():
      visualization_options.setdefault(device_name, {})
      for (stream_name, stream_info) in device_info.items():
        visualization_options[device_name].setdefault(stream_name, {'class': None})

    return visualization_options

  def _define_data_notes(self):
    self._data_notes = {}
    self._data_notes.setdefault('eye-tracking-gaze', {})
    self._data_notes.setdefault('eye-tracking-pupil', {})
    self._data_notes.setdefault('eye-tracking-time', {})
    self._data_notes.setdefault('eye-tracking-video-eye0', {})
    self._data_notes.setdefault('eye-tracking-video-eye1', {})
    self._data_notes.setdefault('eye-tracking-video-world', {})
    self._data_notes.setdefault('eye-tracking-video-worldGaze', {})

    # Gaze data
    self._data_notes['eye-tracking-gaze']['confidence'] = OrderedDict([
      ('Range', '[0, 1]'),
      ('Description', 'Confidence of the gaze detection'),
      ('PupilCapture key', 'gaze.Xd. > confidence'),
    ])
    self._data_notes['eye-tracking-gaze']['eye_center_3d'] = OrderedDict([
      ('Units', 'mm'),
      ('Notes', 'Maps pupil positions into the world camera coordinate system'),
      (SensorStreamer.metadata_data_headings_key, ['x','y','z']),
      ('PupilCapture key', 'gaze.3d. > eye_center_3d'),
    ])
    self._data_notes['eye-tracking-gaze']['normal_3d'] = OrderedDict([
      ('Units', 'mm'),
      ('Notes', 'Maps pupil positions into the world camera coordinate system'),
      (SensorStreamer.metadata_data_headings_key, ['x','y','z']),
      ('PupilCapture key', 'gaze.3d. > gaze_normal_3d'),
    ])
    self._data_notes['eye-tracking-gaze']['point_3d'] = OrderedDict([
      ('Units', 'mm'),
      ('Notes', 'Maps pupil positions into the world camera coordinate system'),
      (SensorStreamer.metadata_data_headings_key, ['x','y','z']),
      ('PupilCapture key', 'gaze.3d. > gaze_point_3d'),
    ])
    self._data_notes['eye-tracking-gaze']['position'] = OrderedDict([
      ('Description', 'The normalized gaze position in image space, corresponding to the world camera image'),
      ('Units', 'normalized between [0, 1]'),
      ('Origin', 'bottom left'),
      (SensorStreamer.metadata_data_headings_key, ['x','y']),
      ('PupilCapture key', 'gaze.Xd. > norm_pos'),
    ])
    self._data_notes['eye-tracking-gaze']['timestamp'] = OrderedDict([
      ('Description', 'The timestamp recorded by the Pupil Capture software, '
                      'which should be more precise than the system time when the data was received (the time_s field).  '
                      'Note that Pupil Core time was synchronized with system time at the start of recording, accounting for communication delays.'),
      ('PupilCapture key', 'gaze.Xd. > timestamp'),
    ])

    # Pupil data
    self._data_notes['eye-tracking-pupil']['confidence'] = OrderedDict([
      ('Range', '[0, 1]'),
      ('Description', 'Confidence of the pupil detection'),
      ('PupilCapture key', 'gaze.Xd. > base_data > confidence'),
    ])
    self._data_notes['eye-tracking-pupil']['circle3d_center'] = OrderedDict([
      ('Units', 'mm'),
      ('PupilCapture key', 'gaze.Xd. > base_data > circle_3d > center'),
    ])
    self._data_notes['eye-tracking-pupil']['circle3d_normal'] = OrderedDict([
      ('Units', 'mm'),
      ('PupilCapture key', 'gaze.Xd. > base_data > circle_3d > normal'),
    ])
    self._data_notes['eye-tracking-pupil']['circle3d_radius'] = OrderedDict([
      ('Units', 'mm'),
      ('PupilCapture key', 'gaze.Xd. > base_data > circle_3d > radius'),
    ])
    self._data_notes['eye-tracking-pupil']['diameter'] = OrderedDict([
      ('Units', 'pixels'),
      ('Notes', 'The estimated pupil diameter in image space, corresponding to the eye camera image'),
      ('PupilCapture key', 'gaze.Xd. > base_data > diameter'),
    ])
    self._data_notes['eye-tracking-pupil']['diameter3d'] = OrderedDict([
      ('Units', 'mm'),
      ('Notes', 'The estimated pupil diameter in 3D space'),
      ('PupilCapture key', 'gaze.Xd. > base_data > diameter_3d'),
    ])
    self._data_notes['eye-tracking-pupil']['polar_phi'] = OrderedDict([
      ('Notes', 'Pupil polar coordinate on 3D eye model. The model assumes a fixed eye ball size, so there is no radius key.'),
      ('See also', 'polar_theta is the other polar coordinate'),
      ('PupilCapture key', 'gaze.Xd. > base_data > phi'),
    ])
    self._data_notes['eye-tracking-pupil']['polar_theta'] = OrderedDict([
      ('Notes', 'Pupil polar coordinate on 3D eye model. The model assumes a fixed eye ball size, so there is no radius key.'),
      ('See also', 'polar_phi is the other polar coordinate'),
      ('PupilCapture key', 'gaze.Xd. > base_data > theta'),
    ])
    self._data_notes['eye-tracking-pupil']['position'] = OrderedDict([
      ('Description', 'The normalized pupil position in image space, corresponding to the eye camera image'),
      ('Units', 'normalized between [0, 1]'),
      ('Origin', 'bottom left'),
      (SensorStreamer.metadata_data_headings_key, ['x','y']),
      ('PupilCapture key', 'gaze.Xd. > base_data > norm_pos'),
    ])
    self._data_notes['eye-tracking-pupil']['projected_sphere_angle'] = OrderedDict([
      ('Description', 'Projection of the 3D eye ball sphere into image space corresponding to the eye camera image'),
      ('Units', 'degrees'),
      ('PupilCapture key', 'gaze.Xd. > base_data > projected_sphere > angle'),
    ])
    self._data_notes['eye-tracking-pupil']['projected_sphere_axes'] = OrderedDict([
      ('Description', 'Projection of the 3D eye ball sphere into image space corresponding to the eye camera image'),
      ('Units', 'pixels'),
      ('Origin', 'bottom left'),
      ('PupilCapture key', 'gaze.Xd. > base_data > projected_sphere > axes'),
    ])
    self._data_notes['eye-tracking-pupil']['projected_sphere_center'] = OrderedDict([
      ('Description', 'Projection of the 3D eye ball sphere into image space corresponding to the eye camera image'),
      ('Units', 'pixels'),
      ('Origin', 'bottom left'),
      (SensorStreamer.metadata_data_headings_key, ['x','y']),
      ('PupilCapture key', 'gaze.Xd. > base_data > projected_sphere > center'),
    ])
    self._data_notes['eye-tracking-pupil']['sphere_center'] = OrderedDict([
      ('Description', 'The 3D eye ball sphere'),
      ('Units', 'mm'),
      (SensorStreamer.metadata_data_headings_key, ['x','y','z']),
      ('PupilCapture key', 'gaze.Xd. > base_data > sphere > center'),
    ])
    self._data_notes['eye-tracking-pupil']['sphere_radius'] = OrderedDict([
      ('Description', 'The 3D eye ball sphere'),
      ('Units', 'mm'),
      ('PupilCapture key', 'gaze.Xd. > base_data > sphere > radius'),
    ])
    self._data_notes['eye-tracking-pupil']['timestamp'] = OrderedDict([
      ('Description', 'The timestamp recorded by the Pupil Capture software, '
                      'which should be more precise than the system time when the data was received (the time_s field).  '
                      'Note that Pupil Core time was synchronized with system time at the start of recording, accounting for communication delays.'),
      ('PupilCapture key', 'gaze.Xd. > base_data > timestamp'),
    ])

    # Time
    self._data_notes['eye-tracking-time']['pupilCore_time_s'] = OrderedDict([
      ('Description', 'The timestamp fetched from the Pupil Core service, which can be used for alignment to system time in time_s.  '
                      'As soon as system time time_s was recorded, a command was sent to Pupil Capture to get its time; '
                      'so a slight communication delay is included on the order of milliseconds.  '
                      'Note that Pupil Core time was synchronized with system time at the start of recording, accounting for communication delays.'),
    ])

    # Eye videos
    for i in range(2):
      self._data_notes['eye-tracking-video-eye%s' % i]['frame_timestamp'] = OrderedDict([
        ('Description', 'The timestamp recorded by the Pupil Core service, '
                        'which should be more precise than the system time when the data was received (the time_s field).  '
                        'Note that Pupil Core time was synchronized with system time at the start of recording, accounting for communication delays.'),
      ])
      self._data_notes['eye-tracking-video-eye%s' % i]['frame_index'] = OrderedDict([
        ('Description', 'The frame index recorded by the Pupil Core service, '
                        'which relates to world frame used for annotation'),
      ])
      self._data_notes['eye-tracking-video-eye%s' % i]['frame'] = OrderedDict([
        ('Format', 'Frames are in BGR format'),
      ])
    # World video
    self._data_notes['eye-tracking-video-world']['frame_timestamp'] = OrderedDict([
      ('Description', 'The timestamp recorded by the Pupil Core service, '
                      'which should be more precise than the system time when the data was received (the time_s field).  '
                      'Note that Pupil Core time was synchronized with system time at the start of recording, accounting for communication delays.'),
    ])
    self._data_notes['eye-tracking-video-world']['frame_index'] = OrderedDict([
      ('Description', 'The frame index recorded by the Pupil Core service, '
                      'which relates to world frame used for annotation'),
    ])
    self._data_notes['eye-tracking-video-world']['frame'] = OrderedDict([
      ('Format', 'Frames are in BGR format'),
    ])
    # World-gaze video
    self._data_notes['eye-tracking-video-worldGaze']['frame_timestamp'] = OrderedDict([
      ('Description', 'The timestamp recorded by the Pupil Core service, '
                      'which should be more precise than the system time when the data was received (the time_s field).  '
                      'Note that Pupil Core time was synchronized with system time at the start of recording, accounting for communication delays.'),
    ])
    self._data_notes['eye-tracking-video-worldGaze']['frame_index'] = OrderedDict([
      ('Description', 'The frame index recorded by the Pupil Core service, '
                      'which relates to world frame used for annotation'),
    ])
    self._data_notes['eye-tracking-video-worldGaze']['frame'] = OrderedDict([
      ('Format', 'Frames are in BGR format'),
      ('Description', 'The world video with a gaze estimate overlay.  '
                      'The estimate in eye-tracking-gaze > position was used.  '
                      'The gaze indicator is black if the gaze estimate is \'stale\','
                      'defined here as being predicted more than %gs before the video frame.' % self._gaze_estimate_stale_s),
    ])
