############
#
# Copyright (c) 2024-2025 Maxim Yudayev and KU Leuven eMedia Lab
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
from typing import Any, Iterator

try:
    import ffmpeg
except ImportError as e:
    print(
        e,
        "\nFFmpeg not installed, will crash if you configure streaming of video/audio.",
        flush=True,
    )

from hermes.base.stream import Stream
from hermes.base.storage.storage_interface import StorageInterface
from hermes.base.storage.storage_states import AbstractStorageState, StartState
from hermes.utils.time_utils import get_time, get_time_str
from hermes.utils.dict_utils import convert_dict_values_to_str
from hermes.utils.types import LoggingSpec


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

    def __init__(self, log_tag: str, spec: LoggingSpec):
        """Constructor of the Storage component responsible for all IO.

        Args:
            log_tag (str): Filename prefix.
            spec (LoggingSpec): Specifies what and how to store to disk.
        """
        self._log_tag = log_tag
        self._spec = spec

        # Initialize variables that will guide the thread that will do stream/dump logging of data available in the Stream objects.
        #   Main thread will listen to the sockets and put files to the Stream objects.
        self._is_streaming: bool  # whether periodic writing is active
        self._is_flush: bool  # whether remaining data at the end should now be flushed
        self._is_finished: bool  # whether the logging loop is finished and all data was flushed

        # Initialize the logging writers.
        self._thread_pool: concurrent.futures.ThreadPoolExecutor
        self._hdf5_file: h5py.File | None = None
        self._video_writers: list[tuple[Popen, str, str, str]] = []
        self._audio_writers: list[tuple[Popen, str, str, str]] = []
        self._csv_writers: list[tuple[TextIOWrapper, str, str, str]] = []
        self._csv_writer_metadata: TextIOWrapper | None = None

        # Create the log directory if needed.
        if self._is_to_stream() or self._is_to_dump():
            os.makedirs(self._spec.log_dir, exist_ok=True)

    def __call__(self, streams: OrderedDict[str, Stream]) -> None:
        """Callable that runs main FSM loop.

        Runs continuously, ignoring Ctrl+C interrupt, until owner Node triggers an exit.

        Args:
            streams (OrderedDict[str, Stream]): Reference to the Stream objects to flush to disk.
        """
        self._state = StartState(self, streams)
        while self._state.is_continue():
            self._state.run()
        print("%s Logger safely exited." % self._log_tag, flush=True)

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
    def _initialize(self, streams: OrderedDict[str, Stream]) -> None:
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
        num_workers: int = 0
        if self._spec.stream_csv:
            num_workers += self._init_files_csv()
        if self._spec.stream_hdf5:
            num_workers += self._init_files_hdf5()
        if self._spec.stream_video:
            num_workers += self._init_files_video()
        if self._spec.stream_audio:
            num_workers += self._init_files_audio()
        self._init_log_indices()
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=num_workers
        )
        self._is_streaming = True
        self._is_flush = False
        self._is_finished = False

    def _stop_stream_logging(self) -> None:
        self._is_streaming = False
        self._is_flush = True

    def _start_dump_logging(self) -> None:
        num_workers: int = 0
        if self._spec.dump_csv:
            num_workers += self._init_files_csv()
        if self._spec.dump_hdf5:
            num_workers += self._init_files_hdf5()
        if self._spec.dump_video:
            num_workers += self._init_files_video()
        if self._spec.dump_audio:
            num_workers += self._init_files_audio()
        # Log all data.
        # Will basically enable periodic stream-logging,
        #  but will set self._is_flush and self._is_streaming such that
        #  it seems like the experiment ended and just a final flush is required.
        #  This will cause the stream-logging in self._log_data()
        #  to fetch and write any outstanding data, which is all data since
        #  none is written yet.  It will then exit after the single write.
        # Pretend like the dumping options are actually streaming options.
        self._spec.stream_csv = self._spec.dump_csv
        self._spec.stream_hdf5 = self._spec.dump_hdf5
        self._spec.stream_video = self._spec.dump_video
        self._spec.stream_audio = self._spec.dump_audio
        # Clear the is_finished flag in case dump is run after stream so the log loop
        #  can run once to flush all logged data that wasn't stream-logged.
        self._is_finished = False
        # Initialize indices and log all of the data.
        self._init_log_indices()
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=num_workers
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
        for streamer_name, stream in self._streams.items():
            for device_name, device_info in stream.get_stream_info_all().items():
                self._timesteps_before_solidified[streamer_name][
                    device_name
                ] = OrderedDict()
                for stream_name, stream_info in device_info.items():
                    self._timesteps_before_solidified[streamer_name][device_name][
                        stream_name
                    ] = stream_info["timesteps_before_solidified"]

    def _init_files_csv(self) -> int:
        """Create and initialize CSV files.

        Will have a separate file for each stream of each device.
        Currently assumes that device names are unique across all streamers.

        Returns:
            int: Number of initialized writers.
        """
        num_writers: int = 0
        for streamer_name, streamer in self._streams.items():
            for device_name, device_info in streamer.get_stream_info_all().items():
                for stream_name, stream_info in device_info.items():
                    # Skip saving video or audio in a CSV.
                    if stream_info["is_video"] or stream_info["is_audio"]:
                        continue
                    filename_csv = "%s_%s_%s.csv" % (
                        self._log_tag,
                        device_name,
                        stream_name,
                    )
                    filepath_csv = os.path.join(self._spec.log_dir, filename_csv)
                    csv_writer = open(filepath_csv, "w")
                    self._csv_writers.append(
                        (csv_writer, streamer_name, device_name, stream_name)
                    )
                    num_writers += 1

        # Open a writer for a CSV metadata file.
        filename_csv = "%s__metadata.csv" % (self._log_tag)
        filepath_csv = os.path.join(self._spec.log_dir, filename_csv)
        self._csv_writer_metadata = open(filepath_csv, "w")

        # Write CSV headers.
        for stream_writer, streamer_name, device_name, stream_name in self._csv_writers:
            # First check if custom header titles have been specified.
            stream_info = self._streams[streamer_name].get_stream_info_all()[
                device_name
            ][stream_name]
            sample_size = stream_info["sample_size"]
            if (
                isinstance(stream_info["data_notes"], dict)
                and Stream.metadata_data_headings_key in stream_info["data_notes"]
            ):
                data_headers = stream_info["data_notes"][
                    Stream.metadata_data_headings_key
                ]
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
            stream_writer.write(",")
            stream_writer.write(",".join(data_headers))
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
        self._hdf5_file = h5py.File(filepath_hdf5, "w")
        # Create a dataset for each data key of each stream of each device.
        for streamer_name, stream in self._streams.items():
            streamer_group = self._hdf5_file.create_group(streamer_name)
            for device_name, device_info in stream.get_stream_info_all().items():
                device_group = streamer_group.create_group(device_name)
                self._next_data_indices_hdf5[streamer_name][device_name] = OrderedDict()
                for stream_name, stream_info in device_info.items():
                    # Skip saving video and audio in the HDF5.
                    if stream_info["is_video"] or stream_info["is_audio"]:
                        continue
                    self._next_data_indices_hdf5[streamer_name][device_name][
                        stream_name
                    ] = 0
                    # The main data has specifications defined by stream_info.
                    sample_size = stream_info["sample_size"]
                    data_type = stream_info["data_type"]
                    # Create the dataset.
                    device_group.create_dataset(
                        name=stream_name,
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
        for streamer_name, streamer in self._streams.items():
            for device_name, device_info in streamer.get_stream_info_all().items():
                for stream_name, stream_info in device_info.items():
                    # Skip non-video streams.
                    if not stream_info["is_video"]:
                        continue
                    # Create a unique file.
                    filename_base = "%s_%s" % (self._log_tag, device_name)
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
                    frame_height = stream_info["sample_size"][0]
                    frame_width = stream_info["sample_size"][1]
                    fps = stream_info["sampling_rate_hz"]
                    input_stream_format: str = stream_info["format"]
                    input_stream_pix_fmt: str = stream_info["color"]
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
                                ("Xencoded-by", "HERMES"),
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
                    video_writer: Popen = ffmpeg.run_async(video_stream, quiet=self._spec.is_quiet, pipe_stdin=True)  # type: ignore
                    # Store the writer.
                    self._video_writers.append(
                        (video_writer, streamer_name, device_name, stream_name)
                    )
                    num_writers += 1
        return num_writers

    def _init_files_audio(self) -> int:
        """[Not implemented] Create and initialize audio writers, one for each device.

        TODO: implement audio streaming info on the Stream object.

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
        for streamer_name, streamer in self._streams.items():
            for device_name, device_info in streamer.get_stream_info_all().items():
                for stream_name, stream_info in device_info.items():
                    # Skip non-audio streams.
                    if not stream_info["is_audio"]:
                        continue
                    # Create a unique file.
                    filename_base = "%s_%s" % (self._log_tag, device_name)
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
                    fps = stream_info["sampling_rate_hz"]
                    num_channels = stream_info["num_channels"]
                    input_stream_sample_fmt = stream_info["sample_format"]

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
                    audio_writer: Popen = ffmpeg.run_async(audio_stream, quiet=self._spec.is_quiet, pipe_stdin=True)  # type: ignore
                    # Store the writer.
                    self._audio_writers.append(
                        (audio_writer, streamer_name, device_name, stream_name)
                    )
                    num_writers += 1
        return num_writers

    def _log_metadata_csv(self) -> None:
        """Add experiment metadata on the CSV files.

        TODO: validate logic.
        """
        for streamer_name, stream in self._streams.items():
            for device_name, device_info in stream.get_stream_info_all().items():
                # Get data notes for each stream.
                for stream_name, stream_info in device_info.items():
                    data_notes = stream_info["data_notes"]
                    if isinstance(data_notes, dict):
                        stream_metadata = data_notes
                    else:
                        stream_metadata = {"data_notes": data_notes}
                    stream_metadata = convert_dict_values_to_str(
                        stream_metadata, preserve_nested_dicts=False
                    )
                    # Write the stream-level metadata.
                    if self._csv_writer_metadata is not None:
                        self._csv_writer_metadata.write("\n")
                        self._csv_writer_metadata.write(
                            "Stream Name,%s" % (stream_name)
                        )
                        for meta_key, meta_value in stream_metadata.items():
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
            },
            preserve_nested_dicts=False,
        )
        if self._hdf5_file is not None:
            file_group = self._hdf5_file["/"]
            file_group.attrs.update(file_metadata)
            # Add metadata per stream.
            # Flatten and prune the dictionary to make it HDF5 compatible.
            for streamer_name, stream in self._streams.items():
                # Add the class name.
                streamer_metadata = convert_dict_values_to_str(
                    {Stream.metadata_class_name_key: type(stream).__name__},
                    preserve_nested_dicts=False,
                )
                streamer_group = self._hdf5_file["/".join([streamer_name])]
                streamer_group.attrs.update(streamer_metadata)
                for device_name, device_info in stream.get_stream_info_all().items():
                    # NOTE: no per-device metadata for now.
                    # Get data notes for each stream.
                    for stream_name, stream_info in device_info.items():
                        try:
                            stream_group = self._hdf5_file[
                                "/".join([streamer_name, device_name, stream_name])
                            ]
                            data_notes = stream_info["data_notes"]
                            if isinstance(data_notes, dict):
                                stream_metadata = data_notes
                            else:
                                stream_metadata = {"Notes": data_notes}
                            stream_metadata = convert_dict_values_to_str(
                                stream_metadata, preserve_nested_dicts=False
                            )
                            stream_group.attrs.update(stream_metadata)
                        except KeyError:  # a writer was not created for this stream
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
        if self._hdf5_file is not None:
            for streamer_name, stream in self._streams.items():
                for device_name, device_info in stream.get_stream_info_all().items():
                    for stream_name, stream_info in device_info.items():
                        try:
                            dataset: h5py.Dataset = self._hdf5_file["/".join([streamer_name, device_name, stream_name])]  # type: ignore
                        except KeyError:  # a dataset was not created for this stream
                            continue
                        starting_index = self._next_data_indices_hdf5[streamer_name][
                            device_name
                        ][stream_name]
                        ending_index = starting_index - 1
                        dataset.resize((ending_index + 1, *dataset.shape[1:]))
            self._hdf5_file.close()
            self._hdf5_file = None

    def _close_files_video(self) -> None:
        """Flush/close the video files writers."""
        for (video_writer, *_) in self._video_writers:
            video_writer.stdin.close()  # type: ignore
            if self._spec.is_quiet:
                video_writer.stderr.close()  # type: ignore
                video_writer.stdout.close()  # type: ignore
            video_writer.wait()
        self._video_writers = []

    def _close_files_csv(self) -> None:
        """Flush/close the CSV file writers."""
        for (stream_writer, *_) in self._csv_writers:
            stream_writer.close()
        self._csv_writers = []
        if self._csv_writer_metadata is not None:
            self._csv_writer_metadata.close()
            self._csv_writer_metadata = None

    def _close_files_audio(self) -> None:
        """Flush/close the audio file writers."""
        for (audio_writer, *_) in self._audio_writers:
            audio_writer.stdin.close()  # type: ignore
            if self._spec.is_quiet:
                audio_writer.stderr.close()  # type: ignore
                audio_writer.stdout.close()  # type: ignore
            audio_writer.wait()
        self._audio_writers = []

    def _close_files(self) -> None:
        """Convenience method to close all files writers."""
        self._close_files_csv()
        self._close_files_hdf5()
        self._close_files_video()
        self._close_files_audio()

    def _sync_write_hdf5(
        self, node_name: str, device_name: str, stream_name: str
    ) -> None:
        """Write provided data to the HDF5 file.

        Can be called during streaming (periodic writing) and post-experiment dumping.

        Args:
            node_name (str): Valid unique tag of the Node owning the data.
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
        """
        if self._hdf5_file is not None:
            try:
                dataset: h5py.Dataset = self._hdf5_file["/".join([node_name, device_name, stream_name])]  # type: ignore
            except KeyError:  # a dataset was not created for this stream
                return
            new_data: Iterator[Any] = self._streams[node_name].pop_data(
                device_name=device_name,
                stream_name=stream_name,
                is_flush=self._is_flush,
            )
            for data in new_data:
                dataset_dtype: np.dtype = dataset.dtype
                # if dataset_dtype.char == 'S':
                #   data: str
                #   encoded_text = [data.encode("ascii", "ignore")]
                #   arr = np.array(encoded_text, ndmin=1)
                # else:
                arr = np.array(data, ndmin=1)
                num_elements = 1 if arr.shape == dataset.shape[1:] else arr.shape[0]
                # Extend the dataset as needed while iterating over the 'new_data'.
                start_index = self._next_data_indices_hdf5[node_name][device_name][
                    stream_name
                ]
                # Expand the dataset if needed.
                if not (start_index + num_elements < len(dataset)):
                    dataset.resize(
                        (
                            len(dataset) + self._hdf5_log_length_increment,
                            *dataset.shape[1:],
                        )
                    )
                dataset[start_index : start_index + num_elements, :] = arr
                # Write the new entries.
                # Update the next starting index to use.
                start_index += num_elements
                self._next_data_indices_hdf5[node_name][device_name][
                    stream_name
                ] = start_index
            # Flush the file with the new data.
            self._hdf5_file.flush()

    def _sync_write_video(
        self, video_writer: Popen, node_name: str, device_name: str, stream_name: str
    ):
        """Write provided data to the video files.

        Can be called during streaming (periodic writing) and post-experiment dumping.

        Args:
            video_writer (Popen): FFmpeg writer corresponding to the video.
            node_name (str): Valid unique tag of the Node owning the data.
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
        """
        new_data: Iterator[tuple[bytes, bool, int]] = self._streams[node_name].pop_data(
            device_name=device_name, stream_name=stream_name, is_flush=self._is_flush
        )
        for frame_buffer, is_keyframe, frame_index in new_data:
            video_writer.stdin.write(frame_buffer)  # type: ignore

    def _sync_write_csv(
        self,
        csv_writer: TextIOWrapper,
        node_name: str,
        device_name: str,
        stream_name: str,
    ) -> None:
        """Write provided data to the CSV file.

        Can be called during streaming (periodic writing) and post-experiment dumping.

        Args:
            csv_writer (TextIOWrapper): Text file writer corresponding to the stream.
            node_name (str): Valid unique tag of the Node owning the data.
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
        """
        new_data: Iterator[Any] = self._streams[node_name].pop_data(
            device_name=device_name, stream_name=stream_name, is_flush=self._is_flush
        )
        for data_to_write in new_data:
            # Create a list of column entries to write.
            # Note that they should match the heading order in _init_writing_csv().
            if isinstance(data_to_write, np.ndarray):
                to_write = list(np.atleast_1d(data_to_write.reshape(1, -1).squeeze()))
            elif isinstance(data_to_write, (list, tuple)):
                to_write = data_to_write
            else:
                to_write = list(data_to_write)
            # Write the new row.
            csv_writer.write("\n")
            csv_writer.write(",".join([str(x) for x in to_write]))
        csv_writer.flush()

    def _sync_write_audio(
        self, audio_writer: Popen, node_name: str, device_name: str, stream_name: str
    ):
        """Write provided data to the audio files.

        Can be called during streaming (periodic writing) and post-experiment dumping.

        Args:
            audio_writer (Popen): FFmpeg writer corresponding to the audio.
            node_name (str): Valid unique tag of the Node owning the data.
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
        """
        new_data: Iterator[Any] = self._streams[node_name].pop_data(
            device_name=device_name, stream_name=stream_name, is_flush=self._is_flush
        )
        for frame in new_data:
            audio_writer.stdin.write(frame)  # type: ignore

    def _write_hdf5(self) -> None:
        """Convenience wrapper to write new data for multiple HDF5 streams.

        Writes all new text data to a single HDF5 file.
        """
        for streamer_name, stream in self._streams.items():
            for device_name, device_info in stream.get_stream_info_all().items():
                for stream_name, stream_info in device_info.items():
                    self._sync_write_hdf5(
                        node_name=streamer_name,
                        device_name=device_name,
                        stream_name=stream_name,
                    )

    async def _write_video(
        self, video_writer: Popen, node_name: str, device_name: str, stream_name: str
    ):
        """Coroutine asynchronous wrapper for multiple video streams.

        Wraps synchronous IO of each video file into an asynchronous pool of coroutines.

        Args:
            video_writer (Popen): FFmpeg writer corresponding to the video.
            node_name (str): Valid unique tag of the Node owning the data.
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
        """
        await asyncio.get_event_loop().run_in_executor(
            self._thread_pool,
            lambda: self._sync_write_video(
                video_writer=video_writer,
                node_name=node_name,
                device_name=device_name,
                stream_name=stream_name,
            ),
        )

    async def _write_csv(
        self,
        csv_writer: TextIOWrapper,
        node_name: str,
        device_name: str,
        stream_name: str,
    ):
        """Coroutine asynchronous wrapper for multiple CSV streams.

        Wraps synchronous IO of each CSV file into an asynchronous pool of coroutines.

        Args:
            csv_writer (TextIOWrapper): Text file writer corresponding to the stream.
            node_name (str): Valid unique tag of the Node owning the data.
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
        """
        await asyncio.get_event_loop().run_in_executor(
            self._thread_pool,
            lambda: self._sync_write_csv(
                csv_writer=csv_writer,
                node_name=node_name,
                device_name=device_name,
                stream_name=stream_name,
            ),
        )

    async def _write_audio(
        self, audio_writer: Popen, node_name: str, device_name: str, stream_name: str
    ):
        """Coroutine asynchronous wrapper for multiple audio streams.

        Wraps synchronous IO of each video file into an asynchronous pool of coroutines.

        Args:
            audio_writer (Popen): FFmpeg writer corresponding to the audio.
            node_name (str): Valid unique tag of the Node owning the data.
            device_name (str): Valid device tree name.
            stream_name (str): Valid sub-stream name.
        """
        await asyncio.get_event_loop().run_in_executor(
            self._thread_pool,
            lambda: self._sync_write_audio(
                audio_writer=audio_writer,
                node_name=node_name,
                device_name=device_name,
                stream_name=stream_name,
            ),
        )

    async def _write_files_hdf5(self):
        """Convenience method to asynchronously write all HDF5 data to file.

        Will launch coroutine concurrently with other IO writer types.
        """
        await asyncio.get_event_loop().run_in_executor(
            self._thread_pool, lambda: self._write_hdf5()
        )

    async def _write_files_video(self):
        """Convenience method to asynchronously write all video data to files.

        Will launch coroutines concurrently with other IO writer types.
        """
        tasks = []
        for (
            video_writer,
            streamer_name,
            device_name,
            stream_name,
        ) in self._video_writers:
            tasks.append(
                self._write_video(
                    video_writer=video_writer,
                    node_name=streamer_name,
                    device_name=device_name,
                    stream_name=stream_name,
                )
            )
        await asyncio.gather(*tasks)

    async def _write_files_csv(self):
        """Convenience method to asynchronously write all CSV data to files.

        Will launch coroutine concurrently with other IO writer types.
        """
        tasks = []
        for stream_writer, streamer_name, device_name, stream_name in self._csv_writers:
            tasks.append(
                self._write_csv(
                    csv_writer=stream_writer,
                    node_name=streamer_name,
                    device_name=device_name,
                    stream_name=stream_name,
                )
            )
        await asyncio.gather(*tasks)

    async def _write_files_audio(self):
        """Convenience method to asynchronously write all audio data to files.

        Will launch coroutine concurrently with other IO writer types.
        """
        tasks = []
        for (
            audio_writer,
            streamer_name,
            device_name,
            stream_name,
        ) in self._audio_writers:
            tasks.append(
                self._write_audio(
                    audio_writer=audio_writer,
                    node_name=streamer_name,
                    device_name=device_name,
                    stream_name=stream_name,
                )
            )
        await asyncio.gather(*tasks)

    ##########################
    ###### DATA LOGGING ######
    ##########################
    async def _log_data(self) -> None:
        """Trigger release of AsyncIO resources used for writing files.

        Polls data from each Node periodically or all at once.

        The poll period is set by self._stream_period_s.

        Will loop until self._is_streaming is False, and then
        will do one final fetch/log if self._is_flush is True.

        Assert self._is_streaming and deassert self._is_flush for streaming.
            To finish, deassert self._is_streaming to False and assert self._is_flush.

        Deassert self._is_streaming and assert self._is_flush to dump record.
            The thread will be inactive until terminated.
            User is responsible to provision sufficient memory.
        """
        last_log_time_s = None
        # Set at the beginning of the iteration if _is_flush is externally modified to indicate cleanup and exit,
        #   to catch case where external command to flush happened while some of streamers already saved part of available data.
        is_flush_all_in_current_iteration = False
        while (self._is_streaming or self._is_flush) and not self._is_finished:
            # Wait until it is time to write new data, which is either:
            #  1. This is the first iteration.
            #  2. It has been at least self._stream_period_s since the last write.
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
            # If running Logger in dump mode, wait until _is_flush is set externally.
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
            # Delegate file writing to each AsyncIO method that manages corresponding stream type writing.
            tasks = []
            if self._spec.stream_hdf5:
                tasks.append(self._write_files_hdf5())
            if self._spec.stream_video:
                tasks.append(self._write_files_video())
            if self._spec.stream_csv:
                tasks.append(self._write_files_csv())
            if self._spec.stream_audio:
                tasks.append(self._write_files_audio())
            # Execute all file writing concurrently.
            await asyncio.gather(*tasks)
            # If stream-logging is disabled, but a final flush had been requested,
            #   record that the flush is complete so streaming can really stop now.
            # Note that it also checks whether the flush was configured to happen for all streamers during this iteration.
            #   Especially if a lot of data was being written (such as with video data),
            #   the self._is_flush flag may have been set sometime during the data writing.
            #   In that case, all streamers would not have known to flush data and some data may be omitted.
            # flushing_log set True when _is_flush was set before any streamer saved its data chunk, to make ure nothing is left behind.
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
