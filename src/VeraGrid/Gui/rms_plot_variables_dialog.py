# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QDialogButtonBox, QMenu
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QCloseEvent

from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely, is_dialog_available
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
import numpy as np


class RmsPlotDialog(QDialog):
    """
    Special plot for dynamic variables
    """

    def __init__(self, results: RmsResults, parent=None):
        super().__init__(parent)

        devices = results.devices

        devices_options = {}
        for device in devices:
            devices_options[device.name] = [
                var.name + device.name
                for var in (
                    results.devices_vars_info[device]
                )
            ]

        self.setWindowTitle(self.tr("Plot Variables"))
        self.uid2idx = results.uid2idx
        self.vars_glob_name2uid = results.vars_glob_name2uid
        self.devices = devices_options

        self.time_values: np.ndarray = np.asarray(results.time_array)
        self.result_values: np.ndarray = np.asarray(results.values, dtype=float)
        self.variable_names: np.ndarray = np.asarray(results.variable_array, dtype=str)

        self.selected_vars = []
        # main layout
        layout = QVBoxLayout(self)

        # device selector
        dev_layout = QHBoxLayout()
        dev_layout.addWidget(QLabel(self.tr("Device:")))
        self.device_combo = QComboBox()
        self.device_combo.addItems(list(devices_options.keys()))
        self.device_combo.currentIndexChanged.connect(self.update_variables)
        dev_layout.addWidget(self.device_combo)
        layout.addLayout(dev_layout)

        # variable selector
        var_layout = QHBoxLayout()
        var_layout.addWidget(QLabel(self.tr("Variable:")))
        self.var_combo = QComboBox()
        var_layout.addWidget(self.var_combo)
        layout.addLayout(var_layout)

        # add variables button
        add_btn = QPushButton(self.tr("Add"))
        add_btn.clicked.connect(self.add_variable)
        layout.addWidget(add_btn)

        # selected vars list
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_variable_context_menu)
        layout.addWidget(self.list_widget)

        self._plot_dialogue: PlotDialogue | None = None

        # accept reject buttons layout
        buttons_layout = QHBoxLayout()

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.plot_selected)
        self.buttons.rejected.connect(self.reject)
        buttons_layout.addWidget(self.buttons)

        # show in separate window button
        show_window_btn = QPushButton(self.tr("Show in new window"))
        show_window_btn.clicked.connect(self.show_external_plot)
        buttons_layout.addWidget(show_window_btn)

        layout.addLayout(buttons_layout)

        # update variables
        self.update_variables(0)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Release the retained native plot dialog before the dialog closes.

        :param event: Qt close event.
        :return: None.
        """
        self.close_plot_dialogue()
        QDialog.closeEvent(self, event)

    def done(self, result: int) -> None:
        """
        Release the retained native plot dialog before accepting or rejecting.

        :param result: Qt dialog result code.
        :return: None.
        """
        self.close_plot_dialogue()
        QDialog.done(self, result)

    def update_variables(self, index):

        device = self.device_combo.currentText()
        self.var_combo.clear()
        self.var_combo.addItems(self.devices[device])

    def add_variable(self):

        var = self.var_combo.currentText()
        if var and var not in [self.list_widget.item(i).text() for i in range(self.list_widget.count())]:
            self.selected_vars.append(self.vars_glob_name2uid[var])
            self.list_widget.addItem(var)
            self.plot_selected()

    def show_variable_context_menu(self, pos: QPoint):

        item = self.list_widget.itemAt(pos)
        if item is not None:
            menu = QMenu(self)
            remove_action = menu.addAction(self.tr("Remove variable"))
            action = menu.exec(self.list_widget.mapToGlobal(pos))
            if action == remove_action:
                self.remove_variable(item)

    def remove_variable(self, item):

        var_name = item.text()
        if var_name in self.vars_glob_name2uid:
            uid_to_remove = self.vars_glob_name2uid[var_name]
            if uid_to_remove in self.selected_vars:
                self.selected_vars.remove(uid_to_remove)

        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
        self.plot_selected()

    def plot_selected(self):
        """Refresh a visible native RMS plot after the variable selection changes.

        :return: None.
        """
        if is_dialog_available(self._plot_dialogue) and len(self.selected_vars) > 0:
            selected_col_idx: list[int] = [self.uid2idx[uid] for uid in self.selected_vars]
            series_names: list[str] = list()
            series_values: list[np.ndarray] = list()
            column_index: int
            for column_index in selected_col_idx:
                series_names.append(str(self.variable_names[column_index]))
                series_values.append(self.result_values[:, column_index])
            self._plot_dialogue.set_time_series(
                time_values=self.time_values,
                series_names=series_names,
                series_values=series_values,
                title=self.tr('RMS variables'),
                y_axis_title='',
            )
        elif is_dialog_available(self._plot_dialogue):
            self.close_plot_dialogue()
        else:
            pass

    def show_external_plot(self):
        """Open the selected RMS variables in one retained native plot dialog.

        :return: None.
        """
        if len(self.selected_vars) > 0:
            self.close_plot_dialogue()
            self._plot_dialogue = PlotDialogue(title=self.tr('RMS variables'), parent=self)
            self.plot_selected()
            self._plot_dialogue.show()
        else:
            pass

    def close_plot_dialogue(self) -> None:
        """Dispose the owned modeless plot before this selector is destroyed.

        :return: None.
        """
        if is_dialog_available(self._plot_dialogue):
            self._plot_dialogue.reject()
            delete_dialog_safely(dialog=self._plot_dialogue)
        else:
            pass
        self._plot_dialogue = None
