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


class SvTapStep(Base):
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		self.position: float = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tap_changer import TapChanger
		self.TapChanger: TapChanger | None = None

		self.register_property(
			name='position',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The floating point tap position.   This is not the tap ratio, but rather the tap step position as defined by the related tap changer model and normally is constrained to be within the range of minimum and maximum tap positions.''',
			profiles=[]
		)
		self.register_property(
			name='TapChanger',
			class_type=TapChanger,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The tap changer associated with the tap step state.''',
			profiles=[]
		)
