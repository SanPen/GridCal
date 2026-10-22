from __future__ import annotations

import pytest

from VeraGridEngine.Utils.Symbolic.block import Block

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.switch_emt_template import get_switch_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType, SolverType, VarPowerFlowReferenceType
import VeraGridEngine.api as gce


def _get_default_emt_options() -> EmtOptions:
    return EmtOptions(
        time_step=5e-6,
        simulation_time=1.0e-3,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=0,
    )


def test_switch_emt_template_builds_uncontrolled_three_phase() -> None:
    vf = gce.MultiCircuit().var_factory
    templ = get_switch_emt_template(vf=vf, signal_controlled=False, name="switch_uncontrolled")

    assert templ.tpe == gce.DeviceType.SwitchDevice
    assert len(templ.block.in_vars) == 6
    assert len(templ.block.out_vars) == 6
    assert len(templ.block.mode_dict) == 1
    assert len(templ.block.procedural_logic) == 0


def test_switch_emt_template_builds_signal_controlled_with_command_input() -> None:
    vf = gce.MultiCircuit().var_factory
    templ = get_switch_emt_template(vf=vf, signal_controlled=True, name="switch_controlled")
    input_names = [var.name for var in templ.block.in_vars]
    mode_names = [var.name for var in templ.block.mode_dict.keys()]

    assert "switch_cmd" in input_names
    assert "switch_closed_mode" in mode_names
    assert len(templ.block.procedural_logic) == 1
    closed_mode = templ.block.external_mapping[VarPowerFlowReferenceType.switch_closed_mode]
    seed_flag = templ.block.external_mapping[VarPowerFlowReferenceType.switch_seed_from_pf]
    assert closed_mode in templ.block.mode_dict
    assert seed_flag in templ.block.event_dict
    assert closed_mode.ref == VarPowerFlowReferenceType.switch_closed_mode


@pytest.mark.parametrize("seed_from_pf,initial_closed,active,expected,nested", [
    (True, True, False, 0.0, False),
    (True, False, True, 1.0, False),
    (False, True, False, 1.0, False),
    (False, False, True, 0.0, False),
    (True, True, False, 0.0, True),
])
def test_switch_emt_problem_seeds_closed_mode_from_switch_active_state(
        seed_from_pf, initial_closed, active, expected, nested) -> None:
    grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)
    bus0 = gce.Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10.0)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    switch = gce.Switch(name="SW", bus_from=bus0, bus_to=bus1, r=1.0e-6, x=1.0e-6, active=True)
    load = gce.Load(name="load", P1=0.2, P2=0.2, P3=0.2, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.GroundedStar
    gen = gce.Generator(name="Gen", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)

    grid.add_switch(switch)
    grid.add_generator(bus=bus0, api_obj=gen)
    grid.add_load(bus=bus1, api_obj=load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    pf_options = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        generate_report=False,
    )
    power_flow = PowerFlowDriver3Ph(grid, pf_options)
    power_flow.run()
    pf_res_3ph = power_flow.results

    gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    switch_mdl = get_switch_emt_template(
        vf=grid.var_factory, signal_controlled=False, name="SW",
        seed_from_pf_active=seed_from_pf, initial_closed=initial_closed,
    ).block
    mode_var = switch_mdl.external_mapping[VarPowerFlowReferenceType.switch_closed_mode]
    seed_var = switch_mdl.external_mapping[VarPowerFlowReferenceType.switch_seed_from_pf]
    # Initialization must depend on the references, not display names.
    mode_var.name = "renamed_contact_state"
    seed_var.name = "renamed_initialization_policy"
    if nested:
        switch_mdl = Block(name="SwitchWrapper", children=[switch_mdl],
                           in_vars=switch_mdl.in_vars.copy(), out_vars=switch_mdl.out_vars.copy())
    load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

    set_emt_model(device=gen, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=switch, model=switch_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    switch.active = active
    problem = EmtProblemDae(grid=grid, options=_get_default_emt_options(), pf_results=None, pf_results_3ph=pf_res_3ph)
    runtime_idx = problem.uid2idx_event_params[mode_var.uid]

    assert float(problem.event_params_values[runtime_idx]) == expected


def test_emt_problem_tolerates_missing_optional_neutral_load_mapping() -> None:
    grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)
    bus0 = gce.Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10.0)
    switch = gce.Switch(name="SW", bus_from=bus0, bus_to=bus1, r=1.0e-6, x=1.0e-6, active=True)
    load = gce.Load(name="load", P1=0.2, P2=0.2, P3=0.2, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.GroundedStar
    gen = gce.Generator(name="Gen", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)

    grid.add_bus(bus0)
    grid.add_bus(bus1)
    grid.add_switch(switch)
    grid.add_generator(bus=bus0, api_obj=gen)
    grid.add_load(bus=bus1, api_obj=load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    pf_options = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        generate_report=False,
    )
    power_flow = PowerFlowDriver3Ph(grid, pf_options)
    power_flow.run()
    pf_res_3ph = power_flow.results

    gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    switch_mdl = get_switch_emt_template(vf=grid.var_factory, signal_controlled=False, name="SW").block
    load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block
    load_mdl.external_mapping.pop(VarPowerFlowReferenceType.i_N, None)

    set_emt_model(device=gen, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=switch, model=switch_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    problem = EmtProblemDae(grid=grid, options=_get_default_emt_options(), pf_results=None, pf_results_3ph=pf_res_3ph)

    assert problem is not None
