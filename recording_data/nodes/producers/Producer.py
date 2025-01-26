from abc import abstractmethod

import zmq

from nodes.Node import Node
from streams.Stream import Stream
from utils.time_utils import *
from utils.dict_utils import *
from utils.print_utils import *
from utils.zmq_utils import *


###########################################################
###########################################################
# An abstract class to interface with a particular sensor.
#   I.e. a superclass for DOTs, PupilCore, or Camera class.
# TODO: add logger thread.
# TODO: add propagation delay thread.
###########################################################
###########################################################
class Producer(Node):
  def __init__(self, 
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               stream_info: dict = None,
               print_status: bool = True,
               print_debug: bool = False) -> None:
    super().__init__(port_sync, port_killsig, print_status, print_debug)
    self._port_pub = port_pub
    self._is_continue_capture = True

    # Data structure for keeping track of data
    self._stream: Stream = self.create_stream(stream_info)


  # Instantiate Stream datastructure object specific to this Streamer.
  #   Should also be a class method to create Stream objects on consumers. 
  @classmethod
  @abstractmethod
  def create_stream(cls, stream_info: dict) -> Stream:
    pass


  # Initialize backend parameters specific to Producer.
  def _initialize(self):
    super()._initialize()
    # Socket to publish sensor data and log
    self._pub: zmq.SyncSocket = self._ctx.socket(zmq.PUB)
    self._pub.connect("tcp://%s:%s" % (DNS_LOCALHOST, self._port_pub))


  # Connect to the sensor device(s).
  @abstractmethod
  def _connect(self) -> bool:
    pass


  # Launch data streaming from the device.
  def _activate_data_poller(self) -> None:
    self._poller.register(self._pub, zmq.POLLOUT)

  
  # Process custom event first, then Node generic (killsig).
  def _on_poll(self, poll_res):
    if self._pub in poll_res[0]:
      self._process_data()
    super()._on_poll(poll_res)


  # Iteration loop logic for the sensor.
  # Acquire data from your sensor as desired, and for each timestep.
  # SDK thread pushes data into shared memory space, this thread pulls data and does all the processing,
  #   ensuring that lost packets are responsibility of the slow consumer.
  @abstractmethod
  def _process_data(self) -> None:
    pass


  def _trigger_stop(self):
    self._is_continue_capture = False
    self._stop_new_data()


  # Stop sampling data, continue sending already captured until none is left.
  @abstractmethod
  def _stop_new_data(self) -> None:
    pass


  # Send 'END' empty packet and label Node as done to safely finish and exit the process and its threads.
  def _send_end_packet(self) -> None:
    self._pub.send_multipart([("%s.data" % self._log_source_tag).encode('utf-8'), b'', CMD_END.encode('utf-8')])
    self._is_done = True


  # Cleanup sensor specific resources, then Producer generics, then Node generics.
  @abstractmethod
  def _cleanup(self) -> None:
    # Before closing the PUB socket, wait for the 'BYE' signal from the Broker.
    self._sync.recv() # no need to read contents of the message.
    self._pub.close()
    # TODO: join the logger thread.
    super()._cleanup()
