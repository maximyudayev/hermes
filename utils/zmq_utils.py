# ZeroMQ topics and message strings
TOPIC_KILL  = 'KILL'
CMD_GO      = 'GO'
CMD_END     = 'END'
CMD_BYE     = 'BYE'
MSG_ON      = 'ON'
MSG_OFF     = 'OFF'
MSG_OK      = 'OK'

# Ports used for ZeroMQ by our system
PORT_BACKEND    = '42069'
PORT_FRONTEND   = '42070'
PORT_SYNC       = '42071'
PORT_KILL       = '42066'
PORT_KILL_BTN   = '42065'
PORT_PAUSE      = '42067'

# Ports of connected devices/sensors
PORT_MOTICON      = '8888' # defined by the Moticon desktop app, putting data at the loopback address for listening
PORT_PROSTHESIS   = '51702' # defined by LabView code of VUB
PORT_GUI          = '8005'
PORT_EYE          = '50020'
PORT_VICON        = '801'

# IP addresses of devices on the network used by our system
DNS_LOCALHOST   = 'localhost'
IP_LOOPBACK     = '127.0.0.1'
IP_STATION      = '192.168.0.100'
IP_PROSTHESIS   = '192.168.0.101'
IP_BACKPACK     = '192.168.0.103'
