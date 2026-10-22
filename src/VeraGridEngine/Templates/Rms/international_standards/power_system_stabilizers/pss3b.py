# SPDX-License-Identifier: MPL-2.0
"""Dual-measurement supplementary damping with optional washouts and two quadratic phase compensators."""
from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.international_standards.power_system_stabilizers.ieeest import polynomial_measurement_filter
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class QuadraticDualStabilizerParameters:
    """Physical measurement gains, optional lags/washouts and quadratic phase coefficients."""
    __slots__ = ('gains','transducer_times','washout_times','coefficients','upper','lower')

    def __init__(self, gains: tuple[float,float] = (1.,-.5),
                 transducer_times: tuple[float,float] = (.02,.03),
                 washout_times: tuple[float,float,float] = (10.,12.,0.),
                 coefficients: tuple[float,float,float,float,float,float,float,float] = (.1,.01,.2,.02,.1,.01,.2,.02),
                 upper: float = .1, lower: float = -.1) -> None:
        """Store physical controller coefficients; construction validates their domains.

        :param gains: Two finite nonzero measurement gains, allowing opposite signs.
        :param transducer_times: Nonnegative measurement lag times in seconds.
        :param washout_times: Two channel washouts and one common washout in seconds; zero bypasses.
        :param coefficients: A1..A8 defining two quadratic numerator/denominator pairs.
        :param upper: Upper supplementary-voltage capability.
        :param lower: Lower supplementary-voltage capability.
        """
        self.gains: tuple[float,float] = gains
        self.transducer_times: tuple[float,float] = transducer_times
        self.washout_times: tuple[float,float,float] = washout_times
        self.coefficients: tuple[float,float,float,float,float,float,float,float] = coefficients
        self.upper: float = upper
        self.lower: float = lower


def _quadratic_stabilizer_channel(c: ControlRealization, index: int, signal: Var,
                                  gain_value: float, lag_value: float, washout_value: float) -> Var:
    """Realize one measurement path with its own physical gain and optional dynamic memories.

    :param c: Owning physical controller graph.
    :param index: One-based channel index for signal/coefficient names.
    :param signal: Host-scaled measured input and equilibrium seed.
    :param gain_value: Nonzero physical input gain.
    :param lag_value: Nonnegative transducer time in seconds.
    :param washout_value: Nonnegative washout time in seconds; zero bypasses.
    :return: Conditioned signal with an exact operating-point initializer.
    """
    suffix: str = str(index)
    gain: Var = c.parameter('KS'+suffix,gain_value)
    lag: Var = c.parameter('T'+suffix,lag_value)
    washout: Var = c.parameter('TW'+suffix,washout_value)
    measured: Var = c.lag('Measured'+suffix+'Pu',gain*signal,lag,lag_value,gain*signal)
    if washout_value > 0:
        return c.washout('Washout'+suffix+'Pu',measured,washout,washout_value,Const(1.),measured)
    else:
        return c.algebraic('Washout'+suffix+'Pu',measured,measured)


def build_pss3b_template(vf: VarFactory, name: str | None = None,
                          parameters: QuadraticDualStabilizerParameters | None = None) -> RmsModelTemplate:
    """Build dual-input damping with independently conditioned measurements and quadratic phase shaping.

    Each selected measurement passes through its own signed gain, transducer
    lag and washout. Their sum passes through an optional common washout and
    the two phase compensators
    ``(1+A1*s+A2*s**2)/(1+A3*s+A4*s**2)`` and
    ``(1+A5*s+A6*s**2)/(1+A7*s+A8*s**2)``. Supplementary-voltage limits act only
    after these stages. Filter memories keep responding while output is clipped.
    Unlike a factored real-pole approximation, the polynomial realization handles
    repeated and complex poles without discarding numerator feedthrough.

    Inputs are two host-selected, host-scaled measurements; output is per-unit
    supplementary excitation voltage. There is no implicit shaft-speed reference,
    electrical power-base conversion, remote-bus selection or voltage supervisor
    inside the physical controller. Those connections belong to the host.
    All transducer/washout times are seconds. Polynomial first/second coefficients
    have units of seconds/seconds squared respectively.

    Zero transducer or washout time produces an exact bypass. Constant-input
    initialization follows each active or bypassed path, including nonzero
    steady signals when every washout is bypassed. Proper zero coefficients
    reduce polynomial state order exactly; improper differentiators are rejected.
    Nine states exist with all lags/washouts active and quadratic denominators.
    This construction has no electrical-power enable/disable hysteresis.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical channel, washout, phase and limiter coefficients.
    :return: Native dual-input supplementary-voltage controller.
    :raises ValueError: Invalid domains, nonfinite coefficients or improper polynomial stages.
    """
    p: QuadraticDualStabilizerParameters = QuadraticDualStabilizerParameters() if parameters is None else parameters
    groups: tuple[tuple[float,...],...] = (p.gains,p.transducer_times,p.washout_times,p.coefficients,(p.upper,p.lower))
    if not all(math.isfinite(value) for group in groups for value in group):
        raise ValueError('Quadratic dual-input stabilizer coefficients must be finite')
    elif min(p.transducer_times) < 0 or min(p.washout_times) < 0 or p.lower >= p.upper:
        raise ValueError('Dual-input stabilizer times and voltage limits are invalid')
    elif p.gains[0] == 0 or p.gains[1] == 0:
        raise ValueError('Both quadratic dual-input measurement gains must be nonzero')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'PSS3B' if name is None else name)
    signal1: Var = c.input('Signal1Pu',Const(0.))
    signal2: Var = c.input('Signal2Pu',Const(0.))
    first: Var = _quadratic_stabilizer_channel(c,1,signal1,p.gains[0],p.transducer_times[0],p.washout_times[0])
    second: Var = _quadratic_stabilizer_channel(c,2,signal2,p.gains[1],p.transducer_times[1],p.washout_times[1])
    combined: Var = c.algebraic('CombinedPu',first+second,first+second)
    common_time: Var = c.parameter('TW3',p.washout_times[2])
    common: Var
    if p.washout_times[2] > 0:
        common = c.washout('CommonWashoutPu',combined,common_time,p.washout_times[2],Const(1.),combined)
    else:
        common = c.algebraic('CommonWashoutPu',combined,combined)
    a: tuple[float,float,float,float,float,float,float,float] = p.coefficients
    phase1: Var = polynomial_measurement_filter(c,common,(a[2],a[3],0.,0.,a[0],a[1]),'First')
    phase2: Var = polynomial_measurement_filter(c,phase1,(a[6],a[7],0.,0.,a[4],a[5]),'Second')
    upper: Var = c.parameter('VSTMAX',p.upper)
    lower: Var = c.parameter('VSTMIN',p.lower)
    output_initial: Expr = sym.hard_sat(phase2,lower,upper)
    output: Var = c.algebraic('VsPu',sym.hard_sat(phase2,lower,upper),output_initial)
    return c.finish((output,),'Dual-input damping with optional washouts and two exact quadratic phase compensators')
