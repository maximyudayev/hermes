Hermes
======

Distributed wireless-wired multi-sensor local realtime data collection, processing, and analysis system for intelligent sensor-based applications.

# Table of Contents
1. [System Architecture](#system-architecture)
   1. [Sensor Network](#sensor-network)
   2. [UML](#uml)
      1. [Broker](#stream-broker)
      2. [Streamers](#streamers)
      3. [Workers](#workers)
2. [Installation](#installation)
   1. [Environment](#environment)
      1. [Pupil Core Smartglasses](#pupil-capture)
      2. [DOTs IMUs](#movella-dot-sdk)
      3. [Awinda IMUs](#mtw-awinda-sdk)
      4. [Basler Cameras](#pypylon)
      5. [Moticon Insoles](#moticon-insoles)
      6. [Cometa Pico EMGs](#pico-emg)
      7. [HDF File Viewer](#hdfview)
   2. [Windows-Specific](#windows-specific-configuration)
      1. [Firewall](#firewall)
   3. [Networking](#networking)
      1. [Mobile Router](#mobile-router)
      2. [LANs and WLANs](#lans-and-wlans)
      3. [Remote Desktop](#remote-desktop)
      4. [Synchronization](#synchronization-ptp)
3. [Running](#running)

# System Architecture
## Sensor Network
![Sensor network layout image.](/images/AidWear%20Setup%20Colored.svg)

The [networking](#networking) section extensively describes the connectivity and IT details of the system.

## UML
Here goes the system architecture... drawing

### Stream Broker
The **StreamBroker** class is a an endpoint for proxying data between subscribers and publishers, and a manager for coordinating the lifetime of locally attached sensors wrapped into individual **SensorStreamer** subprocesses, and consumers wrapped into individual **Worker** subprocesses (e.g. AI prediction agents, data visualization, data logging, etc.).  It connects and launches streamers for all locally connected sensors, and creates and configures all desired local consumers of data produced both, locally and remotely by other brokers.  It does so using multiprocessing and [ZeroMQ](https://zeromq.org/) sockets, so that multiple cores can be leveraged to parallelize the work and permit the throughput of sensor data streaming.

### Streamers
The code is based around the abstract **SensorStreamer** class, which provides methods for streaming data.  Each streamer can have one or more *devices*, and each device can have one or more data *streams*.  Data streams can have arbitrary sampling rates, data types, and dimensions.  Each subclass specifies the expected streams and their data types.

For example, the CameraStreamer class may have several camera devices connected.  Each one has a stream for video data and timestamp. An AwindaStreamer has only one device, the suit, but multiple streams of data for acceleration, orientation, packet sequence number, etc.  EMG data uses 100 Hz, IMUs use 20-100 Hz, cameras use 20 FPS, prosthesis data is asynchronous and event-based.

Each stream has a few channels that are created automatically: the data itself, a timestamp as seconds since epoch, and the timestamp formatted as a string.  Subclasses can also add extra channels as desired.  Timestamps indicate the system clock of the moment of arrival of the sample to the host system (i.e. using `time.time()`).  Some devices such as the Pupil Core smartglasses, Basler cameras, and DOTs or Awinda, have their own timestamps: these are treated and saved as another data stream to enable data alignment in post-processing or down the consumer line in realtime applications, where the responsibility to implement an alignment strategy falls on the data subscriber.

#### DotsStreamer
The DotsStreamer streams lower limb data from the Dots IMUs.

#### EyeStreamer
The EyeStreamer streams gaze and video data from the Pupil Labs eye tracker.  Pupil Capture should be running, calibrated, and streaming before starting the Python scripts.  The following outlines the setup procedure:
- Start Pupil Capture
- Calibrate according to https://docs.pupil-labs.com/core/#_4-calibration
- In Pupil Capture, select `Network API` on the right.  The code currently expects:
  - Port `50020`
  - Frames in `BGR` format
- Copy selected resolution and fps settings into the `streamer_specs` dictionary

#### AwindaStreamer
The AwindaStreamer streams data from the Awinda body tracking suit.

#### CameraStreamer

#### InsoleStreamer

#### CometaStreamer

#### MoxyStreamer

#### ExperimentControlStreamer

#### NotesStreamer

### Workers
#### Saving Data
The **DataLogger** class provides functionality to save data that is streamed from SensorStreamer objects.  It can write data to HDF5 and/or CSV files.  Video data will be excluded from these files, and instead written to video files.  Data can be saved incrementally throughout the recording process, and/or at the end of an experiment.  Data can optionally be cleared from memory after it is incrementally saved, thus reducing RAM usage.

Data from all streamers given to a DataLogger object will be organized into a single hierarchical HDF5 file that also contains metadata.  Note that when using CSVs, a separate file will always be created for each data stream.

N-dimensional data will be written to HDF5 files directly, and will be unwrapped into individual columns for CSV files.

#### Visualizing Data
The **DataVisualizer** class...

#### AI Worker
The class...

# Installation
A brief summary of the required software and the currently tested versions is below.  The following subsections contain more information about each one.

- Conda
- Plotly Dash
- Pupil Capture 3.5.1
- Movella DOT SDK 2023.6
- Xsens Awinda MTw SDK 2022.2
- PyPylon
- OpenCV
- Moticon OpenGo smartphone app
- TMSi SDK
- Vicon SDK
- OpenANT
- Basler Pylon Viewer [optional but useful]
- HDFView 3.1.3 [optional but useful]

## Environment
First recreate the Conda environment by `conda env create --file environment.yml` on each networked PC that will connect to sensors and broker data in the setup in any capacity (i.e. fixed and wearable PC).

With `aidwear` conda environment active, install missing PyPi packages `pip install opencv-python`.

### PyPylon
To interface Basler cameras, install [the official](https://github.com/basler/pypylon) Python pylon wrapper into the project conda environment. 

With `aidwear` conda environment active: `pip install pypylon`

In Pylon Viewer, configure camera resolution to guarantee desired frame rate and export persistent profile configuration to a `*.pfs` file to easily and consistently preload desired configurations for Basler cameras.

### Pupil Capture
The Pupil Core software to interface with the eye tracker can be downloaded from https://docs.pupil-labs.com/core.  Version 3.5.1 has been tested so far.

### Movella DOT SDK
Download and install [DOT SDK](https://www.xsens.com/software-downloads).  Version 2023.6 has been tested so far.

Activate project conda environment: `conda activate aidwear` 

Install the wheel file for DOTs into the environment:
`pip install --no-deps "<path to installed Movella directory>\DOT PC SDK <SDK version>\SDK Files\Python\x64\movelladot_pc_sdk-<SDK version>-cp310-none-win_amd64.whl"`

### MTw Awinda SDK
Download and install [MTw Awinda SDK](https://www.xsens.com/software-downloads).  Version 2022.2 has been tested so far.

With `aidwear` conda environment active, install the wheel file for DOTs into the environment:
`pip install --no-deps "<path to installed Awinda directory>\MT Software Suite <SDK version>\MT SDK\Python\x64\xsensdeviceapi-<SDK version>-cp310-none-win_amd64.whl"`

### Moticon Insoles
The insoles transfer realtime data throught Moticon's proprietary OpenGo software/app. Install the OpenGo smartphone app and turn on streaming to receive all the data from it.

### HDFView
While not required, this lightweight tool is great for exploring HDF5 data.  The official download page is at https://www.hdfgroup.org/downloads/hdfview, and it can also be downloaded without an account from https://www.softpedia.com/get/Others/Miscellaneous/HDFView.shtml.

## Windows-specific Configuration
### Firewall
Set all used network interfaces on each Windows PC to private networks using `Set-NetConnectionProfile -InterfaceAlias <ALIAS> –NetworkCategory private`, replacing `<ALIAS>` with the user-friendly name used in the Network Adapter properties `Control Panel > Network and Internet > Network Connections`.

In `Windows Defender Firewall` main dashboard, choose `Windows Defender Firewall Properties`. Under `Private Profile > State > Protected Network Connections`, click `Customize` and deselect all network interfaces used in our data collection setup on that device. This will whitelist them to guarantee that devices are reachable and data can be exchanged, without disabling the Firewall.

Enable network discovery on both PCs on private networks through `File Explorer > Network > *Pop-up: Allow device discovery on private networks?`.

On the fixed PC and wearable PC, change security policies to enable remote desktop and enable remote desktop in its settings.

## Networking
### Mobile Router
The [Netgear MR450](https://www.netgear.com/be/home/mobile-wifi/hotspots/mr6450/) mobile 5G/LTE router (hotspot) is a neat high-throughput router that allows us to remote access our entire LAN + WLAN sensor network setup over the LTE network, anywhere in the world.

Any alternative device can be used. We recommend a WiFi6 router with high throughput to allow heavy data streams, like video cameras, to be seemlessly exchanged between devices on the local sensor network (e.g. stream of eye video data from the wearable PC to the lab PC).

#### Gateway IP Address
The router has a picky web-based setup console. To change the IP address of the router, under `Settings > Advanced > Mobile Router Setup`:
1. tick the DHCP server function
2. change router IP address to 192.168.69.1 and mask to 255.255.255.0
3. match the DHCP range to the new subnet (e.g. 192.168.69.30 in the starting field and 192.168.69.50 in the eding field) 
4. untick the DHCP server function if you want all devices on the network to have static IPs (we reserve 20 IPs for DHCP clients)

The firmware will refuse to change the IP address of the router otherwise, with the error `Please use an IP address from the DHCP range`, even if you are not using DHCP.

Enable Ethernet setting on the router to bridge WLAN and LAN interfaces, so that traffic to and from the lab PC can be offloaded onto the wired interface (if possible to wire the router to the lab PC).

<!-- #### Port Forwarding
For remote access over the Internet of our lab network we will run a VPN server on the Raspberry Pi 5, to be able to connect to an device on the lab network like `your device > public Internet > mobile router > VPN server > lab device`. Setup port forwarding on the router to forward traffic from its public WAN IP to the Raspberry Pi's internal network endpoint: under `Settings > Advanced > Port Forwarding`, tick  -->

### LANs and WLANs
For PoE camera network interfaces [turn off other protocols](https://docs.baslerweb.com/network-configuration-(gige-cameras)#changing-the-network-adapter-properties-windows) in the network settings and configure network adapters used for the cameras for better performance. On each used network interface in Windows, enable PTP Hardware Timestamping.

Configure wireless router to a 192.168.69.0/24 subnet and bridge LAN and WLAN connections on it to connect wired and wireless peers. Set static IPs on the fixed PC (192.168.69.100/24), wearable PC (192.168.69.101/24), and the Linux PTP + VPN server (192.168.69.99/24).

In Pylon Viewer configure IP addresses of cameras 192.168.70.101-104/24. They will form own subnet on the bridged wired connection between fixed PC, themselves and the Raspberry Pi PTP server.

On the raspberry Pi (Linux PTP server), set the ethernet interface (i.e. eth0) to 192.168.70.99/24. On some Pi's, the IP address doesn't change for some reason. If after address reassignment device is not pinggable, remove connection in the network settings and add it again through the GUI.

Ping devices on both subnets to verify all are reachable back and forth.

| AidWear(-2.4)     | Details |
| :---------------- | :---------------------------: |
| Type              | WiFi + LAN |
| Network           | 192.168.69.0/24 |
| Gateway           | 192.168.69.1 |
| Usable addresses  | 192.168.69.2 - 192.168.69.254 |
| DHCP range[^DHCP] | 192.168.69.30 - 192.168.69.49 |
| Services          | 192.168.69.90 - 192.168.69.99 |
| Sensing devices   | 192.168.69.100 - 192.168.69.254 |

[^DHCP]: reservation for WiFi clients using the [mobile hotspot](#mobile-router) for Internet access (e.g. mobile device of staff or participant).

| Cameras           | Details |
| :---------------- | :---------------------------: |
| Type              | PoE + LAN |
| Network           | 192.168.70.0/24 |
| Gateway           | N/A |
| Usable addresses  | 192.168.70.1 - 192.168.70.254 |
| Services          | 192.168.70.90 - 192.168.70.99 |
| Sensing devices   | 192.168.70.100 - 192.168.70.254 |

### Remote Desktop
Install [RustDesk](https://rustdesk.com/) on the fixed PC for easy GUI remote desktop access. Once connected from a remote machine, we can SSH from the fixed PC into any desired device on the LAN.

<!-- ### WireGuard VPN Server
We use the [PiVPN project](https://www.pivpn.io/) to create a VPN server that runs atop [WireGuard](https://www.wireguard.com/), the modern, open-source, secure and light-weight VPN that works across all platforms (operating systems) and processor architectures. 

Add routes to the table
<!-- TODO: installation and configuration steps TODO: ISP NAT workaround -->

### Synchronization
#### PTP Server
Run the Precision Time Protocol (PTP) service on the Raspberry Pi to serve the entire setup. We use the [LinuxPTP (ptp4l)](https://linuxptp.sourceforge.net/) implementation for this. 

To sync cameras and the fixed PC to the PTP server: 
  1. Bridge network interfaces on the fixed PC (PoE camera connections, and Ethernet connection to the Raspberry Pi). Set IPv4 address of the fixed PC on the bridge to 192.168.70.100/24.

To sync the wearable PC to the rest: 
  1. Bridge network interfaces on the fixed PC (Ethernet connection to the Raspberry Pi and Ethernet connection to the router). 
  The fixed PC will pass sync signals from the RPi PTP server through the bridge to the router and wirelessly to the wearable PC. **OR**
  2. Bridge network interfaces on the Raspberry Pi (Ethernet and WLAN adapters). **OR**
  3. Connect the PTP server to both, eth0 and wlan0 interfaces, without bridging the networks to avoid irrelevant rebroadcasts of data.
  The Raspberry Pi will offer the best sync quality to the wired connection of the fixed PC, and lesser quality sync over WLAN passed through the router to the wearable PC.

Setup PTP Windows client on the fixed PC and the wearable PC to sync to the Linux PTP grandmaster clock.

Turn off energy saving mode on the WLANs adapters to avoid buffering packets prior to waking up the interface, to produce more consistent (less jittery) network round trips.

# Running
Run relevant launcher script in the `launchers/` directory, adjust parameters for the experiment and the sensors as desired.

```bash
conda info --envs
conda env create -f environment.yml
conda list --revisions
conda install --rev REVNUM
conda env update --file environment.yml --prune
conda env export --from-history > environment.yml
conda remove --name myenv --all
```

Transcoding resulting 2K videos with the Tesla P4 GPU for a 10x compression.
```bash
ffmpeg -y -hwaccel cuda -hwaccel_output_format cuda -i cameras_40478064.mp4 -hwaccel cuda -hwaccel_output_format cuda -i cameras_40549960.mp4 -hwaccel cuda -hwaccel_output_format cuda -i cameras_40549975.mp4 -hwaccel cuda -hwaccel_output_format cuda -i cameras_40549976.mp4 -map 0:0 -vf scale_cuda=1920:1080 -c:v h264_nvenc -b:v 6M -preset p7 temp1.mp4 -map 1:0 -vf scale_cuda=1920:1080 -c:v h264_nvenc -b:v 6M -preset p7 temp2.mp4 -map 2:0 -vf scale_cuda=1920:1080 -c:v h264_nvenc -b:v 6M -preset p7 temp3.mp4 -map 3:0 -vf scale_cuda=1920:1080 -c:v h264_nvenc -b:v 6M -preset p7 temp4.mp4
```

Extract PTS from the recorded video.
```bash
ffprobe -loglevel error -select_streams v:0 -show_entries frame=pts -of csv=print_section=0 eye_eye-video-world.mkv > pts.txt
```

Install package from Git
```bash
python -m pip install -e SomeProject @ git+https://git.repo/some_pkg.git
```
