from GridCalEngine.Devices import MultiCircuit
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.IO.cim.cgmes.base import get_new_rdfid, form_rdfid
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
import GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices as cgmes
import GridCalEngine.Devices as gcdev

# if cgmes_version == '2.4.15.':
#     from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import \
#         Terminal

from GridCalEngine.data_logger import DataLogger
from typing import Dict, List, Tuple


# region UTILS
# def find_terms_connections():
#     pass   # TODO


def find_object_by_uuid(object_list, target_uuid):  #TODO move to CGMES utils
    """
    Finds an object with the specified uuid
     in the given object_list from a CGMES Circuit.

    Args:
        object_list (list[MyObject]): List of MyObject instances.
        target_uuid (str): The uuid to search for.

    Returns:
        MyObject or None: The found object or None if not found.
    """
    for obj in object_list:
        if obj.uuid == target_uuid:
            return obj
    return None


def find_object_by_vnom(object_list: List[cgmes.BaseVoltage], target_vnom):
    for obj in object_list:
        if obj.nominalVoltage == target_vnom:
            return obj
    return None

# endregion

# region create new classes for CC


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
        object_list=cgmes_model.TopologicalNode_list,
        target_uuid=bus.idtag
    )
    if isinstance(tn, cgmes.TopologicalNode):
        term.TopologicalNode = tn
    else:
        logger.add_error(msg='No found TopologinalNode',
                         device=bus,
                         device_class=bus.name)

    cgmes_model.Terminal_list.append(term)

    return term


def create_cgmes_load_response_char(load: gcdev.Load) \
        -> cgmes.LoadResponseCharacteristic:

    new_rdf_id = get_new_rdfid()
    lrc = cgmes.LoadResponseCharacteristic(rdfid=new_rdf_id)
    # lrc.name =
    lrc.pConstantPower = 1
    lrc.qConstantPower = 1
    lrc.pConstantCurrent = load.Ir / load.P
    lrc.qConstantCurrent = load.Ii / load.Q
    lrc.pConstantImpedance = load.G / load.P
    lrc.qConstantImpedance = load.B / load.Q

    return lrc


def create_cgmes_regulating_control():
    pass

# endregion

# region Convert functions from MC to CC


def get_cgmes_geograpical_regions(multi_circuit_model: MultiCircuit,
                                  cgmes_model: CgmesCircuit,
                                  logger: DataLogger):
    pass


def get_cgmes_subgeograpical_regions(multi_circuit_model: MultiCircuit,
                                     cgmes_model: CgmesCircuit,
                                     logger: DataLogger):
    pass


def get_cgmes_base_voltages(multi_circuit_model: MultiCircuit,
                            cgmes_model: CgmesCircuit,
                            logger: DataLogger) -> None:
    base_volt_set = set()
    for bus in multi_circuit_model.buses:

        if bus.Vnom not in base_volt_set:
            base_volt_set.add(bus.Vnom)

            new_rdfid = get_new_rdfid()
            base_volt = cgmes.BaseVoltage(rdfid=new_rdfid)
            base_volt.name = f'_BV_{int(bus.Vnom)}'
            base_volt.nominalVoltage = bus.Vnom

            cgmes_model.BaseVoltage_list.append(base_volt)
    return


def get_cgmes_substations(multi_circuit_model: MultiCircuit,
                          cgmes_model: CgmesCircuit,
                          logger: DataLogger) -> None:

    for mc_elm in multi_circuit_model.substations:

        substation = cgmes.Substation(rdfid=form_rdfid(mc_elm.idtag))
        substation.name = mc_elm.name
        substation.Region = find_object_by_uuid(
            object_list=cgmes_model.SubGeographicalRegion_list,
            target_uuid=mc_elm.idtag  #TODO Community.idtag!
        )

        cgmes_model.Substation_list.append(substation)


def get_cgmes_voltage_levels(multi_circuit_model: MultiCircuit,
                             cgmes_model: CgmesCircuit,
                             logger: DataLogger) -> None:

    for mc_elm in multi_circuit_model.voltage_levels:

        vl = cgmes.VoltageLevel(rdfid=form_rdfid(mc_elm.idtag))
        vl.name = mc_elm.name
        vl.BaseVoltage = find_object_by_vnom(
            object_list=cgmes_model.BaseVoltage_list,
            target_vnom=mc_elm.Vnom
        )
        # vl.Bays = later

        if mc_elm.substation is not None:
            substation: cgmes.Substation = find_object_by_uuid(
                object_list=cgmes_model.Substation_list,
                target_uuid=mc_elm.substation.idtag
            )
            if substation:
                vl.Substation = substation

                # link back
                if substation.VoltageLevels is None:
                    substation.VoltageLevels = set()
                substation.VoltageLevels.add(vl)

        cgmes_model.VoltageLevel_list.append(vl)


