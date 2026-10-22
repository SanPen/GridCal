# SPDX-License-Identifier: MPL-2.0
"""Bidirectional controlled-bridge excitation with external clipping and shaped feedback."""
from __future__ import annotations

from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class BridgeExcitationSupply(Enum):
    """Terminal-powered or independently powered controlled bridge."""
    TERMINAL = 0
    INDEPENDENT = 1


def build_exni_template(vf: VarFactory, name: str | None = None,
                       tr: float = .02, ka: float = 20., ta: float = .05,
                       vrmax: float = 5., vrmin: float = -5., kf: float = .05,
                       tf1: float = 1., tf2: float = .1,
                       supply: BridgeExcitationSupply = BridgeExcitationSupply.TERMINAL) -> RmsModelTemplate:
    """Build externally limited static voltage regulation with bidirectional current.

    Filtered voltage opposes reference and additive supplementary/minimum
    excitation signals. The amplifier KA/(1+s*TA) has unrestricted memory;
    an external VRMIN/VRMAX clip limits delivered regulator voltage. Its memory
    may wind up while the bridge is saturated. Filtered derivative feedback
    KF*s/((1+s*TF1)*(1+s*TF2)) senses that bounded regulator voltage before
    terminal-supply multiplication. It does not sense raw amplifier memory or
    final field voltage after terminal sag.

    Terminal-fed operation multiplies the limited regulator output by actual
    terminal voltage. Independent supply uses unity. The bridge admits both
    signs of field current and voltage; there is no discharge-resistor switch
    or unreviewed reverse-current limiter in this realization.

    Inputs are sensed voltage, reference, supplementary voltage, additive
    minimum-excitation voltage and actual terminal voltage. Outputs are field
    voltage, limited regulator voltage and raw amplifier voltage. Positive
    sensing time gives four states; zero sensing time removes that memory
    exactly. Amplifier and both feedback times are positive. Signals are per
    unit on compatible field/terminal bases and time constants are seconds.

    Initialization divides required field voltage by actual initial terminal
    supply when appropriate, initializes the unrestricted amplifier and first
    feedback memory to that regulator forcing, and derives a reference that
    accounts for steady auxiliary bias. Compensated sensing and actual supply
    voltage are separate frozen quantities. A nonzero initial field requires
    positive terminal supply in terminal-powered operation and feasible limits.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param tr: Nonnegative sensing time, seconds.
    :param ka: Positive amplifier gain.
    :param ta: Positive amplifier lag, seconds.
    :param vrmax: Upper external regulator limit.
    :param vrmin: Lower external regulator limit.
    :param kf: Nonnegative rate-feedback gain.
    :param tf1: Positive washout time, seconds.
    :param tf2: Positive second feedback lag, seconds.
    :param supply: Physical bridge supply selection.
    :return: Native bidirectional controlled-bridge excitation controller.
    :raises ValueError: Invalid physical gains, times, limits or supply selection.
    """
    if min(tr,kf) < 0 or min(ka,ta,tf1,tf2) <= 0 or vrmax <= vrmin:
        raise ValueError('Bidirectional bridge excitation coefficients have invalid domains')
    elif not isinstance(supply,BridgeExcitationSupply):
        raise ValueError('Bidirectional bridge excitation requires explicit supply selection')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'EXNI' if name is None else name)
    sensing_time: Var = c.parameter('TR',tr)
    amplifier_gain: Var = c.parameter('KA',ka)
    amplifier_time: Var = c.parameter('TA',ta)
    upper: Var = c.parameter('VRMAX',vrmax)
    lower: Var = c.parameter('VRMIN',vrmin)
    rate_gain: Var = c.parameter('KF',kf)
    rate_time: Var = c.parameter('TF1',tf1)
    feedback_time: Var = c.parameter('TF2',tf2)
    field0: Var = c.parameter('Efd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    terminal0: Var = c.parameter('Vt0Pu',1.)
    auxiliary0: Var = c.parameter('Aux0Pu',0.)
    regulator0: Expr = field0/terminal0 if supply == BridgeExcitationSupply.TERMINAL else field0
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0+regulator0/amplifier_gain-auxiliary0)
    supplement: Var = c.input('VsPu',Const(0.))
    minimum: Var = c.input('UelPu',auxiliary0)
    terminal: Var = c.input('VtPu',terminal0)
    limited: Var = vf.add_var('LimitedRegulatorPu_'+c.name)
    measured: Var = c.lag('MeasuredPu',sensed,sensing_time,tr,voltage0)
    rate: Var = c.washout('RatePu',limited,rate_time,tf1,rate_gain/rate_time,regulator0)
    feedback: Var = c.lag('FeedbackPu',rate,feedback_time,tf2,Const(0.))
    error: Expr = reference+supplement+minimum-measured-feedback
    raw: Var = c.lag('RawRegulatorPu',amplifier_gain*error,amplifier_time,ta,regulator0)
    c.block.algebraic_vars.append(limited)
    c.block.algebraic_eqs.append(limited-sym.hard_sat(raw,lower,upper))
    c.block.init_eqs[limited] = regulator0
    field: Var = c.algebraic('EfdPu',limited*terminal if supply == BridgeExcitationSupply.TERMINAL else limited,field0)
    return c.finish((field,limited,raw),'Bidirectional controlled-bridge excitation with bounded-regulator feedback')
