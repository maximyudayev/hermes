from multiprocessing import Process, set_start_method

import zmq

from utils.time_utils import *
from utils.dict_utils import *
from utils.print_utils import *

from streamers.SensorStreamer import SensorStreamer
from streamers import STREAMERS
from workers import WORKERS
from workers.Worker import Worker

from streamers import STREAMERS
from workers import WORKERS
from workers.Worker import Worker

from streamers import STREAMERS
from workers import WORKERS
from workers.Worker import Worker

################################################
################################################
# PUB-SUB Broker to manage a collection of SensorStreamer objects.
# Hosts control logic of interactive proxy/server.
# Will launch/destroy/connect to streamers on creation and ad-hoc.
# Will use a separate process for each streamer and consumer.
# Will use the main process to:
#   * route PUB-SUB messages
#   * TODO: measure and publish per-sensor network delays
#   * TODO: subscribe to stdin/stdout messages of all publishers and subscribers
#   * TODO: process REQ-REP transactions
# Each SensorStreamer connects only to its local broker,
#   which then exposes its data to outside LAN subscribers.
################################################
################################################
class StreamBroker:
  _log_source_tag = 'manager'

  ########################
  ###### INITIALIZE ######
  ########################

  def __init__(self, 
               ip: str,
               streamer_specs: list[dict] | tuple[dict] = None,
               worker_specs: list[dict] | tuple[dict] = None,
               port_backend: str = "42069", 
               port_frontend: str = "42070", 
               port_sync: str = "42071",
               port_killsig: str = "42066",
               print_status: bool = True, 
               print_debug: bool = False) -> None:

    # Record various configuration options.
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
    self._sync: zmq.SyncSocket = self._ctx.socket(zmq.ROUTER)
    self._sync.bind("tcp://%s:%s" % (self._ip, self._port_sync))

    # Termination control socket to command publishers and subscribers to finish and exit.
    killsig_pub: zmq.SyncSocket = self._ctx.socket(zmq.PUB)
    killsig_pub.bind("tcp://*:%s" % (self._port_killsig))
    self._killsigs: list[zmq.SyncSocket] = [killsig_pub]

    # Poll object to listen to sockets without blocking
    self._poller: zmq.Poller = zmq.Poller()

    # Instantiate each desired local streamer.
    # Use ZeroMQ sockets to transfer collected data to other processes.
    self._streamers: list[SensorStreamer] = []
    if streamer_specs is not None:
      for streamer_spec in streamer_specs:
        class_name: str = streamer_spec['class']
        class_args = streamer_spec.copy()
        del(class_args['class'])
        class_args['port_pub'] = self._port_backend      
        class_args['port_sync'] = self._port_sync
        class_args['port_killsig'] = self._port_killsig
        # Create the class object.
        class_type: type[SensorStreamer] = STREAMERS[class_name]
        class_object: SensorStreamer = class_type(**class_args)
        # Store the streamer object.
        self._streamers.append(class_object)

    # Create all desired consumers and connect them to the PUB broker socket.
    self._workers: list[Worker] = []
    if worker_specs is not None:
      for worker_spec in worker_specs:
        class_name: str = worker_spec['class']
        class_args = worker_spec.copy()
        del(class_args['class'])
        class_args['port_sub'] = self._port_frontend
        class_args['port_sync'] = self._port_sync
        class_args['port_killsig'] = self._port_killsig
        # Create the class object.
        class_type: type[Worker] = WORKERS[class_name]
        class_object: Worker = class_type(**class_args)
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
    killsig_sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    killsig_sub.connect("tcp://%s:%s" % (addr, port_killsig))
    killsig_sub.subscribe('kill')
    self._poller.register(killsig_sub, zmq.POLLIN)
    self._killsigs.append(killsig_sub)

  # Register PUB-SUB sockets on both interfaces for polling.
  def register_pubsub_for_poll(self) -> None:
    for s in self._backends: self._poller.register(s, zmq.POLLIN)
    for s in self._frontends: self._poller.register(s, zmq.POLLIN)


  #####################
  ###### RUNNING ######
  #####################
  def start(self):
    # Make sure that the child processes are spawned and not forked.
    set_start_method('spawn')

    # Start each publisher-subscriber in its own process (e.g. local sensors, data logger, visualizer, AI worker).
    nodes = [*self._streamers, *self._workers]
    self._processes: list[Process] = [Process(target=node) for node in nodes]
    for p in self._processes: 
      p.start()

  # The main run method.
  #   Runs continuously until the user ends the experiment or after the specified duration.
  # TODO (1): measure network delay to each locally connected sensor on a periodic basis and publish information for the datalogger to record as well
  # TODO (3): check connection between Proxies has been established before starting subscribers?
  # TODO (3): verify subscribers subscribed to desired topics and publishers are ready to send non-dummy data?
  def run(self, duration_s: int = None) -> None:
    # Configure running condition
    start_time_s: float = time.time()
    condition_fn = (lambda: (time.time() - start_time_s) > duration_s) if not not duration_s else lambda: True

    try:
      # Synchronize all the components of the system, start external recording in DataLogger through common interface
      # num_expected_connections: int = len(self._streamers) + len(self._workers) + (len(self._backends)-1)
      # count = 0
      # addresses = []
      # while count < num_expected_connections:
      #   address, _, msg = self._sync.recv_multipart()
      #   addresses.append(address)
      #   print("%s connected to broker" % msg, flush=True)
      #   count += 1
      # for address in addresses:
      #   self._sync.send_multipart([address, b'', b'GO'])

      # Run until main loop condition reaches the end.
      # TODO (2): wrap into an FSM for cleanliness and readability.
      self.register_pubsub_for_poll()
      while condition_fn():
        poll_res: tuple[list[zmq.SyncSocket], list[int]] = tuple(zip(*(self._poller.poll())))
        for socket in poll_res[0]:
          ############################
          ###### PUB-SUB Broker ######
          ############################
          # Forwards data packets from publishers to subscribers. 
          if socket in self._backends:
            msg = socket.recv_multipart()
            for s in self._frontends: s.send_multipart(msg)
          # Forwards subscription packets from subscribers to publishers.
          if socket in self._frontends:
            msg = socket.recv_multipart()
            for s in self._backends: s.send_multipart(msg)

          ##################################
          ###### REQ-REP Transactions ######
          ##################################
          # TODO (3):

          ##################
          ###### KILL ######
          ##################
          # Receives KILL signal from another broker (e.g. lab PC in AidFOG project).
          # TODO: enter own sublogic that brokers until the end frame of each sensor and then exits too.
          if socket in self._killsigs:
            # Ignore any more KILL signals, enter the wrap-up routine.
            self._poller.unregister(self._killsigs[1])
            # Send kill signals to own locally connected devices.
            self._killsigs[0].send(b'kill')
    
    except KeyboardInterrupt:
      # Exit gracefully when user clicks 'end' in GUI or Ctrl+C, or when time runs out.
      pass
    finally:
      # Send termination signal over dedicated socket to all processes to wrap up.
      self._killsigs[0].send(b'kill')
      print("quitting broker", flush=True)
      # Wait for all processes (local and remote) to send the last messages before closing.
      #   Continue brokering packets until signalled by all publishers that there will be no more packets.
      #   Append a frame to the ZeroMQ message that indicates the last message from the sensor.

      # Wait for each publisher to finish sending and acknowledge end of stream command.
      self.stop()


  # Stop each component of the system before exiting the program.
  def stop(self) -> None:
    # Wait for all the local subprocesses to gracefully exit before terminating the main process.
    for p in self._processes: p.join()

    # Release all used sockets.
    for s in self._backends: s.close()
    for s in self._frontends: s.close()
    for s in self._killsigs: s.close()
    self._sync.close()

    # Destroy ZeroMQ context.
    self._ctx.term()


