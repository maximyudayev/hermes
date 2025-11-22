import plotly.graph_objects as go
import numpy as np
import h5py
from pathlib import Path
import os


def create_histogram_trace(data, bin_width=1, normalize=True):
    # Create bins with specified width
    data_min = np.floor(data.min())
    data_max = np.ceil(data.max())
    bin_edges = np.arange(data_min, data_max + bin_width + 1, bin_width)

    counts, bin_edges = np.histogram(data, bins=bin_edges)

    if normalize:
        counts = counts / counts.max()  # Normalize to max height of 1

    # Create coordinates for the histogram bars
    x_coords = []
    y_coords = []

    # Start at the leftmost edge, baseline
    x_coords.append(bin_edges[0])
    y_coords.append(0)

    for i in range(len(counts)):
        # Top left corner
        x_coords.append(bin_edges[i])
        y_coords.append(counts[i])
        # Top right corner
        x_coords.append(bin_edges[i + 1])
        y_coords.append(counts[i])

    # End at the rightmost edge, baseline
    x_coords.append(bin_edges[-1])
    y_coords.append(0)

    return np.array(x_coords), np.array(y_coords)


def read_hdf5_dataset_missingness_freq(
    folder_path: str,
    pattern_template: str,
    dataset_name: str,
    subjects=[],
    sample_rate=100,
) -> tuple[np.ndarray, float]:
    folder = Path(folder_path)

    total = 0
    modality_missingness = []

    for idx in subjects:
        # Create pattern for current index
        pattern = pattern_template.format(idx)
        matched_files = list(folder.glob(pattern))

        if not matched_files:
            print(f"Index {idx}: No files found matching pattern '{pattern}'")
            continue

        print(f"\nIndex {idx}: Found {len(matched_files)} file(s)")

        # Loop over each matched file
        for filepath in matched_files:
            try:
                with h5py.File(filepath, "r") as f:
                    raw_modality = np.array(f[dataset_name])[:, 0]
                    modality = raw_modality[raw_modality > 0]
                    total += len(modality)
                    gaps = np.round(np.diff(modality) * sample_rate)
                    modality_missingness.append(gaps[gaps > 0])
            except Exception as e:
                print(f"  {os.path.basename(filepath)}: Error reading file - {e}")

    print(f"Dataset '{pattern_template}' length = {total}")

    return np.concatenate(modality_missingness), total


def read_hdf5_dataset_missingness_emg(
    folder_path: str, pattern_template: str, dataset_name: str, subjects=[]
) -> tuple[np.ndarray, float]:
    folder = Path(folder_path)

    total = 0
    modality_missingness = []

    for idx in subjects:
        # Create pattern for current index
        pattern = pattern_template.format(idx)
        matched_files = list(folder.glob(pattern))

        if not matched_files:
            print(f"Index {idx}: No files found matching pattern '{pattern}'")
            continue

        print(f"\nIndex {idx}: Found {len(matched_files)} file(s)")

        # Loop over each matched file
        for filepath in matched_files:
            try:
                with h5py.File(filepath, "r") as f:
                    modality = np.array(f[dataset_name])
                    total += len(modality) * modality.shape[-1]
                    gaps = np.diff(modality, axis=0)
                    for i in range(gaps.shape[-1]):
                        inds = np.where(gaps[:, i] == 0)[0]
                        new_gaps = np.diff(inds)
                        modality_missingness.append(new_gaps)
            except Exception as e:
                print(f"  {os.path.basename(filepath)}: Error reading file - {e}")

    print(f"Dataset '{pattern_template}' length = {total}")

    return np.concatenate(modality_missingness), total


