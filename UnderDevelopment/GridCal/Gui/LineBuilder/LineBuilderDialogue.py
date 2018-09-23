# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import os
import string
import sys
from enum import Enum

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import math
from PyQt5.QtWidgets import *

from GridCal.Gui.LineBuilder.gui import *
from GridCal.Engine.DeviceTypes import *
from GridCal.Gui.GuiFunctions import PandasModel
from GridCal.Gui.GeneralDialogues import LogsDialogue


class TowerBuilderGUI(QtWidgets.QDialog):

    def __init__(self, parent=None, tower=None, wires_catalogue=list()):
        """
        Constructor
        Args:
            parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Line builder')

        self.ui.main_splitter.setSizes([10, 1])

        # create wire collection from the catalogue
        self.wire_collection = WiresCollection(self)
        for wire in wires_catalogue:
            self.wire_collection.add(wire)

        # was there a tower passed? else create one
        if tower is None:
            self.tower = Tower(self, edit_callback=self.plot)
        else:
            self.tower = tower

        self.ui.name_lineEdit.setText(self.tower.tower_name)
        self.ui.rho_doubleSpinBox.setValue(self.tower.earth_resistivity)

        # set models
        self.ui.wires_tableView.setModel(self.wire_collection)
        self.ui.tower_tableView.setModel(self.tower)

        # button clicks
        # self.ui.add_wire_pushButton.clicked.connect(self.add_wire_to_collection)
        # self.ui.delete_wire_pushButton.clicked.connect(self.delete_wire_from_collection)
        self.ui.add_to_tower_pushButton.clicked.connect(self.add_wire_to_tower)
        self.ui.delete_from_tower_pushButton.clicked.connect(self.delete_wire_from_tower)
        self.ui.compute_pushButton.clicked.connect(self.compute)

    def msg(self, text, title="Warning"):
        """
        Message box
        :param text: Text to display
        :param title: Name of the window
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()

    def add_wire_to_collection(self):
        """
        Add new wire to collection
        :return:
        """
        name = 'Wire_' + str(len(self.wire_collection.wires) + 1)
        wire = Wire(name, xpos=0, ypos=0, gmr=0.01, r=0.01, x=0, phase=1)
        self.wire_collection.add(wire)

    def delete_wire_from_collection(self):
        """
        Delete wire from the collection
        :return:
        """
        idx = self.ui.wires_tableView.currentIndex()
        sel_idx = idx.row()

        if sel_idx > -1:

            # delete all the wires from the tower too
            self.tower.delete_by_name(self.wire_collection.wires[sel_idx])

            # delete from the catalogue
            self.wire_collection.delete(sel_idx)

            self.plot()
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
            selected_wire = self.wire_collection.wires[sel_idx].copy()
            self.tower.add(selected_wire)
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
            self.tower.delete(sel_idx)

            self.plot()
        else:
            self.msg('Select a wire from the tower')

    def compute(self):
        """

        :return:
        """

        self.tower.frequency = self.ui.frequency_doubleSpinBox.value()
        self.tower.earth_resistivity = self.ui.rho_doubleSpinBox.value()

        # heck the wires configuration
        logs = list()
        all_ok = self.tower.check(logs)

        if not all_ok:
            logger_diag = LogsDialogue(name='Tower computation', logs=logs)
            logger_diag.exec_()
        else:
            # compute the matrices
            self.tower.compute()

            # Impedances in Ohm/km
            cols = ['Phase' + str(i) for i in self.tower.z_phases_abcn]
            z_df = pd.DataFrame(data=self.tower.z_abcn, columns=cols, index=cols)
            self.ui.z_tableView_abcn.setModel(PandasModel(z_df))

            cols = ['Phase' + str(i) for i in self.tower.z_phases_abc]
            z_df = pd.DataFrame(data=self.tower.z_abc, columns=cols, index=cols)
            self.ui.z_tableView_abc.setModel(PandasModel(z_df))

            cols = ['Sequence ' + str(i) for i in range(3)]
            z_df = pd.DataFrame(data=self.tower.z_seq, columns=cols, index=cols)
            self.ui.z_tableView_seq.setModel(PandasModel(z_df))

            # Admittances in uS/km
            cols = ['Phase' + str(i) for i in self.tower.y_phases_abcn]
            z_df = pd.DataFrame(data=self.tower.y_abcn * 1e6, columns=cols, index=cols)
            self.ui.y_tableView_abcn.setModel(PandasModel(z_df))

            cols = ['Phase' + str(i) for i in self.tower.y_phases_abc]
            z_df = pd.DataFrame(data=self.tower.y_abc * 1e6, columns=cols, index=cols)
            self.ui.y_tableView_abc.setModel(PandasModel(z_df))

            cols = ['Sequence ' + str(i) for i in range(3)]
            z_df = pd.DataFrame(data=self.tower.y_seq * 1e6, columns=cols, index=cols)
            self.ui.y_tableView_seq.setModel(PandasModel(z_df))

            # plot
            self.plot()

    def plot(self):

        self.ui.plotwidget.clear()

        fig = self.ui.plotwidget.get_figure()
        fig.set_facecolor('white')
        ax = self.ui.plotwidget.get_axis()

        self.tower.plot(ax=ax)
        self.ui.plotwidget.redraw()

    def example_1(self):
        name = '4/0 6/1 ACSR'
        r = 0.367851632  # ohm / km
        x = 0  # ohm / km
        gmr = 0.002481072  # m

        self.tower.add(Wire(name, xpos=0, ypos=8.8392, gmr=gmr, r=r, x=x, phase=0))
        self.tower.add(Wire(name, xpos=0.762, ypos=8.8392, gmr=gmr, r=r, x=x, phase=1))
        self.tower.add(Wire(name, xpos=2.1336, ypos=8.8392, gmr=gmr, r=r, x=x, phase=2))
        self.tower.add(Wire(name, xpos=1.2192, ypos=7.62, gmr=gmr, r=r, x=x, phase=3))

        self.wire_collection.add(Wire(name, xpos=0, ypos=0, gmr=gmr, r=r, x=x, phase=1))

    def example_2(self):
        name = '4/0 6/1 ACSR'
        r = 0.367851632  # ohm / km
        x = 0  # ohm / km
        gmr = 0.002481072  # m

        incx = 0.1
        incy = 0.1

        self.tower.add(Wire(name, xpos=0,      ypos=8.8392, gmr=gmr, r=r, x=x, phase=1))
        self.tower.add(Wire(name, xpos=0.762,  ypos=8.8392, gmr=gmr, r=r, x=x, phase=2))
        self.tower.add(Wire(name, xpos=2.1336, ypos=8.8392, gmr=gmr, r=r, x=x, phase=3))
        self.tower.add(Wire(name, xpos=1.2192, ypos=7.62,   gmr=gmr, r=r, x=x, phase=0))

        self.tower.add(Wire(name, xpos=incx+0, ypos=8.8392, gmr=gmr, r=r, x=x, phase=1))
        self.tower.add(Wire(name, xpos=incx+0.762, ypos=8.8392, gmr=gmr, r=r, x=x, phase=2))
        self.tower.add(Wire(name, xpos=incx+2.1336, ypos=8.8392, gmr=gmr, r=r, x=x, phase=3))
        # self.tower.add(Wire(name, xpos=incx+1.2192, ypos=7.62, gmr=gmr, r=r, x=x, phase=0))

        self.tower.add(Wire(name, xpos=incx/2 + 0,    ypos=incy+8.8392, gmr=gmr, r=r, x=x, phase=1))
        self.tower.add(Wire(name, xpos=incx/2 + 0.762, ypos=incy+8.8392, gmr=gmr, r=r, x=x, phase=2))
        self.tower.add(Wire(name, xpos=incx/2 + 2.1336, ypos=incy+8.8392, gmr=gmr, r=r, x=x, phase=3))
        # self.tower.add(Wire(name, xpos=incx/2 + 1.2192, ypos=incy+7.62, gmr=gmr, r=r, x=x, phase=0))

        self.wire_collection.add(Wire(name, xpos=0, ypos=0, gmr=gmr, r=r, x=x, phase=1))


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = TowerBuilderGUI()

    window.example_2()
    window.compute()

    window.resize(1.61 * 700.0, 700.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

