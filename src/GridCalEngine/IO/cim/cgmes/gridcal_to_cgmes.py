from GridCalEngine.Devices import MultiCircuit
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.IO.cim.cgmes.base import get_new_rdfid, form_rdfid, rfid2uuid
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.full_model import FullModel
from GridCalEngine.IO.cim.cgmes.base import Base
import GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices as cgmes
import GridCalEngine.Devices as gcdev
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults

from GridCalEngine.data_logger import DataLogger
from typing import Dict, List, Tuple, Union


# region UTILS

# class ReferenceManager:
#     # use it after an element object added
#     def __init__(self):
#         self.data = dict()
#
#     def add(self, cgmes_obj: Base):
#
#         tpe_dict = self.data.get(cgmes_obj.tpe, None)
#         if tpe_dict is None:
#             self.data[cgmes_obj.tpe] = {cgmes_obj.rdfid: cgmes_obj}
#         else:
#             tpe_dict[cgmes_obj.rdfid] = cgmes_obj


def find_object_by_uuid(cgmes_model: CgmesCircuit, object_list, target_uuid):  # TODO move to CGMES utils
    """
    Finds an object with the specified uuid
     in the given object_list from a CGMES Circuit.

    Args:
        cgmes_model:
        object_list (list[MyObject]): List of MyObject instances.
        target_uuid (str): The uuid to search for.

    Returns:
        MyObject or None: The found object or None if not found.
    """
    boundary_obj_dict = cgmes_model.all_objects_dict_boundary
    if boundary_obj_dict is not None:
        for k, obj in boundary_obj_dict.items():
            if rfid2uuid(k) == target_uuid:
                return obj
    for obj in object_list:
        if obj.uuid == target_uuid:
            return obj
    return None


def find_object_by_vnom(cgmes_model: CgmesCircuit, object_list: List[cgmes.BaseVoltage], target_vnom):
    boundary_obj_list = cgmes_model.elements_by_type_boundary.get("BaseVoltage")
    if boundary_obj_list is not None:
        for obj in boundary_obj_list:
            if obj.nominalVoltage == target_vnom:
                return obj
    for obj in object_list:
        if obj.nominalVoltage == target_vnom:
            return obj
    return None


def find_object_by_attribute(object_list: List, target_attr_name, target_value):
    if hasattr(object_list[0], target_attr_name):
        for obj in object_list:
            obj_attr = getattr(obj, target_attr_name)
            if obj_attr == target_value:
                return obj
    return None


def get_ohm_values_power_transformer(r, x, g, b, r0, x0, g0, b0, nominal_power, rated_voltage):
    """
    Get the transformer ohm values
    :return:
    """
    try:
        Sbase_system = 100
        Zbase = (rated_voltage * rated_voltage) / nominal_power
        Ybase = 1.0 / Zbase
        R, X, G, B = 0, 0, 0, 0
        R0, X0, G0, B0 = 0, 0, 0, 0
        machine_to_sys = Sbase_system / nominal_power
        R = r * Zbase / machine_to_sys
        X = x * Zbase / machine_to_sys
        G = g * Ybase / machine_to_sys
        B = b * Ybase / machine_to_sys
        R0 = r0 * Zbase / machine_to_sys if r0 is not None else 0
        X0 = x0 * Zbase / machine_to_sys if x0 is not None else 0
        G0 = g0 * Ybase / machine_to_sys if g0 is not None else 0
        B0 = b0 * Ybase / machine_to_sys if b0 is not None else 0

    except KeyError:
        R, X, G, B = 0, 0, 0, 0
        R0, X0, G0, B0 = 0, 0, 0, 0

    return R, X, G, B, R0, X0, G0, B0


# endregion

# region create new classes for CC

