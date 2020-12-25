__author__ = 'spv86_000'
# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.
from numpy import ones, flatnonzero as find, intc, double, string_, where, delete, zeros, r_, where, delete
from scipy.sparse import csr_matrix as sparse

from .matpower_gen_definitions import GEN_BUS, GEN_STATUS
from .matpower_storage_definitions import BUS_S, STO_STATUS, StorageDispatchMode

from warnings import warn
"""
Defines constants for named column indices to bus matrix.

Some examples of usage, after defining the constants using the line above,
are::

    Pd = bus[3, PD]     # get the real power demand at bus 4
    bus[:, VMIN] = 0.95 # set the min voltage magnitude to 0.95 at all buses

The index, name and meaning of each column of the bus matrix is given
below:

columns 0-12 must be included in input matrix (in case file)
    0.  C{BUS_I}       bus number (1 to 29997)
    1.  C{BUS_TYPE}    bus type (1 = PQ, 2 = PV, 3 = ref, 4 = isolated)
    2.  C{PD}          real power demand (MW)
    3.  C{QD}          reactive power demand (MVAr)
    4.  C{GS}          shunt conductance (MW at V = 1.0 p.u.)
    5.  C{BS}          shunt susceptance (MVAr at V = 1.0 p.u.)
    6.  C{BUS_AREA}    area number, 1-100
    7.  C{VM}          voltage magnitude (p.u.)
    8.  C{VA}          voltage angle (degrees)
    9.  C{BASE_KV}     base voltage (kV)
    10. C{ZONE}        loss zone (1-999)
    11. C{VMAX}        maximum voltage magnitude (p.u.)
    12. C{VMIN}        minimum voltage magnitude (p.u.)

columns 13-16 are added to matrix after OPF solution
they are typically not present in the input matrix

(assume OPF objective function has units, u)
    13. C{LAM_P}       Lagrange multiplier on real power mismatch (u/MW)
    14. C{LAM_Q}       Lagrange multiplier on reactive power mismatch (u/MVAr)
    15. C{MU_VMAX}     Kuhn-Tucker multiplier on upper voltage limit (u/p.u.)
    16. C{MU_VMIN}     Kuhn-Tucker multiplier on lower voltage limit (u/p.u.)

additional constants, used to assign/compare values in the C{BUS_TYPE} column
    1.  C{PQ}    PQ bus
    2.  C{PV}    PV bus
    3.  C{REF}   reference bus
    4.  C{NONE}  isolated bus

@author: Ray Zimmerman (PSERC Cornell)
@author: Richard Lincoln
"""


# define bus types
PQ      = 1
PV      = 2
REF     = 3
NONE    = 4

# define the indices
BUS_I       = 0    # bus number (1 to 29997)
BUS_TYPE    = 1    # bus type
PD          = 2    # Pd, real power demand (MW)
QD          = 3    # Qd, reactive power demand (MVAr)
GS          = 4    # Gs, shunt conductance (MW at V = 1.0 p.u.)
BS          = 5    # Bs, shunt susceptance (MVAr at V = 1.0 p.u.)
BUS_AREA    = 6    # area number, 1-100
VM          = 7    # Vm, voltage magnitude (p.u.)
VA          = 8    # Va, voltage angle (degrees)
BASE_KV     = 9    # baseKV, base voltage (kV)
ZONE        = 10   # zone, loss zone (1-999)
VMAX        = 11   # maxVm, maximum voltage magnitude (p.u.)
VMIN        = 12   # minVm, minimum voltage magnitude (p.u.)

# included in opf solution, not necessarily in input
# assume objective function has units, u
LAM_P       = 13   # Lagrange multiplier on real power mismatch (u/MW)
LAM_Q       = 14   # Lagrange multiplier on reactive power mismatch (u/MVAr)
MU_VMAX     = 15   # Kuhn-Tucker multiplier on upper voltage limit (u/p.u.)
MU_VMIN     = 16   # Kuhn-Tucker multiplier on lower voltage limit (u/p.u.)

# bus location
BUS_X = 17  # X position for the graphical representation
BUS_Y = 18  # Y position for the graphical representation

COLLAPSED = 19

DISPATCHABLE_BUS = 20
FIX_POWER_BUS = 21



