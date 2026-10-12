# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import math
from typing import Dict, List, Tuple

import numpy as np

import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import *
from VeraGridEngine.enumerations import (
    ExternalGridMode,
    SwitchGraphicType,
    TapChangerTypes,
    TapModuleControl,
    WindingType,
    ShuntControlMode,
    GeneratorControlMode
)
from VeraGridEngine.Devices.Branches.transformer_type import reverse_transformer_short_circuit_study

SQRT3 = np.sqrt(3)


def _winding_type_to_pf_code(winding_type: WindingType) -> str:
    """
    Convert a VeraGrid winding connection to the PowerFactory/DGS code.

    :param winding_type: VeraGrid winding connection
    :return: PowerFactory connection code
    """
    conversion_dict: Dict[WindingType, str] = {
        WindingType.FloatingStar: "Y",
        WindingType.NeutralStar: "Y",
        WindingType.GroundedStar: "YN",
        WindingType.Delta: "D",
        WindingType.FloatingZigZag: "Z",
        WindingType.NeutralZigZag: "ZN",
    }
    return conversion_dict.get(winding_type, "Y")


def _switch_graphic_type_to_pf_usage(graphic_type: SwitchGraphicType) -> Tuple[int, str]:
    """
    Convert a VeraGrid switch graphic type into PowerFactory usage fields.

    :param graphic_type: VeraGrid graphic type
    :return: Tuple with iUse and aUsage
    """
    if graphic_type == SwitchGraphicType.Disconnector:
        return 1, "DIS"
    else:
        return 0, "CBK"


def _add_element_cubicles_with_state(
        dgs_grid: DgsCircuit,
        element_id: str,
        dgs_buses: List[ElmTerm],
        switch_state: int | None = None,
        switch_type_id: str = "",
        switch_iuse: int = 0,
        switch_usage: str = "CBK",
) -> None:
    """
    Add cubicles and patch the generated StaSwitch state metadata.

    :param dgs_grid: Target DGS circuit
    :param element_id: DGS element ID
    :param dgs_buses: Connected buses
    :param switch_state: Optional cubicle switch state
    :param switch_type_id: Optional TypSwitch pointer
    :param switch_iuse: StaSwitch use code
    :param switch_usage: StaSwitch usage string
    :return: None
    """
    switch_count_before: int = len(dgs_grid.staswitchs)
    dgs_grid.add_element_cubicles(element_id=element_id, dgs_buses=dgs_buses)
    if switch_state is None:
        return
    else:
        pass

    new_switches: List[StaSwitch] = dgs_grid.staswitchs[switch_count_before:]
    for sta_switch in new_switches:
        sta_switch.on_off = int(switch_state)
        sta_switch.typ_id = switch_type_id
        sta_switch.iUse = int(switch_iuse)
        sta_switch.aUsage = switch_usage


def _get_bus_voltage_for_branch(bus_from: dev.Bus, bus_to: dev.Bus) -> float:
    """
    Return the representative nominal voltage for a two-terminal branch.

    :param bus_from: From bus
    :param bus_to: To bus
    :return: Nominal voltage in kV
    """
    return max(float(bus_from.Vnom), float(bus_to.Vnom))


def _get_bus_voltage_for_injection(bus: dev.Bus) -> float:
    """
    Return the nominal voltage of an injection bus.

    :param bus: Connection bus
    :return: Nominal voltage in kV
    """
    return float(bus.Vnom)


def _get_tap_phase_step_angle(tc_type: TapChangerTypes, asymmetry_angle_deg: float) -> float:
    """
    Convert a VeraGrid tap changer mode into the PowerFactory ``phitr`` angle.

    :param tc_type: VeraGrid tap changer type
    :param asymmetry_angle_deg: VeraGrid asymmetry angle in degrees
    :return: PowerFactory tap phase step angle in degrees
    """
    if tc_type == TapChangerTypes.Asymmetrical:
        return float(asymmetry_angle_deg)
    elif tc_type == TapChangerTypes.Symmetrical:
        return 180.0
    else:
        return 0.0


def _set_tr2_type_connections_from_branch(tr: dev.Transformer2W, tpe: TypTr2) -> None:
    """
    Fill the DGS 2W transformer connection fields from the branch orientation.

    :param tr: VeraGrid transformer
    :param tpe: DGS type to populate
    :return: None
    """
    from_voltage, to_voltage, hv_at_from = tr.get_from_to_nominal_voltages()
    if abs(float(from_voltage) - float(to_voltage)) <= 1e-9:
        hv_at_from = True
    else:
        pass
    if hv_at_from:
        hv_connection: WindingType = tr.conn_f
        lv_connection: WindingType = tr.conn_t
    else:
        hv_connection = tr.conn_t
        lv_connection = tr.conn_f

    tpe.tr2cn_h = _winding_type_to_pf_code(hv_connection)
    tpe.tr2cn_l = _winding_type_to_pf_code(lv_connection)
    tpe.nt2ag = float(tr.vector_group_number)


def _set_tr2_tap_control_fields_from_vgrid(tr: dev.Transformer2W, element: ElmTr2, t: int | None) -> None:
    """
    Fill the DGS transformer control fields from the VeraGrid branch control state.

    :param tr: VeraGrid transformer
    :param element: DGS transformer element
    :return: None
    """
    if tr.get_tap_module_control_mode_at(t) == TapModuleControl.Vm:
        element.ntrcn = 1
        element.usetp = float(tr.get_vset_at(t))
    else:
        element.ntrcn = 0
        element.usetp = 1.0

    element.usp_low = 0.99
    element.usp_up = 1.01
    element.t2ldc = 0


def _get_tr3_winding_tap_fields_from_vgrid(winding: dev.Winding) -> Tuple[int, int, int, int, float, float]:
    """
    Export a VeraGrid winding tap changer into PowerFactory 3W winding tap fields.

    :param winding: VeraGrid internal winding
    :return: ``(current_position, minimum_position, maximum_position, neutral_position, step_percent, phase_angle)``
    """
    total_positions: int = int(winding.tap_changer.total_positions)
    if total_positions <= 0:
        minimum_position: int = 0
        maximum_position: int = 0
        neutral_position: int = 0
        current_position: int = 0
    else:
        minimum_position = 0
        maximum_position = total_positions - 1
        neutral_position = int(winding.tap_changer.neutral_position)
        current_position = int(winding.tap_changer.tap_position)

    step_percent: float = float(winding.tap_changer.dV) * 100.0
    phase_angle: float = _get_tap_phase_step_angle(
        tc_type=winding.tap_changer.tc_type,
        asymmetry_angle_deg=float(winding.tap_changer.asymmetry_angle),
    )
    return int(current_position), int(minimum_position), int(maximum_position), int(
        neutral_position), step_percent, phase_angle


def _get_transformer3w_side_sort_key(
        side_data: Tuple[dev.Bus, dev.Winding, float, float, float, float, float, float]
) -> float:
    """
    Return the nominal-voltage sort key for a 3W transformer side.

    :param side_data: 3W side tuple used by the exporter
    :return: Connected bus nominal voltage in kV
    """
    return float(side_data[0].Vnom)


def _get_line_export_length(line: dev.Line) -> float:
    """
    Return the DGS-exported line length.

    :param line: VeraGrid line
    :return: Export length in km
    """
    if float(line.length) > 0.0:
        return float(line.length)
    else:
        return 1.0


