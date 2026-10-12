# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import (
    DeviceType,
    ValveEmtModelVariant,
    ValveEmtType,
    ValveInitializationState,
    VarPowerFlowReferenceType,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, abs
from VeraGridEngine.Utils.procedural_logic import ValveStateLogic


def _get_valve_type_code(valve_tpe: ValveEmtType) -> float:
    """
    Return the numeric code used by the EMT valve template for one valve type.

    :param valve_tpe: Valve physical type.
    :return: Numeric code stored in runtime parameters.
    """
    if valve_tpe == ValveEmtType.Diode:
        return 0.0
    else:
        pass

    if valve_tpe == ValveEmtType.Igbt:
        return 1.0
    else:
        pass

    if valve_tpe == ValveEmtType.Thyristor:
        return 2.0
    else:
        raise ValueError(f"Unsupported EMT valve type {valve_tpe}")


def _get_valve_variant_code(model_variant: ValveEmtModelVariant) -> float:
    """
    Return the numeric code used by the EMT valve template for one model variant.

    :param model_variant: Valve EMT modelling variant.
    :return: Numeric code stored in runtime parameters.
    """
    if model_variant == ValveEmtModelVariant.Ideal:
        return 0.0
    else:
        pass

    if model_variant == ValveEmtModelVariant.Complete:
        return 1.0
    else:
        raise ValueError(f"Unsupported EMT valve model variant {model_variant}")


def _get_valve_initialization_code(initial_state: ValveInitializationState) -> float:
    """
    Return the numeric code used by the EMT valve template for the initialization state.

    :param initial_state: Valve initialization policy.
    :return: Numeric code stored in runtime parameters.
    """
    if initial_state == ValveInitializationState.FromPowerFlow:
        return 0.0
    else:
        pass

    if initial_state == ValveInitializationState.Blocked:
        return 1.0
    else:
        pass

    if initial_state == ValveInitializationState.ForwardConducting:
        return 2.0
    else:
        pass

    if initial_state == ValveInitializationState.ReverseConducting:
        return 3.0
    else:
        raise ValueError(f"Unsupported EMT valve initialization state {initial_state}")


def _build_initial_path_mode_expression(
        initial_state_code: Var,
        path_mode_pf_seed: Var,
) -> Expr:
    """
    Build the initialization expression of the retained valve path mode.

    The retained runtime mode is initialized from a symbolic expression so the
    explicit runtime-parameter bootstrap can combine the user-selected policy
    with the PF-derived conduction seed before the first EMT step.

    :param initial_state_code: Runtime parameter encoding the initialization policy.
    :param path_mode_pf_seed: PF-derived forward/reverse conduction seed.
    :return: Symbolic initialization expression for the retained path mode.
    """
    from_pf_flag: Expr = (initial_state_code == Const(0.0)).to_expression()
    blocked_flag: Expr = (initial_state_code == Const(1.0)).to_expression()
    forward_flag: Expr = (initial_state_code == Const(2.0)).to_expression()
    reverse_flag: Expr = (initial_state_code == Const(3.0)).to_expression()

    # Each flag is mutually exclusive, so the weighted sum selects the requested startup mode.
    return (
        from_pf_flag * path_mode_pf_seed
        + blocked_flag * Const(0.0)
        + forward_flag * Const(1.0)
        + reverse_flag * Const(-1.0)
    )


