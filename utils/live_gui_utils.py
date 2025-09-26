############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Created 2024-2025 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Juha Carlon and Vayalet Stefanova.
#
# ############
import numpy as np
import socket
import json
from typing import Optional
import cv2
import sys
from pathlib import Path
import threading

cv2.setNumThreads(1)
LIVE_GUI_PATH = Path(r"C:\Users\HERMES\Documents\Live-GUI\LiveGUI.py")
sys.path.insert(0, str(LIVE_GUI_PATH.parent))

from LiveGUI import run_gui #type: ignore

class LiveGUIPoster:
    def __init__(self,
                tag: str,
                ip_gui: str,
                port_gui: str,
                buffer_shape: Optional[tuple[int, int, int]] = None,
                 buffer_dtype: Optional[type] = None):

        self.tag = tag

        self._data_buffer_index = 0
        self._data_buffer_counter = 0
        self._data_buffer_shape = buffer_shape
        self._data_buffer = np.zeros(buffer_shape, dtype=buffer_dtype)

        self.GUIsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ip_gui = ip_gui
        self.port_gui = int(port_gui)

    def send_frame_meta(self, meta: dict) -> None:
        try:
            payload_meta = json.dumps(meta, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            header = f"meta||{self.tag}||".encode("utf-8")
            self.GUIsocket.sendto(header + payload_meta, (self.ip_gui, self.port_gui))
        except OSError:
            return
        
    def send_frame_bytes(self,
                         camera_id: str,
                         frame_index: int,
                         frame_bytes: bytes,
                         *,
                         max_payload: int = 1400) -> None:
        total = (len(frame_bytes) + max_payload - 1) // max_payload
        if total == 0:
            total = 1

        for chunk_idx in range(total):
            start = chunk_idx * max_payload
            end = min(start + max_payload, len(frame_bytes))
            chunk = frame_bytes[start:end]

            header = f"frame||{self.tag}||{camera_id}||{int(frame_index)}||{chunk_idx}||{total}||".encode("utf-8")
            try:
                self.GUIsocket.sendto(header + chunk, (self.ip_gui, self.port_gui))
            except OSError:
                return

    def post_data_UDP(self) -> None:
        for i in range(self._data_buffer.shape[0]):
            samples = self._data_buffer[i]   
            payload = f"sensor||{self.tag}-{i+1}||{self._data_buffer_counter}||".encode() + samples.tobytes()
            try:
                self.GUIsocket.sendto(payload, (self.ip_gui, self.port_gui))
            except OSError as e:
                return

    def flush_data_buffer(self) -> None:
        # reset valid data index to 0
        self._data_buffer_index = 0
        self.post_data_UDP()
        # add data counter
        self._data_buffer_counter += 1

def get_free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def launch_gui(args):
    # extract camera ids once
    camera_ids = []
    for spec in args.producer_specs:
        if spec.get("class") == "CameraStreamer":
            cam_map = spec.get("camera_mapping", {})
            camera_ids = list(cam_map.values())
            break

    port = int(args.external_gui_specs['gui_port'])
    # print(f"GUI port: {port}")

    t = threading.Thread(
        target=run_gui,
        kwargs={"port": port, "camera_ids": camera_ids, "quiet": True},
        name="LiveGUI-Main",
        daemon=True,
    )
    t.start()
    print("To see live camera stream, go to: http://127.0.0.1:8050", flush=True)
    return t