class publisher():
  def __init__(self,
               ip,
               port_backend,
               port_killsig,
               port_sync):
    self.ip = ip
    self.port_backend = port_backend
    self.port_killsig = port_killsig
    self.port_sync = port_sync

  def __call__(self):
    self.ctx = zmq.Context.instance()
    self.pub: zmq.SyncSocket = self.ctx.socket(zmq.PUB)
    self.pub.connect("tcp://%s:%s" % (self.ip, self.port_backend))

    self.killsig: zmq.SyncSocket = self.ctx.socket(zmq.SUB)
    self.killsig.connect("tcp://%s:%s" % (self.ip, self.port_killsig))
    self.killsig.subscribe("kill")

    self.poller: zmq.Poller = zmq.Poller()
    self.poller.register(self.killsig, zmq.POLLIN)
    self.poller.register(self.pub, zmq.POLLOUT)

    self.sync: zmq.SyncSocket = self.ctx.socket(zmq.REQ)
    self.sync.connect("tcp://%s:%s" % (self.ip, self.port_sync))

    # time.sleep(5.0)

    # self.sync.send_multipart([b'',b'PUB'])
    # self.sync.recv()

    msg_id: int = 0
    _running = True
    while _running:
      poll_res: tuple[list[zmq.SyncSocket], list[int]] = tuple(zip(*(self.poller.poll())))
      if self.pub in poll_res[0]:
        self.pub.send_multipart([b'PUB', bytes(str(msg_id), 'utf-8')])
        print("Sent #%d"%msg_id, flush=True)
        msg_id += 1
      if self.killsig in poll_res[0]:
        self.killsig.recv_multipart()
        self.poller.unregister(self.killsig)
        _running = False
        print("quitting publisher", flush=True)

    self.sync.close()
    self.pub.close()
    self.ctx.term()

