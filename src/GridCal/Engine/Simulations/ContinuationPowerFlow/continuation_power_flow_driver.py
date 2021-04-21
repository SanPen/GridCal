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

import pandas as pd
import numpy as np
import json
from matplotlib import pyplot as plt

from PySide2.QtCore import QThread, Signal

from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.ContinuationPowerFlow.continuation_power_flow import continuation_nr, CpfStopAt, CpfParametrization, CpfNumericResults
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit
from GridCal.Engine.plot_config import LINEWIDTH
from GridCal.Engine.Simulations.results_model import ResultsModel


########################################################################################################################
# Voltage collapse classes
########################################################################################################################


class ContinuationPowerFlowOptions:

    def __init__(self, step=0.01, approximation_order=CpfParametrization.Natural,
                 adapt_step=True, step_min=0.0001,
                 step_max=0.2, error_tol=1e-3, tol=1e-6, max_it=20,
                 stop_at=CpfStopAt.Nose, verbose=False):
        """
        Voltage collapse options
        @param step: Step length
        @param approximation_order: Order of the approximation: 1, 2, 3, etc...
        @param adapt_step: Use adaptive step length?
        @param step_min: Minimum step length
        @param step_max: Maximum step length
        @param error_tol: Error tolerance
        @param tol: tolerance
        @param max_it: Maximum number of iterations
        @param stop_at: Value of lambda to stop at, it can be specified by a concept namely NOSE to sto at the edge or
        FULL tp draw the full curve
        """

        self.step = step

        self.approximation_order = approximation_order

        self.adapt_step = adapt_step

        self.step_min = step_min

        self.step_max = step_max

        self.error_tol = error_tol

        self.tol = tol

        self.max_it = max_it

        self.stop_at = stop_at

        self.verbose = verbose


class ContinuationPowerFlowInput:

    def __init__(self, Sbase, Vbase, Starget, base_overload_number=0):
        """
        ContinuationPowerFlowInput constructor
        @param Sbase: Initial power array
        @param Vbase: Initial voltage array
        @param Starget: Final power array
        @:param base_overload_number: number of overloads in the base situation
        """
        self.Sbase = Sbase

        self.Starget = Starget

        self.Vbase = Vbase

        self.base_overload_number = base_overload_number


