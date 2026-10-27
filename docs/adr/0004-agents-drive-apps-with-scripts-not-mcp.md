# Agents drive apps with scripts that a skill teaches, not through an MCP server

Agents reach Qat through a skill that teaches them to write Python scripts on Qat and qat-agent-helpers, not through an MCP server with a tool per action. A script runs a whole scenario in one tool call where an MCP server needs a model turn per action; the script is already a draft of the test, which is the project's second goal; and the value lay in getting around Qat's weak spots, which a library does without a server.

On 2026-10-18 the same six-step scenario on the demo bench's `demo-widgets` was run by a fresh Claude Code agent per variant, each ending with a test:

| | A: MCP server (FastMCP) | B: scripts on bare Qat | C: qat-agent-helpers and the skill |
|---|---|---|---|
| Time to the finished test | about 7 min | 5 min 40 s | 4 min 33 s |
| Tool calls | 49, 24 of them Qat tools | 25 | 24 |
| Conversation tokens | about 65k, counted at the report | about 48k | about 41k |
| Failed runs | none | 1, the check box | 0 |
| Test passed on its first run | no: a bug in our server, a Qat call without `blocking=False` | yes | yes |
| Modal dialog | no hang | no hang: the agent found `blocking=False` in Qat's docstrings | no hang: the library handles it |
| Check box | missed, while the tool reported success | missed; the script timed out and the agent fixed it | hit at once |
| Read Qat's sources | yes, to write the test | yes, the whole API | hardly: the skill was enough |

- The main argument for MCP did not hold. It was that without a server an agent would have to know Qat, but agent B learned Qat's API from the installed package's docstrings in a couple of minutes.
- An MCP server is a product of its own to maintain: protocol revisions, Cursor CLI's limit of 60 s per call, clients that treat `structuredContent` differently, open bugs of Claude Code with FastMCP 4, and tool schemas in every request of a client that does not load them on demand.

## Consequences

- Each variant ran once, and A's tokens were counted later than B's and C's. A's failed test and its false success on the check box came from bugs in our server, not from MCP: an MCP layer over qat-agent-helpers would share the library's checks. The decision rests on the turns per action, on scripts becoming tests and on maintenance, not on the margins.
- Claude Code loads MCP tool schemas only when they are needed, so their cost in context matters little there. The turns per action and the results that pass through the model remain.
- Two cases were not covered, and neither is verified:
  - Agent sandboxes wrap shell commands, so they can keep a script and its app from talking over localhost, while Claude Code runs MCP servers outside its sandbox. As their docs said on 2026-10-28: Claude Code's sandbox is off by default, and when it is on, a sandboxed command on macOS reaches localhost only with `sandbox.network.allowLocalBinding`, while on Linux its `localhost` is private to it; Codex runs without network by default, and with its network proxy it blocks loopback unless `allow_local_binding` is set; Cursor's sandbox blocks `127.x` and `::1`. Tried on 2026-10-28 with Codex 0.165 on macOS: inside its sandbox the app cannot even reach the window server and aborts at once, whatever the network settings, so each script there runs outside the sandbox on the user's approval.
  - A long exploration deep inside an app makes every script walk the whole path again. On Linux and macOS, Qat attaches to any process that loaded its injector, which `launch()` preloads, so a mode that leaves the app running between scripts might cover this without a server. The app would need a log file of its own, since it shares the script's stdout.
- The way back is a thin MCP layer over qat-agent-helpers; the server code of variant A is kept in qat-mcp under the tag `mcp-paused`. A tool per action would bring back the turn cost, so a tool that runs a script in a live session is the better shape, at the price of running any code outside the agent's sandbox.
- If Qat ships an MCP server of its own, as its issue #49 proposes, the maintenance would move upstream, but the turn cost would remain.
- Others who weighed the same trade-off came down on the same side for coding agents and kept MCP for agent loops that need persistent state: Anthropic's [code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp), Playwright's [CLI for coding agents](https://playwright.dev/docs/getting-started-cli) and Armin Ronacher's [code-running MCP tool](https://lucumr.pocoo.org/2025/8/18/code-mcps/).
