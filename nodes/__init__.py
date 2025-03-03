from producers import PRODUCERS
from consumers import CONSUMERS
from pipelines import PIPELINES
from nodes.Node import Node
from nodes.Broker import Broker

NODES = {
  **PRODUCERS,
  **CONSUMERS,
  **PIPELINES
}
