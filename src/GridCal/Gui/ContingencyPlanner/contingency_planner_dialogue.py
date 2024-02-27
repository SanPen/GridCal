# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from PySide6 import QtWidgets
from typing import List

from GridCal.Gui.ContingencyPlanner.gui import Ui_MainWindow
import GridCalEngine.Devices as dev
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCal.Gui.GuiFunctions as gf
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_plan import generate_automatic_contingency_plan


class ContingencyPlannerGUI(QtWidgets.QDialog):
    """
    ContingencyPlannerGUI
    """

    def __init__(self, parent=None, grid: MultiCircuit = None):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
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

        self.ui.contingencyBranchTypesListView.setModel(gf.get_list_model(self.contingency_branch_types,
                                                                          checks=True, check_value=True))

        self.ui.contingenctyInjectionsListView.setModel(gf.get_list_model(self.contingency_injection_types,
                                                                          checks=True, check_value=True))

        # contingencies
        self.contingencies: List[dev.Contingency] = list()
        self.contingency_groups: List[dev.ContingencyGroup] = list()

        self.ui.autoNminusXButton.clicked.connect(self.auto_generate_contingencies)

        self.generated_results = False

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

    def auto_generate_contingencies(self):
        """
        Automatically generate the contingency plan from the selection
        :return:
        """

        # filters
        branch_indices = gf.get_checked_indices(self.ui.contingencyBranchTypesListView.model())
        injection_indices = gf.get_checked_indices(self.ui.contingenctyInjectionsListView.model())

        branch_types = [self.contingency_branch_types[i] for i in branch_indices]
        injection_types = [self.contingency_injection_types[i] for i in injection_indices]

        # generate the contingency plan
        self.contingencies, self.contingency_groups = generate_automatic_contingency_plan(
            grid=self.circuit,
            k=self.ui.contingencyNspinBox.value(),
            consider_branches=self.ui.addBranchesToContingencyCheckBox.isChecked(),
            filter_branches_by_voltage=self.ui.filterContingencyBranchesByVoltageCheckBox.isChecked(),
            vmin=self.ui.filterContingencyBranchesByVoltageMinSpinBox.value(),
            vmax=self.ui.filterContingencyBranchesByVoltageMaxSpinBox.value(),
            branch_types=branch_types,
            consider_injections=self.ui.addInjectionsToContingencyCheckBox.isChecked(),
            filter_injections_by_power=self.ui.contingencyFilterInjectionsByPowerCheckBox.isChecked(),
            contingency_perc=self.ui.contingencyInjectionPowerReductionSpinBox.value(),
            pmin=self.ui.contingencyFilterInjectionsByPowerMinSpinBox.value(),
            pmax=self.ui.contingencyFilterInjectionsByPowerMaxSpinBox.value(),
            injection_types=injection_types
        )

        self.generated_results = True
        self.close()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = ContingencyPlannerGUI()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
