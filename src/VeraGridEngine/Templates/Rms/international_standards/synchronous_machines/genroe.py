# SPDX-License-Identifier: MPL-2.0
"""Round-rotor synchronous machine with power-law magnetic saturation."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import (
    GenrouSaturationMode, get_genrou_rms_template,
)


def build_genroe_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Build a six-state round-rotor machine with power-law saturation.

    Rotor angle, speed, two transient rotor voltages and two damper-winding flux
    states describe mechanical and subtransient electromagnetic behavior. The
    stator equations retain armature resistance and d/q-axis saliency. Both
    magnetic axes respond to saturation of the resultant subtransient flux.

    The saturation factor is S(psi)=S10*psi**n, with
    n=log(S12/S10)/log(1.2). Its amplitude and exponent therefore reproduce the
    specified factors at resultant fluxes 1.0 and 1.2 pu. The field and q-axis
    rotor equations consume this factor through their respective magnetizing
    paths; replacing it by a quadratic curve changes the physical model.

    Inputs are terminal voltage magnitude/angle, mechanical torque and field
    voltage. Outputs include terminal active/reactive power and the machine
    signals needed by excitation and turbine controls. Angles use electrical
    radians, times use seconds, and impedances, powers and inertia share the
    chosen network power base. Initialization solves the saturated rotor/stator
    balance from terminal P/Q rather than imposing an unsaturated rotor angle.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :return: Network-ready native machine with six continuous states.
    """
    label: str = 'GENROE' if name is None else name
    template: RmsModelTemplate = get_genrou_rms_template(vf,label,GenrouSaturationMode.POWER_LAW)
    template.comment = 'Round-rotor synchronous machine with power-law magnetic saturation'
    return template
