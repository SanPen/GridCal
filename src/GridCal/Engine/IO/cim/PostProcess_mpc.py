"""
The PYPOWER extension converts :class:`Case` objects to PYPOWER cases and
writes results from a power flow calculation back to the orignal case instance.
The module ``PostProcess_CIM_files`` defines function to be used for preprocessing CIM files before they are parsed with
the ``PyCIM`` ``RDFXMLReader``. Most often it means fixing certain HTML tags.

.. note:: This module is based mostly on the the started but never finished OpenSource project Cim2BusBranch https://www.versioneye.com/Python/Cim2BusBranch/0.1

.. seealso:: :py:func:`CIM2Matpower.cim_to_mpc` and the Matlab functions ``MPC_NODAL2BB`` and ``MPC_BB2NODAL``

:Date: 2016-05-10
:Authors: Konstantin Gerasimov
:e-mail: kkgerasimov@gmail.com

:Credits: This function is created for KU-Leuven as part of the GARPUR project http://www.garpur-project.eu
"""
from pypower import idx_bus, idx_gen, idx_brch
import numpy as np

from Topology_BusBranch import bus_type


bus_type_map = {
    bus_type.PQ: idx_bus.PQ,
    bus_type.PV: idx_bus.PV,
    bus_type.REF: idx_bus.REF,
    bus_type.ISOLATED: idx_bus.NONE,
}


def create_mpc(case, node_breaker_topology):
    """Creates and returns a Matpower case (mpc) from *case*."""

    node_breaker_topology_dict = {'nodes': node_breaker_topology.nodes,
                'areas':node_breaker_topology.areas,
                'zones':node_breaker_topology.zones,
                'substations': node_breaker_topology.substations,
                'switches': node_breaker_topology.switches,
                'branches': node_breaker_topology.branches,
                'generators': node_breaker_topology.generators,
                'loads': node_breaker_topology.loads,
                'shunts': node_breaker_topology.shunts,
                'phasetapchangers': node_breaker_topology.phasetapchangers,
                'ratiotapchangers': node_breaker_topology.ratiotapchangers,
                'CIM_filenames': node_breaker_topology.CIM_filenames,
                }

    mpc = {
        'version': '2',
        'baseMVA': case.base_mva,
        'bus': _make_bus_list(case),
        'gen': _make_gen_list(case.generators, case.bus_ids),
        'branch': _make_branch_list(case.branches, case.bus_ids),
        'NodeBreaker_topology': node_breaker_topology_dict,
    }
    return mpc


# def write_results_to_case(ppc, case):
#     """
#     Write the results of a pf computation ((re)active power, voltage magnitude
#     and angle) back to the *case*.
#
#     """
#     for res, bus in zip(ppc['bus'], case.buses):
#         assert res[idx_bus.BUS_I] == case.bus_ids[bus]
#
#         bus.pd = res[idx_bus.PD]
#         bus.qd = res[idx_bus.QD]
#         bus.vm = res[idx_bus.VM]
#         bus.va = res[idx_bus.VA]
#
#     for res, gen in zip(ppc['gen'], case.generators):
#         assert res[idx_gen.GEN_BUS] == case.bus_ids[gen.bus]
#
#         gen.pg = res[idx_gen.PG]
#         gen.qg = res[idx_gen.QG]
#
#     for res, branch in zip(ppc['branch'], case.branches):
#         assert res[idx_brch.F_BUS] == case.bus_ids[branch.from_bus]
#         assert res[idx_brch.T_BUS] == case.bus_ids[branch.to_bus]
#
#         branch.p_from = res[idx_brch.PF]
#         branch.q_from = res[idx_brch.QF]
#         branch.p_to = res[idx_brch.PT]
#         branch.q_to = res[idx_brch.QT]


def _make_bus_list(case):
    """Creates a list ob bus arrays for PYPOWER."""
    # Needs *case* to create/update the mapping bus: bus_id mapping
    # PYPOWER bus description has 13 (or +4) entries
    bus_list = np.zeros((len(case.buses), 13), dtype=np.float64)

    case.bus_ids = {}

    for i, bus in enumerate(case.buses):
        case.bus_ids[bus] = bus.id
        _fill_bus_array(bus_list[i], bus, bus.id)

    return bus_list


