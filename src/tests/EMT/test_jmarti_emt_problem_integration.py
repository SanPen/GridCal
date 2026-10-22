from __future__ import annotations

from enum import Enum
import json
import numpy as np
import pytest

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_bundle import JMartiFitBundle, build_jmarti_fit_bundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_fit_options import JMartiFitOptions
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_frequency_samples import build_jmarti_frequency_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_loewner_seed import build_jmarti_mode_loewner_seed
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import build_jmarti_modal_samples
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import estimate_jmarti_mode_delays
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_modal_processing import JMartiModeDelayEstimate
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import JMartiHistoryRuntime
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import get_jmarti_block_runtime_data
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import get_jmarti_block_fit_bundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import set_jmarti_block_fit_bundle
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime import set_jmarti_block_runtime_data
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_runtime_data import JMartiModeRuntimeData, JMartiRuntimeData
from VeraGridEngine.Simulations.EMT.JMARTI_Sim.jmarti_vector_fit import JMartiRationalModeFit, build_jmarti_mode_vector_fit
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.jmarti_line_emt_template import get_jmarti_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_balanced_3ph_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_current_source_emt_template, get_voltage_source_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType, SolverType, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian, SymbolicVector
from VeraGridEngine.Utils.Symbolic.symbolic_io import BlockSaver

def _evaluate_scalar_rational_response(frequency_hz: np.ndarray,
                                       poles_s: np.ndarray,
                                       residues: np.ndarray,
                                       constant_term: complex = 0.0 + 0.0j) -> np.ndarray:
    """
    Evaluate one scalar rational response on the imaginary axis.

    :param frequency_hz: Frequency grid in Hz.
    :param poles_s: Continuous-time poles.
    :param residues: Residues paired with ``poles_s``.
    :param constant_term: Optional constant term.
    :return: Complex response samples.
    """
    angular_frequency: np.ndarray = 2.0 * np.pi * frequency_hz
    response: np.ndarray = np.zeros(frequency_hz.size, dtype=np.complex128)
    sample_index: int = 0
    pole_index: int
    s_value: complex

    while sample_index < frequency_hz.size:
        s_value = 1j * angular_frequency[sample_index]
        response[sample_index] = complex(constant_term)
        pole_index = 0

        while pole_index < poles_s.size:
            response[sample_index] = response[sample_index] + residues[pole_index] / (s_value - poles_s[pole_index])
            pole_index += 1

        sample_index += 1

    return response


def _build_jmarti_fit_bundle_for_three_phase_line() -> object:
    """
    Build one synthetic three-mode JMARTI fit bundle suitable for EMT integration tests.

    :return: Offline JMARTI fit bundle.
    """
    frequency_hz: np.ndarray = np.asarray([10.0, 40.0, 80.0, 160.0, 320.0, 640.0], dtype=np.float64)
    z_per_length: np.ndarray = np.zeros((frequency_hz.size, 3, 3), dtype=np.complex128)
    y_per_length: np.ndarray = np.zeros((frequency_hz.size, 3, 3), dtype=np.complex128)
    sample_index: int = 0
    options = JMartiFitOptions(forced_model_order=1, vf_max_iterations=6)
    yc_mode_responses = [
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-50.0 + 0.0j], dtype=np.complex128), np.asarray([0.30 + 0.0j], dtype=np.complex128), constant_term=0.10 + 0.0j),
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-120.0 + 0.0j], dtype=np.complex128), np.asarray([0.15 + 0.0j], dtype=np.complex128), constant_term=0.08 + 0.0j),
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-200.0 + 0.0j], dtype=np.complex128), np.asarray([0.10 + 0.0j], dtype=np.complex128), constant_term=0.07 + 0.0j),
    ]
    hres_mode_responses = [
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-80.0 + 0.0j], dtype=np.complex128), np.asarray([0.020 + 0.0j], dtype=np.complex128), constant_term=0.85 + 0.0j),
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-160.0 + 0.0j], dtype=np.complex128), np.asarray([0.010 + 0.0j], dtype=np.complex128), constant_term=0.75 + 0.0j),
        _evaluate_scalar_rational_response(frequency_hz, np.asarray([-240.0 + 0.0j], dtype=np.complex128), np.asarray([0.008 + 0.0j], dtype=np.complex128), constant_term=0.65 + 0.0j),
    ]
    mode_index: int
    samples = None
    modal_samples = None
    mode_delays = None
    yc_fits = list()
    hres_fits = list()

    while sample_index < frequency_hz.size:
        z_per_length[sample_index, :, :] = np.diag(np.asarray([
            1.0 + 0.2j * float(sample_index + 1),
            2.0 + 0.3j * float(sample_index + 1),
            3.0 + 0.4j * float(sample_index + 1),
        ], dtype=np.complex128))
        y_per_length[sample_index, :, :] = np.diag(np.asarray([
            yc_mode_responses[0][sample_index] * yc_mode_responses[0][sample_index],
            yc_mode_responses[1][sample_index] * yc_mode_responses[1][sample_index],
            yc_mode_responses[2][sample_index] * yc_mode_responses[2][sample_index],
        ], dtype=np.complex128))
        sample_index += 1

    samples = build_jmarti_frequency_samples(
        frequency_hz=frequency_hz,
        z_per_length=z_per_length,
        y_per_length=y_per_length,
        line_length_m=1000.0,
        phase_labels=("A", "B", "C"),
    )
    modal_samples = build_jmarti_modal_samples(samples=samples, options=options)
    mode_delays = estimate_jmarti_mode_delays(modal_samples, options=options)

    mode_index = 0
    while mode_index < 3:
        yc_fits.append(
            build_jmarti_mode_vector_fit(
                frequency_hz=frequency_hz,
                response_values=modal_samples.get_yc_modal()[:, mode_index],
                loewner_seed=build_jmarti_mode_loewner_seed(
                    frequency_hz,
                    modal_samples.get_yc_modal()[:, mode_index],
                    "Yc",
                    mode_index,
                    options,
                ),
                options=options,
            )
        )
        hres_fits.append(
            build_jmarti_mode_vector_fit(
                frequency_hz=frequency_hz,
                response_values=hres_mode_responses[mode_index],
                loewner_seed=build_jmarti_mode_loewner_seed(
                    frequency_hz,
                    hres_mode_responses[mode_index],
                    "Hres",
                    mode_index,
                    options,
                ),
                options=options,
            )
        )
        mode_index += 1

    return build_jmarti_fit_bundle(
        modal_samples=modal_samples,
        mode_delays=mode_delays,
        yc_fits=yc_fits,
        hres_fits=hres_fits,
    )


def test_jmarti_emt_problem_builds_one_history_runtime_and_runs_short_simulation() -> None:
    grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)
    bus0 = gce.Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10.0)
    generator = gce.Generator(name="Gen", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.2)
    line_template = gce.create_known_abc_overhead_template(
        name="JMartiDemoLine",
        z_nabc=np.array([
            [0.01 + 1j * 0.03, 0.0 + 0.0j, 0.0 + 0.0j],
            [0.0 + 0.0j, 0.01 + 1j * 0.03, 0.0 + 0.0j],
            [0.0 + 0.0j, 0.0 + 0.0j, 0.01 + 1j * 0.03],
        ], dtype=complex),
        ysh_nabc=np.zeros((3, 3), dtype=complex),
        phases=np.array([1, 2, 3]),
        Vnom=10.0,
        frequency=50.0,
    )
    line = gce.Line(name="Line", bus_from=bus0, bus_to=bus1, length=0.1)
    load = gce.Load(name="Load", P1=0.05, P2=0.05, P3=0.05, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.FloatingStar
    pf_options = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1.0e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        generate_report=False,
    )
    emt_options = EmtOptions(
        time_step=1.0e-4,
        simulation_time=3.0e-4,
        tolerance=1.0e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=0,
    )

    grid.add_bus(bus0)
    grid.add_bus(bus1)
    grid.add_generator(bus=bus0, api_obj=generator)
    grid.add_overhead_line(line_template)
    line.apply_template(line_template, grid.Sbase, grid.fBase, gce.Logger())
    grid.add_line(obj=line)
    grid.add_load(bus=bus1, api_obj=load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    set_emt_model(device=generator, model=get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="Gen").block, var_factory=grid.var_factory)
    line_model = get_jmarti_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name="Line").block
    set_jmarti_block_fit_bundle(line_model, _build_jmarti_fit_bundle_for_three_phase_line())
    set_emt_model(device=line, model=line_model, var_factory=grid.var_factory)
    set_emt_model(
        device=load,
        model=get_shunt_rlc_combo_emt_template(
            vf=grid.var_factory,
            include_r=True,
            include_l=False,
            include_c=False,
            phA=True,
            phB=True,
            phC=True,
            connection_type=ShuntConnectionType.FloatingStar,
            direct_r_value=100.0,
            name="Load_R_demo",
        ).block,
        var_factory=grid.var_factory,
    )

    original_line_model = line.emt_model
    original_api_mapping = dict(line.emt_model.api_obj_mapping)
    original_parameter_keys = set(line.emt_model.parameters.keys())
    original_event_keys = set(line.emt_model.event_dict.keys())

    power_flow = PowerFlowDriver3Ph(grid, pf_options)
    power_flow.run()
    problem = EmtProblemDae(grid=grid, options=emt_options, pf_results=None, pf_results_3ph=power_flow.results)
    assert len(problem.history_models) == 1
    assert isinstance(problem.history_models[0], JMartiHistoryRuntime)
    assert line.emt_model is original_line_model
    assert dict(line.emt_model.api_obj_mapping) == original_api_mapping
    assert set(line.emt_model.parameters.keys()) == original_parameter_keys
    assert set(line.emt_model.event_dict.keys()) == original_event_keys
    assert get_jmarti_block_runtime_data(line.emt_model) is None
    runtime_model: Block = problem.history_models[0].block
    assert runtime_model is line.emt_model
    assert problem.history_models[0].runtime_data is not None

    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        verbose=False,
    )
    time_vector, state_history, _diff_history, converged, _diag = solver.simulate(boundary_updater=problem)

    assert len(time_vector) > 1
    assert np.isfinite(state_history).all()
    assert converged is True


