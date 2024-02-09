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
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.equipment import Equipment
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile


class HydroPump(Equipment):
	def __init__(self, rdfid='', tpe='HydroPump'):
		Equipment.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.hydro_power_plant import HydroPowerPlant
		self.HydroPowerPlant: HydroPowerPlant | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.rotating_machine import RotatingMachine
		self.RotatingMachine: RotatingMachine | None = None

		self.register_property(
			name='HydroPowerPlant',
			class_type=HydroPowerPlant,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The hydro pump may be a member of a pumped storage plant or a pump for distributing water.''',
			profiles=[]
		)
		self.register_property(
			name='RotatingMachine',
			class_type=RotatingMachine,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The synchronous machine drives the turbine which moves the water from a low elevation to a higher elevation. The direction of machine rotation for pumping may or may not be the same as for generating.''',
			profiles=[]
		)