bus_format_array = [intc,
                    intc,
                    double,
                    double,
                    double,
                    double,
                    intc,
                    double,
                    double,
                    double,
                    intc,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    intc,
                    intc,
                    intc
                    ]

bus_headers = ["bus_i",
               "type",
               "Pd",
               "Qd",
               "Gs",
               "Bs",
               "area",
               "Vm",
               "Va",
               "baseKV",
               "zone",
               "Vmax",
               "Vmin",
               "LaM_P",
               "LaM_Q",
               "Mu_Vmax",
               "Mu_Vmin",
               "Bus_X",
               "Bus_Y",
               "Collapsed",
               "Dispatchable",
               "Fix_power"]


def bustypes(bus, gen, storage, Sbus, storage_dispatch_mode=StorageDispatchMode.no_dispatch):
    """
    Builds index lists of each type of bus (C{REF}, C{PV}, C{PQ}).

    Generators with "out-of-service" status are treated as L{PQ} buses with
    zero generation (regardless of C{Pg}/C{Qg} values in gen). Expects C{bus}
    and C{gen} have been converted to use internal consecutive bus numbering.

    @param bus: bus data
    @param gen: generator data
    @return: index lists of each bus type

    @author: Ray Zimmerman (PSERC Cornell)
    """
    # flag to indicate that it is impossible to solve the grid
    the_grid_is_disabled = False

    # get generator status
    nb = bus.shape[0]
    ng = gen.shape[0]
    ns = storage.shape[0]

    # gen connection matrix, element i, j is 1 if, generator j at bus i is ON
    Cg = sparse((gen[:, GEN_STATUS] > 0, (gen[:, GEN_BUS], range(ng))), (nb, ng))

    # gen connection matrix, element i, j is 1 if, storage j at bus i is ON
    Cs = sparse((storage[:, STO_STATUS] > 0, (storage[:, BUS_S], range(ns))), (nb, ns))

    # set all the nn ref buses type to PQ
    non_ref = find(bus[:, BUS_TYPE] != REF)
    bus[non_ref, BUS_TYPE] = PQ

    # Pick the selected reference buses
    ref = find(bus[:, BUS_TYPE] == REF)

    # Set the buses type according to the storage devices dispatch mode
    if storage_dispatch_mode == StorageDispatchMode.dispatch_vd:
        sto_bus = storage[Cs.indices, BUS_S].astype(int)
        bus[sto_bus, BUS_TYPE] = REF
        # Add the storage buses to the reference
        ref = r_[ref, sto_bus]

    elif storage_dispatch_mode == StorageDispatchMode.dispatch_pv:
        sto_bus = storage[Cs.indices, BUS_S].astype(int)
        bus[sto_bus, BUS_TYPE] = PV

    elif storage_dispatch_mode == StorageDispatchMode.no_dispatch:
        # Pick the selected reference buses
        ref = find(bus[:, BUS_TYPE] == REF)

    # Set the generator buses to PV
    gen_bus = gen[Cg.indices, GEN_BUS].astype(int)
    bus[gen_bus, BUS_TYPE] = PV

    # assembly the list of PQ nodes
    pq = find(bus[:, BUS_TYPE] == PQ)
    # assembly the list of PV nodes
    pv = find(bus[:, BUS_TYPE] == PV)
    # Remove the references from PV
    pv_ref_idx = where(pv==ref)[0]
    pv = delete(pv, pv_ref_idx)

    # Select a reference from the PV nodes is no reference was set
    if len(ref) == 0:
        if len(pv) > 0:
            ref = [pv[0]]    # use the first PV bus
            pv = pv[1:]      # take it off PV list
        else:
            # look for positive power injections to take the largest as the slack
            positive_power_injections = Sbus.real[where(Sbus.real > 0)[0]]
            if len(positive_power_injections) > 0:
                idx = where(Sbus.real == max(positive_power_injections))[0]
                if len(idx) == 1:
                    ref = idx
                    i = where(pq == idx[0])[0][0]
                    pq = delete(pq, i)
                else:
                    warn('It was not possible to find a slack bus')
                    the_grid_is_disabled = True
            else:
                warn('It was not possible to find a slack bus')
                the_grid_is_disabled = True

    # create the types array
    types = zeros(nb)
    types[ref] = REF
    types[pv] = PV
    types[pq] = PQ

    return ref, pv, pq, types, the_grid_is_disabled
