# SPDX-License-Identifier: MPL-2.0
"""Cascaded brushless excitation with compound or self-derived power and explicit gates."""
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.cascaded_brushless_circuit import CascadedBrushlessCircuit
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.ac7b import CascadedBrushlessParameters, build_cascaded_brushless_exciter


def build_ac7c_template(vf: VarFactory, name: str | None = None,
                        parameters: CascadedBrushlessParameters | None = None,
                        circuit: CascadedBrushlessCircuit | None = None) -> RmsModelTemplate:
    """Build cascaded PID/PI brushless control with independently selected power and limiter paths.

    A bounded outer voltage PID feeds a separately bounded field PI after mixed
    delivered-field and winding-current feedback. Winding-current washout opposes
    voltage error. Limiters add signed error or take over before/after voltage
    PID; maximum excitation additionally can take over after field PI. High gates
    precede low gates. Supplement can enter before or after the input high gate.

    The field PI is multiplied by a loaded compound/independent potential or KR
    times live delivered EFD. The source bridge loads on winding VFE, distinct
    from generator IFD loading the output bridge. A -KL*VFE forcing floor limits
    negative demand without adding steady damping. Winding dynamics and their
    directional voltage/current stops remain separate from delivered field.

    Ten inputs are sensing, reference, supplement, rectangular terminal voltage,
    rectangular outgoing current, generator field current and two limiter signals.
    Six outputs are delivered field and pre-gate demand at the five takeover
    points. Times are seconds, potential phase is degrees and connected voltage/
    current bases must agree. Six full-order memories reduce exactly for disabled
    paths. Initial diode inversion and winding loss determine field demand divided
    by the selected supply. Mixed feedback determines outer demand; integral or
    proportional offsets balance both loops. Actual summed auxiliary biases set
    reference. Missing sums are zero and missing gates follow exposed pre-gate
    outputs. Positive initial supply and feasible capabilities are required.

    :param vf: Shared native symbolic factory.
    :param name: Optional controller label.
    :param parameters: Cascaded loops, rotating field and output bridge settings.
    :param circuit: Physical source, self-excitation and limiter connections.
    :return: Native selectable-source cascaded rotating excitation controller.
    :raises ValueError: Invalid domains, unavailable power or incompatible selection.
    """
    power: CascadedBrushlessCircuit = CascadedBrushlessCircuit() if circuit is None else circuit
    return build_cascaded_brushless_exciter(vf,'AC7C' if name is None else name,parameters,power)
