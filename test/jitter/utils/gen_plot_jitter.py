import argparse
from io import TextIOWrapper
import h5py
import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


def analyze_jitter(log_file: TextIOWrapper, group_name: str, series_name: str, file_path: str, dataset_path: str, sequence_path: str):
    """
    Reads timestamp data from an HDF5 file, performs a linear fit,
    and returns the jitter and related statistics.

    Args:
        log_file (TextIOWrapper): Open file handle for writing log information.
        group_name (str): Name of the group for plotting.
        series_name (str): Name of the series for plotting.
        file_path (str): Path to the HDF5 file.
        dataset_path (str): Path to the timestamp dataset within the HDF5 file
                            (e.g., '/my_producer/my_device/process_time_s').
        sequence_path (str): Path to the sequence number dataset.
    """
    try:
        with h5py.File(file_path, 'r') as f:
            if dataset_path not in f:
                print(f"Error: Dataset '{dataset_path}' not found in '{file_path}'.")
                print("Available datasets:")
                def print_name(name):
                    print(name)
                f.visit(print_name)
                return None

            timestamps = f[dataset_path][:]
            if sequence_path:
                indices = f[sequence_path][:]
            else:
                indices = np.arange(0)

    except Exception as e:
        print(f"Error reading HDF5 file: {e}")
        return None

    if timestamps.ndim > 1:
        timestamps = timestamps.flatten()

    num_samples = len(timestamps)
    if num_samples < 2:
        print("Error: Need at least two data points to perform a fit.")
        return None

    if indices.ndim > 1:
        indices = indices.flatten()

    if len(indices) != num_samples:
        print(f"Warning: Timestamp and counter datasets have different lengths ({num_samples} vs {len(indices)}).")
        print("Falling back to sequential indices.")
        indices = np.arange(num_samples)

    # Perform a first-order (linear) polynomial fit
    slope, intercept = np.polyfit(indices, timestamps, 1)
    fit_line = slope * indices + intercept

    # Calculate residuals (jitter)
    residuals = timestamps - fit_line

    # Convert residuals to milliseconds for better readability
    residuals_ms = residuals * 1000

    # Calculate statistics
    p50_jitter_ms, p90_jitter_ms, p95_jitter_ms, p99_jitter_ms = np.percentile(residuals_ms, [50, 90, 95, 99])
    mean_jitter_ms = np.mean(residuals_ms)
    std_jitter_ms = np.std(residuals_ms)
    sampling_rate_hz = 1 / slope

    print("--- Timing Jitter Analysis ---")
    print(f"File: {file_path}")
    print(f"Dataset: {dataset_path}")
    print(f"Number of samples: {num_samples}")
    print(f"Estimated sampling rate: {sampling_rate_hz:.4f} Hz")
    print(f"Sampling period (slope): {slope*1000:.4f} ms")
    print(f"Mean jitter: {mean_jitter_ms:.4f} ms")
    print(f"Jitter (std dev): {std_jitter_ms:.4f} ms")
    print(f"Median jitter: {p50_jitter_ms:.4f} ms")
    print(f"Jitter (P95): {p95_jitter_ms:.4f} ms")
    print(f"Jitter (P99): {p99_jitter_ms:.4f} ms")
    print("------------------------------")
    log_file.write(
        f"{group_name},{series_name},{sampling_rate_hz},{slope*1000},{num_samples},"
        f"{mean_jitter_ms},{std_jitter_ms},{np.min(residuals_ms)},{np.max(residuals_ms)},"
        f"{p50_jitter_ms},{p90_jitter_ms},{p95_jitter_ms},{p99_jitter_ms}\n"
    )

    return {
        "residuals_ms": residuals_ms[residuals_ms < p99_jitter_ms],
        "indices": indices[residuals_ms < p99_jitter_ms],
        "label": series_name,
        "group": group_name,
    }


