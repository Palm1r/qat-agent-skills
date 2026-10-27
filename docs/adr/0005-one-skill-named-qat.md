# One skill, `qat`, with its branches in references

One skill named `qat` replaces the two skills qat-explore and qat-tests. Its SKILL.md holds what every task needs: the loop launch → snapshot → screenshot → act → wait, the library's calls, the pitfalls that bite everywhere, when each kind of driving is done, and which file to read for what. Tests in a pytest suite, Qat suites, Qat's whole API and the platforms live in `references/`.

A test is never written without driving the app, since its definitions come from snapshots and its scenario is checked live, so a skill for tests had no trigger of its own worth a second description in every agent's context. One skill keeps one copy of the Qat reference and the platform notes, which qat-tests used to repeat or point back to. And the steps for tests stay out of view while the agent explores, so it does not hurry towards them.

## Considered Options

- Two skills, `qat-drive` with the core and `qat-tests`, which loads it first: precise triggers and a direct way in for tests, at the price of a second description and a dependency between the skills.
- Three or four skills, adding setup and Qat suites: setup has no trigger of its own, since launch problems surface in the middle of a task as a `LaunchError`, and Qat suites are a branch of tests.

## Consequences

- The way to the tests is a pointer in SKILL.md, not a skill of its own, so its wording has to be firm.
- The skill is named after the tool, as Anthropic's `pdf`, `docx` and `xlsx` skills are. If Qat ever ships a skill of its own named `qat`, the names will collide.
- Users who installed qat-explore and qat-tests have to remove them; the README and the CHANGELOG say so.
