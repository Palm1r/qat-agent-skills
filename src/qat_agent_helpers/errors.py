"""The errors qat-agent-helpers raises. Each message says what went wrong and what to do next."""

from __future__ import annotations

from typing import Any


class QatAgentHelpersError(Exception):
    """The base class of every error qat-agent-helpers raises."""


class LaunchError(QatAgentHelpersError, RuntimeError):
    """The app could not be started or attached to, or it did not connect to Qat."""


class AppGoneError(QatAgentHelpersError, ConnectionError):
    """The app has exited, or Qat lost its connection to it."""


class ObjectGoneError(QatAgentHelpersError, LookupError):
    """The object has been destroyed."""


class CommandError(QatAgentHelpersError, RuntimeError):
    """Qat refused a command, for example a click outside the object."""


class NotFoundError(QatAgentHelpersError, LookupError):
    """No object matches a definition."""


class NotReadyError(QatAgentHelpersError, TimeoutError):
    """The target stayed hidden or disabled for as long as the action waited for it."""


class NotToggledError(QatAgentHelpersError, AssertionError):
    """A click on a check box, radio button or switch left its checked state as it was."""


class NotAcceptedError(QatAgentHelpersError, RuntimeError):
    """No widget accepted the typed keys."""


class NonAsciiTextError(QatAgentHelpersError, ValueError):
    """type_text() got characters that Qat cannot type."""


class AmbiguousDefinitionWarning(UserWarning):
    """definition_for() found no definition that matches only the object, and returned the
    best one it found."""


class AmbiguousDefinitionError(QatAgentHelpersError, LookupError):
    """A definition matches several objects. The message lists them with their definitions.

    `candidates` holds a unique definition for each match, or None where there is none.
    """

    def __init__(self, message: str, candidates: list[dict[str, Any] | None]) -> None:
        super().__init__(message)
        self.candidates = candidates
