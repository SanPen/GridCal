# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import os.path
import warnings
import numpy as np
from typing import List, Dict, Union, TYPE_CHECKING

import GridCalEngine
from GridCalEngine.basic_structures import IntVec, Vec
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import (HvdcControlType, SolverType, TimeGrouping,
                                        ZonalGrouping, MIPSolvers, ContingencyMethod,
                                        BuildStatus)
import GridCalEngine.Devices as dev
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults

from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit

from GridCalEngine.IO.file_system import get_create_gridcal_folder
from GridCalEngine.basic_structures import ConvergenceReport

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
    from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
    from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
    from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions
    from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults

GSLV_RECOMMENDED_VERSION = "0.0.4"
GSLV_VERSION = ''
GSLV_AVAILABLE = False
try:
    import pygslv as pg

    pg.activate(os.path.join(get_create_gridcal_folder(), "license.gslv"), verbose=True)

    # activate
    if not pg.isLicensed():
        # license not found
        GSLV_AVAILABLE = False
    else:
        # already activated
        GSLV_AVAILABLE = True
        GSLV_VERSION = pg.get_version()

    if GSLV_AVAILABLE:
        if GSLV_VERSION < GSLV_RECOMMENDED_VERSION:
            warnings.warn(f"Recommended version for GSLV is {GSLV_RECOMMENDED_VERSION} "
                          f"instead of {GSLV_VERSION}")

except ImportError as e:
    pg = None
    GSLV_AVAILABLE = False
    GSLV_VERSION = ''

# numpy integer type for GSLV's uword
BINT = np.ulonglong


def get_gslv_mip_solvers_list() -> List[str]:
    """
    Get list of available MIP solvers
    :return:
    """
    if GSLV_AVAILABLE:
        return list()
    else:
        return list()


def get_final_profile(time_series: bool,
                      time_indices: Union[IntVec, None],
                      profile: Union[IntVec, Vec, None],
                      ntime=1,
                      default_val=0,
                      dtype=float) -> Union[Vec, IntVec]:
    """
    Generates a default time series
    :param time_series: use time series?
    :param time_indices: time series indices if any (optional)
    :param profile: Profile array (must be provided if time_series = True
    :param ntime: (if time_series = False) number of time steps
    :param default_val: Default value
    :param dtype: data type (float, int, etc...)
    :return: Profile array
    """

    if time_series:
        return profile if time_indices is None else profile[time_indices]
    else:
        return np.full(ntime, default_val, dtype=dtype)


def convert_area(area: dev.Area) -> "pg.Area":
    """
    
    :param area:
    :return:
    """
    return pg.Area(idtag=area.idtag, code=str(area.code), name=area.name)


def add_areas(circuit: MultiCircuit,
              gslv_grid: "pg.MultiCircuit") -> Dict[dev.Area, "pg.Area"]:
    """
    Add GSLV Areas
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :return: Dictionary [GridCal area] -> GSLV Area
    """
    d = dict()

    for i, area in enumerate(circuit.areas):
        elm = convert_area(area)
        gslv_grid.add_area(elm)
        d[area] = elm

    return d


def convert_zone(zone: dev.Zone) -> "pg.Zone":
    return pg.Zone(idtag=zone.idtag, code=str(zone.code), name=zone.name)


def add_zones(circuit: MultiCircuit,
              gslv_grid: "pg.MultiCircuit") -> Dict[dev.Zone, "pg.Zone"]:
    """
    Add GSLV Zones
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :return: Dictionary [GridCal Zone] -> GSLV Zone
    """
    d = dict()

    for i, zone in enumerate(circuit.zones):
        elm = convert_zone(zone)
        gslv_grid.add_zone(elm)
        d[zone] = elm

    return d


def convert_contingency_groups(elm: dev.ContingencyGroup) -> "pg.ContingencyGroup":
    return pg.ContingencyGroup(idtag=elm.idtag,
                               code=str(elm.code),
                               name=elm.name,
                               category=elm.category)


def add_contingency_groups(circuit: MultiCircuit,
                           gslv_grid: "pg.MultiCircuit") -> Dict[dev.ContingencyGroup, "pg.ContingencyGroup"]:
    """
    Add GSLV ContingenciesGroup
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :return: Dictionary [GridCal ContingenciesGroup] -> GSLV ContingenciesGroup
    """
    d = dict()

    for i, elm in enumerate(circuit.get_contingency_groups()):
        dev = convert_contingency_groups(elm)
        gslv_grid.add_contingency_group(dev)
        d[elm] = dev

    return d


def convert_contingencies(elm: dev.Contingency,
                          n_time: int,
                          groups_dict: Dict[dev.ContingencyGroup, "pg.ContingencyGroup"]) -> "pg.Contingency":
    return pg.Contingency(idtag=elm.idtag,
                          code=str(elm.code),
                          name=elm.name,
                          nt=n_time,
                          device_idtag=elm.device_idtag,
                          prop=elm.prop,
                          value=elm.value,
                          group=groups_dict[elm.group])


def add_contingencies(circuit: MultiCircuit,
                      gslv_grid: "pg.MultiCircuit",
                      n_time: int,
                      groups_dict: Dict[dev.ContingencyGroup, "pg.ContingencyGroup"], ):
    """
    Add GSLV ContingenciesGroup
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :param n_time: number of time steps
    :param groups_dict: Contingency groups dictionary
    :return: Dictionary [GridCal ContingenciesGroup] -> GSLV ContingenciesGroup
    """
    d = dict()

    for i, elm in enumerate(circuit.contingencies):
        dev = convert_contingencies(elm=elm, n_time=n_time, groups_dict=groups_dict[elm.group])

        gslv_grid.add_contingency(dev)

        d[elm] = dev

    return d


def convert_investment_group(elm: dev.InvestmentsGroup) -> "pg.InvestmentGroup":
    return pg.InvestmentGroup(idtag=elm.idtag,
                              code=str(elm.code),
                              name=elm.name,
                              category=elm.category)


def add_investment_groups(circuit: MultiCircuit, gslv_grid: "pg.MultiCircuit"):
    """

    :param circuit:
    :param gslv_grid:
    :return:
    """
    d = dict()

    for i, elm in enumerate(circuit.investments_groups):
        dev = convert_investment_group(elm)
        gslv_grid.add_investment_group(dev)
        d[elm] = dev

    return d


