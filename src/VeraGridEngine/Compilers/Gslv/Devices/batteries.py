# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Dict, TYPE_CHECKING

from VeraGridEngine.Compilers.Gslv.activation import (
    battery_dispatch_mode_dict, build_status_dict, generator_control_mode_dict, pg,
)
from VeraGridEngine.Compilers.Gslv.common import fill_profile, fill_profile_with_array, set_generator_associations
from VeraGridEngine.Devices.Aggregation.facility import Facility
from VeraGridEngine.Devices.Aggregation.market_unit import MarketUnit
from VeraGridEngine.Devices.Associations.emission_gas import EmissionGas
from VeraGridEngine.Devices.Associations.fuel import Fuel
from VeraGridEngine.Devices.Associations.technology import Technology
from VeraGridEngine.Devices.Injections.battery import Battery
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.basic_structures import IntVec

if TYPE_CHECKING:
    from VeraGridEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults


def convert_battery(k: int,
                    elm: Battery,
                    bus_dict: Dict[str, "pg.Bus"],
                    facility_dict: Dict[Facility, "pg.Facility"],
                    market_unit_dict: Dict[MarketUnit, "pg.MarketUnit"],
                    technology_dict: Dict[Technology, "pg.Technology"],
                    fuel_dict: Dict[Fuel, "pg.Fuel"],
                    emission_gas_dict: Dict[EmissionGas, "pg.EmissionGas"],
                    n_time: int,
                    use_time_series: bool,
                    time_indices: IntVec | None = None,
                    opf_results: OptimalPowerFlowResults | None = None,
                    add_three_phase_data: bool = False) -> "pg.Battery":
    """
    Convert one VeraGrid battery into one GSLV battery.

    :param k: Battery index.
    :param elm: VeraGrid battery.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param facility_dict: VeraGrid-to-GSLV facility lookup.
    :param market_unit_dict: VeraGrid-to-GSLV market-unit lookup.
    :param technology_dict: VeraGrid-to-GSLV technology lookup.
    :param fuel_dict: VeraGrid-to-GSLV fuel lookup.
    :param emission_gas_dict: VeraGrid-to-GSLV emission gas lookup.
    :param n_time: Number of exported time steps.
    :param use_time_series: Whether the export is time-series based.
    :param time_indices: Optional time-series selection.
    :param opf_results: Optional OPF results.
    :param add_three_phase_data: Export sequence impedances needed by three-phase studies.
    :return: GSLV battery.
    """
    battery_r0: float
    battery_x0: float
    battery_r2: float
    battery_x2: float

    if add_three_phase_data:
        battery_r0 = float(elm.R0)
        battery_x0 = float(elm.X0)
        battery_r2 = float(elm.R2)
        battery_x2 = float(elm.X2)
    else:
        battery_r0 = 1e-20
        battery_x0 = 1e-20
        battery_r2 = 1e-20
        battery_x2 = 1e-20

    gen = pg.Battery(
        nt=n_time,
        bus=None if elm.bus is None else bus_dict[elm.bus.idtag],
        name=elm.name,
        idtag=elm.idtag,
        code=elm.code,
        P=elm.P,
        Q=0.0,
        power_factor=elm.Pf,
        vset=elm.Vset,
        active=elm.active,
        max_soc=elm.max_soc,
        min_soc=elm.min_soc,
        Qmin=elm.Qmin,
        Qmax=elm.Qmax,
        Pmin=elm.Pmin,
        Pmax=elm.Pmax,
        Snom=elm.Snom,
        Enom=elm.Enom,
        Cost=elm.Cost,
        Sbase=elm.Sbase,
        enabled_dispatch=elm.enabled_dispatch,
        mttf=elm.mttf,
        mttr=elm.mttr,
        charge_efficiency=elm.charge_efficiency,
        discharge_efficiency=elm.discharge_efficiency,
        is_controlled=elm.is_controlled,
        soc=elm.soc,
        charge_per_cycle=elm.charge_per_cycle,
        discharge_per_cycle=elm.discharge_per_cycle,
        r1=elm.R1,
        x1=elm.X1,
        r0=battery_r0,
        x0=battery_x0,
        r2=battery_r2,
        x2=battery_x2,
        capex=elm.capex,
        opex=elm.opex,
        srap_enabled=elm.srap_enabled,
        build_status=build_status_dict[elm.build_status],
        control_mode=generator_control_mode_dict[elm.control_mode],
        dispatch_mode=battery_dispatch_mode_dict[elm.dispatch_mode],
    )
    fill_profile(gen.dispatch_mode, elm.dispatch_mode_prof, use_time_series, time_indices, n_time, elm.dispatch_mode)
    gen.min_soc_charge = elm.min_soc_charge
    gen.startup_cost = elm.startup_cost
    gen.shutdown_cost = elm.shutdown_cost
    gen.min_time_up = elm.min_time_up
    gen.min_time_down = elm.min_time_down
    gen.ramp_up = elm.ramp_up
    gen.ramp_down = elm.ramp_down

    if elm.control_bus is None:
        pass
    else:
        gen.set_control_bus_val(bus_dict[elm.control_bus.idtag])

    set_generator_associations(
        gslv_elm=gen,
        elm=elm,
        facility_dict=facility_dict,
        technology_dict=technology_dict,
        fuel_dict=fuel_dict,
        emission_gas_dict=emission_gas_dict,
    )

    fill_profile(gen.active, elm.active_prof, use_time_series, time_indices, n_time, elm.active)
    fill_profile(gen.srap_enabled, elm.srap_enabled_prof, use_time_series, time_indices, n_time, elm.srap_enabled)

    gen.enabled_dispatch = fill_profile(
        gen.enabled_dispatch,
        elm.enabled_dispatch_prof,
        use_time_series,
        time_indices,
        n_time,
        elm.enabled_dispatch,
    )

    gen.must_run = fill_profile(gen.must_run, elm.must_run_prof, use_time_series, time_indices, n_time, elm.must_run)

    if opf_results is None:
        fill_profile(gen.P, elm.P_prof, use_time_series, time_indices, n_time, elm.P)
    else:
        fill_profile_with_array(
            gslv_profile=gen.P,
            arr=opf_results.battery_power[:, k],
            use_time_series=use_time_series,
            time_indices=time_indices,
            n_time=n_time,
            default_val=elm.P,
        )

    # The pre-solve NumericalCircuit keeps battery reactive injection at zero; Q is solved through controls/limits.
    gen.Q.fill(0.0)
    fill_profile(gen.power_factor, elm.Pf_prof, use_time_series, time_indices, n_time, elm.Pf)

    gen.Pmin = fill_profile(gen.Pmin, elm.Pmin_prof, use_time_series, time_indices, n_time, elm.Pmin)
    gen.Pmax = fill_profile(gen.Pmax, elm.Pmax_prof, use_time_series, time_indices, n_time, elm.Pmax)
    gen.qmin_set = fill_profile(gen.qmin_set, elm.Qmin_prof, use_time_series, time_indices, n_time, elm.Qmin)
    gen.qmax_set = fill_profile(gen.qmax_set, elm.Qmax_prof, use_time_series, time_indices, n_time, elm.Qmax)

    fill_profile(gen.Vset, elm.Vset_prof, use_time_series, time_indices, n_time, elm.Vset)
    fill_profile(gen.cost, elm.Cost_prof, use_time_series, time_indices, n_time, elm.Cost)
    fill_profile(gen.Cost0, elm.Cost0_prof, use_time_series, time_indices, n_time, elm.Cost0)
    fill_profile(gen.Cost2, elm.Cost2_prof, use_time_series, time_indices, n_time, elm.Cost2)

    return gen


