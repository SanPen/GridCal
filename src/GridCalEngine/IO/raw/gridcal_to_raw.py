# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math

import numpy as np
from typing import Dict
from itertools import groupby
from scipy.sparse import lil_matrix

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.raw.devices import (RawArea, RawZone, RawBus, RawLoad, RawFixedShunt, RawGenerator,
                                          RawSwitchedShunt, RawTransformer, RawBranch, RawVscDCLine,
                                          RawTwoTerminalDCLine, RawFACTS)
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import (TapChangerTypes,
                                        TapPhaseControl,
                                        TapModuleControl)


def get_area(area: dev.Area, i: int) -> RawArea:
    """

    :param area:
    :param i:
    :return:
    """
    result = RawArea()
    result.ARNAME = area.name
    result.I = i
    return result


def get_zone(zone: dev.Zone, i: int) -> RawZone:
    """

    :param zone:
    :param i:
    :return:
    """
    result = RawZone()
    result.ZONAME = zone.name
    result.I = i
    return result


def get_psse_bus(bus: dev.Bus,
                 area_dict: Dict[dev.Area, int],
                 zones_dict: Dict[dev.Zone, int],
                 suggested_psse_number: int) -> RawBus:
    """

    :param bus:
    :param area_dict:
    :param zones_dict:
    :param suggested_psse_number:
    :return:
    """
    psse_bus = RawBus()
    psse_bus.NAME = str(bus.name)
    psse_bus.BASKV = bus.Vnom

    psse_bus.I = suggested_psse_number

    psse_bus.EVLO = bus.Vmin
    psse_bus.EVHI = bus.Vmax

    psse_bus.AREA = area_dict.get(bus.area, 0)
    psse_bus.ZONE = zones_dict.get(bus.zone, 0)
    psse_bus.VM = bus.Vm0
    psse_bus.VA = np.rad2deg(bus.Va0)

    psse_bus.IDE = bus.type.value

    return psse_bus


def get_psse_load(load: dev.Load, bus_dict: Dict[dev.Bus, int], id_number: int) -> RawLoad:
    """

    :param load:
    :param bus_dict:
    :param id_number:
    :return:
    """
    psse_load = RawLoad()

    psse_load.I = bus_dict[load.bus]
    psse_load.ID = id_number

    psse_load.YP = load.G
    psse_load.YQ = load.B
    psse_load.IP = load.Ir
    psse_load.IQ = -load.Ii
    psse_load.PL = load.P
    psse_load.QL = load.Q
    psse_load.STATUS = 1 if load.active else 0
    psse_load.SCALE = 1.0 if load.scalable else 0.0

    return psse_load


def get_psse_load_from_external_grid(load: dev.ExternalGrid, bus_dict: Dict[dev.Bus, int], id_number: int) -> RawLoad:
    """

    :param load:
    :param bus_dict:
    :param id_number:
    :return:
    """
    psse_load = RawLoad()

    psse_load.I = bus_dict[load.bus]
    psse_load.ID = id_number

    psse_load.PL = load.P
    psse_load.QL = load.Q
    psse_load.STATUS = 1 if load.active else 0

    return psse_load


def get_psse_fixed_shunt(shunt: dev.Shunt, bus_dict: Dict[dev.Bus, int], id_number: int) -> RawFixedShunt:
    """

    :param shunt:
    :param bus_dict:
    :param id_number:
    :return:
    """
    psse_shunt = RawFixedShunt()

    psse_shunt.I = bus_dict[shunt.bus]
    psse_shunt.ID = id_number

    psse_shunt.GL = shunt.G
    psse_shunt.BL = shunt.B

    psse_shunt.STATUS = 1 if shunt.active else 0

    return psse_shunt


def get_psse_switched_shunt(shunt: dev.ControllableShunt,
                            bus_dict: Dict[dev.Bus, int]) -> RawSwitchedShunt:
    """

    :param shunt:
    :param bus_dict:
    :return:
    """
    psse_switched_shunt = RawSwitchedShunt()

    psse_switched_shunt.I = bus_dict[shunt.bus]

    psse_switched_shunt.STATUS = 1 if shunt.active else 0

    psse_switched_shunt.BINIT = shunt.B
    psse_switched_shunt.STAT = int(shunt.active)

    if shunt.control_bus is not None and shunt.control_bus != shunt.bus:
        psse_switched_shunt.SWREG = bus_dict.get(shunt.control_bus, 0)

    if len(shunt.b_steps) > 0:
        diff_list = np.insert(np.diff(shunt.b_steps), 0, shunt.b_steps[0])
        aggregated_steps = [(sum(1 for _ in group), key) for key, group in groupby(diff_list)]

        for index, aggregated_step in enumerate(aggregated_steps):
            if index < 8:
                setattr(psse_switched_shunt, f'S{index + 1}', 1)
                setattr(psse_switched_shunt, f'N{index + 1}', aggregated_step[0])
                setattr(psse_switched_shunt, f'B{index + 1}', aggregated_step[1])

    return psse_switched_shunt


