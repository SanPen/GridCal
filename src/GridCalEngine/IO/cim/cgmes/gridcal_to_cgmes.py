from GridCalEngine.Devices import MultiCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.energy_consumer import EnergyConsumer
from GridCalEngine.data_logger import DataLogger


def find_terms_connections():
    pass # TODO 


def get_cgmes_loads(cgmes_model: CgmesCircuit,
                    multicircuit_model: MultiCircuit,
                    logger: DataLogger):
    cgmes_model.EnergyConsumer_list = []
    # TODO find connections
    find_terms_connections()
    for load in multicircuit_model.loads:
        ec = EnergyConsumer()   #TODO How do we determine what the MultiCircuit Load corresponds to in the Cgmes object? Is it EnergyConsumer, ConformLoad, NonConformLoad
        ec.uuid = load.idtag
        ec.description = load.code
        ec.name = load.name
        ec.p = load.P
        ec.q = load.Q
        cgmes_model.EnergyConsumer_list.append(ec)
        # load.bus contains the Terminal connections

def gridcal_to_cgmes(gc_model: MultiCircuit, logger: DataLogger) -> CgmesCircuit:
    cgmes_circuit = CgmesCircuit()  # TODO: Define which object to fill up with data. This may become a function parameter later.

    #TODO How to determine the device_to_terminal_dict, calc_node_dict, and cn_dict dictionaries? What are the appropriate data types in MultiCircuit that provide the connectivity?

    #TODO Determine multicircuit terminals here to be able to define connections
    get_cgmes_loads(cgmes_model=cgmes_circuit, multicircuit_model=gc_model, logger=logger) # Fill up loads in cgmes_object

    return cgmes_circuit
