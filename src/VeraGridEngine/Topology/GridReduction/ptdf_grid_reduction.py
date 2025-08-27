# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from typing import Tuple, TYPE_CHECKING
from scipy.sparse import coo_matrix
import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import IntVec, Mat, Logger
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Topology.topology import find_islands, build_branches_C_coo_3

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


def ptdf_reduction(grid: MultiCircuit,
                   reduction_bus_indices: IntVec,
                   PTDF: Mat,
                   tol=1e-8) -> Logger:
    """
    In-place Grid reduction using the PTDF injection mirroring
    No theory available
    :param grid: MultiCircuit
    :param reduction_bus_indices: Bus indices of the buses to delete
    :param PTDF: PTDF matrix
    :param tol: Tolerance, any equivalent power value under this is omitted
    """
    logger = Logger()

    # find the boundary set: buses from the internal set the join to the external set
    e_buses, b_buses, i_buses, b_branches = grid.get_reduction_sets(reduction_bus_indices=reduction_bus_indices)

    if len(e_buses) == 0:
        logger.add_info(msg="Nothing to reduce")
        return logger

    if len(i_buses) == 0:
        logger.add_info(msg="Nothing to keep (null grid as a result)")
        return logger

    if len(b_buses) == 0:
        logger.add_info(msg="The reducible and non reducible sets are disjoint and cannot be reduced")
        return logger

    # Start moving objects
    e_buses_set = set(e_buses)
    bus_dict = grid.get_bus_index_dict()
    has_ts = grid.has_time_series

    for elm in grid.get_injection_devices():

        i = bus_dict[elm.bus]  # bus index where it is currently connected

        if i in e_buses_set:
            # this generator is to be reduced

            for b in range(len(b_buses)):
                bus_idx = b_buses[b]
                branch_idx = b_branches[b]
                bus = grid.buses[bus_idx]
                ptdf_val = PTDF[branch_idx, bus_idx]

                if abs(ptdf_val) > tol:

                    # create new device at the boundary bus
                    if elm.device_type == DeviceType.GeneratorDevice:
                        new_elm = dev.Generator(name=f"{elm.name}@{bus.name}")
                        new_elm.P = ptdf_val * elm.P
                        if has_ts:
                            new_elm.P_prof = ptdf_val * elm.P_prof.toarray()
                        new_elm.comment = "Equivalent generator"
                        grid.add_generator(bus=bus, api_obj=new_elm)

                    elif elm.device_type == DeviceType.BatteryDevice:
                        new_elm = dev.Battery(name=f"{elm.name}@{bus.name}")
                        new_elm.P = ptdf_val * elm.P
                        if has_ts:
                            new_elm.P_prof = ptdf_val * elm.P_prof.toarray()
                        new_elm.comment = "Equivalent battery"
                        grid.add_battery(bus=bus, api_obj=new_elm)

                    elif elm.device_type == DeviceType.StaticGeneratorDevice:
                        new_elm = dev.StaticGenerator(name=f"{elm.name}@{bus.name}")
                        new_elm.P = ptdf_val * elm.P
                        new_elm.Q = ptdf_val * elm.Q
                        if has_ts:
                            new_elm.P_prof = ptdf_val * elm.P_prof.toarray()
                            new_elm.Q_prof = ptdf_val * elm.Q_prof.toarray()
                        new_elm.comment = "Equivalent static generator"
                        grid.add_static_generator(bus=bus, api_obj=new_elm)

                    elif elm.device_type == DeviceType.LoadDevice:
                        new_elm = dev.Load(name=f"{elm.name}@{bus.name}")
                        new_elm.P = ptdf_val * elm.P
                        new_elm.Q = ptdf_val * elm.Q
                        if has_ts:
                            new_elm.P_prof = ptdf_val * elm.P_prof.toarray()
                            new_elm.Q_prof = ptdf_val * elm.Q_prof.toarray()
                        new_elm.comment = "Equivalent load"
                        grid.add_load(bus=bus, api_obj=new_elm)
                    else:
                        # device I don't care about
                        logger.add_warning(msg="Ignored device",
                                           device=str(elm),
                                           device_class=elm.device_type.value)

    # Delete the external buses
    to_be_deleted = [grid.buses[e] for e in e_buses]
    for bus in to_be_deleted:
        grid.delete_bus(obj=bus, delete_associated=True)

    return logger


