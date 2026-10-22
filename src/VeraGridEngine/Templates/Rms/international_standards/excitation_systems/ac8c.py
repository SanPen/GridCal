# SPDX-License-Identifier: MPL-2.0
"""Compound-fed rotating excitation with bounded PID and selectable limiter gates."""
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac8b import PidBrushlessExciterParameters, CompoundPidPowerCircuit, build_pid_brushless_exciter


def build_ac8c_template(vf: VarFactory, name: str | None = None,
                        parameters: PidBrushlessExciterParameters | None = None,
                        circuit: CompoundPidPowerCircuit | None = None) -> RmsModelTemplate:
    """Build PID regulation of a rotating field with an explicit loaded power source.

    A compound terminal-voltage/current potential or independent potential KP
    feeds a controlled bridge. Its diode loading uses the exciter winding's
    current equivalent VFE, distinct from generator field current IFD used by
    the output diode bridge. Available supply is capped at VBMAX and multiplies
    the bounded amplifier demand before driving the rotating field.

    Limiters independently add at voltage error, take over before PID or take
    over between PID and amplifier. Minimum gates precede maximum gates. The
    supplementary signal enters before or immediately after the input minimum
    gate. PID and amplifier have separate directional anti-windup limits.

    Ten inputs are sensed voltage, reference, supplement, real/imaginary
    terminal voltage, real/imaginary outgoing current, field current and two
    limiter signals. Outputs are delivered field and four pre-gate demands.
    Times are seconds, phase is degrees and voltage/current bases must agree.
    Five full-order memories initialize from actual field, diode loading and
    winding loss; supply division sets amplifier demand and actual summed
    auxiliary biases set reference. Initial supply must be positive and all
    capabilities feasible. Absent gates follow exposed pre-gate outputs.

    :param vf: Shared symbolic factory.
    :param name: Optional controller label.
    :param parameters: PID, amplifier, rotating-field and output-diode settings.
    :param circuit: Potential, supply-diode and signal-location settings.
    :return: Native compound-fed PID rotating excitation controller.
    :raises ValueError: Invalid domains, capabilities or selections.
    """
    power: CompoundPidPowerCircuit = CompoundPidPowerCircuit() if circuit is None else circuit
    return build_pid_brushless_exciter(vf,'AC8C' if name is None else name,parameters,power)
