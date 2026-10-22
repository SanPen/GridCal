# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from VeraGridEngine.Devices.Aggregation.area import Area
from VeraGridEngine.Devices.Aggregation.branch_group import BranchGroup
from VeraGridEngine.Devices.Aggregation.country import Country
from VeraGridEngine.Devices.Aggregation.facility import Facility
from VeraGridEngine.Devices.Aggregation.investments_group import InvestmentsGroup
from VeraGridEngine.Devices.Aggregation.market_unit import MarketUnit
from VeraGridEngine.Devices.Aggregation.modelling_authority import ModellingAuthority
from VeraGridEngine.Devices.Aggregation.municipality import Municipality
from VeraGridEngine.Devices.Aggregation.region import Region
from VeraGridEngine.Devices.Aggregation.zone import Zone
from VeraGridEngine.Devices.Associations.emission_gas import EmissionGas
from VeraGridEngine.Devices.Associations.fuel import Fuel
from VeraGridEngine.Devices.Associations.technology import Technology
from VeraGridEngine.Devices.Events.contingency_group import ContingencyGroup
from VeraGridEngine.Devices.Substation.substation import Substation
from VeraGridEngine.Devices.Substation.voltage_level import VoltageLevel
from VeraGridEngine.Compilers.Gslv.activation import pg
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import IntVec
import numpy as np
from typing import (
    Dict,
    List,
    TYPE_CHECKING,
    Tuple,
    Union,
)
from VeraGridEngine.Compilers.Gslv.Devices.remedial_actions import bind_event_devices
from VeraGridEngine.Compilers.Gslv.Devices.areas import add_areas
from VeraGridEngine.Compilers.Gslv.Devices.zones import add_zones
from VeraGridEngine.Compilers.Gslv.Devices.countries import add_countries
from VeraGridEngine.Compilers.Gslv.Devices.municipalities import add_municipalities
from VeraGridEngine.Compilers.Gslv.Devices.regions import add_regions
from VeraGridEngine.Compilers.Gslv.Devices.branch_groups import add_branch_groups
from VeraGridEngine.Compilers.Gslv.Devices.substations import add_substations
from VeraGridEngine.Compilers.Gslv.Devices.voltage_levels import add_voltage_levels
from VeraGridEngine.Compilers.Gslv.Devices.contingencies import add_contingency_groups, add_contingencies
from VeraGridEngine.Compilers.Gslv.Devices.investments import add_investment_groups, add_investments
from VeraGridEngine.Compilers.Gslv.Devices.facilities import add_facilities
from VeraGridEngine.Compilers.Gslv.Devices.market_units import add_market_units
from VeraGridEngine.Compilers.Gslv.Devices.modelling_authorities import add_modelling_authorities
from VeraGridEngine.Compilers.Gslv.Devices.associations import add_emission_gases, add_fuels, add_technologies
from VeraGridEngine.Compilers.Gslv.Devices.buses import add_buses
from VeraGridEngine.Compilers.Gslv.Devices.loads import add_loads
from VeraGridEngine.Compilers.Gslv.Devices.static_generators import add_static_generators
from VeraGridEngine.Compilers.Gslv.Devices.shunts import add_shunts
from VeraGridEngine.Compilers.Gslv.Devices.controllable_shunts import add_controllable_shunts
from VeraGridEngine.Compilers.Gslv.Devices.generators import add_generators
from VeraGridEngine.Compilers.Gslv.Devices.batteries import add_battery_data
from VeraGridEngine.Compilers.Gslv.Devices.lines import add_lines
from VeraGridEngine.Compilers.Gslv.Devices.dc_lines import add_dc_lines
from VeraGridEngine.Compilers.Gslv.Devices.transformers import add_transformers
from VeraGridEngine.Compilers.Gslv.Devices.transformers3w import add_transformers3w
from VeraGridEngine.Compilers.Gslv.Devices.vsc import add_vscs
from VeraGridEngine.Compilers.Gslv.Devices.hvdc_line import add_hvdcs

if TYPE_CHECKING:
    from VeraGridEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults


class GslvDicts:
    """
    Hold the VeraGrid-to-GSLV object lookup dictionaries produced during conversion.
    """
    __slots__ = (
        "area_dict",
        "zone_dict",
        "substation_dict",
        "voltage_level_dict",
        "country_dict",
        "facility_dict",
        "market_unit_dict",
        "modelling_authorities_dict",
        "branch_groups_dict",
        "municipalities_dict",
        "regions_dict",
        "con_groups_dict",
        "inv_groups_dict",
        "technology_dict",
        "fuel_dict",
        "emission_gas_dict",
    )

    def __init__(self) -> None:
        """
        Initialize every conversion lookup dictionary before the conversion stages fill them.

        :return: None.
        """
        self.area_dict: Dict[Area, "pg.Area"] = dict()

        self.zone_dict: Dict[Zone, "pg.Zone"] = dict()

        self.substation_dict: Dict[Substation, "pg.Substation"] = dict()

        self.voltage_level_dict: Dict[VoltageLevel, "pg.VoltageLevel"] = dict()

        self.country_dict: Dict[Country, "pg.Country"] = dict()

        self.facility_dict: Dict[Facility, "pg.Facility"] = dict()

        self.market_unit_dict: Dict[MarketUnit, "pg.MarketUnit"] = dict()

        self.modelling_authorities_dict: Dict[ModellingAuthority, "pg.ModellingAuthority"] = dict()

        self.branch_groups_dict: Dict[BranchGroup, "pg.BranchGroup"] = dict()

        self.municipalities_dict: Dict[Municipality, "pg.Municipality"] = dict()

        self.regions_dict: Dict[Region, "pg.Region"] = dict()

        self.con_groups_dict: Dict[ContingencyGroup, "pg.ContingencyGroup"] = dict()

        self.inv_groups_dict: Dict[InvestmentsGroup, "pg.InvestmentGroup"] = dict()

        self.technology_dict: Dict[Technology, "pg.Technology"] = dict()

        self.fuel_dict: Dict[Fuel, "pg.Fuel"] = dict()

        self.emission_gas_dict: Dict[EmissionGas, "pg.EmissionGas"] = dict()


