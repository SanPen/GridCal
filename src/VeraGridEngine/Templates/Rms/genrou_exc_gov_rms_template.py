# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Standard GENROU generator, TGOV1-family governor and exciter RMS models.

This module follows the complete-generator composition pattern already used by
VeraGrid: the synchronous machine, governor and selected exciter are independent
child blocks connected through a shared :class:`VarFactory`. Every physical
dynamic variable is an explicit ``state_var`` so RMS small-signal analysis sees
the complete standard-model realization.

The available blocks are GENROU, TGOV1, TGOV1N, EXST1 and the zero-TA structural
variant of ESST3A. Numerical case inventories remain outside this reusable
model module.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Dict
from typing import List

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym



class GenrouRmsParameters:
    """Numerical parameters for one GENROU synchronous machine."""

    __slots__ = ("fn", "d", "m", "ra", "xl", "xd1", "s10", "s12", "xd", "xq",
                 "xd2", "xq1", "xq2", "td10", "td20", "tq10", "tq20")

    def __init__(self: "GenrouRmsParameters", fn: float, d: float, m: float, ra: float, xl: float,
                 xd1: float, s10: float, s12: float, xd: float, xq: float,
                 xd2: float, xq1: float, xq2: float, td10: float, td20: float,
                 tq10: float, tq20: float) -> None:
        """Store one parsed GENROU record.

        :param fn: Nominal frequency.
        :param d: Damping coefficient.
        :param m: Inertia coefficient.
        :param ra: Armature resistance.
        :param xl: Leakage reactance.
        :param xd1: D-axis transient reactance.
        :param s10: Saturation point at 1.0 pu.
        :param s12: Saturation point at 1.2 pu.
        :param xd: D-axis synchronous reactance.
        :param xq: Q-axis synchronous reactance.
        :param xd2: D-axis subtransient reactance.
        :param xq1: Q-axis transient reactance.
        :param xq2: Q-axis subtransient reactance.
        :param td10: D-axis transient time constant.
        :param td20: D-axis subtransient time constant.
        :param tq10: Q-axis transient time constant.
        :param tq20: Q-axis subtransient time constant.
        :return: None.
        """
        self.fn: float = fn
        self.d: float = d
        self.m: float = m
        self.ra: float = ra
        self.xl: float = xl
        self.xd1: float = xd1
        self.s10: float = s10
        self.s12: float = s12
        self.xd: float = xd
        self.xq: float = xq
        self.xd2: float = xd2
        self.xq1: float = xq1
        self.xq2: float = xq2
        self.td10: float = td10
        self.td20: float = td20
        self.tq10: float = tq10
        self.tq20: float = tq20


class Tgov1RmsParameters:
    """Numerical parameters for one TGOV1 turbine governor."""

    __slots__ = ("wref0", "r", "vmax", "vmin", "t1", "t2", "t3", "dt")

    def __init__(self: "Tgov1RmsParameters", wref0: float, r: float, vmax: float, vmin: float,
                 t1: float, t2: float, t3: float, dt: float) -> None:
        """Store one parsed TGOV1 record.

        :param wref0: Frozen speed reference.
        :param r: Droop.
        :param vmax: Upper limiter.
        :param vmin: Lower limiter.
        :param t1: Lag time constant.
        :param t2: Lead time constant.
        :param t3: Lead-lag denominator time constant.
        :param dt: Turbine damping.
        :return: None.
        """
        self.wref0: float = wref0
        self.r: float = r
        self.vmax: float = vmax
        self.vmin: float = vmin
        self.t1: float = t1
        self.t2: float = t2
        self.t3: float = t3
        self.dt: float = dt


class Tgov1ModelType(Enum):
    """Power-reference placements in the standard TGOV1 model family."""

    TGOV1 = 1
    TGOV1N = 2


class Exst1RmsParameters:
    """Numerical parameters for one EXST1 excitation system."""

    __slots__ = ("tr", "vimax", "vimin", "tc", "tb", "ka", "ta", "vrmax",
                 "vrmin", "kc", "kf", "tf")

    def __init__(self: "Exst1RmsParameters", tr: float, vimax: float, vimin: float, tc: float,
                 tb: float, ka: float, ta: float, vrmax: float, vrmin: float,
                 kc: float, kf: float, tf: float) -> None:
        """Store one EXST1 workbook record.

        :param tr: Measurement lag time constant.
        :param vimax: Input upper limit.
        :param vimin: Input lower limit.
        :param tc: Lead time constant.
        :param tb: Lead-lag denominator time constant.
        :param ka: Regulator gain.
        :param ta: Regulator lag time constant.
        :param vrmax: Regulator upper limit.
        :param vrmin: Regulator lower limit.
        :param kc: Exciter compensation coefficient.
        :param kf: Washout gain.
        :param tf: Washout time constant.
        :return: None.
        """
        self.tr: float = tr
        self.vimax: float = vimax
        self.vimin: float = vimin
        self.tc: float = tc
        self.tb: float = tb
        self.ka: float = ka
        self.ta: float = ta
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.kc: float = kc
        self.kf: float = kf
        self.tf: float = tf


class Esst3aRmsParameters:
    """Numerical parameters for one ESST3A excitation system."""

    __slots__ = ("tr", "vimax", "vimin", "km", "tc", "tb", "ka", "ta",
                 "vrmax", "vrmin", "kg", "kp", "ki", "vbmax", "kc", "xl",
                 "vgmax", "thetap", "tm", "vmmax", "vmmin")

    def __init__(self: "Esst3aRmsParameters", tr: float, vimax: float, vimin: float, km: float,
                 tc: float, tb: float, ka: float, ta: float, vrmax: float,
                 vrmin: float, kg: float, kp: float, ki: float, vbmax: float,
                 kc: float, xl: float, vgmax: float, thetap: float, tm: float,
                 vmmax: float, vmmin: float) -> None:
        """Store one ESST3A workbook record.

        :param tr: Measurement lag time constant.
        :param vimax: Input upper limit.
        :param vimin: Input lower limit.
        :param km: Final regulator gain.
        :param tc: Lead time constant.
        :param tb: Lead-lag denominator time constant.
        :param ka: Regulator gain.
        :param ta: LAW1 time constant.
        :param vrmax: Regulator upper limit.
        :param vrmin: Regulator lower limit.
        :param kg: Feedback gain.
        :param kp: Potential-circuit active coefficient.
        :param ki: Potential-circuit reactive coefficient.
        :param vbmax: Rectifier output upper limit.
        :param kc: Commutation-reactance coefficient.
        :param xl: Potential-circuit reactance.
        :param vgmax: Feedback upper limit.
        :param thetap: Potential-circuit angle.
        :param tm: LAW2 time constant.
        :param vmmax: Internal signal upper limit.
        :param vmmin: Internal signal lower limit.
        :return: None.
        """
        self.tr: float = tr
        self.vimax: float = vimax
        self.vimin: float = vimin
        self.km: float = km
        self.tc: float = tc
        self.tb: float = tb
        self.ka: float = ka
        self.ta: float = ta
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.kg: float = kg
        self.kp: float = kp
        self.ki: float = ki
        self.vbmax: float = vbmax
        self.kc: float = kc
        self.xl: float = xl
        self.vgmax: float = vgmax
        self.thetap: float = thetap
        self.tm: float = tm
        self.vmmax: float = vmmax
        self.vmmin: float = vmmin




class GenrouExciterType(Enum):
    """Excitation-system structures supported by complete GENROU models."""

    EXST1 = 1
    ESST3A = 2


class GenrouSaturationMode(Enum):
    """Structural magnetic-saturation realizations supported by GENROU."""

    QUADRATIC = 1
    DISABLED = 2
    POWER_LAW = 3


