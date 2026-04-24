from typing import Tuple
import numpy as np
import ffmpeg
import h5py

from components import DataComponent
from components.types import VideoComponentInfo

class VideoComponent(DataComponent):
    def __init__(
        self,
        unique_id: str,
        video_filepath: str,
        hdf5_filepath: str,
        data_path: str,
        legend_name: str,
        offset: int,
    ):
        self._legend_name = legend_name
        self._video_path = video_filepath
        self._hdf5_path = hdf5_filepath
        self._data_path = data_path
        self._offset = offset

        # Get video properties
        self._width, self._height, self._fps, self._total_frames = self._get_video_properties()
        self._empty_frame = np.zeros([self._height, self._width, 3], np.uint8)
        self._current_frame_id = 0

        super().__init__(unique_id=unique_id)

    @property
    def current_frame_id(self) -> int:
        return self._current_frame_id


    def _decode(self, frame_id: int) -> bytes:
        # Seek to the timestamp because it is much faster than using frame index
        timestamp_start = frame_id / self._fps
        # Get multiple frames for caching, to mask decoding latency
        buf, _ = (
            ffmpeg.input(
                filename=self._video_path,
                ss=timestamp_start,
            )
            .output(
                'pipe:',
                vframes=1,
                format='image2',
                vcodec='mjpeg',
            )
            .run(capture_stdout=True, quiet=True)
        )
        return buf


    def read_data(self):
        with h5py.File(self._hdf5_path, 'r') as hdf5:
            try:
                self._toa_s = hdf5[f'{self._data_path}/toa_s'][:, 0] - self._offset
                self._sequence = hdf5[f'{self._data_path}/frame_index'][:, 0]
                self._timestamp = hdf5[f'{self._data_path}/frame_timestamp'][:, 0]
            except Exception as e:
                print(f'Error reading timestamps for cameras: {e}', flush=True)

    def get_frame(self, frame_id: int) -> bytes:
        """Get video frame at a specific index."""
        # Ensure we don't go beyond bounds
        if frame_id < 0:
            frame_id = 0
        elif frame_id >= self._total_frames:
            frame_id = self._total_frames - 1

        # Get the frame from the cache manager
        try:
            return self._decode(frame_id)
        except Exception as e:
            print(f'Error getting frame {frame_id}: {e}')
            return self._empty_frame.tobytes()

    def _get_video_properties(self) -> Tuple[int, int, float, int]:
        """Get video width, height, fps, and total frames using `ffprobe`."""
        probe = ffmpeg.probe(self._video_path)
        video_stream = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        fps_num, fps_denum = map(lambda x: float(x), video_stream['r_frame_rate'].split('/'))
        fps = fps_num / fps_denum
        num_frames = round(float(probe['format']['duration']) * fps)

        return width, height, fps, num_frames

    def get_frame_for_timestamp(self, timestamp: float) -> int:
        """Find the frame index closest to, but not later than the given timestamp."""
        timestamp_diffs = np.abs(self._timestamp - timestamp)
        return np.argmin(timestamp_diffs).item()

    def get_timestamp_at_frame(self, frame_id: int) -> float:
        """Get the timestamp for a given frame."""
        return self._timestamp[frame_id].item()

    def get_toa_at_frame(self, frame_id: int) -> float:
        """Get the time-of-arrival for a given frame."""
        return self._toa_s[frame_id].item()

    def get_sequence_at_frame(self, frame_id: int) -> int:
        """Get the aligned sequence id for a given frame."""
        return (self._sequence[frame_id] - self._sequence[self._align_info.start_id]).item()

    def get_sync_info(self):
        return VideoComponentInfo(
            unique_id=self._unique_id,
            toa_s=self._toa_s,
            sequence=self._sequence,
            frame_timestamp=self._timestamp,
        )
