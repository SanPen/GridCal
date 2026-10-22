# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import math
import re
import numpy as np
from typing import Dict, List, Set, Tuple, TypeVar

from VeraGridEngine.enumerations import (
    ExternalGridMode,
    SwitchGraphicType,
    TapChangerTypes,
    TapModuleControl,
    WindingType,
    ShuntControlMode,
    ConverterControlType,
    ConverterFaultControlType,
    GeneratorType,
    GeneratorControlMode,
    StaticGeneratorControlMode,
    BusGraphicType,
    ShuntConnectionType,
    DynamicSimulationMode,
)
import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType, WireInTower
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_logical_actuator_binding import (
    bind_dgs_logical_actuator_runtime,
    prepare_dgs_logical_actuator_topology,
    release_dgs_logical_actuator_import_context,
)
from VeraGridEngine.IO.dgs.dgs_rms_measurement_binding import bind_dgs_rms_measurements
from VeraGridEngine.IO.dgs.dgs_rms_preparation import (
    bind_dgs_switch_event_runtime,
    prepare_dgs_circuit_for_rms,
)
from VeraGridEngine.IO.dgs.dynamic_models.dynamic_model_import import (
    DgsDynamicTemplateConversionResult,
    apply_dgs_dynamic_templates_to_devices,
    convert_and_add_dgs_dynamic_templates_to_circuit,
)
from VeraGridEngine.IO.dgs.dgs_objects import *

TDgsObject = TypeVar("TDgsObject")

PhaseMap = Dict[Tuple[str, int], int]

_PHASE_NAME_PATTERN = re.compile(r"SP1|SP2|DP1|DP2|SP|[ABCN]")
_LOCAL_PHASE_INDEX: Dict[str, int] = {
    "A": 0,
    "B": 1,
    "C": 2,
    "N": 3,
    "SP": 0,
    "SP1": 0,
    "SP2": 1,
    "DP1": 0,
    "DP2": 1,
}
_GLOBAL_PHASE_INDEX: Dict[str, int] = {
    "N": 0,
    "A": 1,
    "B": 2,
    "C": 3,
}


def _is_element_closed_by_cubicle_switches(
        element_id: str,
        cubics_by_objid: Dict[str, List[StaCubic]],
        switch_by_cubic_id: Dict[str, StaSwitch],
) -> bool:
    """
    Is element closed by cubicle switches.

    :param element_id: element_id parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :return: Function result.
    """
    cbs = cubics_by_objid.get(_ref_id(element_id), [])
    if not cbs:
        return True  # no cubicles found -> keep legacy behavior
    found_switch = False
    for cb in cbs:
        cb_id = _ref_id(cb.ID)
        if not cb_id:
            continue
        sw = switch_by_cubic_id.get(cb_id)
        if sw is None:
            continue
        found_switch = True
        if int(sw.on_off) == 0:
            return False
    # if no StaSwitch rows for those cubicles, keep backward-compatible behavior
    return True if not found_switch else True


def _get_tr3_winding_closed_states(
        tr3_id: str,
        cubics_by_objid: Dict[str, List[StaCubic]],
        switch_by_cubic_id: Dict[str, StaSwitch],
        bus_by_term_id: Dict[str, dev.Bus],
        bus_hv: dev.Bus,
        bus_mv: dev.Bus,
        bus_lv: dev.Bus,
) -> tuple[bool, bool, bool]:
    """
    Get tr3 winding closed states.

    :param tr3_id: tr3_id parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param bus_hv: bus_hv parameter.
    :param bus_mv: bus_mv parameter.
    :param bus_lv: bus_lv parameter.
    :return: Function result.
    """
    hv_closed = True
    mv_closed = True
    lv_closed = True
    for cb in cubics_by_objid.get(_ref_id(tr3_id), []):
        cb_id = _ref_id(cb.ID)
        term_id = _ref_id(cb.fold_id)
        if not cb_id or not term_id:
            continue
        sw = switch_by_cubic_id.get(cb_id)
        if sw is None:
            continue  # no StaSwitch => keep default True
        is_closed = int(sw.on_off) != 0
        bus = bus_by_term_id.get(term_id)
        if bus is bus_hv:
            hv_closed = hv_closed and is_closed
        elif bus is bus_mv:
            mv_closed = mv_closed and is_closed
        elif bus is bus_lv:
            lv_closed = lv_closed and is_closed
    return hv_closed, mv_closed, lv_closed


def _ref_id(x: str | None) -> str | None:
    """
    Ref id.

    :param x: x parameter.
    :return: Function result.
    """
    if x is None:
        return None
    s = str(x)
    if "\\" in s:
        return s.split("\\")[-1]
    else:
        return s


def _get_cubic_phase_names(cubic: StaCubic) -> List[str]:
    """
    Parse the local phase names stored in ``StaCubic.cPhInfo``.

    Examples: ``aN`` becomes ``[A, N]`` and ``SPN`` becomes ``[SP, N]``.

    :param cubic: PowerFactory cubicle.
    :return: Local phase names in their displayed order.
    """
    return _PHASE_NAME_PATTERN.findall((cubic.cPhInfo or "").upper())


def _get_cubic_active_phase_indices(cubic: StaCubic) -> Set[int]:
    """
    Return the local conductor indices that are connected in a cubicle.

    The ``it2p`` fields may contain default values for disconnected conductors,
    so ``cPhInfo`` is used to determine which values are meaningful.

    :param cubic: PowerFactory cubicle.
    :return: Connected local conductor indices.
    """
    return {_LOCAL_PHASE_INDEX[name] for name in _get_cubic_phase_names(cubic)}


def _get_cubic_phases(cubic: StaCubic, phase_map: PhaseMap) -> List[int]:
    """
    Return the resolved N/A/B/C phases used by a cubicle.

    The returned order follows the element phase order ``it2p1``, ``it2p2``
    and ``it2p3``. Active conductors without an ``it2p`` slot, normally the
    neutral of an ABCN cubicle, are appended. Unresolved conductors are omitted.

    :param cubic: PowerFactory cubicle.
    :param phase_map: Resolved terminal-conductor phase map.
    :return: Global phase indices (0=N, 1=A, 2=B, 3=C).
    """
    terminal_id = _ref_id(cubic.fold_id)
    if terminal_id is None:
        return []

    active_indices = _get_cubic_active_phase_indices(cubic)
    used_indices: Set[int] = set()
    phases: List[int] = []

    for attribute in ("it2p1", "it2p2", "it2p3"):
        local_index = int(getattr(cubic, attribute))
        if local_index in active_indices and local_index not in used_indices:
            used_indices.add(local_index)
            phase = phase_map.get((terminal_id, local_index))
            if phase is not None:
                phases.append(phase)

    # StaCubic has only three it2p fields. In a four-wire ABCN cubicle the
    # neutral is present in cPhInfo but has no explicit it2p slot.
    for local_index in sorted(active_indices - used_indices):
        phase = phase_map.get((terminal_id, local_index))
        if phase is not None:
            phases.append(phase)

    return phases


def _get_element_phases(element_id: str,
                        cubics_by_objid: Dict[str, List[StaCubic]],
                        phase_map: PhaseMap) -> List[int]:
    """
    Return all resolved phases connected to an element.

    :param element_id: DGS element identifier.
    :param cubics_by_objid: Cubicles grouped by connected element.
    :param phase_map: Resolved terminal-conductor phase map.
    :return: Sorted unique global phase indices.
    """
    phases: Set[int] = set()
    for cubic in cubics_by_objid.get(_ref_id(element_id), []):
        phases.update(_get_cubic_phases(cubic=cubic, phase_map=phase_map))
    return sorted(phases)


def _stacubic_obj_bus_sort_key(cubic: StaCubic) -> int:
    """
    Stacubic obj bus sort key.

    :param cubic: cubic parameter.
    :return: Function result.
    """
    return int(cubic.obj_bus)


def _bus_vnom_sort_key(bus: dev.Bus) -> float:
    """
    Bus vnom sort key.

    :param bus: bus parameter.
    :return: Function result.
    """
    return float(bus.Vnom)


def _resolve_pointer_dict_value(key: str | None, mapping: Dict[str, TDgsObject]) -> TDgsObject | None:
    """
    Resolve pointer dict value.

    :param key: key parameter.
    :param mapping: mapping parameter.
    :return: Function result.
    """
    if key is None:
        return None
    value = mapping.get(key, None)
    if value is not None:
        return value
    normalized_key = _ref_id(key)
    if normalized_key is not None:
        return mapping.get(normalized_key, None)
    else:
        return None


def _get_non_empty_name(name: str | None, default_value: str) -> str:
    """
    Get non empty name.

    :param name: name parameter.
    :param default_value: default_value parameter.
    :return: Function result.
    """
    if name is not None and str(name).strip() != "":
        return str(name)
    else:
        return default_value


def _get_parallel_device_count(count: int) -> int:
    """
    Get parallel device count.

    :param count: count parameter.
    :return: Function result.
    """
    if count > 1:
        return int(count)
    else:
        return 1


def _get_parallel_device_name(base_name: str, parallel_index: int, parallel_count: int) -> str:
    """
    Get parallel device name.

    :param base_name: base_name parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    if parallel_count <= 1:
        return base_name
    else:
        return f"{base_name} ({parallel_index + 1})"


def _get_parallel_device_idtag(base_id: str | None, parallel_index: int, parallel_count: int) -> str | None:
    """
    Get parallel device idtag.

    :param base_id: base_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    if base_id is None or base_id == "":
        return None
    else:
        if parallel_count <= 1:
            return base_id
        else:
            return f"{base_id}:{parallel_index + 1}"


def _get_transformer_tap_changer_type(typtr2: TypTr2) -> TapChangerTypes:
    """
    Get transformer tap changer type.

    :param typtr2: typtr2 parameter.
    :return: Function result.
    """
    if int(typtr2.itapch) == 0:
        return TapChangerTypes.NoRegulation
    else:
        pass

    phase_deg = float(typtr2.phitr)
    phase_mod = math.fmod(abs(phase_deg), 180.0)
    if abs(phase_mod) < 1e-9:
        return TapChangerTypes.VoltageRegulation
    else:
        if abs(phase_mod - 90.0) < 1e-6:
            return TapChangerTypes.Asymmetrical
        else:
            return TapChangerTypes.Symmetrical


def _get_safe_tap_value(value: float, fallback_value: float) -> float:
    """
    Get safe tap value.

    :param value: value parameter.
    :param fallback_value: fallback_value parameter.
    :return: Function result.
    """
    minimum_positive_value: float = 1e-6
    fallback: float = float(fallback_value)
    if not math.isfinite(fallback) or fallback <= 0.0:
        fallback = 1.0
    else:
        pass

    candidate: float = float(value)
    if not math.isfinite(candidate):
        return fallback
    else:
        pass

    if candidate <= 0.0:
        return fallback
    else:
        pass

    if candidate < minimum_positive_value:
        return minimum_positive_value
    else:
        return candidate


def _sanitize_tap_window(
        tap_value: float,
        tap_min_value: float,
        tap_max_value: float,
        fallback_tap_value: float,
        fallback_tap_min_value: float,
        fallback_tap_max_value: float,
) -> Tuple[float, float, float]:
    """
    Sanitize tap window.

    :param tap_value: tap_value parameter.
    :param tap_min_value: tap_min_value parameter.
    :param tap_max_value: tap_max_value parameter.
    :param fallback_tap_value: fallback_tap_value parameter.
    :param fallback_tap_min_value: fallback_tap_min_value parameter.
    :param fallback_tap_max_value: fallback_tap_max_value parameter.
    :return: Function result.
    """
    safe_tap_min: float = _get_safe_tap_value(tap_min_value, fallback_tap_min_value)
    safe_tap_max: float = _get_safe_tap_value(tap_max_value, fallback_tap_max_value)

    if safe_tap_min > safe_tap_max:
        original_minimum: float = safe_tap_min
        safe_tap_min = safe_tap_max
        safe_tap_max = original_minimum
    else:
        pass

    safe_tap: float = _get_safe_tap_value(tap_value, fallback_tap_value)
    if safe_tap < safe_tap_min:
        safe_tap = safe_tap_min
    else:
        pass

    if safe_tap > safe_tap_max:
        safe_tap = safe_tap_max
    else:
        pass

    return safe_tap, safe_tap_min, safe_tap_max


def _apply_branch_tap_state(
        branch: dev.Transformer2W,
        tap_value: float,
        tap_phase: float,
        tap_min_value: float,
        tap_max_value: float,
        tap_phase_min: float,
        tap_phase_max: float,
) -> None:
    """
    Apply branch tap state.

    :param branch: branch parameter.
    :param tap_value: tap_value parameter.
    :param tap_phase: tap_phase parameter.
    :param tap_min_value: tap_min_value parameter.
    :param tap_max_value: tap_max_value parameter.
    :param tap_phase_min: tap_phase_min parameter.
    :param tap_phase_max: tap_phase_max parameter.
    :return: Function result.
    """
    branch.tap_module = float(tap_value)
    branch.tap_phase = float(tap_phase)
    branch.tap_module_min = float(tap_min_value)
    branch.tap_module_max = float(tap_max_value)
    branch.tap_phase_min = float(tap_phase_min)
    branch.tap_phase_max = float(tap_phase_max)


def _get_switch_impedance_in_pu(r_ohm: float, x_ohm: float, vnom_kv: float, sbase_mva: float) -> Tuple[float, float]:
    """
    Get switch impedance in pu.

    :param r_ohm: r_ohm parameter.
    :param x_ohm: x_ohm parameter.
    :param vnom_kv: vnom_kv parameter.
    :param sbase_mva: sbase_mva parameter.
    :return: Function result.
    """
    if vnom_kv <= 0.0 or sbase_mva <= 0.0:
        return 1e-20, 1e-20
    else:
        pass

    zbase_ohm = (vnom_kv * vnom_kv) / sbase_mva
    if zbase_ohm <= 0.0:
        return 1e-20, 1e-20
    else:
        pass

    r_pu = float(r_ohm) / zbase_ohm
    x_pu = float(x_ohm) / zbase_ohm

    return r_pu, x_pu


def _line_section_index_sort_key(section: ElmLnesec) -> float:
    """
    Line section index sort key.

    :param section: section parameter.
    :return: Function result.
    """
    return float(section.index)


def _get_unique_name_mapping(lines: List[ElmLne], use_characteristic_name: bool) -> Dict[str, str]:
    """
    Get unique name mapping.

    :param lines: lines parameter.
    :param use_characteristic_name: use_characteristic_name parameter.
    :return: Function result.
    """
    counts: Dict[str, int] = dict()
    values: Dict[str, str] = dict()
    for line in lines:
        if use_characteristic_name:
            name = str(line.chr_name)
        else:
            name = str(line.loc_name)
        if name == "":
            continue
        counts[name] = counts.get(name, 0) + 1
        values[name] = _ref_id(line.ID) or line.ID

    mapping: Dict[str, str] = dict()
    for name, count in counts.items():
        if count == 1:
            mapping[name] = values[name]
        else:
            pass
    return mapping


def _resolve_line_section_owner_id(section: ElmLnesec,
                                   line_ids: Set[str],
                                   folder_parent: Dict[str, str],
                                   line_id_by_loc_name: Dict[str, str],
                                   line_id_by_chr_name: Dict[str, str]) -> str:
    """
    Resolve line section owner id.

    :param section: section parameter.
    :param line_ids: line_ids parameter.
    :param folder_parent: folder_parent parameter.
    :param line_id_by_loc_name: line_id_by_loc_name parameter.
    :param line_id_by_chr_name: line_id_by_chr_name parameter.
    :return: Function result.
    """
    current = _ref_id(section.fold_id) or str(section.fold_id)
    if current != "":
        for _ in range(25):
            if current in line_ids:
                return current
            parent_ptr = folder_parent.get(current, "")
            if parent_ptr == "":
                break
            current = _ref_id(parent_ptr) or parent_ptr
    else:
        pass

    if section.loc_name != "":
        owner_line_id = line_id_by_loc_name.get(section.loc_name, "")
        if owner_line_id != "":
            return owner_line_id
        else:
            pass
    else:
        pass

    if section.chr_name != "":
        return line_id_by_chr_name.get(section.chr_name, "")
    else:
        return ""


def get_terminal_ids(element_id: str, cubics_by_objid: Dict[str, List[StaCubic]]) -> List[str]:
    """
    Get terminal ids.

    :param element_id: element_id parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :return: Function result.
    """
    cbs: List[StaCubic] = list()
    cbs_raw: List[StaCubic] = cubics_by_objid.get(_ref_id(element_id), list())
    for cubic in cbs_raw:
        fold_id = _ref_id(cubic.fold_id)
        if fold_id is not None and fold_id != "":
            cbs.append(cubic)
        else:
            pass

    if len(cbs) == 2:
        cbs = sorted(cbs, key=_stacubic_obj_bus_sort_key)
    else:
        pass

    terminal_ids: List[str] = list()
    for cubic in cbs:
        fold_id = _ref_id(cubic.fold_id)
        if fold_id is not None and fold_id != "":
            terminal_ids.append(fold_id)
        else:
            pass

    return terminal_ids


def get_branch_buses(elm_id: str,
                     stacubic_dict: Dict[str, List[int]],
                     buses: List[dev.Bus],
                     cubics_by_objid: Dict[str, List[StaCubic]],
                     bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.Bus]:
    """
    Get branch buses.

    :param elm_id: elm_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 2:
        return bus_by_term_id[term_ids[0]], bus_by_term_id[term_ids[1]]

    # Legacy fallback (index-based), kept for backward compatibility
    elm_id_ref = _ref_id(elm_id)
    bus_ids = stacubic_dict.get(elm_id_ref, None)
    if bus_ids is None:
        raise ValueError(f"No buses for the line {elm_id}")

    if len(bus_ids) != 2:
        raise ValueError(f"Not exactly 2 buses for the line {elm_id}")

    bus_from = buses[bus_ids[0]]
    bus_to = buses[bus_ids[1]]

    return bus_from, bus_to


def get_injection_bus(elm_id: str,
                      stacubic_dict: Dict[str, List[int]],
                      buses: List[dev.Bus],
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus]) -> dev.Bus:
    """
    Get injection bus.

    :param elm_id: elm_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 1:
        return bus_by_term_id[term_ids[0]]

    # Legacy fallback (index-based), kept for backward compatibility
    elm_id_ref = _ref_id(elm_id)
    bus_ids = stacubic_dict.get(elm_id_ref, None)
    if bus_ids is None or len(bus_ids) == 0:
        raise ValueError(f"No buses for the element {elm_id}")

    if len(bus_ids) != 1:
        raise ValueError(f"Not exactly 1 bus for the element {elm_id}")

    return buses[bus_ids[0]]


def convert_dgs_to_bus(elmterm: ElmTerm,
                       pos_by_objid: Dict[str, Tuple[float, float]]) -> dev.Bus:
    """
    Convert dgs to bus.

    :param elmterm: elmterm parameter.
    :param pos_by_objid: pos_by_objid parameter.
    :return: Function result.
    """
    tid = _ref_id(elmterm.ID)
    x, y = pos_by_objid.get(tid, (0.0, 0.0))
    # Preserve a solved DGS snapshot as a numerical seed while keeping the
    # configured voltage target independent from optional measured results.
    measured_voltage_magnitude: float = float(elmterm.m_u)
    measured_voltage_angle_radians: float = math.radians(float(elmterm.m_phiu))
    if measured_voltage_magnitude > 0.0 and math.isfinite(measured_voltage_magnitude):
        initial_voltage_magnitude: float = measured_voltage_magnitude
        initial_voltage_angle: float = measured_voltage_angle_radians
    else:
        initial_voltage_magnitude = 1.0
        initial_voltage_angle = 0.0

    bus = dev.Bus(
        name=elmterm.loc_name or f"Bus_{tid}",
        idtag=tid,
        Vnom=float(elmterm.uknom),
        # Alex review required: preserve the native AC/DC domain used to resolve VSC terminals.
        is_dc=(int(elmterm.systype or 0) == 1),
        vmin=0.9,
        vmax=1.1,
        xpos=float(x) * 5,
        ypos=float(-y) * 5,
        active=(int(elmterm.outserv or 0) == 0),
        Vm0=initial_voltage_magnitude,
        Va0=initial_voltage_angle,
        graphic_type=(
            BusGraphicType.BusBar
            if int(elmterm.iUsage or 0) == 0
            else BusGraphicType.Connectivity
        ),
    )

    if measured_voltage_magnitude > 0.0 and math.isfinite(measured_voltage_magnitude):
        pass
    elif float(elmterm.vtarget) > 0.0:
        bus.Vm0 = float(elmterm.vtarget)
    else:
        pass

    return bus


def convert_dgs_to_sequence_line(typlne: TypLne) -> dev.SequenceLineType:
    """
    Convert dgs to sequence line.

    :param typlne: typlne parameter.
    :return: Function result.
    """
    resistance: float = 0.0 if typlne.rline is None else float(typlne.rline)
    reactance: float = 0.0 if typlne.xline is None else float(typlne.xline)
    susceptance: float = 0.0 if typlne.bline is None else float(typlne.bline)
    capacitance_uf: float = 0.0 if typlne.cline is None else float(typlne.cline)
    nominal_voltage: float = 0.0 if typlne.uline is None else float(typlne.uline)
    rated_current: float = 0.0 if typlne.sline is None else float(typlne.sline)
    elm = dev.SequenceLineType(
        name=typlne.loc_name,
        R=resistance,
        X=reactance,
        B=susceptance,
        CnF=capacitance_uf * 1000.0,
        R0=typlne.rline0,
        X0=typlne.xline0,
        B0=typlne.bline0,
        CnF0=typlne.cline0 * 1000,
        Vnom=nominal_voltage,
        Imax=rated_current,
        use_conductance=capacitance_uf != 0.0,
    )

    return elm


def _get_dgs_line_installation_type(
        typlne: TypLne,
) -> PowerFactoryLineInstallationType:
    """Resolve cable or overhead evidence without guessing a source default.

    Older PowerFactory DGS files declare ``aohl_`` as ``cab`` or ``ohl``.
    Current files declare ``cohl_`` as 0 or 1. When both are present they must
    agree; an absent, invalid, or contradictory declaration remains explicit
    uncertainty and cannot authorize creation of a physical cable asset.

    :param typlne: Parsed PowerFactory line type.
    :return: Resolved installation classification.
    """
    legacy_declared: bool = typlne.aohl_declared
    legacy_valid: bool = not legacy_declared
    legacy_type: PowerFactoryLineInstallationType = (
        PowerFactoryLineInstallationType.Unknown
    )
    if legacy_declared:
        if typlne.aohl_ is None:
            legacy_valid = False
        else:
            legacy_code: str = str(typlne.aohl_).strip().lower()
            if legacy_code == 'cab':
                legacy_type = PowerFactoryLineInstallationType.Cable
                legacy_valid = True
            else:
                if legacy_code == 'ohl':
                    legacy_type = PowerFactoryLineInstallationType.Overhead
                    legacy_valid = True
                else:
                    legacy_valid = False
    else:
        pass

    current_declared: bool = typlne.cohl_declared
    current_valid: bool = not current_declared
    current_type: PowerFactoryLineInstallationType = (
        PowerFactoryLineInstallationType.Unknown
    )
    if current_declared:
        if typlne.cohl_ is None:
            current_valid = False
        else:
            current_code: int = int(typlne.cohl_)
            if current_code == 0:
                current_type = PowerFactoryLineInstallationType.Cable
                current_valid = True
            else:
                if current_code == 1:
                    current_type = PowerFactoryLineInstallationType.Overhead
                    current_valid = True
                else:
                    current_valid = False
    else:
        pass

    # A malformed declared field is source ambiguity even if the other field
    # happens to look usable. Silently ignoring it could hide an edited file.
    has_invalid_declaration: bool = not legacy_valid or not current_valid
    if has_invalid_declaration:
        result = PowerFactoryLineInstallationType.Unknown
    else:
        if legacy_declared and current_declared:
            if legacy_type == current_type:
                result = legacy_type
            else:
                result = PowerFactoryLineInstallationType.Conflict
        else:
            if legacy_declared:
                result = legacy_type
            else:
                if current_declared:
                    result = current_type
                else:
                    result = PowerFactoryLineInstallationType.Unknown
    return result


def convert_dgs_to_dc_cable_type(typlne: TypLne,
                                 logger: Logger) -> dev.UndergroundLineType | None:
    """
    Convert one physically complete PowerFactory DC cable declaration.

    Reactance is converted to frequency-neutral inductance. PowerFactory can
    export capacitance directly or as susceptance at the nominal frequency;
    direct capacitance is canonical when both representations are available.
    A type with missing or zero energy data is not materialized because those
    parser values do not prove that the physical cable has zero stored energy.

    :param typlne: PowerFactory line type explicitly marked as a DC cable.
    :param logger: Import logger receiving the resistive-fallback warning.
    :return: Physical DC cable type, or ``None`` when evidence is incomplete.
    """
    installation_type: PowerFactoryLineInstallationType = (
        _get_dgs_line_installation_type(typlne=typlne)
    )
    is_dc_system_type: bool = int(typlne.systp) == 1

    # The electrical system code and the physical installation code answer
    # different questions. Both must support a DC cable before creating the
    # reusable asset that will later be assigned to DcLine.
    if not is_dc_system_type:
        logger.add_warning(
            msg='Line type is not declared as DC; not creating Cable System',
            device=typlne.loc_name,
            device_class='TypLne',
            device_property='systp',
        )
        return None
    else:
        pass

    if installation_type == PowerFactoryLineInstallationType.Cable:
        pass
    else:
        if installation_type == PowerFactoryLineInstallationType.Overhead:
            logger.add_info(
                msg='DC line type is explicitly overhead; keeping resistive DcLine without a cable template',
                device=typlne.loc_name,
                device_class='TypLne',
                device_property='aohl_/cohl_',
            )
        else:
            if installation_type == PowerFactoryLineInstallationType.Conflict:
                logger.add_warning(
                    msg='DGS line installation fields disagree; not creating Cable System',
                    device=typlne.loc_name,
                    device_class='TypLne',
                    device_property='aohl_/cohl_',
                )
            else:
                logger.add_warning(
                    msg='DGS line type does not explicitly identify a cable; not creating Cable System',
                    device=typlne.loc_name,
                    device_class='TypLne',
                    device_property='aohl_/cohl_',
                )
        return None

    rated_current_source: float | None
    if typlne.sline is not None:
        rated_current_source = float(typlne.sline)
    else:
        if typlne.InomAir is not None:
            rated_current_source = float(typlne.InomAir)
        else:
            rated_current_source = None

    has_required_fields: bool = (
            typlne.uline is not None
            and rated_current_source is not None
            and typlne.rline is not None
            and typlne.xline is not None
            and (typlne.cline is not None or typlne.bline is not None)
            and typlne.frnom is not None
    )
    if has_required_fields:
        nominal_voltage: float = float(typlne.uline)
        rated_current: float = float(rated_current_source)
        resistance_ohm_per_km: float = float(typlne.rline)
        reactance_ohm_per_km: float = float(typlne.xline)
        frequency_hz: float = float(typlne.frnom)

        # The frequency is needed to recover physical inductance and to
        # interpret susceptance when direct capacitance was not exported.
        angular_frequency: float = 2.0 * math.pi * frequency_hz
        if typlne.cline is not None:
            capacitance_uf_per_km: float = float(typlne.cline)

            # Both fields describe the same cable quantity. Keep the physical
            # capacitance and report externally edited or incoherent DGS data.
            if typlne.bline is not None:
                susceptance_us_per_km: float = float(typlne.bline)
                expected_susceptance_us_per_km: float = (
                        angular_frequency * capacitance_uf_per_km
                )
                has_comparable_capacitance_fields: bool = (
                        math.isfinite(capacitance_uf_per_km)
                        and math.isfinite(susceptance_us_per_km)
                        and math.isfinite(expected_susceptance_us_per_km)
                )
                if has_comparable_capacitance_fields:
                    capacitance_fields_match: bool = math.isclose(
                        susceptance_us_per_km,
                        expected_susceptance_us_per_km,
                        rel_tol=1.0e-6,
                        abs_tol=1.0e-9,
                    )
                    if capacitance_fields_match:
                        pass
                    else:
                        logger.add_warning(
                            msg='DC cable capacitance and susceptance are inconsistent; using capacitance',
                            device=typlne.loc_name,
                            device_class='TypLne',
                            value=susceptance_us_per_km,
                            expected_value=expected_susceptance_us_per_km,
                            device_property='bline',
                        )
                else:
                    pass
            else:
                susceptance_us_per_km = 0.0
        else:
            # DGS export definitions may omit cline. In that case bline still
            # carries the same capacitance at the declared nominal frequency.
            susceptance_us_per_km = float(typlne.bline)
            if math.isfinite(angular_frequency) and angular_frequency > 0.0:
                capacitance_uf_per_km = (
                        susceptance_us_per_km / angular_frequency
                )
            else:
                capacitance_uf_per_km = 0.0

        has_valid_values: bool = (
                math.isfinite(nominal_voltage)
                and nominal_voltage > 0.0
                and math.isfinite(rated_current)
                and rated_current >= 0.0
                and math.isfinite(resistance_ohm_per_km)
                and resistance_ohm_per_km >= 0.0
                and math.isfinite(reactance_ohm_per_km)
                and reactance_ohm_per_km > 0.0
                and math.isfinite(capacitance_uf_per_km)
                and capacitance_uf_per_km > 0.0
                and math.isfinite(frequency_hz)
                and frequency_hz > 0.0
        )
    else:
        nominal_voltage = 0.0
        rated_current = 0.0
        resistance_ohm_per_km = 0.0
        reactance_ohm_per_km = 0.0
        susceptance_us_per_km = 0.0
        capacitance_uf_per_km = 0.0
        frequency_hz = 0.0
        angular_frequency = 0.0
        has_valid_values = False

    if has_required_fields and has_valid_values:
        inductance_h_per_km: float = reactance_ohm_per_km / angular_frequency
        capacitance_f_per_km: float = capacitance_uf_per_km * 1.0e-6
        return dev.UndergroundLineType(
            name=typlne.loc_name,
            Vnom=nominal_voltage,
            Imax=rated_current,
            R=resistance_ohm_per_km,
            X=angular_frequency * inductance_h_per_km,
            C=capacitance_f_per_km * 1.0e6,
            B=angular_frequency * capacitance_f_per_km * 1.0e6,
            freq=frequency_hz,
        )
    else:
        logger.add_warning(
            msg='DC cable type lacks complete physical L/C evidence; using resistive DcLine fallback',
            device=typlne.loc_name,
            device_class='TypLne',
            value='X, C or B, and frequency must be present and positive',
        )
        return None


def _get_dc_resistance_pu(source_type: TypLne,
                          length: float,
                          line_voltage: float,
                          base_mva: float) -> float | None:
    """
    Convert the resistive part of one source DC cable type to per unit.

    This helper deliberately consumes only the independently known resistance.
    It does not use missing inductance or capacitance as a reason to discard a
    usable stationary DC branch.

    :param source_type: Parsed PowerFactory line type.
    :param length: Installed cable length in kilometres.
    :param line_voltage: Connected DC bus voltage base in kV.
    :param base_mva: VeraGrid system power base in MVA.
    :return: Total resistance in p.u., or ``None`` when it cannot be derived.
    """
    has_required_values: bool = (
            source_type.rline is not None
            and math.isfinite(float(source_type.rline))
            and float(source_type.rline) >= 0.0
            and math.isfinite(length)
            and length > 0.0
            and math.isfinite(line_voltage)
            and line_voltage > 0.0
            and math.isfinite(base_mva)
            and base_mva > 0.0
    )
    if has_required_values:
        impedance_base: float = line_voltage * line_voltage / base_mva
        return float(source_type.rline) * length / impedance_base
    else:
        return None


def _get_dc_sections_resistance_pu(
        sections: List[ElmLnesec],
        source_line_type_dict: Dict[str, TypLne],
        line_voltage: float,
        base_mva: float,
) -> float | None:
    """
    Sum the independently known resistance of a sectioned DC cable.

    :param sections: Ordered or unordered PowerFactory line sections.
    :param source_line_type_dict: Parsed line types keyed by source pointer.
    :param line_voltage: Connected DC bus voltage base in kV.
    :param base_mva: VeraGrid system power base in MVA.
    :return: Total resistance in p.u., or ``None`` if any section is incomplete.
    """
    total_resistance_pu: float = 0.0
    complete_resistance: bool = True
    section: ElmLnesec
    for section in sections:
        source_type: TypLne | None = _resolve_pointer_dict_value(
            key=section.typ_id,
            mapping=source_line_type_dict,
        )
        if source_type is not None:
            section_resistance_pu: float | None = _get_dc_resistance_pu(
                source_type=source_type,
                length=float(section.dline),
                line_voltage=line_voltage,
                base_mva=base_mva,
            )
            if section_resistance_pu is not None:
                total_resistance_pu += section_resistance_pu
            else:
                complete_resistance = False
        else:
            complete_resistance = False

    if complete_resistance:
        return total_resistance_pu
    else:
        return None


def _bundle_offsets(n_sub: int, spacing_m: float) -> List[Tuple[float, float]]:
    """
    Bundle offsets.

    :param n_sub: n_sub parameter.
    :param spacing_m: spacing_m parameter.
    :return: Function result.
    """
    if n_sub <= 1:
        default_offsets: List[Tuple[float, float]] = list()
        default_offsets.append((0.0, 0.0))
        return default_offsets
    else:
        pass
    if spacing_m <= 0.0:
        default_offsets = list()
        default_offsets.append((0.0, 0.0))
        return default_offsets
    else:
        pass

    # Radius of the circumcircle for a regular n-gon with side length = spacing.
    # r = s / (2*sin(pi/n))
    radius = spacing_m / (2.0 * math.sin(math.pi / float(n_sub)))

    offsets: List[Tuple[float, float]] = list()
    for k in range(n_sub):
        ang = 2.0 * math.pi * float(k) / float(n_sub)
        dx = radius * math.cos(ang)
        dy = radius * math.sin(ang)
        offsets.append((dx, dy))

    return offsets


def convert_dgs_to_wire(typcon: TypCon) -> Wire:
    """
    Convert dgs to wire.

    :param typcon: typcon parameter.
    :return: Function result.
    """
    tid = _ref_id(typcon.ID)
    if typcon.loc_name is not None and str(typcon.loc_name).strip() != "":
        name = typcon.loc_name
    else:
        name = f"Wire_{tid}"

    # PowerFactory: diatub may be 0/empty for non-tubular conductors.
    diatub = float(typcon.diatub)

    # Conductor Model (Solid or Tubular)
    if typcon.iModel == 1:
        is_tube = True
    else:
        is_tube = False

    # Keep a compact but informative stranding label.
    stranding = f"ncsub={int(typcon.ncsub)}, dsubc={float(typcon.dsubc)}"

    wire = Wire(
        name=name,
        idtag=tid,
        r=float(typcon.rpha),
        max_current=float(typcon.sline),
        stranding=stranding,
        material=str(typcon.mlei),
        diameter=float(typcon.diaco),
        diameter_internal=diatub,
        is_tube=is_tube,
        code=str(typcon.loc_name),
    )

    return wire


def _convert_gearth_us_per_cm_to_resistivity_ohm_m(gearth_us_per_cm: float) -> float:
    """
    Convert gearth us per cm to resistivity ohm m.

    :param gearth_us_per_cm: gearth_us_per_cm parameter.
    :return: Function result.
    """
    # uS/cm -> S/m: 1 uS = 1e-6 S; 1/cm = 100/m
    conductivity_s_per_m = float(gearth_us_per_cm) * 1e-4
    if conductivity_s_per_m <= 0.0:
        return 100.0
    return 1.0 / conductivity_s_per_m


