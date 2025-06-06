# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import math
from typing import Dict, List, Tuple, Union
from GridCalEngine.basic_structures import Logger
import GridCalEngine.Devices as dev
from GridCalEngine.Topology import detect_substations
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.raw.devices.branch import RawBranch
from GridCalEngine.IO.raw.devices.bus import RawBus
from GridCalEngine.IO.raw.devices.facts import RawFACTS
from GridCalEngine.IO.raw.devices.generator import RawGenerator
from GridCalEngine.IO.raw.devices.load import RawLoad
from GridCalEngine.IO.raw.devices.fixed_shunt import RawFixedShunt
from GridCalEngine.IO.raw.devices.switched_shunt import RawSwitchedShunt
from GridCalEngine.IO.raw.devices.transformer import RawTransformer
from GridCalEngine.IO.raw.devices.two_terminal_dc_line import RawTwoTerminalDCLine
from GridCalEngine.IO.raw.devices.vsc_dc_line import RawVscDCLine
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit
from GridCalEngine.enumerations import TapChangerTypes, TapPhaseControl, TapModuleControl


def get_gridcal_bus(psse_bus: RawBus,
                    area_dict: Dict[int, dev.Area],
                    zone_dict: Dict[int, dev.Zone],
                    logger: Logger) -> Tuple[dev.Bus, Union[dev.Shunt, None]]:
    """

    :return:
    """

    bustype = {1: dev.BusMode.PQ_tpe, 2: dev.BusMode.PV_tpe, 3: dev.BusMode.Slack_tpe, 4: dev.BusMode.PQ_tpe}
    sh = None

    if psse_bus.version >= 33:
        # create bus
        name = psse_bus.NAME.replace("'", "")
        bus = dev.Bus(name=name,
                      Vnom=psse_bus.BASKV,
                      code=str(psse_bus.I),
                      vmin=psse_bus.EVLO,
                      vmax=psse_bus.EVHI,
                      xpos=0, ypos=0,
                      active=True,
                      area=area_dict[psse_bus.AREA],
                      zone=zone_dict[psse_bus.ZONE],
                      Vm0=psse_bus.VM,
                      Va0=np.deg2rad(psse_bus.VA))

    elif psse_bus.version == 32:
        # create bus
        name = psse_bus.NAME
        bus = dev.Bus(name=name, code=str(psse_bus.I),
                      Vnom=psse_bus.BASKV,
                      vmin=psse_bus.NVLO, vmax=psse_bus.NVHI,
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
        bus = dev.Bus(name=name, code=str(psse_bus.I),
                      Vnom=psse_bus.BASKV,
                      vmin=0.9, vmax=1.1, xpos=0, ypos=0,
                      active=True,
                      area=area_dict[psse_bus.AREA],
                      zone=zone_dict[psse_bus.ZONE],
                      Vm0=psse_bus.VM,
                      Va0=np.deg2rad(psse_bus.VA))

        if psse_bus.GL > 0 or psse_bus.BL > 0:
            sh = dev.Shunt(name='Shunt_' + str(psse_bus.I),
                           G=psse_bus.GL, B=psse_bus.BL,
                           active=True)

    else:
        logger.add_warning('Bus not implemented for version', str(psse_bus.version))
        # create bus (try v33)
        name = psse_bus.NAME.replace("'", "")
        bus = dev.Bus(name=name,
                      Vnom=psse_bus.BASKV,
                      code=str(psse_bus.I),
                      vmin=psse_bus.EVLO,
                      vmax=psse_bus.EVHI,
                      xpos=0, ypos=0,
                      active=True,
                      area=area_dict[psse_bus.AREA],
                      zone=zone_dict[psse_bus.ZONE],
                      Vm0=psse_bus.VM,
                      Va0=np.deg2rad(psse_bus.VA))

    # set type
    if psse_bus.IDE in bustype.keys():
        bus.type = bustype[psse_bus.IDE]
    else:
        bus.type = dev.BusMode.PQ_tpe

    if int(psse_bus.IDE) == 4:
        bus.active = False

    if bus.type == dev.BusMode.Slack_tpe:
        bus.is_slack = True

    # Ensures unique name
    bus.name = bus.name.replace("'", "").strip()

    bus.code = str(psse_bus.I)

    if bus.name == '':
        bus.name = 'Bus ' + str(psse_bus.I)

    return bus, sh


def get_gridcal_load(psse_load: RawLoad, bus: dev.Bus, logger: Logger) -> dev.Load:
    """
    Return GridCal Load object
    Returns:
        Newton Load object
    """
    name = str(psse_load.I) + '_' + str(psse_load.ID).replace("'", "")
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
    if psse_load.SCALE == 1.0:
        elm.scalable = True
    else:
        elm.scalable = False

    return elm


def get_gridcal_shunt_fixed(psse_elm: RawFixedShunt, bus: dev.Bus, logger: Logger):
    """
    Return GridCal Shunt object
    Returns:
        GridCal Shunt object
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


def get_gridcal_shunt_switched(
        psse_elm: RawSwitchedShunt,
        bus: dev.Bus,
        psse_bus_dict: Dict[int, dev.Bus],
        logger: Logger) -> dev.ControllableShunt:
    """

    :param psse_elm:
    :param bus:
    :param psse_bus_dict:
    :param logger:
    :return:
    """
    busnum_id = psse_elm.get_id()

    # GL and BL come in MW and MVAr
    # They must be in siemens
    vv = bus.Vnom ** 2.0

    if vv == 0:
        logger.add_error('Voltage equal to zero in shunt conversion', busnum_id)

    vset = 1.0

    if psse_elm.MODSW == 0:  # locked
        is_controlled = False
        b_init = psse_elm.BINIT

    elif psse_elm.MODSW in [1, 2]:
        # 1 - discrete adjustment, controlling voltage locally or at bus SWREG
        # 2 - continuous adjustment, controlling voltage locally or at bus SWREG
        is_controlled = True
        b_init = psse_elm.BINIT * psse_elm.RMPCT / 100.0
        vset = (psse_elm.VSWHI + psse_elm.VSWLO) / 2.0

    elif psse_elm.MODSW in [3, 4, 5, 6]:
        is_controlled = True
        b_init = psse_elm.BINIT
        logger.add_warning(
            msg="Not supported control mode for Switched Shunt",
            value=psse_elm.MODSW
        )

    else:
        is_controlled = False
        b_init = psse_elm.BINIT
        logger.add_warning(
            msg="Invalid control mode for Switched Shunt.",
            device=psse_elm,
            expected_value="0-6",
            value=psse_elm.MODSW,
        )

    elm = dev.ControllableShunt(name='Switched shunt ' + busnum_id,
                                active=bool(psse_elm.STAT),
                                B=b_init,
                                step=0,
                                vset=vset,
                                code=busnum_id,
                                is_nonlinear=True,
                                is_controlled=is_controlled, )

    if psse_elm.SWREG > 0:
        if psse_elm.SWREG != psse_elm.I:
            elm.control_bus = psse_bus_dict[psse_elm.SWREG]

    n_list = []
    b_list = []

    for i in range(1, 9):
        s = getattr(psse_elm, f"S{i}")
        n = getattr(psse_elm, f"N{i}")

        if s == 1:
            n_list.append(n)
            b_list.append(getattr(psse_elm, f"B{i}"))

    if len(n_list) == 1:
        elm.is_nonlinear = False

    elm.set_blocks(n_list, b_list)

    return elm


def get_gridcal_generator(psse_elm: RawGenerator, psse_bus_dict: Dict[int, dev.Bus], logger: Logger) -> dev.Generator:
    """

    :param psse_elm:
    :param psse_bus_dict:
    :param logger:
    :return:
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
                        active=bool(psse_elm.STAT),
                        power_factor=psse_elm.WPF if psse_elm.WPF is not None else 0.8)

    if psse_elm.IREG > 0:
        if psse_elm.IREG != psse_elm.I:
            elm.control_bus = psse_bus_dict[psse_elm.IREG]

    return elm


