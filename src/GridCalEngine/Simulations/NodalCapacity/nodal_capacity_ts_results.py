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
import numpy as np
import pandas as pd
from typing import Union, TYPE_CHECKING
from GridCalEngine.basic_structures import IntVec, StrVec, Mat
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
from GridCalEngine.enumerations import DeviceType, ResultTypes

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults


class NodalCapacityTimeSeriesResults(OptimalPowerFlowTimeSeriesResults):
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
                 clustering_results: Union[None, ClusteringResults] = None,
                 capacity_nodes_idx: Union[None, IntVec] = None):
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
        :param capacity_nodes_idx:
        """
        OptimalPowerFlowTimeSeriesResults.__init__(self,
                                                   bus_names=bus_names,
                                                   branch_names=branch_names,
                                                   load_names=load_names,
                                                   generator_names=generator_names,
                                                   battery_names=battery_names,
                                                   hvdc_names=hvdc_names,
                                                   fuel_names=fuel_names,
                                                   emission_names=emission_names,
                                                   fluid_node_names=fluid_node_names,
                                                   fluid_path_names=fluid_path_names,
                                                   fluid_injection_names=fluid_injection_names,
                                                   n=n,
                                                   m=m,
                                                   nt=nt,
                                                   ngen=ngen,
                                                   nbat=nbat,
                                                   nload=nload,
                                                   nhvdc=nhvdc,
                                                   n_fluid_node=n_fluid_node,
                                                   n_fluid_path=n_fluid_path,
                                                   n_fluid_injection=n_fluid_injection,
                                                   time_array=time_array,
                                                   bus_types=bus_types,
                                                   clustering_results=clustering_results)

        self.capacity_nodes_idx = capacity_nodes_idx if capacity_nodes_idx is not None else np.zeros(0, dtype=int)

        self.nodal_capacity = np.zeros((nt, len(self.capacity_nodes_idx)), dtype=float)

        # hack the available results to add another entry
        self.available_results[ResultTypes.BusResults].append(ResultTypes.BusNodalCapacity)

        self.register(name='capacity_nodes_idx', tpe=IntVec)
        self.register(name='nodal_capacity', tpe=Mat)

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type:
        :return:
        """

        if result_type == ResultTypes.BusNodalCapacity:
            return ResultsTable(data=self.nodal_capacity[:, :],
                                index=pd.to_datetime(self.time_array),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=self.bus_names[self.capacity_nodes_idx],
                                cols_device_type=DeviceType.BusDevice,
                                title=str(result_type.value),
                                ylabel='(MW)',
                                xlabel='',
                                units='(MW)')

        else:
            return super().mdl(result_type=result_type)
