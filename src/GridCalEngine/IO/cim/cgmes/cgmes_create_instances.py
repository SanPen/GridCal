"""
Collection of functions to create new CGMES instances for CGMES export.
"""
import numpy as np
from datetime import datetime

from GridCalEngine import StrVec
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.IO.cim.cgmes.base import get_new_rdfid, form_rdfid
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_enums import (cgmesProfile,
                                                    WindGenUnitKind,
                                                    RegulatingControlModeKind,
                                                    UnitMultiplier,
                                                    DCPolarityKind,
                                                    DCConverterOperatingModeKind,
                                                    VsPpccControlKind,
                                                    VsQpccControlKind)
from GridCalEngine.IO.cim.cgmes.cgmes_utils import find_object_by_uuid, \
    get_voltage_terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.full_model import FullModel
from GridCalEngine.IO.cim.cgmes.base import Base
import GridCalEngine.Devices as gcdev
from GridCalEngine.enumerations import CGMESVersions

from GridCalEngine.data_logger import DataLogger
from typing import List, Union


def create_cgmes_headers(cgmes_model: CgmesCircuit,
                         mas_names: StrVec,
                         profiles_to_export: List[cgmesProfile],
                         logger: DataLogger,
                         desc: str = "",
                         scenariotime: str = "", version: str = ""):
    """

    :param cgmes_model:
    :param mas_names:
    :param profiles_to_export:
    :param desc:
    :param scenariotime:
    :param modelingauthorityset:
    :param version:
    :param logger:
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
        fm.modelingAuthoritySet = []
        if len(mas_names):
            for mas_name in mas_names:
                fm.modelingAuthoritySet.append(mas_name)
        else:
            fm.modelingAuthoritySet.append("http://www.ree.es/OperationalPlanning")
            logger.add_warning(msg="Missing Modeling Authority! (set to default)",
                               comment="Default value used. (http://www.ree.es/OperationalPlanning)")
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
        logger.add_error(msg='No found TopologicalNode',
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


def create_cgmes_regulating_control(cgmes_elm,
                                    mc_gen: Union[gcdev.Generator, gcdev.ControllableShunt],
                                    cgmes_model: CgmesCircuit,
                                    logger: DataLogger):
    """
    Create Regulating Control for a CGMES device

    :param cgmes_elm: Cgmes Synchronous Machine or Shunt (Nonlin or Lin)
    :param mc_gen: MultiCircuit element: Generator or Controllable Shunt
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
    rc.Terminal = cgmes_elm.Terminals   # TODO get a terminal from the controlled bus !!!

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
    voltage = get_voltage_terminal(tcc.Terminal, logger)
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
                               op_limit_type: Base,
                               cgmes_model: CgmesCircuit,
                               logger: DataLogger):
    """

    :param terminal: Cgmes Terminal
    :param rate_mw: rating in GridCal in MW/MVA
    :param op_limit_type: Operational Limit Type
    :param cgmes_model: CgmesModel
    :param logger: DataLogger
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("CurrentLimit")
    curr_lim = object_template(rdfid=new_rdf_id)
    curr_lim.name = f'{terminal.name} - CL-1'
    curr_lim.shortName = f'CL-1'
    curr_lim.description = f'Ratings for element {terminal.ConductingEquipment.name} - Limit'

    voltage = get_voltage_terminal(terminal, logger)
    sqrt_3 = 1.73205080756888
    current_rate = rate_mw * 1e3 / (voltage * sqrt_3)
    current_rate = np.round(current_rate, 4)

    curr_lim.value = current_rate  # Current rate in Amps

    op_lim_set_1 = create_operational_limit_set(terminal, cgmes_model, logger)
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


def create_cgmes_operational_limit_type(cgmes_model: CgmesCircuit):
    """

    :param cgmes_model: CgmesModel
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("OperationalLimitType")
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
                         dc_tp: Base,
                         dc_ec: Base,
                         logger: DataLogger):
    """
    Creates a DCTopologicalNode from a gcdev Bus

    :param cn_name:
    :param cn_description:
    :param cgmes_model:
    :param dc_tp: DC TopologicalNode
    :param dc_ec: DC EquipmentContainer (DCConverterUnit)
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("DCNode")
    dc_node = object_template(rdfid=new_rdf_id)

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
                               logger: DataLogger) -> (Base, Base):
    """
    Creates a new Voltage-source converter
    with a DCConverterUnit as a container

    :param cgmes_model: CgmesCircuit
    :param gc_vsc: optional input: VSC from GridCal
    :param p_set: power set point
    :param v_set: voltage set point, only used if gc_vsc is None, otherwise the setpoint is from gc_vsc.vset
    :param logger: DataLogger
    :return: VsConverter and DCConverterUnit objects
    """
    if gc_vsc is None:
        rdf_id = get_new_rdfid()
    else:
        rdf_id = form_rdfid(gc_vsc.idtag)
    object_template = cgmes_model.get_class_type("VsConverter")
    vs_converter = object_template(rdfid=rdf_id)

    if gc_vsc is not None:
        vs_converter.name = gc_vsc.name
        vs_converter.description = gc_vsc.code
        targetUpcc = gc_vsc.vset
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
    dc_conv_unit_1 = create_cgmes_dc_converter_unit(cgmes_model=cgmes_model,
                                                    logger=logger)
    dc_conv_unit_1.description = f'DC_Converter_Unit_for_{vs_converter.name}'
    vs_converter.EquipmentContainer = dc_conv_unit_1

    cgmes_model.add(vs_converter)
    return vs_converter, dc_conv_unit_1


def create_cgmes_acdc_converter_terminal(cgmes_model: CgmesCircuit,
                                         mc_dc_bus: Union[None, Bus],
                                         seq_num: Union[int, None],
                                         dc_node: Union[None, Base],
                                         dc_cond_eq: Union[None, Base],
                                         logger: DataLogger):
    """
    Creates a new ACDCConverterDCTerminal in CGMES model,
    and connects it the relating DCNode

    :param cgmes_model:
    :param mc_dc_bus: optional input, if there is a DC bus in MultiCircuit
    :param seq_num:
    :param dc_node:
    :param dc_cond_eq:
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

    new_rdf_id = get_new_rdfid()
    terminal_template = cgmes_model.get_class_type("ACDCConverterDCTerminal")
    acdc_term = terminal_template(new_rdf_id)
    acdc_term.name = f'{dc_cond_eq.name} - T{seq_num}' if dc_cond_eq is not None else "ACDCTerm"
    acdc_term.description = f'{dc_cond_eq.name}_converter_DC_term'
    acdc_term.sequenceNumber = seq_num if seq_num is not None else 1

    if isinstance(dc_cond_eq, cgmes_model.get_class_type("ACDCConverter")):
        acdc_term.DCConductingEquipment = dc_cond_eq
    else:
        logger.add_error(msg=f'DCConductingEquipment must be an ACDCConverter',
                         device=dc_cond_eq,
                         value=dc_cond_eq.tpe,
                         expected_value="ACDCConverter",
                         comment="create_cgmes_acdc_converter_terminal")
    acdc_term.connected = True
    acdc_term.polarity = DCPolarityKind.positive

    if isinstance(dc_node, cgmes_model.get_class_type("DCNode")):
        acdc_term.DCNode = dc_node

    # tn = find_object_by_uuid(
    #     cgmes_model=cgmes_model,
    #     object_list=cgmes_model.cgmes_assets.DCTopologicalNode_list,
    #     target_uuid=mc_dc_bus.idtag
    # )
    # if isinstance(tn, cgmes_model.get_class_type("TopologicalNode")):
    #     acdc_term.TopologicalNode = tn
    #     acdc_term.ConnectivityNode = tn.ConnectivityNodes
    # else:
    #     logger.add_error(msg='No found TopologinalNode',
    #                      device=mc_dc_bus,
    #                      device_class=gcdev.Bus)

    cgmes_model.add(acdc_term)

    return acdc_term


