from GridCal.Engine.All import *


# Import the necessary modules
from pySOT import SymmetricLatinHypercube, RBFInterpolant
from GridCal.Engine.Replacements.poap_controller import SerialController, ThreadController, BasicWorkerThread
import numpy as np


class AcOPFBlackBox:
    """
    Linear power flow OPF
    Global optimum: :math:`f(0,0,...,0)=0`

    :param dim: Number of dimensions
    :type dim: int
    :ivar dim: Number of dimensions
    :type dim: int
    :ivar xlow: Lower bound constraints
    :type xlow: numpy.array
    :ivar xup: Upper bound constraints
    :type xup: numpy.array
    :ivar info: Problem information:
    :type info: string
    :ivar min: Global optimum
    :type min: float
    :ivar integer: Integer variables
    :type integer: numpy.array
    :ivar continuous: Continuous variables
    :type continuous: numpy.array
    """

    def __init__(self, multi_circuit: MultiCircuit, verbose=False):

        ################################################################
        # Compilation
        ################################################################

        self.verbose = verbose

        self.multi_circuit = multi_circuit

        self.numerical_circuit = self.multi_circuit.compile()

        self.islands = self.numerical_circuit.compute()

        # indices of generators that contribute to the static power vector 'S'
        self.gen_s_idx = np.where((np.logical_not(self.numerical_circuit.controlled_gen_dispatchable)
                                   * self.numerical_circuit.controlled_gen_enabled) == True)[0]

        self.bat_s_idx = np.where((np.logical_not(self.numerical_circuit.battery_dispatchable)
                                   * self.numerical_circuit.battery_enabled) == True)[0]

        # indices of generators that are to be optimized via the solution vector 'x'
        self.gen_x_idx = np.where((self.numerical_circuit.controlled_gen_dispatchable
                                   * self.numerical_circuit.controlled_gen_enabled) == True)[0]

        self.bat_x_idx = np.where((self.numerical_circuit.battery_dispatchable
                                   * self.numerical_circuit.battery_enabled) == True)[0]

        # compute the problem dimension
        dim = len(self.gen_x_idx) + len(self.bat_x_idx)

        # get the limits of the devices to control
        gens = np.array(multi_circuit.get_generators())
        bats = np.array(multi_circuit.get_batteries())
        gen_x_up = np.array([elm.Pmax for elm in gens[self.gen_x_idx]])
        gen_x_low = np.array([elm.Pmin for elm in gens[self.gen_x_idx]])
        bat_x_up = np.array([elm.Pmax for elm in bats[self.bat_x_idx]])
        bat_x_low = np.array([elm.Pmin for elm in bats[self.bat_x_idx]])

        # form S static ################################################

        # all the loads apply
        self.Sfix = self.numerical_circuit.C_load_bus.T * (
                    - self.numerical_circuit.load_power / self.numerical_circuit.Sbase * self.numerical_circuit.load_enabled)

        # static generators (all apply)
        self.Sfix += self.numerical_circuit.C_sta_gen_bus.T * (
                    self.numerical_circuit.static_gen_power / self.numerical_circuit.Sbase * self.numerical_circuit.static_gen_enabled)

        # controlled generators
        self.Sfix += (self.numerical_circuit.C_ctrl_gen_bus[self.gen_s_idx, :]).T * (
                    self.numerical_circuit.controlled_gen_power[self.gen_s_idx] / self.numerical_circuit.Sbase)

        # batteries
        self.Sfix += (self.numerical_circuit.C_batt_bus[self.bat_s_idx, :]).T * (
                    self.numerical_circuit.battery_power[self.bat_s_idx] / self.numerical_circuit.Sbase)

        # build A_sys per island ########################################
        for island in self.islands:
            island.build_linear_ac_sys_mat()  # builds the A matrix factorization and stores it internally

        ################################################################
        # internal variables for PySOT
        ################################################################
        self.xlow = np.r_[gen_x_low, bat_x_low] / self.multi_circuit.Sbase
        self.xup = np.r_[gen_x_up, bat_x_up] / self.multi_circuit.Sbase
        self.dim = dim
        self.info = str(dim) + "-dimensional OPF problem"
        self.min = 0
        self.integer = []
        self.continuous = np.arange(0, dim)
        check_opt_prob(self)
        ################################################################

    def set_fix_state_at(self, t):
        """

        Args:
            t: profiles time index
        """
        # all the loads apply
        self.Sfix = self.numerical_circuit.C_load_bus.T * (
                - self.numerical_circuit.load_power_profile[t, :] / self.numerical_circuit.Sbase * self.numerical_circuit.load_enabled)

        # static generators (all apply)
        self.Sfix += self.numerical_circuit.C_sta_gen_bus.T * (
                self.numerical_circuit.static_gen_power_profile[t, :] / self.numerical_circuit.Sbase * self.numerical_circuit.static_gen_enabled)

        # controlled generators
        self.Sfix += (self.numerical_circuit.C_ctrl_gen_bus[self.gen_s_idx, :]).T * (
                self.numerical_circuit.controlled_gen_power_profile[t, self.gen_s_idx] / self.numerical_circuit.Sbase)

        # batteries
        self.Sfix += (self.numerical_circuit.C_batt_bus[self.bat_s_idx, :]).T * (
                self.numerical_circuit.battery_power_profile[t, self.bat_s_idx] / self.numerical_circuit.Sbase)

    def objfunction(self, x):
        """
        Evaluate the Ackley function  at x
        :param x: Data point
        :type x: numpy.array
        :return: Value at x
        :rtype: float
        """

        if len(x) != self.dim:
            raise ValueError('Dimension mismatch')

        # modify S
        S = self.Sfix.copy()
        ngen = len(self.gen_x_idx)
        S += (self.numerical_circuit.C_ctrl_gen_bus[self.gen_x_idx, :]).T * x[0:ngen]  # controlled generators
        S += (self.numerical_circuit.C_batt_bus[self.bat_x_idx, :]).T * x[ngen:]  # batteries

        # evaluate
        f = 0

        for island in self.islands:

            npv = len(island.pv)
            npq = len(island.pq)

            # build the right-hand-side vector
            rhs = r_[S.real[island.pqpv], S.imag[island.pq]]

            # solve the linear system
            inc_v = island.Asys(rhs)

            # compose the results vector
            V = island.Vbus.copy()

            # set the PV voltages
            va_pv = inc_v[0:npv]
            vm_pv = np.abs(island.Vbus[island.pv])
            V[island.pv] = vm_pv * exp(1j * va_pv)

            # set the PQ voltages
            va_pq = inc_v[npv:npv + npq]
            vm_pq = ones(npq) + inc_v[npv + npq::]
            V[island.pq] = vm_pq * exp(1j * va_pq)

            # build island power flow results
            island_res = island.compute_branch_results(V)
            island_res.voltage = V

            Vm = np.abs(V)
            vmax = self.numerical_circuit.Vmax[island.original_bus_idx]
            vmin = self.numerical_circuit.Vmin[island.original_bus_idx]

            # sum overloads
            over_loading_idx = np.where(island_res.loading > 1)[0]
            f += np.abs(island_res.loading[over_loading_idx] - 1.0).sum()

            # add over voltages
            idx_over_v = np.where(Vm > vmax)[0]
            f += np.abs(Vm[idx_over_v] - vmax[idx_over_v]).sum()

            # add under voltages
            idx_under_v = np.where(Vm < vmin)[0]
            f += np.abs(vmin[idx_under_v] - Vm[idx_under_v]).sum()

        if self.verbose:
            print('fobj:', x, ':', f)

        return f


