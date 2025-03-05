from nodes.Node import Node
from producers.Producer import Producer
from pipelines import PIPELINES
from producers import PRODUCERS
from streams import Stream

from abc import abstractmethod
from collections import OrderedDict
import zmq

from utils.msgpack_utils import deserialize
from utils.zmq_utils import *


##########################################################
##########################################################
# An abstract class to interface with a particular worker.
#   I.e. a superclass for a data logger or passive GUI.
#   Does not by default log consumed data.
##########################################################
##########################################################
class Consumer(Node):
  def __init__(self,
               stream_specs: list[dict],
               port_sub: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               log_history_filepath: str = None,
               print_status: bool = True,
               print_debug: bool = False) -> None:
    super().__init__(port_sync, port_killsig, print_status, print_debug)
    self._port_sub = port_sub
    self._log_history_filepath = log_history_filepath

    self._is_producer_ended: OrderedDict[str, bool] = OrderedDict()
    self._poll_data_fn = self._poll_data_packets

    # Instantiate all desired Streams that DataLogger will subscribe to.
    self._streams: OrderedDict[str, Stream] = OrderedDict()
    for stream_spec in stream_specs:
      class_name: str = stream_spec['class']
      class_args = stream_spec.copy()
      del(class_args['class'])
      # Create the class object.
      class_type: type[Producer] = {**PRODUCERS,**PIPELINES}[class_name]
      class_object: Stream = class_type.create_stream(class_type, class_args)
      # Store the streamer object.
      self._streams.setdefault(class_type._log_source_tag(), class_object)
      self._is_producer_ended.setdefault(class_type._log_source_tag(), False)


  # Initialize backend parameters specific to Consumer.
  def _initialize(self):
    super()._initialize()
    # Socket to subscribe to SensorStreamers
    self._sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    self._sub.connect("tcp://%s:%s" % (DNS_LOCALHOST, self._port_sub))
    
    # Subscribe to topics for each mentioned local and remote streamer
    for tag in self._streams.keys():
      self._sub.subscribe(tag)


  # Launch data receiving.
  def _activate_data_poller(self) -> None:
    self._poller.register(self._sub, zmq.POLLIN)


  # Process custom event first, then Node generic (killsig).
  def _on_poll(self, poll_res):
    if self._sub in poll_res[0]:
      self._poll_data_fn()
    super()._on_poll(poll_res)


  # In normal operation mode, all messages are 2-part.
  def _poll_data_packets(self) -> None:
    topic, payload = self._sub.recv_multipart()
    msg = deserialize(payload)
    topic_tree: list[str] = topic.decode('utf-8').split('.')
    self._streams[topic_tree[0]].append_data(**msg)


  # When system triggered a safe exit, Consumer gets a mix of normal 2-part messages
  #   and 3-part 'END' message from each Producer that safely exited.
  #   It's more efficient to dynamically switch the callback instead of checking every message.
  def _poll_ending_data_packets(self) -> None:
    # Process until all data sources sent 'END' packet.
    message = self._sub.recv_multipart()
    # Regular data packets.
    if len(message) == 2:
      topic, payload = message[0], message[1]
      msg = deserialize(payload)
      topic_tree: list[str] = topic.decode('utf-8').split('.')
      self._streams[topic_tree[0]].append_data(**msg)
    # 'END' empty packet from a Producer.
    elif len(message) == 3 and CMD_END.encode('utf-8') in message:
      topic = message[0]
      topic_tree: list[str] = topic.decode('utf-8').split('.')
      self._is_producer_ended[topic[0]] = True
      if all(list(self._is_producer_ended.values())):
        self._is_done = True


  def _trigger_stop(self):
    self._poll_data_fn = self._poll_ending_data_packets


  @abstractmethod
  def _cleanup(self):
    self._sub.close()
    super()._cleanup()
