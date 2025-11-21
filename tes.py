import time
import multiprocessing as mp
import uvc

# ================= CONFIG =================

DURATION = 30.0  # seconds

# Identify cameras by substring in their name
WORLD_NAME_SUBSTR = "ID2"   # e.g. "Pupil Cam1 ID2" (world/ego)
EYE_NAME_SUBSTR   = "ID0"   # e.g. "Pupil Cam2 ID0" (eye)

# Target modes
WORLD_TARGET = {"width": None, "height": None, "fps": 30}     # any res @ 30 Hz
EYE_TARGET   = {"width": 192, "height": 192, "fps": 120}      # 192x192 @ 120 Hz

# Bandwidth factors
WORLD_BW = 1.0
EYE_BW   = 1.7

# ===========================================


def find_device(devices, name_substr: str):
    """Find first device whose 'name' contains name_substr."""
    for d in devices:
        if name_substr in d["name"]:
            return d
    return None


def select_mode(cap, target_width, target_height, target_fps) -> bool:
    """
    If width/height are None, only match FPS.
    Otherwise match all three.
    """
    print(f"\n[{cap}] Available modes:")
    best = None

    for mode in cap.available_modes:
        print("  MODE:", mode)
        w, h, fps = mode[0], mode[1], mode[2]

        if target_width is not None and target_height is not None:
            if w == target_width and h == target_height and fps == target_fps:
                best = mode
                break
        else:
            # width/height not enforced, just match fps
            if fps == target_fps:
                best = mode
                break

    if best is None:
        print(f"!! No exact mode match for target {target_width}x{target_height}@{target_fps}")
        return False

    print(f">>> SELECTED MODE: {best}")
    cap.frame_mode = best
    return True


def capture_worker(role: str,
                   name_substr: str,
                   target: dict,
                   bandwidth_factor: float,
                   duration: float):
    """
    role: "world" or "eye" (just for logging)
    name_substr: substring to find device by name
    target: dict with keys width, height, fps
    bandwidth_factor: float
    duration: seconds
    """
    print(f"[{role}] Starting worker. Looking for device with name containing '{name_substr}'")

    devices = uvc.device_list()
    print(f"[{role}] Devices: {devices}")

    dev = find_device(devices, name_substr)
    if not dev:
        print(f"[{role}] Device with '{name_substr}' not found, aborting.")
        return

    print(f"[{role}] Opening device: {dev}")

    cap = uvc.Capture(dev["uid"])
    cap.bandwidth_factor = bandwidth_factor
    print(f"[{role}] Set bandwidth_factor = {bandwidth_factor}")

    if not select_mode(cap, target["width"], target["height"], target["fps"]):
        print(f"[{role}] Failed to select mode, closing.")
        cap.close()
        return

    frames = 0
    t0 = time.time()
    print(f"[{role}] Grabbing for {duration:.1f} seconds...")

    try:
        while (time.time() - t0) < duration:
            try:
                frame = cap.get_frame(timeout=0.5)
            except TimeoutError:
                continue
            except uvc.InitError as err:
                print(f"[{role}] InitError: {err}")
                break
            except uvc.StreamError as err:
                print(f"[{role}] StreamError: {err}")
                break
            else:
                frames += 1
    finally:
        cap.close()

    elapsed = time.time() - t0
    fps = frames / elapsed if elapsed > 0 else 0.0
    print(f"[{role}] Elapsed: {elapsed:.2f} s, frames: {frames}, → {fps:.2f} fps")


def main():
    # On Windows, it's safer to use 'spawn'
    mp.set_start_method("spawn", force=True)

    world_proc = mp.Process(
        target=capture_worker,
        args=("world", WORLD_NAME_SUBSTR, WORLD_TARGET, WORLD_BW, DURATION),
    )

    eye_proc = mp.Process(
        target=capture_worker,
        args=("eye", EYE_NAME_SUBSTR, EYE_TARGET, EYE_BW, DURATION),
    )

    print("Starting world and eye processes...")
    world_proc.start()
    eye_proc.start()

    world_proc.join()
    eye_proc.join()
    print("Both processes finished.")


if __name__ == "__main__":
    # main()
    import msgpack

    path = "C:/Users/Owner/pupil_capture_settings/user_settings_eye1"

    with open(path, "rb") as f:
        data = msgpack.unpack(f, raw=False)

    print(data)

