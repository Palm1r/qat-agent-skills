# qat-agent-skills

Agent skills and a Python helper library, qat-agent-helpers, that let AI agents drive running Qt applications with Qat scripts and write Qat tests. The project is community-made and not part of the Qat project.

## Language

### Actors

**Qat**:
The Qt Application Tester (gitlab.com/testing-tool/qat): the external test-automation tool that agents script and qat-agent-helpers smooths over.
_Avoid_: QAT (that is Intel QuickAssist), Qt Test

**Agent**:
The AI model that writes and runs scripts with Qat and qat-agent-helpers, inside a coding assistant such as Claude Code, Cursor or Codex.
_Avoid_: user (that is the human), bot, client

**Drive**:
To operate a running app from a script: look at its UI, click, type, read properties and take screenshots. Driving is the first goal; writing Qat tests from what was learned while driving is the second.
_Avoid_: automate, test (when no test is being written)

**Skill**:
The packaged instructions, a folder with a SKILL.md, that teach an agent to work with Qt apps through Qat and qat-agent-helpers. There are two: qat-explore for driving a running app, and qat-tests for turning what was learned into pytest tests.
_Avoid_: prompt, rules, plugin (a plugin is only one way to ship a skill)

### Apps

**App**:
A running Qt process that a script controls through Qat, either launched or attached.
_Avoid_: application context, session, process (when the control relationship matters)

**Launch**:
To start an app from an executable path so that the script owns it: the app is closed when the script closes it or exits.
_Avoid_: start, run, spawn

**Attach**:
To take control of a Qt process that is already running, identified by its PID. qat-agent-helpers only ever detaches from an attached app and never closes it.
_Avoid_: connect, hook, inject

**Current app**:
The app that Qat's own functions act on. qat-agent-helpers makes the newest app it launched or attached to the current one.
_Avoid_: active app, default app

**Qat adapter**:
The seam through which qat-agent-helpers reaches Qat: launching an app and, per app, listing windows, children and properties, finding objects, and quitting or killing it. The real adapter uses the qat package; unit tests use a fake one, so they need no Qt.
_Avoid_: driver, backend, wrapper

### Objects

**Object**:
A QObject inside an app that the agent can inspect or act on, such as a QML item or a widget.
_Avoid_: element, control, item, widget (unless it really is a QWidget)

**Internal object**:
An object that Qt creates inside a widget for its own workings and that never holds the app's own objects. For now these are the containers of a scroll area's scroll bars, `qt_scrollarea_hcontainer` and `qt_scrollarea_vcontainer`. Snapshots leave internal objects out unless `include_internal=True`. The other objects Qt names `qt_...`, such as a tab widget's page stack or a message box's buttons, are not internal objects, because the agent needs what they hold.
_Avoid_: Qt internals, private object

**Target**:
The object a qat-agent-helpers function works on, given as a definition or as a Qat object proxy, such as one that `qat.wait_for_object()` returns.
_Avoid_: element, locator, ref

**Snapshot**:
A compact text view of part of an app's object tree at one moment, with one line per object that shows the object's definition wherever a unique one exists.
_Avoid_: dump, tree, DOM

**Definition**:
Qat's way of identifying an object: a set of property values, such as `objectName` and `type`, that must match exactly one object.
_Avoid_: selector, locator, query

### Actions

**Action**:
Input sent to an app, or a change to its state: a click, typed text, keys, a drag, a scroll, a property write or a method call.
_Avoid_: command, event
