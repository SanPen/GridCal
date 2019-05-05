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

from GridCal.Engine.plot_config import LINEWIDTH
from GridCal.Engine.Simulations.result_types import ResultTypes


class OptimalPowerFlowResults:
    """
    OPF results.

    Arguments:

        **Sbus**: bus power injections

        **voltage**: bus voltages

        **load_shedding**: load shedding values

        **Sbranch**: branch power values

        **overloads**: branch overloading values

        **loading**: branch loading values

        **losses**: branch losses

        **converged**: converged?
    """

    def __init__(self, Sbus=None, voltage=None, load_shedding=None, generation_shedding=None,
                 battery_power=None, controlled_generation_power=None,
                 Sbranch=None, overloads=None, loading=None, losses=None, converged=None, bus_types=None):

        self.Sbus = Sbus

        self.voltage = voltage

        self.load_shedding = load_shedding

        self.generation_shedding = generation_shedding

        self.Sbranch = Sbranch

        self.bus_types = bus_types

        self.overloads = overloads

        self.loading = loading

        self.losses = losses

        self.battery_power = battery_power

        self.controlled_generation_power = controlled_generation_power

        self.flow_direction = None

        self.converged = converged

        self.available_results = [ResultTypes.BusVoltageModule,
                                  ResultTypes.BusVoltageAngle,
                                  ResultTypes.BranchPower,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchOverloads,
                                  ResultTypes.LoadShedding,
                                  ResultTypes.ControlledGeneratorShedding,
                                  ResultTypes.ControlledGeneratorPower,
                                  ResultTypes.BatteryPower]

        self.plot_bars_limit = 100

    def copy(self):
        """
        Return a copy of this
        @return:
        """
        return OptimalPowerFlowResults(Sbus=self.Sbus,
                                       voltage=self.voltage,
                                       load_shedding=self.load_shedding,
                                       Sbranch=self.Sbranch,
                                       overloads=self.overloads,
                                       loading=self.loading,
                                       generation_shedding=self.generation_shedding,
                                       battery_power=self.battery_power,
                                       controlled_generation_power=self.controlled_generation_power,
                                       converged=self.converged)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = np.zeros(n, dtype=complex)

        self.voltage = np.zeros(n, dtype=complex)

        self.load_shedding = np.zeros(n, dtype=float)

        self.Sbranch = np.zeros(m, dtype=complex)

        self.loading = np.zeros(m, dtype=complex)

        self.overloads = np.zeros(m, dtype=complex)

        self.losses = np.zeros(m, dtype=complex)

        self.converged = list()

        self.plot_bars_limit = 100

    def plot(self, result_type, ax=None, indices=None, names=None):
        """
        Plot the results
        :param result_type: type of results (string)
        :param ax: matplotlib axis object
        :param indices: element indices
        :param names: element names
        :return: DataFrame of the results (or None if the result was not understood)
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if indices is None:
            indices = np.array(range(len(names)))

        if len(indices) > 0:
            labels = names[indices]
            y_label = ''
            title = ''
            if result_type == ResultTypes.BusVoltageModule:
                y = np.abs(self.voltage[indices])
                y_label = '(p.u.)'
                title = 'Bus voltage module'

            if result_type == ResultTypes.BusVoltageAngle:
                y = np.angle(self.voltage[indices])
                y_label = '(Radians)'
                title = 'Bus voltage angle'

            elif result_type == ResultTypes.BranchPower:
                y = self.Sbranch[indices].real
                y_label = '(MW)'
                title = 'Branch power '

            elif result_type == ResultTypes.BusPower:
                y = self.Sbus[indices].real
                y_label = '(MW)'
                title = 'Bus power '

            elif result_type == ResultTypes.BranchLoading:
                y = np.abs(self.loading[indices] * 100.0)
                y_label = '(%)'
                title = 'Branch loading '

            elif result_type == ResultTypes.BranchOverloads:
                y = np.abs(self.overloads[indices])
                y_label = '(MW)'
                title = 'Branch overloads '

            elif result_type == ResultTypes.BranchLosses:
                y = self.losses[indices].real
                y_label = '(MW)'
                title = 'Branch losses '

            elif result_type == ResultTypes.LoadShedding:
                y = self.load_shedding[indices]
                y_label = '(MW)'
                title = 'Load shedding'

            elif result_type == ResultTypes.ControlledGeneratorShedding:
                y = self.generation_shedding[indices]
                y_label = '(MW)'
                title = 'Controlled generator shedding'

            elif result_type == ResultTypes.ControlledGeneratorPower:
                y = self.controlled_generation_power[indices]
                y_label = '(MW)'
                title = 'Controlled generators power'

            elif result_type == ResultTypes.BatteryPower:
                y = self.battery_power[indices]
                y_label = '(MW)'
                title = 'Battery power'

            else:
                pass

            df = pd.DataFrame(data=y, index=labels, columns=[result_type])
            df.fillna(0, inplace=True)

            if len(df.columns) < self.plot_bars_limit:
                df.plot(ax=ax, kind='bar')
            else:
                df.plot(ax=ax, legend=False, linewidth=LINEWIDTH)
            ax.set_ylabel(y_label)
            ax.set_title(title)

            return df

        else:
            return None