def get_psse_generator(generator: dev.Generator, bus_dict: Dict[dev.Bus, int], id_number: int) -> RawGenerator:
    """

    :param generator:
    :param bus_dict:
    :param id_number:
    :return:
    """
    psse_generator = RawGenerator()

    psse_generator.I = bus_dict[generator.bus]
    psse_generator.ID = id_number

    if generator.control_bus is not None and generator.control_bus != generator.bus:
        psse_generator.IREG = bus_dict.get(generator.control_bus, 0)

    psse_generator.PG = generator.P
    psse_generator.VS = generator.Vset
    psse_generator.QB = generator.Qmin
    psse_generator.QT = generator.Qmax
    psse_generator.MBASE = generator.Snom
    psse_generator.PT = generator.Pmax
    psse_generator.PB = generator.Pmin
    psse_generator.STAT = 1 if generator.active else 0
    psse_generator.WPF = generator.Pf

    return psse_generator


def get_psse_transformer2w(transformer: dev.Transformer2W,
                           bus_dict: Dict[dev.Bus, int],
                           ckt: int) -> RawTransformer:
    """

    :param transformer:
    :param bus_dict:
    :param ckt:
    :return:
    """
    psse_transformer = RawTransformer()
    psse_transformer.windings = 2

    psse_transformer.idtag = transformer.idtag
    psse_transformer.STAT = 1 if transformer.active else 0

    psse_transformer.SBASE1_2 = transformer.Sn
    psse_transformer.RATE1_1 = transformer.rate
    psse_transformer.RATE1_2 = transformer.rate * transformer.contingency_factor
    psse_transformer.RATE1_3 = transformer.rate * transformer.protection_rating_factor

    # i, j, ckt = transformer.code.split("_", 2)
    psse_transformer.I = bus_dict[transformer.bus_from]
    psse_transformer.J = bus_dict[transformer.bus_to]
    psse_transformer.CKT = ckt

    psse_transformer.CW = 1
    # WINDV1 is the Winding 1 off-nominal turns ratio in pu of Winding1 bus base voltage
    mf, mt = transformer.get_virtual_taps()
    psse_transformer.WINDV1 = transformer.tap_module * mf / mt
    psse_transformer.WINDV2 = 1.0

    V1, V2, _ = transformer.get_from_to_nominal_voltages()
    psse_transformer.NOMV1 = V1
    psse_transformer.NOMV2 = V2 if V2 != V1 else 0.0

    psse_transformer.CZ = 1
    # 1 for resistance and reactance in pu on system MVA base and winding voltage base
    # translating: impedances in the system base, do noting
    psse_transformer.R1_2 = transformer.R
    psse_transformer.X1_2 = transformer.X

    psse_transformer.CM = 1
    # 1 for complex  admittance  in pu  on  system  MVA  base  and Winding 1 bus voltage base
    psse_transformer.MAG1 = transformer.G
    psse_transformer.MAG2 = transformer.B

    # tap changer values
    psse_transformer.NTP1 = transformer.tap_changer.total_positions
    psse_transformer.VMA1 = transformer.tap_changer.get_tap_module_max()
    psse_transformer.VMI1 = transformer.tap_changer.get_tap_module_min()

    psse_transformer.ANG1 = np.rad2deg(transformer.tap_phase)

    # Control types
    if transformer.tap_changer.tc_type == TapChangerTypes.NoRegulation:

        psse_transformer.COD1 = 0

    elif transformer.tap_changer.tc_type == TapChangerTypes.VoltageRegulation:

        if transformer.tap_module_control_mode == TapModuleControl.fixed:
            psse_transformer.COD1 = -1
        else:
            psse_transformer.COD1 = 1

    elif transformer.tap_changer.tc_type == TapChangerTypes.Symmetrical:

        if transformer.tap_phase_control_mode == TapPhaseControl.fixed:
            psse_transformer.COD1 = -3
        else:
            psse_transformer.COD1 = 3

        # RMA - Phase shift angle in degrees when |COD1| is 3 or 5. No default is allowed
        number_of_symmetrical_step = (transformer.tap_changer.total_positions - 1) / 2
        psse_transformer.RMA1 = 2 * math.degrees(math.atan(
             number_of_symmetrical_step * transformer.tap_changer.dV / 2
        ))

    elif transformer.tap_changer.tc_type == TapChangerTypes.Asymmetrical:

        if (transformer.tap_module_control_mode == TapModuleControl.fixed or
                transformer.tap_phase_control_mode == TapPhaseControl.fixed):
            psse_transformer.COD1 = -5
        else:
            psse_transformer.COD1 = 5
        psse_transformer.CNXA1 = transformer.tap_changer.asymmetry_angle

    else:
        pass

    return psse_transformer


