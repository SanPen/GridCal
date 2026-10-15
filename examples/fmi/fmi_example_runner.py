# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path

import numpy as np

from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    VarPowerFlowReferenceType,
)

from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.IO.fmu.Elements.bindings import FmuRefBinding
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuDeviceAttachmentRequest,
    FmuDeviceDomain,
    FmuReferenceValue,
    attach_fmu_to_device,
)
from examples.fmi.example_models import (
    build_emt_example_grid,
    build_example_power_flow_options,
    build_rms_example_grid,
    export_example_emt_cs_fmu,
    export_example_emt_me_fmu,
    export_example_rms_cs_fmu,
    export_example_rms_me_fmu,
)
from examples.fmi.event_scenario import (
    RmsLoadPowerStepScenario,
    build_default_rms_load_power_step_scenario,
)


def write_example_report(report_path: Path, lines: tuple[str, ...]) -> Path:
    """Write a plain-text report for one FMU import example run.

    :param report_path: Report output path.
    :param lines: Lines written to the report.
    :return: Final report path.
    """

    text: str = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    return report_path


class RmsFmiExampleExecution:
    """Own the conclusive numerical evidence from one RMS FMI example run."""

    __slots__ = (
        "_fmu_path",
        "_mode",
        "_report_path",
        "_time_seconds",
        "_active_power",
        "_reactive_power",
        "_voltage_magnitude",
        "_event_time_seconds",
        "_solver_tolerance",
        "_power_flow_residual",
    )

    def __init__(
            self,
            fmu_path: Path,
            mode: FmuInterfaceMode,
            report_path: Path,
            time_seconds: np.ndarray,
            active_power: np.ndarray,
            reactive_power: np.ndarray,
            voltage_magnitude: np.ndarray | None,
            event_time_seconds: float,
            solver_tolerance: float,
            power_flow_residual: float,
    ) -> None:
        """Store one completed RMS FMI execution without exposing mutable arrays.

        :param fmu_path: Exact FMU file consumed by the RMS runtime.
        :param mode: FMI interface mode used by the example.
        :param report_path: Human-readable execution report.
        :param time_seconds: Accepted RMS time lattice in seconds.
        :param active_power: Accepted active-power trajectory in p.u.
        :param reactive_power: Accepted reactive-power trajectory in p.u.
        :param voltage_magnitude: Accepted bus-voltage trajectory in p.u., when required.
        :param event_time_seconds: Exact RMS load-step boundary in seconds.
        :param solver_tolerance: RMS algebraic residual tolerance.
        :param power_flow_residual: Actual converged power-flow infinity-norm residual.
        :return: None.
        """

        self._fmu_path: Path = fmu_path.resolve()
        self._mode: FmuInterfaceMode = mode
        self._report_path: Path = report_path.resolve()
        self._time_seconds: np.ndarray = np.array(time_seconds, dtype=float, copy=True)
        self._active_power: np.ndarray = np.array(active_power, dtype=float, copy=True)
        self._reactive_power: np.ndarray = np.array(reactive_power, dtype=float, copy=True)
        if voltage_magnitude is None:
            self._voltage_magnitude: np.ndarray | None = None
        else:
            self._voltage_magnitude = np.array(voltage_magnitude, dtype=float, copy=True)
        self._event_time_seconds: float = float(event_time_seconds)
        self._solver_tolerance: float = float(solver_tolerance)
        self._power_flow_residual: float = float(power_flow_residual)

    def get_fmu_path(self) -> Path:
        """Return the exact FMU path used by both comparison consumers.

        :return: Resolved FMU path.
        """

        return self._fmu_path

    def get_mode(self) -> FmuInterfaceMode:
        """Return the executed FMI interface mode.

        :return: Co-Simulation or Model Exchange mode.
        """

        return self._mode

    def get_report_path(self) -> Path:
        """Return the generated human-readable report path.

        :return: Resolved report path.
        """

        return self._report_path

    def get_time_seconds(self) -> np.ndarray:
        """Return a defensive copy of the accepted time lattice.

        :return: Time in seconds.
        """

        return self._time_seconds.copy()

    def get_active_power(self) -> np.ndarray:
        """Return a defensive copy of the accepted active-power trace.

        :return: Active power in p.u.
        """

        return self._active_power.copy()

    def get_reactive_power(self) -> np.ndarray:
        """Return a defensive copy of the accepted reactive-power trace.

        :return: Reactive power in p.u.
        """

        return self._reactive_power.copy()

    def get_voltage_magnitude(self) -> np.ndarray | None:
        """Return a defensive copy of the accepted voltage-magnitude trace.

        :return: Voltage magnitude in p.u., or None when the mode does not need it.
        """

        if self._voltage_magnitude is None:
            return None
        else:
            return self._voltage_magnitude.copy()

    def get_event_time_seconds(self) -> float:
        """Return the exact RMS load-step boundary.

        :return: Event boundary in seconds.
        """

        return self._event_time_seconds

    def get_solver_tolerance(self) -> float:
        """Return the RMS algebraic residual tolerance used by the driver.

        :return: RMS residual tolerance.
        """

        return self._solver_tolerance

    def get_power_flow_residual(self) -> float:
        """Return the actual converged power-flow infinity-norm residual.

        :return: Power-flow residual in p.u.
        """

        return self._power_flow_residual


