import zmq
from handlers.PupilFacade import PupilFacade
from producers.Producer import Producer
from streams.EyeStream import EyeStream
from utils.msgpack_utils import serialize
from utils.zmq_utils import *

#######################################################
#######################################################
# A class to interface with the Pupil Labs eye tracker.
#######################################################
#######################################################
class EyeStreamer(Producer):
  @property
  def _log_source_tag(self) -> str:
    return 'eye'


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
               print_debug: bool = False,
               **_) -> None:

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

    super().__init__(port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     stream_info=stream_info,
                     print_status=print_status,
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict) -> EyeStream:
    return EyeStream(**stream_info)


  def _connect(self) -> bool:
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


  def _process_data(self) -> None:
    if self._is_continue_capture:
      time_s, data = self._handler.process_pupil_data()

      # Store the data.
      self._stream.append_data(time_s=time_s, data=data)
      # Get serialized object to send over ZeroMQ.
      msg = serialize(time_s=time_s, data=data)
      # Send the data packet on the PUB socket.
      self._pub.send_multipart([("%s.data" % (self._log_source_tag)).encode('utf-8'), msg])
    else:
      self._send_end_packet()


  def _stop_new_data(self):
    self._handler.close()


  def _cleanup(self):
    super()._cleanup()


# TODO: update the unit test.
#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  stream_info = {
    'pupil_capture_ip'      : 'localhost',
    'pupil_capture_port'    : '50020',
    'video_image_format'    : 'bgr',
    'gaze_estimate_stale_s' : 0.2,
    'stream_video_world'    : False, # the world video
    'stream_video_worldGaze': True, # the world video with gaze indication overlayed
    'stream_video_eye'      : False, # video of the eye
    'is_binocular'          : True, # uses both eyes for gaze data and for video
    'shape_video_world'     : (720,1280,3),
    'shape_video_eye0'      : (400,400,3),
    'shape_video_eye1'      : (400,400,3),
    'fps_video_world'       : 30.0,
    'fps_video_eye0'        : 120.0,
    'fps_video_eye1'        : 120.0
  }

  ip = IP_LOOPBACK
  port_backend = PORT_BACKEND
  port_frontend = PORT_FRONTEND
  port_sync = PORT_SYNC
  port_killsig = PORT_KILL

  # Pass exactly one ZeroMQ context instance throughout the program
  ctx: zmq.Context = zmq.Context()

  # Exposes a known address and port to locally connected sensors to connect to.
  local_backend: zmq.SyncSocket = ctx.socket(zmq.XSUB)
  local_backend.bind("tcp://%s:%s" % (IP_LOOPBACK, port_backend))
  backends: list[zmq.SyncSocket] = [local_backend]

  # Exposes a known address and port to broker data to local workers.
  local_frontend: zmq.SyncSocket = ctx.socket(zmq.XPUB)
  local_frontend.bind("tcp://%s:%s" % (IP_LOOPBACK, port_frontend))
  frontends: list[zmq.SyncSocket] = [local_frontend]

  streamer = EyeStreamer(**stream_info, 
                         port_pub=port_backend,
                         port_sync=port_sync,
                         port_killsig=port_killsig)

  streamer()
