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

from dataclasses import dataclass, field
from io import TextIOWrapper
from typing import List, Optional, TypeAlias, Any, Iterable, Mapping, Dict
import multiprocessing as mp
from multiprocessing import Value
from multiprocessing.synchronize import Lock
from multiprocessing.sharedctypes import Synchronized
from subprocess import Popen
from enum import Enum
import numpy as np
import zmq


ExtraDataInfoDict: TypeAlias = Dict[str, Dict[str, Any]]
ZMQResult: TypeAlias = Iterable[tuple[zmq.SyncSocket, int]]


@dataclass
class AudioFormat:
    write_format: str
    sample_format: str
    codec: str
    num_bytes: int
    extension: str


@dataclass
class VideoFormat:
    write_format: str
    pixel_format: str


class VideoFormatEnum(Enum):
    """Video format enumeration for supported FFmpeg video formats.

    Must be a tuple of (<FFmpeg write format>, <Color format>), where:
        write format is one of: `ffmpeg -formats`
        pixel color is one of: `ffmpeg -pix_fmts`
    """

    BGR = VideoFormat("rawvideo", "bgr24")
    # YUV = VideoFormat("rawvideo", "yuv420p")
    JPEG = VideoFormat("image2pipe", "yuv420p")
    MJPEG = VideoFormat("jpeg_pipe", "yuv420p")
    BAYER_RG8 = VideoFormat("rawvideo", "bayer_rggb8")


class AudioBackendEnum(Enum):
    DSHOW = "dshow"
    AVFOUNDATION = "avfoundation"
    PULSE = "pulse"
    ALSA = "alsa"


class AudioFormatEnum(Enum):
    """Audio format enumeration for supported FFmpeg audio formats.
    """

    MP3_MF = AudioFormat("s16le", "s16", "mp3_mf", 2, "mp3")
    LIBMP3LAME = AudioFormat("s16le", "s16", "libmp3lame", 2, "mp3")
    PCM_S16LE = AudioFormat("s16le", "s16", "pcm_s16le", 2, "wav")
    PCM_S32LE = AudioFormat("s32le", "s32", "pcm_s32le", 4, "wav")
    PCM_F32LE = AudioFormat("f32le", "flt", "pcm_f32le", 4, "wav")
    AAC = AudioFormat("s16le", "s16", "aac", 2, "m4a")
    AAC_MF = AudioFormat("s16le", "s16", "aac_mf", 2, "m4a")
    FLAC = AudioFormat("s16le", "s16", "flac", 2, "flac")


@dataclass
class BundleFillLevel:
    num_samples: int
    sample_num_bytes: int
    buf_len: int


@dataclass
class BundleMetadata:
    """Atomic data bundle synchronization primitives (non-blocking) to guard `SharedMemoryCircularBuffer` across processes."""
    lock: Lock = field(init=False)
    is_writing: "Synchronized[bool]" = field(init=False)
    is_reading: "Synchronized[bool]" = field(init=False)
    write_head: "Synchronized[int]" = field(init=False)
    read_head: "Synchronized[int]" = field(init=False)
    read_tail: "Synchronized[int]" = field(init=False)

    def __post_init__(self):
        self.lock = mp.Lock()
        self.is_writing = Value("b", False, lock=False)
        self.is_reading = Value("b", False, lock=False)
        self.write_head = Value("i", 0, lock=False)
        self.read_head = Value("i", 0, lock=False)
        self.read_tail = Value("i", 0, lock=False)


@dataclass
class SharedMemoryCircularBufferMetadata:
    """Shared memory circular buffer information to bind processes to the same underlying allocated memory."""
    buf_len: int
    data_type: str
    sample_size: Iterable[int]
    element_size: int
    shm_id: str


@dataclass
class RawBytesSharedMemoryCircularBufferMetadata(SharedMemoryCircularBufferMetadata):
    """Shared memory circular buffer information to bind processes to the same underlying allocated memory."""
    mem_size: int


