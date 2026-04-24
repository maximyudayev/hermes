import numpy as np
import h5py
from pathlib import Path
import argparse
import os


def read_hdf5_dataset(
    filename: Path, dataset_name=None
) -> tuple[np.ndarray, np.ndarray]:
    with h5py.File(filename, "r") as f:
        modality = f[dataset_name]
        return np.array(modality["process_time_s"]), np.array(modality["sequence"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("base_path", type=str)
    parser.add_argument("trial", type=int)
    parser.add_argument("freq", type=int)
    parser.add_argument("bytes", type=int)
    parser.add_argument("is_freq", type=int)

    args = parser.parse_args()


    if args.is_freq == 1:
        with open(
            Path(f"{args.base_path}/latency_vs_frequency.csv"), "a"
        ) as f:
            if f.tell() == 0:
                f.write("value,mean,std,min,max,med,p50,p90,p95,p99\n")

            producer_times, producer_sequences = read_hdf5_dataset(
                filename=Path(
                    f"{args.base_path}/run_latency_vs_frequency/trial_{args.trial}/dummy-producer.hdf5",
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            consumer_times, consumer_sequences = read_hdf5_dataset(
                filename=Path(
                    f"{args.base_path}/run_latency_vs_frequency/trial_{args.trial}/dummy-consumer.hdf5",
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )

            mean_gen_rate = np.mean(np.diff(producer_times, axis=0))
            if (
                mean_gen_rate < 1 / args.freq * 1.05
                and mean_gen_rate > 1 / args.freq * 0.95
            ):
                diff = (
                    consumer_times[:, 0]
                    - producer_times[:, 0][consumer_sequences[:, 0]]
                )

                p50, p90, p95, p99 = np.percentile(diff, [50, 90, 95, 99])
                f.write(
                    f"{args.freq},"
                    f"{np.mean(diff)},"
                    f"{np.std(diff)},"
                    f"{np.min(diff)},"
                    f"{np.max(diff)},"
                    f"{np.median(diff)},"
                    f"{p50},{p90},{p95},{p99}\n"
                )
            else:
                print(f"Experiment couldnt generate packets at {args.freq}Hz")

    elif args.is_freq == 0:
        with open(
            Path(f"{args.base_path}/latency_vs_msgsize.csv"), "a"
        ) as f:
            if f.tell() == 0:
                f.write("value,mean,std,min,max,med,p50,p90,p95,p99\n")

            producer_times, producer_sequences = read_hdf5_dataset(
                filename=Path(
                    f"{args.base_path}/run_latency_vs_msgsize/trial_{args.trial}/dummy-producer.hdf5",
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            consumer_times, consumer_sequences = read_hdf5_dataset(
                filename=Path(
                    f"{args.base_path}/run_latency_vs_msgsize/trial_{args.trial}/dummy-consumer.hdf5",
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            mean_gen_rate = np.mean(np.diff(producer_times, axis=0))
            if mean_gen_rate < 1 / args.freq * 1.05 and mean_gen_rate > 1 / args.freq * 0.95:
                diff = (
                    consumer_times[:, 0]
                    - producer_times[:, 0][consumer_sequences[:, 0]]
                )
                p50, p90, p95, p99 = np.percentile(diff, [50, 90, 95, 99])
                f.write(
                    f"{args.bytes},"
                    f"{np.mean(diff)},"
                    f"{np.std(diff)},"
                    f"{np.min(diff)},"
                    f"{np.max(diff)},"
                    f"{np.median(diff)},"
                    f"{p50},{p90},{p95},{p99}\n"
                )
            else:
                print(
                    f"Experiment {args.bytes} couldnt generate packets at 100Hz for msg {args.bytes} bytes"
                )
