import numpy as np

from hermes.datastructures.shared_memory import RawBytesSharedMemoryCircularBuffer


def test_circular_buffer():
    print("Initializing RawBytesSharedMemoryCircularBuffer...")
    index_len = 5
    buf_len = 20  # small buffer to force wrap-around easily
    shm_buf = RawBytesSharedMemoryCircularBuffer(
        index_len=index_len,
        buf_len=buf_len,
        sample_size=[1],
        metadata=None
    )

    try:
        # 1. Sequential Pushes
        frames = [
            np.array([1, 2, 3, 4, 5], dtype=np.uint8),      # size 5, offsets [0:5]
            np.array([6, 7, 8], dtype=np.uint8),            # size 3, offsets [5:8]
            np.array([9, 10, 11, 12], dtype=np.uint8),      # size 4, offsets [8:12]
        ]
        
        for i, frame in enumerate(frames):
            print(f"Pushing frame {i} (size {frame.size})")
            shm_buf.push_unprotected(
                bundle_name="test",
                channel_name="frame",
                new_data=frame,
                write_tail=i,
                write_head=i+1,
                num_elements=1
            )
        
        print("index_buffer after initial pushes:\n", shm_buf.index_buffer[:])
        
        # Pop all 3 frames
        popped = shm_buf.pop_unprotected(start=0, end=3)
        print("Popped frames (0 to 3):", popped)
        # Expected contiguous array of size 5 + 3 + 4 = 12
        expected_all = np.concatenate(frames)
        assert len(popped) == 1
        assert np.array_equal(popped[0], expected_all)
        print("Sequential pop of multiple frames passed!")

        # 2. Test wrapping around the flat bytes buffer
        # Currently we are at offset 12. Let's push a frame of size 10.
        # This should wrap around: 8 bytes at [12:20] and 2 bytes at [0:2].
        frame_wrap = np.array([21, 22, 23, 24, 25, 26, 27, 28, 29, 30], dtype=np.uint8)
        print("Pushing wrapping frame (size 10)")
        shm_buf.push_unprotected(
            bundle_name="test",
            channel_name="frame",
            new_data=frame_wrap,
            write_tail=3,
            write_head=4,
            num_elements=1
        )
        print("index_buffer after wrapping push:\n", shm_buf.index_buffer[:])
        
        # Pop the wrapping frame
        popped_wrap = shm_buf.pop_unprotected(start=3, end=4)
        print("Popped wrapping frame:", popped_wrap)
        assert len(popped_wrap) == 2
        assert np.array_equal(np.concatenate(popped_wrap), frame_wrap)
        print("Wrap-around byte buffer test passed!")

        # 3. Test wrapping around index buffer AND byte buffer together
        # We are at write_head = 4. Let's push another frame at index 4 (write_head = 0 after wrap)
        frame_index_wrap = np.array([101, 102], dtype=np.uint8)
        print("Pushing index-wrapping frame (size 2)")
        shm_buf.push_unprotected(
            bundle_name="test",
            channel_name="frame",
            new_data=frame_index_wrap,
            write_tail=4,
            write_head=0,
            num_elements=1
        )
        print("index_buffer after index-wrapping push:\n", shm_buf.index_buffer[:])
        
        # Pop the wrapping frame
        popped_idx_wrap = shm_buf.pop_unprotected(start=4, end=0)
        print("Popped index-wrapping frame:", popped_idx_wrap)
        assert len(popped_idx_wrap) == 1
        assert np.array_equal(popped_idx_wrap[0], frame_index_wrap)
        print("Wrap-around index buffer test passed!")

    finally:
        shm_buf.close()
        shm_buf.unlink()

if __name__ == "__main__":
    test_circular_buffer()
