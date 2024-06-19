# Create the callbacks
import xme
from time import sleep

awindaChannel = 15


class MyXmeCallbacks(xme.XmeCallback):
    def __init__(self, xme_ctrl):
        super(MyXmeCallbacks, self).__init__()
        self.calibrationAborted = False
        self.calibrationComplete = False
        self.calibrationProcessed = False
        self.recordingStarted = False
        self.xmeControl = xme_ctrl

    def onBufferOverflow(self, dev):
        print("WARNING! Data buffer overflow. Your PC can't keep up with the incoming data. Buy a better PC.")

    def onPoseReady(self, dev):
        print(f"testing this callback {dev}")

    def onCalibrationAborted(self, dev):
        print("Calibration aborted")
        self.calibrationAborted = True

    def onCalibrationComplete(self, dev):
        print("Calibration completed")
        self.calibrationComplete = True

    def onCalibrationProcessed(self, dev):
        print("Calibration processed")
        self.calibrationProcessed = True

    def onConfigurationChangeComplete(self, dev):
        print("Configuration is successfully changed")

    def onConfigurationChangeFailed(self, dev):
        print("Configuration change is failed!")

    def onHardwareDisconnected(self, dev):
        print("Hardware disconnected")

    def onLiveDataAvailable(self, dev):
        print("Live data is available, this message is a test that this callback is called.")

    def onHardwareError(self, dev):
        xmeStatus = self.xmeControl.status()  # important to get a copy!
        suitStatus = xmeStatus.suitStatus()
        hardwareStatus = suitStatus.m_hardwareStatus

        if suitStatus.m_masterDevice.m_deviceId.isAwindaX() and suitStatus.m_wirelessChannel != awindaChannel:
            print("Setting radio channel of", suitStatus.m_masterDevice.m_deviceId, "to", awindaChannel, flush=True)
            dev.setRadioChannel(suitStatus.m_masterDevice.m_deviceId, awindaChannel)

        if hardwareStatus == xme.XHS_HardwareOk:
            print("The suit is configured correctly")

        elif hardwareStatus == xme.XHS_Error:
            print("An error occurred during initialization: %s" % suitStatus.m_hardwareStatusText)
            print("Device ID=%d" % suitStatus.m_lastProblematicDeviceId)

        elif hardwareStatus == xme.XHS_NothingFound:
            print('.', end='', flush=True)

        elif hardwareStatus == xme.XHS_MissingSensor:
            print("Master id:", suitStatus.m_masterDevice.m_deviceId)
            print("At least one usable Motion Tracker is missing")
            missingSensors = suitStatus.m_missingSensors
            print("%u missing locations:" % len(missingSensors))
            for missingSensor in missingSensors:
                print(" %d(%s)" % (missingSensor, self.xmeControl.segmentName(missingSensor)))

            # Check for duplicates
            duplicates = xme.XsIntArray()
            duplicatesIds = xme.XsDeviceIdArray()
            for index in range(len(suitStatus.m_sensors)):
                if suitStatus.m_sensors[index].m_validity == xme.XDV_Duplicate:
                    duplicates.push_back(suitStatus.m_sensors[index].m_segmentId)
                    duplicatesIds.push_back(suitStatus.m_sensors[index].m_deviceId)
            if len(duplicates):
                print("%d duplicate locations:" % len(duplicates))
                for index in range(len(duplicates)):
                    print(" [%s-%d(%s)]"
                          % (duplicatesIds[index], duplicates[index], self.xmeControl.segmentName(duplicates[index])))

        elif hardwareStatus == xme.XHS_ObrMode:
            print("The system is configured for On Body Recording mode, preventing it from being initialized")

        elif hardwareStatus == xme.XHS_Invalid:
            print("Some invalid hardware was detected or the status is uninitialized")

        else:
            print("The system is in unknown state")

    def onHardwareReady(self, dev):
        print("\nHardware is ready")

    def onLowBatteryLevel(self, dev):
        xmeStatus = self.xmeControl.status()  # important to get a copy!
        sensors = xmeStatus.suitStatus().m_sensors
        skipBatteryWarning = False
        for sensor in sensors:
            if ((sensor.m_batteryLevel == 0) or (sensor.m_batteryLevel == -1)):
                skipBatteryWarning = True
        if not (skipBatteryWarning):
            print("Attention! Low battery level!")

    def onRecordingStateChanged(self, dev, newState):
        if newState == xme.XRS_NotRecording:
            print("Recording stopped")
            self.recordingStarted = False
        elif newState == xme.XRS_WaitingForStart:
            print("Waiting for recording to start")
        elif newState == xme.XRS_Recording:
            print("Recording started")
            self.recordingStarted = True
        elif newState == xme.XRS_Flushing:
            print("Flushing data, receiving retransmissions")
        else:
            print("Unknown recording state")

    def onHardwareWarning(self, dev, resultValue, additionalMessage):
        print("Hardware warning! Result value number %d, additional message: %s" % (resultValue, additionalMessage))

    def onProgressUpdate(self, dev, percentage, category):
        print("Progress update in category %s: %d" % (category, percentage))

    def onProcessingProgress(this, dev, stage, firstFrame, lastFrame):
        print("Processing pgress update: stage %d, %d --> %d" % (stage, firstFrame, lastFrame))