def create_cgmes_headers(cgmes_model: CgmesCircuit, desc: str = "", scenariotime: str = "",
                         modelingauthorityset: str = "", version: str = ""):
    from datetime import datetime

    fm_list = [FullModel(rdfid=get_new_rdfid(), tpe="FullModel"), FullModel(rdfid=get_new_rdfid(), tpe="FullModel"),
               FullModel(rdfid=get_new_rdfid(), tpe="FullModel"), FullModel(rdfid=get_new_rdfid(), tpe="FullModel")]
    for fm in fm_list:
        fm.scenarioTime = scenariotime
        if modelingauthorityset != "":
            fm.modelingAuthoritySet = modelingauthorityset
        current_time = datetime.utcnow()
        formatted_time = current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        fm.created = formatted_time
        fm.version = version
        fm.description = desc

    if cgmes_model.cgmes_version == "2.4.15":
        profile_uris = {
            "EQ": ["http://entsoe.eu/CIM/EquipmentCore/3/1",
                   "http://entsoe.eu/CIM/EquipmentShortCircuit/3/1",
                   "http://entsoe.eu/CIM/EquipmentOperation/3/1"],
            "SSH": ["http://entsoe.eu/CIM/SteadyStateHypothesis/1/1"],
            "TP": ["http://entsoe.eu/CIM/Topology/4/1"],
            "SV": ["http://entsoe.eu/CIM/StateVariables/4/1"]
        }
    elif cgmes_model.cgmes_version == "3.0.0":
        profile_uris = {
            "EQ": ["http://iec.ch/TC57/ns/CIM/CoreEquipment-EU/3.0",
                   "http://iec.ch/TC57/ns/CIM/Operation-EU/3.0",
                   "http://iec.ch/TC57/ns/CIM/ShortCircuit-EU/3.0"],
            "SSH": ["http://iec.ch/TC57/ns/CIM/SteadyStateHypothesis-EU/3.0"],
            "TP": ["http://iec.ch/TC57/ns/CIM/Topology-EU/3.0"],
            "SV": ["http://iec.ch/TC57/ns/CIM/StateVariables-EU/3.0"]
        }
    else:
        return

    # EQ profiles
    prof = profile_uris.get("EQ")
    fm_list[0].profile = [prof[0]]
    if True:  # TODO How to decide if it contains Operation?
        fm_list[0].profile.append(prof[1])
    if True:  # TODO How to decide if it contains ShortCircuit?
        fm_list[0].profile.append(prof[2])

    fm_list[1].profile = profile_uris.get("SSH")
    fm_list[2].profile = profile_uris.get("TP")
    fm_list[3].profile = profile_uris.get("SV")

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
            fm_list[3].DependentOn = [tpbd_id, fm_list[1].rdfid, fm_list[2].rdfid]
        else:
            fm_list[3].DependentOn = [fm_list[1].rdfid, fm_list[2].rdfid]
    except TypeError:
        print("Missing default boundary files")
        fm_list[1].DependentOn = [fm_list[0].rdfid]
        fm_list[2].DependentOn = [fm_list[0].rdfid]
        fm_list[3].DependentOn = [fm_list[0].rdfid, fm_list[1].rdfid, fm_list[2].rdfid]

    cgmes_model.cgmes_assets.FullModel_list = fm_list
    return cgmes_model


def create_cgmes_terminal(bus: Bus,
                          cgmes_model: CgmesCircuit,
                          logger: DataLogger) -> cgmes.Terminal:
    """ Creates a new Terminal in CGMES model,
    and connects it the relating Topologinal Node """

    new_rdf_id = get_new_rdfid()
    term = cgmes.Terminal(new_rdf_id)
    term.name = bus.name
    # term.phases =
    # term.ConductingEquipment = BusBarSection
    term.connected = True
    tn = find_object_by_uuid(
        cgmes_model=cgmes_model,
        object_list=cgmes_model.cgmes_assets.TopologicalNode_list,
        target_uuid=bus.idtag
    )

    if isinstance(tn, cgmes.TopologicalNode):
        term.TopologicalNode = tn
    else:
        logger.add_error(msg='No found TopologinalNode',
                         device=bus,
                         device_class=gcdev.Bus)

    cgmes_model.add(term)

    return term


