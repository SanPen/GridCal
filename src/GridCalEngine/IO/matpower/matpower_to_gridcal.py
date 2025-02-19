# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, Tuple
import numpy as np
import math
from GridCalEngine.IO.matpower.matpower_circuit import MatpowerCircuit
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import TapModuleControl, TapPhaseControl, ConverterControlType
import GridCalEngine.Devices as dev
from GridCalEngine.basic_structures import Logger


def convert_areas(circuit: MultiCircuit,
                  m_grid: MatpowerCircuit) -> Dict[int, Tuple[dev.Area, int]]:
    """
    Parse Matpower / FUBM Matpower area data into GridCal
    :param circuit: MultiCircuit instance
    :param m_grid: MatpowerCircuit
    :return: area index -> object dictionary
    """
    area_idx_dict: Dict[int, Tuple[dev.Area, int]] = dict()

    for i in range(len(m_grid.areas)):
        m_area = m_grid.areas[i]
        a = dev.Area(name='Area ' + str(m_area.area_i), code=str(m_area.area_i))
        area_idx_dict[m_area.area_i] = (a, m_area.bus_i)
        circuit.add_area(a)

    return area_idx_dict


def convert_buses(circuit: MultiCircuit,
                  m_grid: MatpowerCircuit,
                  area_idx_dict) -> Dict[int, dev.Bus]:
    """
    Parse Matpower / FUBM Matpower bus data into GridCal
    :param circuit: MultiCircuit instance
    :param m_grid: MatpowerCircuit
    :param area_idx_dict: area index -> object dictionary
    :return: bus index -> object dictionary
    """
    # define bus types
    PQ = 1
    PV = 2
    REF = 3
    NONE = 4

    # Buses
    bus_dict: Dict[int, dev.Bus] = dict()

    for i in range(len(m_grid.buses)):

        m_bus = m_grid.buses[i]

        # Create bus
        # area_idx = int(table[i, matpower_buses.BUS_AREA])
        # bus_idx = int(table[i, matpower_buses.BUS_I])
        is_slack = False

        if m_bus.bus_area in area_idx_dict.keys():
            area, ref_idx = area_idx_dict[m_bus.bus_area]
            if ref_idx == m_bus.bus_i:
                is_slack = True
        else:
            area = None

        code = str(m_bus.bus_i)

        bus = dev.Bus(name=m_bus.name,
                      code=code,
                      Vnom=m_bus.base_kv,
                      vmax=m_bus.vmax,
                      vmin=m_bus.vmin,
                      area=area,
                      is_slack=is_slack,
                      Vm0=m_bus.vm,
                      Va0=np.deg2rad(m_bus.va))

        # store the given bus index in relation to its real index in the table for later
        bus_dict[m_bus.bus_i] = bus

        # determine if the bus is set as slack manually
        bus.is_slack = m_bus.bus_type == REF

        # Add the bus to the circuit buses
        circuit.add_bus(bus)

        # Add the load
        if m_bus.pd != 0 or m_bus.qd != 0:
            load = dev.Load(P=m_bus.pd, Q=m_bus.qd)
            circuit.add_load(bus=bus, api_obj=load)

        # Add the shunt
        if m_bus.gs != 0 or m_bus.bs != 0:
            shunt = dev.Shunt(G=m_bus.gs, B=m_bus.bs)
            circuit.add_shunt(bus=bus, api_obj=shunt)

    return bus_dict


def convert_dc_buses(circuit: MultiCircuit,
                     m_grid: MatpowerCircuit,
                     area_idx_dict,
                     freq=50.0) -> Dict[int, dev.Bus]:
    """
    Parse Matpower / FUBM Matpower bus data into GridCal
    :param circuit: MultiCircuit instance
    :param m_grid: MatpowerCircuit
    :param area_idx_dict: area index -> object dictionary
    :param freq: frequency in Hz
    :return: bus index -> object dictionary
    """

    # Buses
    bus_dict: Dict[int, dev.Bus] = dict()

    for m_bus in m_grid.dc_buses:

        code = str(m_bus.busdc_i)

        bus = dev.Bus(name=code,
                      code=code,
                      is_dc=True,
                      Vnom=m_bus.base_kvdc,
                      vmax=m_bus.vdcmax,
                      vmin=m_bus.vdcmin,
                      Vm0=m_bus.vdc,
                      Va0=0)

        # store the given bus index in relation to its real index in the table for later
        bus_dict[m_bus.busdc_i] = bus

        # Add the bus to the circuit buses
        circuit.add_bus(bus)

        # Add the load
        if m_bus.pdc != 0:
            load = dev.Load(P=m_bus.pdc, Q=0)
            circuit.add_load(bus=bus, api_obj=load)

        # Add the shunt (not used in power flow...)
        # if m_bus.cdc != 0:
        #     g = 1e-6 * 2.0 * np.pi * freq * (m_bus.base_kvdc * 1e3) ** 2  # MW @ v=1 p.u.
        #     shunt = dev.Shunt(G=g, B=0.0)
        #     circuit.add_shunt(bus=bus, api_obj=shunt)

    return bus_dict


