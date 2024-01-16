# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.raw.devices.psse_object import RawObject
from GridCalEngine.basic_structures import Logger
import numpy as np


class RawLoad(RawObject):

    def __init__(self):
        RawObject.__init__(self, "load")

        self.I = 0
        self.ID = '1'
        self.STATUS = 1
        self.AREA = 0
        self.ZONE = 0
        self.PL = 0
        self.QL = 0
        self.IP = 0
        self.IQ = 0
        self.YP = 0
        self.YQ = 0
        self.OWNER = 0
        self.SCALE = 0.0
        self.INTRPT = 0

        self.DGENP = 0
        self.DGENQ = 0
        self.DGENM = 0
        self.LOADTYPE = ''

        self.register_property(property_name="I",
                               rawx_key="ibus",
                               class_type=int,
                               description="Bus number",
                               min_value=1,
                               max_value=999997)

        self.register_property(property_name="ID",
                               rawx_key="loadid",
                               class_type=str,
                               description="Load 2-character ID",
                               max_chars=2)

        self.register_property(property_name="STATUS",
                               rawx_key="stat",
                               class_type=int,
                               description="Status",
                               min_value=0,
                               max_value=1)

        self.register_property(property_name="AREA",
                               rawx_key="area",
                               class_type=int,
                               description="Area number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="ZONE",
                               rawx_key="zone",
                               class_type=int,
                               description="Zone number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="PL",
                               rawx_key="pl",
                               class_type=float,
                               unit=Unit.get_mw(),
                               description="Active power load")

        self.register_property(property_name="QL",
                               rawx_key="ql",
                               class_type=float,
                               unit=Unit.get_mvar(),
                               description="Reactive power load")

        self.register_property(property_name="IP",
                               rawx_key="ip",
                               class_type=float,
                               unit=Unit.get_mw(),
                               description="Active current load @v=1 p.u.")

        self.register_property(property_name="IQ",
                               rawx_key="iq",
                               class_type=float,
                               unit=Unit.get_mvar(),
                               description="Reactive current load @v=1 p.u.")

        self.register_property(property_name="YP",
                               rawx_key="yp",
                               class_type=float,
                               unit=Unit.get_mw(),
                               description="Active admittance power load @v=1 p.u.")

        self.register_property(property_name="YQ",
                               rawx_key="yq",
                               class_type=float,
                               unit=Unit.get_mvar(),
                               description="Reactive admittance power load @v=1 p.u.")

        self.register_property(property_name="OWNER",
                               rawx_key="owner",
                               class_type=int,
                               description="Owner number",
                               min_value=1,
                               max_value=9999)

        self.register_property(property_name="SCALE",
                               rawx_key="scale",
                               class_type=float,
                               unit=Unit.get_pu(),
                               description="Load scaling flag of one for a scalable load and zero for a fixed load")

        self.register_property(property_name="INTRPT",
                               rawx_key="intrpt",
                               class_type=float,
                               description="Interruptible load flag.",
                               min_value=0,
                               max_value=1)

        self.register_property(property_name="DGENP",
                               rawx_key="dgenp",
                               class_type=float,
                               unit=Unit.get_mw(),
                               description="Distributed Generation active power component")

        self.register_property(property_name="DGENQ",
                               rawx_key="dgenq",
                               class_type=float,
                               unit=Unit.get_mvar(),
                               description="Distributed Generation reactive power component")

        self.register_property(property_name="DGENM",
                               rawx_key="dgenm",
                               class_type=int,
                               description="Distributed generation mode 0:off, 1: on.",
                               min_value=0,
                               max_value=1)

        self.register_property(property_name="LOADTYPE",
                               rawx_key="loadtype",
                               class_type=str,
                               description="Load type",
                               max_chars=12)

    def parse(self, data, version, logger: Logger):

        """

        :param data:
        :param version:
        :param logger:
        """

        if version >= 35:

            if len(data[0]) == 18:
                (self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL,
                 self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE, self.INTRPT,
                 self.DGENP, self.DGENQ, self.DGENM, self.LOADTYPE) = data[0]

            elif len(data[0]) == 17:
                (self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL,
                 self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE, self.INTRPT,
                 self.DGENP, self.DGENQ, self.LOADTYPE) = data[0]
            else:
                raise Exception("PSSe 35 load data came with {} "
                                "elements and 18 or 17 were expected :/".format(len(data[0])))

        elif version == 34:

            #  I,'ID',STAT,AREA,ZONE,PL, QL,IP,IQ, YP,YQ, OWNER,SCALE,INTRPT,  DGENP,     DGENQ, DGENF
            n = len(data[0])
            dta = np.zeros(17, dtype=object)
            dta[0:n] = data[0]

            (self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL,
             self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE,
             self.INTRPT, self.DGENP, self.DGENQ, self.DGENM) = dta

        elif version == 33:

            n = len(data[0])
            dta = np.zeros(14, dtype=object)
            dta[0:n] = data[0]

            (self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL,
             self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE, self.INTRPT) = dta
        elif version == 32:

            (self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL,
             self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE) = data[0]

        elif version in [29, 30]:
            # I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER
            self.I, self.ID, self.STATUS, self.AREA, self.ZONE, \
                self.PL, self.QL, self.IP, self.IQ, self.YP, self.YQ, self.OWNER = data[0]

            self.SCALE = 1.0

        else:
            logger.add_warning('Load not implemented for version', str(version))

    def get_raw_line(self, version):
        """
        Get raw file line(s)
        :param version: supported version
        :return: 
        """
        if version >= 35:

            return self.format_raw_line([self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL,
                                         self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE, self.INTRPT,
                                         self.DGENP, self.DGENQ, self.DGENM, self.LOADTYPE])

        elif version in [33, 34]:

            return self.format_raw_line([self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL,
                                         self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE, self.INTRPT])

        elif version == 32:

            return self.format_raw_line([self.I, self.ID, self.STATUS, self.AREA, self.ZONE, self.PL, self.QL,
                                         self.IP, self.IQ, self.YP, self.YQ, self.OWNER, self.SCALE])

        elif version in [29, 30]:
            # I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER
            return self.format_raw_line([self.I, self.ID, self.STATUS, self.AREA, self.ZONE,
                                         self.PL, self.QL, self.IP, self.IQ, self.YP, self.YQ, self.OWNER])

        else:
            raise Exception('Load not implemented for version ' + str(version))

    def get_id(self):
        """
        Get the element PSSE ID
        :return:
        """
        return "{0}_{1}".format(self.I, self.ID)

    def get_seed(self):
        """
        Get the element PSSE Seed
        :return:
        """
        return "{0}_{1}".format(self.I, self.ID)