def create_cgmes_load_response_char(
        load: gcdev.Load,
        logger: DataLogger) -> cgmes.LoadResponseCharacteristic:
    new_rdf_id = get_new_rdfid()
    lrc = cgmes.LoadResponseCharacteristic(rdfid=new_rdf_id)
    # lrc.name =
    lrc.pConstantCurrent = load.Ir / load.P if load.P != 0.0 else 0
    lrc.qConstantCurrent = load.Ii / load.Q if load.Q != 0.0 else 0
    lrc.pConstantImpedance = load.G / load.P if load.P != 0.0 else 0
    lrc.qConstantImpedance = load.B / load.Q if load.Q != 0.0 else 0  # TODO ask Chavdar
    lrc.pConstantPower = 1 - lrc.pConstantCurrent - lrc.pConstantImpedance
    lrc.qConstantPower = 1 - lrc.qConstantCurrent - lrc.qConstantImpedance
    if lrc.pConstantPower < 0 or lrc.qConstantPower < 0:
        logger.add_error(msg='Constant Impedance/Current parameters are not correct',
                         device=load,
                         device_class=gcdev.Load)
    # sum for 3 for p = 1
    # TODO B only 1 lrc for every load
    # if it not supports voltage dependent load, lf wont be the same
    return lrc


def create_cgmes_generating_unit(gen: gcdev.Generator,
                                 cgmes_model: CgmesCircuit) \
        -> Union[cgmes.GeneratingUnit, None]:
    """
    Creates the appropriate CGMES GeneratingUnit object
    from a MultiCircuit Generator.
    """

    new_rdf_id = get_new_rdfid()
    if gen.technology.name == 'General':
        sm = cgmes.GeneratingUnit(new_rdf_id)
        cgmes_model.add(sm)
        return sm

    if gen.technology.name == 'Thermal':
        tgu = cgmes.ThermalGeneratingUnit(new_rdf_id)
        cgmes_model.add(tgu)
        return tgu

    if gen.technology.name == 'Hydro':
        hgu = cgmes.HydroGeneratingUnit(new_rdf_id)
        cgmes_model.add(hgu)
        return hgu

    if gen.technology.name == 'Solar':
        sgu = cgmes.SolarGeneratingUnit(new_rdf_id)
        cgmes_model.add(sgu)
        return sgu

    if gen.technology.name == 'Wind':
        wgu = cgmes.WindGeneratingUnit(new_rdf_id)
        cgmes_model.add(wgu)
        return wgu

    if gen.technology.name == 'Nuclear':
        ngu = cgmes.NuclearGeneratingUnit(new_rdf_id)
        cgmes_model.add(ngu)
        return ngu

    return None


def create_cgmes_regulating_control(
        gen: gcdev.Generator,
        cgmes_model: CgmesCircuit) -> Union[cgmes.RegulatingControl, None]:
    """

    :param gen: MultiCircuit Generator
    :param cgmes_model: CgmesCircuit
    :return:
    """
    new_rdf_id = get_new_rdfid()
    rc = cgmes.RegulatingControl(rdfid=new_rdf_id)

    rc.name = f'_RC_{gen.name}'
    rc.RegulatingCondEq = gen
    # rc.mode: RegulatingControlModeKind
    # rc.Terminal
    # rc.discrete
    # rc.enabled
    # rc.targetDeadband
    # rc.targetValue = gen.Vset
    # rc.targetValueUnitMultiplier = 'k'

    cgmes_model.add(rc)

    return rc


# endregion

# region Convert functions from MC to CC


def get_cgmes_geograpical_regions(multi_circuit_model: MultiCircuit,
                                  cgmes_model: CgmesCircuit,
                                  logger: DataLogger):
    for mc_elm in multi_circuit_model.countries:
        geo_region = cgmes.GeographicalRegion(rdfid=form_rdfid(mc_elm.idtag))
        geo_region.name = mc_elm.name
        geo_region.description = mc_elm.code

        cgmes_model.add(geo_region)


def get_cgmes_subgeograpical_regions(multi_circuit_model: MultiCircuit,
                                     cgmes_model: CgmesCircuit,
                                     logger: DataLogger):
    for mc_elm in multi_circuit_model.communities:
        sub_geo_region = cgmes.SubGeographicalRegion(rdfid=form_rdfid(mc_elm.idtag))
        sub_geo_region.name = mc_elm.name
        sub_geo_region.description = mc_elm.code

        region = find_object_by_uuid(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.GeographicalRegion_list,
            target_uuid=mc_elm.idtag
        )
        if region is not None:
            sub_geo_region.Region = region

        cgmes_model.add(sub_geo_region)


def get_base_voltage_from_boundary(cgmes_model: CgmesCircuit, vnom: float):
    bv_list = cgmes_model.elements_by_type_boundary.get("BaseVoltage")
    if bv_list is not None:
        for bv in bv_list:
            if bv.nominalVoltage == vnom:
                return bv
    return None


