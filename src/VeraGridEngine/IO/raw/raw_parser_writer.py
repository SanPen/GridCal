# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import re
import datetime
from pathlib import Path
from typing import List, AnyStr, Dict, Sequence, Callable

from VeraGridEngine.IO.raw.raw_writer_comment_map import comment_version_map
from VeraGridEngine.Utils.charatcter_detection import detect_character_encoding
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.psse_auxiliary import BusInputMode
from VeraGridEngine.IO.raw.versioned.base.seq import Sequence35Layout
from VeraGridEngine.IO.raw.versioned.v29.area import RawAreaV29
from VeraGridEngine.IO.raw.versioned.v29.zone import RawZoneV29
from VeraGridEngine.IO.raw.versioned.v29.bus import RawBusV29
from VeraGridEngine.IO.raw.versioned.v29.load import RawLoadV29
from VeraGridEngine.IO.raw.versioned.v29.fixed_shunt import RawFixedShuntV29
from VeraGridEngine.IO.raw.versioned.v29.switched_shunt import RawSwitchedShuntV29
from VeraGridEngine.IO.raw.versioned.v29.generator import RawGeneratorV29
from VeraGridEngine.IO.raw.versioned.v29.branch import RawBranchV29
from VeraGridEngine.IO.raw.versioned.v29.transformer import RawTransformerV29
from VeraGridEngine.IO.raw.versioned.v29.two_terminal_dc_line import RawTwoTerminalDCLineV29
from VeraGridEngine.IO.raw.versioned.v29.vsc_dc_line import RawVscDCLineV29
from VeraGridEngine.IO.raw.versioned.v29.facts import RawFACTSV29
from VeraGridEngine.IO.raw.versioned.v29.system_switching_device import RawSystemSwitchingDeviceV29
from VeraGridEngine.IO.raw.versioned.v29.induction_machine import RawInductionMachineV29
from VeraGridEngine.IO.raw.versioned.v29.owner import RawOwnerV29
from VeraGridEngine.IO.raw.versioned.v29.inter_area import RawInterAreaV29
from VeraGridEngine.IO.raw.versioned.v29.multi_section_line import RawMultiLineSectionV29
from VeraGridEngine.IO.raw.versioned.v29.impedance_correction_table import RawImpedanceCorrectionTableV29
from VeraGridEngine.IO.raw.versioned.v29.substation import RawSubstationV29
from VeraGridEngine.IO.raw.versioned.v29.node import RawNodeV29
from VeraGridEngine.IO.raw.versioned.v29.gne_device import RawGneDeviceV29
from VeraGridEngine.IO.raw.versioned.v30.area import RawAreaV30
from VeraGridEngine.IO.raw.versioned.v30.zone import RawZoneV30
from VeraGridEngine.IO.raw.versioned.v30.bus import RawBusV30
from VeraGridEngine.IO.raw.versioned.v30.load import RawLoadV30
from VeraGridEngine.IO.raw.versioned.v30.fixed_shunt import RawFixedShuntV30
from VeraGridEngine.IO.raw.versioned.v30.switched_shunt import RawSwitchedShuntV30
from VeraGridEngine.IO.raw.versioned.v30.generator import RawGeneratorV30
from VeraGridEngine.IO.raw.versioned.v30.branch import RawBranchV30
from VeraGridEngine.IO.raw.versioned.v30.transformer import RawTransformerV30
from VeraGridEngine.IO.raw.versioned.v30.two_terminal_dc_line import RawTwoTerminalDCLineV30
from VeraGridEngine.IO.raw.versioned.v30.vsc_dc_line import RawVscDCLineV30
from VeraGridEngine.IO.raw.versioned.v30.facts import RawFACTSV30
from VeraGridEngine.IO.raw.versioned.v30.system_switching_device import RawSystemSwitchingDeviceV30
from VeraGridEngine.IO.raw.versioned.v30.induction_machine import RawInductionMachineV30
from VeraGridEngine.IO.raw.versioned.v30.owner import RawOwnerV30
from VeraGridEngine.IO.raw.versioned.v30.inter_area import RawInterAreaV30
from VeraGridEngine.IO.raw.versioned.v30.multi_section_line import RawMultiLineSectionV30
from VeraGridEngine.IO.raw.versioned.v30.impedance_correction_table import RawImpedanceCorrectionTableV30
from VeraGridEngine.IO.raw.versioned.v30.substation import RawSubstationV30
from VeraGridEngine.IO.raw.versioned.v30.node import RawNodeV30
from VeraGridEngine.IO.raw.versioned.v30.gne_device import RawGneDeviceV30
from VeraGridEngine.IO.raw.versioned.v31.area import RawAreaV31
from VeraGridEngine.IO.raw.versioned.v31.zone import RawZoneV31
from VeraGridEngine.IO.raw.versioned.v31.bus import RawBusV31
from VeraGridEngine.IO.raw.versioned.v31.load import RawLoadV31
from VeraGridEngine.IO.raw.versioned.v31.fixed_shunt import RawFixedShuntV31
from VeraGridEngine.IO.raw.versioned.v31.switched_shunt import RawSwitchedShuntV31
from VeraGridEngine.IO.raw.versioned.v31.generator import RawGeneratorV31
from VeraGridEngine.IO.raw.versioned.v31.branch import RawBranchV31
from VeraGridEngine.IO.raw.versioned.v31.transformer import RawTransformerV31
from VeraGridEngine.IO.raw.versioned.v31.two_terminal_dc_line import RawTwoTerminalDCLineV31
from VeraGridEngine.IO.raw.versioned.v31.vsc_dc_line import RawVscDCLineV31
from VeraGridEngine.IO.raw.versioned.v31.facts import RawFACTSV31
from VeraGridEngine.IO.raw.versioned.v31.system_switching_device import RawSystemSwitchingDeviceV31
from VeraGridEngine.IO.raw.versioned.v31.induction_machine import RawInductionMachineV31
from VeraGridEngine.IO.raw.versioned.v31.owner import RawOwnerV31
from VeraGridEngine.IO.raw.versioned.v31.inter_area import RawInterAreaV31
from VeraGridEngine.IO.raw.versioned.v31.multi_section_line import RawMultiLineSectionV31
from VeraGridEngine.IO.raw.versioned.v31.impedance_correction_table import RawImpedanceCorrectionTableV31
from VeraGridEngine.IO.raw.versioned.v31.substation import RawSubstationV31
from VeraGridEngine.IO.raw.versioned.v31.node import RawNodeV31
from VeraGridEngine.IO.raw.versioned.v31.gne_device import RawGneDeviceV31
from VeraGridEngine.IO.raw.versioned.v32.area import RawAreaV32
from VeraGridEngine.IO.raw.versioned.v32.zone import RawZoneV32
from VeraGridEngine.IO.raw.versioned.v32.bus import RawBusV32
from VeraGridEngine.IO.raw.versioned.v32.load import RawLoadV32
from VeraGridEngine.IO.raw.versioned.v32.fixed_shunt import RawFixedShuntV32
from VeraGridEngine.IO.raw.versioned.v32.switched_shunt import RawSwitchedShuntV32
from VeraGridEngine.IO.raw.versioned.v32.generator import RawGeneratorV32
from VeraGridEngine.IO.raw.versioned.v32.branch import RawBranchV32
from VeraGridEngine.IO.raw.versioned.v32.transformer import RawTransformerV32
from VeraGridEngine.IO.raw.versioned.v32.two_terminal_dc_line import RawTwoTerminalDCLineV32
from VeraGridEngine.IO.raw.versioned.v32.vsc_dc_line import RawVscDCLineV32
from VeraGridEngine.IO.raw.versioned.v32.facts import RawFACTSV32
from VeraGridEngine.IO.raw.versioned.v32.system_switching_device import RawSystemSwitchingDeviceV32
from VeraGridEngine.IO.raw.versioned.v32.induction_machine import RawInductionMachineV32
from VeraGridEngine.IO.raw.versioned.v32.owner import RawOwnerV32
from VeraGridEngine.IO.raw.versioned.v32.inter_area import RawInterAreaV32
from VeraGridEngine.IO.raw.versioned.v32.multi_section_line import RawMultiLineSectionV32
from VeraGridEngine.IO.raw.versioned.v32.impedance_correction_table import RawImpedanceCorrectionTableV32
from VeraGridEngine.IO.raw.versioned.v32.substation import RawSubstationV32
from VeraGridEngine.IO.raw.versioned.v32.node import RawNodeV32
from VeraGridEngine.IO.raw.versioned.v32.gne_device import RawGneDeviceV32
from VeraGridEngine.IO.raw.versioned.v33.area import RawAreaV33
from VeraGridEngine.IO.raw.versioned.v33.zone import RawZoneV33
from VeraGridEngine.IO.raw.versioned.v33.bus import RawBusV33
from VeraGridEngine.IO.raw.versioned.v33.load import RawLoadV33
from VeraGridEngine.IO.raw.versioned.v33.fixed_shunt import RawFixedShuntV33
from VeraGridEngine.IO.raw.versioned.v33.switched_shunt import RawSwitchedShuntV33
from VeraGridEngine.IO.raw.versioned.v33.generator import RawGeneratorV33
from VeraGridEngine.IO.raw.versioned.v33.branch import RawBranchV33
from VeraGridEngine.IO.raw.versioned.v33.transformer import RawTransformerV33
from VeraGridEngine.IO.raw.versioned.v33.two_terminal_dc_line import RawTwoTerminalDCLineV33
from VeraGridEngine.IO.raw.versioned.v33.vsc_dc_line import RawVscDCLineV33
from VeraGridEngine.IO.raw.versioned.v33.facts import RawFACTSV33
from VeraGridEngine.IO.raw.versioned.v33.system_switching_device import RawSystemSwitchingDeviceV33
from VeraGridEngine.IO.raw.versioned.v33.induction_machine import RawInductionMachineV33
from VeraGridEngine.IO.raw.versioned.v33.owner import RawOwnerV33
from VeraGridEngine.IO.raw.versioned.v33.inter_area import RawInterAreaV33
from VeraGridEngine.IO.raw.versioned.v33.multi_section_line import RawMultiLineSectionV33
from VeraGridEngine.IO.raw.versioned.v33.impedance_correction_table import RawImpedanceCorrectionTableV33
from VeraGridEngine.IO.raw.versioned.v33.substation import RawSubstationV33
from VeraGridEngine.IO.raw.versioned.v33.node import RawNodeV33
from VeraGridEngine.IO.raw.versioned.v33.gne_device import RawGneDeviceV33
from VeraGridEngine.IO.raw.versioned.v34.area import RawAreaV34
from VeraGridEngine.IO.raw.versioned.v34.zone import RawZoneV34
from VeraGridEngine.IO.raw.versioned.v34.bus import RawBusV34
from VeraGridEngine.IO.raw.versioned.v34.load import RawLoadV34
from VeraGridEngine.IO.raw.versioned.v34.fixed_shunt import RawFixedShuntV34
from VeraGridEngine.IO.raw.versioned.v34.switched_shunt import RawSwitchedShuntV34
from VeraGridEngine.IO.raw.versioned.v34.generator import RawGeneratorV34
from VeraGridEngine.IO.raw.versioned.v34.branch import RawBranchV34
from VeraGridEngine.IO.raw.versioned.v34.transformer import RawTransformerV34
from VeraGridEngine.IO.raw.versioned.v34.two_terminal_dc_line import RawTwoTerminalDCLineV34
from VeraGridEngine.IO.raw.versioned.v34.vsc_dc_line import RawVscDCLineV34
from VeraGridEngine.IO.raw.versioned.v34.facts import RawFACTSV34
from VeraGridEngine.IO.raw.versioned.v34.system_switching_device import RawSystemSwitchingDeviceV34
from VeraGridEngine.IO.raw.versioned.v34.induction_machine import RawInductionMachineV34
from VeraGridEngine.IO.raw.versioned.v34.owner import RawOwnerV34
from VeraGridEngine.IO.raw.versioned.v34.inter_area import RawInterAreaV34
from VeraGridEngine.IO.raw.versioned.v34.multi_section_line import RawMultiLineSectionV34
from VeraGridEngine.IO.raw.versioned.v34.impedance_correction_table import RawImpedanceCorrectionTableV34
from VeraGridEngine.IO.raw.versioned.v34.substation import RawSubstationV34
from VeraGridEngine.IO.raw.versioned.v34.node import RawNodeV34
from VeraGridEngine.IO.raw.versioned.v34.substation_switching_device import RawSubstationSwitchingDeviceV34
from VeraGridEngine.IO.raw.versioned.v34.equipment_terminal import RawEquipmentTerminalV34
from VeraGridEngine.IO.raw.versioned.v34.gne_device import RawGneDeviceV34
from VeraGridEngine.IO.raw.versioned.v35.area import RawAreaV35
from VeraGridEngine.IO.raw.versioned.v35.zone import RawZoneV35
from VeraGridEngine.IO.raw.versioned.v35.bus import RawBusV35
from VeraGridEngine.IO.raw.versioned.v35.load import RawLoadV35
from VeraGridEngine.IO.raw.versioned.v35.fixed_shunt import RawFixedShuntV35
from VeraGridEngine.IO.raw.versioned.v35.switched_shunt import RawSwitchedShuntV35
from VeraGridEngine.IO.raw.versioned.v35.generator import RawGeneratorV35
from VeraGridEngine.IO.raw.versioned.v35.branch import RawBranchV35
from VeraGridEngine.IO.raw.versioned.v35.transformer import RawTransformerV35
from VeraGridEngine.IO.raw.versioned.v35.two_terminal_dc_line import RawTwoTerminalDCLineV35
from VeraGridEngine.IO.raw.versioned.v35.vsc_dc_line import RawVscDCLineV35
from VeraGridEngine.IO.raw.versioned.v35.facts import RawFACTSV35
from VeraGridEngine.IO.raw.versioned.v35.system_switching_device import RawSystemSwitchingDeviceV35
from VeraGridEngine.IO.raw.versioned.v35.induction_machine import RawInductionMachineV35
from VeraGridEngine.IO.raw.versioned.v35.owner import RawOwnerV35
from VeraGridEngine.IO.raw.versioned.v35.inter_area import RawInterAreaV35
from VeraGridEngine.IO.raw.versioned.v35.multi_section_line import RawMultiLineSectionV35
from VeraGridEngine.IO.raw.versioned.v35.impedance_correction_table import RawImpedanceCorrectionTableV35
from VeraGridEngine.IO.raw.versioned.v35.substation import RawSubstationV35
from VeraGridEngine.IO.raw.versioned.v35.node import RawNodeV35
from VeraGridEngine.IO.raw.versioned.v35.substation_switching_device import RawSubstationSwitchingDeviceV35
from VeraGridEngine.IO.raw.versioned.v35.equipment_terminal import RawEquipmentTerminalV35
from VeraGridEngine.IO.raw.versioned.v35.gne_device import RawGneDeviceV35
from VeraGridEngine.IO.raw.versioned.v36.area import RawAreaV36
from VeraGridEngine.IO.raw.versioned.v36.zone import RawZoneV36
from VeraGridEngine.IO.raw.versioned.v36.bus import RawBusV36
from VeraGridEngine.IO.raw.versioned.v36.load import RawLoadV36
from VeraGridEngine.IO.raw.versioned.v36.fixed_shunt import RawFixedShuntV36
from VeraGridEngine.IO.raw.versioned.v36.switched_shunt import RawSwitchedShuntV36
from VeraGridEngine.IO.raw.versioned.v36.generator import RawGeneratorV36
from VeraGridEngine.IO.raw.versioned.v36.branch import RawBranchV36
from VeraGridEngine.IO.raw.versioned.v36.transformer import RawTransformerV36
from VeraGridEngine.IO.raw.versioned.v36.two_terminal_dc_line import RawTwoTerminalDCLineV36
from VeraGridEngine.IO.raw.versioned.v36.vsc_dc_line import RawVscDCLineV36
from VeraGridEngine.IO.raw.versioned.v36.facts import RawFACTSV36
from VeraGridEngine.IO.raw.versioned.v36.system_switching_device import RawSystemSwitchingDeviceV36
from VeraGridEngine.IO.raw.versioned.v36.induction_machine import RawInductionMachineV36
from VeraGridEngine.IO.raw.versioned.v36.owner import RawOwnerV36
from VeraGridEngine.IO.raw.versioned.v36.inter_area import RawInterAreaV36
from VeraGridEngine.IO.raw.versioned.v36.multi_section_line import RawMultiLineSectionV36
from VeraGridEngine.IO.raw.versioned.v36.impedance_correction_table import RawImpedanceCorrectionTableV36
from VeraGridEngine.IO.raw.versioned.v36.substation import RawSubstationV36
from VeraGridEngine.IO.raw.versioned.v36.node import RawNodeV36
from VeraGridEngine.IO.raw.versioned.v36.substation_switching_device import RawSubstationSwitchingDeviceV36
from VeraGridEngine.IO.raw.versioned.v36.equipment_terminal import RawEquipmentTerminalV36
from VeraGridEngine.IO.raw.versioned.v36.gne_device import RawGneDeviceV36

