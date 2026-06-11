import argparse
from pathlib import Path
import pandas as pd
from scipy import stats
import sys


def analyze_jitter_trends(stats_file: Path):
    """
    Reads the aggregated jitter statistics and performs a one-sample t-test
    on the jitter slope to check for temporal trends.

    Args:
        stats_file (Path): Path to the 'stats.csv' file containing jitter data from multiple trials.
    """
    if not stats_file.exists():
        print(f"Error: Statistics file not found at '{stats_file}'")
        sys.exit(1)

    try:
        df = pd.read_csv(stats_file)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)

    if "jitter_slope" not in df.columns:
        print("Error: 'jitter_slope' column not found in the stats file.")
        print(
            "Please re-run 'gen_plot_jitter.py' from the updated script to generate this column."
        )
        sys.exit(1)

    # Group by modality, which is a combination of the device group and the series name
    grouped = df.groupby(["group", "name"])

    results = []
    for (group, name), data in grouped:
        modality_name = f"{group}/{name}"
        slopes = data["jitter_slope"].dropna()
        num_trials = len(slopes)

        if num_trials < 2:
            print(
                f"Skipping '{modality_name}': needs at least 2 trials for analysis, found {num_trials}."
            )
            continue

        # H₀: The true mean slope is >= 0 (jitter compounds or is constant)
        # H₁: The true mean slope is < 0 (jitter decreases over time)
        # We want to reject H₀ to support the claim of no compounding.
        t_stat, p_value = stats.ttest_1samp(slopes, 0, alternative="less")

        results.append(
            {
                "Modality": modality_name,
                "Trials": num_trials,
                "Mean Slope (ms/sample)": slopes.mean(),
                "t-statistic": t_stat,
                "p-value": p_value,
            }
        )

    if not results:
        print("No data available for analysis.")
        return

    # Print results in a formatted table
    results_df = pd.DataFrame(results)
    print("\n--- Jitter Trend Analysis ---")
    print("Hypothesis Test: Testing if jitter slope is significantly less than zero.")
    print(
        "A small p-value (< 0.05) suggests that jitter does not compound over time.\n"
    )
    print(results_df.to_string(index=False))
    print("\n" + "=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Perform statistical analysis on jitter trends from multiple trials.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--dir",
        "-d",
        type=str,
        required=True,
        help="Path to the output directory containing the 'stats.csv' file.",
    )

    args = parser.parse_args()
    stats_file_path = Path(args.dir) / "stats.csv"

    analyze_jitter_trends(stats_file_path)
