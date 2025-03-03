from nodes.Node import Node

from pipelines.Pipeline import Pipeline
from pipelines.DummyPipeline import DummyPipeline
from pipelines.PytorchWorker import PytorchWorker

PIPELINES: dict[str, Node] = {
  "PytorchWorker": PytorchWorker,
  "DummyPipeline": DummyPipeline,
}
