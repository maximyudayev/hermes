from collections import OrderedDict
import queue
from vicon_dssdk import ViconDataStream


from streamers.SensorStreamer import SensorStreamer
from streams.ViconStream import ViconStream

from utils.msgpack_utils import serialize
from utils.print_utils import *

import zmq

################################################
################################################
# A class for streaming Awinda IMU data.
################################################
################################################
class ViconStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'vicon'

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

    super(ViconStreamer, self).__init__( 
                                         port_pub=port_pub,
                                         port_sync=port_sync,
                                         port_killsig=port_killsig,
                                         stream_info=stream_info,
                                         print_status=print_status, 
                                         print_debug=print_debug)
  @classmethod
  def create_stream(self, stream_info: dict) -> ViconStream:  
    return ViconStream(**stream_info)


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
    
    time.sleep(1) # wait for the setup
    HasFrame = False
    timeout = 50
    while not HasFrame:
        print( '.' )
        try:
            if self._client.GetFrame():
                HasFrame = True
            timeout=timeout-1
            if timeout < 0:
                print('Failed to get frame')
        except ViconDataStream.DataStreamException as e:
            self._client.GetFrame()
    
    self._client.GetDeviceNames()


  # Acquire data from the sensors until signalled externally to quit
  def run(self) -> None:
    # While background process reads-out new data, can do something useful
    #   like poll for commands from the Broker to terminate, and block on the Queue 
    devices = self._client.GetDeviceNames()
    # Keep only EMG. This device was renamed in the Nexus SDK
    devices = [d for d in devices if d[0] == "Cometa EMG"]
    while self._running:
      self._client.GetFrame()
      time_s = time.time()
      frame_number = self._client.GetFrameNumber()

      for deviceName, deviceType in devices:
        # handle Cometa EMG
        if deviceName == "Cometa EMG":
          deviceOutputDetails = self._client.GetDeviceOutputDetails( deviceName )
          all_results = []
          for outputName, componentName, unit in deviceOutputDetails:
            if outputName != "EMG Channels": continue # only record EMG
            values, occluded = self._client.GetDeviceOutputValues( deviceName, outputName, componentName )
            all_results.append(values)
            # Store the captured data into the data structure.
          result_array = np.array(all_results)
          for sample in result_array.T:
            self._stream.append_data_EMG(time_s, sample)
            msg = serialize(time_s=time_s, mocap = None, EMG=sample, frame_number=frame_number)
          # Send the data packet on the PUB socket.
            self._pub.send_multipart([("%s.data" % self._log_source_tag).encode('utf-8'), msg])
          

  # Clean up and quit
  def quit(self) -> None:
    # Clean up the SDK
    self._client.close()

    super(ViconStreamer, self).quit(self)