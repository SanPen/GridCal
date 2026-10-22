# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import List, Dict, Tuple, TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_page import DynamicEventsPage
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.Editor.dynamic_editor_models import initialize_connected_bus_models_for_editor_assignment
from VeraGrid.Gui.DynamicModelEditor.Plots.dynamic_plots_page import DynamicPlotsPage
from VeraGrid.Gui.DynamicModelEditor.ModelComparison.dynamic_model_comparison_page import DynamicModelComparisonPage
from VeraGrid.Gui.DynamicModelEditor.Workspace.Tabs.dynamic_editor_tab import DynamicEditorTab
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import DynamicEditorEntry
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import build_dynamic_editor_entry
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import get_block_for_entry
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import get_templates_for_entry
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.enumerations import DynamicSimulationMode, DynEditorGraphicsModes

if TYPE_CHECKING:
    from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_workspace_window import DynamicEditorWorkspaceWindow


def _get_page_entry(
        page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage | None,
) -> DynamicEditorEntry | None:
    """
    Return the cached dynamic-editor entry stored on one page widget.

    :param page: Candidate workspace page.
    :return: Cached entry or ``None`` when unavailable.
    """
    if page is None:
        return None
    return page.get_dynamic_editor_entry()


def get_page_mode(
        page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage | None,
) -> DynamicSimulationMode | None:
    """
    Return the cached dynamic-editor mode stored on one page widget.

    :param page: Candidate workspace page.
    :return: Cached mode or ``None`` when unavailable.
    """
    if page is None:
        return None
    return page.get_dynamic_editor_mode()


