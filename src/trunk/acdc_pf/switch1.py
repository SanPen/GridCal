import GridCalEngine as gce


#  B0 - switch - B1 - L12 - B2
#   |                       |
# Gen1                    Load 

# Grid instantiation
grid = gce.MultiCircuit()

# Define objects
bus0 = gce.Bus(name='B0', Vnom=100)
bus1 = gce.Bus(name='B1', Vnom=100)
bus2 = gce.Bus(name='B2', Vnom=100)
line12 = gce.Line(name='L12', bus_from=bus1, bus_to=bus2, r=1e-20, x=1e-5)
load2 = gce.Load(name='Load2', P=0.8, Q=0.3)
gen1 = gce.Generator(name='Gen1', P=0.5, vset=1.01)
sw1 = gce.Switch(name='Sw1', bus_from=bus0, bus_to=bus1, retained=True, normal_open=True, r=1e-6, x=1e-6)

# Add to grid
grid.add_bus(bus0)
grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_line(line12)
grid.add_load(bus=bus2, api_obj=load2)
grid.add_generator(bus=bus0, api_obj=gen1)
grid.add_switch(sw1)

# Run with open switch
pf_driver = gce.PowerFlowDriver(grid=grid)
pf_driver.run()
print('Voltage magnitudes with open switch: ', abs(pf_driver.results.voltage))

# Modify switch state
grid.switch_devices[0].retained = False
pf_driver = gce.PowerFlowDriver(grid=grid)
pf_driver.run()
print('Voltage magnitudes w/ closed switch: ', abs(pf_driver.results.voltage))

