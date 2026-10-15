# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Tests for the EMT power-flow injection operating-point contract."""

import numpy as np

from VeraGridEngine.Devices.Injections.battery import Battery
from VeraGridEngine.Devices.Injections.controllable_shunt import ControllableShunt
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.shunt import Shunt
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.types import INJECTION_DEVICE_TYPES
from VeraGridEngine.Simulations.EMT.injection_operating_point import (
    EmtInjectionOperatingPoint,
    build_balanced_emt_injection_operating_point,
)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.enumerations import BusMode


def _build_balanced_results(
        n_gen: int,
        n_batt: int = 0,
        n_shunt: int = 0,
) -> PowerFlowResults:
    """Build a minimal balanced PF result for operating-point unit tests.

    :param n_gen: Number of generator result rows.
    :param n_batt: Number of battery result rows.
    :param n_shunt: Number of shunt result rows.
    :return: Preallocated balanced power-flow result object.
    """
    generator_names: np.ndarray = np.empty(n_gen, dtype=object)
    battery_names: np.ndarray = np.empty(n_batt, dtype=object)
    shunt_names: np.ndarray = np.empty(n_shunt, dtype=object)
    generator_index: int = 0
    battery_index: int = 0
    shunt_index: int = 0

    while generator_index < n_gen:
        generator_names[generator_index] = f"G{generator_index + 1}"
        generator_index += 1

    while battery_index < n_batt:
        battery_names[battery_index] = f"B{battery_index + 1}"
        battery_index += 1

    while shunt_index < n_shunt:
        shunt_names[shunt_index] = f"SH{shunt_index + 1}"
        shunt_index += 1
    results: PowerFlowResults = PowerFlowResults(
        n=1,
        m=0,
        n_hvdc=0,
        n_vsc=0,
        n_gen=n_gen,
        n_batt=n_batt,
        n_sh=n_shunt,
        bus_names=np.array(["Slack"], dtype=object),
        branch_names=np.empty(0, dtype=object),
        hvdc_names=np.empty(0, dtype=object),
        vsc_names=np.empty(0, dtype=object),
        gen_names=generator_names,
        batt_names=battery_names,
        sh_names=shunt_names,
        bus_types=np.array([BusMode.Slack_tpe.value], dtype=int),
    )
    results.voltage[0] = 1.0 + 0.0j
    return results


def test_balanced_operating_point_uses_pf_device_dispatch_instead_of_snom() -> None:
    """Verify that parallel slack generators preserve their PF-owned dispatch.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    slack_bus: Bus = Bus(name="Slack", is_slack=True)
    generator_1: Generator = Generator(name="G1", Snom=1.5)
    generator_2: Generator = Generator(name="G2", Snom=4.5)
    grid.add_bus(slack_bus)
    grid.add_generator(bus=slack_bus, api_obj=generator_1)
    grid.add_generator(bus=slack_bus, api_obj=generator_2)

    results: PowerFlowResults = _build_balanced_results(n_gen=2)
    results.gen_p[:] = np.array([40.0, 40.0], dtype=float)
    results.gen_q[:] = np.array([10.0, 10.0], dtype=float)
    injection_devices: list[INJECTION_DEVICE_TYPES] = list(grid.get_injection_devices_iter())
    operating_point: EmtInjectionOperatingPoint = build_balanced_emt_injection_operating_point(
        grid=grid,
        power_flow_results=results,
        bus_dict=dict(((slack_bus, 0),)),
        injection_devices=injection_devices,
    )

    generator_1_power: complex = complex(np.sum(operating_point.get_ac_seed(0)))
    generator_2_power: complex = complex(np.sum(operating_point.get_ac_seed(1)))
    assert np.isclose(generator_1_power, complex(0.4, 0.1))
    assert np.isclose(generator_2_power, complex(0.4, 0.1))
    assert np.isclose(generator_2_power / generator_1_power, 1.0 + 0.0j)


def test_balanced_operating_point_excludes_inactive_generator() -> None:
    """Verify that an inactive parallel generator receives a zero seed.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    slack_bus: Bus = Bus(name="Slack", is_slack=True)
    active_generator: Generator = Generator(name="G1", active=True)
    inactive_generator: Generator = Generator(name="G2", active=False)
    grid.add_bus(slack_bus)
    grid.add_generator(bus=slack_bus, api_obj=active_generator)
    grid.add_generator(bus=slack_bus, api_obj=inactive_generator)

    results: PowerFlowResults = _build_balanced_results(n_gen=2)
    results.gen_p[:] = np.array([80.0, 0.0], dtype=float)
    results.gen_q[:] = np.array([20.0, 0.0], dtype=float)
    injection_devices: list[INJECTION_DEVICE_TYPES] = list(grid.get_injection_devices_iter())
    operating_point: EmtInjectionOperatingPoint = build_balanced_emt_injection_operating_point(
        grid=grid,
        power_flow_results=results,
        bus_dict=dict(((slack_bus, 0),)),
        injection_devices=injection_devices,
    )

    active_power: complex = complex(np.sum(operating_point.get_ac_seed(0)))
    inactive_power: complex = complex(np.sum(operating_point.get_ac_seed(1)))
    assert np.isclose(active_power, complex(0.8, 0.2))
    assert np.isclose(inactive_power, 0.0 + 0.0j)


