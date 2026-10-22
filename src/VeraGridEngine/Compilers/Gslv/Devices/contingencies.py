# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.Devices.Events.contingency import Contingency
from VeraGridEngine.Devices.Events.contingency_group import ContingencyGroup
from VeraGridEngine.Compilers.Gslv.activation import (
    contingency_ops_type_dict,
    pg,
)
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from typing import Dict

def convert_contingency_groups(elm: ContingencyGroup) -> "pg.ContingencyGroup":
    """

    :param elm:
    :return:
    """
    return pg.ContingencyGroup(idtag=elm.idtag,
                               code=str(elm.code),
                               name=elm.name,
                               category=elm.category)


def add_contingency_groups(circuit: MultiCircuit,
                           gslv_grid: "pg.MultiCircuit") -> Dict[ContingencyGroup, "pg.ContingencyGroup"]:
    """
    Add GSLV ContingenciesGroup
    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV Circuit
    :return: Dictionary [VeraGrid ContingenciesGroup] -> GSLV ContingenciesGroup
    """
    d = dict()

    for i, elm in enumerate(circuit.get_contingency_groups()):
        cg = convert_contingency_groups(elm)
        gslv_grid.add_contingency_group(cg)
        d[elm] = cg

    return d


def convert_contingencies(elm: Contingency,
                          n_time: int,
                          groups_dict: Dict[ContingencyGroup, "pg.ContingencyGroup"]) -> "pg.Contingency":
    """

    :param elm:
    :param n_time:
    :param groups_dict:
    :return:
    """

    return pg.Contingency(idtag=elm.idtag,
                          device_idtag=elm.device_idtag,
                          name=elm.name,
                          code=str(elm.code),
                          prop=contingency_ops_type_dict[elm.prop],
                          value=elm.value,
                          group=None if elm.group is None else groups_dict[elm.group])


def add_contingencies(circuit: MultiCircuit,
                      gslv_grid: "pg.MultiCircuit",
                      n_time: int,
                      groups_dict: Dict[ContingencyGroup, "pg.ContingencyGroup"], ):
    """
    Add GSLV ContingenciesGroup
    :param circuit: VeraGrid circuit
    :param gslv_grid: GSLV Circuit
    :param n_time: number of time steps
    :param groups_dict: Contingency groups dictionary
    :return: Dictionary [VeraGrid ContingenciesGroup] -> GSLV ContingenciesGroup
    """
    d = dict()

    for i, elm in enumerate(circuit.contingencies):
        con = convert_contingencies(elm=elm,
                                    n_time=n_time,
                                    groups_dict=groups_dict)
        gslv_grid.add_contingency(con)
        d[elm] = con

    return d