def convert_dgs_to_overhead_line_type_geometrical_parameters(
        typtow: TypTow,
        typcon_by_id: Dict[str, TypCon],
        wire_by_id: Dict[str, Wire],
        default_frequency_hz: float,
        phase_order: List[int] | None = None,
) -> dev.OverheadLineType:
    """
    Convert dgs to overhead line type geometrical parameters.

    :param typtow: typtow parameter.
    :param typcon_by_id: typcon_by_id parameter.
    :param wire_by_id: wire_by_id parameter.
    :param default_frequency_hz: default_frequency_hz parameter.
    :param phase_order: Resolved N/A/B/C phase of each physical conductor.
    :return: Function result.
    """

    tid = _ref_id(typtow.ID)
    if typtow.loc_name is not None and str(typtow.loc_name).strip() != "":
        name = typtow.loc_name
    else:
        name = f"Tower_{tid}"

    # Frequency / earth parameters
    if typtow.frnom is not None and float(typtow.frnom) > 0.0:
        freq = float(typtow.frnom)
    else:
        freq = float(default_frequency_hz)

    earth_res = _convert_gearth_us_per_cm_to_resistivity_ohm_m(float(typtow.gearth))

    # Determine nominal voltage from referenced conductor types.
    v_candidates: List[float] = list()
    for ptr in typtow.pcond_c:
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                tc = typcon_by_id.get(cid, None)
                if tc is not None:
                    v_candidates.append(float(tc.uline))

    for ptr in typtow.pcond_e:
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                tc = typcon_by_id.get(cid, None)
                if tc is not None:
                    v_candidates.append(float(tc.uline))

    if len(v_candidates) > 0:
        vnom = max(v_candidates)
    else:
        vnom = 0.0

    ohl_type = OverheadLineType(
        name=name,
        idtag=tid,
        Vnom=vnom,
        earth_resistivity=earth_res,
        frequency=freq,
    )

    # Earth wires (phase 0)
    for ew_idx, ptr in enumerate(typtow.pcond_e):
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                wire = wire_by_id.get(cid, None)
                tc = typcon_by_id.get(cid, None)
                if wire is not None and tc is not None:
                    if ew_idx < len(typtow.xy_e) and len(typtow.xy_e[ew_idx]) >= 2:
                        x0 = float(typtow.xy_e[ew_idx][0])
                        y0 = float(typtow.xy_e[ew_idx][1])
                    else:
                        x0 = 0.0
                        y0 = 0.0

                    offsets = _bundle_offsets(n_sub=int(tc.ncsub), spacing_m=float(tc.dsubc))
                    for dx, dy in offsets:
                        ohl_type.wires_in_tower.append(WireInTower(wire=wire, xpos=x0 + dx, ypos=y0 + dy, phase=0))
                else:
                    pass
            else:
                pass
        else:
            pass

    # Phase wires per circuit. TypTow.xy_c always reserves coordinates for
    # three conductors, but nphas states how many of them actually exist.
    # Expected xy_c row format: [xA, xB, xC, yA, yB, yC]
    phase_cursor = 0
    for c_idx, ptr in enumerate(typtow.pcond_c):
        if c_idx < len(typtow.nphas):
            phase_count = int(typtow.nphas[c_idx])
        else:
            phase_count = 3
        phase_count = max(0, min(phase_count, 3))

        base_phase = 3 * int(c_idx)  # circuit 0 -> phases 1, 2, 3
        circuit_phases: List[int] = []
        for conductor_idx in range(phase_count):
            if phase_order is not None and phase_cursor < len(phase_order):
                circuit_phases.append(phase_order[phase_cursor])
            else:
                circuit_phases.append(base_phase + conductor_idx + 1)
            phase_cursor += 1

        if ptr is not None:

            cid = _ref_id(ptr)
            if cid is not None:
                wire = wire_by_id.get(cid, None)
                tc = typcon_by_id.get(cid, None)
                if wire is not None and tc is not None:
                    if c_idx < len(typtow.xy_c) and len(typtow.xy_c[c_idx]) >= 6:
                        row = typtow.xy_c[c_idx]
                        xA, xB, xC = float(row[0]), float(row[1]), float(row[2])
                        yA, yB, yC = float(row[3]), float(row[4]), float(row[5])
                    else:
                        xA, xB, xC = 0.0, 0.0, 0.0
                        yA, yB, yC = 0.0, 0.0, 0.0

                    offsets = _bundle_offsets(n_sub=int(tc.ncsub), spacing_m=float(tc.dsubc))

                    x_positions = (xA, xB, xC)
                    y_positions = (yA, yB, yC)
                    for conductor_idx, phase in enumerate(circuit_phases):
                        for dx, dy in offsets:
                            ohl_type.wires_in_tower.append(
                                WireInTower(
                                    wire=wire,
                                    xpos=x_positions[conductor_idx] + dx,
                                    ypos=y_positions[conductor_idx] + dy,
                                    phase=phase,
                                )
                            )
                else:
                    pass
            else:
                pass
        else:
            pass

    return ohl_type


def convert_dgs_to_overhead_line_type_electrical_parameters(
        typtow: TypTow,
        typcon_by_id: Dict[str, TypCon],
        wire_by_id: Dict[str, Wire],
        default_frequency_hz: float,
) -> dev.SequenceLineType:
    """
    Convert dgs to overhead line type electrical parameters.

    :param typtow: typtow parameter.
    :param typcon_by_id: typcon_by_id parameter.
    :param wire_by_id: wire_by_id parameter.
    :param default_frequency_hz: default_frequency_hz parameter.
    :return: Function result.
    """

    tid = _ref_id(typtow.ID)
    if typtow.loc_name is not None and str(typtow.loc_name).strip() != "":
        name = typtow.loc_name
    else:
        name = f"Tower_{tid}"

    # Frequency / earth parameters
    if typtow.frnom is not None and float(typtow.frnom) > 0.0:
        freq = float(typtow.frnom)
    else:
        freq = float(default_frequency_hz)

    earth_res = _convert_gearth_us_per_cm_to_resistivity_ohm_m(float(typtow.gearth))

    # Determine nominal voltage from referenced conductor types.
    v_candidates: List[float] = list()
    for ptr in typtow.pcond_c:
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                tc = typcon_by_id.get(cid, None)
                if tc is not None:
                    v_candidates.append(float(tc.uline))

    for ptr in typtow.pcond_e:
        if ptr is not None:
            cid = _ref_id(ptr)
            if cid is not None:
                tc = typcon_by_id.get(cid, None)
                if tc is not None:
                    v_candidates.append(float(tc.uline))

    if len(v_candidates) > 0:
        vnom = max(v_candidates)
    else:
        vnom = 0.0

    ohl_type = dev.SequenceLineType(
        name=name,
        idtag=tid,
        Vnom=vnom,
        R=typtow.R_c1[0][0],
        R0=typtow.R_c0[0][0],
        X=typtow.X_c1[0][0],
        X0=typtow.X_c0[0][0],
    )

    return ohl_type


def _convert_pf_tr2_connection(code: str) -> WindingType | None:
    """
    Convert pf tr2 connection.

    :param code: code parameter.
    :return: Function result.
    """
    if code is None:
        return None

    c = str(code).strip().upper()
    if c == "":
        return None

    # Common PowerFactory 2-char winding codes in DGS: Y, YN, D, Z, ZN
    conversion_dict: Dict[str, WindingType] = {
        "D": WindingType.Delta,
        "Y": WindingType.NeutralStar,
        "YN": WindingType.GroundedStar,
        "Z": WindingType.FloatingZigZag,
        "ZN": WindingType.NeutralZigZag,
    }

    if c in conversion_dict:
        return conversion_dict[c]
    elif c.startswith("Y"):
        # Defensive fallback: any "Y*" treated as star (prefer grounded if it contains N)
        if "N" in c:
            return WindingType.GroundedStar
        return WindingType.NeutralStar
    else:
        return None


def convert_dgs_to_transformer_type(typtr2: TypTr2) -> dev.TransformerType:
    """
    Convert dgs to transformer type.

    :param typtr2: typtr2 parameter.
    :return: Function result.
    """
    tpe = dev.TransformerType(hv_nominal_voltage=float(typtr2.utrn_h),
                              lv_nominal_voltage=float(typtr2.utrn_l),
                              nominal_power=float(typtr2.strn),
                              copper_losses=float(typtr2.pcutr),
                              iron_losses=float(typtr2.pfe),
                              no_load_current=float(typtr2.curmg),
                              short_circuit_voltage=float(typtr2.uktr),
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              total_positions=max(1, int(typtr2.ntpmx) - int(typtr2.ntpmn) + 1),
                              neutral_position=max(0, int(typtr2.nntap0) - int(typtr2.ntpmn)),
                              dV=float(typtr2.dutap) / 100.0,
                              asymmetry_angle=float(typtr2.phitr),
                              tc_type=_get_transformer_tap_changer_type(typtr2=typtr2),
                              name=typtr2.loc_name)

    conn_hv = _convert_pf_tr2_connection(typtr2.tr2cn_h)
    conn_lv = _convert_pf_tr2_connection(typtr2.tr2cn_l)

    if conn_hv is not None:
        tpe.conn_hv = conn_hv

    if conn_lv is not None:
        tpe.conn_lv = conn_lv
    else:
        pass

    vector_group_number = int(round(float(typtr2.nt2ag))) % 12
    tpe.vector_group_number = vector_group_number

    return tpe


def _order_hv_lv(bus_a: dev.Bus, bus_b: dev.Bus, logger: Logger, tr_name: str) -> Tuple[dev.Bus, dev.Bus]:
    """
    Order hv lv.

    :param bus_a: bus_a parameter.
    :param bus_b: bus_b parameter.
    :param logger: logger parameter.
    :param tr_name: tr_name parameter.
    :return: Function result.
    """
    va = float(bus_a.Vnom)
    vb = float(bus_b.Vnom)

    if va == 0.0 or vb == 0.0:
        logger.add_warning(f"Transformer '{tr_name}': one or both buses have Vnom=0.0 (va={va}, vb={vb}).")
        return bus_a, bus_b

    if va > vb:
        return bus_a, bus_b
    if vb > va:
        return bus_b, bus_a

    # Equal-Vnom transformers: HV/LV is ambiguous.
    # Use deterministic lexical ordering by bus name to keep import orientation stable.
    name_a: str = str(bus_a.name or "").strip()
    name_b: str = str(bus_b.name or "").strip()

    if name_a != "" and name_b != "":
        if name_a <= name_b:
            logger.add_warning(
                f"Transformer '{tr_name}': HV/LV ambiguous (equal Vnom={va}). Ordered lexically by bus name."
            )
            return bus_a, bus_b
        else:
            logger.add_warning(
                f"Transformer '{tr_name}': HV/LV ambiguous (equal Vnom={va}). Ordered lexically by bus name."
            )
            return bus_b, bus_a
    else:
        pass

    logger.add_warning(f"Transformer '{tr_name}': HV/LV ambiguous (equal Vnom={va}). Keeping original order.")
    return bus_a, bus_b


def _order_hv_mv_lv(bus_a: dev.Bus, bus_b: dev.Bus, bus_c: dev.Bus, logger: Logger, tr_name: str) -> Tuple[
    dev.Bus, dev.Bus, dev.Bus]:
    """
    Order hv mv lv.

    :param bus_a: bus_a parameter.
    :param bus_b: bus_b parameter.
    :param bus_c: bus_c parameter.
    :param logger: logger parameter.
    :param tr_name: tr_name parameter.
    :return: Function result.
    """
    va = float(bus_a.Vnom)
    vb = float(bus_b.Vnom)
    vc = float(bus_c.Vnom)

    if va == 0.0 or vb == 0.0 or vc == 0.0:
        logger.add_warning(
            f"one or more buses have Vnom=0.0",
            device=tr_name,
            device_class="Transformer3W",
            value=f"(va={va}, vb={vb}, vc={vc})"
        )

        return bus_a, bus_b, bus_c

    buses: List[dev.Bus] = list()
    buses.append(bus_a)
    buses.append(bus_b)
    buses.append(bus_c)
    buses_sorted: List[dev.Bus] = sorted(buses, key=_bus_vnom_sort_key, reverse=True)

    v0 = float(buses_sorted[0].Vnom)
    v1 = float(buses_sorted[1].Vnom)
    v2 = float(buses_sorted[2].Vnom)

    if v0 == v1 or v1 == v2:
        logger.add_warning(
            f"HV/MV/LV ambiguous, keeping Vnom-based ordering ",
            device=tr_name,
            device_class="Transformer3W",
            value=f"(va={va}, vb={vb}, vc={vc})"
        )

    return buses_sorted[0], buses_sorted[1], buses_sorted[2]


def _order_tr4(bus_a: dev.Bus,
               bus_b: dev.Bus,
               bus_c: dev.Bus,
               bus_d: dev.Bus,
               logger: Logger,
               tr_name: str) -> Tuple[dev.Bus, dev.Bus, dev.Bus, dev.Bus, List[int]]:
    """
    Order tr4 buses by voltage and return the original DGS-side indices.

    DGS-side indices:
    0 = h0
    1 = l1
    2 = l2
    3 = l3

    :param bus_a: First DGS-side bus.
    :param bus_b: Second DGS-side bus.
    :param bus_c: Third DGS-side bus.
    :param bus_d: Fourth DGS-side bus.
    :param logger: Logger.
    :param tr_name: Transformer name.
    :return: Ordered buses plus original DGS-side indices.
    """
    va: float = float(bus_a.Vnom)
    vb: float = float(bus_b.Vnom)
    vc: float = float(bus_c.Vnom)
    vd: float = float(bus_d.Vnom)

    if va == 0.0 or vb == 0.0 or vc == 0.0 or vd == 0.0:
        logger.add_warning(
            f"one or more buses have Vnom=0.0",
            device=tr_name,
            device_class="Transformer4W",
            value=f"(va={va}, vb={vb}, vc={vc}, vd={vd})"
        )

        return bus_a, bus_b, bus_c, bus_d, [0, 1, 2, 3]
    else:
        pass

    indexed_buses: List[Tuple[dev.Bus, int]] = list()
    indexed_buses.append((bus_a, 0))
    indexed_buses.append((bus_b, 1))
    indexed_buses.append((bus_c, 2))
    indexed_buses.append((bus_d, 3))

    indexed_buses_sorted: List[Tuple[dev.Bus, int]] = sorted(
        indexed_buses,
        key=lambda item: float(item[0].Vnom),
        reverse=True
    )

    v0: float = float(indexed_buses_sorted[0][0].Vnom)
    v1: float = float(indexed_buses_sorted[1][0].Vnom)
    v2: float = float(indexed_buses_sorted[2][0].Vnom)
    v3: float = float(indexed_buses_sorted[3][0].Vnom)

    if v0 == v1 or v1 == v2 or v2 == v3:
        logger.add_warning(
            f"HV/LV1/LV2/LV3 ambiguous, keeping Vnom-based ordering",
            device=tr_name,
            device_class="Transformer4W",
            value=f"(va={va}, vb={vb}, vc={vc}, vd={vd})"
        )
    else:
        pass

    ordered_original_indices: List[int] = list()
    ordered_original_indices.append(indexed_buses_sorted[0][1])
    ordered_original_indices.append(indexed_buses_sorted[1][1])
    ordered_original_indices.append(indexed_buses_sorted[2][1])
    ordered_original_indices.append(indexed_buses_sorted[3][1])

    return (
        indexed_buses_sorted[0][0],
        indexed_buses_sorted[1][0],
        indexed_buses_sorted[2][0],
        indexed_buses_sorted[3][0],
        ordered_original_indices,
    )


def _apply_tr3_winding_connection_data(
        winding: dev.Winding,
        pf_connection_code: str,
        pf_vector_group_angle: float,
) -> None:
    """
    Apply tr3 winding connection data.

    :param winding: winding parameter.
    :param pf_connection_code: pf_connection_code parameter.
    :param pf_vector_group_angle: pf_vector_group_angle parameter.
    :return: Function result.
    """
    external_connection = _convert_pf_tr2_connection(code=pf_connection_code)
    if external_connection is not None:
        # These branches run from the physical terminal to the internal star.
        winding.conn_f = (WindingType.FloatingStar if pf_connection_code.strip().upper() == 'Y'
                          else external_connection)
        winding.conn_t = WindingType.GroundedStar
    else:
        pass

    winding.vector_group_number = int(round(float(pf_vector_group_angle))) % 12


def _apply_tr3_winding_tap_data(
        winding: dev.Winding,
        current_position: int,
        neutral_position: int,
        minimum_position: int,
        maximum_position: int,
        step_percent: float,
        phase_angle_deg: float,
) -> None:
    """
    Apply tr3 winding tap data.

    :param winding: winding parameter.
    :param current_position: current_position parameter.
    :param neutral_position: neutral_position parameter.
    :param minimum_position: minimum_position parameter.
    :param maximum_position: maximum_position parameter.
    :param step_percent: step_percent parameter.
    :param phase_angle_deg: phase_angle_deg parameter.
    :return: Function result.
    """
    total_positions = int(maximum_position) - int(minimum_position) + 1
    if total_positions <= 0:
        return
    else:
        pass

    tc_type = TapChangerTypes.VoltageRegulation
    if abs(float(phase_angle_deg)) > 1e-12:
        tc_type = TapChangerTypes.Symmetrical
        if abs(abs(float(phase_angle_deg)) % 180.0 - 90.0) < 1e-6:
            tc_type = TapChangerTypes.Asymmetrical
        else:
            pass
    else:
        pass

    winding.tap_changer.total_positions = int(total_positions)
    winding.tap_changer.neutral_position = max(0, int(neutral_position) - int(minimum_position))
    winding.tap_changer.dV = float(step_percent) / 100.0
    winding.tap_changer.asymmetry_angle = float(phase_angle_deg)
    winding.tap_changer.tc_type = tc_type

    tap_position = int(current_position) - int(minimum_position)
    if tap_position < 0:
        tap_position = 0
    else:
        pass
    if tap_position >= winding.tap_changer.total_positions:
        tap_position = winding.tap_changer.total_positions - 1
    else:
        pass
    winding.tap_changer.tap_position = tap_position

    fallback_tap: float = winding.tap_changer.get_tap_module()
    fallback_tap_min: float = winding.tap_changer.get_tap_module_min()
    fallback_tap_max: float = winding.tap_changer.get_tap_module_max()

    if tc_type == TapChangerTypes.VoltageRegulation:
        step = float(step_percent) / 100.0
        tap = 1.0 + (int(current_position) - int(neutral_position)) * step
        tap_min = 1.0 + (int(minimum_position) - int(neutral_position)) * step
        tap_max = 1.0 + (int(maximum_position) - int(neutral_position)) * step

        tap, tap_min, tap_max = _sanitize_tap_window(
            tap_value=tap,
            tap_min_value=tap_min,
            tap_max_value=tap_max,
            fallback_tap_value=fallback_tap,
            fallback_tap_min_value=fallback_tap_min,
            fallback_tap_max_value=fallback_tap_max,
        )

        _apply_branch_tap_state(
            branch=winding,
            tap_value=tap,
            tap_phase=0.0,
            tap_min_value=tap_min,
            tap_max_value=tap_max,
            tap_phase_min=0.0,
            tap_phase_max=0.0,
        )
    else:
        tap_value, tap_min_value, tap_max_value = _sanitize_tap_window(
            tap_value=fallback_tap,
            tap_min_value=fallback_tap_min,
            tap_max_value=fallback_tap_max,
            fallback_tap_value=fallback_tap,
            fallback_tap_min_value=fallback_tap_min,
            fallback_tap_max_value=fallback_tap_max,
        )

        _apply_branch_tap_state(
            branch=winding,
            tap_value=tap_value,
            tap_phase=winding.tap_changer.get_tap_phase(),
            tap_min_value=tap_min_value,
            tap_max_value=tap_max_value,
            tap_phase_min=winding.tap_changer.get_tap_phase_min(),
            tap_phase_max=winding.tap_changer.get_tap_phase_max(),
        )


def _fill_tr4w_simple_values(trafo4w: dev.TransformerNW,
                             nominal_voltages: Tuple[float, float, float, float],
                             nominal_powers: Tuple[float, float, float, float],
                             short_circuit_voltages: Tuple[float, float, float, float],
                             copper_losses: Tuple[float, float, float, float],
                             Pfe: float,
                             I0: float,
                             Sbase: float) -> None:
    """
    Fill four-winding transformer values from simplified per-winding input data.

    :param trafo4w: Four-winding transformer.
    :param nominal_voltages: DGS-side voltages in h0, l1, l2, l3 order.
    :param nominal_powers: DGS-side powers in h0, l1, l2, l3 order.
    :param short_circuit_voltages: DGS-side short-circuit voltages in h0, l1, l2, l3 order.
    :param copper_losses: DGS-side copper losses in h0, l1, l2, l3 order.
    :param ordered_original_indices: Mapping from transformer winding order to original DGS-side order.
    :param Pfe: Shared iron-core losses in kW.
    :param I0: Shared no-load current in percent.
    :param Sbase: System base power in MVA.
    :return: None.
    """

    for winding_index in range(4):
        winding: dev.Winding = trafo4w.windings[winding_index]

        winding.HV = nominal_voltages[winding_index]
        winding.LV = 1.0

        winding.Sn = nominal_powers[winding_index]
        winding.rate = nominal_powers[winding_index]
        winding.design_rate = nominal_powers[winding_index]

        winding.Pcu = copper_losses[winding_index]
        winding.Vsc = short_circuit_voltages[winding_index]

    trafo4w.Pfe = Pfe
    trafo4w.I0 = I0

    trafo4w.recalculate_windings_from_definition(Sbase=Sbase)


def _fill_tr4w_complete_values(
        trafo4w: dev.TransformerNW, V_h0: float, V_l1: float, V_l2: float, V_l3: float,
        Sn_h0: float, Sn_l1: float, Sn_l2: float, Sn_l3: float, Vsc_h0l1: float,
        Vsc_h0l2: float, Vsc_h0l3: float, Vsc_l1l2: float, Vsc_l1l3: float,
        Vsc_l2l3: float, Pcu_h0l1: float, Pcu_h0l2: float, Pcu_h0l3: float,
        Pcu_l1l2: float, Pcu_l1l3: float, Pcu_l2l3: float, Pfe: float,
        I0: float = 0.5, Sbase: float = 100,
) -> None:
    """
    Fill four-winding transformer values from simplified per-winding input data.

    :param trafo4w: Four-winding transformer.
    :param nominal_voltages: DGS-side voltages in h0, l1, l2, l3 order.
    :param nominal_powers: DGS-side powers in h0, l1, l2, l3 order.
    :param short_circuit_voltages: DGS-side short-circuit voltages in h0, l1, l2, l3 order.
    :param copper_losses: DGS-side copper losses in h0, l1, l2, l3 order.
    :param ordered_original_indices: Mapping from transformer winding order to original DGS-side order.
    :param Pfe: Shared iron-core losses in kW.
    :param I0: Shared no-load current in percent.
    :param Sbase: System base power in MVA.
    :return: None.
    """
    Sr_hv = Sn_h0

    def get_pairwise_impedance(
            uk: float,
            pcu: float,
            Sr_a: float,
            Sr_b: float,
    ) -> complex:
        """
        Returns the pairwise short-circuit impedance in p.u.

        uk: short-circuit voltage in %
        pcu: copper losses in kW
        Sr_a, Sr_b: rated powers in MVA
        """

        Sr_pair = min(Sr_a, Sr_b)

        # Total impedance magnitude
        z_abs = (uk / 100.0) * (Sr_hv / Sr_pair)

        # Resistive part
        zr = (pcu / 1000.0) * (Sr_hv / (Sr_pair ** 2))

        # Reactive part
        zi_squared = z_abs ** 2 - zr ** 2

        if zi_squared < 0.0:
            zi = 0.0
        else:
            zi = math.sqrt(zi_squared)

        return complex(zr, zi)

    def parallel(z_a: complex, z_b: complex) -> complex:
        if abs(z_a + z_b) < 1e-12:
            return complex(0.0, 0.0)
        return (z_a * z_b) / (z_a + z_b)

    # Pairwise impedances
    z_h0l1 = get_pairwise_impedance(
        uk=Vsc_h0l1,
        pcu=Pcu_h0l1,
        Sr_a=Sn_h0,
        Sr_b=Sn_l1,
    )

    z_h0l2 = get_pairwise_impedance(
        uk=Vsc_h0l2,
        pcu=Pcu_h0l2,
        Sr_a=Sn_h0,
        Sr_b=Sn_l2,
    )

    z_h0l3 = get_pairwise_impedance(
        uk=Vsc_h0l3,
        pcu=Pcu_h0l3,
        Sr_a=Sn_h0,
        Sr_b=Sn_l3,
    )

    z_l1l2 = get_pairwise_impedance(
        uk=Vsc_l1l2,
        pcu=Pcu_l1l2,
        Sr_a=Sn_l1,
        Sr_b=Sn_l2,
    )

    z_l1l3 = get_pairwise_impedance(
        uk=Vsc_l1l3,
        pcu=Pcu_l1l3,
        Sr_a=Sn_l1,
        Sr_b=Sn_l3,
    )

    z_l2l3 = get_pairwise_impedance(
        uk=Vsc_l2l3,
        pcu=Pcu_l2l3,
        Sr_a=Sn_l2,
        Sr_b=Sn_l3,
    )

    # Equivalent circuit impedances
    k1 = z_h0l2 + z_l1l3 - z_h0l1 - z_l2l3
    k2 = z_h0l2 + z_l1l3 - z_h0l3 - z_l1l2
    k_2 = np.abs(k1 * k2)
    k = math.sqrt(k_2)

    z_internal_i = k1 + k
    z_internal_j = k2 + k

    z_h0 = (z_h0l1 + z_h0l3 - z_l1l3 - k) / 2.0
    z_l1 = (z_h0l1 + z_l1l2 - z_h0l2 - k) / 2.0
    z_l2 = (z_l1l2 + z_l2l3 - z_l1l3 - k) / 2.0
    z_l3 = (z_l2l3 + z_h0l3 - z_h0l2 - k) / 2.0

    # Equivalent internal path impedances
    z_path_l1 = parallel(
        z_internal_i,
        2.0 * z_internal_j + z_internal_i,
    )

    z_path_l2 = parallel(
        z_internal_i + z_internal_j,
        z_internal_j + z_internal_i,
    )

    z_path_l3 = parallel(
        z_internal_j,
        2.0 * z_internal_i + z_internal_j,
    )

    # Add path impedance to each branch impedance
    z_l1 += z_path_l1
    z_l2 += z_path_l2
    z_l3 += z_path_l3

    # Winding-side data in h0, l1, l2, l3 order
    nominal_voltages = [V_h0, V_l1, V_l2, V_l3]
    nominal_powers = [Sn_h0, Sn_l1, Sn_l2, Sn_l3]

    # Use equivalent branch impedances obtained from the complete-input model
    branch_impedances_hv_base = [z_h0, z_l1, z_l2, z_l3]

    # Optional reporting fields, expressed approximately on each winding base
    short_circuit_voltages = []
    copper_losses = []

    for z_branch, Sn_w in zip(branch_impedances_hv_base, nominal_powers):
        # Convert from HV-winding base to each winding rated-power base
        z_winding_base = z_branch * (Sn_w / Sr_hv)

        short_circuit_voltages.append(abs(z_winding_base) * 100.0)
        copper_losses.append(z_winding_base.real * (Sn_w ** 2 / Sn_w) * 1000.0)

    # Assign winding data
    for winding_index in range(4):
        winding: dev.Winding = trafo4w.windings[winding_index]

        z_branch = branch_impedances_hv_base[winding_index]

        # Convert impedance from transformer HV-rated-power base to VeraGrid system base
        z_system_base = z_branch * (Sbase / Sr_hv)

        winding.HV = nominal_voltages[winding_index]
        winding.LV = 1.0

        winding.Sn = nominal_powers[winding_index]
        winding.rate = nominal_powers[winding_index]
        winding.design_rate = nominal_powers[winding_index]

        winding.R = z_system_base.real
        winding.X = z_system_base.imag

        # Negative sequence is normally equal to positive sequence for passive transformer impedances
        winding.R2 = z_system_base.real
        winding.X2 = z_system_base.imag

        winding.Pcu = copper_losses[winding_index]
        winding.Vsc = short_circuit_voltages[winding_index]

    trafo4w.Pfe = Pfe
    trafo4w.I0 = I0


def _apply_tr4_winding_tap_data(
        windings: Tuple[dev.Winding, ...],
        current_positions: Tuple[int, int, int, int],
        neutral_positions: Tuple[int, int, int, int],
        minimum_positions: Tuple[int, int, int, int],
        maximum_positions: Tuple[int, int, int, int],
        step_percents: Tuple[float, float, float, float],
        phase_angle_degs: Tuple[float, float, float, float],
) -> None:
    """
    Apply tr4 winding tap data.

    :param windings: Four transformer windings.
    :param current_positions: Current tap positions for h0, l1, l2 and l3.
    :param neutral_positions: Neutral tap positions for h0, l1, l2 and l3.
    :param minimum_positions: Minimum tap positions for h0, l1, l2 and l3.
    :param maximum_positions: Maximum tap positions for h0, l1, l2 and l3.
    :param step_percents: Tap step percentages for h0, l1, l2 and l3.
    :param phase_angle_degs: Tap phase angles in degrees for h0, l1, l2 and l3.
    :return: None.
    """
    for winding_index in range(4):
        winding: dev.Winding = windings[winding_index]

        current_position: int = current_positions[winding_index]
        neutral_position: int = neutral_positions[winding_index]
        minimum_position: int = minimum_positions[winding_index]
        maximum_position: int = maximum_positions[winding_index]
        step_percent: float = step_percents[winding_index]
        phase_angle_deg: float = phase_angle_degs[winding_index]

        total_positions: int = maximum_position - minimum_position + 1
        if total_positions <= 0:
            pass
        else:
            tc_type: TapChangerTypes = TapChangerTypes.VoltageRegulation
            if abs(phase_angle_deg) > 1e-12:
                tc_type = TapChangerTypes.Symmetrical
                if abs(abs(phase_angle_deg) % 180.0 - 90.0) < 1e-6:
                    tc_type = TapChangerTypes.Asymmetrical
                else:
                    pass
            else:
                pass

            winding.tap_changer.total_positions = total_positions
            winding.tap_changer.neutral_position = max(0, neutral_position - minimum_position)
            winding.tap_changer.dV = step_percent / 100.0
            winding.tap_changer.asymmetry_angle = phase_angle_deg
            winding.tap_changer.tc_type = tc_type

            tap_position: int = current_position - minimum_position
            if tap_position < 0:
                tap_position = 0
            else:
                pass

            if tap_position >= winding.tap_changer.total_positions:
                tap_position = winding.tap_changer.total_positions - 1
            else:
                pass

            winding.tap_changer.tap_position = tap_position

            fallback_tap: float = winding.tap_changer.get_tap_module()
            fallback_tap_min: float = winding.tap_changer.get_tap_module_min()
            fallback_tap_max: float = winding.tap_changer.get_tap_module_max()

            if tc_type == TapChangerTypes.VoltageRegulation:
                step: float = step_percent / 100.0
                tap: float = 1.0 + (current_position - neutral_position) * step
                tap_min: float = 1.0 + (minimum_position - neutral_position) * step
                tap_max: float = 1.0 + (maximum_position - neutral_position) * step

                tap, tap_min, tap_max = _sanitize_tap_window(
                    tap_value=tap,
                    tap_min_value=tap_min,
                    tap_max_value=tap_max,
                    fallback_tap_value=fallback_tap,
                    fallback_tap_min_value=fallback_tap_min,
                    fallback_tap_max_value=fallback_tap_max,
                )

                _apply_branch_tap_state(
                    branch=winding,
                    tap_value=tap,
                    tap_phase=0.0,
                    tap_min_value=tap_min,
                    tap_max_value=tap_max,
                    tap_phase_min=0.0,
                    tap_phase_max=0.0,
                )
            else:
                tap_value: float
                tap_min_value: float
                tap_max_value: float

                tap_value, tap_min_value, tap_max_value = _sanitize_tap_window(
                    tap_value=fallback_tap,
                    tap_min_value=fallback_tap_min,
                    tap_max_value=fallback_tap_max,
                    fallback_tap_value=fallback_tap,
                    fallback_tap_min_value=fallback_tap_min,
                    fallback_tap_max_value=fallback_tap_max,
                )

                _apply_branch_tap_state(
                    branch=winding,
                    tap_value=tap_value,
                    tap_phase=winding.tap_changer.get_tap_phase(),
                    tap_min_value=tap_min_value,
                    tap_max_value=tap_max_value,
                    tap_phase_min=winding.tap_changer.get_tap_phase_min(),
                    tap_phase_max=winding.tap_changer.get_tap_phase_max(),
                )


