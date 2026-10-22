"""Focused contracts for simulation-owned FMI Model Exchange integration."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import scipy.sparse as sp
import pytest

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.IO.fmu.Elements.bindings import FmuImportConfig
from VeraGridEngine.IO.fmu.fmu_device_integration import CompositeEmtBoundaryUpdater
from VeraGridEngine.IO.fmu.model_exchange import (
    RmsFmuMeDeviceAdapter,
    EmtFmuMeDeviceAdapter,
    FmuMeDomain,
    FmuMeDeviceAdapter,
    FmuMeSolverPolicy,
    _build_fmu_me_solver_policy,
    advance_rms_fmu_me_devices,
    build_fmu_me_device_spec,
    _prepare_rms_fmu_me_state_event_retry,
)
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode
from VeraGridEngine.IO.fmu.coordinator import (
    FmiThreeModelExchangeCoordinator,
)
from VeraGridEngine.IO.fmu.host import (
    FmiOneEventUpdate,
    FmiTwoEventUpdate,
)
from VeraGridEngine.IO.fmu.profile import FmuMeEvaluationBudget
from VeraGridEngine.IO.fmu.worker_host import FmiThreeWorkerHostLimits
from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerCompletedIntegratorStepResult,
    FmiThreeWorkerDiscreteStatesResult,
)
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx_vectorized import (
    BackEulerImplicitIntegrationVec,
)
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx_full_vectorized import (
    BackEulerImplicitIntegrationFullVec,
)
from VeraGridEngine.Simulations.Rms.numerical.midpoint import (
    MidpointImplicitIntegration,
)
from VeraGridEngine.Simulations.Rms.numerical.trapezoidal import (
    TrapezoidalImplicitIntegration,
)
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_vectorized import (
    RmsProblemDaeVec,
)
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_full_vectorized import (
    RmsProblemDaeFullVec,
)
from VeraGridEngine.Simulations.Rms.problems.rms_problem_phasor import (
    RmsProblemPhasor,
)
from VeraGridEngine.enumerations import DeviceType, DynamicIntegrationMethod, VarPowerFlowReferenceType


class _CurrentPointCouplingProblem:
    """Expose one differential state and deterministic FMI transaction traces."""

    __slots__ = (
        "_algebraic_eqs",
        "_variable_parameters_values",
        "_fmu_me_adapters",
        "algebraic_vars",
        "logger",
        "me_advance_snapshots",
        "resolve_acceptances",
        "operation_log",
        "cs_advance_count",
        "enable_cs",
        "cs_advance_result",
        "initial_event_time",
        "corrected_event_time",
        "pending_retry_time",
        "event_emitted",
        "initial_state_value",
        "cs_initialize_count",
        "me_initialize_count",
        "cs_close_count",
        "me_close_count",
        "derivative_rate",
        "quadratic_rate",
        "rate_change",
        "initial_candidate_value",
        "active_derivative_rate",
        "gathered_state_value",
        "jacobian_evaluations",
        "residual_evaluations",
        "last_update_time",
    )

    def __init__(
        self,
        enable_cs: bool = True,
        cs_advance_result: bool = False,
        initial_event_time: float | None = None,
        corrected_event_time: float | None = None,
        initial_state_value: float | None = None,
        derivative_rate: float = 1.0,
        quadratic_rate: float = 0.0,
        rate_change: tuple[float, float] | None = None,
        initial_candidate_value: float = 1.0,
    ) -> None:
        """Initialize the bounded one-state solver contract.

        :param enable_cs: Whether the problem exposes an active CS owner.
        :param cs_advance_result: Result returned after each CS advancement.
        :param initial_event_time: Event exposed by the initial ME candidate.
        :param corrected_event_time: Event exposed after a Newton correction.
        :param initial_state_value: Optional state value written by CS
            initialization.
        :param derivative_rate: Constant term of the analytic state derivative.
        :param quadratic_rate: Coefficient multiplying the squared state.
        :param rate_change: Optional target time and replacement constant rate.
        :param initial_candidate_value: Seed used to exercise finite-candidate guards.
        :return: None.
        """

        self._algebraic_eqs: list[object] = list()
        self._variable_parameters_values: np.ndarray = np.empty(0, dtype=float)
        self._fmu_me_adapters: list[object] = list()
        self.algebraic_vars: list[object] = list()
        self.logger: Mock = Mock()
        self.me_advance_snapshots: list[np.ndarray] = list()
        self.resolve_acceptances: list[bool] = list()
        self.operation_log: list[str] = list()
        self.cs_advance_count: int = 0
        self.enable_cs: bool = enable_cs
        self.cs_advance_result: bool = cs_advance_result
        self.initial_event_time: float | None = initial_event_time
        self.corrected_event_time: float | None = corrected_event_time
        self.pending_retry_time: float | None = None
        self.event_emitted: bool = False
        self.initial_state_value: float | None = initial_state_value
        self.cs_initialize_count: int = 0
        self.me_initialize_count: int = 0
        self.cs_close_count: int = 0
        self.me_close_count: int = 0
        # Keep the scalar oracle and gathered point in this existing test owner.
        self.derivative_rate: float = derivative_rate
        self.quadratic_rate: float = quadratic_rate
        self.rate_change: tuple[float, float] | None = rate_change
        self.initial_candidate_value: float = initial_candidate_value
        self.active_derivative_rate: float = derivative_rate
        self.gathered_state_value: float = initial_candidate_value
        self.jacobian_evaluations: int = 0
        self.residual_evaluations: int = 0
        self.last_update_time: float = 0.0

    def get_x0(self) -> np.ndarray:
        """Return the accepted initial state.

        :return: One-state initial vector.
        """

        return np.array((self.initial_candidate_value,), dtype=float)

    def get_all_vars_number(self) -> int:
        """Return the complete state-vector size.

        :return: One variable.
        """

        return 1

    def get_diff_var_number(self) -> int:
        """Return the differential-variable count.

        :return: One differential variable.
        """

        return 1

    def get_algebraic_var_number(self) -> int:
        """Return the algebraic-variable count.

        :return: Zero algebraic variables.
        """

        return 0

    def get_states_number(self) -> int:
        """Return the differential-state count.

        :return: One state.
        """

        return 1

    def get_small_signal_reference_indices(self) -> tuple[int, int] | None:
        """Return the absent reference constraint.

        :return: None because the scalar problem is nonsingular.
        """

        return None

    def get_dx(
        self,
        x_new: np.ndarray,
        x_previous: np.ndarray,
        dx_previous: np.ndarray,
        step_size: float,
    ) -> np.ndarray:
        """Compute the visible state slope.

        :param x_new: Current Newton state.
        :param x_previous: Accepted state.
        :param dx_previous: Previously accepted slope.
        :param step_size: Positive local step size.
        :return: Current finite-difference slope.
        """

        if dx_previous.size == 1 and step_size > 0.0:
            return (x_new - x_previous) / step_size
        else:
            raise AssertionError("Current-point slope contract is invalid")

    def update_variable_params(
        self,
        t: float,
        x_snapshot: np.ndarray,
        scheduled_t: float | None = None,
    ) -> None:
        """Validate the explicit parameter-update point.

        :param t: Target time.
        :param x_snapshot: Current network snapshot.
        :param scheduled_t: Accepted scheduling time.
        :return: None.
        """

        scheduling_time: float = t if scheduled_t is None else scheduled_t
        if math.isfinite(t) and math.isfinite(scheduling_time) and x_snapshot.size == 1:
            pass
        else:
            raise AssertionError("Current-point parameter update is invalid")

    def update(
        self,
        t: float,
        x_snapshot: np.ndarray,
        variable_parameters: np.ndarray,
    ) -> None:
        """Validate the explicit equation-update point.

        :param t: Target time.
        :param x_snapshot: Current network snapshot.
        :param variable_parameters: Empty parameter vector.
        :return: None.
        """

        if math.isfinite(t) and x_snapshot.size == 1 and variable_parameters.size == 0:
            pass
        else:
            raise AssertionError("Current-point equation update is invalid")
        # Scheduled rates let rejection be exercised after accepted macro samples.
        self.last_update_time = t
        if self.rate_change is not None and t >= self.rate_change[0]:
            self.active_derivative_rate = self.rate_change[1]
        else:
            self.active_derivative_rate = self.derivative_rate

    def update_input_matrices_by_model(
        self,
        x_snapshot: np.ndarray,
        dx_snapshot: np.ndarray,
    ) -> None:
        """Validate a vectorized gather without retaining duplicate state.

        :param x_snapshot: Current network snapshot.
        :param dx_snapshot: Current differential snapshot.
        :return: None.
        """

        if x_snapshot.size == 1 and dx_snapshot.size == 1:
            self.gathered_state_value = float(x_snapshot[0])
        else:
            raise AssertionError("Current-point vector gather is invalid")

    def rhs_algebraic(
        self,
        x_snapshot: np.ndarray,
        dx_snapshot: np.ndarray,
    ) -> np.ndarray:
        """Return the empty algebraic residual.

        :param x_snapshot: Current network snapshot.
        :param dx_snapshot: Current differential snapshot.
        :return: Empty residual vector.
        """

        if x_snapshot.size == 1 and dx_snapshot.size == 1:
            return np.empty(0, dtype=float)
        else:
            raise AssertionError("Current-point algebraic residual is invalid")

    def rhs_algebraic_vec(
        self,
        x_snapshot: np.ndarray,
        dx_snapshot: np.ndarray,
    ) -> np.ndarray:
        """Return the empty vectorized algebraic residual.

        :param x_snapshot: Current network snapshot.
        :param dx_snapshot: Current differential snapshot.
        :return: Empty residual vector.
        """

        return self.rhs_algebraic(x_snapshot, dx_snapshot)

    def rhs_state(
        self,
        x_snapshot: np.ndarray,
        dx_snapshot: np.ndarray,
    ) -> np.ndarray:
        """Evaluate the independent scalar constant-plus-quadratic derivative.

        :param x_snapshot: Current network snapshot.
        :param dx_snapshot: Current differential snapshot.
        :return: Analytic derivative at the supplied state.
        """

        if x_snapshot.size == 1 and dx_snapshot.size == 1:
            self.residual_evaluations += 1
            derivative: float = (
                self.active_derivative_rate
                + self.quadratic_rate * float(x_snapshot[0]) * float(x_snapshot[0])
            )
            return np.array((derivative,), dtype=float)
        else:
            raise AssertionError("Current-point state residual is invalid")

    def rhs_state_vec(self) -> np.ndarray:
        """Return the gathered vectorized state derivative.

        :return: Analytic derivative at the most recently gathered state.
        """

        self.residual_evaluations += 1
        derivative: float = (
            self.active_derivative_rate
            + self.quadratic_rate * self.gathered_state_value * self.gathered_state_value
        )
        return np.array((derivative,), dtype=float)

    def get_j11(
        self,
        x_snapshot: np.ndarray,
        dx_snapshot: np.ndarray,
        step_size: float,
    ) -> sp.csc_matrix:
        """Return the state-derivative Jacobian.

        :param x_snapshot: Current network snapshot.
        :param dx_snapshot: Current differential snapshot.
        :param step_size: Positive local step size.
        :return: One-by-one analytic derivative Jacobian in CSC storage.
        """

        if x_snapshot.size == 1 and dx_snapshot.size == 1 and step_size > 0.0:
            self.jacobian_evaluations += 1
            derivative: float = 2.0 * self.quadratic_rate * float(x_snapshot[0])
            return sp.csc_matrix(np.array(((derivative,),), dtype=float))
        else:
            raise AssertionError("Current-point J11 contract is invalid")

    def get_j12(
        self,
        x_snapshot: np.ndarray,
        dx_snapshot: np.ndarray,
        step_size: float,
    ) -> sp.csc_matrix:
        """Return the state-to-algebraic Jacobian block.

        :param x_snapshot: Current network snapshot.
        :param dx_snapshot: Current differential snapshot.
        :param step_size: Positive local step size.
        :return: One-by-zero CSC matrix.
        """

        if x_snapshot.size == 1 and dx_snapshot.size == 1 and step_size > 0.0:
            return sp.csc_matrix((1, 0), dtype=float)
        else:
            raise AssertionError("Current-point J12 contract is invalid")

    def get_j21(
        self,
        x_snapshot: np.ndarray,
        dx_snapshot: np.ndarray,
        step_size: float,
    ) -> sp.csc_matrix:
        """Return the algebraic-to-state Jacobian block.

        :param x_snapshot: Current network snapshot.
        :param dx_snapshot: Current differential snapshot.
        :param step_size: Positive local step size.
        :return: Zero-by-one CSC matrix.
        """

        if x_snapshot.size == 1 and dx_snapshot.size == 1 and step_size > 0.0:
            return sp.csc_matrix((0, 1), dtype=float)
        else:
            raise AssertionError("Current-point J21 contract is invalid")

    def get_j22(
        self,
        x_snapshot: np.ndarray,
        dx_snapshot: np.ndarray,
        step_size: float,
    ) -> sp.csc_matrix:
        """Return the empty algebraic Jacobian block.

        :param x_snapshot: Current network snapshot.
        :param dx_snapshot: Current differential snapshot.
        :param step_size: Positive local step size.
        :return: Empty CSC matrix.
        """

        if x_snapshot.size == 1 and dx_snapshot.size == 1 and step_size > 0.0:
            return sp.csc_matrix((0, 0), dtype=float)
        else:
            raise AssertionError("Current-point J22 contract is invalid")

    def get_j11_vec(self, step_size: float) -> sp.csc_matrix:
        """Return the gathered vectorized J11 block.

        :param step_size: Positive local step size.
        :return: One-by-one analytic derivative Jacobian in CSC storage.
        """

        if step_size > 0.0:
            self.jacobian_evaluations += 1
            derivative: float = 2.0 * self.quadratic_rate * self.gathered_state_value
            return sp.csc_matrix(np.array(((derivative,),), dtype=float))
        else:
            raise AssertionError("Current-point vector J11 is invalid")

    def get_j12_vec(self, step_size: float) -> sp.csc_matrix:
        """Return the gathered vectorized J12 block.

        :param step_size: Positive local step size.
        :return: One-by-zero CSC matrix.
        """

        if step_size > 0.0:
            return sp.csc_matrix((1, 0), dtype=float)
        else:
            raise AssertionError("Current-point vector J12 is invalid")

    def get_j21_vec(
        self,
        x_snapshot_or_step: np.ndarray | float,
        dx_snapshot: np.ndarray | None = None,
        step_size: float | None = None,
    ) -> sp.csc_matrix:
        """Return the gathered vectorized J21 block.

        :param x_snapshot_or_step: Current network snapshot for the full
            vectorized path, or the step for the gathered path.
        :param dx_snapshot: Current differential snapshot when supplied.
        :param step_size: Positive local step size when supplied separately.
        :return: Zero-by-one CSC matrix.
        """

        if isinstance(x_snapshot_or_step, np.ndarray):
            if dx_snapshot is not None and step_size is not None:
                return self.get_j21(
                    x_snapshot_or_step,
                    dx_snapshot,
                    step_size,
                )
            else:
                raise AssertionError("Full-vector J21 inputs are incomplete")
        else:
            gathered_step_size: float = float(x_snapshot_or_step)
            if dx_snapshot is None and step_size is None and gathered_step_size > 0.0:
                return sp.csc_matrix((0, 1), dtype=float)
            else:
                raise AssertionError("Gathered J21 inputs are invalid")

    def get_j22_vec(
        self,
        x_snapshot_or_step: np.ndarray | float,
        dx_snapshot: np.ndarray | None = None,
        step_size: float | None = None,
    ) -> sp.csc_matrix:
        """Return the gathered vectorized J22 block.

        :param x_snapshot_or_step: Current network snapshot for the full
            vectorized path, or the step for the gathered path.
        :param dx_snapshot: Current differential snapshot when supplied.
        :param step_size: Positive local step size when supplied separately.
        :return: Empty CSC matrix.
        """

        if isinstance(x_snapshot_or_step, np.ndarray):
            if dx_snapshot is not None and step_size is not None:
                return self.get_j22(
                    x_snapshot_or_step,
                    dx_snapshot,
                    step_size,
                )
            else:
                raise AssertionError("Full-vector J22 inputs are incomplete")
        else:
            gathered_step_size: float = float(x_snapshot_or_step)
            if dx_snapshot is None and step_size is None and gathered_step_size > 0.0:
                return sp.csc_matrix((0, 0), dtype=float)
            else:
                raise AssertionError("Gathered J22 inputs are invalid")

    def report_progress2(self, step_index: int, step_count: int) -> None:
        """Validate deterministic solver progress.

        :param step_index: Zero-based macro-step index.
        :param step_count: Positive macro-step count.
        :return: None.
        """

        if 0 <= step_index < step_count:
            pass
        else:
            raise AssertionError("Current-point progress is invalid")

    def initialize_fmu_me_devices(
        self,
        x_snapshot: np.ndarray,
        time_value: float,
    ) -> None:
        """Validate ME ownership initialization.

        :param x_snapshot: Accepted network snapshot.
        :param time_value: Initial solver time.
        :return: None.
        """

        if x_snapshot.size == 1 and math.isfinite(time_value):
            self.me_initialize_count += 1
        else:
            raise AssertionError("Current-point ME initialization is invalid")

    def initialize_fmu_cs_devices(
        self,
        x_snapshot: np.ndarray,
        time_value: float,
    ) -> None:
        """Expose or suppress CS ownership for the requested scenario.

        :param x_snapshot: Accepted network snapshot.
        :param time_value: Initial solver time.
        :return: None.
        """

        if self.enable_cs and x_snapshot.size == 1 and math.isfinite(time_value):
            self.cs_initialize_count += 1
            if self.initial_state_value is not None:
                x_snapshot[0] = self.initial_state_value
            else:
                pass
        else:
            raise AttributeError("Synthetic problem has no active CS owner")

    def advance_fmu_me_devices(
        self,
        t: float,
        x_snapshot: np.ndarray,
        h: float,
    ) -> None:
        """Record each accepted or corrected network point presented to ME.

        :param t: Accepted local time.
        :param x_snapshot: Network point used to derive FMU inputs.
        :param h: Positive candidate step size.
        :return: None.
        """

        if math.isfinite(t) and x_snapshot.size == 1 and h > 0.0:
            self.me_advance_snapshots.append(x_snapshot.copy())
            self.operation_log.append("me")
        else:
            raise AssertionError("Current-point ME advance is invalid")
        if self.pending_retry_time is not None:
            self.pending_retry_time = None
        elif not self.event_emitted and np.isclose(x_snapshot[0], 1.0):
            self.pending_retry_time = self.initial_event_time
            self.event_emitted = self.initial_event_time is not None
        elif not self.event_emitted:
            self.pending_retry_time = self.corrected_event_time
            self.event_emitted = self.corrected_event_time is not None
        else:
            pass

    def prepare_fmu_me_state_event_retry(self) -> float | None:
        """Return the configured pending event boundary.

        :return: Pending retry time or None.
        """

        return self.pending_retry_time

    def advance_fmu_cs_devices(
        self,
        t: float,
        x_snapshot: np.ndarray,
        h: float,
    ) -> bool:
        """Record a real or no-op CS advancement result.

        :param t: Accepted local time.
        :param x_snapshot: Accepted network snapshot.
        :param h: Positive communication step.
        :return: Configured advancement result.
        """

        co_simulation_advanced: bool = False
        if (
            math.isfinite(t)
            and x_snapshot.size == 1
            and h > 0.0
        ):
            self.cs_advance_count += 1
            self.operation_log.append("cs")
            co_simulation_advanced = self.cs_advance_result
        else:
            raise AssertionError("Current-point CS advance is invalid")
        return co_simulation_advanced

    def get_next_forced_event_time(
        self,
        lower_time: float,
        upper_time: float,
    ) -> float | None:
        """Return a pending localized event inside the active interval.

        :param lower_time: Accepted lower interval boundary.
        :param upper_time: Candidate upper interval boundary.
        :return: Pending event time when it lies strictly inside.
        """

        retry_time: float | None = self.pending_retry_time
        if retry_time is not None and lower_time < retry_time < upper_time:
            return retry_time
        else:
            return None

    def resolve_fmu_me_devices(self, accepted: bool) -> None:
        """Record whether the solver accepted the current ME candidate.

        :param accepted: True for accepted candidates.
        :return: None.
        """

        self.resolve_acceptances.append(accepted)
        if accepted:
            self.pending_retry_time = None
        else:
            pass

    def resolve_manufacturer_native_boundary(
        self,
        t: float,
        x: np.ndarray,
    ) -> None:
        """Validate the committed manufacturer-native solver boundary.

        :param t: Converged boundary time.
        :param x: Converged network state.
        :return: None.
        """

        if math.isfinite(t) and x.size == 1:
            self.operation_log.append("native_commit")
        else:
            raise AssertionError("Current-point native commit is invalid")

    def close_fmu_me_devices(self) -> None:
        """Close the synthetic ME owner.

        :return: None.
        """

        self.operation_log.append("close_me")
        self.me_close_count += 1

    def close_fmu_cs_devices(self) -> None:
        """Close the synthetic CS owner.

        :return: None.
        """

        self.operation_log.append("close_cs")
        self.cs_close_count += 1


def _evaluate_linear_decay_derivative(
    time_value: float,
    continuous_state_values: tuple[float, ...],
    writable_values: tuple[float, ...],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Evaluate the autonomous linear decay used by solver contracts.

    :param time_value: Finite solver probe time.
    :param continuous_state_values: Continuous state presented by the solver.
    :param writable_values: One-element tuple containing the decay rate.
    :return: Linear derivatives and an empty readable-output tuple.
    """

    if math.isfinite(time_value) and len(writable_values) == 1:
        decay_rate: float = writable_values[0]
    else:
        raise AssertionError("Linear-decay probe has an invalid contract")
    derivative_values: list[float] = [0.0] * len(continuous_state_values)
    state_index: int
    for state_index in range(len(continuous_state_values)):
        derivative_values[state_index] = (
            -decay_rate * continuous_state_values[state_index]
        )
    return tuple(derivative_values), tuple()


