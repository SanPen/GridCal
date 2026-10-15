# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Two-bus persistent-fault experiment using VeraGrid's RMS equations.

Run from the repository root with:
    .venv/bin/python examples/dynamic_fault_equilibrium.py

The converter is represented as an AC injection device, as in a WECC plant
model. Its three differential states are free to evolve. The grid source uses
the existing RMS Thevenin model with a fixed internal EMF.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import VeraGridEngine.api as vg
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import (
    project_initial_algebraic_state, solve_rms_newton_correction,
)
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.shunt_template import ShuntLoadBuild
from VeraGridEngine.Templates.Rms.voltage_source_template import build_thevenin_voltage_source
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Utils.procedural_logic import SampledValueLogic, bool_or
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import VarPowerFlowReferenceType as Ref
from VeraGridEngine.enumerations import ConverterControlType, ConverterFaultControlType, MethodShortCircuit, GeneratorControlMode


def build_wecc_block(vf, voltage_reference: float, rated_ratio: float = 0.5,
                     p_order: float = 0.8, q_order: float = 0.0,
                     kqv: float = 2.0, measurement_tau: float = 0.02,
                     current_tau: float = 0.02, blocking_voltage: float = 0.1) -> Block:
    """Express the existing simplified WECC law as an ordinary RMS block.

    Current and command quantities use converter base; terminal P/Q use system
    base and the injection convention. Setpoints are model parameters, not
    frozen differential states. This is a deliberately small WECC-like model,
    not a complete REGC/REEC implementation.
    """
    vm = vf.add_var("Vm", reference=Ref.Vm)
    p = vf.add_var("P", reference=Ref.P)
    q = vf.add_var("Q", reference=Ref.Q)
    measured = vf.add_var("V_measurement")
    ip = vf.add_var("Ip")
    iq = vf.add_var("Iq")
    blocked = vf.add_var("blocked")
    gain = vf.add_var("Kqv")
    vref = vf.add_var("V_reference")
    pref = vf.add_var("P_order")
    qref = vf.add_var("Q_order")
    tv = vf.add_var("T_measurement")
    ti = vf.add_var("T_current")
    # Keep each control signal explicit: nested symbolic limiters duplicate
    # expression trees, making the equations and graphical expansion enormous.
    signals = {}

    def signal(name, expression):
        variable = vf.add_var(name)
        signals[variable] = expression
        return variable

    dv = signal("V_error", vref - measured)
    deadband = signal("V_deadband", sym.max(dv - 0.05, 0.0) + sym.min(dv + 0.05, 0.0))
    safe_voltage = signal("V_divisor", sym.max(measured, 0.01))
    iq_injection = signal("Iq_support", sym.hard_sat(gain * deadband, -1.1, 1.1))
    iq_unlimited = signal("Iq_unlimited", iq_injection + sym.hard_sat(qref, -1.0, 1.0) / safe_voltage)
    # Same piecewise-linear VDL table as converter_fault_controls.py.
    vdl = signal("I_vdl", 1.1 - 2.0 * sym.hard_sat(measured - 1.1, 0.0, 0.05)
                 - (1.0 / 0.15) * sym.hard_sat(measured - 1.15, 0.0, 0.15))
    iq_limit = signal("Iq_limit", sym.min(vdl, 1.3) * (1.0 - blocked))
    iq_command = signal("Iq_command", sym.hard_sat(iq_unlimited, -iq_limit, iq_limit))
    # Preserve the legacy law, including its asymmetric iq_used convention.
    iq_used = signal("Iq_used", sym.min(sym.min(vdl, 1.3), iq_unlimited))
    ip_limit = signal("Ip_limit", sym.min(vdl, sym.sqrt(sym.max(1.3 ** 2 - iq_used ** 2, 0.0))))
    ip_unlimited = signal("Ip_unlimited", sym.hard_sat(pref, 0.0, 1.0) / safe_voltage)
    ip_command = signal("Ip_command", sym.hard_sat(ip_unlimited, 0.0, ip_limit))
    return Block(
        name="WECC-like voltage support and current limit",
        state_vars=[measured, ip, iq],
        state_eqs=[(vm - measured) / tv, (ip_command - ip) / ti, (iq_command - iq) / ti],
        # Keep this procedural equation block atomic in the diagram. The
        # named signals and equations remain editable in its properties table.
        is_decomposable=False,
        algebraic_vars=[*signals, p, q],
        algebraic_eqs=[v - rhs for v, rhs in signals.items()] + [
            p - rated_ratio * vm * ip * (1.0 - blocked),
            q - rated_ratio * vm * iq * (1.0 - blocked)],
        in_vars=[vm], out_vars=[p, q],
        event_dict={gain: sym.Const(kqv), vref: sym.Const(voltage_reference),
                    pref: sym.Const(p_order), qref: sym.Const(q_order),
                    tv: sym.Const(measurement_tau), ti: sym.Const(current_tau)},
        mode_dict={blocked: sym.Const(0.0)},
        procedural_logic=[SampledValueLogic(
            output_var_name=blocked.name, output_var_uid=blocked.uid,
            source_expr=bool_or(measured <= blocking_voltage, measured >= 1.2),
            name="WECC voltage blocking")],
        init_eqs={measured: vm, ip: pref / vm, iq: qref / vm, **signals},
        external_mapping={Ref.Vm: vm, Ref.P: p, Ref.Q: q},
    )


