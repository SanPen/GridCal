# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import chardet
import re
import datetime
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

    # elms = lne.split(splitter)

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
    meta_data['impedance correction'] = [grid.indiction_tables, RawImpedanceCorrectionTable, 2]
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
                    data = list()
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

                    elif key == 'impedance correction':
                        # since PSSe is nothing but a very questionable set of legacy sofwtare,
                        # when we're dealing with impedance tables, the number of lines is unkown
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
                    obj = ObjectT()
                    obj.parse(data, version, logger)
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

        # IC,SBASE,REV,XFRRAT,NXFRAT,BASFRQ
        w.write("  {},{},{},{},{},{}\n".format(psse_model.IC, psse_model.SBASE, version,
                                               psse_model.XFRRAT, psse_model.NXFRAT, psse_model.BASFRQ))

        # comment 1
        now = datetime.datetime.now()
        w.write("" + now.ctime() + "\n")

        # comment 2
        w.write("Created with GridCal\n")

        if version >= 35:
            w.write("0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n")
            w.write("@!   I,'NAME        ', BASKV, IDE,AREA,ZONE,OWNER, VM,        VA,    NVHI,   NVLO,   EVHI,   "
                    "EVLO\n")

        for p_elm in psse_model.buses:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF BUS DATA, BEGIN LOAD DATA   \n")
        w.write("@!   I,'ID',STAT,AREA,ZONE,      PL,        QL,        IP,        IQ,        YP,        YQ, OWNER,"
                "SCALE,INTRPT,  DGENP,     DGENQ,DGENF,'  LOAD TYPE '\n")
        for p_elm in psse_model.loads:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF LOAD DATA, BEGIN FIXED BUS SHUNT DATA  \n")
        w.write("@!   I,'ID',STATUS,  GL,        BL\n")
        for p_elm in psse_model.fixed_shunts:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF FIXED BUS SHUNT DATA, BEGIN GENERATOR DATA\n")
        w.write("@!   I,'ID',      PG,        QG,        QT,        QB,     VS,    IREG,NREG,     MBASE,     ZR,      "
                "   ZX,         RT,         XT,     GTAP,STAT, RMPCT,      PT,        PB,BASLOD,O1,    F1,  O2,    "
                "F2,  O3,    F3,  O4,    F4,WMOD, WPF\n")
        for p_elm in psse_model.generators:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF GENERATOR DATA, BEGIN NONTRANSFORMER BRANCH DATA  \n")
        w.write("@!   I,     J,'CKT',      R,           X,       B,                   'N A M E'                 ,  "
                "RATE1,  RATE2,  RATE3,  RATE4,  RATE5,  RATE6,  RATE7,  RATE8,  RATE9, RATE10, RATE11, RATE12,   GI, "
                "     BI,      GJ,      BJ,STAT,MET, LEN,  O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4\n")
        for p_elm in psse_model.branches:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF NONTRANSFORMER BRANCH DATA, BEGIN SYSTEM SWITCHING DEVICE DATA\n")
        w.write("@!   I,     J,'CKT',          X,  RATE1,  RATE2,  RATE3,  RATE4,  RATE5,  RATE6,  RATE7,  RATE8,  "
                "RATE9, RATE10, RATE11, RATE12, STAT,NSTAT,  MET,STYPE,'NAME'\n")
        for p_elm in psse_model.switches:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF SYSTEM SWITCHING DEVICE DATA, BEGIN TRANSFORMER DATA\n")
        w.write("@!   I,     J,     K,'CKT',CW,CZ,CM,     MAG1,        MAG2,NMETR,               'N A M E',"
                "               STAT,O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4,     'VECGRP', ZCOD\n"
                "@!   R1-2,       X1-2, SBASE1-2,     R2-3,       X2-3, SBASE2-3,     R3-1,       X3-1, SBASE3-1,"
                " VMSTAR,   ANSTAR\n"
                "@!WINDV1, NOMV1,   ANG1, RATE1-1, RATE1-2, RATE1-3, RATE1-4, RATE1-5, RATE1-6, RATE1-7, RATE1-8,"
                " RATE1-9,RATE1-10,RATE1-11,RATE1-12,COD1,CONT1,NOD1,  RMA1,   RMI1,"
                "   VMA1,   VMI1, NTP1,TAB1, CR1,    CX1,  CNXA1\n"
                "@!WINDV2, NOMV2,   ANG2, RATE2-1, RATE2-2, RATE2-3, RATE2-4, RATE2-5, RATE2-6, RATE2-7, RATE2-8,"
                " RATE2-9,RATE2-10,RATE2-11,RATE2-12,COD2,CONT2,NOD2,  RMA2,   RMI2,"
                "   VMA2,   VMI2, NTP2,TAB2, CR2,    CX2,  CNXA2\n"
                "@!WINDV3, NOMV3,   ANG3, RATE3-1, RATE3-2, RATE3-3, RATE3-4, RATE3-5, RATE3-6, RATE3-7, RATE3-8, "
                "RATE3-9,RATE3-10,RATE3-11,RATE3-12,COD3,CONT3,NOD3,  RMA3,   RMI3,   VMA3,   VMI3, NTP3,TAB3, CR3,   "
                " CX3,  CNXA3\n")
        for p_elm in psse_model.transformers:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF TRANSFORMER DATA, BEGIN AREA INTERCHANGE DATA \n")
        w.write("@! I,   ISW,    PDES,     PTOL,    'ARNAME'\n")
        for p_elm in psse_model.areas:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF AREA INTERCHANGE DATA, BEGIN TWO-TERMINAL DC LINE DATA \n")
        w.write("@!  'NAME',   MDC,    RDC,     SETVL,    VSCHD,    VCMOD,    RCOMP,   DELTI,METER   DCVMIN,CCCITMX,"
                "CCCACC\n"
                "@! IPR,NBR,  ANMXR,  ANMNR,   RCR,    XCR,   EBASR,  TRR,    TAPR,   TMXR,   TMNR,   STPR,    ICR,"
                "NDR,   IFR,   ITR,'IDR', XCAPR\n"
                "@! IPI,NBI,  ANMXI,  ANMNI,   RCI,    XCI,   EBASI,  TRI,    TAPI,   TMXI,   TMNI,   STPI,    ICI,"
                "NDI,   IFI,   ITI,'IDI', XCAPI\n")
        for p_elm in psse_model.two_terminal_dc_lines:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF TWO-TERMINAL DC LINE DATA, BEGIN VSC DC LINE DATA \n")
        w.write("@!  'NAME',   MDC,  RDC,   O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4\n"
                "@!IBUS,TYPE,MODE,  DCSET,  ACSET,  ALOSS,  BLOSS,MINLOSS,  SMAX,   IMAX,   PWF,     MAXQ,   MINQ, \n"
                "VSREG,NREG, RMPCT\n")
        for p_elm in psse_model.vsc_dc_lines:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF VSC DC LINE DATA, BEGIN TRANSFORMER IMPEDANCE CORRECTION DATA \n")
        w.write("@!I,  T1,   Re(F1), Im(F1),   T2,   Re(F2), Im(F2),   T3,   Re(F3), Im(F3),   T4,   Re(F4), Im(F4),  "
                " T5,   Re(F5), Im(F5),   T6,   Re(F6), Im(F6)\n"
                "@!    T7,   Re(F7), Im(F7),   T8,   Re(F8), Im(F8),   T9,   Re(F9), Im(F9),   T10, Re(F10),Im(F10),  "
                " T11, Re(F11),Im(F11),   T12, Re(F12),Im(F12)\n"
                "@!      ...\n")
        # TODO implement impedance correction data

        w.write(" 0 / END OF TRANSFORMER IMPEDANCE CORRECTION DATA, BEGIN MULTI-TERMINAL DC LINE DATA \n")
        w.write("@!  'NAME',    NCONV,NDCBS,NDCLN,  MDC, VCONV,   VCMOD, VCONVN\n"
                "@!  IB, N,  ANGMX,  ANGMN,   RC,     XC,     EBAS,   TR,    TAP,    TPMX,   TPMN,   TSTP,   SETVL,   "
                "DCPF,  MARG,CNVCOD\n"
                "@!IDC, IB,AREA,ZONE,   'DCNAME',  IDC2, RGRND,OWNER\n"
                "@!IDC,JDC,'DCCKT',MET,  RDC,      LDC\n")
        # todo: implement multi terminal dc line data

        w.write(" 0 / END OF MULTI-TERMINAL DC LINE DATA, BEGIN MULTI-SECTION LINE GROUP DATA \n")
        w.write("@!   I,     J,'ID',MET,DUM1,  DUM2,  DUM3,  DUM4,  DUM5,  DUM6,  DUM7,  DUM8,  DUM9\n")
        # todo: implement multi-section line group data

        w.write(" 0 / END OF MULTI-SECTION LINE GROUP DATA, BEGIN ZONE DATA\n")
        w.write("@! I,   'ZONAME'\n")
        for p_elm in psse_model.zones:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF ZONE DATA, BEGIN INTER-AREA TRANSFER DATA \n")
        w.write("@!ARFROM,ARTO,'TRID',PTRAN\n")
        for p_elm in psse_model.inter_areas:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF INTER-AREA TRANSFER DATA, BEGIN OWNER DATA \n")
        w.write("@! I,   'OWNAME'\n")
        for p_elm in psse_model.owners:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF OWNER DATA, BEGIN FACTS CONTROL DEVICE DATA \n")
        w.write("@!  'NAME',         I,     J,MODE,PDES,   QDES,  VSET,   SHMX,   TRMX,   VTMN,   VTMX,   VSMX,    "
                "IMX,   LINX,   RMPCT,OWNER,  SET1,    SET2,VSREF, FCREG,NREG,   'MNAME'\n")
        for p_elm in psse_model.facts:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF FACTS CONTROL DEVICE DATA, BEGIN SWITCHED SHUNT DATA\n")
        w.write("@!   I,'ID',MODSW,ADJM,ST, VSWHI,  VSWLO, SWREG,NREG, RMPCT,   'RMIDNT',     BINIT,S1,N1,    B1, S2,"
                "N2,    B2, S3,N3,    B3, S4,N4,    B4, S5,N5,    B5, S6,N6,    B6, S7,N7,    B7, S8,N8,    B8\n")
        for p_elm in psse_model.switched_shunts:
            w.write(" " + p_elm.get_raw_line(version=version) + "\n")

        w.write(" 0 / END OF SWITCHED SHUNT DATA, BEGIN GNE DATA\n")
        w.write("@!  'NAME',        'MODEL',     NTERM,BUS1...BUSNTERM,NREAL,NINTG,NCHAR\n"
                "@!ST,OWNER,NMETR\n"
                "@! REAL1...REAL(MIN(10,NREAL))\n"
                "@! INTG1...INTG(MIN(10,NINTG))\n"
                "@! CHAR1...CHAR(MIN(10,NCHAR))\n")
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
