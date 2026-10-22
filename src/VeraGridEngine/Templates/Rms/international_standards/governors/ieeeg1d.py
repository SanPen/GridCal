# SPDX-License-Identifier: MPL-2.0
"""Steam-turbine speed regulation with asymmetric deadband and separate shaft fractions."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.ieeeg1 import (
    MultiStageSteamGovernorParameters, build_ieeeg1_template)


def build_ieeeg1d_template(vf: VarFactory, name: str | None = None,
                           parameters: MultiStageSteamGovernorParameters | None = None) -> RmsModelTemplate:
    """Build deadband steam regulation with bounded valve velocity and position.

    Independent over- and underspeed thresholds define a continuous deadband:
    outside the band, the corresponding threshold is subtracted from speed
    deviation. Compensated speed demand drives a valve with separate opening
    and closing rates and directional position stops. Four cascaded steam lags
    feed independent first- and second-shaft fraction sums. Zero lag times are
    exact algebraic stages and zero deadband thresholds bypass the deadband.

    Up to six states store speed compensation, valve position and turbine
    memories. Initialization at nominal speed divides the total load-power
    reference by the sum of all stage fractions, preserving nonunit turbine
    gain. Inputs are shaft speed, speed reference and load-power reference;
    outputs are first-shaft power, second-shaft power and their total. Powers
    use the declared turbine base, time constants are seconds and valve rates
    are per second; the host owns conversion to the network power base.

    :param vf: Shared native symbolic factory.
    :param name: Optional instance label.
    :param parameters: Physical governor settings; defaults include symmetric 0.0005 speed deadband.
    :return: Native steam governor with asymmetric speed deadband.
    :raises ValueError: Invalid physical parameter domains.
    """
    settings: MultiStageSteamGovernorParameters = (MultiStageSteamGovernorParameters(deadband_high=.0005, deadband_low=-.0005)
        if parameters is None else parameters)
    return build_ieeeg1_template(vf, 'IEEEG1D' if name is None else name, settings)
