############
#
# Copyright (c) 2022 MIT CSAIL and Joseph DelPreto
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# See https://action-net.csail.mit.edu for more usage information.
# Created 2021-2022 for the MIT ActionNet project by Joseph DelPreto [https://josephdelpreto.com].
#
############


import socket
import struct
import time
import numpy as np
import traceback
import os

import pandas
from bs4 import BeautifulSoup
import glob

from nodes.producers.Producer import Producer
from streams import MvnAnalyzeStream
from utils.dict_utils import *
from utils.print_utils import *
from utils.time_utils import *
from utils.angle_utils import *
from utils.zmq_utils import *


###########################################################################
###########################################################################
# A class for streaming medically certified data from MVN Analyze software.
#
# A class to interface with the Xsens motion trackers.
# A full body suit and two optional gloves are supported.
# The following data will be streamed:
#   Euler pose and orientation data
#   Quaternion orientation data
#   Joint angles
#   Center of mass dynamics
#   Device timestamps for each timestep
# For the gloves, no joint angles are currently sent from the Xsens software.
# Note that device timestamps and frame counts will be treated as any other data stream,
#  so they will be timestamped with the Python system time.
#  This should facilitate alignment with other sensors, as well as among Xsens streams.
# Note that Xsens will send data for a single timestep as multiple messages.
#  The system timestamp of the first one will be used for all of them.
###########################################################################
###########################################################################
class XsensStreamer(Producer):
  @classmethod
  def _log_source_tag(cls) -> str:
    return 'mvn-analyze'


  def __init__(self,
               logging_spec: dict,
               mvn_ip: str = IP_LOOPBACK,
               mvn_port: str = PORT_MVN,
               mvn_protocol: str = "udp",
               mvn_msg_startcode: str = "MXTP",
               buffer_read_size: int = 2048,
               postprocessing_time_strategy: str = "constant-rate", # ['interpolate-xsens', 'constant-rate', 'interpolate-system']
               is_pose_euler: bool = False,
               is_pose_quaternion: bool = False,
               is_joint_angles: bool = False,
               is_center_of_mass: bool = False,
               is_timestamp: bool = False,
               port_pub: str = PORT_BACKEND,
               port_sync: str = PORT_SYNC,
               port_killsig: str = PORT_KILL,
               transmit_delay_sample_period_s: float = None,
               print_status: bool = True, 
               print_debug: bool = False):

    # Initialize counts of segments/joints/fingers.
    # These will be updated automatically later based on initial streaming data.
    self._num_segments = None # will be set to 23 for the full body
    self._num_fingers = None  # will be set to 0 or 40 depending on whether fingers are enabled
    self._num_joints = None # will be set to 28 = 22 regular joints + 6 ergonomic joints
    
    # Specify the Xsens streaming configuration.
    self._xsens_network_protocol = mvn_protocol
    self._xsens_network_ip = mvn_ip
    self._xsens_network_port = mvn_port
    self._xsens_msg_start_code = mvn_msg_startcode.encode('utf-8')
    # Post-processing configuration for merging Xsens recordings with streamed data.
    self._postprocessing_time_strategy = postprocessing_time_strategy
    
    self._is_pose_euler = is_pose_euler
    self._is_pose_quaternion = is_pose_quaternion
    self._is_joint_angles = is_joint_angles
    self._is_center_of_mass = is_center_of_mass
    self._is_timestamp = is_timestamp


    # Specify message types that might be received.
    self._xsens_msg_types = {
      'pose_euler':      1,
      'pose_quaternion': 2,
      # 'character_scale': 13,
      'joint_angle':     20,
      'center_of_mass':  24,
      'time_code_str':   25,
    }
    
    # Initialize a record of which ones are actually active.
    # This will be automatically set later based on iniital streaming data.
    self._xsens_is_streaming = dict([(msg_type, False) for msg_type in self._xsens_msg_types.values()])


    # Note that the buffer read size must be large enough to receive a full Xsens message.
    #  The longest message is currently from the stream "Position + Orientation (Quaternion)"
    #  which has a message length of 2040 when finger data is enabled.
    self._buffer_read_size = buffer_read_size
    self._buffer_max_size = self._buffer_read_size * 16
    
    
    # Initialize state.
    self._buffer = b''
    self._socket = None
    self._xsens_sample_index = None # The current Xsens timestep being processed (each timestep will send multiple messages)
    self._xsens_message_start_time_s = None    # When an Xsens message was first received
    self._xsens_timestep_receive_time_s = None # When the first Xsens message for an Xsens timestep was received

    stream_info = {
    }

    super().__init__(self, 
                     stream_info=stream_info,
                     logging_spec=logging_spec,
                     port_pub=port_pub,
                     port_sync=port_sync,
                     port_killsig=port_killsig,
                     transmit_delay_sample_period_s=transmit_delay_sample_period_s,
                     print_status=print_status,
                     print_debug=print_debug)


  def create_stream(cls, stream_info: dict) -> MvnAnalyzeStream:
    return MvnAnalyzeStream(**stream_info)


  def _ping_device(self) -> None:
    return None


  # Connect to the Xsens network streams, and determine what streams are active.
  def _connect(self) -> bool:
    # Open a socket to the Xsens network stream
    if self._xsens_network_protocol == 'tcp':
      self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self._socket.listen(1) # number of waiting connections
      self._socket_connection, socket_address = self._socket.accept()
      self._socket_connection.setblocking(False)
    elif self._xsens_network_protocol == 'udp':
      self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      self._socket.settimeout(5) # timeout for all socket operations, such as receiving if the Xsens network stream is inactive
    self._socket.bind((self._xsens_network_ip, self._xsens_network_port))

    return True


  # Helper to read a specified number of bytes starting at a specified index
  # and to return an updated index counter.
  def _read_bytes(self, message, starting_index: int, num_bytes: int):
    if None in [message, starting_index, num_bytes]:
      res = None
      next_index = None
    elif starting_index + num_bytes <= len(message):
      res = message[starting_index : (starting_index + num_bytes)]
      next_index = starting_index + num_bytes
    else:
      res = None
      next_index = None
    return res, next_index


  # Parse an Xsens message to extract its information and data.
  def _process_xsens_message_from_buffer(self):
    # self._log_debug('\nProcessing buffer!')
    message = self._buffer

    # Use the starting code to determine the initial index
    next_index = message.find(self._xsens_msg_start_code)
    if next_index < 0:
      return None
    
    # Parse the header
    start_code,       next_index = self._read_bytes(message, next_index, len(self._xsens_msg_start_code))
    message_type,     next_index = self._read_bytes(message, next_index, 2)
    sample_counter,   next_index = self._read_bytes(message, next_index, 4)
    datagram_counter, next_index = self._read_bytes(message, next_index, 1)
    num_items,        next_index = self._read_bytes(message, next_index, 1)
    time_code,        next_index = self._read_bytes(message, next_index, 4)
    char_id,          next_index = self._read_bytes(message, next_index, 1)
    num_segments,     next_index = self._read_bytes(message, next_index, 1)
    num_props,        next_index = self._read_bytes(message, next_index, 1)
    num_fingers,      next_index = self._read_bytes(message, next_index, 1)
    reserved,         next_index = self._read_bytes(message, next_index, 2)
    payload_size,     next_index = self._read_bytes(message, next_index, 2)

    # Decode (and verify) header information
    try:
      message_type = int(message_type)
      payload_size = int.from_bytes(payload_size, byteorder='big', signed=False) # number of bytes in the actual data of the message
      sample_counter = int.from_bytes(sample_counter, byteorder='big', signed=False) # message index basically
      datagram_counter = int.from_bytes(datagram_counter, byteorder='big', signed=False) # index of datagram chunk
      time_code = int.from_bytes(time_code, byteorder='big', signed=False) # ms since the start of recording
      char_id = int.from_bytes(char_id, byteorder='big', signed=False) # id of the tracker person (if multiple)
      num_items = int.from_bytes(num_items, byteorder='big', signed=False) # number of points in this message
      num_segments = int.from_bytes(num_segments, byteorder='big', signed=False) # we always have 23 body segments
      num_fingers = int.from_bytes(num_fingers, byteorder='big', signed=False) # number of finger track segments
      num_props = int.from_bytes(num_props, byteorder='big', signed=False) # number of props (swords etc)
      reserved = int.from_bytes(reserved, byteorder='big', signed=False)
      assert datagram_counter == (1 << 7), 'Not a single last message' # We did not implement datagram splitting
      assert char_id == 0, 'We only support a single person (a single character).'
    except TypeError:
      # Not all message parts were received.
      # This will be dealt with below, after checking if some of it was at least received.
      pass

    # If the message type and sample counter are known,
    #  use this time as the best-guess timestamp for the data.
    if message_type is not None and sample_counter is not None:
      if self._xsens_sample_index != sample_counter:
        # self._log_debug('Updating timestamp receive time, and setting sample counter to %d' % sample_counter)
        self._xsens_timestep_receive_time_s = self._xsens_message_start_time_s
        self._xsens_sample_index = sample_counter

    # Check that all were present by checking the last one.
    if payload_size is None:
      print('Incomplete message')
      return None

    # Organize the metadata so far
    metadata = {
      'message_type': message_type,
      'sample_counter': sample_counter,
      'datagram_counter': datagram_counter,
      'num_items': num_items,
      'time_since_start_s': time_code/1000.0,
      'char_id': char_id,
      'num_segments': num_segments,
      'num_props': num_props,
      'num_fingers': num_fingers,
      'reserved': reserved,
      'payload_size': payload_size,
    }
    # Validate that the number of segments/joints/fingers remains the same
    if self._num_segments is not None and self._num_segments != num_segments:
      self._log_error('ERROR: The number of Xsens segments changed from %d to %d' % (self._num_segments, num_segments))
    if self._num_fingers is not None and self._num_fingers != num_fingers and message_type in [self._xsens_msg_types['pose_euler'], self._xsens_msg_types['pose_quaternion']]:
      self._log_error('ERROR: The number of Xsens fingers changed from %d to %d' % (self._num_fingers, num_fingers))
    if self._num_joints is not None and self._num_joints != num_items and message_type == self._xsens_msg_types['joint_angle']:
      self._log_error('ERROR: The number of Xsens joints changed from %d to %d' % (self._num_joints, num_items))

    # Store the number of segments/joints/fingers if needed
    self._num_segments = num_segments # note that this field is correct even if the message is not segment-based
    if message_type in [self._xsens_msg_types['pose_euler'], self._xsens_msg_types['pose_quaternion']]:
      self._num_fingers = num_fingers
    if message_type == self._xsens_msg_types['joint_angle']:
      self._num_joints = num_items

    # Read the payload, and check that it is fully present
    payload, payload_end_index = self._read_bytes(message, next_index, payload_size)
    if payload is None:
      self._log_debug('No message payload yet')
      return None

    extra_data = {
      'xsens_sample_number'     : sample_counter,
      'xsens_time_since_start_s': time_code/1000.0,
    }
    

    # Euler and Quaternion messages are very similar,
    #   so parse them with the same code.
    # Euler-focused data contains:
    #   Segment positions (x/y/z) in cm
    #   Segment rotation (x/y/z) using a Y-Up and right-handed coordinate system
    # Quaternion-focused data contains:
    #   Segment positions (x/y/z) in cm
    #   Segment rotation (re/i/j/k) using a Z-Up and right-handed coordinate system
    # Note that the position data from the Euler stream and the Quaternion
    #   streams should be redundant.
    #   So if Euler is streaming, ignore the position from the quaternion.
    is_euler = message_type == self._xsens_msg_types['pose_euler']
    is_quaternion = message_type == self._xsens_msg_types['pose_quaternion']
    if is_euler or is_quaternion:
      if is_euler:
        num_rotation_elements = 3
        rotation_stream_name = 'orientation_euler_deg'
      else:
        num_rotation_elements = 4
        rotation_stream_name = 'orientation_quaternion'
      segment_positions_cm = np.zeros((num_segments + num_fingers, 3), dtype=np.float32)
      segment_rotations = np.zeros((num_segments + num_fingers, num_rotation_elements), dtype=np.float32)
      # Read the position and rotation of each segment
      for segment_index in range(num_segments + num_fingers):
        segment_id, next_index = self._read_bytes(message, next_index, 4)
        segment_position_cm, next_index = self._read_bytes(message, next_index, 3*4) # read x/y/z at once - each is 4 bytes
        segment_rotation, next_index = self._read_bytes(message, next_index, num_rotation_elements*4) # read x/y/z at once - each is 4 bytes

        segment_id = int.from_bytes(segment_id, byteorder='big', signed=False)
        segment_position_cm = np.array(struct.unpack('!3f', segment_position_cm), np.float32)
        segment_rotation = np.array(struct.unpack('!%df' % num_rotation_elements, segment_rotation), np.float32)
        
        # If using the Euler stream, received data is YZX so swap order to get XYZ.
        #  (Note that positions from the quaternion stream are already XYZ.)
        if is_euler:
          segment_position_cm = segment_position_cm[[2,0,1]]
          segment_rotation = segment_rotation[[2,0,1]]
        # If using the Quaternion stream, received data is in m so convert to cm.
        #  (Note that positions from the Euler stream are already in cm.)
        if is_quaternion:
          segment_position_cm = 100.0*segment_position_cm
        
        # Note that segment IDs from Xsens are 1-based,
        #  but otherwise should be usable as the matrix index.
        segment_positions_cm[segment_id-1, :] = segment_position_cm
        segment_rotations[segment_id-1, :] = segment_rotation

      # Store the data
      self.append_data('xsens-segments', rotation_stream_name,
                        self._xsens_timestep_receive_time_s, segment_rotations, extra_data=extra_data)
      if is_euler or not self._xsens_is_streaming[self._xsens_msg_types['pose_euler']]:
        self.append_data('xsens-segments', 'position_cm',
                          self._xsens_timestep_receive_time_s, segment_positions_cm, extra_data=extra_data)
      if self._print_debug:
        self._log_debug(segment_positions_cm)
        self._log_debug(segment_rotations)

    # Joint angle data contains:
    #  The parent and child segments of the joint.
    #   These are represented as a single integer: 256*segment_id + point_id
    #  Rotation around the x/y/z axes in degrees
    elif message_type == self._xsens_msg_types['joint_angle']:
      joint_parents = np.zeros((num_items), dtype=np.float32)
      joint_childs = np.zeros((num_items), dtype=np.float32)
      joint_rotations_deg = np.zeros((num_items, 3), dtype=np.float32)
      # Read the ids and rotations of each joint
      for joint_index in range(num_items):
          joint_parent, next_index = self._read_bytes(message, next_index, 4)
          joint_child, next_index = self._read_bytes(message, next_index, 4)
          joint_rotation_deg, next_index = self._read_bytes(message, next_index, 3*4) # read x/y/z at once - each is 4 bytes

          joint_parent = int.from_bytes(joint_parent, byteorder='big', signed=False)
          joint_child = int.from_bytes(joint_child, byteorder='big', signed=False)
          joint_rotation_deg = np.array(struct.unpack('!3f', joint_rotation_deg), np.float32)

          # Convert IDs from segmentID*256+localPointID to segmentID.localPointID
          joint_parent_segment = int(joint_parent/256)
          joint_parent_point = joint_parent - joint_parent_segment*256
          joint_child_segment = int(joint_child/256)
          joint_child_point = joint_child - joint_child_segment*256
          joint_parent = joint_parent_segment + joint_parent_point/1000.0
          joint_child = joint_child_segment + joint_child_point/1000.0

          # Record the joint data
          joint_parents[joint_index] = joint_parent
          joint_childs[joint_index] = joint_child
          joint_rotations_deg[joint_index, :] = joint_rotation_deg

      # Store the data
      self.append_data('xsens-joints', 'rotation_deg',
                        self._xsens_timestep_receive_time_s, joint_rotations_deg, extra_data=extra_data)
      self.append_data('xsens-joints', 'parent',
                        self._xsens_timestep_receive_time_s, joint_parents, extra_data=extra_data)
      self.append_data('xsens-joints', 'child',
                        self._xsens_timestep_receive_time_s, joint_childs, extra_data=extra_data)
      if self._print_debug:
        self._log_debug(joint_rotations_deg)
        self._log_debug(joint_parents)
        self._log_debug(joint_childs)

    # Center of mass data contains:
    #  x/y/z position in cm
    #  x/y/z velocity in cm/s
    #  x/y/z acceleration in cm/s/s
    elif message_type == self._xsens_msg_types['center_of_mass']:
      com_position_m, next_index = self._read_bytes(message, next_index, 3*4) # read x/y/z at once - each is 4 bytes
      com_velocity_m_s, next_index = self._read_bytes(message, next_index, 3*4) # read x/y/z at once - each is 4 bytes
      com_acceleration_m_ss, next_index = self._read_bytes(message, next_index, 3*4) # read x/y/z at once - each is 4 bytes

      com_position_m = np.array(struct.unpack('!3f', com_position_m), np.float32)
      com_velocity_m_s = np.array(struct.unpack('!3f', com_velocity_m_s), np.float32)
      com_acceleration_m_ss = np.array(struct.unpack('!3f', com_acceleration_m_ss), np.float32)
      
      # Store the data
      self.append_data('xsens-CoM', 'position_cm',
                        self._xsens_timestep_receive_time_s, 100.0*com_position_m, extra_data=extra_data)
      self.append_data('xsens-CoM', 'velocity_cm_s',
                        self._xsens_timestep_receive_time_s, 100.0*com_velocity_m_s, extra_data=extra_data)
      self.append_data('xsens-CoM', 'acceleration_cm_ss',
                        self._xsens_timestep_receive_time_s, 100.0*com_acceleration_m_ss, extra_data=extra_data)
      if self._print_debug:
        self._log_debug(100.0*com_position_m)
        self._log_debug(100.0*com_velocity_m_s)
        self._log_debug(100.0*com_acceleration_m_ss)

    # Time data contains:
    #  A string for the sample timestamp formatted as HH:MM:SS.mmm
    elif message_type == self._xsens_msg_types['time_code_str']:

      str_length, next_index = self._read_bytes(message, next_index, 4)
      str_length = int.from_bytes(str_length, byteorder='big', signed=True)
      assert str_length == 12, 'Unexpected number of bytes in the time code string: %d instead of 12' % str_length

      time_code_str, next_index = self._read_bytes(message, next_index, str_length)
      time_code_str = time_code_str.decode('utf-8')
      
      # The received string is a time in UTC without a date.
      # Convert this to local time with the current date, then to seconds since epoch.
      time_code_s = get_time_s_from_utc_timeNoDate_str(time_code_str, input_time_format='%H:%M:%S.%f')
      
      # Store the data
      extra_data['device_time_utc_str'] = time_code_str
      extra_data['device_timestamp_str'] = get_time_str(time_code_s, '%Y-%m-%d %H:%M:%S.%f')
      self.append_data('xsens-time', 'device_timestamp_s',
                        self._xsens_timestep_receive_time_s, time_code_s, extra_data=extra_data)
      # self._log_debug(time_code_str)

    # The message had a type that is not currently being processed/recorded.
    # No processing is required, but the pointer should still be advanced to ignore the message.
    else:
      self._log_debug('Unknown message type:', message_type)
      return payload_end_index-1

    # Check that the entire message was parsed.
    assert payload_end_index == next_index, 'The Xsens payload should end at byte %d, but the last byte processed was %d' % (payload_end_index, next_index-1)

    # The message was successfully parsed.
    # Return the last index of the message that was used.
    return next_index-1


  def _run(self):
    try:
      # Run for a few seconds to clear any frames in the input buffer.
      # Often this contains a few frames before the Xsens software reset the frame index.
      run_start_time_s = time.time()
      save_data_start_time_s = run_start_time_s + 0.1
      while self._running:
        # Receive more data
        try:
          if 'tcp' == self._xsens_network_protocol.lower().strip():
            data = self._socket_connection.recv(self._buffer_read_size)
          else: #'udp' == self._xsens_network_protocol.lower().strip():
            data = self._socket.recv(self._buffer_read_size)
          if len(self._buffer)+len(data) <= self._buffer_max_size:
            self._buffer += data
          else:
            # Remove old data if the buffer is overflowing
            self._buffer = data
        except:
          # Xsens stopped running / needs recalibration?
          self._log_warn('WARNING: Did not receive data from the Xsens. Attempting to reconnect in 5 seconds.')
          time.sleep(5)
          self._buffer = b''
          continue

        # Record this as the message arrival time if it's the first time
        #  seeing this message start code in the buffer.
        message_start_index = self._buffer.find(self._xsens_msg_start_code)
        if message_start_index >= 0 and self._xsens_message_start_time_s is None:
          # self._log_debug('Recording xsens message start time')
          self._xsens_message_start_time_s = time.time()

        # Try to process the message
        message_end_index = self._process_xsens_message_from_buffer()
        # If the message was complete, remove it from the buffer
        #  and note that we're waiting for a new start code.
        if message_end_index is not None:
          # self._log_debug('Clearing xsens message start time')
          self._buffer = self._buffer[message_end_index+1:]
          self._xsens_message_start_time_s = None
        
        # Clear the data if this is during the initial flush period.
        if time.time() < save_data_start_time_s:
          self.clear_data_all()
    except KeyboardInterrupt: # The program was likely terminated
      pass
    except:
      self._log_error('\n\n***ERROR RUNNING XsensStreamer:\n%s\n' % traceback.format_exc())
    finally:
      pass


  #####################################
  ###### EXTERNAL DATA RECORDING ######
  #####################################

  # Tell the user to start recording via the Xsens software.
  def start_external_data_recording(self, recording_dir):
    recording_dir = os.path.realpath(os.path.join(recording_dir, 'xsens'))
    os.makedirs(recording_dir, exist_ok=True)
    msg = '\n\n--------------------\n'
    msg += 'Start an Xsens recording to the following directory:'
    msg += '\n%s' % recording_dir
    msg+= '\n> Waiting for a new mvn file to appear in that directory... '
    self._log_userAction(msg)
    try:
      import pyperclip
      pyperclip.copy(recording_dir)
    except ModuleNotFoundError:
      pass
    mvn_files = glob.glob(os.path.join(recording_dir, '*.mvn'))
    new_mvn_filename = None
    while new_mvn_filename is None:
      new_mvn_files = [file for file in glob.glob(os.path.join(recording_dir, '*.mvn'))
                       if file not in mvn_files]
      if len(new_mvn_files) > 0:
        new_mvn_filename = new_mvn_files[0]
      else:
        time.sleep(0.2)
    self._external_recording_mvn_filepath = os.path.join(recording_dir, new_mvn_filename)
    self._log_userAction('--------------------\n')

  # Tell the user to stop recording via the Xsens software.
  def stop_external_data_recording(self):
    self._log_userAction('\n\n--------------------')
    self._log_userAction('Stop the Xsens recording')
    time.sleep(3) # wait at least a little, since the below may do nothing if Xsens happens to flush some data to the file
    try:
      timeout_s = 10
      self._log_userAction('\n> Waiting for the mvn file to increase in size (or for %ds to elapse)... ' % timeout_s)
      start_time_s = time.time()
      mvn_size_bytes_original = os.path.getsize(self._external_recording_mvn_filepath)
      while (os.path.getsize(self._external_recording_mvn_filepath) <= mvn_size_bytes_original) \
              and (time.time() - start_time_s < timeout_s):
        time.sleep(0.2)
    except FileNotFoundError:
      pass
    self._log_userAction('')
    self._log_userAction('Note that to later merge the data with the streamed log, use')
    self._log_userAction(' the Xsens software to export an Excel file in the same folder')
    self._log_userAction(' as the recording.  HD reprocessing can be done too if desired.')
    self._log_userAction('--------------------\n')
  
  # Update a streamed data log with data recorded from the Xsens software.
  # An exported Excel or MVNX file of the recording should be in data_dir_external_original/xsens.
  # The MVNX file will be preferred if it is available, since it contains frame timestamps.
  def merge_external_data_with_streamed_data(self,
                                             # Final post-processed outputs
                                             hdf5_file_toUpdate,
                                             data_dir_toUpdate,
                                             # Original streamed and external data
                                             data_dir_streamed,
                                             data_dir_external_original,
                                             # Archives for data no longer needed
                                             data_dir_archived,
                                             hdf5_file_archived):
  
    self._log_status('XsensStreamer merging streamed data with Xsens data')
    
    # Check if a file with a desired extension has been exported in the recording directory.
    def get_filepath_forExportType(dir_to_check, extension):
      filepaths = glob.glob(os.path.join(dir_to_check, '*.%s' % extension))
      filepaths = [x for x in filepaths if '~$' not in x.lower()]
      # See if there is one labeled 'HD' and if so use it (prefer the HD-reprocessed data).
      filepaths_hd = [x for x in filepaths if '_hd.%s' % extension in x.lower()]
      if len(filepaths_hd) > 0:
        filepaths = filepaths_hd
      # Check that a single file was found.
      if len(filepaths) == 0:
        error_msg = 'No exported %s file found in %s' % (extension.upper(), dir_to_check)
        return (None, error_msg)
      if len(filepaths) > 1:
        error_msg = 'Multiple exported %s files found in %s' % (extension.upper(), dir_to_check)
        return (None, error_msg)
      return (filepaths[0], '')
    
    # Look for an MVNX and/or Excel export.
    data_dir_external_original = os.path.join(data_dir_external_original, 'xsens')
    (excel_filepath, error_msg_excel) = get_filepath_forExportType(data_dir_external_original, 'xlsx')
    (mvnx_filepath, error_msg_mvnx) = get_filepath_forExportType(data_dir_external_original, 'mvnx')
    
    # Call the appropriate merging function.
    if mvnx_filepath is not None:
      self._merge_mvnx_data_with_streamed_data(mvnx_filepath, hdf5_file_toUpdate, hdf5_file_archived)
    elif excel_filepath is not None:
      self._merge_excel_data_with_streamed_data(excel_filepath, hdf5_file_toUpdate, hdf5_file_archived)
    else:
      self._log_error('\n\nAborting data merge for Xsens!')
      self._log_error('\n  ' + error_msg_excel)
      self._log_error('\n  ' + error_msg_mvnx)

  # A merging helper function to estimate what time every Xsens frame would
  #  have been received by the system, interpolating between frames that
  #  were missed during the actual streaming.
  def _interpolate_system_time(self, hdf5_file_streamed, all_frame_numbers):
    # Get the system time that was associated with frame numbers during streaming,
    #  and the 'actual' frame time recorded by the Xsens device.
    self._log_debug('Loading and interpolating streamed timestamps')
    if 'xsens-time' in hdf5_file_streamed:
      stream_group = hdf5_file_streamed['xsens-time']['device_timestamp_s']
      streamed_xsens_time_s = np.squeeze(stream_group['data'])
    else:
      # If the Xsens time was not streamed, just get system time from the first device/stream.
      device_group = hdf5_file_streamed[list(hdf5_file_streamed.keys())[0]]
      stream_group = device_group[list(device_group.keys())[0]]
      streamed_xsens_time_s = None
    streamed_system_times_s = np.squeeze(stream_group['time_s'])
    streamed_frame_numbers = np.squeeze(stream_group['xsens_sample_number'])
    streamed_xsens_times_since_start_s = np.squeeze(stream_group['xsens_time_since_start_s'])
  
    # Trim the datasets to ignore times before Xsens started recording,
    #  at which point it resets frame numbers to 0.
    streamed_frame_numbers_diff = np.diff(streamed_frame_numbers)
    if np.any(streamed_frame_numbers_diff < 0):
      # Start after the last time the frame numbers reset.
      stream_start_index = np.where(streamed_frame_numbers_diff < 0)[0][-1]+1
    else:
      stream_start_index = 0
    # Trim the datasets to remove trailing 0s, in case the data logging ended unexpectedly
    #  and did not successfully resize the dataset to fit the data.
    if np.any(streamed_system_times_s == 0):
      stream_end_index = np.where(streamed_system_times_s == 0)[0][0]-1
    else:
      stream_end_index = len(streamed_system_times_s)-1
    # It seems to take about 10-30 frames or so for the stream to settle,
    #  so remove the initial frames from the datasets.
    #  (often these initial frames will be received super close together rather than
    #   at a reasonable sampling rate).
    #  Update: XsensStreamer now discards the first 0.1 seconds of data, so this
    #   should address the above issue, but still trim the dataset just in case.
    # A few ending frames also sometimes seem strange, so remove those too.
    settling_frame_count = 50
    if (stream_end_index - stream_start_index) > settling_frame_count:
      stream_start_index = stream_start_index + settling_frame_count
    if (stream_end_index - stream_start_index) > settling_frame_count:
      stream_end_index = stream_end_index - settling_frame_count
    # Apply the desired trimming.
    streamed_system_times_s = streamed_system_times_s[stream_start_index:stream_end_index+1]
    streamed_frame_numbers = streamed_frame_numbers[stream_start_index:stream_end_index+1]
    streamed_xsens_times_since_start_s = streamed_xsens_times_since_start_s[stream_start_index:stream_end_index+1]
    if streamed_xsens_time_s is not None:
      streamed_xsens_time_s = streamed_xsens_time_s[stream_start_index:stream_end_index+1]
  
    # Interpolate between missed frames to generate a system time for every Excel frame
    #  that estimates when it would have arrived during live streaming.
    # The streaming may have skipped frames due to network stream limitations,
    #  but a piecewise linear interpolation can be used between known frames.
    # For frames before streaming started or after streaming ended, fit a
    #  linear line to all known points and use it to extrapolate.
    all_frame_numbers = np.array(all_frame_numbers)
    frame_numbers_preStream = all_frame_numbers[all_frame_numbers < min(streamed_frame_numbers)]
    frame_numbers_inStream = all_frame_numbers[(all_frame_numbers >= min(streamed_frame_numbers)) & (all_frame_numbers <= max(streamed_frame_numbers))]
    frame_numbers_postStream = all_frame_numbers[all_frame_numbers > max(streamed_frame_numbers)]
    # Interpolate/extrapolate for the system time.
    (number_to_time_m, number_to_time_b) = np.polyfit(streamed_frame_numbers, streamed_system_times_s, deg=1)
    frame_times_s_preStream = frame_numbers_preStream * number_to_time_m + number_to_time_b
    frame_times_s_postStream = frame_numbers_postStream * number_to_time_m + number_to_time_b
    frame_times_s_inStream = np.interp(frame_numbers_inStream, streamed_frame_numbers, streamed_system_times_s)
    all_system_times_s = np.concatenate((frame_times_s_preStream,
                                         frame_times_s_inStream,
                                         frame_times_s_postStream))
    # Return the results and some useful intermediaries.
    return (all_system_times_s,
            streamed_system_times_s, streamed_frame_numbers,
            streamed_xsens_time_s, streamed_xsens_times_since_start_s,
            frame_numbers_preStream, frame_numbers_postStream, frame_numbers_inStream)
  
  # Update a streamed data log with data recorded from the Xsens software and exported to Excel.
  def _merge_excel_data_with_streamed_data(self, excel_filepath,
                                           hdf5_file_toUpdate, hdf5_file_archived):
  
    self._log_status('XsensStreamer merging streamed data with Xsens Excel data')
    
    # Load the Excel data.
    # Will be a dictionary mapping sheet names to dataframes.
    self._log_debug('Loading exported Xsens data from %s' % excel_filepath)
    excel_dataframes = pandas.read_excel(excel_filepath, sheet_name=None)
    
    # Get a list of frame numbers recorded in the Xsens data.
    # This will be the same for all sheets with real data, but sheets
    #  such as metadata and 'Markers' should be skipped.
    all_frame_numbers = None
    num_frames = 0
    for (sheet_name, dataframe) in excel_dataframes.items():
      if 'Frame' in dataframe:
        sheet_frame_numbers = np.array(dataframe.Frame)
        if len(sheet_frame_numbers) > num_frames:
          all_frame_numbers = sheet_frame_numbers
          num_frames = len(all_frame_numbers)
    assert num_frames > 0

    # Interpolate between missed frames to generate a system time for every Excel frame
    #  that estimates when it would have arrived during live streaming.
    (all_system_times_s,
     streamed_system_times_s, streamed_frame_numbers,
     streamed_xsens_time_s, streamed_xsens_times_since_start_s,
     frame_numbers_preStream, frame_numbers_postStream, frame_numbers_inStream) \
      = self._interpolate_system_time(hdf5_file_toUpdate, all_frame_numbers)
      
    # Record a timestamp for every frame in the Excel file that estimates when the data was recorded.
    # This could be done by
    #   1) estimating the start time then assuming Xsens sampled perfectly at a fixed rate,
    #   2) interpolating between timestamps recorded by the Xsens device for streamed frames,
    #   3) interpolating between the times at which data was received by Python for streamed frames.
    # See above comments/code regarding the system-time interpolation approach.
    #   Note that system times at which data was received include network/processing delays.
    # Assuming a constant rate is usually a bit precarious for hardware systems,
    #   but some testing indicates that it does yield times that line up very nicely
    #   with the streamed times at which data was received (with the streamed times
    #   being a bit erratic around the straight constant-fps line, as would be
    #   expected for somewhat stochastic network delays).
    #  Also, exporting data as MVNX and importing into Excel as an XML file to inspect
    #   the device timestamps indicates that assuming a constant rate would yield errors
    #   between -0.5ms and 0.75ms (with a few outliers at -1.3ms),
    #   and this error bound is constant even after ~20s.
    # Interpolating Xsens device timestamps seems promising, but how well the extrapolation
    #  works to data before the stream start and after the stream end has not been tested.
    # So for now, the 'constant-rate' assumption is preferred.
    if self._postprocessing_time_strategy == 'constant-rate':
      # Get a sequence of frame times assuming a constant rate and starting at 0.
      xsens_Fs = 60.0
      xsens_Ts = 1/xsens_Fs
      all_times_s = all_frame_numbers * xsens_Ts
      all_xsens_times_since_start_s = all_times_s - min(all_times_s) # min(all_times_s) should be 0 since Xsens always starts recording frame indexes at 0, but include just in case
      # Shift the Excel times so they represent 'real' time instead of starting at 0.
      # Compute the average offset between the Excel time and the real time
      #  for each streamed frame, to average over network/processing delays
      #  instead of just using one frame to compute the Excel start time.
      offsets = []
      for index_streamed in range(len(streamed_frame_numbers)):
        frame_streamed = streamed_frame_numbers[index_streamed]
        if streamed_xsens_time_s is not None:
          t_streamed = streamed_xsens_time_s[index_streamed]
        else:
          t_streamed = streamed_system_times_s[index_streamed]
        index_excel = np.where(all_frame_numbers == frame_streamed)[0][0]
        t_excel = all_times_s[index_excel]
        offsets.append(t_streamed - t_excel)
      all_times_s = all_times_s + np.mean(offsets)
    elif self._postprocessing_time_strategy == 'interpolate-system':
      # Use the interpolations computed above
      all_times_s = all_system_times_s
      # Interpolate/extrapolate for the Xsens time since start.
      (number_to_time_m, number_to_time_b) = np.polyfit(streamed_frame_numbers, streamed_xsens_times_since_start_s, deg=1)
      frame_times_since_start_s_preStream = frame_numbers_preStream * number_to_time_m + number_to_time_b
      frame_times_since_start_s_postStream = frame_numbers_postStream * number_to_time_m + number_to_time_b
      frame_times_since_start_s_inStream = np.interp(frame_numbers_inStream, streamed_frame_numbers, streamed_xsens_times_since_start_s)
      all_xsens_times_since_start_s = np.concatenate((frame_times_since_start_s_preStream,
                                                      frame_times_since_start_s_inStream,
                                                      frame_times_since_start_s_postStream))
    elif self._postprocessing_time_strategy == 'interpolate-xsens' and streamed_xsens_time_s is not None:
      # Interpolate/extrapolate the Xsens timestamps.
      (number_to_time_m, number_to_time_b) = np.polyfit(streamed_frame_numbers, streamed_xsens_time_s, deg=1)
      frame_times_s_preStream = frame_numbers_preStream * number_to_time_m + number_to_time_b
      frame_times_s_postStream = frame_numbers_postStream * number_to_time_m + number_to_time_b
      frame_times_s_inStream = np.interp(frame_numbers_inStream, streamed_frame_numbers, streamed_xsens_time_s)
      all_times_s = np.concatenate((frame_times_s_preStream,
                                      frame_times_s_inStream,
                                      frame_times_s_postStream))
      all_xsens_times_since_start_s = all_times_s - min(all_times_s)
    else:
      raise AssertionError('Invalid post-processing time strategy: ' + self._postprocessing_time_strategy)
      
    # Compute time strings for each timestamp.
    all_times_str = [get_time_str(t, '%Y-%m-%d %H:%M:%S.%f') for t in all_times_s]
    
    # Move all streamed data to the archive HDF5 file.
    self._log_debug('Moving streamed data to the archive HDF5 file')
    for (device_name, device_group) in hdf5_file_toUpdate.items():
      if 'xsens-' in device_name:
        hdf5_file_toUpdate.copy(device_group, hdf5_file_archived,
                                name=None, shallow=False,
                                expand_soft=True, expand_external=True, expand_refs=True,
                                without_attrs=False)
        device_group_metadata = dict(device_group.attrs.items())
        hdf5_file_archived[device_name].attrs.update(device_group_metadata)
        del hdf5_file_toUpdate[device_name]
    
    # Import Excel data into the HDF5 file.
    self._log_debug('Importing data from Excel to the new HDF5 file')
    
    def add_hdf5_data(device_name, stream_name,
                      excel_sheet_name,
                      target_data_shape_per_frame,
                      data=None, # if given, will be used instead of Excel data (sheet name and target shape arguments are ignored)
                      data_processing_fn=None,
                      stream_group_metadata=None):
      # Extract the desired sheet data.
      if data is None:
        dataframe = excel_dataframes[excel_sheet_name]
        data = dataframe.to_numpy()
        # Remove the 'Frame' column.
        data = data[:, 1:]
        # Reshape so that data for each frame has the desired shape.
        data = data.reshape((data.shape[0], *target_data_shape_per_frame))
        assert data.shape[0] == num_frames
        # Process the data if desired.
        if callable(data_processing_fn):
          data = data_processing_fn(data)
      
      # Add the data to the HDF5 file.
      if device_name not in hdf5_file_toUpdate:
        hdf5_file_toUpdate.create_group(device_name)
      if stream_name in hdf5_file_toUpdate[device_name]:
        del hdf5_file_toUpdate[device_name][stream_name]
      hdf5_file_toUpdate[device_name].create_group(stream_name)
      stream_group = hdf5_file_toUpdate[device_name][stream_name]
      stream_group.create_dataset('data', data=data)
      stream_group.create_dataset('xsens_sample_number', [num_frames, 1],
                                  data=all_frame_numbers)
      stream_group.create_dataset('xsens_time_since_start_s', [num_frames, 1],
                                  data=all_xsens_times_since_start_s)
      stream_group.create_dataset('time_s', [num_frames, 1], dtype='float64',
                                  data=all_times_s)
      stream_group.create_dataset('time_str', [num_frames, 1], dtype='S26',
                                  data=all_times_str)
      # Copy the original device-level and stream-level metadata.
      if device_name in hdf5_file_archived:
        archived_device_group = hdf5_file_archived[device_name]
        device_group_metadata_original = dict(archived_device_group.attrs.items())
        hdf5_file_toUpdate[device_name].attrs.update(device_group_metadata_original)
        if stream_name in archived_device_group:
          archived_stream_group = archived_device_group[stream_name]
          stream_group_metadata_original = dict(archived_stream_group.attrs.items())
          hdf5_file_toUpdate[device_name][stream_name].attrs.update(stream_group_metadata_original)
      else:
        # Create a basic device-level metadata if there was none to copy from the original file.
        device_group_metadata = {SensorStreamer.metadata_class_name_key: type(self).__name__}
        hdf5_file_toUpdate[device_name].attrs.update(device_group_metadata)
      # Override with provided stream-level metadata if desired.
      if stream_group_metadata is not None:
        hdf5_file_toUpdate[device_name][stream_name].attrs.update(
            convert_dict_values_to_str(stream_group_metadata, preserve_nested_dicts=False))
    
    # Define the data notes to use for each stream.
    self._define_data_notes()
    
    # Segment orientation data (quaternion)
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='orientation_quaternion',
                  excel_sheet_name='Segment Orientation - Quat',
                  target_data_shape_per_frame=[-1, 4], # 4-element quaternion per segment per frame
                  data_processing_fn=None,
                  stream_group_metadata=self._data_notes_excel['xsens-segments']['orientation_quaternion'])
    # Segment orientation data (Euler)
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='orientation_euler_deg',
                  excel_sheet_name='Segment Orientation - Euler',
                  target_data_shape_per_frame=[-1, 3], # 3-element Euler vector per segment per frame
                  data_processing_fn=None,
                  stream_group_metadata=self._data_notes_excel['xsens-segments']['orientation_euler_deg'])
    
    # Segment position data.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='position_cm',
                  excel_sheet_name='Segment Position',
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  data_processing_fn=lambda data: data*100.0, # convert from m to cm
                  stream_group_metadata=self._data_notes_excel['xsens-segments']['position_cm'])
    # Segment velocity data.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='velocity_cm_s',
                  excel_sheet_name='Segment Velocity',
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  data_processing_fn=lambda data: data*100.0, # convert from m to cm
                  stream_group_metadata=self._data_notes_excel['xsens-segments']['velocity_cm_s'])
    # Segment acceleration data.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='acceleration_cm_ss',
                  excel_sheet_name='Segment Acceleration',
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  data_processing_fn=lambda data: data*100.0, # convert from m to cm
                  stream_group_metadata=self._data_notes_excel['xsens-segments']['acceleration_cm_ss'])
    # Segment angular velocity.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='angular_velocity_deg_s',
                  excel_sheet_name='Segment Angular Velocity',
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  data_processing_fn=lambda data: data*180.0/np.pi, # convert from rad to deg
                  stream_group_metadata=self._data_notes_excel['xsens-segments']['angular_velocity_deg_s'])
    # Segment angular acceleration.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='angular_acceleration_deg_ss',
                  excel_sheet_name='Segment Angular Acceleration',
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  data_processing_fn=lambda data: data*180.0/np.pi, # convert from rad to deg
                  stream_group_metadata=self._data_notes_excel['xsens-segments']['angular_acceleration_deg_ss'])

    # Joint angles ZXY.
    add_hdf5_data(device_name='xsens-joints',
                  stream_name='rotation_zxy_deg',
                  excel_sheet_name='Joint Angles ZXY',
                  target_data_shape_per_frame=[-1, 3], # 3-element vector per segment per frame
                  data_processing_fn=None,
                  stream_group_metadata=self._data_notes_excel['xsens-joints']['rotation_zxy_deg'])
    # Joint angles XZY.
    add_hdf5_data(device_name='xsens-joints',
                  stream_name='rotation_xzy_deg',
                  excel_sheet_name='Joint Angles XZY',
                  target_data_shape_per_frame=[-1, 3], # 3-element vector per segment per frame
                  data_processing_fn=None,
                  stream_group_metadata=self._data_notes_excel['xsens-joints']['rotation_xzy_deg'])
    # Ergonomic joint angles ZXY.
    add_hdf5_data(device_name='xsens-ergonomic-joints',
                  stream_name='rotation_zxy_deg',
                  excel_sheet_name='Ergonomic Joint Angles ZXY',
                  target_data_shape_per_frame=[-1, 3], # 3-element vector per segment per frame
                  data_processing_fn=None,
                  stream_group_metadata=self._data_notes_excel['xsens-ergonomic-joints']['rotation_zxy_deg'])
    # Ergonomic joint angles XZY.
    add_hdf5_data(device_name='xsens-ergonomic-joints',
                  stream_name='rotation_xzy_deg',
                  excel_sheet_name='Ergonomic Joint Angles XZY',
                  target_data_shape_per_frame=[-1, 3], # 3-element vector per segment per frame
                  data_processing_fn=None,
                  stream_group_metadata=self._data_notes_excel['xsens-ergonomic-joints']['rotation_xzy_deg'])

    # Center of mass position.
    add_hdf5_data(device_name='xsens-CoM',
                  stream_name='position_cm',
                  excel_sheet_name='Center of Mass',
                  target_data_shape_per_frame=[9], # 9-element vector per segment per frame (x/y/z for position/velocity/acceleration)
                  data_processing_fn=lambda data: data[:, 0:3]*100.0, # convert from m to cm, and select the 3 position columns
                  stream_group_metadata=self._data_notes_excel['xsens-CoM']['position_cm'])
    # Center of mass velocity.
    add_hdf5_data(device_name='xsens-CoM',
                  stream_name='velocity_cm_s',
                  excel_sheet_name='Center of Mass',
                  target_data_shape_per_frame=[9], # 9-element vector per segment per frame (x/y/z for position/velocity/acceleration)
                  data_processing_fn=lambda data: data[:, 3:6]*100.0, # convert from m to cm, and select the 3 velocity columns
                  stream_group_metadata=self._data_notes_excel['xsens-CoM']['velocity_cm_s'])
    # Center of mass acceleration.
    add_hdf5_data(device_name='xsens-CoM',
                  stream_name='acceleration_cm_ss',
                  excel_sheet_name='Center of Mass',
                  target_data_shape_per_frame=[9], # 9-element vector per segment per frame (x/y/z for position/velocity/acceleration)
                  data_processing_fn=lambda data: data[:, 6:9]*100.0, # convert from m to cm, and select the 3 acceleration columns
                  stream_group_metadata=self._data_notes_excel['xsens-CoM']['acceleration_cm_ss'])
    
    # Sensor data - acceleration
    add_hdf5_data(device_name='xsens-sensors',
                  stream_name='free_acceleration_cm_ss',
                  excel_sheet_name='Sensor Free Acceleration',
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  data_processing_fn=lambda data: data*100.0, # convert from m to cm
                  stream_group_metadata=self._data_notes_excel['xsens-sensors']['free_acceleration_cm_ss'])
    # Sensor data - magnetic field
    add_hdf5_data(device_name='xsens-sensors',
                  stream_name='magnetic_field',
                  excel_sheet_name='Sensor Magnetic Field',
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  data_processing_fn=None,
                  stream_group_metadata=self._data_notes_excel['xsens-sensors']['magnetic_field'])
    # Sensor data - orientation
    add_hdf5_data(device_name='xsens-sensors',
                  stream_name='orientation_quaternion',
                  excel_sheet_name='Sensor Orientation - Quat',
                  target_data_shape_per_frame=[-1, 4], # 4-element quaternion per segment per frame
                  data_processing_fn=None,
                  stream_group_metadata=self._data_notes_excel['xsens-sensors']['orientation_quaternion'])
    # Sensor data - orientation
    add_hdf5_data(device_name='xsens-sensors',
                  stream_name='orientation_euler_deg',
                  excel_sheet_name='Sensor Orientation - Euler',
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  data_processing_fn=None,
                  stream_group_metadata=self._data_notes_excel['xsens-sensors']['orientation_euler_deg'])
    
    # Sytem time
    add_hdf5_data(device_name='xsens-time',
                  stream_name='stream_receive_time_s',
                  excel_sheet_name=None,
                  target_data_shape_per_frame=None,
                  data=all_system_times_s,
                  stream_group_metadata=self._data_notes_excel['xsens-time']['stream_receive_time_s'])

  # Update a streamed data log with data recorded from the Xsens software exported to MVNX.
  def _merge_mvnx_data_with_streamed_data(self, mvnx_filepath,
                                         hdf5_file_toUpdate, hdf5_file_archived):
  
    self._log_status('XsensStreamer merging streamed data with Xsens MVNX data')
    
    # Read and parse the MVNX file as an XML file.
    self._log_debug('Reading and parsing the MVNX file')
    with open(mvnx_filepath, 'r') as fin:
      mvnx_contents = fin.read()
    mvnx_data = BeautifulSoup(mvnx_contents, 'xml')
    
    # Extract all of the frames, ignoring the first few that are empty rows.
    self._log_debug('Extracting streams from the MVNX data')
    frames = mvnx_data.find_all('frame')
    frame_indexes = [frame.get('index') for frame in frames]
    frames = [frame for (i, frame) in enumerate(frames) if frame_indexes[i].isnumeric()]
    frame_indexes = [int(frame_index) for frame_index in frame_indexes if frame_index.isnumeric()]
    num_frames = len(frames)
    
    # Get time information.
    times_since_start_s = [float(frame.get('time'))/1000.0 for frame in frames]
    times_utc_str = [frame.get('tc') for frame in frames]
    times_s = [float(frame.get('ms'))/1000.0 for frame in frames]
    times_str = [get_time_str(time_s, '%Y-%m-%d %H:%M:%S.%f') for time_s in times_s]
    
    # Check that the timestamps monotonically increase.
    times_s_np = np.array(times_s)
    times_s_diffs = np.diff(times_s_np)
    if np.any(times_s_diffs < 0):
      print_var(times_str, 'times_str')
      msg = '\n'*2
      msg += 'x'*75
      msg += 'XsensStreamer aborting merge due to incorrect timestamps in the MVNX file (they are not monotonically increasing)'
      msg += 'x'*75
      msg = '\n'*2
      self._log_status(msg)
      return
    
    # A helper to get a matrix of data for a given tag, such as 'position'.
    def get_tagged_data(tag):
      datas = [frame.find_all(tag)[0] for frame in frames]
      data = np.array([[float(x) for x in data.contents[0].split()] for data in datas])
      return data
    
    # Extract the data!
    segment_positions_body_cm                 = get_tagged_data('position')*100.0 # convert from m to cm
    segment_orientations_body_quaternion      = get_tagged_data('orientation')
    segment_velocities_body_cm_s              = get_tagged_data('velocity')*100.0 # convert from m to cm
    segment_accelerations_body_cm_ss          = get_tagged_data('acceleration')*100.0 # convert from m to cm
    segment_angular_velocities_body_deg_s     = get_tagged_data('angularVelocity')*180.0/np.pi # convert from radians to degrees
    segment_angular_accelerations_body_deg_ss = get_tagged_data('angularAcceleration')*180.0/np.pi # convert from radians to degrees
    foot_contacts                             = get_tagged_data('footContacts')
    sensor_freeAccelerations_cm_ss            = get_tagged_data('sensorFreeAcceleration')*100.0 # convert from m to cm
    sensor_magnetic_fields                    = get_tagged_data('sensorMagneticField')
    sensor_orientations_quaternion            = get_tagged_data('sensorOrientation')
    joint_angles_zxy_body_deg                 = get_tagged_data('jointAngle')
    joint_angles_xzy_body_deg                 = get_tagged_data('jointAngleXZY')
    ergonomic_joint_angles_zxy_deg            = get_tagged_data('jointAngleErgo')
    ergonomic_joint_angles_xzy_deg            = get_tagged_data('jointAngleErgoXZY')
    center_of_mass                            = get_tagged_data('centerOfMass')
    center_of_mass_positions_cm               = center_of_mass[:, 0:3]*100.0 # convert from m to cm
    center_of_mass_velocities_cm_s            = center_of_mass[:, 3:6]*100.0 # convert from m to cm
    center_of_mass_accelerations_cm_ss        = center_of_mass[:, 6:9]*100.0 # convert from m to cm
    try:
      segment_positions_fingersLeft_cm             = get_tagged_data('positionFingersLeft')*100.0
      segment_positions_fingersRight_cm            = get_tagged_data('positionFingersRight')*100.0
      segment_orientations_fingersLeft_quaternion  = get_tagged_data('orientationFingersLeft')
      segment_orientations_fingersRight_quaternion = get_tagged_data('orientationFingersRight')
      joint_angles_zxy_fingersLeft_deg             = get_tagged_data('jointAngleFingersLeft')
      joint_angles_zxy_fingersRight_deg            = get_tagged_data('jointAngleFingersRight')
      joint_angles_xzy_fingersLeft_deg             = get_tagged_data('jointAngleFingersLeftXZY')
      joint_angles_xzy_fingersRight_deg            = get_tagged_data('jointAngleFingersRightXZY')
      segment_positions_all_cm = np.concatenate((segment_positions_body_cm,
                                                 segment_positions_fingersLeft_cm,
                                                 segment_positions_fingersRight_cm),
                                                axis=1)
      segment_orientations_all_quaternion = np.concatenate((segment_orientations_body_quaternion,
                                                            segment_orientations_fingersLeft_quaternion,
                                                            segment_orientations_fingersRight_quaternion),
                                                           axis=1)
      joint_angles_zxy_all_deg = np.concatenate((joint_angles_zxy_body_deg,
                                                 joint_angles_zxy_fingersLeft_deg,
                                                 joint_angles_zxy_fingersRight_deg),
                                                axis=1)
      joint_angles_xzy_all_deg = np.concatenate((joint_angles_xzy_body_deg,
                                                 joint_angles_xzy_fingersLeft_deg,
                                                 joint_angles_xzy_fingersRight_deg),
                                                axis=1)
    except IndexError: # fingers were not included in the data
      segment_positions_all_cm = segment_positions_body_cm
      segment_orientations_all_quaternion = segment_orientations_body_quaternion
      joint_angles_zxy_all_deg = joint_angles_zxy_body_deg
      joint_angles_xzy_all_deg = joint_angles_xzy_body_deg
    
    # Get the number of segments and sensors
    num_segments_body = segment_orientations_body_quaternion.shape[1]/4
    assert num_segments_body == int(num_segments_body)
    num_segments_body = int(num_segments_body)
    num_segments_all = segment_orientations_all_quaternion.shape[1]/4
    assert num_segments_all == int(num_segments_all)
    num_segments_all = int(num_segments_all)
    num_sensors = sensor_orientations_quaternion.shape[1]/4
    assert num_sensors == int(num_sensors)
    num_sensors = int(num_sensors)

    # Create Euler orientations from quaternion orientations.
    segment_orientations_all_euler_deg = np.empty([num_frames, 3*num_segments_all])
    for segment_index in range(num_segments_all):
      for frame_index in range(num_frames):
        eulers_deg = euler_from_quaternion(*segment_orientations_all_quaternion[frame_index, (segment_index*4):(segment_index*4+4)])
        segment_orientations_all_euler_deg[frame_index, (segment_index*3):(segment_index*3+3)] = eulers_deg
    sensor_orientations_euler_deg = np.empty([num_frames, 3*num_sensors])
    for sensor_index in range(num_sensors):
      for frame_index in range(num_frames):
        eulers_deg = euler_from_quaternion(*sensor_orientations_quaternion[frame_index, (sensor_index*4):(sensor_index*4+4)])
        sensor_orientations_euler_deg[frame_index, (sensor_index*3):(sensor_index*3+3)] = eulers_deg

    # Create streams of joint child and parent IDs from the streamed HDF5 file.
    # Note that it is always the same, so only need to reference one streamed entry.
    joint_child_data = hdf5_file_toUpdate['xsens-joints']['child']['data'][0]
    joint_parent_data = hdf5_file_toUpdate['xsens-joints']['parent']['data'][0]
    joint_child_data  = np.tile(np.array(joint_child_data), [num_frames, 1])
    joint_parent_data = np.tile(np.array(joint_parent_data), [num_frames, 1])
    
    # Move all streamed data to the archive HDF5 file.
    self._log_debug('Moving streamed data to the archive HDF5 file')
    for (device_name, device_group) in hdf5_file_toUpdate.items():
      if 'xsens-' in device_name:
        hdf5_file_toUpdate.copy(device_group, hdf5_file_archived,
                                name=None, shallow=False,
                                expand_soft=True, expand_external=True, expand_refs=True,
                                without_attrs=False)
        device_group_metadata = dict(device_group.attrs.items())
        hdf5_file_archived[device_name].attrs.update(device_group_metadata)
        del hdf5_file_toUpdate[device_name]

    # Interpolate between missed frames to generate a system time for every Excel frame
    #  that estimates when it would have arrived during live streaming.
    interpolation_results = self._interpolate_system_time(hdf5_file_archived, frame_indexes)
    system_times_s = interpolation_results[0]
    
    # Helper to import the MVNX data into the HDF5 file.
    def add_hdf5_data(device_name, stream_name,
                      data, target_data_shape_per_frame,
                      stream_group_metadata=None):
      # Reshape so that data for each frame has the desired shape.
      data = data.reshape((data.shape[0], *target_data_shape_per_frame))
      assert data.shape[0] == num_frames
      # Create the stream group.
      if device_name not in hdf5_file_toUpdate:
        hdf5_file_toUpdate.create_group(device_name)
      if stream_name in hdf5_file_toUpdate[device_name]:
        del hdf5_file_toUpdate[device_name][stream_name]
      hdf5_file_toUpdate[device_name].create_group(stream_name)
      stream_group = hdf5_file_toUpdate[device_name][stream_name]
      # Create the datasets.
      stream_group.create_dataset('data', data=data)
      stream_group.create_dataset('xsens_sample_number', [num_frames, 1],
                                  data=frame_indexes)
      stream_group.create_dataset('xsens_time_since_start_s', [num_frames, 1],
                                  data=times_since_start_s)
      stream_group.create_dataset('time_s', [num_frames, 1], dtype='float64',
                                  data=times_s)
      stream_group.create_dataset('time_str', [num_frames, 1], dtype='S26',
                                  data=times_str)
      # Copy the original device-level and stream-level metadata.
      if device_name in hdf5_file_archived:
        archived_device_group = hdf5_file_archived[device_name]
        device_group_metadata_original = dict(archived_device_group.attrs.items())
        hdf5_file_toUpdate[device_name].attrs.update(device_group_metadata_original)
        if stream_name in archived_device_group:
          archived_stream_group = archived_device_group[stream_name]
          stream_group_metadata_original = dict(archived_stream_group.attrs.items())
          hdf5_file_toUpdate[device_name][stream_name].attrs.update(stream_group_metadata_original)
      else:
        # Create a basic device-level metadata if there was none to copy from the original file.
        device_group_metadata = {SensorStreamer.metadata_class_name_key: type(self).__name__}
        hdf5_file_toUpdate[device_name].attrs.update(device_group_metadata)
      # Override with provided stream-level metadata if desired.
      if stream_group_metadata is not None:
        hdf5_file_toUpdate[device_name][stream_name].attrs.update(
            convert_dict_values_to_str(stream_group_metadata, preserve_nested_dicts=False))

    # Define the data notes to use for each stream.
    self._define_data_notes()
    
    # Import the data!
    self._log_debug('Importing data to the new HDF5 file')
    
    # Segment orientation data (quaternion)
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='orientation_quaternion',
                  data=segment_orientations_all_quaternion,
                  target_data_shape_per_frame=[-1, 4], # 4-element quaternion per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-segments']['orientation_quaternion'])
    # Segment orientation data (Euler)
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='orientation_euler_deg',
                  data=segment_orientations_all_euler_deg,
                  target_data_shape_per_frame=[-1, 3], # 3-element Euler vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-segments']['orientation_euler_deg'])

    # Segment position data.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='position_cm',
                  data=segment_positions_all_cm,
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-segments']['position_cm'])
    # Segment velocity data.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='velocity_cm_s',
                  data=segment_velocities_body_cm_s,
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-segments']['velocity_cm_s'])
    # Segment acceleration data.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='acceleration_cm_ss',
                  data=segment_accelerations_body_cm_ss,
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-segments']['acceleration_cm_ss'])
    # Segment angular velocity.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='angular_velocity_deg_s',
                  data=segment_angular_velocities_body_deg_s,
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-segments']['angular_velocity_deg_s'])
    # Segment angular acceleration.
    add_hdf5_data(device_name='xsens-segments',
                  stream_name='angular_acceleration_deg_ss',
                  data=segment_angular_accelerations_body_deg_ss,
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-segments']['angular_acceleration_deg_ss'])

    # Joint angles ZXY.
    add_hdf5_data(device_name='xsens-joints',
                  stream_name='rotation_zxy_deg',
                  data=joint_angles_zxy_all_deg,
                  target_data_shape_per_frame=[-1, 3], # 3-element vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-joints']['rotation_zxy_deg'])
    # Joint angles XZY.
    add_hdf5_data(device_name='xsens-joints',
                  stream_name='rotation_xzy_deg',
                  data=joint_angles_xzy_all_deg,
                  target_data_shape_per_frame=[-1, 3], # 3-element vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-joints']['rotation_xzy_deg'])
    # Ergonomic joint angles ZXY.
    add_hdf5_data(device_name='xsens-ergonomic-joints',
                  stream_name='rotation_zxy_deg',
                  data=ergonomic_joint_angles_zxy_deg,
                  target_data_shape_per_frame=[-1, 3], # 3-element vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-ergonomic-joints']['rotation_zxy_deg'])
    # Ergonomic joint angles XZY.
    add_hdf5_data(device_name='xsens-ergonomic-joints',
                  stream_name='rotation_xzy_deg',
                  data=ergonomic_joint_angles_xzy_deg,
                  target_data_shape_per_frame=[-1, 3], # 3-element vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-ergonomic-joints']['rotation_xzy_deg'])
    # Joint child and parent IDs.
    add_hdf5_data(device_name='xsens-joints',
                  stream_name='child',
                  data=joint_child_data,
                  target_data_shape_per_frame=[joint_child_data.shape[1]], # 28-element vector per frame
                  stream_group_metadata=self._data_notes_stream['xsens-joints']['child'])
    add_hdf5_data(device_name='xsens-joints',
                  stream_name='parent',
                  data=joint_parent_data,
                  target_data_shape_per_frame=[joint_parent_data.shape[1]], # 28-element vector per frame
                  stream_group_metadata=self._data_notes_stream['xsens-joints']['parent'])
    
    # Center of mass position.
    add_hdf5_data(device_name='xsens-CoM',
                  stream_name='position_cm',
                  data=center_of_mass_positions_cm,
                  target_data_shape_per_frame=[3], # 3-element x/y/z vector per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-CoM']['position_cm'])
    # Center of mass velocity.
    add_hdf5_data(device_name='xsens-CoM',
                  stream_name='velocity_cm_s',
                  data=center_of_mass_velocities_cm_s,
                  target_data_shape_per_frame=[3], # 3-element x/y/z vector per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-CoM']['velocity_cm_s'])
    # Center of mass acceleration.
    add_hdf5_data(device_name='xsens-CoM',
                  stream_name='acceleration_cm_ss',
                  data=center_of_mass_accelerations_cm_ss,
                  target_data_shape_per_frame=[3], # 3-element x/y/z vector per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-CoM']['acceleration_cm_ss'])

    # Sensor data - acceleration
    add_hdf5_data(device_name='xsens-sensors',
                  stream_name='free_acceleration_cm_ss',
                  data=sensor_freeAccelerations_cm_ss,
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-sensors']['free_acceleration_cm_ss'])
    # Sensor data - magnetic field
    add_hdf5_data(device_name='xsens-sensors',
                  stream_name='magnetic_field',
                  data=sensor_magnetic_fields,
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-sensors']['magnetic_field'])
    # Sensor data - orientation
    add_hdf5_data(device_name='xsens-sensors',
                  stream_name='orientation_quaternion',
                  data=sensor_orientations_quaternion,
                  target_data_shape_per_frame=[-1, 4], # 4-element quaternion vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-sensors']['orientation_quaternion'])
    # Sensor data - orientation
    add_hdf5_data(device_name='xsens-sensors',
                  stream_name='orientation_euler_deg',
                  data=sensor_orientations_euler_deg,
                  target_data_shape_per_frame=[-1, 3], # 3-element x/y/z vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-sensors']['orientation_euler_deg'])

    # Foot contacts
    add_hdf5_data(device_name='xsens-foot-contacts',
                  stream_name='foot_contact_points',
                  data=foot_contacts,
                  target_data_shape_per_frame=[4], # 4-element contact vector per segment per frame
                  stream_group_metadata=self._data_notes_mvnx['xsens-foot-contacts']['foot-contacts'])
  
    # System time
    add_hdf5_data(device_name='xsens-time',
                  stream_name='stream_receive_time_s',
                  data=system_times_s,
                  target_data_shape_per_frame=[1],
                  stream_group_metadata=self._data_notes_mvnx['xsens-time']['stream_receive_time_s'])
  