SYSTEM_WIDE_SECTION_KEYS: set[str] = {
    "GENERAL",
    "GAUSS",
    "NEWTON",
    "ADJUST",
    "TYSL",
    "SOLVER",
    "RATING",
}

KNOWN_CONTINUATION_HEADER_KEYS: set[str] = {"VSREG"}


def normalize_psse_version(version: int) -> int:
    """
    Normalize a RAW version to the supported range.

    :param version: Requested or detected PSSE version.
    :return: Supported PSSE version.
    """
    normalized_version: int = version

    if version > 36:
        normalized_version = 36
    elif version < 29:
        normalized_version = 33
    else:
        normalized_version = version

    return normalized_version


def delete_comment(raw_line):
    """

    :param raw_line:
    :return:
    """
    lne = ""
    text_active = False
    for c in raw_line:

        if c == "'":
            text_active = not text_active

        if c == "/":
            if text_active:
                pass
            else:
                return lne

        lne += c

    return lne


def interpret_line(raw_line: str, splitter=','):
    """
    Split text into arguments and parse each of them to an appropriate format (int, float or string)
    Args:
        raw_line: text line
        splitter: value to split by
    Returns: list of arguments
    """
    raw_line = delete_comment(raw_line)

    # Remove the last useless comma if it is there:
    if raw_line[-1] == ",":
        lne = raw_line[:-1]
    else:
        lne = raw_line

    parsed = list()

    # Regular expression to split on commas but ignore commas within single quotes
    pattern = splitter + r"\s*(?=(?:[^']*'[^']*')*[^']*$)"

    # Use re.split to apply the pattern
    if ',' in lne:
        elms = re.split(pattern, lne)
    else:
        elms = lne.split()

    for elm in elms:

        if "'" in elm:
            el = elm.replace("'", "").strip()
        else:

            if "/" in elm:
                # the line might end with a comment "/ whatever" so we must delete the comment
                print("Comment detected:", elm, end="")
                ss = elm.split("/")
                elm = ss[0]
                print(" corrected to:", elm)

            try:
                # try int
                el = int(elm)
            except ValueError as ex1:
                try:
                    # try float
                    el = float(elm)
                except ValueError as ex2:
                    # otherwise just leave it as string
                    el = elm.strip()
        parsed.append(el)

    return parsed


