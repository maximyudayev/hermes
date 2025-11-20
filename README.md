<h1 align="center">
  <picture>
    <!-- Source for dark mode -->
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/maximyudayev/hermes/refs/heads/main/images/logo_dark.png" media="(width = 60%)">
    <!-- Fallback image for light mode and other clients -->
    <img src="https://raw.githubusercontent.com/maximyudayev/hermes/refs/heads/main/images/logo.png" alt="HERMES: Heterogeneous Edge Realtime Measurement and Execution System" width="60%">
  </picture>

  <br>
  Heterogeneous Edge Realtime Measurement and Execution System
</h1>

<h4 align="center">A Unified Open-Source Framework for Realtime Multimodal Physiological Sensing, Edge AI, and Intervention in Closed-Loop Smart Healthcare Applications
</h4>

<div align="center">

  [![Windows](https://img.shields.io/badge/Windows-%230078D6.svg?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB2aWV3Qm94PSIwIDAgODggODgiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgaGVpZ2h0PSI4OCIgd2lkdGg9Ijg4Ij4NCjxwYXRoIGQ9Im0wIDEyLjQwMiAzNS42ODctNC44Ni4wMTYgMzQuNDIzLTM1LjY3LjIwM3ptMzUuNjcgMzMuNTI5LjAyOCAzNC40NTNMLjAyOCA3NS40OC4wMjYgNDUuN3ptNC4zMjYtMzkuMDI1TDg3LjMxNCAwdjQxLjUyN2wtNDcuMzE4LjM3NnptNDcuMzI5IDM5LjM0OS0uMDExIDQxLjM0LTQ3LjMxOC02LjY3OC0uMDY2LTM0LjczOXoiIHN0eWxlPSJvcGFjaXR5OjE7ZmlsbDojZmZmZmZmO2ZpbGwtb3BhY2l0eToxO3N0cm9rZS13aWR0aDoxIj48L3BhdGg+DQo8L3N2Zz4=)](#)
  [![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](#)
  [![macOS](https://img.shields.io/badge/mac%20os-%23000000.svg?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbDpzcGFjZT0icHJlc2VydmUiIHdpZHRoPSI4MTQiIGhlaWdodD0iMTAwMCI+CjxwYXRoIGQ9Ik03ODguMSAzNDAuOWMtNS44IDQuNS0xMDguMiA2Mi4yLTEwOC4yIDE5MC41IDAgMTQ4LjQgMTMwLjMgMjAwLjkgMTM0LjIgMjAyLjItLjYgMy4yLTIwLjcgNzEuOS02OC43IDE0MS45LTQyLjggNjEuNi04Ny41IDEyMy4xLTE1NS41IDEyMy4xcy04NS41LTM5LjUtMTY0LTM5LjVjLTc2LjUgMC0xMDMuNyA0MC44LTE2NS45IDQwLjhzLTEwNS42LTU3LTE1NS41LTEyN0M0Ni43IDc5MC43IDAgNjYzIDAgNTQxLjhjMC0xOTQuNCAxMjYuNC0yOTcuNSAyNTAuOC0yOTcuNSA2Ni4xIDAgMTIxLjIgNDMuNCAxNjIuNyA0My40IDM5LjUgMCAxMDEuMS00NiAxNzYuMy00NiAyOC41IDAgMTMwLjkgMi42IDE5OC4zIDk5LjJ6bS0yMzQtMTgxLjVjMzEuMS0zNi45IDUzLjEtODguMSA1My4xLTEzOS4zIDAtNy4xLS42LTE0LjMtMS45LTIwLjEtNTAuNiAxLjktMTEwLjggMzMuNy0xNDcuMSA3NS44LTI4LjUgMzIuNC01NS4xIDgzLjYtNTUuMSAxMzUuNSAwIDcuOCAxLjMgMTUuNiAxLjkgMTguMSAzLjIuNiA4LjQgMS4zIDEzLjYgMS4zIDQ1LjQgMCAxMDIuNS0zMC40IDEzNS41LTcxLjN6IiBzdHlsZT0ib3BhY2l0eToxO2ZpbGw6I2ZmZmZmZjtmaWxsLW9wYWNpdHk6MTtzdHJva2Utd2lkdGg6MSIvPgo8L3N2Zz4=)](#)

</div>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="https://maximyudayev.github.io/hermes">Docs</a> •
  <a href="#data-annotation">GUI</a> •
  <a href="#showcase">Showcase</a> •
  <a href="#citation">Cite</a> •
  <a href="#contact">Contact</a>
</p>

HERMES for the Greek mythology analogy of the god of communication and speed, protector of information, the gods' herald. He embodies the nature of smooth and reliable communication. His role accurately resonates with the vision of this framework: facilitate reliable and fast exchange of continuously generated multimodal physiological and external data across distributed wireless and wired multi-sensor hosts for synchronized realtime data collection, in-the-loop AI stream processing, and analysis, in intelligent med- and health-tech (wearable) applications.

<br>
<div align="center"><img src="https://raw.githubusercontent.com/maximyudayev/hermes/refs/heads/main/images/overview.png" alt="Overview of the system architecture on one of the distributed hosts" width="80%"></div>
<br>

HERMES offers out-of-the-box streaming integrations to a number of commercial sensor devices and systems, high resolution cameras, templates for extension with custom user devices, and a ready-made wrapper for easy PyTorch AI model insertion. It reliably and synchronously captures heterogeneous data across distributed interconnected devices on a local network in a continuous manner, and enables realtime AI processing at the edge toward personalized intelligent closed-loop interventions of the user. All continuously acquired data is periodically flushed to disk for as long as the system has disk space, as MKV/MP4 and HDF5 files, for video and sensor data, respectively.

# Quickstart
## Core
Create a Python 3 virtual environment `python -m venv .venv` (python >= 3.7).

Activate it with `.venv/bin/activate` for Linux or `.venv\Scripts\activate` for Windows.

Single-command install HERMES into your project along other dependendices. 
```bash
pip install pysio-hermes
```

## Extra
All the integrated, validated and supported sensor devices are separately installable as `pysio-hermes-<subpackage_name>`, like:
```bash
pip install pysio-hermes-torch
```
Will install the AI processing subpackage to wrap user-specified PyTorch models.

<details>
  <summary>List of supported devices <i>(continuously updated)</i></summary>
Some subpackages require OEM software installation, check each below for detailed prerequisites.

- `torch` [Wrapper for PyTorch AI models](https://github.com/maximyudayev/hermes-torch)
- `pupillabs` [Pupil Labs Core smartglasses](https://github.com/maximyudayev/hermes-pupillabs)
- `basler` [Basler cameras](https://github.com/maximyudayev/hermes-basler)
- `dots` [Movella DOTs IMUs](https://github.com/maximyudayev/hermes-dots)
- `mvn` [Xsens MVN Analyze MoCap suit](https://github.com/maximyudayev/hermes-mvn)
- `awinda` [Xsens Awinda IMUs](https://github.com/maximyudayev/hermes-awinda)
- `cometa` [Cometa WavePlus sEMG](https://github.com/maximyudayev/hermes-cometa)
- `moticon` [Moticon OpenGo pressure insoles](https://github.com/maximyudayev/hermes-moticon)
- `tmsi` [TMSi SAGA physiological signals](https://github.com/maximyudayev/hermes-tmsi)
- `vicon` [Vicon Nexus capture system](https://github.com/maximyudayev/hermes-vicon)
- `moxy` [Moxy muscle oxygenation monitor](https://github.com/maximyudayev/hermes-moxy)

The following subpackages are in development.
- `gui` [Live monitoring dashboard](https://github.com/maximyudayev/hermes-gui)
- `mic` [PC-attached generic microphone](https://github.com/maximyudayev/hermes-mic)

</details>
<br>

### FFmpeg (Optional)
If dealing with video or audio, you will have to install [FFmpeg](https://ffmpeg.org/).

Make a copy of the `examples/video_codec_<type>.yml`, that matches your video encoding hardware (AMD or Intel CPU, or an NVIDIA GPU), as `examples/video_codec.yml`

#### Windows
1. Download the full build with shared libraries from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full-shared.7z).
1. Unpack the archive into the desired folder, like `C:\Program Files\ffmpeg`.
1. Add path to the FFmpeg binaries to the `Path` environment variable manually, or via CMD. 
   ```powershell
   SETX PATH "%PATH%;C:\Program Files\ffmpeg\bin;C:\Program Files\ffmpeg" /M
   ```
1. Open a new terminal window and check that FFmpeg can be correctly found by the system `where ffmpeg`.

#### Linux
1. Install with the package manager `sudo apt-get install ffmpeg`.
1. Check that ffmpeg is on path `which ffmpeg`.

## Running
The system runs based on YAML configuration files, where connection to other hosts, and local or remote [Producer](https://maximyudayev.github.io/hermes/api/nodes/producer/)'s, [Consumer](https://maximyudayev.github.io/hermes/api/nodes/consumer/)'s, [Pipeline](https://maximyudayev.github.io/hermes/api/nodes/pipeline/)'s.

## Benchmarking
### Latency
1. Install Plotly into the current virtual environment `pip install plotly`.
1. On each host device, run the latency evaluation automated script under `test/`:
   ```bash
   cd test
   ```
   as `test_latency.bat` for Windows or `. test_latency.sh` for Linux.
1. Gather generated text files from all tested devices and place in `test/data/latency/<device_name>` subfolders in the following structure. The folder name will be used as the trace name of the corresponding series.
   ```bash
   root/
   └───test
       └───data
           └───latency
               ├───laptop
               │   ├───latency_vs_frequency.txt
               │   └───latency_vs_msgsize.txt
               ├───nuc
               ├───pi
               └───server
   ```
1. Visualize latencies by running `plot_latency.bat` for Windows or `. plot_latency.sh` for Linux:

<p align="center">
  <img src="https://raw.githubusercontent.com/maximyudayev/hermes/refs/heads/main/images/latency_freq.png" alt="Latency vs sampling frequency" width="45%" />
  <img src="https://raw.githubusercontent.com/maximyudayev/hermes/refs/heads/main/images/latency_msgsize.png" alt="Latency vs message size" width="45%" />
</p>

# Documentation
Check out the [full documentation site](https://maximyudayev.github.io/hermes) for more usage examples, architecture overview, detailed extension guide, and FAQs.

# Data Annotation
<br>
<div align="center"><img src="https://raw.githubusercontent.com/maximyudayev/hermes/refs/heads/main/images/gui.png" alt="Pysioviz: A dashboard for visualization and annotation of collected multimodal data for AI workflows" width="80%"></div>
<br>

We developed [PysioViz](https://github.com/maximyudayev/pysioviz) a complementary dashboard based on [Dash Plotly](https://dash.plotly.com/) for analysis and annotation of the collected multimodal data. We use it ourselves to generate ground truth labels for the AI training workflows. Check it out and leave feedback!

# Showcase
These are some of our own projects enabled by HERMES to excite you to adopt it in your smart closed-looop healthtech usecases.

<details>
  <summary>AI-enabled intent prediction for high-level locomotion mode selection in a smart leg prosthesis</summary>
</details>
<br>

<details>
  <summary>Realtime automated cueing for freezing-of-gait Parkinson's patients in free-living conditions</summary>
</details>
<br>

<details>
  <summary>Personalized level of assistance in prolong use rehabilitation and support exoskeletons</summary>
</details>
<br>

# License
This sourcecode is licensed under the MIT license - see the [LICENSE](https://github.com/maximyudayev/hermes/blob/main/LICENSE) file for details.

The project's logo is distributed under the CC BY-NC-ND 4.0 license  - see the [LOGO-LICENSE](https://github.com/maximyudayev/hermes/blob/main/LOGO_LICENSE.md).

# Citation
When using in your project, research, or product, please cite the following and notify us so we can update the index of success stories enabled by HERMES.

<!-- <a href="https://arxiv.org/abs/..." style="display:inline-block;">
  <img src="http://img.shields.io/badge/paper-arxiv.x-B31B1B.svg" height="20" >
</a>
```bibtex
@inproceedings{yudayev2025hermes,
  title={HERMES: A Unified Open-Source Framework for Realtime Multimodal Physiological Sensing, Edge AI, and Intervention in Closed-Loop Smart Healthcare Applications},
  author={Yudayev, Maxim and Carlon, Juha and Lamsal, Diwas and Stefanova, Vayalet and Vanrumste, Bart, and Filtjens, Benjamin},
  booktitle={},
  year={2025}
}
``` -->

# Acknowledgement
This project was primarily written by Maxim Yudayev while at the Department of Electrical Engineering, KU Leuven.

This study was funded, in part, by the AidWear project funded by the Federal Public Service for Policy and Support, 
the AID-FOG project by the Michael J. Fox Foundation for Parkinson’s Research under Grant No.: MJFF-024628, 
the strategic basic research project RevalExo (S001024N) funded by the Research Foundation Flanders, 
and the Flemish Government under the Flanders AI Research Program (FAIR).

HERMES is a "Ship of Theseus"[[1](https://en.wikipedia.org/wiki/Ship_of_Theseus)] of [ActionSense](https://github.com/delpreto/ActionNet) that started as a fork and became a complete architectural rewrite of the system from the ground up to bridge the fundamental gaps in the state-of-the-art, and to match our research group's needs in realtime deployments and reliable data acquisition.
Although there is no part of ActionSense in HERMES, we believe that its authors deserve recognition as inspiration for our system.

Special thanks for contributions, usage, bug reports, good times, and feature requests to [Juha Carlon](https://www.linkedin.com/in/juha-carlon-8aa41122b) (KU Leuven), [Vayalet Stefanova](https://www.linkedin.com/in/vayalet-stefanova-9208b2174/) (KU Leuven), [Diwas Lamsal](https://www.linkedin.com/in/diwaslamsal123) (KU Leuven), [Stefano Nuzzo](https://www.linkedin.com/in/stefano-nuzzo-69648b20b) (VUB), [Léonore Foguenne](https://www.linkedin.com/in/l%C3%A9onore-foguenne-293243234/) (ULiège).
