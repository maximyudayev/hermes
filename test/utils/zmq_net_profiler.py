import argparse
import zmq
import time
import struct


def run_profiler(ip_address, pub_port, sub_port, duration, freq):
    ctx = zmq.Context()

    # Setup Publisher (Sends the Ping)
    pub = ctx.socket(zmq.PUB)
    pub.bind(f"tcp://{ip_address}:{pub_port}")

    # Setup Subscriber (Receives the Pong)
    sub = ctx.socket(zmq.SUB)
    sub.bind(f"tcp://{ip_address}:{sub_port}")
    sub.setsockopt(zmq.SUBSCRIBE, b"")  # Subscribe to all topics

    print("Sockets bound. Waiting 2 seconds for ZMQ Slow Joiner syndrome...")
    time.sleep(2)

    print(f"Starting RTT Echo Test at {freq} Hz for {duration} seconds...")

    rtt_measurements = []
    end_time = time.time() + duration

    while time.time() < end_time:
        # 1. Take monotonic timestamp in nanoseconds
        t_send = time.perf_counter()

        # 2. Pack as an unsigned long long (8 bytes) and publish
        payload = struct.pack("<d", t_send)
        pub.send(payload)

        try:
            # 3. Block until we get the echo back (with a 1-second timeout)
            sub.poll(1000)
            echo_payload = sub.recv(zmq.NOBLOCK)

            # 4. Take arrival timestamp immediately
            t_recv = time.perf_counter()

            # Unpack to verify it's our payload (optional, but good practice)
            t_orig = struct.unpack("<d", echo_payload)[0]
            if t_orig == t_send:
                rtt_measurements.append(t_recv - t_send)

        except zmq.Again:
            print("Dropped packet or timeout.")

        # Maintain roughly the target frequency
        time.sleep(1.0 / freq)

    # --- Processing the Results ---
    if not rtt_measurements:
        print("Error: No echoes received. Check network and Device B.")
        return

    # Convert to milliseconds for easier reading
    absolute_min_rtt = min(rtt_measurements)
    physical_floor = absolute_min_rtt / 2.0

    print("\n--- Network Floor Profile Complete ---")
    print(f"Total Packets Echoed: {len(rtt_measurements)}")
    print(f"Absolute Minimum RTT: {absolute_min_rtt:.9f} s")
    print(f"Calculated 1-Way Floor: {physical_floor:.9f} s")
    print(
        f"Average RTT (For reference, includes jitter): {sum(rtt_measurements) / len(rtt_measurements):.9f} s"
    )

    pub.close()
    sub.close()
    ctx.term()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ip_address", type=str)
    parser.add_argument("pub_port", type=int)
    parser.add_argument("sub_port", type=int)
    parser.add_argument("duration", type=int)
    parser.add_argument("freq", type=int)

    args = parser.parse_args()

    run_profiler(
        args.ip_address, args.pub_port, args.sub_port, args.duration, args.freq
    )
