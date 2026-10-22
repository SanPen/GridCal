# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from enum import Enum

import numpy as np

from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_bundle import JMartiFitBundle


class JMartiDiscretization(Enum):
    """Convention used by stored modal coefficients and direct terms."""

    ZeroOrderHold = "Zero-order hold"
    Trapezoidal = "Trapezoidal"


class JMartiModeRuntimeData:
    """
    Discrete-time runtime coefficients of one scalar JMARTI modal channel.

    The EMT runtime will later consume these coefficients directly instead of
    re-discretizing every pole on the fly. This keeps the time-stepping loop as
    lean as possible.
    """

    __slots__ = (
        '_mode_index',
        '_tau_s',
        '_delay_step_count',
        '_residual_delay_s',
        '_yc_poles_s',
        '_yc_residues',
        '_yc_constant_term',
        '_yc_proportional_term',
        '_hres_poles_s',
        '_hres_residues',
        '_hres_constant_term',
        '_hres_proportional_term',
        '_yc_alpha',
        '_yc_beta',
        '_hres_alpha',
        '_hres_beta',
    )

    def __init__(self,
                 mode_index: int,
                 tau_s: float,
                 delay_step_count: int,
                 residual_delay_s: float,
                 yc_poles_s: np.ndarray,
                 yc_residues: np.ndarray,
                 yc_constant_term: complex,
                 yc_proportional_term: complex,
                 hres_poles_s: np.ndarray,
                 hres_residues: np.ndarray,
                 hres_constant_term: complex,
                 hres_proportional_term: complex,
                 yc_alpha: np.ndarray,
                 yc_beta: np.ndarray,
                 hres_alpha: np.ndarray,
                 hres_beta: np.ndarray) -> None:
        """
        Store one discretized modal runtime record.

        :param mode_index: Modal channel index.
        :param tau_s: Estimated pure delay in seconds.
        :param delay_step_count: Integer delay in EMT steps.
        :param residual_delay_s: Remaining sub-step delay in seconds.
        :param yc_poles_s: Continuous-time poles of ``Yc``.
        :param yc_residues: Residues of ``Yc``.
        :param yc_constant_term: Constant term of ``Yc``.
        :param yc_proportional_term: Proportional term of ``Yc``.
        :param hres_poles_s: Continuous-time poles of ``Hres``.
        :param hres_residues: Residues of ``Hres``.
        :param hres_constant_term: Constant term of ``Hres``.
        :param hres_proportional_term: Proportional term of ``Hres``.
        :param yc_alpha: Trapezoidal discrete state-transition multipliers of ``Yc``.
        :param yc_beta: Trapezoidal discrete input gains of ``Yc``.
        :param hres_alpha: Trapezoidal discrete state-transition multipliers of ``Hres``.
        :param hres_beta: Trapezoidal discrete input gains of ``Hres``.
        :return: None.
        """
        self._mode_index: int = int(mode_index)
        self._tau_s: float = float(tau_s)
        self._delay_step_count: int = int(delay_step_count)
        self._residual_delay_s: float = float(residual_delay_s)
        self._yc_poles_s: np.ndarray = np.asarray(yc_poles_s, dtype=np.complex128)
        self._yc_residues: np.ndarray = np.asarray(yc_residues, dtype=np.complex128)
        self._yc_constant_term: complex = complex(yc_constant_term)
        self._yc_proportional_term: complex = complex(yc_proportional_term)
        self._hres_poles_s: np.ndarray = np.asarray(hres_poles_s, dtype=np.complex128)
        self._hres_residues: np.ndarray = np.asarray(hres_residues, dtype=np.complex128)
        self._hres_constant_term: complex = complex(hres_constant_term)
        self._hres_proportional_term: complex = complex(hres_proportional_term)
        self._yc_alpha: np.ndarray = np.asarray(yc_alpha, dtype=np.complex128)
        self._yc_beta: np.ndarray = np.asarray(yc_beta, dtype=np.complex128)
        self._hres_alpha: np.ndarray = np.asarray(hres_alpha, dtype=np.complex128)
        self._hres_beta: np.ndarray = np.asarray(hres_beta, dtype=np.complex128)

    def get_mode_index(self) -> int:
        """
        Return the modal channel index.

        :return: Modal channel index.
        """
        return self._mode_index

    def get_tau_s(self) -> float:
        """
        Return the pure delay in seconds.

        :return: Pure delay in seconds.
        """
        return self._tau_s

    def get_delay_step_count(self) -> int:
        """
        Return the integer delay in EMT steps.

        :return: Integer delay in EMT steps.
        """
        return self._delay_step_count

    def get_residual_delay_s(self) -> float:
        """
        Return the unresolved sub-step delay in seconds.

        :return: Residual delay in seconds.
        """
        return self._residual_delay_s

    def get_yc_poles_s(self) -> np.ndarray:
        """
        Return the continuous-time poles of ``Yc``.

        :return: Complex pole vector of ``Yc``.
        """
        return self._yc_poles_s

    def get_yc_residues(self) -> np.ndarray:
        """
        Return the residues of ``Yc``.

        :return: Complex residue vector of ``Yc``.
        """
        return self._yc_residues

    def get_yc_constant_term(self) -> complex:
        """
        Return the constant term of ``Yc``.

        :return: Complex constant term of ``Yc``.
        """
        return self._yc_constant_term

    def get_yc_proportional_term(self) -> complex:
        """
        Return the proportional term of ``Yc``.

        :return: Complex proportional term of ``Yc``.
        """
        return self._yc_proportional_term

    def get_hres_poles_s(self) -> np.ndarray:
        """
        Return the continuous-time poles of ``Hres``.

        :return: Complex pole vector of ``Hres``.
        """
        return self._hres_poles_s

    def get_hres_residues(self) -> np.ndarray:
        """
        Return the residues of ``Hres``.

        :return: Complex residue vector of ``Hres``.
        """
        return self._hres_residues

    def get_hres_constant_term(self) -> complex:
        """
        Return the constant term of ``Hres``.

        :return: Complex constant term of ``Hres``.
        """
        return self._hres_constant_term

    def get_hres_proportional_term(self) -> complex:
        """
        Return the proportional term of ``Hres``.

        :return: Complex proportional term of ``Hres``.
        """
        return self._hres_proportional_term

    def get_yc_alpha(self) -> np.ndarray:
        """
        Return the stored discrete state-transition multipliers of ``Yc``.

        :return: Complex transition multipliers.
        """
        return self._yc_alpha

    def get_yc_beta(self) -> np.ndarray:
        """
        Return the stored discrete input gains of ``Yc``.

        :return: Complex input gains.
        """
        return self._yc_beta

    def get_hres_alpha(self) -> np.ndarray:
        """
        Return the stored discrete state-transition multipliers of ``Hres``.

        :return: Complex transition multipliers.
        """
        return self._hres_alpha

    def get_hres_beta(self) -> np.ndarray:
        """
        Return the stored discrete input gains of ``Hres``.

        :return: Complex input gains.
        """
        return self._hres_beta