def get_cgmes_base_voltages(multi_circuit_model: MultiCircuit,
                            cgmes_model: CgmesCircuit,
                            logger: DataLogger) -> None:
    base_volt_set = set()
    for bus in multi_circuit_model.buses:

        if bus.Vnom not in base_volt_set and get_base_voltage_from_boundary(cgmes_model, vnom=bus.Vnom) is None:
            base_volt_set.add(bus.Vnom)

            new_rdf_id = get_new_rdfid()
            base_volt = cgmes.BaseVoltage(rdfid=new_rdf_id)
            base_volt.name = f'_BV_{int(bus.Vnom)}'
            base_volt.nominalVoltage = bus.Vnom

            cgmes_model.add(base_volt)
    return


def get_cgmes_substations(multi_circuit_model: MultiCircuit,
                          cgmes_model: CgmesCircuit,
                          logger: DataLogger) -> None:
    for mc_elm in multi_circuit_model.substations:
        substation = cgmes.Substation(rdfid=form_rdfid(mc_elm.idtag))
        substation.name = mc_elm.name
        region = find_object_by_uuid(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.SubGeographicalRegion_list,
            target_uuid=mc_elm.community.idtag  # TODO Community.idtag!
        )
        if region is not None:
            substation.Region = region
        else:
            print(f'Region not found for Substation {substation.name}')
            logger.add_warning(msg='Region not found for Substation',
                               device_class=cgmes.SubGeographicalRegion)

        cgmes_model.add(substation)


def get_cgmes_voltage_levels(multi_circuit_model: MultiCircuit,
                             cgmes_model: CgmesCircuit,
                             logger: DataLogger) -> None:
    for mc_elm in multi_circuit_model.voltage_levels:

        vl = cgmes.VoltageLevel(rdfid=form_rdfid(mc_elm.idtag))
        vl.name = mc_elm.name
        vl.BaseVoltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=mc_elm.Vnom
        )
        # vl.Bays = later
        # vl.TopologicalNode added at tn_nodes func

        if mc_elm.substation is not None:
            substation: cgmes.Substation = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.Substation_list,
                target_uuid=mc_elm.substation.idtag
            )
            if substation:
                vl.Substation = substation

                # link back
                if substation.VoltageLevels is None:
                    substation.VoltageLevels = list()
                substation.VoltageLevels.append(vl)

        cgmes_model.add(vl)


def get_cgmes_tn_nodes(multi_circuit_model: MultiCircuit,
                       cgmes_model: CgmesCircuit,
                       logger: DataLogger) -> None:
    for bus in multi_circuit_model.buses:

        tn = cgmes.TopologicalNode(rdfid=bus.idtag)
        tn.name = bus.name
        tn.BaseVoltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=bus.Vnom
        )

        if bus.voltage_level is not None and cgmes_model.cgmes_assets.VoltageLevel_list:  # VoltageLevel
            vl: cgmes.VoltageLevel = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.VoltageLevel_list,
                target_uuid=bus.voltage_level.idtag
            )
            tn.ConnectivityNodeContainer = vl
            # link back
            vl.TopologicalNode = tn
        else:
            print(f'Bus.voltage_level.idtag is None for {bus.name}')
        # TODO bus should have association for VoltageLevel first
        # and the voltagelevel to the substation

        cgmes_model.add(tn)

    return


def get_cgmes_cn_nodes(multi_circuit_model: MultiCircuit,
                       cgmes_model: CgmesCircuit,
                       logger: DataLogger) -> None:
    for mc_elm in multi_circuit_model.connectivity_nodes:

        cn = cgmes.ConnectivityNode(rdfid=form_rdfid(mc_elm.idtag))
        cn.name = mc_elm.name
        if mc_elm.default_bus is not None:
            tn: cgmes.TopologicalNode = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.TopologicalNode_list,
                target_uuid=mc_elm.default_bus.idtag
            )
            if tn is not None:
                cn.TopologicalNode = tn
                cn.ConnectivityNodeContainer = tn.ConnectivityNodeContainer
                tn.ConnectivityNodes = cn  # link back
            else:
                logger.add_error(msg='No TopologinalNode found',
                                 device=cn.name,
                                 device_class=cn.tpe)
        else:
            logger.add_error(msg='Connectivity Node has no default bus',
                             device=mc_elm.name,
                             device_class=mc_elm.device_type)
            # print(f'Topological node not found for cn: {cn.name}')

        cgmes_model.add(cn)

    return


