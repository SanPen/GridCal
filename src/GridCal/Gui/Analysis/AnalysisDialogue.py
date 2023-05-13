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
from typing import List
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import math

from PySide2.QtWidgets import *
from PySide2 import QtWidgets, QtGui

from GridCal.Gui.Analysis.gui import *
from GridCal.Gui.Analysis.object_plot_analysis import grid_analysis, GridErrorLog, FixableErrorOutOfRange
from GridCal.Gui.GuiFunctions import PandasModel, get_list_model
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices import *
from GridCal.Gui.GeneralDialogues import LogsDialogue


class GridAnalysisGUI(QtWidgets.QMainWindow):

    def __init__(self, parent=None, object_types=list(), circuit: MultiCircuit = None, use_native_dialogues=False):
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

        self.fixable_errors: List[FixableErrorOutOfRange] = list()

        self.object_types = object_types

        self.ui.actionSave_diagnostic.triggered.connect(self.save_diagnostic)
        self.ui.actionAnalyze.triggered.connect(self.analyze_all)
        self.ui.actionFix_issues.triggered.connect(self.fix_all)

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

    def analyze_all(self):
        """
        Analyze the model data
        :return:
        """
        self.log = GridErrorLog()

        print('Analyzing...')
        # declare logs
        self.fixable_errors = grid_analysis(circuit=self.circuit,
                                            imbalance_threshold=self.ui.activePowerImbalanceSpinBox.value() / 100.0,
                                            v_low=self.ui.genVsetMinSpinBox.value(),
                                            v_high=self.ui.genVsetMaxSpinBox.value(),
                                            tap_min=self.ui.transformerTapModuleMinSpinBox.value(),
                                            tap_max=self.ui.transformerTapModuleMaxSpinBox.value(),
                                            transformer_virtual_tap_tolerance=self.ui.virtualTapToleranceSpinBox.value() / 100.0,
                                            branch_connection_voltage_tolerance=self.ui.lineNominalVoltageToleranceSpinBox.value() / 100.0,
                                            logger=self.log)

        # set logs
        self.ui.logsTreeView.setModel(self.log.get_model())

    def fix_all(self):
        """
        Fix all detected fixable errors
        :return:
        """
        print('Fixing issues...')
        logger = Logger()
        for fixable_err in self.fixable_errors:
            fixable_err.fix(logger=logger,
                            fix_ts=self.ui.fixTimeSeriesCheckBox.isChecked())

        if len(logger) > 0:
            dlg = LogsDialogue("Fixed issues", logger)
            dlg.setModal(True)
            dlg.exec_()

        # re-analyze
        self.analyze_all()

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
