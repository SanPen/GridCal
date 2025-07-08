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
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_results import PowerFlowTimeSeriesResults


def ward_reduction(grid: MultiCircuit,
                   reduction_bus_indices: IntVec,
                   pf_res: PowerFlowResults,
                   pf_ts_res: PowerFlowTimeSeriesResults | None = None,
                   add_power_loads: bool = True):
    """
    In-place Grid reduction using the Ward equivalent model
    :param grid: MultiCircuit
    :param reduction_bus_indices: Bus indices of the buses to delete
    :param pf_res: PowerFlowResults
    :param pf_ts_res: PowerFlowTimeSeriesResults
    :param add_power_loads: If true Ward currents are converted to loads, else currents are added instead
    """
    nc = compile_numerical_circuit_at(grid, t_idx=None)

    adm = nc.get_admittance_matrices()

    # external bus indices (to reduce)
    e_buses = reduction_bus_indices

    # internal bus indices (to keep)
    i_buses = np.arange(nc.nbus)
    np.delete(i_buses, e_buses)

    YII = adm.Ybus[np.ix_(i_buses, i_buses)]
    YIE = adm.Ybus[np.ix_(i_buses, e_buses)]
    YEI = adm.Ybus[np.ix_(e_buses, i_buses)]
    YEE = adm.Ybus[np.ix_(e_buses, e_buses)]
    YEE_fact = factorized(YEE)

    # Ward Y
    Yred = YII - (YIE @ YEE_fact(YEI))

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
        load = dev.Load(name=f"Ward equivalent load {i}", P=Seq[i].real, Q=Seq[i].imag)
        load.comment = "Added because of a Ward reduction of the grid"
        bus = grid.buses[i]
        grid.add_load(bus=bus, api_obj=load)

    # Delete the external buses
    to_be_deleted = [grid.buses[e] for e in e_buses]
    for bus in to_be_deleted:
        grid.delete_bus(obj=bus, delete_associated=True)

def opti_kron_reduction(grid: MultiCircuit, reduction_bus_indices: IntVec):

    pass