def build_case(fault_r: float = 0.15, kqv: float = 2.0,
               current_tau: float = 0.02, time_step: float = 0.001,
               end_time: float = 1.0, blocking_voltage: float = 0.1):
    """Initialize the existing RMS assembler for a two-AC-bus grid."""
    if not np.all(np.isfinite([fault_r, kqv, current_tau, time_step, end_time, blocking_voltage])):
        raise ValueError("Example parameters must be finite")
    if fault_r <= 0.0:
        raise ValueError("fault_r must be finite and positive")
    if current_tau <= 0.0 or time_step <= 0.0 or end_time <= 0.1:
        raise ValueError("Positive time constants/step and end_time > 0.1 s are required")
    if not 0.0 < blocking_voltage < 0.9:
        raise ValueError("Choose a blocking threshold between 0 and 0.9 p.u. so the pre-fault converter operates")
    grid = vg.MultiCircuit(name="Two-bus dynamic fault equilibrium", Sbase=100.0)
    source_bus = vg.Bus(name="Source bus", Vnom=20.0, is_slack=True)
    fault_bus = vg.Bus(name="Converter / fault bus", Vnom=20.0)
    for bus_index, bus in enumerate((source_bus, fault_bus)):
        grid.add_bus(bus)
        initialize_bus_rms(bus, vf=grid.var_factory)
        # Distinguish the two connected voltage signals in editor tables.
        for variable in bus.rms_model.out_vars:
            variable.name += f"_bus{bus_index + 1}"
    line = vg.Line(bus_from=source_bus, bus_to=fault_bus, name="AC line",
                   r=0.01, x=0.25, rate=100.0)
    grid.add_line(line)
    source = vg.Generator(name="Grid EMF", vset=1.0, r1=0.01, x1=0.15)
    grid.add_generator(source_bus, source)
    converter = vg.Generator(name="WECC converter", P=40.0, Q=0.0, Snom=50.0,
                             control_mode=GeneratorControlMode.Q)
    grid.add_generator(fault_bus, converter)
    fault = vg.Shunt(name="Persistent fault", G=0.0, B=0.0)
    grid.add_shunt(fault_bus, fault)
    pf = vg.power_flow(grid, options=vg.PowerFlowOptions(tolerance=1e-10))
    if not pf.converged:
        raise RuntimeError("Pre-fault power flow did not converge")
    fault_model = ShuntLoadBuild(grid.var_factory).block
    # This template ships illustrative b=0.4 and Q=0.1 defaults. The fault is
    # initially open, so explicitly set both its admittance and its seeds to zero.
    fault_model.set_parameter_in_model(var_name="b", new_value=0.0)
    fault_model.init_eqs = {v: sym.Const(0.0) for v in fault_model.algebraic_vars}
    fault_model.out_vars = list(fault_model.algebraic_vars)
    for reference in (Ref.P, Ref.Q):
        fault_model.external_mapping[reference].ref = reference
    models = [
        (source, build_thevenin_voltage_source(grid.var_factory, source.R1, source.X1).block),
        (line, get_line_rms_template(grid.var_factory).block),
        (converter, build_wecc_block(grid.var_factory, abs(pf.voltage[1]), kqv=kqv,
                                     current_tau=current_tau, blocking_voltage=blocking_voltage)),
        (fault, fault_model),
    ]
    for device, model in models:
        # These are equation models, including implicit Thevenin constraints.
        # Retain them intact when inspected: graphical decomposition can only
        # represent a subset of an implicit DAE on the current editor path.
        for block in model.get_all_blocks():
            block.is_decomposable = False
            # Keep inherited line parameter mappings visible at equation level.
            block.api_obj_mapping.update({reference: variable
                                          for reference, variable in model.api_obj_mapping.items()
                                          if variable in block.parameters})
        if not model.children:
            # Follow the library template convention: a device interface wraps
            # an equation block, so the editor can draw actual boundary wires.
            model = Block(name=device.name + " RMS", children=[model],
                          in_vars=list(model.in_vars), out_vars=list(model.out_vars),
                          external_mapping=dict(model.external_mapping),
                          api_obj_mapping=dict(model.api_obj_mapping))
        set_rms_model(device=device, model=model, var_factory=grid.var_factory)
    fault_g = next(v for b in fault.rms_model.get_all_blocks() for v in b.event_dict if v.name == "g")
    group = RmsEventsGroup(name="Fault at 0.1 s, no clearing")
    grid.add_rms_events_group(group)
    grid.add_rms_event(RmsEvent(device=fault, parameter=fault_g, time=0.1,
                               value=1.0 / fault_r, group=group,
                               force_step_alignment=True))
    options = RmsOptions(time_step=time_step, simulation_time=end_time,
                         tolerance=1e-9, max_iter=40, verbose=0)
    logger = vg.Logger()
    problem = RmsProblemDae(grid=grid, options=options, pf_results=pf, logger=logger)
    problem.set_events_group(group)
    return grid, pf, problem, converter, source, fault, options


