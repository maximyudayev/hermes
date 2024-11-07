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

from multiprocessing import Process
import multiprocessing
import sys

from streams.AwindaIMUStream import AwindaIMUStream
from streamers.SensorStreamer import SensorStreamer
from visualizers.LinePlotVisualizer import LinePlotVisualizer

from collections import OrderedDict
import traceback

from utils.print_utils import *

import utils.AwindaSDK.AwindaHelper as AwH
import xsensdeviceapi as xda

def sampling_function(mtw_callbacks, _data):
  try:
    start = time.time()
    while time.time() - start < 60 * 60 * 3:
        for item, (callback) in enumerate(mtw_callbacks):
            packet = callback.getOldestPacket()
            time_s = time.time()
            name = callback.m_device.deviceId().toInt()
            packet = callback.getOldestPacket() 
            _data.append_data(name, time_s, packet)
            if packet.counter % 100 == 0:
                print(f"{item} | {time.perf_counter()}")
  except KeyboardInterrupt: # The program was likely terminated
    pass
  finally:
    print("Finally reached")


################################################
################################################
# A class for streaming Dots IMU data.
################################################
################################################
class AwindaIMUStreamer(SensorStreamer):
  
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
               print_debug: bool = False,):
    SensorStreamer.__init__(self, 
                            port_pub=port_pub,
                            port_sync = port_sync,
                            port_killsig = port_killsig,
                            stream_info = stream_info,
                            print_status=print_status, 
                            print_debug=print_debug,
                            log_history_filepath=log_history_filepath)

    #self._log_source_tag = 'AW (IMU)'

    self.device_id_to_name = OrderedDict([(11850724, "Pelv"),
                                          (11850711, "ULegR"),
                                          (11850722, "LLegR"),
                                          (11850717, "FootR"),
                                          (11850727, "ULegL"),
                                          (11850708, "LLegL"),
                                          (11850712, "FootL")])
    
    self.device_ids = list(self.device_id_to_name.keys())

    ## Initialize any state that your sensor needs.
    self.desired_update_rate = 100
    self.desired_radio_channel = 15

    self._device_name = 'awinda-imu'
    self._num_joints = 7
    self._packet = OrderedDict()
    self._data = self.create_stream(stream_info)
    self._data_notes_stream = {
      "awinda-imu": {
        "acceleration-x": "AccX",
        "acceleration-y": "AccY",
        "acceleration-z": "AccZ",
        "gyroscope-x": "GyrX",
        "gyroscope-y": "GyrY",
        "gyroscope-z": "GyrZ",
      },
      "awinda-counter": {
        "counter": None
      }
    }

  def create_stream(self, stream_info: dict = {}) -> AwindaIMUStream:  
    return AwindaIMUStream(**stream_info, device_name_list = self.device_ids)
  
  def _log_source_tag(self):
    pass

  #######################################
  # Connect to the sensor.
  # @param timeout_s How long to wait for the sensor to respond.

  def connect(self, timeout=10):
    control = xda.XsControl.construct()
    if control is None:
        print("Failed to construct XsControl instance.")
        sys.exit(1)

    print("Scanning ports...")

    wireless_master_callback = AwH.WirelessMasterCallback()

    detected_devices = xda.XsScanner_scanPorts()

    print("Finding wireless master...")
    wireless_master_port = next((port for port in detected_devices if port.deviceId().isWirelessMaster()), None)
    if wireless_master_port is None:
        raise RuntimeError("No wireless masters found")

    print(f"Wireless master found @ {wireless_master_port}")

    print("Opening port...")
    if not control.openPort(wireless_master_port.portName(), wireless_master_port.baudrate()):
        raise RuntimeError(f"Failed to open port {wireless_master_port}")

    print("Getting XsDevice instance for wireless master...")
    self.wireless_master_device = control.device(wireless_master_port.deviceId())
    if self.wireless_master_device is None:
        raise RuntimeError(f"Failed to construct XsDevice instance: {wireless_master_port}")

    print(f"XsDevice instance created @ {self.wireless_master_device}")

    print("Setting config mode...")
    if not self.wireless_master_device.gotoConfig():
        raise RuntimeError(f"Failed to goto config mode: {self.wireless_master_device}")

    print("Disabling radio channel if previously enabled...")

    if self.wireless_master_device.isRadioEnabled():
        if not self.wireless_master_device.disableRadio():
            raise RuntimeError(f"Failed to disable radio channel: {self.wireless_master_device}")

    print(f"Setting radio channel to {11} and enabling radio...")
    if not self.wireless_master_device.enableRadio(11):
        raise RuntimeError(f"Failed to set radio channel: {self.wireless_master_device}")

    print("Attaching callback handler...")
    self.wireless_master_device.addCallbackHandler(wireless_master_callback)

    print("Waiting for MTW to wirelessly connect...\n")

    wait_for_connections = True
    connected_mtw_count = len(wireless_master_callback.getWirelessMTWs())
    if wait_for_connections:
        time.sleep(5)
            


    print("Configuring the device...")
    new_update_rate = 100
    configArray = xda.XsOutputConfigurationArray()
    configArray.push_back(xda.XsOutputConfiguration(xda.XDI_PacketCounter, 0))
    configArray.push_back(xda.XsOutputConfiguration(xda.XDI_SampleTimeFine, 0))
    configArray.push_back(xda.XsOutputConfiguration(xda.XDI_Acceleration, new_update_rate))
    configArray.push_back(xda.XsOutputConfiguration(xda.XDI_EulerAngles , new_update_rate))

    if not self.wireless_master_device.setUpdateRate(new_update_rate):
        raise RuntimeError("Could not configure the device. Aborting.")

    mtw_devices = self.wireless_master_device.children()

    #mtw_data_queues = [multiprocessing.Queue(maxsize=1000) for _ in range(len(mtw_devices))]
    self.mtw_callbacks = [AwH.MtwCallback(i, mtw_devices[i]) for i in range(len(mtw_devices))]
    for i in range(len(mtw_devices)):
        mtw_devices[i].addCallbackHandler(self.mtw_callbacks[i])

    for ch in self.wireless_master_device.children():
        print(ch.updateRate())

    self.wireless_master_device.gotoMeasurement()

    time.sleep(1) 
    process = multiprocessing.Process(target=sampling_function(self.mtw_callbacks, self._data))
    process.start()
    

  '''def connect(self, timeout_s=10):

    self.wireless_master_callback = AwH.WirelessMasterCallback()

    print("Constructing XsControl...")
    self.control = xda.XsControl.construct()
    if self.control is None:
        print("Failed to construct XsControl instance.")
        sys.exit(1)

    print("Scanning ports...")

    wireless_master_callback = AwH.WirelessMasterCallback()

    detected_devices = xda.XsScanner_scanPorts()

    print("Finding wireless master...")
    wireless_master_port = next((port for port in detected_devices if port.deviceId().isWirelessMaster()), None)
    if wireless_master_port is None:
        raise RuntimeError("No wireless masters found")

    print(f"Wireless master found @ {wireless_master_port}")

    print("Opening port...")
    if not self.control.openPort(wireless_master_port.portName(), wireless_master_port.baudrate()):
        raise RuntimeError(f"Failed to open port {wireless_master_port}")

    print("Getting XsDevice instance for wireless master...")
    self.wireless_master_device = self.control.device(wireless_master_port.deviceId())
    if self.wireless_master_device is None:
        raise RuntimeError(f"Failed to construct XsDevice instance: {wireless_master_port}")

    print(f"XsDevice instance created @ {self.wireless_master_device}")

    print("Setting config mode...")
    if not self.wireless_master_device.gotoConfig():
        raise RuntimeError(f"Failed to goto config mode: {self.wireless_master_device}")

    print("Disabling radio channel if previously enabled...")

    if self.wireless_master_device.isRadioEnabled():
        if not self.wireless_master_device.disableRadio():
            raise RuntimeError(f"Failed to disable radio channel: {self.wireless_master_device}")

    print(f"Setting radio channel to {self.desired_radio_channel} and enabling radio...")
    if not self.wireless_master_device.enableRadio(self.desired_radio_channel):
        raise RuntimeError(f"Failed to set radio channel: {self.wireless_master_device}")

    print("Attaching callback handler...")
    self.wireless_master_device.addCallbackHandler(wireless_master_callback)

    print("Waiting for MTW to wirelessly connect...\n")
    
    time.sleep(10)

    print("Configuring the device...")
    self.new_update_rate = 100
    configArray = xda.XsOutputConfigurationArray()
    configArray.push_back(xda.XsOutputConfiguration(xda.XDI_PacketCounter, 0))
    configArray.push_back(xda.XsOutputConfiguration(xda.XDI_SampleTimeFine, 0))
    configArray.push_back(xda.XsOutputConfiguration(xda.XDI_Acceleration, self.new_update_rate))
    configArray.push_back(xda.XsOutputConfiguration(xda.XDI_EulerAngles , self.new_update_rate))

    if not self.wireless_master_device.setUpdateRate(self.new_update_rate):
        raise RuntimeError("Could not configure the device. Aborting.")

    self.mtw_devices = self.wireless_master_device.children()

    #self.mtw_data_queues = [multiprocessing.Queue(maxsize=10000) for _ in range(len(self.mtw_devices))]
    self.mtw_callbacks = [AwH.MtwCallback(i, self.mtw_devices[i]) for i in range(len(self.mtw_devices))]
    for i in range(len(self.mtw_devices)):
        self.mtw_devices[i].addCallbackHandler(self.mtw_callbacks[i])

    for ch in self.wireless_master_device.children():
        print(ch.updateRate())
    
    return True'''
  
  #####################
  ###### RUNNING ######
  #####################
  # Loop until self._running is False.
  # Acquire data from your sensor as desired, and for each timestep.
  def run(self):
      return

  
  # Clean up and quit
  def quit(self):
    print(log_debug('AwindaIMU',"Stopping Awinda IMU measurement."))
    if not self.wireless_master_device.stopRecording():
      raise RuntimeError("Failed to stop recording. Aborting.")


    self.wireless_master_device.clearCallbackHandlers()
    for ch in self.wireless_master_device.children():
       ch.clearCallbackHandlers()
       ch.reset()

    print("Disabling radio...")
    if not self.wireless_master_device.disableRadio():
        raise RuntimeError(f"Failed to disable radio: {self.wireless_master_device}")
    
    for port in self.detected_devices:
       self.control.closePort(port.portName())
    

    self.control.closePort(self.wireless_master_port)
    print(log_debug("AwindaIMUStreamer quitting."))
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