def test_balanced_operating_point_keeps_multiple_ac_injections_independent() -> None:
    """Preserve every AC device contribution when several share one bus.

    The operating-point store must keep one row per device. In particular, the
    PF-owned generator and battery dispatch must not overwrite either the two
    scheduled loads or the voltage-dependent shunt contribution.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    bus: Bus = Bus(name="Shared AC bus", is_slack=True)
    generator: Generator = Generator(name="G1")
    battery: Battery = Battery(name="B1")
    load_1: Load = Load(name="Load 1", P=10.0, Q=3.0)
    load_2: Load = Load(name="Load 2", P=5.0, Q=1.0)
    shunt: Shunt = Shunt(name="SH1", G=2.0, B=4.0)
    grid.add_bus(bus)
    grid.add_generator(bus=bus, api_obj=generator)
    grid.add_battery(bus=bus, api_obj=battery)
    grid.add_load(bus=bus, api_obj=load_1)
    grid.add_load(bus=bus, api_obj=load_2)
    grid.add_shunt(bus=bus, api_obj=shunt)

    results: PowerFlowResults = _build_balanced_results(
        n_gen=1,
        n_batt=1,
        n_shunt=1,
    )
    results.gen_p[0] = 30.0
    results.gen_q[0] = 5.0
    results.battery_p[0] = 10.0
    results.battery_q[0] = -2.0
    injection_devices: list[INJECTION_DEVICE_TYPES] = list(grid.get_injection_devices_iter())
    operating_point: EmtInjectionOperatingPoint = build_balanced_emt_injection_operating_point(
        grid=grid,
        power_flow_results=results,
        bus_dict=dict(((bus, 0),)),
        injection_devices=injection_devices,
    )

    generator_power: complex = complex(np.sum(
        operating_point.get_ac_seed(injection_devices.index(generator))
    ))
    battery_power: complex = complex(np.sum(
        operating_point.get_ac_seed(injection_devices.index(battery))
    ))
    load_1_power: complex = complex(np.sum(
        operating_point.get_ac_seed(injection_devices.index(load_1))
    ))
    load_2_power: complex = complex(np.sum(
        operating_point.get_ac_seed(injection_devices.index(load_2))
    ))
    shunt_power: complex = complex(np.sum(
        operating_point.get_ac_seed(injection_devices.index(shunt))
    ))

    assert np.isclose(generator_power, complex(0.30, 0.05))
    assert np.isclose(battery_power, complex(0.10, -0.02))
    assert np.isclose(load_1_power, complex(-0.10, -0.03))
    assert np.isclose(load_2_power, complex(-0.05, -0.01))
    assert np.isclose(shunt_power, complex(-0.02, 0.04))
    assert np.isclose(
        generator_power + battery_power + load_1_power + load_2_power + shunt_power,
        complex(0.23, 0.03),
    )


def test_balanced_operating_point_keeps_multiple_dc_injections_independent() -> None:
    """Preserve distinct active-power seeds for loads on one DC bus.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    bus: Bus = Bus(name="Shared DC bus", is_dc=True)
    load_1: Load = Load(name="DC load 1", P=20.0, Q=0.0)
    load_2: Load = Load(name="DC load 2", P=7.5, Q=0.0)
    grid.add_bus(bus)
    grid.add_load(bus=bus, api_obj=load_1)
    grid.add_load(bus=bus, api_obj=load_2)

    results: PowerFlowResults = _build_balanced_results(n_gen=0)
    injection_devices: list[INJECTION_DEVICE_TYPES] = list(grid.get_injection_devices_iter())
    operating_point: EmtInjectionOperatingPoint = build_balanced_emt_injection_operating_point(
        grid=grid,
        power_flow_results=results,
        bus_dict=dict(((bus, 0),)),
        injection_devices=injection_devices,
    )

    load_1_index: int = injection_devices.index(load_1)
    load_2_index: int = injection_devices.index(load_2)
    assert operating_point.has_seed(load_1_index)
    assert operating_point.has_seed(load_2_index)
    assert np.isclose(operating_point.get_dc_seed(load_1_index), -0.20)
    assert np.isclose(operating_point.get_dc_seed(load_2_index), -0.075)
    assert np.isclose(
        operating_point.get_dc_seed(load_1_index) + operating_point.get_dc_seed(load_2_index),
        -0.275,
    )


