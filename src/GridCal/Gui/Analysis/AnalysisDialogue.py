# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

import sys
from typing import List

from PySide6 import QtWidgets
from GridCal.Gui.Analysis.gui import Ui_MainWindow
from GridCal.Gui.Analysis.object_plot_analysis import grid_analysis, GridErrorLog, FixableErrorOutOfRange
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCal.Gui.GeneralDialogues import LogsDialogue, Logger


class GridAnalysisGUI(QtWidgets.QMainWindow):
    """

    """
    def __init__(self, circuit: MultiCircuit = None):
        """

        :param circuit: MultiCircuit
        """
        QtWidgets.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Grid analysis')

        # set the circuit
        self.circuit = circuit

        self.object_types = [dev.device_type.value for dev in circuit.get_objects_with_profiles_list()]

        # declare logs
        self.log = GridErrorLog()

        self.fixable_errors: List[FixableErrorOutOfRange] = []

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
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.setText(text)
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle(title)
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        retval = msg.exec_()

    def analyze_all(self):
        """
        Analyze the model data
        :return:
        """
        self.log = GridErrorLog()

        # declare logs
        self.fixable_errors = grid_analysis(
            circuit=self.circuit,
            imbalance_threshold=self.ui.activePowerImbalanceSpinBox.value() / 100.0,
            v_low=self.ui.genVsetMinSpinBox.value(),
            v_high=self.ui.genVsetMaxSpinBox.value(),
            tap_min=self.ui.transformerTapModuleMinSpinBox.value(),
            tap_max=self.ui.transformerTapModuleMaxSpinBox.value(),
            transformer_virtual_tap_tolerance=self.ui.virtualTapToleranceSpinBox.value() / 100.0,
            branch_connection_voltage_tolerance=self.ui.lineNominalVoltageToleranceSpinBox.value() / 100.0,
            min_vcc=self.ui.transformerVccMinSpinBox.value(),
            max_vcc=self.ui.transformerVccMaxSpinBox.value(),
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
        """
        save_diagnostic
        :return:
        """
        files_types = "Excel (*.xlsx)"

        fname = 'Grid error analysis.xlsx'

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save file', fname, files_types)

        if filename != '':
            self.log.save(filename)


if __name__ == "__main__":
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication(sys.argv)
    window = GridAnalysisGUI(circuit=None)
    window.resize(1.61 * 700.0, 700.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())