def _add_parameter(
    block: Block,
    vfactory: VarFactory,
    name: str,
    value: float | None,
) -> Var:
    """Create one named model parameter and register it in ``event_dict``.

    :param block: Block that owns the parameter.
    :param vfactory: Shared symbolic variable factory.
    :param name: Standard model parameter name.
    :param value: Initial/default numerical value. ``None`` marks a value that is
                  populated from ``init_eqs``.
    :return: Parameter variable.
    """
    parameter: Var = vfactory.add_var(name)
    block.event_dict[parameter] = vfactory.add_const(value=value, name=name)
    return parameter


def _anti_windup_state_derivative(
    state_var: Var,
    raw_derivative: Expr,
    lower_limit: Expr,
    upper_limit: Expr,
) -> Expr:
    """Project one state derivative onto its admissible limiter interval.

    This reproduces the directional behavior of the ANDES ``AntiWindup``
    discrete element. At either bound, an outward derivative is blocked while
    an inward derivative remains active. A zero derivative remains on the
    interior linearization branch so the equilibrium Jacobian is not changed
    merely because an initialized state is exactly equal to one limit.

    :param state_var: Limited differential state.
    :param raw_derivative: Unconstrained state derivative.
    :param lower_limit: Minimum admissible state value.
    :param upper_limit: Maximum admissible state value.
    :return: Directionally limited state derivative.
    """
    # VeraGrid's Heaviside function is one only for a strictly positive input.
    # Its complement therefore detects a state that is equal to or outside a
    # bound, while preserving an ordinary interior derivative elsewhere.
    at_or_below_lower: Expr = sym.Const(1.0) - sym.heaviside(state_var - lower_limit)
    at_or_above_upper: Expr = sym.Const(1.0) - sym.heaviside(upper_limit - state_var)

    # Direction flags are deliberately strict. At an exact equilibrium where
    # the raw derivative is zero, both flags remain zero and small-signal
    # linearization follows the same interior branch as ANDES.
    moving_below_lower: Expr = sym.heaviside(-raw_derivative)
    moving_above_upper: Expr = sym.heaviside(raw_derivative)
    freeze_at_lower: Expr = at_or_below_lower * moving_below_lower
    freeze_at_upper: Expr = at_or_above_upper * moving_above_upper
    integration_gate: Expr = (
        (sym.Const(1.0) - freeze_at_lower)
        * (sym.Const(1.0) - freeze_at_upper)
    )
    return raw_derivative * integration_gate


def set_rms_model_parameter(
    block: Block,
    parameter_name: str,
    value: float,
    vfactory: VarFactory,
) -> None:
    """Set exactly one named static or event parameter.

    The function fails if the parameter is absent or duplicated so an explicit
    model configuration can never leave a default active silently.

    :param block: Block whose parameter will be changed.
    :param parameter_name: Exact symbolic parameter name.
    :param value: New numerical value.
    :param vfactory: Shared symbolic variable factory.
    :return: None.
    :raises ValueError: If exactly one parameter is not found.
    """
    matching_parameters: List[Var] = list()
    parameter: Var
    for parameter in list(block.parameters) + list(block.event_dict):
        if parameter.name == parameter_name:
            matching_parameters.append(parameter)
        else:
            pass

    if len(matching_parameters) != 1:
        raise ValueError(
            f"Expected exactly one parameter named '{parameter_name}' in block "
            f"'{block.name}', found {len(matching_parameters)}."
        )
    else:
        pass

    target = matching_parameters[0]
    destination = block.parameters if target in block.parameters else block.event_dict
    destination[target] = vfactory.add_const(
        value=value,
        name=parameter_name,
    )



def _set_named_parameters(
    block: Block,
    values: Dict[str, float],
    vfactory: VarFactory,
) -> None:
    """Apply a complete named parameter mapping to one model block.

    :param block: Block to configure.
    :param values: Exact ``parameter_name -> value`` mapping.
    :param vfactory: Shared symbolic variable factory.
    :return: None.
    """
    parameter_name: str
    parameter_value: float
    for parameter_name, parameter_value in values.items():
        set_rms_model_parameter(
            block=block,
            parameter_name=parameter_name,
            value=parameter_value,
            vfactory=vfactory,
        )


def configure_genrou_block(
    block: Block,
    parameters: GenrouRmsParameters,
    vfactory: VarFactory,
) -> None:
    """Configure one GENROU block from named model parameters."""
    _set_named_parameters(
        block,
        dict(
            fn=parameters.fn,
            D=parameters.d,
            M=parameters.m,
            Ra=parameters.ra,
            Xl=parameters.xl,
            Xd_prime=parameters.xd1,
            S10=parameters.s10,
            S12=parameters.s12,
            Xd=parameters.xd,
            Xq=parameters.xq,
            Xd_2prime=parameters.xd2,
            Xq_prime=parameters.xq1,
            Xq_2prime=parameters.xq2,
            Td0_prime=parameters.td10,
            Td0_2prime=parameters.td20,
            Tq0_prime=parameters.tq10,
            Tq0_2prime=parameters.tq20,
        ),
        vfactory,
    )


def configure_tgov1_block(
    block: Block,
    parameters: Tgov1RmsParameters,
    vfactory: VarFactory,
) -> None:
    """Configure one TGOV1 block from named model parameters."""
    _set_named_parameters(
        block,
        dict(
            wref=parameters.wref0,
            R=parameters.r,
            VMAX=parameters.vmax,
            VMIN=parameters.vmin,
            T1=parameters.t1,
            T2=parameters.t2,
            T3=parameters.t3,
            Dt=parameters.dt,
        ),
        vfactory,
    )


def configure_exst1_block(
    block: Block,
    parameters: Exst1RmsParameters,
    vfactory: VarFactory,
) -> None:
    """Configure one EXST1 block from named model parameters."""
    _set_named_parameters(
        block,
        dict(
            TR=parameters.tr,
            VIMAX=parameters.vimax,
            VIMIN=parameters.vimin,
            TC=parameters.tc,
            TB=parameters.tb,
            KA=parameters.ka,
            TA=parameters.ta,
            VRMAX=parameters.vrmax,
            VRMIN=parameters.vrmin,
            KC=parameters.kc,
            KF=parameters.kf,
            TF=parameters.tf,
        ),
        vfactory,
    )


def configure_esst3a_block(
    block: Block,
    parameters: Esst3aRmsParameters,
    vfactory: VarFactory,
) -> None:
    """Configure one ESST3A block from named model parameters."""
    _set_named_parameters(
        block,
        dict(
            TR=parameters.tr,
            VIMAX=parameters.vimax,
            VIMIN=parameters.vimin,
            KM=parameters.km,
            TC=parameters.tc,
            TB=parameters.tb,
            KA=parameters.ka,
            TA=parameters.ta,
            VRMAX=parameters.vrmax,
            VRMIN=parameters.vrmin,
            KG=parameters.kg,
            KP=parameters.kp,
            KI=parameters.ki,
            VBMAX=parameters.vbmax,
            KC=parameters.kc,
            XL=parameters.xl,
            VGMAX=parameters.vgmax,
            THETAP=parameters.thetap,
            TM=parameters.tm,
            VMMAX=parameters.vmmax,
            VMMIN=parameters.vmmin,
        ),
        vfactory,
    )



