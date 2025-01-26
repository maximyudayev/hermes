from nodes.Node import Node
from producers.AwindaStreamer import AwindaStreamer
from producers.DotsStreamer import DotsStreamer
from producers.CameraStreamer import CameraStreamer
from producers.EyeStreamer import EyeStreamer
from producers.InsoleStreamer import InsoleStreamer
from producers.ExperimentControlStreamer import ExperimentControlStreamer

PRODUCERS: dict[str, Node] = {
  "AwindaStreamer": AwindaStreamer,
  "DotsStreamer": DotsStreamer,
  "CameraStreamer": CameraStreamer,
  "EyeStreamer": EyeStreamer,
  "InsoleStreamer": InsoleStreamer,
  "ExperimentControlStreamer": ExperimentControlStreamer
}