def _get_load_power_default(
        grid: MultiCircuit,
        load: Load,
) -> tuple[float, float]:
    """Return the active and reactive injection owned by one load.

    A bus can own other devices, including the independent disturbance load.
    Therefore the imported FMU shell must derive its defaults from its own
    static device powers rather than from the aggregate solved bus injection.

    :param grid: Grid that owns the system base power.
    :param load: Imported load represented by the FMU.
    :return: Active and reactive device injections in p.u.
    """

    base_power_mva: float = float(grid.Sbase)
    active_power_pu: float = -float(load.P) / base_power_mva
    reactive_power_pu: float = -float(load.Q) / base_power_mva
    return active_power_pu, reactive_power_pu


def _get_rms_example_group_index(driver: RmsSimulationDriver) -> int:
    """Return the sole conclusive event-group index from an RMS example.

    :param driver: Finished RMS simulation driver.
    :return: Event-group index that owns the accepted result.
    """

    if driver.results is None:
        raise RuntimeError("The RMS simulation did not produce results")
    else:
        pass

    # Match declared activation to result availability so preallocated
    # placeholder groups can never be selected by position.
    declared_group_count: int = len(driver.grid.rms_events_groups)
    active_group_mask: np.ndarray = np.zeros(declared_group_count, dtype=bool)
    declared_group_index: int
    for declared_group_index in range(declared_group_count):
        event_group: RmsEventsGroup = driver.grid.rms_events_groups[declared_group_index]
        active_group_mask[declared_group_index] = bool(event_group.active)
    active_group_indices: np.ndarray = np.flatnonzero(active_group_mask)
    available_group_indices: np.ndarray = np.flatnonzero(
        driver.results.has_event_group_results
    )
    groups_match: bool = bool(
        active_group_indices.size == 1
        and available_group_indices.size == 1
        and np.array_equal(active_group_indices, available_group_indices)
    )
    if groups_match:
        group_index: int = int(active_group_indices[0])
    else:
        raise RuntimeError(
            "The RMS example requires one identical active and available event group"
        )

    # Numerical rows become evidence only after both initialization and the
    # transient solve have completed successfully for the selected group.
    well_initialized: bool = bool(driver.results.well_initialized[group_index])
    converged: bool = bool(driver.results.converged[group_index])
    if well_initialized and converged:
        pass
    else:
        raise RuntimeError(
            "The RMS example did not initialize and converge successfully"
        )

    # Reject a preallocated lattice from an early return before extracting any
    # trajectory from the result container.
    final_time_seconds: float = float(driver.results.time_array[-1].value) * 1.0e-9
    final_time_matches: bool = bool(
        np.isclose(
            final_time_seconds,
            driver.options.simulation_time,
            rtol=0.0,
            atol=1.0e-12,
        )
    )
    if final_time_matches:
        pass
    else:
        raise RuntimeError("The RMS example did not reach its configured terminal time")
    return group_index


