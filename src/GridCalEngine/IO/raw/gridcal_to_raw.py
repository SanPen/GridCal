import numpy as np

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.raw.devices import RawArea, RawZone, RawBus, RawLoad, RawFixedShunt
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit
import GridCalEngine.Devices as dev


def get_area(area: dev.Area, i: int) -> RawArea:
    result = RawArea()
    result.ARNAME = area.name
    result.I = i
    return result


def get_zone(zone: dev.Zone, i: int) -> RawZone:
    result = RawZone()
    result.ZONAME = zone.name
    result.I = i
    return result


def get_psse_bus(bus: dev.Bus, area_dict, zones_dict) -> RawBus:
    psse_bus = RawBus()
    psse_bus.NAME = bus.name
    psse_bus.BASKV = bus.Vnom

    # TODO: Can it be modified on the UI?
    #  Does the "I" need to be generated as an automatically incrementing number?
    psse_bus.I = int(bus.code)

    psse_bus.EVLO = bus.Vmin
    psse_bus.EVHI = bus.Vmax

    psse_bus.AREA = area_dict[bus.area]
    psse_bus.ZONE = zones_dict[bus.zone]
    psse_bus.VM = bus.Vm0
    psse_bus.VA = np.rad2deg(bus.Va0)

    psse_bus.IDE = bus.type.value

    return psse_bus


def get_psse_load(load: dev.Load) -> RawLoad:
    psse_load = RawLoad()

    # TODO: Can it be modified on the UI?
    #  Does the "I" need to be generated as an automatically incrementing number?
    #  Then how should the ID be generated?
    i, id_ = load.name.split("_", 1)

    psse_load.I = i
    psse_load.ID = id_

    psse_load.YP = load.G
    psse_load.YQ = load.B
    psse_load.IP = load.Ir
    psse_load.IQ = load.Ii
    psse_load.PL = load.P
    psse_load.QL = load.Q
    psse_load.STATUS = 1 if load.active else 0

    return psse_load


def get_psse_fixed_shunt(shunt: dev.Shunt) -> RawFixedShunt:
    psse_shunt = RawFixedShunt()

    i, id_ = shunt.name.split("_", 1)

    # TODO: Can it be modified on the UI?
    #  Does the "I" need to be generated as an automatically incrementing number?
    #  Then how should the ID be generated?
    psse_shunt.I = i
    psse_shunt.ID = id_

    psse_shunt.GL = shunt.G
    psse_shunt.BL = shunt.B

    psse_shunt.STATUS = 1 if shunt.active else 0

    return psse_shunt


def gridcal_to_raw(grid: MultiCircuit) -> PsseCircuit:
    psse_circuit = PsseCircuit()

    area_dict = {area: get_area(area, index + 1) for index, area in enumerate(grid.areas)}
    zones_dict = {zone: get_zone(zone, index + 1) for index, zone in enumerate(grid.zones)}

    psse_circuit.areas = list(area_dict.values())
    psse_circuit.zones = list(zones_dict.values())

    psse_circuit.buses = [get_psse_bus(bus, area_dict, zones_dict) for bus in grid.buses]

    psse_circuit.loads = [get_psse_load(load) for load in grid.loads]

    psse_circuit.fixed_shunts = [get_psse_fixed_shunt(shunt) for shunt in grid.shunts]

    # TODO: convert switched shunts

    return psse_circuit
