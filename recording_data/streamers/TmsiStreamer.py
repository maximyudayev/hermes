import queue
from streams.TmsiStream import TmsiStream
from streamers.SensorStreamer import SensorStreamer
from utils.TMSiSDK.device.tmsi_device_enums import DeviceInterfaceType, DeviceType, MeasurementType
from utils.TMSiSDK.sample_data_server.sample_data_server import SampleDataServer
from visualizers import LinePlotVisualizer
from visualizers.HeatmapVisualizer import HeatmapVisualizer
from utils.TMSiSDK.tmsi_utilities.support_functions import array_to_matrix as Reshape
from utils.TMSiSDK.tmsi_sdk import TMSiSDK
from utils.TMSiSDK.device.devices.saga.saga_API_enums import SagaBaseSampleRate
from utils.TMSiSDK.device.tmsi_channel import ChannelType

import numpy as np
import time
from collections import OrderedDict
import traceback

from utils.print_utils import *

################################################
################################################
# A template class for implementing a new sensor.
################################################
################################################
class TmsiStreamer(SensorStreamer):
  
  ########################
  ###### INITIALIZE ######
  ########################
  
  # Initialize the sensor streamer.
  # @param visualization_options Can be used to specify how data should be visualized.
  #   It should be a dictionary with the following keys:
  #     'visualize_streaming_data': Whether or not visualize any data during streaming.
  #     'update_period_s': How frequently to update the visualizations during streaming.
  #     'visualize_all_data_when_stopped': Whether to visualize a summary of data at the end of the experiment.
  #     'wait_while_visualization_windows_open': After the experiment finishes, whether to automatically close visualization windows or wait for the user to close them.
  #     'classes_to_visualize': [optional] A list of class names that should be visualized (others will be suppressed).  For example, ['TouchStreamer', 'MyoStreamer']
  #     'use_composite_video': Whether to combine visualizations from multiple streamers into a single tiled visualization.  If not, each streamer will create its own window.
  #     'composite_video_filepath': If using composite video, can specify a filepath to save it as a video.
  #     'composite_video_layout': If using composite video, can specify which streamers should be included and how to arrange them. See some of the launch files for examples.
  # @param log_player_options Can be used to replay data from an existing log instead of streaming real-time data.
  #   It should be a dictionary with the following keys:
  #     'log_dir': The directory with log data to replay (should directly contain the HDF5 file).
  #     'pause_to_replay_in_realtime': If reading from the logs is faster than real-time, can wait between reads to keep the replay in real time.
  #     'skip_timesteps_to_replay_in_realtime': If reading from the logs is slower than real-time, can skip timesteps as needed to remain in real time.
  #     'load_datasets_into_memory': Whether to load all data into memory before starting the replay, or whether to read from the HDF5 file each timestep.
  # @param print_status Whether or not to print messages with level 'status'
  # @param print_debug Whether or not to print messages with level 'debug'
  # @param log_history_filepath A filepath to save log messages if desired.
  def __init__(self,
               port_pub: str = "42069",
               port_sync: str = "42071",
               port_killsig: str = "42066",
               stream_info: dict = {},
               log_history_filepath: str | None = None,
               print_status: bool = True,
               print_debug: bool = False,)-> None:
    
    SensorStreamer.__init__(self, 
                            port_pub=port_pub,
                            port_sync = port_sync,
                            port_killsig = port_killsig,
                            stream_info = stream_info,
                            print_status=print_status, 
                            print_debug=print_debug,
                            log_history_filepath=log_history_filepath)
    
    self._log_source_tag = 'SAGA'
    self._device_name = 'TMSi_SAGA'
    self._data = self.create_stream(stream_info)
    """self.add_stream(device_name=self._device_name,
                    stream_name='breath',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")
    
    self.add_stream(device_name=self._device_name,
                    stream_name='GSR',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")
    
    self.add_stream(device_name=self._device_name,
                    stream_name='SPO2',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")
    
    self.add_stream(device_name=self._device_name,
                    stream_name='BIP-01',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")
    
    self.add_stream(device_name=self._device_name,
                    stream_name='BIP-02',
                    data_type='float32',
                    sample_size=[1],
                    sampling_rate_hz=20,
                    extra_data_info={},
                    data_notes="")"""
    

  #######################################
  def create_stream(self, stream_info: dict = {}) -> TmsiStream:  
    return TmsiStream(**stream_info)
  
  def _log_source_tag(self):
    pass

  # Connect to the sensor.
  # @param timeout_s How long to wait for the sensor to respond.
  def connect(self, timeout_s=10):
    #from utils.tmsi_aux.TMSiSDK.tmsi_sdk import TMSiSDK
    #from utils.tmsi_aux.TMSiSDK.device.devices.saga import saga_API
    try:
      TMSiSDK().discover(dev_type = DeviceType.saga, dr_interface = DeviceInterfaceType.docked, ds_interface = DeviceInterfaceType.usb)
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
        self.dev.set_device_sampling_config(base_sample_rate = SagaBaseSampleRate.Decimal,  channel_type = ChannelType.all_types, channel_divider = 4)

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
  
  #####################
  ###### RUNNING ######
  #####################
  
  ## TODO: Continuously read data from your sensor.
  # Loop until self._running is False.
  # Acquire data from your sensor as desired, and for each timestep
  #  call self.append_data(device_name, stream_name, time_s, data).
  def run(self):
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
  def quit(self):
    ## TODO: Add any desired clean-up code.
    self._log_debug(f'{self._device_name}-streamer quitting')
    # Set the DR-DS interface type back to docked
    self.dev.set_device_interface(DeviceInterfaceType.docked)
    self.dev.close()
    SensorStreamer.quit(self)

  ###########################
  ###### VISUALIZATION ######
  ###########################

  # Specify how the streams should be visualized.
  # Return a dict of the form options[device_name][stream_name] = stream_options
  #  Where stream_options is a dict with the following keys:
  #   'class': A subclass of Visualizer that should be used for the specified stream.
  #   Any other options that can be passed to the chosen class.
  def get_default_visualization_options(self, visualization_options=None):
    # Start by not visualizing any streams.
    processed_options = {}
    for (device_name, device_info) in self._streams_info.items():
      processed_options.setdefault(device_name, {})
      for (stream_name, stream_info) in device_info.items():
        processed_options[device_name].setdefault(stream_name, {'class': None})
    
    ## TODO: Specify whether some streams should be visualized.
    #        Examples of a line plot and a heatmap are below.
    #        To not visualize data, simply omit the following code and just leave each streamer mapped to the None class as shown above.
    # Use a line plot to visualize the weight.
    processed_options[self._device_name]['stream_1'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    processed_options[self._device_name]['stream_2'] = \
      {'class': HeatmapVisualizer,
       'colorbar_levels': 'auto', # The range of the colorbar.
                                  # Can be a 2-element list [min, max] to use hard-coded bounds,
                                  # or 'auto' to determine them dynamically based on a buffer of the data.
      }
  
    # Override the above defaults with any provided options.
    if isinstance(visualization_options, dict):
      for (device_name, device_info) in self._streams_info.items():
        if device_name in visualization_options:
          device_options = visualization_options[device_name]
          # Apply the provided options for this device to all of its streams.
          for (stream_name, stream_info) in device_info.items():
            for (k, v) in device_options.items():
              processed_options[device_name][stream_name][k] = v
  
    return processed_options


#####################
###### TESTING ######
#####################
if __name__ == '__main__':
  # Configuration.
  duration_s = 30
  
  # Connect to the device(s).
  template_streamer = TmsiStreamer(print_status=True, print_debug=False)
  template_streamer.connect()
  
  # Run for the specified duration and periodically print the sample rate.
  print('\nRunning for %gs!' % duration_s)
  template_streamer.run()
  start_time_s = time.time()
  try:
    while time.time() - start_time_s < duration_s:
      time.sleep(2)
      # Print the sampling rates.
      msg = ' Duration: %6.2fs' % (time.time() - start_time_s)
      for device_name in template_streamer.get_device_names():
        stream_names = template_streamer.get_stream_names(device_name=device_name)
        for stream_name in stream_names:
          num_timesteps = template_streamer.get_num_timesteps(device_name, stream_name)
          msg += ' | %s-%s: %6.2f Hz (%4d Timesteps)' % \
                 (device_name, stream_name, ((num_timesteps)/(time.time() - start_time_s)), num_timesteps)
      print(msg)
  except:
    pass
  
  # Stop the streamer.
  template_streamer.stop()
  print('\n'*2)
  print('='*75)
  print('Done!')
  print('\n'*2)