def convert_investment(elm: dev.Investment,
                       groups_dict: Dict[dev.InvestmentsGroup, "pg.InvestmentGroup"]) -> "pg.Investment":
    return pg.Investment(idtag=elm.idtag,
                         code=str(elm.code),
                         name=elm.name,
                         device_idtag=elm.device_idtag,
                         group=groups_dict[elm.group],
                         CAPEX=elm.CAPEX,
                         OPEX=elm.OPEX)


def add_investments(circuit: MultiCircuit,
                    gslv_grid: "pg.MultiCircuit",
                    groups_dict: Dict[dev.InvestmentsGroup, "pg.InvestmentGroup"]):
    """

    :param circuit:
    :param gslv_grid:
    :param groups_dict:
    :return:
    """
    d = dict()

    for i, elm in enumerate(circuit.investments):
        dev = convert_investment(elm, groups_dict=groups_dict[elm.group])
        gslv_grid.add_investment(dev)
        d[elm] = dev

    return d


def convert_bus(bus: dev.Bus, n_time: int,
                area_dict: Dict[dev.Area, "pg.Area"],
                time_indices: IntVec,
                use_time_series: bool) -> "pg.Bus":
    elm = pg.Bus(idtag=bus.idtag,
                 code=str(bus.code),
                 name=bus.name,
                 nt=n_time,
                 is_slack=bus.is_slack,
                 is_dc=bus.is_dc,
                 Vnom=bus.Vnom,
                 vmin=bus.Vmin,
                 vmax=bus.Vmax,
                 angle_min=bus.angle_min,
                 angle_max=bus.angle_max,
                 area=area_dict.get(bus.area, None))

    if use_time_series and n_time > 1:
        elm.active = (bus.active_prof.astype(BINT)
                      if time_indices is None
                      else bus.active_prof.astype(BINT)[time_indices])
    else:
        elm.set_active_val(int(bus.active))

    return elm


def add_buses(circuit: MultiCircuit,
              gslv_grid: "pg.MultiCircuit",
              use_time_series: bool,
              n_time: int = 1,
              time_indices: Union[IntVec, None] = None,
              area_dict: Dict[dev.Area, "pg.Area"] = None) -> Dict[str, "pg.Bus"]:
    """
    Convert the buses to GSLV buses
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param use_time_series: compile the time series from GridCal? otherwise, just the snapshot
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param area_dict: Area object translation dictionary
    :return: bus dictionary buses[uuid] -> Bus
    """

    if time_indices is not None:
        assert (len(time_indices) == n_time)

    if area_dict is None:
        area_dict = {elm: k for k, elm in enumerate(circuit.areas)}

    bus_dict: Dict[str, "pg.Bus"] = dict()

    for i, bus in enumerate(circuit.buses):
        elm = convert_bus(bus=bus, n_time=n_time,
                          area_dict=area_dict,
                          use_time_series=use_time_series,
                          time_indices=time_indices)

        gslv_grid.add_bus(elm)
        bus_dict[bus.idtag] = elm

    return bus_dict


def convert_load(k: int, elm: dev.Load, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                 use_time_series: bool, time_indices: IntVec | None = None,
                 opf_results: OptimalPowerFlowResults | None = None) -> "pg.Load":
    """

    :param k:
    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :param opf_results:
    :return:
    """

    """
    TypeError: __init__(): incompatible constructor arguments. The following argument types are supported:
    pygslv.Load(
    nt: int, 
    name: str = 'Load', 
    idtag: str = '', 
    code: str = '', 
    G: float = 0.0, 
    B: float = 0.0, 
    Ir: float = 0.0,
    Ii: float = 0.0, 
    P: float = 0.0, 
    Q: float = 0.0, 
    Cost: float = 1200.0, 
    active: bool = True, 
    mttf: float = 0.0, 
    mttr: float = 0.0, 
    capex: float = 0.0, 
    opex: float = 0.0, 
    build_status: pygslv.BuildStatus = <BuildStatus.Commissioned: 0>)
       
    Invoked with: kwargs: idtag='1d19d20c90924be7928e0fbb61aa699f', code='2_1', name='2_1', calc_node=BUS 2, nt=1, P=21.7, Q=12.7, build_status=Commissioned

    """
    build_status_dict = {
        BuildStatus.Planned: pg.BuildStatus.Planned,
        BuildStatus.Commissioned: pg.BuildStatus.Commissioned,
        BuildStatus.Candidate: pg.BuildStatus.Candidate,
        BuildStatus.Decommissioned: pg.BuildStatus.Decommissioned,
        BuildStatus.PlannedDecommission: pg.BuildStatus.PlannedDecommission,
    }

    load = pg.Load(
        nt=n_time,
        name=elm.name,
        idtag=elm.idtag,
        code=str(elm.code),
        G=elm.G,
        B=elm.B,
        Ir=elm.Ir,
        Ii=elm.Ii,
        P=elm.P if opf_results is None else elm.P - opf_results.load_shedding[k],
        Q=elm.Q,
        Cost=elm.Cost,
        active=elm.active,
        mttf=elm.mttf,
        mttr=elm.mttr,
        capex=elm.capex,
        opex=elm.opex,
        build_status=build_status_dict[elm.build_status],
    )

    load.bus = bus_dict[elm.bus.idtag]

    if use_time_series:
        load.active = (elm.active_prof.astype(BINT)
                       if time_indices is None
                       else elm.active_prof.astype(BINT)[time_indices])

        if opf_results is None:
            P = elm.P_prof.toarray()
        else:
            P = elm.P_prof.toarray() - opf_results.load_shedding[:, k]

        load.P = P if time_indices is None else P[time_indices]
        load.Q = elm.Q_prof.toarray() if time_indices is None else elm.Q_prof.toarray()[time_indices]
        load.cost_1 = elm.Cost_prof.toarray() if time_indices is None else elm.Cost_prof.toarray()[time_indices]
    else:
        load.set_active_val(int(elm.active))
        load.setAllCost1(elm.Cost)

    return load