def convert_generators(circuit: MultiCircuit,
                       m_grid: MatpowerCircuit,
                       bus_idx_dict: Dict[int, dev.Bus]):
    """
    Parse Matpower / FUBM Matpower generator data into GridCal
    :param circuit: MultiCircuit instance
    :param m_grid: MatpowerCircuit
    :param bus_idx_dict: matpower bus index -> object dictionary
    :return:
    """

    for m_gen in m_grid.generators:
        # TODO: Calculate pf based on reactive_power
        gen = dev.Generator(name=m_gen.name,
                            P=float(m_gen.pg),
                            vset=float(m_gen.vg),
                            Qmax=float(m_gen.qmax),
                            Qmin=float(m_gen.qmin),
                            active=bool(m_gen.gen_status),
                            Pmin=float(m_gen.pmin),
                            Pmax=float(m_gen.pmax),
                            Cost0=float(m_gen.Cost0),
                            Cost=float(m_gen.Cost),
                            Cost2=float(m_gen.Cost2),
                            )

        # Add the generator to the bus
        gen.bus = bus_idx_dict[int(m_gen.gen_bus)]
        circuit.add_generator(bus=gen.bus, api_obj=gen)


def convert_branches(circuit: MultiCircuit,
                     m_grid: MatpowerCircuit,
                     bus_idx_dict: Dict[int, dev.Bus],
                     logger: Logger):
    """
    Parse Matpower / FUBM Matpower branch data into GridCal
    :param circuit: MultiCircuit instance
    :param m_grid: MatpowerCircuit
    :param bus_idx_dict: bus index -> object dictionary
    :param logger: Logger
    :return: Nothing
    """

    for br in m_grid.branches:

        bus_f = bus_idx_dict[br.f_bus]
        bus_t = bus_idx_dict[br.t_bus]
        code = "{0}_{1}_1".format(br.f_bus, br.t_bus)

        if br.is_fubm:  # FUBM model

            # converter type (I, II, III)
            matpower_converter_mode = br.conv_a

            # determine the converter control mode
            Pfset = br.pf
            Ptset = br.pt
            Vt_set = br.vt_set
            Vf_set = br.vf_set  # dc voltage
            Qfset = br.qf
            Qtset = br.qt
            m = br.tap if br.tap > 0 else 1.0
            tap_phase = np.deg2rad(br.shift)
            v_set = 1.0
            Pset = 0.0
            Qset = 0.0
            control_bus = None

            is_transformer = (bus_f.Vnom != bus_t.Vnom or
                              (br.tap != 1.0 and br.tap != 0) or
                              br.shift != 0.0 or
                              Pfset != 0.0 or
                              Ptset != 0.0 or
                              Qtset != 0.0 or
                              Qfset != 0.0 or
                              Vf_set != 0.0 or
                              Vt_set != 0.0)

            # tau based controls
            if Pfset != 0.0:
                tap_phase_control_mode = TapPhaseControl.Pf
                Pset = Pfset
            elif Ptset != 0.0:
                tap_phase_control_mode = TapPhaseControl.Pt
                Pset = Ptset
            else:
                tap_phase_control_mode = TapPhaseControl.fixed

            # m based controls
            if Qtset != 0.0:
                tap_module_control_mode = TapModuleControl.Qt
                Qset = Qtset
            elif Qfset != 0.0:
                tap_module_control_mode = TapModuleControl.Qf
                Qset = Qtset
            elif Vt_set != 0.0:
                tap_module_control_mode = TapModuleControl.Vm
                v_set = Vt_set
                control_bus = bus_t
            elif Vf_set != 0.0:
                tap_module_control_mode = TapModuleControl.Vm
                v_set = Vf_set
                control_bus = bus_f
            else:
                tap_module_control_mode = TapModuleControl.fixed

            if matpower_converter_mode > 0:  # it is a converter

                """
                FUBM control chart

                Type I are the ones making Qf = 0, therefore each DC grid must have at least one
                Type II control the voltage, and DC grids must have at least one
                Type III are the droop controlled ones, there may be one

                Control Mode    Constraint1     Constraint2     VSC type
                1               Pf              vdc -> Vf       I
                2               Pf              Qac -> Qt       I   
                3               Pf              vac -> Vt       I

                4               vdc -> Vf       Qac -> Qt       II
                5               vdc -> Vf       vac -> Vt       II

                6               vdc droop       Qac -> Qt       III
                7               vdc droop       vac -> Vt       III

                """
                control1 = None
                control2 = None
                control1val = 0.0
                control2val = 0.0

                # tau based controls
                if Pfset != 0.0:
                    control1 = ConverterControlType.Pdc
                    control1val = Pfset
                elif Ptset != 0.0:
                    control1 = ConverterControlType.Pac
                    control1val = Ptset
                else:
                    control1 = ConverterControlType.Qac
                    control1val = 0.0

                # m based controls
                if Qtset != 0.0:
                    control2 = ConverterControlType.Qac
                    control2val = Qtset
                elif Qfset != 0.0:
                    control2 = ConverterControlType.Qac
                    control2val = 0.0
                elif Vt_set != 0.0:
                    control2 = ConverterControlType.Vm_ac
                    control2val = Vt_set
                elif Vf_set != 0.0:
                    control2 = ConverterControlType.Vm_dc
                    control2val = Vf_set
                else:
                    control2 = ConverterControlType.Qac
                    control2val = 0.0

                # set the from bus as a DC bus
                # this is by design of the matpower FUBM model,
                # if it is a converter,
                # the DC bus is always the "from" bus
                bus_f.is_dc = True

                if matpower_converter_mode == 1:  # Type I: normal converter
                    pass

                elif matpower_converter_mode == 2:  # Type II: voltage controlling converter (slack converter)
                    pass

                elif matpower_converter_mode == 3:  # Type III: Power-voltage droop
                    pass

                else:
                    pass

                rate = np.max([br.rate_a, br.rate_b, br.rate_c])

                if rate == 0.0:
                    # in matpower rate=0 means not limited by rating
                    rate = 10000
                    monitor_loading = False
                else:
                    monitor_loading = True

                # TODO: Figure this one out
                branch = dev.VSC(bus_from=bus_f,
                                 bus_to=bus_t,
                                 code=code,
                                 name='VSC' + str(len(circuit.vsc_devices) + 1),
                                 active=bool(br.br_status),
                                 # r=table[i, matpower_branches.BR_R],
                                 # x=table[i, matpower_branches.BR_X],
                                 # tap_module=m,
                                 # tap_module_max=table[i, matpower_branches.MA_MAX],
                                 # tap_module_min=table[i, matpower_branches.MA_MIN],
                                 # tap_phase=tap_phase,
                                 # tap_phase_max=np.deg2rad(table[i, matpower_branches.SH_MAX]),
                                 # tap_phase_min=np.deg2rad(table[i, matpower_branches.SH_MIN]),
                                 # G0sw=table[i, matpower_branches.GSW],
                                 # Beq=table[i, matpower_branches.BEQ],
                                 # Beq_max=table[i, matpower_branches.BEQ_MAX],
                                 # Beq_min=table[i, matpower_branches.BEQ_MIN],
                                 rate=rate,
                                 kdp=br.kdp,
                                 k=br.k2,
                                 # tap_phase_control_mode=tap_phase_control_mode,
                                 # tap_module_control_mode=tap_module_control_mode,
                                 # Pset=Pset,
                                 # Qset=Qset,
                                 # vset=v_set,
                                 alpha1=br.alpha1,
                                 alpha2=br.alpha2,
                                 alpha3=br.alpha3,
                                 monitor_loading=monitor_loading,
                                 control1=control1,
                                 control2=control2,
                                 control1_val=control1val,
                                 control2_val=control2val)

                branch.regulation_bus = control_bus

                circuit.add_vsc(obj=branch)

                logger.add_info('Branch as converter', f'Branch {code}')

            elif is_transformer:

                rate = br.rate_a

                if rate == 0.0:
                    # in matpower rate=0 means not limited by rating
                    rate = 10000.0
                    monitor_loading = False
                else:
                    monitor_loading = True

                branch = dev.Transformer2W(bus_from=bus_f,
                                           bus_to=bus_t,
                                           code=code,
                                           name=code,
                                           r=float(br.br_r),
                                           x=float(br.br_x),
                                           g=0.0,
                                           b=float(br.br_b),
                                           rate=rate,
                                           active=bool(br.br_status),
                                           monitor_loading=monitor_loading,
                                           tap_module=m,
                                           tap_module_max=float(br.ma_max),
                                           tap_module_min=float(br.ma_min),
                                           tap_phase=tap_phase,
                                           tap_phase_max=np.deg2rad(br.sh_max),
                                           tap_phase_min=np.deg2rad(br.sh_min),
                                           tap_phase_control_mode=tap_phase_control_mode,
                                           tap_module_control_mode=tap_module_control_mode,
                                           Pset=Pset,
                                           Qset=Qset,
                                           vset=v_set)
                branch.regulation_bus = control_bus
                circuit.add_transformer2w(obj=branch)
                logger.add_info('Branch as 2w transformer', f'Branch {code}')

            else:
                rate = br.rate_a

                if rate == 0.0:
                    # in matpower rate=0 means not limited by rating
                    rate = 10000
                    monitor_loading = False
                else:
                    monitor_loading = True

                branch = dev.Line(bus_from=bus_f,
                                  bus_to=bus_t,
                                  code=code,
                                  name=code,
                                  r=float(br.br_r),
                                  x=float(br.br_x),
                                  b=float(br.br_b),
                                  rate=rate,
                                  monitor_loading=monitor_loading,
                                  active=bool(br.br_status))
                circuit.add_line(obj=branch, logger=logger)
                logger.add_info('Branch as line', f'Branch {code}')

        else:

            if (bus_f.Vnom != bus_t.Vnom or
                    (br.tap != 1.0 and br.tap != 0) or
                    br.shift != 0.0):

                rate = br.rate_a

                if rate == 0.0:
                    # in matpower rate=0 means not limited by rating
                    rate = 10000.0
                    monitor_loading = False
                    logger.add_info('Branch not limited by rating', f'Branch {code}')
                else:
                    monitor_loading = True

                branch = dev.Transformer2W(bus_from=bus_f,
                                           bus_to=bus_t,
                                           code=code,
                                           name=code,
                                           r=float(br.br_r),
                                           x=float(br.br_x),
                                           g=0.0,
                                           b=float(br.br_b),
                                           rate=rate,
                                           monitor_loading=monitor_loading,
                                           tap_module=float(br.tap),
                                           tap_phase=np.deg2rad(br.shift),  # * np.pi / 180,
                                           active=bool(br.br_status))
                circuit.add_transformer2w(obj=branch)
                logger.add_info('Branch as 2w transformer', f'Branch {code}')

            else:

                rate = br.rate_a

                if rate == 0.0:
                    # in matpower rate=0 means not limited by rating
                    rate = 10000
                    monitor_loading = False
                else:
                    monitor_loading = True

                branch = dev.Line(bus_from=bus_f,
                                  bus_to=bus_t,
                                  code=code,
                                  name=code,
                                  r=float(br.br_r),
                                  x=float(br.br_x),
                                  b=float(br.br_b),
                                  rate=rate,
                                  monitor_loading=monitor_loading,
                                  active=bool(br.br_status))
                circuit.add_line(obj=branch, logger=logger)
                logger.add_info('Branch as line', f'Branch {code}')

    # convert normal lines into DC-lines if needed
    for line in circuit.lines:

        if line.bus_to.is_dc and line.bus_from.is_dc:
            dc_line = dev.DcLine(bus_from=line.bus_from,
                                 bus_to=line.bus_to,
                                 code=line.code,
                                 name=line.name,
                                 active=line.active,
                                 rate=line.rate,
                                 r=line.R)

            dc_line.active_prof = line.active_prof
            dc_line.rate_prof = line.rate_prof

            # add device to the circuit
            circuit.add_dc_line(obj=dc_line)

            # delete the line from the circuit
            circuit.delete_line(line)
            logger.add_info('Converted to DC line', line.name)


