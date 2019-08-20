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
from numpy import complex, zeros, conj, maximum, array
from scipy.sparse.linalg import inv
from matplotlib import pyplot as plt
from PySide2.QtCore import QRunnable

from GridCal.Engine.Simulations.ShortCircuit.short_circuit import short_circuit_3p
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.plot_config import LINEWIDTH
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from GridCal.Engine.Core.calculation_inputs import CalculationInputs
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Devices import Branch, Bus

########################################################################################################################
# Short circuit classes
########################################################################################################################


class ShortCircuitOptions:

    def __init__(self, bus_index=[], branch_index=[], branch_fault_locations=[], branch_fault_impedance=[],
                 branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
                 verbose=False):
        """

        Args:
            bus_index:
            branch_index:
            branch_fault_locations:
            branch_fault_impedance:
            verbose:
        """

        assert (len(branch_fault_locations) == len(branch_index))
        assert (len(branch_fault_impedance) == len(branch_index))

        self.bus_index = bus_index

        self.branch_index = branch_index

        self.branch_fault_locations = branch_fault_locations

        self.branch_fault_impedance = branch_fault_impedance

        self.branch_impedance_tolerance_mode = branch_impedance_tolerance_mode

        self.verbose = verbose


class ShortCircuitResults(PowerFlowResults):

    def __init__(self, Sbus=None, voltage=None, Sbranch=None, Ibranch=None, loading=None, losses=None, SCpower=None,
                 error=None, converged=None, Qpv=None):

        """

        Args:
            Sbus:
            voltage:
            Sbranch:
            Ibranch:
            loading:
            losses:
            SCpower:
            error:
            converged:
            Qpv:
        """
        PowerFlowResults.__init__(self, Sbus=Sbus, voltage=voltage, Sbranch=Sbranch, Ibranch=Ibranch,
                                  loading=loading, losses=losses, error=error, converged=converged, Qpv=Qpv)

        self.short_circuit_power = SCpower

        self.available_results = [ResultTypes.BusVoltage,
                                  ResultTypes.BranchPower,
                                  ResultTypes.BranchCurrent,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchLosses,
                                  ResultTypes.BusShortCircuitPower]

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return ShortCircuitResults(Sbus=self.Sbus, voltage=self.voltage, Sbranch=self.Sbranch,
                                   Ibranch=self.Ibranch, loading=self.loading,
                                   losses=self.losses, SCpower=self.short_circuit_power, error=self.error,
                                   converged=self.converged, Qpv=self.Qpv)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = zeros(n, dtype=complex)

        self.voltage = zeros(n, dtype=complex)

        self.short_circuit_power = zeros(n, dtype=complex)

        self.overvoltage = zeros(n, dtype=complex)

        self.undervoltage = zeros(n, dtype=complex)

        self.Sbranch = zeros(m, dtype=complex)

        self.Ibranch = zeros(m, dtype=complex)

        self.loading = zeros(m, dtype=complex)

        self.losses = zeros(m, dtype=complex)

        self.overloads = zeros(m, dtype=complex)

        self.error = 0

        self.converged = True

        self.buses_useful_for_storage = list()

    def apply_from_island(self, results, b_idx, br_idx):
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

        self.overvoltage[b_idx] = results.overvoltage

        self.undervoltage[b_idx] = results.undervoltage

        self.Sbranch[br_idx] = results.Sbranch

        self.Ibranch[br_idx] = results.Ibranch

        self.loading[br_idx] = results.loading

        self.losses[br_idx] = results.losses

        self.overloads[br_idx] = results.overloads

        if results.error > self.error:
            self.error = results.error

        self.converged = self.converged and results.converged

        if results.buses_useful_for_storage is not None:
            self.buses_useful_for_storage = b_idx[results.buses_useful_for_storage]

    def plot(self, result_type, ax=None, indices=None, names=None):
        """
        Plot the results
        Args:
            result_type:
            ax:
            indices:
            names:

        Returns:

        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None:
            indices = array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            ylabel = ''
            title = ''
            if result_type == ResultTypes.BusVoltage:
                y = self.voltage[indices]
                ylabel = '(p.u.)'
                title = 'Bus voltage '

            elif result_type == ResultTypes.BranchPower:
                y = self.Sbranch[indices]
                ylabel = '(MVA)'
                title = 'Branch power '

            elif result_type == ResultTypes.BranchCurrent:
                y = self.Ibranch[indices]
                ylabel = '(p.u.)'
                title = 'Branch current '

            elif result_type == ResultTypes.BranchLoading:
                y = self.loading[indices] * 100
                ylabel = '(%)'
                title = 'Branch loading '

            elif result_type == ResultTypes.BranchLosses:
                y = self.losses[indices]
                ylabel = '(MVA)'
                title = 'Branch losses '

            elif result_type == ResultTypes.BusShortCircuitPower:
                y = self.short_circuit_power[indices]
                ylabel = '(MVA)'
                title = 'Bus short circuit power'
            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            df.abs().plot(ax=ax, kind='bar', linewidth=LINEWIDTH)
            ax.set_ylabel(ylabel)
            ax.set_title(title)

            return df

        else:
            return None


class ShortCircuit(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: ShortCircuitOptions, pf_results: PowerFlowResults):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # power flow results
        self.pf_results = pf_results

        # Options to use
        self.options = options

        self.results = None

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return list()

    @staticmethod
    def compile_zf(grid):

        # compile the buses short circuit impedance array
        n = len(grid.buses)
        Zf = zeros(n, dtype=complex)
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

    def single_short_circuit(self, calculation_inputs: CalculationInputs, Vpf, Zf):
        """
        Run a power flow simulation for a single circuit
        @param calculation_inputs:
        @param Vpf: Power flow voltage vector applicable to the island
        @param Zf: Short circuit impedance vector applicable to the island
        @return: short circuit results
        """
        # compute Zbus
        # is dense, so no need to store it as sparse
        if calculation_inputs.Ybus.shape[0] > 1:
            Zbus = inv(calculation_inputs.Ybus).toarray()

            # Compute the short circuit
            V, SCpower = short_circuit_3p(bus_idx=self.options.bus_index,
                                          Zbus=Zbus,
                                          Vbus=Vpf,
                                          Zf=Zf,
                                          baseMVA=calculation_inputs.Sbase)

            # Compute the branches power
            Sbranch, Ibranch, loading, losses = self.compute_branch_results(calculation_inputs=calculation_inputs, V=V)

            # voltage, Sbranch, loading, losses, error, converged, Qpv
            results = ShortCircuitResults(Sbus=calculation_inputs.Sbus,
                                          voltage=V,
                                          Sbranch=Sbranch,
                                          Ibranch=Ibranch,
                                          loading=loading,
                                          losses=losses,
                                          SCpower=SCpower,
                                          error=0,
                                          converged=True,
                                          Qpv=None)
        else:
            nbus = calculation_inputs.Ybus.shape[0]
            nbr = calculation_inputs.nbr

            # voltage, Sbranch, loading, losses, error, converged, Qpv
            results = ShortCircuitResults(Sbus=calculation_inputs.Sbus,
                                          voltage=zeros(nbus, dtype=complex),
                                          Sbranch=zeros(nbr, dtype=complex),
                                          Ibranch=zeros(nbr, dtype=complex),
                                          loading=zeros(nbr, dtype=complex),
                                          losses=zeros(nbr, dtype=complex),
                                          SCpower=zeros(nbus, dtype=complex),
                                          error=0,
                                          converged=True,
                                          Qpv=None)

        return results

    @staticmethod
    def compute_branch_results(calculation_inputs: CalculationInputs, V):
        """
        Compute the power flows trough the branches
        @param calculation_inputs: instance of Circuit
        @param V: Voltage solution array for the circuit buses
        @return: Sbranch, Ibranch, loading, losses
        """
        If = calculation_inputs.Yf * V
        It = calculation_inputs.Yt * V
        Sf = (calculation_inputs.C_branch_bus_f * V) * conj(If)
        St = (calculation_inputs.C_branch_bus_t * V) * conj(It)
        losses = Sf - St
        Ibranch = maximum(If, It)
        Sbranch = maximum(Sf, St)
        loading = Sbranch * calculation_inputs.Sbase / calculation_inputs.branch_rates

        # idx = where(abs(loading) == inf)[0]
        # loading[idx] = 9999

        return Sbranch, Ibranch, loading, losses

    def run(self):
        """
        Run a power flow for every circuit
        @return:
        """
        # print('Short circuit at ', self.grid.name)
        # self.progress_signal.emit(0.0)

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

        n = len(grid.buses)
        m = len(grid.branches)
        results = ShortCircuitResults()  # yes, reuse this class
        results.initialize(n, m)

        # Compile the grid
        numerical_circuit = self.grid.compile()
        calculation_inputs = numerical_circuit.compute(branch_tolerance_mode=self.options.branch_impedance_tolerance_mode)

        results.bus_types = numerical_circuit.bus_types

        Zf = self.compile_zf(grid)

        if len(calculation_inputs) > 1:  # multi-island

            for i, calculation_input in enumerate(calculation_inputs):

                bus_original_idx = numerical_circuit.islands[i]
                branch_original_idx = numerical_circuit.island_branches[i]

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

    def cancel(self):
        self.__cancel__ = True
