#!/bin/bash

source ../../.venv/bin/activate

python utils/calc_jitter.py
    -o "~/Documents/hermes/test/data/jitter/aidfog/camera_1"
    -f "~/Documents/hermes/data/trial_0/cameras.hdf5"
    -d /cameras/40478064/toa_s
    -s /cameras/40478064/frame_index
