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
from GridCal.Engine.Simulations.OPF.opf_driver import OptimalPowerFlowResults
from GridCal.Engine.Simulations.results_model import ResultsModel
from GridCal.Engine.Simulations.result_types import ResultTypes


class OptimalPowerFlowTimeSeriesResults:

    def __init__(self, bus_names, branch_names, load_names, generator_names, battery_names,
                 n, m, nt, ngen=0, nbat=0, nload=0, time=None, bus_types=()):
        """
        OPF Time Series results constructor
        :param n: number of buses
        :param m: number of branches
        :param nt: number of time steps
        :param ngen:
        :param nbat:
        :param nload:
        :param time: Time array (optional)
        """
        self.name = 'OPF time series'

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.load_names = load_names
        self.generator_names = generator_names
        self.battery_names = battery_names

        self.bus_types = bus_types

        self.n = n

        self.m = m

        self.nt = nt

        self.time = time

        self.voltage = np.zeros((nt, n), dtype=complex)

        self.load_shedding = np.zeros((nt, nload), dtype=float)

        self.loading = np.zeros((nt, m), dtype=float)

        self.losses = np.zeros((nt, m), dtype=float)

        self.overloads = np.zeros((nt, m), dtype=float)

        self.Sbus = np.zeros((nt, n), dtype=complex)

        self.shadow_prices = np.zeros((nt, n), dtype=float)

        self.Sf = np.zeros((nt, m), dtype=complex)

        self.bus_types = np.zeros(n, dtype=int)

        self.available_results = [ResultTypes.BusVoltageModule,
                                  ResultTypes.BusVoltageAngle,
                                  ResultTypes.ShadowPrices,
                                  ResultTypes.BranchPower,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchOverloads,
                                  ResultTypes.LoadShedding,
                                  ResultTypes.ControlledGeneratorShedding,
                                  ResultTypes.ControlledGeneratorPower,
                                  ResultTypes.BatteryPower,
                                  ResultTypes.BatteryEnergy]

        self.generator_power = np.zeros((nt, ngen), dtype=float)

        self.generator_shedding = np.zeros((nt, ngen), dtype=float)

        self.battery_power = np.zeros((nt, nbat), dtype=float)

        self.battery_energy = np.zeros((nt, nbat), dtype=float)

        self.converged = np.empty(nt, dtype=bool)

    def init_object_results(self, ngen, nbat):
        """
        declare the generator results. This is done separately since these results are known at the end of the simulation
        :param ngen: number of generators
        :param nbat: number of batteries
        """
        self.generator_power = np.zeros((self.nt, ngen), dtype=float)

        self.battery_power = np.zeros((self.nt, nbat), dtype=float)

    def set_at(self, t, res: OptimalPowerFlowResults):
        """
        Set the results
        :param t: time index
        :param res: OptimalPowerFlowResults instance
        """

        self.voltage[t, :] = res.voltage

        self.load_shedding[t, :] = res.load_shedding

        self.loading[t, :] = np.abs(res.loading)

        self.overloads[t, :] = np.abs(res.overloads)

        self.losses[t, :] = np.abs(res.losses)

        self.Sbus[t, :] = res.Sbus

        self.Sf[t, :] = res.Sf

    def mdl(self, result_type) -> "ResultsModel":
        """
        Plot the results
        :param result_type:
        :return:
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

        elif result_type == ResultTypes.ShadowPrices:
            labels = self.bus_names
            y = self.shadow_prices
            y_label = '(currency)'
            title = 'Bus shadow prices'

        elif result_type == ResultTypes.BranchPower:
            labels = self.branch_names
            y = self.Sf.real
            y_label = '(MW)'
            title = 'Branch power '

        elif result_type == ResultTypes.BusPower:
            labels = self.bus_names
            y = self.Sbus.real
            y_label = '(MW)'
            title = 'Bus power '

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            y = np.abs(self.loading * 100.0)
            y_label = '(%)'
            title = 'Branch loading '

        elif result_type == ResultTypes.BranchOverloads:
            labels = self.branch_names
            y = np.abs(self.overloads)
            y_label = '(MW)'
            title = 'Branch overloads '

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            y = self.losses.real
            y_label = '(MW)'
            title = 'Branch losses '

        elif result_type == ResultTypes.LoadShedding:
            labels = self.load_names
            y = self.load_shedding
            y_label = '(MW)'
            title = 'Load shedding'

        elif result_type == ResultTypes.ControlledGeneratorPower:
            labels = self.generator_names
            y = self.generator_power
            y_label = '(MW)'
            title = 'Controlled generator power'

        elif result_type == ResultTypes.ControlledGeneratorShedding:
            labels = self.generator_names
            y = self.generator_shedding
            y_label = '(MW)'
            title = 'Controlled generator power'

        elif result_type == ResultTypes.BatteryPower:
            labels = self.battery_names
            y = self.battery_power
            y_label = '(MW)'
            title = 'Battery power'

        elif result_type == ResultTypes.BatteryEnergy:
            labels = self.battery_names
            y = self.battery_energy
            y_label = '(MWh)'
            title = 'Battery energy'

        else:
            labels = ''
            y_label = ''
            title = ''
            y = np.zeros(0)

        if self.time is not None:
            index = self.time
        else:
            index = np.arange(0, y.shape[0], 1)

        mdl = ResultsModel(data=y, index=index, columns=labels, title=title,
                           ylabel=y_label, xlabel='', units=y_label)
        return mdl
