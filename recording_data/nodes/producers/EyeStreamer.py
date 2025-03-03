from producers import Producer
from streams import EyeStream
from handlers.PupilFacade import PupilFacade
from utils.zmq_utils import *
import zmq


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
               logging_spec: dict,
               pupil_capture_ip: str = DNS_LOCALHOST,
               pupil_capture_port: str = PORT_EYE,
               video_image_format: str = "bgr", # bgr or jpeg
               gaze_estimate_stale_s: float = 0.2, # how long before a gaze estimate is considered stale (changes color in the world-gaze video)
               stream_video_world: bool = False, 
               stream_video_eye: bool = False, 
               is_binocular: bool = True,
               shape_video_world: tuple[int] = (1080,720,3),
               shape_video_eye0: tuple[int] = (192,192,3),
               shape_video_eye1: tuple[int] = (192,192,3),
               fps_video_world: float = 30.0,
               fps_video_eye0: float = 120.0,
               fps_video_eye1: float = 120.0,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               port_pause: str = PORT_PAUSE,
               print_status: bool = True,
               print_debug: bool = False,
               **_) -> None:

    self._stream_video_world = stream_video_world
    self._stream_video_eye = stream_video_eye
    self._is_binocular = is_binocular
    self._pupil_capture_ip = pupil_capture_ip
    self._pupil_capture_port = pupil_capture_port
    self._video_image_format = video_image_format
    self._gaze_estimate_stale_s = gaze_estimate_stale_s
    self._port_pause = port_pause

    stream_info = {
      "stream_video_world": stream_video_world,
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

    super().__init__(stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status,
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict) -> EyeStream:
    return EyeStream(**stream_info)


  def _connect(self) -> bool:
    self._handler: PupilFacade = PupilFacade(stream_video_world=self._stream_video_world,
                                             stream_video_eye=self._stream_video_eye,
                                             is_binocular=self._is_binocular,
                                             pupil_capture_ip=self._pupil_capture_ip,
                                             pupil_capture_port=self._pupil_capture_port,
                                             video_image_format=self._video_image_format,
                                             gaze_estimate_stale_s=self._gaze_estimate_stale_s)
    self._handler.set_stream_data_getter(fn=self._stream.get_data_multiple_streams)
    return True


  def _process_data(self) -> None:
    if self._is_continue_capture:
      time_s, data = self._handler.process_data()
      tag: str = "%s.data" % self._log_source_tag
      self._publish(tag, time_s=time_s, data=data)
    else:
      self._send_end_packet()


  def _stop_new_data(self):
    self._handler.close()


  def _cleanup(self):
    self._pause.close()
    super()._cleanup()


  ##############################
  ###### Custom Overrides ######
  ##############################
  # For remote pause/resume control.
  # Initialize backend parameters specific to Producer.
  def _initialize(self):
    super()._initialize()
    # Socket to publish sensor data and log
    self._pause: zmq.SyncSocket = self._ctx.socket(zmq.REP)
    self._pause.bind("tcp://*:%s" % (self._port_pause))


  # Listen on the dedicated socket a pause command from the GUI.
  def _activate_data_poller(self) -> None:
    super()._activate_data_poller()
    self._poller.register(self._pause, zmq.POLLIN)


  def _on_poll(self, poll_res):
    if self._pause in poll_res[0]:
      self._pause.recv()
      is_enabled = self._handler.toggle_capturing()
      # NOTE: for now not waiting that the glasses received the message,
      #   but assumes that it happens fast enough before replying 'OK' to the GUI.
      self._pause.send_string(MSG_ON if is_enabled else MSG_OFF)
    super()._on_poll(poll_res)


# TODO: update the unit test.
#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  stream_info = {
    'pupil_capture_ip'      : DNS_LOCALHOST,
    'pupil_capture_port'    : PORT_EYE,
    'video_image_format'    : 'bgr',
    'gaze_estimate_stale_s' : 0.2,
    'stream_video_world'    : True, # the world video
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
