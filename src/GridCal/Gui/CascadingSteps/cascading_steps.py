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
from PySide6 import QtWidgets, QtGui

from GridCal.Gui.CascadingSteps.gui import Ui_Dialog
import GridCalEngine.basic_structures as bs
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
        if len(self.gridcal_main.circuit.buses) > 0:

            self.gridcal_main.LOCK()
            if self.gridcal_main.session.exists(sim.SimulationTypes.Cascade_run):
                options = self.gridcal_main.get_selected_power_flow_options()
                options.solver_type = bs.SolverType.LM
                max_isl = self.gridcal_main.ui.cascading_islands_spinBox.value()
                drv = sim.Cascading(self.gridcal_main.circuit.copy(), options, max_additional_islands=max_isl)

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
        if len(self.gridcal_main.circuit.buses) > 0:

            if not self.gridcal_main.session.is_this_running(sim.SimulationTypes.Cascade_run):

                self.gridcal_main.add_simulation(sim.SimulationTypes.Cascade_run)

                self.gridcal_main.LOCK()

                self.gridcal_main.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()

                options = self.gridcal_main.get_selected_power_flow_options()
                options.solver_type = bs.SolverType.LM

                max_isl = self.gridcal_main.ui.cascading_islands_spinBox.value()
                n_lsh_samples = self.gridcal_main.ui.max_iterations_stochastic_spinBox.value()

                drv = sim.Cascading(self.gridcal_main.circuit.copy(), options,
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


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = CascadingStepsGUI()
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
