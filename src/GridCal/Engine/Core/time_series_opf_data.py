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
import pandas as pd
import scipy.sparse as sp
from typing import List, Dict

from GridCal.Engine.basic_structures import Logger
import GridCal.Engine.Core.topology as tp
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.time_series_pf_data import TimeCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
import GridCal.Engine.Core.Compilers.circuit_to_data as gc_compiler


class OpfTimeCircuit(TimeCircuit):

    def __init__(self, nbus, nline, ndcline, ntr, nvsc, nupfc, nhvdc, nload, ngen, nbatt, nshunt, nstagen, sbase, time_array):
        """
        :param nbus: number of buses
        :param nline: number of lines
        :param ndcline:
        :param ntr: number of transformers
        :param nvsc:
        :param nupfc:
        :param nhvdc:
        :param nload:
        :param ngen:
        :param nbatt:
        :param nshunt:
        :param nstagen:
        :param sbase:
        :param time_array:
        """

        TimeCircuit.__init__(self, nbus=nbus, nline=nline, ndcline=ndcline,
                             ntr=ntr, nvsc=nvsc, nupfc=nupfc,
                             nhvdc=nhvdc, nload=nload,
                             ngen=ngen, nbatt=nbatt, nshunt=nshunt,
                             nstagen=nstagen, sbase=sbase, time_array=time_array)

    @property
    def battery_pmax(self):
        return self.battery_data.battery_pmax

    @property
    def battery_pmin(self):
        return self.battery_data.battery_pmin

    @property
    def battery_enom(self):
        return self.battery_data.battery_enom

    @property
    def battery_min_soc(self):
        return self.battery_data.battery_min_soc

    @property
    def battery_max_soc(self):
        return self.battery_data.battery_max_soc

    @property
    def battery_charge_efficiency(self):
        return self.battery_data.battery_charge_efficiency

    @property
    def battery_soc_0(self):
        return self.battery_data.battery_soc_0

    @property
    def battery_discharge_efficiency(self):
        return self.battery_data.battery_discharge_efficiency

    @property
    def battery_cost(self):
        return self.battery_data.battery_cost

    @property
    def generator_pmax(self):
        return self.generator_data.generator_pmax

    @property
    def generator_pmin(self):
        return self.generator_data.generator_pmin

    @property
    def generator_dispatchable(self):
        return self.generator_data.generator_dispatchable

    @property
    def generator_cost(self):
        return self.generator_data.generator_cost

    @property
    def generator_p(self):
        return self.generator_data.generator_p

    @property
    def generator_active(self):
        return self.generator_data.generator_active

    @property
    def load_active(self):
        return self.load_data.load_active

    @property
    def load_s(self):
        return self.load_data.load_s

    @property
    def load_cost(self):
        return self.load_data.load_cost

    @property
    def branch_R(self):
        return self.branch_data.R

    @property
    def branch_X(self):
        return self.branch_data.X

    @property
    def branch_active(self):
        return self.branch_data.branch_active

    @property
    def branch_rates(self):
        return self.branch_data.branch_rates

    @property
    def branch_contingency_rates(self):
        return self.branch_data.branch_contingency_rates

    @property
    def branch_cost(self):
        return self.branch_data.branch_cost

    def get_island(self, bus_idx, time_idx=None) -> "OpfTimeCircuit":
        """
        Get the island corresponding to the given buses
        :param bus_idx: array of bus indices
        :param time_idx: array of time indices (or None for all time indices)
        :return: SnapshotData
        """
        # if the island is the same as the original bus indices, no slicing is needed
        if len(bus_idx) == len(self.original_bus_idx):
            if np.all(bus_idx == self.original_bus_idx):
                if len(time_idx) == len(self.original_time_idx):
                    if np.all(time_idx == self.original_time_idx):
                        return self

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

        nc = OpfTimeCircuit(nbus=len(bus_idx),
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
                            time_array=self.time_array)

        # set the original indices
        nc.original_bus_idx = bus_idx
        nc.original_branch_idx = br_idx
        nc.original_line_idx = line_idx
        nc.original_tr_idx = tr_idx
        nc.original_dc_line_idx = dc_line_idx
        nc.original_vsc_idx = vsc_idx
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


