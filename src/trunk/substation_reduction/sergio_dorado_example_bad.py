import GridCalEngine.api as gce

grid = gce.MultiCircuit(name="TNR_three_bus")

# SADR: object to encapsulate the elements within the reconfigurable substation.
s3 = gce.Substation(name="bus_3")
grid.add_substation(s3)

# SADR: substations modeled as bus-branch.
bus_1 = gce.Bus("bus_1", vnom=240, vmax=1.10, vmin=0.90)
bus_1.is_slack = True
grid.add_bus(bus_1)

bus_2 = gce.Bus("bus_2", vnom=240, vmax=1.10, vmin=0.90)
grid.add_bus(bus_2)

# SADR: substation modeled as a node-breaker model.
# Busbars
busbar_1 = gce.BusBar('busbar_1')
grid.add_bus_bar(busbar_1)
busbar_2 = gce.BusBar('busbar_2')
grid.add_bus_bar(busbar_2)

# SADR: connectivity nodes for the elements connected to the original substation.
bus3_g3 = gce.Bus('bus3_g3', vnom=240, vmax=1.10, vmin=0.90)
grid.add_bus(bus3_g3)

bus3_l3 = gce.Bus('bus3_l3', vnom=240, vmax=1.10, vmin=0.90)
grid.add_bus(bus3_l3)

bus3_l13 = gce.Bus('bus3_l13', vnom=240, vmax=1.10, vmin=0.90)
grid.add_bus(bus3_l13)

bus3_l32 = gce.Bus('bus3_l32', vnom=240, vmax=1.10, vmin=0.90)
grid.add_bus(bus3_l32)

# SADR: generator at bus 1.
gen_1 = gce.Generator(name='gen_1', vset=1.00,
                      Pmin=0, Pmax=307, Qmin=-1000, Qmax=1000,
                      Cost2=0.11, Cost=5.00, Cost0=0.00,
                      P=153.5
                      )
grid.add_generator(bus_1, gen_1)

# SADR: generator at bus 2.
gen_2 = gce.Generator(name='gen_2',
                      Pmin=0, Pmax=214, Qmin=-1000, Qmax=1000,
                      Cost2=0.085, Cost=1.200, Cost0=0.00,
                      P=107.0)
grid.add_generator(bus_2, gen_2)

# SADR: generator at bus 3 (synchronous condenser).
gen_3 = gce.Generator(name='gen_3',
                      Pmin=0.0, Pmax=0.00, Qmin=-1000, Qmax=1000,
                      Cost2=0.000, Cost=0.000, Cost0=0.000,
                      P=0.0)
grid.add_generator(bus3_g3, gen_3)

# SADR: lines
grid.add_line(gce.Line(bus_1, bus3_l13, name='line 1-3', r=0.065, x=0.62, b=0.45, rate=9000))
grid.add_line(gce.Line(bus3_l32, bus_2, name='line 3-2', r=0.025, x=0.75, b=0.70, rate=50))
grid.add_line(gce.Line(bus_1, bus_2, name='line 1-2', r=0.042, x=0.90, b=0.30, rate=9000))

grid.add_load(bus_1, gce.Load(name='load1', P=147.08, Q=40.00))
grid.add_load(bus_2, gce.Load(name='load2', P=147.08, Q=40.00))
grid.add_load(bus3_l3, gce.Load(name='load3', P=127.03, Q=50.00))

grid.add_switch(gce.Switch(name="CB1", bus_from=bus3_g3, bus_to=busbar_1, is_open=False))
grid.add_switch(gce.Switch(name="CB2", bus_from=bus3_l13, bus_to=busbar_1, is_open=False))
grid.add_switch(gce.Switch(name="CB3", bus_from=bus3_l32, bus_to=busbar_1, is_open=False))
grid.add_switch(gce.Switch(name="CB4", bus_from=bus3_l3, bus_to=busbar_1, is_open=False))
grid.add_switch(gce.Switch(name="CB5", bus_from=bus3_g3, bus_to=busbar_2, is_open=True))
grid.add_switch(gce.Switch(name="CB6", bus_from=bus3_g3, bus_to=busbar_2, is_open=True))
grid.add_switch(gce.Switch(name="CB7", bus_from=bus3_g3, bus_to=busbar_2, is_open=True))
grid.add_switch(gce.Switch(name="CB8", bus_from=bus3_g3, bus_to=busbar_2, is_open=True))

# grid.convert_to_node_breaker()
# grid.process_topology_at(t_idx=None)

options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=True, control_q=False)
power_flow = gce.PowerFlowDriver(grid, options)

power_flow.run()
print(f"Converged: {power_flow.results.converged}")
if power_flow.results.converged:
    print(f"Error: {power_flow.results.error}")
    print(power_flow.results.get_bus_df())
    print(power_flow.results.get_branch_df())
