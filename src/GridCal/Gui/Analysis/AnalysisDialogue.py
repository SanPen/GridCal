# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import string
import sys
from enum import Enum
import PySide2

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import math

from PySide2.QtWidgets import *
from PySide2 import QtWidgets, QtGui

from GridCal.Gui.Analysis.gui import *
from GridCal.Gui.Analysis.object_plot_analysis import grid_analysis, GridErrorLog
from GridCal.Gui.GuiFunctions import PandasModel, get_list_model
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices import *


class GridAnalysisGUI(QtWidgets.QMainWindow):

    def __init__(self, parent=None, object_types=list(), circuit: MultiCircuit=None, use_native_dialogues=False):
        """
        Constructor
        Args:
            parent:
            object_types:
            circuit:
        """
        QtWidgets.QMainWindow.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Grid analysis')

        # set the circuit
        self.circuit = circuit

        self.use_native_dialogues = use_native_dialogues

        # declare logs
        self.log = GridErrorLog()

        self.object_types = object_types

        self.ui.actionSave_diagnostic.triggered.connect(self.save_diagnostic)

        self.analyze_all()

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

    def analyze_all(self, imbalance_threshold=0.02, v_low=0.95, v_high=1.05):
        """
        Analyze the model data
        :param imbalance_threshold: Allowed percentage of imbalance
        :param v_low: lower voltage setting
        :param v_high: higher voltage setting
        :return:
        """

        print('Analyzing...')
        # declare logs
        self.log = grid_analysis(circuit=self.circuit, imbalance_threshold=imbalance_threshold,
                                 v_low=v_low, v_high=v_high)

        # set logs
        self.ui.logsTreeView.setModel(self.log.get_model())

    def save_diagnostic(self):

        files_types = "Excel (*.xlsx)"

        options = QFileDialog.Options()
        if self.use_native_dialogues:
            options |= QFileDialog.DontUseNativeDialog

        fname = 'Grid error analysis.xlsx'

        filename, type_selected = QFileDialog.getSaveFileName(self, 'Save file', fname, files_types, options=options)

        if filename != '':
            self.log.save(filename)


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = GridAnalysisGUI()
    window.resize(1.61 * 700.0, 700.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

