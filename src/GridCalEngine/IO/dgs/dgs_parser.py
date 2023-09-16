# -*- coding: utf-8 -*-
"""
GridCal
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
"""

from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Core.Devices as dev
import math
import numpy as np
from numpy import array
from pandas import DataFrame as df
from warnings import warn


# def get_transformer_impedances(Uhv, Ulv, Sn, Pcu, Pfe, I0, Usc, GR_hv1=0.5, GX_hv1=0.5):
#     """
#     Get the transformer series and shunt equivalent impedances from the short circuit values
#     @param Uhv: Nominal voltage at the high side (kV)
#     @param Ulv: Nominal voltage at the low side (kV)
#     @param Sn: Nominal power (MVA)
#     @param Pcu: Copper losses (kW) (Losses due to the Joule effect)
#     @param Pfe: Iron-losses (kW)  (Losses in the magnetic circuit)
#     @param I0: No-load current (%)
#     @param Usc: Short-circuit voltage (%)
#     @param GR_hv1: Resistive short circuit contribution to the HV side. It is a value from 0 to 1.
#     @param GX_hv1: Reactive short circuit contribution to the HV side. It is a value from 0 to 1.
#     @return:
#     """
#
#     # Nominal impedance HV (Ohm)
#     Zn_hv = Uhv * Uhv / Sn
#
#     # Nominal impedance LV (Ohm)
#     Zn_lv = Ulv * Ulv / Sn
#
#     # Short circuit impedance (p.u.)
#     zsc = Usc / 100.0
#
#     # Short circuit resistance (p.u.)
#     rsc = (Pcu / 1000.0) / Sn
#
#     # Short circuit reactance (p.u.)
#     xsc = np.sqrt(zsc * zsc - rsc * rsc)
#
#     # HV resistance (p.u.)
#     rcu_hv = rsc * GR_hv1
#
#     # LV resistance (p.u.)
#     rcu_lv = rsc * (1.0 - GR_hv1)
#
#     # HV shunt reactance (p.u.)
#     xs_hv = xsc * GX_hv1
#
#     # LV shunt reactance (p.u.)
#     xs_lv = xsc * (1.0 - GX_hv1)
#
#     # Shunt resistance (p.u.)
#     if Pfe > 0:
#         rfe = Sn / (Pfe / 1000.0)
#     else:
#         rfe = 1e-20
#
#     # Magnetization impedance (p.u.)
#     if I0 > 0:
#         zm = 1.0 / (I0 / 100.0)
#     else:
#         zm = 1e-20
#
#     # Magnetization reactance (p.u.)
#     xm = 0.0
#     if rfe > zm:
#         xm = 1.0 / np.sqrt(1.0 / (zm * zm) - 1.0 / (rfe * rfe))
#     else:
#         xm = 0.0  # the square root cannot be computed
#
#     # Calculated parameters in per unit
#     # leakage_impedance = rsc + 1j * xsc
#     # magnetizing_impedance = rfe + 1j * xm
#
#     leakage_impedance = (rcu_hv + rcu_lv) + 1j * (xs_hv + xs_lv)
#     magnetizing_impedance = rfe + 1j * xm
#
#     return leakage_impedance, magnetizing_impedance


def read_DGS(filename):
    """
    Read a DigSilent Power Factory .dgs file and return a dictionary with the data
    Args:
        filename: File name or path

    Returns: Dictionary of data where the keys are the object types and the values
             are the data of the objects of the key object type
    """
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

    current_type = None
    data_types = None
    header = None

    Headers = dict()
    # parse the file lines
    for line in lines:

        if line.startswith("$$"):
            line = line[2:]
            chnks = line.split(";")
            current_type = chnks[0]
            data[current_type] = list()
            # print(current_type)

            # analyze types
            data_types = list()
            header = list()
            for i in range(1, len(chnks)):
                token = chnks[i].split("(")
                name = token[0]
                tpe = token[1][:-1]
                data_types.append((name, types_dict[tpe[0]]))
                header.append(name)

            types_dict2[current_type] = data_types

            Headers[current_type] = header

        elif line.startswith("*"):
            pass

        elif line.startswith("  "):
            if current_type is not None:
                line = line.strip()
                chnks = line.split(";")
                chnks = ["0" if x == "" else x for x in chnks]
                data[current_type].append(array(tuple(chnks)))

    # format keys
    for key in data.keys():
        # print("Converting " + str(key))
        table = array([tuple(x) for x in data[key]], dtype=types_dict2[key])
        table = array([list(x) for x in table], dtype=np.object)
        header = Headers[key]
        data[key] = df(data=table, columns=header)

    # positions dictionary
    obj_id = data['IntGrf']['pDataObj'].values
    x_vec = data['IntGrf']['rCenterX'].values
    y_vec = data['IntGrf']['rCenterY'].values
    pos_dict = dict()
    for i in range(len(obj_id)):
        pos_dict[obj_id[i]] = (x_vec[i], y_vec[i])

    return data, pos_dict


