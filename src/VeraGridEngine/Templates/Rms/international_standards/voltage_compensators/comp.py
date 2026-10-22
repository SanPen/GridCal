# SPDX-License-Identifier: MPL-2.0
"""Reactive line-drop compensation for a voltage regulator's measurement."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_comp_template(vf: VarFactory, name: str | None = None,
                        reactance: float = 0.0) -> RmsModelTemplate:
    """Measure voltage behind a signed series reactance without adding states.

    The compensated phasor is ``Vc = Vt - j*Xe*It`` for current directed out of
    the generator. In rectangular coordinates its components are
    ``Vc.real = Vt.real + Xe*It.imag`` and
    ``Vc.imag = Vt.imag - Xe*It.real``. The output is the magnitude of that
    phasor, not a linearized voltage correction. The minus sign is part of this
    component's convention; it must not be replaced by a positive line-drop
    convention merely because the reactance parameter has the same units.

    Inputs are ``VrPu``, ``ViPu``, ``IrPu`` and ``IiPu`` in that order. Current
    and Xe must use the same current/impedance base, and voltage uses the exciter
    measurement base. Signed Xe permits sensing on either side of the terminal.
    Three algebraic equations expose both compensated components and ``VcPu``;
    initialization evaluates those same equations at the supplied phasors.

    :param vf: Symbol factory owning the measurement graph.
    :param name: Optional label, defaulting to COMP.
    :param reactance: Signed per-unit compensation reactance on the input-current base.
    :return: Stateless native rectangular-phasor compensator.
    :raises ValueError: Nonfinite reactance.
    """
    builder: ControlRealization = ControlRealization(vf, 'COMP' if name is None else name)
    xe: Var = builder.parameter('Xe',reactance)
    vr: Var = builder.input('VrPu',Const(1.0))
    vi: Var = builder.input('ViPu',Const(0.0))
    ir: Var = builder.input('IrPu',Const(0.0))
    ii: Var = builder.input('IiPu',Const(0.0))
    real: Var = builder.algebraic('VcRealPu',vr+xe*ii,vr+xe*ii)
    imag: Var = builder.algebraic('VcImagPu',vi-xe*ir,vi-xe*ir)
    magnitude: Var = builder.algebraic('VcPu',sym.sqrt(real*real+imag*imag),sym.sqrt(real*real+imag*imag))
    return builder.finish((magnitude,), 'Voltage measurement behind a signed reactive impedance')
