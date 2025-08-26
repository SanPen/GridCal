# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_system_resource import PowerSystemResource
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType, UnitSymbol


class TapChanger(PowerSystemResource):
	def __init__(self, rdfid='', tpe='TapChanger'):
		PowerSystemResource.__init__(self, rdfid, tpe)

		self.highStep: int = None
		self.lowStep: int = None
		self.ltcFlag: bool = None
		self.neutralStep: int = None
		self.neutralU: float = None
		self.normalStep: int = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.tap_changer_control import TapChangerControl
		self.TapChangerControl: TapChangerControl | None = None
		from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_tap_step import SvTapStep
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
			description='''Lowest possible tap step position, retard from neutral''',
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
The attribute shall be equal or greater than lowStep and equal or less than highStep.''',
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
			description='''The tap step position used in &quot;normal&quot; network operation for this winding. For a &quot;Fixed&quot; tap changer indicates the current physical tap setting.
The attribute shall be equal or greater than lowStep and equal or less than highStep.''',
			profiles=[]
		)
		self.register_property(
			name='TapChangerControl',
			class_type=TapChangerControl,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The tap changers that participates in this regulating tap control scheme.''',
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
			description='''A floating point number. The range is unspecified and not limited.''',
			profiles=[]
		)