def convert_dgs_to_transformer(tr2: ElmTr2,
                               buses: List[dev.Bus],
                               stacubic_dict: Dict[str, List[int]],
                               templates_dict: Dict[str, dev.TransformerType],
                               typtr2_dict: Dict[str, TypTr2],
                               freq: float,
                               baseMVA: float,
                               logger: Logger,
                               cubics_by_objid: Dict[str, List[StaCubic]],
                               bus_by_term_id: Dict[str, dev.Bus],
                               switch_by_cubic_id: Dict[str, StaSwitch],
                               phase_map: PhaseMap,
                               parallel_index: int = 0,
                               parallel_count: int = 1) -> dev.Transformer2W:
    """
    Convert dgs to transformer.

    :param tr2: tr2 parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param templates_dict: templates_dict parameter.
    :param typtr2_dict: typtr2_dict parameter.
    :param freq: freq parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param phase_map: Resolved terminal-conductor phase map.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    template = templates_dict.get(tr2.typ_id, None)
    if template is None:
        template = templates_dict.get(_ref_id(tr2.typ_id), None)

    if template is None:
        raise ValueError(f"No template for the transformer {tr2.ID}")

    # Resolve the raw TypTr2 (needed to parse tap settings: step/min/max/neutral)
    typtr2_raw = _resolve_pointer_dict_value(key=tr2.typ_id, mapping=typtr2_dict)
    if typtr2_raw is None:
        raise ValueError(f"No raw TypTr2 data for the transformer {tr2.ID}")
    else:
        pass

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=tr2.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        # Fall back to legacy check only if terminal mapping is not available
        bus_ids = stacubic_dict.get(_ref_id(tr2.ID), None)
        if bus_ids is None:
            raise ValueError(f"No buses for the transformer {tr2.ID}")

        if len(bus_ids) != 2:
            raise ValueError(f"Not exactly 2 buses for the transformer {tr2.ID}")

    bus_from, bus_to = get_branch_buses(elm_id=tr2.ID,
                                        stacubic_dict=stacubic_dict,
                                        buses=buses,
                                        cubics_by_objid=cubics_by_objid,
                                        bus_by_term_id=bus_by_term_id)

    cbs = cubics_by_objid.get(_ref_id(tr2.ID), [])
    has_dgs_from_to = (len(cbs) == 2) and ({int(cb.obj_bus) for cb in cbs} == {0, 1})

    if has_dgs_from_to:
        bus_vg_from, bus_vg_to = bus_from, bus_to
    else:
        bus_vg_from, bus_vg_to = _order_hv_lv(bus_a=bus_from, bus_b=bus_to, logger=logger, tr_name=tr2.loc_name)

    transformer_name = _get_non_empty_name(tr2.loc_name, f"Transformer_{_ref_id(tr2.ID)}")
    transformer_name = _get_parallel_device_name(transformer_name, parallel_index, parallel_count)
    transformer_idtag = _get_parallel_device_idtag(_ref_id(tr2.ID), parallel_index, parallel_count)

    trafo = dev.Transformer2W(bus_from=bus_vg_from,
                              bus_to=bus_vg_to,
                              name=transformer_name,
                              idtag=transformer_idtag,
                              active=not tr2.outserv and _is_element_closed_by_cubicle_switches(element_id=tr2.ID,
                                                                                                cubics_by_objid=cubics_by_objid,
                                                                                                switch_by_cubic_id=switch_by_cubic_id), )

    trafo.apply_template(obj=template, Sbase=baseMVA, logger=logger)
    trafo.vector_group_number = int(round(float(typtr2_raw.nt2ag))) % 12
    trafo.rate = float(trafo.rate) * float(tr2.ratfac)

    #   - TypTr2.dutap   : tap step in percent (%)
    #   - TypTr2.nntap0  : neutral position (integer)
    #   - TypTr2.ntpmn   : minimum position (integer)
    #   - TypTr2.ntpmx   : maximum position (integer)
    #   - TypTr2.tap_side: side where the tap-changer is located (typically 0=HV, 1=LV)
    #   - ElmTr2.nntap   : current position (integer)
    #   - TypTr2.tr2cn_h : high voltage side connection
    #   - TypTr2.tr2cn_l : low voltage side connection

    # From-side is the HV-side
    if bus_vg_from.Vnom > bus_vg_to.Vnom:

        # D-D (or Y-Y) Connection (non-auto transformer)
        if typtr2_raw.tr2cn_h == 'D' and typtr2_raw.tr2cn_l == 'D' and tr2.i_auto == 0 and typtr2_raw.nt2ph == 2:

            if tr2.i_eahv == 1:
                trafo.conn_f = WindingType.GroundedStar
            else:
                trafo.conn_f = WindingType.Delta

            if tr2.i_ealv == 1:
                trafo.conn_t = WindingType.GroundedStar
            else:
                trafo.conn_t = WindingType.Delta

        elif typtr2_raw.tr2cn_h == 'Y' and typtr2_raw.tr2cn_l == 'Y' and tr2.i_auto == 0 and typtr2_raw.nt2ph == 2:

            if tr2.i_eahv == 1:
                trafo.conn_f = WindingType.GroundedStar
            else:
                trafo.conn_f = WindingType.Delta

            if tr2.i_ealv == 1:
                trafo.conn_t = WindingType.GroundedStar
            else:
                trafo.conn_t = WindingType.Delta

    # To-side is the HV-side
    else:

        # D-D (or Y-Y) Connection (non-auto transformer)
        if typtr2_raw.tr2cn_h == 'D' and typtr2_raw.tr2cn_l == 'D' and tr2.i_auto == 0 and typtr2_raw.nt2ph == 2:

            if tr2.i_eahv == 1:
                trafo.conn_t = WindingType.GroundedStar
            else:
                trafo.conn_t = WindingType.Delta

            if tr2.i_ealv == 1:
                trafo.conn_f = WindingType.GroundedStar
            else:
                trafo.conn_f = WindingType.Delta

        elif typtr2_raw.tr2cn_h == 'Y' and typtr2_raw.tr2cn_l == 'Y' and tr2.i_auto == 0 and typtr2_raw.nt2ph == 2:

            if tr2.i_eahv == 1:
                trafo.conn_t = WindingType.GroundedStar
            else:
                trafo.conn_t = WindingType.Delta

            if tr2.i_ealv == 1:
                trafo.conn_f = WindingType.GroundedStar
            else:
                trafo.conn_f = WindingType.Delta

    cubicles = cubics_by_objid.get(_ref_id(tr2.ID), [])
    cubicles = sorted(cubicles, key=_stacubic_obj_bus_sort_key)
    phases = _get_element_phases(
        element_id=tr2.ID,
        cubics_by_objid=cubics_by_objid,
        phase_map=phase_map,
    )

    # Keep the previous direct cPhInfo behaviour when no propagated mapping
    # could be built, for example in incomplete legacy DGS exports.
    if len(phases) == 0 and len(cubicles) > 0:
        phases = sorted({
            _GLOBAL_PHASE_INDEX[name]
            for name in _get_cubic_phase_names(cubicles[0])
            if name in _GLOBAL_PHASE_INDEX
        })

    trafo.phases = np.array(phases, dtype=int)

    if int(typtr2_raw.itapch) != 0 and trafo.tap_changer.total_positions > 0:
        tap_position = int(tr2.nntap) - int(typtr2_raw.ntpmn)
        if tap_position < 0:
            tap_position = 0
        else:
            pass
        if tap_position >= trafo.tap_changer.total_positions:
            tap_position = trafo.tap_changer.total_positions - 1
        else:
            pass

        trafo.tap_changer.tap_position = tap_position

        fallback_tap: float = trafo.tap_changer.get_tap_module()
        fallback_tap_min: float = trafo.tap_changer.get_tap_module_min()
        fallback_tap_max: float = trafo.tap_changer.get_tap_module_max()

        tc_type = _get_transformer_tap_changer_type(typtr2=typtr2_raw)
        if tc_type == TapChangerTypes.VoltageRegulation:
            step: float = float(typtr2_raw.dutap) / 100.0
            neutral_position: int = int(typtr2_raw.nntap0)
            current_position: int = int(tr2.nntap)

            tap: float = 1.0 + (current_position - neutral_position) * step
            tap_min: float = 1.0 + (int(typtr2_raw.ntpmn) - neutral_position) * step
            tap_max: float = 1.0 + (int(typtr2_raw.ntpmx) - neutral_position) * step

            if tap_min > tap_max:
                old_tap_min = tap_min
                tap_min = tap_max
                tap_max = old_tap_min
            else:
                pass

            hv_bus: dev.Bus
            lv_bus: dev.Bus
            if float(bus_vg_from.Vnom) >= float(bus_vg_to.Vnom):
                hv_bus = bus_vg_from
                lv_bus = bus_vg_to
            else:
                hv_bus = bus_vg_to
                lv_bus = bus_vg_from

            if int(typtr2_raw.tap_side) == 0:
                tap_on_bus = hv_bus
            else:
                tap_on_bus = lv_bus

            if tap_on_bus is not bus_vg_from:
                tap = 1.0 / tap
                tap_min_inverted = 1.0 / tap_min
                tap_max_inverted = 1.0 / tap_max
                tap_min = min(tap_min_inverted, tap_max_inverted)
                tap_max = max(tap_min_inverted, tap_max_inverted)
            else:
                pass

            tap, tap_min, tap_max = _sanitize_tap_window(
                tap_value=tap,
                tap_min_value=tap_min,
                tap_max_value=tap_max,
                fallback_tap_value=fallback_tap,
                fallback_tap_min_value=fallback_tap_min,
                fallback_tap_max_value=fallback_tap_max,
            )

            _apply_branch_tap_state(
                branch=trafo,
                tap_value=tap,
                tap_phase=0.0,
                tap_min_value=tap_min,
                tap_max_value=tap_max,
                tap_phase_min=0.0,
                tap_phase_max=0.0,
            )
        else:
            tap_value, tap_min_value, tap_max_value = _sanitize_tap_window(
                tap_value=fallback_tap,
                tap_min_value=fallback_tap_min,
                tap_max_value=fallback_tap_max,
                fallback_tap_value=fallback_tap,
                fallback_tap_min_value=fallback_tap_min,
                fallback_tap_max_value=fallback_tap_max,
            )

            _apply_branch_tap_state(
                branch=trafo,
                tap_value=tap_value,
                tap_phase=trafo.tap_changer.get_tap_phase(),
                tap_min_value=tap_min_value,
                tap_max_value=tap_max_value,
                tap_phase_min=trafo.tap_changer.get_tap_phase_min(),
                tap_phase_max=trafo.tap_changer.get_tap_phase_max(),
            )
    else:
        pass

    if int(tr2.ntrcn) != 0:
        trafo.tap_module_control_mode = TapModuleControl.Vm
        if float(tr2.usetp) > 0.0:
            trafo.vset = float(tr2.usetp)
        else:
            pass
    else:
        pass

    if float(typtr2_raw.uk0tr) > 0.0:
        nominal_power = float(typtr2_raw.strn)
        if nominal_power > 0.0:
            z0_pu = (float(typtr2_raw.uk0tr) / 100.0) * (float(baseMVA) / nominal_power)
            r0_pu = (float(typtr2_raw.ur0tr) / 100.0) * (float(baseMVA) / nominal_power)
            x0_sq = max(0.0, z0_pu * z0_pu - r0_pu * r0_pu)
            trafo.R0 = r0_pu
            trafo.X0 = math.sqrt(x0_sq)
        else:
            pass
    else:
        pass

    trafo.R2 = trafo.R
    trafo.X2 = trafo.X
    # ---------------------------------------------------------------

    trafo.fix_inconsistencies(logger=logger, maximum_difference=0.1)

    return trafo


def _tr3_zero_sequence_impedance(uk0: float, ur0: float, rated_power: float,
                                  base_mva: float) -> complex:
    """Convert a PF pairwise zero-sequence test to the system base.

    :param uk0: Impedance magnitude in percent on the smaller winding rating.
    :param ur0: Resistance in percent on the same base.
    :param rated_power: Smaller winding rating, MVA.
    :param base_mva: Network power base, MVA.
    :return: Pairwise impedance in system p.u.
    """
    if rated_power <= 0.0 or not np.isfinite(uk0) or not np.isfinite(ur0) or uk0 < abs(ur0):
        raise ValueError('Invalid TypTr3 zero-sequence test: check uk0, ur0 and winding ratings')
    else:
        return complex(ur0, np.sqrt(uk0 * uk0 - ur0 * ur0)) * base_mva / (100.0 * rated_power)


def convert_dgs_to_transformer3w(tr3: ElmTr3,
                                 buses: List[dev.Bus],
                                 stacubic_dict: Dict[str, List[int]],
                                 templates_dict: Dict[str, TypTr3],
                                 baseMVA: float,
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 switch_by_cubic_id: Dict[str, StaSwitch],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1) -> dev.Transformer3W:
    """
    Convert dgs to transformer3w.

    :param tr3: tr3 parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param templates_dict: templates_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    template = _resolve_pointer_dict_value(key=tr3.typ_id, mapping=templates_dict)
    if template is None:
        raise ValueError(f"No TypTr3 data for transformer {tr3.ID}")
    else:
        pass

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=tr3.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 3:
        bus_a = bus_by_term_id[term_ids[0]]
        bus_b = bus_by_term_id[term_ids[1]]
        bus_c = bus_by_term_id[term_ids[2]]
    else:
        bus_ids = stacubic_dict[_ref_id(tr3.ID)]
        bus_a = buses[bus_ids[0]]
        bus_b = buses[bus_ids[1]]
        bus_c = buses[bus_ids[2]]

    bus_hv, bus_mv, bus_lv = _order_hv_mv_lv(bus_a=bus_a,
                                             bus_b=bus_b,
                                             bus_c=bus_c,
                                             logger=logger,
                                             tr_name=tr3.loc_name)

    # Graphic position not working right now
    x = (float(bus_hv.x) + float(bus_mv.x) + float(bus_lv.x)) / 3.0
    y = (float(bus_hv.y) + float(bus_mv.y) + float(bus_lv.y)) / 3.0

    transformer_name = _get_non_empty_name(tr3.loc_name, f"Transformer3W_{_ref_id(tr3.ID)}")
    transformer_name = _get_parallel_device_name(transformer_name, parallel_index, parallel_count)
    transformer_idtag = _get_parallel_device_idtag(_ref_id(tr3.ID), parallel_index, parallel_count)

    trafo3w = dev.Transformer3W(name=transformer_name,
                                idtag=transformer_idtag,
                                bus1=bus_hv,
                                bus2=bus_mv,
                                bus3=bus_lv,
                                active=not tr3.outserv,
                                x=x,
                                y=y)

    trafo3w.fill_from_design_values(
        V1=float(template.utrn3_h),
        V2=float(template.utrn3_m),
        V3=float(template.utrn3_l),
        Sn1=float(template.strn3_h),
        Sn2=float(template.strn3_m),
        Sn3=float(template.strn3_l),
        Pcu12=float(template.pcut3_h),
        Pcu23=float(template.pcut3_m),
        Pcu31=float(template.pcut3_l),
        Vsc12=float(template.uktr3_h),
        Vsc23=float(template.uktr3_m),
        Vsc31=float(template.uktr3_l),
        Pfe=float(template.pfe),
        I0=float(template.curm3),
        Sbase=float(baseMVA),
    )

    # Reuse the validated pairwise-to-star conversion, retaining independent Z0.
    trafo3w.fill_zero_sequence(
        z12=_tr3_zero_sequence_impedance(template.uk0hm, template.ur0hm,
                                         min(template.strn3_h, template.strn3_m), baseMVA),
        z23=_tr3_zero_sequence_impedance(template.uk0ml, template.ur0ml,
                                         min(template.strn3_m, template.strn3_l), baseMVA),
        z31=_tr3_zero_sequence_impedance(template.uk0hl, template.ur0hl,
                                         min(template.strn3_l, template.strn3_h), baseMVA))

    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding1,
        current_position=int(tr3.n3tap_h),
        neutral_position=int(template.n3tp0_h),
        minimum_position=int(template.n3tmn_h),
        maximum_position=int(template.n3tmx_h),
        step_percent=float(template.du3tp_h),
        phase_angle_deg=float(template.ph3tr_h)
    )
    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding2,
        current_position=int(tr3.n3tap_m),
        neutral_position=int(template.n3tp0_m),
        minimum_position=int(template.n3tmn_m),
        maximum_position=int(template.n3tmx_m),
        step_percent=float(template.du3tp_m),
        phase_angle_deg=float(template.ph3tr_m)
    )
    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding3,
        current_position=int(tr3.n3tap_l),
        neutral_position=int(template.n3tp0_l),
        minimum_position=int(template.n3tmn_l),
        maximum_position=int(template.n3tmx_l),
        step_percent=float(template.du3tp_l),
        phase_angle_deg=float(template.ph3tr_l)
    )

    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding1,
        pf_connection_code=str(template.tr3cn_h),
        pf_vector_group_angle=float(template.nt3ag_h)
    )
    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding2,
        pf_connection_code=str(template.tr3cn_m),
        pf_vector_group_angle=float(template.nt3ag_m)
    )
    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding3,
        pf_connection_code=str(template.tr3cn_l),
        pf_vector_group_angle=float(template.nt3ag_l)
    )

    hv_closed, mv_closed, lv_closed = _get_tr3_winding_closed_states(
        tr3_id=tr3.ID,
        cubics_by_objid=cubics_by_objid,
        switch_by_cubic_id=switch_by_cubic_id,
        bus_by_term_id=bus_by_term_id,
        bus_hv=bus_hv,
        bus_mv=bus_mv,
        bus_lv=bus_lv,
    )
    trafo3w.winding1.active = hv_closed
    trafo3w.winding2.active = mv_closed
    trafo3w.winding3.active = lv_closed

    return trafo3w


def convert_dgs_to_transformer4w(tr4: ElmTr4,
                                 buses: List[dev.Bus],
                                 stacubic_dict: Dict[str, List[int]],
                                 templates_dict: Dict[str, TypTr4],
                                 baseMVA: float,
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 switch_by_cubic_id: Dict[str, StaSwitch],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1) -> dev.TransformerNW:
    """
    Convert dgs to transformer4w.

    :param tr4: tr4 parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param templates_dict: templates_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    template = _resolve_pointer_dict_value(key=tr4.typ_id, mapping=templates_dict)
    if template is None:
        raise ValueError(f"No TypTr4 data for transformer {tr4.ID}")
    else:
        pass

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=tr4.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 4:
        bus_a = bus_by_term_id[term_ids[0]]
        bus_b = bus_by_term_id[term_ids[1]]
        bus_c = bus_by_term_id[term_ids[2]]
        bus_d = bus_by_term_id[term_ids[3]]
    else:
        bus_ids = stacubic_dict[_ref_id(tr4.ID)]
        bus_a = buses[bus_ids[0]]
        bus_b = buses[bus_ids[1]]
        bus_c = buses[bus_ids[2]]
        bus_d = buses[bus_ids[3]]

    # bus_hv, bus_lv1, bus_lv2, bus_lv3, ordered_original_indices = _order_tr4(bus_a=bus_a, bus_b=bus_b, bus_c=bus_c, bus_d=bus_d, logger=logger, tr_name=tr4.loc_name)

    cubic_by_id: Dict[str, StaCubic] = dict()
    for cubic in cubics_by_objid.get(_ref_id(tr4.ID), list()):
        cubic_id: str | None = _ref_id(cubic.ID)
        if cubic_id is not None and cubic_id != "":
            cubic_by_id[cubic_id] = cubic
        else:
            pass

    cubic_hv: StaCubic | None = _resolve_pointer_dict_value(key=tr4.bush0, mapping=cubic_by_id)
    cubic_lv1: StaCubic | None = _resolve_pointer_dict_value(key=tr4.busl1, mapping=cubic_by_id)
    cubic_lv2: StaCubic | None = _resolve_pointer_dict_value(key=tr4.busl2, mapping=cubic_by_id)
    cubic_lv3: StaCubic | None = _resolve_pointer_dict_value(key=tr4.busl3, mapping=cubic_by_id)

    if cubic_hv is None or cubic_lv1 is None or cubic_lv2 is None or cubic_lv3 is None:
        raise ValueError(f"Missing one or more ElmTr4 side cubicles for transformer {tr4.ID}")
    else:
        pass

    term_hv: str | None = _ref_id(cubic_hv.fold_id)
    term_lv1: str | None = _ref_id(cubic_lv1.fold_id)
    term_lv2: str | None = _ref_id(cubic_lv2.fold_id)
    term_lv3: str | None = _ref_id(cubic_lv3.fold_id)

    if term_hv is None or term_lv1 is None or term_lv2 is None or term_lv3 is None:
        raise ValueError(f"Missing one or more ElmTr4 side terminals for transformer {tr4.ID}")
    else:
        pass

    bus_hv: dev.Bus = bus_by_term_id[term_hv]
    bus_lv1: dev.Bus = bus_by_term_id[term_lv1]
    bus_lv2: dev.Bus = bus_by_term_id[term_lv2]
    bus_lv3: dev.Bus = bus_by_term_id[term_lv3]

    # Graphic position not working right now
    x = (float(bus_hv.x) + float(bus_lv1.x) + float(bus_lv2.x) + float(bus_lv3.x)) / 4.0
    y = (float(bus_hv.y) + float(bus_lv1.y) + float(bus_lv2.y) + float(bus_lv3.y)) / 4.0

    transformer_name = _get_non_empty_name(tr4.loc_name, f"Transformer4W_{_ref_id(tr4.ID)}")
    transformer_name = _get_parallel_device_name(transformer_name, parallel_index, parallel_count)
    transformer_idtag = _get_parallel_device_idtag(_ref_id(tr4.ID), parallel_index, parallel_count)

    trafo4w = dev.TransformerNW(
        idtag=transformer_idtag,
        code=_ref_id(tr4.ID) or "",
        name=transformer_name,
        bus0=None,
        winding_count=4,
        buses=[
            bus_hv,
            bus_lv1,
            bus_lv2,
            bus_lv3,
        ],
        active=(int(tr4.outserv) == 0),
        Pfe=float(template.pfe),
        I0=float(template.curmag),
        x=x,
        y=y,
    )

    if template.inputData == 0:
        _fill_tr4w_complete_values(
            trafo4w=trafo4w,
            V_h0=template.un_h0,
            V_l1=template.un_l1,
            V_l2=template.un_l2,
            V_l3=template.un_l3,

            Sn_h0=template.sn_h0,
            Sn_l1=template.sn_l1,
            Sn_l2=template.sn_l2,
            Sn_l3=template.sn_l3,

            Vsc_h0l1=template.uk_h0l1,
            Vsc_h0l2=template.uk_h0l2,
            Vsc_h0l3=template.uk_h0l3,
            Vsc_l1l2=template.uk_l1l2,
            Vsc_l1l3=template.uk_l1l3,
            Vsc_l2l3=template.uk_l2l3,

            Pcu_h0l1=template.pcu_h0l1,
            Pcu_h0l2=template.pcu_h0l2,
            Pcu_h0l3=template.pcu_h0l3,
            Pcu_l1l2=template.pcu_l1l2,
            Pcu_l1l3=template.pcu_l1l3,
            Pcu_l2l3=template.pcu_l2l3,

            Pfe=template.pfe,
            I0=template.curmag,
            Sbase=baseMVA,
        )
    else:
        _fill_tr4w_simple_values(
            trafo4w=trafo4w,
            nominal_voltages=(
                template.un_h0,
                template.un_l1,
                template.un_l2,
                template.un_l3,
            ),
            nominal_powers=(
                template.sn_h0,
                template.sn_l1,
                template.sn_l2,
                template.sn_l3,
            ),
            short_circuit_voltages=(
                template.uk_h0,
                template.uk_l1,
                template.uk_l2,
                template.uk_l3,
            ),
            copper_losses=(
                template.pcu_h0,
                template.pcu_l1,
                template.pcu_l2,
                template.pcu_l3,
            ),
            Pfe=template.pfe,
            I0=template.curmag,
            Sbase=baseMVA,
        )

    return trafo4w

    _apply_tr4_winding_tap_data(
        windings=trafo4w.windings,
        current_positions=(
            tr4.ntap_h0,
            tr4.ntap_l1,
            tr4.ntap_l2,
            tr4.ntap_l3,
        ),
        neutral_positions=(
            template.ntapneu_h0,
            template.ntapneu_l1,
            template.ntapneu_l2,
            template.ntapneu_l3,
        ),
        minimum_positions=(
            template.ntapmin_h0,
            template.ntapmin_l1,
            template.ntapmin_l2,
            template.ntapmin_l3,
        ),
        maximum_positions=(
            template.ntapmax_h0,
            template.ntapmax_l1,
            template.ntapmax_l2,
            template.ntapmax_l3,
        ),
        step_percents=(
            template.dutap_h0,
            template.dutap_l1,
            template.dutap_l2,
            template.dutap_l3,
        ),
        phase_angle_degs=(
            template.phitr_h0,
            template.phitr_l1,
            template.phitr_l2,
            template.phitr_l3,
        ),
    )

    return trafo4w

    trafoNw.fill_from_design_values(
        V1=float(template.utrn3_h),
        V2=float(template.utrn3_m),
        V3=float(template.utrn3_l),
        Sn1=float(template.strn3_h),
        Sn2=float(template.strn3_m),
        Sn3=float(template.strn3_l),
        Pcu12=float(template.pcut3_h),
        Pcu23=float(template.pcut3_m),
        Pcu31=float(template.pcut3_l),
        Vsc12=float(template.uktr3_h),
        Vsc23=float(template.uktr3_m),
        Vsc31=float(template.uktr3_l),
        Pfe=float(template.pfe),
        I0=float(template.curm3),
        Sbase=float(baseMVA),
    )

    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding1,
        current_position=int(tr3.n3tap_h),
        neutral_position=int(template.n3tp0_h),
        minimum_position=int(template.n3tmn_h),
        maximum_position=int(template.n3tmx_h),
        step_percent=float(template.du3tp_h),
        phase_angle_deg=float(template.ph3tr_h)
    )
    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding2,
        current_position=int(tr3.n3tap_m),
        neutral_position=int(template.n3tp0_m),
        minimum_position=int(template.n3tmn_m),
        maximum_position=int(template.n3tmx_m),
        step_percent=float(template.du3tp_m),
        phase_angle_deg=float(template.ph3tr_m)
    )
    _apply_tr3_winding_tap_data(
        winding=trafo3w.winding3,
        current_position=int(tr3.n3tap_l),
        neutral_position=int(template.n3tp0_l),
        minimum_position=int(template.n3tmn_l),
        maximum_position=int(template.n3tmx_l),
        step_percent=float(template.du3tp_l),
        phase_angle_deg=float(template.ph3tr_l)
    )

    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding1,
        pf_connection_code=str(template.tr3cn_h),
        pf_vector_group_angle=float(template.nt3ag_h)
    )
    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding2,
        pf_connection_code=str(template.tr3cn_m),
        pf_vector_group_angle=float(template.nt3ag_m)
    )
    _apply_tr3_winding_connection_data(
        winding=trafo3w.winding3,
        pf_connection_code=str(template.tr3cn_l),
        pf_vector_group_angle=float(template.nt3ag_l)
    )

    hv_closed, mv_closed, lv_closed = _get_tr3_winding_closed_states(
        tr3_id=tr3.ID,
        cubics_by_objid=cubics_by_objid,
        switch_by_cubic_id=switch_by_cubic_id,
        bus_by_term_id=bus_by_term_id,
        bus_hv=bus_hv,
        bus_mv=bus_mv,
        bus_lv=bus_lv,
    )
    trafo3w.winding1.active = hv_closed
    trafo3w.winding2.active = mv_closed
    trafo3w.winding3.active = lv_closed

    return trafo3w


def build_switch_by_cubic_id(staswitchs: List[StaSwitch]) -> Dict[str, StaSwitch]:
    """
    Build switch by cubic id.

    :param staswitchs: staswitchs parameter.
    :return: Function result.
    """
    d: Dict[str, StaSwitch] = dict()
    for sw in staswitchs:
        cubic_id: str | None = _ref_id(sw.fold_id)
        if cubic_id is None or cubic_id == "":
            continue
        d[cubic_id] = sw
    return d


def convert_dgs_to_switches_from_elmcoup(elmcoups: List[ElmCoup],
                                         cubics_by_objid: Dict[str, List[StaCubic]],
                                         bus_by_term_id: Dict[str, dev.Bus],
                                         switch_by_cubic_id: Dict[str, StaSwitch],
                                         typ_switch_by_id: Dict[str, TypSwitch],
                                         sbase_mva: float,
                                         logger: Logger) -> List[dev.Switch]:
    """
    Convert dgs to switches from elmcoup.

    :param elmcoups: elmcoups parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param typ_switch_by_id: typ_switch_by_id parameter.
    :param sbase_mva: sbase_mva parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    switches: List[dev.Switch] = list()

    for coup in elmcoups:
        coup_id: str | None = _ref_id(coup.ID)
        if coup_id is None or coup_id == "":
            continue

        # Resolve connectivity
        term_ids_raw: List[str] = get_terminal_ids(element_id=coup_id, cubics_by_objid=cubics_by_objid)

        # Deduplicate terminals while preserving order
        term_ids: List[str] = list()
        for tid in term_ids_raw:
            if tid not in term_ids:
                term_ids.append(tid)

        if len(term_ids) != 2:
            logger.add_warning(
                f"Not exactly 2 terminals.",
                device=coup.ID,
                device_class="ElmCoup",
                value=str(len(term_ids)),
                expected_value="2"
            )
            continue

        bus_from: dev.Bus = bus_by_term_id[term_ids[0]]
        bus_to: dev.Bus = bus_by_term_id[term_ids[1]]

        # Skip degenerate cases
        if bus_from is bus_to:
            logger.add_warning(
                f"Both ends connect to the same bus.",
                device=coup.ID,
                device_class="ElmCoup"
            )
            continue

        # ElmCoup.on_off is the authoritative electrical state
        is_closed: bool = (int(coup.on_off) != 0)

        # Validation using StaSwitch on each cubicle
        # (StaSwitch.on_off may represent a cubicle-end representation, not the physical device state)
        cubics: List[StaCubic] = cubics_by_objid.get(coup_id, list())
        for cb in cubics:
            cb_id: str | None = _ref_id(cb.ID)
            if cb_id is None or cb_id == "":
                continue

            stasw: StaSwitch | None = switch_by_cubic_id.get(cb_id, None)
            if stasw is None:
                continue

            stasw_closed: bool = (int(stasw.on_off) != 0)
            if stasw_closed != is_closed:
                logger.add_warning(
                    f"state differs from StaSwitch. Using ElmCoup.on_off as truth.",
                    device=coup.ID,
                    device_class="ElmCoup",
                    value=int(coup.on_off),
                    expected_value=int(stasw.on_off)
                )

        graphic_type: SwitchGraphicType = _convert_pf_switch_graphic_type(iuse=0, ausage=coup.aUsage)
        typ_switch = _resolve_pointer_dict_value(key=coup.typ_id, mapping=typ_switch_by_id)
        rated_current = 0.0
        switch_r = 1e-20
        switch_x = 1e-20

        if typ_switch is not None:
            rated_current = max(float(typ_switch.InomA), float(typ_switch.InomB))
            bus_vnom = max(float(bus_from.Vnom), float(bus_to.Vnom))
            switch_r, switch_x = _get_switch_impedance_in_pu(
                r_ohm=float(typ_switch.Ron),
                x_ohm=float(typ_switch.Xon),
                vnom_kv=bus_vnom,
                sbase_mva=sbase_mva
            )
        else:
            pass

        sw = dev.Switch(
            bus_from=bus_from,
            bus_to=bus_to,
            name=coup.loc_name or f"ElmCoup_{coup_id}",
            idtag=coup_id,
            code=coup.typ_id,
            r=switch_r,
            x=switch_x,
            active=is_closed,
            normal_open=not is_closed,
            retained=False,
            rated_current=rated_current,
            graphic_type=graphic_type
        )

        switches.append(sw)

    return switches


def _convert_pf_switch_graphic_type(iuse: int, ausage: str) -> SwitchGraphicType:
    """
    Convert pf switch graphic type.

    :param iuse: iuse parameter.
    :param ausage: ausage parameter.
    :return: Function result.
    """
    usage = str(ausage).strip().upper()

    usage_to_member: Dict[str, str] = {
        "CB": "CircuitBreaker",
        "BREAKER": "CircuitBreaker",
        "CBK": "CircuitBreaker",
        "DIS": "Disconnector",
        "DISCONNECTOR": "Disconnector",
        "LBS": "LoadBreakSwitch",
        "LOADBREAKSWITCH": "LoadBreakSwitch",
        "FUSE": "Fuse",
    }

    member_name = usage_to_member.get(usage, None)
    if member_name is not None and member_name in SwitchGraphicType.__members__:
        return SwitchGraphicType.__members__[member_name]

    iuse_to_member: Dict[int, str] = {
        0: "CircuitBreaker",
        1: "Disconnector",
        2: "LoadBreakSwitch",
        3: "Fuse",
    }

    member_name = iuse_to_member.get(int(iuse), "CircuitBreaker")
    if member_name in SwitchGraphicType.__members__:
        return SwitchGraphicType.__members__[member_name]

    return SwitchGraphicType.CircuitBreaker


