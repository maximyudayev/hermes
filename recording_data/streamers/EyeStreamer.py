from handlers import PupilFacade
from streamers import SensorStreamer
from streams import EyeStream
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
               port_pub: str | None = None,
               port_sync: str | None = None,
               port_killsig: str | None = None,
               pupil_capture_ip: str = "localhost",
               pupil_capture_port: str = "50020",
               video_image_format: str = "bgr", # bgr or jpeg
               gaze_estimate_stale_s: float = 0.2, # how long before a gaze estimate is considered stale (changes color in the world-gaze video)
               stream_video_world: bool = True, 
               stream_video_worldGaze: bool = True, 
               stream_video_eye: bool = True, 
               is_binocular: bool = True,
               log_history_filepath: str | None = None,
               print_status: bool = True,
               print_debug: bool = False) -> None:

    self._handler: PupilFacade = PupilFacade(stream_video_world=stream_video_world,
                                             stream_video_worldGaze=stream_video_worldGaze,
                                             stream_video_eye=stream_video_eye,
                                             is_binocular=is_binocular,
                                             pupil_capture_ip=pupil_capture_ip,
                                             pupil_capture_port=pupil_capture_port,
                                             video_image_format=video_image_format,
                                             gaze_estimate_stale_s=gaze_estimate_stale_s)

    stream_info: dict = self._handler.get_stream_info()
    stream_info["stream_video_world"] = stream_video_world
    stream_info["stream_video_worldGaze"] = stream_video_worldGaze
    stream_info["stream_video_eye"] = stream_video_eye
    stream_info["is_binocular"] = is_binocular

    super(EyeStreamer, self).__init__(self,
                                      port_pub=port_pub,
                                      port_sync=port_sync,
                                      port_killsig=port_killsig,
                                      stream_info=stream_info,
                                      log_history_filepath=log_history_filepath,
                                      print_status=print_status,
                                      print_debug=print_debug)

  # Factory class method called inside superclass's constructor to instantiate corresponding Stream object.
  def create_stream(cls, stream_info: dict | None = None) -> EyeStream:
    return EyeStream(**stream_info)

  # Connect to the data streams, detect video frame rates, and detect available data type (e.g. 2D vs 3D).
  def connect(self):
    # TODO:
    return True

  # Loop until self._running is False
  def run(self):
    while self._running:
      time_s, data = self._handler.process_pupil_data()
      
      # Store the data.
      self._stream.append_data(time_s=time_s, data=data)

      # Get serialized object to send over ZeroMQ.
      msg = serialize(time_s=time_s, data=data)

      # Send the data packet on the PUB socket.
      self._pub.send_multipart([b"%s.data"%(self._log_source_tag), msg])

  # Clean up and quit
  def quit(self):
    pass
