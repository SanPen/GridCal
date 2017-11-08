import pandas as pd
from warnings import warn

from matplotlib import pyplot as plt
from numpy import ones, r_, linalg, Inf, delete, zeros, double, conj, where, \
    ndarray, array, maximum

from GridCal.grid.calculate.power_flow.FastDecoupled import FDPF
from GridCal.grid.calculate.power_flow.Helm import helm
from GridCal.grid.calculate.power_flow.JacobianBased import Jacobian, IwamotoNR, \
    LevenbergMarquardtPF
from GridCal.grid.plot.params import LINEWIDTH
from GridCal.grid.model.node_type import NodeType
from GridCal.grid.calculate.solver_type import SolverType
from GridCal.grid.model.circuit import MultiCircuit, Circuit


class PowerFlowOptions:

    def __init__(self, solver_type: SolverType = SolverType.NR, aux_solver_type: SolverType = SolverType.HELM,
                 verbose=False, robust=False, initialize_with_existing_solution=True, dispatch_storage=True,
                 tolerance=1e-6, max_iter=25, control_q=True):
        """
        Power flow execution options
        @param solver_type:
        @param aux_solver_type:
        @param verbose:
        @param robust:
        @param initialize_with_existing_solution:
        @param dispatch_storage:
        @param tolerance:
        @param max_iter:
        @param control_q:
        """
        self.solver_type = solver_type

        self.auxiliary_solver_type = aux_solver_type

        self.tolerance = tolerance

        self.max_iter = max_iter

        self.control_Q = control_q

        self.dispatch_storage = dispatch_storage

        self.verbose = verbose

        self.robust = robust

        self.initialize_with_existing_solution = initialize_with_existing_solution

        self.dispatch_storage = dispatch_storage


