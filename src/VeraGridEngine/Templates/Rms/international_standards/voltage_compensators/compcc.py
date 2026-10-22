# SPDX-License-Identifier: MPL-2.0
"""Two-machine cross-compound voltage sensing with shared current compensation."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_compcc_template(vf: VarFactory, name: str | None = None,
                          shared_resistance: float = 0.0, shared_reactance: float = 0.0,
                          individual_resistance: float = 0.0,
                          individual_reactance: float = 0.0) -> RmsModelTemplate:
    """Build two compensated voltage measurements for a cross-compound unit.

    Both machines share terminal voltage Vt. The common voltage correction is
    ``(I1+I2)*(R1+j*X1)/2`` and is subtracted from Vt. An individual correction
    ``Ik*(R2+j*X2)`` is then added for each machine. The two outputs are the
    magnitudes of these resulting phasors; the individual terms must not be
    formed from half of the summed current because that would remove the
    cross-current sharing behavior.

    Open inputs are terminal ``VrPu``, ``ViPu``, followed by rectangular outgoing
    currents ``I1rPu``, ``I1iPu``, ``I2rPu``, ``I2iPu``. Both currents and the
    four impedances must use a common system base before connection. Outputs
    ``Vc1Pu`` and ``Vc2Pu`` feed the respective exciters. Six algebraic equations
    calculate phasor components and magnitudes; no controller state or artificial
    delay is introduced. Swapping machine currents swaps only the two outputs.

    :param vf: Symbol factory owning both measurement paths.
    :param name: Optional label, defaulting to COMPCC.
    :param shared_resistance: Common correction resistance R1 in per unit.
    :param shared_reactance: Common correction reactance X1 in per unit.
    :param individual_resistance: Individual correction resistance R2 in per unit.
    :param individual_reactance: Individual correction reactance X2 in per unit.
    :return: Stateless native two-machine compensator with two voltage outputs.
    :raises ValueError: Nonfinite impedance parameter.
    """
    builder: ControlRealization = ControlRealization(vf,'COMPCC' if name is None else name)
    r1: Var = builder.parameter('R1',shared_resistance)
    x1: Var = builder.parameter('X1',shared_reactance)
    r2: Var = builder.parameter('R2',individual_resistance)
    x2: Var = builder.parameter('X2',individual_reactance)
    vr: Var = builder.input('VrPu',Const(1.0))
    vi: Var = builder.input('ViPu',Const(0.0))
    i1r: Var = builder.input('I1rPu',Const(0.0))
    i1i: Var = builder.input('I1iPu',Const(0.0))
    i2r: Var = builder.input('I2rPu',Const(0.0))
    i2i: Var = builder.input('I2iPu',Const(0.0))
    shared_real: Expr = (r1*(i1r+i2r)-x1*(i1i+i2i))*Const(.5)
    shared_imag: Expr = (r1*(i1i+i2i)+x1*(i1r+i2r))*Const(.5)
    first_real: Expr = vr-shared_real+r2*i1r-x2*i1i
    first_imag: Expr = vi-shared_imag+r2*i1i+x2*i1r
    second_real: Expr = vr-shared_real+r2*i2r-x2*i2i
    second_imag: Expr = vi-shared_imag+r2*i2i+x2*i2r
    first_r: Var = builder.algebraic('Vc1RealPu',first_real,first_real)
    first_i: Var = builder.algebraic('Vc1ImagPu',first_imag,first_imag)
    second_r: Var = builder.algebraic('Vc2RealPu',second_real,second_real)
    second_i: Var = builder.algebraic('Vc2ImagPu',second_imag,second_imag)
    first: Var = builder.algebraic('Vc1Pu',sym.sqrt(first_r*first_r+first_i*first_i),sym.sqrt(first_r*first_r+first_i*first_i))
    second: Var = builder.algebraic('Vc2Pu',sym.sqrt(second_r*second_r+second_i*second_i),sym.sqrt(second_r*second_r+second_i*second_i))
    return builder.finish((first,second),'Two-machine cross-compound shared-current voltage compensation')
