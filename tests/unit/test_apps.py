"""qat-agent-helpers launches or attaches to apps.

It closes the apps it launched and only detaches the others.
"""

import pytest

import qat_agent_helpers
from tests.unit.fake_qat import FakeApp, widget


def demo_app(**options) -> FakeApp:
    return FakeApp(widget("QMainWindow", "mainWindow"), **options)


def test_launch_hands_qat_the_executable_arguments_environment_and_lock(use_fake, executable):
    fake = use_fake(demo_app())

    qat_agent_helpers.launch(
        executable, ["--demo", "two words"], {"QT_SCALE_FACTOR": "2"}, lock_ui=True
    )

    assert fake.launches == [(executable, ["--demo", "two words"], {"QT_SCALE_FACTOR": "2"}, True)]


def test_by_default_an_app_gets_no_arguments_no_extra_environment_and_an_unlocked_ui(
    use_fake, executable
):
    fake = use_fake(demo_app())

    qat_agent_helpers.launch(executable)

    assert fake.launches == [(executable, [], {}, False)]


def test_a_path_without_an_executable_is_refused(use_fake, tmp_path):
    use_fake()

    with pytest.raises(FileNotFoundError, match=r"No executable at .*missing"):
        qat_agent_helpers.launch(tmp_path / "missing.exe")


def test_a_failed_launch_says_why(use_fake, executable):
    use_fake(launch_error="demo exited with code 1 before Qat could connect.")

    with pytest.raises(qat_agent_helpers.LaunchError, match="exited with code 1"):
        qat_agent_helpers.launch(executable)


def test_close_asks_a_launched_app_to_quit_and_returns_its_exit_code(use_fake, executable):
    fake_app = demo_app()
    use_fake(fake_app)
    app = qat_agent_helpers.launch(executable)

    assert app.close() == 0
    assert app.close() == 0  # closing again changes nothing
    assert not fake_app.killed


def test_close_kills_an_app_that_does_not_quit_in_time(use_fake, executable):
    fake_app = demo_app(quits=False)
    use_fake(fake_app)
    app = qat_agent_helpers.launch(executable)

    assert app.close(timeout=0.1) == 1
    assert fake_app.killed


def test_an_attached_app_is_never_closed_only_detached(use_fake):
    fake_app = demo_app()
    fake = use_fake(fake_app)
    app = qat_agent_helpers.attach(4321)

    with pytest.raises(qat_agent_helpers.QatAgentHelpersError, match=r"attached.*detach\(\)"):
        app.close()
    app.detach()

    assert fake.attaches == [4321]
    assert fake_app.detached
    assert fake_app.exit_code is None


def test_a_launched_app_is_closed_not_detached(use_fake, executable):
    use_fake(demo_app())
    app = qat_agent_helpers.launch(executable)

    with pytest.raises(qat_agent_helpers.QatAgentHelpersError, match=r"launched.*close\(\)"):
        app.detach()


def test_the_context_manager_closes_a_launched_app_and_detaches_an_attached_one(
    use_fake, executable
):
    launched, attached = demo_app(), demo_app()
    use_fake(launched, attached)

    with qat_agent_helpers.launch(executable):
        pass
    with qat_agent_helpers.attach(4321):
        pass

    assert launched.exit_code == 0
    assert attached.detached
    assert attached.exit_code is None
