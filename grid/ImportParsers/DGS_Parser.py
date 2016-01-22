# -*- coding: utf-8 -*-
"""
Created on Fri Oct 02 14:45:18 2015

@author: sanpen
"""
from numpy import array
import numpy as np
import math
from pandas import DataFrame as df
import networkx as nx

bus_headers = ["bus_i",
               "type",
               "Pd",
               "Qd",
               "Gs",
               "Bs",
               "area",
               "Vm",
               "Va",
               "baseKV",
               "zone",
               "Vmax",
               "Vmin",
               "LaM_P",
               "LaM_Q",
               "Mu_Vmax",
               "Mu_Vmin",
               "Bus_X",
               "Bus_Y",
               "BUS_NAME"]

branch_headers = ["fbus",  # 0
                  "tbus",
                  "r",
                  "x",
                  "b",
                  "rateA",
                  "rateB",
                  "rateC",
                  "ratio",
                  "angle",  # 9
                  "status",
                  "angmin",
                  "angmax",
                  "Pf",
                  "Qf",
                  "Pt",
                  "Qt",
                  "Mu_Sf",
                  "Mu_St",
                  "Mu_AngMin",  # 19
                  "Mu_AngMax",
                  "Current",
                  "Loading",
                  "Original_index"]
                  
gen_headers = ["bus",
               "Pg",
               "Qg",
               "Qmax",
               "Qmin",
               "Vg",
               "mBase",
               "status",
               "Pmax",
               "Pmin",
               "Pc1",
               "Pc2",
               "Qc1min",
               "Qc1max",
               "Qc2min",
               "Qc2max",
               "ramp_agc",
               "ramp_10",
               "ramp_30",
               "ramp_q",
               "apf",
               "MU_PMAX",
               "MU_PMIN",
               "MU_QMAX",
               "MU_QMIN"]

