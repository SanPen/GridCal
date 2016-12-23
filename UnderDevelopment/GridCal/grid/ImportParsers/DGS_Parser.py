# -*- coding: utf-8 -*-
"""
# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
"""

import networkx as nx
from GridCal.grid.ImportParsers import BusDefinitions as bd
from GridCal.grid.ImportParsers import BranchDefinitions as brd
from GridCal.grid.ImportParsers import GenDefinitions as gd
import math
import numpy as np
import pandas as pd
from numpy import array
from pandas import DataFrame as df
from warnings import warn

pd.set_option('display.height', 1000)
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)


def get_transformer_impedances(Uhv, Ulv, Sn, Pcu, Pfe, I0, Usc, GR_hv1=0.5, GX_hv1=0.5):
    """
    Get the transformer series and shunt equivalent impedances from the short circuit values
    @param Uhv: Nominal voltage at the high side (kV)
    @param Ulv: Nominal voltage at the low side (kV)
    @param Sn: Nominal power (MVA)
    @param Pcu: Copper losses (kW) (Losses due to the Joule effect)
    @param Pfe: Iron-losses (kW)  (Losses in the magnetic circuit)
    @param I0: No-load current (%)
    @param Usc: Short-circuit voltage (%)
    @param GR_hv1: Resistive short circuit contribution to the HV side. It is a value from 0 to 1.
    @param GX_hv1: Reactive short circuit contribution to the HV side. It is a value from 0 to 1.
    @return:
    """

    # Nominal impedance HV (Ohm)
    Zn_hv = Uhv * Uhv / Sn

    # Nominal impedance LV (Ohm)
    Zn_lv = Ulv * Ulv / Sn

    # Short circuit impedance (p.u.)
    zsc = Usc / 100.0

    # Short circuit resistance (p.u.)
    rsc = (Pcu / 1000.0) / Sn

    # Short circuit reactance (p.u.)
    xsc = np.sqrt(zsc * zsc - rsc * rsc)

    # HV resistance (p.u.)
    rcu_hv = rsc * GR_hv1

    # LV resistance (p.u.)
    rcu_lv = rsc * (1.0 - GR_hv1)

    # HV shunt reactance (p.u.)
    xs_hv = xsc * GX_hv1

    # LV shunt reactance (p.u.)
    xs_lv = xsc * (1.0 - GX_hv1)

    # Shunt resistance (p.u.)
    rfe = Sn / (Pfe / 1000.0)

    # Magnetization impedance (p.u.)
    zm = 1.0 / (I0 / 100.0)

    # Magnetization reactance (p.u.)
    xm = 0.0
    if rfe > zm:
        xm = 1.0 / np.sqrt(1.0 / (zm * zm) - 1.0 / (rfe * rfe))
    else:
        xm = 0.0  # the square root cannot be computed

    # Calculated parameters in per unit
    leakage_impedance = rsc + 1j * xsc
    magnetizing_impedance = rfe + 1j * xm

    return leakage_impedance, magnetizing_impedance


