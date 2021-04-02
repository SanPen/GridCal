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

    def consolidate(self):
        self.Vbus_ = self.bus_data.Vbus.copy()
        self.Sbus_ = self.get_injections(normalize=True)
        self.Ibus_ = np.zeros((len(self.bus_data), self.ntime), dtype=complex)

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

    @property
    def hvdc_Pf(self):
        return self.hvdc_data.Pf

    @property
    def hvdc_Pt(self):
        return self.hvdc_data.Pt

    @property
    def hvdc_loading(self):
        return self.hvdc_data.get_loading()

    @property
    def hvdc_losses(self):
        return self.hvdc_data.get_losses()

    def get_island(self, bus_idx, time_idx=None) -> "TimeCircuit":
        """
        Get the island corresponding to the given buses
        :param bus_idx: array of bus indices
        :param time_idx: array of time indices (or None for all time indices)
        :return: SnapshotData
        """

        # find the indices of the devices of the island
        line_idx = self.line_data.get_island(bus_idx)
        dc_line_idx = self.dc_line_data.get_island(bus_idx)
        tr_idx = self.transformer_data.get_island(bus_idx)
        vsc_idx = self.vsc_data.get_island(bus_idx)
        upfc_idx = self.upfc_data.get_island(bus_idx)
        hvdc_idx = self.hvdc_data.get_island(bus_idx)
        br_idx = self.branch_data.get_island(bus_idx)

        load_idx = self.load_data.get_island(bus_idx)
        stagen_idx = self.static_generator_data.get_island(bus_idx)
        gen_idx = self.generator_data.get_island(bus_idx)
        batt_idx = self.battery_data.get_island(bus_idx)
        shunt_idx = self.shunt_data.get_island(bus_idx)

        nc = TimeCircuit(nbus=len(bus_idx),
                         nline=len(line_idx),
                         ndcline=len(dc_line_idx),
                         ntr=len(tr_idx),
                         nvsc=len(vsc_idx),
                         nupfc=len(upfc_idx),
                         nhvdc=len(hvdc_idx),
                         nload=len(load_idx),
                         ngen=len(gen_idx),
                         nbatt=len(batt_idx),
                         nshunt=len(shunt_idx),
                         nstagen=len(stagen_idx),
                         sbase=self.Sbase,
                         time_array=self.time_array[time_idx])

        # set the original indices
        nc.original_bus_idx = bus_idx
        nc.original_branch_idx = br_idx
        nc.original_line_idx = line_idx
        nc.original_tr_idx = tr_idx
        nc.original_dc_line_idx = dc_line_idx
        nc.original_vsc_idx = vsc_idx
        nc.original_upfc_idx = upfc_idx
        nc.original_hvdc_idx = hvdc_idx
        nc.original_gen_idx = gen_idx
        nc.original_bat_idx = batt_idx
        nc.original_load_idx = load_idx
        nc.original_stagen_idx = stagen_idx
        nc.original_shunt_idx = shunt_idx

        # slice data
        nc.bus_data = self.bus_data.slice(bus_idx, time_idx)
        nc.branch_data = self.branch_data.slice(br_idx, bus_idx, time_idx)
        nc.line_data = self.line_data.slice(line_idx, bus_idx, time_idx)
        nc.transformer_data = self.transformer_data.slice(tr_idx, bus_idx, time_idx)
        nc.hvdc_data = self.hvdc_data.slice(hvdc_idx, bus_idx, time_idx)
        nc.vsc_data = self.vsc_data.slice(vsc_idx, bus_idx, time_idx)
        nc.dc_line_data = self.dc_line_data.slice(dc_line_idx, bus_idx, time_idx)
        nc.load_data = self.load_data.slice(load_idx, bus_idx, time_idx)
        nc.static_generator_data = self.static_generator_data.slice(stagen_idx, bus_idx, time_idx)
        nc.battery_data = self.battery_data.slice(batt_idx, bus_idx, time_idx)
        nc.generator_data = self.generator_data.slice(gen_idx, bus_idx, time_idx)
        nc.shunt_data = self.shunt_data.slice(shunt_idx, bus_idx, time_idx)

        return nc

    def split_into_islands(self, ignore_single_node_islands=False) -> List["TimeCircuit"]:
        """
        Split circuit into islands
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

    nc.shunt_data = ds.circuit_to_data.get_shunt_data(circuit, bus_dict, nc.bus_data.Vbus, logger,
                                                      time_series=True, ntime=ntime)

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