def _build_mock_backward_euler_adapter(
    solver_policy: FmuMeSolverPolicy | None = None,
) -> tuple[FmuMeDeviceAdapter, Mock]:
    """Build a runtime-free adapter for deterministic solver evaluation.

    :param solver_policy: Optional policy override for boundary tests.
    :return: Adapter and coordinator mock exposing all solver probes.
    """

    if solver_policy is None:
        active_policy: FmuMeSolverPolicy = FmuMeSolverPolicy(
            integration_method=DynamicIntegrationMethod.DaeBackEuler,
            absolute_tolerance=1.0e-8,
            relative_tolerance=1.0e-8,
            maximum_newton_iterations=20,
            maximum_continuous_states=128,
        )
    else:
        active_policy = solver_policy
    coordinator: Mock = Mock()
    coordinator.evaluate_probe.side_effect = _evaluate_linear_decay_derivative
    adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    adapter.spec = SimpleNamespace(
        input_variable_names=("decay_rate",),
        output_variable_names=tuple(),
        output_bindings=tuple(),
        state_variable_names=("state",),
        maximum_event_iterations=2,
    )
    adapter.solver_policy = active_policy
    adapter.runtime_host = None
    adapter.fmi_three_coordinator = coordinator
    adapter.localized_state_event_time = None
    adapter._fmi_one_state_value_references = tuple()
    adapter.fmi_two_next_event_time = None
    adapter.pending_candidate_input_values = None
    adapter.fmi_two_accepted_input_values = (1.0,)
    return adapter, coordinator


def test_fmi_one_event_update_converges_and_refreshes_changed_states() -> None:
    """Converge FMI 1 event iteration and refresh state values when declared."""

    adapter: FmuMeDeviceAdapter
    coordinator: Mock
    adapter, coordinator = _build_mock_backward_euler_adapter()
    runtime_host: Mock = Mock()
    runtime_host.get_continuous_states.return_value = [2.0]
    runtime_host.event_update_fmi_one.return_value = FmiOneEventUpdate(
        iteration_converged=True,
        state_value_references_changed=False,
        state_values_changed=False,
        terminate_simulation=False,
        next_event_time=None,
    )
    adapter.runtime_host = runtime_host
    adapter.fmi_three_coordinator = None
    adapter.state_vector = np.array([1.0], dtype=float)
    adapter._settle_fmi_one_event(
        event_update=FmiOneEventUpdate(
            iteration_converged=False,
            state_value_references_changed=False,
            state_values_changed=True,
            terminate_simulation=False,
            next_event_time=1.0,
        ),
        entry_time=0.0,
        evaluation_budget=FmuMeEvaluationBudget(3),
    )
    assert adapter.get_state_vector().tolist() == [2.0]
    assert adapter.fmi_two_next_event_time is None
    runtime_host.get_continuous_states.assert_called_once()
    runtime_host.event_update_fmi_one.assert_called_once()


def test_fmi_one_event_update_refreshes_state_value_references() -> None:
    """Refresh FMI 1 state identities when the event information requests it."""

    adapter: FmuMeDeviceAdapter
    coordinator: Mock
    adapter, coordinator = _build_mock_backward_euler_adapter()
    runtime_host: Mock = Mock()
    runtime_host.get_state_value_references.return_value = (17,)
    adapter.runtime_host = runtime_host
    adapter.fmi_three_coordinator = None
    adapter._settle_fmi_one_event(
        event_update=FmiOneEventUpdate(
            iteration_converged=True,
            state_value_references_changed=True,
            state_values_changed=False,
            terminate_simulation=False,
            next_event_time=2.0,
        ),
        entry_time=1.0,
        evaluation_budget=FmuMeEvaluationBudget(1),
    )
    assert adapter._fmi_one_state_value_references == (17,)
    assert adapter.fmi_two_next_event_time == 2.0
    runtime_host.get_state_value_references.assert_called_once()


def test_fmi_one_event_update_stops_on_termination_request() -> None:
    """Close an FMI 1 runtime immediately when event information terminates."""

    adapter: FmuMeDeviceAdapter
    coordinator: Mock
    adapter, coordinator = _build_mock_backward_euler_adapter()
    runtime_host: Mock = Mock()
    adapter.runtime_host = runtime_host
    adapter.fmi_three_coordinator = None
    with pytest.raises(RuntimeError, match="requested simulation termination"):
        adapter._settle_fmi_one_event(
            event_update=FmiOneEventUpdate(
                iteration_converged=True,
                state_value_references_changed=False,
                state_values_changed=False,
                terminate_simulation=True,
                next_event_time=None,
            ),
            entry_time=0.0,
            evaluation_budget=FmuMeEvaluationBudget(1),
        )
    runtime_host.close.assert_called_once()
    assert adapter.runtime_host is None


def _evaluate_linear_test_event_indicator(
    time_value: float,
    continuous_state_values: tuple[float, ...],
    point_is_presented: bool,
    evaluation_budget: FmuMeEvaluationBudget,
) -> tuple[float, ...]:
    """Evaluate two independent state indicators during localization.

    :param time_value: Probe time supplied by the localization algorithm.
    :param continuous_state_values: Backward Euler continuous-state vector.
    :param point_is_presented: Whether the solver already presented the point.
    :param evaluation_budget: Shared evaluation budget passed by the adapter.
    :return: Indicators crossing when the state decays through 0.7 and 0.6.
    """

    if math.isfinite(time_value) and point_is_presented:
        pass
    else:
        raise AssertionError("Synthetic localization probe was not presented")
    if evaluation_budget.get_consumed_count() > 0:
        evaluation_budget.consume()
    else:
        raise AssertionError("Synthetic localization received an unused budget")
    return (
        continuous_state_values[0] - 0.7,
        continuous_state_values[0] - 0.6,
    )


