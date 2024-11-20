import queue
from streams.TmsiStream import TmsiStream
from streamers.SensorStreamer import SensorStreamer
from utils.TMSiSDK.device.tmsi_device_enums import DeviceInterfaceType, DeviceType, MeasurementType
from utils.TMSiSDK.sample_data_server.sample_data_server import SampleDataServer
from utils.TMSiSDK.tmsi_utilities.support_functions import array_to_matrix as Reshape
from utils.TMSiSDK.tmsi_sdk import TMSiSDK
from utils.TMSiSDK.device.devices.saga.saga_API_enums import SagaBaseSampleRate
from utils.TMSiSDK.device.tmsi_channel import ChannelType

import numpy as np
import time
import traceback

from utils.print_utils import *

################################################
################################################
# A template class for implementing a new sensor.
################################################
################################################
class TmsiStreamer(SensorStreamer):
  _log_source_tag = 'SAGA'

  def __init__(self,
               port_pub: str = "42069",
               port_sync: str = "42071",
               port_killsig: str = "42066",
               sampling_rate_hz: int = 20,
               print_status: bool = True,
               print_debug: bool = False,)-> None:
    
    stream_info = {
      "sampling_rate_hz": sampling_rate_hz
    }

    super().__init__(port_pub=port_pub,
                     port_sync = port_sync,
                     port_killsig = port_killsig,
                     stream_info = stream_info,
                     print_status=print_status, 
                     print_debug=print_debug)


  def create_stream(self, stream_info: dict) -> TmsiStream:  
    return TmsiStream(**stream_info)


  def connect(self) -> bool:
    #from utils.tmsi_aux.TMSiSDK.tmsi_sdk import TMSiSDK
    #from utils.tmsi_aux.TMSiSDK.device.devices.saga import saga_API
    try:
      TMSiSDK().discover(dev_type=DeviceType.saga, 
                         dr_interface=DeviceInterfaceType.docked, 
                         ds_interface=DeviceInterfaceType.usb)
      discoveryList = TMSiSDK().get_device_list(DeviceType.saga)
      if (len(discoveryList) > 0):
        # Get the handle to the first discovered device and open the connection.
        for i,_ in enumerate(discoveryList):
          self.dev = discoveryList[i]
          if self.dev.get_dr_interface() == DeviceInterfaceType.docked:
                  # Open the connection to SAGA
            self.dev.open()
            break

        # Check the current bandwidth that's in use
        current_bandwidth = self.dev.get_device_bandwidth()
        print('The current bandwidth in use is {:} bit/s'.format(current_bandwidth['in use']))
        print('Maximum bandwidth for wifi measurements is {:} bit/s'.format(current_bandwidth['wifi']))

        # Maximal allowable sample rate with all enabled channels is 1000 Hz
        self.dev.set_device_sampling_config(base_sample_rate=SagaBaseSampleRate.Decimal,  
                                            channel_type=ChannelType.all_types, 
                                            channel_divider=4)

        # channels
        # oxy goes to digi
        # breath to aux 1
        # gsr aux 2
        # double bip to bipolar
        # 65 66 double bipolar
        # 69 breath
        # 72 gsr
        # 78 blood oxy
        # 79, 80, 81, 82, 83, 84, 85, 86 -> sensors
        enable_channels = [65, 66, 69, 72, 78, 79, 80, 81, 82, 83, 84, 85, 86]
        disable_channels = [i for i in range(90) if i not in enable_channels]
        self.dev.set_device_active_channels(enable_channels, True)
        self.dev.set_device_active_channels(disable_channels, False)  

        # Check the current bandwidth that's in use
        current_bandwidth = self.dev.get_device_bandwidth()
        print('The current bandwidth in use is {:} bit/s'.format(current_bandwidth['in use']))

        # Choose the desired DR-DS interface type 
        self.dev.set_device_interface(DeviceInterfaceType.wifi)
        
        # Close the connection to the device (with the original interface type)
        self.dev.close()
        
      print("Remove saga from the dock")
      time.sleep(3)
      # connection over wifi
      TMSiSDK().discover(dev_type = DeviceType.saga, dr_interface = DeviceInterfaceType.wifi, ds_interface = DeviceInterfaceType.usb, num_retries = 10)
      discoveryList = TMSiSDK().get_device_list(DeviceType.saga)

      if (len(discoveryList) > 0):
        # Get the handle to the first discovered device and open the connection.
        for i,_ in enumerate(discoveryList):
          self.dev = discoveryList[i]
          if self.dev.get_dr_interface() == DeviceInterfaceType.wifi:
            # Open the connection to SAGA
            self.dev.open()
            break

        self.data_sampling_server = SampleDataServer()
        self.data_queue = queue.Queue(maxsize=0)
        self.data_sampling_server.register_consumer(self.dev.get_id(), self.data_queue)

        print(log_status("SAGA",'Successfully connected to the TMSi streamer.'))
        return True
    except Exception as e:
      print(e)
    print(log_status("SAGA",'Unsuccessful connection to the TMSi streamer.'))
    return False
  

  def run(self) -> None:
    try:
      self.dev.start_measurement(MeasurementType.SAGA_SIGNAL)
      while self._running:
        if len(self.data_queue.queue) != 0:
            sample_data = self.data_queue.get(0)
            reshaped = np.array(Reshape(sample_data.samples, sample_data.num_samples_per_sample_set))
            time_s = time.time()
            for column in reshaped.T:
              self._data.append_data(time_s, column)
        
    except KeyboardInterrupt: # The program was likely terminated
      pass
    except:
      print(log_error("SAGA",'\n\n***ERROR RUNNING TemplateStreamer:\n%s\n' % traceback.format_exc()))
    finally:
      ## TODO: Disconnect from the sensor if desired.
      pass
  

  # Clean up and quit
  def quit(self) -> None:
    # Set the DR-DS interface type back to docked
    self.dev.set_device_interface(DeviceInterfaceType.docked)
    self.dev.close()
    super().quit()