def _get_rms_result_trace(
        driver: RmsSimulationDriver,
        variable: Var,
        group_index: int,
) -> np.ndarray:
    """Return one finite trajectory from the selected RMS result group.

    :param driver: Finished RMS simulation driver.
    :param variable: Canonical symbolic variable whose stored trace is required.
    :param group_index: Conclusive event-group index.
    :return: Defensive one-dimensional trajectory copy.
    """

    if driver.results is None:
        raise RuntimeError("The RMS simulation did not produce results")
    else:
        pass

    column_index: int | None = driver.results.uid2idx.get(variable.uid, None)
    indices_are_valid: bool = bool(
        column_index is not None
        and driver.results.values.ndim == 3
        and column_index >= 0
        and column_index < driver.results.values.shape[1]
        and group_index >= 0
        and group_index < driver.results.values.shape[2]
    )
    if indices_are_valid and column_index is not None:
        trace: np.ndarray = np.array(
            driver.results.values[:, column_index, group_index],
            dtype=float,
            copy=True,
        )
    else:
        raise RuntimeError(f"The RMS example did not record variable {variable.name}")

    trace_is_conclusive: bool = bool(
        trace.ndim == 1
        and trace.size == driver.results.time_array.size
        and trace.size > 0
        and np.all(np.isfinite(trace))
    )
    if trace_is_conclusive:
        return trace
    else:
        raise RuntimeError(
            f"The RMS example trace for {variable.name} is incomplete or non-finite"
        )


def _build_rms_example_request(
        fmu_path: Path,
        output_dir: Path,
        mode: FmuInterfaceMode,
        active_power_default: float,
        reactive_power_default: float,
) -> FmuDeviceAttachmentRequest:
    """Build the mode-specific attachment request shared by RMS examples.

    :param fmu_path: Exact exported FMU path.
    :param output_dir: Trusted extraction directory owned by the example.
    :param mode: FMI interface mode.
    :param active_power_default: Initial active-power shell value in p.u.
    :param reactive_power_default: Initial reactive-power shell value in p.u.
    :return: Complete RMS attachment request.
    """

    if (
        mode == FmuInterfaceMode.CO_SIMULATION
        or mode == FmuInterfaceMode.MODEL_EXCHANGE
    ):
        input_bindings: tuple[FmuRefBinding, ...] = (
            FmuRefBinding(VarPowerFlowReferenceType.Vm, "u"),
        )
    else:
        raise ValueError(f"Unsupported RMS FMI example mode: {mode.value}")

    return FmuDeviceAttachmentRequest(
        fmu_path=fmu_path,
        domain=FmuDeviceDomain.RMS,
        mode=mode,
        input_bindings=input_bindings,
        output_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.P, "p_out"),
            FmuRefBinding(VarPowerFlowReferenceType.Q, "q_out"),
        ),
        output_defaults=(
            FmuReferenceValue(
                VarPowerFlowReferenceType.P,
                active_power_default,
            ),
            FmuReferenceValue(
                VarPowerFlowReferenceType.Q,
                reactive_power_default,
            ),
        ),
        extraction_root=output_dir,
    )


def _build_rms_results_summary(driver: RmsSimulationDriver, load: Load) -> tuple[str, ...]:
    """Build a human-readable summary for one RMS FMU import example.

    :param driver: Finished RMS simulation driver.
    :param load: Imported FMU load device.
    :return: Summary lines.
    """

    group_index: int = _get_rms_example_group_index(driver)
    if driver.results is None:
        raise RuntimeError("The RMS simulation did not produce results")
    else:
        pass

    # External mappings preserve the canonical device identities used by the
    # comparison API; no report parsing or parallel output registry is needed.
    p_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.P]
    q_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
    active_power: np.ndarray = _get_rms_result_trace(driver, p_var, group_index)
    reactive_power: np.ndarray = _get_rms_result_trace(driver, q_var, group_index)
    p_final: float = float(active_power[-1])
    q_final: float = float(reactive_power[-1])
    power_values: np.ndarray = np.array([p_final, q_final], dtype=float)
    powers_are_conclusive: bool = bool(
        np.all(np.isfinite(power_values))
        and np.all(np.abs(power_values) >= 1.0e-8)
    )
    if powers_are_conclusive:
        pass
    else:
        raise RuntimeError(
            "The RMS example P and Q outputs are non-finite or placeholders"
        )

    final_time_seconds: float = float(driver.results.time_array[-1].value) * 1.0e-9
    well_initialized: bool = bool(driver.results.well_initialized[group_index])
    converged: bool = bool(driver.results.converged[group_index])
    return (
        "event_group_count = 1",
        f"well_initialized = {well_initialized}",
        f"converged = {converged}",
        f"final_time_seconds = {final_time_seconds:.12f}",
        f"P_final = {p_final:.8f}",
        f"Q_final = {q_final:.8f}",
    )


