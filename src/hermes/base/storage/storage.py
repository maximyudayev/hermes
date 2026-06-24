############
#
# Copyright (c) 2024-2026 Maxim Yudayev and KU Leuven eMedia Lab
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

from collections import OrderedDict
from io import TextIOWrapper
from subprocess import Popen
import os
import time
import asyncio
import concurrent.futures
import h5py
import numpy as np
from typing import Dict
from multiprocessing.synchronize import Event as _Event

try:
    import ffmpeg
except ImportError as e:
    print(
        e,
        "\nFFmpeg not installed, will crash if you configure streaming of video/audio.",
        flush=True,
    )
try:
    # For Python 3.8+
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    # For Python < 3.8
    from importlib_metadata import PackageNotFoundError, version # type: ignore
try:
    __version__ = version("pysio-hermes")
except PackageNotFoundError:
    __version__ = "NA"

from hermes.base.stream import DataContainer
from hermes.base.storage.storage_interface import StorageInterface
from hermes.base.storage.storage_states import AbstractStorageState, StartState
from hermes.utils.time_utils import init_time, get_time, get_time_str
from hermes.utils.dict_utils import convert_dict_values_to_str
from hermes.utils.types import (
    LoggingSpec,
    DataContainerInfo,
    VideoWriter,
    AudioWriter,
    CsvWriter,
)


