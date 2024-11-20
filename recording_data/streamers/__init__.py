from streamers.AwindaStreamer import AwindaStreamer
from streamers.DotsStreamer import DotsStreamer
from streamers.CameraStreamer import CameraStreamer
from streamers.EyeStreamer import EyeStreamer
from streamers.InsoleStreamer import InsoleStreamer
from streamers.ExperimentControlStreamer import ExperimentControlStreamer

STREAMERS = {
  "AwindaStreamer": AwindaStreamer,
  "DotsStreamer": DotsStreamer,
  "CameraStreamer": CameraStreamer,
  "EyeStreamer": EyeStreamer,
  "InsoleStreamer": InsoleStreamer,
  "ExperimentControlStreamer": ExperimentControlStreamer
}
