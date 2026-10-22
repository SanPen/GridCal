# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import math
from typing import Dict, List, Tuple, Union
from VeraGridEngine.basic_structures import Logger
import VeraGridEngine.Devices as dev
from VeraGridEngine.Topology import detect_substations
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.raw.psse_circuit import PsseCircuit
from VeraGridEngine.IO.raw.raw_types import (
    RawBranchLike,
    RawBusLike,
    RawEquipmentTerminalLike,
    RawFACTSLike,
    RawFixedShuntLike,
    RawGeneratorLike,
    RawLoadLike,
    RawNodeLike,
    RawSubstationLike,
    RawSubstationSwitchingDeviceLike,
    RawSwitchedShuntLike,
    RawSystemSwitchingDeviceLike,
    RawTransformerLike,
    RawTwoTerminalDCLineLike,
    RawVscDCLineLike,
)
from VeraGridEngine.enumerations import (
    TapChangerTypes, TapPhaseControl, TapModuleControl, ShuntControlMode, SwitchGraphicType,
    GeneratorControlMode
)


def _get_branch_ratings(psse_elm: RawBranchLike) -> tuple[float, float, float]:
    if psse_elm.version <= 33:
        return psse_elm.RATEA, psse_elm.RATEB, psse_elm.RATEC
    return psse_elm.RATE1, psse_elm.RATE2, psse_elm.RATE3


def _get_transformer_winding_ratings(psse_elm: RawTransformerLike, winding_index: int) -> tuple[float, float, float]:
    return psse_elm.get_winding_rating_triplet(winding_index=winding_index, version=psse_elm.version)


def normalize_terminal_identifier(value: int | float | str) -> str:
    """
    Normalize a terminal identifier for cross-record matching.

    :param value: Terminal identifier from RAW.
    :return: Normalized identifier.
    """
    text = str(value).replace("'", "").replace('"', "").strip()
    if text == '':
        return '1'
    else:
        return text


def create_substation_objects(
        psse_substations: List[RawSubstationLike],
        circuit: MultiCircuit) -> Dict[int, dev.Substation]:
    """
    Create VeraGrid substations from the RAW substation records.

    :param psse_substations: PSSE substation records.
    :param circuit: Destination circuit.
    :return: Mapping from PSSE substation number to VeraGrid substation.
    """
    substation_dict: Dict[int, dev.Substation] = dict()
    for psse_substation in psse_substations:
        name = str(psse_substation.NAME).replace("'", "").strip()
        if name == '':
            name = f"Substation {psse_substation.IS}"
        else:
            name = name

        substation = dev.Substation(
            name=name,
            code=str(psse_substation.IS),
            latitude=float(psse_substation.LATI),
            longitude=float(psse_substation.LONG)
        )
        circuit.add_substation(substation)
        substation_dict[psse_substation.IS] = substation

    return substation_dict


def create_node_breaker_buses(
        psse_nodes: List[RawNodeLike],
        raw_bus_by_number: Dict[int, RawBusLike],
        area_dict: Dict[int, dev.Area],
        zone_dict: Dict[int, dev.Zone],
        substation_dict: Dict[int, dev.Substation],
        circuit: MultiCircuit,
        logger: Logger) -> tuple[
    Dict[tuple[int, int], dev.Bus], Dict[tuple[int, int], dev.Bus], Dict[int, dev.Bus], set[int]]:
    """
    Create VeraGrid buses for PSSE node-breaker nodes.

    Each PSSE node becomes a VeraGrid bus. The PSSE electrical bus record is kept as
    metadata for voltage level, area, zone, and solved-state defaults.

    :param psse_nodes: Node records.
    :param raw_bus_by_number: RAW bus records keyed by bus number.
    :param area_dict: Area dictionary.
    :param zone_dict: Zone dictionary.
    :param substation_dict: Substation dictionary.
    :param circuit: Destination circuit.
    :param logger: Logger.
    :return: Node-bus lookup dictionaries and the set of electrical bus numbers with node-breaker data.
    """
    node_bus_by_substation_node: Dict[tuple[int, int], dev.Bus] = dict()
    node_bus_by_bus_and_node: Dict[tuple[int, int], dev.Bus] = dict()
    representative_bus_by_number: Dict[int, dev.Bus] = dict()
    node_breaker_bus_numbers: set[int] = set()

    for psse_node in psse_nodes:
        raw_bus = raw_bus_by_number.get(psse_node.I, None)
        substation = substation_dict.get(psse_node.ISUB, None)

        if raw_bus is None:
            logger.add_error('Node references a bus that does not exist', value=str(psse_node.I))
        elif substation is None:
            logger.add_error('Node references a substation that does not exist', value=str(psse_node.ISUB))
        else:
            bus, _ = get_veragrid_bus(
                psse_bus=raw_bus,
                area_dict=area_dict,
                zone_dict=zone_dict,
                logger=logger
            )

            node_name = str(psse_node.NAME).replace("'", "").strip()
            if node_name == '':
                node_name = f"{substation.name}_{psse_node.NI}"
            else:
                node_name = node_name

            if psse_node.VM != 0.0 or psse_node.VA != 0.0:
                vm0 = float(psse_node.VM)
                va0 = np.deg2rad(float(psse_node.VA))
            else:
                vm0 = float(raw_bus.VM)
                va0 = np.deg2rad(float(raw_bus.VA))

            bus.name = node_name
            bus.code = f"{psse_node.I}:{psse_node.NI}"
            bus.substation = substation
            bus.active = bus.active and bool(psse_node.STATUS)
            bus.Vm0 = vm0
            bus.Va0 = va0

            # Only one node bus should carry the slack designation of the reduced
            # electrical bus. The others are plain PQ nodes until topology reduction.
            if raw_bus.I in representative_bus_by_number:
                bus.set_is_slack_at(t=None, val=False)
                bus.bus_type = dev.BusMode.PQ_tpe

            circuit.add_bus(bus)

            if substation.area is None:
                substation.area = area_dict.get(abs(raw_bus.AREA), None)
            else:
                substation.area = substation.area

            if substation.zone is None:
                substation.zone = zone_dict.get(abs(raw_bus.ZONE), None)
            else:
                substation.zone = substation.zone

            node_bus_by_substation_node[(psse_node.ISUB, psse_node.NI)] = bus
            node_bus_by_bus_and_node[(psse_node.I, psse_node.NI)] = bus
            node_breaker_bus_numbers.add(psse_node.I)

            if psse_node.I not in representative_bus_by_number:
                representative_bus_by_number[psse_node.I] = bus
            else:
                representative_bus_by_number[psse_node.I] = representative_bus_by_number[psse_node.I]

    return node_bus_by_substation_node, node_bus_by_bus_and_node, representative_bus_by_number, node_breaker_bus_numbers


