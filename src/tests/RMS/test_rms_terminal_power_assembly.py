# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pytest

from VeraGridEngine.api import power_flow
from VeraGridEngine.basic_structures import BoolVec, ObjVec
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import assign_static_api_object_mapping_for_device
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx_full_vectorized import (
    BackEulerImplicitIntegrationFullVec,
)
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx_vectorized import (
    BackEulerImplicitIntegrationVec,
)
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_vectorized import RmsProblemDaeVec
from VeraGridEngine.Simulations.Rms.problems.rms_problem_phasor import RmsProblemPhasor
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae_full_vectorized import (
    RmsProblemDaeFullVec,
)
from VeraGridEngine.Simulations.Rms.problems.rms_terminal_power_assembly import (
    assemble_rms_mapped_power_references,
    convert_rms_ac_power_balance_to_current_balance,
)
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import (
    get_complete_generator_template_rms,
)
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.line_phasor_rms_template import get_line_phasor_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.vsc_gfl_dclinked import build_vsc_rms
from VeraGridEngine.Templates.Rms.vsc_gfm import VscGfmBuild
from VeraGridEngine.Templates.Rms.hvdc_vsc_gfl_rms_template_v2 import build_hvdc_vsc_gfl_rms
from VeraGridEngine.Utils.Symbolic.block import Block, DynamicModelContract
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, get_expression_vars
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType, VarPowerFlowReferenceType


def test_mapped_power_assembly_uses_physical_topology() -> None:
    """Map DC and AC powers to buses without dynamic diagram connections.

    :return: None.
    """
    dc_power: Var = Var(name="Pdc")
    ac_active_power: Var = Var(name="Pac")
    ac_reactive_power: Var = Var(name="Qac")
    model: Block = Block(
        algebraic_vars=list((dc_power, ac_active_power, ac_reactive_power)),
        algebraic_eqs=list((dc_power, ac_active_power, ac_reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Pf, dc_power),
            (VarPowerFlowReferenceType.Pt, ac_active_power),
            (VarPowerFlowReferenceType.Qt, ac_reactive_power),
        )),
    )
    active_balance: ObjVec = np.zeros(2, dtype=object)
    reactive_balance: ObjVec = np.zeros(2, dtype=object)
    active_used: BoolVec = np.zeros(2, dtype=bool)
    reactive_used: BoolVec = np.zeros(2, dtype=bool)

    assemble_rms_mapped_power_references(
        model=model,
        bus_from_index=0,
        bus_to_index=1,
        bus_from_is_dc=True,
        bus_to_is_dc=False,
        active_power_balance=active_balance,
        active_power_balance_used=active_used,
        reactive_power_balance=reactive_balance,
        reactive_power_balance_used=reactive_used,
    )

    assert active_used.tolist() == [True, True]
    assert reactive_used.tolist() == [False, True]
    assert active_balance[0].eval(Pdc=0.25) == pytest.approx(-0.25)
    assert active_balance[1].eval(Pac=-0.24) == pytest.approx(0.24)
    assert reactive_balance[1].eval(Qac=0.1) == pytest.approx(-0.1)


def test_mapped_power_assembly_rejects_reactive_power_on_dc_bus_atomically() -> None:
    """Reject a domain mismatch before mutating any nodal balance.

    :return: None.
    """
    active_power: Var = Var(name="Pf")
    reactive_power: Var = Var(name="Qf")
    model: Block = Block(
        algebraic_vars=list((active_power, reactive_power)),
        algebraic_eqs=list((active_power, reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Pf, active_power),
            (VarPowerFlowReferenceType.Qf, reactive_power),
        )),
    )
    active_balance: ObjVec = np.zeros(2, dtype=object)
    reactive_balance: ObjVec = np.zeros(2, dtype=object)
    active_used: BoolVec = np.zeros(2, dtype=bool)
    reactive_used: BoolVec = np.zeros(2, dtype=bool)

    with pytest.raises(ValueError, match="reactive power on a DC bus"):
        assemble_rms_mapped_power_references(
            model=model,
            bus_from_index=0,
            bus_to_index=1,
            bus_from_is_dc=True,
            bus_to_is_dc=False,
            active_power_balance=active_balance,
            active_power_balance_used=active_used,
            reactive_power_balance=reactive_balance,
            reactive_power_balance_used=reactive_used,
        )

    assert active_used.tolist() == [False, False]
    assert reactive_used.tolist() == [False, False]


def test_single_bus_device_assembly_uses_selected_power_interface() -> None:
    """Assemble a one-terminal physical device without graphical connections.

    :return: None.
    """
    active_power: Var = Var(name="P")
    reactive_power: Var = Var(name="Q")
    model: Block = Block(
        algebraic_vars=list((active_power, reactive_power)),
        algebraic_eqs=list((active_power, reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.P, active_power),
            (VarPowerFlowReferenceType.Q, reactive_power),
        )),
    )
    active_balance: ObjVec = np.zeros(2, dtype=object)
    reactive_balance: ObjVec = np.zeros(2, dtype=object)
    active_used: BoolVec = np.zeros(2, dtype=bool)
    reactive_used: BoolVec = np.zeros(2, dtype=bool)

    assemble_rms_mapped_power_references(
        model=model,
        active_power_balance=active_balance,
        active_power_balance_used=active_used,
        reactive_power_balance=reactive_balance,
        reactive_power_balance_used=reactive_used,
        bus_index=1,
        bus_is_dc=False,
    )
    assert active_used.tolist() == [False, True]
    assert reactive_used.tolist() == [False, True]
    assert active_balance[1].eval(P=0.2) == pytest.approx(0.2)
    assert reactive_balance[1].eval(Q=-0.1) == pytest.approx(-0.1)


def test_standard_vsc_template_uses_mapped_terminal_powers() -> None:
    """Keep VSC topology separate from its mapped dynamic quantities.

    :return: None.
    """
    model: Block = build_vsc_rms(vfactory=VarFactory()).block
    assert model.out_vars == list()
    assert "rms_terminal_power_contributions" not in DynamicModelContract.__slots__
    assert VarPowerFlowReferenceType.Pf in model.external_mapping
    assert VarPowerFlowReferenceType.Pt in model.external_mapping
    assert VarPowerFlowReferenceType.Qt in model.external_mapping


def test_mapped_bus_power_requires_one_terminal_topology() -> None:
    """Reject a P/Q mapping when its static bus topology is absent."""
    active_power = Var(name="P")
    model = Block(external_mapping={VarPowerFlowReferenceType.P: active_power})

    with pytest.raises(
        ValueError,
        match="RMS bus terminal requires one-terminal device topology",
    ):
        assemble_rms_mapped_power_references(
            model=model,
            active_power_balance=np.zeros(1, dtype=object),
            active_power_balance_used=np.zeros(1, dtype=bool),
            reactive_power_balance=np.zeros(1, dtype=object),
            reactive_power_balance_used=np.zeros(1, dtype=bool),
        )


def test_mapped_to_power_requires_two_terminal_topology() -> None:
    """Reject a Pt/Qt mapping when its static to-side topology is absent."""
    active_power = Var(name="Pt")
    model = Block(external_mapping={VarPowerFlowReferenceType.Pt: active_power})

    with pytest.raises(
        ValueError,
        match="RMS to terminal requires two-terminal device topology",
    ):
        assemble_rms_mapped_power_references(
            model=model,
            active_power_balance=np.zeros(1, dtype=object),
            active_power_balance_used=np.zeros(1, dtype=bool),
            reactive_power_balance=np.zeros(1, dtype=object),
            reactive_power_balance_used=np.zeros(1, dtype=bool),
        )


