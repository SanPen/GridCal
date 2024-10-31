# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import sys
from PySide6 import QtWidgets, QtGui

from GridCal.Gui.CascadingSteps.gui import Ui_Dialog
from GridCalEngine.enumerations import SolverType, SimulationTypes
import GridCalEngine.Simulations as sim
from GridCal.Gui.messages import warning_msg


class CascadingStepsGUI(QtWidgets.QDialog):
    """
    ContingencyPlannerGUI
    """

    def __init__(self, parent=None, gridcal_main=None):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Cascading steps')

        self.gridcal_main = gridcal_main

        self.ui.run_cascade_pushButton.clicked.connect(self.run_cascade)

        self.ui.clear_cascade_pushButton.clicked.connect(self.clear_cascade)

        self.ui.run_cascade_step_pushButton.clicked.connect(self.run_cascade_step)

        # Table clicks
        self.ui.cascade_tableView.clicked.connect(self.cascade_table_click)

    def clear_cascade(self):
        """
        Clear cascade simulation
        """
        # self.cascade = None
        self.ui.cascade_tableView.setModel(None)

    def run_cascade_step(self):
        """
        Run cascade step
        """
        if len(self.gridcal_main.circuit.get_buses()) > 0:

            self.gridcal_main.LOCK()
            if self.gridcal_main.session.exists(SimulationTypes.Cascade_run):
                options = self.gridcal_main.get_selected_power_flow_options()
                options.solver_type = SolverType.LM
                max_isl = self.gridcal_main.ui.cascading_islands_spinBox.value()
                drv = sim.CascadingDriver(self.gridcal_main.circuit.copy(), options, max_additional_islands=max_isl)

                self.gridcal_main.session.run(drv,
                                              post_func=self.gridcal_main.post_cascade,
                                              prog_func=self.gridcal_main.ui.progressBar.setValue,
                                              text_func=self.gridcal_main.ui.progress_label.setText)

            self.gridcal_main.cascade.perform_step_run()

            self.gridcal_main.post_cascade()

            self.gridcal_main.UNLOCK()

    def run_cascade(self):
        """
        Run a cascading to blackout simulation
        """
        if len(self.gridcal_main.circuit.get_buses()) > 0:

            if not self.gridcal_main.session.is_this_running(SimulationTypes.Cascade_run):

                self.gridcal_main.add_simulation(SimulationTypes.Cascade_run)

                self.gridcal_main.LOCK()

                self.gridcal_main.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()

                options = self.gridcal_main.get_selected_power_flow_options()
                options.solver_type = SolverType.LM

                max_isl = self.gridcal_main.ui.cascading_islands_spinBox.value()
                n_lsh_samples = self.gridcal_main.ui.max_iterations_stochastic_spinBox.value()

                drv = sim.CascadingDriver(self.gridcal_main.circuit.copy(), options,
                                          max_additional_islands=max_isl,
                                          n_lhs_samples_=n_lsh_samples)

                self.gridcal_main.session.run(drv,
                                              post_func=self.gridcal_main.post_cascade,
                                              prog_func=self.gridcal_main.ui.progressBar.setValue,
                                              text_func=self.gridcal_main.ui.progress_label.setText)

                # run
                drv.start()

            else:
                warning_msg('Another cascade is running...')
        else:
            pass

    def cascade_table_click(self):
        """
        Display cascade upon cascade scenario click
        Returns:

        """

        idx = self.ui.cascade_tableView.currentIndex()
        if idx.row() > -1:
            self.gridcal_main.post_cascade(idx=idx.row())


# if __name__ == "__main__":
#     app = QtWidgets.QApplication(sys.argv)
#     window = CascadingStepsGUI()
#     window.resize(1.61 * 700, 600)  # golden ratio
#     window.show()
#     sys.exit(app.exec())
