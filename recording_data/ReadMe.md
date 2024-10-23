# Installation
A brief summary of the required software and the currently tested versions is below.  The following subsections contain more information about each one.

- Conda
- Pupil Capture 3.5.1
- Movella DOT SDK 2023.6
- HDFView 3.1.3 [optional but useful]

## Windows
### Environment

Recreate the environment by `conda create --file environment.yml`

### Pupil Capture

The Pupil Core software to interface with the eye tracker can be downloaded from https://docs.pupil-labs.com/core.  Version 3.5.1 has been tested so far.

### Movella DOT SDK

Download and install [DOT SDK](https://www.xsens.com/software-downloads).  Version 2023.6 has been tested so far.

Activate project conda environment: `conda activate aidwear` 

Install the wheel file for DOTs into the environment:
`pip install --no-deps "<path to installed Movella dictionary>\DOT PC SDK <SDK version>\SDK Files\Python\x64\movelladot_pc_sdk-<SDK version>-cp39-none-win_amd64.whl"`

### HDFView

While not required, this lightweight tool is great for exploring HDF5 data.  The official download page is at https://www.hdfgroup.org/downloads/hdfview, and it can also be downloaded without an account from https://www.softpedia.com/get/Others/Miscellaneous/HDFView.shtml.

# Running

Run `_launchers\stream_AidWear.py`, adjust parameters for experiment and active sensors as desired (also in individual sensor streamers, if needed).

See `stream_and_save_data_multiProcess.py` for an example of streaming and saving data.  Adjust `sensor_streamer_specs` to reflect the available sensors, adjust `datalogging_options` as desired to select when/where/how data is saved, and adjust `duration_s` to the desired maximum runtime.

See `stream_and_save_data_singleProcess.py` for an example of streaming and saving data without using SensorManager.  This will run in a single process and thus will not leverage multiple cores.

# Code and Usage Overview

## Streaming Data
The code is based around the abstract **SensorStreamer** class, which provides methods for streaming data.  Each streamer can have one or more *devices*, and each device can have one or more data *streams*.  Data streams can have arbitrary sampling rates, data types, and dimensions.  Each subclass specifies the expected streams and their data types.

For example, the MyoStreamer class may have a left-arm device and a right-arm device connected.  Each one has streams for EMG, acceleration, angular velocity, gesture predictions, etc.  EMG data uses 200Hz, IMU uses 50Hz, and prediction data is asynchronous.

Each stream has a few channels that are created automatically: the data itself, a timestamp as seconds since epoch, and the timestamp formatted as a string.  Subclasses can also add extra channels if desired.  Timestamps are always created by using `time.time()` when data arrives.  Some devices such as the Xsens also have their own timestamps; these are treated as simply another data stream, and can be used in post-processing if desired.

## Implemented Streamers

### DotsStreamer
The DotsStreamer streams lower limb data from the Dots IMUs.

### EyeStreamer
The EyeStreamer streams gaze and video data from the Pupil Labs eye tracker.  Pupil Capture should be running, calibrated, and streaming before starting the Python scripts.  The following outlines the setup procedure:
- Start Pupil Capture
- Calibrate according to https://docs.pupil-labs.com/core/#_4-calibration
- In Pupil Capture, select `Network API` on the right.  The code currently expects:
  - Port `50020`
  - Frames in `BGR` format

### AwindaStreamer
The AwindaStreamer streams data from the Awinda body tracking suit as well as two Manus gloves if they are available.

The Xsens MVN software should be running, calibrated, and configured for network streaming before starting the Python scripts.  Network streaming can be configured in `Options > Network Streamer` with the following options:
- IP address `127.0.0.1`
- Port `9763`
- Protocol `UDP`
- Stream rate as desired
- Currently supported Datagram selections include:
  - `Position + Orientation (Quaternion)`: segment positions and orientations, which will include finger data if enabled
  - `Position + Orientation (Euler)`: segment positions and orientations, which will include finger data if enabled
  - `Time Code`: the device timestamp of each frame
  - `Send Finger Tracking Data` (if Manus gloves are connected - see below for more details)
  - `Center of Mass`: position, velocity, and acceleration of the center of mass
  - `Joint Angles`: angle of each joint, but only for the main body (finger joint angles do not seem to be supported by Xsens)

Note that it seems like the selected stream rate is not generally achieved in practice.  During some testing with a simple loop that only read raw data from the stream when only the `Time Code` was being streamed, the message rate was approximately half the selected rate up to a selection of 60Hz.  After that, the true rate remained constant at about 30-35Hz.

A few optional Xsens configuration settings in `Options > Preferences` that might be useful are noted below:
- Check `Enable simple calibration routines` to allow calibration without movement.  This is not recommended for 'real' experiments, but can make debugging/iterating faster.
- Uncheck `Maximum number of frames kept in memory` if long experiments are anticipated and memory is not a large concern.

### CameraStreamer

### InsoleStreamer

### ExperimentControlStreamer
The NotesStreamer allows the user to enter notes at any time to describe experiment updates.  Each note will be timestamped in the same way as any other data, allowing notes to be syncronized with sensor data.

### NotesStreamer
The NotesStreamer allows the user to enter notes at any time to describe experiment updates.  Each note will be timestamped in the same way as any other data, allowing notes to be syncronized with sensor data.

## Saving Data
The **DataLogger** class provides functionality to save data that is streamed from SensorStreamer objects.  It can write data to HDF5 and/or CSV files.  Video data will be excluded from these files, and instead written to video files.  Data can be saved incrementally throughout the recording process, and/or at the end of an experiment.  Data can optionally be cleared from memory after it is incrementally saved, thus reducing RAM usage.

Data from all streamers given to a DataLogger object will be organized into a single hierarchical HDF5 file that also contains metadata.  If you would prefer data from different streamers be saved in separate HDF5 files, multiple DataLogger objects can simply be created.  Note that when using CSVs, a separate file will always be created for each data stream.

N-dimensional data will be written to HDF5 files directly, and will be unwrapped into individual columns for CSV files.

## Sensor Manager
The **SensorManager** class is a helpful wrapper for coordinating multiple streamers and data loggers.  It connects and launches all streamers, and creates and configures all desired data loggers.  It does so using multiprocessing, so that multiple cores can be leveraged; see below for more details on this.

## Multiprocessing and threading

Note that in Python, using `Threads` is useful for allowing operations to happen concurrently and for using `Locks` to coordinate access, but it does not leverage multiple cores due to Python's Global Interpreter Lock.  Using `Multiprocessing` creates separate system processes and can thus leverage multiple cores, but data cannot be shared between such processes as easily as threads.

The current framework uses both threads and processes.

SensorStreamer and DataLogger launch their run() methods in new threads, and use locks to coordinate data access.  You can thus use these classes directly, and have non-blocking operations but only use a single core.

SensorManager spawns multiple processes so multiple cores can be used.
- It starts each sensor streamer in its own process, unless the streamer specifies that it must be in the main process (currently only NotesStreamer, since user input does not work from child processes).
- Data logging happens on the main process.
- To allow data to be passed from the child processes to the main process for logging, each streamer class is registered with Python's `BaseManager` to create a `Proxy` class that pickles data for communication.

So hopefully, incrementally writing to files will not unduly impact streaming performance.  This will facilitate saving data in the event of a crash, and reducing RAM usage during experiments.

```bash
conda info --envs
conda env create -f environment.yml
conda list --revisions
conda install --rev REVNUM
conda env update --file environment.yml --prune
conda env export --from-history > environment.yml
conda remove --name myenv --all
```