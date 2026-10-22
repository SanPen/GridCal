# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
System-level integration test for the grid-forming VSC EMT template.

The system models a DC-fed AC island:

    [DC bus] -- DC voltage source -+
                                   |
                                  VSC (GFM)
                                   |
                              [AC bus 1] -- AC line -- [AC bus 2] -- Load (R)

The tests cover:

* PF-consistent EMT initialization with small residual and physically
  sensible converter state (``omega = 1.0``, ``Epk ~ sqrt(2)``,
  ``Pe > 0`` for AC generation).
* Runtime event registration and ``problem.update`` evaluation along the
  same pattern as ``test_switched_vsc_emt_passes_validation_and_switches_gates``.
* Full ``solver.simulate`` over the load step: the AC current and bus
  voltage stay bounded and sinusoidal, ``omega`` drifts only slightly,
  and the load resistance step changes converter active power as
  expected.
"""

from typing import Any, cast

import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import get_bergeron_line_emt_template
from VeraGridEngine.Templates.Emt.vsc_gfm_emt import get_gfm_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DeviceType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ParamPowerFlowReferenceType,
    ShuntConnectionType,
    VarPowerFlowReferenceType,
    SolverType,
)


def _build_rl_line_emt_template(
    vf: VarFactory,
    R_pu: float,
    X_pu: float,
    name: str = "RL",
) -> EmtModelTemplate:
    """
    Build a minimal three-phase series-RL line EMT template.

    The line carries the converter output filter R + L, replacing the
    impedance that used to live inside the GFM model. No shunt
    capacitance and no history terms — just ``L * di/dt = v_f - v_t -
    R * i``, with one current state per phase. ``R`` and ``X`` are
    hard-coded constants so the template needs no overhead-line
    template attached to its API device.

    :param vf: EMT variable factory.
    :param R_pu: Per-unit resistance.
    :param X_pu: Per-unit reactance.
    :param name: Symbolic suffix for the line variables.
    :return: Configured EMT line template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name
    templ.block.name = name

    R_par = vf.add_var(name=f"R_{name}")
    X_par = vf.add_var(name=f"X_{name}")
    omega_base = vf.add_var(name=f"omega_base_{name}")

    vf_A = vf.add_var(name=f"vf_A_{name}", reference=VarPowerFlowReferenceType.vf_A)
    vf_B = vf.add_var(name=f"vf_B_{name}", reference=VarPowerFlowReferenceType.vf_B)
    vf_C = vf.add_var(name=f"vf_C_{name}", reference=VarPowerFlowReferenceType.vf_C)
    vt_A = vf.add_var(name=f"vt_A_{name}", reference=VarPowerFlowReferenceType.vt_A)
    vt_B = vf.add_var(name=f"vt_B_{name}", reference=VarPowerFlowReferenceType.vt_B)
    vt_C = vf.add_var(name=f"vt_C_{name}", reference=VarPowerFlowReferenceType.vt_C)

    i_ser_A = vf.add_var(name=f"i_ser_A_{name}")
    i_ser_B = vf.add_var(name=f"i_ser_B_{name}")
    i_ser_C = vf.add_var(name=f"i_ser_C_{name}")
    di_A = vf.add_diff_var(name=f"di_A_{name}", base_var=i_ser_A)
    di_B = vf.add_diff_var(name=f"di_B_{name}", base_var=i_ser_B)
    di_C = vf.add_diff_var(name=f"di_C_{name}", base_var=i_ser_C)

    if_A = vf.add_var(name=f"if_A_{name}", reference=VarPowerFlowReferenceType.if_A)
    if_B = vf.add_var(name=f"if_B_{name}", reference=VarPowerFlowReferenceType.if_B)
    if_C = vf.add_var(name=f"if_C_{name}", reference=VarPowerFlowReferenceType.if_C)
    it_A = vf.add_var(name=f"it_A_{name}", reference=VarPowerFlowReferenceType.it_A)
    it_B = vf.add_var(name=f"it_B_{name}", reference=VarPowerFlowReferenceType.it_B)
    it_C = vf.add_var(name=f"it_C_{name}", reference=VarPowerFlowReferenceType.it_C)

    state_eqs = [
        omega_base * (vf_A - vt_A - R_par * i_ser_A) / X_par,
        omega_base * (vf_B - vt_B - R_par * i_ser_B) / X_par,
        omega_base * (vf_C - vt_C - R_par * i_ser_C) / X_par,
    ]
    algebraic_eqs = [
        if_A - i_ser_A,
        if_B - i_ser_B,
        if_C - i_ser_C,
        it_A - (-i_ser_A),
        it_B - (-i_ser_B),
        it_C - (-i_ser_C),
    ]
    templ.block = Block(
        state_eqs=state_eqs,
        state_vars=[i_ser_A, i_ser_B, i_ser_C],
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=[if_A, if_B, if_C, it_A, it_B, it_C],
        in_vars=[vf_A, vf_B, vf_C, vt_A, vt_B, vt_C],
        out_vars=[if_A, if_B, if_C, it_A, it_B, it_C],
    )
    templ.block.diff_vars = [di_A, di_B, di_C]
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.vf_A: vf_A,
        VarPowerFlowReferenceType.vf_B: vf_B,
        VarPowerFlowReferenceType.vf_C: vf_C,
        VarPowerFlowReferenceType.vt_A: vt_A,
        VarPowerFlowReferenceType.vt_B: vt_B,
        VarPowerFlowReferenceType.vt_C: vt_C,
        VarPowerFlowReferenceType.if_A: if_A,
        VarPowerFlowReferenceType.if_B: if_B,
        VarPowerFlowReferenceType.if_C: if_C,
        VarPowerFlowReferenceType.it_A: it_A,
        VarPowerFlowReferenceType.it_B: it_B,
        VarPowerFlowReferenceType.it_C: it_C,
    }
    templ.block.api_obj_mapping = {
        ParamPowerFlowReferenceType.omega_base: omega_base,
    }
    templ.block.event_dict = {
        omega_base: vf.add_const(2.0 * np.pi * 50.0),
        R_par: vf.add_const(float(R_pu)),
        X_par: vf.add_const(float(X_pu)),
    }
    # The series RL model owns its internal-current initialization.
    templ.block.init_eqs = {
        i_ser_A: if_A,
        i_ser_B: if_B,
        i_ser_C: if_C,
    }
    templ.block.diff_init_eqs = {
        di_A: omega_base * (vf_A - vt_A - R_par * i_ser_A) / X_par,
        di_B: omega_base * (vf_B - vt_B - R_par * i_ser_B) / X_par,
        di_C: omega_base * (vf_C - vt_C - R_par * i_ser_C) / X_par,
    }
    return templ


