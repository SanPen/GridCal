# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, Dict

from GridCalEngine.IO.raw.devices.multi_section_line import RawMultiLineSection
from GridCalEngine.IO.raw.devices.psse_object import RawObject, PsseProperty
from GridCalEngine.IO.raw.devices.area import RawArea
from GridCalEngine.IO.raw.devices.branch import RawBranch
from GridCalEngine.IO.raw.devices.bus import RawBus
from GridCalEngine.IO.raw.devices.facts import RawFACTS
from GridCalEngine.IO.raw.devices.generator import RawGenerator
from GridCalEngine.IO.raw.devices.induction_machine import RawInductionMachine
from GridCalEngine.IO.raw.devices.inter_area import RawInterArea
from GridCalEngine.IO.raw.devices.load import RawLoad
from GridCalEngine.IO.raw.devices.fixed_shunt import RawFixedShunt
from GridCalEngine.IO.raw.devices.switched_shunt import RawSwitchedShunt
from GridCalEngine.IO.raw.devices.transformer import RawTransformer
from GridCalEngine.IO.raw.devices.two_terminal_dc_line import RawTwoTerminalDCLine
from GridCalEngine.IO.raw.devices.vsc_dc_line import RawVscDCLine
from GridCalEngine.IO.raw.devices.zone import RawZone
from GridCalEngine.IO.raw.devices.owner import RawOwner
from GridCalEngine.IO.raw.devices.substation import RawSubstation
from GridCalEngine.IO.raw.devices.gne_device import RawGneDevice
from GridCalEngine.IO.raw.devices.impedance_correction_table import RawImpedanceCorrectionTable
from GridCalEngine.IO.raw.devices.system_switching_device import RawSystemSwitchingDevice
from GridCalEngine.IO.base.base_circuit import BaseCircuit
from GridCalEngine.basic_structures import Logger


class PsseCircuit(RawObject, BaseCircuit):

    def __init__(self):
        RawObject.__init__(self, "Circuit")
        BaseCircuit.__init__(self)

        self.IC = ''
        self.SBASE = 100.0
        self.REV = 35
        self.XFRRAT = 0
        self.NXFRAT = 0
        self.BASFRQ = 50

        self.areas: List[RawArea] = list()

        self.inter_areas: List[RawInterArea] = list()

        self.zones: List[RawZone] = list()

        self.owners: List[RawOwner] = list()

        self.buses: List[RawBus] = list()

        self.branches: List[RawBranch] = list()

        self.transformers: List[RawTransformer] = list()

        self.two_terminal_dc_lines: List[RawTwoTerminalDCLine] = list()

        self.vsc_dc_lines: List[RawVscDCLine] = list()

        self.facts: List[RawFACTS] = list()

        self.loads: List[RawLoad] = list()

        self.generators: List[RawGenerator] = list()

        self.induction_machines: List[RawInductionMachine] = list()

        self.fixed_shunts: List[RawFixedShunt] = list()

        self.switched_shunts: List[RawSwitchedShunt] = list()

        self.substations: List[RawSubstation] = list()

        self.switches: List[RawSystemSwitchingDevice] = list()

        self.gne: List[RawGneDevice] = list()

        self.indiction_tables: List[RawImpedanceCorrectionTable] = list()

        self.multi_line_sections: List[RawMultiLineSection] = list()

        self.register_property(property_name="areas", rawx_key="area", class_type=RawArea)
        self.register_property(property_name="inter_areas", rawx_key="iatrans", class_type=RawInterArea)
        self.register_property(property_name="zones", rawx_key="zone", class_type=RawZone)
        self.register_property(property_name="owners", rawx_key="owner", class_type=RawOwner)
        self.register_property(property_name="buses", rawx_key="bus", class_type=RawBus)
        self.register_property(property_name="branches", rawx_key="acline", class_type=RawBranch)
        self.register_property(property_name="transformers", rawx_key="transformer", class_type=RawTransformer)
        self.register_property(property_name="two_terminal_dc_lines", rawx_key="twotermdc",
                               class_type=RawTwoTerminalDCLine)
        self.register_property(property_name="vsc_dc_lines", rawx_key="vscdc", class_type=RawVscDCLine)
        self.register_property(property_name="facts", rawx_key="facts", class_type=RawFACTS)
        self.register_property(property_name="loads", rawx_key="load", class_type=RawLoad)
        self.register_property(property_name="generators", rawx_key="generator", class_type=RawGenerator)
        self.register_property(property_name="induction_machines", rawx_key="indmach", class_type=RawInductionMachine)
        self.register_property(property_name="fixed_shunts", rawx_key="fixshunt", class_type=RawFixedShunt)
        self.register_property(property_name="switched_shunts", rawx_key="swshunt", class_type=RawSwitchedShunt)
        self.register_property(property_name="substations", rawx_key="sub", class_type=RawSubstation)
        self.register_property(property_name="switches", rawx_key="subswd", class_type=RawSystemSwitchingDevice)
        self.register_property(property_name="gne", rawx_key="gne", class_type=RawGneDevice)
        self.register_property(property_name="indiction_tables", rawx_key="impcor",
                               class_type=RawImpedanceCorrectionTable)
        self.register_property(property_name="multi_line_sections", rawx_key="msline",
                               class_type=RawMultiLineSection)

    def parse(self, data: List[int | float], logger: Logger) -> None:
        """
        Parse the basic data
        :param data: line with information
        :param logger: logger object
        :return:
        """
        if len(data) == 6:
            self.IC, self.SBASE, self.REV, self.XFRRAT, self.NXFRAT, self.BASFRQ = data
        elif len(data) == 3:
            self.IC, self.SBASE, self.REV = data
            logger.add_warning("RAW header contains 3 elements instead of the expected 6")
        else:
            logger.add_warning(f"RAW header contains {len(data)} elements instead of the expected 6")

    def get_class_properties(self) -> List[PsseProperty]:
        """

        :return:
        """
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

                if uuid_ in global_index:
                    found_elm = global_index[uuid_]
                    logger.add_error(msg="Global UUID5 duplicate", device=id_,
                                     device_class=prop.rawx_key, value=uuid_,
                                     comment="Found {}:{}".format(found_elm.class_name, found_elm.get_id()))
                else:
                    global_index[uuid_] = elm

