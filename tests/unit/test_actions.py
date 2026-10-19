"""click(), press_keys() and type_text(): wait for the target, send the input, check the effect."""

import pytest
from qat.test_settings import Settings

import qat_agent_helpers
from tests.unit.fake_qat import (
    FakeApp,
    check_box,
    line_edit,
    qml_check_box,
    qobject,
    widget,
)


@pytest.fixture
def short_wait(monkeypatch):
    """Qat's wait for an object, which the library's actions use too, cut to 0.2 s."""
    monkeypatch.setattr(Settings, "wait_for_object_timeout", 200)


def open_app(use_fake, executable, *objects) -> FakeApp:
    app = FakeApp(widget("QMainWindow", "mainWindow", *objects))
    use_fake(app)
    qat_agent_helpers.launch(executable)
    return app


def clicks(app: FakeApp) -> list[tuple[str, dict]]:
    return [(uid, options) for command, uid, options in app.inputs if command == "click"]


def ok_button(**options):
    return widget("QPushButton", "okButton", text="OK", **options)


# Waiting for the target


def test_a_click_waits_for_a_hidden_button_to_appear(use_fake, executable):
    button = ok_button(visible=False)
    app = open_app(use_fake, executable, button)
    app.later(0.2, button, visible=True)

    qat_agent_helpers.click({"objectName": "okButton"})

    assert [uid for uid, _ in clicks(app)] == [button.uid]


def test_a_button_that_stays_hidden_is_not_clicked(use_fake, executable, short_wait):
    app = open_app(use_fake, executable, ok_button(visible=False))

    with pytest.raises(qat_agent_helpers.NotReadyError) as raised:
        qat_agent_helpers.click({"objectName": "okButton"})

    assert str(raised.value).startswith('QPushButton #okButton "OK" hidden def=')
    assert str(raised.value).endswith(
        "is still hidden after 0.2 s. Make it visible first, or wait for it with "
        "qat.wait_for_object()."
    )
    assert app.inputs == []


def test_a_button_that_stays_disabled_is_not_clicked(use_fake, executable, short_wait):
    app = open_app(use_fake, executable, ok_button(enabled=False))

    with pytest.raises(qat_agent_helpers.NotReadyError, match=r"is still disabled after 0.2 s"):
        qat_agent_helpers.click({"objectName": "okButton"})

    assert app.inputs == []


def test_a_definition_that_matches_nothing_fails_after_the_wait(use_fake, executable, short_wait):
    open_app(use_fake, executable, ok_button())

    with pytest.raises(qat_agent_helpers.NotFoundError, match=r"cancelButton.* after 0\.2 s"):
        qat_agent_helpers.click({"objectName": "cancelButton"})


def test_a_definition_skips_hidden_objects_as_qat_wait_for_object_does(use_fake, executable):
    hidden, shown = ok_button(visible=False), ok_button()
    app = open_app(use_fake, executable, hidden, shown)

    qat_agent_helpers.click({"objectName": "okButton"})

    assert [uid for uid, _ in clicks(app)] == [shown.uid]


def test_a_definition_matching_several_ready_objects_fails_at_once(use_fake, executable):
    app = open_app(
        use_fake,
        executable,
        widget("QPushButton", "twinButton", text="Twin A"),
        widget("QPushButton", "twinButton", text="Twin B"),
    )

    with pytest.raises(qat_agent_helpers.AmbiguousDefinitionError, match="matches 2 objects"):
        qat_agent_helpers.click({"objectName": "twinButton"})

    assert app.inputs == []


def test_a_non_visual_object_cannot_take_input(use_fake, executable):
    open_app(use_fake, executable, qobject("QTimer", "autoSaveTimer"))

    with pytest.raises(
        qat_agent_helpers.QatAgentHelpersError, match="not a widget, Qt Quick item or window"
    ):
        qat_agent_helpers.click({"objectName": "autoSaveTimer"})


# The click


def test_button_double_click_modifiers_and_position_reach_qat(use_fake, executable):
    button = ok_button()
    app = open_app(use_fake, executable, button)

    qat_agent_helpers.click(
        {"objectName": "okButton"},
        button="right",
        double=True,
        modifiers=("ctrl", "shift"),
        x=5,
        y=10,
    )

    options = {"button": "right", "double": True, "modifiers": ("ctrl", "shift"), "x": 5, "y": 10}
    assert clicks(app) == [(button.uid, options)]


