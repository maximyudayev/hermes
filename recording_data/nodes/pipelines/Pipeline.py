from abc import abstractmethod

import zmq

from nodes.Node import Node
from producers import PRODUCERS
from streams.Stream import Stream
from utils.time_utils import *
from utils.dict_utils import *
from utils.print_utils import *
from utils.zmq_utils import *


##############################################################
##############################################################
# An abstract class to interface with a data-producing worker.
#   I.e. a superclass for AI worker, controllable GUI, etc.
##############################################################
##############################################################
class Pipeline(Node):
  def __init__(self,
               classes: list[str] = [],
               port_pub: str = PORT_BACKEND,
               port_sub: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               stream_info: dict = None,
               print_status: bool = True,
               print_debug: bool = False) -> None:
    super().__init__(port_sync, port_killsig, print_status, print_debug)
    self._port_pub = port_pub
    self._port_sub = port_sub
    self._classes = classes

    # Data structure for keeping track of data.
    self._stream: Stream = self.create_stream(stream_info)


  # Instantiate Stream datastructure object specific to this Pipeline.
  #   Should also be a class method to create Stream objects on consumers. 
  @classmethod
  @abstractmethod
  def create_stream(cls, stream_info: dict) -> Stream:
    pass


  # Initialize backend parameters specific to Pipeline.
  def _initialize(self):
    super()._initialize()

    # Socket to publish sensor data and log.
    self._pub: zmq.SyncSocket = self._ctx.socket(zmq.PUB)
    self._pub.connect("tcp://%s:%s" % (DNS_LOCALHOST, self._port_pub))

    # Socket to subscribe to other Producers.
    self._sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    self._sub.connect("tcp://%s:%s" % (DNS_LOCALHOST, self._port_sub))
    
    for class_type in self._classes:
      # Subscribe to topics for each mentioned local and remote streamer.
      self._sub.subscribe(PRODUCERS[class_type]._log_source_tag)


  # Launch data receiving and result producing.
  def _activate_data_poller(self) -> None:
    self._poller.register(self._sub, zmq.POLLIN)
    self._poller.register(self._pub, zmq.POLLOUT)


  # Process custom event first, then Node generic (killsig).
  def _on_poll(self, poll_res):
    if self._sub in poll_res[0]:
      # TODO: process until all data sources sent 'END' packet.
      pass
    if self._pub in poll_res[0]:
      self._process_data()
    super()._on_poll(poll_res)


  # Iteration loop logic for the worker.
  @abstractmethod
  def _process_data(self) -> None:
    pass


  # TODO:
  def _trigger_stop(self):
    self._is_continue_capture = False
    self._stop_new_data()


  # Stop sampling data, continue sending already captured until none is left.
  @abstractmethod
  def _stop_new_data(self) -> None:
    pass


  @abstractmethod
  def _cleanup(self) -> None:
    self._pub.close()
    self._sub.close()
    super()._cleanup()
