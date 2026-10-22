# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from PySide6 import QtCore, QtWidgets, QtGui
from typing import Union, Dict

from VeraGrid.Gui.DynamicModelEditor.Plots.dynamic_plots_handler import (
    DynamicsResultsHandler)
from VeraGrid.Gui.table_view_header_wrap import HeaderViewWithWordWrap
import VeraGrid.Gui.gui_functions as gf
from VeraGrid.Gui.messages import error_msg, warning_msg, yes_no_question
from VeraGrid.Gui.Main.SubClasses.simulations import SimulationsMain
from VeraGrid.Gui.results_model import ResultsModel
from VeraGrid.Gui.general_dialogues import fill_tree_from_logs
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely, exec_dialog_safely
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.PlotDialogue.result_table_data import get_result_table_series, get_result_table_xy
from VeraGrid.Gui.PlotDialogue.qt_chart_widget import GraphsWidget, PolarAngleUnit
import VeraGridEngine.Utils.Filtering as flt
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (ResultTypes, SimulationTypes, PlotSimulationType, DynamicPlotEntryKind,
                                         DynamicPlotMode, DynamicSimulationMode, ResultTablePlotType)
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Devices.Events.dynamic_plot_entry import DynamicPlotEntry
from VeraGridEngine.Simulations.results_table import ResultsTable


