# SPDX-License-Identifier: MPL-2.0
"""Asymmetric control deadband for electrohydraulic PID regulation with raw-speed mechanical damping."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.international_standards.governors.pidgov import PidHydroGovernorParameters, build_pidgov_template


def build_pidgovd_template(vf: VarFactory, name: str | None = None,
                           parameters: PidHydroGovernorParameters | None = None) -> RmsModelTemplate:
    """Build deadbanded hydraulic PID control without suppressing physical shaft damping.

    Excess speed deviation outside asymmetric thresholds opposes the filtered
    permanent-droop error. Within the control deadband, proportional, integral
    and derivative speed corrections vanish, while raw-speed turbine damping
    remains active. The distinct droop-feedback selection, two controller
    filters, filtered derivative, gate velocity/travel stops, calibrated
    gate/power curve and inverse-response water column remain explicit.

    Inputs are absolute shaft speed, selected droop reference and turbine-base
    electrical power. Outputs are turbine-base mechanical power, actual gate
    and bounded gate velocity. Seven states exist with positive measurement
    time; zero measurement time removes its memory exactly. Initial mechanical
    and electrical powers are independent frozen operating-point parameters;
    monotone curve inversion initializes actual gate position. Time constants
    use seconds, and the host owns all electrical/turbine power conversions.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param parameters: Physical coefficients, feedback selection and deadband thresholds.
    :return: Native deadbanded hydraulic PID governor.
    :raises ValueError: Invalid physical domains, curve or control deadband.
    """
    label: str = 'PIDGOVD' if name is None else name
    p: PidHydroGovernorParameters = PidHydroGovernorParameters(deadband_low=-.0005,deadband_high=.0005) if parameters is None else parameters
    return build_pidgov_template(vf,label,p)