def get_valve_emt_template(
        vf: VarFactory,
        name: str = "valve_emt_template",
        valve_tpe: ValveEmtType = ValveEmtType.Igbt,
        model_variant: ValveEmtModelVariant = ValveEmtModelVariant.Ideal,
        initial_state: ValveInitializationState = ValveInitializationState.Blocked,
        antiparallel_diode: bool = True,
        internal_name_suffix: str | None = None,
) -> EmtModelTemplate:
    """
    Build a generic two-terminal EMT valve template.

    The template represents one controlled DC semiconductor branch that can be
    reused inside arbitrary EMT models. It exposes explicit terminal voltages and
    currents so it can act as a standalone two-terminal DC branch or as a nested
    sub-block inside a larger converter model.

    The retained conduction path is encoded as:

    - ``+1``: forward conduction from the ``from`` side to the ``to`` side
    - ``0``: blocked state
    - ``-1``: reverse conduction through the antiparallel path

    :param vf: Shared symbolic variable factory.
    :param name: Template instance name.
    :param valve_tpe: Valve physical type.
    :param model_variant: Valve EMT modelling variant.
    :param initial_state: Startup policy for the conduction state.
    :param antiparallel_diode: Enable the reverse freewheeling path.
    :param internal_name_suffix: Optional suffix that makes every internal
        variable unique when several valve blocks share one composite model.
        ``None`` preserves the legacy standalone variable names.
    :return: Reusable EMT valve template.
    """
    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.DynamicModelHostDevice
    templ.name = name
    templ.block.name = name

    # Standalone valve models keep their established public variable names.
    # Composite devices opt into a suffix because procedural logic is bound
    # against the complete system block and therefore requires unique names.
    symbolic_suffix: str
    if internal_name_suffix is None:
        symbolic_suffix = ""
    else:
        symbolic_suffix = f"_{internal_name_suffix}"

    # ------------------------------------------------------------------
    # Terminal inputs.
    # ------------------------------------------------------------------
    v_f_dc: Var = vf.add_var(
        name=f"v_f_dc{symbolic_suffix}",
        reference=VarPowerFlowReferenceType.Vf_dc,
    )
    v_t_dc: Var = vf.add_var(
        name=f"v_t_dc{symbolic_suffix}",
        reference=VarPowerFlowReferenceType.Vt_dc,
    )

    # ------------------------------------------------------------------
    # Runtime parameters.
    # ------------------------------------------------------------------
    valve_type_code: Var = vf.add_var(name=f"valve_type_code{symbolic_suffix}")
    model_variant_code: Var = vf.add_var(name=f"model_variant_code{symbolic_suffix}")
    antiparallel_diode_enabled: Var = vf.add_var(
        name=f"antiparallel_diode_enabled{symbolic_suffix}",
    )
    rated_current: Var = vf.add_var(name=f"rated_current{symbolic_suffix}")
    forward_voltage: Var = vf.add_var(name=f"forward_voltage{symbolic_suffix}")
    on_resistance: Var = vf.add_var(name=f"on_resistance{symbolic_suffix}")
    off_conductance: Var = vf.add_var(name=f"off_conductance{symbolic_suffix}")
    gate_fired: Var = vf.add_var(name=f"gate_fired{symbolic_suffix}")
    initial_state_code: Var = vf.add_var(name=f"initial_state_code{symbolic_suffix}")
    snubber_enabled: Var = vf.add_var(name=f"snubber_enabled{symbolic_suffix}")
    snubber_capacitance: Var = vf.add_var(
        name=f"snubber_capacitance{symbolic_suffix}",
    )
    snubber_conductance: Var = vf.add_var(
        name=f"snubber_conductance{symbolic_suffix}",
    )
    voltage_eps: Var = vf.add_var(name=f"voltage_eps{symbolic_suffix}")
    current_eps: Var = vf.add_var(name=f"current_eps{symbolic_suffix}")
    path_mode_pf_seed: Var = vf.add_var(name=f"path_mode_pf_seed{symbolic_suffix}")

    # ------------------------------------------------------------------
    # Retained runtime mode.
    # ------------------------------------------------------------------
    path_mode: Var = vf.add_var(name=f"path_mode{symbolic_suffix}")

    # ------------------------------------------------------------------
    # Dynamic and algebraic variables.
    # ------------------------------------------------------------------
    q_snubber: Var = vf.add_var(name=f"q_snubber{symbolic_suffix}")
    d_q_snubber: Var = vf.add_diff_var(
        name=f"d_q_snubber{symbolic_suffix}",
        base_var=q_snubber,
    )

    v_valve: Var = vf.add_var(name=f"v_valve{symbolic_suffix}")
    i_static: Var = vf.add_var(name=f"i_static{symbolic_suffix}")
    i_capacitive: Var = vf.add_var(name=f"i_capacitive{symbolic_suffix}")
    i_f_dc: Var = vf.add_var(
        name=f"i_f_dc{symbolic_suffix}",
        reference=VarPowerFlowReferenceType.If_dc,
    )
    i_t_dc: Var = vf.add_var(
        name=f"i_t_dc{symbolic_suffix}",
        reference=VarPowerFlowReferenceType.It_dc,
    )
    p_f: Var = vf.add_var(
        name=f"p_f{symbolic_suffix}",
        reference=VarPowerFlowReferenceType.Pf,
    )
    p_t: Var = vf.add_var(
        name=f"p_t{symbolic_suffix}",
        reference=VarPowerFlowReferenceType.Pt,
    )
    i_rating_margin: Var = vf.add_var(name=f"i_rating_margin{symbolic_suffix}")

    # ------------------------------------------------------------------
    # Fixed numerical safeguards.
    # ------------------------------------------------------------------
    c_zero: Const = vf.add_const(0.0)
    c_one: Const = vf.add_const(1.0)
    c_minus_one: Const = vf.add_const(-1.0)
    c_half: Const = vf.add_const(0.5)
    c_minus_half: Const = vf.add_const(-0.5)
    ideal_on_resistance_floor: Const = vf.add_const(1.0e-6)

    # ------------------------------------------------------------------
    # Variant-dependent effective parameters.
    # ------------------------------------------------------------------
    complete_flag: Expr = (model_variant_code == Const(1.0)).to_expression()
    ideal_flag: Expr = c_one - complete_flag

    # The ideal variant is regularized with a very small resistance to keep the DAE well posed.
    on_resistance_effective: Expr = complete_flag * (on_resistance + ideal_on_resistance_floor) + ideal_flag * ideal_on_resistance_floor
    forward_voltage_effective: Expr = complete_flag * forward_voltage
    off_conductance_effective: Expr = complete_flag * off_conductance
    snubber_conductance_effective: Expr = complete_flag * snubber_enabled * snubber_conductance
    snubber_capacitance_effective: Expr = complete_flag * snubber_enabled * snubber_capacitance

    # ------------------------------------------------------------------
    # Conduction-path indicator expressions.
    # ------------------------------------------------------------------
    forward_mode_flag: Expr = (path_mode > c_half).to_expression()
    reverse_mode_flag: Expr = (path_mode < c_minus_half).to_expression()
    blocked_mode_flag: Expr = c_one - forward_mode_flag - reverse_mode_flag

    # ------------------------------------------------------------------
    # Main conduction and snubber currents.
    # ------------------------------------------------------------------
    forward_current_expr: Expr = forward_mode_flag * (v_valve - forward_voltage_effective) / on_resistance_effective
    reverse_current_expr: Expr = reverse_mode_flag * (v_valve + forward_voltage_effective) / on_resistance_effective
    leakage_current_expr: Expr = blocked_mode_flag * off_conductance_effective * v_valve
    snubber_conductive_current_expr: Expr = snubber_conductance_effective * v_valve
    static_current_expr: Expr = forward_current_expr + reverse_current_expr + leakage_current_expr + snubber_conductive_current_expr

    # ------------------------------------------------------------------
    # Block assembly.
    # ------------------------------------------------------------------
    templ.block = Block(
        name=name,
        state_vars=[q_snubber],
        diff_vars=[d_q_snubber],
        state_eqs=[i_capacitive],
        algebraic_vars=[v_valve, i_static, i_capacitive, i_f_dc, i_t_dc, p_f, p_t, i_rating_margin],
        algebraic_eqs=[
            v_valve - (v_f_dc - v_t_dc),
            i_static - static_current_expr,
            i_capacitive - (i_f_dc - i_static),
            i_t_dc + i_f_dc,
            p_f - v_f_dc * i_f_dc,
            p_t - v_t_dc * i_t_dc,
            i_rating_margin - (rated_current - abs(i_f_dc)),
            q_snubber - snubber_capacitance_effective * v_valve,
        ],
        in_vars=[v_f_dc, v_t_dc],
        out_vars=[i_f_dc, i_t_dc, v_valve, i_static, i_capacitive, p_f, p_t, i_rating_margin],
        event_dict=dict([
            (valve_type_code, Const(_get_valve_type_code(valve_tpe))),
            (model_variant_code, Const(_get_valve_variant_code(model_variant))),
            (antiparallel_diode_enabled, Const(1.0 if antiparallel_diode else 0.0)),
            (rated_current, Const(1.0)),
            (forward_voltage, Const(0.0)),
            (on_resistance, Const(0.0)),
            (off_conductance, Const(0.0)),
            (gate_fired, Const(0.0)),
            (initial_state_code, Const(_get_valve_initialization_code(initial_state))),
            (snubber_enabled, Const(0.0)),
            (snubber_capacitance, Const(0.0)),
            (snubber_conductance, Const(0.0)),
            (voltage_eps, Const(1.0e-6)),
            (current_eps, Const(1.0e-6)),
            (path_mode_pf_seed, Const(0.0)),
        ]),
        mode_dict=dict([
            (path_mode, _build_initial_path_mode_expression(initial_state_code, path_mode_pf_seed)),
        ]),
        init_eqs=dict([
            (q_snubber, snubber_capacitance_effective * (v_f_dc - v_t_dc)),
            (v_valve, v_f_dc - v_t_dc),
            (i_static, static_current_expr),
            (i_capacitive, c_zero),
            (i_f_dc, static_current_expr),
            (i_t_dc, -static_current_expr),
            (p_f, v_f_dc * static_current_expr),
            (p_t, -v_t_dc * static_current_expr),
            (i_rating_margin, rated_current - abs(static_current_expr)),
        ]),
        diff_init_eqs=dict([
            (d_q_snubber, c_zero),
        ]),
        external_mapping=dict([
            (VarPowerFlowReferenceType.Vf_dc, v_f_dc),
            (VarPowerFlowReferenceType.Vt_dc, v_t_dc),
            (VarPowerFlowReferenceType.Vdc, v_f_dc),
            (VarPowerFlowReferenceType.If_dc, i_f_dc),
            (VarPowerFlowReferenceType.It_dc, i_t_dc),
            (VarPowerFlowReferenceType.Idc, i_f_dc),
            (VarPowerFlowReferenceType.Pf, p_f),
            (VarPowerFlowReferenceType.Pt, p_t),
            (VarPowerFlowReferenceType.DcPathModeSeed, path_mode_pf_seed),
        ]),
        procedural_logic=list([
            ValveStateLogic(
                mode_var_name=path_mode.name,
                valve_type_var_name=valve_type_code.name,
                gate_var_name=gate_fired.name,
                antiparallel_var_name=antiparallel_diode_enabled.name,
                voltage_eps_var_name=voltage_eps.name,
                current_eps_var_name=current_eps.name,
                valve_voltage_var_name=v_valve.name,
                valve_current_var_name=i_f_dc.name,
                name=f"valve_state_logic{symbolic_suffix}",
            ),
        ]),
    )

    return templ
