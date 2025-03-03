# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import chardet
import re
import datetime
from typing import List, AnyStr, Dict

from GridCalEngine.IO.raw.raw_writer_comment_map import comment_version_map
from GridCalEngine.basic_structures import Logger
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
from GridCalEngine.IO.raw.devices.multi_section_line import RawMultiLineSection
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit


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
    elms = re.split(pattern, lne)

    for elm in elms:

        if "'" in elm:
            el = elm.replace("'", "").strip()
        else:

            if "/" in elm:
                # the line might end with a comment "/ whatever" so we must remove the comment
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

    # make a guess of the file encoding
    detection = chardet.detect(open(file_name, "rb").read())

    # open the text file into a variable

    if text_func is not None:
        text_func("Reading raw file...")

    sections_dict: Dict[str, List[List[str | float | int] | str]] = dict()
    sections_dict["bus"] = list()
    sep = ","
    with open(file_name, 'r', encoding=detection['encoding']) as my_file:
        i = 0
        block_category = "bus"
        for line_ in my_file:

            if line_[0] != '@':
                # remove garbage
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

def read_raw(filename, text_func=None, progress_func=None, logger=Logger()) -> PsseCircuit:
    """

    :param filename:
    :param text_func:
    :param progress_func:
    :param logger:
    :return:
    """
    """
    Parser implemented according to:
        - POM section 4.1.1 Power Flow Raw Data File Contents (v.29)
        - POM section 5.2.1                                   (v.33)
        - POM section 5.2.1                                   (v.32)

    Returns: MultiCircuit, List[str]
    """

    versions = [35, 34, 33, 32, 30, 29]

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
        version = grid.REV

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
    meta_data['bus'] = [grid.buses, RawBus, 1]
    meta_data['load'] = [grid.loads, RawLoad, 1]
    meta_data['fixed shunt'] = [grid.fixed_shunts, RawFixedShunt, 1]
    meta_data['fixed bus shunt'] = [grid.fixed_shunts, RawFixedShunt, 1]
    meta_data['shunt'] = [grid.fixed_shunts, RawFixedShunt, 1]
    meta_data['switched shunt'] = [grid.switched_shunts, RawSwitchedShunt, 1]
    meta_data['generator'] = [grid.generators, RawGenerator, 1]
    meta_data['induction machine'] = [grid.induction_machines, RawInductionMachine, 3]
    meta_data['branch'] = [grid.branches, RawBranch, 1]
    meta_data['nontransformer branch'] = [grid.branches, RawBranch, 1]
    meta_data['system switching device'] = [grid.switches, RawSystemSwitchingDevice, 1]
    meta_data['substation'] = [grid.substations, RawSubstation, 1]
    meta_data['transformer'] = [grid.transformers, RawTransformer, 4]
    meta_data['two-terminal dc'] = [grid.two_terminal_dc_lines, RawTwoTerminalDCLine, 3]
    meta_data['two-terminal dc line'] = [grid.two_terminal_dc_lines, RawTwoTerminalDCLine, 3]
    meta_data['vsc dc line'] = [grid.vsc_dc_lines, RawVscDCLine, 3]
    meta_data['facts device'] = [grid.facts, RawFACTS, 1]
    meta_data['facts control device'] = [grid.facts, RawFACTS, 1]
    meta_data['area data'] = [grid.areas, RawArea, 1]
    meta_data['area'] = [grid.areas, RawArea, 1]
    meta_data['area interchange'] = [grid.areas, RawArea, 1]
    meta_data['inter-area transfer'] = [grid.areas, RawInterArea, 1]
    meta_data['zone'] = [grid.zones, RawZone, 1]
    meta_data['owner'] = [grid.owners, RawOwner, 1]
    meta_data['gne'] = [grid.gne, RawGneDevice, 5]
    meta_data['impedance correction'] = [grid.indiction_tables, RawImpedanceCorrectionTable, 1]
    meta_data['multi-section line'] = [grid.multi_line_sections, RawMultiLineSection, 1]
    bus_set = {lne[0] for lne in sections_dict["bus"]}

    for key, lines in sections_dict.items():

        if key in meta_data:

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
                        if is_3w(lines[l_count], bus_set):
                            # 3 - windings (5 lines)
                            for k in range(5):
                                data.append(lines[l_count])
                                l_count += 1
                        else:
                            # 2-windings (4 lines)
                            for k in range(4):
                                data.append(lines[l_count])
                                l_count += 1

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
                    data2 = format_lines(data1=data, logger=logger)
                    obj = ObjectT()
                    obj.parse(data2, version, logger)
                    objects_list.append(obj)

                    if progress_func is not None:
                        progress_func((l_count / len(lines)) * 100)

            else:
                pass

        else:
            if len(lines) > 0 and key not in ['info', 'comment', 'comment2']:
                # add logs for the non parsed objects
                logger.add_warning('Not implemented in the parser', key)

    # check all primary keys
    grid.check_primary_keys(logger)

    return grid


def write_raw(file_name: str, psse_model: PsseCircuit, version=33) -> Logger:
    """
    Write PsseCircuit as .raw version 33
    :param file_name: name of the file
    :param psse_model: PsseCircuit instance
    :param version: RAW version
    """

    if len(psse_model.owners) == 0:
        ow = RawOwner()
        ow.I = 1
        ow.OWNAME = "default"
        psse_model.owners.append(ow)

    logger = Logger()
    with open(file_name, "w", encoding="utf-8") as w:

        comment_map = None
        if version in comment_version_map.keys():
            comment_map = comment_version_map.get(version)

        # IC,SBASE,REV,XFRRAT,NXFRAT,BASFRQ
        if version == 35:
            w.write("@!IC,SBASE,REV,XFRRAT,NXFRAT,BASFRQ\n")
        w.write("{},{},{},{},{},{}     / Created with GridCal\n".format(psse_model.IC, psse_model.SBASE, version,
                                                                        psse_model.XFRRAT, psse_model.NXFRAT,
                                                                        psse_model.BASFRQ))

        # comment 1
        now = datetime.datetime.now()
        w.write("(" + now.ctime() + ")  HORIZON: 20241205 00H DEM: 25029.8MW\n")  # Using fake values

        # comment 2
        w.write("HID:4644MW,TERM:10747MW,EOL:6503MW,FV:0MW,OK\n")
        if version == 35:
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
                ("GNE", psse_model.gne),
                ("SUBSTATION", psse_model.substations),
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
                ("SUBSTATION", psse_model.substations),
            ]
        else:
            logger.add_error(msg="Version not supported",
                             value=version)
            return logger

        prev_section = None
        s_count = 0
        if version == 35:
            prev_section = "SYSTEM-WIDE"
        elif version == 33:
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
                for obj in objects_list:
                    w.write(obj.get_raw_line(version=version) + "\n")

            prev_section = section_name
            s_count += 1

        w.write("0 / END OF " + prev_section + " DATA\n")

        w.write("Q\n")

    return logger