@dataclass
class DataChannelInfo:
    sampling_rate_hz: float
    shm_buffer_metadata: SharedMemoryCircularBufferMetadata
    is_video: bool
    is_audio: bool
    timesteps_before_solidified: int
    extra_data_info: ExtraDataInfoDict
    data_notes: Mapping[str, str]
    video_format: Optional[VideoFormatEnum] = None
    audio_format: Optional[AudioFormatEnum] = None
    num_audio_channels: Optional[int] = None
    is_measure_rate_hz: Optional[bool] = None
    actual_rate_hz: Optional[float] = None
    dt_circular_buffer: Optional[List[float]] = None
    dt_circular_index: Optional[int] = None
    dt_running_sum: Optional[float] = None
    old_toa: Optional[float] = None


@dataclass
class DataBundleInfo:
    metadata: BundleMetadata = field(default_factory=BundleMetadata)
    channels: Dict[str, DataChannelInfo] = field(default_factory=dict)


@dataclass
class DataContainerInfo:
    bundles: Dict[str, DataBundleInfo] = field(default_factory=dict)
    bundles_not_to_write: List[str] = field(default_factory=list)


NewData: TypeAlias = Dict[str, Dict[str, np.ndarray]]


@dataclass
class VideoWriter:
    subproc: Popen
    node_name: str
    bundle_name: str
    channel_name: str


@dataclass
class AudioWriter:
    subproc: Popen
    node_name: str
    bundle_name: str
    channel_name: str


@dataclass
class CsvWriter:
    file: TextIOWrapper
    node_name: str
    bundle_name: str
    channel_name: str


@dataclass
class VideoCodec:
    """Object specifying video codec options for FFmpeg."""

    codec_name: str
    pix_format: str
    num_cpu: int = 1
    input_options: Mapping = None
    output_options: Mapping = None


@dataclass
class AudioCodec:
    """Object specifying audio codec options for FFmpeg."""

    codec_name: str
    sample_format: str
    num_cpu: int = 1
    num_audio_channels: Optional[int] = None
    sample_rate: Optional[int] = None
    input_options: Mapping = None
    output_options: Mapping = None


@dataclass
class LoggingSpec:
    """Object specifying data storage options.

    Args:
        log_dir (str): Path to the directory on disk to flush data to.
        experiment (dict[str, str]): Nested setup definition of Nodes across distributed hosts.
        log_time_s (float): Start time of saving data.
        ref_time_s (float): Reference time of the Broker to align all Nodes to.
        stream_period_s (float, optional): Duration of periods over which to flush streamed accumulated data from memory to disk. Defaults to `30.0`.
        is_quiet (bool): Whether to print FFmpeg stats to the terminal. Defaults to `False`.
        is_metadata (bool): Whether to record tabular data's metadata to files (e.g. count for chunked samples in HDF5/CSV). Defaults to `True`.
        stream_hdf5 (bool, optional): Whether to stream data into HDF5 files. Defaults to `False`.
        stream_video (bool, optional): Whether to stream video data into MP4/MKV files. Defaults to `False`.
        stream_csv (bool, optional): Whether to stream data into CSV files. Defaults to `False`.
        stream_audio (bool, optional): Whether to stream audio data into MP3/WAV files. Defaults to `False`.
        dump_csv (bool, optional): Weather to dump in-memory recorded data in CSV files. Defaults to `False`.
        dump_hdf5 (bool, optional): Weather to dump in-memory recorded data in HDF5 files. Defaults to `False`.
        dump_video (bool, optional): Weather to dump in-memory recorded video data in MP4/MKV files. Defaults to `False`.
        dump_audio (bool, optional): Weather to dump in-memory recorded audio data in MP3/WAV files. Defaults to `False`.
        video_codec (VideoCodec, optional): Definition of the video codec to use for FFmpeg. Defaults to `None`.
        audio_codec (AudioCodec, optional): Definition of the audio codec to use for FFmpeg. Defaults to `None`.
    """

    log_dir: str
    experiment: dict[str, str]
    log_time_s: float
    ref_time_s: float
    stream_period_s: Optional[float] = 30.0
    is_quiet: Optional[bool] = True
    is_metadata: Optional[bool] = False
    stream_hdf5: Optional[bool] = False
    stream_video: Optional[bool] = False
    stream_csv: Optional[bool] = False
    stream_audio: Optional[bool] = False
    dump_hdf5: Optional[bool] = False
    dump_video: Optional[bool] = False
    dump_csv: Optional[bool] = False
    dump_audio: Optional[bool] = False
    video_codec: Optional[VideoCodec] = None
    audio_codec: Optional[AudioCodec] = None
