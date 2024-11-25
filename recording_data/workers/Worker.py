from abc import ABC, abstractmethod
import copy

import zmq

from streamers import STREAMERS


class Worker(ABC):
  # Read-only property that every subclass must implement.
  @property
  @abstractmethod
  def _log_source_tag(self):
    pass

  def __init__(self,
               classes: list[str] = [],
               port_sub: str = "42070",
               port_sync: str = "42071",
               port_killsig: str = "42066") -> None:
    self._classes = classes
    self._port_sub = port_sub
    self._port_sync = port_sync
    self._port_killsig = port_killsig
    self._poller: zmq.Poller = zmq.Poller()

  # A worker instance is a callable to launch as a Process
  def __call__(self, *args, **kwds):
    # Connect local subscriber to the Broker's XPUB socket
    self._ctx: zmq.Context = zmq.Context.instance()

    # Socket to subscribe to SensorStreamers
    self._sub: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    self._sub.connect("tcp://localhost:%s" % self._port_sub)
    
    for class_type in self._classes:
      # Subscribe to topics for each mentioned local and remote streamer
      self._sub.subscribe(STREAMERS[class_type]._log_source_tag)

    # Socket to receive kill signal
    self._killsig: zmq.SyncSocket = self._ctx.socket(zmq.SUB)
    self._killsig.connect("tcp://localhost:%s" % self._port_killsig)
    topics = ["kill"]
    for topic in topics: self._killsig.subscribe(topic)

    # Socket to indicate to broker that the subscriber is ready
    self._sync: zmq.SyncSocket = self._ctx.socket(zmq.REQ)
    self._sync.connect("tcp://localhost:%s" % self._port_sync)

    # Start running!
    self.run()

  @abstractmethod
  def run(self):
    self._poller.register(self._sub, zmq.POLLIN)
    self._poller.register(self._killsig, zmq.POLLIN)

  @abstractmethod
  def quit(self):
    self._sub.close()
    self._killsig.close()
    self._sync.close()
    # Destroy ZeroMQ context.
    self._ctx.term()