def read_and_split(file_name: str, text_func=None, progress_func=None) -> (List[AnyStr], Dict[AnyStr, AnyStr]):
    """
    Read the text file and split it into sections
    :return: list of sections, dictionary of sections by type
    """

    if text_func is not None:
        text_func("Detecting raw file encoding...")

    if progress_func is not None:
        progress_func(0)

    detected_encoding: str = detect_character_encoding(source=file_name)

    # open the text file into a variable

    if text_func is not None:
        text_func("Reading raw file...")

    sections_dict: Dict[str, List[List[str | float | int] | str]] = dict()
    sections_dict["bus"] = list()
    sep = ","
    # Reuse the shared detector so the guessed encoding is validated before the
    # parser starts iterating through the RAW records.
    with open(file_name, 'r', encoding=detected_encoding) as my_file:
        i = 0
        block_category = "bus"
        for line_ in my_file:

            if line_[0] != '@':
                # delete garbage
                lne: str = str(line_).strip()

                if lne.startswith("program"):
                    # common header
                    block_category = 'program'
                    sections_dict[block_category] = list()

                if i == 0:
                    sections_dict['info'] = [interpret_line(raw_line=lne, splitter=sep)]
                elif i == 1:
                    sections_dict['comment'] = [lne]
                elif i == 2:
                    sections_dict['comment2'] = [lne]
                else:
                    record_key: str = lne.split(",", 1)[0].strip().upper()

                    if record_key in SYSTEM_WIDE_SECTION_KEYS:
                        block_category = "system-wide"
                        if block_category not in sections_dict:
                            sections_dict[block_category] = list()

                    if record_key in KNOWN_CONTINUATION_HEADER_KEYS:
                        i += 1
                        continue

                    if lne.startswith("0 /"):
                        # this is a category splitter
                        if lne.startswith("cards"):
                            # MISO file
                            pass
                        else:
                            # common header
                            s = lne.lower().split(", begin")
                            if len(s) == 2:
                                block_category = s[1].replace("begin", "").replace("data", "").strip()
                                sections_dict[block_category] = list()

                    elif lne.startswith("Q"):
                        pass
                    else:
                        if lne.strip() != '':
                            sections_dict[block_category].append(
                                interpret_line(raw_line=lne, splitter=sep)
                            )

                i += 1
            else:
                # it is a header
                hdr = line_.strip()
                pass

    return sections_dict


