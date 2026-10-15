# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


import sys
from typing import List
import numpy as np
import pandas as pd
from PySide6 import QtWidgets

from VeraGrid.Gui.DeviceEditors.TowerBuilder.tower_builder import Ui_TowerBuilderDialog
from VeraGrid.Gui.dialog_lifecycle import exec_dialog_safely
import VeraGridEngine.Devices as dev
from VeraGrid.Gui.DeviceEditors.TowerBuilder.table_models import TowerModel, WireInTower, WiresTable, Wire
from VeraGrid.Gui.pandas_model import PandasModel
from VeraGrid.Gui.general_dialogues import LogsDialogue
from VeraGridEngine.basic_structures import Logger


class TowerBuilderGUI(QtWidgets.QDialog):

    def __init__(self, tower: dev.OverheadLineType = None, wires_catalogue: List[Wire] = None):
        """
        Constructor
        :param tower:
        :param wires_catalogue:
        """
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_TowerBuilderDialog()
        self.ui.setupUi(self)
        self.setWindowTitle(self.tr('Line builder'))

        # create wire collection from the catalogue
        self.wires_table = WiresTable(self)

        # create the tower driver
        self.tower_driver = TowerModel(edit_callback=self.compute, tower=tower)

        self.ui.name_lineEdit.setText(self.tower_driver.tower.name)
        self.ui.rho_doubleSpinBox.setValue(self.tower_driver.tower.earth_resistivity)
        self.ui.frequency_doubleSpinBox.setValue(self.tower_driver.tower.frequency)
        self.ui.voltage_doubleSpinBox.setValue(self.tower_driver.tower.Vnom)

        if wires_catalogue is not None:
            catalogue_by_id = {wire.idtag: wire for wire in wires_catalogue}
            # Older editor sessions copied catalogue wires with the same idtag.
            # Rebind those references so edited conductor data (including GMR)
            # are used when recomputing the tower.
            for wit in self.tower_driver.tower.wires_in_tower.data:
                wit.wire = catalogue_by_id.get(wit.wire.idtag, wit.wire)
            for wire in wires_catalogue:
                self.wires_table.add(wire)
            self.compute()

        # matrix combo
        self.ui.matrixViewComboBox.addItem("Series impedance [Ω/km]")
        self.ui.matrixViewComboBox.addItem("Series impedance (no neutral) [Ω/km]")
        self.ui.matrixViewComboBox.addItem("Series impedance (sequence) [Ω/km]")
        self.ui.matrixViewComboBox.addItem("Shunt admittance [μS/km]")
        self.ui.matrixViewComboBox.addItem("Shunt admittance (no neutral) [μS/km]")
        self.ui.matrixViewComboBox.addItem("Shunt admittance (sequence) [μS/km]")


        # set models
        self.ui.wires_tableView.setModel(self.wires_table)
        self.ui.tower_tableView.setModel(self.tower_driver)

        # set divider
        self.ui.main_splitter.setStretchFactor(0, 6)
        self.ui.main_splitter.setStretchFactor(1, 2)

        # button clicks
        self.ui.add_to_tower_pushButton.clicked.connect(self.add_wire_to_tower)
        self.ui.delete_from_tower_pushButton.clicked.connect(self.delete_wire_from_tower)
        self.ui.compute_pushButton.clicked.connect(self.compute_btn_click)
        self.ui.acceptButton.clicked.connect(self.accept)
        self.ui.name_lineEdit.textChanged.connect(self.name_changed)

        # combobox update
        self.ui.matrixViewComboBox.currentIndexChanged.connect(self.show_matrix)
        self.ui.frequency_doubleSpinBox.valueChanged.connect(self.compute)
        self.ui.rho_doubleSpinBox.valueChanged.connect(self.compute)
        self.ui.voltage_doubleSpinBox.valueChanged.connect(self.compute)

    def done(self, result: int) -> None:
        """
        Release editor-owned plotting resources before closing the modal dialog.

        :param result: Qt dialog result code.
        :return: None.
        """
        self.ui.plotwidget.dispose()
        QtWidgets.QDialog.done(self, result)

    def msg(self, text, title="Warning"):
        """
        Message box
        :param text: Text to display
        :param title: Name of the window
        """
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        retval = exec_dialog_safely(dialog=msg)

    def name_changed(self):
        """
        Change name
        :return:
        """
        self.tower_driver.tower.name = self.ui.name_lineEdit.text()

    def add_wire_to_collection(self):
        """
        Add new wire to collection
        :return:
        """
        name = 'Wire_' + str(len(self.wires_table.wires) + 1)
        wire = dev.Wire(name=name, r_ext=0.01, r=0.01, x=0)
        self.wires_table.add(wire)

    def delete_wire_from_collection(self):
        """
        Delete wire from the collection
        :return:
        """
        idx = self.ui.wires_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:

            # delete_with_dialogue all the wires from the tower too
            self.tower_driver.delete_by_name(self.wires_table.wires[sel_idx])

            # delete_with_dialogue from the catalogue
            self.wires_table.delete(sel_idx)

            self.compute()
        else:
            self.msg('Select a wire in the wires catalogue')

    def add_wire_to_tower(self):
        """
        Add wire to tower
        :return:
        """
        idx = self.ui.wires_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:
            selected_wire: Wire = self.wires_table.wires[sel_idx]
            self.tower_driver.add(WireInTower(wire=selected_wire))
            self.compute()
        else:
            self.msg('Select a wire in the wires catalogue')

    def delete_wire_from_tower(self):
        """
        Delete wire from the tower
        :return:
        """
        idx = self.ui.tower_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:
            self.tower_driver.delete(sel_idx)
            self.compute()
        else:
            self.msg('Select a wire from the wire composition')

    def show_matrix(self) -> None:
        """
        Display the selected computed matrix in the matrix table view.
        """
        idx: int = self.ui.matrixViewComboBox.currentIndex()

        if idx == 0:
            # Impedances in Ohm/km
            cols: List[str] = ['Phase' + str(i) for i in self.tower_driver.tower.z_phases_nabc]
            z_df: pd.DataFrame = pd.DataFrame(data=self.tower_driver.tower.z_nabc, columns=cols, index=cols)
            self.ui.matrixTableView.setModel(PandasModel(z_df))

        elif idx == 1:
            cols: List[str] = ['Phase' + str(i) for i in self.tower_driver.tower.z_phases_abc]
            z_df: pd.DataFrame = pd.DataFrame(data=self.tower_driver.tower.z_abc, columns=cols, index=cols)
            self.ui.matrixTableView.setModel(PandasModel(z_df))

        elif idx == 2:
            if self.tower_driver.tower.z_seq is not None:
                if self.tower_driver.tower.z_seq.shape[0] % 3 == 0:
                    ncirc: int = self.tower_driver.tower.z_seq.shape[0] // 3
                    circuits: List[int] = self.tower_driver.tower.wires_in_tower.get_circuits()
                    unique_circuits: List[int] = sorted(set(circuits))
                    if len(unique_circuits) == ncirc:
                        cols: List[str] = [f'Seq{i}@circ{c}' for c in unique_circuits for i in range(3)]
                    else:
                        cols: List[str] = [f'Seq{i}@circ{c + 1}' for c in range(ncirc) for i in range(3)]

                    if len(cols) == self.tower_driver.tower.z_seq.shape[0]:
                        z_df: pd.DataFrame = pd.DataFrame(data=self.tower_driver.tower.z_seq, columns=cols, index=cols)
                        self.ui.matrixTableView.setModel(PandasModel(z_df))
                    else:
                        self.ui.matrixTableView.setModel(None)
                else:
                    self.ui.matrixTableView.setModel(None)
            else:
                self.ui.matrixTableView.setModel(None)

        elif idx == 3:
            # Admittances in uS/km
            cols: List[str] = ['Phase' + str(i) for i in self.tower_driver.tower.y_phases_nabc]
            z_df: pd.DataFrame = pd.DataFrame(data=self.tower_driver.tower.y_nabc.imag * 1e6, columns=cols, index=cols)
            self.ui.matrixTableView.setModel(PandasModel(z_df))

        elif idx == 4:
            cols: List[str] = ['Phase' + str(i) for i in self.tower_driver.tower.y_phases_abc]
            z_df: pd.DataFrame = pd.DataFrame(data=self.tower_driver.tower.y_abc.imag * 1e6, columns=cols, index=cols)
            self.ui.matrixTableView.setModel(PandasModel(z_df))

        elif idx == 5:
            if self.tower_driver.tower.y_seq is not None:
                if self.tower_driver.tower.y_seq.shape[0] % 3 == 0:
                    ncirc: int = self.tower_driver.tower.y_seq.shape[0] // 3
                    circuits: List[int] = self.tower_driver.tower.wires_in_tower.get_circuits()
                    unique_circuits: List[int] = sorted(set(circuits))
                    if len(unique_circuits) == ncirc:
                        cols: List[str] = [f'Seq{i}@circ{c}' for c in unique_circuits for i in range(3)]
                    else:
                        cols: List[str] = [f'Seq{i}@circ{c + 1}' for c in range(ncirc) for i in range(3)]

                    if len(cols) == self.tower_driver.tower.y_seq.shape[0]:
                        z_df: pd.DataFrame = pd.DataFrame(
                            data=self.tower_driver.tower.y_seq.imag * 1e6,
                            columns=cols,
                            index=cols
                        )
                        self.ui.matrixTableView.setModel(PandasModel(z_df))
                    else:
                        self.ui.matrixTableView.setModel(None)
                else:
                    self.ui.matrixTableView.setModel(None)
            else:
                self.ui.matrixTableView.setModel(None)
        else:
            pass

        # set auto adjust headers
        self.ui.matrixTableView.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )

    def compute(self):
        """

        :return:
        """

        self.tower_driver.tower.frequency = self.ui.frequency_doubleSpinBox.value()
        self.tower_driver.tower.earth_resistivity = self.ui.rho_doubleSpinBox.value()
        self.tower_driver.tower.Vnom = self.ui.voltage_doubleSpinBox.value()

        # heck the wires configuration
        logs = Logger()
        all_ok = self.tower_driver.tower.check(logs)

        if all_ok:
            # try:
            # compute the matrices
            self.tower_driver.tower.compute()

            self.show_matrix()

            # plot
            self.plot()

            # except Exception as e:
            #     self.msg(str(e), 'Tower calculation')

        return all_ok, logs

    def plot(self):
        """
        Plot the tower wire positions in the Qt Graphs view.
        """
        wires = self.tower_driver.tower.wires_in_tower.data
        x_values: np.ndarray = np.asarray([wire.xpos for wire in wires], dtype=float)
        y_values: np.ndarray = np.asarray([wire.ypos for wire in wires], dtype=float)
        series_data: list[tuple[np.ndarray, np.ndarray, str | None]] = [
            (x_values, y_values, "#2563eb"),
        ]
        updated: bool = self.ui.plotwidget.replace_xy_series_data(series_data=series_data)
        if not updated:
            self.ui.plotwidget.clear()
            self.ui.plotwidget.add_scatter_series(name=self.tr("Wire positions"),
                                                  x_values=x_values,
                                                  y_values=y_values,
                                                  color="#2563eb")
        else:
            pass
        self.ui.plotwidget.setTitle(self.tr("Tower wire position"))
        self.ui.plotwidget.set_axis_titles(self.tr("Horizontal position (m)"),
                                           self.tr("Vertical position (m)"))
        self.ui.plotwidget.redraw()

    def compute_btn_click(self):
        """
        Call compute and display the bugs (if any)
        :return:
        """
        all_ok, logs = self.compute()

        if not all_ok:
            logger_diag = LogsDialogue(name=self.tr('Tower computation'), logger=logs, parent=self)
            exec_dialog_safely(dialog=logger_diag)

    def example_1(self):
        name = '4/0 6/1 ACSR'
        r = 0.367851632  # ohm / km
        x = 0  # ohm / km
        gmr = 0.002481072  # m

        wire = dev.Wire(name=name, r_ext=gmr, r=r, x=x)

        self.tower_driver.add(WireInTower(wire=wire, xpos=0, ypos=8.8392, phase=0))
        self.tower_driver.add(WireInTower(wire=wire, xpos=0.762, ypos=8.8392, phase=1))
        self.tower_driver.add(WireInTower(wire=wire, xpos=2.1336, ypos=8.8392, phase=2))
        self.tower_driver.add(WireInTower(wire=wire, xpos=1.2192, ypos=7.62, phase=3))

        self.wires_table.add(wire)

    def example_2(self):
        name = '4/0 6/1 ACSR'
        r = 0.367851632  # ohm / km
        x = 0  # ohm / km
        gmr = 0.002481072  # m

        incx = 0.1
        incy = 0.1

        wire = dev.Wire(name=name, r_ext=gmr, r=r, x=x)

        self.tower_driver.add(WireInTower(wire, xpos=0, ypos=8.8392, phase=1))
        self.tower_driver.add(WireInTower(wire, xpos=0.762, ypos=8.8392, phase=2))
        self.tower_driver.add(WireInTower(wire, xpos=2.1336, ypos=8.8392, phase=3))
        self.tower_driver.add(WireInTower(wire, xpos=1.2192, ypos=7.62, phase=0))

        self.tower_driver.add(WireInTower(wire, xpos=incx + 0, ypos=8.8392, phase=1))
        self.tower_driver.add(WireInTower(wire, xpos=incx + 0.762, ypos=8.8392, phase=2))
        self.tower_driver.add(WireInTower(wire, xpos=incx + 2.1336, ypos=8.8392, phase=3))
        # self.tower.add(Wire(name, xpos=incx+1.2192, ypos=7.62, gmr=gmr, r=r, x=x, phase=0))

        self.tower_driver.add(WireInTower(wire, xpos=incx / 2 + 0, ypos=incy + 8.8392, phase=1))
        self.tower_driver.add(WireInTower(wire, xpos=incx / 2 + 0.762, ypos=incy + 8.8392, phase=2))
        self.tower_driver.add(WireInTower(wire, xpos=incx / 2 + 2.1336, ypos=incy + 8.8392, phase=3))
        # self.tower.add(Wire(name, xpos=incx/2 + 1.2192, ypos=incy+7.62, gmr=gmr, r=r, x=x, phase=0))

        self.wires_table.add(wire)

    def example_3(self):
        name = '4/0 6/1 ACSR'
        r = 0.367851632  # ohm / km
        x = 0  # ohm / km
        gmr = 0.002481072  # m

        wire = dev.Wire(name=name, diameter=gmr, r=r)

        self.tower_driver.add(WireInTower(wire=wire, xpos=1.5, ypos=10, phase=0))
        self.tower_driver.add(WireInTower(wire=wire, xpos=1, ypos=7, phase=1))
        self.tower_driver.add(WireInTower(wire=wire, xpos=1, ypos=8, phase=2))
        self.tower_driver.add(WireInTower(wire=wire, xpos=1, ypos=9, phase=3))

        self.tower_driver.add(WireInTower(wire=wire, xpos=2, ypos=7, phase=4))
        self.tower_driver.add(WireInTower(wire=wire, xpos=2, ypos=8, phase=5))
        self.tower_driver.add(WireInTower(wire=wire, xpos=2, ypos=9, phase=6))

        self.wires_table.add(wire)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = TowerBuilderGUI()

    window.example_3()
    window.compute()

    window.resize(1.61 * 600.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