def _evaluate_constant_test_derivative(
    time_value: float,
    continuous_state_values: tuple[float, ...],
    writable_values: tuple[float, ...],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Return a constant derivative for method-consistent localization.

    :param time_value: Finite probe time.
    :param continuous_state_values: Current continuous states.
    :param writable_values: Finite synthetic writable vector.
    :return: Constant derivatives and no readable values.
    """

    writable_values_are_finite: bool = all(
        math.isfinite(writable_value) for writable_value in writable_values
    )
    if math.isfinite(time_value) and writable_values_are_finite:
        pass
    else:
        raise AssertionError("Synthetic derivative probe contains a non-finite value")
    derivative_values: list[float] = [3.0] * len(continuous_state_values)
    return tuple(derivative_values), tuple()


def _build_synthetic_localization_adapter(
    accepted_time: float,
    candidate_time: float,
    accepted_states: tuple[float, ...],
    candidate_states: tuple[float, ...],
    accepted_indicators: tuple[float, ...],
    candidate_indicators: tuple[float, ...],
    accepted_inputs: tuple[float, ...] | None = None,
    candidate_inputs: tuple[float, ...] | None = None,
) -> tuple[FmuMeDeviceAdapter, Mock]:
    """Build one bounded localization adapter without opening an FMU.

    :param accepted_time: Stored accepted time.
    :param candidate_time: Stored candidate time.
    :param accepted_states: Accepted continuous states.
    :param candidate_states: Candidate continuous states.
    :param accepted_indicators: Accepted indicator vector.
    :param candidate_indicators: Candidate indicator vector.
    :param accepted_inputs: Optional accepted scalar input vector.
    :param candidate_inputs: Optional candidate scalar input vector.
    :return: Synthetic adapter and its coordinator mock.
    """

    coordinator: Mock = Mock()
    coordinator.has_pending_candidate.return_value = True
    if accepted_inputs is None and candidate_inputs is None:
        if len(accepted_states) == 0:
            input_variable_names: tuple[str, ...] = tuple()
            accepted_input_values: tuple[float, ...] = tuple()
        else:
            input_variable_names = ("decay_rate",)
            accepted_input_values = (1.0,)
        candidate_input_values: tuple[float, ...] = accepted_input_values
    else:
        if (
            accepted_inputs is not None
            and candidate_inputs is not None
            and len(accepted_inputs) == len(candidate_inputs)
        ):
            pass
        else:
            raise AssertionError("Synthetic localization inputs are incomplete")
        input_variable_names = tuple(
            f"coupling_input_{input_index}"
            for input_index in range(len(accepted_inputs))
        )
        accepted_input_values = accepted_inputs
        candidate_input_values = candidate_inputs
    if len(accepted_states) == 0:
        coordinator.evaluate_probe.side_effect = _evaluate_constant_test_derivative
    else:
        coordinator.evaluate_probe.side_effect = _evaluate_linear_decay_derivative
    coordinator.evaluate_event_indicators_probe.side_effect = (
        _evaluate_linear_test_event_indicator
    )
    adapter: FmuMeDeviceAdapter = object.__new__(FmuMeDeviceAdapter)
    adapter.spec = SimpleNamespace(
        input_variable_names=input_variable_names,
        output_variable_names=tuple(),
    )
    adapter.solver_policy = FmuMeSolverPolicy(
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        absolute_tolerance=1.0e-8,
        relative_tolerance=1.0e-8,
        maximum_newton_iterations=20,
        maximum_continuous_states=128,
    )
    adapter.runtime_host = None
    adapter.fmi_three_coordinator = coordinator
    adapter.state_vector = np.array(candidate_states, dtype=float)
    adapter.pending_time = candidate_time
    adapter.pending_candidate_state_values = candidate_states
    adapter.pending_candidate_input_values = candidate_input_values
    candidate_derivative_values: list[float] = [0.0] * len(candidate_states)
    candidate_state_index: int
    for candidate_state_index in range(len(candidate_states)):
        candidate_derivative_values[candidate_state_index] = (
            -candidate_states[candidate_state_index]
        )
    adapter.pending_candidate_derivative_values = tuple(candidate_derivative_values)
    adapter.pending_candidate_readable_values = tuple()
    adapter.pending_candidate_event_indicators = candidate_indicators
    adapter.pending_accepted_time = accepted_time
    adapter.pending_accepted_state_values = accepted_states
    adapter.pending_accepted_input_values = accepted_input_values
    accepted_derivative_values: list[float] = [0.0] * len(accepted_states)
    accepted_state_index: int
    for accepted_state_index in range(len(accepted_states)):
        accepted_derivative_values[accepted_state_index] = (
            -accepted_states[accepted_state_index]
        )
    adapter.pending_accepted_derivative_values = tuple(accepted_derivative_values)
    adapter.pending_accepted_readable_values = tuple()
    adapter.pending_accepted_event_indicators = accepted_indicators
    adapter.localized_state_event_time = None
    adapter.fmi_two_next_event_time = None
    adapter.fmi_two_accepted_input_values = accepted_input_values
    adapter.fmi_two_accepted_derivative_values = None
    adapter.fmi_two_accepted_readable_values = None
    adapter.fmi_two_accepted_event_indicators = None
    adapter.initialized = True
    return adapter, coordinator


def _evaluate_time_test_event_indicator(
    time_value: float,
    continuous_state_values: tuple[float, ...],
    point_is_presented: bool,
    evaluation_budget: FmuMeEvaluationBudget,
) -> tuple[float, ...]:
    """Evaluate one time-only indicator for a zero-state FMU.

    :param time_value: Probe time supplied by localization.
    :param continuous_state_values: Empty continuous-state vector.
    :param point_is_presented: Whether the point is already visible.
    :param evaluation_budget: Shared runtime-call budget.
    :return: One indicator crossing at 0.4 seconds.
    """

    if (
        len(continuous_state_values) == 0
        and point_is_presented
        and math.isfinite(time_value)
    ):
        evaluation_budget.consume()
    else:
        raise AssertionError("Synthetic zero-state probe is invalid")
    return (time_value - 0.4,)


def test_fmi_me_option_policy_schema() -> None:
    """Keep RMS and EMT Model Exchange policy defaults identical and persisted.

    :return: None.
    """

    rms_options: RmsOptions = RmsOptions()
    emt_options: EmtOptions = EmtOptions()
    expected_values: tuple[float | int, ...] = (
        1.0e-8,
        1.0e-8,
        20,
        128,
        100000,
    )
    rms_values: tuple[float | int, ...] = (
        rms_options.fmi_me_newton_absolute_tolerance,
        rms_options.fmi_me_newton_relative_tolerance,
        rms_options.fmi_me_newton_max_iterations,
        rms_options.fmi_me_max_continuous_states,
        rms_options.fmi_me_max_runtime_evaluations_per_step,
    )
    emt_values: tuple[float | int, ...] = (
        emt_options.fmi_me_newton_absolute_tolerance,
        emt_options.fmi_me_newton_relative_tolerance,
        emt_options.fmi_me_newton_max_iterations,
        emt_options.fmi_me_max_continuous_states,
        emt_options.fmi_me_max_runtime_evaluations_per_step,
    )
    persisted_keys: tuple[str, ...] = (
        "fmi_me_newton_absolute_tolerance",
        "fmi_me_newton_relative_tolerance",
        "fmi_me_newton_max_iterations",
        "fmi_me_max_continuous_states",
        "fmi_me_max_runtime_evaluations_per_step",
    )

    assert rms_values == expected_values
    assert emt_values == expected_values
    for persisted_key in persisted_keys:
        assert persisted_key in rms_options.registered_properties
        assert persisted_key in emt_options.registered_properties

    # Policies copy validated owner options without retaining the problem.
    rms_policy: FmuMeSolverPolicy = _build_fmu_me_solver_policy(rms_options)
    emt_me_options: EmtOptions = EmtOptions(
        integration_method=DynamicIntegrationMethod.DaeBackEuler
    )
    emt_policy: FmuMeSolverPolicy = _build_fmu_me_solver_policy(emt_me_options)
    assert rms_policy.maximum_continuous_states == 128
    assert emt_policy.integration_method == DynamicIntegrationMethod.DaeBackEuler
    assert RmsOptions(
        fmi_me_max_runtime_evaluations_per_step=100001
    ).fmi_me_max_runtime_evaluations_per_step == 100001

    # Invalid values fail at the owner or policy boundary before native use.
    with pytest.raises(ValueError, match="absolute tolerance"):
        RmsOptions(fmi_me_newton_absolute_tolerance=0.0)
    with pytest.raises(ValueError, match="relative tolerance"):
        EmtOptions(fmi_me_newton_relative_tolerance=math.nan)
    with pytest.raises(ValueError, match="iteration limit"):
        RmsOptions(fmi_me_newton_max_iterations=True)
    with pytest.raises(ValueError, match="state limit"):
        EmtOptions(fmi_me_max_continuous_states=129)
    with pytest.raises(ValueError, match="runtime evaluation limit"):
        RmsOptions(fmi_me_max_runtime_evaluations_per_step=10_000_001)
    with pytest.raises(ValueError, match="absolute tolerance"):
        FmuMeSolverPolicy(
            integration_method=DynamicIntegrationMethod.DaeBackEuler,
            absolute_tolerance=math.inf,
            relative_tolerance=1.0e-8,
            maximum_newton_iterations=20,
            maximum_continuous_states=128,
        )


def test_fmi_me_policy_rejects_unsupported_method_before_runtime() -> None:
    """Reject attached Model Exchange use under another solver family.

    :return: None.
    """

    with pytest.raises(RuntimeError, match="DaeBackEuler"):
        FmuMeSolverPolicy(
            integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
            absolute_tolerance=1.0e-8,
            relative_tolerance=1.0e-8,
            maximum_newton_iterations=20,
            maximum_continuous_states=128,
        )


def test_fmi_me_runtime_budget_call_mapping() -> None:
    """Map FMI 2 and FMI 3 native transactions and keep them fail-closed.

    :return: None.
    """

    evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(2)

    evaluation_budget.consume()
    evaluation_budget.consume()
    assert evaluation_budget.get_consumed_count() == 2
    with pytest.raises(RuntimeError, match="before the next native call"):
        evaluation_budget.consume()
    assert evaluation_budget.get_consumed_count() == 2

    fmi_three_adapter: FmuMeDeviceAdapter
    fmi_three_coordinator: Mock
    fmi_three_adapter, fmi_three_coordinator = (
        _build_mock_backward_euler_adapter()
    )
    fmi_three_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(1)
    fmi_three_derivatives: np.ndarray
    ignored_readable_values: tuple[float, ...] | None
    fmi_three_derivatives, ignored_readable_values = (
        fmi_three_adapter._evaluate_derivatives_for_state(
            time_value=0.25,
            state_values=np.array([2.0], dtype=float),
            input_values=dict(decay_rate=0.5),
            evaluation_budget=fmi_three_budget,
        )
    )
    assert fmi_three_derivatives.tolist() == pytest.approx([-1.0])
    assert fmi_three_budget.get_consumed_count() == 1
    fmi_three_coordinator.evaluate_probe.assert_called_once()

    fmi_two_adapter: FmuMeDeviceAdapter
    ignored_coordinator: Mock
    fmi_two_adapter, ignored_coordinator = _build_mock_backward_euler_adapter()
    runtime_host: Mock = Mock()
    runtime_host.get_derivatives.return_value = [-1.0]
    runtime_host.get_real.return_value = dict()
    fmi_two_adapter.runtime_host = runtime_host
    fmi_two_adapter.fmi_three_coordinator = None
    fmi_two_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(1)
    fmi_two_derivatives: np.ndarray
    fmi_two_derivatives, ignored_readable_values = (
        fmi_two_adapter._evaluate_derivatives_for_state(
            time_value=0.25,
            state_values=np.array([2.0], dtype=float),
            input_values=dict(decay_rate=0.5),
            evaluation_budget=fmi_two_budget,
        )
    )
    assert fmi_two_derivatives.tolist() == pytest.approx([-1.0])
    assert fmi_two_budget.get_consumed_count() == 1
    runtime_host.set_time.assert_called_once_with(0.25)
    runtime_host.set_continuous_states.assert_called_once_with([2.0])
    runtime_host.get_derivatives.assert_called_once()

    # The largest supported Backward Euler solve has one initial probe, one
    # base residual, and one Jacobian column plus one corrected residual per
    # Newton iteration. A non-retained localization probe adds one indicator.
    maximum_state_count: int = 128
    maximum_newton_iterations: int = 20
    retained_endpoint_evaluation_bound: int = (
        2 + maximum_newton_iterations * (maximum_state_count + 1)
    )
    non_retained_point_evaluation_bound: int = (
        retained_endpoint_evaluation_bound + 1
    )
    assert retained_endpoint_evaluation_bound == 2582
    assert non_retained_point_evaluation_bound == 2583

    # Drive the actual Newton loop through all 20 iterations. Each synthetic
    # Jacobian is the identity, while the last corrected residual converges
    # only on iteration 20, making the theoretical bound observable.
    bound_policy: FmuMeSolverPolicy = FmuMeSolverPolicy(
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        absolute_tolerance=1.0e-8,
        relative_tolerance=1.0e-8,
        maximum_newton_iterations=maximum_newton_iterations,
        maximum_continuous_states=maximum_state_count,
    )
    bound_adapter: FmuMeDeviceAdapter
    bound_coordinator: Mock
    bound_adapter, bound_coordinator = _build_mock_backward_euler_adapter(
        solver_policy=bound_policy
    )
    bound_probe_results: list[
        tuple[tuple[float, ...], tuple[float, ...]]
    ] = [(tuple(), tuple())] * retained_endpoint_evaluation_bound
    zero_derivatives: tuple[float, ...] = tuple(
        [0.0] * maximum_state_count
    )
    bound_probe_results[0] = (zero_derivatives, tuple())
    bound_probe_results[1] = (
        tuple([1.0] * maximum_state_count),
        tuple(),
    )
    probe_result_index: int = 2
    bound_iteration_index: int
    for bound_iteration_index in range(maximum_newton_iterations):
        jacobian_derivative_value: float = float(bound_iteration_index + 1)
        jacobian_derivatives: tuple[float, ...] = tuple(
            [jacobian_derivative_value] * maximum_state_count
        )
        jacobian_column_index: int
        for jacobian_column_index in range(maximum_state_count):
            bound_probe_results[probe_result_index] = (
                jacobian_derivatives,
                tuple(),
            )
            probe_result_index += 1
        if bound_iteration_index == maximum_newton_iterations - 1:
            endpoint_derivative_value: float = float(
                maximum_newton_iterations
            )
        else:
            endpoint_derivative_value = float(bound_iteration_index + 2)
        bound_probe_results[probe_result_index] = (
            tuple([endpoint_derivative_value] * maximum_state_count),
            tuple(),
        )
        probe_result_index += 1
    assert probe_result_index == retained_endpoint_evaluation_bound

    bound_coordinator.evaluate_probe.side_effect = bound_probe_results.copy()
    retained_bound_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(2582)
    retained_bound_states: np.ndarray
    retained_bound_derivatives: np.ndarray
    retained_bound_readable_values: tuple[float, ...] | None
    (
        retained_bound_states,
        retained_bound_derivatives,
        retained_bound_readable_values,
    ) = bound_adapter._solve_backward_euler_candidate(
        current_time=0.0,
        step_size=0.1,
        accepted_state_values=np.zeros(maximum_state_count, dtype=float),
        input_values=dict(decay_rate=1.0),
        evaluation_budget=retained_bound_budget,
    )
    assert retained_bound_states.tolist() == pytest.approx(
        [2.0] * maximum_state_count
    )
    assert retained_bound_derivatives.tolist() == pytest.approx(
        [20.0] * maximum_state_count
    )
    assert retained_bound_readable_values == tuple()
    assert bound_coordinator.evaluate_probe.call_count == 2582
    assert retained_bound_budget.get_consumed_count() == 2582
    with pytest.raises(RuntimeError, match="before the next native call"):
        retained_bound_budget.consume()

    # The FMI 3 retained candidate transaction adds exactly one charge after
    # the maximal point solve, producing the 2583 non-retained boundary.
    bound_coordinator.reset_mock()
    bound_coordinator.evaluate_probe.side_effect = bound_probe_results.copy()
    bound_coordinator.get_accepted_point.return_value = (
        0.0,
        tuple([0.0] * maximum_state_count),
        (1.0,),
        tuple(),
        (0.5,),
        tuple([1.0] * maximum_state_count),
        zero_derivatives,
    )
    bound_coordinator.evaluate_candidate.return_value = (
        tuple([20.0] * maximum_state_count),
        tuple(),
        (0.25,),
    )
    bound_adapter.state_vector = np.zeros(maximum_state_count, dtype=float)
    non_retained_bound_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(2583)
    bound_adapter._prepare_bound_step(
        current_time=0.0,
        step_size=0.1,
        input_values=dict(decay_rate=1.0),
        evaluation_budget=non_retained_bound_budget,
    )
    assert bound_coordinator.evaluate_probe.call_count == 2582
    bound_coordinator.evaluate_candidate.assert_called_once()
    assert non_retained_bound_budget.get_consumed_count() == 2583

    default_limit_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(100000)
    default_operation_index: int
    for default_operation_index in range(100000):
        default_limit_budget.consume()
    with pytest.raises(RuntimeError, match="before the next native call"):
        default_limit_budget.consume()
    raised_limit_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(100001)
    raised_operation_index: int
    for raised_operation_index in range(100001):
        raised_limit_budget.consume()
    assert raised_limit_budget.get_consumed_count() == 100001

    # FMI 2 exposes output and indicator reads separately after the solver
    # probes, while FMI 3 groups candidate derivatives and outputs and adds one
    # compound candidate transaction for the indicator and retained snapshot.
    retained_fmi_two_adapter: FmuMeDeviceAdapter
    retained_fmi_two_coordinator: Mock
    retained_fmi_two_adapter, retained_fmi_two_coordinator = (
        _build_mock_backward_euler_adapter()
    )
    retained_fmi_two_runtime: Mock = Mock()
    retained_fmi_two_runtime.get_derivatives.return_value = [-1.0]
    retained_fmi_two_runtime.get_real.return_value = dict()
    retained_fmi_two_runtime.get_event_indicators.return_value = (0.25,)
    retained_fmi_two_adapter.runtime_host = retained_fmi_two_runtime
    retained_fmi_two_adapter.fmi_three_coordinator = None
    retained_fmi_two_adapter.state_vector = np.array([1.0], dtype=float)
    retained_fmi_two_adapter.fmi_two_accepted_derivative_values = (-1.0,)
    retained_fmi_two_adapter.fmi_two_accepted_readable_values = tuple()
    retained_fmi_two_adapter.fmi_two_accepted_event_indicators = (0.5,)
    retained_fmi_two_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(20)
    retained_fmi_two_adapter._prepare_bound_step(
        current_time=0.0,
        step_size=0.5,
        input_values=dict(decay_rate=1.0),
        evaluation_budget=retained_fmi_two_budget,
    )
    retained_fmi_two_solver_calls: int = (
        retained_fmi_two_runtime.get_derivatives.call_count
    )
    assert retained_fmi_two_runtime.set_time.call_count == (
        retained_fmi_two_solver_calls
    )
    assert retained_fmi_two_runtime.set_continuous_states.call_count == (
        retained_fmi_two_solver_calls
    )
    assert retained_fmi_two_runtime.get_real.call_count == (
        retained_fmi_two_solver_calls + 1
    )
    assert retained_fmi_two_runtime.get_event_indicators.call_count == 1
    assert retained_fmi_two_budget.get_consumed_count() == (
        retained_fmi_two_solver_calls + 2
    )

    # FMI 2 has no native checkpoint contract. Rejection therefore restores
    # and validates the accepted visible point with one compound evaluation
    # plus one indicator read.
    retained_fmi_two_runtime.reset_mock()
    retained_fmi_two_runtime.get_derivatives.return_value = [-1.0]
    retained_fmi_two_runtime.get_real.return_value = dict()
    retained_fmi_two_runtime.get_event_indicators.return_value = (0.5,)
    fmi_two_rejection_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(2)
    retained_fmi_two_adapter.resolve_pending_step(
        accepted=False,
        evaluation_budget=fmi_two_rejection_budget,
    )
    assert fmi_two_rejection_budget.get_consumed_count() == 2
    assert retained_fmi_two_runtime.get_derivatives.call_count == 1
    assert retained_fmi_two_runtime.get_real.call_count == 1
    assert retained_fmi_two_runtime.get_event_indicators.call_count == 1

    # A smooth accepted FMI 2 candidate requires no native transition when
    # completedIntegratorStep is not declared by the FMU.
    retained_fmi_two_runtime.get_event_indicators.return_value = (0.25,)
    smooth_candidate_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(20)
    retained_fmi_two_adapter._prepare_bound_step(
        current_time=0.0,
        step_size=0.5,
        input_values=dict(decay_rate=1.0),
        evaluation_budget=smooth_candidate_budget,
    )
    retained_fmi_two_runtime.reset_mock()
    retained_fmi_two_runtime.needs_completed_integrator_step.return_value = False
    fmi_two_smooth_acceptance_budget: FmuMeEvaluationBudget = (
        FmuMeEvaluationBudget(1)
    )
    retained_fmi_two_adapter.resolve_pending_step(
        accepted=True,
        evaluation_budget=fmi_two_smooth_acceptance_budget,
    )
    assert fmi_two_smooth_acceptance_budget.get_consumed_count() == 0
    retained_fmi_two_runtime.completed_integrator_step.assert_not_called()
    retained_fmi_two_runtime.enter_event_mode.assert_not_called()

    # The optional completedIntegratorStep boundary has one charge even when
    # it does not request Event Mode.
    completed_candidate_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(20)
    retained_fmi_two_runtime.get_derivatives.return_value = [-1.0]
    retained_fmi_two_runtime.get_real.return_value = dict()
    retained_fmi_two_runtime.get_event_indicators.return_value = (0.25,)
    retained_fmi_two_adapter._prepare_bound_step(
        current_time=0.5,
        step_size=0.5,
        input_values=dict(decay_rate=1.0),
        evaluation_budget=completed_candidate_budget,
    )
    retained_fmi_two_runtime.reset_mock()
    retained_fmi_two_runtime.needs_completed_integrator_step.return_value = True
    retained_fmi_two_runtime.completed_integrator_step.return_value = (
        False,
        False,
    )
    fmi_two_completed_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(1)
    retained_fmi_two_adapter.resolve_pending_step(
        accepted=True,
        evaluation_budget=fmi_two_completed_budget,
    )
    assert fmi_two_completed_budget.get_consumed_count() == 1
    retained_fmi_two_runtime.completed_integrator_step.assert_called_once()
    retained_fmi_two_runtime.enter_event_mode.assert_not_called()

    # Event acceptance charges entry, one discrete update, return to
    # continuous time, state read, derivative/output evaluation, and indicator.
    event_candidate_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(20)
    retained_fmi_two_runtime.get_derivatives.return_value = [-1.0]
    retained_fmi_two_runtime.get_real.return_value = dict()
    retained_fmi_two_runtime.get_event_indicators.return_value = (0.25,)
    retained_fmi_two_adapter._prepare_bound_step(
        current_time=1.0,
        step_size=0.5,
        input_values=dict(decay_rate=1.0),
        evaluation_budget=event_candidate_budget,
    )
    event_state_value: float = float(retained_fmi_two_adapter.state_vector[0])
    retained_fmi_two_runtime.reset_mock()
    retained_fmi_two_runtime.needs_completed_integrator_step.return_value = False
    retained_fmi_two_runtime.new_discrete_states.return_value = FmiTwoEventUpdate(
        discrete_states_need_update=False,
        terminate_simulation=False,
        nominals_changed=False,
        states_changed=False,
        next_event_time=None,
    )
    retained_fmi_two_runtime.get_continuous_states.return_value = [
        event_state_value
    ]
    retained_fmi_two_runtime.get_derivatives.return_value = [-1.0]
    retained_fmi_two_runtime.get_real.return_value = dict()
    retained_fmi_two_runtime.get_event_indicators.return_value = (0.25,)
    fmi_two_event_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(6)
    retained_fmi_two_adapter.resolve_pending_step(
        accepted=True,
        importer_detected_event=True,
        evaluation_budget=fmi_two_event_budget,
    )
    assert fmi_two_event_budget.get_consumed_count() == 6
    retained_fmi_two_runtime.enter_event_mode.assert_called_once()
    retained_fmi_two_runtime.new_discrete_states.assert_called_once()
    retained_fmi_two_runtime.enter_continuous_time_mode.assert_called_once()
    retained_fmi_two_runtime.get_continuous_states.assert_called_once()
    retained_fmi_two_runtime.get_derivatives.assert_called_once()
    retained_fmi_two_runtime.get_real.assert_called_once()
    retained_fmi_two_runtime.get_event_indicators.assert_called_once()

    retained_fmi_three_adapter: FmuMeDeviceAdapter
    retained_fmi_three_coordinator: Mock
    retained_fmi_three_adapter, retained_fmi_three_coordinator = (
        _build_mock_backward_euler_adapter()
    )
    retained_fmi_three_adapter.state_vector = np.array([1.0], dtype=float)
    retained_fmi_three_coordinator.get_accepted_point.return_value = (
        0.0,
        (1.0,),
        (1.0,),
        tuple(),
        (0.5,),
        (1.0,),
        (-1.0,),
    )
    retained_fmi_three_coordinator.evaluate_candidate.return_value = (
        (-2.0 / 3.0,),
        tuple(),
        (0.25,),
    )
    retained_fmi_three_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(20)
    retained_fmi_three_adapter._prepare_bound_step(
        current_time=0.0,
        step_size=0.5,
        input_values=dict(decay_rate=1.0),
        evaluation_budget=retained_fmi_three_budget,
    )
    retained_fmi_three_solver_calls: int = (
        retained_fmi_three_coordinator.evaluate_probe.call_count
    )
    retained_fmi_three_coordinator.evaluate_candidate.assert_called_once()
    assert retained_fmi_three_budget.get_consumed_count() == (
        retained_fmi_three_solver_calls + 1
    )

    # Exercise every FMI 3 checkpoint/no-checkpoint branch that adds charges
    # outside the numerical solve: initialization, both localization forms,
    # rejection, smooth acceptance, and event acceptance.
    checkpoint_is_supported: bool
    for checkpoint_is_supported in (True, False):
        coordinator_session: Mock = Mock()
        coordinator_session.supports_fmu_state_checkpoint.return_value = (
            checkpoint_is_supported
        )
        coordinator_session.update_model_exchange_discrete_states.return_value = (
            FmiThreeWorkerDiscreteStatesResult(
                discrete_states_need_update=False,
                terminate_simulation=False,
                nominals_of_continuous_states_changed=False,
                values_of_continuous_states_changed=False,
                next_event_time_defined=False,
                next_event_time=0.0,
            )
        )
        coordinator_session.read_model_exchange_state_and_values.return_value = (
            (1.0,),
            (2.0,),
        )
        coordinator_session.get_model_exchange_event_indicators.return_value = (
            0.25,
        )
        coordinator_session.get_model_exchange_continuous_state_nominals.return_value = (
            1.0,
        )
        coordinator_session.evaluate_model_exchange.return_value = (
            (-1.0,),
            (2.0,),
        )
        coordinator_session.needs_completed_integrator_step.return_value = False
        coordinator_session.complete_model_exchange_integrator_step.return_value = (
            FmiThreeWorkerCompletedIntegratorStepResult(
                enter_event_mode=False,
                terminate_simulation=False,
            )
        )
        runtime_coordinator: FmiThreeModelExchangeCoordinator = (
            FmiThreeModelExchangeCoordinator(
                session=coordinator_session,
                maximum_event_iterations=2,
            )
        )
        initialization_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(20)
        runtime_coordinator.initialize(
            start_time=0.0,
            stop_time=1.0,
            relative_tolerance=1.0e-6,
            initial_writable_values=(1.0,),
            evaluation_budget=initialization_budget,
        )
        expected_initialization_charge: int = (
            9 if checkpoint_is_supported else 8
        )
        assert initialization_budget.get_consumed_count() == (
            expected_initialization_charge
        )
        assert coordinator_session.initialize_model_exchange.call_count == 1
        assert coordinator_session.update_model_exchange_discrete_states.call_count == 1
        assert coordinator_session.read_model_exchange_state_and_values.call_count == 1
        assert coordinator_session.evaluate_model_exchange.call_count == 1
        assert coordinator_session.get_model_exchange_event_indicators.call_count == 2
        assert coordinator_session.save_checkpoint.call_count == int(
            checkpoint_is_supported
        )

        runtime_coordinator.evaluate_candidate(
            time_value=0.25,
            continuous_state_values=(0.8,),
            writable_values=(1.0,),
            presented_derivative_values=(-0.8,),
            presented_readable_values=(2.0,),
        )
        coordinator_session.reset_mock()
        coordinator_session.evaluate_model_exchange.return_value = (
            (-0.8,),
            (2.0,),
        )
        presented_probe_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(10)
        runtime_coordinator.evaluate_event_indicators_probe(
            time_value=0.125,
            continuous_state_values=(0.9,),
            point_is_presented=True,
            evaluation_budget=presented_probe_budget,
        )
        expected_presented_probe_charge: int = (
            4 if checkpoint_is_supported else 3
        )
        assert presented_probe_budget.get_consumed_count() == (
            expected_presented_probe_charge
        )
        assert coordinator_session.evaluate_model_exchange.call_count == 1
        assert coordinator_session.get_model_exchange_event_indicators.call_count == 2
        assert coordinator_session.restore_checkpoint.call_count == int(
            checkpoint_is_supported
        )

        coordinator_session.evaluate_model_exchange.return_value = (
            (-1.0,),
            (2.0,),
        )
        rejection_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(3)
        runtime_coordinator.reject_candidate(evaluation_budget=rejection_budget)
        expected_rejection_charge: int = 1 if checkpoint_is_supported else 2
        assert rejection_budget.get_consumed_count() == expected_rejection_charge

        runtime_coordinator.evaluate_candidate(
            time_value=0.25,
            continuous_state_values=(0.8,),
            writable_values=(1.0,),
            presented_derivative_values=(-0.8,),
            presented_readable_values=(2.0,),
        )
        coordinator_session.reset_mock()
        coordinator_session.evaluate_model_exchange.return_value = (
            (-0.8,),
            (2.0,),
        )
        non_presented_probe_budget: FmuMeEvaluationBudget = (
            FmuMeEvaluationBudget(10)
        )
        runtime_coordinator.evaluate_event_indicators_probe(
            time_value=0.125,
            continuous_state_values=(0.9,),
            point_is_presented=False,
            evaluation_budget=non_presented_probe_budget,
        )
        expected_non_presented_probe_charge: int = (
            5 if checkpoint_is_supported else 4
        )
        assert non_presented_probe_budget.get_consumed_count() == (
            expected_non_presented_probe_charge
        )
        assert coordinator_session.evaluate_model_exchange.call_count == 2
        assert coordinator_session.get_model_exchange_event_indicators.call_count == 2
        coordinator_session.evaluate_model_exchange.return_value = (
            (-1.0,),
            (2.0,),
        )
        second_rejection_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(3)
        runtime_coordinator.reject_candidate(
            evaluation_budget=second_rejection_budget
        )
        assert second_rejection_budget.get_consumed_count() == (
            expected_rejection_charge
        )

        runtime_coordinator.evaluate_candidate(
            time_value=0.25,
            continuous_state_values=(0.8,),
            writable_values=(1.0,),
            presented_derivative_values=(-0.8,),
            presented_readable_values=(2.0,),
        )
        coordinator_session.reset_mock()
        coordinator_session.needs_completed_integrator_step.return_value = True
        smooth_acceptance_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(3)
        runtime_coordinator.accept_candidate(
            importer_detected_event=False,
            evaluation_budget=smooth_acceptance_budget,
        )
        expected_smooth_acceptance_charge: int = (
            2 if checkpoint_is_supported else 1
        )
        assert smooth_acceptance_budget.get_consumed_count() == (
            expected_smooth_acceptance_charge
        )
        assert coordinator_session.complete_model_exchange_integrator_step.call_count == 1
        assert coordinator_session.save_checkpoint.call_count == int(
            checkpoint_is_supported
        )

        runtime_coordinator.evaluate_candidate(
            time_value=0.5,
            continuous_state_values=(0.6,),
            writable_values=(1.0,),
            presented_derivative_values=(-0.6,),
            presented_readable_values=(2.0,),
        )
        coordinator_session.reset_mock()
        coordinator_session.needs_completed_integrator_step.return_value = False
        coordinator_session.evaluate_model_exchange.return_value = (
            (-1.0,),
            (2.0,),
        )
        event_acceptance_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(10)
        runtime_coordinator.accept_candidate(
            importer_detected_event=True,
            evaluation_budget=event_acceptance_budget,
        )
        expected_event_acceptance_charge: int = (
            8 if checkpoint_is_supported else 7
        )
        assert event_acceptance_budget.get_consumed_count() == (
            expected_event_acceptance_charge
        )
        assert coordinator_session.enter_model_exchange_event_mode.call_count == 1
        assert coordinator_session.update_model_exchange_discrete_states.call_count == 1
        assert coordinator_session.read_model_exchange_state_and_values.call_count == 1
        assert coordinator_session.get_model_exchange_event_indicators.call_count == 1
        assert coordinator_session.evaluate_model_exchange.call_count == 1
        assert coordinator_session.save_checkpoint.call_count == int(
            checkpoint_is_supported
        )


def test_backward_euler_matches_analytic_decay() -> None:
    """Match the exact Backward Euler solution of scalar linear decay.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    coordinator: Mock
    adapter, coordinator = _build_mock_backward_euler_adapter()
    evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(10)
    candidate_states: np.ndarray
    endpoint_derivatives: np.ndarray
    readable_values: tuple[float, ...] | None
    candidate_states, endpoint_derivatives, readable_values = (
        adapter._solve_backward_euler_candidate(
            current_time=0.0,
            step_size=0.1,
            accepted_state_values=np.array([1.0], dtype=float),
            input_values=dict(decay_rate=2.0),
            evaluation_budget=evaluation_budget,
        )
    )

    expected_state: float = 1.0 / 1.2
    assert candidate_states.tolist() == pytest.approx([expected_state])
    assert endpoint_derivatives.tolist() == pytest.approx([-2.0 * expected_state])
    assert readable_values == tuple()
    assert coordinator.evaluate_probe.call_count == 4
    assert evaluation_budget.get_consumed_count() == 4


def test_backward_euler_newton_exact_iterates_and_probe_order() -> None:
    """Expose predictor, perturbation, and corrected endpoint probe order.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    coordinator: Mock
    adapter, coordinator = _build_mock_backward_euler_adapter()
    evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(10)
    candidate_states: np.ndarray
    ignored_derivatives: np.ndarray
    ignored_readable_values: tuple[float, ...] | None
    candidate_states, ignored_derivatives, ignored_readable_values = (
        adapter._solve_backward_euler_candidate(
            current_time=0.0,
            step_size=0.25,
            accepted_state_values=np.array([2.0], dtype=float),
            input_values=dict(decay_rate=0.5),
            evaluation_budget=evaluation_budget,
        )
    )

    probe_calls: list[object] = coordinator.evaluate_probe.call_args_list
    probe_times: list[float] = [
        float(probe_call.kwargs["time_value"])
        for probe_call in probe_calls
    ]
    probe_states: list[float] = [
        float(probe_call.kwargs["continuous_state_values"][0])
        for probe_call in probe_calls
    ]
    assert probe_times == pytest.approx([0.0, 0.25, 0.25, 0.25])
    assert probe_states[0] == pytest.approx(2.0)
    assert probe_states[1] == pytest.approx(1.75)
    assert probe_states[2] > probe_states[1]
    assert probe_states[3] == pytest.approx(2.0 / 1.125)
    assert candidate_states.tolist() == pytest.approx([2.0 / 1.125])


def test_backward_euler_scaled_vector_and_zero_state() -> None:
    """Solve disparate state scales and the zero-state endpoint path.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    ignored_coordinator: Mock
    adapter, ignored_coordinator = _build_mock_backward_euler_adapter()
    evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(20)
    accepted_states: np.ndarray = np.array([1.0e-12, 1.0e6], dtype=float)
    candidate_states: np.ndarray
    ignored_derivatives: np.ndarray
    ignored_readable_values: tuple[float, ...] | None
    candidate_states, ignored_derivatives, ignored_readable_values = (
        adapter._solve_backward_euler_candidate(
            current_time=1.0,
            step_size=0.2,
            accepted_state_values=accepted_states,
            input_values=dict(decay_rate=0.25),
            evaluation_budget=evaluation_budget,
        )
    )
    assert candidate_states.tolist() == pytest.approx(
        (accepted_states / 1.05).tolist()
    )

    zero_adapter: FmuMeDeviceAdapter
    zero_coordinator: Mock
    zero_adapter, zero_coordinator = _build_mock_backward_euler_adapter()
    zero_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(1)
    zero_states: np.ndarray
    zero_derivatives: np.ndarray
    zero_readable_values: tuple[float, ...] | None
    zero_states, zero_derivatives, zero_readable_values = (
        zero_adapter._solve_backward_euler_candidate(
            current_time=0.0,
            step_size=0.1,
            accepted_state_values=np.zeros(0, dtype=float),
            input_values=dict(decay_rate=0.25),
            evaluation_budget=zero_budget,
        )
    )
    assert zero_states.size == 0
    assert zero_derivatives.size == 0
    assert zero_readable_values == tuple()
    assert zero_coordinator.evaluate_probe.call_count == 1
    assert zero_budget.get_consumed_count() == 1


def test_backward_euler_rejects_nonfinite_singular_and_exhausted() -> None:
    """Fail closed for non-finite, singular, and unconverged solves.

    :return: None.
    """

    nonfinite_adapter: FmuMeDeviceAdapter
    nonfinite_coordinator: Mock
    nonfinite_adapter, nonfinite_coordinator = _build_mock_backward_euler_adapter()
    nonfinite_coordinator.evaluate_probe.side_effect = None
    nonfinite_coordinator.evaluate_probe.return_value = ((math.nan,), tuple())
    with pytest.raises(RuntimeError, match="derivative vector"):
        nonfinite_adapter._solve_backward_euler_candidate(
            current_time=0.0,
            step_size=1.0,
            accepted_state_values=np.array([1.0], dtype=float),
            input_values=dict(decay_rate=1.0),
            evaluation_budget=FmuMeEvaluationBudget(10),
        )

    singular_adapter: FmuMeDeviceAdapter
    singular_coordinator: Mock
    singular_adapter, singular_coordinator = _build_mock_backward_euler_adapter()
    perturbation: float = math.sqrt(np.finfo(np.float64).eps)
    singular_coordinator.evaluate_probe.side_effect = [
        ((0.0,), tuple()),
        ((1.0,), tuple()),
        ((1.0 + perturbation,), tuple()),
    ]
    with pytest.raises(RuntimeError, match="Jacobian is singular"):
        singular_adapter._solve_backward_euler_candidate(
            current_time=0.0,
            step_size=1.0,
            accepted_state_values=np.array([1.0], dtype=float),
            input_values=dict(decay_rate=1.0),
            evaluation_budget=FmuMeEvaluationBudget(10),
        )

    exhausted_policy: FmuMeSolverPolicy = FmuMeSolverPolicy(
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        absolute_tolerance=1.0e-12,
        relative_tolerance=1.0e-12,
        maximum_newton_iterations=1,
        maximum_continuous_states=128,
    )
    exhausted_adapter: FmuMeDeviceAdapter
    exhausted_coordinator: Mock
    exhausted_adapter, exhausted_coordinator = _build_mock_backward_euler_adapter(
        exhausted_policy
    )
    exhausted_coordinator.evaluate_probe.side_effect = [
        ((0.0,), tuple()),
        ((1.0,), tuple()),
        ((1.0,), tuple()),
        ((0.0,), tuple()),
    ]
    with pytest.raises(RuntimeError, match="iteration limit was exhausted"):
        exhausted_adapter._solve_backward_euler_candidate(
            current_time=0.0,
            step_size=1.0,
            accepted_state_values=np.array([1.0], dtype=float),
            input_values=dict(decay_rate=1.0),
            evaluation_budget=FmuMeEvaluationBudget(10),
        )


def test_backward_euler_state_and_shared_evaluation_bounds() -> None:
    """Enforce the 128-state and shared-call limits at exact boundaries.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    coordinator: Mock
    adapter, coordinator = _build_mock_backward_euler_adapter()
    bounded_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(2)
    bounded_states: np.ndarray
    ignored_derivatives: np.ndarray
    ignored_readable_values: tuple[float, ...] | None
    bounded_states, ignored_derivatives, ignored_readable_values = (
        adapter._solve_backward_euler_candidate(
            current_time=0.0,
            step_size=0.1,
            accepted_state_values=np.zeros(128, dtype=float),
            input_values=dict(decay_rate=0.0),
            evaluation_budget=bounded_budget,
        )
    )
    assert bounded_states.size == 128
    assert bounded_budget.get_consumed_count() == 2

    coordinator.reset_mock()
    rejected_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(2)
    with pytest.raises(RuntimeError, match="state count exceeds"):
        adapter._solve_backward_euler_candidate(
            current_time=0.0,
            step_size=0.1,
            accepted_state_values=np.zeros(129, dtype=float),
            input_values=dict(decay_rate=0.0),
            evaluation_budget=rejected_budget,
        )
    coordinator.evaluate_probe.assert_not_called()
    assert rejected_budget.get_consumed_count() == 0

    owner_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(100000)
    operation_index: int
    for operation_index in range(100000):
        owner_budget.consume()
    assert operation_index == 99999
    assert owner_budget.get_consumed_count() == 100000
    with pytest.raises(RuntimeError, match="before the next native call"):
        owner_budget.consume()
    assert owner_budget.get_consumed_count() == 100000


@pytest.mark.parametrize("event_time", (None, 0.5))
def test_me_device_retry_restores_adapter_owned_state(event_time: float | None) -> None:
    """Restore local outputs and EMT clock using the same runtime call budget.

    :param event_time: Event arming request for a source or another device.
    :return: None; reevaluation, extra calls or stale clock/output state fail.
    """
    budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(23)
    restored: dict[VarPowerFlowReferenceType, float] = dict(((VarPowerFlowReferenceType.P, 4.0),))
    rms: RmsFmuMeDeviceAdapter = object.__new__(RmsFmuMeDeviceAdapter)
    emt: EmtFmuMeDeviceAdapter = object.__new__(EmtFmuMeDeviceAdapter)
    adapter: RmsFmuMeDeviceAdapter | EmtFmuMeDeviceAdapter
    for adapter in (rms, emt):
        runtime: Mock = Mock(spec=FmuMeDeviceAdapter)
        runtime.prepare_state_event_retry.return_value = (4.0,)
        runtime.map_bound_output_values.return_value = restored
        adapter.runtime_adapter = runtime
        adapter.last_outputs = dict(((VarPowerFlowReferenceType.P, -99.0),))
        if isinstance(adapter, EmtFmuMeDeviceAdapter):
            adapter.last_time = 1.0
            adapter.pending_previous_time = 0.0
        else:
            pass
        assert adapter.prepare_state_event_retry(event_time, budget) == restored
        assert adapter.last_outputs == restored and adapter.last_outputs is not restored
        runtime.prepare_state_event_retry.assert_called_once_with(event_time=event_time, evaluation_budget=budget)
        runtime.map_bound_output_values.assert_called_once_with((4.0,))
        assert len(runtime.mock_calls) == 2
        if isinstance(adapter, EmtFmuMeDeviceAdapter):
            assert adapter.last_time == 0.0 and adapter.pending_previous_time is None
        else:
            pass
    assert budget.get_consumed_count() == 0


def test_fmi_me_budget_survives_localized_retry_rms() -> None:
    """Share one RMS budget across localization and coordinated rollback.

    :return: None.
    """

    localized_times: tuple[float, float, float] = (0.5, 0.5000000001, 0.75)
    wrappers: list[Mock] = [Mock()] * 3
    wrapper_index: int
    for wrapper_index in range(3):
        runtime_adapter: Mock = Mock()
        runtime_adapter.get_pending_state_event_time.return_value = (
            localized_times[wrapper_index]
        )
        runtime_adapter.prepare_state_event_retry.return_value = (1.0,)
        mapped_outputs: dict[VarPowerFlowReferenceType, float] = dict()
        mapped_outputs[VarPowerFlowReferenceType.P] = 1.0
        wrappers[wrapper_index] = Mock(spec=RmsFmuMeDeviceAdapter)
        wrappers[wrapper_index].runtime_adapter = runtime_adapter
        wrappers[wrapper_index].prepare_state_event_retry.return_value = mapped_outputs
    shared_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(100000)
    problem: SimpleNamespace = SimpleNamespace(
        _fmu_me_adapters=wrappers,
        _variable_parameters_values=np.zeros(1, dtype=float),
        _last_variable_parameters_values=None,
        _fmu_me_evaluation_budget=shared_budget,
    )

    retry_time: float | None = _prepare_rms_fmu_me_state_event_retry(
        problem=problem,
        state_event_time_tolerance=1.0e-9,
        state_event_max_iterations=40,
    )

    assert retry_time == pytest.approx(0.5)
    expected_event_times: tuple[float | None, ...] = (0.5, 0.5, None)
    wrapper: Mock
    for wrapper_index in range(3):
        wrapper = wrappers[wrapper_index]
        wrapper.prepare_state_event_retry.assert_called_once_with(expected_event_times[wrapper_index], shared_budget)
        wrapper.apply_outputs.assert_called_once()


def test_fmi_me_budget_survives_localized_retry_emt() -> None:
    """Keep the EMT ME budget through retry before advancing CS.

    :return: None.
    """

    problem: SimpleNamespace = SimpleNamespace(
        emt_boundary_update=Mock(),
        commit_boundary=Mock(),
        options=SimpleNamespace(
            fmi_state_event_time_tolerance=1.0e-9,
            fmi_state_event_max_iterations=40,
            fmi_me_max_runtime_evaluations_per_step=100000,
        ),
    )
    cs_outputs: dict[VarPowerFlowReferenceType, float] = dict()
    cs_outputs[VarPowerFlowReferenceType.P] = 2.0
    cs_adapter: Mock = Mock()
    cs_adapter.last_time = 0.0
    cs_adapter.advance.return_value = cs_outputs
    me_outputs: dict[VarPowerFlowReferenceType, float] = dict()
    me_outputs[VarPowerFlowReferenceType.P] = 1.0
    me_runtime_adapter: Mock = Mock()
    me_runtime_adapter.get_pending_state_event_time.return_value = 0.5
    me_runtime_adapter.prepare_state_event_retry.return_value = (1.0,)
    me_runtime_adapter.map_bound_output_values.return_value = me_outputs
    me_adapter: Mock = Mock()
    me_adapter.last_time = 0.0
    me_adapter.pending_previous_time = 0.0
    me_adapter.runtime_adapter = me_runtime_adapter
    me_adapter.prepare_state_event_retry.return_value = me_outputs
    me_adapter.advance.return_value = me_outputs
    updater: CompositeEmtBoundaryUpdater = CompositeEmtBoundaryUpdater(
        problem=problem,
        cs_adapters=[cs_adapter],
        me_adapters=[me_adapter],
    )
    updater.initialized = True
    params: np.ndarray = np.zeros(1, dtype=float)

    retry_time: float | None = updater.update(
        time_value=1.0,
        x_snapshot=np.zeros(1, dtype=float),
        full_params=params,
    )
    assert retry_time == pytest.approx(0.5)
    me_adapter.advance.assert_called_once()
    cs_adapter.advance.assert_not_called()
    me_adapter.prepare_state_event_retry.assert_called_once_with(0.5, updater.me_evaluation_budget)
    problem.commit_boundary.assert_not_called()
    updater.resolve_step(accepted=False, params=params)
    problem.commit_boundary.assert_not_called()

    me_runtime_adapter.get_pending_state_event_time.return_value = None
    updater.update(
        time_value=0.5,
        x_snapshot=np.zeros(1, dtype=float),
        full_params=params,
    )
    cs_adapter.advance.assert_called_once()
    problem.commit_boundary.assert_not_called()
    committed_state: np.ndarray = np.zeros(1, dtype=float)
    updater.commit_boundary(0.5, committed_state, params)
    problem.commit_boundary.assert_called_once_with(0.5, committed_state, params)

    initial_adapter: Mock = Mock()
    initial_adapter.pending_previous_time = None
    initial_updater: CompositeEmtBoundaryUpdater = CompositeEmtBoundaryUpdater(
        problem=SimpleNamespace(),
        cs_adapters=list(),
        me_adapters=[initial_adapter],
    )
    initial_retry_time: float | None = initial_updater.resolve_step(
        accepted=True,
        params=np.zeros(1, dtype=float),
    )
    assert initial_retry_time is None
    initial_adapter.resolve_step.assert_not_called()


def test_state_event_localization_supports_one_transition_per_indicator() -> None:
    """Give each crossing one bracket and reject an insufficient bound early.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    coordinator: Mock
    adapter, coordinator = _build_synthetic_localization_adapter(
        accepted_time=0.0,
        candidate_time=1.0,
        accepted_states=(1.0,),
        candidate_states=(0.5,),
        accepted_indicators=(0.3, 0.4),
        candidate_indicators=(-0.2, -0.1),
    )
    assert adapter._get_pending_state_event_crossing_indices() == (0, 1)
    evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(100000)
    localized_time: float | None = adapter.get_pending_state_event_time(
        time_tolerance=1.0e-9,
        maximum_iterations=40,
        evaluation_budget=evaluation_budget,
    )
    assert localized_time == pytest.approx(3.0 / 7.0, abs=1.0e-9)
    assert coordinator.evaluate_event_indicators_probe.call_count == 60

    coordinator.reset_mock()
    preflight_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(100000)
    with pytest.raises(
        RuntimeError,
        match="localization bound cannot meet its tolerance",
    ):
        adapter.get_pending_state_event_time(
            time_tolerance=1.0e-12,
            maximum_iterations=1,
            evaluation_budget=preflight_budget,
        )
    coordinator.evaluate_probe.assert_not_called()
    coordinator.evaluate_event_indicators_probe.assert_not_called()
    assert preflight_budget.get_consumed_count() == 0

    # Endpoint signs alone cannot identify the earliest of three transitions.
    transition_times: tuple[float, float, float] = (0.2, 0.5, 0.8)
    full_start_value: float = (-0.2) * (-0.5) * (-0.8)
    full_end_value: float = 0.8 * 0.5 * 0.2
    assert adapter._get_pending_state_event_crossing_indices(
        accepted_indicators=(full_start_value,),
        candidate_indicators=(full_end_value,),
    ) == (0,)
    reduced_transition_count: int = 0
    transition_time: float
    for transition_time in transition_times:
        if 0.0 < transition_time <= 0.3:
            reduced_transition_count += 1
        else:
            pass
    assert reduced_transition_count == 1
    reduced_end_value: float = 0.1 * (-0.2) * (-0.5)
    assert full_start_value < 0.0 < reduced_end_value


def test_backward_euler_localization_uses_method_consistent_midpoint_fmi_two() -> None:
    """Localize FMI 2 by solving every midpoint with Backward Euler.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    ignored_coordinator: Mock
    adapter, ignored_coordinator = _build_synthetic_localization_adapter(
        accepted_time=0.0,
        candidate_time=1.0,
        accepted_states=(1.0,),
        candidate_states=(0.5,),
        accepted_indicators=(0.3,),
        candidate_indicators=(-0.2,),
    )
    runtime_host: Mock = Mock()
    perturbation: float = math.sqrt(np.finfo(np.float64).eps)
    presented_states: tuple[float, ...] = (
        1.0, 0.5, 0.5 + perturbation, 2.0 / 3.0, 0.5,
        1.0, 0.75, 0.75 + perturbation, 0.8, 0.5,
        1.0, 0.625, 0.625 + perturbation, 1.0 / 1.375, 0.5,
    )
    derivative_results: list[list[float]] = [
        [-presented_state] for presented_state in presented_states
    ]
    runtime_host.get_derivatives.side_effect = derivative_results
    runtime_host.get_real.return_value = dict()
    runtime_host.get_event_indicators.side_effect = [
        (2.0 / 3.0 - 0.7,),
        (-0.2,),
        (0.1,),
        (-0.2,),
        (1.0 / 1.375 - 0.7,),
        (-0.2,),
    ]
    adapter.runtime_host = runtime_host
    adapter.fmi_three_coordinator = None
    evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(21)

    localized_time: float | None = adapter.get_pending_state_event_time(
        time_tolerance=0.125,
        maximum_iterations=3,
        evaluation_budget=evaluation_budget,
    )

    assert localized_time == pytest.approx(0.5)
    assert runtime_host.get_derivatives.call_count == 15
    assert runtime_host.get_event_indicators.call_count == 6
    assert evaluation_budget.get_consumed_count() == 21
    state_calls: list[object] = runtime_host.set_continuous_states.call_args_list
    state_call_index: int
    for state_call_index in range(len(state_calls)):
        assert state_calls[state_call_index].args[0] == pytest.approx(
            [presented_states[state_call_index]]
        )
        assert derivative_results[state_call_index][0] == pytest.approx(
            -presented_states[state_call_index]
        )
    event_state_indices: tuple[int, ...] = (3, 4, 8, 9, 13, 14)
    event_results: tuple[float, ...] = (
        2.0 / 3.0 - 0.7, -0.2, 0.1, -0.2,
        1.0 / 1.375 - 0.7, -0.2,
    )
    event_result_index: int
    for event_result_index in range(len(event_results)):
        assert event_results[event_result_index] == pytest.approx(
            presented_states[event_state_indices[event_result_index]] - 0.7
        )
    interpolated_midpoint_indicator: float = 0.75 - 0.7
    backward_euler_midpoint_indicator: float = 2.0 / 3.0 - 0.7
    assert interpolated_midpoint_indicator > 0.0
    assert backward_euler_midpoint_indicator < 0.0


def test_backward_euler_localization_uses_method_consistent_midpoint_fmi_three() -> None:
    """Localize FMI 3 stateful and zero-state probes with solver midpoints.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    coordinator: Mock
    adapter, coordinator = _build_synthetic_localization_adapter(
        accepted_time=0.0,
        candidate_time=1.0,
        accepted_states=(1.0,),
        candidate_states=(0.5,),
        accepted_indicators=(0.3, 0.4),
        candidate_indicators=(-0.2, -0.1),
    )
    evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(100000)
    localized_time: float | None = adapter.get_pending_state_event_time(
        time_tolerance=1.0e-9,
        maximum_iterations=40,
        evaluation_budget=evaluation_budget,
    )
    assert localized_time == pytest.approx(3.0 / 7.0, abs=1.0e-9)
    interpolated_midpoint_indicator: float = 0.75 - 0.7
    backward_euler_midpoint_indicator: float = 2.0 / 3.0 - 0.7
    assert interpolated_midpoint_indicator > 0.0
    assert backward_euler_midpoint_indicator < 0.0
    probe_call: object
    for probe_call in coordinator.evaluate_event_indicators_probe.call_args_list:
        assert probe_call.kwargs["point_is_presented"]

    zero_adapter: FmuMeDeviceAdapter
    zero_coordinator: Mock
    zero_adapter, zero_coordinator = _build_synthetic_localization_adapter(
        accepted_time=0.0,
        candidate_time=1.0,
        accepted_states=tuple(),
        candidate_states=tuple(),
        accepted_indicators=(-0.4,),
        candidate_indicators=(0.6,),
    )
    zero_coordinator.evaluate_event_indicators_probe.side_effect = (
        _evaluate_time_test_event_indicator
    )
    zero_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(10)
    zero_localized_time: float | None = zero_adapter.get_pending_state_event_time(
        time_tolerance=0.125,
        maximum_iterations=3,
        evaluation_budget=zero_budget,
    )
    assert zero_localized_time == pytest.approx(0.5)
    assert zero_coordinator.evaluate_probe.call_count == 3
    assert zero_coordinator.evaluate_event_indicators_probe.call_count == 3


def test_rms_problem_co_simulation_step_boundaries_report_actual_advancement() -> None:
    """Report advancement only after the shared owner completes an adapter.

    :return: None.
    """

    state_snapshot: np.ndarray = np.array([1.0], dtype=float)
    inactive_problem: SimpleNamespace = SimpleNamespace(_fmu_cs_adapters=list())
    inactive_results: tuple[bool, bool, bool, bool] = (
        RmsProblemDae.advance_fmu_cs_devices(
            inactive_problem,
            t=0.0,
            x_snapshot=state_snapshot,
            h=0.1,
        ),
        RmsProblemDaeVec.advance_fmu_cs_devices(
            inactive_problem,
            t=0.0,
            x_snapshot=state_snapshot,
            h=0.1,
        ),
        RmsProblemDaeFullVec.advance_fmu_cs_devices(
            inactive_problem,
            t=0.0,
            x_snapshot=state_snapshot,
            h=0.1,
        ),
        RmsProblemPhasor.advance_fmu_cs_devices(
            inactive_problem,
            t=0.0,
            x_snapshot=state_snapshot,
            h=0.1,
        ),
    )
    assert inactive_results == (False, False, False, False)

    adapter: Mock = Mock()
    adapter.advance.return_value = dict()
    active_problem: SimpleNamespace = SimpleNamespace(
        _fmu_cs_adapters=[adapter],
        _fmu_cs_initialized=True,
        _variable_parameters_values=np.array([0.0], dtype=float),
        _last_variable_parameters_values=None,
    )
    active_results: tuple[bool, bool, bool, bool] = (
        RmsProblemDae.advance_fmu_cs_devices(
            active_problem,
            t=0.0,
            x_snapshot=state_snapshot,
            h=0.1,
        ),
        RmsProblemDaeVec.advance_fmu_cs_devices(
            active_problem,
            t=0.0,
            x_snapshot=state_snapshot,
            h=0.1,
        ),
        RmsProblemDaeFullVec.advance_fmu_cs_devices(
            active_problem,
            t=0.0,
            x_snapshot=state_snapshot,
            h=0.1,
        ),
        RmsProblemPhasor.advance_fmu_cs_devices(
            active_problem,
            t=0.0,
            x_snapshot=state_snapshot,
            h=0.1,
        ),
    )
    assert active_results == (True, True, True, True)
    assert adapter.advance.call_count == 4
    assert adapter.apply_outputs.call_count == 4


def test_all_rms_integrators_use_co_simulation_step_boundary() -> None:
    """Exercise the renamed Co-Simulation boundary in every RMS integrator.

    :return: None.
    """

    solver_types: tuple[type, ...] = (
        BackEulerImplicitIntegration,
        BackEulerImplicitIntegrationVec,
        BackEulerImplicitIntegrationFullVec,
        MidpointImplicitIntegration,
        TrapezoidalImplicitIntegration,
    )
    solver_type: type
    for solver_type in solver_types:
        problem: _CurrentPointCouplingProblem = _CurrentPointCouplingProblem(
            enable_cs=True,
            cs_advance_result=True,
        )
        solver = solver_type(
            problem=problem,
            t0=0.0,
            t_end=0.1,
            h=0.1,
            max_iter=4,
            tolerance=1.0e-10,
        )
        ignored_result: tuple = solver.simulate()
        assert problem.cs_advance_count == 1
        assert problem.operation_log.count("cs") == 1


def test_backward_euler_variants_refresh_me_from_current_network_iterate() -> None:
    """Refresh ME from the corrected point before the next residual.

    :return: None.
    """

    solver_types: tuple[type, ...] = (
        BackEulerImplicitIntegration,
        BackEulerImplicitIntegrationVec,
        BackEulerImplicitIntegrationFullVec,
    )
    solver_type: type
    for solver_type in solver_types:
        problem: _CurrentPointCouplingProblem = _CurrentPointCouplingProblem()
        solver = solver_type(
            problem=problem,
            t0=0.0,
            t_end=0.1,
            h=0.1,
            max_iter=4,
            tolerance=1.0e-10,
        )
        ignored_times: np.ndarray
        state_history: np.ndarray
        initialized: bool
        converged: bool
        ignored_times, state_history, initialized, converged = solver.simulate()
        assert initialized
        assert converged
        assert state_history[-1, 0] == pytest.approx(1.1)
        assert len(problem.me_advance_snapshots) >= 2
        assert problem.me_advance_snapshots[0][0] == pytest.approx(1.0)
        assert problem.me_advance_snapshots[1][0] == pytest.approx(1.1)
        assert problem.resolve_acceptances == [True]
        if solver_type in (
                BackEulerImplicitIntegration,
                BackEulerImplicitIntegrationVec,
        ):
            assert problem.operation_log.count("native_commit") == 1
            assert problem.operation_log.index("native_commit") < problem.operation_log.index("close_me")
        else:
            # FullVec is an existing FMI regression participant; the sealed
            # manufacturer-native scope owns only scalar and vector RMS.
            assert solver_type is BackEulerImplicitIntegrationFullVec
            assert problem.operation_log.count("native_commit") == 0


def test_backward_euler_pure_me_and_pre_cs_events_retry_before_cs() -> None:
    """Retry pure-ME and pre-CS events without advancing CS first.

    :return: None.
    """

    pure_me_problem: _CurrentPointCouplingProblem = _CurrentPointCouplingProblem(
        enable_cs=False,
        initial_event_time=0.05,
    )
    pure_me_solver: BackEulerImplicitIntegration = BackEulerImplicitIntegration(
        problem=pure_me_problem,
        t0=0.0,
        t_end=0.1,
        h=0.1,
        max_iter=4,
        tolerance=1.0e-10,
    )
    ignored_pure_result: tuple = pure_me_solver.simulate()
    assert pure_me_problem.cs_advance_count == 0
    assert pure_me_problem.operation_log[:2] == ["me", "me"]
    assert pure_me_problem.resolve_acceptances == [True, True]
    assert pure_me_problem.operation_log.count("native_commit") == 2

    pre_cs_problem: _CurrentPointCouplingProblem = _CurrentPointCouplingProblem(
        enable_cs=True,
        cs_advance_result=True,
        initial_event_time=0.05,
    )
    pre_cs_solver: BackEulerImplicitIntegration = BackEulerImplicitIntegration(
        problem=pre_cs_problem,
        t0=0.0,
        t_end=0.1,
        h=0.1,
        max_iter=4,
        tolerance=1.0e-10,
    )
    ignored_pre_cs_result: tuple = pre_cs_solver.simulate()
    assert pre_cs_problem.operation_log[:3] == ["me", "me", "cs"]
    assert pre_cs_problem.cs_advance_count == 2
    assert pre_cs_problem.resolve_acceptances == [True, True]
    assert pre_cs_problem.operation_log.count("native_commit") == 2


def test_backward_euler_variants_fail_closed_after_real_cs_advance() -> None:
    """Reject an ME retry discovered after any real CS advancement.

    :return: None.
    """

    expected_message: str = (
        "RMS FMI ME state event cannot retry after Co-Simulation devices advanced"
    )
    solver_types: tuple[type, ...] = (
        BackEulerImplicitIntegration,
        BackEulerImplicitIntegrationVec,
        BackEulerImplicitIntegrationFullVec,
    )
    solver_type: type
    for solver_type in solver_types:
        problem: _CurrentPointCouplingProblem = _CurrentPointCouplingProblem(
            enable_cs=True,
            cs_advance_result=True,
            corrected_event_time=0.05,
        )
        solver = solver_type(
            problem=problem,
            t0=0.0,
            t_end=0.1,
            h=0.1,
            max_iter=4,
            tolerance=1.0e-10,
        )
        # The full-vector solver still raises, while the other two variants
        # report the failed step through their logger and truncated results.
        if solver_type is BackEulerImplicitIntegrationFullVec:
            with pytest.raises(RuntimeError, match=expected_message):
                solver.simulate()
        else:
            result_time: np.ndarray
            result_state: np.ndarray
            well_initialized: bool
            converged: bool
            result_time, result_state, well_initialized, converged = solver.simulate()
            problem.logger.add_error.assert_called_once()
            logged_message: str = problem.logger.add_error.call_args.kwargs["msg"]
            assert "RMS FMI ME state event" in logged_message
            assert "cannot retry after Co-Simulation devices advanced" in logged_message
            assert "failed step is omitted" in logged_message
            assert result_time.tolist() == [0.0]
            assert result_state.shape == (1, 1)
            assert result_state[0, 0] == pytest.approx(1.0)
            assert well_initialized is True
            assert converged is False
            assert problem.resolve_acceptances == [False]
        assert problem.cs_advance_count == 1
        assert len(problem.me_advance_snapshots) == 2
        assert problem.me_advance_snapshots[1][0] == pytest.approx(1.1)
        assert problem.operation_log.count("native_commit") == 0
        assert problem.operation_log[-2:] == ["close_cs", "close_me"]


def test_fmi_two_candidate_input_does_not_replace_accepted_rollback_input() -> None:
    """Restore FMI 2 with accepted inputs after rejecting a new candidate.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    ignored_coordinator: Mock
    adapter, ignored_coordinator = _build_mock_backward_euler_adapter()
    runtime_host: Mock = Mock()
    runtime_host.get_derivatives.return_value = [-1.0]
    runtime_host.get_real.return_value = dict()
    runtime_host.get_event_indicators.return_value = (0.5,)
    adapter.runtime_host = runtime_host
    adapter.fmi_three_coordinator = None
    adapter.state_vector = np.array([1.0], dtype=float)
    adapter.fmi_two_accepted_input_values = (0.25,)
    adapter.fmi_two_accepted_derivative_values = (-1.0,)
    adapter.fmi_two_accepted_readable_values = tuple()
    adapter.fmi_two_accepted_event_indicators = (0.5,)
    preparation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(20)
    adapter._prepare_bound_step(
        current_time=0.0,
        step_size=0.5,
        input_values=dict(decay_rate=1.5),
        evaluation_budget=preparation_budget,
    )
    assert adapter.pending_accepted_input_values == (0.25,)
    assert adapter.pending_candidate_input_values == (1.5,)

    runtime_host.reset_mock()
    rejection_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(2)
    adapter.resolve_pending_step(
        accepted=False,
        evaluation_budget=rejection_budget,
    )
    restored_values: dict[str, float] = runtime_host.set_real.call_args.args[0]
    assert restored_values == dict(decay_rate=0.25)
    assert adapter.fmi_two_accepted_input_values == (0.25,)
    assert adapter.pending_candidate_input_values is None


def test_rms_me_candidate_replacement_reuses_one_budget() -> None:
    """Reject then replace all ME candidates under one local-step budget.

    :return: None.
    """

    runtime_adapter: Mock = Mock()
    runtime_adapter.has_pending_candidate.side_effect = [False, True]
    rms_adapter: Mock = Mock()
    rms_adapter.runtime_adapter = runtime_adapter
    rms_adapter.advance.side_effect = [dict(), dict()]
    problem: SimpleNamespace = SimpleNamespace(
        _fmu_me_adapters=[rms_adapter],
        _fmu_me_initialized=True,
        _fmu_me_evaluation_budget=None,
        _variable_parameters_values=np.zeros(1, dtype=float),
        _last_variable_parameters_values=None,
        options=SimpleNamespace(fmi_me_max_runtime_evaluations_per_step=17),
    )
    first_snapshot: np.ndarray = np.array([1.0], dtype=float)
    second_snapshot: np.ndarray = np.array([1.1], dtype=float)
    advance_rms_fmu_me_devices(
        problem=problem,
        time_value=0.0,
        x_snapshot=first_snapshot,
        step_size=0.1,
    )
    first_budget: FmuMeEvaluationBudget = (
        rms_adapter.advance.call_args_list[0].kwargs["evaluation_budget"]
    )
    advance_rms_fmu_me_devices(
        problem=problem,
        time_value=0.0,
        x_snapshot=second_snapshot,
        step_size=0.1,
    )
    second_budget: FmuMeEvaluationBudget = (
        rms_adapter.advance.call_args_list[1].kwargs["evaluation_budget"]
    )
    assert second_budget is first_budget
    assert problem._fmu_me_evaluation_budget is first_budget
    rms_adapter.resolve_step.assert_called_once_with(
        accepted=False,
        evaluation_budget=first_budget,
    )
    assert rms_adapter.advance.call_args_list[1].kwargs["x_snapshot"] is second_snapshot


def test_fmi_two_state_event_localization_interpolates_input_trajectory() -> None:
    """Present linearly interpolated FMI 2 inputs at every bisection point.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    ignored_coordinator: Mock
    adapter, ignored_coordinator = _build_synthetic_localization_adapter(
        accepted_time=0.0,
        candidate_time=1.0,
        accepted_states=tuple(),
        candidate_states=tuple(),
        accepted_indicators=(-0.4,),
        candidate_indicators=(0.6,),
        accepted_inputs=(0.0,),
        candidate_inputs=(2.0,),
    )
    runtime_host: Mock = Mock()
    runtime_host.get_derivatives.return_value = list()
    runtime_host.get_real.return_value = dict()
    runtime_host.get_event_indicators.side_effect = [
        (0.1,),
        (0.6,),
        (-0.15,),
        (0.6,),
        (-0.025,),
        (0.6,),
    ]
    adapter.runtime_host = runtime_host
    adapter.fmi_three_coordinator = None
    evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(20)
    localized_time: float | None = adapter.get_pending_state_event_time(
        time_tolerance=0.125,
        maximum_iterations=3,
        evaluation_budget=evaluation_budget,
    )
    assert localized_time == pytest.approx(0.5)
    presented_inputs: list[float] = list()
    input_call: object
    for input_call in runtime_host.set_real.call_args_list:
        input_values: dict[str, float] = input_call.args[0]
        presented_inputs.append(input_values["coupling_input_0"])
    assert presented_inputs == pytest.approx([1.0, 2.0, 0.5, 2.0, 0.75, 2.0])


def test_fmi_three_state_event_localization_interpolates_input_trajectory() -> None:
    """Present linearly interpolated FMI 3 inputs at every bisection point.

    :return: None.
    """

    adapter: FmuMeDeviceAdapter
    coordinator: Mock
    adapter, coordinator = _build_synthetic_localization_adapter(
        accepted_time=0.0,
        candidate_time=1.0,
        accepted_states=tuple(),
        candidate_states=tuple(),
        accepted_indicators=(-0.4,),
        candidate_indicators=(0.6,),
        accepted_inputs=(0.0,),
        candidate_inputs=(2.0,),
    )
    coordinator.evaluate_event_indicators_probe.side_effect = (
        _evaluate_time_test_event_indicator
    )
    evaluation_budget: FmuMeEvaluationBudget = FmuMeEvaluationBudget(10)
    localized_time: float | None = adapter.get_pending_state_event_time(
        time_tolerance=0.125,
        maximum_iterations=3,
        evaluation_budget=evaluation_budget,
    )
    assert localized_time == pytest.approx(0.5)
    presented_inputs: list[float] = list()
    probe_call: object
    for probe_call in coordinator.evaluate_probe.call_args_list:
        writable_values: tuple[float, ...] = probe_call.kwargs["writable_values"]
        presented_inputs.append(writable_values[0])
    assert presented_inputs == pytest.approx([1.0, 0.5, 0.75])


def test_fmi_two_me_spec_rejects_non_continuous_runtime_inputs(
    tmp_path: Path,
) -> None:
    """Accept the FMI 2 continuous default and reject other input domains.

    :param tmp_path: Isolated extracted-FMU parent provided by pytest.
    :return: None.
    """

    accepted_source: Path = tmp_path / "fmi-two-continuous-default"
    accepted_source.mkdir()
    accepted_xml: str = (
        '<fmiModelDescription fmiVersion="2.0" modelName="InputDomain" '
        'guid="fmi-two-continuous-default">'
        '<ModelExchange modelIdentifier="input_domain"/>'
        '<ModelVariables><ScalarVariable name="u" valueReference="1" '
        'causality="input"><Real start="0"/></ScalarVariable></ModelVariables>'
        '<ModelStructure/></fmiModelDescription>'
    )
    (accepted_source / "modelDescription.xml").write_text(
        accepted_xml,
        encoding="utf-8",
    )
    accepted_spec = build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=FmuImportConfig(
            fmu_path=accepted_source,
            preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
        ),
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=("u",),
        output_variable_names=tuple(),
    )
    assert accepted_spec.input_variable_names == ("u",)

    rejected_domains: tuple[tuple[str, str], ...] = (
        ("parameter", "fixed"),
        ("input", "discrete"),
    )
    causality: str
    variability: str
    for causality, variability in rejected_domains:
        source: Path = tmp_path / f"fmi-two-{causality}-{variability}"
        source.mkdir()
        xml_text: str = (
            '<fmiModelDescription fmiVersion="2.0" modelName="InputDomain" '
            f'guid="fmi-two-{causality}-{variability}">'
            '<ModelExchange modelIdentifier="input_domain"/>'
            '<ModelVariables><ScalarVariable name="u" valueReference="1" '
            f'causality="{causality}" variability="{variability}">'
            '<Real start="0"/></ScalarVariable></ModelVariables>'
            '<ModelStructure/></fmiModelDescription>'
        )
        (source / "modelDescription.xml").write_text(xml_text, encoding="utf-8")
        with pytest.raises(RuntimeError, match="runtime input must be continuous input"):
            build_fmu_me_device_spec(
                domain=FmuMeDomain.RMS,
                config=FmuImportConfig(
                    fmu_path=source,
                    preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
                ),
                device_tpe=DeviceType.LoadDevice,
                input_variable_names=("u",),
                output_variable_names=tuple(),
            )