def get_gridcal_transformer(
        psse_elm: RawTransformer,
        psse_bus_dict: Dict[int, dev.Bus],
        Sbase: float,
        logger: Logger,
        adjust_taps_to_discrete_positions: bool = False) -> Tuple[Union[dev.Transformer2W, dev.Transformer3W], int]:
    """

    :param psse_elm:
    :param psse_bus_dict:
    :param Sbase:
    :param logger:
    :param adjust_taps_to_discrete_positions: Modify the tap angle and module to the discrete positions
    :return:
    """

    """
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
    """

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

        contingency_factor = (psse_elm.RATE1_2 / psse_elm.RATE1_1
                              if psse_elm.RATE1_1 > 0.0 and psse_elm.RATE1_2 > 0.0
                              else 1.0)

        protection_factor = (psse_elm.RATE1_3 / psse_elm.RATE1_1
                             if psse_elm.RATE1_1 > 0.0 and psse_elm.RATE1_3 > 0.0
                             else 1.4)

        r, x, g, b, tap_module, tap_angle = psse_elm.get_2w_pu_impedances(Sbase=Sbase,
                                                                          v_bus_i=bus_from.Vnom,
                                                                          v_bus_j=bus_to.Vnom)

        if V1 >= V2:
            HV = V1
            LV = V2
        else:
            HV = V2
            LV = V1

        # GET CONTROL and TAP CHANGER DATA
        # transformer control
        tap_module_control_mode = TapModuleControl.fixed
        tap_phase_control_mode = TapPhaseControl.fixed
        regulation_bus = None
        # tap changer
        tc_total_positions: int = 1
        tc_neutral_position: int = 0
        tc_normal_position: int = 0
        tc_dV: float = 0.05
        tc_asymmetry_angle = 90
        tc_type: TapChangerTypes = TapChangerTypes.NoRegulation
        tc_tap_pos = 0

        if psse_elm.COD1 in [0, 1, -1]:  # for no-regulation(0) and voltage control (1)

            tap_module_control_mode = TapModuleControl.Vm if psse_elm.COD1 > 0 else TapModuleControl.fixed
            tap_phase_control_mode = TapPhaseControl.fixed

            if psse_elm.COD1 in [1, -1]:  # for voltage control (1)
                tc_type = TapChangerTypes.VoltageRegulation

            if psse_elm.VMA1 != 0:
                if psse_elm.NTP1 > 0:
                    tc_total_positions = psse_elm.NTP1
                    tc_neutral_position = np.floor(psse_elm.NTP1 / 2)
                    tc_normal_position = np.floor(psse_elm.NTP1 / 2)
                    tc_dV = (psse_elm.VMA1 - psse_elm.VMI1) / (psse_elm.NTP1 - 1) if (psse_elm.NTP1 - 1) > 0 else 0.01
                    distance_from_low = tap_module - psse_elm.VMI1
                    tc_tap_pos = distance_from_low / tc_dV if tc_dV != 0 else 0.5
            elif psse_elm.VMA2 != 0:
                if psse_elm.NTP2 > 0:
                    tc_total_positions = psse_elm.NTP2
                    tc_neutral_position = np.floor(psse_elm.NTP2 / 2)
                    tc_normal_position = np.floor(psse_elm.NTP2 / 2)
                    tc_dV = (psse_elm.VMA2 - psse_elm.VMI2) / (psse_elm.NTP2 - 1) if (psse_elm.NTP2 - 1) > 0 else 0.01
                    distance_from_low = tap_module - psse_elm.VMI2
                    tc_tap_pos = distance_from_low / tc_dV if tc_dV != 0 else 0.5
            else:
                if psse_elm.NTP3 > 0:
                    tc_total_positions = psse_elm.NTP3
                    tc_neutral_position = np.floor(psse_elm.NTP3 / 2)
                    tc_normal_position = np.floor(psse_elm.NTP3 / 2)
                    tc_dV = (psse_elm.VMA3 - psse_elm.VMI3) / (psse_elm.NTP3 - 1) if (psse_elm.NTP3 - 1) > 0 else 0.01
                    distance_from_low = tap_module - psse_elm.VMI3
                    tc_tap_pos = distance_from_low / tc_dV if tc_dV != 0 else 0.5

            if round(tc_tap_pos, 2) != int(tc_tap_pos):
                # the calculated step is not an integer
                tc_dV = round((1 - tap_module) / tap_module, 6)
                tc_total_positions = 2
                tc_neutral_position = 0
                tc_normal_position = -1
                tc_tap_pos = -1
                tc_total_positions = 2  # [0,1]
                tc_neutral_position = 1
                tc_normal_position = 0
                tc_tap_pos = 0

                logger.add_warning(
                    msg='Calculated tap position is not integer',
                    device=code,
                    device_class='Transformer',
                    value=42)

        elif psse_elm.COD1 in [2, -2]:  # for reactive power flow control

            tap_module_control_mode = TapModuleControl.Qf if psse_elm.COD1 > 0 else TapModuleControl.fixed
            tap_phase_control_mode = TapPhaseControl.fixed

        elif psse_elm.COD1 in [3, -3]:  # for active power flow control

            tap_module_control_mode = TapModuleControl.fixed
            tap_phase_control_mode = TapPhaseControl.Pf if psse_elm.COD1 > 0 else TapPhaseControl.fixed
            tc_type = TapChangerTypes.Symmetrical
            tc_total_positions = psse_elm.NTP1
            tc_neutral_position = int((psse_elm.NTP1 + 1) / 2)
            tc_normal_position = int((psse_elm.NTP1 + 1) / 2)

            alpha_per_2 = math.radians(psse_elm.RMA1 / 2)
            # NTP1 should be an odd number
            number_of_symmetrical_step = (psse_elm.NTP1 - 1) / 2
            tc_dV = 2 * math.tan(alpha_per_2) / number_of_symmetrical_step

            d_ang = psse_elm.RMA1 / ((psse_elm.NTP1 - 1) / 2)
            # ?: this value is set internally by set_tap_phase
            # tc_tap_position
            if d_ang != 0.0:
                tc_step = round(psse_elm.ANG1 / d_ang)
                if tc_step - (psse_elm.ANG1 / d_ang) > 0.1:
                    logger.add_warning(
                        device=psse_elm,
                        device_class=psse_elm.class_name,
                        msg="Tap changer is not on discrete step.",
                        value=psse_elm.ANG1 / d_ang,
                    )
                tc_tap_pos = tc_neutral_position + tc_step
            else:
                tc_step = 0
            # print()
            # corrected_phase = elm.tap_changer.set_tap_phase(elm.tap_phase)
            # elm.tap_phase = corrected_phase
            #
            # print("Tap module, and phase calculated:",
            #       elm.tap_module, elm.tap_phase)

            # if psse_elm.NTP1 > 1:
            #     tc_total_positions = psse_elm.NTP1
            #     tc_neutral_position = int((psse_elm.NTP1 + 1) / 2)
            #     tc_normal_position = int((psse_elm.NTP1 + 1) / 2)
            #     alpha_per_2 = math.radians(psse_elm.RMA1)
            #     number_of_symmetrical_step = (psse_elm.NTP1 - 1) / 2
            #     tc_dV = 2 * math.tan(alpha_per_2) / number_of_symmetrical_step
            # else:
            #     tc_total_positions = 1
            #     tc_neutral_position = 0
            #     tc_normal_position = 0
            #     alpha_per_2 = math.radians(psse_elm.RMA1)
            #     tc_dV = 0.0
            #     logger.add_warning(msg='Number of tap positions == 1', value=1)

        elif psse_elm.COD1 in [4, -4]:  # for control of a dc line quantity
            # (valid only for two-winding transformers)

            logger.add_error(msg="Not implemented transformer control. (COD1)",
                             value=psse_elm.COD1)

        elif psse_elm.COD1 in [5, -5]:  # for asymmetric active power flow control

            tap_module_control_mode = TapModuleControl.Vm if psse_elm.COD1 > 0 else TapModuleControl.fixed
            tap_phase_control_mode = TapPhaseControl.Pf if psse_elm.COD1 > 0 else TapPhaseControl.fixed
            tc_type = TapChangerTypes.Asymmetrical
            tc_asymmetry_angle = psse_elm.CNXA1

        else:
            logger.add_error(msg="COD1 (transformer control mode) not recognized.",
                             value=psse_elm.COD1)

        elm = dev.Transformer2W(
            bus_from=bus_from,
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
            protection_rating_factor=round(protection_factor, 6),
            # regulation_bus=regulation_bus,
            tap_module=tap_module,
            tap_phase=tap_angle,
            active=bool(psse_elm.STAT),
            mttf=0,
            mttr=0,
            tap_phase_control_mode=tap_phase_control_mode,
            tap_module_control_mode=tap_module_control_mode,
            tc_total_positions=tc_total_positions,
            tc_neutral_position=tc_neutral_position,
            tc_normal_position=tc_normal_position,
            tc_dV=tc_dV,
            tc_asymmetry_angle=tc_asymmetry_angle,
            tc_type=tc_type,
        )

        if adjust_taps_to_discrete_positions:

            if psse_elm.COD1 == 0:  # for no control

                elm.tap_changer.tc_type = TapChangerTypes.VoltageRegulation
                elm.tap_changer.recalc()
                elm.tap_module = elm.tap_changer.set_tap_module(tap_module=tap_module)
                elm.tap_changer.tc_type = TapChangerTypes.NoRegulation

                logger.add_info("Raw import: tap module recalculated, but the transformer is not regulating",
                                device=code,
                                value=elm.tap_module)

            if psse_elm.COD1 in [1, -1]:  # for voltage control (1)
                reg_bus_id = abs(psse_elm.CONT1)
                if reg_bus_id > 0:
                    elm.regulation_bus = psse_bus_dict.get(reg_bus_id, None)
                    # defined only in ControllableBranchParent

                elm.tap_module = elm.tap_changer.set_tap_module(tap_module=tap_module)

                logger.add_info("Raw import: tap module calculated:",
                                device=code,
                                value=elm.tap_module)

            elif psse_elm.COD1 in [3, -3]:  # for active power flow control

                elm.tap_phase = elm.tap_changer.set_tap_phase(tap_phase=tap_angle)

                logger.add_info("Raw import: tap phase calculated:",
                                device=code,
                                value=elm.tap_phase)

        mf, mt = elm.get_virtual_taps()

        # we need to discount that PSSe includes the virtual tap inside the normal tap
        elm.tap_module = tap_module / mf * mt

        return elm, 2

    elif psse_elm.windings == 3:

        bus_1 = psse_bus_dict[abs(psse_elm.I)]
        bus_2 = psse_bus_dict[abs(psse_elm.J)]
        bus_3 = psse_bus_dict[abs(psse_elm.K)]
        code = str(psse_elm.I) + '_' + str(psse_elm.J) + '_' + str(psse_elm.K) + '_' + str(psse_elm.CKT)

        V1 = bus_1.Vnom if psse_elm.NOMV1 == 0 else psse_elm.NOMV1
        V2 = bus_2.Vnom if psse_elm.NOMV2 == 0 else psse_elm.NOMV2
        V3 = bus_3.Vnom if psse_elm.NOMV3 == 0 else psse_elm.NOMV3

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
                                 rate12=psse_elm.RATE1_1,
                                 rate23=psse_elm.RATE2_1,
                                 rate31=psse_elm.RATE3_1)

        tr3w.winding1.tap_phase = psse_elm.ANG1
        tr3w.winding2.tap_phase = psse_elm.ANG2
        tr3w.winding3.tap_phase = psse_elm.ANG3
        tr3w.compute_delta_to_star()

        return tr3w, 3

    else:
        raise Exception(str(psse_elm.windings) + ' number of windings!')