def compile_opf_time_circuit(circuit: MultiCircuit, apply_temperature=False,
                             branch_tolerance_mode=BranchImpedanceMode.Specified,
                             use_stored_guess=False) -> OpfTimeCircuit:
    """
    Compile the information of a circuit and generate the pertinent power flow islands
    :param circuit: Circuit instance
    :param apply_temperature:
    :param branch_tolerance_mode:
    :param use_stored_guess:
    :return: list of TimeOpfCircuit
    """

    logger = Logger()
    nc = OpfTimeCircuit(nbus=0,
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

    opf_results = None

    bus_dict = {bus: i for i, bus in enumerate(circuit.buses)}

    nc.bus_data = gc_compiler.get_bus_data(circuit=circuit,
                                           time_series=True,
                                           ntime=ntime,
                                           use_stored_guess=use_stored_guess)

    nc.load_data = gc_compiler.get_load_data(circuit=circuit,
                                             bus_dict=bus_dict,
                                             opf_results=opf_results,
                                             time_series=True,
                                             ntime=ntime,
                                             opf=True)

    nc.static_generator_data = gc_compiler.get_static_generator_data(circuit=circuit,
                                                                     bus_dict=bus_dict,
                                                                     time_series=True,
                                                                     ntime=ntime)

    nc.generator_data = gc_compiler.get_generator_data(circuit=circuit,
                                                       bus_dict=bus_dict,
                                                       Vbus=nc.bus_data.Vbus,
                                                       logger=logger,
                                                       opf_results=opf_results,
                                                       time_series=True,
                                                       opf=True,
                                                       ntime=ntime,
                                                       use_stored_guess=use_stored_guess)

    nc.battery_data = gc_compiler.get_battery_data(circuit=circuit,
                                                   bus_dict=bus_dict,
                                                   Vbus=nc.bus_data.Vbus,
                                                   logger=logger,
                                                   opf_results=opf_results,
                                                   time_series=True,
                                                   opf=True,
                                                   ntime=ntime,
                                                   use_stored_guess=use_stored_guess)

    nc.shunt_data = gc_compiler.get_shunt_data(circuit=circuit,
                                               bus_dict=bus_dict,
                                               Vbus=nc.bus_data.Vbus,
                                               logger=logger,
                                               time_series=True,
                                               ntime=ntime,
                                               use_stored_guess=use_stored_guess)

    nc.line_data = gc_compiler.get_line_data(circuit=circuit,
                                             bus_dict=bus_dict,
                                             apply_temperature=apply_temperature,
                                             branch_tolerance_mode=branch_tolerance_mode,
                                             time_series=True, ntime=ntime)

    nc.transformer_data = gc_compiler.get_transformer_data(circuit=circuit,
                                                           bus_dict=bus_dict,
                                                           time_series=True,
                                                           ntime=ntime)

    nc.vsc_data = gc_compiler.get_vsc_data(circuit=circuit,
                                           bus_dict=bus_dict,
                                           time_series=True,
                                           ntime=ntime)

    nc.upfc_data = gc_compiler.get_upfc_data(circuit=circuit,
                                             bus_dict=bus_dict,
                                             time_series=True,
                                             ntime=ntime)

    nc.dc_line_data = gc_compiler.get_dc_line_data(circuit=circuit,
                                                   bus_dict=bus_dict,
                                                   apply_temperature=apply_temperature,
                                                   branch_tolerance_mode=branch_tolerance_mode,
                                                   time_series=True,
                                                   ntime=ntime)

    nc.branch_data = gc_compiler.get_branch_data(circuit=circuit,
                                                 bus_dict=bus_dict,
                                                 Vbus=nc.bus_data.Vbus,
                                                 apply_temperature=apply_temperature,
                                                 branch_tolerance_mode=branch_tolerance_mode,
                                                 time_series=True,
                                                 opf=True,
                                                 ntime=ntime,
                                                 use_stored_guess=use_stored_guess)

    nc.hvdc_data = gc_compiler.get_hvdc_data(circuit=circuit,
                                             bus_dict=bus_dict,
                                             bus_types=nc.bus_data.bus_types,
                                             time_series=True, ntime=ntime)

    nc.consolidate_information()

    return nc

