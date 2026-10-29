# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-29

### Added

- `launch()` takes a macOS `.app` bundle and launches the executable that the bundle's Info.plist names, as Qat's `start_application` does.
- The agent skill `qat`, which replaces qat-explore and qat-tests: remove those two when you install it (ADR 0005). Its SKILL.md covers driving an app to explore it, to check a change or to reproduce a bug, with screenshots as a step of their own and a criterion for when each kind of work is done, which build to drive, and the `objectName` an agent may add to the app. Its `references/` cover tests in a pytest suite, tests in a Qat suite (behave feature files or scripts), Qat's API beyond the essentials (the mouse, the keyboard, touch, item views, menus, native dialogs, method calls, signals and screenshots), and what an app needs on Windows, macOS and Linux, including app bundles, the hardened runtime, Qt 5.15 on Apple silicon, a distribution's newer Qt, and agent sandboxes. It also covers message boxes under KDE Plasma, which an app on the distribution's Qt shows twice, screenshots of a minimized Qt Quick window and on a scaled display, selection in Qt Quick lists, the main window and the registry of a new Qat suite, what Qat prints on Windows while it starts apps, the exit code of an app that does not find its DLLs, and objects from `qat.wait_for_object()`, which stop working once the object is hidden or deleted.

### Changed

- qat-agent-helpers requires Qat 1.9.0, which supports Qt 6.12, types text beyond ASCII, and lets a non-blocking click reach Qt Quick buttons on macOS.
- `type_text()` types any text that Qat can type, instead of refusing text beyond ASCII. Qat 1.9.0 types everything but characters beyond the Basic Multilingual Plane, such as emoji, into a Qt 5 app on Linux and macOS.
- A `LaunchError` names Qt 6.2-6.12 among the versions an app may use, and on macOS it no longer asks for a Release build: a Debug build connects as long as it loads Qt's release frameworks.
- The README and docs/library.md point to the skill's table of calls instead of repeating it.
- The library looks a definition up in Qat's current app instead of in the newest app it opened, so `qat.set_current_application_context()` applies to `snapshot()`, `click()` and the other calls too. When the current app is closed or detached, the newest open app becomes current, or no app is current when none is left, and closing another app leaves the current one alone. Without a current app the calls raise and list the open apps (ADR 0003).
- `click()` no longer raises `NotToggledError` for a checkable object without an indicator that is not a button, such as a `QGroupBox`, which toggles only on its title: the check now applies to controls with an indicator and to widget buttons.
- `snapshot()` walks the object tree lazily and stops at its size budget, instead of visiting every object first; the note at the cut no longer counts the objects left out.
- The Qat adapter now also answers what a Qat object proxy stands for and how long `wait_for_object()` waits, so no module but `real_qat.py` reads Qat's internals.
- `LaunchError` on macOS mentions the hardened runtime among what an app needs.
- On macOS, `launch()` refuses an app that Qat's server cannot be injected into because of the app's architecture, such as an arm64 app on Qt 5.15, before it launches the app. The `LaunchError` says what to do. Qat builds its Qt 5.15 server for x86_64 only, in 1.9.0 too; such an app used to run unconnected until Qat gave up after about 10 s with a message about build types.
- On Linux, `launch()` refuses an app on a Qt version that Qat has no server for, such as one newer than Qat supports, which a rolling distribution may ship, before it launches the app. The `LaunchError` names the QtCore the app loads and says how to build it with another Qt. Such an app used to run unconnected until Qat gave up after about 10 s with a message about build types.

### Removed

- `NonAsciiTextError`, since `type_text()` no longer refuses text beyond ASCII.
- The skills qat-explore and qat-tests, which the skill `qat` replaces.

### Fixed

- `click()`, `press_keys()`, `type_text()`, `snapshot()` and `definition_for()` refuse a row or cell of an item view with a `ValueError` that names Qat's own call to use, instead of failing with an `ObjectGoneError` about Qat's cache: Qat reaches those rows through a wrapper it makes for each request.
- `definition_for()` and the object lines in error messages find the same definition as `snapshot()`, including a container that has a container of its own and objects inside a Qt Quick window, whose content item Qat reports without a parent. They used to call an object ambiguous that the snapshot showed a unique definition for.
- `click()`, `press_keys()` and `type_text()` wait for a definition's container as they wait for the target, instead of failing at once with Qat's own `LookupError`, and look only inside visible and enabled containers, as `qat.wait_for_object()` does, so a hidden copy of a dialog no longer gets in the way. A container that matches several objects raises `AmbiguousDefinitionError`, which lists them.
- An error about an object that is destroyed while the error is being built keeps its type and message instead of turning into `ObjectGoneError`.
- `launch()` connects to an app whose `env` gives it a `TEMP` of its own. Qat's server leaves its port in the app's `TEMP`, and the library looked for it in the script's until it gave up after about 10 s with a `LaunchError` about the build.
- `App.detach()` releases an attached app that has already exited, as at the end of a `with qat_agent_helpers.attach(pid):` block, instead of raising Qat's `ConnectionAbortedError` and leaving Qat's own server open.
- `click()` judges a Qt Quick check box by its `checkState`, so a tristate one that goes from unchecked to partly checked, where `checked` stays false, no longer raises `NotToggledError`. Nor does a tristate Qt Widgets check box that goes from partly checked to checked, where `checked` stays true; Qt Widgets show no check state, so a click on one that was checked or partly checked is not verified.
- `snapshot(target)` shows the definition that `definition_for()` finds for a target that is unique only inside a container above it, where it showed none.

## [0.1.1] - 2026-10-19

### Fixed

- `click()` reaches Qt Quick buttons on macOS: it sends a non-blocking press and release instead of Qat's non-blocking `click`, which those buttons never received.

## [0.1.0] - 2026-10-19

### Added

- qat-agent-helpers, a helper library for agents' Qat scripts:
  - `launch()` and `attach()`, which return an `App` with `close()`, `detach()`, `context` and `pid`. Launches write no `applications.json`, and launched apps still open at exit are closed.
  - `snapshot()`, a compact object tree whose lines end with a definition to copy. It leaves out the containers of Qt's scroll bars unless `include_internal=True`.
  - `click()`, `press_keys()` and `type_text()`, which wait for their target and do not block on modal dialogs. A click on a check box aims at its indicator and checks that it toggled.
  - `definition_for()`, and errors that list every match of an ambiguous definition with its own definition.
  - The `launch_app` pytest fixture.
- The agent skills in `skills/`: qat-explore, for driving a running app from scripts, and qat-tests, for turning what was learned into pytest tests.

[Unreleased]: https://github.com/Palm1r/qat-agent-skills/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Palm1r/qat-agent-skills/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/Palm1r/qat-agent-skills/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Palm1r/qat-agent-skills/releases/tag/v0.1.0
