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


import numpy as np


def calculate_truncation_points(camera_components, eye_component, baseline_frame=100):
    """
    Calculate truncation points using eye video as baseline.
    
    Args:
        camera_components: List of camera VideoComponent instances
        eye_component: Eye camera VideoComponent instance
        baseline_frame: Eye video frame to use as synchronization reference (default: 100)
    
    Returns:
        dict: Truncation points for each component {'component_id': (start_frame, end_frame)}
    """
    truncation_points = {}
    
    if not eye_component:
        raise ValueError("Eye component is required for this synchronization method")
    
    # Get sync info from all components
    camera_infos = [cam.get_sync_info() for cam in camera_components]
    eye_info = eye_component.get_sync_info()
    
    # Get the timestamp at the baseline frame for eye video
    eye_timestamps = eye_info['timestamps']
    if baseline_frame >= len(eye_timestamps):
        print(f"Warning: baseline_frame {baseline_frame} exceeds eye video length {len(eye_timestamps)}")
        baseline_frame = min(baseline_frame, len(eye_timestamps) - 1)
    
    baseline_timestamp = eye_timestamps[baseline_frame]
    print(f"\nSynchronization using eye video frame {baseline_frame} as baseline")
    print(f"Eye baseline timestamp: {baseline_timestamp}")
    
    # Find closest frame in each camera relative to the baseline timestamp (from eye video)
    camera_sync_frames = {}
    for cam_idx, (cam, cam_info) in enumerate(zip(camera_components, camera_infos)):
        toa_s = cam_info['toa_s']
        
        # Find closest toa_s to baseline timestamp
        time_diffs = np.abs(toa_s - baseline_timestamp)
        closest_idx = np.argmin(time_diffs)
        closest_timestamp = toa_s[closest_idx]
        
        camera_sync_frames[cam._unique_id] = {
            'sync_frame': closest_idx,
            'sync_timestamp': closest_timestamp,
            'time_diff': time_diffs[closest_idx]
        }
        
        print(f"Camera {cam._unique_id}: frame {closest_idx}, timestamp {closest_timestamp}, diff {time_diffs[closest_idx]}s")
    
    # Set truncation points for cameras
    for cam in camera_components:
        sync_info = camera_sync_frames[cam._unique_id]
        start_frame = sync_info['sync_frame']
        # End frame is the last frame of the video
        cam_info = next(info for info in camera_infos if info['unique_id'] == cam._unique_id)
        end_frame = len(cam_info['toa_s']) - 1
        
        truncation_points[str(cam._unique_id)] = (start_frame, end_frame)
    
    # Set truncation point for eye video
    # Start at baseline_frame
    truncation_points[str(eye_component._unique_id)] = (baseline_frame, len(eye_timestamps) - 1)
    
    # Calculate the common end point based on the shortest duration after sync
    min_frames_after_sync = float('inf')
    
    # Check eye video
    eye_frames_after_sync = len(eye_timestamps) - baseline_frame
    min_frames_after_sync = min(min_frames_after_sync, eye_frames_after_sync)
    
    # Check cameras
    for cam in camera_components:
        start_frame, end_frame = truncation_points[str(cam._unique_id)]
        frames_after_sync = end_frame - start_frame + 1
        min_frames_after_sync = min(min_frames_after_sync, frames_after_sync)
    
    print(f"\nMinimum frames after sync: {min_frames_after_sync}")
    
    # Update end frames to ensure all videos have the same length
    for cam in camera_components:
        start_frame, _ = truncation_points[str(cam._unique_id)]
        new_end_frame = start_frame + min_frames_after_sync - 1
        truncation_points[str(cam._unique_id)] = (start_frame, new_end_frame)
    
    # Update eye video end frame
    truncation_points[str(eye_component._unique_id)] = (baseline_frame, baseline_frame + min_frames_after_sync - 1)
    
    return truncation_points


def apply_truncation(components, truncation_points):
    """
    Apply truncation points to all components.
    
    Args:
        components: List of VideoComponent instances
        truncation_points: Dict of truncation points from calculate_truncation_points
    """
    for component in components:
        # Use string key to look up truncation points
        key = str(component._unique_id)
        if key in truncation_points:
            start, end = truncation_points[key]
            component.set_truncation_points(start, end)