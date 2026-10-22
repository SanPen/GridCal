# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from pathlib import Path
import pytest
import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import (
    project_initial_algebraic_state,
)
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    DynamicSimulationMode,
    FileType,
    ParamPowerFlowReferenceType,
    RmsInitializationMethod,
    SolverType,
)

def test_dgs_v2_first_rms_step_is_finite_and_converged() -> None:
    """Run the tracked Nuactis V2 DGS model through one scalar RMS step.

    :return: None.
    """
    # Import the portable V2 fixture through the same production route used by
    # scripting and the GUI so both consumers receive one canonical circuit.
    fixture_path: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "grids"
        / "DGS"
        / "hvdc_vsc_v2_complete_static_dynamic.dgs"
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

    # Fail closed on the known V2 import contract before numerical execution.
    assert grid is not None
    assert file_open.logger.error_count() == 0
    assert file_open.logger.warning_count() == 0
    assert len(grid.buses) == 10
    assert len(grid.get_vsc()) == 2
    vsc: VSC
    for vsc in grid.get_vsc():
        assert vsc.dc_link_capacitance_uf == 76.80000305175781
    else:
        pass

    # Reconstruct the exact imported operating point before RMS initialization.
    power_flow_options: PowerFlowOptions = PowerFlowOptions(
        use_stored_guess=False,
        tolerance=1.0e-9,
        max_iter=100,
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
    )
    power_flow_results: PowerFlowResults = gce.power_flow(
        grid=grid,
        options=power_flow_options,
    )
    assert power_flow_results.converged
    assert np.all(np.isfinite(power_flow_results.voltage))
    expected_voltage_magnitudes: np.ndarray = np.array(
        [
            0.99305449497315,
            0.97827079645434,
            1.00000000000085,
            0.99999999999954,
            0.99999999999993,
            0.99305374736455,
            0.98734944091317,
            0.97826973988012,
            0.98438149730841,
            1.00613187974404,
        ],
        dtype=float,
    )
    expected_voltage_angles: np.ndarray = np.deg2rad(
        np.array(
            [
                5.43962357467693,
                -10.481835935501,
                3.51384198717049e-11,
                -7.25762234448074e-12,
                0.0,
                5.44061914175967,
                11.5847546649269,
                -10.4828023281179,
                -16.8707878220013,
                0.0,
            ],
            dtype=float,
        )
    )
    expected_voltage: np.ndarray = expected_voltage_magnitudes * np.exp(
        1j * expected_voltage_angles
    )
    assert np.max(np.abs(power_flow_results.voltage - expected_voltage)) <= 1.0e-6

    # Build explicit initialization at t=0 and advance one Backward-Euler step.
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
    dc_cable: DcLine = grid.dc_lines[0]
    dynamic_values: tuple[float, float] | None = (
        dc_cable.get_applied_dynamic_values_pu_seconds(Sbase=float(grid.Sbase))
    )
    assert dynamic_values is not None
    # Inductance is owned by the model's child event declaration; physical
    # cable data does not override this established RMS model parameter.
    inductance_parameter: Var | None = None
    inductance_owner: Block | None = None
    inductance_declaration_count: int = 0
    model_block: Block
    event_parameter: Var
    static_parameter: Var
    for model_block in dc_cable.rms_model.get_all_blocks():
        # No root or sibling may introduce a competing physical/static L.
        assert model_block.api_obj_mapping.get(
            ParamPowerFlowReferenceType.dc_line_l_pu_seconds,
            None,
        ) is None
        for static_parameter in model_block.parameters:
            assert static_parameter.name != "l"
        for event_parameter in model_block.event_dict:
            if event_parameter.name == "l":
                inductance_parameter = event_parameter
                inductance_owner = model_block
                inductance_declaration_count += 1
            else:
                pass
    assert inductance_parameter is not None
    assert inductance_owner is not None
    assert inductance_owner is not dc_cable.rms_model
    assert inductance_declaration_count == 1
    assert problem.event_params_init_dict[inductance_parameter.uid] == 0.05
    assert len(problem._external_time_uids) == 3
    problem.set_events_group(
        rms_events_group=RmsEventsGroup(name="Nuactis V2 directed step")
    )
    external_time_index: int = problem._uid2idx_event_params[
        problem._external_time_parameter.uid
    ]
    external_time_compiler_name: str = problem._compiler_names_dict[
        problem._external_time_parameter.uid
    ]
    external_time_uid: int
    for external_time_uid in problem._external_time_uids:
        assert problem._compiler_names_dict[external_time_uid] == (
            external_time_compiler_name
        )
    else:
        pass
    initial_values: np.ndarray = problem.get_x0()
    initial_differentials: np.ndarray = np.zeros(
        problem.get_diff_var_number(),
        dtype=float,
    )
    assert np.all(np.isfinite(initial_values))
    projected_values: np.ndarray
    projection_converged: bool
    projection_residual: float
    projected_values, projection_converged, projection_residual = (
        project_initial_algebraic_state(
            problem=problem,
            initial_values=initial_values,
            differential_values=initial_differentials,
            tolerance=rms_options.tolerance,
            max_iter=rms_options.max_iter,
        )
    )
    projected_residuals: np.ndarray = problem.rhs_algebraic(
        projected_values,
        initial_differentials,
    )
    worst_projection_index: int = int(np.argmax(np.abs(projected_residuals)))
    projection_diagnostics: list[tuple[int, float]] = list()
    diagnostic_index: int
    for diagnostic_index in np.argsort(np.abs(projected_residuals))[-12:]:
        projection_diagnostics.append(
            (
                int(diagnostic_index),
                float(projected_residuals[diagnostic_index]),
            )
        )
    assert projection_converged, (
        projection_residual,
        worst_projection_index,
        projection_diagnostics,
    )
    time_step_parameters: list[tuple[str, float]] = list()
    parameter_index: int
    parameter_var: Var
    for parameter_index, parameter_var in enumerate(problem._variable_parameters):
        if parameter_var.name.endswith("T_step"):
            time_step_parameters.append(
                (
                    parameter_var.name,
                    float(problem._variable_parameters_values[parameter_index]),
                )
            )
        else:
            pass
    assert len(time_step_parameters) == 4
    assert [parameter_value for _, parameter_value in time_step_parameters] == [
        2.0,
        1.0,
        2.0,
        2.0,
    ]
    assert np.all(
        np.isfinite(
            problem.get_j11(initial_values, initial_differentials, 0.001).data
        )
    )

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
    assert float(problem._variable_parameters_values[external_time_index]) == 0.001
