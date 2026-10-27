import pytest

import qat_agent_helpers
from qat_agent_helpers import apps
from tests.unit.fake_qat import (
    FakeApp,
    FakeProxy,
    FakeQat,
    check_box,
    line_edit,
    qml_check_box,
    qobject,
    tristate_check_box,
    widget,
)


@pytest.fixture
def short_wait(monkeypatch):
    monkeypatch.setattr(FakeQat, "wait_seconds", 0.2)


def open_app(use_fake, executable, *objects) -> FakeApp:
    app = FakeApp(widget("QMainWindow", "mainWindow", *objects))
    use_fake(app)
    qat_agent_helpers.launch(executable)
    return app


def clicks(app: FakeApp) -> list[tuple[str, dict]]:
    return [(uid, options) for command, uid, options in app.inputs if command == "click"]


def ok_button(**options):
    return widget("QPushButton", "okButton", text="OK", **options)


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


OK_IN_DIALOG = {"type": "QPushButton", "text": "OK", "container": {"objectName": "openDialog"}}


def test_a_click_waits_for_the_container_of_its_target_to_appear(use_fake, executable):
    button = widget("QPushButton", "", text="OK", visible=False)
    dialog = widget("QDialog", "openDialog", button, visible=False)
    app = open_app(use_fake, executable, dialog)
    app.later(0.2, dialog, visible=True)
    app.later(0.2, button, visible=True)

    qat_agent_helpers.click(OK_IN_DIALOG)

    assert [uid for uid, _ in clicks(app)] == [button.uid]


def test_a_hidden_twin_of_the_container_is_skipped_as_qat_wait_for_object_does(
    use_fake, executable, short_wait
):
    hidden = widget("QPushButton", "", text="OK", visible=False)
    shown = widget("QPushButton", "", text="OK")
    app = open_app(
        use_fake,
        executable,
        widget("QDialog", "openDialog", hidden, visible=False),
        widget("QDialog", "openDialog", shown),
    )

    qat_agent_helpers.click(OK_IN_DIALOG)

    assert [uid for uid, _ in clicks(app)] == [shown.uid]


def test_a_target_in_a_container_with_a_hidden_twin_is_reported_as_disabled(
    use_fake, executable, short_wait
):
    app = open_app(
        use_fake,
        executable,
        widget("QDialog", "openDialog", widget("QPushButton", "", text="OK"), visible=False),
        widget("QDialog", "openDialog", widget("QPushButton", "", text="OK", enabled=False)),
    )

    with pytest.raises(qat_agent_helpers.NotReadyError, match=r"is still disabled after 0.2 s"):
        qat_agent_helpers.click(OK_IN_DIALOG)

    assert app.inputs == []


def test_a_container_matching_several_objects_fails_at_once_and_lists_them(
    use_fake, executable, short_wait
):
    app = open_app(
        use_fake,
        executable,
        widget("QDialog", "openDialog", widget("QPushButton", "", text="OK"), window_title="Open"),
        widget("QDialog", "openDialog", widget("QPushButton", "", text="OK"), window_title="Copy"),
    )

    with pytest.raises(qat_agent_helpers.AmbiguousDefinitionError) as raised:
        qat_agent_helpers.click(OK_IN_DIALOG)

    assert str(raised.value) == (
        'The container {"objectName": "openDialog"} matches 2 objects:\n'
        '- QDialog #openDialog "Open"\n'
        '- QDialog #openDialog "Copy"'
    )
    assert app.inputs == []


def test_a_non_visual_object_cannot_take_input(use_fake, executable):
    open_app(use_fake, executable, qobject("QTimer", "autoSaveTimer"))

    with pytest.raises(
        qat_agent_helpers.QatAgentHelpersError, match="not a widget, Qt Quick item or window"
    ):
        qat_agent_helpers.click({"objectName": "autoSaveTimer"})


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


def test_a_checkable_widget_without_an_indicator_is_clicked_at_its_centre_unchecked(
    use_fake, executable
):
    group = widget("QGroupBox", "options", checked=False, size=(400, 300))
    open_app(use_fake, executable, group)

    qat_agent_helpers.click({"objectName": "options"})

    assert group.properties["checked"] is False


def test_a_checkable_button_that_does_not_toggle_raises(use_fake, executable):
    button = widget("QPushButton", "bold", text="Bold", checked=False)
    button.bases = ("QAbstractButton", "QWidget")
    open_app(use_fake, executable, button)

    with pytest.raises(qat_agent_helpers.NotToggledError, match="checked stayed False"):
        qat_agent_helpers.click({"objectName": "bold"})


def test_a_click_from_partly_checked_to_checked_on_a_tristate_check_box_is_no_error(
    use_fake, executable
):
    box = tristate_check_box("selectAll", "Select all", state="PartiallyChecked")
    app = open_app(use_fake, executable, box)

    qat_agent_helpers.click({"objectName": "selectAll"})

    assert box.properties["checked"] is True
    assert [(options["x"], options["y"]) for _, options in clicks(app)] == [(10, 10)]


