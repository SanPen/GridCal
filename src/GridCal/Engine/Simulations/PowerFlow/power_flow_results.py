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
import pandas as pd
from matplotlib import pyplot as plt

# from GridCal.Engine.NewEngine import NumericalCircuit
from GridCal.Engine.plot_config import LINEWIDTH
from GridCal.Engine.Simulations.result_types import ResultTypes


class PowerFlowResults:
    """
    A **PowerFlowResults** object is create as an attribute of the
    :ref:`PowerFlowMP<pf_mp>` (as PowerFlowMP.results) when the power flow is run. It
    provides access to the simulation results through its class attributes.

    Attributes:

        **Sbus** (list): Power at each bus in complex MVA

        **voltage** (list): Voltage at each bus in complex per unit

        **Sbranch** (list): Power through each branch in complex MVA

        **Ibranch** (list): Current through each branch in complex per unit

        **loading** (list): Loading of each branch in per unit

        **losses** (list): Losses in each branch in complex MVA

        **tap_module** (list): Computed tap module at each branch in per unit

        **flow_direction** (list): Flow direction at each branch

        **error** (float): Power flow computed error

        **converged** (bool): Did the power flow converge?

        **Qpv** (list): Reactive power at each PV node in per unit

        **inner_it** (int): Number of inner iterations

        **outer_it** (int): Number of outer iterations

        **elapsed** (float): Simulation duration in seconds

        **methods** (list): Power flow methods used

    """

    def __init__(self, Sbus=None, voltage=None, Sbranch=None, Ibranch=None, loading=None, losses=None, tap_module=None,
                 flow_direction=None, error=None, converged=None, Qpv=None, battery_power_inc=None, inner_it=None,
                 outer_it=None, elapsed=None, methods=None, bus_types=None):

        self.Sbus = Sbus

        self.voltage = voltage

        self.Sbranch = Sbranch

        self.Ibranch = Ibranch

        self.loading = loading

        self.losses = losses

        self.flow_direction = flow_direction

        self.tap_module = tap_module

        self.error = error

        self.bus_types = bus_types

        self.converged = converged

        self.Qpv = Qpv

        self.battery_power_inc = battery_power_inc

        self.overloads = None

        self.overvoltage = None

        self.undervoltage = None

        self.overloads_idx = None

        self.overvoltage_idx = None

        self.undervoltage_idx = None

        self.buses_useful_for_storage = None

        self.available_results = [ResultTypes.BusVoltage,
                                  # 'Bus voltage (polar)',
                                  ResultTypes.BranchPower,
                                  ResultTypes.BranchCurrent,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchLosses,
                                  ResultTypes.BatteryPower]

        self.plot_bars_limit = 100

        self.inner_iterations = inner_it

        self.outer_iterations = outer_it

        self.elapsed = elapsed

        self.methods = methods

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return PowerFlowResults(Sbus=self.Sbus, voltage=self.voltage, Sbranch=self.Sbranch,
                                Ibranch=self.Ibranch, loading=self.loading,
                                losses=self.losses, error=self.error,
                                converged=self.converged, Qpv=self.Qpv, inner_it=self.inner_iterations,
                                outer_it=self.outer_iterations, elapsed=self.elapsed, methods=self.methods)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = np.zeros(n, dtype=complex)

        self.voltage = np.zeros(n, dtype=complex)

        self.overvoltage = np.zeros(n, dtype=complex)

        self.undervoltage = np.zeros(n, dtype=complex)

        self.Sbranch = np.zeros(m, dtype=complex)

        self.Ibranch = np.zeros(m, dtype=complex)

        self.loading = np.zeros(m, dtype=complex)

        self.flow_direction = np.zeros(m, dtype=float)

        self.losses = np.zeros(m, dtype=complex)

        self.overloads = np.zeros(m, dtype=complex)

        self.error = list()

        self.converged = list()

        self.buses_useful_for_storage = list()

        self.plot_bars_limit = 100

        self.inner_iterations = list()

        self.outer_iterations = list()

        self.elapsed = list()

        self.methods = list()

    def apply_from_island(self, results, b_idx, br_idx):
        """
        Apply results from another island circuit to the circuit results represented
        here.

        Arguments:

            **results**: PowerFlowResults

            **b_idx**: bus original indices

            **br_idx**: branch original indices
        """
        self.Sbus[b_idx] = results.Sbus

        self.voltage[b_idx] = results.voltage

        # self.overvoltage[b_idx] = results.overvoltage

        # self.undervoltage[b_idx] = results.undervoltage

        self.Sbranch[br_idx] = results.Sbranch

        self.Ibranch[br_idx] = results.Ibranch

        self.loading[br_idx] = results.loading

        self.losses[br_idx] = results.losses

        self.flow_direction[br_idx] = results.flow_direction

        # self.overloads[br_idx] = results.overloads

        # if results.error > self.error:
        self.error.append(results.error)

        self.converged.append(results.converged)

        self.inner_iterations.append(results.inner_iterations)

        self.outer_iterations.append(results.outer_iterations)

        self.elapsed.append(results.elapsed)

        self.methods.append(results.methods)

        # self.converged = self.converged and results.converged

        # if results.buses_useful_for_storage is not None:
        #     self.buses_useful_for_storage = b_idx[results.buses_useful_for_storage]

    def check_limits(self, F, T, Vmax, Vmin, wo=1, wv1=1, wv2=1):
        """
        Check the grid violations on the whole circuit

        Arguments:

            **F**:

            **T**:

            **Vmax**:

            **Vmin**:

            **wo**:

            **wv1**:

            **wv2**:

        Returns:

            Summation of the deviations
        """
        # branches: Returns the loading rate when greater than 1 (nominal), zero otherwise
        br_idx = np.where(self.loading > 1)[0]
        bb_f = F[br_idx]
        bb_t = T[br_idx]
        self.overloads = self.loading[br_idx]

        # Over and under voltage values in the indices where it occurs
        Vabs = np.abs(self.voltage)
        vo_idx = np.where(Vabs > Vmax)[0]
        self.overvoltage = (Vabs - Vmax)[vo_idx]
        vu_idx = np.where(Vabs < Vmin)[0]
        self.undervoltage = (Vmin - Vabs)[vu_idx]

        self.overloads_idx = br_idx

        self.overvoltage_idx = vo_idx

        self.undervoltage_idx = vu_idx

        self.buses_useful_for_storage = list(set(np.r_[vo_idx, vu_idx, bb_f, bb_t]))

        return np.abs(wo * np.sum(self.overloads) + wv1 * np.sum(self.overvoltage) + wv2 * np.sum(self.undervoltage))

    def get_convergence_report(self):

        res = 'converged' + str(self.converged)

        res += '\n\tinner_iterations: ' + str(self.inner_iterations)

        res += '\n\touter_iterations: ' + str(self.outer_iterations)

        res += '\n\terror: ' + str(self.error)

        res += '\n\telapsed: ' + str(self.elapsed)

        res += '\n\tmethods: ' + str(self.methods)

        return res

    def get_report_dataframe(self, island_idx=0):
        """
        Get a DataFrame containing the convergence report.

        Arguments:

            **island_idx**: (optional) island index

        Returns:

            DataFrame
        """
        if type(self.methods[island_idx]) == list:

            data = np.c_[self.methods[island_idx],
                         self.converged[island_idx],
                         self.error[island_idx],
                         self.elapsed[island_idx],
                         self.inner_iterations[island_idx]]
        else:

            data = np.c_[self.methods,
                         self.converged,
                         self.error,
                         self.elapsed,
                         self.inner_iterations]

        col = ['Method', 'Converged?', 'Error', 'Elapsed (s)', 'Iterations']
        df = pd.DataFrame(data, columns=col)

        return df

    def plot(self, result_type: ResultTypes, ax=None, indices=None, names=None):
        """
        Plot the results.

        Arguments:

            **result_type**: ResultTypes

            **ax**: matplotlib axis

            **indices**: Indices f the array to plot (indices of the elements)

            **names**: Names of the elements

        Returns:

            DataFrame
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None and names is not None:
            indices = np.array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            polar = False
            if result_type == ResultTypes.BusVoltage:
                y = self.voltage[indices]
                y_label = '(p.u.)'
                title = 'Bus voltage '
                polar = False

            elif result_type == ResultTypes.BusVoltagePolar:
                y = self.voltage[indices]
                y_label = '(p.u.)'
                title = 'Bus voltage '
                polar = True

            elif result_type == ResultTypes.BranchPower:
                y = self.Sbranch[indices]
                y_label = '(MVA)'
                title = 'Branch power '
                polar = False

            elif result_type == ResultTypes.BranchCurrent:
                y = self.Ibranch[indices]
                y_label = '(p.u.)'
                title = 'Branch current '
                polar = False

            elif result_type == ResultTypes.BranchLoading:
                y = self.loading[indices] * 100
                y_label = '(%)'
                title = 'Branch loading '
                polar = False

            elif result_type == ResultTypes.BranchLosses:
                y = self.losses[indices]
                y_label = '(MVA)'
                title = 'Branch losses '
                polar = False

            elif result_type == ResultTypes.BatteryPower:
                if self.battery_power_inc is not None:
                    y = self.battery_power_inc[indices]
                else:
                    y = np.zeros(len(indices))
                y_label = '(MVA)'
                title = 'Battery power'
                polar = False
            else:
                n = len(labels)
                y = np.zeros(n)
                x_label = ''
                y_label = ''
                title = ''

            # plot
            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            if len(df.columns) < self.plot_bars_limit:
                df.abs().plot(ax=ax, kind='bar')
            else:
                df.abs().plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(y_label)
            ax.set_title(title)

            return df

        else:
            return None

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
        bus_cols = ['Real voltage (p.u.)', 'Imag Voltage (p.u.)', 'Voltage module (p.u.)', 'Voltage angle (rad)']
        df_bus = pd.DataFrame(data=bus_data, columns=bus_cols)

        # branch results
        sr = self.Sbranch.real
        si = self.Sbranch.imag
        sm = np.abs(self.Sbranch)
        ld = np.abs(self.loading)
        la = self.losses.real
        lr = self.losses.imag
        ls = np.abs(self.losses)
        tm = self.tap_module

        branch_data = np.c_[sr, si, sm, ld, la, lr, ls, tm]
        branch_cols = ['Real power (MW)', 'Imag power (MVAr)', 'Power module (MVA)', 'Loading(%)', 'Losses (MW)', 'Losses (MVAr)', 'Losses (MVA)', 'Tap module']
        df_branch = pd.DataFrame(data=branch_data, columns=branch_cols)

        return df_bus, df_branch