def data_to_grid_object(data, pos_dict, codification="utf-8") -> MultiCircuit:
    """
    Turns the read data dictionary into a GridCal MultiCircuit object
    Args:
        data: Dictionary of data read from a DGS file
        pos_dict: Dictionary of objects and their positions read from a DGS file
    Returns: GridCal MultiCircuit object
    """
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
    lines = data.get("ElmLne", np.zeros((0, 20)))

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
        lines_types = np.zeros((0, 20))

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

        ###############################################################################
        # Post process the data
        ###############################################################################

    # put the tables that connect to a terminal in a list
    classes = [lines, transformers, loads, external, static_generators, shunts,
               synchronous_machine, asynchronous_machine]

    # construct the terminals dictionary
    '''
    $$StaCubic;ID(a:40);loc_name(a:40);fold_id(p);chr_name(a:20);obj_bus(i);obj_id(p)
    ********************************************************************************
    *  Cubicle
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  chr_name: Characteristic Name
    *  obj_bus: Bus Index
    *  obj_id: Connected with in Elm*
    ********************************************************************************
    '''
    terminals_dict = dict()  # dictionary to store the terminals ID associated with an object ID
    cub_obj_idx = cubicles['obj_id'].values
    cub_term_idx = cubicles['fold_id'].values

    # for i, elm_id in enumerate(cub_obj_idx):
    #     elm_idx = cub_term_idx[i]
    #     terminals_dict[elm_id] = elm_idx

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

    circuit = MultiCircuit()

    ####################################################################################################################
    # Terminals (nodes)
    ####################################################################################################################
    '''
    ********************************************************************************
    *  Terminal
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypBar
    *  iUsage: Usage:Busbar:Junction Node:Internal Node
    *  uknom: Nominal Voltage: Line-Line in kV
    *  chr_name: Characteristic Name
    *  outserv: Out of Service
    ********************************************************************************
    '''
    # print('Parsing terminals')
    buses_dict = dict()
    for i in range(len(buses)):
        ID = buses['ID'][i]
        x, y = pos_dict[ID]
        buses_dict[ID] = i
        bus_name = buses['loc_name'][i].decode(codification)  # BUS_Name
        vnom = buses['uknom'][i]
        bus = dev.Bus(name=bus_name, vnom=vnom, vmin=0.9, vmax=1.1, xpos=x, ypos=-y, active=True)
        circuit.add_bus(bus)

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
        bus1 = buses_dict[buses[0]]  # index of the bus

        bus_obj = circuit.buses[bus1]

        # apply the slack values to the buses structure if the element is marked as slack
        if external['bustp'].values[i] == b'SL':
            # create the slack entry on buses
            bus_obj.is_slack = True

            # BUSES[bus1, bd.BUS_TYPE] = 3
            # BUSES[bus1, bd.VA] = va
            # BUSES[bus1, bd.VM] = vm
            #
            # # create the slack entry on generators (add the slack generator)
            # gen_ = gen_line.copy()
            # gen_[gd.GEN_BUS] = bus1
            # gen_[gd.MBASE] = baseMVA
            # gen_[gd.VG] = vm
            # gen_[gd.GEN_STATUS] = 1
            # gen_[gd.PG] += external['pgini'].values[i]
            #
            # GEN.append(gen_)
            # GEN_NAMES.append(external['loc_name'][i])

        elif external['bustp'].values[i] == b'PV':

            if 'pgini' in external.columns.values:
                p = external['pgini'].values[i]
            else:
                p = 0

            # add a generator to the bus
            gen = dev.Generator(name=external['loc_name'][i].decode(codification),
                                P=p,
                                vset=vm, Qmin=-9999, Qmax=9999, Snom=9999,
                                P_prof=None, vset_prof=None)
            circuit.add_generator(bus_obj, gen)

            # # mark the bus as pv
            # BUSES[bus1, bd.BUS_TYPE] = 2
            # BUSES[bus1, bd.VA] = 0.0
            # BUSES[bus1, bd.VM] = vm
            # # add the PV entry on generators
            # gen_ = gen_line.copy()
            # gen_[gd.GEN_BUS] = bus1
            # gen_[gd.MBASE] = baseMVA
            # gen_[gd.VG] = vm
            # gen_[gd.GEN_STATUS] = 1
            # gen_[gd.PG] += external['pgini'].values[i]
            #
            # GEN.append(gen_)
            # GEN_NAMES.append(external['loc_name'][i])

        elif external['bustp'].values[i] == b'PQ':
            # Add a load to the bus
            load = dev.Load(name=external['loc_name'][i].decode(codification),
                            P=external['pgini'].values[i],
                            Q=external['qgini'].values[i])
            circuit.add_load(bus_obj, load)

            # BUSES[bus1, bd.BUS_TYPE] = 1
            # BUSES[bus1, bd.VA] = va
            # BUSES[bus1, bd.VM] = vm
            # BUSES[bus1, bd.PD] += external['pgini'].values[i]
            # BUSES[bus1, bd.QD] += external['qgini'].values[i]

    ####################################################################################################################
    # Lines (Branches)
    ####################################################################################################################
    # print('Parsing lines')

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
            # line_ = branch_line.copy()

            ID = lines_ID[i]
            ID_Type = lines_type_id[i]
            type_idx = np.where(line_types_ID == ID_Type)[0][0]

            buses = terminals_dict[ID]  # array with the ID of the connection Buses
            bus1 = buses_dict[buses[0]]
            bus2 = buses_dict[buses[1]]

            bus_from = circuit.buses[bus1]
            bus_to = circuit.buses[bus2]

            status = lines_enables[i]

            # impedances
            lenght = np.double(lines_lenght[i])
            R = np.double(lines_R[type_idx]) * lenght  # Ohm
            L = np.double(lines_L[type_idx]) * lenght  # Ohm
            C = np.double(lines_C[type_idx]) * lenght * w * 1e-6  # S (siemens)

            # pass impedance to per unit
            vbase = np.double(lines_voltage[type_idx])  # kV
            zbase = vbase ** 2 / baseMVA  # Ohm
            ybase = 1.0 / zbase  # S
            r = R / zbase  # pu
            l = L / zbase  # pu
            b = C / ybase  # pu

            # rated power
            Irated = np.double(lines_rate[type_idx])  # kA
            Smax = Irated * vbase  # MVA

            line = dev.Branch(bus_from=bus_from, bus_to=bus_to,
                              name=lines['loc_name'][i].decode(codification),
                              r=r,
                              x=l,
                              g=1e-20,
                              b=b,
                              rate=Smax,
                              tap=1,
                              shift_angle=0,
                              active=status, mttf=0, mttr=0)

            circuit.add_branch(line)

            # # put all in the correct column
            # line_[brd.F_BUS] = bus1
            # line_[brd.T_BUS] = bus2
            # line_[brd.BR_R] = r
            # line_[brd.BR_X] = l
            # line_[brd.BR_B] = c
            # line_[brd.RATE_A] = Smax
            # line_[brd.BR_STATUS] = status
            # BRANCHES.append(line_)
            #
            # name_ = lines['loc_name'][i]  # line_Name
            # BRANCH_NAMES.append(name_)
            #
            # # add edge to graph
            # g.add_edge(bus1, bus2)
    else:
        warn('Line types are empty')

    ####################################################################################################################
    # Transformers (Branches)
    ####################################################################################################################
    # print('Parsing transformers')

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
        '''
        ********************************************************************************
        *  2-Winding Transformer Type
        *
        *  ID: Unique identifier for DGS file
        *  loc_name: Name
        *  fold_id: In Folder
        *  strn: Rated Power in MVA
        *  frnom: Nominal Frequency in Hz
        *  utrn_h: Rated Voltage: HV-Side in kV
        *  utrn_l: Rated Voltage: LV-Side in kV
        *  uktr: Positive Sequence Impedance: Short-Circuit Voltage uk in %
        *  pcutr: Positive Sequence Impedance: Copper Losses in kW
        *  uk0tr: Zero Sequence Impedance: Short-Circuit Voltage uk0 in %
        *  ur0tr: Zero Sequence Impedance: SHC-Voltage (Re(uk0)) uk0r in %
        *  tr2cn_h: Vector Group: HV-Side:Y :YN:Z :ZN:D
        *  tr2cn_l: Vector Group: LV-Side:Y :YN:Z :ZN:D
        *  nt2ag: Vector Group: Phase Shift in *30deg
        *  curmg: Magnetizing Impedance: No Load Current in %
        *  pfe: Magnetizing Impedance: No Load Losses in kW
        *  zx0hl_n: Zero Sequence Magnetizing Impedance: Mag. Impedance/uk0
        *  tap_side: Tap Changer 1: at Side:HV:LV
        *  dutap: Tap Changer 1: Additional Voltage per Tap in %
        *  phitr: Tap Changer 1: Phase of du in deg
        *  nntap0: Tap Changer 1: Neutral Position
        *  ntpmn: Tap Changer 1: Minimum Position
        *  ntpmx: Tap Changer 1: Maximum Position
        *  manuf: Manufacturer
        *  chr_name: Characteristic Name
        ********************************************************************************
        '''
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

            # line_ = branch_line.copy()

            ID = transformers['ID'][i]
            ID_Type = transformers['typ_id'][i]

            if ID_Type in type_ID:
                type_idx = np.where(type_ID == ID_Type)[0][0]
                buses = terminals_dict[ID]  # array with the ID of the connection Buses
                bus1 = buses_dict[buses[0]]
                bus2 = buses_dict[buses[1]]

                bus_from = circuit.buses[bus1]
                bus_to = circuit.buses[bus2]

                Smax = Nominal_power[type_idx]

                # Uhv, Ulv, Sn, Pcu, Pfe, I0, Usc
                tpe = dev.TransformerType(hv_nominal_voltage=HV_nominal_voltage[type_idx],
                                          lv_nominal_voltage=LV_nominal_voltage[type_idx],
                                          nominal_power=Smax,
                                          copper_losses=Copper_losses[type_idx],
                                          iron_losses=Iron_losses[type_idx],
                                          no_load_current=No_load_current[type_idx],
                                          short_circuit_voltage=Short_circuit_voltage[type_idx],
                                          gr_hv1=0.5,
                                          gx_hv1=0.5)

                Zs, Zsh = tpe.get_impedances(VH=HV_nominal_voltage[type_idx],
                                             VL=LV_nominal_voltage[type_idx],
                                             Sbase=baseMVA)

                if Zsh != 0:
                    Ysh = 1.0 / Zsh
                else:
                    Ysh = 0j

                status = 1 - transformers['outserv'][i]

                trafo = dev.Branch(bus_from=bus_from,
                                   bus_to=bus_to,
                                   name=transformers['loc_name'][i].decode(codification),
                                   r=Zs.real,
                                   x=Zs.imag,
                                   g=Ysh.real,
                                   b=Ysh.imag,
                                   rate=Smax,
                                   tap=1.0,
                                   shift_angle=0.0,
                                   active=status,
                                   mttf=0,
                                   mttr=0,
                                   branch_type=dev.BranchType.Transformer)

                circuit.add_branch(trafo)

            else:
                warn('Transformer type not found!')
    else:
        warn('Transformer types are empty')

    ####################################################################################################################
    # Loads (nodes)
    ####################################################################################################################
    '''
    ********************************************************************************
    *  General Load
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypLod,TypLodind
    *  chr_name: Characteristic Name
    *  plini: Operating Point: Active Power in MW
    *  qlini: Operating Point: Reactive Power in Mvar
    *  scale0: Operating Point: Scaling Factor
    ********************************************************************************
    '''
    # print('Parsing Loads')
    if len(loads) > 0:
        loads_ID = loads['ID']
        loads_P = loads['plini']
        loads_Q = loads['qlini']
        scale = loads['scale0']
        for i in range(len(loads)):
            ID = loads_ID[i]
            bus_idx = buses_dict[(terminals_dict[ID][0])]
            bus_obj = circuit.buses[bus_idx]
            p = loads_P[i] * scale[i]  # in MW
            q = loads_Q[i] * scale[i]  # in MVA

            load = dev.Load(name=loads['loc_name'][i].decode(codification),
                            P=p,
                            Q=q)

            circuit.add_load(bus_obj, load)

            # BUSES[elm_idx, 2] += p
            # BUSES[elm_idx, 3] += q
    else:
        warn('There are no loads')

    ####################################################################################################################
    # Shunts
    ####################################################################################################################
    '''
    ********************************************************************************
    *  Shunt/Filter
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  chr_name: Characteristic Name
    *  shtype: Shunt Type
    *  ushnm: Nominal Voltage in kV
    *  qcapn: Design Parameter (per Step): Rated Reactive Power, C in Mvar
    *  ncapx: Controller: Max. No. of Steps
    *  ncapa: Controller: Act.No. of Step
    *  outserv: Out of Service
    ********************************************************************************
    '''
    for i in range(len(shunts)):
        ID = shunts['ID'][i]
        buses = terminals_dict[ID]  # array with the ID of the connection Buses
        bus1 = buses_dict[buses[0]]
        bus_obj = circuit.buses[bus1]
        name = shunts['loc_name'][i].decode(codification)

        if 'qcapn' in shunts.columns.values:
            b = shunts['ushnm'][i] / shunts['qcapn'][i]
        elif 'qtotn' in shunts.columns.values:
            b = shunts['ushnm'][i] / shunts['qtotn'][i]
        else:
            b = 1e-20

        shunt = dev.Shunt(name=name, B=b)
        circuit.add_shunt(bus_obj, shunt)

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
        bus_obj = circuit.buses[bus1]
        mode = static_generators['av_mode'][i]
        num_machines = static_generators['ngnum'][i]

        gen = dev.StaticGenerator(name=static_generators['loc_name'][i].decode(codification),
                                  P=static_generators['pgini'][i] * num_machines,
                                  Q=static_generators['qgini'][i] * num_machines)
        circuit.add_static_generator(bus_obj, gen)

    ####################################################################################################################
    # Synchronous Machine (Gen)
    ####################################################################################################################
    '''
    ********************************************************************************
    *  Synchronous Machine
    *
    *  ID: Unique identifier for DGS file
    *  loc_name: Name
    *  fold_id: In Folder
    *  typ_id: Type in TypSym
    *  ngnum: Number of: parallel Machines
    *  i_mot: Generator/Motor
    *  chr_name: Characteristic Name
    *  outserv: Out of Service
    *  pgini: Dispatch: Active Power in MW
    *  qgini: Dispatch: Reactive Power in Mvar
    *  usetp: Dispatch: Voltage in p.u.
    *  iv_mode: Mode of Local Voltage Controller
    *  q_min: Reactive Power Operational Limits: Min. in p.u.
    *  q_max: Reactive Power Operational Limits: Max. in p.u.
    ********************************************************************************
    '''
    for i in range(len(synchronous_machine)):
        ID = synchronous_machine['ID'][i]
        buses = terminals_dict[ID]  # array with the ID of the connection Buses
        bus1 = buses_dict[buses[0]]
        bus_obj = circuit.buses[bus1]
        num_machines = synchronous_machine['ngnum'][i]

        # Get the type element
        '''
        ********************************************************************************
        *  Synchronous Machine Type
        *
        *  ID: Unique identifier for DGS file
        *  loc_name: Name
        *  fold_id: In Folder
        *  sgn: Nominal Apparent Power in MVA
        *  ugn: Nominal Voltage in kV
        *  cosn: Power Factor
        *  xd: Synchronous Reactances: xd in p.u.
        *  xq: Synchronous Reactances: xq in p.u.
        *  xdsss: Subtransient Reactance: saturated value xd''sat in p.u.
        *  rstr: Stator Resistance: rstr in p.u.
        *  xdsat: For single fed short-circuit: Reciprocal of short-circuit ratio (xdsat) in p.u.
        *  satur: For single fed short-circuit: Machine Type IEC909/IEC60909
        ********************************************************************************
        '''
        typ = synchronous_machine_type[synchronous_machine_type.ID == synchronous_machine['typ_id'][i]]

        snom = typ['sgn'].values[0]
        vnom = synchronous_machine['usetp'][i]
        name = synchronous_machine['loc_name'][i].decode(codification)
        gen = dev.Generator(name=name,
                            P=synchronous_machine['pgini'][i] * num_machines,
                            vset=vnom,
                            Qmin=synchronous_machine['q_min'][i] * num_machines * snom,
                            Qmax=synchronous_machine['q_max'][i] * num_machines * snom,
                            Snom=snom,
                            P_prof=None,
                            vset_prof=None)
        circuit.add_generator(bus_obj, gen)

        # if synchronous_machine['pgini'][i] != 0:
        #     # gen = StaticGenerator(name=name, power=complex(0, synchronous_machine['pgini'][i]))
        #     gen = Generator(name=name, active_power=synchronous_machine['pgini'][i])
        #     circuit.add_static_generator(bus_obj, gen)

    return circuit


def dgs_to_circuit(filename) -> MultiCircuit:
    data, pos_dict = read_DGS(filename)

    return data_to_grid_object(data, pos_dict)
