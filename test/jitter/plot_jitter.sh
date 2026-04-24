#!/bin/bash

source ../../.venv/bin/activate

python utils/gen_plot_jitter.py
    -o "~/Documents/hermes/test/data/jitter"
    -g "Intel Core i7-9700TE"
    -n "Camera Eth1"
    -f "~/Documents/hermes/data/trial_0/cameras.hdf5"
    -d /cameras/40478064/toa_s
    -s /cameras/40478064/frame_index
