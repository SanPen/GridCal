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
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, UnitSymbol


class TapChanger(PowerSystemResource):
	def __init__(self, rdfid='', tpe='TapChanger'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		self.highStep: int = None
		self.lowStep: int = None
		self.ltcFlag: bool = None
		self.neutralStep: int = None
		self.neutralU: float = None
		self.normalStep: int = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.tap_changer_control import TapChangerControl
		self.TapChangerControl: TapChangerControl | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.sv_tap_step import SvTapStep
		self.SvTapStep: SvTapStep | None = None
		self.controlEnabled: bool = None
		self.step: float = None

		self.register_property(
			name='highStep',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Highest possible tap step position, advance from neutral.
The attribute shall be greater than lowStep.''',
			profiles=[]
		)
		self.register_property(
			name='lowStep',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Lowest possible tap step position, retard from neutral.''',
			profiles=[]
		)
		self.register_property(
			name='ltcFlag',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Specifies whether or not a TapChanger has load tap changing capabilities.''',
			profiles=[]
		)
		self.register_property(
			name='neutralStep',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The neutral tap step position for this winding.
The attribute shall be equal to or greater than lowStep and equal or less than highStep.
It is the step position where the voltage is neutralU when the other terminals of the transformer are at the ratedU.  If there are other tap changers on the transformer those taps are kept constant at their neutralStep.''',
			profiles=[]
		)
		self.register_property(
			name='neutralU',
			class_type=float,
			multiplier=UnitMultiplier.k,
			unit=UnitSymbol.V,
			description='''Electrical voltage, can be both AC and DC.''',
			profiles=[]
		)
		self.register_property(
			name='normalStep',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The tap step position used in "normal" network operation for this winding. For a "Fixed" tap changer indicates the current physical tap setting.
The attribute shall be equal to or greater than lowStep and equal to or less than highStep.''',
			profiles=[]
		)
		self.register_property(
			name='TapChangerControl',
			class_type=TapChangerControl,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The regulating control scheme in which this tap changer participates.''',
			profiles=[]
		)
		self.register_property(
			name='SvTapStep',
			class_type=SvTapStep,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The tap step state associated with the tap changer.''',
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
		self.register_property(
			name='step',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Tap changer position.
Starting step for a steady state solution. Non integer values are allowed to support continuous tap variables. The reasons for continuous value are to support study cases where no discrete tap changer has yet been designed, a solution where a narrow voltage band forces the tap step to oscillate or to accommodate for a continuous solution as input.
The attribute shall be equal to or greater than lowStep and equal to or less than highStep.''',
			profiles=[]
		)
