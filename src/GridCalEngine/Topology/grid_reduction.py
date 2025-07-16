# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING
from scipy.sparse.linalg import factorized, spsolve
from scipy.sparse import csc_matrix, bmat
import GridCalEngine.Devices as dev
from GridCalEngine.basic_structures import IntVec, Logger
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearAnalysis
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at

if TYPE_CHECKING:
    from GridCalEngine.Devices.multi_circuit import MultiCircuit
    from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


def ward_reduction(grid: MultiCircuit,
                   reduction_bus_indices: IntVec,
                   pf_res: PowerFlowResults | None = None,
                   add_power_loads: bool = True,
                   use_linear: bool = False,
                   tol=1e-8) -> Logger:
    """
    In-place Grid reduction using the Ward equivalent model
    from: Power System Network Reduction for Engineering and Economic Analysis by Di Shi, 2012
    :param grid: MultiCircuit
    :param reduction_bus_indices: Bus indices of the buses to delete
    :param pf_res: PowerFlowResults
    :param add_power_loads: If true Ward currents are converted to loads, else currents are added instead
    :param use_linear: if true, the admittance matrix is used and no voltages are required
    :param tol: Tolerance, any equivalent power value under this is omitted
    """
    logger = Logger()

    # find the boundary set: buses from the internal set the join to the external set
    e_buses, b_buses, i_buses = grid.get_reduction_sets(reduction_bus_indices=reduction_bus_indices)

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

    if use_linear:
        indices = nc.get_simulation_indices()
        adm = nc.get_linear_admittance_matrices(indices)
        Ybus = adm.Bbus
    else:
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

    YEE_fact = factorized(YEE)

    Yeq = - YBE @ YEE_fact(YEB.toarray())  # 2.16
    YBBp = YBB + csc_matrix(Yeq)  # YBBp = YBB - YBE @ YEE_fact(YEB)  # 2.13

    # compute the current
    I = (pf_res.Sbus / nc.Sbase) / np.conj(pf_res.voltage)
    II = I[i_buses]
    IB = I[b_buses]
    IE = I[e_buses]

    Ieq = - YBE @ YEE_fact(IE)  # 2.17

    if use_linear:
        Seq = Ieq

    else:
        # now, we compute the new voltages at the internal and boundary (2.15)
        Ysys = bmat(blocks=[[YII.tocsc(), YIB.tocsc()], [YBI.tocsc(), YBBp.tocsc()]], format='csc')
        IBp = IB + Ieq  # IBp = IB - YBE @ YEE_fact(IE)  # 2.14
        Isys = np.r_[II, IBp]
        V = spsolve(Ysys, Isys)
        ni = len(i_buses)
        VI = V[:ni]
        VB = V[ni:]

        Seq = VB * np.conj(IB)

    n_boundary = len(b_buses)

    # add boundary buses
    # boundary_buses = [dev.Bus(name=f'Boundary {i}') for i in range(n_boundary)]
    boundary_buses = [grid.buses[b_buses[i]] for i in range(n_boundary)]
    grid.buses.extend(boundary_buses)

    # add boundary equivalent sub-grid
    # for i in range(n_boundary):
    #     for j in range(n_boundary):
    #         if abs(Yeq[i, j]) > tol:
    #
    #             if i == j:
    #                 bus_from = grid.buses[b_buses[i]]
    #                 bus_to = boundary_buses[i]
    #             else:
    #                 bus_from = boundary_buses[i]
    #                 bus_to = boundary_buses[j]
    #
    #             z = 1.0 / Yeq[i, j]
    #             series_reactance = dev.SeriesReactance(
    #                 name=f"Equivalent boundary impedance {i}-{j}",
    #                 bus_from=bus_from,
    #                 bus_to=bus_to,
    #                 r=z.real,
    #                 x=z.imag
    #             )
    #             grid.add_series_reactance(series_reactance)

    # Add loads at the boundary buses
    for i in range(n_boundary):
        if add_power_loads:
            # add power values
            P = Seq[i].real
            Q = Seq[i].imag
            if abs(P) > tol and abs(Q) > tol:
                load = dev.Load(name=f"Ward equivalent load {i}", P=P, Q=Q)
                load.comment = "Added because of a Ward reduction of the grid"
                bus = boundary_buses[i]
                grid.add_load(bus=bus, api_obj=load)
        else:
            # add current values
            Ire = Ieq[i].real
            Iim = Ieq[i].imag
            if abs(Ire) > tol and abs(Iim) > tol:
                load = dev.Load(name=f"Ward equivalent load {i}", Ir=Ire, Ii=Iim)
                load.comment = "Added because of a Ward reduction of the grid"
                bus = boundary_buses[i]
                grid.add_load(bus=bus, api_obj=load)

    # Delete the external buses
    to_be_deleted = [grid.buses[e] for e in e_buses]
    for bus in to_be_deleted:
        grid.delete_bus(obj=bus, delete_associated=True)

    return logger


def ptdf_reduction(grid: MultiCircuit,
                   reduction_bus_indices: IntVec,
                   tol=1e-8) -> Logger:
    """
    In-place Grid reduction using the Ward equivalent model
    from: Power System Network Reduction for Engineering and Economic Analysis by Di Shi, 2012
    :param grid: MultiCircuit
    :param reduction_bus_indices: Bus indices of the buses to delete
    :param tol: Tolerance, any equivalent power value under this is omitted
    """
    logger = Logger()

    # find the boundary set: buses from the internal set the join to the external set
    e_buses, b_buses, i_buses = grid.get_reduction_sets(reduction_bus_indices=reduction_bus_indices)

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

    lin = LinearAnalysis(nc=nc, distributed_slack=False)

    # PTDF (branches, buses)
