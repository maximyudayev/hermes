from collections import OrderedDict, deque, namedtuple
from typing import TypeAlias, Any, Deque, Iterable, Iterator, Mapping, TypedDict, Dict, NamedTuple
from threading import Lock
import cv2


NewDataDict: TypeAlias = Dict[str, Dict[str, Any]]
DataFifo: TypeAlias = Deque[Any]
DataFifoDict: TypeAlias = Dict[str, Dict[str, DataFifo]]
StreamInfoDict: TypeAlias = Dict[str, Dict[str, Dict[str, Any]]]
DeviceLockDict: TypeAlias = Dict[str, Lock]
ExtraDataInfoDict: TypeAlias = Dict[str, Dict[str, Any]]
VideoFormatTuple = namedtuple('VideoFormatTuple', ('ffmpeg_input_format', 'ffmpeg_pix_fmt', 'cv2_cvt_color'))
VideoCodecDict = TypedDict('VideoCodecDict', {'codec_name': str, 'pix_format': str, 'options': Mapping})


# Must be a tuple of (<FFmpeg write format>, <OpenCV display format>):
#   one of the supported FFmpeg pixel formats: https://ffmpeg.org/doxygen/trunk/pixfmt_8h.html#a9a8e335cf3be472042bc9f0cf80cd4c5 
#   one of the supported OpenCV pixel conversion formats: https://docs.opencv.org/3.4/d8/d01/group__imgproc__color__conversions.html
VIDEO_FORMAT = {
  'bgr':        VideoFormatTuple('rawvideo',    'bgr24',        cv2.COLOR_BGR2RGB),
  'yuv':        VideoFormatTuple('rawvideo',    'yuv420p',      cv2.COLOR_YUV2RGB),
  'jpeg':       VideoFormatTuple('image2pipe',  'yuv420p',      cv2.COLOR_YUV2RGB),
  'bayer_rg8':  VideoFormatTuple('rawvideo',    'bayer_rggb8',  cv2.COLOR_BAYER_RG2RGB),
}
