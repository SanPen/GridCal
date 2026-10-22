# SPDX-License-Identifier: MPL-2.0
"""Brushless alternator excitation with rate feedback from rectified field voltage."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_exciter import build_brushless_exciter_base
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var


def build_exac1a_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build a brushless rotating exciter stabilized by its rectified field voltage.

    A voltage-sensing lag, phase lead-lag and bounded amplifier drive a rotating
    alternator field circuit. Saturation and the demagnetizing effect of generator
    field current oppose its forcing. The rotating diode bridge reduces available
    field voltage according to commutation loading and prevents negative output.
    The independently supplied voltage regulator retains its capability during
    terminal-voltage disturbances.

    The stabilizing loop applies ``KF*s/(1+s*TF)`` to the rectified output Efd,
    rather than the internal exciter field-current equivalent. The latter signal
    still supplies the physical field-circuit loss term; changing the measurement
    does not remove resistive, saturation or demagnetizing effects. This feedback
    location changes closed-loop gain and phase even when the forward circuits
    and parameter values are otherwise identical.

    Five states store sensed voltage, phase memory, amplifier forcing, alternator
    field voltage and rate-feedback memory. Initialization balances alternator
    forcing and rectifier loading, derives the matching reference and stores
    initial rectified output in the rate-feedback memory. Inputs are generator
    field current, overexcitation voltage, stabilizing voltage, sensed voltage,
    voltage reference and underexcitation voltage. The output is field voltage.
    Signals are per unit on their connected voltage/current bases; all time
    constants are seconds. Positive sensing, phase, amplifier, field and feedback
    times select this realization.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :return: Native five-state brushless excitation controller.
    """
    label: str = 'EXAC1A' if name is None else name
    template: RmsModelTemplate = build_brushless_exciter_base(vf, label)
    block: Block = template.block
    variables: dict[str, Var] = dict((variable.name, variable) for variable in block.get_all_vars())
    variables.update((variable.name, variable) for variable in block.event_dict)
    memory: Var = variables['avr.derivative.x_'+label]
    feedback: Var = variables['avr.derivative.y_'+label]
    current_equivalent: Var = variables['avr.add3.y_'+label]
    field_voltage: Var = variables['avr.EfdPu_'+label]
    substitution: dict[Var, Expr] = dict(((current_equivalent, field_voltage),))
    for index, variable in enumerate(block.state_vars):
        if variable == memory:
            block.state_eqs[index] = block.state_eqs[index].subs(substitution)
        else:
            pass
    for index, variable in enumerate(block.algebraic_vars):
        if variable == feedback:
            block.algebraic_eqs[index] = block.algebraic_eqs[index].subs(substitution)
        else:
            pass
    # The new sensor's memory starts at Efd0, not at the exciter's internal
    # field-current equivalent, which generally has a different steady value.
    block.event_dict[variables['avr.derivative.x_start_'+label]] = variables['avr.Efd0Pu_'+label]
    template.comment = 'Brushless excitation with rectified-field-voltage rate feedback'
    return template
