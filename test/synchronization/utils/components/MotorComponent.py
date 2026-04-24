import numpy as np
import h5py

from . import DataComponent

class MotorComponent(DataComponent):
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
        self._data: np.ndarray
        
        super().__init__(unique_id=unique_id)

    def read_data(self):
        self._read_timestamps()
        self._read_data()

    def _read_timestamps(self):
        with h5py.File(self._hdf5_path, 'r') as hdf5:
            self._toa_s = hdf5[f'{self._data_path}/timestamp'][:, 0] - self._offset
            if self._toa_s.ndim > 1:
                self._toa_s = self._toa_s.flatten()
            self._first_timestamp = float(self._toa_s[0])
            self._last_timestamp = float(self._toa_s[-1])

    def _read_data(self):
        with h5py.File(self._hdf5_path, 'r') as hdf5:
            self._data = hdf5[f'{self._data_path}/position'][:, 0]

    def get_sync_info(self):
        return {
            'first_timestamp': self._first_timestamp,
            'last_timestamp': self._last_timestamp,
            'timestamps': self._toa_s,
            'data': self._data,
        }
