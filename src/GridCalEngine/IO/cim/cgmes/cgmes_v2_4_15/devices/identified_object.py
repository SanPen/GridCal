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


class IdentifiedObject(Base):
	def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
		Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

		self.description: str = None
		self.energyIdentCodeEic: str = None
		self.mRID: str = rdfid
		self.name: str = None
		self.shortName: str = None

		self.register_property(
			name='description',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The description is a free human readable text describing or naming the object. It may be non unique and may not correlate to a naming hierarchy.''',
			profiles=[]
		)
		self.register_property(
			name='energyIdentCodeEic',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The attribute is used for an exchange of the EIC code (Energy identification Code). The length of the string is 16 characters as defined by the EIC code.
References: 
<ul>
	<li>Local issuing offices for EIC: <a href="https://www.entsoe.eu/publications/edi-library/links-to-eic-websites/"><font color="#0000ff"><u>https://www.entsoe.eu/publications/edi-library/links-to-eic-websites/</u></font></a> </li>
	<li>EIC description: <a href="https://www.entsoe.eu/index.php?id=73&amp;libCat=eic"><font color="#0000ff"><u>https://www.entsoe.eu/index.php?id=73&amp;libCat=eic</u></font></a> .</li>
</ul>''',
			profiles=[]
		)
		self.register_property(
			name='mRID',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''Master resource identifier issued by a model authority. The mRID is globally unique within an exchange context. Global uniqueness is easily achieved by using a UUID,  as specified in RFC 4122, for the mRID.  The use of UUID is strongly recommended.
For CIMXML data files in RDF syntax conforming to IEC 61970-552 Edition 1, the mRID is mapped to rdf:ID or rdf:about attributes that identify CIM object elements.''',
			profiles=[]
		)
		self.register_property(
			name='name',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The name is any free human readable and possibly non unique text naming the object.''',
			profiles=[]
		)
		self.register_property(
			name='shortName',
			class_type=str,
			multiplier=UnitMultiplier.none,
			unit=UnitSymbol.none,
			description='''The attribute is used for an exchange of a human readable short name with length of the string 12 characters maximum.''',
			profiles=[]
		)