def add_loads(circuit: MultiCircuit,
              gslv_grid: "pg.MultiCircuit",
              bus_dict: Dict[str, "pg.Bus"],
              use_time_series: bool,
              n_time=1,
              time_indices: IntVec | None = None,
              opf_results: OptimalPowerFlowResults | None = None,
              build_status_dict: Dict[BuildStatus, "pg.BuildStatus"] | None = None,):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param use_time_series: compile the time series from GridCal? otherwise just the snapshot
    :param n_time: number of time steps
    :param time_indices:
    :param opf_results:
    :param build_status_dict:
    :return:
    """
    devices = circuit.get_loads()
    for k, elm in enumerate(devices):
        load = convert_load(k=k, elm=elm, bus_dict=bus_dict,
                            n_time=n_time, use_time_series=use_time_series,
                            time_indices=time_indices, opf_results=opf_results)
        gslv_grid.add_load(load)


def convert_static_generator(elm: dev.StaticGenerator, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                             use_time_series: bool, time_indices: IntVec | None = None, ) -> "pg.StaticGenerator":
    pe_inj = pg.StaticGenerator(
        idtag=elm.idtag,
        code=str(elm.code),
        name=elm.name,
        calc_node=bus_dict[elm.bus.idtag],
        nt=n_time,
        P=elm.P,
        Q=elm.Q,
        build_status=elm.build_status,
    )

    if use_time_series:
        pe_inj.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
            time_indices]
        pe_inj.P = elm.P_prof.toarray() if time_indices is None else elm.P_prof.toarray()[time_indices]
        pe_inj.Q = elm.Q_prof.toarray() if time_indices is None else elm.Q_prof.toarray()[time_indices]
        pe_inj.cost_1 = elm.Cost_prof.toarray() if time_indices is None else elm.Cost_prof.toarray()[time_indices]
    else:
        pe_inj.active = np.ones(n_time, dtype=BINT) * int(elm.active)
        pe_inj.setAllCost1(elm.Cost)

    return pe_inj


def add_static_generators(circuit: MultiCircuit, gslv_grid: "pg.MultiCircuit",
                          bus_dict: Dict[str, "pg.Bus"],
                          time_series: bool,
                          n_time=1,
                          time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """
    devices = circuit.get_static_generators()
    for k, elm in enumerate(devices):
        pe_inj = convert_static_generator(elm=elm, bus_dict=bus_dict, n_time=n_time,
                                          use_time_series=time_series, time_indices=time_indices)
        gslv_grid.add_static_generator(pe_inj)


def convert_shunt(elm: dev.Shunt, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                  use_time_series: bool, time_indices: IntVec | None = None, ) -> "pg.Shunt":
    sh = pg.Shunt(
        idtag=elm.idtag,
        code=str(elm.code),
        name=elm.name,
        calc_node=bus_dict[elm.bus.idtag],
        nt=n_time,
        G=elm.G,
        B=elm.B,
        build_status=elm.build_status,
    )

    if use_time_series:
        sh.active = (elm.active_prof.astype(BINT)
                     if time_indices is None
                     else elm.active_prof.astype(BINT)[time_indices])
        sh.G = elm.G_prof.toarray() if time_indices is None else elm.G_prof.toarray()[time_indices]
        sh.B = elm.B_prof.toarray() if time_indices is None else elm.B_prof.toarray()[time_indices]
    else:
        sh.active = np.ones(n_time, dtype=BINT) * int(elm.active)

    return sh


