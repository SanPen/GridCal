


from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit


def gridcal_to_raw(grid: MultiCircuit) -> PsseCircuit:

    psse_circuit = PsseCircuit()

    return psse_circuit