# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.base import Base
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class SvPowerFlow(Base):

    def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
        """
        General CIM object container
        :param rdfid: RFID
        :param tpe: type of the object (class)
        """
        Base.__init__(self, rdfid='', tpe=tpe, resources=resources, class_replacements=class_replacements)

        self.Terminal: Terminal = None

        self.p: float = 0.0

        self.q: float = 0.0

        self.register_property(name='Terminal',
                               class_type=Terminal,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The terminal associated with the power flow state variable. Default: None",
                               profiles=[cgmesProfile.SV])

        self.register_property(name='p',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="The active power flow. Load sign convention is used, i.e. "
                                           "positive sign means flow out from a TopologicalNode (bus) into the "
                                           "conducting equipment. Default: 0.0",
                               profiles=[cgmesProfile.SV])

        self.register_property(name='q',
                               class_type=float,
                               multiplier=UnitMultiplier.M,
                               unit=UnitSymbol.W,
                               description="The reactive power flow. Load sign convention is used, i.e. "
                                           "positive sign means flow out from a TopologicalNode (bus) into the "
                                           "conducting equipment. Default: 0.0",
                               profiles=[cgmesProfile.SV])
