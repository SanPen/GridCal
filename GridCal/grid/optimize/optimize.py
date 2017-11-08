from matplotlib import pyplot as plt
from numpy import ones

from GridCal.grid.calculate.power_flow.runnable import PowerFlowRunnable
from GridCal.grid.calculate.power_flow.options import PowerFlowOptions
from GridCal.grid.model.circuit import MultiCircuit


class Optimize(QThread):

    progress_signal = pyqtSignal(float)
    progress_text = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, max_iter=1000):
        """
        Constructor
        Args:
            grid: Grid to cascade
            options: Power flow Options
            triggering_idx: branch indices to trigger first
        """

        QThread.__init__(self)

        self.grid = grid

        self.options = options

        self.__cancel__ = False

        # initialize the power flow
        self.power_flow = PowerFlowRunnable(self.grid, self.options)

        self.max_eval = max_iter
        n = len(self.grid.buses)
        m = len(self.grid.branches)

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

    def objfunction(self, x):

        # For every circuit, run the time series
        for c in self.grid.circuits:

            # sample from the CDF give the vector x of values in [0, 1]
            c.sample_at(x)

            #  run the sampled values
            res = self.power_flow.run_at(0, mc=True)

            Y, I, S = c.mc_time_series.get_at(0)
            self.results.S_points[self.it, c.bus_original_idx] = S
            self.results.V_points[self.it, c.bus_original_idx] = res.voltage[c.bus_original_idx]
            self.results.I_points[self.it, c.branch_original_idx] = res.Ibranch[c.branch_original_idx]
            self.results.loading_points[self.it, c.branch_original_idx] = res.loading[c.branch_original_idx]

        self.it += 1
        prog = self.it / self.max_eval * 100
        # self.progress_signal.emit(prog)

        f = abs(self.results.V_points[self.it-1, :].sum()) / self.dim
        print(prog, ' % \t', f)

        return f

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        self.it = 0
        n = len(self.grid.buses)
        m = len(self.grid.branches)
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
        Returns:

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
            ax.plot(np.arange(0, max_eval), np.minimum.accumulate(self.optimization_values), color=clr[1], linewidth=3.0)
            ax.set_xlabel('Evaluations')
            ax.set_ylabel('Function Value')
            ax.set_title('Optimization convergence')

    def cancel(self):
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()
