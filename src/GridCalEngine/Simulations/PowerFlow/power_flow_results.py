# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib.colors as plt_colors
from typing import List
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.basic_structures import IntVec, Vec, StrVec, CxVec, ConvergenceReport
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class NumericPowerFlowResults:
    """
    NumericPowerFlowResults, used to return values from the numerical methods
    """

    def __init__(self,
                 V: CxVec,
                 Scalc: CxVec,
                 m: Vec,
                 tau: Vec,
                 Sf: CxVec,
                 St: CxVec,
                 If: CxVec,
                 It: CxVec,
                 loading: CxVec,
                 losses: CxVec,
                 Pf_vsc: Vec,
                 St_vsc: CxVec,
                 If_vsc: Vec,
                 It_vsc: CxVec,
                 losses_vsc: Vec,
                 loading_vsc: Vec,
                 Sf_hvdc: CxVec,
                 St_hvdc: CxVec,
                 losses_hvdc: CxVec,
                 loading_hvdc: Vec,
                 norm_f: float,
                 converged: bool,
                 iterations: int,
                 elapsed: float):
        """
        Object to store the results returned by a numeric power flow routine
        :param V: Voltage vector
        :param Scalc: Calculated power vector
        :param m: Tap modules vector for all the Branches
        :param tau: Tap angles vector for all the Branches
        :param Sf: Power flom vector for all the Branches
        :param St: Power to vector for all the Branches
        :param If: Current flom vector for all the Branches
        :param It: Current to vector for all the Branches
        :param loading: Loading vector for all the Branches
        :param losses: Losses vector for all the Branches
        :param Pf_vsc:
        :param St_vsc:
        :param If_vsc:
        :param It_vsc:
        :param losses_vsc:
        :param Sf_hvdc:
        :param St_hvdc:
        :param losses_hvdc:
        :param norm_f: error
        :param converged: converged?
        :param iterations: number of iterations
        :param elapsed: time elapsed
        """
        self.V = V
        self.Scalc = Scalc

        # regular branches
        self.Sf = Sf
        self.St = St
        self.If = If
        self.It = It
        self.loading = loading
        self.losses = losses

        # controllable branches
        self.tap_module = m
        self.tap_angle = tau

        # VSC
        self.Pf_vsc = Pf_vsc
        self.St_vsc = St_vsc
        self.If_vsc = If_vsc
        self.It_vsc = It_vsc
        self.losses_vsc = losses_vsc
        self.loading_vsc = loading_vsc

        # Hvdc
        self.Sf_hvdc = Sf_hvdc
        self.St_hvdc = St_hvdc
        self.losses_hvdc = losses_hvdc
        self.loading_hvdc = loading_hvdc

        # convergence metrics
        self.converged = converged
        self.norm_f = norm_f
        self.iterations = iterations
        self.elapsed = elapsed
        self.method = None


