# Whether to use OpenCV or pyqtgraph to generate a composite visualization.
#   The OpenCV method is a bit faster, but the pyqtgraph method is interactive.
use_opencv_for_composite = False

if not use_opencv_for_composite:
  import pyqtgraph
  import pyqtgraph.exporters
  import numpy as np
  from PyQt6 import QtWidgets, QtGui

import threading
import cv2
import numpy as np
import os
import time
from collections import OrderedDict

from handlers.LoggingHandler import Logger
from consumers.Consumer import Consumer
from visualizers.Visualizer import Visualizer

from utils.print_utils import *
from utils.zmq_utils import *


###########################################################################
###########################################################################
# A class to visualize streaming data.
# SensorStreamer instances are passed to the class, and the data
#  that they stream can be visualized periodically or all at once.
# Each streamer that supports visualization should implement the following:
#   get_default_visualization_options(self, device_name, stream_name)
#   which returns a dict with 'class' and any additional options.
#  The specified class should inherit from visualizers.Visualizer.
#   To not show a visualization, 'class' can map to 'none' or None.
###########################################################################
###########################################################################
class DataVisualizer(Consumer):
  @property
  def _log_source_tag(self) -> str:
    return 'visualizer'


  def __init__(self, 
               streamer_specs: list[dict],
               logging_spec: dict,
               port_sub: str = PORT_FRONTEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               is_visualize_streaming: bool = True,
               is_visualize_all_when_stopped: bool = False,
               is_wait_while_windows_open: bool = False,
               update_period_s: float = 2.0,
               use_composite_video: bool = True, 
               composite_video_filepath: str = None,
               composite_video_layout: list[list[dict]] = None, 
               log_history_filepath: str = None,
               print_status: bool = True, 
               print_debug: bool = False, 
               **_):

    super().__init__(streamer_specs=streamer_specs,
                     port_sub=port_sub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     log_history_filepath=log_history_filepath,
                     print_status=print_status,
                     print_debug=print_debug)

    # Record the configuration options.
    self._update_period_s = update_period_s
    self._use_composite_video = use_composite_video
    self._composite_video_filepath = composite_video_filepath
    self._composite_video_layout = composite_video_layout
    self._composite_video_tileBorder_width = max(1, round(1/8/100*sum([tile_layout['width'] for tile_layout in composite_video_layout[0]]))) if composite_video_layout is not None else None
    self._composite_video_tileBorder_color = [225, 225, 225] # BGR
    self._composite_frame_width = None # will be computed from the layout
    self._composite_frame_height = None # will be computed from the layout
    self._composite_frame_height_withTimestamp = None # will be computed from the layout and the timestamp height
    self._is_visualize_streaming = is_visualize_streaming
    self._is_visualize_all_when_stopped = is_visualize_all_when_stopped
    self._is_wait_while_windows_open = is_wait_while_windows_open
    self._print_debug_extra = False # Print debugging information for visualizers that probably isn't needed during normal experiment logging
    self._last_debug_updateTime_print_s = 0

    # Inherits the datalogging functionality.
    self._logger = Logger(**logging_spec)

    # Launch datalogging thread with reference to the Stream object.
    self._logger_thread = threading.Thread(target=self._logger, args=(self._streams,))
    self._logger_thread.start()
    self._is_visualize = True
    self._visualize_streaming_data()


  def _cleanup(self):
    self._logger.cleanup()
    self._is_visualize = False
    self._close_visualizations()
    # Finish up the file saving before exitting.
    self._logger_thread.join()
    super()._cleanup()


  ##############################
  ###### VISUALIZING DATA ######
  ##############################
  # Initialize visualizers.
  # Will use the visualizer specified by each streamer,
  #  which may be a default visualizer defined in this file or a custom one.
  def _init_visualizations(self, hide_composite: bool = False):
    # Initialize the composite view.
    self._composite_video_writer = None
    self._composite_parent_layout = None
    self._composite_visualizer_layouts = None
    self._composite_visualizer_layout_sizes = None
    self._hide_composite = hide_composite
    # Validate the composite video configuration.
    if self._composite_video_layout is None and self._use_composite_video:
      raise AssertionError('Automatic composite video layout is not currently supported.')
    if self._use_composite_video:
      num_columns_perRow = np.array([len(row_layout) for row_layout in self._composite_video_layout])
      # assert (not any(np.diff(num_columns_perRow)) != 0), 'All rows of the composite video layout must have the same number of columns'
      heights = np.array([[tile_spec['height'] for tile_spec in row_layout if tile_spec] for row_layout in self._composite_video_layout])
      # assert (not np.any(np.diff(heights, axis=1) != 0)), 'All images in a row of the composite video must have the same height.'
      widths = np.array([[tile_spec['width'] for tile_spec in row_layout] for row_layout in self._composite_video_layout])
      # assert (not np.any(np.diff(widths, axis=0) != 0)), 'All images in a column of the composite video must have the same width.'
      
      # Determine the overall size of the composite video frames.
      self._composite_frame_width = np.sum(widths, axis=1)[0] # + 2*len(widths)*self._composite_video_tileBorder_width
      self._composite_frame_height = np.sum(heights, axis=0)[0] # + 2*len(widths)*self._composite_video_tileBorder_width
      
      # Configure the bottom banner that includes the timestamps and labels.
      self._composite_video_banner_height = max(20, round(1/30 * self._composite_frame_height))
      self._composite_frame_height_withTimestamp = self._composite_frame_height + self._composite_video_banner_height
      self._composite_video_banner_bg_color = [100, 100, 100] # BGR
      self._composite_video_banner_text_color = [255, 255, 0] # BGR
      self._composite_video_banner_activity_text_colors = {
        'Good' : self._composite_video_banner_text_color, # BGR
        'Maybe': [0, 155, 255], # BGR
        'Bad'  : [50, 50, 255] # BGR
      }
      # Find a font scale that will make the text fit within the desired pad size.
      target_height = 0.5*self._composite_video_banner_height
      target_width = 0.5*self._composite_frame_width
      fontFace = cv2.FONT_HERSHEY_SIMPLEX
      fontScale = 0
      fontThickness = 2 if self._composite_video_banner_height > 25 else 1
      textsize = None
      while (textsize is None) or ((textsize[1] < target_height) and (textsize[0] < target_width)):
        fontScale += 0.2
        textsize = cv2.getTextSize(get_time_str(0, format='%Y-%m-%d %H:%M:%S.%f'), fontFace, fontScale, fontThickness)[0]
      fontScale -= 0.2
      textsize = cv2.getTextSize(get_time_str(0, format='%Y-%m-%d %H:%M:%S.%f'), fontFace, fontScale, fontThickness)[0]
      self._composite_video_banner_timestamp_fontScale = fontScale
      self._composite_video_banner_timestamp_textSize = textsize
      self._composite_video_banner_fontThickness = fontThickness
      self._composite_video_banner_fontFace = fontFace
      self._composite_video_banner_targetFontHeight = target_height

      # Check whether an ExperimentControlStreamer is present,
      #  so activity labels can be added to the composite video.
      self._experimentControl_stream = None
      for _, stream in self._streams.items():
        if type(stream).__name__ == 'ExperimentControlStream':
          self._experimentControl_stream = stream
          
      # Get a list of streams included in the composite video.
      streams_in_composite = []
      for (row_index, row_layout) in enumerate(self._composite_video_layout):
        for (column_index, tile_info) in enumerate(row_layout):
          if tile_info['device_name'] is None:
            continue
          if tile_info['stream_name'] is None:
            continue
          streams_in_composite.append((tile_info['device_name'], tile_info['stream_name']))
          
      # Create a parent layout and sub-layouts for the composite visualization.
      if not use_opencv_for_composite:
        pyqtgraph.setConfigOption('background', 'w')
        pyqtgraph.setConfigOption('foreground', 'k')
        self._app = QtWidgets.QApplication([])
        # Define a top-level widget to hold everything
        self._composite_widget = QtWidgets.QWidget()
        if hide_composite:
          self._composite_widget.hide()
        # Create a grid layout to manage the widgets size and position
        self._composite_parent_layout = QtWidgets.QGridLayout()
        self._composite_widget.setLayout(self._composite_parent_layout)
        self._composite_widget.setWindowTitle('Composite Visualization')
        self._composite_widget.setGeometry(10, 50, self._composite_frame_width, self._composite_frame_height)
        self._composite_widget.show()
        # Create widgets for each streamer.
        self._composite_visualizer_layouts = {}
        self._composite_visualizer_layout_sizes = {}
        for (row_index, row_layout) in enumerate(self._composite_video_layout):
          for (column_index, tile_info) in enumerate(row_layout):
            device_name = tile_info['device_name']
            stream_name = tile_info['stream_name']
            rowspan = tile_info['rowspan']
            colspan = tile_info['colspan']
            width = tile_info['width']
            height = tile_info['height']
            if tile_info['device_name'] is None:
              continue
            if tile_info['stream_name'] is None:
              continue
            layout = pyqtgraph.GraphicsLayoutWidget()
            self._composite_parent_layout.addWidget(layout, row_index, column_index, rowspan, colspan)
            self._composite_visualizer_layouts.setdefault(device_name, {})
            self._composite_visualizer_layouts[device_name][stream_name] = layout
            self._composite_visualizer_layout_sizes.setdefault(device_name, {})
            self._composite_visualizer_layout_sizes[device_name][stream_name] = (width, height)
            
      # Create a composite video writer if desired.
      if self._composite_video_filepath is not None:
        extension = 'avi'
        fourcc = 'MJPG'
        fps = 1/self._update_period_s
        self._composite_video_filepath = '%s.%s' % (os.path.splitext(self._composite_video_filepath)[0], extension)
        if use_opencv_for_composite:
          composite_video_frame_height = self._composite_frame_height_withTimestamp
        else:
          composite_video_frame_height = self._composite_frame_height
        composite_video_frame_width = self._composite_frame_width
        self._composite_video_writer = cv2.VideoWriter(self._composite_video_filepath,
                                                       cv2.VideoWriter_fourcc(*fourcc),
                                                       fps, 
                                                       (composite_video_frame_width, composite_video_frame_height))

    # Initialize a record of the next indexes that should be fetched for each stream,
    #  and how many timesteps to stay behind of the most recent step (if needed).
    self._next_data_indexes = [OrderedDict() for i in range(len(self._streams.items()))]
    self._timesteps_before_solidified = [OrderedDict() for i in range(len(self._streams.items()))]
    for stream_index, (stream_type, stream) in enumerate(self._streams.items()):
      for (device_name, device_info) in stream.get_stream_info_all().items():
        self._next_data_indexes[stream_index][device_name] = OrderedDict()
        self._timesteps_before_solidified[stream_index][device_name] = OrderedDict()
        for (stream_name, stream_info) in device_info.items():
          self._next_data_indexes[stream_index][device_name][stream_name] = 0
          self._timesteps_before_solidified[stream_index][device_name][stream_name] = stream_info['timesteps_before_solidified']

    # Instantiate and initialize the visualizers.
    self._visualizers = [OrderedDict() for i in range(len(self._streams.items()))]
    for stream_index, (stream_type, stream) in enumerate(self._streams.items()):
      for (device_name, device_info) in stream.get_stream_info_all().items():
        self._visualizers[stream_index][device_name] = OrderedDict()
        for (stream_name, stream_info) in device_info.items():
          visualizer_options = stream.get_default_visualization_options()[device_name][stream_name]
          if callable(visualizer_options['class']):
            try:
              composite_visualizer_layout = self._composite_visualizer_layouts[device_name][stream_name]
              composite_visualizer_layout_size = self._composite_visualizer_layout_sizes[device_name][stream_name]
            except:
              composite_visualizer_layout = None
              composite_visualizer_layout_size = None
            visualizer: Visualizer = visualizer_options['class'](visualizer_options,
                                                                 hidden=self._use_composite_video,
                                                                 parent_layout=composite_visualizer_layout,
                                                                 parent_layout_size=composite_visualizer_layout_size,
                                                                 print_status=self._print_status)
            visualizer.init(device_name, stream_name, stream_info)
          else:
            visualizer = None
          self._visualizers[stream_index][device_name][stream_name] = visualizer

    # Initialize state for visualization control.
    self._last_update_time_s = None


  # Close line plot figures, video windows, and custom visualizers.
  def _close_visualizations(self):
    for visualizers_streamer in self._visualizers:
      for (device_name, visualizers_device) in visualizers_streamer.items():
        for (stream_name, visualizer) in visualizers_device.items():
          if visualizer is not None:
            try:
              visualizer.close()
            except:
              pass
    if self._composite_video_writer is not None:
      self._composite_video_writer.release()
      time.sleep(2)
    try:
      cv2.destroyAllWindows()
    except:
      pass
    try:
      self._app.quit()
    except:
      pass


  # Periodically update the visualizations until a stopping criteria is met.
  def _visualize_streaming_data(self):
    # Initialize visualizations.
    self._init_visualizations()

    # Visualize the streaming data.
    while self._is_visualize:
      self._update_visualizations(wait_for_next_update_time=True)


  # Visualize data that is already logged, either from streaming or from replaying logs.
  # Periodically update the visualizations until a stopping criteria is met.
  # This function is blocking.
  def _visualize_logged_data(self, 
                             start_offset_s: float = None, 
                             end_offset_s: float = None,
                             start_time_s: float = None, 
                             end_time_s: float = None,
                             duration_s: float = None,
                             hide_composite: bool = False, 
                             realtime: bool = True):
    # Initialize visualizations.
    self._init_visualizations(hide_composite=hide_composite)
    
    # Determine reasonable start and end times.
    (start_time_s, end_time_s) = self._get_loggedData_start_end_times_s(start_offset_s=start_offset_s,
                                                                        end_offset_s=end_offset_s,
                                                                        start_time_s=start_time_s,
                                                                        end_time_s=end_time_s,
                                                                        duration_s=duration_s)
      
    # Visualize the existing data.
    # self._log_status('DataVisualizer visualizing logged data')
    current_time_s = start_time_s
    current_frame_index = 0
    start_viz_time_s = time.time()
    while current_time_s <= end_time_s:
      # self._log_debug('Visualizing for time %0.2f' % current_time_s)
      self._update_visualizations(wait_for_next_update_time=False,
                                  verify_next_update_time=False,
                                  ending_time_s=current_time_s, 
                                  hide_composite=hide_composite)
      current_time_s += self._update_period_s
      current_frame_index += 1
      if realtime:
        next_update_time_s = start_viz_time_s + current_frame_index * self._update_period_s
        time.sleep(max(0, next_update_time_s - time.time()))
    # self._log_status('DataVisualizer finished visualizing logged data')


  # Determine reasonable start and end times for visualizing logged data.
  def _get_loggedData_start_end_times_s(self, 
                                        start_offset_s: float = None, 
                                        end_offset_s: float = None,
                                        start_time_s: float = None,
                                        end_time_s: float = None,
                                        duration_s: float = None):
    start_times_s = []
    end_times_s = []
    for streamer_index, (stream_type, stream) in enumerate(self._streams.items()):
      streamer_start_times_s = []
      streamer_end_times_s = []
      for (device_name, device_info) in stream.get_stream_info_all().items():
        for (stream_name, stream_info) in device_info.items():
          streamer_start_time_s = stream._get_start_time_s(device_name, stream_name)
          streamer_end_time_s = stream._get_end_time_s(device_name, stream_name)
          if streamer_start_time_s is not None:
            streamer_start_times_s.append(streamer_start_time_s)
          if streamer_end_time_s is not None:
            streamer_end_times_s.append(streamer_end_time_s)
      # Use the earliest start time and the latest end time
      #  to indicate when any data from the streamer was available.
      if len(streamer_start_times_s) > 0:
        start_times_s.append(min(streamer_start_times_s))
        end_times_s.append(max(streamer_end_times_s))
    # # Choose the latest start time and the earliest end time,
    # #  so that data is always available from every streamer.
    # start_time_s = max(start_times_s)
    # end_time_s = min(end_times_s)
    # Choose the earliest start time and the latest end time,
    #  to cover all data from all streamers.
    if start_time_s is None:
      start_time_s = min(start_times_s)
    if end_time_s is None:
      end_time_s = max(end_times_s)
  
    # Adjust the start and end times if desired.
    if start_offset_s is not None:
      start_time_s += start_offset_s
    if end_offset_s is not None:
      end_time_s -= end_offset_s
    if duration_s is not None:
      end_time_s = start_time_s + duration_s
    
    # Return the results.
    return (start_time_s, end_time_s)


  # Fetch recent data from each streamer and visualize it.
  # If a poll period is set by self._visualize_period_s, can opt to check whether
  #  the next update time has been reached before proceeding by setting verify_next_update_time.
  #  If so, can wait for the time to arrive or return immediately by setting wait_for_next_update_time.
  # If an ending time is specified, will only fetch data up to that time.
  #  Otherwise, will fetch up to the end of the current log.
  def _update_visualizations(self, 
                             wait_for_next_update_time: bool = True, 
                             verify_next_update_time: bool = True, 
                             ending_time_s: float = None, 
                             hide_composite: bool = False):
    # Check whether it is time to show new data, which is when:
    #  This is the first iteration,
    #  it has been at least self._update_period_s since the last visualization, or
    #  no polling period was specified.
    if verify_next_update_time and self._update_period_s is not None:
      if self._print_debug_extra: pass
        # self._log_debug('Visualization thread checking if the next update time is reached')
      next_update_time_s = (self._last_update_time_s or 0) + self._update_period_s
      if time.time() < next_update_time_s:
        # Return immediately or wait as appropriate.
        if not wait_for_next_update_time:
          return
        time.sleep(max(0, next_update_time_s - time.time()))
      # Update the last update time now, before the visualization actually starts.
      # This will keep the period more consistent; otherwise, the amount
      #   of time it takes to visualize would be added to the update period.
      #   This would compound over time, leading to longer delays and more data to display each time.
      #   This becomes more severe as the visualization duration increases.
      self._last_update_time_s = time.time()
    if self._print_debug_extra: pass
      # self._log_debug('Visualization thread starting update')
    # Visualize new data for each stream of each device of each streamer.
    start_update_time_s = time.time()
    for stream_index, (stream_type, stream) in enumerate(self._streams.items()):
      for (device_name, device_info) in stream.get_stream_info_all().items():
        if self._print_debug_extra: pass
          # self._log_debug('Visualizing streams for streamer %d device %s' % (stream_index, device_name))
        for (stream_name, stream_info) in device_info.items():
          # Check if a visualizer is created for this stream.
          visualizer: Visualizer = self._visualizers[stream_index][device_name][stream_name]
          if visualizer is None:
            continue
          # Determine the start and end bounds for data to fetch.
          if ending_time_s is None:
            #  End at the most recent data (or back by a few timesteps
            #  if the streamer may still edit the most recent timesteps).
            ending_index = -self._timesteps_before_solidified[stream_index][device_name][stream_name]
            if ending_index == 0: # no time is needed to solidify, so fetch up to the most recent data
              ending_index = None
          else:
            #  End at the specified time.
            ending_index = None
          # Start with the first timestep that hasn't been shown yet,
          #  or with just the last frame if getting video data.
          starting_index = self._next_data_indexes[stream_index][device_name][stream_name]
          if stream_info['is_video']:
            if ending_time_s is None:
              if ending_index is None:
                starting_index = stream.get_num_timesteps(device_name, stream_name) - 1
              else:
                starting_index = ending_index - 1
            else:
              ending_index_forTime = stream.get_index_for_time_s(device_name, stream_name, ending_time_s, target_before=True)
              if ending_index_forTime is not None:
                ending_index_forTime += 1 # since will use as a list index and thus exclude the specified index
                starting_index = ending_index_forTime - 1
          # Get the data!
          start_get_data_time_s = time.time()
          new_data = stream.get_data(device_name, 
                                     stream_name, 
                                     return_deepcopy=False,
                                     starting_index=starting_index,
                                     ending_index=ending_index,
                                     ending_time_s=ending_time_s)
          # self._log_status('Time to get data: \t%s \t \t%0.3f' % (type(streamer).__name__, time.time() - start_get_data_time_s))
          if new_data is not None:
            # Visualize any new data and save any updated sates.
            if visualizer is not None:
              start_visualizer_update_time_s = time.time()
              fps_info = stream.get_fps()
              visualizer.update(new_data, visualizing_all_data=False, fps=fps_info[device_name])
              # self._log_status('Time to update vis: \t%s \t%s \t%s \t%0.3f' % (type(streamer).__name__, stream_name, type(visualizer).__name__, time.time() - start_visualizer_update_time_s))
            # Update starting indexes for the next write.
            stream.clear_data(device_name, stream_name, first_index_to_keep=starting_index)
            next_starting_index = 0
            new_data = None
            self._next_data_indexes[stream_index][device_name][stream_name] = next_starting_index
            if self._print_debug_extra: pass
              # self._log_debug('Visualized %d new entries for stream %s.%s' % (num_new_entries, device_name, stream_name))
          else:
            # check if data has been cleared from memory, thus invalidating our start index.
            if stream.get_num_timesteps(device_name, stream_name) < starting_index:
              self._next_data_indexes[stream_index][device_name][stream_name] = 0
    if self._print_debug_extra: pass
      # self._log_debug('Visualization thread finished update of each streamer')
    if self._print_debug_extra: pass
      # self._log_debug('Time to update visualizers: \t \t \t \t%0.3f' % (time.time() - start_update_time_s))
    # self._log_status('Time to update visualizers: \t \t \t \t%0.3f' % (time.time() - start_update_time_s))
    # If showing a composite video, update it now that the streamers have updated their frames.
    if self._use_composite_video:
      start_composite_update_time_s = time.time()
      if use_opencv_for_composite:
        self._update_composite_video_opencv(hidden=hide_composite, time_s=ending_time_s or self._last_update_time_s)
      else:
        self._update_composite_video_pyqtgraph(hidden=hide_composite, time_s=ending_time_s or self._last_update_time_s)
      if self._print_debug_extra: pass
        # self._log_debug('Time to update composite visualization: \t \t \t \t%0.3f' % (time.time() - start_composite_update_time_s))
    if (time.time() - self._last_debug_updateTime_print_s > 5) or self._print_debug_extra:
      # self._log_debug('Time to update visualizers and composite: %0.4f' % (time.time() - start_update_time_s))
      self._last_debug_updateTime_print_s = time.time()


  # Visualize all data currently in the streamers' memory.
  # This is meant to be called at the end of an experiment.
  # This may interfere with windows/figures created by update_visualizations()
  #  so it is recommended to close all existing visualizations first.
  def _visualize_all_data(self):
    # Initialize visualizations.
    self._init_visualizations()

    # Visualize all recorded data.
    # self._log_status('DataVisualizer visualizing all data')
    for (stream_index, stream) in enumerate(self._streams):
      for (device_name, device_info) in stream.get_all_stream_infos().items():
        if self._print_debug_extra: pass
          # self._log_debug('Visualizing streams for streamer %d device %s' % (stream_index, device_name))
        for (stream_name, stream_info) in device_info.items():
          # Fetch data starting with the first timestep,
          #  and ending at the most recent data (or back by a few timesteps
          #  if the streamer may still edit the most recent timesteps).
          starting_index = 0
          ending_index = -self._timesteps_before_solidified[stream_index][device_name][stream_name]
          if ending_index == 0: # no time is needed to solidify, so fetch up to the most recent data
            ending_index = None
          new_data = stream.get_data(device_name, stream_name, return_deepcopy=False,
                                        starting_index=starting_index, ending_index=ending_index)
          if new_data is not None:
            # Visualize any new data and save any updates states.
            visualizer: Visualizer = self._visualizers[stream_index][device_name][stream_name]
            if visualizer is not None:
              visualizer.update(new_data, visualizing_all_data=True)
            if self._print_debug_extra: pass
              # self._log_debug('Visualized %d new entries for stream %s.%s' % (len(new_data['data']), device_name, stream_name))


  # Create a composite video from all streamers that are creating visualizations.
  def _update_composite_video_opencv(self, 
                                     hidden: bool = False, 
                                     time_s: float = None):
    if self._print_debug_extra: pass
      # self._log_debug('DataVisualizer updating the composite video using OpenCV')
    # Get the latest images from each streamer.
    imgs = []
    for (row_index, row_layout) in enumerate(self._composite_video_layout):
      imgs.append([])
      for (column_index, tile_info) in enumerate(row_layout):
        if tile_info['device_name'] is None:
          imgs[-1].append(None)
          continue
        # Find the streamer for this tile.
        img = None
        for visualizers_streamer in self._visualizers:
          for (device_name, visualizers_device) in visualizers_streamer.items():
            if device_name != tile_info['device_name']:
              continue
            for (stream_name, visualizer) in visualizers_device.items():
              if stream_name != tile_info['stream_name']:
                continue
              if visualizer is None:
                continue
              # Get the latest image
              try:
                img = visualizer.get_visualization_image(device_name, stream_name)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
              except AttributeError:
                # The streamer likely hasn't actually made a figure yet,
                #  so just use a black image for now.
                img = np.zeros((100, 100, 3), dtype=np.uint8) # will be resized later
        # Append the image, or a blank image if the device/stream was not found.
        if img is None:
          img = np.zeros((100, 100, 3), dtype=np.uint8) # will be resized later
        imgs[-1].append(img)
    # Resize the images.
    for (row_index, row_layout) in enumerate(self._composite_video_layout):
      for (column_index, tile_info) in enumerate(row_layout):
        img = imgs[row_index][column_index]
        if img is None:
          continue
        img_width = img.shape[1]
        img_height = img.shape[0]
        target_width = tile_info['width'] - 2*self._composite_video_tileBorder_width
        target_height = tile_info['height'] - 2*self._composite_video_tileBorder_width
        # Check if the width or height will be the controlling dimension.
        scale_factor_fromWidth = target_width/img_width
        scale_factor_fromHeight = target_height/img_height
        if img_height*scale_factor_fromWidth > target_height:
          scale_factor = scale_factor_fromHeight
        else:
          scale_factor = scale_factor_fromWidth
        # Resize the image.
        img = cv2.resize(img, (0,0), None, scale_factor, scale_factor)
        # Pad the image to fill the tile.
        img_width = img.shape[1]
        img_height = img.shape[0]
        pad_top = int(max(0, (target_height - img_height)/2))
        pad_bottom = (target_height - (img_height+pad_top))
        pad_left = int(max(0, (target_width - img_width)/2))
        pad_right = (target_width - (img_width+pad_left))
        pad_color = [225, 225, 225]
        img = cv2.copyMakeBorder(img, 
                                 pad_top, 
                                 pad_bottom, 
                                 pad_left, 
                                 pad_right,
                                 cv2.BORDER_CONSTANT, 
                                 value=pad_color)
        # Add a border around each tile
        border_color = self._composite_video_tileBorder_color
        border_width = self._composite_video_tileBorder_width
        img = cv2.copyMakeBorder(img, 
                                 border_width, 
                                 border_width, 
                                 border_width, 
                                 border_width,
                                 cv2.BORDER_CONSTANT, 
                                 value=border_color)
        imgs[row_index][column_index] = img
    # # Create the composite image.
    # composite_row_imgs = []
    # for (row_index, row_imgs) in enumerate(imgs):
    #   composite_row_imgs.append(cv2.hconcat(row_imgs))
    # composite_img = cv2.vconcat(composite_row_imgs)
    # Create the composite image.
    composite_column_imgs = []
    for column_index in range(len(imgs[0])):
      imgs_for_column = []
      for (row_index, row_imgs) in enumerate(imgs):
        if row_imgs[column_index] is not None:
          imgs_for_column.append(row_imgs[column_index])
      composite_column_imgs.append(cv2.vconcat(imgs_for_column))
    composite_img = cv2.hconcat(composite_column_imgs)
    
    # Add a banner on the bottom.
    if time_s is not None or self._experimentControl_stream is not None:
      composite_img = cv2.copyMakeBorder(composite_img, 
                                         0, 
                                         self._composite_video_banner_height, 
                                         0, 
                                         0,
                                         cv2.BORDER_CONSTANT, 
                                         value=self._composite_video_banner_bg_color)
    # Add a timestamp to the bottom banner.
    if time_s is not None:
      timestamp_str = get_time_str(time_s, format='%Y-%m-%d %H:%M:%S.%f')
      composite_img = cv2.putText(composite_img, timestamp_str,
                                  [int(composite_img.shape[1]/50),  # for centered text: int(composite_img.shape[1] - self._composite_video_timestamp_textSize[0]/2)
                                   int(composite_img.shape[0] - self._composite_video_banner_height/2 + self._composite_video_banner_timestamp_textSize[1]/3)],
                                  fontFace=self._composite_video_banner_fontFace, 
                                  fontScale=self._composite_video_banner_timestamp_fontScale,
                                  color=self._composite_video_banner_text_color, 
                                  thickness=self._composite_video_banner_fontThickness)
    # Add active labels to the bottom banner.
    if self._experimentControl_stream is not None:
      device_name = 'experiment-activities'
      stream_name = 'activities'
      index_forTime = self._experimentControl_stream.get_index_for_time_s(device_name, stream_name, time_s, target_before=True)
      if index_forTime is not None:
        # Get the most recent label entry.
        label_data = self._experimentControl_stream.get_data(device_name, 
                                                             stream_name, 
                                                             return_deepcopy=False,
                                                             starting_index=index_forTime,
                                                             ending_index=index_forTime+1)
        # If it started an activity, then write its label in the banner.
        label_data = label_data['data'][-1]
        if not isinstance(label_data[0], str):
          # The data will be str if streaming, but bytes if replaying existing logs.
          label_data = [x.decode('utf-8') for x in label_data]
        if 'Start' in label_data:
          activity_label = label_data[0]
          activity_ranking = label_data[2]
          # Find a text size so it will fit in the banner height and in half of the frame width.
          target_height = self._composite_video_banner_targetFontHeight
          target_width = 0.5*self._composite_frame_width
          fontFace = self._composite_video_banner_fontFace
          fontScale = 0
          fontThickness = self._composite_video_banner_fontThickness
          textsize = None
          while (textsize is None) or ((textsize[1] < target_height) and (textsize[0] < target_width)):
            fontScale += 0.2
            textsize = cv2.getTextSize(activity_label, fontFace, fontScale, fontThickness)[0]
          fontScale -= 0.2
          textsize = cv2.getTextSize(activity_label, fontFace, fontScale, fontThickness)[0]
          fontColor = self._composite_video_banner_text_color
          if activity_ranking in self._composite_video_banner_activity_text_colors:
            fontColor = self._composite_video_banner_activity_text_colors[activity_ranking]
          composite_img = cv2.putText(composite_img, activity_label,
                                      [int(composite_img.shape[1] - composite_img.shape[1]/50 - textsize[0]),
                                       int(composite_img.shape[0] - self._composite_video_banner_height/2 + textsize[1]/3)],
                                      fontFace=fontFace, 
                                      fontScale=fontScale,
                                      color=fontColor, 
                                      thickness=fontThickness)
    
    # Display the composite image if desired.
    if not hidden:
      cv2.imshow('Action!', composite_img)
      cv2.waitKey(1)
    # Write the composite image to a video if desired.
    if self._composite_video_writer is not None:
      self._composite_video_writer.write(composite_img)


  def _update_composite_video_pyqtgraph(self, 
                                        hidden: bool = False, 
                                        time_s: float = None):
    if self._print_debug_extra: pass
      # self._log_debug('DataVisualizer updating the composite video using pyqtgraph')
    # Display the composite image if desired.
    if not hidden:
      cv2.waitKey(1) # find a better way?
    # Write the composite image to a video if desired.
    if self._composite_video_writer is not None:
      composite_img = self._composite_widget.grab() # returns a QPixmap
      composite_img = composite_img.toImage() # returns a QImage
      composite_img = self._convertQImageToMat(composite_img)
      composite_img = composite_img[:,:,0:3]
      scale_factor_width = self._composite_frame_width / composite_img.shape[1]
      scale_factor_height = self._composite_frame_height / composite_img.shape[0]
      composite_img = cv2.resize(composite_img, (0,0), None, scale_factor_width, scale_factor_height)
      self._composite_video_writer.write(composite_img)


  # Convert a QImage to a numpy ndarray in BGR format.
  def _convertQImageToMat(self, qimg):
    img = qimg.convertToFormat(QtGui.QImage.Format.Format_RGB32)
    ptr = img.bits()
    ptr.setsize(img.sizeInBytes())
    arr = np.array(ptr).reshape(img.height(), img.width(), 4)  #  Copies the data
    return arr


  # Keep line plot figures responsive if any are active.
  # Wait for user to press a key or close the windows if any videos are active.
  # Note that this will only work if called on the main thread.
  def _wait_while_windows_open(self):
    # Get a list of waiting functions for the various visualizers.
    waiting_functions = []
    for visualizers_streamer in self._visualizers:
      for (device_name, visualizers_device) in visualizers_streamer.items():
        for (stream_name, visualizer) in visualizers_device.items():
          if visualizer is not None:
            waiting_functions.append(visualizer.wait_for_user_to_close)
    # Wait for all of the functions to be satisfied.
    if len(waiting_functions) > 0:
      # self._log_userAction('\n\n*** Close all visualization windows to exit\n\n')
      pass
    for wait_fn in waiting_functions:
      wait_fn()
    if self._use_composite_video and not self._hide_composite:
      if use_opencv_for_composite:
        cv2.waitKey(0)
      else:
        self._app.exec()


