# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Collection of functions to create new CGMES instances for CGMES export.
"""
import numpy as np
from datetime import datetime
from typing import List, Union, Tuple
from VeraGridEngine import StrVec
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.IO.cim.cgmes.base import get_new_rdfid, form_rdfid
import VeraGridEngine.IO.cim.cgmes.cgmes_assets.cgmes_2_4_15_assets as cgmes24
import VeraGridEngine.IO.cim.cgmes.cgmes_assets.cgmes_3_0_0_assets as cgmes30
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_typing import (is_term,
                                                      CGMES_CONDUCTING_EQUIPMENT,
                                                      CGMES_EQUIPMENT_CONTAINER,
                                                      CGMES_DC_CONDUCTING_EQUIPMENT,
                                                      CGMES_OPERATIONAL_LIMIT_TYPE,
                                                      CGMES_DC_TOPOLOGICAL_NODE,
                                                      CGMES_CONNECTIVITY_NODE,
                                                      CGMES_VS_CONVERTER,
                                                      CGMES_DC_CONVERTER_UNIT,
                                                      CGMES_LINE,
                                                      CGMES_DC_LINE,
                                                      CGMES_DC_LINE_SEGMENT,
                                                      CGMES_TERMINAL,
                                                      CGMES_DC_TERMINAL,
                                                      CGMES_LOCATION,
                                                      CGMES_NON_LINEAR_SHUNT_COMPENSATOR)

from VeraGridEngine.IO.cim.cgmes.cgmes_enums import (CgmesProfileType,
                                                     WindGenUnitKind,
                                                     RegulatingControlModeKind,
                                                     UnitMultiplier,
                                                     DCPolarityKind,
                                                     DCConverterOperatingModeKind,
                                                     VsPpccControlKind,
                                                     VsQpccControlKind)

from VeraGridEngine.IO.cim.cgmes.cgmes_utils import find_object_by_uuid, get_voltage_terminal
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.full_model import FullModel
import VeraGridEngine.Devices as gcdev
from VeraGridEngine.enumerations import CGMESVersions
from VeraGridEngine.data_logger import DataLogger


def create_cgmes_headers(cgmes_model: CgmesCircuit,
                         mas_names: StrVec,
                         profiles_to_export: List[CgmesProfileType],
                         logger: DataLogger,
                         desc: str = "",
                         scenario_time: str = "",
                         version: str = "",
                         modeller_url="http://www.ree.es/OperationalPlanning"):
    """

    :param cgmes_model:
    :param mas_names:
    :param profiles_to_export:
    :param logger:
    :param desc:
    :param scenario_time:
    :param version:
    :param modeller_url:
    :return:
    """
    if cgmes_model.cgmes_version == CGMESVersions.v2_4_15:
        fm_list = [FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel")]
    elif cgmes_model.cgmes_version == CGMESVersions.v3_0_0:
        fm_list = [FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
                   FullModel(rdfid=get_new_rdfid(), tpe="FullModel")]
    else:
        raise ValueError(
            f"CGMES format not supported {cgmes_model.cgmes_version}")

    for fm in fm_list:
        fm.scenarioTime = scenario_time
        fm.modelingAuthoritySet = []
        if len(mas_names):
            for mas_name in mas_names:
                fm.modelingAuthoritySet.append(mas_name)
        else:
            fm.modelingAuthoritySet.append(modeller_url)
            logger.add_warning(msg="Missing Modeling Authority! (set to default)",
                               comment=f"Default value used. ({modeller_url})")
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        fm.created = formatted_time
        fm.version = version
        fm.description = desc

    if cgmes_model.cgmes_version == CGMESVersions.v2_4_15:
        profile_uris = {
            "EQ": ["http://entsoe.eu/CIM/EquipmentCore/3/1",
                   "http://entsoe.eu/CIM/EquipmentOperation/3/1",
                   "http://entsoe.eu/CIM/EquipmentShortCircuit/3/1"],
            "SSH": ["http://entsoe.eu/CIM/SteadyStateHypothesis/1/1"],
            "TP": ["http://entsoe.eu/CIM/Topology/4/1"],
            "SV": ["http://entsoe.eu/CIM/StateVariables/4/1"],
            "GL": ["http://entsoe.eu/CIM/GeographicalLocation/2/1"]
        }
    elif cgmes_model.cgmes_version == CGMESVersions.v3_0_0:
        profile_uris = {
            "EQ": ["http://iec.ch/TC57/ns/CIM/CoreEquipment-EU/3.0"],
            "OP": ["http://iec.ch/TC57/ns/CIM/Operation-EU/3.0"],
            "SC": ["http://iec.ch/TC57/ns/CIM/ShortCircuit-EU/3.0"],
            "SSH": ["http://iec.ch/TC57/ns/CIM/SteadyStateHypothesis-EU/3.0"],
            "TP": ["http://iec.ch/TC57/ns/CIM/Topology-EU/3.0"],
            "SV": ["http://iec.ch/TC57/ns/CIM/StateVariables-EU/3.0"],
            "GL": ["http://iec.ch/TC57/ns/CIM/GeographicalLocation-EU/3.0"]
        }
    else:
        raise ValueError(
            f"CGMES format not supported {cgmes_model.cgmes_version}")

    if cgmes_model.cgmes_version == CGMESVersions.v2_4_15:
        prof = profile_uris.get("EQ")
        fm_list[0].profile = [prof[0]]
        if CgmesProfileType.OP in profiles_to_export:
            fm_list[0].profile.append(prof[1])
        if CgmesProfileType.SC in profiles_to_export:
            fm_list[0].profile.append(prof[2])
    elif cgmes_model.cgmes_version == CGMESVersions.v3_0_0:
        fm_list[0].profile = profile_uris.get("EQ")
        fm_list[5].profile = profile_uris.get("OP")
        fm_list[6].profile = profile_uris.get("SC")
    else:
        raise ValueError(
            f"CGMES format not supported {cgmes_model.cgmes_version}")

    fm_list[1].profile = profile_uris.get("SSH")
    fm_list[2].profile = profile_uris.get("TP")
    fm_list[3].profile = profile_uris.get("SV")
    fm_list[4].profile = profile_uris.get("GL")
    if cgmes_model.cgmes_version == CGMESVersions.v2_4_15 and len(mas_names) > 1:
        # if 2.4 than no need in SV in 3.0 we need all
        fm_list[3].modelingAuthoritySet = None

    # DependentOn
    eqbd_id = ""
    tpbd_id = ""
    try:
        for bd in cgmes_model.elements_by_type_boundary.get("FullModel"):
            if ("http://entsoe.eu/CIM/EquipmentBoundary/3/1" in bd.profile or
                    "http://iec.ch/TC57/ns/CIM/EquipmentBoundary-EU" in bd.profile):
                eqbd_id = bd.rdfid
            if "http://entsoe.eu/CIM/TopologyBoundary/3/1" in bd.profile:  # no TPBD in 3.0
                tpbd_id = bd.rdfid

        fm_list[0].DependentOn = [eqbd_id]
        fm_list[1].DependentOn = [fm_list[0].rdfid]
        fm_list[2].DependentOn = [fm_list[0].rdfid]
        if tpbd_id != "":
            fm_list[3].DependentOn = [tpbd_id, fm_list[1].rdfid,
                                      fm_list[2].rdfid]
        else:
            fm_list[3].DependentOn = [fm_list[1].rdfid, fm_list[2].rdfid]
        fm_list[2].DependentOn = [fm_list[0].rdfid, eqbd_id]
        fm_list[4].DependentOn = [fm_list[0].rdfid]
        if cgmes_model.cgmes_version == CGMESVersions.v3_0_0:
            fm_list[5].DependentOn = [fm_list[0].rdfid]
            fm_list[6].DependentOn = [fm_list[0].rdfid]
    except TypeError:
        print("Missing default boundary files")
        fm_list[1].DependentOn = [fm_list[0].rdfid]
        fm_list[2].DependentOn = [fm_list[0].rdfid]
        fm_list[3].DependentOn = [fm_list[0].rdfid, fm_list[1].rdfid,
                                  fm_list[2].rdfid]
        fm_list[4].DependentOn = [fm_list[0].rdfid]
        if cgmes_model.cgmes_version == CGMESVersions.v3_0_0:
            fm_list[5].DependentOn = [fm_list[0].rdfid]
            fm_list[6].DependentOn = [fm_list[0].rdfid]

    cgmes_model.cgmes_assets.FullModel_list = fm_list
    return cgmes_model


def create_cgmes_terminal(mc_bus: Bus,
                          seq_num: Union[int, None],
                          cond_eq: Union[None, CGMES_CONDUCTING_EQUIPMENT],
                          cgmes_model: CgmesCircuit,
                          ver: CGMESVersions,
                          logger: DataLogger) -> CGMES_TERMINAL:
    """
    Creates a new Terminal in CGMES model,
    and connects it the relating Topological Node
    :param mc_bus:
    :param seq_num:
    :param cond_eq:
    :param cgmes_model:
    :param ver
    :param logger:
    :return: CGMES_TERMINAL
    """

    new_rdf_id = get_new_rdfid()
    name = f'{cond_eq.name} - T{seq_num}' if cond_eq is not None else ""

    tn = find_object_by_uuid(
        cgmes_model=cgmes_model,
        object_list=cgmes_model.cgmes_assets.TopologicalNode_list,
        target_uuid=mc_bus.idtag
    )

    if ver == CGMESVersions.v2_4_15:
        term = cgmes24.Terminal(rdfid=new_rdf_id)
        term.name = name

        if cond_eq and isinstance(cond_eq, cgmes_model.assets.ConductingEquipment):
            term.ConductingEquipment = cond_eq

        if isinstance(tn, cgmes_model.assets.TopologicalNode):
            term.TopologicalNode = tn
            term.ConnectivityNode = tn.ConnectivityNodes
        else:
            logger.add_error(msg='No found TopologicalNode',
                             device=mc_bus,
                             device_class=gcdev.Bus)

    elif CGMESVersions.v3_0_0:
        term = cgmes30.Terminal(rdfid=new_rdf_id)
        term.name = name

        if cond_eq and isinstance(cond_eq, cgmes30.ConductingEquipment):
            term.ConductingEquipment = cond_eq

        if isinstance(tn, cgmes30.TopologicalNode):
            term.TopologicalNode = tn
            term.ConnectivityNode = tn.ConnectivityNodes
        else:
            logger.add_error(msg='No found TopologicalNode',
                             device=mc_bus,
                             device_class=gcdev.Bus)

    else:
        raise NotImplemented()

    if seq_num is not None:
        term.sequenceNumber = seq_num

    term.connected = True

    cgmes_model.add(term)

    return term


def create_cgmes_load_response_char(load: gcdev.Load,
                                    cgmes_model: CgmesCircuit,
                                    ver: CGMESVersions):
    """

    :param load:
    :param cgmes_model:
    :param ver:
    :return:
    """
    if ver == CGMESVersions.v2_4_15:
        lrc = cgmes24.LoadResponseCharacteristic(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        lrc = cgmes30.LoadResponseCharacteristic(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    lrc.name = f'LoadRespChar_{load.name}'
    # lrc.shortName = load.name
    lrc.exponentModel = False
    # SUPPOSING that
    lrc.pConstantImpedance = 0.0
    lrc.qConstantImpedance = 0.0
    # Expression got simpler
    lrc.pConstantPower = np.round(load.P / (load.Ir + load.P), 4)
    lrc.qConstantPower = np.round(load.Q / (load.Ii + load.Q), 4)
    lrc.pConstantCurrent = np.round(1 - lrc.pConstantPower, 4)
    lrc.qConstantCurrent = np.round(1 - lrc.qConstantPower, 4)

    # Legacy
    # lrc.pConstantCurrent = load.Ir / load.P if load.P != 0.0 else 0
    # lrc.qConstantCurrent = load.Ii / load.Q if load.Q != 0.0 else 0
    # lrc.pConstantImpedance = load.G / load.P if load.P != 0.0 else 0
    # lrc.qConstantImpedance = load.B / load.Q if load.Q != 0.0 else 0
    # lrc.pConstantPower = 1 - lrc.pConstantCurrent - lrc.pConstantImpedance
    # lrc.qConstantPower = 1 - lrc.qConstantCurrent - lrc.qConstantImpedance
    # if lrc.pConstantPower < 0 or lrc.qConstantPower < 0:
    #     logger.add_error(msg='Constant Impedance/Current parameters are not correct',
    #                      device=load,
    #                      device_class=gcdev.Load)
    # sum for 3 for p = 1
    # if it not supports voltage dependent load, lf wont be the same
    cgmes_model.add(lrc)
    return lrc


def create_cgmes_generating_unit(gen: gcdev.Generator,
                                 cgmes_model: CgmesCircuit,
                                 ver: CGMESVersions):
    """
    Creates the appropriate CGMES GeneratingUnit object
    from a MultiCircuit Generator.
    """

    if len(gen.technologies) == 0:
        if ver == CGMESVersions.v2_4_15:
            sm = cgmes24.GeneratingUnit(get_new_rdfid())
        elif ver == CGMESVersions.v3_0_0:
            sm = cgmes30.GeneratingUnit(get_new_rdfid())
        else:
            raise NotImplemented()

        cgmes_model.add(sm)
        return sm
    else:
        for tech_association in gen.technologies:

            if tech_association.api_object.name == 'General':

                if ver == CGMESVersions.v2_4_15:
                    sm = cgmes24.GeneratingUnit(get_new_rdfid())
                elif ver == CGMESVersions.v3_0_0:
                    sm = cgmes30.GeneratingUnit(get_new_rdfid())
                else:
                    raise NotImplemented()

                cgmes_model.add(sm)
                return sm

            if tech_association.api_object.name == 'Thermal':

                if ver == CGMESVersions.v2_4_15:
                    tgu = cgmes24.ThermalGeneratingUnit(get_new_rdfid())
                elif ver == CGMESVersions.v3_0_0:
                    tgu = cgmes30.ThermalGeneratingUnit(get_new_rdfid())
                else:
                    raise NotImplemented()

                cgmes_model.add(tgu)
                return tgu

            if tech_association.api_object.name == 'Hydro':

                if ver == CGMESVersions.v2_4_15:
                    hgu = cgmes24.HydroGeneratingUnit(get_new_rdfid())
                elif ver == CGMESVersions.v3_0_0:
                    hgu = cgmes30.HydroGeneratingUnit(get_new_rdfid())
                else:
                    raise NotImplemented()

                cgmes_model.add(hgu)
                return hgu

            if tech_association.api_object.name == 'Solar':

                if ver == CGMESVersions.v2_4_15:
                    sgu = cgmes24.SolarGeneratingUnit(get_new_rdfid())
                elif ver == CGMESVersions.v3_0_0:
                    sgu = cgmes30.SolarGeneratingUnit(get_new_rdfid())
                else:
                    raise NotImplemented()

                cgmes_model.add(sgu)
                return sgu

            if tech_association.api_object.name == 'Wind Onshore':

                if ver == CGMESVersions.v2_4_15:
                    wgu = cgmes24.WindGeneratingUnit(get_new_rdfid())
                elif ver == CGMESVersions.v3_0_0:
                    wgu = cgmes30.WindGeneratingUnit(get_new_rdfid())
                else:
                    raise NotImplemented()

                wgu.windGenUnitType = WindGenUnitKind.onshore
                cgmes_model.add(wgu)
                return wgu

            if tech_association.api_object.name == 'Wind Offshore':

                if ver == CGMESVersions.v2_4_15:
                    wgu = cgmes24.WindGeneratingUnit(get_new_rdfid())
                elif ver == CGMESVersions.v3_0_0:
                    wgu = cgmes30.WindGeneratingUnit(get_new_rdfid())
                else:
                    raise NotImplemented()

                wgu.windGenUnitType = WindGenUnitKind.offshore
                cgmes_model.add(wgu)
                return wgu

            if tech_association.api_object.name == 'Nuclear':

                if ver == CGMESVersions.v2_4_15:
                    ngu = cgmes24.NuclearGeneratingUnit(get_new_rdfid())
                elif ver == CGMESVersions.v3_0_0:
                    ngu = cgmes30.NuclearGeneratingUnit(get_new_rdfid())
                else:
                    raise NotImplemented()

                cgmes_model.add(ngu)
                return ngu

    return None


def create_cgmes_regulating_control(cgmes_elm,
                                    mc_gen: Union[gcdev.Generator, gcdev.ControllableShunt],
                                    cgmes_model: CgmesCircuit,
                                    ver: CGMESVersions,
                                    logger: DataLogger):
    """
    Create Regulating Control for a CGMES device

    :param cgmes_elm: Cgmes Synchronous Machine or Shunt (Nonlin or Lin)
    :param mc_gen: MultiCircuit element: Generator or Controllable Shunt
    :param cgmes_model: CgmesCircuit
    :param ver: Version
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()

    if ver == CGMESVersions.v2_4_15:
        rc = cgmes24.RegulatingControl(rdfid=new_rdf_id)
    elif ver == CGMESVersions.v3_0_0:
        rc = cgmes30.RegulatingControl(rdfid=new_rdf_id)
    else:
        raise NotImplemented()

    # RC for EQ
    rc.name = f'_RC_{mc_gen.name}'
    rc.shortName = rc.name
    rc.mode = RegulatingControlModeKind.voltage
    rc.Terminal = cgmes_elm.Terminals  # TODO get a terminal from the controlled bus !!!

    rc.RegulatingCondEq = cgmes_elm
    rc.discrete = False
    rc.targetDeadband = 0.5
    rc.targetValueUnitMultiplier = UnitMultiplier.k
    rc.enabled = True
    rc.targetValue = mc_gen.Vset * mc_gen.bus.Vnom
    # TODO control_cn.Vnom

    cgmes_model.add(rc)

    return rc