def test_a_click_that_misses_an_unchecked_tristate_check_box_still_raises(use_fake, executable):
    box = tristate_check_box("selectAll", "Select all", state="Unchecked")
    open_app(use_fake, executable, box)

    with pytest.raises(qat_agent_helpers.NotToggledError, match="checked stayed False"):
        qat_agent_helpers.click({"objectName": "selectAll"}, x=300, y=10)


def test_a_qml_check_box_is_judged_by_its_check_state(use_fake, executable):
    box = qml_check_box("selectAll", "Select all", tristate=True)
    open_app(use_fake, executable, box)

    qat_agent_helpers.click({"objectName": "selectAll"})

    assert (box.properties["checkState"], box.properties["checked"]) == ("PartiallyChecked", False)


def test_a_click_that_leaves_a_qml_check_box_in_its_check_state_raises(use_fake, executable):
    box = qml_check_box("selectAll", "Select all", tristate=True)
    box.on_click = None
    open_app(use_fake, executable, box)

    with pytest.raises(qat_agent_helpers.NotToggledError, match="checkState stayed Unchecked"):
        qat_agent_helpers.click({"objectName": "selectAll"})


def test_a_proxy_target_is_clicked_in_its_own_app_not_the_current_one(use_fake, executable):
    first_button, second_button = ok_button(), ok_button()
    first = FakeApp(widget("QMainWindow", "mainWindow", first_button))
    second = FakeApp(widget("QMainWindow", "mainWindow", second_button))
    use_fake(first, second)
    qat_agent_helpers.launch(executable)
    qat_agent_helpers.launch(executable)

    qat_agent_helpers.click(FakeProxy(first, first_button))

    assert [uid for uid, _ in clicks(first)] == [first_button.uid]
    assert clicks(second) == []


def test_a_proxy_from_an_app_qat_opened_itself_is_adopted(use_fake, executable):
    button = ok_button()
    qats_own = FakeApp(widget("QMainWindow", "mainWindow", button))
    fake = use_fake(FakeApp(widget("QMainWindow", "mainWindow")), qats_own)
    qat_agent_helpers.launch(executable)

    qat_agent_helpers.click(FakeProxy(qats_own, button))

    assert fake.adopted == [qats_own]
    assert [uid for uid, _ in clicks(qats_own)] == [button.uid]
    assert len(apps.open_apps()) == 1


def test_clicking_a_checked_radio_button_again_is_no_error(use_fake, executable):
    radio = widget("QRadioButton", "dark", text="Dark", checked=True, size=(200, 21))
    radio.properties["autoExclusive"] = True
    radio.bases = ("QAbstractButton", "QWidget")
    open_app(use_fake, executable, radio)

    qat_agent_helpers.click({"objectName": "dark"})

    assert radio.properties["checked"] is True


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


def test_text_beyond_ascii_is_typed_as_it_is(use_fake, executable):
    field = line_edit("nameField")
    open_app(use_fake, executable, field)

    qat_agent_helpers.type_text({"objectName": "nameField"}, "Привет, café")

    assert field.properties["text"] == "Привет, café"


def test_a_row_of_an_item_view_is_refused_with_the_qat_call_to_use(use_fake, executable):
    app = open_app(use_fake, executable, widget("QListWidget", "fruitList"))
    row = {"container": {"objectName": "fruitList"}, "row": 1}

    with pytest.raises(ValueError) as raised:
        qat_agent_helpers.click(row)

    assert str(raised.value) == (
        '{"container": {"objectName": "fruitList"}, "row": 1} is a row or cell of an item view, '
        "which qat-agent-helpers cannot act on yet. Use Qat's own calls on it, such as "
        "qat.mouse_click(definition, blocking=False), and check the effect with a Qat wait."
    )
    assert app.inputs == []


def test_a_child_row_of_a_tree_view_is_refused_too(use_fake, executable):
    open_app(use_fake, executable, widget("QTreeView", "tree"))
    child = {"container": {"container": {"objectName": "tree"}, "row": 0}, "row": 2}

    with pytest.raises(ValueError, match=r"is a row or cell of an item view"):
        qat_agent_helpers.definition_for(child)


def test_typing_into_an_object_that_takes_no_text_raises(use_fake, executable):
    open_app(use_fake, executable, widget("QLabel", "counterLabel", text="0"))

    with pytest.raises(
        qat_agent_helpers.NotAcceptedError, match=r"No widget accepted the keys typed into"
    ):
        qat_agent_helpers.type_text({"objectName": "counterLabel"}, "5")


def test_an_object_the_keys_destroy_still_gets_the_error_about_them(use_fake, executable):
    blank = widget("QWidget")
    app = open_app(use_fake, executable, blank)
    blank.on_keys = lambda keys: app.destroy(blank)

    with pytest.raises(qat_agent_helpers.NotAcceptedError) as raised:
        qat_agent_helpers.type_text({"type": "QWidget"}, "5")

    assert str(raised.value) == (
        "No widget accepted the keys typed into QWidget: it may not take text. "
        "Target a text field instead."
    )