def get_psse_transformer3w(transformer: dev.Transformer3W,
                           bus_dict: Dict[dev.Bus, int]) -> RawTransformer:
    """

    :param transformer:
    :param bus_dict:
    :return:
    """
    psse_transformer = RawTransformer()
    psse_transformer.windings = 3

    psse_transformer.NOMV1 = transformer.V1
    psse_transformer.NOMV2 = transformer.V2
    psse_transformer.NOMV3 = transformer.V3

    psse_transformer.idtag = transformer.idtag
    psse_transformer.STAT = 1 if transformer.active else 0

    psse_transformer.NAME = transformer.name
    psse_transformer.RATE1_1 = transformer.rate1
    psse_transformer.RATE2_1 = transformer.rate2
    psse_transformer.RATE3_1 = transformer.rate3

    psse_transformer.RATE1_2 = transformer.rate1 * transformer.winding1.contingency_factor
    psse_transformer.RATE2_2 = transformer.rate2 * transformer.winding2.contingency_factor
    psse_transformer.RATE3_2 = transformer.rate3 * transformer.winding3.contingency_factor

    psse_transformer.RATE1_3 = transformer.rate1 * transformer.winding1.protection_rating_factor
    psse_transformer.RATE2_3 = transformer.rate2 * transformer.winding2.protection_rating_factor
    psse_transformer.RATE3_3 = transformer.rate3 * transformer.winding3.protection_rating_factor

    psse_transformer.ANG1 = transformer.winding1.tap_phase
    psse_transformer.ANG2 = transformer.winding2.tap_phase
    psse_transformer.ANG3 = transformer.winding3.tap_phase

    i, j, k, ckt = transformer.code.split("_", 3)

    psse_transformer.I = bus_dict[transformer.bus1]
    psse_transformer.J = bus_dict[transformer.bus2]
    psse_transformer.K = bus_dict[transformer.bus3]
    psse_transformer.CKT = ckt

    psse_transformer.R1_2 = transformer.r12
    psse_transformer.X1_2 = transformer.x12
    psse_transformer.R2_3 = transformer.r23
    psse_transformer.X2_3 = transformer.x23
    psse_transformer.R3_1 = transformer.r31
    psse_transformer.X3_1 = transformer.x31

    return psse_transformer


def get_psse_branch(branch: dev.Line, bus_dict: Dict[dev.Bus, int], ckt: int) -> RawBranch:
    """

    :param branch:
    :param bus_dict:
    :param ckt:
    :return:
    """
    psse_branch = RawBranch()

    # i, j, ckt = line.code.split("_", 2)

    psse_branch.I = bus_dict[branch.bus_from]
    psse_branch.J = bus_dict[branch.bus_to]

    psse_branch.CKT = ckt

    psse_branch.NAME = branch.name
    psse_branch.R = branch.R
    psse_branch.X = branch.X
    psse_branch.B = branch.B
    psse_branch.ST = 1 if branch.active else 0
    psse_branch.idtag = branch.idtag
    psse_branch.LEN = branch.length
    psse_branch.RATE1 = branch.rate
    psse_branch.RATE2 = branch.rate * branch.contingency_factor
    psse_branch.RATE3 = branch.rate * branch.protection_rating_factor

    return psse_branch


def get_vsc_dc_line(hvdc_line: dev.HvdcLine, bus_dict: Dict[dev.Bus, int]) -> RawVscDCLine:
    """

    :param hvdc_line:
    :param bus_dict:
    :return:
    """
    psse_vsc_dc_line = RawVscDCLine()
    psse_vsc_dc_line.NAME = hvdc_line.name
    psse_vsc_dc_line.ACSET1 = hvdc_line.Vset_f
    psse_vsc_dc_line.ACSET2 = hvdc_line.Vset_t

    V1 = hvdc_line.bus_from.Vnom * psse_vsc_dc_line.ACSET1
    V2 = hvdc_line.bus_to.Vnom * psse_vsc_dc_line.ACSET2
    dV = (V1 - V2) * 1000.0
    P = hvdc_line.Pset / 1e-6
    psse_vsc_dc_line.RDC = dV * dV / P if P != 0 else 0

    return psse_vsc_dc_line


