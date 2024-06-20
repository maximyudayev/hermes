import time

from IMUStreamer import DotManager
import threading


def record_from_dots(imu_manager):
    print("starting IMU manager")
    imu_manager.init_sensors()
    imu_manager.sensor_sync()
    imu_manager.start_streaming()


def recording_consumer(imu_manager):
    print("Starting IMU consumer")
    start_time = time.time()
    duration = 2 * 60  # 2 minutes
    while time.time() - start_time < duration:
        res = imu_manager.pop_from_queue()
        if res is not None:
            print(res)
        else:
            time.sleep(5)


newDotManager = DotManager()

producer_thread = threading.Thread(target=record_from_dots, args=(newDotManager,))
consumer_thread = threading.Thread(target=recording_consumer, args=(newDotManager,))

producer_thread.start()
consumer_thread.start()
