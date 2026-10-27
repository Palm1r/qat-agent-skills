# The current app is Qat's, and the library reads it

Qat's own functions act on Qat's current application context, and agents mix them with qat-agent-helpers calls in every script, so a definition given to the library is looked up in the app that `qat.current_application_context()` names. The library keeps no current app of its own: `launch()` and `attach()` make the new app current through Qat, as `qat.start_application()` does, and a switch made with `qat.set_current_application_context()` applies to the library's functions too. When the library closes or detaches the current app, the newest app still open becomes current, or no app is current when none is left; closing another app leaves the current one alone.

## Considered Options

- The library owns the current app: the newest app in its own list, with a switch of its own, pushed into Qat on every change. Rejected: Qat's functions and `QtObject`'s fallback for a lost context read Qat's state, so a switch made with Qat's function left the two apart, which is what happened before this decision.

## Consequences

- The library depends on `qat.current_application_context()` and `qat.set_current_application_context()`, both public.
- Naming a successor is the library's addition: Qat itself leaves no current app after `close_application()`. The successor is named only when the closed app was current.
- Only the library changes the current app when it closes or detaches one: the Qat adapter's kill and detach leave the current app as it is, and the library then names the successor, or leaves no app current. The whole rule thus lives in one module, where the unit tests see all of it.
- An app that Qat started itself and that is current is adopted: the library's functions work on it, but the library never closes it.
- Without a current app, the library's functions raise and name the open apps, instead of falling back to one of them.
