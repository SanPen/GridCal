# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import pandas as pd
from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.basic_structures import IntVec, Vec, StrVec, CxVec
from GridCalEngine.enumerations import StudyResultsType


class OptimalPowerFlowResults(ResultsTemplate):
    """
    OPF results.

    Arguments:

        **Sbus**: bus power Injections

        **voltage**: bus voltages

        **load_shedding**: load shedding values

        **Sf**: branch power values

        **overloads**: branch overloading values

        **loading**: branch loading values

        **losses**: branch losses

        **converged**: converged?
    """

    def __init__(self,
                 bus_names: StrVec,
                 branch_names: StrVec,
                 load_names: StrVec,
                 generator_names: StrVec,
                 battery_names: StrVec,
                 hvdc_names: StrVec,
                 bus_types: IntVec,
                 area_names: StrVec,
                 F: IntVec,
                 T: IntVec,
                 F_hvdc: IntVec,
                 T_hvdc: IntVec,
                 bus_area_indices: IntVec):

        ResultsTemplate.__init__(self,
                                 name='OPF',
                                 available_results={ResultTypes.BusResults: [ResultTypes.BusVoltageModule,
                                                                             ResultTypes.BusVoltageAngle,
                                                                             ResultTypes.BusShadowPrices,
                                                                             ResultTypes.BusActivePower,
                                                                             ResultTypes.BusReactivePower],

                                                    ResultTypes.GeneratorResults: [ResultTypes.GeneratorPower,
                                                                                   ResultTypes.GeneratorShedding],

                                                    ResultTypes.BatteryResults: [ResultTypes.BatteryPower],

                                                    ResultTypes.LoadResults: [ResultTypes.LoadShedding],

                                                    ResultTypes.BranchResults: [ResultTypes.BranchActivePowerFrom,
                                                                                ResultTypes.BranchActivePowerTo,
                                                                                ResultTypes.BranchLoading,
                                                                                ResultTypes.BranchLosses,
                                                                                ResultTypes.BranchOverloads,
                                                                                ResultTypes.BranchTapAngle],

                                                    ResultTypes.HvdcResults: [ResultTypes.HvdcPowerFrom,
                                                                              ResultTypes.HvdcLoading],

                                                    ResultTypes.ReportsResults: [ResultTypes.ContingencyFlowsReport],

                                                    ResultTypes.AreaResults: [ResultTypes.InterAreaExchange,
                                                                              ResultTypes.ActivePowerFlowPerArea,
                                                                              ResultTypes.LossesPerArea,
                                                                              ResultTypes.LossesPercentPerArea,
                                                                              ResultTypes.LossesPerGenPerArea]
                                                    },
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.OptimalPowerFlow)

        n = len(bus_names)
        m = len(branch_names)
        ngen = len(generator_names)
        nbat = len(battery_names)
        nload = len(load_names)
        nhvdc = len(hvdc_names)

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.load_names = load_names
        self.generator_names = generator_names
        self.battery_names = battery_names
        self.hvdc_names = hvdc_names
        self.bus_types = bus_types

        self.voltage = np.zeros(n, dtype=complex)
        self.Sbus = np.zeros(n, dtype=complex)
        self.bus_shadow_prices = np.zeros(n, dtype=float)

        self.load_shedding = np.zeros(nload, dtype=float)

        self.Sf = np.zeros(m, dtype=float)
        self.St = np.zeros(m, dtype=float)
        self.overloads = np.zeros(m, dtype=float)
        self.loading = np.zeros(m, dtype=float)
        self.losses = np.zeros(m, dtype=float)
        self.phase_shift = np.zeros(m, dtype=float)
        self.rates = np.zeros(m, dtype=float)
        self.contingency_rates = np.zeros(m, dtype=float)

        self.hvdc_Pf = np.zeros(nhvdc, dtype=float)
        self.hvdc_loading = np.zeros(nhvdc, dtype=float)
        self.hvdc_losses = np.zeros(nhvdc, dtype=float)

        self.generator_shedding = np.zeros(ngen, dtype=float)
        self.generator_power = np.zeros(ngen, dtype=float)
        self.battery_power = np.zeros(nbat, dtype=float)

        self.contingency_flows_list = list()
        self.contingency_indices_list = list()  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = list()

        self.converged = False

        # vars for the inter-area computation
        self.F = F
        self.T = T
        self.hvdc_F = F_hvdc
        self.hvdc_T = T_hvdc
        self.bus_area_indices = bus_area_indices
        self.area_names = area_names

        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='load_names', tpe=StrVec)
        self.register(name='generator_names', tpe=StrVec)
        self.register(name='battery_names', tpe=StrVec)
        self.register(name='hvdc_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='voltage', tpe=CxVec)
        self.register(name='Sbus', tpe=CxVec)
        self.register(name='bus_shadow_prices', tpe=Vec)

        self.register(name='load_shedding', tpe=Vec)

        self.register(name='Sf', tpe=CxVec)
        self.register(name='St', tpe=CxVec)
        self.register(name='overloads', tpe=Vec)
        self.register(name='loading', tpe=Vec)
        self.register(name='losses', tpe=Vec)
        self.register(name='phase_shift', tpe=Vec)
        self.register(name='rates', tpe=Vec)
        self.register(name='contingency_rates', tpe=Vec)

        self.register(name='hvdc_Pf', tpe=Vec)
        self.register(name='hvdc_loading', tpe=Vec)
        self.register(name='hvdc_losses', tpe=Vec)

        self.register(name='generator_power', tpe=Vec)
        self.register(name='generator_shedding', tpe=Vec)
        self.register(name='battery_power', tpe=Vec)

        self.register(name='converged', tpe=bool)
        self.register(name='contingency_flows_list', tpe=list)
        self.register(name='contingency_indices_list', tpe=list)
        self.register(name='contingency_flows_slacks_list', tpe=list)

        self.register(name='F', tpe=IntVec)
        self.register(name='T', tpe=IntVec)
        self.register(name='hvdc_F', tpe=IntVec)
        self.register(name='hvdc_T', tpe=IntVec)
        self.register(name='bus_area_indices', tpe=IntVec)
        self.register(name='area_names', tpe=IntVec)

        self.plot_bars_limit = 100

    def apply_new_rates(self, nc: "NumericalCircuit"):
        """

        :param nc:
        """
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

    def fill_circuit_info(self, grid: "MultiCircuit"):
        """

        :param grid:
        """
        area_dict = {elm: i for i, elm in enumerate(grid.get_areas())}
        bus_dict = grid.get_bus_index_dict()

        self.area_names = [a.name for a in grid.get_areas()]
        self.bus_area_indices = np.array([area_dict[b.area] for b in grid.buses])

        branches = grid.get_branches_wo_hvdc()
        self.F = np.zeros(len(branches), dtype=int)
        self.T = np.zeros(len(branches), dtype=int)
        for k, elm in enumerate(branches):
            self.F[k] = bus_dict[elm.bus_from]
            self.T[k] = bus_dict[elm.bus_to]

        hvdc = grid.get_hvdc()
        self.hvdc_F = np.zeros(len(hvdc), dtype=int)
        self.hvdc_T = np.zeros(len(hvdc), dtype=int)
        for k, elm in enumerate(hvdc):
            self.hvdc_F[k] = bus_dict[elm.bus_from]
            self.hvdc_T[k] = bus_dict[elm.bus_to]

    def get_bus_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the buses results
        :return: DataFrame
        """
        return pd.DataFrame(data={'Va': np.angle(self.voltage, deg=True),
                                  'P': self.Sbus.real,
                                  'Shadow price': self.bus_shadow_prices},
                            index=self.bus_names)

    def get_branch_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the branches results
        :return: DataFrame
        """
        return pd.DataFrame(data={'Pf': self.Sf.real,
                                  'Pt': self.St.real,
                                  'Tap angle': self.phase_shift,
                                  'loading': self.loading.real * 100.0},
                            index=self.branch_names)

    def get_gen_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the generator results
        :return: DataFrame
        """
        return pd.DataFrame(data={'P': self.generator_power,
                                  'P shedding': self.generator_shedding},
                            index=self.generator_names)

    def get_batt_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the battery results
        :return: DataFrame
        """
        return pd.DataFrame(data={'P': self.generator_power},
                            index=self.battery_power)

    def get_hvdc_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the battery results
        :return: DataFrame
        """
        return pd.DataFrame(data={'P': self.hvdc_Pf,
                                  'Loading': self.hvdc_loading},
                            index=self.hvdc_names)

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
            title = 'Branch power from'

        elif result_type == ResultTypes.BranchActivePowerTo:
            labels = self.branch_names
            y = self.St.real
            y_label = '(MW)'
            title = 'Branch power to'

        elif result_type == ResultTypes.BusActivePower:
            labels = self.bus_names
            y = self.Sbus.real
            y_label = '(MW)'
            title = 'Bus active power'

        elif result_type == ResultTypes.BusReactivePower:
            labels = self.bus_names
            y = self.Sbus.imag
            y_label = '(MVAr)'
            title = 'Bus reactive power'

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

        elif result_type == ResultTypes.HvdcLoading:
            labels = self.hvdc_names
            y = self.hvdc_loading * 100.0
            y_label = '(%)'
            title = 'HVDC loading'

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

        elif result_type == ResultTypes.InterAreaExchange:
            labels = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            y = self.get_inter_area_flows(area_names=self.area_names,
                                          F=self.F,
                                          T=self.T,
                                          Sf=self.Sf,
                                          hvdc_F=self.hvdc_F,
                                          hvdc_T=self.hvdc_T,
                                          hvdc_Pf=self.hvdc_Pf,
                                          bus_area_indices=self.bus_area_indices).real
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.LossesPercentPerArea:
            labels = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            Pf = self.get_branch_values_per_area(np.abs(self.Sf.real), self.area_names, self.bus_area_indices, self.F,
                                                 self.T)
            Pf += self.get_hvdc_values_per_area(np.abs(self.hvdc_Pf), self.area_names, self.bus_area_indices,
                                                self.hvdc_F, self.hvdc_T)
            Pl = self.get_branch_values_per_area(np.abs(self.losses.real), self.area_names, self.bus_area_indices,
                                                 self.F, self.T)
            # Pl += self.get_hvdc_values_per_area(np.abs(self.hvdc_losses))

            y = Pl / (Pf + 1e-20) * 100.0
            y_label = '(%)'
            title = result_type.value[0]

        elif result_type == ResultTypes.LossesPerGenPerArea:
            labels = [a for a in self.area_names]
            columns = [result_type.value[0]]
            gen_bus = self.Sbus.copy().real
            gen_bus[gen_bus < 0] = 0
            Gf = self.get_bus_values_per_area(gen_bus, self.area_names, self.bus_area_indices)
            Pl = self.get_branch_values_per_area(np.abs(self.losses.real), self.area_names, self.bus_area_indices,
                                                 self.F, self.T)
            Pl += self.get_hvdc_values_per_area(np.abs(self.hvdc_losses), self.area_names, self.bus_area_indices,
                                                self.hvdc_F, self.hvdc_T)

            y = np.zeros(len(self.area_names))
            for i in range(len(self.area_names)):
                y[i] = Pl[i, i] / (Gf[i] + 1e-20) * 100.0

            y_label = '(%)'
            title = result_type.value[0]

        elif result_type == ResultTypes.LossesPerArea:
            labels = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            y = self.get_branch_values_per_area(np.abs(self.losses.real), self.area_names, self.bus_area_indices,
                                                self.F, self.T)
            y += self.get_hvdc_values_per_area(np.abs(self.hvdc_losses), self.area_names, self.bus_area_indices,
                                               self.hvdc_F, self.hvdc_T)

            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.ActivePowerFlowPerArea:
            labels = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            y = self.get_branch_values_per_area(np.abs(self.Sf.real), self.area_names, self.bus_area_indices, self.F,
                                                self.T)
            y += self.get_hvdc_values_per_area(np.abs(self.hvdc_Pf), self.area_names, self.bus_area_indices,
                                               self.hvdc_F, self.hvdc_T)

            y_label = '(MW)'
            title = result_type.value[0]

        else:
            labels = []
            y = np.zeros(0)
            y_label = '(MW)'
            title = 'Battery power'

        mdl = ResultsTable(data=y,
                           index=np.array(labels),
                           columns=np.array(columns),
                           title=title,
                           ylabel=y_label,
                           xlabel='',
                           units=y_label)
        return mdl
