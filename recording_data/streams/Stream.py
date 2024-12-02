from abc import ABC, abstractmethod

import copy
from collections import OrderedDict
from queue import Queue
import numpy as np

from utils.time_utils import *
from utils.dict_utils import *
from utils.print_utils import *


################################################
################################################
# An abstract class to store data of a SensorStreamer.
#   May contain multiple streams from the sensor, such as acceleration and gyroscope from the DOTs.
# Structure of data and streams_info:
#   Dict with device names as keys, each of which maps to:
#     Dict with name of streams, each of which maps to:
#       for data: 'data', 'time_s', 'time_str', and others if desired
#       for streams_info: 'data_type', 'sample_size', 'sampling_rate_hz', 'timesteps_before_solidified', 'extra_data_info'
# TODO: set a flag to periodically clear old data (if needed)
################################################
################################################
class Stream(ABC):
  # Will store the class name of each sensor in HDF5 metadata,
  #   to facilitate recreating classes when replaying the logs later.
  # The following is the metadata key to store that information.
  metadata_class_name_key = 'SensorStreamer class name'
  # Will look for a special metadata key that labels data channels,
  #   to use for logging purposes and general user information.
  metadata_data_headings_key = 'Data headings'

  def __init__(self) -> None:
    self._data = OrderedDict()
    self._metadata = OrderedDict()
    self._streams_info = OrderedDict()
    self._replaying_data_logs = False

  ############################
  ###### INTERFACE FLOW ######
  ############################
  # Business logic of concrete Stream implementation, must specify `time_s` parameter and any custom data thereafter
  @abstractmethod
  def append_data(self, time_s: float) -> None:
    pass

  # Get how each stream should be visualized.
  # Should be overridden by subclasses if desired.
  # Returns a dictionary mapping [device_name][stream_name] to a dict of visualizer options.
  # See DataVisualizer for options of default visualizers, such as line plots and videos.
  @abstractmethod
  def get_default_visualization_options(self) -> dict:
    # By default no streams are visualized
    visualization_options = {}
    for (device_name, device_info) in self._streams_info.items():
      visualization_options.setdefault(device_name, {})
      for (stream_name, stream_info) in device_info.items():
        visualization_options[device_name].setdefault(stream_name, {'class': None})
    return visualization_options

  # Get actual frame rate, subject to expected transmission delay and throughput limitation,
  #   to confidently judge the performance of the system.
  # Computed based on how fast data becomes available to the data structure, hence suitable
  #   to measure frame rate on the subscriber, local or remote.
  @abstractmethod
  def get_fps(self) -> dict[str, float]:
    pass

  #############################
  ###### GETTERS/SETTERS ######
  #############################
  # Retrieve actual frame rate of a stream if it was set to measure.
  # Records and refreshes statistics on each data structure append
  #   call, making actual frame rate estimate if data sampled remotely and
  #   sent over LAN to collection device.
  def _get_fps(self, device_name: str, stream_name: str) -> float | None:
    if self._streams_info[device_name][stream_name]['is_measure_rate_hz']:
      return self._streams_info[device_name][stream_name]['actual_rate_hz']
    else:
      return None

  # Add a new device stream.
  # @param timesteps_before_solidified allows indication that data/timestamps for
  #   previous timesteps may be altered when a new sample is received.
  #   For example, some sensors may send two samples at the same time, and the
  #     streamer class may infer a timestamp for the previous reading when
  #     a new pair of readings arrive.  A timestamp is thus not 'final' until the next timestep.
  # @param extra_data_info is used to specify additional data keys that will be streamed
  #   along with the default 'data', 'time_s', and 'time_str'.
  #   It should be a dict, where each extra data key maps to a dict with at least 'data_type' and 'sample_size'.
  # @param data_notes can be a string or a dict of relevant info.
  #   If it's a dict, the key 'Data headings' is recommended and will be used by DataLogger for headers.
  #     In that case, 'Data headings' should map to a list of strings of length sample_size.
  def add_stream(self, 
                 device_name: str, 
                 stream_name: str, 
                 data_type: type, 
                 sample_size: list[int] | tuple[int], 
                 sampling_rate_hz: float, 
                 is_measure_rate_hz: bool = False,
                 data_notes: str | dict = None,
                 is_video: bool = False,
                 is_audio: bool = False, 
                 timesteps_before_solidified: int = 0,
                 extra_data_info: dict[str, dict] = None) -> None:
    self._streams_info.setdefault(device_name, OrderedDict())
    if not isinstance(sample_size, (list, tuple)):
      sample_size = [sample_size]
    self._streams_info[device_name][stream_name] = OrderedDict([
                                                    ('data_type', data_type),
                                                    ('sample_size', sample_size),
                                                    ('data_notes', data_notes or {}),
                                                    ('sampling_rate_hz', sampling_rate_hz),
                                                    ('is_measure_rate_hz', is_measure_rate_hz),
                                                    ('is_video', is_video),
                                                    ('is_audio', is_audio),
                                                    ('timesteps_before_solidified', timesteps_before_solidified),
                                                    ('extra_data_info', extra_data_info or {}),
                                                    ])
    if is_measure_rate_hz:
      # Set at start actual rate equal to desired sample rate
      self._streams_info[device_name][stream_name]['actual_rate_hz'] = self._streams_info[device_name][stream_name]['sampling_rate_hz']
      # Create a circular buffer of 1 second, w.r.t. desired sample rate
      circular_buffer_len: int = max(round(sampling_rate_hz), 1)
      self._streams_info[device_name][stream_name]['dt_circular_buffer'] = list([1/sampling_rate_hz] * circular_buffer_len)
      self._streams_info[device_name][stream_name]['dt_circular_index'] = 0
      self._streams_info[device_name][stream_name]['dt_running_sum'] = 1.0
      self._streams_info[device_name][stream_name]['old_toa'] = time.time()

    self.clear_data(device_name, stream_name)

  # Add a single timestep of data to the data log.
  # @param time_s and @param data should each be a single value.
  # @param extra_data should be a dict mapping each extra data key to a single value.
  #   The extra data keys should match what was specified in add_stream() or set_streams_info().
  def _append_data(self, 
                   device_name: str, 
                   stream_name: str, 
                   time_s: float, 
                   data, 
                   extra_data: dict[str, dict] = None) -> None:
    time_str = get_time_str(time_s, '%Y-%m-%d %H:%M:%S.%f')
    self._data[device_name][stream_name]['time_s'].append(time_s)
    self._data[device_name][stream_name]['time_str'].append(time_str)
    self._data[device_name][stream_name]['data'].append(data)
    if extra_data is not None:
      for (extra_key, extra_value) in extra_data.items():
        self._data[device_name][stream_name][extra_key].append(extra_value)
    # If stream set to measure actual fps
    if self._streams_info[device_name][stream_name]['is_measure_rate_hz']:
      # Make intermediate variables for current and previous samples' time-of-arrival
      new_toa = time.time()
      old_toa = self._streams_info[device_name][stream_name]['old_toa']
      # Record the new arrival time for the next iteration
      self._streams_info[device_name][stream_name]['old_toa'] = new_toa
      # Update the running sum of time increments of the circular buffer  
      oldest_dt = self._streams_info[device_name][stream_name]['dt_circular_buffer']\
                    [self._streams_info[device_name][stream_name]['dt_circular_index']]
      newest_dt = new_toa - old_toa
      self._streams_info[device_name][stream_name]['dt_running_sum'] += (newest_dt - oldest_dt)
      # Put current time increment in place of the oldest one in the circular buffer
      self._streams_info[device_name][stream_name]['dt_circular_buffer']\
        [self._streams_info[device_name][stream_name]['dt_circular_index']] = newest_dt
      # Move the index in the circular fashion
      self._streams_info[device_name][stream_name]['dt_circular_index'] %=\
        len(self._streams_info[device_name][stream_name]['dt_circular_buffer'])
      # Refresh the actual frame rate information
      self._streams_info[device_name][stream_name]['actual_rate_hz'] = \
        len(self._streams_info[device_name][stream_name]['dt_circular_buffer']) / \
        self._streams_info[device_name][stream_name]['dt_running_sum']

  # Clear data for a stream (and add the stream if it doesn't exist).
  # Optionally, can clear only data before a specified index.
  def clear_data(self, 
                 device_name: str, 
                 stream_name: str, 
                 first_index_to_keep: int = None) -> None:
    # Create the device/stream entry if it doesn't exist
    self._data.setdefault(device_name, OrderedDict())
    self._data[device_name].setdefault(stream_name, OrderedDict())

    # Get the data keys that have been populated so far.
    data_keys = list(self._data[device_name][stream_name].keys())
    # Get the expected data keys in the stream,
    #  in case data hasn't been received for some of them yet.
    data_keys.extend(['time_s', 'time_str', 'data'])
    data_keys.extend(list(self._streams_info[device_name][stream_name]['extra_data_info'].keys()))
    data_keys = list(set(data_keys))
    # Clear data for each known or expected data key.
    for data_key in data_keys:
      if first_index_to_keep is None:
        self._data[device_name][stream_name][data_key] = []
      else:
        self._data[device_name][stream_name][data_key] = \
          self._data[device_name][stream_name][data_key][first_index_to_keep:]

  def clear_data_all(self) -> None:
    for (device_name, device_info) in self._streams_info.items():
      for (stream_name, stream_info) in device_info.items():
        self.clear_data(device_name, stream_name)

  # Get the number of timesteps recorded so far.
  def get_num_timesteps(self, device_name: str, stream_name: str) -> int:
    times_s = self._get_times_s(device_name, stream_name)
    try: # If reading from a stored HDF5 file, avoid loading the array into memory
      return times_s.shape[0]
    except:
      return len(times_s)

  # Get the start time of data recorded so far.
  def get_start_time_s(self, device_name: str, stream_name: str) -> float:
    try:
      start_time_s = self._get_times_s(device_name, stream_name)[0]
      if isinstance(start_time_s, np.ndarray):
        start_time_s = start_time_s[0]
      return start_time_s
    except IndexError:
      return None

  # Get the end time of data recorded so far.
  def get_end_time_s(self, device_name: str, stream_name: str) -> float:
    try:
      end_time_s = self._get_times_s(device_name, stream_name)[-1]
      if isinstance(end_time_s, np.ndarray):
        end_time_s = end_time_s[0]
      return end_time_s
    except IndexError:
      return None
  
  # Get the duration of data recorded so far.
  def get_duration_s(self, device_name: str, stream_name: str) -> float:
    start_time_s = self.get_start_time_s(device_name, stream_name)
    end_time_s = self.get_end_time_s(device_name, stream_name)
    if end_time_s is not None and start_time_s is not None:
      return end_time_s - start_time_s
    return None

  # Get data.
  # Can get all data, or only data to/from a specified timestep.
  # @starting_index the desired first index to return, or None to start at the beginning.
  # @ending_index the desired ending index to return, or None to go until the end.
  #   If provided, will be used with standard Python list indexing,
  #    so the provided index will be *excluded* from the returned data.
  #   Note that it can also be negative, in accordance with standard Python list indexing.
  # @starting_time_s and @ending_time_s are alternatives to starting_index and ending_index.
  #   If not None, will be used instead of the corresponding index argument.
  # If no data exists based on the specified timesteps, will return None.
  # @param return_deepcopy Whether to return a deep copy of the data (safer)
  #   or to potentially include pointers to the data record (faster).
  def get_data(self, 
               device_name: str, 
               stream_name: str,
               starting_index: int = None, 
               ending_index: int = None,
               starting_time_s: float = None, 
               ending_time_s: float = None,
               return_deepcopy: bool = True) -> dict[str, np.ndarray]:
    # Convert desired times to indexes if applicable.
    if starting_time_s is not None:
      starting_index = self._get_index_for_time_s(device_name, stream_name, starting_time_s, target_before=False)
      if starting_index is None:
        return None
    if ending_time_s is not None:
      ending_index = self._get_index_for_time_s(device_name, stream_name, ending_time_s, target_before=True)
      if ending_index is None:
        return None
      else:
        ending_index += 1 # since will use as a list index and thus exclude the specified index
    # Update default starting/ending indexes.
    if starting_index is None:
      starting_index = 0
    if ending_index is None:
      ending_index = self.get_num_timesteps(device_name, stream_name)

    # Get the desired subset of data.
    # Note that this also creates a copy of each array, so the returned data remains static as new data is collected.
    res = dict([(key, values[starting_index:ending_index]) for (key, values) in self._data[device_name][stream_name].items()])

    # Return the result
    if len(list(res.values())[0]) == 0:
      return None
    elif return_deepcopy:
      return copy.deepcopy(res)
    else:
      return res
        
  # Helper to get the time array for a specified stream.
  # Will use the streaming data or the loaded log data as applicable.
  def _get_times_s(self, 
                   device_name: str, 
                   stream_name: str) -> np.ndarray:
    return self._data[device_name][stream_name]['time_s']
    
  # Helper to get the sample index that best corresponds to the specified time.
  # Will return the index of the last sample that is <= the specified time
  #  or the index of the first sample that is >= the specified time.
  def _get_index_for_time_s(self, 
                            device_name: str, 
                            stream_name: str, 
                            target_time_s: float, 
                            target_before: bool = True) -> np.ndarray:
    # Get the sample times streamed so far, or loaded from existing logs.
    times_s = np.array(self._get_times_s(device_name, stream_name))
    # Get the last sample before the specified time.
    if target_before:
      indexes = np.argwhere(times_s <= target_time_s)
      return np.max(indexes) if indexes.size > 0 else None
    # Get the first sample after the specified time.
    else:
      indexes = np.argwhere(times_s >= target_time_s)
      return np.min(indexes) if indexes.size > 0 else None

  # Get/set metadata
  def get_metadata(self, 
                   device_name: str = None, 
                   only_str_values: bool = False) -> OrderedDict:
    # Get metadata for all devices or for the specified device.
    if device_name is None:
      metadata = self._metadata
    elif device_name in self._metadata:
      metadata = self._metadata[device_name]
    else:
      metadata = OrderedDict()

    # Add the class name.
    class_name = type(self).__name__
    if device_name is None:
      for device_name_toUpdate in metadata:
        metadata[device_name_toUpdate][self.metadata_class_name_key] = class_name
    else:
      metadata[self.metadata_class_name_key] = class_name

    # Convert values to strings if desired.
    if only_str_values:
      metadata = convert_dict_values_to_str(metadata)
    return metadata

  def set_metadata(self, new_metadata: OrderedDict) -> None:
    self._metadata = new_metadata

  def get_num_devices(self) -> int:
    return len(self._streams_info)

  # Get the names of streaming devices
  def get_device_names(self) -> list[str]:
    return list(self._streams_info.keys())

  # Rename a device (and keep the device indexing order the same).
  # If the name already exists, will not do anything.
  def rename_device(self, old_device_name, new_device_name) -> None:
    self._streams_info = rename_dict_key(self._streams_info, old_device_name, new_device_name)
    self._metadata = rename_dict_key(self._metadata, old_device_name, new_device_name)
    self._data = rename_dict_key(self._data, old_device_name, new_device_name)

  # Get the names of streams.
  # If device_name is None, will assume streams are the same for every device.
  def get_stream_names(self, device_name: str = None) -> list[str]:
    if device_name is None:
      device_name = self.get_device_names()[0]
    return list(self._streams_info[device_name].keys())

  # Get information about a stream.
  # Returned dict will have keys data_type, sample_size, sampling_rate_hz, timesteps_before_solidified, extra_data_info
  def get_stream_info(self, device_name: str, stream_name: str) -> OrderedDict:
    return self._streams_info[device_name][stream_name]

  # Get all information about all streams.
  def get_all_stream_infos(self) -> OrderedDict:
    return copy.deepcopy(self._streams_info)

  # Get a list of values for a particular type of stream info (decoupled from device/stream names).
  # info_key can be data_type, sample_size, sampling_rate_hz, timesteps_before_solidified, extra_data_info
  def get_stream_attribute_allStreams(self, stream_attribute) -> list[np.ndarray]:
    infos = []
    for (device_name, device_info) in self._streams_info.items():
      for (stream_name, stream_info) in device_info.items():
        infos.append(stream_info[stream_attribute])
    return infos

  # Get a list of data keys associated with a stream.
  # Will include 'data', 'time_s', 'time_str', and any extra ones defined.
  def get_stream_data_keys(self, device_name: str, stream_name: str) -> list[str]:
    return list(self._data[device_name][stream_name].keys())