def create_cgmes_dc_line(cgmes_model: CgmesCircuit,
                         logger: DataLogger) -> Base:
    """
    Creates a new CGMES DCLine

    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("DCLine")
    dc_line = object_template(rdfid=new_rdf_id)

    cgmes_model.add(dc_line)
    return dc_line


def create_cgmes_dc_line_segment(cgmes_model: CgmesCircuit,
                                 mc_elm: Union[gcdev.HvdcLine,
                                 gcdev.DcLine],
                                 dc_tp_1: Base,
                                 dc_node_1: Base,
                                 dc_tp_2: Base,
                                 dc_node_2: Base,
                                 eq_cont: Base,
                                 logger: DataLogger) -> Base:
    """
    Creates a new CGMES DCLineSegment

    :param cgmes_model:
    :param mc_elm:
    :param dc_tp_1:
    :param dc_node_1:
    :param dc_tp_2:
    :param dc_node_2:
    :param eq_cont: EquipmentContainer (DCLine)
    :param logger:
    :return:
    """
    object_template = cgmes_model.get_class_type("DCLineSegment")
    dc_line_segment = object_template(rdfid=form_rdfid(mc_elm.idtag))

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
                             logger=logger)
    create_cgmes_dc_terminal(cgmes_model=cgmes_model,
                             dc_tp=dc_tp_2,
                             dc_node=dc_node_2,
                             dc_cond_eq=dc_line_segment,
                             seq_num=2,
                             logger=logger)

    cgmes_model.add(dc_line_segment)
    return dc_line_segment


def create_cgmes_dc_terminal(cgmes_model: CgmesCircuit,
                             dc_tp: Base,
                             dc_node: Base,
                             dc_cond_eq: Base,
                             seq_num: int,
                             logger: DataLogger) -> Base:
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
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("DCTerminal")
    dc_term = object_template(rdfid=new_rdf_id)

    # EQ
    i = len(cgmes_model.cgmes_assets.DCTerminal_list)
    dc_term.name = f'DC_term_{i + 1}'
    if isinstance(dc_node, cgmes_model.get_class_type("DCNode")):
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
                                   logger: DataLogger) -> Base:
    """
    Creates a new CGMES DCConverterUnit

    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("DCConverterUnit")
    dc_cu = object_template(rdfid=new_rdf_id)

    dc_cu.Substation = None  # TODO
    dc_cu.operationMode = DCConverterOperatingModeKind.monopolarGroundReturn

    cgmes_model.add(dc_cu)
    return dc_cu


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


