"""qat-agent-helpers: helpers for AI agents that drive running Qt apps with Qat scripts.

The library covers only Qat's weak spots. For everything else, including waits,
property access and screenshots, use Qat's own API: the library makes each app it
launches or attaches to Qat's current app.

Unofficial, community-made. Not affiliated with or endorsed by the Qat project.
"""

from qat_agent_helpers.actions import click, press_keys, type_text
from qat_agent_helpers.apps import App, attach, launch
from qat_agent_helpers.errors import (
    AmbiguousDefinitionError,
    AmbiguousDefinitionWarning,
    AppGoneError,
    CommandError,
    LaunchError,
    NonAsciiTextError,
    NotAcceptedError,
    NotFoundError,
    NotReadyError,
    NotToggledError,
    ObjectGoneError,
    QatAgentHelpersError,
)
from qat_agent_helpers.snapshot import snapshot
from qat_agent_helpers.targets import definition_for

__all__ = [
    "AmbiguousDefinitionError",
    "AmbiguousDefinitionWarning",
    "App",
    "AppGoneError",
    "CommandError",
    "LaunchError",
    "NonAsciiTextError",
    "NotAcceptedError",
    "NotFoundError",
    "NotReadyError",
    "NotToggledError",
    "ObjectGoneError",
    "QatAgentHelpersError",
    "attach",
    "click",
    "definition_for",
    "launch",
    "press_keys",
    "snapshot",
    "type_text",
]
