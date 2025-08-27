# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from typing import Tuple, Sequence, TYPE_CHECKING
from scipy.sparse.linalg import factorized, spsolve
from scipy.sparse import csc_matrix, bmat

import networkx as nx
import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import IntVec, CxVec, Logger
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
    from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit


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

    return Yeq, Ybbp.tocsc()

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


def ward_reduction_linear2(Ybus: csc_matrix, e_buses: IntVec, i_buses: IntVec):
    """

    :param Ybus:
    :param e_buses:
    :param i_buses:
    :return:
    """

    # slice matrices

    Yii = Ybus[np.ix_(i_buses, i_buses)]
    Yie = Ybus[np.ix_(i_buses, e_buses)]

    Yei = Ybus[np.ix_(e_buses, i_buses)]
    Yee = Ybus[np.ix_(e_buses, e_buses)]

    Yee_fact = factorized(Yee.tocsc())

    Yeq = - Yie @ Yee_fact(Yei.toarray())  # 2.16

    # Ybbp = Yii + csc_matrix(Yeq)  # YBBp = YBB - YBE @ YEE_fact(YEB)  # 2.13

    return Yeq.tocsc()


def get_reduction_sets_1(nc: NumericalCircuit,
                         reduction_bus_indices: Sequence[int]) -> Tuple[IntVec, IntVec, IntVec, IntVec]:
    """
    Generate the set of bus indices for grid reduction
    :param nc: NumericalCircuit
    :param reduction_bus_indices: array of bus indices to reduce (external set)
    :return: external, boundary, internal, boundary_branches
    """

    external_set = set(reduction_bus_indices)
    boundary_set = set()
    internal_set = set()
    boundary_branches = list()

    for k in range(nc.nbr):
        f = nc.passive_branch_data.F[k]
        t = nc.passive_branch_data.T[k]
        if f in external_set:
            if t in external_set:
                # the branch belongs to the external set
                pass
            else:
                # the branch is a boundary link and t is a frontier bus
                boundary_set.add(t)
                boundary_branches.append(k)
        else:
            # we know f is not external...

            if t in external_set:
                # f is not in the external set, but t is: the branch is a boundary link and f is a frontier bus
                boundary_set.add(f)
                boundary_branches.append(k)
            else:
                # f nor t are in the external set: both belong to the internal set
                internal_set.add(f)
                internal_set.add(t)

    # buses cannot be in both the internal and boundary set
    elms_to_remove = list()
    for i in internal_set:
        if i in boundary_set:
            elms_to_remove.append(i)

    for i in elms_to_remove:
        internal_set.remove(i)

    # convert to arrays and sort
    external = np.sort(np.array(list(external_set)))
    boundary = np.sort(np.array(list(boundary_set)))
    internal = np.sort(np.array(list(internal_set)))
    boundary_branches = np.array(boundary_branches)

    return external, boundary, internal, boundary_branches


def create_new_boundary_branches(grid: MultiCircuit, b_buses: IntVec, Yeq_1: csc_matrix, Ybbp_1: csc_matrix,
                                 tol: float, use_linear=False):
    """

    :param grid:
    :param b_buses:
    :param Yeq_1:
    :param Ybbp_1:
    :param tol:
    :param use_linear:
    :return:
    """
    # add boundary equivalent sub-grid: traverse only the triangular
    max_x = 5.0
    for i in range(len(b_buses)):
        for j in range(i):
            if abs(Yeq_1[i, j]) > tol:

                if i == j:
                    # add shunt reactance
                    bus = b_buses[i]
                    yeq_row_i = Yeq_1[i, :].copy()
                    yeq_row_i[i] = 0
                    ysh = Ybbp_1[i, i] - np.sum(yeq_row_i)
                    if use_linear:
                        sh = dev.Shunt(name=f"Equivalent shunt {i}", B=ysh, G=0.0)
                    else:
                        sh = dev.Shunt(name=f"Equivalent shunt {i}", B=ysh.imag, G=ysh.real)
                    grid.add_shunt(bus=bus, api_obj=sh)
                else:
                    # add series reactance
                    f = b_buses[i]
                    t = b_buses[j]

                    z = - 1.0 / Yeq_1[i, j]

                    if z.imag <= max_x:
                        series_reactance = dev.SeriesReactance(
                            name=f"Equivalent boundary impedance {b_buses[i]}-{b_buses[j]}",
                            bus_from=grid.buses[f],
                            bus_to=grid.buses[t],
                            r=z.real,
                            x=z.imag
                        )
                        grid.add_series_reactance(series_reactance)


