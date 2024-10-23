import glob
from multiprocessing import Process
import os

import zmq

from utils.time_utils import *
from utils.dict_utils import *
from utils.print_utils import *

from sensor_streamers.SensorStreamer import SensorStreamer

################################################
################################################
# PUB-SUB Proxy to manage a collection of SensorStreamer objects.
# Hosts control logic of interactive proxy/server.
# Will launch/destroy/connect to streamers on creation and ad-hoc.
# Will use a separate process for each streamer.
# Will use the main process for stdin 
#   and for REQ-REP transactions.
# Each SensorStreamer connects only to its local Proxy,
#   which then exposes its data to outside LAN subscribers.
################################################
################################################
class StreamerManager:

  ########################
  ###### INITIALIZE ######
  ########################

  # @param sensor_streamer_specs contains dicts that describe what streamers to make.
  #   Each dict should have an entry for 'class' with the class name to instantiate.
  #     It can then have as many keyword arguments for the initializer as desired.
  def __init__(self, ip: str,
              sensor_streamer_specs: list[dict] | tuple[dict] | None = None,
              port_backend: str = "42069", port_frontend: str = "42070",
              port_sync: str = "42071",
              port_killsig: str = "42066",
              print_status: bool = True, print_debug: bool = False) -> None:

    # Import all classes in the sensor_streamers folder.
    # Assumes the class name matches the filename.
    self._sensor_streamer_classes = {}
    sensor_streamer_files = glob.glob(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'sensor_streamers', '*.py'))
    for sensor_streamer_file in sensor_streamer_files:
      try:
        sensor_streamer_class_name = os.path.splitext(os.path.basename(sensor_streamer_file))[0]
        sensor_streamer_module = __import__('sensor_streamers.%s' % sensor_streamer_class_name, fromlist=[sensor_streamer_class_name])
        sensor_streamer_class = getattr(sensor_streamer_module, sensor_streamer_class_name)
        self._sensor_streamer_classes[sensor_streamer_class_name] = sensor_streamer_class
      except:
        pass

    # Record various configuration options.
    self._log_source_tag = 'manager'
    self._ip = ip
    self._port_backend = port_backend
    self._port_frontend = port_frontend
    self._port_sync = port_sync
    self._port_killsig = port_killsig

    #################
    # CONFIGURATION #
    #################
    # NOTE: We don't want streamers to share memory, each is a separate process communicating and sharing data over sockets
    #   ActionSense used multiprocessing.Manager and proxies to access streamers' data from the main process.
    # NOTE: Lab PC needs to receive packets on 2 interfaces - internally (own loopback) and over the network from the wearable PC.
    #   It then brokers data to its workers (data logging, visualization) in an abstract way so they don't have to know sensor topology.
    # NOTE: Wearable PC needs to send packets on 2 interfaces - internally (own loopback) and over the network to the lab PC.
    #   To wearable PC, lab PC looks just like another subscriber.
    # NOTE: Loopback and LAN can use the same port of the device because different interfaces are treated as independent connections.
    # NOTE: Loopback is faster than the network interface of the same device because it doesn't have to go through routing tables.
    
    # Pass exactly one ZeroMQ context instance throughout the program
    self._ctx: zmq.Context = zmq.Context()

    # Exposes a known address and port to locally connected sensors to connect to.
    self._backend: zmq.SyncSocket = self._ctx.socket(zmq.XSUB)
    self._backend.bind("tcp://localhost:%s" % self._port_backend)

    # Exposes a known address and port to broker data to local workers.
    self._frontend: zmq.SyncSocket = self._ctx.socket(zmq.XPUB)
    self._frontend.bind("tcp://localhost:%s" % self._port_frontend)

    # Listener endpoint to receive signals of streamers' readiness
    self._sync: zmq.SyncSocket = self._ctx.socket(zmq.REP)
    self._sync.bind("tcp://*:%s" % self._port_sync)

    # Register sockets to poll for new data
    self._poller: zmq.Poller = zmq.Poller()
    self._poller.register(self._frontend, zmq.POLLIN)
    self._poller.register(self._backend, zmq.POLLIN)

    # Instantiate each desired local streamer.
    # Use ZeroMQ sockets to transfer collected data to other processes.
    self._streamers: list[SensorStreamer] = []

    for streamer_spec in sensor_streamer_specs:
      class_name: str = streamer_spec['class']
      class_args = streamer_spec.copy()
      del(class_args['class'])
      class_args['port_pub'] = self._port_backend
      # Create the class object.
      class_type: type[SensorStreamer] = self._sensor_streamer_classes[class_name]
      class_object: SensorStreamer = class_type(**class_args)
      # Store the streamer object.
      self._streamers.append(class_object)

    self._workers = []
    # Create all desired consumers and connect them to the PUB proxy socket.
    data_logger = DataLogger(sensor_streamers=None,
                            port_sub=port_frontend,
                            **datalogging_options)
    data_visualizer = DataVisualizer(sensor_streamers=None,
                                    port_sub=port_frontend,
                                    **visualization_options)

  #############################
  ###### GETTERS/SETTERS ######
  #############################

  # Get the port number used by the proxy to publish updates on.
  def get_port_frontend(self) -> str:
    return self._port_frontend

  # Exposes a known address and port to remote networked subscribers if configured.
  def expose_to_remote_sub(self) -> None:
    self._is_xpub: bool = True
    self._frontend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XPUB)
    self._frontend_remote.bind("tcp://%s:%s" % self._ip, self._port_frontend)
    self._poller.register(self._frontend_remote, zmq.POLLIN)

  # Connects to a known address and port of external LAN data broker.
  def connect_to_remote_pub(self, addr: str, port_pub: str = "42070") -> None:
    self._is_xsub: bool = True
    self._backend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XSUB)
    self._backend_remote.connect("tcp://%s:%s" % addr, port_pub)
    self._poller.register(self._backend_remote, zmq.POLLIN)


  #####################
  ###### RUNNING ######
  #####################
  def start(self):
    # Start each publisher-subscriber in its own process (e.g. local sensors, data logger, visualizer, AI worker).
    nodes = [*self._streamers, *self._workers]
    
    self._processes: list[Process] = [Process(target=node) for node in nodes]
    for p in self._processes: p.start()

    # TODO: check connection between Proxies has been established before starting subscribers
    # TODO: verify subscribers subscribed to desired topics and publishers ready to send non-dummy data
    # TODO: synchronize all streamers to account for network delays

  # The main run method.
  #   Runs continuously until the user ends the experiment or after the specified duration
  # TODO: check if packets are indeed routed according to desired business logic
  def run(self, duration_s: int | None = None) -> None:
    try:
      # TODO: synchronize all the components of the system, start external recording in DataLogger through common interface

      while True:
        ###########################
        ###### PUB-SUB Proxy ######
        ###########################
        sockets = dict(self._poller.poll())
        # Forwards data packets from local publishers to local subscribers
        #   and to remote subscribers if configured. 
        if self._backend in sockets:
          msg = self._backend.recv_multipart()
          self._frontend.send_multipart(msg)
          if self._is_xpub:
            self._frontend_remote.send_multipart(msg)
        # Forwards subscription packets from local subscribers to local publishers
        #   and to remote publishers if configured.
        if self._frontend in sockets:
          msg = self._frontend.recv_multipart()
          self._backend.send_multipart(msg)
          if self._is_xsub:
            self._backend_remote.send_multipart(msg)
        # Forwards subscription packets from remote subscribers to local publishers
        #   and to remote publishers if configured.
        if self._is_xpub and self._frontend_remote in sockets:
          msg = self._frontend_remote.recv_multipart()
          self._backend.send_multipart(msg)
          if self._is_xsub:
            self._backend_remote.send_multipart(msg)
        # Forwards data packets from remote publishers to local subscribers
        #   and to remote subscribers if configured.
        if self._is_xsub and self._backend_remote in sockets:
          msg = self._backend_remote.recv_multipart()
          self._frontend.send_multipart(msg)
          if self._is_xpub:
            self._frontend_remote.send_multipart(msg)

        ##################################
        ###### REQ-REP transactions ######
        ##################################
    
    # Exit gracefully when user clicks 'end' in GUI or Ctrl+C, or when time runs out.
    #   Send termination signal over another socket to all processes to wrap up.
    except KeyboardInterrupt:
      pass
    finally:
      # wait for each publisher to finish sending and acknowledge end of stream command
      self.stop()


  # Stop each streamer and data logger.
  # TODO:
  def stop(self) -> None:
    # Stop each streamer.
    # TODO: send all a KILL signal and wait for them to exit
    
    # Wait for all the local subprocesses to gracefully exit before terminating the main process
    for p in self._processes: p.join()

    # Clean up
    self._backend.close()
    self._frontend.close()
    if self._is_xpub: self._frontend_remote.close()
    if self._is_xsub: self._backend_remote.close()
    self._sync.close()
    self._ctx.term()