class JMartiCouplingTestCase(Enum):
    """Select the ten declared complete-network coupling and boundary fixtures."""

    __slots__ = ()

    DIRECT_REAL_BALANCED = 0
    MIXED_REAL_BASIS_PF3 = 1
    COMPLEX_BASIS_REAL_TRANSFER = 2
    PRODUCTIVE_FIT_SHORT_DIRECT = 3
    COMPLEX_BASIS_UNPAIRED_FIT = 4
    B_PLUS_ONE = 5
    B_MINUS_ONE = 6
    CONSTANT_NABC_ZERO_NEUTRAL = 7
    RANKDEF_ZERO_CURRENT = 8
    INCOMPATIBLE_CURRENT_SUM = 9


def _build_jmarti_coupled_network_case(
        case: JMartiCouplingTestCase,
        solver_type: EmtSolverTypes,
        time_step_s: float | None = None,
) -> tuple[EmtProblemDae, np.ndarray, np.ndarray]:
    """Build the native network and an independent full discrete-frequency orbit.

    The source providers come from the complete physical network equations,
    rather than from the fitted line buffers or the candidate's target solve.
    Both frequency signs retain complex modal channels. The exact real cases
    use their declared invariant phase quotient, including the B=+/-1 cases.

    :param case: Declared modal operator, provider and boundary selection.
    :param solver_type: One of the four existing common-graph EMT backends.
    :param time_step_s: Optional different fixed timestep for fresh construction.
    :return: Native problem,402 target values in V/Wreal/Wimag/I order, and the
        six families of complex frequency phasors used to check filter memory.
    """
    neutral: bool = case == JMartiCouplingTestCase.CONSTANT_NABC_ZERO_NEUTRAL
    boundary: bool = case in (
        JMartiCouplingTestCase.RANKDEF_ZERO_CURRENT,
        JMartiCouplingTestCase.INCOMPATIBLE_CURRENT_SUM,
    )
    fitted: bool = case in (
        JMartiCouplingTestCase.PRODUCTIVE_FIT_SHORT_DIRECT,
        JMartiCouplingTestCase.COMPLEX_BASIS_UNPAIRED_FIT,
    )
    frequency: float = 50.0
    source_h: float = 1e-4
    if fitted:
        frequency = 0.05
    elif neutral or boundary:
        frequency = 0.0
    elif case in (JMartiCouplingTestCase.COMPLEX_BASIS_REAL_TRANSFER,
                  JMartiCouplingTestCase.B_PLUS_ONE, JMartiCouplingTestCase.B_MINUS_ONE):
        frequency = 60.0
    else:
        pass
    h: float = 0.02 if fitted else source_h
    if time_step_s is None:
        pass
    else:
        h = time_step_s
    labels: tuple[str, ...] = ("N", "A", "B", "C") if neutral else ("A", "B", "C")
    m: int = len(labels)
    transform: np.ndarray = np.eye(m, dtype=np.complex128)
    if case in (JMartiCouplingTestCase.MIXED_REAL_BASIS_PF3,
                JMartiCouplingTestCase.CONSTANT_NABC_ZERO_NEUTRAL):
        start: int = 1 if neutral else 0
        transform[start:start + 2, start:start + 2] = np.asarray(
            ((np.cos(0.37), -np.sin(0.37)), (np.sin(0.37), np.cos(0.37))), dtype=np.complex128)
    elif case in (JMartiCouplingTestCase.COMPLEX_BASIS_REAL_TRANSFER,
                  JMartiCouplingTestCase.COMPLEX_BASIS_UNPAIRED_FIT):
        transform[:2, :2] = np.asarray(((1.0, 1.0), (1j, -1j)), dtype=np.complex128) / np.sqrt(2.0)
    else:
        pass
    modes: list[JMartiModeRuntimeData | None] = list([None] * m)
    fit_bundle: JMartiFitBundle | None = None
    if fitted:
        produced: object = _build_jmarti_fit_bundle_for_three_phase_line()
        assert isinstance(produced, JMartiFitBundle)
        fit_bundle = produced
        if case == JMartiCouplingTestCase.PRODUCTIVE_FIT_SHORT_DIRECT:
            transform = fit_bundle.get_modal_transform().copy()
        else:
            # Reindex identical copies of the original unpaired fitted channel.
            # No fitter is rerun and no imaginary coefficient is discarded.
            fit_families: tuple[list[JMartiRationalModeFit], ...] = (
                list(fit_bundle.get_yc_fits()), list(fit_bundle.get_hres_fits()))
            family: list[JMartiRationalModeFit]
            mode_index: int
            for family in fit_families:
                original_fit: JMartiRationalModeFit = family[0]
                for mode_index in range(m):
                    family[mode_index] = JMartiRationalModeFit(
                        mode_index=mode_index, target_name=original_fit.get_target_name(),
                        poles_s=original_fit.get_poles_s().copy(), residues=original_fit.get_residues().copy(),
                        constant_term=original_fit.get_constant_term(), proportional_term=original_fit.get_proportional_term(),
                        fit_error_rms=original_fit.get_fit_error_rms(), max_relative_error=original_fit.get_max_relative_error(),
                        iterations_completed=original_fit.get_iterations_completed(),
                        converged=original_fit.get_converged(), stable=original_fit.get_stable())
            fit_bundle = JMartiFitBundle(
                frequency_hz=produced.get_frequency_hz().copy(), line_length_m=produced.get_line_length_m(),
                phase_labels=labels, modal_transform=transform, modal_transform_inv=np.linalg.inv(transform),
                reference_frequency_hz=produced.get_reference_frequency_hz(),
                decoupling_error_z=produced.get_decoupling_error_z().copy(),
                decoupling_error_y=produced.get_decoupling_error_y().copy(),
                mode_delays=tuple(JMartiModeDelayEstimate(mode_index=mode_index,
                    tau_s=produced.get_mode_delays()[0].get_tau_s(),
                    rms_phase_error_rad=produced.get_mode_delays()[0].get_rms_phase_error_rad()) for mode_index in range(m)),
                yc_fits=fit_families[0], hres_fits=fit_families[1], passivity_report=produced.get_passivity_report())
        for mode_index in range(m):
            yc_fit: JMartiRationalModeFit = fit_bundle.get_yc_fits()[mode_index]
            h_fit: JMartiRationalModeFit = fit_bundle.get_hres_fits()[mode_index]
            poles_y: np.ndarray = yc_fit.get_poles_s().copy()
            poles_h: np.ndarray = h_fit.get_poles_s().copy()
            # The oracle independently discretizes the declared continuous fit.
            alpha_y: np.ndarray = np.exp(poles_y * h)
            alpha_h: np.ndarray = np.exp(poles_h * h)
            beta_y: np.ndarray = yc_fit.get_residues() * np.expm1(poles_y * h) / poles_y
            beta_h: np.ndarray = h_fit.get_residues() * np.expm1(poles_h * h) / poles_h
            tau: float = fit_bundle.get_mode_delays()[mode_index].get_tau_s()
            lag: int = int(np.floor(tau / h))
            modes[mode_index] = JMartiModeRuntimeData(
                mode_index=mode_index, tau_s=tau, delay_step_count=lag, residual_delay_s=tau - lag * h,
                yc_poles_s=poles_y, yc_residues=yc_fit.get_residues().copy(),
                yc_constant_term=yc_fit.get_constant_term(), yc_proportional_term=yc_fit.get_proportional_term(),
                hres_poles_s=poles_h, hres_residues=h_fit.get_residues().copy(),
                hres_constant_term=h_fit.get_constant_term(), hres_proportional_term=h_fit.get_proportional_term(),
                yc_alpha=alpha_y, yc_beta=beta_y, hres_alpha=alpha_h, hres_beta=beta_h)
    else:
        mode_index: int
        for mode_index in range(m):
            alpha_y: np.ndarray = np.asarray((0.9 + 0j,), dtype=np.complex128)
            beta_y: np.ndarray = np.asarray((0.003 + 0j,), dtype=np.complex128)
            alpha_h: np.ndarray = np.asarray((0.97 + 0j,), dtype=np.complex128)
            beta_h: np.ndarray = np.asarray((0.0003 + 0j,), dtype=np.complex128)
            direct_y: complex = 0.12 + 0j
            direct_h: complex = 0.8 + 0j
            lag: int = 0
            fraction: float = 0.0
            if case == JMartiCouplingTestCase.MIXED_REAL_BASIS_PF3 and mode_index == 1:
                alpha_y = np.asarray((0.9 + 0.04j, 0.9 - 0.04j))
                beta_y = np.asarray((0.003 + 0.001j, 0.003 - 0.001j))
                alpha_h = np.asarray((0.97 + 0.02j, 0.97 - 0.02j))
                beta_h = np.asarray((0.0003 + 0.0001j, 0.0003 - 0.0001j))
                direct_y, direct_h, fraction = 0.1 + 0j, 0.7 + 0j, 0.5
            elif case == JMartiCouplingTestCase.MIXED_REAL_BASIS_PF3 and mode_index == 2:
                direct_y, direct_h, lag, fraction = 0.08 + 0j, 0.6 + 0j, 3, 0.5
            elif case == JMartiCouplingTestCase.COMPLEX_BASIS_REAL_TRANSFER:
                alpha_y = np.asarray((0.9 + 0.04j, 0.9 - 0.04j))
                beta_y = np.asarray((0.003 + 0.001j, 0.003 - 0.001j))
                alpha_h = np.asarray((0.97 + 0.02j, 0.97 - 0.02j))
                beta_h = np.asarray((0.0003 + 0.0001j, 0.0003 - 0.0001j))
                fraction = 0.25
            elif case in (JMartiCouplingTestCase.B_PLUS_ONE, JMartiCouplingTestCase.B_MINUS_ONE) or boundary:
                alpha_y, beta_y = np.zeros(0, dtype=np.complex128), np.zeros(0, dtype=np.complex128)
                alpha_h, beta_h = np.zeros(0, dtype=np.complex128), np.zeros(0, dtype=np.complex128)
                direct_h = -1.0 + 0j if case == JMartiCouplingTestCase.B_MINUS_ONE else 1.0 + 0j
            elif neutral:
                fraction, direct_h = 0.25, 0.6 + 0j
                if mode_index == 0:
                    alpha_y, beta_y = np.asarray((0.85 + 0j,)), np.asarray((0.002 + 0j,))
                    alpha_h, beta_h = np.asarray((0.92 + 0j,)), np.asarray((0.0005 + 0j,))
                    direct_y, direct_h, fraction = 0.09 + 0j, 0.4 + 0j, 0.5
                else:
                    pass
            else:
                pass
            # Source metadata and stored coefficients describe the same operator.
            poles_y: np.ndarray = np.log(alpha_y) / source_h
            poles_h: np.ndarray = np.log(alpha_h) / source_h
            residues_y: np.ndarray = beta_y * poles_y / np.expm1(poles_y * source_h)
            residues_h: np.ndarray = beta_h * poles_h / np.expm1(poles_h * source_h)
            modes[mode_index] = JMartiModeRuntimeData(
                mode_index=mode_index, tau_s=(lag + fraction) * source_h,
                delay_step_count=lag, residual_delay_s=fraction * source_h,
                yc_poles_s=poles_y, yc_residues=residues_y, yc_constant_term=direct_y, yc_proportional_term=0j,
                hres_poles_s=poles_h, hres_residues=residues_h, hres_constant_term=direct_h, hres_proportional_term=0j,
                yc_alpha=alpha_y, yc_beta=beta_y, hres_alpha=alpha_h, hres_beta=beta_h)
    declared_modes: tuple[JMartiModeRuntimeData, ...] = tuple(mode for mode in modes if isinstance(mode, JMartiModeRuntimeData))
    assert len(declared_modes) == m
    source_data: JMartiRuntimeData = JMartiRuntimeData(
        time_step_s=h if fitted else source_h, line_length_m=1000.0, phase_labels=labels,
        modal_transform=transform, modal_transform_inv=np.linalg.inv(transform), reference_frequency_hz=frequency,
        mode_data=declared_modes)
    # Build both frequency responses independently of the native runtime buffers.
    inverse: np.ndarray = np.linalg.inv(transform)
    advance: complex = complex(np.exp(2j * np.pi * frequency * h))
    y_sign: np.ndarray = np.zeros((2, m), dtype=np.complex128)
    propagation_sign: np.ndarray = np.zeros((2, m), dtype=np.complex128)
    mode: JMartiModeRuntimeData
    sign_index: int
    for mode_index, mode in enumerate(declared_modes):
        tau: float = mode.get_tau_s()
        lag = int(np.floor(tau / h))
        fraction = (tau - lag * h) / h
        direct_y: complex = mode.get_yc_constant_term()
        direct_h: complex = mode.get_hres_constant_term()
        if fitted or source_h != h:
            # Fit conversion and retiming use the retained trapezoidal kernel.
            denominator_y: np.ndarray = 1.0 - 0.5 * h * mode.get_yc_poles_s()
            denominator_h: np.ndarray = 1.0 - 0.5 * h * mode.get_hres_poles_s()
            alpha_y = (1.0 + 0.5 * h * mode.get_yc_poles_s()) / denominator_y
            alpha_h = (1.0 + 0.5 * h * mode.get_hres_poles_s()) / denominator_h
            beta_y = h * mode.get_yc_residues() / denominator_y ** 2
            beta_h = h * mode.get_hres_residues() / denominator_h ** 2
            direct_y += np.sum(0.5 * h * mode.get_yc_residues() / denominator_y)
            direct_h += np.sum(0.5 * h * mode.get_hres_residues() / denominator_h)
        else:
            # Unretimed legacy records retain their declared ZOH realization.
            alpha_y, beta_y = mode.get_yc_alpha(), mode.get_yc_beta()
            alpha_h, beta_h = mode.get_hres_alpha(), mode.get_hres_beta()
        for sign_index in range(2):
            z: complex = advance if sign_index == 0 else advance.conjugate()
            delay: complex = z ** (-lag) * (1.0 - fraction + fraction / z)
            y_sign[sign_index, mode_index] = direct_y + np.sum(beta_y / (z - alpha_y))
            propagation_sign[sign_index, mode_index] = delay * (direct_h + np.sum(beta_h / (z - alpha_h)))
    y_plus: np.ndarray = transform @ np.diag(y_sign[0]) @ inverse
    y_minus: np.ndarray = transform @ np.diag(y_sign[1]) @ inverse
    p_plus: np.ndarray = transform @ np.diag(propagation_sign[0]) @ inverse
    p_minus: np.ndarray = transform @ np.diag(propagation_sign[1]) @ inverse
    y_real: np.ndarray = (y_plus + y_minus.conjugate()) / 2.0
    p_real: np.ndarray = (p_plus + p_minus.conjugate()) / 2.0
    p_imag: np.ndarray = (p_plus - p_minus.conjugate()) / (2j)
    yp_real: np.ndarray = (y_plus @ p_plus + (y_minus @ p_minus).conjugate()) / 2.0
    yp_imag: np.ndarray = (y_plus @ p_plus - (y_minus @ p_minus).conjugate()) / (2j)
    eye: np.ndarray = np.eye(m)
    matrix: np.ndarray = np.zeros((6 * m, 6 * m), dtype=np.complex128)
    conductance_f: float = 0.0 if boundary else 0.3
    conductance_t: float = 0.0 if boundary else 0.45
    matrix[:m, :m], matrix[m:2 * m, m:2 * m] = conductance_f * eye + y_real, conductance_t * eye + y_real
    matrix[:m, 4 * m:5 * m], matrix[:m, 5 * m:] = -2 * yp_real, 2 * yp_imag
    matrix[m:2 * m, 2 * m:3 * m], matrix[m:2 * m, 3 * m:4 * m] = -2 * yp_real, 2 * yp_imag
    matrix[2 * m:3 * m, :m], matrix[2 * m:3 * m, 2 * m:3 * m] = -eye, eye
    matrix[2 * m:3 * m, 4 * m:5 * m], matrix[2 * m:3 * m, 5 * m:] = p_real, -p_imag
    matrix[3 * m:4 * m, 3 * m:4 * m], matrix[3 * m:4 * m, 4 * m:5 * m] = eye, p_imag
    matrix[3 * m:4 * m, 5 * m:] = p_real
    matrix[4 * m:5 * m, m:2 * m], matrix[4 * m:5 * m, 4 * m:5 * m] = -eye, eye
    matrix[4 * m:5 * m, 2 * m:3 * m], matrix[4 * m:5 * m, 3 * m:4 * m] = p_real, -p_imag
    matrix[5 * m:, 2 * m:3 * m], matrix[5 * m:, 3 * m:4 * m], matrix[5 * m:, 5 * m:] = p_imag, p_real, eye
    source_angles: np.ndarray = np.deg2rad(np.asarray(((14.0, -106.0, 134.0), (-23.0, -143.0, 97.0))))
    sources: np.ndarray = np.zeros((2, m), dtype=np.complex128)
    sources[:, m - 3:] = np.asarray((1.1, 0.82))[:, None] / np.sqrt(2.0) * np.exp(1j * source_angles)
    if frequency == 0.0:
        sources = 1j * sources.imag
    else:
        pass
    phasors: np.ndarray = np.zeros(6 * m, dtype=np.complex128)
    if boundary:
        pass
    else:
        forcing: np.ndarray = np.zeros(6 * m, dtype=np.complex128)
        forcing[:m], forcing[m:2 * m] = conductance_f * sources[0], conductance_t * sources[1]
        if fitted:
            phasors[:] = np.linalg.solve(matrix, forcing)
        else:
            # Only the declared exact real invariant removes imaginary PHASE
            # wave coordinates. Complex MODAL rows remain in the memory oracle.
            physical_indices: np.ndarray = np.concatenate((np.arange(3 * m), np.arange(4 * m, 5 * m)))
            phasors[physical_indices] = np.linalg.solve(matrix[np.ix_(physical_indices, physical_indices)], forcing[physical_indices])
        assert np.max(np.abs(matrix @ phasors - forcing)) <= 1e-12
    reference: np.ndarray = np.zeros((402, 8 * m), dtype=np.float64)
    current_phasors: np.ndarray = np.zeros((2, m), dtype=np.complex128)
    current_phasors[0] = conductance_f * (sources[0] - phasors[:m])
    current_phasors[1] = conductance_t * (sources[1] - phasors[m:2 * m])
    step: int
    for step in range(402):
        reference[step, :6 * m] = np.sqrt(2.0) * np.imag(phasors * advance ** step)
        reference[step, 6 * m:] = np.sqrt(2.0) * np.imag(current_phasors.reshape(2 * m) * advance ** step)
    # Register actual source templates and ordinary line/bus assets once.
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=100.0, fbase=frequency)
    bus_f: gce.Bus = gce.Bus(name="Coupled from", Vnom=110.0, is_slack=True)
    bus_t: gce.Bus = gce.Bus(name="Coupled to", Vnom=110.0)
    grid.add_bus(bus_f)
    grid.add_bus(bus_t)
    line: gce.Line = gce.Line(name="Declared JMARTI", bus_from=bus_f, bus_to=bus_t, length=1.0)
    geometry: gce.OverheadLineType = gce.create_known_abc_overhead_template(
        name="Coupling phase layout", z_nabc=np.eye(m, dtype=np.complex128) * (0.01 + 0.03j),
        ysh_nabc=np.zeros((m, m), dtype=np.complex128), phases=np.arange(0 if neutral else 1, 4), Vnom=110.0,
        frequency=50.0)
    grid.add_overhead_line(geometry)
    line.apply_template(geometry, grid.Sbase, 50.0, gce.Logger())
    grid.add_line(obj=line)
    get_bus_emt_template(grid, bus_f)
    get_bus_emt_template(grid, bus_t)
    line_model: Block = get_jmarti_line_emt_template(
        vf=grid.var_factory, phN=neutral, phA=True, phB=True, phC=True, name="Coupled JMARTI").block
    if fit_bundle is None:
        set_jmarti_block_runtime_data(line_model, source_data)
    else:
        set_jmarti_block_fit_bundle(line_model, fit_bundle)
    set_emt_model(device=line, model=line_model, var_factory=grid.var_factory)
    end: int
    bus: gce.Bus
    for end, bus in enumerate((bus_f, bus_t)):
        generator: gce.Generator = gce.Generator(name=f"Norton source {end}", Snom=100.0)
        generator.P = float(np.real(np.sum(phasors[end * m:(end + 1) * m] * current_phasors[end].conjugate())) * grid.Sbase / 3.0)
        grid.add_generator(bus=bus, api_obj=generator)
        if boundary:
            offset: float = 0.1 if case == JMartiCouplingTestCase.INCOMPATIBLE_CURRENT_SUM else 0.0
            source_model: Block = get_current_source_emt_template(
                vf=grid.var_factory, amplitude_values=dict(A=0.0, B=0.0, C=0.0),
                frequency_hz=0.0, phase_angle_deg=dict(A=0.0, B=0.0, C=0.0),
                offset_values=dict(A=offset, B=offset, C=offset), name=f"Floating current source {end}").block
        elif neutral:
            source_model = get_voltage_source_emt_template(
                vf=grid.var_factory, phN=True, amplitude_values=dict(N=0.0, A=1.1 if end == 0 else 0.82,
                    B=1.1 if end == 0 else 0.82, C=1.1 if end == 0 else 0.82), frequency_hz=0.0,
                phase_angle_deg=dict(N=0.0, A=14.0 if end == 0 else -23.0,
                    B=-106.0 if end == 0 else -143.0, C=134.0 if end == 0 else 97.0),
                offset_values=dict(N=0.0, A=0.0, B=0.0, C=0.0),
                source_conductance_value=conductance_f if end == 0 else conductance_t,
                name=f"Zero-neutral Norton {end}").block
        else:
            source_model = get_balanced_3ph_voltage_source_emt_template(
                vf=grid.var_factory, amplitude_value=1.1 if end == 0 else 0.82, frequency_hz=frequency,
                phase_a_deg=14.0 if end == 0 else -23.0,
                source_conductance_value=conductance_f if end == 0 else conductance_t, name=f"Norton {end}").block
        set_emt_model(device=generator, model=source_model, var_factory=grid.var_factory)
    # Providers transport the independent physical voltages and powers unchanged.
    pf: PowerFlowResults | None = None
    pf3: PowerFlowResults3Ph | None = None
    arrays: tuple[np.ndarray, ...] = tuple()
    empty_names: np.ndarray = np.zeros(0, dtype=str)
    if boundary:
        pass
    elif case == JMartiCouplingTestCase.DIRECT_REAL_BALANCED:
        pf = PowerFlowResults(n=2, m=1, n_hvdc=0, n_vsc=0, n_gen=2, n_batt=0, n_sh=0,
            bus_names=np.asarray((bus_f.name, bus_t.name)), branch_names=np.asarray((line.name,)),
            hvdc_names=empty_names, vsc_names=empty_names, gen_names=np.asarray(("From", "To")),
            batt_names=empty_names, sh_names=empty_names, bus_types=np.asarray((3, 1)))
        pf.voltage[:] = phasors[:2 * m].reshape(2, m)[:, 0]
        pf.If[0], pf.It[0] = current_phasors[:, 0]
        pf.Sf[0], pf.St[0] = grid.Sbase * pf.voltage * current_phasors[:, 0].conjugate()
        pf.Sbus[:] = np.asarray((pf.Sf[0], pf.St[0]))
        pf.gen_p[:], pf.gen_q[:] = pf.Sbus.real, pf.Sbus.imag
        pf.F, pf.T = np.zeros(1, dtype=int), np.ones(1, dtype=int)
        arrays = (pf.voltage, pf.Sf, pf.St, pf.If, pf.It, pf.Sbus, pf.gen_p, pf.gen_q, pf.F, pf.T)
    else:
        # The established PF3 result constructor receives expanded ABC counts
        # and divides them by three to allocate each physical-phase array.
        pf3 = PowerFlowResults3Ph(n=6, m=3, n_hvdc=0, n_vsc=0, n_gen=2, n_batt=0, n_sh=0, n_load=0,
            bus_names=np.asarray((bus_f.name, bus_t.name)), branch_names=np.asarray((line.name,)),
            hvdc_names=empty_names, vsc_names=empty_names, gen_names=np.asarray(("From", "To")),
            batt_names=empty_names, sh_names=empty_names, load_names=empty_names, bus_types=np.asarray((3, 1)))
        phase: int
        phase_arrays: tuple[tuple[np.ndarray, ...], ...] = (
            (pf3.voltage_A, pf3.Sf_A, pf3.St_A, pf3.If_A, pf3.It_A, pf3.Sbus_A, pf3.gen_q_A),
            (pf3.voltage_B, pf3.Sf_B, pf3.St_B, pf3.If_B, pf3.It_B, pf3.Sbus_B, pf3.gen_q_B),
            (pf3.voltage_C, pf3.Sf_C, pf3.St_C, pf3.If_C, pf3.It_C, pf3.Sbus_C, pf3.gen_q_C))
        phase_array: tuple[np.ndarray, ...]
        for phase, phase_array in enumerate(phase_arrays):
            channel: int = phase + (1 if neutral else 0)
            phase_array[0][:] = np.asarray((phasors[channel], phasors[m + channel]))
            phase_array[3][0], phase_array[4][0] = current_phasors[:, channel]
            phase_array[1][0], phase_array[2][0] = grid.Sbase / 3.0 * phase_array[0] * current_phasors[:, channel].conjugate()
            phase_array[5][:] = np.asarray((phase_array[1][0], phase_array[2][0]))
            phase_array[6][:] = phase_array[5].imag
        pf3.F, pf3.T = np.zeros(1, dtype=int), np.ones(1, dtype=int)
        arrays = tuple(array for phase_array in phase_arrays for array in phase_array) + (pf3.voltage_N, pf3.If_N, pf3.It_N, pf3.F, pf3.T)
    copies: tuple[np.ndarray, ...] = tuple(array.copy() for array in arrays)
    source_block: Block = line.emt_model
    # Use the persisted block owner, which encodes Enum mappings and retains
    # symbolic identities in its canonical tables before runtime preparation.
    source_saver: BlockSaver = BlockSaver(var_factory=grid.var_factory)
    source_saver.save_block(source_block, main=True)
    saved_source: str = json.dumps((source_saver.get_blocks(), source_saver.get_const_to_save(),
        source_saver.get_vars_to_save(), source_saver.get_diff_vars_to_save(),
        source_saver.get_shared_references_to_save(), source_saver.get_connections_to_save()), sort_keys=True)
    factory_uids: tuple[int, ...] = tuple(grid.var_factory.get_vars_dict())
    # Keep the existing integration default: backend source-angle residuals
    # contain derivative/h units, while the independent orbit and physical g
    # checks below retain their separate strict bounds for these fixtures.
    options: EmtOptions = EmtOptions(time_step=h, simulation_time=401 * h,
        init_newton_tol=1e-13, init_newton_max_iter=20, solver_type=solver_type,
        initialization_method=EmtInitializationMethod.Explicit, integration_method=DynamicIntegrationMethod.DaeTrapezoidal)
    problem: EmtProblemDae = EmtProblemDae(grid=grid, options=options, pf_results=pf, pf_results_3ph=pf3)
    assert line.emt_model is source_block
    prepared_source_saver: BlockSaver = BlockSaver(var_factory=grid.var_factory)
    prepared_source_saver.save_block(source_block, main=True)
    assert json.dumps((prepared_source_saver.get_blocks(), prepared_source_saver.get_const_to_save(),
        prepared_source_saver.get_vars_to_save(), prepared_source_saver.get_diff_vars_to_save(),
        prepared_source_saver.get_shared_references_to_save(), prepared_source_saver.get_connections_to_save()), sort_keys=True) == saved_source
    assert tuple(grid.var_factory.get_vars_dict()) == factory_uids
    array: np.ndarray
    before: np.ndarray
    for array, before in zip(arrays, copies):
        np.testing.assert_array_equal(array, before)
    return problem, reference, phasors


