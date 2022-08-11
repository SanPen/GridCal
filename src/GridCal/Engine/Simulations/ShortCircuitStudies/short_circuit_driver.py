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
import scipy.sparse as sp
from scipy.sparse.linalg import inv

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.ShortCircuitStudies.short_circuit import short_circuit_3p, short_circuit_unbalance
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults, PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import power_flow_post_process
from GridCal.Engine.Simulations.ShortCircuitStudies.short_circuit_worker import short_circuit_post_process
from GridCal.Engine.Core.snapshot_pf_data import SnapshotData
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Devices import Branch, Bus
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Core.admittance_matrices import get_Y012
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


class ShortCircuitResults(PowerFlowResults):

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

                # Compute the branches power
                # Sf, If, loading, losses = self.compute_branch_results(calculation_inputs=calculation_inputs, V=V)
                # Sfb, Stb, If, It, Vbranch, \
                # loading, losses, Sbus = power_flow_post_process(calculation_inputs=calculation_inputs,
                #                                                 Sbus=calculation_inputs.Sbus,
                #                                                 V=V,
                #                                                 branch_rates=calculation_inputs.branch_rates,
                #                                                 Yf=calculation_inputs.Yf,
                #                                                 Yt=calculation_inputs.Yt)

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
                                            bus_names=calculation_inputs.bus_names,
                                            branch_names=calculation_inputs.branch_names,
                                            transformer_names=calculation_inputs.tr_names,
                                            bus_types=calculation_inputs.bus_types)

                results.SCpower = SCpower
                results.Sbus = calculation_inputs.Sbus * calculation_inputs.Sbase  # MVA
                results.voltage = V
                results.Sf = Sfb  # in MVA already
                results.St = Stb  # in MVA already
                results.If = If  # in p.u.
                results.It = It  # in p.u.
                results.Vbranch = Vbranch
                results.loading = loading
                results.losses = losses

            elif self.options.fault_type in [FaultType.LG, FaultType.LL, FaultType.LLG]:

                # build Y0, Y1, Y2
                nbr = calculation_inputs.nbr
                nbus = calculation_inputs.nbus


                # Y_shunt_bus = C_bus_elm @ np.power((r + 1j * x), -1)
                # Y_shunt_gen = calculation_inputs.generator_data.get_gen_Yshunt(seq=0)

                Y0 = get_Y012(R=calculation_inputs.branch_data.R0,
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
                                Yshunt_bus=np.zeros(nbus, dtype=complex),
                                gen_data=calculation_inputs.generator_data,
                                batt_data=calculation_inputs.battery_data,
                                conn=calculation_inputs.branch_data.conn,
                                seq=0)

                Y1 = get_Y012(R=calculation_inputs.branch_data.R,
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
                                Yshunt_bus=calculation_inputs.Yshunt_from_devices[:, 0],
                                gen_data=calculation_inputs.generator_data,
                                batt_data=calculation_inputs.battery_data,
                                conn=calculation_inputs.branch_data.conn,
                                seq=1)

                Y2 = get_Y012(R=calculation_inputs.branch_data.R2,
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
                                Yshunt_bus=np.zeros(nbus, dtype=complex),
                                gen_data=calculation_inputs.generator_data,
                                batt_data=calculation_inputs.battery_data,
                                conn=calculation_inputs.branch_data.conn,
                                seq=2)

                # get impedances matrices
                Z0 = inv(Y0.Ybus.tocsc()).toarray()
                Z1 = inv(Y1.Ybus.tocsc()).toarray()
                Z2 = inv(Y2.Ybus.tocsc()).toarray()

                # solve the fault
                Vpf = np.array([1., 1., 1., 1., 1 * np.exp(-1j * np.pi / 6)])  # hardcoded, remove!
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
                                            bus_names=calculation_inputs.bus_names,
                                            branch_names=calculation_inputs.branch_names,
                                            transformer_names=calculation_inputs.tr_names,
                                            bus_types=calculation_inputs.bus_types)

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

            else:
                nbus = calculation_inputs.Ybus.shape[0]
                nbr = calculation_inputs.nbr

                # voltage, Sf, loading, losses, error, converged, Qpv
                results = ShortCircuitResults(n=calculation_inputs.nbus,
                                            m=calculation_inputs.nbr,
                                            n_tr=calculation_inputs.ntr,
                                            bus_names=calculation_inputs.bus_names,
                                            branch_names=calculation_inputs.branch_names,
                                            transformer_names=calculation_inputs.tr_names,
                                            bus_types=calculation_inputs.bus_types)

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
                                      bus_names=numerical_circuit.bus_names,
                                      branch_names=numerical_circuit.branch_names,
                                      transformer_names=numerical_circuit.tr_names,
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
