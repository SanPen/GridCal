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
import numpy as np
from typing import Dict, List, Tuple, Union
from GridCalEngine.basic_structures import Logger
import GridCalEngine.Core.Devices as dev
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
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
from GridCalEngine.IO.base.base_circuit import BaseCircuit
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit


def get_gridcal_bus(psse_bus: RawBus,
                    area_dict: Dict[int, dev.Area],
                    zone_dict: Dict[int, dev.Zone],
                    logger: Logger) -> dev.Bus:
    """

    :return:
    """

    bustype = {1: dev.BusMode.PQ, 2: dev.BusMode.PV, 3: dev.BusMode.Slack, 4: dev.BusMode.PQ}

    if psse_bus.version >= 33:
        # create bus
        name = psse_bus.NAME.replace("'", "")
        bus = dev.Bus(name=name,
                      vnom=psse_bus.BASKV, code=str(psse_bus.I), vmin=psse_bus.EVLO, vmax=psse_bus.EVHI, xpos=0, ypos=0,
                      active=True,
                      area=area_dict[psse_bus.AREA],
                      zone=zone_dict[psse_bus.ZONE],
                      Vm0=psse_bus.VM,
                      Va0=np.deg2rad(psse_bus.VA))

    elif psse_bus.version == 32:
        # create bus
        name = psse_bus.NAME
        bus = dev.Bus(name=name, code=str(psse_bus.I), vnom=psse_bus.BASKV, vmin=psse_bus.NVLO, vmax=psse_bus.NVHI,
                      xpos=0,
                      ypos=0,
                      active=True,
                      area=area_dict[psse_bus.AREA],
                      zone=zone_dict[psse_bus.ZONE],
                      Vm0=psse_bus.VM,
                      Va0=np.deg2rad(psse_bus.VA))

    elif psse_bus.version in [29, 30]:
        # create bus
        name = psse_bus.NAME
        bus = dev.Bus(name=name, code=str(psse_bus.I), vnom=psse_bus.BASKV, vmin=0.9, vmax=1.1, xpos=0, ypos=0,
                      active=True,
                      area=area_dict[psse_bus.AREA],
                      zone=zone_dict[psse_bus.ZONE],
                      Vm0=psse_bus.VM,
                      Va0=np.deg2rad(psse_bus.VA))

        if psse_bus.GL > 0 or psse_bus.BL > 0:
            sh = dev.Shunt(name='Shunt_' + str(psse_bus.I),
                           G=psse_bus.GL, B=psse_bus.BL,
                           active=True)

            bus.shunts.append(sh)

    else:
        logger.add_warning('Bus not implemented for version', str(psse_bus.version))
        # create bus (try v33)
        name = psse_bus.NAME.replace("'", "")
        bus = dev.Bus(name=name,
                      vnom=psse_bus.BASKV, code=str(psse_bus.I), vmin=psse_bus.EVLO, vmax=psse_bus.EVHI, xpos=0, ypos=0,
                      active=True,
                      area=area_dict[psse_bus.AREA],
                      zone=zone_dict[psse_bus.ZONE],
                      Vm0=psse_bus.VM,
                      Va0=np.deg2rad(psse_bus.VA))

    # set type
    if psse_bus.IDE in bustype.keys():
        bus.type = bustype[psse_bus.IDE]
    else:
        bus.type = dev.BusMode.PQ

    if int(psse_bus.IDE) == 4:
        bus.active = False

    if bus.type == dev.BusMode.Slack:
        bus.is_slack = True

    # Ensures unique name
    bus.name = bus.name.replace("'", "").strip()

    bus.code = str(psse_bus.I)

    if bus.name == '':
        bus.name = 'Bus ' + str(psse_bus.I)

    return bus


def get_gridcal_load(psse_load: RawLoad, bus: dev.Bus, logger: Logger) -> dev.Load:
    """
    Return GridCal Load object
    Returns:
        Newton Load object
    """
    name = str(psse_load.I) + '_' + psse_load.ID.replace("'", "")
    name = name.strip()

    # GL and BL come in MW and MVAr
    vv = bus.Vnom ** 2.0

    if vv == 0:
        logger.add_error('Voltage equal to zero in load conversion', name)

    # self.SCALEs means if the load is scalable, so omit it
    g = psse_load.YP
    b = psse_load.YQ
    ir = psse_load.IP
    ii = -psse_load.IQ
    p = psse_load.PL
    q = psse_load.QL

    elm = dev.Load(name=name,
                   idtag=None,
                   code=name,
                   active=bool(psse_load.STATUS),
                   P=p, Q=q, Ir=ir, Ii=ii, G=g, B=b)

    return elm


