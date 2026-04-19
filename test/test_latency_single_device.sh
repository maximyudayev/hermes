#!/bin/bash

. ../.venv/bin/activate

rm -r ./data/latency/localhost/run_latency_vs_frequency
rm -r ./data/latency/localhost/run_latency_vs_msgsize

DURATION=60

export HERMES_EXP_NUM_BYTES=1000
counter=0
for n in 1 2 5 10 20 50 100 200 500 1000 2000 5000 10000 20000; do
  export HERMES_EXP_RATE=$n

  echo "Starting experiment $counter..."
  hermes-cli -o data/latency/localhost -d $DURATION --experiment run=latency_vs_frequency trial=$counter --config_file localhost.yml

  python latency.py $counter $n 1
  rm -r ./data/latency/localhost/run_latency_vs_frequency/trial_$counter

  ((counter++))
  echo "Completed experiment $counter"
  echo
done

export HERMES_EXP_RATE=100
counter=0
for n in 10 20 50 100 200 500 1000 2000 5000 10000 20000 50000 100000 200000 500000; do
  export HERMES_EXP_NUM_BYTES=$n

  echo "Starting experiment $counter..."
  hermes-cli -o data/latency/localhost -d $DURATION --experiment run=latency_vs_msgsize trial=$counter --config_file localhost.yml

  python latency.py $counter $n 0
  rm -r ./data/latency/localhost/run_latency_vs_msgsize/trial_$counter

  ((counter++))
  echo "Completed experiment $counter"
  echo
done
