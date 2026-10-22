# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Dict

from VeraGridEngine.Compilers.Gslv.activation import build_status_dict, pg
from VeraGridEngine.Compilers.Gslv.common import fill_profile, set_injection_associations
from VeraGridEngine.Devices.Aggregation.facility import Facility
from VeraGridEngine.Devices.Associations.technology import Technology
from VeraGridEngine.Devices.Injections.static_generator import StaticGenerator
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import IntVec


def convert_static_generator(elm: StaticGenerator,
                             bus_dict: Dict[str, "pg.Bus"],
                             facility_dict: Dict[Facility, "pg.Facility"],
                             technology_dict: Dict[Technology, "pg.Technology"],
                             n_time: int,
                             use_time_series: bool,
                             time_indices: IntVec | None = None) -> "pg.StaticGenerator":
    """
    Convert one VeraGrid static generator into one GSLV static generator.

    :param elm: VeraGrid static generator.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param facility_dict: VeraGrid-to-GSLV facility lookup.
    :param technology_dict: VeraGrid-to-GSLV technology lookup.
    :param n_time: Number of exported time steps.
    :param use_time_series: Whether the export is time-series based.
    :param time_indices: Optional time-series selection.
    :return: GSLV static generator.
    """
    pe_inj = pg.StaticGenerator(
        idtag=elm.idtag,
        code=str(elm.code),
        name=elm.name,
        bus=None if elm.bus is None else bus_dict[elm.bus.idtag],
        nt=n_time,
        P=elm.P,
        Q=elm.Q,
        Cost=elm.Cost,
        active=elm.active,
        mttf=elm.mttf,
        mttr=elm.mttr,
        capex=elm.capex,
        opex=elm.opex,
        build_status=build_status_dict[elm.build_status],
    )
    set_injection_associations(
        gslv_elm=pe_inj,
        elm=elm,
        facility_dict=facility_dict,
        technology_dict=technology_dict,
    )

    fill_profile(pe_inj.active, elm.active_prof, use_time_series, time_indices, n_time, elm.active)
    fill_profile(pe_inj.P, elm.P_prof, use_time_series, time_indices, n_time, elm.P)
    fill_profile(pe_inj.Q, elm.Q_prof, use_time_series, time_indices, n_time, elm.Q)
    fill_profile(pe_inj.cost, elm.Cost_prof, use_time_series, time_indices, n_time, elm.Cost)

    return pe_inj


def add_static_generators(circuit: MultiCircuit,
                          gslv_grid: "pg.MultiCircuit",
                          bus_dict: Dict[str, "pg.Bus"],
                          facility_dict: Dict[Facility, "pg.Facility"],
                          technology_dict: Dict[Technology, "pg.Technology"],
                          time_series: bool,
                          n_time: int = 1,
                          time_indices: IntVec | None = None) -> None:
    """
    Add every VeraGrid static generator to the target GSLV grid.

    :param circuit: VeraGrid circuit.
    :param gslv_grid: GSLV circuit.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param facility_dict: VeraGrid-to-GSLV facility lookup.
    :param technology_dict: VeraGrid-to-GSLV technology lookup.
    :param time_series: Whether the export is time-series based.
    :param n_time: Number of exported time steps.
    :param time_indices: Optional time-series selection.
    :return: None.
    """
    devices = circuit.get_static_generators()
    for elm in devices:
        pe_inj = convert_static_generator(
            elm=elm,
            bus_dict=bus_dict,
            facility_dict=facility_dict,
            technology_dict=technology_dict,
            n_time=n_time,
            use_time_series=time_series,
            time_indices=time_indices,
        )
        gslv_grid.add_static_generator(pe_inj)
