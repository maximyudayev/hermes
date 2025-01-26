from producers import PRODUCERS
from consumers import CONSUMERS
from pipelines import PIPELINES

NODES = {
  **PRODUCERS,
  **CONSUMERS,
  **PIPELINES
}
