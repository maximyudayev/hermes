import numpy as np

from . import DataComponent, VideoComponent
from .types import AlignmentInfo


def extract_refticks_from_cameras(
    camera_components: list[VideoComponent],
) -> tuple[np.ndarray, np.ndarray, dict[str, AlignmentInfo], float, float]:
    """Calculate truncation points w.r.t the reference camera.

    Args:
        camera_components (list[VideoComponent]): List of cameras as reference for annotation and analysis.

    Returns:
        tuple[np.ndarray, dict[str, AlignmentInfo], float, float]: Camera frame timestamps and toas for complete trial,
          videos alignment info, experiment start UNIX time, experiment end UNIX time.
    """
    if not camera_components:
        raise ValueError('Camera components are required for synchronization.')

    # ========================================
    # Get initial metadata from all components
    # ========================================
    camera_infos = [cam.get_sync_info() for cam in camera_components]

    # =====================================================
    # Set range for the future slider, based on the cameras
    # =====================================================
    # Get range in the cameras synchronized timeline.
    camera_start_timestamps, camera_end_timestamps = zip(
        *map(lambda x: (x.frame_timestamp[0], x.frame_timestamp[-1]), camera_infos)
    )
    start_timestamp = np.max(camera_start_timestamps)
    end_timestamp = np.min(camera_end_timestamps)

    camera_align_info: dict[str, AlignmentInfo] = {}
    camera_start_toas: list[float] = []
    camera_end_toas: list[float] = []
    camera_sequences: list[np.ndarray] = []
    for cam, cam_info in zip(camera_components, camera_infos):
        # Extract indices of frames per-camera that correspond to the desired slider range.
        timestamp = cam_info.frame_timestamp
        # TODO: only seek frames that are before the current one.
        time_diffs_start = np.abs(timestamp - start_timestamp)
        time_diffs_end = np.abs(timestamp - end_timestamp)

        start_id = np.argmin(time_diffs_start)
        end_id = np.argmin(time_diffs_end)

        # Use aligned indices to extract min `toa_s` at trial start and max `toa_s` at trial end to align with external modalities.
        camera_start_toas.append(cam_info.toa_s[start_id])
        camera_end_toas.append(cam_info.toa_s[end_id])

        # Record sequence ids w.r.t. to aligned starting frame of each camera. (starts ids from 0 for easier gaps finding).
        camera_sequences.append(cam_info.sequence[start_id:end_id] - cam_info.sequence[start_id])

        # Use aligned indices (based on `frame_timestamp`) for truncation of each camera stream.
        camera_align_info[cam._unique_id] = AlignmentInfo(start_id=start_id, end_id=end_id)

        print(
            f'Camera {cam._unique_id}: '
            f'start {start_id}, timestamp {start_timestamp}, diff {time_diffs_start[start_id]}s, at {camera_start_toas[-1]}s',
            f'end {end_id}, timestamp {end_timestamp}, diff {time_diffs_end[start_id]}s, at {camera_end_toas[-1]}s',
            flush=True,
        )

    # ==================================================================
    # Merge `frame_timestamp` for all cameras for aligned `sequence_id`s
    # ==================================================================
    combined_sequences = np.unique(np.hstack(camera_sequences))
    claimed = np.zeros(len(combined_sequences), dtype=bool)
    result_indices = []
    for arr in camera_sequences:
        idx_in_combined = np.searchsorted(combined_sequences, arr)
        valid = (idx_in_combined < len(combined_sequences)) & (combined_sequences[idx_in_combined] == arr)
        contributes = valid & ~claimed[idx_in_combined]
        result_indices.append(np.where(contributes)[0])
        claimed[idx_in_combined[contributes]] = True

    camera_timestamps = []
    camera_toas = []
    for cam_info, indices in zip(camera_infos, result_indices):
        start_id = camera_align_info[cam_info.unique_id].start_id
        end_id = camera_align_info[cam_info.unique_id].end_id
        timestamps = cam_info.frame_timestamp[start_id:end_id][indices]
        toas = cam_info.toa_s[start_id:end_id][indices]
        if timestamps.shape[0]:
            camera_timestamps.append(timestamps)
            camera_toas.append(toas)

    # Merged timestamps to map slider ticks to the aligned frame timestamps of synchronized cameras.
    combined_timestamps = np.unique(np.hstack(camera_timestamps))
    combined_toas = np.unique(np.hstack(camera_toas))

    # ======================================
    # Specify the start and end of the trial
    # ======================================
    start_trial_toa = np.min(camera_start_toas)
    end_trial_toa = np.min(camera_end_toas)

    return combined_timestamps, combined_toas, camera_align_info, start_trial_toa, end_trial_toa


def add_alignment_info(components: list[DataComponent], alignment_info: dict[str, AlignmentInfo]) -> None:
    for component in components:
        component.set_align_info(alignment_info[component._unique_id])
