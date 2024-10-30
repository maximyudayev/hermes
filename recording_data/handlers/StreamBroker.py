import glob
from multiprocessing import Process
import os

import zmq

from utils.time_utils import *
from utils.dict_utils import *
from utils.print_utils import *

from streamers.SensorStreamer import SensorStreamer

################################################
################################################
# PUB-SUB Broker to manage a collection of SensorStreamer objects.
# Hosts control logic of interactive proxy/server.
# Will launch/destroy/connect to streamers on creation and ad-hoc.
# Will use a separate process for each streamer and consumer.
# Will use the main process to:
#   * route PUB-SUB messages
#   * TODO: measure and publish per-sensor network delays
#   * TODO: subscribe to stdin messages
#   * TODO: process REQ-REP transactions
# Each SensorStreamer connects only to its local broker,
#   which then exposes its data to outside LAN subscribers.
################################################
################################################
class StreamBroker:

  ########################
  ###### INITIALIZE ######
  ########################

  def __init__(self, 
               ip: str,
               streamer_specs: list[dict] | tuple[dict] | None = None,
               worker_specs: list[dict] | tuple[dict] | None = None,
               port_backend: str = "42069", 
               port_frontend: str = "42070", 
               port_sync: str = "42071",
               port_killsig: str = "42066",
               print_status: bool = True, print_debug: bool = False) -> None:

    # Import all classes in the sensor_streamers folder.
    # Assumes the class name matches the filename.
    self._sensor_streamer_classes = {}
    sensor_streamer_files = glob.glob(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'streamers', '*.py'))
    for sensor_streamer_file in sensor_streamer_files:
      try:
        sensor_streamer_class_name = os.path.splitext(os.path.basename(sensor_streamer_file))[0]
        sensor_streamer_module = __import__('streamers.%s' % (sensor_streamer_class_name), fromlist=[sensor_streamer_class_name])
        sensor_streamer_class = getattr(sensor_streamer_module, sensor_streamer_class_name)
        self._sensor_streamer_classes[sensor_streamer_class_name] = sensor_streamer_class
      except:
        pass
    self._worker_classes = {}
    worker_files = glob.glob(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'workers', '*.py'))
    for worker_file in worker_files:
      try:
        worker_class_name = os.path.splitext(os.path.basename(worker_file))[0]
        worker_module = __import__('workers.%s' % (worker_class_name), fromlist=[worker_class_name])
        worker_class = getattr(worker_module, worker_class_name)
        self._worker_classes[worker_class_name] = worker_class
      except:
        pass

    # Record various configuration options.
    self._log_source_tag = 'manager'
    self._ip = ip
    self._port_backend = port_backend
    self._port_frontend = port_frontend
    self._port_sync = port_sync
    self._port_killsig = port_killsig
    self._print_status = print_status
    self._print_debug = print_debug

    ###########################
    ###### CONFIGURATION ######
    ###########################
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
    local_backend: zmq.SyncSocket = self._ctx.socket(zmq.XSUB)
    local_backend.bind("tcp://127.0.0.1:%s" % (self._port_backend))
    self._backends: list[zmq.SyncSocket] = [local_backend]

    # Exposes a known address and port to broker data to local workers.
    local_frontend: zmq.SyncSocket = self._ctx.socket(zmq.XPUB)
    local_frontend.bind("tcp://127.0.0.1:%s" % (self._port_frontend))
    self._frontends: list[zmq.SyncSocket] = [local_frontend]

    # Listener endpoint to receive signals of streamers' readiness
    # TODO: decide if we use REP or ROUTER socket for syncing
    self._sync: zmq.SyncSocket = self._ctx.socket(zmq.REP)
    self._sync.bind("tcp://%s:%s" % (self._ip, self._port_sync))

    # Termination control socket to command publishers and subscribers to finish and exit.
    self._killsig_pub: zmq.SyncSocket = self._ctx.socket(zmq.PUB)
    self._killsig_pub.bind("tcp://*:%s" % (self._port_killsig))

    # Poll object to listen to sockets without blocking
    self._poller: zmq.Poller = zmq.Poller()

    # Instantiate each desired local streamer.
    # Use ZeroMQ sockets to transfer collected data to other processes.
    self._streamers: list[SensorStreamer] = []
    for streamer_spec in streamer_specs:
      class_name: str = streamer_spec['class']
      class_args = streamer_spec.copy()
      del(class_args['class'])
      class_args['port_pub'] = self._port_backend      
      class_args['port_sync'] = self._port_sync
      class_args['port_killsig'] = self._port_killsig
      # Create the class object.
      class_type: type[SensorStreamer] = self._sensor_streamer_classes[class_name]
      class_object: SensorStreamer = class_type(**class_args)
      # Store the streamer object.
      self._streamers.append(class_object)

    # Create all desired consumers and connect them to the PUB broker socket.
    self._workers = []
    for worker_spec in worker_specs:
      class_name: str = worker_spec['class']
      class_args = worker_spec.copy()
      del(class_args['class'])
      class_args['port_sub'] = self._port_frontend
      class_args['port_sync'] = self._port_sync
      class_args['port_killsig'] = self._port_killsig
      # Create the class object.
      class_type = self._sensor_streamer_classes[class_name]
      class_object = class_type(**class_args)
      # Store the consumer object.
      self._workers.append(class_object)

  #############################
  ###### GETTERS/SETTERS ######
  #############################

  # Get the port number used by the proxy to publish updates on.
  def get_port_frontend(self) -> str:
    return self._port_frontend

  # Exposes a known address and port to remote networked subscribers if configured.
  def expose_to_remote_sub(self) -> None:
    frontend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XPUB)
    frontend_remote.bind("tcp://%s:%s" % (self._ip, self._port_frontend))
    self._frontends.append(frontend_remote)

  # Connects to a known address and port of external LAN data broker.
  def connect_to_remote_pub(self, addr: str, port_pub: str = "42070") -> None:
    backend_remote: zmq.SyncSocket = self._ctx.socket(zmq.XSUB)
    backend_remote.connect("tcp://%s:%s" % (addr, port_pub))
    self._backends.append(backend_remote)

  # Subscribes to external kill signal (e.g. lab PC in AidFOG project).
  def subscribe_to_killsig(self, addr: str, port_killsig: str = "42066") -> None:
    self._killsig_sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    self._killsig_sub.connect("tcp://%s:%s" % (addr, port_killsig))
    self._killsig_sub.subscribe('kill')
    self._poller.register(self._killsig_sub, zmq.POLLIN)

  # Register PUB-SUB sockets on both interfaces for polling.
  def register_pubsub_for_poll(self) -> None:
    for s in self._backends: self._poller.register(s, zmq.POLLIN)
    for s in self._frontends: self._poller.register(s, zmq.POLLIN)


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
    # TODO: measure network delay to each locally connected sensor on a periodic basis and publish information for the datalogger to record as well

  # The main run method.
  #   Runs continuously until the user ends the experiment or after the specified duration
  def run(self, duration_s: int | None = None) -> None:
    try:
      # TODO: synchronize all the components of the system, start external recording in DataLogger through common interface

      self.register_pubsub_for_poll()
      while True:
        ############################
        ###### PUB-SUB Broker ######
        ############################
        sockets, events = zip(*self._poller.poll())
        for socket in sockets:
          # Forwards data packets from publishers to subscribers. 
          if socket in self._backends:
            msg = socket.recv_multipart()
            for s in self._frontends: s.send_multipart(msg)
          # Forwards subscription packets from subscribers to publishers.
          if socket in self._frontends:
            msg = socket.recv_multipart()
            for s in self._backends: s.send_multipart(msg)
          
          # Receives KILL signal from another broker (e.g. lab PC in AidFOG project).
          # TODO:  
        
        ##################################
        ###### REQ-REP transactions ######
        ##################################
        # TODO:
    
    except KeyboardInterrupt:
      # Exit gracefully when user clicks 'end' in GUI or Ctrl+C, or when time runs out.
      #   Send termination signal over another socket to all processes to wrap up.
      #   Continue brokering packets until signalled by all publishers that there will be no more packets.
      # TODO:
      # self._killsig_pub.send(b'kill')
      pass
    finally:
      # Wait for each publisher to finish sending and acknowledge end of stream command.
      self.stop()

  # def broker()

  # Stop each component of the system before exiting the program.
  def stop(self) -> None:
    # TODO: send all subscribers a KILL signal and wait for them to send the last messages before closing.
    #   Append a frame to the ZeroMQ message that indicates the last message from the sensor. 
    
    # Wait for all the local subprocesses to gracefully exit before terminating the main process.
    for p in self._processes: p.join()

    # Release all used sockets.
    for s in self._backends: s.close()
    for s in self._frontends: s.close()
    self._sync.close()

    # Destroy ZeroMQ context.
    self._ctx.term()
