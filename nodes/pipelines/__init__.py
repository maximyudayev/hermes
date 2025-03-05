from nodes.Node import Node

from nodes.pipelines.DummyPipeline import DummyPipeline
from nodes.pipelines.PytorchWorker import PytorchWorker

PIPELINES: dict[str, Node] = {
  "PytorchWorker": PytorchWorker,
  "DummyPipeline": DummyPipeline,
}
