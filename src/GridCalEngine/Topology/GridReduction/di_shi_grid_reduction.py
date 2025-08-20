# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from typing import Tuple, TYPE_CHECKING
from scipy.sparse.linalg import factorized, spsolve
from scipy.sparse import csc_matrix, bmat, coo_matrix
from scipy.sparse.csgraph import dijkstra
import GridCalEngine.Devices as dev
from GridCalEngine.basic_structures import IntVec, Mat, CxVec, Logger
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Topology.topology import find_islands, build_branches_C_coo_3

if TYPE_CHECKING:
    from GridCalEngine.Devices.multi_circuit import MultiCircuit
    from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
    from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit


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
                                tol=1e-8) -> Logger:
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

    return logger


def ward_reduction_non_linear(nc: NumericalCircuit, e_buses, b_buses, i_buses, voltage: CxVec, Sbus: CxVec):
    """

    :param nc:
    :param e_buses:
    :param b_buses:
    :param i_buses:
    :param voltage:
    :param Sbus:
    :return:
    """

    adm = nc.get_admittance_matrices()
    Ybus = adm.Ybus

    # slice matrices
    YII = Ybus[np.ix_(i_buses, i_buses)]
    YIB = Ybus[np.ix_(i_buses, b_buses)]

    YBI = Ybus[np.ix_(b_buses, i_buses)]
    YBB = Ybus[np.ix_(b_buses, b_buses)]
    YBE = Ybus[np.ix_(b_buses, e_buses)]

    YEB = Ybus[np.ix_(e_buses, b_buses)]
    YEE = Ybus[np.ix_(e_buses, e_buses)]

    YEE_fact = factorized(YEE.tocsc())

    Yeq = - YBE @ YEE_fact(YEB.toarray())  # 2.16
    YBBp = YBB + csc_matrix(Yeq)  # YBBp = YBB - YBE @ YEE_fact(YEB)  # 2.13

    # compute the current
    I = (Sbus / nc.Sbase) / np.conj(voltage)

    II = I[i_buses]
    IB = I[b_buses]
    IE = I[e_buses]

    # these are the currents to be added ar every bus that remains
    Ieq = - YBE @ YEE_fact(IE)  # 2.17

    # now, we compute the new voltages at the internal and boundary (2.15)
    Ysys = bmat(blocks=[[YII.tocsc(), YIB.tocsc()], [YBI.tocsc(), YBBp.tocsc()]], format='csc')
    IBp = IB + Ieq  # IBp = IB - YBE @ YEE_fact(IE)  # 2.14
    Isys = np.r_[II, IBp]
    V = spsolve(Ysys, Isys)
    ni = len(i_buses)
    VI = V[:ni]
    VB = V[ni:]

    Seq = VB * np.conj(IB)

    return Seq, Ieq, Yeq, YBBp, adm.Ybus.tocsc()


def ward_reduction_linear(Ybus: csc_matrix, e_buses: IntVec, b_buses: IntVec, i_buses: IntVec):
    """

    :param Ybus:
    :param e_buses:
    :param b_buses:
    :param i_buses:
    :return:
    """

    # slice matrices
    Yii = Ybus[np.ix_(i_buses, i_buses)]
    Yib = Ybus[np.ix_(i_buses, b_buses)]
    Yie = Ybus[np.ix_(i_buses, e_buses)]

    Ybi = Ybus[np.ix_(b_buses, i_buses)]
    Ybb = Ybus[np.ix_(b_buses, b_buses)]
    Ybe = Ybus[np.ix_(b_buses, e_buses)]

    Yeb = Ybus[np.ix_(e_buses, b_buses)]
    Yee = Ybus[np.ix_(e_buses, e_buses)]

    Yee_fact = factorized(Yee.tocsc())

    Yeq = - Ybe @ Yee_fact(Yeb.toarray())  # 2.16

    Ybbp = Ybb + csc_matrix(Yeq)  # YBBp = YBB - YBE @ YEE_fact(YEB)  # 2.13

    return Yeq.tocsc(), Ybbp.tocsc()

    # # compute the current
    # P = nc.get_power_injections_pu().real
    #
    # Pi = P[i_buses]
    # Pb = P[b_buses]
    # Pe = P[e_buses]
    #
    # # these are the power to be added ar every boundary bus
    # Pb_eq = - Bbe @ Bee_fact(Pe)  # 2.17
    #
    # # ΔP = −B_ie B_ee⁻¹ P_e
    # Pe = -Bie @ Bee_fact(Pe)
    #
    # return Pb_eq, Pb_eq, Beq, Bbbp, adm.Bbus.tocsc()