def create_sv_power_flow(cgmes_model: CgmesCircuit,
                         p: float,
                         q: float,
                         terminal) -> None:
    """
    Creates a SvPowerFlow instance

    :param cgmes_model:
    :param p: The active power flow. Load sign convention is used,
                i.e. positive sign means flow out
                from a TopologicalNode (bus) into the conducting equipment.
    :param q:
    :param terminal:
    :return:
    """
    object_template = cgmes_model.get_class_type("SvPowerFlow")
    new_rdf_id = get_new_rdfid()
    sv_pf = object_template(rdfid=new_rdf_id)

    sv_pf.p = p
    sv_pf.q = q
    sv_pf.Terminal = terminal

    cgmes_model.add(sv_pf)


def create_sv_shunt_compensator_sections(cgmes_model: CgmesCircuit,
                                         sections: int,
                                         cgmes_shunt_compensator) -> None:
    """
    Creates a SvShuntCompensatorSections instance

    :param cgmes_model: Cgmes Circuit
    :param sections: sections active
    :param cgmes_shunt_compensator: Linear or Non-linear
        ShuntCompensator instance from cgmes model
    :return:
    """
    object_template = cgmes_model.get_class_type("SvShuntCompensatorSections")
    new_rdf_id = get_new_rdfid()
    sv_scs = object_template(rdfid=new_rdf_id, 
                             tpe="SvShuntCompensatorSections")

    # sections: The number of sections in service as a continous variable.
    # To get integer value scale with ShuntCompensator.bPerSection.
    sv_scs.sections = sections
    sv_scs.ShuntCompensator = cgmes_shunt_compensator

    cgmes_model.add(sv_scs)


