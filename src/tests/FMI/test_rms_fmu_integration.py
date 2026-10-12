from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.IO.fmu.CosimulationInterface.build import host_build_capable
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.worker_host import (
    FmiThreeWorkerHostLimits,
)
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.enumerations import FmiVersion, VarPowerFlowReferenceType
from tests.FMI.fmi_test_support import execute_test_rms_fmu_case


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_rms_fmu_co_simulation_runs_end_to_end(tmp_path: Path) -> None:
    """Compare FMI 1 and FMI 2 CS through the complete RMS product path.

    :param tmp_path: Isolated FMU and native staging directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    versions: tuple[FmiVersion, ...] = (
        FmiVersion.FMI_1_0,
        FmiVersion.FMI_2_0,
    )
    expected_time_nanoseconds: np.ndarray = np.array(
        [0, 1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000],
        dtype=np.int64,
    )
    fmi_one_time: np.ndarray | None = None
    fmi_one_active_power: np.ndarray | None = None
    fmi_one_reactive_power: np.ndarray | None = None
    fmi_two_time: np.ndarray | None = None
    fmi_two_active_power: np.ndarray | None = None
    fmi_two_reactive_power: np.ndarray | None = None
    fmi_version: FmiVersion
    for fmi_version in versions:
        run_directory: Path = tmp_path / fmi_version.name.lower()
        driver: RmsSimulationDriver
        load: Load
        fmu_path: Path
        driver, load, fmu_path = execute_test_rms_fmu_case(
            output_dir=run_directory,
            mode=FmuInterfaceMode.CO_SIMULATION,
            fmi_version=fmi_version,
        )

        if driver.results is None:
            raise AssertionError(
                f"The RMS FMI {fmi_version.value} CS case published no results"
            )
        else:
            results: RmsResults = driver.results
        available_group_indices: np.ndarray = np.flatnonzero(
            results.has_event_group_results
        )
        assert available_group_indices.size == 1
        group_index: int = int(available_group_indices[0])
        assert bool(results.well_initialized[group_index])
        assert bool(results.converged[group_index])
        observed_time_nanoseconds: np.ndarray = np.array(
            [int(time_value.value) for time_value in results.time_array],
            dtype=np.int64,
        )
        np.testing.assert_array_equal(
            observed_time_nanoseconds,
            expected_time_nanoseconds,
        )
        time_seconds: np.ndarray = observed_time_nanoseconds.astype(float) * 1.0e-9
        p_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.P]
        q_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
        p_values: np.ndarray = results.values[
            :, results.uid2idx[p_var.uid], group_index
        ]
        q_values: np.ndarray = results.values[
            :, results.uid2idx[q_var.uid], group_index
        ]
        inferred_state: np.ndarray = -(p_values + 0.1) / 0.02
        expected_active_power: np.ndarray = -0.1 - 0.02 * time_seconds
        expected_reactive_power: np.ndarray = np.full(
            time_seconds.shape,
            -0.01,
            dtype=float,
        )
        np.testing.assert_allclose(
            inferred_state,
            time_seconds,
            rtol=0.0,
            atol=5.0e-8,
        )
        np.testing.assert_allclose(
            p_values,
            expected_active_power,
            rtol=0.0,
            atol=1.0e-9,
        )
        np.testing.assert_allclose(
            q_values,
            expected_reactive_power,
            rtol=0.0,
            atol=1.0e-9,
        )
        if fmi_version == FmiVersion.FMI_1_0:
            fmi_one_time = observed_time_nanoseconds
            fmi_one_active_power = p_values
            fmi_one_reactive_power = q_values
        else:
            fmi_two_time = observed_time_nanoseconds
            fmi_two_active_power = p_values
            fmi_two_reactive_power = q_values
        assert fmu_path.exists()
        assert tuple(run_directory.glob("veragrid_fmu_stage_*")) == tuple()

    if (
        fmi_one_time is not None
        and fmi_one_active_power is not None
        and fmi_one_reactive_power is not None
        and fmi_two_time is not None
        and fmi_two_active_power is not None
        and fmi_two_reactive_power is not None
    ):
        np.testing.assert_array_equal(fmi_one_time, fmi_two_time)
        np.testing.assert_allclose(
            fmi_one_active_power,
            fmi_two_active_power,
            rtol=0.0,
            atol=1.0e-12,
        )
        np.testing.assert_allclose(
            fmi_one_reactive_power,
            fmi_two_reactive_power,
            rtol=0.0,
            atol=1.0e-12,
        )
    else:
        raise AssertionError("The RMS CS FMI 1/2 matrix is incomplete")


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_rms_fmu_model_exchange_runs_end_to_end(tmp_path: Path) -> None:
    """Compare FMI 1 and FMI 2 ME through the complete RMS product path.

    :param tmp_path: Isolated FMU and native staging directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    expected_time_nanoseconds: np.ndarray = np.array(
        [0, 1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000],
        dtype=np.int64,
    )
    versions: tuple[FmiVersion, ...] = (
        FmiVersion.FMI_1_0,
        FmiVersion.FMI_2_0,
    )
    fmi_one_time: np.ndarray | None = None
    fmi_one_active_power: np.ndarray | None = None
    fmi_one_reactive_power: np.ndarray | None = None
    fmi_two_time: np.ndarray | None = None
    fmi_two_active_power: np.ndarray | None = None
    fmi_two_reactive_power: np.ndarray | None = None
    fmi_version: FmiVersion
    for fmi_version in versions:
        run_directory: Path = tmp_path / fmi_version.name.lower()
        driver: RmsSimulationDriver
        load: Load
        fmu_path: Path
        driver, load, fmu_path = execute_test_rms_fmu_case(
            output_dir=run_directory,
            mode=FmuInterfaceMode.MODEL_EXCHANGE,
            fmi_version=fmi_version,
        )

        if driver.results is None:
            raise AssertionError(
                f"The RMS FMI {fmi_version.value} ME case published no results"
            )
        else:
            results: RmsResults = driver.results
        available_group_indices: np.ndarray = np.flatnonzero(
            results.has_event_group_results
        )
        assert available_group_indices.size == 1
        group_index: int = int(available_group_indices[0])
        assert bool(results.well_initialized[group_index])
        assert bool(results.converged[group_index])
        observed_time_nanoseconds: np.ndarray = np.array(
            [int(time_value.value) for time_value in results.time_array],
            dtype=np.int64,
        )
        np.testing.assert_array_equal(
            observed_time_nanoseconds,
            expected_time_nanoseconds,
        )
        p_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.P]
        q_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
        if load.bus is not None and load.bus.rms_model is not None:
            vm_var: Var = load.bus.rms_model.external_mapping[
                VarPowerFlowReferenceType.Vm
            ]
        else:
            raise AssertionError(
                "The imported RMS load has no initialized voltage bus"
            )
        p_values: np.ndarray = results.values[
            :, results.uid2idx[p_var.uid], group_index
        ]
        q_values: np.ndarray = results.values[
            :, results.uid2idx[q_var.uid], group_index
        ]
        vm_values: np.ndarray = results.values[
            :, results.uid2idx[vm_var.uid], group_index
        ]
        assert bool(np.all(np.isfinite(p_values)))
        assert bool(np.all(np.isfinite(q_values)))
        assert bool(np.all(np.isfinite(vm_values)))
        assert p_values.size == 6
        assert q_values.size == 6
        assert vm_values.size == 6
        voltage_deviation: np.ndarray = vm_values - vm_values[0]
        expected_active_power: np.ndarray = -0.1 - 2.0 * voltage_deviation
        expected_reactive_power: np.ndarray = -0.01 - voltage_deviation
        np.testing.assert_allclose(
            p_values,
            expected_active_power,
            rtol=0.0,
            atol=1.0e-6,
        )
        np.testing.assert_allclose(
            q_values,
            expected_reactive_power,
            rtol=0.0,
            atol=1.0e-6,
        )
        assert float(p_values[2]) == pytest.approx(-0.1, abs=1.0e-6)
        assert float(q_values[2]) == pytest.approx(-0.01, abs=1.0e-6)
        assert abs(float(vm_values[3] - vm_values[2])) > 1.0e-5
        assert abs(float(p_values[3] - p_values[2])) > 1.0e-5
        assert abs(float(q_values[3] - q_values[2])) > 1.0e-5
        previous_voltage_active_power: float = -0.1 - 2.0 * float(
            vm_values[2] - vm_values[0]
        )
        previous_voltage_reactive_power: float = -0.01 - float(
            vm_values[2] - vm_values[0]
        )
        assert abs(float(p_values[3]) - previous_voltage_active_power) > 1.0e-5
        assert abs(float(q_values[3]) - previous_voltage_reactive_power) > 1.0e-5
        if fmi_version == FmiVersion.FMI_1_0:
            fmi_one_time = observed_time_nanoseconds
            fmi_one_active_power = p_values
            fmi_one_reactive_power = q_values
        else:
            fmi_two_time = observed_time_nanoseconds
            fmi_two_active_power = p_values
            fmi_two_reactive_power = q_values
        assert fmu_path.exists()
        assert tuple(run_directory.glob("veragrid_fmu_stage_*")) == tuple()

    if (
        fmi_one_time is not None
        and fmi_one_active_power is not None
        and fmi_one_reactive_power is not None
        and fmi_two_time is not None
        and fmi_two_active_power is not None
        and fmi_two_reactive_power is not None
    ):
        np.testing.assert_array_equal(fmi_one_time, fmi_two_time)
        np.testing.assert_allclose(
            fmi_one_active_power,
            fmi_two_active_power,
            rtol=0.0,
            atol=1.0e-12,
        )
        np.testing.assert_allclose(
            fmi_one_reactive_power,
            fmi_two_reactive_power,
            rtol=0.0,
            atol=1.0e-12,
        )
    else:
        raise AssertionError("The RMS ME FMI 1/2 matrix is incomplete")


