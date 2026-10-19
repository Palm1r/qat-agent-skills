"""snapshot() shows an object tree as text, one line per object, with its definition."""

import pytest

import qat_agent_helpers
from tests.unit.fake_qat import FakeApp, item, line_edit, list_widget, qobject, widget

# About 8k tokens of snapshot lines, at roughly three characters per token. Codex cuts
# the middle out of text results longer than 10k tokens.
BUDGET_CHARS = 24_000


def launch(use_fake, executable, *fake_apps: FakeApp) -> None:
    use_fake(*fake_apps)
    for _ in fake_apps:
        qat_agent_helpers.launch(executable)


def test_each_object_takes_one_line_with_names_text_flags_and_definition(use_fake, executable):
    window = widget(
        "QMainWindow",
        "mainWindow",
        widget("QPushButton", "incrementButton", text="Increment"),
        widget("QLabel", "counterLabel", text="0"),
        line_edit("nameField", placeholder="Your name", focus=True),
        window_title="Demo Widgets",
    )
    launch(use_fake, executable, FakeApp(window))

    assert qat_agent_helpers.snapshot().splitlines() == [
        '- QMainWindow #mainWindow "Demo Widgets" '
        'def={"objectName": "mainWindow", "type": "QMainWindow"}',
        '  - QPushButton #incrementButton "Increment" '
        'def={"objectName": "incrementButton", "type": "QPushButton"}',
        '  - QLabel #counterLabel "0" def={"objectName": "counterLabel", "type": "QLabel"}',
        '  - QLineEdit #nameField placeholder="Your name" focused '
        'def={"objectName": "nameField", "type": "QLineEdit"}',
    ]


def test_qml_items_show_their_id_and_count_as_focused_only_with_active_focus(use_fake, executable):
    window = item(
        "Main",
        "mainWindow",
        item("Button", "", qml_id="okButton", text="OK", focus=True),
        item("TextField", "", qml_id="nameField", text="Ada", focus=True, active_focus=True),
        title="Demo Quick",
    )
    launch(use_fake, executable, FakeApp(window))

    assert qat_agent_helpers.snapshot().splitlines()[1:] == [
        '  - Button id=okButton "OK" def={"id": "okButton", "type": "Button"}',
        '  - TextField id=nameField "Ada" focused def={"id": "nameField", "type": "TextField"}',
    ]


def test_state_flags_follow_the_text_in_a_fixed_order(use_fake, executable):
    window = widget(
        "QDialog",
        "settingsDialog",
        widget("QCheckBox", "autoSave", text="Auto save", checked=True, focus=True),
        widget("QPushButton", "applyButton", text="Apply", enabled=False, focus=True),
    )
    launch(use_fake, executable, FakeApp(window))

    lines = qat_agent_helpers.snapshot().splitlines()

    assert lines[1].startswith('  - QCheckBox #autoSave "Auto save" focused checked def=')
    assert lines[2].startswith('  - QPushButton #applyButton "Apply" disabled focused def=')


def test_objects_that_share_a_name_get_a_definition_by_type_and_text(use_fake, executable):
    window = widget(
        "QMainWindow",
        "mainWindow",
        widget("QPushButton", "twinButton", text="Twin A"),
        widget("QPushButton", "twinButton", text="Twin B"),
    )
    launch(use_fake, executable, FakeApp(window))

    assert qat_agent_helpers.snapshot().splitlines()[1:] == [
        '  - QPushButton #twinButton "Twin A" def={"type": "QPushButton", "text": "Twin A"}',
        '  - QPushButton #twinButton "Twin B" def={"type": "QPushButton", "text": "Twin B"}',
    ]


def test_look_alike_objects_get_a_definition_inside_a_named_container(use_fake, executable):
    save = widget("QDialog", "saveDialog", widget("QPushButton", "", text="OK"))
    open_ = widget("QDialog", "openDialog", widget("QPushButton", "", text="OK"))
    launch(use_fake, executable, FakeApp(save, open_))

    lines = qat_agent_helpers.snapshot().splitlines()

    assert lines[3] == (
        '  - QPushButton "OK" def={"type": "QPushButton", "text": "OK", '
        '"container": {"objectName": "openDialog", "type": "QDialog"}}'
    )


def test_an_object_without_a_unique_definition_has_no_def(use_fake, executable):
    window = widget("QMainWindow", "mainWindow", widget("QLabel", ""), widget("QLabel", ""))
    launch(use_fake, executable, FakeApp(window))

    assert qat_agent_helpers.snapshot().splitlines()[1:] == ["  - QLabel", "  - QLabel"]


def test_non_visual_objects_are_left_out_and_shared_children_shown_once(use_fake, executable):
    ok = widget("QPushButton", "okButton", text="OK")
    window = widget(
        "QMainWindow",
        "mainWindow",
        qobject("QVBoxLayout", "", ok),
        widget("QWidget", "buttonBox", ok),
        qobject("QTimer", "autoSaveTimer"),
    )
    launch(use_fake, executable, FakeApp(window))

    assert [line.split(" def=")[0] for line in qat_agent_helpers.snapshot().splitlines()] == [
        "- QMainWindow #mainWindow",
        "  - QWidget #buttonBox",
        '    - QPushButton #okButton "OK"',
    ]


def test_hidden_objects_are_shown_only_with_include_hidden(use_fake, executable):
    # The children of a hidden widget report visible=False too, as in Qt.
    secret = widget("QLabel", "secretLabel", text="The secret is 42", visible=False)
    launch(use_fake, executable, FakeApp(widget("QMainWindow", "mainWindow", secret)))

    assert len(qat_agent_helpers.snapshot().splitlines()) == 1
    assert qat_agent_helpers.snapshot(include_hidden=True).splitlines()[1] == (
        '  - QLabel #secretLabel "The secret is 42" hidden '
        'def={"objectName": "secretLabel", "type": "QLabel"}'
    )