def read_DGS(filename):
    ###############################################################################
    # Read the file
    ###############################################################################
    f = open(filename, errors='replace')
    lines = f.readlines()
    f.close()

    ###############################################################################
    # Process the data
    ###############################################################################
    data = dict()

    """
    Numpy types:

    'b' 	boolean
    'i' 	(signed) integer
    'u' 	unsigned integer
    'f' 	floating-point
    'c' 	complex-floating point
    'O' 	(Python) objects
    'S', 'a' 	(byte-)string
    'U' 	Unicode
    'V' 	raw data (void)
    """

    """
    DGS types

    a
    p
    i
    r

    """
    types_dict = dict()
    types_dict["a"] = "|S32"
    types_dict["p"] = "|S32"
    types_dict["i"] = "<i4"
    types_dict["r"] = "<f4"
    types_dict["d"] = "<f4"

    types_dict2 = dict()

    CurrentType = None
    DataTypes = None
    Header = None

    Headers = dict()
    # parse the file lines
    for line in lines:

        if line.startswith("$$"):
            line = line[2:]
            chnks = line.split(";")
            CurrentType = chnks[0]
            data[CurrentType] = list()

            # analyze types
            DataTypes = list()
            DataTypes2 = list()
            Header = list()
            for i in range(1, len(chnks)):
                token = chnks[i].split("(")
                name = token[0]
                tpe = token[1][:-1]
                DataTypes.append((name, types_dict[tpe[0]]))
                Header.append(name)

            types_dict2[CurrentType] = DataTypes

            Headers[CurrentType] = Header

        elif line.startswith("*"):
            pass

        elif line.startswith("  "):
            if CurrentType is not None:
                line = line.strip()
                chnks = line.split(";")
                chnks = ["0" if x == "" else x for x in chnks]
                data[CurrentType].append(array(tuple(chnks)))

    # format keys
    for key in data.keys():
        print("Converting " + str(key))
        table = array([tuple(x) for x in data[key]],dtype=types_dict2[key])
        table = array([list(x) for x in table],dtype=np.object)
        header = Headers[key]
        data[key] = df(data=table, columns=header)

    # positions dictionary
    obj_id = data['IntGrf']['pDataObj'].values
    x_vec = data['IntGrf']['rCenterX'].values
    y_vec = data['IntGrf']['rCenterY'].values
    pos_dict = dict()
    for i in range(len(obj_id)):
        pos_dict[obj_id[i]] = (x_vec[i], y_vec[i])
    ###############################################################################
    # Refactor data into classes
    ###############################################################################

    # store tables for easy reference

    '''
    ###############################################################################
    *  Line
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypLne,TypTow,TypGeo,TypCabsys
    *  chr_name: Characteristic Name
    *  dline: Parameters: Length of Line in km
    *  fline: Parameters: Derating Factor
    *  outserv: Out of Service
    *  pStoch: Failures: Element model in StoTyplne
    '''
    if "ElmLne" in data.keys():
        lines = data["ElmLne"]
    else:
        lines = np.zeros((0,20))



    '''
    ###############################################################################
    *  Line Type
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  chr_name: Characteristic Name
    *  Ithr: Rated Short-Time (1s) Current (Conductor) in kA
    *  aohl_: Cable / OHL
    *  cline: Parameters per Length 1,2-Sequence: Capacitance C' in uF/km
    *  cline0: Parameters per Length Zero Sequence: Capacitance C0' in uF/km
    *  nlnph: Phases:1:2:3
    *  nneutral: Number of Neutrals:0:1
    *  rline: Parameters per Length 1,2-Sequence: AC-Resistance R'(20°C) in Ohm/km
    *  rline0: Parameters per Length Zero Sequence: AC-Resistance R0' in Ohm/km
    *  rtemp: Max. End Temperature in degC
    *  sline: Rated Current in kA
    *  uline: Rated Voltage in kV
    *  xline: Parameters per Length 1,2-Sequence: Reactance X' in Ohm/km
    *  xline0: Parameters per Length Zero Sequence: Reactance X0' in Ohm/km
    '''
    if "TypLne" in data.keys():
        lines_types = data["TypLne"]
    else:
        lines_types = np.zeros((0,20))

    '''
    ###############################################################################
    *  2-Winding Transformer
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypTr2
    *  chr_name: Characteristic Name
    *  sernum: Serial Number
    *  constr: Year of Construction
    *  cgnd_h: Internal Grounding Impedance, HV Side: Star Point:Connected:Not connected
    *  cgnd_l: Internal Grounding Impedance, LV Side: Star Point:Connected:Not connected
    *  i_auto: Auto Transformer
    *  nntap: Tap Changer 1: Tap Position
    *  ntrcn: Controller, Tap Changer 1: Automatic Tap Changing
    *  outserv: Out of Service
    *  ratfac: Rating Factor
    '''
    if "ElmTr2" in data.keys():
        transformers = data["ElmTr2"]
    else:
        transformers = np.zeros((0, 20))



    '''
    ###############################################################################
    *  2-Winding Transformer Type
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  chr_name: Characteristic Name
    *  curmg: Magnetising Impedance: No Load Current in %
    *  dutap: Tap Changer 1: Additional Voltage per Tap in %
    *  frnom: Nominal Frequency in Hz
    *  manuf: Manufacturer
    *  nntap0: Tap Changer 1: Neutral Position
    *  nt2ag: Vector Group: Phase Shift in *30deg
    *  ntpmn: Tap Changer 1: Minimum Position
    *  ntpmx: Tap Changer 1: Maximum Position
    *  pcutr: Positive Sequence Impedance: Copper Losses in kW
    *  pfe: Magnetising Impedance: No Load Losses in kW
    *  phitr: Tap Changer 1: Phase of du in deg
    *  strn: Rated Power in MVA
    *  tap_side: Tap Changer 1: at Side:HV:LV
    *  tr2cn_h: Vector Group: HV-Side:Y :YN:Z :ZN:D
    *  tr2cn_l: Vector Group: LV-Side:Y :YN:Z :ZN:D
    *  uk0tr: Zero Sequence Impedance: Short-Circuit Voltage uk0 in %
    *  uktr: Positive Sequence Impedance: Short-Circuit Voltage uk in %
    *  ur0tr: Zero Sequence Impedance: SHC-Voltage (Re(uk0)) uk0r in %
    *  utrn_h: Rated Voltage: HV-Side in kV
    *  utrn_l: Rated Voltage: LV-Side in kV
    *  zx0hl_n: Zero Sequence Magnetising Impedance: Mag. Impedance/uk0
    '''
    if "TypTr2" in data.keys():
        transformers_types = data["TypTr2"]
    else:
        transformers_types = np.zeros((0, 20))

    '''
    ###############################################################################
    *  Terminal
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypBar
    *  chr_name: Characteristic Name
    *  iUsage: Usage:Busbar:Junction Node:Internal Node
    *  outserv: Out of Service
    *  phtech: Phase Technology:ABC:ABC-N:BI:BI-N:2PH:2PH-N:1PH:1PH-N:N
    *  uknom: Nominal Voltage: Line-Line in kV
    '''
    if "ElmTerm" in data.keys():
        buses = data["ElmTerm"]
    else:
        buses = np.zeros((0, 20))


    '''
    ###############################################################################
    *  Cubicle
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  chr_name: Characteristic Name
    *  obj_bus: Bus Index
    *  obj_id: Connected with in Elm*
    '''
    if "StaCubic" in data.keys():
        cubicles = data["StaCubic"]
    else:
        cubicles = np.zeros((0, 20))

    '''
    ###############################################################################
    *  General Load
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypLod,TypLodind
    *  chr_name: Characteristic Name
    *  outserv: Out of Service
    *  plini: Operating Point: Active Power in MW
    *  qlini: Operating Point: Reactive Power in Mvar
    *  scale0: Operating Point: Scaling Factor
    '''
    if "ElmLod" in data.keys():
        loads = data["ElmLod"]
    else:
        loads = np.zeros((0, 20))



    '''
    ###############################################################################
    *  External Grid
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  chr_name: Characteristic Name
    *  bustp: Bus Type:PQ:PV:SL
    *  cgnd: Internal Grounding Impedance: Star Point:Connected:Not connected
    *  iintgnd: Neutral Conductor: N-Connection:None:At terminal (ABC-N):Separate terminal
    *  ikssmin: Min. Values: Short-Circuit Current Ik''min in kA
    *  r0tx0: Max. Values Impedance Ratio: R0/X0 max.
    *  r0tx0min: Min. Values Impedance Ratio: R0/X0 min.
    *  rntxn: Max. Values: R/X Ratio (max.)
    *  rntxnmin: Min. Values: R/X Ratio (min.)
    *  snss: Max. Values: Short-Circuit Power Sk''max in MVA
    *  snssmin: Min. Values: Short-Circuit Power Sk''min in MVA
    '''
    if "ElmXnet" in data.keys():
        external = data["ElmXnet"]
    else:
        external = np.zeros((0, 20))


    '''
    ###############################################################################
    *  Grid
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  frnom: Nominal Frequency in Hz
    '''
    if "ElmNet" in data.keys():
        grid = data["ElmNet"]
    else:
        grid = np.zeros((0, 20))



    '''
    ###############################################################################
    '''
    if "ElmGenstat" in data.keys():
        static_generators = data["ElmGenstat"]
    else:
        static_generators = np.zeros((0, 20))


    '''
    ###############################################################################
    *  Synchronous Machine
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypSym
    *  chr_name: Characteristic Name
    *  i_mot: Generator/Motor
    *  iv_mode: Local Controller
    *  ngnum: Number of: parallel Machines
    *  outserv: Out of Service
    *  pgini: Dispatch: Active Power in MW
    *  q_max: Reactive Power Operational Limits: Max. in p.u.
    *  q_min: Reactive Power Operational Limits: Min. in p.u.
    *  qgini: Dispatch: Reactive Power in Mvar
    *  usetp: Dispatch: Voltage in p.u.
    '''
    if "ElmSym" in data.keys():
        synchronous_machine = data["ElmSym"]
    else:
        synchronous_machine = np.zeros((0, 20))


    '''
    ###############################################################################
    *  Synchronous Machine Type
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  cosn: Power Factor
    *  rstr: Stator Resistance: rstr in p.u.
    *  satur: For single fed short-circuit: Machine Type IEC909/IEC60909
    *  sgn: Nominal Apparent Power in MVA
    *  ugn: Nominal Voltage in kV
    *  xd: Synchronous Reactances: xd in p.u.
    *  xdsat: For single fed short-circuit: Reciprocal of short-circuit ratio (xdsat) in p.u.
    *  xdsss: Subtransient Reactance: saturated value xd''sat in p.u.
    *  xq: Synchronous Reactances: xq in p.u.
    '''
    if "TypSym" in data.keys():
        synchronous_machine_type = data["TypSym"]
    else:
        synchronous_machine_type = np.zeros((0, 20))


    '''
    ###############################################################################
    *  Asynchronous Machine
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypAsm*,TypAsmo*,TypAsm1*
    *  chr_name: Characteristic Name
    *  i_mot: Generator/Motor
    *  ngnum: Number of: parallel Machines
    *  outserv: Out of Service
    *  pgini: Dispatch: Active Power in MW
    '''
    if "ElmAsm" in data.keys():
        asynchronous_machine = data["ElmAsm"]
    else:
        asynchronous_machine = np.zeros((0, 20))



    '''
    ###############################################################################
    *  Synchronous Machine Type
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  i_mode: Input Mode
    *  aiazn: Consider Transient Parameter: Locked Rotor Current (Ilr/In) in p.u.
    *  amazn: Locked Rotor Torque in p.u.
    *  amkzn: Torque at Stalling Point in p.u.
    *  anend: Nominal Speed in rpm
    *  cosn: Rated Power Factor
    *  effic: Efficiency at nominal Operation in %
    *  frequ: Nominal Frequency in Hz
    *  i_cage: Rotor
    *  nppol: No of Pole Pairs
    *  pgn: Power Rating: Rated Mechanical Power in kW
    *  ugn: Rated Voltage in kV
    *  xmrtr: Rotor Leakage Reac. Xrm in p.u.
    *  xstr: Stator Reactance Xs in p.u.
    '''
    if "TypAsmo" in data.keys():
        asynchronous_machine_type = data["TypAsmo"]
    else:
        asynchronous_machine_type = np.zeros((0, 20))


    '''
    ###############################################################################
    *  Shunt/Filter
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  chr_name: Characteristic Name
    *  ctech: Technology
    *  fres: Design Parameter (per Step): Resonance Frequency in Hz
    *  greaf0: Design Parameter (per Step): Quality Factor (at fr)
    *  iswitch: Controller: Switchable
    *  ncapa: Controller: Act.No. of Step
    *  ncapx: Controller: Max. No. of Steps
    *  outserv: Out of Service
    *  qtotn: Design Parameter (per Step): Rated Reactive Power, L-C in Mvar
    *  shtype: Shunt Type
    *  ushnm: Nominal Voltage in kV
    '''
    if "ElmShnt" in data.keys():
        shunts = data["ElmShnt"]
    else:
        shunts = np.zeros((0, 20))

    '''
    ###############################################################################
    *  Breaker/Switch
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypSwitch
    *  chr_name: Characteristic Name
    *  aUsage: Switch Type
    *  nneutral: No. of Neutrals:0:1
    *  nphase: No. of Phases:1:2:3
    *  on_off: Closed
    '''
    if "ElmCoup" in data.keys():
        switches = data["ElmCoup"]
    else:
        switches = np.zeros((0, 20))

    # put the tables that connect to a terminal in a list
    classes = [lines, transformers, loads, external, static_generators, shunts]

    # put the branch classes in a list
    branch_classes = [lines, transformers]

    # generator classes
    generator_classes = [static_generators, synchronous_machine,
                         asynchronous_machine]

    ###############################################################################
    # Post process the data
    ###############################################################################

    # dictionary to store the terminals ID associated with an object ID
    terminals_dict = dict()

    # construct the terminals dictionary
    cub_obj_idx = cubicles['obj_id'].values
    cub_term_idx = cubicles['fold_id'].values
    ID_idx = 0
    for cla in classes:
        if cla.__len__() > 0:
            for ID in cla['ID'].values:
                idx = np.where(cubicles == ID)[0]
                terminals_dict[ID] = cub_term_idx[idx]

    ###############################################################################
    # Generate GridCal data
    ###############################################################################

    # general values
    baseMVA = 100
    frequency = grid['frnom'][0]
    w = 2.0 * math.pi * frequency

    BUSES = list()
    BUS_NAMES = list()
    bus_line = np.zeros(len(bd.bus_headers), dtype=np.double)

    BRANCHES = list()
    BRANCH_NAMES = list()
    branch_line = np.zeros(len(brd.branch_headers), dtype=np.double)

    GEN = list()
    GEN_NAMES = list()
    gen_line = np.zeros(len(gd.gen_headers), dtype=np.double)

    g = nx.graph.Graph()

    ####################################################################################################################
    # Terminals (nodes)
    ####################################################################################################################
    print('Parsing terminals')
    buses_dict = dict()
    gpos = dict()
    for i in range(len(buses)):
        ID = buses['ID'][i]
        x, y = pos_dict[ID]
        bus_ = bus_line.copy()
        bus_[bd.BUS_I] = BUSES.__len__()  # ID
        bus_[bd.BUS_TYPE] = 1  # by default is a PQ node  {1:PQ, 2:PV, 3:VD}
        bus_[bd.VM] = 1.0  # VM
        bus_[bd.VA] = 0.0  # VA
        bus_[bd.BASE_KV] = buses['uknom'][i]  # BaseKv
        bus_[bd.VMAX] = 1.05  # VMax
        bus_[bd.VMIN] = 0.95  # VMin
        bus_[bd.BUS_X] = x
        bus_[bd.BUS_Y] = y
        BUSES.append(bus_)

        bus_name = buses['loc_name'][i]  # BUS_Name
        BUS_NAMES.append(bus_name)

        buses_dict[ID] = i
        gpos[i] = (x, y)

    BUSES = np.array(BUSES)
    BUS_NAMES = np.array(BUS_NAMES)

    ####################################################################################################################
    # External grids (slacks)
    ####################################################################################################################
    '''
    ###############################################################################
    ********************************************************************************
    *  External Grid
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  outserv: Out of Service
    *  snss: Max. Values: Short-Circuit Power Sk''max in MVA
    *  rntxn: Max. Values: R/X Ratio (max.)
    *  z2tz1: Max. Values Impedance Ratio: Z2/Z1 max.
    *  snssmin: Min. Values: Short-Circuit Power Sk''min in MVA
    *  rntxnmin: Min. Values: R/X Ratio (min.)
    *  z2tz1min: Min. Values Impedance Ratio: Z2/Z1 min.
    *  chr_name: Characteristic Name
    *  bustp: Bus Type:PQ:PV:SL
    *  pgini: Operation Point: Active Power in MW
    *  qgini: Operation Point: Reactive Power in Mvar
    *  phiini: Operation Point: Angle in deg
    *  usetp: Operation Point: Voltage Setpoint in p.u.
    ********************************************************************************
    '''

    for i in range(len(external)):
        ID = external['ID'][i]

        if 'phiini' in external.columns.values:
            va = external['phiini'][i]
            vm = external['usetp'][i]
        else:
            va = 0
            vm = 1

        buses = terminals_dict[ID]  # array with the ID of the connection Buses
        bus1 = buses_dict[buses[0]]

        # apply the slack values to the buses structure if the element is marked as slack
        if external['bustp'].values[i] == b'SL':
            # create the slack entry on buses
            BUSES[bus1, bd.BUS_TYPE] = 3
            BUSES[bus1, bd.VA] = va
            BUSES[bus1, bd.VM] = vm

            # create the slack entry on generators (add the slack generator)
            gen_ = gen_line.copy()
            gen_[gd.GEN_BUS] = bus1
            gen_[gd.MBASE] = baseMVA
            gen_[gd.VG] = vm
            gen_[gd.GEN_STATUS] = 1
            gen_[gd.PG] += external['pgini'].values[i]

            GEN.append(gen_)
            GEN_NAMES.append(external['loc_name'][i])

        elif external['bustp'].values[i] == b'PV':
            # mark the bus as pv
            BUSES[bus1, bd.BUS_TYPE] = 2
            BUSES[bus1, bd.VA] = 0.0
            BUSES[bus1, bd.VM] = vm
            # add the PV entry on generators
            gen_ = gen_line.copy()
            gen_[gd.GEN_BUS] = bus1
            gen_[gd.MBASE] = baseMVA
            gen_[gd.VG] = vm
            gen_[gd.GEN_STATUS] = 1
            gen_[gd.PG] += external['pgini'].values[i]

            GEN.append(gen_)
            GEN_NAMES.append(external['loc_name'][i])

        elif external['bustp'].values[i] == b'PQ':
            # mark the bus as pv
            BUSES[bus1, bd.BUS_TYPE] = 1
            BUSES[bus1, bd.VA] = va
            BUSES[bus1, bd.VM] = vm
            BUSES[bus1, bd.PD] += external['pgini'].values[i]
            BUSES[bus1, bd.QD] += external['qgini'].values[i]

    ####################################################################################################################
    # Lines (branches)
    ####################################################################################################################
    print('Parsing lines')

    if lines_types.__len__() > 0:
        lines_ID = lines['ID'].values
        lines_type_id = lines['typ_id'].values
        line_types_ID = lines_types['ID'].values
        lines_lenght = lines['dline'].values

        if 'outserv' in lines.keys():
            lines_enables = lines['outserv']
        else:
            lines_enables = np.ones(len(lines_ID))

        lines_R = lines_types['rline'].values
        lines_L = lines_types['xline'].values
        lines_C = lines_types['cline'].values
        lines_rate = lines_types['sline'].values
        lines_voltage = lines_types['uline'].values
        for i in range(len(lines)):
            line_ = branch_line.copy()

            ID = lines_ID[i]
            ID_Type = lines_type_id[i]
            type_idx = np.where(line_types_ID == ID_Type)[0][0]

            buses = terminals_dict[ID]  # array with the ID of the connection Buses
            bus1 = buses_dict[buses[0]]
            bus2 = buses_dict[buses[1]]

            status = lines_enables[i]

            # impedances
            lenght = np.double(lines_lenght[i])
            R = np.double(lines_R[type_idx]) * lenght  # Ohm
            L = np.double(lines_L[type_idx]) * lenght  # Ohm
            C = np.double(lines_C[type_idx]) * lenght * w * 1e-6  # S (siemens)

            # pass impedance to per unit
            vbase = np.double(lines_voltage[type_idx])  # kV
            zbase = vbase**2 / baseMVA  # Ohm
            ybase = 1.0 / zbase  # S
            r = R / zbase  # pu
            l = L / zbase  # pu
            c = C / ybase  # pu

            # rated power
            Irated = np.double(lines_rate[type_idx])  # kA
            Smax = Irated * vbase  # MVA

            # put all in the correct column
            line_[brd.F_BUS] = bus1
            line_[brd.T_BUS] = bus2
            line_[brd.BR_R] = r
            line_[brd.BR_X] = l
            line_[brd.BR_B] = c
            line_[brd.RATE_A] = Smax
            line_[brd.BR_STATUS] = status
            BRANCHES.append(line_)

            name_ = lines['loc_name'][i]  # line_Name
            BRANCH_NAMES.append(name_)

            # add edge to graph
            g.add_edge(bus1, bus2)
    else:
        warn('Line types are empty')

    ####################################################################################################################
    # Transformers (Branches)
    ####################################################################################################################
    print('Parsing transformers')

    '''
    ********************************************************************************
    *  2-Winding Transformer
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypTr2
    *  outserv: Out of Service
    *  nntap: Tap Changer 1: Tap Position
    *  sernum: Serial Number
    *  constr: Year of Construction
    *  chr_name: Characteristic Name
    ********************************************************************************
    '''

    if len(transformers_types) > 0:
        type_ID = transformers_types['ID'].values
        HV_nominal_voltage = transformers_types['utrn_h'].values
        LV_nominal_voltage = transformers_types['utrn_l'].values
        Nominal_power = transformers_types['strn'].values
        Copper_losses = transformers_types['pcutr'].values
        Iron_losses = transformers_types['pfe'].values
        No_load_current = transformers_types['curmg'].values
        Short_circuit_voltage = transformers_types['uktr'].values
        # GR_hv1 = transformers_types['ID']
        # GX_hv1 = transformers_types['ID']
        for i in range(len(transformers)):

            line_ = branch_line.copy()

            ID = transformers['ID'][i]
            ID_Type = transformers['typ_id'][i]

            if ID_Type in type_ID:
                type_idx = np.where(type_ID == ID_Type)[0][0]
                buses = terminals_dict[ID]  # array with the ID of the connection Buses
                bus1 = buses_dict[buses[0]]
                bus2 = buses_dict[buses[1]]

                Smax = Nominal_power[type_idx]

                # Uhv, Ulv, Sn, Pcu, Pfe, I0, Usc
                Zs, Zsh = get_transformer_impedances(Uhv=HV_nominal_voltage[type_idx],
                                                     Ulv=LV_nominal_voltage[type_idx],
                                                     Sn=Smax,
                                                     Pcu=Copper_losses[type_idx],
                                                     Pfe=Iron_losses[type_idx],
                                                     I0=No_load_current[type_idx],
                                                     Usc=Short_circuit_voltage[type_idx],
                                                     GR_hv1=0.5,
                                                     GX_hv1=0.5)

                status = 1 - transformers['outserv'][i]

                # put all in the correct column
                line_[brd.F_BUS] = bus1
                line_[brd.T_BUS] = bus2
                line_[brd.BR_R] = Zs.real
                line_[brd.BR_X] = Zs.imag
                line_[brd.BR_B] = Zsh.imag
                line_[brd.RATE_A] = Smax
                line_[brd.BR_STATUS] = status
                BRANCHES.append(line_)

                name_ = transformers['loc_name'][i]  # line_Name
                BRANCH_NAMES.append(name_)

                # add edge to graph
                g.add_edge(bus1, bus2)
            else:
                warn('Transformer type not found!')
        else:
            warn('Transformer types are empty')

    ####################################################################################################################
    # Loads (nodes)
    ####################################################################################################################
    print('Parsing Loads')
    if len(loads) > 0:
        loads_ID = loads['ID']
        loads_P = loads['plini']
        loads_Q = loads['qlini']
        for i in range(len(loads)):
            ID = loads_ID[i]
            bus_idx = buses_dict[(terminals_dict[ID][0])]

            p = -loads_P[i]  # in MW
            q = -loads_Q[i]  # in MVA

            BUSES[bus_idx, 2] += p
            BUSES[bus_idx, 3] += q
    else:
        warn('There are no loads')

    ####################################################################################################################
    # Static generators (Gen)
    ####################################################################################################################
    '''
    ********************************************************************************
    *  Static Generator
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  bus1: Terminal in StaCubic
    *  outserv: Out of Service
    *  sgn: Ratings: Nominal Apparent Power in MVA
    *  cosn: Ratings: Power Factor
    *  ngnum: Number of: parallel Machines
    *  pgini: Dispatch: Active Power in MW
    *  qgini: Dispatch: Reactive Power in Mvar
    *  av_mode: Local Controller
    *  ip_ctrl: Reference Machine
    ********************************************************************************
    '''
    for i in range(len(static_generators)):
        ID = static_generators['ID'][i]
        buses = terminals_dict[ID]  # array with the ID of the connection Buses
        bus1 = buses_dict[buses[0]]
        mode = static_generators['av_mode'][i]
        # declare the generator array
        gen_ = gen_line.copy()
        gen_[gd.GEN_BUS] = bus1
        gen_[gd.GEN_STATUS] = not static_generators['outserv'][i]

        num_machines = static_generators['ngnum'][i]

        gen_[gd.PG] = static_generators['pgini'][i] * num_machines
        gen_[gd.QG] = static_generators['qgini'][i] * num_machines
        gen_[gd.VG] = 1.0  # static_generators['outserv'][i]
        gen_[gd.MBASE] = static_generators['sgn'][i]

        GEN.append(gen_)

        name_ = static_generators['loc_name'][i]
        GEN_NAMES.append(name_)

    ####################################################################################################################
    # make data-frames out of data
    ####################################################################################################################

    BRANCH_NAMES = array(BRANCH_NAMES, dtype=np.str)
    BUS_NAMES = array(BUS_NAMES, dtype=np.str)
    GEN_NAMES = array(GEN_NAMES, dtype=np.str)

    if len(BRANCHES) > 0:
        BRANCHES = df(data=np.array(BRANCHES, dtype=np.object), columns=brd.branch_headers, index=BRANCH_NAMES)
    else:
        BRANCHES = df(data=np.zeros((0, len(brd.branch_headers))), columns=brd.branch_headers)

    if len(BUSES) > 0:
        BUSES = df(data=np.array(BUSES, dtype=np.object), columns=bd.bus_headers, index=BUS_NAMES)
    else:
        BUSES = df(data=np.zeros((0, len(bd.bus_headers))), columns=bd.bus_headers)

    if len(GEN) > 0:
        GEN = df(data=np.array(GEN, dtype=np.object), columns=gd.gen_headers, index=GEN_NAMES)
    else:
        GEN = df(data=np.zeros((0, len(gd.gen_headers))), columns=gd.gen_headers)

    print('Done!')

    return baseMVA, BUSES, BRANCHES, GEN, g, gpos, BUS_NAMES, BRANCH_NAMES, GEN_NAMES


if __name__ == "__main__":

    fname = 'Bogfinkeveg.dgs'
    # fname = 'PLATOS grid 3.dgs'
    # fname = 'Example4.dgs'
    baseMVA, BUSES, BRANCHES, GEN, graph, gpos, BUS_NAMES, BRANCH_NAMES, GEN_NAMES = read_DGS(fname)

    print(BUS_NAMES, '\n')
    print(BUSES)

    print(BRANCH_NAMES, '\n')
    print(BRANCHES)

    print(GEN_NAMES, '\n')
    print(GEN)

    print(graph)
    print('Plotting grid...')
    nx.draw(graph, pos=gpos)

    from matplotlib import pyplot as plt
    plt.show()

    print('done')