def test_fmi_three_me_spec_rejects_non_continuous_runtime_inputs(
    tmp_path: Path,
) -> None:
    """Accept continuous FMI 3 inputs and reject parameters or discrete inputs.

    :param tmp_path: Isolated extracted-FMU parent provided by pytest.
    :return: None.
    """

    worker_limits: FmiThreeWorkerHostLimits = FmiThreeWorkerHostLimits(
        maximum_frame_size=262144,
        maximum_float64_values_per_request=64,
        response_timeout_seconds=60.0,
        graceful_join_timeout_seconds=10.0,
        terminate_join_timeout_seconds=5.0,
        kill_join_timeout_seconds=5.0,
    )
    accepted_source: Path = tmp_path / "fmi-three-continuous"
    accepted_source.mkdir()
    accepted_xml: str = (
        '<fmiModelDescription fmiVersion="3.0" modelName="InputDomain" '
        'instantiationToken="fmi-three-continuous">'
        '<ModelExchange modelIdentifier="input_domain"/>'
        '<ModelVariables><Float64 name="u" valueReference="1" '
        'causality="input" variability="continuous" start="0"/>'
        '<Float64 name="time" valueReference="2" causality="independent" '
        'variability="continuous"/>'
        '</ModelVariables><ModelStructure/></fmiModelDescription>'
    )
    (accepted_source / "modelDescription.xml").write_text(
        accepted_xml,
        encoding="utf-8",
    )
    accepted_spec = build_fmu_me_device_spec(
        domain=FmuMeDomain.RMS,
        config=FmuImportConfig(
            fmu_path=accepted_source,
            preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
        ),
        device_tpe=DeviceType.LoadDevice,
        input_variable_names=("u",),
        output_variable_names=tuple(),
        worker_limits=worker_limits,
    )
    assert accepted_spec.input_variable_names == ("u",)

    rejected_domains: tuple[tuple[str, str], ...] = (
        ("parameter", "fixed"),
        ("input", "discrete"),
    )
    causality: str
    variability: str
    for causality, variability in rejected_domains:
        source: Path = tmp_path / f"fmi-three-{causality}-{variability}"
        source.mkdir()
        xml_text: str = (
            '<fmiModelDescription fmiVersion="3.0" modelName="InputDomain" '
            f'instantiationToken="fmi-three-{causality}-{variability}">'
            '<ModelExchange modelIdentifier="input_domain"/>'
            '<ModelVariables><Float64 name="u" valueReference="1" '
            f'causality="{causality}" variability="{variability}" start="0"/>'
            '<Float64 name="time" valueReference="2" causality="independent" '
            'variability="continuous"/>'
            '</ModelVariables><ModelStructure/></fmiModelDescription>'
        )
        (source / "modelDescription.xml").write_text(xml_text, encoding="utf-8")
        with pytest.raises(RuntimeError, match="runtime input must be continuous input"):
            build_fmu_me_device_spec(
                domain=FmuMeDomain.RMS,
                config=FmuImportConfig(
                    fmu_path=source,
                    preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
                ),
                device_tpe=DeviceType.LoadDevice,
                input_variable_names=("u",),
                output_variable_names=tuple(),
                worker_limits=worker_limits,
            )


