import matplotlib.pyplot as plt
import networkx as nx
import matplotlib
from GridCalEngine.Utils.MIP.selected_interface import *
from GridCalEngine.basic_structures import MIPSolvers

matplotlib.use('TkAgg')

"""
This script models a hydro network with:

- Turbine
- Pump
- FluidNode, as single place where water to electricity may happen and/or fluid can be stored
- FlowTransporter
"""


class FluidNode:
    """
    Device that can balance water (reservoirs, generators, etc)
    A "Water node"
    """

    def __init__(self, name: str,
                 min_level: float = 0.0,
                 max_level: float = 0.0,
                 current_level: float = 0.0):
        """

        :param name:
        :param min_level:
        :param max_level:
        :param current_level:
        """
        self.name = name
        self.min_level = min_level  # m3
        self.max_level = max_level  # m3
        self.initial_level = current_level  # m3

        self.level = None  # m3 -> LpVar
        self.spillage = None  # m3/h -> LpVar

        self.inflow = 0.0  # m3/h -> LpExpression
        self.outflow = 0.0  # m3/h -> LpExpression

    def __str__(self):
        return self.name

    def is_run_of_river(self) -> bool:
        """
        Is a run-of-river plant?
        :return: True/False
        """
        return self.max_level > self.min_level

    def get_inflow_value(self, solver: LpModel) -> float:

        if isinstance(self.inflow, float):
            return self.inflow
        else:
            return solver.get_value(self.inflow)

    def get_outflow_value(self, solver: LpModel) -> float:

        if isinstance(self.outflow, float):
            return self.outflow
        else:
            return solver.get_value(self.outflow)


class Turbine:
    """
    Turbine device
    """

    def __init__(self, name: str,
                 p_min: float, p_max: float, efficiency: float, max_flow_rate: float,
                 plant: FluidNode):
        """
        Generator
        :param name: name of the generator
        :param p_min: Minimum power when active (MW)
        :param p_max: Maximum power when active (MW)
        :param efficiency: Power plant energy production per fluid unit (MWh/m3)
        :param max_flow_rate: maximum water flow (m3/h)
        :param plant: Pointer to the plant where the turbine is hosted
        """
        self.name = name
        self.p_min = p_min  # MW
        self.p_max = p_max  # MW
        self.efficiency = efficiency  # MWh/m3
        self.max_flow_rate = max_flow_rate  # m3/h
        self.plant: FluidNode = plant

        self.power_output = None  # LP var -> MW

    def __str__(self):
        return self.name


class Pump:
    """
    Pump device
    """

    def __init__(self, name: str, p_min: float, p_max: float, efficiency: float, max_flow_rate: float,
                 reservoir: FluidNode):
        """
        Generator
        :param name: name of the generator
        :param p_min: Minimum power when active (MW)
        :param p_max: Maximum power when active (MW)
        :param efficiency: Power plant energy production per fluid unit (MWh/m3)
        :param max_flow_rate: maximum water flow (m3/h)
        :param reservoir: Pointer to the node where the pump is hosted
        """
        self.name = name
        self.p_min = p_min  # MW
        self.p_max = p_max  # MW
        self.efficiency = efficiency  # MWh/m3
        self.max_flow_rate = max_flow_rate  # m3/h
        self.plant: FluidNode = reservoir

        self.power_input = None  # LP var -> MW

    def __str__(self):
        return self.name


class FluidPath:
    """
    Class to represent a device that transports flow (rivers, pipes, canals, etc...)
    """

    def __init__(self,
                 name: str,
                 source: FluidNode,
                 target: FluidNode,
                 min_flow: float,
                 max_flow: float):
        """
        fluid transporter
        :param name: Name of the fluid transporter
        :param source: Source of fluid
        :param target: target for the fluid
        :param min_flow: minimum flow (m3/h)
        :param max_flow: maximum flow (m3/h)
        """
        self.name = name
        self.source = source
        self.target = target
        self.min_flow = min_flow
        self.max_flow = max_flow  # m3/h

        self.flow = None  # LP var -> m3

    def __str__(self):
        return self.name


def make_node_device_relationship(devices: List[Union[Turbine, Pump]], nodes: List[FluidNode]):
    """
    Create dictionary of the devices attached at each node
    :param devices: list of fluid moving devices (Turbines, pumps, ...)
    :param nodes: list of hosting fluid nodes (FluidNode, ...)
    :return: Dict[FluidNode] -> List[Union[Turbine, Pump]]
    """
    plants_dict = {plant: list() for plant in nodes}
    for turbine in devices:
        plants_dict[turbine.plant].append(turbine)
    return plants_dict


