# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
from __future__ import annotations

import os
import chardet
import datetime
import re
from typing import List, AnyStr, Dict
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
from GridCalEngine.IO.raw.devices.system_switching_device import RawSystemSwitchingDevice
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


def interpret_line(raw_line, splitter=','):
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
    elms = lne.split(splitter)

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


#
# class PSSeRawParser:
#     """
#     PSSeParser
#     """
#
#     def __init__(self, file_name, text_func=print,  progress_func=None):
#         """
#         Parse PSSe file
#         Args:
#             file_name: file name or path
#         """
#         self.parsers = dict()
#         self.versions = [35, 34, 33, 32, 30, 29]
#
#         self.logger = Logger()
#
#         self.file_name = file_name
#
#         self.pss_grid, logs = self.parse_psse(text_func=text_func,  progress_func=progress_func)
#
#         self.logger += logs

def read_and_split(file_name, text_func=None, progress_func=None) -> (List[AnyStr], Dict[AnyStr, AnyStr]):
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

    sections_dict: Dict[str, List[str | float | int]] = dict()
    sections_dict["bus"] = list()
    sep = ","
    with open(file_name, 'r', encoding=detection['encoding']) as my_file:
        i = 0
        block_category = "bus"
        for line_ in my_file:

            if line_[0] != '@':
                # remove garbage
                lne = line_.strip()

                if lne.startswith("program"):
                    # common header
                    block_category = 'program'
                    sections_dict[block_category] = list()

                if i == 0:
                    sections_dict['info'] = [interpret_line(raw_line=lne, splitter=sep)]  # TODO: Fix the typing
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
                            sections_dict[block_category].append(interpret_line(raw_line=lne, splitter=sep))  # TODO: Fix the typing

                i += 1
            else:
                # it is a header
                hdr = line_.strip()
                pass

    return sections_dict


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

    sections_dict = read_and_split(file_name=filename, text_func=text_func, progress_func=progress_func)

    # header -> new grid
    # grid = PSSeGrid(interpret_line(sections[0]))
    grid = PsseCircuit()
    grid.parse(sections_dict['info'][0])

    if grid.REV not in versions:
        msg = 'The PSSe version is not compatible. Compatible versions are:'
        msg += ', '.join([str(a) for a in versions])
        logger.add_error(msg)
        return grid
    else:
        version = grid.REV

    # declare contents:
    # section_idx, objects_list, expected_data_length, ObjectT, lines per objects

    # SEQUENCE ORDER:
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

    bus_set = {lne[0] for lne in sections_dict["bus"]}

    def is_3w(row):
        return row[0] in bus_set and row[1] in bus_set and row[2] in bus_set

    def is_one_line_for_induction_machine(row):
        return len(row) != 12

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

                    lines_per_object2 = lines_per_object

                    if version in versions:
                        if key == 'transformer':
                            # as you know the PSS/e raw format is nuts, that is why for v29 (onwards probably)
                            # the transformers may have 4 or 5 lines to define them
                            # so, to be able to know, we look at the line "l" and check if the first arguments
                            # are 2 or 3 buses
                            if is_3w(lines[l_count]):
                                # 3 - windings
                                lines_per_object2 = 5
                            else:
                                # 2-windings
                                lines_per_object2 = 4
                        elif key == 'induction machine':
                            if is_one_line_for_induction_machine(lines[l_count]):
                                lines_per_object2 = 1

                    data = list()
                    for k in range(lines_per_object2):
                        data.append(lines[l_count + k])

                    # pick the line that matches the object and split it by line returns \n
                    # object_lines = line.split('\n')

                    # interpret each line of the object and store into data.
                    # data is a vector of vectors with data definitions
                    # for the buses, branches, loads etc. data contains 1 vector,
                    # for the transformers data contains 4 vectors
                    # data = [interpret_line(object_lines[k]) for k in range(lines_per_object)]

                    # pass the data to the according object to assign it to the matching variables
                    obj = ObjectT()
                    obj.parse(data, version, logger)
                    objects_list.append(obj)

                    # add lines
                    l_count += lines_per_object2

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
    logger = Logger()
    with open(file_name, "w", encoding="utf-8") as w:

        # IC,SBASE,REV,XFRRAT,NXFRAT,BASFRQ
        w.write("  {},{},{},{},{},{}\n".format(psse_model.IC, psse_model.SBASE, version,
                                               psse_model.XFRRAT, psse_model.NXFRAT, psse_model.BASFRQ))

        # comment 1
        now = datetime.datetime.now()
        w.write("" + now.ctime() + "\n")

        # comment 2
        w.write("Created with Roseta converter\n")

        if version >= 35:
            w.write("0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n")

        for p_elm in psse_model.buses:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF BUS DATA, BEGIN LOAD DATA   \n")
        for p_elm in psse_model.loads:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF LOAD DATA, BEGIN FIXED BUS SHUNT DATA  \n")
        for p_elm in psse_model.fixed_shunts:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF FIXED BUS SHUNT DATA, BEGIN GENERATOR DATA\n")
        for p_elm in psse_model.generators:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF GENERATOR DATA, BEGIN NONTRANSFORMER BRANCH DATA  \n")
        for p_elm in psse_model.branches:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF NONTRANSFORMER BRANCH DATA, BEGIN SYSTEM SWITCHING DEVICE DATA\n")
        for p_elm in psse_model.switches:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF SYSTEM SWITCHING DEVICE DATA, BEGIN TRANSFORMER DATA\n")
        for p_elm in psse_model.transformers:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF TRANSFORMER DATA, BEGIN AREA INTERCHANGE DATA \n")
        for p_elm in psse_model.areas:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF AREA INTERCHANGE DATA, BEGIN TWO-TERMINAL DC LINE DATA \n")
        for p_elm in psse_model.two_terminal_dc_lines:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF TWO-TERMINAL DC LINE DATA, BEGIN VSC DC LINE DATA \n")
        for p_elm in psse_model.vsc_dc_lines:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF VSC DC LINE DATA, BEGIN TRANSFORMER IMPEDANCE CORRECTION DATA \n")
        # TODO implement impedance correction data

        w.write(" 0 / END OF TRANSFORMER IMPEDANCE CORRECTION DATA, BEGIN MULTI-TERMINAL DC LINE DATA \n")
        # todo: implement multi terminal dc line data

        w.write(" 0 / END OF MULTI-TERMINAL DC LINE DATA, BEGIN MULTI-SECTION LINE GROUP DATA \n")
        # todo: implement multi-section line group data

        w.write(" 0 / END OF MULTI-SECTION LINE GROUP DATA, BEGIN ZONE DATA\n")
        for p_elm in psse_model.zones:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF ZONE DATA, BEGIN INTER-AREA TRANSFER DATA \n")
        for p_elm in psse_model.inter_areas:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF INTER-AREA TRANSFER DATA, BEGIN OWNER DATA \n")
        for p_elm in psse_model.owners:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF OWNER DATA, BEGIN FACTS CONTROL DEVICE DATA \n")
        for p_elm in psse_model.facts:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF FACTS CONTROL DEVICE DATA, BEGIN SWITCHED SHUNT DATA\n")
        for p_elm in psse_model.switched_shunts:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF SWITCHED SHUNT DATA, BEGIN GNE DATA\n")
        for p_elm in psse_model.gne:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF GNE DATA, BEGIN SUBSTATION DATA\n")
        for p_elm in psse_model.substations:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write("0 / END OF SUBSTATION DATA\n")

        w.write("Q\n")

        # for p_elm in psse_model.induction_machines:
        #     w.write(" " + p_elm.get_raw_line(version=version) + "\n")

    return logger
