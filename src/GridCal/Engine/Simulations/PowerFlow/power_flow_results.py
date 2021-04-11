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
import pandas as pd
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel


class NumericPowerFlowResults:

    def __init__(self, V, converged, norm_f, Scalc, ma=None, theta=None, Beq=None, iterations=0, elapsed=0):
        """

        :param V:
        :param converged:
        :param norm_f:
        :param Scalc:
        :param ma:
        :param theta:
        :param Beq:
        :param iterations:
        :param elapsed:
        """
        self.V = V
        self.converged = converged
        self.norm_f = norm_f
        self.Scalc = Scalc
        self.ma = ma
        self.theta = theta
        self.Beq = Beq
        self.iterations = iterations
        self.elapsed = elapsed


class PowerFlowResults:
    """
    A **PowerFlowResults** object is create as an attribute of the
    :ref:`PowerFlowMP<pf_mp>` (as PowerFlowMP.results) when the power flow is run. It
    provides access to the simulation results through its class attributes.

    Attributes:

        **Sbus** (list): Power at each bus in complex per unit

        **voltage** (list): Voltage at each bus in complex per unit

        **Sf** (list): Power through each branch in complex MVA

        **If** (list): Current through each branch in complex per unit

        **loading** (list): Loading of each branch in per unit

        **losses** (list): Losses in each branch in complex MVA

        **tap_module** (list): Computed tap module at each branch in per unit

        **flow_direction** (list): Flow direction at each branch

        **Vbranch** (list): Voltage increment at each branch

        **error** (float): Power flow computed error

        **converged** (bool): Did the power flow converge?

        **Qpv** (list): Reactive power at each PV node in per unit

        **inner_it** (int): Number of inner iterations

        **outer_it** (int): Number of outer iterations

        **elapsed** (float): Simulation duration in seconds

        **methods** (list): Power flow methods used

    """

    def __init__(self, n, m, n_tr, n_hvdc, bus_names, branch_names, transformer_names, hvdc_names, bus_types):

        self.name = 'Power flow'

        self.n = n
        self.m = m
        self.n_tr = n_tr
        self.n_hvdc = n_hvdc

        self.bus_types = bus_types

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.transformer_names = transformer_names
        self.hvdc_names = hvdc_names

        self.Sbus = np.zeros(n, dtype=complex)

        self.voltage = np.zeros(n, dtype=complex)

        self.overvoltage = np.zeros(n, dtype=complex)

        self.undervoltage = np.zeros(n, dtype=complex)

        self.Sf = np.zeros(m, dtype=complex)
        self.St = np.zeros(m, dtype=complex)

        self.If = np.zeros(m, dtype=complex)
        self.It = np.zeros(m, dtype=complex)

        self.ma = np.zeros(m, dtype=float)
        self.theta = np.zeros(m, dtype=float)
        self.Beq = np.zeros(m, dtype=float)

        self.Vbranch = np.zeros(m, dtype=complex)

        self.loading = np.zeros(m, dtype=complex)

        self.flow_direction = np.zeros(m, dtype=float)

        self.transformer_tap_module = np.zeros(n_tr, dtype=float)

        self.losses = np.zeros(m, dtype=complex)

        self.hvdc_losses = np.zeros(self.n_hvdc)

        self.hvdc_Pf = np.zeros(self.n_hvdc)

        self.hvdc_Pt = np.zeros(self.n_hvdc)

        self.hvdc_loading = np.zeros(self.n_hvdc)

        self.plot_bars_limit = 100

        self.convergence_reports = list()

        self.available_results = [ResultTypes.BusVoltageModule,
                                  ResultTypes.BusVoltageAngle,
                                  ResultTypes.BusActivePower,
                                  ResultTypes.BusReactivePower,

                                  ResultTypes.BranchActivePowerFrom,
                                  ResultTypes.BranchReactivePowerFrom,
                                  ResultTypes.BranchActivePowerTo,
                                  ResultTypes.BranchReactivePowerTo,

                                  ResultTypes.BranchActiveCurrentFrom,
                                  ResultTypes.BranchReactiveCurrentFrom,
                                  ResultTypes.BranchActiveCurrentTo,
                                  ResultTypes.BranchReactiveCurrentTo,

                                  ResultTypes.BranchTapModule,
                                  ResultTypes.BranchTapAngle,
                                  ResultTypes.BranchBeq,

                                  ResultTypes.BranchLoading,
                                  ResultTypes.Transformer2WTapModule,
                                  ResultTypes.BranchActiveLosses,
                                  ResultTypes.BranchReactiveLosses,
                                  ResultTypes.BranchVoltage,
                                  ResultTypes.BranchAngles,

                                  ResultTypes.HvdcLosses,
                                  ResultTypes.HvdcPowerFrom,
                                  ResultTypes.HvdcPowerTo]

    @property
    def converged(self):
        """
        Check if converged in all modes
        :return: True / False
        """
        val = True
        for conv in self.convergence_reports:
            val *= conv.converged()
        return val

    @property
    def error(self):
        """
        Check if converged in all modes
        :return: True / False
        """
        val = 0.0
        for conv in self.convergence_reports:
            val = max(val, conv.error())
        return val

    @property
    def elapsed(self):
        """
        Check if converged in all modes
        :return: True / False
        """
        val = 0.0
        for conv in self.convergence_reports:
            val = max(val, conv.elapsed())
        return val

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        val = PowerFlowResults(n=self.n, m=self.m, n_tr=self.n_tr,
                               bus_names=self.bus_names,
                               branch_names=self.branch_names,
                               transformer_names=self.transformer_names)
        val.Sbus = self.Sbus.copy()
        val.voltage = self.voltage.copy()
        val.overvoltage = self.overvoltage.copy()
        val.undervoltage = self.undervoltage.copy()
        val.Sf = self.Sf.copy()
        val.If = self.If.copy()
        val.Vbranch = self.Vbranch.copy()
        val.loading = self.loading.copy()
        val.flow_direction = self.flow_direction.copy()
        val.transformer_tap_module = self.transformer_tap_module.copy()
        val.losses = self.losses.copy()
        val.overloads = self.overloads.copy()

        return val

    def apply_from_island(self, results: "PowerFlowResults", b_idx, br_idx, tr_idx):
        """
        Apply results from another island circuit to the circuit results represented
        here.

        Arguments:

            **results**: PowerFlowResults

            **b_idx**: bus original indices

            **elm_idx**: branch original indices
        """
        self.Sbus[b_idx] = results.Sbus

        self.voltage[b_idx] = results.voltage

        self.Sf[br_idx] = results.Sf

        self.St[br_idx] = results.St

        self.If[br_idx] = results.If

        self.Vbranch[br_idx] = results.Vbranch

        self.loading[br_idx] = results.loading

        self.transformer_tap_module[tr_idx] = results.transformer_tap_module

        self.losses[br_idx] = results.losses

        self.flow_direction[br_idx] = results.flow_direction

        self.convergence_reports += results.convergence_reports

    def get_report_dataframe(self, island_idx=0):
        """
        Get a DataFrame containing the convergence report.

        Arguments:

            **island_idx**: (optional) island index

        Returns:

            DataFrame
        """
        report = self.convergence_reports[island_idx]
        data = {'Method': report.methods_,
                'Converged?': report.converged_,
                'Error': report.error_,
                'Elapsed (s)': report.elapsed_,
                'Iterations': report.iterations_}

        df = pd.DataFrame(data)

        return df

    def mdl(self, result_type: ResultTypes) -> "ResultsModel":
        """

        :param result_type:
        :return:
        """

        if result_type == ResultTypes.BusVoltageModule:
            labels = self.bus_names
            y = np.abs(self.voltage)
            y_label = '(p.u.)'
            title = 'Bus voltage '

        elif result_type == ResultTypes.BusVoltageAngle:
            labels = self.bus_names
            y = np.angle(self.voltage, deg=True)
            y_label = '(deg)'
            title = 'Bus voltage '

        elif result_type == ResultTypes.BusActivePower:
            labels = self.bus_names
            y = self.Sbus.real
            y_label = '(MW)'
            title = 'Bus Active power '

        elif result_type == ResultTypes.BusReactivePower:
            labels = self.bus_names
            y = self.Sbus.imag
            y_label = '(MVAr)'
            title = 'Bus Reactive power '

        elif result_type == ResultTypes.BusVoltagePolar:
            labels = self.bus_names
            y = self.voltage
            y_label = '(p.u.)'
            title = 'Bus voltage '

        elif result_type == ResultTypes.BranchPower:
            labels = self.branch_names
            y = self.Sf
            y_label = '(MVA)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchActivePowerFrom:
            labels = self.branch_names
            y = self.Sf.real
            y_label = '(MW)'
            title = 'Branch active power '

        elif result_type == ResultTypes.BranchReactivePowerFrom:
            labels = self.branch_names
            y = self.Sf.imag
            y_label = '(MVAr)'
            title = 'Branch reactive power '

        elif result_type == ResultTypes.BranchActivePowerTo:
            labels = self.branch_names
            y = self.St.real
            y_label = '(MW)'
            title = 'Branch active power '

        elif result_type == ResultTypes.BranchReactivePowerTo:
            labels = self.branch_names
            y = self.St.imag
            y_label = '(MVAr)'
            title = 'Branch reactive power '

        elif result_type == ResultTypes.Transformer2WTapModule:
            labels = self.transformer_names
            y = self.transformer_tap_module
            y_label = '(p.u.)'
            title = 'Transformer tap module '

        elif result_type == ResultTypes.BranchCurrent:
            labels = self.branch_names
            y = self.If
            y_label = '(p.u.)'
            title = 'Branch current '

        elif result_type == ResultTypes.BranchActiveCurrentFrom:
            labels = self.branch_names
            y = self.If.real
            y_label = '(p.u.)'
            title = 'Branch active current '

        elif result_type == ResultTypes.BranchReactiveCurrentFrom:
            labels = self.branch_names
            y = self.If.imag
            y_label = '(p.u.)'
            title = 'Branch reactive current '

        elif result_type == ResultTypes.BranchActiveCurrentTo:
            labels = self.branch_names
            y = self.It.real
            y_label = '(p.u.)'
            title = 'Branch active current '

        elif result_type == ResultTypes.BranchReactiveCurrentTo:
            labels = self.branch_names
            y = self.It.imag
            y_label = '(p.u.)'
            title = 'Branch reactive current '

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            y = np.abs(self.loading) * 100
            y_label = '(%)'
            title = 'Branch loading '

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            y = self.losses
            y_label = '(MVA)'
            title = 'Branch losses '

        elif result_type == ResultTypes.BranchActiveLosses:
            labels = self.branch_names
            y = self.losses.real
            y_label = '(MW)'
            title = 'Branch active losses '

        elif result_type == ResultTypes.BranchReactiveLosses:
            labels = self.branch_names
            y = self.losses.imag
            y_label = '(MVAr)'
            title = 'Branch reactive losses '

        elif result_type == ResultTypes.BranchVoltage:
            labels = self.branch_names
            y = np.abs(self.Vbranch)
            y_label = '(p.u.)'
            title = 'Branch voltage drop '

        elif result_type == ResultTypes.BranchAngles:
            labels = self.branch_names
            y = np.angle(self.Vbranch, deg=True)
            y_label = '(deg)'
            title = 'Branch voltage angle '

        elif result_type == ResultTypes.BranchTapModule:
            labels = self.branch_names
            y = self.ma
            y_label = '(p.u.)'
            title = 'Branch tap module '

        elif result_type == ResultTypes.BranchTapAngle:
            labels = self.branch_names
            y = self.theta
            y_label = '(rad)'
            title = 'Branch tap angle '

        elif result_type == ResultTypes.BranchBeq:
            labels = self.branch_names
            y = self.Beq
            y_label = '(p.u.)'
            title = 'Branch Beq '

        elif result_type == ResultTypes.HvdcLosses:
            labels = self.hvdc_names
            y = self.hvdc_losses
            y_label = '(MW)'
            title = result_type.value

        elif result_type == ResultTypes.HvdcPowerFrom:
            labels = self.hvdc_names
            y = self.hvdc_Pf
            y_label = '(MW)'
            title = result_type.value

        elif result_type == ResultTypes.HvdcPowerTo:
            labels = self.hvdc_names
            y = self.hvdc_Pt
            y_label = '(MW)'
            title = result_type.value

        else:
            raise Exception('Unsupported result type: ' + str(result_type))

        # assemble model
        mdl = ResultsModel(data=y, index=labels, columns=[result_type.value[0]],
                           title=title, ylabel=y_label, units=y_label)
        return mdl

    def export_all(self):
        """
        Exports all the results to DataFrames.

        Returns:

            Bus results, Branch reuslts
        """

        # buses results
        vm = np.abs(self.voltage)
        va = np.angle(self.voltage)
        vr = self.voltage.real
        vi = self.voltage.imag
        bus_data = np.c_[vr, vi, vm, va]
        bus_cols = ['Real voltage (p.u.)', 'Imag Voltage (p.u.)', 'Voltage module (p.u.)', 'Voltage angle (rad)']
        df_bus = pd.DataFrame(data=bus_data, columns=bus_cols)

        # branch results
        sr = self.Sf.real
        si = self.Sf.imag
        sm = np.abs(self.Sf)
        ld = np.abs(self.loading)
        la = self.losses.real
        lr = self.losses.imag
        ls = np.abs(self.losses)
        tm = self.transformer_tap_module

        branch_data = np.c_[sr, si, sm, ld, la, lr, ls, tm]
        branch_cols = ['Real power (MW)', 'Imag power (MVAr)', 'Power module (MVA)', 'Loading(%)',
                       'Losses (MW)', 'Losses (MVAr)', 'Losses (MVA)', 'Tap module']
        df_branch = pd.DataFrame(data=branch_data, columns=branch_cols)

        return df_bus, df_branch