def _build_emt_results_summary(driver: EmtSimulationDriver, load: Load) -> tuple[str, ...]:
    """Build a human-readable summary for one EMT FMU import example.

    :param driver: Finished EMT simulation driver.
    :param load: Imported FMU load device.
    :return: Summary lines.
    """

    if driver.results is None:
        raise RuntimeError("The EMT simulation did not produce results")
    else:
        # A report represents one conclusive run, not the placeholder storage
        # allocated for inactive or failed event groups.
        active_group_count: int = 0
        event_group: EmtEventsGroup
        for event_group in driver.grid.emt_events_groups:
            if event_group.active:
                active_group_count += 1
            else:
                pass
        available_group_indices: np.ndarray = np.flatnonzero(driver.results.has_event_group_results)
        if active_group_count == 1 and available_group_indices.size == 1:
            group_index: int = int(available_group_indices[0])
        else:
            raise RuntimeError(
                "The EMT example requires exactly one active and available event group"
            )

        # Solver status must be affirmative before any preallocated numerical
        # value can be presented as a successful native FMI result.
        well_initialized: bool = bool(driver.results.well_initialized[group_index])
        converged: bool = bool(driver.results.converged[group_index])
        if well_initialized and converged:
            pass
        else:
            raise RuntimeError(
                "The EMT example did not initialize and converge successfully"
            )

        final_time_seconds: float = float(driver.results.time_array[-1].value) * 1.0e-9
        final_time_matches: bool = bool(
            np.isclose(
                final_time_seconds,
                driver.options.simulation_time,
                rtol=0.0,
                atol=1.0e-12,
            )
        )
        if final_time_matches:
            pass
        else:
            raise RuntimeError("The EMT example did not reach its configured terminal time")

        i_a_var: Var = load.emt_model.external_mapping[VarPowerFlowReferenceType.i_A]
        i_b_var: Var = load.emt_model.external_mapping[VarPowerFlowReferenceType.i_B]
        i_c_var: Var = load.emt_model.external_mapping[VarPowerFlowReferenceType.i_C]
        i_a_final: float | None = _try_get_result_value(
            driver.results.values, driver.results.uid2idx.get(i_a_var.uid, None), group_index
        )
        i_b_final: float | None = _try_get_result_value(
            driver.results.values, driver.results.uid2idx.get(i_b_var.uid, None), group_index
        )
        i_c_final: float | None = _try_get_result_value(
            driver.results.values, driver.results.uid2idx.get(i_c_var.uid, None), group_index
        )
        if i_a_final is not None and i_b_final is not None and i_c_final is not None:
            currents: np.ndarray = np.array([i_a_final, i_b_final, i_c_final], dtype=float)
        else:
            raise RuntimeError("The EMT example did not record all three phase currents")

        currents_are_finite: bool = bool(np.all(np.isfinite(currents)))
        max_abs_current: float = float(np.max(np.abs(currents)))
        current_balance: float = float(np.sum(currents))
        if currents_are_finite and max_abs_current >= 1.0e-8 and abs(current_balance) <= 1.0e-6:
            pass
        else:
            raise RuntimeError(
                "The EMT example currents are non-finite, placeholders, or unbalanced"
            )

        return (
            f"event_group_count = {active_group_count}",
            f"well_initialized = {well_initialized}",
            f"converged = {converged}",
            f"final_time_seconds = {final_time_seconds:.12f}",
            f"iA_final = {i_a_final:.8f}",
            f"iB_final = {i_b_final:.8f}",
            f"iC_final = {i_c_final:.8f}",
            f"current_balance = {current_balance:.8e}",
        )


def _try_get_result_value(
        values: np.ndarray,
        column_index: int | None,
        group_index: int,
) -> float | None:
    """Try to recover one scalar value from a VeraGrid results matrix.

    :param values: Results matrix.
    :param column_index: Candidate variable column index.
    :param group_index: Selected event-group index in the third storage axis.
    :return: Final scalar value when available.
    """

    if column_index is None:
        return None
    else:
        indices_are_valid: bool = bool(
            values.ndim == 3
            and column_index >= 0
            and column_index < values.shape[1]
            and group_index >= 0
            and group_index < values.shape[2]
        )
        if indices_are_valid:
            return float(values[-1, column_index, group_index])
        else:
            return None


