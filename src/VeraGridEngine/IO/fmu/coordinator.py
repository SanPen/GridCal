# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Solver-agnostic FMI 3 Model Exchange lifecycle coordination."""

from __future__ import annotations

import math

from VeraGridEngine.IO.fmu.Elements.protocol import (
    FmiThreeWorkerCompletedIntegratorStepResult,
    FmiThreeWorkerDiscreteStatesResult,
)
from VeraGridEngine.IO.fmu.Elements.session import (
    FmiThreeNumericSession,
)
from VeraGridEngine.IO.fmu.profile import FmuMeEvaluationBudget


class FmiThreeModelExchangeCoordinator:
    """Own accepted/candidate FMI state without choosing a numerical method.

    The coordinator takes ownership of one initialized-or-new FMI 3 session.
    It manages FMI lifecycle, event convergence, and native rollback while the
    caller retains integration, step-size, and event-localization policy.

    :param session: Isolated Model Exchange session transferred to this owner.
    :param maximum_event_iterations: Positive bound for one Event Mode fixpoint.
    """

    __slots__ = (
        "_session",
        "_maximum_event_iterations",
        "_initialized",
        "_has_checkpoint",
        "_accepted_time",
        "_accepted_states",
        "_accepted_inputs",
        "_accepted_derivatives",
        "_accepted_readable_values",
        "_accepted_event_indicators",
        "_accepted_nominals",
        "_next_event_time",
        "_candidate_time",
        "_candidate_states",
        "_candidate_inputs",
        "_candidate_derivatives",
        "_candidate_readable_values",
        "_candidate_event_indicators",
    )

    def __init__(
        self,
        session: FmiThreeNumericSession,
        maximum_event_iterations: int,
    ) -> None:
        """Store one session and an explicit finite event-iteration bound.

        :param session: Isolated Model Exchange session transferred to this owner.
        :param maximum_event_iterations: Positive Event Mode iteration limit.
        :return: None.
        """

        if (
            isinstance(maximum_event_iterations, int)
            and not isinstance(maximum_event_iterations, bool)
            and 1 <= maximum_event_iterations <= 1024
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 maximum Event Mode iterations must be an integer between 1 and 1024"
            )
        self._session: FmiThreeNumericSession = session
        self._maximum_event_iterations: int = maximum_event_iterations
        self._initialized: bool = False
        self._has_checkpoint: bool = False
        self._accepted_time: float | None = None
        self._accepted_states: tuple[float, ...] | None = None
        self._accepted_inputs: tuple[float, ...] | None = None
        self._accepted_derivatives: tuple[float, ...] | None = None
        self._accepted_readable_values: tuple[float, ...] | None = None
        self._accepted_event_indicators: tuple[float, ...] | None = None
        self._accepted_nominals: tuple[float, ...] | None = None
        self._next_event_time: float | None = None
        self._candidate_time: float | None = None
        self._candidate_states: tuple[float, ...] | None = None
        self._candidate_inputs: tuple[float, ...] | None = None
        self._candidate_derivatives: tuple[float, ...] | None = None
        self._candidate_readable_values: tuple[float, ...] | None = None
        self._candidate_event_indicators: tuple[float, ...] | None = None

    def supports_rollback(self) -> bool:
        """Return whether native accepted-point rollback is available.

        :return: ``True`` when the FMU declared Get/Set/FreeFMUState.
        """

        return self._session.supports_fmu_state_checkpoint()

    def has_pending_candidate(self) -> bool:
        """Return whether one candidate awaits acceptance or rejection.

        :return: ``True`` after evaluation and before its resolution.
        """

        return self._candidate_time is not None

    def get_next_event_time(self) -> float | None:
        """Return the latest accepted FMI time-event request.

        :return: Absolute next event time or ``None`` when undefined.
        """

        return self._next_event_time

    def get_accepted_point(
        self,
    ) -> tuple[
        float,
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
    ]:
        """Return immutable accepted time, states, inputs, outputs, and scales.

        :return: Time, states, inputs, readable values, event indicators,
            continuous-state nominals, and accepted derivatives.
        :raises RuntimeError: If initialization has not established a point.
        """

        if (
            self._initialized
            and self._accepted_time is not None
            and self._accepted_states is not None
            and self._accepted_inputs is not None
            and self._accepted_derivatives is not None
            and self._accepted_readable_values is not None
            and self._accepted_event_indicators is not None
            and self._accepted_nominals is not None
        ):
            return (
                self._accepted_time,
                self._accepted_states,
                self._accepted_inputs,
                self._accepted_readable_values,
                self._accepted_event_indicators,
                self._accepted_nominals,
                self._accepted_derivatives,
            )
        else:
            raise RuntimeError(
                "FMI 3 coordinator has no initialized accepted point"
            )

    def _clear_candidate(self) -> None:
        """Clear the bounded candidate snapshot without changing native state.

        :return: None.
        """

        self._candidate_time = None
        self._candidate_states = None
        self._candidate_inputs = None
        self._candidate_derivatives = None
        self._candidate_readable_values = None
        self._candidate_event_indicators = None

    def _settle_event_mode(
        self,
        entry_time: float,
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> tuple[
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
        tuple[float, ...],
    ]:
        """Converge one bounded Event Mode and return its continuous snapshot.

        :param entry_time: Exact finite time at which Event Mode was entered.
        :param evaluation_budget: Optional owner-provided runtime-call budget.
        :return: States, readable values, event indicators, and state nominals.
        :raises RuntimeError: If the FMU requests simulation termination.
        :raises RuntimeError: If the discrete-state fixpoint exceeds its bound.
        """

        normalized_entry_time: float = float(entry_time)
        if math.isfinite(normalized_entry_time):
            pass
        else:
            raise ValueError("FMI 3 Event Mode entry time must be finite")

        converged: bool = False
        event_iteration: int
        for event_iteration in range(self._maximum_event_iterations):
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            discrete_result: FmiThreeWorkerDiscreteStatesResult = (
                self._session.update_model_exchange_discrete_states()
            )
            if discrete_result.terminate_simulation:
                raise RuntimeError(
                    "FMI 3 Model Exchange requested termination in Event Mode"
                )
            else:
                pass
            if discrete_result.next_event_time_defined:
                normalized_next_event_time: float = float(
                    discrete_result.next_event_time
                )
                if (
                    math.isfinite(normalized_next_event_time)
                    and normalized_next_event_time > normalized_entry_time
                ):
                    self._next_event_time = normalized_next_event_time
                else:
                    raise RuntimeError(
                        "FMI 3 nextEventTime must be finite and follow Event Mode entry"
                    )
            else:
                self._next_event_time = None
            if discrete_result.discrete_states_need_update:
                pass
            else:
                converged = True
                break
        if converged:
            pass
        else:
            raise RuntimeError(
                "FMI 3 Model Exchange Event Mode exceeded its iteration bound"
            )
        # Only a converged discrete state may return to continuous evaluation.
        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        self._session.enter_model_exchange_continuous_time_mode()
        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        state_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        state_values, readable_values = (
            self._session.read_model_exchange_state_and_values()
        )
        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        event_indicators: tuple[float, ...] = (
            self._session.get_model_exchange_event_indicators()
        )
        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        nominal_values: tuple[float, ...] = (
            self._session.get_model_exchange_continuous_state_nominals()
        )
        return state_values, readable_values, event_indicators, nominal_values

    def initialize(
        self,
        start_time: float,
        stop_time: float | None,
        relative_tolerance: float | None,
        initial_writable_values: tuple[float, ...],
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Initialize, settle initial Event Mode, and establish acceptance.

        :param start_time: Finite simulation start time.
        :param stop_time: Optional finite stop time greater than the start.
        :param relative_tolerance: Optional finite positive relative tolerance.
        :param initial_writable_values: Complete bound FMI input vector.
        :param evaluation_budget: Optional owner-provided initialization budget.
        :return: Accepted continuous states and readable values.
        """

        if self._initialized:
            raise RuntimeError("FMI 3 coordinator is already initialized")
        else:
            pass
        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        self._session.initialize_model_exchange(
            start_time=start_time,
            stop_time=stop_time,
            relative_tolerance=relative_tolerance,
            initial_writable_float64_values=initial_writable_values,
        )
        state_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        event_indicators: tuple[float, ...]
        nominal_values: tuple[float, ...]
        (
            state_values,
            readable_values,
            event_indicators,
            nominal_values,
        ) = self._settle_event_mode(
            entry_time=float(start_time),
            evaluation_budget=evaluation_budget,
        )
        # Capture derivatives at the exact continuous point so the no-checkpoint
        # branch can later prove that visible reconstruction is lossless.
        accepted_derivatives: tuple[float, ...]
        evaluated_readable_values: tuple[float, ...]
        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        accepted_derivatives, evaluated_readable_values = (
            self._session.evaluate_model_exchange(
                time_value=float(start_time),
                continuous_state_values=state_values,
                writable_float64_values=tuple(initial_writable_values),
            )
        )
        # Presenting the exact continuous point may legitimately refresh
        # outputs after Event Mode.  The post-evaluation values, rather than
        # the earlier Event Mode observation, define the accepted point.
        readable_values = evaluated_readable_values
        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        event_indicators = (
            self._session.get_model_exchange_event_indicators()
        )
        # Native state is retained when available.  Standards-conforming FMUs
        # without Get/Set FMU State use exact visible reconstruction instead.
        if self._session.supports_fmu_state_checkpoint():
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            self._session.save_checkpoint()
            self._has_checkpoint = True
        else:
            self._has_checkpoint = False
        self._accepted_time = float(start_time)
        self._accepted_states = state_values
        self._accepted_inputs = tuple(initial_writable_values)
        self._accepted_derivatives = accepted_derivatives
        self._accepted_readable_values = readable_values
        self._accepted_event_indicators = event_indicators
        self._accepted_nominals = nominal_values
        self._clear_candidate()
        self._initialized = True
        return state_values, readable_values

    def _reconstruct_and_validate_point(
        self,
        time_value: float,
        state_values: tuple[float, ...],
        writable_values: tuple[float, ...],
        expected_derivative_values: tuple[float, ...],
        expected_readable_values: tuple[float, ...],
        expected_event_indicators: tuple[float, ...],
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> None:
        """Re-present and exactly validate one visible continuous point.

        This is a fail-closed compatibility boundary for FMI 3 FMUs that do not
        implement Get/Set FMU State.  It does not claim to reconstruct hidden
        delay buffers, Event Mode state, or vendor-private state.

        :param time_value: Exact stored point time.
        :param state_values: Exact stored continuous states.
        :param writable_values: Exact stored writable inputs.
        :param expected_derivative_values: Previously observed derivatives.
        :param expected_readable_values: Previously observed bound outputs.
        :param expected_event_indicators: Previously observed indicators.
        :param evaluation_budget: Optional owner-provided runtime-call budget.
        :return: None.
        :raises RuntimeError: If any visible value differs after reconstruction.
        """

        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        reconstructed_derivatives: tuple[float, ...]
        reconstructed_readable_values: tuple[float, ...]
        reconstructed_derivatives, reconstructed_readable_values = (
            self._session.evaluate_model_exchange(
                time_value=time_value,
                continuous_state_values=state_values,
                writable_float64_values=writable_values,
            )
        )
        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        reconstructed_event_indicators: tuple[float, ...] = (
            self._session.get_model_exchange_event_indicators()
        )
        if (
            reconstructed_derivatives == expected_derivative_values
            and reconstructed_readable_values == expected_readable_values
            and reconstructed_event_indicators == expected_event_indicators
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 no-checkpoint visible reconstruction detected "
                "unsupported observable state leakage"
            )

    def evaluate_candidate(
        self,
        time_value: float,
        continuous_state_values: tuple[float, ...],
        writable_values: tuple[float, ...],
        presented_derivative_values: tuple[float, ...] | None = None,
        presented_readable_values: tuple[float, ...] | None = None,
    ) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
        """Evaluate one candidate without accepting or integrating it.

        :param time_value: Candidate time not earlier than the accepted time.
        :param continuous_state_values: Complete solver-provided candidate state.
        :param writable_values: Complete bound FMI input vector at the candidate.
        :param presented_derivative_values: Derivatives already read at this exact point.
        :param presented_readable_values: Outputs already read at this exact point.
        :return: Derivatives, readable values, and event indicators.
        """

        accepted_time: float | None = self._accepted_time
        accepted_states: tuple[float, ...] | None = self._accepted_states
        if (
            self._initialized
            and accepted_time is not None
            and accepted_states is not None
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 candidate evaluation requires one free initialized slot"
            )
        normalized_time: float = float(time_value)
        if math.isfinite(normalized_time) and normalized_time >= accepted_time:
            pass
        else:
            raise ValueError(
                "FMI 3 candidate time must be finite and not precede acceptance"
            )
        if len(continuous_state_values) == len(accepted_states):
            pass
        else:
            raise ValueError(
                "FMI 3 candidate state cardinality differs from acceptance"
            )
        if (
            presented_derivative_values is None
            and presented_readable_values is None
        ):
            derivative_values: tuple[float, ...]
            readable_values: tuple[float, ...]
            derivative_values, readable_values = (
                self._session.evaluate_model_exchange(
                    time_value=normalized_time,
                    continuous_state_values=continuous_state_values,
                    writable_float64_values=writable_values,
                )
            )
        else:
            if (
                presented_derivative_values is not None
                and presented_readable_values is not None
                and len(presented_derivative_values) == len(accepted_states)
            ):
                derivative_values = tuple(presented_derivative_values)
                readable_values = tuple(presented_readable_values)
            else:
                raise ValueError(
                    "FMI 3 presented candidate derivatives and outputs must be "
                    "complete and supplied together"
                )
        event_indicators: tuple[float, ...] = (
            self._session.get_model_exchange_event_indicators()
        )
        self._candidate_time = normalized_time
        self._candidate_states = tuple(continuous_state_values)
        self._candidate_inputs = tuple(writable_values)
        self._candidate_derivatives = derivative_values
        self._candidate_readable_values = readable_values
        self._candidate_event_indicators = event_indicators
        return derivative_values, readable_values, event_indicators

    def evaluate_probe(
        self,
        time_value: float,
        continuous_state_values: tuple[float, ...],
        writable_values: tuple[float, ...],
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Evaluate a temporary continuous point without creating a candidate.

        Successive residual and Jacobian probes stay in Continuous-Time Mode.
        The logical solver transaction restores its accepted or pending point
        once, after the complete solve or localization operation.

        :param time_value: Finite probe time not earlier than acceptance.
        :param continuous_state_values: Complete solver-provided probe state.
        :param writable_values: Complete bound FMI input vector.
        :return: Derivatives and readable values at the probe point.
        """

        accepted_time: float | None = self._accepted_time
        accepted_states: tuple[float, ...] | None = self._accepted_states
        if (
            self._initialized
            and accepted_time is not None
            and accepted_states is not None
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 probe evaluation requires an initialized accepted point"
            )
        normalized_time: float = float(time_value)
        if math.isfinite(normalized_time) and normalized_time >= accepted_time:
            pass
        else:
            raise ValueError(
                "FMI 3 probe time must be finite and not precede acceptance"
            )
        if len(continuous_state_values) == len(accepted_states):
            pass
        else:
            raise ValueError(
                "FMI 3 probe state cardinality differs from acceptance"
            )
        derivative_values: tuple[float, ...]
        readable_values: tuple[float, ...]
        derivative_values, readable_values = (
            self._session.evaluate_model_exchange(
                time_value=normalized_time,
                continuous_state_values=continuous_state_values,
                writable_float64_values=writable_values,
            )
        )
        return derivative_values, readable_values

    def evaluate_event_indicators_probe(
        self,
        time_value: float,
        continuous_state_values: tuple[float, ...],
        point_is_presented: bool = False,
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> tuple[float, ...]:
        """Evaluate event indicators inside the current candidate interval.

        The caller supplies an interpolated continuous state while this
        coordinator preserves the already prepared candidate.  Restoring that
        candidate after every probe keeps accept_candidate() independent
        while native checkpoint restoration preserves hidden FMU state.

        :param time_value: Probe time inside the accepted-candidate interval.
        :param continuous_state_values: Interpolated complete state vector.
        :param point_is_presented: Whether the preceding BE solve left this exact point visible.
        :param evaluation_budget: Optional owner-provided runtime-call budget.
        :return: Event indicators at the probe point.
        :raises RuntimeError: If no complete candidate interval is available.
        """

        accepted_time: float | None = self._accepted_time
        accepted_states: tuple[float, ...] | None = self._accepted_states
        candidate_time: float | None = self._candidate_time
        candidate_states: tuple[float, ...] | None = self._candidate_states
        candidate_inputs: tuple[float, ...] | None = self._candidate_inputs
        candidate_derivatives: tuple[float, ...] | None = (
            self._candidate_derivatives
        )
        candidate_readable_values: tuple[float, ...] | None = (
            self._candidate_readable_values
        )
        candidate_event_indicators: tuple[float, ...] | None = (
            self._candidate_event_indicators
        )
        if (
            self._initialized
            and accepted_time is not None
            and accepted_states is not None
            and candidate_time is not None
            and candidate_states is not None
            and candidate_inputs is not None
            and candidate_derivatives is not None
            and candidate_readable_values is not None
            and candidate_event_indicators is not None
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 event-indicator probe requires a complete candidate interval"
            )

        normalized_time: float = float(time_value)
        if (
            math.isfinite(normalized_time)
            and accepted_time <= normalized_time <= candidate_time
        ):
            pass
        else:
            raise ValueError(
                "FMI 3 event-indicator probe must remain inside its candidate interval"
            )
        if len(continuous_state_values) == len(accepted_states):
            pass
        else:
            raise ValueError(
                "FMI 3 event-indicator probe state cardinality differs from acceptance"
            )

        # A method-consistent localization solve already leaves its final point
        # visible. Compatibility callers may still present the point here.
        if point_is_presented:
            pass
        else:
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            self._session.evaluate_model_exchange(
                time_value=normalized_time,
                continuous_state_values=continuous_state_values,
                writable_float64_values=candidate_inputs,
            )
        if evaluation_budget is not None:
            evaluation_budget.consume()
        else:
            pass
        probe_event_indicators: tuple[float, ...] = (
            self._session.get_model_exchange_event_indicators()
        )

        # The native instance must again represent the prepared endpoint before
        # it can be accepted or rejected by the surrounding transaction.
        if self._session.supports_fmu_state_checkpoint():
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            self._session.restore_checkpoint()
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            restored_derivatives: tuple[float, ...]
            restored_readable_values: tuple[float, ...]
            restored_derivatives, restored_readable_values = (
                self._session.evaluate_model_exchange(
                    time_value=candidate_time,
                    continuous_state_values=candidate_states,
                    writable_float64_values=candidate_inputs,
                )
            )
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            restored_event_indicators: tuple[float, ...] = (
                self._session.get_model_exchange_event_indicators()
            )
            if (
                restored_derivatives == candidate_derivatives
                and restored_readable_values == candidate_readable_values
                and restored_event_indicators == candidate_event_indicators
            ):
                pass
            else:
                raise RuntimeError(
                    "FMI 3 checkpoint restoration did not re-establish the "
                    "pending endpoint"
                )
        else:
            self._reconstruct_and_validate_point(
                time_value=candidate_time,
                state_values=candidate_states,
                writable_values=candidate_inputs,
                expected_derivative_values=candidate_derivatives,
                expected_readable_values=candidate_readable_values,
                expected_event_indicators=candidate_event_indicators,
                evaluation_budget=evaluation_budget,
            )
        return probe_event_indicators

    def reject_candidate(
        self,
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> None:
        """Restore the accepted native point and clear the candidate.

        :param evaluation_budget: Optional owner-provided runtime-call budget.
        :return: None.
        :raises RuntimeError: If no complete accepted point exists.
        """

        accepted_time: float | None = self._accepted_time
        accepted_states: tuple[float, ...] | None = self._accepted_states
        accepted_inputs: tuple[float, ...] | None = self._accepted_inputs
        accepted_derivatives: tuple[float, ...] | None = (
            self._accepted_derivatives
        )
        accepted_readable_values: tuple[float, ...] | None = (
            self._accepted_readable_values
        )
        accepted_event_indicators: tuple[float, ...] | None = (
            self._accepted_event_indicators
        )
        if (
            self._initialized
            and accepted_time is not None
            and accepted_states is not None
            and accepted_inputs is not None
            and accepted_derivatives is not None
            and accepted_readable_values is not None
            and accepted_event_indicators is not None
        ):
            if self._session.supports_fmu_state_checkpoint():
                if evaluation_budget is not None:
                    evaluation_budget.consume()
                else:
                    pass
                self._session.restore_checkpoint()
            else:
                self._reconstruct_and_validate_point(
                    time_value=accepted_time,
                    state_values=accepted_states,
                    writable_values=accepted_inputs,
                    expected_derivative_values=accepted_derivatives,
                    expected_readable_values=accepted_readable_values,
                    expected_event_indicators=accepted_event_indicators,
                    evaluation_budget=evaluation_budget,
                )
            self._clear_candidate()
        else:
            raise RuntimeError(
                "FMI 3 rejection requires a complete accepted point"
            )

    def accept_candidate(
        self,
        importer_detected_event: bool,
        evaluation_budget: FmuMeEvaluationBudget | None = None,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Accept one candidate and settle Event Mode when requested.

        :param importer_detected_event: Whether the solver localized an event at
            the candidate point.
        :param evaluation_budget: Optional owner-provided runtime-call budget.
        :return: Accepted continuous states and readable values after events.
        :raises RuntimeError: If the FMU requests simulation termination.
        """

        candidate_time: float | None = self._candidate_time
        candidate_states: tuple[float, ...] | None = self._candidate_states
        candidate_inputs: tuple[float, ...] | None = self._candidate_inputs
        candidate_readable_values: tuple[float, ...] | None = (
            self._candidate_readable_values
        )
        candidate_derivatives: tuple[float, ...] | None = (
            self._candidate_derivatives
        )
        candidate_event_indicators: tuple[float, ...] | None = (
            self._candidate_event_indicators
        )
        previous_nominals: tuple[float, ...] | None = self._accepted_nominals
        if (
            self.has_pending_candidate()
            and candidate_time is not None
            and candidate_states is not None
            and candidate_inputs is not None
            and candidate_derivatives is not None
            and candidate_readable_values is not None
            and candidate_event_indicators is not None
            and previous_nominals is not None
        ):
            pass
        else:
            raise RuntimeError(
                "FMI 3 candidate acceptance requires a complete candidate"
            )
        if self._session.needs_completed_integrator_step():
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            completed_result: FmiThreeWorkerCompletedIntegratorStepResult = (
                self._session.complete_model_exchange_integrator_step(
                    no_set_fmu_state_prior_to_current_point=(
                        not self._session.supports_fmu_state_checkpoint()
                    )
                )
            )
            if completed_result.terminate_simulation:
                raise RuntimeError(
                    "FMI 3 Model Exchange requested simulation termination"
                )
            else:
                pass
            completed_step_requested_event: bool = (
                completed_result.enter_event_mode
            )
        else:
            completed_step_requested_event = False
        event_is_required: bool = (
            bool(importer_detected_event) or completed_step_requested_event
        )
        accepted_states: tuple[float, ...]
        accepted_derivatives: tuple[float, ...]
        accepted_readable_values: tuple[float, ...]
        accepted_event_indicators: tuple[float, ...]
        accepted_nominals: tuple[float, ...]
        if event_is_required:
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            self._session.enter_model_exchange_event_mode()
            (
                accepted_states,
                accepted_readable_values,
                accepted_event_indicators,
                accepted_nominals,
            ) = self._settle_event_mode(
                entry_time=candidate_time,
                evaluation_budget=evaluation_budget,
            )
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            evaluated_readable_values: tuple[float, ...]
            accepted_derivatives, evaluated_readable_values = (
                self._session.evaluate_model_exchange(
                    time_value=candidate_time,
                    continuous_state_values=accepted_states,
                    writable_float64_values=candidate_inputs,
                )
            )
            if evaluated_readable_values == accepted_readable_values:
                pass
            else:
                raise RuntimeError(
                    "FMI 3 post-event readable values changed while capturing "
                    "accepted derivatives"
                )
        else:
            accepted_states = candidate_states
            accepted_derivatives = candidate_derivatives
            accepted_readable_values = candidate_readable_values
            accepted_event_indicators = candidate_event_indicators
            accepted_nominals = previous_nominals
        # Replacing the checkpoint commits the new accepted FMI internal state
        # only for FMUs that implement the optional state API.
        if self._session.supports_fmu_state_checkpoint():
            if evaluation_budget is not None:
                evaluation_budget.consume()
            else:
                pass
            self._session.save_checkpoint()
            self._has_checkpoint = True
        else:
            self._has_checkpoint = False
        self._accepted_time = candidate_time
        self._accepted_states = accepted_states
        self._accepted_inputs = candidate_inputs
        self._accepted_derivatives = accepted_derivatives
        self._accepted_readable_values = accepted_readable_values
        self._accepted_event_indicators = accepted_event_indicators
        self._accepted_nominals = accepted_nominals
        self._clear_candidate()
        return accepted_states, accepted_readable_values

    def close(self) -> None:
        """Release the owned session and clear all coordinator snapshots.

        :return: None.
        """

        self._session.close()
        self._initialized = False
        self._has_checkpoint = False
        self._accepted_time = None
        self._accepted_states = None
        self._accepted_inputs = None
        self._accepted_derivatives = None
        self._accepted_readable_values = None
        self._accepted_event_indicators = None
        self._accepted_nominals = None
        self._next_event_time = None
        self._clear_candidate()