def get_transformer_impedances(HV_nominal_voltage, LV_nominal_voltage, 
                               Nominal_power, Copper_losses, Iron_losses,
                               No_load_current, Short_circuit_voltage, 
                               GR_hv1, GX_hv1):

        Uhv = HV_nominal_voltage

        Ulv = LV_nominal_voltage

        Sn = Nominal_power

        Pcu = Copper_losses

        Pfe = Iron_losses

        I0 = No_load_current

        Usc = Short_circuit_voltage

        # Nominal impedance HV (Ohm)
        Zn_hv = Uhv * Uhv / Sn

        # Nominal impedance LV (Ohm)
        Zn_lv = Ulv * Ulv / Sn

        # Short circuit impedance (p.u.)
        zsc = Usc / 100

        # Short circuit resistance (p.u.)
        rsc = (Pcu / 1000) / Sn

        # Short circuit reactance (p.u.)
        xsc = np.sqrt(zsc * zsc - rsc * rsc)

        # HV resistance (p.u.)
        rcu_hv = rsc * GR_hv1

        # LV resistance (p.u.)
        rcu_lv = rsc * (1 - GR_hv1)

        # HV shunt reactance (p.u.)
        xs_hv = xsc * GX_hv1

        # LV shunt reactance (p.u.)
        xs_lv = xsc * (1 - GX_hv1)

        #Shunt resistance (p.u.)
        rfe = Sn / (Pfe / 1000)

        # Magnetization impedance (p.u.)
        zm = 1 / (I0 / 100)

        # Magnetization reactance (p.u.)
        xm = 0.0
        if rfe > zm:
            xm = 1 / sqrt(1 / (zm * zm) - 1 / (rfe * rfe))
        else:
            xm = 0  # the square root cannot be computed

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

    # store tables for easy refference

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
        transformers = np.zeros((0,20))



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
        transformers_types = np.zeros((0,20))

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
        buses = np.zeros((0,20))


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
        cubicles = np.zeros((0,20))

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
        loads = np.zeros((0,20))



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
        external = np.zeros((0,20))


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
        grid = np.zeros((0,20))



    '''
    ###############################################################################
    '''
    if "ElmGenstat" in data.keys():
        static_generators = data["ElmGenstat"]
    else:
        static_generators = np.zeros((0,20))


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
        synchronous_machine = np.zeros((0,20))


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
        synchronous_machine_type = np.zeros((0,20))


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
        asynchronous_machine = np.zeros((0,20))



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
        asynchronous_machine_type = np.zeros((0,20))


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
        shunts = np.zeros((0,20))


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
        switches = np.zeros((0,20))



    # put the tables that connect to a terminal in a list
    classes = [lines, transformers, loads, external, static_generators, shunts]

    #put the brach classes in a list
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

    '''
    ###############################################################################
    BUSES
    ###############################################################################

    BUS_I       = 0    # bus number (1 to 29997)
    BUS_TYPE    = 1    # bus type
    PD          = 2    # Pd, real power demand (MW)
    QD          = 3    # Qd, reactive power demand (MVAr)
    GS          = 4    # Gs, shunt conductance (MW at V = 1.0 p.u.)
    BS          = 5    # Bs, shunt susceptance (MVAr at V = 1.0 p.u.)
    BUS_AREA    = 6    # area number, 1-100
    VM          = 7    # Vm, voltage magnitude (p.u.)
    VA          = 8    # Va, voltage angle (degrees)
    BASE_KV     = 9    # baseKV, base voltage (kV)
    ZONE        = 10   # zone, loss zone (1-999)
    VMAX        = 11   # maxVm, maximum voltage magnitude (p.u.)
    VMIN        = 12   # minVm, minimum voltage magnitude (p.u.)

    # included in opf solution, not necessarily in input
    # assume objective function has units, u
    LAM_P       = 13   # Lagrange multiplier on real power mismatch (u/MW)
    LAM_Q       = 14   # Lagrange multiplier on reactive power mismatch (u/MVAr)
    MU_VMAX     = 15   # Kuhn-Tucker multiplier on upper voltage limit (u/p.u.)
    MU_VMIN     = 16   # Kuhn-Tucker multiplier on lower voltage limit (u/p.u.)

    # bus location
    BUS_X = 17  # X position for the graphical representation
    BUS_Y = 18  # Y position for the graphical representation
    BUS_NAME = 19

    ###############################################################################
    BRANCHES
    ###############################################################################

    F_BUS       = 0    # f, from bus number
    T_BUS       = 1    # t, to bus number
    BR_R        = 2    # r, resistance (p.u.)
    BR_X        = 3    # x, reactance (p.u.)
    BR_B        = 4    # b, total line charging susceptance (p.u.)
    RATE_A      = 5    # rateA, MVA rating A (long term rating)
    RATE_B      = 6    # rateB, MVA rating B (short term rating)
    RATE_C      = 7    # rateC, MVA rating C (emergency rating)
    TAP         = 8    # ratio, transformer off nominal turns ratio
    SHIFT       = 9    # angle, transformer phase shift angle (degrees)
    BR_STATUS   = 10   # initial branch status, 1 - in service, 0 - out of service
    ANGMIN      = 11   # minimum angle difference, angle(Vf) - angle(Vt) (degrees)
    ANGMAX      = 12   # maximum angle difference, angle(Vf) - angle(Vt) (degrees)

    # included in power flow solution, not necessarily in input
    PF          = 13   # real power injected at "from" bus end (MW)
    QF          = 14   # reactive power injected at "from" bus end (MVAr)
    PT          = 15   # real power injected at "to" bus end (MW)
    QT          = 16   # reactive power injected at "to" bus end (MVAr)

    # included in opf solution, not necessarily in input
    # assume objective function has units, u
    MU_SF       = 17   # Kuhn-Tucker multiplier on MVA limit at "from" bus (u/MVA)
    MU_ST       = 18   # Kuhn-Tucker multiplier on MVA limit at "to" bus (u/MVA)
    MU_ANGMIN   = 19   # Kuhn-Tucker multiplier lower angle difference limit
    MU_ANGMAX   = 20   # Kuhn-Tucker multiplier upper angle difference limit

    BR_CURRENT = 21  # Branch current in kA
    LOADING = 22  # Branch loading factor
    O_INDEX = 23  # Original index

    ###############################################################################
    GEN
    ###############################################################################

    GEN_BUS     = 0    # bus number
    PG          = 1    # Pg, real power output (MW)
    QG          = 2    # Qg, reactive power output (MVAr)
    QMAX        = 3    # Qmax, maximum reactive power output at Pmin (MVAr)
    QMIN        = 4    # Qmin, minimum reactive power output at Pmin (MVAr)
    VG          = 5    # Vg, voltage magnitude setpoint (p.u.)
    MBASE       = 6    # mBase, total MVA base of this machine, defaults to baseMVA
    GEN_STATUS  = 7    # status, 1 - machine in service, 0 - machine out of service
    PMAX        = 8    # Pmax, maximum real power output (MW)
    PMIN        = 9    # Pmin, minimum real power output (MW)
    PC1         = 10   # Pc1, lower real power output of PQ capability curve (MW)
    PC2         = 11   # Pc2, upper real power output of PQ capability curve (MW)
    QC1MIN      = 12   # Qc1min, minimum reactive power output at Pc1 (MVAr)
    QC1MAX      = 13   # Qc1max, maximum reactive power output at Pc1 (MVAr)
    QC2MIN      = 14   # Qc2min, minimum reactive power output at Pc2 (MVAr)
    QC2MAX      = 15   # Qc2max, maximum reactive power output at Pc2 (MVAr)
    RAMP_AGC    = 16   # ramp rate for load following/AGC (MW/min)
    RAMP_10     = 17   # ramp rate for 10 minute reserves (MW)
    RAMP_30     = 18   # ramp rate for 30 minute reserves (MW)
    RAMP_Q      = 19   # ramp rate for reactive power (2 sec timescale) (MVAr/min)
    APF         = 20   # area participation factor

    # included in opf solution, not necessarily in input
    # assume objective function has units, u
    MU_PMAX     = 21   # Kuhn-Tucker multiplier on upper Pg limit (u/MW)
    MU_PMIN     = 22   # Kuhn-Tucker multiplier on lower Pg limit (u/MW)
    MU_QMAX     = 23   # Kuhn-Tucker multiplier on upper Qg limit (u/MVAr)
    MU_QMIN     = 24   # Kuhn-Tucker multiplier on lower Qg limit (u/MVAr)
    '''

    baseMVA = 100
    frequency = grid['frnom'][0]
    w = 2.0 * math.pi * frequency

    BUSES = list()
    bus_line = np.zeros(20, dtype=np.object)

    BRANCHES = list()
    branch_line = np.zeros(24, dtype=np.object)

    GEN = list()
    gen_line = np.zeros(25, dtype=np.object)

    g = nx.graph.Graph()

    # terminals
    print('Parsing terminals')
    buses_dict = dict()
    gpos = dict()
    for i in range(len(buses)):
        ID = buses['ID'][i]
        x, y = pos_dict[ID]
        bus_ = bus_line.copy()
        bus_[0] = BUSES.__len__() +1  # ID
        bus_[7] = 1.0  # VM
        bus_[8] = 0.0  # VA
        bus_[9] = buses['uknom'][i]  # BaseKv
        bus_[11] = 1.05  # VMax
        bus_[12] = 0.95  # VMin
        bus_[17] = x
        bus_[18] = y
        bus_[19] = buses['loc_name'][i]  # BUS_Name
        BUSES.append(bus_)

        buses_dict[ID] = i
        gpos[i] = (x, y)

    BUSES = np.array(BUSES, dtype=np.object)

    # Branches
    print('Parsing lines')
    lines_ID = lines['ID']
    lines_type_id = lines['typ_id']
    line_types_ID = lines_types['ID']
    lines_lenght = lines['dline']

    if 'outserv' in lines.keys():
        lines_enables = lines['outserv']
    else:
        lines_enables = np.ones(len(lines_ID))

    lines_R = lines_types['rline']
    lines_L = lines_types['xline']
    lines_C = lines_types['cline']
    lines_rate = lines_types['sline']
    lines_voltage = lines_types['uline']
    for i in range(len(lines)):
        line_ = branch_line.copy()

        ID = lines_ID[i]
        ID_Type = lines_type_id[i]
        type_idx = np.where(line_types_ID == ID_Type)[0][0]

        buses = terminals_dict[ID]  # arry with the ID of the connection Buses
        bus1 = buses_dict[buses[0]]
        bus2 = buses_dict[buses[1]]

        status = lines_enables[i]

        # impedances
        lenght = np.double(lines_lenght[i])
        R = np.double(lines_R[type_idx]) * lenght  # Ohm
        L = np.double(lines_L[type_idx]) * lenght  # Ohm
        C = np.double(lines_C[type_idx]) * lenght * w *1e-6 # S

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
        line_[0] = bus1
        line_[1] = bus2
        line_[2] = r
        line_[3] = l
        line_[4] = c
        line_[5] = Smax
        line_[10] = status
        BRANCHES.append(line_)

        # add edge to graph
        g.add_edge(bus1, bus2)



    print('Parsing transformers')

    type_ID = transformers_types['ID']
    HV_nominal_voltage = transformers_types['utrn_h']
    LV_nominal_voltage = transformers_types['utrn_l']
    Nominal_power = transformers_types['strn']
    Copper_losses = transformers_types['pcutr']
    Iron_losses = transformers_types['pfe']
    No_load_current = transformers_types['curmg']
    Short_circuit_voltage = transformers_types['uktr']
    #GR_hv1 = transformers_types['ID']
    #GX_hv1 = transformers_types['ID']
    for i in range(len(transformers)):
        line_ = branch_line.copy()

        ID = transformers['ID'][i]
        ID_Type = transformers['typ_id'][i]
        type_idx = np.where(type_ID == ID_Type)[0][0]

        buses = terminals_dict[ID]  # arry with the ID of the connection Buses
        bus1 = buses_dict[buses[0]]
        bus2 = buses_dict[buses[1]]

        Smax = Nominal_power[type_idx]

        Zs, Zsh = get_transformer_impedances(HV_nominal_voltage=HV_nominal_voltage[type_idx],
                                             LV_nominal_voltage=LV_nominal_voltage[type_idx],
                                             Nominal_power=Smax,
                                             Copper_losses=Copper_losses[type_idx],
                                             Iron_losses=Iron_losses[type_idx],
                                             No_load_current=No_load_current[type_idx],
                                             Short_circuit_voltage=Short_circuit_voltage[type_idx],
                                             GR_hv1=0.5,
                                             GX_hv1=0.5)

        status = 1 - transformers['outserv'][i]

        # put all in the correct column
        line_[0] = bus1
        line_[1] = bus2
        line_[2] = Zs.real
        line_[3] = Zs.imag
        line_[4] = Zsh.imag
        line_[5] = Smax
        line_[10] = status
        BRANCHES.append(line_)

        # add edge to graph
        g.add_edge(bus1, bus2)



    print('Parsing Loads')
    loads_ID = loads['ID']
    loads_P = loads['plini']
    loads_Q = loads['qlini']
    for i in range(len(loads)):
        ID = loads_ID[i]
        bus_idx = buses_dict[(terminals_dict[ID][0])]

        p = loads_P[i]  # in MW
        q = loads_Q[i]  # in MVA

        BUSES[bus_idx, 2] += p
        BUSES[bus_idx, 3] += q

    # make data-frames out of data
    BRANCHES = df(data=np.array(BRANCHES, dtype=np.object), columns=branch_headers)
    BUSES = df(data=np.array(BUSES, dtype=np.object), columns=bus_headers)
    GEN = df(data=np.array(GEN, dtype=np.object), columns=gen_headers)

    print('Plotting grid...')
    nx.draw(g, pos=gpos)

    from matplotlib import pyplot as plt
    plt.show()

    print('Done!')

    return BUSES, BRANCHES, GEN, g


if __name__ == "__main__":
    fname = "Bogfinkeveg.dgs"
    read_DGS(fname)