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
# Created 2024-2026 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Maxim Yudayev [https://yudayev.com].
#
# ############

import argparse
from pathlib import Path
import numpy as np
import os
import matplotlib.pyplot as plt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("base_path", type=str)

    args = parser.parse_args()

    folder_path = os.path.dirname(os.path.realpath(__file__))
    root_folder = Path(folder_path, f"../{args.base_path}")
    folders = root_folder.glob("*")

    latency = dict()

    for folder in folders:
        subfolders = folder.glob("*")
        for subfolder in subfolders:
            device = subfolder.name
            if os.path.exists(Path(subfolder, "latency_vs_frequency.csv")):
                with open(Path(subfolder, "latency_vs_frequency.csv"), "r") as f:
                    f.readline()  # Skip header
                    data = [
                        line.strip().split(",") for line in f.readlines() if line.strip()
                    ]
                    latency.setdefault(folder.name, dict())
                    latency[folder.name][device] = np.array(data, dtype=float)[:, 1:]
            if os.path.exists(Path(subfolder, "latency_vs_msgsize.csv")):
                with open(Path(subfolder, "latency_vs_msgsize.csv"), "r") as f:
                    f.readline()  # Skip header
                    data = [
                        line.strip().split(",") for line in f.readlines() if line.strip()
                    ]
                    latency.setdefault(folder.name, dict())
                    latency[folder.name][device] = np.array(data, dtype=float)[:, 1:]

    x_freq = [
        1,
        2,
        5,
        10,
        20,
        50,
        100,
        200,
        500,
        1000,
        2000,
        5000,
        10000,
        20000,
        50000,
        100000,
    ]
    x_msg = [
        10,
        20,
        50,
        100,
        200,
        500,
        1000,
        2000,
        5000,
        10000,
        20000,
        50000,
        100000,
        200000,
        500000,
        1000000,
    ]

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman"],  # A common font for papers
            "font.size": 12,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "legend.fontsize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "figure.figsize": (6, 4),
            "lines.markersize": 5,
        }
    )

    colors = plt.get_cmap("tab10").colors

    for f in ['bytes_100', 'bytes_1000', 'bytes_5000', 'bytes_10000', 'rate_1', 'rate_10', 'rate_100', 'rate_1000']:
        fig, ax = plt.subplots()

        cond, val_str = f.split("_")
        val_num = int(val_str)

        if val_num >= 1000:
            val_formatted = f"{val_num // 1000}k"
        else:
            val_formatted = val_str

        for i, (name, data) in enumerate(latency[f].items()):
            color = colors[i % len(colors)]
            mean = data[:, 0] * 1e3  # to ms
            p50 = data[:, 5] * 1e3  # to ms
            p95 = data[:, 7] * 1e3  # to ms
            current_x = x_freq[: len(data)]

            ax.plot(
                current_x, mean, marker="o", linestyle="-", label=name, color=color
            )
            ax.fill_between(
                current_x, p50, p95, alpha=0.2, color=color, edgecolor=None
            )

        ax.set_xscale("log")
        ax.set_title(f"Intra-device Latency w.r.t. {'Frequency' if cond == "bytes" else 'Message Size'} @{val_formatted}{'B' if cond == "bytes" else 'Hz'}")
        ax.set_xlabel("Frequency (Hz)" if cond == "bytes" else "Message Size (bytes)")
        ax.set_ylabel("Latency (ms)")
        ax.set_ylim(0, 3.5)
        ax.legend()
        ax.grid(True, which="both", axis="both", linestyle="--", linewidth=0.5)
        fig.tight_layout()

    plt.show()
    print("Done.")
