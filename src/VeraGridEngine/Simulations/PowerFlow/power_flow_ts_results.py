# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import json
import numpy as np
import pandas as pd
from typing import Union

from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate, ResultsProperty
from VeraGridEngine.basic_structures import DateVec, IntVec, StrVec, CxMat, Mat, Vec, BoolVec
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType, ResultTablePlotType
from VeraGridEngine.Simulations.Clustering.clustering_results import ClusteringResults


class PowerFlowTimeSeriesResults(ResultsTemplate):

    LOCAL_RESULTS_DECLARATIONS = (
        ResultsProperty(name='bus_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='branch_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='hvdc_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='vsc_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='gen_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='batt_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='sh_names', tpe=StrVec, old_names=list(), expandable=False),
        ResultsProperty(name='bus_types', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='time_array', tpe=DateVec, old_names=list(), expandable=False),
        ResultsProperty(name='F', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='T', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='hvdc_F', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='hvdc_T', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='bus_area_indices', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='area_names', tpe=IntVec, old_names=list(), expandable=False),
        ResultsProperty(name='S', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='voltage', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='Sf', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='St', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='If', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='It', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='tap_module', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='tap_angle', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='Vbranch', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='loading', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='losses', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='hvdc_losses', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='hvdc_Pf', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='hvdc_Pt', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='hvdc_loading', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='losses_vsc', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='Pf_vsc', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='Pfn_vsc', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='St_vsc', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='If_vsc', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='It_vsc', tpe=CxMat, old_names=list(), expandable=True),
        ResultsProperty(name='loading_vsc', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='gen_p', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='gen_q', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='battery_p', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='battery_q', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='shunt_q', tpe=Mat, old_names=list(), expandable=True),
        ResultsProperty(name='error_values', tpe=Vec, old_names=list(), expandable=True),
        ResultsProperty(name='converged_values', tpe=BoolVec, old_names=list(), expandable=True),
    )

    __slots__ = (
        "bus_names",
        "branch_names",
        "hvdc_names",
        "vsc_names",
        "gen_names",
        "batt_names",
        "sh_names",
        "bus_types",
        "voltage",
        "S",
        "Sf",
        "St",
        "If",
        "It",
        "tap_module",
        "tap_angle",
        "Vbranch",
        "loading",
        "losses",
        "hvdc_losses",
        "hvdc_Pf",
        "hvdc_Pt",
        "hvdc_loading",
        "Pf_vsc",
        "Pfn_vsc",
        "St_vsc",
        "If_vsc",
        "It_vsc",
        "loading_vsc",
        "losses_vsc",
        "gen_p",
        "gen_q",
        "battery_p",
        "battery_q",
        "shunt_q",
        "error_values",
        "converged_values",
    )

    def __init__(self,
                 n: int,
                 m: int,
                 n_hvdc: int,
                 n_vsc: int,
                 bus_names: StrVec,
                 branch_names: StrVec,
                 hvdc_names: StrVec,
                 vsc_names: StrVec,
                 time_array: DateVec,
                 bus_types: IntVec,
                 n_gen: int,
                 n_batt: int,
                 n_sh: int,
                 gen_names: StrVec,
                 batt_names: StrVec,
                 sh_names: StrVec,
                 area_names: StrVec,
                 clustering_results: Union[ClusteringResults, None] = None):
        """

        :param n: Number of buses.
        :param m: Number of AC branches.
        :param n_hvdc: Number of HVDC devices.
        :param n_vsc: Number of VSC devices.
        :param bus_names: Bus-name vector.
        :param branch_names: Branch-name vector.
        :param hvdc_names: HVDC-name vector.
        :param vsc_names: VSC-name vector.
        :param time_array: Simulated time index.
        :param bus_types: Bus-type vector.
        :param n_gen: Number of generators.
        :param n_batt: Number of batteries.
        :param n_sh: Number of shunts.
        :param gen_names: Generator-name vector.
        :param batt_names: Battery-name vector.
        :param sh_names: Shunt-name vector.
        :param area_names: Area-name vector.
        :param clustering_results: Optional clustering metadata.
        """
        ResultsTemplate.__init__(self,
                                 name='Power flow time series',
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
                                         ResultTypes.HvdcLosses,
                                         ResultTypes.HvdcPowerFrom,
                                         ResultTypes.HvdcPowerTo
                                     ],
                                     ResultTypes.VscResults: [
                                         ResultTypes.VscPowerFromPositive,
                                         ResultTypes.VscPowerFromNegative,
                                         ResultTypes.VscPowerTo,
                                         ResultTypes.VscLosses
                                     ],
                                     ResultTypes.GeneratorResults: [
                                         ResultTypes.GeneratorPower,
                                         ResultTypes.GeneratorReactivePower
                                     ],
                                     ResultTypes.BatteryResults: [
                                         ResultTypes.BatteryPower,
                                         ResultTypes.BatteryReactivePower
                                     ],
                                     ResultTypes.ShuntResults: [
                                         ResultTypes.ShuntReactivePower
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
                                     ],
                                     ResultTypes.InfoResults: [
                                         ResultTypes.SimulationError
                                     ]
                                 },
                                 time_array=None,
                                 clustering_results=clustering_results,
                                 study_results_type=StudyResultsType.PowerFlowTimeSeries
                                 )

        self.bus_names: StrVec = bus_names
        self.branch_names: StrVec = branch_names
        self.hvdc_names: StrVec = hvdc_names
        self.vsc_names: StrVec = vsc_names
        self.gen_names: StrVec = gen_names
        self.batt_names: StrVec = batt_names
        self.sh_names: StrVec = sh_names
        self.bus_types: IntVec = np.array(bus_types, dtype=int)
        self.time_array = time_array

        # vars for the inter-area computation
        self.F: IntVec = None
        self.T: IntVec = None
        self.hvdc_F: IntVec = None
        self.hvdc_T: IntVec = None
        self.bus_area_indices: IntVec = None
        self.area_names: StrVec = area_names

        nt: int = len(time_array)

        self.voltage = np.zeros((nt, n), dtype=np.complex64)
        self.S = np.zeros((nt, n), dtype=np.complex64)

        self.Sf = np.zeros((nt, m), dtype=np.complex64)
        self.St = np.zeros((nt, m), dtype=np.complex64)
        self.If: CxMat = np.zeros((nt, m), dtype=np.complex64)
        self.It: CxMat = np.zeros((nt, m), dtype=np.complex64)
        self.tap_module: Mat = np.zeros((nt, m), dtype=np.float16)
        self.tap_angle: Mat = np.zeros((nt, m), dtype=np.float16)
        self.Vbranch = np.zeros((nt, m), dtype=np.complex64)
        self.loading = np.zeros((nt, m), dtype=np.complex64)
        self.losses = np.zeros((nt, m), dtype=np.complex64)

        # link flows in float32, like the branch flows: float16 resolves only ~1 MW at 2000 MW
        self.hvdc_losses = np.zeros((nt, n_hvdc), dtype=np.float16)
        self.hvdc_Pf = np.zeros((nt, n_hvdc), dtype=np.float32)
        self.hvdc_Pt = np.zeros((nt, n_hvdc), dtype=np.float32)
        self.hvdc_loading = np.zeros((nt, n_hvdc), dtype=np.float16)

        self.losses_vsc = np.zeros((nt, n_vsc), dtype=np.float16)
        self.Pf_vsc = np.zeros((nt, n_vsc), dtype=np.float32)
        self.Pfn_vsc = np.zeros((nt, n_vsc), dtype=np.float32)
        self.St_vsc = np.zeros((nt, n_vsc), dtype=np.complex64)
        self.If_vsc = np.zeros((nt, n_vsc), dtype=np.float16)
        self.It_vsc = np.zeros((nt, n_vsc), dtype=np.complex64)
        self.loading_vsc = np.zeros((nt, n_vsc), dtype=np.float16)

        self.gen_p = np.zeros((nt, n_gen), dtype=np.float16)
        self.gen_q = np.zeros((nt, n_gen), dtype=np.float16)
        self.battery_p = np.zeros((nt, n_batt), dtype=np.float16)
        self.battery_q = np.zeros((nt, n_batt), dtype=np.float16)
        self.shunt_q = np.zeros((nt, n_sh), dtype=np.float16)

        self.error_values = np.zeros(nt)
        self.converged_values = np.ones(nt, dtype=bool)  # guilty assumption


    def apply_new_time_series_rates(self, nc: NumericalCircuit) -> None:
        """
        Recompute the loading with new rates

        :param nc: NumericalCircuit instance.
        """
        self.loading = self.Sf / (nc.passive_branch_data.rates + 1e-9)

    def fill_circuit_info(self, grid: MultiCircuit) -> None:
        """

        :param grid:
        :return:
        """
        area_dict = {elm: i for i, elm in enumerate(grid.get_areas())}
        bus_dict = grid.get_bus_index_dict()

        self.area_names = [a.name for a in grid.get_areas()]
        self.bus_area_indices = np.array([area_dict.get(b.area, 0) for b in grid.buses])

        branches = grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)
        self.F = np.zeros(len(branches), dtype=int)
        self.T = np.zeros(len(branches), dtype=int)
        for k, elm in enumerate(branches):
            self.F[k] = bus_dict[elm.bus_from]
            self.T[k] = bus_dict[elm.bus_to]

        hvdc = grid.get_hvdc()
        self.hvdc_F = np.zeros(len(hvdc), dtype=int)
        self.hvdc_T = np.zeros(len(hvdc), dtype=int)
        for k, elm in enumerate(hvdc):
            self.hvdc_F[k] = bus_dict[elm.bus_from]
            self.hvdc_T[k] = bus_dict[elm.bus_to]

    def set_at(self, t: int, results: PowerFlowResults) -> None:
        """
        Store one snapshot power-flow solution into a time position.

        :param t: Time index.
        :param results: Snapshot power-flow results.
        """

        self.voltage[t, :] = results.voltage
        self.S[t, :] = results.Sbus
        self.Sf[t, :] = results.Sf
        self.St[t, :] = results.St
        self.If[t, :] = results.If
        self.It[t, :] = results.It
        self.tap_module[t, :] = results.tap_module
        self.tap_angle[t, :] = results.tap_angle
        self.Vbranch[t, :] = results.Vbranch
        self.loading[t, :] = results.loading
        self.losses[t, :] = results.losses
        self.hvdc_losses[t, :] = results.losses_hvdc
        self.hvdc_Pf[t, :] = results.Pf_hvdc
        self.hvdc_Pt[t, :] = results.Pt_hvdc
        self.hvdc_loading[t, :] = results.loading_hvdc
        self.losses_vsc[t, :] = results.losses_vsc
        self.Pf_vsc[t, :] = results.Pfp_vsc
        self.Pfn_vsc[t, :] = results.Pfn_vsc
        self.St_vsc[t, :] = results.St_vsc
        self.If_vsc[t, :] = results.If_vsc
        self.It_vsc[t, :] = results.It_vsc
        self.loading_vsc[t, :] = results.loading_vsc
        self.gen_p[t, :] = results.gen_p
        self.gen_q[t, :] = results.gen_q
        self.battery_p[t, :] = results.battery_p
        self.battery_q[t, :] = results.battery_q
        self.shunt_q[t, :] = results.shunt_q

        self.error_values[t] = results.error
        self.converged_values[t] = results.converged

    @staticmethod
    def merge_if(df, arr, ind, cols):
        """

        @param df:
        @param arr:
        @param ind:
        @param cols:
        @return:
        """
        obj = pd.DataFrame(data=arr, index=ind, columns=cols)
        if df is None:
            df = obj
        else:
            df = pd.concat([df, obj], axis=1)

        return df

    def to_json(self, fname):
        """
        Export as json
        """

        with open(fname, "w") as output_file:
            json_str = json.dumps(self.get_dict())
            output_file.write(json_str)

    def get_ordered_area_names(self):
        """

        :return:
        """
        na = len(self.area_names)
        x = [''] * (na * na)
        for i, a in enumerate(self.area_names):
            for j, b in enumerate(self.area_names):
                x[i * na + j] = f"{a} -> {b}"
        return x

    def get_inter_area_flows(self):
        """

        :return:
        """
        na = len(self.area_names)
        nt = len(self.time_array)
        x = np.zeros((nt, na * na), dtype=complex)

        for f, t, flow in zip(self.F, self.T, self.Sf.T):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            if a1 != a2:
                x[:, a1 * na + a2] += flow
                x[:, a2 * na + a1] -= flow

        for f, t, flow in zip(self.hvdc_F, self.hvdc_T, self.hvdc_Pf.T):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            if a1 != a2:
                x[:, a1 * na + a2] += flow
                x[:, a2 * na + a1] -= flow

        return x

    def get_branch_values_per_area(self, branch_values: Union[Mat, CxMat]) -> Union[Mat, CxMat]:
        """

        :param branch_values:
        :return:
        """
        na = len(self.area_names)
        nt = len(self.time_array)
        x = np.zeros((nt, na * na), dtype=branch_values.dtype)

        for f, t, val in zip(self.F, self.T, branch_values.T):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            x[:, a1 * na + a2] += val

        return x

    def get_hvdc_values_per_area(self, hvdc_values: np.ndarray):
        """

        :param hvdc_values:
        :return:
        """
        na = len(self.area_names)
        nt = len(self.time_array)
        x = np.zeros((nt, na * na), dtype=hvdc_values.dtype)

        for f, t, val in zip(self.hvdc_F, self.hvdc_T, hvdc_values.T):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            x[:, a1 * na + a2] += val

        return x

    def get_bus_values_per_area(self, bus_values: Union[Mat, CxMat]) -> Union[Mat, CxMat]:
        """
        Aggregate bus-related time-series values per area.

        :param bus_values: Time-series bus values with shape ``(nt, nbus)``.
        :return: Area-aggregated values with shape ``(nt, n_area)``.
        """
        na: int = len(self.area_names)
        nt: int = len(self.time_array)
        x = np.zeros((nt, na), dtype=bus_values.dtype)

        if na > 0:
            for bus_idx, area_idx in enumerate(self.bus_area_indices):
                x[:, area_idx] += bus_values[:, bus_idx]
        else:
            x = x

        return x

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """

        :param result_type:
        :return:
        """

        if result_type == ResultTypes.BusVoltageModule:

            return ResultsTable(data=np.abs(self.voltage),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BusVoltageAngle:

            return ResultsTable(data=np.angle(self.voltage, deg=True),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.BusVoltagePolarPlot:
            vm = np.abs(self.voltage)
            va = np.angle(self.voltage, deg=True)
            module_columns: list[str] = list()
            angle_columns: list[str] = list()
            column_names: np.ndarray
            data: np.ndarray

            for bus_name in self.bus_names:
                module_columns.append(f"{bus_name} |V|")
                angle_columns.append(f"{bus_name} angle (deg)")

            column_names = np.array(module_columns + angle_columns)
            data = np.concatenate((vm, va), axis=1)


            return ResultsTable(data=data,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=column_names,
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u., deg)',
                                plot_type=ResultTablePlotType.POLAR,
                                units='(p.u., deg)')

        elif result_type == ResultTypes.BusActivePower:

            return ResultsTable(data=self.S.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BusReactivePower:

            return ResultsTable(data=self.S.imag,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActivePowerFrom:

            return ResultsTable(data=self.Sf.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactivePowerFrom:

            return ResultsTable(data=self.Sf.imag,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActivePowerTo:

            return ResultsTable(data=self.St.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactivePowerTo:

            return ResultsTable(data=self.St.imag,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActiveCurrentFrom:

            return ResultsTable(data=self.If.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentFrom:

            return ResultsTable(data=self.If.imag,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchActiveCurrentTo:

            return ResultsTable(data=self.It.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchReactiveCurrentTo:

            return ResultsTable(data=self.It.imag,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchTapModule:

            return ResultsTable(data=self.tap_module,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchTapAngle:

            return ResultsTable(data=np.rad2deg(self.tap_angle),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.BranchLoading:

            return ResultsTable(data=np.abs(self.loading) * 100,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchActiveLosses:

            return ResultsTable(data=self.losses.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactiveLosses:

            return ResultsTable(data=self.losses.imag,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActiveLossesPercentage:

            return ResultsTable(data=np.abs(self.losses.real) / np.abs(self.Sf.real + 1e-20) * 100.0,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.BranchVoltage:

            return ResultsTable(data=np.abs(self.Vbranch),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchAngles:

            return ResultsTable(data=np.angle(self.Vbranch, deg=True),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                units='(deg)')

        elif result_type == ResultTypes.SimulationError:

            return ResultsTable(data=self.error_values.reshape(-1, 1),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=['Error'],
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.HvdcLosses:

            return ResultsTable(data=self.hvdc_losses,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.hvdc_names,
                                cols_device_type=DeviceType.HVDCLineDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerFrom:

            return ResultsTable(data=self.hvdc_Pf,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.hvdc_names,
                                cols_device_type=DeviceType.HVDCLineDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerTo:

            return ResultsTable(data=self.hvdc_Pt,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.hvdc_names,
                                cols_device_type=DeviceType.HVDCLineDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.VscLosses:

            return ResultsTable(data=self.losses_vsc,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.vsc_names,
                                cols_device_type=DeviceType.VscDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.VscPowerFromPositive:

            return ResultsTable(data=self.Pf_vsc,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.vsc_names,
                                cols_device_type=DeviceType.VscDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.VscPowerFromNegative:

            return ResultsTable(data=self.Pfn_vsc,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.vsc_names,
                                cols_device_type=DeviceType.VscDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.VscPowerTo:

            return ResultsTable(data=self.St_vsc.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.vsc_names,
                                cols_device_type=DeviceType.VscDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.InterAreaExchange:

            return ResultsTable(data=self.get_inter_area_flows().real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.get_ordered_area_names(),
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.LossesPercentPerArea:
            Pf = (self.get_branch_values_per_area(np.abs(self.Sf.real))
                  + self.get_hvdc_values_per_area(np.abs(self.hvdc_Pf)))

            Pl = (self.get_branch_values_per_area(np.abs(self.losses.real))
                  + self.get_hvdc_values_per_area(np.abs(self.hvdc_losses)))

            data = Pl / (Pf + 1e-20) * 100.0

            return ResultsTable(data=data,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.get_ordered_area_names(),
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.LossesPerGenPerArea:
            gen_bus = self.S.real.copy()
            losses_per_area = (self.get_branch_values_per_area(np.abs(self.losses.real))
                               + self.get_hvdc_values_per_area(np.abs(self.hvdc_losses)))
            generation_per_area: np.ndarray
            data: np.ndarray
            na: int = len(self.area_names)
            area_idx: int
            diagonal_idx: int

            # Only positive injections contribute to local generation when building the ratio.
            gen_bus[gen_bus < 0] = 0
            generation_per_area = self.get_bus_values_per_area(gen_bus)
            data = np.zeros((len(self.time_array), na), dtype=losses_per_area.dtype)

            for area_idx, _ in enumerate(self.area_names):
                # The diagonal position contains the losses produced and absorbed inside the same area.
                diagonal_idx = area_idx * na + area_idx
                data[:, area_idx] = losses_per_area[:, diagonal_idx] / (generation_per_area[:, area_idx] + 1e-20) * 100.0

            return ResultsTable(data=data,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=np.array(self.area_names),
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        elif result_type == ResultTypes.LossesPerArea:

            data = (self.get_branch_values_per_area(np.abs(self.losses.real))
                    + self.get_hvdc_values_per_area(np.abs(self.hvdc_losses)))

            return ResultsTable(data=data,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.get_ordered_area_names(),
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.ActivePowerFlowPerArea:

            data = (self.get_branch_values_per_area(np.abs(self.Sf.real))
                    + self.get_hvdc_values_per_area(np.abs(self.hvdc_Pf)))

            return ResultsTable(data=data,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.get_ordered_area_names(),
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.GeneratorPower:

            return ResultsTable(data=self.gen_p,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.gen_names,
                                cols_device_type=DeviceType.GeneratorDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.GeneratorReactivePower:

            return ResultsTable(data=self.gen_q,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.gen_names,
                                cols_device_type=DeviceType.GeneratorDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.BatteryPower:

            return ResultsTable(data=self.battery_p,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.batt_names,
                                cols_device_type=DeviceType.BatteryDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BatteryReactivePower:

            return ResultsTable(data=self.battery_q,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.batt_names,
                                cols_device_type=DeviceType.BatteryDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        elif result_type == ResultTypes.ShuntReactivePower:

            return ResultsTable(data=self.shunt_q,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.sh_names,
                                cols_device_type=DeviceType.ShuntLikeDevice,
                                title=result_type.value,
                                ylabel='(MVAr)',
                                units='(MVAr)')

        else:
            raise Exception('Result type not understood:' + str(result_type))
