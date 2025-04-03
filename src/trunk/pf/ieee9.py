# https://github.com/SanPen/GridCal/issues/354
import numpy as np
import GridCalEngine.api as gce

# ieee9 grid
grid9 = gce.MultiCircuit('IEEE-9', Sbase=100, fbase=50)

# Add the buses and the generators and loads attached
bus1 = gce.Bus(name='Bus 1', Vnom=17.16, is_slack=True)
bus2 = gce.Bus(name='Bus 2', Vnom=18.45)
bus3 = gce.Bus(name='Bus 3', Vnom=14.145)
bus4 = gce.Bus(name='Bus 4', Vnom=230)
bus5 = gce.Bus(name='Bus 5', Vnom=230)
bus6 = gce.Bus(name='Bus 6', Vnom=230)
bus7 = gce.Bus(name='Bus 7', Vnom=230)
bus8 = gce.Bus(name='Bus 8', Vnom=230)
bus9 = gce.Bus(name='Bus 9', Vnom=230)

grid9.add_bus(bus1)
grid9.add_bus(bus2)
grid9.add_bus(bus3)
grid9.add_bus(bus4)
grid9.add_bus(bus5)
grid9.add_bus(bus6)
grid9.add_bus(bus7)
grid9.add_bus(bus8)
grid9.add_bus(bus9)

grid9.add_generator(bus1, gce.Generator(name='Slack Generator', P=0.0, vset=1.0))
grid9.add_generator(bus2, gce.Generator(name='Gen2', P=163, Sbase=100, vset=1.0))
grid9.add_generator(bus3, gce.Generator(name='Gen3', P=85, vset=1.0))

grid9.add_load(bus5, gce.Load(name='Load 1', P=125, Q=50))
grid9.add_load(bus6, gce.Load(name='Load 2', P=90, Q=30))
grid9.add_load(bus8, gce.Load(name='Load 3', P=100, Q=35))

# add Lines connecting the buses
tr1 = gce.Transformer2W(bus_from=bus4,bus_to= bus1, name='T1', HV=230, LV=16.5, nominal_power=247.5, rate=247.5, tap_phase=150*np.pi/180)
tr1.fill_design_properties(Pcu=0.0, Pfe=0.0, I0=0.0, Vsc=14.3, Sbase=grid9.Sbase)

tr2 = gce.Transformer2W(bus_from=bus7, bus_to=bus2, name='T2', HV=230, LV=18, nominal_power=192, rate=192, tap_phase=150*np.pi/180)
tr2.fill_design_properties(Pcu=0.0, Pfe=0.0, I0=0.0, Vsc=12.0, Sbase=grid9.Sbase)

tr3 = gce.Transformer2W(bus_from=bus9, bus_to=bus3, name='T3', HV=230, LV=13.8, nominal_power=128, rate=128, tap_phase=150*np.pi/180)
tr3.fill_design_properties(Pcu=0.0, Pfe=0.0, I0=0.0, Vsc=7.5, Sbase=grid9.Sbase)

grid9.add_transformer2w(tr1)  # 0.5236 => 30°#2.618
grid9.add_transformer2w(tr2)  # 2.618#2.618#0.5236
grid9.add_transformer2w(tr3)  # 0.5236

l1 = gce.Line(bus_from=bus4, bus_to=bus5, name='line 4-5')
l1.fill_design_properties(r_ohm=5.3, x_ohm=45.0, c_nf=1060, length=1.0, Imax=1.0, freq=grid9.fBase, Sbase=grid9.Sbase)

l2 = gce.Line(bus_from=bus4, bus_to=bus6, name='line 4-6')
l2.fill_design_properties(r_ohm=9.0, x_ohm=48.7, c_nf=950, length=1.0, Imax=1.0, freq=grid9.fBase, Sbase=grid9.Sbase)

l3 = gce.Line(bus_from=bus5, bus_to=bus7, name='line 5-7')
l3.fill_design_properties(r_ohm=16.9, x_ohm=85.2, c_nf=1840, length=1.0, Imax=1.0, freq=grid9.fBase, Sbase=grid9.Sbase)

l4 = gce.Line(bus_from=bus6, bus_to=bus9, name='line 6-9')
l4.fill_design_properties(r_ohm=20.6, x_ohm=89.9, c_nf=2150, length=1.0, Imax=1.0, freq=grid9.fBase, Sbase=grid9.Sbase)

l5 = gce.Line(bus_from=bus7, bus_to=bus8, name='line 7-8')
l5.fill_design_properties(r_ohm=4.5, x_ohm=38.1, c_nf=870, length=1.0, Imax=1.0, freq=grid9.fBase, Sbase=grid9.Sbase)

l6 = gce.Line(bus_from=bus8, bus_to=bus9, name='line 8-9')
l6.fill_design_properties(r_ohm=6.3, x_ohm=53.3, c_nf=1260, length=1.0, Imax=1.0, freq=grid9.fBase, Sbase=grid9.Sbase)

grid9.add_line(l1)
grid9.add_line(l2)
grid9.add_line(l3)
grid9.add_line(l4)
grid9.add_line(l5)
grid9.add_line(l6)

gce.save_file(grid9, "IEEE9.gridcal")

# Power flow
options = gce.PowerFlowOptions(gce.SolverType.HELM,
                               retry_with_other_methods=False,
                               tolerance=1e-6,
                               control_q=False,
                               control_taps_phase=False,
                               control_taps_modules=False,
                               apply_temperature_correction=False,
                               verbose=False)

drv = gce.InputsAnalysisDriver(grid=grid9)
mdl = drv.results.mdl(gce.ResultTypes.AreaAnalysis)
df = mdl.to_df()

print(df)

power_flow = gce.PowerFlowDriver(grid9, options)
power_flow.run()
print(grid9.name)
print('Converged:', power_flow.results.converged, 'error:', power_flow.results.error)
resultsDF = power_flow.results.get_bus_df()
resultsDF['V (kV)'] = resultsDF['Vm'] * np.array([bus.Vnom for bus in grid9.buses])

print(resultsDF)
