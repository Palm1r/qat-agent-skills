# Tests in a Qat suite

A Qat suite is laid out by Qat's own template, `qat-create-suite`. New tests go into it in its own style: its steps, its object dictionary and its way of starting apps.

## Recognizing one

- A **BDD suite** has a `features/` folder with an `environment.py` that calls `qat.bdd_hooks`, feature files in Gherkin, step modules in `features/steps/` (`given.py`, `when.py`, `then.py`), and an object dictionary, `features/scripts/object_dictionary.py`, whose `bdd_mapping` maps the names used in feature files to definitions.
- A **script suite** has Python scripts that report through `qat.report`, between `report.start_report()` and `report.stop_report()`, often with an object dictionary in `scripts/object_dictionary.py`.
- Both keep `applications.json`, the registry of the apps the suite starts, and `testSettings.json` at the suite's root.
- Qat's `qat-create-suite --dest suite` makes a new BDD suite in `suite/`, and `qat-create-suite script --dest suite` a script suite. Make one only when the user asks for a Qat suite. Its object dictionary names the main window `{'type': 'ApplicationWindow'}`, a Qt Quick type that its demo scenario looks for; for a Qt Widgets app, replace it with the main window's `def=` from a snapshot.

## How the suite starts apps

A suite starts apps by name: `qat.start_application("name")` takes the path from `applications.json`, which `qat.register_application(name, path, args)` or Qat's `qat-gui` writes. Keep that: register the app the suite needs rather than calling `qat_agent_helpers.launch()` in its steps. `qat.register_application()` writes the `applications.json` in the current folder, so call it from the suite's root, with the app's absolute path or one relative to that root, where the suite runs. The tag `@fixture.app.autoclose` on a feature or a scenario closes its apps when it ends.

## qat-agent-helpers in a suite

The library's calls work on the app the suite started, since that app is Qat's current app, and the library never closes an app it did not launch. Use `qat_agent_helpers.click()`, `press_keys()` and `type_text()` in steps for the same reasons as in scripts, the modal dialogs, check boxes and Return in text fields of SKILL.md's pitfalls, and `snapshot()` to find definitions while you write them. Install qat-agent-helpers into the environment the suite runs in. Qat's template keeps no list of dependencies, so add it next to `qat` where the project lists that, in a requirements file or a pyproject, or else install it with `pip install "qat-agent-helpers @ git+https://github.com/Palm1r/qat-agent-skills@v0.1.1"` and tell the user.

## Writing a scenario

1. Find the phrases the suite already has. Steps are functions decorated with `@given`, `@when` and `@then` in `features/steps/`, and their text is a pattern with `{name}` placeholders. Reuse a step whenever its phrase fits, under its own keyword: an `And` or a `But` line takes the keyword of the line above it, so a `@then` step after a `When` line needs a `Then` line of its own.
2. Add the definitions you need to the object dictionary, under a readable name in `bdd_mapping`, copied from the `def=` of a snapshot line.
3. Write the scenario in a feature file, in the suite's own wording.
4. Add a step only for an action or a check the suite lacks, in the module where its neighbours live:

   ```python
   import qat
   import qat_agent_helpers
   from behave import Then, When
   from qat import report
   from scripts.object_dictionary import bdd_mapping


   @When("I click the {name}")
   def step(context, name):
       qat_agent_helpers.click(bdd_mapping[name])


   @Then('The {name} shows "{text}"')
   def step(context, name, text):
       reached = qat.wait_for_property_value(bdd_mapping[name], "text", text)
       shown = qat.wait_for_object_exists(bdd_mapping[name]).text
       report.verify(reached, f"{name} shows {text}", f"text is {shown}")
   ```

   `report.verify(condition, description, details)` records a check in the report and raises when the condition is false; `report.log(text)` records a note.

In a script suite, add a test function next to the others, in the same style, with checks through `report.verify()`.

## Running the suite

Run behave in the suite's own environment from the suite's root, the folder that holds `applications.json` and `testSettings.json`, which need not be the project's root: there, `python -m behave` runs every feature, and `python -m behave features/demo/counter.feature` one of them. The report goes to `report/results.xml`, or where `-D report_file=path` says. `testSettings.json` holds Qat's timeouts, `screenshotOnFail`, which saves a screenshot into the report's folder on a failure, `continueAfterFail` and `lockUI`.

A script suite runs its scripts with Python. Each must call `report.stop_report()` when it ends, or the report writer keeps the script from exiting.

A scenario is done when it passes as the project runs its suite, uses the suite's steps and object dictionary wherever they fit, and checks every effect it relies on with `report.verify()` or a Qat wait.
