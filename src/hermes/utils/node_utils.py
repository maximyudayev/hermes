############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
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
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Created 2024-2025 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Maxim Yudayev [https://yudayev.com].
#
# ############

import importlib

from hermes.base.nodes.node import Node
from hermes.base.nodes.node_interface import NodeInterface


def launch_node(spec: dict):
  module_name: str = spec['package']
  class_name: str = spec['class']
  class_args: dict = spec['settings']
  node_class: type[NodeInterface] = search_node_class(module_name, class_name)
  node: Node = node_class(**class_args) # type: ignore
  node()


def search_node_class(module_name: str, class_name: str) -> type[NodeInterface]:
  module_path = "hermes.%s" % module_name

  try:
    module = importlib.import_module(module_path)
  except ImportError as e:
    raise ImportError(
      "Could not import subpackage '%s'. "
      "Ensure it is installed: pip install pysio-hermes-%s" % (module_name, module_name)
    ) from e

  if not hasattr(module, class_name):
    raise AttributeError(
      "Class '%s' not found in module '%s'. "
      "Check the spelling of the class name." % (class_name, module_name)
    )

  class_type = getattr(module, class_name)

  return class_type
