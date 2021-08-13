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
import multiprocessing

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.LinearFactors.linear_analysis import *
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.driver_template import DriverTemplate


########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class LinearAnalysisResults(ResultsTemplate):

    def __init__(self, n_br=0, n_bus=0, br_names=(), bus_names=(), bus_types=()):
        """
        PTDF and LODF results class
        :param n_br: number of branches
        :param n_bus: number of buses
        :param br_names: branch names
        :param bus_names: bus names
        :param bus_types: bus types array
        """
        ResultsTemplate.__init__(self,
                                 name='Linear Analysis',
                                 available_results=[ResultTypes.PTDFBranchesSensitivity,
                                                    ResultTypes.OTDF,
                                                    ResultTypes.BranchActivePowerFrom,
                                                    ResultTypes.BranchLoading],
                                 data_variables=['branch_names',
                                                 'bus_names',
                                                 'bus_types',
                                                 'PTDF',
                                                 'LODF',
                                                 'Sf',
                                                 'loading'])
        # number of branches
        self.n_br = n_br

        self.n_bus = n_bus

        # names of the branches
        self.branch_names = br_names

        self.bus_names = bus_names

        self.bus_types = bus_types

        self.logger = Logger()

        self.PTDF = np.zeros((n_br, n_bus))
        self.LODF = np.zeros((n_br, n_br))

        self.Sf = np.zeros(self.n_br)

        self.loading = np.zeros(self.n_br)

    def apply_new_rates(self, nc: "SnapshotData"):
        """

        :param nc:
        :return:
        """
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results.

        Arguments:

            **result_type**: ResultTypes

        Returns: ResultsModel
        """

        if result_type == ResultTypes.PTDFBranchesSensitivity:
            labels = self.bus_names
            y = self.PTDF
            y_label = '(p.u.)'
            title = 'Branches sensitivity'

        elif result_type == ResultTypes.OTDF:
            labels = self.branch_names
            y = self.LODF
            y_label = '(p.u.)'
            title = 'Branch failure sensitivity'

        elif result_type == ResultTypes.BranchActivePowerFrom:
            labels = self.branch_names
            y = self.Sf
            y_label = '(MW)'
            title = 'Branch Sf'

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            y = self.loading * 100.0
            y_label = '(%)'
            title = 'Branch loading'

        else:
            labels = []
            y = np.zeros(0)
            y_label = ''
            title = ''

        # assemble model
        mdl = ResultsTable(data=y,
                           index=self.branch_names,
                           columns=labels,
                           title=title,
                           ylabel=y_label,
                           units=y_label)
        return mdl


class LinearAnalysisOptions:

    def __init__(self, distribute_slack=True, correct_values=True):
        """
        Power Transfer Distribution Factors' options
        :param distribute_slack:
        """
        self.distribute_slack = distribute_slack
        self.correct_values = correct_values


class LinearAnalysisDriver(DriverTemplate):
    name = 'Linear analysis'
    tpe = SimulationTypes.LinearAnalysis_run

    def __init__(self, grid: MultiCircuit, options: LinearAnalysisOptions):
        """
        Power Transfer Distribution Factors class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        DriverTemplate.__init__(self, grid=grid)

        # Options to use
        self.options = options

        # OPF results
        self.results = LinearAnalysisResults(n_br=0,
                                             n_bus=0,
                                             br_names=[],
                                             bus_names=[],
                                             bus_types=[])

        self.all_solved = True

    def run(self):
        """
        Run thread
        """
        start = time.time()
        self.progress_text.emit('Analyzing')
        self.progress_signal.emit(0)

        # Run Analysis
        analysis = LinearAnalysis(grid=self.grid,
                                  distributed_slack=self.options.distribute_slack,
                                  correct_values=self.options.correct_values)

        analysis.run()

        self.results = LinearAnalysisResults(n_br=analysis.numerical_circuit.nbr,
                                             n_bus=analysis.numerical_circuit.nbus,
                                             br_names=analysis.numerical_circuit.branch_data.branch_names,
                                             bus_names=analysis.numerical_circuit.bus_data.bus_names,
                                             bus_types=analysis.numerical_circuit.bus_data.bus_types)
        self.results.PTDF = analysis.PTDF
        self.results.LODF = analysis.LODF
        self.results.Sf = analysis.get_flows(analysis.numerical_circuit.Sbus.real)

        self.logger += analysis.logger

        end = time.time()
        self.elapsed = end - start
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [v for v in self.results.bus_names]
        else:
            return list()


if __name__ == '__main__':

    from GridCal.Engine import FileOpen, SolverType

    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'

    main_circuit = FileOpen(fname).open()

    options = LinearAnalysisOptions()
    simulation = LinearAnalysisDriver(grid=main_circuit, options=options)
    simulation.run()
    ptdf_df = simulation.results.mdl(result_type=ResultTypes.PTDFBranchesSensitivity)

    print(ptdf_df.get_data_frame())