def find_gen_relocation(grid: MultiCircuit,
                        reduction_bus_indices: Sequence[int]):
    """
    Relocate generators
    :param grid: MultiCircuit
    :param reduction_bus_indices: array of bus indices to reduce (external set)
    :return: None
    """
    G = nx.Graph()
    bus_idx_dict = grid.get_bus_index_dict()
    external_set = set(reduction_bus_indices)
    external_gen_set = set()
    external_gen_data = list()
    internal_set = set()

    # loop through the generators in the external set
    for k, elm in enumerate(grid.generators):
        i = bus_idx_dict[elm.bus]
        if i in external_set:
            external_set.remove(i)
            external_gen_set.add(i)
            external_gen_data.append((k, i, 'generator'))
            G.add_node(i)

    # loop through the branches
    for branch in grid.get_branches(add_vsc=False, add_hvdc=False, add_switch=True):
        f = bus_idx_dict[branch.bus_from]
        t = bus_idx_dict[branch.bus_to]
        if f in external_set or t in external_set:
            # the branch belongs to the external set
            pass
        else:
            # f nor t are in the external set: both belong to the internal set
            internal_set.add(f)
            internal_set.add(t)

        G.add_node(f)
        G.add_node(t)
        w = branch.get_weight()
        G.add_edge(f, t, weight=w)

    # convert to arrays and sort
    # external = np.sort(np.array(list(external_set)))
    # purely_internal_set = np.sort(np.array(list(purely_internal_set)))

    purely_internal_set = list(internal_set - external_gen_set)

    # now, for every generator, we need to find the shortest path in the "purely internal set"
    for elm_idx, bus_idx, tpe in external_gen_data:
        # Compute shortest path lengths from this source
        lengths = nx.single_source_shortest_path_length(G, bus_idx)

        # Filter only target nodes
        target_distances = {t: lengths[t] for t in purely_internal_set if t in lengths}
        if target_distances:

            # Pick the closest
            closest = min(target_distances, key=target_distances.get)

            # relocate
            if tpe == 'generator':
                grid.generators[elm_idx].bus = grid.buses[closest]


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

    nc = compile_numerical_circuit_at(grid, t_idx=None)

    # Step 1 – First Ward reduction ------------------------------------------------------------------------------------

    # This first reduction is to obtain the equivalent admittance matrix Y_eq1
    # that serves to create the inter-boundary branches that represent the grid
    # that we are going to remove.
    # For this the buses to keep are the internal (I) + boundary (B).

    # find the boundary set: buses from the internal set the join to the external set
    e_buses, b_buses, i_buses, b_branches = get_reduction_sets_1(nc=nc, reduction_bus_indices=reduction_bus_indices)

    if len(e_buses) == 0:
        logger.add_info(msg="Nothing to reduce")
        return logger

    if len(i_buses) == 0:
        logger.add_info(msg="Nothing to keep (null grid as a result)")
        return logger

    if len(b_buses) == 0:
        logger.add_info(msg="The reducible and non reducible sets are disjoint and cannot be reduced")
        return logger

    indices = nc.get_simulation_indices()
    adm = nc.get_admittance_matrices()

    if not use_linear and pf_res is None:
        logger.add_warning("Cannot uses non linear since power flow results are None")
        use_linear = True

    Yeq_1, Ybbp_1 = ward_reduction_linear(Ybus=adm.Ybus, e_buses=e_buses, b_buses=b_buses, i_buses=i_buses)

    create_new_boundary_branches(grid=grid, b_buses=b_buses, Yeq_1=Yeq_1, Ybbp_1=Ybbp_1, tol=tol, use_linear=False)

    # Step 2 – Second Ward reduction: Extending to the external generation buses ---------------------------------------

    # The second reduction is to generate another equivalent admittance matrix Y_eq2
    # that we use as adjacency matrix to search the closest bus to move each generator
    # that is external.
    # For this the buses to keep are the internal (I) + boundary (B) + the generation buses of E.

    find_gen_relocation(grid=grid, reduction_bus_indices=reduction_bus_indices)

    # remove the buses of the external system finally
    # Delete the external buses
    to_be_deleted = [grid.buses[e] for e in e_buses]
    for bus in to_be_deleted:
        grid.delete_bus(obj=bus, delete_associated=True)

    # Step 3 – Relocate generators -------------------------------------------------------------------------------------

    # Using the matrix Y_eq2, we calculate the shortest paths from every external
    # generation bus, to all the other buses in I + B. The end of each path will
    # be the relocation bus of every external generator.

    # This is done in the step before: In the original Di-Shi reduction method,
    # they use a second ward reduction to compute the distances, however that
    # can be done directly

    # Step 4 – Relocate loads with inverse power flow ------------------------------------------------------------------

    # Let's not forget about the loads! in order to move the external loads such that
    # the reduced flows resemble the original flows (even after brutally moving the generators!),
    # we need to perform an inverse power flow.
    #
    # First, we need to run a linear power flow in the original system.
    # That will get us the original voltage angles.
    #
    # Second, we need to form the admittance matrix of the reduced grid
    # (including the inter-boundary branches), and multiply this admittance matrix
    # by the original voltage angles for the reduced set of buses.
    # This gets us the "final" power injections in the reduced system.
    #
    # From those, we need to subtract the reduced grid injections.
    # This will provide us with a vector of new loads that we need
    # to add at the corresponding reduced grid buses in order to have a final equivalent.

    nc_red = compile_numerical_circuit_at(grid, t_idx=0)
    adm = nc_red.get_admittance_matrices()

    Vred = np.delete(pf_res.voltage, e_buses)

    S_expected = (Vred * np.conj(adm.Ybus @ Vred)) * grid.Sbase

    Sred_current = grid.get_Sbus()

    dSred = Sred_current - S_expected

    # add loads
    for i, S in enumerate(dSred):
        ld = dev.Load(name=f"compensation {i}", P=S.real, Q=S.imag)
        grid.add_load(bus=grid.buses[i], api_obj=ld)

    return grid, logger


if __name__ == '__main__':
    import VeraGridEngine as gce

    fname = '/home/santi/Documentos/Git/GitHub/VeraGrid/src/tests/data/grids/Matpower/case9.m'
    fname_expected = '/home/santi/Documentos/Git/GitHub/VeraGrid/src/tests/data/grids/Matpower/ieee9_reduced.m'

    reduction_bus_indices_ = np.array([2, 4, 5, 6])

    grid_ = gce.open_file(fname)
    grid_expected = gce.open_file(fname_expected)

    grid_red, logger_ = di_shi_reduction(grid=grid_.copy(),
                                         reduction_bus_indices=reduction_bus_indices_,
                                         pf_res=gce.power_flow(grid_),
                                         add_power_loads=True,
                                         use_linear=True,
                                         tol=1e-8)

    logger_.print()
