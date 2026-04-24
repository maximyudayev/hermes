import argparse
import io
import sys
from pathlib import Path
import time
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import FuncFormatter
from matplotlib.transforms import (
    Bbox, 
    TransformedBbox,
    blended_transform_factory,
)
from mpl_toolkits.axes_grid1.inset_locator import (
    BboxConnector,
    BboxConnectorPatch,
    BboxPatch,
)
import numpy as np
from PIL import Image

# Add the parent directory ('urils') to the Python path
# to allow for absolute imports of the 'components' package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from components.sync_utils import add_alignment_info, extract_refticks_from_cameras
from components import (
    DataComponent,
    ExoImuComponent,
    MotorComponent,
    ReferenceVideoComponent,
    SkeletonComponent,
    VideoComponent
)

# Define Xsens skeleton connections (assuming a 23-joint model).
# This is a common configuration for Xsens MVN, but may need adjustment
# if your skeleton structure is different.
XSENS_SKELETON_CONNECTIONS = [
    # Spine and Head
    (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
    # Right Arm
    (4, 7), (7, 8), (8, 9), (9, 10),
    # Left Arm
    (4, 11), (11, 12), (12, 13), (13, 14),
    # Right Leg
    (0, 15), (15, 16), (16, 17), (17, 18),
    # Left Leg
    (0, 19), (19, 20), (20, 21), (21, 22),
]

def create_components(modalities: dict) -> tuple[DataComponent, ...]:
    camera = ReferenceVideoComponent(
        unique_id="cam",
        video_filepath=modalities["camera"]["video"],
        hdf5_filepath=modalities["camera"]["file"],
        data_path=modalities["camera"]["dataset"],
        legend_name="Camera",
        offset=modalities["camera"]["offset"],
    )

    ego = VideoComponent(
        unique_id="ego",
        video_filepath=modalities["ego"]["video"],
        hdf5_filepath=modalities["ego"]["file"],
        data_path=modalities["ego"]["dataset"],
        legend_name="FPOV",
        offset=modalities["ego"]["offset"],
    )

    motor = MotorComponent(
        unique_id="motor",
        hdf5_path=modalities["motor"]["file"],
        data_path=modalities["motor"]["dataset"],
        legend_name="Motor",
        offset=modalities["motor"]["offset"],
    )

    imu = ExoImuComponent(
        unique_id="imu",
        hdf5_path=modalities["imu"]["file"],
        data_path=modalities["imu"]["dataset"],
        legend_name="IMU",
        offset=modalities["imu"]["offset"],
    )

    skeleton = SkeletonComponent(
        unique_id="pose",
        hdf5_path=modalities["pose"]["file"],
        data_path=modalities["pose"]["dataset"],
        legend_name="3D Pose",
        offset=modalities["pose"]["offset"],
    )

    return (
        camera,
        ego,
        motor,
        imu,
        skeleton
    )

def connect_bbox(
    bbox1,
    bbox2,
    loc1a,
    loc2a,
    loc1b,
    loc2b,
    prop_lines,
    prop_patches=None
):
    if prop_patches is None:
        prop_patches = {
            **prop_lines,
            "alpha": prop_lines.get("alpha", 1) * 0.2,
            "clip_on": False,
        }

    c1 = BboxConnector(
        bbox1,
        bbox2,
        loc1=loc1a,
        loc2=loc2a,
        clip_on=False,
        **prop_lines
    )
    c2 = BboxConnector(
        bbox1,
        bbox2,
        loc1=loc1b,
        loc2=loc2b,
        clip_on=False,
        **prop_lines
    )

    prop_patches2 = prop_patches.copy()
    prop_patches2["alpha"] = 0.1
    prop_patches2["color"] = "tab:red"
    bbox_patch1 = BboxPatch(bbox1, **prop_patches2)

    prop_patches2["alpha"] = 0.8
    bbox_patch2 = BboxPatch(bbox2, **prop_patches2)

    p = BboxConnectorPatch(
        bbox1,
        bbox2,
        loc1a=loc1a,
        loc2a=loc2a,
        loc1b=loc1b,
        loc2b=loc2b,
        clip_on=False,
        **prop_patches
    )

    return c1, c2, bbox_patch1, bbox_patch2, p

def zoom_series(ax1, ax2, xmin, xmax, **kwargs):
    bbox = Bbox.from_extents(xmin, 0, xmax, 1)

    mybbox1 = TransformedBbox(bbox, ax1.get_xaxis_transform())
    mybbox2 = TransformedBbox(bbox, ax2.get_xaxis_transform())

    prop_patches = {**kwargs, "ec": "none", "alpha": 0.2}

    c1, c2, bbox_patch1, bbox_patch2, p = connect_bbox(
        mybbox1,
        mybbox2,
        loc1a=3,
        loc2a=2,
        loc1b=4,
        loc2b=1,
        prop_lines=kwargs,
        prop_patches=prop_patches
    )

    ax1.add_patch(bbox_patch1)
    ax2.add_patch(bbox_patch2)
    ax2.add_patch(c1)
    ax2.add_patch(c2)
    ax2.add_patch(p)

    return c1, c2, bbox_patch1, bbox_patch2, p

def plot_skeleton(ax, pose_data, connections):
    # Plot joints
    ax.scatter(pose_data[:, 0], pose_data[:, 1], pose_data[:, 2], marker='o', color='tab:red', s=14, depthshade=True)

    # Plot bones
    for i, j in connections:
        if i < len(pose_data) and j < len(pose_data):
            ax.plot(
                [pose_data[i, 0], pose_data[j, 0]],
                [pose_data[i, 1], pose_data[j, 1]],
                [pose_data[i, 2], pose_data[j, 2]],
                color='tab:blue',
                linewidth=1.75
            )

    x_lim = (np.min(pose_data[:, 0]), np.max(pose_data[:, 0]))
    y_lim = (np.min(pose_data[:, 1]), np.max(pose_data[:, 1])) 
    z_lim = (np.min(pose_data[:, 2]), np.max(pose_data[:, 2]))

    ax.set_xlim(*x_lim)
    ax.set_ylim(*y_lim)
    ax.set_zlim(*z_lim)

    # Set aspect ratio to be proportional to data ranges for a realistic shape
    ax.set_box_aspect((x_lim[1]-x_lim[0], y_lim[1]-y_lim[0], z_lim[1]-z_lim[0]))
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_zticklabels([])
    # ax.view_init(elev=20., azim=-75)
    # Make the background panes white and remove gridlines
    ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 1.0))
    ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 1.0))
    ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 1.0))
    ax.set_xmargin(0.0)
    ax.set_ymargin(0.0)
    ax.set_zmargin(0.0)
    ax.grid(False)