def get_cgmes_loads(multicircuit_model: MultiCircuit,
                    cgmes_model: CgmesCircuit,
                    logger: DataLogger):
    """
    Converts every Multi Circuit load into CGMES ConformLoad.

    :param multicircuit_model:
    :param cgmes_model:
    :param logger:
    :return:
    """

    for mc_elm in multicircuit_model.loads:
        cl = cgmes.ConformLoad(rdfid=form_rdfid(mc_elm.idtag))
        cl.Terminals = create_cgmes_terminal(mc_elm.bus, cgmes_model, logger)
        cl.name = mc_elm.name

        # vl = find_object_by_tn_uuid(
        #     object_list=cgmes_model.VoltageLevel_list,
        #     target_uuid=cl.Terminals.TopologicalNode.uuid
        # )
        # if isinstance(vl, cgmes.VoltageLevel):
        #     cl.EquipmentContainer = vl
        # else:
        #     print("hello")

        # cl.BaseVoltage = BaseVoltage
        cl.LoadResponse = create_cgmes_load_response_char(load=mc_elm, logger=logger)
        # cl.LoadGroup = ConformLoadGroup ..?
        cl.p = mc_elm.P / cl.LoadResponse.pConstantPower
        cl.q = mc_elm.Q / cl.LoadResponse.qConstantPower

        cl.description = mc_elm.code

        cgmes_model.add(cl)


def get_cgmes_equivalent_injections(multicircuit_model: MultiCircuit,
                                    cgmes_model: CgmesCircuit,
                                    logger: DataLogger):
    """
    Converts every Multi Circuit external grid
    into CGMES equivalent injection.

    :param multicircuit_model:
    :param cgmes_model:
    :param logger:
    :return:
    """

    for mc_elm in multicircuit_model.external_grids:
        ei = cgmes.EquivalentInjection(rdfid=form_rdfid(mc_elm.idtag))
        ei.description = mc_elm.code
        ei.name = mc_elm.name
        ei.p = mc_elm.P
        ei.q = mc_elm.Q
        ei.BaseVoltage = find_object_by_vnom(cgmes_model=cgmes_model,
                                             object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
                                             target_vnom=mc_elm.bus.Vnom)

        cgmes_model.add(ei)


def get_cgmes_ac_line_segments(multicircuit_model: MultiCircuit,
                               cgmes_model: CgmesCircuit,
                               logger: DataLogger):
    """
    Converts every Multi Circuit line
    into CGMES AC line segment.

    :param multicircuit_model:
    :param cgmes_model:
    :param logger:
    :return:
    """
    sbase = multicircuit_model.Sbase
    for mc_elm in multicircuit_model.lines:
        line = cgmes.ACLineSegment(rdfid=form_rdfid(mc_elm.idtag))
        line.description = mc_elm.code
        line.name = mc_elm.name
        line.BaseVoltage = find_object_by_vnom(cgmes_model=cgmes_model,
                                               object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
                                               target_vnom=mc_elm.get_max_bus_nominal_voltage()
                                               )  # which Vnom we need?
        vnom = line.BaseVoltage.nominalVoltage

        if vnom is not None:
            # Calculate Zbase
            zbase = (vnom * vnom) / sbase
            ybase = 1.0 / zbase

            line.r = mc_elm.R * zbase
            line.x = mc_elm.X * zbase
            # line.gch = mc_elm.G * Ybase
            line.bch = mc_elm.B * ybase
            line.r0 = mc_elm.R0 * zbase
            line.x0 = mc_elm.X0 * zbase
            # line.g0ch = mc_elm.G0 * Ybase
            line.b0ch = mc_elm.B0 * ybase

        cgmes_model.add(line)


def get_cgmes_operational_limits(multicircuit_model: MultiCircuit,
                                 cgmes_model: CgmesCircuit,
                                 logger: DataLogger):
    # OperationalLimitSet and OperationalLimitType

    pass


