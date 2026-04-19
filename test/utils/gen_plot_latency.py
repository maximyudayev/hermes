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
    folder = Path(folder_path, f"../{args.base_path}")
    subfolders = folder.glob("*")

    latency_vs_freq = dict()
    latency_vs_msg = dict()

    for subfolder in subfolders:
        device = subfolder.name
        if os.path.exists(Path(subfolder, "latency_vs_frequency.csv")):
            with open(Path(subfolder, "latency_vs_frequency.csv"), "r") as f:
                f.readline()  # Skip header
                data = [
                    line.strip().split(",") for line in f.readlines() if line.strip()
                ]
                latency_vs_freq[device] = np.array(data, dtype=float)[:, 1:]

        if os.path.exists(Path(subfolder, "latency_vs_msgsize.csv")):
            with open(Path(subfolder, "latency_vs_msgsize.csv"), "r") as f:
                f.readline()  # Skip header
                data = [
                    line.strip().split(",") for line in f.readlines() if line.strip()
                ]
                latency_vs_msg[device] = np.array(data, dtype=float)[:, 1:]

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

    # --- Plot for latency vs frequency ---
    fig_freq, ax_freq = plt.subplots()

    colors = plt.get_cmap("tab10").colors

    for i, (name, data) in enumerate(latency_vs_freq.items()):
        color = colors[i % len(colors)]
        mean = data[:, 0] * 1e3  # to ms
        p50 = data[:, 5] * 1e3  # to ms
        p95 = data[:, 7] * 1e3  # to ms
        current_x_freq = x_freq[: len(data)]

        ax_freq.plot(
            current_x_freq, mean, marker="o", linestyle="-", label=name, color=color
        )
        ax_freq.fill_between(
            current_x_freq, p50, p95, alpha=0.2, color=color, edgecolor=None
        )

    ax_freq.set_xscale("log")
    ax_freq.set_title("Inter-device Latency w.r.t. Frequency @1kB")
    ax_freq.set_xlabel("Frequency (Hz)")
    ax_freq.set_ylabel("Latency (ms)")
    # ax_freq.set_ylim(0, 3.5)
    ax_freq.legend()
    ax_freq.grid(True, which="both", axis="both", linestyle="--", linewidth=0.5)
    fig_freq.tight_layout()

    # --- Plot for latency vs message size ---
    fig_msg, ax_msg = plt.subplots()

    for i, (name, data) in enumerate(latency_vs_msg.items()):
        color = colors[i % len(colors)]
        mean = data[:, 0] * 1e3  # to ms
        p50 = data[:, 5] * 1e3  # to ms
        p95 = data[:, 7] * 1e3  # to ms
        current_x_msg = x_msg[: len(data)]

        ax_msg.plot(
            current_x_msg, mean, marker="o", linestyle="-", label=name, color=color
        )
        ax_msg.fill_between(
            current_x_msg, p50, p95, alpha=0.2, color=color, edgecolor=None
        )

    ax_msg.set_xscale("log")
    ax_msg.set_title("Inter-device Latency w.r.t. Message Size @100Hz")
    ax_msg.set_xlabel("Message Size (bytes)")
    ax_msg.set_ylabel("Latency (ms)")
    ax_msg.set_ylim(0, 10)
    ax_msg.legend()
    ax_msg.grid(True, which="both", axis="both", linestyle="--", linewidth=0.5)
    fig_msg.tight_layout()

    plt.show()
    print("Done.")
