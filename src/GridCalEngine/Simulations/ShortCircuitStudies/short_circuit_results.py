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

import numpy as np
import pandas as pd
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.enumerations import FaultType
from GridCalEngine.basic_structures import IntVec, Vec, StrVec, CxVec
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class ShortCircuitResults(ResultsTemplate):

    def __init__(self, n, m, n_hvdc, bus_names, branch_names, hvdc_names, bus_types, area_names=None):
        """
        A **ShortCircuitResults** object is create as an attribute of the
        :ref:`ShortCircuitResults<pf_mp>` (as ShortCircuitResults.results) when the power flow is run. It
        provides access to the simulation results through its class attributes.
        :param n: number of nodes
        :param m: number of branches (without HVDC)
        :param n_hvdc: number of HVDC lines
        :param bus_names: array of bus names
        :param branch_names: array of branch names
        :param hvdc_names: array of HVDC names
        :param bus_types: array of bus types
        """

        ResultsTemplate.__init__(self,
                                 name='Short circuit',
                                 available_results={
                                     ResultTypes.BusResults: [ResultTypes.BusVoltageModule0,
                                                              ResultTypes.BusVoltageModule1,
                                                              ResultTypes.BusVoltageModule2,

                                                              ResultTypes.BusVoltageAngle0,
                                                              ResultTypes.BusVoltageAngle1,
                                                              ResultTypes.BusVoltageAngle2,

                                                              ResultTypes.BusShortCircuitActivePower,
                                                              ResultTypes.BusShortCircuitReactivePower],

                                     ResultTypes.BranchResults: [ResultTypes.BranchActivePowerFrom0,
                                                                 ResultTypes.BranchActivePowerFrom1,
                                                                 ResultTypes.BranchActivePowerFrom2,

                                                                 ResultTypes.BranchReactivePowerFrom0,
                                                                 ResultTypes.BranchReactivePowerFrom1,
                                                                 ResultTypes.BranchReactivePowerFrom2,

                                                                 ResultTypes.BranchActiveCurrentFrom0,
                                                                 ResultTypes.BranchActiveCurrentFrom1,
                                                                 ResultTypes.BranchActiveCurrentFrom2,

                                                                 ResultTypes.BranchReactiveCurrentFrom0,
                                                                 ResultTypes.BranchReactiveCurrentFrom1,
                                                                 ResultTypes.BranchReactiveCurrentFrom2,

                                                                 ResultTypes.BranchLoading0,
                                                                 ResultTypes.BranchLoading1,
                                                                 ResultTypes.BranchLoading2,

                                                                 ResultTypes.BranchActiveLosses0,
                                                                 ResultTypes.BranchActiveLosses1,
                                                                 ResultTypes.BranchActiveLosses2,

                                                                 ResultTypes.BranchReactiveLosses0,
                                                                 ResultTypes.BranchReactiveLosses1,
                                                                 ResultTypes.BranchReactiveLosses2],

                                     ResultTypes.InfoResults: [ResultTypes.ShortCircuitInfo],
                                 },
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.ShortCircuit
                                 )

        self.bus_types = bus_types
        self.bus_names = bus_names
        self.branch_names = branch_names
        self.hvdc_names = hvdc_names

        # vars for the inter-area computation
        self.F = np.zeros(m, dtype=int)
        self.T = np.zeros(m, dtype=int)
        self.hvdc_F = np.zeros(n_hvdc, dtype=int)
        self.hvdc_T = np.zeros(n_hvdc, dtype=int)
        self.bus_area_indices = np.zeros(n, dtype=int)
        self.area_names = area_names

        self.Sbus1 = np.zeros(n, dtype=complex)
        self.voltage1 = np.zeros(n, dtype=complex)
        self.Sf1 = np.zeros(m, dtype=complex)
        self.St1 = np.zeros(m, dtype=complex)
        self.If1 = np.zeros(m, dtype=complex)
        self.It1 = np.zeros(m, dtype=complex)
        self.Vbranch1 = np.zeros(m, dtype=complex)
        self.loading1 = np.zeros(m, dtype=complex)
        self.losses1 = np.zeros(m, dtype=complex)

        self.Sbus0 = np.zeros(n, dtype=complex)
        self.voltage0 = np.zeros(n, dtype=complex)
        self.Sf0 = np.zeros(m, dtype=complex)
        self.St0 = np.zeros(m, dtype=complex)
        self.If0 = np.zeros(m, dtype=complex)
        self.It0 = np.zeros(m, dtype=complex)
        self.Vbranch0 = np.zeros(m, dtype=complex)
        self.loading0 = np.zeros(m, dtype=complex)
        self.losses0 = np.zeros(m, dtype=complex)

        self.Sbus2 = np.zeros(n, dtype=complex)
        self.voltage2 = np.zeros(n, dtype=complex)
        self.Sf2 = np.zeros(m, dtype=complex)
        self.St2 = np.zeros(m, dtype=complex)
        self.If2 = np.zeros(m, dtype=complex)
        self.It2 = np.zeros(m, dtype=complex)
        self.Vbranch2 = np.zeros(m, dtype=complex)
        self.loading2 = np.zeros(m, dtype=complex)
        self.losses2 = np.zeros(m, dtype=complex)

        self.hvdc_losses = np.zeros(n_hvdc)
        self.hvdc_Pf = np.zeros(n_hvdc)
        self.hvdc_Pt = np.zeros(n_hvdc)
        self.hvdc_loading = np.zeros(n_hvdc)

        self.sc_bus_index = 0
        self.sc_type = FaultType.ph3
        self.SCpower = np.zeros(n, dtype=complex)

        # Register results
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='hvdc_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='F', tpe=IntVec)
        self.register(name='T', tpe=IntVec)
        self.register(name='hvdc_F', tpe=IntVec)
        self.register(name='hvdc_T', tpe=IntVec)
        self.register(name='bus_area_indices', tpe=IntVec)
        self.register(name='area_names', tpe=IntVec)

        self.register(name='Sbus1', tpe=CxVec)
        self.register(name='voltage1', tpe=CxVec)
        self.register(name='Sf1', tpe=CxVec)
        self.register(name='St1', tpe=CxVec)
        self.register(name='If1', tpe=CxVec)
        self.register(name='It1', tpe=CxVec)
        self.register(name='Vbranch1', tpe=CxVec)
        self.register(name='loading1', tpe=CxVec)
        self.register(name='losses1', tpe=CxVec)

        self.register(name='Sbus0', tpe=CxVec)
        self.register(name='voltage0', tpe=CxVec)
        self.register(name='Sf0', tpe=CxVec)
        self.register(name='St0', tpe=CxVec)
        self.register(name='If0', tpe=CxVec)
        self.register(name='It0', tpe=CxVec)
        self.register(name='Vbranch0', tpe=CxVec)
        self.register(name='loading0', tpe=CxVec)
        self.register(name='losses0', tpe=CxVec)

        self.register(name='Sbus2', tpe=CxVec)
        self.register(name='voltage2', tpe=CxVec)
        self.register(name='Sf2', tpe=CxVec)
        self.register(name='St2', tpe=CxVec)
        self.register(name='If2', tpe=CxVec)
        self.register(name='It2', tpe=CxVec)
        self.register(name='Vbranch2', tpe=CxVec)
        self.register(name='loading2', tpe=CxVec)
        self.register(name='losses2', tpe=CxVec)

        self.register(name='hvdc_losses', tpe=Vec)
        self.register(name='hvdc_Pf', tpe=Vec)
        self.register(name='hvdc_Pt', tpe=Vec)
        self.register(name='hvdc_loading', tpe=Vec)

        self.register(name='sc_bus_index', tpe=int)
        self.register(name='sc_type', tpe=FaultType)
        self.register(name='SCpower', tpe=CxVec)


    @property
    def elapsed(self):
        """
        Check if converged in all modes
        :return: True / False
        """
        val = 0.0
        return val

    def apply_from_island(self, results: "ShortCircuitResults", b_idx, br_idx):
        """
        Apply results from another island circuit to the circuit results represented
        here.

        Arguments:

            **results**: PowerFlowResults

            **b_idx**: bus original indices

            **elm_idx**: branch original indices
        """
        self.SCpower[b_idx] = results.SCpower

        self.Sbus1[b_idx] = results.Sbus1
        self.voltage1[b_idx] = results.voltage1
        self.Sf1[br_idx] = results.Sf1
        self.St1[br_idx] = results.St1
        self.If1[br_idx] = results.If1
        self.It1[br_idx] = results.It1
        self.Vbranch1[br_idx] = results.Vbranch1
        self.loading1[br_idx] = results.loading1
        self.losses1[br_idx] = results.losses1

        self.Sbus0[b_idx] = results.Sbus0
        self.voltage0[b_idx] = results.voltage0
        self.Sf0[br_idx] = results.Sf0
        self.St0[br_idx] = results.St0
        self.If0[br_idx] = results.If0
        self.It0[br_idx] = results.It0
        self.Vbranch0[br_idx] = results.Vbranch0
        self.loading0[br_idx] = results.loading0
        self.losses0[br_idx] = results.losses0

        self.Sbus2[b_idx] = results.Sbus2
        self.voltage2[b_idx] = results.voltage2
        self.Sf2[br_idx] = results.Sf2
        self.St2[br_idx] = results.St2
        self.If2[br_idx] = results.If2
        self.It2[br_idx] = results.It2
        self.Vbranch2[br_idx] = results.Vbranch2
        self.loading2[br_idx] = results.loading2
        self.losses2[br_idx] = results.losses2

    def get_inter_area_sequence_flows(self, sequence: int = 1):
        """
        Get the inter are flows per sequence
        :param sequence: Sequence number 0, 1, 2
        :return:
        """
        assert sequence in [0, 1, 2]
        na = len(self.area_names)
        x = np.zeros((na, na), dtype=complex)

        if sequence == 0:
            Sf = self.Sf0
        elif sequence == 1:
            Sf = self.Sf1
        elif sequence == 2:
            Sf = self.Sf2
        else:
            Sf = self.Sf1

        for f, t, flow in zip(self.F, self.T, Sf):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            if a1 != a2:
                x[a1, a2] += flow
                x[a2, a1] -= flow

        for f, t, flow in zip(self.hvdc_F, self.hvdc_T, self.hvdc_Pf):
            a1 = self.bus_area_indices[f]
            a2 = self.bus_area_indices[t]
            if a1 != a2:
                x[a1, a2] += flow
                x[a2, a1] -= flow

        return x

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """

        :param result_type:
        :return:
        """

        columns = [result_type.value]
        title = result_type.value

        if result_type == ResultTypes.BusVoltageModule0:
            labels = self.bus_names
            y = np.abs(self.voltage0)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageAngle0:
            labels = self.bus_names
            y = np.angle(self.voltage0)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitActivePower:
            labels = self.bus_names
            y = np.real(self.SCpower)
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitReactivePower:
            labels = self.bus_names
            y = np.imag(self.SCpower)
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActivePowerFrom0:
            labels = self.branch_names
            y = self.Sf0.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactivePowerFrom0:
            labels = self.branch_names
            y = self.Sf0.imag
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveCurrentFrom0:
            labels = self.branch_names
            y = self.If0.real
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveCurrentFrom0:
            labels = self.branch_names
            y = self.If0.imag
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLoading0:
            labels = self.branch_names
            y = self.loading0.real * 100.0
            y_label = '(%)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveLosses0:
            labels = self.branch_names
            y = self.losses0.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveLosses0:
            labels = self.branch_names
            y = self.losses0.imag
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageModule1:
            labels = self.bus_names
            y = np.abs(self.voltage1)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageAngle1:
            labels = self.bus_names
            y = np.angle(self.voltage1)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActivePowerFrom1:
            labels = self.branch_names
            y = self.Sf1.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactivePowerFrom1:
            labels = self.branch_names
            y = self.Sf1.imag
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveCurrentFrom1:
            labels = self.branch_names
            y = self.If1.real
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveCurrentFrom1:
            labels = self.branch_names
            y = self.If1.imag
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLoading1:
            labels = self.branch_names
            y = self.loading1.real * 100.0
            y_label = '(%)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveLosses1:
            labels = self.branch_names
            y = self.losses1.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveLosses1:
            labels = self.branch_names
            y = self.losses1.imag
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageModule2:
            labels = self.bus_names
            y = np.abs(self.voltage2)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageAngle2:
            labels = self.bus_names
            y = np.angle(self.voltage2)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActivePowerFrom2:
            labels = self.branch_names
            y = self.Sf2.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactivePowerFrom2:
            labels = self.branch_names
            y = self.Sf2.imag
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveCurrentFrom2:
            labels = self.branch_names
            y = self.If2.real
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveCurrentFrom2:
            labels = self.branch_names
            y = self.If2.imag
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLoading2:
            labels = self.branch_names
            y = self.loading2.real * 100.0
            y_label = '(%)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveLosses2:
            labels = self.branch_names
            y = self.losses2.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveLosses2:
            labels = self.branch_names
            y = self.losses2.imag
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.ShortCircuitInfo:
            labels = np.array(['Type', 'Bus name'])
            y = np.array([self.sc_type.value, self.bus_names[self.sc_bus_index]])
            y_label = ''

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        else:
            raise Exception('Unsupported result type: ' + str(result_type))

    def export_all(self):
        """
        Exports all the results to DataFrames.

        Returns:

            Bus results, Branch reuslts
        """

        # buses results
        vm = np.abs(self.voltage1)
        va = np.angle(self.voltage1)
        vr = self.voltage1.real
        vi = self.voltage1.imag
        bus_data = np.c_[vr, vi, vm, va]
        bus_cols = ['Real voltage (p.u.)',
                    'Imag Voltage (p.u.)',
                    'Voltage module (p.u.)',
                    'Voltage angle (rad)']
        df_bus = pd.DataFrame(data=bus_data, columns=bus_cols)

        # branch results
        sr = self.Sf1.real
        si = self.Sf1.imag
        sm = np.abs(self.Sf1)
        ld = np.abs(self.loading1)
        la = self.losses1.real
        lr = self.losses1.imag
        ls = np.abs(self.losses1)

        branch_data = np.c_[sr, si, sm, ld, la, lr, ls]
        branch_cols = ['Real power (MW)',
                       'Imag power (MVAr)',
                       'Power module (MVA)',
                       'Loading(%)',
                       'Losses (MW)',
                       'Losses (MVAr)',
                       'Losses (MVA)']
        df_branch = pd.DataFrame(data=branch_data, columns=branch_cols)

        return df_bus, df_branch
