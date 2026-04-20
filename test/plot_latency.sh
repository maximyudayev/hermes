#!/bin/bash

. ../.venv/bin/activate

python utils/gen_plot_latency.py $1
