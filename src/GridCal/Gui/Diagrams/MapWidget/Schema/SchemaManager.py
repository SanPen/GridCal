import math

from GridCal.Gui.Diagrams.MapWidget.Schema.Nodes import NodeGraphicItem
from GridCal.Gui.Diagrams.MapWidget.Schema.Connector import Connector
from GridCalEngine.Devices import MultiCircuit


class schemaManager:
    def __init__(self, scene):
        self.disableMove = False
        self.Scene = scene
        self.Nodes = list()
        self.ConnectorList = []
        self.CreateDummySchema()
    def UpdateConnectors(self):
        print("Updating connectors")
        for conector in self.ConnectorList:
            conector.update()

    def createSchema(self, circuit: MultiCircuit):
        for line in circuit.dc_lines:
            fromBus = line.bus_from
            toBus = line.bus_to

    def CreateDummySchema(self):
        # Define the parameters for the array formation
        num_points = 100  # Number of points in the array
        start_x = -400  # X-coordinate of the starting point
        start_y = -2800  # Y-coordinate of the starting point
        spacing_x = 2.5  # Horizontal spacing between points
        spacing_y = 2.5  # Vertical spacing between points
        # Create nodes in an array formation
        for i in range(num_points):
            for j in range(num_points):
                x = start_x + i * spacing_x
                y = start_y + j * spacing_y
                node = NodeGraphicItem(self, 0.5, x,
                                       y)  # Assuming NodeGraphicItem takes (scene, type, x, y) as arguments
                self.Nodes.append(node)

            # Create connectors between nodes
            for j in range(1, num_points):
                con = Connector(self, self.Nodes[(i * num_points) + j - 1],
                                self.Nodes[(i * num_points) + j])  # Assuming Connector takes (scene, node1, node2) as arguments
                self.ConnectorList.append(con)
