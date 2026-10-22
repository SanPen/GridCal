# SPDX-License-Identifier: MPL-2.0
"""Power-sensitive supplementary excitation control with double reset filtering."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def build_stabni_template(vf: VarFactory, name: str | None = None,
                          gain: float = 1.0, lead_time: float = .2,
                          transducer_time: float = .1, reset_time: float = 1.0,
                          output_limit: float = .1) -> RmsModelTemplate:
    """Build a power stabilizer with two washouts and fourth-order reset shaping.

    Electrical power first passes through ``K/(1+s*T2)``. The remaining shaping
    transfer is ``(1+s*T1)*(s*T0)^2/(1+s*T0)^4``. Two washout stages followed
    by a lead-lag and a final low-pass stage realize that expression without
    taking numerical derivatives of measured power. The shaped signal is
    symmetrically limited and inverted to produce supplementary voltage.

    The only open input, ``PePu``, is electrical power on the machine MVA base.
    Output ``VsPu`` feeds the exciter voltage summation. Positive transducer time
    gives five states; zero transducer time gives an exact algebraic gain and
    four states. Initialization stores the operating power in the transducer
    and first washout memory while the remaining states start at zero. Both
    constant power and constant-rate power variation are rejected at low
    frequency by the double zero at the origin.

    :param vf: Symbol factory owning the controller graph.
    :param name: Optional label, defaulting to STABNI.
    :param gain: Nonnegative power-transducer gain K.
    :param lead_time: Positive lead numerator T1 in seconds.
    :param transducer_time: Nonnegative initial transducer lag T2 in seconds.
    :param reset_time: Positive common reset denominator T0 in seconds.
    :param output_limit: Positive symmetric supplementary-voltage limit.
    :return: Native power stabilizer with the complete fourth-order shaping filter.
    :raises ValueError: Nonfinite settings or invalid gain, time constants or limit.
    """
    if gain < 0 or transducer_time < 0 or min(lead_time,reset_time,output_limit) <= 0:
        raise ValueError('Double-reset stabilizer settings are invalid')
    else:
        pass
    builder: ControlRealization = ControlRealization(vf,'STABNI' if name is None else name)
    k: Var = builder.parameter('K',gain)
    t1: Var = builder.parameter('T1',lead_time)
    t2: Var = builder.parameter('T2',transducer_time)
    t0: Var = builder.parameter('T0',reset_time)
    limit: Var = builder.parameter('LIMIT',output_limit)
    power: Var = builder.input('PePu',Const(.5))
    measured: Var = builder.lag('MeasuredPowerPu',k*power,t2,transducer_time,k*power)
    first: Var = builder.washout('Reset1Pu',measured,t0,reset_time,Const(1.0),k*power)
    second: Var = builder.washout('Reset2Pu',first,t0,reset_time,Const(1.0),Const(0.0))
    phase: Var = builder.lead_lag('PhasePu',second,t1,t0,lead_time,reset_time,Const(0.0))
    filtered: Var = builder.lag('OutputFilterPu',phase,t0,reset_time,Const(0.0))
    output: Var = builder.algebraic('VsPu',-sym.hard_sat(filtered,-limit,limit),Const(0.0))
    return builder.finish((output,),'Electrical-power stabilizer with double reset and fourth-order shaping')