def _build_sequence_line_type_from_branch(
        line: dev.Line,
        new_id: str,
        sbase_mva: float,
        t: int | None,
) -> TypLne:
    """
    Build a DGS line type from a VeraGrid line object.

    :param line: VeraGrid line
    :param new_id: DGS type ID
    :param sbase_mva: Circuit base power in MVA
    :param t: Optional time index
    :return: DGS line type
    """
    export_length: float = _get_line_export_length(line=line)
    line_voltage_kv: float = float(line.get_max_bus_nominal_voltage())
    rated_current_ka: float = 1.0

    line_rate_mva: float = float(line.get_rate_at(t))
    if line_voltage_kv > 0.0 and line_rate_mva > 0.0:
        rated_current_ka = line_rate_mva / (SQRT3 * line_voltage_kv)
    else:
        pass

    sequence_line = dev.SequenceLineType(
        name=f"{line.name}_type",
        Imax=rated_current_ka,
        Vnom=line_voltage_kv,
        R=float(line.R) / export_length,
        X=float(line.X) / export_length,
        B=float(line.B) / export_length,
        R0=float(line.R0) / export_length,
        X0=float(line.X0) / export_length,
        B0=float(line.B0) / export_length,
    )

    if line_voltage_kv > 0.0 and float(sbase_mva) > 0.0:
        zbase: float = (line_voltage_kv * line_voltage_kv) / float(sbase_mva)
        ybase: float = 1.0 / zbase

        sequence_line.R *= zbase
        sequence_line.X *= zbase
        sequence_line.R0 *= zbase
        sequence_line.X0 *= zbase
        sequence_line.B *= ybase * 1e6
        sequence_line.B0 *= ybase * 1e6
    else:
        pass

    return convert_sequence_line(seq=sequence_line, new_id=new_id)


def _get_transformer_export_nominal_power(transformer: dev.Transformer2W, sbase_mva: float, t: int | None) -> float:
    """
    Return the nominal transformer rating to use when exporting short-circuit data.

    :param transformer: VeraGrid transformer
    :param sbase_mva: Circuit base power in MVA
    :param t: Optional time index
    :return: Nominal transformer power in MVA
    """
    nominal_power: float = float(transformer.Sn)
    if nominal_power <= 0.0:
        nominal_power = float(transformer.get_rate_at(t))
    else:
        pass
    if nominal_power <= 0.0:
        nominal_power = float(sbase_mva)
    else:
        pass

    return nominal_power


def _convert_branch_impedance_to_elm_sind(
        branch: dev.SeriesReactance,
        new_id: str,
        fold_id: str,
        sbase_mva: float,
        t: int | None,
) -> ElmSind:
    """
    Convert a VeraGrid series reactance into a DGS ``ElmSind``.

    :param branch: VeraGrid series reactance
    :param new_id: DGS element ID
    :param fold_id: Parent folder ID
    :param sbase_mva: Circuit base power in MVA
    :return: DGS series impedance element
    """
    element = ElmSind()
    element.ID = new_id
    element.loc_name = branch.name
    element.fold_id = fold_id

    bus_voltage_kv: float = _get_bus_voltage_for_branch(branch.bus_from, branch.bus_to)
    z_pu: float = math.sqrt(float(branch.R) * float(branch.R) + float(branch.X) * float(branch.X))

    element.ucn = bus_voltage_kv
    element.Sn = float(sbase_mva)
    element.uk = 100.0 * z_pu
    element.Pcu = float(branch.R) * float(sbase_mva) * 1000.0
    element.outserv = 0 if branch.get_active_at(t) else 1

    return element


def _convert_switch_to_dgs_type(
        switch: dev.Switch,
        new_id: str,
        fold_id: str,
        sbase_mva: float,
        t: int | None,
) -> TypSwitch:
    """
    Convert a VeraGrid switch electrical data into a DGS ``TypSwitch``.

    :param switch: VeraGrid switch
    :param new_id: DGS type ID
    :param fold_id: Parent folder ID
    :param sbase_mva: Circuit base power in MVA
    :param t: Optional time index
    :return: DGS switch type
    """
    typ_switch = TypSwitch()
    typ_switch.ID = new_id
    typ_switch.loc_name = f"{switch.name} type"
    typ_switch.fold_id = fold_id

    bus_voltage_kv: float = _get_bus_voltage_for_branch(switch.bus_from, switch.bus_to)
    zbase: float
    if bus_voltage_kv > 0.0:
        zbase = (bus_voltage_kv * bus_voltage_kv) / float(sbase_mva)
    else:
        zbase = 0.0

    if zbase > 0.0:
        typ_switch.Ron = float(switch.R) * zbase
        typ_switch.Xon = float(switch.X) * zbase
    else:
        typ_switch.Ron = 0.0
        typ_switch.Xon = 0.0

    rated_current: float = float(switch.rated_current)
    if rated_current <= 0.0 and bus_voltage_kv > 0.0:
        rated_current = float(switch.get_rate_at(t)) / (SQRT3 * bus_voltage_kv)
    else:
        pass

    typ_switch.InomA = rated_current
    typ_switch.InomB = rated_current
    return typ_switch


def convert_bus(bus: dev.Bus, new_id: str, t: int | None = None) -> ElmTerm:
    """

    :param bus:
    :param new_id:
    :param t:
    :return:
    """
    elm_term = ElmTerm()
    elm_term.ID = new_id
    elm_term.loc_name = bus.name
    elm_term.uknom = bus.Vnom
    elm_term.unknom = bus.Vnom / SQRT3
    elm_term.vtarget = float(bus.Vm0)
    elm_term.outserv = 0 if bus.get_active_at(t) else 1

    if bus.get_is_slack_at(t):
        elm_term.bustp = "SL"
    else:
        pass

    return elm_term


def convert_bus_graphic(elm_term, bus: dev.Bus, new_id: str) -> IntGrf:
    """

    :param elm_term:
    :param bus:
    :param new_id:
    :return:
    """
    # opcional: IntGrf para posición
    int_grf = IntGrf()
    int_grf.ID = new_id
    int_grf.pDataObj = elm_term.ID
    int_grf.rCenterX = bus.x
    int_grf.rCenterY = bus.y

    return int_grf


def convert_shunt(shunt: dev.Shunt, new_id: str, ushnm_kv: float, t: int | None = None) -> ElmShnt:
    """
    Export VeraGrid fixed Shunt to PowerFactory ElmShnt.

    VeraGrid:
      - G in MW @ v=1 p.u.
      - B in MVAr @ v=1 p.u. (positive capacitive, negative inductive)

    DGS (ElmShnt) fields used by our importer:
      - shtype: 1 reactor, 2 capacitor
      - qtotn: total rated MVAr magnitude (usually stored as magnitude in PF)
      - qcapn/ncapa (capacitor steps) and qrean (reactor) as fallback
    """
    e = ElmShnt()
    e.ID = new_id
    e.loc_name = shunt.name

    g_mw = float(shunt.get_G_at(t))
    b_mvar = float(shunt.get_B_at(t))

    # Nominal voltage of the connection bus (kV)
    e.ushnm = float(ushnm_kv)

    # Technology / type (match typical PF export style)
    e.ctech = 1

    # Capacitor vs reactor (sign convention)
    if b_mvar >= 0.0:
        e.shtype = 2  # capacitor
        e.qcapn = abs(b_mvar)
        e.ncapx = 1
        e.ncapa = 1
        e.qrean = 0.0
    else:
        e.shtype = 1  # reactor
        e.qcapn = 0.0
        e.ncapx = 1
        e.ncapa = 1
        e.qrean = abs(b_mvar)

    # Total MVAr magnitude (importer prefers this when != 0)
    e.qtotn = abs(b_mvar)

    # Fixed shunt (not switchable by default)
    e.iswitch = 0

    # Frequency (optional but sane)
    e.fres = 50.0

    # Active losses are not represented in this common PF DGS shunt model.
    e.greaf0 = 0.0
    e.grea = 0.0

    if b_mvar > 0.0:
        if abs(b_mvar) > 1e-12:
            e.tandc = abs(g_mw) / abs(b_mvar)
        else:
            e.tandc = 0.0
    else:
        e.tandc = 0.0
        if abs(g_mw) > 1e-12:
            e.grea = abs(b_mvar) / abs(g_mw)
        else:
            e.grea = 0.0

    e.outserv = 0 if shunt.get_active_at(t) else 1
    return e


