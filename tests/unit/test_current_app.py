import pytest

import qat_agent_helpers
from qat_agent_helpers import apps
from tests.unit.fake_qat import FakeApp, FakeQat, widget


def window(name: str) -> FakeApp:
    return FakeApp(widget("QMainWindow", name, widget("QPushButton", "okButton", text="OK")))


def launch_all(
    use_fake, executable, *fake_apps: FakeApp
) -> tuple[FakeQat, list[qat_agent_helpers.App]]:
    fake = use_fake(*fake_apps)
    return fake, [qat_agent_helpers.launch(executable) for _ in fake_apps]


def test_a_switch_made_with_qat_applies_to_the_librarys_calls_too(use_fake, executable):
    first, second = window("first"), window("second")
    fake, _ = launch_all(use_fake, executable, first, second)

    fake.make_current(first.context)

    assert qat_agent_helpers.snapshot().startswith("- QMainWindow #first")
    qat_agent_helpers.click({"objectName": "okButton"})
    assert [command for command, _, _ in first.inputs] == ["click"]
    assert second.inputs == []


def test_closing_the_current_app_makes_the_newest_open_app_current(use_fake, executable):
    first, second, third = window("first"), window("second"), window("third")
    fake, (_, _, third_app) = launch_all(use_fake, executable, first, second, third)

    third_app.close()

    assert fake.current is second
    assert qat_agent_helpers.snapshot().startswith("- QMainWindow #second")


def test_closing_another_app_leaves_the_current_one_alone(use_fake, executable):
    first, second = window("first"), window("second")
    fake, (_, second_app) = launch_all(use_fake, executable, first, second)
    fake.make_current(first.context)

    second_app.close()

    assert fake.current is first
    assert qat_agent_helpers.snapshot().startswith("- QMainWindow #first")


def test_closing_the_only_app_leaves_no_app_current(use_fake, executable):
    fake, (app,) = launch_all(use_fake, executable, window("only"))

    app.close()

    assert fake.current is None
    with pytest.raises(qat_agent_helpers.QatAgentHelpersError, match=r"^No app is open"):
        qat_agent_helpers.snapshot()


def test_detaching_the_current_app_makes_the_newest_open_app_current(use_fake, executable):
    launched, attached = window("launched"), window("attached")
    fake = use_fake(launched, attached)
    qat_agent_helpers.launch(executable)
    app = qat_agent_helpers.attach(4321)

    app.detach()

    assert fake.current is launched
    assert qat_agent_helpers.snapshot().startswith("- QMainWindow #launched")


def test_detaching_the_only_app_leaves_no_app_current(use_fake):
    fake = use_fake(window("attached"))
    app = qat_agent_helpers.attach(4321)

    app.detach()

    assert fake.current is None
    with pytest.raises(qat_agent_helpers.QatAgentHelpersError, match=r"^No app is open"):
        qat_agent_helpers.snapshot()


def test_without_a_current_app_the_open_ones_are_listed_with_how_to_pick_one(use_fake, executable):
    first, second = window("first"), window("second")
    fake, _ = launch_all(use_fake, executable, first, second)
    fake.current = None

    with pytest.raises(qat_agent_helpers.QatAgentHelpersError) as raised:
        qat_agent_helpers.snapshot()

    assert str(raised.value) == (
        f"No app is current, but 2 are open: <qat_agent_helpers.App pid {first.pid}, launched "
        f"{executable}>, <qat_agent_helpers.App pid {second.pid}, launched {executable}>. Make one "
        "current with qat.set_current_application_context(app.context), or launch or attach "
        "another with qat_agent_helpers."
    )


def test_a_current_app_that_qat_started_itself_is_adopted(use_fake, executable):
    qats_own = window("qatsOwn")
    fake = use_fake(window("mine"), qats_own)
    qat_agent_helpers.launch(executable)
    fake.make_current(qats_own.context)

    assert qat_agent_helpers.snapshot().startswith("- QMainWindow #qatsOwn")
    assert fake.adopted == [qats_own]
    assert len(apps.open_apps()) == 1
