# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.template_definition import TemplateDefinition, TemplateProp
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class PvLoadRmsTemplate(TemplateDefinition):
    __slots__ = ()

    def __init__(self, vf):
        super().__init__(vf, params=[
            TemplateProp(name="Pg0_val", units="pu", descr="Optional initial active power override; otherwise use power flow.", tpe=float),
            TemplateProp(name="Vg0_val", units="pu", descr="Initial voltage reference.", tpe=float),
            TemplateProp(name="name", units="", descr="Name of the rms model.", tpe=str),
        ])

    def eval(self) -> RmsModelTemplate:
        return PVLoadBuild(self.vf, self.get_value("name"), self.get_value("Pg0_val"), self.get_value("Vg0_val"))


def PVLoadBuild(vfactory: VarFactory, name: str = "PV load RMS template",
                Pg0_val: float | None = None, Vg0_val: float = 1.0) -> RmsModelTemplate:
    """
    Builds an RMS model template for a PV load with reactive power limits.
    
    The PV load model represents a load/generator with constant active power (P)
    and reactive power limited between Qmin and Qmax. When reactive power is within
    limits, the voltage is held at the reference value V0. When reactive power hits
    a limit, the voltage is allowed to vary.
    
    Equations:
        P = Pg0 (constant active power)
        Qh = Qg
        Qg = Qmax_G   if Qh >= Qmax_G
        Vh = Vg0      if Qmax_G < Qh < Qmin_G
        Qg = Qmin_G   if Qh <= Qmin_G
    
    :param vfactory: Factory that owns the model's symbolic variables.
    :param name: Name assigned to the generated RMS model template.
    :param Pg0_val: Optional initial active power in per unit; otherwise use the solved power-flow value.
    :param Vg0_val: Initial voltage reference in per unit.
    :return: Configured PV-load RMS model template.
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name
    
    # Input: Vm (voltage magnitude)
    Vm = vfactory.add_var("Vm")
    inputs = [Vm]
    
    # Variables
    P = vfactory.add_var('P')
    Q = vfactory.add_var('Q')
    
    # Parameters
    Pg0 = vfactory.add_var('Pg0')
    Vg0 = vfactory.add_var('Vg0')
    Qmax_G = vfactory.add_var('Qmax_G')
    Qmin_G = vfactory.add_var('Qmin_G')
    
    # Event dictionary with default values
    event_dict = {
        Pg0: P if Pg0_val is None else vfactory.add_const(Pg0_val),
        Vg0: Vm,
        Qmax_G: vfactory.add_const(1.0),
        Qmin_G: vfactory.add_const(-1.0),
    }
    
    # Initialize Q to Qg0
    init_eqs = {
        P: Pg0,
    }
    
    within_limits = ((Qmax_G - Q)>=0).to_expression() * (0 <= (Q - Qmin_G)).to_expression()
    # 
    # Implementation using saturation:
    # Qg = max(Qmin, min(Qh, Qmax))
    Q_sat = sym.max(Qmin_G, sym.min(Q, Qmax_G))
    
    templ.block = Block(
        algebraic_eqs=[
            P - Pg0,
            (Vm - Vg0) * within_limits + (Q - Q_sat)*(1 - within_limits),
        ],
        algebraic_vars=[P, Q],
        init_eqs=init_eqs,
        event_dict=event_dict,
    )
    
    templ.block.name = 'PV Load'
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.P: P,
        VarPowerFlowReferenceType.Q: Q,
        VarPowerFlowReferenceType.Vm: inputs[0],
    }
    
    templ.block.in_vars = inputs
    
    templ.comment = 'Load RMS PV voltage-dependent model'
    return templ
