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
from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import DateVec, IntVec, Vec, StrVec, CxMat, Mat, BoolVec
from GridCalEngine.enumerations import StudyResultsType


class OptimalPowerFlowTimeSeriesResults(ResultsTemplate):
    """
    Optimal power flow time series results
    """

    def __init__(self, bus_names, branch_names, load_names, generator_names, battery_names, hvdc_names,
                 n, m, nt, ngen=0, nbat=0, nload=0, nhvdc=0, time_array=None, bus_types=(), clustering_results=None):
        """
        OPF Time Series results constructor
        :param n: number of buses
        :param m: number of Branches
        :param nt: number of time steps
        :param ngen:
        :param nbat:
        :param nload:
        :param time_array: Time array (optional)
        """
        ResultsTemplate.__init__(self,
                                 name='OPF time series',
                                 available_results={ResultTypes.BusResults: [ResultTypes.BusVoltageModule,
                                                                             ResultTypes.BusVoltageAngle,
                                                                             ResultTypes.BusShadowPrices],

                                                    ResultTypes.GeneratorResults: [ResultTypes.GeneratorPower,
                                                                                   ResultTypes.GeneratorShedding],

                                                    ResultTypes.BatteryResults: [ResultTypes.BatteryPower,
                                                                                 ResultTypes.BatteryEnergy],

                                                    ResultTypes.LoadResults: [ResultTypes.LoadShedding],

                                                    ResultTypes.BranchResults: [ResultTypes.BranchPower,
                                                                                ResultTypes.BranchLoading,
                                                                                ResultTypes.BranchOverloads,
                                                                                ResultTypes.BranchTapAngle],

                                                    ResultTypes.ReportsResults: [ResultTypes.ContingencyFlowsReport],

                                                    ResultTypes.HvdcResults: [ResultTypes.HvdcPowerFrom,
                                                                              ResultTypes.HvdcLoading],

                                                    },
                                 time_array=time_array,
                                 clustering_results=clustering_results,
                                 study_results_type=StudyResultsType.OptimalPowerFlowTimeSeries)

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.load_names = load_names
        self.generator_names = generator_names
        self.battery_names = battery_names
        self.hvdc_names = hvdc_names
        self.bus_types = bus_types

        self.voltage = np.zeros((nt, n), dtype=complex)
        self.load_shedding = np.zeros((nt, nload), dtype=float)
        self.loading = np.zeros((nt, m), dtype=float)
        self.losses = np.zeros((nt, m), dtype=float)
        self.overloads = np.zeros((nt, m), dtype=float)
        self.Sbus = np.zeros((nt, n), dtype=complex)
        self.bus_shadow_prices = np.zeros((nt, n), dtype=float)
        self.Sf = np.zeros((nt, m), dtype=complex)
        self.St = np.zeros((nt, m), dtype=complex)
        self.hvdc_Pf = np.zeros((nt, nhvdc), dtype=float)
        self.hvdc_loading = np.zeros((nt, nhvdc), dtype=float)
        self.phase_shift = np.zeros((nt, m), dtype=float)
        self.generator_power = np.zeros((nt, ngen), dtype=float)
        self.generator_shedding = np.zeros((nt, ngen), dtype=float)
        self.battery_power = np.zeros((nt, nbat), dtype=float)
        self.battery_energy = np.zeros((nt, nbat), dtype=float)
        self.rates = np.zeros(m)
        self.contingency_rates = np.zeros(m)
        self.converged = np.empty(nt, dtype=bool)
        self.contingency_flows_list = list()
        self.contingency_indices_list = list()  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = list()

        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='load_names', tpe=StrVec)
        self.register(name='generator_names', tpe=StrVec)
        self.register(name='battery_names', tpe=StrVec)
        self.register(name='hvdc_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='voltage', tpe=CxMat)
        self.register(name='load_shedding', tpe=Mat)
        self.register(name='loading', tpe=Mat)
        self.register(name='losses', tpe=Mat)
        self.register(name='overloads', tpe=Mat)
        self.register(name='Sbus', tpe=CxMat)
        self.register(name='bus_shadow_prices', tpe=Mat)
        self.register(name='Sf', tpe=CxMat)
        self.register(name='St', tpe=CxMat)
        self.register(name='hvdc_Pf', tpe=Mat)
        self.register(name='hvdc_loading', tpe=Mat)
        self.register(name='phase_shift', tpe=Mat)
        self.register(name='generator_power', tpe=Mat)
        self.register(name='generator_shedding', tpe=Mat)
        self.register(name='battery_power', tpe=Mat)
        self.register(name='battery_energy', tpe=Mat)
        self.register(name='rates', tpe=Vec)
        self.register(name='contingency_rates', tpe=Vec)
        self.register(name='converged', tpe=BoolVec)
        self.register(name='contingency_flows_list', tpe=list)
        self.register(name='contingency_indices_list', tpe=list)
        self.register(name='contingency_flows_slacks_list', tpe=list)

    def apply_new_time_series_rates(self, nc: "NumericalCircuit"):
        """

        :param nc:
        """
        rates = nc.Rates.T
        self.loading = self.Sf / (rates + 1e-9)

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

    def apply_lp_profiles(self, circuit: MultiCircuit):
        """
        Apply the LP results as device profiles.
        """
        generators = circuit.get_generators()
        for i, elm in enumerate(generators):
            pr = self.generator_power[:, i]
            if len(pr) == circuit.get_time_number():
                elm.P_prof = pr

        batteries = circuit.get_batteries()
        for i, elm in enumerate(batteries):
            pr = self.battery_power[:, i]
            if len(pr) == circuit.get_time_number():
                elm.P_prof = pr

        loads = circuit.get_loads()
        for i, elm in enumerate(loads):
            pr = self.load_shedding[:, i]
            if len(pr) == circuit.get_time_number():
                elm.P_prof -= pr

        # TODO: implement more devices

    def mdl(self, result_type) -> "ResultsTable":
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

        elif result_type == ResultTypes.BusShadowPrices:
            labels = self.bus_names
            y = self.bus_shadow_prices
            y_label = '(currency / MW)'
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

        elif result_type == ResultTypes.BranchTapAngle:
            labels = self.branch_names
            # y = np.rad2deg(self.phase_shift)
            # y_label = '(deg)'
            y = self.phase_shift
            y_label = '(rad)'
            title = 'Branch tap angle '

        elif result_type == ResultTypes.HvdcPowerFrom:
            labels = self.hvdc_names
            y = self.hvdc_Pf
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.HvdcLoading:
            labels = self.hvdc_names
            y = self.hvdc_loading * 100.0
            y_label = '(%)'
            title = result_type.value[0]

        elif result_type == ResultTypes.LoadShedding:
            labels = self.load_names
            y = self.load_shedding
            y_label = '(MW)'
            title = 'Load shedding'

        elif result_type == ResultTypes.GeneratorPower:
            labels = self.generator_names
            y = self.generator_power
            y_label = '(MW)'
            title = 'Controlled generator power'

        elif result_type == ResultTypes.GeneratorShedding:
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

        elif result_type == ResultTypes.ContingencyFlowsReport:
            y = list()
            index = list()
            for i in range(len(self.contingency_flows_list)):
                if self.contingency_flows_list[i] != 0.0:
                    t, m, c = self.contingency_indices_list[i]
                    y.append((t, m, c,
                              str(self.time_array[t]), self.branch_names[m], self.branch_names[c],
                              self.contingency_flows_list[i], self.Sf[t, m].real,
                              self.contingency_flows_list[i] / self.contingency_rates[c, t] * 100,
                              self.Sf[t, m].real / self.rates[m, t] * 100))
                    index.append(i)

            labels = ['Time index', 'Monitored idx ', 'Contingency idx',
                      'Time', 'Monitored', 'Contingency',
                      'ContingencyFlow (MW)', 'Base flow (MW)',
                      'ContingencyFlow (%)', 'Base flow (%)']
            y = np.array(y, dtype=object)
            y_label = ''
            title = result_type.value[0]

            return ResultsTable(data=y, index=index, columns=labels, title=title,
                                ylabel=y_label, xlabel='', units=y_label)

        else:
            labels = ''
            y_label = ''
            title = ''
            y = np.zeros(0)

        if self.time_array is not None:
            index = pd.to_datetime(self.time_array)
        else:
            index = np.arange(0, y.shape[0], 1)

        mdl = ResultsTable(data=y, index=index, columns=labels, title=title,
                           ylabel=y_label, xlabel='', units=y_label)
        return mdl
