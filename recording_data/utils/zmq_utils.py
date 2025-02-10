# ZeroMQ topics and message strings
TOPIC_KILL = 'KILL'
CMD_GO = 'GO'
CMD_END = 'END'
CMD_BYE = 'BYE'

# Ports used for ZeroMQ by our system
PORT_BACKEND = '42069'
PORT_FRONTEND = '42070'
PORT_SYNC = '42071'
PORT_KILL ='42066'

# Ports of connected devices/sensors
PORT_MOTICON ='8888' # defined by the Moticon desktop app, putting data at the loopback address for listening
PORT_PROSTHESIS ='51267' # defined by LabView code of VUB

# IP addresses of devices on the network used by our system
IP_LOOPBACK = '127.0.0.1'
DNS_LOCALHOST = 'localhost'
IP_STATION = '192.168.69.100'
IP_PROSTHESIS = '192.168.69.101'
IP_BACKPACK = '192.168.69.103'
