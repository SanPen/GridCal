# SPDX-License-Identifier: MPL-2.0
"""Three-channel static excitation with selectable summed or takeover limiters."""
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.self_feedback_exciter import ExcitationLimiterLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st5b import ParallelChannelExciterParameters, build_parallel_channel_exciter


def build_st5c_template(vf: VarFactory, name: str | None = None,
                        parameters: ParallelChannelExciterParameters | None = None) -> RmsModelTemplate:
    """Build static excitation with three independently evolving bounded channels.

    Minimum and maximum excitation each choose signed addition at voltage
    error or a takeover gate. Only a strict gate takeover selects that limiter's
    channel; a summed signal always leaves channel selection unchanged. Maximum
    takeover has priority when both gates act. Supplementary voltage enters
    after the gates. All six compensator memories evolve even while inactive.

    Seven inputs are sensed voltage, reference, supplement, field current,
    terminal magnitude, minimum and maximum limiter signals. Six outputs are
    field voltage, two pre-gate demands and three channel demands. Voltage and
    current use compatible per-unit bases; times are seconds. The final field
    capability follows actual terminal magnitude. Positive lead stages track
    clipped output through numerator time; zero lead gives a bounded lag.

    All channels initialize to (EFD0+KC*IFD0)/KR. Reference initialization
    subtracts actual summed limiter and supplementary biases. Unconnected
    sums use zero; unconnected gates follow their own pre-gate demand. Positive
    gain, proper filters and feasible initial capabilities are required.

    :param vf: Shared symbolic factory.
    :param name: Optional controller label.
    :param parameters: Channel settings and independent limiter locations.
    :return: Native selectable-location three-channel excitation controller.
    :raises ValueError: Invalid domains or unsupported limiter location.
    """
    p: ParallelChannelExciterParameters = ParallelChannelExciterParameters(
        minimum_location=ExcitationLimiterLocation.REFERENCE_SUM,
        maximum_location=ExcitationLimiterLocation.REFERENCE_SUM) if parameters is None else parameters
    return build_parallel_channel_exciter(vf,'ST5C' if name is None else name,p)