class JMartiRuntimeData:
    """
    Runtime-ready discrete JMARTI data built from one offline fit bundle.
    """

    __slots__ = (
        '_time_step_s',
        '_line_length_m',
        '_phase_labels',
        '_modal_transform',
        '_modal_transform_inv',
        '_reference_frequency_hz',
        '_mode_data',
        '_discretization',
    )

    def __init__(self,
                 time_step_s: float,
                 line_length_m: float,
                 phase_labels: tuple[str, ...],
                 modal_transform: np.ndarray,
                 modal_transform_inv: np.ndarray,
                 reference_frequency_hz: float,
                 mode_data: tuple[JMartiModeRuntimeData, ...],
                 discretization: JMartiDiscretization = JMartiDiscretization.ZeroOrderHold) -> None:
        """
        Store one runtime-ready JMARTI dataset.

        :param time_step_s: EMT time step in seconds.
        :param line_length_m: Line length in meters.
        :param phase_labels: Ordered phase labels.
        :param modal_transform: Frozen modal transform.
        :param modal_transform_inv: Inverse frozen modal transform.
        :param reference_frequency_hz: Frequency used to freeze the modal basis.
        :param mode_data: Discrete modal runtime data.
        :param discretization: Stored coefficient convention; legacy records use ZOH.
        :return: None.
        """
        self._time_step_s: float = float(time_step_s)
        self._line_length_m: float = float(line_length_m)
        self._phase_labels: tuple[str, ...] = phase_labels
        self._modal_transform: np.ndarray = np.asarray(modal_transform, dtype=np.complex128)
        self._modal_transform_inv: np.ndarray = np.asarray(modal_transform_inv, dtype=np.complex128)
        self._reference_frequency_hz: float = float(reference_frequency_hz)
        self._mode_data: tuple[JMartiModeRuntimeData, ...] = mode_data
        self._discretization: JMartiDiscretization = discretization

    def get_discretization(self) -> JMartiDiscretization:
        """Return the stored coefficient convention.

        :return: Discretization used for the modal coefficients and direct terms.
        """
        return self._discretization

    def get_time_step_s(self) -> float:
        """
        Return the EMT time step in seconds.

        :return: EMT time step in seconds.
        """
        return self._time_step_s

    def get_mode_data(self) -> tuple[JMartiModeRuntimeData, ...]:
        """
        Return the discrete modal runtime records.

        :return: Modal runtime tuple.
        """
        return self._mode_data

    def get_modal_transform(self) -> np.ndarray:
        """
        Return the frozen modal transform.

        :return: Complex modal transform.
        """
        return self._modal_transform

    def get_modal_transform_inv(self) -> np.ndarray:
        """
        Return the inverse frozen modal transform.

        :return: Inverse modal transform.
        """
        return self._modal_transform_inv

    def get_line_length_m(self) -> float:
        """
        Return the line length in meters.

        :return: Line length in meters.
        """
        return self._line_length_m

    def get_phase_labels(self) -> tuple[str, ...]:
        """
        Return the ordered phase labels.

        :return: Ordered phase-label tuple.
        """
        return self._phase_labels

    def get_reference_frequency_hz(self) -> float:
        """
        Return the modal-reference frequency.

        :return: Reference frequency in Hz.
        """
        return self._reference_frequency_hz

    def get_mode_count(self) -> int:
        """
        Return the number of modes.

        :return: Number of modes.
        """
        return int(len(self._mode_data))