def bytes_to_jpeg(jpeg_bytes: bytes) -> np.ndarray:
    # Create a binary stream from the raw bytes
    image_stream = io.BytesIO(jpeg_bytes)
    # Open the image using Pillow, which automatically decodes it
    pil_image = Image.open(image_stream)
    # Convert the Pillow image to a NumPy array
    return np.array(pil_image)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--name',
        '-n',
        action='append',
        type=str,
        required=True,
        help="Name of the modality. Can be specified multiple times."
    )
    parser.add_argument(
        '--file',
        '-f',
        action='append',
        type=str,
        required=True,
        help="Path to the HDF5 file. Can be specified multiple times."
    )
    parser.add_argument(
        '--video',
        '-v',
        action='append',
        type=str,
        default=None,
        required=False,
        help="Path to the video file. Can be specified multiple times."
    )
    parser.add_argument(
        '--dataset',
        '-d',
        action='append',
        type=str,
        required=True,
        help="Path to the dataset. Must be specified for each file.\n"
             "Example: '/MyProducer/MyDevice/'. Can be specified multiple times."
    )
    parser.add_argument(
        '--offset',
        '-o',
        action='append',
        type=float,
        required=True,
        help="Offset for initial alignment to counter internal delay of the corresponding system. Can be specified multiple times."
    )

    args = parser.parse_args()

    if (len(args.name) != len(args.file) or
        len(args.video) != len(args.file) or
        len(args.dataset) != len(args.file) or
        len(args.offset) != len(args.file)
    ):
        sys.exit("Error: The number of --name, --video, --dataset, --offset arguments must match.")

    modalities = dict(
        map(lambda x: (x[0], dict(zip(["file", "video", "dataset", "offset"], x[1:]))),
            zip(
                args.name,
                args.file,
                args.video,
                args.dataset,
                args.offset,
            )
        )
    )

    cam, ego, motor, imu, pose = create_components(modalities)
    combined_timestamps, combined_toas, camera_align_info, start_trial_toa, end_trial_toa = (
        extract_refticks_from_cameras([cam])
    )
    add_alignment_info([cam], camera_align_info)

    print(f'\nUsing Cameras as reference for visualization duration', flush=True)
    print(f'Total {len(combined_timestamps)} video frames in trial, for {end_trial_toa - start_trial_toa:.2f}s', flush=True)

    # Prompt user for two timestamps from the list to generate an overlaid plot
    cam_frame_id_1 = 15980 #int(input(f'Enter start frame between 0 and {len(combined_timestamps)-1} (e.g. 15980): '))
    cam_frame_id_2 = 85000 #int(input(f'Enter end frame between {cam_frame_id_1} and {len(combined_timestamps)-1} (e.g. 85000): '))
    assert 0 <= cam_frame_id_1 < cam_frame_id_2 < len(combined_timestamps), "Invalid frame indices."

    toa_1, toa_2 = cam.get_toa_at_frame(cam_frame_id_1), cam.get_toa_at_frame(cam_frame_id_2)
    ego_frame_id_1, ego_frame_id_2 = ego.get_frame_for_toa(toa_1), ego.get_frame_for_toa(toa_2)
    pose_frame_id_1, pose_frame_id_2 = pose.get_frame_for_toa(toa_1), pose.get_frame_for_toa(toa_2)

    imu_idx_start, imu_idx_end = imu.get_frame_for_toa(start_trial_toa), imu.get_frame_for_toa(end_trial_toa)
    motor_idx_start, motor_idx_end = motor.get_frame_for_toa(start_trial_toa), motor.get_frame_for_toa(end_trial_toa)

    cam_frame_1, cam_frame_2 = cam.get_frame(cam_frame_id_1), cam.get_frame(cam_frame_id_2)
    ego_frame_1, ego_frame_2 = ego.get_frame(ego_frame_id_1), ego.get_frame(ego_frame_id_2)
    pose_frame_1, pose_frame_2 = pose.get_sync_info()['data'][pose_frame_id_1], pose.get_sync_info()['data'][pose_frame_id_2]
    imu_data = imu.get_sync_info()['data'][imu_idx_start:imu_idx_end]
    imu_timestamps = imu.get_sync_info()['timestamps'][imu_idx_start:imu_idx_end]
    motor_data = motor.get_sync_info()['data'][motor_idx_start:motor_idx_end]
    motor_timestamps = motor.get_sync_info()['timestamps'][motor_idx_start:motor_idx_end]
    duration = end_trial_toa - start_trial_toa

    # Generate the overlaid plot for the selected frame range using the aligned data from all components.
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman"],
            "font.size": 12,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "legend.fontsize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 12,
            "figure.figsize": (16, 8),
            "lines.markersize": 5,
        }
    )

    fig = plt.figure()
    plt.suptitle("Snapshot of Longitudinal Synchronization in Raw HERMES Multimodal Data", fontsize=18)

    gs1 = GridSpec(2, 5, width_ratios=[1, 1, 1, 1, 1], height_ratios=[1, 1], wspace=0.15, bottom=0.37)
    gs2 = GridSpec(1, 5, width_ratios=[1, 1, 1, 1, 1], top=0.35)

    time_fmt_fn = lambda s, _: time.strftime('%M:%S', time.gmtime(s))
    formatter = FuncFormatter(time_fmt_fn)

    ax_main = fig.add_subplot(gs1[1, :])
    ax_main.xaxis.set_major_formatter(formatter)
    ax_main_2 = ax_main.twinx()
    ax_zoom1 = fig.add_subplot(gs1[0, 0])
    ax_zoom1.xaxis.set_major_formatter(formatter)
    ax_zoom1_2 = ax_zoom1.twinx()
    ax_zoom2 = fig.add_subplot(gs1[0, -1])
    ax_zoom2.xaxis.set_major_formatter(formatter)
    ax_zoom2_2 = ax_zoom2.twinx()
    ax_pose1 = fig.add_subplot(gs1[0, 1], projection='3d')
    ax_pose2 = fig.add_subplot(gs1[0, -2], projection='3d')
    ax_cam1 = fig.add_subplot(gs2[0, 0])
    ax_ego1 = fig.add_subplot(gs2[0, 1])
    ax_cam2 = fig.add_subplot(gs2[0, -2])
    ax_ego2 = fig.add_subplot(gs2[0, -1])

    # --- Main Plot ---
    # Plot the full time series on the main axes
    ax_main.plot(motor_timestamps-start_trial_toa, motor_data, label="Motor", color="tab:blue")
    ax_main.set_xlim(0, duration)
    ax_main.set_xlabel("Time since start (mm:ss)")
    ax_main.set_ylabel("Motor position (degrees)", color="tab:blue")
    ax_main.tick_params(axis='y', labelcolor="tab:blue")
    ax_main.set_xticks(np.arange(0, duration + 1, 300))
    ax_main_2.plot(imu_timestamps-start_trial_toa, imu_data[:, 0], label="IMU", color="tab:orange")
    ax_main_2.set_ylabel("IMU angle (degrees)", color="tab:orange")
    ax_main_2.tick_params(axis='y', labelcolor="tab:orange")

    # --- Zoom 1 Plot ---
    # ax_zoom2.set_title(f"Zoom around {(toa_2-start_trial_toa):.3f}s")
    ax_zoom1.plot(motor_timestamps-start_trial_toa, motor_data, color="tab:blue")
    zoom1_xmin = (toa_1-start_trial_toa) - 3.5
    zoom1_xmax = (toa_1-start_trial_toa) + 3.5
    ax_zoom1.set_xlim(zoom1_xmin-1.5, zoom1_xmax+1.5)
    ax_zoom1.axvline(x=toa_1-start_trial_toa, color='r', linestyle='--')
    ax_zoom1.tick_params(axis='y', labelcolor="tab:blue")
    ax_zoom1.set_ylabel("Motor position (degrees)", color="tab:blue")
    ax_zoom1.grid(True, axis="x", linestyle="--", linewidth=0.5)
    ax_zoom1_2.plot(imu_timestamps-start_trial_toa, imu_data[:, 0], color="tab:orange")
    ax_zoom1_2.tick_params(axis='y', labelcolor="tab:orange")
    ax_zoom1_2.set_ylabel("IMU angle (degrees)", color="tab:orange")

    # --- Zoom 2 Plot ---
    # ax_zoom2.set_title(f"Zoom around {(toa_2-start_trial_toa):.3f}s")
    ax_zoom2.plot(motor_timestamps-start_trial_toa, motor_data, color="tab:blue")
    zoom2_xmin = (toa_2-start_trial_toa) - 3.5
    zoom2_xmax = (toa_2-start_trial_toa) + 3.5
    ax_zoom2.set_xlim(zoom2_xmin-1.5, zoom2_xmax+1.5)
    ax_zoom2.axvline(x=toa_2-start_trial_toa, color='r', linestyle='--')
    ax_zoom2.tick_params(axis='y', labelcolor="tab:blue")
    ax_zoom2.set_ylabel("Motor position (degrees)", color="tab:blue")
    ax_zoom2.grid(True, axis="x", linestyle="--", linewidth=0.5)
    ax_zoom2_2.plot(imu_timestamps-start_trial_toa, imu_data[:, 0], color="tab:orange")
    ax_zoom2_2.tick_params(axis='y', labelcolor="tab:orange")
    ax_zoom2_2.set_ylabel("IMU angle (degrees)", color="tab:orange")

    # --- Connectors ---
    zoom_series(ax_zoom1, ax_main, zoom1_xmin, zoom1_xmax)
    zoom_series(ax_zoom2, ax_main, zoom2_xmin, zoom2_xmax)

    # --- Pose Plot ---
    plot_skeleton(ax_pose1, pose_frame_1, XSENS_SKELETON_CONNECTIONS)
    plot_skeleton(ax_pose2, pose_frame_2, XSENS_SKELETON_CONNECTIONS)

    # --- Image Plots ---
    # TODO: verify alignment between images and other sensors data. Skeleton looks off.
    ax_cam1.imshow(bytes_to_jpeg(cam_frame_1))
    # ax_cam1.set_title(f"Ref Cam @ {toa_1-start_trial_toa:.2f}s")
    ax_cam1.axis('off')

    ax_ego1.imshow(bytes_to_jpeg(ego_frame_1))
    # ax_ego1.set_title(f"FPOV @ {toa_1-start_trial_toa:.2f}s")
    ax_ego1.axis('off')

    ax_cam2.imshow(bytes_to_jpeg(cam_frame_2))
    # ax_cam2.set_title(f"Ref Cam @ {toa_2-start_trial_toa:.2f}s")
    ax_cam2.axis('off')

    ax_ego2.imshow(bytes_to_jpeg(ego_frame_2))
    # ax_ego2.set_title(f"FPOV @ {toa_2-start_trial_toa:.2f}s")
    ax_ego2.axis('off')

    plt.tight_layout()
    plt.subplots_adjust(left=0.05, right=0.955, top=0.92, bottom=0.05, wspace=0.02, hspace=0.2)
    plt.show()
    print("Done.")