def convert_load(load: dev.Load, new_id: str, t: int | None = None) -> ElmLod:
    """

    :param load:
    :param new_id:
    :param t:
    :return:
    """
    e = ElmLod()
    e.ID = new_id
    e.loc_name = load.name
    e.plini = float(load.get_P_at(t))
    e.qlini = float(load.get_Q_at(t))
    e.scale0 = 1.0
    e.outserv = 0 if load.get_active_at(t) else 1

    return e


def convert_static_gen(stagen: dev.StaticGenerator, new_id: str, t: int | None = None) -> ElmGenstat:
    """

    :param stagen:
    :param new_id:
    :param t:
    :return:
    """
    e = ElmGenstat()
    e.ID = new_id
    e.loc_name = stagen.name
    e.pgini = float(stagen.get_P_at(t))
    e.qgini = float(stagen.get_Q_at(t))
    e.scale0 = 1.0
    e.outserv = 0 if stagen.get_active_at(t) else 1
    e.ngnum = 1
    e.cosn = stagen.get_Pf_at(t)
    e.sgn = stagen.Snom if stagen.Snom > 0 else 9999.0

    return e


def convert_gen_to_static_gen(gen: dev.Generator, new_id: str, t: int | None = None) -> ElmGenstat:
    """

    :param gen:
    :param new_id:
    :param t:
    :return:
    """
    e = ElmGenstat()
    e.ID = new_id
    e.loc_name = gen.name
    e.pgini = float(gen.get_P_at(t))
    e.qgini = float(gen.get_Q_at(t))
    e.scale0 = 1.0
    e.outserv = 0 if gen.get_active_at(t) else 1
    e.ngnum = 1
    e.cosn = gen.get_Pf_at(t)
    e.sgn = gen.Snom if gen.Snom > 0 else 9999.0

    return e


def convert_battery(batt: dev.Battery, new_id: str, t: int | None = None) -> ElmGenstat:
    """

    :param batt:
    :param new_id:
    :param t:
    :return:
    """
    e = ElmGenstat()
    e.ID = new_id
    e.loc_name = batt.name
    e.pgini = float(batt.get_P_at(t))
    e.qgini = float(batt.get_Q_at(t))
    e.scale0 = 1.0
    e.outserv = 0 if batt.get_active_at(t) else 1
    e.cCategory = "stor"
    e.ngnum = 1
    e.cosn = batt.get_Pf_at(t)
    e.sgn = batt.Snom if batt.Snom > 0 else 9999.0

    return e


def convert_generator(gen: dev.Generator, tpe_new_id: str, new_id: str,
                      Sbase: float, t: int | None) -> Tuple[TypSym, ElmSym]:
    """

    :param gen:
    :param tpe_new_id:
    :param new_id:
    :param Sbase:
    :param t:
    :return:
    """
    # Generate a fake TypSym
    tpe = TypSym()
    tpe.ID = tpe_new_id
    tpe.loc_name = gen.name
    tpe.ugn = gen.bus.Vnom
    tpe.cosn = gen.get_Pf_at(t)
    tpe.nphase = 3
    tpe.sgn = 0.01 if gen.Snom == 0 else gen.Snom

    e = ElmSym()
    e.ID = new_id
    e.loc_name = gen.name
    e.ngnum = 1
    e.outserv = 0 if gen.get_active_at(t) else 1
    e.pgini = gen.get_P_at(t)

    # DGS/PowerFactory convention: qgini is reactive power injection.
    q = float(gen.get_Q_at(t))

    # If Q is not stored in VeraGrid (often 0.0), approximate it from P and power factor.
    if abs(q) < 1e-12:
        p = float(e.pgini)
        pf = abs(gen.get_Pf_at(t))
        if 0.0 < pf < 1.0 and abs(p) > 0.0:
            q_abs = abs(p) * math.tan(math.acos(pf))
            q = q_abs
        else:
            pass
    else:
        pass

    e.qgini = q

    e.q_min = gen.get_Qmin_at(t) / Sbase
    e.q_max = gen.get_Qmax_at(t) / Sbase
    e.usetp = gen.get_Vset_at(t)
    if gen.bus is not None:
        e.ip_ctrl = 1 if gen.bus.get_is_slack_at(t) else 0
    else:
        e.ip_ctrl = 0
    e.typ_id = tpe.ID
    e.Pmin_uc = gen.get_Pmin_at(t)
    e.Pmax_uc = gen.get_Pmax_at(t)

    e.av_mode = "constv" if gen.control_mode == GeneratorControlMode.V else "constq"

    return tpe, e


def convert_sequence_line(seq: dev.SequenceLineType, new_id: str) -> TypLne:
    """

    :param seq:
    :param new_id:
    :return:
    """
    typlne = TypLne()
    typlne.ID = new_id

    typlne.loc_name = seq.name
    typlne.rline = seq.R
    typlne.xline = seq.X
    typlne.bline = seq.B
    typlne.gline = seq.G

    if seq.use_conductance:
        typlne.cline = seq.Cnf
    else:
        typlne.cline = 0.0

    typlne.bline0 = seq.B0 if seq.B0 > 0 else 2 * seq.B
    typlne.gline0 = seq.G0 if seq.G0 > 0 else 2 * seq.G

    if seq.use_conductance:
        typlne.cline0 = seq.Cnf0 if seq.Cnf0 > 0 else 2 * seq.Cnf
    else:
        typlne.cline0 = 0.0

    typlne.rline0 = seq.R0 if seq.R0 > 0 else 2 * seq.R
    typlne.xline0 = seq.X0 if seq.X0 > 0 else 2 * seq.X

    typlne.uline = seq.Vnom
    typlne.sline = seq.Imax
    typlne.InomAir = seq.Imax
    typlne.aohl_ = "cab"

    return typlne


