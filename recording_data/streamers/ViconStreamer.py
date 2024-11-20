from collections import OrderedDict
import queue
from vicon_dssdk import ViconDataStream

import numpy as np

from streamers.SensorStreamer import SensorStreamer
from streams.AwindaStream import AwindaStream

from utils.msgpack_utils import serialize
from utils.print_utils import *

import xsensdeviceapi as xda

import zmq

################################################
################################################
# A class for streaming Awinda IMU data.
################################################
################################################
class ViconStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'awinda'

  ########################
  ###### INITIALIZE ######
  ########################

  def __init__(self, 
               port_pub: str = None,
               port_sync: str = None,
               port_killsig: str = None,
               print_status: bool = True, 
               print_debug: bool = False):

    stream_info = {
    }

    super(ViconStreamer, self).__init__(self, 
                                         port_pub=port_pub,
                                         port_sync=port_sync,
                                         port_killsig=port_killsig,
                                         stream_info=stream_info,
                                         print_status=print_status, 
                                         print_debug=print_debug)

  def create_stream(self, stream_info: dict) -> AwindaStream:  
    return AwindaStream(**stream_info)


  def connect(self) -> None:
    self._client = ViconDataStream.Client()
    print( 'Connecting' )
    while not self._client.IsConnected():
        self._client.Connect( 'localhost:801' )

    # Check setting the buffer size works
    self._client.SetBufferSize( 1 )

    #Enable all the data types
    self._client.EnableSegmentData()
    self._client.EnableMarkerData()
    self._client.EnableUnlabeledMarkerData()
    self._client.EnableMarkerRayData()
    self._client.EnableDeviceData()
    self._client.EnableCentroidData()

    # Set server push mode, server pushes frames to client buffer, TCP/IP buffer, then server buffer. Code must keep up to ensure no overflow
    self._client.SetStreamMode( ViconDataStream.Client.StreamMode.EServerPush )
    print( 'Get Frame Push', self._client.GetFrame(), self._client.GetFrameNumber() )

    self._client.getFrame()


  # Acquire data from the sensors until signalled externally to quit
  def run(self) -> None:
    # While background process reads-out new data, can do something useful
    #   like poll for commands from the Broker to terminate, and block on the Queue 
    devices = self._client.GetDeviceNames()
    while self._running:
      self._client.getFrame()
      time_s = time.time()
      frame_number = self._client.getFrameNumber()

      for deviceName, deviceType in devices:
        print( deviceName, 'Device of type', deviceType )
        deviceOutputDetails = self._client.GetDeviceOutputDetails( deviceName )
        for outputName, componentName, unit in deviceOutputDetails:
            values, occluded = self._client.GetDeviceOutputValues( deviceName, outputName, componentName )
            print( deviceName, componentName, values, unit, occluded )
            # Store the captured data into the data structure.
            self._stream.append_data(time_s=time_s, deviceName=deviceName, componentName=componentName, values=values, frame_number=frame_number)
            # Get serialized object to send over ZeroMQ.
            msg = serialize(time_s=time_s, deviceName=deviceName, componentName=componentName, values=values, frame_number=frame_number)
            # Send the data packet on the PUB socket.
            self._pub.send_multipart(["%s.data" % self._log_source_tag, msg])

    #TODO make this work while at the Vicon Lab

  # Clean up and quit
  def quit(self) -> None:
    # Clean up the SDK
    self._client.close()

    super(ViconStreamer, self).quit(self)