def _find_name_in_block(name: str, block: Block) -> Any:
    """
    Locate one symbolic variable by name inside a block hierarchy.

    :param name: Symbolic variable name.
    :param block: Root symbolic block.
    :return: Matching variable or ``None``.
    """
    for var in (
        block.algebraic_vars
        + block.state_vars
        + list(block.event_dict.keys())
        + list(block.parameters.keys())
        + block.diff_vars
    ):
        if name == var.name:
            return var
    for child in block.children:
        found = _find_name_in_block(name, child)
        if found is not None:
            return found
    return None


def _build_dc_fed_gfm_island(balanced_line: bool = False) -> tuple:
    """
    Assemble the small DC-fed GFM island grid with EMT models attached.

    :return: Tuple ``(grid, vsc, load, R_A, R_B, R_C)`` ready for EMT.
    """
    vnom_ac: float = 10.0
    vnom_dc: float = 1.0
    grid: gce.MultiCircuit = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

    bus_dc: gce.Bus = gce.Bus(name="Bus_DC", Vnom=vnom_dc, is_dc=True, is_slack=True)
    bus_vsc_int: gce.Bus = gce.Bus(name="Bus_VSC_Internal", Vnom=vnom_ac)
    bus_ac1: gce.Bus = gce.Bus(name="Bus_AC1", Vnom=vnom_ac)
    bus_ac2: gce.Bus = gce.Bus(name="Bus_AC2", Vnom=vnom_ac)
    grid.add_bus(bus_dc)
    grid.add_bus(bus_vsc_int)
    grid.add_bus(bus_ac1)
    grid.add_bus(bus_ac2)

    gen_dc: gce.Generator = gce.Generator(
        name="DC_Gen",
        vset=1.0,
        Snom=2.0,
        freq=50.0,
        r1=0.001,
        x1=0.01,
    )
    grid.add_generator(bus_dc, gen_dc)

    # The VSC is treated as a pure converter: PF pins its internal bus
    # voltage to 1.0 pu. The GFM's series filter R + L is modelled as a
    # separate RL branch between the internal bus and bus_ac1 so PF
    # accounts for the filter impedance naturally and the EMT settled
    # operating point matches the PF prediction at every bus.
    vsc: gce.VSC = gce.VSC(
        name="GFM_VSC",
        alpha1=0.0, alpha2=0.0, alpha3=0.0,
        bus_from=bus_dc,
        bus_to=bus_vsc_int,
        rate=2.0,
        control1=ConverterControlType.Vm_ac,
        control2=ConverterControlType.Va_ac,
        control1_val=1.0,
        control2_val=0.0,
    )
    grid.add_vsc(vsc)

    filter_R_pu: float = 0.01
    filter_X_pu: float = 0.1
    filter_line: gce.Line = gce.Line(
        name="VSC_Filter",
        bus_from=bus_vsc_int,
        bus_to=bus_ac1,
        r=filter_R_pu,
        x=filter_X_pu,
        b=0.0,
        rate=2.0,
    )
    grid.add_line(filter_line)

    line: gce.Line = gce.Line(
        name="Line",
        bus_from=bus_ac1,
        bus_to=bus_ac2,
        length=10.0,
        rate=2.0,
    )
    tower = gce.OverheadLineType(name="Tower", Vnom=vnom_ac)
    wire = gce.Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line.apply_template(tower, grid.Sbase, grid.fBase)
    if balanced_line:
        # Use the sequence equivalent in both balanced PF and EMT.
        line.template = None
    grid.add_line(line)

    # Constant-admittance loads (G/B), so PF and EMT see the same load
    # model: ``S_load = (G + jB) * |V|^2``. The EMT shunt-R template is
    # a fixed resistor per phase, so its draw scales with ``V^2``; using
    # G in PF matches the EMT resistor voltage dependence. The balanced PI
    # variant also matches the line model for the steady-state regression.
    R_load_initial: float = 100.0
    v_ph: float = vnom_ac / np.sqrt(3.0)
    G_ph_initial: float = (v_ph * v_ph) / R_load_initial
    G_total_initial: float = 3.0 * G_ph_initial
    load: gce.Load = gce.Load(
        name="Load",
        G=G_total_initial,
        B=0.0,
        G1=G_ph_initial,
        G2=G_ph_initial,
        G3=G_ph_initial,
        B1=0.0,
        B2=0.0,
        B3=0.0,
    )
    load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus_ac2, load)

    R_damp: float = 1.0e3
    G_ph_damp: float = (v_ph * v_ph) / R_damp
    G_total_damp: float = 3.0 * G_ph_damp
    damp_shunt: gce.Load = gce.Load(
        name="DampShunt",
        G=G_total_damp,
        B=0.0,
        G1=G_ph_damp,
        G2=G_ph_damp,
        G3=G_ph_damp,
        B1=0.0,
        B2=0.0,
        B3=0.0,
    )
    damp_shunt.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus_ac1, damp_shunt)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    # Include the Norton voltage drop when deriving the source setpoint.
    dc_src_mdl = get_dc_voltage_source_emt_template(
        vf=grid.var_factory,
        source_voltage_value=None,
        source_conductance_value=200.0,
        name="DC_Gen",
    ).block
    # The GFM's internal series impedance now sits in the filter line,
    # so set the GFM's internal R_s / X_s to a vanishing value. A small
    # but finite ``X_s`` is required to keep the state equation for
    # ``di/dt`` well-posed; 1.0e-4 pu is small enough that the GFM
    # behaves as an ideal voltage source compared to the 0.1 pu filter.
    vsc_template = get_gfm_emt_template(vf=grid.var_factory, name="GFM_VSC")
    R_s_var = _find_name_in_block("R_s", vsc_template.block)
    X_s_var = _find_name_in_block("X_s", vsc_template.block)
    assert R_s_var is not None and X_s_var is not None
    vsc_template.block.children[0].parameters[R_s_var] = grid.var_factory.add_const(1.0e-4)
    vsc_template.block.children[0].parameters[X_s_var] = grid.var_factory.add_const(1.0e-4)
    vsc_mdl = vsc_template.block
    if balanced_line:
        line_mdl = get_pi_line_emt_template(vf=grid.var_factory).block
    else:
        line_mdl = get_bergeron_line_emt_template(
            vf=grid.var_factory,
            phN=False,
            phA=True,
            phB=True,
            phC=True,
        ).block
    filter_mdl = _build_rl_line_emt_template(
        vf=grid.var_factory,
        R_pu=filter_R_pu,
        X_pu=filter_X_pu,
        name="VSC_Filter",
    ).block
    load_mdl = get_shunt_r_emt_template(
        vf=grid.var_factory,
        phA=True,
        phB=True,
        phC=True,
    ).block
    damp_mdl = get_shunt_r_emt_template(
        vf=grid.var_factory,
        phA=True,
        phB=True,
        phC=True,
        name="DampShunt_R",
    ).block

    # The default shunt-R template derives ``R`` from ``load.P`` via
    # ``R = Vnom^2 / Pl0``. Because we are using a Y-load (``load.G``)
    # in PF so PF and EMT see the same load model, ``Pl0`` is zero and
    # that expression would divide by zero. Override the per-phase
    # ``R`` event entries with hardcoded numerical constants derived
    # directly from ``G_pu``. Runtime ``EmtEvent`` updates to these
    # variables (the load-step events used by the tests) still work
    # because the events overwrite the entry at the event time.
    def _override_shunt_r(template: Any, event_suffix: str,
                          G_total_pu: float) -> None:
        # EMT phase currents use the system three-phase current base.
        # A phase resistor therefore sees the total per-unit conductance.
        R_pu: float = 1.0 / G_total_pu
        for phase_label in ("A", "B", "C"):
            R_var = _find_name_in_block(f"R_{phase_label}_{event_suffix}", template)
            assert R_var is not None
            # The resistance is owned by a child block. Replacing only the
            # wrapper entry leaves the compiled runtime equation at 1e9 pu.
            owners = [block for block in template.get_all_blocks()
                      if any(var.uid == R_var.uid for var in block.event_dict)]
            assert owners, f"No runtime owner for {R_var.name}"
            for owner in owners:
                owner.event_dict[R_var] = grid.var_factory.add_const(R_pu)

    _override_shunt_r(load_mdl, "Shunt_R_3ph",
                      G_total_pu=G_total_initial / grid.Sbase)
    _override_shunt_r(damp_mdl, "DampShunt_R_3ph",
                      G_total_pu=G_total_damp / grid.Sbase)

    set_emt_model(device=gen_dc, model=dc_src_mdl, var_factory=grid.var_factory)
    set_emt_model(device=vsc, model=vsc_mdl, var_factory=grid.var_factory)
    set_emt_model(device=filter_line, model=filter_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line, model=line_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)
    set_emt_model(device=damp_shunt, model=damp_mdl, var_factory=grid.var_factory)

    R_A = _find_name_in_block("R_A_Shunt_R_3ph", load_mdl)
    R_B = _find_name_in_block("R_B_Shunt_R_3ph", load_mdl)
    R_C = _find_name_in_block("R_C_Shunt_R_3ph", load_mdl)

    return grid, vsc, load, R_A, R_B, R_C


