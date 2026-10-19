# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- qat-agent-helpers, a helper library for agents' Qat scripts:
  - `launch()` and `attach()`, which return an `App` with `close()`, `detach()`, `context` and `pid`. Launches write no `applications.json`, and launched apps still open at exit are closed.
  - `snapshot()`, a compact object tree whose lines end with a definition to copy. It leaves out the containers of Qt's scroll bars unless `include_internal=True`.
  - `click()`, `press_keys()` and `type_text()`, which wait for their target and do not block on modal dialogs. A click on a check box aims at its indicator and checks that it toggled.
  - `definition_for()`, and errors that list every match of an ambiguous definition with its own definition.
  - The `launch_app` pytest fixture.
- The agent skills in `skills/`: qat-explore, for driving a running app from scripts, and qat-tests, for turning what was learned into pytest tests.
