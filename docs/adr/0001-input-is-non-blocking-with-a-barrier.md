# Input is sent non-blocking, followed by a barrier

Mouse input, single keys and shortcuts are sent with Qat's `blocking=False`, which posts the events to the app. Each send is followed by a cheap barrier request (`versionInfo`). The app's GUI thread can only answer the barrier after it has processed the posted events, and it can do so from inside a modal dialog's nested event loop.

We avoid Qat's default blocking mode because there the reply waits for the event handler to finish. A click that opens a dialog with `exec()` then hangs (Qat issue #33), and the Qat client re-sends the request, which replays the click. The price is that we cannot tell when no widget accepted an event, because Qat's `check` only works in blocking mode.

## Consequences

- Typing text (`type_in`) stays blocking, because Qat has no non-blocking mode for it. Enter and other single keys go through the shortcut path instead.
- The barrier only covers the posted input events, not work their handlers defer (queued signals, timers, animations). Waiting for that is the script's job, through Qat's `wait_for_*` functions.
- State-changing commands are sent without the Qat client's automatic retries, using its internal `send_command(..., nb_trials=1)`, because a retried click or method call runs twice. This relies on Qat internals. The exact version pin keeps that dependency in check, and moving to a new Qat version needs a run against a real app.