def get_gridcal_shunt_fixed(psse_elm: RawFixedShunt, bus: dev.Bus, logger: Logger):
    """
    Return Newton Load object
    Returns:
        Newton Load object
    """
    name = str(psse_elm.I) + '_' + str(psse_elm.ID).replace("'", "")
    name = name.strip()

    # GL and BL come in MW and MVAr
    # They must be in siemens
    vv = bus.Vnom * bus.Vnom

    if vv == 0:
        logger.add_error('Voltage equal to zero in shunt conversion', name)

    g = psse_elm.GL
    b = psse_elm.BL

    elm = dev.Shunt(name=name,
                    idtag=None,
                    G=g, B=b,
                    active=bool(psse_elm.STATUS),
                    code=name)

    return elm


def get_gridcal_shunt_switched(psse_elm: RawSwitchedShunt, bus: dev.Bus, logger: Logger):
    """
    Return Newton Load object
    Returns:
        Newton Load object
    """
    name = str(psse_elm.I).replace("'", "")
    name = name.strip()

    # GL and BL come in MW and MVAr
    # They must be in siemens
    vv = bus.Vnom ** 2.0

    if vv == 0:
        logger.add_error('Voltage equal to zero in shunt conversion', name)

    g = 0.0
    if psse_elm.MODSW in [1, 2]:
        b = psse_elm.BINIT * psse_elm.RMPCT / 100.0
    else:
        b = psse_elm.BINIT

    elm = dev.Shunt(name='Switched shunt ' + name,
                    G=g, B=b,
                    active=bool(psse_elm.STAT),
                    code=name)

    return elm


def get_gridcal_generator(psse_elm: RawGenerator, logger: Logger) -> dev.Generator:
    """
    Return Newton Load object
    Returns:
        Newton Load object
    """
    name = str(psse_elm.I) + '_' + str(psse_elm.ID).replace("'", "")
    elm = dev.Generator(name=name,
                        idtag=None,
                        code=name,
                        P=psse_elm.PG,
                        vset=psse_elm.VS,
                        Qmin=psse_elm.QB,
                        Qmax=psse_elm.QT,
                        Snom=psse_elm.MBASE,
                        Pmax=psse_elm.PT,
                        Pmin=psse_elm.PB,
                        active=bool(psse_elm.STAT))

    return elm