def convert_dgs_to_switch(stasw: StaSwitch,
                          buses: List[dev.Bus],
                          stacubic_dict: Dict[str, List[int]],
                          logger: Logger,
                          cubics_by_objid: Dict[str, List[StaCubic]],
                          bus_by_term_id: Dict[str, dev.Bus]) -> dev.Switch | None:
    """
    Convert dgs to switch.

    :param stasw: stasw parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    term_ids: List[str] = get_terminal_ids(element_id=stasw.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        logger.add_warning(
            f"not connected to exactly 2 terminals.",
            device=f"'{stasw.loc_name}' (ID={stasw.ID})",
            device_class="StaSwitch",
        )
        return None

    bus_from = bus_by_term_id[term_ids[0]]
    bus_to = bus_by_term_id[term_ids[1]]

    # PowerFactory/DGS state: on_off (int)
    # We interpret on_off != 0 as "closed/connected" (active switch).
    is_closed: bool = (int(stasw.on_off) != 0)
    normal_open: bool = not is_closed

    graphic_type: SwitchGraphicType = _convert_pf_switch_graphic_type(iuse=stasw.iUse,
                                                                      ausage=stasw.aUsage)

    sw = dev.Switch(bus_from=bus_from,
                    bus_to=bus_to,
                    name=stasw.loc_name,
                    idtag=stasw.ID,
                    code=stasw.typ_id,
                    active=is_closed,
                    normal_open=normal_open,
                    retained=False,
                    rated_current=0.0,
                    graphic_type=graphic_type)

    return sw


def convert_dgs_to_line(
        lne: ElmLne,
        buses: List[dev.Bus],
        stacubic_dict: Dict[str, List[int]],
        sequence_templates_dict: Dict[str, dev.SequenceLineType],
        dc_cable_type_dict: Dict[str, dev.UndergroundLineType],
        source_line_type_dict: Dict[str, TypLne],
        overhead_line_type_dict: Dict[str, dev.OverheadLineType],
        underground_line_type_dict: Dict[str, dev.UndergroundLineType],
        line_type_by_line_id: Dict[str, str],
        line_sections_by_line_id: Dict[str, List[ElmLnesec]],
        tower_template_by_line_id: Dict[str, dev.OverheadLineType],
        freq: float,
        baseMVA: float,
        logger: Logger,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        phase_map: PhaseMap,
        parallel_index: int = 0,
        parallel_count: int = 1
) -> dev.Line | dev.DcLine:
    """
    Convert dgs to line.

    :param lne: lne parameter.
    :param buses: buses parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param sequence_templates_dict: sequence_templates_dict parameter.
    :param dc_cable_type_dict: Complete physical DC cable templates by source pointer.
    :param source_line_type_dict: Parsed line types used for resistive fallback.
    :param overhead_line_type_dict: overhead_line_type_dict parameter.
    :param underground_line_type_dict: Physical cable systems by source pointer.
    :param line_type_by_line_id: line_type_by_line_id parameter.
    :param line_sections_by_line_id: line_sections_by_line_id parameter.
    :param tower_template_by_line_id: tower_template_by_line_id parameter.
    :param freq: freq parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """

    # ------------------------------------------------------------
    # Connectivity via StaCubic.fold_id -> ElmTerm.ID (preferred)
    # ------------------------------------------------------------
    term_ids = get_terminal_ids(element_id=lne.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        ref = _ref_id(lne.ID)
        if ref is not None:
            bus_ids = stacubic_dict.get(ref, None)
            if bus_ids is None:
                raise ValueError(f"No buses for the line {lne.ID}")
            if len(bus_ids) != 2:
                raise ValueError(f"Not exactly 2 buses for the line {lne.ID}")
        else:
            pass

    bus_from, bus_to = get_branch_buses(
        elm_id=lne.ID,
        stacubic_dict=stacubic_dict,
        buses=buses,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id
    )

    line_name = _get_non_empty_name(lne.loc_name, f"Line_{_ref_id(lne.ID)}")
    line_name = _get_parallel_device_name(line_name, parallel_index, parallel_count)
    line_idtag = _get_parallel_device_idtag(_ref_id(lne.ID), parallel_index, parallel_count)

    line_key = _ref_id(lne.ID)
    if line_key is None or line_key == "":
        line_key = str(lne.ID)
    else:
        pass
    owned_sections = line_sections_by_line_id.get(line_key, list())
    line_length: float = float(lne.dline)
    if len(owned_sections) > 0:
        sections_length: float = 0.0
        section: ElmLnesec
        for section in owned_sections:
            sections_length += float(section.dline)
        if sections_length > 0.0:
            line_length = sections_length
        else:
            pass
    else:
        pass

    # ------------------------------------------------------------
    # Apply the resolved template
    # ------------------------------------------------------------

    # ------------------------------------------------------------
    # Resolve typ_id (some PF exports store the type in ElmLnesec instead of ElmLne).
    # If the line is part of an ElmTow (tower coupling), it may legitimately have no typ_id.
    # In that case, we defer the template to the tower mapping.
    # ------------------------------------------------------------
    typ_id: str | None = lne.typ_id
    if typ_id is None or typ_id == "":
        # Try raw line ID and normalized pointer ID
        typ_id = line_type_by_line_id.get(lne.ID, None)
        if typ_id is None or typ_id == "":
            lid = _ref_id(lne.ID)
            if lid is not None and lid != "":
                typ_id = line_type_by_line_id.get(lid, None)

    is_dc_cable: bool = bus_from.is_dc and bus_to.is_dc
    if is_dc_cable:
        dc_line: dev.DcLine = dev.DcLine(
            bus_from=bus_from,
            bus_to=bus_to,
            name=line_name,
            idtag=line_idtag,
            active=not lne.outserv,
            length=line_length,
        )
        cable_type: dev.UndergroundLineType | None = None
        if len(owned_sections) > 0:
            first_section: ElmLnesec = owned_sections[0]
            first_type: dev.UndergroundLineType | None = _resolve_pointer_dict_value(
                key=first_section.typ_id,
                mapping=dc_cable_type_dict,
            )
            same_type: bool = first_type is not None
            section: ElmLnesec
            for section in owned_sections:
                section_type: dev.UndergroundLineType | None = _resolve_pointer_dict_value(
                    key=section.typ_id,
                    mapping=dc_cable_type_dict,
                )
                if section_type is first_type:
                    pass
                else:
                    same_type = False
            if same_type:
                cable_type = first_type
            else:
                # One DcLine can own one reusable cable type. Mixed or
                # incomplete source sections therefore retain only resistance
                # instead of fabricating an equivalent catalogue asset.
                cable_type = None
        else:
            cable_type = _resolve_pointer_dict_value(
                key=typ_id,
                mapping=dc_cable_type_dict,
            )

        if cable_type is not None:
            dc_line.apply_template(
                obj=cable_type,
                Sbase=baseMVA,
                logger=logger,
            )
        else:
            line_voltage: float = dc_line.get_max_bus_nominal_voltage()
            resistance_pu: float | None
            if len(owned_sections) > 0:
                resistance_pu = _get_dc_sections_resistance_pu(
                    sections=owned_sections,
                    source_line_type_dict=source_line_type_dict,
                    line_voltage=line_voltage,
                    base_mva=baseMVA,
                )
            else:
                source_type: TypLne | None = _resolve_pointer_dict_value(
                    key=typ_id,
                    mapping=source_line_type_dict,
                )
                if source_type is not None:
                    resistance_pu = _get_dc_resistance_pu(
                        source_type=source_type,
                        length=line_length,
                        line_voltage=line_voltage,
                        base_mva=baseMVA,
                    )
                else:
                    resistance_pu = None

            if resistance_pu is not None:
                dc_line.R = resistance_pu
            else:
                logger.add_warning(
                    msg='DC line resistance could not be derived from its source type',
                    device=dc_line.name,
                    device_class='ElmLne',
                )

        return dc_line
    else:
        pass

    line = dev.Line(
        bus_from=bus_from,
        bus_to=bus_to,
        name=line_name,
        idtag=line_idtag,
        active=not lne.outserv,
        length=line_length,
    )

    # Tower-derived template (ElmTow -> TypTow). This is used only when typ_id is missing.
    tower_template: dev.OverheadLineType | None = None
    if typ_id is None or typ_id == "":
        tower_template = tower_template_by_line_id.get(lne.ID, None)
        if tower_template is None:
            lid = _ref_id(lne.ID)
            if lid is not None and lid != "":
                tower_template = tower_template_by_line_id.get(lid, None)

    # ------------------------------------------------------------
    # Resolve the line template (TypLne or TypTow)
    # ------------------------------------------------------------
    seq_template: dev.SequenceLineType | None = None
    ohl_template: dev.OverheadLineType | None = None
    underground_template: dev.UndergroundLineType | None = None

    ohl_template = overhead_line_type_dict.get(lne.ID, None)
    if ohl_template is None:
        line_id = _ref_id(lne.ID)
        if line_id is not None:
            ohl_template = overhead_line_type_dict.get(line_id, None)

    if ohl_template is None and typ_id is not None and typ_id != "":
        underground_template = _resolve_pointer_dict_value(
            key=typ_id,
            mapping=underground_line_type_dict,
        )
        seq_template = sequence_templates_dict.get(typ_id, None)
        if seq_template is None:
            tid = _ref_id(typ_id)
            if tid is not None and tid != "":
                seq_template = sequence_templates_dict.get(tid, None)

        if seq_template is None:
            ohl_template = overhead_line_type_dict.get(typ_id, None)
            if ohl_template is None:
                tid = _ref_id(typ_id)
                if tid is not None and tid != "":
                    ohl_template = overhead_line_type_dict.get(tid, None)
    elif ohl_template is None:
        # typ_id is missing: rely on tower coupling template
        ohl_template = tower_template

    applied_template = False
    if len(owned_sections) > 0:
        section_r = 0.0
        section_x = 0.0
        section_b = 0.0
        section_r0 = 0.0
        section_x0 = 0.0
        section_b0 = 0.0
        section_rate: float | None = None
        section_template_found = False
        section_templates_complete: bool = True
        bus_vnom = line.get_max_bus_nominal_voltage()

        ordered_sections = sorted(owned_sections, key=_line_section_index_sort_key)
        for section in ordered_sections:
            seq_section_template = _resolve_pointer_dict_value(key=section.typ_id, mapping=sequence_templates_dict)
            ohl_section_template = _resolve_pointer_dict_value(key=section.typ_id, mapping=overhead_line_type_dict)

            if seq_section_template is not None:
                section_template_found = True
                # Sequence conversion includes G/G0; preserve the existing section
                # aggregation of series, charging and rating at their new positions.
                sequence_values: Tuple[float, float, float, float, float, float, float, float, float] = seq_section_template.get_values(
                    Sbase=baseMVA,
                    freq=freq,
                    length=float(section.dline),
                    line_Vnom=bus_vnom,
                    decimals_rounding=16  # basically not rounding
                )
                section_r += sequence_values[0]
                section_x += sequence_values[1]
                section_b += sequence_values[2]
                section_r0 += sequence_values[4]
                section_x0 += sequence_values[5]
                section_b0 += sequence_values[6]
                current_rate = sequence_values[8]
            elif ohl_section_template is not None:
                if not ohl_section_template.is_computed():
                    ohl_section_template.compute()
                else:
                    pass
                section_template_found = True
                if not ohl_section_template.has_sequence_data():
                    section_templates_complete = False
                else:
                    pass
                values = ohl_section_template.get_values(
                    Sbase=baseMVA,
                    length=float(section.dline),
                    circuit_index=1,
                    Vnom=bus_vnom
                )
                section_r += float(values[0])
                section_x += float(values[1])
                section_b += float(values[2])
                section_r0 += float(values[3])
                section_x0 += float(values[4])
                section_b0 += float(values[5])
                current_rate = float(values[6])
            else:
                section_templates_complete = False
                current_rate = 0.0
                logger.add_warning(
                    "Line section type not found.",
                    device=section.loc_name,
                    device_class="ElmLnesec",
                    value=str(section.typ_id)
                )

            current_rate = current_rate * float(section.fline)
            if section_rate is None:
                section_rate = current_rate
            else:
                if current_rate > 0.0:
                    section_rate = min(section_rate, current_rate)
                else:
                    pass

        if section_template_found:
            line.R = section_r
            line.X = section_x
            line.B = section_b
            line.R0 = section_r0
            line.X0 = section_x0
            line.B0 = section_b0
            if section_rate is not None:
                line.rate = section_rate
            else:
                pass
            applied_template = True
        else:
            applied_template = False
    elif seq_template is not None:
        # Preserve the declarative series values on the canonical Line for every simulation domain.
        line.apply_template(
            obj=seq_template,
            Sbase=baseMVA,
            freq=freq,
            logger=logger,
            decimals_rounding=16,
        )
        applied_template = True
    elif ohl_template is not None:
        # OverheadLineType uses a 1-based circuit index. Default to circuit 1 here.
        line.set_circuit_idx(val=1, obj=ohl_template)
        line.apply_template(obj=ohl_template, Sbase=baseMVA, freq=freq, logger=logger)
        applied_template = True
    elif underground_template is not None:
        # TypCabsys uses the same one-based circuit convention as TypTow.
        line.set_circuit_idx(val=1, obj=underground_template)
        line.apply_template(obj=underground_template, Sbase=baseMVA, freq=freq, logger=logger)
        applied_template = True
    else:
        pass

    if applied_template:
        line.rate = float(line.rate) * float(lne.fline)
    else:
        pass

    phases = _get_element_phases(
        element_id=lne.ID,
        cubics_by_objid=cubics_by_objid,
        phase_map=phase_map,
    )
    if len(phases) > 0:
        active_phases = set(phases)
        for admittance in (line.ys, line.ysh):
            admittance.phN = 0 in active_phases
            admittance.phA = 1 in active_phases
            admittance.phB = 2 in active_phases
            admittance.phC = 3 in active_phases

    # Physical line templates own phase matrices that remain authoritative even
    # when a single- or two-phase system has no sequence-scalar representation.
    is_physical_line: bool = isinstance(
        line.template,
        (dev.OverheadLineType, dev.UndergroundLineType),
    )

    # Preserve historical reduction only for scalar-defined ideal AC links.
    is_ac_topological_link: bool = (
            not is_physical_line
            and np.round(float(line.R), decimals=6) == 0.0
            and np.round(float(line.X), decimals=6) == 0.0
    )
    if is_ac_topological_link:
        line.reducible = True
    else:
        pass

    return line


def convert_dgs_common_impedance_to_series_reactance(
        element: ElmZpu,
        buses: List[dev.Bus],
        bus_by_terminal_id: Dict[str, dev.Bus],
        stacubic_dict: Dict[str, List[int]],
        cubics_by_obj_id: Dict[str, List[StaCubic]],
        logger: Logger,
        Sbase_vg: float
) -> dev.SeriesReactance:
    """
    Convert dgs common impedance to series reactance.

    :param element: element parameter.
    :param buses: buses parameter.
    :param bus_by_terminal_id: bus_by_terminal_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_obj_id: cubics_by_obj_id parameter.
    :param logger: logger parameter.
    :param Sbase_vg: Sbase_vg parameter.
    :return: Function result.
    """

    # Resolve buses via StaCubic.fold_id -> ElmTerm.ID -> Bus (same approach as lines/transformers)
    term_ids: List[str] = get_terminal_ids(element_id=element.ID, cubics_by_objid=cubics_by_obj_id)
    if len(term_ids) != 2:
        raise ValueError(
            f"ElmZpu '{element.loc_name}' (ID={element.ID}) is not connected to exactly 2 terminals.")

    bus_from, bus_to = get_branch_buses(
        elm_id=element.ID,
        stacubic_dict=stacubic_dict,
        buses=buses,
        cubics_by_objid=cubics_by_obj_id,
        bus_by_term_id=bus_by_terminal_id
    )

    name: str = element.loc_name

    r1 = element.r_pu * Sbase_vg / element.Sn
    x1 = element.x_pu * Sbase_vg / element.Sn

    sr = dev.SeriesReactance(
        bus_from=bus_from,
        bus_to=bus_to,
        name=name,
        idtag=_ref_id(element.ID),
        active=not element.outserv,
        r=r1,
        x=x1,
        rate=element.Sn
    )

    # Reuse SeriesReactance's ABC sequence stamp; old exports retain its Z1 fallback.
    if element.iequalz == 0:
        logger.add_warning('Common impedance has unequal i-j/j-i data; SeriesReactance uses i-j values.',
                           device=name)
    else:
        pass
    if element.r0_pu is not None and element.x0_pu is not None:
        sr.R0 = element.r0_pu * Sbase_vg / element.Sn
        sr.X0 = element.x0_pu * Sbase_vg / element.Sn
    else:
        logger.add_warning('Common impedance Z0 missing: export r0_pu and x0_pu. ABC uses Z1.', device=name)
    if element.iz2eqz1 == 1:
        sr.R2, sr.X2 = r1, x1
    elif element.r2_pu is not None and element.x2_pu is not None:
        sr.R2 = element.r2_pu * Sbase_vg / element.Sn
        sr.X2 = element.x2_pu * Sbase_vg / element.Sn
    else:
        logger.add_warning('Common impedance Z2 missing: export r2_pu and x2_pu. ABC uses Z1.', device=name)

    return sr


def convert_dgs_series_capacitor_to_reactance(
        element: ElmScap,
        buses: List[dev.Bus],
        bus_by_terminal_id: Dict[str, dev.Bus],
        stacubic_dict: Dict[str, List[int]],
        cubics_by_obj_id: Dict[str, List[StaCubic]],
        logger: Logger,
        sbase_mva: float = 100.0
) -> dev.SeriesReactance:
    """
    Convert dgs series capacitor to reactance.

    :param element: element parameter.
    :param buses: buses parameter.
    :param bus_by_terminal_id: bus_by_terminal_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_obj_id: cubics_by_obj_id parameter.
    :param logger: logger parameter.
    :param sbase_mva: sbase_mva parameter.
    :return: Function result.
    """

    # Resolve buses via StaCubic.fold_id -> ElmTerm.ID -> Bus (same approach as lines/transformers)
    term_ids: List[str] = get_terminal_ids(element_id=element.ID, cubics_by_objid=cubics_by_obj_id)
    if len(term_ids) != 2:
        raise ValueError(
            f"ElmSind '{element.loc_name}' (ID={element.ID}) is not connected to exactly 2 terminals.")

    bus_from, bus_to = get_branch_buses(
        elm_id=element.ID,
        stacubic_dict=stacubic_dict,
        buses=buses,
        cubics_by_objid=cubics_by_obj_id,
        bus_by_term_id=bus_by_terminal_id
    )

    name: str = element.loc_name

    # Rated power calculation [MVA]
    Ur = element.ucn
    Ir = element.Curn
    Sr = np.sqrt(3) * Ur * Ir

    # Series capacitive reactance [pu]
    Zbase = Ur ** 2 / sbase_mva
    x = -1 * element.xcap / Zbase

    series_reactance = dev.SeriesReactance(
        bus_from=bus_from,
        bus_to=bus_to,
        name=name,
        idtag=_ref_id(element.ID),
        active=not element.outserv,
        r=0.0,
        x=x,
        rate=Sr
    )

    return series_reactance


def convert_dgs_to_series_reactance(
        element: ElmSind,
        buses: List[dev.Bus],
        bus_by_terminal_id: Dict[str, dev.Bus],
        stacubic_dict: Dict[str, List[int]],
        cubics_by_obj_id: Dict[str, List[StaCubic]],
        typsind_dict: Dict[str, TypSind],
        logger: Logger,
        sbase_mva: float = 100.0
) -> dev.SeriesReactance:
    """
    Convert dgs to series reactance.

    :param element: element parameter.
    :param buses: buses parameter.
    :param bus_by_terminal_id: bus_by_terminal_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_obj_id: cubics_by_obj_id parameter.
    :param typsind_dict: typsind_dict parameter.
    :param logger: logger parameter.
    :param sbase_mva: sbase_mva parameter.
    :return: Function result.
    """

    # Resolve buses via StaCubic.fold_id -> ElmTerm.ID -> Bus (same approach as lines/transformers)
    term_ids: List[str] = get_terminal_ids(element_id=element.ID, cubics_by_objid=cubics_by_obj_id)
    if len(term_ids) != 2:
        raise ValueError(
            f"ElmSind '{element.loc_name}' (ID={element.ID}) is not connected to exactly 2 terminals.")

    bus_from, bus_to = get_branch_buses(
        elm_id=element.ID,
        stacubic_dict=stacubic_dict,
        buses=buses,
        cubics_by_objid=cubics_by_obj_id,
        bus_by_term_id=bus_by_terminal_id
    )

    name: str = element.loc_name

    # Initialize sequence impedances (p.u.)
    r_pu: float = 1e-20
    x_pu: float = 1e-20
    r0_pu: float = 1e-20
    x0_pu: float = 1e-20
    r2_pu: float = 1e-20
    x2_pu: float = 1e-20

    # --- ElmSind: series reactor / series reactance

    # Prefer the type/template if present (PowerFactory "Type" pattern)
    typ_id: str | None = _ref_id(element.typ_id)
    if typ_id == "":
        typ_id = None

    src: ElmSind | TypSind = element
    if typ_id is not None and typ_id in typsind_dict:
        src = typsind_dict[typ_id]

    # PowerFactory ElmSind (as exported in test_export_v5.dgs):
    # - ucn: rated voltage (kV)
    # - Sn : rated power (MVA)
    # - uk : short-circuit voltage (%), gives |Z| in p.u. on device base (Sn, ucn)
    # - Pcu: copper losses (kW) at rated current, gives R in p.u. on device base
    sn_mva: float = float(src.Sn)
    uk_pu_dev: float = float(src.uk) / 100.0
    p_cu_mw: float = float(src.Pcu) / 1000.0

    r_pu_dev: float = p_cu_mw / sn_mva
    z_pu_dev: float = uk_pu_dev
    x_pu_dev: float = math.sqrt(max(0.0, z_pu_dev * z_pu_dev - r_pu_dev * r_pu_dev))

    # Convert from device base (Sn, ucn) to system base (sbase_mva, Vbase)
    v_dev_kv: float = float(src.ucn)
    v_base_kv: float = float(max(float(bus_from.Vnom), float(bus_to.Vnom)))
    v_ratio: float = v_dev_kv / v_base_kv

    scale: float = (sbase_mva / sn_mva) * (v_ratio * v_ratio)

    r_pu = r_pu_dev * scale
    x_pu = x_pu_dev * scale

    # If no explicit sequence data is exported, keep them consistent with positive sequence
    r0_pu = r_pu
    x0_pu = x_pu
    r2_pu = r_pu
    x2_pu = x_pu

    series_reactance = dev.SeriesReactance(
        bus_from=bus_from,
        bus_to=bus_to,
        name=name,
        idtag=_ref_id(element.ID),
        active=not element.outserv,
        r=r_pu,
        x=x_pu,
        r0=r0_pu,
        x0=x0_pu,
        r2=r2_pu,
        x2=x2_pu,
        rate=sn_mva
    )

    return series_reactance


def _get_scale_factor(scale0: float, logger: Logger, name: str) -> float:
    """
    Get scale factor.

    :param scale0: scale0 parameter.
    :param logger: logger parameter.
    :param name: name parameter.
    :return: Function result.
    """
    s = scale0
    if s == 0.0:
        return 1.0

    # Heuristic: values > 10 are very likely percentages (e.g., 100 = 100%)
    if s > 10.0:
        logger.add_warning(
            f"looks like percent.",
            device=name,
            device_class="ElmLod",
            value=s,
        )
        return s / 100.0

    return s


def _extract_load_pq(elmlod: ElmLod, logger: Logger) -> Tuple[float, float, float, float, float, float, float, float]:
    """
    Extract load pq.

    :param elmlod: elmlod parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    name = elmlod.loc_name or _ref_id(elmlod.ID) or "Load"

    phase_technology = (elmlod.phtech or "").strip().upper()
    single_phase = phase_technology.startswith("1PH")

    if elmlod.i_sym == 1 and not single_phase:

        # Apply scaling
        scale = _get_scale_factor(scale0=elmlod.scale0, logger=logger, name=name)

        # Active Power [MW]
        pa = elmlod.plinir * scale
        pb = elmlod.plinis * scale
        pc = elmlod.plinit * scale
        p = pa + pb + pc

        # Reactive Power [MVAr]
        qa = elmlod.qlinir * scale
        qb = elmlod.qlinis * scale
        qc = elmlod.qlinit * scale
        q = qa + qb + qc

    elif elmlod.i_sym == 1 and single_phase:

        # Apply scaling
        scale = _get_scale_factor(scale0=elmlod.scale0, logger=logger, name=name)

        # Active Power [MW]
        pa = elmlod.plini * scale
        p = pa

        # Reactive Power [MVAr]
        qa = elmlod.qlini * scale
        q = qa

        # Not connected phases
        pb, pc = 0.0, 0.0
        qb, qc = 0.0, 0.0

    else:
        # Primary: direct P/Q
        p = elmlod.plini
        q = elmlod.qlini

        # Fallback: S + cos(phi)
        if p == 0.0 and q == 0.0:
            s = elmlod.slini
            cosphi = elmlod.coslini

            if s != 0.0 and cosphi != 0.0:
                cosphi = max(min(cosphi, 1.0), -1.0)
                p = s * cosphi
                sinphi = math.sqrt(max(0.0, 1.0 - cosphi * cosphi))
                q = s * sinphi
                logger.add_warning(
                    f"P/Q not provided, derived from slini/coslini.",
                    device=name,
                    device_class="ElmLod",
                    value=q,
                )

        # Apply scaling
        scale = _get_scale_factor(scale0=elmlod.scale0, logger=logger, name=name)
        p *= scale
        q *= scale

        if phase_technology.startswith("1PH"):
            phase_count = 1
        elif phase_technology.startswith("2PH"):
            phase_count = 2
        else:
            phase_count = 3

        # PowerFactory stores balanced P/Q as the total of all connected
        # phases. Keep explicit local phase values so they can be mapped to
        # the resolved N/A/B/C conductors below.
        local_p = p / phase_count
        local_q = q / phase_count
        pa = local_p
        pb = local_p if phase_count >= 2 else 0.0
        pc = local_p if phase_count == 3 else 0.0
        qa = local_q
        qb = local_q if phase_count >= 2 else 0.0
        qc = local_q if phase_count == 3 else 0.0

    return p, pa, pb, pc, q, qa, qb, qc


def _map_load_pq_to_global_phases(
        elmlod: ElmLod,
        cubics_by_objid: Dict[str, List[StaCubic]],
        phase_map: PhaseMap,
        local_p: Tuple[float, float, float],
        local_q: Tuple[float, float, float],
        logger: Logger,
) -> Tuple[float, float, float, float, float, float]:
    """
    Map PowerFactory local load phases to VeraGrid A/B/C fields.

    The angular treatment of phase-to-phase loads is deliberately outside
    this mapping. If the DGS phase information is missing, the original local
    order is returned to preserve the previous behaviour.

    :param elmlod: PowerFactory load.
    :param cubics_by_objid: Cubicles grouped by connected element.
    :param phase_map: Resolved terminal-conductor phase map.
    :param local_p: Active power in PowerFactory Phase 1/2/3 order.
    :param local_q: Reactive power in PowerFactory Phase 1/2/3 order.
    :param logger: VeraGrid logger.
    :return: Active and reactive power in VeraGrid P1/P2/P3 order.
    """
    cubics = cubics_by_objid.get(_ref_id(elmlod.ID), [])
    if len(cubics) == 0:
        return local_p + local_q

    phase_technology = (elmlod.phtech or "").strip().upper()
    phases = [
        phase
        for phase in _get_cubic_phases(cubic=cubics[0], phase_map=phase_map)
        if phase != 0
    ]

    if phase_technology.startswith("1PH"):
        expected_phases = 1
    elif phase_technology.startswith("2PH"):
        expected_phases = 2
    else:
        expected_phases = 3

    if len(phases) < expected_phases:
        if len(phases) > 0:
            logger.add_warning(
                "Incomplete phase mapping for load; keeping local phase order.",
                device=elmlod.loc_name,
                device_class="ElmLod",
                value=phases,
                expected_value=expected_phases,
            )
        return local_p + local_q

    global_p = [0.0, 0.0, 0.0]
    global_q = [0.0, 0.0, 0.0]

    if phase_technology == "1PH PH-PH" and len(phases) >= 2:
        phase_pair = tuple(sorted(phases[:2]))
        branch_idx = {(1, 2): 0, (2, 3): 1, (1, 3): 2}[phase_pair]
        global_p[branch_idx] = local_p[0]
        global_q[branch_idx] = local_q[0]
        return (*global_p, *global_q)

    for local_index, phase in enumerate(phases[:expected_phases]):
        global_index = phase - 1
        global_p[global_index] = local_p[local_index]
        global_q[global_index] = local_q[local_index]

    return (*global_p, *global_q)


def convert_dgs_ward_equivalent_to_load(elmvac: ElmVac,
                                        stacubic_dict: Dict[str, List[int]],
                                        buses: List[dev.Bus],
                                        logger: Logger,
                                        cubics_by_objid: Dict[str, List[StaCubic]],
                                        bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.Load]:
    """
    Convert dgs ward equivalent to load.

    :param elmvac: elmvac parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmvac.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    name: str = elmvac.loc_name

    constant_p = elmvac.Pload - elmvac.Pgen  # Net constant P active power [MW]
    constant_q = elmvac.Qload - elmvac.Qgen  # Net constant Q reactive power [Mvar]
    constant_g = elmvac.Pzload  # Constant Z active power [MW]
    constant_b = -1 * elmvac.Qzload  # Constant Z reactive power [Mvar]

    load = dev.Load(
        name=name,
        idtag=_ref_id(elmvac.ID),
        P=constant_p,
        Q=constant_q,
        G=constant_g,
        B=constant_b,
        active=not bool(elmvac.outserv)
    )

    return bus, load


def convert_dgs_to_load(elmlod: ElmLod,
                        stacubic_dict: Dict[str, List[int]],
                        buses: List[dev.Bus],
                        logger: Logger,
                        cubics_by_objid: Dict[str, List[StaCubic]],
                        bus_by_term_id: Dict[str, dev.Bus],
                        phase_map: PhaseMap,
                        comldf: ComLdf | None,
                        typlod: TypLod | None) -> Tuple[dev.Bus, dev.Load]:
    """
    Convert dgs to load.

    :param elmlod: elmlod parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param phase_map: Resolved terminal-conductor phase map.
    :param comldf: PowerFactory load-flow configuration, if exported.
    :param typlod: PowerFactory type referenced by the load, if available.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmlod.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    p_mw, pa_mw, pb_mw, pc_mw, q_mvar, qa_mvar, qb_mvar, qc_mvar = _extract_load_pq(
        elmlod=elmlod,
        logger=logger,
    )
    pa_mw, pb_mw, pc_mw, qa_mvar, qb_mvar, qc_mvar = _map_load_pq_to_global_phases(
        elmlod=elmlod,
        cubics_by_objid=cubics_by_objid,
        phase_map=phase_map,
        local_p=(pa_mw, pb_mw, pc_mw),
        local_q=(qa_mvar, qb_mvar, qc_mvar),
        logger=logger,
    )

    use_voltage_dependency = comldf is not None and int(comldf.iopt_pq) == 1
    is_constant_current = (
            typlod is not None
            and typlod.aP == 0.0
            and typlod.bP == 1.0
            and typlod.aQ == 0.0
            and typlod.bQ == 1.0
    )
    is_constant_impedance = (
            typlod is not None
            and typlod.aP == 0.0
            and typlod.bP == 0.0
            and typlod.aQ == 0.0
            and typlod.bQ == 0.0
    )

    # Use the voltage-dependent model only when PowerFactory enables it.
    if use_voltage_dependency and is_constant_current:

        load = dev.Load(
            name=elmlod.loc_name or f"Load_{_ref_id(elmlod.ID)}",
            Ir=p_mw,
            Ir1=pa_mw,
            Ir2=pb_mw,
            Ir3=pc_mw,
            Ii=-1.0 * q_mvar,
            Ii1=-1.0 * qa_mvar,
            Ii2=-1.0 * qb_mvar,
            Ii3=-1.0 * qc_mvar,
            active=not bool(elmlod.outserv)
        )

    # Constant impedance loads
    elif use_voltage_dependency and is_constant_impedance:

        load = dev.Load(
            name=elmlod.loc_name or f"Load_{_ref_id(elmlod.ID)}",
            G=p_mw,
            G1=pa_mw,
            G2=pb_mw,
            G3=pc_mw,
            B=-1.0 * q_mvar,
            B1=-1.0 * qa_mvar,
            B2=-1.0 * qb_mvar,
            B3=-1.0 * qc_mvar,
            active=not bool(elmlod.outserv)
        )

    else:

        load = dev.Load(
            name=elmlod.loc_name or f"Load_{_ref_id(elmlod.ID)}",
            P=p_mw,
            P1=pa_mw,
            P2=pb_mw,
            P3=pc_mw,
            Q=q_mvar,
            Q1=qa_mvar,
            Q2=qb_mvar,
            Q3=qc_mvar,
            active=not bool(elmlod.outserv)
        )

    # Add the connection type
    if elmlod.phtech == "3PH-'D'":
        load.conn = ShuntConnectionType.Delta
    elif elmlod.phtech == "3PH PH-E":
        load.conn = ShuntConnectionType.GroundedStar
    elif elmlod.phtech == "3PH-'YN'":
        load.conn = ShuntConnectionType.NeutralStar
    elif elmlod.phtech == "2PH PH-E":
        load.conn = ShuntConnectionType.GroundedStar
    elif elmlod.phtech == "2PH-'YN'":
        load.conn = ShuntConnectionType.NeutralStar
    elif elmlod.phtech == "1PH PH-PH":
        load.conn = ShuntConnectionType.Delta
    elif elmlod.phtech == "1PH PH-N":
        load.conn = ShuntConnectionType.NeutralStar
    elif elmlod.phtech == "1PH PH-E":
        load.conn = ShuntConnectionType.GroundedStar
    else:
        load.conn = ShuntConnectionType.GroundedStar

    return bus, load


def _set_generator_load_flow_sequences(gen: dev.Generator | dev.StaticGenerator, source: ElmGenstat,
                                       Sbase: float, logger: Logger) -> None:
    """Import the physical connection and available load-flow sequence impedances.

    :param gen: Voltage-controlled or fixed-power sequence injection to populate.
    :param source: ElmGenstat with optional advanced load-flow fields.
    :param Sbase: Circuit power base in MVA.
    :param logger: Import diagnostics; missing values must not become short circuits.
    """
    if source.phtech not in (PowerFactoryGeneratorTechnology.ThreePhase,
                             PowerFactoryGeneratorTechnology.ThreePhaseEarth):
        logger.add_warning('Generator sequence response not imported: missing or unsupported phase technology.',
                           device=gen.name)
        return
    else:
        technology: PowerFactoryGeneratorTechnology = PowerFactoryGeneratorTechnology(source.phtech)
    # Reuse the injection connection, which also governs manually created generators.
    if technology == PowerFactoryGeneratorTechnology.ThreePhase:
        gen.conn = ShuntConnectionType.FloatingStar
    elif source.nneutral == 0:
        gen.conn = ShuntConnectionType.GroundedStar
    elif source.nneutral in (1, 2):
        gen.conn = ShuntConnectionType.NeutralStar
        logger.add_warning('Generator has an explicit neutral connection unsupported by U1 power flow.',
                           device=gen.name)
    else:
        logger.add_warning('Generator sequence response not imported: export a valid nneutral connection.',
                           device=gen.name)
        return
    if not np.isfinite(source.sgn) or source.sgn <= 0.0 or not np.isfinite(Sbase) or Sbase <= 0.0:
        logger.add_warning('Generator sequence response not imported: invalid power base.', device=gen.name)
        return
    else:
        factor: float = Sbase / source.sgn

    # Preserve provided Z0 even when blocked; the connection determines whether it acts.
    if source.r0 is not None and source.x0 is not None:
        z0: complex = complex(source.r0, source.x0) * factor
        if np.isfinite(z0) and abs(z0) >= 1e-12:
            gen.R0, gen.X0 = z0.real, z0.imag
        else:
            logger.add_warning('Generator Z0 not imported: impedance must be finite and nonzero.', device=gen.name)
    elif technology == PowerFactoryGeneratorTechnology.ThreePhaseEarth:
        logger.add_warning('Generator Z0 response omitted: export both r0 and x0.', device=gen.name)
    else:
        pass
    if source.r2 is not None and source.x2 is not None:
        z2: complex = complex(source.r2, source.x2) * factor
        if np.isfinite(z2) and abs(z2) >= 1e-12:
            gen.R2, gen.X2 = z2.real, z2.imag
        else:
            logger.add_warning('Generator Z2 response omitted: impedance must be finite and nonzero.', device=gen.name)
    else:
        logger.add_warning('Generator Z2 response omitted: export both r2 and x2.', device=gen.name)


def convert_dgs_staticgen_to_gen(elmgenstat: ElmGenstat,
                                 stacubic_dict: Dict[str, List[int]],
                                 buses: List[dev.Bus],
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1,
                                 Sbase: float = 100.0) -> Tuple[dev.Bus, dev.Generator]:
    """
    Convert dgs staticgen to gen.

    :param elmgenstat: elmgenstat parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param Sbase: Circuit base for imported sequence impedances.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmgenstat.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    # Slack/reference machine indicator (PowerFactory exports ip_ctrl=1 on the slack generator)
    if int(elmgenstat.ip_ctrl) == 1:
        bus.set_is_slack_at(t=None, val=True)

    generator_name = _get_non_empty_name(elmgenstat.loc_name, f"{_ref_id(elmgenstat.ID)}")
    generator_name = _get_parallel_device_name(generator_name, parallel_index, parallel_count)
    generator_idtag = _get_parallel_device_idtag(_ref_id(elmgenstat.ID), parallel_index, parallel_count)

    gen = dev.Generator(
        name=generator_name,
        idtag=generator_idtag,
        P=float(elmgenstat.pgini),
        vset=float(elmgenstat.usetp),
        Snom=float(elmgenstat.sgn),
        active=not bool(elmgenstat.outserv),
    )

    _set_generator_load_flow_sequences(gen=gen, source=elmgenstat, Sbase=Sbase, logger=logger)

    return bus, gen


def convert_dgs_staticgen_to_battery(elmgenstat: ElmGenstat,
                                     stacubic_dict: Dict[str, List[int]],
                                     buses: List[dev.Bus],
                                     logger: Logger,
                                     cubics_by_objid: Dict[str, List[StaCubic]],
                                     bus_by_term_id: Dict[str, dev.Bus],
                                     parallel_index: int = 0,
                                     parallel_count: int = 1,
                                     Sbase: float = 100.0) -> Tuple[dev.Bus, dev.Battery]:
    """
    Convert dgs staticgen to battery.

    :param elmgenstat: elmgenstat parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param Sbase: Circuit power base in MVA.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmgenstat.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    name = _get_non_empty_name(elmgenstat.loc_name, f"Storage_{_ref_id(elmgenstat.ID)}")
    name = _get_parallel_device_name(name, parallel_index, parallel_count)
    battery_idtag = _get_parallel_device_idtag(_ref_id(elmgenstat.ID), parallel_index, parallel_count)

    # Power Factor from P and Q
    P = float(elmgenstat.pgini)
    Q = float(elmgenstat.qgini)
    pf = np.cos(np.atan(Q / (P + 1e-20)))

    battery = dev.Battery(
        name=name,
        idtag=battery_idtag,
        P=P,
        Q=Q,
        control_mode=GeneratorControlMode.Q,
        Snom=float(elmgenstat.sgn),
        active=not bool(elmgenstat.outserv)
    )

    _set_generator_load_flow_sequences(gen=battery, source=elmgenstat, Sbase=Sbase, logger=logger)

    return bus, battery


