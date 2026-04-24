import argparse
from io import TextIOWrapper
import os
import h5py
import sys
import numpy as np
from pathlib import Path


def log_jitter(log_file: TextIOWrapper, file_path: str, dataset_path: str, sequence_path: str):
    """
    Reads timestamp data from an HDF5 file, performs a linear fit,
    and returns the jitter and related statistics.

    Args:
        log_file (TextIOWrapper): Open file handle for writing log information.
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

    log_file.write(
        f"{sampling_rate_hz},{slope*1000},{num_samples},"
        f"{mean_jitter_ms},{std_jitter_ms},{np.min(residuals_ms)},{np.max(residuals_ms)},"
        f"{p50_jitter_ms},{p90_jitter_ms},{p95_jitter_ms},{p99_jitter_ms}\n"
    )


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
        '--file',
        '-f',
        type=str,
        required=True,
        help="Path to the HDF5 file. Can be specified multiple times."
    )
    parser.add_argument(
        '--dataset',
        '-d',
        type=str,
        required=True,
        help="Path to the timestamp dataset. Must be specified for each file.\n"
             "Example: '/MyProducer/MyDevice/toa_s'. Can be specified multiple times."
    )
    parser.add_argument(
        '--sequence',
        '-s',
        type=str,
        required=True,
        help="Path to the sequence dataset. Can be specified multiple times.\n"
             "Example: '/MyProducer/MyDevice/counter'."
    )

    args = parser.parse_args()

    out_folder = Path(args.out)
    out_folder.mkdir(parents=True, exist_ok=True)

    with open(
        Path(out_folder, "stats.csv"), "a"
    ) as f:
        if f.tell() == 0:  # Only write header if file is new/empty
            f.write("rate,period,num_samples,mean,std,min,max,p50,p90,p95,p99\n")
        log_jitter(f, args.file, args.dataset, args.sequence)
