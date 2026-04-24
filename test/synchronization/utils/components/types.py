from dataclasses import dataclass
import numpy as np

@dataclass
class VideoComponentInfo:
    unique_id: str
    toa_s: np.ndarray
    sequence: np.ndarray
    frame_timestamp: np.ndarray


@dataclass
class AlignmentInfo:
    start_id: int
    end_id: int