def convert_dc_cable_type(cable_type: dev.UndergroundLineType,
                          new_id: str,
                          frequency_hz: float, conductor: int = 1) -> TypLne:
    """
    Convert one Cable System DC equivalent to PowerFactory quantities.

    The DGS representation stores inductive and capacitive construction data
    as reactance and susceptance at its declared reference frequency. VeraGrid
    obtains H/km and F/km from the common Cable System DC parameter API.

    :param cable_type: Common Cable System.
    :param conductor: One-based global conductor number.
    :param new_id: Destination DGS identifier.
    :param frequency_hz: Positive DGS reference frequency in Hz.
    :return: PowerFactory DC line type.
    """
    resistance, inductance, capacitance = cable_type.get_dc_parameters(conductor)
    typlne: TypLne = TypLne()
    typlne.ID = new_id
    typlne.loc_name = cable_type.name
    typlne.uline = float(cable_type.Vnom)
    typlne.sline = float(cable_type.Imax)
    typlne.InomAir = float(cable_type.Imax)
    typlne.aohl_ = "cab"
    typlne.aohl_declared = True
    typlne.cohl_ = 0
    typlne.cohl_declared = True
    typlne.rline = resistance
    typlne.systp = 1
    typlne.nlnph = 1
    typlne.frnom = float(frequency_hz)

    has_valid_frequency: bool = (
        math.isfinite(frequency_hz)
        and frequency_hz > 0.0
    )
    if has_valid_frequency:
        angular_frequency: float = 2.0 * math.pi * frequency_hz
        typlne.xline = angular_frequency * inductance
        typlne.cline = capacitance * 1.0e6
        typlne.bline = (
            angular_frequency * capacitance * 1.0e6
        )
    else:
        typlne.xline = None
        typlne.cline = None
        typlne.bline = None
    return typlne


def build_resistive_dc_line_type(line: dev.DcLine,
                                 new_id: str,
                                 system_base_mva: float,
                                 frequency_hz: float) -> TypLne:
    """
    Build a DGS type for a resistive DC line without inventing cable energy.

    :param line: DC line without a registered physical cable template.
    :param new_id: Destination DGS identifier.
    :param system_base_mva: VeraGrid system power base in MVA.
    :param frequency_hz: DGS reference frequency in Hz.
    :return: DC line type containing resistance and blank L/C source fields.
    """
    typlne: TypLne = TypLne()
    typlne.ID = new_id
    typlne.loc_name = f"{line.name} resistive type"
    line_voltage: float = line.get_max_bus_nominal_voltage()
    line_length: float = float(line.length)
    has_valid_base: bool = (
        math.isfinite(system_base_mva)
        and system_base_mva > 0.0
        and math.isfinite(line_voltage)
        and line_voltage > 0.0
        and math.isfinite(line_length)
        and line_length > 0.0
    )
    if has_valid_base:
        impedance_base: float = line_voltage * line_voltage / system_base_mva
        typlne.rline = float(line.R) * impedance_base / line_length
        typlne.uline = line_voltage
    else:
        typlne.rline = None
        typlne.uline = None
    typlne.sline = None
    typlne.InomAir = None
    typlne.aohl_ = "cab"
    typlne.xline = None
    typlne.cline = None
    typlne.bline = None
    typlne.systp = 1
    typlne.nlnph = 1
    typlne.frnom = float(frequency_hz)
    return typlne


def convert_transformer_type(tr: dev.TransformerType, new_id: str) -> TypTr2:
    """

    :param tr:
    :param new_id:
    :return:
    """
    typtr2 = TypTr2()
    typtr2.ID = new_id

    typtr2.utrn_h = tr.HV
    typtr2.utrn_l = tr.LV
    typtr2.strn = tr.Sn
    typtr2.pcutr = tr.Pcu
    typtr2.pfe = tr.Pfe
    typtr2.curmg = tr.I0
    typtr2.uktr = tr.Vsc
    typtr2.loc_name = tr.name
    typtr2.nt2ph = 3  # 3 phase

    typtr2.tr2cn_h = _winding_type_to_pf_code(tr.conn_hv)
    typtr2.tr2cn_l = _winding_type_to_pf_code(tr.conn_lv)

    return typtr2


def _set_tr2_tap_fields_from_vgrid(tr: dev.Transformer2W, tpe: TypTr2, e: ElmTr2, t: int | None) -> None:
    """Set tap fields in TypTr2 and ElmTr2.

    This makes the exported DGS coherent with the importer (dgs_to_veragrid),
    which reconstructs tap_module from:
      - TypTr2.dutap, TypTr2.nntap0, TypTr2.ntpmn, TypTr2.ntpmx, TypTr2.tap_side, TypTr2.itapch
      - ElmTr2.nntap

    Notes:
    - VeraGrid Transformer2W exposes tap_module, tap_module_min, tap_module_max.
    - We must NOT choose step = max_dev. That makes most taps round to 0.
    - If tap_min/max look like garbage defaults, we ignore them.
    """
    from_voltage, to_voltage, hv_at_from = tr.get_from_to_nominal_voltages()
    if abs(float(from_voltage) - float(to_voltage)) <= 1e-9:
        hv_at_from = True
    else:
        pass
    if hv_at_from:
        tpe.tap_side = 0
    else:
        tpe.tap_side = 1

    tap_changer = tr.tap_changer
    total_positions: int = int(tap_changer.total_positions)
    has_discrete_tap: bool = (
            tap_changer.tc_type != TapChangerTypes.NoRegulation
            or int(tap_changer.tap_position) != int(tap_changer.neutral_position)
    )

    if has_discrete_tap:
        minimum_position: int = 0
        maximum_position: int = total_positions - 1
        neutral_position: int = int(tap_changer.neutral_position)
        current_position: int = int(tap_changer.tap_position)

        tpe.itapch = 1
        tpe.dutap = float(tap_changer.dV) * 100.0
        tpe.phitr = _get_tap_phase_step_angle(
            tc_type=tap_changer.tc_type,
            asymmetry_angle_deg=float(tap_changer.asymmetry_angle),
        )
        tpe.nntap0 = neutral_position
        tpe.ntpmn = minimum_position
        tpe.ntpmx = maximum_position
        e.nntap = current_position
        return
    else:
        pass

    tap = float(tr.get_tap_module_at(t))
    tol = 1e-12
    tap_dev = abs(tap - 1.0)

    tpe.phitr = 0.0
    tpe.nntap0 = 0

    if tap_dev < tol:
        tpe.itapch = 0
        tpe.dutap = 0.0
        tpe.ntpmn = 0
        tpe.ntpmx = 0
        e.nntap = 0
        return
    else:
        pass

    step = tap_dev
    if tap < 1.0:
        neutral_position = 1
        current_position = 0
    else:
        neutral_position = 0
        current_position = 1

    tpe.itapch = 1
    tpe.dutap = float(step * 100.0)
    tpe.nntap0 = int(neutral_position)
    tpe.ntpmn = 0
    tpe.ntpmx = 1
    e.nntap = int(current_position)