def is_3w(row, bus_set):
    """
    If this a 3W transformer?
    :param row: transformer file row
    :param bus_set: Set of raw bus information
    :return:
    """
    return row[0] in bus_set and row[1] in bus_set and row[2] in bus_set


def is_one_line_for_induction_machine(row):
    """
    Is this a one line induction machine?
    :param row: file row
    :return:
    """
    return len(row) != 12


def check_end_of_impedance_table(row: List[int | float | str]) -> bool:
    """
    Check the insane impedance line termination criteria
    :param row:
    :return:
    """
    n = len(row)
    if n < 3:
        return False

    if row[n - 1] == 0 and row[n - 2] == 0 and row[n - 3] == 0:
        return True
    else:
        return False


def is_valid(value: float | int | str):
    return value is not None and isinstance(value, (int, float, str))


def format_lines(data1: List[List[float | int | str]], logger: Logger) -> List[List[float | int | str]]:
    """
    Format PSSe lines
    :param data1:
    :param logger:
    :return:
    """
    data = list()
    for lst in data1:
        sublist = list()
        for val in lst:
            if is_valid(val):
                sublist.append(val)
            else:
                sublist.append(0)
                logger.add_error("Invalid PSSe value", value=val)
        data.append(sublist)

    return data


def parse_substation_data_group(
        lines: List[List[float | int | str]],
        version: int,
        logger: Logger,
        grid: PsseCircuit,
        raw_substation_t,
        raw_node_t,
        raw_substation_switching_device_t,
        raw_equipment_terminal_t) -> None:
    """
    Parse the nested PSSE 34+ substation data group.

    The RAW substation section is not a flat list of homogeneous records. Each
    substation block contains one substation record, a node list terminated by
    zero, a station-switch list terminated by zero, and an equipment-terminal
    list terminated by zero.

    :param lines: Flat list of already tokenized RAW records from the section.
    :param version: PSSE version.
    :param logger: Logger instance.
    :param grid: Destination PSSE circuit.
    :param raw_substation_t: Version-specific substation class.
    :param raw_node_t: Version-specific node class.
    :param raw_substation_switching_device_t: Version-specific station-switch class.
    :param raw_equipment_terminal_t: Version-specific terminal class.
    :return: None
    """
    cursor: int = 0
    total_lines: int = len(lines)

    # Consume one nested block at a time. The outer zero record terminates the
    # whole section, while the inner zero records terminate the node, switch,
    # and terminal subsections of the current substation.
    while cursor < total_lines:
        substation_record: List[float | int | str] = lines[cursor]
        if len(substation_record) == 0:
            cursor += 1
        elif substation_record[0] == 0:
            break
        else:
            substation = raw_substation_t()
            substation.parse([substation_record], version, logger)
            grid.substations.append(substation)
            cursor += 1

            while cursor < total_lines:
                node_record: List[float | int | str] = lines[cursor]
                if len(node_record) == 0:
                    cursor += 1
                elif node_record[0] == 0:
                    cursor += 1
                    break
                else:
                    node = raw_node_t()
                    node.ISUB = substation.IS
                    node.parse([node_record], version, logger)
                    grid.nodes.append(node)
                    cursor += 1

            while cursor < total_lines:
                switch_record: List[float | int | str] = lines[cursor]
                if len(switch_record) == 0:
                    cursor += 1
                elif switch_record[0] == 0:
                    cursor += 1
                    break
                else:
                    switch = raw_substation_switching_device_t()
                    switch.ISUB = substation.IS
                    switch.parse([switch_record], version, logger)
                    grid.substation_switching_devices.append(switch)
                    cursor += 1

            while cursor < total_lines:
                terminal_record: List[float | int | str] = lines[cursor]
                if len(terminal_record) == 0:
                    cursor += 1
                elif terminal_record[0] == 0:
                    cursor += 1
                    break
                else:
                    terminal = raw_equipment_terminal_t()
                    terminal.ISUB = substation.IS
                    terminal.parse([terminal_record], version, logger)
                    grid.equipment_terminals.append(terminal)
                    cursor += 1

    if cursor == total_lines and total_lines > 0 and len(lines[-1]) > 0 and lines[-1][0] != 0:
        logger.add_warning(
            'Substation data group terminated without the expected zero record',
            value=str(version)
        )


