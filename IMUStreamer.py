from abc import ABC, abstractmethod
import xme
import AwindaHelper as AwH
from xdpchandler import *
from time import sleep
from pynput import keyboard as pyKey
import keyboard
import queue
from datetime import datetime


class IMUManager(ABC):
    def __init__(self):
        super().__init__()
        self.buffer = queue.Queue(50000)

    def put_in_queue(self, item):
        if self.buffer.full():
            print("IMU data buffer is full, future data will be overwritten...")
            self.buffer.get()  # remove 1 item from queue
        self.buffer.put(item)

    def pop_from_queue(self):
        if self.buffer.empty():
            print("No data has been buffered currently...")
        else:
            return self.buffer.get()

    @abstractmethod
    def init_sensors(self):
        pass

    @abstractmethod
    def start_streaming(self):
        pass

    @abstractmethod
    def stop_streaming(self):
        pass


class DotPacket:
    def __init__(self, sensor_id, timestamp, arrival_time, data):
        self.sensor_id = sensor_id
        self.timestamp = timestamp
        self.arrival_time = arrival_time
        self.data = data


class DotManager(IMUManager):
    """
    Some notes: if the dots are not shutdown properly they stay in sync mode (2 fast green blinks)
    which messes up the timing when rerun. Fix is to rerun and quit a recording with "q".
    To guarantee heading accuracy and, therefore, to avoid drift in orientation data, the
    sensors must be kept still at the beginning of the measurement for 2-3 seconds.
    """
    def __init__(self):
        super().__init__()
        self.xdpcHandler = XdpcHandler()
        if not self.xdpcHandler.initialize():
            self.xdpcHandler.cleanup()
            exit(-1)

    def start_streaming(self):
        # Start live data output. Make sure root node is last to go to measurement.
        print("Putting devices into measurement mode.")
        for device in self.xdpcHandler.connectedDots():
            if not device.startMeasurement(movelladot_pc_sdk.XsPayloadMode_ExtendedEuler):
                print(f"Could not put device into measurement mode. Reason: {device.lastResultText()}")
                continue

        print("Resetting device headings")
        for device in self.xdpcHandler.connectedDots():
            print(f"\nResetting heading for device {device.portInfo().bluetoothAddress()}: ", end="", flush=True)
            if device.resetOrientation(movelladot_pc_sdk.XRM_Heading):
                print("OK", end="", flush=True)
            else:
                print(f"NOK: {device.lastResultText()}", end="", flush=True)
        print("\n", end="", flush=True)

        record_time = 1200

        print(f"\nMain loop. Recording data for {record_time} seconds. Quit recording by pressing 'Q'.")
        print("-----------------------------------------")

        # First printing some headers, so we see which data belongs to which device
        ''''s = ""
        for device in self.xdpcHandler.connectedDots():
            s += f"{device.portInfo().bluetoothAddress():27}"
        print("%s" % s, flush=True)'''

        startTime = movelladot_pc_sdk.XsTimeStamp_nowMs()
        while movelladot_pc_sdk.XsTimeStamp_nowMs() - startTime <= 1000 * record_time:
            if keyboard.is_pressed('q'):
                print('Q pressed, exiting recording loop...')
                self.stop_streaming()
                return

            if self.xdpcHandler.packetsAvailable():
                for device in self.xdpcHandler.connectedDots():
                    # Retrieve a packet
                    packet = self.xdpcHandler.getNextPacket(device.portInfo().bluetoothAddress())
                    if packet.containsOrientation():
                        euler = packet.orientationEuler()
                        self.put_in_queue(DotPacket(device.bluetoothAddress(), packet.sampleTimeFine(), datetime.now(), (euler.x(), euler.y(), euler.z(), euler.pitch(), euler.yaw(), euler.roll())))

                #print("%s" % s, flush=True)
        self.stop_streaming()

    def stop_streaming(self):
        print("\n-----------------------------------------", end="", flush=True)

        print("\nStopping measurement...")
        for device in self.xdpcHandler.connectedDots():
            if not device.stopMeasurement():
                print("Failed to stop measurement.")

        print("Stopping sync...")
        if not self.manager.stopSync():
            print("Failed to stop sync.")

        print("Closing ports...")
        self.manager.close()

        print("Successful exit.")

    def init_sensors(self):
        output_rate = 20
        self.xdpcHandler.scanForDots()
        if len(self.xdpcHandler.detectedDots()) == 0:
            print("No Movella DOT device(s) found. Aborting.")
            self.xdpcHandler.cleanup()
            exit(-1)

        self.xdpcHandler.connectDots()

        if len(self.xdpcHandler.connectedDots()) == 0:
            print("Could not connect to any Movella DOT device(s). Aborting.")
            self.xdpcHandler.cleanup()
            exit(-1)

        for device in self.xdpcHandler.connectedDots():
            # Make sure all connected devices have the same filter profile and output rate
            if device.setOnboardFilterProfile("General"):
                print("Successfully set profile to General")
            else:
                print("Setting filter profile failed!")

            if device.setOutputRate(output_rate):
                print(f"Successfully set output rate to {output_rate} Hz")
            else:
                print("Setting output rate failed!")

        self.manager = self.xdpcHandler.manager()
        self.deviceList = self.xdpcHandler.connectedDots()

    def sensor_sync(self):
        if len(self.deviceList) == 1:
            print("Only 1 device connected, sync not needed...")
        else:
            print(f"\nStarting sync for connected devices... Root node: {self.deviceList[-1].bluetoothAddress()}")
            print("This takes at least 14 seconds")
            if not self.manager.startSync(self.deviceList[-1].bluetoothAddress()):
                print(f"Could not start sync. Reason: {self.manager.lastResultText()}")
                if self.manager.lastResult() != movelladot_pc_sdk.XRV_SYNC_COULD_NOT_START:
                    print("Sync could not be started. Aborting.")
                    self.xdpcHandler.cleanup()
                    exit(-1)

                # If (some) devices are already in sync mode.Disable sync on all devices first.
                self.manager.stopSync()
                print(f"Retrying start sync after stopping sync")
                if not self.manager.startSync(self.deviceList[-1].bluetoothAddress()):
                    print(f"Could not start sync. Reason: {self.manager.lastResultText()}. Aborting.")
                    self.xdpcHandler.cleanup()
                    exit(-1)