def _build_typtr3_and_elmtr3(
        tr3: dev.Transformer3W,
        type_id: str,
        element_id: str,
        fold_id: str,
        t: int | None,
        sbase_mva: float = 100.0,
) -> Tuple[TypTr3, ElmTr3, List[dev.Bus]]:
    """
    Convert a VeraGrid 3W transformer into DGS ``TypTr3`` and ``ElmTr3`` objects.

    :param tr3: VeraGrid 3W transformer
    :param type_id: DGS type ID
    :param element_id: DGS element ID
    :param fold_id: Parent folder ID
    :param t: Optional profile index.
    :param sbase_mva: Network power base, MVA.
    :return: Tuple with TypTr3, ElmTr3, and the ordered buses [HV, MV, LV]
    """
    ordered_sides: List[Tuple[dev.Bus, dev.Winding, float, float, float, float, float, float]] = list()
    ordered_sides.append((tr3.bus1, tr3.winding1, float(tr3.V1), float(tr3.rate1),
                          float(tr3.Pcu12), float(tr3.Vsc12), float(tr3.Pcu31), float(tr3.Vsc31)))
    ordered_sides.append((tr3.bus2, tr3.winding2, float(tr3.V2), float(tr3.rate2),
                          float(tr3.Pcu23), float(tr3.Vsc23), float(tr3.Pcu12), float(tr3.Vsc12)))
    ordered_sides.append((tr3.bus3, tr3.winding3, float(tr3.V3), float(tr3.rate3),
                          float(tr3.Pcu31), float(tr3.Vsc31), float(tr3.Pcu23), float(tr3.Vsc23)))
    ordered_sides = sorted(ordered_sides, key=_get_transformer3w_side_sort_key, reverse=True)

    bus_hv, winding_hv, rated_voltage_hv, rated_power_hv, pcu_hv, vsc_hv, _, _ = ordered_sides[0]
    bus_mv, winding_mv, rated_voltage_mv, rated_power_mv, pcu_mv, vsc_mv, _, _ = ordered_sides[1]
    bus_lv, winding_lv, rated_voltage_lv, rated_power_lv, pcu_lv, vsc_lv, _, _ = ordered_sides[2]

    typtr3 = TypTr3()
    typtr3.ID = type_id
    typtr3.loc_name = tr3.name
    typtr3.fold_id = fold_id
    typtr3.curm3 = float(tr3.I0)
    typtr3.pfe = float(tr3.Pfe)
    typtr3.utrn3_h = rated_voltage_hv
    typtr3.utrn3_m = rated_voltage_mv
    typtr3.utrn3_l = rated_voltage_lv
    typtr3.strn3_h = rated_power_hv
    typtr3.strn3_m = rated_power_mv
    typtr3.strn3_l = rated_power_lv
    typtr3.pcut3_h = pcu_hv
    typtr3.pcut3_m = pcu_mv
    typtr3.pcut3_l = pcu_lv
    typtr3.uktr3_h = vsc_hv
    typtr3.uktr3_m = vsc_mv
    typtr3.uktr3_l = vsc_lv
    typtr3.tr3cn_h = _winding_type_to_pf_code(winding_hv.get_winding_connections()[0])
    typtr3.tr3cn_m = _winding_type_to_pf_code(winding_mv.get_winding_connections()[0])
    typtr3.tr3cn_l = _winding_type_to_pf_code(winding_lv.get_winding_connections()[0])
    typtr3.nt3ag_h = float(winding_hv.vector_group_number)
    typtr3.nt3ag_m = float(winding_mv.vector_group_number)
    typtr3.nt3ag_l = float(winding_lv.vector_group_number)

    # PF stores pairwise tests, whereas the existing Winding objects store legs.
    z0_hm: complex = complex(winding_hv.R0 + winding_mv.R0, winding_hv.X0 + winding_mv.X0)
    z0_ml: complex = complex(winding_mv.R0 + winding_lv.R0, winding_mv.X0 + winding_lv.X0)
    z0_hl: complex = complex(winding_hv.R0 + winding_lv.R0, winding_hv.X0 + winding_lv.X0)
    base_hm: float = 100.0 * min(rated_power_hv, rated_power_mv) / sbase_mva
    base_ml: float = 100.0 * min(rated_power_mv, rated_power_lv) / sbase_mva
    base_hl: float = 100.0 * min(rated_power_hv, rated_power_lv) / sbase_mva
    typtr3.uk0hm, typtr3.ur0hm = abs(z0_hm) * base_hm, z0_hm.real * base_hm
    typtr3.uk0ml, typtr3.ur0ml = abs(z0_ml) * base_ml, z0_ml.real * base_ml
    typtr3.uk0hl, typtr3.ur0hl = abs(z0_hl) * base_hl, z0_hl.real * base_hl

    hv_current_position, hv_minimum_position, hv_maximum_position, hv_neutral_position, hv_step_percent, hv_phase_angle = (
        _get_tr3_winding_tap_fields_from_vgrid(winding=winding_hv)
    )
    mv_current_position, mv_minimum_position, mv_maximum_position, mv_neutral_position, mv_step_percent, mv_phase_angle = (
        _get_tr3_winding_tap_fields_from_vgrid(winding=winding_mv)
    )
    lv_current_position, lv_minimum_position, lv_maximum_position, lv_neutral_position, lv_step_percent, lv_phase_angle = (
        _get_tr3_winding_tap_fields_from_vgrid(winding=winding_lv)
    )

    typtr3.n3tmn_h = hv_minimum_position
    typtr3.n3tmx_h = hv_maximum_position
    typtr3.n3tp0_h = hv_neutral_position
    typtr3.du3tp_h = hv_step_percent
    typtr3.ph3tr_h = hv_phase_angle

    typtr3.n3tmn_m = mv_minimum_position
    typtr3.n3tmx_m = mv_maximum_position
    typtr3.n3tp0_m = mv_neutral_position
    typtr3.du3tp_m = mv_step_percent
    typtr3.ph3tr_m = mv_phase_angle

    typtr3.n3tmn_l = lv_minimum_position
    typtr3.n3tmx_l = lv_maximum_position
    typtr3.n3tp0_l = lv_neutral_position
    typtr3.du3tp_l = lv_step_percent
    typtr3.ph3tr_l = lv_phase_angle

    elmtr3 = ElmTr3()
    elmtr3.ID = element_id
    elmtr3.loc_name = tr3.name
    elmtr3.fold_id = fold_id
    elmtr3.typ_id = typtr3.ID
    elmtr3.outserv = 0 if tr3.get_active_at(t) else 1
    elmtr3.nt3nm = 1
    elmtr3.n3tap_h = hv_current_position
    elmtr3.n3tap_m = mv_current_position
    elmtr3.n3tap_l = lv_current_position
    elmtr3.i_auto_hl = 0
    elmtr3.t3ldc = 0
    elmtr3.usp_low = 0.99
    elmtr3.usp_up = 1.01
    typtr3.i3loc = 0

    controlled_side: int | None = None
    for side_index, winding in enumerate((winding_hv, winding_mv, winding_lv)):
        if winding.get_tap_module_control_mode_at(t) == TapModuleControl.Vm:
            controlled_side = side_index
            break
        else:
            pass

    if controlled_side is not None:
        elmtr3.ntrcn = 1
        elmtr3.ictrlside = int(controlled_side)
        control_winding: dev.Winding = tr3.get_winding(controlled_side)
        regulation_bus: dev.Bus | None = control_winding.regulation_bus
        if regulation_bus is tr3.bus1:
            elmtr3.t3ldc = 0
        elif regulation_bus is tr3.bus2:
            elmtr3.t3ldc = 1
        elif regulation_bus is tr3.bus3:
            elmtr3.t3ldc = 2
        else:
            elmtr3.t3ldc = 3
        if controlled_side == 0:
            elmtr3.usetp = float(winding_hv.get_vset_at(t))
        elif controlled_side == 1:
            elmtr3.usetp = float(winding_mv.get_vset_at(t))
        else:
            elmtr3.usetp = float(winding_lv.get_vset_at(t))
    else:
        elmtr3.ntrcn = 0
        elmtr3.ictrlside = 0
        elmtr3.usetp = 1.0

    return typtr3, elmtr3, [bus_hv, bus_mv, bus_lv]