def equilibrium_residual(problem, values):
    """Use the exact time-domain RMS residuals with every derivative set to zero."""
    dx = np.zeros(problem.get_diff_var_number())
    return np.r_[problem.rhs_state(values, dx), problem.rhs_algebraic(values, dx)]


def solve_equilibrium(problem, initial, time: float = 1.0, tolerance: float = 1e-10):
    """Small equilibrium driver over an already compiled RMS problem.

    Memoryless procedural modes are refreshed between continuous solves. This
    example supports its instantaneous blocking rule; it does not infer the
    infinite-time behaviour of timers, latches, PWM, or arbitrary history.
    """
    values = initial.copy()
    voltage_indices = [problem.get_var_idx(bus.rms_model.external_mapping[Ref.Vm])
                       for bus in problem.grid.buses]
    # Deliberately restricted to the memoryless procedural entry in this demo.
    # Never silently interpret a latch, timer or sample history as an equilibrium.
    for block in problem.sys_block.get_all_blocks():
        if any(not isinstance(logic, SampledValueLogic) for logic in block.procedural_logic):
            raise ValueError("This example supports only memoryless SampledValueLogic")
    dx = np.zeros(problem.get_diff_var_number())
    trace = []
    problem.reset_boundary_update_state(0.0)
    for mode_iteration in range(8):
        problem.update_variable_params(t=time, x_snapshot=values, scheduled_t=time)
        # Reconcile algebraic signals with the supplied state seed, just as
        # the time integrator does. This is a zero-time projection, not a
        # trajectory or a constraint freezing the converter states below.
        values, projected, _ = project_initial_algebraic_state(
            problem, values, dx, tolerance=tolerance, max_iter=40)
        if not projected or np.any(values[voltage_indices] <= 1e-6):
            raise RuntimeError("Equilibrium Newton initial algebraic projection failed")
        for iteration in range(40):
            residual = equilibrium_residual(problem, values)
            error = float(np.linalg.norm(residual, np.inf))
            trace.append(error)
            if error <= tolerance:
                break
            jacobian = sp.bmat([[problem.get_fx_ct(values, dx), problem.get_fy_ct(values, dx)],
                               [problem.get_gx_ct(values, dx), problem.get_gy_ct(values, dx)]], format="csc")
            if jacobian.shape != (len(values), len(values)):
                raise ValueError("This example requires a square RMS system with a fixed source EMF")
            delta = solve_rms_newton_correction(jacobian, residual, reference_column=None)
            if not np.all(np.isfinite(delta)):
                raise RuntimeError("Equilibrium Jacobian is singular or non-finite")
            for reduction in range(20):
                trial = values + (0.5 ** reduction) * delta
                # Power-balance equations admit spurious zero-voltage roots.
                # Keep the polar voltage magnitudes in their physical domain.
                if np.any(trial[voltage_indices] <= 1e-6):
                    continue
                if np.linalg.norm(equilibrium_residual(problem, trial), np.inf) < error:
                    values = trial
                    break
            else:
                raise RuntimeError(f"Equilibrium Newton stalled: residual {error:.3g}")
        else:
            raise RuntimeError("Equilibrium Newton exceeded 40 iterations")
        # Recheck the same block-attached procedural logic against the solved state.
        problem.update_variable_params(t=time, x_snapshot=values, scheduled_t=time)
        if np.linalg.norm(equilibrium_residual(problem, values), np.inf) <= tolerance:
            return values, np.asarray(trace)
    raise RuntimeError("Equilibrium procedural modes did not settle")