def _quadratic_saturation_coefficients(
    s10: Expr,
    s12: Expr,
) -> tuple[Expr, Expr]:
    """Return quadratic GENROU saturation coefficients.

    ``S10=0`` and ``S12=1`` yield ``SAT_A=1`` and ``SAT_B=0``, so saturation
    is disabled explicitly.

    :param s10: Saturation factor at 1.0 pu flux.
    :param s12: Saturation factor at 1.2 pu flux.
    :return: Tuple ``(SAT_A, SAT_B)``.
    """
    e1: Const = sym.Const(1.0)
    e2: Const = sym.Const(1.2)
    sat_ratio: Expr = sym.sqrt((s10 * e1) / (s12 * e2))
    sat_a: Expr = e2 - (e1 - e2) / (sat_ratio - sym.Const(1.0))

    # The zero-ratio branch must disable the quadratic gain. The symbolic
    # Heaviside is constant around practical non-zero ratios and preserves the
    # intended small-signal derivative.
    nonzero_ratio: Expr = sym.heaviside(
        sym.abs(sat_ratio) - sym.Const(1.0e-12)
    )
    sat_b: Expr = (
        nonzero_ratio
        * s12
        * e2
        * (sat_ratio - sym.Const(1.0)) ** 2
        / (e1 - e2) ** 2
    )
    return sat_a, sat_b



def _esst3a_fex(in_var: Expr, first_boundary: Expr | None = None,
                middle_boundary: Expr | None = None, first_slope: Expr | None = None,
                last_slope: Expr | None = None) -> Expr:
    """Return the standard ESST3A commutating-reactance function ``FEX``.

    The function uses five pieces with breakpoints 0, 0.433, 0.75 and 1.0. The
    Heaviside representation keeps the active formula in each open interval;
    the final linear region includes its lower boundary at 0.75.

    :param in_var: ESST3A normalized field-current variable ``IN``.
    :param first_boundary: Optional calibrated first transition, default 0.433.
    :param middle_boundary: Optional middle intercept/transition, default 0.75.
    :param first_slope: Optional linear commutation slope, default 0.577.
    :param last_slope: Optional final-region slope, default 1.732.
    :return: Piecewise ``FEX`` expression.
    """
    low: Expr = sym.Const(0.433) if first_boundary is None else first_boundary
    high: Expr = sym.Const(0.75) if middle_boundary is None else middle_boundary
    slope1: Expr = sym.Const(0.577) if first_slope is None else first_slope
    slope3: Expr = sym.Const(1.732) if last_slope is None else last_slope
    h0: Expr = sym.heaviside(in_var)
    h0433: Expr = sym.heaviside(in_var - low)
    h075: Expr = sym.Const(1.0)-sym.heaviside(high-in_var)
    h1: Expr = sym.heaviside(in_var - sym.Const(1.0))

    f0: Expr = sym.Const(1.0)
    f1: Expr = sym.Const(1.0) - slope1 * in_var
    # Inactive branches are still evaluated by symbolic kernels. A unit
    # radicand outside this region keeps both values and Jacobians finite;
    # max(0, ...) alone would leave a removable 0/sqrt(0) in the derivative.
    middle_gate: Expr = h0433-h075
    sqrt_argument: Expr = sym.Const(1.0)+middle_gate*(high-in_var*in_var-sym.Const(1.0))
    f2: Expr = sym.sqrt(sqrt_argument)
    f3: Expr = slope3 * (sym.Const(1.0) - in_var)

    return (
        (sym.Const(1.0) - h0) * f0
        + (h0 - h0433) * f1
        + (h0433 - h075) * f2
        + (h075 - h1) * f3
    )


def _genrou_initial_expressions(
    vm_var: Var,
    va_var: Var,
    pg_var: Var,
    qg_var: Var,
    ra_var: Var,
    xd_var: Var,
    xq_var: Var,
    xd1_var: Var,
    xq1_var: Var,
    xd2_var: Var,
    xq2_var: Var,
    xl_var: Var,
    gd1_expr: Expr,
    gd2_expr: Expr,
    gqd_expr: Expr,
    sat_a_expr: Expr,
    sat_b_expr: Expr,
    s10_var: Var,
    s12_var: Var,
    saturation_mode: GenrouSaturationMode,
) -> Dict[str, Expr]:
    """Build consistent steady-state GENROU initialization expressions.

    :param vm_var: Terminal voltage magnitude.
    :param va_var: Terminal voltage angle.
    :param pg_var: Initial active power injection.
    :param qg_var: Initial reactive power injection.
    :param ra_var: Armature resistance.
    :param xd_var: d-axis synchronous reactance.
    :param xq_var: q-axis synchronous reactance.
    :param xd1_var: d-axis transient reactance.
    :param xq1_var: q-axis transient reactance.
    :param xd2_var: d-axis sub-transient reactance.
    :param xq2_var: q-axis sub-transient reactance.
    :param xl_var: Leakage reactance.
    :param gd1_expr: GENROU gamma d1 coefficient.
    :param gd2_expr: GENROU gamma d2 coefficient.
    :param gqd_expr: GENROU gamma qd coefficient.
    :param sat_a_expr: Quadratic saturation threshold.
    :param sat_b_expr: Quadratic saturation gain.
    :param s10_var: Saturation factor at unit resultant flux.
    :param s12_var: Saturation factor at resultant flux 1.2 pu.
    :param saturation_mode: Explicit physical saturation characteristic.
    :return: Named initialization expressions.
    """
    voltage_complex: Expr = vm_var * sym.exp(1j * va_var)
    terminal_current: Expr = sym.conj(
        (pg_var + 1j * qg_var) / voltage_complex
    )
    stator_impedance: Expr = ra_var + 1j * xd2_var
    psi20_complex: Expr = voltage_complex + terminal_current * stator_impedance
    psi20_abs: Expr = sym.abs(psi20_complex)
    psi20_arg: Expr = sym.imag(sym.log(psi20_complex))
    # Resolve current components directly: its phase is undefined at zero P/Q,
    # although the winding equilibrium itself remains perfectly well defined.
    current_in_flux_frame: Expr = terminal_current * sym.exp(-1j * psi20_arg)

    se0: Expr
    if saturation_mode is GenrouSaturationMode.POWER_LAW:
        se0 = s10_var*psi20_abs**(sym.log(s12_var/s10_var)/sym.log(sym.Const(1.2)))
    else:
        se0 = (sym.heaviside(psi20_abs-sat_a_expr)
            *(psi20_abs-sat_a_expr)**2*sat_b_expr/psi20_abs)
    delta_a: Expr = psi20_abs * (sym.Const(1.0) + se0 * gqd_expr)
    reactance_difference: Expr = xq2_var - xq_var
    delta0: Expr = (
        sym.atan(
            reactance_difference
            * sym.real(current_in_flux_frame)
            / (
                -reactance_difference * sym.imag(current_in_flux_frame)
                - delta_a
            )
        )
        + psi20_arg
    )

    tdq: Expr = sym.cos(delta0) - 1j * sym.sin(delta0)
    psi20_dq: Expr = psi20_complex * tdq
    current_dq: Expr = sym.conj(terminal_current * tdq)

    psi2d0: Expr = sym.real(psi20_dq)
    psi2q0: Expr = -sym.imag(psi20_dq)
    id0: Expr = sym.imag(current_dq)
    iq0: Expr = sym.real(current_dq)
    vd0: Expr = psi2q0 + xq2_var * iq0 - ra_var * id0
    vq0: Expr = psi2d0 - xd2_var * id0 - ra_var * iq0
    tm0: Expr = (
        (vq0 + ra_var * iq0) * iq0
        + (vd0 + ra_var * id0) * id0
    )
    vf0: Expr = (
        (se0 + sym.Const(1.0)) * psi2d0
        + (xd_var - xd2_var) * id0
    )
    psid0: Expr = ra_var * iq0 + vq0
    psiq0: Expr = -ra_var * id0 - vd0
    e1q0: Expr = (
        id0 * (-xd_var + xd1_var)
        - se0 * psi2d0
        + vf0
    )
    e1d0: Expr = (
        iq0 * (xq_var - xq1_var)
        - se0 * gqd_expr * psi2q0
    )
    e2d0: Expr = (
        id0 * (xl_var - xd_var)
        - se0 * psi2d0
        + vf0
    )
    e2q0: Expr = (
        -iq0 * (xl_var - xq_var)
        - se0 * gqd_expr * psi2q0
    )
    xadifd0: Expr = (
        e1q0
        + (xd_var - xd1_var)
        * (
            gd1_expr * id0
            - gd2_expr * e2d0
            + gd2_expr * e1q0
        )
        + se0 * psi2d0
    )

    initial_values: Dict[str, Expr] = dict()
    initial_values["delta"] = delta0
    initial_values["omega"] = sym.Const(1.0)
    initial_values["Id"] = id0
    initial_values["Iq"] = iq0
    initial_values["Vd"] = vd0
    initial_values["Vq"] = vq0
    initial_values["psi2d"] = psi2d0
    initial_values["psi2q"] = psi2q0
    initial_values["psi2"] = sym.sqrt(psi2d0 ** 2 + psi2q0 ** 2)
    initial_values["Se"] = se0
    initial_values["psid"] = psid0
    initial_values["psiq"] = psiq0
    initial_values["Te"] = tm0
    initial_values["Tm"] = tm0
    initial_values["Vf"] = vf0
    initial_values["XadIfd"] = xadifd0
    # At equilibrium de1d/dt = -XaqI1q/Tq0' = 0.
    initial_values["XaqI1q"] = sym.Const(0.0)
    initial_values["e1q"] = e1q0
    initial_values["e1d"] = e1d0
    initial_values["e2d"] = e2d0
    initial_values["e2q"] = e2q0
    return initial_values


