from abc import ABC, abstractmethod

import copy
from collections import OrderedDict
import zmq

from data_structures import Stream
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

  ########################
  ###### INITIALIZE ######
  ########################

  # Will store the class name of each sensor in HDF5 metadata,
  #   to facilitate recreating classes when replaying the logs later.
  # The following is the metadata key to store that information.
  metadata_class_name_key = 'SensorStreamer class name'
  # Will look for a special metadata key that labels data channels,
  #   to use for logging purposes and general user information.
  metadata_data_headings_key = 'Data headings'

  def __init__(self, port_pub: str = "42069",
               streams_info: dict[str, dict[str, dict]] | None = None,
               log_player_options = None,
               log_history_filepath: str | None = None,
               visualization_options: dict | None = None,
               print_status: bool = True, print_debug: bool = False) -> None:
    
    # Connect local publisher to the Proxy's XSUB socket
    self._ctx: zmq.Context = zmq.Context.instance()

    # Socket to publish sensor data and log
    self._pub: zmq.SyncSocket = self._ctx.socket(zmq.PUB)
    self._pub.connect("tcp://localhost:%s" % port_pub)

    # # Socket to receive kill signal and stdin events (if needed)
    # self._sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    # self._sub.connect("tcp://localhost:%s" % port_pub)
    # topics = ["kill.", "stdin."]
    # for topic in topics: self._sub.subscribe(topic)
    
    # Data structure for keeping track of data
    self._data: Stream = self.create_stream(streams_info)

    self._metadata = OrderedDict()

    self._log_source_tag = type(self).__name__
    self._print_status = print_status
    self._print_debug = print_debug
    self._log_history_filepath = log_history_filepath
    self._running = False

  # A SensorStreamer instance is a callable to launch as a Process
  def __call__(self, *args: copy.Any, **kwds: copy.Any):
    # Start running!
    self._running = True
    self._run()
  
  ############################
  ###### INTERFACE FLOW ######
  ############################

  # Instantiate Stream datastructure object specific to this Streamer
  @abstractmethod
  def create_stream(self, streams_info) -> Stream:
    pass

  # Connect to the sensor device(s)
  @abstractmethod
  def connect(self):
    pass

  # Launch data streaming form the device
  @abstractmethod
  def _run(self):
    pass

  # Clean up and quit
  @abstractmethod
  def _quit(self):
    pass

  ##############################
  ###### GETTERS/SETTERS ######
  ##############################
  
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
