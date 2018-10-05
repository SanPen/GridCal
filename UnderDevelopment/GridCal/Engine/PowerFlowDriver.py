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

from enum import Enum
from warnings import warn
from numpy import complex, zeros, conj, ndarray, delete, where, r_, maximum, array
import pandas as pd
from pySOT import *
# from timeit import default_timer as timer
from PyQt5.QtCore import QThread, QRunnable, pyqtSignal

from GridCal.Engine.IoStructures import PowerFlowResults, CalculationInputs
from GridCal.Engine.CalculationEngine import MultiCircuit
from GridCal.Engine.BasicStructures import BusMode
from GridCal.Engine.Numerical.LinearizedPF import dcpf, lacpf
from GridCal.Engine.Numerical.HELM import helm
from GridCal.Engine.Numerical.JacobianBased import IwamotoNR, LevenbergMarquardtPF, NR_LS, NR_I_LS
from GridCal.Engine.Numerical.FastDecoupled import FDPF


class SolverType(Enum):
    NR = 1
    NRFD_XB = 2
    NRFD_BX = 3
    GAUSS = 4
    DC = 5,
    HELM = 6,
    ZBUS = 7,
    IWAMOTO = 8,
    CONTINUATION_NR = 9,
    HELMZ = 10,
    LM = 11  # Levenberg-Marquardt
    FASTDECOUPLED = 12,
    LACPF = 13,
    DC_OPF = 14,
    AC_OPF = 15,
    NRI = 16,
    DYCORS_OPF = 17,
    GA_OPF = 18


########################################################################################################################
# Power flow classes
########################################################################################################################


class PowerFlowOptions:

    def __init__(self, solver_type: SolverType = SolverType.NR, aux_solver_type: SolverType = SolverType.HELM,
                 verbose=False, robust=False, initialize_with_existing_solution=True,
                 tolerance=1e-6, max_iter=25, control_q=True, multi_core=True, dispatch_storage=False):
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

        self.verbose = verbose

        self.robust = robust

        self.initialize_with_existing_solution = initialize_with_existing_solution

        self.multi_thread = multi_core

        self.dispatch_storage = dispatch_storage


