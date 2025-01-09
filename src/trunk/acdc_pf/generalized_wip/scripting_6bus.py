import numpy as np
import GridCalEngine as gce
from GridCalEngine.enumerations import ConverterControlType

# Grid instantiation
grid = gce.MultiCircuit()

# Define buses
bus1 = gce.Bus(name='B1', Vnom=135, is_slack=True)
bus2 = gce.Bus(name='B2', Vnom=135)
bus3 = gce.Bus(name='B3', Vnom=100, is_dc=True)
bus4 = gce.Bus(name='B4', Vnom=100, is_dc=True)
bus5 = gce.Bus(name='B5', Vnom=135)
bus6 = gce.Bus(name='B6', Vnom=135)

# Define AC lines
line12 = gce.Line(name='L12', bus_from=bus1, bus_to=bus2, r=0.001, x=0.1)
line25 = gce.Line(name='L25', bus_from=bus2, bus_to=bus5, r=1.05, x=0.5)
line56 = gce.Line(name='L56', bus_from=bus5, bus_to=bus6, r=0.001, x=0.1)

# Define DC lines
line34 = gce.DcLine(name='L34', bus_from=bus3, bus_to=bus4, r=2.05)

# Define VSCs
vsc1 = gce.VSC(name='VSC1', bus_from=bus3, bus_to=bus2, rate=100, alpha1=0.001, alpha2=0.015, alpha3=0.01,
               control1=ConverterControlType.Vm_ac, control2=ConverterControlType.Pdc,
               control1_val=1.0333, control2_val=0.2)

vsc2 = gce.VSC(name='VSC2', bus_from=bus4, bus_to=bus5, rate=100, alpha1=0.001, alpha2=0.015, alpha3=0.01,
               control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Qac,
               control1_val=1.05, control2_val=-7.21)

# Define generators
gen1 = gce.Generator(name='Gen1', P=1.0, vset=1.01)
gen2 = gce.Generator(name='Gen2', P=1.0, vset=1.02)

# Define loads
load1 = gce.Load(name='Load1', P=3.0, Q=0.3)
load2 = gce.Load(name='Load2', P=2.0, Q=0.5)

###############
# Add to the grid
grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_bus(bus3)
grid.add_bus(bus4)
grid.add_bus(bus5)
grid.add_bus(bus6)

grid.add_line(line12)
grid.add_line(line25)
grid.add_line(line56)

grid.add_dc_line(line34)

grid.add_vsc(vsc1)
grid.add_vsc(vsc2)

grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_generator(bus=bus6, api_obj=gen2)

grid.add_load(bus=bus2, api_obj=load1)
grid.add_load(bus=bus5, api_obj=load2)


#########
pf_driver = gce.PowerFlowDriver(grid=grid)
pf_driver.run()
print('Voltage magnitudes (p.u.): ', abs(pf_driver.results.voltage))
print('Voltage angles (deg): ', np.angle(pf_driver.results.voltage, deg=True))

# Exercise: grab the powers of VSCs