def plot_multiple_jitters(jitter_data_list: list[dict]):
    """Plots multiple jitter distributions side-by-side."""

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman"],
            "font.size": 12,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "legend.fontsize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "lines.markersize": 5,
        }
    )

    # Dynamically adjust figure width based on the number of plots
    fig_width = max(7, 2.5 * len(jitter_data_list))
    fig, ax = plt.subplots(figsize=(fig_width, 8))

    labels = [d['label'] for d in jitter_data_list]
    group_xloc = {group: [] for group in set([d['group'] for d in jitter_data_list])}
    scatter_artist = None

    for i, data in enumerate(jitter_data_list):
        residuals_ms = data['residuals_ms']
        indices = data['indices']
        group_xloc[data['group']].append(i)

        max_index = indices.max() if indices.size > 0 else 1

        # 1. Bin the jitter data to create vertical slots for the swarm
        num_bins = 300  # Bins for vertical resolution
        bins = np.linspace(residuals_ms.min(), residuals_ms.max(), num_bins)
        binned_jitter_indices = np.digitize(residuals_ms, bins)

        # 2. Group original sample indices by the jitter bin they fall into
        points_in_bins = [[] for _ in range(num_bins + 1)]
        for idx, bin_num in enumerate(binned_jitter_indices):
            points_in_bins[bin_num].append(indices[idx])

        # 3. For each bin, sort points by time and assign x-coordinates for the swarm
        all_x, all_y, all_colors = [], [], []
        for bin_num, points in enumerate(points_in_bins):
            if not points:
                continue

            points.sort()  # Sort by sample index (time)
            y_val = bins[bin_num - 1] if bin_num > 0 else bins[0]

            points_left = points[::2]
            points_right = points[1::2]

            x_right = np.arange(1, len(points_right) + 1)
            all_x.extend(x_right)
            all_y.extend([y_val] * len(points_right))
            all_colors.extend(np.array(points_right) / max_index * 100)

            x_left = -np.arange(1, len(points_left) + 1)
            all_x.extend(x_left)
            all_y.extend([y_val] * len(points_left))
            all_colors.extend(np.array(points_left) / max_index * 100)

        # Normalize the width of the swarm plot to prevent overlap
        max_abs_x = np.max(np.abs(all_x)) if all_x else 1.0
        violin_body_width = 0.8  # The width of the violin body on the x-axis

        # Scale x coordinates to fit within the violin body width and shift to position 'i'
        shifted_x = [(x / max_abs_x * (violin_body_width / 2)) + i for x in all_x]

        # 4. Create the scatter plot
        scatter_artist = ax.scatter(shifted_x, all_y, c=all_colors, cmap='copper', s=2, alpha=0.8, zorder=1)

        # 5. Add a box plot inside the violin
        ax.boxplot(
            residuals_ms,
            positions=[i],
            vert=True,
            patch_artist=True,
            showmeans=True,
            showfliers=False,
            widths=0.1, # A fixed width that looks good inside the violin
            meanprops={"visible": False},
            boxprops={
                "facecolor": "limegreen",
                "edgecolor": "limegreen",
                "alpha": 0.8
            },
            whiskerprops={"color": "limegreen", "linewidth": 1.5},
            capprops={"visible": False},
            medianprops={"color": "white", "linewidth": 1.5},
            zorder=2
        )

    # Customize the plot aesthetics
    ax.set_title('Temporal Evolution of Time-of-Arrival Jitter Distribution Across Heterogeneous Modalities', fontsize=14)
    ax.set_ylabel('Time-of-Arrival Jitter (ms)', fontsize=14)
    # To position the x-axis label below the secondary ticks, add `labelpad`.
    # You can also set the font size for the label here.
    ax.set_xlabel('Modality', labelpad=32, fontsize=14)
    ax.set_xticks(np.arange(len(jitter_data_list)))
    ax.set_xticklabels(labels)
    # To change the font size of the primary (top) tick labels:
    # ax.tick_params(axis='x', labelsize=12)
    ax.grid(True, which="both", axis="y", linestyle="--", linewidth=0.5)
    sec = ax.secondary_xaxis(location=0)
    sec.set_xticks(
        ticks=list(map(lambda vals: sum(vals)/len(vals), group_xloc.values())),
        labels=map(lambda k: f"\n\n{k}", group_xloc.keys()),
    )
    # To change the font size of the secondary (group) tick labels and remove the tick marks:
    # sec.tick_params(axis='x', labelsize=10, length=0)
    sec2 = ax.secondary_xaxis(location=0)
    sec2.set_xticks([-0.5, *[vals[-1]+0.5 for vals in group_xloc.values()]], labels=[])
    sec2.tick_params('x', length=40, width=1.0)

    # Add a color bar to show the mapping from color to time (sample index)
    if scatter_artist:
        cbar = fig.colorbar(scatter_artist, ax=ax)
        cbar.set_label('Temporal Evolution of the Recording (%)', fontsize=14)

    fig.tight_layout()

    plt.show()
    print("Done.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Analyze and plot timestamp jitter from an HDF5 file.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--out',
        '-o',
        type=str,
        required=True,
        help="Output folder path. Doesn't have to exist."
    )
    parser.add_argument(
        '--group',
        '-g',
        action='append',
        type=str,
        required=True,
        help="Grouping by host device name. Can be specified multiple times."
    )
    parser.add_argument(
        '--name',
        '-n',
        action='append',
        type=str,
        required=True,
        help="Name for the dataset. Can be specified multiple times."
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
        '--dataset',
        '-d',
        action='append',
        type=str,
        required=True,
        help="Path to the timestamp dataset. Must be specified for each file.\n"
             "Example: '/MyProducer/MyDevice/toa_s'. Can be specified multiple times."
    )
    parser.add_argument(
        '--sequence',
        '-s',
        action='append',
        type=str,
        required=True,
        help="Path to the sequence dataset. Can be specified multiple times.\n"
             "Example: '/MyProducer/MyDevice/counter'."
    )

    args = parser.parse_args()

    if (len(args.sequence) != len(args.file) or 
        len(args.dataset) != len(args.file) or
        len(args.name) != len(args.file) or
        len(args.group) != len(args.file)
    ):
        sys.exit("Error: The number of --group, --name, --file, and --dataset arguments must match.")

    jitter_data_list = []
    out_folder = Path(args.out)
    out_folder.mkdir(parents=True, exist_ok=True)

    with open(
        Path(out_folder, "stats.csv"), "w"
    ) as f:
        f.write("group,name,rate,period,num_samples,mean,std,min,max,p50,p90,p95,p99\n")
        for i in range(len(args.file)):
            data = analyze_jitter(f, args.group[i], args.name[i], args.file[i], args.dataset[i], args.sequence[i])
            if data:
                jitter_data_list.append(data)

    if jitter_data_list:
        plot_multiple_jitters(jitter_data_list)
    else:
        print("No valid data could be analyzed. Exiting.")