class PowerFlowResults(ResultsTemplate):

    def __init__(
            self,
            n: int,
            m: int,
            n_hvdc: int,
            n_vsc: int,
            n_gen: int,
            n_batt: int,
            n_sh: int,
            bus_names: np.ndarray,
            branch_names: np.ndarray,
            hvdc_names: np.ndarray,
            vsc_names: np.ndarray,
            gen_names: np.ndarray,
            batt_names: np.ndarray,
            sh_names: np.ndarray,
            bus_types: np.ndarray,
            clustering_results=None):
        """
        A **PowerFlowResults** object is create as an attribute of the
        :ref:`PowerFlowMP<pf_mp>` (as PowerFlowMP.results) when the power flow is run. It
        provides access to the simulation results through its class attributes.
        :param n: number of nodes
        :param m: number of Branches
        :param n_hvdc: number of HVDC devices
        :param bus_names: list of bus names
        :param branch_names: list of branch names
        :param hvdc_names: list of HVDC names
        :param bus_types: array of bus types
        """

        ResultsTemplate.__init__(
            self,
            name='Power flow',
            available_results={
                ResultTypes.BusResults: [
                    ResultTypes.BusVoltageModule,
                    ResultTypes.BusVoltageAngle,
                    ResultTypes.BusActivePower,
                    ResultTypes.BusReactivePower
                ],
                ResultTypes.BranchResults: [
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

                    ResultTypes.BranchLoading,
                    ResultTypes.BranchActiveLosses,
                    ResultTypes.BranchReactiveLosses,
                    ResultTypes.BranchActiveLossesPercentage,
                    ResultTypes.BranchVoltage,
                    ResultTypes.BranchAngles
                ],
                ResultTypes.HvdcResults: [
                    ResultTypes.HvdcPowerFrom,
                    ResultTypes.HvdcPowerTo,
                    ResultTypes.HvdcLosses,
                ],

                ResultTypes.VscResults: [
                    ResultTypes.VscPowerFrom,
                    ResultTypes.VscPowerTo,
                    ResultTypes.VscLosses,
                ],
                ResultTypes.GeneratorResults: [
                    ResultTypes.GeneratorReactivePower,
                ],

                ResultTypes.BatteryResults: [
                    ResultTypes.BatteryReactivePower,
                ],

                ResultTypes.ShuntResults: [
                    ResultTypes.ShuntReactivePower,
                ],

                ResultTypes.AreaResults: [
                    ResultTypes.InterAreaExchange,
                    ResultTypes.ActivePowerFlowPerArea,
                    ResultTypes.LossesPerArea,
                    ResultTypes.LossesPercentPerArea,
                    ResultTypes.LossesPerGenPerArea
                ],
                ResultTypes.SpecialPlots: [
                    ResultTypes.BusVoltagePolarPlot
                ]
            },
            time_array=None,
            clustering_results=clustering_results,
            study_results_type=StudyResultsType.PowerFlow
        )

        self.bus_names: StrVec = bus_names
        self.branch_names: StrVec = branch_names
        self.hvdc_names: StrVec = hvdc_names
        self.vsc_names: StrVec = vsc_names
        self.gen_names = gen_names
        self.batt_names = batt_names
        self.sh_names = sh_names
        self.bus_types: IntVec = bus_types

        self.Sbus: CxVec = np.zeros(n, dtype=complex)
        self.voltage: CxVec = np.zeros(n, dtype=complex)

        self.Sf: CxVec = np.zeros(m, dtype=complex)
        self.St: CxVec = np.zeros(m, dtype=complex)
        self.If: CxVec = np.zeros(m, dtype=complex)
        self.It: CxVec = np.zeros(m, dtype=complex)

        self.tap_module: Vec = np.zeros(m, dtype=float)
        self.tap_angle: Vec = np.zeros(m, dtype=float)

        self.Vbranch: CxVec = np.zeros(m, dtype=complex)
        self.loading: CxVec = np.zeros(m, dtype=complex)
        self.losses: CxVec = np.zeros(m, dtype=complex)

        self.losses_hvdc: Vec = np.zeros(n_hvdc)
        self.Pf_hvdc: Vec = np.zeros(n_hvdc)
        self.Pt_hvdc: Vec = np.zeros(n_hvdc)
        self.loading_hvdc: Vec = np.zeros(n_hvdc)

        # VSC
        self.Pf_vsc = np.zeros(n_vsc, dtype=float)
        self.St_vsc = np.zeros(n_vsc, dtype=complex)
        self.If_vsc = np.zeros(n_vsc, dtype=float)
        self.It_vsc = np.zeros(n_vsc, dtype=complex)
        self.losses_vsc = np.zeros(n_vsc, dtype=float)
        self.loading_vsc = np.zeros(n_vsc, dtype=float)

        self.gen_q: Vec = np.zeros(n_gen)
        self.battery_q: Vec = np.zeros(n_batt)
        self.shunt_q: Vec = np.zeros(n_sh)

        self.plot_bars_limit: int = 100
        self.convergence_reports: List[ConvergenceReport] = list()

        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='hvdc_names', tpe=StrVec)

        self.register(name='gen_names', tpe=StrVec)
        self.register(name='batt_names', tpe=StrVec)
        self.register(name='sh_names', tpe=StrVec)

        self.register(name='bus_types', tpe=IntVec)

        self.register(name='F', tpe=IntVec)
        self.register(name='T', tpe=IntVec)
        self.register(name='hvdc_F', tpe=IntVec)
        self.register(name='hvdc_T', tpe=IntVec)
        self.register(name='bus_area_indices', tpe=IntVec)
        self.register(name='area_names', tpe=IntVec)

        self.register(name='Sbus', tpe=CxVec)
        self.register(name='voltage', tpe=CxVec)

        self.register(name='Sf', tpe=CxVec)
        self.register(name='St', tpe=CxVec)
        self.register(name='If', tpe=CxVec)
        self.register(name='It', tpe=CxVec)
        self.register(name='tap_module', tpe=Vec)
        self.register(name='tap_angle', tpe=Vec)
        self.register(name='Vbranch', tpe=CxVec)
        self.register(name='loading', tpe=CxVec)
        self.register(name='losses', tpe=CxVec)

        self.register(name='losses_hvdc', tpe=Vec)
        self.register(name='Pf_hvdc', tpe=Vec)
        self.register(name='Pt_hvdc', tpe=Vec)
        self.register(name='loading_hvdc', tpe=Vec)

        self.register(name='losses_vsc', tpe=Vec)
        self.register(name='Pf_vsc', tpe=Vec)
        self.register(name='St_vsc', tpe=CxVec)
        self.register(name='If_vsc', tpe=Vec)
        self.register(name='It_vsc', tpe=CxVec)
        self.register(name='loading_vsc', tpe=Vec)

        self.register(name='gen_q', tpe=Vec)
        self.register(name='battery_q', tpe=Vec)
        self.register(name='shunt_q', tpe=Vec)

        # self.register(name='island_number', tpe=int)

    def apply_new_rates(self, nc: NumericalCircuit):
        """

        :param nc:
        :return:
        """
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

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

    @property
    def iterations(self):
        """
        Check if converged in all modes
        :return: True / False
        """
        val = 0.0
        for conv in self.convergence_reports:
            val = max(val, conv.iterations())
        return val

    def apply_from_island(self,
                          results: NumericPowerFlowResults,
                          b_idx: np.ndarray,
                          br_idx: np.ndarray,
                          hvdc_idx: np.ndarray,
                          vsc_idx: np.ndarray) -> None:
        """
        Apply results from another island circuit to the circuit results represented
        here.
        :param results: NumericPowerFlowResults from an island circuit
        :param b_idx: bus original indices
        :param br_idx: branch original indices
        :param hvdc_idx: hvdc original indices
        :param vsc_idx: vsc original indices
        :return: None
        """
        self.voltage[b_idx] = results.V
        self.Sbus[b_idx] = results.Scalc

        self.tap_module[br_idx] = results.tap_module
        self.tap_angle[br_idx] = results.tap_angle

        self.Sf[br_idx] = results.Sf
        self.St[br_idx] = results.St
        self.If[br_idx] = results.If
        self.It[br_idx] = results.It

        # self.Vbranch[br_idx] = results.Vbranch
        self.loading[br_idx] = results.loading
        self.losses[br_idx] = results.losses

        # Hvdc
        self.Pf_hvdc[hvdc_idx] = results.Sf_hvdc.real
        self.Pt_hvdc[hvdc_idx] = results.St_hvdc.real
        self.losses_hvdc[hvdc_idx] = results.losses_hvdc.real
        self.loading_hvdc[hvdc_idx] = results.loading_hvdc.real

        # VSC
        self.Pf_vsc[vsc_idx] = results.Pf_vsc
        self.St_vsc[vsc_idx] = results.St_vsc
        self.If_vsc[vsc_idx] = results.If_vsc
        self.It_vsc[vsc_idx] = results.It_vsc
        self.losses_vsc[vsc_idx] = results.losses_vsc
        self.loading_vsc[vsc_idx] = results.loading_vsc

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

    def get_oveload_score(self, branch_prices: Vec):
        """
        Compute the cost of overload
        :param branch_prices: array of branch prices
        :return:
        """
        ld = np.abs(self.loading)
        idx = np.where(ld > 1)[0]
        cost = np.sum(ld[idx] * branch_prices[idx])
        return cost

    def get_bus_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the buses results
        :return: DataFrame
        """
        return pd.DataFrame(data={'Vm': np.abs(self.voltage),
                                  'Va': np.angle(self.voltage, deg=True),
                                  'P': self.Sbus.real,
                                  'Q': self.Sbus.imag},
                            index=self.bus_names)

    def get_branch_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the branches results
        :return: DataFrame
        """
        return pd.DataFrame(data={'Pf': self.Sf.real,
                                  'Qf': self.Sf.imag,
                                  'Pt': self.St.real,
                                  'Qt': self.St.imag,
                                  'loading': self.loading.real * 100.0,
                                  "Ploss": self.losses.real,
                                  "Qloss": self.losses.imag,
                                  },
                            index=self.branch_names)

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """

        :param result_type:
        :return:
        """

        if result_type == ResultTypes.BusVoltageModule:

            return ResultsTable(data=np.abs(self.voltage),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BusVoltageAngle:

            return ResultsTable(data=np.angle(self.voltage, deg=True),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.BusVoltagePolarPlot:
            vm = np.abs(self.voltage)
            va = np.angle(self.voltage, deg=True)
            va_rad = np.angle(self.voltage, deg=False)
            data = np.c_[vm, va]

            if self.plotting_allowed():
                plt.ion()
                color_norm = plt_colors.LogNorm()
                fig = plt.figure(figsize=(8, 6))
                ax3 = plt.subplot(1, 1, 1, projection='polar')
                sc3 = ax3.scatter(va_rad, vm, c=vm, norm=color_norm)
                fig.suptitle(result_type.value)
                plt.tight_layout()
                plt.show()

            return ResultsTable(data=data,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array(['Voltage module', 'Voltage angle (deg)']),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u., deg)',
                                units='(p.u., deg)')

        elif result_type == ResultTypes.BusActivePower:

            return ResultsTable(data=self.Sbus.real,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BusReactivePower:

            return ResultsTable(data=self.Sbus.imag,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActivePowerFrom:

            return ResultsTable(data=self.Sf.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactivePowerFrom:

            return ResultsTable(data=self.Sf.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActivePowerTo:

            return ResultsTable(data=self.St.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactivePowerTo:

            return ResultsTable(data=self.St.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActiveCurrentFrom:

            return ResultsTable(data=self.If.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentFrom:

            return ResultsTable(data=self.If.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchActiveCurrentTo:

            return ResultsTable(data=self.It.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentTo:

            return ResultsTable(data=self.It.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchLoading:

            return ResultsTable(data=np.abs(self.loading) * 100,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchActiveLosses:

            return ResultsTable(data=self.losses.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactiveLosses:

            return ResultsTable(data=self.losses.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActiveLossesPercentage:

            return ResultsTable(data=np.abs(self.losses.real) / np.abs(self.Sf.real + 1e-20) * 100.0,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchVoltage:

            return ResultsTable(data=np.abs(self.Vbranch),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchAngles:

            return ResultsTable(data=np.angle(self.Vbranch, deg=True),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.BranchTapModule:

            return ResultsTable(data=self.tap_module,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchTapAngle:

            return ResultsTable(data=np.rad2deg(self.tap_angle),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.HvdcLosses:

            return ResultsTable(data=self.losses_hvdc,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerFrom:

            return ResultsTable(data=self.Pf_hvdc,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerTo:

            return ResultsTable(data=self.Pt_hvdc,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.VscLosses:

            return ResultsTable(data=self.losses_vsc,
                                index=self.vsc_names,
                                idx_device_type=DeviceType.VscDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.VscPowerFrom:

            return ResultsTable(data=self.Pf_vsc,
                                index=self.vsc_names,
                                idx_device_type=DeviceType.VscDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.VscPowerTo:

            return ResultsTable(data=self.St_vsc.real,
                                index=self.vsc_names,
                                idx_device_type=DeviceType.VscDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.InterAreaExchange:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            data = self.get_inter_area_flows(area_names=self.area_names,
                                             F=self.F,
                                             T=self.T,
                                             Sf=self.Sf,
                                             hvdc_F=self.hvdc_F,
                                             hvdc_T=self.hvdc_T,
                                             hvdc_Pf=self.Pf_hvdc,
                                             bus_area_indices=self.bus_area_indices).real

            return ResultsTable(data=data,
                                index=np.array(index),
                                idx_device_type=DeviceType.AreaDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.LossesPercentPerArea:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            Pf = self.get_branch_values_per_area(np.abs(self.Sf.real), self.area_names, self.bus_area_indices, self.F,
                                                 self.T)
            Pf += self.get_hvdc_values_per_area(np.abs(self.Pf_hvdc), self.area_names, self.bus_area_indices,
                                                self.hvdc_F, self.hvdc_T)
            Pl = self.get_branch_values_per_area(np.abs(self.losses.real), self.area_names, self.bus_area_indices,
                                                 self.F, self.T)
            Pl += self.get_hvdc_values_per_area(np.abs(self.losses_hvdc), self.area_names, self.bus_area_indices,
                                                self.hvdc_F, self.hvdc_T)

            data = Pl / (Pf + 1e-20) * 100.0

            return ResultsTable(data=data,
                                index=np.array(index),
                                idx_device_type=DeviceType.AreaDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.LossesPerGenPerArea:
            index = [a for a in self.area_names]
            gen_bus = self.Sbus.copy().real
            gen_bus[gen_bus < 0] = 0
            Gf = self.get_bus_values_per_area(gen_bus, self.area_names, self.bus_area_indices)
            Pl = self.get_branch_values_per_area(np.abs(self.losses.real), self.area_names, self.bus_area_indices,
                                                 self.F, self.T)
            Pl += self.get_hvdc_values_per_area(np.abs(self.losses_hvdc), self.area_names, self.bus_area_indices,
                                                self.hvdc_F, self.hvdc_T)

            data = np.zeros(len(self.area_names))
            for i in range(len(self.area_names)):
                data[i] = Pl[i, i] / (Gf[i] + 1e-20) * 100.0

            return ResultsTable(data=data,
                                index=np.array(index),
                                idx_device_type=DeviceType.AreaDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.LossesPerArea:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            data = self.get_branch_values_per_area(np.abs(self.losses.real), self.area_names, self.bus_area_indices,
                                                   self.F, self.T)
            data += self.get_hvdc_values_per_area(np.abs(self.losses_hvdc), self.area_names, self.bus_area_indices,
                                                  self.hvdc_F, self.hvdc_T)

            return ResultsTable(data=data,
                                index=np.array(index),
                                idx_device_type=DeviceType.AreaDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.ActivePowerFlowPerArea:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            data = self.get_branch_values_per_area(np.abs(self.Sf.real), self.area_names, self.bus_area_indices,
                                                   self.F, self.T)
            data += self.get_hvdc_values_per_area(np.abs(self.Pf_hvdc), self.area_names, self.bus_area_indices,
                                                  self.hvdc_F, self.hvdc_T)

            return ResultsTable(data=data,
                                index=np.array(index),
                                idx_device_type=DeviceType.AreaDevice,
                                columns=np.array(columns),
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.GeneratorReactivePower:

            return ResultsTable(data=self.gen_q,
                                index=self.gen_names,
                                idx_device_type=DeviceType.GeneratorDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BatteryReactivePower:

            return ResultsTable(data=self.battery_q,
                                index=self.batt_names,
                                idx_device_type=DeviceType.BatteryDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.ShuntReactivePower:

            return ResultsTable(data=self.shunt_q,
                                index=self.sh_names,
                                idx_device_type=DeviceType.ShuntLikeDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        else:
            raise Exception('Unsupported result type: ' + str(result_type))

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
        bus_cols = ['Real voltage (p.u.)',
                    'Imag Voltage (p.u.)',
                    'Voltage module (p.u.)',
                    'Voltage angle (rad)']
        df_bus = pd.DataFrame(data=bus_data, columns=bus_cols)

        # branch results
        sr = self.Sf.real
        si = self.Sf.imag
        sm = np.abs(self.Sf)
        ld = np.abs(self.loading)
        la = self.losses.real
        lr = self.losses.imag
        ls = np.abs(self.losses)
        tm = np.abs(self.tap_module)

        branch_data = np.c_[sr, si, sm, ld, la, lr, ls, tm]
        branch_cols = ['Real power (MW)',
                       'Imag power (MVAr)',
                       'Power module (MVA)',
                       'Loading(%)',
                       'Losses (MW)',
                       'Losses (MVAr)',
                       'Losses (MVA)',
                       'Tap module']
        df_branch = pd.DataFrame(data=branch_data, columns=branch_cols)

        return df_bus, df_branch
