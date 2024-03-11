# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import json
import numpy as np
import pandas as pd
from typing import Union

from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.basic_structures import DateVec, IntVec, StrVec, CxMat, Mat
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType
from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults


class PowerFlowTimeSeriesResults(ResultsTemplate):

    def __init__(self,
                 n: int,
                 m: int,
                 n_hvdc: int,
                 bus_names: np.ndarray,
                 branch_names: np.ndarray,
                 hvdc_names: np.ndarray,
                 time_array: np.ndarray,
                 bus_types: np.ndarray,
                 area_names: Union[np.ndarray, None] = None,
                 clustering_results: Union[ClusteringResults, None] = None):
        """

        :param n:
        :param m:
        :param n_hvdc:
        :param bus_names:
        :param branch_names:
        :param hvdc_names:
        :param time_array:
        :param bus_types:
        :param area_names:
        :param clustering_results:
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
                                         ResultTypes.BranchBeq,

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
                                     ResultTypes.AreaResults: [
                                         ResultTypes.InterAreaExchange,
                                         ResultTypes.ActivePowerFlowPerArea,
                                         ResultTypes.LossesPerArea,
                                         ResultTypes.LossesPercentPerArea
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
        self.bus_types: IntVec = bus_types
        self.time_array = time_array
        self.bus_types = np.zeros(n, dtype=int)

        # vars for the inter-area computation
        self.F: IntVec = None
        self.T: IntVec = None
        self.hvdc_F: IntVec = None
        self.hvdc_T: IntVec = None
        self.bus_area_indices: IntVec = None
        self.area_names: StrVec = area_names

        nt = len(time_array)

        self.voltage = np.zeros((nt, n), dtype=complex)
        self.S = np.zeros((nt, n), dtype=complex)

        self.Sf = np.zeros((nt, m), dtype=complex)
        self.St = np.zeros((nt, m), dtype=complex)
        self.If: CxMat = np.zeros((nt, m), dtype=complex)
        self.It: CxMat = np.zeros((nt, m), dtype=complex)
        self.tap_module: Mat = np.zeros((nt, m), dtype=float)
        self.tap_angle: Mat = np.zeros((nt, m), dtype=float)
        self.Beq: Mat = np.zeros((nt, m), dtype=float)
        self.Vbranch = np.zeros((nt, m), dtype=complex)
        self.loading = np.zeros((nt, m), dtype=complex)
        self.losses = np.zeros((nt, m), dtype=complex)

        self.hvdc_losses = np.zeros((nt, n_hvdc))
        self.hvdc_Pf = np.zeros((nt, n_hvdc))
        self.hvdc_Pt = np.zeros((nt, n_hvdc))
        self.hvdc_loading = np.zeros((nt, n_hvdc))

        self.error_values = np.zeros(nt)
        self.converged_values = np.ones(nt, dtype=bool)  # guilty assumption

        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='hvdc_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)
        self.register(name='time_array', tpe=DateVec)

        self.register(name='F', tpe=IntVec)
        self.register(name='T', tpe=IntVec)
        self.register(name='hvdc_F', tpe=IntVec)
        self.register(name='hvdc_T', tpe=IntVec)
        self.register(name='bus_area_indices', tpe=IntVec)
        self.register(name='area_names', tpe=IntVec)

        self.register(name='S', tpe=CxMat)
        self.register(name='voltage', tpe=CxMat)

        self.register(name='Sf', tpe=CxMat)
        self.register(name='St', tpe=CxMat)
        self.register(name='If', tpe=CxMat)
        self.register(name='It', tpe=CxMat)
        self.register(name='tap_module', tpe=Mat)
        self.register(name='tap_angle', tpe=Mat)
        self.register(name='Beq', tpe=Mat)
        self.register(name='Vbranch', tpe=CxMat)
        self.register(name='loading', tpe=CxMat)
        self.register(name='losses', tpe=CxMat)

        self.register(name='hvdc_losses', tpe=Mat)
        self.register(name='hvdc_Pf', tpe=Mat)
        self.register(name='hvdc_Pt', tpe=Mat)
        self.register(name='hvdc_loading', tpe=Mat)

    def apply_new_time_series_rates(self, nc: NumericalCircuit):
        """
        Recompute the loading with new rates
        :param nc: NumericalCircuit instance
        """
        self.loading = self.Sf / (nc.rates + 1e-9)

    def fill_circuit_info(self, grid: MultiCircuit):
        """

        :param grid:
        :return:
        """
        area_dict = {elm: i for i, elm in enumerate(grid.get_areas())}
        bus_dict = grid.get_bus_index_dict()

        self.area_names = [a.name for a in grid.get_areas()]
        self.bus_area_indices = np.array([area_dict.get(b.area, 0) for b in grid.buses])

        branches = grid.get_branches_wo_hvdc()
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

    def set_at(self, t, results: PowerFlowResults):
        """
        Set the results at the step t
        @param t: time index
        @param results: PowerFlowResults instance
        """

        self.voltage[t, :] = results.voltage

        self.S[t, :] = results.Sbus

        self.Sf[t, :] = results.Sf
        self.St[t, :] = results.St

        self.Vbranch[t, :] = results.Vbranch

        self.loading[t, :] = results.loading

        self.losses[t, :] = results.losses

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

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return:  of 2D numpy arrays (probably of complex numbers)
        """
        data = {'Vm': np.abs(self.voltage).tolist(),
                'Va': np.angle(self.voltage).tolist(),
                'P': self.S.real.tolist(),
                'Q': self.S.imag.tolist(),
                'Sf_real': self.Sf.real.tolist(),
                'Sf_imag': self.Sf.imag.tolist(),
                'loading': np.abs(self.loading).tolist(),
                'losses_real': np.real(self.losses).tolist(),
                'losses_imag': np.imag(self.losses).tolist()}
        return data

    def to_json(self, fname):
        """
        Export as json
        """

        with open(fname, "w") as output_file:
            json_str = json.dumps(self.get_results_dict())
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

        elif result_type == ResultTypes.BranchBeq:

            return ResultsTable(data=self.Beq,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

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

        else:
            raise Exception('Result type not understood:' + str(result_type))
