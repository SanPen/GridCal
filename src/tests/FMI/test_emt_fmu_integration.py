from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from VeraGridEngine.Devices.Events.emt_event import EmtEvent
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
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import SmallSignalStabilityEmtDriver
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import SmallSignalStabilityEmtOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_results import SmallSignalStabilityEmtResults
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    FmiVersion,
    SmallSignalEmtBuildTypes,
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


@pytest.mark.parametrize("solver_tpe", (EmtSolverTypes.Automatic, EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled))
def test_emt_driver_preserves_partial_event_group_results(solver_tpe: EmtSolverTypes) -> None:
    """Publish failed prefixes without damaging independent event groups.

    :param solver_tpe: Implicit EMT backend selected through the public driver.
    :return: None.
    """
    grid: MultiCircuit
    load: Load
    grid, load = build_test_emt_grid()
    z: Var = grid.var_factory.add_var("failure_probe_z")
    p: Var = grid.var_factory.add_var("failure_probe_p")
    block: Block = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block
    # Preserve the physical shunt and isolate failure in one algebraic equation.
    block.algebraic_vars.append(z)
    block.algebraic_eqs.append(z * z - p)
    block.mode_dict[p] = Const(1.0)
    block.init_eqs[z] = Const(1.0)
    set_emt_model(device=load, model=block, var_factory=grid.var_factory)
    assert load.emt_model is not None
    # Resolve the event parameter from the assigned symbolic model.
    parameter: Var | None = None
    model_parameter: Var
    for model_parameter in load.emt_model.mode_dict:
        if model_parameter.name == "failure_probe_p":
            parameter = model_parameter
        else:
            pass
    assert parameter is not None
    failed: EmtEventsGroup = EmtEventsGroup(name="partial_failure", idtag="probe-failed")
    complete: EmtEventsGroup = EmtEventsGroup(name="complete", idtag="probe-complete")
    inactive: EmtEventsGroup = EmtEventsGroup(name="inactive", idtag="probe-inactive", active=False)
    grid.add_emt_events_group(failed)
    grid.add_emt_events_group(complete)
    grid.add_emt_events_group(inactive)
    grid.add_emt_event(EmtEvent(device=load, parameter=parameter, time=1.5e-5, value=1e30, group=failed))
    pf: PowerFlowDriver = PowerFlowDriver(grid=grid, options=build_test_power_flow_options())
    pf.run()
    assert pf.results.converged
    driver: EmtSimulationDriver = EmtSimulationDriver(grid=grid, options=EmtOptions(
        time_step=5e-6, simulation_time=3e-5, tolerance=1e-6, solver_type=solver_tpe,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=EmtInitializationMethod.Explicit, init_newton_max_iter=5, verbose=0), pf_results=pf.results)
    driver.run()
    results: EmtResults = driver.results
    assert results is not None
    assert results.emt_events_group_names.tolist() == list(("partial_failure", "complete", "inactive"))
    assert results.emt_events_group_idtags.tolist() == list(("probe-failed", "probe-complete", "probe-inactive"))
    assert results.has_event_group_results.tolist() == list((True, True, False))
    assert results.converged.tolist() == list((False, True, False))
    assert results.well_initialized.tolist() == list((True, True, False))
    assert results.values.shape[0] == results.diff_values.shape[0] == 7
    np.testing.assert_allclose(np.asarray(results.time_array, dtype=np.int64) * 1e-9, np.arange(7) * 5e-6, rtol=0, atol=1e-12)
    assert np.all(np.isfinite(results.values[:3, :, 0]))
    assert np.all(np.isfinite(results.diff_values[:3, :, 0]))
    assert np.all(np.isnan(results.values[3:, :, 0]))
    assert np.all(np.isnan(results.diff_values[3:, :, 0]))
    assert np.all(np.isfinite(results.values[:, :, 1]))
    assert np.all(np.isfinite(results.diff_values[:, :, 1]))
    assert driver.problem is not None
    probe_var: Var | None = None
    model_variable: Var
    for model_variable in driver.problem.state_and_algebraic_vars():
        if model_variable.name == "failure_probe_z":
            probe_var = model_variable
        else:
            pass
    assert probe_var is not None
    probe_index: int = driver.problem.uid2idx_vars[probe_var.uid]
    assert results.variables[probe_index].uid == probe_var.uid
    np.testing.assert_allclose(results.values[:3, probe_index, 0], 1.0, rtol=0, atol=1e-12)
    np.testing.assert_allclose(results.values[:, probe_index, 1], 1.0, rtol=0, atol=1e-12)


