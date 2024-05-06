import GridCalEngine.api as gce


def get_grid_bus_branch() -> gce.MultiCircuit:
    """
    Example from Sergio Dorado: 3-bus grid with no switches
    see: https://github.com/SanPen/GridCal/issues/279
    :return: MultiCircuit
    """
    grid1 = gce.MultiCircuit(name="Bus-branch grid")

    b1 = gce.Bus(name="B1")
    b2 = gce.Bus(name="B2")
    b3 = gce.Bus(name="B3")

    grid1.add_bus(b1)
    grid1.add_bus(b2)
    grid1.add_bus(b3)

    # SADR: generator at bus 1.
    gen_1 = gce.Generator(name='gen_1', vset=1.00,
                          Pmin=0, Pmax=307, Qmin=-1000, Qmax=1000,
                          Cost2=0.11, Cost=5.00, Cost0=0.00,
                          P=153.5)
    grid1.add_generator(b1, gen_1)

    # SADR: generator at bus 2.
    gen_2 = gce.Generator(name='gen_2',
                          Pmin=0, Pmax=214, Qmin=-1000, Qmax=1000,
                          Cost2=0.085, Cost=1.200, Cost0=0.00,
                          P=107.0)
    grid1.add_generator(b2, gen_2)

    # SADR: generator at bus 3 (synchronous condenser).
    gen_3 = gce.Generator(name='gen_3',
                          Pmin=0.0, Pmax=0.00, Qmin=-1000, Qmax=1000,
                          Cost2=0.000, Cost=0.000, Cost0=0.000,
                          P=0.0)
    grid1.add_generator(b3, gen_3)

    # SADR: lines
    grid1.add_line(gce.Line(b1, b2, name='line 1-2', r=0.042, x=0.90, b=0.30, rate=9000))
    grid1.add_line(gce.Line(b1, b3, name='line 1-3', r=0.065, x=0.62, b=0.45, rate=9000))
    grid1.add_line(gce.Line(b3, b2, name='line 3-2', r=0.025, x=0.75, b=0.70, rate=50))

    # add the loads
    grid1.add_load(b1, gce.Load(name='load1', P=147.08, Q=40.00))
    grid1.add_load(b2, gce.Load(name='load2', P=147.08, Q=40.00))
    grid1.add_load(b3, gce.Load(name='load3', P=127.03, Q=50.00))

    return grid1


