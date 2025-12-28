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

from collections import namedtuple
from dataclasses import dataclass
from typing import Optional, TypeAlias, Any, Deque, Iterable, Mapping, Dict
from enum import Enum
from threading import Lock
import zmq


NewDataDict: TypeAlias = Dict[str, Dict[str, Any]]
DataFifo: TypeAlias = Deque[Any]
DataFifoDict: TypeAlias = Dict[str, Dict[str, DataFifo]]
StreamInfoDict: TypeAlias = Dict[str, Dict[str, Dict[str, Any]]]
DeviceLockDict: TypeAlias = Dict[str, Lock]
ExtraDataInfoDict: TypeAlias = Dict[str, Dict[str, Any]]
VideoFormatTuple = namedtuple("VideoFormatTuple", ("format", "color"))
AudioFormatTuple = namedtuple("AudioFormatTuple", ("format", "color"))
ZMQResult: TypeAlias = Iterable[tuple[zmq.SyncSocket, int]]


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
    pix_format: str
    num_cpu: int = 1
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
    is_quiet: Optional[bool] = False
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


class VideoFormatEnum(Enum):
    """Video format enumeration for supported FFmpeg video formats.

    Must be a tuple of (<FFmpeg write format>, <Color format>), where:
        write format is one of: `ffmpeg -formats`
        pixel color is one of: `ffmpeg -pix_fmts`
    """

    BGR = VideoFormatTuple("rawvideo", "bgr24")
    YUV = VideoFormatTuple("rawvideo", "yuv420p")
    JPEG = VideoFormatTuple("image2pipe", "yuv420p")
    MJPEG = VideoFormatTuple("jpeg_pipe", "yuv420p")
    BAYER_RG8 = VideoFormatTuple("rawvideo", "bayer_rggb8")


class AudioFormatEnum(Enum):
    """Audio format enumeration for supported FFmpeg video formats.

    TODO:
    Must be a tuple of (<FFmpeg write format>, ...), where:
        write format is one of: `ffmpeg -formats`
    """

    BGR = AudioFormatTuple("rawvideo", "bgr24")
    YUV = AudioFormatTuple("rawvideo", "yuv420p")
    JPEG = AudioFormatTuple("image2pipe", "yuv420p")
    BAYER_RG8 = AudioFormatTuple("rawvideo", "bayer_rggb8")