def _convert_external_grid(external_grid: dev.ExternalGrid, new_id: str, fold_id: str, t: int | None) -> ElmXnet:
    """
    Convert a VeraGrid external grid into a DGS ``ElmXnet``.

    :param external_grid: VeraGrid external grid
    :param new_id: DGS element ID
    :param fold_id: Parent folder ID
    :param t: Optional time index
    :return: DGS external grid element
    """
    element = ElmXnet()
    element.ID = new_id
    element.loc_name = external_grid.name
    element.fold_id = fold_id
    element.outserv = 0 if external_grid.get_active_at(t) else 1
    element.pgini = float(external_grid.get_P_at(t))
    element.qgini = float(external_grid.get_Q_at(t))
    element.usetp = float(external_grid.get_Vm_at(t))
    element.phiini = math.degrees(float(external_grid.get_Va_at(t)))

    if external_grid.mode == ExternalGridMode.VD:
        element.bustp = "SL"
    elif external_grid.mode == ExternalGridMode.PV:
        element.bustp = "PV"
    else:
        element.bustp = "PQ"

    return element


def _convert_controllable_shunt_to_dgs(
        shunt: dev.ControllableShunt,
        new_id: str,
        fold_id: str,
        t: int | None,
) -> Tuple[ElmShnt | None, ElmSvs | None]:
    """
    Convert a VeraGrid controllable shunt into a DGS ``ElmShnt`` or ``ElmSvs``.

    :param shunt: VeraGrid controllable shunt
    :param new_id: DGS element ID
    :param fold_id: Parent folder ID
    :return: Tuple ``(ElmShnt, ElmSvs)``, one side being ``None``
    """
    b_steps = np.asarray(shunt.b_steps, dtype=float)
    if len(b_steps) > 1:
        step_increments = b_steps[1:]
    else:
        step_increments = np.zeros(0, dtype=float)

    if len(step_increments) > 0:
        first_increment = float(step_increments[0])
        uniform_steps = bool(np.allclose(step_increments, first_increment))
    else:
        uniform_steps = False

    if uniform_steps:
        element = ElmShnt()
        element.ID = new_id
        element.loc_name = shunt.name
        element.fold_id = fold_id
        element.ushnm = 0.0
        element.ncapx = int(len(step_increments))
        element.ncapa = int(shunt.step)
        element.iswitch = 0 if shunt.control_mode == ShuntControlMode.Locked else 1
        element.usetp = float(shunt.get_Vset_at(t))
        element.outserv = 0 if shunt.get_active_at(t) else 1
        element.qtotn = abs(float(np.sum(step_increments)))

        if first_increment >= 0.0:
            element.shtype = 2
            element.qcapn = abs(first_increment)
            element.qrean = 0.0
        else:
            element.shtype = 1
            element.qcapn = 0.0
            element.qrean = abs(first_increment)

        return element, None
    else:
        pass

    element_svs = ElmSvs()
    element_svs.ID = new_id
    element_svs.loc_name = shunt.name
    element_svs.fold_id = fold_id
    element_svs.qmin = float(shunt.Bmin)
    element_svs.qmax = float(shunt.Bmax)
    element_svs.usetp = float(shunt.get_Vset_at(t))
    element_svs.outserv = 0 if shunt.get_active_at(t) else 1

    positive_steps = step_increments[step_increments > 0.0]
    negative_steps = step_increments[step_increments < 0.0]
    element_svs.nxcap = int(len(positive_steps))
    element_svs.nfixcap = 0
    element_svs.Qfixcap = 0.0
    element_svs.tcrmax = abs(float(np.sum(negative_steps)))

    return None, element_svs


def generate_diesel_dsl_composite(dgs_grid: DgsCircuit, name: str, net_id: str) -> ElmComp:
    """
    Generate a diesel composite
    :param dgs_grid:
    :param name:
    :param net_id:
    :return:
    """
    elmcomp = ElmComp()
    elmcomp.ID = dgs_grid.new_id()
    elmcomp.loc_name = name
    elmcomp.fold_id = net_id

    for dsl_name in ["PSS/E COMP",
                     "PSS/E DEGOV1",
                     "PSS/E EXAC1"]:
        comp1 = ElmDsl()
        comp1.ID = dgs_grid.new_id()
        comp1.loc_name = dsl_name
        comp1.fold_id = elmcomp.ID
        dgs_grid.elmdsls.append(comp1)

    dgs_grid.elmcomps.append(elmcomp)

    return elmcomp


def generate_pv_dsl_composite(dgs_grid: DgsCircuit, name: str, net_id: str) -> ElmComp:
    """
    Generate a PV composite
    :param dgs_grid:
    :param name:
    :param net_id:
    :return:
    """
    elmcomp = ElmComp()
    elmcomp.ID = dgs_grid.new_id()
    elmcomp.loc_name = name
    elmcomp.fold_id = net_id

    for dsl_name in ["Active Power Reduction",
                     "Controller",
                     "DC Busbar and Capacitor",
                     "PV Array",
                     "Protection",
                     "Qreference",
                     "Solar Radiation",
                     "Temperature"]:
        comp1 = ElmDsl()
        comp1.ID = dgs_grid.new_id()
        comp1.loc_name = dsl_name
        comp1.fold_id = elmcomp.ID
        dgs_grid.elmdsls.append(comp1)

    dgs_grid.elmcomps.append(elmcomp)

    return elmcomp


