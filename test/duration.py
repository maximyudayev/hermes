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

import h5py
from pathlib import Path
import os
import numpy as np


def read_hdf5_dataset_lengths(
    folder_path=".", pattern_template="*_{}.hdf5", dataset_name=None, subjects=[]
) -> list:
    folder = Path(folder_path)

    lengths = [0] * len(subjects)

    for i, idx in enumerate(subjects):
        # Create pattern for current index
        pattern = pattern_template.format(idx)
        matched_files = list(folder.glob(pattern))

        if not matched_files:
            print(f"Index {idx}: No files found matching pattern '{pattern}'")
            continue

        print(f"\nIndex {idx}: Found {len(matched_files)} file(s)")

        # Loop over each matched file
        for filepath in matched_files:
            try:
                with h5py.File(filepath, "r") as f:
                    # If dataset_name is specified, use it
                    lengths[i] += len(f[dataset_name])
            except Exception as e:
                print(f"  {os.path.basename(filepath)}: Error reading file - {e}")

        print(f"Dataset '{idx}' length = {lengths}")

    return lengths


if __name__ == "__main__":
    subjects = [0, 1, 2, 3, 4, 5, 6, 7]
    d1 = read_hdf5_dataset_lengths(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40478064/toa_s",
        subjects=subjects,
    )
    subjects = [12, 13, 14, 15, 16, 17]
    d2 = read_hdf5_dataset_lengths(
        folder_path="./visualizations/data/cameras",
        pattern_template="cameras_{}_*.hdf5",
        dataset_name="cameras/40644951/toa_s",
        subjects=subjects,
    )
    d_tot = d1 + d2
    print(f"Mean: {np.mean(d_tot)/30/60/60} | {np.std(d_tot)/30/60/60}")
    print(f"Total: {np.array(d_tot).sum() /30/60/60}")
