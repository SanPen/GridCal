from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import textwrap
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(BENCHMARKS_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import numpy as np

import VeraGridEngine.api as vg
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.file_open import FileOpenOptions

from power_flow_roundtrip import (
    build_branch_active_power_map,
    build_bus_voltage_map,
    create_power_flow_options,
)


def open_grid(file_name: str | list[str], options: FileOpenOptions | None = None) -> MultiCircuit:
    if options is None:
        return vg.open_file(file_name)
    return vg.FileOpen(file_name=file_name, options=options).open()


def compare_power_flow(
    left_file_name: str | list[str],
    right_file_name: str | list[str],
    left_options: FileOpenOptions | None = None,
    right_options: FileOpenOptions | None = None,
    voltage_atol: float = 1e-4,
    flow_atol: float = 1e-2,
    power_flow_options=None,
) -> dict[str, int]:
    if power_flow_options is None:
        power_flow_options = create_power_flow_options()

    left_grid = open_grid(left_file_name, left_options)
    right_grid = open_grid(right_file_name, right_options)

    left_results = vg.power_flow(left_grid, power_flow_options)
    right_results = vg.power_flow(right_grid, power_flow_options)
    assert left_results.converged
    assert right_results.converged

    left_voltage_map = build_bus_voltage_map(left_grid, left_results)
    right_voltage_map = build_bus_voltage_map(right_grid, right_results)
    left_branch_map = build_branch_active_power_map(left_grid, left_results)
    right_branch_map = build_branch_active_power_map(right_grid, right_results)

    assert set(left_voltage_map.keys()) == set(right_voltage_map.keys())
    assert set(left_branch_map.keys()) == set(right_branch_map.keys())

    for bus_key, left_voltage in left_voltage_map.items():
        right_voltage = right_voltage_map[bus_key]
        assert np.isclose(left_voltage, right_voltage, atol=voltage_atol), (
            f"Voltage mismatch at {bus_key}: {left_voltage} vs {right_voltage}"
        )

    for branch_key, left_flow in left_branch_map.items():
        right_flow = right_branch_map[branch_key]
        assert np.isclose(left_flow, right_flow, atol=flow_atol), (
            f"Branch flow mismatch at {branch_key}: {left_flow} vs {right_flow}"
        )

    return {
        "buses": len(left_grid.buses),
        "branches": len(left_branch_map),
    }


def run_python_snippet(
    code: str,
    pythonpath_entries: list[Path],
    args: list[str],
) -> None:
    env = os.environ.copy()
    pythonpath = [str(path) for path in pythonpath_entries]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)

    subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code), *args],
        check=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


def merge_zip_files(output_path: Path, input_paths: list[Path]) -> None:
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as output_zip:
        seen_names: set[str] = set()
        for input_path in input_paths:
            with zipfile.ZipFile(input_path, "r") as input_zip:
                for zip_info in input_zip.infolist():
                    if zip_info.is_dir() or zip_info.filename in seen_names:
                        continue
                    seen_names.add(zip_info.filename)
                    output_zip.writestr(zip_info.filename, input_zip.read(zip_info.filename))
