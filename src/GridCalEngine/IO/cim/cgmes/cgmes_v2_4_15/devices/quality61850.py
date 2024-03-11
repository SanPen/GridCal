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
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile, Source, Validity


class Quality61850(Base):
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		self.badReference: bool = None
		self.estimatorReplaced: bool = None
		self.failure: bool = None
		self.oldData: bool = None
		self.operatorBlocked: bool = None
		self.oscillatory: bool = None
		self.outOfRange: bool = None
		self.overFlow: bool = None
		self.source: Source = None
		self.suspect: bool = None
		self.test: bool = None
		self.validity: Validity = None

		self.register_property(
			name='badReference',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Measurement value may be incorrect due to a reference being out of calibration.''',
			profiles=[]
		)
		self.register_property(
			name='estimatorReplaced',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Value has been replaced by State Estimator. estimatorReplaced is not an IEC61850 quality bit but has been put in this class for convenience.''',
			profiles=[]
		)
		self.register_property(
			name='failure',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''This identifier indicates that a supervision function has detected an internal or external failure, e.g. communication failure.''',
			profiles=[]
		)
		self.register_property(
			name='oldData',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Measurement value is old and possibly invalid, as it has not been successfully updated during a specified time interval.''',
			profiles=[]
		)
		self.register_property(
			name='operatorBlocked',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Measurement value is blocked and hence unavailable for transmission. ''',
			profiles=[]
		)
		self.register_property(
			name='oscillatory',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''To prevent some overload of the communication it is sensible to detect and suppress oscillating (fast changing) binary inputs. If a signal changes in a defined time (tosc) twice in the same direction (from 0 to 1 or from 1 to 0) then oscillation is detected and the detail quality identifier &quot;oscillatory&quot; is set. If it is detected a configured numbers of transient changes could be passed by. In this time the validity status &quot;questionable&quot; is set. If after this defined numbers of changes the signal is still in the oscillating state the value shall be set either to the opposite state of the previous stable value or to a defined default value. In this case the validity status &quot;questionable&quot; is reset and &quot;invalid&quot; is set as long as the signal is oscillating. If it is configured such that no transient changes should be passed by then the validity status &quot;invalid&quot; is set immediately in addition to the detail quality identifier &quot;oscillatory&quot; (used for status information only).''',
			profiles=[]
		)
		self.register_property(
			name='outOfRange',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Measurement value is beyond a predefined range of value.''',
			profiles=[]
		)
		self.register_property(
			name='overFlow',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Measurement value is beyond the capability of being  represented properly. For example, a counter value overflows from maximum count back to a value of zero. ''',
			profiles=[]
		)
		self.register_property(
			name='source',
			class_type=Source,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Source gives information related to the origin of a value. The value may be acquired from the process, defaulted or substituted.''',
			profiles=[]
		)
		self.register_property(
			name='suspect',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''A correlation function has detected that the value is not consitent with other values. Typically set by a network State Estimator.''',
			profiles=[]
		)
		self.register_property(
			name='test',
			class_type=bool,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Measurement value is transmitted for test purposes.''',
			profiles=[]
		)
		self.register_property(
			name='validity',
			class_type=Validity,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Validity of the measurement value.''',
			profiles=[]
		)