class DynamicEditorWorkspaceSession(QtCore.QObject):
    """
    Shared state for one family of detachable workspace windows.
    """

    dynamicPlotsChanged = QtCore.Signal(object, object)

    def __init__(self) -> None:
        """
        Initialize the shared session state for one workspace family.

        :param current_theme:
        :return: None.
        """
        super().__init__()
        self._open_workspaces: List[DynamicEditorWorkspaceWindow] = list()
        self._session_pages: Dict[str, DynamicEditorTab] = dict()
        self._event_pages: Dict[tuple[int, DynamicSimulationMode], DynamicEventsPage] = dict()
        self._plot_pages: Dict[tuple[int, DynamicSimulationMode], DynamicPlotsPage] = dict()
        self._comparison_pages: Dict[tuple[int, DynamicSimulationMode], DynamicModelComparisonPage] = dict()
        self._last_mode_by_key_base: Dict[str, DynamicSimulationMode] = dict()
        self._last_active_workspace: DynamicEditorWorkspaceWindow | None = None
        self._pending_drag_page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage | None = None
        self._pending_drag_workspace: DynamicEditorWorkspaceWindow | None = None
        self._retained_workspaces: List[DynamicEditorWorkspaceWindow] = list()
        self._retained_pages: List[DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage] = list()
        self.current_theme: DynEditorGraphicsModes = DynEditorGraphicsModes.DARK

    def register_workspace(self, workspace: "DynamicEditorWorkspaceWindow") -> None:
        """
        Register one live workspace window in this shared session.

        :param workspace: Workspace to register.
        :return: None.
        """
        if workspace not in self._open_workspaces:
            self._open_workspaces.append(workspace)
        if workspace not in self._retained_workspaces:
            self._retained_workspaces.append(workspace)
        self._last_active_workspace = workspace

    def unregister_workspace(self, workspace: "DynamicEditorWorkspaceWindow") -> None:
        """
        Remove one workspace window from this shared session.

        :param workspace: Workspace to unregister.
        :return: None.
        """
        if workspace in self._open_workspaces:
            self._open_workspaces.remove(workspace)
        if workspace in self._retained_workspaces:
            self._retained_workspaces.remove(workspace)
        if self._last_active_workspace is workspace:
            self._last_active_workspace = self._open_workspaces[-1] if self._open_workspaces else None

    def get_open_workspaces(self) -> list["DynamicEditorWorkspaceWindow"]:
        """
        Return the currently open workspaces belonging to this session.

        :return: Open workspaces for this session.
        """
        return list(
            workspace
            for workspace in self._open_workspaces
            if workspace.is_available_for_pages()
        )

    def refresh_dynamic_library_templates(self, circuit: MultiCircuit) -> None:
        """
        Refresh compatible template catalogues in every open editor for a circuit.

        Detached workspace windows belong to the same session, so the refresh
        traverses the complete stable workspace snapshot rather than only the
        most recently active window.

        :param circuit: Circuit whose template catalogue changed.
        :return: None.
        """
        workspaces: List[DynamicEditorWorkspaceWindow] = self.get_open_workspaces()
        workspace: DynamicEditorWorkspaceWindow
        page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage

        # Reuse the established entry and mode resolver for each page. This
        # keeps device compatibility rules in one place and excludes catalogues
        # owned by any other circuit open in the same GUI process.
        for workspace in workspaces:
            for page in workspace.pages_iter():
                if isinstance(page, DynamicEventsPage):
                    pass
                else:
                    entry: DynamicEditorEntry | None = _get_page_entry(page=page)
                    mode: DynamicSimulationMode | None = get_page_mode(page=page)
                    if entry is not None and entry.circuit is circuit and mode is not None:
                        editor: DynamicBlockEditorGUI | None
                        if isinstance(page, DynamicEditorTab):
                            editor = page.editor
                        else:
                            if isinstance(page, DynamicBlockEditorGUI):
                                editor = page
                            else:
                                editor = None

                        if editor is not None:
                            templates: List[ALL_DEV_TYPES] = get_templates_for_entry(
                                entry=entry,
                                mode=mode,
                            )
                            editor.refresh_dynamic_library_templates(
                                templates_list=templates,
                            )
                        else:
                            pass
                    else:
                        pass

    def get_last_active_workspace(self) -> "DynamicEditorWorkspaceWindow | None":
        """
        Return the workspace that should receive newly opened editor tabs.

        :return: Preferred workspace or ``None`` when no window is open.
        """
        if self._last_active_workspace is not None and self._last_active_workspace.is_available_for_pages():
            return self._last_active_workspace

        self._last_active_workspace = None
        available_workspaces: list[DynamicEditorWorkspaceWindow] = self.get_open_workspaces()
        if len(available_workspaces) > 0:
            self._last_active_workspace = available_workspaces[-1]
            return self._last_active_workspace
        return None

    def reset_for_tests(self) -> None:
        """
        Close every workspace and clear all retained session state.

        :return: None.
        """
        # Close from a stable snapshot because each close event unregisters its
        # workspace and pages from this same session.
        workspaces_to_close: List[DynamicEditorWorkspaceWindow] = list(self._open_workspaces)
        workspace_to_close: DynamicEditorWorkspaceWindow | None
        for workspace_to_close in workspaces_to_close:
            workspace_to_close.close()
            workspace_to_close.deleteLater()

        # Drop every Python-side owner before Qt processes DeferredDelete events.
        # Keeping retained pages/workspaces alive while their C++ children are
        # destroyed is unsafe after a long mixed GUI test process.
        self._open_workspaces.clear()
        self._session_pages.clear()
        self._event_pages.clear()
        self._plot_pages.clear()
        self._comparison_pages.clear()
        self._last_mode_by_key_base.clear()
        self._last_active_workspace = None
        self._pending_drag_page = None
        self._pending_drag_workspace = None
        self._retained_workspaces.clear()
        self._retained_pages.clear()
        workspaces_to_close.clear()
        workspace_to_close = None

        # Do not flush the process-wide Qt event queue here. Other GUI tests may
        # own unrelated DeferredDelete events, and processing them from this
        # session-specific reset can destroy C++ objects while their Python test
        # fixtures are still alive. Tests that require immediate destruction
        # explicitly flush DeferredDelete after releasing their own references.

    def can_close_pages(
            self,
            pages: List[DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage],
            parent: QtWidgets.QWidget,
    ) -> bool:
        """Validate a page-closing operation before any page is destroyed.

        Model pages retain their existing per-document guard. Event pages edit
        circuit objects immediately and therefore never need a close prompt.

        :param pages: Complete set of pages affected by the closing operation.
        :param parent: Widget that owns any save or discard prompt.
        :return: Whether the complete closing operation may proceed.
        """
        page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage
        for page in pages:
            if isinstance(page, (DynamicEventsPage, DynamicPlotsPage)):
                # Event and plot pages edit circuit assets immediately and therefore have no close guard.
                pass
            else:
                if not bool(page.can_close_editor(parent)):
                    return False
                else:
                    pass
        return True

    def close_all_for_project_replacement(self, parent: QtWidgets.QWidget) -> bool:
        """Close every dynamic-editor workspace before replacing its project.

        Close guards are evaluated for all pages before any workspace is
        modified. Consequently, rejecting one unapplied-change warning leaves
        the complete editor family and the current circuit untouched.

        :param parent: Main window that owns unapplied-change confirmations.
        :return: ``True`` when every workspace was closed or none was open;
            ``False`` when the user cancelled the replacement.
        """
        # Detachable workspaces share this session, so one stable snapshot
        # covers both the primary window and every detached editor window.
        workspaces_to_close: List[DynamicEditorWorkspaceWindow] = list(self.get_open_workspaces())
        workspace_to_check: DynamicEditorWorkspaceWindow
        pages_to_check: List[DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage] = list()

        # Validate the complete operation first. Closing during this loop would
        # make cancellation in a later detached window only partially effective.
        for workspace_to_check in workspaces_to_close:
            page_to_check: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage
            for page_to_check in workspace_to_check.pages_iter():
                pages_to_check.append(page_to_check)

        if not self.can_close_pages(pages=pages_to_check, parent=parent):
            return False
        else:
            pass

        # Every guard has accepted, so each workspace can now destroy its pages
        # without prompting again. Page teardown also closes block properties.
        workspace_to_close: DynamicEditorWorkspaceWindow
        for workspace_to_close in workspaces_to_close:
            workspace_to_close.close_for_project_replacement()

        # Project-specific routing and mode history must not leak into editors
        # opened later for devices from the replacement circuit.
        self._open_workspaces.clear()
        self._session_pages.clear()
        self._event_pages.clear()
        self._plot_pages.clear()
        self._comparison_pages.clear()
        self._last_mode_by_key_base.clear()
        self._last_active_workspace = None
        self._pending_drag_page = None
        self._pending_drag_workspace = None
        self._retained_workspaces.clear()
        self._retained_pages.clear()
        return True

    def workspace_for_page(
            self,
            page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage,
    ) -> "DynamicEditorWorkspaceWindow | None":
        """
        Locate the workspace that currently owns one editor page.

        :param page: Page to resolve.
        :return: Owning workspace or ``None``.
        """
        workspace: DynamicEditorWorkspaceWindow
        for workspace in self.get_open_workspaces():
            if workspace.index_of_page(page) >= 0:
                return workspace
            else:
                pass

        return None

    def note_page_activated(
            self,
            page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage,
    ) -> None:
        """Record activation and lazily refresh event and plot projections.

        Event reconciliation deliberately happens here, not in the model save
        path. Consequently, saving a model cannot mutate or dirty a hidden
        events tab; the events are regenerated only when the user accesses it.
        :param page: Newly activated page.
        :return: None.
        """
        entry: DynamicEditorEntry | None = _get_page_entry(page)
        mode: DynamicSimulationMode | None = get_page_mode(page)
        workspace: DynamicEditorWorkspaceWindow | None = self.workspace_for_page(page)
        if entry is not None and mode is not None:
            self._last_mode_by_key_base[entry.key_base] = mode
        if workspace is not None:
            self._last_active_workspace = workspace

        if isinstance(page, (DynamicEventsPage, DynamicPlotsPage)):
            page.refresh_from_saved_model()
        else:
            pass

    @staticmethod
    def build_page_tab_title(
            page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage,
    ) -> str:
        """
        Build the tab title shown for one page, including dirty-state marker.

        :param page: Page whose title will be shown.
        :return: User-facing tab title.
        """
        title = str(page.get_dynamic_editor_display_title())
        if page.has_unapplied_changes:
            return f"* {title}"
        return title

    def refresh_open_page_title(
            self,
            page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage,
    ) -> None:
        """
        Refresh the tab title for one open page if its workspace is still alive.

        :param page: Page whose title should be refreshed.
        :return: None.
        """
        workspace = self.workspace_for_page(page)
        if workspace is not None:
            workspace.set_page_tab_title(page, self.build_page_tab_title(page))

    def connect_page_signals(
            self,
            page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage,
    ) -> None:
        """
        Connect long-lived page signals needed by the workspace session.

        :param page: Editor page whose signals will be connected.
        :return: None.
        """
        page.dirtyStateChanged.connect(self._on_page_dirty_state_changed)
        if isinstance(page, DynamicEditorTab):
            page.dynamicPlotDefinitionsChanged.connect(self.notify_dynamic_plots_changed)
        else:
            pass

    def _on_page_dirty_state_changed(self, _dirty: bool) -> None:
        """
        Refresh the sender page title after its dirty state changes.

        :param _dirty: New dirty-state flag emitted by the page.
        :return: None.
        """
        page: QtCore.QObject | None = self.sender()
        if isinstance(page, QtWidgets.QWidget):
            workspace_page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage | None = None
            if isinstance(page, (DynamicBlockEditorGUI, DynamicEditorTab, DynamicEventsPage, DynamicPlotsPage, DynamicModelComparisonPage)):
                workspace_page = page
            else:
                pass
            if workspace_page is not None:
                if isinstance(workspace_page, DynamicEventsPage):
                    event_page: DynamicEventsPage
                    for event_page in self._event_pages.values():
                        self.refresh_open_page_title(event_page)
                else:
                    self.refresh_open_page_title(workspace_page)
            else:
                pass
        else:
            pass

    def resolve_mode(self,
                     entry: DynamicEditorEntry,
                     preferred_mode: DynamicSimulationMode | None = None) -> DynamicSimulationMode:
        """
        Choose the dynamic mode to open for one entry.

        :param entry: Entry being opened.
        :param preferred_mode: Explicit requested mode, if any.
        :return: Mode that should be opened.
        """
        if preferred_mode is not None:
            return preferred_mode
        last_mode = self._last_mode_by_key_base.get(entry.key_base, None)
        if last_mode is not None and last_mode in entry.available_modes:
            return last_mode
        if DynamicSimulationMode.RMS in entry.available_modes:
            return DynamicSimulationMode.RMS
        return entry.available_modes[0]

    def create_page(self, entry: DynamicEditorEntry, mode: DynamicSimulationMode) -> "DynamicEditorTab":
        """
        Instantiate one embedded editor tab for the requested entry and mode.

        :param entry: Entry being edited.
        :param mode: Dynamic mode to open.
        :return: Newly created editor tab.
        """
        # Reconcile persistent interfaces before the tab clones the model and factory.
        initialize_connected_bus_models_for_editor_assignment(
            api_object=entry.api_object, circuit=entry.circuit,
            var_factory=entry.circuit.var_factory, mode=mode,
        )
        page = DynamicEditorTab(
            var_factory=entry.circuit.var_factory,
            block=get_block_for_entry(entry, mode),
            api_object=entry.api_object,
            mode=mode,
            templates_list=get_templates_for_entry(entry, mode),
            circuit=entry.circuit,
            current_theme = self.current_theme
        )
        page.set_dynamic_editor_entry(entry)
        self.connect_page_signals(page)
        self._retained_pages.append(page)
        return page

    def open_entry(self,
                   entry: DynamicEditorEntry,
                   preferred_mode: DynamicSimulationMode | None = None,
                   target_workspace: "DynamicEditorWorkspaceWindow | None" = None) -> "DynamicEditorTab":
        """
        Open one entry in the session, reusing an existing page when possible.

        :param entry: Entry to open.
        :param preferred_mode: Explicit requested mode, if any.
        :param target_workspace: Preferred destination workspace.
        :return: Open editor tab for the requested entry.
        """
        mode = self.resolve_mode(entry, preferred_mode)
        session_key = entry.session_key(mode)
        existing_page = self._session_pages.get(session_key, None)
        if existing_page is not None:
            workspace = self.workspace_for_page(existing_page)
            if workspace is None:
                self.unregister_page(existing_page)
            else:
                workspace.editor_tabs.setCurrentWidget(existing_page)
                workspace.showNormal()
                workspace.raise_()
                workspace.activateWindow()
                self.note_page_activated(existing_page)
                return existing_page

        workspace = target_workspace if target_workspace is not None else self.get_last_active_workspace()
        if workspace is None:
            raise RuntimeError("DynamicEditorWorkspaceSession requires an existing workspace")
        page = self.create_page(entry, mode)
        self._session_pages[session_key] = page
        self._last_mode_by_key_base[entry.key_base] = mode
        workspace.add_editor_page(page, self.build_page_tab_title(page), activate=True)
        self._last_active_workspace = workspace
        return page

    def open_dynamic_editor_for(
            self,
            api_object: ALL_DEV_TYPES,
            circuit: MultiCircuit,
            preferred_mode: DynamicSimulationMode | None = None,
            target_workspace: "DynamicEditorWorkspaceWindow | None" = None
    ) -> "DynamicEditorTab | None":
        """
        Build and open the dynamic-editor entry for one API object.

        :param api_object: Device or template to edit.
        :param circuit: Circuit that owns the device.
        :param preferred_mode: Explicit requested mode, if any.
        :param target_workspace: Preferred destination workspace.
        :return: Open editor tab or ``None`` when no dynamic editor exists.
        """
        entry = build_dynamic_editor_entry(api_object, circuit)
        if entry is None:
            return None
        return self.open_entry(entry, preferred_mode=preferred_mode, target_workspace=target_workspace)

    def create_events_page(
            self,
            circuit: MultiCircuit,
            mode: DynamicSimulationMode,
    ) -> DynamicEventsPage:
        """Create one circuit-wide events page.

        :param circuit: Circuit whose complete event family is edited.
        :param mode: RMS or EMT event family to open.
        :return: New global events page.
        """
        page: DynamicEventsPage = DynamicEventsPage(
            circuit=circuit,
            mode=mode,
        )
        self.connect_page_signals(page=page)
        self._retained_pages.append(page)
        return page

    def open_events_page(
            self,
            circuit: MultiCircuit,
            mode: DynamicSimulationMode,
            target_workspace: "DynamicEditorWorkspaceWindow | None" = None,
    ) -> DynamicEventsPage:
        """Open or focus the unique circuit-wide page for one event family.

        :param circuit: Circuit whose complete events are edited.
        :param mode: RMS or EMT event family to open.
        :param target_workspace: Preferred workspace receiving a new page.
        :return: Open global events page.
        """
        page_key: tuple[int, DynamicSimulationMode] = (id(circuit), mode)
        existing_page: DynamicEventsPage | None = self._event_pages.get(page_key, None)
        if existing_page is not None:
            workspace: DynamicEditorWorkspaceWindow | None = self.workspace_for_page(existing_page)
            if workspace is None:
                self.unregister_page(page=existing_page)
            else:
                existing_page.refresh_from_saved_model()
                workspace.editor_tabs.setCurrentWidget(existing_page)
                workspace.showNormal()
                workspace.raise_()
                workspace.activateWindow()
                self.note_page_activated(page=existing_page)
                return existing_page
        else:
            pass

        workspace = target_workspace if target_workspace is not None else self.get_last_active_workspace()
        if workspace is None:
            raise RuntimeError("DynamicEditorWorkspaceSession requires an existing workspace")
        else:
            pass
        page: DynamicEventsPage = self.create_events_page(circuit=circuit, mode=mode)
        self._event_pages[page_key] = page
        workspace.add_editor_page(page, self.build_page_tab_title(page), activate=True)
        self._last_active_workspace = workspace
        return page

    def create_plots_page(self,
                          circuit: MultiCircuit,
                          mode: DynamicSimulationMode) -> DynamicPlotsPage:
        """Create one circuit-wide persistent plots editor page.

        :param circuit: Circuit that owns the plot definitions.
        :param mode: RMS or EMT plot family.
        :return: Newly created global plots page.
        """
        page: DynamicPlotsPage = DynamicPlotsPage(
            circuit=circuit,
            mode=mode,
            session=self,
        )
        self.connect_page_signals(page=page)
        self._retained_pages.append(page)
        return page

    def open_plots_page(
            self,
            circuit: MultiCircuit,
            mode: DynamicSimulationMode,
            target_workspace: "DynamicEditorWorkspaceWindow | None" = None,
    ) -> DynamicPlotsPage:
        """Open or focus the unique circuit-wide plots page for one family.

        :param circuit: Circuit whose complete dynamic model universe is shown.
        :param mode: RMS or EMT plot family.
        :param target_workspace: Preferred workspace receiving a new page.
        :return: Open global plots page.
        """
        page_key: tuple[int, DynamicSimulationMode] = (id(circuit), mode)
        existing_page: DynamicPlotsPage | None = self._plot_pages.get(page_key, None)
        if existing_page is not None:
            existing_workspace: DynamicEditorWorkspaceWindow | None = self.workspace_for_page(existing_page)
            if existing_workspace is None:
                self.unregister_page(page=existing_page)
            else:
                existing_workspace.editor_tabs.setCurrentWidget(existing_page)
                existing_workspace.showNormal()
                existing_workspace.raise_()
                existing_workspace.activateWindow()
                self.note_page_activated(page=existing_page)
                return existing_page
        else:
            pass

        workspace: DynamicEditorWorkspaceWindow | None = (
            target_workspace if target_workspace is not None else self.get_last_active_workspace()
        )
        if workspace is None:
            raise RuntimeError("DynamicEditorWorkspaceSession requires an existing workspace")
        else:
            pass
        page: DynamicPlotsPage = self.create_plots_page(circuit=circuit, mode=mode)
        self._plot_pages[page_key] = page
        workspace.add_editor_page(page, self.build_page_tab_title(page), activate=True)
        self._last_active_workspace = workspace
        return page

    def notify_dynamic_plots_changed(self,
                                     mode: DynamicSimulationMode,
                                     source: QtCore.QObject) -> None:
        """Broadcast a persistent plot-definition change to all GUI projections.

        :param mode: RMS or EMT family whose assets changed.
        :param source: GUI object that originated the change.
        :return: None.
        """
        self.dynamicPlotsChanged.emit(mode, source)

    def create_comparison_page(
            self,
            circuit: MultiCircuit,
            mode: DynamicSimulationMode,
    ) -> DynamicModelComparisonPage:
        """Create one circuit-wide saved-model comparison page.

        :param circuit: Circuit whose authoritative models are compared.
        :param mode: RMS or EMT model family.
        :return: Newly created comparison page.
        """
        page: DynamicModelComparisonPage = DynamicModelComparisonPage(
            circuit=circuit,
            mode=mode,
        )
        self.connect_page_signals(page=page)
        self._retained_pages.append(page)
        return page

    def open_comparison_page(
            self,
            circuit: MultiCircuit,
            mode: DynamicSimulationMode,
            target_workspace: "DynamicEditorWorkspaceWindow | None" = None,
    ) -> DynamicModelComparisonPage:
        """Open or focus the unique circuit-wide model comparator.

        :param circuit: Circuit whose saved models are compared.
        :param mode: RMS or EMT model family.
        :param target_workspace: Preferred workspace receiving a new page.
        :return: Open comparison page.
        """
        page_key: tuple[int, DynamicSimulationMode] = (id(circuit), mode)
        existing_page: DynamicModelComparisonPage | None = self._comparison_pages.get(page_key, None)
        if existing_page is not None:
            existing_workspace: DynamicEditorWorkspaceWindow | None = self.workspace_for_page(existing_page)
            if existing_workspace is None:
                self.unregister_page(page=existing_page)
            else:
                # Only the explicit comparison-button action may replace the
                # page snapshot. Switching tabs and editor saves stay isolated.
                existing_page.refresh_from_saved_model()
                existing_workspace.editor_tabs.setCurrentWidget(existing_page)
                existing_workspace.showNormal()
                existing_workspace.raise_()
                existing_workspace.activateWindow()
                return existing_page
        else:
            pass

        workspace: DynamicEditorWorkspaceWindow | None = (
            target_workspace if target_workspace is not None else self.get_last_active_workspace()
        )
        if workspace is None:
            raise RuntimeError("DynamicEditorWorkspaceSession requires an existing workspace")
        else:
            pass
        page: DynamicModelComparisonPage = self.create_comparison_page(circuit=circuit, mode=mode)
        self._comparison_pages[page_key] = page
        workspace.add_editor_page(page, self.build_page_tab_title(page), activate=True)
        self._last_active_workspace = workspace
        return page

    def unregister_page(
            self,
            page: DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage,
    ) -> None:
        """
        Forget one page in the session registries.

        :param page: Page being removed.
        :return: None.
        """
        try:
            page.dirtyStateChanged.disconnect(self._on_page_dirty_state_changed)
        except (RuntimeError, TypeError):
            pass
        if isinstance(page, DynamicEditorTab):
            try:
                page.dynamicPlotDefinitionsChanged.disconnect(self.notify_dynamic_plots_changed)
            except (RuntimeError, TypeError):
                pass
        else:
            pass
        entry = _get_page_entry(page)
        mode = get_page_mode(page)
        if isinstance(page, DynamicPlotsPage):
            page_key: tuple[int, DynamicSimulationMode] = (id(page.circuit), page.mode)
            self._plot_pages.pop(page_key, None)
        elif isinstance(page, DynamicModelComparisonPage):
            comparison_page_key: tuple[int, DynamicSimulationMode] = (id(page.circuit), page.mode)
            self._comparison_pages.pop(comparison_page_key, None)
        elif isinstance(page, DynamicEventsPage):
            event_page_key: tuple[int, DynamicSimulationMode] = (id(page.circuit), page.mode)
            self._event_pages.pop(event_page_key, None)
        elif entry is not None and mode is not None:
            self._session_pages.pop(entry.session_key(mode), None)
        else:
            pass

        if page in self._retained_pages:
            self._retained_pages.remove(page)
        else:
            pass

        if self._pending_drag_page is page:
            self._pending_drag_page = None
            self._pending_drag_workspace = None
        else:
            pass

    def handle_tab_drag_started(self, workspace: "DynamicEditorWorkspaceWindow", index: int) -> None:
        """
        Remember which page started a detach or reattach drag gesture.

        :param workspace: Source workspace.
        :param index: Dragged tab index.
        :return: None.
        """
        page = workspace.page_at(index)
        if page is not None:
            self._pending_drag_page = page
            self._pending_drag_workspace = workspace

    def get_pending_tab_drag(
            self,
    ) -> Tuple[DynamicBlockEditorGUI | DynamicEditorTab | DynamicEventsPage | DynamicPlotsPage | DynamicModelComparisonPage | None,
               "DynamicEditorWorkspaceWindow | None"]:
        """
        Return the page and workspace remembered for the current drag gesture.

        :return: Pending dragged page and its source workspace.
        """
        return self._pending_drag_page, self._pending_drag_workspace

    def clear_pending_tab_drag(self) -> None:
        """
        Clear the remembered drag source information.

        :return: None.
        """
        self._pending_drag_page = None
        self._pending_drag_workspace = None

    def set_dark_mode(self):
        """
        Set the dark mode
        :return:
        """
        self.current_theme = DynEditorGraphicsModes.DARK
        for ws in self._open_workspaces:
            ws.set_dark_mode()

    def set_light_mode(self):
        """
                Set the dark mode
                :return:
                """
        self.current_theme = DynEditorGraphicsModes.LIGHT
        for ws in self._open_workspaces:
            ws.set_light_mode()
