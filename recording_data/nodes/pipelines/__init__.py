from nodes.Node import Node
from pipelines.DummyPipeline import DummyPipeline
from pipelines.PytorchWorker import PytorchWorker

PIPELINES: dict[str, Node] = {
  "PytorchWorker": PytorchWorker,
  "DummyPipeline": DummyPipeline,
}
