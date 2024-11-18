from collections import OrderedDict
import numpy as np
from streams.Stream import Stream
from visualizers import LinePlotVisualizer

################################################
################################################
# A structure to store Awinda MTws' stream's data.
################################################
################################################
class MoxyStream(Stream):
  def __init__(self, devices, **kwargs) -> None:
    super().__init__()
    
    self._device_name = 'MoxyStream'
    
    # Invert device mapping to map device_id -> joint_name

    self._define_data_notes()

    # When using onLiveDataAvailable, every immediately available packet from each MTw is pushed in its own corresponding Stream.
    # When using onAllLiveDataAvailable, packets are packaged all at once (potentially for multiple timesteps)
    #   with interpolation of data for steps where some of sensors missed a measurement.
    # Choose the desired behavior for the system later. (currently onAllLiveDataAvailable).
    for dev in devices:
        self.add_stream(device_name=dev,
                            stream_name='THb',
                            data_type='float32',
                            sample_size=[1],
                            sampling_rate_hz=0.5,
                            extra_data_info={},
                            data_notes="")
            
        self.add_stream(device_name=dev,
                            stream_name='SmO2',
                            data_type='float32',
                            sample_size=[1],
                            sampling_rate_hz=0.5,
                            extra_data_info={},
                            data_notes="")
            
        self.add_stream(device_name=dev,
                            stream_name='counter',
                            data_type='uint8',
                            sample_size=[1],
                            sampling_rate_hz=0.5,
                            extra_data_info={},
                            data_notes="")

  def append_data(self,
                  device_id: int,
                  time_s: float,
                  THb: np.ndarray,
                  SmO2: np.ndarray,
                  counter: np.ndarray):
    self._append_data(device_id, 'THb', time_s, THb)
    self._append_data(device_id, 'SmO2', time_s, SmO2)
    self._append_data(device_id, 'counter', time_s, counter)



  ###########################
  ###### VISUALIZATION ######
  ###########################

  # Specify how the streams should be visualized.
  # Return a dict of the form options[device_name][stream_name] = stream_options
  #  Where stream_options is a dict with the following keys:
  #   'class': A subclass of Visualizer that should be used for the specified stream.
  #   Any other options that can be passed to the chosen class.
  def get_default_visualization_options(self):
    visualization_options = {}

    visualization_options[self._device_name] = {}

    return visualization_options
  
  def _define_data_notes(self):
    self._data_notes = {}
