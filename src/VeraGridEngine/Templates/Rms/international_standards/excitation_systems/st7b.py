# SPDX-License-Identifier: MPL-2.0
"""Static excitation with reference takeover and dynamic delivered-field feedback."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.self_feedback_exciter import (
    ExcitationBridgeDynamics, SelfFeedbackExciterParameters, build_self_feedback_exciter,
)


def build_st7b_template(vf: VarFactory, name: str | None = None,
                        parameters: SelfFeedbackExciterParameters | None = None) -> RmsModelTemplate:
    """Build static excitation with a shaped measurement and output-feedback loop.

    A voltage transducer and measurement lead-lag oppose a bounded reference.
    Maximum excitation selects signed reference addition, a low reference gate
    or a low output gate. Minimum excitation independently selects reference
    addition, a high reference gate or a high output gate. At each location the
    low gate precedes the high gate. Supplementary voltage enters after reference
    capability clipping. Proportional regulation is bounded between moving
    capabilities VT*VRMIN-KH*z and VT*VRMAX-KL*z, where z is filtered delivered
    field feedback KIA/(1+s*TIA)*Efd.

    A regulator phase compensator follows those bounds, and z adds to its output
    before the selected final gates and terminal-powered field limits.
    The bridge delivers limited forcing algebraically, without an extra firing-control state.
    The terminal-scaled ceiling is applied last if bounds cross. The two feedback
    coefficients remain independent; the inner limits do not become an invented
    ordinary PI regulator or a fixed amplifier capability.

    Six inputs are sensed voltage, reference, supplementary voltage, minimum
    limiter, actual terminal voltage and maximum limiter. Five outputs provide
    delivered field and demand before each reference/output gate. Absent gates
    connect to these exact live demands; absent additive signals supply zero.
    Initialization balances z0=KIA*Efd0 and proportional demand Efd0-z0, accounting
    for nonzero auxiliary biases. Signals use compatible per-unit bases and
    seconds. Positive lags give four states; permitted zero sensing/phase pairs
    reduce algebraically. Feedback time is positive.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique instance label.
    :param parameters: Physical coefficients and independent limiter selections.
    :return: Native six-input static excitation controller.
    :raises ValueError: Invalid physical coefficients, limits or selections.
    """
    return build_self_feedback_exciter(vf,'ST7B' if name is None else name,
        ExcitationBridgeDynamics.INSTANTANEOUS,parameters)