def build_hardcoded_reference(fault_r: float, blocking_voltage: float = 0.1):
    """Prepare the unmodified legacy SC driver on an equivalent AC network.

    The legacy WECC path requires a VSC branch, hence one auxiliary DC supply
    bus here. The two physical AC buses, source impedance and converter rating
    match the dynamic case; the DC supply adjusts its power without a DC limit.
    """
    grid = vg.MultiCircuit(name="Legacy WECC comparison", Sbase=100.0)
    source_bus = vg.Bus(name="Source bus", Vnom=20.0, is_slack=True)
    fault_bus = vg.Bus(name="Converter / fault bus", Vnom=20.0)
    dc_bus = vg.Bus(name="Auxiliary DC supply", Vnom=20.0, is_dc=True, is_slack=True)
    for bus in (source_bus, fault_bus, dc_bus):
        grid.add_bus(bus)
    grid.add_line(vg.Line(bus_from=source_bus, bus_to=fault_bus, r=0.01, x=0.25, rate=100.0))
    grid.add_generator(source_bus, vg.Generator(vset=1.0, r1=0.01, x1=0.15))
    grid.add_generator(dc_bus, vg.Generator(vset=1.0, r1=0.01))
    grid.add_vsc(vg.VSC(bus_from=dc_bus, bus_to=fault_bus, rate=50.0,
                        alpha1=0.0, alpha2=0.0, alpha3=0.0,
                        control1=ConverterControlType.Pac, control1_val=-40.0,
                        control2=ConverterControlType.Qac, control2_val=0.0,
                        min_ac_voltage=blocking_voltage,
                        fault_control=ConverterFaultControlType.WECC_WT_Type_4B))
    options = vg.PowerFlowOptions(tolerance=1e-10, max_iter=80, retry_with_other_methods=False)
    pf = vg.power_flow(grid, options=options)
    if not pf.converged:
        raise RuntimeError("Legacy comparison power flow did not converge")
    grid.add_short_circuit_event(vg.ShortCircuitEvent(device=fault_bus, r_fault=fault_r,
                                                     method=MethodShortCircuit.sequences_vsc))
    driver = vg.ShortCircuitDriver(grid=grid, options=vg.ShortCircuitOptions(),
                                   pf_options=options, pf_results=pf, pf_results3ph=None)

    return pf, driver


def hardcoded_reference(fault_r: float, blocking_voltage: float = 0.1):
    """Run the prepared legacy driver and return only a converged reference."""
    pf, driver = build_hardcoded_reference(fault_r, blocking_voltage)
    driver.run()
    if any("did not converge" in entry.msg for entry in driver.logger.entries):
        return pf, None
    return pf, driver.results


def prepare_prefault(problem):
    """Reuse RMS's zero-time algebraic projection before applying the fault."""
    problem.reset_boundary_update_state(0.0)
    x0 = problem.get_x0()
    problem.update_variable_params(t=0.0, x_snapshot=x0, scheduled_t=0.0)
    x0, converged, error = project_initial_algebraic_state(
        problem, x0, np.zeros(problem.get_diff_var_number()), tolerance=1e-10, max_iter=40)
    if not converged or np.linalg.norm(equilibrium_residual(problem, x0), np.inf) > 1e-8:
        raise RuntimeError(f"Pre-fault dynamic equilibrium is inconsistent: {error:.3g}")
    return x0


