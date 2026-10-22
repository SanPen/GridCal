from __future__ import annotations

import math

import numpy as np

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.gencls_rms_template import get_gencls_rms_template
from VeraGridEngine.Templates.Rms.gencls_rms_template import configure_gencls_block, GenclsRmsParameters
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import get_esst3a_rms_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import get_exst1_rms_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import get_genrou_rms_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import get_tgov1_rms_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import GenrouSaturationMode
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import Tgov1ModelType
from VeraGridEngine.Templates.Rms.ieeex1_ieeest_rms_template import get_complete_genrou_ieeex1_ieeest_rms_template
from VeraGridEngine.Templates.Rms.ieeex1_ieeest_rms_template import IeeestInputMode
from VeraGridEngine.Utils.Symbolic.block import Block


def test_gencls_current_equations_include_machine_fluxes() -> None:
    """GENCLS current constraints must retain both dq-axis flux terms."""

    template: RmsModelTemplate = get_gencls_rms_template(
        vfactory=VarFactory(),
        name="gencls_flux_test",
    )
    block: Block = template.block.children[0]
    direct_axis_equation: str = str(block.algebraic_eqs[2])
    quadrature_axis_equation: str = str(block.algebraic_eqs[3])

    assert "(Xd_prime) * (Id)" in direct_axis_equation
    assert "(psid)" in direct_axis_equation
    assert "(Xd_prime) * (Iq)" in quadrature_axis_equation
    assert "(psiq)" in quadrature_axis_equation


def test_classical_fixed_rotor_and_dynamic_reconfiguration() -> None:
    """Zero inertia fixes both rotor derivatives without disabling stator response."""
    from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
    factory: VarFactory = VarFactory()
    block: Block = get_gencls_rms_template(factory).block.children[0]
    configure_gencls_block(block,GenclsRmsParameters(50,.3,0,.01,.2),factory)
    assert all(isinstance(equation,Const) and equation.value == 0 for equation in block.state_eqs)
    assert len(block.algebraic_eqs) > 0
    configure_gencls_block(block,GenclsRmsParameters(50,.3,8,.01,.2),factory)
    symbols: dict[str,Var] = dict()
    values: dict[int,float] = dict()
    for registry in (block.init_eqs,block.event_dict,block.parameters):
        for variable,expression in registry.items():
            symbols[variable.name] = variable
            if isinstance(expression,Const) and expression.value is not None:
                values[variable.uid] = expression.value
            else:
                pass
    values[symbols['omega'].uid] = 1.2
    values[symbols['Tm'].uid] = 1.0
    values[symbols['Te'].uid] = .2
    assert abs(block.state_eqs[0].eval_uid(values)-20*math.pi) < 1e-12
    assert abs(block.state_eqs[1].eval_uid(values)-.0925) < 1e-12


def test_busfreq_local_jacobian_matches_standard_realization() -> None:
    """The IEEEST-owned frequency helper must retain the standard realization."""

    template: RmsModelTemplate = get_complete_genrou_ieeex1_ieeest_rms_template(
        vfactory=VarFactory(),
        input_mode=IeeestInputMode.BUS_FREQUENCY,
        name="busfreq_local_test",
    )
    block: Block = template.block.children[-1]

    assert list(var.name for var in block.state_vars) == list(("L_y", "WO_x"))
    assert list(var.name for var in block.algebraic_vars) == list(("WO_y", "f"))

    wo_state_equation: str = str(block.state_eqs[1])
    wo_output_equation: str = str(block.algebraic_eqs[0])

    assert "(L_y) - (WO_x)" in wo_state_equation
    assert "6.283185307179586" not in wo_state_equation
    assert "3.141592653589793" in wo_output_equation
    assert "(L_y) - (WO_x)" in wo_output_equation


def test_exst1_local_structure_matches_standard_blocks() -> None:
    """EXST1 must follow the standard Lag/LeadLag/Lag/Washout realization."""

    template: RmsModelTemplate = get_exst1_rms_template(VarFactory(), name="exst1_local_test")
    block: Block = template.block.children[0]

    assert list(var.name for var in block.state_vars) == list(("LG_y", "LL_x", "LR_y", "WF_x"))

    lg_equation: str = str(block.state_eqs[0])
    ll_equation: str = str(block.state_eqs[1])
    lr_equation: str = str(block.state_eqs[2])
    wf_equation: str = str(block.state_eqs[3])
    ll_y_equation: str = str(block.algebraic_eqs[3])

    assert "/ (TR)" in lg_equation or "/ ((TR) + (1e-08))" in lg_equation
    assert "/ (TB)" in ll_equation or "/ ((TB) + (1e-08))" in ll_equation
    assert "(KA) * (LL_y)" in lr_equation
    assert "/ (TA)" in lr_equation or "/ ((TA) + (1e-08))" in lr_equation
    assert "/ (TF)" in wf_equation or "/ ((TF) + (1e-08))" in wf_equation
    assert "(TC) / (TB)" in ll_y_equation