def read_hdf5_dataset_missingness(
    folder_path: str, pattern_template: str, dataset_name: str, subjects=[]
) -> tuple[np.ndarray, float]:
    folder = Path(folder_path)

    total = 0
    modality_missingness = []

    for idx in subjects:
        # Create pattern for current index
        pattern = pattern_template.format(idx)
        matched_files = list(folder.glob(pattern))

        if not matched_files:
            print(f"Index {idx}: No files found matching pattern '{pattern}'")
            continue

        print(f"\nIndex {idx}: Found {len(matched_files)} file(s)")

        # Loop over each matched file
        for filepath in matched_files:
            try:
                with h5py.File(filepath, "r") as f:
                    raw_modality = np.array(f[dataset_name])
                    modality = np.concatenate(
                        (raw_modality[0], raw_modality[raw_modality > 0])
                    )
                    total += len(modality)
                    gaps = (modality[1:] - modality[:-1]) - 1
                    modality_missingness.append(gaps[gaps > 0])
            except Exception as e:
                print(f"  {os.path.basename(filepath)}: Error reading file - {e}")

    print(f"Dataset '{pattern_template}' length = {total}")

    return np.concatenate(modality_missingness), total


if __name__ == "__main__":
    coh1 = [0, 1, 2, 3, 4, 5, 6, 7]
    coh2 = [12, 13, 14, 15, 16, 17]

    cam1_coh1, cam1_coh1_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40478064/frame_index",
        subjects=coh1,
    )
    cam2_coh1, cam2_coh1_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40549960/frame_index",
        subjects=coh1,
    )
    cam3_coh1, cam3_coh1_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40549975/frame_index",
        subjects=coh1,
    )
    cam4_coh1, cam4_coh1_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40549976/frame_index",
        subjects=coh1,
    )

    cam1_coh2, cam1_coh2_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40644951/frame_index",
        subjects=coh2,
    )
    cam2_coh2, cam2_coh2_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40644952/frame_index",
        subjects=coh2,
    )
    cam3_coh2, cam3_coh2_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40644953/frame_index",
        subjects=coh2,
    )
    cam4_coh2, cam4_coh2_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40644954/frame_index",
        subjects=coh2,
    )

    ego_coh, ego_coh_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/smartglasses",
        pattern_template="eye_{}_*.hdf5",
        dataset_name="eye/eye-video-world/frame_index",
        subjects=coh1 + coh2,
    )
    gaze_coh, gaze_coh_tot = read_hdf5_dataset_missingness_freq(
        folder_path="./visualizations/data/smartglasses",
        pattern_template="eye_{}_*.hdf5",
        dataset_name="eye/eye-gaze/timestamp",
        subjects=coh1 + coh2,
        sample_rate=250,
    )
    pupil_coh, pupil_coh_tot = read_hdf5_dataset_missingness_freq(
        folder_path="./visualizations/data/smartglasses",
        pattern_template="eye_{}_*.hdf5",
        dataset_name="eye/eye-pupil/timestamp",
        subjects=coh1 + coh2,
        sample_rate=120,
    )
    blinks_coh, blinks_coh_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/smartglasses",
        pattern_template="eye_{}_*.hdf5",
        dataset_name="eye/eye-blinks/timestamp",
        subjects=coh1 + coh2,
    )
    fixations_coh, fixations_coh_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/smartglasses",
        pattern_template="eye_{}_*.hdf5",
        dataset_name="eye/eye-fixations/timestamp",
        subjects=coh1 + coh2,
    )

    cam1_tot = cam1_coh1_tot + cam1_coh2_tot
    cam2_tot = cam2_coh1_tot + cam2_coh2_tot
    cam3_tot = cam3_coh1_tot + cam3_coh2_tot
    cam4_tot = cam4_coh1_tot + cam4_coh2_tot

    insole_coh, insole_coh_tot = read_hdf5_dataset_missingness_freq(
        folder_path="./visualizations/data/insoles",
        pattern_template="insoles_{}_*.hdf5",
        dataset_name="insoles/insoles-data/timestamp",
        subjects=[2, 3, 4, 5, 6, 7],
        sample_rate=100,
    )

    imu_coh, imu_coh_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/imu",
        pattern_template="imu_{}_*.hdf5",
        dataset_name="mvn-analyze/xsens-motion-trackers/counter",
        subjects=coh1 + coh2,
    )
    pose_coh, pose_coh_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/imu",
        pattern_template="imu_{}_*.hdf5",
        dataset_name="mvn-analyze/xsens-pose/counter",
        subjects=coh1 + coh2,
    )
    joints_coh, joints_coh_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/imu",
        pattern_template="imu_{}_*.hdf5",
        dataset_name="mvn-analyze/xsens-joints/counter",
        subjects=coh1 + coh2,
    )
    linear_segments_coh, linear_segments_coh_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/imu",
        pattern_template="imu_{}_*.hdf5",
        dataset_name="mvn-analyze/xsens-linear-segments/counter",
        subjects=coh1 + coh2,
    )
    angular_segments_coh, angular_segments_coh_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/imu",
        pattern_template="imu_{}_*.hdf5",
        dataset_name="mvn-analyze/xsens-angular-segments/counter",
        subjects=coh1 + coh2,
    )
    com_coh, com_coh_tot = read_hdf5_dataset_missingness(
        folder_path="./visualizations/data/imu",
        pattern_template="imu_{}_*.hdf5",
        dataset_name="mvn-analyze/xsens-com/counter",
        subjects=coh1 + coh2,
    )

    emg_coh, emg_coh_tot = read_hdf5_dataset_missingness_emg(
        folder_path="./visualizations/data/emg",
        pattern_template="emg_{}_*.hdf5",
        dataset_name="emgs/cometa-emg/emg",
        subjects=coh1 + coh2,
    )

    data = [
        np.concatenate((cam1_coh1, cam1_coh2)),
        np.concatenate((cam2_coh1, cam2_coh2)),
        np.concatenate((cam3_coh1, cam3_coh2)),
        np.concatenate((cam4_coh1, cam4_coh2)),
        ego_coh,
        gaze_coh,
        pupil_coh,
        # blinks_coh,
        # fixations_coh,
        insole_coh,
        imu_coh,
        pose_coh,
        joints_coh,
        linear_segments_coh,
        angular_segments_coh,
        com_coh,
        emg_coh,
        np.array([0]),
    ]

    names = [
        "Camera 1",
        "Camera 2",
        "Camera 3",
        "Camera 4",
        "Ego vision",
        "Gaze",
        "Pupils",
        # "Blinks",
        # "Fixations",
        "Insole pressure",
        "9-DOF IMU",
        "3D pose",
        "Joint angles",
        "Linear segments",
        "Angular segments",
        "Center of mass",
        "sEMG",
        "Telemetry",
    ]

    colors = {
        "Camera 1": "rgb(127, 127, 127)",
        "Camera 2": "rgb(227, 119, 194)",
        "Camera 3": "rgb(140, 86, 75)",
        "Camera 4": "rgb(148, 103, 189)",
        "Ego vision": "rgb(214, 39, 40)",
        "Gaze": "rgb(44, 160, 44)",
        "Pupils": "rgb(255, 127, 14)",
        "Blinks": "rgb(31, 119, 180)",
        "Fixations": "rgb(23, 190, 207)",
        "Insole pressure": "rgb(188, 189, 34)",
        "9-DOF IMU": "rgb(127, 127, 127)",
        "3D pose": "rgb(227, 119, 194)",
        "Joint angles": "rgb(140, 86, 75)",
        "Linear segments": "rgb(148, 103, 189)",
        "Angular segments": "rgb(214, 39, 40)",
        "Center of mass": "rgb(44, 160, 44)",
        "sEMG": "rgb(255, 127, 14)",
        "Telemetry": "rgb(31, 119, 180)",
    }

    annotations = [
        np.concatenate((cam1_coh1, cam1_coh2)).sum()
        / (cam1_tot + np.concatenate((cam1_coh1, cam1_coh2)).sum()),
        np.concatenate((cam2_coh1, cam2_coh2)).sum()
        / (cam2_tot + np.concatenate((cam2_coh1, cam2_coh2)).sum()),
        np.concatenate((cam3_coh1, cam3_coh2)).sum()
        / (cam3_tot + np.concatenate((cam3_coh1, cam3_coh2)).sum()),
        np.concatenate((cam4_coh1, cam4_coh2)).sum()
        / (cam4_tot + np.concatenate((cam4_coh1, cam4_coh2)).sum()),
        ego_coh.sum() / (ego_coh_tot + ego_coh.sum()),
        gaze_coh.sum() / (gaze_coh_tot + gaze_coh.sum()),
        pupil_coh.sum() / (pupil_coh_tot + pupil_coh.sum()),
        # blinks_coh.sum() / blinks_coh_tot,
        # fixations_coh.sum() / fixations_coh_tot,
        insole_coh.sum() / (insole_coh_tot + insole_coh.sum()),
        imu_coh.sum() / (imu_coh_tot + imu_coh.sum()),
        pose_coh.sum() / (pose_coh_tot + pose_coh.sum()),
        joints_coh.sum() / (joints_coh_tot + joints_coh.sum()),
        linear_segments_coh.sum()
        / (linear_segments_coh_tot + linear_segments_coh.sum()),
        angular_segments_coh.sum()
        / (angular_segments_coh_tot + angular_segments_coh.sum()),
        com_coh.sum() / (com_coh_tot + com_coh.sum()),
        emg_coh.sum() / (emg_coh_tot + emg_coh.sum()),
        0,
    ]

    new_annotations = []
    padding = 0.2

    fig = go.Figure()
    for i, (data_line, name) in enumerate(zip(data, names)):
        # Offset y-coordinates by trace index for ridgeline effect
        y_offset = (len(data) - i - 1) * (1 + padding)

        # Check if data is empty or just contains [0]
        if len(data_line) <= 1 or (len(data_line) == 1 and data_line[0] == 0):
            # Add a flat line at y_offset
            fig.add_trace(
                go.Scatter(
                    x=[1, 40],  # Adjust the x-range to match your plot
                    y=[y_offset, y_offset],
                    mode="lines",
                    line=dict(color=colors[name], width=1),
                    name=name,
                    hoverinfo="name",
                )
            )
        else:
            x_hist, y_hist = create_histogram_trace(data_line, bin_width=1)
            fig.add_trace(
                go.Scatter(
                    x=x_hist,
                    y=y_hist + y_offset,
                    fill="toself",
                    line=dict(color=colors[name], width=1),
                    mode="lines",
                    name=name,
                    hoverinfo="x+name",
                )
            )

        if annotations[i] < 1e-6:
            text = f"{annotations[i]*1e9:.0f} ppb"
        elif annotations[i] < 1e-3:
            text = f"{annotations[i]*1e6:.0f} ppm"
        elif annotations[i] < 1e0:
            text = f"{annotations[i]*1e3:.0f} ppt"
        else:
            text = f"{annotations[i]*1e3:.0f} pph"

        new_annotations.append(
            dict(
                x=40,
                y=y_offset + 0.5,  # y position corresponds to trace index
                text=text,
                showarrow=False,
                xanchor="right",
                xshift=-5,  # Shift text 10 pixels to the right
                font=dict(size=20, family="Linux Libertine O"),
            )
        )

    fig.update_layout(
        xaxis_showgrid=False,
        yaxis_showgrid=False,
        xaxis_zeroline=False,
        showlegend=False,
        legend_traceorder="reversed",
        font=dict(size=22, family="Linux Libertine O"),
        xaxis=dict(
            title=dict(
                text="# Consecutive dropped samples",
                font=dict(size=24, family="Linux Libertine O"),
            ),  # Y-axis title
            range=[1, 40],
            tickmode="array",
            tickvals=[1, 5, 10, 15, 20, 25, 30, 35, 40],
            tickfont=dict(size=18),
        ),
        yaxis=dict(
            tickvals=[
                (len(names) - i - 1) * (1 + padding) + 0.5 for i in range(len(names))
            ],  # Align with baselines
            ticktext=names,
        ),
        height=800,
        width=700,
        annotations=new_annotations,
    )

    fig.show()
