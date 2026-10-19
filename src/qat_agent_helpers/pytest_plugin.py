"""The pytest plugin of qat-agent-helpers, registered through the pytest11 entry point.

def test_counter(launch_app):
    launch_app("path/to/app.exe")
    qat_agent_helpers.click({"objectName": "incrementButton"})
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from qat_agent_helpers.apps import App, launch


@pytest.fixture
def launch_app() -> Iterator[Callable[..., App]]:
    """A function that launches an app as qat_agent_helpers.launch() does, for this test only.

    Every app it launched is closed in the test's teardown, whatever the outcome.
    """
    launched: list[App] = []

    def launch_for_test(*args, **kwargs) -> App:
        app = launch(*args, **kwargs)
        launched.append(app)
        return app

    yield launch_for_test
    for app in reversed(launched):
        app.close()