def test_mapped_reactive_power_rejects_dc_topology() -> None:
    """Reject Q at a DC bus before mutating either nodal balance."""
    reactive_power = Var(name="Q")
    model = Block(external_mapping={VarPowerFlowReferenceType.Q: reactive_power})

    with pytest.raises(
        ValueError,
        match="RMS terminal declares reactive power on a DC bus",
    ):
        assemble_rms_mapped_power_references(
            model=model,
            active_power_balance=np.zeros(1, dtype=object),
            active_power_balance_used=np.zeros(1, dtype=bool),
            reactive_power_balance=np.zeros(1, dtype=object),
            reactive_power_balance_used=np.zeros(1, dtype=bool),
            bus_index=0,
            bus_is_dc=True,
        )


def test_vsc_dc_from_reactive_fallback_keeps_ac_reactive_balance() -> None:
    """A legacy VSC Qf mapping must not enter the DC nodal balance."""
    model = Block(external_mapping={
        VarPowerFlowReferenceType.Pf: Var(name="Pf"),
        VarPowerFlowReferenceType.Qf: Var(name="Qf"),
        VarPowerFlowReferenceType.Pt: Var(name="Pt"),
        VarPowerFlowReferenceType.Qt: Var(name="Qt"),
    })
    active = np.zeros(2, dtype=object)
    reactive = np.zeros(2, dtype=object)
    active_used = np.zeros(2, dtype=bool)
    reactive_used = np.zeros(2, dtype=bool)

    assemble_rms_mapped_power_references(
        model=model,
        active_power_balance=active,
        active_power_balance_used=active_used,
        reactive_power_balance=reactive,
        reactive_power_balance_used=reactive_used,
        bus_from_index=0,
        bus_to_index=1,
        bus_from_is_dc=True,
        bus_to_is_dc=False,
        ignore_dc_from_reactive=True,
    )

    assert active_used.tolist() == [True, True]
    assert reactive_used.tolist() == [False, True]


def test_mapped_power_rejects_mixed_terminal_reference_families() -> None:
    """Reject an ambiguous physical model even when topology is available."""
    model = Block(external_mapping={
        VarPowerFlowReferenceType.P: Var(name="P"),
        VarPowerFlowReferenceType.Pf: Var(name="Pf"),
    })

    with pytest.raises(
        ValueError,
        match="mixes one-terminal and two-terminal power references",
    ):
        assemble_rms_mapped_power_references(
            model=model,
            active_power_balance=np.zeros(2, dtype=object),
            active_power_balance_used=np.zeros(2, dtype=bool),
            reactive_power_balance=np.zeros(2, dtype=object),
            reactive_power_balance_used=np.zeros(2, dtype=bool),
            bus_from_index=0,
            bus_to_index=1,
            bus_from_is_dc=False,
            bus_to_is_dc=False,
        )


def test_gfm_vsc_root_exposes_only_branch_power_references() -> None:
    """Keep internal converter P/Q out of the physical VSC root mapping."""
    model = VscGfmBuild(vfactory=VarFactory()).block

    assert VarPowerFlowReferenceType.P not in model.external_mapping
    assert VarPowerFlowReferenceType.Q not in model.external_mapping
    assert VarPowerFlowReferenceType.Pf in model.external_mapping
    assert VarPowerFlowReferenceType.Qf in model.external_mapping
    assert VarPowerFlowReferenceType.Pt in model.external_mapping
    assert VarPowerFlowReferenceType.Qt in model.external_mapping


def test_hvdc_vsc_v2_declares_reactive_power_only_at_ac_terminal() -> None:
    """The DC terminal has active power but no reactive power reference."""
    model = build_hvdc_vsc_gfl_rms(vfactory=VarFactory()).block

    assert VarPowerFlowReferenceType.Pf in model.external_mapping
    assert VarPowerFlowReferenceType.Qf not in model.external_mapping
    assert VarPowerFlowReferenceType.Pt in model.external_mapping
    assert VarPowerFlowReferenceType.Qt in model.external_mapping

    active = np.zeros(2, dtype=object)
    reactive = np.zeros(2, dtype=object)
    active_used = np.zeros(2, dtype=bool)
    reactive_used = np.zeros(2, dtype=bool)
    assemble_rms_mapped_power_references(
        model=model,
        active_power_balance=active,
        active_power_balance_used=active_used,
        reactive_power_balance=reactive,
        reactive_power_balance_used=reactive_used,
        bus_from_index=0,
        bus_to_index=1,
        bus_from_is_dc=True,
        bus_to_is_dc=False,
    )
    assert active_used.tolist() == [True, True]
    assert reactive_used.tolist() == [False, True]


def build_legacy_vsc_dae_case(
        capacitive_dc_bus: bool = False,
) -> tuple[MultiCircuit, PowerFlowResults]:
    """Build one v1-style VSC case for power-balance constructors.

    :param capacitive_dc_bus: Whether the DC voltage is a capacitive state.
    :return: Grid and power-flow seed data containing a contract-free VSC.
    """
    grid: MultiCircuit = MultiCircuit()
    from_bus: Bus = Bus(name="Legacy VSC DC bus", is_dc=True)
    ac_bus: Bus = Bus(name="Legacy VSC AC bus", is_dc=False)
    grid.add_bus(obj=from_bus)
    grid.add_bus(obj=ac_bus)
    if capacitive_dc_bus:
        initialize_bus_rms(
            bus=from_bus,
            vf=grid.var_factory,
            dc_shunt_capacitance_pu_seconds=0.1,
        )
    else:
        initialize_bus_rms(bus=from_bus, vf=grid.var_factory)
    initialize_bus_rms(bus=ac_bus, vf=grid.var_factory)

    converter: VSC = VSC(
        name="Legacy VSC",
        bus_from=from_bus,
        bus_to=ac_bus,
    )
    from_active_power: Var = grid.var_factory.add_var(
        name="Pf",
        reference=VarPowerFlowReferenceType.Pf,
    )
    to_active_power: Var = grid.var_factory.add_var(
        name="Pt",
        reference=VarPowerFlowReferenceType.Pt,
    )
    to_reactive_power: Var = grid.var_factory.add_var(
        name="Qt",
        reference=VarPowerFlowReferenceType.Qt,
    )
    converter.rms_model = Block(
        algebraic_vars=list((from_active_power, to_active_power, to_reactive_power)),
        algebraic_eqs=list((
            from_active_power,
            to_active_power,
            to_reactive_power,
        )),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Pf, from_active_power),
            (VarPowerFlowReferenceType.Pt, to_active_power),
            (VarPowerFlowReferenceType.Qt, to_reactive_power),
        )),
    )
    grid.add_vsc(obj=converter)

    power_flow_results: PowerFlowResults = PowerFlowResults(
        n=2,
        m=0,
        n_hvdc=0,
        n_vsc=1,
        n_gen=0,
        n_batt=0,
        n_sh=0,
        bus_names=np.array((from_bus.name, ac_bus.name)),
        branch_names=np.array(tuple()),
        hvdc_names=np.array(tuple()),
        vsc_names=np.array((converter.name,)),
        gen_names=np.array(tuple()),
        batt_names=np.array(tuple()),
        sh_names=np.array(tuple()),
        bus_types=np.zeros(2, dtype=int),
    )
    power_flow_results.voltage = np.array((1.0 + 0.0j, 1.0 + 0.0j))
    power_flow_results.Pfp_vsc[0] = 0.20
    power_flow_results.St_vsc[0] = complex(-0.19, 0.03)
    return grid, power_flow_results


def build_legacy_vsc_current_seed_case() -> tuple[MultiCircuit, PowerFlowResults]:
    """Build a VSC case whose RMS model exposes AC current magnitude.

    :return: Grid and power-flow data with a non-unit VSC current seed.
    """
    grid: MultiCircuit
    power_flow_results: PowerFlowResults
    grid, power_flow_results = build_legacy_vsc_dae_case()
    converter: VSC = grid.get_vsc()[0]
    current_magnitude: Var = grid.var_factory.add_var(
        name="Im",
        reference=VarPowerFlowReferenceType.Im,
    )
    converter.rms_model.algebraic_vars.append(current_magnitude)
    converter.rms_model.algebraic_eqs.append(current_magnitude)
    converter.rms_model.external_mapping[
        VarPowerFlowReferenceType.Im
    ] = current_magnitude
    power_flow_results.It_vsc[0] = complex(7.5, 0.0)
    return grid, power_flow_results


