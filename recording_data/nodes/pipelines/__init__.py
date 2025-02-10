from nodes.Node import Node
from pipelines.PytorchWorker import PytorchWorker

PIPELINES: dict[str, Node] = {
  "PytorchWorker": PytorchWorker,
}
