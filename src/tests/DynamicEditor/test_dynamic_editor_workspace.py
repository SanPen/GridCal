from __future__ import annotations

import sys

from PySide6 import QtCore, QtGui, QtWidgets
import shiboken6

from VeraGrid.Gui.DynamicModelEditor.Workspace.Tabs.dynamic_editor_tab import DynamicEditorTab
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_page import DynamicEventsPage
from VeraGrid.Gui.DynamicModelEditor.Plots.dynamic_plots_page import DynamicPlotsPage
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_window import DynamicEditorWorkspaceWindow
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import DynamicEditorEntry
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import build_dynamic_editor_entry
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_session import DynamicEditorWorkspaceSession
from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.enumerations import DeviceType, DynamicSimulationMode, FmuTemplateDomain
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var

import VeraGridEngine.api as gce


def _get_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return QtWidgets.QApplication(sys.argv)
    return app


def _build_load_entry():
    circuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    circuit.add_bus(bus)
    load = gce.Load()
    circuit.add_load(bus=bus, api_obj=load)
    entry = build_dynamic_editor_entry(load, circuit)
    assert entry is not None
    return circuit, load, entry


def _build_dc_load_entry():
    circuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="DC Bus 1", Vnom=10.0, is_dc=True)
    circuit.add_bus(bus)
    load = gce.Load()
    circuit.add_load(bus=bus, api_obj=load)
    entry = build_dynamic_editor_entry(load, circuit)
    assert entry is not None
    return circuit, load, entry


def _build_workspace() -> DynamicEditorWorkspaceWindow:
    session = DynamicEditorWorkspaceSession()
    return DynamicEditorWorkspaceWindow(session=session)