def to_gslv(circuit: MultiCircuit,
            use_time_series: bool,
            time_indices: Union[IntVec, None] = None,
            override_branch_controls: bool = False,
            opf_results: Union[None, OptimalPowerFlowResults] = None,
            add_three_phase_data: bool = False) -> Tuple["pg.MultiCircuit", GslvDicts]:
    """
    Convert VeraGrid circuit to GSLV
    :param circuit: MultiCircuit
    :param use_time_series: compile the time series from VeraGrid? otherwise just the snapshot
    :param time_indices: Array of time indices
    :param override_branch_controls: If true the branch controls are set to Fix
    :param opf_results:
    :param add_three_phase_data: Export explicit three-phase device data when possible.
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

    for substation in circuit.substations:
        if substation.country is None:
            pass
        else:
            dicts.substation_dict[substation].country = dicts.country_dict[substation.country]

    dicts.facility_dict = add_facilities(circuit=circuit, gslv_grid=pg_grid)

    dicts.market_unit_dict = add_market_units(circuit=circuit)

    dicts.technology_dict = add_technologies(circuit=circuit, gslv_grid=pg_grid)

    dicts.fuel_dict = add_fuels(circuit=circuit, gslv_grid=pg_grid)

    dicts.emission_gas_dict = add_emission_gases(circuit=circuit, gslv_grid=pg_grid)

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
        facility_dict=dicts.facility_dict,
        technology_dict=dicts.technology_dict,
        use_time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        add_three_phase_data=add_three_phase_data,
    )

    add_static_generators(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        facility_dict=dicts.facility_dict,
        technology_dict=dicts.technology_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
    )

    add_shunts(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        facility_dict=dicts.facility_dict,
        technology_dict=dicts.technology_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        add_three_phase_data=add_three_phase_data,
    )

    add_controllable_shunts(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        facility_dict=dicts.facility_dict,
        technology_dict=dicts.technology_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        add_three_phase_data=add_three_phase_data,
    )

    add_generators(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        facility_dict=dicts.facility_dict,
        technology_dict=dicts.technology_dict,
        fuel_dict=dicts.fuel_dict,
        emission_gas_dict=dicts.emission_gas_dict,
        market_unit_dict=dicts.market_unit_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        opf_results=opf_results,
        add_three_phase_data=add_three_phase_data,
    )

    add_battery_data(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        facility_dict=dicts.facility_dict,
        technology_dict=dicts.technology_dict,
        fuel_dict=dicts.fuel_dict,
        emission_gas_dict=dicts.emission_gas_dict,
        market_unit_dict=dicts.market_unit_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        opf_results=opf_results,
        add_three_phase_data=add_three_phase_data,
    )

    add_lines(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        branch_groups_dict=dicts.branch_groups_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        add_three_phase_data=add_three_phase_data,
    )

    add_transformers(
        circuit=circuit,
        gslv_grid=pg_grid,
        bus_dict=bus_dict,
        branch_groups_dict=dicts.branch_groups_dict,
        time_series=use_time_series,
        n_time=n_time,
        time_indices=time_indices,
        override_controls=override_branch_controls,
        add_three_phase_data=add_three_phase_data,
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

    bind_event_devices(circuit=circuit, gslv_grid=pg_grid)

    return pg_grid, dicts


class FakeAdmittances:
    """
    Fake admittances class needed to make the translation
    """

    __slots__ = (
        'Ybus',
        'Yf',
        'Yt',
    )

    def __init__(self) -> None:
        """
        Build one placeholder admittance container.

        :return: None.
        """
        self.Ybus = None
        self.Yf = None
        self.Yt = None


def get_snapshots_from_gslv(circuit: MultiCircuit, override_branch_controls: bool = False) -> List[NumericalCircuit]:
    """

    :param circuit:
    :param override_branch_controls:
    :return:
    """

    gslv_grid, _ = to_gslv(circuit,
                           use_time_series=False,
                           override_branch_controls=override_branch_controls)

    logger = pg.Logger()
    npa_data_lst = pg.compile(gslv_grid, logger=logger, t_idx=0).split_into_islands(logger=logger)

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

        conn = npa_data.get_connectivity_matrices()
        power_injections = npa_data.get_power_injections()
        current_injections = npa_data.get_current_injections()
        tpes = npa_data.get_simulation_indices(power_injections.real)
        adm = npa_data.get_admittance_matrices()
        series_adm = npa_data.get_series_admittances(conn)
        qmax_bus, qmin_bus = npa_data.get_reactive_power_limits()

        data.Vbus_ = npa_data.bus_data.Vbus.reshape(-1, 1)
        data.Sbus_ = power_injections.reshape(-1, 1)
        data.Ibus_ = current_injections.reshape(-1, 1)
        data.passive_branch_data.names = np.array(npa_data.passive_branch_data.names)
        data.passive_branch_data.virtual_tap_f = npa_data.passive_branch_data.virtual_tap_f
        data.passive_branch_data.virtual_tap_t = npa_data.passive_branch_data.virtual_tap_t
        data.passive_branch_data.original_idx = npa_data.passive_branch_data.original_idx

        data.bus_data.names = np.array(npa_data.bus_data.names)
        data.bus_data.original_idx = npa_data.bus_data.original_idx

        data.admittances_ = FakeAdmittances()
        data.admittances_.Ybus = adm.Ybus
        data.admittances_.Yf = adm.Yf
        data.admittances_.Yt = adm.Yt

        # The current wrapper does not expose NumericalCircuit::getLinearAdmittanceMatrices.
        # The compatibility layer keeps VeraGrid's expected fields populated from the available admittance matrices.
        data.Bbus_ = -adm.Ybus.imag
        data.Bf_ = -adm.Yf.imag

        data.Yseries_ = series_adm.Yseries
        data.Yshunt_ = series_adm.Yshunt

        data.B1_ = data.Bbus_
        data.B2_ = data.Bbus_

        data.Cf_ = conn.Cf
        data.Ct_ = conn.Ct

        data.bus_data.bus_types = tpes.types
        data.pq_ = tpes.pq
        data.pv_ = tpes.pv
        data.vd_ = tpes.vd
        data.pqpv_ = tpes.no_slack

        data.Qmax_bus_ = qmax_bus
        data.Qmin_bus_ = qmin_bus

        data_lst.append(data)

    return data_lst
