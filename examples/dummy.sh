#!/bin/sh
source .venv/bin/activate
export PYTHONPATH="$(pwd)"

while true; do
    printf "Enter Subject ID: "
    read -r SUBJECT_ID
    if [ -n "$SUBJECT_ID" ]; then
        break
    fi
    echo "Error: Subject ID cannot be empty."
done

mkdir -p ./run
FILE="./run/trial_auto_id_${SUBJECT_ID}.txt"
if [ -f "$FILE" ]; then
    TRIAL_ID=$(cat "$FILE")
    TRIAL_ID=$((TRIAL_ID + 1))
else
    TRIAL_ID=0
fi
echo "$TRIAL_ID" > "$FILE"

hermes-cli -o ./data -f ./examples/dummy.yml -e project=Test subject="$SUBJECT_ID" trial="$TRIAL_ID"