def execute_rms_fmi_example(
        output_dir: Path,
        mode: FmuInterfaceMode,
        scenario: RmsLoadPowerStepScenario | None = None,
) -> RmsFmiExampleExecution:
    """Execute one native RMS FMI example and retain its accepted trajectories.

    :param output_dir: Owned directory used for the FMU, extraction and report.
    :param mode: Co-Simulation or Model Exchange interface mode.
    :param scenario: Validated benchmark scenario, or None for the maintained default.
    :return: Typed execution evidence with defensive trajectory access.
    """

    # Retain a validated scenario copy before creating output or exporting an
    # FMU so caller mutation cannot alter partial benchmark evidence.
    active_scenario: RmsLoadPowerStepScenario
    if scenario is None:
        active_scenario = build_default_rms_load_power_step_scenario()
    elif isinstance(scenario, RmsLoadPowerStepScenario):
        active_scenario = scenario.copy_validated()
    else:
        raise TypeError("RMS FMI scenario has an unsupported type")

    output_dir.mkdir(parents=True, exist_ok=True)
    time_step_seconds: float = active_scenario.time_step_seconds
    simulation_time_seconds: float = active_scenario.stop_time_seconds
    event_time_seconds: float = active_scenario.event_time_seconds

    # Export exactly once so the native RMS path and the later direct FMPy
    # consumer can be bound to the same archive bytes.
    if mode == FmuInterfaceMode.CO_SIMULATION:
        fmu_path: Path = export_example_rms_cs_fmu(output_dir)
        report_path: Path = output_dir / "rms_cs_example_report.txt"
    elif mode == FmuInterfaceMode.MODEL_EXCHANGE:
        fmu_path = export_example_rms_me_fmu(output_dir)
        report_path = output_dir / "rms_me_example_report.txt"
    else:
        raise ValueError(f"Unsupported RMS FMI example mode: {mode.value}")

    # The static operating point supplies the initial shell parameter. Its
    # actual infinity-norm residual is retained for the row-zero error budget.
    grid: MultiCircuit
    load: Load
    grid, load = build_rms_example_grid(
        event_time_seconds=event_time_seconds,
        scenario=active_scenario,
    )
    power_flow_options: PowerFlowOptions = build_example_power_flow_options()
    pf_driver: PowerFlowDriver = PowerFlowDriver(
        grid=grid,
        options=power_flow_options,
    )
    pf_driver.run()
    power_flow_results: PowerFlowResults = pf_driver.results
    power_flow_residual: float = float(power_flow_results.error)
    power_flow_is_conclusive: bool = bool(
        len(power_flow_results.convergence_reports) > 0
        and power_flow_results.converged
        and np.isfinite(power_flow_residual)
        and power_flow_residual >= 0.0
        and power_flow_residual < power_flow_options.tolerance
    )
    if power_flow_is_conclusive:
        pass
    else:
        raise RuntimeError(
            "The RMS FMI example requires one converged finite power-flow result"
        )

    active_power_default: float
    reactive_power_default: float
    if load.bus is None:
        raise RuntimeError("The RMS FMI example load is not connected to a bus")
    else:
        active_power_default, reactive_power_default = _get_load_power_default(
            grid,
            load,
        )
    request: FmuDeviceAttachmentRequest = _build_rms_example_request(
        fmu_path=fmu_path,
        output_dir=output_dir,
        mode=mode,
        active_power_default=active_power_default,
        reactive_power_default=reactive_power_default,
    )
    attach_fmu_to_device(load, grid, request)

    # Keep the time lattice and nonlinear tolerance explicit because both are
    # part of the comparison proof, not display-only metadata.
    rms_options: RmsOptions = RmsOptions(
        time_step=time_step_seconds,
        simulation_time=simulation_time_seconds,
        tolerance=1.0e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        max_iter=50,
    )
    rms_driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=rms_options,
        pf_results=power_flow_results,
    )
    rms_driver.run()
    group_index: int = _get_rms_example_group_index(rms_driver)
    if rms_driver.results is None:
        raise RuntimeError("The RMS simulation did not produce results")
    else:
        pass

    p_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.P]
    q_var: Var = load.rms_model.external_mapping[VarPowerFlowReferenceType.Q]
    active_power: np.ndarray = _get_rms_result_trace(
        rms_driver,
        p_var,
        group_index,
    )
    reactive_power: np.ndarray = _get_rms_result_trace(
        rms_driver,
        q_var,
        group_index,
    )
    time_seconds: np.ndarray = (
        np.asarray(rms_driver.results.time_array.asi8, dtype=float) * 1.0e-9
    )

    # Both FMI modes consume the same physical bus-voltage trajectory. Retain
    # the exact accepted samples so direct FMPy can replay the event excitation.
    vm_candidate: Var | None = load.bus.rms_model.external_mapping.get(
        VarPowerFlowReferenceType.Vm,
        None,
    )
    if isinstance(vm_candidate, Var):
        voltage_magnitude: np.ndarray | None = _get_rms_result_trace(
            rms_driver,
            vm_candidate,
            group_index,
        )
    else:
        raise RuntimeError("The RMS FMI example did not expose bus voltage magnitude")

    # The solver stores the boundary with the old event value and applies the
    # step strictly afterward. Validate the exact lattice and a measurable
    # physical input/output response rather than relying on plot autoscaling.
    expected_time_seconds: np.ndarray = active_scenario.build_time_lattice()
    expected_sample_count: int = active_scenario.sample_count
    boundary_indices: np.ndarray = np.flatnonzero(
        np.abs(time_seconds - event_time_seconds) <= 1.0e-12
    )
    post_event_indices: np.ndarray = np.flatnonzero(
        time_seconds > event_time_seconds
    )
    lattice_is_conclusive: bool = bool(
        time_seconds.size == expected_sample_count
        and np.all(np.abs(time_seconds - expected_time_seconds) <= 1.0e-12)
        and boundary_indices.size == 1
        and post_event_indices.size > 0
        and int(boundary_indices[0])
        == active_scenario.event_boundary_index
        and int(post_event_indices[0])
        == active_scenario.first_post_event_index
        and abs(
            float(time_seconds[post_event_indices[0]])
            - active_scenario.first_post_event_time_seconds
        ) <= 1.0e-12
    )
    if lattice_is_conclusive:
        boundary_index: int = int(boundary_indices[0])
    else:
        raise RuntimeError("The RMS event comparison lattice is not conclusive")
    voltage_response: float = float(
        np.max(
            np.abs(
                voltage_magnitude[post_event_indices]
                - voltage_magnitude[boundary_index]
            )
        )
    )
    active_power_response: float = float(
        np.max(
            np.abs(
                active_power[post_event_indices]
                - active_power[boundary_index]
            )
        )
    )
    response_is_conclusive: bool = bool(
        voltage_response >= active_scenario.voltage_response_threshold_pu
        and active_power_response
        >= active_scenario.active_power_response_threshold_pu
    )
    if response_is_conclusive:
        pass
    else:
        raise RuntimeError(
            "The RMS event did not produce the required measurable response: "
            f"Vm={voltage_response:.16e}, P={active_power_response:.16e}"
        )

    # Reuse the scenario's evidence boundary so the report and manifest cannot
    # drift through duplicated classification text.
    event_record: dict[str, object] = active_scenario.build_manifest_event_record()
    boundary_semantics_candidate: object = event_record.get(
        "boundary_semantics",
        None,
    )
    if isinstance(boundary_semantics_candidate, str):
        boundary_semantics: str = boundary_semantics_candidate
    else:
        raise RuntimeError("RMS event evidence lacks boundary semantics")

    lines: tuple[str, ...] = (
        f"fmu_path = {fmu_path}",
        f"mode = {request.mode.value}",
        f"power_flow_residual = {power_flow_residual:.16e}",
        f"rms_solver_tolerance = {rms_options.tolerance:.16e}",
        f"event_time_seconds = {event_time_seconds:.16e}",
        (
            "event_boundary_semantics = "
            f"{boundary_semantics}"
        ),
        f"post_event_voltage_response = {voltage_response:.16e}",
        f"post_event_active_power_response = {active_power_response:.16e}",
    ) + _build_rms_results_summary(rms_driver, load)
    written_report_path: Path = write_example_report(report_path, lines)
    return RmsFmiExampleExecution(
        fmu_path=fmu_path,
        mode=mode,
        report_path=written_report_path,
        time_seconds=time_seconds,
        active_power=active_power,
        reactive_power=reactive_power,
        voltage_magnitude=voltage_magnitude,
        event_time_seconds=event_time_seconds,
        solver_tolerance=rms_options.tolerance,
        power_flow_residual=power_flow_residual,
    )


