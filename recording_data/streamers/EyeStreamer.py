from handlers.PupilFacade import PupilFacade
from streamers.SensorStreamer import SensorStreamer
from streams.EyeStream import EyeStream
from utils.msgpack_utils import serialize

################################################
################################################
# A class to interface with the Pupil Labs eye tracker.
# Will stream gaze data in the video and world frames.
# Will stream world video and eye video.
################################################
################################################
class EyeStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'eye'

  ########################
  ###### INITIALIZE ######
  ########################

  def __init__(self,
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               pupil_capture_ip: str = "localhost",
               pupil_capture_port: str = "50020",
               video_image_format: str = "bgr", # bgr or jpeg
               gaze_estimate_stale_s: float = 0.2, # how long before a gaze estimate is considered stale (changes color in the world-gaze video)
               stream_video_world: bool = False, 
               stream_video_worldGaze: bool = True, 
               stream_video_eye: bool = False, 
               is_binocular: bool = True,
               shape_video_world: tuple[int] = (1080,720,3),
               shape_video_eye0: tuple[int] = (192,192,3),
               shape_video_eye1: tuple[int] = (192,192,3),
               fps_video_world: float = 30.0,
               fps_video_eye0: float = 120.0,
               fps_video_eye1: float = 120.0,
               print_status: bool = True,
               print_debug: bool = False) -> None:

    self._stream_video_world = stream_video_world
    self._stream_video_worldGaze = stream_video_worldGaze
    self._stream_video_eye = stream_video_eye
    self._is_binocular = is_binocular
    self._pupil_capture_ip = pupil_capture_ip
    self._pupil_capture_port = pupil_capture_port
    self._video_image_format = video_image_format
    self._gaze_estimate_stale_s = gaze_estimate_stale_s

    stream_info = {
      "stream_video_world": stream_video_world,
      "stream_video_worldGaze": stream_video_worldGaze,
      "stream_video_eye": stream_video_eye,
      "is_binocular": is_binocular,
      "gaze_estimate_stale_s": gaze_estimate_stale_s,
      "shape_video_world": shape_video_world,
      "shape_video_eye0": shape_video_eye0,
      "shape_video_eye1": shape_video_eye1,
      "fps_video_world": fps_video_world,
      "fps_video_eye0": fps_video_eye0,
      "fps_video_eye1": fps_video_eye1
    }

    super().__init__(self,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     stream_info=stream_info,
                     print_status=print_status,
                     print_debug=print_debug)


  # Factory class method called inside superclass's constructor to instantiate corresponding Stream object.
  def create_stream(cls, stream_info: dict) -> EyeStream:
    return EyeStream(**stream_info)


  # Connect to the data streams, detect video frame rates, and detect available data type (e.g. 2D vs 3D).
  def connect(self) -> bool:
    self._handler: PupilFacade = PupilFacade(stream_video_world=self._stream_video_world,
                                             stream_video_worldGaze=self._stream_video_worldGaze,
                                             stream_video_eye=self._stream_video_eye,
                                             is_binocular=self._is_binocular,
                                             pupil_capture_ip=self._pupil_capture_ip,
                                             pupil_capture_port=self._pupil_capture_port,
                                             video_image_format=self._video_image_format,
                                             gaze_estimate_stale_s=self._gaze_estimate_stale_s)
    self._handler.set_stream_data_getter(fn=self._stream.get_data)
    return True


  # Loop until self._running is False
  def run(self) -> None:
    while self._running:
      time_s, data = self._handler.process_pupil_data()
      
      # Store the data.
      self._stream.append_data(time_s=time_s, data=data)

      # Get serialized object to send over ZeroMQ.
      msg = serialize(time_s=time_s, data=data)

      # Send the data packet on the PUB socket.
      self._pub.send_multipart(["%s.data"%(self._log_source_tag), msg])


  # Clean up and quit
  def quit(self):
    self._handler.close()
    super().quit()