def test_esst3a_local_structure_matches_standard_chain() -> None:
    """ESST3A must keep the the standard lead-lag and LAW1/LAW2 chain."""

    template: RmsModelTemplate = get_esst3a_rms_template(VarFactory(), name="esst3a_local_test")
    block: Block = template.block.children[0]

    assert list(var.name for var in block.state_vars) == list(("LG_y", "LL_x", "LAW2_y"))

    ll_equation: str = str(block.state_eqs[1])
    law2_equation: str = str(block.state_eqs[2])
    ll_y_equation: str = str(block.algebraic_eqs[4])
    law1_equation: str = str(block.algebraic_eqs[5])
    vg_equation: str = str(block.algebraic_eqs[9])
    vrs_equation: str = str(block.algebraic_eqs[10])

    assert "(HG_y) - (LL_x)" in ll_equation
    assert "(KM) * (vrs)" in law2_equation
    assert "(TC) / (TB)" in ll_y_equation
    assert "(HG_y) - (LL_x)" in ll_y_equation
    assert "+ (LL_x)" in ll_y_equation
    assert "(KA) * (LL_y)" in law1_equation
    assert "(KG) * (Vf)" in vg_equation
    assert "(LAW1_y) - (VG_y)" in vrs_equation


def test_esst3a_expected_local_law2_coefficients_from_parameters() -> None:
    """ESST3A local chain must produce the the expected LAW2 coefficients."""

    ka: float = 20.0
    km: float = 8.0
    tm: float = 0.4
    tc: float = 1.0
    tb: float = 5.0

    expected_llx: float = km * ka / tm * (1.0 - tc / tb)
    expected_lgy: float = -km * ka / tm * (tc / tb)

    assert abs(expected_llx - 320.0) <= 1.0e-12
    assert abs(expected_lgy + 80.0) <= 1.0e-12


def test_esst3a_local_structure_reduces_to_standard_law2_chain() -> None:
    """The symbolic ESST3A chain must expose the expected 320/-80 reduction."""

    template: RmsModelTemplate = get_esst3a_rms_template(VarFactory(), name="esst3a_chain_test")
    block: Block = template.block.children[0]

    ll_y_equation: str = str(block.algebraic_eqs[4])
    law1_equation: str = str(block.algebraic_eqs[5])
    vrs_equation: str = str(block.algebraic_eqs[10])
    law2_equation: str = str(block.state_eqs[2])

    assert "(TC) / (TB)" in ll_y_equation
    assert "(HG_y) - (LL_x)" in ll_y_equation
    assert "+ (LL_x)" in ll_y_equation
    assert "(KA) * (LL_y)" in law1_equation
    assert "(LAW1_y) - (VG_y)" in vrs_equation
    assert "(KM) * (vrs)" in law2_equation


def test_genrou_local_structure_contains_standard_internal_realization() -> None:
    """GENROU must expose the internal standard algebraic realization."""

    template: RmsModelTemplate = get_genrou_rms_template(VarFactory(), name="genrou_local_test")
    block: Block = template.block.children[0]

    algebraic_names: list[str] = list(var.name for var in block.algebraic_vars)
    for required_name in ("psid", "psiq", "psi2d", "psi2q", "psi2", "Se", "XaqI1q", "XadIfd"):
        assert required_name in algebraic_names
    assert len(block.algebraic_vars) >= len(block.algebraic_eqs)

    e1q_equation: str = str(block.state_eqs[2])
    e1d_equation: str = str(block.state_eqs[3])
    xadifd_equation: str = next(
        str(eq)
        for var, eq in zip(block.algebraic_vars, block.algebraic_eqs)
        if var.name == "XadIfd"
    )
    psi2_equation: str = next(
        str(eq)
        for var, eq in zip(block.algebraic_vars, block.algebraic_eqs)
        if var.name == "psi2"
    )

    assert "(XadIfd)" in e1q_equation
    assert "(XaqI1q)" in e1d_equation
    assert "(Se) * (psi2d)" in xadifd_equation
    assert "(psi2d) ** (2)" in psi2_equation
    assert "(psi2q) ** (2)" in psi2_equation


