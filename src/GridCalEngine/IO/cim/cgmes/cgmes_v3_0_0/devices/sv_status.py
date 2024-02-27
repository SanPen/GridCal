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
from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.base import Base
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class SvStatus(Base):
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conducting_equipment import ConductingEquipment
		self.ConductingEquipment: ConductingEquipment | None = None
		self.inService: bool = None

		self.register_property(
			name='ConductingEquipment',
			class_type=ConductingEquipment,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The conducting equipment associated with the status state variable.''',
			profiles=[]
		)
		self.register_property(
			name='inService',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The in service status as a result of topology processing.  It indicates if the equipment is considered as energized by the power flow. It reflects if the equipment is connected within a solvable island.  It does not necessarily reflect whether or not the island was solved by the power flow.''',
			profiles=[]
		)
