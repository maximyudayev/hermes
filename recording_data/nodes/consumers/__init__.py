from nodes.Node import Node
from consumers.DataLogger import DataLogger
from consumers.DataVisualizer import DataVisualizer

CONSUMERS: dict[str, Node] = {
  "DataLogger": DataLogger,
  "DataVisualizer": DataVisualizer
}