@pytest.mark.parametrize("solver_type", (
    EmtSolverTypes.Symbolic, EmtSolverTypes.Automatic,
    EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled))
@pytest.mark.parametrize("case", tuple(JMartiCouplingTestCase))
def test_jmarti_coupled_network_matches_discrete_orbit(
        case: JMartiCouplingTestCase, solver_type: EmtSolverTypes) -> None:
    """Verify every native target, physical boundary and complex history row.

    :param case: Eight declared periodic/constant operators or two boundaries.
    :param solver_type: Actual EMT backend consuming the common assembled graph.
    :return: None; record actual rank/residual and preserve all physical rows.
    """
    problem: EmtProblemDae
    reference: np.ndarray
    phasors: np.ndarray
    problem, reference, phasors = _build_jmarti_coupled_network_case(case, solver_type)
    assert len(problem.history_models) == 1
    assert isinstance(problem.history_models[0], JMartiHistoryRuntime)
    runtime: JMartiHistoryRuntime = problem.history_models[0]
    m: int = runtime.m
    block: Block
    assert runtime.coupling_block is not None
    # The native system flattens declarations, while the device registration
    # retains the companion owner for initialization and branch association.
    assert sum(block is runtime.coupling_block for block in problem._device_models_for_ptc) == 1
    assert runtime.coupling_var_factory is not problem.grid.var_factory
    assert runtime.phase_real_kernel == (case not in (
        JMartiCouplingTestCase.PRODUCTIVE_FIT_SHORT_DIRECT, JMartiCouplingTestCase.COMPLEX_BASIS_UNPAIRED_FIT))
    assert len(runtime.coupling_block.algebraic_vars) == (2 * m if runtime.phase_real_kernel else 4 * m)
    families: tuple[tuple[list[Var], list[int]], ...] = (
        (runtime.outgoing_wave_f_re, runtime.idx_wave_f_re), (runtime.outgoing_wave_t_re, runtime.idx_wave_t_re),
        (runtime.outgoing_wave_f_im, runtime.idx_wave_f_im), (runtime.outgoing_wave_t_im, runtime.idx_wave_t_im))
    variables: list[Var]
    indices: list[int]
    variable: Var
    registered_variable: Var
    index: int
    for variables, indices in families:
        assert len(variables) == len(indices)
        for variable, index in zip(variables, indices):
            assert index >= 0 and problem.uid2idx_vars[variable.uid] == index
            assert sum(registered_variable.uid == variable.uid
                       for registered_variable in problem.get_algebraic_vars()) == 1
            assert problem._vars2device[variable.uid] is problem.grid.lines[0]
            assert variable.uid in problem.init_guess
    retained_uids: set[int] = set(variable.uid for variable in problem.get_runtime_mode_parameters())
    parameter_families: tuple[list[Var], ...] = (
        runtime.Ih_f, runtime.Ih_t, runtime.incoming_voltage_f_re, runtime.incoming_voltage_t_re,
        runtime.incoming_voltage_f_im, runtime.incoming_voltage_t_im)
    values: np.ndarray = problem.get_x0()
    derivatives: np.ndarray = problem.get_dx0()
    params: np.ndarray = problem.event_params_values.copy()
    constants: np.ndarray = np.asarray(tuple(float(item.value) for item in problem.get_parameters_values()))
    item: Const
    position: int
    source: Var
    for variables in parameter_families:
        for variable in variables:
            index = problem.uid2idx_event_params[variable.uid]
            assert variable.uid in retained_uids
            assert problem._runtime_parameter_devices[variable.uid] is problem.grid.lines[0]
            assert sum(source.uid == variable.uid for source in problem._runtime_all_parameters_source) == 1
            assert params[index] == problem.init_guess[variable.uid]
            assert params[index] == problem._temp_init_guess[variable.uid]
            assert params[index] == problem._temp_post_init_guess[variable.uid]
            source_index: int = next(position for position, source in enumerate(problem._runtime_all_parameters_source)
                                     if source.uid == variable.uid)
            source_eq: Const = problem._runtime_all_eqs_source[source_index]
            assert isinstance(source_eq, Const) and float(source_eq.value) == params[index]
    # Differentiate the actual complete native g, with fixed differential states.
    residual_fn: SymbolicVector = SymbolicVector(
        eqs=problem.get_algebraic_eqs(), compiler_names_dict=problem.get_compiler_names_dict(),
        alias_names_dict=problem.get_alias_names_dict(), VARS_NAME=problem.VARS_NAME,
        DIFF_NAME=problem.DIFF_NAME, EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME, PARAMS_NAME=problem.CONSTANT_PARAMS_NAME)
    jacobian_fn: SymbolicJacobian = SymbolicJacobian(
        eqs=problem.get_algebraic_eqs(), variables=problem.get_algebraic_vars(),
        compiler_names_dict=problem.get_compiler_names_dict(), alias_names_dict=problem.get_alias_names_dict(),
        VARS_NAME=problem.VARS_NAME, DIFF_NAME=problem.DIFF_NAME,
        EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME, PARAMS_NAME=problem.CONSTANT_PARAMS_NAME)
    initial_g: np.ndarray = residual_fn(values, derivatives, params, constants).copy()
    jacobian: np.ndarray = jacobian_fn(values, derivatives, params, constants, 1.0).toarray()
    rank: int = int(np.linalg.matrix_rank(jacobian))
    finite_difference: np.ndarray = np.zeros_like(jacobian)
    column: int
    for column, variable in enumerate(problem.get_algebraic_vars()):
        # These fixtures are linear in algebraic variables with theta held
        # fixed. A central binary step avoids amplifying residual roundoff
        # without introducing truncation error or changing the Jacobian bound.
        variable_index: int = problem.uid2idx_vars[variable.uid]
        delta: float = max(1.0, abs(float(values[variable_index]))) / 4096.0
        positive_values: np.ndarray = values.copy()
        negative_values: np.ndarray = values.copy()
        positive_values[variable_index] += delta
        negative_values[variable_index] -= delta
        positive_g: np.ndarray = residual_fn(positive_values, derivatives, params, constants).copy()
        negative_g: np.ndarray = residual_fn(negative_values, derivatives, params, constants).copy()
        finite_difference[:, column] = (positive_g - negative_g) / (2.0 * delta)
    np.testing.assert_allclose(jacobian, finite_difference, rtol=0.0,
                               atol=1e-10 * max(1.0, float(np.max(np.abs(jacobian)))))
    boundary: bool = case in (JMartiCouplingTestCase.RANKDEF_ZERO_CURRENT, JMartiCouplingTestCase.INCOMPATIBLE_CURRENT_SUM)
    solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver = build_emt_solver(
        options=problem.options, problem=problem, t0=0.0, t_end=problem.options.simulation_time,
        h=problem.options.time_step, method=problem.options.integration_method)
    times: np.ndarray
    trajectory: np.ndarray
    differential_history: np.ndarray
    converged: bool
    initialized: bool
    if boundary:
        # The actual source-current variables add rows to the reviewed physical
        # quotient. Its three floating voltage directions remain observable.
        assert jacobian.shape[1] - rank == m
        left_vectors: np.ndarray
        singular_values: np.ndarray
        right_vectors: np.ndarray
        left_vectors, singular_values, right_vectors = np.linalg.svd(jacobian)
        incompatible_norm: float = float(np.linalg.norm(left_vectors[:, rank:].T @ initial_g))
        if case == JMartiCouplingTestCase.RANKDEF_ZERO_CURRENT:
            assert np.max(np.abs(initial_g)) <= 1e-12
            assert incompatible_norm <= 1e-12
        else:
            expected_left_null_norm: float = 0.2 * np.sqrt(m / (4.0 + 2.0 * 0.12 * 0.12))
            assert incompatible_norm == pytest.approx(expected_left_null_norm, rel=0.0, abs=1e-12)
        failure: str = ""
        converged = False
        word: str
        error: np.linalg.LinAlgError | RuntimeError | ZeroDivisionError
        try:
            times, trajectory, differential_history, initialized, converged = solver.simulate(boundary_updater=problem)
        except (np.linalg.LinAlgError, RuntimeError, ZeroDivisionError) as error:
            failure = str(error)
            assert any(word in failure.lower() for word in ("singular", "factor", "pivot", "division", "converg"))
        else:
            if case == JMartiCouplingTestCase.INCOMPATIBLE_CURRENT_SUM:
                assert not converged
            else:
                if converged:
                    assert np.isfinite(trajectory).all()
                    row: int
                    for row in range(times.size):
                        assert np.max(np.abs(residual_fn(trajectory[row], differential_history[row],
                                                        problem.event_params_values, constants))) <= 1e-12
                else:
                    pass
        print(case, solver_type, "native algebraic rank", rank, "of", jacobian.shape[1],
              "left-null residual", incompatible_norm, "converged", converged, "failure", failure)
    else:
        assert rank == jacobian.shape[1]
        assert np.max(np.abs(initial_g)) <= 1e-12
        times, trajectory, differential_history, initialized, converged = solver.simulate(boundary_updater=problem)
        assert initialized and converged and times.size == 402
        np.testing.assert_allclose(times, np.arange(402) * problem.options.time_step, rtol=0.0, atol=1e-12)
        actual: np.ndarray = np.zeros_like(reference)
        actual[:, :m], actual[:, m:2 * m] = trajectory[:, runtime.idx_vf], trajectory[:, runtime.idx_vt]
        actual[:, 2 * m:3 * m], actual[:, 4 * m:5 * m] = trajectory[:, runtime.idx_wave_f_re], trajectory[:, runtime.idx_wave_t_re]
        if runtime.phase_real_kernel:
            pass
        else:
            actual[:, 3 * m:4 * m], actual[:, 5 * m:6 * m] = trajectory[:, runtime.idx_wave_f_im], trajectory[:, runtime.idx_wave_t_im]
        generators: list[gce.Generator] = problem.grid.get_generators()
        end: int
        current_refs: tuple[VarPowerFlowReferenceType, ...] = (
            VarPowerFlowReferenceType.i_N, VarPowerFlowReferenceType.i_A,
            VarPowerFlowReferenceType.i_B, VarPowerFlowReferenceType.i_C)
        phase: int
        for end in range(2):
            for phase in range(m):
                current_var: Var | None = generators[end].emt_model.external_mapping.get(current_refs[phase + 4 - m], None)
                assert isinstance(current_var, Var)
                actual[:, (6 + end) * m + phase] = trajectory[:, problem.uid2idx_vars[current_var.uid]]
        numerical_bound: float = 1e-10 * max(1.0, float(np.max(np.abs(reference))))
        np.testing.assert_allclose(actual, reference, rtol=0.0, atol=numerical_bound)
        assert np.max(np.abs(residual_fn(trajectory[-1], differential_history[-1], problem.event_params_values, constants))) <= 1e-12
        # Check complete complex filter rows and ring ownership independently.
        inverse: np.ndarray = runtime.runtime_data.get_modal_transform_inv()
        advance: complex = complex(np.exp(2j * np.pi * problem.grid.fBase * problem.options.time_step))
        amplitude_positive: np.ndarray = np.zeros((4, m), dtype=np.complex128)
        amplitude_negative: np.ndarray = np.zeros((4, m), dtype=np.complex128)
        for end in range(2):
            wave_re: np.ndarray = phasors[(2 + 2 * end) * m:(3 + 2 * end) * m]
            wave_im: np.ndarray = phasors[(3 + 2 * end) * m:(4 + 2 * end) * m]
            amplitude_positive[end] = inverse @ (-1j / np.sqrt(2.0) * (wave_re + 1j * wave_im))
            amplitude_negative[end] = inverse @ (1j / np.sqrt(2.0) * (wave_re.conjugate() + 1j * wave_im.conjugate()))
            amplitude_positive[end + 2] = inverse @ (-1j / np.sqrt(2.0) * phasors[end * m:(end + 1) * m])
            amplitude_negative[end + 2] = inverse @ (1j / np.sqrt(2.0) * phasors[end * m:(end + 1) * m].conjugate())
        mode_index: int
        mode: JMartiModeRuntimeData
        for mode_index, mode in enumerate(runtime.runtime_data.get_mode_data()):
            fraction: float = mode.get_residual_delay_s() / problem.options.time_step
            h_plus: complex = mode.get_hres_constant_term() + np.sum(mode.get_hres_beta() / (advance - mode.get_hres_alpha()))
            h_minus: complex = mode.get_hres_constant_term() + np.sum(mode.get_hres_beta() / (advance.conjugate() - mode.get_hres_alpha()))
            delay_plus: complex = advance ** (-mode.get_delay_step_count()) * (1.0 - fraction + fraction / advance)
            delay_minus: complex = delay_plus.conjugate()
            for end in range(2):
                remote: int = 1 - end
                expected_h: np.ndarray = mode.get_hres_beta() / (advance - mode.get_hres_alpha()) * delay_plus * amplitude_positive[remote, mode_index] * advance ** 401
                expected_h += mode.get_hres_beta() / (advance.conjugate() - mode.get_hres_alpha()) * delay_minus * amplitude_negative[remote, mode_index] * advance.conjugate() ** 401
                expected_y: np.ndarray = mode.get_yc_beta() / (advance - mode.get_yc_alpha()) * (
                    amplitude_positive[end + 2, mode_index] - 2.0 * h_plus * delay_plus * amplitude_positive[remote, mode_index]) * advance ** 401
                expected_y += mode.get_yc_beta() / (advance.conjugate() - mode.get_yc_alpha()) * (
                    amplitude_negative[end + 2, mode_index] - 2.0 * h_minus * delay_minus * amplitude_negative[remote, mode_index]) * advance.conjugate() ** 401
                h_state: np.ndarray = runtime.hres_state_from if end == 0 else runtime.hres_state_to
                y_state: np.ndarray = runtime.yc_state_from if end == 0 else runtime.yc_state_to
                np.testing.assert_allclose(h_state[mode_index, :expected_h.size], expected_h, rtol=0.0, atol=numerical_bound)
                np.testing.assert_allclose(y_state[mode_index, :expected_y.size], expected_y, rtol=0.0, atol=numerical_bound)
        buffer_index: int
        for buffer_index in range(runtime.buffer_size):
            accepted_step: int = 400 - ((400 - buffer_index) % runtime.buffer_size)
            expected_f: np.ndarray = amplitude_positive[0] * advance ** accepted_step + amplitude_negative[0] * advance.conjugate() ** accepted_step
            expected_t: np.ndarray = amplitude_positive[1] * advance ** accepted_step + amplitude_negative[1] * advance.conjugate() ** accepted_step
            np.testing.assert_allclose(runtime.buf_a_f[buffer_index], expected_f, rtol=0.0, atol=numerical_bound)
            np.testing.assert_allclose(runtime.buf_a_t[buffer_index], expected_t, rtol=0.0, atol=numerical_bound)
        if case == JMartiCouplingTestCase.CONSTANT_NABC_ZERO_NEUTRAL:
            assert np.max(np.abs(actual[:, np.asarray((0, m, 2 * m, 4 * m, 6 * m, 7 * m))])) <= 1e-12
            coarse_problem: EmtProblemDae
            coarse_reference: np.ndarray
            coarse_phasors: np.ndarray
            coarse_problem, coarse_reference, coarse_phasors = _build_jmarti_coupled_network_case(case, solver_type, 1e-3)
            coarse_solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver = build_emt_solver(
                options=coarse_problem.options, problem=coarse_problem, t0=0.0, t_end=coarse_problem.options.simulation_time,
                h=coarse_problem.options.time_step, method=coarse_problem.options.integration_method)
            coarse_times: np.ndarray
            coarse_values: np.ndarray
            coarse_derivatives: np.ndarray
            coarse_converged: bool
            coarse_initialized: bool
            coarse_times, coarse_values, coarse_derivatives, coarse_initialized, coarse_converged = coarse_solver.simulate(boundary_updater=coarse_problem)
            assert coarse_initialized and coarse_converged and coarse_times.size == 402
            coarse_runtime: JMartiHistoryRuntime = coarse_problem.history_models[0]
            coarse_actual: np.ndarray = np.zeros_like(coarse_reference)
            coarse_actual[:, :m], coarse_actual[:, m:2 * m] = coarse_values[:, coarse_runtime.idx_vf], coarse_values[:, coarse_runtime.idx_vt]
            coarse_actual[:, 2 * m:3 * m], coarse_actual[:, 4 * m:5 * m] = coarse_values[:, coarse_runtime.idx_wave_f_re], coarse_values[:, coarse_runtime.idx_wave_t_re]
            coarse_generators: list[gce.Generator] = coarse_problem.grid.get_generators()
            for end in range(2):
                for phase in range(m):
                    current_var = coarse_generators[end].emt_model.external_mapping.get(current_refs[phase], None)
                    assert isinstance(current_var, Var)
                    coarse_actual[:, (6 + end) * m + phase] = coarse_values[:, coarse_problem.uid2idx_vars[current_var.uid]]
            np.testing.assert_allclose(coarse_actual, coarse_reference, rtol=0.0, atol=numerical_bound)
            np.testing.assert_allclose(coarse_phasors, phasors, rtol=0.0, atol=numerical_bound)
        else:
            pass


