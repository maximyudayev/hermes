# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- insertion marker -->
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