# Emulation of subscriber
class subscriber():
  def __init__(self,
               ip,
               port_frontend,
               port_killsig,
               port_sync):
    self.ip = ip
    self.port_frontend = port_frontend
    self.port_killsig = port_killsig
    self.port_sync = port_sync

  def __call__(self):
    self.ctx = zmq.Context.instance()
    self.sub: zmq.SyncSocket = self.ctx.socket(zmq.SUB)
    self.sub.connect("tcp://%s:%s" % (ip, port_frontend))
    self.sub.subscribe("PUB")

    self.killsig: zmq.SyncSocket = self.ctx.socket(zmq.SUB)
    self.killsig.connect("tcp://%s:%s" % (self.ip, self.port_killsig))
    self.killsig.subscribe("kill")

    self.poller: zmq.Poller = zmq.Poller()
    self.poller.register(self.sub, zmq.POLLIN)
    self.poller.register(self.killsig, zmq.POLLIN)

    self.sync: zmq.SyncSocket = self.ctx.socket(zmq.REQ)
    self.sync.connect("tcp://%s:%s" % (self.ip, self.port_sync))

    # time.sleep(8.0)

    # self.sync.send_multipart([b'',b'SUB'])
    # self.sync.recv()

    _running = True
    while _running:
      poll_res: tuple[list[zmq.SyncSocket], list[int]] = tuple(zip(*(self.poller.poll())))
      if self.sub in poll_res[0]:
        msg: tuple[str, bytes] = self.sub.recv_multipart()
        print("Received #%d"% int(msg[1].decode('utf-8')), flush=True)
      if self.killsig in poll_res[0]:
        self.killsig.recv_multipart()
        self.poller.unregister(self.killsig)
        _running = False
        print("quitting publisher", flush=True)

    self.sync.close()
    self.sub.close()
    self.ctx.term()

#####################
###### TESTING ######
#####################
if __name__ == "__main__":
  ip = "127.0.0.1"
  port_backend = "42069"
  port_frontend = "42070"
  port_sync = "42071"
  port_killsig = "42066"

  # Test launcher
  stream_broker: StreamBroker = StreamBroker(ip=ip)
  
  # set_start_method('spawn')
  # Hacking an emulation of workers and sensors
  processes: list[Process] = [Process(target=node) for node in [publisher(ip, port_backend, port_killsig, port_sync), subscriber(ip, port_frontend, port_killsig, port_sync)]]
  for p in processes: 
    p.start()

  stream_broker.start()
  stream_broker.run(duration_s=None)

  for p in processes: p.join()
