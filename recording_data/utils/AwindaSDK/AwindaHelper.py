# Create the callbacks
from collections import defaultdict, deque

#import xme
import queue
from time import sleep
from threading import Lock
import time

awindaChannel = 15

def find_closest_update_rate(supported_update_rates, desired_update_rate):
    if not supported_update_rates:
        return 0

    if len(supported_update_rates) == 1:
        return supported_update_rates[0]

    closest_update_rate = min(supported_update_rates, key=lambda x: abs(x - desired_update_rate))
    return closest_update_rate



# Create the callbacks
from collections import deque

#import xme
from time import sleep
import xsensdeviceapi as xda
from threading import Lock

awindaChannel = 15

def find_closest_update_rate(supported_update_rates, desired_update_rate):
    if not supported_update_rates:
        return 0

    if len(supported_update_rates) == 1:
        return supported_update_rates[0]

    closest_update_rate = min(supported_update_rates, key=lambda x: abs(x - desired_update_rate))
    return closest_update_rate

class CustomPacket():

    def __init__(self, counter, timestamp, acceleration, rotation):
        self.counter = counter
        self.timestamp = timestamp
        self.acceleration = acceleration
        self.rotation = rotation

class MtwCallback(xda.XsCallback):
    def __init__(self, mtwIndex, device):
        super().__init__()
        self.m_packetBuffer = queue.Queue()
        self.m_mutex = Lock()
        self.m_mtwIndex = mtwIndex
        self.m_device = device

    def dataAvailable(self):
        with self.m_mutex:
            return bool(self.m_packetBuffer)

    def getOldestPacket(self):
        with self.m_mutex:
            packet = self.m_packetBuffer.get()
            return packet

    def deleteOldestPacket(self):
        with self.m_mutex:
            self.m_packetBuffer.get()

    def getMtwIndex(self):
        with self.m_mutex:
            return self.m_mtwIndex

    def device(self):
        with self.m_mutex:
            return self.m_device

    def onLiveDataAvailable(self, _, packet):
        #time.sleep(0.001)
        self.m_packetBuffer.put(CustomPacket(packet.packetCounter(), 
                                                packet.sampleTimeFine(), 
                                                [packet.calibratedAcceleration()[0], packet.calibratedAcceleration()[1], packet.calibratedAcceleration()[2]], 
                                                [packet.orientationEuler().x(), packet.orientationEuler().y(), packet.orientationEuler().z()]))

    def onConnectivityChanged(self, dev, newState):
        print(newState)

    def onError(self, dev, error):
        print(error.toString())
            



class WirelessMasterCallback(xda.XsCallback):
    def __init__(self):
        super().__init__()
        self.m_connectedMTWs = set()
        self.m_mutex = Lock()

    def getWirelessMTWs(self):
        with self.m_mutex:
            return self.m_connectedMTWs.copy()

    def onConnectivityChanged(self, dev, newState):
        with self.m_mutex:
            if newState == xda.XCS_Disconnected:
                print(f"\nEVENT: MTW Disconnected -> {dev.deviceId()}")
                self.m_connectedMTWs.discard(dev)
            elif newState == xda.XCS_Rejected:
                print(f"\nEVENT: MTW Rejected -> {dev.deviceId()}")
                self.m_connectedMTWs.discard(dev)
            elif newState == xda.XCS_PluggedIn:
                print(f"\nEVENT: MTW PluggedIn -> {dev.deviceId()}")
                self.m_connectedMTWs.discard(dev)
            elif newState == xda.XCS_Wireless:
                print(f"\nEVENT: MTW Connected -> {dev.deviceId()}")
                self.m_connectedMTWs.add(dev)
            elif newState == xda.XCS_File:
                print(f"\nEVENT: MTW File -> {dev.deviceId()}")
                self.m_connectedMTWs.discard(dev)
            elif newState == xda.XCS_Unknown:
                print(f"\nEVENT: MTW Unknown -> {dev.deviceId()}")
                self.m_connectedMTWs.discard(dev)
            else:
                print(f"\nEVENT: MTW Error -> {dev.deviceId()}")
                self.m_connectedMTWs.discard(dev)


                


