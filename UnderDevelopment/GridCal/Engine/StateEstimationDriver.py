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
from enum import Enum
from PyQt5.QtCore import QThread, QRunnable, pyqtSignal


from GridCal.Engine.Numerical.SE import solve_se_lm
from GridCal.Engine.PowerFlowDriver import PowerFlowResults, PowerFlowMP
from GridCal.Engine.CalculationEngine import MultiCircuit, NumericalCircuit


class MeasurementType(Enum):
    Pinj = 1,
    Qinj = 2,
    Vmag = 3,
    Pflow = 4,
    Qflow = 5,
    Iflow = 6


class Measurement:

    def __init__(self, value, uncertainty, mtype: MeasurementType):
        """
        Constructor
        :param value: value
        :param uncertainty: uncertainty (standard deviation)
        :param mtype: type of measurement
        """
        self.val = value
        self.sigma = uncertainty
        self.measurement_type = mtype


########################################################################################################################
# State Estimation classes
########################################################################################################################

class StateEstimationInput:

    def __init__(self):
        """
        State estimation inputs constructor
        """

        # Node active power measurements vector of pointers
        self.p_inj =list()

        # Node  reactive power measurements vector of pointers
        self.q_inj = list()

        # Branch active power measurements vector of pointers
        self.p_flow = list()

        # Branch reactive power measurements vector of pointers
        self.q_flow = list()

        # Branch current module measurements vector of pointers
        self.i_flow = list()

        # Node voltage module measurements vector of pointers
        self.vm_m = list()

        # nodes without power injection measurements
        self.p_inj_idx = list()

        # branches without power measurements
        self.p_flow_idx = list()

        # nodes without reactive power injection measurements
        self.q_inj_idx = list()

        # branches without reactive power measurements
        self.q_flow_idx = list()

        # branches without current measurements
        self.i_flow_idx = list()

        # nodes without voltage module measurements
        self.vm_m_idx = list()

    def clear(self):
        """
        Clear
        """
        self.p_inj.clear()
        self.p_flow.clear()
        self.q_inj.clear()
        self.q_flow.clear()
        self.i_flow.clear()
        self.vm_m.clear()

        self.p_inj_idx.clear()
        self.p_flow_idx.clear()
        self.q_inj_idx.clear()
        self.q_flow_idx.clear()
        self.i_flow_idx.clear()
        self.vm_m_idx.clear()

    def consolidate(self):
        """
        consolidate the measurements into "measurements" and "sigma"
        :return: measurements, sigma
        """

        nz = len(self.p_inj) + len(self.p_flow) + len(self.q_inj) + len(self.q_flow) + len(self.i_flow) + len(self.vm_m)

        magnitudes = np.zeros(nz)
        sigma = np.zeros(nz)

        # go through the measurements in order and form the vectors
        k = 0
        for m in self.p_flow + self.p_inj + self.q_flow + self.q_inj + self.i_flow + self.vm_m:
            magnitudes[k] = m.val
            sigma[k] = m.sigma
            k += 1

        return magnitudes, sigma


class StateEstimationResults(PowerFlowResults):

    def __init__(self, Sbus=None, voltage=None, Sbranch=None, Ibranch=None, loading=None, losses=None,
                 error=None, converged=None, Qpv=None):
        """
        Constructor
        :param Sbus: Bus power injections
        :param voltage: Bus voltages
        :param Sbranch: Branch power flow
        :param Ibranch: Branch current flow
        :param loading: Branch loading
        :param losses: Branch losses
        :param error: error
        :param converged: converged?
        :param Qpv: Reactive power at the PV nodes
        """
        # initialize the
        PowerFlowResults.__init__(self, Sbus=Sbus, voltage=voltage, Sbranch=Sbranch, Ibranch=Ibranch,
                                  loading=loading, losses=losses, error=error, converged=converged, Qpv=Qpv)


class StateEstimation(QRunnable):

    def __init__(self, circuit: MultiCircuit):
        """
        Constructor
        :param circuit: circuit object
        """

        QRunnable.__init__(self)

        self.grid = circuit

        self.se_results = None

    @staticmethod
    def collect_measurements(circuit: NumericalCircuit):
        """
        Form the input from the circuit measurements
        :return: nothing, the input object is stored in this class
        """
        se_input = StateEstimationInput()

        # collect the bus measurements
        for i, bus in enumerate(circuit.buses):

            for m in bus.measurements:

                if m.measurement_type == MeasurementType.Pinj:
                    se_input.p_inj_idx.append(i)
                    se_input.p_inj.append(m)

                elif m.measurement_type == MeasurementType.Qinj:
                    se_input.q_inj_idx.append(i)
                    se_input.q_inj.append(m)

                elif m.measurement_type == MeasurementType.Vmag:
                    se_input.vm_m_idx.append(i)
                    se_input.vm_m.append(m)

                else:
                    raise Exception('The bus ' + str(bus) + ' contains a measurement of type ' + str(m.measurement_type))

        # collect the branch measurements
        for i, branch in enumerate(circuit.branches):

            for m in branch.measurements:

                if m.measurement_type == MeasurementType.Pflow:
                    se_input.p_flow_idx.append(i)
                    se_input.p_flow.append(m)

                elif m.measurement_type == MeasurementType.Qflow:
                    se_input.q_flow_idx.append(i)
                    se_input.q_flow.append(m)

                elif m.measurement_type == MeasurementType.Iflow:
                    se_input.i_flow_idx.append(i)
                    se_input.i_flow.append(m)

                else:
                    raise Exception(
                        'The branch ' + str(branch) + ' contains a measurement of type ' + str(m.measurement_type))

        return se_input

    def run(self):
        """
        Run state estimation
        :return:
        """
        n = len(self.grid.buses)
        m = len(self.grid.branches)
        self.se_results = StateEstimationResults()
        self.se_results.initialize(n, m)

        for circuit in self.grid.circuits:

            # collect inputs
            se_input = self.collect_measurements(circuit=circuit)

            # run solver
            v_sol, err, converged = solve_se_lm(Ybus=circuit.power_flow_input.Ybus,
                                                Yf=circuit.power_flow_input.Yf,
                                                Yt=circuit.power_flow_input.Yt,
                                                f=circuit.power_flow_input.F,
                                                t=circuit.power_flow_input.T,
                                                se_input=se_input,
                                                ref=circuit.power_flow_input.ref,
                                                pq=circuit.power_flow_input.pq,
                                                pv=circuit.power_flow_input.pv)

            # Compute the branches power and the slack buses power
            Sbranch, Ibranch, loading, \
            losses, flow_direction, Sbus = PowerFlowMP.power_flow_post_process(calculation_inputs=circuit, V=v_sol)

            # pack results into a SE results object
            results = StateEstimationResults(Sbus=Sbus,
                                             voltage=v_sol,
                                             Sbranch=Sbranch,
                                             Ibranch=Ibranch,
                                             loading=loading,
                                             losses=losses,
                                             error=[err],
                                             converged=[converged],
                                             Qpv=None)

            self.se_results.apply_from_island(results, circuit.bus_original_idx, circuit.branch_original_idx)