#!/bin/bash

. ../.venv/bin/activate

rm -r ./data/latency/run_latency_vs_frequency
rm -r ./data/latency/run_latency_vs_msgsize

export HERMES_EXP_NUM_BYTES=1000
counter=0
for n in 1 2 5 10 20 50 100 200 500 1000 2000 5000 10000 20000; do
  export HERMES_EXP_RATE=$n
  echo "Starting experiment $counter..."
  hermes-cli -o data/latency -d 30 --experiment run=latency_vs_frequency --config_file test_latency.yml
  ((counter++))
  echo "Completed experiment $counter"
  echo
  python latency.py $n 1
  rm -r ./data/latency/run_latency_vs_frequency
done

export HERMES_EXP_RATE=100
counter=0
for n in 10 20 50 100 200 500 1000 2000 5000 10000 20000 50000 100000 200000 500000; do
  export HERMES_EXP_NUM_BYTES=$n
  echo "Starting experiment $counter..."
  hermes-cli -o data/latency -d 30 --experiment run=latency_vs_msgsize --config_file test_latency.yml
  ((counter++))
  echo "Completed experiment $counter"
  echo
  python latency.py $n 0
  rm -r ./data/latency/run_latency_vs_msgsize
done