def get_cgmes_current_limits(multicircuit_model: MultiCircuit,
                             cgmes_model: CgmesCircuit,
                             logger: DataLogger):
    pass


def get_cgmes_generators(multicircuit_model: MultiCircuit,
                         cgmes_model: CgmesCircuit,
                         logger: DataLogger):
    """
    Converts Multi Circuit generators
    into approriate CGMES Generating Unit.

    :param multicircuit_model:
    :param cgmes_model:
    :param logger:
    :return:
    """

    for mc_elm in multicircuit_model.generators:
        # Generating Units
        cgmes_gen = create_cgmes_generating_unit(
            gen=mc_elm, cgmes_model=cgmes_model
        )
        cgmes_gen.name = mc_elm.name
        cgmes_gen.description = mc_elm.code
        # cgmes_gen.EquipmentContainer: cgmes.Substation
        cgmes_gen.initialP = mc_elm.P
        cgmes_gen.maxOperatingP = mc_elm.Pmax
        cgmes_gen.minOperatingP = mc_elm.Pmin
        cgmes_gen.normalPF = mc_elm.Pf  # power_factor

        # Synchronous Machine
        cgmes_syn = cgmes.SynchronousMachine(rdfid=form_rdfid(mc_elm.idtag))
        cgmes_syn.description = mc_elm.code
        cgmes_syn.name = mc_elm.name
        # cgmes_syn.aggregate is optional, not exported
        # cgmes_syn.EquipmentContainer: VoltageLevel
        # TODO implement control_node in MultiCircuit
        # has_control: do we have control
        # control_type: voltage or power control, ..
        # is_controlled: enabling flag (already have)
        if mc_elm.is_controlled:
            cgmes_syn.RegulatingControl = create_cgmes_regulating_control(cgmes_syn, cgmes_model)
            cgmes_syn.RegulatingControl.RegulatingCondEq = cgmes_syn

        # cgmes_syn.ratedPowerFactor =
        cgmes_syn.ratedS = mc_elm.Snom
        cgmes_syn.GeneratingUnit = cgmes_gen  # linking them together
        cgmes_gen.RotatingMachine = cgmes_syn  # linking them together
        cgmes_syn.maxQ = mc_elm.Qmax
        cgmes_syn.minQ = mc_elm.Qmin
        # ...
        cgmes_syn.referencePriority = '0'  # ?

        cgmes_model.add(cgmes_syn)