def get_grid_node_breaker() -> gce.MultiCircuit:
    """
    Example from Sergio Dorado: 3-bus grid with switches
    See: https://github.com/SanPen/GridCal/issues/279
    :return: MultiCircuit
    """
    grid1 = gce.MultiCircuit(name="Node-breaker grid")

    # add buses: Buses can be thought as calculation nodes.
    # they are not necessarily substation busbars
    b1 = gce.Bus(name="B1")
    b2 = gce.Bus(name="B2")

    grid1.add_bus(b1)
    grid1.add_bus(b2)

    # add a proper substation
    se3 = gce.Substation(name="Substation3")
    grid1.add_substation(se3)

    # add the substation voltage levels
    vl3_1 = gce.VoltageLevel(name="VL3-1", substation=se3)
    vl3_2 = gce.VoltageLevel(name="VL3-2", substation=se3)
    grid1.add_voltage_level(vl3_1)
    grid1.add_voltage_level(vl3_2)

    # add the substation busbars
    # we create 2 busbars, each busbar will have a connectivity node inside automatically created
    b3_1 = gce.BusBar(name="BusBar 3-1", voltage_level=vl3_1)
    b3_2 = gce.BusBar(name="BusBar 3-2", voltage_level=vl3_2)

    grid1.add_bus_bar(b3_1)
    grid1.add_bus_bar(b3_2)

    # we create the 4 middle connectivity nodes
    cn3_1 = gce.ConnectivityNode(name="CN3_1")
    cn3_2 = gce.ConnectivityNode(name="CN3_2")
    cn3_3 = gce.ConnectivityNode(name="CN3_3")
    cn3_4 = gce.ConnectivityNode(name="CN3_4")

    grid1.add_connectivity_node(cn3_1)
    grid1.add_connectivity_node(cn3_2)
    grid1.add_connectivity_node(cn3_3)
    grid1.add_connectivity_node(cn3_4)

    # Add the generators
    g1 = gce.Generator(name='gen_1', vset=1.00, Pmin=0, Pmax=307, Qmin=-1000, Qmax=1000,
                       Cost2=0.11, Cost=5.00, Cost0=0.00, P=153.5)

    g2 = gce.Generator(name='gen_2', Pmin=0, Pmax=214, Qmin=-1000, Qmax=1000,
                       Cost2=0.085, Cost=1.200, Cost0=0.00, P=107.0)

    g3 = gce.Generator(name='gen_3', Pmin=0.0, Pmax=0.00, Qmin=-1000, Qmax=1000,
                       Cost2=0.000, Cost=0.000, Cost0=0.000, P=0.0)

    grid1.add_generator(bus=b1, api_obj=g1)
    grid1.add_generator(bus=b2, api_obj=g2)
    grid1.add_generator(bus=None, api_obj=g3, cn=cn3_2)

    # SADR: lines
    grid1.add_line(gce.Line(b1, b2, name='line 1-2', r=0.042, x=0.90, b=0.30, rate=9000))
    grid1.add_line(gce.Line(bus_from=b1, cn_to=cn3_1, name='line 1-3', r=0.065, x=0.62, b=0.45, rate=9000))
    grid1.add_line(gce.Line(cn_from=cn3_4, bus_to=b2, name='line 3-2', r=0.025, x=0.75, b=0.70, rate=50))

    # add loads
    grid1.add_load(bus=b1, api_obj=gce.Load(name='load1', P=147.08, Q=40.00))
    grid1.add_load(bus=b2, api_obj=gce.Load(name='load2', P=147.08, Q=40.00))
    grid1.add_load(bus=None, api_obj=gce.Load(name='load3', P=127.03, Q=50.00), cn=cn3_3)

    # add switches
    grid1.add_switch(gce.Switch(name="CB1", cn_from=cn3_1, cn_to=b3_1.cn, is_open=False))
    grid1.add_switch(gce.Switch(name="CB2", cn_from=cn3_2, cn_to=b3_1.cn, is_open=False))
    grid1.add_switch(gce.Switch(name="CB3", cn_from=cn3_3, cn_to=b3_1.cn, is_open=False))
    grid1.add_switch(gce.Switch(name="CB4", cn_from=cn3_4, cn_to=b3_1.cn, is_open=False))

    grid1.add_switch(gce.Switch(name="CB5", cn_from=cn3_1, cn_to=b3_2.cn, is_open=False))
    grid1.add_switch(gce.Switch(name="CB6", cn_from=cn3_2, cn_to=b3_2.cn, is_open=False))
    grid1.add_switch(gce.Switch(name="CB7", cn_from=cn3_3, cn_to=b3_2.cn, is_open=False))
    grid1.add_switch(gce.Switch(name="CB8", cn_from=cn3_4, cn_to=b3_2.cn, is_open=False))

    # Note: As you may observe, objects can be independently connected to buses or connectivity nodes
    # busbars are just a convenient proxy for connectivity nodes, which they store internally.
    # any model with connectivity nodes must be previously processed (only once, or upon switch state changes)
    # Switches are not used as regular branches and this constitutes the proper way of handling substation tpologies.

    # process the topology
    grid1.process_topology_at(t_idx=None)

    return grid1


if __name__ == "__main__":

    for grid_ in [
        get_grid_bus_branch(),
        get_grid_node_breaker()
    ]:
        options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=True, control_q=False)
        power_flow = gce.PowerFlowDriver(grid_, options)

        power_flow.run()
        print(f"Converged: {power_flow.results.converged}")
        if power_flow.results.converged:
            print(f"Error: {power_flow.results.error}")
            print(power_flow.results.get_bus_df())
            print(power_flow.results.get_branch_df())