def run_case(fault_r=0.15, kqv=2.0, current_tau=0.02, time_step=0.001, end_time=1.0,
             blocking_voltage=0.1):
    """Solve equilibrium and integrate the very same compiled RMS problem."""
    grid, pf, problem, converter, source, fault, options = build_case(
        fault_r, kqv, current_tau, time_step, end_time, blocking_voltage)
    x0 = prepare_prefault(problem)
    # Save generator EMFs to verify that neither solve alters them.
    emf_vars = [v for b in source.rms_model.get_all_blocks() for v in b.event_dict]
    emf_indices = [problem.uid2idx_event_params[v.uid] for v in emf_vars]
    emf_before = problem._variable_parameters_values[emf_indices].copy()
    start = perf_counter()
    equilibrium, trace = solve_equilibrium(problem, x0)
    equilibrium_seconds = perf_counter() - start
    problem.reset_boundary_update_state(0.0)
    solver = BackEulerImplicitIntegration(problem, t0=0.0, t_end=options.simulation_time,
                                         h=options.time_step, max_iter=options.max_iter,
                                         tolerance=options.tolerance)
    start = perf_counter()
    times, trajectory, initialized, converged = solver.simulate()
    integration_seconds = perf_counter() - start
    if not initialized or not converged:
        raise RuntimeError("RMS time integration failed")
    vm_indices = [problem.get_var_idx(bus.rms_model.external_mapping[Ref.Vm]) for bus in grid.buses]
    if np.any(trajectory[:, vm_indices] <= 1e-6):
        raise RuntimeError("RMS power-balance integration reached a nonphysical zero/negative-voltage branch")
    problem.update_variable_params(t=times[-1], x_snapshot=trajectory[-1], scheduled_t=times[-1])
    final_residual = float(np.linalg.norm(equilibrium_residual(problem, trajectory[-1]), np.inf))
    endpoint_error = float(np.max(np.abs(trajectory[-1] - equilibrium)))
    if final_residual > 1e-6 or endpoint_error > 1e-6:
        raise RuntimeError(f"RMS has not settled: residual={final_residual:.3g}, endpoint error={endpoint_error:.3g}")
    if not np.array_equal(emf_before, problem._variable_parameters_values[emf_indices]):
        raise RuntimeError("Generator internal EMF changed")
    va_indices = [problem.get_var_idx(bus.rms_model.external_mapping[Ref.Va]) for bus in grid.buses]
    state_indices = [problem.get_var_idx(v) for b in converter.rms_model.get_all_blocks() for v in b.state_vars]
    p_index = problem.get_var_idx(converter.rms_model.external_mapping[Ref.P])
    q_index = problem.get_var_idx(converter.rms_model.external_mapping[Ref.Q])
    return dict(grid=grid, pf=pf, problem=problem, converter=converter,
                initial=x0, equilibrium=equilibrium, trace=trace, times=times, trajectory=trajectory,
                vm_indices=vm_indices, va_indices=va_indices, state_indices=state_indices,
                p_index=p_index, q_index=q_index, fault_r=fault_r,
                blocking_voltage=blocking_voltage,
                equilibrium_seconds=equilibrium_seconds, integration_seconds=integration_seconds,
                final_residual=final_residual, endpoint_error=endpoint_error,
                emf=emf_before)


def physical_results(result):
    """Compute independent terminal-current and KCL checks on system base."""
    values = result["equilibrium"]
    voltage = values[result["vm_indices"]] * np.exp(1j * values[result["va_indices"]])
    power = complex(values[result["p_index"]], values[result["q_index"]])
    converter_current = np.conj(power / voltage[1])
    fault_current = voltage[1] / result["fault_r"]
    line_current = (voltage[0] - voltage[1]) / complex(0.01, 0.25)
    emf = result["emf"][0] * np.exp(1j * result["emf"][1])
    source_current = (emf - voltage[0]) / complex(0.01, 0.15)
    kcl = max(abs(source_current - line_current), abs(line_current + converter_current - fault_current))
    return voltage, power, converter_current, fault_current, float(kcl)


