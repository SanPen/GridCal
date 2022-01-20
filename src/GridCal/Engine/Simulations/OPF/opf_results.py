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

import numpy as np
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate


class OptimalPowerFlowResults(ResultsTemplate):
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
                 Sbus=None, voltage=None, load_shedding=None, generator_shedding=None,
                 battery_power=None, controlled_generation_power=None,
                 Sf=None, St=None, overloads=None, loading=None, losses=None,
                 hvdc_names=None, hvdc_power=None, hvdc_loading=None,
                 phase_shift=None, bus_shadow_prices=None,
                 contingency_flows_list=None, contingency_indices_list=None, contingency_flows_slacks_list=None,
                 rates=None, contingency_rates=None,
                 converged=None, bus_types=None):

        ResultsTemplate.__init__(self,
                                 name='OPF',
                                 available_results=[ResultTypes.BusVoltageModule,
                                                    ResultTypes.BusVoltageAngle,
                                                    ResultTypes.BusShadowPrices,
                                                    ResultTypes.BusPower,
                                                    ResultTypes.BranchActivePowerFrom,
                                                    ResultTypes.BranchLoading,
                                                    ResultTypes.BranchOverloads,
                                                    ResultTypes.BranchTapAngle,

                                                    ResultTypes.ContingencyFlowsReport,

                                                    ResultTypes.HvdcPowerFrom,
                                                    ResultTypes.HvdcLoading,

                                                    ResultTypes.LoadShedding,
                                                    ResultTypes.GeneratorShedding,
                                                    ResultTypes.GeneratorPower,
                                                    ResultTypes.BatteryPower],
                                 data_variables=['bus_names',
                                                 'branch_names',
                                                 'load_names',
                                                 'generator_names',
                                                 'battery_names',
                                                 'Sbus',
                                                 'voltage',
                                                 'load_shedding',
                                                 'generator_shedding',
                                                 'Sf',
                                                 'bus_types',
                                                 'overloads',
                                                 'loading',
                                                 'hvdc_names',
                                                 'hvdc_Pf',
                                                 'hvdc_loading',
                                                 'phase_shift',
                                                 'battery_power',
                                                 'generator_power',
                                                 'converged'])

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.load_names = load_names
        self.generator_names = generator_names
        self.battery_names = battery_names

        self.Sbus = Sbus

        self.voltage = voltage

        self.load_shedding = load_shedding

        self.Sf = Sf

        self.St = St

        self.bus_types = bus_types

        self.overloads = overloads

        self.loading = loading

        self.losses = losses

        self.hvdc_names = hvdc_names
        self.hvdc_Pf = hvdc_power
        self.hvdc_loading = hvdc_loading

        self.phase_shift = phase_shift

        self.battery_power = battery_power

        self.generator_shedding = generator_shedding

        self.generator_power = controlled_generation_power

        self.bus_shadow_prices = bus_shadow_prices

        self.contingency_flows_list = contingency_flows_list
        self.contingency_indices_list = contingency_indices_list  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = contingency_flows_slacks_list

        self.rates = rates
        self.contingency_rates = contingency_rates

        self.converged = converged

        self.plot_bars_limit = 100

    def apply_new_rates(self, nc: "SnapshotData"):
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
        """
        columns = [result_type.value[0]]

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

        elif result_type == ResultTypes.BusShadowPrices:
            labels = self.bus_names
            y = self.bus_shadow_prices
            y_label = '(Currency/MW)'
            title = 'Bus shadow prices'

        elif result_type == ResultTypes.BranchActivePowerFrom:
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
            y = self.loading * 100.0
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

        elif result_type == ResultTypes.BranchTapAngle:
            labels = self.branch_names
            y = np.rad2deg(self.phase_shift)
            y_label = '(deg)'
            title = result_type.value[0]

        elif result_type == ResultTypes.LoadShedding:
            labels = self.load_names
            y = self.load_shedding
            y_label = '(MW)'
            title = 'Load shedding'

        elif result_type == ResultTypes.GeneratorShedding:
            labels = self.generator_names
            y = self.generator_shedding
            y_label = '(MW)'
            title = 'Controlled generator shedding'

        elif result_type == ResultTypes.GeneratorPower:
            labels = self.generator_names
            y = self.generator_power
            y_label = '(MW)'
            title = 'Controlled generators power'

        elif result_type == ResultTypes.BatteryPower:
            labels = self.battery_names
            y = self.battery_power
            y_label = '(MW)'
            title = 'Battery power'

        elif result_type == ResultTypes.HvdcPowerFrom:
            labels = self.hvdc_names
            y = self.hvdc_Pf
            y_label = '(MW)'
            title = 'HVDC power'

        elif result_type == ResultTypes.ContingencyFlowsReport:

            y = list()
            labels = list()
            for i in range(len(self.contingency_flows_list)):
                if self.contingency_flows_list[i] != 0.0:
                    m, c = self.contingency_indices_list[i]
                    y.append((m, c,
                              self.branch_names[m], self.branch_names[c],
                              self.contingency_flows_list[i], self.Sf[m],
                              self.contingency_flows_list[i] / self.contingency_rates[c] * 100,
                              self.Sf[m] / self.rates[m] * 100))
                    labels.append(i)

            columns = ['Monitored idx ', 'Contingency idx',
                       'Monitored', 'Contingency',
                       'ContingencyFlow (MW)', 'Base flow (MW)',
                       'ContingencyFlow (%)', 'Base flow (%)']
            y = np.array(y, dtype=object)
            y_label = ''
            title = result_type.value[0]

        else:
            labels = []
            y = np.zeros(0)
            y_label = '(MW)'
            title = 'Battery power'

        mdl = ResultsTable(data=y,
                           index=labels,
                           columns=columns,
                           title=title,
                           ylabel=y_label,
                           xlabel='',
                           units=y_label)
        return mdl

