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

from sensor_streamers import SensorStreamer
from visualizers import LinePlotVisualizer
from visualizers import XsensSkeletonVisualizer

import numpy as np
import time
from collections import OrderedDict
import traceback

from utils.print_utils import *
from sensor_streamer_handlers.xdpchandler import *

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
    
    ## Add a tag here for your sensor that can be used in log messages.
    #        Try to keep it under 10 characters long.
    #        For example, 'myo' or 'scale'.
    self._log_source_tag = 'dots'

    # Run in the main process for now because accessing stdin from child process causes crashes at first input() call
    self._always_run_in_main_process = True
    
    ## Initialize any state that your sensor needs.
    self._output_rate = 20
    self._device_name = 'dots-imu'
    self._num_joints = 5
    self._packet = OrderedDict()
    self._data_notes_stream = {
      "dots-imu": {
        "acceleration-x": "AccX",
        "acceleration-y": "AccY",
        "acceleration-z": "AccZ",
        "gyroscope-x": "GyrX",
        "gyroscope-y": "GyrY",
        "gyroscope-z": "GyrZ",
      },
      "dots-time": {
        "device_timestamp_s": None
      }
    }

  #######################################
  # Connect to the sensor.
  # @param timeout_s How long to wait for the sensor to respond.
  def _connect(self, timeout_s=10):
    xqp_joints = [0,1,2,3,4] # remove lines with xqp_ variables 
    def map_dot_to_joint(devices, device):
      msg = format_log_message("Which joint is this DOT attached to? (New DOT lights up green) : ", source_tag=self._log_source_tag, userAction=True, print_message=False)
      while True:
        try:
          joint_of_device = str(xqp_joints.pop(0)) #input(msg)
          if int(joint_of_device) < 0 or str(int(joint_of_device)) in devices: raise KeyError
          else: 
            devices[joint_of_device] = device
            self._log_debug("DOT @%s associated with joint %s."% (device.bluetoothAddress(), joint_of_device))
            return devices
        except ValueError:
          self._log_error("Joint specifier must be a unique positive integer.")
        except KeyError:
          self._log_error("This joint specifier already used by %s" % devices[joint_of_device].bluetoothAddress())

    def set_master_joint(devices):
      msg = format_log_message("Which joint is center of skeleton? : ", source_tag=self._log_source_tag, userAction=True, print_message=False)
      while True:
        try:
          master_joint = int(input(msg))
          if master_joint < 0 or str(master_joint) not in devices: raise KeyError
          else: 
            self._log_debug("Joint %s set as master. (DOT @%s)."% (master_joint, devices[str(master_joint)].bluetoothAddress()))
            self.xdpcHandler.setMasterDot(str(master_joint))
            self._packet = OrderedDict([(v.bluetoothAddress(), None) for k, v in devices.items()])
        except ValueError:
          self._log_error("Joint specifier must be a positive integer.")
        except KeyError:
          self._log_error("This joint specifier does not exist in the device list.")
        else: break

    ## Connecting to your sensor.
    #        Then return True or False to indicate whether connection was successful.
    self.xdpcHandler = XdpcHandler(log_debug=self._log_debug, log_error=self._log_error, log_status=self._log_status)

    # DOTs backend is annoying and doesn't always connect/discover devices from first try, loop until success
    while True:
      if not self.xdpcHandler.initialize():
        self.xdpcHandler.cleanup()
        continue
      else: break

    while True:
      self.xdpcHandler.scanForDots(timeout_s)
      if len(self.xdpcHandler.detectedDots()) == 0:
        self._log_error("No Movella DOT device(s) found. Aborting.")
      elif len(self.xdpcHandler.detectedDots()) < self._num_joints:
        self._log_error("Not all %s requested Movella DOT device(s) found. Aborting." % self._num_joints)
      else:
        self._log_debug("All %s requested Movella DOT device(s) found." % self._num_joints)
        break

    while True:
      self.xdpcHandler.connectDots(onDotConnected=map_dot_to_joint, onConnected=set_master_joint, connectAttempts=10)
      if len(self.xdpcHandler.connectedDots()) == 0:
        self._log_error("Could not connect to any Movella DOT device(s). Aborting.")
      elif len(self.xdpcHandler.connectedDots()) < self._num_joints:
        self._log_error("Not all requested Movella DOT devices connected %s/%s. Aborting." % (len(self.xdpcHandler.connectedDots()), self._num_joints))
      else:
        self._log_debug("All %s detected Movella DOT device(s) connected." % self._num_joints)
        break

    for joint, device in self.xdpcHandler.connectedDots().items():
      # Make sure all connected devices have the same filter profile and output rate
      if device.setOnboardFilterProfile("General"):
        self._log_debug("Successfully set profile to General for joint %s." % joint)
      else:
        self._log_error("Setting filter profile for joint %s failed!" % joint)
        return False

      if device.setOutputRate(self._output_rate):
        self._log_debug(f"Successfully set output rate for joint {joint} to {self._output_rate} Hz.")
      else:
        self._log_error("Setting output rate for joint %s failed!" % joint)
        return False

    self._manager = self.xdpcHandler.manager()
    self._devices = self.xdpcHandler.connectedDots()

    # Call facade sync function, not directly the backend manager proxy
    while not self.xdpcHandler.sync():
      self._log_error("Synchronization of dots failed! Retrying.")
    
    self._log_debug(f"Successfully synchronized {len(self._devices)} dots.")
    self._log_status('Successfully connected to the dots streamer.')

    ## Add devices and streams to organize data from your sensor.
    #        Data is organized as devices and then streams.
    #        For example, a DOTs device may have streams for Gyro and Acceleration.
    #        If desired, this could also be done in the connect() method instead.
    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration-x',
                    data_type='float32',
                    sample_size=(self._num_joints),     # the size of data saved for each timestep
                    sampling_rate_hz=None, # the expected sampling rate for the stream
                    extra_data_info=None,
                    data_notes=self._data_notes_stream['dots-imu']['acceleration-x'])
    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration-y',
                    data_type='float32',
                    sample_size=(self._num_joints),     # the size of data saved for each timestep
                    sampling_rate_hz=None, # the expected sampling rate for the stream
                    extra_data_info=None,
                    data_notes=self._data_notes_stream['dots-imu']['acceleration-y'])
    self.add_stream(device_name=self._device_name,
                    stream_name='acceleration-z',
                    data_type='float32',
                    sample_size=(self._num_joints),     # the size of data saved for each timestep
                    sampling_rate_hz=None, # the expected sampling rate for the stream
                    extra_data_info=None,
                    data_notes=self._data_notes_stream['dots-imu']['acceleration-z'])
    self.add_stream(device_name=self._device_name,
                    stream_name='gyroscope-x',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=None,
                    extra_data_info=None, 
                    data_notes=self._data_notes_stream['dots-imu']['gyroscope-x'])
    self.add_stream(device_name=self._device_name,
                    stream_name='gyroscope-y',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=None,
                    extra_data_info=None, 
                    data_notes=self._data_notes_stream['dots-imu']['gyroscope-y'])
    self.add_stream(device_name=self._device_name,
                    stream_name='gyroscope-z',
                    data_type='float32',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=None,
                    extra_data_info=None, 
                    data_notes=self._data_notes_stream['dots-imu']['gyroscope-z'])
    self.add_stream(device_name=self._device_name,
                    stream_name='timestamp',
                    data_type='int64',
                    sample_size=(self._num_joints),
                    sampling_rate_hz=None,
                    extra_data_info=None,
                    data_notes=self._data_notes_stream['dots-time']['device_timestamp_s'])
    # Set dots to streaming mode
    return self.xdpcHandler.stream()
  
  #####################
  ###### RUNNING ######
  #####################
  
  # Loop until self._running is False.
  # Acquire data from your sensor as desired, and for each timestep.
  def _run(self):
    try:
      while self._running:
        if self.xdpcHandler.packetsAvailable():
          time_s = time.time()
          for joint, device in self.xdpcHandler.connectedDots().items():
            # Retrieve a packet
            packet = self.xdpcHandler.getNextPacket(device.portInfo().bluetoothAddress())
            euler = packet.orientationEuler()
            acc = packet.freeAcceleration()
            self._packet[device.bluetoothAddress()] = {
              'timestamp': packet.sampleTimeFine(),
              'acceleration': (acc[0], acc[1], acc[2]),
              'gyroscope': (euler.x(), euler.y(), euler.z()),
            }
          
          acceleration = np.array([v['acceleration'] for (_,v) in self._packet.items()])
          gyroscope = np.array([v['gyroscope'] for (_,v) in self._packet.items()])
          timestamp = np.array([v['timestamp'] for (_,v) in self._packet.items()])

          # Read and store data for streams
          self.append_data(self._device_name, 'acceleration-x', time_s, acceleration[:,0])
          self.append_data(self._device_name, 'acceleration-y', time_s, acceleration[:,1])
          self.append_data(self._device_name, 'acceleration-z', time_s, acceleration[:,2])
          self.append_data(self._device_name, 'gyroscope-x', time_s, gyroscope[:,0])
          self.append_data(self._device_name, 'gyroscope-y', time_s, gyroscope[:,1])
          self.append_data(self._device_name, 'gyroscope-z', time_s, gyroscope[:,2])
          self.append_data(self._device_name, 'timestamp', time_s, timestamp)

    except KeyboardInterrupt: # The program was likely terminated
      pass
    except:
      self._log_error('\n\n***ERROR RUNNING DotsStreamer:\n%s\n' % traceback.format_exc())
    finally:
      ## TODO: Disconnect from the sensor if desired.
      pass
  
  # Clean up and quit
  def quit(self):
    self._log_debug("Stopping DOTs measurement.")
    for device in self.xdpcHandler.connectedDots():
      if not device.stopMeasurement():
        self._log_error("Failed to stop DOT %s measurement." % device.bluetoothAddress())

    self._log_debug("Stopping DOTs sync.")
    if not self._manager.stopSync():
      self._log_error("Failed to stop DOTs sync.")

    self._log_debug("Closing DOTs ports.")
    self._manager.close()

    self._log_debug("DotsStreamer quitting.")
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
    # Visualize the segments position stream by drawing a skeleton.
    processed_options = {}
    
    # TODO: to visualize DOTs data as skeleton, must first process the streams of accelerometer data into positions
    processed_options[self._device_name] = {}
    # options['dots-imu']['position_cm'] = {
    #   'class': XsensSkeletonVisualizer,
    # }

    # Use a line plot to visualize the acceleration.
    processed_options[self._device_name]['acceleration-x'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    processed_options[self._device_name]['acceleration-y'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    processed_options[self._device_name]['acceleration-z'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    processed_options[self._device_name]['gyroscope-x'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    processed_options[self._device_name]['gyroscope-y'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    processed_options[self._device_name]['gyroscope-z'] = \
      {'class': LinePlotVisualizer,
       'single_graph': True,   # Whether to show each dimension on a subplot or all on the same plot.
       'plot_duration_s': 15,  # The timespan of the x axis (will scroll as more data is acquired).
       'downsample_factor': 1, # Can optionally downsample data before visualizing to improve performance.
      }
    
    # Don't visualize the other devices/streams.
    for (device_name, device_info) in self._streams_info.items():
      processed_options.setdefault(device_name, {})
      for (stream_name, stream_info) in device_info.items():
        processed_options[device_name].setdefault(stream_name, {'class': None})

    return processed_options


#####################
###### TESTING ######
#####################
if __name__ == '__main__':
  # Configuration.
  duration_s = 30
  print('\nStarting debugging')
  # Connect to the device(s).
  dots_streamer = DotsStreamer(print_status=True, print_debug=True)
  connection_result = dots_streamer.connect(20)

  if not connection_result:
    dots_streamer.stop()
    exit()

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
