from __future__ import annotations

from pathlib import Path
import sys
from typing import Callable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import VeraGridEngine.api as vg
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations import PowerFlowOptions
from VeraGridEngine.enumerations import SolverType


def create_power_flow_options() -> PowerFlowOptions:
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        control_q=False,
    )


def build_bus_voltage_map(circuit: MultiCircuit, power_flow_results) -> dict[tuple[str, int], float]:
    value_map: dict[tuple[str, int], float] = {}
    repetitions_by_name: dict[str, int] = {}

    for bus_index, bus in enumerate(circuit.buses):
        bus_name = str(bus.name)
        repetition_index = repetitions_by_name.get(bus_name, 0)
        repetitions_by_name[bus_name] = repetition_index + 1
        value_map[(bus_name, repetition_index)] = float(np.abs(power_flow_results.voltage[bus_index]))

    return value_map


def build_branch_active_power_map(circuit: MultiCircuit, power_flow_results) -> dict[tuple[str, str, str, int], float]:
    value_map: dict[tuple[str, str, str, int], float] = {}
    repetitions_by_key: dict[tuple[str, str, str], int] = {}
    branches = circuit.get_branches(add_vsc=False, add_hvdc=False, add_switch=False)

    for branch_index, branch in enumerate(branches):
        ordered_endpoint_names = tuple(sorted((str(branch.bus_from.name), str(branch.bus_to.name))))
        base_key = (branch.device_type.value, ordered_endpoint_names[0], ordered_endpoint_names[1])
        repetition_index = repetitions_by_key.get(base_key, 0)
        repetitions_by_key[base_key] = repetition_index + 1
        value_map[(base_key[0], base_key[1], base_key[2], repetition_index)] = float(
            np.abs(power_flow_results.Sf.real[branch_index])
        )

    return value_map


def run_export_roundtrip_power_flow(
    import_file_name: str,
    export_file_name: str,
    export_func: Callable[[MultiCircuit, str], None],
    voltage_atol: float = 1e-4,
    flow_atol: float = 1e-2,
) -> tuple[int, int]:
    source_grid = vg.open_file(import_file_name)
    power_flow_options = create_power_flow_options()

    source_results = vg.power_flow(source_grid, power_flow_options)
    assert source_results.converged

    export_func(source_grid, export_file_name)

    roundtrip_grid = vg.open_file(export_file_name)
    roundtrip_results = vg.power_flow(roundtrip_grid, power_flow_options)
    assert roundtrip_results.converged

    source_voltage_map = build_bus_voltage_map(source_grid, source_results)
    roundtrip_voltage_map = build_bus_voltage_map(roundtrip_grid, roundtrip_results)
    source_branch_map = build_branch_active_power_map(source_grid, source_results)
    roundtrip_branch_map = build_branch_active_power_map(roundtrip_grid, roundtrip_results)

    assert set(source_voltage_map.keys()) == set(roundtrip_voltage_map.keys())
    assert set(source_branch_map.keys()) == set(roundtrip_branch_map.keys())

    for bus_key, source_voltage in source_voltage_map.items():
        roundtrip_voltage = roundtrip_voltage_map[bus_key]
        assert np.isclose(source_voltage, roundtrip_voltage, atol=voltage_atol), (
            f"Voltage mismatch at {bus_key}: {source_voltage} vs {roundtrip_voltage}"
        )

    for branch_key, source_flow in source_branch_map.items():
        roundtrip_flow = roundtrip_branch_map[branch_key]
        assert np.isclose(source_flow, roundtrip_flow, atol=flow_atol), (
            f"Branch flow mismatch at {branch_key}: {source_flow} vs {roundtrip_flow}"
        )

    return len(source_grid.buses), len(source_branch_map)