def get_cgmes_cn_tn_nodes(multi_circuit_model: MultiCircuit,
                          cgmes_model: CgmesCircuit,
                          logger: DataLogger) -> None:

    for bus in multi_circuit_model.buses:

        new_rdf_id = get_new_rdfid()
        tn = cgmes.TopologicalNode(rdfid=new_rdf_id)
        tn.name = bus.name
        tn.BaseVoltage = find_object_by_vnom(
            object_list=cgmes_model.BaseVoltage_list,
            target_vnom=bus.Vnom
        )
        # tn.ConnectivityNodeContainer = VoltageLevel
        #TODO bus should have association for VoltageLevel first
        # and the voltagelevel to the substation

        cn = cgmes.ConnectivityNode(rdfid=form_rdfid(bus.idtag))
        cn.name = bus.name
        cn.TopologicalNode = tn
        # cn.ConnectivityNodeContainer = VoltageLevel same as for tn

        cgmes_model.ConnectivityNode_list.append(cn)
        cgmes_model.TopologicalNode_list.append(tn)

    return


def get_cgmes_svvoltages(v_dict: Dict[str, Tuple[float, float]],
                         cgmes_model: CgmesCircuit,
                         logger: DataLogger) -> CgmesCircuit:
    """
    Creates a CgmesCircuit SvVoltage_list.

    Args:
        v_dict (Dict[str, Tuple[float, float]]): The voltage dictionary.
        logger (DataLogger): The data logger for error handling.

    Returns:
        CgmesCircuit: A CgmesCircuit object with SvVoltage_list populated.
    """
    #TODO should it come from the results?
    for uuid, (v, angle) in v_dict.items():
        # Create an SvVoltage instance for each entry in v_dict
        sv_voltage = cgmes.SvVoltage(
            rdfid=uuid, tpe='SvVoltage'
        )
        sv_voltage.v = v
        sv_voltage.angle = angle

        # Add the SvVoltage instance to the SvVoltage_list
        cgmes_model.SvVoltage_list.append(sv_voltage)

    return cgmes_model


def get_cgmes_loads(multicircuit_model: MultiCircuit,
                    cgmes_model: CgmesCircuit,
                    logger: DataLogger):

    for mc_elm in multicircuit_model.loads:

        cl = cgmes.ConformLoad(rdfid=form_rdfid(mc_elm.idtag))
        cl.Terminals = create_cgmes_terminal(mc_elm.bus, cgmes_model, logger)
        cl.name = mc_elm.name
        # cl.EquipmentContainer =
        # cl.BaseVoltage =
        cl.LoadResponse = create_cgmes_load_response_char(load=mc_elm)
        # cl.LoadGroup =
        cl.p = mc_elm.P     # LoadResponse
        cl.q = mc_elm.Q

        cl.description = mc_elm.code

        cgmes_model.ConformLoad_list.append(cl)

# endregion


def gridcal_to_cgmes(gc_model: MultiCircuit, logger: DataLogger) -> CgmesCircuit:
    """
    Converts the input Multi circuit to a new CGMES Circuit.

    :param gc_model: Multi circuit object
    :param logger: Logger object
    :return: CGMES circuit (as a new object)
    """

    cgmes_model = CgmesCircuit(cgmes_version='2.4.15.')   # get from GUI
    
    get_cgmes_geograpical_regions(gc_model, cgmes_model, logger)
    get_cgmes_subgeograpical_regions(gc_model, cgmes_model, logger)
    
    get_cgmes_base_voltages(gc_model, cgmes_model, logger)

    get_cgmes_substations(gc_model, cgmes_model, logger)
    get_cgmes_voltage_levels(gc_model, cgmes_model, logger)

    get_cgmes_cn_tn_nodes(gc_model, cgmes_model, logger)

    get_cgmes_loads(gc_model, cgmes_model, logger)

    return cgmes_model