def get_gridcal_transformer(psse_elm: RawTransformer,
                            psse_bus_dict, Sbase,
                            logger: Logger) -> Tuple[Union[dev.Transformer2W, dev.Transformer3W], int]:
    """

    :param psse_elm:
    :param psse_bus_dict:
    :param Sbase:
    :param logger:
    :return:
    """

    '''
    R1-2, X1-2 The measured impedance of the transformer between the buses to which its first
        and second windings are connected.

        When CZ is 1, they are the resistance and reactance, respectively, in pu on system
        MVA base and winding voltage base.

        When CZ is 2, they are the resistance and reactance, respectively, in pu on Winding
        1 to 2 MVA base (SBASE1-2) and winding voltage base.

        When CZ is 3, R1-2 is the load loss in watts, and X1-2 is the impedance magnitude
        in pu on Winding 1 to 2 MVA base (SBASE1-2) and winding voltage base. For
        three-phase transformers or three-phase banks of single phase transformers, R1-2
        should specify the three-phase load loss.

        R1-2 = 0.0 by default, but no default is allowed for X1-2.
    '''

    psse_elm.CKT = str(psse_elm.CKT).replace("'", "")

    psse_elm.NAME = psse_elm.NAME.replace("'", "").strip()

    if psse_elm.windings == 0:
        # guess the number of windings
        psse_elm.windings = 2 if psse_elm.K == 0 else 3

    if psse_elm.windings == 2:
        bus_from = psse_bus_dict[psse_elm.I]
        bus_to = psse_bus_dict[psse_elm.J]

        name = "{0}_{1}_{2}_{3}_{4}_{5}_{6}".format(psse_elm.I, bus_from.name, bus_from.Vnom,
                                                    psse_elm.J, bus_to.name, bus_to.Vnom, psse_elm.CKT)

        name = name.replace("'", "").replace(" ", "").strip()

        code = str(psse_elm.I) + '_' + str(psse_elm.J) + '_' + str(psse_elm.CKT)
        code = code.strip().replace("'", "")

        """            
        PSS/e's randomness:            
        """

        if psse_elm.NOMV1 == 0:
            V1 = bus_from.Vnom
        else:
            V1 = psse_elm.NOMV1

        if psse_elm.NOMV2 == 0:
            V2 = bus_to.Vnom
        else:
            V2 = psse_elm.NOMV2

        contingency_factor = psse_elm.RATE1_1 / psse_elm.RATE1_2 if psse_elm.RATE1_2 > 0.0 else 1.0

        r, x, g, b, tap_module, tap_angle = psse_elm.get_2w_pu_impedances(Sbase=Sbase,
                                                                          v_bus_i=bus_from.Vnom,
                                                                          v_bus_j=bus_to.Vnom)

        if V1 >= V2:
            HV = V1
            LV = V2
        else:
            HV = V2
            LV = V1

        elm = dev.Transformer2W(bus_from=bus_from,
                                bus_to=bus_to,
                                idtag=psse_elm.idtag,
                                code=code,
                                name=name,
                                HV=HV,
                                LV=LV,
                                nominal_power=psse_elm.SBASE1_2,
                                r=r,
                                x=x,
                                g=g,
                                b=b,
                                rate=psse_elm.RATE1_1,
                                contingency_factor=round(contingency_factor, 6),
                                tap_module=tap_module,
                                tap_phase=tap_angle,
                                active=bool(psse_elm.STAT),
                                mttf=0,
                                mttr=0)

        return elm, 2

    elif psse_elm.windings == 3:

        bus_1 = psse_bus_dict[abs(psse_elm.I)]
        bus_2 = psse_bus_dict[abs(psse_elm.J)]
        bus_3 = psse_bus_dict[abs(psse_elm.K)]
        code = str(psse_elm.I) + '_' + str(psse_elm.J) + '_' + str(psse_elm.K) + '_' + str(psse_elm.CKT)

        if psse_elm.NOMV1 == 0:
            V1 = bus_1.Vnom
        else:
            V1 = psse_elm.NOMV1

        if psse_elm.NOMV2 == 0:
            V2 = bus_2.Vnom
        else:
            V2 = psse_elm.NOMV2

        if psse_elm.NOMV3 == 0:
            V3 = bus_3.Vnom
        else:
            V3 = psse_elm.NOMV3

        """
        PSS/e's randomness:
        """

        # see: https://en.wikipedia.org/wiki/Per-unit_system
        base_change12 = Sbase / psse_elm.SBASE1_2
        base_change23 = Sbase / psse_elm.SBASE2_3
        base_change31 = Sbase / psse_elm.SBASE3_1

        if psse_elm.CZ == 1:
            """
            When CZ is 1, they are the resistance and reactance, respectively, in pu on system
            MVA base and winding voltage base.
            """
            r12 = psse_elm.R1_2
            x12 = psse_elm.X1_2
            r23 = psse_elm.R2_3
            x23 = psse_elm.X2_3
            r31 = psse_elm.R3_1
            x31 = psse_elm.X3_1

        elif psse_elm.CZ == 2:

            """
            When CZ is 2, they are the resistance and reactance, respectively, in pu on Winding
            1 to 2 MVA base (SBASE1-2) and winding voltage base.
            """
            zb12 = Sbase / psse_elm.SBASE1_2
            zb23 = Sbase / psse_elm.SBASE2_3
            zb31 = Sbase / psse_elm.SBASE3_1

            r12 = psse_elm.R1_2 * zb12
            x12 = psse_elm.X1_2 * zb12
            r23 = psse_elm.R2_3 * zb23
            x23 = psse_elm.X2_3 * zb23
            r31 = psse_elm.R3_1 * zb31
            x31 = psse_elm.X3_1 * zb31

        elif psse_elm.CZ == 3:

            """
            When CZ is 3, R1-2 is the load loss in watts, and X1-2 is the impedance magnitude
            in pu on Winding 1 to 2 MVA base (SBASE1-2) and winding voltage base. For
            three-phase transformers or three-phase banks of single phase transformers, R1-2
            should specify the three-phase load loss.
            """

            r12 = psse_elm.R1_2 * 1e-6
            x12 = psse_elm.X1_2 * base_change12
            r23 = psse_elm.R2_3 * 1e-6
            x23 = psse_elm.X2_3 * base_change23
            r31 = psse_elm.R3_1 * 1e-6
            x31 = psse_elm.X3_1 * base_change31
        else:
            raise Exception('Unknown impedance combination CZ=' + str(psse_elm.CZ))

        tr3w = dev.Transformer3W(bus1=bus_1,
                                 bus2=bus_2,
                                 bus3=bus_3,
                                 V1=V1, V2=V2, V3=V3,
                                 name=psse_elm.NAME,
                                 idtag=psse_elm.idtag,
                                 code=code,
                                 active=bool(psse_elm.STAT),
                                 r12=r12, r23=r23, r31=r31,
                                 x12=x12, x23=x23, x31=x31,
                                 rate12=psse_elm.RATE1_1, rate23=psse_elm.RATE2_1, rate31=psse_elm.RATE3_1,
                                 x=0.0, y=0.0)

        tr3w.winding1.tap_phase = psse_elm.ANG1
        tr3w.winding2.tap_phase = psse_elm.ANG2
        tr3w.winding3.tap_phase = psse_elm.ANG3

        return tr3w, 3

    else:
        raise Exception(str(psse_elm.windings) + ' number of windings!')


