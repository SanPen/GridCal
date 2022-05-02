# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import numpy as np
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *

from GridCal.Engine.Devices.transformer3w import Transformer3W
from GridCal.Gui.GridEditorWidget.generic_graphics import ACTIVE, DEACTIVATED, FONT_SCALE, EMERGENCY
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCal.Engine.Simulations.Topology.topology_driver import reduce_buses
from GridCal.Gui.GridEditorWidget.terminal_item import TerminalItem, HandleItem
from GridCal.Gui.GridEditorWidget.load_graphics import LoadGraphicItem
from GridCal.Gui.GridEditorWidget.generator_graphics import GeneratorGraphicItem
from GridCal.Gui.GridEditorWidget.static_generator_graphics import StaticGeneratorGraphicItem
from GridCal.Gui.GridEditorWidget.battery_graphics import BatteryGraphicItem
from GridCal.Gui.GridEditorWidget.shunt_graphics import ShuntGraphicItem
from GridCal.Gui.GridEditorWidget.messages import *
from GridCal.Engine.Devices.enumerations import DeviceType


class Transformer3WGraphicItem(QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self, diagramScene, parent=None, index=0, editor=None,
                 elm: Transformer3W = None, pos: QPoint = None, n_windings=3):
        """

        :param diagramScene:
        :param parent:
        :param index:
        :param editor:
        :param elm:
        :param pos:
        :param n_windings:
        """
        QGraphicsRectItem.__init__(self, parent=parent)

        self.min_w = 180.0
        self.min_h = 20.0
        self.offset = 10
        self.h = 70
        self.w = 80
        self.setRect(0.0, 0.0, self.w, self.h)

        self.api_object: Transformer3W = elm
        self.diagramScene = diagramScene  # this is the parent that hosts the pointer to the circuit
        self.editor = editor

        # color
        self.pen_width = 4
        if self.api_object is not None:
            if self.api_object.active:
                self.color = ACTIVE['color']
                self.style = ACTIVE['style']
            else:
                self.color = DEACTIVATED['color']
                self.style = DEACTIVATED['style']
        else:
            self.color = ACTIVE['color']
            self.style = ACTIVE['style']

        self.setPen(QPen(Qt.transparent, self.pen_width, self.style))
        self.setBrush(Qt.transparent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # index
        self.index = index

        if pos is not None:
            self.setPos(pos)

        # windings
        diameter = self.w * 0.5
        r = diameter / 2
        angle_0 = -90
        d_angle = 360 / n_windings
        angles_deg = [angle_0 + d_angle * i for i in range(n_windings)]
        angles = np.deg2rad(angles_deg)
        x = r * np.cos(angles) + self.w / 4
        y = r * np.sin(angles) + self.w / 4
        xt = diameter * np.cos(angles) + diameter
        yt = diameter * np.sin(angles) + diameter

        self.windings = list()
        self.terminals = list()
        for i in range(n_windings):

            # create objects
            winding = QGraphicsEllipseItem(parent=self)
            winding.setRect(0.0, 0.0, diameter, diameter)
            winding.setPos(x[i], y[i])

            terminal = TerminalItem("t", parent=self, editor=self.editor)
            terminal.setPos(xt[i], yt[i])
            terminal.setRotation(angles_deg[i])

            # set objects style
            winding.setPen(QPen(self.color, self.pen_width, self.style))
            terminal.setPen(QPen(self.color, self.pen_width, self.style))

            self.windings.append(winding)
            self.terminals.append(terminal)

        self.big_marker = None


        # other actions
        self.set_winding_tool_tips()

    def set_winding_tool_tips(self):

        if self.api_object is not None:
            self.windings[0].setToolTip("Winding 1: {0} kV".format(self.api_object.V1))
            self.windings[1].setToolTip("Winding 2: {0} kV".format(self.api_object.V2))
            self.windings[2].setToolTip("Winding 3: {0} kV".format(self.api_object.V3))
        pass

    def set_label(self, val: str):
        """
        Set the label content
        :param val:
        :return:
        """
        self.label.setPlainText(val)

    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """
        On mouse move of this object...
        Args:
            event: QGraphicsSceneMouseEvent inherited
        """
        super().mouseMoveEvent(event)

        self.api_object.retrieve_graphic_position()

        # Arrange line positions
        for terminal in self.terminals:
            terminal.process_callbacks(self.pos() + terminal.pos() / 2)

    def add_big_marker(self, color=Qt.red, tool_tip_text=""):
        """
        Add a big marker to the bus
        :param color: Qt Color ot the marker
        :param tool_tip_text: tool tip text to display
        :return:
        """
        if self.big_marker is None:
            self.big_marker = QGraphicsEllipseItem(0, 0, 180, 180, parent=self)
            self.big_marker.setBrush(color)
            self.big_marker.setOpacity(0.5)
            self.big_marker.setToolTip(tool_tip_text)

    def delete_big_marker(self):
        """
        Delete the big marker
        """
        if self.big_marker is not None:
            self.diagramScene.removeItem(self.big_marker)
            self.big_marker = None

    def set_position(self, x, y):
        """
        Set the bus x, y position
        :param x: x in pixels
        :param y: y in pixels
        """
        if np.isnan(x):
            x = 0
        if np.isnan(y):
            y = 0
        self.setPos(QPoint(int(x), int(y)))

    def merge(self, other_bus_graphic):

        self.shunt_children += other_bus_graphic.shunt_children

    def update(self):
        """
        Update the object
        :return:
        """
        pass