def get_genrou_rms_template(
    vfactory: VarFactory,
    name: str = "GENROU RMS template",
    saturation_mode: GenrouSaturationMode = GenrouSaturationMode.QUADRATIC,
) -> RmsModelTemplate:
    """Build a standard six-state GENROU synchronous-machine model.

    :param vfactory: Shared symbolic variable factory.
    :param name: Template name.
    :param saturation_mode: Magnetic-saturation structural realization.
    :return: RMS template containing one GENROU block.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice

    vm_var: Var = vfactory.add_var(
        "Vm",
        reference=VarPowerFlowReferenceType.Vm,
    )
    va_var: Var = vfactory.add_var(
        "Va",
        reference=VarPowerFlowReferenceType.Va,
    )
    tm_var: Var = vfactory.add_var(
        "Tm",
        shared_reference="tm_reference",
    )
    vf_var: Var = vfactory.add_var(
        "Vf",
        shared_reference="vf_reference",
    )

    pg_var: Var = vfactory.add_var(
        "Pg",
        reference=VarPowerFlowReferenceType.P,
    )
    qg_var: Var = vfactory.add_var(
        "Qg",
        reference=VarPowerFlowReferenceType.Q,
    )

    delta_var: Var = vfactory.add_var("delta", shared_reference="delta_reference")
    omega_var: Var = vfactory.add_var("omega", shared_reference="omega_reference")
    e1q_var: Var = vfactory.add_var("e1q")
    e1d_var: Var = vfactory.add_var("e1d")
    e2d_var: Var = vfactory.add_var("e2d")
    e2q_var: Var = vfactory.add_var("e2q")

    id_var: Var = vfactory.add_var("Id", shared_reference="id_reference")
    iq_var: Var = vfactory.add_var("Iq", shared_reference="iq_reference")
    vd_var: Var = vfactory.add_var("Vd", shared_reference="vd_reference")
    vq_var: Var = vfactory.add_var("Vq", shared_reference="vq_reference")
    te_var: Var = vfactory.add_var("Te", shared_reference="te_reference")
    xadifd_var: Var = vfactory.add_var(
        "XadIfd",
        shared_reference="irpu_reference",
    )
    xadi1q_var: Var = vfactory.add_var("XaqI1q")
    psid_var: Var = vfactory.add_var("psid")
    psiq_var: Var = vfactory.add_var("psiq")
    psi2d_var: Var = vfactory.add_var("psi2d")
    psi2q_var: Var = vfactory.add_var("psi2q")
    psi2_var: Var = vfactory.add_var("psi2")
    se_var: Var = vfactory.add_var("Se")

    block: Block = Block(name=name)

    fn_var: Var = vfactory.add_var("fn")
    block.parameters[fn_var] = vfactory.add_const(60.0)
    block.api_obj_mapping[ParamPowerFlowReferenceType.freq] = fn_var
    ws_expr: Expr = sym.Const(2.0 * math.pi) * fn_var
    m_var: Var = _add_parameter(block, vfactory, "M", 8.0)
    d_var: Var = _add_parameter(block, vfactory, "D", 0.0)
    ra_var: Var = _add_parameter(block, vfactory, "Ra", 0.0)
    xd_var: Var = _add_parameter(block, vfactory, "Xd", 1.8)
    xq_var: Var = _add_parameter(block, vfactory, "Xq", 1.75)
    xd1_var: Var = _add_parameter(block, vfactory, "Xd_prime", 0.6)
    xq1_var: Var = _add_parameter(block, vfactory, "Xq_prime", 0.8)
    xd2_var: Var = _add_parameter(block, vfactory, "Xd_2prime", 0.23)
    xq2_var: Var = _add_parameter(block, vfactory, "Xq_2prime", 0.23)
    td10_var: Var = _add_parameter(block, vfactory, "Td0_prime", 6.5)
    td20_var: Var = _add_parameter(block, vfactory, "Td0_2prime", 0.06)
    tq10_var: Var = _add_parameter(block, vfactory, "Tq0_prime", 0.2)
    tq20_var: Var = _add_parameter(block, vfactory, "Tq0_2prime", 0.05)
    xl_var: Var = _add_parameter(block, vfactory, "Xl", 0.15)
    s10_var: Var = _add_parameter(block, vfactory, "S10", 0.09)
    s12_var: Var = _add_parameter(block, vfactory, "S12", 0.38)
    psi2_diag_ref_var: Var = _add_parameter(block, vfactory, "psi2_diag_ref", None)
    se_diag_ref_var: Var = _add_parameter(block, vfactory, "Se_diag_ref", None)
    diag_eps_expr: Expr = sym.Const(1.0e-8)

    gd1_expr: Expr = (xd2_var - xl_var) / (xd1_var - xl_var)
    gq1_expr: Expr = (xq2_var - xl_var) / (xq1_var - xl_var)
    gd2_expr: Expr = (xd1_var - xd2_var) / (xd1_var - xl_var) ** 2
    gq2_expr: Expr = (xq1_var - xq2_var) / (xq1_var - xl_var) ** 2
    gqd_expr: Expr = (xq_var - xl_var) / (xd_var - xl_var)
    # A disabled saturation is a structural model choice. Substituting
    # S10=S12=0 into the quadratic fit would evaluate an undefined 0/0 ratio.
    if saturation_mode is GenrouSaturationMode.QUADRATIC:
        sat_a_expr, sat_b_expr = _quadratic_saturation_coefficients(s10_var, s12_var)
        saturation_excess: Expr = sym.heaviside(psi2_var-sat_a_expr)*(psi2_var-sat_a_expr)**2*sat_b_expr
    elif saturation_mode is GenrouSaturationMode.POWER_LAW:
        sat_a_expr = sym.Const(0.0)
        sat_b_expr = sym.Const(0.0)
        # Magnitude is nonnegative physically. A signed real continuation keeps
        # fractional powers finite if a Newton trial crosses its zero boundary.
        saturation_excess = s10_var*(sym.Const(2.0)*sym.heaviside(psi2_var)-sym.Const(1.0))*sym.max(psi2_var,-psi2_var)**(
            sym.Const(1.0)+sym.log(s12_var/s10_var)/sym.log(sym.Const(1.2)))
    else:
        sat_a_expr = sym.Const(1.0)
        sat_b_expr = sym.Const(0.0)
        saturation_excess = sym.Const(0.0)

    block.state_vars = list((
        delta_var,
        omega_var,
        e1q_var,
        e1d_var,
        e2d_var,
        e2q_var,
    ))
    block.state_eqs = list((
        ws_expr * (omega_var - sym.Const(1.0)),
        (tm_var - te_var - d_var * (omega_var - sym.Const(1.0))) / m_var,
        (vf_var - xadifd_var) / td10_var,
        (-xadi1q_var) / tq10_var,
        (-e2d_var + e1q_var - (xd1_var - xl_var) * id_var) / td20_var,
        (-e2q_var + e1d_var + (xq1_var - xl_var) * iq_var) / tq20_var,
    ))

    block.algebraic_vars = list((
        vd_var,
        vq_var,
        id_var,
        iq_var,
        pg_var,
        qg_var,
        psid_var,
        psiq_var,
        te_var,
        psi2d_var,
        psi2q_var,
        psi2_var,
        se_var,
        xadifd_var,
        xadi1q_var,
    ))
    block.algebraic_eqs = list((
        vm_var * sym.sin(delta_var - va_var) - vd_var,
        vm_var * sym.cos(delta_var - va_var) - vq_var,
        xd2_var * id_var - psi2d_var + psid_var,
        xq2_var * iq_var + psi2q_var + psiq_var,
        vd_var * id_var + vq_var * iq_var - pg_var,
        vq_var * id_var - vd_var * iq_var - qg_var,
        ra_var * iq_var + vq_var - psid_var,
        ra_var * id_var + vd_var + psiq_var,
        psid_var * iq_var - psiq_var * id_var - te_var,
        gd1_expr * e1q_var
        + gd2_expr * (xd1_var - xl_var) * e2d_var
        - psi2d_var,
        gq1_expr * e1d_var
        + (sym.Const(1.0) - gq1_expr) * e2q_var
        - psi2q_var,
        psi2d_var ** 2
        + psi2q_var ** 2
        - psi2_var ** 2
        + diag_eps_expr * (psi2_var - psi2_diag_ref_var),
        saturation_excess
        - psi2_var * se_var
        + diag_eps_expr * (se_var - se_diag_ref_var),
        e1q_var
        + (xd_var - xd1_var)
        * (
            gd1_expr * id_var
            - gd2_expr * e2d_var
            + gd2_expr * e1q_var
        )
        + se_var * psi2d_var
        - xadifd_var,
        e1d_var
        + (xq_var - xq1_var)
        * (
            gq2_expr * e1d_var
            - gq2_expr * e2q_var
            - gq1_expr * iq_var
        )
        + se_var * psi2q_var * gqd_expr
        - xadi1q_var,
    ))

    initial: Dict[str, Expr] = _genrou_initial_expressions(
        vm_var=vm_var,
        va_var=va_var,
        pg_var=pg_var,
        qg_var=qg_var,
        ra_var=ra_var,
        xd_var=xd_var,
        xq_var=xq_var,
        xd1_var=xd1_var,
        xq1_var=xq1_var,
        xd2_var=xd2_var,
        xq2_var=xq2_var,
        xl_var=xl_var,
        gd1_expr=gd1_expr,
        gd2_expr=gd2_expr,
        gqd_expr=gqd_expr,
        sat_a_expr=sat_a_expr,
        sat_b_expr=sat_b_expr,
        s10_var=s10_var,
        s12_var=s12_var,
        saturation_mode=saturation_mode,
    )
    block.init_eqs = dict()
    block.init_eqs[delta_var] = initial["delta"]
    block.init_eqs[omega_var] = initial["omega"]
    block.init_eqs[id_var] = initial["Id"]
    block.init_eqs[iq_var] = initial["Iq"]
    block.init_eqs[vd_var] = initial["Vd"]
    block.init_eqs[vq_var] = initial["Vq"]
    block.init_eqs[psi2d_var] = initial["psi2d"]
    block.init_eqs[psi2q_var] = initial["psi2q"]
    block.init_eqs[psi2_var] = initial["psi2"]
    block.init_eqs[se_var] = initial["Se"]
    block.init_eqs[psi2_diag_ref_var] = initial["psi2"]
    block.init_eqs[se_diag_ref_var] = initial["Se"]
    block.init_eqs[psid_var] = initial["psid"]
    block.init_eqs[psiq_var] = initial["psiq"]
    block.init_eqs[te_var] = initial["Te"]
    block.init_eqs[tm_var] = initial["Tm"]
    block.init_eqs[vf_var] = initial["Vf"]
    block.init_eqs[xadifd_var] = initial["XadIfd"]
    block.init_eqs[e1d_var] = initial["e1d"]
    block.init_eqs[xadi1q_var] = initial["XaqI1q"]
    block.init_eqs[e1q_var] = initial["e1q"]
    block.init_eqs[e2d_var] = initial["e2d"]
    block.init_eqs[e2q_var] = initial["e2q"]

    block.in_vars = list((vm_var, va_var, tm_var, vf_var))
    block.out_vars = list((
        pg_var,
        qg_var,
        omega_var,
        xadifd_var,
        te_var,
        vd_var,
        vq_var,
        id_var,
        iq_var,
    ))
    block.external_mapping = dict()
    block.external_mapping[VarPowerFlowReferenceType.Vm] = vm_var
    block.external_mapping[VarPowerFlowReferenceType.Va] = va_var
    block.external_mapping[VarPowerFlowReferenceType.P] = pg_var
    block.external_mapping[VarPowerFlowReferenceType.Q] = qg_var

    template.block.children.append(block)
    template.block.external_mapping = dict(block.external_mapping)
    template.block.in_vars = list((vm_var, va_var))
    template.block.out_vars = list((pg_var, qg_var))
    template.block.name = name
    template.comment = 'Generator GENROU RMS model'
    return template


def get_tgov1_rms_template(
    vfactory: VarFactory,
    name: str = "TGOV1 RMS template",
    model_type: Tgov1ModelType = Tgov1ModelType.TGOV1,
) -> RmsModelTemplate:
    """Build a standard two-state TGOV1-family governor realization.

    ``TGOV1`` applies the droop gain after summing speed, reference and
    auxiliary inputs. ``TGOV1N`` applies droop only to speed and sums power
    references afterwards, as required by the IEEE39 reference data.
    The valve lag uses directional anti-windup at ``VMIN`` and ``VMAX`` so an
    outward derivative freezes the state while an inward derivative releases it.

    The second input is the machine electrical torque and is used only to
    initialize the frozen ``pref0``/mechanical-power reference.

    :param vfactory: Shared symbolic variable factory.
    :param name: Template name.
    :param model_type: Standard TGOV1-family equation selection.
    :return: RMS template containing one TGOV1-family block.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice

    omega_var: Var = vfactory.add_var(
        "omega_",
        shared_reference="omega_reference",
    )
    te_var: Var = vfactory.add_var(
        "Te_",
        shared_reference="te_reference",
    )
    tm_var: Var = vfactory.add_var(
        "Tm",
        shared_reference="tm_reference",
    )

    lag_state_var: Var = vfactory.add_var("LAG_y")
    ll_state_var: Var = vfactory.add_var("LL_x")
    pref_var: Var = vfactory.add_var("pref")
    wd_var: Var = vfactory.add_var("wd")
    pd_var: Var = vfactory.add_var("pd")
    ll_y_var: Var = vfactory.add_var("LL_y")

    block: Block = Block(name=name)
    r_var: Var = _add_parameter(block, vfactory, "R", 0.05)
    vmax_var: Var = _add_parameter(block, vfactory, "VMAX", 1.2)
    vmin_var: Var = _add_parameter(block, vfactory, "VMIN", 0.0)
    t1_var: Var = _add_parameter(block, vfactory, "T1", 0.1)
    t2_var: Var = _add_parameter(block, vfactory, "T2", 1.0)
    t3_var: Var = _add_parameter(block, vfactory, "T3", 2.1)
    dt_var: Var = _add_parameter(block, vfactory, "Dt", 0.0)
    wref_var: Var = _add_parameter(block, vfactory, "wref", 1.0)
    pref0_var: Var = _add_parameter(block, vfactory, "pref0", None)
    paux_var: Var = _add_parameter(block, vfactory, "paux", 0.0)
    ll_y_diag_ref_var: Var = _add_parameter(block, vfactory, "LL_y_diag_ref", None)
    diag_eps_expr: Expr = sym.Const(1.0e-8)

    # TGOV1 uses the standard directional anti-windup lag. This matters when
    # the operating point lies exactly on VMIN/VMAX: an outward disturbance
    # must freeze LAG_y, whereas a returning disturbance must release it.
    lag_raw_derivative: Expr = (pd_var - lag_state_var) / t1_var
    lag_limited_derivative: Expr = _anti_windup_state_derivative(
        state_var=lag_state_var,
        raw_derivative=lag_raw_derivative,
        lower_limit=vmin_var,
        upper_limit=vmax_var,
    )
    block.state_vars = list((lag_state_var, ll_state_var))
    block.state_eqs = list((
        lag_limited_derivative,
        (lag_state_var - ll_state_var) / t3_var,
    ))
    # TGOV1N moves the power references after the droop gain. This structural
    # choice cannot be reproduced by parameter scaling alone.
    if model_type is Tgov1ModelType.TGOV1:
        reference_equation: Expr = pref0_var * r_var - pref_var
        power_demand_equation: Expr = (
            -wd_var / r_var + pref_var / r_var + paux_var / r_var - pd_var
        )
        initial_reference: Expr = tm_var * r_var
    else:
        reference_equation = pref0_var - pref_var
        power_demand_equation = -wd_var / r_var + pref_var + paux_var - pd_var
        initial_reference = tm_var

    block.algebraic_vars = list((pref_var, wd_var, pd_var, ll_y_var, tm_var))
    block.algebraic_eqs = list((
        reference_equation,
        omega_var - wref_var - wd_var,
        power_demand_equation,
        t2_var / t3_var * (lag_state_var - ll_state_var)
        + ll_state_var
        - ll_y_var
        + diag_eps_expr / t3_var * (ll_y_var - ll_y_diag_ref_var),
        ll_y_var - dt_var * wd_var - tm_var,
    ))
    block.init_eqs = dict()
    block.init_eqs[pref0_var] = tm_var
    block.init_eqs[pref_var] = initial_reference
    block.init_eqs[wd_var] = sym.Const(0.0)
    block.init_eqs[pd_var] = tm_var
    block.init_eqs[lag_state_var] = tm_var
    block.init_eqs[ll_state_var] = tm_var
    block.init_eqs[ll_y_var] = tm_var
    block.init_eqs[ll_y_diag_ref_var] = tm_var
    block.in_vars = list((omega_var, te_var))
    block.out_vars = list((tm_var,))

    template.block.children.append(block)
    template.block.in_vars = list((omega_var, te_var))
    template.block.out_vars = list((tm_var,))
    template.block.name = name
    template.comment = 'Generator TGOV1 turbine-governor RMS model'
    return template