def build_supported_vectorized_ac_load_case(physical_conductance: float = 0.0) -> tuple[MultiCircuit, PowerFlowResults]:
    """Build a supported square RMS case for vectorized initial projection.

    The established generator, line, and load templates provide a physical
    two-bus AC system with a converged power-flow seed. This avoids using the
    independently underdetermined legacy partial-VSC topology as an adapter
    test.

    :param physical_conductance: Total line shunt conductance in per unit.
    :return: Grid and converged power-flow results for vectorized RMS problems.
    """
    # Build the smallest established network fixture that has a voltage angle
    # reference and non-trivial network coupling.
    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    slack_bus: Bus = Bus(name="Bus0", Vnom=10.0, is_slack=True)
    load_bus: Bus = Bus(name="Bus1", Vnom=10.0)
    grid.add_bus(obj=slack_bus)
    grid.add_bus(obj=load_bus)
    initialize_bus_rms(bus=slack_bus, vf=grid.var_factory)
    initialize_bus_rms(bus=load_bus, vf=grid.var_factory)

    # Reuse the same static devices and RMS templates exercised by the
    # established RMS simulation regression.
    line: Line = Line(
        name="line 0-1",
        bus_from=slack_bus,
        bus_to=load_bus,
        r=0.029585798816568046,
        x=0.07100591715976332,
        b=0.03,
        g=physical_conductance,
        rate=900.0,
    )
    load: Load = Load(name="Load1", P=9.999999, Q=0.999999)
    generator: Generator = Generator(
        name="Gen0",
        P=10.0,
        vset=1.0,
        Snom=900.0,
        x1=0.86138701,
        r1=0.3,
        freq=50.0,
    )
    grid.add_line(obj=line)
    grid.add_load(bus=load_bus, api_obj=load)
    grid.add_generator(bus=slack_bus, api_obj=generator)

    generator_model: Block = get_complete_generator_template_rms(
        grid.var_factory
    ).block
    line_model: Block = get_line_rms_template(grid.var_factory).block
    load_model: Block = get_load_rms_template(grid.var_factory).block
    load_model.set_parameter_in_model(var_name="Pl0", new_value=-0.0999999)
    load_model.set_parameter_in_model(
        var_name="Ql0",
        new_value=-0.009999999862208533,
    )
    set_rms_model(
        device=generator,
        model=generator_model,
        var_factory=grid.var_factory,
    )
    set_rms_model(device=line, model=line_model, var_factory=grid.var_factory)
    set_rms_model(device=load, model=load_model, var_factory=grid.var_factory)

    # A real power-flow seed exercises the same initialization boundary used
    # by the driver instead of inventing algebraic values in the test.
    power_flow_results: PowerFlowResults = power_flow(grid=grid)
    return grid, power_flow_results