def hydro_dispatch_transport(fluid_nodes: List[FluidNode],
                             turbines: List[Turbine],
                             pumps: List[Pump],
                             flow_transporters: List[FluidPath],
                             demand: float,
                             dt: float = 1.0):
    """
    Formulate and solve the LP fluid dispatch problem
    :param fluid_nodes: list of FluidNodes
    :param turbines: List of turbines
    :param pumps: List of pumps
    :param flow_transporters: list of flow transporter objects (rivers, channels, etc.)
    :param demand: demand in MW
    :param dt: time step in hours
    """
    # solver = pywraplp.Solver.CreateSolver('SCIP')
    solver = LpModel(solver_type=MIPSolvers.SCIP)

    # Variables ----------------------------------------------------------------
    for turbine in turbines:
        turbine.power_output = solver.add_var(lb=turbine.p_min,
                                              ub=turbine.p_max,
                                              name=f'TPower_{turbine.name}')

    for pump in pumps:
        pump.power_output = solver.add_var(lb=pump.p_min,
                                           ub=pump.p_max,
                                           name=f'PPower_{pump.name}')

    for node in fluid_nodes:
        node.spillage = solver.add_var(lb=0.0,
                                       ub=1e20,
                                       name=f'NodeSpillage_{node.name}')

        node.level = solver.add_var(lb=node.min_level,
                                    ub=node.max_level,
                                    name=f'Level_{node.name}')

    for river in flow_transporters:
        river.flow = solver.add_var(lb=river.min_flow,
                                    ub=river.max_flow,
                                    name=f'Flow_{river.name}')

    # Constraints --------------------------------------------------------------

    # flow accounting
    for river in flow_transporters:
        river.target.inflow += river.flow  # add flow that comes in
        river.source.outflow += river.flow  # add flow that goes out

    # plants
    plants_turbine_dict = make_node_device_relationship(devices=turbines, nodes=fluid_nodes)
    plants_pumps_dict = make_node_device_relationship(devices=pumps, nodes=fluid_nodes)
    total_power_generated = 0.0  # MW
    for i, node in enumerate(fluid_nodes):

        plant_fluid_flow = 0.0
        turbines_at_the_plant = plants_turbine_dict[node]
        for turbine in turbines_at_the_plant:
            # add the generator output to the plant output in terms of water
            #    m3             h         MW                  MWh/m3  # efficiency should be dividing!?
            plant_fluid_flow += dt * turbine.power_output / turbine.efficiency

            # add the electric power to the total generation
            total_power_generated += turbine.power_output

        pumps_at_the_plant = plants_pumps_dict[node]
        for pump in pumps_at_the_plant:
            # add the pump output to the plant output in terms of water
            #    m3             h         MW                  MWh/m3
            plant_fluid_flow += dt * pump.power_output / pump.efficiency

            # subtract the electric power of the pump
            total_power_generated -= pump.power_output

        if (len(pumps_at_the_plant) + len(turbines_at_the_plant)) > 0:
            # the "produced" fluid by the turbines or pumps equals the fluid going out of the node
            solver.add_cst(cst=plant_fluid_flow == node.outflow,
                           name=f'{node.name} output')

        # Node flow balance
        # level = initial_level + dt * (inflow - outflow - spillage_flow)
        # m3 - m3 == (m3/h - m3/h) * h

        solver.add_cst(cst=node.level ==  # m3
                       node.initial_level  # m3
                       + dt * node.inflow  # h · m3 / h
                       - dt * node.outflow  # h · m3 / h
                       - dt * node.spillage,  # h · m3 / h
                       name=f'{node.name} balance')

    # Demand constraint
    solver.add_cst(cst=total_power_generated >= demand,
                   name='Satisfy_demand')

    # Objective
    total_flows = solver.sum([river.flow for river in flow_transporters])
    total_spillage = (solver.sum([plant.spillage for plant in fluid_nodes]))
    solver.minimize(total_power_generated +
                    1000 * total_spillage +  # penalize spillage
                    total_flows)

    # Solve
    # print(solver.model.ExportModelAsLpFormat(obfuscated=False))
    # solver.model.EnableOutput()
    status = solver.solve()

    # Print LP representation
    # print(solver.ExportModelAsLpFormat(obfuscated=False))

    if status == solver.OPTIMAL:

        print('Optimal solution found:')
        for node in fluid_nodes:
            turbines_at_the_plant = plants_turbine_dict[node]
            for turbine in turbines_at_the_plant:
                print(f'Plant, {node.name}:{turbine.name} : Power = {solver.get_value(turbine.power_output)} MW')

            print(f'Reservoir {node.name}: Level = {solver.get_value(node.level)} m3')
            print(f'Spillage {node.name}: {solver.get_value(node.spillage)} m3/h')

        print()
        for river in flow_transporters:
            print(f'River {river.name}: Flow = {solver.get_value(river.flow)} m3/h')

        print()
        print(f'Total Power Generated: {solver.get_value(total_power_generated)}')

        # Plot the result
        plot_hydro_dispatch(solver, fluid_nodes, turbines, flow_transporters)
    else:
        # fix(solver=solver)
        print('The problem does not have an optimal solution.')


