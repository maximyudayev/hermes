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

import numpy as np
import h5py
from pathlib import Path
import plotly.figure_factory as ff


def read_hdf5_dataset_telemetry(
    folder_path=".", filename="", dataset_name=None
) -> np.ndarray:
    folder = Path(folder_path)

    # Create pattern for current index
    file = list(folder.glob(filename))

    with h5py.File(file[0], "r") as f:
        modality = np.array(f[dataset_name])
        return modality


def read_hdf5_dataset(folder_path=".", filename="", dataset_name=None) -> np.ndarray:
    folder = Path(folder_path)

    # Create pattern for current index
    file = list(folder.glob(filename))

    with h5py.File(file[0], "r") as f:
        modality = np.array(f[dataset_name])
        return modality[(modality > 1759406585) & (modality < 1759406595)]


if __name__ == "__main__":
    coh1 = [0, 1, 2, 3, 4, 5, 6, 7]
    coh2 = [12, 13, 14, 15, 16, 17]

    cam1_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/cameras",
        filename="cameras_2_0.hdf5",
        dataset_name="cameras/40644951/toa_s",
    )
    cam2_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/cameras",
        filename="cameras_2_0.hdf5",
        dataset_name="cameras/40644952/toa_s",
    )
    cam3_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/cameras",
        filename="cameras_2_0.hdf5",
        dataset_name="cameras/40644953/toa_s",
    )
    cam4_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/cameras",
        filename="cameras_2_0.hdf5",
        dataset_name="cameras/40644954/toa_s",
    )

    ego_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/smartglasses",
        filename="eye_2_0.hdf5",
        dataset_name="eye/eye-video-world/process_time_s",
    )
    gaze_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/smartglasses",
        filename="eye_2_0.hdf5",
        dataset_name="eye/eye-gaze/process_time_s",
    )
    pupil_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/smartglasses",
        filename="eye_2_0.hdf5",
        dataset_name="eye/eye-pupil/process_time_s",
    )
    blinks_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/smartglasses",
        filename="eye_2_0.hdf5",
        dataset_name="eye/eye-blinks/process_time_s",
    )
    fixations_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/smartglasses",
        filename="eye_2_0.hdf5",
        dataset_name="eye/eye-fixations/process_time_s",
    )

    insole_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/insoles",
        filename="insoles_2_0.hdf5",
        dataset_name="insoles/insoles-data/timestamp",
    )

    imu_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/imu",
        filename="imu_2_0.hdf5",
        dataset_name="mvn-analyze/xsens-motion-trackers/process_time_s",
    )
    pose_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/imu",
        filename="imu_2_0.hdf5",
        dataset_name="mvn-analyze/xsens-pose/process_time_s",
    )
    joints_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/imu",
        filename="imu_2_0.hdf5",
        dataset_name="mvn-analyze/xsens-joints/process_time_s",
    )
    linear_segments_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/imu",
        filename="imu_2_0.hdf5",
        dataset_name="mvn-analyze/xsens-linear-segments/process_time_s",
    )
    angular_segments_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/imu",
        filename="imu_2_0.hdf5",
        dataset_name="mvn-analyze/xsens-angular-segments/process_time_s",
    )
    com_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/imu",
        filename="imu_2_0.hdf5",
        dataset_name="mvn-analyze/xsens-com/process_time_s",
    )

    emg_coh = read_hdf5_dataset(
        folder_path="./visualizations/data/emg",
        filename="emg_2_0.hdf5",
        dataset_name="emgs/cometa-emg/toa_s",
    )

    telemetry_coh = read_hdf5_dataset_telemetry(
        folder_path="./visualizations/data/telemetry",
        filename="telemetry_2_0.hdf5",
        dataset_name="dummy-producer/sensor-emulator/process_time_s",
    )
    telemetry_coh = telemetry_coh[:, 0] - telemetry_coh[0, 0] + 1759406585

    data = [
        cam1_coh,
        cam2_coh,
        cam3_coh,
        cam4_coh,
        ego_coh,
        gaze_coh,
        pupil_coh,
        blinks_coh,
        fixations_coh,
        insole_coh,
        imu_coh,
        pose_coh,
        joints_coh,
        linear_segments_coh,
        angular_segments_coh,
        com_coh,
        emg_coh,
        telemetry_coh[telemetry_coh < 1759406595],
    ]

    names = [
        "Camera 1",
        "Camera 2",
        "Camera 3",
        "Camera 4",
        "Ego vision",
        "Gaze",
        "Pupils",
        "Blinks",
        "Fixations",
        "Insole pressure",
        "9-DOF IMU",
        "3D pose",
        "Joint angles",
        "Linear segments",
        "Angular segments",
        "Center of mass",
        "sEMG",
        "Telemetry",
    ]

    colors = {
        "Camera 1": "rgb(127, 127, 127)",
        "Camera 2": "rgb(227, 119, 194)",
        "Camera 3": "rgb(140, 86, 75)",
        "Camera 4": "rgb(148, 103, 189)",
        "Ego vision": "rgb(214, 39, 40)",
        "Gaze": "rgb(44, 160, 44)",
        "Pupils": "rgb(255, 127, 14)",
        "Blinks": "rgb(31, 119, 180)",
        "Fixations": "rgb(23, 190, 207)",
        "Insole pressure": "rgb(188, 189, 34)",
        "9-DOF IMU": "rgb(127, 127, 127)",
        "3D pose": "rgb(227, 119, 194)",
        "Joint angles": "rgb(140, 86, 75)",
        "Linear segments": "rgb(148, 103, 189)",
        "Angular segments": "rgb(214, 39, 40)",
        "Center of mass": "rgb(44, 160, 44)",
        "sEMG": "rgb(255, 127, 14)",
        "Telemetry": "rgb(31, 119, 180)",
    }

    fig = ff.create_distplot(
        list(reversed(data)),
        list(reversed(names)),
        colors=list(reversed(list(colors.values()))),
        show_curve=False,
        bin_size=0.01,
    )

    fig.update_layout(
        legend_traceorder="reversed",
        font=dict(family="Linux Libertine O"),
        height=1200,
        width=1200,
    )
    fig.show()
