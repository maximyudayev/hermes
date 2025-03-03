from abc import ABC, abstractmethod
import dash_bootstrap_components as dbc
from streams import Stream


#############################################
#############################################
# Interface class to visualize Producer data.
#############################################
#############################################
class Visualizer(ABC):
  def __init__(self,
               stream: Stream,
               col_width: int):
    self._stream = stream
    self._col_width = col_width
    self._layout = None


  @property
  def layout(self) -> dbc.Col:
    return self._layout


  @abstractmethod
  def _activate_callbacks(self) -> None:
    pass