def add_shunts(circuit: MultiCircuit,
               gslv_grid: "pg.MultiCircuit",
               bus_dict: Dict[str, "pg.Bus"],
               time_series: bool,
               n_time=1,
               time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """
    devices = circuit.get_shunts()
    for k, elm in enumerate(devices):
        sh = convert_shunt(elm=elm, bus_dict=bus_dict, n_time=n_time,
                           use_time_series=time_series, time_indices=time_indices)
        gslv_grid.add_shunt(sh)


def convert_generator(k: int, elm: dev.Generator, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                      use_time_series: bool, time_indices: IntVec | None = None,
                      opf_results: OptimalPowerFlowResults | None = None) -> "pg.Generator":
    """

    :param k:
    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :param opf_results:
    :return:
    """
    gen = pg.Generator(idtag=elm.idtag,
                       name=elm.name,
                       calc_node=bus_dict[elm.bus.idtag],
                       nt=n_time,
                       P=elm.P,
                       Vset=elm.Vset,
                       Pmin=elm.Pmin,
                       Pmax=elm.Pmax,
                       Qmin=elm.Qmin,
                       Qmax=elm.Qmax,
                       Snom=elm.Snom,
                       controllable_default=BINT(elm.is_controlled),
                       dispatchable_default=BINT(elm.enabled_dispatch),
                       is_controlled=elm.is_controlled,
                       q_points=elm.q_curve.get_data())

    if use_time_series:

        gen.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
            time_indices]

        if opf_results is None:
            P = elm.P_prof.toarray()
        else:
            P = opf_results.generator_power[:, k] - opf_results.generator_shedding[:, k]

        gen.P = P if time_indices is None else P[time_indices]

        gen.Vset = elm.Vset_prof.toarray() if time_indices is None else elm.Vset_prof.toarray()[time_indices]
        gen.cost_0 = elm.Cost0_prof.toarray() if time_indices is None else elm.Cost0_prof.toarray()[time_indices]
        gen.cost_1 = elm.Cost_prof.toarray() if time_indices is None else elm.Cost_prof.toarray()[time_indices]
        gen.cost_2 = elm.Cost2_prof.toarray() if time_indices is None else elm.Cost2_prof.toarray()[time_indices]
    else:
        gen.active = np.ones(n_time, dtype=BINT) * int(elm.active)

        if opf_results is None:
            gen.P = np.full(n_time, elm.P, dtype=float)
        else:
            gen.P = np.full(n_time, opf_results.generator_power[k] - opf_results.generator_shedding[k], dtype=float)

        gen.Vset = np.ones(n_time, dtype=float) * elm.Vset
        gen.setAllCost0(elm.Cost0)
        gen.setAllCost1(elm.Cost)
        gen.setAllCost2(elm.Cost2)

    return gen


def add_generators(circuit: MultiCircuit,
                   gslv_grid: "pg.MultiCircuit",
                   bus_dict: Dict[str, "pg.Bus"],
                   time_series: bool,
                   n_time=1,
                   time_indices: Union[IntVec, None] = None,
                   opf_results: Union[None, OptimalPowerFlowResults] = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param opf_results: OptimalPowerFlowResults (optional)
    """
    devices = circuit.get_generators()

    for k, elm in enumerate(devices):
        gen = convert_generator(k=k, elm=elm, bus_dict=bus_dict,
                                n_time=n_time, use_time_series=time_series,
                                time_indices=time_indices, opf_results=opf_results)

        gslv_grid.add_generator(gen)


def convert_battery(k: int, elm: dev.Battery, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                    use_time_series: bool, time_indices: IntVec | None = None,
                    opf_results: OptimalPowerFlowResults | None = None) -> "pg.Battery":
    """

    :param k:
    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :param opf_results:
    :return:
    """
    gen = pg.Battery(idtag=elm.idtag,
                     name=elm.name,
                     calc_node=bus_dict[elm.bus.idtag],
                     nt=n_time,
                     nominal_energy=elm.Enom,
                     P=elm.P,
                     Vset=elm.Vset,
                     soc_max=elm.max_soc,
                     soc_min=elm.min_soc,
                     Qmin=elm.Qmin,
                     Qmax=elm.Qmax,
                     Pmin=elm.Pmin,
                     Pmax=elm.Pmax,
                     Snom=elm.Snom,
                     charge_efficiency=elm.charge_efficiency,
                     discharge_efficiency=elm.discharge_efficiency,
                     is_controlled=elm.is_controlled, )

    if use_time_series:
        gen.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
            time_indices]

        if opf_results is None:
            P = elm.P_prof.toarray()
        else:
            P = opf_results.generator_power[:, k] - opf_results.generator_shedding[:, k]

        gen.P = P if time_indices is None else P[time_indices]

        # gen.P = elm.P_prof if time_indices is None else elm.P_prof[time_indices]
        gen.Vset = elm.Vset_prof.toarray() if time_indices is None else elm.Vset_prof.toarray()[time_indices]
        gen.cost_0 = elm.Cost0_prof.toarray() if time_indices is None else elm.Cost0_prof.toarray()[time_indices]
        gen.cost_1 = elm.Cost_prof.toarray() if time_indices is None else elm.Cost_prof.toarray()[time_indices]
        gen.cost_2 = elm.Cost2_prof.toarray() if time_indices is None else elm.Cost2_prof.toarray()[time_indices]
    else:
        gen.active = np.ones(n_time, dtype=BINT) * int(elm.active)

        if opf_results is None:
            gen.P = np.full(n_time, elm.P, dtype=float)
        else:
            gen.P = np.full(n_time, opf_results.battery_power[k], dtype=float)

        gen.Vset = np.ones(n_time, dtype=float) * elm.Vset
        gen.setAllCost0(elm.Cost0)
        gen.setAllCost1(elm.Cost)
        gen.setAllCost2(elm.Cost2)

    return gen


