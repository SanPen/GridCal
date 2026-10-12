# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from PySide6 import QtWidgets

from VeraGrid.Gui.DeviceEditors.UndergroundCableBuilder.table_models import (
    UndergroundCableCatalogueModel,
    UndergroundCableSystemModel,
)
from VeraGrid.Gui.DeviceEditors.UndergroundCableBuilder.underground_cable_builder_ui import (
    Ui_UndergroundCableBuilderDialog,
)
from VeraGrid.Gui.dialog_lifecycle import exec_dialog_safely
from VeraGrid.Gui.general_dialogues import LogsDialogue
from VeraGrid.Gui.gui_functions import ComboDelegate
from VeraGrid.Gui.pandas_model import PandasModel
from VeraGridEngine.basic_structures import CxMat, Logger
from VeraGridEngine.Devices.Branches.underground_cable_type import UndergroundCableType
from VeraGridEngine.Devices.Branches.underground_line_type import CableInSystem, UndergroundLineType
from VeraGridEngine.enumerations import CableResistanceInput


class UndergroundCableBuilderGUI(QtWidgets.QDialog):
    """Edit and calculate a PowerFactory-style underground cable system."""

    __slots__ = ('ui', 'system', 'catalogue_model', 'composition_model')

    def __init__(self,
                 system: UndergroundLineType | None = None,
                 cables_catalogue: List[UndergroundCableType] | None = None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """Create the cable-system builder.

        :param system: Existing underground-line template, or ``None`` for a new one.
        :param cables_catalogue: Physical cable constructions available to the system.
        :param parent: Optional Qt parent widget.
        :return: None.
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui: Ui_UndergroundCableBuilderDialog = Ui_UndergroundCableBuilderDialog()
        self.ui.setupUi(self)
        self.system: UndergroundLineType = UndergroundLineType() if system is None else system
        catalogue: List[UndergroundCableType] = list() if cables_catalogue is None else cables_catalogue

        self.ui.name_lineEdit.setText(self.system.name)
        self.ui.rho_doubleSpinBox.setValue(self.system.earth_resistivity)
        self.ui.frequency_doubleSpinBox.setValue(self.system.freq)
        self.ui.voltage_doubleSpinBox.setValue(self.system.Vnom)
        self.ui.rated_current_doubleSpinBox.setValue(self.system.Imax)

        self.catalogue_model: UndergroundCableCatalogueModel = UndergroundCableCatalogueModel(
            cables=catalogue,
            edit_callback=self.compute,
        )
        self.composition_model: UndergroundCableSystemModel = UndergroundCableSystemModel(
            system=self.system,
            edit_callback=self.compute,
        )
        self.ui.wires_tableView.setModel(self.catalogue_model)
        mode_column = next(i for i, prop in enumerate(self.catalogue_model.properties)
                           if prop.name == 'resistance_input')
        modes = list(CableResistanceInput)
        self.ui.wires_tableView.setItemDelegateForColumn(
            mode_column, ComboDelegate(self.ui.wires_tableView, modes, [mode.value for mode in modes])
        )
        self.ui.tower_tableView.setModel(self.composition_model)
        self.ui.wires_tableView.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.ui.tower_tableView.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )

        self.ui.matrixViewComboBox.addItems((
            self.tr('Primitive series impedance [Ω/km]'),
            self.tr('Reduced series impedance [Ω/km]'),
            self.tr('Sequence series impedance [Ω/km]'),
            self.tr('Primitive shunt admittance [μS/km]'),
            self.tr('Reduced shunt admittance [μS/km]'),
            self.tr('Sequence shunt admittance [μS/km]'),
        ))
        self.ui.main_splitter.setStretchFactor(0, 6)
        self.ui.main_splitter.setStretchFactor(1, 2)

        self.ui.add_to_tower_pushButton.clicked.connect(self.add_cable_to_system)
        self.ui.delete_from_tower_pushButton.clicked.connect(self.delete_cable_from_system)
        self.ui.compute_pushButton.clicked.connect(self.compute_button_clicked)
        self.ui.acceptButton.clicked.connect(self.accept)
        self.ui.name_lineEdit.textChanged.connect(self.name_changed)
        self.ui.matrixViewComboBox.currentIndexChanged.connect(self.show_matrix)
        self.ui.frequency_doubleSpinBox.valueChanged.connect(self.compute)
        self.ui.rho_doubleSpinBox.valueChanged.connect(self.compute)
        self.ui.voltage_doubleSpinBox.valueChanged.connect(self.compute)
        self.ui.rated_current_doubleSpinBox.valueChanged.connect(self.compute)

        if self.system.has_physical_data():
            self.compute()
        else:
            self.plot()

    def done(self, result: int) -> None:
        """Dispose plotting resources before closing the dialog.

        :param result: Qt dialog result code.
        :return: None.
        """
        self.ui.plotwidget.dispose()
        QtWidgets.QDialog.done(self, result)

    def show_message(self, text: str, title: str = 'Warning') -> None:
        """Display one informational message.

        :param text: Message text.
        :param title: Message-box title.
        :return: None.
        """
        message: QtWidgets.QMessageBox = QtWidgets.QMessageBox(self)
        message.setIcon(QtWidgets.QMessageBox.Icon.Information)
        message.setText(text)
        message.setWindowTitle(title)
        message.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        exec_dialog_safely(dialog=message)

    def name_changed(self, text: str) -> None:
        """Apply the edited system name.

        :param text: New name.
        :return: None.
        """
        self.system.name = text

    def add_cable_to_system(self) -> None:
        """Add the selected physical construction to the composition.

        :return: None.
        """
        selected_row: int = self.ui.wires_tableView.currentIndex().row()
        if 0 <= selected_row < len(self.catalogue_model.cables):
            cable: UndergroundCableType = self.catalogue_model.cables[selected_row]
            next_phase: int = self.composition_model.rowCount() + 1
            relation: CableInSystem = CableInSystem(
                cable=cable,
                xpos=0.1 * float(next_phase - 1),
                ypos=1.0,
                phase=next_phase,
            )
            self.composition_model.add(relation=relation)
            self.compute()
        else:
            self.show_message(self.tr('Select a cable construction from the catalogue.'))

    def delete_cable_from_system(self) -> None:
        """Delete the selected cable from the composition.

        :return: None.
        """
        selected_row: int = self.ui.tower_tableView.currentIndex().row()
        if 0 <= selected_row < self.composition_model.rowCount():
            self.composition_model.delete(row=selected_row)
            self.compute()
        else:
            self.show_message(self.tr('Select a cable from the system composition.'))

    def compute(self, unused_value: object | None = None) -> tuple[bool, Logger]:
        """Calculate all cable matrices from the current visible inputs.

        :param unused_value: Optional Qt signal value.
        :return: Calculation state and validation log.
        """
        self.system.freq = self.ui.frequency_doubleSpinBox.value()
        self.system.earth_resistivity = self.ui.rho_doubleSpinBox.value()
        self.system.Vnom = self.ui.voltage_doubleSpinBox.value()
        self.system.Imax = self.ui.rated_current_doubleSpinBox.value()
        relation: CableInSystem
        for relation in self.system.cables_in_system.data:
            if relation.cable is not None:
                relation.name = relation.cable.name
            else:
                pass
        self.composition_model.layoutChanged.emit()
        logger: Logger = Logger()
        valid: bool = self.system.check(logger=logger)
        if valid:
            calculated: bool = self.system.compute(logger=logger)
            if calculated:
                self.show_matrix()
            else:
                pass
        else:
            calculated = False
        self.plot()
        return calculated, logger

    def compute_button_clicked(self) -> None:
        """Calculate and show validation messages when inputs are incomplete.

        :return: None.
        """
        calculated: bool
        logger: Logger
        calculated, logger = self.compute()
        if calculated:
            pass
        else:
            log_dialog: LogsDialogue = LogsDialogue(name=self.tr('Cable calculation'), logger=logger, parent=self)
            exec_dialog_safely(dialog=log_dialog)

    def _matrix_labels(self, primitive: bool) -> List[str]:
        """Build labels for primitive or reduced phase matrices.

        :param primitive: Include one metallic-sheath label per cable.
        :return: Matrix row and column labels.
        """
        phase_labels: List[str] = list()
        phase: int
        for phase in self.system.z_phases_nabc:
            phase_labels.append(f'Phase {int(phase)}')
        if primitive:
            sheath_labels: List[str] = list()
            for phase in self.system.z_phases_nabc:
                sheath_labels.append(f'Sheath {int(phase)}')
            labels: List[str] = phase_labels + sheath_labels
        else:
            labels = phase_labels
        return labels

    def _sequence_labels(self, matrix: CxMat) -> List[str]:
        """Build sequence labels using the matrix's circuit-block order.

        :param matrix: Complete sequence matrix.
        :return: Sequence labels.
        """
        circuit_count: int = matrix.shape[0] // 3
        labels: List[str] = list()
        circuit_index: int
        sequence_index: int
        for circuit_index in range(circuit_count):
            for sequence_index in range(3):
                labels.append(f'Seq {sequence_index} @ circuit {circuit_index + 1}')
        return labels

    def _set_matrix(self, matrix: CxMat | None, labels: List[str], scale: float = 1.0) -> None:
        """Display one calculated matrix.

        :param matrix: Matrix to display, or ``None`` when unavailable.
        :param labels: Row and column labels.
        :param scale: Unit conversion applied for display.
        :return: None.
        """
        if matrix is not None:
            data_frame: pd.DataFrame = pd.DataFrame(
                data=np.asarray(matrix) * scale,
                columns=labels,
                index=labels,
            )
            self.ui.matrixTableView.setModel(PandasModel(data_frame))
            self.ui.matrixTableView.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        else:
            self.ui.matrixTableView.setModel(None)

    def show_matrix(self, unused_index: int | None = None) -> None:
        """Display the selected primitive, reduced or sequence matrix.

        :param unused_index: Optional Qt signal index.
        :return: None.
        """
        matrix_index: int = self.ui.matrixViewComboBox.currentIndex()
        if matrix_index == 0:
            self._set_matrix(
                matrix=self.system.z_primitive,
                labels=self._matrix_labels(primitive=True),
            )
        elif matrix_index == 1:
            self._set_matrix(
                matrix=self.system.z_nabc,
                labels=self._matrix_labels(primitive=False),
            )
        elif matrix_index == 2:
            sequence_impedance: CxMat | None = self.system.z_seq
            labels: List[str] = (
                self._sequence_labels(matrix=sequence_impedance)
                if sequence_impedance is not None
                else list()
            )
            self._set_matrix(matrix=sequence_impedance, labels=labels)
        elif matrix_index == 3:
            self._set_matrix(
                matrix=self.system.y_primitive,
                labels=self._matrix_labels(primitive=True),
                scale=1.0e6,
            )
        elif matrix_index == 4:
            self._set_matrix(
                matrix=self.system.y_nabc,
                labels=self._matrix_labels(primitive=False),
                scale=1.0e6,
            )
        else:
            sequence_admittance: CxMat | None = self.system.y_seq
            labels = (
                self._sequence_labels(matrix=sequence_admittance)
                if sequence_admittance is not None
                else list()
            )
            self._set_matrix(matrix=sequence_admittance, labels=labels, scale=1.0e6)

    def plot(self) -> None:
        """Redraw the cable positions with the QWidget chart renderer.

        :return: None.
        """
        cables: List[CableInSystem] = self.system.cables_in_system.data
        cable_count: int = len(cables)
        x_values: np.ndarray = np.empty(cable_count, dtype=float)
        depth_values: np.ndarray = np.empty(cable_count, dtype=float)
        point_tooltips: List[str] = list()
        cable_index: int

        # Copy every plotted value into chart-owned buffers so deleting a table
        # row never leaves the widget holding an engine object or stale pointer.
        for cable_index in range(cable_count):
            relation: CableInSystem = cables[cable_index]
            x_values[cable_index] = relation.xpos
            depth_values[cable_index] = relation.ypos
            point_tooltips.append(relation.name)

        series_data: List[tuple[np.ndarray, np.ndarray, str | None]] = list(
            [(x_values, depth_values, '#2563eb')]
        )
        updated: bool = self.ui.plotwidget.replace_xy_series_data(series_data=series_data)
        if updated:
            self.ui.plotwidget.set_series_point_tooltips(
                series_index=0,
                point_tooltips=point_tooltips,
            )
        else:
            self.ui.plotwidget.clear()
            self.ui.plotwidget.add_scatter_series(
                name=self.tr('Cable positions'),
                x_values=x_values,
                y_values=depth_values,
                color='#2563eb',
                point_tooltips=point_tooltips,
            )
        self.ui.plotwidget.setTitle(self.tr('Underground cable position'))
        self.ui.plotwidget.set_axis_titles(
            self.tr('Horizontal position (m)'),
            self.tr('Depth (m)'),
        )
        self.ui.plotwidget.redraw()