def create_cgmes_tap_changer_control(
        tap_changer,
        tcc_mode,
        tcc_enabled,
        mc_trafo: Union[gcdev.Transformer2W, gcdev.Transformer3W],
        cgmes_model: CgmesCircuit,
        ver: CGMESVersions,
        logger: DataLogger):
    """
    Create Tap Changer Control for Tap changers.

    :param tap_changer: Cgmes tap Changer
    :param tcc_mode: TapChangerContol mode attr (RegulatingControlModeKind.voltage)
    :param tcc_enabled: TapChangerContol enabled
    :param mc_trafo: MultiCircuit Transformer
    :param cgmes_model: CgmesCircuit
    :param ver:
    :param logger: DataLogger
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        tcc = cgmes24.TapChangerControl(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        tcc = cgmes30.TapChangerControl(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    # EQ
    tcc.name = f'_tcc_{mc_trafo.name}'
    tcc.shortName = tcc.name
    tcc.mode = tcc_mode
    tcc.Terminal = tap_changer.TransformerEnd.Terminal
    # SSH
    tcc.discrete = True
    tcc.targetDeadband = 0.5
    tcc.targetValueUnitMultiplier = UnitMultiplier.k
    tcc.enabled = tcc_enabled
    voltage: float | None = get_voltage_terminal(tcc.Terminal, logger)

    if voltage is not None:
        tcc.targetValue = mc_trafo.vset * voltage

        # TODO consider other control types
        # if mc_trafo.tap_module_control_mode ...:
        #     tcc.targetValue = mc_trafo.Pset
        # tcc.RegulatingCondEq not required .?
        # control_cn.Vnom ?

        cgmes_model.add(tcc)

    return tcc


def create_cgmes_current_limit(terminal,
                               rate_mw: float,
                               op_limit_type: CGMES_OPERATIONAL_LIMIT_TYPE,
                               cgmes_model: CgmesCircuit,
                               ver: CGMESVersions,
                               logger: DataLogger):
    """

    :param terminal: Cgmes Terminal
    :param rate_mw: rating in VeraGrid in MW/MVA
    :param op_limit_type: Operational Limit Type
    :param cgmes_model: CgmesModel
    :param ver: CGMESVersions
    :param logger: DataLogger
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        curr_lim = cgmes24.CurrentLimit(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        curr_lim = cgmes30.CurrentLimit(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    curr_lim.name = f'{terminal.name} - CL-1'
    curr_lim.shortName = f'CL-1'
    curr_lim.description = f'Ratings for element {terminal.ConductingEquipment.name} - Limit'

    voltage: float | None = get_voltage_terminal(terminal, logger)

    if voltage is not None:
        sqrt_3 = 1.73205080756888
        current_rate = rate_mw * 1e3 / (voltage * sqrt_3)
        current_rate = np.round(current_rate, 4)

        curr_lim.value = current_rate  # Current rate in Amps

        op_lim_set_1 = create_operational_limit_set(terminal, cgmes_model, ver, logger)
        if op_lim_set_1 is not None:
            curr_lim.OperationalLimitSet = op_lim_set_1
        else:
            logger.add_error(msg='No operational limit created',
                             device=op_lim_set_1,
                             comment="create_cgmes_current_limit")

        curr_lim.OperationalLimitType = op_limit_type

        cgmes_model.add(curr_lim)
    return


def create_operational_limit_set(terminal,
                                 cgmes_model: CgmesCircuit,
                                 ver: CGMESVersions,
                                 logger: DataLogger):
    """

    :param terminal:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        op_lim_set = cgmes24.OperationalLimitSet(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        op_lim_set = cgmes30.OperationalLimitSet(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    term_num = terminal.sequenceNumber if terminal.sequenceNumber is not None else 1
    op_lim_set.name = f'OperationalLimit at Term-{term_num}'
    op_lim_set.description = f'OperationalLimit at Port1'

    if is_term(terminal):
        op_lim_set.Terminal = terminal

    cgmes_model.add(op_lim_set)
    return op_lim_set


def create_cgmes_operational_limit_type(cgmes_model: CgmesCircuit, ver: CGMESVersions):
    """

    :param cgmes_model: CgmesModel
    :param ver:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        op_lim_type = cgmes24.OperationalLimitType(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        op_lim_type = cgmes30.OperationalLimitType(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    cgmes_model.add(op_lim_type)
    return op_lim_type


def create_cgmes_dc_tp_node(tp_name: str,
                            tp_description: str,
                            cgmes_model: CgmesCircuit,
                            ver: CGMESVersions,
                            logger: DataLogger):
    """
    Creates a DCTopologicalNode from a gcdev Bus
    :param tp_name:
    :param tp_description:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        dc_tp = cgmes24.DCTopologicalNode(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        dc_tp = cgmes30.DCTopologicalNode(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    dc_tp.name = tp_name
    dc_tp.description = tp_description

    cgmes_model.add(dc_tp)
    return dc_tp


def create_cgmes_dc_node(cn_name: str,
                         cn_description: str,
                         cgmes_model: CgmesCircuit,
                         dc_tp: CGMES_DC_TOPOLOGICAL_NODE,
                         dc_ec: CGMES_EQUIPMENT_CONTAINER,
                         ver: CGMESVersions,
                         logger: DataLogger):
    """
    Creates a DCTopologicalNode from a gcdev Bus

    :param cn_name:
    :param cn_description:
    :param cgmes_model:
    :param dc_tp: DC TopologicalNode
    :param dc_ec: DC EquipmentContainer (DCConverterUnit)
    :param ver:
    :param logger:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        dc_node = cgmes24.DCNode(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        dc_node = cgmes30.DCNode(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    dc_node.name = cn_name
    dc_node.description = cn_description
    dc_node.DCTopologicalNode = dc_tp
    dc_node.DCEquipmentContainer = dc_ec

    cgmes_model.add(dc_node)
    return dc_node


def create_cgmes_vsc_converter(cgmes_model: CgmesCircuit,
                               gc_vsc: Union[gcdev.VSC, None],
                               p_set: float,
                               v_set: float,
                               ver: CGMESVersions,
                               logger: DataLogger) -> Tuple[CGMES_VS_CONVERTER, CGMES_DC_CONVERTER_UNIT]:
    """
    Creates a new Voltage-source converter
    with a DCConverterUnit as a container

    :param cgmes_model: CgmesCircuit
    :param gc_vsc: optional input: VSC from VeraGrid
    :param p_set: power set point
    :param v_set: voltage set point, only used if gc_vsc is None,
                  otherwise the set point is from gc_vsc.vset
    :param ver:
    :param logger: DataLogger
    :return: VsConverter and DCConverterUnit objects
    """
    if gc_vsc is None:
        rdf_id = get_new_rdfid()
    else:
        rdf_id = form_rdfid(gc_vsc.idtag)

    if ver == CGMESVersions.v2_4_15:
        vs_converter = cgmes24.VsConverter(rdfid=rdf_id)
    elif ver == CGMESVersions.v3_0_0:
        vs_converter = cgmes30.VsConverter(rdfid=rdf_id)
    else:
        raise NotImplemented()

    if gc_vsc is not None:
        vs_converter.name = gc_vsc.name
        vs_converter.description = gc_vsc.code
        targetUpcc = gc_vsc.Vf
    else:
        i = len(cgmes_model.cgmes_assets.VsConverter_list)
        vs_converter.name = f'VSC_{i + 1}'
        vs_converter.description = f'VSC_{i + 1}'
        targetUpcc = v_set

    # EQ
    vs_converter.baseS = 9999
    vs_converter.idleLoss = 1.0
    # <cim:ACDCConverter.maxUdc>180.000000</cim:ACDCConverter.maxUdc>
    # <cim:ACDCConverter.minUdc>0e+000</cim:ACDCConverter.minUdc>
    # <cim:ACDCConverter.ratedUdc>160.000000</cim:ACDCConverter.ratedUdc>
    # <cim:ACDCConverter.resistiveLoss>2.000000</cim:ACDCConverter.resistiveLoss>
    # <cim:ACDCConverter.switchingLoss>0.000500</cim:ACDCConverter.switchingLoss>
    # <cim:ACDCConverter.valveU0>0e+000</cim:ACDCConverter.valveU0>
    # <cim:ACDCConverter.numberOfValves>1</cim:ACDCConverter.numberOfValves>
    # <cim:VsConverter.maxModulationIndex>1.000000</cim:VsConverter.maxModulationIndex>
    vs_converter.numberOfValves = 1
    vs_converter.switchingLoss = 0.00308
    vs_converter.maxValveCurrent = 99999

    # SSH
    vs_converter.p = p_set  # hvdc_line.Pset or VSC.Pset
    vs_converter.q = 0.0
    vs_converter.targetPpcc = p_set
    vs_converter.targetUdc = 0
    vs_converter.droop = 0
    vs_converter.droopCompensation = 0
    vs_converter.pPccControl = VsPpccControlKind.pPcc
    vs_converter.qPccControl = VsQpccControlKind.voltagePcc
    vs_converter.qShare = 100  # Reactive power-sharing factor among parallel converters on Uac control.
    vs_converter.targetQpcc = 0
    vs_converter.targetUpcc = targetUpcc

    # SV
    #     <cim:VsConverter.delta>0</cim:VsConverter.delta>
    #     <cim:VsConverter.uf>124.427328</cim:VsConverter.uf>
    #     <cim:ACDCConverter.uc>124.427328</cim:ACDCConverter.uc>
    #     <cim:ACDCConverter.udc>152.405856</cim:ACDCConverter.udc>
    #     <cim:ACDCConverter.poleLossP>3.333380</cim:ACDCConverter.poleLossP>
    #     <cim:ACDCConverter.idc>962.342430</cim:ACDCConverter.idc>

    # DCConverterUnit for containment
    dc_conv_unit_1 = create_cgmes_dc_converter_unit(cgmes_model=cgmes_model, ver=ver, logger=logger)
    dc_conv_unit_1.description = f'DC_Converter_Unit_for_{vs_converter.name}'
    vs_converter.EquipmentContainer = dc_conv_unit_1

    cgmes_model.add(vs_converter)
    return vs_converter, dc_conv_unit_1


def create_cgmes_acdc_converter_terminal(cgmes_model: CgmesCircuit,
                                         mc_dc_bus: Union[None, Bus],
                                         seq_num: Union[int, None],
                                         dc_node: Union[None, CGMES_DC_TOPOLOGICAL_NODE],
                                         dc_cond_eq: Union[None, CGMES_DC_CONDUCTING_EQUIPMENT],
                                         ver: CGMESVersions,
                                         logger: DataLogger):
    """
    Creates a new ACDCConverterDCTerminal in CGMES model,
    and connects it the relating DCNode

    :param cgmes_model:
    :param mc_dc_bus: optional input, if there is a DC bus in MultiCircuit
    :param seq_num:
    :param dc_node:
    :param dc_cond_eq:
    :param ver:
    :param logger:
    :return:
    """
    if mc_dc_bus is not None:
        if not mc_dc_bus.is_dc:
            logger.add_error(msg=f'Bus must be a DC bus',
                             device=mc_dc_bus,
                             device_property=mc_dc_bus.is_dc,
                             expected_value=True,
                             value=mc_dc_bus.is_dc,
                             comment="create_cgmes_acdc_converter_terminal")
            return None

    if ver == CGMESVersions.v2_4_15:
        acdc_term = cgmes24.ACDCConverterDCTerminal(get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        acdc_term = cgmes30.ACDCConverterDCTerminal(get_new_rdfid())
    else:
        raise NotImplemented()

    acdc_term.name = f'{dc_cond_eq.name} - T{seq_num}' if dc_cond_eq is not None else "ACDCTerm"
    acdc_term.description = f'{dc_cond_eq.name}_converter_DC_term'
    acdc_term.sequenceNumber = seq_num if seq_num is not None else 1

    if isinstance(dc_cond_eq, (cgmes24.ACDCConverter, cgmes30.ACDCConverter)):
        acdc_term.DCConductingEquipment = dc_cond_eq
    else:
        logger.add_error(msg=f'DCConductingEquipment must be an ACDCConverter',
                         device=dc_cond_eq,
                         value=str(dc_cond_eq),
                         expected_value="ACDCConverter",
                         comment="create_cgmes_acdc_converter_terminal")
    acdc_term.connected = True
    acdc_term.polarity = DCPolarityKind.positive

    if isinstance(dc_node, (cgmes24.DCNode, cgmes30.DCNode)):
        acdc_term.DCNode = dc_node

    cgmes_model.add(acdc_term)

    return acdc_term


def create_cgmes_dc_line(cgmes_model: CgmesCircuit,
                         ver: CGMESVersions,
                         logger: DataLogger) -> CGMES_DC_LINE:
    """
    Creates a new CGMES DCLine
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        dc_line = cgmes24.DCLine(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        dc_line = cgmes30.DCLine(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    cgmes_model.add(dc_line)
    return dc_line


def create_cgmes_dc_line_segment(cgmes_model: CgmesCircuit,
                                 mc_elm: Union[gcdev.HvdcLine, gcdev.DcLine],
                                 dc_tp_1: CGMES_DC_TOPOLOGICAL_NODE,
                                 dc_node_1: CGMES_CONNECTIVITY_NODE,
                                 dc_tp_2: CGMES_DC_TOPOLOGICAL_NODE,
                                 dc_node_2: CGMES_CONNECTIVITY_NODE,
                                 eq_cont: CGMES_EQUIPMENT_CONTAINER,
                                 ver: CGMESVersions,
                                 logger: DataLogger) -> CGMES_DC_LINE_SEGMENT:
    """
    Creates a new CGMES DCLineSegment

    :param cgmes_model:
    :param mc_elm:
    :param dc_tp_1:
    :param dc_node_1:
    :param dc_tp_2:
    :param dc_node_2:
    :param eq_cont: EquipmentContainer (DCLine)
    :param ver:
    :param logger:
    :return:
    """
    if ver == CGMESVersions.v2_4_15:
        dc_line_segment = cgmes24.DCLineSegment(rdfid=form_rdfid(mc_elm.idtag))
    elif ver == CGMESVersions.v3_0_0:
        dc_line_segment = cgmes30.DCLineSegment(rdfid=form_rdfid(mc_elm.idtag))
    else:
        raise NotImplemented()

    dc_line_segment.name = mc_elm.name
    dc_line_segment.description = mc_elm.code

    dc_line_segment.length = mc_elm.length if mc_elm.length is not None else 1.0
    dc_line_segment.resistance = mc_elm.r
    dc_line_segment.inductance = 0.0
    dc_line_segment.capacitance = 0.0
    dc_line_segment.aggregate = False

    dc_line_segment.EquipmentContainer = eq_cont

    # Terminals
    create_cgmes_dc_terminal(cgmes_model=cgmes_model,
                             dc_tp=dc_tp_1,
                             dc_node=dc_node_1,
                             dc_cond_eq=dc_line_segment,
                             seq_num=1,
                             ver=ver,
                             logger=logger)
    create_cgmes_dc_terminal(cgmes_model=cgmes_model,
                             dc_tp=dc_tp_2,
                             dc_node=dc_node_2,
                             dc_cond_eq=dc_line_segment,
                             seq_num=2,
                             ver=ver,
                             logger=logger)

    cgmes_model.add(dc_line_segment)
    return dc_line_segment


def create_cgmes_dc_terminal(cgmes_model: CgmesCircuit,
                             dc_tp: CGMES_DC_TOPOLOGICAL_NODE,
                             dc_node: CGMES_CONNECTIVITY_NODE,
                             dc_cond_eq: CGMES_DC_CONDUCTING_EQUIPMENT,
                             seq_num: int,
                             ver: CGMESVersions,
                             logger: DataLogger) -> CGMES_DC_TERMINAL:
    """
    Creates a new CGMES DCTerminal

    :param cgmes_model: CgmesCircuit
    :param dc_tp: DC TopologicalNode where the Terminal is connected
    :param dc_node: DC Node where the Terminal should be placed in
    :param dc_cond_eq: DC Conducting Equipment
    :param seq_num: sequence number
    :param logger: DataLogger
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        dc_term = cgmes24.DCTerminal(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        dc_term = cgmes30.DCTerminal(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    # EQ
    i = len(cgmes_model.cgmes_assets.DCTerminal_list)
    dc_term.name = f'DC_term_{i + 1}'

    if isinstance(dc_node, (cgmes24.DCNode, cgmes30.DCNode)):
        dc_term.DCNode = dc_node

    dc_term.DCConductingEquipment = dc_cond_eq
    dc_term.sequenceNumber = seq_num

    # TP
    dc_term.DCTopologicalNode = dc_tp

    # SSH
    dc_term.connected = True

    cgmes_model.add(dc_term)
    return dc_term


def create_cgmes_dc_converter_unit(cgmes_model: CgmesCircuit,
                                   ver: CGMESVersions,
                                   logger: DataLogger) -> CGMES_DC_CONVERTER_UNIT:
    """
    Creates a new CGMES DCConverterUnit

    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        dc_cu = cgmes24.DCConverterUnit(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        dc_cu = cgmes30.DCConverterUnit(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    dc_cu.Substation = None  # TODO
    dc_cu.operationMode = DCConverterOperatingModeKind.monopolarGroundReturn

    cgmes_model.add(dc_cu)
    return dc_cu


def create_cgmes_location(cgmes_model: CgmesCircuit,
                          device: CGMES_LINE,
                          longitude: float,
                          latitude: float,
                          ver: CGMESVersions,
                          logger: DataLogger) -> CGMES_LOCATION:
    """

    :param cgmes_model:
    :param device:
    :param longitude:
    :param latitude:
    :param ver:
    :param logger:
    :return:
    """
    if ver == CGMESVersions.v2_4_15:
        location = cgmes24.Location(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        location = cgmes30.Location(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    location.CoordinateSystem = cgmes_model.cgmes_assets.CoordinateSystem_list[0]
    location.PowerSystemResource = device

    if ver == CGMESVersions.v2_4_15:
        pos_point = cgmes24.PositionPoint(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        pos_point = cgmes30.PositionPoint(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    pos_point.Location = location
    pos_point.sequenceNumber = 1
    pos_point.xPosition = str(longitude)
    pos_point.yPosition = str(latitude)
    location.PositionPoint = pos_point

    cgmes_model.cgmes_assets.CoordinateSystem_list[0].Locations.append(location)
    cgmes_model.add(location)
    cgmes_model.add(pos_point)

    device.Location = location

    return location


def create_sv_power_flow(cgmes_model: CgmesCircuit,
                         p: float,
                         q: float,
                         terminal: CGMES_TERMINAL,
                         ver: CGMESVersions) -> None:
    """
    Creates a SvPowerFlow instance

    :param cgmes_model:
    :param p: The active power flow. Load sign convention is used,
                i.e. positive sign means flow out
                from a TopologicalNode (bus) into the conducting equipment.
    :param q:
    :param terminal:
    :param ver:
    :return:
    """
    if ver == CGMESVersions.v2_4_15:
        sv_pf = cgmes24.SvPowerFlow(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        sv_pf = cgmes30.SvPowerFlow(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    sv_pf.p = p
    sv_pf.q = q
    sv_pf.Terminal = terminal

    cgmes_model.add(sv_pf)


def create_sv_shunt_compensator_sections(cgmes_model: CgmesCircuit,
                                         sections: int,
                                         cgmes_shunt_compensator,
                                         ver: CGMESVersions) -> None:
    """
    Creates a SvShuntCompensatorSections instance

    :param cgmes_model: Cgmes Circuit
    :param sections: sections active
    :param cgmes_shunt_compensator: Linear or Non-linear ShuntCompensator instance from cgmes model
    :param ver:
    :return:
    """
    if ver == CGMESVersions.v2_4_15:
        sv_scs = cgmes24.SvShuntCompensatorSections(rdfid=get_new_rdfid(), tpe="SvShuntCompensatorSections")
    elif ver == CGMESVersions.v3_0_0:
        sv_scs = cgmes30.SvShuntCompensatorSections(rdfid=get_new_rdfid(), tpe="SvShuntCompensatorSections")
    else:
        raise NotImplemented()

    # sections: The number of sections in service as a continous variable.
    # To get integer value scale with ShuntCompensator.bPerSection.
    sv_scs.sections = sections
    sv_scs.ShuntCompensator = cgmes_shunt_compensator

    cgmes_model.add(sv_scs)


def create_sv_status(cgmes_model: CgmesCircuit,
                     in_service: int,
                     cgmes_conducting_equipment,
                     ver: CGMESVersions) -> None:
    """
    Creates a SvStatus instance

    :param cgmes_model: Cgmes Circuit
    :param in_service: is active parameter
    :param cgmes_conducting_equipment: cgmes CondEq
    :param ver:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        sv_status = cgmes24.SvStatus(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        sv_status = cgmes30.SvStatus(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    sv_status.inService = in_service
    # TODO sv_status.ConductingEquipment = cgmes_conducting_equipment

    cgmes_model.add(sv_status)


def create_cgmes_conform_load_group(
        cgmes_model: CgmesCircuit,
        ver: CGMESVersions,
        logger: DataLogger):
    """

    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        c_load_group = cgmes24.ConformLoadGroup(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        c_load_group = cgmes30.ConformLoadGroup(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    c_load_group.name = "_CLG_"
    c_load_group.description = "_CLG_"
    c_load_group.EnergyConsumers = []
    c_load_group.SubLoadArea = cgmes_model.cgmes_assets.SubLoadArea_list[0]

    cgmes_model.add(c_load_group)
    return c_load_group


def create_cgmes_non_conform_load_group(
        cgmes_model: CgmesCircuit,
        ver: CGMESVersions,
        logger: DataLogger):
    """

    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        nc_load_group = cgmes24.NonConformLoadGroup(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        nc_load_group = cgmes30.NonConformLoadGroup(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    nc_load_group.name = "_NCLG_"
    nc_load_group.description = "_NCLG_"
    nc_load_group.EnergyConsumers = []
    nc_load_group.SubLoadArea = cgmes_model.cgmes_assets.SubLoadArea_list[0]

    cgmes_model.add(nc_load_group)
    return nc_load_group


def create_cgmes_sub_load_area(
        cgmes_model: CgmesCircuit,
        ver: CGMESVersions,
        logger: DataLogger):
    """

    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    if ver == CGMESVersions.v2_4_15:
        sub_load_area = cgmes24.SubLoadArea(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        sub_load_area = cgmes30.SubLoadArea(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    sub_load_area.name = "_SLA_"
    sub_load_area.description = "_SLA_"
    sub_load_area.LoadArea = create_cgmes_load_area(cgmes_model, ver, logger)

    cgmes_model.add(sub_load_area)
    return sub_load_area


def create_cgmes_load_area(
        cgmes_model: CgmesCircuit,
        ver: CGMESVersions,
        logger: DataLogger):
    """

    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """
    if ver == CGMESVersions.v2_4_15:
        sub_load_area = cgmes24.LoadArea(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        sub_load_area = cgmes30.LoadArea(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    sub_load_area.name = "_LA_"
    sub_load_area.description = "_LA_"

    cgmes_model.add(sub_load_area)
    return sub_load_area


def create_cgmes_nonlinear_sc_point(
        section_num: int,
        b: float,
        g: float,
        nl_sc: CGMES_NON_LINEAR_SHUNT_COMPENSATOR,
        cgmes_model: CgmesCircuit,
        ver: CGMESVersions
):
    """
    
    :param section_num: 
    :param b: b in Siemens
    :param g: g in 
    :param nl_sc: NonlinearShuntCompensator object
    :param cgmes_model: CgmesModel
    :param ver:
    :return: 
    """""

    if ver == CGMESVersions.v2_4_15:
        nl_sc_p = cgmes24.NonlinearShuntCompensatorPoint(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        nl_sc_p = cgmes30.NonlinearShuntCompensatorPoint(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    nl_sc_p.sectionNumber = section_num
    nl_sc_p.b = b
    nl_sc_p.g = g
    nl_sc_p.b0 = 0.0
    nl_sc_p.g0 = 0.0
    nl_sc_p.NonlinearShuntCompensator = nl_sc

    cgmes_model.add(nl_sc_p)
