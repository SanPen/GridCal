# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.Devices.Aggregation.investment import Investment
from VeraGridEngine.Devices.Aggregation.investments_group import InvestmentsGroup
from VeraGridEngine.Compilers.Gslv.activation import pg
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from typing import Dict

def convert_investment_group(elm: InvestmentsGroup) -> "pg.InvestmentGroup":
    """

    :param elm:
    :return:
    """
    return pg.InvestmentGroup(idtag=elm.idtag,
                              code=str(elm.code),
                              name=elm.name,
                              category=elm.category)


def add_investment_groups(circuit: MultiCircuit,
                          gslv_grid: "pg.MultiCircuit") -> Dict[InvestmentsGroup, "pg.InvestmentGroup"]:
    """

    :param circuit:
    :param gslv_grid:
    :return:
    """
    d = dict()

    for i, elm in enumerate(circuit.investments_groups):
        ig = convert_investment_group(elm)
        gslv_grid.add_investment_group(ig)
        d[elm] = ig

    return d


def convert_investment(
        elm: Investment,
        groups_dict: Dict[InvestmentsGroup, "pg.InvestmentGroup"]
) -> "pg.Investment":
    """

    :param elm:
    :param groups_dict:
    :return:
    """
    return pg.Investment(idtag=elm.idtag,
                         code=str(elm.code),
                         name=elm.name,
                         device_idtag=elm.device_idtag,
                         group=None if elm.group is None else groups_dict[elm.group],
                         CAPEX=elm.CAPEX,
                         OPEX=0.0,
                         status=elm.status, )


def add_investments(circuit: MultiCircuit,
                    gslv_grid: "pg.MultiCircuit",
                    groups_dict: Dict[InvestmentsGroup, "pg.InvestmentGroup"]):
    """

    :param circuit:
    :param gslv_grid:
    :param groups_dict:
    :return:
    """
    d = dict()

    for i, elm in enumerate(circuit.investments):
        investment = convert_investment(elm, groups_dict=groups_dict)
        gslv_grid.add_investment(investment)
        d[elm] = investment

    return d

