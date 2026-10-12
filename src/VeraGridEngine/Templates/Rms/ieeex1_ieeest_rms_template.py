# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Standard IEEEX1 excitation-system and IEEEST stabilizer RMS templates.

IEEEX1 and IEEEST are normally used as blocks of one synchronous-generator
assembly.  This module exposes each block independently and also provides a
composite GENROU--TGOV1N--IEEEX1--IEEEST model. The IEEEST realization is the
zeroed input-filter structural variant used by the IEEE39 reference data: F1,
F2 and LL1 are exact algebraic pass-through blocks, while LL2 and the washout
remain differential states.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import List

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import get_genrou_rms_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import get_tgov1_rms_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import GenrouSaturationMode
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import Tgov1ModelType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class Ieeex1RmsParameters:
    """Numerical parameters for one zero-TR, zero-TB/TC IEEEX1 exciter."""

    __slots__ = (
        "ta", "te", "tf1", "kf1", "ka", "ke", "vrmax", "vrmin",
        "e1", "se1", "e2", "se2",
    )

    def __init__(
        self: "Ieeex1RmsParameters",
        ta: float,
        te: float,
        tf1: float,
        kf1: float,
        ka: float,
        ke: float,
        vrmax: float,
        vrmin: float,
        e1: float,
        se1: float,
        e2: float,
        se2: float,
    ) -> None:
        """Store one IEEEX1 parameter set.

        :param ta: Regulator lag time constant in seconds.
        :param te: Exciter time constant in seconds.
        :param tf1: Feedback washout time constant in seconds.
        :param kf1: Feedback washout gain.
        :param ka: Regulator gain.
        :param ke: Linear exciter feedback gain.
        :param vrmax: Upper regulator limit coefficient.
        :param vrmin: Lower regulator limit coefficient.
        :param e1: First quadratic-saturation voltage point.
        :param se1: Saturation factor at ``e1``.
        :param e2: Second quadratic-saturation voltage point.
        :param se2: Saturation factor at ``e2``.
        :return: None.
        """
        self.ta: float = ta
        self.te: float = te
        self.tf1: float = tf1
        self.kf1: float = kf1
        self.ka: float = ka
        self.ke: float = ke
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.e1: float = e1
        self.se1: float = se1
        self.e2: float = e2
        self.se2: float = se2


class IeeestInputMode(Enum):
    """Input signals supported by the standard IEEEST template."""

    ROTOR_SPEED = 1
    BUS_FREQUENCY = 2
    ELECTRICAL_POWER = 3
    ACCELERATING_POWER = 4
    BUS_VOLTAGE = 5


class IeeestRmsParameters:
    """Numerical parameters for the reduced zero-input-filter IEEEST variant."""

    __slots__ = (
        "t3", "t4", "t5", "t6", "ks", "lsmax", "lsmin", "vcu", "vcl",
        "machine_to_system_power_scale",
    )

    def __init__(
        self: "IeeestRmsParameters",
        t3: float,
        t4: float,
        t5: float,
        t6: float,
        ks: float,
        lsmax: float,
        lsmin: float,
        vcu: float,
        vcl: float,
        machine_to_system_power_scale: float,
    ) -> None:
        """Store one IEEEST parameter set.

        :param t3: LL2 numerator time constant in seconds.
        :param t4: LL2 denominator time constant in seconds.
        :param t5: Washout numerator time constant in seconds.
        :param t6: Washout denominator time constant in seconds.
        :param ks: Stabilizer gain before the washout.
        :param lsmax: Maximum stabilizer output.
        :param lsmin: Minimum stabilizer output.
        :param vcu: Upper voltage-enabling threshold.
        :param vcl: Lower voltage-enabling threshold.
        :param machine_to_system_power_scale: ``Sn/Sbase`` conversion factor.
        :return: None.
        """
        self.t3: float = t3
        self.t4: float = t4
        self.t5: float = t5
        self.t6: float = t6
        self.ks: float = ks
        self.lsmax: float = lsmax
        self.lsmin: float = lsmin
        self.vcu: float = vcu
        self.vcl: float = vcl
        self.machine_to_system_power_scale: float = machine_to_system_power_scale


