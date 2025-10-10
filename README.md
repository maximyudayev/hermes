<h1 align="center">
  <img src="https://raw.githubusercontent.com/maximyudayev/hermes/refs/heads/main/images/logo.png" alt="HERMES: Heterogeneous Edge Realtime Measurement and Execution System" width="60%">

  <br>
  Heterogeneous Edge Realtime Measurement and Execution System
</h1>

<h4 align="center">A Unified Open-Source Framework for Realtime Multimodal Physiological Sensing, Edge AI, and Intervention in Closed-Loop Smart Healthcare Applications
</h4>

<div align="center">

  ![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
  ![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
  ![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)

</div>

<p align="center">
  <a href="#installation">Quickstart</a> •
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
This project is licensed under the MIT license - see the [LICENSE](/LICENSE) file for details.

# Citation
When using in your project, research, or product, please cite the following and notify us so we can update the index of success stories enabled by HERMES.

<!-- <a href="https://arxiv.org/abs/..." style="display:inline-block;">
  <img src="http://img.shields.io/badge/paper-arxiv.x-B31B1B.svg" height="20" >
</a>
```bibtex
@inproceedings{yudayev2025hermes,
  title={HERMES: A Unified Open-Source Framework for Realtime Multimodal Physiological Sensing, Edge AI, and Intervention in Closed-Loop Smart Healthcare Applications},
  author={Yudayev, Maxim and Carlon, Juha and Lamsal, Diwas and Vanrumste, Bart, and Filtjens, Benjamin},
  booktitle={},
  year={2025}
}
``` -->

# Acknowledgement
This project was primarily written by Maxim Yudayev while at the Department of Electrical Engineering, KU Leuven.

This study was funded, in part, by the AidWear project funded by the Federal Public Service for Policy and Support, 
the AID-FOG project by the Michael J. Fox Foundation for Parkinson’s Research under Grant No.: MJFF-024628, 
and the Flemish Government under the Flanders AI Research Program (FAIR).

HERMES is a "Ship of Theseus"[[1](https://en.wikipedia.org/wiki/Ship_of_Theseus)] of [ActionSense](https://github.com/delpreto/ActionNet) that started as a fork and became a complete architectural rewrite of the system from the ground up to bridge the fundamental gaps in the state-of-the-art, and to match our research group's needs in realtime deployments and reliable data acquisition.
Although there is no part of ActionSense in HERMES, we believe that its authors deserve recognition as inspiration for our system.

Special thanks for contributions, usage, bug reports, good times, and feature requests to Juha Carlon (KU Leuven), Stefano Nuzzo (VUB), Diwas Lamsal (KU Leuven), Vayalet Stefanova (KU Leuven), Léonore Foguenne (ULiège).
