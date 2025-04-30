# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import os.path
import warnings
import numpy as np
from typing import List, Dict, Union, Tuple, TYPE_CHECKING

from GridCalEngine import TapModuleControl, TapPhaseControl, BusMode
from GridCalEngine.DataStructures.branch_parent_data import BranchParentData
from GridCalEngine.basic_structures import IntVec, Vec
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import (HvdcControlType, SolverType, TimeGrouping,
                                        ZonalGrouping, MIPSolvers, ContingencyMethod, ContingencyOperationTypes,
                                        BuildStatus, BranchGroupTypes, ConverterControlType)
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

GSLV_RECOMMENDED_VERSION = "0.2.0"
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

    build_status_dict = {
        BuildStatus.Planned: pg.BuildStatus.Planned,
        BuildStatus.Commissioned: pg.BuildStatus.Commissioned,
        BuildStatus.Candidate: pg.BuildStatus.Candidate,
        BuildStatus.Decommissioned: pg.BuildStatus.Decommissioned,
        BuildStatus.PlannedDecommission: pg.BuildStatus.PlannedDecommission,
    }

    tap_module_control_mode_dict = {
        TapModuleControl.fixed: pg.TapModuleControl.fixed,
        TapModuleControl.Qf: pg.TapModuleControl.Qf,
        TapModuleControl.Qt: pg.TapModuleControl.Qt,
        TapModuleControl.Vm: pg.TapModuleControl.Vm,
    }

    tap_phase_control_mode_dict = {
        TapPhaseControl.fixed: pg.TapPhaseControl.fixed,
        TapPhaseControl.Pf: pg.TapPhaseControl.Pf,
        TapPhaseControl.Pt: pg.TapPhaseControl.Pt,
    }

    hvdc_control_mode_dict = {
        HvdcControlType.type_0_free: pg.HvdcControlType.type_0_free,
        HvdcControlType.type_1_Pset: pg.HvdcControlType.type_1_Pset,
    }

    group_type_dict = {
        BranchGroupTypes.GenericGroup: pg.BranchGroupTypes.GenericGroup,
        BranchGroupTypes.TransformerGroup: pg.BranchGroupTypes.TransformerGroup,
        BranchGroupTypes.LineSegmentsGroup: pg.BranchGroupTypes.LineSegmentsGroup,
    }

    contingency_ops_type_dict = {
        ContingencyOperationTypes.Active: pg.ContingencyOperationTypes.Active,
        ContingencyOperationTypes.PowerPercentage: pg.ContingencyOperationTypes.PowerPercentage,
    }

    contingency_method_dict = {
        ContingencyMethod.PTDF: pg.ContingencyMethod.PTDF,
        ContingencyMethod.PowerFlow: pg.ContingencyMethod.PowerFlow,
        ContingencyMethod.HELM: pg.ContingencyMethod.HELM,
    }

    converter_control_type_dict = {
        ConverterControlType.Vm_dc: pg.ConverterControlType.Vm_dc,
        ConverterControlType.Vm_ac: pg.ConverterControlType.Vm_ac,
        ConverterControlType.Va_ac: pg.ConverterControlType.Va_ac,
        ConverterControlType.Qac: pg.ConverterControlType.Q_ac,
        ConverterControlType.Pdc: pg.ConverterControlType.P_dc,
        ConverterControlType.Pac: pg.ConverterControlType.P_ac,
    }

    bus_type_dict = {
        BusMode.PQ_tpe.value: pg.BusMode.PQ,
        BusMode.PV_tpe.value: pg.BusMode.PV,
        BusMode.Slack_tpe.value: pg.BusMode.Slack,
        BusMode.P_tpe.value: pg.BusMode.P,
        BusMode.PQV_tpe.value: pg.BusMode.PQV,
    }

except ImportError as e:
    pg = None
    GSLV_AVAILABLE = False
    GSLV_VERSION = ''
    build_status_dict = dict()
    tap_module_control_mode_dict = dict()
    tap_phase_control_mode_dict = dict()
    contingency_ops_type_dict = dict()
    contingency_method_dict = dict()


def get_gslv_mip_solvers_list() -> List[str]:
    """
    Get list of available MIP solvers
    :return:
    """
    if GSLV_AVAILABLE:
        return list()
    else:
        return list()


def convert_tap_module_control_mode_dict(data: Dict[int, TapModuleControl]) -> Dict[int, "pg.TapModuleControl"]:
    """
    Function to convert a dictionary of TapModuleControl modes to pg.TapModuleControl modes
    :param data:
    :return:
    """
    return {i: tap_module_control_mode_dict[val] for i, val in data.items()}


def convert_tap_module_control_mode_lst(data: List[TapModuleControl]) -> List["pg.TapModuleControl"]:
    """
    Function to convert a list of TapModuleControl modes to pg.TapModuleControl modes
    :param data:
    :return:
    """
    return [tap_module_control_mode_dict[val] for val in data]


def convert_tap_phase_control_mode_dict(data: Dict[int, TapPhaseControl]) -> Dict[int, "pg.TapPhaseControl"]:
    """
    Function to convert a dictionary of TapPhaseControl modes to pg.TapPhaseControl modes
    :param data:
    :return:
    """
    return {i: tap_phase_control_mode_dict[val] for i, val in data.items()}


def convert_tap_phase_control_mode_lst(data: List[TapPhaseControl]) -> List["pg.TapPhaseControl"]:
    """
    Function to convert a list of TapPhaseControl modes to pg.TapPhaseControl modes
    :param data:
    :return:
    """
    return [tap_phase_control_mode_dict[val] for val in data]


def fill_profile(gslv_profile: "pg.Profiledouble|pg.Profilebool|pg.Profileint|pg.Profileuint",
                 gc_profile: Profile,
                 use_time_series: bool,
                 time_indices: Union[IntVec, None],
                 n_time: int = 1,
                 default_val: int | float | bool | TapPhaseControl | TapModuleControl = 0) -> None:
    """
    Generates a default time series
    :param gslv_profile: Profile from gslv to fill in
    :param gc_profile: Profile from gridcal to convert
    :param use_time_series: use time series?
    :param time_indices: time series indices if any (optional)
    :param n_time: number of time steps
    :param default_val: Default value
    """



    if use_time_series:
        if gc_profile.is_sparse:
            if time_indices is None:

                default_val = gc_profile.sparse_array.default_value

                if isinstance(default_val, TapPhaseControl):
                    data = convert_tap_phase_control_mode_dict(data=gc_profile.sparse_array.get_map())

                    # we pick all the profile
                    gslv_profile.init_sparse(default_value=tap_phase_control_mode_dict[gc_profile.default_value],
                                             data=data)

                elif isinstance(default_val, TapModuleControl):
                    data = convert_tap_module_control_mode_dict(data=gc_profile.sparse_array.get_map())

                    # we pick all the profile
                    gslv_profile.init_sparse(default_value=tap_module_control_mode_dict[gc_profile.default_value],
                                             data=data)
                else:
                    data = gc_profile.sparse_array.get_map()

                    # we pick all the profile
                    gslv_profile.init_sparse(default_value=gc_profile.default_value, data=data)

            else:
                assert len(time_indices) == n_time

                # we need a sliced version
                sp_arr2 = gc_profile.sparse_array.slice(time_indices)

                if isinstance(default_val, TapPhaseControl):
                    data = convert_tap_phase_control_mode_dict(data=sp_arr2.get_map())
                    gslv_profile.init_sparse(default_value=tap_phase_control_mode_dict[gc_profile.default_value],
                                             data=data)

                elif isinstance(default_val, TapModuleControl):
                    data = convert_tap_module_control_mode_dict(data=sp_arr2.get_map())
                    gslv_profile.init_sparse(default_value=tap_module_control_mode_dict[gc_profile.default_value],
                                             data=data)

                else:
                    data = sp_arr2.get_map()
                    gslv_profile.init_sparse(default_value=gc_profile.default_value,
                                             data=data)

        else:
            if time_indices is None:
                # we pick all the profile

                if isinstance(default_val, TapPhaseControl):
                    data = convert_tap_phase_control_mode_lst(data=gc_profile.dense_array)
                elif isinstance(default_val, TapModuleControl):
                    data = convert_tap_module_control_mode_dict(data=gc_profile.dense_array)
                else:
                    data = gc_profile.dense_array

                gslv_profile.init_dense(data)

            else:
                assert len(time_indices) == n_time
                # we need a sliced version
                if isinstance(default_val, TapPhaseControl):
                    data = convert_tap_phase_control_mode_lst(data=gc_profile.dense_array[time_indices])
                elif isinstance(default_val, TapModuleControl):
                    data = convert_tap_module_control_mode_dict(data=gc_profile.dense_array[time_indices])
                else:
                    data = gc_profile.dense_array[time_indices]

                gslv_profile.init_dense(data)

    else:
        if isinstance(default_val, TapPhaseControl):
            gslv_profile.fill(tap_phase_control_mode_dict[default_val])

        elif isinstance(default_val, TapModuleControl):
            gslv_profile.fill(tap_module_control_mode_dict[default_val])

        else:
            gslv_profile.fill(default_val)


