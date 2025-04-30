import numpy as np
import GridCalEngine.api as gce

grid = gce.MultiCircuit()
node = [
    4071, 4072, 4011, 4012, 4021, 4022, 4031, 4032, 1011, 1012,
    1013, 1014, 1021, 1022, 2031, 2032, 4041, 4042, 4043, 4044,
    4045, 4046, 4047, 4051, 1041, 1042, 1043, 1044, 1045, 41,
    42, 43, 46, 47, 51, 4061, 4062, 4063, 61, 62, 63
]
nominal_voltage_kv = [
    400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 130.0, 130.0,
    130.0, 130.0, 130.0, 130.0, 220.0, 220.0, 400.0, 400.0, 400.0, 400.0,
    400.0, 400.0, 400.0, 400.0, 130.0, 130.0, 130.0, 130.0, 130.0, 130.0,
    130.0, 130.0, 130.0, 130.0, 130.0, 400.0, 400.0, 400.0, 130.0, 130.0, 130.0
]

node_to_voltage = dict(zip(node, nominal_voltage_kv))

type = [
    "PV", "PV", "Slack", "PV", "PV", "PQ", "PV", "PQ", "PQ", "PV",
    "PV", "PV", "PV", "PV", "PQ", "PV", "PV", "PV", "PQ", "PQ",
    "PQ", "PQ", "PV", "PV", "PQ", "PV", "PV", "PQ", "PQ", "PQ",
    "PQ", "PQ", "PQ", "PQ", "PQ", "PQ", "PV", "PV", "PQ", "PQ", "PQ"
]
area = [
    "External", "External", "North", "North", "North", "North", "North", "North", "North", "North",
    "North", "North", "North", "North", "North", "North", "Central", "Central", "Central", "Central",
    "Central", "Central", "Central", "Central", "Central", "Central", "Central", "Central", "Central", "Central",
    "Central", "Central", "Central", "Central", "Central", "Southwest", "Southwest", "Southwest", "Southwest", "Southwest", "Southwest"
]
active_load_mw = [
    300, 2000, 0, 0, 0, 0, 0, 0, 200, 300,
    100, 0, 0, 280, 100, 200, 0, 0, 0, 0,
    0, 0, 0, 0, 600, 300, 230, 800, 700, 540,
    400, 900, 700, 100, 800, 0, 0, 0, 500, 300, 590
]
reactive_load_mvar = [
    100.0, 500.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 80.0, 100.0,
    40.0, 0.0, 0.0, 95.0, 30.0, 50.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 200.0, 80.0, 100.0, 300.0, 250.0, 128.3,
    125.7, 238.8, 193.7, 45.2, 253.2, 0.0, 0.0, 0.0, 112.3, 80.0, 256.2
]
shunt_reactive_comp_mvar = [
    -400, 0, 0, -100, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 50, 0, 0, 200, 0, 200, 0,
    0, 100, 0, 100, 200, 0, 150, 200, 200, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
]
for i in range(len(node)):
    bus = gce.Bus(name=node[i], Vnom=nominal_voltage_kv[i], area=area[i])
    if type[i] == "Slack":
        bus.is_slack = True

    load = gce.Load(name=node[i], P=active_load_mw[i], Q=reactive_load_mvar[i])

    shunt = gce.Shunt(name=node[i], B=shunt_reactive_comp_mvar[i])

    grid.add_bus(obj=bus)
    grid.add_load(bus=bus, api_obj=load)
    grid.add_shunt(bus=bus, api_obj=shunt)

# Lines
From = [
    1011, 1011, 1012, 1012, 1013, 1013, 1021, 1021, 1041, 1041,
    1041, 1041, 1042, 1042, 1042, 1043, 1043, 2031, 2031, 4011,
    4011, 4011, 4011, 4012, 4012, 4021, 4021, 4022, 4022, 4031,
    4031, 4031, 4032, 4032, 4041, 4041, 4042, 4042, 4043, 4043,
    4043, 4044, 4044, 4045, 4045, 4045, 4046, 4062, 4062, 4071, 4071
]
To = [
    1013, 1013, 1014, 1014, 1014, 1014, 1022, 1022, 1043, 1043,
    1045, 1045, 1044, 1044, 1045, 1044, 1044, 2032, 2032, 4012,
    4021, 4022, 4071, 4022, 4071, 4032, 4042, 4031, 4031, 4032,
    4041, 4041, 4042, 4044, 4044, 4061, 4043, 4044, 4044, 4046,
    4047, 4045, 4045, 4051, 4051, 4062, 4047, 4063, 4063, 4072, 4072
]
Resistance_Ohms = [
    1.69, 1.69, 2.37, 2.37, 1.18, 1.18, 5.07, 5.07, 1.69, 1.69,
    2.53, 2.53, 6.42, 6.42, 8.45, 1.69, 1.69, 5.81, 5.81, 1.6,
    9.6, 6.4, 8.0, 6.4, 8.0, 6.4, 16.0, 6.4, 6.4, 1.6,
    9.6, 9.6, 16.0, 9.6, 4.8, 9.6, 3.2, 3.2, 1.6, 1.6,
    3.2, 3.2, 3.2, 6.4, 6.4, 17.6, 1.6, 4.8, 4.8, 4.8, 4.8
]
Inductance_mH = [
    11.83, 11.83, 15.21, 15.21, 8.45, 8.45, 33.80, 33.80, 10.14, 10.14,
    20.28, 20.28, 47.32, 47.32, 50.70, 13.52, 13.52, 43.56, 43.56, 12.8,
    96.0, 64.0, 72.0, 56.0, 80.0, 64.0, 96.0, 64.0, 64.0, 16.0,
    64.0, 64.0, 64.0, 80.0, 48.0, 72.0, 24.0, 32.0, 16.0, 16.0,
    32.0, 32.0, 32.0, 64.0, 64.0, 128.0, 24.0, 48.0, 48.0, 48.0, 48.0
]
Capacitance_uF = [
    0.26, 0.26, 0.34, 0.34, 0.19, 0.19, 0.57, 0.57, 0.23, 0.23,
    0.47, 0.47, 1.13, 1.13, 1.13, 0.3, 0.3, 0.1, 0.1, 0.4,
    3.58, 2.39, 2.79, 2.09, 2.98, 2.39, 5.97, 2.39, 2.39, 0.6,
    4.77, 4.77, 3.98, 4.77, 1.79, 2.59, 0.99, 1.19, 0.6, 0.6,
    1.19, 1.19, 1.19, 2.39, 2.39, 4.77, 0.99, 1.79, 1.79, 5.97, 5.97
]

