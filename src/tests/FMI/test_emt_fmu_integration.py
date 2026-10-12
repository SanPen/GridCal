from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.fmu.CosimulationInterface.build import host_build_capable
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.IO.fmu.Elements.bindings import FmuRefBinding
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuDeviceAttachmentRequest,
    FmuDeviceDomain,
    FmuReferenceValue,
    attach_fmu_to_device,
)
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    FmiVersion,
    VarPowerFlowReferenceType,
)
from tests.FMI.fmi_test_support import (
    build_test_emt_grid,
    build_test_power_flow_options,
    execute_test_emt_fmu_case,
    export_test_emt_cs_fmu,
)


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_emt_fmu_co_simulation_runs_end_to_end(tmp_path: Path) -> None:
    """Compare FMI 1, FMI 2, and FMI 3 CS through the EMT product path.

    :param tmp_path: Isolated FMU and native staging directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    versions: tuple[FmiVersion, ...] = (
        FmiVersion.FMI_1_0,
        FmiVersion.FMI_2_0,
        FmiVersion.FMI_3_0,
    )
    fmi_one_time: np.ndarray | None = None
    fmi_one_currents: np.ndarray | None = None
    fmi_two_time: np.ndarray | None = None
    fmi_two_currents: np.ndarray | None = None
    fmi_three_time: np.ndarray | None = None
    fmi_three_currents: np.ndarray | None = None
    fmi_version: FmiVersion
    for fmi_version in versions:
        run_directory: Path = tmp_path / fmi_version.name.lower()
        driver: EmtSimulationDriver
        load: Load
        fmu_path: Path
        # The time proxy divides current by the 0.01 ramp slope. Resolve each
        # 5 us EMT sample below that scale before checking the 100 us FMU step.
        driver, load, fmu_path = execute_test_emt_fmu_case(
            output_dir=run_directory,
            mode=FmuInterfaceMode.CO_SIMULATION,
            fmi_version=fmi_version,
            emt_tolerance=1.0e-9,
        )

        if driver.results is None:
            raise AssertionError(
                f"The EMT {fmi_version.value} Co-Simulation case published no results"
            )
        else:
            results: EmtResults = driver.results
        available_group_indices: np.ndarray = np.flatnonzero(
            results.has_event_group_results
        )
        assert available_group_indices.size == 1
        group_index: int = int(available_group_indices[0])
        assert bool(results.well_initialized[group_index])
        assert bool(results.converged[group_index])

        time_seconds: np.ndarray = np.array(
            [float(time_value.value) * 1.0e-9 for time_value in results.time_array],
            dtype=float,
        )
        assert time_seconds[-1] == pytest.approx(1.0e-3)
        i_a_var: Var = load.emt_model.external_mapping[
            VarPowerFlowReferenceType.i_A
        ]
        i_b_var: Var = load.emt_model.external_mapping[
            VarPowerFlowReferenceType.i_B
        ]
        i_c_var: Var = load.emt_model.external_mapping[
            VarPowerFlowReferenceType.i_C
        ]
        currents: np.ndarray = np.column_stack((
            results.values[:, results.uid2idx[i_a_var.uid], group_index],
            results.values[:, results.uid2idx[i_b_var.uid], group_index],
            results.values[:, results.uid2idx[i_c_var.uid], group_index],
        ))
        assert bool(np.all(np.isfinite(currents)))

        # Recover the FMU source time from its phase-A ramp. The worker may
        # retain a value during initialization, but it must never lead the EMT
        # clock, lag it by more than one communication step, or jump farther.
        source_progress: np.ndarray = -currents[:, 0] / 0.01
        source_progress_steps: np.ndarray = np.diff(source_progress)
        progress_lag: np.ndarray = time_seconds - source_progress
        assert source_progress[0] == pytest.approx(0.0, abs=1.0e-12)
        assert bool(np.all(source_progress_steps >= -1.0e-12))
        assert bool(np.all(source_progress <= time_seconds + 1.0e-12))
        assert bool(np.all(progress_lag <= 1.0e-4 + 1.0e-12))
        assert bool(np.all(source_progress_steps <= 1.0e-4 + 1.0e-12))
        assert source_progress[-1] == pytest.approx(1.0e-3, abs=1.0e-12)

        # The remaining phases are direct fixture outputs, so their exact
        # coefficients validate sign and scale independently of outer time.
        np.testing.assert_allclose(
            currents[:, 1],
            0.005 * source_progress,
            rtol=0.0,
            atol=1.0e-12,
        )
        np.testing.assert_allclose(
            currents[:, 2],
            0.005 * source_progress,
            rtol=0.0,
            atol=1.0e-12,
        )
        if fmi_version == FmiVersion.FMI_1_0:
            fmi_one_time = time_seconds
            fmi_one_currents = currents
        else:
            if fmi_version == FmiVersion.FMI_2_0:
                fmi_two_time = time_seconds
                fmi_two_currents = currents
            else:
                if fmi_version == FmiVersion.FMI_3_0:
                    fmi_three_time = time_seconds
                    fmi_three_currents = currents
                else:
                    raise AssertionError(
                        f"Unexpected FMI version: {fmi_version.value}"
                    )
        assert fmu_path.exists()
        assert tuple(run_directory.glob("veragrid_fmu_stage_*")) == tuple()

    if (
        fmi_one_time is not None
        and fmi_one_currents is not None
        and fmi_two_time is not None
        and fmi_two_currents is not None
        and fmi_three_time is not None
        and fmi_three_currents is not None
    ):
        assert bool(np.array_equal(fmi_one_time, fmi_two_time))
        np.testing.assert_allclose(
            fmi_one_currents,
            fmi_two_currents,
            rtol=0.0,
            atol=1.0e-12,
        )
        assert bool(np.array_equal(fmi_two_time, fmi_three_time))
        np.testing.assert_allclose(
            fmi_two_currents,
            fmi_three_currents,
            rtol=1.0e-5,
            atol=2.0e-7,
        )
    else:
        raise AssertionError("The EMT CS version matrix is incomplete")


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
@pytest.mark.parametrize("solver_tpe", tuple(EmtSolverTypes))
def test_emt_fmu_model_exchange_runs_end_to_end(
    tmp_path: Path,
    solver_tpe: EmtSolverTypes,
) -> None:
    """Compare FMI 1, FMI 2, and FMI 3 ME through one EMT solver backend.

    :param tmp_path: Isolated FMU and native staging directory supplied by pytest.
    :param solver_tpe: EMT Jacobian backend under test.
    :return: None.
    """

    pytest.importorskip("fmpy")
    versions: tuple[FmiVersion, ...] = (
        FmiVersion.FMI_1_0,
        FmiVersion.FMI_2_0,
        FmiVersion.FMI_3_0,
    )
    fmi_one_time: np.ndarray | None = None
    fmi_one_currents: np.ndarray | None = None
    fmi_two_time: np.ndarray | None = None
    fmi_two_currents: np.ndarray | None = None
    fmi_three_time: np.ndarray | None = None
    fmi_three_currents: np.ndarray | None = None
    fmi_version: FmiVersion
    for fmi_version in versions:
        run_directory: Path = tmp_path / fmi_version.name.lower()
        driver: EmtSimulationDriver
        load: Load
        fmu_path: Path
        driver, load, fmu_path = execute_test_emt_fmu_case(
            output_dir=run_directory,
            mode=FmuInterfaceMode.MODEL_EXCHANGE,
            solver_tpe=solver_tpe,
            fmi_version=fmi_version,
        )

        if driver.results is None:
            raise AssertionError(
                f"The EMT {fmi_version.value} Model Exchange case published no results"
            )
        else:
            results: EmtResults = driver.results
        available_group_indices: np.ndarray = np.flatnonzero(
            results.has_event_group_results
        )
        assert available_group_indices.size == 1
        group_index: int = int(available_group_indices[0])
        assert bool(results.well_initialized[group_index])
        assert bool(results.converged[group_index])

        time_seconds: np.ndarray = np.array(
            [float(time_value.value) * 1.0e-9 for time_value in results.time_array],
            dtype=float,
        )
        assert time_seconds[-1] == pytest.approx(1.0e-3)
        i_a_var: Var = load.emt_model.external_mapping[
            VarPowerFlowReferenceType.i_A
        ]
        i_b_var: Var = load.emt_model.external_mapping[
            VarPowerFlowReferenceType.i_B
        ]
        i_c_var: Var = load.emt_model.external_mapping[
            VarPowerFlowReferenceType.i_C
        ]
        v_a_var: Var = load.bus.emt_model.external_mapping[
            VarPowerFlowReferenceType.v_A
        ]
        i_a_values: np.ndarray = results.values[
            :, results.uid2idx[i_a_var.uid], group_index
        ]
        i_b_values: np.ndarray = results.values[
            :, results.uid2idx[i_b_var.uid], group_index
        ]
        i_c_values: np.ndarray = results.values[
            :, results.uid2idx[i_c_var.uid], group_index
        ]
        v_a_values: np.ndarray = results.values[
            :, results.uid2idx[v_a_var.uid], group_index
        ]
        currents: np.ndarray = np.column_stack((
            i_a_values,
            i_b_values,
            i_c_values,
        ))
        assert bool(np.all(np.isfinite(currents)))
        assert bool(np.all(np.isfinite(v_a_values)))
        np.testing.assert_allclose(
            i_b_values,
            -0.5 * i_a_values,
            rtol=1.0e-5,
            atol=2.0e-6,
        )
        np.testing.assert_allclose(
            i_c_values,
            -0.5 * i_a_values,
            rtol=1.0e-5,
            atol=2.0e-6,
        )
        # Normalize the Backward Euler current increments by their retained
        # time steps so the small phase-A input contribution is observable.
        time_steps: np.ndarray = np.diff(time_seconds)
        actual_rate: np.ndarray = np.diff(i_a_values) / time_steps
        expected_rate: np.ndarray = 1.0 + v_a_values[:-1]
        active_step_indices: np.ndarray = np.flatnonzero(
            np.abs(actual_rate) >= 0.5
        )
        assert active_step_indices.size > 0
        first_active_index: int = int(active_step_indices[0])
        assert first_active_index <= 1
        if first_active_index > 0:
            inactive_prefix: np.ndarray = actual_rate[:first_active_index]
            assert bool(np.all(np.abs(inactive_prefix) <= 2.0e-5))
        else:
            pass
        np.testing.assert_allclose(
            actual_rate[first_active_index:],
            expected_rate[first_active_index:],
            rtol=1.0e-8,
            atol=2.0e-5,
        )

        # Require enough canonical bus-voltage excitation that an FMU which
        # silently evaluates x'=1 would exceed the absolute acceptance margin.
        maximum_voltage_excitation: float = float(
            np.max(np.abs(v_a_values[:-1]))
        )
        omission_counterexample_error: float = float(
            np.max(np.abs(expected_rate - 1.0))
        )
        assert maximum_voltage_excitation >= 5.0e-4
        assert omission_counterexample_error > 2.0e-5

        attached_block: Block = load.emt_model
        copied_block: Block = attached_block.copy()
        candidate_blocks: tuple[Block, Block] = (attached_block, copied_block)
        candidate_block: Block
        reference: VarPowerFlowReferenceType
        for candidate_block in candidate_blocks:
            for reference in (
                VarPowerFlowReferenceType.v_A,
                VarPowerFlowReferenceType.v_B,
                VarPowerFlowReferenceType.v_C,
            ):
                input_var: Var | None = candidate_block.external_mapping.get(
                    reference,
                    None,
                )
                matching_input_vars: list[Var] = list(
                    candidate_var
                    for candidate_var in candidate_block.in_vars
                    if candidate_var.ref == reference
                )
                assert input_var is not None
                assert len(matching_input_vars) == 1
                assert input_var is matching_input_vars[0]
                assert input_var.ref == reference

        if fmi_version == FmiVersion.FMI_1_0:
            fmi_one_time = time_seconds
            fmi_one_currents = currents
        else:
            if fmi_version == FmiVersion.FMI_2_0:
                fmi_two_time = time_seconds
                fmi_two_currents = currents
            else:
                if fmi_version == FmiVersion.FMI_3_0:
                    fmi_three_time = time_seconds
                    fmi_three_currents = currents
                else:
                    raise AssertionError(
                        f"Unexpected FMI version: {fmi_version.value}"
                    )
        assert fmu_path.exists()
        assert tuple(run_directory.glob("veragrid_fmu_stage_*")) == tuple()

    if (
        fmi_one_time is not None
        and fmi_one_currents is not None
        and fmi_two_time is not None
        and fmi_two_currents is not None
        and fmi_three_time is not None
        and fmi_three_currents is not None
    ):
        assert bool(np.array_equal(fmi_one_time, fmi_two_time))
        np.testing.assert_allclose(
            fmi_one_currents,
            fmi_two_currents,
            rtol=0.0,
            atol=1.0e-12,
        )
        assert bool(np.array_equal(fmi_two_time, fmi_three_time))
        np.testing.assert_allclose(
            fmi_two_currents,
            fmi_three_currents,
            rtol=1.0e-5,
            atol=2.0e-7,
        )
    else:
        raise AssertionError("The EMT ME version matrix is incomplete")


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_emt_driver_releases_native_runtime_after_failed_solve(tmp_path: Path) -> None:
    """Prove driver-owned native runtimes close after a failed EMT solve.

    :param tmp_path: Isolated FMU and staging directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    fmu_path: Path = export_test_emt_cs_fmu(tmp_path)
    grid: MultiCircuit
    load: Load
    grid, load = build_test_emt_grid()
    grid.add_emt_events_group(
        EmtEventsGroup(name="failed_native_cleanup_group")
    )

    power_flow_driver: PowerFlowDriver = PowerFlowDriver(
        grid=grid,
        options=build_test_power_flow_options(),
    )
    power_flow_driver.run()
    request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
        fmu_path=fmu_path,
        domain=FmuDeviceDomain.EMT,
        mode=FmuInterfaceMode.CO_SIMULATION,
        input_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.v_A, "v_a_in"),
            FmuRefBinding(VarPowerFlowReferenceType.v_B, "v_b_in"),
            FmuRefBinding(VarPowerFlowReferenceType.v_C, "v_c_in"),
        ),
        output_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.i_A, "i_a_out"),
            FmuRefBinding(VarPowerFlowReferenceType.i_B, "i_b_out"),
            FmuRefBinding(VarPowerFlowReferenceType.i_C, "i_c_out"),
        ),
        output_defaults=(
            FmuReferenceValue(VarPowerFlowReferenceType.i_A, 0.0),
            FmuReferenceValue(VarPowerFlowReferenceType.i_B, 0.0),
            FmuReferenceValue(VarPowerFlowReferenceType.i_C, 0.0),
        ),
        extraction_root=tmp_path,
    )
    attached_block: Block = attach_fmu_to_device(load, grid, request)
    assert attached_block is load.emt_model

    # Zero initialization iterations deliberately fails only after the real
    # boundary runtime has opened, exercising driver-owned cleanup.
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=EmtOptions(
            time_step=5.0e-6,
            simulation_time=1.0e-3,
            tolerance=1.0e-6,
            solver_type=EmtSolverTypes.Symbolic,
            integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
            initialization_method=EmtInitializationMethod.ConsistentNewton,
            init_newton_max_iter=0,
            verbose=0,
        ),
        pf_results=power_flow_driver.results,
        pf_results_3ph=None,
    )
    emt_driver.run()

    if emt_driver.results is None:
        raise AssertionError("The failed EMT solve did not publish its status")
    else:
        assert not bool(emt_driver.results.well_initialized[0])
        assert not bool(emt_driver.results.converged[0])
    assert fmu_path.exists()
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()