def convert_dc_branches(circuit: MultiCircuit,
                        m_grid: MatpowerCircuit,
                        dc_bus_dict: Dict[int, dev.Bus],
                        logger: Logger):
    """

    :param circuit:
    :param m_grid:
    :param dc_bus_dict:
    :param logger:
    :return:
    """
    for br in m_grid.dc_branches:

        bus_f = dc_bus_dict[br.fbusdc]
        bus_t = dc_bus_dict[br.tbusdc]
        code = "{0}_{1}_1".format(br.fbusdc, br.tbusdc)

        if bus_f.Vnom != bus_t.Vnom:

            rate = br.rate_a

            if rate == 0.0:
                # in matpower rate=0 means not limited by rating
                rate = 10000
                monitor_loading = False
            else:
                monitor_loading = True

            branch = dev.Transformer2W(bus_from=bus_f,
                                       bus_to=bus_t,
                                       code=code,
                                       name=code,
                                       r=float(br.r),
                                       # x=float(br.br_x),
                                       g=0.0,
                                       # b=float(br.br_b),
                                       rate=rate,
                                       monitor_loading=monitor_loading,
                                       active=bool(br.status))
            circuit.add_transformer2w(obj=branch)
            logger.add_info('Branch as 2w transformer', f'Branch {code}')

        else:

            rate = br.rate_a

            if rate == 0.0:
                # in matpower rate=0 means not limited by rating
                rate = 10000
                monitor_loading = False
            else:
                monitor_loading = True

            branch = dev.DcLine(bus_from=bus_f,
                                bus_to=bus_t,
                                code=code,
                                name=code,
                                r=float(br.r),
                                rate=rate,
                                monitor_loading=monitor_loading,
                                active=bool(br.status))
            circuit.add_dc_line(obj=branch)
            logger.add_info('Branch as line', f'Branch {code}')


