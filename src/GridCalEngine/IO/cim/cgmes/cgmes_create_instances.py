"""
Collection of functions to create new CGMES instances for CGMES export.
"""
import numpy as np
from datetime import datetime
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.IO.cim.cgmes.base import get_new_rdfid
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_enums import (cgmesProfile,
                                                    WindGenUnitKind,
                                                    RegulatingControlModeKind,
                                                    UnitMultiplier)
from GridCalEngine.IO.cim.cgmes.cgmes_utils import find_object_by_uuid
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.full_model import FullModel
from GridCalEngine.IO.cim.cgmes.base import Base
import GridCalEngine.Devices as gcdev
from GridCalEngine.enumerations import CGMESVersions

from GridCalEngine.data_logger import DataLogger
from typing import List, Union


def create_cgmes_headers(cgmes_model: CgmesCircuit,
                         profiles_to_export: List[cgmesProfile],
                         desc: str = "",
                         scenariotime: str = "",
                         modelingauthorityset: str = "", version: str = ""):
    """

    :param cgmes_model:
    :param profiles_to_export:
    :param desc:
    :param scenariotime:
    :param modelingauthorityset:
    :param version:
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
        fm.scenarioTime = scenariotime
        if modelingauthorityset != "":
            fm.modelingAuthoritySet = modelingauthorityset
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
        if cgmesProfile.OP in profiles_to_export:
            fm_list[0].profile.append(prof[1])
        if cgmesProfile.SC in profiles_to_export:
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
    if cgmes_model.cgmes_version == CGMESVersions.v2_4_15:  # if 2.4 than no need in SV in 3.0 we need all
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
                          cond_eq: Union[None, Base],
                          cgmes_model: CgmesCircuit,
                          logger: DataLogger):
    """
    Creates a new Terminal in CGMES model,
    and connects it the relating Topologinal Node
    :param mc_bus:
    :param seq_num:
    :param cond_eq:
    :param cgmes_model:
    :param logger:
    :return:
    """

    new_rdf_id = get_new_rdfid()
    terminal_template = cgmes_model.get_class_type("Terminal")
    term = terminal_template(new_rdf_id)
    term.name = f'{cond_eq.name} - T{seq_num}' if cond_eq is not None else ""
    # term.shortName =
    if seq_num is not None:
        term.sequenceNumber = seq_num

    # further properties
    # term.phases =
    # term.energyIdentCodeEic =

    cond_eq_type = cgmes_model.get_class_type("ConductingEquipment")
    if cond_eq and isinstance(cond_eq, cond_eq_type):
        term.ConductingEquipment = cond_eq
    term.connected = True

    tn = find_object_by_uuid(
        cgmes_model=cgmes_model,
        object_list=cgmes_model.cgmes_assets.TopologicalNode_list,
        target_uuid=mc_bus.idtag
    )
    if isinstance(tn, cgmes_model.get_class_type("TopologicalNode")):
        term.TopologicalNode = tn
        term.ConnectivityNode = tn.ConnectivityNodes
    else:
        logger.add_error(msg='No found TopologinalNode',
                         device=mc_bus,
                         device_class=gcdev.Bus)

    cgmes_model.add(term)

    return term


def create_cgmes_load_response_char(load: gcdev.Load,
                                    cgmes_model: CgmesCircuit,
                                    logger: DataLogger):
    """

    :param load:
    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    lrc_template = cgmes_model.get_class_type("LoadResponseCharacteristic")
    lrc = lrc_template(rdfid=new_rdf_id)
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
                                 cgmes_model: CgmesCircuit):
    """
    Creates the appropriate CGMES GeneratingUnit object
    from a MultiCircuit Generator.
    """

    new_rdf_id = get_new_rdfid()

    if len(gen.technologies) == 0:
        object_template = cgmes_model.get_class_type("GeneratingUnit")
        sm = object_template(new_rdf_id)
        cgmes_model.add(sm)
        return sm
    else:
        for tech_association in gen.technologies:

            if tech_association.api_object.name == 'General':
                object_template = cgmes_model.get_class_type("GeneratingUnit")
                sm = object_template(new_rdf_id)
                cgmes_model.add(sm)
                return sm

            if tech_association.api_object.name == 'Thermal':
                object_template = cgmes_model.get_class_type(
                    "ThermalGeneratingUnit")
                tgu = object_template(new_rdf_id)
                cgmes_model.add(tgu)
                return tgu

            if tech_association.api_object.name == 'Hydro':
                object_template = cgmes_model.get_class_type(
                    "HydroGeneratingUnit")
                hgu = object_template(new_rdf_id)
                cgmes_model.add(hgu)
                return hgu

            if tech_association.api_object.name == 'Solar':
                object_template = cgmes_model.get_class_type(
                    "SolarGeneratingUnit")
                sgu = object_template(new_rdf_id)
                cgmes_model.add(sgu)
                return sgu

            if tech_association.api_object.name == 'Wind Onshore':
                object_template = cgmes_model.get_class_type(
                    "WindGeneratingUnit")
                wgu = object_template(new_rdf_id)
                wgu.windGenUnitType = WindGenUnitKind.onshore
                cgmes_model.add(wgu)
                return wgu

            if tech_association.api_object.name == 'Wind Offshore':
                object_template = cgmes_model.get_class_type(
                    "WindGeneratingUnit")
                wgu = object_template(new_rdf_id)
                wgu.windGenUnitType = WindGenUnitKind.offshore
                cgmes_model.add(wgu)
                return wgu

            if tech_association.api_object.name == 'Nuclear':
                object_template = cgmes_model.get_class_type(
                    "NuclearGeneratingUnit")
                ngu = object_template(new_rdf_id)
                cgmes_model.add(ngu)
                return ngu

    return None


