from nodes.Node import Node

from nodes.consumers.DataLogger import DataLogger
from nodes.consumers.DataVisualizer import DataVisualizer
from nodes.consumers.DummyConsumer import DummyConsumer

CONSUMERS: dict[str, Node] = {
  "DataLogger": DataLogger,
  "DataVisualizer": DataVisualizer,
  "DummyConsumer": DummyConsumer,
}