class ContinuationPowerFlowResults(ResultsTemplate):

    def __init__(self, nval, nbus, nbr, bus_names, branch_names, bus_types):
        """
        ContinuationPowerFlowResults instance
        :param nbus: number of buses
        :param nbr: number of branches
        :param bus_names: names of the buses
        """
        ResultsTemplate.__init__(self,
                                 name='Continuation Power Flow',
                                 available_results=[ResultTypes.BusVoltage,
                                                    ResultTypes.BusActivePower,
                                                    ResultTypes.BusReactivePower,
                                                    ResultTypes.BranchActivePowerFrom,
                                                    ResultTypes.BranchReactivePowerFrom,
                                                    ResultTypes.BranchActivePowerTo,
                                                    ResultTypes.BranchReactivePowerTo,
                                                    ResultTypes.BranchActiveLosses,
                                                    ResultTypes.BranchReactiveLosses,
                                                    ResultTypes.BranchLoading],
                                 data_variables=['bus_names',
                                                 'branch_names',
                                                 'voltages',
                                                 'lambdas',
                                                 'error',
                                                 'converged',
                                                 'Sf',
                                                 'St',
                                                 'loading',
                                                 'losses',
                                                 'Sbus',
                                                 'bus_types']
                                 )

        self.bus_names = bus_names

        self.branch_names = branch_names

        self.voltages = np.zeros((nval, nbus), dtype=complex)

        self.lambdas = np.zeros(nval)

        self.error = np.zeros(nval)

        self.converged = np.zeros(nval, dtype=bool)

        self.Sf = np.zeros((nval, nbr), dtype=complex)
        self.St = np.zeros((nval, nbr), dtype=complex)

        self.loading = np.zeros((nval, nbr))

        self.losses = np.zeros((nval, nbr), dtype=complex)

        self.Sbus = np.zeros((nval, nbus), dtype=complex)

        self.bus_types = bus_types

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'lambda': self.lambdas.tolist(),
                'Vm': np.abs(self.voltages).tolist(),
                'Va': np.angle(self.voltages).tolist(),
                'error': self.error.tolist()}
        return data

    def apply_from_island(self, results: CpfNumericResults, bus_original_idx, branch_original_idx):
        """
        Apply the results of an island to this ContinuationPowerFlowResults instance
        :param results: CpfNumericResults instance of the island
        :param bus_original_idx: indices of the buses in the complete grid
        :param branch_original_idx: indices of the branches in the complete grid
        """

        nval = np.arange(len(results))

        self.voltages[np.ix_(nval, bus_original_idx)] = results.V
        self.Sbus[np.ix_(nval, bus_original_idx)] = results.Sbus

        self.lambdas[nval] = results.lmbda
        self.error[nval] = results.normF
        self.converged[nval] = results.success

        self.Sf[np.ix_(nval, branch_original_idx)] = results.Sf
        self.St[np.ix_(nval, branch_original_idx)] = results.St

        self.loading[np.ix_(nval, branch_original_idx)] = results.loading
        self.losses[np.ix_(nval, branch_original_idx)] = results.losses

    def mdl(self, result_type: ResultTypes = ResultTypes.BusVoltage) -> ResultsModel:
        """
        Plot the results
        :param result_type:
        :return:
        """
        y_label = ''
        x_label = ''
        title = ''
        if result_type == ResultTypes.BusVoltage:
            labels = self.bus_names
            y = abs(np.array(self.voltages))
            x = self.lambdas
            title = 'Bus voltage'
            y_label = '(p.u.)'
            x_label = 'Loading from the base situation ($\lambda$)'

        elif result_type == ResultTypes.BusActivePower:
            labels = self.bus_names
            y = self.Sbus.real
            x = self.lambdas
            title = 'Bus active power'
            y_label = '(p.u.)'
            x_label = 'Loading from the base situation ($\lambda$)'

        elif result_type == ResultTypes.BusReactivePower:
            labels = self.bus_names
            y = self.Sbus.imag
            x = self.lambdas
            title = 'Bus reactive power'
            y_label = '(p.u.)'
            x_label = 'Loading from the base situation ($\lambda$)'

        elif result_type == ResultTypes.BranchActivePowerFrom:
            labels = self.branch_names
            y = self.Sf.real
            x = self.lambdas
            title = 'Branch active power (from)'
            y_label = 'MW'
            x_label = 'Loading from the base situation ($\lambda$)'

        elif result_type == ResultTypes.BranchReactivePowerFrom:
            labels = self.branch_names
            y = self.Sf.imag
            x = self.lambdas
            title = 'Branch reactive power (from)'
            y_label = 'MVAr'
            x_label = 'Loading from the base situation ($\lambda$)'

        elif result_type == ResultTypes.BranchActivePowerTo:
            labels = self.branch_names
            y = self.St.real
            x = self.lambdas
            title = 'Branch active power (to)'
            y_label = 'MW'
            x_label = 'Loading from the base situation ($\lambda$)'

        elif result_type == ResultTypes.BranchReactivePowerTo:
            labels = self.branch_names
            y = self.St.imag
            x = self.lambdas
            title = 'Branch reactive power (to)'
            y_label = 'MVAr'
            x_label = 'Loading from the base situation ($\lambda$)'

        elif result_type == ResultTypes.BranchActiveLosses:
            labels = self.branch_names
            y = self.losses.real
            x = self.lambdas
            title = 'Branch active power losses'
            y_label = 'MW'
            x_label = 'Loading from the base situation ($\lambda$)'

        elif result_type == ResultTypes.BranchReactiveLosses:
            labels = self.branch_names
            y = self.losses.imag
            x = self.lambdas
            title = 'Branch reactive power losses'
            y_label = 'MVAr'
            x_label = 'Loading from the base situation ($\lambda$)'

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            y = self.loading * 100.0
            x = self.lambdas
            title = 'Branch loading'
            y_label = '%'
            x_label = 'Loading from the base situation ($\lambda$)'

        else:
            labels = self.bus_names
            x = self.lambdas
            y = self.voltages

        # assemble model
        mdl = ResultsModel(data=y, index=x, columns=labels, title=title,
                           ylabel=y_label, xlabel=x_label, units=y_label)
        return mdl


