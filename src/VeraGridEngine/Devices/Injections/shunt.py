# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.enumerations import BuildStatus
from VeraGridEngine.Devices.Parents.shunt_parent import ShuntParent
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, DynamicVarType

class Shunt(ShuntParent):

    def __init__(self, name='shunt', idtag=None, code='',
                 G=0.0, B=0.0, active=True,
                 G1=0.0, G2=0.0, G3=0.0, B1=0.0, B2=0.0, B3=0.0,
                 mttf=0.0, mttr=0.0,
                 G0=0, B0=0,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """
        Fixed shunt, not controllable

        :param name: Name of the device
        :param idtag: unique id of the device (if None or "" a new one is generated)
        :param code: secondary code for compatibility
        :param active:active state
        :param G: positive conductance (MW @ v=1 p.u.)
        :param G1: phase 1 conductance (MW @ v=1 p.u.)
        :param G2: phase 2 conductance (MW @ v=1 p.u.)
        :param G3: phase 3 conductance (MW @ v=1 p.u.)
        :param B: positive conductance (MVAr @ v=1 p.u.)
        :param B1: phase 1 conductance (MVAr @ v=1 p.u.)
        :param B2: phase 2 conductance (MVAr @ v=1 p.u.)
        :param B3: phase 3 conductance (MVAr @ v=1 p.u.)
        :param G0: zero-sequence conductance (MW @ v=1 p.u.)
        :param B0: zero-sequence conductance (MVAr @ v=1 p.u.)
        :param mttf: mean time to failure (h)
        :param mttr: mean time to recovery (h)
        :param capex: capital expenditures (investment cost)
        :param opex: operational expenditures (maintenance cost)
        :param build_status: BuildStatus
        """

        ShuntParent.__init__(self,
                             name=name,
                             idtag=idtag,
                             code=code,
                             bus=None,
                             active=active,
                             G=G,
                             G1=G1,
                             G2=G2,
                             G3=G3,
                             B=B,
                             B1=B1,
                             B2=B2,
                             B3=B3,
                             G0=G0,
                             B0=B0,
                             Cost=0.0,
                             mttf=mttf,
                             mttr=mttr,
                             capex=capex,
                             opex=opex,
                             build_status=build_status,
                             device_type=DeviceType.ShuntDevice)
        
        Sbase: float = 100 #NOTE: to remove
        self.g = self.G / Sbase
        self.b = self.B / Sbase
        
    def initialize_rms(self):
        if self.rms_model.empty():

            Pshunt = Var("Pshunt")
            Qshunt = Var("Qshunt")

            Vm = self.bus.rms_model.model.E(DynamicVarType.Vm) 

            # Assign Block
            self.rms_model.model = Block(
                algebraic_eqs=[
                    Pshunt - self.g * Vm**2,
                    Qshunt - self.b * Vm**2
                ],
                algebraic_vars=[Pshunt, Qshunt],
                init_eqs={
                    Pshunt: self.g * Vm**2,
                    Qshunt: self.b * Vm**2
                },
                init_vars=[Pshunt, Qshunt],
                parameters=[],
                external_mapping={
                    DynamicVarType.P: Pshunt,
                    DynamicVarType.Q: Qshunt
                }
            )
