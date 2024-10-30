import msgpack
import numpy as np

def encode_ndarray(obj):
  if isinstance(obj, np.ndarray):
    return {'__numpy__': True, 
            'shape': obj.shape, 
            'dtype': str(obj.dtype), 
            'bytes': obj.tobytes()}
  return obj

def decode_ndarray(obj):
  if '__numpy__' in obj:
    obj = np.frombuffer(obj['bytes'], dtype=obj['dtype']).reshape(obj['shape'])
  return obj

# Serializes the message objects.
#   Preserves named arguments as key-value pairs for a dictionary-like message.
def serialize(**kwargs) -> bytes:
  return msgpack.packb(o=kwargs, default=encode_ndarray)

# Deserializes the message back into a dictionary-like message.
def deserialize(msg) -> dict:
  return msgpack.unpackb(msg, object_hook=decode_ndarray)