def fill_profile_with_array(gslv_profile: "pg.Profiledouble",
                            arr: Vec,
                            use_time_series: bool,
                            time_indices: Union[IntVec, None],
                            n_time=1,
                            default_val=0) -> None:
    """
    Generates a default time series
    :param gslv_profile: Profile from gslv to fill in
    :param arr:  array to fill in
    :param use_time_series: use time series?
    :param time_indices: time series indices if any (optional)
    :param n_time: number of time steps
    :param default_val: Default value
    """

    if use_time_series:
        if time_indices is None:
            # we pick all the profile
            gslv_profile.init_dense(arr)
        else:
            assert len(time_indices) == n_time
            # we need a sliced version
            gslv_profile.init_dense(arr[time_indices])

    else:
        gslv_profile.fill(default_val)


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
    """

    :param zone:
    :return:
    """
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


def convert_country(country: dev.Country) -> "pg.Country":
    """

    :param country:
    :return:
    """
    return pg.Country(idtag=country.idtag, code=str(country.code), name=country.name)


def add_countries(circuit: MultiCircuit,
                  gslv_grid: "pg.MultiCircuit") -> Dict[dev.Country, "pg.Country"]:
    """
    Add GSLV countries
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :return: Dictionary [GridCal country] -> GSLV country
    """
    d = dict()

    for i, country in enumerate(circuit.countries):
        elm = convert_country(country)
        gslv_grid.add_country(elm)
        d[country] = elm

    return d


def convert_municipality(country: dev.Municipality) -> "pg.Municipality":
    """

    :param country:
    :return:
    """
    return pg.Municipality(idtag=country.idtag, code=str(country.code), name=country.name)


def add_municipalities(circuit: MultiCircuit,
                       gslv_grid: "pg.MultiCircuit") -> Dict[dev.Country, "pg.Country"]:
    """
    Add GSLV countries
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :return: Dictionary [GridCal country] -> GSLV country
    """
    d = dict()

    for i, municipality in enumerate(circuit.municipalities):
        elm = convert_municipality(municipality)
        gslv_grid.add_municipality(elm)
        d[municipality] = elm

    return d


def convert_region(country: dev.Municipality) -> "pg.Municipality":
    """

    :param country:
    :return:
    """
    return pg.Municipality(idtag=country.idtag, code=str(country.code), name=country.name)


def add_regions(circuit: MultiCircuit,
                gslv_grid: "pg.MultiCircuit") -> Dict[dev.Country, "pg.Country"]:
    """
    Add GSLV countries
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :return: Dictionary [GridCal country] -> GSLV country
    """
    d = dict()

    for i, municipality in enumerate(circuit.regions):
        elm = convert_region(municipality)
        gslv_grid.add_region(elm)
        d[municipality] = elm

    return d


def convert_branch_group(country: dev.BranchGroup) -> "pg.BranchGroup":
    """

    :param country:
    :return:
    """
    return pg.BranchGroup(
        idtag=country.idtag,
        code=str(country.code),
        name=country.name,
        group_type=group_type_dict[country.group_type]
    )


def add_branch_groups(circuit: MultiCircuit,
                      gslv_grid: "pg.MultiCircuit") -> Dict[dev.BranchGroup, "pg.BranchGroup"]:
    """
    Add GSLV countries
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :return: Dictionary [GridCal country] -> GSLV country
    """
    d = dict()

    for i, branch_group in enumerate(circuit.branch_groups):
        elm = convert_branch_group(branch_group)
        gslv_grid.add_branch_group(elm)
        d[branch_group] = elm

    return d


def convert_substation(se: dev.Substation, n_time: int) -> "pg.Substation":
    """

    :param se:
    :param n_time:
    :return:
    """
    return pg.Substation(
        nt=n_time,
        idtag=se.idtag,
        code=str(se.code),
        name=se.name
    )


def add_substations(circuit: MultiCircuit,
                    gslv_grid: "pg.MultiCircuit",
                    n_time: int) -> Dict[dev.Substation, "pg.Substation"]:
    """
    Add GSLV substations
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :param n_time: number of time steps
    :return: Dictionary [GridCal Zone] -> GSLV Zone
    """
    d = dict()

    for i, se in enumerate(circuit.substations):
        elm = convert_substation(se, n_time=n_time)
        gslv_grid.add_substation(elm)
        d[se] = elm

    return d


def convert_voltage_level(elm: dev.VoltageLevel,
                          substations_dict: Dict[dev.Substation, "pg.Substation"]) -> "pg.VoltageLevel":
    """

    :param elm:
    :param substations_dict:
    :return:
    """
    return pg.VoltageLevel(
        idtag=elm.idtag,
        code=str(elm.code),
        name=elm.name,
        Vnom=elm.Vnom,
        substation=substations_dict.get(elm.substation, None)
    )


def add_voltage_levels(
        circuit: MultiCircuit,
        gslv_grid: "pg.MultiCircuit",
        substations_dict: Dict[dev.Substation, "pg.Substation"]
) -> Dict[dev.VoltageLevel, "pg.VoltageLevel"]:
    """
    Add GSLV substations
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV Circuit
    :param substations_dict: substations mapping dictionary
    :return: Dictionary [GridCal Zone] -> GSLV Zone
    """
    d = dict()

    for i, vl in enumerate(circuit.voltage_levels):
        elm = convert_voltage_level(vl, substations_dict=substations_dict)
        gslv_grid.add_voltage_level(elm)
        d[vl] = elm

    return d


def convert_contingency_groups(elm: dev.ContingencyGroup) -> "pg.ContingencyGroup":
    """

    :param elm:
    :return:
    """
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
        cg = convert_contingency_groups(elm)
        gslv_grid.add_contingency_group(cg)
        d[elm] = cg

    return d


def convert_contingencies(elm: dev.Contingency,
                          n_time: int,
                          groups_dict: Dict[dev.ContingencyGroup, "pg.ContingencyGroup"]) -> "pg.Contingency":
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
        con = convert_contingencies(elm=elm,
                                    n_time=n_time,
                                    groups_dict=groups_dict)
        gslv_grid.add_contingency(con)
        d[elm] = con

    return d


def convert_investment_group(elm: dev.InvestmentsGroup) -> "pg.InvestmentGroup":
    """

    :param elm:
    :return:
    """
    return pg.InvestmentGroup(idtag=elm.idtag,
                              code=str(elm.code),
                              name=elm.name,
                              category=elm.category)


def add_investment_groups(circuit: MultiCircuit,
                          gslv_grid: "pg.MultiCircuit") -> Dict[dev.InvestmentsGroup, "pg.InvestmentGroup"]:
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
        elm: dev.Investment,
        groups_dict: Dict[dev.InvestmentsGroup, "pg.InvestmentGroup"]
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
                         group=groups_dict[elm.group],
                         CAPEX=elm.CAPEX,
                         OPEX=elm.OPEX,
                         status=elm.status, )


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
        investment = convert_investment(elm, groups_dict=groups_dict[elm.group])
        gslv_grid.add_investment(investment)
        d[elm] = investment

    return d


def convert_facility(elm: dev.Facility) -> "pg.Facility":
    """

    :param elm:
    :return:
    """
    return pg.Facility(idtag=elm.idtag,
                       code=str(elm.code),
                       name=elm.name)


