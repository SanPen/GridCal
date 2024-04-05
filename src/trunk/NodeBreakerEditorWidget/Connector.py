# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from enum import Enum
import numpy as np
from math import sqrt
from PySide6 import QtGui
from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsPathItem


class PlugOrganization(Enum):
    HORIZONTAL = 1
    VERTICAL = 2
    CIRCULAR = 3


class Plug(QGraphicsRectItem):
    def __init__(self, parent: QGraphicsScene, container=None, connector=None):
        self.size = 10
        super().__init__(-self.size / 2, -self.size / 2, self.size, self.size)
        self.Parent = parent
        self.Container = container
        self.Connectors = list()
        self.setBrush(Qt.gray)
        self.Update()
        self.Parent.addItem(self)

    def Update(self):
        position = self.Container.scenePos()
        self.setPos(position.x(), position.y())


class Connector(QGraphicsPathItem):
    def __init__(self, parent: QGraphicsScene, first: Plug, second: Plug):
        super().__init__()
        self.Parent = parent
        self.First = first
        self.Second = second
        self.Parent.addItem(self)
        self.update()

    def update(self):
        # Get the positions of the first and second objects
        first_pos = self.getPos(self.First)
        second_pos = self.getPos(self.Second)

        mid_x = first_pos.x() + ((second_pos.x() - first_pos.x()) * 0.5)

        path = QtGui.QPainterPath(QPointF(first_pos.x(), first_pos.y()))
        path.lineTo(mid_x, first_pos.y())
        path.lineTo(mid_x, second_pos.y())
        path.lineTo(second_pos.x(), second_pos.y())

        self.setPath(path)

        # Set the line's starting and ending points
        # self.setLine(first_pos.x(), first_pos.y(), second_pos.x(), second_pos.y())

    def getPos(self, element):
        return element.scenePos()


class ConnectionManager:
    def __init__(self):
        self.PlugList = list()
        self.FirstConnector = None
        self.SecondConnector = None
        self.minimumDistance = 50

    def FindNearestConnector(self, xPos: float, yPos: float):
        min_distance = self.minimumDistance  # Initialize with positive infinity
        nearest_connector = None
        for i, plug in enumerate(self.PlugList):
            # Get the position as a QPointF
            position = plug.scenePos()

            # Access the X and Y coordinates
            x = position.x()
            y = position.y()

            # Calculate the distance using the Euclidean distance formula
            dist = sqrt((x - xPos) ** 2 + (y - yPos) ** 2)

            if dist < min_distance:
                min_distance = dist
                nearest_connector = plug

        return nearest_connector

    def SetFirstConnector(self, xPos: float, yPos: float):
        self.FirstConnector = self.FindNearestConnector(xPos, yPos)

    def SetSecondConnector(self, xPos: float, yPos: float):
        self.SecondConnector = self.FindNearestConnector(xPos, yPos)

    def CreateConnection(self, parent: QGraphicsScene):
        print(self.FirstConnector)
        print(self.SecondConnector)
        if (self.FirstConnector != None and self.SecondConnector != None):
            if (self.FirstConnector.Container != self.SecondConnector.Container
                    and self.FirstConnector != self.SecondConnector):
                newConnector = Connector(parent, self.FirstConnector, self.SecondConnector)
                self.FirstConnector.Container.Connection.Connectors.append(newConnector)
                self.SecondConnector.Container.Connection.Connectors.append(newConnector)
                self.FirstConnector.Connectors.append(newConnector)
                self.SecondConnector.Connectors.append(newConnector)
        self.FirstConnector = None
        self.SecondConnector = None


class ConnectionItem:
    def __init__(self, parent: QGraphicsScene, manager: ConnectionManager, container=None, organization=3):
        self.Parent = parent
        self.Manager = manager
        self.Container = container
        self.Connectors = list()
        self.Organization = organization
        # Plugs
        self.PlugList = list()
        self.UpdatePlugs()

    def CreatePlugs(self, number=1, updateModel=True):
        self.PlugList.clear()
        for i in range(number):
            newPlug = Plug(self.Parent, self.Container, None)
            """Add a Plug object to the Bus and arrange it vertically."""
            self.PlugList.append(newPlug)
            newPlug.setParentItem(self.Container)
            if (updateModel):
                self.UpdatePlugs()
            self.Manager.PlugList.append(newPlug)

    def UpdatePlugs(self):
        if len(self.PlugList) > 0:
            if self.Organization == 2:
                bus_height = self.Container.rect().height()
                plug_height = 20  # Height of each Plug
                spacing = bus_height / (len(self.PlugList) + 1)

                # numberPlugs = 1 + int(bus_height / (plug_height + 5))
                # self.CreatePlugs(numberPlugs, False)

                total_height = (len(self.PlugList) * (plug_height + spacing)) - spacing
                y_offset = (bus_height - total_height) / 2

                for i, plug in enumerate(self.PlugList):
                    plug.setPos(self.Container.rect().width() + 10, y_offset + i * (plug_height + spacing))

            if self.Organization == 3:
                rx = self.Container.w / 2
                ry = self.Container.h / 2
                angle_0 = 0
                d_angle = 360 / len(self.PlugList)
                angles_deg = [angle_0 + d_angle * i for i in range(len(self.PlugList))]
                angles = np.deg2rad(angles_deg)
                x = 0
                y = 0
                xt = rx * 1.2 * np.cos(angles) + rx
                yt = ry * 1.2 * np.sin(angles) + ry

                for i, plug in enumerate(self.PlugList):
                    plug.setPos(xt[i], yt[i])

    def Update(self):
        self.UpdatePlugs()
        for connector in self.Connectors:
            connector.update()