def test_vsc_gfm_emt_dc_fed_island_initializes_consistently() -> None:
    """Check mapped GFM references and the initialized operating point."""
    grid, vsc, _, _, _, _ = _build_dc_fed_gfm_island()

    pf_options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=50,
        tolerance=1e-6,
    )
    pf_results = gce.power_flow(grid=grid, options=pf_options)
    assert pf_results.converged

    options: EmtOptions = EmtOptions(
        time_step=1.0e-5,  # Resolve the 10 km Bergeron line's shortest modal delay.
        simulation_time=0.01,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        verbose=0,
    )
    problem: EmtProblemDae = EmtProblemDae(
        grid=grid,
        options=options,
        pf_results_3ph=None,
        pf_results=pf_results,
    )

    assert problem.initialization_report is not None
    final_residual: float = float(problem.initialization_report.final_residual_inf)
    assert final_residual <= 1.0e-6, (
        f"EMT init residual too large: {final_residual:.3e}"
    )

    x0 = problem.get_x0()

    omega_var = _find_name_in_block("omega", vsc.emt_model)
    Epk_var = _find_name_in_block("Epk", vsc.emt_model)
    Pe_var = _find_name_in_block("Pe", vsc.emt_model)
    theta_var = _find_name_in_block("theta", vsc.emt_model)
    assert omega_var is not None
    assert Epk_var is not None
    assert Pe_var is not None
    assert theta_var is not None

    omega_init: float = float(x0[problem.get_var_idx(omega_var)])
    Epk_init: float = float(x0[problem.get_var_idx(Epk_var)])
    Pe_init: float = float(x0[problem.get_var_idx(Pe_var)])

    assert abs(omega_init - 1.0) < 1.0e-6, (
        f"Steady-state omega should start at 1.0 pu, got {omega_init:.6f}"
    )
    assert 1.0 < Epk_init < 2.0, (
        f"Steady-state Epk should be near sqrt(2) pu, got {Epk_init:.6f}"
    )
    assert Pe_init > 0.1, (
        f"Steady-state Pe should be positive (converter generating into AC load), got {Pe_init:.6f}"
    )
    expected_pe: float = float(-np.real(pf_results.St_vsc[0]) / grid.Sbase)
    assert abs(Pe_init - expected_pe) < 1.0e-6, (
        f"VSC Pe must match total AC PF export: {Pe_init:.6f} vs {expected_pe:.6f}"
    )
    p_ref_var = _find_name_in_block("P_ref", vsc.emt_model)
    assert p_ref_var is not None
    p_ref_idx = problem.uid2idx_event_params[p_ref_var.uid]
    assert abs(float(problem.event_params_values[p_ref_idx]) - Pe_init) < 1.0e-6
    # The voltage controller must start at the internal EMF, including the
    # impedance drop, rather than at the terminal voltage magnitude.
    voltage_ref = _find_name_in_block("V_ref", vsc.emt_model)
    terminal_peak = _find_name_in_block("Vpk_ref", vsc.emt_model)
    emf_derivative = _find_name_in_block("d_Epk", vsc.emt_model)
    assert voltage_ref is not None and terminal_peak is not None and emf_derivative is not None
    reference_value = problem.event_params_values[problem.uid2idx_event_params[voltage_ref.uid]]
    terminal_value = problem.event_params_values[problem.uid2idx_event_params[terminal_peak.uid]]
    np.testing.assert_allclose(reference_value, Epk_init, rtol=0.0, atol=1e-9)
    assert abs(reference_value - terminal_value) > 1e-5
    reactive_ref = _find_name_in_block("Q_ref", vsc.emt_model)
    reactive_power = _find_name_in_block("Qe", vsc.emt_model)
    q_reference = problem.event_params_values[problem.uid2idx_event_params[reactive_ref.uid]]
    q_actual = x0[problem.get_var_idx(reactive_power)]
    np.testing.assert_allclose(q_actual, q_reference, rtol=0.0, atol=1e-8)
    np.testing.assert_allclose(
        problem.get_dx0()[problem.get_diff_var_idx(emf_derivative)],
        0.0, rtol=0.0, atol=1e-8,
    )
    # PF projection must give equal and opposite converter/filter current on
    # the shared AC bus, using the same three-phase system current base.
    i_a_var = _find_name_in_block("i_A", vsc.emt_model)
    filter_if_a_var = _find_name_in_block("if_A_VSC_Filter", grid.lines[0].emt_model)
    assert i_a_var is not None and filter_if_a_var is not None
    assert abs(float(x0[problem.get_var_idx(i_a_var)] +
                     x0[problem.get_var_idx(filter_if_a_var)])) < 1.0e-6

    # Bergeron PF history sources must survive runtime-vector construction.
    history = problem.history_models[0]
    history_values = np.asarray([
        problem.event_params_values[problem.uid2idx_event_params[var.uid]]
        for var in (*history.Ih_f, *history.Ih_t)
    ])
    assert np.any(np.abs(history_values) > 1.0e-6)


