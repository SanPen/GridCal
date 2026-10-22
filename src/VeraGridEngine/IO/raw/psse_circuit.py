# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import datetime
from pathlib import Path
from typing import List, Dict, Tuple

from VeraGridEngine.IO.raw.psse_object import RawObject
from VeraGridEngine.IO.raw.psse_property import PsseProperty
from VeraGridEngine.IO.raw.psse_file_type import PsseFileType
from VeraGridEngine.IO.raw.psse_conversion_report import PsseImportReport
from VeraGridEngine.IO.raw.psse_auxiliary import BusInputMode, PsseVersion, resolve_psse_version
from VeraGridEngine.IO.raw.raw_types import PsseAuxiliaryDocument
from VeraGridEngine.IO.raw.versioned.base.sub import RawSub
from VeraGridEngine.IO.raw.versioned.base.mon import RawMon
from VeraGridEngine.IO.raw.versioned.base.con_ import RawCon
from VeraGridEngine.IO.raw.versioned.base.dyr import RawDyr
from VeraGridEngine.IO.raw.versioned.base.seq import RawSeq, Sequence35Layout
from VeraGridEngine.IO.raw.versioned.base.rop import RawRop
from VeraGridEngine.IO.raw.versioned.base.gcp import RawGcp
from VeraGridEngine.IO.raw.versioned.base.loc import RawLoc
from VeraGridEngine.IO.raw.sub_parser import read_sub
from VeraGridEngine.IO.raw.mon_parser import read_mon
from VeraGridEngine.IO.raw.con_parser import read_con
from VeraGridEngine.IO.raw.dyr_parser import read_dyr
from VeraGridEngine.IO.raw.seq_parser import read_seq
from VeraGridEngine.IO.raw.rop_parser import read_rop
from VeraGridEngine.IO.raw.gcp_parser import read_gcp
from VeraGridEngine.IO.raw.loc_parser import read_loc
from VeraGridEngine.IO.raw.raw_types import RawAreaLike, RawBranchLike, RawBusLike, RawEquipmentTerminalLike, \
    RawFACTSLike, RawFixedShuntLike, RawGeneratorLike, RawGneDeviceLike, RawImpedanceCorrectionTableLike, \
    RawInductionMachineLike, RawInterAreaLike, RawLoadLike, RawMultiLineSectionLike, RawNodeLike, RawOwnerLike, \
    RawSubstationLike, RawSubstationSwitchingDeviceLike, RawSwitchedShuntLike, RawSystemSwitchingDeviceLike, \
    RawTransformerLike, RawTwoTerminalDCLineLike, RawVscDCLineLike, RawZoneLike
from VeraGridEngine.IO.raw.versioned.base.multi_section_line import RawMultiLineSection
from VeraGridEngine.IO.raw.versioned.base.area import RawArea
from VeraGridEngine.IO.raw.versioned.base.branch import RawBranch
from VeraGridEngine.IO.raw.versioned.base.bus import RawBus
from VeraGridEngine.IO.raw.versioned.base.facts import RawFACTS
from VeraGridEngine.IO.raw.versioned.base.generator import RawGenerator
from VeraGridEngine.IO.raw.versioned.base.induction_machine import RawInductionMachine
from VeraGridEngine.IO.raw.versioned.base.inter_area import RawInterArea
from VeraGridEngine.IO.raw.versioned.base.load import RawLoad
from VeraGridEngine.IO.raw.versioned.base.fixed_shunt import RawFixedShunt
from VeraGridEngine.IO.raw.versioned.base.switched_shunt import RawSwitchedShunt
from VeraGridEngine.IO.raw.versioned.base.transformer import RawTransformer
from VeraGridEngine.IO.raw.versioned.base.two_terminal_dc_line import RawTwoTerminalDCLine
from VeraGridEngine.IO.raw.versioned.base.vsc_dc_line import RawVscDCLine
from VeraGridEngine.IO.raw.versioned.base.zone import RawZone
from VeraGridEngine.IO.raw.versioned.base.owner import RawOwner
from VeraGridEngine.IO.raw.versioned.base.substation import RawSubstation
from VeraGridEngine.IO.raw.versioned.base.node import RawNode
from VeraGridEngine.IO.raw.versioned.base.substation_switching_device import RawSubstationSwitchingDevice
from VeraGridEngine.IO.raw.versioned.base.equipment_terminal import RawEquipmentTerminal
from VeraGridEngine.IO.raw.versioned.base.gne_device import RawGneDevice
from VeraGridEngine.IO.raw.versioned.base.impedance_correction_table import RawImpedanceCorrectionTable
from VeraGridEngine.IO.raw.versioned.base.system_switching_device import RawSystemSwitchingDevice
from VeraGridEngine.IO.base.base_circuit import BaseCircuit
from VeraGridEngine.basic_structures import Logger