def test_scroll_bar_containers_are_left_out_with_their_scroll_bars_hidden_or_not(
    use_fake, executable
):
    window = widget("QMainWindow", "mainWindow", list_widget("fruitList"))
    launch(use_fake, executable, FakeApp(window))

    expected = [
        "- QMainWindow #mainWindow",
        "  - QListWidget #fruitList",
        "    - QWidget #qt_scrollarea_viewport",
    ]
    assert [
        line.split(" def=")[0] for line in qat_agent_helpers.snapshot().splitlines()
    ] == expected
    assert [
        line.split(" def=")[0]
        for line in qat_agent_helpers.snapshot(include_hidden=True).splitlines()
    ] == expected


def test_include_internal_shows_the_scroll_bar_containers(use_fake, executable):
    window = widget("QMainWindow", "mainWindow", list_widget("fruitList"))
    launch(use_fake, executable, FakeApp(window))

    lines = qat_agent_helpers.snapshot(include_hidden=True, include_internal=True).splitlines()

    assert [line.split(" def=")[0] for line in lines] == [
        "- QMainWindow #mainWindow",
        "  - QListWidget #fruitList",
        "    - QWidget #qt_scrollarea_viewport",
        "    - QWidget #qt_scrollarea_hcontainer hidden",
        "      - QScrollBar hidden",
        "    - QWidget #qt_scrollarea_vcontainer",
        "      - QScrollBar",
    ]


def test_depth_limits_the_levels_below_the_root(use_fake, executable):
    window = widget(
        "QMainWindow", "mainWindow", widget("QWidget", "panel", widget("QLabel", "label"))
    )
    launch(use_fake, executable, FakeApp(window))

    assert len(qat_agent_helpers.snapshot(depth=1).splitlines()) == 2
    assert len(qat_agent_helpers.snapshot(depth=0).splitlines()) == 1


def test_a_definition_target_starts_the_tree_at_its_object(use_fake, executable):
    options = widget("QGroupBox", "options", widget("QCheckBox", "autoSave", text="Auto save"))
    launch(use_fake, executable, FakeApp(widget("QMainWindow", "mainWindow", options)))

    lines = qat_agent_helpers.snapshot({"objectName": "options"}).splitlines()

    assert [line.split(" def=")[0] for line in lines] == [
        "- QGroupBox #options",
        '  - QCheckBox #autoSave "Auto save"',
    ]


def test_a_definition_matching_several_objects_lists_them_with_their_definitions(
    use_fake, executable
):
    window = widget(
        "QMainWindow",
        "mainWindow",
        widget("QPushButton", "twinButton", text="Twin A"),
        widget("QPushButton", "twinButton", text="Twin B"),
    )
    launch(use_fake, executable, FakeApp(window))

    with pytest.raises(qat_agent_helpers.AmbiguousDefinitionError) as raised:
        qat_agent_helpers.snapshot({"objectName": "twinButton"})

    assert str(raised.value) == (
        'The definition {"objectName": "twinButton"} matches 2 objects:\n'
        '- QPushButton #twinButton "Twin A" def={"type": "QPushButton", "text": "Twin A"}\n'
        '- QPushButton #twinButton "Twin B" def={"type": "QPushButton", "text": "Twin B"}'
    )
    assert raised.value.candidates == [
        {"type": "QPushButton", "text": "Twin A"},
        {"type": "QPushButton", "text": "Twin B"},
    ]


def test_a_definition_matching_nothing_suggests_a_snapshot(use_fake, executable):
    launch(use_fake, executable, FakeApp(widget("QMainWindow", "mainWindow")))

    with pytest.raises(qat_agent_helpers.NotFoundError, match=r"^No object matches the definition"):
        qat_agent_helpers.snapshot({"objectName": "missing"})


def test_without_an_open_app_snapshot_says_how_to_start_one(use_fake):
    use_fake()

    with pytest.raises(qat_agent_helpers.QatAgentHelpersError, match=r"No app is open: launch one"):
        qat_agent_helpers.snapshot()


def test_the_newest_open_app_is_the_one_shown(use_fake, executable):
    launch(
        use_fake,
        executable,
        FakeApp(widget("QMainWindow", "first")),
        FakeApp(widget("QMainWindow", "second")),
    )

    assert qat_agent_helpers.snapshot().startswith("- QMainWindow #second")


def test_texts_are_quoted_and_escaped_and_long_ones_shortened(use_fake, executable):
    window = widget(
        "QMainWindow",
        "mainWindow",
        widget("QLabel", "", text='Say "hi"\nthen go'),
        widget("QLabel", "", text="a" * 100),
    )
    launch(use_fake, executable, FakeApp(window))

    lines = qat_agent_helpers.snapshot().splitlines()

    assert lines[1].startswith('  - QLabel "Say \\"hi\\"\\nthen go" def=')
    assert lines[2].startswith('  - QLabel "' + "a" * 77 + '..." def=')


def test_a_snapshot_over_the_budget_is_cut_and_says_how_many_objects_are_missing(
    use_fake, executable
):
    labels = [widget("QLabel", f"label{n:04}", text="x" * 40) for n in range(1000)]
    launch(use_fake, executable, FakeApp(widget("QMainWindow", "mainWindow", *labels)))

    snapshot = qat_agent_helpers.snapshot()

    lines = snapshot.splitlines()
    assert len(snapshot) <= BUDGET_CHARS
    shown = len(lines) - 1
    assert lines[-1] == f"{1001 - shown} more objects not shown; narrow with a target or depth."
