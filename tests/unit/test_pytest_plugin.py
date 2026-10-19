"""The pytest plugin: the launch_app fixture closes the apps a test launched."""

from tests.unit.fake_qat import FakeApp, widget


def test_the_launch_app_fixture_closes_its_apps_after_the_test(use_fake, executable, pytester):
    fake_app = FakeApp(widget("QMainWindow", "mainWindow"))
    use_fake(fake_app)
    pytester.makepyfile(
        f"""
        def test_launch(launch_app):
            app = launch_app(r"{executable}")
            assert app.pid
        """
    )

    # In process, so the test inside sees the fake Qat.
    result = pytester.runpytest_inprocess()

    result.assert_outcomes(passed=1)
    assert fake_app.exit_code == 0
