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
from __future__ import annotations
from typing import Union, TYPE_CHECKING
import numpy as np
import pandas as pd
from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import IntVec, Vec, StrVec, CxMat, Mat, BoolVec
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults
    from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit


class OptimalPowerFlowTimeSeriesResults(ResultsTemplate):
    """
    Optimal power flow time series results
    """

    def __init__(self,
                 bus_names: StrVec,
                 branch_names: StrVec,
                 load_names: StrVec,
                 generator_names: StrVec,
                 battery_names: StrVec,
                 hvdc_names: StrVec,
                 fuel_names: StrVec,
                 emission_names: StrVec,
                 fluid_node_names: StrVec,
                 fluid_path_names: StrVec,
                 fluid_injection_names: StrVec,
                 n: int,
                 m: int,
                 nt: int,
                 ngen: int = 0,
                 nbat: int = 0,
                 nload: int = 0,
                 nhvdc: int = 0,
                 n_fluid_node: int = 0,
                 n_fluid_path: int = 0,
                 n_fluid_injection: int = 0,
                 time_array=None,
                 bus_types=(),
                 clustering_results: Union[None, ClusteringResults] = None):
        """
        OPF Time Series results constructor
        :param bus_names:
        :param branch_names:
        :param load_names:
        :param generator_names:
        :param battery_names:
        :param hvdc_names:
        :param fuel_names:
        :param emission_names:
        :param fluid_node_names:
        :param fluid_path_names:
        :param fluid_injection_names:
        :param n: number of buses
        :param m: number of Branches
        :param nt: number of time steps
        :param ngen: number of generators
        :param nbat: number of batteries
        :param nload: number of loads
        :param nhvdc: number of HVDC lines
        :param n_fluid_node: number of fluid nodes
        :param n_fluid_path: number of fluid paths
        :param n_fluid_injection: number of fluid injections
        :param time_array: Time array (optional)
        :param bus_types: array of bus types
        :param clustering_results:
        """
        ResultsTemplate.__init__(self,
                                 name='OPF time series',
                                 available_results={ResultTypes.BusResults: [ResultTypes.BusVoltageModule,
                                                                             ResultTypes.BusVoltageAngle,
                                                                             ResultTypes.BusShadowPrices],

                                                    ResultTypes.GeneratorResults: [ResultTypes.GeneratorPower,
                                                                                   ResultTypes.GeneratorShedding,
                                                                                   ResultTypes.GeneratorCost,
                                                                                   ResultTypes.GeneratorProducing,
                                                                                   ResultTypes.GeneratorStartingUp,
                                                                                   ResultTypes.GeneratorShuttingDown
                                                                                   ],

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

                                                    ResultTypes.FluidNodeResults: [ResultTypes.FluidCurrentLevel,
                                                                                   ResultTypes.FluidFlowIn,
                                                                                   ResultTypes.FluidFlowOut,
                                                                                   ResultTypes.FluidP2XFlow,
                                                                                   ResultTypes.FluidSpillage],

                                                    ResultTypes.FluidPathResults: [ResultTypes.FluidFlowPath],

                                                    ResultTypes.FluidInjectionResults: [ResultTypes.FluidFlowInjection],

                                                    ResultTypes.SystemResults: [ResultTypes.SystemFuel,
                                                                                ResultTypes.SystemEmissions,
                                                                                ResultTypes.SystemEnergyCost]
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
        self.fuel_names = fuel_names
        self.emission_names = emission_names
        self.bus_types = bus_types
        self.fluid_node_names = fluid_node_names
        self.fluid_path_names = fluid_path_names
        self.fluid_injection_names = fluid_injection_names

        nfuels = len(fuel_names)
        nemissions = len(emission_names)

        self.voltage = np.zeros((nt, n), dtype=complex)
        self.Sbus = np.zeros((nt, n), dtype=complex)
        self.bus_shadow_prices = np.zeros((nt, n), dtype=float)

        self.Sf = np.zeros((nt, m), dtype=complex)
        self.St = np.zeros((nt, m), dtype=complex)
        self.loading = np.zeros((nt, m), dtype=float)
        self.losses = np.zeros((nt, m), dtype=float)
        self.phase_shift = np.zeros((nt, m), dtype=float)
        self.overloads = np.zeros((nt, m), dtype=float)
        self.rates = np.zeros(m)
        self.contingency_rates = np.zeros(m)
        self.contingency_flows_list = list()
        self.contingency_indices_list = list()  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = list()

        self.hvdc_Pf = np.zeros((nt, nhvdc), dtype=float)
        self.hvdc_loading = np.zeros((nt, nhvdc), dtype=float)

        self.load_shedding = np.zeros((nt, nload), dtype=float)

        self.generator_power = np.zeros((nt, ngen), dtype=float)
        self.generator_shedding = np.zeros((nt, ngen), dtype=float)
        self.generator_cost = np.zeros((nt, ngen), dtype=float)
        self.generator_producing = np.zeros((nt, ngen), dtype=bool)
        self.generator_starting_up = np.zeros((nt, ngen), dtype=bool)
        self.generator_shutting_down = np.zeros((nt, ngen), dtype=bool)

        self.battery_power = np.zeros((nt, nbat), dtype=float)
        self.battery_energy = np.zeros((nt, nbat), dtype=float)

        self.fluid_node_current_level = np.zeros((nt, n_fluid_node), dtype=float)
        self.fluid_node_flow_in = np.zeros((nt, n_fluid_node), dtype=float)
        self.fluid_node_flow_out = np.zeros((nt, n_fluid_node), dtype=float)
        self.fluid_node_p2x_flow = np.zeros((nt, n_fluid_node), dtype=float)
        self.fluid_node_spillage = np.zeros((nt, n_fluid_node), dtype=float)

        self.fluid_path_flow = np.zeros((nt, n_fluid_path), dtype=float)
        self.fluid_injection_flow = np.zeros((nt, n_fluid_injection), dtype=float)

        self.converged = np.empty(nt, dtype=bool)
        self.system_fuel = np.empty((nt, nemissions), dtype=float)
        self.system_emissions = np.empty((nt, nfuels), dtype=float)
        self.system_energy_cost = np.empty(nt, dtype=float)

        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='load_names', tpe=StrVec)
        self.register(name='generator_names', tpe=StrVec)
        self.register(name='battery_names', tpe=StrVec)
        self.register(name='hvdc_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)

        self.register(name='voltage', tpe=CxMat)
        self.register(name='Sbus', tpe=CxMat)
        self.register(name='bus_shadow_prices', tpe=Mat)

        self.register(name='load_shedding', tpe=Mat)

        self.register(name='Sf', tpe=CxMat)
        self.register(name='St', tpe=CxMat)
        self.register(name='loading', tpe=Mat)
        self.register(name='losses', tpe=Mat)
        self.register(name='phase_shift', tpe=Mat)
        self.register(name='overloads', tpe=Mat)
        self.register(name='rates', tpe=Vec)
        self.register(name='contingency_rates', tpe=Vec)
        self.register(name='contingency_flows_list', tpe=list)
        self.register(name='contingency_indices_list', tpe=list)
        self.register(name='contingency_flows_slacks_list', tpe=list)

        self.register(name='hvdc_Pf', tpe=Mat)
        self.register(name='hvdc_loading', tpe=Mat)

        self.register(name='fluid_node_current_level', tpe=Mat)
        self.register(name='fluid_node_flow_in', tpe=Mat)
        self.register(name='fluid_node_flow_out', tpe=Mat)
        self.register(name='fluid_node_p2x_flow', tpe=Mat)
        self.register(name='fluid_node_spillage', tpe=Mat)

        self.register(name='fluid_path_flow', tpe=Mat)
        self.register(name='fluid_injection_flow', tpe=Mat)

        self.register(name='generator_power', tpe=Mat)
        self.register(name='generator_shedding', tpe=Mat)
        self.register(name='generator_cost', tpe=Mat)
        # self.register(name='generator_fuel', tpe=Mat)
        # self.register(name='generator_emissions', tpe=Mat)
        self.register(name='generator_producing', tpe=Mat)
        self.register(name='generator_starting_up', tpe=Mat)
        self.register(name='generator_shutting_down', tpe=Mat)

        self.register(name='battery_power', tpe=Mat)
        self.register(name='battery_energy', tpe=Mat)

        self.register(name='system_fuel', tpe=Mat)
        self.register(name='system_emissions', tpe=Mat)
        self.register(name='system_energy_cost', tpe=Mat)

        self.register(name='converged', tpe=BoolVec)

    def apply_new_time_series_rates(self, nc: NumericalCircuit):
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

        loads = circuit.get_load_like_devices()
        for i, elm in enumerate(loads):
            pr = self.load_shedding[:, i]
            if len(pr) == circuit.get_time_number():
                elm.P_prof -= pr

        hvdc = circuit.get_hvdc()
        for i, elm in enumerate(hvdc):
            pr = self.hvdc_Pf[:, i]
            if len(pr) == circuit.get_time_number():
                elm.Pset_prof = pr

    def mdl(self, result_type) -> ResultsTable:
        """
        Plot the results
        :param result_type:
        :return:
        """

        if result_type == ResultTypes.BusVoltageModule:

            return ResultsTable(data=np.abs(self.voltage),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                xlabel='',
                                units='(p.u.)')

        elif result_type == ResultTypes.BusVoltageAngle:

            return ResultsTable(data=np.angle(self.voltage, deg=True),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                xlabel='',
                                units='(deg)')

        elif result_type == ResultTypes.BusShadowPrices:

            return ResultsTable(data=self.bus_shadow_prices,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel='(currency / MW)',
                                xlabel='',
                                units='(currency / MW)')

        elif result_type == ResultTypes.BusPower:

            return ResultsTable(data=self.Sbus.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BranchPower:

            return ResultsTable(data=self.Sf.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BranchLoading:

            return ResultsTable(data=np.abs(self.loading * 100.0),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                xlabel='',
                                units='(%)')

        elif result_type == ResultTypes.BranchOverloads:

            return ResultsTable(data=np.abs(self.overloads),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BranchLosses:

            return ResultsTable(data=self.losses.real,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BranchTapAngle:

            return ResultsTable(data=np.rad2deg(self.phase_shift),
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                ylabel='(deg)',
                                xlabel='',
                                units='(deg)')

        elif result_type == ResultTypes.HvdcPowerFrom:

            return ResultsTable(data=self.hvdc_Pf,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.hvdc_names,
                                cols_device_type=DeviceType.HVDCLineDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.HvdcLoading:

            return ResultsTable(data=self.hvdc_loading * 100.0,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.hvdc_names,
                                cols_device_type=DeviceType.HVDCLineDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                xlabel='',
                                units='(%)')

        elif result_type == ResultTypes.FluidCurrentLevel:

            return ResultsTable(data=self.fluid_node_current_level * 1e-6,  # convert m3 to hm3,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.fluid_node_names,
                                cols_device_type=DeviceType.FluidNodeDevice,
                                title=result_type.value,
                                ylabel='(hm3)',
                                xlabel='',
                                units='(hm3)')

        elif result_type == ResultTypes.FluidFlowIn:

            return ResultsTable(data=self.fluid_node_flow_in,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.fluid_node_names,
                                cols_device_type=DeviceType.FluidNodeDevice,
                                title=result_type.value,
                                ylabel='(m3/s)',
                                xlabel='',
                                units='(m3/s)')

        elif result_type == ResultTypes.FluidFlowOut:

            return ResultsTable(data=self.fluid_node_flow_out,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.fluid_node_names,
                                cols_device_type=DeviceType.FluidNodeDevice,
                                title=result_type.value,
                                ylabel='(m3/s)',
                                xlabel='',
                                units='(m3/s)')

        elif result_type == ResultTypes.FluidP2XFlow:

            return ResultsTable(data=self.fluid_node_p2x_flow,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.fluid_node_names,
                                cols_device_type=DeviceType.FluidNodeDevice,
                                title=result_type.value,
                                ylabel='(m3/s)',
                                xlabel='',
                                units='(m3/s)')

        elif result_type == ResultTypes.FluidSpillage:

            return ResultsTable(data=self.fluid_node_spillage,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.fluid_node_names,
                                cols_device_type=DeviceType.FluidNodeDevice,
                                title=result_type.value,
                                ylabel='(m3/s)',
                                xlabel='',
                                units='(m3/s)')

        elif result_type == ResultTypes.FluidFlowPath:

            return ResultsTable(data=self.fluid_path_flow,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.fluid_path_names,
                                cols_device_type=DeviceType.FluidPathDevice,
                                title=result_type.value,
                                ylabel='(m3/s)',
                                xlabel='',
                                units='(m3/s)')

        elif result_type == ResultTypes.FluidFlowInjection:

            return ResultsTable(data=self.fluid_injection_flow,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.fluid_injection_names,
                                cols_device_type=DeviceType.FluidInjectionDevice,
                                title=result_type.value,
                                ylabel='(m3/s)',
                                xlabel='',
                                units='(m3/s)')

        elif result_type == ResultTypes.LoadShedding:

            return ResultsTable(data=self.load_shedding,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.load_names,
                                cols_device_type=DeviceType.LoadLikeDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.GeneratorPower:

            return ResultsTable(data=self.generator_power,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.generator_names,
                                cols_device_type=DeviceType.GeneratorDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.GeneratorShedding:

            return ResultsTable(data=self.generator_shedding,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.generator_names,
                                cols_device_type=DeviceType.GeneratorDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.GeneratorCost:

            return ResultsTable(data=self.generator_cost,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.generator_names,
                                cols_device_type=DeviceType.GeneratorDevice,
                                title=result_type.value,
                                ylabel='(Currency)',
                                xlabel='',
                                units='(Currency)')

        elif result_type == ResultTypes.GeneratorProducing:

            return ResultsTable(data=self.generator_producing,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.generator_names,
                                cols_device_type=DeviceType.GeneratorDevice,
                                title=result_type.value,
                                ylabel='',
                                xlabel='',
                                units='')

        elif result_type == ResultTypes.GeneratorStartingUp:

            return ResultsTable(data=self.generator_starting_up,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.generator_names,
                                cols_device_type=DeviceType.GeneratorDevice,
                                title=result_type.value,
                                ylabel='',
                                xlabel='',
                                units='')

        elif result_type == ResultTypes.GeneratorShuttingDown:

            return ResultsTable(data=self.generator_shutting_down,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.generator_names,
                                cols_device_type=DeviceType.GeneratorDevice,
                                title=result_type.value,
                                ylabel='',
                                xlabel='',
                                units='')

        elif result_type == ResultTypes.BatteryPower:

            return ResultsTable(data=self.battery_power,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.battery_names,
                                cols_device_type=DeviceType.BatteryDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        elif result_type == ResultTypes.BatteryEnergy:

            return ResultsTable(data=self.battery_energy,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.battery_names,
                                cols_device_type=DeviceType.BatteryDevice,
                                title=result_type.value,
                                ylabel='(MWh)',
                                xlabel='',
                                units='(MWh)')

        elif result_type == ResultTypes.SystemFuel:

            return ResultsTable(data=self.system_fuel,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.fuel_names,
                                cols_device_type=DeviceType.FuelDevice,
                                title=result_type.value,
                                ylabel='(t)',
                                xlabel='',
                                units='(t)')

        elif result_type == ResultTypes.SystemEmissions:

            return ResultsTable(data=self.system_emissions,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.emission_names,
                                cols_device_type=DeviceType.EmissionGasDevice,
                                title=result_type.value,
                                ylabel='(t)',
                                xlabel='',
                                units='(t)')

        elif result_type == ResultTypes.SystemEnergyCost:

            return ResultsTable(data=self.system_energy_cost,
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=['System cost'],
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(Currency/MWh)',
                                xlabel='',
                                units='(Currency/MWh)')

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

            columns = ['Time index', 'Monitored idx ', 'Contingency idx',
                       'Time', 'Monitored', 'Contingency',
                       'ContingencyFlow (MW)', 'Base flow (MW)',
                       'ContingencyFlow (%)', 'Base flow (%)']

            return ResultsTable(data=np.array(y, dtype=object),
                                index=index,
                                idx_device_type=DeviceType.NoDevice,
                                columns=columns,
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value)

        else:
            raise Exception('Result type not understood:' + str(result_type))
