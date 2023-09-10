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
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_enums import cgmesProfile
from GridCalEngine.IO.cim.cgmes_2_4_15.devices.base import Base, str2num, index_find
from GridCalEngine.data_logger import DataLogger


class IdentifiedObject(Base):

    def __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):
        """
        General CIM object container
        :param rdfid: RFID
        :param tpe: type of the object (class)
        """
        Base.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, class_replacements=class_replacements)

        self.name = ''
        self.shortName = ''
        self.description = ''
        self.energyIdentCodeEic = ''
        self.aggregate: bool = False

        # document followed for the implementation
        self.standard_document = '57_1816e_DTS.pdf'

        # register the CIM properties
        self.register_property(name='rdfid',
                               class_type=str,
                               description="Master resource identifier issued by a model "
                                           "authority. The mRID is globally unique within an "
                                           "exchange context. Global uniqueness is easily "
                                           "achieved by using a UUID, as specified in RFC "
                                           "4122, for the mRID. The use of UUID is strongly "
                                           "recommended.",
                               profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                                         cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                                         cgmesProfile.SV])

        self.register_property(name='name',
                               class_type=str,
                               description='The name is any free human readable and '
                                           'possibly non unique text naming the object.',
                               profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                                         cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                                         cgmesProfile.SV, ])

        self.register_property(name='shortName',
                               class_type=str,
                               description='The attribute is used for an exchange of a '
                                           'human readable short name with length of the '
                                           'string 12 characters maximum.',
                               max_chars=12,
                               profiles=[cgmesProfile.TP_BD, cgmesProfile.EQ, cgmesProfile.TP, cgmesProfile.EQ_BD])

        self.register_property(name='description',
                               class_type=str,
                               description="The attribute is used for an exchange of the "
                                           "EIC code (Energy identification Code). "
                                           "The length of the string is 16 characters as "
                                           "defined by the EIC code.",
                               profiles=[cgmesProfile.TP_BD, cgmesProfile.EQ, cgmesProfile.DY,
                                         cgmesProfile.TP, cgmesProfile.EQ_BD])

        self.register_property(name='energyIdentCodeEic',
                               class_type=str,
                               description='The attribute is used for an exchange '
                                           'of the EIC code (Energy identification '
                                           'Code). The length of the string is 16 '
                                           'characters as defined by the EIC code.',
                               max_chars=16,
                               profiles=[cgmesProfile.TP_BD, cgmesProfile.EQ, cgmesProfile.TP, cgmesProfile.EQ_BD])

        self.register_property(name='aggregate',
                               class_type=bool,
                               description='Aggregate identifier',
                               profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                                         cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                                         cgmesProfile.SV])