@pytest.mark.parametrize("solver_class", (
    BackEulerImplicitIntegration, BackEulerImplicitIntegrationVec,
    BackEulerImplicitIntegrationFullVec,
))
@pytest.mark.parametrize(
    "derivative_rate,quadratic_rate,budget,tolerance,expected_converged,expected_last,expected_corrections",
    (
        (1.0, 0.0, 1, 1e-10, True, 1.1, 1),
        (0.0, 0.0, 0, 1e-10, True, 1.0, 0),
        (1.0, 0.0, 0, 1e-10, False, 1.0, 0),
        (0.0, 1.0, 1, 1e-6, False, 1.0, 1),
        (0.0, 1.0, 1, 0.002, True, 1.125, 1),
    ),
)
def test_rms_backward_euler_accepts_final_correction(
    solver_class: type[BackEulerImplicitIntegration] | type[BackEulerImplicitIntegrationVec] | type[BackEulerImplicitIntegrationFullVec],
    derivative_rate: float,
    quadratic_rate: float,
    budget: int,
    tolerance: float,
    expected_converged: bool,
    expected_last: float,
    expected_corrections: int,
) -> None:
    """Judge actual final residuals without exceeding the correction budget.

    :param solver_class: Existing public backward Euler implementation.
    :param derivative_rate: Constant derivative oracle coefficient.
    :param quadratic_rate: Squared-state derivative oracle coefficient.
    :param budget: Maximum allowed Newton corrections.
    :param tolerance: Strict residual tolerance passed to the solver.
    :param expected_converged: Analytically expected step acceptance.
    :param expected_last: Last available accepted state value.
    :param expected_corrections: Required Jacobian/correction count.
    :return: None.
    """
    problem: _CurrentPointCouplingProblem = _CurrentPointCouplingProblem(
        enable_cs=False, derivative_rate=derivative_rate, quadratic_rate=quadratic_rate,
    )
    solver: BackEulerImplicitIntegration | BackEulerImplicitIntegrationVec | BackEulerImplicitIntegrationFullVec = solver_class(
        problem=problem, t0=0.0, t_end=0.1, h=0.1, max_iter=budget, tolerance=tolerance,
    )
    times: np.ndarray
    values: np.ndarray
    initialized: bool
    converged: bool
    times, values, initialized, converged = solver.simulate()
    assert initialized
    assert converged == expected_converged
    expected_rows: int = 2 if expected_converged else 1
    assert times.shape == (expected_rows,)
    assert values.shape == (expected_rows, 1)
    np.testing.assert_allclose(values[-1, 0], expected_last, rtol=0, atol=1e-12)
    assert problem.jacobian_evaluations == expected_corrections
    assert problem.jacobian_evaluations <= budget
    assert problem.resolve_acceptances == list((expected_converged,))
    assert problem.me_close_count == 1
    assert problem.cs_close_count == 0
    if expected_converged:
        # Compute the accepted-state residual independently of the solver flag.
        final_residual: float = (
            float(values[-1, 0]) - 1.0
            - 0.1 * (derivative_rate + quadratic_rate * float(values[-1, 0]) ** 2)
        )
        assert math.isfinite(final_residual)
        assert abs(final_residual) < tolerance
        np.testing.assert_allclose(times, (0.0, 0.1), rtol=0, atol=1e-12)
    else:
        np.testing.assert_array_equal(times, np.zeros(1, dtype=float))