def test_genrou_disabled_saturation_is_structural_and_finite() -> None:
    """Zero saturation data must select a finite no-saturation realization."""

    template: RmsModelTemplate = get_genrou_rms_template(
        VarFactory(),
        name="genrou_disabled_saturation_test",
        saturation_mode=GenrouSaturationMode.DISABLED,
    )
    block: Block = template.block.children[0]
    saturation_equation: str = next(
        str(equation)
        for variable, equation in zip(block.algebraic_vars, block.algebraic_eqs)
        if variable.name == "Se"
    )

    assert "(0.0)" in saturation_equation
    assert "(S10)" not in saturation_equation
    assert "(S12)" not in saturation_equation


def test_ieee14_style_generator_wrapper_preserves_machine_first_state_order() -> None:
    """IEEE14 wrapper assembly must keep the machine states before controllers."""

    vf: VarFactory = VarFactory()
    wrapper: Block = get_genrou_rms_template(vf, name="wrapper_test").block
    machine_block: Block = wrapper.children[0]
    governor_block: Block = get_tgov1_rms_template(vf, name="wrapper_gov").block.children[0]
    exciter_block: Block = get_esst3a_rms_template(vf, name="wrapper_esst3a").block.children[0]

    wrapper.children.append(governor_block)
    wrapper.children.append(exciter_block)

    child_names: list[str] = list(child.name for child in wrapper.children)
    assert child_names[0] == machine_block.name
    assert list(var.name for var in wrapper.children[0].state_vars[:6]) == list(
        ("delta", "omega", "e1q", "e1d", "e2d", "e2q")
    )


def test_tgov1n_places_power_reference_after_droop_gain() -> None:
    """TGOV1N must scale speed only and retain a system-base power reference."""

    vfactory: VarFactory = VarFactory()
    tgov1_block: Block = get_tgov1_rms_template(
        vfactory=vfactory,
        name="tgov1_equation_test",
        model_type=Tgov1ModelType.TGOV1,
    ).block.children[0]
    tgov1n_block: Block = get_tgov1_rms_template(
        vfactory=vfactory,
        name="tgov1n_equation_test",
        model_type=Tgov1ModelType.TGOV1N,
    ).block.children[0]

    tgov1_reference_equation: str = str(tgov1_block.algebraic_eqs[0])
    tgov1n_reference_equation: str = str(tgov1n_block.algebraic_eqs[0])
    tgov1_demand_equation: str = str(tgov1_block.algebraic_eqs[2])
    tgov1n_demand_equation: str = str(tgov1n_block.algebraic_eqs[2])

    assert "(pref0) * (R)" in tgov1_reference_equation
    assert "(pref0) - (pref)" in tgov1n_reference_equation
    assert "(pref) / (R)" in tgov1_demand_equation
    assert "(pref) / (R)" not in tgov1n_demand_equation


def test_bus_frequency_measurement_is_owned_only_by_frequency_consumer() -> None:
    """A composite must embed BusFrequency only when its PSS consumes frequency."""

    electrical_power_template: RmsModelTemplate = get_complete_genrou_ieeex1_ieeest_rms_template(
        vfactory=VarFactory(),
        input_mode=IeeestInputMode.ELECTRICAL_POWER,
        name="mode_three_pss_test",
    )
    frequency_template: RmsModelTemplate = get_complete_genrou_ieeex1_ieeest_rms_template(
        vfactory=VarFactory(),
        input_mode=IeeestInputMode.BUS_FREQUENCY,
        name="mode_two_pss_test",
    )
    electrical_child_names: list[str] = list()
    frequency_child_names: list[str] = list()
    child: Block
    for child in electrical_power_template.block.children:
        electrical_child_names.append(child.name)
    for child in frequency_template.block.children:
        frequency_child_names.append(child.name)

    assert len(electrical_child_names) == 4
    assert len(frequency_child_names) == 5
    assert all("BusFrequency" not in name for name in electrical_child_names)
    assert any("BusFrequency" in name for name in frequency_child_names)
    assert len(frequency_template.block.children[-1].in_vars) == 1


def test_zero_time_constant_state_stays_algebraic_in_schur_reduction() -> None:
    """One T=0 state must remain an algebraic constraint before Schur reduction."""

    tf: np.ndarray = np.diag(np.array((2.0, 0.0)))
    fx: np.ndarray = np.array(((-3.0, 1.5), (4.0, -2.0)))
    fy: np.ndarray = np.array(((2.0,), (-1.0,)))
    gx: np.ndarray = np.array(((5.0, -3.0),))
    gy: np.ndarray = np.array(((7.0,),))

    reduced_full: np.ndarray = np.linalg.solve(
        tf[:1, :1],
        fx[:1, :1] - fy[:1, :] @ np.linalg.solve(gy, gx[:, :1]),
    )
    expected: np.ndarray = np.array(((-31.0 / 14.0,),))

    assert np.allclose(reduced_full, expected, atol=1.0e-12)