import logging
import atexit


#####################
###### TESTING ######
#####################
try:
  if __name__ == '__main__':
    # Configuration.
    atexit.register(print, "exited")
    duration_s = 3600
    print('\nStarting debugging')
    #import xsensdeviceapi  
    # Connect to the device(s).
    dots_streamer = AwindaIMUStreamer(print_status=True, print_debug=True)
    connection_result = dots_streamer.connect(20)

    #if not connection_result:
    #  dots_streamer.stop()
    #  exit()

    # Run for the specified duration and periodically print the sample rate.
    print('\nRunning for %gs!' % duration_s)
    dots_streamer.run()
    start_time_s = time.time()
    try:
      while time.time() - start_time_s < duration_s:
        time.sleep(10)
        # Print the sampling rates.
        msg = ' Duration: %6.2fs' % (time.time() - start_time_s)
        for device_name in dots_streamer.get_device_names():
          stream_names = dots_streamer.get_stream_names(device_name=device_name)
          for stream_name in stream_names:
            num_timesteps = dots_streamer.get_num_timesteps(device_name, stream_name)
            msg += ' | %s-%s: %6.2f Hz (%4d Timesteps)' % \
                  (device_name, stream_name, ((num_timesteps)/(time.time() - start_time_s)), num_timesteps)
        print(msg)
    except Exception as e:
      print(e)
    
    # Stop the streamer.
    dots_streamer.stop()
except Exception as e:
    logging.info(e)  
