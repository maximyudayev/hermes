from abc import ABC, abstractmethod

import zmq

from streams.Stream import Stream
from utils.time_utils import *
from utils.dict_utils import *
from utils.print_utils import *

################################################
################################################
# An abstract class to interface with a particular sensor.
#   For example, may be a superclass for DOTs, PupilCore, or Camera class.
################################################
################################################
class SensorStreamer(ABC):
  # Read-only property that every subclass must implement.
  @property
  @abstractmethod
  def _log_source_tag(self):
    pass

  ########################
  ###### INITIALIZE ######
  ########################

  def __init__(self, 
               port_pub: str = "42069",
               port_sync: str = "42071",
               port_killsig: str = "42066",
               stream_info: dict = None,
               print_status: bool = True,
               print_debug: bool = False) -> None:
    self._port_pub = port_pub
    self._port_sync = port_sync
    self._port_killsig = port_killsig
    self._print_status = print_status
    self._print_debug = print_debug
    self._running = False
    self._poller: zmq.Poller = zmq.Poller()
    # Data structure for keeping track of data
    self._stream: Stream = self.create_stream(stream_info)


  # A SensorStreamer instance is a callable to launch as a Process
  def __call__(self, *args, **kwds):
    # Connect local publisher to the Proxy's XSUB socket
    self._ctx: zmq.Context = zmq.Context.instance()

    # Socket to publish sensor data and log
    self._pub: zmq.SyncSocket = self._ctx.socket(zmq.PUB)
    self._pub.connect("tcp://localhost:%s" % self._port_pub)

    # Socket to receive kill signal
    self._killsig: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    self._killsig.connect("tcp://localhost:%s" % self._port_killsig)
    topics = ["kill"]
    for topic in topics: self._killsig.subscribe(topic)

    # Socket to indicate to broker that the publisher is ready
    self._sync: zmq.SyncSocket = self._ctx.socket(zmq.REQ)
    self._sync.connect("tcp://localhost:%s" % self._port_sync)

    # Start running!
    self._running = True
    self.connect()
    self.run()

  ############################
  ###### INTERFACE FLOW ######
  ############################

  # Instantiate Stream datastructure object specific to this Streamer.
  #   Should also be a class method to create Stream objects on consumers. 
  @classmethod
  @abstractmethod
  def create_stream(cls) -> Stream:
    pass

  # Connect to the sensor device(s).
  @abstractmethod
  def connect(self) -> bool:
    pass

  # Launch data streaming form the device.
  @abstractmethod
  def run(self) -> None:
    # TODO: boiler plate for awaiting the SYNC signal from the broker
    self._poller.register(self._killsig, zmq.POLLIN)

  # Clean up and quit.
  @abstractmethod
  def quit(self) -> None:
    self._pub.close()
    self._killsig.close()
    self._sync.close()

  #############################
  ###### GETTERS/SETTERS ######
  #############################
  
  def is_running(self):
    return self._running

  #####################################
  ###### EXTERNAL DATA RECORDING ######
  #####################################
  
  # Start recording data via the sensor's dedicated software.
  def start_external_data_recording(self, data_dir):
    pass
  
  # Stop recording data via the sensor's dedicated software.
  def stop_external_data_recording(self):
    pass

  # Whether recording via the sensor's dedicated software will require user action.
  def external_data_recording_requires_user(self):
    pass
  
  # Process externally recorded data and use it to update the main data log.
  def merge_external_data_with_streamed_data(self,
                                             # Final post-processed outputs
                                             hdf5_file_toUpdate,
                                             data_dir_toUpdate,
                                             # Original streamed and external data
                                             data_dir_streamed,
                                             data_dir_external_original,
                                             # Archives for data no longer needed
                                             data_dir_archived,
                                             hdf5_file_archived):
    pass
