from streamers.AwindaStreamer import AwindaStreamer
from streamers.DotsStreamer import DotsStreamer
from streamers.CameraStreamer import CameraStreamer
from streamers.EyeStreamer import EyeStreamer
from streamers.InsoleStreamer import InsoleStreamer
from streamers.ExperimentControlStreamer import ExperimentControlStreamer
from streamers.MoxyStreamer import MoxyStreamer
from streamers.TmsiStreamer import TmsiStreamer 
STREAMERS = {
  "AwindaStreamer": AwindaStreamer,
  "DotsStreamer": DotsStreamer,
  "CameraStreamer": CameraStreamer,
  "EyeStreamer": EyeStreamer,
  "InsoleStreamer": InsoleStreamer,
  "ExperimentControlStreamer": ExperimentControlStreamer,
  "MoxyStreamer": MoxyStreamer,
  "TmsiStreamer": TmsiStreamer
}