def create_cgmes_regulating_control(cgmes_syn,
                                    mc_gen: gcdev.Generator,
                                    cgmes_model: CgmesCircuit,
                                    logger: DataLogger):
    """
    Create Regulating Control for Generators

    :param cgmes_syn: Cgmes Synchronous Machine
    :param mc_gen: MultiCircuit Generator
    :param cgmes_model: CgmesCircuit
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("RegulatingControl")
    rc = object_template(rdfid=new_rdf_id)

    # RC for EQ
    rc.name = f'_RC_{mc_gen.name}'
    rc.shortName = rc.name
    rc.mode = RegulatingControlModeKind.voltage
    rc.Terminal = create_cgmes_terminal(mc_bus=mc_gen.bus,
                                        seq_num=1,
                                        cond_eq=cgmes_syn,
                                        cgmes_model=cgmes_model,
                                        logger=logger)

    rc.RegulatingCondEq = cgmes_syn
    rc.discrete = False
    rc.targetDeadband = 0.5
    rc.targetValueUnitMultiplier = UnitMultiplier.k
    rc.enabled = True  # todo correct?
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
        logger: DataLogger):
    """
    Create Tap Changer Control for Tap changers.

    :param tap_changer: Cgmes tap Changer
    :param tcc_mode: TapChangerContol mode attr (RegulatingControlModeKind.voltage)
    :param tcc_enabled: TapChangerContol enabled
    :param mc_trafo: MultiCircuit Transformer
    :param cgmes_model: CgmesCircuit
    :param logger: DataLogger
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("TapChangerControl")
    tcc = object_template(rdfid=new_rdf_id)

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
    if tcc.enabled:
        tcc.targetValue = 0.0  # TODO # if enabled it should be calculated
    else:
        tcc.targetValue = None
    # tcc.RegulatingCondEq not required .?
    # control_cn.Vnom ?

    cgmes_model.add(tcc)

    return tcc


