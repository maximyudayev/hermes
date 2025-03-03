from utils.time_utils import *
from nodes.Broker import Broker
from utils.zmq_utils import *
from sensor_configs.AidWear import *


# Note that multiprocessing requires the __main__ check.
if __name__ == '__main__':
  # Define locally connected streamers.
  producers = dict([
    # Use one of the following to control the experiment (enter notes, quit, etc)
    ('ExperimentControlStreamer', False),  # A GUI to label activities/calibrations and enter notes
    # Sensors!
    ('AwindaStreamer',     False),  # The Awinda body tracking system (includes the Manus finger-tracking gloves if connected to Xsens)
    ('DotsStreamer',       True),  # The Dots lower limb tracking system
    ('EyeStreamer',        True),  # The Pupil Labs eye-tracking headset
    ('MicrophoneStreamer', False),  # One or more microphones
    ('CameraStreamer',     False),  # One or more cameras
    ('InsoleStreamer',     True),  # The Moticon pressure insoles
    ('TmsiStreamer',       False),
  ])
  # Remove disabled streamers.
  local_producer_specs = [spec for spec in producer_specs 
                          if spec['class'] in producers
                          and producers[spec['class']]]

  # TODO:
  local_pipeline_specs = []

  ############################
  ###### PROCESS LAUNCH ######
  ############################
  # Create the broker and manage all the components of the experiment.
  stream_broker: Broker = Broker(ip=IP_BACKPACK,
                                 node_specs=local_producer_specs+local_pipeline_specs,
                                 print_status=print_status, 
                                 print_debug=print_debug)
  # Expose local wearable data to remote subscribers (e.g. lab PC in AidFOG project).
  stream_broker.expose_to_remote_sub()
  # Subscribe to the KILL signal of a remote machine.
  stream_broker.subscribe_to_killsig(addr=IP_STATION)
  # Run proxy/server's main.
  stream_broker(duration_s=None)
