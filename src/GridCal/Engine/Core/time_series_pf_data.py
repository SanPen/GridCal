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
import scipy.sparse as sp
from typing import List, Dict

from GridCal.Engine.basic_structures import Logger
import GridCal.Engine.Core.topology as tp
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import SnapshotData
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian
from GridCal.Engine.Core.common_functions import compile_types, find_different_states
from GridCal.Engine.Simulations.sparse_solve import get_sparse_type
# from GridCal.Engine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
import GridCal.Engine.Core.DataStructures as ds


sparse_type = get_sparse_type()


class TimeCircuit(SnapshotData):

    def __init__(self, nbus, nline, ndcline, ntr, nvsc, nupfc, nhvdc, nload, ngen, nbatt, nshunt, nstagen, sbase, time_array):
        """

        :param nbus: number of buses
        :param nline: number of lines
        :param ntr: number of transformers
        :param nvsc:
        :param nhvdc:
        :param nload:
        :param ngen:
        :param nbatt:
        :param nshunt:
        """

        SnapshotData.__init__(self, nbus=nbus, nline=nline,
                              ndcline=ndcline, ntr=ntr, nvsc=nvsc, nupfc=nupfc,
                              nhvdc=nhvdc, nload=nload, ngen=ngen,
                              nbatt=nbatt, nshunt=nshunt, nstagen=nstagen,
                              sbase=sbase, ntime=len(time_array))

        self.time_array = time_array

    @property
    def Vbus(self):

        if self.Vbus_ is None:
            self.Vbus_ = self.bus_data.Vbus.copy()

        return self.Vbus_

    @property
    def Sbus(self):

        if self.Sbus_ is None:
            self.Sbus_ = self.get_injections(normalize=True)

        return self.Sbus_

    @property
    def Ibus(self):

        if self.Ibus_ is None:
            self.Ibus_ = np.zeros((len(self.bus_data), self.ntime), dtype=complex)

        return self.Ibus_

    @property
    def Rates(self):
        return self.branch_data.branch_rates

    @property
    def vd(self):

        if self.vd_ is None:
            self.vd_, self.pq_, self.pv_, self.pqpv_ = compile_types(Sbus=self.Sbus[:, 0],
                                                                     types=self.bus_data.bus_types)

        return self.vd_

    def split_into_islands(self, ignore_single_node_islands=False) -> List["TimeCircuit"]:
        """
        Split circuit into islands
        :param numeric_circuit: NumericCircuit instance
        :param ignore_single_node_islands: ignore islands composed of only one bus
        :return: List[NumericCircuit]
        """

        circuit_islands = list()  # type: List[TimeCircuit]

        all_buses = np.arange(self.nbus)
        all_time = np.arange(self.ntime)

        # find the probable time slices
        states = find_different_states(branch_active_prof=self.branch_data.branch_active.T)

        if len(states) == 1:
            # compute the adjacency matrix
            A = tp.get_adjacency_matrix(C_branch_bus_f=self.Cf,
                                        C_branch_bus_t=self.Ct,
                                        branch_active=self.branch_data.branch_active[:, 0],
                                        bus_active=self.bus_data.bus_active[:, 0])

            # find the matching islands
            idx_islands = tp.find_islands(A)

            if len(idx_islands) == 1:  # only one state and only one island -> just copy the data

                return [self]

            else:  # one state, many islands -> split by bus index, keep the time

                for bus_idx in idx_islands:

                    if ignore_single_node_islands:

                        if len(bus_idx) > 1:
                            island = self.get_island(bus_idx, all_time)
                            circuit_islands.append(island)

                    else:
                        island = self.get_island(bus_idx, all_time)
                        circuit_islands.append(island)

                return circuit_islands

        else:  # ------------------------------------------------------------------------------------------------------

            for t, t_array in states.items():

                # compute the adjacency matrix
                A = tp.get_adjacency_matrix(C_branch_bus_f=self.Cf,
                                            C_branch_bus_t=self.Ct,
                                            branch_active=self.branch_data.branch_active[:, t_array],
                                            bus_active=self.bus_data.bus_active[:, t_array])

                # find the matching islands
                idx_islands = tp.find_islands(A)

                if len(idx_islands) == 1:  # many time states, one island -> slice only by time ------------------------

                    island = self.get_island(all_buses, t_array)  # convert the circuit to an island

                    circuit_islands.append(island)

                else:  # any time states, many islands -> slice by both time and bus index -----------------------------

                    for bus_idx in idx_islands:

                        if ignore_single_node_islands:

                            if len(bus_idx) > 1:
                                island = self.get_island(bus_idx, t_array)
                                circuit_islands.append(island)

                        else:
                            island = self.get_island(bus_idx, t_array)
                            circuit_islands.append(island)

            return circuit_islands


