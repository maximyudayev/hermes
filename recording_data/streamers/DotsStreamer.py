from streamers import SensorStreamer
from streams import DotsStream

import numpy as np
import time
from collections import OrderedDict

from utils.msgpack_utils import serialize
from handlers import MovellaFacade

################################################
################################################
# A class for streaming Dots IMU data.
################################################
################################################
class DotsStreamer(SensorStreamer):
  # Mandatory read-only property of the abstract class.
  _log_source_tag = 'dots'

  ########################
  ###### INITIALIZE ######
  ########################
  
  # Initialize the sensor streamer.
  def __init__(self,
               port_pub: str | None = None,
               port_sync: str | None = None,
               port_killsig: str | None = None,
               sampling_rate_hz: int = 20,
               num_joints: int = 5,
               log_history_filepath: str | None = None,
               print_status: bool = True,
               print_debug: bool = False):

    # Initialize any state that your sensor needs.
    self._sampling_rate_hz = sampling_rate_hz
    self._num_joints = num_joints
    self._packet = OrderedDict()

    stream_info = {
      "num_joints": self._num_joints,
      "sampling_rate_hz": self._sampling_rate_hz
    }

    # Abstract class will call concrete implementation's creation methods
    #   to build the data structure of the sensor
    super(DotsStreamer, self).__init__(self,
                                       port_pub=port_pub,
                                       port_sync=port_sync,
                                       port_killsig=port_killsig,
                                       stream_info=stream_info,
                                       log_history_filepath=log_history_filepath,
                                       print_status=print_status, 
                                       print_debug=print_debug)


  ######################################
  ###### INTERFACE IMPLEMENTATION ######
  ######################################

  # Factory class method called inside superclass's constructor to instantiate corresponding Stream object.
  def create_stream(cls, stream_info: dict | None = None) -> DotsStream:
    return DotsStream(**stream_info)

  # Connect to the sensor.
  def connect(self):
    timeout_s = 10
    xqp_joints = [0,1,2,3,4] # remove lines with xqp_ variables 
    def map_dot_to_joint(devices, device):
      # msg = format_log_message("Which joint is this DOT attached to? (New DOT lights up green) : ", source_tag=self._log_source_tag, userAction=True, print_message=False)
      while True:
        try:
          # joint_of_device = input(msg)
          joint_of_device = str(xqp_joints.pop(0))
          if int(joint_of_device) < 0 or str(int(joint_of_device)) in devices: raise KeyError
          else: 
            devices[joint_of_device] = device
            # self._log_debug("DOT @%s associated with joint %s."% (device.bluetoothAddress(), joint_of_device))
            return devices
        except ValueError:
          # self._log_error("Joint specifier must be a unique positive integer.")
          pass
        except KeyError:
          # self._log_error("This joint specifier already used by %s" % devices[joint_of_device].bluetoothAddress())
          pass

    def set_master_joint(devices):
      # msg = format_log_message("Which joint is center of skeleton? : ", source_tag=self._log_source_tag, userAction=True, print_message=False)
      while True:
        try:
          # master_joint = int(input(msg))
          master_joint = xqp_joints[0]
          if master_joint < 0 or str(master_joint) not in devices: raise KeyError
          else: 
            # self._log_debug("Joint %s set as master. (DOT @%s)."% (master_joint, devices[str(master_joint)].bluetoothAddress()))
            self._handler.setMasterDot(str(master_joint))
            self._packet = OrderedDict([(v.bluetoothAddress(), None) for k, v in devices.items()])
        except ValueError:
          # self._log_error("Joint specifier must be a positive integer.")
          pass
        except KeyError:
          # self._log_error("This joint specifier does not exist in the device list.")
          pass
        else: break

    # Connecting to your sensor.
    #   Then return True or False to indicate whether connection was successful.
    self._handler = MovellaFacade()

    # DOTs backend is annoying and doesn't always connect/discover devices from first try, loop until success
    while True:
      if not self._handler.initialize():
        self._handler.cleanup()
        continue
      else: break

    while True:
      self._handler.scanForDots(timeout_s)
      if len(self._handler.detectedDots()) == 0:
        # self._log_error("No Movella DOT device(s) found. Aborting.")
        pass
      elif len(self._handler.detectedDots()) < self._num_joints:
        # self._log_error("Not all %s requested Movella DOT device(s) found. Aborting." % self._num_joints)
        pass
      else:
        # self._log_debug("All %s requested Movella DOT device(s) found." % self._num_joints)
        break

    while True:
      self._handler.connectDots(onDotConnected=map_dot_to_joint, onConnected=set_master_joint, connectAttempts=10)
      if len(self._handler.connectedDots()) == 0:
        # self._log_error("Could not connect to any Movella DOT device(s). Aborting.")
        pass
      elif len(self._handler.connectedDots()) < self._num_joints:
        # self._log_error("Not all requested Movella DOT devices connected %s/%s. Aborting." % (len(self._handler.connectedDots()), self._num_joints))
        pass
      else:
        # self._log_debug("All %s detected Movella DOT device(s) connected." % self._num_joints)
        break

    for joint, device in self._handler.connectedDots().items():
      # Make sure all connected devices have the same filter profile and output rate
      if device.setOnboardFilterProfile("General"):
        # self._log_debug("Successfully set profile to General for joint %s." % joint)
        pass
      else:
        # self._log_error("Setting filter profile for joint %s failed!" % joint)
        return False

      if device.setOutputRate(self._sampling_rate_hz):
        # self._log_debug(f"Successfully set output rate for joint {joint} to {self._sampling_rate_hz} Hz.")
        pass
      else:
        # self._log_error("Setting output rate for joint %s failed!" % joint)
        return False

    self._manager = self._handler.manager()
    self._devices = self._handler.connectedDots()

    # Call facade sync function, not directly the backend manager proxy
    while not self._handler.sync():
      # self._log_error("Synchronization of dots failed! Retrying.")
      pass
    
    # self._log_debug(f"Successfully synchronized {len(self._devices)} dots.")
    # self._log_status('Successfully connected to the dots streamer.')

    # Set dots to streaming mode
    return self._handler.stream()

  # Loop until self._running is False.
  # Acquire data from your sensor as desired, and for each timestep.
  def run(self):
    while self._running:
      if self._handler.packetsAvailable():
        time_s: float = time.time()
        for joint, device in self._handler.connectedDots().items():
          # Retrieve a packet
          packet = self._handler.getNextPacket(device.portInfo().bluetoothAddress())
          euler = packet.orientationEuler()
          acc = packet.freeAcceleration()
          self._packet[device.bluetoothAddress()] = {
            'timestamp': packet.sampleTimeFine(),
            'acceleration': (acc[0], acc[1], acc[2]),
            'gyroscope': (euler.x(), euler.y(), euler.z()),
          }
        
        acceleration = np.array([v['acceleration'] for (_,v) in self._packet.items()])
        gyroscope = np.array([v['gyroscope'] for (_,v) in self._packet.items()])
        timestamp = np.array([v['timestamp'] for (_,v) in self._packet.items()])

        # Store the captured data into the data structure.
        self._stream.append_data(time_s=time_s, acceleration=acceleration, gyroscope=gyroscope, timestamp=timestamp)

        # Get serialized object to send over ZeroMQ.
        msg = serialize(time_s=time_s, acceleration=acceleration, gyroscope=gyroscope, timestamp=timestamp)

        # Send the data packet on the PUB socket.
        self._pub.send_multipart([b"%s.data"%self._log_source_tag, msg])

  # Clean up and quit
  def quit(self):
    for device in self._handler.connectedDots(): device.stopMeasurement()
    self._manager.stopSync()
    self._manager.close()