def circuit_to_dgs(
        grid: dev.MultiCircuit,
        t_idx: int | None = None,
        convert_gen_to_elmgenstat: bool = False,
        t: int | None = None,
) -> DgsCircuit:
    """
    Convert MultiCircuit to DgsCircuit

    :param grid: MultiCircuit
    :param t_idx: time step (None for snapshot)
    :param convert_gen_to_elmgenstat: Convert generators to ElmGenstat depending on the technology assigned
    :param t: Deprecated compatibility alias for ``t_idx``
    :return: DgsCircuit
    """
    # Normalize the legacy ``t`` argument into the canonical export time selector.
    if t_idx is None:
        export_t_idx: int | None = t
    else:
        export_t_idx = t_idx

    dgs_grid = DgsCircuit()

    # general
    general = General()
    general.ID = dgs_grid.new_id()
    general.Descr = "Version"
    general.Val = "5.0"
    dgs_grid.generals.append(general)

    # grid
    net = ElmNet()
    net.ID = dgs_grid.new_id()
    net.loc_name = grid.name if grid.name != "" else "Grid"
    net.frnom = grid.fBase
    dgs_grid.elmnets.append(net)

    # Default load type. Assign to all loads so typ_id is never empty.
    typlod = TypLod()
    typlod.ID = dgs_grid.new_id()
    typlod.loc_name = "Default Load Type"
    typlod.fold_id = net.ID

    # Defaults (voltage dependency coefficients)
    typlod.systp = 0
    typlod.phtech = 0

    typlod.aP = 1.0
    typlod.bP = 0.0
    typlod.kpu0 = 0.0
    typlod.kpu1 = 1.0
    typlod.kpu = 2.0

    typlod.aQ = 1.0
    typlod.bQ = 0.0
    typlod.kqu0 = 0.0
    typlod.kqu1 = 1.0
    typlod.kqu = 2.0

    dgs_grid.typlods.append(typlod)

    # buses
    bus2term_dict: Dict[dev.Bus, ElmTerm] = dict()
    for bus in grid.buses:
        elm_term = convert_bus(bus, new_id=dgs_grid.new_id(), t=export_t_idx)
        dgs_grid.elmterms.append(elm_term)
        bus2term_dict[bus] = elm_term

        # int_grf = convert_bus_graphic(elm_term, bus, new_id=dgs_grid.new_id())
        # dgs_grid.intgrfs.append(int_grf)

    # Loads
    for load in grid.loads:
        e = convert_load(load, new_id=dgs_grid.new_id(), t=export_t_idx)

        # Folder/type linkage
        e.fold_id = net.ID
        e.typ_id = typlod.ID

        # Input mode/scaling
        e.mode_inp = "DEF"
        e.pf_recap = 0
        e.i_scale = 1

        # Provide S and cos(phi) consistent with P/Q
        p = float(e.plini)
        q = float(e.qlini)
        s = (p * p + q * q) ** 0.5
        e.slini = float(s)
        e.coslini = float(p / s) if s > 0.0 else 1.0

        term = bus2term_dict[load.bus]
        dgs_grid.elmlods.append(e)
        dgs_grid.add_element_cubicles(element_id=e.ID, dgs_buses=[term])

    # Shunts
    for shunt in grid.shunts:
        term = bus2term_dict[shunt.bus]
        e = convert_shunt(shunt, new_id=dgs_grid.new_id(), ushnm_kv=term.uknom, t=export_t_idx)
        e.fold_id = net.ID
        dgs_grid.elmshnts.append(e)
        dgs_grid.add_element_cubicles(element_id=e.ID, dgs_buses=[term])

    # Controllable shunts
    for shunt in grid.controllable_shunts:
        term = bus2term_dict[shunt.bus]
        elmshnt, elmsvs = _convert_controllable_shunt_to_dgs(
            shunt=shunt,
            new_id=dgs_grid.new_id(),
            fold_id=net.ID,
            t=export_t_idx,
        )

        if elmshnt is not None:
            elmshnt.ushnm = float(term.uknom)
            dgs_grid.elmshnts.append(elmshnt)
            dgs_grid.add_element_cubicles(element_id=elmshnt.ID, dgs_buses=[term])
        elif elmsvs is not None:
            dgs_grid.elmsvss.append(elmsvs)
            dgs_grid.add_element_cubicles(element_id=elmsvs.ID, dgs_buses=[term])
        else:
            pass

    # Static generators
    for stagen in grid.static_generators:
        e = convert_static_gen(stagen, new_id=dgs_grid.new_id(), t=export_t_idx)
        e.fold_id = net.ID
        term = bus2term_dict[stagen.bus]
        dgs_grid.elmgenstats.append(e)
        dgs_grid.add_element_cubicles(element_id=e.ID, dgs_buses=[term])

    # Batteries
    for batt in grid.batteries:
        e = convert_battery(batt, new_id=dgs_grid.new_id(), t=export_t_idx)
        e.fold_id = net.ID
        term = bus2term_dict[batt.bus]
        dgs_grid.elmgenstats.append(e)
        dgs_grid.add_element_cubicles(element_id=e.ID, dgs_buses=[term])

    # External grids
    for external_grid in grid.external_grids:
        element = _convert_external_grid(
            external_grid=external_grid,
            new_id=dgs_grid.new_id(),
            fold_id=net.ID,
            t=export_t_idx,
        )
        dgs_grid.elmxnets.append(element)
        dgs_grid.add_element_cubicles(
            element_id=element.ID,
            dgs_buses=[bus2term_dict[external_grid.bus]],
        )

    # generators
    for gen in grid.generators:
        tech_list = gen.tech_list
        if len(gen.tech_list) > 0:
            tech_name = tech_list[0].name.lower()

            if ("pv" in tech_name or "batt" in tech_name or "wind" in tech_name) and convert_gen_to_elmgenstat:
                # This has to be a ElmGenstat
                e = convert_gen_to_static_gen(gen=gen, new_id=dgs_grid.new_id(), t=export_t_idx)
                e.fold_id = net.ID
                dgs_grid.elmgenstats.append(e)
            else:
                # Normal generator
                tpe, e = convert_generator(gen=gen,
                                           tpe_new_id=dgs_grid.new_id(),
                                           new_id=dgs_grid.new_id(),
                                           Sbase=grid.Sbase,
                                           t=export_t_idx)
                tpe.fold_id = net.ID
                e.fold_id = net.ID
                dgs_grid.typsyms.append(tpe)
                dgs_grid.elmsyms.append(e)

            # Add DSL composites
            # if "diesel" in tech_name:
            #     composite = generate_diesel_dsl_composite(dgs_grid=dgs_grid,
            #                                               name=f"{gen.name} composite",
            #                                               net_id=net.ID)
            #     e.c_pmod = composite.ID
            # elif "pv" in tech_name:
            #     composite = generate_pv_dsl_composite(dgs_grid=dgs_grid,
            #                                           name=f"{gen.name} composite",
            #                                           net_id=net.ID)
            #     e.c_pmod = composite.ID

        else:

            # generate the actual generator
            tpe, e = convert_generator(gen=gen,
                                       tpe_new_id=dgs_grid.new_id(),
                                       new_id=dgs_grid.new_id(),
                                       Sbase=grid.Sbase,
                                       t=export_t_idx)
            tpe.fold_id = net.ID
            e.fold_id = net.ID
            dgs_grid.typsyms.append(tpe)
            dgs_grid.elmsyms.append(e)

        term = bus2term_dict[gen.bus]
        dgs_grid.add_element_cubicles(element_id=e.ID, dgs_buses=[term])

    # sequence lines
    seq2typlne_dict: Dict[dev.SequenceLineType, TypLne] = dict()
    for seq in grid.sequence_line_types:
        typtr2 = convert_sequence_line(seq=seq, new_id=dgs_grid.new_id())
        typtr2.fold_id = net.ID
        dgs_grid.typlnes.append(typtr2)
        seq2typlne_dict[seq] = typtr2

    # Export a DC equivalent only for systems used by a DC branch. Each
    # selected conductor has its own equivalent; AC catalogue entries are not
    # incorrectly exported as DC types.
    dc_cable2typlne_dict: Dict[tuple[dev.UndergroundLineType, int], TypLne] = dict()

    # transformer types (base types)
    for trt in grid.transformer_types:
        typtr2 = convert_transformer_type(tr=trt, new_id=dgs_grid.new_id())
        typtr2.fold_id = net.ID
        dgs_grid.typtr2s.append(typtr2)

    # lines
    for line in grid.lines:
        tpe = seq2typlne_dict.get(line.template, None)
        export_length: float = _get_line_export_length(line=line)

        if tpe is None:
            tpe = _build_sequence_line_type_from_branch(
                line=line,
                new_id=dgs_grid.new_id(),
                sbase_mva=float(grid.Sbase),
                t=export_t_idx,
            )
            tpe.fold_id = net.ID
            dgs_grid.typlnes.append(tpe)

        e = ElmLne()
        e.ID = dgs_grid.new_id()
        e.loc_name = line.name
        e.fold_id = net.ID
        e.typ_id = tpe.ID
        e.dline = export_length
        e.fline = 1.0
        e.nlnum = 1
        e.outserv = 0 if line.get_active_at(export_t_idx) else 1

        dgs_grid.elmlnes.append(e)
        dgs_grid.add_element_cubicles(
            element_id=e.ID,
            dgs_buses=[bus2term_dict[line.bus_from], bus2term_dict[line.bus_to]]
        )

    # DC lines export their selected Cable System equivalent. A line without a template is
    # still exportable, but its L/C fields remain blank rather than persisting
    # the runtime resistive reduction as measured cable data.
    dc_line: dev.DcLine
    for dc_line in grid.dc_lines:
        dc_typlne = dc_cable2typlne_dict.get((dc_line.template, dc_line.dc_conductor), None)
        if dc_typlne is None:
            if dc_line.template is not None:
                dc_typlne = convert_dc_cable_type(
                    cable_type=dc_line.template,
                    new_id=dgs_grid.new_id(),
                    frequency_hz=float(grid.fBase),
                    conductor=dc_line.dc_conductor,
                )
                dc_cable2typlne_dict[(dc_line.template, dc_line.dc_conductor)] = dc_typlne
            else:
                dc_typlne = build_resistive_dc_line_type(
                    line=dc_line,
                    new_id=dgs_grid.new_id(),
                    system_base_mva=float(grid.Sbase),
                    frequency_hz=float(grid.fBase),
                )
            dc_typlne.fold_id = net.ID
            dgs_grid.typlnes.append(dc_typlne)
        else:
            pass

        dc_element: ElmLne = ElmLne()
        dc_element.ID = dgs_grid.new_id()
        dc_element.loc_name = dc_line.name
        dc_element.fold_id = net.ID
        dc_element.typ_id = dc_typlne.ID
        dc_element.dline = float(dc_line.length)
        dc_element.fline = 1.0
        dc_element.nlnum = 1
        dc_element.outserv = 0 if dc_line.get_active_at(export_t_idx) else 1
        dgs_grid.elmlnes.append(dc_element)
        dgs_grid.add_element_cubicles(
            element_id=dc_element.ID,
            dgs_buses=[
                bus2term_dict[dc_line.bus_from],
                bus2term_dict[dc_line.bus_to],
            ],
        )

    # 2W transformers
    for tr in grid.transformers2w:
        # Get actual connected buses first (we will force TypTr2 nominal voltages from them)
        hv_bus, lv_bus = tr.get_buses_sorted_by_voltage()

        # Create ONE TypTr2 per ElmTr2. Reusing/caching transformer types can merge
        tpe = convert_transformer_type(tr=tr.get_transformer_type(Sbase=grid.Sbase), new_id=dgs_grid.new_id())
        tpe.fold_id = net.ID
        dgs_grid.typtr2s.append(tpe)

        if float(tpe.frnom) == 0.0:
            tpe.frnom = float(net.frnom)

        # Force nominal voltages from the actual connected buses (not from template)
        # to avoid template contamination and shared-type issues.
        tpe.utrn_h = float(hv_bus.Vnom)
        tpe.utrn_l = float(lv_bus.Vnom)
        _set_tr2_type_connections_from_branch(tr=tr, tpe=tpe)

        # The importer rebuilds transformer R/X from TypTr2.uktr (%) + TypTr2.pcutr (kW).
        nominal_power: float = _get_transformer_export_nominal_power(
            transformer=tr,
            sbase_mva=float(grid.Sbase),
            t=export_t_idx,
        )

        Pfe, Pcu, Vsc, I0, Sn = reverse_transformer_short_circuit_study(
            R=float(tr.R),
            X=float(tr.X),
            G=float(tr.G),
            B=float(tr.B),
            rate=nominal_power,
            Sbase=float(grid.Sbase),
        )

        tpe.pfe = float(Pfe)
        tpe.pcutr = float(Pcu)
        tpe.uktr = float(Vsc)
        tpe.curmg = float(I0)
        tpe.strn = float(Sn)

        e = ElmTr2()
        e.ID = dgs_grid.new_id()
        e.loc_name = tr.name
        e.typ_id = tpe.ID
        e.ntnum = 1
        e.ratfac = 1
        e.outserv = 0 if tr.get_active_at(export_t_idx) else 1

        # PF-like folder placement
        e.fold_id = net.ID

        # Export tap fields from VeraGrid -> TypTr2/ElmTr2
        _set_tr2_tap_fields_from_vgrid(tr=tr, tpe=tpe, e=e, t=export_t_idx)
        _set_tr2_tap_control_fields_from_vgrid(tr=tr, element=e, t=export_t_idx)

        dgs_grid.elmtr2s.append(e)

        # Preserve branch orientation as stored in VeraGrid (bus_from -> bus_to)
        dgs_grid.add_element_cubicles(
            element_id=e.ID,
            dgs_buses=[bus2term_dict[tr.bus_from],
                       bus2term_dict[tr.bus_to]]
        )

    # Switches
    for switch in grid.switch_devices:
        typ_switch = _convert_switch_to_dgs_type(
            switch=switch,
            new_id=dgs_grid.new_id(),
            fold_id=net.ID,
            sbase_mva=float(grid.Sbase),
            t=export_t_idx,
        )
        dgs_grid.typswitches.append(typ_switch)

        switch_iuse, switch_usage = _switch_graphic_type_to_pf_usage(graphic_type=switch.graphic_type)

        element = ElmCoup()
        element.ID = dgs_grid.new_id()
        element.loc_name = switch.name
        element.fold_id = net.ID
        element.typ_id = typ_switch.ID
        element.aUsage = switch_usage
        element.nneutral = 0
        element.nphase = 3
        element.on_off = 1 if switch.get_active_at(export_t_idx) else 0

        dgs_grid.elmcoups.append(element)
        _add_element_cubicles_with_state(
            dgs_grid=dgs_grid,
            element_id=element.ID,
            dgs_buses=[bus2term_dict[switch.bus_from], bus2term_dict[switch.bus_to]],
            switch_state=element.on_off,
            switch_type_id=typ_switch.ID,
            switch_iuse=switch_iuse,
            switch_usage=switch_usage,
        )

    # Series reactances
    for series_reactance in grid.series_reactances:
        element = _convert_branch_impedance_to_elm_sind(
            branch=series_reactance,
            new_id=dgs_grid.new_id(),
            fold_id=net.ID,
            sbase_mva=float(grid.Sbase),
            t=export_t_idx,
        )
        dgs_grid.elmsinds.append(element)
        dgs_grid.add_element_cubicles(
            element_id=element.ID,
            dgs_buses=[bus2term_dict[series_reactance.bus_from], bus2term_dict[series_reactance.bus_to]],
        )

    # 3W transformers
    for transformer3w in grid.transformers3w:
        typtr3, elmtr3, ordered_buses = _build_typtr3_and_elmtr3(
            tr3=transformer3w,
            type_id=dgs_grid.new_id(),
            element_id=dgs_grid.new_id(),
            fold_id=net.ID,
            t=export_t_idx,
            sbase_mva=float(grid.Sbase),
        )
        dgs_grid.typtr3s.append(typtr3)
        dgs_grid.elmtr3s.append(elmtr3)
        dgs_grid.add_element_cubicles(
            element_id=elmtr3.ID,
            dgs_buses=[bus2term_dict[ordered_buses[0]],
                       bus2term_dict[ordered_buses[1]],
                       bus2term_dict[ordered_buses[2]]],
        )

    return dgs_grid
