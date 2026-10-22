# SPDX-License-Identifier: MPL-2.0
"""Electrical-power damping with three independently limited rational filters."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.rational_controller import RationalStageLimiting, RationalStageParameters, build_rational_stage
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var


def build_ivost_template(vf: VarFactory, name: str | None = None,
                         stages: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] | None = None) -> RmsModelTemplate:
    """Build three-stage electrical-power damping with distinct limiting semantics.

    Each stage has transfer K*(A+s*L)/(B+s*T). The first two stages use
    bounded output-tracking recovery, while the final stage has an external
    output limiter around unrestricted filter memory. Stable lead-lags,
    washouts, integral stages after guaranteed zero-DC inputs and exact static
    reductions preserve their different physical memory behavior. Nonnegative
    A/B/time coefficients and signed gains are supported; denominator-zero
    integrators driven by nonzero steady power are rejected rather than given
    fictitious steady initial states.

    The single input is electrical active power on one declared power base.
    The single output is supplementary excitation voltage. Gains carry the
    corresponding inter-stage units; times are seconds. Up to three memories
    store the compensator states. A washout starts with memory canceling actual
    initial power. Subsequent integrators start at zero when their upstream
    structure guarantees zero input. Stable stages propagate their actual
    clipped DC outputs, so nonzero steady supplementary bias is preserved.

    Default settings select power washout followed by two lead-lags. All
    original coefficient and capability symbols remain independent. A host
    freezes actual initial electrical power and owns its power-base conversion,
    then accounts for the resulting steady auxiliary voltage in exciter startup.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique instance label.
    :param stages: Exactly three coefficient/capability groups in cascade order.
    :return: Native electrical-power stabilizer with explicit stage limiting.
    :raises ValueError: Invalid stage count, domains or an unbalanced integral input.
    """
    settings: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] = (
        (RationalStageParameters(gain=2.,numerator=0.,lead=1.,lag=2.,maximum=.1,minimum=-.1),
         RationalStageParameters(maximum=.1,minimum=-.1),RationalStageParameters(maximum=.1,minimum=-.1))
        if stages is None else stages)
    if len(settings) != 3:
        raise ValueError('Power damping requires exactly three rational compensation stages')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'IVOST' if name is None else name)
    power0: Var = c.parameter('InitialElectricalPowerPu',.5)
    signal: Var = c.input('ElectricalPowerPu',power0)
    initial: Expr = power0
    zero_dc: bool = False
    stage_index: int
    stage: RationalStageParameters
    limiting: RationalStageLimiting
    for stage_index,stage,limiting in zip((1,3,5),settings,(
            RationalStageLimiting.OUTPUT_TRACKING,RationalStageLimiting.OUTPUT_TRACKING,RationalStageLimiting.OUTPUT_ONLY)):
        signal,initial,zero_dc = build_rational_stage(c,stage_index,signal,initial,zero_dc,stage,limiting)
    return c.finish((signal,),'Three-stage electrical-power damping with independent rational filters and capability limits')