def test_rms_fmi_three_me_runs_end_to_end(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Exercise an FMI 3 ME binary through the complete RMS product path.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Host-native dual-interface
        FMI 3 fixture supplied by the test session.
    :param tmp_path: Isolated native staging directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    driver: RmsSimulationDriver
    load: Load
    fmu_path: Path
    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    driver, load, fmu_path = execute_test_rms_fmu_case(
        output_dir=tmp_path,
        mode=FmuInterfaceMode.MODEL_EXCHANGE,
        source_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        me_input_variable_name="control_input",
        active_power_output_name="observed_output",
        reactive_power_output_name="observed_output",
        worker_limits=worker_limits,
        static_active_power_mw=0.0,
        static_reactive_power_mvar=0.0,
    )

    if driver.results is None:
        raise AssertionError("The RMS FMI 3 Model Exchange case published no results")
    else:
        results: RmsResults = driver.results
    available_group_indices: np.ndarray = np.flatnonzero(
        results.has_event_group_results
    )
    assert available_group_indices.size == 1
    group_index: int = int(available_group_indices[0])
    assert bool(results.well_initialized[group_index])
    assert bool(results.converged[group_index])
    assert float(results.time_array[-1].value) * 1.0e-9 == pytest.approx(5.0e-3)

    p_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.P]
    q_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
    p_values: np.ndarray = results.values[
        :, results.uid2idx[p_var.uid], group_index
    ]
    q_values: np.ndarray = results.values[
        :, results.uid2idx[q_var.uid], group_index
    ]
    assert bool(np.all(np.isfinite(p_values)))
    assert bool(np.all(np.isfinite(q_values)))
    assert bool(np.allclose(p_values, q_values))
    assert fmu_path == compiled_fmi_three_scalar_co_simulation_fmu
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()