def get_exst1_rms_template(
    vfactory: VarFactory,
    name: str = "EXST1 RMS template",
) -> RmsModelTemplate:
    """Build EXST1 with explicit dynamic states and initialized ``vref0``.

    :param vfactory: Shared symbolic variable factory.
    :param name: Template name.
    :return: RMS template containing one EXST1 block.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice

    xadifd_var: Var = vfactory.add_var(
        "XadIfd_",
        shared_reference="irpu_reference",
    )
    vm_var: Var = vfactory.add_var(
        "Vm_",
        reference=VarPowerFlowReferenceType.Vm,
    )
    vf_var: Var = vfactory.add_var(
        "Vf",
        shared_reference="vf_reference",
    )

    lg_state_var: Var = vfactory.add_var("LG_y")
    ll_state_var: Var = vfactory.add_var("LL_x")
    lr_state_var: Var = vfactory.add_var("LR_y")
    wf_state_var: Var = vfactory.add_var("WF_x")
    wf_y_var: Var = vfactory.add_var("WF_y")
    vpss_var: Var = vfactory.add_var("vpss")
    vref_var: Var = vfactory.add_var("vref")
    vi_var: Var = vfactory.add_var("vi")
    vl_var: Var = vfactory.add_var("vl")
    ll_y_var: Var = vfactory.add_var("LL_y")
    vfmax_var: Var = vfactory.add_var("vfmax")
    vfmin_var: Var = vfactory.add_var("vfmin")

    block: Block = Block(name=name)
    tr_var: Var = _add_parameter(block, vfactory, "TR", 0.02)
    vimax_var: Var = _add_parameter(block, vfactory, "VIMAX", 99.0)
    vimin_var: Var = _add_parameter(block, vfactory, "VIMIN", -99.0)
    tc_var: Var = _add_parameter(block, vfactory, "TC", 0.0)
    tb_var: Var = _add_parameter(block, vfactory, "TB", 0.02)
    ka_var: Var = _add_parameter(block, vfactory, "KA", 50.0)
    ta_var: Var = _add_parameter(block, vfactory, "TA", 0.02)
    vrmax_var: Var = _add_parameter(block, vfactory, "VRMAX", 9999.0)
    vrmin_var: Var = _add_parameter(block, vfactory, "VRMIN", -9999.0)
    kc_var: Var = _add_parameter(block, vfactory, "KC", 0.0)
    kf_var: Var = _add_parameter(block, vfactory, "KF", 0.01)
    tf_var: Var = _add_parameter(block, vfactory, "TF", 1.0)
    vref0_var: Var = _add_parameter(block, vfactory, "vref0", None)
    ll_y_diag_ref_var: Var = _add_parameter(block, vfactory, "LL_y_diag_ref", None)
    wf_y_diag_ref_var: Var = _add_parameter(block, vfactory, "WF_y_diag_ref", None)
    vf_diag_ref_var: Var = _add_parameter(block, vfactory, "Vf_diag_ref", None)
    diag_eps_expr: Expr = sym.Const(1.0e-8)

    block.state_vars = list((lg_state_var, ll_state_var, lr_state_var, wf_state_var))
    block.state_eqs = list((
        (vm_var - lg_state_var) / tr_var,
        (vl_var - ll_state_var) / tb_var,
        (ka_var * ll_y_var - lr_state_var) / ta_var,
        (lr_state_var - wf_state_var) / tf_var,
    ))
    block.algebraic_vars = list((
        vref_var,
        vi_var,
        vl_var,
        ll_y_var,
        wf_y_var,
        vfmax_var,
        vfmin_var,
        vf_var,
    ))
    lower_active: Expr = sym.heaviside(vfmin_var - wf_y_var)
    upper_active: Expr = sym.heaviside(wf_y_var - vfmax_var)
    interior_active: Expr = (
        sym.Const(1.0) - lower_active - upper_active
    )
    vf_expression: Expr = (
        interior_active * lr_state_var
        + lower_active * vfmin_var
        + upper_active * vfmax_var
    )

    block.algebraic_eqs = list((
        vref0_var - vref_var,
        vref_var - lg_state_var - wf_y_var + vpss_var - vi_var,
        sym.hard_sat(vi_var, vimin_var, vimax_var) - vl_var,
        tc_var / tb_var * (vl_var - ll_state_var)
        + ll_state_var
        - ll_y_var
        + diag_eps_expr / tb_var * (ll_y_var - ll_y_diag_ref_var),
        kf_var / tf_var * (lr_state_var - wf_state_var)
        - wf_y_var
        + diag_eps_expr / tf_var * (wf_y_var - wf_y_diag_ref_var),
        vrmax_var - kc_var * xadifd_var - vfmax_var,
        vrmin_var - kc_var * xadifd_var - vfmin_var,
        vf_expression - vf_var + diag_eps_expr * (vf_var - vf_diag_ref_var),
    ))
    block.init_eqs = dict()
    block.init_eqs[vref0_var] = vm_var + vf_var / ka_var
    block.init_eqs[vref_var] = vm_var + vf_var / ka_var
    block.init_eqs[vi_var] = vf_var / ka_var
    block.init_eqs[vl_var] = vf_var / ka_var
    block.init_eqs[lg_state_var] = vm_var
    block.init_eqs[ll_state_var] = vf_var / ka_var
    block.init_eqs[ll_y_var] = vf_var / ka_var
    block.init_eqs[ll_y_diag_ref_var] = vf_var / ka_var
    block.init_eqs[lr_state_var] = vf_var
    block.init_eqs[wf_state_var] = vf_var
    block.init_eqs[wf_y_var] = sym.Const(0.0)
    block.init_eqs[wf_y_diag_ref_var] = sym.Const(0.0)
    block.init_eqs[vfmax_var] = vrmax_var - kc_var * xadifd_var
    block.init_eqs[vfmin_var] = vrmin_var - kc_var * xadifd_var
    block.init_eqs[vf_var] = xadifd_var
    block.init_eqs[vf_diag_ref_var] = xadifd_var
    block.in_vars = list((xadifd_var, vm_var, vpss_var))
    block.out_vars = list((vf_var,))

    template.block.children.append(block)
    template.block.in_vars = list((xadifd_var, vm_var, vpss_var))
    template.block.out_vars = list((vf_var,))
    template.block.name = name
    template.comment = 'Generator EXST1 exciter RMS model'
    return template


def get_esst3a_rms_template(
    vfactory: VarFactory,
    name: str = "ESST3A RMS template",
) -> RmsModelTemplate:
    """Build the standard zero-TA ESST3A structural realization.

    With ``TA=0``, ``LAW1_y`` is algebraic and is not retained as a differential
    state. The retained states are ``LG_y``, ``LL_x`` and ``LAW2_y``.

    :param vfactory: Shared symbolic variable factory.
    :param name: Template name.
    :return: RMS template containing one ESST3A block.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice

    xadifd_var: Var = vfactory.add_var(
        "XadIfd_",
        shared_reference="irpu_reference",
    )
    vm_var: Var = vfactory.add_var(
        "Vm_",
        reference=VarPowerFlowReferenceType.Vm,
    )
    vd_var: Var = vfactory.add_var("Vd_", shared_reference="vd_reference")
    vq_var: Var = vfactory.add_var("Vq_", shared_reference="vq_reference")
    id_var: Var = vfactory.add_var("Id_", shared_reference="id_reference")
    iq_var: Var = vfactory.add_var("Iq_", shared_reference="iq_reference")
    vf_var: Var = vfactory.add_var(
        "Vf",
        shared_reference="vf_reference",
    )

    lg_state_var: Var = vfactory.add_var("LG_y")
    ll_state_var: Var = vfactory.add_var("LL_x")
    law2_state_var: Var = vfactory.add_var("LAW2_y")

    vref_var: Var = vfactory.add_var("vref")
    vi_var: Var = vfactory.add_var("vi")
    vil_var: Var = vfactory.add_var("vil")
    hg_var: Var = vfactory.add_var("HG_y")
    ll_y_var: Var = vfactory.add_var("LL_y")
    law1_var: Var = vfactory.add_var("LAW1_y")
    in_var: Var = vfactory.add_var("IN")
    fex_var: Var = vfactory.add_var("FEX_y")
    vb_var: Var = vfactory.add_var("VB_y")
    vg_var: Var = vfactory.add_var("VG_y")
    vrs_var: Var = vfactory.add_var("vrs")
    vpss_var: Var = vfactory.add_var("vpss")

    block: Block = Block(name=name)
    # VE is an initialized service parameter rather than a DAE algebraic
    # variable, preserving its operating-point value during linearization.
    ve_var: Var = _add_parameter(block, vfactory, "VE", None)
    tr_var: Var = _add_parameter(block, vfactory, "TR", 0.02)
    vimax_var: Var = _add_parameter(block, vfactory, "VIMAX", 0.2)
    vimin_var: Var = _add_parameter(block, vfactory, "VIMIN", -0.2)
    km_var: Var = _add_parameter(block, vfactory, "KM", 8.0)
    tc_var: Var = _add_parameter(block, vfactory, "TC", 1.0)
    tb_var: Var = _add_parameter(block, vfactory, "TB", 5.0)
    ka_var: Var = _add_parameter(block, vfactory, "KA", 20.0)
    ta_var: Var = _add_parameter(block, vfactory, "TA", 0.0)
    vrmax_var: Var = _add_parameter(block, vfactory, "VRMAX", 99.0)
    vrmin_var: Var = _add_parameter(block, vfactory, "VRMIN", -99.0)
    kg_var: Var = _add_parameter(block, vfactory, "KG", 1.0)
    kp_var: Var = _add_parameter(block, vfactory, "KP", 3.67)
    ki_var: Var = _add_parameter(block, vfactory, "KI", 0.435)
    vbmax_var: Var = _add_parameter(block, vfactory, "VBMAX", 5.48)
    kc_var: Var = _add_parameter(block, vfactory, "KC", 0.01)
    xl_var: Var = _add_parameter(block, vfactory, "XL", 0.0098)
    vgmax_var: Var = _add_parameter(block, vfactory, "VGMAX", 3.86)
    thetap_var: Var = _add_parameter(block, vfactory, "THETAP", 3.33)
    tm_var: Var = _add_parameter(block, vfactory, "TM", 0.4)
    vmmax_var: Var = _add_parameter(block, vfactory, "VMMAX", 99.0)
    vmmin_var: Var = _add_parameter(block, vfactory, "VMMIN", 0.0)
    vref0_var: Var = _add_parameter(block, vfactory, "vref0", None)
    ll_y_diag_ref_var: Var = _add_parameter(block, vfactory, "LL_y_diag_ref", None)
    in_diag_ref_var: Var = _add_parameter(block, vfactory, "IN_diag_ref", None)
    vf_diag_ref_var: Var = _add_parameter(block, vfactory, "Vf_diag_ref", None)
    diag_eps_expr: Expr = sym.Const(1.0e-8)

    theta_rad: Expr = thetap_var * sym.Const(math.pi / 180.0)
    cos_theta: Expr = sym.cos(theta_rad)
    sin_theta: Expr = sym.sin(theta_rad)
    kpc_real: Expr = kp_var * cos_theta
    kpc_imag: Expr = kp_var * sin_theta
    source_real: Expr = kpc_real * vd_var - kpc_imag * vq_var
    source_imag: Expr = kpc_real * vq_var + kpc_imag * vd_var
    current_gain_real: Expr = ki_var + xl_var * kpc_real
    current_gain_imag: Expr = xl_var * kpc_imag
    current_term_real: Expr = -(
        current_gain_real * iq_var
        + current_gain_imag * id_var
    )
    current_term_imag: Expr = (
        current_gain_real * id_var
        - current_gain_imag * iq_var
    )
    ve_expr: Expr = sym.sqrt(
        (source_real + current_term_real) ** 2
        + (source_imag + current_term_imag) ** 2
    )
    fex_expr: Expr = _esst3a_fex(in_var)
    vb_expr: Expr = sym.min(ve_var * fex_var, vbmax_var)
    vg_expr: Expr = sym.min(kg_var * vf_var, vgmax_var)

    block.state_vars = list((lg_state_var, ll_state_var, law2_state_var))
    block.state_eqs = list((
        (vm_var - lg_state_var) / tr_var,
        (hg_var - ll_state_var) / tb_var,
        (km_var * vrs_var - law2_state_var) / tm_var,
    ))
    block.algebraic_vars = list((
        vref_var,
        vi_var,
        vil_var,
        hg_var,
        ll_y_var,
        law1_var,
        in_var,
        fex_var,
        vb_var,
        vg_var,
        vrs_var,
        vf_var,
    ))
    block.algebraic_eqs = list((
        vref0_var - vref_var,
        -lg_state_var + vref_var + vpss_var - vi_var,
        sym.hard_sat(vi_var, vimin_var, vimax_var) - vil_var,
        vil_var - hg_var,
        tc_var / tb_var * (hg_var - ll_state_var)
        + ll_state_var
        - ll_y_var
        + diag_eps_expr / tb_var * (ll_y_var - ll_y_diag_ref_var),
        ka_var * ll_y_var - law1_var,
        kc_var * xadifd_var
        - ve_var * in_var
        + diag_eps_expr * (in_var - in_diag_ref_var),
        fex_expr - fex_var,
        vb_expr - vb_var,
        vg_expr - vg_var,
        law1_var - vg_var - vrs_var,
        vb_var * law2_state_var
        - vf_var
        + diag_eps_expr * (vf_var - vf_diag_ref_var),
    ))

    # Initialize the rectifier from compensated terminal voltage. Using XadIfd
    # as VB would change the LAW2 equilibrium and the reduced Jacobian.
    initial_ve: Expr = ve_expr
    initial_in: Expr = kc_var * xadifd_var / initial_ve
    initial_fex: Expr = _esst3a_fex(initial_in)
    initial_vb: Expr = sym.min(initial_ve * initial_fex, vbmax_var)
    initial_vg: Expr = sym.min(kg_var * xadifd_var, vgmax_var)
    initial_law2: Expr = xadifd_var / initial_vb
    initial_vrs: Expr = initial_law2 / km_var
    initial_law1: Expr = initial_vrs + initial_vg
    initial_ll: Expr = initial_law1 / ka_var
    initial_vref: Expr = vm_var + initial_ll

    block.init_eqs = dict()
    block.init_eqs[ve_var] = initial_ve
    block.init_eqs[in_var] = initial_in
    block.init_eqs[in_diag_ref_var] = initial_in
    block.init_eqs[fex_var] = initial_fex
    block.init_eqs[vb_var] = initial_vb
    block.init_eqs[vg_var] = initial_vg
    block.init_eqs[vrs_var] = initial_vrs
    block.init_eqs[law1_var] = initial_law1
    block.init_eqs[ll_y_var] = initial_ll
    block.init_eqs[ll_y_diag_ref_var] = initial_ll
    block.init_eqs[ll_state_var] = initial_ll
    block.init_eqs[law2_state_var] = initial_law2
    block.init_eqs[lg_state_var] = vm_var
    block.init_eqs[vi_var] = initial_ll
    block.init_eqs[vil_var] = initial_ll
    block.init_eqs[hg_var] = initial_ll
    block.init_eqs[vref0_var] = initial_vref
    block.init_eqs[vref_var] = initial_vref
    block.init_eqs[vf_var] = xadifd_var
    block.init_eqs[vf_diag_ref_var] = xadifd_var

    # TA and the limits remain registered as standard parameters. This structural
    # variant requires TA=0, so LAW1 is algebraic. A non-zero-TA ESST3A should be
    # built as a separate structural variant rather than dividing by TA or adding
    # an epsilon.
    _ = ta_var
    _ = vrmax_var
    _ = vrmin_var
    _ = vmmax_var
    _ = vmmin_var

    block.in_vars = list((
        xadifd_var, vm_var, vd_var, vq_var, id_var, iq_var, vpss_var,
    ))
    block.out_vars = list((vf_var,))

    template.block.children.append(block)
    template.block.in_vars = list(block.in_vars)
    template.block.out_vars = list((vf_var,))
    template.block.name = name
    template.comment = 'Generator ESST3A exciter RMS model'
    return template