def add_battery_data(circuit: MultiCircuit,
                     gslv_grid: "pg.MultiCircuit",
                     bus_dict: Dict[str, "pg.Bus"],
                     facility_dict: Dict[Facility, "pg.Facility"],
                     market_unit_dict: Dict[MarketUnit, "pg.MarketUnit"],
                     technology_dict: Dict[Technology, "pg.Technology"],
                     fuel_dict: Dict[Fuel, "pg.Fuel"],
                     emission_gas_dict: Dict[EmissionGas, "pg.EmissionGas"],
                     time_series: bool,
                     n_time: int = 1,
                     time_indices: IntVec | None = None,
                     opf_results: OptimalPowerFlowResults | None = None,
                     add_three_phase_data: bool = False) -> None:
    """
    Add every VeraGrid battery to the target GSLV grid.

    :param circuit: VeraGrid circuit.
    :param gslv_grid: GSLV circuit.
    :param bus_dict: Bus lookup by VeraGrid id tag.
    :param facility_dict: VeraGrid-to-GSLV facility lookup.
    :param market_unit_dict: VeraGrid-to-GSLV market-unit lookup.
    :param technology_dict: VeraGrid-to-GSLV technology lookup.
    :param fuel_dict: VeraGrid-to-GSLV fuel lookup.
    :param emission_gas_dict: VeraGrid-to-GSLV emission gas lookup.
    :param time_series: Whether the export is time-series based.
    :param n_time: Number of exported time steps.
    :param time_indices: Optional time-series selection.
    :param opf_results: Optional OPF results.
    :param add_three_phase_data: Export sequence impedances needed by three-phase studies.
    :return: None.
    """
    devices = circuit.get_batteries()

    for k, elm in enumerate(devices):
        batt = convert_battery(
            k=k,
            elm=elm,
            bus_dict=bus_dict,
            facility_dict=facility_dict,
            market_unit_dict=market_unit_dict,
            technology_dict=technology_dict,
            fuel_dict=fuel_dict,
            emission_gas_dict=emission_gas_dict,
            n_time=n_time,
            use_time_series=time_series,
            time_indices=time_indices,
            opf_results=opf_results,
            add_three_phase_data=add_three_phase_data,
        )
        gslv_grid.add_battery(batt)
