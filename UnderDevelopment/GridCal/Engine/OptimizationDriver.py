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
import os
import pickle as pkl
from warnings import warn
import pandas as pd
import pulp
import numpy as np
from numpy import complex, zeros, exp, r_, array, angle, c_, power, vstack, ones, arange
from pyDOE import lhs
from matplotlib import pyplot as plt
import multiprocessing
from PyQt5.QtCore import QThread, QRunnable, pyqtSignal
from sklearn.ensemble import RandomForestRegressor
from pySOT import *
from poap.controller import SerialController
from GridCal.Engine.CalculationEngine import MultiCircuit
from GridCal.Engine.PowerFlowDriver import PowerFlow, PowerFlowOptions
from GridCal.Engine.IoStructures import MonteCarloResults
from GridCal.Engine.StochasticDriver import make_monte_carlo_input

########################################################################################################################
# Optimization classes
########################################################################################################################


class Optimize(QThread):
    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

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

        self.__cancel__ = False

        # initialize the power flow
        self.power_flow = PowerFlow(self.circuit, self.options)

        self.max_eval = max_iter
        n = len(self.circuit.buses)
        m = len(self.circuit.branches)

        # the dimension is the number of nodes
        self.dim = n

        # results
        self.results = MonteCarloResults(n, m, self.max_eval)

        # variables for the optimization
        self.xlow = zeros(n)  # lower bounds
        self.xup = ones(n)
        self.info = ""  # info
        self.integer = array([])  # integer variables
        self.continuous = arange(0, n, 1)  # continuous variables
        self.solution = None
        self.optimization_values = None
        self.it = 0

        # compile
        # compile circuits
        self.numerical_circuit = self.circuit.compile()
        self.numerical_input_islands = self.numerical_circuit.compute()

    def objfunction(self, x):
        """
        Objective function to run
        :param x: combinations of values between 0~1
        :return: objective function value, the average voltage in this case
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
            res = self.power_flow.run_pf(circuit=numerical_island, Vbus=numerical_island.Vbus, Sbus=S, Ibus=I)

            # Y, I, S = circuit.mc_time_series.get_at(0)
            self.results.S_points[self.it, numerical_island.original_bus_idx] = S
            self.results.V_points[self.it, numerical_island.original_bus_idx] = res.voltage[numerical_island.original_bus_idx]
            self.results.I_points[self.it, numerical_island.original_branch_idx] = res.Ibranch[numerical_island.original_branch_idx]
            self.results.loading_points[self.it, numerical_island.original_branch_idx] = res.loading[numerical_island.original_branch_idx]

        self.it += 1
        prog = self.it / self.max_eval * 100
        # self.progress_signal.emit(prog)

        f = abs(self.results.V_points[self.it - 1, :].sum()) / self.dim
        # print(prog, ' % \t', f)

        return f

    def run(self):
        """
        Run the optimization
        @return: Nothing
        """
        self.it = 0
        n = len(self.circuit.buses)
        m = len(self.circuit.branches)
        self.xlow = zeros(n)  # lower bounds
        self.xup = ones(n)  # upper bounds
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Running stochastic voltage collapse...')
        self.results = MonteCarloResults(n, m, self.max_eval)

        # (1) Optimization problem
        # print(data.info)

        # (2) Experimental design
        # Use a symmetric Latin hypercube with 2d + 1 samples
        exp_des = SymmetricLatinHypercube(dim=self.dim, npts=2 * self.dim + 1)

        # (3) Surrogate model
        # Use a cubic RBF interpolant with a linear tail
        surrogate = RBFInterpolant(kernel=CubicKernel, tail=LinearTail, maxp=self.max_eval)

        # (4) Adaptive sampling
        # Use DYCORS with 100d candidate points
        adapt_samp = CandidateDYCORS(data=self, numcand=100 * self.dim)

        # Use the serial controller (uses only one thread)
        controller = SerialController(self.objfunction)

        # (5) Use the sychronous strategy without non-bound constraints
        strategy = SyncStrategyNoConstraints(worker_id=0,
                                             data=self,
                                             maxeval=self.max_eval,
                                             nsamples=1,
                                             exp_design=exp_des,
                                             response_surface=surrogate,
                                             sampling_method=adapt_samp)
        controller.strategy = strategy

        # Run the optimization strategy
        result = controller.run()

        # Print the final result
        print('Best value found: {0}'.format(result.value))
        print('Best solution found: {0}'.format(np.array_str(result.params[0], max_line_width=np.inf, precision=5,
                                                             suppress_small=True)))
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



