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
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.injections.shunt.shunt_compensator import ShuntCompensator
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol


class SvShuntCompensatorSections(Base):

    def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
        """
        General CIM object container
        :param rdfid: RFID
        :param tpe: type of the object (class)
        """
        Base.__init__(self, rdfid='', tpe=tpe, resources=resources, class_replacements=class_replacements)

        self.ShuntCompensator: ShuntCompensator = None

        self.sections: int = 0

        self.register_property(name='ShuntCompensator',
                               class_type=ShuntCompensator,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The shunt compensator for which the state applies.",
                               profiles=[cgmesProfile.SV],
                               mandatory=True)

        self.register_property(name='sections',
                               class_type=int,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The number of sections in service as a continous variable. "
                                           "To get integer value scale with ShuntCompensator.bPerSection.",
                               profiles=[cgmesProfile.SV])
