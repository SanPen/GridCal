import numpy as np
from itertools import groupby

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.raw.devices import RawArea, RawZone, RawBus, RawLoad, RawFixedShunt, RawGenerator, \
    RawSwitchedShunt, RawTransformer
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


def get_psse_switched_shunt(shunt: dev.ControllableShunt) -> RawSwitchedShunt:
    psse_switched_shunt = RawSwitchedShunt()
    # TODO: Does the "I" need to be generated as an automatically incrementing number?
    psse_switched_shunt.I = int(shunt.name.replace("Switched shunt ", ""))
    psse_switched_shunt.STATUS = 1 if shunt.active else 0

    if len(shunt.g_steps) > 0:
        diff_list = np.insert(np.diff(shunt.g_steps), 0, shunt.g_steps[0])
        aggregated_steps = [(sum(1 for _ in group), key) for key, group in groupby(diff_list)]

        for index, aggregated_step in enumerate(aggregated_steps):
            setattr(psse_switched_shunt, f'S{index + 1}', 1)
            setattr(psse_switched_shunt, f'N{index + 1}', aggregated_step[0])
            setattr(psse_switched_shunt, f'B{index + 1}', aggregated_step[1])

    return psse_switched_shunt


def get_psse_generator(generator: dev.Generator) -> RawGenerator:
    psse_generator = RawGenerator()

    i, id_ = generator.name.split("_", 1)

    # TODO: Can it be modified on the UI?
    #  Does the "I" need to be generated as an automatically incrementing number?
    #  Then how should the ID be generated?
    psse_generator.I = i
    psse_generator.ID = id_

    psse_generator.PG = generator.P
    psse_generator.VS = generator.Vset
    psse_generator.QB = generator.Qmin
    psse_generator.QT = generator.Qmax
    psse_generator.MBASE = generator.Snom
    psse_generator.PT = generator.Pmax
    psse_generator.PB = generator.Pmin
    psse_generator.STAT = 1 if generator.active else 0

    return psse_generator


def get_psse_transformer2w(transformer: dev.Transformer2W) -> RawTransformer:
    psse_transformer = RawTransformer()
    psse_transformer.windings = 2

    psse_transformer.idtag = transformer.idtag
    psse_transformer.STAT = 1 if transformer.active else 0

    psse_transformer.SBASE1_2 = transformer.Sn
    psse_transformer.RATE1_1 = transformer.rate

    i, j, ckt = transformer.code.split("_")

    psse_transformer.I = i
    psse_transformer.J = j
    psse_transformer.CKT = ckt

    return psse_transformer


def get_psse_transformer3w(transformer: dev.Transformer3W) -> RawTransformer:
    psse_transformer = RawTransformer()
    psse_transformer.windings = 3

    psse_transformer.idtag = transformer.idtag
    psse_transformer.STAT = 1 if transformer.active else 0

    psse_transformer.NAME = transformer.name
    psse_transformer.RATE1_1 = transformer.rate12
    psse_transformer.RATE2_1 = transformer.rate23
    psse_transformer.RAte3_1 = transformer.rate31

    psse_transformer.ANG1 = transformer.winding1.tap_phase
    psse_transformer.ANG2 = transformer.winding2.tap_phase
    psse_transformer.ANG3 = transformer.winding3.tap_phase

    i, j, k, ckt = psse_transformer.code.split("_")

    psse_transformer.I = i
    psse_transformer.J = j
    psse_transformer.K = k
    psse_transformer.CKT = ckt

    return psse_transformer


def gridcal_to_raw(grid: MultiCircuit) -> PsseCircuit:
    psse_circuit = PsseCircuit()

    area_dict = {area: get_area(area, index + 1) for index, area in enumerate(grid.areas)}
    zones_dict = {zone: get_zone(zone, index + 1) for index, zone in enumerate(grid.zones)}

    psse_circuit.areas = list(area_dict.values())
    psse_circuit.zones = list(zones_dict.values())

    psse_circuit.buses = [get_psse_bus(bus, area_dict, zones_dict) for bus in grid.buses]

    psse_circuit.loads = [get_psse_load(load) for load in grid.loads]

    psse_circuit.fixed_shunts = [get_psse_fixed_shunt(shunt) for shunt in grid.shunts]

    psse_circuit.switched_shunts = [get_psse_switched_shunt(controllable_shunt) for controllable_shunt in
                                    grid.controllable_shunts]

    psse_circuit.generators = [get_psse_generator(generator) for generator in grid.generators]

    psse_circuit.transformers = [get_psse_transformer2w(transformer) for transformer in grid.transformers2w]
    psse_circuit.transformers.extend(get_psse_transformer3w(transformer) for transformer in grid.transformers3w)

    return psse_circuit