def _add_parameter(
    block: Block,
    vfactory: VarFactory,
    name: str,
    value: float | None,
) -> Var:
    """Create and register one named model parameter.

    :param block: Block owning the parameter.
    :param vfactory: Shared symbolic variable factory.
    :param name: Parameter name.
    :param value: Numerical value or ``None`` for initialization.
    :return: Registered parameter variable.
    """
    parameter: Var = vfactory.add_var(name)
    block.event_dict[parameter] = vfactory.add_const(value)
    return parameter


def _get_bus_frequency_measurement_block(
    vfactory: VarFactory,
    name: str,
) -> Block:
    """Build the internal angle-to-frequency measurement used by IEEEST.

    The helper is intentionally private to the consuming device model. The bus
    remains an algebraic ``Vm``/``Va`` object, while this block's filter memory
    becomes part of the IEEEST-containing generator state space only for input
    mode 2.

    :param vfactory: Shared symbolic variable factory.
    :param name: Embedded block name.
    :return: Two-state filtered frequency-measurement block.
    """
    va_var: Var = vfactory.add_var("Va")
    angle_filter_state: Var = vfactory.add_var("L_y")
    washout_state: Var = vfactory.add_var("WO_x")
    washout_output: Var = vfactory.add_var("WO_y")
    frequency_output: Var = vfactory.add_var("f")

    block: Block = Block(name=name)
    filter_time: Var = _add_parameter(block, vfactory, "Tf", 0.02)
    washout_time: Var = _add_parameter(block, vfactory, "Tw", 0.02)
    nominal_frequency: Var = vfactory.add_var("fn")
    block.parameters[nominal_frequency] = vfactory.add_const(60.0)
    block.api_obj_mapping[ParamPowerFlowReferenceType.freq] = nominal_frequency
    initial_angle: Var = _add_parameter(block, vfactory, "a0", None)
    inverse_nominal_speed: Expr = (
        sym.Const(1.0)
        / (sym.Const(2.0) * sym.Const(math.pi) * nominal_frequency)
    )

    # Both filters have memory and therefore remain differential states of the
    # IEEEST consumer rather than becoming variables of the network bus.
    block.state_vars = list((angle_filter_state, washout_state))
    block.state_eqs = list((
        ((va_var - initial_angle) - angle_filter_state) / filter_time,
        (angle_filter_state - washout_state) / washout_time,
    ))
    block.algebraic_vars = list((washout_output, frequency_output))
    block.algebraic_eqs = list((
        inverse_nominal_speed * (angle_filter_state - washout_state)
        - washout_time * washout_output,
        sym.Const(1.0) + washout_output - frequency_output,
    ))
    block.init_eqs = dict()
    block.init_eqs[initial_angle] = va_var
    block.init_eqs[angle_filter_state] = sym.Const(0.0)
    block.init_eqs[washout_state] = sym.Const(0.0)
    block.init_eqs[washout_output] = sym.Const(0.0)
    block.init_eqs[frequency_output] = sym.Const(1.0)
    block.in_vars = list((va_var,))
    block.out_vars = list((frequency_output,))
    return block


def _set_parameter(
    block: Block,
    vfactory: VarFactory,
    parameter_name: str,
    value: float,
) -> None:
    """Replace exactly one named block parameter.

    :param block: Block whose parameter will be replaced.
    :param vfactory: Shared symbolic variable factory.
    :param parameter_name: Exact parameter name.
    :param value: New numerical value.
    :return: None.
    :raises ValueError: If the parameter name is missing or ambiguous.
    """
    matching_parameters: List[Var] = list()
    parameter: Var
    for parameter in block.event_dict.keys():
        if parameter.name == parameter_name:
            matching_parameters.append(parameter)
        else:
            pass
    if len(matching_parameters) != 1:
        raise ValueError(
            f"Expected one parameter named '{parameter_name}' in "
            f"'{block.name}', found {len(matching_parameters)}."
        )
    else:
        pass
    block.event_dict[matching_parameters[0]] = vfactory.add_const(value)


