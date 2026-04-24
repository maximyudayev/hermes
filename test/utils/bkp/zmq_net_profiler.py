import argparse
import os
from pathlib import Path
import zmq
import time
import struct
import platform
import subprocess


def launch_echo_node(
    ssh_os: str,
    ssh_username: str,
    ssh_host_ip: str,
    launch_dir: str,
    master_ip: str,
) -> list[subprocess.Popen]:
    if ssh_os == "windows":
        remote_cmd = (
            f"cd /d {launch_dir} && "
            f"python utils\zmq_net_echo.py {master_ip} && "
            f"exit"
        )
    else:
        remote_cmd = (
            f"source ~/.bash_profile 2>/dev/null || source ~/.profile 2>/dev/null; "
            f"cd {launch_dir} && "
            f'export PYTHONPATH="$(pwd):$PYTHONPATH" && '
            f"python utils/zmq_net_echo.py {master_ip} && "
            f"exit"
        )

    if platform.system() == "Windows":
        prog = ["cmd", "/c"]
    elif platform.system() == "Linux":
        prog = ["gnome-terminal", "--"]
    elif platform.system() == "Darwin":
        prog = ["open", "-a", "Terminal"]

    proc = subprocess.Popen(
        [
            *prog,
            "ssh",
            "-tt",
            "-o",
            "TCPKeepAlive=no",
            "-o",
            "ServerAliveInterval=30",
            f"{ssh_username}@{ssh_host_ip}",
            remote_cmd,
        ],
        creationflags=subprocess.CREATE_NEW_CONSOLE
        if platform.system() == "Windows"
        else 0,
    )

    return proc


def run_profiler(
    echo_os: str,
    echo_username: str,
    echo_ip: str,
    echo_dir: str,
    profiler_ip: str,
    duration: int,
    freq: int,
):
    ssh_echo_proc = launch_echo_node(echo_os, echo_username, echo_ip, echo_dir, profiler_ip)

    ctx = zmq.Context()

    # Setup Publisher (Sends the Ping)
    pub = ctx.socket(zmq.PUB)
    pub.bind(f"tcp://{profiler_ip}:5555")

    # Setup Subscriber (Receives the Pong)
    sub = ctx.socket(zmq.SUB)
    sub.bind(f"tcp://{profiler_ip}:5556")
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

    ssh_echo_proc.wait()  # Wait for the echo process to finish (it should exit after 30s of no messages)

    # --- Processing the Results ---
    if not rtt_measurements:
        print("Error: No echoes received. Check network and Device B.")
        return

    # Convert to milliseconds for easier reading
    absolute_min_rtt = min(rtt_measurements)
    physical_floor = absolute_min_rtt / 2.0

    current_folder = os.path.dirname(os.path.realpath(__file__))
    with open(Path(current_folder, '../net_floor.txt'), 'w') as f:
        f.write(f"{physical_floor:.9f}")

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
    parser.add_argument("echo_os", type=str)
    parser.add_argument("echo_username", type=str)
    parser.add_argument("echo_ip", type=str)
    parser.add_argument("echo_dir", type=str)
    parser.add_argument("profiler_ip", type=str)
    parser.add_argument("duration", type=int)
    parser.add_argument("freq", type=int)

    args = parser.parse_args()

    run_profiler(
        args.echo_os,
        args.echo_username,
        args.echo_ip,
        args.echo_dir,
        args.profiler_ip,
        args.duration,
        args.freq,
    )