def convert_dgs_to_static_gen(elmgenstat: ElmGenstat,
                              stacubic_dict: Dict[str, List[int]],
                              buses: List[dev.Bus],
                              logger: Logger,
                              cubics_by_objid: Dict[str, List[StaCubic]],
                              bus_by_term_id: Dict[str, dev.Bus],
                              parallel_index: int = 0,
                              parallel_count: int = 1,
                              Sbase: float = 100.0) -> Tuple[dev.Bus, dev.StaticGenerator]:
    """
    Convert dgs to static gen.

    :param elmgenstat: elmgenstat parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :param Sbase: Circuit base for imported sequence impedances.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmgenstat.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    # Slack/reference machine indicator (PowerFactory exports ip_ctrl=1 on the slack generator)
    if int(elmgenstat.ip_ctrl) == 1:
        bus.set_is_slack_at(t=None, val=True)

    generator_name = _get_non_empty_name(elmgenstat.loc_name, f"StaticGen_{_ref_id(elmgenstat.ID)}")
    generator_name = _get_parallel_device_name(generator_name, parallel_index, parallel_count)
    generator_idtag = _get_parallel_device_idtag(_ref_id(elmgenstat.ID), parallel_index, parallel_count)

    stagen = dev.StaticGenerator(
        name=generator_name,
        idtag=generator_idtag,
        P=float(elmgenstat.pgini),
        Q=float(elmgenstat.qgini),
        Snom=float(elmgenstat.sgn),
        active=not bool(elmgenstat.outserv)
    )

    # Storage droop uses the existing AC control unless VSC import was explicitly requested.
    if elmgenstat.cCategory == 'Storage' and elmgenstat.av_mode == 'vdroop':
        stagen.control_mode = StaticGeneratorControlMode.QVDroop
        stagen.Vset = float(elmgenstat.usetp)
        stagen.droop = float(elmgenstat.ddroop)
        stagen.Vset_min = float(elmgenstat.usp_min)
        stagen.Vset_max = float(elmgenstat.usp_max)
    else:
        pass

    _set_generator_load_flow_sequences(gen=stagen, source=elmgenstat, Sbase=Sbase, logger=logger)

    return bus, stagen


def convert_dgs_staticgen_to_vsc(elmgenstat: ElmGenstat,
                                 stacubic_dict: Dict[str, List[int]],
                                 buses: List[dev.Bus],
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1) -> Tuple[dev.Bus, dev.VSC]:
    """
    Convert dgs staticgen to vsc.

    :param elmgenstat: elmgenstat parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    ac_bus = get_injection_bus(elm_id=elmgenstat.ID,
                               stacubic_dict=stacubic_dict,
                               buses=buses,
                               cubics_by_objid=cubics_by_objid,
                               bus_by_term_id=bus_by_term_id)

    dc_bus = dev.Bus(name=f'{_ref_id(ac_bus.name)}_DC',
                     is_dc=True,
                     is_slack=True,
                     xpos=ac_bus.x,
                     ypos=ac_bus.y - 200)

    vsc_name = _get_non_empty_name(elmgenstat.loc_name, f"VSC_{_ref_id(elmgenstat.ID)}")
    vsc_name = _get_parallel_device_name(vsc_name, parallel_index, parallel_count)
    vsc_idtag = _get_parallel_device_idtag(_ref_id(elmgenstat.ID), parallel_index, parallel_count)

    if elmgenstat.av_mode == 'vdroop':
        vsc = dev.VSC(
            name=vsc_name,
            idtag=vsc_idtag,
            active=not bool(elmgenstat.outserv),
            bus_from=dc_bus,
            bus_to=ac_bus,
            rate=float(elmgenstat.sgn),
            alpha1=0.0,
            alpha2=0.0,
            alpha3=0.0,
            control1=ConverterControlType.Pac,
            control2=ConverterControlType.Q_droop,
            control1_val=-1.0 * float(elmgenstat.pgini),
            control2_val=-1.0 * float(elmgenstat.qgini),
            fault_control=ConverterFaultControlType.WECC_WT_Type_4B,
            control2_droop=float(elmgenstat.ddroop),
            control2_droop_val_min=float(elmgenstat.usp_min),
            control2_droop_val_max=float(elmgenstat.usp_max),
            control2_droop_val=float(elmgenstat.usetp),
            control2_val_min=float(elmgenstat.cQ_min),
            control2_val_max=float(elmgenstat.cQ_max)
        )

    elif elmgenstat.av_mode == 'constq':
        vsc = dev.VSC(
            name=vsc_name,
            idtag=vsc_idtag,
            active=not bool(elmgenstat.outserv),
            bus_from=dc_bus,
            bus_to=ac_bus,
            rate=float(elmgenstat.sgn),
            alpha1=0.0,
            alpha2=0.0,
            alpha3=0.0,
            control1=ConverterControlType.Pac,
            control2=ConverterControlType.Qac,
            control1_val=-1.0 * float(elmgenstat.pgini),
            control2_val=-1.0 * float(elmgenstat.qgini),
            fault_control=ConverterFaultControlType.WECC_WT_Type_4B
        )

    else:
        vsc = dev.VSC(
            name=vsc_name,
            idtag=vsc_idtag,
            active=not bool(elmgenstat.outserv),
            bus_from=dc_bus,
            bus_to=ac_bus,
            rate=float(elmgenstat.sgn),
            alpha1=0.0,
            alpha2=0.0,
            alpha3=0.0,
            control1=ConverterControlType.Pac,
            control2=ConverterControlType.Qac,
            control1_val=0.0,
            control2_val=0.0,
            fault_control=ConverterFaultControlType.WECC_WT_Type_4B
        )
        logger.add_warning(
            f"This wind turbine is not Const. Q or Voltage Q-droop.",
            device=vsc_name,
            device_class="ElmGenstat"
        )

    return dc_bus, vsc


