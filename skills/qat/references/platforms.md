# What an app needs, and how to launch it

Qat injects its server into the app as the app starts. The script then talks to that server over TCP on localhost in both directions: the script connects to the app's server, and the app connects back to a port the script opens.

## What an app needs

Every app needs Qt 5.15 or 6.2–6.12, linked dynamically, and a visible top-level window. Per platform:

- **Windows:** the app is built with MSVC, as a Release or RelWithDebInfo build: a Debug build loads Qt's debug DLLs, which Qat's server cannot share. The app has to find its Qt DLLs when Qat launches it: deploy them next to it with `windeployqt`, or put Qt's `bin` folder on `PATH` for it through `launch(path, env={"PATH": ...})`.
- **macOS:** Qat injects itself through `DYLD_INSERT_LIBRARIES`, which an app signed with the hardened runtime ignores, so drive a local build without it. On Apple silicon, Qat's server for Qt 5.15 is built for x86_64 only: build a Qt 5.15 app for x86_64 and run it under Rosetta; `launch()` refuses an arm64 app on Qt 5.15 and says so. A Debug build connects as long as it loads Qt's release frameworks, as builds against the Qt online installer do. `otool -L` on the executable shows which Qt it links.
- **Linux:** Qat injects itself through `LD_PRELOAD`, and apps can be driven on X11 and on Wayland alike, with no `QT_QPA_PLATFORM` needed. A distribution may ship a Qt newer than Qat supports, and CMake builds against it unless `CMAKE_PREFIX_PATH` points at another Qt, such as `~/Qt/6.12.0/gcc_64` from the Qt online installer. `launch()` refuses an app on a Qt that Qat has no server for, and names it. `ldd` on the executable shows which Qt it loads. Under KDE Plasma, an app on the distribution's Qt loads Plasma's platform theme, which shows message boxes through copies of its own; `launch(path, env={"QT_QPA_PLATFORMTHEME": "generic"})` keeps Qt's own, as SKILL.md's pitfalls say. An app on a Qt from the online installer does not load that theme.

## A build for Qat

When the user's build cannot connect, such as a Debug build on Windows, configure a second build directory and leave theirs as it is:

```bash
cmake -S . -B build-qat -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_PREFIX_PATH=/path/to/Qt
cmake --build build-qat --config RelWithDebInfo
```

`CMAKE_BUILD_TYPE` picks the configuration for Ninja and Makefiles, and `--config` for a multi-configuration generator such as Visual Studio's. On Windows, point `CMAKE_PREFIX_PATH` at an MSVC kit of Qt, such as `msvc2022_64`, not at a MinGW one. With another build system, build its release configuration into a directory of its own.

## When a launch fails

`launch()` raises a `LaunchError` that gives the reason. The usual causes:
- on Windows, a Debug build, for which Qat prints "Could not find qVersion function", or an app built with MinGW, for which it prints "Failed to load Qat server": the launch fails when Qat gives up waiting, after about 10 s;
- on macOS, the hardened runtime, or an arm64 app on Qt 5.15;
- a Qt that Qat has no server for, such as one newer than 6.12: on Linux `launch()` names it at once, while on Windows and macOS the launch fails when Qat gives up waiting, after about 10 s;
- an app that exits before Qat connects, for example over wrong arguments or a file it cannot find: the error gives its exit code. On Windows, 3221225781 (0xC0000135) means that a DLL it needs was not found, usually one of Qt's: deploy them or put them on `PATH`, as [What an app needs](#what-an-app-needs) says;
- no visible top-level window, such as an app that starts hidden in the system tray;
- an agent sandbox, such as Codex's on macOS, where the app cannot reach the window server and exits at once with code -6;
- an antivirus or a firewall that blocks the injection or the connection on localhost.

On Linux and macOS, `attach(pid)` works only for an app that Qat launched, since Qat injects itself there as the app starts.

## Agent sandboxes

A sandbox may block the connection on localhost. What the agents' documentation said on 2026-10-28:
- **Claude Code:** its sandbox is off by default, and scripts work as they are on Windows, macOS and Linux. With the sandbox on, a sandboxed command on macOS reaches localhost only with `sandbox.network.allowLocalBinding` set to `true`, and on Linux it has a `localhost` of its own; list the command in `excludedCommands` to run it outside the sandbox.
- **Codex:** run the scripts and tests outside its sandbox, by asking to run the command outside it, which the user approves, or with full access for the session. On macOS its sandbox keeps a command away from the window server, so an app launched inside it aborts at once with exit code -6, whatever the network settings; without network, the script cannot even open its own port.
- **Cursor:** its sandbox blocks `127.x` and `::1`, so run the scripts outside it: its agent asks for full permissions for the command, which the user approves.

Of these, Claude Code without its sandbox, Codex 0.165's sandbox on macOS, and Cursor's agent outside its sandbox have been tried with Qat; the rest comes from the agents' documentation.
