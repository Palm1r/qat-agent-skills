# Apps are launched with Qat's parts, not with start_application

`launch()` starts the executable with its own `subprocess.Popen` and then runs Qat's own steps:
- `app_launcher.inject_dll` on Windows; on Linux and macOS the injector is preloaded through `LD_PRELOAD` or `DYLD_INSERT_LIBRARIES`, as Qat does;
- `app_launcher.connect_to`;
- `debug_operations.lock_application`, when `lock_ui=True`.

It neither registers the app in a Qat registry nor calls `qat.start_application`.

Qat 1.8.1's `start_application` has three problems for this library:
- It takes the app's environment from `os.environ` only, so passing `launch()`'s `env` would mean changing the environment of the whole script.
- On Windows it builds a command line that leaves the executable path unquoted whenever there are arguments, so paths with spaces break.
- After a failure it waits up to 10 s more for the app's port file and launches the app a second time, which puts a second window in front of the user.

## Considered Options

- `start_application` with a private registry, `env` passed through a temporary change to `os.environ`, and paths with spaces refused when arguments are given. Rejected: it changes the environment of the whole process, restricts what can be launched, and keeps the second launch.

## Consequences

- The library sets the fields that `ApplicationContext.launch()` would set: `_internal.process`, `_internal.has_ownership` and `pid`. This relies on Qat internals. The exact version pin keeps that dependency in check, and moving to a new Qat version needs a run against a real app.
- No `applications.json` is written. The library never touches Qat's registry or `testSettings.json`, which belong to the script.
- The app gets its stdin from the null device and shares the script's stdout and stderr.
- A launch runs once: the injector has 20 s, and Qat's own waits for the port file and the handshake follow.
- Paths to macOS `.app` bundles are resolved as `start_application` resolves them: to the executable in `Contents/MacOS` that the bundle's `Info.plist` names, or else the one named after the bundle.
- On macOS, the injector loads Qat's server for the app's Qt version, and a dylib loads only into a process of an architecture it was built for. When the server cannot load, the injector only prints why, and the app runs on unconnected until Qat's waits give up. So before a launch, the library reads the Mach-O headers of the app and of that server, and refuses the app with the reason when the architecture it would run as is missing from the server: Qat 1.8.1 builds its Qt 5.15 server for x86_64 only. The headers are read in Python, so no Xcode tools are needed. The check refuses only a certain mismatch; when the app's architecture, its Qt version or the server cannot be told, the launch goes ahead.
- On Linux, the injector loads Qat's server for the app's Qt version, and Qat 1.8.1 has servers for Qt 5.15 and 6.2-6.11 only, while rolling distributions ship newer ones. When there is no server for the app's Qt, the injector only prints that it is missing, and the app runs on unconnected until Qat's waits give up. So before a launch, the library asks `ldd`, with the app's environment, which QtCore the app would load, reads the Qt version from the name of the file that library's links lead to, such as `libQt6Core.so.6.12.0`, and refuses the app with the reason when Qat has no server for that version. The check refuses only a certain gap; when `ldd` cannot run, finds no QtCore, or the file name has no version, the launch goes ahead.
