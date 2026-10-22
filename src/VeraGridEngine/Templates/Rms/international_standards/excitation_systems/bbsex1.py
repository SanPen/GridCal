# SPDX-License-Identifier: MPL-2.0
"""Transformer-fed static excitation with bounded feedback realization and voltage-dependent capability."""
from __future__ import annotations

import math
from enum import Enum
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class AuxiliaryVoltageLocation(Enum):
    """Physical insertion point and corresponding units of supplementary excitation."""
    VOLTAGE_ERROR = 1
    FIELD_OUTPUT = 2


class FeedbackStaticExciterParameters:
    """Physical coefficients for a static regulator with explicit bounded-output feedback."""
    __slots__ = ('tr','gain','t1','t2','t3','t4','regulator_max','regulator_min',
                 'field_max','field_min','auxiliary_location')

    def __init__(self, tr: float = .02, gain: float = 20., t1: float = .2,
                 t2: float = .1, t3: float = .05, t4: float = .1,
                 regulator_max: float = 5., regulator_min: float = -5.,
                 field_max: float = 5., field_min: float = -5.,
                 auxiliary_location: AuxiliaryVoltageLocation = AuxiliaryVoltageLocation.VOLTAGE_ERROR) -> None:
        """Store physical regulator settings; graph construction validates their domain.

        :param tr: Nonnegative sensing lag in seconds.
        :param gain: Positive steady regulator gain.
        :param t1: Positive effective regulator lag in seconds.
        :param t2: Positive feedback-memory lag and effective regulator lead in seconds.
        :param t3: Nonnegative input phase-compensator lead in seconds.
        :param t4: Nonnegative input phase-compensator lag in seconds.
        :param regulator_max: Fixed upper internal regulator capability.
        :param regulator_min: Fixed lower internal regulator capability.
        :param field_max: Upper field capability per unit terminal voltage.
        :param field_min: Lower field capability per unit terminal voltage.
        :param auxiliary_location: Error summation or final field-voltage summation.
        """
        self.tr: float = tr
        self.gain: float = gain
        self.t1: float = t1
        self.t2: float = t2
        self.t3: float = t3
        self.t4: float = t4
        self.regulator_max: float = regulator_max
        self.regulator_min: float = regulator_min
        self.field_max: float = field_max
        self.field_min: float = field_min
        self.auxiliary_location: AuxiliaryVoltageLocation = auxiliary_location


def build_bbsex1_template(vf: VarFactory, name: str | None = None,
                          parameters: FeedbackStaticExciterParameters | None = None) -> RmsModelTemplate:
    """Build a transformer-fed static voltage regulator with explicit bounded feedback.

    Sensed voltage and reference form the voltage error, followed by an input
    phase compensator. An algebraic amplifier of gain ``K*T2/T1`` receives that
    compensated error and positive feedback from its bounded output through
    ``(T1/T2-1)/(K*(1+s*T2))``. Inside its limits, the resulting regulator transfer
    is ``K*(1+s*T2)/(1+s*T1)``. Feedback senses the internally limited output,
    not the final delivered field voltage. This topology controls recovery from
    saturation and must not be replaced by clipping an unconstrained lead-lag.

    Supplementary and minimum-excitation signals sum either into voltage error
    before phase compensation or directly into field output after the internal
    regulator limit. Their units follow that physical insertion point. Delivered
    excitation is clipped between terminal-voltage-scaled field capabilities;
    the internal regulator limits remain fixed. The model contains no final
    field integrator or output filter. A terminal-voltage collapse therefore
    collapses delivered field voltage immediately without resetting memories.

    Inputs are compensated voltage, reference voltage, supplementary voltage,
    additive minimum-excitation signal and actual terminal-voltage magnitude.
    Outputs are field voltage and internal regulator voltage. Initialization
    balances the initial field voltage and auxiliary bias against regulator
    forcing and initializes feedback memory from that bounded regulator output.
    Three states exist with positive sensing and input phase-compensator lags;
    zero permitted lags become algebraic stages. All times are seconds; voltage
    signals use their connected per-unit terminal or field bases.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical regulator coefficients and signal insertion point.
    :return: Native static excitation controller.
    :raises ValueError: Nonfinite settings, invalid limits or undefined dynamics.
    """
    p: FeedbackStaticExciterParameters = FeedbackStaticExciterParameters() if parameters is None else parameters
    coefficients: tuple[float,...] = (p.tr,p.gain,p.t1,p.t2,p.t3,p.t4,p.regulator_max,
        p.regulator_min,p.field_max,p.field_min)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('Static feedback excitation coefficients must be finite')
    elif min(p.gain,p.t1,p.t2) <= 0 or min(p.tr,p.t3,p.t4) < 0:
        raise ValueError('Static feedback excitation gains and times have invalid domains')
    elif p.t4 == 0 and p.t3 != 0:
        raise ValueError('Zero phase-compensator lag requires zero lead')
    elif p.regulator_max <= p.regulator_min or p.field_max <= p.field_min:
        raise ValueError('Static feedback excitation capabilities must be ordered')
    elif not isinstance(p.auxiliary_location,AuxiliaryVoltageLocation):
        raise ValueError('Auxiliary voltage location requires an explicit physical selection')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'BBSEX1' if name is None else name)
    tr: Var = c.parameter('TF',p.tr)
    gain: Var = c.parameter('K',p.gain)
    t1: Var = c.parameter('T1',p.t1)
    t2: Var = c.parameter('T2',p.t2)
    t3: Var = c.parameter('T3',p.t3)
    t4: Var = c.parameter('T4',p.t4)
    upper: Var = c.parameter('VRMAX',p.regulator_max)
    lower: Var = c.parameter('VRMIN',p.regulator_min)
    field_upper: Var = c.parameter('EFDMAX',p.field_max)
    field_lower: Var = c.parameter('EFDMIN',p.field_min)
    field0: Var = c.parameter('Efd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    auxiliary0: Var = c.parameter('Aux0Pu',0.)
    at_error: bool = p.auxiliary_location == AuxiliaryVoltageLocation.VOLTAGE_ERROR
    regulator0: Expr = field0 if at_error else field0-auxiliary0
    reference0: Expr = voltage0+regulator0/gain-(auxiliary0 if at_error else Const(0.))
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',reference0)
    supplementary: Var = c.input('VsPu',Const(0.))
    minimum: Var = c.input('UelPu',Const(0.))
    terminal: Var = c.input('VtPu',voltage0)
    auxiliary: Expr = supplementary+minimum
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    error: Expr = reference-measured+(auxiliary if at_error else Const(0.))
    lead: Var = c.lead_lag('LeadPu',error,t3,t4,p.t3,p.t4,regulator0/gain)
    regulator: Var = vf.add_var('RegulatorPu_'+c.name)
    memory: Var = c.lag('FeedbackMemoryPu',regulator,t2,p.t2,regulator0)
    feedback: Expr = (t1/t2-Const(1.))*memory/gain
    c.lag('RegulatorPu',gain*t2/t1*(lead+feedback),Const(0.),0.,regulator0,lower,upper,output=regulator)
    field: Var = c.algebraic('EfdPu',sym.hard_sat(regulator+(Const(0.) if at_error else auxiliary),
        terminal*field_lower,terminal*field_upper),field0)
    return c.finish((field,regulator),'Static excitation with bounded feedback and terminal-voltage-dependent field capability')
