#!/bin/bash

. ../.venv/bin/activate

python utils/gen_plot_latency.py ./data/ntp_sync
