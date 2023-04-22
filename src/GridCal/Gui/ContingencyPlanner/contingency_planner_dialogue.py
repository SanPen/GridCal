import os
import string
import sys
from random import randint
from enum import Enum
import numpy as np
from numpy.random import default_rng
import networkx as nx
from PySide2.QtWidgets import *
from typing import List

from GridCal.Gui.ContingencyPlanner.gui import *
from GridCal.Engine.Devices import *
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Gui.GuiFunctions import *
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_plan import generate_automatic_contingency_plan


class ContingencyPlannerGUI(QDialog):

    def __init__(self, parent=None, grid: MultiCircuit = None):
        """

        :param parent:
        """
        QDialog.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Contingency planner')

        self.circuit = grid

        self.contingency_branch_types = [DeviceType.LineDevice,
                                         DeviceType.DCLineDevice,
                                         DeviceType.Transformer2WDevice,
                                         DeviceType.VscDevice,
                                         DeviceType.UpfcDevice]

        self.contingency_injection_types = [DeviceType.GeneratorDevice,
                                            DeviceType.BatteryDevice]

        self.ui.contingencyBranchTypesListView.setModel(get_list_model(self.contingency_branch_types,
                                                                       checks=True, check_value=True))

        self.ui.contingenctyInjectionsListView.setModel(get_list_model(self.contingency_injection_types,
                                                                       checks=True, check_value=True))

        # contingencies
        self.contingencies: List[Contingency] = list()
        self.contingency_groups: List[ContingencyGroup] = list()

        self.ui.autoNminusXButton.clicked.connect(self.auto_generate_contingencies)

        self.generated_results = False

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

    def auto_generate_contingencies(self):
        """
        Automatically generate the contingency plan from the selection
        :return:
        """

        # filters
        branch_indices = get_checked_indices(self.ui.contingencyBranchTypesListView.model())
        injection_indices = get_checked_indices(self.ui.contingenctyInjectionsListView.model())

        branch_types = [self.contingency_branch_types[i] for i in branch_indices]
        injection_types = [self.contingency_injection_types[i] for i in injection_indices]

        # generate the contingency plan
        self.contingencies, self.contingency_groups = generate_automatic_contingency_plan(
            grid=self.circuit,
            k=self.ui.contingencyNspinBox.value(),
            filter_branches_by_voltage=self.ui.filterContingencyBranchesByVoltageCheckBox.isChecked(),
            vmin=self.ui.filterContingencyBranchesByVoltageMinSpinBox.value(),
            vmax=self.ui.filterContingencyBranchesByVoltageMaxSpinBox.value(),
            branch_types=branch_types,
            filter_injections_by_power=self.ui.contingencyFilterInjectionsByPowerCheckBox.isChecked(),
            contingency_perc=self.ui.contingencyInjectionPowerReductionSpinBox.value(),
            pmin=self.ui.contingencyFilterInjectionsByPowerMinSpinBox.value(),
            pmax=self.ui.contingencyFilterInjectionsByPowerMaxSpinBox.value(),
            injection_types=injection_types
        )

        self.generated_results = True
        self.close()


if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = ContingencyPlannerGUI()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec_())

