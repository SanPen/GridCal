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
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, HydroPlantStorageKind


class HydroPowerPlant(PowerSystemResource):
	def __init__(self, rdfid='', tpe='HydroPowerPlant'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_generating_unit import HydroGeneratingUnit
		self.HydroGeneratingUnits: HydroGeneratingUnit | None = None
		self.hydroPlantStorageType: HydroPlantStorageKind = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.hydro_pump import HydroPump
		self.HydroPumps: HydroPump | None = None

		self.register_property(
			name='HydroGeneratingUnits',
			class_type=HydroGeneratingUnit,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The hydro generating unit belongs to a hydro power plant.''',
			profiles=[]
		)
		self.register_property(
			name='hydroPlantStorageType',
			class_type=HydroPlantStorageKind,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The type of hydro power plant water storage.''',
			profiles=[]
		)
		self.register_property(
			name='HydroPumps',
			class_type=HydroPump,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The hydro pump may be a member of a pumped storage plant or a pump for distributing water.''',
			profiles=[]
		)
