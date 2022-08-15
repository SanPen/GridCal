# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

from xmlrpc.client import Fault
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import inv
from cmath import rect

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.ShortCircuitStudies.short_circuit import short_circuit_3p, short_circuit_unbalance
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults, PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import power_flow_post_process
from GridCal.Engine.Simulations.ShortCircuitStudies.short_circuit_worker import short_circuit_post_process
from GridCal.Engine.Core.snapshot_pf_data import SnapshotData
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Devices import Branch, Bus
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Core.admittance_matrices import compute_admittances
from GridCal.Engine.Devices.enumerations import FaultType

########################################################################################################################
# Short circuit classes
########################################################################################################################


class ShortCircuitOptions:

    def __init__(self, bus_index=None, fault_type=FaultType.ph3, branch_index=None, branch_fault_locations=None, 
                 branch_fault_impedance=None, branch_impedance_tolerance_mode=BranchImpedanceMode.Specified, verbose=False):
        """

        :param bus_index:
        :param fault_type: fault type among 3x, LG, LL and LLG possibilities
        :param branch_index:
        :param branch_fault_locations:
        :param branch_fault_impedance:
        :param branch_impedance_tolerance_mode:
        :param verbose:
        """

        if branch_index is not None:
            assert (len(branch_fault_locations) == len(branch_index))
            assert (len(branch_fault_impedance) == len(branch_index))

        if bus_index is None:
            self.bus_index = list()
        else:
            self.bus_index = bus_index

        self.fault_type = fault_type

        if branch_index is None:
            self.branch_index = list()
        else:
            self.branch_index = branch_index

        if branch_fault_locations is None:
            self.branch_fault_locations = list()
        else:
            self.branch_fault_locations = branch_fault_locations

        if branch_fault_impedance is None:
            self.branch_fault_impedance = list()
        else:
            self.branch_fault_impedance = branch_fault_impedance

        self.branch_impedance_tolerance_mode = branch_impedance_tolerance_mode

        self.verbose = verbose


