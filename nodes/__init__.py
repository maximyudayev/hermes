from nodes.producers import PRODUCERS
from nodes.consumers import CONSUMERS
from nodes.pipelines import PIPELINES

NODES = {
  **PRODUCERS,
  **CONSUMERS,
  **PIPELINES
}