class PowerFlowMP:
    """
    Power flow without QT to use with multi processing
    """
    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        """

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        self.results = None

        self.last_V = None

        self.logger = list()

        self.convergence_reports = list()

        self.__cancel__ = False

    @staticmethod
    def compile_types(Sbus, types=None, logger=list()):
        """
        Compile the types
        @return:
        """

        pq = where(types == BusMode.PQ.value[0])[0]
        pv = where(types == BusMode.PV.value[0])[0]
        ref = where(types == BusMode.REF.value[0])[0]
        sto = where(types == BusMode.STO_DISPATCH.value)[0]

        if len(ref) == 0:  # there is no slack!

            if len(pv) == 0:  # there are no pv neither -> blackout grid

                warn('There are no slack nodes selected')
                logger.append('There are no slack nodes selected')

            else:  # select the first PV generator as the slack

                mx = max(Sbus[pv])
                if mx > 0:
                    # find the generator that is injecting the most
                    i = where(Sbus == mx)[0][0]

                else:
                    # all the generators are injecting zero, pick the first pv
                    i = pv[0]

                # delete the selected pv bus from the pv list and put it in the slack list
                pv = delete(pv, where(pv == i)[0])
                ref = [i]
                # print('Setting bus', i, 'as slack')

            ref = ndarray.flatten(array(ref))
            types[ref] = BusMode.REF.value[0]
        else:
            pass  # no problem :)

        pqpv = r_[pq, pv]
        pqpv.sort()

        return ref, pq, pv, pqpv

    def single_power_flow(self, circuit: CalculationInputs, solver_type: SolverType, voltage_solution, Sbus, Ibus, island_index=0):
        """
        Run a power flow simulation for a single circuit
        @param circuit:
        @param solver_type
        @param voltage_solution
        @return:
        """

        original_types = circuit.types.copy()
        ref, pq, pv, pqpv = self.compile_types(Sbus, original_types)

        any_control_issue = True  # guilty assumption...
        regulators_stable = False # Transformers' voltage regulators are stable

        control_max_iter = 10

        inner_it = list()
        outer_it = 0
        elapsed = list()
        methods = list()
        converged_lst = list()
        errors = list()
        it = list()
        el = list()

        while (any_control_issue or not regulators_stable) and outer_it < control_max_iter:

            if len(circuit.ref) == 0:
                voltage_solution = zeros(len(Sbus), dtype=complex)
                normF = 0
                Scalc = Sbus.copy()
                any_control_issue = False
                converged = True
                warn('Not solving power flow because there is no slack bus')
                self.logger.append('Not solving power flow because there is no slack bus')
            else:
                # type HELM
                if solver_type == SolverType.HELM:
                    methods.append(SolverType.HELM)
                    voltage_solution, converged, normF, Scalc, it, el = helm(Vbus=voltage_solution,
                                                                             Sbus=Sbus,
                                                                             Ybus=circuit.Ybus,
                                                                             pq=pq,
                                                                             pv=pv,
                                                                             ref=ref,
                                                                             pqpv=pqpv,
                                                                             tol=self.options.tolerance,
                                                                             max_coefficient_count=self.options.max_iter)

                # type DC
                elif solver_type == SolverType.DC:
                    methods.append(SolverType.DC)
                    voltage_solution, converged, normF, Scalc, it, el = dcpf(Ybus=circuit.Ybus,
                                                                             Sbus=Sbus,
                                                                             Ibus=Ibus,
                                                                             V0=voltage_solution,
                                                                             ref=ref,
                                                                             pvpq=pqpv,
                                                                             pq=pq,
                                                                             pv=pv)

                # LAC PF
                elif solver_type == SolverType.LACPF:
                    methods.append(SolverType.LACPF)

                    voltage_solution, converged, normF, Scalc, it, el = lacpf(Y=circuit.Ybus,
                                                                              Ys=circuit.Yseries,
                                                                              S=Sbus,
                                                                              I=Ibus,
                                                                              Vset=voltage_solution,
                                                                              pq=pq,
                                                                              pv=pv)

                # Levenberg-Marquardt
                elif solver_type == SolverType.LM:
                    methods.append(SolverType.LM)
                    voltage_solution, converged, normF, Scalc, it, el = LevenbergMarquardtPF(
                        Ybus=circuit.Ybus,
                        Sbus=Sbus,
                        V0=voltage_solution,
                        Ibus=Ibus,
                        pv=pv,
                        pq=pq,
                        tol=self.options.tolerance,
                        max_it=self.options.max_iter)

                # Fast decoupled
                elif solver_type == SolverType.FASTDECOUPLED:
                    methods.append(SolverType.FASTDECOUPLED)
                    voltage_solution, converged, normF, Scalc, it, el = FDPF(Vbus=voltage_solution,
                                                                             Sbus=Sbus,
                                                                             Ibus=Ibus,
                                                                             Ybus=circuit.Ybus,
                                                                             B1=circuit.B1,
                                                                             B2=circuit.B2,
                                                                             pq=pq,
                                                                             pv=pv,
                                                                             pqpv=pqpv,
                                                                             tol=self.options.tolerance,
                                                                             max_it=self.options.max_iter)

                # Newton-Raphson
                elif solver_type == SolverType.NR:
                    methods.append(SolverType.NR)

                    # Solve NR with the linear AC solution
                    voltage_solution, converged, normF, Scalc, it, el = NR_LS(Ybus=circuit.Ybus,
                                                                              Sbus=Sbus,
                                                                              V0=voltage_solution,
                                                                              Ibus=Ibus,
                                                                              pv=pv,
                                                                              pq=pq,
                                                                              tol=self.options.tolerance,
                                                                              max_it=self.options.max_iter)

                # Newton-Raphson-Iwamoto
                elif solver_type == SolverType.IWAMOTO:
                    methods.append(SolverType.IWAMOTO)
                    voltage_solution, converged, normF, Scalc, it, el = IwamotoNR(Ybus=circuit.Ybus,
                                                                                  Sbus=Sbus,
                                                                                  V0=voltage_solution,
                                                                                  Ibus=Ibus,
                                                                                  pv=pv,
                                                                                  pq=pq,
                                                                                  tol=self.options.tolerance,
                                                                                  max_it=self.options.max_iter,
                                                                                  robust=True)

                # Newton-Raphson in current equations
                elif solver_type == SolverType.NRI:
                    methods.append(SolverType.NRI)
                    # NR_I_LS(Ybus, Sbus_sp, V0, Ibus_sp, pv, pq, tol, max_it
                    voltage_solution, converged, normF, Scalc, it, el = NR_I_LS(Ybus=circuit.Ybus,
                                                                                Sbus_sp=Sbus,
                                                                                V0=voltage_solution,
                                                                                Ibus_sp=Ibus,
                                                                                pv=pv,
                                                                                pq=pq,
                                                                                tol=self.options.tolerance,
                                                                                max_it=self.options.max_iter)

                # for any other method, for now, do a LM
                else:
                    methods.append(SolverType.LM)
                    voltage_solution, converged, \
                    normF, Scalc, it, el = LevenbergMarquardtPF(Ybus=circuit.Ybus,
                                                                Sbus=Sbus,
                                                                V0=voltage_solution,
                                                                Ibus=Ibus,
                                                                pv=pv,
                                                                pq=pq,
                                                                tol=self.options.tolerance,
                                                                max_it=self.options.max_iter)

                if converged:
                    # Check controls
                    if self.options.control_Q:
                        voltage_solution, \
                        Qnew, \
                        types_new, \
                        any_control_issue = self.switch_logic(V=voltage_solution,
                                                              Vset=abs(voltage_solution),
                                                              Q=Scalc.imag,
                                                              Qmax=circuit.Qmax,
                                                              Qmin=circuit.Qmin,
                                                              types=circuit.types,
                                                              original_types=original_types,
                                                              verbose=self.options.verbose)
                        if any_control_issue:
                            # voltage_solution = Vnew
                            Sbus = Sbus.real + 1j * Qnew
                            ref, pq, pv, pqpv = self.compile_types(Sbus, types_new)
                        else:
                            if self.options.verbose:
                                print('Controls Ok')

                    else:
                        # did not check Q limits
                        any_control_issue = False

                    print("Checking voltage regulators...")
                    branches, regulators_stable = self.adjust_tap_changers(voltage=voltage_solution,
                                                                           buses=self.grid.buses,
                                                                           branches=self.grid.branches)
                    if not regulators_stable:
                        print("Updating the circuit...")
                        for j, new_branch in enumerate(branches):
                            for i, old_branch in enumerate(self.grid.branches):
                                if old_branch.name == new_branch.name:
                                    self.grid.branches[i].tap_module = new_branch.tap_module
                                    numerical_circuit = self.grid.compile()
                                    circuit = numerical_circuit.compute()[island_index]
                                    break
                else:
                    any_control_issue = False

            # increment the inner iterations counter
            inner_it.append(it)

            # increment the outer control iterations counter
            outer_it += 1

            # add the time taken by the solver in this iteration
            elapsed.append(el)

            # append loop error
            errors.append(normF)

            # append converged
            converged_lst.append(bool(converged))

        # revert the types to the original
        # ref, pq, pv, pqpv = self.compile_types(original_types)

        # Compute the branches power and the slack buses power
        Sbranch, Ibranch, loading, losses, \
        flow_direction, Sbus = self.power_flow_post_process(calculation_inputs=circuit, V=voltage_solution)

        # voltage, Sbranch, loading, losses, error, converged, Qpv
        results = PowerFlowResults(Sbus=Sbus,
                                   voltage=voltage_solution,
                                   Sbranch=Sbranch,
                                   Ibranch=Ibranch,
                                   loading=loading,
                                   losses=losses,
                                   flow_direction=flow_direction,
                                   error=errors,
                                   converged=converged_lst,
                                   Qpv=None,
                                   inner_it=inner_it,
                                   outer_it=outer_it,
                                   elapsed=elapsed,
                                   methods=methods)

        return results

    @staticmethod
    def power_flow_post_process(calculation_inputs: CalculationInputs, V, only_power=False):
        """
        Compute the power flows trough the branches
        @param calculation_inputs: instance of Circuit
        @param V: Voltage solution array for the circuit buses
        @param only_power: compute only the power injection
        @return: Sbranch (MVA), Ibranch (p.u.), loading (p.u.), losses (MVA), Sbus(MVA)
        """
        # Compute the slack and pv buses power
        Sbus = calculation_inputs.Sbus

        vd = calculation_inputs.ref
        pv = calculation_inputs.pv

        # power at the slack nodes
        Sbus[vd] = V[vd] * conj(calculation_inputs.Ybus[vd, :][:, :].dot(V))

        # Reactive power at the pv nodes
        P = Sbus[pv].real
        Q = (V[pv] * conj(calculation_inputs.Ybus[pv, :][:, :].dot(V))).imag
        Sbus[pv] = P + 1j * Q  # keep the original P injection and set the calculated reactive power

        if not only_power:
            # Branches current, loading, etc
            If = calculation_inputs.Yf * V
            It = calculation_inputs.Yt * V
            Sf = (calculation_inputs.C_branch_bus_f * V) * conj(If)
            St = (calculation_inputs.C_branch_bus_t * V) * conj(It)

            # Branch losses in MVA
            losses = (Sf + St) * calculation_inputs.Sbase

            flow_direction = Sf / np.abs(Sf + 1e-20)

            # Branch current in p.u.
            Ibranch = maximum(If, It)

            # Branch power in MVA
            Sbranch = maximum(Sf, St) * calculation_inputs.Sbase

            # Branch loading in p.u.
            loading = Sbranch / (calculation_inputs.branch_rates + 1e-9)

            return Sbranch, Ibranch, loading, losses, flow_direction, Sbus

        else:
            no_val = np.zeros(calculation_inputs.nbr, dtype=complex)
            flow_direction = np.ones(calculation_inputs.nbr, dtype=complex)
            return no_val, no_val, no_val, no_val, flow_direction, Sbus

    @staticmethod
    def switch_logic(V, Vset, Q, Qmax, Qmin, types, original_types, verbose):
        """
        Change the buses type in order to control the generators reactive power
        @param pq: array of pq indices
        @param pv: array of pq indices
        @param ref: array of pq indices
        @param V: array of voltages (all buses)
        @param Vset: Array of set points (all buses)
        @param Q: Array of reactive power (all buses)
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

            if types[i] == BusMode.REF.value[0]:
                pass

            elif types[i] == BusMode.PQ.value[0] and original_types[i] == BusMode.PV.value[0]:

                if Vm[i] != Vset[i]:

                    if round(Q[i], 4) >= round(Qmax[i], 4):  # it is still a PQ bus but set Qi = Qimax .
                        Qnew[i] = Qmax[i]

                    elif round(Q[i], 4) <= round(Qmin[i], 4):  # it is still a PQ bus and set Qi = Qimin .
                        Qnew[i] = Qmin[i]

                    else:  # switch back to PV, set Vinew = Viset.
                        if verbose:
                            print('Bus', i, ' switched back to PV')
                        types_new[i] = BusMode.PV.value[0]
                        Vnew[i] = complex(Vset[i], 0)

                    any_control_issue = True

                else:
                    pass  # The voltages are equal

            elif types[i] == BusMode.PV.value[0]:

                if round(Q[i], 4) >= round(Qmax[i], 4):  # it is switched to PQ and set Qi = Qimax .
                    if verbose:
                        print(f"Bus {i} switched to PQ: Q {round(Q[i], 4)}  Qmax: {round(Qmax[i], 4)}")
                    types_new[i] = BusMode.PQ.value[0]
                    Qnew[i] = Qmax[i]
                    any_control_issue = True

                elif round(Q[i], 4) <= round(Qmin[i], 4):  # it is switched to PQ and set Qi = Qimin .
                    if verbose:
                        print(f"Bus {i} switched to PQ: Q {round(Q[i], 4)}  Qmin: {round(Qmin[i], 4)}")
                    types_new[i] = BusMode.PQ.value[0]
                    Qnew[i] = Qmin[i]
                    any_control_issue = True

                else:  # it is still a PV bus.
                    pass

            else:
                pass

        return Vnew, Qnew, types_new, any_control_issue

    def adjust_tap_changers(self, voltage, buses, branches):
        """
        Adjust he transformer taps in the grid
        :param voltage: voltage vector solution
        :param buses: list of bus objects
        :param branches: list of branch objects
        :return: stable?
        """
        stable = True
        for i, branch in enumerate(branches):

            if branch.bus_to_regulated:
                print(f"{branch} has a voltage regulator, checking if it has to act...")

                for j, bus in enumerate(buses):

                    if bus.name == branch.bus_to.name:
                        v = abs(voltage[j])
                        print(f"Bus {bus}: U={v}pu, U_set={branch.vset}")

                        if branch.tap_changer.tap > 0:
                            if branch.vset > v + branch.tap_changer.inc_reg_up/2:
                                if branch.tap_changer.tap == branch.tap_changer.min_tap:
                                    print(f"{branch}: Already at lowest tap ({branch.tap_changer.tap}), skipping")
                                    break
                                branches[i].tap_down()
                                print(f"{branch}: Lowering from tap {branch.tap_changer.tap}")
                                stable = False

                        elif branch.vset < v - branch.tap_changer.inc_reg_up/2:

                            if branch.tap_changer.tap == branch.tap_changer.max_tap:
                                print(f"{branch}: Already at highest tap ({branch.tap_changer.tap}), skipping")
                                break
                            branches[i].tap_up()
                            print(f"{branch}: Raising from tap {branch.tap_changer.tap}")
                            stable = False

                        elif branch.tap_changer.tap < 0:
                            if branch.vset > v + branch.tap_changer.inc_reg_down/2:
                                if branch.tap_changer.tap == branch.tap_changer.min_tap:
                                    print(f"{branch}: Already at lowest tap ({branch.tap_changer.tap}), skipping")
                                    break
                                branches[i].tap_down()
                                print(f"{branch}: Lowering from tap {branch.tap_changer.tap}")
                                stable = False

                        elif branch.vset < v - branch.tap_changer.inc_reg_down/2:
                            if branch.tap_changer.tap == branch.tap_changer.max_tap:
                                print(f"{branch}: Already at highest tap ({branch.tap_changer.tap}), skipping")
                                break
                            branches[i].tap_up()
                            print(f"{branch}: Raising from tap {branch.tap_changer.tap}")
                            stable = False

                        else:
                            if branch.vset > v + branch.tap_changer.inc_reg_up/2:
                                if branch.tap_changer.tap == branch.tap_changer.min_tap:
                                    print(f"{branch}: Already at lowest tap ({branch.tap_changer.tap}), skipping")
                                    break
                                branches[i].tap_down()
                                print(f"{branch}: Lowering from tap {branch.tap_changer.tap}")
                                stable = False

                            elif branch.vset < v - branch.tap_changer.inc_reg_down / 2:
                                if branch.tap_changer.tap == branch.tap_changer.max_tap:
                                    print(f"{branch}: Already at highest tap ({branch.tap_changer.tap}), skipping")
                                    break
                                branches[i].tap_up()
                                print(f"{branch}: Raising from tap {branch.tap_changer.tap}")
                                stable = False
                        break
        return branches, stable

    def run(self, store_in_island=False):
        """
        Pack run_pf for the QThread
        :return:
        """
        # print('PowerFlow at ', self.grid.name)
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        results = PowerFlowResults()
        results.initialize(n, m)
        # self.progress_signal.emit(0.0)
        Sbase = self.grid.Sbase

        # columns of the report
        col = ['Method', 'Converged?', 'Error', 'Elapsed (s)', 'Iterations']
        self.convergence_reports.clear()

        print('Compiling...', end='')
        numerical_circuit = self.grid.compile()
        calculation_inputs = numerical_circuit.compute()

        if len(numerical_circuit.islands) > 1:

            # simulate each island and merge the results
            for i, calculation_input in enumerate(calculation_inputs):

                if len(calculation_input.ref) > 0:
                    Vbus = calculation_input.Vbus
                    Sbus = calculation_input.Sbus
                    Ibus = calculation_input.Ibus

                    # run circuit power flow
                    res = self.run_pf(calculation_input, Vbus, Sbus, Ibus, island_index=i)

                    bus_original_idx = numerical_circuit.islands[i]
                    branch_original_idx = numerical_circuit.island_branches[i]

                    # merge the results from this island
                    results.apply_from_island(res, bus_original_idx, branch_original_idx)

                    # build the report
                    data = np.c_[results.methods[i],
                                 results.converged[i],
                                 results.error[i],
                                 results.elapsed[i],
                                 results.inner_iterations[i]]
                    df = pd.DataFrame(data, columns=col)
                    self.convergence_reports.append(df)
                else:
                    warn('There are no slack nodes in the island ' + str(i))
                    self.logger.append('There are no slack nodes in the island ' + str(i))
        else:
            # only one island
            Vbus = calculation_inputs[0].Vbus
            Sbus = calculation_inputs[0].Sbus
            Ibus = calculation_inputs[0].Ibus

            # run circuit power flow
            results = self.run_pf(calculation_inputs[0], Vbus, Sbus, Ibus, 0)

            # build the report
            data = np.c_[results.methods[0],
                         results.converged[0],
                         results.error[0],
                         results.elapsed[0],
                         results.inner_iterations[0]]
            df = pd.DataFrame(data, columns=col)
            self.convergence_reports.append(df)

        self.last_V = results.voltage  # done inside single_power_flow

        # check the limits
        sum_dev = results.check_limits(F=numerical_circuit.F, T=numerical_circuit.T,
                                       Vmax=numerical_circuit.Vmax, Vmin=numerical_circuit.Vmin,
                                       wo=1, wv1=1, wv2=1)

        self.results = results

        return self.results

    def run_pf(self, calculation_inputs: CalculationInputs, Vbus, Sbus, Ibus, island_index=0):
        """
        Run a power flow for a circuit
        @return:
        """

        # Run the power flow
        # results = self.single_power_flow(circuit=circuit,
        #                                  solver_type=self.options.solver_type,
        #                                  voltage_solution=Vbus,
        #                                  Sbus=Sbus,
        #                                  Ibus=Ibus)

        # Retry with another solver

        if self.options.auxiliary_solver_type is not None:
            solvers = [self.options.solver_type,
                       SolverType.IWAMOTO,
                       SolverType.FASTDECOUPLED,
                       SolverType.LM,
                       SolverType.LACPF]
        else:
            # No retry selected
            solvers = [self.options.solver_type]

        # set worked to false to enter in the loop
        worked = False

        if not worked:

            k = 0
            methods = list()
            inner_it = list()
            elapsed = list()
            errors = list()
            converged_lst = list()
            outer_it = 0
            while k < len(solvers) and not worked:

                # get the solver
                solver = solvers[k]

                print('Trying', solver)

                # set the initial voltage
                V0 = Vbus.copy()

                # run power flow
                results = self.single_power_flow(circuit=calculation_inputs,
                                                 solver_type=solver,
                                                 voltage_solution=V0,
                                                 Sbus=Sbus,
                                                 Ibus=Ibus,
                                                 island_index=island_index)

                # did it worked?
                worked = np.all(results.converged)

                # record the solver steps
                methods += results.methods
                inner_it += results.inner_iterations
                outer_it += results.outer_iterations
                elapsed += results.elapsed
                errors += results.error
                converged_lst += results.converged

                k += 1

            if not worked:
                print('Did not converge, even after retry!, Error:', results.error)
        else:
            # the original solver worked
            pass

        # set the total process variables:
        results.methods = methods
        results.inner_iterations = inner_it
        results.outer_iterations = outer_it
        results.elapsed = elapsed
        results.error = errors
        results.converged = converged_lst

        # check the power flow limits
        results.check_limits(F=calculation_inputs.F, T=calculation_inputs.T,
                             Vmax=calculation_inputs.Vmax, Vmin=calculation_inputs.Vmin,
                             wo=1, wv1=1, wv2=1)

        return results

    def cancel(self):
        self.__cancel__ = True