def convert_converters(circuit: MultiCircuit,
                       m_grid: MatpowerCircuit,
                       bus_dict: Dict[int, dev.Bus],
                       dc_bus_dict: Dict[int, dev.Bus],
                       logger: Logger):
    for br in m_grid.converters:

        bus_f = dc_bus_dict[br.busdc_i]
        bus_t = bus_dict[br.busac_i]

        code = "{0}_{1}_1".format(br.busdc_i, br.busac_i)

        rate = br.imax * bus_t.Vnom * np.sqrt(3)  # using the current at the AC side

        if rate == 0.0:
            # in matpower rate=0 means not limited by rating
            rate = 10000.0
            monitor_loading = False
        else:
            monitor_loading = True

        if br.type_dc == 1 and br.type_ac == 1:
            control1 = ConverterControlType.Pac
            control1_val = -1 * br.p_g
            control2 = ConverterControlType.Qac
            control2_val = -1 * br.q_g

        elif br.type_dc == 1 and br.type_ac == 2:
            control1 = ConverterControlType.Pac
            control1_val = -1 * br.p_g
            control2 = ConverterControlType.Vm_ac
            control2_val = br.vtar

        elif br.type_dc == 2 and br.type_ac == 1:
            control1 = ConverterControlType.Vm_dc
            control1_val = br.vtar
            control2 = ConverterControlType.Qac
            control2_val = -1 * br.q_g

        else:
            control1 = ConverterControlType.Pac
            control1_val = -1 * br.p_g
            control2 = ConverterControlType.Qac
            control2_val = -1 * br.q_g

        """
        convmode    =   sign(Pc);       %% converter operation mode
        rectifier   =   convmode>0;
        inverter    =   convmode<0;
        """
        Ibase = m_grid.Sbase/ (math.sqrt(3) * br.base_kvac)
        if br.p_g > 0:
            alpha3 = br.loss_crec*Ibase**2/m_grid.Sbase
        else:
            alpha3 = br.loss_cinv*Ibase**2/m_grid.Sbase

        alpha2 = br.loss_b*Ibase/m_grid.Sbase
        alpha1 = br.loss_a/m_grid.Sbase

        branch = dev.VSC(
            bus_from=bus_f,
            bus_to=bus_t,
            code=code,
            name=code,
            rate=rate,
            monitor_loading=monitor_loading,
            active=bool(br.status),
            alpha3=alpha3,
            alpha2=alpha2,
            alpha1=alpha1,
            kdp=br.droop,
            control1=control1,
            control1_val=control1_val,
            control2=control2,
            control2_val=control2_val
        )

        circuit.add_vsc(obj=branch)
        logger.add_info('Branch as 2w transformer', f'Branch {code}')


def matpower_to_gridcal(m_grid: MatpowerCircuit, logger: Logger) -> MultiCircuit:
    """

    :param m_grid:
    :param logger:
    :return:
    """
    grid = MultiCircuit()
    grid.Sbase = m_grid.Sbase

    # register the parsing logs
    logger += m_grid.logger

    area_dict = convert_areas(grid, m_grid)
    bus_dict = convert_buses(grid, m_grid, area_dict)

    dc_bus_dict = convert_dc_buses(grid, m_grid, area_dict, freq=50.0)

    convert_generators(grid, m_grid, bus_dict)

    convert_branches(grid, m_grid, bus_dict, logger)

    convert_converters(grid, m_grid, bus_dict, dc_bus_dict, logger)

    convert_dc_branches(grid, m_grid, dc_bus_dict, logger)

    return grid