for i in range(len(From)):
    Ubase = node_to_voltage[From[i]]
    Sbase = grid.Sbase
    Zbase = Ubase**2 / Sbase
    Ybase = 1/Zbase

    line = gce.Line(bus_from=next(bus for bus in grid.buses if bus.name == From[i]),
                    bus_to=next(bus for bus in grid.buses if bus.name == To[i]),
                    r=Resistance_Ohms[i] / Zbase,
                    x=Inductance_mH[i] * 2 * np.pi * 50 / Zbase * 1e-3,
                    b=Capacitance_uF[i] * 2 * np.pi * 50 / Ybase * 1e-6
                    )

    grid.add_line(obj=line)

# Transformers
HV_Busbar = [
    4011, 4012, 4022, 4031, 4044, 4044, 4045, 4045,
    4041, 4042, 4043, 4046, 4047, 4051, 4061, 4062, 4063
]
LV_Busbar = [
    1011, 1012, 1022, 2031, 1044, 1044, 1045, 1045,
    41, 42, 43, 46, 47, 51, 61, 62, 63
]
Rating_MVA_Traf = [
    1250.0, 1250.0, 835.0, 835.0, 1000.0, 1000.0, 1000.0, 1000.0,
    1000.0, 750.0, 1500.0, 1000.0, 250.0, 1500.0, 750.0, 500.0, 1000.0
]
HV_kV = [
    400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 400.0,
    400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 400.0, 400.0
]
LV_kV = [
    130.0, 130.0, 130.0, 220.0, 130.0, 130.0, 130.0, 130.0,
    130.0, 130.0, 130.0, 130.0, 130.0, 130.0, 130.0, 130.0, 130.0
]
EX12_pu = [
    0.1, 0.1, 0.1002, 0.1002, 0.1, 0.1, 0.1, 0.1,
    0.1, 0.0975, 0.105, 0.1, 0.1, 0.105, 0.0975, 0.1, 0.1
]
turn_ratio = [
    1.12, 1.12, 1.07, 1.05, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1
]

for i in range(len(HV_Busbar)):
    trafo = gce.Transformer2W(bus_from=next(bus for bus in grid.buses if bus.name == HV_Busbar[i]),
                              bus_to=next(bus for bus in grid.buses if bus.name == LV_Busbar[i]),
                              nominal_power=Rating_MVA_Traf[i],
                              HV=HV_kV[i],
                              LV=LV_kV[i],
                              x=EX12_pu[i],
                              tap_module = turn_ratio[i])

    grid.add_transformer2w(trafo)

# Generators
names = [
    "411G1", "412G1", "421G1", "431G1", "441G1", "442G1", "447G1", "447G2",
    "451G1", "451G2", "462G1", "463G1", "463G2", "471G1", "472G1", "112G1",
    "113G1", "114G1", "121G1", "122G1", "232G1", "142G1", "143G1"
]
busbars = [
    4011, 4012, 4021, 4031, 4041, 4042, 4047, 4047,
    4051, 4051, 4062, 4063, 4063, 4071, 4072, 1012,
    1013, 1014, 1021, 1022, 2032, 1042, 1043
]
ratings = [
    1000, 800, 300, 350, 300, 700, 600, 600,
    700, 700, 700, 600, 600, 500, 4500, 800,
    600, 700, 600, 250, 850, 400, 200
]
states = [
    True, True, True, True, True, True, True, True,
    True, False, True, True, True, True, True, True,
    True, True, True, True, True, True, True
]
active_productions = [
    0, 600, 250, 310, 0, 630, 540, 540,
    600, 0, 530, 530, 530, 300, 2000, 600,
    300, 550, 400, 200, 750, 360, 180
]
voltage_setpoints = [
    404, 404, 400, 404, 400, 400, 408, 408,
    408, 400, 400, 400, 400, 404, 404, 146.9,
    148.85, 150.8, 143, 139.1, 242, 130, 130
]
qmax = [
    700, 400, 150, 175, 300, 350, 300, 300,
    350, 700, 300, 300, 300, 250, 1000, 400,
    300, 350, 300, 125, 425, 200, 100
]
qmin = [
    -700, -160, -30, -40, -200, 0, 0, 0,
    0, -700, 0, 0, 0, -50, -300, -80,
    -50, -100, -60, -25, -80, -40, -20
]
for i in range(len(states)):
    gen = gce.Generator(name = names[i],
                        P = active_productions[i],
                        vset = voltage_setpoints[i] / node_to_voltage[busbars[i]],
                        Qmin = qmin[i],
                        Qmax = qmax[i],
                        Snom = ratings[i],
                        active = states[i]
                        )
    grid.add_generator(bus = next(bus for bus in grid.buses if bus.name == busbars[i]), api_obj = gen)

# Save
gce.save_file(grid, "Nordic_Grid.gridcal")