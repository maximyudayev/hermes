from collections import OrderedDict
from streams import Stream
import dash_bootstrap_components as dbc

from visualizers import ExperimentControlVisualizer


################################################
################################################
# A structure to store Experiment stream's data.
################################################
################################################
class ExperimentControlStream(Stream):
  def __init__(self, 
               activities: list[str],
               sampling_rate_hz: int = 0,
               **_) -> None:
    super().__init__()
    self._activities = activities
    self._define_data_notes()

    self.add_stream(device_name='experiment',
                    stream_name='activity',
                    data_type='str',
                    sample_size=[1],
                    sampling_rate_hz=sampling_rate_hz)


  def build_visulizer(self) -> dbc.Row:
    acceleration_plot = ExperimentControlVisualizer(stream=self,
                                                    activities=self._activities,
                                                    col_width=6)
    return dbc.Row([acceleration_plot.layout])


  def get_fps(self) -> dict[str, float]:
    return {'experiment': None}


  def _define_data_notes(self) -> None:
    self._data_notes = {}
    self._data_notes.setdefault('experiment', {})

    self._data_notes['experiment']['activity'] = OrderedDict([
      ('Description', 'Label of the performed activity, marked during the trial by the researcher. '
                      '[0,%d], corresponding to %s'.format(len(self._activities)-1, self._activities))
    ])