class PowerFlowInput:

    def __init__(self, n, m):
        """
        Power Flow study input values
        @param n: Number of buses
        @param m: Number of branches
        """
        # Array of integer values representing the buses types
        self.types = zeros(n, dtype=int)

        self.ref = None

        self.pv = None

        self.pq = None

        self.sto = None

        self.pqpv = None

        # Branch admittance matrix with the from buses
        self.Yf = zeros((m, n), dtype=complex)

        # Branch admittance matrix with the to buses
        self.Yt = zeros((m, n), dtype=complex)

        # Array with the 'from' index of the from bus of each branch
        self.F = zeros(m, dtype=int)

        # Array with the 'to' index of the from bus of each branch
        self.T = zeros(m, dtype=int)

        # array to store a 1 for the active branches
        self.active_branches = zeros(m, dtype=int)

        # Full admittance matrix (will be converted to sparse)
        self.Ybus = zeros((n, n), dtype=complex)

        # Full impedance matrix (will be computed upon requirement ad the inverse of Ybus)
        self.Zbus = None

        # Admittance matrix of the series elements (will be converted to sparse)
        self.Yseries = zeros((n, n), dtype=complex)

        # Admittance matrix of the shunt elements (actually it is only the diagonal, so let's make it a vector)
        self.Yshunt = zeros(n, dtype=complex)

        # Jacobian matrix 1 for the fast-decoupled power flow
        self.B1 = zeros((n, n), dtype=double)

        # Jacobian matrix 2 for the fast-decoupled power flow
        self.B2 = zeros((n, n), dtype=double)

        # Array of line-line nominal voltages of the buses
        self.Vnom = zeros(n)

        # Currents at the buses array
        self.Ibus = zeros(n, dtype=complex)

        # Powers at the buses array
        self.Sbus = zeros(n, dtype=complex)

        # Voltages at the buses array
        self.Vbus = zeros(n, dtype=complex)

        self.Vmin = zeros(n, dtype=double)

        self.Vmax = zeros(n, dtype=double)

        self.Qmin = ones(n, dtype=double) * -9999

        self.Qmax = ones(n, dtype=double) * 9999

        self.branch_rates = zeros(m)

        self.bus_names = zeros(n, dtype=object)

        self.available_structures = ['Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries', 'Types', 'Jacobian']

    def compile(self):
        """
        Make the matrices sparse
        Create the ref, pv and pq lists
        @return:
        """
        self.Yf = sparse(self.Yf)
        self.Yt = sparse(self.Yt)
        self.Ybus = sparse(self.Ybus)
        self.Yseries = sparse(self.Yseries)
        self.B1 = sparse(self.B1)
        self.B2 = sparse(self.B2)
        # self.Yshunt = sparse(self.Yshunt)  No need to make it sparse, it is a vector already
        # compile the types lists from the types vector
        self.compile_types()

    def mismatch(self, V, Sbus):
        """
        Compute the power flow mismatch
        @param V: Voltage array (calculated)
        @param Sbus: Power array (especified)
        @return: mismatch of the computed solution
        """
        Scalc = V * conj(self.Ybus * V)
        mis = Scalc - Sbus  # compute the mismatch
        F = r_[mis[self.pv].real,
               mis[self.pq].real,
               mis[self.pq].imag]

        # check tolerance
        normF = linalg.norm(F, Inf)

        return normF

    def compile_types(self, types_new=None):
        """
        Compile the types
        @return:
        """
        if types_new is not None:
            self.types = types_new.copy()
        self.pq = where(self.types == NodeType.PQ.value[0])[0]
        self.pv = where(self.types == NodeType.PV.value[0])[0]
        self.ref = where(self.types == NodeType.REF.value[0])[0]
        self.sto = where(self.types == NodeType.STO_DISPATCH.value)[0]

        if len(self.ref) == 0:
            if len(self.pv) == 0:
                warn('There are no slack nodes selected')
            else:  # select the first PV generator as the slack
                mx = max(self.Sbus)
                i = where(self.Sbus == mx)[0]
                print('Setting the bus ' + str(i) + ' as slack instead of pv')
                self.pv = delete(self.pv, i)
                self.ref = [i]
            self.ref = ndarray.flatten(array(self.ref))
        else:
            pass  # no problem :)

        self.pqpv = r_[self.pq, self.pv]
        self.pqpv.sort()

    def set_from(self, obj, bus_idx, br_idx):
        """
        Copy data from other PowerFlowInput object
        @param obj: PowerFlowInput instance
        @param bus_idx: original bus indices
        @param br_idx: original branch indices
        @return:
        """
        self.types[bus_idx] = obj.types

        self.bus_names[bus_idx] = obj.bus_names

        # self.ref = None
        #
        # self.pv = None
        #
        # self.pq = None
        #
        # self.sto = None

        # Branch admittance matrix with the from buses
        self.Yf[br_idx, :][:, bus_idx] = obj.Yf.todense()

        # Branch admittance matrix with the to buses
        self.Yt[br_idx, :][:, bus_idx] = obj.Yt.todense()

        # Array with the 'from' index of the from bus of each branch
        self.F[br_idx] = obj.F

        # Array with the 'to' index of the from bus of each branch
        self.T[br_idx] = obj.T

        # array to store a 1 for the active branches
        self.active_branches[br_idx] = obj.active_branches

        # Full admittance matrix (will be converted to sparse)
        self.Ybus[bus_idx, :][:, bus_idx] = obj.Ybus.todense()

        # Admittance matrix of the series elements (will be converted to sparse)
        self.Yseries[bus_idx, :][:, bus_idx] = obj.Yseries.todense()

        # Admittance matrix of the shunt elements (will be converted to sparse)
        self.Yshunt[bus_idx] = obj.Yshunt

        # Currents at the buses array
        self.Ibus[bus_idx] = obj.Ibus

        # Powers at the buses array
        self.Sbus[bus_idx] = obj.Sbus

        # Voltages at the buses array
        self.Vbus[bus_idx] = obj.Vbus

        self.Vmin[bus_idx] = obj.Vmin

        self.Vmax[bus_idx] = obj.Vmax

        # self.Qmin = ones(n, dtype=double) * -9999
        #
        # self.Qmax = ones(n, dtype=double) * 9999

        self.branch_rates[br_idx] = obj.branch_rates

        self.compile()

    def get_structure(self, structure_type):
        """
        Get a DataFrame with the input
        Args:
            structure_type: 'Vbus', 'Sbus', 'Ibus', 'Ybus', 'Yshunt', 'Yseries', 'Types'

        Returns: Pandas DataFrame
        """

        if structure_type == 'Vbus':

            df = pd.DataFrame(data=self.Vbus, columns=['Voltage (p.u.)'], index=self.bus_names)

        elif structure_type == 'Sbus':
            df = pd.DataFrame(data=self.Sbus, columns=['Power (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ibus':
            df = pd.DataFrame(data=self.Ibus, columns=['Current (p.u.)'], index=self.bus_names)

        elif structure_type == 'Ybus':
            df = pd.DataFrame(data=self.Ybus.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Yshunt':
            df = pd.DataFrame(data=self.Yshunt, columns=['Shunt admittance (p.u.)'], index=self.bus_names)

        elif structure_type == 'Yseries':
            df = pd.DataFrame(data=self.Yseries.toarray(), columns=self.bus_names, index=self.bus_names)

        elif structure_type == 'Types':
            df = pd.DataFrame(data=self.types, columns=['Bus types'], index=self.bus_names)

        elif structure_type == 'Jacobian':

            J = Jacobian(self.Ybus, self.Vbus, self.Ibus, self.pq, self.pqpv)

            """
            J11 = dS_dVa[array([pvpq]).T, pvpq].real
            J12 = dS_dVm[array([pvpq]).T, pq].real
            J21 = dS_dVa[array([pq]).T, pvpq].imag
            J22 = dS_dVm[array([pq]).T, pq].imag
            """
            npq = len(self.pq)
            npv = len(self.pv)
            npqpv = npq + npv
            cols = ['dS/dVa'] * npqpv + ['dS/dVm'] * npq
            rows = cols
            df = pd.DataFrame(data=J.toarray(), columns=cols, index=rows)

        else:

            raise Exception('PF input: structure type not found')

        return df


class PowerFlowResults:

    def __init__(self, Sbus=None, voltage=None, Sbranch=None, Ibranch=None, loading=None, losses=None, error=None,
                 converged=None, Qpv=None, inner_it=None, outer_it=None, elapsed=None, methods=None):
        """

        @param voltage: Voltages array (p.u.)
        @param Sbranch: Branches power array (MVA)
        @param Ibranch: Branches current array (p.u.)
        @param loading: Branches loading array (p.u.)
        @param losses: Branches losses array (MW)
        @param error: power flow error value
        @param converged: converged (True / False)
        @param Qpv: Reactive power at the PV nodes array (p.u.)
        """
        self.Sbus = Sbus

        self.voltage = voltage

        self.Sbranch = Sbranch

        self.Ibranch = Ibranch

        self.loading = loading

        self.losses = losses

        self.error = error

        self.converged = converged

        self.Qpv = Qpv

        self.overloads = None

        self.overvoltage = None

        self.undervoltage = None

        self.overloads_idx = None

        self.overvoltage_idx = None

        self.undervoltage_idx = None

        self.buses_useful_for_storage = None

        self.available_results = ['Bus voltage', 'Branch power', 'Branch current', 'Branch_loading', 'Branch losses']

        self.plot_bars_limit = 100

        self.inner_iterations = inner_it

        self.outer_iterations = outer_it

        self.elapsed = elapsed

        self.methods = methods

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return PowerFlowResults(Sbus=self.Sbus, voltage=self.voltage, Sbranch=self.Sbranch,
                                Ibranch=self.Ibranch, loading=self.loading,
                                losses=self.losses, error=self.error,
                                converged=self.converged, Qpv=self.Qpv, inner_it=self.inner_iterations,
                                outer_it=self.outer_iterations, elapsed=self.elapsed, methods=self.methods)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = zeros(n, dtype=complex)

        self.voltage = zeros(n, dtype=complex)

        self.overvoltage = zeros(n, dtype=complex)

        self.undervoltage = zeros(n, dtype=complex)

        self.Sbranch = zeros(m, dtype=complex)

        self.Ibranch = zeros(m, dtype=complex)

        self.loading = zeros(m, dtype=complex)

        self.losses = zeros(m, dtype=complex)

        self.overloads = zeros(m, dtype=complex)

        self.error = list()

        self.converged = list()

        self.buses_useful_for_storage = list()

        self.plot_bars_limit = 100

        self.inner_iterations = list()

        self.outer_iterations = list()

        self.elapsed = list()

        self.methods = list()

    def apply_from_island(self, results, b_idx, br_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        @param results: PowerFlowResults
        @param b_idx: bus original indices
        @param br_idx: branch original indices
        @return:
        """
        self.Sbus[b_idx] = results.Sbus

        self.voltage[b_idx] = results.voltage

        self.overvoltage[b_idx] = results.overvoltage

        self.undervoltage[b_idx] = results.undervoltage

        self.Sbranch[br_idx] = results.Sbranch

        self.Ibranch[br_idx] = results.Ibranch

        self.loading[br_idx] = results.loading

        self.losses[br_idx] = results.losses

        self.overloads[br_idx] = results.overloads

        # if results.error > self.error:
        self.error.append(results.error)

        self.converged.append(results.converged)

        self.inner_iterations.append(results.inner_iterations)

        self.outer_iterations.append(results.outer_iterations)

        self.elapsed.append(results.elapsed)

        self.methods.append(results.methods)

        # self.converged = self.converged and results.converged

        if results.buses_useful_for_storage is not None:
            self.buses_useful_for_storage = b_idx[results.buses_useful_for_storage]

    def check_limits(self, inputs: PowerFlowInput, wo=1, wv1=1, wv2=1):
        """
        Check the grid violations
        @param inputs: PowerFlowInput object
        @return: summation of the deviations
        """
        # branches: Returns the loading rate when greater than 1 (nominal), zero otherwise
        br_idx = where(self.loading > 1)[0]
        bb_f = inputs.F[br_idx]
        bb_t = inputs.T[br_idx]
        self.overloads = self.loading[br_idx]

        # Over and under voltage values in the indices where it occurs
        vo_idx = where(self.voltage > inputs.Vmax)[0]
        self.overvoltage = (self.voltage - inputs.Vmax)[vo_idx]
        vu_idx = where(self.voltage < inputs.Vmin)[0]
        self.undervoltage = (inputs.Vmin - self.voltage)[vu_idx]

        self.overloads_idx = br_idx

        self.overvoltage_idx = vo_idx

        self.undervoltage_idx = vu_idx

        self.buses_useful_for_storage = list(set(r_[vo_idx, vu_idx, bb_f, bb_t]))

        return abs(wo * sum(self.overloads) + wv1 * sum(self.overvoltage) + wv2 * sum(self.undervoltage))

    def get_convergence_report(self):

        res = 'converged' + str(self.converged)

        res += '\n\tinner_iterations: ' + str(self.inner_iterations)

        res += '\n\touter_iterations: ' + str(self.outer_iterations)

        res += '\n\terror: ' + str(self.error)

        res += '\n\telapsed: ' + str(self.elapsed)

        res += '\n\tmethods: ' + str(self.methods)

        return res

    def plot(self, result_type, ax=None, indices=None, names=None):
        """
        Plot the results
        Args:
            result_type:
            ax:
            indices:
            names:

        Returns:

        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            ylabel = ''
            title = ''
            if result_type == 'Bus voltage':
                y = self.voltage[indices]
                ylabel = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == 'Branch power':
                y = self.Sbranch[indices]
                ylabel = '(MVA)'
                title = 'Branch power '

            elif result_type == 'Branch current':
                y = self.Ibranch[indices]
                ylabel = '(p.u.)'
                title = 'Branch current '

            elif result_type == 'Branch_loading':
                y = self.loading[indices] * 100
                ylabel = '(%)'
                title = 'Branch loading '

            elif result_type == 'Branch losses':
                y = self.losses[indices]
                ylabel = '(MVA)'
                title = 'Branch losses '

            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            if len(df.columns) < self.plot_bars_limit:
                df.plot(ax=ax, kind='bar')
            else:
                df.plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(ylabel)
            ax.set_title(title)

            return df

        else:
            return None


class PowerFlow(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        self.results = None

        self.last_V = None

        self.__cancel__ = False

    @staticmethod
    def optimization(pv, circuit, Sbus, V, tol, maxiter, robust, verbose):
        """

        @param pv:
        @param circuit:
        @param Sbus:
        @param V:
        @param tol:
        @param maxiter:
        @param robust:
        @param verbose:
        @return:
        """
        from scipy.optimize import minimize

        def optimization_function(x, pv, circuit, Sbus, V, tol, maxiter, robust, verbose):
            # Set the voltage set points given by x
            V[pv] = ones(len(pv), dtype=complex) * x

            # run power flow: The voltage V is modified by reference
            V, converged, normF, Scalc = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                   Sbus=Sbus,
                                                   V0=V,
                                                   pv=circuit.power_flow_input.pv,
                                                   pq=circuit.power_flow_input.pq,
                                                   tol=tol,
                                                   max_it=maxiter,
                                                   robust=robust)

            # calculate the reactive power mismatches
            n = len(Scalc)
            excess = zeros(n)
            Qgen = circuit.power_flow_input.Sbus.imag - Scalc.imag
            exceed_up = where(Qgen > circuit.power_flow_input.Qmax)[0]
            exceed_down = where(Qgen < circuit.power_flow_input.Qmin)[0]
            # exceed = r_[exceed_down, exceed_up]
            excess[exceed_up] = circuit.power_flow_input.Qmax[exceed_up] - Qgen[exceed_up]
            excess[exceed_down] = circuit.power_flow_input.Qmax[exceed_down] - Qgen[exceed_down]

            fev = sum(excess)
            if verbose:
                print('f:', fev, 'x:', x)
                print('\tQmin:', circuit.power_flow_input.Qmin[pv])
                print('\tQgen:', Qgen[pv])
                print('\tQmax:', circuit.power_flow_input.Qmax[pv])
            return fev

        x0 = ones(len(pv))  # starting solution for the iteration
        bounds = ones((len(pv), 2))
        bounds[:, 0] *= 0.7
        bounds[:, 1] *= 1.2

        args = (pv, circuit, Sbus, V, tol, maxiter, robust, verbose)  # extra arguments of the function after x
        method = 'SLSQP'  # 'Nelder-Mead', TNC, SLSQP
        tol = 0.001
        options = dict()
        options['disp'] = verbose
        options['maxiter'] = 1000

        res = minimize(fun=optimization_function, x0=x0, args=args, method=method, tol=tol,
                       bounds=bounds, options=options)

        # fval = res.fun
        # xsol = res.x
        norm = circuit.power_flow_input.mismatch(V, Sbus)
        return res.fun, norm

    def single_power_flow(self, circuit: Circuit):
        """
        Run a power flow simulation for a single circuit
        @param circuit:
        @return:
        """
        # print('Single grid PF')
        optimize = False

        # Initial magnitudes
        if self.options.initialize_with_existing_solution and self.last_V is not None:
            V = self.last_V[circuit.bus_original_idx]
        else:
            V = circuit.power_flow_input.Vbus
        Sbus = circuit.power_flow_input.Sbus
        original_types = circuit.power_flow_input.types.copy()

        any_control_issue = True  # guilty assumption...

        control_max_iter = 10

        inner_it = list()
        outer_it = 0
        elapsed = list()
        methods = list()
        it = list()
        el = list()

        while any_control_issue and outer_it < control_max_iter:

            if len(circuit.power_flow_input.ref) == 0:
                V = zeros(len(Sbus), dtype=complex)
                normF = 0
                Scalc = Sbus.copy()
                any_control_issue = False
                converged = True
            else:
                # type HELM
                if self.options.solver_type == SolverType.HELM:
                    methods.append(SolverType.HELM)
                    V, converged, normF, Scalc, it, el = helm(Y=circuit.power_flow_input.Ybus,
                                                              Ys=circuit.power_flow_input.Yseries,
                                                              Ysh=circuit.power_flow_input.Yshunt,
                                                              max_coefficient_count=30,
                                                              S=circuit.power_flow_input.Sbus,
                                                              voltage_set_points=V,
                                                              pq=circuit.power_flow_input.pq,
                                                              pv=circuit.power_flow_input.pv,
                                                              vd=circuit.power_flow_input.ref,
                                                              eps=self.options.tolerance)
                # type DC
                elif self.options.solver_type == SolverType.DC:
                    methods.append(SolverType.DC)
                    V, converged, normF, Scalc, it, el = dcpf(Ybus=circuit.power_flow_input.Ybus,
                                                              Sbus=Sbus,
                                                              Ibus=circuit.power_flow_input.Ibus,
                                                              V0=V,
                                                              ref=circuit.power_flow_input.ref,
                                                              pvpq=circuit.power_flow_input.pqpv,
                                                              pq=circuit.power_flow_input.pq,
                                                              pv=circuit.power_flow_input.pv)

                elif self.options.solver_type == SolverType.LM:
                    methods.append(SolverType.LM)
                    V, converged, normF, Scalc, it, el = LevenbergMarquardtPF(Ybus=circuit.power_flow_input.Ybus,
                                                                              Sbus=Sbus,
                                                                              V0=V,
                                                                              Ibus=circuit.power_flow_input.Ibus,
                                                                              pv=circuit.power_flow_input.pv,
                                                                              pq=circuit.power_flow_input.pq,
                                                                              tol=self.options.tolerance,
                                                                              max_it=self.options.max_iter)

                elif self.options.solver_type == SolverType.FASTDECOUPLED:
                    methods.append(SolverType.FASTDECOUPLED)
                    V, converged, normF, Scalc, it, el = FDPF(Vbus=circuit.power_flow_input.Vbus,
                                                              Sbus=circuit.power_flow_input.Sbus,
                                                              Ibus=circuit.power_flow_input.Ibus,
                                                              Ybus=circuit.power_flow_input.Ybus,
                                                              B1=circuit.power_flow_input.B1,
                                                              B2=circuit.power_flow_input.B2,
                                                              pq=circuit.power_flow_input.pq,
                                                              pv=circuit.power_flow_input.pv,
                                                              pqpv=circuit.power_flow_input.pqpv,
                                                              tol=self.options.tolerance,
                                                              max_it=self.options.max_iter)

                elif self.options.solver_type == SolverType.NR:
                    methods.append(SolverType.NR)
                    V, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                   Sbus=Sbus,
                                                                   V0=V,
                                                                   Ibus=circuit.power_flow_input.Ibus,
                                                                   pv=circuit.power_flow_input.pv,
                                                                   pq=circuit.power_flow_input.pq,
                                                                   tol=self.options.tolerance,
                                                                   max_it=self.options.max_iter,
                                                                   robust=False)

                elif self.options.solver_type == SolverType.IWAMOTO:
                    methods.append(SolverType.IWAMOTO)
                    V, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                   Sbus=Sbus,
                                                                   V0=V,
                                                                   Ibus=circuit.power_flow_input.Ibus,
                                                                   pv=circuit.power_flow_input.pv,
                                                                   pq=circuit.power_flow_input.pq,
                                                                   tol=self.options.tolerance,
                                                                   max_it=self.options.max_iter,
                                                                   robust=True)

                # for any other method, for now, do a NR Iwamoto
                else:
                    methods.append(SolverType.IWAMOTO)
                    V, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                   Sbus=Sbus,
                                                                   V0=V,
                                                                   Ibus=circuit.power_flow_input.Ibus,
                                                                   pv=circuit.power_flow_input.pv,
                                                                   pq=circuit.power_flow_input.pq,
                                                                   tol=self.options.tolerance,
                                                                   max_it=self.options.max_iter,
                                                                   robust=self.options.robust)

                    if not converged:
                        # Try with HELM
                        methods.append(SolverType.HELM)
                        V, converged, normF, Scalc, it, el = helm(Y=circuit.power_flow_input.Ybus,
                                                                  Ys=circuit.power_flow_input.Yseries,
                                                                  Ysh=circuit.power_flow_input.Yshunt,
                                                                  max_coefficient_count=30,
                                                                  S=circuit.power_flow_input.Sbus,
                                                                  voltage_set_points=circuit.power_flow_input.Vbus,
                                                                  pq=circuit.power_flow_input.pq,
                                                                  pv=circuit.power_flow_input.pv,
                                                                  vd=circuit.power_flow_input.ref,
                                                                  eps=self.options.tolerance)
                        Vhelm = V.copy()

                        # Retry NR using the HELM solution as starting point
                        if not converged:
                            methods.append(SolverType.IWAMOTO)
                            V, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.power_flow_input.Ybus,
                                                                           Sbus=Sbus,
                                                                           V0=V,
                                                                           Ibus=circuit.power_flow_input.Ibus,
                                                                           pv=circuit.power_flow_input.pv,
                                                                           pq=circuit.power_flow_input.pq,
                                                                           tol=self.options.tolerance,
                                                                           max_it=self.options.max_iter,
                                                                           robust=self.options.robust)

                            # if it still did not converge, just use the helm voltage approximation
                            if not converged:
                                V = Vhelm

                # Check controls
                Vnew, Qnew, types_new, any_control_issue = self.switch_logic(V=V,
                                                                             Vset=abs(V),
                                                                             Q=Scalc.imag,
                                                                             Qmax=circuit.power_flow_input.Qmax,
                                                                             Qmin=circuit.power_flow_input.Qmin,
                                                                             types=circuit.power_flow_input.types,
                                                                             original_types=original_types,
                                                                             verbose=self.options.verbose)
                if any_control_issue:
                    V = Vnew
                    Sbus = Sbus.real + 1j * Qnew
                    circuit.power_flow_input.compile_types(types_new)
                else:
                    if self.options.verbose:
                        print('Controls Ok')

            # # increment the inner iterations counter
            inner_it.append(it)

            # increment the outer control iterations counter
            outer_it += 1

            # add the time taken by the solver in this iteration
            elapsed.append(el)

        # revert the types to the original
        circuit.power_flow_input.compile_types(original_types)

        # Compute the branches power
        Sbranch, Ibranch, loading, losses = self.compute_branch_results(circuit=circuit, V=V)

        # voltage, Sbranch, loading, losses, error, converged, Qpv
        results = PowerFlowResults(Sbus=Sbus,
                                   voltage=V,
                                   Sbranch=Sbranch,
                                   Ibranch=Ibranch,
                                   loading=loading,
                                   losses=losses,
                                   error=normF,
                                   converged=bool(converged),
                                   Qpv=None,
                                   inner_it=inner_it,
                                   outer_it=outer_it,
                                   elapsed=elapsed,
                                   methods=methods)

        # # check the limits
        # sum_dev = results.check_limits(circuit.power_flow_input)
        # print('dev sum: ', sum_dev)

        return results

    @staticmethod
    def compute_branch_results(circuit: Circuit, V):
        """
        Compute the power flows trough the branches
        @param circuit: instance of Circuit
        @param V: Voltage solution array for the circuit buses
        @return: Sbranch (MVA), Ibranch (p.u.), loading (p.u.), losses (MVA)
        """
        If = circuit.power_flow_input.Yf * V
        It = circuit.power_flow_input.Yt * V
        Sf = V[circuit.power_flow_input.F] * conj(If)
        St = V[circuit.power_flow_input.T] * conj(It)
        losses = (Sf + St) * circuit.Sbase  # Branch losses in MVA
        Ibranch = maximum(If, It)  # Branch current in p.u.
        Sbranch = maximum(Sf, St) * circuit.Sbase  # Branch power in MVA
        loading = Sbranch / circuit.power_flow_input.branch_rates  # Branch loading in p.u.

        # idx = where(abs(loading) == inf)[0]
        # loading[idx] = 9999

        return Sbranch, Ibranch, loading, losses

    @staticmethod
    def switch_logic(V, Vset, Q, Qmax, Qmin, types, original_types, verbose):
        """
        Change the buses type in order to control the generators reactive power
        @param pq: array of pq indices
        @param pv: array of pq indices
        @param ref: array of pq indices
        @param V: array of voltages (all buses)
        @param Vset: Array of set points (all buses)
        @param Q: Array of rective power (all buses)
        @param types: Array of types (all buses)
        @param original_types: Types as originally intended (all buses)
        @param verbose: output messages via the console
        @return:
            Vnew: New voltage values
            Qnew: New reactive power values
            types_new: Modified types array
            any_control_issue: Was there any control issue?
        """

        '''
        ON PV-PQ BUS TYPE SWITCHING LOGIC IN POWER FLOW COMPUTATION
        Jinquan Zhao

        1) Bus i is a PQ bus in the previous iteration and its
        reactive power was fixed at its lower limit:

        If its voltage magnitude Vi ≥ Viset, then

            it is still a PQ bus at current iteration and set Qi = Qimin .

            If Vi < Viset , then

                compare Qi with the upper and lower limits.

                If Qi ≥ Qimax , then
                    it is still a PQ bus but set Qi = Qimax .
                If Qi ≤ Qimin , then
                    it is still a PQ bus and set Qi = Qimin .
                If Qimin < Qi < Qi max , then
                    it is switched to PV bus, set Vinew = Viset.

        2) Bus i is a PQ bus in the previous iteration and
        its reactive power was fixed at its upper limit:

        If its voltage magnitude Vi ≤ Viset , then:
            bus i still a PQ bus and set Q i = Q i max.

            If Vi > Viset , then

                Compare between Qi and its upper/lower limits

                If Qi ≥ Qimax , then
                    it is still a PQ bus and set Q i = Qimax .
                If Qi ≤ Qimin , then
                    it is still a PQ bus but let Qi = Qimin in current iteration.
                If Qimin < Qi < Qimax , then
                    it is switched to PV bus and set Vinew = Viset

        3) Bus i is a PV bus in the previous iteration.

        Compare Q i with its upper and lower limits.

        If Qi ≥ Qimax , then
            it is switched to PQ and set Qi = Qimax .
        If Qi ≤ Qimin , then
            it is switched to PQ and set Qi = Qimin .
        If Qi min < Qi < Qimax , then
            it is still a PV bus.
        '''
        if verbose:
            print('Control logic')

        n = len(V)
        Vm = abs(V)
        Qnew = Q.copy()
        Vnew = V.copy()
        types_new = types.copy()
        any_control_issue = False
        for i in range(n):

            if types[i] == NodeType.REF.value[0]:
                pass

            elif types[i] == NodeType.PQ.value[0] and original_types[i] == NodeType.PV.value[0]:

                if Vm[i] != Vset[i]:

                    if Q[i] >= Qmax[i]:  # it is still a PQ bus but set Qi = Qimax .
                        Qnew[i] = Qmax[i]

                    elif Q[i] <= Qmin[i]:  # it is still a PQ bus and set Qi = Qimin .
                        Qnew[i] = Qmin[i]

                    else:  # switch back to PV, set Vinew = Viset.
                        if verbose:
                            print('Bus', i, ' switched back to PV')
                        types_new[i] = NodeType.PV.value[0]
                        Vnew[i] = complex(Vset[i], 0)

                    any_control_issue = True

                else:
                    pass  # The voltages are equal

            elif types[i] == NodeType.PV.value[0]:

                if Q[i] >= Qmax[i]:  # it is switched to PQ and set Qi = Qimax .
                    if verbose:
                        print('Bus', i, ' switched to PQ: Q', Q[i], ' Qmax:', Qmax[i])
                    types_new[i] = NodeType.PQ.value[0]
                    Qnew[i] = Qmax[i]
                    any_control_issue = True

                elif Q[i] <= Qmin[i]:  # it is switched to PQ and set Qi = Qimin .
                    if verbose:
                        print('Bus', i, ' switched to PQ: Q', Q[i], ' Qmin:', Qmin[i])
                    types_new[i] = NodeType.PQ.value[0]
                    Qnew[i] = Qmin[i]
                    any_control_issue = True

                else:  # it is still a PV bus.
                    pass

            else:
                pass

        return Vnew, Qnew, types_new, any_control_issue

    def run(self):
        """
        Run a power flow for every circuit
        @return:
        """
        print('PowerFlow at ', self.grid.name)
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        results = PowerFlowResults()
        results.initialize(n, m)
        # self.progress_signal.emit(0.0)
        k = 0
        for circuit in self.grid.circuits:
            if self.options.verbose:
                print('Solving ' + circuit.name)

            circuit.power_flow_results = self.single_power_flow(circuit)
            results.apply_from_island(circuit.power_flow_results, circuit.bus_original_idx, circuit.branch_original_idx)

            # self.progress_signal.emit((k+1) / len(self.grid.circuits))
            k += 1
        # remember the solution for later
        self.last_V = results.voltage

        # check the limits
        sum_dev = results.check_limits(self.grid.power_flow_input)

        self.results = results
        self.grid.power_flow_results = results

        # self.progress_signal.emit(0.0)
        # self.done_signal.emit()

    def run_at(self, t, mc=False):
        """
        Run power flow at the time series object index t
        @param t:
        @return:
        """
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        if self.grid.power_flow_results is None:
            self.grid.power_flow_results = PowerFlowResults()
        self.grid.power_flow_results.initialize(n, m)
        i = 1
        # self.progress_signal.emit(0.0)
        for circuit in self.grid.circuits:
            if self.options.verbose:
                print('Solving ' + circuit.name)

            # Set the profile values
            circuit.set_at(t, mc)
            # run
            circuit.power_flow_results = self.single_power_flow(circuit)
            self.grid.power_flow_results.apply_from_island(circuit.power_flow_results,
                                                           circuit.bus_original_idx,
                                                           circuit.branch_original_idx)

            # prog = (i / len(self.grid.circuits)) * 100
            # self.progress_signal.emit(prog)
            i += 1

        # check the limits
        sum_dev = self.grid.power_flow_results.check_limits(self.grid.power_flow_input)

        # self.progress_signal.emit(0.0)
        # self.done_signal.emit()

        return self.grid.power_flow_results

    def cancel(self):
        self.__cancel__ = True