def _build_trapezoidal_discrete_coefficients(poles_s: np.ndarray,
                                            residues: np.ndarray,
                                            time_step_s: float) -> tuple[np.ndarray, np.ndarray, complex]:
    """Convert pole-residue filters to a trapezoidal companion realization.

    The runtime stores history states with transfer beta / (z - alpha).
    Trapezoidal integration also contributes an instantaneous input term;
    return it separately so it enters the Norton conductance as well as the
    propagation filter. Omitting this term would introduce a sample lag.
    """
    denominator = 1.0 - 0.5 * time_step_s * poles_s
    alpha = (1.0 + 0.5 * time_step_s * poles_s) / denominator
    beta = time_step_s * residues / denominator**2
    direct_term = complex(np.sum(0.5 * time_step_s * residues / denominator))
    return alpha, beta, direct_term


def _build_delay_step_decomposition(tau_s: float, time_step_s: float) -> tuple[int, float]:
    """
    Split one pure delay into an integer number of EMT steps and a residual part.

    :param tau_s: Pure delay in seconds.
    :param time_step_s: EMT time step in seconds.
    :return: Tuple ``(delay_step_count, residual_delay_s)``.
    """
    delay_step_count: int = int(np.floor(float(tau_s) / float(time_step_s)))
    residual_delay_s: float = float(tau_s - delay_step_count * time_step_s)
    return delay_step_count, residual_delay_s


