############
#
# Copyright (c) 2024-2025 Maxim Yudayev and KU Leuven eMedia Lab
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

import msgpack
import numpy as np


def encode_ndarray(obj: object) -> object:
    """Encodes NumPy contents of the provided object into bytes.

    Args:
        obj (object): NumPy array to encode as serializeable key-value pair.

    Returns:
        object: Encoded key-value mapping with NumPy arrays serialized to bytes.
    """
    if isinstance(obj, np.ndarray):
        return {
            "__numpy__": True,
            "shape": obj.shape,
            "dtype": str(obj.dtype),
            "bytes": obj.tobytes(),
        }
    return obj


def decode_ndarray(obj: object) -> object:
    """Decodes received bytes and reconstructs detected NumPy arrays into original objects.

    Args:
        obj (object): Raw bytes to convert into NumPy arrays if any detected.

    Returns:
        object: Decoded key-value mapping with NumPy arrays reconstructed.
    """
    if "__numpy__" in obj:
        obj = np.frombuffer(obj["bytes"], dtype=obj["dtype"]).reshape(obj["shape"])
    return obj


def convert_bytes_keys_to_strings(obj: object) -> object:
    """Recursively decodes keys of the key-value mappings into strings.

    Args:
        obj (object): Object whose keys to decode.

    Returns:
        object: Processed object with keys converted into proper dictionary string fields.
    """
    if isinstance(obj, dict):
        return {
            (
                key.decode("utf-8") if isinstance(key, bytes) else key
            ): convert_bytes_keys_to_strings(value)
            for key, value in obj.items()
        }
    elif isinstance(obj, list):
        return [convert_bytes_keys_to_strings(item) for item in obj]
    else:
        return obj


def serialize(**kwargs) -> bytes:
    """Serializes a Python dict-like object for ZeroMQ transmission.

    Preserves named arguments as key-value pairs.

    Args:
        kwargs (dict): Inputs to serialize using a custom encoding hook for NumPy arrays.

    Returns:
        bytes: Serialized binary data safe to transmit.
    """
    return msgpack.packb(o=kwargs, default=encode_ndarray)  # type: ignore


def deserialize(msg: bytes) -> dict:
    """Deserializes the received message to construct the original Python object.

    Args:
        msg (bytes): Raw binary data containing the original Python object.

    Returns:
        dict: Python object with the key-value pairs preserved and any NumPy arrays reconstructed.
    """
    raw_dict = msgpack.unpackb(msg, object_hook=decode_ndarray)
    return convert_bytes_keys_to_strings(raw_dict)  # type: ignore