def test_vsc_gfm_emt_dc_fed_island_event_registration_and_update_path() -> None:
    """
    Build the DC-fed GFM island, register a load-step EmtEvent, and
    evaluate ``problem.update`` at several time points to confirm the
    runtime update path runs end-to-end without raising. This mirrors
    the runtime-evaluation half of
    ``test_switched_vsc_emt_passes_validation_and_switches_gates``.

    :return: None.
    """
    grid, vsc, load, R_A, R_B, R_C = _build_dc_fed_gfm_island()
    assert R_A is not None 
    assert R_B is not None
    assert R_C is not None

    pf_options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=50,
        tolerance=1e-6,
    )
    pf_results = gce.power_flow(grid=grid, options=pf_options)
    assert pf_results.converged

    events_group: EmtEventsGroup = EmtEventsGroup(name="gfm_load_step")
    grid.add_emt_events_group(events_group)
    R_step_value: float = 60.0
    event_time: float = 0.02
    for phase_R in (R_A, R_B, R_C):
        grid.add_emt_event(
            EmtEvent(
                device=load,
                parameter=phase_R,
                time=event_time,
                value=R_step_value,
                group=events_group,
            )
        )

    options: EmtOptions = EmtOptions(
        time_step=1.0e-5,  # Resolve the 10 km Bergeron line's shortest modal delay.
        simulation_time=0.05,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        verbose=0,
    )

    problem: EmtProblemDae = EmtProblemDae(
        grid=grid,
        options=options,
        pf_results_3ph=None,
        pf_results=pf_results,
    )
    problem.set_events_group(events_group)

    assert problem.initialization_report is not None

    runtime_param_map = {var.name: var for var in problem.get_variable_parameters()}
    assert "R_A_Shunt_R_3ph" in runtime_param_map, (
        "Load runtime parameter not exposed by EMT problem"
    )

    problem.reset_boundary_update_state(0.0)
    x0 = problem.get_x0()
    runtime_values: np.ndarray = problem.event_params_values.copy()
    constant_values: np.ndarray = np.asarray(
        [const.value for const in problem.get_parameters_values()],
        dtype=float,
    )
    full_params: np.ndarray = np.concatenate((runtime_values, constant_values))

    Pe_var = _find_name_in_block("Pe", vsc.emt_model)
    omega_var = _find_name_in_block("omega", vsc.emt_model)
    Epk_var = _find_name_in_block("Epk", vsc.emt_model)
    assert Pe_var is not None 
    assert omega_var is not None
    assert Epk_var is not None

    Pe_idx: int = problem.get_var_idx(Pe_var)
    omega_idx: int = problem.get_var_idx(omega_var)
    Epk_idx: int = problem.get_var_idx(Epk_var)

    for time_s in np.linspace(0.0, options.simulation_time, 21):
        problem.update(float(time_s), x0.copy(), full_params)
        assert np.all(np.isfinite(full_params)), (
            f"Runtime parameters went non-finite at t={time_s}"
        )

    assert np.isfinite(float(x0[Pe_idx]))
    assert np.isfinite(float(x0[omega_idx]))
    assert np.isfinite(float(x0[Epk_idx]))
    assert abs(float(x0[omega_idx]) - 1.0) < 1.0e-6
    assert 1.0 < float(x0[Epk_idx]) < 2.0


