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
import sys
import os
import numpy as np
import pandas as pd
from typing import List, Dict, Union, Tuple
from collections.abc import Callable
import networkx as nx
import pyproj

from PySide6.QtCore import (Qt, QPoint, QSize, QPointF, QRect, QRectF, QMimeData, QIODevice, QByteArray,
                            QDataStream, QModelIndex)
from PySide6.QtGui import (QIcon, QPixmap, QImage, QPainter, QStandardItemModel, QStandardItem, QColor, QPen,
                           QDragEnterEvent, QDragMoveEvent, QDropEvent, QWheelEvent, QKeyEvent, QDrag)
from PySide6.QtWidgets import (QApplication, QGraphicsView, QListView, QTableView, QVBoxLayout, QHBoxLayout, QFrame,
                               QSplitter, QMessageBox, QAbstractItemView, QGraphicsScene, QGraphicsSceneMouseEvent,
                               QGraphicsItem)
from PySide6.QtSvg import QSvgGenerator

from GridCal.Gui.NodeBreakerEditorWidget.Connector import Connector, Plug, ConnectionManager
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.Devices.Substation import Bus
from GridCalEngine.Core.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.Core.Devices.Branches.line import Line
from GridCalEngine.Core.Devices.Branches.dc_line import DcLine
from GridCalEngine.Core.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Core.Devices.Branches.vsc import VSC
from GridCalEngine.Core.Devices.Branches.upfc import UPFC
from GridCalEngine.Core.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Core.Devices.Branches.transformer3w import Transformer3W
from GridCalEngine.Core.Devices.Fluid import FluidNode, FluidPath
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.Core.Devices.Diagrams.node_breaker_diagram import NodeBreakerDiagram
from GridCalEngine.Core.Devices.Diagrams.graphic_location import GraphicLocation
from GridCalEngine.basic_structures import Vec, CxVec, IntVec
from GridCalEngine.Core.Devices.types import ALL_DEV_TYPES

from GridCal.Gui.NodeBreakerEditorWidget.terminal_item import TerminalItem
from GridCal.Gui.NodeBreakerEditorWidget.Substation.bus_graphics import BusGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Fluid.fluid_path_graphics import FluidPathGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Branches.line_graphics import LineGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Branches.winding_graphics import WindingGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Branches.dc_line_graphics import DcLineGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Branches.transformer2w_graphics import TransformerGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Branches.hvdc_graphics import HvdcGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Branches.vsc_graphics import VscGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Branches.upfc_graphics import UpfcGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Branches.Rectangle_Connector import RectangleConnectorGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.Injections.generator_graphics import GeneratorGraphicItem
from GridCal.Gui.NodeBreakerEditorWidget.generic_graphics import ACTIVE
import GridCal.Gui.Visualization.visualization as viz
import GridCal.Gui.Visualization.palettes as palettes
from GridCal.Gui.messages import info_msg
from GridCal.Gui.GuiFunctions import ObjectsModel
from matplotlib import pyplot as plt

'''
Structure:

{NodeBreakerEditorWidget: QSplitter}
 |
  - .editor_graphics_view {QGraphicsView} (Handles the drag and drop)
 |      
  - .diagram_scene {DiagramScene: QGraphicsScene}
 |       
  - .circuit {MultiCircuit} (Calculation engine)
 |       
  - .diagram {BusBranchDiagram} records the objects and their position to load and save diagrams


The graphic objects need to call the API objects and functions inside the MultiCircuit instance.
To do this the graphic objects call "parent.circuit.<function or object>"
'''


class NodeBreakerLibraryModel(QStandardItemModel):
    """
    Items model to host the draggable icons
    This is the list of draggable items
    """

    def __init__(self, parent=None):
        """
        Items model to host the draggable icons
        @param parent:
        """
        QStandardItemModel.__init__(self, parent)

        self.setColumnCount(1)

        # add bus to the drag&drop
        bus_icon = QIcon()
        bus_icon.addPixmap(QPixmap(":/Icons/icons/bus_icon.svg"))
        self.bus_name = "BUS_BAR"
        item = QStandardItem(bus_icon, self.bus_name)
        item.setToolTip("Drag & drop this into the schematic")
        self.appendRow(item)

        # add transformer3w to the drag&drop
        t3w_icon = QIcon()
        t3w_icon.addPixmap(QPixmap(":/Icons/icons/transformer3w.svg"))
        self.transformer3w_name = "RECTANGLE"
        item = QStandardItem(t3w_icon, self.transformer3w_name)
        item.setToolTip("Drag & drop this into the schematic")
        self.appendRow(item)

        # add fluid-node to the drag&drop
        # dam_icon = QIcon()
        # dam_icon.addPixmap(QPixmap(":/Icons/icons/dam.svg"))
        # self.fluid_node_name = "Fluid-node"
        # item = QStandardItem(dam_icon, self.fluid_node_name)
        # item.setToolTip("Drag & drop this into the schematic")
        # self.appendRow(item)

    @staticmethod
    def to_bytes_array(val: str) -> QByteArray:
        """
        Convert string to QByteArray
        :param val: string
        :return: QByteArray
        """
        data = QByteArray()
        stream = QDataStream(data, QIODevice.WriteOnly)
        stream.writeQString(val)
        return data

    def get_bus_mime_data(self) -> QByteArray:
        return self.to_bytes_array(self.bus_name)

    def get_3w_transformer_mime_data(self) -> QByteArray:
        return self.to_bytes_array(self.transformer3w_name)


    def mimeTypes(self) -> List[str]:
        """

        @return:
        """
        return ['component/name']

    def mimeData(self, idxs: List[QModelIndex]) -> QMimeData:
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

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled


class NodeBreakerDiagramScene(QGraphicsScene):
    """
    DiagramScene
    This class is needed to augment the mouse move and release events
    """

    def __init__(self, parent: "NodeBreakerEditorWidget"):
        """

        :param parent:
        """
        super(NodeBreakerDiagramScene, self).__init__(parent)
        self.parent_ = parent
        self.displacement = QPoint(0, 0)
        # self.setSceneRect(-5000, -5000, 10000, 10000)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """

        # pan movement
        if self.parent_.startPos is not None:
            scale_factor = 1.5
            try:
                scene_pos = QPointF(event.scenePos())
                self.displacement = self.displacement + ((scene_pos - self.parent_.startPos) / scale_factor)
                temp_cen = self.parent_.newCenterPos - self.displacement
                self.parent_.editor_graphics_view.centerOn(temp_cen)
            except RecursionError:
                print("Recursion Error at mouseMoveEvent")

        self.parent_.scene_mouse_move_event(event)

        # call the parent event
        super(NodeBreakerDiagramScene, self).mouseMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        :param event:
        :return:
        """

        self.parent_.scene_mouse_press_event(event)
        self.displacement = QPointF(0, 0)
        super(NodeBreakerDiagramScene, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """
        self.parent_.create_branch_on_mouse_release_event(event)

        # Mouse pan
        if event.button() == Qt.MouseButton.RightButton:
            self.parent_.startPos = None
            self.parent_.editor_graphics_view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

        self.deselectAllItems()

        # call mouseReleaseEvent on "me" (continue with the rest of the actions)
        super(NodeBreakerDiagramScene, self).mouseReleaseEvent(event)

    def deselectAllItems(self):

        num = 0
        for item in self.items():
            if (item.isSelected()):
                num = num + 1

        if (num < 2):
            for item in self.items():
                item.setSelected(False)

