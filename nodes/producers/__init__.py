from nodes.Node import Node

from nodes.producers.ViconStreamer import ViconStreamer
from nodes.producers.DummyProducer import DummyProducer
from nodes.producers.CyberlegStreamer import CyberlegStreamer
from nodes.producers.AwindaStreamer import AwindaStreamer
from nodes.producers.DotsStreamer import DotsStreamer
from nodes.producers.CameraStreamer import CameraStreamer
from nodes.producers.EyeStreamer import EyeStreamer
from nodes.producers.InsoleStreamer import InsoleStreamer
from nodes.producers.ExperimentControlStreamer import ExperimentControlStreamer
from nodes.producers.MoxyStreamer import MoxyStreamer
from nodes.producers.TmsiStreamer import TmsiStreamer

PRODUCERS: dict[str, Node] = {
  "AwindaStreamer": AwindaStreamer,
  "DotsStreamer": DotsStreamer,
  "CameraStreamer": CameraStreamer,
  "EyeStreamer": EyeStreamer,
  "InsoleStreamer": InsoleStreamer,
  "CyberlegStreamer": CyberlegStreamer,
  "ExperimentControlStreamer": ExperimentControlStreamer,
  "DummyStreamer": DummyProducer,
  "MoxyStreamer": MoxyStreamer,
  "TmsiStreamer": TmsiStreamer,
  "ViconStreamer": ViconStreamer
}