def read_raw(filename: str | Path,
             text_func: Callable[[str], None] | None = None,
             progress_func: Callable[[float], None] | None = None,
             logger: Logger = Logger(),
             auxiliary_files: Sequence[str | Path] | None = None,
             layout_35: Sequence35Layout = Sequence35Layout.V35_2,
             bus_mode: BusInputMode = BusInputMode.NUMBERS) -> PsseCircuit:
    """

    :param filename:
    :param text_func:
    :param progress_func:
    :param logger:
    :param auxiliary_files: Explicitly selected auxiliary paths, read in supplied order after RAW.
    :param layout_35: SEQ 35.0/35.1 versus 35.2 layout; applies only to circuit REV 35.
    :param bus_mode: Initial bus-reference mode for the ordered auxiliary inputs.
    :return:
    """
    """
    Parser implemented according to:
        - POM section 4.1.1 Power Flow Raw Data File Contents (v.29)
        - POM section 5.2.1                                   (v.33)
        - POM section 5.2.1                                   (v.32)

    Returns: MultiCircuit, List[str]
    """

    versions = [36, 35, 34, 33, 32, 31, 30, 29]

    if text_func is not None:
        text_func("Reading file...")

    sections_dict = read_and_split(file_name=filename,
                                   text_func=text_func,
                                   progress_func=progress_func)

    # header -> new grid
    # grid = PSSeGrid(interpret_line(sections[0]))
    grid = PsseCircuit()
    grid.parse(sections_dict['info'][0], logger=logger)

    if grid.REV not in versions:
        msg = 'The PSSe version is not compatible. Compatible versions are:'
        msg += ', '.join([str(a) for a in versions])
        logger.add_error(msg)
        return grid
    else:
        version = normalize_psse_version(grid.REV)

    if version == 29:
        RawAreaT = RawAreaV29
        RawZoneT = RawZoneV29
        RawBusT = RawBusV29
        RawLoadT = RawLoadV29
        RawFixedShuntT = RawFixedShuntV29
        RawSwitchedShuntT = RawSwitchedShuntV29
        RawGeneratorT = RawGeneratorV29
        RawBranchT = RawBranchV29
        RawTransformerT = RawTransformerV29
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV29
        RawVscDCLineT = RawVscDCLineV29
        RawFACTST = RawFACTSV29
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV29
        RawInductionMachineT = RawInductionMachineV29
        RawOwnerT = RawOwnerV29
        RawInterAreaT = RawInterAreaV29
        RawMultiLineSectionT = RawMultiLineSectionV29
        RawImpedanceCorrectionTableT = RawImpedanceCorrectionTableV29
        RawSubstationT = RawSubstationV29
        RawNodeT = RawNodeV29
        RawSubstationSwitchingDeviceT = None
        RawEquipmentTerminalT = None
        RawGneDeviceT = RawGneDeviceV29
    elif version == 30:
        RawAreaT = RawAreaV30
        RawZoneT = RawZoneV30
        RawBusT = RawBusV30
        RawLoadT = RawLoadV30
        RawFixedShuntT = RawFixedShuntV30
        RawSwitchedShuntT = RawSwitchedShuntV30
        RawGeneratorT = RawGeneratorV30
        RawBranchT = RawBranchV30
        RawTransformerT = RawTransformerV30
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV30
        RawVscDCLineT = RawVscDCLineV30
        RawFACTST = RawFACTSV30
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV30
        RawInductionMachineT = RawInductionMachineV30
        RawOwnerT = RawOwnerV30
        RawInterAreaT = RawInterAreaV30
        RawMultiLineSectionT = RawMultiLineSectionV30
        RawImpedanceCorrectionTableT = RawImpedanceCorrectionTableV30
        RawSubstationT = RawSubstationV30
        RawNodeT = RawNodeV30
        RawSubstationSwitchingDeviceT = None
        RawEquipmentTerminalT = None
        RawGneDeviceT = RawGneDeviceV30
    elif version == 31:
        RawAreaT = RawAreaV31
        RawZoneT = RawZoneV31
        RawBusT = RawBusV31
        RawLoadT = RawLoadV31
        RawFixedShuntT = RawFixedShuntV31
        RawSwitchedShuntT = RawSwitchedShuntV31
        RawGeneratorT = RawGeneratorV31
        RawBranchT = RawBranchV31
        RawTransformerT = RawTransformerV31
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV31
        RawVscDCLineT = RawVscDCLineV31
        RawFACTST = RawFACTSV31
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV31
        RawInductionMachineT = RawInductionMachineV31
        RawOwnerT = RawOwnerV31
        RawInterAreaT = RawInterAreaV31
        RawMultiLineSectionT = RawMultiLineSectionV31
        RawImpedanceCorrectionTableT = RawImpedanceCorrectionTableV31
        RawSubstationT = RawSubstationV31
        RawNodeT = RawNodeV31
        RawSubstationSwitchingDeviceT = None
        RawEquipmentTerminalT = None
        RawGneDeviceT = RawGneDeviceV31
    elif version == 32:
        RawAreaT = RawAreaV32
        RawZoneT = RawZoneV32
        RawBusT = RawBusV32
        RawLoadT = RawLoadV32
        RawFixedShuntT = RawFixedShuntV32
        RawSwitchedShuntT = RawSwitchedShuntV32
        RawGeneratorT = RawGeneratorV32
        RawBranchT = RawBranchV32
        RawTransformerT = RawTransformerV32
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV32
        RawVscDCLineT = RawVscDCLineV32
        RawFACTST = RawFACTSV32
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV32
        RawInductionMachineT = RawInductionMachineV32
        RawOwnerT = RawOwnerV32
        RawInterAreaT = RawInterAreaV32
        RawMultiLineSectionT = RawMultiLineSectionV32
        RawImpedanceCorrectionTableT = RawImpedanceCorrectionTableV32
        RawSubstationT = RawSubstationV32
        RawNodeT = RawNodeV32
        RawSubstationSwitchingDeviceT = None
        RawEquipmentTerminalT = None
        RawGneDeviceT = RawGneDeviceV32
    elif version == 33:
        RawAreaT = RawAreaV33
        RawZoneT = RawZoneV33
        RawBusT = RawBusV33
        RawLoadT = RawLoadV33
        RawFixedShuntT = RawFixedShuntV33
        RawSwitchedShuntT = RawSwitchedShuntV33
        RawGeneratorT = RawGeneratorV33
        RawBranchT = RawBranchV33
        RawTransformerT = RawTransformerV33
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV33
        RawVscDCLineT = RawVscDCLineV33
        RawFACTST = RawFACTSV33
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV33
        RawInductionMachineT = RawInductionMachineV33
        RawOwnerT = RawOwnerV33
        RawInterAreaT = RawInterAreaV33
        RawMultiLineSectionT = RawMultiLineSectionV33
        RawImpedanceCorrectionTableT = RawImpedanceCorrectionTableV33
        RawSubstationT = RawSubstationV33
        RawNodeT = RawNodeV33
        RawSubstationSwitchingDeviceT = None
        RawEquipmentTerminalT = None
        RawGneDeviceT = RawGneDeviceV33
    elif version == 34:
        RawAreaT = RawAreaV34
        RawZoneT = RawZoneV34
        RawBusT = RawBusV34
        RawLoadT = RawLoadV34
        RawFixedShuntT = RawFixedShuntV34
        RawSwitchedShuntT = RawSwitchedShuntV34
        RawGeneratorT = RawGeneratorV34
        RawBranchT = RawBranchV34
        RawTransformerT = RawTransformerV34
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV34
        RawVscDCLineT = RawVscDCLineV34
        RawFACTST = RawFACTSV34
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV34
        RawInductionMachineT = RawInductionMachineV34
        RawOwnerT = RawOwnerV34
        RawInterAreaT = RawInterAreaV34
        RawMultiLineSectionT = RawMultiLineSectionV34
        RawImpedanceCorrectionTableT = RawImpedanceCorrectionTableV34
        RawSubstationT = RawSubstationV34
        RawNodeT = RawNodeV34
        RawSubstationSwitchingDeviceT = RawSubstationSwitchingDeviceV34
        RawEquipmentTerminalT = RawEquipmentTerminalV34
        RawGneDeviceT = RawGneDeviceV34
    elif version == 35:
        RawAreaT = RawAreaV35
        RawZoneT = RawZoneV35
        RawBusT = RawBusV35
        RawLoadT = RawLoadV35
        RawFixedShuntT = RawFixedShuntV35
        RawSwitchedShuntT = RawSwitchedShuntV35
        RawGeneratorT = RawGeneratorV35
        RawBranchT = RawBranchV35
        RawTransformerT = RawTransformerV35
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV35
        RawVscDCLineT = RawVscDCLineV35
        RawFACTST = RawFACTSV35
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV35
        RawInductionMachineT = RawInductionMachineV35
        RawOwnerT = RawOwnerV35
        RawInterAreaT = RawInterAreaV35
        RawMultiLineSectionT = RawMultiLineSectionV35
        RawImpedanceCorrectionTableT = RawImpedanceCorrectionTableV35
        RawSubstationT = RawSubstationV35
        RawNodeT = RawNodeV35
        RawSubstationSwitchingDeviceT = RawSubstationSwitchingDeviceV35
        RawEquipmentTerminalT = RawEquipmentTerminalV35
        RawGneDeviceT = RawGneDeviceV35
    else:
        RawAreaT = RawAreaV36
        RawZoneT = RawZoneV36
        RawBusT = RawBusV36
        RawLoadT = RawLoadV36
        RawFixedShuntT = RawFixedShuntV36
        RawSwitchedShuntT = RawSwitchedShuntV36
        RawGeneratorT = RawGeneratorV36
        RawBranchT = RawBranchV36
        RawTransformerT = RawTransformerV36
        RawTwoTerminalDCLineT = RawTwoTerminalDCLineV36
        RawVscDCLineT = RawVscDCLineV36
        RawFACTST = RawFACTSV36
        RawSystemSwitchingDeviceT = RawSystemSwitchingDeviceV36
        RawInductionMachineT = RawInductionMachineV36
        RawOwnerT = RawOwnerV36
        RawInterAreaT = RawInterAreaV36
        RawMultiLineSectionT = RawMultiLineSectionV36
        RawImpedanceCorrectionTableT = RawImpedanceCorrectionTableV36
        RawSubstationT = RawSubstationV36
        RawNodeT = RawNodeV36
        RawSubstationSwitchingDeviceT = RawSubstationSwitchingDeviceV36
        RawEquipmentTerminalT = RawEquipmentTerminalV36
        RawGneDeviceT = RawGneDeviceV36

    # declare contents:
    # section_idx, objects_list, expected_data_length, ObjectT, lines per objects

    # SEQUENCE ORDER:logger.add_warning("RAW header contains 3 elements instead of the expected 6")
    # 0:  Case Identification Data
    # 1:  Bus Data
    # 2:  Load Data
    # 3:  Fixed Bus Shunt Data
    # 4:  Generator Data
    # 5:  Non-Transformer Branch Data
    # 6:  Transformer Data
    # 7:  Area Interchange Data
    # 8:  Two-Terminal DC Transmission Line Data
    # 9:  Voltage Source Converter (VSC) DC Transmission Line Data
    # 10: Transformer Impedance Correction Tables
    # 11: Multi-Terminal DC Transmission Line Data
    # 12: Multi-Section Line Grouping Data
    # 13: Zone Data
    # 14: Inter-area Transfer Data
    # 15: Owner Data
    # 16: FACTS Device Data
    # 17: Switched Shunt Data
    # 18: GNE Device Data
    # 19: Induction Machine Data
    # 20: Q Record

    meta_data = dict()
    meta_data['bus'] = [grid.buses, RawBusT, 1]
    meta_data['load'] = [grid.loads, RawLoadT, 1]
    meta_data['fixed shunt'] = [grid.fixed_shunts, RawFixedShuntT, 1]
    meta_data['fixed bus shunt'] = [grid.fixed_shunts, RawFixedShuntT, 1]
    meta_data['shunt'] = [grid.fixed_shunts, RawFixedShuntT, 1]
    meta_data['switched shunt'] = [grid.switched_shunts, RawSwitchedShuntT, 1]
    meta_data['generator'] = [grid.generators, RawGeneratorT, 1]
    meta_data['induction machine'] = [grid.induction_machines, RawInductionMachineT, 3]
    meta_data['branch'] = [grid.branches, RawBranchT, 1]
    meta_data['nontransformer branch'] = [grid.branches, RawBranchT, 1]
    meta_data['system switching device'] = [grid.switches, RawSystemSwitchingDeviceT, 1]
    meta_data['transformer'] = [grid.transformers, RawTransformerT, 4]
    meta_data['two-terminal dc'] = [grid.two_terminal_dc_lines, RawTwoTerminalDCLineT, 3]
    meta_data['two-terminal dc line'] = [grid.two_terminal_dc_lines, RawTwoTerminalDCLineT, 3]
    meta_data['vsc dc line'] = [grid.vsc_dc_lines, RawVscDCLineT, 3]
    meta_data['facts device'] = [grid.facts, RawFACTST, 1]
    meta_data['facts control device'] = [grid.facts, RawFACTST, 1]
    meta_data['area data'] = [grid.areas, RawAreaT, 1]
    meta_data['area'] = [grid.areas, RawAreaT, 1]
    meta_data['area interchange'] = [grid.areas, RawAreaT, 1]
    meta_data['inter-area transfer'] = [grid.areas, RawInterAreaT, 1]
    meta_data['zone'] = [grid.zones, RawZoneT, 1]
    meta_data['owner'] = [grid.owners, RawOwnerT, 1]
    meta_data['gne'] = [grid.gne, RawGneDeviceT, 5]
    meta_data['impedance correction'] = [grid.indiction_tables, RawImpedanceCorrectionTableT, 1]
    meta_data['multi-section line'] = [grid.multi_line_sections, RawMultiLineSectionT, 1]
    bus_set = {lne[0] for lne in sections_dict["bus"]}

    for key, lines in sections_dict.items():

        if key == 'substation':
            if version >= 34:
                parse_substation_data_group(
                    lines=lines,
                    version=version,
                    logger=logger,
                    grid=grid,
                    raw_substation_t=RawSubstationT,
                    raw_node_t=RawNodeT,
                    raw_substation_switching_device_t=RawSubstationSwitchingDeviceT,
                    raw_equipment_terminal_t=RawEquipmentTerminalT
                )
            else:
                logger.add_warning(
                    'Substation data group is not defined before PSSE 34 and will be ignored',
                    key
                )
        elif key in meta_data:

            # get the parsers for the declared object type
            objects_list, ObjectT, lines_per_object = meta_data[key]

            if text_func is not None:
                text_func("Converting {0}...".format(key))

            if key in sections_dict.keys():

                # iterate ove the object's lines to pack them as expected
                # (normally 1 per object except transformers...)
                l_count = 0
                while l_count < len(lines):

                    # lines_per_object2 = lines_per_object
                    data: List[List[float | int | str]] = list()
                    if key == 'transformer':
                        # as you know the PSS/e raw format is nuts, that is why for v29 (onwards probably)
                        # the transformers may have 4 or 5 lines to define them
                        # so, to be able to know, we look at the line "l" and check if the first arguments
                        # are 2 or 3 buses
                        # Alex review required: this changes static PSS/E RAW import behavior.
                        is_three_winding: bool = is_3w(lines[l_count], bus_set)
                        if is_three_winding:
                            transformer_line_count: int = 5
                            transformer_description: str = "3W"
                        else:
                            transformer_line_count = 4
                            transformer_description = "2W"

                        # Parse a transformer only when its complete fixed-size record is available.
                        remaining_line_count: int = len(lines) - l_count
                        if remaining_line_count >= transformer_line_count:
                            for k in range(transformer_line_count):
                                data.append(lines[l_count])
                                l_count += 1
                        else:
                            logger.add_error(
                                "Incomplete {0} transformer data at the raw file".format(
                                    transformer_description
                                )
                            )
                            l_count = len(lines)

                    elif key == 'induction machine':
                        if is_one_line_for_induction_machine(lines[l_count]):
                            # only one line
                            data.append(lines[l_count])
                            l_count += 1
                        else:
                            for k in range(lines_per_object):
                                data.append(lines[l_count])
                                l_count += 1

                    elif key == 'impedance correction' and version >= 35:
                        # since PSSe is nothing but a very questionable set of legacy software,
                        # when we're dealing with impedance tables, the number of lines is unknown
                        # and determined by the termination criteria 0.0, 0.0, 0.0
                        done = False
                        while not done:
                            data.append(lines[l_count])
                            done = check_end_of_impedance_table(lines[l_count])
                            l_count += 1

                    else:

                        for k in range(lines_per_object):
                            data.append(lines[l_count])
                            l_count += 1

                    # pick the line that matches the object and split it by line returns \n
                    # object_lines = line.split('\n')

                    # interpret each line of the object and store into data.
                    # data is a vector of vectors with data definitions
                    # for the buses, branches, loads etc. data contains 1 vector,
                    # for the transformers data contains 4 vectors
                    # data = [interpret_line(object_lines[k]) for k in range(lines_per_object)]

                    # pass the data to the according object to assign it to the matching variables
                    if len(data) > 0:
                        data2 = format_lines(data1=data, logger=logger)
                        obj = ObjectT()
                        obj.parse(data2, version, logger)
                        objects_list.append(obj)
                    else:
                        pass

                    if progress_func is not None:
                        progress_func((l_count / len(lines)) * 100)

            else:
                pass

        else:
            if len(lines) > 0 and key not in ['info', 'comment', 'comment2', 'system-wide']:
                # add logs for the non parsed objects
                logger.add_warning('Not implemented in the parser', key)

    # check all primary keys
    grid.check_primary_keys(logger)

    # Auxiliary versions are chosen only after the RAW header establishes REV.
    if auxiliary_files is not None:
        grid.auxiliary_bus_mode = bus_mode
        for auxiliary_file in auxiliary_files:
            grid.read_auxiliary_file(auxiliary_file, layout_35=layout_35)
        logger += grid.auxiliary_logger
    else:
        pass

    return grid