@pytest.mark.parametrize("solver_type", (
    EmtSolverTypes.Symbolic, EmtSolverTypes.Automatic,
    EmtSolverTypes.StructuralAD, EmtSolverTypes.StructuralCompiled))
@pytest.mark.parametrize("case", (
    JMartiCouplingTestCase.DIRECT_REAL_BALANCED, JMartiCouplingTestCase.PRODUCTIVE_FIT_SHORT_DIRECT))
def test_jmarti_coupled_network_preserves_source_and_restart(
        case: JMartiCouplingTestCase, solver_type: EmtSolverTypes) -> None:
    """Restart an advanced native problem and rebind without source accumulation.

    :param case: Balanced PF or general complex PF3 source and private companion.
    :param solver_type: Actual backend used for both advanced and fresh runs.
    :return: None; verify source identity, declarations, coefficients and replay.
    """
    problem: EmtProblemDae
    reference: np.ndarray
    phasors: np.ndarray
    problem, reference, phasors = _build_jmarti_coupled_network_case(case, solver_type)
    assert isinstance(problem.history_models[0], JMartiHistoryRuntime)
    runtime: JMartiHistoryRuntime = problem.history_models[0]
    source: Block = problem.grid.lines[0].emt_model
    assert runtime.coupling_block is not None
    source_data: JMartiRuntimeData | None = get_jmarti_block_runtime_data(source)
    source_fit: JMartiFitBundle | None = get_jmarti_block_fit_bundle(source)
    # Persistence uses the same existing declarative codec as the constructor
    # guard; no source generator or lossy conversion is part of this snapshot.
    source_saver: BlockSaver = BlockSaver(var_factory=problem.grid.var_factory)
    source_saver.save_block(source, main=True)
    serialization: str = json.dumps((source_saver.get_blocks(), source_saver.get_const_to_save(),
        source_saver.get_vars_to_save(), source_saver.get_diff_vars_to_save(),
        source_saver.get_shared_references_to_save(), source_saver.get_connections_to_save()), sort_keys=True)
    factory_uids: tuple[int, ...] = tuple(problem.grid.var_factory.get_vars_dict())
    source_vars: tuple[Var, ...] = tuple(source.get_all_vars())
    generator: gce.Generator
    source_powers: tuple[float, ...] = tuple(generator.P for generator in problem.grid.get_generators())
    provider_arrays: tuple[np.ndarray, ...]
    if problem.power_flow_results is not None:
        pf: PowerFlowResults = problem.power_flow_results
        provider_arrays = (pf.voltage, pf.Sf, pf.St, pf.If, pf.It, pf.Sbus, pf.gen_p, pf.gen_q)
        assert runtime.runtime_data is source_data
    else:
        pf3: PowerFlowResults3Ph = problem.power_flow_results_3ph
        assert isinstance(pf3, PowerFlowResults3Ph)
        provider_arrays = (pf3.voltage_N, pf3.voltage_A, pf3.voltage_B, pf3.voltage_C,
            pf3.Sf_A, pf3.Sf_B, pf3.Sf_C, pf3.St_A, pf3.St_B, pf3.St_C,
            pf3.If_N, pf3.If_A, pf3.If_B, pf3.If_C, pf3.It_N, pf3.It_A, pf3.It_B, pf3.It_C,
            pf3.Sbus_A, pf3.Sbus_B, pf3.Sbus_C, pf3.gen_q_A, pf3.gen_q_B, pf3.gen_q_C)
        assert source_data is None and source_fit is not None
    provider_copies: tuple[np.ndarray, ...] = tuple(array.copy() for array in provider_arrays)
    initial_ring_f: np.ndarray = runtime.buf_a_f.copy()
    initial_ring_t: np.ndarray = runtime.buf_a_t.copy()
    initial_y_f: np.ndarray = runtime.yc_state_from.copy()
    initial_y_t: np.ndarray = runtime.yc_state_to.copy()
    initial_h_f: np.ndarray = runtime.hres_state_from.copy()
    initial_h_t: np.ndarray = runtime.hres_state_to.copy()
    initial_waves: np.ndarray = runtime.initial_phase_waves.copy()
    initial_offsets: np.ndarray = runtime.initial_voltage_offsets.copy()
    initial_sources: np.ndarray = runtime.initial_source_phasors.copy()
    initial_params: np.ndarray = problem.event_params_values.copy()
    assert runtime.initial_source_available
    solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver = build_emt_solver(
        options=problem.options, problem=problem, t0=0.0, t_end=problem.options.simulation_time,
        h=problem.options.time_step, method=problem.options.integration_method)
    times: np.ndarray
    values: np.ndarray
    derivatives: np.ndarray
    converged: bool
    initialized: bool
    times, values, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
    assert initialized and converged and times.size == 402
    first_times: np.ndarray = times.copy()
    first_values: np.ndarray = values.copy()
    first_derivatives: np.ndarray = derivatives.copy()
    advanced_y_f: np.ndarray = runtime.yc_state_from.copy()
    advanced_y_t: np.ndarray = runtime.yc_state_to.copy()
    advanced_h_f: np.ndarray = runtime.hres_state_from.copy()
    advanced_h_t: np.ndarray = runtime.hres_state_to.copy()
    # At 50 Hz the ring's final previous sample n400 aliases two periods.
    # The complex filter states consume target401 and must prove real advance.
    assert max(float(np.max(np.abs(advanced_y_f - initial_y_f))),
               float(np.max(np.abs(advanced_y_t - initial_y_t))),
               float(np.max(np.abs(advanced_h_f - initial_h_f))),
               float(np.max(np.abs(advanced_h_t - initial_h_t)))) > 1e-6
    # Reset only through the established problem owner and inspect every seed.
    problem.reset_boundary_update_state(t0=0.0)
    np.testing.assert_allclose(runtime.buf_a_f, initial_ring_f, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.buf_a_t, initial_ring_t, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.yc_state_from, initial_y_f, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.yc_state_to, initial_y_t, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.hres_state_from, initial_h_f, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(runtime.hres_state_to, initial_h_t, rtol=0.0, atol=1e-12)
    np.testing.assert_array_equal(runtime.initial_phase_waves, initial_waves)
    np.testing.assert_array_equal(runtime.initial_voltage_offsets, initial_offsets)
    np.testing.assert_array_equal(runtime.initial_source_phasors, initial_sources)
    np.testing.assert_allclose(problem.event_params_values, initial_params, rtol=0.0, atol=1e-12)
    variables: list[Var]
    variable: Var
    for variables in (runtime.Ih_f, runtime.Ih_t, runtime.incoming_voltage_f_re, runtime.incoming_voltage_t_re,
                      runtime.incoming_voltage_f_im, runtime.incoming_voltage_t_im):
        for variable in variables:
            index: int = problem.uid2idx_event_params[variable.uid]
            assert problem.event_params_values[index] == pytest.approx(problem.init_guess[variable.uid], rel=0.0, abs=1e-12)
            assert problem.event_params_values[index] == pytest.approx(problem._temp_post_init_guess[variable.uid], rel=0.0, abs=1e-12)
    times, values, derivatives, initialized, converged = solver.simulate(boundary_updater=problem)
    assert initialized and converged
    bound: float = 1e-10 * max(1.0, float(np.max(np.abs(first_values))))
    np.testing.assert_allclose(times, first_times, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(values, first_values, rtol=0.0, atol=bound)
    np.testing.assert_allclose(derivatives, first_derivatives, rtol=0.0, atol=bound)
    np.testing.assert_allclose(runtime.yc_state_from, advanced_y_f, rtol=0.0, atol=bound)
    np.testing.assert_allclose(runtime.yc_state_to, advanced_y_t, rtol=0.0, atol=bound)
    np.testing.assert_allclose(runtime.hres_state_from, advanced_h_f, rtol=0.0, atol=bound)
    np.testing.assert_allclose(runtime.hres_state_to, advanced_h_t, rtol=0.0, atol=bound)
    # Rebinding the identical saved graph must allocate a different companion.
    fresh: EmtProblemDae = EmtProblemDae(grid=problem.grid, options=problem.options,
        pf_results=problem.power_flow_results, pf_results_3ph=problem.power_flow_results_3ph)
    assert isinstance(fresh.history_models[0], JMartiHistoryRuntime)
    fresh_runtime: JMartiHistoryRuntime = fresh.history_models[0]
    assert fresh_runtime.coupling_block is not None
    assert fresh_runtime is not runtime
    assert fresh_runtime.coupling_block is not runtime.coupling_block
    assert fresh_runtime.coupling_var_factory is not runtime.coupling_var_factory
    assert set(variable.uid for variable in fresh_runtime.coupling_block.algebraic_vars).isdisjoint(
        variable.uid for variable in runtime.coupling_block.algebraic_vars)
    fresh_solver: JitSymbolicSolver | JitAdSolver | StructuralVectorizedSolver | StructuralCompiledSolver = build_emt_solver(
        options=fresh.options, problem=fresh, t0=0.0, t_end=fresh.options.simulation_time,
        h=fresh.options.time_step, method=fresh.options.integration_method)
    fresh_times: np.ndarray
    fresh_values: np.ndarray
    fresh_derivatives: np.ndarray
    fresh_converged: bool
    fresh_initialized: bool
    fresh_times, fresh_values, fresh_derivatives, fresh_initialized, fresh_converged = fresh_solver.simulate(boundary_updater=fresh)
    assert fresh_initialized and fresh_converged
    np.testing.assert_allclose(fresh_times, first_times, rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(fresh_values[:, fresh_runtime.idx_vf], first_values[:, runtime.idx_vf], rtol=0.0, atol=bound)
    np.testing.assert_allclose(fresh_values[:, fresh_runtime.idx_vt], first_values[:, runtime.idx_vt], rtol=0.0, atol=bound)
    np.testing.assert_allclose(fresh_values[:, fresh_runtime.idx_wave_f_re], first_values[:, runtime.idx_wave_f_re], rtol=0.0, atol=bound)
    np.testing.assert_allclose(fresh_values[:, fresh_runtime.idx_wave_t_re], first_values[:, runtime.idx_wave_t_re], rtol=0.0, atol=bound)
    if runtime.phase_real_kernel:
        pass
    else:
        np.testing.assert_allclose(fresh_values[:, fresh_runtime.idx_wave_f_im], first_values[:, runtime.idx_wave_f_im], rtol=0.0, atol=bound)
        np.testing.assert_allclose(fresh_values[:, fresh_runtime.idx_wave_t_im], first_values[:, runtime.idx_wave_t_im], rtol=0.0, atol=bound)
    # Different fixed h is a fresh constructor check, not a variable-step orbit.
    rebind_h: float = 1e-3 if case == JMartiCouplingTestCase.DIRECT_REAL_BALANCED else 0.005
    rebind_options: EmtOptions = EmtOptions(time_step=rebind_h, simulation_time=401 * rebind_h,
        initialization_method=EmtInitializationMethod.Explicit, solver_type=solver_type,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal, init_newton_tol=1e-13)
    retimed: EmtProblemDae = EmtProblemDae(grid=problem.grid, options=rebind_options,
        pf_results=problem.power_flow_results, pf_results_3ph=problem.power_flow_results_3ph)
    assert isinstance(retimed.history_models[0], JMartiHistoryRuntime)
    retimed_runtime: JMartiHistoryRuntime = retimed.history_models[0]
    assert retimed_runtime.runtime_data.get_time_step_s() == rebind_h
    mode_index: int
    mode: JMartiModeRuntimeData
    for mode_index, mode in enumerate(retimed_runtime.runtime_data.get_mode_data()):
        original_mode: JMartiModeRuntimeData = runtime.runtime_data.get_mode_data()[mode_index]
        np.testing.assert_array_equal(mode.get_yc_poles_s(), original_mode.get_yc_poles_s())
        np.testing.assert_array_equal(mode.get_yc_residues(), original_mode.get_yc_residues())
        np.testing.assert_allclose(mode.get_yc_alpha(), (1.0 + 0.5 * rebind_h * original_mode.get_yc_poles_s()) / (1.0 - 0.5 * rebind_h * original_mode.get_yc_poles_s()), rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(mode.get_yc_beta(), rebind_h * original_mode.get_yc_residues() / (1.0 - 0.5 * rebind_h * original_mode.get_yc_poles_s()) ** 2, rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(mode.get_hres_alpha(), (1.0 + 0.5 * rebind_h * original_mode.get_hres_poles_s()) / (1.0 - 0.5 * rebind_h * original_mode.get_hres_poles_s()), rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(mode.get_hres_beta(), rebind_h * original_mode.get_hres_residues() / (1.0 - 0.5 * rebind_h * original_mode.get_hres_poles_s()) ** 2, rtol=0.0, atol=1e-12)
        assert mode.get_delay_step_count() == int(np.floor(original_mode.get_tau_s() / rebind_h))
        assert mode.get_residual_delay_s() == pytest.approx(original_mode.get_tau_s() - mode.get_delay_step_count() * rebind_h, rel=0.0, abs=1e-15)
    if case == JMartiCouplingTestCase.PRODUCTIVE_FIT_SHORT_DIRECT:
        assert retimed_runtime.coupling_block is None
        assert retimed_runtime.idx_wave_f_re == list() and retimed_runtime.idx_q_f_im == list()
    else:
        assert retimed_runtime.runtime_data is not source_data
        assert retimed_runtime.coupling_block is not None
        # A dual declaration must keep Data as the authoritative physical owner.
        dual_fit: object = _build_jmarti_fit_bundle_for_three_phase_line()
        assert isinstance(dual_fit, JMartiFitBundle)
        set_jmarti_block_fit_bundle(source, dual_fit)
        dual: EmtProblemDae = EmtProblemDae(grid=problem.grid, options=rebind_options,
            pf_results=problem.power_flow_results, pf_results_3ph=problem.power_flow_results_3ph)
        assert isinstance(dual.history_models[0], JMartiHistoryRuntime)
        dual_runtime: JMartiHistoryRuntime = dual.history_models[0]
        for mode_index, mode in enumerate(dual_runtime.runtime_data.get_mode_data()):
            np.testing.assert_array_equal(mode.get_yc_poles_s(), retimed_runtime.runtime_data.get_mode_data()[mode_index].get_yc_poles_s())
            np.testing.assert_array_equal(mode.get_yc_alpha(), retimed_runtime.runtime_data.get_mode_data()[mode_index].get_yc_alpha())
            np.testing.assert_array_equal(mode.get_yc_beta(), retimed_runtime.runtime_data.get_mode_data()[mode_index].get_yc_beta())
        assert get_jmarti_block_fit_bundle(source) is dual_fit
        set_jmarti_block_fit_bundle(source, source_fit)
    assert problem.grid.lines[0].emt_model is source
    assert get_jmarti_block_runtime_data(source) is source_data
    assert get_jmarti_block_fit_bundle(source) is source_fit
    replayed_source_saver: BlockSaver = BlockSaver(var_factory=problem.grid.var_factory)
    replayed_source_saver.save_block(source, main=True)
    assert json.dumps((replayed_source_saver.get_blocks(), replayed_source_saver.get_const_to_save(),
        replayed_source_saver.get_vars_to_save(), replayed_source_saver.get_diff_vars_to_save(),
        replayed_source_saver.get_shared_references_to_save(), replayed_source_saver.get_connections_to_save()), sort_keys=True) == serialization
    assert tuple(source.get_all_vars()) == source_vars
    assert tuple(problem.grid.var_factory.get_vars_dict()) == factory_uids
    assert tuple(generator.P for generator in problem.grid.get_generators()) == source_powers
    array: np.ndarray
    before: np.ndarray
    for array, before in zip(provider_arrays, provider_copies):
        np.testing.assert_array_equal(array, before)
