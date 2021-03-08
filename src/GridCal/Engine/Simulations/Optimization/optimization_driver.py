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

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import single_island_pf
from GridCal.Engine.Simulations.Stochastic.monte_carlo_results import StochasticPowerFlowResults
from GridCal.Engine.Simulations.Stochastic.monte_carlo_driver import make_monte_carlo_input

########################################################################################################################
# Optimization classes
########################################################################################################################


class VoltageOptimizationProblem(OptimizationProblem):
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

        n = len(self.circuit.buses)
        m = self.circuit.get_branch_number()

        self.max_eval = max_iter

        # the dimension is the number of nodes
        self.dim = n
        self.min = 0
        self.minimum = np.zeros(self.dim)
        self.lb = -15 * np.ones(self.dim)
        self.ub = 20 * np.ones(self.dim)
        self.int_var = np.array([])
        self.cont_var = np.arange(0, self.dim)
        self.info = str(self.dim) + "Voltage collapse optimization"

        # results
        self.results = StochasticPowerFlowResults(n, m, self.max_eval, name='Voltage optimization')

        # compile circuits
        self.numerical_circuit = self.circuit.compile_snapshot()
        self.numerical_input_islands = self.numerical_circuit.compute(ignore_single_node_islands=options.ignore_single_node_islands)

        self.it = 0

    def eval(self, x):
        """
        Evaluate the Ackley function  at x

        :param x: Data point
        :type x: numpy.array
        :return: Value at x
        :rtype: float
        """
        # For every circuit, run the time series
        for numerical_island in self.numerical_input_islands:
            # sample from the CDF give the vector x of values in [0, 1]
            # c.sample_at(x)
            monte_carlo_input = make_monte_carlo_input(numerical_island)
            mc_time_series = monte_carlo_input.get_at(x)

            Y, I, S = mc_time_series.get_at(t=0)

            #  run the sampled values
            # res = self.power_flow.run_at(0, mc=True)
            res = single_island_pf(circuit, Vbus, Sbus, Ibus, options=self.options, logger=self.logger)

            self.results.S_points[self.it, numerical_island.original_bus_idx] = S
            self.results.V_points[self.it, numerical_island.original_bus_idx] = res.voltage[
                numerical_island.original_bus_idx]
            self.results.Sbr_points[self.it, numerical_island.original_branch_idx] = res.If[
                numerical_island.original_branch_idx]
            self.results.loading_points[self.it, numerical_island.original_branch_idx] = res.loading[
                numerical_island.original_branch_idx]

        self.it += 1
        if self.callback is not None:
            prog = self.it / self.max_eval * 100
            self.callback(prog)

        f = abs(self.results.V_points[self.it - 1, :].sum()) / self.dim
        # print(prog, ' % \t', f)

        return f


class Optimize(QThread):
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

    def run(self):
        """
        Run the optimization
        @return: Nothing
        """

        self.problem = VoltageOptimizationProblem(self.circuit,
                                                  self.options,
                                                  self.max_iter,
                                                  callback=self.progress_signal.emit)

        # # (1) Optimization problem
        # # print(data.info)
        #
        # # (2) Experimental design
        # # Use a symmetric Latin hypercube with 2d + 1 samples
        # exp_des = SymmetricLatinHypercube(dim=self.problem.dim, npts=2 * self.problem.dim + 1)
        #
        # # (3) Surrogate model
        # # Use a cubic RBF interpolant with a linear tail
        # surrogate = RBFInterpolant(kernel=CubicKernel, tail=LinearTail, maxp=self.max_eval)
        #
        # # (4) Adaptive sampling
        # # Use DYCORS with 100d candidate points
        # adapt_samp = CandidateDYCORS(data=self, numcand=100 * self.dim)
        #
        # # Use the serial controller (uses only one thread)
        # controller = SerialController(self.objfunction)
        #
        # # (5) Use the sychronous strategy without non-bound constraints
        # strategy = SyncStrategyNoConstraints(worker_id=0,
        #                                      data=self,
        #                                      maxeval=self.max_eval,
        #                                      nsamples=1,
        #                                      exp_design=exp_des,
        #                                      response_surface=surrogate,
        #                                      sampling_method=adapt_samp)
        #
        # controller.strategy = strategy
        #
        # # Run the optimization strategy
        # result = controller.run()
        #
        # # Print the final result
        # print('Best value found: {0}'.format(result.value))
        # print('Best solution found: {0}'.format(np.array_str(result.params[0], max_line_width=np.inf, precision=5,
        #                                                      suppress_small=True)))

        num_threads = 4

        surrogate_model = GPRegressor(dim=self.problem.dim)
        sampler = SymmetricLatinHypercube(dim=self.problem.dim, num_pts=2 * (self.problem.dim + 1))

        # Create a strategy and a controller
        controller = ThreadController()
        controller.strategy = SRBFStrategy(max_evals=self.max_iter,
                                           opt_prob=self.problem,
                                           exp_design=sampler,
                                           surrogate=surrogate_model,
                                           asynchronous=True,
                                           batch_size=num_threads)

        print("Number of threads: {}".format(num_threads))
        print("Maximum number of evaluations: {}".format(self.max_iter))
        print("Strategy: {}".format(controller.strategy.__class__.__name__))
        print("Experimental design: {}".format(sampler.__class__.__name__))
        print("Surrogate: {}".format(surrogate_model.__class__.__name__))

        # Launch the threads and give them access to the objective function
        for _ in range(num_threads):
            worker = BasicWorkerThread(controller, self.problem.eval)
            controller.launch_worker(worker)

        # Run the optimization strategy
        result = controller.run()

        print('Best value found: {0}'.format(result.value))
        print('Best solution found: {0}\n'.format(np.array_str(result.params[0],
                                                               max_line_width=np.inf,
                                                               precision=4, suppress_small=True)))

        self.solution = result.params[0]

        # Extract function values from the controller
        self.optimization_values = np.array([o.value for o in controller.fevals])

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
            ax.scatter(np.arange(0, max_eval), self.optimization_values, color=clr[6])
            # Best value found
            ax.plot(np.arange(0, max_eval), np.minimum.accumulate(self.optimization_values), color=clr[1],
                    linewidth=3.0)
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



