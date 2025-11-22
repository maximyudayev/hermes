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
    parser.add_argument("val", type=int)
    parser.add_argument("is_freq", type=int)

    args = parser.parse_args()

    folder = os.path.dirname(os.path.realpath(__file__))

    if args.is_freq == 1:
        with open(Path(folder, "data/latency/latency_vs_frequency.txt"), "a") as f:
            producer_times, producer_sequences = read_hdf5_dataset(
                filename=Path(
                    folder, "data/latency/run_latency_vs_frequency/dummy-producer.hdf5"
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            consumer_times, consumer_sequences = read_hdf5_dataset(
                filename=Path(
                    folder, "data/latency/run_latency_vs_frequency/dummy-consumer.hdf5"
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            mean_gen_rate = np.mean(np.diff(producer_times, axis=0))
            if (
                mean_gen_rate < 1 / args.val * 1.05
                and mean_gen_rate > 1 / args.val * 0.95
            ):
                diff = (
                    consumer_times[:, 0]
                    - producer_times[:, 0][consumer_sequences[:, 0]]
                )
                f.write(
                    f"{args.val},{np.mean(diff)},{np.std(diff)},{np.min(diff)},{np.max(diff)},{np.median(diff)}\n"
                )
            else:
                print(f"Experiment couldnt generate packets at {args.val}Hz")

    elif args.is_freq == 0:
        with open(Path(folder, "data/latency/latency_vs_msgsize.txt"), "a") as f:
            rate = 100
            producer_times, producer_sequences = read_hdf5_dataset(
                filename=Path(
                    folder, "data/latency/run_latency_vs_msgsize/dummy-producer.hdf5"
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            consumer_times, consumer_sequences = read_hdf5_dataset(
                filename=Path(
                    folder, "data/latency/run_latency_vs_msgsize/dummy-consumer.hdf5"
                ),
                dataset_name="dummy-producer/sensor-emulator",
            )
            mean_gen_rate = np.mean(np.diff(producer_times, axis=0))
            if mean_gen_rate < 1 / rate * 1.05 and mean_gen_rate > 1 / rate * 0.95:
                diff = (
                    consumer_times[:, 0]
                    - producer_times[:, 0][consumer_sequences[:, 0]]
                )
                f.write(
                    f"{args.val},{np.mean(diff)},{np.std(diff)},{np.min(diff)},{np.max(diff)},{np.median(diff)}\n"
                )
            else:
                print(
                    f"Experiment {args.val} couldnt generate packets at 100Hz for msg {args.val} bytes"
                )
