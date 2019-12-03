# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
from GridCal.Engine.Devices.bus import Bus
from GridCal.Gui.GridEditorWidget.generic import ACTIVE, DEACTIVATED, FONT_SCALE, EMERGENCY
from GridCal.Gui.GuiFunctions import ObjectsModel
from GridCal.Engine.Simulations.Topology.topology_driver import reduce_buses
from GridCal.Gui.GridEditorWidget.load import LoadGraphicItem
from GridCal.Gui.GridEditorWidget.generator import GeneratorGraphicItem
from GridCal.Gui.GridEditorWidget.static_generator import StaticGeneratorGraphicItem
from GridCal.Gui.GridEditorWidget.battery import BatteryGraphicItem
from GridCal.Gui.GridEditorWidget.shunt import ShuntGraphicItem


class TerminalItem(QGraphicsRectItem):
    """
    Represents a connection point to a subsystem
    """

    def __init__(self, name, editor=None, parent=None, h=10, w=10):
        """

        @param name:
        @param editor:
        @param parent:
        """

        QGraphicsRectItem.__init__(self, QRectF(-6, -6, h, w), parent)
        self.setCursor(QCursor(Qt.CrossCursor))

        # Properties:
        self.color = ACTIVE['color']
        self.pen_width = 2
        self.style = ACTIVE['style']
        self.setBrush(Qt.darkGray)
        self.setPen(QPen(self.color, self.pen_width, self.style))

        # terminal parent object
        self.parent = parent

        self.hosting_connections = list()

        self.editor = editor

        # Name:
        self.name = name
        self.posCallbacks = list()
        self.setFlag(self.ItemSendsScenePositionChanges, True)

    def process_callbacks(self, value):

        w = self.rect().width()
        h2 = self.rect().height() / 2.0
        n = len(self.posCallbacks)
        dx = w / (n + 1)
        for i, call_back in enumerate(self.posCallbacks):
            call_back(value + QPointF((i + 1) * dx, h2))

    def itemChange(self, change, value):
        """

        @param change:
        @param value: This is a QPointF object with the coordinates of the upper left corner of the TerminalItem
        @return:
        """
        if change == self.ItemScenePositionHasChanged:

            self.process_callbacks(value)

            return value

        else:
            return super(TerminalItem, self).itemChange(change, value)

    def mousePressEvent(self, event):
        """
        Start a connection
        Args:
            event:

        Returns:

        """
        self.editor.startConnection(self)
        self.hosting_connections.append(self.editor.started_branch)

    def remove_all_connections(self):
        """
        Removes all the terminal connections
        Returns:

        """
        n = len(self.hosting_connections)
        for i in range(n - 1, -1, -1):
            self.hosting_connections[i].remove_widget()
            self.hosting_connections.pop(i)


class HandleItem(QGraphicsEllipseItem):
    """
    A handle that can be moved by the mouse: Element to resize the boxes
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """
        QGraphicsEllipseItem.__init__(self, QRectF(-4, -4, 8, 8), parent)

        self.posChangeCallbacks = []
        self.setBrush(Qt.red)
        self.setFlag(self.ItemIsMovable, True)
        self.setFlag(self.ItemSendsScenePositionChanges, True)
        self.setCursor(QCursor(Qt.SizeFDiagCursor))

    def itemChange(self, change, value):
        """

        @param change:
        @param value:
        @return:
        """
        if change == self.ItemPositionChange:
            x, y = value.x(), value.y()
            # TODO: make this a signal?
            # This cannot be a signal because this is not a QObject
            for cb in self.posChangeCallbacks:
                res = cb(x, y)
                if res:
                    x, y = res
                    value = QPointF(x, y)
            return value

        # Call superclass method:
        return super(HandleItem, self).itemChange(change, value)