def build_jmarti_runtime_data(fit_bundle: JMartiFitBundle | JMartiRuntimeData,
                              time_step_s: float) -> JMartiRuntimeData:
    """Build a private timestep-specific record from declared continuous data.

    New records use trapezoidal coefficients. Data overrides retain their
    physical coefficients when retimed; their declared method determines how
    to recover the continuous direct term. Their
    original discrete arrays must agree with their continuous metadata within
    componentwise floating-point operation bounds; no fit fallback is inferred.

    :param fit_bundle: Declared offline fit or authoritative discrete source.
    :param time_step_s: Positive finite target EMT timestep in seconds.
    :return: New runtime data; the supplied source is never modified.
    :raises ValueError: If mandatory source metadata is inconsistent or invalid.
    """
    h: float = float(time_step_s)
    count: int = fit_bundle.get_mode_count()
    transform: np.ndarray = fit_bundle.get_modal_transform()
    inverse: np.ndarray = fit_bundle.get_modal_transform_inv()
    if (np.isfinite(h) and h > 0.0 and count > 0
            and len(fit_bundle.get_phase_labels()) == count
            and transform.shape == (count, count) and inverse.shape == (count, count)
            and np.isfinite(transform).all() and np.isfinite(inverse).all()
            and np.isfinite(fit_bundle.get_line_length_m())
            and np.isfinite(fit_bundle.get_reference_frequency_hz())):
        pass
    else:
        raise ValueError("JMARTI conversion requires finite positive timestep and aligned source dimensions")
    if isinstance(fit_bundle, JMartiFitBundle):
        if (len(fit_bundle.get_yc_fits()) == count
                and len(fit_bundle.get_hres_fits()) == count
                and len(fit_bundle.get_mode_delays()) == count):
            pass
        else:
            raise ValueError("JMARTI fit families have inconsistent cardinality")
    else:
        pass
    source_h: float = fit_bundle.get_time_step_s() if isinstance(fit_bundle, JMartiRuntimeData) else h
    if np.isfinite(source_h) and source_h > 0.0:
        pass
    else:
        raise ValueError("JMARTI declared runtime timestep is invalid")
    unit_roundoff: float = np.finfo(float).eps / 2.0
    gamma: float = 128.0 * unit_roundoff / (1.0 - 128.0 * unit_roundoff)
    underflow: float = 128.0 * float(np.nextafter(0.0, 1.0))
    records: list[JMartiModeRuntimeData | None] = list([None] * count)
    index: int
    for index in range(count):
        tau: float
        poles_y: np.ndarray
        residues_y: np.ndarray
        poles_h: np.ndarray
        residues_h: np.ndarray
        direct_y: complex
        direct_h: complex
        proportional_y: complex
        proportional_h: complex
        source: JMartiModeRuntimeData | None = None
        if isinstance(fit_bundle, JMartiRuntimeData):
            source = fit_bundle.get_mode_data()[index]
            if source.get_mode_index() == index:
                pass
            else:
                raise ValueError("JMARTI runtime mode order contradicts its declared metadata")
            tau = source.get_tau_s()
            poles_y, residues_y = source.get_yc_poles_s(), source.get_yc_residues()
            poles_h, residues_h = source.get_hres_poles_s(), source.get_hres_residues()
            direct_y, direct_h = source.get_yc_constant_term(), source.get_hres_constant_term()
            proportional_y, proportional_h = source.get_yc_proportional_term(), source.get_hres_proportional_term()
        else:
            tau = fit_bundle.get_mode_delays()[index].get_tau_s()
            poles_y = fit_bundle.get_yc_fits()[index].get_poles_s()
            residues_y = fit_bundle.get_yc_fits()[index].get_residues()
            poles_h = fit_bundle.get_hres_fits()[index].get_poles_s()
            residues_h = fit_bundle.get_hres_fits()[index].get_residues()
            direct_y = fit_bundle.get_yc_fits()[index].get_constant_term()
            direct_h = fit_bundle.get_hres_fits()[index].get_constant_term()
            proportional_y = fit_bundle.get_yc_fits()[index].get_proportional_term()
            proportional_h = fit_bundle.get_hres_fits()[index].get_proportional_term()
            if (fit_bundle.get_yc_fits()[index].get_mode_index() == index
                    and fit_bundle.get_hres_fits()[index].get_mode_index() == index
                    and fit_bundle.get_mode_delays()[index].get_mode_index() == index):
                pass
            else:
                raise ValueError("JMARTI fit families are not aligned by mode")
        if (np.isfinite(tau) and tau >= 0.0
                and np.isfinite(direct_y) and np.isfinite(direct_h)
                and np.isfinite(proportional_y) and np.isfinite(proportional_h)
                and abs(proportional_y) <= 1.0e-14 and abs(proportional_h) <= 1.0e-14):
            pass
        else:
            raise ValueError("JMARTI delay/direct terms are invalid or proportional terms unsupported")
        family_index: int
        for family_index in range(2):
            poles: np.ndarray = poles_y if family_index == 0 else poles_h
            residues: np.ndarray = residues_y if family_index == 0 else residues_h
            if (poles.ndim == 1 and residues.shape == poles.shape
                    and np.isfinite(poles).all() and np.isfinite(residues).all()):
                pass
            else:
                raise ValueError("JMARTI continuous pole/residue family is invalid")
            if source is not None:
                alpha: np.ndarray = source.get_yc_alpha() if family_index == 0 else source.get_hres_alpha()
                beta: np.ndarray = source.get_yc_beta() if family_index == 0 else source.get_hres_beta()
                if (alpha.shape == poles.shape and beta.shape == poles.shape
                        and np.isfinite(alpha).all() and np.isfinite(beta).all()):
                    pass
                else:
                    raise ValueError("JMARTI discrete family does not match continuous metadata")
                if fit_bundle.get_discretization() == JMartiDiscretization.Trapezoidal:
                    expected_alpha, expected_beta, direct_increment = _build_trapezoidal_discrete_coefficients(
                        poles, residues, source_h,
                    )
                    # Compare each component: a large real part cannot hide an
                    # inconsistent imaginary coefficient in restart metadata.
                    for declared, expected in ((alpha, expected_alpha), (beta, expected_beta)):
                        for actual_component, expected_component in (
                                (declared.real, expected.real), (declared.imag, expected.imag)):
                            bound: np.ndarray = gamma * (np.abs(actual_component) + np.abs(expected_component)) + underflow
                            if np.all(np.abs(actual_component - expected_component) <= bound):
                                pass
                            else:
                                raise ValueError("JMARTI trapezoidal coefficients contradict declared poles/residues")
                    # Recover the continuous direct term before changing h.
                    if family_index == 0:
                        direct_y -= direct_increment
                    else:
                        direct_h -= direct_increment
                elif fit_bundle.get_discretization() == JMartiDiscretization.ZeroOrderHold:
                    pole_index: int
                    for pole_index in range(poles.size):
                        pole: complex = complex(poles[pole_index])
                        residue: complex = complex(residues[pole_index])
                        declared_a: complex = complex(alpha[pole_index])
                        declared_b: complex = complex(beta[pole_index])
                        q: complex = pole * source_h
                        x: float = q.real
                        y: float = q.imag
                        exponential: float = float(np.exp(x))
                        cosine: float = float(np.cos(y))
                        sine: float = float(np.sin(y))
                        expected_a: complex = complex(np.exp(q))
                        a_scale: np.ndarray = np.array((
                            exponential * (abs(cosine) * (1.0 + abs(x)) + abs(sine) * abs(y)),
                            exponential * (abs(sine) * (1.0 + abs(x)) + abs(cosine) * abs(y)),
                        ))
                        a_bound: np.ndarray = gamma * (a_scale + np.array((abs(declared_a.real), abs(declared_a.imag)))) + underflow
                        a_delta: complex = declared_a - expected_a
                        if np.isfinite(a_bound).all() and np.all(np.array((abs(a_delta.real), abs(a_delta.imag))) <= a_bound):
                            pass
                        else:
                            raise ValueError("JMARTI alpha contradicts declared continuous poles")
                        beta_valid: bool = False
                        spelling: int
                        for spelling in range(2):
                            expected_b: complex
                            b_bound: np.ndarray
                            if pole == 0.0 or (spelling == 1 and abs(pole) <= 1.0e-20):
                                expected_b = residue * source_h
                                b_bound = gamma * np.array((abs(expected_b.real) + abs(declared_b.real), abs(expected_b.imag) + abs(declared_b.imag))) + underflow
                            else:
                                z: complex
                                z_bound: np.ndarray
                                if spelling == 0:
                                    z = complex(np.expm1(q))
                                    z_bound = gamma * np.array((
                                        abs(np.expm1(x) * cosine) + 2.0 * np.sin(y / 2.0) ** 2 + exponential * (abs(x * cosine) + abs(y * sine)),
                                        exponential * (abs(sine) * (1.0 + abs(x)) + abs(y * cosine)),
                                    )) + underflow
                                else:
                                    z = declared_a - 1.0
                                    z_bound = gamma * np.array((abs(z.real), abs(z.imag))) + underflow
                                scale_p: float = max(abs(pole.real), abs(pole.imag))
                                normalized: complex = pole / scale_p
                                denominator: float = normalized.real ** 2 + normalized.imag ** 2
                                ur: float = abs(residue.real * z.real) + abs(residue.imag * z.imag)
                                ui: float = abs(residue.real * z.imag) + abs(residue.imag * z.real)
                                er: float = abs(residue.real) * z_bound[0] + abs(residue.imag) * z_bound[1] + gamma * ur + underflow
                                ei: float = abs(residue.real) * z_bound[1] + abs(residue.imag) * z_bound[0] + gamma * ui + underflow
                                terms: np.ndarray = np.array((ur * abs(normalized.real) + ui * abs(normalized.imag), ui * abs(normalized.real) + ur * abs(normalized.imag))) / (scale_p * denominator)
                                propagated: np.ndarray = np.array((er * abs(normalized.real) + ei * abs(normalized.imag), ei * abs(normalized.real) + er * abs(normalized.imag))) / (scale_p * denominator)
                                expected_b = residue * z / pole
                                b_bound = (1.0 + gamma) * propagated + gamma * (terms + np.array((abs(declared_b.real), abs(declared_b.imag)))) + underflow
                            b_delta: complex = declared_b - expected_b
                            beta_valid = beta_valid or bool(np.isfinite(b_bound).all() and np.isfinite(expected_b)
                                and np.all(np.array((abs(b_delta.real), abs(b_delta.imag))) <= b_bound))
                        if beta_valid:
                            pass
                        else:
                            raise ValueError("JMARTI beta contradicts declared continuous poles/residues")
                else:
                    raise ValueError("JMARTI runtime discretization is unsupported")
            else:
                pass
        if source is not None:
            lag_source: int = source.get_delay_step_count()
            residual_source: float = source.get_residual_delay_s()
            source_lag_time: float
            conversion_error: OverflowError
            try:
                source_lag_time = float(lag_source) * source_h
            except OverflowError as conversion_error:
                raise ValueError("JMARTI declared delay count cannot be checked in finite arithmetic") from conversion_error
            source_reconstruction: float = source_lag_time + residual_source
            delay_bound: float = gamma * (abs(tau) + abs(source_lag_time) + abs(residual_source)) + underflow
            if (lag_source >= 0 and np.isfinite(residual_source) and np.isfinite(source_lag_time)
                    and np.isfinite(source_reconstruction) and np.isfinite(delay_bound)
                    and abs(tau - source_reconstruction) <= delay_bound
                    and -delay_bound <= residual_source <= source_h + delay_bound):
                pass
            else:
                raise ValueError("JMARTI delay split contradicts declared continuous delay")
        else:
            pass
        lag: int
        residual: float
        target_delay_ratio: float = tau / h
        if np.isfinite(target_delay_ratio):
            pass
        else:
            raise ValueError("JMARTI private delay/timestep ratio is not finite")
        lag, residual = _build_delay_step_decomposition(tau, h)
        lag_time: float = lag * h
        reconstruction: float = lag_time + residual
        split_bound: float = gamma * (abs(tau) + abs(lag_time) + abs(residual)) + underflow
        if (lag >= 0 and np.isfinite(residual) and np.isfinite(lag_time)
                and np.isfinite(reconstruction) and np.isfinite(split_bound)
                and abs(tau - reconstruction) <= split_bound
                and -split_bound <= residual <= h + split_bound):
            # Normalize only arithmetic endpoints to the existing sampler's
            # effective interpolation. Source tau and source h are untouched.
            fraction: float = min(max(residual / h, 0.0), 1.0)
            if fraction == 1.0:
                lag += 1
                residual = 0.0
            else:
                residual = fraction * h
        else:
            raise ValueError("JMARTI private delay split cannot be represented consistently")
        ay: np.ndarray
        by: np.ndarray
        ah: np.ndarray
        bh: np.ndarray
        ay, by, direct_y_increment = _build_trapezoidal_discrete_coefficients(poles_y, residues_y, h)
        ah, bh, direct_h_increment = _build_trapezoidal_discrete_coefficients(poles_h, residues_h, h)
        if np.isfinite(ay).all() and np.isfinite(by).all() and np.isfinite(ah).all() and np.isfinite(bh).all():
            records[index] = JMartiModeRuntimeData(index, tau, lag, residual, poles_y, residues_y,
                direct_y + direct_y_increment, proportional_y, poles_h, residues_h,
                direct_h + direct_h_increment, proportional_h, ay, by, ah, bh)
        else:
            raise ValueError("JMARTI private discrete coefficients are not finite")
    first_record: JMartiModeRuntimeData | None = records[0]
    if isinstance(first_record, JMartiModeRuntimeData):
        final_records: list[JMartiModeRuntimeData] = list((first_record,)) * count
    else:
        raise ValueError("JMARTI private conversion did not produce its first modal record")
    record: JMartiModeRuntimeData | None
    for index in range(count):
        record = records[index]
        if isinstance(record, JMartiModeRuntimeData):
            final_records[index] = record
        else:
            raise ValueError("JMARTI private conversion did not produce every modal record")
    return JMartiRuntimeData(h, fit_bundle.get_line_length_m(), fit_bundle.get_phase_labels(),
        transform, inverse, fit_bundle.get_reference_frequency_hz(), tuple(final_records),
        JMartiDiscretization.Trapezoidal)