def create_sv_status(cgmes_model: CgmesCircuit,
                     in_service: int,
                     cgmes_conducting_equipment) -> None:
    """
    Creates a SvStatus instance

    :param cgmes_model: Cgmes Circuit
    :param in_service: is active paramater
    :param cgmes_conducting_equipment: cgmes CondEq
    :return:
    """
    object_template = cgmes_model.get_class_type("SvStatus")
    new_rdf_id = get_new_rdfid()
    sv_status = object_template(rdfid=new_rdf_id)

    sv_status.inService = in_service
    # TODO sv_status.ConductingEquipment = cgmes_conducting_equipment

    cgmes_model.add(sv_status)


def create_cgmes_conform_load_group(
        cgmes_model: CgmesCircuit,
        logger: DataLogger):
    """

    :param mc_elm:
    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("ConformLoadGroup")
    c_load_group = object_template(rdfid=new_rdf_id)
    c_load_group.name = "_CLG_"
    c_load_group.description = "_CLG_"
    c_load_group.EnergyConsumers = []
    c_load_group.SubLoadArea = cgmes_model.cgmes_assets.SubLoadArea_list[0]

    cgmes_model.add(c_load_group)
    return c_load_group


def create_cgmes_non_conform_load_group(
        cgmes_model: CgmesCircuit,
        logger: DataLogger):
    """

    :param mc_elm:
    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("NonConformLoadGroup")
    nc_load_group = object_template(rdfid=new_rdf_id)
    nc_load_group.name = "_NCLG_"
    nc_load_group.description = "_NCLG_"
    nc_load_group.EnergyConsumers = []
    nc_load_group.SubLoadArea = cgmes_model.cgmes_assets.SubLoadArea_list[0]

    cgmes_model.add(nc_load_group)
    return nc_load_group


def create_cgmes_sub_load_area(
        cgmes_model: CgmesCircuit,
        logger: DataLogger):
    """

    :param mc_elm:
    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("SubLoadArea")
    sub_load_area = object_template(rdfid=new_rdf_id)
    sub_load_area.name = "_SLA_"
    sub_load_area.description = "_SLA_"
    sub_load_area.LoadArea = create_cgmes_load_area(cgmes_model, logger)

    cgmes_model.add(sub_load_area)
    return sub_load_area


def create_cgmes_load_area(
        cgmes_model: CgmesCircuit,
        logger: DataLogger):
    """

    :param mc_elm:
    :param cgmes_model:
    :param logger:
    :return:
    """
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("LoadArea")
    sub_load_area = object_template(rdfid=new_rdf_id)
    sub_load_area.name = "_LA_"
    sub_load_area.description = "_LA_"

    cgmes_model.add(sub_load_area)
    return sub_load_area


def create_cgmes_nonlinear_sc_point(
        section_num: int,
        b: float,
        g: float,
        nl_sc: Base,
        cgmes_model: CgmesCircuit,
    ):
    """
    
    :param section_num: 
    :param b: b in Siemens
    :param g: g in 
    :param nl_sc: NonlinearShuntCompensator object
    :param cgmes_model: CgmesModel
    :param logger: DataLogger
    :return: 
    """""
    new_rdf_id = get_new_rdfid()
    object_template = cgmes_model.get_class_type("NonlinearShuntCompensatorPoint")
    nl_sc_p = object_template(rdfid=new_rdf_id)

    nl_sc_p.sectionNumber = section_num
    nl_sc_p.b = b
    nl_sc_p.g = g
    nl_sc_p.b0 = 0.0
    nl_sc_p.g0 = 0.0
    nl_sc_p.NonlinearShuntCompensator = nl_sc

    cgmes_model.add(nl_sc_p)