def create_cgmes_current_limit(terminal,
                               rate: float,
                               # mc_elm: Union[gcdev.Line,
                               #               # gcdev.Transformer2W,
                               #               # gcdev.Transformer3W
                               #               ],
                               cgmes_model: CgmesCircuit,
                               logger: DataLogger):
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("CurrentLimit")
    curr_lim = object_template(rdfid=new_rdf_id)
    curr_lim.name = f'{terminal.name} - CL-1'
    curr_lim.shortName = f'CL-1'
    curr_lim.description = f'Ratings for element {terminal.ConductingEquipment.name} - Limit'

    curr_lim.value = rate

    op_lim_set_1 = create_operational_limit_set(terminal, cgmes_model, logger)
    if op_lim_set_1 is not None:
        curr_lim.OperationalLimitSet = op_lim_set_1
    else:
        logger.add_error(msg='No operational limit created')

    # curr_lim.OperationalLimitType

    cgmes_model.add(curr_lim)
    return


def create_operational_limit_set(terminal,
                                 cgmes_model: CgmesCircuit,
                                 logger: DataLogger):
    """

    :param terminal:
    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("OperationalLimitSet")
    op_lim_set = object_template(rdfid=new_rdf_id)
    term_num = terminal.sequenceNumber if terminal.sequenceNumber is not None else 1
    op_lim_set.name = f'OperationalLimit at Term-{term_num}'
    op_lim_set.description = f'OperationalLimit at Port1'

    terminal_type = cgmes_model.get_class_type('Terminal')
    if isinstance(terminal, terminal_type):
        op_lim_set.Terminal = terminal

    cgmes_model.add(op_lim_set)
    return op_lim_set


def create_cgmes_operational_limit_type(mc_elm: gcdev.Line,
                                        cgmes_model: CgmesCircuit,
                                        logger: DataLogger):
    """

    :param mc_elm:
    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("OperationalLimitSet")
    op_lim_type = object_template(rdfid=new_rdf_id)

    cgmes_model.add(op_lim_type)
    return op_lim_type


def create_cgmes_dc_tp_node(tp_name: str,
                            tp_description: str,
                            cgmes_model: CgmesCircuit,
                            logger: DataLogger):
    """
    Creates a DCTopologicalNode from a gcdev Bus
    :param tp_name:
    :param tp_description:
    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("DCTopologicalNode")
    dc_tp = object_template(rdfid=new_rdf_id)

    dc_tp.name = tp_name
    dc_tp.description = tp_description

    cgmes_model.add(dc_tp)
    return dc_tp


def create_cgmes_dc_node(cn_name: str,
                         cn_description: str,
                         cgmes_model: CgmesCircuit,
                         logger: DataLogger):
    """
    Creates a DCTopologicalNode from a gcdev Bus

    :param cn_name:
    :param cn_description:
    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("DCNode")
    dc_node = object_template(rdfid=new_rdf_id)

    dc_node.name = cn_name
    dc_node.description = cn_description

    cgmes_model.add(dc_node)
    return dc_node


def create_cgmes_location(cgmes_model: CgmesCircuit,
                          device: Base,
                          longitude: float,
                          latitude: float,
                          logger: DataLogger):
    """

    :param cgmes_model:
    :param device:
    :param longitude:
    :param latitude:
    :param logger:
    :return:
    """
    object_template = cgmes_model.get_class_type("Location")
    location = object_template(rdfid=get_new_rdfid(), tpe="Location")

    location.CoordinateSystem = cgmes_model.cgmes_assets.CoordinateSystem_list[0]
    location.PowerSystemResource = device

    position_point_t = cgmes_model.get_class_type("PositionPoint")
    pos_point = position_point_t(rdfid=get_new_rdfid(), tpe="PositionPoint")
    pos_point.Location = location
    pos_point.sequenceNumber = 1
    pos_point.xPosition = str(longitude)
    pos_point.yPosition = str(latitude)
    location.PositionPoint = pos_point

    cgmes_model.cgmes_assets.CoordinateSystem_list[0].Locations.append(location)
    cgmes_model.add(location)
    cgmes_model.add(pos_point)

    device.Location = location

    return
