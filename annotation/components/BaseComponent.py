############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
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

from abc import ABC, abstractmethod
import dash_bootstrap_components as dbc


#############################################
#############################################
# Interface class to visualize Producer data.
#############################################
#############################################
class BaseComponent(ABC):
  def __init__(self,
               unique_id: str,
               col_width: int):
    self._col_width = col_width
    self._unique_id = unique_id
    self._sync_offset = 0  # Initialize sync offset, only relevant for data components, not the control components


  @property
  def layout(self) -> dbc.Col:
    return self._layout


  @abstractmethod
  def _activate_callbacks(self) -> None:
    pass


  def set_sync_offset(self, offset: int):
    """Set synchronization offset for this component"""
    self._sync_offset = int(offset)
    
  
  def get_sync_offset(self):
    """Get current synchronization offset"""
    return self._sync_offset
