from nodes.Node import Node


PRODUCERS: dict[str, Node] = {}
try:
  from nodes.producers.DotsStreamer import DotsStreamer
  PRODUCERS["DotsStreamer"] = DotsStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"DotsStreamer.")

try:
  from nodes.producers.CameraStreamer import CameraStreamer
  PRODUCERS["CameraStreamer"] = CameraStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"CameraStreamer.")

try:
  from nodes.producers.EyeStreamer import EyeStreamer
  PRODUCERS["EyeStreamer"] = EyeStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"EyeStreamer.")

try:
  from nodes.producers.CyberlegStreamer import CyberlegStreamer
  PRODUCERS["CyberlegStreamer"] = CyberlegStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"CyberlegStreamer.")

try:
  from nodes.producers.InsoleStreamer import InsoleStreamer
  PRODUCERS["InsoleStreamer"] = InsoleStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"InsoleStreamer.")

try:
  from nodes.producers.ExperimentControlStreamer import ExperimentControlStreamer
  PRODUCERS["ExperimentControlStreamer"] = ExperimentControlStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"ExperimentControlStreamer.")

try:
  from nodes.producers.AwindaStreamer import AwindaStreamer
  PRODUCERS["AwindaStreamer"] = AwindaStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"AwindaStreamer.")

try:
  from nodes.producers.MoxyStreamer import MoxyStreamer
  PRODUCERS["MoxyStreamer"] = MoxyStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"MoxyStreamer.")

try:
  from nodes.producers.TmsiStreamer import TmsiStreamer
  PRODUCERS["TmsiStreamer"] = TmsiStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"TmsiStreamer.")

try:
  from nodes.producers.ViconStreamer import ViconStreamer
  PRODUCERS["ViconStreamer"] = ViconStreamer
except ImportError as e:
  print(e, "\nSkipping %s"%"ViconStreamer.")

try:
  from nodes.producers.DummyProducer import DummyProducer
  PRODUCERS["DummyProducer"] = DummyProducer
except ImportError as e:
  print(e, "\nSkipping %s"%"DummyProducer.")