def _reset_dynamic_editor_workspaces() -> None:
    """
    Close every dynamic-editor workspace that may still be alive in the test Qt process.

    :return: None.
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        return

    sessions: list[DynamicEditorWorkspaceSession] = list()
    widget: QtWidgets.QWidget
    for widget in app.topLevelWidgets():
        if isinstance(widget, DynamicEditorWorkspaceWindow) and widget.session not in sessions:
            sessions.append(widget.session)

    session: DynamicEditorWorkspaceSession
    for session in sessions:
        session.reset_for_tests()


def test_workspace_reuses_existing_tab_and_remembers_last_mode() -> None:
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit, load, _entry = _build_load_entry()
    workspace = _build_workspace()

    rms_page = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    assert rms_page is not None
    assert workspace.ui.editorTabs.count() == 1

    same_page = workspace.open_dynamic_editor_for(load, circuit)
    assert same_page is rms_page
    assert workspace.ui.editorTabs.count() == 1

    emt_page = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        target_workspace=workspace,
    )
    assert emt_page is not None
    assert emt_page is not rms_page
    assert workspace.ui.editorTabs.count() == 2

    workspace.note_page_activated(emt_page)
    reopened = workspace.open_dynamic_editor_for(load, circuit)
    assert reopened is emt_page

    _reset_dynamic_editor_workspaces()

def test_tree_is_searchable_and_double_click_opens_rms() -> None:
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit, load, entry = _build_load_entry()
    workspace = _build_workspace()

    workspace.open_dynamic_editor_for(load, circuit, preferred_mode=DynamicSimulationMode.RMS)
    proxy_model = workspace.ui.treeView.model()
    assert proxy_model is not None

    parent_index = proxy_model.index(0, 0)
    device_index = proxy_model.index(0, 0, parent_index)
    assert device_index.isValid()

    modes = workspace._get_tree_entry_modes(device_index)
    assert DynamicSimulationMode.RMS in modes
    assert DynamicSimulationMode.EMT in modes

    workspace.ui.searchInTreeLineEdit.setText(entry.display_name[:2].lower())
    filtered_index = workspace.ui.treeView.currentIndex()
    assert filtered_index.isValid()
    assert workspace._entry_from_tree_index(filtered_index) is not None

    workspace._on_tree_double_clicked(filtered_index)
    assert workspace.current_page() is not None
    assert workspace.get_current_block_editor() is not None

    _reset_dynamic_editor_workspaces()


def test_tree_displays_device_icons() -> None:
    """
    Verify that the dynamic-editor tree shows device icons on both group and device rows.

    :return: None.
    """
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit, load, _entry = _build_load_entry()
    workspace = _build_workspace()

    workspace.open_dynamic_editor_for(load, circuit, preferred_mode=DynamicSimulationMode.RMS)
    proxy_model = workspace.ui.treeView.model()
    assert proxy_model is not None

    parent_index = proxy_model.index(0, 0)
    device_index = proxy_model.index(0, 0, parent_index)
    assert parent_index.isValid()
    assert device_index.isValid()

    parent_icon = proxy_model.data(parent_index, QtCore.Qt.ItemDataRole.DecorationRole)
    device_icon = proxy_model.data(device_index, QtCore.Qt.ItemDataRole.DecorationRole)

    assert isinstance(parent_icon, QtGui.QIcon)
    assert isinstance(device_icon, QtGui.QIcon)
    assert not parent_icon.isNull()
    assert not device_icon.isNull()

    _reset_dynamic_editor_workspaces()


def test_workspace_detaches_and_reattaches_tabs_between_windows() -> None:
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit, load, _entry = _build_load_entry()
    workspace = _build_workspace()

    rms_page = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    assert workspace.current_page() is rms_page
    emt_page = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        target_workspace=workspace,
    )

    emt_index = workspace.index_of_page(emt_page)
    workspace._on_tab_drag_started(emt_index)
    workspace._on_tab_detach_requested(workspace.pos())

    assert len(workspace.get_open_workspaces()) == 2
    detached_workspace = workspace.workspace_for_page(emt_page)
    assert detached_workspace is not None
    assert detached_workspace is not workspace
    assert workspace.ui.editorTabs.count() == 1
    assert detached_workspace.ui.editorTabs.count() == 1

    detached_workspace._on_tab_drag_started(detached_workspace.index_of_page(emt_page))
    workspace._on_tab_reattach_requested(workspace.pos(), -1)

    assert workspace.workspace_for_page(emt_page) is workspace
    assert workspace.ui.editorTabs.count() == 2

    _reset_dynamic_editor_workspaces()


def test_project_replacement_closes_all_detached_dynamic_editor_workspaces() -> None:
    """Close all editor pages and windows before their circuit is replaced.

    :return: None.
    """
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit: gce.MultiCircuit
    load: gce.Load
    _entry: DynamicEditorEntry
    circuit, load, _entry = _build_load_entry()
    session: DynamicEditorWorkspaceSession = DynamicEditorWorkspaceSession()
    workspace: DynamicEditorWorkspaceWindow = DynamicEditorWorkspaceWindow(session=session)

    rms_page: DynamicEditorTab | None = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    emt_page: DynamicEditorTab | None = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        target_workspace=workspace,
    )
    assert rms_page is not None
    assert emt_page is not None

    # Detach one page to prove project replacement covers the complete session
    # rather than only the most recently active workspace window.
    emt_index: int = workspace.index_of_page(emt_page)
    workspace._on_tab_drag_started(emt_index)
    workspace._on_tab_detach_requested(workspace.pos())
    assert len(session.get_open_workspaces()) == 2

    replacement_accepted: bool = session.close_all_for_project_replacement(parent=workspace)

    assert replacement_accepted
    assert len(session.get_open_workspaces()) == 0
    assert len(session._session_pages) == 0
    assert rms_page.editor is None
    assert emt_page.editor is None

    _reset_dynamic_editor_workspaces()


def test_workspace_prepare_to_delete_detaches_runtime_widgets() -> None:
    """Detach workspace-owned runtime widgets before Qt final deletion.

    :return: None.
    """
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit: gce.MultiCircuit
    load: gce.Load
    _entry: DynamicEditorEntry
    circuit, load, _entry = _build_load_entry()
    workspace: DynamicEditorWorkspaceWindow = _build_workspace()

    page: DynamicEditorTab | None = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    assert page is not None
    editor_tabs: QtWidgets.QTabWidget = workspace.editor_tabs
    device_tree: QtWidgets.QWidget = workspace.device_tree_widget

    workspace.prepare_to_delete()

    assert not workspace.is_available_for_pages()
    assert workspace.ui.editorTabs.count() == 0
    assert page.editor is None
    assert editor_tabs.parent() is None
    assert device_tree.parent() is None
    assert shiboken6.isValid(editor_tabs)
    assert shiboken6.isValid(device_tree)

    workspace.close()
    workspace.deleteLater()
    _reset_dynamic_editor_workspaces()


def test_workspace_opens_rms_editor_for_dc_bus_load() -> None:
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit, load, _entry = _build_dc_load_entry()
    workspace = _build_workspace()

    rms_page = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )

    assert rms_page is not None
    assert workspace.get_current_block_editor() is not None

    _reset_dynamic_editor_workspaces()


def test_repeated_workspace_teardown_destroys_dynamic_editor_qt_objects() -> None:
    """
    Destroy every editor-owned Qt object across repeated open/close cycles.

    :return: None.
    """
    app: QtWidgets.QApplication = _get_app()
    _reset_dynamic_editor_workspaces()
    iteration: int
    for iteration in range(8):
        circuit, load, _entry = _build_load_entry()
        session = DynamicEditorWorkspaceSession()
        workspace = DynamicEditorWorkspaceWindow(session=session)
        page = workspace.open_dynamic_editor_for(
            load,
            circuit,
            preferred_mode=DynamicSimulationMode.EMT,
            target_workspace=workspace,
        )
        assert page is not None
        editor = page.editor
        assert editor is not None
        scene = editor.scene
        view = editor.view
        assert scene is not None
        assert view is not None

        workspace.close_tab_at(workspace.index_of_page(page))

        assert editor.scene is None
        assert editor.view is None
        assert scene.editor is None
        assert len(scene.items()) == 0
        assert page.editor is None
        assert len(session._session_pages) == 0

        QtCore.QCoreApplication.sendPostedEvents(
            None,
            QtCore.QEvent.Type.DeferredDelete,
        )
        app.processEvents()
        assert not shiboken6.isValid(scene)
        assert not shiboken6.isValid(view)
        assert not shiboken6.isValid(editor)
        assert not shiboken6.isValid(page)

    _reset_dynamic_editor_workspaces()


def test_workspace_hosts_model_and_events_tabs_with_contextual_toolbar() -> None:
    """Keep every workspace action visible for model and events pages.

    :return: None.
    """
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit: gce.MultiCircuit
    load: gce.Load
    entry: DynamicEditorEntry
    circuit, load, entry = _build_load_entry()
    workspace: DynamicEditorWorkspaceWindow = _build_workspace()

    model_page: DynamicEditorTab | None = workspace.open_dynamic_editor_for(
        api_object=load,
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    events_page: DynamicEventsPage = workspace.open_dynamic_events_for(
        circuit=circuit,
        mode=DynamicSimulationMode.RMS,
        target_workspace=workspace,
    )
    reopened_events_page: DynamicEventsPage = workspace.open_dynamic_events_for(
        circuit=circuit,
        mode=DynamicSimulationMode.RMS,
        target_workspace=workspace,
    )

    assert model_page is not None
    assert events_page is reopened_events_page
    assert entry.session_key(DynamicSimulationMode.RMS) in workspace.session._session_pages
    assert workspace.session._event_pages[(id(circuit), DynamicSimulationMode.RMS)] is events_page
    assert workspace.editor_tabs.count() == 2
    assert workspace.editor_tabs.tabText(workspace.index_of_page(model_page)).endswith("[RMS model]")
    assert workspace.editor_tabs.tabText(workspace.index_of_page(events_page)) == "RMS Events"

    toolbar_actions: tuple[QtGui.QAction, ...] = (
        workspace.ui.actionview_tree,
        workspace.ui.actionRMS_Editor,
        workspace.ui.actionRMS_Events,
        workspace.ui.actionEMT_Editor,
        workspace.ui.actionEMT_Events,
        workspace.ui.actionRMS_Plots,
        workspace.ui.actionEMT_Plots,
    )
    workspace.editor_tabs.setCurrentWidget(model_page)
    assert all(action.isVisible() for action in toolbar_actions)
    workspace.editor_tabs.setCurrentWidget(events_page)
    assert all(action.isVisible() for action in toolbar_actions)

    _reset_dynamic_editor_workspaces()


def test_workspace_hosts_one_global_plots_tab_per_simulation_family() -> None:
    """Open circuit-wide plot pages without requiring a contextual device entry.

    :return: None.
    """
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit: gce.MultiCircuit
    load: gce.Load
    entry: DynamicEditorEntry
    circuit, load, entry = _build_load_entry()
    workspace: DynamicEditorWorkspaceWindow = _build_workspace()
    workspace._set_workspace_circuit(circuit=circuit)

    rms_page: DynamicPlotsPage = workspace.open_dynamic_plots_for(
        circuit=circuit,
        mode=DynamicSimulationMode.RMS,
    )
    reopened_rms_page: DynamicPlotsPage = workspace.open_dynamic_plots_for(
        circuit=circuit,
        mode=DynamicSimulationMode.RMS,
    )
    emt_page: DynamicPlotsPage = workspace.open_dynamic_plots_for(
        circuit=circuit,
        mode=DynamicSimulationMode.EMT,
    )

    assert rms_page is reopened_rms_page
    assert emt_page is not rms_page
    assert rms_page.get_dynamic_editor_entry() is None
    assert emt_page.get_dynamic_editor_entry() is None
    assert workspace.editor_tabs.count() == 2
    assert workspace.ui.actionRMS_Plots.isEnabled()
    assert workspace.ui.actionEMT_Plots.isEnabled()
    assert load is entry.api_object


def test_workspace_refreshes_unified_fmu_catalogue_and_preserves_navigation() -> None:
    """
    Verify initial and live FMU catalogue updates use one shared editor list.

    :return: None.
    """
    _get_app()
    _reset_dynamic_editor_workspaces()
    circuit: gce.MultiCircuit
    load: gce.Load
    _entry: DynamicEditorEntry
    circuit, load, _entry = _build_load_entry()

    first_template: FmuTemplate = FmuTemplate(name="FMU before editor open")
    first_template.tpe = DeviceType.LoadDevice
    first_template.domain = FmuTemplateDomain.RMS
    circuit.add_fmu_template(first_template)

    wrong_device_template: FmuTemplate = FmuTemplate(name="Generator-only RMS FMU")
    wrong_device_template.tpe = DeviceType.GeneratorDevice
    wrong_device_template.domain = FmuTemplateDomain.RMS
    circuit.add_fmu_template(wrong_device_template)
    wrong_domain_template: FmuTemplate = FmuTemplate(name="Load EMT FMU")
    wrong_domain_template.tpe = DeviceType.LoadDevice
    wrong_domain_template.domain = FmuTemplateDomain.EMT
    circuit.add_fmu_template(wrong_domain_template)

    workspace: DynamicEditorWorkspaceWindow = _build_workspace()
    page: DynamicEditorTab | None = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    assert page is not None
    editor = page.editor
    assert editor is not None

    match_flags: QtCore.Qt.MatchFlag = (
        QtCore.Qt.MatchFlag.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
    )
    first_start_index: QtCore.QModelIndex = editor.library.library_model.index(0, 0)
    first_matches: list[QtCore.QModelIndex] = editor.library.library_model.match(
        first_start_index,
        QtCore.Qt.ItemDataRole.DisplayRole,
        first_template.name,
        -1,
        match_flags,
    )
    assert len(first_matches) == 1
    assert editor.templates_list == [first_template]

    second_template: FmuTemplate = FmuTemplate(name="FMU after editor open")
    second_template.tpe = DeviceType.LoadDevice
    second_template.domain = FmuTemplateDomain.RMS
    circuit.add_fmu_template(second_template)
    editor.ui.librarySearchLineEdit.setText("FMU")

    workspace.session.refresh_dynamic_library_templates(circuit=circuit)

    refreshed_editor = page.editor
    assert refreshed_editor is editor
    assert refreshed_editor.ui.librarySearchLineEdit.text() == "FMU"
    assert refreshed_editor.templates_list == [first_template, second_template]
    second_start_index: QtCore.QModelIndex = refreshed_editor.library.library_model.index(0, 0)
    first_refreshed_matches: list[QtCore.QModelIndex] = refreshed_editor.library.library_model.match(
        second_start_index,
        QtCore.Qt.ItemDataRole.DisplayRole,
        first_template.name,
        -1,
        match_flags,
    )
    second_refreshed_matches: list[QtCore.QModelIndex] = refreshed_editor.library.library_model.match(
        second_start_index,
        QtCore.Qt.ItemDataRole.DisplayRole,
        second_template.name,
        -1,
        match_flags,
    )
    assert len(first_refreshed_matches) == 1
    assert len(second_refreshed_matches) == 1

    # Navigation rebuilds the hosted editor. The tab-owned list must retain the
    # refreshed catalogue so the replacement Library contains both FMUs once.
    page._replace_editor()
    rebuilt_editor = page.editor
    assert rebuilt_editor is not None
    assert rebuilt_editor is not refreshed_editor
    assert rebuilt_editor.templates_list == [first_template, second_template]
    rebuilt_start_index: QtCore.QModelIndex = rebuilt_editor.library.library_model.index(0, 0)
    rebuilt_first_matches: list[QtCore.QModelIndex] = rebuilt_editor.library.library_model.match(
        rebuilt_start_index,
        QtCore.Qt.ItemDataRole.DisplayRole,
        first_template.name,
        -1,
        match_flags,
    )
    rebuilt_second_matches: list[QtCore.QModelIndex] = rebuilt_editor.library.library_model.match(
        rebuilt_start_index,
        QtCore.Qt.ItemDataRole.DisplayRole,
        second_template.name,
        -1,
        match_flags,
    )
    assert len(rebuilt_first_matches) == 1
    assert len(rebuilt_second_matches) == 1


    _reset_dynamic_editor_workspaces()
