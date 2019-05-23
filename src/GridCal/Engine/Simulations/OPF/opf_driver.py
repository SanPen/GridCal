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

from PySide2.QtCore import QRunnable

from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.OPF.ac_opf import AcOpf
from GridCal.Engine.Simulations.OPF.dc_opf import DcOpf
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import SolverType
from GridCal.Engine.Simulations.OPF.nelder_mead_opf import AcOpfNelderMead
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class OptimalPowerFlowOptions:

    def __init__(self, verbose=False, load_shedding=False, generation_shedding=False,
                 solver=SolverType.DC_OPF, realistic_results=False, control_batteries=True,
                 faster_less_accurate=False, generation_shedding_weight=10000, load_shedding_weight=10000,
                 power_flow_options=None, bus_types=None):
        """
        OPF options constructor
        :param verbose:
        :param load_shedding:
        :param generation_shedding:
        :param solver:
        :param realistic_results:
        :param faster_less_accurate:
        :param bus_types:
        """
        self.verbose = verbose

        self.load_shedding = load_shedding

        self.generation_shedding = generation_shedding

        self. control_batteries = control_batteries

        self.solver = solver

        self.realistic_results = realistic_results

        self.faster_less_accurate = faster_less_accurate

        self.generation_shedding_weight = generation_shedding_weight

        self.load_shedding_weight = load_shedding_weight

        self.power_flow_options = power_flow_options

        self.bus_types = bus_types


class OptimalPowerFlow(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: OptimalPowerFlowOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        # OPF results
        self.results = None

        # set cancel state
        self.__cancel__ = False

        self.all_solved = True

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return list()

    def opf(self, t_idx=None, collect=True):
        """
        Run a power flow for every circuit
        @return: OptimalPowerFlowResults object
        """
        # print('PowerFlow at ', self.grid.name)

        # self.progress_signal.emit(0.0)
        numerical_circuit = self.grid.compile()
        islands = numerical_circuit.compute()

        if self.options.solver == SolverType.DC_OPF:
            # DC optimal power flow
            problem = DcOpf(self.grid, verbose=False,
                            allow_load_shedding=self.options.load_shedding,
                            allow_generation_shedding=self.options.generation_shedding,
                            generation_shedding_weight=self.options.generation_shedding_weight,
                            load_shedding_weight=self.options.load_shedding_weight)

        elif self.options.solver == SolverType.AC_OPF:
            # AC optimal power flow
            problem = AcOpf(self.grid, verbose=False,
                            allow_load_shedding=self.options.load_shedding,
                            allow_generation_shedding=self.options.generation_shedding,
                            generation_shedding_weight=self.options.generation_shedding_weight,
                            load_shedding_weight=self.options.load_shedding_weight)

        elif self.options.solver == SolverType.NELDER_MEAD_OPF:

            if self.options.power_flow_options is None:
                options = PowerFlowOptions(SolverType.LACPF, verbose=False,
                                           initialize_with_existing_solution=False,
                                           multi_core=False, dispatch_storage=True,
                                           control_q=False, control_taps=False)
            else:
                options = self.options.power_flow_options

            problem = AcOpfNelderMead(self.grid, options, verbose=False, break_at_value=False)

        else:
            raise Exception('Solver not recognized ' + str(self.options.solver))

        # Solve
        problem.build_solvers()
        problem.set_default_state()
        problem.solve(verbose=True)

        # get the branch flows (it is used more than one time)
        Sbr = problem.get_branch_flows()
        ld = problem.get_load_shedding()
        ld[ld == None] = 0
        bt = problem.get_batteries_power()
        bt[bt == None] = 0
        gn = problem.get_controlled_generation()
        gn[gn == None] = 0
        gs = problem.get_generation_shedding()
        gs[gs == None] = 0

        # pack the results
        self.results = OptimalPowerFlowResults(Sbus=None,
                                               voltage=problem.get_voltage(),
                                               load_shedding=ld * self.grid.Sbase,
                                               generation_shedding=gs * self.grid.Sbase,
                                               battery_power=bt * self.grid.Sbase,
                                               controlled_generation_power=gn * self.grid.Sbase,
                                               Sbranch=Sbr * self.grid.Sbase,
                                               overloads=problem.get_overloads(),
                                               loading=problem.get_loading(),
                                               converged=bool(problem.converged),
                                               bus_types = numerical_circuit.bus_types)

        return self.results

    def run(self):
        """

        :return:
        """
        self.opf(collect=True)

    def run_at(self, t):
        """
        Run power flow at the time series object index t
        @param t: time index
        @return: OptimalPowerFlowResults object
        """

        res = self.opf(t, collect=False)  # the collection of results is done in the OpfTimeSeriesDriver

        return res

    def cancel(self):
        self.__cancel__ = True

