from nodes import NODES
from nodes.Node import Node

def launch(spec: dict,
           port_backend: str,
           port_frontend: str,
           port_sync: str,
           port_killsig: str):
  # Create all desired consumers and connect them to the PUB broker socket.
  class_name: str = spec['class']
  class_args = spec.copy()
  del (class_args['class'])
  class_args['port_pub'] = port_backend
  class_args['port_sub'] = port_frontend
  class_args['port_sync'] = port_sync
  class_args['port_killsig'] = port_killsig
  # Create the class object.
  class_type: type[Node] = NODES[class_name]
  class_object: Node = class_type(**class_args)
  class_object()
