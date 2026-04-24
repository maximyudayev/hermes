import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import lognorm


def plot_latency_distribution(log_folder_path: str):
    def to_seconds_float(value_str):
        if isinstance(value_str, str):
            try:
                return float(value_str.strip().rstrip('s'))
            except ValueError:
                return np.nan
        return value_str

    folder_path = Path(log_folder_path)
    files = folder_path.glob("*.log")

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
    bin_width = 0.050  # 50 us in ms
    marks = ['o', 'X', 'd', '*']  # Different markers for each statistic
    max_lim = 0
    legend_handles = []

    for i, file in enumerate(files):
        data = pd.read_csv(
            file,
            skiprows=3,
            delimiter=',',
            header=None,
            usecols=[1],
            converters={1: to_seconds_float},
            engine='python'
        )
        latencies = data[1].dropna().abs() * 1e3
        latencies = latencies[latencies > 0]  # Filter out zeros values

        # Ensure we have positive values for log-normal distribution fitting
        if latencies.empty:
            print("No positive latency data found to plot.")
            continue

        device_name = file.name.split('.')[0]
        legend_handles.append(plt.Line2D([0], [0], color=colors[i], lw=4, label=device_name))

        # Calculate statistics
        mean_val = latencies.mean()
        p50_val = latencies.median()
        p90_val = latencies.quantile(0.90)
        p95_val = latencies.quantile(0.95)
        max_lim = max(max_lim, p95_val)

        print(f"Latency Statistics of {file.name.split('.')[0]}:")
        print(f"  Mean: {mean_val:.6f} ms")
        print(f"  Median: {p50_val:.6f} ms")
        print(f"  90th Percentile (P90): {p90_val:.6f} ms")
        print(f"  95th Percentile (P95): {p95_val:.6f} ms")

        # Plot histogram of the latencies
        # `density=True` normalizes the histogram so its area sums to 1,
        # which is necessary for overlaying a probability density function (PDF).
        bins = np.arange(0, latencies.max() + bin_width, bin_width)
        plt.hist(latencies, bins=bins, density=True, alpha=0.2, color=colors[i])

        # Fit a log-normal distribution to the data.
        # `floc=0` forces the location parameter to 0. Latency is a duration, so it can't be negative.
        shape, loc, scale = lognorm.fit(latencies, floc=0)

        # Generate a range of x-values for plotting the fitted PDF
        x = np.linspace(latencies.min(), latencies.max(), 1000)

        # Calculate the PDF for the x-values
        pdf = lognorm.pdf(x, shape, loc, scale)

        # Plot the PDF line
        plt.plot(x, pdf, lw=1, color=colors[i])
        print(f"Fitted Log-Normal Parameters: shape={shape:.4f}, loc={loc:.4f}, scale={scale:.4f}")

        # Annotate the plot with vertical lines for the calculated statistics
        stats_to_plot = {
            'Mean time offset': mean_val,
            '50th percentile': p50_val,
            '90th percentile': p90_val,
            '95th percentile': p95_val,
        }

        for k, (name, val) in enumerate(stats_to_plot.items()):
            # Find the corresponding y-value on the fitted PDF curve
            y_val_on_pdf = lognorm.pdf(val, shape, loc, scale)
            # Plot the point as a dot on the line curve, without a label
            plt.plot(val, y_val_on_pdf, marks[k], color=colors[i], markersize=6)

    # Create proxy artists for the legend
    legend_handles.append(plt.Rectangle((0, 0), 1, 1, color='grey', alpha=0.2, label='Time offset distribution'))
    legend_handles.append(plt.Line2D([0], [0], color='grey', lw=1, label='Log normal PDF'))

    for k, name in enumerate(stats_to_plot.keys()):
        legend_handles.append(
            plt.Line2D([0], [0], marker=marks[k], color='grey', label=name, linestyle='None', markersize=6)
        )

    # Finalize the plot with titles, labels, and a legend
    plt.title(f'Synchronization Tail Analysis')
    plt.xlabel('| Offset (ms) |')
    plt.ylabel('Probability')
    plt.xlim(0, max_lim * 1.1)
    plt.ylim(0, 2.5)
    plt.legend(handles=legend_handles)
    plt.grid(True, which="both", axis="both", linestyle="--", linewidth=0.5)

    plt.show()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "log_folder",
        type=str,
        help="Path to the log folder containing files to be parsed."
    )
    args = parser.parse_args()

    plot_latency_distribution(args.log_folder)