def get_cgmes_power_transformers(multicircuit_model: MultiCircuit,
                                 cgmes_model: CgmesCircuit,
                                 logger: DataLogger):
    for mc_elm in multicircuit_model.transformers2w:
        cm_transformer = cgmes.PowerTransformer(rdfid=form_rdfid(mc_elm.idtag))
        cm_transformer.uuid = mc_elm.idtag
        cm_transformer.description = mc_elm.code
        cm_transformer.name = mc_elm.name
        cm_transformer.Terminals = [create_cgmes_terminal(mc_elm.bus_from, cgmes_model, logger),
                                    create_cgmes_terminal(mc_elm.bus_to, cgmes_model, logger)]
        cm_transformer.aggregate = False  # what is this?
        # cm_transformer.EquipmentContainer: can be obtained only if the data is stored in MultiCircuit as well

        cm_transformer.PowerTransformerEnd = []
        pte1 = cgmes.PowerTransformerEnd()
        pte1.PowerTransformer = cm_transformer
        R, X, G, B, R0, X0, G0, B0 = (mc_elm.R, mc_elm.X, mc_elm.G, mc_elm.B, mc_elm.R0,
                                      mc_elm.X0, mc_elm.G0, mc_elm.B0)
        r, x, g, b, r0, x0, g0, b0 = get_ohm_values_power_transformer(R, X, G, B, R0, X0, G0, B0, mc_elm.Sn, mc_elm.HV)
        pte1.r = r
        pte1.x = x
        pte1.g = g
        pte1.b = b
        pte1.r0 = r0
        pte1.x0 = x0
        pte1.g0 = g0
        pte1.b0 = b0
        pte1.ratedU = mc_elm.HV
        pte1.ratedS = mc_elm.Sn
        pte1.endNumber = 1

        pte2 = cgmes.PowerTransformerEnd()
        pte2.PowerTransformer = cm_transformer
        pte2.r = 0
        pte2.x = 0
        pte2.g = 0
        pte2.b = 0
        pte2.r0 = 0
        pte2.x0 = 0
        pte2.g0 = 0
        pte2.b0 = 0
        pte2.ratedU = mc_elm.LV
        pte2.ratedS = mc_elm.Sn
        pte2.endNumber = 2

        cm_transformer.PowerTransformerEnd.append(pte1)
        cgmes_model.add(pte1)
        cm_transformer.PowerTransformerEnd.append(pte2)
        cgmes_model.add(pte2)

        cgmes_model.add(cm_transformer)

    for mc_elm in multicircuit_model.transformers3w:
        cm_transformer = cgmes.PowerTransformer(rdfid=form_rdfid(mc_elm.idtag))
        cm_transformer.uuid = mc_elm.idtag
        cm_transformer.description = mc_elm.code
        cm_transformer.name = mc_elm.name
        cm_transformer.Terminals = [create_cgmes_terminal(mc_elm.bus1, cgmes_model, logger),
                                    create_cgmes_terminal(mc_elm.bus2, cgmes_model, logger),
                                    create_cgmes_terminal(mc_elm.bus3, cgmes_model, logger)]
        cm_transformer.PowerTransformerEnd = []

        pte1 = cgmes.PowerTransformerEnd()
        pte1.PowerTransformer = cm_transformer
        pte1.ratedU = mc_elm.V1
        pte1.ratedS = mc_elm.rate12
        pte1.endNumber = 1
        R, X, G, B, R0, X0, G0, B0 = (
            mc_elm.winding1.R, mc_elm.winding1.X, mc_elm.winding1.G, mc_elm.winding1.B, mc_elm.winding1.R0,
            mc_elm.winding1.X0, mc_elm.winding1.G0, mc_elm.winding1.B0)
        r, x, g, b, r0, x0, g0, b0 = get_ohm_values_power_transformer(R, X, G, B, R0, X0, G0, B0, mc_elm.winding1.rate,
                                                                      mc_elm.winding1.HV)
        pte1.r = r
        pte1.x = x
        pte1.g = g
        pte1.b = b
        pte1.r0 = r0
        pte1.x0 = x0
        pte1.g0 = g0
        pte1.b0 = b0

        pte2 = cgmes.PowerTransformerEnd()
        pte2.PowerTransformer = cm_transformer
        pte2.ratedU = mc_elm.V2
        pte2.ratedS = mc_elm.rate23
        pte2.endNumber = 2
        R, X, G, B, R0, X0, G0, B0 = (
            mc_elm.winding2.R, mc_elm.winding2.X, mc_elm.winding2.G, mc_elm.winding2.B, mc_elm.winding2.R0,
            mc_elm.winding2.X0, mc_elm.winding2.G0, mc_elm.winding2.B0)
        r, x, g, b, r0, x0, g0, b0 = get_ohm_values_power_transformer(R, X, G, B, R0, X0, G0, B0, mc_elm.winding2.rate,
                                                                      mc_elm.winding2.HV)
        pte2.r = r
        pte2.x = x
        pte2.g = g
        pte2.b = b
        pte2.r0 = r0
        pte2.x0 = x0
        pte2.g0 = g0
        pte2.b0 = b0

        pte3 = cgmes.PowerTransformerEnd()
        pte3.PowerTransformer = cm_transformer
        pte3.ratedU = mc_elm.V3
        pte3.ratedS = mc_elm.rate31
        pte3.endNumber = 3
        R, X, G, B, R0, X0, G0, B0 = (
            mc_elm.winding3.R, mc_elm.winding3.X, mc_elm.winding3.G, mc_elm.winding3.B, mc_elm.winding3.R0,
            mc_elm.winding3.X0, mc_elm.winding3.G0, mc_elm.winding3.B0)
        r, x, g, b, r0, x0, g0, b0 = get_ohm_values_power_transformer(R, X, G, B, R0, X0, G0, B0, mc_elm.winding3.rate,
                                                                      mc_elm.winding3.HV)
        pte3.r = r
        pte3.x = x
        pte3.g = g
        pte3.b = b
        pte3.r0 = r0
        pte3.x0 = x0
        pte3.g0 = g0
        pte3.b0 = b0

        cm_transformer.PowerTransformerEnd.append(pte1)
        cgmes_model.add(pte1)
        cm_transformer.PowerTransformerEnd.append(pte2)
        cgmes_model.add(pte2)
        cm_transformer.PowerTransformerEnd.append(pte3)
        cgmes_model.add(pte3)

        cgmes_model.add(cm_transformer)