def write_report(result, reference_pf, reference, directory: Path, kqv: float):
    """Write a reproducible numerical report."""

    directory.mkdir(parents=True, exist_ok=True)
    voltage, power, converter_current, fault_current, kcl = physical_results(result)
    baseline_voltage = None if reference is None else reference.voltage1[:2, 0]
    baseline_power = None if reference is None else -reference.vsc_St[0, 0] / result["grid"].Sbase
    pre_error = float(np.max(np.abs(result["pf"].voltage - reference_pf.voltage[:2])))
    baseline_error = None if reference is None else float(np.max(np.abs(voltage - baseline_voltage)))
    equilibrium_error = float(np.linalg.norm(equilibrium_residual(result["problem"], result["equilibrium"]), np.inf))
    if pre_error > 1e-8 or kcl > 1e-8:
        raise RuntimeError("Reference network or independent current balance is inconsistent")
    if reference is not None and kqv == 2.0 and (baseline_error > 1e-6 or abs(power - baseline_power) > 1e-6):
        raise RuntimeError("Dynamic model does not reproduce the hardcoded WECC baseline")

    summary = dict(
        fault_resistance_pu=result["fault_r"], kqv=kqv, blocking_voltage_pu=result["blocking_voltage"],
        states={result["problem"].state_vars[i].name: {
            "prefault": float(result["initial"][index]),
            "equilibrium": float(result["equilibrium"][index]),
            "rms_endpoint": float(result["trajectory"][-1, index]),
        } for i, index in enumerate(result["state_indices"])},
        bus_voltage_magnitude_pu=np.abs(voltage).tolist(),
        converter_active_power_mw=power.real * 100.0,
        converter_reactive_power_mvar=power.imag * 100.0,
        converter_current_pu_on_50_mva_base=float(abs(converter_current) / 0.5),
        fault_current_pu_on_100_mva_base=float(abs(fault_current)),
        equilibrium_residual_inf=equilibrium_error,
        rms_endpoint_residual_inf=result["final_residual"],
        rms_endpoint_vs_equilibrium_max_abs=result["endpoint_error"],
        independent_kcl_residual_pu=kcl,
        prefault_reference_voltage_max_abs=pre_error,
        legacy_reference_voltage_max_abs=baseline_error,
        legacy_reference_converged=reference is not None,
        legacy_reference_kqv=2.0,
        equilibrium_solve_seconds=result["equilibrium_seconds"],
        rms_integration_seconds=result["integration_seconds"],
        generator_internal_emf_magnitude_pu=float(result["emf"][0]),
        generator_internal_emf_angle_rad=float(result["emf"][1]),
    )
    (directory / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    vg.save_file(result["grid"], str(directory / "two_bus.veragrid"))
    np.savetxt(directory / "rms_trajectory.csv", np.column_stack([result["times"], result["trajectory"]]),
               delimiter=",", header="time_s," + ",".join(f"{i}:{v.name}" for i, v in enumerate(result["problem"].state_and_algebraic_vars)), comments="")
    np.savetxt(directory / "equilibrium_convergence.csv", result["trace"],
               delimiter=",", header="residual_inf", comments="")

    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fault-r", type=float, default=0.15, help="Fault resistance in system p.u.")
    parser.add_argument("--kqv", type=float, default=2.0, help="Dynamic model voltage-support gain (legacy baseline: 2)")
    parser.add_argument("--current-tau", type=float, default=0.02, help="Current-state time constant in seconds")
    parser.add_argument("--duration", type=float, default=1.0, help="Physical RMS simulation duration in seconds")
    parser.add_argument("--time-step", type=float, default=0.001, help="RMS integration step in seconds")
    parser.add_argument("--blocking-voltage", type=float, default=0.1, help="Low-voltage blocking threshold in p.u.")
    parser.add_argument("--output", type=Path, default=Path("output/dynamic_fault_equilibrium"))
    args = parser.parse_args()
    result = run_case(args.fault_r, args.kqv, args.current_tau, args.time_step, args.duration, args.blocking_voltage)
    reference_pf, reference = hardcoded_reference(args.fault_r, args.blocking_voltage)
    summary = write_report(result, reference_pf, reference, args.output, args.kqv)
    print("\nTwo-bus RMS persistent-fault equilibrium")
    print("Source / converter voltage:", ", ".join(f"{v:.6f} p.u." for v in summary["bus_voltage_magnitude_pu"]))
    print(f"Converter: {summary['converter_active_power_mw']:.4f} MW, {summary['converter_reactive_power_mvar']:.4f} MVAr, {summary['converter_current_pu_on_50_mva_base']:.6f} p.u. current")
    print(f"Fault current: {summary['fault_current_pu_on_100_mva_base']:.6f} p.u. on 100 MVA base")
    print(f"RMS endpoint error: {summary['rms_endpoint_vs_equilibrium_max_abs']:.2e}")
    if summary["legacy_reference_converged"]:
        print(f"Legacy voltage error: {summary['legacy_reference_voltage_max_abs']:.2e}")
    else:
        print("Legacy WECC solver did not converge; its output is excluded from the comparison.")
    print(f"Equilibrium / RMS solve time (compilation excluded): {summary['equilibrium_solve_seconds']:.3f} / {summary['rms_integration_seconds']:.3f} s")
    print(f"Numerical results: {args.output.resolve()}")


if __name__ == "__main__":
    main()
