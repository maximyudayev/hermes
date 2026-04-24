import argparse
import zmq


def run_echo(profiler_ip: str):
    ctx = zmq.Context()

    # Setup Subscriber (Receives the Ping)
    sub = ctx.socket(zmq.SUB)
    sub.connect(f"tcp://{profiler_ip}:5555")
    sub.setsockopt(zmq.SUBSCRIBE, b"")

    # Setup Publisher (Sends the Pong)
    pub = ctx.socket(zmq.PUB)
    pub.connect(f"tcp://{profiler_ip}:5556")

    print(f"Connected to {profiler_ip}. Ready to echo...")

    try:
        while True:
            # Wait for a message with a 30-second timeout
            if sub.poll(30000):  # 30 seconds in milliseconds
                payload = sub.recv()

                # Immediately dump it back onto the network
                pub.send(payload)
            else:
                print("No message received for 30 seconds. Exiting.")
                break

    except KeyboardInterrupt:
        print("Echo stopped by user.")
    finally:
        pub.close()
        sub.close()
        ctx.term()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("profiler_ip", type=str)

    args = parser.parse_args()

    run_echo(args.profiler_ip)