def configure_ieeex1_block(
    block: Block,
    parameters: Ieeex1RmsParameters,
    vfactory: VarFactory,
) -> None:
    """Apply numerical IEEEX1 parameters to an existing block.

    :param block: IEEEX1 model block.
    :param parameters: Numerical IEEEX1 parameters.
    :param vfactory: Shared symbolic variable factory.
    :return: None.
    """
    _set_parameter(block, vfactory, "TA", parameters.ta)
    _set_parameter(block, vfactory, "TE", parameters.te)
    _set_parameter(block, vfactory, "TF1", parameters.tf1)
    _set_parameter(block, vfactory, "KF1", parameters.kf1)
    _set_parameter(block, vfactory, "KA", parameters.ka)
    _set_parameter(block, vfactory, "KE", parameters.ke)
    _set_parameter(block, vfactory, "VRMAX", parameters.vrmax)
    _set_parameter(block, vfactory, "VRMIN", parameters.vrmin)
    _set_parameter(block, vfactory, "E1", parameters.e1)
    _set_parameter(block, vfactory, "SE1", parameters.se1)
    _set_parameter(block, vfactory, "E2", parameters.e2)
    _set_parameter(block, vfactory, "SE2", parameters.se2)


def configure_ieeest_block(
    block: Block,
    parameters: IeeestRmsParameters,
    vfactory: VarFactory,
) -> None:
    """Apply numerical IEEEST parameters to an existing block.

    :param block: IEEEST model block.
    :param parameters: Numerical IEEEST parameters.
    :param vfactory: Shared symbolic variable factory.
    :return: None.
    """
    _set_parameter(block, vfactory, "T3", parameters.t3)
    _set_parameter(block, vfactory, "T4", parameters.t4)
    _set_parameter(block, vfactory, "T5", parameters.t5)
    _set_parameter(block, vfactory, "T6", parameters.t6)
    _set_parameter(block, vfactory, "KS", parameters.ks)
    _set_parameter(block, vfactory, "LSMAX", parameters.lsmax)
    _set_parameter(block, vfactory, "LSMIN", parameters.lsmin)
    _set_parameter(block, vfactory, "VCU", parameters.vcu)
    _set_parameter(block, vfactory, "VCL", parameters.vcl)
    _set_parameter(
        block,
        vfactory,
        "SnSb",
        parameters.machine_to_system_power_scale,
    )


def _quadratic_saturation_coefficients(
    e1: Expr,
    se1: Expr,
    e2: Expr,
    se2: Expr,
) -> tuple[Expr, Expr]:
    """Return standard quadratic exciter-saturation coefficients.

    :param e1: First voltage point.
    :param se1: First saturation factor.
    :param e2: Second voltage point.
    :param se2: Second saturation factor.
    :return: Saturation start and gain expressions.
    """
    ratio: Expr = sym.sqrt((se1 * e1) / (se2 * e2))
    saturation_start: Expr = e2 - (e1 - e2) / (ratio - sym.Const(1.0))
    saturation_gain: Expr = (
        se2 * e2 * (ratio - sym.Const(1.0)) ** 2 / (e1 - e2) ** 2
    )
    return saturation_start, saturation_gain