class Storage(StorageInterface):
    """Manages IO operations of all stream data.

    Flushes data periodically for continuous operation and clears from memory
    to reduce RAM usage, or all at once if user guarantees enough memory.
    In continuous mode, will flush leftover data once the program is stopped.

    Logs video and audio data with FFmpeg to MKV/MP4 and MP3, respectively.
    Logs all other sensor data in a single hierarchical HDF5 file.
    CSV format is also supported, but discouraged -> creates file per sub-stream.

    If sub-stream elements contain a burst of samples of sample_size,
    will automatically unroll it.

    Will fail if no FFmpeg is installed on the system.
    """

    # Initialize variables that will guide the process that will do stream/dump logging of data available in the `Stream` objects.
    #   Main thread will listen to the sockets and put files to the `Stream` objects.
    _is_streaming: bool  # whether periodic writing is active.
    _is_flush: bool  # whether remaining data at the end should now be flushed.
    _is_finished: bool  # whether the logging loop is finished and all data was flushed.

    # Initialize the logging writers.
    _thread_pool: concurrent.futures.ThreadPoolExecutor
    _hdf5_writer: h5py.File | None = None
    _video_writers: dict[str, VideoWriter] = {}
    _audio_writers: dict[str, AudioWriter] = {}
    _csv_writers: dict[str, CsvWriter] = {}
    _csv_writer_metadata: TextIOWrapper | None = None

    def __init__(
        self,
        log_tag: str,
        spec: LoggingSpec,
        streams: Dict[str, DataContainerInfo],
        is_cleanup_event: _Event,
    ):
        """Constructor of the Storage component responsible for all IO.

        Args:
            log_tag (str): Filename prefix.
            spec (LoggingSpec): Specifies what and how to store to disk.
            streams (Dict[str, StreamInfoDict]): Dictionary of per-stream metadata required
                to rebuild the `Stream` object in the `Storage` subprocess.
            is_cleanup_event (Event): Multiprocessing flag used to indicate by the parent `Node`
                to the `Storage` subprocess to clean up and flush all remaining data to disk.
        """
        self._log_tag = log_tag
        self._spec = spec
        self._is_cleanup_event = is_cleanup_event

        self._streams: Dict[str, DataContainer] = {}
        for node_name, stream_reconstructor in streams.items():
            self._streams[node_name] = DataContainer.create_from_metadata(stream_reconstructor)

        # Create the log directory if needed.
        if self._is_to_stream() or self._is_to_dump():
            os.makedirs(self._spec.log_dir, exist_ok=True)

    def __call__(self) -> None:
        """Callable that runs main FSM loop.

        Runs continuously, ignoring Ctrl+C interrupt, until owner Node triggers an exit.
        """
        init_time(ref_time=self._spec.ref_time_s)
        self._state = StartState(self, self._streams)
        while self._state.is_continue():
            self._state.run()
        print("%s Storage safely exited." % self._log_tag, flush=True)

    def cleanup(self) -> None:
        """Stop stream-logging and wait for it to finish.

        Will stop stream-logging, if it is active.
        Will trigger data dump, if configured.
        Node pushing data to the Stream should stop adding new data before cleaning up Logger.
        """
        self._stop_stream_logging()
        self._log_stop_time_s = get_time()

    ############################
    ###### FSM OPERATIONS ######
    ############################
    def _initialize(self, streams: OrderedDict[str, DataContainer]) -> None:
        self._hdf5_log_length_increment = 10000
        self._streams = streams
        self._timesteps_before_solidified: OrderedDict[
            str, OrderedDict[str, OrderedDict[str, int]]
        ] = OrderedDict()
        self._next_data_indices_hdf5: OrderedDict[
            str, OrderedDict[str, OrderedDict[str, int]]
        ] = OrderedDict()
        for tag in streams.keys():
            # Initialize a record of what indices have been logged,
            #  and how many timesteps to stay behind of the most recent step (if needed).
            self._timesteps_before_solidified.setdefault(tag, OrderedDict())
            # Each time an HDF5 dataset reaches its limit,
            #  its size will be increased by the following amount.
            self._next_data_indices_hdf5.setdefault(tag, OrderedDict())

    def _set_state(self, state: AbstractStorageState) -> None:
        self._state = state

    def _is_to_stream(self) -> bool:
        return (
            self._spec.stream_csv
            or self._spec.stream_hdf5
            or self._spec.stream_video
            or self._spec.stream_audio
        )

    def _is_to_dump(self) -> bool:
        return (
            self._spec.dump_csv
            or self._spec.dump_hdf5
            or self._spec.dump_video
            or self._spec.dump_audio
        )

    def _start_stream_logging(self) -> None:
        num_file_writers: int = 0
        if self._spec.stream_csv:
            num_file_writers += self._init_files_csv()
        if self._spec.stream_hdf5:
            num_file_writers += self._init_files_hdf5()
        if self._spec.stream_video:
            num_file_writers += self._init_files_video()
        if self._spec.stream_audio:
            num_file_writers += self._init_files_audio()
        self._init_log_indices()
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=sum(map(lambda x: x.get_num_bundles(), self._streams.values()))
        )
        self._is_streaming = True
        self._is_flush = False
        self._is_finished = False

    def _stop_stream_logging(self) -> None:
        self._is_streaming = False
        self._is_flush = True

    def _start_dump_logging(self) -> None:
        num_writers: int = 0
        if self._spec.dump_csv:
            num_writers += self._init_files_csv()
        if self._spec.dump_hdf5:
            num_writers += self._init_files_hdf5()
        if self._spec.dump_video:
            num_writers += self._init_files_video()
        if self._spec.dump_audio:
            num_writers += self._init_files_audio()
        # Log all data.
        # Will basically enable periodic stream-logging,
        #   but will set self._is_flush and self._is_streaming such that
        #   it seems like the experiment ended and just a final flush is required.
        #   This will cause the stream-logging in self._log_data()
        #   to fetch and write any outstanding data, which is all data since
        #   none is written yet.  It will then exit after the single write.
        # Pretend like the dumping options are actually streaming options.
        self._spec.stream_csv = self._spec.dump_csv
        self._spec.stream_hdf5 = self._spec.dump_hdf5
        self._spec.stream_video = self._spec.dump_video
        self._spec.stream_audio = self._spec.dump_audio
        # Clear the is_finished flag in case dump is run after stream so the log loop
        #   can run once to flush all logged data that wasn't stream-logged.
        self._is_finished = False
        # Initialize indices and log all of the data.
        self._init_log_indices()
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=sum(map(lambda x: x.get_num_bundles(), self._streams.values()))
        )

    def _wait_till_flush(self) -> None:
        while not self._is_flush:
            time.sleep(self._spec.stream_period_s)

    def _release_thread_pool(self) -> None:
        self._thread_pool.shutdown()

    #############################
    ###### FILE OPERATIONS ######
    #############################
    def _init_log_indices(self) -> None:
        """Initialize the data indices to fetch for logging

        Will record the next data indices that should be fetched for each stream,
        and the number of timesteps that each streamer needs before data is solidified.
        """
        for node_name, container in self._streams.items():
            for bundle_name, bundle_info in container.get_info_all().items():
                self._timesteps_before_solidified[node_name][bundle_name] = OrderedDict()
                for channel_name, channel_info in bundle_info.channels.items():
                    self._timesteps_before_solidified[node_name][bundle_name][
                        channel_name
                    ] = channel_info.timesteps_before_solidified

    def _init_files_csv(self) -> int:
        """Create and initialize CSV files.

        Will have a separate file for each stream of each device.
        Currently assumes that device names are unique across all streamers.

        Returns:
            int: Number of initialized writers.
        """
        num_writers: int = 0
        for node_name, container in self._streams.items():
            for bundle_name, bundle_info in container.get_info_all().items():
                for channel_name, channel_info in bundle_info.channels.items():
                    # Skip saving video or audio in a CSV.
                    if channel_info.is_video or channel_info.is_audio:
                        continue
                    filename_csv = "%s_%s_%s.csv" % (
                        self._log_tag,
                        bundle_name,
                        channel_name,
                    )
                    filepath_csv = os.path.join(self._spec.log_dir, filename_csv)
                    csv_file = open(filepath_csv, "w")
                    self._csv_writers["/".join(node_name, bundle_name, channel_name)] = (
                        CsvWriter(csv_file, node_name, bundle_name, channel_name)
                    )
                    num_writers += 1

        # Open a writer for a CSV metadata file.
        filename_csv = "%s__metadata.csv" % (self._log_tag)
        filepath_csv = os.path.join(self._spec.log_dir, filename_csv)
        self._csv_writer_metadata = open(filepath_csv, "w")

        # Write CSV headers.
        for csv_file, node_name, bundle_name, channel_name in self._csv_writers.values():
            # First check if custom header titles have been specified.
            channel_info = self._streams[node_name].get_info(bundle_name, channel_name)
            sample_size = channel_info.shm_buffer_metadata.sample_size
            if (
                isinstance(channel_info.data_notes, dict)
                and DataContainer.metadata_data_headings_key in channel_info.data_notes
            ):
                data_headers = channel_info.data_notes[DataContainer.metadata_data_headings_key]
            else:
                # Write a number of data headers based on how many values are in each data sample.
                # Each sample may be a matrix that will be unwrapped into columns,
                #  so label headers as i-j where i is the original matrix row
                #  and j is the original matrix column (and if more than 2D keep adding more).
                data_headers = []
                subs = np.unravel_index(range(0, np.prod(sample_size)), sample_size)
                subs = np.stack(subs).T
                for header_index in range(subs.shape[0]):
                    header = "Data Entry "
                    for sub_index in range(subs.shape[1]):
                        header += "%d-" % subs[header_index, sub_index]
                    header = header.strip("-")
                    data_headers.append(header)
            csv_file.write(",")
            csv_file.write(",".join(data_headers))
        return num_writers

    def _init_files_hdf5(self) -> int:
        """Create and initialize a hierarchical HDF5 file.

        Will have a single file for all streams from all devices.
        Currently assumes that device names are unique across all streamers.

        Returns:
            int: Number of initialized writers.
        """
        filename_hdf5 = "%s.hdf5" % self._log_tag
        filepath_hdf5 = os.path.join(self._spec.log_dir, filename_hdf5)
        num_to_append = 0
        while os.path.exists(filepath_hdf5):
            num_to_append += 1
            filename_hdf5 = "%s_%02d.hdf5" % (self._log_tag, num_to_append)
            filepath_hdf5 = os.path.join(self._spec.log_dir, filename_hdf5)
        self._hdf5_writer = h5py.File(filepath_hdf5, "w")
        # Create a dataset for each data key of each stream of each device.
        for node_name, container in self._streams.items():
            node_group = self._hdf5_writer.create_group(node_name)
            for bundle_name, bundle_info in container.get_info_all().items():
                device_group = node_group.create_group(bundle_name)
                self._next_data_indices_hdf5[node_name][bundle_name] = OrderedDict()
                for channel_name, channel_info in bundle_info.channels.items():
                    # Skip saving video and audio in the HDF5.
                    if channel_info.is_video or channel_info.is_audio:
                        continue
                    self._next_data_indices_hdf5[node_name][bundle_name][channel_name] = 0
                    # The main data has specifications defined by stream_info.
                    sample_size = channel_info.shm_buffer_metadata.sample_size
                    data_type = channel_info.shm_buffer_metadata.data_type
                    # Create the dataset.
                    device_group.create_dataset(
                        name=channel_name,
                        shape=(self._hdf5_log_length_increment, *sample_size),
                        maxshape=(None, *sample_size),
                        dtype=data_type,
                        chunks=True,
                    )
        return 1

    def _init_files_video(self) -> int:
        """Create and initialize video writers, one for each device.

        Will fail if no FFmpeg installed.

        Raises:
            ValueError: When no supported codec specification was provided in config file.

        Returns:
            int: Number of initialized writers.
        """
        if self._spec.video_codec is None:
            raise ValueError(
                "Must provide video codec specification when streaming video."
            )

        num_writers: int = 0
        for node_name, container in self._streams.items():
            for bundle_name, bundle_info in container.get_info_all().items():
                for channel_name, channel_info in bundle_info.channels.items():
                    # Skip non-video streams.
                    if not channel_info.is_video:
                        continue
                    # Create a unique file.
                    filename_base = "%s_%s" % (self._log_tag, bundle_name)
                    filename_video = "%s.mkv" % (filename_base)
                    filepath_video = os.path.join(self._spec.log_dir, filename_video)
                    num_to_append = 0
                    while os.path.exists(filepath_video):
                        num_to_append += 1
                        filename_video = "%s_%02d.mkv" % (filename_base, num_to_append)
                        filepath_video = os.path.join(
                            self._spec.log_dir, filename_video
                        )
                    # Create a video writer.
                    frame_height = channel_info.shm_buffer_metadata.sample_size[0]
                    frame_width = channel_info.shm_buffer_metadata.sample_size[1]
                    fps = channel_info.sampling_rate_hz
                    input_stream_format: str = channel_info.video_format
                    input_stream_pix_fmt: str = channel_info.video_color
                    metadata_dict = {
                        "metadata:g:%d" % i: "%s=%s" % (k, v)
                        for i, (k, v) in enumerate(
                            [
                                ("title", "/".join(self._spec.experiment.values())),
                                (
                                    "date",
                                    get_time_str(self._spec.log_time_s, "%Y-%m-%d"),
                                ),
                                (
                                    "comment",
                                    "HERMES multi-modal data acquisition system recording",
                                ),
                                *map(
                                    lambda tup: ("X%s" % tup[0], tup[1]),
                                    list(self._spec.experiment.items()),
                                ),
                                ("Xencoder", self._spec.video_codec.codec_name),
                                ("Xencoded-by", f"HERMES v{__version__}"),
                            ]
                        )
                    }
                    # Make a subprocess pipe to FFMPEG that streams in our frames and encode them into a video.
                    video_stream = ffmpeg.input(
                        "pipe:",  # type: ignore
                        format=input_stream_format,
                        pix_fmt=input_stream_pix_fmt,  # color format of piped input frames.
                        s="{}x{}".format(
                            frame_width, frame_height
                        ),  # size of frames from the sensor.
                        framerate=fps,
                        cpucount=self._spec.video_codec.num_cpu,
                        **self._spec.video_codec.input_options,
                    )
                    # TODO: use this to stream encoded video into a local file, and also as RTSP stream to the GUI.
                    # video_stream = ffmpeg.filter_multi_output
                    video_stream = ffmpeg.output(
                        video_stream,  # type: ignore
                        filename=filepath_video,
                        vcodec=self._spec.video_codec.codec_name,
                        pix_fmt=self._spec.video_codec.pix_format,
                        cpucount=self._spec.video_codec.num_cpu,  # prevent ffmpeg from suffocating the processor.
                        **self._spec.video_codec.output_options,
                        **metadata_dict,
                    )
                    video_stream = video_stream.global_args("-hide_banner")
                    video_subproc: Popen = ffmpeg.run_async(
                        video_stream, quiet=self._spec.is_quiet, pipe_stdin=True
                    )  # type: ignore
                    # Store the writer.
                    self._video_writers["/".join(node_name, bundle_name, channel_name)] = (
                        VideoWriter(video_subproc, node_name, bundle_name, channel_name)
                    )
                    num_writers += 1
        return num_writers

    def _init_files_audio(self) -> int:
        """[Not implemented] Create and initialize audio writers, one for each device.

        TODO: implement audio streaming info on the `DataContainer` object.

        Will fail if no FFmpeg installed.

        Raises:
            ValueError: When no supported codec specification was provided in config file.

        Returns:
            int: Number of initialized writers.
        """
        if self._spec.audio_codec is None:
            raise ValueError(
                "Must provide audio codec specification when streaming audio."
            )

        num_writers: int = 0
        for node_name, container in self._streams.items():
            for bundle_name, bundle_info in container.get_info_all().items():
                for channel_name, channel_info in bundle_info.channels.items():
                    # Skip non-audio streams.
                    if not channel_info.is_audio:
                        continue
                    # Create a unique file.
                    filename_base = "%s_%s" % (self._log_tag, bundle_name)
                    filename_audio = "%s.mp3" % (filename_base)
                    filepath_audio = os.path.join(self._spec.log_dir, filename_audio)
                    num_to_append = 0
                    while os.path.exists(filepath_audio):
                        num_to_append += 1
                        filename_audio = "%s_%02d.mp3" % (filename_base, num_to_append)
                        filepath_audio = os.path.join(
                            self._spec.log_dir, filename_audio
                        )

                    # Create an audio writer.
                    fps = channel_info.sampling_rate_hz
                    num_channels = channel_info.num_channels
                    input_stream_sample_fmt = channel_info.sample_format

                    metadata_dict = {
                        "metadata:g:%d" % i: "%s=%s" % (k, v)
                        for i, (k, v) in enumerate(
                            [
                                ("title", "/".join(self._spec.experiment.values())),
                                (
                                    "date",
                                    get_time_str(self._spec.log_time_s, "%Y-%m-%d"),
                                ),
                                (
                                    "comment",
                                    "HERMES multi-modal data acquisition system recording",
                                ),
                                *map(
                                    lambda tup: ("X%s" % tup[0], tup[1]),
                                    list(self._spec.experiment.items()),
                                ),
                                ("Xencoder", self._spec.audio_codec.codec_name),
                                ("Xencoded-by", "HERMES"),
                            ]
                        )
                    }
                    # Make a subprocess pipe to FFMPEG that streams in our frames and encode them into an audio.
                    audio_stream = ffmpeg.input(
                        "pipe:",  # type: ignore
                        ar=fps,
                        ac=num_channels,
                        cpucount=self._spec.audio_codec.num_cpu,
                        **self._spec.audio_codec.input_options,
                    )
                    # TODO: use this to stream encoded audio into a local file, and also as RTSP stream to the GUI.
                    # audio_stream = ffmpeg.filter_multi_output
                    audio_stream = ffmpeg.output(
                        audio_stream,  # type: ignore
                        filename=filepath_audio,
                        acodec=self._spec.audio_codec.codec_name,
                        sample_fmt=input_stream_sample_fmt,
                        cpucount=self._spec.audio_codec.num_cpu,  # prevent ffmpeg from suffocating the processor.
                        **self._spec.audio_codec.output_options,
                        **metadata_dict,
                    )
                    audio_stream = audio_stream.global_args("-hide_banner")
                    audio_subproc: Popen = ffmpeg.run_async(
                        audio_stream, quiet=self._spec.is_quiet, pipe_stdin=True
                    )  # type: ignore
                    # Store the writer.
                    self._audio_writers["/".join(node_name, bundle_name, channel_name)] = (
                        AudioWriter(audio_subproc, node_name, bundle_name, channel_name)
                    )
                    num_writers += 1
        return num_writers

    def _log_metadata_csv(self) -> None:
        """Add experiment metadata on the CSV files.

        TODO: validate logic.
        """
        for node_name, container in self._streams.items():
            for bundle_name, bundle_info in container.get_info_all().items():
                # Get data notes for each stream.
                for channel_name, channel_info in bundle_info.channels.items():
                    data_notes = channel_info.data_notes
                    if isinstance(data_notes, dict):
                        container_metadata = data_notes
                    else:
                        container_metadata = {"data_notes": data_notes}

                    container_metadata = convert_dict_values_to_str(
                        container_metadata, preserve_nested_dicts=False
                    )
                    # Write the container-level metadata.
                    if self._csv_writer_metadata is not None:
                        self._csv_writer_metadata.write("\n")
                        self._csv_writer_metadata.write(
                            "Stream Name,%s" % (channel_name)
                        )
                        for meta_key, meta_value in container_metadata.items():
                            self._csv_writer_metadata.write("\n")
                            self._csv_writer_metadata.write(
                                '%s,"%s"' % (str(meta_key), str(meta_value))
                            )
                        self._csv_writer_metadata.write("\n")

    def _log_metadata_hdf5(self) -> None:
        """Add experiment metadata on the HDF5 file."""
        file_metadata = convert_dict_values_to_str(
            {
                **self._spec.experiment,
                "Date": get_time_str(self._spec.log_time_s, "%Y-%m-%d"),
                "Time": get_time_str(self._spec.log_time_s, "%H-%M-%S"),
                "Comment": "HERMES multi-modal data acquisition system recording",
                "Version": __version__,
            },
            preserve_nested_dicts=False,
        )
        if self._hdf5_writer is not None:
            file_group = self._hdf5_writer["/"]
            file_group.attrs.update(file_metadata)
            # Add metadata per stream.
            # Flatten and prune the dictionary to make it HDF5 compatible.
            for node_name, container in self._streams.items():
                # Add the class name.
                container_metadata = convert_dict_values_to_str(
                    {DataContainer.metadata_class_name_key: type(container).__name__},
                    preserve_nested_dicts=False,
                )
                node_group = self._hdf5_writer["/".join([node_name])]
                node_group.attrs.update(container_metadata)
                for bundle_name, bundle_info in container.get_info_all().items():
                    # NOTE: no per-bundle metadata for now.
                    # Get data notes for each channel.
                    for channel_name, channel_info in bundle_info.channels.items():
                        try:
                            channel_group = self._hdf5_writer[
                                "/".join([node_name, bundle_name, channel_name])
                            ]
                            data_notes = channel_info.data_notes
                            if isinstance(data_notes, dict):
                                channel_metadata = data_notes
                            else:
                                channel_metadata = {"Notes": data_notes}
                            channel_metadata = convert_dict_values_to_str(
                                channel_metadata, preserve_nested_dicts=False
                            )
                            channel_group.attrs.update(channel_metadata)
                        except KeyError:  # a writer was not created for this stream.
                            pass

    def _log_metadata_video(self) -> None:
        """Add experiment metadata on the video files.

        Dummy method, metadata is written on instantiation.
        """
        pass

    def _log_metadata_audio(self) -> None:
        """Add experiment metadata on the audio files.

        Dummy method, metadata is written on instantiation.
        """
        pass

    def _log_metadata(self):
        """Convenience method to add metadata to all file types.

        Will include device-level metadata and any lower-level data notes.
        """
        self._log_metadata_csv()
        self._log_metadata_hdf5()
        self._log_metadata_video()
        self._log_metadata_audio()

    def _close_files_hdf5(self) -> None:
        """Flush/close the HDF5 file writer.

        Resizes datasets to remove extra empty rows.
        """
        if self._hdf5_writer is not None:
            for node_name, container in self._streams.items():
                for bundle_name, bundle_info in container.get_info_all().items():
                    for channel_name, channel_info in bundle_info.channels.items():
                        try:
                            dataset: h5py.Dataset = self._hdf5_writer[
                                "/".join([node_name, bundle_name, channel_name])
                            ]  # type: ignore
                        except KeyError:  # a dataset was not created for this stream
                            continue
                        starting_index = self._next_data_indices_hdf5[node_name][
                            bundle_name
                        ][channel_name]
                        ending_index = starting_index - 1
                        dataset.resize((ending_index + 1, *dataset.shape[1:]))
            self._hdf5_writer.close()
            self._hdf5_writer = None

    def _close_files_video(self) -> None:
        """Flush/close the video files writers."""
        for video_writer in self._video_writers.values():
            video_writer.subproc.stdin.close()  # type: ignore
            if self._spec.is_quiet:
                video_writer.subproc.stderr.close()  # type: ignore
                video_writer.subproc.stdout.close()  # type: ignore
            video_writer.subproc.wait()
        self._video_writers = {}

    def _close_files_csv(self) -> None:
        """Flush/close the CSV file writers."""
        for stream_writer in self._csv_writers.values():
            stream_writer.file.close()
        self._csv_writers = {}
        if self._csv_writer_metadata is not None:
            self._csv_writer_metadata.close()
            self._csv_writer_metadata = None

    def _close_files_audio(self) -> None:
        """Flush/close the audio file writers."""
        for audio_writer in self._audio_writers.values():
            audio_writer.subproc.stdin.close()  # type: ignore
            if self._spec.is_quiet:
                audio_writer.subproc.stderr.close()  # type: ignore
                audio_writer.subproc.stdout.close()  # type: ignore
            audio_writer.subproc.wait()
        self._audio_writers = {}

    def _close_files(self) -> None:
        """Convenience method to close all files writers."""
        self._close_files_csv()
        self._close_files_hdf5()
        self._close_files_video()
        self._close_files_audio()

    def _sync_write_hdf5(
        self,
        node_name: str,
        bundle_name: str,
        channel_name: str,
        view: np.ndarray,
    ) -> None:
        """Write provided data to the HDF5 file.

        Args:
            node_name (str): Valid unique tag of the `Node` owning the data.
            bundle_name (str): Valid data bundle name.
            channel_name (str): Valid data channel name.
            view (np.ndarray): View over contiguous memory of a batch of new samples.
        """
        try:
            dataset: h5py.Dataset = self._hdf5_writer[
                "/".join([node_name, bundle_name, channel_name])
            ]  # type: ignore
        except KeyError:  # a dataset was not created for this stream
            return

        num_elements = view.shape[0]
        # Extend the dataset as needed while iterating over the `new_data`.
        start_index = self._next_data_indices_hdf5[node_name][bundle_name][
            channel_name
        ]
        # Expand the dataset if needed.
        if not (start_index + num_elements < len(dataset)):
            dataset.resize(
                (
                    len(dataset)
                    + max(self._hdf5_log_length_increment, num_elements),
                    *dataset.shape[1:],
                )
            )
        dataset[start_index : start_index + num_elements, :] = view
        # Write the new entries.
        # Update the next starting index to use.
        start_index += num_elements
        self._next_data_indices_hdf5[node_name][bundle_name][channel_name] = (
            start_index
        )

        # Flush the file with the new data.
        self._hdf5_writer.flush()

    def _sync_write_video(
        self,
        video_writer: Popen,
        view: np.ndarray,
    ) -> None:
        """Write provided data to the video files.

        Args:
            video_writer (Popen): FFmpeg writer corresponding to the video.
            view (np.ndarray): View over contiguous memory of a batch of new samples.
        """
        video_writer.stdin.write(view)  # type: ignore

    def _sync_write_csv(
        self,
        csv_writer: TextIOWrapper,
        view: np.ndarray,
    ) -> None:
        """Write provided data to the CSV file.

        Args:
            csv_writer (TextIOWrapper): Text file writer corresponding to the stream.
            view (np.ndarray): View over contiguous memory of a batch of new samples.
        """
        # Create a list of column entries to write.
        # Note that they should match the heading order in `_init_writing_csv()`.
        for row in view:
            to_write = view.reshape(1, -1).squeeze()
            # Write the new row.
            csv_writer.write("\n")
            csv_writer.write(",".join([str(x) for x in to_write]))
        csv_writer.flush()

    def _sync_write_audio(
        self,
        audio_writer: Popen,
        view: np.ndarray,
    ) -> None:
        """Write provided data to the audio files.

        Args:
            audio_writer (Popen): FFmpeg writer corresponding to the audio.
            view (np.ndarray): View over contiguous memory of a batch of new samples.
        """
        audio_writer.stdin.write(view)  # type: ignore

    def _write_data(
        self,
        node: DataContainer,
        node_name: str,
        bundle_name: str,
        is_flush: bool,
    ) -> None:
        """Routes channel data from an atomic bundle to the corresponding synchronous writer.
        
        Will synchronously write collected channels data to disk, releasing the atomic bundle at the end.
        """
        for channel_name, view in node.pop(bundle_name, is_flush=is_flush):
            channel_info = node.get_info(bundle_name, channel_name)
            if self._spec.stream_hdf5 and not (channel_info.is_video or channel_info.is_audio):
                self._sync_write_hdf5(
                    node_name=node_name,
                    bundle_name=bundle_name,
                    channel_name=channel_name,
                    view=view,
                )
            elif self._spec.stream_video and channel_info.is_video:
                self._sync_write_video(
                    video_writer=self._video_writers["/".join(node_name, bundle_name, channel_name)],
                    view=view,
                )
            elif self._spec.stream_audio and channel_info.is_audio:
                self._sync_write_audio(
                    audio_writer=self._audio_writers["/".join(node_name, bundle_name, channel_name)],
                    view=view,
                )
            elif self._spec.stream_csv and not (channel_info.is_video or channel_info.is_audio):
                self._sync_write_csv(
                    csv_writer=self._csv_writers["/".join(node_name, bundle_name, channel_name)],
                    view=view,
                )

    async def _write_bundle(
        self,
        node: DataContainer,
        node_name: str,
        bundle_name: str,
        is_flush: bool,
    ):
        """Asynchronously write all data channels of a bundle to file in a coroutine.

        Will launch the coroutine concurrently with other bundles.
        """
        await asyncio.get_event_loop().run_in_executor(
            self._thread_pool,
            lambda: self._write_data(
                node=node,
                node_name=node_name,
                bundle_name=bundle_name,
                is_flush=is_flush,   
            )
        )

    ##########################
    ###### DATA LOGGING ######
    ##########################
    async def _log_data(self) -> None:
        """Trigger release of AsyncIO resources used for writing files.

        Polls data from each `Node` periodically or all at once.

        The poll period is set by `self._stream_period_s`.

        Will loop until `self._is_streaming` is False, and then
        will do one final fetch/log if `self._is_flush` is True.

        Assert `self._is_streaming` and deassert `self._is_flush` for streaming.
            To finish, deassert `self._is_streaming` to False and assert `self._is_flush`.

        Deassert `self._is_streaming` and assert `self._is_flush` to dump record.
            The thread will be inactive until terminated.
            User is responsible to provision sufficient memory.
        """
        last_log_time_s = None
        # Set at the beginning of the iteration if `_is_flush` is externally modified to indicate cleanup and exit,
        #   to catch case where external command to flush happened while some of streamers already saved part of available data.
        is_flush_all_in_current_iteration = False
        is_cleanup_triggered = False

        while (self._is_streaming or self._is_flush) and not self._is_finished:
            if self._is_cleanup_event.is_set() and not is_cleanup_triggered:
                is_cleanup_triggered = True
                self.cleanup()

            # Wait until it is time to write new data, which is either:
            #  1. This is the first iteration.
            #  2. It has been at least `self._stream_period_s` since the last write.
            #  3. Periodic logging has been deactivated.
            while (
                last_log_time_s is not None
                and (
                    time_to_next_period := (
                        last_log_time_s + self._spec.stream_period_s - get_time()
                    )
                )
                > 0
                and self._is_streaming
            ):
                # Will wake up periodically to check if the experiment had been ended.
                #   Will proceed only if time for next logging or if experiment ended.
                await asyncio.sleep(min(1, time_to_next_period))

            # If running `Storage` in dump mode, wait until `_is_flush` is set externally.
            if not self._is_streaming and not self._is_flush:
                continue

            # Update the last log time now, before the write actually starts.
            # This will keep the log period more consistent; otherwise, the amount
            #   of time it takes to perform the write would be added to the log period.
            #   This would compound over time, leading to longer delays and more data to write each time.
            #   This becomes more severe as the write duration increases (e.g. videos).
            last_log_time_s = get_time()
            # If the log should be flushed, record that it is happening during this iteration for ALL streamers.
            if self._is_flush:
                is_flush_all_in_current_iteration = True

            tasks = []
            # Execute all data bundles writing concurrently.
            for node_name, container in self._streams.items():
                for bundle_name, bundle_info in container.get_info_all().items():
                    tasks.append(
                        self._write_bundle(
                            node=container,
                            node_name=node_name,
                            bundle_name=bundle_name,
                            is_flush=is_flush_all_in_current_iteration,
                        )
                    )
            await asyncio.gather(*tasks)
            # If stream-logging is disabled, but a final flush had been requested,
            #   record that the flush is complete so streaming can really stop now.
            # Note that it also checks whether the flush was configured to happen for all streamers during this iteration.
            #   Especially if a lot of data was being written (such as with video data),
            #   the `self._is_flush` flag may have been set sometime during the data writing.
            #   In that case, all streamers would not have known to flush data and some data may be omitted.
            # flushing_log set True when `self._is_flush` was set before any streamer saved its data chunk,
            #   to make ure nothing is left behind.
            if (
                (not self._is_streaming)
                and self._is_flush
                and is_flush_all_in_current_iteration
            ):
                self._is_finished = True
        # Log metadata.
        self._log_metadata()
        # Save and close the files.
        self._close_files()
        # Close handles to the allocated shared memory for the `Streams`.
        for container in self._streams.values():
            container.close_all()
