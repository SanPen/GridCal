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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.energy_connection import EnergyConnection
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class RegulatingCondEq(EnergyConnection):
	def __init__(self, rdfid='', tpe='RegulatingCondEq'):
		EnergyConnection.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.regulating_control import RegulatingControl
		self.RegulatingControl: RegulatingControl | None = None
		self.controlEnabled: bool = None

		self.register_property(
			name='RegulatingControl',
			class_type=RegulatingControl,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The regulating control scheme in which this equipment participates.''',
			profiles=[]
		)
		self.register_property(
			name='controlEnabled',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Specifies the regulation status of the equipment.  True is regulating, false is not regulating.''',
			profiles=[]
		)