class ShortCircuitResults_old(PowerFlowResults):

    def __init__(self, n, m, n_tr, bus_names, branch_names, transformer_names, bus_types):
        """

        :param n:
        :param m:
        :param n_tr:
        :param bus_names:
        :param branch_names:
        :param transformer_names:
        :param bus_types:
        """
        PowerFlowResults.__init__(self,
                                  n=n,
                                  m=m,
                                  n_tr=n_tr,
                                  n_hvdc=0,
                                  bus_names=bus_names,
                                  branch_names=branch_names,
                                  transformer_names=transformer_names,
                                  hvdc_names=(),
                                  bus_types=bus_types)

        self.name = 'Short circuit'

        self.short_circuit_power = None

        self.available_results = [ResultTypes.BusVoltageModule,
                                  ResultTypes.BusVoltageAngle,
                                  ResultTypes.BranchActivePowerFrom,
                                  ResultTypes.BranchReactivePowerFrom,
                                  ResultTypes.BranchActiveCurrentFrom,
                                  ResultTypes.BranchReactiveCurrentFrom,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchActiveLosses,
                                  ResultTypes.BranchReactiveLosses]

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        elm = super().copy()
        elm.short_circuit_power = self.short_circuit_power
        return elm

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = np.zeros(n, dtype=complex)

        self.voltage = np.zeros(n, dtype=complex)

        self.short_circuit_power = np.zeros(n, dtype=complex)

        self.Sf = np.zeros(m, dtype=complex)

        self.If = np.zeros(m, dtype=complex)

        self.loading = np.zeros(m, dtype=complex)

        self.losses = np.zeros(m, dtype=complex)

    def apply_from_island(self, results: "ShortCircuitResults", b_idx, br_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        @param results: PowerFlowResults
        @param b_idx: bus original indices
        @param br_idx: branch original indices
        @return:
        """
        self.Sbus[b_idx] = results.Sbus

        self.voltage[b_idx] = results.voltage

        self.short_circuit_power[b_idx] = results.short_circuit_power

        self.Sf[br_idx] = results.Sf

        self.If[br_idx] = results.If

        self.loading[br_idx] = results.loading

        self.losses[br_idx] = results.losses


class ShortCircuitResults(ResultsTemplate):

    def __init__(self, n, m, n_tr, n_hvdc, bus_names, branch_names, transformer_names, hvdc_names, bus_types,
                 area_names=None):
        """
        A **ShortCircuitResults** object is create as an attribute of the
        :ref:`ShortCircuitResults<pf_mp>` (as ShortCircuitResults.results) when the power flow is run. It
        provides access to the simulation results through its class attributes.
        :param n:
        :param m:
        :param n_tr:
        :param n_hvdc:
        :param bus_names:
        :param branch_names:
        :param transformer_names:
        :param hvdc_names:
        :param bus_types:
        """

        ResultsTemplate.__init__(self,
                                 name='Short circuit',
                                 available_results=[ResultTypes.BusVoltageModule0,
                                                    ResultTypes.BusVoltageModule1,
                                                    ResultTypes.BusVoltageModule2,

                                                    ResultTypes.BusVoltageAngle0,
                                                    ResultTypes.BusVoltageAngle1,
                                                    ResultTypes.BusVoltageAngle2,

                                                    ResultTypes.BranchActivePowerFrom0,
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
                                                    ResultTypes.BranchReactiveLosses2,
                                                    ],
                                 data_variables=['bus_types',
                                                 'bus_names',
                                                 'branch_names',
                                                 'transformer_names',
                                                 'hvdc_names',
                                                 'Sbus',
                                                 'voltage',
                                                 'Sf',
                                                 'St',
                                                 'If',
                                                 'It',
                                                 'ma',
                                                 'theta',
                                                 'Beq',
                                                 'Vbranch',
                                                 'loading',
                                                 'transformer_tap_module',
                                                 'losses',
                                                 'hvdc_losses',
                                                 'hvdc_Pf',
                                                 'hvdc_Pt',
                                                 'hvdc_loading']
                                 )

        self.n = n
        self.m = m
        self.n_tr = n_tr
        self.n_hvdc = n_hvdc

        self.bus_types = bus_types

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.transformer_names = transformer_names
        self.hvdc_names = hvdc_names

        # vars for the inter-area computation
        self.F = None
        self.T = None
        self.hvdc_F = None
        self.hvdc_T = None
        self.bus_area_indices = None
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

        self.hvdc_losses = np.zeros(self.n_hvdc)
        self.hvdc_Pf = np.zeros(self.n_hvdc)
        self.hvdc_Pt = np.zeros(self.n_hvdc)
        self.hvdc_loading = np.zeros(self.n_hvdc)

    @property
    def elapsed(self):
        """
        Check if converged in all modes
        :return: True / False
        """
        val = 0.0
        return val

    def apply_from_island(self, results: "ShortCircuitResults", b_idx, br_idx, tr_idx):
        """
        Apply results from another island circuit to the circuit results represented
        here.

        Arguments:

            **results**: PowerFlowResults

            **b_idx**: bus original indices

            **elm_idx**: branch original indices
        """
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

    def get_inter_area_flows(self, sequence=1):

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

    def mdl(self, result_type: ResultTypes) -> "ResultsTable":
        """

        :param result_type:
        :return:
        """

        columns = [result_type.value[0]]
        title = result_type.value[0]

        if result_type == ResultTypes.BusVoltageModule0:
            labels = self.bus_names
            y = np.abs(self.voltage0)
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BusVoltageAngle0:
            labels = self.bus_names
            y = np.angle(self.voltage0)
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BranchActivePowerFrom0:
            labels = self.branch_names
            y = self.Sf0.real
            y_label = '(MW)'
            
        elif result_type == ResultTypes.BranchReactivePowerFrom0:
            labels = self.branch_names
            y = self.Sf0.imag
            y_label = '(MVAr)'
            
        elif result_type == ResultTypes.BranchActiveCurrentFrom0:
            labels = self.branch_names
            y = self.If0.real
            y_label = '(p.u.)'
            
        elif result_type == ResultTypes.BranchReactiveCurrentFrom0:
            labels = self.branch_names
            y = self.If0.imag
            y_label = '(p.u.)'
            
        elif result_type == ResultTypes.BranchLoading0:
            labels = self.branch_names
            y = self.loading0.real
            y_label = '(%)'
            
        elif result_type == ResultTypes.BranchActiveLosses0:
            labels = self.branch_names
            y = self.losses0.real
            y_label = '(MW)'
            
        elif result_type == ResultTypes.BranchReactiveLosses0:
            labels = self.branch_names
            y = self.losses0.imag
            y_label = '(MW)'

        elif result_type == ResultTypes.BusVoltageModule1:
            labels = self.bus_names
            y = np.abs(self.voltage1)
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BusVoltageAngle1:
            labels = self.bus_names
            y = np.angle(self.voltage1)
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BranchActivePowerFrom1:
            labels = self.branch_names
            y = self.Sf1.real
            y_label = '(MW)'

        elif result_type == ResultTypes.BranchReactivePowerFrom1:
            labels = self.branch_names
            y = self.Sf1.imag
            y_label = '(MVAr)'

        elif result_type == ResultTypes.BranchActiveCurrentFrom1:
            labels = self.branch_names
            y = self.If1.real
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BranchReactiveCurrentFrom1:
            labels = self.branch_names
            y = self.If1.imag
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BranchLoading1:
            labels = self.branch_names
            y = self.loading1.real
            y_label = '(%)'

        elif result_type == ResultTypes.BranchActiveLosses1:
            labels = self.branch_names
            y = self.losses1.real
            y_label = '(MW)'

        elif result_type == ResultTypes.BranchReactiveLosses1:
            labels = self.branch_names
            y = self.losses1.imag
            y_label = '(MW)'

        elif result_type == ResultTypes.BusVoltageModule2:
            labels = self.bus_names
            y = np.abs(self.voltage2)
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BusVoltageAngle2:
            labels = self.bus_names
            y = np.angle(self.voltage2)
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BranchActivePowerFrom2:
            labels = self.branch_names
            y = self.Sf2.real
            y_label = '(MW)'

        elif result_type == ResultTypes.BranchReactivePowerFrom2:
            labels = self.branch_names
            y = self.Sf2.imag
            y_label = '(MVAr)'

        elif result_type == ResultTypes.BranchActiveCurrentFrom2:
            labels = self.branch_names
            y = self.If2.real
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BranchReactiveCurrentFrom2:
            labels = self.branch_names
            y = self.If2.imag
            y_label = '(p.u.)'

        elif result_type == ResultTypes.BranchLoading2:
            labels = self.branch_names
            y = self.loading2.real
            y_label = '(%)'

        elif result_type == ResultTypes.BranchActiveLosses2:
            labels = self.branch_names
            y = self.losses2.real
            y_label = '(MW)'

        elif result_type == ResultTypes.BranchReactiveLosses2:
            labels = self.branch_names
            y = self.losses2.imag
            y_label = '(MW)'

        else:
            raise Exception('Unsupported result type: ' + str(result_type))

        # assemble model
        mdl = ResultsTable(data=y, index=labels, columns=columns,
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
        if self.transformer_tap_module.size == 0:
            tm = [np.nan] * sr.size
        else:
            tm = self.transformer_tap_module

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



class ShortCircuitDriver(DriverTemplate):
    name = 'Short Circuit'
    tpe = SimulationTypes.ShortCircuit_run

    def __init__(self, grid: MultiCircuit, options: ShortCircuitOptions, pf_options: PowerFlowOptions,
                 pf_results: PowerFlowResults, opf_results=None):
        """
        PowerFlowDriver class constructor
        @param grid: MultiCircuit Object
        """
        DriverTemplate.__init__(self, grid=grid)

        # power flow results
        self.pf_results = pf_results

        self.pf_options = pf_options

        self.opf_results = opf_results

        # Options to use
        self.options = options

        self.results = None

        self.logger = Logger()

        self.__cancel__ = False

        self._is_running = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return list()

    @staticmethod
    def compile_zf(grid):

        # compile the buses short circuit impedance array
        n = len(grid.buses)
        Zf = np.zeros(n, dtype=complex)
        for i in range(n):
            Zf[i] = grid.buses[i].get_fault_impedance()

        return Zf

    @staticmethod
    def split_branch(branch: Branch, fault_position, r_fault, x_fault):
        """
        Split a branch by a given distance
        :param branch: Branch of a circuit
        :param fault_position: per unit distance measured from the "from" bus (0 ~ 1)
        :param r_fault: Fault resistance in p.u.
        :param x_fault: Fault reactance in p.u.
        :return: the two new branches and the mid short circuited bus
        """

        assert(0.0 < fault_position < 1.0)

        r = branch.R
        x = branch.X
        g = branch.G
        b = branch.B

        # deactivate the current branch
        branch.active = False

        # each of the branches will have the proportional impedance
        # Bus_from------------Middle_bus------------Bus_To
        #    |---------x---------|   (x: distance measured in per unit (0~1)

        middle_bus = Bus()

        # set the bus fault impedance
        middle_bus.Zf = complex(r_fault, x_fault)

        br1 = Branch(bus_from=branch.bus_from,
                     bus_to=middle_bus,
                     r=r * fault_position,
                     x=x * fault_position,
                     g=g * fault_position,
                     b=b * fault_position)

        br2 = Branch(bus_from=middle_bus,
                     bus_to=branch.bus_to,
                     r=r * (1 - fault_position),
                     x=x * (1 - fault_position),
                     g=g * (1 - fault_position),
                     b=b * (1 - fault_position))

        return br1, br2, middle_bus

    def short_circuit_ph3(self, calculation_inputs, Vpf, Zf):
        """
        Run a 3-phase short circuit simulation for a single island
        @param calculation_inputs:
        @param Vpf: Power flow voltage vector applicable to the island
        @param Zf: Short circuit impedance vector applicable to the island
        @return: short circuit results
        """
        Y_gen = calculation_inputs.generator_data.get_gen_Yshunt(seq=1)
        Y_batt = calculation_inputs.battery_data.get_batt_Yshunt(seq=1)
        Ybus_gen_batt = calculation_inputs.Ybus + sp.diags(Y_gen) + sp.diags(Y_batt)
        Zbus = inv(Ybus_gen_batt.tocsc()).toarray()

        # Compute the short circuit
        V, SCpower = short_circuit_3p(bus_idx=self.options.bus_index,
                                      Zbus=Zbus,
                                      Vbus=Vpf,
                                      Zf=Zf,
                                      baseMVA=calculation_inputs.Sbase)

        Sfb, Stb, If, It, Vbranch, \
        loading, losses = short_circuit_post_process(calculation_inputs=calculation_inputs,
                                                     V=V,
                                                     branch_rates=calculation_inputs.branch_rates,
                                                     Yf=calculation_inputs.Yf,
                                                     Yt=calculation_inputs.Yt)

        # voltage, Sf, loading, losses, error, converged, Qpv
        results = ShortCircuitResults(n=calculation_inputs.nbus,
                                      m=calculation_inputs.nbr,
                                      n_tr=calculation_inputs.ntr,
                                      n_hvdc=calculation_inputs.nhvdc,
                                      bus_names=calculation_inputs.bus_names,
                                      branch_names=calculation_inputs.branch_names,
                                      transformer_names=calculation_inputs.tr_names,
                                      hvdc_names=calculation_inputs.hvdc_names,
                                      bus_types=calculation_inputs.bus_types,
                                      area_names=None)

        results.SCpower = SCpower
        results.Sbus1 = calculation_inputs.Sbus * calculation_inputs.Sbase  # MVA
        results.voltage1 = V
        results.Sf1 = Sfb  # in MVA already
        results.St1 = Stb  # in MVA already
        results.If1 = If  # in p.u.
        results.It1 = It  # in p.u.
        results.Vbranch1 = Vbranch
        results.loading1 = loading
        results.losses1 = losses

        return results

    def short_circuit_unbalanced(self, calculation_inputs, Vpf, Zf):
        """
        Run an unbalanced short circuit simulation for a single island
        @param calculation_inputs:
        @param Vpf: Power flow voltage vector applicable to the island
        @param Zf: Short circuit impedance vector applicable to the island
        @return: short circuit results
        """

        # build Y0, Y1, Y2
        nbr = calculation_inputs.nbr
        nbus = calculation_inputs.nbus

        Y_gen0 = calculation_inputs.generator_data.get_gen_Yshunt(seq=0)
        Y_batt0 = calculation_inputs.battery_data.get_batt_Yshunt(seq=0)
        Yshunt_bus0 = Y_gen0 + Y_batt0

        Y0 = compute_admittances(R=calculation_inputs.branch_data.R0,
                                 X=calculation_inputs.branch_data.X0,
                                 G=calculation_inputs.branch_data.G0_,  # renamed, it was overwritten
                                 B=calculation_inputs.branch_data.B0,
                                 k=calculation_inputs.branch_data.k,
                                 tap_module=calculation_inputs.branch_data.m[:, 0],
                                 vtap_f=calculation_inputs.branch_data.tap_f,
                                 vtap_t=calculation_inputs.branch_data.tap_t,
                                 tap_angle=calculation_inputs.branch_data.theta[:, 0],
                                 Beq=np.zeros(nbr),
                                 Cf=calculation_inputs.branch_data.C_branch_bus_f,
                                 Ct=calculation_inputs.branch_data.C_branch_bus_t,
                                 G0=np.zeros(nbr),
                                 If=np.zeros(nbr),
                                 a=np.zeros(nbr),
                                 b=np.zeros(nbr),
                                 c=np.zeros(nbr),
                                 Yshunt_bus=Yshunt_bus0,
                                 conn=calculation_inputs.branch_data.conn,
                                 seq=0)

        Y_gen1 = calculation_inputs.generator_data.get_gen_Yshunt(seq=1)
        Y_batt1 = calculation_inputs.battery_data.get_batt_Yshunt(seq=1)
        Yshunt_bus1 = calculation_inputs.Yshunt_from_devices[:, 0] + Y_gen1 + Y_batt1

        Y1 = compute_admittances(R=calculation_inputs.branch_data.R,
                                 X=calculation_inputs.branch_data.X,
                                 G=calculation_inputs.branch_data.G,
                                 B=calculation_inputs.branch_data.B,
                                 k=calculation_inputs.branch_data.k,
                                 tap_module=calculation_inputs.branch_data.m[:, 0],
                                 vtap_f=calculation_inputs.branch_data.tap_f,
                                 vtap_t=calculation_inputs.branch_data.tap_t,
                                 tap_angle=calculation_inputs.branch_data.theta[:, 0],
                                 Beq=calculation_inputs.branch_data.Beq[:, 0],
                                 Cf=calculation_inputs.branch_data.C_branch_bus_f,
                                 Ct=calculation_inputs.branch_data.C_branch_bus_t,
                                 G0=calculation_inputs.branch_data.G0[:, 0],
                                 If=np.zeros(nbr),
                                 a=calculation_inputs.branch_data.a,
                                 b=calculation_inputs.branch_data.b,
                                 c=calculation_inputs.branch_data.c,
                                 Yshunt_bus=Yshunt_bus1,
                                 conn=calculation_inputs.branch_data.conn,
                                 seq=1)

        Y_gen2 = calculation_inputs.generator_data.get_gen_Yshunt(seq=2)
        Y_batt2 = calculation_inputs.battery_data.get_batt_Yshunt(seq=2)
        Yshunt_bus2 = Y_gen2 + Y_batt2

        Y2 = compute_admittances(R=calculation_inputs.branch_data.R2,
                                 X=calculation_inputs.branch_data.X2,
                                 G=calculation_inputs.branch_data.G2,
                                 B=calculation_inputs.branch_data.B2,
                                 k=calculation_inputs.branch_data.k,
                                 tap_module=calculation_inputs.branch_data.m[:, 0],
                                 vtap_f=calculation_inputs.branch_data.tap_f,
                                 vtap_t=calculation_inputs.branch_data.tap_t,
                                 tap_angle=calculation_inputs.branch_data.theta[:, 0],
                                 Beq=np.zeros(nbr),
                                 Cf=calculation_inputs.branch_data.C_branch_bus_f,
                                 Ct=calculation_inputs.branch_data.C_branch_bus_t,
                                 G0=np.zeros(nbr),
                                 If=np.zeros(nbr),
                                 a=np.zeros(nbr),
                                 b=np.zeros(nbr),
                                 c=np.zeros(nbr),
                                 Yshunt_bus=Yshunt_bus2,
                                 conn=calculation_inputs.branch_data.conn,
                                 seq=2)

        # get impedances matrices
        Z0 = inv(Y0.Ybus.tocsc()).toarray()
        Z1 = inv(Y1.Ybus.tocsc()).toarray()
        Z2 = inv(Y2.Ybus.tocsc()).toarray()

        """
        Initialize Vpf introducing phase shifts
        No search algo is needed. Instead, we need to solve YV=0,
        get the angle of the voltages from here and add them to the
        original Vpf. Y should be Yseries (avoid shunts).
        In more detail:
        -----------------   -----   -----
        |   |           |   |Vvd|   |   |
        -----------------   -----   -----
        |   |           |   |   |   |   |
        |   |           | x |   | = |   |
        | Yu|     Yx    |   | V |   | 0 |
        |   |           |   |   |   |   |
        |   |           |   |   |   |   |
        -----------------   -----   -----

        where Yu = Y1.Ybus[pqpv, vd], Yx = Y1.Ybus[pqpv, pqpv], so:
        V = - inv(Yx) Yu Vvd
        ph_add = np.angle(V)
        Vpf[pqpv] *= np.exp(1j * ph_add)
        """

        Y1_series = compute_admittances(R=calculation_inputs.branch_data.R,
                                        X=calculation_inputs.branch_data.X,
                                        G=np.zeros(nbr),
                                        B=np.zeros(nbr),
                                        k=calculation_inputs.branch_data.k,
                                        tap_module=calculation_inputs.branch_data.m[:, 0],
                                        vtap_f=calculation_inputs.branch_data.tap_f,
                                        vtap_t=calculation_inputs.branch_data.tap_t,
                                        tap_angle=calculation_inputs.branch_data.theta[:, 0],
                                        Beq=np.zeros(nbr),
                                        Cf=calculation_inputs.branch_data.C_branch_bus_f,
                                        Ct=calculation_inputs.branch_data.C_branch_bus_t,
                                        G0=np.zeros(nbr),
                                        If=np.zeros(nbr),
                                        a=calculation_inputs.branch_data.a,
                                        b=calculation_inputs.branch_data.b,
                                        c=calculation_inputs.branch_data.c,
                                        Yshunt_bus=np.zeros(nbus, dtype=complex),
                                        conn=calculation_inputs.branch_data.conn,
                                        seq=1)

        vd = calculation_inputs.vd
        pqpv = calculation_inputs.pqpv

        Y1_arr = np.array(Y1_series.Ybus.todense())
        Yu = Y1_arr[np.ix_(pqpv, vd)]
        Yx = Y1_arr[np.ix_(pqpv, pqpv)]

        I_vd = Yu * np.array(Vpf[vd])
        Vpqpv_ph = - np.linalg.inv(Yx) @ I_vd

        ph_add = np.angle(Vpqpv_ph)
        nprect = np.vectorize(rect)
        Vpf[pqpv] = nprect(np.abs(Vpf[pqpv]), np.angle(Vpf[pqpv]) + ph_add.T[0])

        # solve the fault
        V0, V1, V2 = short_circuit_unbalance(bus_idx=self.options.bus_index,
                                             Z0=Z0,
                                             Z1=Z1,
                                             Z2=Z2,
                                             Vbus=Vpf,
                                             Zf=Zf,
                                             fault_type=self.options.fault_type)

        # process results in the sequences
        Sfb0, Stb0, If0, It0, Vbranch0, \
        loading0, losses0 = short_circuit_post_process(calculation_inputs=calculation_inputs,
                                                       V=V0,
                                                       branch_rates=calculation_inputs.branch_rates,
                                                       Yf=Y0.Yf,
                                                       Yt=Y0.Yt)

        Sfb1, Stb1, If1, It1, Vbranch1, \
        loading1, losses1 = short_circuit_post_process(calculation_inputs=calculation_inputs,
                                                       V=V1,
                                                       branch_rates=calculation_inputs.branch_rates,
                                                       Yf=Y1.Yf,
                                                       Yt=Y1.Yt)

        Sfb2, Stb2, If2, It2, Vbranch2, \
        loading2, losses2 = short_circuit_post_process(calculation_inputs=calculation_inputs,
                                                       V=V2,
                                                       branch_rates=calculation_inputs.branch_rates,
                                                       Yf=Y2.Yf,
                                                       Yt=Y2.Yt)

        # voltage, Sf, loading, losses, error, converged, Qpv
        results = ShortCircuitResults(n=calculation_inputs.nbus,
                                      m=calculation_inputs.nbr,
                                      n_tr=calculation_inputs.ntr,
                                      n_hvdc=calculation_inputs.nhvdc,
                                      bus_names=calculation_inputs.bus_names,
                                      branch_names=calculation_inputs.branch_names,
                                      transformer_names=calculation_inputs.tr_names,
                                      hvdc_names=calculation_inputs.hvdc_names,
                                      bus_types=calculation_inputs.bus_types,
                                      area_names=None)

        results.voltage0 = V0
        results.Sf0 = Sfb0  # in MVA already
        results.St0 = Stb0  # in MVA already
        results.If0 = If0  # in p.u.
        results.It0 = It0  # in p.u.
        results.Vbranch0 = Vbranch0
        results.loading0 = loading0
        results.losses0 = losses0

        results.voltage1 = V1
        results.Sf1 = Sfb1  # in MVA already
        results.St1 = Stb1  # in MVA already
        results.If1 = If1  # in p.u.
        results.It1 = It1  # in p.u.
        results.Vbranch1 = Vbranch1
        results.loading1 = loading1
        results.losses1 = losses1

        results.voltage2 = V2
        results.Sf2 = Sfb2  # in MVA already
        results.St2 = Stb2  # in MVA already
        results.If2 = If2  # in p.u.
        results.It2 = It2  # in p.u.
        results.Vbranch2 = Vbranch2
        results.loading2 = loading2
        results.losses2 = losses2

        return results

    def single_short_circuit(self, calculation_inputs: SnapshotData, Vpf, Zf):
        """
        Run a short circuit simulation for a single island
        @param calculation_inputs:
        @param Vpf: Power flow voltage vector applicable to the island
        @param Zf: Short circuit impedance vector applicable to the island
        @return: short circuit results
        """
        # compute Zbus
        # is dense, so no need to store it as sparse
        if calculation_inputs.Ybus.shape[0] > 1:
            if self.options.fault_type == FaultType.ph3:
                return self.short_circuit_ph3(calculation_inputs, Vpf, Zf)

            elif self.options.fault_type in [FaultType.LG, FaultType.LL, FaultType.LLG]:
                return self.short_circuit_unbalanced(calculation_inputs, Vpf, Zf)

            else:
                raise Exception('Unknown fault type!')

        # if we get here, no short circuit was done, so declare empty results and exit
        nbus = calculation_inputs.Ybus.shape[0]
        nbr = calculation_inputs.nbr

        # voltage, Sf, loading, losses, error, converged, Qpv
        results = results = ShortCircuitResults(n=calculation_inputs.nbus,
                                                m=calculation_inputs.nbr,
                                                n_tr=calculation_inputs.ntr,
                                                n_hvdc=calculation_inputs.nhvdc,
                                                bus_names=calculation_inputs.bus_names,
                                                branch_names=calculation_inputs.branch_names,
                                                transformer_names=calculation_inputs.tr_names,
                                                hvdc_names=calculation_inputs.hvdc_names,
                                                bus_types=calculation_inputs.bus_types,
                                                area_names=None)

        results.Sbus = calculation_inputs.Sbus
        results.voltage = np.zeros(nbus, dtype=complex)
        results.Sf = np.zeros(nbr, dtype=complex)
        results.If = np.zeros(nbr, dtype=complex)
        results.losses = np.zeros(nbr, dtype=complex)
        results.SCpower = np.zeros(nbus, dtype=complex)

        return results

    def run(self):
        """
        Run a power flow for every circuit
        @return:
        """
        self._is_running = True
        if len(self.options.branch_index) > 0:

            # if there are branch indices where to perform short circuits, modify the grid accordingly

            grid = self.grid.copy()

            sc_bus_index = list()

            for k, br_idx in enumerate(self.options.branch_index):

                # modify the grid by inserting a mid-line short circuit bus
                br1, br2, middle_bus = self.split_branch(branch=br_idx,
                                                         fault_position=self.options.branch_fault_locations[k],
                                                         r_fault=self.options.branch_fault_impedance[k].real,
                                                         x_fault=self.options.branch_fault_impedance[k].imag)

                grid.add_branch(br1)
                grid.add_branch(br2)
                grid.add_bus(middle_bus)
                sc_bus_index.append(len(grid.buses) - 1)

        else:
            grid = self.grid

        # Compile the grid
        numerical_circuit = compile_snapshot_circuit(circuit=grid,
                                                     apply_temperature=self.pf_options.apply_temperature_correction,
                                                     branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode,
                                                     opf_results=self.opf_results)

        calculation_inputs = numerical_circuit.split_into_islands(ignore_single_node_islands=self.pf_options.ignore_single_node_islands)

        results = ShortCircuitResults(n=numerical_circuit.nbus,
                                      m=numerical_circuit.nbr,
                                      n_tr=numerical_circuit.ntr,
                                      n_hvdc=numerical_circuit.nhvdc,
                                      bus_names=numerical_circuit.bus_names,
                                      branch_names=numerical_circuit.branch_names,
                                      transformer_names=numerical_circuit.tr_names,
                                      hvdc_names=numerical_circuit.hvdc_names,
                                      bus_types=numerical_circuit.bus_types)
        results.bus_types = numerical_circuit.bus_types

        Zf = self.compile_zf(grid)

        if len(calculation_inputs) > 1:  # multi-island

            for i, calculation_input in enumerate(calculation_inputs):

                bus_original_idx = calculation_input.original_bus_idx
                branch_original_idx = calculation_input.original_branch_idx

                res = self.single_short_circuit(calculation_inputs=calculation_input,
                                                Vpf=self.pf_results.voltage[bus_original_idx],
                                                Zf=Zf[bus_original_idx])

                # merge results
                results.apply_from_island(res, bus_original_idx, branch_original_idx)

        else:  # single island

            results = self.single_short_circuit(calculation_inputs=calculation_inputs[0],
                                                Vpf=self.pf_results.voltage,
                                                Zf=Zf)

        self.results = results
        self.grid.short_circuit_results = results
        self._is_running = False

    def isRunning(self):
        return self._is_running


if __name__ == '__main__':

    import GridCal.Engine as gce


    fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/South Island of New Zealand.gridcal'

    grid = gce.FileOpen(fname).open()

    pf_options = PowerFlowOptions(solver_type=gce.SolverType.NR,  # Base method to use
                                  verbose=False,  # Verbose option where available
                                  tolerance=1e-6,  # power error in p.u.
                                  max_iter=25,  # maximum iteration number
                                  )
    pf = gce.PowerFlowDriver(grid, pf_options)
    pf.run()

    sc_options = ShortCircuitOptions(bus_index=[2], fault_type=FaultType.LG)
    sc = ShortCircuitDriver(grid, options=sc_options, pf_options=pf_options, pf_results=pf.results)
    sc.run()