def compile_time_circuit(circuit: MultiCircuit, apply_temperature=False,
                         branch_tolerance_mode=BranchImpedanceMode.Specified,
                         opf_results=None) -> TimeCircuit:
    """
    Compile the information of a circuit and generate the pertinent power flow islands
    :param circuit: Circuit instance
    :param apply_temperature:
    :param branch_tolerance_mode:
    :param opf_results: OptimalPowerFlowTimeSeriesResults instance
    :return: list of NumericIslands
    """

    logger = Logger()
    nc = TimeCircuit(nbus=0,
                     nline=0,
                     ndcline=0,
                     ntr=0,
                     nvsc=0,
                     nupfc=0,
                     nhvdc=0,
                     nload=0,
                     ngen=0,
                     nbatt=0,
                     nshunt=0,
                     nstagen=0,
                     sbase=circuit.Sbase,
                     time_array=circuit.time_profile)

    ntime = nc.ntime

    bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}

    nc.bus_data = ds.circuit_to_data.get_bus_data(circuit, time_series=True, ntime=ntime)

    nc.load_data = ds.circuit_to_data.get_load_data(circuit, bus_dict, opf_results, time_series=True, ntime=ntime)

    nc.static_generator_data = ds.circuit_to_data.get_static_generator_data(circuit, bus_dict,
                                                                            time_series=True, ntime=ntime)

    nc.generator_data = ds.circuit_to_data.get_generator_data(circuit, bus_dict, nc.bus_data.Vbus, logger, opf_results,
                                                              time_series=True, ntime=ntime)

    nc.battery_data = ds.circuit_to_data.get_battery_data(circuit, bus_dict, nc.bus_data.Vbus, logger, opf_results,
                                                          time_series=True, ntime=ntime)

    nc.shunt_data = ds.circuit_to_data.get_shunt_data(circuit, bus_dict, time_series=True, ntime=ntime)

    nc.line_data = ds.circuit_to_data.get_line_data(circuit, bus_dict, apply_temperature, branch_tolerance_mode,
                                                    time_series=True, ntime=ntime)

    nc.transformer_data = ds.circuit_to_data.get_transformer_data(circuit, bus_dict, time_series=True, ntime=ntime)

    nc.vsc_data = ds.circuit_to_data.get_vsc_data(circuit, bus_dict, time_series=True, ntime=ntime)

    nc.dc_line_data = ds.circuit_to_data.get_dc_line_data(circuit, bus_dict, apply_temperature, branch_tolerance_mode,
                                                          time_series=True, ntime=ntime)

    nc.upfc_data = ds.circuit_to_data.get_upfc_data(circuit, bus_dict, time_series=True, ntime=ntime)

    nc.branch_data = ds.circuit_to_data.get_branch_data(circuit, bus_dict, nc.bus_data.Vbus,
                                                        apply_temperature, branch_tolerance_mode,
                                                        time_series=True, ntime=ntime)

    nc.hvdc_data = ds.circuit_to_data.get_hvdc_data(circuit, bus_dict, nc.bus_data.bus_types,
                                                    time_series=True, ntime=ntime)

    nc.consolidate_information()

    return nc

