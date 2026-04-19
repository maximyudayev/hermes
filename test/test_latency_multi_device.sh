#!/bin/bash

. ../.venv/bin/activate

rm -r ./data/latency/multi_device/run_latency_vs_frequency
rm -r ./data/latency/multi_device/run_latency_vs_msgsize

# --- Configuration for remote slave device. Match with the values in master.yml ---
REMOTE_USER=<slave_username>
REMOTE_HOST=<slave_ip_address>
REMOTE_BASE_DIR=<slave_hermes_project_path>  # Documents/hermes <-- OS-independent
REMOTE_OS=<slave_os>  # "linux" or "windows"
DURATION=60

export HERMES_EXP_NUM_BYTES=1000
counter=0
for n in 1 2 5 10 20 50 100 200 500 1000 2000 5000 10000 20000 50000 100000; do
  export HERMES_EXP_RATE=$n
  REMOTE_PATH="$REMOTE_BASE_DIR/data/latency/multi_device/run_latency_vs_frequency/trial_$counter"
  LOCAL_PATH="./data/latency/multi_device/run_latency_vs_frequency/trial_$counter"

  echo "Injecting environment variables into slave device configuration..."
  python dist_utils.py slave_src.yml slave.yml

  echo "Starting experiment $counter..."
  hermes-cli -o data/latency/multi_device -d $DURATION --experiment run=latency_vs_frequency trial=$counter -f master.yml

  echo "Copying results from remote device..."
  scp "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/*" "$LOCAL_PATH/"

  echo "Calculating latency between devices..."
  python latency.py ./data/latency/multi_device $counter $n 1

  ((counter++))
  echo "Completed experiment $counter"
  echo

  echo "Removing log data from local device..."
  rm -r "$LOCAL_PATH"

  echo "Removing log data from remote device..."
  if [ "$REMOTE_OS" == "linux" ]; then
    ssh "$REMOTE_USER@$REMOTE_HOST" "rm -r '$REMOTE_PATH'"
  elif [ "$REMOTE_OS" == "windows" ]; then
    REMOTE_WIN_PATH=${REMOTE_PATH//\//\\}
    ssh "$REMOTE_USER@$REMOTE_HOST" "rmdir /s /q $REMOTE_WIN_PATH"
  fi
done

export HERMES_EXP_RATE=100
counter=0
for n in 10 20 50 100 200 500 1000 2000 5000 10000 20000 50000 100000 200000 500000 1000000; do
  export HERMES_EXP_NUM_BYTES=$n
  REMOTE_PATH="$REMOTE_BASE_DIR/data/latency/multi_device/run_latency_vs_msgsize/trial_$counter"
  LOCAL_PATH="./data/latency/multi_device/run_latency_vs_msgsize/trial_$counter"

  echo "Injecting environment variables into slave device configuration..."
  python dist_utils.py slave_src.yml slave.yml

  echo "Starting experiment $counter..."
  hermes-cli -o data/latency/multi_device -d $DURATION --experiment run=latency_vs_msgsize trial=$counter -f master.yml

  echo "Copying results from remote device..."
  scp "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/*" "$LOCAL_PATH/"

  echo "Calculating latency between devices..."
  python latency.py ./data/latency/multi_device $counter $n 0

  ((counter++))
  echo "Completed experiment $counter"
  echo

  echo "Removing log data from local device..."
  rm -r "$LOCAL_PATH"

  echo "Removing log data from remote device..."
  if [ "$REMOTE_OS" == "linux" ]; then
    ssh "$REMOTE_USER@$REMOTE_HOST" "rm -r '$REMOTE_PATH'"
  elif [ "$REMOTE_OS" == "windows" ]; then
    REMOTE_WIN_PATH=${REMOTE_PATH//\//\\}
    ssh "$REMOTE_USER@$REMOTE_HOST" "rmdir /s /q $REMOTE_WIN_PATH"
  fi
done