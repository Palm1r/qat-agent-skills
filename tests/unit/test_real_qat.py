"""RealAppConnection: the commands it sends to Qat's server, checked on a fake Qat context."""

from __future__ import annotations

from typing import Any

from qat_agent_helpers.real_qat import RealAppConnection


class FakeContext:
    """Records what would go to Qat's server, as ApplicationContext.send_command() gets it."""

    pid = 4321

    def __init__(self) -> None:
        self.sent: list[tuple[dict[str, Any], int]] = []

    def is_running(self) -> bool:
        return True

    def send_command(self, command: dict[str, Any], timeout: int, nb_trials: int = 3) -> dict:
        self.sent.append((command, nb_trials))
        return {}


def connect() -> tuple[RealAppConnection, FakeContext]:
    context = FakeContext()
    return RealAppConnection(context, None), context  # pyright: ignore[reportArgumentType]


def mouse_commands(context: FakeContext) -> list[tuple[str, dict[str, Any]]]:
    return [
        (command["attribute"], command["args"])
        for command, _ in context.sent
        if command["command"] == "mouse"
    ]


def test_a_click_is_a_press_then_a_release_neither_of_them_blocking():
    connection, context = connect()

    connection.click("7")

    assert mouse_commands(context) == [
        ("press", {"button": "left", "modifier": "none", "blocking": False}),
        ("release", {"button": "left", "modifier": "none", "blocking": False}),
    ]
    assert all(command["object"] == {"cache_uid": "7"} for command, _ in context.sent)


def test_the_press_and_the_release_carry_the_button_modifiers_and_position():
    connection, context = connect()

    connection.click("7", button="right", modifiers=("ctrl", "shift"), x=3, y=4)

    args = {"button": "right", "modifier": ["ctrl", "shift"], "blocking": False, "x": 3, "y": 4}
    assert mouse_commands(context) == [("press", args), ("release", args)]


def test_each_part_of_a_click_is_sent_once():
    connection, context = connect()

    connection.click("7")

    assert [nb_trials for _, nb_trials in context.sent] == [1, 1]


def test_a_double_click_stays_one_double_click_command():
    connection, context = connect()

    connection.click("7", double=True)

    assert mouse_commands(context) == [
        ("double-click", {"button": "left", "modifier": "none", "blocking": False}),
    ]
