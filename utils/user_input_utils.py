############
#
# Copyright (c) 2025 Vayalet Stefanova and KU Leuven eMedia Lab
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
# Created 2025 for AidWear, AidFOG, and RevalExo projects of KU Leuven.
#
# ############

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
import time
import sys
from tkinter.scrolledtext import ScrolledText


######################################
######################################
# A class for selecting experiment args.
######################################
######################################
class ExperimentGUI:
    def __init__(self, args):
        self.args = args
        self.root = tk.Tk()
        self.root.title("Experiment Setup")
        self.root.geometry("500x400")  
        self.root.eval('tk::PlaceWindow . center')  

        self.subject_id = tk.Entry(self.root, justify="center")
        self.group_id = tk.StringVar(value="")
        self.session_id = tk.StringVar(value="")
        self.medication = tk.StringVar(value="")

        self.group_id_box = None
        self.session_id_box = None
        self.medication_box = None

        self._build_ui()
        self.root.mainloop()

    def _create_dropdown(self, text, variable, values):
        tk.Label(self.root, text=text).pack(pady=5)
        combo = ttk.Combobox(self.root, textvariable=variable, values=values, state="readonly", justify="center")
        combo.set("Select") 
        combo.pack()
        return combo

    def _build_ui(self):
        tk.Label(self.root, text="Subject ID").pack(pady=5)
        self.subject_id.pack()

        self.group_id_box = self._create_dropdown("Group ID", self.group_id, ["FR", "NF", "HC"])
        self.session_id_box = self._create_dropdown("Session ID", self.session_id, ["01", "02", "03"])
        self.medication_box = self._create_dropdown("Medication", self.medication, ["ON", "OFF"])

        # New text above buttons
        tk.Label(self.root, text="\nStart a new recording:").pack(pady=10)

        # Two buttons for recording options
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="Without glasses", width=20,
                  command=lambda: self._submit("configs/test/local_dots.yml")).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="With glasses", width=20,
                  command=lambda: self._submit("configs/AiDFOD/backpack_no_glasses.yml")).pack(side=tk.LEFT, padx=10)



    def _submit(self, config_file):
        uid = self.subject_id.get().strip()

        if not uid or self.group_id.get() in ["", "Select"] or \
           self.session_id.get() in ["", "Select"] or \
           self.medication.get() in ["", "Select"]:
            messagebox.showerror("Error", "Fill in all fields!")
            return

        self.args.experiment.update({
            "subject": uid.zfill(3),
            "group": self.group_id.get(),
            "session": self.session_id.get(),
            "medication": self.medication.get()
        })
        self.args.config_file = config_file

        self.root.destroy()

    def get_experiment_inputs(self):
        return self.args

class QueueHandler(logging.Handler):
    def __init__(self, message_queue):
        super().__init__()
        self.queue = message_queue
    def emit(self, record):
        self.queue.put(self.format(record))

class ThreadSafeStdout:
    def __init__(self, message_queue):
        self.queue = message_queue
    def write(self, message):
        if message.strip():
            self.queue.put(message)
    def flush(self):
        pass

class PrintPopup(tk.Tk):
    def __init__(self, message_queue, quit_flag):
        super().__init__()
        self.title("Updates")
        self.text_area = ScrolledText(self, wrap=tk.WORD, state='disabled', height=25, width=100)
        self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        tk.Button(self, text="Quit Experiment", command=lambda: quit_flag.__setitem__('stop', True)).pack(pady=5)
        self.queue = message_queue
        self.quit_flag = quit_flag
        self.after(100, self._poll_queue)
    def _poll_queue(self):
        while not self.queue.empty():
            msg = self.queue.get_nowait()
            self.text_area.configure(state='normal')
            self.text_area.insert(tk.END, msg + "\n")
            self.text_area.configure(state='disabled')
            self.text_area.yview(tk.END)
        self.after(100, self._poll_queue)

def run_broker(local_broker, duration_s, quit_flag):
    from utils.mp_utils import launch_callable
    t = threading.Thread(target=launch_callable, args=(local_broker, duration_s))
    t.start()
    while not quit_flag["stop"] and t.is_alive():
        time.sleep(0.5)
    local_broker.set_is_quit()
    t.join()

