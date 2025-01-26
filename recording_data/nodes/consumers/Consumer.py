from abc import abstractmethod

import zmq

from nodes.Node import Node
from producers import PRODUCERS
from utils.zmq_utils import *


##########################################################
##########################################################
# An abstract class to interface with a particular worker.
#   I.e. a superclass for a data logger or passive GUI.
##########################################################
##########################################################
class Consumer(Node):
  def __init__(self,
               classes: list[str] = [],
               port_sub: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               print_status: bool = True,
               print_debug: bool = False) -> None:
    super().__init__(port_sync, port_killsig, print_status, print_debug)
    self._port_sub = port_sub
    self._classes = classes


  # Initialize backend parameters specific to Consumer.
  def _initialize(self):
    super()._initialize()
    # Socket to subscribe to SensorStreamers
    self._sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    self._sub.connect("tcp://%s:%s" % (DNS_LOCALHOST, self._port_sub))
    
    # Subscribe to topics for each mentioned local and remote streamer
    for class_type in self._classes:
      self._sub.subscribe(PRODUCERS[class_type]._log_source_tag)


  # Launch data receiving.
  def _activate_data_poller(self) -> None:
    self._poller.register(self._sub, zmq.POLLIN)


  # Process custom event first, then Node generic (killsig).
  def _on_poll(self, poll_res):
    if self._sub in poll_res[0]:
      # TODO: process until all data sources sent 'END' packet.
      pass
    super()._on_poll(poll_res)


  # TODO:
  def _trigger_stop(self):
    pass


  @abstractmethod
  def _cleanup(self):
    self._sub.close()
    super()._cleanup()