def get_gridcal_line(psse_elm: RawBranch,
                     psse_bus_dict: Dict[int, dev.Bus],
                     Sbase: float,
                     logger: Logger) -> dev.Line:
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

    protection_factor = psse_elm.RATE3 / psse_elm.RATE1 if psse_elm.RATE1 > 0.0 else 1.4

    if protection_factor == 0:
        protection_factor = 1.4

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
                      protection_rating_factor=round(protection_factor, 6),
                      active=bool(psse_elm.ST),
                      mttf=0,
                      mttr=0,
                      length=psse_elm.LEN)
    return branch


def get_hvdc_from_vscdc(psse_elm: RawVscDCLine,
                        psse_bus_dict: Dict[int, dev.Bus],
                        Sbase: float,
                        logger: Logger) -> Union[dev.HvdcLine, None]:
    """
    Get equivalent object
    :param psse_elm:
    :param psse_bus_dict:
    :param Sbase: Base power in MVA
    :param logger:
    :return:
    """
    IBUS1 = abs(psse_elm.IBUS1)
    IBUS2 = abs(psse_elm.IBUS2)

    if IBUS1 > 0 and IBUS2 > 0:
        bus1 = psse_bus_dict[IBUS1]
        bus2 = psse_bus_dict[IBUS2]

        name1 = psse_elm.NAME.replace("'", "").replace('/', '').strip()
        code = str(psse_elm.IBUS1) + '_' + str(psse_elm.IBUS2) + '_1'

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
                           code=code,
                           Pset=specified_power,
                           Vset_f=Vset_f,
                           Vset_t=Vset_t,
                           rate=rate)

        return obj
    else:

        logger.add_error("VscDCLine has no bus from or bus to, or is missing both", device=psse_elm.get_id())

        return None