def test_dae_constructors_preserve_power_flow_vsc_current_base() -> None:
    """Seed every power-balance DAE with the PF VSC current base unchanged.

    :return: None.
    """
    grid: MultiCircuit
    power_flow_results: PowerFlowResults
    current_magnitude: Var
    current_index: int

    grid, power_flow_results = build_legacy_vsc_current_seed_case()
    scalar_problem: RmsProblemDae = RmsProblemDae(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    current_magnitude = grid.get_vsc()[0].rms_model.E(
        VarPowerFlowReferenceType.Im
    )
    current_index = scalar_problem._uid2idx_vars[current_magnitude.uid]
    assert scalar_problem.get_x0()[current_index] == pytest.approx(7.5)

    grid, power_flow_results = build_legacy_vsc_current_seed_case()
    vectorized_problem: RmsProblemDaeVec = RmsProblemDaeVec(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    current_magnitude = grid.get_vsc()[0].rms_model.E(
        VarPowerFlowReferenceType.Im
    )
    current_index = vectorized_problem._uid2idx_vars[current_magnitude.uid]
    assert vectorized_problem.get_x0()[current_index] == pytest.approx(7.5)

    grid, power_flow_results = build_legacy_vsc_current_seed_case()
    full_vectorized_problem: RmsProblemDaeFullVec = RmsProblemDaeFullVec(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    current_magnitude = grid.get_vsc()[0].rms_model.E(
        VarPowerFlowReferenceType.Im
    )
    current_index = full_vectorized_problem._uid2idx_vars[
        current_magnitude.uid
    ]
    assert full_vectorized_problem.get_x0()[current_index] == pytest.approx(7.5)


def test_dae_constructors_preserve_legacy_vsc_power_coupling() -> None:
    """Keep v1/custom VSC models runnable in all power-balance DAE paths.

    :return: None.
    """
    grid: MultiCircuit
    power_flow_results: PowerFlowResults
    grid, power_flow_results = build_legacy_vsc_dae_case()
    scalar_problem: RmsProblemDae = RmsProblemDae(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    assert len(scalar_problem._algebraic_eqs) > 0

    grid, power_flow_results = build_legacy_vsc_dae_case()
    vectorized_problem: RmsProblemDaeVec = RmsProblemDaeVec(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    assert len(vectorized_problem._algebraic_eqs) > 0

    grid, power_flow_results = build_legacy_vsc_dae_case()
    full_vectorized_problem: RmsProblemDaeFullVec = RmsProblemDaeFullVec(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    assert len(full_vectorized_problem._mapped_power_layout_by_model_type) == 1
    full_vectorized_problem.set_events_group(rms_events_group=RmsEventsGroup())
    assert set(full_vectorized_problem._mapped_power_layout_by_model_type.keys()).issubset(
        set(full_vectorized_problem._rhs_algeb_fn_by_types.keys())
    )
    converter: VSC = grid.get_vsc()[0]
    from_active_power: Var = converter.rms_model.E(VarPowerFlowReferenceType.Pf)
    to_active_power: Var = converter.rms_model.E(VarPowerFlowReferenceType.Pt)
    to_reactive_power: Var = converter.rms_model.E(VarPowerFlowReferenceType.Qt)
    variables: np.ndarray = full_vectorized_problem.get_x0()
    from_active_index: int = full_vectorized_problem._uid2idx_vars[from_active_power.uid]
    to_active_index: int = full_vectorized_problem._uid2idx_vars[to_active_power.uid]
    to_reactive_index: int = full_vectorized_problem._uid2idx_vars[to_reactive_power.uid]
    variables[from_active_index] = 0.20
    variables[to_active_index] = -0.19
    variables[to_reactive_index] = 0.03
    differentials: np.ndarray = np.zeros(full_vectorized_problem.get_diff_var_number())
    full_vectorized_problem.update_input_matrices_by_model(
        x=variables,
        dx=differentials,
    )
    legacy_model_type: int = next(
        iter(full_vectorized_problem._mapped_power_layout_by_model_type.keys())
    )
    class_residual: np.ndarray = full_vectorized_problem._rhs_algeb_fn_by_types[
        legacy_model_type
    ](
        full_vectorized_problem._input_matrices_by_model[legacy_model_type][0],
        full_vectorized_problem._input_matrices_by_model[legacy_model_type][1],
        full_vectorized_problem._input_matrices_by_model[legacy_model_type][2],
        full_vectorized_problem._input_matrices_by_model[legacy_model_type][3],
    )
    assert class_residual[:, 0].tolist() == pytest.approx((
        0.20,
        -0.19,
        0.03,
        -0.20,
        0.19,
        -0.03,
    ))
    residual: np.ndarray = full_vectorized_problem.rhs_algebraic_vec(
        x=variables,
        dx=differentials,
    )
    jacobian: np.ndarray = full_vectorized_problem.get_j22_vec(
        x=variables,
        dx=differentials,
        h=1.0e-3,
    ).toarray()
    generic_residual: np.ndarray = full_vectorized_problem.rhs_algebraic(
        x=variables,
        dx=differentials,
    )
    generic_jacobian: np.ndarray = full_vectorized_problem.get_j22(
        x=variables,
        dx=differentials,
        h=1.0e-3,
    ).toarray()

    assert np.array_equal(generic_residual, residual)
    assert np.array_equal(generic_jacobian, jacobian)
    assert residual[:3].tolist() == pytest.approx((0.20, -0.19, 0.03))
    assert full_vectorized_problem.Q_vec[1] == pytest.approx(-0.03)
    # The physical AC converter bus retains both Q and P nodal rows; converter
    # control equations do not replace either network balance.
    assert residual[-3:].tolist() == pytest.approx((-0.20, -0.03, 0.19))
    assert jacobian[-3, from_active_index] == pytest.approx(-1.0)
    assert jacobian[-2, to_reactive_index] == pytest.approx(-1.0)
    assert jacobian[-1, to_active_index] == pytest.approx(-1.0)


def test_vectorized_integrators_use_supported_initial_projection() -> None:
    """Exercise the shared algebraic projector through both vectorized solvers.

    A zero-macro-step run isolates initialization and cleanup while still
    dispatching the real ``rhs_algebraic`` projection interface selected by
    each solver.

    :return: None.
    """
    partial_grid: MultiCircuit
    partial_power_flow_results: PowerFlowResults
    partial_grid, partial_power_flow_results = (
        build_supported_vectorized_ac_load_case()
    )
    assert partial_power_flow_results.converged
    partial_problem: RmsProblemDaeVec = RmsProblemDaeVec(
        grid=partial_grid,
        options=RmsOptions(),
        pf_results=partial_power_flow_results,
    )
    partial_problem.set_events_group(rms_events_group=RmsEventsGroup())

    # Compare the generic projection boundary with the established vectorized
    # owner on the same gathered non-trivial operating point.
    partial_variables: np.ndarray = partial_problem.get_x0()
    partial_differentials: np.ndarray = partial_problem.get_dx0()
    partial_problem.update_input_matrices_by_model(
        x=partial_variables,
        dx=partial_differentials,
    )
    partial_vectorized_residual: np.ndarray = partial_problem.rhs_algebraic_vec(
        x=partial_variables,
        dx=partial_differentials,
    )
    partial_vectorized_jacobian: np.ndarray = partial_problem.get_j22_vec(
        x=partial_variables,
        dx=partial_differentials,
        h=1.0e-3,
    ).toarray()
    partial_generic_residual: np.ndarray = partial_problem.rhs_algebraic(
        x=partial_variables,
        dx=partial_differentials,
    )
    partial_generic_jacobian: np.ndarray = partial_problem.get_j22(
        x=partial_variables,
        dx=partial_differentials,
        h=1.0e-3,
    ).toarray()
    assert np.array_equal(partial_generic_residual, partial_vectorized_residual)
    assert np.array_equal(partial_generic_jacobian, partial_vectorized_jacobian)
    assert np.any(np.abs(partial_vectorized_jacobian) > 0.0)

    partial_solver: BackEulerImplicitIntegrationVec = (
        BackEulerImplicitIntegrationVec(
            problem=partial_problem,
            t0=0.0,
            t_end=0.0,
            h=1.0e-3,
            max_iter=25,
        )
    )
    partial_times: np.ndarray
    partial_values: np.ndarray
    partial_well_initialized: bool
    partial_converged: bool
    (
        partial_times,
        partial_values,
        partial_well_initialized,
        partial_converged,
    ) = partial_solver.simulate()

    assert partial_times.tolist() == pytest.approx((0.0,))
    assert partial_values.shape == (1, partial_problem.get_all_vars_number())
    assert np.all(np.isfinite(partial_values))
    assert partial_well_initialized
    assert not partial_converged

    full_grid: MultiCircuit
    full_power_flow_results: PowerFlowResults
    full_grid, full_power_flow_results = build_supported_vectorized_ac_load_case()
    assert full_power_flow_results.converged
    full_problem: RmsProblemDaeFullVec = RmsProblemDaeFullVec(
        grid=full_grid,
        options=RmsOptions(),
        pf_results=full_power_flow_results,
    )
    full_problem.set_events_group(rms_events_group=RmsEventsGroup())
    full_solver: BackEulerImplicitIntegrationFullVec = (
        BackEulerImplicitIntegrationFullVec(
            problem=full_problem,
            t0=0.0,
            t_end=0.0,
            h=1.0e-3,
            max_iter=25,
        )
    )
    full_times: np.ndarray
    full_values: np.ndarray
    full_well_initialized: bool
    full_converged: bool
    (
        full_times,
        full_values,
        full_well_initialized,
        full_converged,
    ) = full_solver.simulate()

    assert full_times.tolist() == pytest.approx((0.0,))
    assert full_values.shape == (1, full_problem.get_all_vars_number())
    assert np.all(np.isfinite(full_values))
    assert full_well_initialized
    assert not full_converged


def test_full_vectorized_capacitive_dc_nodal_layout_matches_jacobian() -> None:
    """Evaluate the exact ``P_bus - P_network`` row and its full Jacobian.

    :return: None.
    """
    grid: MultiCircuit
    power_flow_results: PowerFlowResults
    grid, power_flow_results = build_legacy_vsc_dae_case(capacitive_dc_bus=True)
    problem: RmsProblemDaeFullVec = RmsProblemDaeFullVec(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    problem.set_events_group(rms_events_group=RmsEventsGroup())

    converter: VSC = grid.get_vsc()[0]
    from_active_power: Var = converter.rms_model.E(VarPowerFlowReferenceType.Pf)
    to_active_power: Var = converter.rms_model.E(VarPowerFlowReferenceType.Pt)
    to_reactive_power: Var = converter.rms_model.E(VarPowerFlowReferenceType.Qt)
    local_dc_power: Var = grid.buses[0].rms_model.E(VarPowerFlowReferenceType.P)
    variables: np.ndarray = problem.get_x0()
    variables[problem._uid2idx_vars[from_active_power.uid]] = 0.20
    variables[problem._uid2idx_vars[to_active_power.uid]] = -0.19
    variables[problem._uid2idx_vars[to_reactive_power.uid]] = 0.03
    variables[problem._uid2idx_vars[local_dc_power.uid]] = 0.05
    differentials: np.ndarray = np.zeros(problem.get_diff_var_number())
    problem.update_input_matrices_by_model(x=variables, dx=differentials)
    residual: np.ndarray = problem.rhs_algebraic_vec(
        x=variables,
        dx=differentials,
    )
    analytic_jacobian: np.ndarray = np.hstack((
        problem.get_j21_vec(x=variables, dx=differentials, h=1.0e-3).toarray(),
        problem.get_j22_vec(x=variables, dx=differentials, h=1.0e-3).toarray(),
    ))

    finite_difference_jacobian: np.ndarray = np.zeros_like(analytic_jacobian)
    perturbation: float = 1.0e-7
    column_index: int = 0
    while column_index < len(variables):
        variables_plus: np.ndarray = variables.copy()
        variables_minus: np.ndarray = variables.copy()
        variables_plus[column_index] += perturbation
        variables_minus[column_index] -= perturbation
        problem.update_input_matrices_by_model(
            x=variables_plus,
            dx=differentials,
        )
        residual_plus: np.ndarray = problem.rhs_algebraic_vec(
            x=variables_plus,
            dx=differentials,
        )
        problem.update_input_matrices_by_model(
            x=variables_minus,
            dx=differentials,
        )
        residual_minus: np.ndarray = problem.rhs_algebraic_vec(
            x=variables_minus,
            dx=differentials,
        )
        finite_difference_jacobian[:, column_index] = (
            residual_plus - residual_minus
        ) / (2.0 * perturbation)
        column_index += 1

    # A capacitive DC bus contributes its local P balance, while the physical
    # AC terminal independently retains both reactive and active nodal rows.
    assert residual[-3:].tolist() == pytest.approx((0.25, -0.03, 0.19))
    assert np.allclose(
        analytic_jacobian,
        finite_difference_jacobian,
        rtol=1.0e-7,
        atol=1.0e-8,
    )


def test_full_vectorized_rejects_isolated_bus_before_runtime_layout() -> None:
    """Fail closed instead of inventing runtime rows for an isolated bus.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    bus: Bus = Bus(name="Isolated AC bus", is_dc=False)
    grid.add_bus(obj=bus)
    initialize_bus_rms(bus=bus, vf=grid.var_factory)
    power_flow_results: PowerFlowResults = PowerFlowResults(
        n=1,
        m=0,
        n_hvdc=0,
        n_vsc=0,
        n_gen=0,
        n_batt=0,
        n_sh=0,
        bus_names=np.array((bus.name,)),
        branch_names=np.array(tuple()),
        hvdc_names=np.array(tuple()),
        vsc_names=np.array(tuple()),
        gen_names=np.array(tuple()),
        batt_names=np.array(tuple()),
        sh_names=np.array(tuple()),
        bus_types=np.zeros(1, dtype=int),
    )
    power_flow_results.voltage = np.array((1.0 + 0.0j,))

    with pytest.raises(ValueError, match="Isolated RMS bus"):
        RmsProblemDaeFullVec(
            grid=grid,
            options=RmsOptions(),
            pf_results=power_flow_results,
        )


def test_phasor_constructor_preserves_legacy_vsc_power_coupling() -> None:
    """Keep a v1/custom VSC coupled through its historical power references.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    dc_bus: Bus = Bus(name="Legacy phasor DC bus", is_dc=True)
    ac_bus: Bus = Bus(name="Legacy phasor AC bus", is_dc=False)
    grid.add_bus(obj=dc_bus)
    grid.add_bus(obj=ac_bus)

    dc_voltage: Var = grid.var_factory.add_var(
        name="Vdc_legacy",
        reference=VarPowerFlowReferenceType.Vdc,
    )
    dc_bus.rms_model = Block(
        algebraic_vars=list((dc_voltage,)),
        external_mapping=dict(((VarPowerFlowReferenceType.Vdc, dc_voltage),)),
    )
    voltage_real: Var = grid.var_factory.add_var(
        name="Vr_legacy",
        reference=VarPowerFlowReferenceType.Vr,
    )
    voltage_imaginary: Var = grid.var_factory.add_var(
        name="Vi_legacy",
        reference=VarPowerFlowReferenceType.Vi,
    )
    ac_bus.rms_model = Block(
        algebraic_vars=list((voltage_real, voltage_imaginary)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Vr, voltage_real),
            (VarPowerFlowReferenceType.Vi, voltage_imaginary),
        )),
    )

    from_active_power: Var = grid.var_factory.add_var(name="Pf_legacy")
    to_active_power: Var = grid.var_factory.add_var(name="Pt_legacy")
    to_reactive_power: Var = grid.var_factory.add_var(name="Qt_legacy")
    legacy_model: Block = Block(
        algebraic_vars=list((from_active_power, to_active_power, to_reactive_power)),
        algebraic_eqs=list((from_active_power, to_active_power, to_reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Pf, from_active_power),
            (VarPowerFlowReferenceType.Pt, to_active_power),
            (VarPowerFlowReferenceType.Qt, to_reactive_power),
        )),
    )
    converter: VSC = VSC(
        name="Legacy phasor VSC",
        bus_from=dc_bus,
        bus_to=ac_bus,
    )
    converter.rms_model = legacy_model
    grid.add_vsc(obj=converter)

    power_flow_results: PowerFlowResults = PowerFlowResults(
        n=2,
        m=0,
        n_hvdc=0,
        n_vsc=1,
        n_gen=0,
        n_batt=0,
        n_sh=0,
        bus_names=np.array((dc_bus.name, ac_bus.name)),
        branch_names=np.array(tuple()),
        hvdc_names=np.array(tuple()),
        vsc_names=np.array((converter.name,)),
        gen_names=np.array(tuple()),
        batt_names=np.array(tuple()),
        sh_names=np.array(tuple()),
        bus_types=np.zeros(2, dtype=int),
    )
    power_flow_results.voltage = np.array((1.0 + 0.0j, 0.8 + 0.6j))
    power_flow_results.Pfp_vsc[0] = 0.20
    power_flow_results.St_vsc[0] = complex(-0.19, 0.03)

    problem: RmsProblemPhasor = RmsProblemPhasor(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    nodal_equations: list[Expr] = problem._algebraic_eqs[-3:]
    dc_names: set[str] = set(
        variable.name for variable in get_expression_vars(nodal_equations[0])
    )
    ac_real_names: set[str] = set(
        variable.name for variable in get_expression_vars(nodal_equations[1])
    )
    ac_imaginary_names: set[str] = set(
        variable.name for variable in get_expression_vars(nodal_equations[2])
    )

    assert dc_names == set(("Pf_legacy",))
    assert ac_real_names == set(("Pt_legacy", "Qt_legacy", "Vr_legacy", "Vi_legacy"))
    assert ac_imaginary_names == set(("Pt_legacy", "Qt_legacy", "Vr_legacy", "Vi_legacy"))


def test_full_vectorized_runtime_keeps_device_and_terminal_rows_separate() -> None:
    """Evaluate selected one-terminal powers through the compiled RMS runtime.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    bus: Bus = Bus(name="Vectorized AC bus", is_dc=False)
    grid.add_bus(obj=bus)
    initialize_bus_rms(bus=bus, vf=grid.var_factory)

    first_active_power: Var = grid.var_factory.add_var(name="P_selected")
    first_reactive_power: Var = grid.var_factory.add_var(name="Q_selected")
    first_model: Block = Block(
        algebraic_vars=list((first_active_power, first_reactive_power)),
        algebraic_eqs=list((first_active_power, first_reactive_power)),
        out_vars=list(),
        external_mapping=dict((
            (VarPowerFlowReferenceType.P, first_active_power),
            (VarPowerFlowReferenceType.Q, first_reactive_power),
        )),
    )
    first_load: Load = Load(name="First selected power")
    first_load.rms_model = first_model
    grid.add_load(bus=bus, api_obj=first_load)

    second_active_power: Var = grid.var_factory.add_var(name="P_selected")
    second_reactive_power: Var = grid.var_factory.add_var(name="Q_selected")
    second_model: Block = Block(
        algebraic_vars=list((second_active_power, second_reactive_power)),
        algebraic_eqs=list((second_active_power, second_reactive_power)),
        out_vars=list(),
        external_mapping=dict((
            (VarPowerFlowReferenceType.P, second_active_power),
            (VarPowerFlowReferenceType.Q, second_reactive_power),
        )),
    )
    second_load: Load = Load(name="Second selected power")
    second_load.rms_model = second_model
    grid.add_load(bus=bus, api_obj=second_load)

    power_flow_results: PowerFlowResults = PowerFlowResults(
        n=1,
        m=0,
        n_hvdc=0,
        n_vsc=0,
        n_gen=0,
        n_batt=0,
        n_sh=0,
        bus_names=np.array((bus.name,)),
        branch_names=np.array(tuple()),
        hvdc_names=np.array(tuple()),
        vsc_names=np.array(tuple()),
        gen_names=np.array(tuple()),
        batt_names=np.array(tuple()),
        sh_names=np.array(tuple()),
        bus_types=np.zeros(1, dtype=int),
    )
    power_flow_results.voltage = np.array((1.0 + 0.0j,))
    problem: RmsProblemDaeFullVec = RmsProblemDaeFullVec(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    problem.set_events_group(rms_events_group=RmsEventsGroup())
    variables: np.ndarray = problem.get_x0()
    variables[problem._uid2idx_vars[first_active_power.uid]] = 0.10
    variables[problem._uid2idx_vars[first_reactive_power.uid]] = 0.20
    variables[problem._uid2idx_vars[second_active_power.uid]] = -0.03
    variables[problem._uid2idx_vars[second_reactive_power.uid]] = 0.04
    differentials: np.ndarray = np.zeros(problem.get_diff_var_number())
    problem.update_input_matrices_by_model(x=variables, dx=differentials)
    residual: np.ndarray = problem.rhs_algebraic_vec(
        x=variables,
        dx=differentials,
    )

    first_start: int = problem._model_algebraic_eq_start_idx[first_model.uid]
    second_start: int = problem._model_algebraic_eq_start_idx[second_model.uid]
    assert len(problem._mapped_power_layout_by_model_type) == 1
    assert residual[first_start] == pytest.approx(0.10)
    assert residual[first_start + 1] == pytest.approx(0.20)
    assert residual[second_start] == pytest.approx(-0.03)
    assert residual[second_start + 1] == pytest.approx(0.04)
    assert residual[-2] == pytest.approx(0.24)
    assert residual[-1] == pytest.approx(0.07)

    analytic_jacobian: np.ndarray = problem.get_j22_vec(
        x=variables,
        dx=differentials,
        h=1.0e-3,
    ).toarray()
    finite_difference_jacobian: np.ndarray = np.zeros_like(analytic_jacobian)
    perturbation: float = 1.0e-7
    column_index: int = 0
    while column_index < problem.get_algebraic_var_number():
        variables_plus: np.ndarray = variables.copy()
        variables_minus: np.ndarray = variables.copy()
        variables_plus[column_index] += perturbation
        variables_minus[column_index] -= perturbation
        problem.update_input_matrices_by_model(
            x=variables_plus,
            dx=differentials,
        )
        residual_plus: np.ndarray = problem.rhs_algebraic_vec(
            x=variables_plus,
            dx=differentials,
        )
        problem.update_input_matrices_by_model(
            x=variables_minus,
            dx=differentials,
        )
        residual_minus: np.ndarray = problem.rhs_algebraic_vec(
            x=variables_minus,
            dx=differentials,
        )
        finite_difference_jacobian[:, column_index] = (
            residual_plus - residual_minus
        ) / (2.0 * perturbation)
        column_index += 1

    assert np.allclose(
        analytic_jacobian,
        finite_difference_jacobian,
        rtol=1.0e-7,
        atol=1.0e-8,
    )


def build_mixed_terminal_contract_grid(
        contract_first: bool,
) -> tuple[MultiCircuit, PowerFlowResults]:
    """Build two equivalent loads with inconsistent network-interface modes.

    :param contract_first: Whether the typed-contract instance is added first.
    :return: Grid and power-flow seed data for the full-vectorized constructor.
    """
    grid: MultiCircuit = MultiCircuit()
    bus: Bus = Bus(name="Mixed-contract AC bus", is_dc=False)
    grid.add_bus(obj=bus)
    initialize_bus_rms(bus=bus, vf=grid.var_factory)

    typed_active_power: Var = grid.var_factory.add_var(name="P_mixed")
    typed_reactive_power: Var = grid.var_factory.add_var(name="Q_mixed")
    typed_model: Block = Block(
        algebraic_vars=list((typed_active_power, typed_reactive_power)),
        algebraic_eqs=list((typed_active_power, typed_reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.P, typed_active_power),
            (VarPowerFlowReferenceType.Q, typed_reactive_power),
        )),
    )
    typed_load: Load = Load(name="Typed equivalent load")
    typed_load.rms_model = typed_model

    legacy_active_power: Var = grid.var_factory.add_var(name="P_mixed")
    legacy_reactive_power: Var = grid.var_factory.add_var(name="Q_mixed")
    legacy_model: Block = Block(
        algebraic_vars=list((legacy_active_power, legacy_reactive_power)),
        algebraic_eqs=list((legacy_active_power, legacy_reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.P, legacy_active_power),
            (VarPowerFlowReferenceType.Q, legacy_reactive_power),
        )),
    )
    legacy_load: Load = Load(name="Legacy equivalent load")
    legacy_load.rms_model = legacy_model

    if contract_first:
        grid.add_load(bus=bus, api_obj=typed_load)
        grid.add_load(bus=bus, api_obj=legacy_load)
    else:
        grid.add_load(bus=bus, api_obj=legacy_load)
        grid.add_load(bus=bus, api_obj=typed_load)

    power_flow_results: PowerFlowResults = PowerFlowResults(
        n=1,
        m=0,
        n_hvdc=0,
        n_vsc=0,
        n_gen=0,
        n_batt=0,
        n_sh=0,
        bus_names=np.array((bus.name,)),
        branch_names=np.array(tuple()),
        hvdc_names=np.array(tuple()),
        vsc_names=np.array(tuple()),
        gen_names=np.array(tuple()),
        batt_names=np.array(tuple()),
        sh_names=np.array(tuple()),
        bus_types=np.zeros(1, dtype=int),
    )
    power_flow_results.voltage = np.array((1.0 + 0.0j,))
    return grid, power_flow_results


def test_full_vectorized_ignores_persisted_contract_on_representative() -> None:
    """Compile equivalent mappings independently of persisted old metadata.

    :return: None.
    """
    grid: MultiCircuit
    power_flow_results: PowerFlowResults
    grid, power_flow_results = build_mixed_terminal_contract_grid(contract_first=True)

    problem = RmsProblemDaeFullVec(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    assert len(problem._mapped_power_layout_by_model_type) == 1


def test_full_vectorized_ignores_persisted_contract_on_member() -> None:
    """Compile equivalent mappings when only a member has old metadata.

    :return: None.
    """
    grid: MultiCircuit
    power_flow_results: PowerFlowResults
    grid, power_flow_results = build_mixed_terminal_contract_grid(contract_first=False)

    problem = RmsProblemDaeFullVec(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )
    assert len(problem._mapped_power_layout_by_model_type) == 1


def test_phasor_balance_consumes_vsc_mapped_power_references() -> None:
    """Convert mapped VSC terminal powers into the phasor AC KCL residual.

    :return: None.
    """
    dc_power: Var = Var(name="Pdc")
    ac_active_power: Var = Var(name="Pac")
    ac_reactive_power: Var = Var(name="Qac")
    voltage_real: Var = Var(name="Vr")
    voltage_imaginary: Var = Var(name="Vi")
    model: Block = Block(
        algebraic_vars=list((dc_power, ac_active_power, ac_reactive_power)),
        algebraic_eqs=list((dc_power, ac_active_power, ac_reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Pf, dc_power),
            (VarPowerFlowReferenceType.Pt, ac_active_power),
            (VarPowerFlowReferenceType.Qt, ac_reactive_power),
        )),
    )
    active_balance: ObjVec = np.zeros(2, dtype=object)
    reactive_balance: ObjVec = np.zeros(2, dtype=object)
    real_current_balance: ObjVec = np.zeros(2, dtype=object)
    imaginary_current_balance: ObjVec = np.zeros(2, dtype=object)
    active_used: BoolVec = np.zeros(2, dtype=bool)
    reactive_used: BoolVec = np.zeros(2, dtype=bool)
    real_current_used: BoolVec = np.zeros(2, dtype=bool)
    imaginary_current_used: BoolVec = np.zeros(2, dtype=bool)

    # Assemble by physical VSC topology first, as each RMS problem does.
    assemble_rms_mapped_power_references(
        model=model,
        bus_from_index=0,
        bus_to_index=1,
        bus_from_is_dc=True,
        bus_to_is_dc=False,
        active_power_balance=active_balance,
        active_power_balance_used=active_used,
        reactive_power_balance=reactive_balance,
        reactive_power_balance_used=reactive_used,
    )
    # The phasor formulation must then consume the AC power entry in its KCL
    # arrays while retaining the DC active-power equation at the other bus.
    convert_rms_ac_power_balance_to_current_balance(
        bus_index=1,
        voltage_real=voltage_real,
        voltage_imaginary=voltage_imaginary,
        active_power_balance=active_balance,
        active_power_balance_used=active_used,
        reactive_power_balance=reactive_balance,
        reactive_power_balance_used=reactive_used,
        real_current_balance=real_current_balance,
        real_current_balance_used=real_current_used,
        imaginary_current_balance=imaginary_current_balance,
        imaginary_current_balance_used=imaginary_current_used,
    )

    assert active_balance[0].eval(Pdc=0.25) == pytest.approx(-0.25)
    assert real_current_used.tolist() == [False, True]
    assert imaginary_current_used.tolist() == [False, True]
    assert real_current_balance[1].eval(
        Pac=-0.24,
        Qac=0.10,
        Vr=0.8,
        Vi=0.6,
    ) == pytest.approx(0.132)
    assert imaginary_current_balance[1].eval(
        Pac=-0.24,
        Qac=0.10,
        Vr=0.8,
        Vi=0.6,
    ) == pytest.approx(0.224)


def test_phasor_problem_emits_vsc_dc_and_ac_nodal_residuals() -> None:
    """Build the phasor problem and inspect its topology-owned VSC residuals.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    dc_bus: Bus = Bus(name="DC bus", is_dc=True)
    ac_bus: Bus = Bus(name="AC bus", is_dc=False)
    grid.add_bus(obj=dc_bus)
    grid.add_bus(obj=ac_bus)

    # Give each physical bus only its canonical phasor voltage coordinates so
    # the problem constructor must provide the network balance equations.
    dc_voltage: Var = grid.var_factory.add_var(
        name="Vdc",
        reference=VarPowerFlowReferenceType.Vdc,
    )
    dc_bus.rms_model = Block(
        algebraic_vars=list((dc_voltage,)),
        out_vars=list((dc_voltage,)),
        external_mapping=dict(((VarPowerFlowReferenceType.Vdc, dc_voltage),)),
    )
    voltage_real: Var = grid.var_factory.add_var(
        name="Vr",
        reference=VarPowerFlowReferenceType.Vr,
    )
    voltage_imaginary: Var = grid.var_factory.add_var(
        name="Vi",
        reference=VarPowerFlowReferenceType.Vi,
    )
    ac_bus.rms_model = Block(
        algebraic_vars=list((voltage_real, voltage_imaginary)),
        out_vars=list((voltage_real, voltage_imaginary)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Vr, voltage_real),
            (VarPowerFlowReferenceType.Vi, voltage_imaginary),
        )),
    )

    # The VSC owns only its device equations and typed terminal contract. Its
    # physical bus_from/bus_to topology determines where the network terms go.
    dc_power: Var = grid.var_factory.add_var(name="Pf")
    ac_active_power: Var = grid.var_factory.add_var(name="Pt")
    ac_reactive_power: Var = grid.var_factory.add_var(name="Qt")
    vsc_model: Block = Block(
        algebraic_vars=list((dc_power, ac_active_power, ac_reactive_power)),
        algebraic_eqs=list((dc_power, ac_active_power, ac_reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Pf, dc_power),
            (VarPowerFlowReferenceType.Pt, ac_active_power),
            (VarPowerFlowReferenceType.Qt, ac_reactive_power),
        )),
    )
    converter: VSC = VSC(
        name="DC-AC VSC",
        bus_from=dc_bus,
        bus_to=ac_bus,
    )
    converter.rms_model = vsc_model
    grid.add_vsc(obj=converter)

    # Add a pre-existing AC current injection to prove that terminal-power
    # conversion augments the KCL arrays instead of replacing their contents.
    existing_real_current: Var = grid.var_factory.add_var(name="Ir_existing")
    existing_imaginary_current: Var = grid.var_factory.add_var(name="Ii_existing")
    current_model: Block = Block(
        algebraic_vars=list((existing_real_current, existing_imaginary_current)),
        algebraic_eqs=list((existing_real_current, existing_imaginary_current)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.Ir, existing_real_current),
            (VarPowerFlowReferenceType.Ii, existing_imaginary_current),
        )),
    )
    current_injection: Load = Load(name="Existing current")
    current_injection.rms_model = current_model
    grid.add_load(bus=ac_bus, api_obj=current_injection)

    # A second one-terminal physical device selects P/Q as its hidden network
    # interface. It has no graphical root ports, yet the assembler must include
    # it automatically through the same physical AC bus topology.
    selected_active_power: Var = grid.var_factory.add_var(name="P_selected")
    selected_reactive_power: Var = grid.var_factory.add_var(name="Q_selected")
    selected_power_model: Block = Block(
        algebraic_vars=list((selected_active_power, selected_reactive_power)),
        algebraic_eqs=list((selected_active_power, selected_reactive_power)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.P, selected_active_power),
            (VarPowerFlowReferenceType.Q, selected_reactive_power),
        )),
    )
    selected_power_injection: Load = Load(name="Selected power")
    selected_power_injection.rms_model = selected_power_model
    grid.add_load(bus=ac_bus, api_obj=selected_power_injection)

    power_flow_results: PowerFlowResults = PowerFlowResults(
        n=2,
        m=0,
        n_hvdc=0,
        n_vsc=1,
        n_gen=0,
        n_batt=0,
        n_sh=0,
        bus_names=np.array((dc_bus.name, ac_bus.name)),
        branch_names=np.array(tuple()),
        hvdc_names=np.array(tuple()),
        vsc_names=np.array((converter.name,)),
        gen_names=np.array(tuple()),
        batt_names=np.array(tuple()),
        sh_names=np.array(tuple()),
        bus_types=np.zeros(2, dtype=int),
    )
    power_flow_results.voltage = np.array((1.0 + 0.0j, 0.8 + 0.6j))
    power_flow_results.Pfp_vsc[0] = 0.25
    power_flow_results.Pfn_vsc[0] = 0.0
    power_flow_results.St_vsc[0] = complex(-0.24, 0.10)

    problem: RmsProblemPhasor = RmsProblemPhasor(
        grid=grid,
        options=RmsOptions(),
        pf_results=power_flow_results,
    )

    # Seven device equations precede the final topology-owned residuals. The
    # two-bus network must end in one DC and two AC current equations.
    nodal_equations: list[Expr] = problem._algebraic_eqs[-3:]
    dc_variable_names: set[str] = set(
        variable.name for variable in get_expression_vars(nodal_equations[0])
    )
    ac_real_variable_names: set[str] = set(
        variable.name for variable in get_expression_vars(nodal_equations[1])
    )
    ac_imaginary_variable_names: set[str] = set(
        variable.name for variable in get_expression_vars(nodal_equations[2])
    )

    assert len(problem._algebraic_eqs) == 10
    assert dc_variable_names == set(("Pf",))
    assert ac_real_variable_names == set((
        "Pt", "Qt", "Vr", "Vi", "Ir_existing", "P_selected", "Q_selected",
    ))
    assert ac_imaginary_variable_names == set((
        "Pt", "Qt", "Vr", "Vi", "Ii_existing", "P_selected", "Q_selected",
    ))
    assert nodal_equations[0].eval(Pf=0.25) == pytest.approx(-0.25)
    assert nodal_equations[1].eval(
        Pt=-0.24,
        Qt=0.10,
        Vr=0.8,
        Vi=0.6,
        Ir_existing=0.05,
        P_selected=0.04,
        Q_selected=-0.02,
    ) == pytest.approx(0.202)
    assert nodal_equations[2].eval(
        Pt=-0.24,
        Qt=0.10,
        Vr=0.8,
        Vi=0.6,
        Ii_existing=-0.03,
        P_selected=0.04,
        Q_selected=-0.02,
    ) == pytest.approx(0.234)


