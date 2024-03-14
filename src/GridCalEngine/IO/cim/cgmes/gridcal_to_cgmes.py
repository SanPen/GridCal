from GridCalEngine.Devices import MultiCircuit
from GridCalEngine.IO.cim.cgmes.base import get_new_rfid, get_uuid
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.connectivity_node import ConnectivityNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.sv_voltage import SvVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_consumer import EnergyConsumer
from GridCalEngine.data_logger import DataLogger
from typing import Dict, List, Tuple


def find_terms_connections():
    pass # TODO


def get_cgmes_base_voltages(multi_circuit_model: MultiCircuit,
                            cgmes_model: CgmesCircuit,
                            logger: DataLogger):
    base_volt_set = set()
    for bus in multi_circuit_model.buses:

        if bus.Vnom not in base_volt_set:
            base_volt_set.add(bus.Vnom)

            new_rdfid = get_new_rfid()
            base_volt = BaseVoltage(rdfid=new_rdfid)
            base_volt.name = f'_BV_{int(bus.Vnom)}'

            cgmes_model.BaseVoltage_list.append(base_volt)
    return


def get_cgmes_cn_tn_nodes(multi_circuit_model: MultiCircuit,
                          cgmes_model: CgmesCircuit,
                          logger: DataLogger):

    for bus in multi_circuit_model.buses:
        # Topological Node
        new_rdfid = get_new_rfid()
        tn = TopologicalNode(new_rdfid)
        tn.name = bus.name
        # tn.BaseVoltage = BaseVoltage
        # tn.ConnectivityNodeContainer = VoltageLevel

        cn = ConnectivityNode(rdfid=get_uuid(bus.idtag))
        cn.TopologicalNode = tn
        # cn.ConnectivityNodeContainer = VoltageLevel

        cgmes_model.ConnectivityNode_list.append(cn)
        cgmes_model.TopologicalNode_list.append(tn)



    return


def get_svvoltages(v_dict: Dict[str, Tuple[float, float]],
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
    # should it come from the results?
    for uuid, (v, angle) in v_dict.items():
        # Create an SvVoltage instance for each entry in v_dict
        sv_voltage = SvVoltage(
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

    cgmes_model.EnergyConsumer_list = []
    # TODO find connections
    find_terms_connections()
    for load in multicircuit_model.loads:
        # TODO How do we determine what the MultiCircuit Load corresponds to in the Cgmes object? Is it EnergyConsumer, ConformLoad, NonConformLoad
        # all can be ConformLoad! and LoadResponseChar
        ec = EnergyConsumer()
        ec.uuid = load.idtag
        ec.description = load.code
        ec.name = load.name
        ec.p = load.P
        ec.q = load.Q
        cgmes_model.EnergyConsumer_list.append(ec)
        # load.bus contains the Terminal connections


def process_mc_buses(multicircuit_model: MultiCircuit,
                    cgmes_model: CgmesCircuit,
                    logger: DataLogger):
    pass


def gridcal_to_cgmes(gc_model: MultiCircuit, logger: DataLogger) -> CgmesCircuit:
    """
    Converts the input Multi circuit to a new CGMES Circuit.

    :param gc_model: Multi circuit object
    :param logger: Logger object
    :return: CGMES circuit (as a new object)
    """

    cgmes_circuit = CgmesCircuit()

    get_cgmes_base_voltages(gc_model, cgmes_circuit, logger)

    get_cgmes_cn_tn_nodes(gc_model, cgmes_circuit, logger)

    #TODO How to determine the device_to_terminal_dict, calc_node_dict, and cn_dict dictionaries?
    # What are the appropriate data types in MultiCircuit that provide the connectivity?

    #TODO Determine multicircuit terminals here to be able to define connections
    #get_cgmes_loads(cgmes_model=cgmes_circuit, multicircuit_model=gc_model, logger=logger) # Fill up loads in cgmes_object

    return cgmes_circuit
