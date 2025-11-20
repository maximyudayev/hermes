from nodes.consumers.Consumer import Consumer

CONSUMERS: dict[str, type[Consumer]] = {}
try:
  from nodes.consumers.DataLogger import DataLogger
  CONSUMERS["DataLogger"] = DataLogger
except ImportError as e:
  print(e, "\nSkipping %s"%"DummyPipeline.", flush=True)

try:
  from nodes.consumers.DataVisualizer import DataVisualizer
  CONSUMERS["DataVisualizer"] = DataVisualizer
except ImportError as e:
  print(e, "\nSkipping %s"%"DataVisualizer.", flush=True)

try:
  from nodes.consumers.DummyConsumer import DummyConsumer
  CONSUMERS["DummyConsumer"] = DummyConsumer
except ImportError as e:
  print(e, "\nSkipping %s"%"DummyConsumer.", flush=True)
