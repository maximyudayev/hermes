# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## HERMES

### 0.1.8 <small>December 31, 2025</small>
- Feature: `Pipeline` split into synchronous processing of incoming data and asynchronous generation of internal outgoing data.

### 0.1.7 <small>December 04, 2025</small>
- Bugfix: `Broker` doesn't fan-out stdin in multiprocessing -> threading instead.

### 0.1.6 <small>December 02, 2025</small>
- Bugfix: `Broker` and `Storage` use stale reference clock.

### 0.1.5 <small>December 02, 2025</small>
- Replaced `keyboard` package with `input()` calls for rootless keyboard interaction.

### 0.1.4 <small>November 28, 2025</small>
- Propagates user keyboard inputs via `keyboard` package to all threads.

### 0.1.3 <small>November 25, 2025</small>
- Automatic parsing of Video codec from config file.

### 0.1.2 <small>November 21, 2025</small>
- Bugfix: divergent reference system start time.

### 0.1.1 <small>October 19, 2025</small>
- Patched namespace build.
- Added CLI with config-based setup.

### 0.1.0 <small>October 11, 2025</small>
- Initial publically available version of the framework.