def get_psse_two_terminal_dc_line(hvdc_line: dev.HvdcLine,
                                  bus_dict: Dict[dev.Bus, int]) -> RawTwoTerminalDCLine:
    """

    :param hvdc_line:
    :param bus_dict:
    :return:
    """
    psse_two_terminal_dc_line = RawTwoTerminalDCLine()
    psse_two_terminal_dc_line.NAME = hvdc_line.name

    psse_two_terminal_dc_line.IPR = bus_dict[hvdc_line.bus_from]
    psse_two_terminal_dc_line.IPI = bus_dict[hvdc_line.bus_to]

    psse_two_terminal_dc_line.RDC = hvdc_line.r
    psse_two_terminal_dc_line.ANMNR = np.rad2deg(hvdc_line.min_firing_angle_f)
    psse_two_terminal_dc_line.ANMXR = np.rad2deg(hvdc_line.max_firing_angle_f)
    psse_two_terminal_dc_line.ANMNI = np.rad2deg(hvdc_line.min_firing_angle_t)
    psse_two_terminal_dc_line.ANMXI = np.rad2deg(hvdc_line.max_firing_angle_t)

    return psse_two_terminal_dc_line


def get_psse_facts(upfc: dev.UPFC, bus_dict: Dict[dev.Bus, int]) -> RawFACTS:
    """

    :param upfc:
    :param bus_dict:
    :return:
    """
    psse_facts = RawFACTS()
    psse_facts.NAME = upfc.name

    id_tag = upfc.idtag[:-2] if upfc.idtag.endswith("_1") else upfc.idtag
    # i, j = id_tag.split("_", 2)

    psse_facts.I = bus_dict[upfc.bus_from]
    psse_facts.J = bus_dict[upfc.bus_to]
    psse_facts.SET1 = upfc.R
    psse_facts.SHMX = 1 / upfc.Xsh if upfc.Xsh > 0 else 0.0
    psse_facts.VSET = upfc.Vsh
    psse_facts.PDES = upfc.Pfset
    psse_facts.QDES = upfc.Qfset
    psse_facts.IMX = upfc.rate - 1e-20

    return psse_facts


class RawCounter:
    """
    Items to count stuff for the raw files
    """

    def __init__(self, grid: MultiCircuit):
        """
        Constructor
        :param grid: MultiCircuit
        """
        n = grid.get_bus_number()
        self._bus_int_dict = {bus: i + 1 for i, bus in enumerate(grid.get_buses())}
        self._bus_2_psseI_dict = dict()
        self._bus_dev_count_dict = {bus: 0 for bus in grid.get_buses()}
        self._ckt_counter = lil_matrix((n + 1, n + 1), dtype=int)

        self._max_bus_number = 1

    @property
    def psse_numbers_dict(self) -> Dict[dev.Bus, int]:
        """

        :return:
        """
        return self._bus_2_psseI_dict

    def register_psse_number(self, bus: dev.Bus, psse_I: int):
        """

        :param bus:
        :param psse_I:
        :return:
        """
        self._max_bus_number = max(self._max_bus_number, psse_I)

        if psse_I in self._bus_2_psseI_dict.keys():
            print("Repeated PSSe bus!!!")

        self._bus_2_psseI_dict[bus] = psse_I

    def get_next_psse_number(self):
        """

        :return:
        """
        return self._max_bus_number + 1

    def get_suggested_psse_number(self, bus: dev.Bus, logger: Logger) -> int:
        """

        :param bus:
        :param logger:
        :return:
        """
        try:
            psse_I = int(bus.code)

            if psse_I in self._bus_2_psseI_dict.keys():
                psse_I_pre = psse_I
                # repeated number, get a new one
                psse_I = self.get_next_psse_number()
                logger.add_error("Repeated PSSe number",
                                 device=bus.name,
                                 value=psse_I_pre,
                                 expected_value=psse_I)

        except ValueError:
            psse_I = self.get_next_psse_number()
            logger.add_error("Invalid PSSe number stored in bus.code",
                             device=bus.name,
                             value=str(bus.code),
                             expected_value=psse_I)

        self.register_psse_number(bus, psse_I)

        return psse_I

    def get_id(self, bus: dev.Bus) -> int:
        """
        Query the dictionary for the internal number and increase that number for the next time
        :param bus: Bus
        :return: integer
        """
        id_number = self._bus_dev_count_dict[bus] + 1
        self._bus_dev_count_dict[bus] = id_number
        return id_number

    def get_ckt(self, branch: BRANCH_TYPES) -> int:
        """
        Count the circuit number in the PSSe sense
        :param branch: some branch
        :return: CKT
        """
        i = self._bus_int_dict[branch.bus_from]
        j = self._bus_int_dict[branch.bus_to]
        ckt = self._ckt_counter[i, j]
        ckt2 = ckt + 1
        self._ckt_counter[i, j] = ckt2
        self._ckt_counter[j, i] = ckt2
        return ckt2