def add_battery_data(circuit: MultiCircuit,
                     gslv_grid: "pg.MultiCircuit",
                     bus_dict: Dict[str, "pg.Bus"],
                     time_series: bool,
                     n_time: int = 1,
                     time_indices: Union[IntVec, None] = None,
                     opf_results: Union[None, OptimalPowerFlowResults] = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param opf_results: OptimelPowerFlowResults (optional)
    """
    devices = circuit.get_batteries()

    for k, elm in enumerate(devices):
        batt = convert_battery(k=k, elm=elm, bus_dict=bus_dict,
                               n_time=n_time, use_time_series=time_series,
                               time_indices=time_indices, opf_results=opf_results)

        gslv_grid.add_battery(batt)


def convert_line(elm: dev.Line, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                 use_time_series: bool, time_indices: IntVec | None = None, ) -> "pg.Line":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :return:
    """
    lne = pg.Line(idtag=elm.idtag,
                  code=str(elm.code),
                  name=elm.name,
                  calc_node_from=bus_dict[elm.bus_from.idtag],
                  calc_node_to=bus_dict[elm.bus_to.idtag],
                  nt=n_time,
                  length=elm.length,
                  rate=elm.rate,
                  active_default=elm.active,
                  r=elm.R,
                  x=elm.X,
                  b=elm.B,
                  monitor_loading_default=elm.monitor_loading,
                  monitor_contingency_default=elm.contingency_enabled)

    if use_time_series:
        lne.active = (elm.active_prof.astype(BINT)
                      if time_indices is None
                      else elm.active_prof.astype(BINT)[time_indices])

        lne.rates = (elm.rate_prof.toarray()
                     if time_indices is None
                     else elm.rate_prof.toarray()[time_indices])

        contingency_rates = elm.rate_prof.toarray() * elm.contingency_factor

        lne.contingency_rates = (contingency_rates
                                 if time_indices is None
                                 else contingency_rates[time_indices])

        lne.overload_cost = (elm.Cost_prof.toarray()
                             if time_indices is None
                             else elm.Cost_prof.toarray()[time_indices])
    else:
        lne.setAllOverloadCost(elm.Cost)

    return lne


def add_line(circuit: MultiCircuit,
             gslv_grid: "pg.MultiCircuit",
             bus_dict: Dict[str, "pg.Bus"],
             time_series: bool,
             n_time: int = 1,
             time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        lne = convert_line(elm=elm, bus_dict=bus_dict, n_time=n_time,
                           use_time_series=time_series, time_indices=time_indices)
        gslv_grid.add_line(lne)


def convert_transformer(elm: dev.Transformer2W, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                        use_time_series: bool, time_indices: IntVec | None,
                        override_controls: bool) -> "pg.Transformer2W":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :param override_controls:
    :return:
    """
    tr2 = pg.Transformer2W(idtag=elm.idtag,
                           code=str(elm.code),
                           name=elm.name,
                           calc_node_from=bus_dict[elm.bus_from.idtag],
                           calc_node_to=bus_dict[elm.bus_to.idtag],
                           nt=n_time,
                           Vhigh=elm.HV,
                           Vlow=elm.LV,
                           rate=elm.rate,
                           active_default=elm.active,
                           r=elm.R,
                           x=elm.X,
                           g=elm.G,
                           b=elm.B,
                           monitor_loading_default=elm.monitor_loading,
                           monitor_contingency_default=elm.contingency_enabled,
                           tap=elm.tap_module,
                           phase=elm.tap_phase)

    tr2.tap_phase_min = elm.tap_phase_min
    tr2.tap_phase_max = elm.tap_phase_max
    tr2.tap_module_min = elm.tap_module_min
    tr2.tap_module_max = elm.tap_module_max

    if use_time_series:
        contingency_rates = elm.rate_prof.toarray() * elm.contingency_factor
        active_prof = elm.active_prof.astype(BINT)

        tr2.active = active_prof if time_indices is None else active_prof[time_indices]
        tr2.rates = elm.rate_prof.toarray() if time_indices is None else elm.rate_prof.toarray()[time_indices]
        tr2.contingency_rates = contingency_rates if time_indices is None else contingency_rates[time_indices]
        tr2.tap = elm.tap_module_prof.toarray() if time_indices is None else elm.tap_module_prof.toarray()[
            time_indices]
        tr2.phase = elm.tap_phase_prof.toarray() if time_indices is None else elm.tap_phase_prof.toarray()[
            time_indices]
        tr2.overload_cost = elm.Cost_prof.toarray()
    else:
        tr2.setAllOverloadCost(elm.Cost)

    # ctrl_dict = {
    #     TransformerControlType.fixed: pg.BranchControlModes.Fixed,
    #     TransformerControlType.Pf: pg.BranchControlModes.BranchPt,
    #     TransformerControlType.Qt: pg.BranchControlModes.BranchQt,
    #     TransformerControlType.PtQt: pg.BranchControlModes.BranchPt,
    #     TransformerControlType.V: pg.BranchControlModes.BranchVt,
    #     TransformerControlType.PtV: pg.BranchControlModes.BranchPt,
    # }

    # control vars
    if override_controls:
        tr2.tap_module_control_mode = pg.TapModuleControl.fixed
        tr2.tap_phase_control_mode = pg.TapPhaseControl.fixed
    else:
        # tr2.setAllControlMode(ctrl_dict[elm.control_mode])
        pass

    return tr2


def add_transformers(circuit: MultiCircuit,
                     gslv_grid: "pg.MultiCircuit",
                     bus_dict: Dict[str, "pg.Bus"],
                     time_series: bool,
                     n_time: int = 1,
                     time_indices: Union[IntVec, None] = None,
                     override_controls=False):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param override_controls: If true the controls are set to Fix
    """

    for i, elm in enumerate(circuit.transformers2w):
        tr2 = convert_transformer(elm=elm, bus_dict=bus_dict, n_time=n_time,
                                  use_time_series=time_series, time_indices=time_indices,
                                  override_controls=override_controls)
        gslv_grid.add_transformer(tr2)


def convert_transformer3w(elm: dev.Transformer3W, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                          use_time_series: bool, time_indices: IntVec | None,
                          override_controls: bool) -> "pg.Transformer3W":
    # ctrl_dict = {
    #     TransformerControlType.fixed: pg.BranchControlModes.Fixed,
    #     TransformerControlType.Pf: pg.BranchControlModes.BranchPt,
    #     TransformerControlType.Qt: pg.BranchControlModes.BranchQt,
    #     TransformerControlType.PtQt: pg.BranchControlModes.BranchPt,
    #     TransformerControlType.V: pg.BranchControlModes.BranchVt,
    #     TransformerControlType.PtV: pg.BranchControlModes.BranchPt,
    # }

    tr3 = pg.Transformer3W(idtag=elm.idtag,
                           code=str(elm.code),
                           name=elm.name,
                           nt=n_time,
                           active=elm.active,
                           bus1=bus_dict[elm.bus1.idtag] if elm.bus1 else None,
                           bus2=bus_dict[elm.bus2.idtag] if elm.bus2 else None,
                           bus3=bus_dict[elm.bus3.idtag] if elm.bus3 else None,
                           V1=elm.V1,
                           V2=elm.V2,
                           V3=elm.V3,
                           r12=elm.r12, r23=elm.r23, r31=elm.r31,
                           x12=elm.x12, x23=elm.x23, x31=elm.x31,
                           rate12=elm.rate1, rate23=elm.rate2, rate31=elm.rate3)

    # this is because the central node is in the buses list already from GridCal
    tr3.central_node = bus_dict[elm.bus0.idtag]

    if use_time_series:
        pass
    else:
        pass

    return tr3


def add_transformers3w(circuit: MultiCircuit,
                       gslv_grid: "pg.MultiCircuit",
                       bus_dict: Dict[str, "pg.Bus"],
                       time_series: bool,
                       n_time=1,
                       time_indices: Union[IntVec, None] = None,
                       override_controls=False):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param override_controls: If true the controls are set to Fix
    """
    for i, elm in enumerate(circuit.transformers3w):
        tr3 = convert_transformer3w(elm=elm, bus_dict=bus_dict, n_time=n_time,
                                    use_time_series=time_series, time_indices=time_indices,
                                    override_controls=override_controls)

        # because the central bus was added already, do not add it here
        gslv_grid.add_transformer_3w(tr3, add_central_node=False)


def convert_vsc(elm: dev.VSC, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                use_time_series: bool, time_indices: IntVec | None) -> "pg.Vsc":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :return:
    """
    vsc = pg.Vsc(idtag=elm.idtag,
                 code=str(elm.code),
                 name=elm.name,
                 calc_node_from=bus_dict[elm.bus_from.idtag],
                 calc_node_to=bus_dict[elm.bus_to.idtag],
                 nt=n_time,
                 active=elm.active, )

    vsc.alpha1 = elm.alpha1
    vsc.alpha2 = elm.alpha2
    vsc.alpha3 = elm.alpha3

    vsc.setAllMonitorloading(elm.monitor_loading)
    vsc.setAllContingencyenabled(elm.contingency_enabled)

    if use_time_series:
        vsc.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
            time_indices]
        vsc.rates = elm.rate_prof.toarray() if time_indices is None else elm.rate_prof.toarray()[time_indices]
        contingency_rates = elm.rate_prof.toarray() * elm.contingency_factor
        vsc.contingency_rates = contingency_rates if time_indices is None else contingency_rates[time_indices]
        vsc.overload_cost = elm.Cost_prof.toarray()
    else:
        vsc.setAllRates(elm.rate)
        vsc.setAllOverloadCost(elm.Cost)

    return vsc


def add_vscs(circuit: MultiCircuit,
             gslv_grid: "pg.MultiCircuit",
             bus_dict: Dict[str, "pg.Bus"],
             time_series: bool,
             n_time: int = 1,
             time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """
    for i, elm in enumerate(circuit.vsc_devices):
        vsc = convert_vsc(elm=elm, bus_dict=bus_dict, n_time=n_time,
                          use_time_series=time_series, time_indices=time_indices)
        gslv_grid.add_vsc(vsc)


def convert_dc_line(elm: dev.DcLine, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                    use_time_series: bool, time_indices: IntVec | None) -> "pg.DcLine":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :return:
    """
    lne = pg.DcLine(idtag=elm.idtag,
                    name=elm.name,
                    calc_node_from=bus_dict[elm.bus_from.idtag],
                    calc_node_to=bus_dict[elm.bus_to.idtag],
                    nt=n_time,
                    length=elm.length,
                    rate=elm.rate,
                    active_default=elm.active,
                    r=elm.R,
                    monitor_loading_default=elm.monitor_loading,
                    monitor_contingency_default=elm.contingency_enabled
                    )

    if use_time_series:
        lne.active = (elm.active_prof.astype(BINT)
                      if time_indices is None
                      else elm.active_prof.astype(BINT)[time_indices])

        lne.rates = elm.rate_prof.toarray() if time_indices is None else elm.rate_prof.toarray()[time_indices]

        contingency_rates = elm.rate_prof.toarray() * elm.contingency_factor
        lne.contingency_rates = contingency_rates if time_indices is None else contingency_rates[time_indices]
        lne.overload_cost = elm.Cost_prof.toarray()
    else:
        lne.setAllOverloadCost(elm.Cost)

    return lne


def add_dc_lines(circuit: MultiCircuit,
                 gslv_grid: "pg.MultiCircuit",
                 bus_dict: Dict[str, "pg.Bus"],
                 time_series: bool,
                 n_time: int = 1,
                 time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """
    # Compile the lines
    for i, elm in enumerate(circuit.dc_lines):
        lne = convert_dc_line(elm=elm, bus_dict=bus_dict, n_time=n_time,
                              use_time_series=time_series, time_indices=time_indices)
        gslv_grid.add_dc_line(lne)


def convert_hvdc_line(elm: dev.HvdcLine, bus_dict: Dict[str, "pg.Bus"], n_time: int,
                      use_time_series: bool, time_indices: IntVec | None) -> "pg.HvdcLine":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :return:
    """
    cmode_dict = {HvdcControlType.type_0_free: pg.HvdcControlType.HvdcControlAngleDroop,
                  HvdcControlType.type_1_Pset: pg.HvdcControlType.HvdcControlPfix}

    hvdc = pg.HvdcLine(idtag=elm.idtag,
                       code=str(elm.code),
                       name=elm.name,
                       calc_node_from=bus_dict[elm.bus_from.idtag],
                       calc_node_to=bus_dict[elm.bus_to.idtag],
                       cn_from=None,
                       cn_to=None,
                       nt=n_time,
                       active_default=int(elm.active),
                       rate=elm.rate,
                       contingency_rate=elm.rate * elm.contingency_factor,
                       monitor_loading_default=1,
                       monitor_contingency_default=1,
                       P=elm.Pset,
                       Vf=elm.Vset_f,
                       Vt=elm.Vset_t,
                       r=elm.r,
                       angle_droop=elm.angle_droop,
                       length=elm.length,
                       min_firing_angle_f=elm.min_firing_angle_f,
                       max_firing_angle_f=elm.max_firing_angle_f,
                       min_firing_angle_t=elm.min_firing_angle_t,
                       max_firing_angle_t=elm.max_firing_angle_t,
                       control_mode=cmode_dict[elm.control_mode])

    # hvdc.monitor_loading = elm.monitor_loading
    # hvdc.contingency_enabled = elm.contingency_enabled

    if use_time_series:
        hvdc.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
            time_indices]
        hvdc.rates = elm.rate_prof.toarray() if time_indices is None else elm.rate_prof.toarray()[time_indices]
        hvdc.Vf = elm.Vset_f_prof.toarray() if time_indices is None else elm.Vset_f_prof.toarray()[time_indices]
        hvdc.Vt = elm.Vset_t_prof.toarray() if time_indices is None else elm.Vset_t_prof.toarray()[time_indices]

        contingency_rates = elm.rate_prof.toarray() * elm.contingency_factor
        hvdc.contingency_rates = contingency_rates if time_indices is None else contingency_rates[time_indices]

        hvdc.angle_droop = (elm.angle_droop_prof.toarray() if time_indices is None else
                            elm.angle_droop_prof.toarray()[time_indices])
        hvdc.overload_cost = elm.Cost_prof.toarray()
    else:
        hvdc.contingency_rates = elm.rate * elm.contingency_factor
        hvdc.angle_droop = elm.angle_droop
        hvdc.setAllOverloadCost(elm.Cost)
        hvdc.setAllControlMode(cmode_dict[elm.control_mode])

    return hvdc


def add_hvdcs(circuit: MultiCircuit,
              gslv_grid: "pg.MultiCircuit",
              bus_dict: Dict[str, "pg.Bus"],
              time_series: bool,
              n_time=1,
              time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """

    for i, elm in enumerate(circuit.hvdc_lines):
        hvdc = convert_hvdc_line(elm=elm, bus_dict=bus_dict, n_time=n_time,
                                 use_time_series=time_series, time_indices=time_indices)
        gslv_grid.add_hvdc_line(hvdc)


def to_gslv(circuit: MultiCircuit,
            use_time_series: bool,
            time_indices: Union[IntVec, None] = None,
            override_branch_controls=False,
            opf_results: Union[None, OptimalPowerFlowResults] = None):
    """
    Convert GridCal circuit to GSLV
    :param circuit: MultiCircuit
    :param use_time_series: compile the time series from GridCal? otherwise just the snapshot
    :param time_indices: Array of time indices
    :param override_branch_controls: If true the branch controls are set to Fix
    :param opf_results:
    :return: pg.MultiCircuit instance
    """

    if time_indices is None:
        n_time = circuit.get_time_number() if use_time_series else 1
        if n_time == 0:
            n_time = 1
    else:
        n_time = len(time_indices)

    pg_grid = pg.MultiCircuit(name=circuit.name, nt=n_time)
    # pg_grid.idtag = circuit.idtag

    build_status_dict = {
        BuildStatus.Planned: pg.BuildStatus.Planned,
        BuildStatus.Commissioned: pg.BuildStatus.Commissioned,
        BuildStatus.Candidate: pg.BuildStatus.Candidate,
        BuildStatus.Decommissioned: pg.BuildStatus.Decommissioned,
        BuildStatus.PlannedDecommission: pg.BuildStatus.PlannedDecommission,
    }

    area_dict = add_areas(circuit=circuit, gslv_grid=pg_grid)
    zone_dict = add_zones(circuit=circuit, gslv_grid=pg_grid)

    con_groups_dict = add_contingency_groups(circuit=circuit, gslv_grid=pg_grid)

    add_contingencies(circuit=circuit, gslv_grid=pg_grid, n_time=n_time, groups_dict=con_groups_dict)

    inv_groups_dict = add_investment_groups(circuit=circuit, gslv_grid=pg_grid)

    add_investments(circuit=circuit, gslv_grid=pg_grid, groups_dict=inv_groups_dict)

    bus_dict = add_buses(
        circuit=circuit,
        gslv_grid=pg_grid,
        use_time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        area_dict=area_dict
    )

    add_loads(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        use_time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        build_status_dict=build_status_dict
    )

    add_static_generators(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices

    )

    add_shunts(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices
    )

    add_generators(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        opf_results=opf_results
    )

    add_battery_data(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        opf_results=opf_results
    )

    add_line(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices
    )

    add_transformers(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        override_controls=override_branch_controls
    )

    add_transformers3w(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        override_controls=override_branch_controls
    )

    add_vscs(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices
    )

    add_dc_lines(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices
    )

    add_hvdcs(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices
    )

    # pg.FileHandler().save(npaCircuit, circuit.name + "_circuit.GSLV")

    return pg_grid, (bus_dict, area_dict, zone_dict)


class FakeAdmittances:
    """
    Fake admittances class needed to make the translation
    """

    def __init__(self) -> None:
        self.Ybus = None
        self.Yf = None
        self.Yt = None


def get_snapshots_from_gslv(circuit: MultiCircuit, override_branch_controls=False) -> List[NumericalCircuit]:
    """

    :param circuit:
    :param override_branch_controls:
    :return:
    """

    gslv_grid, (bus_dict, area_dict, zone_dict) = to_gslv(circuit,
                                                          use_time_series=False,
                                                          override_branch_controls=override_branch_controls)

    logger = pg.Logger()
    npa_data_lst = pg.compile(gslv_grid, logger, t=0).splitIntoIslands()

    data_lst = list()

    for npa_data in npa_data_lst:
        data = NumericalCircuit(nbus=0,
                                nbr=0,
                                nhvdc=0,
                                nvsc=0,
                                nload=0,
                                ngen=0,
                                nbatt=0,
                                nshunt=0,
                                nfluidnode=0,
                                nfluidturbine=0,
                                nfluidpump=0,
                                nfluidp2x=0,
                                nfluidpath=0,
                                sbase=0,
                                t_idx=0)

        conn = npa_data.getConnectivity()
        inj = npa_data.getInjections()
        tpes = npa_data.getSimulationIndices(inj.S0)
        adm = npa_data.getAdmittances(conn)
        lin = npa_data.getLinearMatrices(conn)
        series_adm = npa_data.getSeriesAdmittances(conn)
        fd_adm = npa_data.getFastDecoupledAdmittances(conn, tpes)
        qlim = npa_data.getQLimits()

        data.Vbus_ = npa_data.Vbus.reshape(-1, 1)
        data.Sbus_ = inj.S0.reshape(-1, 1)
        data.Ibus_ = inj.I0.reshape(-1, 1)
        data.passive_branch_data.names = np.array(npa_data.passive_branch_data.names)
        data.passive_branch_data.virtual_tap_f = npa_data.passive_branch_data.vtap_f
        data.passive_branch_data.virtual_tap_t = npa_data.passive_branch_data.vtap_t
        data.passive_branch_data.original_idx = npa_data.passive_branch_data.original_indices

        data.bus_data.names = np.array(npa_data.bus_data.names)
        data.bus_data.original_idx = npa_data.bus_data.original_indices

        data.admittances_ = FakeAdmittances()
        data.admittances_.Ybus = adm.Ybus
        data.admittances_.Yf = adm.Yf
        data.admittances_.Yt = adm.Yt

        data.Bbus_ = lin.Bbus
        data.Bf_ = lin.Bf

        data.Yseries_ = series_adm.Yseries
        data.Yshunt_ = series_adm.Yshunt

        data.B1_ = fd_adm.B1
        data.B2_ = fd_adm.B2

        data.Cf_ = conn.Cf
        data.Ct_ = conn.Ct

        data.bus_data.bus_types = tpes.types
        data.pq_ = tpes.pq
        data.pv_ = tpes.pv
        data.vd_ = tpes.vd
        data.pqpv_ = tpes.no_slack

        data.Qmax_bus_ = qlim.qmax_bus
        data.Qmin_bus_ = qlim.qmin_bus

        control_indices = npa_data.getSimulationIndices(Sbus=data.Sbus_[:, 0])

        data.k_pf_tau = control_indices.k_pf_tau
        data.k_qf_m = control_indices.k_qf_m
        data.k_zero_beq = control_indices.k_qf_beq
        data.k_vf_beq = control_indices.k_vf_beq
        data.k_vt_m = control_indices.k_v_m
        data.k_qt_m = control_indices.k_qt_m
        data.k_pf_dp = control_indices.k_pf_dp
        data.i_vsc = control_indices.i_vsc
        data.i_vf_beq = control_indices.i_vf_beq
        data.i_vt_m = control_indices.i_vt_m

        data_lst.append(data)

    return data_lst


def get_gslv_pf_options(opt: PowerFlowOptions) -> "pg.PowerFlowOptions":
    """
    Translate GridCal power flow options to GSLV power flow options
    :param opt:
    :return:
    """
    solver_dict = {SolverType.NR: pg.SolverType.NR,
                   SolverType.DC: pg.SolverType.DC,
                   SolverType.HELM: pg.SolverType.HELM,
                   SolverType.IWAMOTO: pg.SolverType.IWAMOTO,
                   SolverType.LM: pg.SolverType.LM,
                   SolverType.LACPF: pg.SolverType.LACPF,
                   SolverType.FASTDECOUPLED: pg.SolverType.FD
                   }

    if opt.solver_type in solver_dict.keys():
        solver_type = solver_dict[opt.solver_type]
    else:
        solver_type = pg.SolverType.NR

    """
    solver_type: GSLVpa.SolverType = <SolverType.NR: 0>, 
    retry_with_other_methods: bool = True, 
    verbose: bool = False, 
    initialize_with_existing_solution: bool = False, 
    tolerance: float = 1e-06, 
    max_iter: int = 15, 
    control_q_mode: GSLVpa.ReactivePowerControlMode = <ReactivePowerControlMode.NoControl: 0>, 
    tap_control_mode: GSLVpa.TapsControlMode = <TapsControlMode.NoControl: 0>, 
    distributed_slack: bool = False, 
    ignore_single_node_islands: bool = False, 
    correction_parameter: float = 0.5, 
    mu0: float = 1.0
    """

    return pg.PowerFlowOptions(solver_type=solver_type,
                               retry_with_other_methods=opt.retry_with_other_methods,
                               verbose=opt.verbose,
                               initialize_with_existing_solution=opt.use_stored_guess,
                               tolerance=opt.tolerance,
                               max_iter=opt.max_iter,
                               control_q_mode=opt.control_Q,
                               distributed_slack=opt.distributed_slack,
                               correction_parameter=0.5,
                               mu0=opt.trust_radius)


def gslv_pf(circuit: MultiCircuit,
            pf_opt: PowerFlowOptions,
            time_series: bool = False,
            time_indices: Union[IntVec, None] = None,
            opf_results: Union[None, OptimalPowerFlowResults] = None) -> "pg.PowerFlowResults":
    """
    GSLV power flow
    :param circuit: MultiCircuit instance
    :param pf_opt: Power Flow Options
    :param time_series: Compile with GridCal time series?
    :param time_indices: Array of time indices
    :param opf_results: Instance of
    :return: GSLV Power flow results object
    """
    override_branch_controls = not (pf_opt.control_taps_modules and pf_opt.control_taps_phase)

    gslv_grid, _ = to_gslv(circuit,
                           use_time_series=time_series,
                           time_indices=None,
                           override_branch_controls=override_branch_controls,
                           opf_results=opf_results)

    pf_options = get_gslv_pf_options(pf_opt)

    if time_series:
        # it is already sliced to the relevant time indices
        if time_indices is None:
            time_indices = [i for i in range(circuit.get_time_number())]
        else:
            time_indices = list(time_indices)
        n_threads = 0  # max threads
    else:
        time_indices = [0]
        n_threads = 1

    pf_res = pg.multi_island_pf(grid=gslv_grid,
                                options=pf_options,
                                time_indices=time_indices,
                                n_threads=n_threads)

    return pf_res


def translate_gslv_pf_results(grid: MultiCircuit, res: "pg.PowerFlowResults") -> PowerFlowResults:
    """
    Translate the GSLV Power Analytics results back to GridCal
    :param grid: MultiCircuit instance
    :param res: GSLV's PowerFlowResults instance
    :return: PowerFlowResults instance
    """
    results = PowerFlowResults(n=grid.get_bus_number(),
                               m=grid.get_branch_number_wo_hvdc(),
                               n_hvdc=grid.get_hvdc_number(),
                               n_vsc=grid.get_vsc_number(),
                               n_gen=grid.get_generators_number(),
                               n_batt=grid.get_batteries_number(),
                               n_sh=grid.get_shunt_like_device_number(),
                               bus_names=res.bus_names,
                               branch_names=res.branch_names,
                               hvdc_names=res.hvdc_names,
                               vsc_names=grid.get_vsc_names(),
                               gen_names=grid.get_generator_names(),
                               batt_names=grid.get_battery_names(),
                               sh_names=grid.get_shunt_like_devices_names(),
                               bus_types=res.bus_types)

    results.voltage = res.voltage[0, :]
    results.Sbus = res.Scalc[0, :]
    results.Sf = res.Sf[0, :]
    results.St = res.St[0, :]
    results.loading = res.Loading[0, :]
    results.losses = res.Losses[0, :]
    # results.Vbranch = res.Vbranch[0, :]
    # results.If = res.If[0, :]
    # results.It = res.It[0, :]
    results.Beq = res.Beq[0, :]
    results.m = res.tap_module[0, :]
    results.tap_angle = res.tap_angle[0, :]
    results.F = res.F
    results.T = res.T
    results.hvdc_F = res.hvdc_F
    results.hvdc_T = res.hvdc_T
    results.Pf_hvdc = res.hvdc_Pf[0, :]
    results.Pt_hvdc = res.hvdc_Pt[0, :]
    results.loading_hvdc = res.hvdc_loading[0, :]
    results.losses_hvdc = res.hvdc_losses[0, :]
    results.bus_area_indices = grid.get_bus_area_indices()
    # results.area_names = [a.name for a in grid.areas]
    # results.bus_types = convert_bus_types(res.bus_types[0])  # this is a list of lists

    for rep in res.stats[0]:
        report = ConvergenceReport()
        for i in range(len(rep.converged)):
            report.add(method=rep.solver[i].name,
                       converged=rep.converged[i],
                       error=rep.norm_f[i],
                       elapsed=rep.elapsed[i],
                       iterations=rep.iterations[i])
            results.convergence_reports.append(report)

    return results