def test_vsc_gfm_emt_dc_fed_island_full_simulate_load_step_response() -> None:
    """
    Build the DC-fed GFM island, run the full DAE simulation across a
    resistive load-step event, and verify the trajectory stays bounded
    and physically sensible: the converter phase current remains in the
    sub-pu range, ``omega`` drifts only slightly off the reference, and
    the converter active power tracks the new load level after the step.

    :return: None.
    """
    grid, vsc, load, R_A, R_B, R_C = _build_dc_fed_gfm_island()
    assert R_A is not None 
    assert R_B is not None
    assert R_C is not None

    pf_options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=False,
        retry_with_other_methods=True,
        max_iter=50,
        tolerance=1e-6,
    )
    pf_results = gce.power_flow(grid=grid, options=pf_options)
    assert pf_results.converged

    events_group: EmtEventsGroup = EmtEventsGroup(name="gfm_load_step_sim")
    grid.add_emt_events_group(events_group)
    # The system-base shunt resistance starts near 2 pu; halving it to
    # 1 pu doubles conductance and raises converter active power.
    R_step_value: float = 1.0
    event_time: float = 0.04
    for phase_R in (R_A, R_B, R_C):
        grid.add_emt_event(
            EmtEvent(
                device=load,
                parameter=phase_R,
                time=event_time,
                value=R_step_value,
                group=events_group,
            )
        )

    options: EmtOptions = EmtOptions(
        time_step=1.0e-5,  # Resolve the 10 km Bergeron line's shortest modal delay.
        simulation_time=0.10,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        verbose=0,
    )

    problem: EmtProblemDae = EmtProblemDae(
        grid=grid,
        options=options,
        pf_results_3ph=None,
        pf_results=pf_results,
    )
    problem.set_events_group(events_group)

    solver: JitSymbolicSolver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        method=options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )
    boundary_updater = cast(Any, problem)
    t, y, dy, _, _ = solver.simulate(boundary_updater=boundary_updater)

    assert np.all(np.isfinite(y)), "EMT state trajectory must remain finite"
    assert np.all(np.isfinite(dy)), "EMT derivative trajectory must remain finite"

    i_A_var = _find_name_in_block("i_A", vsc.emt_model)
    omega_var = _find_name_in_block("omega", vsc.emt_model)
    Pe_var = _find_name_in_block("Pe", vsc.emt_model)
    assert i_A_var is not None 
    assert omega_var is not None
    assert Pe_var is not None

    i_A_idx: int = problem.get_var_idx(i_A_var)
    omega_idx: int = problem.get_var_idx(omega_var)
    Pe_idx: int = problem.get_var_idx(Pe_var)

    i_A_peak: float = float(np.max(np.abs(y[:, i_A_idx])))
    assert i_A_peak < 5.0, (
        f"Converter phase current peak should stay sub-5 pu; got {i_A_peak:.3e}"
    )

    omega_trace: np.ndarray = y[:, omega_idx]
    omega_min: float = float(np.min(omega_trace))
    omega_max: float = float(np.max(omega_trace))
    assert 0.9 < omega_min and omega_max < 1.1, (
        f"omega should stay close to 1.0 pu; got range [{omega_min:.4f}, {omega_max:.4f}]"
    )

    steady_window = (t >= 0.005) & (t <= event_time - 0.005)
    pe_steady = y[steady_window, Pe_idx]
    omega_steady = y[steady_window, omega_idx]
    assert abs(float(np.mean(pe_steady)) - float(y[0, Pe_idx])) < 0.05, (
        "VSC power must stay near the PF operating point before the load step"
    )
    assert float(np.max(np.abs(omega_steady - 1.0))) < 0.005, (
        "GFM frequency must stay near nominal before the load step"
    )
    pre_window = (t > event_time - 0.01) & (t < event_time)
    post_window = t > event_time + 0.04
    pe_pre: float = float(np.mean(y[pre_window, Pe_idx]))
    pe_post: float = float(np.mean(y[post_window, Pe_idx]))
    assert np.isfinite(pe_pre)
    assert np.isfinite(pe_post)
    assert abs(pe_post) > abs(pe_pre) + 1.0e-3, (
        f"Load step (R lowered to {R_step_value:.1f} ohm) should increase the "
        f"magnitude of converter active power; pre={pe_pre:.4f}, post={pe_post:.4f}"
    )


