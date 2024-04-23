import math
from GridCal.Gui.Diagrams.MapWidget.Schema.Line import Line
from GridCal.Gui.Diagrams.MapWidget.Schema.Nodes import NodeGraphicItem
from GridCal.Gui.Diagrams.MapWidget.Schema.Connector import Connector
from GridCal.Gui.Diagrams.MapWidget.Schema.Substations import SubstationGraphicItem
from GridCalEngine.Devices import MultiCircuit


class schemaManager:
    def __init__(self, scene, devX, devY):
        self.disableMove = False
        self.Scene = scene
        self.Lines = list()
        self.Substations = list()
        # self.CreateDummySchema()
        self.devX = devX
        self.devY = devY
        self.CurrentLine = None

    def CreateLine(self, newLine):
        newLine = Line(self, newLine)
        self.Lines.append(newLine)
        self.CurrentLine = newLine

    def UpdateConnectors(self):
        for line in self.Lines:
            for conector in line.ConnectorList:
                conector.update()

    def CreateSubstation(self, diagramEditor=None, diagramObject=None, lat=0.0, long=0.0):
        posX = long * self.devX
        posY = -lat * self.devY
        node = SubstationGraphicItem(self, diagramEditor, diagramObject, 0.5, posX, posY)
        self.Substations.append(node)

    def CreateDummySchema(self):
        # Define the parameters for the array formation
        num_points = 100  # Number of points in the array
        start_x = -400  # X-coordinate of the starting point
        start_y = -2800  # Y-coordinate of the starting point
        spacing_x = 2.5  # Horizontal spacing between points
        spacing_y = 2.5  # Vertical spacing between points
        self.devX = 1
        self.devY = 1
        count = 0
        # Create nodes in an array formation
        for i in range(num_points):
            self.CreateLine()
            for j in range(num_points):
                x = start_x + i * spacing_x
                y = start_y + j * spacing_y
                count = count + 1
                self.CurrentLine.CreateNode(x, y)
                if count > 10:
                    self.CreateSubstation(x, y)
                    count = 0

            # Create connectors between nodes
            for j in range(1, num_points):
                self.CurrentLine.CreateConnector((i * num_points) + j - 1, (i * num_points) + j)