def test_balanced_inductive_load_consumes_reactive_power() -> None:
    """Require positive static Load Q to become negative EMT injection.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    bus: Bus = Bus(name="Load bus")
    load: Load = Load(name="Inductive load", P=10.0, Q=20.0)
    grid.add_bus(bus)
    grid.add_load(bus=bus, api_obj=load)

    results: PowerFlowResults = _build_balanced_results(n_gen=0)
    injection_devices: list[INJECTION_DEVICE_TYPES] = list(grid.get_injection_devices_iter())
    load_index: int = injection_devices.index(load)
    operating_point: EmtInjectionOperatingPoint = build_balanced_emt_injection_operating_point(
        grid=grid,
        power_flow_results=results,
        bus_dict=dict(((bus, 0),)),
        injection_devices=injection_devices,
    )

    load_power: complex = complex(np.sum(operating_point.get_ac_seed(load_index)))
    assert np.isclose(load_power, complex(-0.10, -0.20))


def test_balanced_shunts_use_emt_injection_sign() -> None:
    """Require fixed and controllable shunts to store injected power.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    bus: Bus = Bus(name="Shunt bus")
    fixed_shunt: Shunt = Shunt(name="Fixed", G=10.0, B=20.0)
    controllable_shunt: ControllableShunt = ControllableShunt(
        name="Controlled",
        number_of_steps=0,
        G=5.0,
        B=-15.0,
    )
    grid.add_bus(bus)
    grid.add_shunt(bus=bus, api_obj=fixed_shunt)
    grid.add_controllable_shunt(bus=bus, api_obj=controllable_shunt)

    results: PowerFlowResults = _build_balanced_results(n_gen=0)
    injection_devices: list[INJECTION_DEVICE_TYPES] = list(grid.get_injection_devices_iter())
    fixed_index: int = injection_devices.index(fixed_shunt)
    controllable_index: int = injection_devices.index(controllable_shunt)
    operating_point: EmtInjectionOperatingPoint = build_balanced_emt_injection_operating_point(
        grid=grid,
        power_flow_results=results,
        bus_dict=dict(((bus, 0),)),
        injection_devices=injection_devices,
    )

    # Conductance consumes active power. Positive B is capacitive injection,
    # whereas negative B is inductive reactive consumption.
    fixed_power: complex = complex(np.sum(operating_point.get_ac_seed(fixed_index)))
    controllable_power: complex = complex(np.sum(operating_point.get_ac_seed(controllable_index)))
    assert np.isclose(fixed_power, complex(-0.10, 0.20))
    assert np.isclose(controllable_power, complex(-0.05, -0.15))