def build_terminal_bus_lookup(
        terminals: List[RawEquipmentTerminalLike],
        node_bus_by_bus_and_node: Dict[tuple[int, int], dev.Bus],
        logger: Logger) -> Dict[tuple[str, int, int, int, str], dev.Bus]:
    """
    Build a lookup from terminal records to VeraGrid node buses.

    :param terminals: Parsed equipment terminal records.
    :param node_bus_by_bus_and_node: Node buses keyed by electrical bus and node number.
    :param logger: Logger.
    :return: Terminal lookup dictionary.
    """
    terminal_bus_lookup: Dict[tuple[str, int, int, int, str], dev.Bus] = dict()

    for terminal in terminals:
        if terminal.NI > 0:
            bus = node_bus_by_bus_and_node.get((terminal.IBUS, terminal.NI), None)
            if bus is None:
                logger.add_warning(
                    'Equipment terminal references a node that was not created',
                    value=f"{terminal.IBUS}:{terminal.NI}"
                )
            else:
                key = (
                    terminal.TYPE,
                    terminal.IBUS,
                    terminal.JBUS,
                    terminal.KBUS,
                    normalize_terminal_identifier(terminal.EQID),
                )
                terminal_bus_lookup[key] = bus
        else:
            pass

    return terminal_bus_lookup


def find_terminal_bus(
        terminal_bus_lookup: Dict[tuple[str, int, int, int, str], dev.Bus],
        type_code: str,
        ibus: int,
        jbus: int,
        kbus: int,
        eqid: int | float | str) -> dev.Bus | None:
    """
    Resolve a RAW equipment terminal to a VeraGrid node bus.

    :param terminal_bus_lookup: Terminal lookup dictionary.
    :param type_code: Terminal type code.
    :param ibus: Primary bus number.
    :param jbus: Secondary bus number.
    :param kbus: Tertiary bus number.
    :param eqid: Equipment identifier.
    :return: Node bus or ``None``.
    """
    normalized_id = normalize_terminal_identifier(eqid)
    key = (type_code, ibus, jbus, kbus, normalized_id)
    bus = terminal_bus_lookup.get(key, None)

    if bus is None and type_code == '3':
        alt_key = (type_code, ibus, kbus, jbus, normalized_id)
        bus = terminal_bus_lookup.get(alt_key, None)
    else:
        bus = bus

    return bus


def find_control_node_bus(
        node_bus_by_bus_and_node: Dict[tuple[int, int], dev.Bus],
        bus_number: int,
        node_number: int) -> dev.Bus | None:
    """
    Resolve a control target defined by electrical bus and node number.

    :param node_bus_by_bus_and_node: Node buses keyed by electrical bus and node number.
    :param bus_number: Electrical bus number.
    :param node_number: Node number.
    :return: Node bus or ``None``.
    """
    if node_number > 0:
        return node_bus_by_bus_and_node.get((abs(bus_number), abs(node_number)), None)
    else:
        return None


def create_substation_switch(
        psse_switch: RawSubstationSwitchingDeviceLike,
        node_bus_by_substation_node: Dict[tuple[int, int], dev.Bus],
        logger: Logger) -> dev.Switch | None:
    """
    Create a VeraGrid switch from a PSSE substation switching device.

    :param psse_switch: PSSE substation switching device.
    :param node_bus_by_substation_node: Node buses keyed by substation and node number.
    :param logger: Logger.
    :return: VeraGrid switch or ``None``.
    """
    bus_from = node_bus_by_substation_node.get((psse_switch.ISUB, psse_switch.NI), None)
    bus_to = node_bus_by_substation_node.get((psse_switch.ISUB, psse_switch.NJ), None)

    if bus_from is None or bus_to is None:
        logger.add_error(
            'Substation switching device references a node that does not exist',
            value=f"{psse_switch.ISUB}:{psse_switch.NI}->{psse_switch.NJ}"
        )
        return None

    if psse_switch.TYPE == 3:
        graphic_type = SwitchGraphicType.Disconnector
    else:
        graphic_type = SwitchGraphicType.CircuitBreaker

    if psse_switch.version == 34:
        code = str(psse_switch.CKTID).replace("'", "").strip()
    else:
        code = str(psse_switch.CKT).replace("'", "").strip()

    name = str(psse_switch.NAME).replace("'", "").strip()
    if name == '':
        name = f"{psse_switch.ISUB}_{psse_switch.NI}_{psse_switch.NJ}_{code}"
    else:
        name = name

    switch = dev.Switch(
        bus_from=bus_from,
        bus_to=bus_to,
        name=name,
        code=code,
        x=float(psse_switch.X),
        rate=float(psse_switch.RATE1),
        active=int(psse_switch.STATUS) != 0,
        normal_open=int(psse_switch.NSTAT) == 0,
        graphic_type=graphic_type,
    )

    return switch


