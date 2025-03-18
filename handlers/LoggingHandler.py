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

from abc import ABC, abstractmethod
from collections import OrderedDict
from io import TextIOWrapper
import os
import time
import wave

import cv2
import h5py
import numpy as np
from streams.Stream import Stream
from utils.dict_utils import convert_dict_values_to_str
from utils.time_utils import get_time_str


##############################################################################################
##############################################################################################
# If using the periodic option, latest data will be fetched from the streamers
#   and then written in a separate thread to avoid undue performance impact.
#   Any leftover data once the program is stopped will be flushed to the files.
# If using the periodic option, can optionally clear old data from memory to reduce RAM usage.
#   Data will then be cleared each time new data is logged, 
#     unless all data is expected to be written at the end.
#   Will treat video/audio data separately, so can choose to stream/clear 
#     non-AV data but dump AV data or vice versa.
# Logging currently supports CSV, HDF5, AVI/MP4, and WAV files.
#   If using HDF5, a single file will be created for all of the SensorStreamers.
#   If using CSV, a separate file will be created for each SensorStreamer.
#     N-D data will be unwrapped so that each entry is its own column.
#   Videos can be saved as AVI or MP4 files.
#   Audio can be saved as WAV files.
# Note that the is_video / is_audio flags of each stream will be used to identify video/audio.
#   Classes with audio streams will also require a method get_audioStreaming_info()
#     that returns a dict with keys num_channels, sample_width, sampling_rate.
#   See MicrophoneStreamer for an example of defining these attributes.
##############################################################################################
##############################################################################################
class LoggerInterface(ABC):
  @abstractmethod
  def _set_state(self, state) -> None:
    pass

  @abstractmethod
  def _initialize(self, streams: OrderedDict[str, Stream]) -> None:
    pass

  @abstractmethod
  def _log_data(self) -> None:
    pass

  @abstractmethod
  def _is_to_stream(self) -> bool:
    pass

  @abstractmethod
  def _is_to_dump(self) -> bool:
    pass

  @abstractmethod
  def _start_stream_logging(self) -> None:
    pass

  @abstractmethod
  def _stop_stream_logging(self) -> None:
    pass

  @abstractmethod
  def _start_dump_logging(self) -> None:
    pass

  @abstractmethod
  def _wait_till_flush(self) -> None:
    pass


class BrokerState(ABC):
  def __init__(self, context: LoggerInterface):
    self._context = context
    self._is_continue_fsm = True

  @abstractmethod
  def run(self) -> None:
    pass

  def is_continue(self) -> bool:
    return self._is_continue_fsm


class StartState(BrokerState):
  def __init__(self, context, streams: OrderedDict[str, Stream]):
    super().__init__(context)
    self._context._initialize(streams)

  def run(self) -> None:
    self._context._set_state(StreamState(self._context))


class StreamState(BrokerState):
  def __init__(self, context):
    super().__init__(context)
    # Prepare stream-logging.
    if self._context._is_to_stream():
      self._context._start_stream_logging()

  def run(self) -> None:
    self._context._log_data()
    self._context._set_state(DumpState(self._context))


class DumpState(BrokerState):
  def __init__(self, context):
    super().__init__(context)
    # Dump write files at the end of the trial for data that hadn't been streamed.
    #   Assumes all intermediate recorded data can fit in memory.
    if self._context._is_to_dump():
      self._context._start_dump_logging()

  def run(self) -> None:
    # Until top-level module's main thread indicated that it finished producing data,
    #   periodically sleep the thread to yield the CPU.
    self._context._wait_till_flush()
    # When experiment ended, write data once and wrap up.
    #   Use the end log time to not overwrite written streamed data with empty dumped files.
    self._context._log_data()
    self._is_continue_fsm = False


