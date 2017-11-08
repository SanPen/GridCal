from numpy import ones, zeros, conj, where, \
    maximum

from GridCal.grid.calculate.power_flow.options import PowerFlowOptions
from GridCal.grid.calculate.power_flow.results import PowerFlowResults
from GridCal.grid.calculate.power_flow.solve.DCPF import dcpf
from GridCal.grid.calculate.power_flow.solve.FastDecoupled import FDPF
from GridCal.grid.calculate.power_flow.solve.Helm import helm
from GridCal.grid.calculate.power_flow.solve.JacobianBased import IwamotoNR, \
    LevenbergMarquardtPF
from GridCal.grid.calculate.solver_type import SolverType
from GridCal.grid.model.circuit.circuit import Circuit
from GridCal.grid.model.circuit.multi_circuit import MultiCircuit
from GridCal.grid.model.node_type import NodeType


class PowerFlowRunnable(QRunnable):
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


