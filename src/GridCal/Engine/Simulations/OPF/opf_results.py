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
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_model import ResultsModel


class OptimalPowerFlowResults:
    """
    OPF results.

    Arguments:

        **Sbus**: bus power injections

        **voltage**: bus voltages

        **load_shedding**: load shedding values

        **Sf**: branch power values

        **overloads**: branch overloading values

        **loading**: branch loading values

        **losses**: branch losses

        **converged**: converged?
    """

    def __init__(self, bus_names, branch_names, load_names, generator_names, battery_names,
                 Sbus=None, voltage=None, load_shedding=None, generation_shedding=None,
                 battery_power=None, controlled_generation_power=None,
                 Sf=None, overloads=None, loading=None, losses=None, converged=None, bus_types=None):

        self.name = 'OPF'

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.load_names = load_names
        self.generator_names = generator_names
        self.battery_names = battery_names

        self.Sbus = Sbus

        self.voltage = voltage

        self.load_shedding = load_shedding

        self.generation_shedding = generation_shedding

        self.Sf = Sf

        self.bus_types = bus_types

        self.overloads = overloads

        self.loading = loading

        self.losses = losses

        self.battery_power = battery_power

        self.generators_power = controlled_generation_power

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
        return OptimalPowerFlowResults(bus_names=self.bus_names,
                                       branch_names=self.branch_names,
                                       load_names=self.load_names,
                                       generator_names=self.generator_names,
                                       battery_names=self.battery_names,
                                       Sbus=self.Sbus,
                                       voltage=self.voltage,
                                       load_shedding=self.load_shedding,
                                       Sf=self.Sf,
                                       overloads=self.overloads,
                                       loading=self.loading,
                                       generation_shedding=self.generation_shedding,
                                       battery_power=self.battery_power,
                                       controlled_generation_power=self.generators_power,
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

        self.Sf = np.zeros(m, dtype=complex)

        self.loading = np.zeros(m, dtype=complex)

        self.overloads = np.zeros(m, dtype=complex)

        self.losses = np.zeros(m, dtype=complex)

        self.converged = list()

        self.plot_bars_limit = 100

    def mdl(self, result_type) -> "ResultsModel":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
        """

        if result_type == ResultTypes.BusVoltageModule:
            labels = self.bus_names
            y = np.abs(self.voltage)
            y_label = '(p.u.)'
            title = 'Bus voltage module'

        elif result_type == ResultTypes.BusVoltageAngle:
            labels = self.bus_names
            y = np.angle(self.voltage)
            y_label = '(Radians)'
            title = 'Bus voltage angle'

        elif result_type == ResultTypes.BranchPower:
            labels = self.branch_names
            y = self.Sf.real
            y_label = '(MW)'
            title = 'Branch power'

        elif result_type == ResultTypes.BusPower:
            labels = self.bus_names
            y = self.Sbus.real
            y_label = '(MW)'
            title = 'Bus power'

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            y = np.abs(self.loading * 100.0)
            y_label = '(%)'
            title = 'Branch loading'

        elif result_type == ResultTypes.BranchOverloads:
            labels = self.branch_names
            y = np.abs(self.overloads)
            y_label = '(MW)'
            title = 'Branch overloads'

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            y = self.losses.real
            y_label = '(MW)'
            title = 'Branch losses'

        elif result_type == ResultTypes.LoadShedding:
            labels = self.load_names
            y = self.load_shedding
            y_label = '(MW)'
            title = 'Load shedding'

        elif result_type == ResultTypes.ControlledGeneratorShedding:
            labels = self.generator_names
            y = self.generation_shedding
            y_label = '(MW)'
            title = 'Controlled generator shedding'

        elif result_type == ResultTypes.ControlledGeneratorPower:
            labels = self.generator_names
            y = self.generators_power
            y_label = '(MW)'
            title = 'Controlled generators power'

        elif result_type == ResultTypes.BatteryPower:
            labels = self.battery_names
            y = self.battery_power
            y_label = '(MW)'
            title = 'Battery power'

        else:
            labels = []
            y = np.zeros(0)
            y_label = '(MW)'
            title = 'Battery power'

        mdl = ResultsModel(data=y,
                           index=labels,
                           columns=[result_type.value[0]],
                           title=title,
                           ylabel=y_label,
                           xlabel='',
                           units=y_label)
        return mdl

