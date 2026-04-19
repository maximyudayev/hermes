import argparse
import zmq


def run_echo(ip_address: str, sub_port: int, pub_port: int):
    ctx = zmq.Context()

    # Setup Subscriber (Receives the Ping)
    sub = ctx.socket(zmq.SUB)
    sub.connect(f"tcp://{ip_address}:{sub_port}")
    sub.setsockopt(zmq.SUBSCRIBE, b"")

    # Setup Publisher (Sends the Pong)
    pub = ctx.socket(zmq.PUB)
    pub.connect(f"tcp://{ip_address}:{pub_port}")

    print(f"Connected to {ip_address}. Ready to echo...")

    try:
        while True:
            # Block until a message arrives
            payload = sub.recv()

            # Immediately dump it back onto the network
            pub.send(payload)

    except KeyboardInterrupt:
        print("Echo stopped by user.")
    finally:
        pub.close()
        sub.close()
        ctx.term()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ip_address", type=str)
    parser.add_argument("sub_port", type=int)
    parser.add_argument("pub_port", type=int)

    args = parser.parse_args()

    run_echo(args.ip_address, args.sub_port, args.pub_port)
