# SPDX-License-Identifier: MPL-2.0
"""Bounded parallel PI excitation with separate actuator and exciter dynamics."""
from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class LimitedPiExciterParameters:
    """Physical coefficients for independently limited integral and total PI outputs."""
    __slots__ = ('kp','ka','ke','tr','ti','ta','te','regulator_max','regulator_min','field_max','field_min')

    def __init__(self, kp: float = 5., ka: float = 2., ke: float = 1.5,
                 tr: float = .02, ti: float = 1., ta: float = .1, te: float = .4,
                 regulator_max: float = 5., regulator_min: float = -5.,
                 field_max: float = 5., field_min: float = -5.) -> None:
        """Store physical coefficients; construction validates their domains.

        :param kp: Nonnegative proportional gain.
        :param ka: Positive actuator gain.
        :param ke: Positive exciter gain.
        :param tr: Nonnegative voltage-sensing lag in seconds.
        :param ti: Positive integral time in seconds.
        :param ta: Nonnegative actuator lag in seconds.
        :param te: Nonnegative exciter lag in seconds.
        :param regulator_max: Upper integral-memory and total PI capability.
        :param regulator_min: Lower integral-memory and total PI capability.
        :param field_max: Upper exciter output capability in per unit.
        :param field_min: Lower exciter output capability in per unit.
        """
        self.kp: float = kp
        self.ka: float = ka
        self.ke: float = ke
        self.tr: float = tr
        self.ti: float = ti
        self.ta: float = ta
        self.te: float = te
        self.regulator_max: float = regulator_max
        self.regulator_min: float = regulator_min
        self.field_max: float = field_max
        self.field_min: float = field_min


def build_budczt_template(vf: VarFactory, name: str | None = None,
                          parameters: LimitedPiExciterParameters | None = None) -> RmsModelTemplate:
    """Build bounded PI voltage regulation followed by actuator and exciter lags.

    Voltage reference, supplementary voltage and minimum-excitation signal form
    an error against filtered compensated voltage. Parallel proportional and
    integral paths realize ``KP + 1/(s*TI)``. The integral memory has directional
    non-windup stops at URMIN/URMAX; their sum is clipped independently at the
    same capabilities. Consequently a proportional excursion can saturate total
    PI output while integral memory continues moving inside its own bounds.
    There is no inferred tracking or back-calculation path.

    A first-order actuator with gain KA drives a distinct first-order exciter
    with gain KE. Field capability limits apply to the exciter state, not to
    the intermediate actuator. Independent gains and times remain separate so
    their identities and bounded transient responses are preserved. There are
    four states with positive sensing, actuator and exciter times. Zero permitted
    lags become exact algebraic stages; the integral time remains positive.

    Inputs are compensated voltage, reference voltage, supplementary voltage,
    additive minimum-excitation voltage and a retained terminal-voltage port.
    Terminal voltage does not scale the fixed field capability. Outputs are
    field voltage and bounded total PI demand. At equilibrium the voltage error
    is zero, integral memory equals ``Efd0/(KA*KE)``, and actuator voltage equals
    ``Efd0/KE``. All voltage signals use their connected per-unit bases and time
    constants use seconds. Physical construction requires finite positive gains,
    ordered limits and a proper integral channel.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical PI, actuator and exciter coefficients.
    :return: Native excitation controller with explicit independent state stops.
    :raises ValueError: Invalid coefficients, time constants or capability limits.
    """
    p: LimitedPiExciterParameters = LimitedPiExciterParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.kp,p.ka,p.ke,p.tr,p.ti,p.ta,p.te,p.regulator_max,
        p.regulator_min,p.field_max,p.field_min)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('Limited PI excitation coefficients must be finite')
    elif min(p.ka,p.ke,p.ti) <= 0 or min(p.kp,p.tr,p.ta,p.te) < 0:
        raise ValueError('Limited PI excitation gains and times have invalid domains')
    elif p.regulator_max <= p.regulator_min or p.field_max <= p.field_min:
        raise ValueError('Limited PI excitation capabilities must be ordered')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'BUDCZT' if name is None else name)
    kp: Var = c.parameter('KP',p.kp)
    ka: Var = c.parameter('KA',p.ka)
    ke: Var = c.parameter('KE',p.ke)
    tr: Var = c.parameter('TR',p.tr)
    ti: Var = c.parameter('TI',p.ti)
    ta: Var = c.parameter('TA',p.ta)
    te: Var = c.parameter('TE',p.te)
    upper: Var = c.parameter('URMAX',p.regulator_max)
    lower: Var = c.parameter('URMIN',p.regulator_min)
    field_upper: Var = c.parameter('EFDMAX',p.field_max)
    field_lower: Var = c.parameter('EFDMIN',p.field_min)
    field0: Var = c.parameter('Efd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0)
    supplementary: Var = c.input('VsPu',Const(0.))
    minimum: Var = c.input('UelPu',Const(0.))
    c.input('VtPu',voltage0)
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    error: Expr = reference+supplementary+minimum-measured
    integral0: Expr = field0/(ka*ke)
    integral: Var = c.differential(vf.add_var('IntegralPu_'+c.name),error/ti,integral0,lower,upper)
    demand: Var = c.algebraic('DemandPu',sym.hard_sat(kp*error+integral,lower,upper),integral0)
    actuator: Var = c.lag('ActuatorPu',ka*demand,ta,p.ta,field0/ke)
    field: Var = c.lag('EfdPu',ke*actuator,te,p.te,field0,field_lower,field_upper)
    return c.finish((field,demand),'Parallel PI excitation with independently bounded integral memory and field output')
