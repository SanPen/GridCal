# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
from PySide6 import QtWidgets
from GridCal.Gui.Analysis.gui import Ui_MainWindow
from GridCal.Gui.Analysis.object_plot_analysis import grid_analysis, GridErrorLog, FixableErrorOutOfRange
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCal.Gui.general_dialogues import LogsDialogue, Logger


class GridAnalysisGUI(QtWidgets.QMainWindow):
    """
    GridAnalysisGUI
    """
    def __init__(self, circuit: MultiCircuit):
        """

        :param circuit: MultiCircuit
        """
        QtWidgets.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Grid analysis')

        # set the circuit
        self.circuit = circuit

        self.object_types = [dev.device_type.value for dev in circuit.get_template_objects_list()]

        # declare logs
        self.log = GridErrorLog()

        self.fixable_errors: List[FixableErrorOutOfRange] = []

        self.ui.actionSave_diagnostic.triggered.connect(self.save_diagnostic)
        self.ui.actionAnalyze.triggered.connect(self.analyze_all)
        self.ui.actionFix_issues.triggered.connect(self.fix_all)

        self.analyze_all()

    def analyze_all(self):
        """
        Analyze the model data
        :return:
        """
        self.log = GridErrorLog()

        # declare logs
        self.fixable_errors = grid_analysis(
            circuit=self.circuit,
            analyze_ts=self.ui.fixTimeSeriesCheckBox.isChecked(),
            imbalance_threshold=self.ui.activePowerImbalanceSpinBox.value() / 100.0,
            v_low=self.ui.genVsetMinSpinBox.value(),
            v_high=self.ui.genVsetMaxSpinBox.value(),
            tap_min=self.ui.transformerTapModuleMinSpinBox.value(),
            tap_max=self.ui.transformerTapModuleMaxSpinBox.value(),
            transformer_virtual_tap_tolerance=self.ui.virtualTapToleranceSpinBox.value() / 100.0,
            branch_connection_voltage_tolerance=self.ui.lineNominalVoltageToleranceSpinBox.value() / 100.0,
            min_vcc=self.ui.transformerVccMinSpinBox.value(),
            max_vcc=self.ui.transformerVccMaxSpinBox.value(),
            branch_x_threshold=1e-4,
            condition_number_threshold=1e-4,
            logger=self.log
        )

        # set logs
        self.ui.logsTreeView.setModel(self.log.get_model())

    def fix_all(self):
        """
        Fix all detected fixable errors
        :return:
        """
        logger = Logger()
        for fixable_err in self.fixable_errors:
            fixable_err.fix(logger=logger,
                            fix_ts=self.ui.fixTimeSeriesCheckBox.isChecked())

        if len(logger) > 0:
            dlg = LogsDialogue("Fixed issues", logger)
            dlg.setModal(True)
            dlg.exec()

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