def write_substation_data_group(handle,
                                psse_model: PsseCircuit,
                                version: int) -> None:
    """
    Write the nested PSSE 34+ substation data group.

    :param handle: Open output handle.
    :param psse_model: PSSE model to serialize.
    :param version: Target RAW version.
    :return: None
    """
    nodes_by_substation: Dict[int, List] = dict()
    switches_by_substation: Dict[int, List] = dict()
    terminals_by_substation: Dict[int, List] = dict()

    for node in psse_model.nodes:
        if node.ISUB in nodes_by_substation:
            nodes_by_substation[node.ISUB].append(node)
        else:
            nodes_by_substation[node.ISUB] = [node]

    for switch in psse_model.substation_switching_devices:
        if switch.ISUB in switches_by_substation:
            switches_by_substation[switch.ISUB].append(switch)
        else:
            switches_by_substation[switch.ISUB] = [switch]

    for terminal in psse_model.equipment_terminals:
        if terminal.ISUB in terminals_by_substation:
            terminals_by_substation[terminal.ISUB].append(terminal)
        else:
            terminals_by_substation[terminal.ISUB] = [terminal]

    for substation in psse_model.substations:
        handle.write(substation.get_raw_line(version=version) + "\n")

        substation_nodes = nodes_by_substation.get(substation.IS, list())
        for node in substation_nodes:
            handle.write(node.get_raw_line(version=version) + "\n")
        handle.write("0\n")

        substation_switches = switches_by_substation.get(substation.IS, list())
        for switch in substation_switches:
            handle.write(switch.get_raw_line(version=version) + "\n")
        handle.write("0\n")

        substation_terminals = terminals_by_substation.get(substation.IS, list())
        for terminal in substation_terminals:
            handle.write(terminal.get_raw_line(version=version) + "\n")
        handle.write("0\n")

    handle.write("0\n")