def run_rms_cs_example(output_dir: Path) -> Path:
    """Run the full RMS Co-Simulation FMU device example.

    :param output_dir: Output directory used for the FMU and the report.
    :return: Generated report path.
    """

    execution: RmsFmiExampleExecution = execute_rms_fmi_example(
        output_dir,
        FmuInterfaceMode.CO_SIMULATION,
    )
    return execution.get_report_path()


def run_rms_me_example(output_dir: Path) -> Path:
    """Run the full RMS Model Exchange FMU device example.

    :param output_dir: Output directory used for the FMU and the report.
    :return: Generated report path.
    """

    execution: RmsFmiExampleExecution = execute_rms_fmi_example(
        output_dir,
        FmuInterfaceMode.MODEL_EXCHANGE,
    )
    return execution.get_report_path()


def run_emt_cs_example(output_dir: Path) -> Path:
    """Run the full EMT Co-Simulation FMU device example.

    :param output_dir: Output directory used for the FMU and the report.
    :return: Generated report path.
    """

    fmu_path: Path = export_example_emt_cs_fmu(output_dir)
    report_path: Path = output_dir / "emt_cs_example_report.txt"

    grid: MultiCircuit
    load: Load
    grid, load = build_emt_example_grid()
    grid.add_emt_events_group(EmtEventsGroup(name="default_emt_cs_example_group"))
    pf_driver: PowerFlowDriver = PowerFlowDriver(
        grid=grid,
        options=build_example_power_flow_options(),
    )
    pf_driver.run()

    request = FmuDeviceAttachmentRequest(
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
        extraction_root=output_dir,
    )

    # The public attachment stores the declarative device configuration. The
    # real EMT problem reconstructs and registers the native adapter from it.
    attach_fmu_to_device(load, grid, request)
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=EmtOptions(
            time_step=5.0e-6,
            simulation_time=1.0e-3,
            tolerance=1.0e-6,
            solver_type=EmtSolverTypes.Symbolic,
            integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
            initialization_method=EmtInitializationMethod.Auto,
            verbose=0,
        ),
        pf_results=pf_driver.results,
        pf_results_3ph=None,
    )
    emt_driver.run()

    lines: tuple[str, ...] = (
        f"fmu_path = {fmu_path}",
        f"mode = {request.mode.value}",
    ) + _build_emt_results_summary(emt_driver, load)
    return write_example_report(report_path, lines)


