"""definition_for() gives a portable definition that matches only the object, for tests."""

import pytest

import qat_agent_helpers
from tests.unit.fake_qat import FakeApp, widget


def open_app(use_fake, executable, *windows) -> None:
    use_fake(FakeApp(*windows))
    qat_agent_helpers.launch(executable)


def test_a_named_object_gets_its_object_name_and_type(use_fake, executable):
    open_app(use_fake, executable, widget("QMainWindow", "mainWindow", widget("QLabel", "title")))

    assert qat_agent_helpers.definition_for({"objectName": "title"}) == {
        "objectName": "title",
        "type": "QLabel",
    }


def test_an_object_that_shares_its_name_gets_its_type_and_text(use_fake, executable):
    open_app(
        use_fake,
        executable,
        widget(
            "QMainWindow",
            "mainWindow",
            widget("QPushButton", "twinButton", text="Twin A"),
            widget("QPushButton", "twinButton", text="Twin B"),
        ),
    )

    definition = qat_agent_helpers.definition_for({"type": "QPushButton", "text": "Twin B"})

    assert definition == {"type": "QPushButton", "text": "Twin B"}


def test_a_look_alike_object_gets_a_container(use_fake, executable):
    open_app(
        use_fake,
        executable,
        widget("QDialog", "saveDialog", widget("QPushButton", "", text="OK")),
        widget("QDialog", "openDialog", widget("QPushButton", "", text="OK", focus=True)),
    )

    definition = qat_agent_helpers.definition_for({"type": "QPushButton", "focus": True})

    assert definition == {
        "type": "QPushButton",
        "text": "OK",
        "container": {"objectName": "openDialog", "type": "QDialog"},
    }


def test_without_a_unique_definition_the_best_one_comes_with_a_warning(use_fake, executable):
    open_app(
        use_fake,
        executable,
        widget("QMainWindow", "mainWindow", widget("QLabel", "", focus=True), widget("QLabel", "")),
    )

    with pytest.warns(qat_agent_helpers.AmbiguousDefinitionWarning) as warned:
        definition = qat_agent_helpers.definition_for({"type": "QLabel", "focus": True})

    assert definition == {"type": "QLabel"}
    assert str(warned[0].message) == (
        'No definition matches only QLabel focused: the best one, {"type": "QLabel"}, '
        "matches 2 objects. Give the object an objectName in the app's code to make it unique."
    )