def gridcal_to_raw(grid: MultiCircuit, logger: Logger) -> PsseCircuit:
    """
    Convert MultiCircuit to PSSeCircuit
    :param grid: MultiCircuit
    :param logger: Logger
    :return: PsseCircuit
    """
    psse_circuit = PsseCircuit()

    # create dictionaries
    area_dict: Dict[dev.Area, int] = dict()
    zones_dict: Dict[dev.Zone, int] = dict()

    counter = RawCounter(grid=grid)

    for i, area in enumerate(grid.areas):
        psse_circuit.areas.append(get_area(area=area, i=i + 1))
        area_dict[area] = i + 1

    for i, zone in enumerate(grid.zones):
        psse_circuit.zones.append(get_zone(zone=zone, i=i + 1))
        zones_dict[zone] = i + 1

    for i, bus in enumerate(grid.buses):
        if not bus.internal:
            psse_bus = get_psse_bus(bus=bus,
                                    area_dict=area_dict,
                                    zones_dict=zones_dict,
                                    suggested_psse_number=counter.get_suggested_psse_number(bus=bus, logger=logger))
            psse_circuit.buses.append(psse_bus)
        else:
            logger.add_info(msg="Internal bus skipped at RAW export",
                            device=bus.name)

    for load in grid.loads:
        psse_circuit.loads.append(get_psse_load(load=load,
                                                bus_dict=counter.psse_numbers_dict,
                                                id_number=counter.get_id(load.bus)))

    for load in grid.external_grids:
        psse_circuit.loads.append(get_psse_load_from_external_grid(load=load,
                                                                   bus_dict=counter.psse_numbers_dict,
                                                                   id_number=counter.get_id(load.bus)))

    for generator in grid.generators:
        psse_circuit.generators.append(get_psse_generator(generator=generator,
                                                          bus_dict=counter.psse_numbers_dict,
                                                          id_number=counter.get_id(generator.bus)))

    for shunt in grid.shunts:
        psse_circuit.fixed_shunts.append(get_psse_fixed_shunt(shunt=shunt,
                                                              bus_dict=counter.psse_numbers_dict,
                                                              id_number=counter.get_id(shunt.bus)))

    for controllable_shunt in grid.controllable_shunts:
        psse_circuit.switched_shunts.append(get_psse_switched_shunt(shunt=controllable_shunt,
                                                                    bus_dict=counter.psse_numbers_dict))

    for line in grid.lines:
        psse_circuit.branches.append(get_psse_branch(branch=line,
                                                     bus_dict=counter.psse_numbers_dict,
                                                     ckt=counter.get_ckt(branch=line)))

    for transformer in grid.transformers2w:
        psse_circuit.transformers.append(get_psse_transformer2w(transformer=transformer,
                                                                bus_dict=counter.psse_numbers_dict,
                                                                ckt=counter.get_ckt(branch=transformer)))

    for transformer in grid.transformers3w:
        psse_circuit.transformers.append(get_psse_transformer3w(transformer=transformer,
                                                                bus_dict=counter.psse_numbers_dict))

    # TODO: Decide whether to convert hvdc_lines into vsc_dc_lines or two_terminal_dc_lines.
    for hvdc_line in grid.hvdc_lines:
        psse_circuit.vsc_dc_lines.append(get_vsc_dc_line(hvdc_line,
                                                         bus_dict=counter.psse_numbers_dict))

    for hvdc_line in grid.hvdc_lines:
        psse_circuit.two_terminal_dc_lines.append(get_psse_two_terminal_dc_line(hvdc_line,
                                                                                bus_dict=counter.psse_numbers_dict))

    for upfc_device in grid.upfc_devices:
        psse_circuit.facts.append(get_psse_facts(upfc_device,
                                                 bus_dict=counter.psse_numbers_dict))

    return psse_circuit
