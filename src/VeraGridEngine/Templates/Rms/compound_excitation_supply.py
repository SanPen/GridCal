# SPDX-License-Identifier: MPL-2.0
"""Loaded compound potential circuits supplying rotating or static excitation."""
from __future__ import annotations

import math
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4c import CompoundExcitationSource
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class CompoundSupplyParameters:
    """Potential source, bridge commutation and available field-supply ceiling."""
    __slots__ = ('kp','ki','xl','theta','kc','vbmax','source')

    def __init__(self, kp: float = 1., ki: float = 0., xl: float = 0., theta: float = 0.,
                 kc: float = 0., vbmax: float = 5.,
                 source: CompoundExcitationSource = CompoundExcitationSource.INDEPENDENT) -> None:
        """Store independent physical potential and commutation coefficients.

        :param kp: Nonnegative potential voltage gain.
        :param ki: Nonnegative potential current gain.
        :param xl: Nonnegative potential-circuit reactance, per unit.
        :param theta: Potential voltage phase angle, degrees.
        :param kc: Nonnegative commutation loading coefficient.
        :param vbmax: Positive available supply ceiling, per unit.
        :param source: Terminal compound or independent potential KP.
        """
        self.kp: float = kp
        self.ki: float = ki
        self.xl: float = xl
        self.theta: float = theta
        self.kc: float = kc
        self.vbmax: float = vbmax
        self.source: CompoundExcitationSource = source


def build_compound_supply(c: ControlRealization, vr: Expr, vi: Expr, ir: Expr, ii: Expr,
                          load: Expr, parameters: CompoundSupplyParameters,
                          voltage_gain: Var | None = None) -> Var:
    """Build a loaded potential circuit without conflating its load with generator field current.

    Potential is the magnitude of KP*exp(j*theta)*(V+j*XL*I)+j*KI*I, or KP
    for independent operation. Rectifier commutation depends on KC1 times the
    supplied circuit's current-equivalent load divided by that potential. The
    resulting available voltage is capped at VBMAX. Its current input must use
    the same field base as KC1; rectangular V/I use compatible terminal bases.
    Zero potential supplies zero voltage and retains downstream winding memory.

    :param c: Owning symbolic realization.
    :param vr: Real terminal voltage.
    :param vi: Imaginary terminal voltage.
    :param ir: Real outgoing terminal current.
    :param ii: Imaginary outgoing terminal current.
    :param load: Current-equivalent load of the supplied circuit.
    :param parameters: Potential and commutation settings.
    :param voltage_gain: Optional already declared potential gain to avoid duplicate symbols.
    :return: Available loaded supply variable with an explicit initializer.
    :raises ValueError: Invalid domains or identically absent potential.
    """
    p: CompoundSupplyParameters = parameters
    if not all(math.isfinite(value) for value in (p.kp,p.ki,p.xl,p.theta,p.kc,p.vbmax)):
        raise ValueError('Compound supply coefficients must be finite')
    elif min(p.kp,p.ki,p.xl,p.kc) < 0 or p.vbmax <= 0 or p.kp+p.ki == 0:
        raise ValueError('Compound supply requires nonnegative gains/loading and positive potential/capability')
    elif not isinstance(p.source,CompoundExcitationSource) or p.source == CompoundExcitationSource.INDEPENDENT and p.kp <= 0:
        raise ValueError('Compound supply source selection or independent potential is invalid')
    else:
        pass
    kp: Var = c.parameter('KP',p.kp) if voltage_gain is None else voltage_gain
    ki: Var = c.parameter('KI',p.ki)
    xl: Var = c.parameter('XL',p.xl)
    theta: Var = c.parameter('THETAP',p.theta)
    kc: Var = c.parameter('KC1',p.kc)
    maximum: Var = c.parameter('VBMAX',p.vbmax)
    cosine: Expr = sym.cos(theta*Const(math.pi/180.))
    sine: Expr = sym.sin(theta*Const(math.pi/180.))
    real: Expr = kp*(cosine*(vr-xl*ii)-sine*(vi+xl*ir))-ki*ii
    imag: Expr = kp*(sine*(vr-xl*ii)+cosine*(vi+xl*ir))+ki*ir
    potential_expression: Expr = sym.sqrt(real**2+imag**2) if p.source == CompoundExcitationSource.TERMINAL else kp
    potential: Var = c.algebraic('PotentialPu',potential_expression,potential_expression)
    # The caller chooses the physical load: rotating-field current and delivered field current differ.
    supplied: Expr = sym.min(maximum,potential*_esst3a_fex(sym.safe_divide(kc*load,potential,1.)))
    return c.algebraic('SupplyPu',supplied,supplied)