@pytest.mark.parametrize("solver_class", (
    BackEulerImplicitIntegration, BackEulerImplicitIntegrationVec,
    BackEulerImplicitIntegrationFullVec,
))
@pytest.mark.parametrize(
    "derivative_rate,initial_candidate,step,tolerance,budget,expected_converged,expected_last,expected_corrections",
    (
        (1.0, 1.0, 5e-7, 1e-10, 2, True, 1.0000005, 1),
        (1.0, 1.0, 1e-4, 1e-3, 2, True, 1.0, 0),
        (1.0, 1.0, 0.1, 0.1, 1, True, 1.1, 1),
        (math.nan, 1.0, 0.1, 1e-10, 2, False, 1.0, 0),
        (math.inf, 1.0, 0.1, 1e-10, 2, False, 1.0, 0),
        (-math.inf, 1.0, 0.1, 1e-10, 2, False, 1.0, 0),
        (0.0, math.nan, 0.1, 1e-10, 2, False, math.nan, 0),
        (0.0, math.inf, 0.1, 1e-10, 2, False, math.inf, 0),
        (0.0, -math.inf, 0.1, 1e-10, 2, False, -math.inf, 0),
        (1e308, 1e308, 1.0, 1e-10, 2, False, 1e308, 1),
    ),
)
def test_rms_backward_euler_respects_tolerance_and_rejects_invalid_candidates(
    solver_class: type[BackEulerImplicitIntegration] | type[BackEulerImplicitIntegrationVec] | type[BackEulerImplicitIntegrationFullVec],
    derivative_rate: float,
    initial_candidate: float,
    step: float,
    tolerance: float,
    budget: int,
    expected_converged: bool,
    expected_last: float,
    expected_corrections: int,
) -> None:
    """Respect user tolerance and reject nonfinite inputs before linear solves.

    :param solver_class: Existing public backward Euler implementation.
    :param derivative_rate: Constant derivative, including invalid probe values.
    :param initial_candidate: Supplied initial point used by the candidate guard.
    :param step: Single requested macro step.
    :param tolerance: Caller-selected strict residual tolerance.
    :param budget: Maximum allowed Newton corrections.
    :param expected_converged: Expected acceptance of the requested step.
    :param expected_last: Last available state, including raw invalid initial data.
    :param expected_corrections: Analytically required Jacobian count.
    :return: None.
    """
    problem: _CurrentPointCouplingProblem = _CurrentPointCouplingProblem(
        enable_cs=False, derivative_rate=derivative_rate,
        initial_candidate_value=initial_candidate,
    )
    solver: BackEulerImplicitIntegration | BackEulerImplicitIntegrationVec | BackEulerImplicitIntegrationFullVec = solver_class(
        problem=problem, t0=0.0, t_end=step, h=step, max_iter=budget, tolerance=tolerance,
    )
    times: np.ndarray
    values: np.ndarray
    initialized: bool
    converged: bool
    times, values, initialized, converged = solver.simulate()
    # Initial algebraic projection has no equations here; its meaning is unchanged.
    assert initialized
    assert converged == expected_converged
    expected_rows: int = 2 if expected_converged else 1
    assert times.shape == (expected_rows,)
    assert values.shape == (expected_rows, 1)
    np.testing.assert_equal(values[-1, 0], expected_last)
    # Scalar damping retains a finite point; the two vector backends overflow.
    expected_correction_count: int = (
        budget if derivative_rate == 1e308 and solver_class is BackEulerImplicitIntegration
        else expected_corrections
    )
    assert problem.jacobian_evaluations == expected_correction_count
    if math.isfinite(initial_candidate):
        # No invalid corrected point may reach the FMI ME input consumer.
        presented_snapshot: np.ndarray
        for presented_snapshot in problem.me_advance_snapshots:
            assert np.all(np.isfinite(presented_snapshot))
    else:
        pass
    assert problem.resolve_acceptances == list((expected_converged,))
    assert problem.me_close_count == 1
    assert problem.cs_close_count == 0
    if expected_converged:
        final_residual: float = float(values[-1, 0]) - initial_candidate - step * derivative_rate
        assert math.isfinite(final_residual)
        assert abs(final_residual) < tolerance
    else:
        assert problem.logger.add_error.call_count >= 1
        if not math.isfinite(initial_candidate):
            assert problem.residual_evaluations == 0
        elif derivative_rate == 1e308:
            assert problem.residual_evaluations == expected_correction_count + (
                1 if solver_class is BackEulerImplicitIntegration else 0
            )
        else:
            assert problem.residual_evaluations == 1