class PsseCircuit(RawObject, BaseCircuit):
    LOCAL_PROPERTIES: Tuple[PsseProperty, ...] = (
        PsseProperty(property_name='areas', rawx_key='area', class_type=RawArea),
        PsseProperty(property_name='inter_areas', rawx_key='iatrans', class_type=RawInterArea),
        PsseProperty(property_name='zones', rawx_key='zone', class_type=RawZone),
        PsseProperty(property_name='owners', rawx_key='owner', class_type=RawOwner),
        PsseProperty(property_name='buses', rawx_key='bus', class_type=RawBus),
        PsseProperty(property_name='branches', rawx_key='acline', class_type=RawBranch),
        PsseProperty(property_name='transformers', rawx_key='transformer', class_type=RawTransformer),
        PsseProperty(property_name='two_terminal_dc_lines', rawx_key='twotermdc', class_type=RawTwoTerminalDCLine),
        PsseProperty(property_name='vsc_dc_lines', rawx_key='vscdc', class_type=RawVscDCLine),
        PsseProperty(property_name='facts', rawx_key='facts', class_type=RawFACTS),
        PsseProperty(property_name='loads', rawx_key='load', class_type=RawLoad),
        PsseProperty(property_name='generators', rawx_key='generator', class_type=RawGenerator),
        PsseProperty(property_name='induction_machines', rawx_key='indmach', class_type=RawInductionMachine),
        PsseProperty(property_name='fixed_shunts', rawx_key='fixshunt', class_type=RawFixedShunt),
        PsseProperty(property_name='switched_shunts', rawx_key='swshunt', class_type=RawSwitchedShunt),
        PsseProperty(property_name='substations', rawx_key='sub', class_type=RawSubstation),
        PsseProperty(property_name='nodes', rawx_key='subnode', class_type=RawNode),
        PsseProperty(property_name='substation_switching_devices', rawx_key='subswd',
                     class_type=RawSubstationSwitchingDevice),
        PsseProperty(property_name='equipment_terminals', rawx_key='subterm', class_type=RawEquipmentTerminal),
        PsseProperty(property_name='switches', rawx_key='sysswd', class_type=RawSystemSwitchingDevice),
        PsseProperty(property_name='gne', rawx_key='gne', class_type=RawGneDevice),
        PsseProperty(property_name='indiction_tables', rawx_key='impcor', class_type=RawImpedanceCorrectionTable),
        PsseProperty(property_name='multi_line_sections', rawx_key='msline', class_type=RawMultiLineSection),
        # Documents are registered circuit collections, but not RAWX network sections.
        PsseProperty(property_name='sub_files', rawx_key='', class_type=RawSub, file_type=PsseFileType.SUB),
        PsseProperty(property_name='mon_files', rawx_key='', class_type=RawMon, file_type=PsseFileType.MON),
        PsseProperty(property_name='con_files', rawx_key='', class_type=RawCon, file_type=PsseFileType.CON),
        PsseProperty(property_name='dyr_files', rawx_key='', class_type=RawDyr, file_type=PsseFileType.DYR),
        PsseProperty(property_name='seq_files', rawx_key='', class_type=RawSeq, file_type=PsseFileType.SEQ),
        PsseProperty(property_name='rop_files', rawx_key='', class_type=RawRop, file_type=PsseFileType.ROP),
        PsseProperty(property_name='gcp_files', rawx_key='', class_type=RawGcp, file_type=PsseFileType.GCP),
        PsseProperty(property_name='loc_files', rawx_key='', class_type=RawLoc, file_type=PsseFileType.LOC),
    )

    __slots__ = (
        "IC",
        "SBASE",
        "REV",
        "XFRRAT",
        "NXFRAT",
        "BASFRQ",
        "date_time",
        "areas",
        "inter_areas",
        "zones",
        "owners",
        "buses",
        "branches",
        "transformers",
        "two_terminal_dc_lines",
        "vsc_dc_lines",
        "facts",
        "loads",
        "generators",
        "induction_machines",
        "fixed_shunts",
        "switched_shunts",
        "substations",
        "nodes",
        "substation_switching_devices",
        "equipment_terminals",
        "switches",
        "gne",
        "indiction_tables",
        "multi_line_sections",
        "sub_files",
        "mon_files",
        "con_files",
        "dyr_files",
        "seq_files",
        "rop_files",
        "gcp_files",
        "loc_files",
        "auxiliary_logger",
        "conversion_report",
        "auxiliary_bus_mode",
    )

    def __init__(self) -> None:
        """Initialize network collections and independent auxiliary document collections."""
        RawObject.__init__(self, "Circuit")
        BaseCircuit.__init__(self)

        self.IC = ''
        self.SBASE = 100.0
        self.REV = 35
        self.XFRRAT = 0
        self.NXFRAT = 0
        self.BASFRQ = 50

        self.date_time: datetime.datetime | None = None

        self.areas: List[RawAreaLike] = list()

        self.inter_areas: List[RawInterAreaLike] = list()

        self.zones: List[RawZoneLike] = list()

        self.owners: List[RawOwnerLike] = list()

        self.buses: List[RawBusLike] = list()

        self.branches: List[RawBranchLike] = list()

        self.transformers: List[RawTransformerLike] = list()

        self.two_terminal_dc_lines: List[RawTwoTerminalDCLineLike] = list()

        self.vsc_dc_lines: List[RawVscDCLineLike] = list()

        self.facts: List[RawFACTSLike] = list()

        self.loads: List[RawLoadLike] = list()

        self.generators: List[RawGeneratorLike] = list()

        self.induction_machines: List[RawInductionMachineLike] = list()

        self.fixed_shunts: List[RawFixedShuntLike] = list()

        self.switched_shunts: List[RawSwitchedShuntLike] = list()

        self.substations: List[RawSubstationLike] = list()

        self.nodes: List[RawNodeLike] = list()

        self.substation_switching_devices: List[RawSubstationSwitchingDeviceLike] = list()

        self.equipment_terminals: List[RawEquipmentTerminalLike] = list()

        self.switches: List[RawSystemSwitchingDeviceLike] = list()

        self.gne: List[RawGneDeviceLike] = list()

        self.indiction_tables: List[RawImpedanceCorrectionTableLike] = list()

        self.multi_line_sections: List[RawMultiLineSectionLike] = list()

        # Preserve complete file semantics instead of flattening away headers and order.
        self.sub_files: list[RawSub] = list()
        self.mon_files: list[RawMon] = list()
        self.con_files: list[RawCon] = list()
        self.dyr_files: list[RawDyr] = list()
        self.seq_files: list[RawSeq] = list()
        self.rop_files: list[RawRop] = list()
        self.gcp_files: list[RawGcp] = list()
        self.loc_files: list[RawLoc] = list()
        self.auxiliary_logger: Logger = Logger()
        # Source-specific provenance belongs to the source circuit, not native devices.
        self.conversion_report: PsseImportReport | None = None
        self.auxiliary_bus_mode: BusInputMode = BusInputMode.NUMBERS

    def get_auxiliary_properties(self) -> list[PsseProperty]:
        """Get registered auxiliary collections, including their owning formats.

        :return: Non-network circuit property descriptors.
        """
        return [prop for prop in self.get_properties() if prop.file_type != PsseFileType.RAW]

    def get_rawx_properties(self) -> list[PsseProperty]:
        """Get only properties supported by the RAWX network schema.

        :return: Network properties, excluding auxiliary documents.
        """
        return [prop for prop in self.get_properties() if prop.file_type == PsseFileType.RAW]

    def get_rawx_dict(self) -> dict[str, PsseProperty]:
        """Map actual RAWX network keys without inventing auxiliary sections.

        :return: RAWX network property lookup.
        """
        return dict((prop.rawx_key, prop) for prop in self.get_rawx_properties())

    def get_auxiliary_documents(self) -> tuple[PsseAuxiliaryDocument, ...]:
        """Collect owned documents without copying or rewriting their records.

        :return: All documents, grouped by registered format and ordered within each format.
        """
        documents: list[PsseAuxiliaryDocument] = list()
        for prop in self.get_auxiliary_properties():
            documents.extend(self.get_prop_value(prop))
        return tuple(documents)

    def add_auxiliary(self, document: PsseAuxiliaryDocument) -> bool:
        """Own a parsed document after checking its selected major revision.

        Invalid records remain available for inspection with their diagnostics.
        No file defaults, contingencies or electrical values are applied to RAW.

        :param document: Concrete versioned auxiliary data.
        :return: Whether the document was accepted into its circuit collection.
        """
        version: PsseVersion | None = resolve_psse_version(self.REV, self.auxiliary_logger, 'PsseCircuit.REV')
        if version is None or document.version is None or document.version != version:
            self.auxiliary_logger.add_error('Auxiliary document version does not match circuit REV',
                                            device=document.source, value=document.version,
                                            expected_value=self.REV)
            return False
        elif any(owned is document for owned in self.get_auxiliary_documents()):
            self.auxiliary_logger.add_error('Auxiliary document already belongs to this circuit',
                                            device=document.source)
            return False
        else:
            pass
        # Dispatch explicitly: callers keep the concrete version type and every record.
        if isinstance(document, RawSub):
            self.sub_files.append(document)
            self.auxiliary_bus_mode = document.bus_mode
        elif isinstance(document, RawMon):
            self.mon_files.append(document)
            self.auxiliary_bus_mode = document.bus_mode
        elif isinstance(document, RawCon):
            self.con_files.append(document)
            self.auxiliary_bus_mode = document.bus_mode
        elif isinstance(document, RawDyr):
            self.dyr_files.append(document)
        elif isinstance(document, RawSeq):
            self.seq_files.append(document)
        elif isinstance(document, RawRop):
            self.rop_files.append(document)
        elif isinstance(document, RawGcp):
            self.gcp_files.append(document)
        elif isinstance(document, RawLoc):
            self.loc_files.append(document)
        else:
            self.auxiliary_logger.add_error('Unsupported auxiliary document type')
            return False
        if document.logger is not self.auxiliary_logger:
            self.auxiliary_logger += document.logger
        else:
            pass
        return True

    def read_auxiliary_file(self, file_name: str | Path,
                            bus_mode: BusInputMode | None = None,
                            layout_35: Sequence35Layout = Sequence35Layout.V35_2) -> PsseAuxiliaryDocument | None:
        """Read and own one auxiliary file using circuit REV, never RawObject.version.

        Call in source order: SUB/MON/CON inherit the preceding bus-name mode.
        Explicitly supplying bus_mode starts a new command-file interpretation.

        :param file_name: SUB, MON, CON, DYR, SEQ, ROP, GCP or LOC input path.
        :param bus_mode: Optional initial bus-reference mode override.
        :param layout_35: Explicit SEQ minor-release layout when REV is 35.
        :return: Owned parsed document, or None after a load/version failure.
        """
        path: Path = Path(file_name)
        version: PsseVersion | None = resolve_psse_version(self.REV, self.auxiliary_logger, str(path))
        if version is None:
            return None
        else:
            pass
        file_type: PsseFileType
        try:
            file_type = PsseFileType(path.suffix.lower())
        except ValueError:
            self.auxiliary_logger.add_error('Unsupported PSS/E auxiliary file extension', device=str(path))
            return None
        mode: BusInputMode = self.auxiliary_bus_mode if bus_mode is None else bus_mode
        document: PsseAuxiliaryDocument
        try:
            if file_type == PsseFileType.SUB:
                document = read_sub(path, mode, version)
            elif file_type == PsseFileType.MON:
                document = read_mon(path, mode, version)
            elif file_type == PsseFileType.CON:
                document = read_con(path, mode, version)
            elif file_type == PsseFileType.DYR:
                document = read_dyr(path, version)
            elif file_type == PsseFileType.SEQ:
                document = read_seq(path, version, layout_35)
            elif file_type == PsseFileType.ROP:
                document = read_rop(path, version)
            elif file_type == PsseFileType.GCP:
                document = read_gcp(path, version)
            elif file_type == PsseFileType.LOC:
                document = read_loc(path, version)
            else:
                self.auxiliary_logger.add_error('RAW is not an auxiliary file', device=str(path))
                return None
        except (OSError, UnicodeError) as error:
            self.auxiliary_logger.add_error('Could not read PSS/E auxiliary file', device=str(path), value=str(error))
            return None
        if self.add_auxiliary(document):
            return document
        else:
            return None

    def warn_auxiliary_omission(self, logger: Logger) -> None:
        """Report auxiliary data excluded by a network-only RAW/RAWX export.

        :param logger: Export diagnostics destination.
        """
        for document in self.get_auxiliary_documents():
            logger.add_warning('RAW/RAWX output does not contain auxiliary files', device=document.source)

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
        elif len(data) == 2:
            self.IC, self.SBASE = data
            self.REV = 25
            logger.add_warning("RAW header contains elements instead of the expected 6")
        else:
            logger.add_warning(f"RAW header contains {len(data)} elements instead of the expected 6")

    def get_class_properties(self) -> List[PsseProperty]:
        """Get RAW network collections used by existing object tools.

        :return: Network object descriptors, excluding scalars and auxiliary documents.
        """
        return [p for p in self.get_rawx_properties() if p.class_type not in [str, bool, int, float]]

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
                    logger.add_info(msg="Global UUID5 duplicate", device=id_,
                                    device_class=prop.rawx_key, value=uuid_,
                                    comment="Found {}:{}".format(found_elm.class_name, found_elm.get_id()))
                else:
                    global_index[uuid_] = elm