def test_vsc_gfm_explicit_initialization_stays_at_steady_state() -> None:
    """Verify two cycles with matching balanced PF and EMT PI-line models."""
    grid, vsc, _, _, _, _ = _build_dc_fed_gfm_island(balanced_line=True)
    pf_results = gce.power_flow(grid, PowerFlowOptions(
        solver_type=SolverType.NR, tolerance=1e-10, max_iter=50,
    ))
    assert pf_results.converged
    options = EmtOptions(
        time_step=1e-5, simulation_time=0.04, tolerance=1e-8,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        init_periodic_samples=0, verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results)
    assert problem.initialization_report.final_residual_inf < 1e-8
    solver = JitSymbolicSolver(
        problem=problem, t0=0.0, t_end=options.simulation_time,
        h=options.time_step, method=options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0, verbose=False,
    )
    times, values, _, _, _ = solver.simulate(boundary_updater=problem)
    assert np.all(np.isfinite(values))
    samples_per_cycle = round(1.0 / (grid.fBase * options.time_step))
    assert len(times) >= 2 * samples_per_cycle

    for name in ("i_A", "i_B", "i_C"):
        variable = _find_name_in_block(name, vsc.emt_model)
        trace = values[:, problem.get_var_idx(variable)]
        np.testing.assert_allclose(
            trace[samples_per_cycle:], trace[:-samples_per_cycle],
            rtol=0.0, atol=1e-6, err_msg=f"{name} does not repeat after one cycle",
        )
    for name in ("Pe", "Qe", "omega", "Epk"):
        variable = _find_name_in_block(name, vsc.emt_model)
        trace = values[:, problem.get_var_idx(variable)]
        np.testing.assert_allclose(
            trace, trace[0], rtol=0.0, atol=1e-6,
            err_msg=f"{name} drifts from its initialized operating point",
        )