@pytest.mark.parametrize("solver_class", (
    BackEulerImplicitIntegration, BackEulerImplicitIntegrationVec,
    BackEulerImplicitIntegrationFullVec,
))
@pytest.mark.parametrize("failure_time,retry_time,expected_rows,accepted_local_count", (
    (0.1, None, 1, 0), (0.2, None, 2, 1), (0.1, 0.05, 1, 1),
))
def test_rms_backward_euler_preserves_prefix_on_rejection(
    solver_class: type[BackEulerImplicitIntegration] | type[BackEulerImplicitIntegrationVec] | type[BackEulerImplicitIntegrationFullVec],
    failure_time: float,
    retry_time: float | None,
    expected_rows: int,
    accepted_local_count: int,
) -> None:
    """Retain completed macro samples and prepared earlier FMI retries.

    :param solver_class: Existing public backward Euler implementation.
    :param failure_time: Local target where the derivative becomes invalid.
    :param retry_time: Optional earlier ME retry inside the first macro step.
    :param expected_rows: Initial plus completed macro samples to expose.
    :param accepted_local_count: Converged local boundaries before rejection.
    :return: None.
    """
    problem: _CurrentPointCouplingProblem = _CurrentPointCouplingProblem(
        enable_cs=False, initial_event_time=retry_time, rate_change=(failure_time, math.nan),
    )
    solver: BackEulerImplicitIntegration | BackEulerImplicitIntegrationVec | BackEulerImplicitIntegrationFullVec = solver_class(
        problem=problem, t0=0.0, t_end=0.3, h=0.1, max_iter=2, tolerance=1e-10,
    )
    times: np.ndarray
    values: np.ndarray
    initialized: bool
    converged: bool
    times, values, initialized, converged = solver.simulate()
    assert initialized
    assert not converged
    assert times.shape == (expected_rows,)
    assert values.shape == (expected_rows, 1)
    expected_times: np.ndarray = np.arange(expected_rows, dtype=float) * 0.1
    np.testing.assert_allclose(times, expected_times, rtol=0, atol=1e-12)
    np.testing.assert_allclose(values[:, 0], 1.0 + expected_times, rtol=0, atol=1e-12)
    expected_resolutions: list[bool] = list((True,)) * accepted_local_count
    expected_resolutions.append(False)
    assert problem.resolve_acceptances == expected_resolutions
    assert problem.jacobian_evaluations == accepted_local_count
    assert problem.last_update_time == pytest.approx(failure_time, rel=0, abs=1e-12)
    assert problem.me_close_count == 1
    assert problem.cs_close_count == 0
    if solver_class is BackEulerImplicitIntegrationFullVec:
        assert problem.operation_log.count("native_commit") == 0
    else:
        assert problem.operation_log.count("native_commit") == accepted_local_count
