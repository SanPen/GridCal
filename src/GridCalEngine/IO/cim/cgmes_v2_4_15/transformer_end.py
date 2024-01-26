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
from GridCalEngine.IO.cim.cgmes_v2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_v2_4_15.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes_v2_4_15.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes_v2_4_15.terminal import Terminal
from GridCalEngine.IO.cim.cgmes_v2_4_15.phase_tap_changer import PhaseTapChanger
from GridCalEngine.IO.cim.cgmes_v2_4_15.ratio_tap_changer import RatioTapChanger


class TransformerEnd(IdentifiedObject):
	def __init__(self, rdfid='', tpe='TransformerEnd'):
		IdentifiedObject.__init__(self, rdfid, tpe)

		self.BaseVoltage: BaseVoltage | None = None
		self.Terminal: Terminal | None = None
		self.PhaseTapChanger: PhaseTapChanger | None = None
		self.RatioTapChanger: RatioTapChanger | None = None
		self.rground: float = 0.0
		self.endNumber: int = 0
		self.grounded: bool = False
		self.xground: float = 0.0

		self.register_property(
			name='BaseVoltage',
			class_type=BaseVoltage,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Base voltage of the transformer end.  This is essential for PU calculation.',
			profiles=[]
		)
		self.register_property(
			name='Terminal',
			class_type=Terminal,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Terminal of the power transformer to which this transformer end belongs.',
			profiles=[]
		)
		self.register_property(
			name='PhaseTapChanger',
			class_type=PhaseTapChanger,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Transformer end to which this phase tap changer belongs.',
			profiles=[]
		)
		self.register_property(
			name='RatioTapChanger',
			class_type=RatioTapChanger,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Transformer end to which this ratio tap changer belongs.',
			profiles=[]
		)
		self.register_property(
			name='rground',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='Resistance (real part of impedance).',
			profiles=[]
		)
		self.register_property(
			name='endNumber',
			class_type=int,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='Number for this transformer end, corresponding to the end's order in the power transformer vector group or phase angle clock number.  Highest voltage winding should be 1.  Each end within a power transformer should have a unique subsequent end number.   Note the transformer end number need not match the terminal sequence number.',
			profiles=[]
		)
		self.register_property(
			name='grounded',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='(for Yn and Zn connections) True if the neutral is solidly grounded.',
			profiles=[]
		)
		self.register_property(
			name='xground',
			class_type=float,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.ohm,
			description='Reactance (imaginary part of impedance), at rated frequency.',
			profiles=[]
		)
