import numpy as np
import h5py

from . import DataComponent

class SkeletonComponent(DataComponent):
    def __init__(
        self,
        unique_id: str,
        hdf5_path: str,
        data_path: str,
        legend_name: str,
        offset: int,
    ):
        self._hdf5_path = hdf5_path
        self._data_path = data_path
        self._legend_name = legend_name
        self._offset = offset

        # Segment names and indices (BASED ON THE HDF5 FILE DESCRIPTION)
        self._segment_names = [
            'Pelvis',
            'L5',
            'L3',
            'T12',
            'T8',
            'Neck',
            'Head',
            'Right Shoulder',
            'Right Upper Arm',
            'Right Forearm',
            'Right Hand',
            'Left Shoulder',
            'Left Upper Arm',
            'Left Forearm',
            'Left Hand',
            'Right Upper Leg',
            'Right Lower Leg',
            'Right Foot',
            'Right Toe',
            'Left Upper Leg',
            'Left Lower Leg',
            'Left Foot',
            'Left Toe',
        ]

        # Define skeletal connections
        self._connections = [
            # Spine
            ('Pelvis', 'L5'),
            ('L5', 'L3'),
            ('L3', 'T12'),
            ('T12', 'T8'),
            ('T8', 'Neck'),
            ('Neck', 'Head'),
            # Right arm
            ('Neck', 'Right Shoulder'),
            ('Right Shoulder', 'Right Upper Arm'),
            ('Right Upper Arm', 'Right Forearm'),
            ('Right Forearm', 'Right Hand'),
            # Left arm
            ('Neck', 'Left Shoulder'),
            ('Left Shoulder', 'Left Upper Arm'),
            ('Left Upper Arm', 'Left Forearm'),
            ('Left Forearm', 'Left Hand'),
            # Right leg
            ('Pelvis', 'Right Upper Leg'),
            ('Right Upper Leg', 'Right Lower Leg'),
            ('Right Lower Leg', 'Right Foot'),
            ('Right Foot', 'Right Toe'),
            # Left leg
            ('Pelvis', 'Left Upper Leg'),
            ('Left Upper Leg', 'Left Lower Leg'),
            ('Left Lower Leg', 'Left Foot'),
            ('Left Foot', 'Left Toe'),
        ]

        super().__init__(unique_id=unique_id)

    def read_data(self):
        self._read_timestamps()
        self._read_data()
        self._match_data_to_time()

    def _read_timestamps(self):
        with h5py.File(self._hdf5_path, 'r') as hdf5:
            self._toa_s = hdf5[f'{self._data_path}/xsens-time/timestamp_s'][:, 0] - self._offset
            self._first_timestamp = float(self._toa_s[0])
            self._last_timestamp = float(self._toa_s[-1])

    def _read_data(self):
        with h5py.File(self._hdf5_path, 'r') as hdf5:
            self._positions = hdf5[f'{self._data_path}/xsens-pose/position'][:]

    def _match_data_to_time(self):
        with h5py.File(self._hdf5_path, 'r') as hdf5:
            ref_counters = hdf5[f'{self._data_path}/xsens-time/counter'][:, 0]
            pos_counters = hdf5[f'{self._data_path}/xsens-pose/counter'][:, 0]

            # Create a mapping from values to their first occurrence index in position counters
            unique_pos_counters, first_indices = np.unique(pos_counters, return_index=True)
            value_to_first_idx = dict(zip(unique_pos_counters, first_indices))

            # Look up each element of reference counters
            matches = np.array([value_to_first_idx.get(val, -1) for val in ref_counters])
            self._toa_s = self._toa_s[matches >= 0]
            self._positions = self._positions[matches[matches >= 0]]

            self._start_idx = 0
            self._end_idx = len(self._toa_s) - 1
            print(f'Position data length ({len(self._positions)}) ?= timestamp length ({len(self._toa_s)})', flush=True)

    def get_sync_info(self):
        return {
            'type': 'skeleton',
            'unique_id': self._unique_id,
            'first_timestamp': self._first_timestamp,
            'last_timestamp': self._last_timestamp,
            'timestamps': self._toa_s,
            'data': self._positions,
        }

    def set_truncation_points(self, start_idx: int, end_idx: int):
        self._start_idx = int(max(0, start_idx))
        self._end_idx = int(min(len(self._toa_s) - 1, end_idx))
        print(f'{self._legend_name}: Start index = {self._start_idx}', flush=True)