def test_rms_line_physical_shunt_power() -> None:
    """Compare mapped polar line powers with an independent pi primitive.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0)
    source: Bus = grid.add_bus(Bus(name="source", Vnom=132.0))
    target: Bus = grid.add_bus(Bus(name="target", Vnom=132.0))
    line: Line = Line(bus_from=source, bus_to=target, r=0.01, x=0.1, b=0.002, g=0.003)
    grid.add_line(line)
    model: Block = get_line_rms_template(grid.var_factory).block
    physical_block: Block = model.children[0]
    mapped_values: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(
        grid=grid, device=line, mdl=model, problem_mapping=mapped_values, logger=None,
    )
    from_voltage: complex = 1.03 * np.exp(0.13j)
    to_voltage: complex = 0.96 * np.exp(-0.08j)
    series_admittance: complex = 1.0 / complex(line.R, line.X)
    half_shunt: complex = complex(line.G, line.B) / 2.0
    from_current: complex = series_admittance * (from_voltage - to_voltage) + half_shunt * from_voltage
    to_current: complex = series_admittance * (to_voltage - from_voltage) + half_shunt * to_voltage
    from_power: complex = from_voltage * np.conj(from_current)
    to_power: complex = to_voltage * np.conj(to_current)
    bindings: dict[int, float] = dict()
    parameter: Var
    value: Const
    for parameter, value in physical_block.parameters.items():
        assert value.value is not None
        bindings[parameter.uid] = float(value.value)
    for parameter, value in mapped_values.items():
        assert value.value is not None
        bindings[parameter.uid] = float(value.value)
    variable: Var
    for variable in physical_block.algebraic_vars:
        bindings[variable.uid] = 0.0
    bindings[model.external_mapping[VarPowerFlowReferenceType.Vmf].uid] = abs(from_voltage)
    bindings[model.external_mapping[VarPowerFlowReferenceType.Vaf].uid] = float(np.angle(from_voltage))
    bindings[model.external_mapping[VarPowerFlowReferenceType.Vmt].uid] = abs(to_voltage)
    bindings[model.external_mapping[VarPowerFlowReferenceType.Vat].uid] = float(np.angle(to_voltage))
    status: float
    for status in (0.0, 1.0):
        # Both physical half-shunts follow the existing retained conduction status.
        for parameter in physical_block.event_dict:
            bindings[parameter.uid] = status
        expected: np.ndarray = status * np.array(
            (from_power.real, from_power.imag, to_power.real, to_power.imag), dtype=float,
        )
        actual: np.ndarray = np.zeros(4, dtype=float)
        equation_index: int
        for equation_index in range(4):
            actual[equation_index] = -float(physical_block.algebraic_eqs[equation_index].eval_uid(bindings))
        np.testing.assert_allclose(actual, expected, rtol=1.0e-10, atol=1.0e-12)


    # Exercise the actual DAE assembly and projection with the same nonzero G.
    pf_results: PowerFlowResults
    grid, pf_results = build_supported_vectorized_ac_load_case(physical_conductance=0.003)
    assert pf_results.converged
    problem: RmsProblemDaeVec = RmsProblemDaeVec(
        grid=grid, options=RmsOptions(), pf_results=pf_results,
    )
    problem.set_events_group(rms_events_group=RmsEventsGroup())
    solver: BackEulerImplicitIntegrationVec = BackEulerImplicitIntegrationVec(
        problem=problem, t0=0.0, t_end=0.0, h=1.0e-3, max_iter=25,
    )
    times: np.ndarray
    values: np.ndarray
    initialized: bool
    converged: bool
    times, values, initialized, converged = solver.simulate()
    assert initialized
    problem.update_input_matrices_by_model(x=values[0], dx=problem.get_dx0())
    assert np.linalg.norm(problem.rhs_algebraic_vec(x=values[0], dx=problem.get_dx0()), ord=np.inf) < 1.0e-6
    line = grid.lines[0]
    from_voltage = pf_results.voltage[0]
    to_voltage = pf_results.voltage[1]
    from_current = (from_voltage - to_voltage) / complex(line.R, line.X) + complex(line.G, line.B) * from_voltage / 2.0
    to_current = (to_voltage - from_voltage) / complex(line.R, line.X) + complex(line.G, line.B) * to_voltage / 2.0
    expected_power: np.ndarray = np.array((
        (from_voltage * np.conj(from_current)).real, (from_voltage * np.conj(from_current)).imag,
        (to_voltage * np.conj(to_current)).real, (to_voltage * np.conj(to_current)).imag,
    ))
    power_refs: tuple[VarPowerFlowReferenceType, ...] = (
        VarPowerFlowReferenceType.Pf, VarPowerFlowReferenceType.Qf,
        VarPowerFlowReferenceType.Pt, VarPowerFlowReferenceType.Qt,
    )
    actual_power: np.ndarray = np.array(tuple(
        values[0, problem._uid2idx_vars[line.rms_model.E(reference).uid]] for reference in power_refs
    ))
    np.testing.assert_allclose(actual_power, expected_power, rtol=1.0e-6, atol=1.0e-6)


def test_rms_phasor_line_physical_shunt_current() -> None:
    """Preserve physical shunt currents and virtual-tap scaling in the phasor model.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=2.0)
    source: Bus = grid.add_bus(Bus(Vnom=20.0))
    target: Bus = grid.add_bus(Bus(Vnom=20.0))
    line: Line = Line(bus_from=source, bus_to=target, r=0.02, x=0.2, b=0.006, g=0.004)
    grid.add_line(line)
    model: Block = get_line_phasor_rms_template(grid.var_factory).block
    mapped_values: dict[Var, Const] = dict()
    assign_static_api_object_mapping_for_device(
        grid=grid, device=line, mdl=model, problem_mapping=mapped_values, logger=None,
    )
    bindings: dict[int, float] = dict()
    parameter: Var
    value: Const
    for parameter, value in model.parameters.items():
        if value.value is None:
            pass
        else:
            bindings[parameter.uid] = float(value.value)
    for parameter, value in mapped_values.items():
        assert value.value is not None
        bindings[parameter.uid] = float(value.value)
    from_voltage: complex = 1.02 * np.exp(0.14j)
    to_voltage: complex = 0.97 * np.exp(-0.06j)
    bindings[model.in_vars[0].uid] = float(from_voltage.real)
    bindings[model.in_vars[1].uid] = float(from_voltage.imag)
    bindings[model.in_vars[2].uid] = float(to_voltage.real)
    bindings[model.in_vars[3].uid] = float(to_voltage.imag)
    variable: Var
    for variable in model.algebraic_vars:
        bindings[variable.uid] = 0.0
    from_tap: float
    to_tap: float
    for from_tap, to_tap in ((1.0, 1.0), (1.03, 0.98)):
        tap_parameter: Var | None
        tap_parameter = model.api_obj_mapping.get(ParamPowerFlowReferenceType.vtap_f, None)
        assert tap_parameter is not None
        bindings[tap_parameter.uid] = from_tap
        tap_parameter = model.api_obj_mapping.get(ParamPowerFlowReferenceType.vtap_t, None)
        assert tap_parameter is not None
        bindings[tap_parameter.uid] = to_tap
        series: complex = 1.0 / complex(line.R, line.X)
        half_shunt: complex = complex(line.G, line.B) / 2.0
        from_current: complex = (
            (series + half_shunt) * from_voltage / (from_tap * from_tap)
            - series * to_voltage / (from_tap * to_tap)
        )
        to_current: complex = (
            (series + half_shunt) * to_voltage / (to_tap * to_tap)
            - series * from_voltage / (from_tap * to_tap)
        )
        expected: np.ndarray = np.array((from_current.real, from_current.imag, to_current.real, to_current.imag))
        actual: np.ndarray = np.zeros(4)
        equation_index: int
        for equation_index in range(4):
            actual[equation_index] = -float(model.algebraic_eqs[equation_index].eval_uid(bindings))
        np.testing.assert_allclose(actual, expected, rtol=1.0e-10, atol=1.0e-12)