def test_three_phase_shunt_seed_uses_emt_injection_sign() -> None:
    """Require the PF3 shunt adapter to use the same sign as balanced PF.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    bus: Bus = Bus(name="Shunt bus")
    shunt: Shunt = Shunt(name="Fixed", G=30.0, B=60.0)
    grid.add_bus(bus)
    grid.add_shunt(bus=bus, api_obj=shunt)

    results_3ph: PowerFlowResults3Ph = PowerFlowResults3Ph(
        # PF3 receives the phase-expanded node count and reduces it internally
        # to one physical bus, so a one-bus case requires three nodes here.
        n=3,
        m=0,
        n_hvdc=0,
        n_vsc=0,
        n_gen=0,
        n_batt=0,
        n_sh=1,
        n_load=0,
        bus_names=np.array(["Shunt bus"], dtype=object),
        branch_names=np.empty(0, dtype=object),
        hvdc_names=np.empty(0, dtype=object),
        vsc_names=np.empty(0, dtype=object),
        gen_names=np.empty(0, dtype=object),
        batt_names=np.empty(0, dtype=object),
        sh_names=np.array(["Fixed"], dtype=object),
        load_names=np.empty(0, dtype=object),
        bus_types=np.array([BusMode.PQ_tpe.value], dtype=int),
    )
    results_3ph.voltage_N[0] = 0.0 + 0.0j
    results_3ph.voltage_A[0] = 1.0 + 0.0j
    results_3ph.voltage_B[0] = complex(np.exp(-2.0j * np.pi / 3.0))
    results_3ph.voltage_C[0] = complex(np.exp(2.0j * np.pi / 3.0))

    problem: EmtProblemDae = object.__new__(EmtProblemDae)
    problem.grid = grid
    problem.power_flow_results = None
    problem.power_flow_results_3ph = results_3ph
    phase_power: np.ndarray = problem._get_shunt_fixed_power_vector_3ph(
        shunt=shunt,
        bus_index=0,
    )

    assert np.isclose(phase_power[0], 0.0 + 0.0j)
    assert np.allclose(phase_power[1:4], np.full(3, complex(-0.10, 0.20)))


def test_three_phase_operating_point_splits_slack_residual_by_limits() -> None:
    """Verify PF3 bus power is allocated without requiring PF result changes.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    slack_bus: Bus = Bus(name="Slack", is_slack=True)
    generator_1: Generator = Generator(
        name="G1",
        Pmin=0.0,
        Pmax=100.0,
        Qmin=-100.0,
        Qmax=100.0,
    )
    generator_2: Generator = Generator(
        name="G2",
        Pmin=0.0,
        Pmax=300.0,
        Qmin=-300.0,
        Qmax=300.0,
    )
    grid.add_bus(slack_bus)
    grid.add_generator(bus=slack_bus, api_obj=generator_1)
    grid.add_generator(bus=slack_bus, api_obj=generator_2)

    results_3ph: PowerFlowResults3Ph = PowerFlowResults3Ph(
        n=3,
        m=0,
        n_hvdc=0,
        n_vsc=0,
        n_gen=2,
        n_batt=0,
        n_sh=0,
        n_load=0,
        bus_names=np.array(["Slack"], dtype=object),
        branch_names=np.empty(0, dtype=object),
        hvdc_names=np.empty(0, dtype=object),
        vsc_names=np.empty(0, dtype=object),
        gen_names=np.array(["G1", "G2"], dtype=object),
        batt_names=np.empty(0, dtype=object),
        sh_names=np.empty(0, dtype=object),
        load_names=np.empty(0, dtype=object),
        bus_types=np.array([BusMode.Slack_tpe.value], dtype=int),
    )
    results_3ph.voltage_N[0] = 0.0 + 0.0j
    results_3ph.voltage_A[0] = 1.0 + 0.0j
    results_3ph.voltage_B[0] = complex(np.exp(-2.0j * np.pi / 3.0))
    results_3ph.voltage_C[0] = complex(np.exp(2.0j * np.pi / 3.0))
    results_3ph.Sbus_A[0] = 40.0 + 0.0j
    results_3ph.Sbus_B[0] = 40.0 + 0.0j
    results_3ph.Sbus_C[0] = 40.0 + 0.0j

    problem: EmtProblemDae = object.__new__(EmtProblemDae)
    problem.grid = grid
    problem.power_flow_results = None
    problem.power_flow_results_3ph = results_3ph
    problem.logger = None
    injection_devices: list[INJECTION_DEVICE_TYPES] = list(grid.get_injection_devices_iter())
    operating_point: EmtInjectionOperatingPoint = problem._build_injection_seed_store_3ph(
        grid=grid,
        bus_dict=dict(((slack_bus, 0),)),
        injection_devices=injection_devices,
        sbase=grid.Sbase,
    )

    generator_1_power: np.ndarray = operating_point.get_ac_seed(0)
    generator_2_power: np.ndarray = operating_point.get_ac_seed(1)
    assert np.allclose(generator_1_power[1:4], np.full(3, 0.1 + 0.0j))
    assert np.allclose(generator_2_power[1:4], np.full(3, 0.3 + 0.0j))
    assert np.allclose(
        generator_1_power[1:4] + generator_2_power[1:4],
        np.full(3, 0.4 + 0.0j),
    )