def write_raw(file_name: str, psse_model: PsseCircuit, version=33) -> Logger:
    """
    Write PsseCircuit as .raw version 33
    :param file_name: name of the file
    :param psse_model: PsseCircuit instance
    :param version: RAW version
    """

    version = normalize_psse_version(version)

    if version == 29:
        owner_t = RawOwnerV29
    elif version == 30:
        owner_t = RawOwnerV30
    elif version == 31:
        owner_t = RawOwnerV31
    elif version == 32:
        owner_t = RawOwnerV32
    elif version == 33:
        owner_t = RawOwnerV33
    elif version == 34:
        owner_t = RawOwnerV34
    elif version == 35:
        owner_t = RawOwnerV35
    else:
        owner_t = RawOwnerV36

    if len(psse_model.owners) == 0:
        ow = owner_t()
        ow.I = 1
        ow.OWNAME = "default"
        psse_model.owners.append(ow)

    logger = Logger()
    psse_model.warn_auxiliary_omission(logger)
    with open(file_name, "w", encoding="utf-8") as w:

        comment_map = None
        if version in comment_version_map.keys():
            comment_map = comment_version_map.get(version)

        # IC,SBASE,REV,XFRRAT,NXFRAT,BASFRQ
        if version >= 35:
            w.write("@!IC,SBASE,REV,XFRRAT,NXFRAT,BASFRQ\n")
        w.write("{},{},{},{},{},{}     / Created with VeraGrid\n".format(psse_model.IC, psse_model.SBASE, version,
                                                                         psse_model.XFRRAT, psse_model.NXFRAT,
                                                                         psse_model.BASFRQ))

        # comment 1
        now = datetime.datetime.now()
        w.write("(" + now.ctime() + ")  HORIZON: 20241205 00H DEM: 25029.8MW\n")  # Using fake values

        # comment 2
        w.write("HID:4644MW,TERM:10747MW,EOL:6503MW,FV:0MW,OK\n")
        if version >= 35:
            w.write("GENERAL, THRSHZ=0.0001, PQBRAK=0.7, BLOWUP=5.0, MaxIsolLvls=4, CAMaxReptSln=20, ChkDupCntLbl=0\n"
                    "GAUSS, ITMX=100, ACCP=1.6, ACCQ=1.6, ACCM=1.0, TOL=0.0001\n"
                    "NEWTON, ITMXN=20, ACCN=1.0, TOLN=0.1, VCTOLQ=0.1, VCTOLV=0.00001, DVLIM=0.99, NDVFCT=0.99\n"
                    "ADJUST, ADJTHR=0.005, ACCTAP=1.0, TAPLIM=0.05, SWVBND=100.0, MXTPSS=99, MXSWIM=10\n"
                    "TYSL, ITMXTY=20, ACCTY=1.0, TOLTY=0.00001\n"
                    "SOLVER, FNSL, ACTAPS=0, AREAIN=0, PHSHFT=0, DCTAPS=0, SWSHNT=0, FLATST=0, VARLIM=99, NONDIV=0\n"
                    'RATING, 1, "RATE1 ", "RATING SET 1                    "\n'
                    'RATING, 2, "RATE2 ", "RATING SET 2                    "\n'
                    'RATING, 3, "RATE3 ", "RATING SET 3                    "\n'
                    'RATING, 4, "RATE4 ", "RATING SET 4                    "\n'
                    'RATING, 5, "RATE5 ", "RATING SET 5                    "\n'
                    'RATING, 6, "RATE6 ", "RATING SET 6                    "\n'
                    'RATING, 7, "RATE7 ", "RATING SET 7                    "\n'
                    'RATING, 8, "RATE8 ", "RATING SET 8                    "\n'
                    'RATING, 9, "RATE9 ", "RATING SET 9                    "\n'
                    'RATING,10, "RATE10", "RATING SET 10                   "\n'
                    'RATING,11, "RATE11", "RATING SET 11                   "\n'
                    'RATING,12, "RATE12", "RATING SET 12                   "\n')  # Using fake values

            sections = [
                ("BUS", psse_model.buses),
                ("LOAD", psse_model.loads),
                ("FIXED SHUNT", psse_model.fixed_shunts),
                ("GENERATOR", psse_model.generators),
                ("BRANCH", psse_model.branches),
                ("SYSTEM SWITCHING DEVICE", psse_model.switches),
                ("TRANSFORMER", psse_model.transformers),
                ("AREA INTERCHANGE", psse_model.areas),
                ("TWO-TERMINAL DC LINE", psse_model.two_terminal_dc_lines),
                ("VSC DC LINE", psse_model.vsc_dc_lines),
                ("IMPEDANCE CORRECTION", None),
                ("MULTI-TERMINAL DC LINE", None),
                ("MULTI-SECTION LINE GROUP", psse_model.multi_line_sections),
                ("ZONE", psse_model.zones),
                ("INTER-AREA TRANSFER", psse_model.inter_areas),
                ("OWNER", psse_model.owners),
                ("FACTS DEVICE", psse_model.facts),
                ("SWITCHED SHUNT", psse_model.switched_shunts),
                ("SUBSTATION", psse_model.substations),
                ("GNE", psse_model.gne),
            ]
        elif version == 34:
            sections = [
                ("BUS", psse_model.buses),
                ("LOAD", psse_model.loads),
                ("FIXED SHUNT", psse_model.fixed_shunts),
                ("GENERATOR", psse_model.generators),
                ("BRANCH", psse_model.branches),
                ("SYSTEM SWITCHING DEVICE", psse_model.switches),
                ("TRANSFORMER", psse_model.transformers),
                ("AREA INTERCHANGE", psse_model.areas),
                ("TWO-TERMINAL DC LINE", psse_model.two_terminal_dc_lines),
                ("VSC DC LINE", psse_model.vsc_dc_lines),
                ("IMPEDANCE CORRECTION", None),
                ("MULTI-TERMINAL DC LINE", None),
                ("MULTI-SECTION LINE GROUP", psse_model.multi_line_sections),
                ("ZONE", psse_model.zones),
                ("INTER-AREA TRANSFER", psse_model.inter_areas),
                ("OWNER", psse_model.owners),
                ("FACTS DEVICE", psse_model.facts),
                ("SWITCHED SHUNT", psse_model.switched_shunts),
                ("SUBSTATION", psse_model.substations),
                ("GNE", psse_model.gne),
            ]
        elif version == 33:
            sections = [
                ("BUS", psse_model.buses),
                ("LOAD", psse_model.loads),
                ("FIXED SHUNT", psse_model.fixed_shunts),
                ("GENERATOR", psse_model.generators),
                ("BRANCH", psse_model.branches),
                ("TRANSFORMER", psse_model.transformers),
                ("AREA INTERCHANGE", psse_model.areas),
                ("TWO-TERMINAL DC LINE", psse_model.two_terminal_dc_lines),
                ("VSC DC LINE", psse_model.vsc_dc_lines),
                ("IMPEDANCE CORRECTION", None),  # TODO implement impedance correction data
                ("MULTI-TERMINAL DC LINE", None),  # todo: implement multi terminal dc line data
                ("MULTI-SECTION LINE GROUP", psse_model.multi_line_sections),
                ("ZONE", psse_model.zones),
                ("INTER-AREA TRANSFER", psse_model.inter_areas),
                ("OWNER", psse_model.owners),
                ("FACTS DEVICE", psse_model.facts),
                ("SWITCHED SHUNT", psse_model.switched_shunts),
                ("GNE", psse_model.gne),
            ]
        else:
            logger.add_error(msg="Version not supported",
                             value=version)
            return logger

        prev_section = None
        s_count = 0
        if version >= 35:
            prev_section = "SYSTEM-WIDE"
        elif version == 34 or version == 33:
            prev_section = "BUS"

        for section_name, objects_list in sections:
            if s_count == 0 and version == 33:
                pass
            else:
                w.write("0 / END OF " + prev_section + " DATA, BEGIN " + section_name + " DATA\n")
            if comment_map is not None:
                comment = comment_map.get(section_name)
                if comment is not None:
                    w.write(comment)
                else:
                    logger.add_info(msg="Missing comment for section",
                                    value=section_name)
            if objects_list is not None:
                if section_name == "SUBSTATION":
                    write_substation_data_group(handle=w, psse_model=psse_model, version=version)
                else:
                    for obj in objects_list:
                        w.write(obj.get_raw_line(version=version) + "\n")

            prev_section = section_name
            s_count += 1

        w.write("0 / END OF " + prev_section + " DATA\n")

        w.write("Q\n")

    return logger
