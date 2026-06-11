import argparse
from pathlib import Path
import time
import h5py
from matplotlib.ticker import FuncFormatter
import numpy as np
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt


def read_hdf5_dataset(filename: Path, dataset_name: str) -> np.ndarray:
    with h5py.File(filename, "r") as f:
        return np.array(f[dataset_name])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file_path", type=str)

    args = parser.parse_args()

    file_path = Path(args.file_path)

    ai_predictions = read_hdf5_dataset(file_path, "ai/pytorch-worker/prediction")[
        :, 0
    ].astype(int)
    ai_process_times = read_hdf5_dataset(file_path, "ai/pytorch-worker/process_time_s")[
        :, 0
    ]
    ai_inference_latency = read_hdf5_dataset(
        file_path, "ai/pytorch-worker/inference_latency_s"
    )[:, 0]

    print(f"AI inference latency (s): {ai_inference_latency[1:].mean():.6f} ± {ai_inference_latency[1:].std():.6f}", flush=True)
    print(f"AI inference latency percentiles (s): {', '.join(f'{p:.6f}' for p in np.percentile(ai_inference_latency[1:], [50, 90, 95, 99]))}", flush=True)

    imu_toa = read_hdf5_dataset(file_path, "dots/dots-imu/toa_s")
    imu_acc = read_hdf5_dataset(file_path, "dots/dots-imu/acceleration")

    imu_acc = imu_acc[~np.isnan(imu_toa[:, 0]), 0]
    imu_toa = imu_toa[~np.isnan(imu_toa[:, 0]), 0]

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman"],  # A common font for papers
            "font.size": 12,
            "axes.titlesize": 16,
            "axes.labelsize": 14,
            "legend.fontsize": 12,
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
            "figure.figsize": (12, 4),
            "lines.markersize": 5,
        }
    )

    colors = plt.get_cmap("tab10").colors

    fig, ax = plt.subplots()

    time_fmt_fn = lambda s, _: time.strftime("%H:%M:%S", time.gmtime(s))
    formatter = FuncFormatter(time_fmt_fn)

    x = imu_toa - imu_toa[0]
    ax.plot(x, imu_acc[:, 0], label="Pelvis IMU [X]", color=colors[0], linewidth=1.0)
    # ax.plot(imu_toa, imu_acc[:, 1], label="IMU Accel Y", color=colors[1], linewidth=1.0)
    # ax.plot(imu_toa, imu_acc[:, 2], label="IMU Accel Z", color=colors[2], linewidth=1.0)

    duration = imu_toa[-1] - imu_toa[0]
    ax.xaxis.set_major_formatter(formatter)
    ax.set_xlim(0, duration)
    ax.set_xticks(np.arange(0, duration + 1, 900))
    ax.set_xlabel("Time since start (hh:mm:ss)")
    ax.set_ylabel("Acceleration (m/s²)")
    ax.set_title(
        "Realtime TCN FoG Classifier from 5 IMU Sensors on 3-hour Free-Living Activities"
    )
    ax.grid(True, which="both", axis="both", linestyle="--", linewidth=0.5)

    ai_toa = ai_process_times - imu_toa[0]
    pred_diff = np.diff(ai_predictions, prepend=0, append=0)
    pred_start = (pred_diff == 1).nonzero()[0]
    pred_end = (pred_diff == -1).nonzero()[0] - 1

    for start, end in zip(pred_start, pred_end):
        ax.axvspan(ai_toa[start], ai_toa[end], color=colors[3], alpha=0.3)

    ymin, ymax = ax.get_ylim()

    # Inset Axes
    x1, x2, y1, y2 = 98 * 60 + 50, 99 * 60 + 10, 7, 11
    axins = ax.inset_axes(
        [0.59, 0.45, 0.4, 0.5], xlim=(x1, x2), ylim=(y1, y2), xticks=[], yticks=[]
    )

    region = np.logical_and(x1 < x, x < x2)
    axins.plot(x[region], imu_acc[region, 0], color=colors[0], linewidth=1.0)

    ai_region = np.logical_and(x1 < ai_toa, ai_toa < x2)
    region_ai_toa = ai_toa[ai_region]
    region_ai_predictions = ai_predictions[ai_region]
    region_pred_diff = np.diff(region_ai_predictions, prepend=0, append=0)
    region_pred_start = (region_pred_diff == 1).nonzero()[0]
    region_pred_end = (region_pred_diff == -1).nonzero()[0] - 1

    for start, end in zip(region_pred_start, region_pred_end):
        axins.axvspan(
            region_ai_toa[start], region_ai_toa[end], color=colors[3], alpha=0.3
        )

    # Make the border of the inset and the zoom indicator lines thicker
    ax.indicate_inset_zoom(axins, edgecolor="black", linewidth=1.5, alpha=1.0)
    for spine in axins.spines.values():
        spine.set_linewidth(1.5)

    handles, _ = ax.get_legend_handles_labels()
    fog_patch = mpatches.Patch(color=colors[3], alpha=0.3, label="Detected FoG")
    handles.append(fog_patch)
    ax.legend(handles=handles)

    fig.tight_layout()

    plt.show()
    print("Done.")
