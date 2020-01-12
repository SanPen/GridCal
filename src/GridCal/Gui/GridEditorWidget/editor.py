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
import sys
import os
import networkx as nx
from warnings import warn
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtSvg import QSvgGenerator
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices.bus import Bus
from GridCal.Gui.GridEditorWidget.bus import TerminalItem, BusGraphicItem
from GridCal.Gui.GridEditorWidget.branch import BranchGraphicItem, BranchType, Branch


'''
Dependencies:

GridEditor
 |
  - EditorGraphicsView (Handles the drag and drop)
 |   |
  ---- DiagramScene
        |
         - MultiCircuit (Calculation engine)
        |
         - Graphic Objects: (BusGraphicItem, BranchGraphicItem, LoadGraphicItem, ...)


The graphic objects need to call the API objects and functions inside the MultiCircuit instance.
To do this the graphic objects call "parent.circuit.<function or object>"
'''


class EditorGraphicsView(QGraphicsView):

    def __init__(self, scene, parent=None, editor=None):
        """
        Editor where the diagram is displayed
        @param scene: DiagramScene object
        @param parent:
        @param editor:
        """
        QGraphicsView.__init__(self, scene, parent)

        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.setMouseTracking(True)
        self.setInteractive(True)
        self.scene_ = scene
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.editor = editor
        self.setAlignment(Qt.AlignCenter)

    def adapt_map_size(self):
        w = self.size().width()
        h = self.size().height()
        print('EditorGraphicsView size: ', w, h)
        self.map.change_size(w, h)

    def dragEnterEvent(self, event):
        """

        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            event.accept()

    def dragMoveEvent(self, event):
        """
        Move element
        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            event.accept()

    def dropEvent(self, event):
        """
        Create an element
        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            obj_type = event.mimeData().data('component/name')
            elm = None
            data = QByteArray()
            stream = QDataStream(data, QIODevice.WriteOnly)
            stream.writeQString('Bus')
            if obj_type == data:
                name = 'Bus ' + str(len(self.scene_.circuit.buses))
                obj = Bus(name=name)
                elm = BusGraphicItem(diagramScene=self.scene(), name=name, editor=self.editor, bus=obj)
                obj.graphic_obj = elm
                self.scene_.circuit.add_bus(obj)  # weird but it's the only way to have graphical-API communication

            if elm is not None:
                elm.setPos(self.mapToScene(event.pos()))
                self.scene_.addItem(elm)

    def wheelEvent(self, event):
        """
        Zoom
        @param event:
        @return:
        """
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # Scale the view / do the zoom
        scale_factor = 1.15
        # print(event.angleDelta().x(), event.angleDelta().y(), event.angleDelta().manhattanLength() )
        if event.angleDelta().y() > 0:
            # Zoom in
            self.scale(scale_factor, scale_factor)

        else:
            # Zooming out
            self.scale(1.0 / scale_factor, 1.0 / scale_factor)

    def add_bus(self, bus: Bus, explode_factor=1.0):
        """
        Add bus
        Args:
            bus: GridCal Bus object
            explode_factor: factor to position the node
        """
        elm = BusGraphicItem(diagramScene=self.scene(), name=bus.name, editor=self.editor, bus=bus)
        x = int(bus.x * explode_factor)
        y = int(bus.y * explode_factor)
        elm.setPos(self.mapToScene(QPoint(x, y)))
        self.scene_.addItem(elm)
        return elm


class LibraryModel(QStandardItemModel):
    """
    Items model to host the draggable icons
    """

    def __init__(self, parent=None):
        """
        Items model to host the draggable icons
        @param parent:
        """
        QStandardItemModel.__init__(self, parent)

    def mimeTypes(self):
        """

        @return:
        """
        return ['component/name']

    def mimeData(self, idxs):
        """

        @param idxs:
        @return:
        """
        mimedata = QMimeData()
        for idx in idxs:
            if idx.isValid():
                txt = self.data(idx, Qt.DisplayRole)

                data = QByteArray()
                stream = QDataStream(data, QIODevice.WriteOnly)
                stream.writeQString(txt)

                mimedata.setData('component/name', data)
        return mimedata


class DiagramScene(QGraphicsScene):

    def __init__(self, parent=None, circuit: MultiCircuit = None):
        """

        @param parent:
        """
        super(DiagramScene, self).__init__(parent)
        self.parent_ = parent
        self.circuit = circuit
        # self.setBackgroundBrush(QtCore.Qt.red)

    def mouseMoveEvent(self, mouseEvent):
        """

        @param mouseEvent:
        @return:
        """
        self.parent_.sceneMouseMoveEvent(mouseEvent)
        super(DiagramScene, self).mouseMoveEvent(mouseEvent)

    def mouseReleaseEvent(self, mouseEvent):
        """

        @param mouseEvent:
        @return:
        """
        self.parent_.sceneMouseReleaseEvent(mouseEvent)

        # call mouseReleaseEvent on "me" (continue with the rest of the actions)
        super(DiagramScene, self).mouseReleaseEvent(mouseEvent)


class ObjectFactory(object):

    def get_box(self):
        """

        @return:
        """
        pixmap = QPixmap(40, 40)
        pixmap.fill()
        painter = QPainter(pixmap)
        painter.fillRect(0, 0, 40, 40, Qt.black)
        painter.end()

        return QIcon(pixmap)

    def get_circle(self):
        """

        @return:
        """
        pixmap = QPixmap(40, 40)
        pixmap.fill()
        painter = QPainter(pixmap)

        painter.setBrush(Qt.red)
        painter.drawEllipse(0, 0, 40, 40)

        painter.end()

        return QIcon(pixmap)


class GridEditor(QSplitter):

    def __init__(self, circuit: MultiCircuit):
        """
        Creates the Diagram Editor
        Args:
            circuit: Circuit that is handling
        """
        QSplitter.__init__(self)

        # store a reference to the multi circuit instance
        self.circuit = circuit

        # nodes distance "explosion" factor
        self.expand_factor = 1.5

        # Widget layout and child widgets:
        self.horizontalLayout = QHBoxLayout(self)
        self.object_editor_table = QTableView(self)
        self.libraryBrowserView = QListView(self)
        self.libraryModel = LibraryModel(self)
        self.libraryModel.setColumnCount(1)

        # Create an icon with an icon:
        object_factory = ObjectFactory()

        # initialize library of items
        self.libItems = list()
        self.libItems.append(QStandardItem(object_factory.get_box(), 'Bus'))
        for i in self.libItems:
            self.libraryModel.appendRow(i)

        # set the objects list
        self.object_types = ['Buses', 'Branches', 'Loads', 'Static Generators',
                             'Generators', 'Batteries', 'Shunts']

        self.catalogue_types = ['Wires', 'Overhead lines', 'Underground lines', 'Sequence lines', 'Transformers']

        # Actual libraryView object
        self.libraryBrowserView.setModel(self.libraryModel)
        self.libraryBrowserView.setViewMode(self.libraryBrowserView.ListMode)
        self.libraryBrowserView.setDragDropMode(self.libraryBrowserView.DragOnly)

        # create all the schematic objects and replace the existing ones
        self.diagramScene = DiagramScene(self, circuit)  # scene to add to the QGraphicsView
        self.diagramView = EditorGraphicsView(self.diagramScene, parent=self, editor=self)

        # create the grid name editor
        self.frame1 = QFrame()
        self.frame1_layout = QVBoxLayout()
        self.frame1_layout.setContentsMargins(0, 0, 0, 0)

        self.name_editor_frame = QFrame()
        self.name_layout = QHBoxLayout()
        self.name_layout.setContentsMargins(0, 0, 0, 0)

        self.name_label = QLineEdit()
        self.name_label.setText(self.circuit.name)
        self.name_layout.addWidget(self.name_label)
        self.name_editor_frame.setLayout(self.name_layout)

        self.frame1_layout.addWidget(self.name_editor_frame)
        self.frame1_layout.addWidget(self.libraryBrowserView)
        self.frame1.setLayout(self.frame1_layout)

        # Add the two objects into a layout
        splitter2 = QSplitter(self)
        splitter2.addWidget(self.frame1)
        splitter2.addWidget(self.object_editor_table)
        splitter2.setOrientation(Qt.Vertical)
        self.addWidget(splitter2)
        self.addWidget(self.diagramView)

        # factor 1:10
        splitter2.setStretchFactor(0, 1)
        splitter2.setStretchFactor(1, 5)

        self.started_branch = None

        self.setStretchFactor(0, 0.1)
        self.setStretchFactor(1, 2000)

    def startConnection(self, port: TerminalItem):
        """
        Start the branch creation
        @param port:
        @return:
        """
        self.started_branch = BranchGraphicItem(port, None, self.diagramScene)
        self.started_branch.bus_from = port.parent
        port.setZValue(0)
        # if self.diagramView.map.isVisible():
        #     self.diagramView.map.setZValue(-1)
        port.process_callbacks(port.parent.pos() + port.pos())

    def sceneMouseMoveEvent(self, event):
        """

        @param event:
        @return:
        """
        if self.started_branch:
            pos = event.scenePos()
            self.started_branch.setEndPos(pos)

    def sceneMouseReleaseEvent(self, event):
        """
        Finalize the branch creation if its drawing ends in a terminal
        @param event:
        @return:
        """
        # Clear or finnish the started connection:
        if self.started_branch:
            pos = event.scenePos()
            items = self.diagramScene.items(pos)  # get the item (the terminal) at the mouse position

            for item in items:
                if type(item) is TerminalItem:  # connect only to terminals
                    if item.parent is not self.started_branch.fromPort.parent:  # forbid connecting to itself

                        self.started_branch.setToPort(item)
                        item.hosting_connections.append(self.started_branch)
                        # self.started_branch.setZValue(-1)
                        self.started_branch.bus_to = item.parent
                        name = 'Branch ' + str(len(self.circuit.branches))
                        v1 = self.started_branch.bus_from.api_object.Vnom
                        v2 = self.started_branch.bus_to.api_object.Vnom

                        if abs(v1 - v2) > 1.0:
                            branch_type = BranchType.Transformer
                        else:
                            branch_type = BranchType.Line

                        obj = Branch(bus_from=self.started_branch.bus_from.api_object,
                                     bus_to=self.started_branch.bus_to.api_object,
                                     name=name,
                                     branch_type=branch_type)
                        obj.graphic_obj = self.started_branch
                        self.started_branch.api_object = obj
                        self.circuit.add_branch(obj)
                        item.process_callbacks(item.parent.pos() + item.pos())
                        self.started_branch.setZValue(-1)

            if self.started_branch.toPort is None:
                self.started_branch.remove_widget()

        # release this pointer
        self.started_branch = None

    def bigger_nodes(self):
        """
        Expand the grid
        @return:
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        if len(self.diagramScene.selectedItems()) > 0:

            # expand selection
            for item in self.diagramScene.selectedItems():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() * self.expand_factor
                    y = item.pos().y() * self.expand_factor
                    item.setPos(QPointF(x, y))

                    # apply changes to the API objects
                    if item.api_object is not None:
                        item.api_object.x = x
                        item.api_object.y = y

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

        else:

            # expand all
            for item in self.diagramScene.items():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() * self.expand_factor
                    y = item.pos().y() * self.expand_factor
                    item.setPos(QPointF(x, y))

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

                    # apply changes to the API objects
                    if item.api_object is not None:
                        item.api_object.x = x
                        item.api_object.y = y

        # set the limits of the view
        self.set_limits(min_x, max_x, min_y, max_y)

    def smaller_nodes(self):
        """
        Contract the grid
        @return:
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        if len(self.diagramScene.selectedItems()) > 0:

            # shrink selection only
            for item in self.diagramScene.selectedItems():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() / self.expand_factor
                    y = item.pos().y() / self.expand_factor
                    item.setPos(QPointF(x, y))

                    # apply changes to the API objects
                    if item.api_object is not None:
                        item.api_object.x = x
                        item.api_object.y = y

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)
        else:

            # shrink all
            for item in self.diagramScene.items():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() / self.expand_factor
                    y = item.pos().y() / self.expand_factor
                    item.setPos(QPointF(x, y))

                    # apply changes to the API objects
                    if item.api_object is not None:
                        item.api_object.x = x
                        item.api_object.y = y

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

        # set the limits of the view
        self.set_limits(min_x, max_x, min_y, max_y)

    def set_limits(self, min_x, max_x, min_y, max_y, margin_factor=0.1):
        """
        Set the picture limits
        :param min_x: Minimum x value of the buses location
        :param max_x: Maximum x value of the buses location
        :param min_y: Minimum y value of the buses location
        :param max_y: Maximum y value of the buses location
        :param margin_factor: factor of separation between the buses
        """
        dx = max_x - min_x
        dy = max_y - min_y
        mx = margin_factor * dx
        my = margin_factor * dy
        h = dy + 2 * my + 80
        w = dx + 2 * mx + 80
        self.diagramScene.setSceneRect(min_x - mx, min_y - my, w, h)

    def center_nodes(self):
        """
        Center the view in the nodes
        @return: Nothing
        """
        self.diagramView.fitInView(self.diagramScene.sceneRect(), Qt.KeepAspectRatio)
        self.diagramView.scale(1.0, 1.0)

    def auto_layout(self):
        """
        Automatic layout of the nodes
        """

        if self.circuit.graph is None:
            self.circuit.compile()

        pos = nx.spectral_layout(self.circuit.graph, scale=2, weight='weight')

        pos = nx.fruchterman_reingold_layout(self.circuit.graph, dim=2,
                                             k=None, pos=pos, fixed=None, iterations=500,
                                             weight='weight', scale=20.0, center=None)

        # assign the positions to the graphical objects of the nodes
        for i, bus in enumerate(self.circuit.buses):
            try:
                x, y = pos[i] * 500
                bus.graphic_obj.setPos(QPoint(x, y))

                # apply changes to the API objects
                bus.x = x
                bus.y = y

            except KeyError as ex:
                warn('auto_layout: Node ' + str(i) + ' not in the graph!!!! \n' + str(ex))

        self.center_nodes()

    def export(self, filename, w=1920, h=1080):
        """
        Save the grid to a png file
        """

        name, extension = os.path.splitext(filename.lower())

        if extension == '.png':
            image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            self.diagramScene.render(painter)
            image.save(filename)
            painter.end()

        elif extension == '.svg':
            svg_gen = QSvgGenerator()
            svg_gen.setFileName(filename)
            svg_gen.setSize(QSize(w, h))
            svg_gen.setViewBox(QRect(0, 0, w, h))
            svg_gen.setTitle("Electrical grid schematic")
            svg_gen.setDescription("An SVG drawing created by GridCal")

            painter = QPainter(svg_gen)
            self.diagramScene.render(painter)
            painter.end()
        else:
            raise Exception('Extension ' + str(extension) + ' not supported :(')

    def add_branch(self, branch):
        """
        Add branch to the schematic
        :param branch: Branch object
        """
        terminal_from = branch.bus_from.graphic_obj.terminal
        terminal_to = branch.bus_to.graphic_obj.terminal
        graphic_obj = BranchGraphicItem(terminal_from, terminal_to, self.diagramScene, branch=branch)
        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit
        terminal_from.hosting_connections.append(graphic_obj)
        terminal_to.hosting_connections.append(graphic_obj)
        graphic_obj.redraw()
        branch.graphic_obj = graphic_obj

    def add_api_bus(self, bus: Bus, explode_factor=1.0):
        """
        Add API bus to the diagram
        :param bus: Bus instance
        :param explode_factor: explode factor
        """
        # add the graphic object to the diagram view
        graphic_obj = self.diagramView.add_bus(bus=bus, explode_factor=explode_factor)

        # add circuit pointer to the bus graphic element
        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit

        # create the bus children
        graphic_obj.create_children_icons()

        # arrange the children
        graphic_obj.arrange_children()

        return graphic_obj

    def add_api_branch(self, branch: Branch):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        terminal_from = branch.bus_from.graphic_obj.terminal
        terminal_to = branch.bus_to.graphic_obj.terminal

        graphic_obj = BranchGraphicItem(terminal_from, terminal_to, self.diagramScene, branch=branch)

        graphic_obj.diagramScene.circuit = self.circuit  # add pointer to the circuit

        terminal_from.hosting_connections.append(graphic_obj)
        terminal_to.hosting_connections.append(graphic_obj)

        graphic_obj.redraw()

        return graphic_obj

    def add_circuit_to_schematic(self, circuit: "MultiCircuit", explode_factor=1.0):
        """
        Add a complete circuit to the schematic scene
        :param circuit: MultiCircuit instance
        :param explode_factor: factor of "explosion": Separation of the nodes factor
        """
        # first create the buses
        for bus in circuit.buses:
            bus.graphic_obj = self.add_api_bus(bus, explode_factor)

        for branch in circuit.branches:
            branch.graphic_obj = self.add_api_branch(branch)

    def align_schematic(self):
        """
        Align the scene view to the content
        """
        # figure limits
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        # Align lines
        for bus in self.circuit.buses:
            bus.graphic_obj.arrange_children()
            # get the item position
            x = bus.graphic_obj.pos().x()
            y = bus.graphic_obj.pos().y()

            # compute the boundaries of the grid
            max_x = max(max_x, x)
            min_x = min(min_x, x)
            max_y = max(max_y, y)
            min_y = min(min_y, y)

        # set the figure limits
        self.set_limits(min_x, max_x, min_y, max_y)

        #  center the view
        self.center_nodes()

    def schematic_from_api(self, explode_factor=1.0):
        """
        Generate schematic from the API
        :param explode_factor: factor to separate the nodes
        :return: Nothing
        """
        # clear all
        self.diagramView.scene_.clear()

        # add to schematic
        self.add_circuit_to_schematic(self.circuit, explode_factor=explode_factor)

        self.align_schematic()