def solve_opf_dycors_serial(problem: AcOPFBlackBox, maxeval=1000, verbose=False):
    """

    :param problem:
    :return:
    """

    print(problem.info)

    # (2) Experimental design
    # Use a symmetric Latin hypercube with 2d + 1 samples
    exp_des = SymmetricLatinHypercube(dim=problem.dim, npts=2 * problem.dim + 1)

    # (3) Surrogate model
    # Use a cubic RBF interpolant with a linear tail
    surrogate = RBFInterpolant(kernel=CubicKernel, tail=LinearTail, maxp=maxeval)

    # (4) Adaptive sampling
    # Use DYCORS with 100d candidate points
    adapt_samp = CandidateDYCORS(data=problem, numcand=100 * problem.dim)

    # Use the serial controller (uses only one thread)
    controller = SerialController(problem.objfunction)

    # (5) Use the sychronous strategy without non-bound constraints
    strategy = SyncStrategyNoConstraints(worker_id=0, data=problem, maxeval=maxeval, nsamples=1,
                                         exp_design=exp_des, response_surface=surrogate,
                                         sampling_method=adapt_samp)
    controller.strategy = strategy

    # Run the optimization strategy
    result = controller.run(stop_at=True, stop_value=0)

    # Print the final result
    if verbose:
        print('Best value found: {0}'.format(result.value))
        print('Best solution found: {0}'.format(
            np.array_str(result.params[0], max_line_width=np.inf, precision=5, suppress_small=True)))

    return result.value


def solve_opf_dycors_parallel(problem: AcOPFBlackBox, maxeval=1000, nthreads = 4, verbose=False):
    """

    :param problem:
    :return:
    """

    print(problem.info)

    # (2) Experimental design
    # Use a symmetric Latin hypercube with 2d + 1 samples
    exp_des = SymmetricLatinHypercube(dim=problem.dim, npts=2 * problem.dim + 1)

    # (3) Surrogate model
    # Use a cubic RBF interpolant with a linear tail
    surrogate = RBFInterpolant(kernel=CubicKernel, tail=LinearTail, maxp=maxeval)

    # (4) Adaptive sampling
    # Use DYCORS with 100d candidate points
    adapt_samp = CandidateDYCORS(data=problem, numcand=100 * problem.dim)

    # Use the threaded controller
    controller = ThreadController()

    # (5) Use the sychronous strategy without non-bound constraints
    # Use 4 threads and allow for 4 simultaneous evaluations

    strategy = SyncStrategyNoConstraints(
            worker_id=0, data=problem, maxeval=maxeval, nsamples=nthreads,
            exp_design=exp_des, response_surface=surrogate,
            sampling_method=adapt_samp)
    controller.strategy = strategy

    # Launch the threads and give them access to the objective function
    for _ in range(nthreads):
        worker = BasicWorkerThread(controller, problem.objfunction)
        controller.launch_worker(worker)

    # Run the optimization strategy
    result = controller.run()

    # Print the final result
    if verbose:
        print('Best value found: {0}'.format(result.value))
        print('Best solution found: {0}'.format(
            np.array_str(result.params[0], max_line_width=np.inf, precision=5, suppress_small=True)))

    return result.value


if __name__ == '__main__':

    main_circuit = MultiCircuit()
    # fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\IEEE 30 Bus with storage.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 30 Bus with storage.xlsx'

    print('Reading...')
    main_circuit.load_file(fname)

    # (1) Optimization problem
    problem = AcOPFBlackBox(main_circuit, verbose=False)

    # solve
    solve_opf_dycors_serial(problem, verbose=True)

    # solve
    solve_opf_dycors_parallel(problem, verbose=True)
