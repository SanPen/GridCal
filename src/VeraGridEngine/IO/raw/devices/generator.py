# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.base.units import Unit
from VeraGridEngine.IO.raw.devices.psse_object import RawObject
from VeraGridEngine.basic_structures import Logger


class RawGenerator(RawObject):

    def __init__(self) -> None:
        RawObject.__init__(self, "Generator")

        self.I = 0
        self.ID = 0
        self.PG = 0
        self.QG = 0
        self.QT = 9999.0
        self.QB = -9999.0
        self.VS = 1.0
        self.IREG = 0
        self.NREG = 0
        self.MBASE = 0
        self.ZR = 0
        self.ZX = 0
        self.RT = 0
        self.XT = 0
        self.GTAP = 0
        self.STAT = 0
        self.RMPCT = 100.0
        self.PT = 0
        self.PB = 0
        self.BASLOD = 0
        self.O1 = 1
        self.F1 = 1.0
        self.O2 = 0
        self.F2 = 1.0
        self.O3 = 0
        self.F3 = 1.0
        self.O4 = 0
        self.F4 = 1.0
        self.WMOD = 0
        self.WPF = 0

        self.register_property(property_name="I",
                               rawx_key="ibus",
                               class_type=int,
                               description="Bus number",
                               min_value=1,
                               max_value=999997,
                               max_chars=6)

        self.register_property(property_name="ID",
                               rawx_key="machid",
                               class_type=str,
                               description="2-character ID",
                               max_chars=2)

        self.register_property(property_name="PG",
                               rawx_key="pg",
                               class_type=float,
                               description="Active power output",
                               unit=Unit.get_mw())

        self.register_property(property_name="QG",
                               rawx_key="qg",
                               class_type=float,
                               description="Reactive power output",
                               unit=Unit.get_mvar())

        self.register_property(property_name="QT",
                               rawx_key="qt",
                               class_type=float,
                               description="Maximum generator reactive power output;",
                               unit=Unit.get_mvar())

        self.register_property(property_name="QB",
                               rawx_key="qb",
                               class_type=float,
                               description="Minimum generator reactive power output",
                               unit=Unit.get_mvar())

        self.register_property(property_name="VS",
                               rawx_key="vs",
                               class_type=float,
                               description="Regulated voltage set point",
                               unit=Unit.get_pu())

        self.register_property(property_name="IREG",
                               rawx_key="ireg",
                               class_type=int,
                               description="Regulation bus, zero to regulate its own bus",
                               min_value=0,
                               max_value=999997)

        self.register_property(property_name="NREG",
                               rawx_key="nreg",
                               class_type=int,
                               description="Node number of bus IREG when IREG's bus is a substation",
                               min_value=0,
                               max_value=999997)

        self.register_property(property_name="MBASE",
                               rawx_key="mbase",
                               class_type=float,
                               description="Nominal power",
                               unit=Unit.get_mva())

        self.register_property(property_name="ZR",
                               rawx_key="zr",
                               class_type=float,
                               description="Machine resistance in p.u. of MBASE",
                               unit=Unit.get_pu())

        self.register_property(property_name="ZX",
                               rawx_key="zx",
                               class_type=float,
                               description="Machine reactance in p.u. of MBASE",
                               unit=Unit.get_pu())

        self.register_property(property_name="RT",
                               rawx_key="rt",
                               class_type=float,
                               description="Step-up transformer resistance in p.u. of MBASE",
                               unit=Unit.get_pu())

        self.register_property(property_name="XT",
                               rawx_key="xt",
                               class_type=float,
                               description="Step-up transformer reactance in p.u. of MBASE",
                               unit=Unit.get_pu())

        self.register_property(property_name="GTAP",
                               rawx_key="gtap",
                               class_type=float,
                               description="Step-up transformer off-nominal turns ratio; "
                                           "entered in pu on a system base.",
                               unit=Unit.get_pu())

        self.register_property(property_name="STAT",
                               rawx_key="stat",
                               class_type=int,
                               description="Status",
                               min_value=0,
                               max_value=1)

        self.register_property(property_name="RMPCT",
                               rawx_key="rmpct",
                               class_type=float,
                               description="Percent of the total Mvar required to hold the voltage at the control bus",
                               min_value=0,
                               max_value=100.0,
                               unit=Unit.get_percent())

        self.register_property(property_name="PT",
                               rawx_key="pt",
                               class_type=float,
                               description="Maximum generator active power output;",
                               unit=Unit.get_mw())

        self.register_property(property_name="PB",
                               rawx_key="pb",
                               class_type=float,
                               description="Minimum generator active power output",
                               unit=Unit.get_mw())

        self.register_property(property_name="BASLOD",
                               rawx_key="baslod",
                               class_type=int,
                               description="Base load flag",
                               min_value=0,
                               max_value=2)

        for i in range(4):
            self.register_property(property_name="O{}".format(i + 1),
                                   rawx_key="o{}".format(i + 1),
                                   class_type=int,
                                   description="Owner number",
                                   min_value=1,
                                   max_value=9999)
            self.register_property(property_name="F{}".format(i + 1),
                                   rawx_key="f{}".format(i + 1),
                                   class_type=float,
                                   description="Ownership fraction",
                                   min_value=0.0,
                                   max_value=1.0)

        self.register_property(property_name="WMOD",
                               rawx_key="wmod",
                               class_type=int,
                               description="Machine control mode;",
                               min_value=0,
                               max_value=4)

        self.register_property(property_name="WPF",
                               rawx_key="wpf",
                               class_type=float,
                               description="Power factor",
                               unit=Unit.get_pu())

    def parse(self, data, version, logger: Logger):
        """

        :param data:
        :param version:
        :param logger:
        """

        var = [self.O1, self.F1,
               self.O2, self.F2,
               self.O3, self.F3,
               self.O4, self.F4]

        if version >= 35:
            # I,'ID',      PG,        QG,        QB,     VS,    IREG,     MBASE,
            # ZR,         ZX,         RT,         XT,     GTAP,STAT, RMPCT,      PT,        PB,
            # O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4,
            # WMOD,  WPF
            (self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.NREG, self.MBASE,
             self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, self.BASLOD,
             *var, self.WMOD, self.WPF) = data[0]

        elif 30 <= version <= 34:
            # I,'ID',      PG,        QG,        QB,     VS,    IREG,     MBASE,
            # ZR,         ZX,         RT,         XT,     GTAP,STAT, RMPCT,      PT,        PB,
            # O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4,
            # WMOD,  WPF
            (self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.MBASE,
             self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, *var,
             self.WMOD, self.WPF) = data[0]

        elif version in [29]:
            """
            I,ID,PG,QG,QT,QB,VS,IREG,MBASE,
            ZR,ZX,RT,XT,GTAP,STAT,RMPCT,PT,PB,
            O1,F1,...,O4,F4
            """

            (self.I, self.ID, self.PG, self.QG, self.QT, self.QB, self.VS, self.IREG, self.MBASE, 
                self.ZR, self.ZX, self.RT, self.XT, self.GTAP, self.STAT, self.RMPCT, self.PT, self.PB, *var) = data[0]

        else:
            logger.add_warning('Generator not implemented for version', str(version))

    def get_raw_line(self, version):

        var = ["O1", "F1",
               "O2", "F2",
               "O3", "F3",
               "O4", "F4"]

        if version >= 35:
            # I,'ID',      PG,        QG,        QB,     VS,    IREG,     MBASE,
            # ZR,         ZX,         RT,         XT,     GTAP,STAT, RMPCT,      PT,        PB,
            # O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4,
            # WMOD,  WPF
            return self.format_raw_line(["I", "ID", "PG", "QG", "QT", "QB", "VS", "IREG",
                                         "NREG", "MBASE", "ZR", "ZX", "RT", "XT", "GTAP",
                                         "STAT", "RMPCT", "PT", "PB", "BASLOD"] + var +
                                        ["WMOD", "WPF"])

        elif 30 <= version <= 34:
            # I,'ID',      PG,        QG,        QB,     VS,    IREG,     MBASE,
            # ZR,         ZX,         RT,         XT,     GTAP,STAT, RMPCT,      PT,        PB,
            # O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4,
            # WMOD,  WPF
            return self.format_raw_line(["I", "ID", "PG", "QG", "QT", "QB", "VS", "IREG",
                                         "MBASE", "ZR", "ZX", "RT", "XT", "GTAP", "STAT",
                                         "RMPCT", "PT", "PB"] + var + ["WMOD", "WPF"])

        elif version in [29]:
            """
            I,ID,PG,QG,QT,QB,VS,IREG,MBASE,
            ZR,ZX,RT,XT,GTAP,STAT,RMPCT,PT,PB,
            O1,F1,...,O4,F4
            """

            return self.format_raw_line(["I", "ID", "PG", "QG", "QT", "QB", "VS", "IREG",
                                         "MBASE", "ZR", "ZX", "RT", "XT", "GTAP", "STAT",
                                         "RMPCT", "PT", "PB"] + var)

        else:
            raise Exception('Generator not implemented for version ' + str(version))

    def get_id(self) -> str:
        """
        Get the element PSSE ID
        :return:
        """
        return "{0}_{1}".format(self.I, self.ID)
