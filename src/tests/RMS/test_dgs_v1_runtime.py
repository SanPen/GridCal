# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from pathlib import Path

import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import (
    BackEulerImplicitIntegration,
)
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    DynamicSimulationMode,
    FileType,
    RmsInitializationMethod,
    VarPowerFlowReferenceType,
)

def test_dgs_v1_first_rms_step_is_finite_and_converged() -> None:
    """Run the tracked Nuactis V1 DGS model through one scalar RMS step.

    :return: None.
    """
    fixture_path: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "grids"
        / "DGS"
        / "hvdc_vsc_v1_complete_static_dynamic.dgs"
    )
    file_open: FileOpen = FileOpen(
        file_name=str(fixture_path),
        options=FileOpenOptions(
            file_type=FileType.DGS,
            dgs_use_dynamic_information=True,
            dgs_dynamic_simulation_mode=DynamicSimulationMode.RMS,
        ),
    )
    grid: MultiCircuit | None = file_open.open()
    assert grid is not None
    assert file_open.logger.error_count() == 0

    power_flow_results: PowerFlowResults = gce.power_flow(grid)
    assert power_flow_results.converged
    assert np.all(np.isfinite(power_flow_results.gen_p))

    # The DGS fixture carries PowerFactory's solved m:u/m:phiu snapshot. Verify
    # the canonical VeraGrid network reproduces every retained bus operating
    # point instead of merely reporting numerical convergence.
    expected_bus_rows: list[tuple[str, float, float]] = list([
        ("114", 0.99048188750840, -5.65981560946073),
        ("115", 1.00234679373328, 10.1782348594104),
        ("116", 1.0, 9.87960565184287e-13),
        ("117", 1.0000000000003, -5.70622377173452e-13),
        ("118", 0.99048074052676, -5.66085186519735),
        ("119", 1.00000000000004, 0.0),
        ("120", 0.99048074052676, -5.66085174592973),
        ("121", 1.00234782477042, 10.1791554965137),
        ("122", 0.99370024862455, 0.0),
        ("123", 1.00234782477042, 10.1791553824583),
    ])
    bus_index: int
    for bus_index in range(len(expected_bus_rows)):
        expected_bus_fid: str = expected_bus_rows[bus_index][0]
        expected_voltage_magnitude: float = expected_bus_rows[bus_index][1]
        expected_voltage_angle_degrees: float = expected_bus_rows[bus_index][2]
        expected_voltage: complex = complex(
            expected_voltage_magnitude
            * np.exp(1j * np.deg2rad(expected_voltage_angle_degrees))
        )
        assert str(grid.buses[bus_index].idtag) == expected_bus_fid
        assert power_flow_results.voltage[bus_index] == pytest.approx(
            expected_voltage,
            rel=1.0e-8,
            abs=1.0e-8,
        )

    # PowerFactory m:P/m:Q on ElmVscmono are injection-positive, whereas
    # VeraGrid terminal flows are positive from the bus into the converter.
    expected_vsc_rows: list[tuple[str, complex, float]] = list([
        ("126", complex(1021.08528227788, 5.68712721360498e-09), -1013.49419601605),
        ("127", complex(-999.99999999748, 1.03231627690548e-08), 1007.10943453886),
    ])
    vsc_devices: list[VSC] = grid.get_vsc()
    vsc_index: int
    for vsc_index in range(len(expected_vsc_rows)):
        expected_vsc_fid: str = expected_vsc_rows[vsc_index][0]
        expected_ac_terminal_power: complex = expected_vsc_rows[vsc_index][1]
        expected_dc_terminal_power: float = expected_vsc_rows[vsc_index][2]
        assert str(vsc_devices[vsc_index].idtag) == expected_vsc_fid
        assert power_flow_results.St_vsc[vsc_index] == pytest.approx(
            expected_ac_terminal_power,
            rel=1.0e-8,
            abs=1.0e-6,
        )
        assert (
            power_flow_results.Pfp_vsc[vsc_index]
            + power_flow_results.Pfn_vsc[vsc_index]
        ) == pytest.approx(
            expected_dc_terminal_power,
            rel=1.0e-8,
            abs=1.0e-6,
        )

    rms_options: RmsOptions = RmsOptions(
        time_step=0.001,
        simulation_time=0.001,
        tolerance=1.0e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=100,
        verbose=0,
    )
    problem: RmsProblemDae = RmsProblemDae(
        grid=grid,
        options=rms_options,
        pf_results=power_flow_results,
    )
    problem.set_events_group(
        rms_events_group=RmsEventsGroup(name="Nuactis V1 directed step")
    )
    initial_values: np.ndarray = problem.get_x0()
    initial_differentials: np.ndarray = np.zeros(
        problem.get_diff_var_number(),
        dtype=float,
    )

    # DC branch current seeds must use the solved DC voltage, not the absent AC
    # magnitude slot returned for a DC bus.
    branch_devices: list[BranchParent] = list(
        grid.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=True,
        )
    )
    branch_index: int
    for branch_index in range(len(branch_devices)):
        branch: BranchParent = branch_devices[branch_index]
        dc_current_var: Var | None = branch.rms_model.external_mapping.get(
            VarPowerFlowReferenceType.If_dc,
            None,
        )
        if dc_current_var is None:
            pass
        else:
            from_bus_index: int = grid.buses.index(branch.bus_from)
            expected_dc_current: float = float(
                np.real(power_flow_results.Sf[branch_index] / grid.Sbase)
                / np.abs(power_flow_results.voltage[from_bus_index])
            )
            assert initial_values[problem.uid2idx_vars[dc_current_var.uid]] == pytest.approx(
                expected_dc_current,
                rel=1.0e-10,
                abs=1.0e-10,
            )

    # Finite-impedance external sources expose redundant P/Q and Ir/Ii
    # coordinates. Their explicit point must satisfy S = V * conj(I).
    generator: Generator
    for generator in grid.generators:
        active_power_var: Var | None = generator.rms_model.external_mapping.get(
            VarPowerFlowReferenceType.P,
            None,
        )
        reactive_power_var: Var | None = generator.rms_model.external_mapping.get(
            VarPowerFlowReferenceType.Q,
            None,
        )
        current_real_var: Var | None = generator.rms_model.external_mapping.get(
            VarPowerFlowReferenceType.Ir,
            None,
        )
        current_imaginary_var: Var | None = generator.rms_model.external_mapping.get(
            VarPowerFlowReferenceType.Ii,
            None,
        )
        has_rectangular_source_contract: bool = (
            active_power_var is not None
            and reactive_power_var is not None
            and current_real_var is not None
            and current_imaginary_var is not None
        )
        if has_rectangular_source_contract:
            assert generator.bus is not None
            source_bus_index: int = grid.buses.index(generator.bus)
            source_voltage: complex = complex(
                power_flow_results.voltage[source_bus_index]
            )
            active_power_value: float = float(
                initial_values[problem.uid2idx_vars[active_power_var.uid]]
            )
            reactive_power_value: float = float(
                initial_values[problem.uid2idx_vars[reactive_power_var.uid]]
            )
            current_real_value: float = float(
                initial_values[problem.uid2idx_vars[current_real_var.uid]]
            )
            current_imaginary_value: float = float(
                initial_values[problem.uid2idx_vars[current_imaginary_var.uid]]
            )
            reconstructed_power: complex = (
                source_voltage
                * complex(current_real_value, -current_imaginary_value)
            )
            assert reconstructed_power.real == pytest.approx(
                active_power_value,
                rel=1.0e-10,
                abs=1.0e-10,
            )
            assert reconstructed_power.imag == pytest.approx(
                reactive_power_value,
                rel=1.0e-10,
                abs=1.0e-10,
            )
        else:
            pass
    assert np.all(np.isfinite(initial_values))
    assert np.all(np.isfinite(problem.get_j11(initial_values, initial_differentials, 0.001).data))
    assert np.all(np.isfinite(problem.get_j12(initial_values, initial_differentials, 0.001).data))
    assert np.all(np.isfinite(problem.get_j21(initial_values, initial_differentials, 0.001).data))
    assert np.all(np.isfinite(problem.get_j22(initial_values, initial_differentials, 0.001).data))

    solver: BackEulerImplicitIntegration = BackEulerImplicitIntegration(
        problem=problem,
        t0=0.0,
        t_end=rms_options.simulation_time,
        h=rms_options.time_step,
        max_iter=rms_options.max_iter,
        tolerance=rms_options.tolerance,
    )
    simulation_result: tuple[np.ndarray, np.ndarray, bool, bool] = solver.simulate()
    times: np.ndarray = simulation_result[0]
    values: np.ndarray = simulation_result[1]
    well_initialized: bool = simulation_result[2]
    converged: bool = simulation_result[3]

    assert well_initialized
    assert converged
    assert len(times) == 2
    assert np.all(np.isfinite(values))
