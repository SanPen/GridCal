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

import time
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from GridCal.Engine.Simulations.PTDF.ptdf_analysis import ptdf, ptdf_multi_treading

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class PTDFOptions:

    def __init__(self, group_by_technology=True, power_increment=100.0, use_multi_threading=False):
        """
        Power Transfer Distribution Factors's options
        :param group_by_technology: If true, the increment is divided by the generators per technology,
                                    otherwise it is done by generator
        :param power_increment: Amount of power to change in MVA
        :param use_multi_threading: use multi-threading?
        """
        self.group_by_technology = group_by_technology

        self.power_increment = power_increment

        self.use_multi_threading = use_multi_threading


class PTDF(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, grid: MultiCircuit, options: PTDFOptions, pf_options: PowerFlowOptions):
        """
        Power Transfer Distribution Factors class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        QThread.__init__(self)

        # Grid to run
        self.grid = grid

        # Options to use
        self.options = options

        # power flow options
        self.pf_options = pf_options

        # OPF results
        self.results = None

        # set cancel state
        self.__cancel__ = False

        self.all_solved = True

        self.elapsed = 0.0

    def ptdf(self):
        """
        Run PTDF with the selected options
        :return: None
        """

        if self.options.use_multi_threading:

            self.results = ptdf_multi_treading(circuit=self.grid, options=self.pf_options,
                                               group_by_technology=self.options.group_by_technology,
                                               power_amount=self.options.power_increment,
                                               text_func=self.progress_text.emit,
                                               prog_func=self.progress_signal.emit)
        else:

            self.results = ptdf(circuit=self.grid, options=self.pf_options,
                                group_by_technology=self.options.group_by_technology,
                                power_amount=self.options.power_increment,
                                text_func=self.progress_text.emit,
                                prog_func=self.progress_signal.emit)

        self.results.consolidate()

    def run(self):
        """

        :return:
        """
        start = time.time()
        self.ptdf()
        end = time.time()
        self.elapsed = end - start
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [v.name for v in self.results.variations]
        else:
            return list()

    def cancel(self):
        self.__cancel__ = True


if __name__ == '__main__':
    from GridCal.Engine import FileOpen, SolverType

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'

    main_circuit = FileOpen(fname).open()

    pf_options = PowerFlowOptions(solver_type=SolverType.DC)

    options = PTDFOptions(group_by_technology=False, use_multi_threading=True, power_increment=50)

    module = PTDF(grid=main_circuit, options=options, pf_options=pf_options)

    module.run()

    print(module.results.get_results_data_frame())

    print(module.elapsed)
