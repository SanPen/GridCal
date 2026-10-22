# SPDX-License-Identifier: MPL-2.0
"""Remote voltage sensing port for a regulator's measurement connection."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const


def build_remcmp_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    """Expose a remote bus voltage as an explicit regulator measurement signal.

    This component represents remote sensing rather than an impedance drop or a
    dynamic transducer. Open input ``RemoteVmPu`` receives the selected bus's
    live voltage magnitude; output ``VcPu`` supplies that value unchanged to a
    regulator. There is one algebraic identity and no state, gain, hidden delay
    or assumption about which network bus is remote. The host owns bus selection
    and ensures compatible voltage bases before connecting the port.

    The input seed defaults to one per unit for stand-alone inspection. In a
    network assembly it is replaced by the connected remote operating voltage;
    the output initializes from the same signal, avoiding a nominal-voltage
    guess that disagrees with the actual power-flow solution.

    :param vf: Symbol factory owning the input and measured-voltage output.
    :param name: Optional label, defaulting to REMCMP.
    :return: Stateless native remote-voltage sensing component.
    """
    builder: ControlRealization = ControlRealization(vf,'REMCMP' if name is None else name)
    voltage: Var = builder.input('RemoteVmPu',Const(1.0))
    output: Var = builder.algebraic('VcPu',voltage,voltage)
    return builder.finish((output,),'Remote bus voltage sensing without an artificial transducer delay')