class AwindaManager(IMUManager):
    def __init__(self):
        super().__init__()
        self.license = xme.XmeLicense()
        self.awindaChannel = 15
        self.mvnFileName = 'mvn_outfile.mvn'
        self.xmeControl = xme.XmeControl()
        self.cb = AwH.MyXmeCallbacks(self.xmeControl)
        self.xmeControl.addCallbackHandler(self.cb)

        self.version = self.xmeControl.version()
        print("XmeControl construction successful, XME version %s.%s.%s " % (
            self.version.major(), self.version.minor(), self.version.revision()))

        print("Using channel", self.awindaChannel, "for Awinda communication")
        print("Using file", self.mvnFileName, "for recording")

        self.xmeControl.setLogAllLiveData(r"C:\Users\u0166698\PycharmProjects\ExoSensorStream\Streamers\mvnLiveData")

    def init_sensors(self):
        self.xmeControl.setConfiguration("LowerBody")

        print("Starting scan (press q to quit)")
        self.xmeControl.setScanMode(True)
        self.xmeControl.setRealTimePoseMode(True)
        while not self.xmeControl.status().isConnected():
            with pyKey.Events() as events:
                # Block at most one second
                event = events.get(1)
                if event is not None and event.key == pyKey.Events.Press(pyKey.KeyCode.from_char("q")).key:
                    print('Exiting program...')
                    AwH.exitClean(0, self.xmeControl)
                else:
                    pass

        self.xmeControl.setRealTimePoseMode(False)
        self.xmeControl.setScanMode(False)

        self.xmeControl.setBodyDimension("bodyHeight", 1.78)  # todo make this use input()
        self.xmeControl.setBodyDimension("footSize", 0.32)

        while not self.cb.calibrationComplete:
            event = events.get(1)
            if event is not None and event.key == pyKey.Events.Press(pyKey.KeyCode.from_char("q")).key:
                print('Exiting program...')
                AwH.exitClean(0, self.xmeControl)
            else:
                pass

        AwH.performCalibration(self.xmeControl, self.cb, "Npose")
        AwH.displayCalibrationResults(self.xmeControl.calibrationResult("Npose"))

        while not self.cb.calibrationComplete:
            event = events.get(1)
            if event is not None and event.key == pyKey.Events.Press(pyKey.KeyCode.from_char("q")).key:
                print('Exiting program...')
                AwH.exitClean(0, self.xmeControl)
            else:
                pass

    def start_streaming(self):
        go = input("Press <Enter> to start recording")

        self.xmeControl.createMvnFile(self.mvnFileName)
        self.xmeControl.startRecording()

        # Wait until it starts recording, so we can start the countdown.
        while not self.cb.recordingStarted:
            sleep(0.01)

        # Record for 10 seconds
        seconds = 10
        while seconds > 0:
            print("Recording for another %d seconds" % seconds)
            sleep(1)
            seconds -= 1

        self.xmeControl.stopRecording()
        while self.xmeControl.status().isRecordingOrFlushing():
            sleep(0.01)

        self.xmeControl.saveAndCloseFile()
        self.xmeControl.disconnectHardware()

        AwH.exitClean(0, self.xmeControl)

    def stop_streaming(self):
        pass