def convert_dgs_external_grid_to_generator(elmxnet: ElmXnet,
                                           stacubic_dict: Dict[str, List[int]],
                                           buses: List[dev.Bus],
                                           logger: Logger,
                                           cubics_by_objid: Dict[str, List[StaCubic]],
                                           bus_by_term_id: Dict[str, dev.Bus],
                                           Sbase: float) -> Tuple[dev.Bus, dev.Generator]:
    """
    Convert dgs external grid to generator.

    :param elmxnet: elmxnet parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param Sbase: Sbase parameter.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmxnet.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    bustype = str(elmxnet.bustp).strip().upper()

    k = elmxnet.rntxn  # R/X ratio
    Sk = elmxnet.snss  # Short-circuit power Sk''
    c = elmxnet.cmax  # Maximum voltage factor

    # Synchronous reactances
    xd = elmxnet.xd
    xq = elmxnet.xq
    if xd == xq:
        x = xd
    elif xd <= xq:
        x = xd
    else:
        x = xq

    Snom = x * np.sqrt(1 + k ** 2) * Sk / c  # Nominal Power of the external grid [MVA]
    r1 = x * k * Sbase / Snom  # Positive-sequence equivalent resistance [pu]
    x1 = x * Sbase / Snom  # Positive-sequence equivalent reactance [pu]

    gen = dev.Generator(
        name=elmxnet.loc_name or f"Gen_{_ref_id(elmxnet.ID)}",
        idtag=_ref_id(elmxnet.ID),
        active=not bool(elmxnet.outserv),
        r1=r1,
        x1=x1,
    )

    if bustype == 'SL':
        bus.set_is_slack_at(t=None, val=True)

    elif bustype == 'PV':
        gen.Vset = elmxnet.usetp
        gen.P = elmxnet.pgini

    elif bustype == 'PQ':
        gen.P = elmxnet.pgini
        gen.power_factor = np.cos(np.atan(elmxnet.qgini / elmxnet.pgini))
    else:
        gen.P = elmxnet.pgini
        gen.power_factor = np.cos(np.atan(elmxnet.qgini / elmxnet.pgini))

    return bus, gen


def convert_dgs_to_external_grid(elmxnet: ElmXnet,
                                 stacubic_dict: Dict[str, List[int]],
                                 buses: List[dev.Bus],
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.ExternalGrid]:
    """
    Convert dgs to external grid.

    :param elmxnet: elmxnet parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    bus = get_injection_bus(elm_id=elmxnet.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    bustype = str(elmxnet.bustp).strip().upper()

    xgrid = dev.ExternalGrid(
        name=elmxnet.loc_name or f"Load_{_ref_id(elmxnet.ID)}",
        active=not bool(elmxnet.outserv)
    )

    if bustype == 'SL':
        bus.set_is_slack_at(t=None, val=True)
        xgrid.mode = ExternalGridMode.VD
        xgrid.Vm = elmxnet.usetp
        xgrid.Va = math.radians(float(elmxnet.phiini))

    elif bustype == 'PV':
        xgrid.mode = ExternalGridMode.PV
        xgrid.Vm = elmxnet.usetp
        xgrid.P = elmxnet.pgini

    elif bustype == 'PQ':
        xgrid.mode = ExternalGridMode.PQ
        xgrid.P = elmxnet.pgini
        xgrid.Q = elmxnet.qgini
    else:
        xgrid.mode = ExternalGridMode.PQ
        xgrid.P = elmxnet.pgini
        xgrid.Q = elmxnet.qgini

    return bus, xgrid


def _extract_shunt_gb(elmshnt: ElmShnt, f: float, logger: Logger) -> Tuple[float, float]:
    """
    Extract shunt gb.

    :param elmshnt: elmshnt parameter.
    :param f: f parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    name = elmshnt.loc_name or _ref_id(elmshnt.ID) or "Shunt"

    shtype: int = elmshnt.shtype
    Q: float = elmshnt.qtotn * 1e6  # Rated Reactive Power [Mvar] -> [var]
    U: float = elmshnt.ushnm * 1e3  # Rated Voltage [kV] -> [V]
    fres: float = elmshnt.fres  # Resonance Frequency [Hz]
    h = fres / f  # Tuning Order
    conn: int = elmshnt.ctech  # Connection
    quality_factor: float = elmshnt.grea  # Quality Factor

    w = 2 * np.pi * f  # Electrical angular speed [rad/s]
    if conn == 0:
        d_y = 3.0  # conn==0 -> 3PH-D
    else:
        d_y = 1.0  # 3PH-Y/YN

    if shtype == 0:  # R-L-C

        C = Q / (d_y * w * U ** 2) * (1 - 1 / h ** 2)
        L = 1 / ((h * w) ** 2 * C)
        if quality_factor == 0.0:
            R = 0.0
        else:
            R = (w * L) / quality_factor

        Z = R + 1j * (w * L - 1 / (w * C))
        S = d_y * U ** 2 / np.conj(Z)

        g_mw = np.real(S) / 1e6
        b_mvar = -np.imag(S) / 1e6

    elif shtype == 1:  # R-L

        L = d_y * U ** 2 / (w * Q)
        if quality_factor == 0.0:
            R = 0.0
        else:
            R = (w * L) / quality_factor

        Z = R + 1j * w * L
        S = d_y * U ** 2 / np.conj(Z)

        g_mw = np.real(S) / 1e6
        b_mvar = -np.imag(S) / 1e6

    elif shtype == 2:  # C

        C = Q / (d_y * w * U ** 2)
        G = w * C * elmshnt.tandc

        Y = G + 1j * w * C
        S = d_y * U ** 2 * np.conj(Y)

        g_mw = np.real(S) / 1e6
        b_mvar = -np.imag(S) / 1e6

    elif shtype == 3:  # R-L-C,Rp

        C = Q / (d_y * w * U ** 2) * (1 - 1 / h ** 2)
        L = 1 / ((h * w) ** 2 * C)
        if quality_factor == 0.0:
            R = 0.0
        else:
            R = (w * L) / quality_factor
        Rp = elmshnt.rpara

        try:
            Z = ((R + 1j * w * L) * Rp) / ((R + 1j * w * L) + Rp) + 1 / (1j * w * C)
            S = d_y * U ** 2 / np.conj(Z)

            g_mw = np.real(S) / 1e6
            b_mvar = -np.imag(S) / 1e6
        except ZeroDivisionError:
            g_mw = 0.0
            b_mvar = 0.0
            logger.add_warning(
                f"Cannot be computed because of zero division.",
                device=name,
                device_class="ElmShnt"
            )

    elif shtype == 4:  # R-L-C1-C2,Rp

        C2 = Q / (d_y * w * U ** 2)
        C1 = C2 * (h ** 2 - 1)
        L = 1 / (w ** 2 * C1)
        if quality_factor == 0.0:
            R = 0.0
        else:
            R = w * L / quality_factor
        Rp = elmshnt.rpara

        try:
            Z = ((R + 1j * w * L + 1 / (1j * w * C1)) * Rp) / ((R + 1j * w * L + 1 / (1j * w * C1)) + Rp) + 1 / (
                    1j * w * C2)
            S = d_y * U ** 2 / np.conj(Z)

            g_mw = np.real(S) / 1e6
            b_mvar = -np.imag(S) / 1e6
        except ZeroDivisionError:
            g_mw = 0.0
            b_mvar = 0.0
            logger.add_warning(
                f"Cannot be computed because of zero division.",
                device=name,
                device_class="ElmShnt"
            )
    else:
        g_mw = 0.0
        b_mvar = 0.0
        logger.add_warning(
            f"Cannot be computed because of type not recognized.",
            device=name,
            device_class="ElmShnt",
            value=shtype
        )

    if elmshnt.ncapa == 0 and elmshnt.ncapx <= 1:
        g_mw = 0.0
        b_mvar = 0.0

    return g_mw, b_mvar


def convert_dgs_to_shunt(elmshnt: ElmShnt,
                         stacubic_dict: Dict[str, List[int]],
                         buses: List[dev.Bus],
                         logger: Logger,
                         cubics_by_objid: Dict[str, List[StaCubic]],
                         bus_by_term_id: Dict[str, dev.Bus],
                         phase_map: PhaseMap,
                         frequency: float) -> Tuple[dev.Bus, dev.Shunt]:
    """
    Convert dgs to shunt.

    :param elmshnt: elmshnt parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param phase_map: Resolved terminal-conductor phase map.
    :param frequency: frequency parameter.
    :return: Function result.
    """
    name = elmshnt.loc_name or f"Shunt_{_ref_id(elmshnt.ID)}"

    bus = get_injection_bus(elm_id=elmshnt.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    g_mw, b_mvar = _extract_shunt_gb(elmshnt=elmshnt, f=frequency, logger=logger)
    phases = [phase for phase in _get_element_phases(elmshnt.ID, cubics_by_objid, phase_map) if phase != 0]

    # Unbalanced
    if elmshnt.ctech == 0:  # 3PH-'D'
        g_abc = [g_mw / 3] * 3
        b_abc = [b_mvar / 3] * 3
        connection = ShuntConnectionType.Delta
    elif elmshnt.ctech in (3, 5):  # 2PH-'Y' or 1PH PH-PH
        phase_pair = tuple(sorted(phases[:2])) if len(phases) >= 2 else (1, 2)
        branch_idx = {(1, 2): 0, (2, 3): 1, (1, 3): 2}[phase_pair]
        g_abc = [0.0] * 3
        b_abc = [0.0] * 3
        g_abc[branch_idx] = g_mw
        b_abc[branch_idx] = b_mvar
        connection = ShuntConnectionType.Delta
    else:
        phase_count = {1: 3, 2: 3, 4: 2, 6: 1, 7: 1}.get(elmshnt.ctech, 3)
        active_phases = phases[:phase_count] if len(phases) >= phase_count else list(range(1, phase_count + 1))
        g_abc = [0.0] * 3
        b_abc = [0.0] * 3
        for phase in active_phases:
            g_abc[phase - 1] = g_mw / phase_count
            b_abc[phase - 1] = b_mvar / phase_count

        if elmshnt.ctech == 1:  # 3PH-'Y'
            connection = ShuntConnectionType.FloatingStar
        elif elmshnt.ctech in (2, 4):  # 3PH-'YN' or 2PH-'YN'
            connection = (ShuntConnectionType.GroundedStar if elmshnt.cgnd == 0
                          else ShuntConnectionType.NeutralStar)
        elif elmshnt.ctech == 6:  # 1PH PH-N
            connection = ShuntConnectionType.NeutralStar
        else:  # 1PH PH-E and backwards-compatible fallback
            connection = ShuntConnectionType.GroundedStar

    shunt = dev.Shunt(name=name,
                      G=g_mw,
                      G1=g_abc[0],
                      G2=g_abc[1],
                      G3=g_abc[2],
                      B=b_mvar,
                      B1=b_abc[0],
                      B2=b_abc[1],
                      B3=b_abc[2],
                      active=(elmshnt.outserv == 0))
    shunt.conn = connection
    shunt.phN = (elmshnt.ctech == 6
                 or any("N" in _get_cubic_phase_names(cubic)
                        for cubic in cubics_by_objid.get(_ref_id(elmshnt.ID), [])))

    return bus, shunt


def _build_elmshnt_step_model(elmshnt: ElmShnt, logger: Logger) -> Tuple[np.ndarray, int, float, float]:
    """
    Build elmshnt step model.

    :param elmshnt: elmshnt parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    name: str = elmshnt.loc_name or _ref_id(elmshnt.ID) or "ElmShnt"
    ncapx: int = int(elmshnt.ncapx)
    q_step: float = float(elmshnt.qcapn)
    if q_step == 0.0:
        q_step = -abs(float(elmshnt.qrean))
    else:
        pass

    qtotn: float = float(elmshnt.qtotn)
    if q_step == 0.0 and qtotn != 0.0:
        q_step = qtotn / float(ncapx)
        if int(elmshnt.shtype) == 1:
            q_step = -abs(q_step)
        else:
            pass

        logger.add_warning(
            f"using q_step=qtotn/ncapx.",
            device=name,
            device_class="ElmShnt",
            value=q_step
        )
    else:
        pass

    # Step increments: [0.0, q_step, q_step, ..., q_step] with length ncapx+1
    b_steps: np.ndarray = np.concatenate((np.array([0.0], dtype=float), np.full(ncapx, q_step, dtype=float)))

    # Initial step index equals the number of connected steps (ncapa) because b_steps[0] is OFF (0 MVAr).
    initial_step: int = int(elmshnt.ncapa)
    if initial_step < 0:
        initial_step = 0
    else:
        pass
    if initial_step > ncapx:
        initial_step = ncapx
    else:
        pass

    # Bounds (MVAr @ v=1 p.u.) inferred from the step size sign
    total: float = q_step * float(ncapx)
    if total >= 0.0:
        bmin: float = 0.0
        bmax: float = total
    else:
        bmin = total
        bmax = 0.0

    return b_steps, initial_step, bmin, bmax


def convert_dgs_to_controllable_shunt_from_elmshnt(elmshnt: ElmShnt,
                                                   stacubic_dict: Dict[str, List[int]],
                                                   buses: List[dev.Bus],
                                                   logger: Logger,
                                                   cubics_by_objid: Dict[str, List[StaCubic]],
                                                   bus_by_term_id: Dict[str, dev.Bus],
                                                   frequency: float) -> Tuple[
    dev.Bus, dev.ControllableShunt]:
    """
    Convert dgs to controllable shunt from elmshnt.

    :param elmshnt: elmshnt parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param frequency: frequency parameter.
    :return: Function result.
    """
    name: str = elmshnt.loc_name or f"ElmShnt_{_ref_id(elmshnt.ID)}"

    bus: dev.Bus = get_injection_bus(elm_id=elmshnt.ID,
                                     stacubic_dict=stacubic_dict,
                                     buses=buses,
                                     cubics_by_objid=cubics_by_objid,
                                     bus_by_term_id=bus_by_term_id)

    if elmshnt.i_cont == 1:  # Continuous

        b_steps, initial_step, bmin, bmax = _build_elmshnt_step_model(elmshnt=elmshnt, logger=logger)

        if int(elmshnt.iswitch) != 0:
            control_mode = ShuntControlMode.Discrete
        else:
            control_mode = ShuntControlMode.Locked

        vset: float = float(elmshnt.usetp)

        cshunt: dev.ControllableShunt = dev.ControllableShunt(
            name=name,
            idtag=_ref_id(elmshnt.ID),
            number_of_steps=int(len(b_steps)),
            step=int(initial_step),
            g_per_step=0.0,
            b_per_step=0.0,
            Bmin=bmin,
            Bmax=bmax,
            Gmin=0.0,
            Gmax=0.0,
            active=(elmshnt.outserv == 0),
            vset=vset,
            control_mode=control_mode,
            control_bus=bus,
        )

        # Override step arrays to match the DGS stepped-bank model (OFF + ncapx identical increments).
        cshunt.b_steps = b_steps
        cshunt.g_steps = np.zeros(len(b_steps), dtype=float)
        cshunt.active_steps = np.ones(len(b_steps), dtype=int)

        # Ensure B/G are coherent with the initial step after overriding arrays
        cshunt.step = int(initial_step)

    elif elmshnt.i_cont == 0:  # Discrete

        g_mw, b_mvar = _extract_shunt_gb(elmshnt=elmshnt, f=frequency, logger=logger)

        cshunt: dev.ControllableShunt = dev.ControllableShunt(
            name=name,
            idtag=_ref_id(elmshnt.ID),
            number_of_steps=elmshnt.ncapx,
            step=elmshnt.ncapa,
            g_per_step=g_mw,
            b_per_step=b_mvar,
            active=(elmshnt.outserv == 0),
            vmax=elmshnt.usetp_mx,
            vmin=elmshnt.usetp_mn,
            control_mode=ShuntControlMode.Discrete
        )

    return bus, cshunt


def convert_dgs_svs_to_vsc(elmsvs: ElmSvs,
                           stacubic_dict: Dict[str, List[int]],
                           buses: List[dev.Bus],
                           logger: Logger,
                           cubics_by_objid: Dict[str, List[StaCubic]],
                           bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.VSC]:
    """
    Convert dgs svs to vsc.

    :param elmsvs: elmsvs parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    name = elmsvs.loc_name or f"ElmSvs_{_ref_id(elmsvs.ID)}"

    ac_bus = get_injection_bus(elm_id=elmsvs.ID,
                               stacubic_dict=stacubic_dict,
                               buses=buses,
                               cubics_by_objid=cubics_by_objid,
                               bus_by_term_id=bus_by_term_id)

    dc_bus = dev.Bus(name=f'{_ref_id(ac_bus.name)}_SVS_DC',
                     is_dc=True,
                     is_slack=True,
                     xpos=ac_bus.x,
                     ypos=ac_bus.y - 200, )

    vsc_name = _get_non_empty_name(elmsvs.loc_name, f"SVS_{_ref_id(elmsvs.ID)}")

    control_mode = elmsvs.i_ctrl

    if control_mode == 2:  # Reactive Power Control

        control1 = ConverterControlType.Pac
        control1_val = 0.0  # Active power injection of the SVS [MW]

        control2 = ConverterControlType.Qac
        control2_val = elmsvs.qsetp  # Reactive power injection of the SVS [MVAr]

        rate = max(np.abs(elmsvs.tcrmax), np.abs(elmsvs.qmin))
        kpd = 0.0  # Droop [%]
        ysvs = 0.0  # Fixed admittance based on 1 MVA / Ub^2
        u_setpoint = 1.0  # Voltage Setpoint [pu]

    elif control_mode == 1:  # Voltage Control
        if elmsvs.i_droop == 0:  # No droop, just sets the voltage to the given setpoint

            control1 = ConverterControlType.Pac
            control1_val = 0.0  # Active power injection of the SVS [MW]

            control2 = ConverterControlType.Vm_ac
            control2_val = elmsvs.usetp  # Voltage setpoint [pu]

            ysvs = 0.0  # Fixed admittance based on 1 MVA / Ub^2
            rate = max(np.abs(elmsvs.tcrmax), np.abs(elmsvs.qmin))
            kpd = 0.0  # Droop [%]
            u_setpoint = 1.0  # Voltage Setpoint [pu]

        else:  # Droop Control

            kpd = elmsvs.ddroop  # Droop [%]
            rate = elmsvs.Srated  # Rated Power [MVA]
            u_setpoint = elmsvs.usetp  # Voltage Setpoint [pu]

            control1 = ConverterControlType.Pac
            control1_val = 0.0  # Active power injection of the SVS [MW]

            control2 = ConverterControlType.Q_droop
            control2_val = 0.0  # Reactive power injection of the SVS [MVAr]

            ysvs = 0.0  # Fixed admittance based on 1 MVA / Ub^2

    else:  # No Control
        control1 = ConverterControlType.Pac
        control2 = ConverterControlType.Qac

        # Fixed admittance based on 1 MVA / Ub^2
        ysvs = elmsvs.qmin * elmsvs.nncap + elmsvs.tcrqact + elmsvs.Qfixcap * elmsvs.nfixcap

        # SVS Range
        ymin = elmsvs.qmin * elmsvs.nxcap + elmsvs.Qfixcap * elmsvs.nfixcap
        ymax = elmsvs.tcrmax + elmsvs.Qfixcap * elmsvs.nfixcap
        ysvs = max(min(ysvs, ymax), ymin)

        control1_val = 0.0  # Active power injection of the SVS [MW]
        control2_val = np.abs(1.0 ** 2) * np.conj(ysvs)  # Reactive power injection of the SVS [MVAr]

        rate = max(np.abs(elmsvs.tcrmax), np.abs(elmsvs.qmin))
        kpd = 0.0  # Droop [%]
        u_setpoint = 1.0  # Voltage Setpoint [pu]

    vsc = dev.VSC(
        name=vsc_name,
        idtag=_ref_id(elmsvs.ID),
        active=not bool(elmsvs.outserv),
        bus_from=dc_bus,
        bus_to=ac_bus,
        rate=rate,
        alpha1=0.0,
        alpha2=0.0,
        alpha3=0.0,
        control1=control1,
        control2=control2,
        control1_val=control1_val,
        control2_val=control2_val,
        ysvs=ysvs,
        control2_droop=kpd,
        control2_droop_val=u_setpoint
    )

    return dc_bus, vsc


def convert_dgs_to_controllable_shunt_from_svs(elmsvs: ElmSvs,
                                               stacubic_dict: Dict[str, List[int]],
                                               buses: List[dev.Bus],
                                               logger: Logger,
                                               cubics_by_objid: Dict[str, List[StaCubic]],
                                               bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[
    dev.Bus, dev.ControllableShunt]:
    """
    Convert dgs to controllable shunt from svs.

    :param elmsvs: elmsvs parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    name: str = elmsvs.loc_name or f"ElmSvs_{_ref_id(elmsvs.ID)}"

    bus: dev.Bus = get_injection_bus(elm_id=elmsvs.ID,
                                     stacubic_dict=stacubic_dict,
                                     buses=buses,
                                     cubics_by_objid=cubics_by_objid,
                                     bus_by_term_id=bus_by_term_id)

    bmin: float = float(elmsvs.qmin)
    bmax: float = float(elmsvs.qmax)
    vset: float = float(elmsvs.usetp)
    if elmsvs.i_ctrl == 1 and elmsvs.i_droop == 0 and (
            elmsvs.nxcap != 0 or elmsvs.nfixcap != 0 or elmsvs.tcrmax != 0.0):
        # Reuse the SVS range already calculated by the VSC import route.
        # qmin is one capacitor step, not the whole bank's capacitive capability.
        bmin = elmsvs.qmin * elmsvs.nxcap + elmsvs.Qfixcap * elmsvs.nfixcap
        bmax = elmsvs.tcrmax + elmsvs.Qfixcap * elmsvs.nfixcap
    else:
        pass

    if bmin < 0.0 and bmax > 0.0:
        b_steps: np.ndarray = np.array([bmin, -bmin, bmax], dtype=float)
        initial_step: int = 1
    elif bmin == bmax:
        b_steps = np.array([bmax], dtype=float)
        initial_step = 0
    else:
        b_steps = np.array([bmin, (bmax - bmin)], dtype=float)
        initial_step = 0

    cshunt: dev.ControllableShunt = dev.ControllableShunt(
        name=name,
        idtag=_ref_id(elmsvs.ID),
        number_of_steps=int(len(b_steps)),
        step=int(initial_step),
        g_per_step=0.0,
        b_per_step=0.0,
        Bmin=bmin,
        Bmax=bmax,
        Gmin=0.0,
        Gmax=0.0,
        active=(elmsvs.outserv == 0),
        vset=vset,
        control_mode=ShuntControlMode.Continuous,
        control_bus=bus
    )

    cshunt.b_steps = b_steps
    cshunt.g_steps = np.zeros(len(b_steps), dtype=float)
    cshunt.active_steps = np.ones(len(b_steps), dtype=int)
    cshunt.step = int(initial_step)
    # ElmSvs susceptances connect AB, BC and CA, including with balanced control.
    cshunt.conn = ShuntConnectionType.Delta

    return bus, cshunt


def _pf_from_pq(p_mw: float, q_mvar: float, default: float = 0.8) -> float:
    """
    Pf from pq.

    :param p_mw: p_mw parameter.
    :param q_mvar: q_mvar parameter.
    :param default: default parameter.
    :return: Function result.
    """
    s = math.sqrt(p_mw * p_mw + q_mvar * q_mvar)
    if s <= 0.0:
        return default
    pf = abs(p_mw) / s
    return max(0.0, min(1.0, pf))


def _interpret_pu_limit(value: float,
                        baseMVA: float,
                        reference_abs: float,
                        logger: Logger,
                        name: str,
                        field: str) -> float:
    """
    Interpret pu limit.

    :param value: value parameter.
    :param baseMVA: baseMVA parameter.
    :param reference_abs: reference_abs parameter.
    :param logger: logger parameter.
    :param name: name parameter.
    :param field: field parameter.
    :return: Function result.
    """
    v = value

    # If reference is small too, do not guess
    if abs(reference_abs) <= 5.0:
        return v

    # Heuristic: if |value| is small while reference magnitude is clearly in MW/MVAr,
    # then it is very likely a p.u. value and we scale by baseMVA.
    if abs(v) <= 5.0 and baseMVA > 0.0:
        logger.add_warning(
            f"Interpreting set point as not in p.u.",
            device=name,
            device_class="Generator",
            value=v * baseMVA
        )

        return v * baseMVA

    return v


def convert_dgs_to_generator(elmsym: ElmSym,
                             stacubic_dict: Dict[str, List[int]],
                             buses: List[dev.Bus],
                             typsym_dict: Dict[str, TypSym],
                             baseMVA: float,
                             logger: Logger,
                             cubics_by_objid: Dict[str, List[StaCubic]],
                             bus_by_term_id: Dict[str, dev.Bus],
                             parallel_index: int = 0,
                             parallel_count: int = 1) -> Tuple[dev.Bus, dev.Generator]:
    """
    Convert dgs to generator.

    :param elmsym: elmsym parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param typsym_dict: typsym_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """
    name = _get_non_empty_name(elmsym.loc_name, f"Gen_{_ref_id(elmsym.ID)}")
    name = _get_parallel_device_name(name, parallel_index, parallel_count)
    generator_idtag = _get_parallel_device_idtag(_ref_id(elmsym.ID), parallel_index, parallel_count)

    bus = get_injection_bus(elm_id=elmsym.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    # Slack/reference machine indicator (PowerFactory exports ip_ctrl=1 on the slack generator)
    if int(elmsym.ip_ctrl) == 1:
        bus.set_is_slack_at(t=None, val=True)

    # Resolve type
    typsym = typsym_dict.get(elmsym.typ_id, None)
    if typsym is None:
        typsym = typsym_dict.get(_ref_id(elmsym.typ_id), None)

    p_mw = float(elmsym.pgini)
    q_mvar = float(elmsym.qgini)

    # Voltage control
    vset = elmsym.usetp

    if elmsym.av_mode != "":
        if elmsym.av_mode == "constv":
            control_mode = GeneratorControlMode.V
        else:
            control_mode = GeneratorControlMode.Q
    else:
        if elmsym.iv_mode != 0:
            control_mode = GeneratorControlMode.V
        else:
            control_mode = GeneratorControlMode.Q

    # Power factor (used mainly when not controlled)
    pf = elmsym.cosgini
    if pf == 0.0 and typsym is not None:
        pf = typsym.cosn
    if pf == 0.0:
        pf = _pf_from_pq(p_mw=p_mw, q_mvar=q_mvar, default=0.8)

    # Nominal power
    snom = 9999.0
    if typsym is not None:
        snom = float(typsym.sgn)
    else:
        pass

    # Limits (q_min/q_max are often in p.u. on Sbase in DGS exports)
    qmin_raw = float(elmsym.q_min)
    qmax_raw = float(elmsym.q_max)
    if qmin_raw == 0.0 and typsym is not None:
        qmin_raw = float(typsym.q_min)
    else:
        pass
    if qmax_raw == 0.0 and typsym is not None:
        qmax_raw = float(typsym.q_max)
    else:
        pass

    qmin = _interpret_pu_limit(value=qmin_raw, baseMVA=baseMVA, reference_abs=abs(q_mvar),
                               logger=logger, name=name, field="q_min")
    qmax = _interpret_pu_limit(value=qmax_raw, baseMVA=baseMVA, reference_abs=abs(q_mvar),
                               logger=logger, name=name, field="q_max")

    # Optional P limits if present in schema
    pmin = float(elmsym.Pmin_uc)
    pmax = float(elmsym.Pmax_uc)

    # Interpret P limits if they look like p.u. too
    pmin = _interpret_pu_limit(value=pmin, baseMVA=baseMVA, reference_abs=abs(p_mw),
                               logger=logger, name=name, field="Pmin_uc")
    pmax = _interpret_pu_limit(value=pmax, baseMVA=baseMVA, reference_abs=abs(p_mw),
                               logger=logger, name=name, field="Pmax_uc")

    gen = dev.Generator(name=name,
                        idtag=generator_idtag,
                        P=p_mw,
                        Q=q_mvar,
                        power_factor=pf,
                        vset=vset,
                        control_mode=control_mode,
                        Qmin=qmin,
                        Qmax=qmax,
                        Snom=snom,
                        active=(elmsym.outserv == 0),
                        Pmin=pmin,
                        Pmax=pmax,
                        Sbase=baseMVA)

    # Optional sequence data from type (best-effort, may not exist in all exports)
    if typsym is not None:
        r1 = typsym.rstr * baseMVA / snom
        x1 = typsym.xstr * baseMVA / snom

        if r1 != 0.0 or x1 != 0.0:
            gen.R1 = float(r1)
            gen.X1 = float(x1)
        else:
            pass

        if float(typsym.r0sy) != 0.0 or float(typsym.x0sy) != 0.0:
            gen.R0 = float(typsym.r0sy)
            gen.X0 = float(typsym.x0sy)
        else:
            pass

        if float(typsym.r2sy) != 0.0 or float(typsym.x2sy) != 0.0:
            gen.R2 = float(typsym.r2sy)
            gen.X2 = float(typsym.x2sy)
        else:
            pass

    return bus, gen


def convert_dgs_to_asm_generator(elmasm: ElmAsm,
                                 stacubic_dict: Dict[str, List[int]],
                                 buses: List[dev.Bus],
                                 typasmo_dict: Dict[str, TypAsmo],
                                 logger: Logger,
                                 cubics_by_objid: Dict[str, List[StaCubic]],
                                 bus_by_term_id: Dict[str, dev.Bus],
                                 parallel_index: int = 0,
                                 parallel_count: int = 1) -> Tuple[dev.Bus, dev.Generator]:
    """
    Convert dgs to asm generator.

    :param elmasm: elmasm parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param buses: buses parameter.
    :param typasmo_dict: typasmo_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param parallel_index: parallel_index parameter.
    :param parallel_count: parallel_count parameter.
    :return: Function result.
    """

    name = _get_non_empty_name(elmasm.loc_name, f"ElmAsm_{_ref_id(elmasm.ID)}")
    name = _get_parallel_device_name(name, parallel_index, parallel_count)
    generator_idtag = _get_parallel_device_idtag(_ref_id(elmasm.ID), parallel_index, parallel_count)

    # Bus resolution must be StaCubic-based (PowerFactory connectivity)
    bus = get_injection_bus(elm_id=elmasm.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    if elmasm.i_mot == 0:  # Check that the asynchronous machine is a Generator

        if elmasm.idfig == 0:  # Also check that it is a Standard Asynchronous Machine

            if elmasm.bustp == 'AS' and elmasm.pmode == 0:  # Finally, check the bus type and the power input mode

                P: float = float(elmasm.pgini)  # AG active power P

                typasmo: TypAsmo | None = typasmo_dict.get(elmasm.typ_id, None)  # AG type

                if typasmo is not None:

                    Sr = float(typasmo.sgn) * 1e-3  # Rated apparent power [MVA]
                    Rs = float(typasmo.rstr)  # Stator resistance [pu]
                    Xs = float(typasmo.xstr)  # Stator reactance [pu]
                    Xm = float(typasmo.xm)  # Magnetising reactance [pu]
                    Rr = float(typasmo.rrtrA)  # Rotor resistance [pu]
                    Xr = float(typasmo.xrtrA)  # Rotor reactance [pu]

                    gen = dev.Generator(name=name,
                                        idtag=generator_idtag,
                                        P=P,
                                        power_factor=1.0,
                                        control_mode=GeneratorControlMode.Q,
                                        Snom=Sr,
                                        active=(elmasm.outserv == 0),
                                        Rs=Rs,
                                        Xs=Xs,
                                        Xm=Xm,
                                        Rr=Rr,
                                        Xr=Xr,
                                        tpe=GeneratorType.Asynchronous)

                    # TypAsmo nslty is D:Y:YN. Do not give a delta machine the
                    # default grounded-star homopolar path of a generic generator.
                    if typasmo.nslty == 0:
                        gen.conn = ShuntConnectionType.Delta
                    elif typasmo.nslty == 1:
                        gen.conn = ShuntConnectionType.FloatingStar
                    else:
                        gen.conn = ShuntConnectionType.NeutralStar
                        logger.add_warning('Asynchronous YN import requires explicit neutral/grounding data for ABC',
                                           device=name, device_class='ElmAsm')

                else:
                    logger.add_warning(
                        msg=f"The Asynchronous Generator does not have an assigned type (TypAsmo).",
                        device=name,
                        device_class="ElmAsm",
                        value=typasmo
                    )

                    gen = dev.Generator(name=name,
                                        idtag=generator_idtag,
                                        P=P,
                                        power_factor=1.0,
                                        control_mode=GeneratorControlMode.Q,
                                        Snom=P,
                                        active=(elmasm.outserv == 0),
                                        tpe=GeneratorType.Asynchronous)

            else:
                logger.add_warning(
                    msg=f"Bus type is not AS or the input mode is not Electrical power.",
                    device=name,
                    device_class="ElmAsm",
                    value=elmasm.bustp
                )

                gen = dev.Generator(name=name,
                                    idtag=generator_idtag,
                                    P=0.0,
                                    power_factor=1.0,
                                    control_mode=GeneratorControlMode.Q,
                                    active=(elmasm.outserv == 0),
                                    tpe=GeneratorType.Asynchronous)

        else:
            logger.add_warning(
                msg=f"The AG is not an Standard Asynchronous Machine.",
                device=name,
                device_class="ElmAsm",
                value=elmasm.idfig
            )

            gen = dev.Generator(name=name,
                                idtag=generator_idtag,
                                P=0.0,
                                power_factor=1.0,
                                control_mode=GeneratorControlMode.Q,
                                active=(elmasm.outserv == 0),
                                tpe=GeneratorType.Asynchronous)

    else:
        logger.add_warning(
            msg=f"The asynchronous machine is not a generator, is a motor!",
            device=name,
            device_class="ElmAsm",
            value=elmasm.i_mot
        )

        gen = dev.Generator(name=name,
                            idtag=generator_idtag,
                            P=0.0,
                            power_factor=1.0,
                            control_mode=GeneratorControlMode.Q,
                            active=(elmasm.outserv == 0),
                            tpe=GeneratorType.Asynchronous)

    return bus, gen


def _add_elmsym_generators(dgs_grid: DgsCircuit,
                           grid: dev.MultiCircuit,
                           stacubic_dict: Dict[str, List[int]],
                           typsym_dict: Dict[str, TypSym],
                           baseMVA: float,
                           logger: Logger,
                           cubics_by_objid: Dict[str, List[StaCubic]],
                           bus_by_term_id: Dict[str, dev.Bus]) -> None:
    """
    Add elmsym generators.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typsym_dict: typsym_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    for elmsym in dgs_grid.elmsyms:
        parallel_count = _get_parallel_device_count(count=int(elmsym.ngnum))
        for parallel_index in range(parallel_count):
            bus, gen = convert_dgs_to_generator(
                elmsym=elmsym,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                typsym_dict=typsym_dict,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count
            )
            grid.add_generator(bus=bus, api_obj=gen)


def _add_elmasm_generators(dgs_grid: DgsCircuit,
                           grid: dev.MultiCircuit,
                           stacubic_dict: Dict[str, List[int]],
                           typasmo_dict: Dict[str, TypAsmo],
                           logger: Logger,
                           cubics_by_objid: Dict[str, List[StaCubic]],
                           bus_by_term_id: Dict[str, dev.Bus]) -> None:
    """
    Add elmasm generators.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typasmo_dict: typasmo_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    for elmasm in dgs_grid.elmasms:
        parallel_count = _get_parallel_device_count(count=int(elmasm.ngnum))
        for parallel_index in range(parallel_count):
            bus, gen = convert_dgs_to_asm_generator(
                elmasm=elmasm,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                typasmo_dict=typasmo_dict,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count
            )
            grid.add_generator(bus=bus, api_obj=gen)


def _add_elmvac_loads(dgs_grid: DgsCircuit,
                      grid: dev.MultiCircuit,
                      stacubic_dict: Dict[str, List[int]],
                      logger: Logger,
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus]) -> None:
    """
    Add elmvac loads.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    for elmvac in dgs_grid.elmvacs:
        if elmvac.itype == 2:
            bus, load = convert_dgs_ward_equivalent_to_load(
                elmvac=elmvac,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id
            )
            grid.add_load(bus=bus, api_obj=load)


def _add_elmlod_loads(dgs_grid: DgsCircuit,
                      grid: dev.MultiCircuit,
                      stacubic_dict: Dict[str, List[int]],
                      logger: Logger,
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus],
                      phase_map: PhaseMap) -> None:
    """
    Add elmlod loads.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param phase_map: Resolved terminal-conductor phase map.
    :return: Function result.
    """
    comldf = dgs_grid.comldfs[0] if len(dgs_grid.comldfs) > 0 else None

    typlod_by_id: Dict[str, TypLod] = dict()
    for typlod in dgs_grid.typlods:
        typlod_by_id[typlod.ID] = typlod
        typlod_id = _ref_id(typlod.ID)
        if typlod_id is not None:
            typlod_by_id[typlod_id] = typlod

    for elmlod in dgs_grid.elmlods:
        typlod = _resolve_pointer_dict_value(key=elmlod.typ_id, mapping=typlod_by_id)
        bus, load = convert_dgs_to_load(
            elmlod=elmlod,
            stacubic_dict=stacubic_dict,
            buses=grid.buses,
            logger=logger,
            cubics_by_objid=cubics_by_objid,
            bus_by_term_id=bus_by_term_id,
            phase_map=phase_map,
            comldf=comldf,
            typlod=typlod,
        )
        grid.add_load(bus=bus, api_obj=load)


# Alex review required: convert native losses exactly once into the canonical VSC model.
def _get_powerfactory_vsc_loss_coefficients(
        source: ElmVsc | ElmVscmono,
        system_base_mva: float,
) -> Tuple[float, float, float]:
    """Convert native converter loss data to VeraGrid's per-unit polynomial.

    PowerFactory stores the configured loss parameters independently from its
    solved ``m:*`` outputs. Only the configured parameters enter this mapping.

    :param source: Native monopolar or three-terminal converter row.
    :param system_base_mva: VeraGrid system power base in MVA.
    :return: Idle, linear-current and quadratic-current loss coefficients.
    """
    if system_base_mva > 0.0:
        alpha1: float = float(source.Pnold) / (1000.0 * system_base_mva)
    else:
        alpha1 = 0.0

    nominal_voltage_kv: float = abs(float(source.Unom))
    switching_loss_factor: float = (
        0.0 if source.swtLossFactor is None else float(source.swtLossFactor)
    )
    resistive_loss_factor: float = (
        0.0 if source.resLossFactor is None else float(source.resLossFactor)
    )
    if nominal_voltage_kv > 0.0:
        alpha2: float = switching_loss_factor / (
                math.sqrt(3.0) * nominal_voltage_kv
        )
        alpha3: float = (
                resistive_loss_factor
                * system_base_mva
                / (3.0 * nominal_voltage_kv * nominal_voltage_kv)
        )
    else:
        alpha2 = 0.0
        alpha3 = 0.0

    rated_power_mva: float = (
        0.0 if source.Snom is None else abs(float(source.Snom))
    )
    copper_loss_kw: float = 0.0 if source.Pcu is None else float(source.Pcu)
    if rated_power_mva > 0.0 and system_base_mva > 0.0:
        alpha3 += (
                copper_loss_kw
                * system_base_mva
                / (1000.0 * rated_power_mva * rated_power_mva)
        )
    else:
        pass

    arm_resistance_ohm: float = (
        0.0 if source.Rarm is None else max(float(source.Rarm), 0.0)
    )
    if (
            isinstance(source, ElmVsc)
            and nominal_voltage_kv > 0.0
            and system_base_mva > 0.0
            and arm_resistance_ohm > 0.0
    ):
        alpha3 += (
                arm_resistance_ohm
                * system_base_mva
                / (2.0 * nominal_voltage_kv * nominal_voltage_kv)
        )
    else:
        pass
    return alpha1, alpha2, alpha3


# Dynamic contract: collapse Pcu/uk/Rarm/Larm without duplicating adapter impedance.
def _get_powerfactory_vsc_series_impedance(
        source: ElmVsc | ElmVscmono,
        frequency_hz: float,
) -> Tuple[float, float]:
    """Convert configured converter-reactor data to per unit.

    :param source: Native monopolar or three-terminal converter row.
    :param frequency_hz: Network nominal frequency in Hz.
    :return: Series resistance and reactance on the converter power base.
    """
    rated_power_mva: float = (
        0.0 if source.Snom is None else abs(float(source.Snom))
    )
    copper_loss_kw: float = (
        0.0 if source.Pcu is None else max(float(source.Pcu), 0.0)
    )
    impedance_magnitude_pu: float = (
        0.0 if source.uk is None else max(float(source.uk) / 100.0, 0.0)
    )
    if rated_power_mva > 0.0:
        resistance_pu: float = copper_loss_kw / (1000.0 * rated_power_mva)
    else:
        resistance_pu = 0.0
    reactance_squared: float = max(
        impedance_magnitude_pu * impedance_magnitude_pu
        - resistance_pu * resistance_pu,
        0.0,
    )
    reactance_pu: float = math.sqrt(reactance_squared)

    arm_resistance_ohm: float = (
        0.0 if source.Rarm is None else max(float(source.Rarm), 0.0)
    )
    arm_inductance_mh: float = (
        0.0 if source.Larm is None else max(float(source.Larm), 0.0)
    )
    nominal_voltage_kv: float = abs(float(source.Unom))
    if (
            isinstance(source, ElmVsc)
            and rated_power_mva > 0.0
            and nominal_voltage_kv > 0.0
            and frequency_hz > 0.0
            and (arm_resistance_ohm > 0.0 or arm_inductance_mh > 0.0)
    ):
        impedance_base_ohm: float = (
                nominal_voltage_kv * nominal_voltage_kv / rated_power_mva
        )
        resistance_pu += arm_resistance_ohm / (2.0 * impedance_base_ohm)
        reactance_pu += (
                2.0
                * math.pi
                * frequency_hz
                * arm_inductance_mh
                * 1.0e-3
                / (2.0 * impedance_base_ohm)
        )
    else:
        pass
    return resistance_pu, reactance_pu


# Dynamic contract: store Cmod/Nsm, the MMC quantity consumed by the adapter.
def _get_powerfactory_mmc_arm_capacitance_uf(
        source: ElmVsc | ElmVscmono,
) -> float:
    """Return the equivalent capacitance of one MMC arm.

    PowerFactory exports the capacitance of one submodule and the number of
    series submodules per arm.  Every downstream physical representation uses
    only their quotient, so the source pair is reduced before the transient
    DGS row is discarded.

    :param source: Native monopolar or three-terminal converter row.
    :return: Equivalent arm capacitance in microfarads, or zero when incomplete.
    """
    # Normalize the physical source value without inventing missing equipment data.
    submodule_capacitance_uf: float = (
        0.0 if source.mmcCmod is None else max(float(source.mmcCmod), 0.0)
    )
    # Prefer the current PowerFactory field while retaining declarative legacy compatibility.
    if source.NmmcSM is None:
        if source.MmmcSM is None:
            submodules_per_arm: int = 0
        else:
            submodules_per_arm = max(int(source.MmmcSM), 0)
    else:
        submodules_per_arm = max(int(source.NmmcSM), 0)
    # Reduce the pair only when both native values establish a physical capacitance.
    if submodule_capacitance_uf > 0.0 and submodules_per_arm > 0:
        arm_capacitance_uf: float = (
                submodule_capacitance_uf / float(submodules_per_arm)
        )
    else:
        arm_capacitance_uf = 0.0
    return arm_capacitance_uf


def _get_powerfactory_dc_link_capacitance_uf(
        source: ElmVsc | ElmVscmono,
) -> float:
    """Return the capacitance owned directly by the native DC terminals.

    A two-level converter uses ``Cdc``. MMC rows may still export a stale
    ``Cdc`` value, so their arm capacitance remains owned by the separate MMC
    field and is never interpreted as a terminal capacitor here.

    :param source: Native PowerFactory converter row.
    :return: Applicable two-level DC-link capacitance in microfarads.
    """
    source_type_value: int | None = source.vsctype
    source_type: PowerFactoryVscType | None
    if source_type_value == int(PowerFactoryVscType.TwoLevel):
        source_type = PowerFactoryVscType.TwoLevel
    elif source_type_value == int(PowerFactoryVscType.HalfBridgeMmc):
        source_type = PowerFactoryVscType.HalfBridgeMmc
    elif source_type_value == int(PowerFactoryVscType.FullBridgeMmc):
        source_type = PowerFactoryVscType.FullBridgeMmc
    else:
        source_type = None

    configured_capacitance_uf: float = (
        0.0 if source.Cdc is None else max(float(source.Cdc), 0.0)
    )
    if source_type is PowerFactoryVscType.TwoLevel:
        dc_link_capacitance_uf: float = configured_capacitance_uf
    else:
        dc_link_capacitance_uf = 0.0
    return dc_link_capacitance_uf


# Alex review required: map configured setpoints only; solved m:* values never control the VSC.
def _get_native_vsc_controls(
        source: ElmVsc | ElmVscmono,
        logger: Logger,
) -> Tuple[ConverterControlType, float, ConverterControlType, float, bool]:
    """Translate one configured PowerFactory VSC control pair.

    Solved ``m:*`` values are deliberately excluded. They are optional oracle
    evidence for validation and never replace configured control targets.

    :param source: Parsed monopolar or three-terminal converter row.
    :param logger: Import diagnostic sink.
    :return: Two control modes, their configured targets and exactness flag.
    """
    mode: int = int(source.i_acdc)
    # PowerFactory equipment setpoints are positive when injected into the AC
    # bus. VeraGrid VSC terminal powers are positive from the bus into the
    # converter, so configured AC power targets cross the boundary negated.
    active_power_target: float = -float(source.psetp)
    reactive_power_target: float = -float(source.qsetp)
    if source.usetpdc is None:
        dc_voltage_target: float = float(source.usetp)
    else:
        dc_voltage_target = float(source.usetpdc)
    ac_voltage_target: float = float(source.usetp)

    if mode == 3:
        control1: ConverterControlType = ConverterControlType.Vm_dc
        control1_value: float = dc_voltage_target
        control2: ConverterControlType = ConverterControlType.Qac
        control2_value: float = reactive_power_target
        is_exact: bool = True
    elif mode == 4:
        control1 = ConverterControlType.Pac
        control1_value = active_power_target
        control2 = ConverterControlType.Vm_ac
        control2_value = ac_voltage_target
        is_exact = True
    elif mode == 5:
        control1 = ConverterControlType.Pac
        control1_value = active_power_target
        control2 = ConverterControlType.Qac
        control2_value = reactive_power_target
        is_exact = True
    elif mode == 6:
        control1 = ConverterControlType.Vm_dc
        control1_value = dc_voltage_target
        control2 = ConverterControlType.Vm_ac
        control2_value = ac_voltage_target
        is_exact = True
    else:
        control1 = ConverterControlType.Pac
        control1_value = active_power_target
        control2 = ConverterControlType.Qac
        control2_value = reactive_power_target
        is_exact = False
        logger.add_warning(
            msg="Native VSC control pair is not represented exactly; converter kept inactive",
            device=source.loc_name,
            device_class=source.element_type,
            value=f"i_acdc={mode}",
        )
    return control1, control1_value, control2, control2_value, is_exact


# Alex review required: build the final three-phase VSC directly from its FID and cubicles.
def convert_dgs_to_vsc(
        elmvsc: ElmVsc,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        switch_by_cubic_id: Dict[str, StaSwitch],
        system_base_mva: float,
        frequency_hz: float,
        logger: Logger,
) -> dev.VSC | None:
    """Convert one native three-terminal PowerFactory converter.

    Cubicle role zero is AC, role one is DC positive and role two is DC
    negative. Duplicate or unresolved required roles fail closed.

    :param elmvsc: Source converter row.
    :param cubics_by_objid: Cubicles grouped by converter FID.
    :param bus_by_term_id: Imported buses keyed by terminal FID.
    :param switch_by_cubic_id: Cubicle switches keyed by cubicle FID.
    :param system_base_mva: VeraGrid system power base in MVA.
    :param frequency_hz: Network nominal frequency in Hz.
    :param logger: Import diagnostic sink.
    :return: Final VSC, or ``None`` when required topology is unresolved.
    """
    converter_id: str | None = _ref_id(elmvsc.ID)
    if converter_id is None or converter_id == "":
        converter_cubics: List[StaCubic] = list()
    else:
        converter_cubics = cubics_by_objid.get(converter_id, list())

    ac_bus: dev.Bus | None = None
    dc_positive_bus: dev.Bus | None = None
    dc_negative_bus: dev.Bus | None = None
    duplicate_role: bool = False
    invalid_cubicle: bool = False
    cubic: StaCubic
    for cubic in converter_cubics:
        terminal_id: str | None = _ref_id(cubic.fold_id)
        if terminal_id is None or terminal_id == "":
            terminal_bus: dev.Bus | None = None
        else:
            terminal_bus = bus_by_term_id.get(terminal_id, None)
        terminal_role: int = int(cubic.obj_bus)
        if terminal_bus is None:
            invalid_cubicle = True
        elif terminal_role == 0:
            if ac_bus is None:
                ac_bus = terminal_bus
            else:
                duplicate_role = True
        elif terminal_role == 1:
            if dc_positive_bus is None:
                dc_positive_bus = terminal_bus
            else:
                duplicate_role = True
        elif terminal_role == 2:
            if dc_negative_bus is None:
                dc_negative_bus = terminal_bus
            else:
                duplicate_role = True
        else:
            invalid_cubicle = True

    topology_is_complete: bool = bool(
        ac_bus is not None
        and dc_positive_bus is not None
        and dc_negative_bus is not None
        and not duplicate_role
        and not invalid_cubicle
        and len(converter_cubics) == 3
    )
    if not topology_is_complete:
        logger.add_warning(
            msg=(
                "ElmVsc skipped because AC/DC+/DC- cubicles are incomplete, "
                "unexpected or ambiguous"
            ),
            device=elmvsc.loc_name,
            device_class="ElmVsc",
        )
        converter: dev.VSC | None = None
    else:
        dc_positive_bus.is_dc = True
        dc_negative_bus.is_dc = True
        control1: ConverterControlType
        control1_value: float
        control2: ConverterControlType
        control2_value: float
        control_is_exact: bool
        control1, control1_value, control2, control2_value, control_is_exact = (
            _get_native_vsc_controls(source=elmvsc, logger=logger)
        )
        converter_active: bool = bool(
            not bool(elmvsc.outserv)
            and control_is_exact
            and _is_element_closed_by_cubicle_switches(
                element_id=elmvsc.ID,
                cubics_by_objid=cubics_by_objid,
                switch_by_cubic_id=switch_by_cubic_id,
            )
        )
        rated_power_mva: float = (
            0.0 if elmvsc.Snom is None else abs(float(elmvsc.Snom))
        )
        converter_rate: float = max(
            abs(float(elmvsc.P_max)),
            rated_power_mva,
            math.hypot(float(elmvsc.psetp), float(elmvsc.qsetp)),
            1.0,
        )
        alpha1: float
        alpha2: float
        alpha3: float
        alpha1, alpha2, alpha3 = _get_powerfactory_vsc_loss_coefficients(
            source=elmvsc,
            system_base_mva=system_base_mva,
        )
        resistance_pu: float
        reactance_pu: float
        resistance_pu, reactance_pu = _get_powerfactory_vsc_series_impedance(
            source=elmvsc,
            frequency_hz=frequency_hz,
        )
        converter = dev.VSC(
            name=_get_non_empty_name(
                name=elmvsc.loc_name,
                default_value=f"VSC_{converter_id}",
            ),
            idtag=converter_id,
            code=elmvsc.for_name,
            active=converter_active,
            bus_from=dc_positive_bus,
            bus_to=ac_bus,
            bus_dc_n=dc_negative_bus,
            design_rate=converter_rate,
            rate=converter_rate,
            alpha1=alpha1,
            alpha2=alpha2,
            alpha3=alpha3,
            r_series=resistance_pu,
            x_series=reactance_pu,
            dc_voltage_base=(
                0.0 if elmvsc.Unomdc is None else float(elmvsc.Unomdc)
            ),
            dc_link_capacitance_uf=(
                _get_powerfactory_dc_link_capacitance_uf(source=elmvsc)
            ),
            mmc_arm_capacitance_uf=(
                _get_powerfactory_mmc_arm_capacitance_uf(source=elmvsc)
            ),
            mmc_consider_arm_reactor_dc=(
                False if elmvsc.iZarmDCside is None else bool(elmvsc.iZarmDCside)
            ),
            control1=control1,
            control1_val=control1_value,
            control2=control2,
            control2_val=control2_value,
        )
    return converter


# Alex review required: build the final monopolar VSC directly from its FID and cubicles.
def convert_dgs_to_monopolar_vsc(
        source: ElmVscmono,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        switch_by_cubic_id: Dict[str, StaSwitch],
        system_base_mva: float,
        frequency_hz: float,
        logger: Logger,
) -> dev.VSC | None:
    """Convert one native two-terminal PowerFactory converter.

    :param source: Source monopolar converter row.
    :param cubics_by_objid: Cubicles grouped by converter FID.
    :param bus_by_term_id: Imported buses keyed by terminal FID.
    :param switch_by_cubic_id: Cubicle switches keyed by cubicle FID.
    :param system_base_mva: VeraGrid system power base in MVA.
    :param frequency_hz: Network nominal frequency in Hz.
    :param logger: Import diagnostic sink.
    :return: Final VSC, or ``None`` when required topology is unresolved.
    """
    source_id: str | None = _ref_id(source.ID)
    if source_id is None or source_id == "":
        source_cubics: List[StaCubic] = list()
    else:
        source_cubics = cubics_by_objid.get(source_id, list())

    ac_bus: dev.Bus | None = None
    dc_bus: dev.Bus | None = None
    duplicate_role: bool = False
    invalid_cubicle: bool = False
    cubic: StaCubic
    for cubic in source_cubics:
        terminal_id: str | None = _ref_id(cubic.fold_id)
        if terminal_id is None or terminal_id == "":
            terminal_bus: dev.Bus | None = None
        else:
            terminal_bus = bus_by_term_id.get(terminal_id, None)
        terminal_role: int = int(cubic.obj_bus)
        if terminal_bus is None:
            invalid_cubicle = True
        elif terminal_role == 0:
            if ac_bus is None:
                ac_bus = terminal_bus
            else:
                duplicate_role = True
        elif terminal_role == 1:
            if dc_bus is None:
                dc_bus = terminal_bus
            else:
                duplicate_role = True
        else:
            invalid_cubicle = True

    topology_is_complete: bool = bool(
        ac_bus is not None
        and dc_bus is not None
        and not duplicate_role
        and not invalid_cubicle
        and len(source_cubics) == 2
    )
    if not topology_is_complete:
        logger.add_warning(
            msg=(
                "ElmVscmono skipped because AC/DC cubicles are incomplete, "
                "unexpected or ambiguous"
            ),
            device=source.loc_name,
            device_class="ElmVscmono",
        )
        converter: dev.VSC | None = None
    else:
        dc_bus.is_dc = True
        control1: ConverterControlType
        control1_value: float
        control2: ConverterControlType
        control2_value: float
        control_is_exact: bool
        control1, control1_value, control2, control2_value, control_is_exact = (
            _get_native_vsc_controls(source=source, logger=logger)
        )
        converter_active: bool = bool(
            not bool(source.outserv)
            and control_is_exact
            and _is_element_closed_by_cubicle_switches(
                element_id=source.ID,
                cubics_by_objid=cubics_by_objid,
                switch_by_cubic_id=switch_by_cubic_id,
            )
        )
        converter_rate: float = max(
            abs(float(source.P_max)),
            0.0 if source.Snom is None else abs(float(source.Snom)),
            math.hypot(float(source.psetp), float(source.qsetp)),
            1.0,
        )
        alpha1: float
        alpha2: float
        alpha3: float
        alpha1, alpha2, alpha3 = _get_powerfactory_vsc_loss_coefficients(
            source=source,
            system_base_mva=system_base_mva,
        )
        resistance_pu: float
        reactance_pu: float
        resistance_pu, reactance_pu = _get_powerfactory_vsc_series_impedance(
            source=source,
            frequency_hz=frequency_hz,
        )
        converter = dev.VSC(
            name=_get_non_empty_name(
                name=source.loc_name,
                default_value=f"VSC_MONO_{source_id}",
            ),
            idtag=source_id,
            code=source.for_name,
            active=converter_active,
            bus_from=dc_bus,
            bus_to=ac_bus,
            bus_dc_n=None,
            design_rate=converter_rate,
            rate=converter_rate,
            alpha1=alpha1,
            alpha2=alpha2,
            alpha3=alpha3,
            r_series=resistance_pu,
            x_series=reactance_pu,
            dc_voltage_base=(
                0.0 if source.Unomdc is None else float(source.Unomdc)
            ),
            dc_link_capacitance_uf=(
                _get_powerfactory_dc_link_capacitance_uf(source=source)
            ),
            mmc_arm_capacitance_uf=(
                _get_powerfactory_mmc_arm_capacitance_uf(source=source)
            ),
            mmc_consider_arm_reactor_dc=(
                False if source.iZarmDCside is None else bool(source.iZarmDCside)
            ),
            control1=control1,
            control1_val=control1_value,
            control2=control2,
            control2_val=control2_value,
        )
    return converter


# Alex review required: register already-canonical three-phase VSC devices in MultiCircuit.
def _add_elmvsc_devices(
        dgs_grid: DgsCircuit,
        grid: dev.MultiCircuit,
        logger: Logger,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        switch_by_cubic_id: Dict[str, StaSwitch],
        frequency_hz: float,
) -> None:
    """Add every structurally valid native three-terminal converter.

    :param dgs_grid: Parsed DGS circuit.
    :param grid: Target VeraGrid circuit.
    :param logger: Import diagnostic sink.
    :param cubics_by_objid: Cubicles grouped by source object FID.
    :param bus_by_term_id: Imported buses keyed by terminal FID.
    :param switch_by_cubic_id: Cubicle switches keyed by cubicle FID.
    :param frequency_hz: Network nominal frequency in Hz.
    :return: None.
    """
    elmvsc: ElmVsc
    for elmvsc in dgs_grid.elmvscs:
        converter: dev.VSC | None = convert_dgs_to_vsc(
            elmvsc=elmvsc,
            cubics_by_objid=cubics_by_objid,
            bus_by_term_id=bus_by_term_id,
            switch_by_cubic_id=switch_by_cubic_id,
            system_base_mva=float(grid.Sbase),
            frequency_hz=frequency_hz,
            logger=logger,
        )
        if converter is None:
            pass
        else:
            grid.add_vsc(obj=converter)


# Alex review required: register already-canonical monopolar VSC devices in MultiCircuit.
def _add_elmvscmono_devices(
        dgs_grid: DgsCircuit,
        grid: dev.MultiCircuit,
        logger: Logger,
        cubics_by_objid: Dict[str, List[StaCubic]],
        bus_by_term_id: Dict[str, dev.Bus],
        switch_by_cubic_id: Dict[str, StaSwitch],
        frequency_hz: float,
) -> None:
    """Add every structurally valid native monopolar converter.

    :param dgs_grid: Parsed DGS circuit.
    :param grid: Target VeraGrid circuit.
    :param logger: Import diagnostic sink.
    :param cubics_by_objid: Cubicles grouped by source object FID.
    :param bus_by_term_id: Imported buses keyed by terminal FID.
    :param switch_by_cubic_id: Cubicle switches keyed by cubicle FID.
    :param frequency_hz: Network nominal frequency in Hz.
    :return: None.
    """
    source: ElmVscmono
    for source in dgs_grid.elmvscmonos:
        converter: dev.VSC | None = convert_dgs_to_monopolar_vsc(
            source=source,
            cubics_by_objid=cubics_by_objid,
            bus_by_term_id=bus_by_term_id,
            switch_by_cubic_id=switch_by_cubic_id,
            system_base_mva=float(grid.Sbase),
            frequency_hz=frequency_hz,
            logger=logger,
        )
        if converter is None:
            pass
        else:
            grid.add_vsc(obj=converter)


def _add_elmgenstat_devices(dgs_grid: DgsCircuit,
                            grid: dev.MultiCircuit,
                            stacubic_dict: Dict[str, List[int]],
                            use_vsc_for_injections: bool,
                            logger: Logger,
                            cubics_by_objid: Dict[str, List[StaCubic]],
                            bus_by_term_id: Dict[str, dev.Bus]) -> None:
    """
    Add elmgenstat devices.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param use_vsc_for_injections: use_vsc_for_injections parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    for elmgenstat in dgs_grid.elmgenstats:
        parallel_count = _get_parallel_device_count(count=int(elmgenstat.ngnum))
        for parallel_index in range(parallel_count):
            # Without explicit VSC import, voltage-controlled wind units use the PV path below.
            if (elmgenstat.cCategory == 'Wind' and not bool(elmgenstat.outserv)
                    and (use_vsc_for_injections or elmgenstat.av_mode != 'constv')):
                if use_vsc_for_injections:
                    dc_bus, vsc = convert_dgs_staticgen_to_vsc(
                        elmgenstat=elmgenstat,
                        stacubic_dict=stacubic_dict,
                        buses=grid.buses,
                        logger=logger,
                        cubics_by_objid=cubics_by_objid,
                        bus_by_term_id=bus_by_term_id,
                        parallel_index=parallel_index,
                        parallel_count=parallel_count
                    )
                    grid.add_bus(dc_bus)
                    grid.add_vsc(vsc)
                else:
                    bus, stagen = convert_dgs_to_static_gen(
                        elmgenstat=elmgenstat,
                        stacubic_dict=stacubic_dict,
                        buses=grid.buses,
                        logger=logger,
                        cubics_by_objid=cubics_by_objid,
                        bus_by_term_id=bus_by_term_id,
                        parallel_index=parallel_index,
                        parallel_count=parallel_count,
                        Sbase=grid.Sbase
                    )
                    grid.add_static_generator(bus=bus, api_obj=stagen)
            elif elmgenstat.cCategory == 'HVDC Terminal':
                bus, gen = convert_dgs_staticgen_to_gen(
                    elmgenstat=elmgenstat,
                    stacubic_dict=stacubic_dict,
                    buses=grid.buses,
                    logger=logger,
                    cubics_by_objid=cubics_by_objid,
                    bus_by_term_id=bus_by_term_id,
                    parallel_index=parallel_index,
                    parallel_count=parallel_count,
                    Sbase=grid.Sbase
                )
                grid.add_generator(bus=bus, api_obj=gen)

            elif elmgenstat.cCategory == 'Storage' and elmgenstat.av_mode == 'constq':
                bus, battery = convert_dgs_staticgen_to_battery(
                    elmgenstat=elmgenstat,
                    stacubic_dict=stacubic_dict,
                    buses=grid.buses,
                    logger=logger,
                    cubics_by_objid=cubics_by_objid,
                    bus_by_term_id=bus_by_term_id,
                    parallel_index=parallel_index,
                    parallel_count=parallel_count,
                    Sbase=grid.Sbase
                )
                grid.add_battery(bus=bus, api_obj=battery)

            elif (elmgenstat.cCategory == 'Storage' and elmgenstat.av_mode == 'vdroop'
                  and use_vsc_for_injections):
                dc_bus, vsc = convert_dgs_staticgen_to_vsc(
                    elmgenstat=elmgenstat,
                    stacubic_dict=stacubic_dict,
                    buses=grid.buses,
                    logger=logger,
                    cubics_by_objid=cubics_by_objid,
                    bus_by_term_id=bus_by_term_id,
                    parallel_index=parallel_index,
                    parallel_count=parallel_count
                )
                grid.add_bus(dc_bus)
                grid.add_vsc(vsc)

            elif elmgenstat.av_mode == 'constv':
                bus, gen = convert_dgs_staticgen_to_gen(
                    elmgenstat=elmgenstat,
                    stacubic_dict=stacubic_dict,
                    buses=grid.buses,
                    logger=logger,
                    cubics_by_objid=cubics_by_objid,
                    bus_by_term_id=bus_by_term_id,
                    parallel_index=parallel_index,
                    parallel_count=parallel_count,
                    Sbase=grid.Sbase
                )
                grid.add_generator(bus=bus, api_obj=gen)
            else:
                bus, stagen = convert_dgs_to_static_gen(
                    elmgenstat=elmgenstat,
                    stacubic_dict=stacubic_dict,
                    buses=grid.buses,
                    logger=logger,
                    cubics_by_objid=cubics_by_objid,
                    bus_by_term_id=bus_by_term_id,
                    parallel_index=parallel_index,
                    parallel_count=parallel_count,
                    Sbase=grid.Sbase
                )
                grid.add_static_generator(bus=bus, api_obj=stagen)


def _add_elmxnet_devices(dgs_grid: DgsCircuit,
                         grid: dev.MultiCircuit,
                         stacubic_dict: Dict[str, List[int]],
                         logger: Logger,
                         cubics_by_objid: Dict[str, List[StaCubic]],
                         bus_by_term_id: Dict[str, dev.Bus]) -> None:
    """
    Add elmxnet devices.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    for elmxnet in dgs_grid.elmxnets:
        short_circuit: bool = True
        if short_circuit:
            bus, gen = convert_dgs_external_grid_to_generator(
                elmxnet=elmxnet,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                Sbase=grid.Sbase,
            )
            grid.add_generator(bus=bus, api_obj=gen)
        else:
            bus, ext_grd = convert_dgs_to_external_grid(
                elmxnet=elmxnet,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id
            )
            grid.add_external_grid(bus=bus, api_obj=ext_grd)


def _add_elmshnt_devices(dgs_grid: DgsCircuit,
                         grid: dev.MultiCircuit,
                         stacubic_dict: Dict[str, List[int]],
                         logger: Logger,
                         cubics_by_objid: Dict[str, List[StaCubic]],
                         bus_by_term_id: Dict[str, dev.Bus],
                         phase_map: PhaseMap,
                         frequency: float) -> None:
    """
    Add elmshnt devices.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param phase_map: Resolved terminal-conductor phase map.
    :param frequency: frequency parameter.
    :return: Function result.
    """
    for elmshnt in dgs_grid.elmshnts:
        if int(elmshnt.ncapx) > 1:
            bus, cshunt = convert_dgs_to_controllable_shunt_from_elmshnt(
                elmshnt=elmshnt,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                frequency=frequency
            )
            grid.add_controllable_shunt(bus=bus, api_obj=cshunt)
        else:
            bus, shunt = convert_dgs_to_shunt(
                elmshnt=elmshnt,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                phase_map=phase_map,
                frequency=frequency
            )
            grid.add_shunt(bus=bus, api_obj=shunt)


def _add_elmsvs_devices(dgs_grid: DgsCircuit,
                        grid: dev.MultiCircuit,
                        stacubic_dict: Dict[str, List[int]],
                        use_vsc_for_injections: bool,
                        logger: Logger,
                        cubics_by_objid: Dict[str, List[StaCubic]],
                        bus_by_term_id: Dict[str, dev.Bus]) -> None:
    """
    Add elmsvs devices.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param use_vsc_for_injections: use_vsc_for_injections parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :return: Function result.
    """
    for elmsvs in dgs_grid.elmsvss:
        if use_vsc_for_injections:
            dc_bus, vsc = convert_dgs_svs_to_vsc(
                elmsvs=elmsvs,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id
            )
            grid.add_bus(dc_bus)
            grid.add_vsc(vsc)
        elif elmsvs.i_ctrl == 1 and elmsvs.i_droop != 0:
            # Keep the established VSC droop parameters without inventing a DC terminal for ABC.
            bus: dev.Bus = get_injection_bus(elm_id=elmsvs.ID, stacubic_dict=stacubic_dict,
                buses=grid.buses, cubics_by_objid=cubics_by_objid, bus_by_term_id=bus_by_term_id)
            static_gen: dev.StaticGenerator = dev.StaticGenerator(
                name=_get_non_empty_name(elmsvs.loc_name, f"SVS_{_ref_id(elmsvs.ID)}"),
                idtag=_ref_id(elmsvs.ID), active=not bool(elmsvs.outserv), P=0.0, Q=0.0,
                Snom=float(elmsvs.Srated), control_mode=StaticGeneratorControlMode.QVDroop,
                vset=float(elmsvs.usetp), droop=float(elmsvs.ddroop))
            grid.add_static_generator(bus=bus, api_obj=static_gen)
        else:
            bus, cshunt = convert_dgs_to_controllable_shunt_from_svs(
                elmsvs=elmsvs,
                stacubic_dict=stacubic_dict,
                buses=grid.buses,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id
            )
            grid.add_controllable_shunt(bus=bus, api_obj=cshunt)


def _add_elmcoup_switches(dgs_grid: DgsCircuit,
                          grid: dev.MultiCircuit,
                          cubics_by_objid: Dict[str, List[StaCubic]],
                          bus_by_term_id: Dict[str, dev.Bus],
                          switch_by_cubic_id: Dict[str, StaSwitch],
                          typ_switch_dict: Dict[str, TypSwitch],
                          baseMVA: float,
                          logger: Logger) -> None:
    """
    Add elmcoup switches.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param typ_switch_dict: typ_switch_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    vg_switches: List[dev.Switch] = convert_dgs_to_switches_from_elmcoup(
        elmcoups=dgs_grid.elmcoups,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        typ_switch_by_id=typ_switch_dict,
        sbase_mva=baseMVA,
        logger=logger
    )
    for switch in vg_switches:
        grid.add_switch(obj=switch)


def _add_elmzpu_series_reactances(dgs_grid: DgsCircuit,
                                  grid: dev.MultiCircuit,
                                  bus_by_term_id: Dict[str, dev.Bus],
                                  stacubic_dict: Dict[str, List[int]],
                                  cubics_by_objid: Dict[str, List[StaCubic]],
                                  logger: Logger,
                                  baseMVA: float,
                                  branch_group_by_id: Dict[str, dev.BranchGroup]) -> None:
    """
    Add elmzpu series reactances.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param logger: logger parameter.
    :param baseMVA: baseMVA parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :return: Function result.
    """
    for elmzpu in dgs_grid.elmzpus:
        reactance = convert_dgs_common_impedance_to_series_reactance(
            element=elmzpu,
            buses=grid.buses,
            bus_by_terminal_id=bus_by_term_id,
            stacubic_dict=stacubic_dict,
            cubics_by_obj_id=cubics_by_objid,
            logger=logger,
            Sbase_vg=baseMVA
        )
        fold_id = _ref_id(elmzpu.fold_id)
        if fold_id is not None and fold_id != "":
            branch_group = branch_group_by_id.get(fold_id)
            if branch_group is not None:
                reactance.group = branch_group
        grid.add_series_reactance(reactance)


def _add_elmscap_series_reactances(dgs_grid: DgsCircuit,
                                   grid: dev.MultiCircuit,
                                   bus_by_term_id: Dict[str, dev.Bus],
                                   stacubic_dict: Dict[str, List[int]],
                                   cubics_by_objid: Dict[str, List[StaCubic]],
                                   logger: Logger,
                                   baseMVA: float,
                                   branch_group_by_id: Dict[str, dev.BranchGroup]) -> None:
    """
    Add elmscap series reactances.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param logger: logger parameter.
    :param baseMVA: baseMVA parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :return: Function result.
    """
    for elmscap in dgs_grid.elmscaps:
        reactance = convert_dgs_series_capacitor_to_reactance(
            element=elmscap,
            buses=grid.buses,
            bus_by_terminal_id=bus_by_term_id,
            stacubic_dict=stacubic_dict,
            cubics_by_obj_id=cubics_by_objid,
            logger=logger,
            sbase_mva=baseMVA
        )
        fold_id = _ref_id(elmscap.fold_id)
        if fold_id is not None and fold_id != "":
            branch_group = branch_group_by_id.get(fold_id)
            if branch_group is not None:
                reactance.group = branch_group
        grid.add_series_reactance(obj=reactance)


def _add_elmsind_series_reactances(dgs_grid: DgsCircuit,
                                   grid: dev.MultiCircuit,
                                   bus_by_term_id: Dict[str, dev.Bus],
                                   stacubic_dict: Dict[str, List[int]],
                                   cubics_by_objid: Dict[str, List[StaCubic]],
                                   typsind_raw_dict: Dict[str, TypSind],
                                   logger: Logger,
                                   baseMVA: float,
                                   branch_group_by_id: Dict[str, dev.BranchGroup]) -> None:
    """
    Add elmsind series reactances.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param typsind_raw_dict: typsind_raw_dict parameter.
    :param logger: logger parameter.
    :param baseMVA: baseMVA parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :return: Function result.
    """
    for elmsind in dgs_grid.elmsinds:
        reactance = convert_dgs_to_series_reactance(
            element=elmsind,
            buses=grid.buses,
            bus_by_terminal_id=bus_by_term_id,
            stacubic_dict=stacubic_dict,
            cubics_by_obj_id=cubics_by_objid,
            typsind_dict=typsind_raw_dict,
            logger=logger,
            sbase_mva=baseMVA
        )
        fold_id = _ref_id(elmsind.fold_id)
        if fold_id is not None and fold_id != "":
            branch_group = branch_group_by_id.get(fold_id)
            if branch_group is not None:
                reactance.group = branch_group
        grid.add_series_reactance(obj=reactance)


def _add_elmtr2_transformers(dgs_grid: DgsCircuit,
                             grid: dev.MultiCircuit,
                             stacubic_dict: Dict[str, List[int]],
                             typtr2_dict: Dict[str, dev.TransformerType],
                             typtr2_raw_dict: Dict[str, TypTr2],
                             frequency: float,
                             baseMVA: float,
                             logger: Logger,
                             cubics_by_objid: Dict[str, List[StaCubic]],
                             bus_by_term_id: Dict[str, dev.Bus],
                             switch_by_cubic_id: Dict[str, StaSwitch],
                             branch_group_by_id: Dict[str, dev.BranchGroup],
                             phase_map: PhaseMap) -> None:
    """
    Add elmtr2 transformers.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typtr2_dict: typtr2_dict parameter.
    :param typtr2_raw_dict: typtr2_raw_dict parameter.
    :param frequency: frequency parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :param phase_map: Resolved terminal-conductor phase map.
    :return: Function result.
    """
    for elmtr2 in dgs_grid.elmtr2s:
        parallel_count = _get_parallel_device_count(count=int(elmtr2.ntnum))
        for parallel_index in range(parallel_count):
            trafo = convert_dgs_to_transformer(
                tr2=elmtr2,
                buses=grid.buses,
                stacubic_dict=stacubic_dict,
                templates_dict=typtr2_dict,
                typtr2_dict=typtr2_raw_dict,
                freq=frequency,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                switch_by_cubic_id=switch_by_cubic_id,
                phase_map=phase_map,
                parallel_index=parallel_index,
                parallel_count=parallel_count
            )
            fold_id = _ref_id(elmtr2.fold_id)
            if fold_id is not None and fold_id != "":
                branch_group = branch_group_by_id.get(fold_id)
                if branch_group is not None:
                    trafo.group = branch_group
            grid.add_transformer2w(obj=trafo)


def _add_elmtr3_transformers(dgs_grid: DgsCircuit,
                             grid: dev.MultiCircuit,
                             stacubic_dict: Dict[str, List[int]],
                             typtr3_dict: Dict[str, TypTr3],
                             baseMVA: float,
                             logger: Logger,
                             cubics_by_objid: Dict[str, List[StaCubic]],
                             bus_by_term_id: Dict[str, dev.Bus],
                             switch_by_cubic_id: Dict[str, StaSwitch],
                             branch_group_by_id: Dict[str, dev.BranchGroup]) -> None:
    """
    Add elmtr3 transformers.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typtr3_dict: typtr3_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :return: Function result.
    """
    for elmtr3 in dgs_grid.elmtr3s:
        tr3_typ_id: str | None = _ref_id(elmtr3.typ_id)
        if tr3_typ_id is None or tr3_typ_id == "":
            logger.add_warning(
                f"missing typ_id (no TypTr3 reference in DGS)",
                device=f"{elmtr3.loc_name}' (ID={elmtr3.ID}) ",
                device_class="Transformer3W",
            )
            continue
        if typtr3_dict.get(tr3_typ_id, None) is None:
            logger.add_warning(
                f"referenced TypTr3 not found",
                device=f"{elmtr3.loc_name}' (ID={elmtr3.ID}) ",
                device_class="Transformer3W",
                value=str(elmtr3.typ_id)
            )
            continue
        term_ids: List[str] = get_terminal_ids(element_id=elmtr3.ID, cubics_by_objid=cubics_by_objid)
        if len(term_ids) != 3:
            bus_ids: List[int] | None = stacubic_dict.get(_ref_id(elmtr3.ID), None)
            if bus_ids is None or len(bus_ids) != 3:
                logger.add_warning(
                    f"Not connected to exactly 3 terminals",
                    device=f"{elmtr3.loc_name}' (ID={elmtr3.ID}) ",
                    device_class="Transformer3W",
                )
                continue
        parallel_count = _get_parallel_device_count(count=int(elmtr3.nt3nm))
        for parallel_index in range(parallel_count):
            trafo3w: dev.Transformer3W = convert_dgs_to_transformer3w(
                tr3=elmtr3,
                buses=grid.buses,
                stacubic_dict=stacubic_dict,
                templates_dict=typtr3_dict,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                switch_by_cubic_id=switch_by_cubic_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count
            )
            grid.add_bus(obj=trafo3w.bus0)
            fold_id = _ref_id(elmtr3.fold_id)
            if fold_id is not None and fold_id != "":
                branch_group = branch_group_by_id.get(fold_id)
                if branch_group is not None:
                    trafo3w.winding1.group = branch_group
                    trafo3w.winding2.group = branch_group
                    trafo3w.winding3.group = branch_group
            grid.add_transformer3w(obj=trafo3w)


def _add_elmtr4_transformers(dgs_grid: DgsCircuit,
                             grid: dev.MultiCircuit,
                             stacubic_dict: Dict[str, List[int]],
                             typtr4_dict: Dict[str, TypTr4],
                             baseMVA: float,
                             logger: Logger,
                             cubics_by_objid: Dict[str, List[StaCubic]],
                             bus_by_term_id: Dict[str, dev.Bus],
                             switch_by_cubic_id: Dict[str, StaSwitch],
                             branch_group_by_id: Dict[str, dev.BranchGroup]) -> None:
    """
    Add elmtr3 transformers.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typtr3_dict: typtr3_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param switch_by_cubic_id: switch_by_cubic_id parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :return: Function result.
    """
    for elmtr4 in dgs_grid.elmtr4s:
        tr4_typ_id: str | None = _ref_id(elmtr4.typ_id)
        if tr4_typ_id is None or tr4_typ_id == "":
            logger.add_warning(
                f"missing typ_id (no TypTr4 reference in DGS)",
                device=f"{elmtr4.loc_name}' (ID={elmtr4.ID}) ",
                device_class="Transformer4W",
            )
            continue
        if typtr4_dict.get(tr4_typ_id, None) is None:
            logger.add_warning(
                f"referenced TypTr4 not found",
                device=f"{elmtr4.loc_name}' (ID={elmtr4.ID}) ",
                device_class="Transformer4W",
                value=str(elmtr4.typ_id)
            )
            continue
        term_ids: List[str] = get_terminal_ids(element_id=elmtr4.ID, cubics_by_objid=cubics_by_objid)
        if len(term_ids) != 4:
            bus_ids: List[int] | None = stacubic_dict.get(_ref_id(elmtr4.ID), None)
            if bus_ids is None or len(bus_ids) != 4:
                logger.add_warning(
                    f"Not connected to exactly 4 terminals",
                    device=f"{elmtr4.loc_name}' (ID={elmtr4.ID}) ",
                    device_class="Transformer4W",
                )
                continue
        parallel_count = _get_parallel_device_count(count=int(elmtr4.nt4nm))
        for parallel_index in range(parallel_count):
            trafo4w: dev.TransformerNW = convert_dgs_to_transformer4w(
                tr4=elmtr4,
                buses=grid.buses,
                stacubic_dict=stacubic_dict,
                templates_dict=typtr4_dict,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                switch_by_cubic_id=switch_by_cubic_id,
                parallel_index=parallel_index,
                parallel_count=parallel_count
            )
            grid.add_bus(obj=trafo4w.bus0)
            fold_id = _ref_id(elmtr4.fold_id)
            if fold_id is not None and fold_id != "":
                branch_group = branch_group_by_id.get(fold_id)
                if branch_group is not None:
                    for winding in trafo4w.windings:
                        winding.group = branch_group
            grid.add_transformer_nw(obj=trafo4w)


def _build_stacubic_mappings(stacubics: List[StaCubic]) -> Tuple[Dict[str, List[int]], Dict[str, List[StaCubic]]]:
    """
    Build stacubic mappings.

    :param stacubics: stacubics parameter.
    :return: Function result.
    """
    stacubic_dict: Dict[str, List[int]] = dict()
    cubics_by_objid: Dict[str, List[StaCubic]] = dict()
    for cb in stacubics:
        if cb.obj_id is not None:
            obj_id = _ref_id(cb.obj_id)
            if obj_id is not None:
                lst_bus = stacubic_dict.get(obj_id, None)
                if lst_bus is None:
                    stacubic_dict[obj_id] = [cb.obj_bus]
                else:
                    lst_bus.append(cb.obj_bus)

                lst_cubic = cubics_by_objid.get(obj_id, None)
                if lst_cubic is None:
                    cubics_by_objid[obj_id] = [cb]
                else:
                    lst_cubic.append(cb)

                if cb.obj_id != obj_id:
                    lst_bus_raw = stacubic_dict.get(cb.obj_id, None)
                    if lst_bus_raw is None:
                        stacubic_dict[cb.obj_id] = [cb.obj_bus]
                    else:
                        lst_bus_raw.append(cb.obj_bus)

                    lst_cubic_raw = cubics_by_objid.get(cb.obj_id, None)
                    if lst_cubic_raw is None:
                        cubics_by_objid[cb.obj_id] = [cb]
                    else:
                        lst_cubic_raw.append(cb)
                else:
                    pass
            else:
                pass
        else:
            pass
    return stacubic_dict, cubics_by_objid


def _build_phase_map(stacubics: List[StaCubic], logger: Logger) -> PhaseMap:
    """
    Resolve every terminal conductor to a global N/A/B/C phase.

    Absolute phase names (A, B, C and N) are used as known starting points.
    Local names such as SP, DP1 and DP2 are propagated through every element
    that has two or more cubicles. Repeating the propagation allows phases to
    travel through any number of downstream lines and transformers.

    :param stacubics: All PowerFactory cubicles in the DGS file.
    :param logger: VeraGrid logger.
    :return: Mapping ``(terminal ID, local conductor index) -> N/A/B/C index``.
    """
    phase_map: PhaseMap = {}
    cubics_by_element: Dict[str, List[Tuple[StaCubic, str, Set[int]]]] = {}

    for cubic in stacubics:
        terminal_id = _ref_id(cubic.fold_id)
        element_id = _ref_id(cubic.obj_id)
        if terminal_id is None or element_id is None:
            continue

        phase_names = _get_cubic_phase_names(cubic)
        active_indices = {_LOCAL_PHASE_INDEX[name] for name in phase_names}
        cubics_by_element.setdefault(element_id, []).append((cubic, terminal_id, active_indices))

        # A, B, C and N are already global phase names. Local names are
        # deliberately left unresolved until they can be propagated.
        for phase_name in phase_names:
            global_phase = _GLOBAL_PHASE_INDEX.get(phase_name)
            if global_phase is None:
                continue

            node = (terminal_id, _LOCAL_PHASE_INDEX[phase_name])
            previous_phase = phase_map.get(node)
            if previous_phase is not None and previous_phase != global_phase:
                raise ValueError(
                    f"Conflicting phases for terminal conductor {node}: "
                    f"{previous_phase} and {global_phase}"
                )

            phase_map[node] = global_phase

    changed = True
    while changed:
        changed = False

        for element_id, cubicle_sides in cubics_by_element.items():
            if len(cubicle_sides) < 2:
                continue

            for attribute in ("it2p1", "it2p2", "it2p3"):
                connected_nodes: List[Tuple[str, int]] = []

                for cubic, terminal_id, active_indices in cubicle_sides:
                    local_index = int(getattr(cubic, attribute))
                    if local_index in active_indices:
                        connected_nodes.append((terminal_id, local_index))

                known_phases = {
                    phase_map[node]
                    for node in connected_nodes
                    if node in phase_map
                }

                if len(known_phases) > 1:
                    raise ValueError(
                        f"Conflicting phase mapping in element {element_id} "
                        f"for {attribute}: {sorted(known_phases)}"
                    )

                if len(known_phases) == 0:
                    continue

                resolved_phase = next(iter(known_phases))
                for node in connected_nodes:
                    if node not in phase_map:
                        phase_map[node] = resolved_phase
                        changed = True

    unresolved_nodes: Set[Tuple[str, int]] = set()
    for cubicle_sides in cubics_by_element.values():
        for _, terminal_id, active_indices in cubicle_sides:
            for local_index in active_indices:
                node = (terminal_id, local_index)
                if node not in phase_map:
                    unresolved_nodes.add(node)

    for terminal_id, local_index in sorted(unresolved_nodes):
        logger.add_warning(
            "Could not resolve the global phase of terminal conductor.",
            device=f"ElmTerm ID={terminal_id}",
            device_class="StaCubic",
            value=local_index,
        )

    return phase_map


def _build_graphics_positions(intgrfs: List[IntGrf]) -> Dict[str, Tuple[float, float]]:
    """
    Build object positions from DGS graphical records.

    :param intgrfs: DGS graphical objects.
    :return: Position indexed by referenced DGS object identifier.
    """
    pos_by_objid: Dict[str, Tuple[float, float]] = dict()
    for graphic in intgrfs:
        pos_by_objid[graphic.pDataObj] = (
            float(graphic.rCenterX),
            float(graphic.rCenterY),
        )
    return pos_by_objid


def _add_elmzone_zones(dgs_grid: DgsCircuit, grid: dev.MultiCircuit) -> Dict[str, dev.Zone]:
    """
    Add elmzone zones.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    zone_by_id: Dict[str, dev.Zone] = dict()
    for elmzone in dgs_grid.elmzones:
        zid = _ref_id(elmzone.ID)
        zone_name: str = elmzone.loc_name if elmzone.loc_name != "" else f"Zone_{zid}"
        zone = dev.Zone(name=zone_name, idtag=zid, code="", latitude=0.0, longitude=0.0, area=None)
        grid.add_zone(zone)
        if zid is not None:
            zone_by_id[zid] = zone
    return zone_by_id


def _add_elmarea_areas(dgs_grid: DgsCircuit, grid: dev.MultiCircuit) -> Dict[str, dev.Area]:
    """
    Add elmarea areas.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    area_by_id: Dict[str, dev.Area] = dict()
    for elmarea in dgs_grid.elmareas:
        aid = _ref_id(elmarea.ID)
        area_name: str = elmarea.loc_name if elmarea.loc_name != "" else f"Area_{aid}"
        area = dev.Area(name=area_name, idtag=aid, code="", latitude=0.0, longitude=0.0)
        grid.add_area(area)
        if aid is not None:
            area_by_id[aid] = area
    return area_by_id


def _add_elmbranch_groups(dgs_grid: DgsCircuit, grid: dev.MultiCircuit) -> Dict[str, dev.BranchGroup]:
    """
    Add elmbranch groups.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    branch_group_by_id: Dict[str, dev.BranchGroup] = dict()
    for elmbranch in dgs_grid.elmbranches:
        bid = _ref_id(elmbranch.ID)
        name: str = elmbranch.loc_name if elmbranch.loc_name != "" else f"BranchGroup_{bid}"
        branch_group = dev.BranchGroup(name=name, code="", idtag=bid)
        grid.add_branch_group(obj=branch_group)
        if bid is not None and bid != "":
            branch_group_by_id[bid] = branch_group
    return branch_group_by_id


def add_dgs_terminal_buses(dgs_grid: DgsCircuit,
                           grid: dev.MultiCircuit,
                           pos_by_objid: Dict[str, Tuple[float, float]]) -> Dict[str, dev.Bus]:
    """
    Add buses only after every source terminal FID is proven unambiguous.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param pos_by_objid: pos_by_objid parameter.
    :return: Added buses indexed by their exact normalized ``ElmTerm`` FID.
    :raises ValueError: If any terminal FID is empty or duplicated.
    """
    # Validate the complete source identity envelope before constructing or
    # adding a bus. This prevents a late invalid row from leaving a partially
    # mutated circuit and prevents duplicate FIDs from merging distinct nodes.
    terminal_ids: List[str] = list("" for elmterm in dgs_grid.elmterms)
    known_terminal_ids: Set[str] = set()
    terminal_index: int
    elmterm: ElmTerm
    for terminal_index, elmterm in enumerate(dgs_grid.elmterms):
        terminal_id: str | None = _ref_id(elmterm.ID)
        if terminal_id is None or terminal_id == "":
            raise ValueError("ElmTerm FID must not be empty")
        else:
            if terminal_id in known_terminal_ids:
                raise ValueError(f"Duplicate ElmTerm FID: {terminal_id}")
            else:
                known_terminal_ids.add(terminal_id)
                terminal_ids[terminal_index] = terminal_id

    # The validated one-to-one source mapping can now be committed to the
    # circuit without last-write-wins identity loss.
    bus_by_term_id: Dict[str, dev.Bus] = dict()
    for terminal_index, elmterm in enumerate(dgs_grid.elmterms):
        bus: dev.Bus = convert_dgs_to_bus(
            elmterm=elmterm,
            pos_by_objid=pos_by_objid,
        )
        grid.add_bus(obj=bus)
        bus_by_term_id[terminal_ids[terminal_index]] = bus
    return bus_by_term_id


def _assign_elmterm_zone_references(dgs_grid: DgsCircuit,
                                    bus_by_term_id: Dict[str, dev.Bus],
                                    zone_by_id: Dict[str, dev.Zone]) -> None:
    """
    Assign elmterm zone references.

    :param dgs_grid: dgs_grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param zone_by_id: zone_by_id parameter.
    :return: Function result.
    """
    for elmterm in dgs_grid.elmterms:
        tid = _ref_id(elmterm.ID)
        zid = _ref_id(elmterm.cpZone)
        if tid is not None and zid is not None and zid != "":
            bus = bus_by_term_id.get(tid, None)
            zone = zone_by_id.get(zid, None)
            if bus is not None:
                bus.zone = zone


def _assign_elmterm_area_references(dgs_grid: DgsCircuit,
                                    bus_by_term_id: Dict[str, dev.Bus],
                                    area_by_id: Dict[str, dev.Area]) -> None:
    """
    Assign elmterm area references.

    :param dgs_grid: dgs_grid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param area_by_id: area_by_id parameter.
    :return: Function result.
    """
    for elmterm in dgs_grid.elmterms:
        tid = _ref_id(elmterm.ID)
        aid = _ref_id(elmterm.cpArea)
        if tid is not None and aid is not None and aid != "":
            bus = bus_by_term_id.get(tid, None)
            area = area_by_id.get(aid, None)
            if bus is not None:
                bus.area = area


def _build_typsym_dict(dgs_grid: DgsCircuit) -> Dict[str, TypSym]:
    """
    Build typsym dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typsym_dict: Dict[str, TypSym] = dict()
    for typsym in dgs_grid.typsyms:
        typsym_dict[typsym.ID] = typsym
        tid = _ref_id(typsym.ID)
        if tid is not None:
            typsym_dict[tid] = typsym
    return typsym_dict


def _build_typasmo_dict(dgs_grid: DgsCircuit) -> Dict[str, TypAsmo]:
    """
    Build typasmo dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typasmo_dict: Dict[str, TypAsmo] = dict()
    for typasmo in dgs_grid.typasmos:
        typasmo_dict[typasmo.ID] = typasmo
        tid = _ref_id(typasmo.ID)
        if tid is not None:
            typasmo_dict[tid] = typasmo
    return typasmo_dict


def _build_typswitch_dict(dgs_grid: DgsCircuit) -> Dict[str, TypSwitch]:
    """
    Build typswitch dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typ_switch_dict: Dict[str, TypSwitch] = dict()
    for typ_switch in dgs_grid.typswitches:
        typ_switch_dict[typ_switch.ID] = typ_switch
        tid = _ref_id(typ_switch.ID)
        if tid is not None:
            typ_switch_dict[tid] = typ_switch
    return typ_switch_dict


def _build_typlne_templates(
        dgs_grid: DgsCircuit,
        grid: dev.MultiCircuit,
        logger: Logger,
) -> Tuple[Dict[str, dev.SequenceLineType], Dict[str, dev.UndergroundLineType], Dict[str, TypLne]]:
    """
    Build typlne templates.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param logger: Import logger receiving incomplete DC cable warnings.
    :return: AC templates, complete DC cable templates, and parsed source types.
    """
    typlne_dict: Dict[str, dev.SequenceLineType] = dict()
    dc_cable_type_dict: Dict[str, dev.UndergroundLineType] = dict()
    source_line_type_dict: Dict[str, TypLne] = dict()
    for typlne in dgs_grid.typlnes:
        source_line_type_dict[typlne.ID] = typlne
        source_type_id: str | None = _ref_id(typlne.ID)
        if source_type_id is not None:
            source_line_type_dict[source_type_id] = typlne
        else:
            pass
        if int(typlne.systp) == 1:
            dc_cable_type: dev.UndergroundLineType | None = convert_dgs_to_dc_cable_type(
                typlne=typlne,
                logger=logger,
            )
            if dc_cable_type is not None:
                grid.add_underground_line(obj=dc_cable_type)
                dc_cable_type_dict[typlne.ID] = dc_cable_type
                normalized_type_id: str | None = _ref_id(typlne.ID)
                if normalized_type_id is not None:
                    dc_cable_type_dict[normalized_type_id] = dc_cable_type
                else:
                    pass
            else:
                pass
        else:
            seq_lne: dev.SequenceLineType = convert_dgs_to_sequence_line(typlne=typlne)
            grid.add_sequence_line(obj=seq_lne)
            typlne_dict[typlne.ID] = seq_lne
            normalized_type_id = _ref_id(typlne.ID)
            if normalized_type_id is not None:
                typlne_dict[normalized_type_id] = seq_lne
            else:
                pass
    return typlne_dict, dc_cable_type_dict, source_line_type_dict


def _build_typcab_catalogue(dgs_grid: DgsCircuit,
                            grid: dev.MultiCircuit,
                            logger: Logger) -> Dict[str, dev.UndergroundCableType]:
    """Build physical underground-cable catalogue entries from ``TypCab`` rows.

    :param dgs_grid: Parsed PowerFactory DGS model.
    :param grid: Destination VeraGrid circuit.
    :param logger: Import logger receiving unsupported or unknown layer warnings.
    :return: Cable constructions indexed by raw and normalized DGS pointers.
    """
    cable_type_dict: Dict[str, dev.UndergroundCableType] = dict()
    source_cable: TypCab
    for source_cable in dgs_grid.typcabs:
        # PF retains material properties and thicknesses for disabled layers.
        # Only the explicit existence flags establish that armour is active.
        has_armour: bool = (
                source_cable.has_arm not in (None, 0)
                or source_cable.cHasEl_2 not in (None, 0)
        )
        if has_armour:
            logger.add_warning(
                msg='Active cable armour is not modelled; only core and sheath are imported; cable results are an approximation',
                device=source_cable.loc_name,
                device_class='TypCab',
                device_property='has_arm / cHasEl:2',
            )
        elif source_cable.has_arm is None and source_cable.cHasEl_2 is None:
            logger.add_warning(
                msg='Cable armour flags are missing; importing core and sheath without verifying armour absence',
                device=source_cable.loc_name,
                device_class='TypCab',
                device_property='has_arm / cHasEl:2',
            )
        else:
            pass
        cable_type: dev.UndergroundCableType = dev.UndergroundCableType(
            name=source_cable.loc_name,
            idtag=_ref_id(source_cable.ID),
            nominal_voltage=source_cable.uline,
            core_dc_resistance=source_cable.rpha,
            core_diameter=source_cable.diaCon,
            core_internal_diameter=source_cable.diaTube,
            cable_diameter=source_cable.diaCab,
            sheath_thickness=source_cable.thSht,
            main_insulation_thickness=source_cable.thIns[0],
            core_resistivity=source_cable.crho[0],
            sheath_resistivity=source_cable.crho[1],
            core_filling_factor=source_cable.Cf[0],
            sheath_filling_factor=source_cable.Cf[1],
            main_insulation_permittivity=source_cable.cepsr[0],
            outer_insulation_permittivity=source_cable.cepsr[1],
            main_insulation_loss_tangent=source_cable.ctand[0],
            outer_insulation_loss_tangent=source_cable.ctand[1],
            core_relative_permeability=source_cable.my[0],
            sheath_relative_permeability=source_cable.my[1],
            skin_effect_factor=source_cable.ks,
            proximity_effect_factor=source_cable.kp,
        )
        grid.add_underground_cable(obj=cable_type)

        # DGS references may use either the complete FID or its pointer token.
        cable_type_dict[source_cable.ID] = cable_type
        normalized_id: str | None = _ref_id(source_cable.ID)
        if normalized_id is not None:
            cable_type_dict[normalized_id] = cable_type
        else:
            pass
    return cable_type_dict


def _get_typcabsys_earth_resistivity(source_system: TypCabsys) -> float:
    """Resolve earth resistivity from the two equivalent PowerFactory fields.

    :param source_system: Parsed PowerFactory cable-system type.
    :return: Earth resistivity in ohm metres.
    """
    if source_system.rhoEarth > 0.0:
        earth_resistivity: float = float(source_system.rhoEarth)
    elif source_system.cGearth > 0.0:
        # PowerFactory stores conductivity in micro-siemens per centimetre.
        earth_resistivity = 10000.0 / float(source_system.cGearth)
    else:
        earth_resistivity = 100.0
    return earth_resistivity


def _build_typcabsys_templates(
        dgs_grid: DgsCircuit,
        grid: dev.MultiCircuit,
        cable_type_dict: Dict[str, dev.UndergroundCableType],
        logger: Logger,
) -> Dict[str, dev.UndergroundLineType]:
    """Build physical underground-line templates from ``TypCabsys`` rows.

    :param dgs_grid: Parsed PowerFactory DGS model.
    :param grid: Destination VeraGrid circuit.
    :param cable_type_dict: Imported physical cables indexed by DGS pointer.
    :param logger: Import logger receiving unsupported or incomplete data.
    :return: Cable systems indexed by raw and normalized DGS pointers.
    """
    cable_system_dict: Dict[str, dev.UndergroundLineType] = dict()
    source_system: TypCabsys
    for source_system in dgs_grid.typcabsys:
        is_supported: bool = int(source_system.systp) == 0 and source_system.iopt_bur == 'gnd'
        if is_supported:
            referenced_cables: List[dev.UndergroundCableType | None] = list()
            cable_pointer: str | None
            for cable_pointer in source_system.pcab_c:
                referenced_cable: dev.UndergroundCableType | None = _resolve_pointer_dict_value(
                    key=cable_pointer,
                    mapping=cable_type_dict,
                )
                referenced_cables.append(referenced_cable)

            first_cable: dev.UndergroundCableType | None = (
                referenced_cables[0] if len(referenced_cables) > 0 else None
            )
            if first_cable is not None:
                rated_current_ka: float = (
                    float(source_system.dInom[0]) if len(source_system.dInom) > 0 else 0.0
                )
                cable_system: dev.UndergroundLineType = dev.UndergroundLineType(
                    name=source_system.loc_name,
                    idtag=_ref_id(source_system.ID),
                    Imax=rated_current_ka,
                    Vnom=first_cable.nominal_voltage,
                    freq=source_system.frnom,
                    earth_resistivity=_get_typcabsys_earth_resistivity(source_system=source_system),
                )

                # Each xy_c row stores all X coordinates followed by all burial
                # depths for one circuit. Only nphas positions are meaningful.
                circuit_index: int
                phase_offset: int = 0
                complete_composition: bool = True
                for circuit_index in range(len(source_system.xy_c)):
                    phase_count: int = (
                        int(source_system.nphas[circuit_index])
                        if circuit_index < len(source_system.nphas)
                        else int(source_system.cnphas)
                    )
                    cable_for_circuit: dev.UndergroundCableType | None = (
                        referenced_cables[circuit_index]
                        if circuit_index < len(referenced_cables)
                        else None
                    )
                    coordinate_row: List[float] = source_system.xy_c[circuit_index]
                    coordinate_axis_width: int = int(source_system.cnphas)
                    if (
                            cable_for_circuit is not None
                            and len(coordinate_row) >= coordinate_axis_width + phase_count
                    ):
                        local_phase: int
                        for local_phase in range(phase_count):
                            cable_system.add_cable_relationship(
                                cable=cable_for_circuit,
                                xpos=float(coordinate_row[local_phase]),
                                ypos=float(coordinate_row[coordinate_axis_width + local_phase]),
                                phase=phase_offset + local_phase + 1,
                            )
                    else:
                        complete_composition = False
                    phase_offset += phase_count

                if complete_composition and cable_system.compute(logger=logger):
                    grid.add_underground_line(obj=cable_system)
                    cable_system_dict[source_system.ID] = cable_system
                    normalized_id: str | None = _ref_id(source_system.ID)
                    if normalized_id is not None:
                        cable_system_dict[normalized_id] = cable_system
                    else:
                        pass
                else:
                    logger.add_warning(
                        msg='Underground cable system could not be calculated',
                        device=source_system.loc_name,
                        device_class='TypCabsys',
                    )
            else:
                logger.add_warning(
                    msg='Underground cable construction not found',
                    device=source_system.loc_name,
                    device_class='TypCabsys',
                )
        else:
            logger.add_warning(
                msg='Only AC cable systems laid directly in ground are supported',
                device=source_system.loc_name,
                device_class='TypCabsys',
            )
    return cable_system_dict


def _build_typcon_catalogues(dgs_grid: DgsCircuit,
                             grid: dev.MultiCircuit) -> Tuple[Dict[str, TypCon], Dict[str, Wire]]:
    """
    Build typcon catalogues.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    typcon_raw_dict: Dict[str, TypCon] = dict()
    wire_type_dict: Dict[str, Wire] = dict()
    for typcon in dgs_grid.typcons:
        cid = _ref_id(typcon.ID)
        if cid is not None:
            typcon_raw_dict[cid] = typcon
            typcon_raw_dict[typcon.ID] = typcon
            wire = convert_dgs_to_wire(typcon=typcon)
            wire_type_dict[cid] = wire
            wire_type_dict[typcon.ID] = wire
            grid.wire_types.append(wire)
        else:
            pass
    return typcon_raw_dict, wire_type_dict


def _add_typtow_templates(dgs_grid: DgsCircuit,
                          grid: dev.MultiCircuit,
                          typcon_raw_dict: Dict[str, TypCon],
                          wire_type_dict: Dict[str, Wire],
                          typlne_dict: Dict[str, dev.SequenceLineType],
                          cubics_by_objid: Dict[str, List[StaCubic]],
                          phase_map: PhaseMap,
                          frequency: float,
                          logger: Logger) -> Dict[str, dev.OverheadLineType]:
    """
    Add typtow templates.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param typcon_raw_dict: typcon_raw_dict parameter.
    :param wire_type_dict: wire_type_dict parameter.
    :param typlne_dict: typlne_dict parameter.
    :param cubics_by_objid: Cubicles grouped by connected element.
    :param phase_map: Resolved terminal-conductor phase map.
    :param frequency: frequency parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    overhead_line_type_dict: Dict[str, dev.OverheadLineType] = dict()
    for typtow in dgs_grid.typtows:
        tow_id = _ref_id(typtow.ID)
        if tow_id is not None:
            if typtow.i_mode == 0:
                phase_counts = [
                    max(0, min(int(typtow.nphas[index]), 3))
                    if index < len(typtow.nphas)
                    else 3
                    for index in range(len(typtow.pcond_c))
                ]
                expected_conductors = sum(phase_counts)
                phase_order_by_line_id: Dict[str, Tuple[int, ...]] = dict()

                # TypTow describes the physical circuits, while the line
                # cubicles identify their electrical N/A/B/C conductors.
                for line in dgs_grid.elmlnes:
                    if _ref_id(line.typ_id) != tow_id:
                        continue

                    line_phase_orders: Set[Tuple[int, ...]] = set()
                    for cubic in cubics_by_objid.get(_ref_id(line.ID), []):
                        phases = tuple(_get_cubic_phases(cubic=cubic, phase_map=phase_map))
                        if len(phases) == expected_conductors:
                            line_phase_orders.add(phases)

                    if len(line_phase_orders) == 1:
                        line_phase_order = next(iter(line_phase_orders))
                        phase_order_by_line_id[line.ID] = line_phase_order
                        line_id = _ref_id(line.ID)
                        if line_id is not None:
                            phase_order_by_line_id[line_id] = line_phase_order
                    elif len(line_phase_orders) > 1:
                        logger.add_warning(
                            "Line cubicles have different phase layouts; keeping the shared tower template.",
                            device=line.loc_name,
                            device_class="ElmLne",
                            value=sorted(line_phase_orders),
                        )

                phase_orders = set(phase_order_by_line_id.values())

                phase_order: List[int] | None = None
                if len(phase_orders) == 1:
                    phase_order = list(next(iter(phase_orders)))
                elif len(phase_orders) > 1:
                    ohl_types_by_phase_order: Dict[Tuple[int, ...], dev.OverheadLineType] = dict()
                    phase_labels = ("N", "A", "B", "C")
                    for resolved_phase_order in sorted(phase_orders):
                        ohl_type = convert_dgs_to_overhead_line_type_geometrical_parameters(
                            typtow=typtow,
                            typcon_by_id=typcon_raw_dict,
                            wire_by_id=wire_type_dict,
                            default_frequency_hz=frequency,
                            phase_order=list(resolved_phase_order),
                        )
                        phase_suffix = "".join(phase_labels[phase] for phase in resolved_phase_order)
                        ohl_type.name = f"{ohl_type.name}_{phase_suffix}"
                        ohl_type.idtag = f"{tow_id}_{phase_suffix}"
                        ohl_types_by_phase_order[resolved_phase_order] = ohl_type
                        grid.overhead_line_types.append(ohl_type)

                    default_phase_order = sorted(phase_orders)[0]
                    overhead_line_type_dict[tow_id] = ohl_types_by_phase_order[default_phase_order]
                    overhead_line_type_dict[typtow.ID] = ohl_types_by_phase_order[default_phase_order]
                    for line_id, resolved_phase_order in phase_order_by_line_id.items():
                        overhead_line_type_dict[line_id] = ohl_types_by_phase_order[resolved_phase_order]
                    continue
                elif phase_counts == [3, 1]:
                    phase_order = [1, 2, 3, 0]

                ohl_type = convert_dgs_to_overhead_line_type_geometrical_parameters(
                    typtow=typtow,
                    typcon_by_id=typcon_raw_dict,
                    wire_by_id=wire_type_dict,
                    default_frequency_hz=frequency,
                    phase_order=phase_order,
                )
                overhead_line_type_dict[tow_id] = ohl_type
                overhead_line_type_dict[typtow.ID] = ohl_type
                grid.overhead_line_types.append(ohl_type)
            elif typtow.i_mode == 1:
                ohl_type = convert_dgs_to_overhead_line_type_electrical_parameters(
                    typtow=typtow,
                    typcon_by_id=typcon_raw_dict,
                    wire_by_id=wire_type_dict,
                    default_frequency_hz=frequency,
                )
                typlne_dict[tow_id] = ohl_type
                typlne_dict[typtow.ID] = ohl_type
                grid.sequence_line_types.append(ohl_type)
            else:
                logger.add_warning("TypTow i_mode not recognized",
                                   device_class="TypTow",
                                   device_property="i_mode",
                                   value=typtow.i_mode)
        else:
            pass
    return overhead_line_type_dict


def _build_typtr2_templates(dgs_grid: DgsCircuit,
                            grid: dev.MultiCircuit) -> Tuple[Dict[str, dev.TransformerType], Dict[str, TypTr2]]:
    """
    Build typtr2 templates.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :return: Function result.
    """
    typtr2_dict: Dict[str, dev.TransformerType] = dict()
    typtr2_raw_dict: Dict[str, TypTr2] = dict()
    for typtr2 in dgs_grid.typtr2s:
        transformer_type = convert_dgs_to_transformer_type(typtr2=typtr2)
        grid.add_transformer_type(obj=transformer_type)
        typtr2_dict[typtr2.ID] = transformer_type
        typtr2_raw_dict[typtr2.ID] = typtr2
        tid = _ref_id(typtr2.ID)
        if tid is not None:
            typtr2_dict[tid] = transformer_type
            typtr2_raw_dict[tid] = typtr2
        else:
            pass
    return typtr2_dict, typtr2_raw_dict


def _build_typtr3_dict(dgs_grid: DgsCircuit) -> Dict[str, TypTr3]:
    """
    Build typtr3 dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typtr3_dict: Dict[str, TypTr3] = dict()
    for typtr3 in dgs_grid.typtr3s:
        typtr3_dict[typtr3.ID] = typtr3
        tid = _ref_id(typtr3.ID)
        if tid is not None:
            typtr3_dict[tid] = typtr3
        else:
            pass
    return typtr3_dict


def _build_typtr4_dict(dgs_grid: DgsCircuit) -> Dict[str, TypTr4]:
    """
    Build typtr4 dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typtr4_dict: Dict[str, TypTr4] = dict()
    for typtr4 in dgs_grid.typtr4s:
        typtr4_dict[typtr4.ID] = typtr4
        tid = _ref_id(typtr4.ID)
        if tid is not None:
            typtr4_dict[tid] = typtr4
        else:
            pass
    return typtr4_dict


def _build_typsind_dict(dgs_grid: DgsCircuit) -> Dict[str, TypSind]:
    """
    Build typsind dict.

    :param dgs_grid: dgs_grid parameter.
    :return: Function result.
    """
    typsind_raw_dict: Dict[str, TypSind] = dict()
    for typsind in dgs_grid.typsinds:
        typsind_raw_dict[typsind.ID] = typsind
        tid = _ref_id(typsind.ID)
        if tid is not None:
            typsind_raw_dict[tid] = typsind
        else:
            pass
    return typsind_raw_dict


def _build_line_section_type_maps(dgs_grid: DgsCircuit,
                                  logger: Logger) -> Tuple[Dict[str, str], Dict[str, List[ElmLnesec]]]:
    """
    Build line section type maps.

    :param dgs_grid: dgs_grid parameter.
    :param logger: logger parameter.
    :return: Function result.
    """
    line_type_by_line_id: Dict[str, str] = dict()
    line_sections_by_line_id: Dict[str, List[ElmLnesec]] = dict()

    line_ids: Set[str] = set()
    for elmlne in dgs_grid.elmlnes:
        if elmlne.ID != "":
            line_ids.add(elmlne.ID)
            rid = _ref_id(elmlne.ID)
            if rid is not None and rid != "":
                line_ids.add(rid)
            else:
                pass

    folder_parent: Dict[str, str] = dict()
    for folder in dgs_grid.intfolders:
        if folder.ID != "":
            folder_parent[folder.ID] = folder.fold_id
            fid = _ref_id(folder.ID)
            if fid is not None and fid != "":
                folder_parent[fid] = folder.fold_id
            else:
                pass
        else:
            pass

    line_id_by_loc_name: Dict[str, str] = _get_unique_name_mapping(
        lines=dgs_grid.elmlnes,
        use_characteristic_name=False
    )
    line_id_by_chr_name: Dict[str, str] = _get_unique_name_mapping(
        lines=dgs_grid.elmlnes,
        use_characteristic_name=True
    )

    for sec in dgs_grid.elmlnesecs:
        if sec.typ_id != "":
            owner_line_id = _resolve_line_section_owner_id(
                section=sec,
                line_ids=line_ids,
                folder_parent=folder_parent,
                line_id_by_loc_name=line_id_by_loc_name,
                line_id_by_chr_name=line_id_by_chr_name
            )
            if owner_line_id != "":
                typ_id = _ref_id(sec.typ_id) or sec.typ_id
                line_type_by_line_id[owner_line_id] = typ_id

                normalized_owner_id = _ref_id(owner_line_id) or owner_line_id
                line_type_by_line_id[normalized_owner_id] = typ_id

                owned_sections = line_sections_by_line_id.get(normalized_owner_id, None)
                if owned_sections is None:
                    line_sections_by_line_id[normalized_owner_id] = list()
                    owned_sections = line_sections_by_line_id[normalized_owner_id]
                else:
                    pass

                owned_sections.append(sec)
            else:
                logger.add_warning(
                    "Could not resolve owning line for line section.",
                    device=sec.loc_name,
                    device_class="ElmLnesec",
                    value=str(sec.ID)
                )
    return line_type_by_line_id, line_sections_by_line_id


def _build_tower_template_by_line_id(dgs_grid: DgsCircuit,
                                     overhead_line_type_dict: Dict[str, dev.OverheadLineType]) -> Dict[
    str, dev.OverheadLineType]:
    """
    Build tower template by line id.

    :param dgs_grid: dgs_grid parameter.
    :param overhead_line_type_dict: overhead_line_type_dict parameter.
    :return: Function result.
    """
    tower_template_by_line_id: Dict[str, dev.OverheadLineType] = dict()
    for elmtow in dgs_grid.elmtows:
        if len(elmtow.pGeo) != 0:
            geo_ptr = elmtow.pGeo[0]
            if geo_ptr is not None and geo_ptr != "":
                geo_id = _ref_id(geo_ptr)
                if geo_id is not None:
                    ohl_type = overhead_line_type_dict.get(geo_id, None)
                    if ohl_type is None:
                        ohl_type = overhead_line_type_dict.get(geo_ptr, None)
                    if ohl_type is not None:
                        for line_ptr in elmtow.plines:
                            if line_ptr is not None and line_ptr != "":
                                tower_template_by_line_id[line_ptr] = ohl_type
                                lid = _ref_id(line_ptr)
                                if lid is not None and lid != "":
                                    tower_template_by_line_id[lid] = ohl_type
                            else:
                                pass
                    else:
                        pass
                else:
                    pass
            else:
                pass
        else:
            pass
    return tower_template_by_line_id


def _add_elmlne_lines(dgs_grid: DgsCircuit,
                      grid: dev.MultiCircuit,
                      stacubic_dict: Dict[str, List[int]],
                      typlne_dict: Dict[str, dev.SequenceLineType],
                      dc_cable_type_dict: Dict[str, dev.UndergroundLineType],
                      source_line_type_dict: Dict[str, TypLne],
                      overhead_line_type_dict: Dict[str, dev.OverheadLineType],
                      underground_line_type_dict: Dict[str, dev.UndergroundLineType],
                      line_type_by_line_id: Dict[str, str],
                      line_sections_by_line_id: Dict[str, List[ElmLnesec]],
                      tower_template_by_line_id: Dict[str, dev.OverheadLineType],
                      frequency: float,
                      baseMVA: float,
                      logger: Logger,
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus],
                      branch_group_by_id: Dict[str, dev.BranchGroup],
                      phase_map: PhaseMap) -> Dict[str, List[dev.Line]]:
    """
    Add elmlne lines.

    :param dgs_grid: dgs_grid parameter.
    :param grid: grid parameter.
    :param stacubic_dict: stacubic_dict parameter.
    :param typlne_dict: typlne_dict parameter.
    :param dc_cable_type_dict: Complete physical DC cable types by source pointer.
    :param source_line_type_dict: Parsed line types for resistive fallback.
    :param overhead_line_type_dict: overhead_line_type_dict parameter.
    :param underground_line_type_dict: Physical cable systems by source pointer.
    :param line_type_by_line_id: line_type_by_line_id parameter.
    :param line_sections_by_line_id: line_sections_by_line_id parameter.
    :param tower_template_by_line_id: tower_template_by_line_id parameter.
    :param frequency: frequency parameter.
    :param baseMVA: baseMVA parameter.
    :param logger: logger parameter.
    :param cubics_by_objid: cubics_by_objid parameter.
    :param bus_by_term_id: bus_by_term_id parameter.
    :param branch_group_by_id: branch_group_by_id parameter.
    :param phase_map: Resolved terminal-conductor phase map.
    :return: Function result.
    """
    line_by_dgs_id: Dict[str, List[dev.Line]] = dict()
    for elmlne in dgs_grid.elmlnes:
        term_ids: List[str] = get_terminal_ids(element_id=elmlne.ID, cubics_by_objid=cubics_by_objid)
        if len(term_ids) != 2:
            bus_ids: List[int] | None = stacubic_dict.get(_ref_id(elmlne.ID), None)
            if bus_ids is None or len(bus_ids) != 2:
                if len(term_ids) == 1:
                    # A one-ended line is a disconnected source artefact rather
                    # than a partially constructible VeraGrid branch. Record the
                    # intentional omission without presenting it as an import
                    # warning because no invalid object enters the final circuit.
                    logger.add_info(
                        msg="Skipped disconnected one-terminal line",
                        device=f"{elmlne.loc_name}' (ID={elmlne.ID}) ",
                        device_class="ElmLne",
                        value=len(term_ids),
                        expected_value="2",
                    )
                else:
                    # Zero-ended and over-connected branches remain suspicious
                    # source states that users need to review explicitly.
                    logger.add_warning(
                        msg="not connected to exactly 2 terminals",
                        device=f"{elmlne.loc_name}' (ID={elmlne.ID}) ",
                        device_class="ElmLne",
                        value=len(term_ids),
                        expected_value="2",
                    )
                continue
            else:
                pass

        parallel_count = _get_parallel_device_count(count=int(elmlne.nlnum))
        for parallel_index in range(parallel_count):
            line: dev.Line | dev.DcLine = convert_dgs_to_line(
                lne=elmlne,
                buses=grid.buses,
                stacubic_dict=stacubic_dict,
                sequence_templates_dict=typlne_dict,
                dc_cable_type_dict=dc_cable_type_dict,
                source_line_type_dict=source_line_type_dict,
                overhead_line_type_dict=overhead_line_type_dict,
                underground_line_type_dict=underground_line_type_dict,
                line_type_by_line_id=line_type_by_line_id,
                line_sections_by_line_id=line_sections_by_line_id,
                tower_template_by_line_id=tower_template_by_line_id,
                freq=frequency,
                baseMVA=baseMVA,
                logger=logger,
                cubics_by_objid=cubics_by_objid,
                bus_by_term_id=bus_by_term_id,
                phase_map=phase_map,
                parallel_index=parallel_index,
                parallel_count=parallel_count
            )
            fold_id = _ref_id(elmlne.fold_id)
            if fold_id is not None and fold_id != "":
                branch_group = branch_group_by_id.get(fold_id)
                if branch_group is not None:
                    line.group = branch_group
            if isinstance(line, dev.DcLine):
                grid.add_dc_line(obj=line)
            else:
                grid.add_line(obj=line, logger=logger)

            lid_raw = elmlne.ID
            lid = _ref_id(lid_raw)
            if isinstance(line, dev.Line):
                if lid is not None:
                    line_by_dgs_id.setdefault(lid, list()).append(line)
                else:
                    pass
                if lid_raw is not None and lid_raw != "":
                    line_by_dgs_id.setdefault(lid_raw, list()).append(line)
                else:
                    pass
            else:
                pass
    return line_by_dgs_id


def _apply_elmtow_tower_coupling(dgs_grid: DgsCircuit,
                                 line_by_dgs_id: Dict[str, List[dev.Line]],
                                 overhead_line_type_dict: Dict[str, dev.OverheadLineType],
                                 baseMVA: float,
                                 frequency: float,
                                 logger: Logger,
                                 grid: dev.MultiCircuit | None = None) -> None:
    """
    Apply elmtow tower coupling.

    :param dgs_grid: dgs_grid parameter.
    :param line_by_dgs_id: line_by_dgs_id parameter.
    :param overhead_line_type_dict: overhead_line_type_dict parameter.
    :param baseMVA: baseMVA parameter.
    :param frequency: frequency parameter.
    :param logger: logger parameter.
    :param grid: Catalogue receiving physical phase-layout variants.
    :return: Function result.
    """
    for elmtow in dgs_grid.elmtows:
        if int(elmtow.outserv) != 0:
            continue
        if len(elmtow.pGeo) == 0:
            logger.add_warning(
                f"no pGeo specified, skipping tower binding",
                device=f"{elmtow.loc_name}' (ID={elmtow.ID}) ",
                device_class="ElmTow"
            )
            continue

        geo_ptr = elmtow.pGeo[0]
        if geo_ptr is None:
            logger.add_warning(
                f"pGeo[0] is empty, skipping tower binding",
                device=f"{elmtow.loc_name}' (ID={elmtow.ID}) ",
                device_class="ElmTow"
            )
            continue

        geo_id = _ref_id(geo_ptr)
        ohl_type = overhead_line_type_dict.get(geo_id)
        if ohl_type is None:
            ohl_type = overhead_line_type_dict.get(geo_ptr)
        if ohl_type is None:
            logger.add_warning(
                f"referenced tower type not found",
                device=f"{elmtow.loc_name}' (ID={elmtow.ID}) ",
                device_class="ElmTow",
                value=str(geo_ptr)
            )
            continue

        if len(elmtow.dphasing) < len(elmtow.plines):
            logger.add_warning("Missing tower phase arrangement; assuming ABC. Export ElmTow e:dphasing.",
                               device=elmtow.loc_name, device_class="ElmTow")
        else:
            pass
        if any(code < 0 or code > 5 for code in elmtow.dphasing):
            raise ValueError(f"{elmtow.loc_name}: unsupported ElmTow dphasing {elmtow.dphasing}")
        else:
            pass
        complete_section: bool = not any(value != 0 for value in elmtow.ctransp) and len(elmtow.pGeo) == 1
        if not complete_section:
            logger.add_warning("Transposed or multi-section tower coupling is not supported; "
                               "retaining independent line templates.",
                               device=elmtow.loc_name, device_class="ElmTow")
        else:
            pass
        if any(code != 0 for code in elmtow.dphasing):
            # Relabel a catalogue variant; never change the geometry shared by other sections.
            phase_labels: tuple[tuple[int, int, int], ...] = (
                (1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1))
            original: dev.OverheadLineType = ohl_type
            ohl_type = ohl_type.copy(forced_new_idtag=True)
            ohl_type.wires_in_tower.data.clear()
            ohl_type.name = f"{ohl_type.name} ({elmtow.loc_name})"
            for relationship in original.wires_in_tower.data:
                new_phase: int = relationship.phase
                if relationship.phase > 0:
                    circuit: int = (relationship.phase - 1) // 3
                    phase: int = (relationship.phase - 1) % 3
                    code: int = elmtow.dphasing[circuit] if circuit < len(elmtow.dphasing) else 0
                    new_phase = 3 * circuit + phase_labels[code][phase]
                else:
                    pass
                ohl_type.add_wire_relationship(wire=relationship.wire, xpos=relationship.xpos,
                                              ypos=relationship.ypos, phase=new_phase)
            # Existing per-circuit template accessors expect N, then electrical ABC blocks.
            order: np.ndarray = np.argsort([wire.phase for wire in ohl_type.wires_in_tower.data], kind='stable')
            ohl_type.wires_in_tower.data = [ohl_type.wires_in_tower.data[i] for i in order]
            ohl_type.compute()
            if grid is not None:
                grid.overhead_line_types.append(ohl_type)
            else:
                pass
        else:
            pass

        for idx, line_ptr in enumerate(elmtow.plines):
            if line_ptr is None:
                continue
            line_id = _ref_id(line_ptr)
            api_lines = line_by_dgs_id.get(line_id, list())
            if len(api_lines) == 0:
                api_lines = line_by_dgs_id.get(line_ptr, list())
            if len(api_lines) == 0:
                logger.add_warning(
                    f"referenced line type not found",
                    device=f"{elmtow.loc_name}' (ID={elmtow.ID}) ",
                    device_class="ElmTow",
                    value=str(line_ptr)
                )
                continue

            circuit_idx = int(idx) + 1
            for api_line in api_lines:
                try:
                    api_line.set_circuit_idx(val=circuit_idx, obj=ohl_type)
                    api_line.apply_template(obj=ohl_type, Sbase=baseMVA, freq=frequency, logger=logger)
                    if complete_section:
                        api_line.coupling_group = str(elmtow.ID)
                        api_line.coupling_reversed = idx < len(elmtow.dpolar) and elmtow.dpolar[idx] != 0
                    else:
                        pass
                except ValueError as e:
                    logger.add_warning(
                        str(e).strip() or "Failed to apply tower template.",
                        device_class="ElmLne",
                        device=api_line.name
                    )


def dgs_to_circuit(path: str,
                   use_vsc_for_injections: bool = False,
                   use_dynamic_information: bool = False,
                   dynamic_simulation_mode: DynamicSimulationMode | None = None,
                   logger_: Logger | None = None) -> dev.MultiCircuit:
    """
    Dgs to circuit.

    :param path: path parameter.
    :param use_vsc_for_injections: use_vsc_for_injections parameter.
    :param use_dynamic_information: Import dynamic DGS equations when available.
    :param dynamic_simulation_mode: Explicit RMS or EMT destination for imported dynamic models.
    :param logger_: logger_ parameter.
    :return: Function result.
    """
    logger = Logger() if logger_ is None else logger_

    dgs_grid = DgsCircuit()
    dgs_grid.parse_dgs(path)

    grid = dev.MultiCircuit()

    baseMVA = grid.Sbase

    # --- frequency ---
    if len(dgs_grid.elmnets) > 0:
        frnom = dgs_grid.elmnets[0].frnom
        if frnom is None:
            frequency = 50.0
        else:
            frequency = float(frnom)
    else:
        frequency = 50.0

    # StaCubic dictionaries
    sta_cubic_dict, cubics_by_objid = _build_stacubic_mappings(stacubics=dgs_grid.stacubics)
    phase_map = _build_phase_map(stacubics=dgs_grid.stacubics, logger=logger)

    pos_by_objid: Dict[str, Tuple[float, float]] = _build_graphics_positions(intgrfs=dgs_grid.intgrfs)
    area_by_id: Dict[str, dev.Area] = _add_elmarea_areas(dgs_grid=dgs_grid, grid=grid)
    zone_by_id: Dict[str, dev.Zone] = _add_elmzone_zones(dgs_grid=dgs_grid, grid=grid)
    branch_group_by_id: Dict[str, dev.BranchGroup] = _add_elmbranch_groups(dgs_grid=dgs_grid, grid=grid)
    bus_by_term_id: Dict[str, dev.Bus] = add_dgs_terminal_buses(
        dgs_grid=dgs_grid,
        grid=grid,
        pos_by_objid=pos_by_objid,
    )
    _assign_elmterm_area_references(dgs_grid=dgs_grid, bus_by_term_id=bus_by_term_id, area_by_id=area_by_id)
    _assign_elmterm_zone_references(dgs_grid=dgs_grid, bus_by_term_id=bus_by_term_id, zone_by_id=zone_by_id)

    typ_sym_dict: Dict[str, TypSym] = _build_typsym_dict(dgs_grid=dgs_grid)
    typ_asmo_dict: Dict[str, TypAsmo] = _build_typasmo_dict(dgs_grid=dgs_grid)
    typ_switch_dict: Dict[str, TypSwitch] = _build_typswitch_dict(dgs_grid=dgs_grid)

    # switches (PowerFactory/DGS: ElmCoup is the real device; StaCubic resolves connectivity)
    switch_by_cubic_id: Dict[str, StaSwitch] = build_switch_by_cubic_id(staswitchs=dgs_grid.staswitchs)

    _add_elmcoup_switches(
        dgs_grid=dgs_grid,
        grid=grid,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        typ_switch_dict=typ_switch_dict,
        baseMVA=baseMVA,
        logger=logger,
    )

    _add_elmsym_generators(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        typsym_dict=typ_sym_dict,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
    )
    _add_elmasm_generators(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        typasmo_dict=typ_asmo_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
    )
    _add_elmvac_loads(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
    )
    _add_elmlod_loads(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        phase_map=phase_map,
    )
    _add_elmgenstat_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        use_vsc_for_injections=use_vsc_for_injections,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
    )
    # Alex review required: validate the bipolar VSC for balanced/three-phase load flow and short circuit.
    _add_elmvsc_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        frequency_hz=frequency,
    )
    # Alex review required: validate the monopolar VSC for balanced/three-phase load flow and short circuit.
    _add_elmvscmono_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        frequency_hz=frequency,
    )
    _add_elmxnet_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
    )
    _add_elmshnt_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        phase_map=phase_map,
        frequency=frequency,
    )
    _add_elmsvs_devices(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        use_vsc_for_injections=use_vsc_for_injections,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
    )

    # Loads (LV)
    if len(dgs_grid.elmlodlvs) > 0 or len(dgs_grid.elmlodlvps) > 0:
        logger.add_warning(
            f"ElmLodlv/ElmLodlvp found but no P/Q fields available in DGS schema",
            device_class="ElmLodlv/ElmLodlvp",
        )

    typ_lne_dict: Dict[str, dev.SequenceLineType]
    dc_cable_type_dict: Dict[str, dev.UndergroundLineType]
    source_line_type_dict: Dict[str, TypLne]
    typ_lne_dict, dc_cable_type_dict, source_line_type_dict = _build_typlne_templates(
        dgs_grid=dgs_grid,
        grid=grid,
        logger=logger,
    )
    underground_cable_type_dict: Dict[str, dev.UndergroundCableType] = _build_typcab_catalogue(
        dgs_grid=dgs_grid,
        grid=grid,
        logger=logger,
    )
    underground_line_type_dict: Dict[str, dev.UndergroundLineType] = _build_typcabsys_templates(
        dgs_grid=dgs_grid,
        grid=grid,
        cable_type_dict=underground_cable_type_dict,
        logger=logger,
    )
    typ_con_raw_dict, wire_type_dict = _build_typcon_catalogues(dgs_grid=dgs_grid, grid=grid)
    overhead_line_type_dict: Dict[str, dev.OverheadLineType] = _add_typtow_templates(
        dgs_grid=dgs_grid,
        grid=grid,
        typcon_raw_dict=typ_con_raw_dict,
        wire_type_dict=wire_type_dict,
        typlne_dict=typ_lne_dict,
        cubics_by_objid=cubics_by_objid,
        phase_map=phase_map,
        frequency=frequency,
        logger=logger,
    )
    typtr2_dict, typtr2_raw_dict = _build_typtr2_templates(dgs_grid=dgs_grid, grid=grid)
    typtr3_dict: Dict[str, TypTr3] = _build_typtr3_dict(dgs_grid=dgs_grid)
    typtr4_dict: Dict[str, TypTr4] = _build_typtr4_dict(dgs_grid=dgs_grid)
    typ_sind_raw_dict: Dict[str, TypSind] = _build_typsind_dict(dgs_grid=dgs_grid)

    # ------------------------------------------------------------
    # Fallback map: ElmLne.ID -> typ_id from ElmLnesec
    # Some PowerFactory exports omit ElmLne.typ_id and store it in ElmLnesec.typ_id.
    # In some cases, ElmLnesec.fold_id references an IntFolder chain; we climb until we reach an ElmLne.
    # ------------------------------------------------------------
    line_type_by_line_id, line_sections_by_line_id = _build_line_section_type_maps(
        dgs_grid=dgs_grid,
        logger=logger,
    )

    # ------------------------------------------------------------
    # Tower coupling helper: ElmTow may define the line template (TypTow) instead of ElmLne.typ_id.
    # We build a direct mapping Line.ID -> OverheadLineType so convert_dgs_to_line can proceed
    # even when typ_id is missing, and apply the proper template immediately.
    # ------------------------------------------------------------
    tower_template_by_line_id: Dict[str, dev.OverheadLineType] = _build_tower_template_by_line_id(
        dgs_grid=dgs_grid,
        overhead_line_type_dict=overhead_line_type_dict,
    )

    line_by_dgs_id: Dict[str, List[dev.Line]] = _add_elmlne_lines(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        typlne_dict=typ_lne_dict,
        dc_cable_type_dict=dc_cable_type_dict,
        source_line_type_dict=source_line_type_dict,
        overhead_line_type_dict=overhead_line_type_dict,
        underground_line_type_dict=underground_line_type_dict,
        line_type_by_line_id=line_type_by_line_id,
        line_sections_by_line_id=line_sections_by_line_id,
        tower_template_by_line_id=tower_template_by_line_id,
        frequency=frequency,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        branch_group_by_id=branch_group_by_id,
        phase_map=phase_map,
    )
    _apply_elmtow_tower_coupling(
        dgs_grid=dgs_grid,
        line_by_dgs_id=line_by_dgs_id,
        overhead_line_type_dict=overhead_line_type_dict,
        baseMVA=baseMVA,
        frequency=frequency,
        logger=logger,
        grid=grid,
    )

    _add_elmzpu_series_reactances(
        dgs_grid=dgs_grid,
        grid=grid,
        bus_by_term_id=bus_by_term_id,
        stacubic_dict=sta_cubic_dict,
        cubics_by_objid=cubics_by_objid,
        logger=logger,
        baseMVA=baseMVA,
        branch_group_by_id=branch_group_by_id,
    )
    _add_elmscap_series_reactances(
        dgs_grid=dgs_grid,
        grid=grid,
        bus_by_term_id=bus_by_term_id,
        stacubic_dict=sta_cubic_dict,
        cubics_by_objid=cubics_by_objid,
        logger=logger,
        baseMVA=baseMVA,
        branch_group_by_id=branch_group_by_id,
    )
    _add_elmsind_series_reactances(
        dgs_grid=dgs_grid,
        grid=grid,
        bus_by_term_id=bus_by_term_id,
        stacubic_dict=sta_cubic_dict,
        cubics_by_objid=cubics_by_objid,
        typsind_raw_dict=typ_sind_raw_dict,
        logger=logger,
        baseMVA=baseMVA,
        branch_group_by_id=branch_group_by_id,
    )
    _add_elmtr2_transformers(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        typtr2_dict=typtr2_dict,
        typtr2_raw_dict=typtr2_raw_dict,
        frequency=frequency,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
        phase_map=phase_map,
    )
    _add_elmtr3_transformers(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        typtr3_dict=typtr3_dict,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
    )

    _add_elmtr4_transformers(
        dgs_grid=dgs_grid,
        grid=grid,
        stacubic_dict=sta_cubic_dict,
        typtr4_dict=typtr4_dict,
        baseMVA=baseMVA,
        logger=logger,
        cubics_by_objid=cubics_by_objid,
        bus_by_term_id=bus_by_term_id,
        switch_by_cubic_id=switch_by_cubic_id,
        branch_group_by_id=branch_group_by_id,
    )

    if use_dynamic_information:
        if dynamic_simulation_mode is None:
            logger.add_error(
                msg=(
                    "DGS dynamic model import requires an explicit RMS or EMT "
                    "simulation mode"
                ),
            )
        else:
            # 1: Convert each DGS root to its final template, register it in
            # MultiCircuit and retain only the irreducible root-FID lookup.
            conversion_result: DgsDynamicTemplateConversionResult = (
                convert_and_add_dgs_dynamic_templates_to_circuit(
                    dgs_circuit=dgs_grid,
                    circuit=grid,
                    target_domain=dynamic_simulation_mode,
                    logger=logger,
                )
            )
            templates_by_root_dgs_id: Dict[
                str,
                RmsModelTemplate | EmtModelTemplate,
            ] = conversion_result.templates_by_root_dgs_id

            # 2: Apply the registered templates to exact static devices using
            # that minimal lookup and the original declarative FID relations.
            apply_dgs_dynamic_templates_to_devices(
                dgs_circuit=dgs_grid,
                circuit=grid,
                templates_by_root_dgs_id=templates_by_root_dgs_id,
                logger=logger,
            )

            if dynamic_simulation_mode == DynamicSimulationMode.RMS:
                # Narrow the domain explicitly so logical actuator completion
                # cannot consume an EMT template through the shared lookup.
                rms_templates_by_root_dgs_id: Dict[str, RmsModelTemplate] = dict(
                    (root_id, template)
                    for root_id, template in templates_by_root_dgs_id.items()
                    if isinstance(template, RmsModelTemplate)
                )

                # RMS completion is not a third template-transfer stage. It
                # fills only empty electrical shells, then binds exact native
                # measurement FIDs to the already assigned controller block.
                external_grid_source_ids: Set[str] = set()
                external_grid_source: ElmXnet
                for external_grid_source in dgs_grid.elmxnets:
                    if external_grid_source.ID == "":
                        pass
                    else:
                        external_grid_source_ids.add(external_grid_source.ID)
                elm_gen_stat_source_ids: Set[str] = set()
                elm_gen_stat_source: ElmGenstat
                for elm_gen_stat_source in dgs_grid.elmgenstats:
                    if elm_gen_stat_source.ID == "":
                        pass
                    else:
                        elm_gen_stat_source_ids.add(elm_gen_stat_source.ID)
                elm_sym_source_ids: Set[str] = set()
                elm_sym_reference_source_ids: Set[str] = set()
                elm_sym_source: ElmSym
                for elm_sym_source in dgs_grid.elmsyms:
                    if elm_sym_source.ID == "":
                        pass
                    else:
                        elm_sym_source_ids.add(elm_sym_source.ID)
                        if int(elm_sym_source.ip_ctrl) == 1:
                            elm_sym_reference_source_ids.add(elm_sym_source.ID)
                        else:
                            pass
                typeless_elmlod_source_ids: Set[str] = set()
                elmlod_source: ElmLod
                for elmlod_source in dgs_grid.elmlods:
                    if (
                            elmlod_source.ID != ""
                            and _ref_id(elmlod_source.typ_id) in {None, ""}
                    ):
                        typeless_elmlod_source_ids.add(elmlod_source.ID)
                    else:
                        pass
                prepare_dgs_circuit_for_rms(
                    circuit=grid,
                    external_grid_source_ids=external_grid_source_ids,
                    logger=logger,
                    elmgenstat_source_ids=elm_gen_stat_source_ids,
                    elmsym_source_ids=elm_sym_source_ids,
                    elmsym_reference_source_ids=elm_sym_reference_source_ids,
                    typeless_elmlod_source_ids=typeless_elmlod_source_ids,
                )
                # Passive shells exist now, so exported meter FIDs can place
                # omitted valve terminals on their exact electrical rails.
                prepared_actuator_count: int = prepare_dgs_logical_actuator_topology(
                    circuit=grid,
                    dgs_circuit=dgs_grid,
                    templates_by_root_dgs_id=rms_templates_by_root_dgs_id,
                    logger=logger,
                )

                # Finalize early meter outputs against the prepared physical
                # topology before actuator runtime consumes their signals.
                bind_dgs_rms_measurements(
                    circuit=grid,
                    dgs_circuit=dgs_grid,
                    templates_by_root_dgs_id=templates_by_root_dgs_id,
                    child_blocks_by_root_and_slot_id=conversion_result.child_blocks_by_root_and_slot_id,
                    logger=logger,
                )
                bound_actuator_count: int = bind_dgs_logical_actuator_runtime(
                    circuit=grid,
                    templates_by_root_dgs_id=rms_templates_by_root_dgs_id,
                    logger=logger,
                )
                if 0 < prepared_actuator_count == bound_actuator_count:
                    release_dgs_logical_actuator_import_context(circuit=grid)
                else:
                    if bound_actuator_count != prepared_actuator_count:
                        logger.add_warning(
                            msg="DGS logical actuator import context retained after incomplete binding",
                            value=bound_actuator_count,
                            expected_value=prepared_actuator_count,
                        )
                    else:
                        pass
                bind_dgs_switch_event_runtime(
                    circuit=grid,
                    templates_by_root_dgs_id=templates_by_root_dgs_id,
                    logger=logger,
                )
            else:
                pass
    else:
        pass

    return grid
