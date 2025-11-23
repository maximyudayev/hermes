from nodes.pipelines.Pipeline import Pipeline

PIPELINES: dict[str, type[Pipeline]] = {}
try:
  from nodes.pipelines.PytorchWorker import PytorchWorker
  PIPELINES["PytorchWorker"] = PytorchWorker
except ImportError as e:
  print(e, "\nSkipping %s"%"PytorchWorker.", flush=True)

try:
  from nodes.pipelines.DummyPipeline import DummyPipeline
  PIPELINES["DummyPipeline"] = DummyPipeline
except ImportError as e:
  print(e, "\nSkipping %s"%"DummyPipeline.", flush=True)
