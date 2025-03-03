from nodes.Node import Node

from consumers.Consumer import Consumer 
from consumers.DataLogger import DataLogger
from consumers.DataVisualizer import DataVisualizer
from consumers.DummyConsumer import DummyConsumer

CONSUMERS: dict[str, Node] = {
  "DataLogger": DataLogger,
  "DataVisualizer": DataVisualizer,
  "DummyConsumer": DummyConsumer,
}