def plot_hydro_dispatch(solver: LpModel,
                        nodes: List[FluidNode],
                        turbines: List[Turbine],
                        rivers: List[FluidPath], ):
    """

    :param solver
    :param nodes:
    :param turbines
    :param rivers:
    :return:
    """
    G = nx.DiGraph()

    plants_turbine_dict = make_node_device_relationship(devices=turbines, nodes=nodes)
    for node in nodes:

        plant_power_output = 0.0
        turbines_at_the_plant = plants_turbine_dict[node]
        for turbine in turbines_at_the_plant:
            plant_power_output += solver.get_value(turbine.power_output)

        power = '{:.1f}'.format(plant_power_output)
        flow = '{:.1f}'.format(node.get_outflow_value(solver))
        spill = '{:.1f}'.format(solver.get_value(node.spillage))
        level = '{:.1f}'.format(solver.get_value(node.level))

        label = (f"{node.name}\n"
                 f"p:{power} MW \n"
                 f"f:{flow} m3/h\n"
                 f"s:{spill} m3/h\n"
                 f"l:{level}/{node.max_level} m3")

        G.add_node(node.name, label=label)

    for river in rivers:
        flow = '{:.1f}'.format(solver.get_value(river.flow))
        G.add_edge(river.source.name, river.target.name,
                   label=f"{river.name}\n{flow} m3/h")

    pos = nx.spectral_layout(G)
    labels = nx.get_edge_attributes(G, 'label')
    node_labels = nx.get_node_attributes(G, 'label')

    nx.draw(G, pos,
            with_labels=True, labels=node_labels,
            node_size=2500, node_color='skyblue',
            font_size=7, font_color='black')

    nx.draw_networkx_edge_labels(G, pos,
                                 edge_labels=labels,
                                 font_color='red',
                                 font_size=7)

    plt.show()


########################################################################################################################
# Example
########################################################################################################################

# Example usage with 4 plants, 5 generators, 4 reservoirs, and 6 rivers
reservoir1 = FluidNode(name='Reservoir1', min_level=0, max_level=1000, current_level=500)
reservoir2 = FluidNode(name='Reservoir2', min_level=0, max_level=800, current_level=300)
reservoir3 = FluidNode(name='Reservoir3', min_level=0, max_level=1200, current_level=800)
reservoir4 = FluidNode(name='Reservoir4', min_level=0, max_level=600, current_level=400)

reservoir10 = FluidNode(name='Reservoir10', min_level=0, max_level=600, current_level=400)
reservoir11 = FluidNode(name='Reservoir11', min_level=0, max_level=600, current_level=400)

plant1 = FluidNode(name='Plant1')
plant2 = FluidNode(name='Plant2')
plant3 = FluidNode(name='Plant3')
plant4 = FluidNode(name='Plant4')

plant10 = FluidNode(name='Plant10')

gen1 = Turbine(name="G1", p_min=0.0, p_max=200, efficiency=0.9, max_flow_rate=2000, plant=plant1)
gen2 = Turbine(name="G2", p_min=0.0, p_max=200, efficiency=0.8, max_flow_rate=1500, plant=plant2)
gen3 = Turbine(name="G3", p_min=0.0, p_max=200, efficiency=0.85, max_flow_rate=1800, plant=plant3)
gen4 = Turbine(name="G4", p_min=0.0, p_max=150, efficiency=0.75, max_flow_rate=1200, plant=plant4)
gen5 = Turbine(name="G5", p_min=0.0, p_max=170, efficiency=0.85, max_flow_rate=1200, plant=plant4)

gen10 = Turbine(name="G10", p_min=0.0, p_max=170, efficiency=0.95, max_flow_rate=1200, plant=plant4)

dem1 = Pump(name="P1", p_min=0.0, p_max=100, efficiency=0.9, max_flow_rate=100, reservoir=plant1)

river1 = FluidPath(name='River1', source=reservoir1, target=plant1, min_flow=0, max_flow=550)
river2 = FluidPath(name='River2', source=reservoir2, target=plant2, min_flow=5, max_flow=520)
river3 = FluidPath(name='River3', source=plant1, target=plant2, min_flow=0, max_flow=500)
river4 = FluidPath(name='River4', source=plant2, target=plant3, min_flow=0, max_flow=530)
river5 = FluidPath(name='River5', source=plant3, target=plant4, min_flow=0, max_flow=50)
river6 = FluidPath(name='River6', source=reservoir3, target=plant3, min_flow=4, max_flow=500)
river7 = FluidPath(name='River7', source=plant4, target=reservoir4, min_flow=0, max_flow=500)
river8 = FluidPath(name='River8', source=reservoir2, target=reservoir3, min_flow=-100, max_flow=100)

river10 = FluidPath(name='River10', source=reservoir10, target=plant10, min_flow=-100, max_flow=100)
river11 = FluidPath(name='River11', source=plant10, target=reservoir11, min_flow=-100, max_flow=100)

nodes_ = [reservoir1, reservoir2, reservoir3, reservoir4, reservoir10, reservoir11, plant1, plant2, plant3, plant4, plant10]
rivers_ = [river1, river2, river3, river4, river5, river6, river7, river8, river10, river11]
turbines_ = [gen1, gen2, gen3, gen4, gen5, gen10]
pumps_ = [dem1]
demand_ = 380  # in MW

# plot_problem(reservoirs, hydro_plants, rivers)
hydro_dispatch_transport(fluid_nodes=nodes_,
                         turbines=turbines_,
                         pumps=pumps_,
                         flow_transporters=rivers_,
                         demand=demand_)