def get_gridcal_line(psse_elm: RawBranch, psse_bus_dict, Sbase, logger: Logger) -> dev.Line:
    """

    :param psse_elm:
    :param psse_bus_dict:
    :param Sbase:
    :param logger:
    :return:
    """

    i = abs(psse_elm.I)
    j = abs(psse_elm.J)
    bus_from = psse_bus_dict[i]
    bus_to = psse_bus_dict[j]
    code = str(i) + '_' + str(j) + '_' + str(psse_elm.CKT).replace("'", "").strip()

    if psse_elm.NAME.strip() == '':
        name = "{0}_{1}_{2}_{3}_{4}_{5}_{6}".format(i, bus_from.name, bus_from.Vnom, j, bus_to.name, bus_to.Vnom,
                                                    psse_elm.CKT)
        name = name.replace("'", "").replace(" ", "").strip()
    else:
        name = psse_elm.NAME.strip()

    contingency_factor = psse_elm.RATE2 / psse_elm.RATE1 if psse_elm.RATE1 > 0.0 else 1.0

    if contingency_factor == 0:
        contingency_factor = 1.0

    branch = dev.Line(bus_from=bus_from,
                      bus_to=bus_to,
                      idtag=psse_elm.idtag,
                      code=code,
                      name=name,
                      r=psse_elm.R,
                      x=psse_elm.X,
                      b=psse_elm.B,
                      rate=psse_elm.RATE1,
                      contingency_factor=round(contingency_factor, 6),
                      active=bool(psse_elm.ST),
                      mttf=0,
                      mttr=0,
                      length=psse_elm.LEN)
    return branch


def get_hvdc_from_vscdc(psse_elm: RawVscDCLine, psse_bus_dict, Sbase, logger: Logger) -> dev.HvdcLine:
    """
    GEt equivalent object
    :param psse_bus_dict:
    :param logger:
    :return:
    """
    bus1 = psse_bus_dict[abs(psse_elm.IBUS1)]
    bus2 = psse_bus_dict[abs(psse_elm.IBUS2)]

    name1 = psse_elm.NAME.replace("'", "").replace('/', '').strip()
    idtag = str(psse_elm.IBUS1) + '_' + str(psse_elm.IBUS2) + '_1'

    Vset_f = psse_elm.ACSET1
    Vset_t = psse_elm.ACSET2
    rate = max(psse_elm.SMAX1, psse_elm.SMAX2)

    # Estimate power
    # P = dV^2 / R
    V1 = bus1.Vnom * Vset_f
    V2 = bus2.Vnom * Vset_t
    dV = (V1 - V2) * 1000.0  # in V
    P = dV * dV / psse_elm.RDC if psse_elm.RDC != 0 else 0  # power in W
    specified_power = P * 1e-6  # power in MW

    obj = dev.HvdcLine(bus_from=bus1,
                       bus_to=bus2,
                       name=name1,
                       idtag=idtag,
                       Pset=specified_power,
                       Vset_f=Vset_f,
                       Vset_t=Vset_t,
                       rate=rate)

    return obj