def get_ieeex1_rms_template(
    vfactory: VarFactory,
    name: str = "IEEEX1 RMS template",
) -> RmsModelTemplate:
    """Build the zero-TR, zero-TB/TC IEEEX1 structural variant.

    The voltage-sensing lag and lead-lag blocks are exact algebraic
    pass-throughs.  ``vp``, ``LA_y`` and ``W_x`` remain differential states.

    :param vfactory: Shared symbolic variable factory.
    :param name: Template name.
    :return: RMS template containing one IEEEX1 block.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice

    vm_var: Var = vfactory.add_var("Vm")
    omega_var: Var = vfactory.add_var("omega")
    stabilizer_var: Var = vfactory.add_var("Vs")
    vf_var: Var = vfactory.add_var("Vf")
    vp_var: Var = vfactory.add_var("vp")
    la_state_var: Var = vfactory.add_var("LA_y")
    washout_state_var: Var = vfactory.add_var("W_x")
    se_var: Var = vfactory.add_var("Se")
    washout_output_var: Var = vfactory.add_var("W_y")
    vi_var: Var = vfactory.add_var("vi")
    vref_var: Var = vfactory.add_var("vref")

    block: Block = Block(name=name)
    ta_var: Var = _add_parameter(block, vfactory, "TA", 0.05)
    te_var: Var = _add_parameter(block, vfactory, "TE", 0.5)
    tf1_var: Var = _add_parameter(block, vfactory, "TF1", 1.3)
    kf1_var: Var = _add_parameter(block, vfactory, "KF1", 0.23)
    ka_var: Var = _add_parameter(block, vfactory, "KA", 10.1)
    ke_var: Var = _add_parameter(block, vfactory, "KE", -0.05)
    vrmax_var: Var = _add_parameter(block, vfactory, "VRMAX", 5.0)
    vrmin_var: Var = _add_parameter(block, vfactory, "VRMIN", -5.0)
    e1_var: Var = _add_parameter(block, vfactory, "E1", 3.0)
    se1_var: Var = _add_parameter(block, vfactory, "SE1", 0.1)
    e2_var: Var = _add_parameter(block, vfactory, "E2", 4.0)
    se2_var: Var = _add_parameter(block, vfactory, "SE2", 0.3)
    vref0_var: Var = _add_parameter(block, vfactory, "vref0", None)
    se_diag_ref_var: Var = _add_parameter(block, vfactory, "Se_diag_ref", None)
    diag_eps_expr: Expr = sym.Const(1.0e-8)
    saturation_coefficients: tuple[Expr, Expr] = _quadratic_saturation_coefficients(
        e1_var,
        se1_var,
        e2_var,
        se2_var,
    )
    saturation_start: Expr = saturation_coefficients[0]
    saturation_gain: Expr = saturation_coefficients[1]

    # In the supported structural variant LS and LL are algebraic.  The PSS
    # contribution is added at vi, matching the standard exciter interface.
    regulator_input: Expr = vref_var - vm_var - washout_output_var + stabilizer_var
    regulator_target: Expr = sym.min(
        sym.max(ka_var * regulator_input, vrmin_var * vm_var),
        vrmax_var * vm_var,
    )

    block.state_vars = list((vp_var, la_state_var, washout_state_var))
    block.state_eqs = list((
        (la_state_var - ke_var * vp_var - se_var * vp_var) / te_var,
        (regulator_target - la_state_var) / ta_var,
        (vp_var - washout_state_var) / tf1_var,
    ))
    block.algebraic_vars = list((
        se_var,
        washout_output_var,
        vi_var,
        vref_var,
        vf_var,
    ))
    block.algebraic_eqs = list((
        sym.heaviside(vp_var - saturation_start)
        * saturation_gain
        * (vp_var - saturation_start) ** 2
        - se_var * vp_var
        + diag_eps_expr * (se_var - se_diag_ref_var),
        kf1_var * (vp_var - washout_state_var)
        - tf1_var * washout_output_var,
        regulator_input - vi_var,
        vref0_var - vref_var,
        vp_var - vf_var,
    ))

    initial_se: Expr = (
        sym.heaviside(vf_var - saturation_start)
        * saturation_gain
        * (vf_var - saturation_start) ** 2
        / vf_var
    )
    initial_regulator: Expr = (ke_var + initial_se) * vf_var
    initial_input: Expr = initial_regulator / ka_var
    block.init_eqs = dict()
    block.init_eqs[vp_var] = vf_var
    block.init_eqs[la_state_var] = initial_regulator
    block.init_eqs[washout_state_var] = vf_var
    block.init_eqs[se_var] = initial_se
    block.init_eqs[se_diag_ref_var] = initial_se
    block.init_eqs[washout_output_var] = sym.Const(0.0)
    block.init_eqs[vi_var] = initial_input
    block.init_eqs[vref0_var] = vm_var + initial_input
    block.init_eqs[vref_var] = vm_var + initial_input
    block.in_vars = list((vm_var, omega_var, stabilizer_var))
    block.out_vars = list((vf_var, vi_var))

    template.block.children.append(block)
    template.block.in_vars = list((vm_var, omega_var, stabilizer_var))
    template.block.out_vars = list((vf_var, vi_var))
    template.block.name = name
    template.comment = 'Generator IEEEX1 exciter RMS model'
    return template


def _ieeest_signal(
    input_mode: IeeestInputMode,
    vm_var: Var,
    omega_var: Var,
    te_var: Var,
    tm_var: Var,
    frequency_var: Var,
    sn_sb_var: Var,
) -> Expr:
    """Select the standard IEEEST input signal explicitly.

    :param input_mode: IEEEST input-signal selection.
    :param vm_var: Bus voltage magnitude.
    :param omega_var: Generator speed in per unit.
    :param te_var: Electrical power or torque on system base.
    :param tm_var: Mechanical power or torque on system base.
    :param frequency_var: Bus-frequency measurement in per unit.
    :param sn_sb_var: Machine-to-system power-base factor.
    :return: Selected stabilizer input expression.
    """
    if input_mode is IeeestInputMode.ROTOR_SPEED:
        signal: Expr = omega_var - sym.Const(1.0)
    elif input_mode is IeeestInputMode.BUS_FREQUENCY:
        signal = frequency_var - sym.Const(1.0)
    elif input_mode is IeeestInputMode.ELECTRICAL_POWER:
        signal = te_var / sn_sb_var
    elif input_mode is IeeestInputMode.ACCELERATING_POWER:
        signal = tm_var - te_var
    else:
        signal = vm_var
    return signal


def get_ieeest_rms_template(
    vfactory: VarFactory,
    input_mode: IeeestInputMode = IeeestInputMode.ELECTRICAL_POWER,
    name: str = "IEEEST RMS template",
) -> RmsModelTemplate:
    """Build the reduced zero-input-filter IEEEST structural variant.

    :param vfactory: Shared symbolic variable factory.
    :param input_mode: Standard stabilizer input signal.
    :param name: Template name.
    :return: RMS template containing one IEEEST block.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice

    vm_var: Var = vfactory.add_var("Vm")
    omega_var: Var = vfactory.add_var("omega")
    te_var: Var = vfactory.add_var("Te")
    tm_var: Var = vfactory.add_var("Tm")
    frequency_var: Var = vfactory.add_var("f")
    stabilizer_output: Var = vfactory.add_var("Vs")
    ll2_state: Var = vfactory.add_var("LL2_x")
    washout_state: Var = vfactory.add_var("WO_x")
    ll2_output: Var = vfactory.add_var("LL2_y")
    gain_output: Var = vfactory.add_var("Vks_y")
    washout_output: Var = vfactory.add_var("WO_y")
    limited_output: Var = vfactory.add_var("Vss")

    block: Block = Block(name=name)
    t3_var: Var = _add_parameter(block, vfactory, "T3", 0.0)
    t4_var: Var = _add_parameter(block, vfactory, "T4", 0.75)
    t5_var: Var = _add_parameter(block, vfactory, "T5", 1.0)
    t6_var: Var = _add_parameter(block, vfactory, "T6", 4.2)
    ks_var: Var = _add_parameter(block, vfactory, "KS", -2.0)
    lsmax_var: Var = _add_parameter(block, vfactory, "LSMAX", 0.1)
    lsmin_var: Var = _add_parameter(block, vfactory, "LSMIN", -0.1)
    vcu_var: Var = _add_parameter(block, vfactory, "VCU", 999.0)
    vcl_var: Var = _add_parameter(block, vfactory, "VCL", -999.0)
    sn_sb_var: Var = _add_parameter(block, vfactory, "SnSb", 1.0)
    signal: Expr = _ieeest_signal(
        input_mode,
        vm_var,
        omega_var,
        te_var,
        tm_var,
        frequency_var,
        sn_sb_var,
    )

    # F1, F2 and LL1 are exact pass-throughs for this structural variant.  LL2
    # retains its pole, and the numerator is represented in its output equation.
    block.state_vars = list((ll2_state, washout_state))
    block.state_eqs = list((
        (signal - ll2_state) / t4_var,
        (gain_output - washout_state) / t6_var,
    ))
    block.algebraic_vars = list((
        ll2_output,
        gain_output,
        washout_output,
        limited_output,
        stabilizer_output,
    ))
    block.algebraic_eqs = list((
        t3_var * (signal - ll2_state) / t4_var + ll2_state - ll2_output,
        ks_var * ll2_output - gain_output,
        t5_var * (gain_output - washout_state)
        - t6_var * washout_output,
        sym.min(sym.max(washout_output, lsmin_var), lsmax_var) - limited_output,
        sym.heaviside(vcu_var - vm_var)
        * sym.heaviside(vm_var - vcl_var)
        * limited_output
        - stabilizer_output,
    ))

    initial_gain: Expr = ks_var * signal
    block.init_eqs = dict()
    block.init_eqs[ll2_state] = signal
    block.init_eqs[washout_state] = initial_gain
    block.init_eqs[ll2_output] = signal
    block.init_eqs[gain_output] = initial_gain
    block.init_eqs[washout_output] = sym.Const(0.0)
    block.init_eqs[limited_output] = sym.Const(0.0)
    block.init_eqs[stabilizer_output] = sym.Const(0.0)
    block.in_vars = list((vm_var, omega_var, te_var, tm_var, frequency_var))
    block.out_vars = list((stabilizer_output,))

    template.block.children.append(block)
    template.block.in_vars = list((vm_var, omega_var, te_var, tm_var, frequency_var))
    template.block.out_vars = list((stabilizer_output,))
    template.block.name = name
    template.comment = 'Generator IEEEST stabilizer RMS model'
    return template


