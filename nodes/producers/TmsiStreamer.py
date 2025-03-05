from nodes.producers.Producer import Producer
from streams import TmsiStream

from handlers.TMSiSDK.tmsi_sdk import TMSiSDK
from handlers.TMSiSDK.device.tmsi_device_enums import DeviceInterfaceType, DeviceType, MeasurementType
from handlers.TMSiSDK.sample_data_server.sample_data_server import SampleDataServer
from handlers.TMSiSDK.tmsi_utilities.support_functions import array_to_matrix as Reshape
from handlers.TMSiSDK.device.devices.saga.saga_API_enums import SagaBaseSampleRate
from handlers.TMSiSDK.device.tmsi_channel import ChannelType

import queue
from utils.print_utils import *
from utils.zmq_utils import *


########################################
########################################
# A class to interface TMSi SAGA device.
########################################
########################################
class TmsiStreamer(Producer):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'tmsi'


  def __init__(self,
               logging_spec: dict,
               sampling_rate_hz: int = 20,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               transmit_delay_sample_period_s: float = None,
               print_status: bool = True,
               print_debug: bool = False,
               **_)-> None:
    
    stream_info = {
      "sampling_rate_hz": sampling_rate_hz
    }

    super().__init__(stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     transmit_delay_sample_period_s=transmit_delay_sample_period_s,
                     print_status=print_status, 
                     print_debug=print_debug)


  def create_stream(self, stream_info: dict) -> TmsiStream:  
    return TmsiStream(**stream_info)


  def _ping_device(self) -> None:
    return None


  def _connect(self) -> bool:
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
        # NOTE: must match the hardcoded specs else wrong sensors will be read out.
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
        
      time.sleep(3) # sleep a bit to allow system to set up corretly
      print('wifi setup starting')
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
        self.dev.start_measurement(MeasurementType.SAGA_SIGNAL)
        return True
    except Exception as e:
      print(e)
      print(log_status("SAGA",'Unsuccessful connection to the TMSi streamer.'))
      return False


  def _process_data(self) -> None:
    if len(self.data_queue.queue) != 0:
      sample_data = self.data_queue.get(0)
      reshaped = np.array(Reshape(sample_data.samples, sample_data.num_samples_per_sample_set))
      time_s = time.time()
      tag: str = "%s.data" % self._log_source_tag()
      for column in reshaped.T:
        data = {
          'BIP-01': column[0],
          'BIP-02': column[1],
          'breath': column[2],
          'GSR': column[3],
          'SPO2': column[4],
          'counter': column[-1],
        }
        self._publish(tag=tag, time_s=time_s, data={'tmsi-data': data})
    elif not self._is_continue_capture:
      self._send_end_packet()


  def _stop_new_data(self):
    self.dev.stop_measurement()


  def _cleanup(self) -> None:
    # Set the DR-DS interface type back to docked
    self.dev.set_device_interface(DeviceInterfaceType.docked)
    self.dev.close()
    super()._cleanup()