class Logger(LoggerInterface):
  def __init__(self,
               log_tag: str,
               log_dir: str,
               stream_csv: bool = False,
               stream_hdf5: bool = False,
               stream_video: bool = False,
               stream_audio: bool = False,
               dump_csv: bool = False, 
               dump_hdf5: bool = False, 
               dump_video: bool = False, 
               dump_audio: bool = False,
               videos_in_csv: bool = False, 
               videos_in_hdf5: bool = False, 
               videos_format: str = "avi",
               videos_is_use_intel_api: bool = False,
               audio_in_csv: bool = False, 
               audio_in_hdf5: bool = False, 
               audio_format: str = "wav",
               stream_period_s: float = 30.0,
               clear_logged_data_from_memory: bool = True,
               **_):

    # Record the configuration options.
    self._stream_hdf5 = stream_hdf5
    self._stream_csv = stream_csv
    self._stream_video = stream_video
    self._stream_audio = stream_audio
    self._stream_period_s = stream_period_s
    self._clear_logged_data_from_memory = clear_logged_data_from_memory
    self._dump_hdf5 = dump_hdf5
    self._dump_csv = dump_csv
    self._dump_video = dump_video
    self._dump_audio = dump_audio
    self._videos_in_csv = videos_in_csv
    self._videos_in_hdf5 = videos_in_hdf5
    self._videos_format = videos_format
    self._videos_is_use_intel_api = videos_is_use_intel_api
    self._audio_in_csv = audio_in_csv
    self._audio_in_hdf5 = audio_in_hdf5
    self._audio_format = audio_format
    self._log_tag = log_tag
    self._log_dir = log_dir

    # Initialize the logging writers.
    self._csv_writers = None
    self._csv_writer_metadata = None
    self._hdf5_file = None
    self._video_writers = None
    self._audio_writers = None
    # Create the log directory if needed.
    if self._stream_csv or self._stream_hdf5 or self._stream_video or self._stream_audio \
        or self._dump_csv or self._dump_hdf5 or self._dump_video or self._dump_audio:
      os.makedirs(self._log_dir, exist_ok=True)

    # Initialize variables that will guide the thread that will do stream/dump logging of data available in the Stream objects.
    #   Main thread will listen to the sockets and put files to the Stream objects.
    self._is_streaming = None   # whether periodic writing is active
    self._is_flush = None       # whether remaining data at the end should now be flushed
    self._is_finished = None    # whether the logging loop is finished and all data was flushed


  def __call__(self, streams: OrderedDict[str, Stream]) -> None:
    self._state = StartState(self, streams)
    # Run continuously, ignoring Ctrl+C interrupt, until owner Node commands an exit.
    while self._state.is_continue():
      try:
        self._state.run()
      except KeyboardInterrupt:
        print("Caught Ctrl+C in %s Logger"%self._log_tag, flush=True)
    print("%s Logger safely exited."%self._log_tag, flush=True)


  # Stop logging.
  # Will stop stream-logging, if it is active.
  # Will trigger data dump, if configured.
  # Node pushing data to the Stream should stop adding new data before cleaning up Logger. 
  def cleanup(self):
    # Stop stream-logging and wait for it to finish.
    self._stop_stream_logging()
    self._log_stop_time_s = time.time()


  ############################
  ###### FSM OPERATIONS ######
  ############################
  # Initializes files and indices for write pointer tracking.
  def _initialize(self, streams: OrderedDict[str, Stream]):
    # Create Stream objects for all desired sensors we are to subscribe to from classes_to_log
    self._hdf5_log_length_increment = 10000
    self._streams = streams
    self._next_data_indexes: OrderedDict[str, OrderedDict] = OrderedDict()
    self._timesteps_before_solidified: OrderedDict[str, OrderedDict] = OrderedDict()
    self._next_data_indexes_hdf5: OrderedDict[str, OrderedDict] = OrderedDict()
    for tag in streams.keys():
      # Initialize a record of what indices have been logged,
      #  and how many timesteps to stay behind of the most recent step (if needed).
      self._next_data_indexes.setdefault(tag, OrderedDict())
      self._timesteps_before_solidified.setdefault(tag, OrderedDict())
      # Each time an HDF5 dataset reaches its limit,
      #  its size will be increased by the following amount.
      self._next_data_indexes_hdf5.setdefault(tag, OrderedDict())


  def _set_state(self, state: BrokerState) -> None:
    self._state = state


  def _is_to_stream(self) -> bool:
    return self._stream_csv or self._stream_hdf5 or self._stream_video or self._stream_audio


  def _is_to_dump(self) -> bool:
    return self._dump_csv or self._dump_hdf5 or self._dump_video or self._dump_audio


  def _start_stream_logging(self) -> None:
    log_start_time_s = time.time()
    # Set up CSV/HDF5 file writers for stream-logging if desired.
    if self._stream_csv:
      self._init_writing_csv(log_start_time_s)
    if self._stream_hdf5:
      self._init_writing_hdf5(log_start_time_s)
    if self._stream_video:
      self._init_writing_videos(log_start_time_s)
    if self._stream_audio:
      self._init_writing_audio(log_start_time_s)
    self._init_log_indices()
    self._is_streaming = True
    self._is_flush = False
    self._is_finished = False


  # Helper to stop the stream-logging thread to periodically write data.
  # Will write any outstanding data,
  #  and will log any metadata associated with the streamers.
  # Will wait for the thread to finish before returning.
  def _stop_stream_logging(self):
    self._is_streaming = False
    self._is_flush = True


  def _start_dump_logging(self) -> None:
    if self._dump_csv:
      self._init_writing_csv(self._log_stop_time_s)
    if self._dump_hdf5:
      self._init_writing_hdf5(self._log_stop_time_s)
    if self._dump_video:
      self._init_writing_videos(self._log_stop_time_s)
    if self._dump_audio:
      self._init_writing_audio(self._log_stop_time_s)
    # Log all data.
    # Will basically enable periodic stream-logging,
    #  but will set self._is_flush and self._is_streaming such that
    #  it seems like the experiment ended and just a final flush is required.
    #  This will cause the stream-logging in self._log_data()
    #  to fetch and write any outstanding data, which is all data since
    #  none is written yet.  It will then exit after the single write.
    # Pretend like the dumping options are actually streaming options.
    self._stream_csv = self._dump_csv
    self._stream_hdf5 = self._dump_hdf5
    self._stream_video = self._dump_video
    self._stream_audio = self._dump_audio
    # Clear the is_finished flag in case dump is run after stream so the log loop can run once to flush all logged data that wasn't stream-logged.
    self._is_finished = False
    # Initialize indexes and log all of the data.
    self._init_log_indices()


  def _wait_till_flush(self) -> None:
    while not self._is_flush: 
      time.sleep(self._stream_period_s)


  #############################
  ###### FILE OPERATIONS ######
  #############################
  # Helper to get a base prefix for logging filenames.
  # Will indicate the logging start time and whether it's streaming or post-experiment.
  def _get_filename_base(self, log_time_s: float):
    log_datetime_str = get_time_str(log_time_s, '%Y-%m-%d_%H-%M-%S')
    filename_base = '%s_%s' % (log_datetime_str, self._log_tag)
    return filename_base


  # Initialize the data indices to fetch for logging.
  # Will record the next data indices that should be fetched for each stream,
  #  and the number of timesteps that each streamer needs before data is solidified.
  def _init_log_indices(self):
    for (streamer_name, stream) in self._streams.items():
      for (device_name, device_info) in stream.get_stream_info_all().items():
        self._next_data_indexes[streamer_name][device_name] = OrderedDict()
        self._timesteps_before_solidified[streamer_name][device_name] = OrderedDict()
        for (stream_name, stream_info) in device_info.items():
          self._next_data_indexes[streamer_name][device_name][stream_name] = 0
          self._timesteps_before_solidified[streamer_name][device_name][stream_name] = stream_info['timesteps_before_solidified']


  # Create and initialize CSV files.
  # Will have a separate file for each stream of each device.
  # Currently assumes that device names are unique across all streamers.
  def _init_writing_csv(self, log_time_s: float):
    filename_base = self._get_filename_base(log_time_s=log_time_s)

    # Open a writer for each CSV data file.
    csv_writers = OrderedDict([(k, OrderedDict()) for k in self._streams.keys()])
    for (streamer_name, streamer) in self._streams.items():
      for (device_name, device_info) in streamer.get_stream_info_all().items():
        csv_writers[streamer_name][device_name] = OrderedDict()
        for (stream_name, stream_info) in device_info.items():
          # Skip saving videos in a CSV.
          if stream_info['is_video'] and not self._videos_in_csv:
            continue
          # Skip saving audio in a CSV.
          if stream_info['is_audio'] and not self._audio_in_csv:
            continue
          filename_csv = '%s_%s_%s.csv' % (filename_base, device_name, stream_name)
          filepath_csv = os.path.join(self._log_dir, filename_csv)
          csv_writers[streamer_name][device_name][stream_name] = open(filepath_csv, 'w')

    # Open a writer for a CSV metadata file.
    filename_csv = '%s__metadata.csv' % (filename_base)
    filepath_csv = os.path.join(self._log_dir, filename_csv)
    csv_writer_metadata = open(filepath_csv, 'w')

    # Write CSV headers.
    csv_headers = ['Timestamp [s]']
    for (streamer_name, streamer) in self._streams.items():
      for (device_name, stream_writers) in csv_writers[streamer_name].items():
        for (stream_name, stream_writer) in stream_writers.items():
          stream_writer.write(','.join(csv_headers))
          # First check if custom header titles have been specified.
          stream_info = streamer.get_stream_info_all()[device_name][stream_name]
          sample_size = stream_info['sample_size']
          if isinstance(stream_info['data_notes'], dict) and Stream.metadata_data_headings_key in stream_info['data_notes']:
            data_headers = stream_info['data_notes'][Stream.metadata_data_headings_key]
          else:
            # Write a number of data headers based on how many values are in each data sample.
            # Each sample may be a matrix that will be unwrapped into columns,
            #  so label headers as i-j where i is the original matrix row
            #  and j is the original matrix column (and if more than 2D keep adding more).
            data_headers = []
            subs = np.unravel_index(range(0,np.prod(sample_size)), sample_size)
            subs = np.stack(subs).T
            for header_index in range(subs.shape[0]):
              header = 'Data Entry '
              for sub_index in range(subs.shape[1]):
                header += '%d-' % subs[header_index, sub_index]
              header = header.strip('-')
              data_headers.append(header)
          stream_writer.write(',')
          stream_writer.write(','.join(data_headers))
          # Append headers for any extra items in the stream.
          for (extra_data_key, extra_data_info) in streamer.get_stream_info(device_name, stream_name)['extra_data_info'].items():
            sample_size = extra_data_info['sample_size']
            if np.prod(sample_size) == 1:
              # Use the specified data key as the header title.
              extra_data_headers = [extra_data_key]
            else:
              # See previous comments about unwrapping matrices into columns.
              subs = np.unravel_index(range(0,np.prod(sample_size)), sample_size)
              subs = np.stack(subs).T
              for header_index in range(subs.shape[0]):
                header = '%s ' % extra_data_key
                for sub_index in range(subs.shape[1]):
                  header += '%d-' % subs[header_index, sub_index]
                header = header.strip('-')
                extra_data_headers.append(header)
            stream_writer.write(',%s' % ','.join(extra_data_headers))

    # Store the writers
    self._csv_writers = csv_writers
    self._csv_writer_metadata = csv_writer_metadata


  # Create and initialize an HDF5 file.
  # Will have a single file for all streams from all devices.
  # Currently assumes that device names are unique across all streamers.
  def _init_writing_hdf5(self, log_time_s: float):
    filename_base = self._get_filename_base(log_time_s=log_time_s)

    # Open an HDF5 file writer
    filename_hdf5 = '%s.hdf5' % filename_base
    filepath_hdf5 = os.path.join(self._log_dir, filename_hdf5)
    num_to_append = 1
    while os.path.exists(filepath_hdf5):
      filename_hdf5 = '%s_%02d.hdf5' % (filename_base, num_to_append)
      filepath_hdf5 = os.path.join(self._log_dir, filename_hdf5)
      num_to_append = num_to_append+1
    hdf5_file = h5py.File(filepath_hdf5, 'w')
    # Create a dataset for each data key of each stream of each device.
    for (streamer_name, stream) in self._streams.items():
      for (device_name, device_info) in stream.get_stream_info_all().items():
        device_group = hdf5_file.create_group(device_name)
        self._next_data_indexes_hdf5[streamer_name][device_name] = OrderedDict()
        for (stream_name, stream_info) in device_info.items():
          # Skip saving videos in the HDF5.
          if stream_info['is_video'] and not self._videos_in_hdf5:
            continue
          # Skip saving audio in the HDF5.
          if stream_info['is_audio'] and not self._audio_in_hdf5:
            continue
          stream_group = device_group.create_group(stream_name)
          self._next_data_indexes_hdf5[streamer_name][device_name][stream_name] = 0
          # Create a dataset for each item in the stream.
          for data_key in stream.get_stream_data_keys(device_name, stream_name):
            # The main data has specifications defined by stream_info.
            if data_key == 'data':
              sample_size = stream_info['sample_size']
              data_type = stream_info['data_type']
            # Any extra data has its specification in the extra stream info.
            elif data_key in stream_info['extra_data_info']:
              sample_size = stream_info['extra_data_info'][data_key]['sample_size']
              data_type = stream_info['extra_data_info'][data_key]['data_type']
            # The time fields will have their specifications hard-coded below.
            elif data_key == 'time_s':
              sample_size = [1]
              data_type = 'float64'
            else:
              raise KeyError('Unknown data specification for %s.%s.%s' % (device_name, stream_name, data_key))
            # Create the dataset!
            stream_group.create_dataset(name=data_key,
                                        shape=(self._hdf5_log_length_increment, *sample_size),
                                        maxshape=(None, *sample_size),
                                        dtype=data_type,
                                        chunks=True)
    # Store the writer.
    self._hdf5_file = hdf5_file


  # Create and initialize video writers.
  def _init_writing_videos(self, log_time_s: float):
    filename_base = self._get_filename_base(log_time_s=log_time_s)

    # Create a video writer for each video stream of each device.
    self._video_writers = OrderedDict([(k, OrderedDict()) for k in self._streams.keys()])
    for (streamer_name, streamer) in self._streams.items():
      for (device_name, device_info) in streamer.get_stream_info_all().items():
        for (stream_name, stream_info) in device_info.items():
          # Skip non-video streams.
          if not stream_info['is_video']:
            continue
          # Create a video writer.
          frame_height = stream_info['sample_size'][0]
          frame_width = stream_info['sample_size'][1]
          fps = stream_info['sampling_rate_hz']
          if self._videos_format.lower() == 'mp4':
            extension = 'mp4'
            fourcc = 'MP4V'
          elif self._videos_format.lower() == 'avi':
            extension = 'avi'
            fourcc = 'MJPG'
          # TODO: try a different codec? for better efficiency and speed of writing and network transmission.
          else:
            raise AssertionError('Unsupported video format %s.  Can be mp4 or avi.' % self._videos_format)
          filename_video = '%s_%s_%s.%s' % (filename_base, device_name, stream_name, extension)
          filepath_video = os.path.join(self._log_dir, filename_video)
          writer_params = {
            'filename'  : filepath_video,
            'fourcc'    : cv2.VideoWriter_fourcc(*fourcc),
            'fps'       : fps,
            'frameSize' :(frame_width, frame_height)
          }
          if self._videos_is_use_intel_api: writer_params['apiPreference'] = cv2.CAP_INTEL_MFX
          video_writer = cv2.VideoWriter(**writer_params)
          # Store the writer.
          if device_name not in self._video_writers[streamer_name]:
            self._video_writers[streamer_name][device_name] = {}
          self._video_writers[streamer_name][device_name][stream_name] = video_writer


  # Create and initialize audio writers.
  def _init_writing_audio(self, log_time_s: float):
    filename_base = self._get_filename_base(log_time_s=log_time_s)

    # Create an audio writer for each audio stream of each device.
    self._audio_writers = OrderedDict([(k, OrderedDict()) for k in self._streams.keys()])
    for (streamer_name, stream) in self._streams.items():
      for (device_name, streams_info) in stream.get_stream_info_all().items():
        for (stream_name, stream_info) in streams_info.items():
          # Skip non-audio streams.
          if not stream_info['is_audio']:
            continue
          # Create an audio writer.
          filename_audio = '%s_%s_%s.wav' % (filename_base, device_name, stream_name)
          filepath_audio = os.path.join(self._log_dir, filename_audio)
          audioStreaming_info = stream.get_audioStreaming_info()
          audio_writer = wave.open(filepath_audio, 'wb')
          audio_writer.setnchannels(audioStreaming_info['num_channels'])
          audio_writer.setsampwidth(audioStreaming_info['sample_width'])
          audio_writer.setframerate(audioStreaming_info['sampling_rate'])
          # Store the writer.
          if device_name not in self._audio_writers[streamer_name]:
            self._audio_writers[streamer_name][device_name] = {}
          self._audio_writers[streamer_name][device_name][stream_name] = audio_writer


  # Write provided data to the CSV logs.
  # Note that this can be called during streaming (periodic writing)
  #  or during post-experiment dumping.
  # @param new_data is a dict with 'data', 'time_s',
  #   and any extra fields specified by the streamer.
  #   The data may contain multiple timesteps (each value may be a list).
  def _write_data_csv(self, 
                      streamer_name: str, 
                      device_name: str, 
                      stream_name: str, 
                      new_data: dict):
    stream: Stream = self._streams[streamer_name]
    num_new_entries = len(new_data['data'])
    try:
      stream_writer: TextIOWrapper = self._csv_writers[streamer_name][device_name][stream_name]
    except KeyError: # a writer was not created for this stream
      return
    for entry_index in range(num_new_entries):
      # Create a list of column entries to write.
      # Note that they should match the heading order in _init_writing_csv().
      to_write = []
      to_write.append(new_data['time_s'][entry_index])
      data_toWrite = new_data['data'][entry_index]
      if isinstance(data_toWrite, (list, tuple)):
        to_write.extend(data_toWrite)
      elif isinstance(data_toWrite, np.ndarray):
        to_write.extend(list(np.atleast_1d(data_toWrite.reshape(1, -1).squeeze())))
      else:
        to_write.append(data_toWrite)
      for extra_data_header in stream.get_stream_info(device_name, stream_name)['extra_data_info'].keys():
        to_write.append(new_data[extra_data_header][entry_index])
      # Write the new row
      stream_writer.write('\n')
      stream_writer.write(','.join([str(x) for x in to_write]))
    stream_writer.flush()


  # Write provided data to the HDF5 file.
  # Note that this can be called during streaming (periodic writing)
  #  or during post-experiment dumping.
  # @param new_data is a dict with 'data', probably 'time_s',
  #   and any extra fields specified by the streamer.
  #   The data may contain multiple timesteps (each value may be a list).
  def _write_data_hdf5(self, 
                       streamer_name: str, 
                       device_name: str, 
                       stream_name: str, 
                       new_data: dict):
    try:
      stream_group = self._hdf5_file['/'.join([device_name, stream_name])]
    except KeyError: # a dataset was not created for this stream
      return
    # Get the amount of new data to write and the index to start writing it.
    num_new_entries = len(new_data['data'])
    starting_index = self._next_data_indexes_hdf5[streamer_name][device_name][stream_name]
    num_old_entries = starting_index
    # Write the data!
    for data_key in new_data.keys():
      dataset = stream_group[data_key]
      # Expand the dataset if needed.
      while len(dataset) < num_old_entries + num_new_entries:
        dataset.resize((len(dataset) + self._hdf5_log_length_increment, *dataset.shape[1:]))
      # Write the new entries.
      ending_index = starting_index + num_new_entries - 1
      data_toWrite = new_data[data_key]
      if dataset.dtype.char == 'S':
        if len(data_toWrite) > 0 and isinstance(data_toWrite[0], (list, tuple)):
          data_toWrite = [[n.encode("ascii", "ignore") for n in data_row] for data_row in data_toWrite]
        else:
          data_toWrite = [n.encode("ascii", "ignore") for n in data_toWrite]
      dataset[starting_index:ending_index+1,:] = np.array(data_toWrite).reshape((-1, *dataset.shape[1:]))
    self._hdf5_file.flush()
    # Update the next starting index to use.
    next_starting_index = starting_index + num_new_entries
    self._next_data_indexes_hdf5[streamer_name][device_name][stream_name] = next_starting_index


  # Write provided data to the video files.
  # Note that this can be called during streaming (periodic writing)
  #  or during post-experiment dumping.
  # @param new_data is a dict with 'data' (all other keys will be ignored).
  #   The 'data' entry must contain raw frames as a matrix.
  #   The data may contain multiple timesteps (a list of matrices).
  def _write_data_video(self,
                        streamer_name: str,
                        device_name: str,
                        stream_name: str,
                        new_data: dict):
    stream = self._streams[streamer_name]
    try:
      video_writer: cv2.VideoWriter = self._video_writers[streamer_name][device_name][stream_name]
      for frame in new_data['data']:
        # Assume the data is the frame.
        # If a custom video format was specified, convert the frame before writing it to file. 
        frame = cv2.imdecode(frame, cv2.IMREAD_UNCHANGED)
        if stream._streams_info[device_name][stream_name]['data_notes'] and \
          'color_format' in stream._streams_info[device_name][stream_name]['data_notes']:
            frame = cv2.cvtColor(frame,
                                 stream._streams_info[device_name][stream_name]['data_notes']['color_format'])
        video_writer.write(frame)
    except KeyError: # a writer was not created for this stream
      return


  # Write provided data to the audio files.
  # Note that this can be called during streaming (periodic writing)
  #  or during post-experiment dumping.
  # @param new_data is a dict with 'data' (all other keys will be ignored).
  #   The 'data' entry should be a list of raw audio readings, so it should be
  #    a list of lists (since audio data at each timestep is assumed to be a list, i.e. a chunk).
  def _write_data_audio(self, 
                        streamer_name: str, 
                        device_name: str, 
                        stream_name: str, 
                        new_data: dict):
    stream = self._streams[streamer_name]
    try:
      audio_writer: wave.Wave_write = self._audio_writers[streamer_name][device_name][stream_name]
    except KeyError: # a writer was not created for this stream
      return
    # Assume the data is a list of lists (each entry is a list of chunked audio data).
    if len(new_data['data']) > 0:
      audio_writer.writeframes(b''.join([bytearray(x) for x in new_data['data']]))


  # Write metadata from each streamer to CSV and/or HDF5 files.
  # Will include device-level metadata and any lower-level data notes.
  def _log_metadata(self):
    for (streamer_name, stream) in self._streams.items():
      for (device_name, device_info) in stream.get_stream_info_all().items():
        # Get metadata for this device.
        # To make it HDF5 compatible,
        #  flatten the dictionary and then
        #  prune objects that can't be converted to a string easily.
        device_metadata = stream.get_metadata(device_name=device_name, only_str_values=True)
        device_metadata = convert_dict_values_to_str(device_metadata, preserve_nested_dicts=False)
        # Write the device-level metadata.
        if self._csv_writer_metadata is not None:
          self._csv_writer_metadata.write('\n%s,%s\n' % ('='*25,'='*25))
          self._csv_writer_metadata.write('Device Name,%s' % (device_name))
          self._csv_writer_metadata.write('\n%s,%s' % ('='*25,'='*25))
          for (meta_key, meta_value) in device_metadata.items():
            self._csv_writer_metadata.write('\n')
            self._csv_writer_metadata.write('%s,"%s"' % (str(meta_key), str(meta_value)))
          self._csv_writer_metadata.write('\n')
        if self._hdf5_file is not None:
          device_group = self._hdf5_file['/'.join([device_name])]
          device_group.attrs.update(device_metadata)

        # Get data notes for each stream.
        for (stream_name, stream_info) in device_info.items():
          data_notes = stream_info['data_notes']
          if isinstance(data_notes, dict):
            stream_metadata = data_notes
          else:
            stream_metadata = {'data_notes': data_notes}
          stream_metadata = convert_dict_values_to_str(stream_metadata, preserve_nested_dicts=False)
          # Write the stream-level metadata.
          if self._csv_writer_metadata is not None:
            self._csv_writer_metadata.write('\n')
            self._csv_writer_metadata.write('Stream Name,%s' % (stream_name))
            for (meta_key, meta_value) in stream_metadata.items():
              self._csv_writer_metadata.write('\n')
              self._csv_writer_metadata.write('%s,"%s"' % (str(meta_key), str(meta_value)))
            self._csv_writer_metadata.write('\n')
          if self._hdf5_file is not None:
            try:
              stream_group = self._hdf5_file['/'.join([device_name, stream_name])]
              stream_group.attrs.update(stream_metadata)
            except KeyError: # a writer was not created for this stream
              pass


  # Flush/close CSV, HDF5, and video file writers.
  def _close_files(self):
    # Flush/close all of the CSV writers
    if self._csv_writers is not None:
      for (streamer_name, stream) in self._streams.items():
        for (device_name, stream_writers) in self._csv_writers[streamer_name].items():
          for (stream_name, stream_writer) in stream_writers.items():
            stream_writer.close()
      self._csv_writers = None
      self._csv_writer_metadata = None

    # Flush/close the HDF5 file.
    # Also resize datasets to remove extra empty rows.
    if self._hdf5_file is not None:
      for (streamer_name, stream) in self._streams.items():
        for (device_name, device_info) in stream.get_stream_info_all().items():
          for (stream_name, stream_info) in device_info.items():
            try:
              stream_group = self._hdf5_file['/'.join([device_name, stream_name])]
            except KeyError: # a dataset was not created for this stream
              continue
            starting_index = self._next_data_indexes_hdf5[streamer_name][device_name][stream_name]
            ending_index = starting_index - 1
            for data_key in stream.get_stream_data_keys(device_name, stream_name):
              dataset = stream_group[data_key]
              dataset.resize((ending_index+1, *dataset.shape[1:]))
      self._hdf5_file.close()
      self._hdf5_file = None

    # Flush/close all of the video writers.
    if self._video_writers is not None:
      for (streamer_name, stream) in self._streams.items():
        for (device_name, video_writers) in self._video_writers[streamer_name].items():
          for (stream_name, video_writer) in video_writers.items():
            video_writer.release()
      self._video_writers = None

    # Flush/close all of the audio writers.
    if self._audio_writers is not None:
      for (streamer_name, stream) in self._streams.items():
        for (device_name, audio_writers) in self._audio_writers[streamer_name].items():
          for (stream_name, audio_writer) in audio_writers.items():
            audio_writer.close()
      self._audio_writers = None


  ##########################
  ###### DATA LOGGING ######
  ##########################
  # Poll data from each streamer and log it, either periodically or all at once.
  # The poll period is set by self._stream_period_s.
  # Will loop until self._is_streaming is False, and then
  #  will do one final fetch/log if self._is_flush is True.
  # Usage to periodically poll data from each streamer and log it:
  #   Set self._is_streaming to True and self._is_flush to False
  #     then run this method in a thread.
  #   To finish, set self._is_streaming to False and self._is_flush to True.
  # Usage to log all available data once:
  #   Set self._is_streaming to False and self._is_flush to True
  #     then run this method (in a thread or in the main thread).
  def _log_data(self) -> None:
    # Used to run periodic data writing.
    last_log_time_s = None
    # Set at the beginning of the iteration if _is_flush is externally modified to indicate cleanup and exit,
    #   to catch case where external command to flush happened while some of streamers already saved part of available data.
    is_flush_all_in_current_iteration = False
    while (self._is_streaming or self._is_flush) and not self._is_finished:
      # Wait until it is time to write new data, which is either:
      #  1. This is the first iteration.
      #  2. It has been at least self._stream_period_s since the last write.
      #  3. Periodic logging has been deactivated.
      while (last_log_time_s is not None
            and (time_to_next_period := (last_log_time_s + self._stream_period_s - time.time())) > 0
            and self._is_streaming):
        time.sleep(time_to_next_period)

      if not self._is_streaming and not self._is_flush:
        continue
      # Update the last log time now, before the write actually starts.
      # This will keep the log period more consistent; otherwise, the amount
      #   of time it takes to perform the write would be added to the log period.
      #   This would compound over time, leading to longer delays and more data to write each time.
      #   This becomes more severe as the write duration increases (e.g. videos).
      last_log_time_s = time.time()
      # If the log should be flushed, record that it is happening during this iteration for ALL streamers.
      if self._is_flush:
        is_flush_all_in_current_iteration = True
      # Write new data for each stream of each device of each streamer.
      for (streamer_name, stream) in self._streams.items():
        for (device_name, device_info) in stream.get_stream_info_all().items():
          # self._log_debug('Logging streams for streamer %d device %s' % (streamer_index, device_name))
          for (stream_name, stream_info) in device_info.items():
            # Fetch data starting with the first timestep that hasn't been logged yet,
            #  and ending at the most recent data (or back by a few timesteps
            #  if the streamer may still edit the most recent timesteps).
            starting_index = self._next_data_indexes[streamer_name][device_name][stream_name]
            ending_index = -self._timesteps_before_solidified[streamer_name][device_name][stream_name]
            if self._is_flush: # Flushing everything, so write it even if it would normally need more time to solidify
              ending_index = None
            if ending_index == 0: # no time is needed to solidify, so fetch up to the most recent data
              ending_index = None
            new_data = stream.get_data(device_name, 
                                       stream_name, 
                                       return_deepcopy=False,
                                       starting_index=starting_index, 
                                       ending_index=ending_index)
            # Write any new data to files.
            if new_data is not None:
              if self._stream_csv:
                self._write_data_csv(streamer_name, device_name, stream_name, new_data)
              if self._stream_hdf5:
                self._write_data_hdf5(streamer_name, device_name, stream_name, new_data)
              if self._stream_video:
                self._write_data_video(streamer_name, device_name, stream_name, new_data)
              if self._stream_audio:
                self._write_data_audio(streamer_name, device_name, stream_name, new_data)
              # Update starting indexes for the next write.
              num_new_entries = len(new_data['data'])
              next_starting_index = starting_index + num_new_entries
              # Clear the logged data if desired.
              if stream_info['is_video']:
                logged_data = self._stream_video
                dumping_data = self._dump_video
              elif stream_info['is_audio']:
                logged_data = self._stream_audio
                dumping_data = self._dump_audio
              else:
                logged_data = self._stream_csv or self._stream_hdf5
                dumping_data = self._dump_csv or self._dump_hdf5
              can_clear_data = logged_data and (not dumping_data)
              if self._clear_logged_data_from_memory and can_clear_data:
                stream.clear_data(device_name, stream_name, first_index_to_keep=next_starting_index)
                next_starting_index = 0
              self._next_data_indexes[streamer_name][device_name][stream_name] = next_starting_index
              del(new_data) # should be unnecessary, but maybe it helps free the memory?
      # If stream-logging is disabled, but a final flush had been requested,
      #   record that the flush is complete so streaming can really stop now.
      # Note that it also checks whether the flush was configured to happen for all streamers during this iteration.
      #   Especially if a lot of data was being written (such as with video data),
      #   the self._is_flush flag may have been set sometime during the data writing.
      #   In that case, all streamers would not have known to flush data and some data may be omitted.
      # flushing_log set True when _is_flush was set before any streamer saved its data chunk, to make ure nothing is left behind. 
      if (not self._is_streaming) and self._is_flush and is_flush_all_in_current_iteration:
        self._is_finished = True
        # self._is_flush = False
    # Log metadata.
    self._log_metadata()
    # Save and close the files.
    self._close_files()