class NodeBreakerEditorWidget(QSplitter):
    """
    NodeBreakerEditorWidget
    This is the node-breaker editor
    """

    def __init__(self,
                 circuit: MultiCircuit,
                 diagram: Union[NodeBreakerDiagram, None],
                 default_bus_voltage: float = 10.0):
        """
        Creates the Diagram Editor (NodeBreakerEditorWidget)
        :param circuit: Circuit that is handling
        :param diagram: NodeBreakerDiagram to use (optional)
        :param default_bus_voltage: Default bus voltages (kV)
        """

        QSplitter.__init__(self)

        # connection
        self.PlugManager = ConnectionManager()

        # store a reference to the multi circuit instance
        self.circuit: MultiCircuit = circuit

        # diagram to store the objects locations
        self.diagram: NodeBreakerDiagram = diagram if diagram is not None else NodeBreakerDiagram()

        # default_bus_voltage (kV)
        self.default_bus_voltage = default_bus_voltage

        # nodes distance "explosion" factor
        self.expand_factor = 1.1

        # Widget layout and child widgets:
        self.horizontal_layout = QHBoxLayout(self)
        self.object_editor_table = QTableView(self)

        # library model
        self.library_model = NodeBreakerLibraryModel(self)

        # Actual libraryView object
        self.library_view = QListView(self)
        self.library_view.setModel(self.library_model)
        self.library_view.setViewMode(self.library_view.ViewMode.ListMode)
        self.library_view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

        # create all the schematic objects and replace the existing ones
        self.diagram_scene = NodeBreakerDiagramScene(parent=self)  # scene to add to the QGraphicsView

        self.results_dictionary = dict()

        self.editor_graphics_view = QGraphicsView(self.diagram_scene)
        self.editor_graphics_view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.editor_graphics_view.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.editor_graphics_view.setMouseTracking(True)
        self.editor_graphics_view.setInteractive(True)
        self.editor_graphics_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.editor_graphics_view.setAlignment(Qt.AlignCenter)

        self.editor_graphics_view.dragEnterEvent = self.graphicsDragEnterEvent
        self.editor_graphics_view.dragMoveEvent = self.graphicsDragMoveEvent
        self.editor_graphics_view.dropEvent = self.graphicsDropEvent
        self.editor_graphics_view.wheelEvent = self.graphicsWheelEvent
        self.editor_graphics_view.keyPressEvent = self.graphicsKeyPressEvent

        # Zoom indicator
        self._zoom = 0

        # create the grid name editor
        self.frame1 = QFrame()
        self.frame1_layout = QVBoxLayout()
        self.frame1_layout.setContentsMargins(0, 0, 0, 0)

        self.frame1_layout.addWidget(self.library_view)
        self.frame1.setLayout(self.frame1_layout)

        # Add the two objects into a layout
        splitter2 = QSplitter(self)
        splitter2.addWidget(self.frame1)
        splitter2.addWidget(self.object_editor_table)
        splitter2.setOrientation(Qt.Vertical)
        self.addWidget(splitter2)
        self.addWidget(self.editor_graphics_view)

        # factor 1:10
        splitter2.setStretchFactor(0, 1)
        splitter2.setStretchFactor(1, 5)

        self.setStretchFactor(0, 0)
        self.setStretchFactor(1, 2000)

        self.setMouseTracking(True)
        self.startPos = QPoint()
        self.newCenterPos = QPoint()
        self.displacement = QPoint()
        self.startPos = None

        self.PreviewSketch = False

        obj1 = Bus(name=f'BUS_BAR {len(self.circuit.buses)}',
                  vnom=self.default_bus_voltage)

        Bus1 = BusGraphicItem(editor=self,
                                        bus = obj1,
                                        x=340,
                                        y=340,
                                        h=20,
                                        w=20)

        self.previewPlug1 = Plug(self.diagram_scene, Bus1, None)

        obj2 = Bus(name=f'BUS_BAR {len(self.circuit.buses)}',
                  vnom=self.default_bus_voltage)

        Bus2 = BusGraphicItem(editor=self,
                                        bus = obj2,
                                        x=70,
                                        y=70,
                                        h=20,
                                        w=20)

        self.previewPlug2 = Plug(self.diagram_scene, Bus2, None)

        self.previewLine = Connector(self.diagram_scene, self.previewPlug1, self.previewPlug2)

        self.DisablePreview()

        self.time_index_: Union[None, int] = None

    def set_time_index(self, time_index: Union[int, None]):
        """
        Set the time index of the table
        :param time_index: None or integer value
        """
        self.time_index_ = time_index

        mdl = self.object_editor_table.model()
        if isinstance(mdl, ObjectsModel):
            mdl.set_time_index(time_index=time_index)

    def set_editor_model(self, api_object: ALL_DEV_TYPES, dictionary_of_lists: Dict[str, List[ALL_DEV_TYPES]] = {}):
        """
        Set an api object to appear in the editable table view of the editor
        :param api_object: any EditableDevice
        :param dictionary_of_lists: dictionary of lists of objects that may be referenced to
        """
        mdl = ObjectsModel(objects=[api_object],
                           property_list=api_object.property_list,
                           time_index=self.time_index_,
                           parent=self.object_editor_table,
                           editable=True,
                           transposed=True,
                           dictionary_of_lists=dictionary_of_lists)

        self.object_editor_table.setModel(mdl)

    def DisablePreview(self):
        self.previewPlug1.setVisible(False)
        self.previewPlug2.setVisible(False)
        self.previewLine.setVisible(False)

    def EnablePreview(self):
        self.previewPlug1.setVisible(True)
        self.previewPlug2.setVisible(True)
        self.previewLine.setVisible(True)

    def graphicsDragEnterEvent(self, event: QDragEnterEvent) -> None:
        """

        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            event.accept()

    def graphicsDragMoveEvent(self, event: QDragMoveEvent) -> None:
        """
        Move element
        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            event.accept()

    def graphicsDropEvent(self, event: QDropEvent) -> None:
        """
        Create an element
        @param event:
        @return:
        """
        if event.mimeData().hasFormat('component/name'):
            obj_type = event.mimeData().data('component/name')
            bus_data = self.library_model.get_bus_mime_data()
            tr3w_data = self.library_model.get_3w_transformer_mime_data()

            point0 = self.editor_graphics_view.mapToScene(event.position().x(), event.position().y())
            x0 = point0.x()
            y0 = point0.y()

            if bus_data == obj_type:
                obj = Bus(name=f'BUS_BAR {len(self.circuit.buses)}',
                          vnom=self.default_bus_voltage)

                graphic_object = BusGraphicItem(editor=self,
                                                bus=obj,
                                                x=x0,
                                                y=y0,
                                                h=20,
                                                w=80)

                self.add_to_scene(graphic_object=graphic_object)

                # weird but it's the only way to have graphical-API communication
                self.circuit.add_bus(obj)

                # add to the diagram list
                self.update_diagram_element(device=obj,
                                            x=x0,
                                            y=y0,
                                            w=graphic_object.w,
                                            h=graphic_object.h,
                                            r=0,
                                            graphic_object=graphic_object)

            elif tr3w_data == obj_type:
                obj = Transformer3W(name=f"Transformer 3W {len(self.circuit.transformers3w)}")
                graphic_object = self.create_transformer_3w_graphics(elm=obj, x=x0, y=y0)
                self.add_to_scene(graphic_object=graphic_object)

                # weird but it's the only way to have graphical-API communication
                self.circuit.add_transformer3w(obj)

                # add to the diagram list
                self.update_diagram_element(device=obj,
                                            x=x0,
                                            y=y0,
                                            w=graphic_object.w,
                                            h=graphic_object.h,
                                            r=0,
                                            graphic_object=graphic_object)

            else:
                raise Exception(f"graphicsDropEvent Not implemented for {obj_type}")

    def graphicsWheelEvent(self, event: QWheelEvent) -> None:
        """
        Zoom
        @param event:
        @return:
        """
        self.editor_graphics_view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Scale the view / do the zoom
        scale_factor = 1.15
        # print(event.angleDelta().x(), event.angleDelta().y(), event.angleDelta().manhattanLength() )
        if event.angleDelta().y() > 0:
            # Zoom in
            self.zoom_in(scale_factor)

        else:
            # Zooming out
            self.zoom_out(scale_factor)

    def graphicsKeyPressEvent(self, event: QKeyEvent):
        """
        Key press event cature
        :param event:
        :return:
        """
        if event.key() == Qt.Key_Delete:
            self.delete_Selected()

    def zoom_in(self, scale_factor: float = 1.15) -> None:
        """

        :param scale_factor:
        """
        self.editor_graphics_view.scale(scale_factor, scale_factor)

    def zoom_out(self, scale_factor: float = 1.15) -> None:
        """

        :param scale_factor:
        """
        self.editor_graphics_view.scale(1.0 / scale_factor, 1.0 / scale_factor)

    def start_connection(self, port: TerminalItem) -> LineGraphicItem:
        # this is beign called from the bus graphic item on the creation of a new connection
        pass

    def create_bus_graphics(self, bus: Bus, x: int, y: int, h: int, w: int) -> BusGraphicItem:
        """
        create the Bus graphics
        :param bus: GridCal Bus object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :return: BusGraphicItem
        """

        graphic_object = BusGraphicItem(editor=self,
                                        bus=bus,
                                        x=x,
                                        y=y,
                                        h=h,
                                        w=w)
        return graphic_object

    def create_transformer_3w_graphics(self, elm: Transformer3W, x: int, y: int) -> RectangleConnectorGraphicItem:
        """
        Add Transformer3W to the graphics
        :param elm: Transformer3W
        :param x: x coordinate
        :param y: y coordinate
        :return: Transformer3WGraphicItem
        """
        graphic_object = RectangleConnectorGraphicItem(editor=self, elm=elm)
        graphic_object.setPos(QPoint(x, y))
        return graphic_object

    def create_fluid_node_graphics(self, node: FluidNode, x: int, y: int, h: int, w: int) -> FluidNodeGraphicItem:
        """
        Add fluid node to graphics
        :param node: GridCal FluidNode object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :return: FluidNodeGraphicItem
        """

        graphic_object = FluidNodeGraphicItem(editor=self, fluid_node=node, x=x, y=y, h=h, w=w)
        return graphic_object

    def set_data(self, circuit: MultiCircuit, diagram: NodeBreakerDiagram):
        """
        Set the widget data and redraw
        :param circuit: MultiCircuit
        :param diagram: BusBranchDiagram
        """
        self.clear()
        self.circuit = circuit
        self.diagram = diagram
        self.draw()

    def draw(self) -> None:
        """
        Draw diagram
        :return:
        """
        # add buses first
        bus_dict: Dict[str, BusGraphicItem] = dict()
        fluid_node_dict: Dict[str, FluidNodeGraphicItem] = dict()
        Connector.draw()
        for category, points_group in self.diagram.data.items():

            if category == DeviceType.BusDevice.value:

                for idtag, location in points_group.locations.items():
                    # add the graphic object to the diagram view
                    graphic_object = self.create_bus_graphics(bus=location.api_object,
                                                              x=location.x,
                                                              y=location.y,
                                                              h=location.h,
                                                              w=location.w)
                    self.add_to_scene(graphic_object=graphic_object)

                    # create the bus children
                    graphic_object.create_children_widgets()

                    graphic_object.change_size(h=location.h,
                                               w=location.w)

                    # add buses reference for later
                    bus_dict[idtag] = graphic_object
                    points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.Transformer3WDevice.value:

                for idtag, location in points_group.locations.items():
                    elm: Transformer3W = location.api_object

                    graphic_object = self.create_transformer_3w_graphics(elm=elm,
                                                                         x=location.x,
                                                                         y=location.y)
                    self.add_to_scene(graphic_object=graphic_object)

                    bus_1_graphic_data = self.diagram.query_point(elm.bus1)
                    bus_2_graphic_data = self.diagram.query_point(elm.bus2)
                    bus_3_graphic_data = self.diagram.query_point(elm.bus3)

                    conn1 = WindingGraphicItem(fromPort=graphic_object.terminals[0],
                                               toPort=bus_1_graphic_data.graphic_object.terminal,
                                               editor=self)

                    graphic_object.set_connection(i=0, bus=elm.bus1, conn=conn1)

                    conn2 = WindingGraphicItem(fromPort=graphic_object.terminals[1],
                                               toPort=bus_2_graphic_data.graphic_object.terminal,
                                               editor=self)
                    graphic_object.set_connection(i=1, bus=elm.bus2, conn=conn2)

                    conn3 = WindingGraphicItem(fromPort=graphic_object.terminals[2],
                                               toPort=bus_3_graphic_data.graphic_object.terminal,
                                               editor=self)
                    graphic_object.set_connection(i=2, bus=elm.bus3, conn=conn3)

                    graphic_object.set_position(x=location.x,
                                                y=location.y)

                    graphic_object.change_size(h=location.h,
                                               w=location.w)

                    graphic_object.update_conn()
                    points_group.locations[idtag].graphic_object = graphic_object

            if category == DeviceType.FluidNodeDevice.value:

                for idtag, location in points_group.locations.items():
                    # add the graphic object to the diagram view
                    graphic_object = self.create_fluid_node_graphics(node=location.api_object,
                                                                     x=location.x,
                                                                     y=location.y,
                                                                     h=location.h,
                                                                     w=location.w)
                    self.add_to_scene(graphic_object=graphic_object)

                    # create the bus children
                    graphic_object.create_children_widgets()

                    graphic_object.change_size(h=location.h,
                                               w=location.w)

                    # add fluid node reference for later
                    fluid_node_dict[idtag] = graphic_object
                    points_group.locations[idtag].graphic_object = graphic_object

                    # map the internal bus
                    if location.api_object.bus is not None:
                        bus_dict[location.api_object.bus.idtag] = graphic_object

            else:
                # pass for now...
                pass

        def find_my_node(idtag_: str):
            """
            Function to look for the bus or fluid node
            :param idtag_: bus or fluidnode idtag
            :return: Matching graphic object
            """
            graphic_obj = bus_dict.get(idtag_, None)
            if graphic_obj is None:
                graphic_obj = fluid_node_dict.get(idtag_, None)
            return graphic_obj

        # add the rest of the branches
        for category, points_group in self.diagram.data.items():

            if category == DeviceType.LineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: Line = location.api_object
                    bus_f_graphic_obj = find_my_node(branch.bus_from.idtag)
                    bus_t_graphic_obj = find_my_node(branch.bus_to.idtag)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = LineGraphicItem(fromPort=terminal_from,
                                                         toPort=terminal_to,
                                                         editor=self,
                                                         api_object=branch)
                        self.add_to_scene(graphic_object=graphic_object)

                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.DCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: DcLine = location.api_object
                    bus_f_graphic_obj = find_my_node(branch.bus_from.idtag)
                    bus_t_graphic_obj = find_my_node(branch.bus_to.idtag)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = DcLineGraphicItem(fromPort=terminal_from,
                                                           toPort=terminal_to,
                                                           editor=self,
                                                           api_object=branch)
                        self.add_to_scene(graphic_object=graphic_object)

                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.HVDCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: HvdcLine = location.api_object
                    bus_f_graphic_obj = find_my_node(branch.bus_from.idtag)
                    bus_t_graphic_obj = find_my_node(branch.bus_to.idtag)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = HvdcGraphicItem(fromPort=terminal_from,
                                                         toPort=terminal_to,
                                                         editor=self,
                                                         api_object=branch)
                        self.add_to_scene(graphic_object=graphic_object)

                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.VscDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: VSC = location.api_object
                    bus_f_graphic_obj = find_my_node(branch.bus_from.idtag)
                    bus_t_graphic_obj = find_my_node(branch.bus_to.idtag)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = VscGraphicItem(fromPort=terminal_from,
                                                        toPort=terminal_to,
                                                        editor=self,
                                                        api_object=branch)
                        self.add_to_scene(graphic_object=graphic_object)

                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.UpfcDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: UPFC = location.api_object
                    bus_f_graphic_obj = find_my_node(branch.bus_from.idtag)
                    bus_t_graphic_obj = find_my_node(branch.bus_to.idtag)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = UpfcGraphicItem(fromPort=terminal_from,
                                                         toPort=terminal_to,
                                                         editor=self,
                                                         api_object=branch)
                        self.add_to_scene(graphic_object=graphic_object)

                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.Transformer2WDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: Transformer2W = location.api_object
                    bus_f_graphic_obj = find_my_node(branch.bus_from.idtag)
                    bus_t_graphic_obj = find_my_node(branch.bus_to.idtag)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = TransformerGraphicItem(fromPort=terminal_from,
                                                                toPort=terminal_to,
                                                                editor=self,
                                                                api_object=branch)
                        self.add_to_scene(graphic_object=graphic_object)

                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            elif category == DeviceType.FluidPathDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: FluidPath = location.api_object
                    bus_f_graphic_obj = fluid_node_dict.get(branch.source.idtag, None)
                    bus_t_graphic_obj = fluid_node_dict.get(branch.target.idtag, None)

                    if bus_f_graphic_obj and bus_t_graphic_obj:
                        terminal_from = bus_f_graphic_obj.terminal
                        terminal_to = bus_t_graphic_obj.terminal

                        graphic_object = FluidPathGraphicItem(fromPort=terminal_from,
                                                              toPort=terminal_to,
                                                              editor=self,
                                                              api_object=branch)
                        self.add_to_scene(graphic_object=graphic_object)

                        terminal_from.hosting_connections.append(graphic_object)
                        terminal_to.hosting_connections.append(graphic_object)
                        graphic_object.redraw()
                        points_group.locations[idtag].graphic_object = graphic_object

            else:
                pass
                # print('draw: Unrecognized category: {}'.format(category))

        # last pass: arange children
        for category, points_group in self.diagram.data.items():
            if category in [DeviceType.BusDevice.value, DeviceType.FluidNodeDevice.value]:
                for idtag, location in points_group.locations.items():
                    # arrange children
                    location.graphic_object.arrange_children()

    @property
    def name(self):
        """
        Get the diagram name
        :return:
        """
        return self.diagram.name

    @name.setter
    def name(self, val: str):
        """
        Name setter
        :param val:
        :return:
        """
        self.diagram.name = val

    def update_diagram_element(self, device: EditableDevice,
                               x: int = 0, y: int = 0, w: int = 0, h: int = 0, r: float = 0,
                               graphic_object: QGraphicsItem = None) -> None:
        """
        Set the position of a device in the diagram
        :param device: EditableDevice
        :param x: x position (px)
        :param y: y position (px)
        :param h: height (px)
        :param w: width (px)
        :param r: rotation (deg)
        :param graphic_object: Graphic object associated
        """
        self.diagram.set_point(device=device,
                               location=GraphicLocation(x=x,
                                                        y=y,
                                                        h=h,
                                                        w=w,
                                                        r=r,
                                                        api_object=device,
                                                        graphic_object=graphic_object))

    def add_to_scene(self, graphic_object: QGraphicsItem = None) -> None:
        """
        Add item to the diagram and the diagram scene
        :param graphic_object: Graphic object associated
        """

        self.diagram_scene.addItem(graphic_object)

    def remove_from_scene(self, graphic_object: QGraphicsItem = None) -> None:
        """
        Add item to the diagram and the diagram scene
        :param graphic_object: Graphic object associated
        """

        self.diagram_scene.removeItem(graphic_object)

    def delete_diagram_element(self, device: EditableDevice) -> None:
        """
        Delete device from the diagram registry
        :param device: EditableDevice
        """
        graphic_object: QGraphicsItem = self.diagram.delete_device(device=device)

        if graphic_object is not None:
            try:
                self.remove_from_scene(graphic_object)
            except:
                pass

    def remove_element(self, device: EditableDevice,
                       graphic_object: Union[QGraphicsItem, None] = None) -> None:
        """
        Remove device from the diagram and the database
        :param device: EditableDevice
        :param graphic_object: optionally provide the graphics object associated
        """
        if graphic_object is None:
            self.delete_diagram_element(device=device)
        else:
            self.remove_from_scene(graphic_object)

        self.circuit.delete_elements_by_type(obj=device)

    def delete_diagram_elements(self, elements: List[EditableDevice]):
        """
        Delete device from the diagram registry
        :param elements:
        :return:
        """
        for elm in elements:
            self.delete_diagram_element(elm)

    def set_selected_buses(self, buses: List[Bus]):
        """
        Select the buses
        :param buses: list of Buses
        """
        for bus in buses:
            graphic_object = self.diagram.query_point(bus).graphic_object
            if isinstance(graphic_object, BusGraphicItem):
                graphic_object.setSelected(True)

    def get_selected_buses(self) -> List[Tuple[int, Bus, BusGraphicItem]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, Bus, BusGraphicItem]] = list()
        points_group = self.diagram.data.get(DeviceType.BusDevice.value, None)

        if points_group:

            bus_dict: Dict[str: Tuple[int, Bus]] = {b.idtag: (i, b) for i, b in enumerate(self.circuit.get_buses())}

            for bus_idtag, point in points_group.locations.items():
                if point.graphic_object.isSelected():
                    idx, bus = bus_dict[bus_idtag]
                    lst.append((idx, bus, point.graphic_object))
        return lst

    def delete_Selected(self) -> None:
        """
        Delete the selected items from the diagram
        """
        # get the selected buses
        selected = self.get_selected()

        if len(selected) > 0:
            reply = QMessageBox.question(self, 'Delete',
                                         'Are you sure that you want to delete the selected elements?',
                                         QMessageBox.StandardButton.Yes,
                                         QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes.value:

                # remove the buses (from the schematic and the circuit)
                for bus, graphic_obj in selected:
                    self.remove_element(device=bus, graphic_object=graphic_obj)
            else:
                pass
        else:
            info_msg('Choose some elements from the schematic', 'Delete')

    def get_buses(self) -> List[Tuple[int, Bus, BusGraphicItem]]:
        """
        Get all the buses
        :return: tuple(bus index, bus_api_object, bus_graphic_object)
        """
        lst: List[Tuple[int, Bus, BusGraphicItem]] = list()
        points_group = self.diagram.data.get(DeviceType.BusDevice.value, None)

        if points_group:

            bus_dict: Dict[str: Tuple[int, Bus]] = {b.idtag: (i, b) for i, b in enumerate(self.circuit.get_buses())}

            for bus_idtag, point in points_group.locations.items():
                idx, bus = bus_dict[bus_idtag]
                lst.append((idx, bus, point.graphic_object))

        return lst

    def scene_mouse_move_event(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """

        pos = event.scenePos()
        if (self.PreviewSketch):
            if (self.PlugManager.FirstConnector != None):
                pl1ps = self.PlugManager.FirstConnector.scenePos()
                self.previewPlug1.setPos(pl1ps.x(), pl1ps.y())
                pl2ps = event.scenePos()
                self.previewPlug2.setPos(pl2ps.x(), pl2ps.y())
            self.previewLine.update()


    def scene_mouse_press_event(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        :param event:
        :return:
        """


        mousePos = event.scenePos()
        self.PlugManager.SetFirstConnector(mousePos.x(), mousePos.y())
        if (self.PlugManager.FirstConnector != None):
            if (not self.PlugManager.FirstConnector.Container.isSelected()):
                self.editor_graphics_view.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.EnablePreview()
                self.PreviewSketch = True;
                pl1ps = self.PlugManager.FirstConnector.scenePos()
                self.previewPlug1.setPos(pl1ps.x(), pl1ps.y())
                pl2ps = event.scenePos()
                self.previewPlug2.setPos(pl2ps.x(), pl2ps.y())
                self.previewLine.update()

        # Mouse pan
        if event.button() == Qt.MouseButton.RightButton:
            viewport_rect = self.editor_graphics_view.viewport().rect()
            top_left_scene = self.editor_graphics_view.mapToScene(viewport_rect.topLeft())
            bottom_right_scene = self.editor_graphics_view.mapToScene(viewport_rect.bottomRight())
            center_x = (top_left_scene.x() + bottom_right_scene.x()) / 2
            center_y = (top_left_scene.y() + bottom_right_scene.y()) / 2
            center_scene = QPointF(center_x, center_y)
            self.startPos = event.scenePos()
            self.newCenterPos = center_scene
            self.displacement = self.newCenterPos - self.startPos
            self.editor_graphics_view.setDragMode(QGraphicsView.DragMode.NoDrag)

    def create_branch_on_mouse_release_event(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Finalize the branch creation if its drawing ends in a terminal
        @param event:
        @return:
        """
        mousePos = event.scenePos()
        self.PlugManager.SetSecondConnector(mousePos.x(), mousePos.y())
        self.PlugManager.CreateConnection(self.diagram_scene)
        self.editor_graphics_view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.DisablePreview()
        self.PreviewSketch = False;
        pass

    def set_limits(self, min_x: int, max_x: Union[float, int], min_y: Union[float, int], max_y: int,
                   margin_factor: float = 0.1) -> None:
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
        self.diagram_scene.setSceneRect(QRectF(min_x - mx, min_y - my, w, h))

    def set_boundaries(self, min_x, min_y, width, height):
        """

        :param min_x:
        :param min_y:
        :param width:
        :param height:
        :return:
        """
        # Create the bounding rectangle
        boundaries = QRectF(min_x, min_y, width, height)

        # Fit the view
        self.editor_graphics_view.fitInView(boundaries, Qt.KeepAspectRatio)

    def center_nodes(self, margin_factor: float = 0.1, elements: Union[None, List[Union[Bus, FluidNode]]] = None):
        """
        Center the view in the nodes
        :param margin_factor:
        :param elements:
        :return:
        """

        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize
        if elements is None:
            for item in self.diagram_scene.items():
                if type(item) in [BusGraphicItem, FluidNodeGraphicItem]:
                    x = item.pos().x()
                    y = item.pos().y()

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)
        else:
            for item in self.diagram_scene.items():
                if type(item) in [BusGraphicItem, FluidNodeGraphicItem]:

                    if item.api_object in elements:
                        x = item.pos().x()
                        y = item.pos().y()

                        max_x = max(max_x, x)
                        min_x = min(min_x, x)
                        max_y = max(max_y, y)
                        min_y = min(min_y, y)

        # set the limits of the view
        dx = max_x - min_x
        dy = max_y - min_y
        mx = margin_factor * dx
        my = margin_factor * dy
        h = dy + 2 * my + 80
        w = dx + 2 * mx + 80
        boundaries = QRectF(min_x - mx, min_y - my, w, h)

        self.diagram_scene.setSceneRect(boundaries)
        self.editor_graphics_view.fitInView(boundaries, Qt.KeepAspectRatio)
        self.editor_graphics_view.scale(1.0, 1.0)

    def graphical_search(self, search_text: str):
        """
        Search object in the diagram and center around it
        :param search_text: object name, object code or object idtag
        """
        # Initialize boundaries
        min_x = min_y = max_x = max_y = None

        for key, points_group in self.diagram.data.items():
            for idTag, location in points_group.locations.items():
                if location.api_object is not None:
                    if location.graphic_object is not None:

                        # Check if searchText is in the name, code, or idtag of the api_object
                        if (search_text in location.api_object.name.lower() or
                                search_text in location.api_object.code.lower() or
                                search_text in str(location.api_object.idtag).lower()):

                            # Calculate boundaries
                            left = location.x
                            right = location.x + location.w
                            top = location.y
                            bottom = location.y + location.h

                            if min_x is None or left < min_x:
                                min_x = left
                            if min_y is None or top < min_y:
                                min_y = top
                            if max_x is None or right > max_x:
                                max_x = right
                            if max_y is None or bottom > max_y:
                                max_y = bottom

        # After all matching elements have been processed

        if None not in (min_x, min_y, max_x, max_y):
            # Calculate width and height
            width = max_x - min_x
            height = max_y - min_y

            # Fit the view
            self.set_boundaries(min_x, min_y, width, height)

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
            self.diagram_scene.render(painter)
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
            self.diagram_scene.render(painter)
            painter.end()
        else:
            raise Exception('Extension ' + str(extension) + ' not supported :(')

    def clear(self):
        """
        Clear the schematic
        """
        self.diagram_scene.clear()

    def recolour_mode(self) -> None:
        """
        Change the colour according to the system theme
        :return:
        """

        for key, group in self.diagram.data.items():
            for idtag, location in group.locations.items():
                if location.graphic_object is not None:
                    location.graphic_object.recolour_mode()

    def set_dark_mode(self) -> None:
        """
        Set the dark theme
        :return:
        """
        ACTIVE['color'] = Qt.white
        ACTIVE['text'] = Qt.white
        self.recolour_mode()

    def set_light_mode(self) -> None:
        """
        Set the light theme
        :return:
        """
        ACTIVE['color'] = Qt.black
        ACTIVE['text'] = Qt.black
        self.recolour_mode()

    def get_selected(self) -> List[Tuple[EditableDevice, QGraphicsItem]]:
        """
        Get selection
        :return: List of EditableDevice, QGraphicsItem
        """
        return [(elm.api_object, elm) for elm in self.diagram_scene.selectedItems()]

    def get_selection_api_objects(self) -> List[EditableDevice]:
        """
        Get a list of the API objects from the selection
        :return: List[EditableDevice]
        """
        return [e.api_object for e in self.diagram_scene.selectedItems()]

    def get_boundaries(self):
        """
        Get the graphic representation boundaries
        :return: min_x, max_x, min_y, max_y
        """

        # shrink selection only
        min_x, max_x, min_y, max_y = self.diagram.get_boundaries()

        return min_x, max_x, min_y, max_y




if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = NodeBreakerEditorWidget(circuit=MultiCircuit(),
                                     diagram=NodeBreakerDiagram(),
                                     default_bus_voltage=10.0)

    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