def add_facilities(circuit: MultiCircuit,
                   gslv_grid: "pg.MultiCircuit") -> Dict[dev.Facility, "pg.Facility"]:
    """

    :param circuit:
    :param gslv_grid:
    :return:
    """
    d = dict()

    for i, elm in enumerate(circuit.facilities):
        facility = convert_facility(elm)
        gslv_grid.add_facility(facility)
        d[elm] = facility

    return d


def convert_modelling_authority(elm: dev.ModellingAuthority) -> "pg.ModellingAuthority":
    """

    :param elm:
    :return:
    """
    return pg.ModellingAuthority(idtag=elm.idtag,
                                 code=str(elm.code),
                                 name=elm.name)


def add_modelling_authorities(circuit: MultiCircuit,
                              gslv_grid: "pg.MultiCircuit") -> Dict[dev.ModellingAuthority, "pg.ModellingAuthority"]:
    """

    :param circuit:
    :param gslv_grid:
    :return:
    """
    d = dict()

    for i, elm in enumerate(circuit.modelling_authorities):
        ma = convert_modelling_authority(elm)
        gslv_grid.add_modelling_authority(ma)
        d[elm] = ma

    return d


def convert_bus(elm: dev.Bus, n_time: int,
                area_dict: Dict[dev.Area, "pg.Area"],
                zone_dict: Dict[dev.Zone, "pg.Zone"],
                substation_dict: Dict[dev.Substation, "pg.Substation"],
                voltage_level_dict: Dict[dev.VoltageLevel, "pg.VoltageLevel"],
                country_dict: Dict[dev.Country, "pg.Country"],
                time_indices: IntVec,
                use_time_series: bool) -> "pg.Bus":
    """

    :param elm:
    :param n_time:
    :param area_dict:
    :param zone_dict:
    :param substation_dict:
    :param voltage_level_dict:
    :param country_dict:
    :param time_indices:
    :param use_time_series:
    :return:
    """
    bus = pg.Bus(nt=n_time,
                 name=elm.name,
                 idtag=elm.idtag,
                 code=str(elm.code),
                 Vnom=elm.Vnom,
                 vmin=elm.Vmin,
                 vmax=elm.Vmax,
                 angle_min=elm.angle_min,
                 angle_max=elm.angle_max,
                 r_fault=elm.r_fault,
                 x_fault=elm.x_fault,
                 active_default=elm.active,

                 is_slack=elm.is_slack,
                 is_dc=elm.is_dc,
                 is_internal=elm.internal,

                 area=area_dict.get(elm.area, None),
                 zone=zone_dict.get(elm.zone, None),
                 substation=substation_dict.get(elm.substation, None),
                 voltage_level=voltage_level_dict.get(elm.substation, None),
                 country=country_dict.get(elm.country, None),
                 latitude=elm.latitude,
                 longitude=elm.longitude,
                 Vm0=elm.Vm0,
                 Va0=elm.Va0,
                 )

    fill_profile(gslv_profile=bus.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    return bus


def add_buses(
        circuit: MultiCircuit,
        gslv_grid: "pg.MultiCircuit",
        area_dict: Dict[dev.Area, "pg.Area"],
        zone_dict: Dict[dev.Zone, "pg.Zone"],
        substation_dict: Dict[dev.Substation, "pg.Substation"],
        voltage_level_dict: Dict[dev.VoltageLevel, "pg.VoltageLevel"],
        country_dict: Dict[dev.Country, "pg.Country"],
        use_time_series: bool,
        n_time: int = 1,
        time_indices: Union[IntVec, None] = None,
) -> Dict[str, "pg.Bus"]:
    """
    Convert the buses to GSLV buses
    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param use_time_series: compile the time series from GridCal? otherwise, just the snapshot
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param area_dict: Area object translation dictionary
    :param zone_dict: Zone object translation dictionary
    :param substation_dict: Substation object translation dictionary
    :param voltage_level_dict: Voltage level object translation dictionary
    :param country_dict: Country object translation dictionary
    :return: bus dictionary buses[uuid] -> Bus
    """

    if time_indices is not None:
        assert (len(time_indices) == n_time)

    if area_dict is None:
        area_dict = {elm: k for k, elm in enumerate(circuit.areas)}

    bus_dict: Dict[str, "pg.Bus"] = dict()

    for i, bus in enumerate(circuit.buses):
        elm = convert_bus(elm=bus, n_time=n_time,
                          area_dict=area_dict,
                          zone_dict=zone_dict,
                          substation_dict=substation_dict,
                          voltage_level_dict=voltage_level_dict,
                          country_dict=country_dict,
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

    fill_profile(gslv_profile=load.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    if opf_results is None:
        fill_profile(gslv_profile=load.P,
                     gc_profile=elm.P_prof,
                     use_time_series=use_time_series,
                     time_indices=time_indices,
                     n_time=n_time,
                     default_val=elm.P)
    else:
        fill_profile_with_array(gslv_profile=load.P,
                                arr=elm.P_prof.toarray() - opf_results.load_shedding[:, k],
                                use_time_series=use_time_series,
                                time_indices=time_indices,
                                n_time=n_time,
                                default_val=elm.P)

    fill_profile(gslv_profile=load.Q,
                 gc_profile=elm.Q_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Q)

    fill_profile(gslv_profile=load.G,
                 gc_profile=elm.G_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.G)

    fill_profile(gslv_profile=load.B,
                 gc_profile=elm.B_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.B)

    fill_profile(gslv_profile=load.Ir,
                 gc_profile=elm.Ir_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Ir)

    fill_profile(gslv_profile=load.Ii,
                 gc_profile=elm.Ii_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Ii)

    fill_profile(gslv_profile=load.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    return load


def add_loads(circuit: MultiCircuit,
              gslv_grid: "pg.MultiCircuit",
              bus_dict: Dict[str, "pg.Bus"],
              use_time_series: bool,
              n_time=1,
              time_indices: IntVec | None = None,
              opf_results: OptimalPowerFlowResults | None = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param use_time_series: compile the time series from GridCal? otherwise just the snapshot
    :param n_time: number of time steps
    :param time_indices:
    :param opf_results:
    :return:
    """
    devices = circuit.get_loads()
    for k, elm in enumerate(devices):
        load = convert_load(k=k, elm=elm, bus_dict=bus_dict,
                            n_time=n_time, use_time_series=use_time_series,
                            time_indices=time_indices, opf_results=opf_results)
        gslv_grid.add_load(load)


def convert_static_generator(elm: dev.StaticGenerator,
                             bus_dict: Dict[str, "pg.Bus"],
                             n_time: int,
                             use_time_series: bool,
                             time_indices: IntVec | None = None, ) -> "pg.StaticGenerator":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :return:
    """

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

    fill_profile(gslv_profile=pe_inj.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=pe_inj.P,
                 gc_profile=elm.P_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.P)

    fill_profile(gslv_profile=pe_inj.Q,
                 gc_profile=elm.Q_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Q)

    fill_profile(gslv_profile=pe_inj.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

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
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :return:
    """
    sh = pg.Shunt(
        nt=n_time,
        name=elm.name,
        idtag=elm.idtag,
        code=str(elm.code),
        G=elm.G,
        B=elm.B,
        build_status=build_status_dict[elm.build_status],
    )

    sh.bus = bus_dict[elm.bus.idtag]

    fill_profile(gslv_profile=sh.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=sh.G,
                 gc_profile=elm.G_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.G)

    fill_profile(gslv_profile=sh.B,
                 gc_profile=elm.B_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.B)

    fill_profile(gslv_profile=sh.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

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
    gen = pg.Generator(
        nt=n_time,
        name=elm.name,
        idtag=elm.idtag,
        active=elm.active,
        P=elm.P,
        power_factor=elm.Pf,
        vset=elm.Vset,
        Pmin=elm.Pmin,
        Pmax=elm.Pmax,
        Qmin=elm.Qmin,
        Qmax=elm.Qmax,
        Snom=elm.Snom,
        is_controlled=elm.is_controlled,
        enabled_dispatch=elm.enabled_dispatch,
        q_points=elm.q_curve.get_data().tolist(),
        use_reactive_power_curve=elm.use_reactive_power_curve
    )

    gen.bus = bus_dict[elm.bus.idtag]

    fill_profile(gslv_profile=gen.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    if opf_results is None:
        fill_profile(gslv_profile=gen.P,
                     gc_profile=elm.P_prof,
                     use_time_series=use_time_series,
                     time_indices=time_indices,
                     n_time=n_time,
                     default_val=elm.P)
    else:
        fill_profile_with_array(gslv_profile=gen.P,
                                arr=opf_results.generator_power[:, k] - opf_results.generator_shedding[:, k],
                                use_time_series=use_time_series,
                                time_indices=time_indices,
                                n_time=n_time,
                                default_val=elm.P)

    fill_profile(gslv_profile=gen.Pf,
                 gc_profile=elm.Pf_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Pf)

    fill_profile(gslv_profile=gen.Vset,
                 gc_profile=elm.Vset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset)

    fill_profile(gslv_profile=gen.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    fill_profile(gslv_profile=gen.Cost0,
                 gc_profile=elm.Cost0_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost0)

    fill_profile(gslv_profile=gen.Cost2,
                 gc_profile=elm.Cost2_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost2)

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
    gen = pg.Battery(
        nt=n_time,
        name=elm.name,
        idtag=elm.idtag,
        P=elm.P,
        power_factor=elm.Pf,
        vset=elm.Vset,
        max_soc=elm.max_soc,
        min_soc=elm.min_soc,
        Qmin=elm.Qmin,
        Qmax=elm.Qmax,
        Pmin=elm.Pmin,
        Pmax=elm.Pmax,
        Snom=elm.Snom,
        Enom=elm.Enom,
        charge_efficiency=elm.charge_efficiency,
        discharge_efficiency=elm.discharge_efficiency,
        is_controlled=elm.is_controlled,
    )

    gen.bus = bus_dict[elm.bus.idtag]

    fill_profile(gslv_profile=gen.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    if opf_results is None:
        fill_profile(gslv_profile=gen.P,
                     gc_profile=elm.P_prof,
                     use_time_series=use_time_series,
                     time_indices=time_indices,
                     n_time=n_time,
                     default_val=elm.P)
    else:
        fill_profile_with_array(gslv_profile=gen.P,
                                arr=opf_results.battery_power[:, k],
                                use_time_series=use_time_series,
                                time_indices=time_indices,
                                n_time=n_time,
                                default_val=elm.P)

    fill_profile(gslv_profile=gen.Pf,
                 gc_profile=elm.Pf_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Pf)

    fill_profile(gslv_profile=gen.Vset,
                 gc_profile=elm.Vset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset)

    fill_profile(gslv_profile=gen.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    fill_profile(gslv_profile=gen.Cost0,
                 gc_profile=elm.Cost0_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost0)

    fill_profile(gslv_profile=gen.Cost2,
                 gc_profile=elm.Cost2_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost2)

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


def convert_line(elm: dev.Line,
                 n_time: int,
                 bus_dict: Dict[str, "pg.Bus"],
                 branch_groups_dict: Dict[dev.BranchGroup, "pg.BranchGroup"],
                 use_time_series: bool, time_indices: IntVec | None = None, ) -> "pg.Line":
    """

    :param elm:
    :param n_time:
    :param bus_dict:
    :param branch_groups_dict:
    :param use_time_series:
    :param time_indices:
    :return:
    """
    lne = pg.Line(
        idtag=elm.idtag,
        code=str(elm.code),
        name=elm.name,
        bus_from=bus_dict[elm.bus_from.idtag],
        bus_to=bus_dict[elm.bus_to.idtag],
        nt=n_time,
        length=elm.length,
        rate=elm.rate if elm.rate > 0 else 9999,
        active=elm.active,
        r=elm.R,
        x=elm.X,
        b=elm.B,
        monitor_loading=elm.monitor_loading,
        contingency_enabled=elm.contingency_enabled,
    )

    lne.group = branch_groups_dict.get(elm.group, None)

    fill_profile(gslv_profile=lne.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=lne.rate,
                 gc_profile=elm.rate_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.rate)

    fill_profile(gslv_profile=lne.contingency_factor,
                 gc_profile=elm.contingency_factor_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.contingency_factor)

    fill_profile(gslv_profile=lne.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    return lne


def add_lines(circuit: MultiCircuit,
              gslv_grid: "pg.MultiCircuit",
              bus_dict: Dict[str, "pg.Bus"],
              branch_groups_dict: Dict[dev.BranchGroup, "pg.BranchGroup"],
              time_series: bool,
              n_time: int = 1,
              time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param branch_groups_dict: dictionary of converted branch groups
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        lne = convert_line(elm=elm,
                           bus_dict=bus_dict,
                           branch_groups_dict=branch_groups_dict,
                           n_time=n_time,
                           use_time_series=time_series,
                           time_indices=time_indices)
        gslv_grid.add_line(lne)


def convert_transformer(elm: dev.Transformer2W,
                        bus_dict: Dict[str, "pg.Bus"],
                        branch_groups_dict: Dict[dev.BranchGroup, "pg.BranchGroup"],
                        n_time: int,
                        use_time_series: bool, time_indices: IntVec | None,
                        override_controls: bool) -> "pg.Transformer2W":
    """

    :param elm:
    :param bus_dict:
    :param branch_groups_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :param override_controls:
    :return:
    """
    tr2 = pg.Transformer2W(idtag=elm.idtag,
                           code=str(elm.code),
                           name=elm.name,
                           bus_from=bus_dict[elm.bus_from.idtag],
                           bus_to=bus_dict[elm.bus_to.idtag],
                           nt=n_time,
                           HV=elm.HV,
                           LV=elm.LV,
                           nominal_power=elm.Sn,
                           copper_losses=elm.Pcu,
                           iron_losses=elm.Pfe,
                           no_load_current=elm.I0,
                           short_circuit_voltage=elm.Vsc,
                           active=elm.active,
                           rate=elm.rate if elm.rate > 0 else 9999,

                           r=elm.R,
                           x=elm.X,
                           g=elm.G,
                           b=elm.B,

                           tap_module=elm.tap_module,
                           tap_module_max=elm.tap_module_max,
                           tap_module_min=elm.tap_module_min,

                           tap_phase=elm.tap_phase,
                           tap_phase_max=elm.tap_phase_max,
                           tap_phase_min=elm.tap_phase_min,

                           tolerance=elm.tolerance,

                           cost=elm.Cost,
                           mttf=elm.mttf,
                           mttr=elm.mttr,

                           vset=elm.vset,
                           Pset=elm.Pset,
                           Qset=elm.Qset,

                           temp_base=elm.temp_base,
                           temp_oper=elm.temp_oper,
                           alpha=elm.alpha,

                           tap_module_control_mode=tap_module_control_mode_dict[elm.tap_module_control_mode],
                           tap_phase_control_mode=tap_phase_control_mode_dict[elm.tap_phase_control_mode],

                           contingency_factor=elm.contingency_factor,
                           protection_rating_factor=elm.protection_rating_factor,

                           contingency_enabled=elm.contingency_enabled,
                           monitor_loading=elm.monitor_loading,

                           )

    tr2.tap_phase_min = elm.tap_phase_min
    tr2.tap_phase_max = elm.tap_phase_max
    tr2.tap_module_min = elm.tap_module_min
    tr2.tap_module_max = elm.tap_module_max

    if elm.regulation_bus is not None:
        tr2.regulation_bus = bus_dict[elm.regulation_bus.idtag]

    fill_profile(gslv_profile=tr2.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=tr2.rate,
                 gc_profile=elm.rate_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.rate)

    fill_profile(gslv_profile=tr2.contingency_factor,
                 gc_profile=elm.contingency_factor_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.contingency_factor)

    fill_profile(gslv_profile=tr2.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

    fill_profile(gslv_profile=tr2.Pset,
                 gc_profile=elm.Pset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Pset)

    fill_profile(gslv_profile=tr2.Qset,
                 gc_profile=elm.Qset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Qset)

    fill_profile(gslv_profile=tr2.vset,
                 gc_profile=elm.vset_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.vset)

    fill_profile(gslv_profile=tr2.tap_phase,
                 gc_profile=elm.tap_phase_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.tap_phase)

    fill_profile(gslv_profile=tr2.tap_phase_control_mode,
                 gc_profile=elm.tap_phase_control_mode_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.tap_phase_control_mode)

    fill_profile(gslv_profile=tr2.tap_module,
                 gc_profile=elm.tap_module_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.tap_module)

    fill_profile(gslv_profile=tr2.tap_module_control_mode,
                 gc_profile=elm.tap_module_control_mode_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.tap_module_control_mode)

    # control vars
    if override_controls:
        tr2.tap_module_control_mode.fill(pg.TapModuleControl.fixed)
        tr2.tap_phase_control_mode.fill(pg.TapPhaseControl.fixed)
    else:
        pass

    return tr2


def add_transformers(circuit: MultiCircuit,
                     gslv_grid: "pg.MultiCircuit",
                     bus_dict: Dict[str, "pg.Bus"],
                     branch_groups_dict: Dict[dev.BranchGroup, "pg.BranchGroup"],
                     time_series: bool,
                     n_time: int = 1,
                     time_indices: Union[IntVec, None] = None,
                     override_controls=False):
    """

    :param circuit: GridCal circuit
    :param gslv_grid: GSLV circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to GSLV bus object
    :param branch_groups_dict: dictionary of branch grous converetd
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param override_controls: If true the controls are set to Fix
    """

    for i, elm in enumerate(circuit.transformers2w):
        tr2 = convert_transformer(elm=elm,
                                  bus_dict=bus_dict,
                                  branch_groups_dict=branch_groups_dict,
                                  n_time=n_time,
                                  use_time_series=time_series,
                                  time_indices=time_indices,
                                  override_controls=override_controls)
        gslv_grid.add_transformer(tr2)


def convert_transformer3w(elm: dev.Transformer3W,
                          bus_dict: Dict[str, "pg.Bus"],
                          n_time: int,
                          use_time_series: bool,
                          time_indices: IntVec | None,
                          override_controls: bool) -> "pg.Transformer3W":
    """

    :param elm:
    :param bus_dict:
    :param n_time:
    :param use_time_series:
    :param time_indices:
    :param override_controls:
    :return:
    """

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
        gslv_grid.add_transformer_3w(tr3)


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

    vsc = pg.Vsc(
        nt=n_time,
        bus_from=bus_dict[elm.bus_from.idtag],
        bus_to=bus_dict[elm.bus_to.idtag],
        name=elm.name,
        idtag=elm.idtag,
        code=str(elm.code),
        active=elm.active,
        rate=9999.0,
        kdp=elm.kdp,
        alpha1=elm.alpha1,
        alpha2=elm.alpha2,
        alpha3=elm.alpha3,
        mttf=elm.mttf,
        mttr=elm.mttr,
        overload_cost=elm.Cost,
        contingency_factor=elm.contingency_factor,
        protection_rating_factor=elm.protection_rating_factor,
        contingency_enabled=elm.contingency_enabled,
        monitor_loading=elm.monitor_loading,
        capex=elm.capex,
        opex=elm.opex,
        build_status=build_status_dict[elm.build_status],
        control1=converter_control_type_dict[elm.control1],
        control2=converter_control_type_dict[elm.control2],
        control1_val=elm.control1_val,
        control2_val=elm.control2_val,
        #     TODO: extend the search
        control1_dev=bus_dict.get(elm.control1_dev, None),
        control2_dev=bus_dict.get(elm.control2_dev, None)
    )

    fill_profile(gslv_profile=vsc.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=vsc.rate,
                 gc_profile=elm.rate_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.rate)

    fill_profile(gslv_profile=vsc.contingency_factor,
                 gc_profile=elm.contingency_factor_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.contingency_factor)

    fill_profile(gslv_profile=vsc.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

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
    lne = pg.DcLine(
        idtag=elm.idtag,
        code=str(elm.code),
        name=elm.name,
        bus_from=bus_dict[elm.bus_from.idtag],
        bus_to=bus_dict[elm.bus_to.idtag],
        nt=n_time,
        length=elm.length,
        rate=elm.rate if elm.rate > 0 else 9999,
        active=elm.active,
        r=float(elm.R),
        monitor_loading=elm.monitor_loading,
        contingency_enabled=elm.contingency_enabled,
    )

    fill_profile(gslv_profile=lne.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=lne.rate,
                 gc_profile=elm.rate_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.rate)

    fill_profile(gslv_profile=lne.contingency_factor,
                 gc_profile=elm.contingency_factor_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.contingency_factor)

    fill_profile(gslv_profile=lne.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

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

    hvdc = pg.HvdcLine(
        idtag=elm.idtag,
        code=str(elm.code),
        name=elm.name,
        bus_from=bus_dict[elm.bus_from.idtag],
        bus_to=bus_dict[elm.bus_to.idtag],
        nt=n_time,
        active=elm.active,
        rate=elm.rate,
        contingency_factor=elm.contingency_factor,
        # monitor_loading=elm.monitor_loading,
        # contingency_enabled=elm.contingency_enabled,
        pset=elm.Pset,
        Vset_f=elm.Vset_f,
        Vset_t=elm.Vset_t,
        r=float(elm.r),
        angle_droop=elm.angle_droop,
        length=elm.length,
        min_firing_angle_f=elm.min_firing_angle_f,
        max_firing_angle_f=elm.max_firing_angle_f,
        min_firing_angle_t=elm.min_firing_angle_t,
        max_firing_angle_t=elm.max_firing_angle_t,
        control_mode=hvdc_control_mode_dict[elm.control_mode]
    )

    fill_profile(gslv_profile=hvdc.active,
                 gc_profile=elm.active_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.active)

    fill_profile(gslv_profile=hvdc.Vset_f,
                 gc_profile=elm.Vset_f_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset_f)

    fill_profile(gslv_profile=hvdc.Vset_f,
                 gc_profile=elm.Vset_f_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset_f)

    fill_profile(gslv_profile=hvdc.Vset_t,
                 gc_profile=elm.Vset_t_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Vset_t)

    fill_profile(gslv_profile=hvdc.angle_droop,
                 gc_profile=elm.angle_droop_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.angle_droop)

    fill_profile(gslv_profile=hvdc.rate,
                 gc_profile=elm.rate_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.rate)

    fill_profile(gslv_profile=hvdc.contingency_factor,
                 gc_profile=elm.contingency_factor_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.contingency_factor)

    fill_profile(gslv_profile=hvdc.cost,
                 gc_profile=elm.Cost_prof,
                 use_time_series=use_time_series,
                 time_indices=time_indices,
                 n_time=n_time,
                 default_val=elm.Cost)

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


class GslvDicts:

    def __init__(self):
        self.area_dict: Dict[dev.Area, "pg.Area"] = dict()

        self.zone_dict: Dict[dev.Zone, "pg.Zone"] = dict()

        self.substation_dict: Dict[dev.Substation, "pg.Substation"] = dict()

        self.voltage_level_dict: Dict[dev.VoltageLevel, "pg.VoltageLevel"] = dict()

        self.country_dict: Dict[dev.Country, "pg.Country"] = dict()

        self.facility_dict: Dict[dev.Facility, "pg.Facility"] = dict()

        self.regions_dict: Dict[dev.Country, "pg.Country"] = dict()

        self.con_groups_dict: Dict[dev.ContingencyGroup, "pg.ContingencyGroup"] = dict()

        self.inv_groups_dict: Dict[dev.InvestmentsGroup, "pg.InvestmentGroup"] = dict()


def to_gslv(circuit: MultiCircuit,
            use_time_series: bool,
            time_indices: Union[IntVec, None] = None,
            override_branch_controls=False,
            opf_results: Union[None, OptimalPowerFlowResults] = None) -> Tuple["pg.MultiCircuit", GslvDicts]:
    """
    Convert GridCal circuit to GSLV
    :param circuit: MultiCircuit
    :param use_time_series: compile the time series from GridCal? otherwise just the snapshot
    :param time_indices: Array of time indices
    :param override_branch_controls: If true the branch controls are set to Fix
    :param opf_results:
    :return: pg.MultiCircuit instance
    """

    dicts = GslvDicts()

    if time_indices is None:
        n_time = circuit.get_time_number() if use_time_series else 1
        if n_time == 0:
            n_time = 1
    else:
        n_time = len(time_indices)

    pg_grid = pg.MultiCircuit(name=circuit.name,
                              nt=n_time,
                              Sbase=circuit.Sbase,
                              fBase=circuit.fBase,
                              idtag=circuit.idtag)

    dicts.area_dict = add_areas(circuit=circuit, gslv_grid=pg_grid)

    dicts.zone_dict = add_zones(circuit=circuit, gslv_grid=pg_grid)

    dicts.substation_dict = add_substations(circuit=circuit, gslv_grid=pg_grid, n_time=n_time)

    dicts.voltage_level_dict = add_voltage_levels(circuit=circuit, gslv_grid=pg_grid,
                                                  substations_dict=dicts.substation_dict)

    dicts.country_dict = add_countries(circuit=circuit, gslv_grid=pg_grid)

    dicts.facility_dict = add_facilities(circuit=circuit, gslv_grid=pg_grid)

    dicts.modelling_authorities_dict = add_modelling_authorities(circuit=circuit, gslv_grid=pg_grid)

    dicts.branch_groups_dict = add_branch_groups(circuit=circuit, gslv_grid=pg_grid)

    dicts.municipalities_dict = add_municipalities(circuit=circuit, gslv_grid=pg_grid)

    dicts.regions_dict = add_regions(circuit=circuit, gslv_grid=pg_grid)

    dicts.con_groups_dict = add_contingency_groups(circuit=circuit, gslv_grid=pg_grid)

    add_contingencies(circuit=circuit, gslv_grid=pg_grid, n_time=n_time, groups_dict=dicts.con_groups_dict)

    dicts.inv_groups_dict = add_investment_groups(circuit=circuit, gslv_grid=pg_grid)

    add_investments(circuit=circuit, gslv_grid=pg_grid, groups_dict=dicts.inv_groups_dict)

    bus_dict = add_buses(
        circuit=circuit,
        gslv_grid=pg_grid,
        use_time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        area_dict=dicts.area_dict,
        zone_dict=dicts.zone_dict,
        substation_dict=dicts.substation_dict,
        voltage_level_dict=dicts.voltage_level_dict,
        country_dict=dicts.country_dict,
    )

    add_loads(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        use_time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
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

    add_lines(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        branch_groups_dict=dicts.branch_groups_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices
    )

    add_transformers(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        branch_groups_dict=dicts.branch_groups_dict,
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

    return pg_grid, dicts


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
                   SolverType.FASTDECOUPLED: pg.SolverType.FASTDECOUPLED
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

    """
    solver_type: pygslv.SolverType = <SolverType.NR: 0>, 
    retry_with_other_methods: bool = True, 
    verbose: int = 0, 
    initialize_with_existing_solution: bool = False, 
    tolerance: float = 1e-06, 
    max_iter: int = 25, 
    max_outer_loop_iter: int = 100, 
    control_Q: bool = True, 
    control_taps_modules: bool = True, 
    control_taps_phase: bool = True, 
    control_remote_voltage: bool = True, 
    orthogonalize_controls: bool = True, 
    apply_temperature_correction: bool = True, 
    branch_impedance_tolerance_mode: pygslv.BranchImpedanceMode = <BranchImpedanceMode.Specified: 0>, 
    distributed_slack: bool = False, 
    ignore_single_node_islands: bool = False, 
    trust_radius: float = 1.0, 
    backtracking_parameter: float = 0.05, 
    use_stored_guess: bool = False, 
    generate_report: bool = False)

    """

    return pg.PowerFlowOptions(
        solver_type=solver_type,
        retry_with_other_methods=opt.retry_with_other_methods,
        verbose=opt.verbose,
        initialize_with_existing_solution=opt.use_stored_guess,
        tolerance=opt.tolerance,
        max_iter=opt.max_iter,
        control_Q=opt.control_Q,
        control_taps_modules=opt.control_taps_modules,
        control_taps_phase=opt.control_taps_phase,
        control_remote_voltage=opt.control_remote_voltage,
        orthogonalize_controls=opt.orthogonalize_controls,
        apply_temperature_correction=opt.orthogonalize_controls,
        branch_impedance_tolerance_mode=pg.BranchImpedanceMode.Specified,
        distributed_slack=opt.distributed_slack,
        ignore_single_node_islands=opt.ignore_single_node_islands,
        trust_radius=opt.trust_radius,
        backtracking_parameter=opt.backtracking_parameter,
        use_stored_guess=opt.use_stored_guess,
        generate_report=opt.generate_report
    )


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
    results = PowerFlowResults(
        n=grid.get_bus_number(),
        m=grid.get_branch_number_wo_hvdc(),
        n_hvdc=grid.get_hvdc_number(),
        n_vsc=grid.get_vsc_number(),
        n_gen=grid.get_generators_number(),
        n_batt=grid.get_batteries_number(),
        n_sh=grid.get_shunt_like_device_number(),
        bus_names=grid.get_bus_names(),
        branch_names=grid.get_branch_names(add_switch=True),
        hvdc_names=grid.get_hvdc_names(),
        vsc_names=grid.get_vsc_names(),
        gen_names=grid.get_generator_names(),
        batt_names=grid.get_battery_names(),
        sh_names=grid.get_shunt_like_devices_names(),
        bus_types=np.ones(grid.get_bus_number(), dtype=int)
    )

    results.voltage = res.voltage[0, :]
    results.Sbus = res.S[0, :]
    results.Sf = res.Sf[0, :]
    results.St = res.St[0, :]
    results.loading = res.loading[0, :]
    results.losses = res.losses[0, :]
    # results.Vbranch = res.Vbranch[0, :]
    # results.If = res.If[0, :]
    # results.It = res.It[0, :]
    # results.Beq = res.Beq[0, :]
    results.m = res.tap_module[0, :]
    results.tap_angle = res.tap_angle[0, :]
    # results.F = res.F
    # results.T = res.T
    # results.hvdc_F = res.hvdc_F[0, :]
    # results.hvdc_T = res.hvdc_T[0, :]
    results.Pf_hvdc = res.Pf_hvdc[0, :]
    results.Pt_hvdc = res.Pt_hvdc[0, :]
    results.loading_hvdc = res.loading_hvdc[0, :]
    results.losses_hvdc = res.losses_hvdc[0, :]
    # results.bus_area_indices = grid.get_bus_area_indices()
    # results.area_names = [a.name for a in grid.areas]
    # results.bus_types = convert_bus_types(res.bus_types[0])  # this is a list of lists

    # for rep in res.stats[0]:
    #     report = ConvergenceReport()
    #     for i in range(len(rep.converged)):
    #         report.add(method=rep.solver[i].name,
    #                    converged=rep.converged[i],
    #                    error=rep.norm_f[i],
    #                    elapsed=rep.elapsed[i],
    #                    iterations=rep.iterations[i])
    #         results.convergence_reports.append(report)

    return results


def gslv_contingencies(circuit: MultiCircuit,
                       con_opt: ContingencyAnalysisOptions,
                       time_series: bool = False,
                       time_indices: Union[IntVec, None] = None) -> "pg.ContingencyAnalysisResults":
    """
    GSLV power flow
    :param circuit: MultiCircuit instance
    :param pf_opt: Power Flow Options
    :param time_series: Compile with GridCal time series?
    :param time_indices: Array of time indices
    :param opf_results: Instance of
    :return: GSLV Power flow results object
    """
    override_branch_controls = not (con_opt.pf_options.control_taps_modules and con_opt.pf_options.control_taps_phase)

    gslv_grid, _ = to_gslv(circuit,
                           use_time_series=time_series,
                           time_indices=None,
                           override_branch_controls=override_branch_controls,
                           opf_results=None)

    con_opt_gslv = pg.ContingencyAnalysisOptions(
        use_provided_flows=con_opt.use_provided_flows,
        Pf=con_opt.Pf,
        pf_options=get_gslv_pf_options(con_opt.pf_options),
        lin_options=pg.LinearAnalysisOptions(
            distributeSlack=con_opt.lin_options.distribute_slack,
            correctValues=con_opt.lin_options.correct_values,
            ptdfThreshold=con_opt.lin_options.ptdf_threshold,
            lodfThreshold=con_opt.lin_options.lodf_threshold,
        ),
        use_srap=con_opt.use_srap,
        srap_max_power=con_opt.srap_max_power,
        srap_top_n=con_opt.srap_top_n,
        srap_dead_band=con_opt.srap_deadband,
        srap_rever_to_nominal_rating=con_opt.srap_rever_to_nominal_rating,
        detailed_massive_report=con_opt.detailed_massive_report,
        contingency_dead_band=con_opt.contingency_deadband,
        contingency_method=contingency_method_dict[con_opt.contingency_method],
    )

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

    logger = pg.Logger()

    res = pg.run_contingencies(grid=gslv_grid,
                               options=con_opt_gslv,
                               n_threads=n_threads,
                               time_indices=time_indices,
                               logger=logger)

    return res


def CheckArr(arr: Vec, arr_expected: Vec, tol: float, name: str, test: str, verbose=False):
    """

    :param arr:
    :param arr_expected:
    :param tol:
    :param name:
    :param test:
    :param verbose:
    :return:
    """
    if arr.shape != arr_expected.shape:
        print('failed (shape):', name, test)
        print(f"got     : {arr}, \n"
              f"expected: {arr_expected}")
        return 1

    if np.allclose(arr, arr_expected, atol=tol):
        if verbose:
            print('ok:', name, test)
            print('ok:', name, test)
        return 0
    else:
        diff = arr - arr_expected
        print('failed:', name, test, '| max:', diff.max(), 'min:', diff.min())
        return 1


def CheckArrEq(arr: np.ndarray, arr_expected: np.ndarray,
               name: str, test: str, verbose=False):
    """

    :param arr:
    :param arr_expected:
    :param name:
    :param test:
    :param verbose:
    :return:
    """
    if arr.shape != arr_expected.shape:
        print('failed (shape):', name, test)
        print(f"got     : {arr}, \n"
              f"expected: {arr_expected}")
        return 1

    if np.all(arr == arr_expected):
        if verbose:
            print('ok:', name, test)
        return 0
    else:
        print('failed:', name, test)
        return 1


def convert_arr(arr, d: Dict):
    return np.array([d[e] for e in arr])


def compare_branch_parent_data(gslv_branch_data: pg.BranchParentData,
                               gc_branch_data: BranchParentData,
                               tol: float,
                               parent_name: str):
    """

    :param gslv_branch_data:
    :param gc_branch_data:
    :param tol:
    :param parent_name:
    :return:
    """
    errors = 0

    # branch data
    errors += CheckArrEq(np.array(gslv_branch_data.idtag), np.array(gc_branch_data.idtag), parent_name, 'idtag')
    errors += CheckArrEq(gslv_branch_data.F, gc_branch_data.F, parent_name, 'F')
    errors += CheckArrEq(gslv_branch_data.T, gc_branch_data.T,  parent_name, 'T')
    errors += CheckArrEq(gslv_branch_data.active, gc_branch_data.active,  parent_name, 'active')
    errors += CheckArr(gslv_branch_data.rates, gc_branch_data.rates, tol, parent_name, 'rates')

    errors += CheckArr(gslv_branch_data.contingency_rates, gc_branch_data.contingency_rates, tol,
                       parent_name, 'contingency_rates')

    errors += CheckArr(gslv_branch_data.protection_rates, gc_branch_data.protection_rates, tol,
                       parent_name, 'protection_rates')

    errors += CheckArr(gslv_branch_data.mttf, gc_branch_data.mttf, tol, parent_name, 'mttf')
    errors += CheckArr(gslv_branch_data.mttr, gc_branch_data.mttr, tol, parent_name, 'mttr')

    errors += CheckArrEq(gslv_branch_data.contingency_enabled, gc_branch_data.contingency_enabled,
                       parent_name, 'contingency_enabled')
    errors += CheckArrEq(gslv_branch_data.monitor_loading, gc_branch_data.monitor_loading,
                       parent_name, 'monitor_loading')

    errors += CheckArr(gslv_branch_data.overload_cost, gc_branch_data.overload_cost, tol,
                       parent_name, 'overload_cost')
    errors += CheckArrEq(gslv_branch_data.original_idx, gc_branch_data.original_idx,
                       parent_name, 'original_idx')
    # errors += CheckArr(gslv_branch_data.reducible, gc_branch_data.reducible, tol, parent_name, 'reducible')

    return errors


def compare_nc(nc_gslv: "pg.NumericalCircuit", nc_gc: NumericalCircuit, tol: float):
    """

    :param nc_gslv:
    :param nc_gc:
    :param tol:
    :return:
    """
    errors = 0

    # bus data
    errors += CheckArrEq(nc_gslv.bus_data.active, nc_gc.bus_data.active,  'BusData', 'active')
    errors += CheckArr(nc_gslv.bus_data.Vbus.real, nc_gc.bus_data.Vbus.real, tol, 'BusData', 'V0')
    errors += CheckArr(nc_gslv.bus_data.installed_power, nc_gc.bus_data.installed_power, tol,
                       'BusData', 'installed power')
    errors += CheckArrEq(np.array(nc_gslv.bus_data.bus_types),
                         convert_arr(nc_gc.bus_data.bus_types, bus_type_dict),
                         'BusData', 'bus_types')

    # branch data
    errors += compare_branch_parent_data(nc_gslv.passive_branch_data, nc_gc.passive_branch_data, tol,
                                         "PassiveBranchData")
    errors += CheckArr(nc_gslv.passive_branch_data.R, nc_gc.passive_branch_data.R, tol, 'PassiveBranchData', 'r')
    errors += CheckArr(nc_gslv.passive_branch_data.X, nc_gc.passive_branch_data.X, tol, 'PassiveBranchData', 'x')
    errors += CheckArr(nc_gslv.passive_branch_data.G, nc_gc.passive_branch_data.G, tol, 'PassiveBranchData', 'g')
    errors += CheckArr(nc_gslv.passive_branch_data.B, nc_gc.passive_branch_data.B, tol, 'PassiveBranchData', 'b')
    errors += CheckArr(nc_gslv.passive_branch_data.virtual_tap_f, nc_gc.passive_branch_data.virtual_tap_f, tol,
                       'PassiveBranchData', 'vtap_f')
    errors += CheckArr(nc_gslv.passive_branch_data.virtual_tap_t, nc_gc.passive_branch_data.virtual_tap_t, tol,
                       'PassiveBranchData', 'vtap_t')

    errors += CheckArr(nc_gslv.active_branch_data.tap_module, nc_gc.active_branch_data.tap_module, tol,
                       'BranchData', 'tap_module')
    errors += CheckArr(nc_gslv.active_branch_data.tap_angle, nc_gc.active_branch_data.tap_angle, tol,
                       'BranchData', 'tap_angle')

    # VSC data
    errors += compare_branch_parent_data(nc_gslv.vsc_data, nc_gc.vsc_data, tol, "VscData")
    errors += CheckArr(nc_gslv.vsc_data.alpha1, nc_gc.vsc_data.alpha1, tol, 'VscData', 'alpha1')
    errors += CheckArr(nc_gslv.vsc_data.alpha2, nc_gc.vsc_data.alpha2, tol, 'VscData', 'alpha2')
    errors += CheckArr(nc_gslv.vsc_data.alpha3, nc_gc.vsc_data.alpha3, tol, 'VscData', 'alpha3')

    errors += CheckArrEq(np.array(nc_gslv.vsc_data.control1),
                         convert_arr(nc_gc.vsc_data.control1, converter_control_type_dict),
                         'VscData', 'control1')
    errors += CheckArrEq(np.array(nc_gslv.vsc_data.control2),
                         convert_arr(nc_gc.vsc_data.control2, converter_control_type_dict),
                         'VscData', 'control2')

    errors += CheckArr(nc_gslv.vsc_data.control1_val, nc_gc.vsc_data.control1_val, tol, 'VscData', 'control1_val')
    errors += CheckArr(nc_gslv.vsc_data.control2_val, nc_gc.vsc_data.control2_val, tol, 'VscData', 'control2_val')

    errors += CheckArrEq(nc_gslv.vsc_data.control1_bus_idx, nc_gc.vsc_data.control1_bus_idx,  'VscData',
                       'control1_bus_idx')
    errors += CheckArrEq(nc_gslv.vsc_data.control2_bus_idx, nc_gc.vsc_data.control2_bus_idx,  'VscData',
                       'control2_bus_idx')
    errors += CheckArrEq(nc_gslv.vsc_data.control1_branch_idx, nc_gc.vsc_data.control1_branch_idx,  'VscData',
                       'control1_branch_idx')
    errors += CheckArrEq(nc_gslv.vsc_data.control2_branch_idx, nc_gc.vsc_data.control2_branch_idx,  'VscData',
                       'control2_branch_idx')

    # HVDC data
    errors += compare_branch_parent_data(nc_gslv.hvdc_data, nc_gc.hvdc_data, tol, "HvdcData")
    errors += CheckArrEq(nc_gslv.hvdc_data.dispatchable, nc_gc.hvdc_data.dispatchable,
                         'HvdcData', 'dispatchable')
    errors += CheckArr(nc_gslv.hvdc_data.r, nc_gc.hvdc_data.r, tol, 'HvdcData', 'r')
    errors += CheckArr(nc_gslv.hvdc_data.Pset, nc_gc.hvdc_data.Pset, tol, 'HvdcData', 'Pset')
    errors += CheckArr(nc_gslv.hvdc_data.Pt, nc_gc.hvdc_data.Pt, tol, 'HvdcData', 'Pt')
    errors += CheckArr(nc_gslv.hvdc_data.Vset_f, nc_gc.hvdc_data.Vset_f, tol, 'HvdcData', 'Vset_f')
    errors += CheckArr(nc_gslv.hvdc_data.Vset_t, nc_gc.hvdc_data.Vset_t, tol, 'HvdcData', 'Vset_t')
    errors += CheckArr(nc_gslv.hvdc_data.Vnf, nc_gc.hvdc_data.Vnf, tol, 'HvdcData', 'Vnf')
    errors += CheckArr(nc_gslv.hvdc_data.Vnt, nc_gc.hvdc_data.Vnt, tol, 'HvdcData', 'Vnt')
    errors += CheckArr(nc_gslv.hvdc_data.angle_droop, nc_gc.hvdc_data.angle_droop, tol, 'HvdcData', 'control1_val')

    errors += CheckArrEq(np.array(nc_gslv.hvdc_data.control_mode),
                         convert_arr(nc_gc.hvdc_data.control_mode, hvdc_control_mode_dict),
                         'HvdcData', 'control_mode')

    errors += CheckArr(nc_gslv.hvdc_data.Qmin_f, nc_gc.hvdc_data.Qmin_f, tol, 'HvdcData', 'Qmin_f')
    errors += CheckArr(nc_gslv.hvdc_data.Qmax_f, nc_gc.hvdc_data.Qmax_f, tol, 'HvdcData', 'Qmax_f')
    errors += CheckArr(nc_gslv.hvdc_data.Qmin_t, nc_gc.hvdc_data.Qmin_t, tol, 'HvdcData', 'Qmin_t')
    errors += CheckArr(nc_gslv.hvdc_data.Qmax_t, nc_gc.hvdc_data.Qmax_t, tol, 'HvdcData', 'Qmax_t')

    # generator data
    errors += CheckArrEq(nc_gslv.generator_data.bus_idx, nc_gc.generator_data.bus_idx,  'GenData', 'bus_idx')
    errors += CheckArrEq(nc_gslv.generator_data.active, nc_gc.generator_data.active,  'GenData', 'active')
    errors += CheckArr(nc_gslv.generator_data.p, nc_gc.generator_data.p, tol, 'GenData', 'P')
    errors += CheckArr(nc_gslv.generator_data.pf, nc_gc.generator_data.pf, tol, 'GenData', 'Pf')
    errors += CheckArr(nc_gslv.generator_data.v, nc_gc.generator_data.v, tol, 'GenData', 'v')
    errors += CheckArr(nc_gslv.generator_data.qmin, nc_gc.generator_data.qmin, tol, 'GenData', 'qmin')
    errors += CheckArr(nc_gslv.generator_data.qmax, nc_gc.generator_data.qmax, tol, 'GenData', 'qmax')

    # load data
    errors += CheckArr(nc_gslv.load_data.bus_idx, nc_gc.load_data.bus_idx, tol, 'LoadData', 'bus_idx')
    errors += CheckArr(nc_gslv.load_data.active, nc_gc.load_data.active.astype(int), tol, 'LoadData', 'active')
    errors += CheckArr(nc_gslv.load_data.S, nc_gc.load_data.S, tol, 'LoadData', 'S')
    errors += CheckArr(nc_gslv.load_data.I, nc_gc.load_data.I, tol, 'LoadData', 'I')
    errors += CheckArr(nc_gslv.load_data.Y, nc_gc.load_data.Y, tol, 'LoadData', 'Y')

    # shunt
    errors += CheckArr(nc_gslv.shunt_data.bus_idx, nc_gc.shunt_data.bus_idx, tol, 'ShuntData', 'bus_idx')
    errors += CheckArrEq(nc_gslv.shunt_data.active, nc_gc.shunt_data.active, 'ShuntData', 'active')
    errors += CheckArr(nc_gslv.shunt_data.Y, nc_gc.shunt_data.Y, tol, 'ShuntData', 'Y')

    # ------------------------------------------------------------------------------------------------------------------
    #  Compare arrays and data
    # ------------------------------------------------------------------------------------------------------------------

    gslv_inj = nc_gslv.get_power_injections()
    gslv_types = nc_gslv.get_simulation_indices(gslv_inj.real)
    gslv_conn = nc_gslv.get_connectivity_matrices()
    gslv_adm = nc_gslv.get_admittance_matrices(gslv_conn)

    gc_inj = nc_gc.get_power_injections()
    gc_types = nc_gc.get_simulation_indices(gc_inj)
    gc_conn = nc_gc.get_connectivity_matrices()
    gc_adm = nc_gc.get_admittance_matrices()

    errors += CheckArr(gslv_inj.real, gc_inj.real, tol, 'Pbus', 'P')
    errors += CheckArr(gslv_inj.imag, gc_inj.imag, tol, 'Qbus', 'Q')

    errors += CheckArrEq(np.array(gslv_types.types),
                         convert_arr(gc_types.bus_types, bus_type_dict),
                         'Types', 'bus_types')
    errors += CheckArr(gslv_types.pq, gc_types.pq, tol, 'Types', 'pq')
    errors += CheckArr(gslv_types.pv, gc_types.pv, tol, 'Types', 'pv')
    errors += CheckArr(gslv_types.vd, gc_types.vd, tol, 'Types', 'vd')
    errors += CheckArr(gslv_types.pqv, gc_types.pqv, tol, 'Types', 'pqv')
    errors += CheckArr(gslv_types.p, gc_types.p, tol, 'Types', 'p')

    errors += CheckArr(gslv_conn.Cf.toarray(), gc_conn.Cf.toarray(), tol, 'Connectivity', 'Cf (dense)')
    errors += CheckArr(gslv_conn.Ct.toarray(), gc_conn.Ct.toarray(), tol, 'Connectivity', 'Ct (dense)')
    errors += CheckArr(gslv_conn.Cf.data, gc_conn.Cf.tocsc().data, tol, 'Connectivity', 'Cf')
    errors += CheckArr(gslv_conn.Ct.data, gc_conn.Ct.tocsc().data, tol, 'Connectivity', 'Ct')

    errors += CheckArr(gslv_adm.Ybus.toarray(), gc_adm.Ybus.toarray(), tol, 'Admittances', 'Ybus (dense)')
    errors += CheckArr(gslv_adm.Ybus.data.real, gc_adm.Ybus.tocsc().data.real, tol,
                       'Admittances', 'Ybus (real)')
    errors += CheckArr(gslv_adm.Ybus.data.imag, gc_adm.Ybus.tocsc().data.imag, tol,
                       'Admittances', 'Ybus (imag)')
    errors += CheckArr(gslv_adm.Yf.data.real, gc_adm.Yf.tocsc().data.real, tol, 'Admittances', 'Yf (real)')
    errors += CheckArr(gslv_adm.Yf.data.imag, gc_adm.Yf.tocsc().data.imag, tol, 'Admittances', 'Yf (imag)')
    errors += CheckArr(gslv_adm.Yt.data.real, gc_adm.Yt.tocsc().data.real, tol, 'Admittances', 'Yt (real)')
    errors += CheckArr(gslv_adm.Yt.data.imag, gc_adm.Yt.tocsc().data.imag, tol, 'Admittances', 'Yt (imag)')

    return errors
