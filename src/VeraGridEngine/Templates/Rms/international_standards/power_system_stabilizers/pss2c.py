# SPDX-License-Identifier: MPL-2.0
"""Four-phase dual-input damping with limited measurements and explicitly ordered ramp tracking."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.ramp_tracking_stabilizer import RampStabilizerKind, RampStabilizerParameters, StabilizerInterface, build_ramp_tracking_stabilizer


def build_pss2c_template(vf: VarFactory, name: str | None = None,
                          parameters: RampStabilizerParameters | None = None,
                          interface: StabilizerInterface = StabilizerInterface.SHAFT_SPEED_POWER) -> RmsModelTemplate:
    """Build four-phase dual-input damping with continuously enabled output.

    Independently limited measurements pass through paired washouts and optional
    transducers. With conditioned paths A and B, including the second-path gain,
    ramp tracking produces ``R*(A+KS3*B)-B``, where
    ``R=[(1+s*T8)/(1+s*T9)**M]**N``. Four independent lead/lag compensators shape
    the gained signal before supplementary-voltage clipping. Ramp order selects
    exactly M*N memories; zero M or N bypasses that filter. Zero second washouts,
    transducer times and proper zero-time phase pairs are exact bypasses.

    This continuous construction requires positive first-washout times on both
    paths, yielding zero supplementary output at any constant operating point.
    It contains no electrical-power enable/disable hysteresis and no compensated
    frequency estimator. A host requiring either feature must supply a reviewed
    external realization rather than treating a different measurement as that
    signal. Output clipping does not freeze any filter memory.

    Default ports preserve absolute shaft speed, its reference and electrical
    power; the selected-measurement interface exposes two host-scaled signals.
    Output is per-unit supplementary excitation voltage. All times use seconds;
    the host owns measurement selection and electrical power bases.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Washout, ramp, four-phase and limiter coefficients.
    :param interface: Selected measurements or shaft/reference/power input ports.
    :return: Native continuously enabled dual-input damping controller.
    :raises ValueError: Invalid physical coefficients, limits or improper stages.
    """
    return build_ramp_tracking_stabilizer(vf,'PSS2C' if name is None else name,
        RampStabilizerKind.LIMITED_FOUR_PHASE,parameters,interface)
