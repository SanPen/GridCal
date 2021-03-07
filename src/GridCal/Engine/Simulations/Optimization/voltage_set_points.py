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
import numpy as np
from matplotlib import pyplot as plt
from PySide2.QtCore import QThread, Signal
from pySOT.experimental_design import SymmetricLatinHypercube
from pySOT.strategy import SRBFStrategy
from pySOT.surrogate import GPRegressor
from pySOT.optimization_problems import OptimizationProblem
from poap.controller import ThreadController, BasicWorkerThread
from scipy.optimize import fmin_bfgs, minimize

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
from GridCal.Engine.Simulations.Stochastic.monte_carlo_results import StochasticPowerFlowResults
from GridCal.Engine.Simulations.Stochastic.monte_carlo_driver import make_monte_carlo_input

########################################################################################################################
# Optimization classes
########################################################################################################################


class SetPointsOptimizationProblem(OptimizationProblem):
    """

    :ivar dim: Number of dimensions
    :ivar lb: Lower variable bounds
    :ivar ub: Upper variable bounds
    :ivar int_var: Integer variables
    :ivar cont_var: Continuous variables
    :ivar min: Global minimum value
    :ivar minimum: Global minimizer
    :ivar info: String with problem info
    """
    def __init__(self, circuit: MultiCircuit, options: PowerFlowOptions, max_iter=1000, callback=None):
        self.circuit = circuit

        self.options = options

        self.callback = callback

        # initialize the power flow
        self.power_flow = PowerFlowDriver(self.circuit, self.options)

        # compile circuits
        self.numerical_circuit = self.circuit.compile_snapshot()
        self.numerical_input_islands = self.numerical_circuit.compute()

        n = len(self.circuit.buses)
        m = self.circuit.get_branch_number()

        self.max_eval = max_iter

        # the dimension is the number of nodes
        self.dim = self.numerical_circuit.n_gen
        self.x0 = np.abs(self.numerical_circuit.generator_voltage) - np.ones(self.dim)
        self.min = 0
        self.minimum = np.zeros(self.dim)
        self.lb = -0.1 * np.ones(self.dim)
        self.ub = 0.1 * np.ones(self.dim)
        self.int_var = np.array([])
        self.cont_var = np.arange(0, self.dim)
        self.info = str(self.dim) + "Generators voltage set points optimization"

        # results
        self.results = StochasticPowerFlowResults(n, m, self.max_eval, name='Set point optimization')

        self.all_f = list()

        self.it = 0

    def eval(self, x):
        """
        Evaluate the function  at x

        :param x: Data point; x is a vector of Vset increment for all the generators
        :type x: numpy.array
        :return: Value at x
        :rtype: float
        """

        inc_v = self.numerical_circuit.C_bus_gen.T * x

        losses = np.empty(self.numerical_circuit.nbr, dtype=complex)

        # For every circuit, run the time series
        for island in self.numerical_input_islands:
            # sample from the CDF give the vector x of values in [0, 1]
            # c.sample_at(x)

            V = island.Vbus + inc_v[island.original_bus_idx]

            #  run the sampled values
            # res = self.power_flow.run_at(0, mc=True)
            res = single_island_pf(circuit, Vbus, Sbus, Ibus, options=self.options, logger=self.logger)

            # self.results.S_points[self.it, island.original_bus_idx] = island.Sbus
            # self.results.V_points[self.it, island.original_bus_idx] = res.voltage[island.original_bus_idx]
            # self.results.I_points[self.it, island.original_branch_idx] = res.If[island.original_branch_idx]
            # self.results.loading_points[self.it, island.original_branch_idx] = res.loading[island.original_branch_idx]
            # self.results.losses_points[self.it, island.original_branch_idx] = res.losses[island.original_branch_idx]
            losses[island.original_branch_idx] = res.losses[island.original_branch_idx]

        f = np.abs(losses.sum()) / self.dim
        self.it += 1
        if self.callback is not None:
            prog = self.it / self.max_eval * 100
            # self.callback(prog)
            self.callback(f)

        # print(prog, ' % \t', f)

        self.all_f.append(f)

        return f


class OptimizeVoltageSetPoints(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, circuit: MultiCircuit, options: PowerFlowOptions, max_iter=1000):
        """
        Constructor
        Args:
            circuit: Grid to cascade
            options: Power flow Options
            max_iter: max iterations
        """

        QThread.__init__(self)

        self.circuit = circuit

        self.options = options

        self.max_iter = max_iter

        self.__cancel__ = False

        self.problem = None

        self.solution = None

        self.optimization_values = None

    def run_bfgs(self):
        """
        Run the optimization
        @return: Nothing
        """

        self.problem = SetPointsOptimizationProblem(self.circuit,
                                                    self.options,
                                                    self.max_iter,
                                                    callback=self.progress_signal.emit)

        xopt = fmin_bfgs(f=self.problem.eval, x0=self.problem.x0,
                         fprime=None, args=(), gtol=1e-05,  epsilon=1e-2,
                         maxiter=self.max_iter, full_output=0, disp=1, retall=0,
                         callback=None)

        self.solution = np.ones(self.problem.dim) + xopt

        # Extract function values from the controller
        self.optimization_values = np.array(self.problem.all_f)

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def run_slsqp(self):

        self.problem = SetPointsOptimizationProblem(self.circuit,
                                                    self.options,
                                                    self.max_iter,
                                                    callback=self.progress_signal.emit)

        bounds = [(l, u) for l, u in zip(self.problem.lb, self.problem.ub)]

        options = {'maxiter': self.max_iter, 'tol': 0.01}

        res = minimize(fun=self.problem.eval, x0=self.problem.x0, method='SLSQP', bounds=bounds, options=options)

        self.solution = np.ones(self.problem.dim) + res.x

        # Extract function values from the controller
        self.optimization_values = np.array(self.problem.all_f)

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def plot(self, ax=None):
        """
        Plot the optimization convergence
        """
        clr = np.array(['#2200CC', '#D9007E', '#FF6600', '#FFCC00', '#ACE600', '#0099CC',
                        '#8900CC', '#FF0000', '#FF9900', '#FFFF00', '#00CC01', '#0055CC'])
        if self.optimization_values is not None:
            max_eval = len(self.optimization_values)

            if ax is None:
                f, ax = plt.subplots()
            # Points
            ax.scatter(np.arange(0, max_eval), self.optimization_values, color='b', s=10)
            # Best value found
            ax.plot(np.arange(0, max_eval), np.minimum.accumulate(self.optimization_values), color='r',
                    linewidth=3.0, alpha=0.8)
            ax.set_xlabel('Evaluations')
            ax.set_ylabel('Function Value')
            ax.set_title('Optimization convergence')

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()


if __name__ == '__main__':
    import time
    from GridCal.Engine import *

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    fname = '/mnt/sdc1/tmp/src/ReePlexos/spain_plexos(sin restricciones).gridcal'

    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(solver_type=SolverType.LACPF)

    opt = OptimizeVoltageSetPoints(circuit=main_circuit, options=pf_options, max_iter=100)
    opt.progress_signal.connect(print)

    # opt.run_bfgs()
    # print(opt.solution)
    # opt.plot()

    a = time.time()
    opt.run_slsqp()
    print(opt.solution)
    opt.plot()
    print('Elapsed', time.time() - a)
    plt.show()