def get_cgmes_linear_shunts(multicircuit_model: MultiCircuit,
                            cgmes_model: CgmesCircuit,
                            logger: DataLogger):
    """
    Converts Multi Circuit shunts
    into CGMES Linear shunt compensator

    :param multicircuit_model:
    :param cgmes_model:
    :param logger:
    :return:
    """

    for mc_elm in multicircuit_model.shunts:
        lsc = cgmes.LinearShuntCompensator(rdfid=form_rdfid(mc_elm.idtag))
        lsc.name = mc_elm.name
        lsc.description = mc_elm.code
        # lsc.EquipmentContainer: VoltageLevel .. like at tn_nodes line 284
        lsc.RegulatingControl = False
        lsc.controlEnabled = False
        lsc.maximumSections = 1
        # lsc.nomU = lsc.EquipmentContainer.BaseVoltage.nominalVoltage
        # lsc.bPerSection = mc_elm.B / (lsc.nomU ** 2)
        # lsc.gPerSection = mc_elm.G / (lsc.nomU ** 2)
        # lsc.sections = ?
        # lsc.normalSections = ?

        lsc.Terminals = create_cgmes_terminal(mc_elm.bus, cgmes_model, logger)

        cgmes_model.add(lsc)


def get_cgmes_sv_voltages(cgmes_model: CgmesCircuit,
                          pf_results: PowerFlowResults,
                          logger: DataLogger):
    """
    Creates a CgmesCircuit SvVoltage_list.

    Args:
        cgmes_model: CgmesCircuit
        pf_results: PowerFlowResults
        logger (DataLogger): The data logger for error handling.

    Returns:
        CgmesCircuit: A CgmesCircuit object with SvVoltage_list populated.
    """
    print('hello')
    # for uuid, (v, angle) in v_dict.items():
    #     # Create an SvVoltage instance for each entry in v_dict
    #     sv_voltage = cgmes.SvVoltage(
    #         rdfid=uuid, tpe='SvVoltage'
    #     )
    #     sv_voltage.v = v
    #     sv_voltage.angle = angle
    #
    #     # Add the SvVoltage instance to the SvVoltage_list
    #     cgmes_model.add(sv_voltage)


# endregion


def gridcal_to_cgmes(gc_model: MultiCircuit,
                     cgmes_model: CgmesCircuit,
                     pf_results: Union[None, PowerFlowResults],
                     logger: DataLogger) -> CgmesCircuit:
    """
    Converts the input Multi circuit to a new CGMES Circuit.

    :param gc_model: Multi circuit object
    :param cgmes_model: CGMES circuit object
    :param pf_results: power flow results from GridCal
    :param logger: Logger object
    :return: CGMES circuit (as a new object)
    """

    get_cgmes_geograpical_regions(gc_model, cgmes_model, logger)
    get_cgmes_subgeograpical_regions(gc_model, cgmes_model, logger)

    get_cgmes_base_voltages(gc_model, cgmes_model, logger)  # TODO 46-45

    get_cgmes_substations(gc_model, cgmes_model, logger)
    get_cgmes_voltage_levels(gc_model, cgmes_model, logger)

    get_cgmes_tn_nodes(gc_model, cgmes_model, logger)
    get_cgmes_cn_nodes(gc_model, cgmes_model, logger)

    get_cgmes_loads(gc_model, cgmes_model, logger)
    get_cgmes_equivalent_injections(gc_model, cgmes_model, logger)
    get_cgmes_generators(gc_model, cgmes_model, logger)

    get_cgmes_ac_line_segments(gc_model, cgmes_model, logger)
    # transformers, windings
    get_cgmes_power_transformers(gc_model, cgmes_model, logger)

    # shunts
    get_cgmes_linear_shunts(gc_model, cgmes_model, logger)

    # results: sv classes
    if pf_results:
        get_cgmes_sv_voltages(cgmes_model, pf_results, logger)

    return cgmes_model