def get_complete_genrou_rms_template(
    vfactory: VarFactory,
    exciter_type: GenrouExciterType = GenrouExciterType.EXST1,
    saturation_mode: GenrouSaturationMode = GenrouSaturationMode.QUADRATIC,
    name: str = "Complete GENROU RMS template",
) -> RmsModelTemplate:
    """Build one complete GENROU generator using VeraGrid block composition.

    The wrapper contains GENROU, TGOV1 and one selected excitation system. All
    internal ports are connected before the child blocks are attached.

    :param vfactory: Shared symbolic variable factory.
    :param exciter_type: Standard excitation-system model to compose.
    :param saturation_mode: GENROU magnetic-saturation realization.
    :param name: Wrapper name.
    :return: Complete generator RMS template.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice

    machine_block: Block = get_genrou_rms_template(
        vfactory=vfactory,
        name=f"{name}_GENROU",
        saturation_mode=saturation_mode,
    ).block.children[0]
    governor_block: Block = get_tgov1_rms_template(
        vfactory=vfactory,
        name=f"{name}_TGOV1",
    ).block.children[0]

    if exciter_type is GenrouExciterType.ESST3A:
        exciter_block: Block = get_esst3a_rms_template(
            vfactory=vfactory,
            name=f"{name}_ESST3A",
        ).block.children[0]
    else:
        exciter_block = get_exst1_rms_template(
            vfactory=vfactory,
            name=f"{name}_EXST1",
        ).block.children[0]

    # Machine <-> governor.
    vfactory.add_connection(machine_block.in_vars[2], governor_block.out_vars[0])
    vfactory.add_connection(governor_block.in_vars[0], machine_block.out_vars[2])
    vfactory.add_connection(governor_block.in_vars[1], machine_block.out_vars[4])

    # Machine <-> exciter common connections.
    vfactory.add_connection(machine_block.in_vars[3], exciter_block.out_vars[0])
    vfactory.add_connection(exciter_block.in_vars[0], machine_block.out_vars[3])
    vfactory.add_connection(exciter_block.in_vars[1], machine_block.in_vars[0])

    # ESST3A additionally consumes the machine dq terminal variables and currents.
    if exciter_type is GenrouExciterType.ESST3A:
        vfactory.add_connection(exciter_block.in_vars[2], machine_block.out_vars[5])
        vfactory.add_connection(exciter_block.in_vars[3], machine_block.out_vars[6])
        vfactory.add_connection(exciter_block.in_vars[4], machine_block.out_vars[7])
        vfactory.add_connection(exciter_block.in_vars[5], machine_block.out_vars[8])
        pss_input_var: Var = exciter_block.in_vars[6]
    else:
        pss_input_var = exciter_block.in_vars[2]

    # Complete assemblies without a stabilizer retain the standard zero PSS
    # input. Controller-containing assemblies connect this port explicitly.
    exciter_block.init_eqs[pss_input_var] = sym.Const(0.0)
    exciter_block.algebraic_vars.append(pss_input_var)
    exciter_block.algebraic_eqs.append(-pss_input_var)

    template.block.children.append(machine_block)
    template.block.children.append(governor_block)
    template.block.children.append(exciter_block)
    template.block.external_mapping = dict()
    template.block.external_mapping[VarPowerFlowReferenceType.Vm] = machine_block.in_vars[0]
    template.block.external_mapping[VarPowerFlowReferenceType.Va] = machine_block.in_vars[1]
    template.block.external_mapping[VarPowerFlowReferenceType.P] = machine_block.out_vars[0]
    template.block.external_mapping[VarPowerFlowReferenceType.Q] = machine_block.out_vars[1]
    template.block.in_vars = list((machine_block.in_vars[0], machine_block.in_vars[1]))
    template.block.out_vars = list((machine_block.out_vars[0], machine_block.out_vars[1]))
    template.block.name = name
    template.comment = 'Complete generator GENROU RMS model'
    return template