def power_flow_worker(t, options: PowerFlowOptions, circuit: CalculationInputs, Vbus, Sbus, Ibus, return_dict):
    """
    Power flow worker to schedule parallel power flows
    :param t: execution index
    :param options: power flow options
    :param circuit: circuit
    :param Vbus: Voltages to initialize
    :param Sbus: Power injections
    :param Ibus: Current injections
    :param return_dict: parallel module dictionary in wich to return the values
    :return:
    """

    instance = PowerFlowMP(None, options)
    return_dict[t] = instance.run_pf(circuit, Vbus, Sbus, Ibus)


def power_flow_worker_args(args):
    """
    Power flow worker to schedule parallel power flows

    args -> t, options: PowerFlowOptions, circuit: Circuit, Vbus, Sbus, Ibus, return_dict


    :param t: execution index
    :param options: power flow options
    :param circuit: circuit
    :param Vbus: Voltages to initialize
    :param Sbus: Power injections
    :param Ibus: Current injections
    :param return_dict: parallel module dictionary in wich to return the values
    :return:
    """
    t, options, circuit, Vbus, Sbus, Ibus, return_dict = args
    instance = PowerFlowMP(None, options)
    return_dict[t] = instance.run_pf(circuit, Vbus, Sbus, Ibus)


class PowerFlow(QRunnable):
    """
    Power flow wrapper to use with Qt
    """

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

        self.pf = PowerFlowMP(grid, options)

        self.__cancel__ = False

    def run(self):
        """
        Pack run_pf for the QThread
        :return:
        """

        results = self.pf.run(store_in_island=True)
        self.results = results

    def run_pf(self, circuit: CalculationInputs, Vbus, Sbus, Ibus):
        """
        Run a power flow for every circuit
        @return:
        """

        return self.pf.run_pf(circuit, Vbus, Sbus, Ibus)

    def cancel(self):
        self.__cancel__ = True