class ContinuationPowerFlowDriver(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Continuation Power Flow'

    def __init__(self, circuit: MultiCircuit,
                 options: ContinuationPowerFlowOptions,
                 inputs: ContinuationPowerFlowInput,
                 pf_options: PowerFlowOptions,
                 opf_results=None, t=0):
        """
        ContinuationPowerFlowDriver constructor
        :param circuit: NumericalCircuit instance
        :param options: ContinuationPowerFlowOptions instance
        :param inputs: ContinuationPowerFlowInput instance
        :param pf_options: PowerFlowOptions instance
        :param opf_results:
        """

        QThread.__init__(self)

        # MultiCircuit instance
        self.circuit = circuit

        # voltage stability options
        self.options = options

        self.inputs = inputs

        self.pf_options = pf_options

        self.opf_results = opf_results

        self.t = t

        self.results = None

        self.__cancel__ = False

    def get_steps(self):
        """
        List of steps
        """
        if self.results.lambdas is not None:
            return ['Lambda:' + str(l) for l in self.results.lambdas]
        else:
            return list()

    def progress_callback(self, lmbda):
        """
        Send progress report
        :param lmbda: lambda value
        :return: None
        """
        self.progress_text.emit('Running continuation power flow (lambda:' + "{0:.2f}".format(lmbda) + ')...')

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        print('Running voltage collapse...')

        nc = compile_snapshot_circuit(circuit=self.circuit,
                                      apply_temperature=self.pf_options.apply_temperature_correction,
                                      branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode,
                                      opf_results=self.opf_results)

        islands = nc.split_into_islands(ignore_single_node_islands=self.pf_options.ignore_single_node_islands)

        result_series = list()

        for island in islands:

            self.progress_text.emit('Running voltage collapse at circuit ' + str(nc) + '...')

            if len(island.vd) > 0 and len(island.pqpv) > 0:

                results = continuation_nr(Ybus=island.Ybus,
                                          Cf=island.Cf,
                                          Ct=island.Ct,
                                          Yf=island.Yf,
                                          Yt=island.Yt,
                                          branch_rates=island.branch_rates,
                                          Sbase=island.Sbase,
                                          Ibus_base=island.Ibus,
                                          Ibus_target=island.Ibus,
                                          Sbus_base=self.inputs.Sbase[island.original_bus_idx],
                                          Sbus_target=self.inputs.Starget[island.original_bus_idx],
                                          V=self.inputs.Vbase[island.original_bus_idx],
                                          distributed_slack=self.pf_options.distributed_slack,
                                          bus_installed_power=island.bus_installed_power,
                                          vd=island.vd,
                                          pv=island.pv,
                                          pq=island.pq,
                                          step=self.options.step,
                                          approximation_order=self.options.approximation_order,
                                          adapt_step=self.options.adapt_step,
                                          step_min=self.options.step_min,
                                          step_max=self.options.step_max,
                                          error_tol=self.options.error_tol,
                                          tol=self.options.tol,
                                          max_it=self.options.max_it,
                                          stop_at=self.options.stop_at,
                                          control_q=self.pf_options.control_Q,
                                          qmax_bus=island.Qmax_bus,
                                          qmin_bus=island.Qmin_bus,
                                          original_bus_types=island.bus_types,
                                          base_overload_number=self.inputs.base_overload_number,
                                          verbose=False,
                                          call_back_fx=self.progress_callback)

                # store the result series
                result_series.append(results)

        # analyze the result series to compact all the results into one object
        if len(result_series) > 0:
            max_len = max([len(r) for r in result_series])
        else:
            max_len = 0

            # declare results
        self.results = ContinuationPowerFlowResults(nval=max_len, nbus=nc.nbus, nbr=nc.nbr,
                                                    bus_names=nc.bus_names,
                                                    branch_names=nc.branch_names,
                                                    bus_types=nc.bus_types)

        for i in range(len(result_series)):
            if len(result_series[i]) > 0:
                self.results.apply_from_island(result_series[i],
                                               islands[i].original_bus_idx,
                                               islands[i].original_branch_idx)

        print('done!')
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()

