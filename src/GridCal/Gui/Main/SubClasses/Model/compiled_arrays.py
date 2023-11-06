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
import numpy as np
from PySide6 import QtCore
from matplotlib import pyplot as plt

import GridCalEngine.basic_structures as bs
import GridCal.Gui.GuiFunctions as gf
from GridCal.Gui.Main.SubClasses.base_gui import BaseMainGui
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at


class CompiledArraysMain(BaseMainGui):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        BaseMainGui.__init__(self, parent)

        # array modes
        self.ui.arrayModeComboBox.addItem('real')
        self.ui.arrayModeComboBox.addItem('imag')
        self.ui.arrayModeComboBox.addItem('abs')
        self.ui.arrayModeComboBox.addItem('complex')

        # Buttons
        self.ui.compute_simulation_data_pushButton.clicked.connect(self.update_islands_to_display)
        self.ui.plotArraysButton.clicked.connect(self.plot_simulation_objects_data)
        self.ui.copyArraysButton.clicked.connect(self.copy_simulation_objects_data)
        self.ui.copyArraysToNumpyButton.clicked.connect(self.copy_simulation_objects_data_to_numpy)

        # list clicks
        self.ui.simulationDataStructuresListView.clicked.connect(self.view_simulation_objects_data)

    def view_simulation_objects_data(self):
        """
        Simulation data structure clicked
        """

        i = self.ui.simulation_data_island_comboBox.currentIndex()

        if i > -1 and len(self.circuit.buses) > 0:
            elm_type = self.ui.simulationDataStructuresListView.selectedIndexes()[0].data(role=QtCore.Qt.ItemDataRole.DisplayRole)

            df = self.calculation_inputs_to_display[i].get_structure(elm_type)

            mdl = gf.PandasModel(df)

            self.ui.simulationDataStructureTableView.setModel(mdl)

    def copy_simulation_objects_data(self):
        """
        Copy the arrays of the compiled arrays view to the clipboard
        """
        mdl = self.ui.simulationDataStructureTableView.model()
        mode = self.ui.arrayModeComboBox.currentText()
        mdl.copy_to_clipboard(mode=mode)

    def copy_simulation_objects_data_to_numpy(self):
        """
        Copy the arrays of the compiled arrays view to the clipboard
        """
        mdl = self.ui.simulationDataStructureTableView.model()
        mode = 'numpy'
        mdl.copy_to_clipboard(mode=mode)

    def plot_simulation_objects_data(self):
        """
        Plot the arrays of the compiled arrays view
        """
        mdl = self.ui.simulationDataStructureTableView.model()
        data = mdl.data_c

        # declare figure
        fig = plt.figure()
        ax1 = fig.add_subplot(111)

        if mdl.is_2d():
            ax1.spy(data)

        else:
            if mdl.is_complex():
                ax1.scatter(data.real, data.imag)
                ax1.set_xlabel('Real')
                ax1.set_ylabel('Imag')
            else:
                arr = np.arange(data.shape[0])
                ax1.scatter(arr, data)
                ax1.set_xlabel('Position')
                ax1.set_ylabel('Value')

        fig.tight_layout()
        plt.show()

    def recompile_circuits_for_display(self):
        """
        Recompile the circuits available to display
        :return:
        """
        if self.circuit is not None:

            engine = self.get_preferred_engine()

            if engine == bs.EngineType.GridCal:
                numerical_circuit = compile_numerical_circuit_at(circuit=self.circuit, t_idx=None)
                calculation_inputs = numerical_circuit.split_into_islands()
                self.calculation_inputs_to_display = calculation_inputs

            elif engine == bs.EngineType.Bentayga:
                import GridCalEngine.Core.Compilers.circuit_to_bentayga as ben
                self.calculation_inputs_to_display = ben.get_snapshots_from_bentayga(self.circuit)

            elif engine == bs.EngineType.NewtonPA:
                import GridCalEngine.Core.Compilers.circuit_to_newton_pa as ne
                self.calculation_inputs_to_display = ne.get_snapshots_from_newtonpa(self.circuit)

            else:
                # fallback to gridcal
                numerical_circuit = compile_numerical_circuit_at(circuit=self.circuit, t_idx=None)
                calculation_inputs = numerical_circuit.split_into_islands()
                self.calculation_inputs_to_display = calculation_inputs

            return True
        else:
            self.calculation_inputs_to_display = None
            return False

    def update_islands_to_display(self):
        """
        Compile the circuit and allow the display of the calculation objects
        :return:
        """
        self.recompile_circuits_for_display()
        self.ui.simulation_data_island_comboBox.clear()
        lst = ['Island ' + str(i) for i, circuit in enumerate(self.calculation_inputs_to_display)]
        self.ui.simulation_data_island_comboBox.addItems(lst)
        if len(self.calculation_inputs_to_display) > 0:
            self.ui.simulation_data_island_comboBox.setCurrentIndex(0)