def _fill_bus_array(bus_array, bus, bus_id):
    """Fills the array of a bus with its values."""
    bus_array[idx_bus.BUS_I] = bus_id
    bus_array[idx_bus.BUS_TYPE] = bus.btype
    bus_array[idx_bus.PD] = bus.pd
    bus_array[idx_bus.QD] = bus.qd
    bus_array[idx_bus.GS] = bus.gs
    bus_array[idx_bus.BS] = bus.bs
    bus_array[idx_bus.BUS_AREA] = bus.area
    bus_array[idx_bus.VM] = bus.vm
    bus_array[idx_bus.VA] = bus.va
    bus_array[idx_bus.BASE_KV] = bus.base_kv
    bus_array[idx_bus.ZONE] = bus.zone
    bus_array[idx_bus.VMAX] = bus.vm_max
    bus_array[idx_bus.VMIN] = bus.vm_min

def _make_bus_names(case):
    """Creates a list with the busnames."""
    return [bus.name for bus in case.buses]


def _make_gen_list(generators, bus_ids):
    """Creates a list of generators for PYPOWER."""
    # PYPOWER gen description has 21 (+4) entries
    gen_list = np.zeros((len(generators), 21), dtype=np.float64)

    for i, gen in enumerate(generators):
        _fill_gen_array(gen_list[i], gen, bus_ids)

    return gen_list


def _fill_gen_array(gen_array, gen, bus_ids):
    """Fills the array of a gen with its values."""
    gen_array[idx_gen.GEN_BUS] = bus_ids[gen.bus]
    gen_array[idx_gen.PG] = gen.pg
    gen_array[idx_gen.QG] = gen.qg
    gen_array[idx_gen.QMAX] = gen.qg_max
    gen_array[idx_gen.QMIN] = gen.qg_min
    gen_array[idx_gen.VG] = gen.vg
    gen_array[idx_gen.MBASE] = gen.base_mva
    gen_array[idx_gen.GEN_STATUS] = gen.online
    gen_array[idx_gen.PMAX] = gen.pg_max
    gen_array[idx_gen.PMIN] = gen.pg_min
    gen_array[idx_gen.PC1] = gen.pc1
    gen_array[idx_gen.PC2] = gen.pc2
    gen_array[idx_gen.QC1MIN] = gen.qc1_min
    gen_array[idx_gen.QC1MAX] = gen.qc1_max
    gen_array[idx_gen.QC2MIN] = gen.qc2_min
    gen_array[idx_gen.QC2MAX] = gen.qc2_max
    gen_array[idx_gen.RAMP_AGC] = gen.ramp_agc
    gen_array[idx_gen.RAMP_10] = gen.ramp_10
    gen_array[idx_gen.RAMP_30] = gen.ramp_30
    gen_array[idx_gen.RAMP_Q] = gen.ramp_q
    gen_array[idx_gen.APF] = gen.apf


def _make_branch_list(branches, bus_ids):
    """Creates a list of branches for PYPOWER."""
    # PYPOWER branch description has 17 (+4) entries
    branch_list = np.zeros((len(branches), 17), dtype=np.float64)

    for i, branch in enumerate(branches):
        _fill_branch_array(branch_list[i], branch, bus_ids)

    return branch_list


def _fill_branch_array(branch_array, branch, bus_ids):
    """Fills the array of a gen with its values."""
    branch_array[idx_brch.F_BUS] = bus_ids[branch.from_bus]
    branch_array[idx_brch.T_BUS] = bus_ids[branch.to_bus]
    branch_array[idx_brch.BR_R] = branch.r
    branch_array[idx_brch.BR_X] = branch.x
    branch_array[idx_brch.BR_B] = branch.b
    branch_array[idx_brch.RATE_A] = branch.rate_a
    branch_array[idx_brch.RATE_B] = branch.rate_b
    branch_array[idx_brch.RATE_C] = branch.rate_c
    branch_array[idx_brch.TAP] = branch.ratio
    branch_array[idx_brch.SHIFT] = branch.angle
    branch_array[idx_brch.BR_STATUS] = branch.online
    branch_array[idx_brch.ANGMIN] = branch.angle_min
    branch_array[idx_brch.ANGMAX] = branch.angle_max
    branch_array[idx_brch.PF] = branch.p_from
    branch_array[idx_brch.QF] = branch.q_from
    branch_array[idx_brch.PT] = branch.p_to
    branch_array[idx_brch.QT] = branch.q_to
