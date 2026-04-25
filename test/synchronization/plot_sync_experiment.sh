#!/bin/bash

source ../../.venv/bin/activate

export DATA_PATH=Documents/sample_data/trial_0

python utils/extract_multimodal_snapshot.py
    -n ego
    -f $DATA_PATH/glasses.hdf5
    -v $DATA_PATH/glasses_ego.mkv
    -d /glasses/ego
    -o 0
    -n pose
    -f $DATA_PATH/mvn-analyze.hdf5
    -v -
    -d /mvn-analyze
    -o 0.180
    -n imu
    -f $DATA_PATH/revalexo.hdf5
    -v -
    -d /revalexo/nicla_thigh_right
    -o 0
    -n motor
    -f $DATA_PATH/revalexo.hdf5
    -v -
    -d /revalexo/motor_hip_right
    -o 0
    -n camera
    -f $DATA_PATH/cameras.hdf5
    -v $DATA_PATH/cameras_40478064.mkv
    -d /cameras/40478064
    -o 0