def get_hvdc_from_twotermdc(psse_elm: RawTwoTerminalDCLine, psse_bus_dict, Sbase: float,
                            logger: Logger) -> dev.HvdcLine:
    """

    :param psse_elm:
    :param psse_bus_dict:
    :param Sbase:
    :param logger:
    :return:
    """
    bus1 = psse_bus_dict[abs(psse_elm.IPR)]
    bus2 = psse_bus_dict[abs(psse_elm.IPI)]

    if psse_elm.MDC == 1 or psse_elm.MDC == 0:
        # SETVL is in MW
        specified_power = psse_elm.SETVL
    elif psse_elm.MDC == 2:
        # SETVL is in A, specified_power in MW
        specified_power = psse_elm.SETVL * psse_elm.VSCHD / 1000.0
    else:
        # doesn't say, so zero
        specified_power = 0.0

    # z_base = psse_elm.VSCHD * psse_elm.VSCHD / Sbase
    # r_pu = psse_elm.RDC / z_base

    Vset_f = 1.0
    Vset_t = 1.0

    name1 = psse_elm.NAME.replace("'", "").replace('"', "").replace('/', '').strip()
    idtag = str(psse_elm.IPR) + '_' + str(psse_elm.IPI) + '_1'

    # set the HVDC line active
    active = bus1.active and bus2.active

    obj = dev.HvdcLine(bus_from=bus1,  # Rectifier as of PSSe
                       bus_to=bus2,  # inverter as of PSSe
                       active=active,
                       name=name1,
                       idtag=idtag,
                       Pset=specified_power,
                       Vset_f=Vset_f,
                       Vset_t=Vset_t,
                       rate=specified_power,
                       r=psse_elm.RDC,
                       min_firing_angle_f=np.deg2rad(psse_elm.ANMNR),
                       max_firing_angle_f=np.deg2rad(psse_elm.ANMXR),
                       min_firing_angle_t=np.deg2rad(psse_elm.ANMNI),
                       max_firing_angle_t=np.deg2rad(psse_elm.ANMXI))
    return obj


def get_upfc_from_facts(psse_elm: RawFACTS, psse_bus_dict, Sbase, logger: Logger) -> None:
    """
    GEt equivalent object
    :param psse_bus_dict:
    :param logger:
    :param circuit:
    :return:
    """
    bus1 = psse_bus_dict[abs(psse_elm.I)]

    if abs(psse_elm.J) > 0:
        bus2 = psse_bus_dict[abs(psse_elm.J)]
    else:
        bus2 = None

    name1 = psse_elm.NAME.replace("'", "").replace('"', "").replace('/', '').strip()
    idtag = str(psse_elm.I) + '_' + str(psse_elm.J) + '_1'

    mode = int(psse_elm.MODE)

    if '*' in str(psse_elm.SET2):
        psse_elm.SET2 = 0.0

    if '*' in str(psse_elm.SET1):
        psse_elm.SET1 = 0.0

    if mode == 0:
        active = False
    elif mode == 1 and abs(psse_elm.J) > 0:
        # shunt link
        logger.add_warning('FACTS mode not implemented', str(mode))

    elif mode == 2:
        # only shunt device: STATCOM
        logger.add_warning('FACTS mode not implemented', str(mode))

    elif mode == 3 and abs(psse_elm.J) > 0:  # const Z
        # series and shunt links operating with series link at constant series impedance
        # sh = Shunt(name='FACTS:' + name1, B=psse_elm.SHMX)
        # load_from = Load(name='FACTS:' + name1, P=-psse_elm.PDES, Q=-psse_elm.QDES)
        # gen_to = Generator(name='FACTS:' + name1, active_power=psse_elm.PDES, voltage_module=psse_elm.VSET)
        # # branch = Line(bus_from=bus1, bus_to=bus2, name='FACTS:' + name1, x=psse_elm.LINX)
        # circuit.add_shunt(bus1, sh)
        # circuit.add_load(bus1, load_from)
        # circuit.add_generator(bus2, gen_to)
        # # circuit.add_line(branch)

        elm = dev.UPFC(name=name1,
                       bus_from=bus1,
                       bus_to=bus2,
                       code=idtag,
                       rs=psse_elm.SET1,
                       xs=psse_elm.SET2 + psse_elm.LINX,
                       rp=0.0,
                       xp=1.0 / psse_elm.SHMX if psse_elm.SHMX > 0 else 0.0,
                       vp=psse_elm.VSET,
                       Pset=psse_elm.PDES,
                       Qset=psse_elm.QDES,
                       rate=psse_elm.IMX + 1e-20)

        return elm

    elif mode == 4 and abs(psse_elm.J) > 0:
        # series and shunt links operating with series link at constant series voltage
        logger.add_warning('FACTS mode not implemented', str(mode))

    elif mode == 5 and abs(psse_elm.J) > 0:
        # master device of an IPFC with P and Q setpoints specified;
        # another FACTS device must be designated as the slave device
        # (i.e., its MODE is 6 or 8) of this IPFC.
        logger.add_warning('FACTS mode not implemented', str(mode))

    elif mode == 6 and abs(psse_elm.J) > 0:
        # 6 slave device of an IPFC with P and Q setpoints specified;
        #  the FACTS device specified in MNAME must be the master
        #  device (i.e., its MODE is 5 or 7) of this IPFC. The Q setpoint is
        #  ignored as the master device dictates the active power
        #  exchanged between the two devices.
        logger.add_warning('FACTS mode not implemented', str(mode))

    elif mode == 7 and abs(psse_elm.J) > 0:
        # master device of an IPFC with constant series voltage setpoints
        # specified; another FACTS device must be designated as the slave
        # device (i.e., its MODE is 6 or 8) of this IPFC
        logger.add_warning('FACTS mode not implemented', str(mode))

    elif mode == 8 and abs(psse_elm.J) > 0:
        # slave device of an IPFC with constant series voltage setpoints
        # specified; the FACTS device specified in MNAME must be the
        # master device (i.e., its MODE is 5 or 7) of this IPFC. The complex
        # Vd + jVq setpoint is modified during power flow solutions to reflect
        # the active power exchange determined by the master device
        logger.add_warning('FACTS mode not implemented', str(mode))

    else:
        return None


