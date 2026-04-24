############
#
# Copyright (c) 2024-2026 Maxim Yudayev and KU Leuven eMedia Lab
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

import pandas as pd
import numpy as np
import h5py
from pathlib import Path
import argparse
import matplotlib.pyplot as plt
import os


def read_hdf5_dataset(
    filename: Path, dataset_name=None
) -> tuple[np.ndarray, np.ndarray]:
    with h5py.File(filename, "r") as f:
        modality = f[dataset_name]
        return np.array(modality["process_time_s"]), np.array(modality["sequence"])


def apply_rolling_minimum_filter(
    df: pd.DataFrame,
    time_col: str,
    latency_col: str,
    window_seconds: int,
    physical_floor_ms: float,
) -> pd.DataFrame:
    df['timestamp_dt'] = pd.to_datetime(df[time_col], unit='s')

    # Set it as the index
    df = df.set_index('timestamp_dt')

    # 1. Calculate the rolling minimum (The 'Envelope')
    # We center the window so the offset correction is symmetric around the data point
    window_str = f'{window_seconds}s'
    rolling_min = df[latency_col].rolling(window=window_str, center=True, min_periods=1).min()

    # 2. Subtract the wandering baseline
    # If the rolling min is -4ms, we subtract -4ms (which adds 4ms to the raw value)
    df["offset_corrected_latency"] = df[latency_col] - rolling_min

    # 3. Add back the physical reality floor
    df["final_corrected_latency"] = df["offset_corrected_latency"] + physical_floor_ms

    return df.reset_index()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("base_path", type=str)
    parser.add_argument("trial", type=int)
    parser.add_argument("val", type=int)
    parser.add_argument("is_freq", type=int)
    parser.add_argument("floor", type=float)

    args = parser.parse_args()

    folder = os.path.dirname(os.path.realpath(__file__))

    if args.is_freq == 1:
        with open(
            Path(folder, f"../{args.base_path}/latency_vs_frequency.csv"), "a"
        ) as f:
            if f.tell() == 0:
                f.write("value,mean,std,min,max,med,p50,p90,p95,p99\n")

            producer_times, producer_sequences = read_hdf5_dataset(
                filename=Path(
                    folder,
                    f"../{args.base_path}/run_latency_vs_frequency/trial_{args.trial}/dummy-producer.hdf5",
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            consumer_times, consumer_sequences = read_hdf5_dataset(
                filename=Path(
                    folder,
                    f"../{args.base_path}/run_latency_vs_frequency/trial_{args.trial}/dummy-consumer.hdf5",
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )

            mean_gen_rate = np.mean(np.diff(producer_times, axis=0))
            if (
                mean_gen_rate < 1 / args.val * 1.05
                and mean_gen_rate > 1 / args.val * 0.95
            ):
                raw_diff = (
                    consumer_times[:, 0]
                    - producer_times[:, 0][consumer_sequences[:, 0]]
                )

                my_data = pd.DataFrame(
                    {
                        "timestamp": producer_times[:, 0][consumer_sequences[:, 0]],
                        "raw_delay_ms": raw_diff,
                    }
                )

                # Dynamic windowing
                window_seconds = max(0.5, min(10, 200/args.val))

                corrected_data = apply_rolling_minimum_filter(
                    my_data, "timestamp", "raw_delay_ms", window_seconds, args.floor
                )

                plt.figure(figsize=(12, 6))
                plt.plot(
                    corrected_data["timestamp"],
                    corrected_data["raw_delay_ms"],
                    label="Raw Latency",
                )
                plt.plot(
                    corrected_data["timestamp"],
                    corrected_data["final_corrected_latency"],
                    label="Corrected Latency",
                )
                plt.title(f"Raw vs Corrected Latency (Message Size: {args.val} bytes)")
                plt.xlabel("Timestamp (s)")
                plt.ylabel("Latency (ms)")
                plt.legend()
                plt.grid(True)
                plt.show()

                p50, p90, p95, p99 = np.percentile(
                    corrected_data["final_corrected_latency"], [50, 90, 95, 99]
                )
                raw_p50, raw_p90, raw_p95, raw_p99 = np.percentile(
                    raw_diff, [50, 90, 95, 99]
                )

                f.write(
                    f"{args.val},"
                    f"{np.mean(corrected_data['final_corrected_latency'])},"
                    f"{np.std(corrected_data['final_corrected_latency'])},"
                    f"{np.min(corrected_data['final_corrected_latency'])},"
                    f"{np.max(corrected_data['final_corrected_latency'])},"
                    f"{np.median(corrected_data['final_corrected_latency'])},"
                    f"{p50},{p90},{p95},{p99},"
                    f"{np.mean(raw_diff)},"
                    f"{np.std(raw_diff)},"
                    f"{np.min(raw_diff)},"
                    f"{np.max(raw_diff)},"
                    f"{np.median(raw_diff)},"
                    f"{raw_p50},{raw_p90},{raw_p95},{raw_p99}\n"
                )
            else:
                print(f"Experiment couldnt generate packets at {args.val}Hz")

    elif args.is_freq == 0:
        with open(
            Path(folder, f"../{args.base_path}/latency_vs_msgsize.csv"), "a"
        ) as f:
            if f.tell() == 0:
                f.write("value,mean,std,min,max,med,p50,p90,p95,p99\n")

            rate = 100
            producer_times, producer_sequences = read_hdf5_dataset(
                filename=Path(
                    folder,
                    f"../{args.base_path}/run_latency_vs_msgsize/trial_{args.trial}/dummy-producer.hdf5",
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            consumer_times, consumer_sequences = read_hdf5_dataset(
                filename=Path(
                    folder,
                    f"../{args.base_path}/run_latency_vs_msgsize/trial_{args.trial}/dummy-consumer.hdf5",
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            mean_gen_rate = np.mean(np.diff(producer_times, axis=0))
            if mean_gen_rate < 1 / rate * 1.05 and mean_gen_rate > 1 / rate * 0.95:
                raw_diff = (
                    consumer_times[:, 0]
                    - producer_times[:, 0][consumer_sequences[:, 0]]
                )

                my_data = pd.DataFrame(
                    {
                        "timestamp": producer_times[:, 0][consumer_sequences[:, 0]],
                        "raw_delay_ms": raw_diff,
                    }
                )

                # Dynamic windowing
                window_seconds = max(0.5, min(10, 200/rate))

                corrected_data = apply_rolling_minimum_filter(
                    my_data, "timestamp", "raw_delay_ms", window_seconds, args.floor
                )

                p50, p90, p95, p99 = np.percentile(
                    corrected_data["final_corrected_latency"], [50, 90, 95, 99]
                )

                raw_p50, raw_p90, raw_p95, raw_p99 = np.percentile(
                    raw_diff, [50, 90, 95, 99]
                )

                f.write(
                    f"{args.val},"
                    f"{np.mean(corrected_data['final_corrected_latency'])},"
                    f"{np.std(corrected_data['final_corrected_latency'])},"
                    f"{np.min(corrected_data['final_corrected_latency'])},"
                    f"{np.max(corrected_data['final_corrected_latency'])},"
                    f"{np.median(corrected_data['final_corrected_latency'])},"
                    f"{p50},{p90},{p95},{p99},"
                    f"{np.mean(raw_diff)},"
                    f"{np.std(raw_diff)},"
                    f"{np.min(raw_diff)},"
                    f"{np.max(raw_diff)},"
                    f"{np.median(raw_diff)},"
                    f"{raw_p50},{raw_p90},{raw_p95},{raw_p99}\n"
                )
            else:
                print(
                    f"Experiment {args.val} couldnt generate packets at 100Hz for msg {args.val} bytes"
                )
