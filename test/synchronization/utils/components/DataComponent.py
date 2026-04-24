from abc import ABC, abstractmethod
import numpy as np

from .types import AlignmentInfo

class DataComponent(ABC):
    def __init__(self, unique_id: str):
        self._unique_id = unique_id
        self._toa_s: np.ndarray | None = None
        self.read_data()
        self._align_info = AlignmentInfo(0, len(self._toa_s))

    @abstractmethod
    def read_data(self) -> None:
        """Read the component specific data from the files used in the constructor."""
        pass

    @abstractmethod
    def get_sync_info(self) -> dict:
        """Return synchronization info for this component."""
        pass

    def get_frame_for_toa(self, sync_timestamp: float) -> int:
        """Find the sample index closest but not later than a given timestamp."""
        time_diffs = (self._toa_s - sync_timestamp) <= 0
        return max(np.sum(time_diffs).item() - 1, 0)
    
    def set_align_info(self, alignment_info: AlignmentInfo) -> None:
        """Set alignment info for the component."""
        self._align_info = alignment_info

    def get_align_info(self) -> AlignmentInfo:
        """Get current alignment info for the component."""
        return self._align_info
