# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib.colors as plt_colors
from typing import List, Tuple

from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults
from VeraGridEngine.basic_structures import IntVec, Vec, StrVec, CxVec, ConvergenceReport, Logger
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


def get_3p_indices(length_3p: int) -> Tuple[IntVec, IntVec, IntVec]:
    """
    get the 3-phase indexing
    :param length_3p: 3N length
    :return: index A, index B, index C
    """
    n = length_3p / 3
    bus_seq = np.arange(n, dtype=int)
    ia = 3 * bus_seq
    ib = 3 * bus_seq + 1
    ic = 3 * bus_seq + 2
    return ia, ib, ic


class PowerFlowResults3Ph(ResultsTemplate):

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
                    ResultTypes.BusVoltageModuleA,
                    ResultTypes.BusVoltageModuleB,
                    ResultTypes.BusVoltageModuleC,

                    ResultTypes.BusVoltageAngleA,
                    ResultTypes.BusVoltageAngleB,
                    ResultTypes.BusVoltageAngleC,

                    ResultTypes.BusActivePowerA,
                    ResultTypes.BusActivePowerB,
                    ResultTypes.BusActivePowerC,

                    ResultTypes.BusReactivePowerA,
                    ResultTypes.BusReactivePowerB,
                    ResultTypes.BusReactivePowerC,
                ],
                ResultTypes.BranchResults: [
                    ResultTypes.BranchActivePowerFromA,
                    ResultTypes.BranchActivePowerFromB,
                    ResultTypes.BranchActivePowerFromC,

                    ResultTypes.BranchReactivePowerFromA,
                    ResultTypes.BranchReactivePowerFromB,
                    ResultTypes.BranchReactivePowerFromC,

                    ResultTypes.BranchActivePowerToA,
                    ResultTypes.BranchActivePowerToB,
                    ResultTypes.BranchActivePowerToC,

                    ResultTypes.BranchReactivePowerToA,
                    ResultTypes.BranchReactivePowerToB,
                    ResultTypes.BranchReactivePowerToC,

                    ResultTypes.BranchActiveCurrentFromA,
                    ResultTypes.BranchActiveCurrentFromB,
                    ResultTypes.BranchActiveCurrentFromC,

                    ResultTypes.BranchReactiveCurrentFromA,
                    ResultTypes.BranchReactiveCurrentFromB,
                    ResultTypes.BranchReactiveCurrentFromC,

                    ResultTypes.BranchActiveCurrentToA,
                    ResultTypes.BranchActiveCurrentToB,
                    ResultTypes.BranchActiveCurrentToC,

                    ResultTypes.BranchReactiveCurrentToA,
                    ResultTypes.BranchReactiveCurrentToB,
                    ResultTypes.BranchReactiveCurrentToC,

                    ResultTypes.BranchTapModule,
                    ResultTypes.BranchTapAngle,

                    ResultTypes.BranchLoadingA,
                    ResultTypes.BranchLoadingB,
                    ResultTypes.BranchLoadingC,

                    ResultTypes.BranchActiveLossesA,
                    ResultTypes.BranchActiveLossesB,
                    ResultTypes.BranchActiveLossesC,

                    ResultTypes.BranchReactiveLossesA,
                    ResultTypes.BranchReactiveLossesB,
                    ResultTypes.BranchReactiveLossesC,

                    ResultTypes.BranchActiveLossesPercentageA,
                    ResultTypes.BranchActiveLossesPercentageB,
                    ResultTypes.BranchActiveLossesPercentageC,

                    ResultTypes.BranchVoltageA,
                    ResultTypes.BranchVoltageB,
                    ResultTypes.BranchVoltageC,

                    ResultTypes.BranchAnglesA,
                    ResultTypes.BranchAnglesB,
                    ResultTypes.BranchAnglesC
                ],
                ResultTypes.HvdcResults: [
                    ResultTypes.HvdcPowerFromA,
                    ResultTypes.HvdcPowerFromB,
                    ResultTypes.HvdcPowerFromC,

                    ResultTypes.HvdcPowerToA,
                    ResultTypes.HvdcPowerToB,
                    ResultTypes.HvdcPowerToC,

                    ResultTypes.HvdcLosses,
                ],

                ResultTypes.VscResults: [
                    ResultTypes.VscPowerFrom,

                    ResultTypes.VscPowerToA,
                    ResultTypes.VscPowerToB,
                    ResultTypes.VscPowerToC,

                    ResultTypes.VscLosses,
                ],
                ResultTypes.GeneratorResults: [
                    ResultTypes.GeneratorReactivePowerA,
                    ResultTypes.GeneratorReactivePowerB,
                    ResultTypes.GeneratorReactivePowerC,
                ],

                ResultTypes.BatteryResults: [
                    ResultTypes.BatteryReactivePowerA,
                    ResultTypes.BatteryReactivePowerB,
                    ResultTypes.BatteryReactivePowerC,
                ],

                ResultTypes.ShuntResults: [
                    ResultTypes.ShuntReactivePowerA,
                    ResultTypes.ShuntReactivePowerB,
                    ResultTypes.ShuntReactivePowerC,
                ],

                ResultTypes.SpecialPlots: [
                    ResultTypes.BusVoltagePolarPlot
                ]
            },
            time_array=None,
            clustering_results=clustering_results,
            study_results_type=StudyResultsType.PowerFlow,
            is_3ph=True
        )

        n = int(n/3)
        m = int(m/3)

        self.n = n
        self.m = m
        self.n_hvdc = n_hvdc
        self.n_vsc = n_vsc
        self.n_gen = n_gen
        self.n_batt = n_batt
        self.n_sh = n_sh

        self.bus_names: StrVec = bus_names
        self.branch_names: StrVec = branch_names
        self.hvdc_names: StrVec = hvdc_names
        self.vsc_names: StrVec = vsc_names
        self.gen_names = gen_names
        self.batt_names = batt_names
        self.sh_names = sh_names
        self.bus_types: IntVec = bus_types

        self.Sbus_A: CxVec = np.zeros(n, dtype=complex)
        self.Sbus_B: CxVec = np.zeros(n, dtype=complex)
        self.Sbus_C: CxVec = np.zeros(n, dtype=complex)

        self.voltage_A: CxVec = np.zeros(n, dtype=complex)
        self.voltage_B: CxVec = np.zeros(n, dtype=complex)
        self.voltage_C: CxVec = np.zeros(n, dtype=complex)

        self.Sf_A: CxVec = np.zeros(m, dtype=complex)
        self.Sf_B: CxVec = np.zeros(m, dtype=complex)
        self.Sf_C: CxVec = np.zeros(m, dtype=complex)

        self.St_A: CxVec = np.zeros(m, dtype=complex)
        self.St_B: CxVec = np.zeros(m, dtype=complex)
        self.St_C: CxVec = np.zeros(m, dtype=complex)

        self.If_A: CxVec = np.zeros(m, dtype=complex)
        self.If_B: CxVec = np.zeros(m, dtype=complex)
        self.If_C: CxVec = np.zeros(m, dtype=complex)

        self.It_A: CxVec = np.zeros(m, dtype=complex)
        self.It_B: CxVec = np.zeros(m, dtype=complex)
        self.It_C: CxVec = np.zeros(m, dtype=complex)

        self.tap_module: Vec = np.zeros(m, dtype=float)
        self.tap_angle: Vec = np.zeros(m, dtype=float)

        self.Vbranch_A: CxVec = np.zeros(m, dtype=complex)
        self.Vbranch_B: CxVec = np.zeros(m, dtype=complex)
        self.Vbranch_C: CxVec = np.zeros(m, dtype=complex)

        self.loading_A: CxVec = np.zeros(m, dtype=complex)
        self.loading_B: CxVec = np.zeros(m, dtype=complex)
        self.loading_C: CxVec = np.zeros(m, dtype=complex)

        self.losses_A: CxVec = np.zeros(m, dtype=complex)
        self.losses_B: CxVec = np.zeros(m, dtype=complex)
        self.losses_C: CxVec = np.zeros(m, dtype=complex)

        self.losses_hvdc: Vec = np.zeros(n_hvdc)
        self.Pf_hvdc_A: Vec = np.zeros(n_hvdc)
        self.Pf_hvdc_B: Vec = np.zeros(n_hvdc)
        self.Pf_hvdc_C: Vec = np.zeros(n_hvdc)

        self.Pt_hvdc_A: Vec = np.zeros(n_hvdc)
        self.Pt_hvdc_B: Vec = np.zeros(n_hvdc)
        self.Pt_hvdc_C: Vec = np.zeros(n_hvdc)

        self.loading_hvdc: Vec = np.zeros(n_hvdc)

        # VSC
        self.Pf_vsc = np.zeros(n_vsc, dtype=float)  # DC

        self.St_vsc_A = np.zeros(n_vsc, dtype=complex)
        self.St_vsc_B = np.zeros(n_vsc, dtype=complex)
        self.St_vsc_C = np.zeros(n_vsc, dtype=complex)

        self.If_vsc = np.zeros(n_vsc, dtype=float)

        self.It_vsc_A = np.zeros(n_vsc, dtype=complex)
        self.It_vsc_B = np.zeros(n_vsc, dtype=complex)
        self.It_vsc_C = np.zeros(n_vsc, dtype=complex)

        self.losses_vsc = np.zeros(n_vsc, dtype=float)

        self.loading_vsc = np.zeros(n_vsc, dtype=float)

        self.gen_q_A: Vec = np.zeros(n_gen)
        self.gen_q_B: Vec = np.zeros(n_gen)
        self.gen_q_C: Vec = np.zeros(n_gen)

        self.battery_q_A: Vec = np.zeros(n_batt)
        self.battery_q_B: Vec = np.zeros(n_batt)
        self.battery_q_C: Vec = np.zeros(n_batt)

        self.shunt_q_A: Vec = np.zeros(n_sh)
        self.shunt_q_B: Vec = np.zeros(n_sh)
        self.shunt_q_C: Vec = np.zeros(n_sh)

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

        self.register(name='Sbus_A', tpe=CxVec)
        self.register(name='Sbus_B', tpe=CxVec)
        self.register(name='Sbus_C', tpe=CxVec)

        self.register(name='voltage_A', tpe=CxVec)
        self.register(name='voltage_B', tpe=CxVec)
        self.register(name='voltage_C', tpe=CxVec)

        self.register(name='Sf_A', tpe=CxVec)
        self.register(name='Sf_B', tpe=CxVec)
        self.register(name='Sf_C', tpe=CxVec)

        self.register(name='St_A', tpe=CxVec)
        self.register(name='St_B', tpe=CxVec)
        self.register(name='St_C', tpe=CxVec)

        self.register(name='If_A', tpe=CxVec)
        self.register(name='If_B', tpe=CxVec)
        self.register(name='If_C', tpe=CxVec)

        self.register(name='It_A', tpe=CxVec)
        self.register(name='It_B', tpe=CxVec)
        self.register(name='It_C', tpe=CxVec)

        self.register(name='tap_module', tpe=Vec)
        self.register(name='tap_angle', tpe=Vec)

        self.register(name='Vbranch_A', tpe=CxVec)
        self.register(name='Vbranch_B', tpe=CxVec)
        self.register(name='Vbranch_C', tpe=CxVec)

        self.register(name='loading_A', tpe=CxVec)
        self.register(name='loading_B', tpe=CxVec)
        self.register(name='loading_C', tpe=CxVec)

        self.register(name='losses_A', tpe=CxVec)
        self.register(name='losses_B', tpe=CxVec)
        self.register(name='losses_C', tpe=CxVec)

        self.register(name='losses_hvdc', tpe=Vec)

        self.register(name='Pf_hvdc_A', tpe=Vec)
        self.register(name='Pf_hvdc_B', tpe=Vec)
        self.register(name='Pf_hvdc_C', tpe=Vec)

        self.register(name='Pt_hvdc_A', tpe=Vec)
        self.register(name='Pt_hvdc_B', tpe=Vec)
        self.register(name='Pt_hvdc_C', tpe=Vec)

        self.register(name='loading_hvdc', tpe=Vec)

        self.register(name='losses_vsc', tpe=Vec)

        self.register(name='Pf_vsc', tpe=Vec)

        self.register(name='St_vsc_A', tpe=CxVec)
        self.register(name='St_vsc_B', tpe=CxVec)
        self.register(name='St_vsc_C', tpe=CxVec)

        self.register(name='If_vsc', tpe=Vec)

        self.register(name='It_vsc_A', tpe=CxVec)
        self.register(name='It_vsc_B', tpe=CxVec)
        self.register(name='It_vsc_C', tpe=CxVec)

        self.register(name='loading_vsc', tpe=Vec)

        self.register(name='gen_q_A', tpe=Vec)
        self.register(name='gen_q_B', tpe=Vec)
        self.register(name='gen_q_C', tpe=Vec)

        self.register(name='battery_q_A', tpe=Vec)
        self.register(name='battery_q_B', tpe=Vec)
        self.register(name='battery_q_C', tpe=Vec)

        self.register(name='shunt_q_A', tpe=Vec)
        self.register(name='shunt_q_B', tpe=Vec)
        self.register(name='shunt_q_C', tpe=Vec)

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
        ia, ib, ic = get_3p_indices(length_3p=len(results.V))
        ka, kb, kc = get_3p_indices(length_3p=len(results.Sf))
        vsc_a, vsc_b, vsc_c = get_3p_indices(length_3p=len(results.St_vsc))
        hvdc_a, hvdc_b, hvdc_c = get_3p_indices(length_3p=len(results.St_hvdc))

        self.voltage_A[b_idx] = results.V[ia]
        self.voltage_B[b_idx] = results.V[ib]
        self.voltage_C[b_idx] = results.V[ic]

        self.Sbus_A[b_idx] = results.Scalc[ia]
        self.Sbus_B[b_idx] = results.Scalc[ib]
        self.Sbus_C[b_idx] = results.Scalc[ic]

        # TODO: taps are 3-phase too
        # self.tap_module[br_idx] = results.tap_module
        # self.tap_angle[br_idx] = results.tap_angle

        self.Sf_A[br_idx] = results.Sf[ka]
        self.Sf_B[br_idx] = results.Sf[kb]
        self.Sf_C[br_idx] = results.Sf[kc]

        self.St_A[br_idx] = results.St[ka]
        self.St_B[br_idx] = results.St[kb]
        self.St_C[br_idx] = results.St[kc]

        self.If_A[br_idx] = results.If[ka]
        self.If_B[br_idx] = results.If[kb]
        self.If_C[br_idx] = results.If[kc]

        self.It_A[br_idx] = results.It[ka]
        self.It_B[br_idx] = results.It[kb]
        self.It_C[br_idx] = results.It[kc]

        # self.Vbranch[br_idx] = results.Vbranch
        self.loading_A[br_idx] = results.loading[ka]
        self.loading_B[br_idx] = results.loading[kb]
        self.loading_C[br_idx] = results.loading[kc]

        self.losses_A[br_idx] = results.losses[ka]
        self.losses_B[br_idx] = results.losses[kb]
        self.losses_C[br_idx] = results.losses[kc]

        # Hvdc
        self.Pf_hvdc_A[hvdc_idx] = results.Sf_hvdc.real[hvdc_a]
        self.Pf_hvdc_B[hvdc_idx] = results.Sf_hvdc.real[hvdc_b]
        self.Pf_hvdc_C[hvdc_idx] = results.Sf_hvdc.real[hvdc_c]

        self.Pt_hvdc_A[hvdc_idx] = results.St_hvdc.real[hvdc_a]
        self.Pt_hvdc_B[hvdc_idx] = results.St_hvdc.real[hvdc_b]
        self.Pt_hvdc_C[hvdc_idx] = results.St_hvdc.real[hvdc_c]

        self.losses_hvdc[hvdc_idx] = results.losses_hvdc.real
        self.loading_hvdc[hvdc_idx] = results.loading_hvdc.real

        # VSC
        self.Pf_vsc[vsc_idx] = results.Pf_vsc

        self.St_vsc_A[vsc_idx] = results.St_vsc[vsc_a]
        self.St_vsc_B[vsc_idx] = results.St_vsc[vsc_b]
        self.St_vsc_C[vsc_idx] = results.St_vsc[vsc_a]

        self.If_vsc[vsc_idx] = results.If_vsc

        self.It_vsc_A[vsc_idx] = results.It_vsc[vsc_a]
        self.It_vsc_B[vsc_idx] = results.It_vsc[vsc_b]
        self.It_vsc_C[vsc_idx] = results.It_vsc[vsc_a]

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

    def get_bus_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the buses results
        :return: DataFrame, Vm in p.u., Va in deg, P in MW, Q in MVAr
        """
        return pd.DataFrame(data={
            'VmA': np.abs(self.voltage_A),
            'VmB': np.abs(self.voltage_B),
            'VmC': np.abs(self.voltage_C),
            'VaA': np.angle(self.voltage_A, deg=True),
            'VaB': np.angle(self.voltage_B, deg=True),
            'VaC': np.angle(self.voltage_C, deg=True),
            'PA': self.Sbus_A.real,
            'PB': self.Sbus_B.real,
            'PC': self.Sbus_C.real,
            'QA': self.Sbus_A.imag,
            'QB': self.Sbus_B.imag,
            'QC': self.Sbus_C.imag,
        }, index=self.bus_names)

    def get_branch_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the branches results
        :return: DataFrame, Pf in MW, Qf in MVAr, Pt in MW, Qt in MVAr, loading in %, Ploss in MW, Qloss in MVAr
        """
        return pd.DataFrame(data={
            'PfA': self.Sf_A.real,
            'PfB': self.Sf_B.real,
            'PfC': self.Sf_C.real,

            'QfA': self.Sf_A.imag,
            'QfB': self.Sf_B.imag,
            'QfC': self.Sf_C.imag,

            'PtA': self.St_A.real,
            'PtB': self.St_B.real,
            'PtC': self.St_C.real,

            'QtA': self.St_A.imag,
            'QtB': self.St_B.imag,
            'QtC': self.St_C.imag,

            'loadingA': self.loading_C.real * 100.0,
            'loadingB': self.loading_B.real * 100.0,
            'loadingC': self.loading_A.real * 100.0,

            "PlossA": self.losses_A.real,
            "PlossB": self.losses_B.real,
            "PlossC": self.losses_C.real,

            "QlossA": self.losses_A.imag,
            "QlossB": self.losses_B.imag,
            "QlossC": self.losses_C.imag,
        }, index=self.branch_names)

    def get_voltage_3ph_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the buses results, Vm in p.u., Va in deg
        :return: DataFrame
        """
        df = pd.DataFrame(data={
            'Vm_A': np.abs(self.voltage_A).round(5),
            'Vm_B': np.abs(self.voltage_B).round(5),
            'Vm_C': np.abs(self.voltage_C).round(5),
            'Va_A': np.angle(self.voltage_A, deg=True).round(1),
            'Va_B': np.angle(self.voltage_B, deg=True).round(1),
            'Va_C': np.angle(self.voltage_C, deg=True).round(1)
        }, index=self.bus_names)

        return df

    def export_all(self):
        """
        Exports all the results to DataFrames.

        Returns:

            Bus results, Branch results
        """

        # buses results
        df_bus = self.get_bus_df()

        # branch results
        df_branch = self.get_branch_df()

        return df_bus, df_branch

    def compare(self, other: "PowerFlowResults3Ph", tol=1e-6) -> Tuple[bool, Logger]:
        """
        Compare this results with another
        :param other: PowerFlowResults
        :param tol: absolute comparison tolerance
        :return: all ok?, Logger
        """
        logger = Logger()
        all_ok = True
        for prop_name, prp in self.data_variables.items():

            if prp.tpe in [Vec, CxVec]:
                a = getattr(self, prop_name)
                b = getattr(other, prop_name)

                ok = np.allclose(a, b, atol=tol)

                if not ok:
                    logger.add_error(msg="Difference", device_property=prop_name)
                    all_ok = False

        return all_ok, logger

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        get the ResultsTable model
        :param result_type: ResultTypes
        :return: ResultsTable instance
        """

        if result_type == ResultTypes.BusVoltageModuleA:

            return ResultsTable(data=np.abs(self.voltage_A),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BusVoltageModuleB:

            return ResultsTable(data=np.abs(self.voltage_B),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BusVoltageModuleC:

            return ResultsTable(data=np.abs(self.voltage_C),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BusVoltageAngleA:

            return ResultsTable(data=np.angle(self.voltage_A, deg=True),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.BusVoltageAngleB:

            return ResultsTable(data=np.angle(self.voltage_B, deg=True),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.BusVoltageAngleC:

            return ResultsTable(data=np.angle(self.voltage_C, deg=True),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.BusVoltagePolarPlot:
            V = np.c_[self.voltage_A, self.voltage_B, self.voltage_C]
            vm = np.abs(V)
            va = np.angle(V, deg=True)
            va_rad = np.angle(V, deg=False)
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
                                columns=np.array(['Vm A', 'Vm B', 'Vm C', 'Va A (deg)', 'Va B (deg)', 'Va C (deg)']),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u., deg)',
                                units='(p.u., deg)')

        elif result_type == ResultTypes.BusActivePowerA:

            return ResultsTable(data=self.Sbus_A.real,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BusActivePowerB:

            return ResultsTable(data=self.Sbus_B.real,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BusActivePowerC:

            return ResultsTable(data=self.Sbus_C.real,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BusReactivePowerA:

            return ResultsTable(data=self.Sbus_A.imag,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BusReactivePowerB:

            return ResultsTable(data=self.Sbus_B.imag,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BusReactivePowerC:

            return ResultsTable(data=self.Sbus_C.imag,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActivePowerFromA:

            return ResultsTable(data=self.Sf_A.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchActivePowerFromB:

            return ResultsTable(data=self.Sf_B.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchActivePowerFromC:

            return ResultsTable(data=self.Sf_C.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactivePowerFromA:

            return ResultsTable(data=self.Sf_A.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchReactivePowerFromB:

            return ResultsTable(data=self.Sf_B.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchReactivePowerFromC:

            return ResultsTable(data=self.Sf_C.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')


        elif result_type == ResultTypes.BranchActivePowerToA:

            return ResultsTable(data=self.St_A.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchActivePowerToB:

            return ResultsTable(data=self.St_B.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchActivePowerToC:

            return ResultsTable(data=self.St_C.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactivePowerToA:

            return ResultsTable(data=self.St_A.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchReactivePowerToB:

            return ResultsTable(data=self.St_B.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchReactivePowerToC:

            return ResultsTable(data=self.St_C.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActiveCurrentFromA:

            return ResultsTable(data=self.If_A.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchActiveCurrentFromB:

            return ResultsTable(data=self.If_B.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchActiveCurrentFromC:

            return ResultsTable(data=self.If_C.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentFromA:

            return ResultsTable(data=self.If_A.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentFromB:

            return ResultsTable(data=self.If_B.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentFromC:

            return ResultsTable(data=self.If_C.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchActiveCurrentToA:

            return ResultsTable(data=self.It_A.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchActiveCurrentToB:

            return ResultsTable(data=self.It_B.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchActiveCurrentToC:

            return ResultsTable(data=self.It_C.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentToA:

            return ResultsTable(data=self.It_A.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentToB:

            return ResultsTable(data=self.It_B.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentToC:

            return ResultsTable(data=self.It_C.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchLoadingA:

            return ResultsTable(data=np.abs(self.loading_A) * 100,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchLoadingB:

            return ResultsTable(data=np.abs(self.loading_B) * 100,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchLoadingC:

            return ResultsTable(data=np.abs(self.loading_C) * 100,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchActiveLossesA:

            return ResultsTable(data=self.losses_A.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchActiveLossesB:

            return ResultsTable(data=self.losses_B.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchActiveLossesC:

            return ResultsTable(data=self.losses_C.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactiveLossesA:

            return ResultsTable(data=self.losses_A.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchReactiveLossesB:

            return ResultsTable(data=self.losses_B.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchReactiveLossesC:

            return ResultsTable(data=self.losses_C.imag,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActiveLossesPercentageA:

            return ResultsTable(data=np.abs(self.losses_A.real) / np.abs(self.Sf_A.real + 1e-20) * 100.0,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchActiveLossesPercentageB:

            return ResultsTable(data=np.abs(self.losses_B.real) / np.abs(self.Sf_B.real + 1e-20) * 100.0,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchActiveLossesPercentageC:

            return ResultsTable(data=np.abs(self.losses_C.real) / np.abs(self.Sf_C.real + 1e-20) * 100.0,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchVoltageA:

            return ResultsTable(data=np.abs(self.Vbranch_A),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchVoltageB:

            return ResultsTable(data=np.abs(self.Vbranch_B),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchVoltageC:

            return ResultsTable(data=np.abs(self.Vbranch_C),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchAnglesA:

            return ResultsTable(data=np.angle(self.Vbranch_A, deg=True),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.BranchAnglesB:

            return ResultsTable(data=np.angle(self.Vbranch_B, deg=True),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.BranchAnglesC:

            return ResultsTable(data=np.angle(self.Vbranch_C, deg=True),
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

        elif result_type == ResultTypes.HvdcPowerFromA:

            return ResultsTable(data=self.Pf_hvdc_A,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerFromB:

            return ResultsTable(data=self.Pf_hvdc_B,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerFromC:

            return ResultsTable(data=self.Pf_hvdc_C,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerToA:

            return ResultsTable(data=self.Pt_hvdc_A,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerToB:

            return ResultsTable(data=self.Pt_hvdc_B,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerToC:

            return ResultsTable(data=self.Pt_hvdc_C,
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

        elif result_type == ResultTypes.VscPowerToA:

            return ResultsTable(data=self.St_vsc_A.real,
                                index=self.vsc_names,
                                idx_device_type=DeviceType.VscDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.VscPowerToB:

            return ResultsTable(data=self.St_vsc_B.real,
                                index=self.vsc_names,
                                idx_device_type=DeviceType.VscDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.VscPowerToC:

            return ResultsTable(data=self.St_vsc_C.real,
                                index=self.vsc_names,
                                idx_device_type=DeviceType.VscDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.GeneratorReactivePowerA:

            return ResultsTable(data=self.gen_q_A,
                                index=self.gen_names,
                                idx_device_type=DeviceType.GeneratorDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.GeneratorReactivePowerB:

            return ResultsTable(data=self.gen_q_B,
                                index=self.gen_names,
                                idx_device_type=DeviceType.GeneratorDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.GeneratorReactivePowerC:

            return ResultsTable(data=self.gen_q_C,
                                index=self.gen_names,
                                idx_device_type=DeviceType.GeneratorDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BatteryReactivePowerA:

            return ResultsTable(data=self.battery_q_A,
                                index=self.batt_names,
                                idx_device_type=DeviceType.BatteryDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BatteryReactivePowerB:

            return ResultsTable(data=self.battery_q_B,
                                index=self.batt_names,
                                idx_device_type=DeviceType.BatteryDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BatteryReactivePowerC:

            return ResultsTable(data=self.battery_q_C,
                                index=self.batt_names,
                                idx_device_type=DeviceType.BatteryDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.ShuntReactivePowerA:

            return ResultsTable(data=self.shunt_q_A,
                                index=self.sh_names,
                                idx_device_type=DeviceType.ShuntLikeDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.ShuntReactivePowerB:

            return ResultsTable(data=self.shunt_q_B,
                                index=self.sh_names,
                                idx_device_type=DeviceType.ShuntLikeDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.ShuntReactivePower:

            return ResultsTable(data=self.shunt_q_C,
                                index=self.sh_names,
                                idx_device_type=DeviceType.ShuntLikeDevice,
                                columns=np.array([result_type.value]),
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        else:
            raise Exception('Unsupported result type: ' + str(result_type))