def get_complete_genrou_ieeex1_ieeest_rms_template(
    vfactory: VarFactory,
    input_mode: IeeestInputMode = IeeestInputMode.ELECTRICAL_POWER,
    saturation_mode: GenrouSaturationMode = GenrouSaturationMode.QUADRATIC,
    name: str = "GENROU IEEEX1 IEEEST TGOV1N RMS template",
) -> RmsModelTemplate:
    """Build one GENROU--TGOV1N--IEEEX1--IEEEST assembly.

    :param vfactory: Shared symbolic variable factory.
    :param input_mode: IEEEST input-signal selection.
    :param saturation_mode: GENROU magnetic-saturation realization.
    :param name: Composite-template name.
    :return: Connected generator RMS template.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice

    machine_block: Block = get_genrou_rms_template(
        vfactory=vfactory,
        name=f"{name} GENROU",
        saturation_mode=saturation_mode,
    ).block.children[0]
    governor_block: Block = get_tgov1_rms_template(
        vfactory=vfactory,
        name=f"{name} TGOV1N",
        model_type=Tgov1ModelType.TGOV1N,
    ).block.children[0]
    exciter_block: Block = get_ieeex1_rms_template(
        vfactory,
        f"{name} IEEEX1",
    ).block.children[0]
    stabilizer_block: Block = get_ieeest_rms_template(
        vfactory,
        input_mode,
        f"{name} IEEEST",
    ).block.children[0]
    # Machine, governor and excitation-system feedback connections.
    vfactory.add_connection(machine_block.in_vars[2], governor_block.out_vars[0])
    vfactory.add_connection(machine_block.in_vars[3], exciter_block.out_vars[0])
    vfactory.add_connection(governor_block.in_vars[0], machine_block.out_vars[2])
    vfactory.add_connection(governor_block.in_vars[1], machine_block.out_vars[4])
    vfactory.add_connection(exciter_block.in_vars[0], machine_block.in_vars[0])
    vfactory.add_connection(exciter_block.in_vars[1], machine_block.out_vars[2])
    vfactory.add_connection(exciter_block.in_vars[2], stabilizer_block.out_vars[0])

    # The PSS consumes generator and local-bus measurements.
    vfactory.add_connection(stabilizer_block.in_vars[0], machine_block.in_vars[0])
    vfactory.add_connection(stabilizer_block.in_vars[1], machine_block.out_vars[2])
    vfactory.add_connection(stabilizer_block.in_vars[2], machine_block.out_vars[4])
    vfactory.add_connection(stabilizer_block.in_vars[3], governor_block.out_vars[0])

    template.block.children.append(machine_block)
    template.block.children.append(governor_block)
    template.block.children.append(exciter_block)
    template.block.children.append(stabilizer_block)
    if input_mode is IeeestInputMode.BUS_FREQUENCY:
        # A frequency-sensitive PSS owns its angle-to-frequency measurement.
        frequency_block: Block = _get_bus_frequency_measurement_block(
            vfactory,
            f"{name} BusFrequency",
        )
        vfactory.add_connection(stabilizer_block.in_vars[4], frequency_block.out_vars[0])
        vfactory.add_connection(frequency_block.in_vars[0], machine_block.in_vars[1])
        template.block.children.append(frequency_block)
    else:
        pass
    template.block.external_mapping = dict()
    template.block.external_mapping[VarPowerFlowReferenceType.Vm] = machine_block.in_vars[0]
    template.block.external_mapping[VarPowerFlowReferenceType.Va] = machine_block.in_vars[1]
    template.block.external_mapping[VarPowerFlowReferenceType.P] = machine_block.out_vars[0]
    template.block.external_mapping[VarPowerFlowReferenceType.Q] = machine_block.out_vars[1]
    template.block.in_vars = list((machine_block.in_vars[0], machine_block.in_vars[1]))
    template.block.out_vars = list((machine_block.out_vars[0], machine_block.out_vars[1]))
    template.block.name = name
    template.comment = 'Complete generator GENROU with IEEEX1, IEEEST, and TGOV1N RMS model'
    return template