def get_veragrid_bus(psse_bus: RawBusLike,
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

        if psse_bus.GL != 0 or psse_bus.BL != 0:
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
        bus.bus_type = bustype[psse_bus.IDE]
    else:
        bus.bus_type = dev.BusMode.PQ_tpe

    if int(psse_bus.IDE) == 4:
        bus.active = False

    if bus.bus_type == dev.BusMode.Slack_tpe:
        bus.set_is_slack_at(t=None, val=True)

    # Ensures unique name
    bus.name = bus.name.replace("'", "").strip()

    bus.code = str(psse_bus.I)

    if bus.name == '':
        bus.name = 'Bus ' + str(psse_bus.I)

    return bus, sh


def get_veragrid_load(psse_load: RawLoadLike, bus: dev.Bus, logger: Logger) -> dev.Load:
    """
    Return VeraGrid Load object
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


def get_veragrid_shunt_fixed(psse_elm: RawFixedShuntLike, bus: dev.Bus, logger: Logger):
    """
    Return VeraGrid Shunt object
    Returns:
        VeraGrid Shunt object
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


def get_veragrid_shunt_switched(
        psse_elm: RawSwitchedShuntLike,
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
        control_mode = ShuntControlMode.Locked
        b_init = psse_elm.BINIT

    elif psse_elm.MODSW == 1:
        # 1 - discrete adjustment, controlling voltage locally or at bus SWREG
        control_mode = ShuntControlMode.Discrete
        b_init = psse_elm.BINIT * psse_elm.RMPCT / 100.0
        vset = (psse_elm.VSWHI + psse_elm.VSWLO) / 2.0

    elif psse_elm.MODSW == 2:
        # 2 - continuous adjustment, controlling voltage locally or at bus SWREG
        control_mode = ShuntControlMode.Continuous
        b_init = psse_elm.BINIT * psse_elm.RMPCT / 100.0
        vset = (psse_elm.VSWHI + psse_elm.VSWLO) / 2.0

    elif psse_elm.MODSW in [3, 4, 5, 6]:
        control_mode = ShuntControlMode.Continuous
        b_init = psse_elm.BINIT
        logger.add_warning(
            msg="Not supported control mode for Switched Shunt",
            value=psse_elm.MODSW
        )

    else:
        control_mode = ShuntControlMode.Locked
        b_init = psse_elm.BINIT
        logger.add_warning(
            msg="Invalid control mode for Switched Shunt.",
            device=psse_elm,
            expected_value="0-6",
            value=psse_elm.MODSW,
        )

    n_list: list[int] = list()
    b_list: list[float] = list()

    for i in range(1, 9):
        s = psse_elm.get_block_status(i)
        n = psse_elm.get_block_steps(i)

        if s == 1:
            n_list.append(n)
            b_list.append(psse_elm.get_block_admittance(i))

    # Pick the discrete step whose cumulative susceptance matches the in-service
    # initial value BINIT. The raw is a solved snapshot, so BINIT is the susceptance
    # PSSe converged with; starting here lets a controls-off solve reproduce it
    # (step 0 = neutral/off, step k = first k blocks on).
    cum_b = np.insert(np.cumsum([n * b for n, b in zip(n_list, b_list)]), 0, 0.0)
    init_step = int(np.argmin(np.abs(cum_b - psse_elm.BINIT))) if len(cum_b) > 1 else 0
    b_min = float(np.min(cum_b)) if len(cum_b) > 0 else 0.0
    b_max = float(np.max(cum_b)) if len(cum_b) > 0 else 0.0

    elm = dev.ControllableShunt(
        name='Switched shunt ' + busnum_id,
        code=busnum_id,
        active=bool(psse_elm.STAT),
        B=b_init,
        Bmin=b_min,
        Bmax=b_max,
        step=init_step,
        vset=vset,
        vmin=float(psse_elm.VSWLO),
        vmax=float(psse_elm.VSWHI),
        control_mode=control_mode,
    )

    if psse_elm.SWREG > 0:
        if psse_elm.SWREG != psse_elm.I:
            elm.control_bus = psse_bus_dict[psse_elm.SWREG]

    elm.set_blocks(n_list, b_list)

    return elm


def get_veragrid_switch(psse_elm: RawSystemSwitchingDeviceLike,
                        psse_bus_dict: Dict[int, dev.Bus],
                        logger: Logger) -> dev.Switch | None:
    """
    Return VeraGrid Switch object
    :param psse_elm
    :param psse_bus_dict:
    :param logger:
    """
    bus_from = psse_bus_dict.get(psse_elm.I, None)
    bus_to = psse_bus_dict.get(psse_elm.J, None)

    if bus_from is None or bus_to is None:
        logger.add_error("Switch bus missing", device=psse_elm.get_id(), value=f"{psse_elm.I}->{psse_elm.J}")
        return None

    if psse_elm.STYPE == 3:
        graphic_type = SwitchGraphicType.Disconnector
    else:
        graphic_type = SwitchGraphicType.CircuitBreaker

    code = str(psse_elm.CKT).replace("'", "").strip()
    name = str(psse_elm.NAME).replace("'", "").strip() or f"{psse_elm.I}_{psse_elm.J}_{code}"

    elm = dev.Switch(
        bus_from=bus_from,
        bus_to=bus_to,
        name=name,
        code=code,
        x=float(psse_elm.X),
        rate=float(_get_branch_ratings(psse_elm)[0]),
        active=bool(psse_elm.STATUS),
        normal_open=int(psse_elm.NSTATUS) == 0,
        graphic_type=graphic_type,
    )

    return elm


def get_veragrid_generator(psse_elm: RawGeneratorLike, psse_bus_dict: Dict[int, dev.Bus],
                           logger: Logger) -> dev.Generator:
    """

    :param psse_elm:
    :param psse_bus_dict:
    :param logger:
    :return:
    """
    name = str(psse_elm.I) + '_' + str(psse_elm.ID).replace("'", "")

    if psse_elm.WMOD == 0:  # Conventional machine
        control_mode = GeneratorControlMode.V
        Q = psse_elm.QG
        Qmin = psse_elm.QB
        Qmax = psse_elm.QT
    elif psse_elm.WMOD == 1:  # Standard Qmin, Qmax limits
        control_mode = GeneratorControlMode.V
        Q = psse_elm.QG
        Qmin = psse_elm.QB
        Qmax = psse_elm.QT
    elif psse_elm.WMOD == 2:  # Qmin, Qmax based based on WPF
        control_mode = GeneratorControlMode.V
        # pf = psse_elm.WPF
        # NOTE: the QB and QT limits come correct already, no need to compute this here
        Q = psse_elm.QG
        # Qmin = psse_elm.PB * np.sqrt((1.0 / (pf ** 2)) - 1.0)
        # Qmax = psse_elm.PT * np.sqrt((1.0 / (pf ** 2)) - 1.0)
        Qmin = psse_elm.QB
        Qmax = psse_elm.QT
    elif psse_elm.WMOD == 3:  # Fixed Q
        control_mode = GeneratorControlMode.Q
        pf = psse_elm.WPF if psse_elm.WPF is not None else 0.8
        Q = psse_elm.PG * np.sqrt((1.0 / (pf ** 2)) - 1.0)
        Qmin = psse_elm.QB
        Qmax = psse_elm.QT
    elif psse_elm.WMOD == 4:  # Infeed machine
        control_mode = GeneratorControlMode.Q
        pf = psse_elm.WPF if psse_elm.WPF is not None else 0.8
        Q = psse_elm.PG * np.sqrt((1.0 / (pf ** 2)) - 1.0)
        Qmin = psse_elm.QB
        Qmax = psse_elm.QT
    else:
        control_mode = GeneratorControlMode.V
        Qmin = psse_elm.QB
        Qmax = psse_elm.QT
        Q = psse_elm.QG

    bus = psse_bus_dict[psse_elm.I]
    if Qmax == Qmin and not bus.is_slack:
        has_wind_pf_reactive_control = psse_elm.WMOD == 2 and abs(abs(psse_elm.WPF) - 1.0) > 1e-6
        if not has_wind_pf_reactive_control:
            control_mode = GeneratorControlMode.Q

    elm = dev.Generator(
        name=name,
        idtag=None,
        code=name,
        P=psse_elm.PG,
        Q=Q,
        vset=psse_elm.VS,
        Qmin=Qmin,
        Qmax=Qmax,
        Snom=psse_elm.MBASE,
        Pmax=psse_elm.PT,
        Pmin=psse_elm.PB,
        active=bool(psse_elm.STAT),
        control_mode=control_mode
    )

    if psse_elm.IREG > 0:
        if psse_elm.IREG != psse_elm.I:
            elm.control_bus = psse_bus_dict[psse_elm.IREG]

    return elm


def get_veragrid_transformer(
        psse_elm: RawTransformerLike,
        psse_bus_dict: Dict[int, dev.Bus],
        Sbase: float,
        logger: Logger,
        adjust_taps_to_discrete_positions: bool,
        simple_naming: bool,
        flatten_virtual_taps: bool) -> Tuple[Union[dev.Transformer2W, dev.Transformer3W], int]:
    """

    :param psse_elm:
    :param psse_bus_dict:
    :param Sbase:
    :param logger:
    :param adjust_taps_to_discrete_positions: Modify the tap angle and module to the discrete positions
    :param simple_naming:
    :param flatten_virtual_taps:
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
    ckt = str(psse_elm.CKT).replace("@", "").replace("*", "")

    if psse_elm.windings == 0:
        # guess the number of windings
        psse_elm.windings = 2 if psse_elm.K == 0 else 3

    if psse_elm.windings == 2:
        bus_from = psse_bus_dict[psse_elm.I]
        bus_to = psse_bus_dict[psse_elm.J]

        if simple_naming:
            name = "{0}_{1}_{2}".format(psse_elm.I, psse_elm.J, ckt)
        else:
            name = "{0}_{1}_{2}_{3}_{4}_{5}_{6}".format(psse_elm.I, bus_from.name, bus_from.Vnom,
                                                        psse_elm.J, bus_to.name, bus_to.Vnom, ckt)

        name = name.replace("'", "").replace(" ", "").strip()

        code = str(psse_elm.I) + '_' + str(psse_elm.J) + '_' + str(ckt)
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

        rate1_1, rate1_2, rate1_3 = _get_transformer_winding_ratings(psse_elm, 1)

        contingency_factor = (rate1_2 / rate1_1
                              if rate1_1 > 0.0 and rate1_2 > 0.0
                              else 1.0)

        protection_factor = (rate1_3 / rate1_1
                             if rate1_1 > 0.0 and rate1_3 > 0.0
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

            if psse_elm.NTP1 > 1:

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
            else:

                tc_total_positions = 1
                tc_neutral_position = 0
                tc_normal_position = 0
                alpha_per_2 = math.radians(psse_elm.RMA1)
                tc_dV = 0.0
                logger.add_warning(msg='Number of tap positions == 1', value=1)
         
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

        if flatten_virtual_taps:
            V1 = bus_from.Vnom
            V2 = bus_to.Vnom
            HV2 = max(V1, V2)
            LV2 = min(V1, V2)

            if HV != HV2 or LV != LV2:
                logger.add_info(msg="Flattening virtual taps like PSS/e",
                                value=f"HV:{HV2}, LV:{LV2}",
                                expected_value=f"HV:{HV}, LV:{LV}",
                                device_class="Transformer2W",
                                device=code)
                HV = HV2
                LV = LV2

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
            rate=rate1_1,
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
        # NOTE: may need to be `/ mf / mt` (small Va error on some radial buses); see admittance_matrices.py
        elm.tap_module = tap_module / mf * mt

        return elm, 2

    elif psse_elm.windings == 3:

        bus_1 = psse_bus_dict[abs(psse_elm.I)]
        bus_2 = psse_bus_dict[abs(psse_elm.J)]
        bus_3 = psse_bus_dict[abs(psse_elm.K)]
        code = str(psse_elm.I) + '_' + str(psse_elm.J) + '_' + str(psse_elm.K) + '_' + str(ckt)

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

        if flatten_virtual_taps:

            if V1 != bus_1.Vnom:
                logger.add_info(msg="Flattening virtual taps like PSS/e",
                                value=f"V1:{V1}",
                                expected_value=f"V1:{bus_1.Vnom}",
                                device_class="Transformer3W",
                                device=code)
                V1 = bus_1.Vnom

            if V2 != bus_2.Vnom:
                logger.add_info(msg="Flattening virtual taps like PSS/e",
                                value=f"V2:{V2}",
                                expected_value=f"V2:{bus_2.Vnom}",
                                device_class="Transformer3W",
                                device=code)
                V2 = bus_2.Vnom

            if V3 != bus_3.Vnom:
                logger.add_info(msg="Flattening virtual taps like PSS/e",
                                value=f"V3:{V3}",
                                expected_value=f"V3:{bus_3.Vnom}",
                                device_class="Transformer3W",
                                device=code)
                V3 = bus_3.Vnom

        rate1_1, _, _ = _get_transformer_winding_ratings(psse_elm, 1)
        rate2_1, _, _ = _get_transformer_winding_ratings(psse_elm, 2)
        rate3_1, _, _ = _get_transformer_winding_ratings(psse_elm, 3)

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
                                 rate12=rate1_1,
                                 rate23=rate2_1,
                                 rate31=rate3_1)

        # PSSe defines the winding off-nominal turns ratio (WINDVn) and phase shift (ANGn)
        # on the winding-bus side. The windings are oriented winding-bus(bus_from) ->
        # star(bus_to) with the tap applied on the bus_from (winding-bus) side, so the
        # PSSe winding-side values are used directly.
        tr3w.winding1.tap_phase = np.deg2rad(psse_elm.ANG1)
        tr3w.winding2.tap_phase = np.deg2rad(psse_elm.ANG2)
        tr3w.winding3.tap_phase = np.deg2rad(psse_elm.ANG3)

        # STAT=2/3/4 means winding 2/3/1 is individually out of service
        if psse_elm.STAT == 0:
            tr3w.winding1.active = False
            tr3w.winding2.active = False
            tr3w.winding3.active = False
        elif psse_elm.STAT == 1:
            tr3w.winding1.active = True
            tr3w.winding2.active = True
            tr3w.winding3.active = True
        elif psse_elm.STAT == 2:
            tr3w.winding1.active = True
            tr3w.winding2.active = False
            tr3w.winding3.active = True
        elif psse_elm.STAT == 3:
            tr3w.winding1.active = True
            tr3w.winding2.active = True
            tr3w.winding3.active = False
        elif psse_elm.STAT == 4:
            tr3w.winding1.active = False
            tr3w.winding2.active = True
            tr3w.winding3.active = True

        NOMV1 = psse_elm.NOMV1 if psse_elm.NOMV1 > 0 else bus_1.Vnom
        NOMV2 = psse_elm.NOMV2 if psse_elm.NOMV2 > 0 else bus_2.Vnom
        NOMV3 = psse_elm.NOMV3 if psse_elm.NOMV3 > 0 else bus_3.Vnom

        # winding-bus-side off-nominal ratio in pu (per PSSe convention), applied directly
        # because the winding tap is on the winding-bus (bus_from) side.
        if psse_elm.CW == 1:

            tr3w.winding1.tap_module = psse_elm.WINDV1
            tr3w.winding2.tap_module = psse_elm.WINDV2
            tr3w.winding3.tap_module = psse_elm.WINDV3

        elif psse_elm.CW == 2:

            tr3w.winding1.tap_module = psse_elm.WINDV1 / bus_1.Vnom
            tr3w.winding2.tap_module = psse_elm.WINDV2 / bus_2.Vnom
            tr3w.winding3.tap_module = psse_elm.WINDV3 / bus_3.Vnom

        elif psse_elm.CW == 3:

            tr3w.winding1.tap_module = psse_elm.WINDV1 * NOMV1 / bus_1.Vnom
            tr3w.winding2.tap_module = psse_elm.WINDV2 * NOMV2 / bus_2.Vnom
            tr3w.winding3.tap_module = psse_elm.WINDV3 * NOMV3 / bus_3.Vnom
        else:
            raise Exception('Unknown impedance combination CW=' + str(psse_elm.CZ))

        # --------------------------------------------------------------------------------------
        # Winding tap regulation. With COD = +-1 a winding steps its tap to hold the controlled
        # bus (CONTn) voltage within the band [VMIn, VMAn], the tap ratio moving within
        # [RMIn, RMAn] over NTPn discrete positions. PSSe writes the *initial* tap into WINDVn
        # and adjusts it during the solve, so importing the regulation lets VeraGrid reproduce
        # the regulated tap instead of staying frozen at the input value.
        # --------------------------------------------------------------------------------------
        winding_controls = [
            (tr3w.winding1, psse_elm.COD1, psse_elm.CONT1, psse_elm.RMA1, psse_elm.RMI1,
             psse_elm.VMA1, psse_elm.VMI1, psse_elm.NTP1),
            (tr3w.winding2, psse_elm.COD2, psse_elm.CONT2, psse_elm.RMA2, psse_elm.RMI2,
             psse_elm.VMA2, psse_elm.VMI2, psse_elm.NTP2),
            (tr3w.winding3, psse_elm.COD3, psse_elm.CONT3, psse_elm.RMA3, psse_elm.RMI3,
             psse_elm.VMA3, psse_elm.VMI3, psse_elm.NTP3),
        ]
        for w, cod, cont, rma, rmi, vma, vmi, ntp in winding_controls:
            if cod in (1, -1):  # voltage control (negative => locked, kept fixed)
                w.tap_module_control_mode = TapModuleControl.Vm if cod > 0 else TapModuleControl.fixed

                reg_bus = psse_bus_dict.get(abs(int(cont)), None)
                if reg_bus is not None:
                    w.regulation_bus = reg_bus

                # controlled-voltage band -> regulate towards its midpoint
                if vma > 0.0 and vmi > 0.0:
                    w.vset = 0.5 * (vma + vmi)

                # tap-ratio limits and discrete positions. The parsed tap_module (WINDVn) is
                # the regulator's starting position and is left untouched; only the changer
                # ladder is configured so the solver can step it within [RMIn, RMAn].
                if rma > 0.0 and rmi > 0.0:
                    w.tap_module_max = rma
                    w.tap_module_min = rmi
                    if ntp > 1:
                        tc = w.tap_changer
                        tc.tc_type = TapChangerTypes.VoltageRegulation
                        tc.total_positions = int(ntp)
                        tc.neutral_position = int(ntp // 2)
                        tc.normal_position = int(ntp // 2)
                        tc.dV = (rma - rmi) / (ntp - 1)
                        tc.recalc()

        tr3w.compute_delta_to_star()

        tr3w.bus0.Vm0 = psse_elm.VMSTAR
        tr3w.bus0.Va0 = np.deg2rad(psse_elm.ANSTAR)

        return tr3w, 3

    else:
        raise Exception(str(psse_elm.windings) + ' number of windings!')


def get_veragrid_line(psse_elm: RawBranchLike,
                      psse_bus_dict: Dict[int, dev.Bus],
                      Sbase: float,
                      logger: Logger,
                      simple_naming: bool) -> dev.Line:
    """

    :param psse_elm:
    :param psse_bus_dict:
    :param Sbase:
    :param logger:
    :param simple_naming
    :return:
    """

    i = abs(psse_elm.I)
    j = abs(psse_elm.J)
    bus_from = psse_bus_dict[i]
    bus_to = psse_bus_dict[j]
    ckt = str(psse_elm.CKT).replace("@", "").replace("*", "")
    code = str(i) + '_' + str(j) + '_' + str(ckt).replace("'", "").strip()

    if psse_elm.NAME.strip() == '':
        if simple_naming:
            name = "{0}_{1}_{2}".format(i, j, ckt)
        else:
            name = "{0}_{1}_{2}_{3}_{4}_{5}_{6}".format(i, bus_from.name, bus_from.Vnom, j, bus_to.name, bus_to.Vnom,
                                                        ckt)
        name = name.replace("'", "").replace(" ", "").strip()
    else:
        name = psse_elm.NAME.strip()

    rate1, rate2, rate3 = _get_branch_ratings(psse_elm)

    contingency_factor = rate2 / rate1 if rate1 > 0.0 else 1.0

    if contingency_factor == 0:
        contingency_factor = 1.0

    protection_factor = rate3 / rate1 if rate1 > 0.0 else 1.4

    if protection_factor == 0:
        protection_factor = 1.4

    active = bool(psse_elm.ST)

    if active and (not bus_from.active or not bus_to.active):
        active = False
        logger.add_warning(
            msg="Branch connected to inactive bus imported as inactive",
            device=code,
        )

    branch = dev.Line(bus_from=bus_from,
                      bus_to=bus_to,
                      idtag=psse_elm.idtag,
                      code=code,
                      name=name,
                      r=psse_elm.R,
                      x=psse_elm.X,
                      b=psse_elm.B,
                      rate=rate1,
                      contingency_factor=round(contingency_factor, 6),
                      protection_rating_factor=round(protection_factor, 6),
                      active=active,
                      mttf=0,
                      mttr=0,
                      length=psse_elm.LEN)
    return branch


def get_hvdc_from_vscdc(psse_elm: RawVscDCLineLike,
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


def get_hvdc_from_twotermdc(psse_elm: RawTwoTerminalDCLineLike,
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


def get_upfc_from_facts(psse_elm: RawFACTSLike,
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


def psse_to_veragrid(psse_circuit: PsseCircuit,
                     logger: Logger,
                     branch_connection_voltage_tolerance: float = 0.1,
                     adjust_taps_to_discrete_positions: bool = False,
                     use_short_names: bool = True,
                     flatten_virtual_taps: bool = False) -> MultiCircuit:
    """

    :param psse_circuit: PsseCircuit instance
    :param logger: Logger
    :param branch_connection_voltage_tolerance: tolerance in p.u. of a branch voltage to be considered a transformer
    :param adjust_taps_to_discrete_positions: Modify the tap angle and module to the discrete positions
    :param use_short_names: use from_to_ckt, instead of
    :param use_short_names: use a short name (bus_from_bus_to_ckt)
    :param flatten_virtual_taps: flatten virtual taps (like psse, instead of properly using the voltage differences)
    :return: MultiCircuit instance
    """

    circuit = MultiCircuit(Sbase=psse_circuit.SBASE, fbase=psse_circuit.BASFRQ)
    circuit.comments = 'Converted from a PSS/e .raw file'

    circuit.areas = [dev.Area(name=x.ARNAME) for x in psse_circuit.areas]
    circuit.zones = [dev.Zone(name=x.ZONAME) for x in psse_circuit.zones]

    area_dict = {val.I: elm for val, elm in zip(psse_circuit.areas, circuit.areas)}
    zones_dict = {val.I: elm for val, elm in zip(psse_circuit.zones, circuit.zones)}
    raw_bus_by_number: Dict[int, RawBusLike] = {bus.I: bus for bus in psse_circuit.buses}

    # scan for missing zones or areas (yes, PSSe is so crappy that can reference areas that do not exist)
    missing_areas = False
    missing_zones = False
    slack_buses: List[int] = list()
    for psse_bus in psse_circuit.buses:

        # replace area idx by area name if available
        if abs(psse_bus.AREA) not in area_dict.keys():
            area_dict[abs(psse_bus.AREA)] = dev.Area(name='A' + str(abs(psse_bus.AREA)))
            missing_areas = True

        if abs(psse_bus.ZONE) not in zones_dict.keys():
            zones_dict[abs(psse_bus.ZONE)] = dev.Zone(name='Z' + str(abs(psse_bus.ZONE)))
            missing_zones = True

        if int(psse_bus.IDE) == 3:
            slack_buses.append(psse_bus.I)
        else:
            slack_buses = slack_buses

    if missing_areas:
        circuit.areas = [v for k, v in area_dict.items()]

    if missing_zones:
        circuit.zones = [v for k, v in zones_dict.items()]

    substation_dict = create_substation_objects(psse_circuit.substations, circuit)
    node_bus_by_substation_node, node_bus_by_bus_and_node, representative_node_bus_by_number, node_breaker_bus_numbers = (
        create_node_breaker_buses(
            psse_nodes=psse_circuit.nodes,
            raw_bus_by_number=raw_bus_by_number,
            area_dict=area_dict,
            zone_dict=zones_dict,
            substation_dict=substation_dict,
            circuit=circuit,
            logger=logger
        )
    )

    psse_bus_dict: Dict[int, dev.Bus] = dict()
    for psse_bus in psse_circuit.buses:
        if psse_bus.I in node_breaker_bus_numbers:
            representative_node_bus = representative_node_bus_by_number.get(psse_bus.I, None)
            if representative_node_bus is not None:
                psse_bus_dict[psse_bus.I] = representative_node_bus
            else:
                logger.add_error('Node-breaker bus has no representative node bus', value=str(psse_bus.I))
        else:
            bus, bus_shunt = get_veragrid_bus(psse_bus=psse_bus,
                                              area_dict=area_dict,
                                              zone_dict=zones_dict,
                                              logger=logger)

            circuit.add_bus(bus)
            psse_bus_dict[psse_bus.I] = bus

            # legacy PSSe buses may have shunts declared within, so add them
            if bus_shunt is not None:
                circuit.add_shunt(bus=bus, api_obj=bus_shunt)
            else:
                bus_shunt = bus_shunt

    terminal_bus_lookup = build_terminal_bus_lookup(
        terminals=psse_circuit.equipment_terminals,
        node_bus_by_bus_and_node=node_bus_by_bus_and_node,
        logger=logger
    )

    # check that the area slack buses actually make sense
    for area in psse_circuit.areas:
        if area.ISW not in slack_buses:
            logger.add_error('The area slack bus is not marked as slack', str(area.ISW))

    # Go through loads
    for psse_load in psse_circuit.loads:
        if psse_load.I in psse_bus_dict:
            terminal_bus = find_terminal_bus(terminal_bus_lookup, 'L', psse_load.I, 0, 0, psse_load.ID)
            if terminal_bus is not None:
                bus = terminal_bus
            else:
                bus = psse_bus_dict[psse_load.I]
            api_obj = get_veragrid_load(psse_load, bus, logger)

            circuit.add_load(bus, api_obj)
        else:
            logger.add_error("Load bus is missing", psse_load.I, psse_load.I)

    # Go through shunts
    for psse_shunt in psse_circuit.fixed_shunts:
        if psse_shunt.I in psse_bus_dict:
            terminal_bus = find_terminal_bus(terminal_bus_lookup, 'F', psse_shunt.I, 0, 0, psse_shunt.ID)
            if terminal_bus is not None:
                bus = terminal_bus
            else:
                bus = psse_bus_dict[psse_shunt.I]
            api_obj = get_veragrid_shunt_fixed(psse_shunt, bus, logger)
            circuit.add_shunt(bus, api_obj)
        else:
            logger.add_error("Shunt bus missing", psse_shunt.I, psse_shunt.I)

    for psse_shunt in psse_circuit.switched_shunts:
        if psse_shunt.I in psse_bus_dict:
            if psse_shunt.version >= 35:
                terminal_bus = find_terminal_bus(terminal_bus_lookup, 'S', psse_shunt.I, 0, 0, psse_shunt.ID)
            else:
                terminal_bus = find_terminal_bus(terminal_bus_lookup, 'S', psse_shunt.I, 0, 0, '1')

            if terminal_bus is not None:
                bus = terminal_bus
            else:
                bus = psse_bus_dict[psse_shunt.I]
            api_obj = get_veragrid_shunt_switched(psse_shunt, bus, psse_bus_dict, logger)

            if psse_shunt.version >= 35 and psse_shunt.NREG > 0:
                control_bus = find_control_node_bus(node_bus_by_bus_and_node, psse_shunt.SWREG, psse_shunt.NREG)
                if control_bus is not None:
                    api_obj.control_bus = control_bus
                else:
                    api_obj.control_bus = api_obj.control_bus
            else:
                api_obj.control_bus = api_obj.control_bus
            circuit.add_controllable_shunt(bus, api_obj)
        else:
            logger.add_error("Switched shunt bus missing", psse_shunt.I, psse_shunt.I)

    # Go through generators
    for psse_gen in psse_circuit.generators:
        terminal_bus = find_terminal_bus(terminal_bus_lookup, 'M', psse_gen.I, 0, 0, psse_gen.ID)
        if terminal_bus is not None:
            bus = terminal_bus
        else:
            bus = psse_bus_dict[psse_gen.I]
        api_obj = get_veragrid_generator(psse_gen, psse_bus_dict, logger)

        if psse_gen.version >= 35 and psse_gen.NREG > 0:
            control_bus = find_control_node_bus(node_bus_by_bus_and_node, psse_gen.IREG, psse_gen.NREG)
            if control_bus is not None:
                api_obj.control_bus = control_bus
            else:
                api_obj.control_bus = api_obj.control_bus
        else:
            api_obj.control_bus = api_obj.control_bus

        circuit.add_generator(bus, api_obj)

    # Go through Branches
    branches_already_there = set()

    # Go through Transformers
    for psse_transformer in psse_circuit.transformers:
        # get the object
        transformer, n_windings = get_veragrid_transformer(
            psse_elm=psse_transformer,
            psse_bus_dict=psse_bus_dict,
            Sbase=psse_circuit.SBASE,
            logger=logger,
            adjust_taps_to_discrete_positions=adjust_taps_to_discrete_positions,
            simple_naming=use_short_names,
            flatten_virtual_taps=flatten_virtual_taps
        )

        if n_windings == 2:
            bus_from = find_terminal_bus(terminal_bus_lookup, '2', psse_transformer.I, psse_transformer.J, 0,
                                         psse_transformer.CKT)
            bus_to = find_terminal_bus(terminal_bus_lookup, '2', psse_transformer.J, psse_transformer.I, 0,
                                       psse_transformer.CKT)

            if bus_from is not None:
                transformer.bus_from = bus_from
            else:
                transformer.bus_from = transformer.bus_from

            if bus_to is not None:
                transformer.bus_to = bus_to
            else:
                transformer.bus_to = transformer.bus_to

            if psse_transformer.CONT1 > 0 and psse_transformer.NODE1 > 0:
                control_bus = find_control_node_bus(node_bus_by_bus_and_node, psse_transformer.CONT1,
                                                    psse_transformer.NODE1)
                if control_bus is not None:
                    transformer.regulation_bus = control_bus
                else:
                    transformer.regulation_bus = transformer.regulation_bus
            else:
                transformer.regulation_bus = transformer.regulation_bus
        else:
            bus_1 = find_terminal_bus(terminal_bus_lookup, '3', psse_transformer.I, psse_transformer.J,
                                      psse_transformer.K, psse_transformer.CKT)
            bus_2 = find_terminal_bus(terminal_bus_lookup, '3', psse_transformer.J, psse_transformer.I,
                                      psse_transformer.K, psse_transformer.CKT)
            bus_3 = find_terminal_bus(terminal_bus_lookup, '3', psse_transformer.K, psse_transformer.I,
                                      psse_transformer.J, psse_transformer.CKT)

            if bus_1 is not None:
                transformer.bus1 = bus_1
            else:
                transformer.bus1 = transformer.bus1

            if bus_2 is not None:
                transformer.bus2 = bus_2
            else:
                transformer.bus2 = transformer.bus2

            if bus_3 is not None:
                transformer.bus3 = bus_3
            else:
                transformer.bus3 = transformer.bus3

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
        branch = get_veragrid_line(psse_branch, psse_bus_dict, psse_circuit.SBASE, logger, use_short_names)

        bus_from = find_terminal_bus(terminal_bus_lookup, 'B', psse_branch.I, psse_branch.J, 0, psse_branch.CKT)
        bus_to = find_terminal_bus(terminal_bus_lookup, 'B', psse_branch.J, psse_branch.I, 0, psse_branch.CKT)
        if bus_from is not None:
            branch.bus_from = bus_from
        else:
            branch.bus_from = branch.bus_from

        if bus_to is not None:
            branch.bus_to = bus_to
        else:
            branch.bus_to = branch.bus_to

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

    # Go through switches
    for psse_switch in psse_circuit.switches:
        switch = get_veragrid_switch(psse_switch, psse_bus_dict, logger)

        if switch is not None:
            switch_key = psse_switch.get_id()
            if switch_key not in branches_already_there:
                circuit.add_switch(switch)
                branches_already_there.add(switch_key)
            else:
                logger.add_warning('The RAW file has a repeated switch device and it is omitted from the model',
                                   switch_key)

    for psse_substation_switch in psse_circuit.substation_switching_devices:
        switch = create_substation_switch(psse_substation_switch, node_bus_by_substation_node, logger)
        if switch is not None:
            switch_key = psse_substation_switch.get_id()
            if switch_key not in branches_already_there:
                circuit.add_switch(switch)
                branches_already_there.add(switch_key)
            else:
                logger.add_warning('The RAW file has a repeated substation switch and it is omitted from the model',
                                   switch_key)
        else:
            switch = switch

    # Go through hvdc lines
    for psse_branch in psse_circuit.vsc_dc_lines:
        # get the object
        branch = get_hvdc_from_vscdc(psse_branch, psse_bus_dict, psse_circuit.SBASE, logger)

        if branch is not None:
            bus_from = find_terminal_bus(terminal_bus_lookup, 'V', psse_branch.IBUS1, 0, 0, psse_branch.NAME)
            bus_to = find_terminal_bus(terminal_bus_lookup, 'V', psse_branch.IBUS2, 0, 0, psse_branch.NAME)
            if bus_from is not None:
                branch.bus_from = bus_from
            else:
                branch.bus_from = branch.bus_from

            if bus_to is not None:
                branch.bus_to = bus_to
            else:
                branch.bus_to = branch.bus_to

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
            bus_from = find_terminal_bus(terminal_bus_lookup, 'D', psse_branch.IPR, 0, 0, psse_branch.NAME)
            bus_to = find_terminal_bus(terminal_bus_lookup, 'D', psse_branch.IPI, 0, 0, psse_branch.NAME)
            if bus_from is not None:
                branch.bus_from = bus_from
            else:
                branch.bus_from = branch.bus_from

            if bus_to is not None:
                branch.bus_to = bus_to
            else:
                branch.bus_to = branch.bus_to

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

    # Resolve auxiliary identities only after canonical RAW-derived devices exist.
    if psse_circuit.get_auxiliary_documents():
        from VeraGridEngine.IO.raw.auxiliary_to_veragrid import PsseAuxiliaryConverter
        PsseAuxiliaryConverter(psse_circuit, circuit, psse_bus_dict, logger).convert()
    else:
        pass

    return circuit
