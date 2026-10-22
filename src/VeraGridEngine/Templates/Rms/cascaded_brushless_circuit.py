# SPDX-License-Identifier: MPL-2.0
"""Physical power-source and takeover choices for cascaded rotating excitation."""
from __future__ import annotations
from enum import Enum
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.st4c import CompoundExcitationSource, CompoundSupplementLocation


class CascadedLimiterLocation(Enum):
    """Signed error addition or takeover before PID, after PID, or after field PI."""
    ERROR_SUM = 1
    ERROR_GATE = 2
    VOLTAGE_OUTPUT_GATE = 3
    FIELD_OUTPUT_GATE = 4


class CascadedPowerSupply(Enum):
    """Loaded potential source or power derived from delivered field voltage."""
    RECTIFIED_POTENTIAL = 1
    SELF_EXCITED = 2


class CascadedBrushlessCircuit:
    """Compound-source extension and explicit limiter locations for cascaded field control."""
    __slots__ = ('ki','xl','theta','kc1','vbmax','kr','source','power_supply','minimum_location','maximum_location','supplement_location')

    def __init__(self, ki: float = 0., xl: float = 0., theta: float = 0., kc1: float = 0.,
                 vbmax: float = 5., kr: float = 1.,
                 source: CompoundExcitationSource = CompoundExcitationSource.INDEPENDENT,
                 power_supply: CascadedPowerSupply = CascadedPowerSupply.RECTIFIED_POTENTIAL,
                 minimum_location: CascadedLimiterLocation = CascadedLimiterLocation.ERROR_SUM,
                 maximum_location: CascadedLimiterLocation = CascadedLimiterLocation.ERROR_SUM,
                 supplement_location: CompoundSupplementLocation = CompoundSupplementLocation.ERROR_SUM) -> None:
        """Store source bridge, self-excitation and physical connection settings.

        :param ki: Nonnegative potential current gain.
        :param xl: Nonnegative potential-circuit reactance, per unit.
        :param theta: Potential phase, degrees.
        :param kc1: Nonnegative source-bridge loading on winding-current equivalent.
        :param vbmax: Available source voltage ceiling, positive when selected.
        :param kr: Self-excitation gain, positive when selected.
        :param source: Terminal compound or independent potential KP.
        :param power_supply: Rectified potential or KR times delivered field.
        :param minimum_location: Error addition or takeover before/after voltage PID.
        :param maximum_location: Error addition or takeover before/after PID or field PI.
        :param supplement_location: Before or after the input minimum gate.
        """
        self.ki: float = ki
        self.xl: float = xl
        self.theta: float = theta
        self.kc1: float = kc1
        self.vbmax: float = vbmax
        self.kr: float = kr
        self.source: CompoundExcitationSource = source
        self.power_supply: CascadedPowerSupply = power_supply
        self.minimum_location: CascadedLimiterLocation = minimum_location
        self.maximum_location: CascadedLimiterLocation = maximum_location
        self.supplement_location: CompoundSupplementLocation = supplement_location