def test_rms_fmi_three_cs_runs_end_to_end(
    compiled_fmi_three_scalar_co_simulation_fmu: Path,
    tmp_path: Path,
) -> None:
    """Exercise an FMI 3 CS binary through the complete RMS product path.

    :param compiled_fmi_three_scalar_co_simulation_fmu: Host-native dual-interface
        FMI 3 fixture supplied by the test session.
    :param tmp_path: Isolated native staging directory supplied by pytest.
    :return: None.
    """

    pytest.importorskip("fmpy")
    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    driver: RmsSimulationDriver
    load: Load
    fmu_path: Path
    driver, load, fmu_path = execute_test_rms_fmu_case(
        output_dir=tmp_path,
        mode=FmuInterfaceMode.CO_SIMULATION,
        source_fmu_path=compiled_fmi_three_scalar_co_simulation_fmu,
        active_power_output_name="observed_output",
        reactive_power_output_name=None,
        worker_limits=worker_limits,
        static_active_power_mw=0.0,
        static_reactive_power_mvar=0.0,
        rms_tolerance=1.0e-4,
    )

    if driver.results is None:
        raise AssertionError("The RMS FMI 3 Co-Simulation case published no results")
    else:
        results: RmsResults = driver.results
    available_group_indices: np.ndarray = np.flatnonzero(
        results.has_event_group_results
    )
    assert available_group_indices.size == 1
    group_index: int = int(available_group_indices[0])
    assert bool(results.well_initialized[group_index])
    assert bool(results.converged[group_index])
    assert float(results.time_array[-1].value) * 1.0e-9 == pytest.approx(5.0e-3)

    p_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.P]
    p_values: np.ndarray = results.values[
        :, results.uid2idx[p_var.uid], group_index
    ]
    assert bool(np.all(np.isfinite(p_values)))
    observed_time_seconds: np.ndarray = np.array(
        [float(time_value.value) * 1.0e-9 for time_value in results.time_array],
        dtype=float,
    )
    assert bool(np.allclose(
        p_values,
        observed_time_seconds,
        rtol=0.0,
        atol=1.0e-8,
    ))
    assert fmu_path == compiled_fmi_three_scalar_co_simulation_fmu
    assert tuple(tmp_path.glob("veragrid_fmu_stage_*")) == tuple()
