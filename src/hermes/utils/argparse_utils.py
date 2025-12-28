############
#
# Copyright (c) 2024-2026 Maxim Yudayev and KU Leuven eMedia Lab
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

import argparse


def validate_ip4(s: str) -> str:
    """Validates whether parsed value is a valid IPv4 address.

    Args:
        s (str): Parsed text value to test for validity as IPv4 address.

    Returns:
        str: Unchanged text value to use as IP address.

    Raises:
        argparse.ArgumentTypeError: If the parsed value is not a valid IPv4 address.
    """
    try:
        a = s.split(".")
        assert len(a) == 4
        for x in a:
            assert x.isdigit()
            n = int(x)
            assert n >= 0 and n <= 255
        return s
    except:
        raise argparse.ArgumentTypeError("Not a valid IPv4 address: ", s)


def validate_path(s: str) -> str:
    """Validates whether parsed file path exists.

    Args:
        s (str): File path to parse.

    Returns:
        str: Unchanged path if it exists.

    Raises:
        argparse.ArgumentTypeError: If the provided path does not exist.
    """
    try:
        return s
    except:
        raise argparse.ArgumentTypeError("Invalid path to config file: ", s)


def parse_type(s: str) -> int | float | bool | str:
    """Parsing utility to convert data types to native Python objects.
    
    Args:
        s (str): Text to convert to the corresponding data type.

    Returns:
        int | float | bool | str: Parsed primitive data type. 
    """
    if s.isdigit():
        return int(s)
    elif s == "True":
        return True
    elif s == "False":
        return False
    else:
        try:
            return float(s)
        except:
            return s


class ParseExperimentKwargs(argparse.Action):
    """Parsing object for experiment details specification."""
    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, (list, tuple)):
            setattr(namespace, self.dest, dict())
            for value in values:
                key, value = value.split("=")
                getattr(namespace, self.dest)[key] = value


class ParseStorageKwargs(argparse.Action):
    """Parsing object for `Storage` specification."""
    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, (list, tuple)):
            setattr(namespace, self.dest, dict())
            for value in values:
                if "=" in value:
                    key, val = value.split("=")
                    getattr(namespace, self.dest)[key] = parse_type(val)
                else:
                    getattr(namespace, self.dest)[value] = True


class ParseNodeKwargs(argparse.Action):
    """Parsing object for `Node` specifications."""
    def __call__(self, parser, namespace, values, option_string=None):
        if isinstance(values, (list, tuple)):
            new_items = list()
            # Parse the input values as a dictionary
            id = -1
            for value in values:
                key, val = value.split("=")
                if key == "class":
                    id += 1
                    new_items.append(dict([(key, val)]))
                elif ";" in val:
                    new_items[id][key] = dict()
                    for pair_str in val.split(";"):
                        k, v = pair_str.split(":")
                        new_items[id][key][k] = v
                elif "," in val:
                    new_items[id][key] = list(map(parse_type, val.split(",")))
                else:
                    new_items[id][key] = parse_type(val)
            # Extend the list with the new dictionary
            items = getattr(namespace, self.dest, list())
            items.extend(new_items)
            setattr(namespace, self.dest, items)