def psse_to_gridcal(psse_circuit: PsseCircuit,
                    logger: Logger,
                    branch_connection_voltage_tolerance: float = 0.1) -> MultiCircuit:
    """

    :param psse_circuit: PsseCircuit instance
    :param logger: Logger
    :param branch_connection_voltage_tolerance: tolerance in p.u. of a branch voltage to be considered a transformer
    :return: MultiCircuit instance
    """

    circuit = MultiCircuit(Sbase=psse_circuit.SBASE)
    circuit.comments = 'Converted from a PSS/e .raw file'

    circuit.areas = [dev.Area(name=x.ARNAME) for x in psse_circuit.areas]
    circuit.zones = [dev.Zone(name=x.ZONAME) for x in psse_circuit.zones]

    area_dict = {val.I: elm for val, elm in zip(psse_circuit.areas, circuit.areas)}
    zones_dict = {val.I: elm for val, elm in zip(psse_circuit.zones, circuit.zones)}

    # scan for missing zones or areas (yes, PSSe is so crappy that can reference areas that do not exist)
    missing_areas = False
    missing_zones = False
    psse_bus_dict: Dict[int, dev.Bus] = dict()
    slack_buses: List[int] = list()
    for psse_bus in psse_circuit.buses:

        # replace area idx by area name if available
        if abs(psse_bus.AREA) not in area_dict.keys():
            area_dict[abs(psse_bus.AREA)] = dev.Area(name='A' + str(abs(psse_bus.AREA)))
            missing_areas = True

        if abs(psse_bus.ZONE) not in zones_dict.keys():
            zones_dict[abs(psse_bus.ZONE)] = dev.Zone(name='Z' + str(abs(psse_bus.ZONE)))
            missing_zones = True

        bus = get_gridcal_bus(psse_bus=psse_bus,
                              area_dict=area_dict,
                              zone_dict=zones_dict,
                              logger=logger)

        # bus.ensure_area_objects(circuit)

        if bus.type.value == 3:
            slack_buses.append(psse_bus.I)

        circuit.add_bus(bus)
        psse_bus_dict[psse_bus.I] = bus

    if missing_areas:
        circuit.areas = [v for k, v in area_dict.items()]

    if missing_zones:
        circuit.zones = [v for k, v in zones_dict.items()]

    # check htat the area slack buses actually make sense
    for area in psse_circuit.areas:
        if area.ISW not in slack_buses:
            logger.add_error('The area slack bus is not marked as slack', str(area.ISW))

    # Go through loads
    for psse_load in psse_circuit.loads:
        bus = psse_bus_dict[psse_load.I]
        api_obj = get_gridcal_load(psse_load, bus, logger)

        circuit.add_load(bus, api_obj)

    # Go through shunts
    for psse_shunt in psse_circuit.fixed_shunts:
        if psse_shunt.I in psse_bus_dict:
            bus = psse_bus_dict[psse_shunt.I]
            api_obj = get_gridcal_shunt_fixed(psse_shunt, bus, logger)
            circuit.add_shunt(bus, api_obj)
        else:
            logger.add_error("Shunt bus missing", psse_shunt.I, psse_shunt.I)

    for psse_shunt in psse_circuit.switched_shunts:
        if psse_shunt.I in psse_bus_dict:
            bus = psse_bus_dict[psse_shunt.I]
            api_obj = get_gridcal_shunt_switched(psse_shunt, bus, logger)
            circuit.add_shunt(bus, api_obj)
        else:
            logger.add_error("Switched shunt bus missing", psse_shunt.I, psse_shunt.I)

    # Go through generators
    for psse_gen in psse_circuit.generators:
        bus = psse_bus_dict[psse_gen.I]
        api_obj = get_gridcal_generator(psse_gen, logger)

        circuit.add_generator(bus, api_obj)

    # Go through Branches
    branches_already_there = set()

    # Go through Transformers
    for psse_branch in psse_circuit.transformers:
        # get the object
        branch, n_windings = get_gridcal_transformer(psse_branch, psse_bus_dict, psse_circuit.SBASE, logger)

        if branch.idtag not in branches_already_there:
            # Add to the circuit
            if n_windings == 2:
                circuit.add_transformer2w(branch)
            elif n_windings == 3:
                circuit.add_transformer3w(branch)
            else:
                raise Exception('Unsupported number of windings')
            branches_already_there.add(branch.idtag)

        else:
            logger.add_warning('The RAW file has a repeated transformer and it is omitted from the model',
                               branch.idtag)

    # Go through the Branches
    for psse_branch in psse_circuit.branches:
        # get the object
        branch = get_gridcal_line(psse_branch, psse_bus_dict, psse_circuit.SBASE, logger)

        # detect if this branch is actually a transformer
        if branch.should_this_be_a_transformer(branch_connection_voltage_tolerance):

            logger.add_error(msg="Converted line to transformer due to excessive voltage difference",
                             device=str(branch.idtag))

            transformer = branch.get_equivalent_transformer()

            # Add to the circuit
            circuit.add_transformer2w(transformer)
            branches_already_there.add(branch.idtag)

        else:

            if branch.idtag not in branches_already_there:

                # Add to the circuit
                circuit.add_line(branch, logger=logger)
                branches_already_there.add(branch.idtag)

            else:
                logger.add_warning('The RAW file has a repeated line device and it is omitted from the model',
                                   str(branch.idtag))

    # Go through hvdc lines
    for psse_branch in psse_circuit.vsc_dc_lines:
        # get the object
        branch = get_hvdc_from_vscdc(psse_branch, psse_bus_dict, psse_circuit.SBASE, logger)

        if branch.idtag not in branches_already_there:

            # Add to the circuit
            circuit.add_hvdc(branch)
            branches_already_there.add(branch.idtag)

        else:
            logger.add_warning('The RAW file has a repeated HVDC line device and it is omitted from the model',
                               str(branch.idtag))

    for psse_branch in psse_circuit.two_terminal_dc_lines:
        # get the object
        branch = get_hvdc_from_twotermdc(psse_branch, psse_bus_dict, psse_circuit.SBASE, logger)

        if branch.idtag not in branches_already_there:

            # Add to the circuit
            circuit.add_hvdc(branch)
            branches_already_there.add(branch.idtag)

        else:
            logger.add_warning('The RAW file has a repeated HVDC line device and it is omitted from the model',
                               str(branch.idtag))

    # Go through facts
    for psse_elm in psse_circuit.facts:
        # since these may be shunt or series or both, pass the circuit so that the correct device is added
        if psse_elm.is_connected():
            elm = get_upfc_from_facts(psse_elm, psse_bus_dict, psse_circuit.SBASE, logger)

            if elm is not None:
                circuit.add_upfc(elm)
            else:
                code = str(psse_elm.I) + '_' + str(psse_elm.J) + '_1'
                logger.add_warning('FACTS device was not converted', str(code))

    return circuit