def performCalibration(xmeControl, cb, calibrationType=""):
    xmeControl.initializeCalibration(calibrationType)
    cb.calibrationProcessed = False
    cb.calibrationAborted = False
    cb.calibrationComplete = False

    times = xmeControl.calibrationRecordingTimesRemaining()
    if not times:
        raise RuntimeError("Nothing to calibrate")
    stages = len(times)

    print("Instructions: ")
    print("* Please stand still in", calibrationType, "for", times[0] / 1000, "seconds")
    if stages > 1:
        print("* Please move around for", times[1] / 1000, "seconds")
        if stages > 2:
            for i in range(2, stages):
                print("* Unknown for", times[i] / 1000, "seconds")  # not defined at this time

    go = input("Press <Enter> to start %s calibration" % calibrationType)
    xmeControl.startCalibration()

    # Wait until it starts recording, so we can start the countdown.
    while not cb.recordingStarted:
        sleep(0.01)

    recordingStatic = True
    while len(times) > 0:
        if recordingStatic:
            if cb.calibrationProcessed:
                # done with static part, recording dynamic part
                recordingStatic = False
            else:
                if len(times) < stages:
                    # done recording but waiting for processing to complete, remain standing still until the results have been applied
                    print("Please stand still in", calibrationType)
                else:
                    # recording
                    print("Please stand still in", calibrationType, "for", (times[0] / 1000.0), "more seconds")
        if not recordingStatic:
            # recording dynamic part
            print("Please move around for", (times[0] / 1000.0), "more seconds")
        sleep(0.2)
        times = xmeControl.calibrationRecordingTimesRemaining()

    print("Processing...")
    while not cb.calibrationComplete and not cb.calibrationAborted:
        sleep(0.01)

    print("Done with calibration...")


def displayCalibrationResults(calibrationResult=xme.XmeCalibrationResult()):
    quality = calibrationResult.m_quality
    qualityString = ""

    if quality == xme.XCalQ_Good:
        qualityString = "good"
    elif quality == xme.XCalQ_Acceptable:
        qualityString = "acceptable"
    elif quality == xme.XCalQ_Poor:
        qualityString = "poor"
    elif quality == xme.XCalQ_Failed:
        qualityString = "failed"
    elif quality == xme.XCalQ_Unknown:
        qualityString = "unknown"

    print("Calibration result: %s" % qualityString)

    warnings = calibrationResult.m_warnings
    if len(warnings) != 0:
        print("Received warnings: ")
        for warning in warnings:
            print(warning)


def exitClean(rv, xmeControl):
    if xmeControl:
        xmeControl.setScanMode(False)
        sleep(0.1)
    xme.xmeTerminate()
    exit(rv)
