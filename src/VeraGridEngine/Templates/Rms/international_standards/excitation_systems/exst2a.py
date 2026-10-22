# SPDX-License-Identifier: MPL-2.0
"""Compound-source multiplicative static excitation with a additive minimum-excitation input."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.exst2 import CompoundExciterKind, build_exst2_template


def build_exst2a_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build a multiplicatively controlled compound-source static exciter.

    A voltage regulator multiplies a rectified phasor combination of terminal
    voltage and current. The compound bridge includes the five-region
    commutation-loading characteristic. Field-control inductance integrates
    regulator-times-bridge forcing minus linear field loss; directional lower
    and upper stops represent zero excitation and magnetic-component capability.
    Field-voltage washout supplies transient stabilizing feedback. This structure
    uses a additive minimum-excitation input; its placement is explicit
    in the shared physical realization rather than inferred from model names.

    The first eight inputs are sensed voltage, voltage reference, supplementary
    voltage, terminal-voltage real/imaginary components, outgoing stator-current
    real/imaginary components and normalized field current. The gated structure
    appends a voltage-error limiter port and exposes its pre-gate error as a
    second output for exact limiter bypass. The first output is field voltage.
    Time constants use seconds and signals use their connected per-unit bases.
    Initialization balances actual bridge forcing, field voltage and rate
    feedback. Positive sensing/regulator times own states; zero times select
    exact algebraic stages. Shared construction defaults provide four states.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :return: Native multiplicative static excitation controller.
    :raises ValueError: Invalid shared physical construction settings.
    """
    label: str = 'EXST2A' if name is None else name
    return build_exst2_template(vf,label,kind=CompoundExciterKind.MULTIPLICATIVE_BRIDGE)