def di_shi_reduction(grid: MultiCircuit,
                     reduction_bus_indices: IntVec,
                     pf_res: PowerFlowResults | None = None,
                     add_power_loads: bool = True,
                     use_linear: bool = False,
                     tol=1e-8) -> Tuple[MultiCircuit, Logger]:
    """
    In-place Grid reduction using the Di-Shi equivalent model
    from: Power System Network Reduction for Engineering and Economic Analysis by Di Shi, 2012
    and Optimal Generation Investment Planning: Pt 1: Network Equivalents
    :param grid: MultiCircuit
    :param reduction_bus_indices: Bus indices of the buses to delete
    :param pf_res: PowerFlowResults
    :param add_power_loads: If true Ward currents are converted to loads, else currents are added instead
    :param use_linear: if true, the admittance matrix is used and no voltages are required
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

    nc = compile_numerical_circuit_at(grid, t_idx=None)

    # Step 1 – First Ward reduction ------------------------------------------------------------------------------------

    indices = nc.get_simulation_indices()
    adm = nc.get_admittance_matrices()

    if not use_linear and pf_res is None:
        logger.add_warning("Cannot uses non linear since power flow results are None")
        use_linear = True

    Yeq_1, Ybbp_1 = ward_reduction_linear(Ybus=adm.Ybus,
                                          e_buses=e_buses,
                                          b_buses=b_buses,
                                          i_buses=i_buses)

    # Step 2 – Second Ward reduction: Extending to the external generation buses ---------------------------------------


    # Step 3 – Relocate generators -------------------------------------------------------------------------------------


    # Step 4 – Relocate loads with inverse power flow ------------------------------------------------------------------

    # re-locate the generators using dijkstra

    # 1. multi-source Dijkstra: one row per boundary, all columns = nodes
    dist = dijkstra(Yeq_1, directed=False, indices=b_buses, return_predecessors=False)

    # 2. for each external node, pick the boundary with the minimal distance
    nearest_idx = dist[:, e_buses].argmin(axis=0)  # row index
    nearest_dist = dist[nearest_idx, e_buses]

    # 3. translate row index → actual boundary node ID
    nearest = b_buses[nearest_idx]

    # 4. mark unreachable externals (dist == +∞)
    nearest[np.isinf(nearest_dist)] = -1

    # 5. move the generators to the nearest boundary
    bus_idx_dict = grid.get_bus_index_dict()
    e_dict = {b: idx for idx, b in enumerate(e_buses)}
    for gen in grid.generators:
        i = bus_idx_dict[gen.bus]
        external_position = e_dict.get(i, None)
        if external_position is not None:
            new_bus = grid.buses[nearest[external_position]]
            gen.bus = new_bus

    n_boundary = len(b_buses)

    # add boundary buses
    # boundary_buses = [dev.Bus(name=f'Boundary {i}') for i in range(n_boundary)]
    # grid.buses.extend(boundary_buses)

    boundary_buses = [grid.buses[b_buses[i]] for i in range(n_boundary)]

    # arbitrary criteria: only keep branches which x is less than 10 * max(branches.x)
    max_x = np.max(nc.passive_branch_data.X) * 10

    # add boundary equivalent sub-grid: traverse only the triangular
    for i in range(n_boundary):
        for j in range(i):
            if abs(Yeq[i, j]) > tol:

                if i == j:
                    # add shunt reactance
                    bus = boundary_buses[i]
                    yeq_row_i = Yeq[i, :].copy()
                    yeq_row_i[i] = 0
                    ysh = YBBp[i, i] - np.sum(yeq_row_i)
                    if use_linear:
                        sh = dev.Shunt(name=f"Equivalent shunt {i}", B=ysh, G=0.0)
                    else:
                        sh = dev.Shunt(name=f"Equivalent shunt {i}", B=ysh.imag, G=ysh.real)
                    grid.add_shunt(bus=bus, api_obj=sh)
                else:
                    # add series reactance
                    bus_from = boundary_buses[i]
                    bus_to = boundary_buses[j]

                    z = - 1.0 / Yeq[i, j]

                    if z.imag <= max_x:
                        series_reactance = dev.SeriesReactance(
                            name=f"Equivalent boundary impedance {b_buses[i]}-{b_buses[j]}",
                            bus_from=bus_from,
                            bus_to=bus_to,
                            r=z.real,
                            x=z.imag
                        )
                        grid.add_series_reactance(series_reactance)

    # Add loads at the boundary buses
    for i in range(n_boundary):
        if add_power_loads:
            # add power values
            P = Seq[i].real
            Q = Seq[i].imag
            if abs(P) > tol and abs(Q) > tol:
                load = dev.Load(name=f"Ward equivalent load {i}", P=P * grid.Sbase, Q=Q * grid.Sbase)
                load.comment = "Added because of a Ward reduction of the grid"
                bus = boundary_buses[i]
                grid.add_load(bus=bus, api_obj=load)
        else:
            # add current values
            Ire = Ieq[i].real
            Iim = Ieq[i].imag
            if abs(Ire) > tol and abs(Iim) > tol:
                load = dev.Load(name=f"Ward equivalent load {i}", Ir=Ire * grid.Sbase, Ii=Iim * grid.Sbase)
                load.comment = "Added because of a Ward reduction of the grid"
                bus = boundary_buses[i]
                grid.add_load(bus=bus, api_obj=load)

    # Delete the external buses
    to_be_deleted = [grid.buses[e] for e in e_buses]
    for bus in to_be_deleted:
        grid.delete_bus(obj=bus, delete_associated=True)

    return grid, logger


if __name__ == '__main__':
    import GridCalEngine as gce

    fname = '/home/santi/Documentos/Git/GitHub/GridCal/src/tests/data/grids/Matpower/case9.m'
    fname_expected = '/home/santi/Documentos/Git/GitHub/GridCal/src/tests/data/grids/Matpower/ieee9_reduced.m'

    reduction_bus_indices_ = np.array([0, 4, 7])

    grid_ = gce.open_file(fname)
    grid_expected = gce.open_file(fname_expected)

    # ptdf = gce.linear_power_flow(grid=grid_).PTDF
    # ptdf_reduction_with_islands(grid=grid_,
    #                             reduction_bus_indices=np.array([0, 1, 2, 3, 7]),
    #                             PTDF=ptdf,
    #                             tol=1e-8)

    logger_ = di_shi_reduction(grid=grid_,
                               reduction_bus_indices=reduction_bus_indices_,
                               pf_res=gce.power_flow(grid_),
                               add_power_loads=True,
                               use_linear=True,
                               tol=1e-8)

    logger_.print()