#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  from producers.EyeStreamer import EyeStreamer
  import zmq

  stream_info = {
    'pupil_capture_ip'      : 'localhost',
    'pupil_capture_port'    : '50020',
    'video_image_format'    : 'bgr',
    'gaze_estimate_stale_s' : 0.2,
    'stream_video_world'    : False, # the world video
    'stream_video_worldGaze': True, # the world video with gaze indication overlayed
    'stream_video_eye'      : False, # video of the eye
    'is_binocular'          : True, # uses both eyes for gaze data and for video
    'shape_video_world'     : (720,1280,3),
    'shape_video_eye0'      : (400,400,3),
    'shape_video_eye1'      : (400,400,3),
    'fps_video_world'       : 30.0,
    'fps_video_eye0'        : 120.0,
    'fps_video_eye1'        : 120.0
  }

  ip = "127.0.0.1"
  port_backend = "42069"
  port_frontend = "42070"
  port_sync = "42071"
  port_killsig = "42066"

  # Pass exactly one ZeroMQ context instance throughout the program
  ctx: zmq.Context = zmq.Context()

  # Exposes a known address and port to locally connected sensors to connect to.
  local_backend: zmq.SyncSocket = ctx.socket(zmq.XSUB)
  local_backend.bind("tcp://127.0.0.1:%s" % (port_backend))
  backends: list[zmq.SyncSocket] = [local_backend]

  # Exposes a known address and port to broker data to local workers.
  local_frontend: zmq.SyncSocket = ctx.socket(zmq.XPUB)
  local_frontend.bind("tcp://127.0.0.1:%s" % (port_frontend))
  frontends: list[zmq.SyncSocket] = [local_frontend]

  streamer = EyeStreamer(**stream_info, 
                         port_pub=port_backend,
                         port_sync=port_sync,
                         port_killsig=port_killsig)
  
  # TODO: add datavis in main process to debug

  streamer()