def test_a_position_needs_both_coordinates(use_fake, executable):
    app = open_app(use_fake, executable, ok_button())

    with pytest.raises(ValueError, match=r"Pass both x and y, or neither."):
        qat_agent_helpers.click({"objectName": "okButton"}, x=5)

    assert app.inputs == []


def test_a_click_qat_refuses_says_why(use_fake, executable):
    open_app(use_fake, executable, ok_button())

    with pytest.raises(qat_agent_helpers.CommandError, match="outside widget's boundaries"):
        qat_agent_helpers.click({"objectName": "okButton"}, x=500, y=10)


# Check boxes


def test_a_click_on_a_check_box_aims_at_its_indicator(use_fake, executable):
    box = check_box("showSecretCheckBox", "Show secret")
    app = open_app(use_fake, executable, box)

    qat_agent_helpers.click({"objectName": "showSecretCheckBox"})

    assert box.properties["checked"] is True
    assert [(options["x"], options["y"]) for _, options in clicks(app)] == [(10, 10)]


def test_a_click_on_a_qml_check_box_aims_at_its_indicator_item(use_fake, executable):
    box = qml_check_box("showSecretCheckBox", "Show secret")
    app = open_app(use_fake, executable, box)

    qat_agent_helpers.click({"objectName": "showSecretCheckBox"})

    assert box.properties["checked"] is True
    assert [(options["x"], options["y"]) for _, options in clicks(app)] == [(20, 18)]


def test_a_click_that_does_not_toggle_a_check_box_raises(use_fake, executable):
    box = check_box("showSecretCheckBox", "Show secret")
    open_app(use_fake, executable, box)

    with pytest.raises(qat_agent_helpers.NotToggledError) as raised:
        qat_agent_helpers.click({"objectName": "showSecretCheckBox"}, x=300, y=10)

    assert str(raised.value).startswith(
        'The click on QCheckBox #showSecretCheckBox "Show secret" def='
    )
    assert str(raised.value).endswith(
        "did not toggle it: checked stayed False. Click its indicator, or press Space on it "
        "with press_keys()."
    )


def test_clicking_a_checked_radio_button_again_is_no_error(use_fake, executable):
    radio = widget("QRadioButton", "dark", text="Dark", checked=True, size=(200, 21))
    radio.properties["autoExclusive"] = True
    radio.bases = ("QAbstractButton", "QWidget")
    open_app(use_fake, executable, radio)

    qat_agent_helpers.click({"objectName": "dark"})

    assert radio.properties["checked"] is True


# Keys and text


def test_press_keys_posts_the_keys_to_the_target(use_fake, executable):
    field = line_edit("nameField")
    app = open_app(use_fake, executable, field)

    qat_agent_helpers.press_keys({"objectName": "nameField"}, "Return")

    assert app.inputs == [("keys", field.uid, {"keys": "Return"})]


def test_type_text_types_into_a_text_field(use_fake, executable):
    field = line_edit("nameField")
    open_app(use_fake, executable, field)

    qat_agent_helpers.type_text({"objectName": "nameField"}, "Ada")

    assert field.properties["text"] == "Ada"


def test_non_ascii_text_is_refused_before_anything_is_typed(use_fake, executable):
    app = open_app(use_fake, executable, line_edit("nameField"))

    with pytest.raises(qat_agent_helpers.NonAsciiTextError) as raised:
        qat_agent_helpers.type_text({"objectName": "nameField"}, "café")

    assert str(raised.value) == (
        "type_text() types ASCII text only: Qat cannot type other characters (Qat issue #45), "
        'and "café" contains "é". Set the text property instead, for example '
        'qat.wait_for_object(definition).text = "café".'
    )
    assert app.inputs == []


def test_typing_into_an_object_that_takes_no_text_raises(use_fake, executable):
    open_app(use_fake, executable, widget("QLabel", "counterLabel", text="0"))

    with pytest.raises(
        qat_agent_helpers.NotAcceptedError, match=r"No widget accepted the keys typed into"
    ):
        qat_agent_helpers.type_text({"objectName": "counterLabel"}, "5")
