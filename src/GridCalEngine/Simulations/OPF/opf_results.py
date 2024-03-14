# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.basic_structures import IntVec, Vec, StrVec, CxVec
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class OptimalPowerFlowResults(ResultsTemplate):

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
        """
        Constructor
        :param bus_names:
        :param branch_names:
        :param load_names:
        :param generator_names:
        :param battery_names:
        :param hvdc_names:
        :param bus_types:
        :param area_names:
        :param F:
        :param T:
        :param F_hvdc:
        :param T_hvdc:
        :param bus_area_indices:
        """

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
        if result_type == ResultTypes.BusVoltageModule:

            return ResultsTable(data=np.abs(self.voltage),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(p.u.)',
                                xlabel='',
                                units='(p.u.)')

        elif result_type == ResultTypes.BusVoltageAngle:

            return ResultsTable(data=np.angle(self.voltage, deg=True),
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(deg)',
                                xlabel='',
                                units='(deg)')

        elif result_type == ResultTypes.BusShadowPrices:

            return ResultsTable(data=self.bus_shadow_prices,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(Currency/MW)',
                                xlabel='',
                                units='(Currency/MW)')

        elif result_type == ResultTypes.BusActivePower:

            return ResultsTable(data=self.Sbus.real,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BusReactivePower:

            return ResultsTable(data=self.Sbus.imag,
                                index=self.bus_names,
                                idx_device_type=DeviceType.BusDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MVAr)',
                                xlabel='',
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActivePowerFrom:

            return ResultsTable(data=self.Sf.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BranchActivePowerTo:

            return ResultsTable(data=self.St.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BranchLoading:

            return ResultsTable(data=self.loading * 100.0,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(%)',
                                xlabel='',
                                units='(%)')

        elif result_type == ResultTypes.BranchOverloads:

            return ResultsTable(data=np.abs(self.overloads),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BranchLosses:

            return ResultsTable(data=self.losses.real,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BranchTapAngle:

            return ResultsTable(data=np.rad2deg(self.phase_shift),
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(deg)',
                                xlabel='',
                                units='(deg)')

        elif result_type == ResultTypes.LoadShedding:

            return ResultsTable(data=self.load_shedding,
                                index=self.load_names,
                                idx_device_type=DeviceType.LoadLikeDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.GeneratorShedding:

            return ResultsTable(data=self.generator_shedding,
                                index=self.generator_names,
                                idx_device_type=DeviceType.GeneratorDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.GeneratorPower:

            return ResultsTable(data=self.generator_power,
                                index=self.generator_names,
                                idx_device_type=DeviceType.GeneratorDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BatteryPower:

            return ResultsTable(data=self.battery_power,
                                index=self.battery_names,
                                idx_device_type=DeviceType.BatteryDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcPowerFrom:

            return ResultsTable(data=self.hvdc_Pf,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcLoading:

            return ResultsTable(data=self.hvdc_loading * 100.0,
                                index=self.hvdc_names,
                                idx_device_type=DeviceType.HVDCLineDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                ylabel='(%)',
                                xlabel='',
                                units='(%)')

        elif result_type == ResultTypes.ContingencyFlowsReport:

            y = list()
            index = list()
            for i in range(len(self.contingency_flows_list)):
                if self.contingency_flows_list[i] != 0.0:
                    m, c = self.contingency_indices_list[i]
                    y.append((m, c,
                              self.branch_names[m], self.branch_names[c],
                              self.contingency_flows_list[i], self.Sf[m],
                              self.contingency_flows_list[i] / self.contingency_rates[c] * 100,
                              self.Sf[m] / self.rates[m] * 100))
                    index.append(i)

            columns = ['Monitored idx ', 'Contingency idx',
                       'Monitored', 'Contingency',
                       'ContingencyFlow (MW)', 'Base flow (MW)',
                       'ContingencyFlow (%)', 'Base flow (%)']

            return ResultsTable(data=np.array(y, dtype=object),
                                index=index,
                                idx_device_type=DeviceType.NoDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value))

        elif result_type == ResultTypes.InterAreaExchange:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            y = self.get_inter_area_flows(area_names=self.area_names,
                                          F=self.F,
                                          T=self.T,
                                          Sf=self.Sf,
                                          hvdc_F=self.hvdc_F,
                                          hvdc_T=self.hvdc_T,
                                          hvdc_Pf=self.hvdc_Pf,
                                          bus_area_indices=self.bus_area_indices).real

            return ResultsTable(data=np.array(y, dtype=object),
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=str(result_type.value),
                                units='(MW)')

        elif result_type == ResultTypes.LossesPercentPerArea:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            Pf = self.get_branch_values_per_area(np.abs(self.Sf.real), self.area_names,
                                                 self.bus_area_indices, self.F, self.T)
            Pf += self.get_hvdc_values_per_area(np.abs(self.hvdc_Pf), self.area_names, self.bus_area_indices,
                                                self.hvdc_F, self.hvdc_T)
            Pl = self.get_branch_values_per_area(np.abs(self.losses.real), self.area_names, self.bus_area_indices,
                                                 self.F, self.T)
            # Pl += self.get_hvdc_values_per_area(np.abs(self.hvdc_losses))

            y = Pl / (Pf + 1e-20) * 100.0

            return ResultsTable(data=np.array(y, dtype=object),
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=str(result_type.value),
                                units='(%)')

        elif result_type == ResultTypes.LossesPerGenPerArea:
            index = [a for a in self.area_names]
            columns = [result_type.value]
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

            return ResultsTable(data=np.array(y, dtype=object),
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=str(result_type.value),
                                units='(%)')

        elif result_type == ResultTypes.LossesPerArea:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            y = self.get_branch_values_per_area(np.abs(self.losses.real), self.area_names, self.bus_area_indices,
                                                self.F, self.T)
            y += self.get_hvdc_values_per_area(np.abs(self.hvdc_losses), self.area_names, self.bus_area_indices,
                                               self.hvdc_F, self.hvdc_T)

            return ResultsTable(data=np.array(y, dtype=object),
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=str(result_type.value),
                                units='(%)')

        elif result_type == ResultTypes.ActivePowerFlowPerArea:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            y = self.get_branch_values_per_area(np.abs(self.Sf.real), self.area_names, self.bus_area_indices,
                                                self.F, self.T)
            y += self.get_hvdc_values_per_area(np.abs(self.hvdc_Pf), self.area_names, self.bus_area_indices,
                                               self.hvdc_F, self.hvdc_T)

            return ResultsTable(data=np.array(y, dtype=object),
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=str(result_type.value),
                                units='(MW)')

        else:
            raise Exception('Result type not understood:' + str(result_type))
