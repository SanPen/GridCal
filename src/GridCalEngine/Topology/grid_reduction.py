# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from scipy.sparse.linalg import factorized

from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import IntVec
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


def ward_reduction(grid: MultiCircuit,
                   reduction_bus_indices: IntVec,
                   pf_res: PowerFlowResults | None = None,
                   add_power_loads: bool = True,
                   use_linear: bool = False):
    """
    In-place Grid reduction using the Ward equivalent model
    :param grid: MultiCircuit
    :param reduction_bus_indices: Bus indices of the buses to delete
    :param pf_res: PowerFlowResults
    :param add_power_loads: If true Ward currents are converted to loads, else currents are added instead
    :param use_linear: if true, the admittance matrix is used and no voltages are required
    """
    nc = compile_numerical_circuit_at(grid, t_idx=None)

    if use_linear:
        indices = nc.get_simulation_indices()
        adm = nc.get_linear_admittance_matrices(indices)
        Ybus = adm.Bbus
    else:
        adm = nc.get_admittance_matrices()
        Ybus = adm.Ybus

    # external bus indices (to reduce)
    e_buses = reduction_bus_indices

    # internal bus indices (to keep)
    i_buses = np.arange(nc.nbus)
    np.delete(i_buses, e_buses)

    YII = Ybus[np.ix_(i_buses, i_buses)]
    YIE = Ybus[np.ix_(i_buses, e_buses)]
    YEI = Ybus[np.ix_(e_buses, i_buses)]
    YEE = Ybus[np.ix_(e_buses, e_buses)]
    YEE_fact = factorized(YEE)

    # Ward Y
    Yred = YII - (YIE @ YEE_fact(YEI))

    if use_linear:
        # Compute the external currents
        I = nc.get_power_injections_pu().real
        Ii = I[i_buses]  # internal buses current
        Ie = I[e_buses]  # external buses current

        # compute the equivalent internal currents
        Ieq = Ii - (YIE @ YEE_fact(Ie))

        # Convert the currents to power
        Seq = Ieq
    else:
        # Compute the external currents
        I = np.conj(pf_res.Sbus / pf_res.voltage)
        Ii = I[i_buses]  # internal buses current
        Ie = I[e_buses]  # external buses current

        # compute the equivalent internal currents
        Ieq = Ii - (YIE @ YEE_fact(Ie))

        # Convert the currents to power
        Seq = pf_res.voltage[i_buses] * np.conj(Ieq)

    # Add loads
    for i in i_buses:
        if add_power_loads:
            # add power values
            P = Seq[i].real
            Q = Seq[i].imag
            if P != 0 and Q != 0:
                load = dev.Load(name=f"Ward equivalent load {i}", P=P, Q=Q)
                load.comment = "Added because of a Ward reduction of the grid"
                bus = grid.buses[i]
                grid.add_load(bus=bus, api_obj=load)
        else:
            # add current values
            Ire = Ieq[i].real
            Iim = Ieq[i].imag
            if Ire != 0 and Iim != 0:
                load = dev.Load(name=f"Ward equivalent load {i}", Ir=Ire, Ii=Iim)
                load.comment = "Added because of a Ward reduction of the grid"
                bus = grid.buses[i]
                grid.add_load(bus=bus, api_obj=load)

    # Delete the external buses
    to_be_deleted = [grid.buses[e] for e in e_buses]
    for bus in to_be_deleted:
        grid.delete_bus(obj=bus, delete_associated=True)

def opti_kron_reduction(grid: MultiCircuit, reduction_bus_indices: IntVec):

    pass