@pytest.mark.parametrize("build_tpe", (SmallSignalEmtBuildTypes.Arnoldi, SmallSignalEmtBuildTypes.HybridArnoldi))
@pytest.mark.parametrize("failed,short_period,nonfinite_seed", ((True, False, False), (False, True, False), (False, False, True), (False, False, False)))
@pytest.mark.parametrize("prefer_ak", (False, True))
def test_floquet_rejects_invalid_emt_capture(build_tpe: SmallSignalEmtBuildTypes, failed: bool,
                                          short_period: bool, nonfinite_seed: bool, prefer_ak: bool) -> None:
    """Guard both Floquet consumers while preserving the successful period slice.

    :param build_tpe: Existing Floquet algorithm selection.
    :param failed: Whether the real EMT event causes Newton rejection.
    :param short_period: Whether the requested period exceeds the history.
    :param nonfinite_seed: Whether the captured initial algebraic state is NaN.
    :param prefer_ak: Whether the hybrid consumer requests its A-k operator.
    :return: None.
    """
    grid: MultiCircuit
    load: Load
    grid, load = build_test_emt_grid()
    z: Var = grid.var_factory.add_var("floquet_probe_z")
    p: Var = grid.var_factory.add_var("floquet_probe_p")
    block: Block = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block
    block.algebraic_vars.append(z)
    block.algebraic_eqs.append(z * z - p)
    block.mode_dict[p] = Const(1.0)
    block.init_eqs[z] = Const(float("nan") if nonfinite_seed else 1.0)
    set_emt_model(device=load, model=block, var_factory=grid.var_factory)
    assert load.emt_model is not None
    # Resolve the event parameter from the assigned symbolic model.
    parameter: Var | None = None
    model_parameter: Var
    for model_parameter in load.emt_model.mode_dict:
        if model_parameter.name == "floquet_probe_p":
            parameter = model_parameter
        else:
            pass
    assert parameter is not None
    group: EmtEventsGroup = EmtEventsGroup(name="floquet_probe_group")
    grid.add_emt_events_group(group)
    if failed:
        grid.add_emt_event(EmtEvent(device=load, parameter=parameter, time=1.5e-5, value=1e30, group=group))
    else:
        pass
    pf: PowerFlowDriver = PowerFlowDriver(grid=grid, options=build_test_power_flow_options())
    pf.run()
    assert pf.results.converged
    options: SmallSignalStabilityEmtOptions = SmallSignalStabilityEmtOptions(
        k=1, ss_assessment_time=3e-5, target_period=5e-5 if short_period else 2e-5, verbose=0, build_type=build_tpe, prefer_ak_operator=prefer_ak)
    driver: SmallSignalStabilityEmtDriver = SmallSignalStabilityEmtDriver(grid=grid, emt_options=EmtOptions(
        time_step=5e-6, simulation_time=3e-5, solver_type=EmtSolverTypes.StructuralAD,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=EmtInitializationMethod.Explicit, verbose=0), sss_options=options, pf_results=pf.results)
    driver.problem.set_events_group(emt_events_group=group)
    capture: tuple[np.ndarray, np.ndarray, object, np.ndarray, int] = driver._capture_limit_cycle_and_evaluator(h=5e-6)
    assert len(capture) == 5
    trajectory: np.ndarray = capture[0]
    times: np.ndarray = capture[1]
    static_params: np.ndarray = capture[3]
    event_count: int = capture[4]
    assert trajectory.dtype == times.dtype == static_params.dtype == np.float64
    assert event_count == driver.problem.get_variable_parameter_number()
    assert int(options.target_period / 5e-6) == (10 if short_period else 4)
    if failed or short_period or nonfinite_seed:
        assert trajectory.shape == (0, driver.problem.get_all_vars_number())
        assert times.shape == (0,)
        assert capture[2] is None
        assert driver.logger.error_count() == 1
        # Seed real prior results to verify reuse cannot expose stale spectra.
        driver.results = SmallSignalStabilityEmtResults(multipliers=np.ones(1, dtype=np.complex128),
            right_vecs=np.ones((1, 1), dtype=np.complex128), left_vecs=np.ones((1, 1), dtype=np.complex128),
            period=options.target_period, stat_vars=list((z,)))
        driver.run()
        assert driver.results is None
        assert driver.logger.error_count() == 2
    else:
        assert trajectory.shape == (4, driver.problem.get_all_vars_number())
        np.testing.assert_allclose(times, np.arange(3, 7) * 5e-6, rtol=0, atol=1e-12)
        assert capture[2] is not None
        assert np.all(np.isfinite(trajectory))
        assert driver.logger.error_count() == 0
        probe_var: Var | None = None
        model_variable: Var
        for model_variable in driver.problem.state_and_algebraic_vars():
            if model_variable.name == "floquet_probe_z":
                probe_var = model_variable
            else:
                pass
        assert probe_var is not None
        np.testing.assert_allclose(trajectory[:, driver.problem.uid2idx_vars[probe_var.uid]], 1.0, rtol=0, atol=1e-12)
