############
#
# Copyright (c) 2022 MIT CSAIL and Joseph DelPreto
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
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# See https://action-net.csail.mit.edu for more usage information.
# Created 2021-2022 for the MIT ActionNet project by Joseph DelPreto [https://josephdelpreto.com].
#
############

from sensor_streamers.SensorStreamer import SensorStreamer
from visualizers.LinePlotVisualizer import LinePlotVisualizer
from visualizers.HeatmapVisualizer import HeatmapVisualizer

import numpy as np
import time
from collections import OrderedDict
import traceback

from utils.print_utils import *
from recording_data.sensor_streamer_handlers.xdpchandler import *

################################################
################################################
# A class for streaming Dots IMU data.
################################################
################################################
class DotsStreamer(SensorStreamer):
  
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
               log_player_options=None, visualization_options=None,
               print_status=True, print_debug=False, log_history_filepath=None):
    SensorStreamer.__init__(self, streams_info=None,
                            visualization_options=visualization_options,
                            log_player_options=log_player_options,
                            print_status=print_status, print_debug=print_debug,
                            log_history_filepath=log_history_filepath)
    
    ## TODO: Add a tag here for your sensor that can be used in log messages.
    #        Try to keep it under 10 characters long.
    #        For example, 'myo' or 'scale'.
    self._log_source_tag = 'dots'
    
    ## TODO: Initialize any state that your sensor needs.
    self._output_rate = 20
    self._device_name = 'dots-imu'
    self._packet = dict()
    
    ## TODO: Add devices and streams to organize data from your sensor.
    #        Data is organized as devices and then streams.
    #        For example, a Myo device may have streams for EMG and Acceleration.
    #        If desired, this could also be done in the connect() method instead.
    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration',
                    data_type='float32',
                    sample_size=(self._num_joints, 3),     # the size of data saved for each timestep
                    sampling_rate_hz=None, # the expected sampling rate for the stream
                    extra_data_info=extra_data_info, 
                    # Notes can add metadata about the stream,
                    #  such as an overall description, data units, how to interpret the data, etc.
                    # The SensorStreamer.metadata_data_headings_key is special, and is used to
                    #  describe the headings for each entry in a timestep's data.
                    #  For example - if the data was saved in a spreadsheet with a row per timestep, what should the column headings be.
                    data_notes=self._data_notes_stream['dots-imu']['acceleration'])
    self.add_stream(device_name=self._device_name,
                    stream_name='gyroscope',
                    data_type='float32',
                    sample_size=(self._num_joints, 3),
                    sampling_rate_hz=None,
                    extra_data_info=extra_data_info, 
                    data_notes=self._data_notes_stream['dots-imu']['gyroscope'])
    # Time codes sent from the Xsens device
    if message_type == self._xsens_msg_types['time_code_str']:
      extra_data_info_time = extra_data_info.copy()
      extra_data_info_time['device_time_utc_str']  = {'data_type': 'S12', 'sample_size': [1]}
      extra_data_info_time['device_timestamp_str'] = {'data_type': 'S26', 'sample_size': [1]}
      self.add_stream(device_name=self._device_name,
                      stream_name='timestamp',
                      data_type='float64',
                      sample_size=(1),
                      sampling_rate_hz=None,
                      extra_data_info=extra_data_info_time,
                      data_notes=self._data_notes_stream['xsens-time']['device_timestamp_s'])

  #######################################
  # Connect to the sensor.
  # @param timeout_s How long to wait for the sensor to respond.
  def _connect(self, timeout_s=10):
    ## TODO: Add code for connecting to your sensor.
    #        Then return True or False to indicate whether connection was successful.
    self.xdpcHandler = XdpcHandler()
    if not self.xdpcHandler.initialize():
      self.xdpcHandler.cleanup()
      return False

    self.xdpcHandler.scanForDots(timeout_s)
    if len(self.xdpcHandler.detectedDots()) == 0:
      print("No Movella DOT device(s) found. Aborting.")
      self.xdpcHandler.cleanup()
      return False

    self.xdpcHandler.connectDots()

    if len(self.xdpcHandler.connectedDots()) == 0:
      print("Could not connect to any Movella DOT device(s). Aborting.")
      self.xdpcHandler.cleanup()
      return False

    for device in self.xdpcHandler.connectedDots():
      # Make sure all connected devices have the same filter profile and output rate
      if device.setOnboardFilterProfile("General"):
          print("Successfully set profile to General")
      else:
          print("Setting filter profile failed!")
          return False

      if device.setOutputRate(self._output_rate):
          print(f"Successfully set output rate to {self._output_rate} Hz")
      else:
          print("Setting output rate failed!")
          return False
      
      self._packet[device.bluetoothAddress()] = None

    self._manager = self.xdpcHandler.manager()
    self._devices = self.xdpcHandler.connectedDots()

    if self.xdpcHandler.sync():
      print(f"Successfully synchronized {len(self._devices)} dots.")
    else:
      print("Synchronization of dots failed!")
      return False

    self._log_status('Successfully connected to the dots streamer.')

    return True
  
  #####################
  ###### RUNNING ######
  #####################
  
  ## TODO: Continuously read data from your sensor.
  # Loop until self._running is False.
  # Acquire data from your sensor as desired, and for each timestep
  #  call self.append_data(device_name, stream_name, time_s, data).
  def _run(self):
    try:
      # Set dots to streaming mode
      self._manager.stream()
      while self._running:
        if self.xdpcHandler.packetsAvailable():
          time_s = datetime.now()
          for device in self.xdpcHandler.connectedDots():
            # Retrieve a packet
            packet = self.xdpcHandler.getNextPacket(device.portInfo().bluetoothAddress())
            if packet.containsOrientation():
              euler = packet.orientationEuler()
              self._packet[device.bluetoothAddress()] = {
                'timestamp': packet.sampleTimeFine(),
                'acceleration': (euler.x(), euler.y(), euler.z()),
                'gyroscope': (euler.pitch(), euler.yaw(), euler.roll())
              }

          # Read and store data for streams
          self.append_data(self._device_name, 'acceleration', time_s, np.array([v['acceleration'] for (_,v) in self._packet.items()]))
          self.append_data(self._device_name, 'gyroscope', time_s, np.array([v['gyroscope'] for (_,v) in self._packet.items()]))
          self.append_data(self._device_name, 'timestamp', time_s, np.array([v['timestamp'] for (_,v) in self._packet.items()]))
        
    except KeyboardInterrupt: # The program was likely terminated
      pass
    except:
      self._log_error('\n\n***ERROR RUNNING DotsStreamer:\n%s\n' % traceback.format_exc())
    finally:
      ## TODO: Disconnect from the sensor if desired.
      pass
  
  # Clean up and quit
  def quit(self):
    ## TODO: Add any desired clean-up code.
    print("\n-----------------------------------------", end="", flush=True)

    print("\nStopping measurement...")
    for device in self.xdpcHandler.connectedDots():
        if not device.stopMeasurement():
            print("Failed to stop measurement.")

    print("Stopping sync...")
    if not self._manager.stopSync():
        print("Failed to stop sync.")

    print("Closing ports...")
    self._manager.close()

    print("Successful exit.")

    self._log_debug('DotsStreamer quitting')
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
    # processed_options[self._device_name]['acceleration'] = \
    #   {'class': LinePlotVisualizer,
    #    'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
    #    'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
    #    'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
    #   }
    # processed_options[self._device_name]['gyroscope'] = \
    #   {'class': HeatmapVisualizer,
    #    'colorbar_levels': 'auto', # The range of the colorbar.
    #                               # Can be a 2-element list [min, max] to use hard-coded bounds,
    #                               # or 'auto' to determine them dynamically based on a buffer of the data.
    #   }
  
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
  dots_streamer = DotsStreamer(print_status=True, print_debug=False)
  dots_streamer.connect()
  
  # Run for the specified duration and periodically print the sample rate.
  print('\nRunning for %gs!' % duration_s)
  dots_streamer.run()
  start_time_s = time.time()
  try:
    while time.time() - start_time_s < duration_s:
      time.sleep(2)
      # Print the sampling rates.
      msg = ' Duration: %6.2fs' % (time.time() - start_time_s)
      for device_name in dots_streamer.get_device_names():
        stream_names = dots_streamer.get_stream_names(device_name=device_name)
        for stream_name in stream_names:
          num_timesteps = dots_streamer.get_num_timesteps(device_name, stream_name)
          msg += ' | %s-%s: %6.2f Hz (%4d Timesteps)' % \
                 (device_name, stream_name, ((num_timesteps)/(time.time() - start_time_s)), num_timesteps)
      print(msg)
  except:
    pass
  
  # Stop the streamer.
  dots_streamer.stop()
  print('\n'*2)
  print('='*75)
  print('Done!')
  print('\n'*2)
