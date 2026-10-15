# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_handler import DynamicEventParameterCandidate
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_handler import DynamicEventsHandler
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_handler import DynamicEventsItemDelegate
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_page_ui import Ui_DynamicEventsPage
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_support import SwitchSequenceData, SwitchSequenceDialog
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import DynamicEditorEntry
from VeraGrid.Gui.dialog_lifecycle import exec_dialog_safely
from VeraGrid.Gui.messages import yes_no_question
from VeraGrid.Gui.toast_widget import ToastManager
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicSimulationMode


class DynamicEventsPage(QtWidgets.QWidget):
    """Edit every RMS or EMT event asset belonging to one circuit."""

    dirtyStateChanged = QtCore.Signal(bool)

    __slots__ = (
        "circuit",
        "mode",
        "ui",
        "toast_manager",
        "handler",
        "events_delegate",
        "_prepared_to_delete",
        "_event_column_widths",
        "_toolbar_leading_spacer",
    )

    def __init__(
            self,
            circuit: MultiCircuit,
            mode: DynamicSimulationMode,
            parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Build one circuit-wide events page.

        :param circuit: Circuit owning the dynamic models and event assets.
        :param mode: RMS or EMT event family.
        :param parent: Optional owning widget.
        :return: None.
        """
        QtWidgets.QWidget.__init__(self, parent)
        self.circuit: MultiCircuit = circuit
        self.mode: DynamicSimulationMode = mode
        self._prepared_to_delete: bool = False
        self._event_column_widths: List[int] = list()
        self.ui: Ui_DynamicEventsPage = Ui_DynamicEventsPage()
        self.ui.setupUi(self)

        # The separator reserves a style-defined extent after the first button,
        # with its line painted in the middle. Insert the same half-extent as a
        # real toolbar item before the button so its exterior blank margins are
        # symmetric. A widget item is required because QToolBar does not apply
        # QWidget content margins to the internal action layout consistently.
        toolbar_separator_extent: int = self.ui.eventsToolBar.style().pixelMetric(
            QtWidgets.QStyle.PixelMetric.PM_ToolBarSeparatorExtent,
            None,
            self.ui.eventsToolBar,
        )
        toolbar_leading_space: int = toolbar_separator_extent // 2
        self._toolbar_leading_spacer: QtWidgets.QWidget = QtWidgets.QWidget(self.ui.eventsToolBar)
        self._toolbar_leading_spacer.setObjectName("eventsToolBarLeadingSpacer")
        self._toolbar_leading_spacer.setFixedWidth(toolbar_leading_space)
        self.ui.eventsToolBar.insertWidget(self.ui.actionNewGroup, self._toolbar_leading_spacer)

        self.toast_manager: ToastManager = ToastManager(parent=self, position_top=False)
        self.handler: DynamicEventsHandler = DynamicEventsHandler(
            circuit=circuit,
            mode=mode,
            parent=self,
        )
        self.events_delegate: DynamicEventsItemDelegate = DynamicEventsItemDelegate(
            handler=self.handler,
            parent=self.ui.eventsTreeView,
        )

        # Stage 1: attach the two independent projections. The left tree is a
        # drag source and the right tree edits the persistent event objects.
        self.ui.parametersTreeView.setModel(self.handler.parameters_proxy)
        self.ui.eventsTreeView.setModel(self.handler.events_proxy)
        self.ui.eventsTreeView.setItemDelegate(self.events_delegate)
        self.ui.eventsTreeView.setDropIndicatorShown(True)
        # Start with interactive sections so the initial proportional layout is
        # preserved instead of being recalculated on every window resize.
        self.ui.eventsTreeView.header().setMinimumSectionSize(65)
        self.ui.eventsTreeView.header().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Interactive,
        )
        # Keep the parameters catalog compact and assign future page growth to
        # the events tree, where the multi-column rows need the available room.
        self.ui.eventsSplitter.setStretchFactor(0, 0)
        self.ui.eventsSplitter.setStretchFactor(1, 1)
        self.ui.eventsSplitter.setSizes([180, 820])
        QtCore.QTimer.singleShot(0, self._set_initial_event_column_widths)
        self.ui.parametersTreeView.collapseAll()
        self.ui.eventsTreeView.expandAll()
        self._apply_group_row_spans()

        # Stage 2: connect every user gesture to one immediate circuit mutation
        # or to one of the independent search proxies.
        self.ui.actionNewGroup.triggered.connect(self.add_event_group)
        self.ui.actionAddEvent.triggered.connect(self.add_event)
        self.ui.actionRemove.triggered.connect(self.remove_selection)
        self.ui.parametersSearchButton.clicked.connect(self.apply_parameters_search)
        self.ui.parametersSearchLineEdit.returnPressed.connect(self.apply_parameters_search)
        self.ui.eventsSearchButton.clicked.connect(self.apply_events_search)
        self.ui.eventsSearchLineEdit.returnPressed.connect(self.apply_events_search)
        self.ui.eventsTreeView.selectionModel().currentChanged.connect(self._on_events_selection_changed)
        self.handler.eventAdded.connect(self._on_event_added)
        self.handler.modelAboutToBeRebuilt.connect(self._save_event_column_widths)
        self.handler.modelRebuilt.connect(self._on_model_rebuilt)
        self._select_first_group()
        self.update_actions()

    @property
    def has_unapplied_changes(self) -> bool:
        """Report no transaction because event edits are immediate.

        :return: Always ``False``.
        """
        return False

    def get_dynamic_editor_entry(self) -> DynamicEditorEntry | None:
        """Return no device entry because this is a circuit-wide page.

        :return: Always ``None``.
        """
        return None

    def get_dynamic_editor_mode(self) -> DynamicSimulationMode:
        """Return the page simulation family.

        :return: RMS or EMT mode.
        """
        return self.mode

    def get_dynamic_editor_display_title(self) -> str:
        """Return the global workspace tab title.

        :return: RMS or EMT events title.
        """
        return f"{self.mode.name} Events"

    def can_close_editor(self, parent: QtWidgets.QWidget | None = None) -> bool:
        """Allow immediate-edit pages to close without a save prompt.

        :param parent: Unused compatibility parent.
        :return: Always ``True``.
        """
        del parent
        return True

    def refresh_from_saved_model(self) -> int:
        """Rescan every device model and rebuild both global trees.

        Existing event assets are never deleted during this refresh. Therefore
        stale device or parameter references remain visible for user repair.

        :return: Zero because there is no draft reconciliation.
        """
        selected_group: RmsEventsGroup | EmtEventsGroup | None = self._selected_group()
        selected_event: RmsEvent | EmtEvent | None = self._selected_event()
        self.handler.refresh()
        if selected_event is not None:
            self._select_event(event=selected_event)
        elif selected_group is not None:
            self._select_group(group=selected_group)
        else:
            self._select_first_group()
        return 0

    @QtCore.Slot()
    def apply_parameters_search(self) -> None:
        """Apply the left parameters-tree search.

        :return: None.
        """
        search_text: str = self.ui.parametersSearchLineEdit.text().strip()
        self.handler.set_parameter_search_text(search_text=search_text)
        self.ui.parametersTreeView.expandAll()

    @QtCore.Slot()
    def apply_events_search(self) -> None:
        """Apply the right events-tree search across every visible column.

        :return: None.
        """
        search_text: str = self.ui.eventsSearchLineEdit.text().strip()
        self.handler.set_events_search_text(search_text=search_text)
        self._apply_group_row_spans()
        self.ui.eventsTreeView.expandAll()

    @QtCore.Slot(bool)
    def add_event_group(self, _checked: bool = False) -> None:
        """Ask for a unique name and create one real event group.

        :param _checked: QAction checked state supplied by Qt.
        :return: None.
        """
        del _checked
        group_name: str
        accepted: bool
        group_name, accepted = QtWidgets.QInputDialog.getText(
            self,
            self.tr("Add Events Group"),
            self.tr("Group name:"),
        )
        normalized_name: str = group_name.strip()
        if accepted and normalized_name != "":
            created_group: RmsEventsGroup | EmtEventsGroup | None = self.handler.create_group(name=normalized_name)
            if created_group is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("Invalid event group"),
                    self.tr("An event group with this name already exists."),
                )
            else:
                self._select_group(group=created_group)
        else:
            pass

    @QtCore.Slot(bool)
    def add_event(self, _checked: bool = False) -> None:
        """Add a default event to the explicitly selected group.

        :param _checked: QAction checked state supplied by Qt.
        :return: None.
        """
        del _checked
        group: RmsEventsGroup | EmtEventsGroup | None = self._selected_group()
        candidate: DynamicEventParameterCandidate | None = self.handler.first_candidate()
        if group is None:
            self.toast_manager.show_warning_toast(self.tr("Select an event group before adding an event."))
        elif candidate is None:
            self.toast_manager.show_warning_toast(self.tr("No device exposes event parameters in this mode."))
        else:
            self.handler.add_candidate_to_group(group=group, candidate=candidate)

    @QtCore.Slot(bool)
    def remove_selection(self, _checked: bool = False) -> None:
        """Remove the selected event or selected group after confirmation.

        :param _checked: QAction checked state supplied by Qt.
        :return: None.
        """
        del _checked
        event: RmsEvent | EmtEvent | None = self._selected_event()
        group: RmsEventsGroup | EmtEventsGroup | None = self._selected_group()
        if event is not None:
            answer: bool = yes_no_question(
                text=self.tr("Remove the selected event?"),
                title=self.tr("Remove event"),
                parent=self,
            )
            if answer:
                parent_group: RmsEventsGroup | EmtEventsGroup | None = event.group
                self.handler.delete_event(event=event)
                if parent_group is not None:
                    self._select_group(group=parent_group)
                else:
                    self._select_first_group()
            else:
                pass
        elif group is not None:
            answer = yes_no_question(
                text=self.tr("Remove '{name}' and all events in this group?").format(name=group.name),
                title=self.tr("Remove event group"),
                parent=self,
            )
            if answer:
                self.handler.delete_group(group=group)
                self._select_first_group()
            else:
                pass
        else:
            self.toast_manager.show_warning_toast(self.tr("Select an event or event group to remove."))

    def _selected_group(self) -> RmsEventsGroup | EmtEventsGroup | None:
        """Return a directly selected top-level group.

        :return: Selected group or ``None`` when an event row is selected.
        """
        current_index: QtCore.QModelIndex = self.ui.eventsTreeView.currentIndex()
        return self.handler.group_from_proxy_index(proxy_index=current_index)

    def _selected_event(self) -> RmsEvent | EmtEvent | None:
        """Return the selected child event.

        :return: Selected event or ``None``.
        """
        current_index: QtCore.QModelIndex = self.ui.eventsTreeView.currentIndex()
        return self.handler.event_from_proxy_index(proxy_index=current_index)

    def _select_group(self, group: RmsEventsGroup | EmtEventsGroup) -> None:
        """Select and expand one group in the filtered right tree.

        :param group: Group to select.
        :return: None.
        """
        index: QtCore.QModelIndex = self.handler.proxy_index_for_group(group=group)
        if index.isValid():
            self.ui.eventsTreeView.setCurrentIndex(index)
            self.ui.eventsTreeView.expand(index)
            self.ui.eventsTreeView.scrollTo(index)
        else:
            pass

    def _select_event(self, event: RmsEvent | EmtEvent) -> None:
        """Select and reveal one event in the filtered right tree.

        :param event: Event to select.
        :return: None.
        """
        index: QtCore.QModelIndex = self.handler.proxy_index_for_event(event=event)
        if index.isValid():
            self.ui.eventsTreeView.expand(index.parent())
            self.ui.eventsTreeView.setCurrentIndex(index)
            self.ui.eventsTreeView.scrollTo(index)
        else:
            pass

    def _select_first_group(self) -> None:
        """Select the first visible event group when one exists.

        :return: None.
        """
        if self.handler.events_proxy.rowCount() > 0:
            first_index: QtCore.QModelIndex = self.handler.events_proxy.index(0, 0)
            self.ui.eventsTreeView.setCurrentIndex(first_index)
            self.ui.eventsTreeView.expand(first_index)
        else:
            self.ui.eventsTreeView.clearSelection()
            self.ui.eventsTreeView.setCurrentIndex(QtCore.QModelIndex())

    @QtCore.Slot(QtCore.QModelIndex, QtCore.QModelIndex)
    def _on_events_selection_changed(
            self,
            _current: QtCore.QModelIndex,
            _previous: QtCore.QModelIndex,
    ) -> None:
        """Refresh action availability after right-tree selection changes.

        :param _current: Newly selected proxy index.
        :param _previous: Previous proxy index.
        :return: None.
        """
        self.update_actions()

    @QtCore.Slot(object)
    def _on_event_added(self, event: object) -> None:
        """Reveal an event created by the toolbar or drag-and-drop.

        :param event: Newly created real event.
        :return: None.
        """
        if isinstance(event, (RmsEvent, EmtEvent)):
            self._select_event(event=event)
        else:
            pass

    @QtCore.Slot()
    def _on_model_rebuilt(self) -> None:
        """Reapply tree presentation after a structural model reset.

        :return: None.
        """
        self._restore_event_column_widths()
        self._apply_group_row_spans()
        self.update_actions()

    def _set_initial_event_column_widths(self) -> None:
        """Fill the initial events viewport with readable weighted columns.

        The resulting sections remain interactive, so later window resizing
        does not alter the widths chosen when the page was first laid out.

        :return: None.
        """
        header: QtWidgets.QHeaderView = self.ui.eventsTreeView.header()
        column_count: int = self.handler.events_model.COLUMN_COUNT
        minimum_width: int = header.minimumSectionSize()
        available_width: int = max(
            self.ui.eventsTreeView.viewport().width(),
            minimum_width * column_count,
        )
        column_weights: List[float] = list((1.5, 1.4, 0.8, 0.9, 0.8, 0.9, 1.1))
        total_weight: float = sum(column_weights)
        extra_width: int = max(available_width - minimum_width * column_count, 0)
        remaining_width: int = available_width
        column_index: int

        # Device and Parameter receive more of the free room while compact
        # scalar properties retain enough width for their labels and values.
        for column_index in range(column_count):
            if column_index < column_count - 1:
                section_width: int = minimum_width + int(
                    extra_width * column_weights[column_index] / total_weight
                )
                remaining_width -= section_width
            else:
                section_width = max(remaining_width, minimum_width)
            header.resizeSection(column_index, section_width)
        self._save_event_column_widths()

    @QtCore.Slot()
    def _save_event_column_widths(self) -> None:
        """Remember the current event-column widths before a model reset.

        :return: None.
        """
        header: QtWidgets.QHeaderView = self.ui.eventsTreeView.header()
        widths: List[int] = list()
        column_index: int
        for column_index in range(header.count()):
            widths.append(header.sectionSize(column_index))
        self._event_column_widths = widths

    def _restore_event_column_widths(self) -> None:
        """Restore the column widths saved immediately before a model reset.

        :return: None.
        """
        header: QtWidgets.QHeaderView = self.ui.eventsTreeView.header()
        if len(self._event_column_widths) == header.count():
            header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
            column_index: int
            for column_index in range(header.count()):
                header.resizeSection(column_index, self._event_column_widths[column_index])
        else:
            pass

    def _apply_group_row_spans(self) -> None:
        """Span each event-group label across the right-tree columns.

        :return: None.
        """
        row_index: int
        for row_index in range(self.handler.events_proxy.rowCount()):
            self.ui.eventsTreeView.setFirstColumnSpanned(row_index, QtCore.QModelIndex(), True)

    def update_actions(self) -> None:
        """Refresh toolbar actions from current selection and candidates.

        :return: None.
        """
        selected_group: RmsEventsGroup | EmtEventsGroup | None = self._selected_group()
        selected_event: RmsEvent | EmtEvent | None = self._selected_event()
        self.ui.actionAddEvent.setEnabled(selected_group is not None and self.handler.first_candidate() is not None)
        self.ui.actionRemove.setEnabled(selected_group is not None or selected_event is not None)

    def _switch_candidates(self) -> List[DynamicEventParameterCandidate]:
        """Return EMT switch-state parameters from every eligible device.

        :return: Ordered switch-sequence targets.
        """
        candidates: List[DynamicEventParameterCandidate] = list()
        candidate: DynamicEventParameterCandidate
        for candidate in self.handler.candidates:
            if candidate.is_mode_parameter and candidate.parameter.name.startswith("switch_closed_mode_"):
                candidates.append(candidate)
            else:
                pass
        return candidates

    @QtCore.Slot(bool)
    def open_switch_sequence(self, _checked: bool = False) -> None:
        """Create an EMT switching sequence for the selected global parameter.

        :param _checked: QAction checked state supplied by Qt.
        :return: None.
        """
        del _checked
        switch_candidates: List[DynamicEventParameterCandidate] = self._switch_candidates()
        mode_parameters: List[Var] = list()
        candidate: DynamicEventParameterCandidate
        for candidate in switch_candidates:
            mode_parameters.append(candidate.parameter)
        groups: List[EmtEventsGroup] = list(self.circuit.emt_events_groups)
        if self.mode == DynamicSimulationMode.EMT and len(mode_parameters) > 0 and len(groups) > 0:
            dialog: SwitchSequenceDialog = SwitchSequenceDialog(
                mode_parameters=mode_parameters,
                events_groups=groups,
                parent=self,
            )
            if exec_dialog_safely(dialog=dialog) == QtWidgets.QDialog.DialogCode.Accepted:
                sequence_data: SwitchSequenceData | None = dialog.get_typed_data()
                if sequence_data is not None:
                    target_candidate: DynamicEventParameterCandidate | None = None
                    for candidate in switch_candidates:
                        if candidate.parameter is sequence_data.parameter:
                            target_candidate = candidate
                        else:
                            pass
                    if target_candidate is not None:
                        self._create_switch_sequence(
                            candidate=target_candidate,
                            sequence_data=sequence_data,
                        )
                    else:
                        pass
                else:
                    pass
            else:
                pass
        else:
            pass

    def _create_switch_sequence(
            self,
            candidate: DynamicEventParameterCandidate,
            sequence_data: SwitchSequenceData,
    ) -> None:
        """Create every real EMT event represented by a wizard payload.

        :param candidate: Device and mode parameter selected by the wizard.
        :param sequence_data: Ordered times, values and target group.
        :return: None.
        """
        last_event: EmtEvent | None = None
        sequence_count: int = min(len(sequence_data.times), len(sequence_data.values))
        sequence_index: int
        for sequence_index in range(sequence_count):
            last_event = EmtEvent(
                name=f"EMT event {len(self.circuit.emt_events)}",
                device=candidate.device,
                parameter=candidate.parameter,
                time=float(sequence_data.times[sequence_index]),
                value=float(sequence_data.values[sequence_index]),
                group=sequence_data.group,
                force_step_alignment=True,
                transition_type=DynamicEventTransitionType.Step,
            )
            self.circuit.add_emt_event(obj=last_event)
        self.handler.rebuild_events_model()
        if last_event is not None:
            self._select_event(event=last_event)
        else:
            pass

    def set_dark_mode(self) -> None:
        """Refresh both tree viewports after a dark-theme change.

        :return: None.
        """
        self.ui.parametersTreeView.viewport().update()
        self.ui.eventsTreeView.viewport().update()

    def set_light_mode(self) -> None:
        """Refresh both tree viewports after a light-theme change.

        :return: None.
        """
        self.ui.parametersTreeView.viewport().update()
        self.ui.eventsTreeView.viewport().update()

    def prepare_to_delete(self) -> None:
        """Disconnect long-lived signals and release model references.

        :return: None.
        """
        if self._prepared_to_delete:
            return
        else:
            pass
        self._prepared_to_delete = True
        self._toolbar_leading_spacer.deleteLater()
        selection_model: QtCore.QItemSelectionModel | None = self.ui.eventsTreeView.selectionModel()
        if selection_model is not None:
            try:
                selection_model.currentChanged.disconnect(self._on_events_selection_changed)
            except (RuntimeError, TypeError):
                pass
        else:
            pass
        self.ui.parametersTreeView.setModel(None)
        self.ui.eventsTreeView.setModel(None)
        self.handler.parameters_proxy.setSourceModel(None)
        self.handler.events_proxy.setSourceModel(None)
