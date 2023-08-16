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

from typing import List, Dict
from GridCal.Engine.IO.psse.devices.psse_object import PSSeObject, PsseProperty
from GridCal.Engine.IO.psse.devices.area import PSSeArea
from GridCal.Engine.IO.psse.devices.branch import PSSeBranch
from GridCal.Engine.IO.psse.devices.bus import PSSeBus
from GridCal.Engine.IO.psse.devices.facts import PSSeFACTS
from GridCal.Engine.IO.psse.devices.generator import PSSeGenerator
from GridCal.Engine.IO.psse.devices.induction_machine import PSSeInductionMachine
from GridCal.Engine.IO.psse.devices.inter_area import PSSeInterArea
from GridCal.Engine.IO.psse.devices.load import PSSeLoad
from GridCal.Engine.IO.psse.devices.fixed_shunt import PSSeFixedShunt
from GridCal.Engine.IO.psse.devices.switched_shunt import PSSeSwitchedShunt
from GridCal.Engine.IO.psse.devices.transformer import PSSeTransformer
from GridCal.Engine.IO.psse.devices.two_terminal_dc_line import PSSeTwoTerminalDCLine
from GridCal.Engine.IO.psse.devices.vsc_dc_line import PSSeVscDCLine
from GridCal.Engine.IO.psse.devices.zone import PSSeZone
from GridCal.Engine.IO.psse.devices.owner import PSSeOwner
from GridCal.Engine.IO.psse.devices.substation import PSSeSubstation
from GridCal.Engine.IO.psse.devices.gne_device import PSSeGneDevice
from GridCal.Engine.IO.psse.devices.system_switching_device import PSSeSystemSwitchingDevice
from GridCal.Engine.IO.base.base_circuit import BaseCircuit
from GridCal.Engine.basic_structures import Logger


class PsseCircuit(PSSeObject, BaseCircuit):

    def __init__(self):
        PSSeObject.__init__(self, "Circuit")
        BaseCircuit.__init__(self)

        self.IC = ''
        self.SBASE = 100.0
        self.REV = 35
        self.XFRRAT = 0
        self.NXFRAT = 0
        self.BASFRQ = 50

        self.areas: List[PSSeArea] = list()

        self.inter_areas: List[PSSeInterArea] = list()

        self.zones: List[PSSeZone] = list()

        self.owners: List[PSSeOwner] = list()

        self.buses: List[PSSeBus] = list()

        self.branches: List[PSSeBranch] = list()

        self.transformers: List[PSSeTransformer] = list()

        self.two_terminal_dc_lines: List[PSSeTwoTerminalDCLine] = list()

        self.vsc_dc_lines: List[PSSeVscDCLine] = list()

        self.facts: List[PSSeFACTS] = list()

        self.loads: List[PSSeLoad] = list()

        self.generators: List[PSSeGenerator] = list()

        self.induction_machines: List[PSSeInductionMachine] = list()

        self.fixed_shunts: List[PSSeFixedShunt] = list()

        self.switched_shunts: List[PSSeSwitchedShunt] = list()

        self.substations: List[PSSeSubstation] = list()

        self.switches: List[PSSeSystemSwitchingDevice] = list()

        self.gne: List[PSSeGneDevice] = list()

        self.register_property(property_name="areas", rawx_key="area", class_type=PSSeArea)
        self.register_property(property_name="inter_areas", rawx_key="iatrans", class_type=PSSeInterArea)
        self.register_property(property_name="zones", rawx_key="zone", class_type=PSSeZone)
        self.register_property(property_name="owners", rawx_key="owner", class_type=PSSeOwner)
        self.register_property(property_name="buses", rawx_key="bus", class_type=PSSeBus)
        self.register_property(property_name="branches", rawx_key="acline", class_type=PSSeBranch)
        self.register_property(property_name="transformers", rawx_key="transformer", class_type=PSSeTransformer)
        self.register_property(property_name="two_terminal_dc_lines", rawx_key="twotermdc", class_type=PSSeTwoTerminalDCLine)
        self.register_property(property_name="vsc_dc_lines", rawx_key="vscdc", class_type=PSSeVscDCLine)
        self.register_property(property_name="facts", rawx_key="facts", class_type=PSSeFACTS)
        self.register_property(property_name="loads", rawx_key="load", class_type=PSSeLoad)
        self.register_property(property_name="generators", rawx_key="generator", class_type=PSSeGenerator)
        self.register_property(property_name="induction_machines", rawx_key="indmach", class_type=PSSeInductionMachine)
        self.register_property(property_name="fixed_shunts", rawx_key="fixshunt", class_type=PSSeFixedShunt)
        self.register_property(property_name="switched_shunts", rawx_key="swshunt", class_type=PSSeSwitchedShunt)
        self.register_property(property_name="substations", rawx_key="sub", class_type=PSSeSubstation)
        self.register_property(property_name="switches", rawx_key="subswd", class_type=PSSeSystemSwitchingDevice)
        self.register_property(property_name="gne", rawx_key="gne", class_type=PSSeGneDevice)

    def parse(self, data):
        a = ""
        b = ""
        var = [a, b]
        self.IC, self.SBASE, self.REV, self.XFRRAT, self.NXFRAT, self.BASFRQ = data

    def get_class_properties(self) -> List[PsseProperty]:
        return [p for p in self.get_properties() if p.class_type not in [str, bool, int, float]]

    def check_primary_keys(self, logger: Logger = Logger()):
        """
        Check all primary keys locally and globally
        :param logger:
        :return:
        """

        global_index = dict()

        for prop in self.get_class_properties():

            local_index = dict()
            lst = getattr(self, prop.property_name)

            for elm in lst:
                id_ = elm.get_id()
                uuid_ = elm.get_uuid5()

                if id_ in local_index:
                    found_elm = local_index[id_]
                    logger.add_error(msg="Local ID duplicate", device=id_,
                                     device_class=prop.rawx_key,
                                     comment="Found {}:{}".format(found_elm.class_name, found_elm.get_id()))
                else:
                    local_index[id_] = elm

                # if id_ in global_index:
                #     found_elm = global_index[id_]
                #     logger.add_error(msg="Global ID duplicate", device=id_, device_class=prop.rawx_key,
                #                      comment="Found {}:{}".format(found_elm.class_name, found_elm.get_id()))
                # else:
                #     global_index[id_] = elm

                # if uuid_ in local_index:
                #     found_elm = local_index[uuid_]
                #     logger.add_error(msg="Local UUID5 duplicate", device=id_, device_class=prop.rawx_key, value=uuid_,
                #                      comment="Found {}:{}".format(found_elm.class_name, found_elm.get_id()))
                # else:
                #     local_index[uuid_] = elm

                if uuid_ in global_index:
                    found_elm = global_index[uuid_]
                    logger.add_error(msg="Global UUID5 duplicate", device=id_,
                                     device_class=prop.rawx_key, value=uuid_,
                                     comment="Found {}:{}".format(found_elm.class_name, found_elm.get_id()))
                else:
                    global_index[uuid_] = elm