class ResultsMain(SimulationsMain):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        SimulationsMain.__init__(self, parent)

        self.results_mdl: Union[None, ResultsModel] = None

        self.current_results_logger: Union[None, Logger] = None

        self.dynamic_results_handler: DynamicsResultsHandler | None = None
        self.dynamic_results_handlers: Dict[SimulationTypes, DynamicsResultsHandler] = dict()

        # --------------------------------------------------------------------------------------------------------------
        self.ui.actionSet_OPF_generation_to_profiles.triggered.connect(self.copy_opf_to_profiles)

        # Buttons
        self.ui.saveResultsButton.clicked.connect(self.save_results_df)
        self.ui.copy_results_pushButton.clicked.connect(self.copy_results_data)
        self.ui.copy_numpy_button.clicked.connect(self.copy_results_data_as_numpy)
        self.ui.plot_data_pushButton.clicked.connect(self.plot_results)
        self.ui.search_results_Button.clicked.connect(self.search_in_results)
        self.ui.search_dynamic_objects_Button.clicked.connect(self.search_dynamic_objects)
        self.ui.addDynamicPlotButton.clicked.connect(self.add_dynamic_plot_group)
        self.ui.deleteDynamicPlotButton.clicked.connect(self.delete_dynamic_plot_entry)
        self.ui.dynamicsTablePlotButton.clicked.connect(self.plot_dynamic_plot_entry)
        self.ui.saveResultsLogsButton.clicked.connect(self.save_results_logs)

        # tree-click
        self.ui.results_treeView.clicked.connect(self.results_tree_view_click)
        self.ui.dynamicsDeviceTreeView.clicked.connect(self.dynamic_results_tree_view_click)
        self.ui.dynamicsPlotsTreeView.clicked.connect(self.dynamic_plots_tree_view_click)

        # tree double click
        self.ui.dynamicsDeviceTreeView.doubleClicked.connect(self.dynamic_results_tree_view_dbl_click)
        self.ui.dynamicsPlotsTreeView.doubleClicked.connect(self.dynamic_plots_tree_view_dbl_click)

        # The plots tree exposes group actions through a context menu so the
        # double-click interaction can remain dedicated to plotting.
        self.ui.results_treeView.customContextMenuRequested.connect(self.show_results_tree_context_menu)
        self.ui.results_treeView.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.dynamicsPlotsTreeView.customContextMenuRequested.connect(self.show_dynamic_plots_context_menu)
        self.ui.dynamicsPlotsTreeView.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # line edit enter
        self.ui.search_results_lineEdit.returnPressed.connect(self.search_in_results)
        self.ui.search_dynamic_objects_lineEdit.returnPressed.connect(self.search_dynamic_objects)

        # wrap headers
        self.ui.resultsTableView.setHorizontalHeader(HeaderViewWithWordWrap(self.ui.resultsTableView))

        # The device tree exports variables through drag-and-drop.
        self.ui.dynamicsDeviceTreeView.setDragEnabled(True)
        self.ui.dynamicsDeviceTreeView.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragOnly)
        self.ui.dynamicsDeviceTreeView.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)

        # The plots tree accepts dropped variables into top-level plot groups.
        self.ui.dynamicsPlotsTreeView.setAcceptDrops(True)
        self.ui.dynamicsPlotsTreeView.setDropIndicatorShown(True)
        self.ui.dynamicsPlotsTreeView.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DropOnly)
        self.ui.dynamicsPlotsTreeView.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)

        # Results never acts as the pre-simulation editor. Keep its Dynamics tab
        # hidden until the selected study owns actual RMS or EMT result arrays.
        dynamics_tab_index: int = self.ui.resultsTabWidget.indexOf(self.ui.tab_5)
        if dynamics_tab_index >= 0:
            self.ui.resultsTabWidget.setTabVisible(dynamics_tab_index, False)
        else:
            pass
        self.dynamic_editor_workspace_session.dynamicPlotsChanged.connect(
            self._on_external_dynamic_plot_assets_changed
        )

    def results_tree_view_click(self, index: QtGui.QStandardItem):
        """
        Display the simulation results on the result's table
        :param index: Clicked Tree index
        """
        tree_mdl = self.ui.results_treeView.model()
        item = tree_mdl.itemFromIndex(index)
        study_type: SimulationTypes | None = self.get_results_tree_study_type(item=item)

        if study_type is not None:
            driver = self.session.get_driver(driver_type=study_type)

            if driver is None:
                # set the logs
                self.current_results_logger = None
                self.ui.resultsLogsTreeView.setModel(None)
                self.clear_dynamic_results_view()
                return

            if driver.results is None:
                # set the logs
                self.current_results_logger = None
                self.ui.resultsLogsTreeView.setModel(None)
                self.clear_dynamic_results_view()
                return

            # set the logs
            self.current_results_logger = driver.logger
            logs_mdl = fill_tree_from_logs(driver.logger)
            self.ui.resultsLogsTreeView.setModel(logs_mdl)
            self.ui.resultsLogsTreeView.expandAll()

            # set the report
            self.ui.resultsReportTextEdit.setText(driver.results.report_text)

            # set the dynamics model handler
            if driver.tpe == SimulationTypes.RmsDynamic_run:
                self.dynamic_results_handler = self.get_or_create_dynamic_results_handler(
                    study_type=study_type,
                    results=driver.results
                )

                if self._dynamic_views_already_attached():
                    self.ui.dynamicsPlotsTreeView.update()
                else:
                    self._refresh_dynamic_tree_models(expand_plots_when_empty=True, clear_table=False)

                self._set_dynamic_results_tab_visible(visible=True)
                dynamics_tab_index: int = self.ui.resultsTabWidget.indexOf(self.ui.tab_5)
                self.ui.resultsTabWidget.setCurrentIndex(dynamics_tab_index)


            elif driver.tpe == SimulationTypes.EmtDynamic_run:

                self.dynamic_results_handler = self.get_or_create_dynamic_results_handler(
                    study_type=study_type,
                    results=driver.results
                )

                if self._dynamic_views_already_attached():
                    self.ui.dynamicsPlotsTreeView.update()
                else:
                    self._refresh_dynamic_tree_models(expand_plots_when_empty=True, clear_table=False)
                self._set_dynamic_results_tab_visible(visible=True)
                dynamics_tab_index = self.ui.resultsTabWidget.indexOf(self.ui.tab_5)
                self.ui.resultsTabWidget.setCurrentIndex(dynamics_tab_index)

            else:
                # Go to the Table tab
                self.ui.resultsTabWidget.setCurrentIndex(0)
                self.clear_dynamic_results_view()

            result_type: ResultTypes | None = self.get_results_tree_result_type(item=item)
            if result_type is not None:
                study_results = self.available_results_dict.get(study_type, None)

                if study_results is not None:

                    study_result_type: ResultTypes = study_results.get(result_type, None)

                    if study_result_type is not None:

                        self.results_mdl = self.session.get_results_model(driver_type=study_type,
                                                                          result_type=study_result_type)

                        if self.results_mdl is not None:

                            # pass the matching list of devices to the ResultsModel and ResultsTable for filtering
                            self.results_mdl.table.set_col_devices(
                                devices_list=self.circuit.get_elements_by_type(self.results_mdl.table.cols_device_type)
                            )
                            self.results_mdl.table.set_idx_devices(
                                devices_list=self.circuit.get_elements_by_type(self.results_mdl.table.idx_device_type)
                            )

                            if self.ui.results_traspose_checkBox.isChecked():
                                self.results_mdl.transpose()

                            if self.ui.results_as_abs_checkBox.isChecked():
                                self.results_mdl.convert_to_abs()

                            if self.ui.results_as_cdf_checkBox.isChecked():
                                self.results_mdl.convert_to_cdf()

                            # set the table model
                            self.ui.resultsTableView.setModel(self.results_mdl)
                            self.ui.units_label.setText(self.results_mdl.units)

                        else:
                            self.ui.resultsTableView.setModel(None)
                            self.ui.units_label.setText("")

                    else:
                        self.ui.resultsTableView.setModel(None)
                        self.ui.units_label.setText("")

                else:
                    self.ui.resultsTableView.setModel(None)
                    self.ui.units_label.setText("")

            else:
                pass

        else:
            # set the logs
            self.current_results_logger = None
            self.ui.resultsLogsTreeView.setModel(None)
            self.clear_dynamic_results_view()

    def get_results_tree_study_type(self, item: QtGui.QStandardItem | None) -> SimulationTypes | None:
        """
        Resolve a results tree item to its simulation type.

        :param item: Tree item.
        :return: Simulation type or None.
        """
        current_item: QtGui.QStandardItem | None = item
        while current_item is not None:
            item_data: object = current_item.data(QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(item_data, SimulationTypes):
                return item_data
            else:
                current_item = current_item.parent()
        return None

    def get_results_tree_result_type(self, item: QtGui.QStandardItem | None) -> ResultTypes | None:
        """
        Resolve a results tree item to its result type.

        :param item: Tree item.
        :return: Result type or None.
        """
        if item is not None:
            item_data: object = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(item_data, ResultTypes):
                return item_data
            else:
                return None
        else:
            return None

    def dynamic_results_tree_view_click(self, index: QtCore.QModelIndex) -> Var | None:
        """
        Resolve the clicked dynamics tree node into an RMS/EMT variable.

        :param index: Clicked tree index.
        """
        # The handler owns the mapping between tree nodes and simulation variable objects.
        if self.dynamic_results_handler is not None:
            source_index: QtCore.QModelIndex = self.dynamic_results_handler.map_to_source(index=index)
            selected_var = self.dynamic_results_handler.get_var_from_index(index=source_index)
            if selected_var is not None:
                print(selected_var)
                return selected_var
            else:
                return None
        else:
            return None

    def dynamic_results_tree_view_dbl_click(self, index: QtCore.QModelIndex) -> None:
        """

        :param index:
        :return:
        """
        # The handler owns the mapping between tree nodes and simulation variable objects.
        if self.dynamic_results_handler is not None:
            source_index: QtCore.QModelIndex = self.dynamic_results_handler.map_to_source(index=index)
            selected_series = self.dynamic_results_handler.get_series_from_index(index=source_index)
            if selected_series is not None:
                self.dynamic_results_handler.plot_series(series=selected_series)
                return None
            else:
                parameter_entry: DynamicPlotEntry | None = self.dynamic_results_handler.get_parameter_entry_from_index(
                    index=source_index
                )
                if parameter_entry is not None:
                    parameter_was_plotted: bool = self.dynamic_results_handler.plot_parameter_entry(
                        entry=parameter_entry
                    )
                    if parameter_was_plotted:
                        pass
                    else:
                        warning_msg(
                            self.tr("The selected parameter has no numerical value in these dynamic results."),
                            self.tr("Dynamic parameter unavailable"),
                        )
                    return None
                else:
                    pass

                selected_candidate = self.dynamic_results_handler.get_candidate_from_index(index=source_index)
                if selected_candidate is not None:
                    if selected_candidate.get_entry_kind() == DynamicPlotEntryKind.PARAMETER:
                        self.dynamic_results_handler.plot_parameter_candidate(candidate=selected_candidate)
                        return None
                    else:
                        return None
                else:
                    return None
        else:
            return None

    def show_results_tree_context_menu(self, pos: QtCore.QPoint) -> None:
        """
        Display the context menu for the results tree.

        :param pos: Local click position in the tree view.
        :return: None.
        """
        index: QtCore.QModelIndex = self.ui.results_treeView.indexAt(pos)

        if index.isValid():
            self.ui.results_treeView.setCurrentIndex(index)
            menu: QtWidgets.QMenu = QtWidgets.QMenu(self.ui.results_treeView)
            gf.add_menu_entry(menu=menu,
                              text=self.tr("Delete driver"),
                              icon_path=":/Icons/icons/minus.png",
                              function_ptr=self.delete_results_driver)
            menu.exec(self.ui.results_treeView.viewport().mapToGlobal(pos))
        else:
            pass

    def dynamic_plots_tree_view_dbl_click(self, index: QtCore.QModelIndex) -> None:
        """
        Plot the selected plots-tree entry on double click.

        :param index:
        :return: Nothing.
        """
        del index
        self.plot_dynamic_plot_entry()

    def dynamic_plots_tree_view_click(self, index: QtCore.QModelIndex) -> None:
        """
        Refresh the dynamics table for the selected plot entry.

        :param index: Selected plots-tree index.
        :return: Nothing.
        """
        del index
        if self.dynamic_results_handler is not None:
            selected_indexes = self.ui.dynamicsPlotsTreeView.selectedIndexes()
            if len(selected_indexes) > 0:
                # The selected plot entry already stores source-specific series,
                # so table reconstruction no longer needs a separate selector.
                mdl: ResultsModel | None = self.dynamic_results_handler.get_data_from_plot_index(
                    index=selected_indexes[0]
                )

                self.ui.dynamicsTableView.setModel(mdl)
            else:
                pass
        else:
            pass

    def _refresh_dynamic_tree_models(self,
                                     expand_plots_when_empty: bool,
                                     clear_table: bool) -> None:
        """
        Refresh the dynamic tree widgets while preserving semantic state.

        :param expand_plots_when_empty: Expand all plot groups only when no prior state exists.
        :param clear_table: Clear the dynamics table model after refresh when requested.
        :return: Nothing.
        """
        if self.dynamic_results_handler is not None:
            self.ui.dynamicsDeviceTreeView.setModel(self.dynamic_results_handler.get_view_model())
            self.ui.dynamicsPlotsTreeView.setModel(self.dynamic_results_handler.get_plots_model())

            if expand_plots_when_empty:
                self.ui.dynamicsPlotsTreeView.expandAll()
            else:
                pass

            if clear_table:
                self.ui.dynamicsTableView.setModel(None)
            else:
                pass
        else:
            pass

    def _dynamic_views_already_attached(self) -> bool:
        """
        Check whether the current handler models are already attached to the two dynamic tree views.

        :return: ``True`` when both views already show the current handler models.
        """
        if self.dynamic_results_handler is not None:
            current_device_model: QtCore.QAbstractItemModel | None = self.ui.dynamicsDeviceTreeView.model()
            current_plots_model: QtCore.QAbstractItemModel | None = self.ui.dynamicsPlotsTreeView.model()

            if current_device_model is self.dynamic_results_handler.get_view_model():
                if current_plots_model is self.dynamic_results_handler.get_plots_model():
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False

    def _expand_plot_drop_parent(self, parent: QtCore.QModelIndex) -> None:
        """
        Expand the plot-group row targeted by a drop operation.

        :param parent: Parent index reported by the plots model.
        :return: Nothing.
        """
        if parent.isValid():
            self.ui.dynamicsPlotsTreeView.setExpanded(parent, True)
        else:
            pass

    def show_dynamic_plots_context_menu(self, pos: QtCore.QPoint) -> None:
        """
        Show the context menu for the dynamics plots tree.

        :param pos: Click position in viewport coordinates.
        :return: Nothing.
        """
        # The context menu is only meaningful when a handler exists because the
        # handler owns the mapping between view indexes and plot-group objects.
        if self.dynamic_results_handler is not None:
            index: QtCore.QModelIndex = self.ui.dynamicsPlotsTreeView.indexAt(pos)
            if index.isValid():
                plots_model = self.dynamic_results_handler.get_plots_model()
                item: QtGui.QStandardItem | None = plots_model.itemFromIndex(index)
                if item is not None:
                    if item.parent() is None:
                        menu: QtWidgets.QMenu = QtWidgets.QMenu(parent=self.ui.dynamicsPlotsTreeView)
                        rename_action: QtGui.QAction = menu.addAction(self.tr("Rename group"))
                        selected_action: QtGui.QAction | None = menu.exec_(
                            self.ui.dynamicsPlotsTreeView.viewport().mapToGlobal(pos)
                        )
                        if selected_action == rename_action:
                            self.rename_dynamic_plot_group(index=index)
                        else:
                            pass
                    else:
                        menu = QtWidgets.QMenu(parent=self.ui.dynamicsPlotsTreeView)
                        rename_action = menu.addAction(self.tr("Rename variable"))
                        selected_action = menu.exec_(
                            self.ui.dynamicsPlotsTreeView.viewport().mapToGlobal(pos)
                        )
                        if selected_action == rename_action:
                            self.rename_dynamic_plot_variable(index=index)
                        else:
                            pass
                else:
                    pass
            else:
                pass
        else:
            pass

    def rename_dynamic_plot_group(self, index: QtCore.QModelIndex) -> None:
        """
        Rename the selected dynamics plot group.

        :param index: Selected top-level plot-group index.
        :return: Nothing.
        """
        # The selected index is translated through the handler so the GUI keeps
        # all plot-group state changes centralized in the handler layer.
        if self.dynamic_results_handler is not None:
            old_name: str | None = self.dynamic_results_handler.get_plot_group_name_from_index(index=index)
            if old_name is not None:
                new_name: str
                accepted: bool
                new_name, accepted = QtWidgets.QInputDialog.getText(
                    self,
                    self.tr("Rename dynamic plot"),
                    self.tr("Plot name"),
                    text=old_name
                )
                if accepted:
                    renamed: bool = self.dynamic_results_handler.rename_plot_group(old_name=old_name,
                                                                                   new_name=new_name)
                    if renamed:
                        self.ui.dynamicsPlotsTreeView.update()
                        self._notify_current_dynamic_plot_assets_changed()
                    else:
                        self.show_warning_toast(self.tr("The plot group name is empty or already exists."))
                else:
                    pass
            else:
                self.show_warning_toast(self.tr("Select a plot group first."))
        else:
            self.show_warning_toast(self.tr("There are no RMS dynamics results loaded."))

    def rename_dynamic_plot_variable(self, index: QtCore.QModelIndex) -> None:
        """
        Rename the selected dynamics plot variable.

        :param index: Selected child plot-entry index.
        :return: Nothing.
        """
        if self.dynamic_results_handler is not None:
            plots_model = self.dynamic_results_handler.get_plots_model()
            item: QtGui.QStandardItem | None = plots_model.itemFromIndex(index)
            if item is not None:
                current_name: str = item.text()
                missing_suffix: str = " [missing]"
                pending_suffix: str = " [pending]"

                if current_name.endswith(missing_suffix):
                    current_name = current_name[:-len(missing_suffix)]
                else:
                    pass

                if current_name.endswith(pending_suffix):
                    current_name = current_name[:-len(pending_suffix)]
                else:
                    pass

                new_name: str
                accepted: bool
                new_name, accepted = QtWidgets.QInputDialog.getText(
                    self,
                    self.tr("Rename dynamic variable"),
                    self.tr("Variable name"),
                    text=current_name
                )
                if accepted:
                    renamed: bool = self.dynamic_results_handler.rename_plot_variable_from_index(
                        index=index,
                        new_name=new_name,
                    )
                    if renamed:
                        self.ui.dynamicsPlotsTreeView.update()
                        self._notify_current_dynamic_plot_assets_changed()
                    else:
                        self.show_warning_toast(self.tr("The variable name is empty or could not be changed."))
                else:
                    pass
            else:
                self.show_warning_toast(self.tr("Select a variable first."))
        else:
            self.show_warning_toast(self.tr("There are no RMS dynamics results loaded."))

    def expand_dynamic_plots_tree(self,
                                  parent: QtCore.QModelIndex,
                                  first: int,
                                  last: int) -> None:
        """
        Expand the dynamics plots tree after inserting rows.

        :param parent: Parent index where rows were inserted.
        :param first: First inserted row.
        :param last: Last inserted row.
        :return: Nothing.
        """

        # A row insertion already happened inside the existing model. Rebuilding
        # the views here would destroy the exact expansion state we are trying to
        # preserve. The only required post-insert action is to keep the target
        # parent visible so the newly dropped entry remains in view.
        self._expand_plot_drop_parent(parent=parent)

        del parent
        del first
        del last

    def add_dynamic_plot_group(self) -> None:
        """
        Create a new dynamics plot group.

        :return: Nothing.
        """
        if self.dynamic_results_handler is not None:
            suggested_name: str = self.dynamic_results_handler.get_next_group_name()
            dialog: QtWidgets.QDialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(self.tr("New dynamic plot"))
            layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(dialog)
            name_label: QtWidgets.QLabel = QtWidgets.QLabel(self.tr("Plot name"), dialog)
            name_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(dialog)
            mode_label: QtWidgets.QLabel = QtWidgets.QLabel(self.tr("Plot mode"), dialog)
            mode_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(dialog)
            buttons: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
                dialog)
            name_edit.setText(suggested_name)
            mode_combo.addItem(self.tr("Time Series (Y vs Time)"), DynamicPlotMode.TIME_SERIES)
            mode_combo.addItem(self.tr("X-Y Plot (Y vs X)"), DynamicPlotMode.XY)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(name_label)
            layout.addWidget(name_edit)
            layout.addWidget(mode_label)
            layout.addWidget(mode_combo)
            layout.addWidget(buttons)
            try:
                accepted: bool = exec_dialog_safely(dialog=dialog) == QtWidgets.QDialog.DialogCode.Accepted
                if accepted:
                    group_name: str = name_edit.text()
                    selected_mode_data: object = mode_combo.currentData()
                    selected_mode: DynamicPlotMode = DynamicPlotMode.TIME_SERIES
                    if isinstance(selected_mode_data, DynamicPlotMode):
                        selected_mode = selected_mode_data
                    else:
                        pass
                    created: bool = self.dynamic_results_handler.create_plot_group(name=group_name, mode=selected_mode)
                    if created:
                        self.ui.dynamicsPlotsTreeView.expandAll()
                        self._notify_current_dynamic_plot_assets_changed()
                    else:
                        self.show_warning_toast(self.tr("The plot group name is empty or already exists."))
                else:
                    pass
            finally:
                delete_dialog_safely(dialog=dialog)
        else:
            self.show_warning_toast(self.tr("There are no RMS dynamics results loaded."))

    def delete_dynamic_plot_entry(self) -> None:
        """
        Delete the selected dynamics plot group or variable.

        :return: Nothing.
        """
        if self.dynamic_results_handler is not None:
            selected_indexes = self.ui.dynamicsPlotsTreeView.selectedIndexes()
            if len(selected_indexes) > 0:
                deleted: bool = self.dynamic_results_handler.delete_plot_entry_from_index(index=selected_indexes[0])
                if deleted:
                    self.ui.dynamicsPlotsTreeView.update()
                    self._notify_current_dynamic_plot_assets_changed()
                else:
                    self.show_warning_toast(self.tr("The selected dynamic plot entry could not be deleted."))
            else:
                self.show_warning_toast(self.tr("Select a plot group or variable first."))
        else:
            self.show_warning_toast(self.tr("There are no RMS dynamics results loaded."))

    def plot_dynamic_plot_entry(self) -> None:
        """
        Plot the selected dynamics plot group or variable.

        :return: Nothing.
        """
        if self.dynamic_results_handler is not None:
            selected_indexes = self.ui.dynamicsPlotsTreeView.selectedIndexes()
            if len(selected_indexes) > 0:
                # Plotting uses the event-group information stored with each
                # series, so there is no separate event-group control anymore.
                plotted: bool = self.dynamic_results_handler.plot_entry_from_index(index=selected_indexes[0])
                if plotted:
                    return None
                else:
                    self.show_warning_toast(self.tr("The selected dynamic plot entry could not be plotted."))
                    return None
            else:
                self.show_warning_toast(self.tr("Select a plot group or variable first."))
                return None
        else:
            self.show_warning_toast(self.tr("There are no RMS dynamics results loaded."))
            return None

    def search_dynamic_objects(self) -> None:
        """
        Filter the dynamics tree view using the text entered by the user.

        :return: Nothing.
        """
        # Without an active handler, there is no loaded dynamics tree to search.
        if self.dynamic_results_handler is not None:
            search_text: str = self.ui.search_dynamic_objects_lineEdit.text().strip()
            self.dynamic_results_handler.set_search_text(search_text=search_text)

            # Expanding after filtering keeps matching branches visible, and resetting the filter remains trivial.
            self.ui.dynamicsDeviceTreeView.expandAll()
        else:
            pass

    def get_or_create_dynamic_results_handler(self,
                                              study_type: SimulationTypes,
                                              results: RmsResults | EmtResults) -> DynamicsResultsHandler:
        """
        Get a cached dynamic-results handler for the given study, or create/update it.

        :param study_type: Study simulation type.
        :param results: Dynamic results object associated with the study.
        :return: Cached or newly created dynamics-results handler.

        Handlers are cached per study name so user-defined dynamic plot groups
        survive repeated simulations. Reuse only happens when the previous and
        new results belong to the same dynamics family; otherwise a fresh
        handler is created because RMS and EMT expose different event-group and
        array layouts.
        """
        handler: DynamicsResultsHandler | None = self.dynamic_results_handlers.get(study_type, None)

        if handler is None:
            handler = DynamicsResultsHandler(results=results, circuit=self.circuit)
            handler.dialog_parent = self
            self.dynamic_results_handlers[study_type] = handler
            handler.get_plots_model().rowsInserted.connect(self.expand_dynamic_plots_tree)
            handler.get_plots_model().plotDefinitionsChanged.connect(
                self._notify_current_dynamic_plot_assets_changed
            )
            return handler

        elif type(handler.results) == type(results):
            # Reusing the handler preserves the user's dynamic plot groups across
            # repeated runs of the same study while replacing only the result-backed Vars.
            handler.circuit = self.circuit
            handler.dialog_parent = self
            handler.update_results(results=results)
            return handler

        else:
            # RMS and EMT handlers cannot be mixed because their result containers use
            # different event-group fields and value-array layouts.
            handler = DynamicsResultsHandler(results=results, circuit=self.circuit)
            handler.dialog_parent = self
            self.dynamic_results_handlers[study_type] = handler
            handler.get_plots_model().rowsInserted.connect(self.expand_dynamic_plots_tree)
            handler.get_plots_model().plotDefinitionsChanged.connect(
                self._notify_current_dynamic_plot_assets_changed
            )
            return handler

    def _set_dynamic_results_tab_visible(self, visible: bool) -> None:
        """Show or hide the result-only Dynamics tab.

        :param visible: Whether actual dynamic results are currently available.
        :return: None.
        """
        dynamics_tab_index: int = self.ui.resultsTabWidget.indexOf(self.ui.tab_5)
        if dynamics_tab_index >= 0:
            self.ui.resultsTabWidget.setTabVisible(dynamics_tab_index, visible)
        else:
            pass

    def _notify_current_dynamic_plot_assets_changed(self) -> None:
        """Broadcast plot assets changed from the active Results handler.

        :return: None.
        """
        if self.dynamic_results_handler is not None:
            plot_type: PlotSimulationType = self.dynamic_results_handler.plot_simulation_type
            if plot_type == PlotSimulationType.RMS:
                mode: DynamicSimulationMode = DynamicSimulationMode.RMS
            else:
                mode = DynamicSimulationMode.EMT
            self.dynamic_editor_workspace_session.notify_dynamic_plots_changed(
                mode=mode,
                source=self,
            )
        else:
            pass

    @QtCore.Slot(object, object)
    def _on_external_dynamic_plot_assets_changed(self, mode: object, source: object) -> None:
        """Reload Results plot groups changed in the global Plots Editor.

        :param mode: RMS or EMT family whose persistent assets changed.
        :param source: GUI object that originated the change.
        :return: None.
        """
        handler: DynamicsResultsHandler | None = self.dynamic_results_handler
        if handler is not None and source is not self and isinstance(mode, DynamicSimulationMode):
            handler_is_matching_family: bool = (
                (mode == DynamicSimulationMode.RMS and handler.plot_simulation_type == PlotSimulationType.RMS)
                or (mode == DynamicSimulationMode.EMT and handler.plot_simulation_type == PlotSimulationType.EMT)
            )
            if handler_is_matching_family:
                handler.refresh_plot_definitions()
                self.ui.dynamicsPlotsTreeView.update()
                self.ui.dynamicsTableView.setModel(None)
            else:
                pass
        else:
            pass

    def plot_results(self) -> None:
        """
        Plot the visible results according to the table plot contract.

        Complex-vector tables interpret selected cells as mode-column choices.
        State subsets are selected explicitly through complete rows or through
        the results filter, preventing a single clicked cell from truncating an
        entire right eigenvector accidentally. Complex-point tables use cell
        selection for modes and complete-column selection for coordinate units.

        :return: None.
        """
        mdl: ResultsModel | None = self.ui.resultsTableView.model()

        if mdl is not None:

            # Collect the selected cells once so all plot types use the same
            # visible model after filtering.
            selected_indexes: list[QtCore.QModelIndex] = self.ui.resultsTableView.selectedIndexes()
            selected_columns: np.ndarray | None
            selected_rows: np.ndarray | None
            if len(selected_indexes) > 0:
                selected_columns_array: np.ndarray = np.zeros(len(selected_indexes), dtype=np.int64)
                selected_rows_array: np.ndarray = np.zeros(len(selected_indexes), dtype=np.int64)

                selected_position: int
                selected_index: QtCore.QModelIndex
                for selected_position, selected_index in enumerate(selected_indexes):
                    selected_columns_array[selected_position] = selected_index.column()
                    selected_rows_array[selected_position] = selected_index.row()

                selection_model: QtCore.QItemSelectionModel = self.ui.resultsTableView.selectionModel()
                complete_rows: list[QtCore.QModelIndex] = selection_model.selectedRows()
                complete_columns: list[QtCore.QModelIndex] = selection_model.selectedColumns()

                if mdl.table.plot_type == ResultTablePlotType.COMPLEX_POINTS:
                    # Cell and row selection chooses modal points. Only an
                    # explicit complete-column selection changes the complex
                    # coordinate pair used by the plot.
                    if len(complete_rows) > 0:
                        complete_row_indices: np.ndarray = np.zeros(len(complete_rows), dtype=np.int64)
                        complete_row_position: int
                        complete_row: QtCore.QModelIndex
                        for complete_row_position, complete_row in enumerate(complete_rows):
                            complete_row_indices[complete_row_position] = complete_row.row()
                        selected_rows = np.unique(complete_row_indices)
                    else:
                        selected_rows = np.unique(selected_rows_array)

                    # Selecting every table column normally comes from a row
                    # selection and therefore means "use the default pair".
                    if 0 < len(complete_columns) < mdl.table.c:
                        complete_column_indices: np.ndarray = np.zeros(
                            len(complete_columns),
                            dtype=np.int64,
                        )
                        complete_column_position: int
                        complete_column: QtCore.QModelIndex
                        for complete_column_position, complete_column in enumerate(complete_columns):
                            complete_column_indices[complete_column_position] = complete_column.column()
                        selected_columns = np.unique(complete_column_indices)
                    else:
                        selected_columns = None
                elif mdl.table.plot_type == ResultTablePlotType.COMPLEX_VECTORS:
                    selected_columns = np.unique(selected_columns_array)
                    if len(complete_rows) > 0:
                        complete_row_indices: np.ndarray = np.zeros(len(complete_rows), dtype=np.int64)
                        complete_row_position: int
                        complete_row: QtCore.QModelIndex
                        for complete_row_position, complete_row in enumerate(complete_rows):
                            complete_row_indices[complete_row_position] = complete_row.row()
                        selected_rows = np.unique(complete_row_indices)
                    else:
                        selected_rows = None
                else:
                    selected_columns = np.unique(selected_columns_array)
                    selected_rows = np.unique(selected_rows_array)
            else:
                selected_columns = None
                selected_rows = None

            if mdl.table.plot_type == ResultTablePlotType.COMPLEX_POINTS:
                number_of_plots: int = 1
            elif selected_columns is None:
                number_of_plots: int = mdl.table.c
            else:
                number_of_plots = int(selected_columns.size)

            if number_of_plots > 50:
                ok = yes_no_question(text=self.tr("There are {columns} columns, the plot might take a lot to render.\n"
                                                  "Are you ok with potentially waiting a lot?").format(
                    columns=number_of_plots),
                    title=self.tr("Plot"))
            else:
                ok = True

            if ok:
                self.open_native_results_plot(
                    mdl=mdl,
                    selected_columns=selected_columns,
                    selected_rows=selected_rows,
                    stacked=self.ui.stacked_plot_checkBox.isChecked(),
                )
            else:
                pass
        else:
            warning_msg(
                self.tr("There are no results available to plot."),
                self.tr("Plot results"),
            )

    def open_native_results_plot(self,
                                 mdl: ResultsModel,
                                 selected_columns: np.ndarray | None,
                                 selected_rows: np.ndarray | None,
                                 stacked: bool) -> None:
        """Open the native plot matching the visible results-table contract.

        :param mdl: Filtered table model currently displayed in the results view.
        :param selected_columns: Optional selected visible result columns.
        :param selected_rows: Optional selected visible result rows.
        :param stacked: Whether ordinary series use cumulative areas.
        :return: None.
        """
        plot_type: ResultTablePlotType = mdl.table.plot_type
        if plot_type == ResultTablePlotType.SERIES:
            self.open_native_results_series_plot(
                mdl=mdl,
                selected_columns=selected_columns,
                selected_rows=selected_rows,
                stacked=stacked,
            )
        elif plot_type == ResultTablePlotType.XY:
            self.open_native_xy_results_plot(
                mdl=mdl,
                selected_columns=selected_columns,
                selected_rows=selected_rows,
            )
        elif plot_type == ResultTablePlotType.POLAR:
            self.open_native_polar_results_plot(
                mdl=mdl,
                selected_columns=selected_columns,
                selected_rows=selected_rows,
            )
        elif plot_type == ResultTablePlotType.COMPLEX_POINTS:
            self.open_native_complex_points_plot(
                mdl=mdl,
                selected_columns=selected_columns,
                selected_rows=selected_rows,
            )
        elif plot_type == ResultTablePlotType.COMPLEX_VECTORS:
            self.open_native_complex_vectors_plot(
                mdl=mdl,
                selected_columns=selected_columns,
                selected_rows=selected_rows,
            )
        else:
            error_msg(text=self.tr("This results table has no supported native plot mode."),
                      title=self.tr("Plotting error"))

    def open_native_xy_results_plot(self,
                                    mdl: ResultsModel,
                                    selected_columns: np.ndarray | None,
                                    selected_rows: np.ndarray | None) -> None:
        """Open a generic scatter plot whose first table column is X.

        :param mdl: Filtered table model currently displayed in the results view.
        :param selected_columns: Optional visible columns, with column zero as X.
        :param selected_rows: Optional selected visible rows.
        :return: None.
        """
        plot_data: tuple[np.ndarray, list[str], list[np.ndarray]] | None = get_result_table_xy(
            table=mdl.table,
            selected_rows=selected_rows,
            selected_y_columns=selected_columns,
        )
        if plot_data is not None:
            x_values: np.ndarray
            series_names: list[str]
            series_values: list[np.ndarray]
            x_values, series_names, series_values = plot_data
            plot_dialogue: PlotDialogue = PlotDialogue(title=self.tr("Results plot"), parent=self)
            accepted: bool = plot_dialogue.set_scatter_series(
                x_values=x_values,
                series_names=series_names,
                series_values=series_values,
                title=mdl.table.plot_title or mdl.table.title,
                x_axis_title=mdl.table.x_label,
                y_axis_title=mdl.table.y_label,
            )
            if accepted:
                self.register_open_plot_dialog(plot_dialogue)
                plot_dialogue.show()
            else:
                plot_dialogue.reject()
                error_msg(text=self.tr("The selected values cannot be plotted."), title=self.tr("Plotting error"))
        else:
            error_msg(text=self.tr("Select at least one valid X and Y column."), title=self.tr("Plotting error"))

    def open_native_polar_results_plot(self,
                                       mdl: ResultsModel,
                                       selected_columns: np.ndarray | None,
                                       selected_rows: np.ndarray | None) -> None:
        """Open paired magnitude-angle table columns as native polar samples.

        :param mdl: Filtered table model currently displayed in the results view.
        :param selected_columns: Optional magnitude-angle pair selection.
        :param selected_rows: Optional selected time or device rows.
        :return: None.
        """
        table: ResultsTable = mdl.table
        pair_count: int = table.c // 2
        all_pairs_valid: bool = table.c >= 2 and table.c % 2 == 0
        if selected_rows is None:
            row_indices: np.ndarray = np.arange(table.r, dtype=np.int64)
        else:
            row_indices = np.unique(np.asarray(selected_rows, dtype=np.int64))
        rows_valid: bool = (
            len(row_indices) > 0
            and int(np.min(row_indices)) >= 0
            and int(np.max(row_indices)) < table.r
        )

        pair_indices: np.ndarray = np.arange(pair_count, dtype=np.int64)
        if selected_columns is not None:
            selected_column_indices: np.ndarray = np.unique(np.asarray(selected_columns, dtype=np.int64))
            pair_selected: bool = (
                len(selected_column_indices) == 2
                and int(np.min(selected_column_indices)) >= 0
                and int(np.max(selected_column_indices)) < table.c
            )
            if pair_selected:
                first_column: int = int(selected_column_indices[0])
                second_column: int = int(selected_column_indices[1])
                if first_column < pair_count and second_column == first_column + pair_count:
                    pair_indices = np.array([first_column], dtype=np.int64)
                else:
                    pass
            else:
                pass
        else:
            pass

        if all_pairs_valid and rows_valid:
            series_names: list[str] = list()
            angle_values: list[np.ndarray] = list()
            radius_values: list[np.ndarray] = list()
            pair_position: int
            for pair_position in range(len(pair_indices)):
                magnitude_column: int = int(pair_indices[pair_position])
                angle_column: int = magnitude_column + pair_count
                series_names.append(str(table.cols_c[magnitude_column]))
                angle_values.append(np.asarray(table.data_c[row_indices, angle_column], dtype=float).copy())
                radius_values.append(np.asarray(table.data_c[row_indices, magnitude_column], dtype=float).copy())

            plot_dialogue: PlotDialogue = PlotDialogue(title=self.tr("Results plot"), parent=self)
            accepted: bool = plot_dialogue.set_polar_series(
                series_names=series_names,
                angle_values=angle_values,
                radius_values=radius_values,
                title=table.title,
                radius_title=table.y_label,
                angle_unit=PolarAngleUnit.DEGREES,
                connect_points=False,
            )
            if accepted:
                self.register_open_plot_dialog(plot_dialogue)
                plot_dialogue.show()
            else:
                plot_dialogue.reject()
                error_msg(text=self.tr("The selected polar values cannot be plotted."),
                          title=self.tr("Plotting error"))
        else:
            error_msg(text=self.tr("Select valid rows and a complete magnitude-angle table."),
                      title=self.tr("Plotting error"))

    def open_native_results_series_plot(self,
                                        mdl: ResultsModel,
                                        selected_columns: np.ndarray | None,
                                        selected_rows: np.ndarray | None,
                                        stacked: bool) -> None:
        """Open selected ordinary result columns in one native chart.

        :param mdl: Filtered table model currently displayed in the results view.
        :param selected_columns: Optional selected visible result columns.
        :param selected_rows: Optional selected visible result rows.
        :param stacked: Whether more than one series uses cumulative areas.
        :return: None.
        """
        table: ResultsTable = mdl.table
        hide_zero_values: bool = 'voltage' in table.title.lower()
        plot_data: tuple[np.ndarray, list[str], list[np.ndarray]] | None = get_result_table_series(
            table=table,
            selected_col_idx=selected_columns,
            selected_rows=selected_rows,
            hide_zero_values=hide_zero_values,
        )
        if plot_data is not None:
            x_values: np.ndarray = plot_data[0]
            series_names: list[str] = plot_data[1]
            series_values: list[np.ndarray] = plot_data[2]
            dialog_title: str = self.tr("Results plot")
            plot_dialogue: PlotDialogue = PlotDialogue(
                title=dialog_title,
                parent=self,
            )
            accepted: bool
            if stacked and len(series_names) > 1:
                accepted = plot_dialogue.set_cumulative_area_series(
                    x_values=x_values,
                    series_names=series_names,
                    series_values=series_values,
                    title=table.title,
                    x_axis_title=table.x_label,
                    y_axis_title=table.y_label,
                )
            else:
                accepted = plot_dialogue.set_line_series(
                    x_values=x_values,
                    series_names=series_names,
                    series_values=series_values,
                    title=table.title,
                    x_axis_title=table.x_label,
                    y_axis_title=table.y_label,
                )
            if accepted:
                # Retain the visible table captions before numeric plotting discards them.
                row_indices: np.ndarray = (np.arange(len(table.index_c), dtype=np.int64)
                                           if selected_rows is None else np.unique(selected_rows))
                row_labels: list[str] = [str(table.index_c[int(index)]) for index in row_indices]
                plot_dialogue.get_current_chart().set_row_labels(x_values, row_labels)
                self.register_open_plot_dialog(plot_dialogue)
                plot_dialogue.show()
            else:
                plot_dialogue.reject()
                error_msg(text=self.tr("The selected values cannot be plotted."),
                          title=self.tr("Plotting error"))
        else:
            error_msg(text=self.tr("Select at least one valid result row and column."),
                      title=self.tr("Plotting error"))

    def open_native_complex_points_plot(self,
                                        mdl: ResultsModel,
                                        selected_columns: np.ndarray | None,
                                        selected_rows: np.ndarray | None) -> None:
        """Open labelled circular points for one configured complex plane.

        :param mdl: Filtered table model currently displayed in the results view.
        :param selected_columns: Optional selected real and imaginary columns.
        :param selected_rows: Optional selected visible mode rows.
        :return: None.
        """
        table: ResultsTable = mdl.table
        x_column_name: str | None = table.complex_plot_x_column
        y_column_names: np.ndarray = np.asarray(table.complex_plot_y_columns, dtype=str)
        visible_column_names: np.ndarray = np.asarray(table.cols_c, dtype=str)
        selected_y_name: str | None = None
        if x_column_name is not None and len(y_column_names) > 0:
            if selected_columns is None:
                selected_y_name = str(y_column_names[0])
            else:
                selected_column_indices: np.ndarray = np.unique(np.asarray(selected_columns, dtype=np.int64))
                selected_columns_valid: bool = (
                    len(selected_column_indices) == 2
                    and int(np.min(selected_column_indices)) >= 0
                    and int(np.max(selected_column_indices)) < table.c
                )
                if selected_columns_valid:
                    selected_names: np.ndarray = visible_column_names[selected_column_indices]
                    has_x_coordinate: bool = bool(np.any(selected_names == x_column_name))
                    y_matches: np.ndarray = np.intersect1d(selected_names, y_column_names)
                    if has_x_coordinate and len(y_matches) == 1:
                        selected_y_name = str(y_matches[0])
                    else:
                        pass
                else:
                    pass
        else:
            pass

        if selected_y_name is not None and x_column_name is not None:
            x_matches: np.ndarray = np.where(visible_column_names == x_column_name)[0]
            y_matches = np.where(visible_column_names == selected_y_name)[0]
            if len(x_matches) == 1 and len(y_matches) == 1:
                selected_y_config_matches: np.ndarray = np.where(y_column_names == selected_y_name)[0]
                selected_y_scale: float = float(
                    table.complex_plot_y_scales[int(selected_y_config_matches[0])]
                )
                if selected_rows is None:
                    row_indices: np.ndarray = np.arange(table.r, dtype=np.int64)
                else:
                    row_indices = np.unique(np.asarray(selected_rows, dtype=np.int64))
                row_indices_valid: bool = (
                    len(row_indices) > 0
                    and int(np.min(row_indices)) >= 0
                    and int(np.max(row_indices)) < table.r
                )
                if row_indices_valid:
                    real_values: np.ndarray = np.asarray(table.data_c[row_indices, int(x_matches[0])], dtype=float)
                    imaginary_values: np.ndarray = np.asarray(table.data_c[row_indices, int(y_matches[0])], dtype=float)
                    finite_values: np.ndarray = np.isfinite(real_values) & np.isfinite(imaginary_values)
                    if bool(np.any(finite_values)):
                        finite_real_values: np.ndarray = real_values[finite_values]
                        finite_imaginary_values: np.ndarray = imaginary_values[finite_values]
                        point_labels: np.ndarray = np.asarray(table.index_c, dtype=str)[row_indices][finite_values]
                        tooltip_values: list[str] = list()
                        point_index: int
                        for point_index in range(len(point_labels)):
                            tooltip_values.append(
                                f"{point_labels[point_index]}\n"
                                f"Re={finite_real_values[point_index]:.6g}, "
                                f"Im={finite_imaginary_values[point_index]:.6g}"
                            )
                        dialog_title: str = self.tr("Results plot")
                        plot_dialogue: PlotDialogue = PlotDialogue(title=dialog_title, parent=self)
                        chart: GraphsWidget = plot_dialogue.chart
                        # Derive the viewport from the modes and the origin so
                        # reference geometry cannot pull the useful data away.
                        mode_x_limits: np.ndarray = np.array(
                            [min(float(np.min(finite_real_values)), 0.0),
                             max(float(np.max(finite_real_values)), 0.0)],
                            dtype=float,
                        )
                        mode_y_limits: np.ndarray = np.array(
                            [min(float(np.min(finite_imaginary_values)), 0.0),
                             max(float(np.max(finite_imaginary_values)), 0.0)],
                            dtype=float,
                        )
                        x_span: float = float(mode_x_limits[1] - mode_x_limits[0])
                        y_span: float = float(mode_y_limits[1] - mode_y_limits[0])
                        if x_span > 0.0:
                            x_padding: float = x_span * 0.05
                        else:
                            x_padding = 0.05
                        if y_span > 0.0:
                            y_padding: float = y_span * 0.05
                        else:
                            y_padding = 0.05
                        plot_x_limits: np.ndarray = np.array(
                            [mode_x_limits[0] - x_padding, mode_x_limits[1] + x_padding],
                            dtype=float,
                        )
                        plot_y_limits: np.ndarray = np.array(
                            [mode_y_limits[0] - y_padding, mode_y_limits[1] + y_padding],
                            dtype=float,
                        )

                        # Extend both zero axes to the viewport boundary so no
                        # visual gap remains between an axis and the plot frame.
                        chart.add_line_series(
                            name="",
                            x_values=plot_x_limits,
                            y_values=np.zeros(2, dtype=float),
                            color="#64748b",
                        )
                        chart.add_line_series(
                            name="",
                            x_values=np.zeros(2, dtype=float),
                            y_values=plot_y_limits,
                            color="#64748b",
                        )

                        # A constant damping ratio is a pair of rays in the
                        # stable half-plane. Clip the 5% rays to the mode-based
                        # viewport instead of allowing them to affect its size.
                        configured_damping_ratio: float | None = table.damping_ratio_boundary
                        if (configured_damping_ratio is not None
                                and 0.0 < configured_damping_ratio < 1.0):
                            damping_ratio: float = configured_damping_ratio
                        else:
                            damping_ratio = 0.05
                        damping_slope: float = float(
                            selected_y_scale
                            * np.sqrt(1.0 - damping_ratio * damping_ratio)
                            / damping_ratio
                        )
                        upper_ray_x: float = max(
                            float(plot_x_limits[0]),
                            -float(plot_y_limits[1]) / damping_slope,
                        )
                        lower_ray_x: float = max(
                            float(plot_x_limits[0]),
                            float(plot_y_limits[0]) / damping_slope,
                        )
                        damping_x_values: np.ndarray = np.array(
                            [upper_ray_x, 0.0, lower_ray_x],
                            dtype=float,
                        )
                        damping_y_values: np.ndarray = np.array(
                            [-upper_ray_x * damping_slope, 0.0, lower_ray_x * damping_slope],
                            dtype=float,
                        )
                        chart.add_line_series(
                            name=self.tr("5% damping ratio"),
                            x_values=damping_x_values,
                            y_values=damping_y_values,
                            color="#94a3b8",
                            dashed=True,
                        )

                        # Keep stable modes in the existing colour and make
                        # positive-real modes visually identify instability.
                        unstable_values: np.ndarray = finite_real_values > 0.0001
                        stable_values: np.ndarray = ~unstable_values
                        tooltip_array: np.ndarray = np.asarray(tooltip_values, dtype=str)
                        if bool(np.any(stable_values)):
                            chart.add_scatter_series(
                                name=self.tr("Modes"),
                                x_values=finite_real_values[stable_values],
                                y_values=finite_imaginary_values[stable_values],
                                color="#0f766e",
                                point_tooltips=tooltip_array[stable_values],
                            )
                        else:
                            pass
                        if bool(np.any(unstable_values)):
                            chart.add_scatter_series(
                                name=self.tr("Unstable modes"),
                                x_values=finite_real_values[unstable_values],
                                y_values=finite_imaginary_values[unstable_values],
                                color="#dc2626",
                                point_tooltips=tooltip_array[unstable_values],
                            )
                        else:
                            pass
                        # Adding reference lines updates generic chart bounds;
                        # restore the mode-derived viewport after all series.
                        chart.axis_x.set_range(float(plot_x_limits[0]), float(plot_x_limits[1]))
                        chart.axis_y.set_range(float(plot_y_limits[0]), float(plot_y_limits[1]))
                        chart.axis_x.reset_viewport()
                        chart.axis_y.reset_viewport()
                        chart.redraw()
                        displayed_title: str = table.title if table.plot_title is None else table.plot_title
                        chart.setTitle(displayed_title)
                        chart.set_axis_titles(x_column_name, selected_y_name)
                        self.register_open_plot_dialog(plot_dialogue)
                        plot_dialogue.show()
                    else:
                        error_msg(text=self.tr("The selected modes have no finite complex coordinates."),
                                  title=self.tr("Plotting error"))
                else:
                    error_msg(text=self.tr("Select valid mode rows to plot."), title=self.tr("Plotting error"))
            else:
                error_msg(text=self.tr("The selected results no longer contain a complex coordinate pair."),
                          title=self.tr("Plotting error"))
        else:
            error_msg(text=self.tr("Select the Real column and one configured Imaginary column."),
                      title=self.tr("Plotting error"))

    def open_native_complex_vectors_plot(self,
                                         mdl: ResultsModel,
                                         selected_columns: np.ndarray | None,
                                         selected_rows: np.ndarray | None) -> None:
        """Open one labelled complex-mode vector plot per tab.

        :param mdl: Filtered table model currently displayed in the results view.
        :param selected_columns: Optional selected visible mode columns.
        :param selected_rows: Optional selected visible state rows.
        :return: None.
        """
        table: ResultsTable = mdl.table
        if selected_columns is None:
            mode_indices: np.ndarray = np.arange(table.c, dtype=np.int64)
        else:
            mode_indices = np.unique(np.asarray(selected_columns, dtype=np.int64))
        if selected_rows is None:
            state_indices: np.ndarray = np.arange(table.r, dtype=np.int64)
        else:
            state_indices = np.unique(np.asarray(selected_rows, dtype=np.int64))
        mode_indices_valid: bool = (
            len(mode_indices) > 0
            and int(np.min(mode_indices)) >= 0
            and int(np.max(mode_indices)) < table.c
        )
        state_indices_valid: bool = (
            len(state_indices) > 0
            and int(np.min(state_indices)) >= 0
            and int(np.max(state_indices)) < table.r
        )
        if mode_indices_valid and state_indices_valid:
            dialog_title: str = self.tr("Results plot")
            plot_dialogue: PlotDialogue = PlotDialogue(title=dialog_title, parent=self)
            circle_angles: np.ndarray = np.linspace(0.0, 2.0 * np.pi, 361)
            circle_x: np.ndarray = np.cos(circle_angles)
            circle_y: np.ndarray = np.sin(circle_angles)
            state_names: np.ndarray = np.asarray(table.index_c, dtype=str)
            mode_position: int
            for mode_position in range(len(mode_indices)):
                mode_index: int = int(mode_indices[mode_position])
                # Results tables may use line breaks to make narrow column
                # headers readable, but plot titles and tabs are single-line.
                raw_mode_title: str = str(table.cols_c[mode_index])
                mode_title: str = " ".join(raw_mode_title.split())
                chart: GraphsWidget
                if mode_position == 0:
                    chart = plot_dialogue.chart
                    plot_dialogue.set_current_tab_title(mode_title)
                else:
                    chart = plot_dialogue.add_tab(title=mode_title)
                mode_values: np.ndarray = np.asarray(table.data_c[state_indices, mode_index], dtype=complex)
                finite_values: np.ndarray = np.isfinite(mode_values.real) & np.isfinite(mode_values.imag)
                chart.clear()
                chart.set_equal_axis_scale(enabled=True)
                chart.add_line_series(
                    name=self.tr("Unit circle"),
                    x_values=circle_x,
                    y_values=circle_y,
                    color="#64748b",
                )
                if bool(np.any(finite_values)):
                    visible_values: np.ndarray = mode_values[finite_values]
                    magnitudes: np.ndarray = np.abs(visible_values)
                    maximum_magnitude: float = float(np.max(magnitudes))
                    if maximum_magnitude > 0.0:
                        reference_position: int = int(np.argmax(magnitudes))
                        reference_phase: float = float(np.angle(visible_values[reference_position]))
                        aligned_values: np.ndarray = visible_values * np.exp(-1j * reference_phase) / maximum_magnitude
                    else:
                        aligned_values = np.zeros_like(visible_values)
                    visible_states: np.ndarray = state_names[state_indices][finite_values]
                    state_position: int
                    for state_position in range(len(visible_states)):
                        # Give every state its own colour and legend entry so
                        # the modal component can be identified directly.
                        state_name: str = str(visible_states[state_position])
                        aligned_value: complex = complex(aligned_values[state_position])
                        magnitude: float = float(abs(aligned_value))
                        state_hue: float = (0.60 + float(state_position) / float(len(visible_states))) % 1.0
                        state_color: str = QtGui.QColor.fromHsvF(state_hue, 0.72, 0.90).name()
                        if magnitude > 0.0:
                            # Draw the shaft from the origin and finish it with
                            # a small arrow head expressed in normalized units.
                            unit_real: float = aligned_value.real / magnitude
                            unit_imaginary: float = aligned_value.imag / magnitude
                            arrow_length: float = min(0.04, magnitude * 0.35)
                            arrow_half_width: float = arrow_length * 0.5
                            arrow_left: complex = aligned_value + complex(
                                -arrow_length * unit_real - arrow_half_width * unit_imaginary,
                                -arrow_length * unit_imaginary + arrow_half_width * unit_real,
                            )
                            arrow_right: complex = aligned_value + complex(
                                -arrow_length * unit_real + arrow_half_width * unit_imaginary,
                                -arrow_length * unit_imaginary - arrow_half_width * unit_real,
                            )
                            arrow_points: np.ndarray = np.array(
                                [0.0j, aligned_value, arrow_left, aligned_value, arrow_right],
                                dtype=complex,
                            )
                            chart.add_line_series(
                                name=state_name,
                                x_values=arrow_points.real,
                                y_values=arrow_points.imag,
                                color=state_color,
                            )
                        else:
                            chart.add_scatter_series(
                                name=state_name,
                                x_values=np.zeros(1, dtype=float),
                                y_values=np.zeros(1, dtype=float),
                                color=state_color,
                            )
                else:
                    pass
                # The normalized eigenvector and its unit circle share an
                # identical range on both square axes.
                chart.axis_x.set_range(-1.05, 1.05)
                chart.axis_y.set_range(-1.05, 1.05)
                chart.axis_x.reset_viewport()
                chart.axis_y.reset_viewport()
                chart.setTitle(mode_title)
                chart.set_axis_titles(self.tr("Real"), self.tr("Imaginary"))
            self.register_open_plot_dialog(plot_dialogue)
            plot_dialogue.show()
        else:
            error_msg(text=self.tr("Select at least one valid mode column and state row."),
                      title=self.tr("Plotting error"))

    def save_results_df(self):
        """
        Save the data displayed at the results as excel
        """
        mdl: ResultsModel = self.ui.resultsTableView.model()

        if mdl is not None:
            file, filter_ = QtWidgets.QFileDialog.getSaveFileName(self, self.tr("Export results"), '',
                                                                  filter=self.tr("CSV (*.csv);;Excel files (*.xlsx)"))

            if file != '':
                if 'xlsx' in filter_:
                    f = file
                    if not f.endswith('.xlsx'):
                        f += '.xlsx'
                    mdl.save_to_excel(f)
                    print('Saved!')
                if 'csv' in filter_:
                    f = file
                    if not f.endswith('.csv'):
                        f += '.csv'
                    mdl.save_to_csv(f)
                    print('Saved!')
                else:
                    error_msg(self.tr("{file_name} is not valid :(").format(file_name=file))
        else:
            warning_msg(self.tr("There is no profile displayed, please display one"),
                        self.tr("Copy profile to clipboard"))

    def copy_results_data(self):
        """
        Copy the current displayed profiles to the clipboard
        """
        mdl = self.ui.resultsTableView.model()
        if mdl is not None:
            mdl.copy_to_clipboard()
            self.show_info_toast(self.tr("Copied!"))
        else:
            warning_msg(self.tr("There is no profile displayed, please display one"),
                        self.tr("Copy profile to clipboard"))

    def copy_results_data_as_numpy(self):
        """
        Copy the current displayed profiles to the clipboard
        """
        mdl = self.ui.resultsTableView.model()
        if mdl is not None:
            mdl.copy_numpy_to_clipboard()
            self.show_info_toast(self.tr("Copied!"))
        else:
            warning_msg(self.tr("There is no profile displayed, please display one"),
                        self.tr("Copy profile to clipboard"))

    def search_in_results(self) -> None:
        """
        Search in the results model

        :return: None.
        """

        if self.results_mdl is not None:

            txt: str = self.ui.search_results_lineEdit.text().strip()

            filter_: flt.FilterResultsTable = flt.FilterResultsTable(self.results_mdl.table)

            try:
                filter_.parse(expression=txt)
                filtered_model: ResultsModel = ResultsModel(filter_.apply())
            except ValueError as e:
                error_msg(str(e), self.tr("Filter parse"))
                return
            except Exception as e:
                error_msg(str(e), self.tr("Filter parse"))
                return

            # Keep the unfiltered model as the stable search source. This makes
            # each query independent and lets an empty query restore the table.
            self.ui.resultsTableView.setModel(filtered_model)
        else:
            return

    def delete_results_driver(self):
        """
        Delete the driver
        :return:
        """
        idx = self.ui.results_treeView.selectedIndexes()
        if len(idx) > 0:
            tree_mdl = self.ui.results_treeView.model()
            item = tree_mdl.itemFromIndex(idx[0])
            study_type: SimulationTypes | None = self.get_results_tree_study_type(item=item)

            if study_type is not None:

                quit_msg = self.tr("Do you want to delete the results driver {study_name}?").format(
                    study_name=study_type.value
                )
                reply: bool = yes_no_question(text=quit_msg, title=self.tr("Message"), parent=self)

                if reply:
                    if study_type == SimulationTypes.RmsDynamic_run or study_type == SimulationTypes.EmtDynamic_run:
                        if study_type in self.dynamic_results_handlers:
                            del self.dynamic_results_handlers[study_type]
                        else:
                            pass
                        self.clear_dynamic_results_view()
                    else:
                        pass

                    self.session.delete_driver(study_type)
                    self.update_available_results()
            else:
                pass
        else:
            pass

    def clear_dynamic_results_view(self):
        """
        Clear the dynamic-results UI from the screen.
        """
        self.dynamic_results_handler = None

        # Remove tree models so the views become empty and non-interactive
        self.ui.dynamicsDeviceTreeView.setModel(None)
        self.ui.dynamicsPlotsTreeView.setModel(None)
        self.ui.dynamicsTableView.setModel(None)

        # Clear selections
        self.ui.dynamicsDeviceTreeView.clearSelection()
        self.ui.dynamicsPlotsTreeView.clearSelection()

        # Clear related controls
        self.ui.search_dynamic_objects_lineEdit.clear()

        # Leave the dynamics tab and go back to the normal results table tab
        self.ui.resultsTabWidget.setCurrentIndex(0)
        self._set_dynamic_results_tab_visible(visible=False)

    def copy_opf_to_profiles(self):
        """
        Copy the results from the OPF snapshot and time series to the database
        """

        # copy the snapshot if that exits
        _, results = self.session.optimal_power_flow
        if results is not None:

            ok = yes_no_question(self.tr('Are you sure that you want to overwrite '
                                         'the generation, batteries and load snapshot values '
                                         'with the OPF results?'),
                                 title=self.tr("Overwrite profiles with OPF results"))

            if ok:
                self.circuit.set_opf_snapshot_results(results)
                self.show_info_toast(self.tr("P snapshot set from the OPF results"))

        else:
            self.show_warning_toast(self.tr('The OPF time series has no results :('))

        # copy the time series if that exists --------------------------------------------------------------------------
        _, results = self.session.optimal_power_flow_ts
        if results is not None:

            ok = yes_no_question(self.tr('Are you sure that you want to overwrite '
                                         'the generation, batteries and load profiles '
                                         'with the OPF time series results?'),
                                 title=self.tr("Overwrite profiles with OPF results"))

            if ok:
                self.circuit.set_opf_ts_results(results)
                self.show_info_toast(self.tr("P profiles set from the OPF results"))

        else:
            self.show_warning_toast(self.tr('The OPF time series has no results :('))

    def save_results_logs(self):
        """
        Save the results' logs
        """
        file, filter_ = QtWidgets.QFileDialog.getSaveFileName(self, self.tr("Export logs"), '',
                                                              filter=self.tr("CSV (*.csv);;Excel files (*.xlsx)"), )

        if file != '':
            if 'xlsx' in filter_:
                f = file
                if not f.endswith('.xlsx'):
                    f += '.xlsx'
                self.current_results_logger.to_xlsx(f)

            if 'csv' in filter_:
                f = file
                if not f.endswith('.csv'):
                    f += '.csv'
                self.current_results_logger.to_csv(f)