class BusGraphicItem(QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self, diagramScene, name='Untitled', parent=None, index=0, editor=None,
                 bus: Bus = None, pos: QPoint = None):
        """

        @param diagramScene:
        @param name:
        @param parent:
        @param index:
        @param editor:
        """
        super(BusGraphicItem, self).__init__(parent)

        self.min_w = 180.0
        self.min_h = 20.0
        self.offset = 10
        self.h = bus.h if bus.h >= self.min_h else self.min_h
        self.w = bus.w if bus.w >= self.min_w else self.min_w

        self.api_object = bus

        self.diagramScene = diagramScene  # this is the parent that hosts the pointer to the circuit

        self.editor = editor

        # loads, shunts, generators, etc...
        self.shunt_children = list()

        # Enabled for short circuit
        self.sc_enabled = False
        self.pen_width = 4

        # index
        self.index = index

        if pos is not None:
            self.setPos(pos)

        # color
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

        # Label:
        self.label = QGraphicsTextItem(bus.name, self)
        # self.label.setDefaultTextColor(QtCore.Qt.white)
        self.label.setDefaultTextColor(Qt.black)
        self.label.setScale(FONT_SCALE)

        # square
        self.tile = QGraphicsRectItem(0, 0, self.min_h, self.min_h, self)
        self.tile.setOpacity(0.7)

        # connection terminals the block
        self.terminal = TerminalItem('s', parent=self, editor=self.editor)  # , h=self.h))
        self.terminal.setPen(QPen(Qt.transparent, self.pen_width, self.style))
        self.hosting_connections = list()

        # Create corner for resize:
        self.sizer = HandleItem(self.terminal)
        self.sizer.setPos(self.w, self.h)
        self.sizer.posChangeCallbacks.append(self.change_size)  # Connect the callback
        self.sizer.setFlag(self.ItemIsMovable)
        self.adapt()

        self.big_marker = None

        self.set_tile_color(self.color)

        self.setPen(QPen(Qt.transparent, self.pen_width, self.style))
        self.setBrush(Qt.transparent)
        self.setFlags(self.ItemIsSelectable | self.ItemIsMovable)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # Update size:
        self.change_size(self.w, self.h)

    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent'):
        """
        On mouse move of this object...
        Args:
            event: QGraphicsSceneMouseEvent inherited
        """
        super().mouseMoveEvent(event)

        self.api_object.retrieve_graphic_position()

    def add_big_marker(self, color=Qt.red):
        """
        Add a big marker to the bus
        Args:
            color: Qt Color ot the marker
        """
        if self.big_marker is None:
            self.big_marker = QGraphicsEllipseItem(0, 0, 180, 180, parent=self)
            self.big_marker.setBrush(color)
            self.big_marker.setOpacity(0.5)

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
        # self.setPos(self.editor.diagramView.mapToScene(QPoint(x, y)))
        self.setPos(QPoint(x, y))

    def set_tile_color(self, brush):
        """
        Set the color of the title
        Args:
            brush:  Qt Color
        """
        self.tile.setBrush(brush)
        self.terminal.setBrush(brush)

    def merge(self, other_bus_graphic):

        self.shunt_children += other_bus_graphic.shunt_children

    def update(self):
        """
        Update the object
        :return:
        """
        self.change_size(self.w, self.h)

    def change_size(self, w, h):
        """
        Resize block function
        @param w:
        @param h:
        @return:
        """
        # Limit the block size to the minimum size:
        h = self.min_h
        if w < self.min_w:
            w = self.min_w

        self.setRect(0.0, 0.0, w, h)
        self.h = h
        self.w = w

        # center label:
        rect = self.label.boundingRect()
        lw, lh = rect.width(), rect.height()
        lx = (w - lw) / 2
        ly = (h - lh) / 2 - lh * (FONT_SCALE - 1)
        self.label.setPos(lx, ly)

        # lower
        y0 = h + self.offset
        x0 = 0
        self.terminal.setPos(x0, y0)
        self.terminal.setRect(0.0, 0.0, w, 10)

        # Set text
        if self.api_object is not None:
            self.label.setPlainText(self.api_object.name)

        # rearrange children
        self.arrange_children()

        return w, h

    def arrange_children(self):
        """
        This function sorts the load and generators icons
        Returns:
            Nothing
        """
        y0 = self.h + 40
        n = len(self.shunt_children)
        inc_x = self.w / (n + 1)
        x = inc_x
        for elm in self.shunt_children:
            elm.setPos(x - elm.w / 2, y0)
            x += inc_x

        # Arrange line positions
        self.terminal.process_callbacks(self.pos() + self.terminal.pos())

    def create_children_icons(self):
        """
        Create the icons of the elements that are attached to the API bus object
        Returns:
            Nothing
        """
        for elm in self.api_object.loads:
            self.add_load(elm)

        for elm in self.api_object.static_generators:
            self.add_static_generator(elm)

        for elm in self.api_object.controlled_generators:
            self.add_generator(elm)

        for elm in self.api_object.shunts:
            self.add_shunt(elm)

        for elm in self.api_object.batteries:
            self.add_battery(elm)

        self.arrange_children()

    def contextMenuEvent(self, event):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()

        pe = menu.addAction('Enable/Disable')
        pe.triggered.connect(self.enable_disable_toggle)

        pl = menu.addAction('Plot profiles')
        pl.triggered.connect(self.plot_profiles)

        menu.addSeparator()

        ra3 = menu.addAction('Delete all the connections')
        ra3.triggered.connect(self.delete_all_connections)

        da = menu.addAction('Delete')
        da.triggered.connect(self.remove)

        re = menu.addAction('Reduce')
        re.triggered.connect(self.reduce)

        menu.addSeparator()

        al = menu.addAction('Add load')
        al.triggered.connect(self.add_load)

        ash = menu.addAction('Add shunt')
        ash.triggered.connect(self.add_shunt)

        acg = menu.addAction('Add generator')
        acg.triggered.connect(self.add_generator)

        asg = menu.addAction('Add static generator')
        asg.triggered.connect(self.add_static_generator)

        ab = menu.addAction('Add battery')
        ab.triggered.connect(self.add_battery)

        menu.addSeparator()

        arr = menu.addAction('Arrange')
        arr.triggered.connect(self.arrange_children)

        menu.addSeparator()

        sc = menu.addAction('Enable/Disable \nShort circuit')
        sc.triggered.connect(self.enable_disable_sc)

        menu.exec_(event.screenPos())

    def delete_all_connections(self):

        self.terminal.remove_all_connections()

    def reduce(self):
        """
        Reduce this bus
        :return:
        """
        reduce_buses(self.diagramScene.circuit, [self.api_object])

        self.remove()

    def remove(self):
        """
        Remove this element
        @return:
        """
        self.delete_all_connections()

        for g in self.shunt_children:
            self.diagramScene.removeItem(g.nexus)

        self.diagramScene.removeItem(self)
        self.diagramScene.circuit.delete_bus(self.api_object)

    def enable_disable_toggle(self):
        """
        Toggle bus element state
        @return:
        """
        if self.api_object is not None:
            self.api_object.active = not self.api_object.active
            # print('Enabled:', self.api_object.active)

            if self.api_object.active:

                self.set_tile_color(QBrush(ACTIVE['color']))

                for host in self.terminal.hosting_connections:
                    host.set_enable(val=True)
            else:
                self.set_tile_color(QBrush(DEACTIVATED['color']))

                for host in self.terminal.hosting_connections:
                    host.set_enable(val=False)

    def enable_disable_sc(self):
        """

        Returns:

        """
        if self.sc_enabled is True:
            # self.tile.setPen(QPen(QColor(ACTIVE['color']), self.pen_width))
            self.tile.setPen(QPen(Qt.transparent, self.pen_width))
            self.sc_enabled = False

        else:
            self.sc_enabled = True
            self.tile.setPen(QPen(QColor(EMERGENCY['color']), self.pen_width))

    def plot_profiles(self):
        """

        @return:
        """
        # Ridiculously large call to get the main GUI that hosts this bus graphic
        # time series object from the last simulation
        ts = self.diagramScene.parent().parent().parent().parent().parent().parent().parent().parent().parent().parent().parent().parent().time_series

        # get the index of this object
        i = self.diagramScene.circuit.buses.index(self.api_object)

        # get the time
        t = self.diagramScene.circuit.time_profile

        # plot the profiles
        if t is not None:
            self.api_object.plot_profiles(time_profile=t,
                                          ax_load=None,
                                          ax_voltage=None,
                                          time_series_driver=ts,
                                          my_index=i)

    def mousePressEvent(self, event):
        """
        mouse press: display the editor
        :param event: QGraphicsSceneMouseEvent
        """
        mdl = ObjectsModel([self.api_object], self.api_object.editable_headers,
                           parent=self.diagramScene.parent().object_editor_table, editable=True, transposed=True)
        self.diagramScene.parent().object_editor_table.setModel(mdl)

    def mouseDoubleClickEvent(self, event):
        """
        Mouse double click
        :param event: event object
        """
        self.adapt()

    def adapt(self):
        """
        Set the bus width according to the label text
        """
        # Todo: fix the resizing on double click
        h = self.terminal.boundingRect().height()
        w = len(self.api_object.name) * 8 + 10
        self.change_size(w=w, h=h)
        self.sizer.setPos(w, self.h)

    def add_load(self, api_obj=None):
        """
        Add load object to bus
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_load(self.api_object)

        _grph = LoadGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()

    def add_shunt(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_shunt(self.api_object)

        _grph = ShuntGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()

    def add_generator(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_generator(self.api_object)

        _grph = GeneratorGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()

    def add_static_generator(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_static_generator(self.api_object)

        _grph = StaticGeneratorGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()

    def add_battery(self, api_obj=None):
        """

        Returns:

        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self.diagramScene.circuit.add_battery(self.api_object)

        _grph = BatteryGraphicItem(self, api_obj, self.diagramScene)
        api_obj.graphic_obj = _grph
        self.shunt_children.append(_grph)
        self.arrange_children()