def get_hvdc_from_twotermdc(psse_elm: RawTwoTerminalDCLine,
                            psse_bus_dict: Dict[int, dev.Bus],
                            Sbase: float,
                            logger: Logger) -> Union[dev.HvdcLine, None]:
    """

    :param psse_elm:
    :param psse_bus_dict:
    :param Sbase:
    :param logger:
    :return:
    """
    IPR = abs(psse_elm.IPR)
    IPI = abs(psse_elm.IPI)

    if IPR > 0 and IPI > 0:
        bus1 = psse_bus_dict[IPR]
        bus2 = psse_bus_dict[IPI]

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
        code = str(psse_elm.IPR) + '_' + str(psse_elm.IPI) + '_1'

        # set the HVDC line active
        active = bus1.active and bus2.active

        obj = dev.HvdcLine(bus_from=bus1,  # Rectifier as of PSSe
                           bus_to=bus2,  # inverter as of PSSe
                           active=active,
                           name=name1,
                           code=code,
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
    else:
        logger.add_error("HVDC2TermDC has no bus from or bus to, or is missing both", device=psse_elm.get_id())

        return None


def get_upfc_from_facts(psse_elm: RawFACTS,
                        psse_bus_dict: Dict[int, dev.Bus],
                        Sbase: float,
                        logger: Logger,
                        circuit: MultiCircuit):
    """
    Get equivalent object
    :param psse_elm:
    :param psse_bus_dict:
    :param Sbase:
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

    if abs(psse_elm.J) == 0:  # STATCOM device
        if mode == 0:
            active = False
        else:
            active = True

        # TODO add STATCOM obj

    elif abs(psse_elm.J) > 0:  # FACTS series device

        if mode == 0:
            active = False
        elif mode == 1 and abs(psse_elm.J) > 0:
            # shunt link
            sh = dev.Shunt(name='FACTS:' + name1, B=psse_elm.SHMX)
            circuit.add_shunt(bus1, sh)
            logger.add_warning('FACTS mode (shunt link) added as shunt', str(mode))

        elif mode == 2:
            # only shunt device: STATCOM
            logger.add_warning('FACTS mode (STATCOM) not implemented', str(mode))

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

            circuit.add_upfc(elm)

        elif mode == 4 and abs(psse_elm.J) > 0:
            # series and shunt links operating with series link at constant series voltage
            logger.add_warning('FACTS mode (series+shunt links) not implemented', str(mode))

        elif mode == 5 and abs(psse_elm.J) > 0:
            # master device of an IPFC with P and Q setpoints specified;
            # another FACTS device must be designated as the slave device
            # (i.e., its MODE is 6 or 8) of this IPFC.
            logger.add_warning('FACTS mode (IPFC) not implemented', str(mode))

        elif mode == 6 and abs(psse_elm.J) > 0:
            # 6 slave device of an IPFC with P and Q setpoints specified;
            #  the FACTS device specified in MNAME must be the master
            #  device (i.e., its MODE is 5 or 7) of this IPFC. The Q setpoint is
            #  ignored as the master device dictates the active power
            #  exchanged between the two devices.
            logger.add_warning('FACTS mode (IPFC) not implemented', str(mode))

        elif mode == 7 and abs(psse_elm.J) > 0:
            # master device of an IPFC with constant series voltage setpoints
            # specified; another FACTS device must be designated as the slave
            # device (i.e., its MODE is 6 or 8) of this IPFC
            logger.add_warning('FACTS mode (IPFC) not implemented', str(mode))

        elif mode == 8 and abs(psse_elm.J) > 0:
            # slave device of an IPFC with constant series voltage setpoints
            # specified; the FACTS device specified in MNAME must be the
            # master device (i.e., its MODE is 5 or 7) of this IPFC. The complex
            # Vd + jVq setpoint is modified during power flow solutions to reflect
            # the active power exchange determined by the master device
            logger.add_warning('FACTS mode (IPFC) not implemented', str(mode))

        else:
            return None
    else:
        return None


def psse_to_gridcal(psse_circuit: PsseCircuit,
                    logger: Logger,
                    branch_connection_voltage_tolerance: float = 0.1,
                    adjust_taps_to_discrete_positions: bool = False) -> MultiCircuit:
    """

    :param psse_circuit: PsseCircuit instance
    :param logger: Logger
    :param branch_connection_voltage_tolerance: tolerance in p.u. of a branch voltage to be considered a transformer
    :param adjust_taps_to_discrete_positions: Modify the tap angle and module to the discrete positions
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

        bus, bus_shunt = get_gridcal_bus(psse_bus=psse_bus,
                                         area_dict=area_dict,
                                         zone_dict=zones_dict,
                                         logger=logger)

        # bus.ensure_area_objects(circuit)

        if bus.type.value == 3:
            slack_buses.append(psse_bus.I)

        circuit.add_bus(bus)
        psse_bus_dict[psse_bus.I] = bus

        # legacy PSSe buses may have shunts declared within, so add them
        if bus_shunt is not None:
            circuit.add_shunt(bus=bus, api_obj=bus_shunt)

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
        if psse_load.I in psse_bus_dict:
            bus = psse_bus_dict[psse_load.I]
            api_obj = get_gridcal_load(psse_load, bus, logger)

            circuit.add_load(bus, api_obj)
        else:
            logger.add_error("Load bus is missing", psse_load.I, psse_load.I)

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
            api_obj = get_gridcal_shunt_switched(psse_shunt, bus, psse_bus_dict, logger)
            circuit.add_controllable_shunt(bus, api_obj)
        else:
            logger.add_error("Switched shunt bus missing", psse_shunt.I, psse_shunt.I)

    # Go through generators
    for psse_gen in psse_circuit.generators:
        bus = psse_bus_dict[psse_gen.I]
        api_obj = get_gridcal_generator(psse_gen, psse_bus_dict, logger)

        circuit.add_generator(bus, api_obj)
        api_obj.is_controlled = psse_gen.WMOD == 0 or psse_gen.WMOD == 1

    # Go through Branches
    branches_already_there = set()

    # Go through Transformers
    for psse_transformer in psse_circuit.transformers:
        # get the object
        transformer, n_windings = get_gridcal_transformer(
            psse_elm=psse_transformer,
            psse_bus_dict=psse_bus_dict,
            Sbase=psse_circuit.SBASE,
            logger=logger,
            adjust_taps_to_discrete_positions=adjust_taps_to_discrete_positions
        )

        if transformer.idtag not in branches_already_there:
            # Add to the circuit
            if n_windings == 2:
                circuit.add_transformer2w(transformer)
            elif n_windings == 3:
                circuit.add_transformer3w(transformer)
            else:
                raise Exception('Unsupported number of windings')
            branches_already_there.add(transformer.idtag)

        else:
            logger.add_warning('The RAW file has a repeated transformer and it is omitted from the model',
                               transformer.idtag)

    # Go through the Branches
    for psse_branch in psse_circuit.branches:
        # get the object
        branch = get_gridcal_line(psse_branch, psse_bus_dict, psse_circuit.SBASE, logger)

        # detect if this branch is actually a transformer
        if branch.should_this_be_a_transformer(branch_connection_voltage_tolerance, logger=logger):

            transformer = branch.get_equivalent_transformer(index=None)

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

        if branch is not None:
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

        if branch is not None:
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
            get_upfc_from_facts(psse_elm, psse_bus_dict, psse_circuit.SBASE, logger, circuit=circuit)

    # detect substation from the raw file
    detect_substations(grid=circuit)

    return circuit
