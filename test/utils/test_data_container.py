import numpy as np

from hermes.base.data_container import DataContainer
from hermes.utils.types import VideoFormatEnum, DataBundleInfo, SharedMemoryCircularBufferMetadata


class MockVideoContainer(DataContainer):
    def __init__(self):
        super().__init__()
        # Adding video channel
        self.add_channel(
            bundle_name="camera_bundle",
            channel_name="frame",
            data_type="uint8",
            sample_size=[1],
            buf_len=100,  # 100 bytes buffer
            index_len=5,   # 5 frames index
            is_video=True,
            color_format=VideoFormatEnum.MJPEG
        )
        # Adding metadata channels
        self.add_channel(
            bundle_name="camera_bundle",
            channel_name="toa_s",
            data_type="float64",
            sample_size=[1],
            buf_len=5
        )

def test_container():
    print("Initializing MockVideoContainer...")
    container = MockVideoContainer()

    # Get metadata lock etc.
    bundle_info = container.get_info_all()["camera_bundle"]
    
    # We must manually initialize some synchronized pointers on metadata since they are normally managed by Node/multiprocessing
    # Let's check how metadata is structured in types.py or shared_memory.py
    print("Metadata fields:")
    for field in dir(bundle_info.metadata):
        if not field.startswith("_"):
            print(f"  {field}: {getattr(bundle_info.metadata, field)}")

    try:
        # Push 1st frame
        frame = np.array([[10, 20, 30, 40]], dtype=np.uint8)
        toa = np.array([[123.456]], dtype=np.float64)
        
        data = {
            "frame": frame,
            "toa_s": toa
        }
        
        print("Pushing frame...")
        container.push(process_time_s=123.456, data={"camera_bundle": data})
        
        # Let's try popping
        print("Popping frame...")
        popped = list(container.pop("camera_bundle"))
        print("Popped data:")
        for channel_name, view in popped:
            print(f"  {channel_name}: {view}")
            if channel_name == "frame":
                assert np.array_equal(view, frame)
            elif channel_name == "toa_s":
                assert view[0] == 123.456

        print("DataContainer integration test passed successfully!")

    finally:
        container.unlink_all()

if __name__ == "__main__":
    test_container()
