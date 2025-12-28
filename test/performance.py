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

from pathlib import Path
import plotly.graph_objects as go
import numpy as np
import os


if __name__ == "__main__":
    folder_path = os.path.dirname(os.path.realpath(__file__))
    folder = Path(folder_path, "data/latency")
    subfolders = folder.glob("*")

    latency_vs_freq = dict()
    latency_vs_msg = dict()

    for subfolder in subfolders:
        device = subfolder.as_uri().split("/")[-1].capitalize()
        with open(Path(subfolder, "latency_vs_frequency.txt"), "r") as f:
            latency_vs_freq[device] = [line.split(",")[1] for line in f.readlines()]

        with open(Path(subfolder, "latency_vs_msgsize.txt"), "r") as f:
            latency_vs_msg[device] = [line.split(",")[1] for line in f.readlines()]

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

    fig_freq = go.Figure()
    fig_msg = go.Figure()

    for name, data in latency_vs_freq.items():
        fig_freq.add_trace(
            go.Scatter(
                x=x_freq[: len(data)],
                y=np.array(data, dtype=float) * 1e3,
                mode="lines+markers",
                name=name,
            )
        )

    for name, data in latency_vs_msg.items():
        fig_msg.add_trace(
            go.Scatter(
                x=x_msg[: len(data)],
                y=np.array(data, dtype=float) * 1e3,
                mode="lines+markers",
                name=name,
            )
        )

    fig_freq.update_xaxes(type="log")
    fig_msg.update_xaxes(type="log")

    fig_msg.update_layout(
        title="Latency w.r.t. Message Size @100Hz",
        xaxis_title="Bytes (#)",
        yaxis_title="Latency (ms)",
        font=dict(size=18, family="Linux Libertine O"),
        height=400,
        width=600,
    )

    fig_freq.update_layout(
        title="Latency w.r.t. Frequency @1kB",
        xaxis_title="Frequency (Hz)",
        yaxis_title="Latency (ms)",
        font=dict(size=18, family="Linux Libertine O"),
        height=400,
        width=600,
    )

    fig_freq.show()
    fig_msg.show()