def run_emt_me_example(output_dir: Path) -> Path:
    """Run the full EMT Model Exchange FMU device example.

    :param output_dir: Output directory used for the FMU and the report.
    :return: Generated report path.
    """

    fmu_path: Path = export_example_emt_me_fmu(output_dir)
    report_path: Path = output_dir / "emt_me_example_report.txt"

    grid: MultiCircuit
    load: Load
    grid, load = build_emt_example_grid()
    grid.add_emt_events_group(EmtEventsGroup(name="default_emt_me_example_group"))
    pf_driver: PowerFlowDriver = PowerFlowDriver(
        grid=grid,
        options=build_example_power_flow_options(),
    )
    pf_driver.run()

    request = FmuDeviceAttachmentRequest(
        fmu_path=fmu_path,
        domain=FmuDeviceDomain.EMT,
        mode=FmuInterfaceMode.MODEL_EXCHANGE,
        input_bindings=(
            FmuRefBinding(VarPowerFlowReferenceType.v_A, "u"),
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
        extraction_root=output_dir,
    )

    # The bus template already exposes the real phase-A voltage reference used
    # by the Model Exchange input binding.
    attach_fmu_to_device(load, grid, request)
    emt_driver: EmtSimulationDriver = EmtSimulationDriver(
        grid=grid,
        options=EmtOptions(
            time_step=5.0e-6,
            simulation_time=1.0e-3,
            tolerance=1.0e-6,
            solver_type=EmtSolverTypes.Symbolic,
            integration_method=DynamicIntegrationMethod.DaeBackEuler,
            initialization_method=EmtInitializationMethod.Auto,
            verbose=0,
        ),
        pf_results=pf_driver.results,
        pf_results_3ph=None,
    )
    emt_driver.run()

    lines: tuple[str, ...] = (
        f"fmu_path = {fmu_path}",
        f"mode = {request.mode.value}",
    ) + _build_emt_results_summary(emt_driver, load)
    return write_example_report(report_path, lines)
