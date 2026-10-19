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
- Paths to macOS `.app` bundles, which `start_application` resolves, are not handled yet.
