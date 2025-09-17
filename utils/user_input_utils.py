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
                  command=lambda: self._submit("configs/AidFOG/backpack_no_glasses.yml")).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="With glasses", width=20,
                  command=lambda: self._submit("configs/AidFOG/backpack.yml")).pack(side=tk.LEFT, padx=10)

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

