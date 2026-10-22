# SPDX-License-Identifier: MPL-2.0
"""Droop regulation with asymmetric speed deadband and a reheated steam turbine."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import Tgov1RmsParameters
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var


def build_tgov1d_template(vf: VarFactory, name: str | None = None,
                          parameters: Tgov1RmsParameters | None = None,
                          deadband_low: float = -.0005, deadband_high: float = .0005) -> RmsModelTemplate:
    """Build a non-windup steam valve and reheater with asymmetric speed pickup.

    Excess shaft-speed deviation outside separate underspeed/overspeed
    thresholds enters inverse permanent droop. Subtracting it from the
    turbine-power reference requests valve opening. The valve lag owns
    directional travel stops: outward motion is suppressed at a bound and
    inward recovery is immediate. Its output enters ``(1+s*T2)/(1+s*T3)``
    for the steam/reheater response. Mechanical damping uses raw shaft-speed
    deviation, so it remains effective inside the governor control deadband.

    Inputs are absolute per-unit speed and valve-power reference. Outputs are
    mechanical power and valve opening. Two states store valve and reheater
    memories; positive T1/T3 are required and zero T2 removes the lead term.
    Initial speed is one, both memories equal the bounded operating reference,
    and mechanical power equals that reference. Power, droop and damping use
    one declared turbine base; the host performs network-base conversions.
    Reference changes use power units rather than a hidden speed-gain scaling.

    :param vf: Shared symbolic factory.
    :param name: Optional instance label.
    :param parameters: Droop, valve, reheater and damping settings on one base.
    :param deadband_low: Nonpositive underspeed pickup threshold.
    :param deadband_high: Nonnegative overspeed pickup threshold.
    :return: Native two-state, two-input governor.
    :raises ValueError: Invalid physical settings or nonnominal speed-reference convention.
    """
    p: Tgov1RmsParameters = (Tgov1RmsParameters(1.,.05,1.2,0.,.1,.2,10.,0.)
        if parameters is None else parameters)
    if min(p.r,p.t1,p.t3) <= 0 or min(p.t2,p.dt) < 0 or p.vmax <= p.vmin or p.wref0 != 1.:
        raise ValueError('Steam governor requires positive dynamics/droop and valid limits/reference')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'TGOV1D' if name is None else name)
    r: Var = c.parameter('R',p.r)
    t1: Var = c.parameter('T1',p.t1)
    t2: Var = c.parameter('T2',p.t2)
    t3: Var = c.parameter('T3',p.t3)
    vmax: Var = c.parameter('VMAX',p.vmax)
    vmin: Var = c.parameter('VMIN',p.vmin)
    damping: Var = c.parameter('Dt',p.dt)
    omega: Var = c.input('OmegaPu',Const(1.))
    reference: Var = c.input('PRefPu',Const(.5))
    speed: Var = c.speed_deviation(omega,deadband_low,deadband_high)
    valve: Var = c.lag('ValvePu',reference-speed/r,t1,p.t1,reference,vmin,vmax)
    turbine: Var = c.lead_lag('SteamPowerPu',valve,t2,t3,p.t2,p.t3,reference)
    power: Var = c.algebraic('PmPu',turbine-damping*(omega-Const(1.)),reference)
    return c.finish((power,valve),'Droop steam governor with asymmetric deadband and independent damping')
