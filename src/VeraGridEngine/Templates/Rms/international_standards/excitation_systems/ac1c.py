# SPDX-License-Identifier: MPL-2.0
"""Brushless rotating excitation with selectable limiter routing and a field-current stop."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.dc_exciter import RotatingLimiterLocation
from VeraGridEngine.Templates.Rms.international_standards.excitation_systems.esac1a import build_esac1a_template
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_limiters import configure_brushless_limiters
from VeraGridEngine.Templates.Rms.international_standards.common.brushless_field_limits import limit_brushless_field
from VeraGridEngine.Utils.Symbolic.symbolic import Var


def build_ac1c_template(vf: VarFactory, name: str | None = None,
                        minimum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION,
                        maximum_location: RotatingLimiterLocation = RotatingLimiterLocation.SUMMATION) -> RmsModelTemplate:
    """Build independently supplied brushless excitation with selected limiters.

    Voltage sensing, phase compensation and a bounded amplifier feed the
    rotating exciter. Minimum and maximum excitation signals independently select signed addition
    before phase compensation or high/low takeover after amplification. The
    high gate precedes the low gate; independent forcing bounds follow both.
    Additive absent signals are zero, while absent takeover gates connect to
    their exact preceding demand.

    Field resistance, quadratic magnetic saturation and current demagnetization
    determine Vfe. Filtered Vfe rate feedback subtracts from voltage error.
    The field integrator has a zero lower stop and a separate ceiling detected
    by Vfe reaching VFEMAX. Outward motion stops; inward recovery remains active
    even when generator current moves the ceiling past continuous field memory.
    A current-loaded diode bridge converts internal exciter voltage to delivered
    generator field voltage through its piecewise commutation characteristic.

    Inputs are generator field current, maximum-excitation signal, stabilizing
    voltage, sensed voltage, reference and minimum-excitation signal. Outputs
    are delivered field voltage, demand before the high gate and demand before
    the low gate. Voltages/currents use connected per-unit field bases; times
    are seconds. Five states store sensing, phase, amplifier, field and feedback
    memories. Initialization solves the loaded rectifier and balances actual
    field losses; all active capabilities must admit that operating point.
    This realization requires positive sensing, phase-lag, amplifier, field and
    feedback times, positive resistance and nonnegative saturation/loading.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique instance label.
    :param minimum_location: Additive or high-gate minimum limiter insertion.
    :param maximum_location: Additive or low-gate maximum limiter insertion.
    :return: Native five-state brushless excitation controller.
    :raises ValueError: Invalid limiter insertion selectors.
    """
    label: str = 'AC1C' if name is None else name
    template: RmsModelTemplate = build_esac1a_template(vf,label)
    variables: dict[str,Var] = dict((variable.name,variable) for variable in template.block.get_all_vars())
    variables.update((variable.name,variable) for variable in template.block.event_dict)
    limit_brushless_field(template.block,vf,label,variables['FieldForcingPu_'+label],variables)
    configure_brushless_limiters(template.block,label,minimum_location,maximum_location)
    template.comment = 'Brushless excitation with selectable limiter insertion and field-current ceiling'
    return template
