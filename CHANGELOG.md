# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- insertion marker -->
## [0.4.1](https://github.com/maximyudayev/hermes/releases/tag/0.4.1) - 2026-06-19

<small>[Compare with 0.4.0](https://github.com/maximyudayev/hermes/compare/0.4.0...0.4.1)</small>

### Bug Fixes

- Can't broadcast at ring buffer wrap around ([96e0b14](https://github.com/maximyudayev/hermes/commit/96e0b14cd2651c24066a0eba2200e589273a39d0) by Maxim Yudayev).

## [0.4.0](https://github.com/maximyudayev/hermes/releases/tag/0.4.0) - 2026-06-16

<small>[Compare with 0.3.0](https://github.com/maximyudayev/hermes/compare/0.3.0..0.4.0)</small>

### Features

- subproc `Storage` with shared mem `Stream`s ([ecedcb5](https://github.com/maximyudayev/hermes/commit/ecedcb521b2013e5710acdb1c299180ad9366700) by Maxim Yudayev). Resolves: maximyudayev/hermes#33

### Bug Fixes

- Pipelines send extra separator, crashing exit ([a36e895](https://github.com/maximyudayev/hermes/commit/a36e895fc716c5bf2c1e8a674ecdac6be129d3c4) by Maxim Yudayev).

## [0.3.0](https://github.com/maximyudayev/hermes/releases/tag/0.3.0) - 2026-05-05

<small>[Compare with 0.2.0](https://github.com/maximyudayev/hermes/compare/0.2.0..0.3.0)</small>

### Features
- Provides `logging_spec` in config YAML files individually for each `Node` to avoid writing same videos twice (e.g. in smartglasses node, and in AI node that processes the video) ([9bdc286](https://github.com/maximyudayev/hermes/commit/9bdc286593640c52a84ce7caf32e4bdac8fe7507) by Maxim Yudayev).
- Adds configurable PUB/SUB topics for Nodes to allow multiple instances of the same `Node` and avoid clashes at the PUB/SUB layer ([bbe2040](https://github.com/maximyudayev/hermes/commit/bbe20407989c16e231b64305b90ae7ce0368ca9c) by Maxim Yudayev).

### Bug Fixes
- Cross-coupled hosts with `Pipeline` nodes that consume each other's data rebroadcast the same data back and forth, scramble data in HDF5, and lock-up experiment termination ([22c6383](https://github.com/maximyudayev/hermes/commit/22c63830f2615b369d47d4c59e1c2f81ccf6e631) by Maxim Yudayev).

## [0.2.0](https://github.com/maximyudayev/hermes/releases/tag/0.2.0) - 2026-01-18

<small>[Compare with 0.1.8](https://github.com/maximyudayev/hermes/compare/0.1.8..0.2.0)</small>

### Features
- Centralized cross-platform auto-launching of HERMES across multiple remote host sensing devices in separate console windows ([27e3eec](https://github.com/maximyudayev/hermes/commit/27e3eecbdedcc3db1678dd9f2d322381112b3a00), [2af9e19](https://github.com/maximyudayev/hermes/commit/2af9e1978ea77891337a8cf9842d29fcb3f894ef) by Maxim Yudayev).

### Bug Fixes
- STDIN keyboard input fan-out thread doesn't terminate on program completion ([ba811e4](https://github.com/maximyudayev/hermes/commit/ba811e406e01af43ab527203d50472eb656c6852) by Maxim Yudayev).

## [0.1.8](https://github.com/maximyudayev/hermes/releases/tag/0.1.8) - 2025-12-31

<small>[Compare with 0.1.7](https://github.com/maximyudayev/hermes/compare/0.1.7..0.1.8)</small>

### Features

- `Pipeline` split into synchronous processing of incoming data and asynchronous generation of internal outgoing data ([d4c71f4](https://github.com/maximyudayev/hermes/commit/d4c71f49ee36920ef7e0a2ed374a50512e1340fc) by Maxim Yudayev).
- No cluttering periodic terminal input prompts ([53a3c78](https://github.com/maximyudayev/hermes/commit/53a3c78f9a4520849c4e3874f2140454b3b603bc) by Maxim Yudayev).

## [0.1.7](https://github.com/maximyudayev/hermes/releases/tag/0.1.7) - 2025-12-04

<small>[Compare with 0.1.6](https://github.com/maximyudayev/hermes/compare/0.1.6..0.1.7)</small>

### Bug Fixes
- `Broker` doesn't fan-out stdin in multiprocessing -> threading instead.

## [0.1.6](https://github.com/maximyudayev/hermes/releases/tag/0.1.6) - 2025-12-02

<small>[Compare with 0.1.5](https://github.com/maximyudayev/hermes/compare/0.1.5..0.1.6)</small>

### Bug Fixes
- `Broker` and `Storage` use stale clock reference.

## [0.1.5](https://github.com/maximyudayev/hermes/releases/tag/0.1.5) - 2025-12-02

<small>[Compare with 0.1.4](https://github.com/maximyudayev/hermes/compare/0.1.4..0.1.5)</small>

### Code Refactoring
- Replaced `keyboard` package in favor of cancellable daemon thread with `input()` calls, for rootless cross-platform keyboard interaction.

## [0.1.4](https://github.com/maximyudayev/hermes/releases/tag/0.1.4) - 2025-11-28

<small>[Compare with 0.1.3](https://github.com/maximyudayev/hermes/compare/0.1.3..0.1.4)</small>

### Features
- Propagates user keyboard inputs to all threads / `Node`s ([adf9539](https://github.com/maximyudayev/hermes/commit/adf9539796f5155a4435d1fab3bd4dd1e19315fc) by Maxim Yudayev).

## [0.1.3](https://github.com/maximyudayev/hermes/releases/tag/0.1.3) - 2025-11-25

<small>[Compare with 0.1.2](https://github.com/maximyudayev/hermes/compare/0.1.2..0.1.3)</small>

### Features
- Auto convert `video_image_format` YAML configuraiton into FFmpeg codec ([638c045](https://github.com/maximyudayev/hermes/commit/638c04524f5090be45b8af17ee02900d40e3ec86) by Maxim Yudayev).

### Bug Fixes
- Offset in reference time calculations ([8764a36](https://github.com/maximyudayev/hermes/commit/8764a361523dc69a8ad36d8b1809c0c89315a9d1) by Maxim Yudayev).

## [0.1.2](https://github.com/maximyudayev/hermes/releases/tag/0.1.2) - 2025-11-21

<small>[Compare with 0.1.1](https://github.com/maximyudayev/hermes/compare/0.1.1..0.1.2)</small>

### Bug Fixes
- Divergent reference system time across local subprocessed `Node`'s ([83fa178](https://github.com/maximyudayev/hermes/commit/83fa178224bbe06c27242e65c4ff4a90f95b4304) by Maxim Yudayev).

## [0.1.1](https://github.com/maximyudayev/hermes/releases/tag/0.1.1) - 2025-10-19

<small>[Compare with 0.1.0](https://github.com/maximyudayev/hermes/compare/0.1.0..0.1.1)</small>

### Features
- Added `hermes-cli` CLI executable with config-based setup.

### Bug Fixes
- Patched `hermes` modules structure to allow installable namespace packages like `hermes.dots`, `hermes.torch`, etc.

## [0.1.0](https://github.com/maximyudayev/hermes/releases/tag/0.1.0) - 2025-10-11

<small>[Compare with first commit](https://github.com/maximyudayev/hermes/compare/62d012960b15d6571da49b877035506c19446690..0.1.1)</small>

- Initial publically available version of the framework.
