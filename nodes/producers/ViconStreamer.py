############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Created 2024-2025 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Maxim Yudayev [https://yudayev.com].
#
# ############

from nodes.producers.Producer import Producer
from streams import ViconStream
from vicon_dssdk import ViconDataStream
from utils.print_utils import *
from utils.zmq_utils import *


###############################################
###############################################
# A class for streaming data from Vicon system.
###############################################
###############################################
class ViconStreamer(Producer):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'vicon'


  def __init__(self,
               host_ip: str,
               logging_spec: dict,
               device_mapping: dict[str, str],
               sampling_rate_hz: int = 2000,
               vicon_ip: str = DNS_LOCALHOST,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC_HOST,
               port_killsig: str = PORT_KILL,
               print_status: bool = True, 
               print_debug: bool = False,
               **_):
    self._vicon_ip = vicon_ip

    stream_info = {
      "sampling_rate_hz": sampling_rate_hz,
      "device_mapping": device_mapping
    }

    super().__init__(host_ip=host_ip,
                     stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     print_status=print_status,
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict) -> ViconStream:  
    return ViconStream(**stream_info)


  def _ping_device(self) -> None:
    return None


  def _connect(self) -> bool:
    self._client = ViconDataStream.Client()
    print('Connecting Vicon')
    while not self._client.IsConnected():
      self._client.Connect('%s:%s'%(self._vicon_ip, PORT_VICON))

    # Check setting the buffer size works
    self._client.SetBufferSize(1)

    # Enable all the data types
    # self._client.EnableSegmentData()
    # self._client.EnableMarkerData()
    # self._client.EnableUnlabeledMarkerData()
    # self._client.EnableMarkerRayData()
    self._client.EnableDeviceData()
    # self._client.EnableCentroidData()

    # Set server push mode,
    #  server pushes frames to client buffer, TCP/IP buffer, then server buffer.
    # Code must keep up to ensure no overflow.
    self._client.SetStreamMode(ViconDataStream.Client.StreamMode.EServerPush)
    print('Get Frame Push', self._client.GetFrame(), self._client.GetFrameNumber())
    
    time.sleep(1) # wait for the setup
    is_has_frame = False
    timeout = 50
    while not is_has_frame:
      print('.')
      try:
        if self._client.GetFrame():
          is_has_frame = True
        timeout -= 1
        if timeout < 0:
          print('Failed to get frame')
          return False
      except ViconDataStream.DataStreamException as e:
        pass
    
    devices = self._client.GetDeviceNames()
    # Keep only EMG. This device was renamed in the Nexus SDK
    self._devices = [d for d in devices if d[0] == "Cometa EMG"]
    return True


  # Acquire data from the sensors until signalled externally to quit
  def _process_data(self) -> None:
    if self._is_continue_capture:
      time_s = time.time()
      frame_number = self._client.GetFrameNumber()

      for device_name, device_type in self._devices:
        device_output_details = self._client.GetDeviceOutputDetails(device_name)
        all_results = []
        for output_name, component_name, unit in device_output_details:
          # NOTE: must set this ID in the Vicon software first.
          values, occluded = self._client.GetDeviceOutputValues(device_name, output_name, component_name)
          all_results.append(values)
          # Store the captured data into the data structure.
        result_array = np.array(all_results)

        for sample in result_array.T:
          tag: str = "%s.data" % self._log_source_tag()
          data = {
            'emg': sample,
            'counter': frame_number,
            'latency': 0.0,
          }
          self._publish(tag=tag, time_s=time_s, data={'vicon-data': data})
    elif not self._is_continue_capture:
      # If triggered to stop and no more available data, send empty 'END' packet and join.
      self._send_end_packet()


  def _stop_new_data(self):
    # Disable all the data types
    self._client.DisableSegmentData()
    self._client.DisableMarkerData()
    self._client.DisableUnlabeledMarkerData()
    self._client.DisableMarkerRayData()
    self._client.DisableDeviceData()
    self._client.DisableCentroidData()


  def _cleanup(self) -> None:
    # Clean up the SDK
    self._client.Disconnect()
    super()._cleanup()
