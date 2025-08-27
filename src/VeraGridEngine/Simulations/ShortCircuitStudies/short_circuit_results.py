# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.enumerations import FaultType
from VeraGridEngine.basic_structures import IntVec, Vec, StrVec, CxVec
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import (expand_indices_3ph)


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

                                                              ResultTypes.BusVoltageModuleA,
                                                              ResultTypes.BusVoltageModuleB,
                                                              ResultTypes.BusVoltageModuleC,

                                                              ResultTypes.BusVoltageAngle0,
                                                              ResultTypes.BusVoltageAngle1,
                                                              ResultTypes.BusVoltageAngle2,

                                                              ResultTypes.BusVoltageAngleA,
                                                              ResultTypes.BusVoltageAngleB,
                                                              ResultTypes.BusVoltageAngleC,

                                                              ResultTypes.BusShortCircuitActivePower,
                                                              ResultTypes.BusShortCircuitActivePowerA,
                                                              ResultTypes.BusShortCircuitActivePowerB,
                                                              ResultTypes.BusShortCircuitActivePowerC,

                                                              ResultTypes.BusShortCircuitReactivePower,
                                                              ResultTypes.BusShortCircuitReactivePowerA,
                                                              ResultTypes.BusShortCircuitReactivePowerB,
                                                              ResultTypes.BusShortCircuitReactivePowerC,

                                                              ResultTypes.BusShortCircuitActiveCurrent,
                                                              ResultTypes.BusShortCircuitActiveCurrentA,
                                                              ResultTypes.BusShortCircuitActiveCurrentB,
                                                              ResultTypes.BusShortCircuitActiveCurrentC,

                                                              ResultTypes.BusShortCircuitReactiveCurrent,
                                                              ResultTypes.BusShortCircuitReactiveCurrentA,
                                                              ResultTypes.BusShortCircuitReactiveCurrentB,
                                                              ResultTypes.BusShortCircuitReactiveCurrentC
                                                              ],

                                     ResultTypes.BranchResults: [ResultTypes.BranchActivePowerFrom0,
                                                                 ResultTypes.BranchActivePowerFrom1,
                                                                 ResultTypes.BranchActivePowerFrom2,

                                                                 ResultTypes.BranchActivePowerFromA,
                                                                 ResultTypes.BranchActivePowerFromB,
                                                                 ResultTypes.BranchActivePowerFromC,

                                                                 ResultTypes.BranchReactivePowerFrom0,
                                                                 ResultTypes.BranchReactivePowerFrom1,
                                                                 ResultTypes.BranchReactivePowerFrom2,

                                                                 ResultTypes.BranchReactivePowerFromA,
                                                                 ResultTypes.BranchReactivePowerFromB,
                                                                 ResultTypes.BranchReactivePowerFromC,

                                                                 ResultTypes.BranchActiveCurrentFrom0,
                                                                 ResultTypes.BranchActiveCurrentFrom1,
                                                                 ResultTypes.BranchActiveCurrentFrom2,

                                                                 ResultTypes.BranchActiveCurrentFromA,
                                                                 ResultTypes.BranchActiveCurrentFromB,
                                                                 ResultTypes.BranchActiveCurrentFromC,

                                                                 ResultTypes.BranchReactiveCurrentFrom0,
                                                                 ResultTypes.BranchReactiveCurrentFrom1,
                                                                 ResultTypes.BranchReactiveCurrentFrom2,

                                                                 ResultTypes.BranchReactiveCurrentFromA,
                                                                 ResultTypes.BranchReactiveCurrentFromB,
                                                                 ResultTypes.BranchReactiveCurrentFromC,

                                                                 ResultTypes.BranchLoading0,
                                                                 ResultTypes.BranchLoading1,
                                                                 ResultTypes.BranchLoading2,

                                                                 ResultTypes.BranchLoadingA,
                                                                 ResultTypes.BranchLoadingB,
                                                                 ResultTypes.BranchLoadingC,

                                                                 ResultTypes.BranchActiveLosses0,
                                                                 ResultTypes.BranchActiveLosses1,
                                                                 ResultTypes.BranchActiveLosses2,

                                                                 ResultTypes.BranchActiveLossesA,
                                                                 ResultTypes.BranchActiveLossesB,
                                                                 ResultTypes.BranchActiveLossesC,

                                                                 ResultTypes.BranchReactiveLosses0,
                                                                 ResultTypes.BranchReactiveLosses1,
                                                                 ResultTypes.BranchReactiveLosses2,

                                                                 ResultTypes.BranchReactiveLossesA,
                                                                 ResultTypes.BranchReactiveLossesB,
                                                                 ResultTypes.BranchReactiveLossesC],

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

        self.SbusA = np.zeros(n, dtype=complex)
        self.voltageA = np.zeros(n, dtype=complex)
        self.SfA = np.zeros(m, dtype=complex)
        self.StA = np.zeros(m, dtype=complex)
        self.IfA = np.zeros(m, dtype=complex)
        self.ItA = np.zeros(m, dtype=complex)
        self.VbranchA = np.zeros(m, dtype=complex)
        self.loadingA = np.zeros(m, dtype=complex)
        self.lossesA = np.zeros(m, dtype=complex)

        self.SbusB = np.zeros(n, dtype=complex)
        self.voltageB = np.zeros(n, dtype=complex)
        self.SfB = np.zeros(m, dtype=complex)
        self.StB = np.zeros(m, dtype=complex)
        self.IfB = np.zeros(m, dtype=complex)
        self.ItB = np.zeros(m, dtype=complex)
        self.VbranchB = np.zeros(m, dtype=complex)
        self.loadingB = np.zeros(m, dtype=complex)
        self.lossesB = np.zeros(m, dtype=complex)

        self.SbusC = np.zeros(n, dtype=complex)
        self.voltageC = np.zeros(n, dtype=complex)
        self.SfC = np.zeros(m, dtype=complex)
        self.StC = np.zeros(m, dtype=complex)
        self.IfC = np.zeros(m, dtype=complex)
        self.ItC = np.zeros(m, dtype=complex)
        self.VbranchC = np.zeros(m, dtype=complex)
        self.loadingC = np.zeros(m, dtype=complex)
        self.lossesC = np.zeros(m, dtype=complex)

        self.hvdc_losses = np.zeros(n_hvdc)
        self.hvdc_Pf = np.zeros(n_hvdc)
        self.hvdc_Pt = np.zeros(n_hvdc)
        self.hvdc_loading = np.zeros(n_hvdc)

        self.sc_bus_index = 0
        self.sc_type = FaultType.ph3

        self.SCpower = np.zeros(n, dtype=complex)
        self.SCpowerA = np.zeros(n, dtype=complex)
        self.SCpowerB = np.zeros(n, dtype=complex)
        self.SCpowerC = np.zeros(n, dtype=complex)

        self.ICurrent = np.zeros(n, dtype=complex)
        self.ICurrentA = np.zeros(n, dtype=complex)
        self.ICurrentB = np.zeros(n, dtype=complex)
        self.ICurrentC = np.zeros(n, dtype=complex)

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

        self.register(name='SbusA', tpe=CxVec)
        self.register(name='voltageA', tpe=CxVec)
        self.register(name='SfA', tpe=CxVec)
        self.register(name='StA', tpe=CxVec)
        self.register(name='IfA', tpe=CxVec)
        self.register(name='ItA', tpe=CxVec)
        self.register(name='VbranchA', tpe=CxVec)
        self.register(name='loadingA', tpe=CxVec)
        self.register(name='lossesA', tpe=CxVec)

        self.register(name='SbusB', tpe=CxVec)
        self.register(name='voltageB', tpe=CxVec)
        self.register(name='SfB', tpe=CxVec)
        self.register(name='StB', tpe=CxVec)
        self.register(name='IfB', tpe=CxVec)
        self.register(name='ItB', tpe=CxVec)
        self.register(name='VbranchB', tpe=CxVec)
        self.register(name='loadingB', tpe=CxVec)
        self.register(name='lossesB', tpe=CxVec)

        self.register(name='SbusC', tpe=CxVec)
        self.register(name='voltageC', tpe=CxVec)
        self.register(name='SfC', tpe=CxVec)
        self.register(name='StC', tpe=CxVec)
        self.register(name='IfC', tpe=CxVec)
        self.register(name='ItC', tpe=CxVec)
        self.register(name='VbranchC', tpe=CxVec)
        self.register(name='loadingC', tpe=CxVec)
        self.register(name='lossesC', tpe=CxVec)

        self.register(name='hvdc_losses', tpe=Vec)
        self.register(name='hvdc_Pf', tpe=Vec)
        self.register(name='hvdc_Pt', tpe=Vec)
        self.register(name='hvdc_loading', tpe=Vec)

        self.register(name='sc_bus_index', tpe=int)
        self.register(name='sc_type', tpe=FaultType)

        self.register(name='SCpower', tpe=CxVec)
        self.register(name='SCpowerA', tpe=CxVec)
        self.register(name='SCpowerB', tpe=CxVec)
        self.register(name='SCpowerC', tpe=CxVec)

        self.register(name='ICurrent', tpe=CxVec)
        self.register(name='ICurrentA', tpe=CxVec)
        self.register(name='ICurrentB', tpe=CxVec)
        self.register(name='ICurrentC', tpe=CxVec)


    @property
    def elapsed(self):
        """
        Check if converged in all modes
        :return: True / False
        """
        val = 0.0
        return val

    def apply_from_island(self, results: "ShortCircuitResults", b_idx: IntVec, br_idx: IntVec):
        """
        Apply results from another island circuit to the circuit results represented
        here.

        Arguments:

            **results**: PowerFlowResults

            **b_idx**: bus original indices

            **elm_idx**: branch original indices
        """
        self.SCpower[b_idx] = results.SCpower
        self.ICurrent[b_idx] = results.ICurrent

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

        self.SbusA[b_idx] = results.SbusA
        self.voltageA[b_idx] = results.voltageA
        self.SfA[br_idx] = results.SfA
        self.StA[br_idx] = results.StA
        self.IfA[br_idx] = results.IfA
        self.ItA[br_idx] = results.ItA
        self.VbranchA[br_idx] = results.VbranchA
        self.loadingA[br_idx] = results.loadingA
        self.lossesA[br_idx] = results.lossesA

        self.SbusB[b_idx] = results.SbusB
        self.voltageB[b_idx] = results.voltageB
        self.SfB[br_idx] = results.SfB
        self.StB[br_idx] = results.StB
        self.IfB[br_idx] = results.IfB
        self.ItB[br_idx] = results.ItB
        self.VbranchB[br_idx] = results.VbranchB
        self.loadingB[br_idx] = results.loadingB
        self.lossesB[br_idx] = results.lossesB

        self.SbusC[b_idx] = results.SbusC
        self.voltageC[b_idx] = results.voltageC
        self.SfC[br_idx] = results.SfC
        self.StC[br_idx] = results.StC
        self.IfC[br_idx] = results.IfC
        self.ItC[br_idx] = results.ItC
        self.VbranchC[br_idx] = results.VbranchC
        self.loadingC[br_idx] = results.loadingC
        self.lossesC[br_idx] = results.lossesC

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """

        :param result_type:
        :return:
        """

        columns = np.array([result_type.value])
        title = result_type.value

        if result_type == ResultTypes.BusShortCircuitActivePower:
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

        elif result_type == ResultTypes.BusShortCircuitActivePowerA:
            labels = self.bus_names
            y = np.real(self.SCpowerA)
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitActivePowerB:
            labels = self.bus_names
            y = np.real(self.SCpowerB)
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitActivePowerC:
            labels = self.bus_names
            y = np.real(self.SCpowerC)
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

        elif result_type == ResultTypes.BusShortCircuitReactivePowerA:
            labels = self.bus_names
            y = np.imag(self.SCpowerA)
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitReactivePowerB:
            labels = self.bus_names
            y = np.imag(self.SCpowerB)
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitReactivePowerC:
            labels = self.bus_names
            y = np.imag(self.SCpowerC)
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitActiveCurrent:
            labels = self.bus_names
            y = np.real(self.ICurrent)
            y_label = '(kA)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitActiveCurrentA:
            labels = self.bus_names
            y = np.real(self.ICurrentA)
            y_label = '(kA)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitActiveCurrentB:
            labels = self.bus_names
            y = np.real(self.ICurrentB)
            y_label = '(kA)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitActiveCurrentC:
            labels = self.bus_names
            y = np.real(self.ICurrentC)
            y_label = '(kA)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitReactiveCurrent:
            labels = self.bus_names
            y = np.imag(self.ICurrent)
            y_label = '(kAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitReactiveCurrentA:
            labels = self.bus_names
            y = np.imag(self.ICurrentA)
            y_label = '(kAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitReactiveCurrentB:
            labels = self.bus_names
            y = np.imag(self.ICurrentB)
            y_label = '(kAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusShortCircuitReactiveCurrentC:
            labels = self.bus_names
            y = np.imag(self.ICurrentC)
            y_label = '(kAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageModule0:
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

        elif result_type == ResultTypes.BusVoltageModuleA:
            labels = self.bus_names
            y = np.abs(self.voltageA)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageAngleA:
            labels = self.bus_names
            y = np.angle(self.voltageA)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActivePowerFromA:
            labels = self.branch_names
            y = self.SfA.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactivePowerFromA:
            labels = self.branch_names
            y = self.SfA.imag
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveCurrentFromA:
            labels = self.branch_names
            y = self.IfA.real
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveCurrentFromA:
            labels = self.branch_names
            y = self.IfA.imag
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLoadingA:
            labels = self.branch_names
            y = self.loadingA.real * 100.0
            y_label = '(%)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveLossesA:
            labels = self.branch_names
            y = self.lossesA.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveLossesA:
            labels = self.branch_names
            y = self.lossesA.imag
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageModuleB:
            labels = self.bus_names
            y = np.abs(self.voltageB)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageAngleB:
            labels = self.bus_names
            y = np.angle(self.voltageB)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActivePowerFromB:
            labels = self.branch_names
            y = self.SfB.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactivePowerFromB:
            labels = self.branch_names
            y = self.SfB.imag
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveCurrentFromB:
            labels = self.branch_names
            y = self.IfB.real
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveCurrentFromB:
            labels = self.branch_names
            y = self.IfB.imag
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLoadingB:
            labels = self.branch_names
            y = self.loadingB.real * 100.0
            y_label = '(%)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveLossesB:
            labels = self.branch_names
            y = self.lossesB.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveLossesB:
            labels = self.branch_names
            y = self.lossesB.imag
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageModuleC:
            labels = self.bus_names
            y = np.abs(self.voltageC)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BusVoltageAngleC:
            labels = self.bus_names
            y = np.angle(self.voltageC)
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BusDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActivePowerFromC:
            labels = self.branch_names
            y = self.SfC.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactivePowerFromC:
            labels = self.branch_names
            y = self.SfC.imag
            y_label = '(MVAr)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveCurrentFromC:
            labels = self.branch_names
            y = self.IfC.real
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveCurrentFromC:
            labels = self.branch_names
            y = self.IfC.imag
            y_label = '(p.u.)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchLoadingC:
            labels = self.branch_names
            y = self.loadingC.real * 100.0
            y_label = '(%)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchActiveLossesC:
            labels = self.branch_names
            y = self.lossesC.real
            y_label = '(MW)'

            return ResultsTable(data=y,
                                index=labels,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=title,
                                ylabel=y_label,
                                units=y_label)

        elif result_type == ResultTypes.BranchReactiveLossesC:
            labels = self.branch_names
            y = self.lossesC.imag
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

    def get_voltage_3ph_df(self):
        # phase buses results
        # vm_a = np.abs(self.voltageA)
        # vm_b = np.abs(self.voltageB)
        # vm_c = np.abs(self.voltageC)
        # va_a = np.angle(self.voltageA)
        # va_b = np.angle(self.voltageB)
        # va_c = np.angle(self.voltageC)
        # phases_data = np.c_[vm_a, va_a*(180/np.pi), vm_b, va_b*(180/np.pi), vm_c, va_c*(180/np.pi)]
        # phases_cols = ['U_mod A [p.u.]',
        #                'U_ang A [º]',
        #                'U_mod B [p.u.]',
        #                'U_ang B [º]',
        #                'U_mod C [p.u.]',
        #                'U_ang C [º]',
        #                ]
        # df_phases = pd.DataFrame(data=phases_data, columns=phases_cols)

        return pd.DataFrame(data={'U_mod A [p.u.]': np.abs(self.voltageA),
                                  'U_ang A [º]': np.angle(self.voltageA, deg=True),
                                  'U_mod B [p.u.]': np.abs(self.voltageB),
                                  'U_ang B [º]': np.angle(self.voltageB, deg=True),
                                  'U_mod C [p.u.]': np.abs(self.voltageC),
                                  'U_ang C [º]': np.angle(self.voltageC, deg=True)},
                            index=self.bus_names)

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