def is_jmarti_phase_real_runtime_data(data: JMartiRuntimeData) -> bool:
    """Prove a sufficient exact real-convolution invariant in phase space.

    A failed structural proof preserves general complex coordinates. An invalid
    declared inverse cannot support either coordinate representation and fails
    before the companion is registered. Intentional imaginary coefficients are
    never compared with a roundoff tolerance to authorize dimension reduction.

    :param data: Fixed typed coefficients and declared modal basis.
    :return: True only for an exactly recognized real phase convolution.
    :raises ValueError: If the mandatory basis is invalid or unbounded.
    """
    count: int = data.get_mode_count()
    transform: np.ndarray = data.get_modal_transform()
    inverse: np.ndarray = data.get_modal_transform_inv()
    if (count > 0 and transform.shape == (count, count) and inverse.shape == (count, count)
            and np.isfinite(transform).all() and np.isfinite(inverse).all()):
        pass
    else:
        raise ValueError("JMARTI coupled modal basis dimensions or values are invalid")
    u: float = np.finfo(float).eps / 2.0
    operations: int = 64 * count + 64
    gamma: float = operations * u / (1.0 - operations * u)
    left: np.ndarray
    right: np.ndarray
    for left, right in ((transform, inverse), (inverse, transform)):
        residual: np.ndarray = np.abs(left @ right - np.eye(count))
        bound: np.ndarray = gamma * (np.abs(left) @ np.abs(right) + np.eye(count))
        if (np.isfinite(bound).all() and np.all(residual <= bound)
                and np.linalg.norm(residual + bound, ord=np.inf) < 1.0):
            pass
        else:
            raise ValueError("JMARTI declared modal transform/inverse are inconsistent")
    all_real: bool = bool(np.all(transform.imag == 0.0) and np.all(inverse.imag == 0.0))
    modes: tuple[JMartiModeRuntimeData, ...] = data.get_mode_data()
    mode: JMartiModeRuntimeData
    maximum_order: int = 0
    for mode in modes:
        coefficients: np.ndarray
        for coefficients in (mode.get_yc_alpha(), mode.get_yc_beta(), mode.get_hres_alpha(), mode.get_hres_beta()):
            if coefficients.ndim == 1 and np.isfinite(coefficients).all():
                all_real = all_real and bool(np.all(coefficients.imag == 0.0))
                maximum_order = max(maximum_order, coefficients.size)
            else:
                raise ValueError("JMARTI coupled discrete coefficients are invalid")
        if (mode.get_yc_alpha().shape == mode.get_yc_beta().shape
                and mode.get_hres_alpha().shape == mode.get_hres_beta().shape
                and np.isfinite(mode.get_yc_constant_term()) and np.isfinite(mode.get_hres_constant_term())):
            all_real = all_real and mode.get_yc_constant_term().imag == 0.0 and mode.get_hres_constant_term().imag == 0.0
        else:
            raise ValueError("JMARTI coupled filter families are not aligned")
    if all_real:
        return True
    else:
        pass
    compatible: np.ndarray = np.zeros((count, count), dtype=bool)
    used: np.ndarray = np.zeros(maximum_order, dtype=bool)
    i: int
    j: int
    for i in range(count):
        for j in range(count):
            a: JMartiModeRuntimeData = modes[i]
            b: JMartiModeRuntimeData = modes[j]
            matches: bool = bool(a.get_delay_step_count() == b.get_delay_step_count()
                and a.get_residual_delay_s() == b.get_residual_delay_s()
                and a.get_yc_constant_term() == np.conj(b.get_yc_constant_term())
                and a.get_hres_constant_term() == np.conj(b.get_hres_constant_term()))
            aa: np.ndarray
            ab: np.ndarray
            ba: np.ndarray
            bb: np.ndarray
            for aa, ab, ba, bb in ((a.get_yc_alpha(), a.get_yc_beta(), b.get_yc_alpha(), b.get_yc_beta()),
                                   (a.get_hres_alpha(), a.get_hres_beta(), b.get_hres_alpha(), b.get_hres_beta())):
                used.fill(False)
                if aa.size == ba.size:
                    k: int
                    for k in range(aa.size):
                        found: bool = False
                        l: int
                        for l in range(ba.size):
                            if not found and not used[l] and aa[k] == np.conj(ba[l]) and ab[k] == np.conj(bb[l]):
                                found = True
                                used[l] = True
                            else:
                                pass
                        matches = matches and found
                else:
                    matches = False
            compatible[i, j] = matches
    if bool(compatible[0, 0] and np.all(compatible[:, 0])):
        return True
    else:
        pass
    partners: np.ndarray = np.full(count, -1, dtype=np.int64)
    for i in range(count):
        found = False
        for j in range(count):
            if compatible[i, j] and np.array_equal(transform[:, j], transform[:, i].conj()):
                partners[i] = j
                found = True
            else:
                pass
        if found:
            pass
        else:
            return False
    return bool(np.array_equal(partners[partners], np.arange(count)))