def ptdf_reduction_with_islands(grid: MultiCircuit,
                                reduction_bus_indices: IntVec,
                                PTDF: Mat,
                                tol=1e-8) -> Tuple[MultiCircuit, Logger]:
    """
    In-place Grid reduction using the PTDF injection mirroring power by island
    No theory available
    :param grid: MultiCircuit
    :param reduction_bus_indices: Bus indices of the buses to delete
    :param PTDF: PTDF matrix
    :param tol: Tolerance, any equivalent power value under this is omitted
    """
    logger = Logger()

    # find the boundary set: buses from the internal set the join to the external set
    e_buses, b_buses, i_buses, b_branches = grid.get_reduction_sets(reduction_bus_indices=reduction_bus_indices)

    if len(e_buses) == 0:
        logger.add_info(msg="Nothing to reduce")
        return logger

    if len(i_buses) == 0:
        logger.add_info(msg="Nothing to keep (null grid as a result)")
        return logger

    if len(b_buses) == 0:
        logger.add_info(msg="The reducible and non reducible sets are disjoint and cannot be reduced")
        return logger

    # get the islands --------------------------------------------------------------------------------------------------
    nbus = grid.get_bus_number()
    nc = compile_numerical_circuit_at(circuit=grid, t_idx=None)

    # Get the arrays to prepare the topology
    (bus_active,
     branch_active, branch_F, branch_T,
     hvdc_active, hvdc_F, hvdc_T,
     vsc_active, vsc_F, vsc_T) = grid.get_topology_data(t_idx=None)

    branch_active[b_branches] = 0  # deactivate boundary branches

    i, j, data, n_elm = build_branches_C_coo_3(
        bus_active=bus_active,
        F1=branch_F, T1=branch_T, active1=branch_active,
        F2=vsc_F, T2=vsc_T, active2=vsc_active,
        F3=hvdc_F, T3=hvdc_T, active3=hvdc_active,
    )

    C = coo_matrix((data, (i, j)), shape=(n_elm, nbus), dtype=int)
    adj = (C.T @ C).tocsc()

    idx_islands = find_islands(adj=adj, active=nc.bus_data.active)

    # Start moving objects ---------------------------------------------------------------------------------------------
    e_buses_set = set(e_buses)
    bus_dict = grid.get_bus_index_dict()
    has_ts = grid.has_time_series

    for elm in grid.get_injection_devices():

        i = bus_dict[elm.bus]  # bus index where it is currently connected

        if i in e_buses_set:
            # this generator is to be reduced

            for b in range(len(b_buses)):
                bus_idx = b_buses[b]
                branch_idx = b_branches[b]
                bus = grid.buses[bus_idx]
                ptdf_val = PTDF[branch_idx, bus_idx]

                if abs(ptdf_val) > tol:

                    # create new device at the boundary bus
                    if elm.device_type == DeviceType.GeneratorDevice:
                        new_elm = dev.Generator(name=f"{elm.name}@{bus.name}")
                        new_elm.P = ptdf_val * elm.P
                        if has_ts:
                            new_elm.P_prof = ptdf_val * elm.P_prof.toarray()
                        new_elm.comment = "Equivalent generator"
                        grid.add_generator(bus=bus, api_obj=new_elm)

                    elif elm.device_type == DeviceType.BatteryDevice:
                        new_elm = dev.Battery(name=f"{elm.name}@{bus.name}")
                        new_elm.P = ptdf_val * elm.P
                        if has_ts:
                            new_elm.P_prof = ptdf_val * elm.P_prof.toarray()
                        new_elm.comment = "Equivalent battery"
                        grid.add_battery(bus=bus, api_obj=new_elm)

                    elif elm.device_type == DeviceType.StaticGeneratorDevice:
                        new_elm = dev.StaticGenerator(name=f"{elm.name}@{bus.name}")
                        new_elm.P = ptdf_val * elm.P
                        new_elm.Q = ptdf_val * elm.Q
                        if has_ts:
                            new_elm.P_prof = ptdf_val * elm.P_prof.toarray()
                            new_elm.Q_prof = ptdf_val * elm.Q_prof.toarray()
                        new_elm.comment = "Equivalent static generator"
                        grid.add_static_generator(bus=bus, api_obj=new_elm)

                    elif elm.device_type == DeviceType.LoadDevice:
                        new_elm = dev.Load(name=f"{elm.name}@{bus.name}")
                        new_elm.P = ptdf_val * elm.P
                        new_elm.Q = ptdf_val * elm.Q
                        if has_ts:
                            new_elm.P_prof = ptdf_val * elm.P_prof.toarray()
                            new_elm.Q_prof = ptdf_val * elm.Q_prof.toarray()
                        new_elm.comment = "Equivalent load"
                        grid.add_load(bus=bus, api_obj=new_elm)
                    else:
                        # device I don't care about
                        logger.add_warning(msg="Ignored device",
                                           device=str(elm),
                                           device_class=elm.device_type.value)

    # Delete the external buses
    to_be_deleted = [grid.buses[e] for e in e_buses]
    for bus in to_be_deleted:
        grid.delete_bus(obj=bus, delete_associated=True)

    return grid, logger


if __name__ == '__main__':
    import VeraGridEngine as gce

    fname = '/home/santi/Documentos/Git/GitHub/VeraGrid/src/tests/data/grids/Matpower/case9.m'
    fname_expected = '/home/santi/Documentos/Git/GitHub/VeraGrid/src/tests/data/grids/Matpower/ieee9_reduced.m'

    reduction_bus_indices_ = np.array([0, 4, 7])

    grid_ = gce.open_file(fname)
    grid_expected = gce.open_file(fname_expected)

    ptdf = gce.linear_power_flow(grid=grid_).PTDF
    grid_red, logger_red = ptdf_reduction_with_islands(
        grid=grid_.copy(),
        reduction_bus_indices=np.array([0, 1, 2, 3, 7]),
        PTDF=ptdf,
        tol=1e-8
    )
