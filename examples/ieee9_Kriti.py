import VeraGridEngine.api as gce

# User input - Weights for the two components of the Objective Function
wloss = 0.8
wred = 0.2

### ---------- Create IEEE 9 bus system
grid = gce.MultiCircuit()
# grid.Sbase = 100

# AC Bus 1 with a generator
acbus1 = gce.Bus('ACBus_1', Vnom=345, is_slack=True, is_dc=False)
grid.add_bus(acbus1)
gen1 = gce.Generator('Gen1',P=72.3, vset=1.04, Pmin=10, Pmax=250, Qmin=-300, Qmax=300, Cost0=150, Cost=5, Cost2=0.11,enabled_dispatch=True)
grid.add_generator(acbus1, gen1)

# AC Bus 2 with a generator
acbus2 = gce.Bus('ACBus_2', Vnom=345, is_slack=False, is_dc=False)
grid.add_bus(acbus2)
gen2 = gce.Generator('Gen2', P=163, vset=1.025, Pmin=10, Pmax=300, Qmin=-300, Qmax=300, Cost0=600, Cost=1.2, Cost2=0.085,enabled_dispatch=True)
grid.add_generator(acbus2, gen2)

# AC Bus 3 with a generator
acbus3 = gce.Bus('ACBus_3', Vnom=345, is_slack=False, is_dc=False)
grid.add_bus(acbus3)
gen3 = gce.Generator('Gen3', P=85, vset=1.025, Pmin=10, Pmax=270, Qmin=-300, Qmax=300, Cost0=335, Cost=1, Cost2=0.1225,enabled_dispatch=True)
grid.add_generator(acbus3, gen3)

# AC Bus 4
acbus4 = gce.Bus('ACBus_4', Vnom=345, is_slack=False, is_dc=False)
grid.add_bus(acbus4)

# AC Bus 5 with a load
acbus5 = gce.Bus('ACBus_5', Vnom=345, is_slack=False, is_dc=False)
grid.add_bus(acbus5)
grid.add_load(acbus5, gce.Load('load1', P=90, Q=30))

# AC Bus 6
acbus6 = gce.Bus('ACBus_6', Vnom=345, is_slack=False, is_dc=False)
grid.add_bus(acbus6)

# AC Bus 7 with a load
acbus7 = gce.Bus('ACBus_7', Vnom=345, is_slack=False, is_dc=False)
grid.add_bus(acbus7)
grid.add_load(acbus7, gce.Load('load2', P=100, Q=35))

# AC Bus 8
acbus8 = gce.Bus('ACBus_8', Vnom=345, is_slack=False, is_dc=False)
grid.add_bus(acbus8)

# AC Bus 9 with a load
acbus9 = gce.Bus('ACBus_9', Vnom=345, is_slack=False, is_dc=False)
grid.add_bus(acbus9)
grid.add_load(acbus9, gce.Load('load3', P=125, Q=50))

# DC Bus 1
dcbus1 = gce.Bus('DCBus_1', Vnom=345, is_slack=False, is_dc=True)
grid.add_bus(dcbus1)

# DC Bus 2
dcbus2 = gce.Bus('DCBus_2', Vnom=345, is_slack=False, is_dc=True)
grid.add_bus(dcbus2)

nc = gce.compile_numerical_circuit_at(circuit=grid)
print('')
