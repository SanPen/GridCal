import numpy as np
from itertools import groupby

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.raw.devices import RawArea, RawZone, RawBus, RawLoad, RawFixedShunt, RawGenerator, \
    RawSwitchedShunt, RawTransformer, RawBranch, RawVscDCLine, RawTwoTerminalDCLine, RawFACTS
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

    i, j, ckt = transformer.code.split("_", 2)

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

    i, j, k, ckt = psse_transformer.code.split("_", 3)

    psse_transformer.I = i
    psse_transformer.J = j
    psse_transformer.K = k
    psse_transformer.CKT = ckt

    return psse_transformer


def get_psse_branch(line: dev.Line) -> RawBranch:
    psse_branch = RawBranch()

    i, j, ckt = line.code.split("_", 2)

    psse_branch.I = i
    psse_branch.J = j
    psse_branch.CKT = ckt
    psse_branch.NAME = line.name
    psse_branch.R = line.R
    psse_branch.X = line.X
    psse_branch.B = line.B
    psse_branch.ST = 1 if line.active else 0
    psse_branch.idtag = line.idtag
    psse_branch.LEN = line.length

    return psse_branch


def get_vsc_dc_line(hvdc_line: dev.HvdcLine) -> RawVscDCLine:
    psse_vsc_dc_line = RawVscDCLine()
    psse_vsc_dc_line.NAME = hvdc_line.name
    psse_vsc_dc_line.ACSET1 = hvdc_line.Vset_f
    psse_vsc_dc_line.ACSET2 = hvdc_line.Vset_t

    return psse_vsc_dc_line


def get_psse_two_terminal_dc_line(hvdc_line: dev.HvdcLine) -> RawTwoTerminalDCLine:
    psse_two_terminal_dc_line = RawTwoTerminalDCLine()
    psse_two_terminal_dc_line.NAME = hvdc_line.name

    id_tag = hvdc_line.idtag[:-2] if hvdc_line.idtag.endswith("_1") else hvdc_line.idtag
    ipr, ipi = id_tag.split("_", 2)

    psse_two_terminal_dc_line.IPR = int(ipr)
    psse_two_terminal_dc_line.IPI = int(ipi)

    psse_two_terminal_dc_line.RDC = hvdc_line.r
    psse_two_terminal_dc_line.ANMNR = np.rad2deg(hvdc_line.min_firing_angle_f)
    psse_two_terminal_dc_line.ANMXR = np.rad2deg(hvdc_line.max_firing_angle_f)
    psse_two_terminal_dc_line.ANMNI = np.rad2deg(hvdc_line.min_firing_angle_t)
    psse_two_terminal_dc_line.ANMXI = np.rad2deg(hvdc_line.max_firing_angle_t)

    return psse_two_terminal_dc_line


def get_psse_facts(upfc: dev.UPFC) -> RawFACTS:
    psse_facts = RawFACTS()
    psse_facts.NAME = upfc.name

    id_tag = upfc.idtag[:-2] if upfc.idtag.endswith("_1") else upfc.idtag
    i, j = id_tag.split("_", 2)

    psse_facts.I = int(i)
    psse_facts.J = int(j)
    psse_facts.SET1 = upfc.Rs
    psse_facts.SHMX = 1 / upfc.Xsh if upfc.Xsh > 0 else 0.0
    psse_facts.VSET = upfc.Vsh
    psse_facts.PDES = upfc.Pfset
    psse_facts.QDES = upfc.Qfset
    psse_facts.IMX = upfc.rate - 1e-20

    return psse_facts


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

    # TODO: Decide whether to convert Transformer2W into branches or a transformer.
    psse_circuit.transformers = [get_psse_transformer2w(transformer) for transformer in grid.transformers2w]
    psse_circuit.transformers.extend(get_psse_transformer3w(transformer) for transformer in grid.transformers3w)

    psse_circuit.branches = [get_psse_branch(line) for line in grid.lines]

    # TODO: Decide whether to convert hvdc_lines into vsc_dc_lines or two_terminal_dc_lines.
    # psse_circuit.vsc_dc_lines = [get_vsc_dc_line(hvdc_line) for hvdc_line in grid.hvdc_lines]
    psse_circuit.two_terminal_dc_lines = [get_psse_two_terminal_dc_line(hvdc_line) for hvdc_line in grid.hvdc_lines]

    psse_circuit.facts = [get_psse_facts(upfc_device) for upfc_device in grid.upfc_devices]

    return psse_circuit
