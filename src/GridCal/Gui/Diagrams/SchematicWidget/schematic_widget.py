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
from warnings import warn
import networkx as nx
import pyproj
from matplotlib import pyplot as plt

from PySide6.QtCore import (Qt, QPoint, QSize, QPointF, QRect, QRectF, QMimeData, QIODevice, QByteArray,
                            QDataStream, QModelIndex)
from PySide6.QtGui import (QIcon, QPixmap, QImage, QPainter, QStandardItemModel, QStandardItem, QColor, QPen,
                           QDragEnterEvent, QDragMoveEvent, QDropEvent, QWheelEvent, QKeyEvent, QMouseEvent,
                           QContextMenuEvent)
from PySide6.QtWidgets import (QGraphicsView, QMessageBox, QGraphicsScene, QGraphicsSceneMouseEvent, QGraphicsItem)
from PySide6.QtSvg import QSvgGenerator

from GridCalEngine.Devices.types import ALL_DEV_TYPES, INJECTION_DEVICE_TYPES, FLUID_TYPES
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.busbar import BusBar
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.Branches.vsc import VSC
from GridCalEngine.Devices.Branches.upfc import UPFC
from GridCalEngine.Devices.Branches.switch import Switch
from GridCalEngine.Devices.Branches.series_reactance import SeriesReactance
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Devices.Branches.transformer3w import Transformer3W, Winding
from GridCalEngine.Devices.Injections.generator import Generator
from GridCalEngine.Devices.Fluid import FluidNode, FluidPath
from GridCalEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from GridCalEngine.Devices.Diagrams.graphic_location import GraphicLocation
from GridCalEngine.enumerations import DeviceType, SimulationTypes
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, Logger
from GridCalEngine.Devices.types import BRANCH_TYPES

from GridCal.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from GridCal.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Substation.cn_graphics import CnGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Substation.busbar_graphics import BusBarGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Fluid.fluid_path_graphics import FluidPathGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics import LineGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.winding_graphics import WindingGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.dc_line_graphics import DcLineGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.transformer2w_graphics import TransformerGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.hvdc_graphics import HvdcGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.vsc_graphics import VscGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.upfc_graphics import UpfcGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.series_reactance_graphics import SeriesReactanceGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.switch_graphics import SwitchGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from GridCal.Gui.Diagrams.SchematicWidget.Branches.transformer3w_graphics import Transformer3WGraphicItem
from GridCal.Gui.Diagrams.SchematicWidget.Injections.generator_graphics import GeneratorGraphicItem
from GridCal.Gui.Diagrams.generic_graphics import ACTIVE
from GridCal.Gui.Diagrams.base_diagram_widget import BaseDiagramWidget
from GridCal.Gui.GeneralDialogues import InputNumberDialogue
import GridCal.Gui.Visualization.visualization as viz
import GridCalEngine.Devices.Diagrams.palettes as palettes
from GridCal.Gui.messages import info_msg, error_msg, warning_msg, yes_no_question

BRANCH_GRAPHICS = Union[
    LineGraphicItem,
    WindingGraphicItem,
    DcLineGraphicItem,
    TransformerGraphicItem,
    HvdcGraphicItem,
    VscGraphicItem,
    UpfcGraphicItem,
    SeriesReactanceGraphicItem,
    SwitchGraphicItem
]

OPTIONAL_PORT = Union[BarTerminalItem, RoundTerminalItem, None]


class SchematicLibraryModel(QStandardItemModel):
    """
    Items model to host the draggable icons
    This is the list of draggable items
    """

    def __init__(self) -> None:
        """
        Items model to host the draggable icons
        """
        QStandardItemModel.__init__(self)

        self.setColumnCount(1)

        self.bus_name = "Bus"
        self.transformer3w_name = "3W-Transformer"
        self.fluid_node_name = "Fluid-node"
        self.cn_name = "Connectivity node"
        self.bb_name = "Bus bar"

        self.add(name=self.bus_name, icon_name="bus_icon")
        self.add(name=self.transformer3w_name, icon_name="transformer3w")
        self.add(name=self.fluid_node_name, icon_name="dam")
        self.add(name=self.cn_name, icon_name="cn_icon")
        self.add(name=self.bb_name, icon_name="bus_bar_icon")

    def add(self, name: str, icon_name: str):
        """
        Add element to the library
        :param name: Name of the element
        :param icon_name: Icon name, the path is taken care of
        :return:
        """
        _icon = QIcon()
        _icon.addPixmap(QPixmap(f":/Icons/icons/{icon_name}.svg"))
        _item = QStandardItem(_icon, name)
        _item.setToolTip(f"Drag & drop {name} into the schematic")
        self.appendRow(_item)

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
        """

        :return:
        """
        return self.to_bytes_array(self.bus_name)

    def get_3w_transformer_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(self.transformer3w_name)

    def get_fluid_node_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(self.fluid_node_name)

    def get_connectivity_node_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(self.cn_name)

    def get_bus_bar_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(self.bb_name)

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

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """
        
        :param index: 
        :return: 
        """
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled


class SchematicScene(QGraphicsScene):
    """
    SchematicScene
    This class is needed to augment the mouse move and release events
    """

    def __init__(self, parent: "SchematicWidget"):
        """

        :param parent:
        """
        super(SchematicScene, self).__init__(parent)
        self.parent_ = parent
        self.displacement = QPoint(0, 0)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """
        self.parent_.scene_mouse_move_event(event)

        # call the parent event
        super(SchematicScene, self).mouseMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        :param event:
        :return:
        """
        self.parent_.scene_mouse_press_event(event)
        self.displacement = QPointF(0, 0)
        super(SchematicScene, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """
        self.parent_.create_branch_on_mouse_release_event(event)

        # call mouseReleaseEvent on "me" (conti
        #
        # nue with the rest of the actions)
        super(SchematicScene, self).mouseReleaseEvent(event)

    # def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
    #     """
    #
    #     :param event:
    #     :return:
    #     """
    #     super().contextMenuEvent(event)
    #
    #     context_menu = QMenu()
    #
    #     add_menu_entry(menu=context_menu,
    #                    text="Center",
    #                    icon_path=":/Icons/icons/resize.svg",
    #                    function_ptr=lambda x: self.parent_.align_schematic())
    #
    #     add_menu_entry(menu=context_menu,
    #                    text="Expand",
    #                    icon_path=":/Icons/icons/plus (gray).svg",
    #                    function_ptr=lambda x: self.parent_.expand_node_distances())
    #
    #     add_menu_entry(menu=context_menu,
    #                    text="Contract",
    #                    icon_path=":/Icons/icons/minus (gray).svg",
    #                    function_ptr=lambda x: self.parent_.shrink_node_distances())
    #
    #     add_menu_entry(menu=context_menu,
    #                    text="Auto-layout",
    #                    icon_path=":/Icons/icons/automatic_layout.svg",
    #                    function_ptr=lambda x: self.parent_.auto_layout(sel=""))
    #
    #     add_menu_entry(menu=context_menu,
    #                    text="Layout from (lat, lon) data",
    #                    icon_path=":/Icons/icons/map.svg",
    #                    function_ptr=lambda x: self.parent_.fill_xy_from_lat_lon())
    #
    #     add_menu_entry(menu=context_menu,
    #                    text="Zoom in",
    #                    icon_path=":/Icons/icons/zoom_in.svg",
    #                    function_ptr=lambda x: self.parent_.zoom_in())
    #
    #     add_menu_entry(menu=context_menu,
    #                    text="Zoom out",
    #                    icon_path=":/Icons/icons/zoom_out.svg",
    #                    function_ptr=lambda x: self.parent_.zoom_out())
    #
    #     add_menu_entry(menu=context_menu,
    #                    text="Clear highlight",
    #                    icon_path=":/Icons/icons/bus_icon.svg",
    #                    function_ptr=lambda x: self.parent_.clear_big_bus_markers())
    #
    #     # launch the menu
    #     context_menu.exec(event.screenPos())


class CustomGraphicsView(QGraphicsView):
    """
    CustomGraphicsView to handle the panning of the grid
    """

    def __init__(self, scene: QGraphicsScene, parent: "SchematicWidget"):
        """
        Constructor
        :param scene: QGraphicsScene
        """
        super().__init__(scene)
        self._parent = parent
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)

        self.drag_mode = QGraphicsView.DragMode.RubberBandDrag

        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.setMouseTracking(True)
        self.setInteractive(True)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setAlignment(Qt.AlignCenter)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Mouse press event
        :param event: QMouseEvent
        """

        # By pressing ctrl while dragging, we can move the grid
        if event.modifiers() & Qt.ControlModifier:
            self.drag_mode = QGraphicsView.DragMode.ScrollHandDrag
        else:
            self.drag_mode = QGraphicsView.DragMode.RubberBandDrag

        self.setDragMode(self.drag_mode)

        # process the rest of the events
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """

        :param event:
        :return:
        """
        super().contextMenuEvent(event)

        # Get the position of the mouse during the event
        # pos = event.pos()
        #
        # # Check if there's any child widget at the mouse position
        # child_widget = self.childAt(pos)
        # a = self.childAt(event.globalPos())
        # b = child_widget == self
        # # If there's a child widget, do not show the custom context menu
        # if isinstance(child_widget, QWidget):
        #     return
        #
        # context_menu = QMenu()
        #
        # add_menu_entry(menu=context_menu,
        #                text="Center",
        #                icon_path=":/Icons/icons/resize.svg",
        #                function_ptr=lambda x: self.parent_.align_schematic())
        #
        # add_menu_entry(menu=context_menu,
        #                text="Expand",
        #                icon_path=":/Icons/icons/plus (gray).svg",
        #                function_ptr=lambda x: self.parent_.expand_node_distances())
        #
        # add_menu_entry(menu=context_menu,
        #                text="Contract",
        #                icon_path=":/Icons/icons/minus (gray).svg",
        #                function_ptr=lambda x: self.parent_.shrink_node_distances())
        #
        # add_menu_entry(menu=context_menu,
        #                text="Auto-layout",
        #                icon_path=":/Icons/icons/automatic_layout.svg",
        #                function_ptr=lambda x: self.parent_.auto_layout(sel=""))
        #
        # add_menu_entry(menu=context_menu,
        #                text="Layout from (lat, lon) data",
        #                icon_path=":/Icons/icons/map.svg",
        #                function_ptr=lambda x: self.parent_.fill_xy_from_lat_lon())
        #
        # add_menu_entry(menu=context_menu,
        #                text="Zoom in",
        #                icon_path=":/Icons/icons/zoom_in.svg",
        #                function_ptr=lambda x: self.parent_.zoom_in())
        #
        # add_menu_entry(menu=context_menu,
        #                text="Zoom out",
        #                icon_path=":/Icons/icons/zoom_out.svg",
        #                function_ptr=lambda x: self.parent_.zoom_out())
        #
        # add_menu_entry(menu=context_menu,
        #                text="Clear highlight",
        #                icon_path=":/Icons/icons/bus_icon.svg",
        #                function_ptr=lambda x: self.parent_.clear_big_bus_markers())
        #
        # # launch the menu
        # context_menu.exec(event.globalPos())


# def find_my_node(idtag_: str,
#                  bus_dict: Dict[str, BusGraphicItem],
#                  fluid_node_dict: Dict[str, FluidNodeGraphicItem]):
#     """
#     Function to look for the bus or fluid node
#     :param idtag_: bus or fluidnode idtag
#     :param bus_dict:
#     :param fluid_node_dict:
#     :return: Matching graphic object
#     """
#     graphic_obj = bus_dict.get(idtag_, None)
#     if graphic_obj is None:
#         graphic_obj = fluid_node_dict.get(idtag_, None)
#     return graphic_obj


class SchematicWidget(BaseDiagramWidget):
    """
    This is the bus-branch editor

    Structure:

    {SchematicWidget: BaseDiagramWidget}
     |
      - .editor_graphics_view {QGraphicsView} (Handles the drag and drop)
     |
      - .diagram_scene {SchematicScene: QGraphicsScene}
     |
      - .circuit {MultiCircuit} (Calculation engine)
     |
      - .diagram {SchematicDiagram} records the DB objects and their position to load and save diagrams
     |
      - .graphics_manager {GraphicsManager} records the DB objects and their diagram widgets

    The graphic objects need to call the API objects and functions inside the MultiCircuit instance.
    To do this the graphic objects call "parent.circuit.<function or object>"
    """

    def __init__(self,
                 circuit: MultiCircuit,
                 diagram: Union[SchematicDiagram, None],
                 default_bus_voltage: float = 10.0,
                 time_index: Union[None, int] = None,
                 prefer_node_breaker: bool = False,
                 call_delete_db_element_func: Callable[["SchematicWidget", ALL_DEV_TYPES], None] = None):
        """
        Creates the Diagram Editor (DiagramEditorWidget)
        :param circuit: Circuit that is handling
        :param diagram: SchematicDiagram to use (optional)
        :param default_bus_voltage: Default bus voltages (kV)
        :param time_index: time index to represent
        :param prefer_node_breaker: Preffer the node breaker representation?
        """

        BaseDiagramWidget.__init__(self,
                                   circuit=circuit,
                                   diagram=diagram,
                                   library_model=SchematicLibraryModel(),
                                   time_index=time_index,
                                   call_delete_db_element_func=call_delete_db_element_func)

        # create all the schematic objects and replace the existing ones
        self.diagram_scene = SchematicScene(parent=self)  # scene to add to the QGraphicsView

        # add the actual editor
        self.editor_graphics_view = CustomGraphicsView(self.diagram_scene, parent=self)

        # override events
        self.editor_graphics_view.dragEnterEvent = self.graphicsDragEnterEvent
        self.editor_graphics_view.dragMoveEvent = self.graphicsDragMoveEvent
        self.editor_graphics_view.dropEvent = self.graphicsDropEvent
        self.editor_graphics_view.wheelEvent = self.graphicsWheelEvent
        self.editor_graphics_view.keyPressEvent = self.graphicsKeyPressEvent

        self.addWidget(self.editor_graphics_view)
        self.setStretchFactor(0, 0)
        self.setStretchFactor(1, 2000)

        # default_bus_voltage (kV)
        self.default_bus_voltage = default_bus_voltage

        # Preffer the node breaker representation?
        self.prefer_node_breaker: bool = prefer_node_breaker

        # nodes distance "explosion" factor
        self.expand_factor = 1.1

        # Zoom indicator
        self._zoom = 0

        # line drawing vars
        self.started_branch: Union[LineGraphicTemplateItem, None] = None
        self.setMouseTracking(True)
        self.startPos = QPoint()
        self.newCenterPos = QPoint()
        self.displacement = QPoint()
        self.startPos: Union[QPoint, None] = None

        # for vecinity diagram porpuses
        self.root_bus: Union[Bus, None] = None

        # for graphics dev porpuses
        # self.pos_label = QGraphicsTextItem()
        # self.add_to_scene(self.pos_label)

        if diagram is not None:
            self.draw()

        # -------------------------------------------------------------------------------------------------
        # Note: Do not declare any variable beyond here, as it may bnot be considered if draw is called :/

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

            point0 = self.editor_graphics_view.mapToScene(event.position().x(), event.position().y())
            x0 = point0.x()
            y0 = point0.y()

            if obj_type == self.library_model.get_bus_mime_data():
                obj = Bus(name=f'Bus {self.circuit.get_bus_number()}', Vnom=self.default_bus_voltage)
                graphic_object = BusGraphicItem(editor=self, bus=obj, x=x0, y=y0, h=20, w=80)
                self.circuit.add_bus(obj=obj)

            elif obj_type == self.library_model.get_3w_transformer_mime_data():
                obj = Transformer3W(name=f"Transformer 3W {len(self.circuit.transformers3w)}")
                graphic_object = self.create_transformer_3w_graphics(elm=obj, x=x0, y=y0)
                self.circuit.add_transformer3w(obj)

            elif obj_type == self.library_model.get_fluid_node_mime_data():
                obj = FluidNode(name=f"Fluid node {self.circuit.get_fluid_nodes_number()}")
                graphic_object = self.create_fluid_node_graphics(node=obj, x=x0, y=y0, h=20, w=80)
                self.circuit.add_fluid_node(obj)

            elif obj_type == self.library_model.get_connectivity_node_mime_data():
                obj = ConnectivityNode(name=f"CN {len(self.circuit.get_connectivity_nodes())}")
                graphic_object = self.create_connectivity_node_graphics(node=obj, x=x0, y=y0, h=40, w=40)
                self.circuit.add_connectivity_node(obj)

            elif obj_type == self.library_model.get_bus_bar_mime_data():
                obj = BusBar(name=f"Bus bar {self.circuit.get_bus_bars_number()}")
                graphic_object = self.create_bus_bar_graphics(node=obj, x=x0, y=y0, h=20, w=80)
                self.circuit.add_bus_bar(obj)

            else:
                # unrecognized drop
                return

            # add to the scene
            self.add_to_scene(graphic_object=graphic_object)

            # add to the diagram list
            self.update_diagram_element(device=obj,
                                        x=x0,
                                        y=y0,
                                        w=graphic_object.w,
                                        h=graphic_object.h,
                                        r=0,
                                        draw_labels=graphic_object.draw_labels,
                                        graphic_object=graphic_object)

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
            self.delete_Selected_from_widget_and_db()

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

    def create_bus_graphics(self, bus: Bus, x: int, y: int, h: int, w: int,
                            draw_labels: bool = True) -> BusGraphicItem:
        """
        create the Bus graphics
        :param bus: GridCal Bus object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :param draw_labels: Draw labels?
        :return: BusGraphicItem
        """

        graphic_object = BusGraphicItem(editor=self,
                                        bus=bus,
                                        x=x,
                                        y=y,
                                        h=h,
                                        w=w,
                                        draw_labels=draw_labels)
        return graphic_object

    def create_transformer_3w_graphics(self, elm: Transformer3W, x: int, y: int) -> Transformer3WGraphicItem:
        """
        Add Transformer3W to the graphics
        :param elm: Transformer3W
        :param x: x coordinate
        :param y: y coordinate
        :return: Transformer3WGraphicItem
        """
        graphic_object = Transformer3WGraphicItem(editor=self, elm=elm)
        graphic_object.setPos(QPoint(x, y))
        return graphic_object

    def create_fluid_node_graphics(self, node: FluidNode, x: int, y: int, h: int, w: int,
                                   draw_labels: bool = True) -> FluidNodeGraphicItem:
        """
        Add fluid node to graphics
        :param node: GridCal FluidNode object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :param draw_labels: Draw labels?
        :return: FluidNodeGraphicItem
        """

        graphic_object = FluidNodeGraphicItem(editor=self, fluid_node=node, x=x, y=y, h=h, w=w,
                                              draw_labels=draw_labels)
        return graphic_object

    def create_connectivity_node_graphics(self, node: ConnectivityNode,
                                          x: int, y: int, h: int, w: int,
                                          draw_labels: bool = True) -> CnGraphicItem:
        """
        Add connectivity node to graphics
        :param node: GridCal connectivity node object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :param draw_labels: Draw labels?
        :return: CnGraphicItem
        """

        graphic_object = CnGraphicItem(editor=self, node=node, x=x, y=y, h=h, w=w,
                                       draw_labels=draw_labels)
        return graphic_object

    def create_bus_bar_graphics(self, node: BusBar,
                                x: int, y: int, h: int, w: int,
                                draw_labels: bool = True) -> BusBarGraphicItem:
        """
        Add bus bar node to graphics
        :param node: GridCal BusBar object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :param draw_labels: Draw labels?
        :return: BusBarGraphicItem
        """

        graphic_object = BusBarGraphicItem(editor=self, busbar=node, x=x, y=y, h=h, w=w,
                                           draw_labels=draw_labels)
        return graphic_object

    def draw_additional_diagram(self,
                                diagram: SchematicDiagram,
                                prefer_node_breaker: bool = False,
                                logger: Logger = Logger()) -> None:
        """
        Draw a new diagram
        :param diagram: SchematicDiagram
        :param prefer_node_breaker:
        :param logger: Logger
        """
        inj_dev_by_bus = self.circuit.get_injection_devices_grouped_by_bus()
        inj_dev_by_fluid_node = self.circuit.get_injection_devices_grouped_by_fluid_node()
        inj_dev_by_cn = self.circuit.get_injection_devices_grouped_by_cn()

        # add node-like elements first
        for category, points_group in diagram.data.items():

            if category == DeviceType.BusDevice.value and not prefer_node_breaker:

                for idtag, location in points_group.locations.items():

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is None:
                        # add the graphic object to the diagram view
                        graphic_object = self.create_bus_graphics(bus=location.api_object,
                                                                  x=location.x,
                                                                  y=location.y,
                                                                  h=location.h,
                                                                  w=location.w,
                                                                  draw_labels=location.draw_labels)
                        self.add_to_scene(graphic_object=graphic_object)

                        # create the bus children
                        graphic_object.create_children_widgets(
                            injections_by_tpe=inj_dev_by_bus.get(location.api_object, dict())
                        )

                        graphic_object.change_size(w=location.w)

                        # add buses reference for later
                        # bus_dict[idtag] = graphic_object
                        self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.Transformer3WDevice.value:

                for idtag, location in points_group.locations.items():

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is None:
                        elm: Transformer3W = location.api_object

                        graphic_object = self.create_transformer_3w_graphics(elm=elm,
                                                                             x=location.x,
                                                                             y=location.y)
                        self.add_to_scene(graphic_object=graphic_object)

                        bus_1_graphic = self.graphics_manager.query(elm.bus1)
                        bus_2_graphic = self.graphics_manager.query(elm.bus2)
                        bus_3_graphic = self.graphics_manager.query(elm.bus3)

                        conn1 = WindingGraphicItem(from_port=graphic_object.terminals[0],
                                                   to_port=bus_1_graphic.get_terminal(),
                                                   editor=self)

                        graphic_object.set_connection(i=0, bus=elm.bus1, conn=conn1)

                        conn2 = WindingGraphicItem(from_port=graphic_object.terminals[1],
                                                   to_port=bus_2_graphic.get_terminal(),
                                                   editor=self)
                        graphic_object.set_connection(i=1, bus=elm.bus2, conn=conn2)

                        conn3 = WindingGraphicItem(from_port=graphic_object.terminals[2],
                                                   to_port=bus_3_graphic.get_terminal(),
                                                   editor=self)
                        graphic_object.set_connection(i=2, bus=elm.bus3, conn=conn3)

                        graphic_object.set_position(x=location.x, y=location.y)
                        graphic_object.change_size(h=location.h, w=location.w)

                        self.add_to_scene(graphic_object=conn1)
                        self.add_to_scene(graphic_object=conn2)
                        self.add_to_scene(graphic_object=conn3)

                        graphic_object.update_conn()
                        self.graphics_manager.add_device(elm=elm, graphic=graphic_object)
                        self.graphics_manager.add_device(elm=elm.winding1, graphic=conn1)
                        self.graphics_manager.add_device(elm=elm.winding2, graphic=conn2)
                        self.graphics_manager.add_device(elm=elm.winding3, graphic=conn3)

                        # register the windings for the branches pass
                        # windings_dict[elm.winding1.idtag] = conn1
                        # windings_dict[elm.winding2.idtag] = conn2
                        # windings_dict[elm.winding3.idtag] = conn3

            elif category == DeviceType.FluidNodeDevice.value:

                for idtag, location in points_group.locations.items():

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is None:
                        # add the graphic object to the diagram view
                        graphic_object = self.create_fluid_node_graphics(node=location.api_object,
                                                                         x=location.x,
                                                                         y=location.y,
                                                                         h=location.h,
                                                                         w=location.w,
                                                                         draw_labels=location.draw_labels)
                        self.add_to_scene(graphic_object=graphic_object)

                        # create the bus children
                        graphic_object.create_children_widgets(
                            injections_by_tpe=inj_dev_by_fluid_node.get(location.api_object, dict()))

                        graphic_object.change_size(h=location.h,
                                                   w=location.w)

                        # add fluid node reference for later
                        # fluid_node_dict[idtag] = graphic_object
                        self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)
                        if location.api_object.bus is not None:
                            self.graphics_manager.add_device(elm=location.api_object.bus, graphic=graphic_object)

                        # map the internal bus
                        # if location.api_object.bus is not None:
                        #     bus_dict[location.api_object.bus.idtag] = graphic_object

            elif category == DeviceType.ConnectivityNodeDevice.value and prefer_node_breaker:

                for idtag, location in points_group.locations.items():

                    if not location.api_object.internal:
                        # search for the api object, because it may be created already
                        graphic_object = self.graphics_manager.query(elm=location.api_object)

                        if graphic_object is None:
                            # add the graphic object to the diagram view
                            graphic_object = self.create_connectivity_node_graphics(node=location.api_object,
                                                                                    x=location.x,
                                                                                    y=location.y,
                                                                                    h=location.h,
                                                                                    w=location.w,
                                                                                    draw_labels=location.draw_labels)
                            self.add_to_scene(graphic_object=graphic_object)

                            # create the bus children
                            graphic_object.create_children_widgets(
                                injections_by_tpe=inj_dev_by_cn.get(location.api_object, dict())
                            )

                            # graphic_object.change_size(w=location.w)

                            # add buses reference for later
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.BusBarDevice.value and prefer_node_breaker:

                for idtag, location in points_group.locations.items():

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is None:
                        # add the graphic object to the diagram view
                        graphic_object = self.create_bus_bar_graphics(node=location.api_object,
                                                                      x=location.x,
                                                                      y=location.y,
                                                                      h=location.h,
                                                                      w=location.w,
                                                                      draw_labels=location.draw_labels)
                        self.add_to_scene(graphic_object=graphic_object)

                        # create the bus children
                        graphic_object.create_children_widgets(
                            injections_by_tpe=inj_dev_by_cn.get(graphic_object.api_object.cn, dict())
                        )

                        graphic_object.change_size(w=location.w)

                        # add buses reference for later
                        self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            else:
                # pass for now...
                pass

        # add the rest of the branches
        for category, points_group in diagram.data.items():

            if category == DeviceType.LineDevice.value:

                for idtag, location in points_group.locations.items():
                    self.add_api_line(branch=location.api_object,
                                      draw_labels=location.draw_labels,
                                      prefer_node_breaker=prefer_node_breaker,
                                      logger=logger)

            elif category == DeviceType.DCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    self.add_api_dc_line(branch=location.api_object,
                                         draw_labels=location.draw_labels,
                                         prefer_node_breaker=prefer_node_breaker,
                                         logger=logger)

            elif category == DeviceType.HVDCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    self.add_api_hvdc(branch=location.api_object,
                                      draw_labels=location.draw_labels,
                                      prefer_node_breaker=prefer_node_breaker,
                                      logger=logger)

            elif category == DeviceType.VscDevice.value:

                for idtag, location in points_group.locations.items():
                    self.add_api_vsc(branch=location.api_object,
                                     draw_labels=location.draw_labels,
                                     prefer_node_breaker=prefer_node_breaker,
                                     logger=logger)

            elif category == DeviceType.UpfcDevice.value:

                for idtag, location in points_group.locations.items():
                    self.add_api_upfc(branch=location.api_object,
                                      draw_labels=location.draw_labels,
                                      prefer_node_breaker=prefer_node_breaker,
                                      logger=logger)

            elif category == DeviceType.Transformer2WDevice.value:

                for idtag, location in points_group.locations.items():
                    self.add_api_transformer(branch=location.api_object,
                                             draw_labels=location.draw_labels,
                                             prefer_node_breaker=prefer_node_breaker,
                                             logger=logger)

            elif category == DeviceType.SeriesReactanceDevice.value:

                for idtag, location in points_group.locations.items():
                    self.add_api_series_reactance(branch=location.api_object,
                                                  draw_labels=location.draw_labels,
                                                  prefer_node_breaker=prefer_node_breaker,
                                                  logger=logger)

            elif category == DeviceType.SwitchDevice.value:

                for idtag, location in points_group.locations.items():
                    self.add_api_switch(branch=location.api_object,
                                        draw_labels=location.draw_labels,
                                        prefer_node_breaker=prefer_node_breaker,
                                        logger=logger)

            elif category == DeviceType.WindingDevice.value:

                for idtag, location in points_group.locations.items():

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is not None:
                        graphic_object.redraw()
                        self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.FluidPathDevice.value:

                for idtag, location in points_group.locations.items():

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is None:

                        from_port, to_port = self.find_ports(branch=location.api_object,
                                                             prefer_node_breaker=prefer_node_breaker,
                                                             logger=logger)
                        if from_port is not None and to_port is not None:
                            graphic_object = FluidPathGraphicItem(from_port=from_port,
                                                                  to_port=to_port,
                                                                  editor=self,
                                                                  api_object=location.api_object,
                                                                  draw_labels=location.draw_labels)
                            self.add_to_scene(graphic_object=graphic_object)

                            graphic_object.redraw()
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            else:
                pass
                # print('draw: Unrecognized category: {}'.format(category))

        # last pass: arrange children
        for category in [DeviceType.BusDevice, DeviceType.FluidNodeDevice]:
            graphics_dict = self.graphics_manager.get_device_type_dict(device_type=category)
            for idtag, graphic in graphics_dict.items():
                graphic.arrange_children()

    def draw(self) -> None:
        """
        Draw the stored diagram
        """
        self.draw_additional_diagram(diagram=self.diagram,
                                     prefer_node_breaker=self.prefer_node_breaker,
                                     logger=self.logger)

    def expand_diagram_from_bus(self, root_bus: Bus) -> None:
        """
        Expand the diagram from one bus
        :param root_bus: Root bus to expand from
        """
        extra_diagram = make_vecinity_diagram(circuit=self.circuit,
                                              root_bus=root_bus,
                                              max_level=1)

        self.draw_additional_diagram(diagram=extra_diagram,
                                     prefer_node_breaker=self.prefer_node_breaker,
                                     logger=self.logger)

    def update_diagram_element(self, device: ALL_DEV_TYPES,
                               x: int = 0, y: int = 0, w: int = 0, h: int = 0, r: float = 0,
                               draw_labels: bool = True,
                               graphic_object: QGraphicsItem = None) -> None:
        """
        Set the position of a device in the diagram
        :param device: EditableDevice
        :param x: x position (px)
        :param y: y position (px)
        :param h: height (px)
        :param w: width (px)
        :param r: rotation (deg)
        :param draw_labels: Draw the labels?
        :param graphic_object: Graphic object associated
        """
        self.diagram.set_point(device=device,
                               location=GraphicLocation(x=x,
                                                        y=y,
                                                        h=h,
                                                        w=w,
                                                        r=r,
                                                        draw_labels=draw_labels,
                                                        api_object=device))

        self.graphics_manager.add_device(elm=device, graphic=graphic_object)

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
        if graphic_object is not None:
            if graphic_object.scene() is not None:

                # try to remove nexus and children
                if isinstance(graphic_object,
                              (BusGraphicItem, CnGraphicItem, BusBarGraphicItem, FluidNodeGraphicItem)):
                    graphic_object.delete_all_connections()
                    for g in graphic_object.shunt_children:
                        self.diagram_scene.removeItem(g.nexus)

                self.diagram_scene.removeItem(graphic_object)
            else:
                warn(f"Null scene for {graphic_object}, was it deleted already?")

    def delete_diagram_element(self, device: ALL_DEV_TYPES, propagate: bool = True) -> None:
        """
        Delete device from the diagram registry
        :param device: EditableDevice
        :param propagate: Propagate the delete to other diagrams?
        """
        self.diagram.delete_device(device=device)
        graphic_object: QGraphicsItem = self.graphics_manager.delete_device(device=device)

        if graphic_object is not None:
            self.remove_from_scene(graphic_object)

        if propagate:
            if self.call_delete_db_element_func is not None:
                self.call_delete_db_element_func(self, device)

    def remove_element(self,
                       device: ALL_DEV_TYPES,
                       graphic_object: Union[QGraphicsItem, None] = None,
                       delete_from_db: bool = False) -> None:
        """
        Remove device from the diagram and the database
        :param device: EditableDevice
        :param graphic_object: optionally provide the graphics object associated
        :param delete_from_db: Delete the element also from the database?
        """

        if device is not None:
            self.delete_diagram_element(device=device, propagate=delete_from_db)

            if delete_from_db:
                try:
                    self.circuit.delete_element(obj=device)
                except ValueError as e:
                    print("SchamaticWidget.remove_element", e)

        elif graphic_object is not None:
            self.remove_from_scene(graphic_object)
        else:
            warn(f"Graphic object {graphic_object} and device {device} are none")

        self.object_editor_table.setModel(None)

    def delete_diagram_elements(self, elements: List[ALL_DEV_TYPES]):
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
            graphic_object = self.graphics_manager.query(bus)
            if isinstance(graphic_object, BusGraphicItem):
                graphic_object.setSelected(True)

    def get_selected_buses(self) -> List[Tuple[int, Bus, BusGraphicItem]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, Bus, Union[BusGraphicItem, None]]] = list()
        bus_graphic_dict = self.graphics_manager.get_device_type_dict(DeviceType.BusDevice)

        bus_dict: Dict[str: Tuple[int, Bus]] = {b.idtag: (i, b) for i, b in enumerate(self.circuit.get_buses())}

        for idtag, graphic_object in bus_graphic_dict.items():
            if isinstance(graphic_object, BusGraphicItem):
                if graphic_object.isSelected():
                    idx, bus = bus_dict[idtag]
                    lst.append((idx, bus, graphic_object))
        return lst

    def get_selected_cn(self) -> List[Tuple[int, ConnectivityNode, CnGraphicItem]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, ConnectivityNode, Union[CnGraphicItem, None]]] = list()
        cn_graphic_dict = self.graphics_manager.get_device_type_dict(DeviceType.ConnectivityNodeDevice)

        cn_dict: Dict[str: Tuple[int, ConnectivityNode]] = {b.idtag: (i, b)
                                                            for i, b in
                                                            enumerate(self.circuit.get_connectivity_nodes())}

        for idtag, graphic_object in cn_graphic_dict.items():
            if isinstance(graphic_object, CnGraphicItem):
                if graphic_object.isSelected():
                    idx, bus = cn_dict[idtag]
                    lst.append((idx, bus, graphic_object))
        return lst

    def delete_Selected_from_widget_and_db(self) -> None:
        """
        Delete the selected items from the diagram
        """
        # get the selected buses
        selected = self.get_selected()

        if len(selected) > 0:
            reply = QMessageBox.question(self, 'Delete objects from the diagram and the DB',
                                         'Are you sure that you want to delete the selected elements?',
                                         QMessageBox.StandardButton.Yes,
                                         QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes.value:

                # remove the buses (from the schematic and the circuit)
                for bus, graphic_obj in selected:
                    self.remove_element(device=bus, graphic_object=graphic_obj, delete_from_db=True)
            else:
                pass
        else:
            info_msg('Choose some elements from the schematic', 'Delete')

    def delete_Selected_from_widget(self) -> None:
        """
        Delete the selected items from the diagram
        """
        # get the selected buses
        selected = self.get_selected()

        if len(selected) > 0:
            reply = QMessageBox.question(self, 'Delete objects from the diagram',
                                         'Are you sure that you want to delete the selected elements?',
                                         QMessageBox.StandardButton.Yes,
                                         QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes.value:

                # remove the buses (from the schematic and the circuit)
                for bus, graphic_obj in selected:
                    self.remove_element(device=bus, graphic_object=graphic_obj, delete_from_db=False)
            else:
                pass
        else:
            info_msg('Choose some elements from the schematic', 'Delete')

    def get_buses(self) -> List[Tuple[int, Bus, BusGraphicItem]]:
        """
        Get all the buses
        :return: tuple(bus index, bus_api_object, bus_graphic_object)
        """
        lst: List[Tuple[int, Bus, Union[BusGraphicItem, None]]] = list()
        bus_graphics_dict = self.graphics_manager.get_device_type_dict(DeviceType.BusDevice)
        bus_dict: Dict[str: Tuple[int, Bus]] = {b.idtag: (i, b) for i, b in enumerate(self.circuit.get_buses())}

        for bus_idtag, graphic_object in bus_graphics_dict.items():
            idx, bus = bus_dict[bus_idtag]
            lst.append((idx, bus, graphic_object))

        return lst

    def start_connection(self, port: Union[BarTerminalItem, RoundTerminalItem]) -> LineGraphicTemplateItem:
        """
        Start the branch creation
        @param port:
        @return:
        """
        self.started_branch = LineGraphicTemplateItem(from_port=port,
                                                      to_port=None,
                                                      editor=self)
        self.add_to_scene(self.started_branch)

        port.setZValue(0)

        return self.started_branch

    def scene_mouse_move_event(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """
        if self.started_branch:
            pos = event.scenePos()
            self.started_branch.setEndPos(pos)

        # for graphics dev porpuses
        # self.pos_label.setPlainText(f"{event.scenePos().x()}, {event.scenePos().y()}")

    def scene_mouse_press_event(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        :param event:
        :return:
        """
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

    def create_line(self,
                    from_port: BarTerminalItem,
                    to_port: BarTerminalItem,
                    bus_from: Union[None, Bus] = None,
                    bus_to: Union[None, Bus] = None,
                    cn_from: Union[None, ConnectivityNode] = None,
                    cn_to: Union[None, ConnectivityNode] = None):
        """

        :param from_port:
        :param to_port:
        :param bus_from:
        :param bus_to:
        :param cn_from:
        :param cn_to:
        :return:
        """
        name = 'Line ' + str(len(self.circuit.lines) + 1)
        obj = Line(bus_from=bus_from,
                   bus_to=bus_to,
                   cn_from=cn_from,
                   cn_to=cn_to,
                   name=name)

        graphic_object = LineGraphicItem(from_port=from_port,
                                         to_port=to_port,
                                         editor=self,
                                         api_object=obj)

        self.add_to_scene(graphic_object=graphic_object)

        self.update_diagram_element(device=obj,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        # add the new object to the circuit
        self.circuit.add_line(obj)

        # update the connection placement
        graphic_object.update_ports()

        # set the connection placement
        graphic_object.setZValue(-1)

    def create_dc_line(self, bus_from: Bus, bus_to: Bus, from_port: BarTerminalItem, to_port: BarTerminalItem):
        """

        :param bus_from:
        :param bus_to:
        :param from_port:
        :param to_port:
        :return:
        """
        name = 'Dc line ' + str(len(self.circuit.dc_lines) + 1)
        obj = DcLine(bus_from=bus_from,
                     bus_to=bus_to,
                     name=name)

        graphic_object = DcLineGraphicItem(from_port=from_port,
                                           to_port=to_port,
                                           editor=self,
                                           api_object=obj)

        self.add_to_scene(graphic_object=graphic_object)

        self.update_diagram_element(device=obj,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        # add the new object to the circuit
        self.circuit.add_dc_line(obj)

        # update the connection placement
        graphic_object.update_ports()

        # set the connection placement
        graphic_object.setZValue(-1)

    def create_winding(self, from_port: BarTerminalItem, to_port: BarTerminalItem, api_object: Winding):
        """

        :param from_port:
        :param to_port:
        :param api_object:
        :return:
        """

        winding_graphics = WindingGraphicItem(from_port=from_port,
                                              to_port=to_port,
                                              editor=self,
                                              api_object=api_object)

        self.add_to_scene(graphic_object=winding_graphics)

        self.update_diagram_element(device=winding_graphics.api_object,
                                    draw_labels=winding_graphics.draw_labels,
                                    graphic_object=winding_graphics)

        self.started_branch.update_ports()

        # set the connection placement
        winding_graphics.setZValue(-1)

        return winding_graphics

    def create_transformer(self, bus_from: Bus, bus_to: Bus, from_port: BarTerminalItem, to_port: BarTerminalItem):
        """

        :param bus_from:
        :param bus_to:
        :param from_port:
        :param to_port:
        :return:
        """
        name = 'Transformer ' + str(len(self.circuit.transformers2w) + 1)
        obj = Transformer2W(bus_from=bus_from,
                            bus_to=bus_to,
                            name=name)

        graphic_object = TransformerGraphicItem(from_port=from_port,
                                                to_port=to_port,
                                                editor=self,
                                                api_object=obj)

        self.add_to_scene(graphic_object=graphic_object)

        self.update_diagram_element(device=obj,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        # add the new object to the circuit
        self.circuit.add_transformer2w(obj)

        # update the connection placement
        graphic_object.update_ports()

        # set the connection placement
        graphic_object.setZValue(-1)

    def create_vsc(self, bus_from: Bus, bus_to: Bus, from_port: BarTerminalItem, to_port: BarTerminalItem):
        """

        :param bus_from:
        :param bus_to:
        :param from_port:
        :param to_port:
        :return:
        """
        name = 'VSC ' + str(len(self.circuit.vsc_devices) + 1)
        obj = VSC(bus_from=bus_from,
                  bus_to=bus_to,
                  name=name)

        graphic_object = VscGraphicItem(from_port=from_port,
                                        to_port=to_port,
                                        editor=self,
                                        api_object=obj)

        self.add_to_scene(graphic_object=graphic_object)

        self.update_diagram_element(device=obj,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        # add the new object to the circuit
        self.circuit.add_vsc(obj)

        # update the connection placement
        graphic_object.update_ports()

        # set the connection placement
        graphic_object.setZValue(-1)

    def create_fluid_path(self, source: FluidNode, target: FluidNode, from_port: BarTerminalItem,
                          to_port: BarTerminalItem):
        """

        :param source:
        :param target:
        :param from_port:
        :param to_port:
        :return:
        """
        name = 'FluidPath ' + str(len(self.circuit.fluid_paths) + 1)
        obj = FluidPath(source=source,
                        target=target,
                        name=name)

        graphic_object = FluidPathGraphicItem(from_port=from_port,
                                              to_port=to_port,
                                              editor=self,
                                              api_object=obj)

        self.add_to_scene(graphic_object=graphic_object)

        self.update_diagram_element(device=obj,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        # update the connection placement
        graphic_object.update_ports()

        # set the connection placement
        graphic_object.setZValue(-1)

        self.circuit.add_fluid_path(obj=obj)

    def create_branch_on_mouse_release_event(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Finalize the branch creation if its drawing ends in a terminal
        @param event:
        @return:
        """

        # Clear or finnish the started connection:
        if self.started_branch is not None:

            items = self.diagram_scene.items(event.scenePos())  # get the widgets at the mouse position

            for arriving_widget in items:
                if isinstance(arriving_widget,
                              Union[BarTerminalItem, RoundTerminalItem]):  # arrivinf to a bus or bus-bar

                    if arriving_widget.get_parent() is not self.started_branch.get_terminal_from_parent():  # forbid connecting to itself

                        self.started_branch.set_to_port(arriving_widget)

                        if self.started_branch.connected_between_buses():  # electrical branch between electrical buses

                            if self.started_branch.should_be_a_converter():
                                # different DC status -> VSC

                                self.create_vsc(bus_from=self.started_branch.get_bus_from(),
                                                bus_to=self.started_branch.get_bus_to(),
                                                from_port=self.started_branch.get_terminal_from(),
                                                to_port=self.started_branch.get_terminal_to())

                            elif self.started_branch.should_be_a_dc_line():
                                # both buses are DC

                                self.create_dc_line(bus_from=self.started_branch.get_bus_from(),
                                                    bus_to=self.started_branch.get_bus_to(),
                                                    from_port=self.started_branch.get_terminal_from(),
                                                    to_port=self.started_branch.get_terminal_to())

                            elif self.started_branch.should_be_a_transformer():

                                self.create_transformer(bus_from=self.started_branch.get_bus_from(),
                                                        bus_to=self.started_branch.get_bus_to(),
                                                        from_port=self.started_branch.get_terminal_from(),
                                                        to_port=self.started_branch.get_terminal_to())

                            else:

                                self.create_line(bus_from=self.started_branch.get_bus_from(),
                                                 bus_to=self.started_branch.get_bus_to(),
                                                 from_port=self.started_branch.get_terminal_from(),
                                                 to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.conneted_between_tr3_and_bus():

                            tr3_graphic_object: Transformer3WGraphicItem = self.started_branch.get_from_graphic_object()

                            if self.started_branch.is_to_port_a_bus():
                                # if the bus "from" is the TR3W, the "to" is the bus
                                bus = self.started_branch.get_bus_to()
                            else:
                                raise Exception('Nor the from or to connection points are a bus!')

                            i = tr3_graphic_object.get_connection_winding(
                                from_port=self.started_branch.get_terminal_from(),
                                to_port=self.started_branch.get_terminal_to()
                            )

                            if tr3_graphic_object.connection_lines[i] is None:
                                winding = tr3_graphic_object.api_object.get_winding(i)
                                winding_graphics = self.create_winding(
                                    from_port=self.started_branch.get_terminal_from(),
                                    to_port=self.started_branch.get_terminal_to(),
                                    api_object=winding
                                )

                                tr3_graphic_object.set_connection(i, bus, winding_graphics)
                                tr3_graphic_object.update_conn()  # create winding

                        elif self.started_branch.connected_between_bus_and_tr3():

                            tr3_graphic_object = self.started_branch.get_to_graphic_object()

                            if self.started_branch.is_from_port_a_bus():
                                # if the bus "to" is the TR3W, the "from" is the bus
                                bus = self.started_branch.get_bus_from()
                            else:
                                raise Exception('Nor the from or to connection points are a bus!')

                            i = tr3_graphic_object.get_connection_winding(
                                from_port=self.started_branch.get_terminal_from(),
                                to_port=self.started_branch.get_terminal_to()
                            )

                            if tr3_graphic_object.connection_lines[i] is None:
                                winding = tr3_graphic_object.api_object.get_winding(i)
                                winding_graphics = self.create_winding(
                                    from_port=self.started_branch.get_terminal_from(),
                                    to_port=self.started_branch.get_terminal_to(),
                                    api_object=winding)

                                tr3_graphic_object.set_connection(i, bus, winding_graphics)
                                tr3_graphic_object.update_conn()

                        elif self.started_branch.connected_between_fluid_nodes():  # fluid path

                            self.create_fluid_path(source=self.started_branch.get_fluid_node_from(),
                                                   target=self.started_branch.get_fluid_node_to(),
                                                   from_port=self.started_branch.get_terminal_from(),
                                                   to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_fluid_node_and_bus():

                            # electrical bus
                            bus = self.started_branch.get_bus_to()

                            # check if the fluid node has a bus
                            fn = self.started_branch.get_fluid_node_from()

                            if fn.bus is None:
                                # the fluid node does not have a bus, make one
                                fn_bus = Bus(fn.name, Vnom=bus.Vnom)
                                self.circuit.add_bus(fn_bus)
                                fn.bus = fn_bus
                            else:
                                fn_bus = fn.bus

                            self.create_line(bus_from=fn_bus,
                                             bus_to=bus,
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_bus_and_fluid_node():
                            # electrical bus
                            bus = self.started_branch.get_bus_from()

                            # check if the fluid node has a bus
                            fn = self.started_branch.get_fluid_node_to()

                            if fn.bus is None:
                                # the fluid node does not have a bus, make one
                                fn_bus = Bus(fn.name, Vnom=bus.Vnom)
                                self.circuit.add_bus(fn_bus)
                                fn.bus = fn_bus
                            else:
                                fn_bus = fn.bus

                            self.create_line(bus_from=bus,
                                             bus_to=fn_bus,
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_bus_and_cn():

                            self.create_line(bus_from=self.started_branch.get_bus_from(),
                                             cn_to=self.started_branch.get_cn_to(),
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_cn_and_bus():

                            self.create_line(bus_to=self.started_branch.get_bus_to(),
                                             cn_from=self.started_branch.get_cn_from(),
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_cn():

                            self.create_line(cn_from=self.started_branch.get_cn_from(),
                                             cn_to=self.started_branch.get_cn_to(),
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_busbar_and_bus():

                            self.create_line(cn_from=self.started_branch.get_busbar_from().cn,
                                             bus_to=self.started_branch.get_bus_to(),
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_bus_and_busbar():

                            self.create_line(bus_from=self.started_branch.get_bus_from(),
                                             cn_to=self.started_branch.get_busbar_to().cn,
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_busbar_and_cn():

                            self.create_line(cn_from=self.started_branch.get_busbar_from().cn,
                                             cn_to=self.started_branch.get_cn_to(),
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_cn_and_busbar():

                            self.create_line(cn_from=self.started_branch.get_cn_from(),
                                             cn_to=self.started_branch.get_busbar_to().cn,
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        elif self.started_branch.connected_between_busbar():

                            self.create_line(cn_from=self.started_branch.get_busbar_from().cn,
                                             cn_to=self.started_branch.get_busbar_to().cn,
                                             from_port=self.started_branch.get_terminal_from(),
                                             to_port=self.started_branch.get_terminal_to())

                        else:
                            warn('unknown connection')

            # remove from the hosted connections
            self.started_branch.unregister_port_from()
            self.started_branch.unregister_port_to()
            self.remove_from_scene(self.started_branch)

            # release this pointer
            self.started_branch = None

    def apply_expansion_factor(self, factor: float):
        """
        separate or get closer the drawn elements
        :param factor: expansion factor (i.e 1.1 to expand, 0.9 to get closer)
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        check_selected_only = len(self.diagram_scene.selectedItems()) > 0

        for dev_tpe in [DeviceType.BusDevice,
                        DeviceType.BusBarDevice,
                        DeviceType.ConnectivityNodeDevice,
                        DeviceType.FluidNodeDevice,
                        DeviceType.Transformer3WDevice]:

            graphic_objects_dict = self.graphics_manager.graphic_dict.get(dev_tpe, dict())

            for key, item in graphic_objects_dict.items():
                x = item.pos().x() * factor
                y = item.pos().y() * factor
                item.setPos(QPointF(x, y))

                if check_selected_only:
                    if item.isSelected():
                        max_x = max(max_x, x)
                        min_x = min(min_x, x)
                        max_y = max(max_y, y)
                        min_y = min(min_y, y)
                    else:
                        pass
                else:
                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

                # apply changes to the diagram coordinates
                self.diagram.update_xy(api_object=item.api_object, x=x, y=y)

        # set the limits of the view
        self.set_limits(min_x, max_x, min_y, max_y)

    def expand_node_distances(self) -> None:
        """
        Expand the grid
        """
        self.apply_expansion_factor(self.expand_factor)

    def shrink_node_distances(self) -> None:
        """
        Shrink node distances
        """
        self.apply_expansion_factor(1.0 / self.expand_factor)

    def set_limits(self,
                   min_x: int,
                   max_x: Union[float, int],
                   min_y: Union[float, int],
                   max_y: int,
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
        h = dy + 2 * my + 120
        w = dx + 2 * mx + 120
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
        :param elements: list of API
        """
        node_like_types = [BusGraphicItem, FluidNodeGraphicItem, CnGraphicItem,
                           BusBarGraphicItem, Transformer3WGraphicItem]

        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize
        if elements is None:
            for item in self.diagram_scene.items():
                if type(item) in node_like_types:
                    x = item.pos().x()
                    y = item.pos().y()

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)
        else:
            for item in self.diagram_scene.items():
                if type(item) in node_like_types:

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

        # for device_type, graphics_dict in self.graphics_manager.graphic_dict.items():
        #     for idtag, graphic in graphics_dict.items():

        for key, points_group in self.diagram.data.items():
            for idTag, location in points_group.locations.items():
                if location.api_object is not None:

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

    def get_graph(self):
        """
        Get graph of the diagram (Not the circuit)
        """
        graph = nx.DiGraph()

        bus_dictionary = dict()

        for i, bus, graphic_object in self.get_buses():
            graph.add_node(i)
            bus_dictionary[bus.idtag] = i

        tuples = list()

        for dev_type in BRANCH_TYPES:

            points_group = self.diagram.data.get(dev_type.value, None)

            if points_group:

                for idtag, point in points_group.locations.items():
                    branch = point.api_object
                    f = bus_dictionary[branch.bus_from.idtag]
                    t = bus_dictionary[branch.bus_to.idtag]
                    if hasattr(branch, 'X'):
                        w = branch.X
                    else:
                        w = 1e-3
                    tuples.append((f, t, w))

        graph.add_weighted_edges_from(tuples)

        return graph

    def auto_layout(self, sel: str):
        """
        Automatic layout of the nodes
        """

        nx_graph, node_like_api_objects = self.diagram.build_graph()

        layout_algorithms_dict = dict()
        layout_algorithms_dict['circular_layout'] = nx.circular_layout
        layout_algorithms_dict['random_layout'] = nx.random_layout
        layout_algorithms_dict['shell_layout'] = nx.shell_layout
        layout_algorithms_dict['spring_layout'] = nx.spring_layout
        layout_algorithms_dict['spectral_layout'] = nx.spectral_layout
        layout_algorithms_dict['fruchterman_reingold_layout'] = nx.fruchterman_reingold_layout
        layout_algorithms_dict['kamada_kawai'] = nx.kamada_kawai_layout

        if sel == 'random_layout':
            pos = nx.random_layout(nx_graph)
        elif sel == 'spring_layout':
            pos = nx.spring_layout(nx_graph, iterations=100, scale=10)
        elif sel == 'shell_layout':
            pos = nx.shell_layout(nx_graph, scale=10)
        elif sel == 'circular_layout':
            pos = nx.circular_layout(nx_graph, scale=10)
        elif sel == 'kamada_kawai':
            pos = nx.kamada_kawai_layout(nx_graph, scale=10)
        elif sel == 'fruchterman_reingold_layout':
            pos = nx.fruchterman_reingold_layout(nx_graph, scale=10)
        else:
            pos = nx.spring_layout(nx_graph, iterations=100, scale=10)

        # assign the positions to the graphical objects of the nodes
        for i, bus in enumerate(node_like_api_objects):
            loc = self.diagram.query_point(bus)
            graphic_object = self.graphics_manager.query(elm=bus)

            if graphic_object is not None:
                x, y = pos[i] * 500

                # apply changes to the API objects
                loc.x = x
                loc.y = y
                graphic_object.set_position(x, y)

        self.center_nodes()

    def fill_xy_from_lat_lon(self,
                             destructive: bool = True,
                             factor: float = 0.01,
                             remove_offset: bool = True):
        """
        fill the x and y value from the latitude and longitude values
        :param destructive: if true, the values are overwritten regardless, otherwise only if x and y are 0
        :param factor: Explosion factor
        :param remove_offset: remove the sometimes huge offset coming from pyproj
        :return Logger object
        """

        buses_info_list = self.get_buses()

        n = len(buses_info_list)
        lon = np.zeros(n)
        lat = np.zeros(n)
        i = 0
        for idx, bus, graphic_object in buses_info_list:
            lon[i] = bus.longitude
            lat[i] = bus.latitude
            i += 1

        transformer = pyproj.Transformer.from_crs(4326, 25830, always_xy=True)

        # the longitude is more reated to x, the latitude is more related to y
        x, y = transformer.transform(xx=lon, yy=lat)
        x *= - factor
        y *= factor

        # remove the offset
        if remove_offset:
            x_min = np.min(x)
            y_max = np.max(y)
            x -= x_min + 100  # 100 is a healthy offset
            y -= y_max - 100  # 100 is a healthy offset

        # assign the values
        i = 0
        for idx, bus, graphic_object in buses_info_list:
            graphic_object.set_position(x[i], y[i])
            if destructive:
                bus.x = x[i]
                bus.y = y[i]
            i += 1

    def get_image(self, transparent: bool = False) -> Tuple[QImage, int, int]:
        """
        get the current picture
        :param transparent: Set a transparent background
        :return: QImage, width, height
        """
        w = self.editor_graphics_view.width()
        h = self.editor_graphics_view.height()

        if transparent:
            image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
        else:
            image = QImage(w, h, QImage.Format_RGB32)
            image.fill(ACTIVE['backgound'])

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        self.editor_graphics_view.render(painter)
        painter.end()
        # image = self.editor_graphics_view.grab().toImage()

        return image, w, h

    def take_picture(self, filename: str):
        """
        Save the grid to a png file
        """
        name, extension = os.path.splitext(filename.lower())

        if extension == '.png':
            image, _, _ = self.get_image(transparent=False)
            image.save(filename)

        elif extension == '.svg':
            w = self.editor_graphics_view.width()
            h = self.editor_graphics_view.height()
            svg_gen = QSvgGenerator()
            svg_gen.setFileName(filename)
            svg_gen.setSize(QSize(w, h))
            svg_gen.setViewBox(QRect(0, 0, w, h))
            svg_gen.setTitle("Electrical grid schematic")
            svg_gen.setDescription("An SVG drawing created by GridCal")

            painter = QPainter(svg_gen)
            self.editor_graphics_view.render(painter)
            painter.end()
        else:
            raise Exception('Extension ' + str(extension) + ' not supported :(')

    def add_api_bus(self,
                    bus: Bus,
                    injections_by_tpe: Dict[DeviceType, List[ALL_DEV_TYPES]],
                    explode_factor: float = 1.0,
                    x0: Union[int, None] = None,
                    y0: Union[int, None] = None) -> BusGraphicItem:
        """
        Add API bus to the diagram
        :param bus: Bus instance
        :param injections_by_tpe: dictionary with the device type as key and the list of devices at the bus as values
        :param explode_factor: explode factor
        :param x0: x position of the bus (optional)
        :param y0: y position of the bus (optional)
        """
        x = int(bus.x * explode_factor) if x0 is None else x0
        y = int(bus.y * explode_factor) if y0 is None else y0

        # add the graphic object to the diagram view
        graphic_object = self.create_bus_graphics(bus=bus, x=x, y=y, w=bus.w, h=bus.h)

        # create the bus children
        if len(injections_by_tpe) > 0:
            graphic_object.create_children_widgets(injections_by_tpe=injections_by_tpe)

        self.update_diagram_element(device=bus,
                                    x=x,
                                    y=y,
                                    w=bus.w,
                                    h=bus.h,
                                    r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        return graphic_object

    def add_api_busbar(self,
                       bus: BusBar,
                       injections_by_tpe: Dict[DeviceType, List[ALL_DEV_TYPES]],
                       x0: Union[int, None] = None,
                       y0: Union[int, None] = None) -> BusBarGraphicItem:
        """
        Add API bus to the diagram
        :param bus: Bus instance
        :param injections_by_tpe: dictionary with the device type as key and the list of devices at the bus as values
        :param x0: x position of the bus (optional)
        :param y0: y position of the bus (optional)
        """
        x = 0 if x0 is None else x0
        y = 0 if y0 is None else y0

        # add the graphic object to the diagram view
        graphic_object = self.create_bus_bar_graphics(node=bus, x=x, y=y, w=0, h=0)

        # create the bus children
        if len(injections_by_tpe) > 0:
            graphic_object.create_children_widgets(injections_by_tpe=injections_by_tpe)

        self.update_diagram_element(device=bus,
                                    x=x,
                                    y=y,
                                    w=0,
                                    h=0,
                                    r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        return graphic_object

    def add_api_cn(self,
                   cn: ConnectivityNode,
                   injections_by_tpe: Dict[DeviceType, List[ALL_DEV_TYPES]],
                   x0: Union[int, None] = None,
                   y0: Union[int, None] = None) -> CnGraphicItem:
        """
        Add API bus to the diagram
        :param cn: Bus instance
        :param injections_by_tpe: dictionary with the device type as key and the list of devices at the bus as values
        :param x0: x position of the bus (optional)
        :param y0: y position of the bus (optional)
        """
        x = 0 if x0 is None else x0
        y = 0 if y0 is None else y0

        # add the graphic object to the diagram view
        graphic_object = self.create_connectivity_node_graphics(node=cn, x=x, y=y, w=0, h=0)

        # create the bus children
        if len(injections_by_tpe) > 0:
            graphic_object.create_children_widgets(injections_by_tpe=injections_by_tpe)

        self.update_diagram_element(device=cn,
                                    x=x,
                                    y=y,
                                    w=0,
                                    h=0,
                                    r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        return graphic_object

    def find_port(self,
                  port: OPTIONAL_PORT = None,
                  bus: Union[None, Bus] = None,
                  cn: Union[None, ConnectivityNode] = None) -> OPTIONAL_PORT:
        """
        Try to find the connection graphics from the API connection
        :param port: Conection port (optional)
        :param bus: Api Bus (optional)
        :param cn: API connectivity node (optional)
        :return: OPTIONAL_PORT
        """
        if port is None:

            if bus is not None and cn is None:  # bus provided, no cn provided

                # Bus provided, search its graphics
                bus_graphic0 = self.graphics_manager.query(bus)

                if bus_graphic0 is None:
                    # could not find any graphics :(
                    return None

                else:
                    # the from bu is found, return its terminal
                    return bus_graphic0.get_terminal()

            elif bus is None and cn is not None:  # bus Not provided, cn provided

                cn_graphic0 = self.graphics_manager.query(cn)

                if cn_graphic0 is None:
                    # could not find any graphics :(
                    return None
                else:
                    # found the CN graphics
                    return cn_graphic0.get_terminal()

            elif bus is not None and cn is not None:  # bus provided, cn provided -> preffer the cn

                cn_graphic0 = self.graphics_manager.query(cn)

                if cn_graphic0 is None:
                    # Bus provided, search its graphics
                    bus_graphic0 = self.graphics_manager.query(bus)

                    if bus_graphic0 is None:
                        # No bus found, search for the CN
                        return None

                    else:
                        # the from bu is found, return its terminal
                        return bus_graphic0.get_terminal()
                else:
                    # found the CN graphics
                    return cn_graphic0.get_terminal()

            else:
                # nothing was provided...
                return None
        else:
            return port

    def find_ports(self,
                   branch: BRANCH_TYPES,
                   prefer_node_breaker: bool,
                   logger: Logger) -> Tuple[OPTIONAL_PORT, OPTIONAL_PORT]:
        """
        Find the preferred set of ports for drawing
        :param branch: some API branch
        :param prefer_node_breaker:
        :param logger:
        :return: OPTIONAL_PORT, OPTIONAL_PORT
        """

        obj_from, obj_to, is_ok = branch.get_from_and_to_objects(t_idx=None,
                                                                 logger=logger,
                                                                 prefer_node_breaker=prefer_node_breaker)

        # Bus provided, search its graphics
        bus_graphic0 = self.graphics_manager.query_preferring_busbars(obj_from)
        if bus_graphic0 is None:
            # could not find any graphics :(
            from_port = None
        else:
            # the from bu is found, return its terminal
            from_port = bus_graphic0.get_terminal()

        # Bus provided, search its graphics
        bus_graphic1 = self.graphics_manager.query_preferring_busbars(obj_to)
        if bus_graphic1 is None:
            # could not find any graphics :(
            to_port = None
        else:
            # the from bu is found, return its terminal
            to_port = bus_graphic1.get_terminal()

        # from_port = self.find_port(port=None, bus=branch.bus_from, cn=branch.cn_from)
        # to_port = self.find_port(port=None, bus=branch.bus_to, cn=branch.cn_to)

        return from_port, to_port

    def add_api_branch(self,
                       branch: BRANCH_TYPES,
                       new_graphic_func: Callable[[Union[BarTerminalItem, RoundTerminalItem],
                                                   Union[BarTerminalItem, RoundTerminalItem, None],
                                                   "SchematicWidget",
                                                   int,
                                                   BRANCH_TYPES,
                                                   bool], BRANCH_GRAPHICS],
                       from_port: OPTIONAL_PORT = None,
                       to_port: OPTIONAL_PORT = None,
                       prefer_node_breaker: bool = False,
                       draw_labels: bool = True,
                       logger: Logger = Logger()) -> Union[TransformerGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param new_graphic_func: New graphic object to use if needed
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param prefer_node_breaker: Prefer node breaker representation?
        :param draw_labels: Draw labels by default?
        :param logger: Logger
        """

        # search for the api object, because it may be created already
        graphic_object = self.graphics_manager.query(elm=branch)

        if graphic_object is None:

            if from_port is None and to_port is None:
                from_port, to_port = self.find_ports(branch=branch,
                                                     prefer_node_breaker=prefer_node_breaker,
                                                     logger=logger)

            if from_port is not None and to_port is not None and (from_port != to_port):

                # Create new graphics object
                graphic_object = new_graphic_func(from_port,
                                                  to_port,
                                                  self,
                                                  5,
                                                  branch,
                                                  draw_labels)

                self.add_to_scene(graphic_object=graphic_object)

                graphic_object.redraw()
                self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0,
                                            draw_labels=graphic_object.draw_labels,
                                            graphic_object=graphic_object)
                return graphic_object
            else:
                # print("Branch's ports were not found in the diagram :(")
                logger.add_warning(msg="Branch's ports were not found in the diagram",
                                   device=branch.name)
                return None

        else:
            return graphic_object

    def add_api_line(self,
                     branch: Line,
                     from_port: OPTIONAL_PORT = None,
                     to_port: OPTIONAL_PORT = None,
                     draw_labels: bool = True,
                     prefer_node_breaker: bool = False,
                     logger: Logger = Logger()) -> Union[LineGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param prefer_node_breaker: Prefer node breaker representation?
        :param logger: Logger
        :return: LineGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=LineGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   prefer_node_breaker=prefer_node_breaker,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_dc_line(self,
                        branch: DcLine,
                        from_port: OPTIONAL_PORT = None,
                        to_port: OPTIONAL_PORT = None,
                        draw_labels: bool = True,
                        prefer_node_breaker: bool = False,
                        logger: Logger = Logger()) -> Union[DcLineGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param prefer_node_breaker: Prefer node breaker representation?
        :param logger: Logger
        :return: DcLineGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=DcLineGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   prefer_node_breaker=prefer_node_breaker,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_hvdc(self,
                     branch: HvdcLine,
                     from_port: OPTIONAL_PORT = None,
                     to_port: OPTIONAL_PORT = None,
                     draw_labels: bool = True,
                     prefer_node_breaker: bool = False,
                     logger: Logger = Logger()) -> Union[HvdcGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param prefer_node_breaker: Prefer node breaker representation?
        :param logger: Logger
        :return: SeriesReactanceGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=HvdcGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   prefer_node_breaker=prefer_node_breaker,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_vsc(self,
                    branch: VSC,
                    from_port: OPTIONAL_PORT = None,
                    to_port: OPTIONAL_PORT = None,
                    draw_labels: bool = True,
                    prefer_node_breaker: bool = False,
                    logger: Logger = Logger()) -> Union[VscGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param prefer_node_breaker: Prefer node breaker representation?
        :param logger: Logger
        :return: SeriesReactanceGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=VscGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   prefer_node_breaker=prefer_node_breaker,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_upfc(self,
                     branch: UPFC,
                     from_port: OPTIONAL_PORT = None,
                     to_port: OPTIONAL_PORT = None,
                     draw_labels: bool = True,
                     prefer_node_breaker: bool = False,
                     logger: Logger = Logger()) -> Union[UpfcGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param prefer_node_breaker: Prefer node breaker representation?
        :param logger: Logger
        :return: SeriesReactanceGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=UpfcGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   prefer_node_breaker=prefer_node_breaker,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_series_reactance(self,
                                 branch: SeriesReactance,
                                 from_port: OPTIONAL_PORT = None,
                                 to_port: OPTIONAL_PORT = None,
                                 draw_labels: bool = True,
                                 prefer_node_breaker: bool = False,
                                 logger: Logger = Logger()) -> Union[SeriesReactanceGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param prefer_node_breaker: Prefer node breaker representation?
        :param logger: Logger
        :return: SeriesReactanceGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=SeriesReactanceGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   prefer_node_breaker=prefer_node_breaker,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_transformer(self,
                            branch: Transformer2W,
                            from_port: OPTIONAL_PORT = None,
                            to_port: OPTIONAL_PORT = None,
                            draw_labels: bool = True,
                            prefer_node_breaker: bool = False,
                            logger: Logger = Logger()) -> Union[TransformerGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param prefer_node_breaker: Prefer node breaker representation?
        :param logger: Logger
        :return: TransformerGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=TransformerGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   prefer_node_breaker=prefer_node_breaker,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_switch(self,
                       branch: Switch,
                       from_port: OPTIONAL_PORT = None,
                       to_port: OPTIONAL_PORT = None,
                       draw_labels: bool = True,
                       prefer_node_breaker: bool = False,
                       logger: Logger = Logger()) -> Union[SwitchGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param prefer_node_breaker: Prefer node breaker representation?
        :param logger: Logger
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=SwitchGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   prefer_node_breaker=prefer_node_breaker,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_transformer_3w(self, elm: Transformer3W):
        """
        add API branch to the Scene
        :param elm: Branch instance
        """

        tr3_graphic_object = self.create_transformer_3w_graphics(elm=elm, x=elm.x, y=elm.y)

        port1 = self.find_port(bus=elm.bus1)
        port2 = self.find_port(bus=elm.bus2)
        port3 = self.find_port(bus=elm.bus3)

        conn1 = WindingGraphicItem(from_port=tr3_graphic_object.terminals[0],
                                   to_port=port1,
                                   editor=self)
        tr3_graphic_object.set_connection(i=0, bus=elm.bus1, conn=conn1)

        conn2 = WindingGraphicItem(from_port=tr3_graphic_object.terminals[1],
                                   to_port=port2,
                                   editor=self)
        tr3_graphic_object.set_connection(i=1, bus=elm.bus2, conn=conn2)

        conn3 = WindingGraphicItem(from_port=tr3_graphic_object.terminals[2],
                                   to_port=port3,
                                   editor=self)
        tr3_graphic_object.set_connection(i=2, bus=elm.bus3, conn=conn3)

        tr3_graphic_object.update_conn()

        self.update_diagram_element(device=elm,
                                    x=elm.x,
                                    y=elm.y,
                                    w=80,
                                    h=80,
                                    r=0,
                                    draw_labels=True,
                                    graphic_object=tr3_graphic_object)

        self.update_diagram_element(device=conn1.api_object, graphic_object=conn1)
        self.update_diagram_element(device=conn2.api_object, graphic_object=conn2)
        self.update_diagram_element(device=conn3.api_object, graphic_object=conn3)

        return tr3_graphic_object

    def add_api_fluid_node(self, node: FluidNode,
                           injections_by_tpe: Dict[DeviceType, List[ALL_DEV_TYPES]]):
        """
        Add API bus to the diagram
        :param node: FluidNode instance
        :param injections_by_tpe
        """
        x = 0
        y = 0

        # add the graphic object to the diagram view
        graphic_object = self.create_fluid_node_graphics(node=node, x=x, y=y, w=80, h=40)

        # create the bus children
        graphic_object.create_children_widgets(injections_by_tpe=injections_by_tpe)

        # arrange the children
        graphic_object.arrange_children()

        self.update_diagram_element(device=node,
                                    x=x,
                                    y=y,
                                    w=graphic_object.w,
                                    h=graphic_object.h,
                                    r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        return graphic_object

    def add_api_fluid_path(self, branch: FluidPath):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphics = self.graphics_manager.query(branch.source)
        bus_t_graphics = self.graphics_manager.query(branch.target)

        if bus_f_graphics and bus_t_graphics:

            graphic_object = FluidPathGraphicItem(from_port=bus_f_graphics.get_terminal(),
                                                  to_port=bus_t_graphics.get_terminal(),
                                                  editor=self,
                                                  api_object=branch)

            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0,
                                        draw_labels=graphic_object.draw_labels,
                                        graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's fluid nodes were not found in the diagram :(")
            return None

    def convert_line_to_hvdc(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to HVDC, this is the GUI way to create HVDC objects
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        hvdc = self.circuit.convert_line_to_hvdc(line)

        # add device to the schematic
        graphic_object = self.add_api_hvdc(branch=hvdc,
                                           from_port=line_graphic.get_terminal_from(),
                                           to_port=line_graphic.get_terminal_to(),
                                           draw_labels=line_graphic.draw_labels,
                                           prefer_node_breaker=self.prefer_node_breaker)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=hvdc, x=0, y=0, w=0, h=0, r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

    def convert_line_to_transformer(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to Transformer
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        transformer = self.circuit.convert_line_to_transformer(line)

        # add device to the schematic
        graphic_object = self.add_api_transformer(branch=transformer,
                                                  from_port=line_graphic.get_terminal_from(),
                                                  to_port=line_graphic.get_terminal_to(),
                                                  draw_labels=line_graphic.draw_labels,
                                                  prefer_node_breaker=self.prefer_node_breaker)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=transformer, x=0, y=0, w=0, h=0, r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)
        # self.delete_diagram_element(device=line)

    def convert_line_to_vsc(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        vsc = self.circuit.convert_line_to_vsc(line)

        # add device to the schematic
        graphic_object = self.add_api_vsc(branch=vsc,
                                          from_port=line_graphic.get_terminal_from(),
                                          to_port=line_graphic.get_terminal_to(),
                                          draw_labels=line_graphic.draw_labels,
                                          prefer_node_breaker=self.prefer_node_breaker)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=vsc, x=0, y=0, w=0, h=0, r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

    def convert_line_to_upfc(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to UPFC
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        upfc = self.circuit.convert_line_to_upfc(line)

        # add device to the schematic
        graphic_object = self.add_api_upfc(branch=upfc,
                                           from_port=line_graphic.get_terminal_from(),
                                           to_port=line_graphic.get_terminal_to(),
                                           draw_labels=line_graphic.draw_labels,
                                           prefer_node_breaker=self.prefer_node_breaker)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=upfc, x=0, y=0, w=0, h=0, r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

    def convert_line_to_series_reactance(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to convert_line_to_series_reactance
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        series_reactance = self.circuit.convert_line_to_series_reactance(line)

        # add device to the schematic
        graphic_object = self.add_api_series_reactance(branch=series_reactance,
                                                       from_port=line_graphic.get_terminal_from(),
                                                       to_port=line_graphic.get_terminal_to(),
                                                       draw_labels=line_graphic.draw_labels,
                                                       prefer_node_breaker=self.prefer_node_breaker)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=series_reactance, x=0, y=0, w=0, h=0, r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

    def convert_line_to_switch(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to convert_line_to_series_reactance
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        switch = self.circuit.convert_line_to_switch(line)

        # add device to the schematic
        graphic_object = self.add_api_switch(branch=switch,
                                             from_port=line_graphic.get_terminal_from(),
                                             to_port=line_graphic.get_terminal_to(),
                                             draw_labels=line_graphic.draw_labels,
                                             prefer_node_breaker=self.prefer_node_breaker)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=switch, x=0, y=0, w=0, h=0, r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

    def convert_fluid_path_to_line(self, element: FluidPath, item_graphic: FluidPathGraphicItem):
        """
        Convert a fluid node to an electrical line
        :param element: FluidPath instance
        :param item_graphic: FluidPathGraphicItem
        :return: Nothing
        """

        fl_from = item_graphic.get_fluid_node_graphics_from()
        fl_from.create_bus_if_necessary()

        fl_to = item_graphic.get_fluid_node_graphics_to()
        fl_to.create_bus_if_necessary()

        line = self.circuit.convert_fluid_path_to_line(element)

        # add device to the schematic
        graphic_object = self.add_api_line(branch=line,
                                           from_port=fl_from.get_terminal(),
                                           to_port=fl_to.get_terminal(),
                                           draw_labels=True,
                                           prefer_node_breaker=self.prefer_node_breaker)
        self.add_to_scene(graphic_object)

        # update position
        fl_from.get_terminal().update()
        fl_to.get_terminal().update()

        # delete from the schematic
        self.remove_from_scene(item_graphic)

        self.update_diagram_element(device=line, x=0, y=0, w=0, h=0, r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

    def convert_generator_to_battery(self, gen: Generator, graphic_object: GeneratorGraphicItem):
        """
        Convert a generator to a battery
        :param gen: Generator instance
        :param graphic_object: GeneratorGraphicItem
        :return: Nothing
        """
        battery = self.circuit.convert_generator_to_battery(gen)

        bus_graphic_object = self.graphics_manager.query(gen.bus)

        # add device to the schematic
        if bus_graphic_object is not None:
            bus_graphic_object.add_battery(battery)
        else:
            raise Exception("Bus graphics not found! this is likely a bug")

        # delete from the schematic
        graphic_object.remove(ask=False)

    def add_object_to_the_schematic(
            self,
            elm: ALL_DEV_TYPES,
            injections_by_bus: Union[None, Dict[Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]] = None,
            injections_by_fluid_node: Union[None, Dict[FluidNode, Dict[DeviceType, List[FLUID_TYPES]]]] = None,
            injections_by_cn: Union[None, Dict[Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]] = None,
            logger: Logger = Logger()):
        """

        :param elm:
        :param injections_by_bus:
        :param injections_by_fluid_node:
        :param injections_by_cn:
        :param logger:
        :return:
        """

        if self.graphics_manager.query(elm=elm) is None:

            if isinstance(elm, Bus):

                if not elm.is_internal:  # 3w transformer buses are not represented
                    if injections_by_bus is None:
                        injections_by_bus = self.circuit.get_injection_devices_grouped_by_bus()

                    graphic_obj = self.add_api_bus(bus=elm,
                                                   injections_by_tpe=injections_by_bus.get(elm, dict()),
                                                   explode_factor=1.0)
                else:
                    graphic_obj = None

            elif isinstance(elm, FluidNode):

                if injections_by_fluid_node is None:
                    injections_by_fluid_node = self.circuit.get_injection_devices_grouped_by_fluid_node()

                graphic_obj = self.add_api_fluid_node(node=elm,
                                                      injections_by_tpe=injections_by_fluid_node.get(elm, dict()))

            elif isinstance(elm, ConnectivityNode):

                if injections_by_cn is None:
                    injections_by_cn = self.circuit.get_injection_devices_grouped_by_cn()

                graphic_obj = self.add_api_cn(cn=elm,
                                              injections_by_tpe=injections_by_cn.get(elm, dict()))

            elif isinstance(elm, BusBar):

                if injections_by_cn is None:
                    injections_by_cn = self.circuit.get_injection_devices_grouped_by_cn()

                graphic_obj = self.add_api_busbar(bus=elm,
                                                  injections_by_tpe=injections_by_cn.get(elm.cn, dict()))

            elif isinstance(elm, Line):
                graphic_obj = self.add_api_line(elm)

            elif isinstance(elm, DcLine):
                graphic_obj = self.add_api_dc_line(elm)

            elif isinstance(elm, Transformer2W):
                graphic_obj = self.add_api_transformer(elm)

            elif isinstance(elm, Transformer3W):
                graphic_obj = self.add_api_transformer_3w(elm)

            elif isinstance(elm, HvdcLine):
                graphic_obj = self.add_api_hvdc(elm)

            elif isinstance(elm, SeriesReactance):
                graphic_obj = self.add_api_series_reactance(elm)

            elif isinstance(elm, Switch):
                graphic_obj = self.add_api_switch(elm)

            elif isinstance(elm, VSC):
                graphic_obj = self.add_api_vsc(elm)

            elif isinstance(elm, UPFC):
                graphic_obj = self.add_api_upfc(elm)

            elif isinstance(elm, FluidPath):
                graphic_obj = self.add_api_fluid_path(elm)

            else:
                graphic_obj = None

            self.add_to_scene(graphic_object=graphic_obj)

        else:
            logger.add_warning("Device already added", device_class=elm.device_type.value, device=elm.name)

    def add_elements_to_schematic(self,
                                  buses: List[Bus],
                                  connectivity_nodes: List[ConnectivityNode],
                                  busbars: List[BusBar],
                                  lines: List[Line],
                                  dc_lines: List[DcLine],
                                  transformers2w: List[Transformer2W],
                                  transformers3w: List[Transformer3W],
                                  hvdc_lines: List[HvdcLine],
                                  vsc_devices: List[VSC],
                                  upfc_devices: List[UPFC],
                                  switches: List[Switch],
                                  fluid_nodes: List[FluidNode],
                                  fluid_paths: List[FluidPath],
                                  injections_by_bus: Dict[Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]],
                                  injections_by_cn: Dict[
                                      ConnectivityNode, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]],
                                  injections_by_fluid_node: Dict[FluidNode, Dict[DeviceType, List[FLUID_TYPES]]],
                                  explode_factor=1.0,
                                  prog_func: Union[Callable, None] = None,
                                  text_func: Union[Callable, None] = None):
        """
        Add a elements to the schematic scene
        :param buses: list of Bus objects
        :param connectivity_nodes: list of connectivity nodes
        :param busbars: List of usbars
        :param lines: list of Line objects
        :param dc_lines: list of DcLine objects
        :param transformers2w: list of Transformer Objects
        :param transformers3w: list of Transformer3W Objects
        :param hvdc_lines: list of HvdcLine objects
        :param vsc_devices: list Vsc objects
        :param upfc_devices: List of UPFC devices
        :param switches: List of switches
        :param fluid_nodes: List of FluidNode devices
        :param fluid_paths: List of FluidPath devices
        :param injections_by_bus:
        :param injections_by_fluid_node:
        :param injections_by_cn:
        :param explode_factor: factor of "explosion": Separation of the nodes factor
        :param prog_func: progress report function
        :param text_func: Text report function
        """

        # first create the buses
        if text_func is not None:
            text_func('Creating schematic buses')

        nn = len(buses)
        for i, bus in enumerate(buses):

            if not bus.is_internal:  # 3w transformer buses are not represented

                if prog_func is not None:
                    prog_func((i + 1) / nn * 100.0)

                self.add_api_bus(bus=bus,
                                 injections_by_tpe=injections_by_bus.get(bus, dict()),
                                 explode_factor=explode_factor)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic busbars')

        nn = len(busbars)
        for i, bus in enumerate(busbars):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_busbar(bus=bus, injections_by_tpe=injections_by_cn.get(bus.cn, dict()))

        # --------------------------------------------------------------------------------------------------------------

        if text_func is not None:
            text_func('Creating schematic connectivity nodes')

        nn = len(connectivity_nodes)
        for i, cn in enumerate(connectivity_nodes):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            if not cn.internal:
                self.add_api_cn(cn=cn, injections_by_tpe=injections_by_cn.get(cn, dict()))

        # --------------------------------------------------------------------------------------------------------------

        if text_func is not None:
            text_func('Creating schematic Fluid nodes devices')

        nn = len(fluid_nodes)
        for i, elm in enumerate(fluid_nodes):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_fluid_node(node=elm, injections_by_tpe=injections_by_fluid_node.get(elm, dict()))

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic line devices')

        nn = len(lines)
        for i, branch in enumerate(lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_line(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic line devices')

        nn = len(dc_lines)
        for i, branch in enumerate(dc_lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_dc_line(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic transformer devices')

        nn = len(transformers2w)
        for i, branch in enumerate(transformers2w):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_transformer(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic transformer3w devices')

        nn = len(transformers3w)
        for i, elm in enumerate(transformers3w):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_transformer_3w(elm)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic HVDC devices')

        nn = len(hvdc_lines)
        for i, branch in enumerate(hvdc_lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_hvdc(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic VSC devices')

        nn = len(vsc_devices)
        for i, branch in enumerate(vsc_devices):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_vsc(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic UPFC devices')

        nn = len(upfc_devices)
        for i, branch in enumerate(upfc_devices):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_upfc(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic switches')

        nn = len(switches)
        for i, branch in enumerate(switches):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_switch(branch)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic Fluid paths devices')

        nn = len(fluid_paths)
        for i, elm in enumerate(fluid_paths):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_fluid_path(elm)

    def align_schematic(self, buses: List[Bus] = ()):
        """
        Align the scene view to the content
        :param buses: list of buses to use for alignment
        """
        # figure limits
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        if len(buses):
            lst = buses
        else:
            lst = self.circuit.get_buses()

        if len(lst):
            # first pass
            for bus in lst:

                graphic_object = self.graphics_manager.query(bus)

                if graphic_object:
                    graphic_object.arrange_children()
                    x = graphic_object.pos().x()
                    y = graphic_object.pos().y()

                    # compute the boundaries of the grid
                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

            # second pass
            for bus in lst:
                location = self.diagram.query_point(bus)
                graphic_object = self.graphics_manager.query(bus)

                if graphic_object:
                    # get the item position
                    x = graphic_object.pos().x()
                    y = graphic_object.pos().y()
                    location.x = x - min_x
                    location.y = y - max_y
                    graphic_object.set_position(location.x, location.y)

            # set the figure limits
            self.set_limits(0, max_x - min_x, min_y - max_y, 0)

            #  center the view
            self.center_nodes()

    def clear(self) -> None:
        """
        Clear the schematic
        """
        super().clear()
        self.diagram_scene.clear()

    def recolour_mode(self) -> None:
        """
        Change the colour according to the system theme
        :return:
        """

        for device_type, graphics_dict in self.graphics_manager.graphic_dict.items():
            for idtag, graphic_object in graphics_dict.items():
                if graphic_object is not None:
                    graphic_object.recolour_mode()

    def set_big_bus_marker(self, buses: List[Bus], color: QColor):
        """
        Set a big marker at the selected buses
        :param buses: list of Bus objects
        :param color: colour to use
        """

        for bus in buses:

            graphic_obj = self.graphics_manager.query(bus)
            if graphic_obj is not None:
                graphic_obj.add_big_marker(color=color)
                graphic_obj.setSelected(True)

    def set_big_bus_marker_colours(self,
                                   buses: List[Bus],
                                   colors: List[type(QColor)],
                                   tool_tips: Union[None, List[str]] = None):
        """
        Set a big marker at the selected buses with the matching colours
        :param buses: list of Bus objects
        :param colors: list of colour to use
        :param tool_tips: list of tool tips (optional)
        """

        if tool_tips:
            for bus, color, tool_tip in zip(buses, colors, tool_tips):

                graphic_obj = self.graphics_manager.query(bus)

                if graphic_obj is not None:
                    graphic_obj.add_big_marker(color=color, tool_tip_text=tool_tip)
                    graphic_obj.setSelected(True)
        else:
            for bus, color in zip(buses, colors):

                graphic_obj = self.graphics_manager.query(bus)

                if graphic_obj is not None:
                    graphic_obj.add_big_marker(color=color)
                    graphic_obj.setSelected(True)

    def clear_big_bus_markers(self) -> None:
        """
        Set a big marker at the selected buses
        """

        graphic_objects_list = self.graphics_manager.get_device_type_list(DeviceType.BusDevice)

        for graphic_object in graphic_objects_list:
            graphic_object.delete_big_marker()

    def set_dark_mode(self) -> None:
        """
        Set the dark theme
        :return:
        """
        ACTIVE['color'] = Qt.white
        ACTIVE['text'] = Qt.white
        ACTIVE['backgound'] = Qt.black
        self.recolour_mode()

    def set_light_mode(self) -> None:
        """
        Set the light theme
        :return:
        """
        ACTIVE['color'] = Qt.black
        ACTIVE['text'] = Qt.black
        ACTIVE['backgound'] = Qt.white
        self.recolour_mode()

    def colour_results(self,
                       buses: List[Bus],
                       branches: List[Union[Line, DcLine, Transformer2W, Winding, UPFC, VSC]],
                       hvdc_lines: List[HvdcLine],
                       Sbus: CxVec,
                       bus_active: IntVec,
                       Sf: CxVec,
                       St: CxVec,
                       voltages: CxVec,
                       loadings: CxVec,
                       types: IntVec = None,
                       losses: CxVec = None,
                       br_active: IntVec = None,
                       hvdc_Pf: Vec = None,
                       hvdc_Pt: Vec = None,
                       hvdc_losses: Vec = None,
                       hvdc_loading: Vec = None,
                       hvdc_active: IntVec = None,
                       loading_label: str = 'loading',
                       ma: Vec = None,
                       theta: Vec = None,
                       Beq: Vec = None,
                       use_flow_based_width: bool = False,
                       min_branch_width: int = 5,
                       max_branch_width=5,
                       min_bus_width=20,
                       max_bus_width=20,
                       cmap: palettes.Colormaps = None):
        """
        Color objects based on the results passed
        :param buses: list of matching bus objects
        :param branches: list of Branches without HVDC
        :param hvdc_lines: list of HVDC lines
        :param Sbus: Buses power (MVA)
        :param bus_active: Bus active status
        :param Sf: Branches power from the "from" bus (MVA)
        :param St: Branches power from the "to" bus (MVA)
        :param voltages: Buses voltage
        :param loadings: Branches load (%)
        :param types: Buses type [PQ: 1, PV: 2, REF: 3, NONE: 4, STO_DISPATCH: 5, PVB: 6]
        :param losses: Branches losses [%]
        :param br_active: Branches active status
        :param hvdc_Pf: HVDC branch flows "from" [MW]
        :param hvdc_Pt: HVDC branch flows "to" [MW]
        :param hvdc_losses: HVDC branch losses [MW]
        :param hvdc_loading: HVDC Branch loading [%]
        :param hvdc_active: HVDC Branch status
        :param loading_label: String saling whatever the loading label means
        :param ma: branch phase shift angle (rad)
        :param theta: branch tap module (p.u.)
        :param Beq: Branch equivanet susceptance (p.u.)
        :param use_flow_based_width: use branch width based on the actual flow?
        :param min_branch_width: Minimum branch width [px]
        :param max_branch_width: Maximum branch width [px]
        :param min_bus_width: Minimum bus width [px]
        :param max_bus_width: Maximum bus width [px]
        :param cmap: Color map [palettes.Colormaps]
        """

        # color nodes
        vmin = 0
        vmax = 1.2
        vrng = vmax - vmin
        vabs = np.abs(voltages)
        vang = np.angle(voltages, deg=True)
        vnorm = (vabs - vmin) / vrng

        if Sbus is not None:
            if len(Sbus) > 0:
                Pabs = np.abs(Sbus)
                mx = Pabs.max()
                if mx != 0.0:
                    Pnorm = Pabs / mx
                else:
                    Pnorm = np.zeros(len(buses))
            else:
                Pnorm = np.zeros(len(buses))
        else:
            Pnorm = np.zeros(len(buses))

        voltage_cmap = viz.get_voltage_color_map()
        loading_cmap = viz.get_loading_color_map()

        '''
        class BusMode(Enum):
        PQ = 1,
        PV = 2,
        REF = 3,
        NONE = 4,
        STO_DISPATCH = 5
        PVB = 6
        '''

        bus_types = ['', 'PQ', 'PV', 'Slack', 'None', 'Storage', 'P', 'PQV']
        max_flow = 1

        if len(buses) == len(vnorm):
            for i, bus in enumerate(buses):

                # try to find the diagram object of the DB object
                graphic_object = self.graphics_manager.query(bus)

                if graphic_object:

                    if bus_active[i]:
                        a = 255
                        if cmap == palettes.Colormaps.Green2Red:
                            b, g, r = palettes.green_to_red_bgr(vnorm[i])

                        elif cmap == palettes.Colormaps.Heatmap:
                            b, g, r = palettes.heatmap_palette_bgr(vnorm[i])

                        elif cmap == palettes.Colormaps.TSO:
                            b, g, r = palettes.tso_substation_palette_bgr(vnorm[i])

                        else:
                            r, g, b, a = voltage_cmap(vnorm[i])
                            r *= 255
                            g *= 255
                            b *= 255
                            a *= 255

                        graphic_object.set_tile_color(QColor(r, g, b, a))

                        graphic_object.set_values(i=i,
                                                  Vm=vabs[i],
                                                  Va=vang[i],
                                                  P=Sbus[i].real if Sbus is not None else None,
                                                  Q=Sbus[i].imag if Sbus is not None else None,
                                                  tpe=bus_types[types[i]] if types is not None else None)

                        if use_flow_based_width:
                            graphic_object.change_size(w=graphic_object.w)

                    else:
                        graphic_object.set_tile_color(Qt.gray)

                else:
                    # No graphic object found
                    pass
        else:
            error_msg("Bus results length differs from the number of Bus results. \n"
                      "Did you change the number of devices? If so, re-run the simulation.")
            return

        # color Branches
        if Sf is not None:
            if len(Sf) > 0:
                lnorm = np.abs(loadings)
                lnorm[lnorm == np.inf] = 0
                Sfabs = np.abs(Sf)
                max_flow = Sfabs.max()

                if hvdc_Pf is not None:
                    if len(hvdc_Pf) > 0:
                        max_flow = max(max_flow, np.abs(hvdc_Pf).max())

                if max_flow != 0:
                    Sfnorm = Sfabs / max_flow
                else:
                    Sfnorm = Sfabs

                if len(branches) == len(Sf):
                    for i, branch in enumerate(branches):

                        # try to find the diagram object of the DB object
                        graphic_object = self.graphics_manager.query(branch)

                        if graphic_object:

                            if br_active[i]:

                                if use_flow_based_width:
                                    w = int(
                                        np.floor(
                                            min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width)))
                                else:
                                    w = graphic_object.pen_width

                                style = Qt.SolidLine

                                a = 255
                                if cmap == palettes.Colormaps.Green2Red:
                                    b, g, r = palettes.green_to_red_bgr(lnorm[i])

                                elif cmap == palettes.Colormaps.Heatmap:
                                    b, g, r = palettes.heatmap_palette_bgr(lnorm[i])

                                elif cmap == palettes.Colormaps.TSO:
                                    b, g, r = palettes.tso_line_palette_bgr(branch.get_max_bus_nominal_voltage(),
                                                                            lnorm[i])

                                else:
                                    r, g, b, a = loading_cmap(lnorm[i])
                                    r *= 255
                                    g *= 255
                                    b *= 255
                                    a *= 255

                                color = QColor(r, g, b, a)

                                tooltip = str(i) + ': ' + branch.name
                                tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'

                                tooltip += '\nPower (from):\t' + "{:10.4f}".format(Sf[i]) + ' [MVA]'

                                if St is not None:
                                    tooltip += '\nPower (to):\t' + "{:10.4f}".format(St[i]) + ' [MVA]'

                                if losses is not None:
                                    tooltip += '\nLosses:\t\t' + "{:10.4f}".format(losses[i]) + ' [MVA]'

                                if branch.device_type == DeviceType.Transformer2WDevice:
                                    if ma is not None:
                                        tooltip += '\ntap module:\t' + "{:10.4f}".format(ma[i])

                                    if theta is not None:
                                        tooltip += '\ntap angle:\t' + "{:10.4f}".format(theta[i]) + ' rad'

                                if branch.device_type == DeviceType.VscDevice:
                                    if ma is not None:
                                        tooltip += '\ntap module:\t' + "{:10.4f}".format(ma[i])

                                    if theta is not None:
                                        tooltip += '\nfiring angle:\t' + "{:10.4f}".format(theta[i]) + ' rad'

                                    if Beq is not None:
                                        tooltip += '\nBeq:\t' + "{:10.4f}".format(Beq[i])

                                graphic_object.setToolTipText(tooltip)
                                graphic_object.set_colour(color, w, style)

                                if hasattr(graphic_object, 'set_arrows_with_power'):
                                    graphic_object.set_arrows_with_power(
                                        Sf=Sf[i] if Sf is not None else None,
                                        St=St[i] if St is not None else None)
                            else:
                                w = graphic_object.pen_width
                                style = Qt.DashLine
                                color = Qt.gray
                                graphic_object.set_pen(QPen(color, w, style))
                        else:
                            # No diagram object
                            pass
                else:
                    error_msg("Branch results length differs from the number of branch results. \n"
                              "Did you change the numbe rof devices? If so, re-run the simulation.")
                    return

        if hvdc_Pf is not None:

            hvdc_sending_power_norm = np.abs(hvdc_Pf) / (max_flow + 1e-20)

            if len(hvdc_lines) == len(hvdc_Pf):
                for i, elm in enumerate(hvdc_lines):

                    # try to find the diagram object of the DB object
                    graphic_object = self.graphics_manager.query(elm)

                    if graphic_object:

                        if hvdc_active[i]:

                            if use_flow_based_width:
                                w = int(np.floor(
                                    min_branch_width + hvdc_sending_power_norm[i] * (
                                            max_branch_width - min_branch_width)))
                            else:
                                w = graphic_object.pen_width

                            if elm.active:
                                style = Qt.SolidLine

                                a = 1
                                if cmap == palettes.Colormaps.Green2Red:
                                    b, g, r = palettes.green_to_red_bgr(abs(hvdc_loading[i]))

                                elif cmap == palettes.Colormaps.Heatmap:
                                    b, g, r = palettes.heatmap_palette_bgr(abs(hvdc_loading[i]))

                                elif cmap == palettes.Colormaps.TSO:
                                    b, g, r = palettes.tso_line_palette_bgr(elm.get_max_bus_nominal_voltage(),
                                                                            abs(hvdc_loading[i]))

                                else:
                                    r, g, b, a = loading_cmap(abs(hvdc_loading[i]))
                                    r *= 255
                                    g *= 255
                                    b *= 255
                                    a *= 255

                                color = QColor(r, g, b, a)
                            else:
                                style = Qt.DashLine
                                color = Qt.gray

                            tooltip = str(i) + ': ' + elm.name
                            tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(
                                abs(hvdc_loading[i]) * 100) + ' [%]'

                            tooltip += '\nPower (from):\t' + "{:10.4f}".format(hvdc_Pf[i]) + ' [MW]'

                            if hvdc_losses is not None:
                                tooltip += '\nPower (to):\t' + "{:10.4f}".format(hvdc_Pt[i]) + ' [MW]'
                                tooltip += '\nLosses: \t\t' + "{:10.4f}".format(hvdc_losses[i]) + ' [MW]'
                                graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_Pf[i], Pt=hvdc_Pt[i])
                            else:
                                graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_Pf[i], Pt=-hvdc_Pf[i])

                            graphic_object.setToolTipText(tooltip)
                            graphic_object.set_colour(color, w, style)
                        else:
                            w = graphic_object.pen_width
                            style = Qt.DashLine
                            color = Qt.gray
                            graphic_object.set_pen(QPen(color, w, style))
                    else:
                        # No diagram object
                        pass
            else:
                error_msg("HVDC results length differs from the number of HVDC results. \n"
                          "Did you change the numbe rof devices? If so, re-run the simulation.")

    def get_selected(self) -> List[Tuple[ALL_DEV_TYPES, QGraphicsItem]]:
        """
        Get selection
        :return: List of EditableDevice, QGraphicsItem
        """
        return [(elm.api_object, elm) for elm in self.diagram_scene.selectedItems()]

    def get_selection_api_objects(self) -> List[ALL_DEV_TYPES]:
        """
        Get a list of the API objects from the selection
        :return: List[EditableDevice]
        """
        return [e.api_object for e in self.diagram_scene.selectedItems()]

    def get_selection_diagram(self) -> SchematicDiagram:
        """
        Get a SchematicDiagram of the current selection
        :return: SchematicDiagram
        """
        diagram = SchematicDiagram(name="Selection diagram")

        # first pass (only buses)
        bus_dict = dict()
        for item in self.diagram_scene.selectedItems():
            if isinstance(item, BusGraphicItem):
                # check that the bus is in the original diagram
                location = self.diagram.query_point(item.api_object)

                if location:
                    diagram.set_point(device=item.api_object, location=location)
                    bus_dict[item.api_object.idtag] = item
                else:
                    raise Exception('Item was selected but was not registered!')

        # second pass (Branches, and include their not selected buses)
        for item in self.diagram_scene.selectedItems():
            if isinstance(item, BRANCH_GRAPHICS):

                # add the element
                rect = item.boundingRect()
                diagram.set_point(device=item.api_object,
                                  location=GraphicLocation(x=rect.x(),
                                                           y=rect.y(),
                                                           h=rect.height(),
                                                           w=rect.width(),
                                                           r=item.rotation(),
                                                           api_object=item.api_object))

                # get the api buses from and to
                bus_from = item.api_object.bus_from
                bus_to = item.api_object.bus_to

                for bus in [bus_from, bus_to]:

                    # check that the bus is in the original diagram
                    location = self.diagram.query_point(bus)

                    if location and (bus.idtag not in bus_dict):
                        # if the bus was not added in the first
                        # pass and is in the original diagram, add it now
                        diagram.set_point(device=bus, location=location)
                        graphic_object = self.graphics_manager.query(elm=bus)
                        bus_dict[bus.idtag] = graphic_object

        # third pass: we must also add all those branches connecting the selected buses
        for lst in self.circuit.get_branch_lists():
            for api_object in lst:
                if api_object.bus_from.idtag in bus_dict or api_object.bus_to.idtag in bus_dict:
                    diagram.set_point(device=api_object,
                                      location=GraphicLocation(api_object=api_object))

        return diagram

    def try_to_fix_buses_location(self, buses_selection: List[Tuple[int, Bus, BusGraphicItem]]):
        """
        Try to fix the location of the null-location buses
        :param buses_selection: list of tuples index, bus object, graphic_object
        :return: indices of the corrected buses
        """
        delta = 1e20
        locations_cache = dict()

        for _ in range(100):
            # while delta > 10:

            A = self.circuit.get_adjacent_matrix()

            for k, bus, graphic_object in buses_selection:

                idx = list(self.circuit.get_adjacent_buses(A, k))

                # remove the elements already in the selection
                for i in range(len(idx) - 1, 0, -1):
                    if k == idx[i]:
                        idx.pop(i)

                x_arr = list()
                y_arr = list()
                for i in idx:

                    # try to get the location from the cache
                    loc_i = locations_cache.get(self.circuit.get_bus_at(i), None)

                    if loc_i is None:
                        # search and store
                        loc_i = self.diagram.query_point(self.circuit.get_bus_at(i))
                        locations_cache[self.circuit.get_bus_at(i)] = loc_i

                    x_arr.append(loc_i.x)
                    y_arr.append(loc_i.y)

                x_m = np.mean(x_arr)
                y_m = np.mean(y_arr)

                delta_i = np.sqrt((graphic_object.x() - x_m) ** 2 + (graphic_object.y() - y_m) ** 2)

                if delta_i < delta:
                    delta = delta_i

                self.update_diagram_element(device=bus,
                                            x=x_m,
                                            y=y_m,
                                            w=graphic_object.w,
                                            h=graphic_object.h,
                                            r=0,
                                            draw_labels=graphic_object.draw_labels,
                                            graphic_object=graphic_object)
                graphic_object.set_position(x=x_m, y=y_m)

        return

    def get_boundaries(self):
        """
        Get the graphic representation boundaries
        :return: min_x, max_x, min_y, max_y
        """

        # shrink selection only
        min_x, max_x, min_y, max_y = self.diagram.get_boundaries()

        return min_x, max_x, min_y, max_y

    def plot_bus(self, i, api_object: Bus):
        """
        Plot branch results
        :param i: branch index (not counting HVDC lines because those are not real Branches)
        :param api_object: Bus API object
        :return:
        """
        fig = plt.figure(figsize=(12, 8))
        ax_1 = fig.add_subplot(211)

        # set time
        x = self.circuit.get_time_array()

        if x is not None:
            if len(x) > 0:

                # Get all devices grouped by bus
                all_data = self.circuit.get_injection_devices_grouped_by_bus()

                # filter injections by bus
                bus_devices = all_data.get(api_object, None)

                voltage = dict()

                for key, driver in self.results_dictionary.items():
                    if hasattr(driver, 'results'):
                        if driver.results is not None:
                            if key == SimulationTypes.PowerFlowTimeSeries_run:
                                voltage[key] = np.abs(driver.results.voltage[:, i])

                # Injections
                if bus_devices:

                    power_data = dict()
                    for tpe_name, devices in bus_devices.items():
                        for device in devices:
                            if device.device_type == DeviceType.LoadDevice:
                                power_data[device.name] = -device.P_prof.toarray()
                            elif device.device_type == DeviceType.GeneratorDevice:
                                power_data[device.name] = device.P_prof.toarray()
                            elif device.device_type == DeviceType.ShuntDevice:
                                power_data[device.name] = -device.G_prof.toarray()
                            elif device.device_type == DeviceType.StaticGeneratorDevice:
                                power_data[device.name] = device.P_prof.toarray()
                            elif device.device_type == DeviceType.ExternalGridDevice:
                                power_data[device.name] = device.P_prof.toarray()
                            elif device.device_type == DeviceType.BatteryDevice:
                                power_data[device.name] = device.P_prof.toarray()
                            else:
                                raise Exception("Missing shunt device for plotting")

                    df = pd.DataFrame(data=power_data, index=x)
                    ax_1.set_title('Power', fontsize=14)
                    ax_1.set_ylabel('Injections [MW]', fontsize=11)
                    try:
                        # yt area plots
                        df.plot.area(ax=ax_1)
                    except ValueError:
                        # use regular plots
                        df.plot(ax=ax_1)

                # voltage
                if len(voltage.keys()):
                    ax_2 = fig.add_subplot(212, sharex=ax_1)
                    df = pd.DataFrame(data=voltage, index=x)
                    ax_2.set_title('Time', fontsize=14)
                    ax_2.set_ylabel('Voltage [p.u]', fontsize=11)
                    df.plot(ax=ax_2)

                plt.legend()
                fig.suptitle(api_object.name, fontsize=20)

                # plot the profiles
                plt.show()

    def split_line_now(self, line_graphics: LineGraphicItem, position: float, extra_km: float):
        """

        :param line_graphics:
        :param position:
        :param extra_km:
        :return:
        """

        if 0.0 < position < 1.0:
            original_line = line_graphics.api_object
            mid_sub, mid_vl, mid_bus, br1, br2 = self.circuit.split_line(original_line=original_line,
                                                                         position=position,
                                                                         extra_km=extra_km)

            bus_f_graphics_data = self.diagram.query_point(original_line.bus_from)
            bus_t_graphics_data = self.diagram.query_point(original_line.bus_to)
            bus_f_graphic_obj = self.graphics_manager.query(original_line.bus_from)
            bus_t_graphic_obj = self.graphics_manager.query(original_line.bus_to)

            if bus_f_graphics_data is None:
                error_msg(f"{original_line.bus_from} was not found in the diagram")
                return None
            if bus_t_graphics_data is None:
                error_msg(f"{original_line.bus_to} was not found in the diagram")
                return None
            if bus_f_graphic_obj is None:
                error_msg(f"{original_line.bus_from} was not found in the graphics manager")
                return None
            if bus_t_graphic_obj is None:
                error_msg(f"{original_line.bus_to} was not found in the graphics manager")
                return None

            # C(x, y) = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
            middle_bus_x = int(bus_f_graphics_data.x + (bus_t_graphics_data.x - bus_f_graphics_data.x) * position)
            middle_bus_y = int(bus_f_graphics_data.y + (bus_t_graphics_data.y - bus_f_graphics_data.y) * position)

            # disable the original graphic
            line_graphics.set_enable(False)

            # add to the schematic the new 2 lines and the bus
            middle_bus_graphics = self.add_api_bus(bus=mid_bus,
                                                   injections_by_tpe=dict(),
                                                   x0=middle_bus_x,
                                                   y0=middle_bus_y)
            br1_graphics = self.add_api_line(branch=br1,
                                             from_port=bus_f_graphic_obj.get_terminal(),
                                             to_port=middle_bus_graphics.get_terminal())
            br2_graphics = self.add_api_line(branch=br2,
                                             from_port=middle_bus_graphics.get_terminal(),
                                             to_port=bus_t_graphic_obj.get_terminal())

            self.add_to_scene(middle_bus_graphics)
            self.add_to_scene(br1_graphics)
            self.add_to_scene(br2_graphics)

            # redraw
            bus_f_graphic_obj.arrange_children()
            bus_t_graphic_obj.arrange_children()
            middle_bus_graphics.arrange_children()
        else:
            error_msg("Incorrect position", 'Line split')

    def split_line(self, line_graphics: LineGraphicItem):
        """
        Split line
        :return:
        """
        dlg = InputNumberDialogue(min_value=1.0,
                                  max_value=99.0,
                                  is_int=False,
                                  title="Split line",
                                  text="Enter the distance from the beginning of the \n"
                                       "line as a percentage of the total length",
                                  suffix=' %',
                                  decimals=2,
                                  default_value=50.0)
        if dlg.exec_():

            if dlg.is_accepted:
                position = dlg.value / 100.0

                self.split_line_now(line_graphics=line_graphics,
                                    position=position,
                                    extra_km=0.0)

    def split_line_in_out(self, line_graphics: LineGraphicItem):
        """
        Split line and create extra substations so that an in/out is formed
        :param line_graphics: Original LineGraphicItem to split
        """
        title = "Split line with input/output"
        dlg = InputNumberDialogue(min_value=1.0,
                                  max_value=99.0,
                                  is_int=False,
                                  title=title,
                                  text="Enter the distance from the beginning of the \n"
                                       "line as a percentage of the total length",
                                  suffix=' %',
                                  decimals=2,
                                  default_value=50.0)
        if dlg.exec_():

            if dlg.is_accepted:

                position = dlg.value / 100.0

                if 0.0 < position < 1.0:

                    dlg2 = InputNumberDialogue(min_value=0.01,
                                               max_value=99999999.0,
                                               is_int=False,
                                               title=title,
                                               text="Distance from the splitting point",
                                               suffix=' km',
                                               decimals=2,
                                               default_value=1.0)

                    if dlg2.exec_():

                        if dlg2.is_accepted:

                            create_extra_nodes = yes_no_question(text="Add extra buses?", title=title)

                            if create_extra_nodes:

                                original_line = line_graphics.api_object

                                (mid_sub, mid_vl,
                                 B1, B2, B3,
                                 br1, br2, br3, br4) = self.circuit.split_line_int_out(original_line=original_line,
                                                                                       position=position,
                                                                                       km_io=dlg2.value)

                                bus_f_graphics_data = self.diagram.query_point(original_line.bus_from)
                                bus_t_graphics_data = self.diagram.query_point(original_line.bus_to)
                                bus_f_graphic_obj = self.graphics_manager.query(original_line.bus_from)
                                bus_t_graphic_obj = self.graphics_manager.query(original_line.bus_to)

                                if bus_f_graphics_data is None:
                                    error_msg(f"{original_line.bus_from} was not found in the diagram")
                                    return None
                                if bus_t_graphics_data is None:
                                    error_msg(f"{original_line.bus_to} was not found in the diagram")
                                    return None
                                if bus_f_graphic_obj is None:
                                    error_msg(f"{original_line.bus_from} was not found in the graphics manager")
                                    return None
                                if bus_t_graphic_obj is None:
                                    error_msg(f"{original_line.bus_to} was not found in the graphics manager")
                                    return None

                                # C(x, y) = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
                                mid_x = bus_f_graphics_data.x + (
                                        bus_t_graphics_data.x - bus_f_graphics_data.x) * position
                                mid_y = bus_f_graphics_data.y + (
                                        bus_t_graphics_data.y - bus_f_graphics_data.y) * position

                                # deactivate the original line
                                line_graphics.set_enable(False)

                                # add to the schematic the new 2 lines and the bus
                                B1_graphics = self.add_api_bus(bus=B1,
                                                               injections_by_tpe=dict(),
                                                               x0=mid_x,
                                                               y0=mid_y)

                                B2_graphics = self.add_api_bus(bus=B2,
                                                               injections_by_tpe=dict(),
                                                               x0=mid_x,
                                                               y0=mid_y)

                                B3_graphics = self.add_api_bus(bus=B3,
                                                               injections_by_tpe=dict(),
                                                               x0=mid_x,
                                                               y0=mid_y)

                                br1_graphics = self.add_api_line(branch=br1,
                                                                 from_port=bus_f_graphic_obj.get_terminal(),
                                                                 to_port=B1_graphics.get_terminal())

                                br2_graphics = self.add_api_line(branch=br2,
                                                                 from_port=B2_graphics.get_terminal(),
                                                                 to_port=bus_t_graphic_obj.get_terminal())

                                br3_graphics = self.add_api_line(branch=br3,
                                                                 from_port=B1_graphics.get_terminal(),
                                                                 to_port=B3_graphics.get_terminal())

                                br4_graphics = self.add_api_line(branch=br4,
                                                                 from_port=B3_graphics.get_terminal(),
                                                                 to_port=B2_graphics.get_terminal())

                                self.add_to_scene(B1_graphics)
                                self.add_to_scene(B2_graphics)
                                self.add_to_scene(B3_graphics)
                                self.add_to_scene(br1_graphics)
                                self.add_to_scene(br2_graphics)
                                self.add_to_scene(br3_graphics)
                                self.add_to_scene(br4_graphics)

                                # redraw
                                bus_f_graphic_obj.arrange_children()
                                bus_t_graphic_obj.arrange_children()
                                B1_graphics.arrange_children()
                                B2_graphics.arrange_children()
                                B3_graphics.arrange_children()
                            else:
                                self.split_line_now(line_graphics=line_graphics,
                                                    position=position,
                                                    extra_km=dlg2.value)
                        else:
                            pass
                else:
                    error_msg("Incorrect position", 'Line split')

    def change_bus(self, line_graphics: LineGraphicTemplateItem):
        """
        change the from or to bus of the nbranch with another selected bus
        :param line_graphics
        """

        idx_bus_list = self.get_selected_buses()

        if len(idx_bus_list) == 2:

            # detect the bus and its combinations
            if idx_bus_list[0][1] == line_graphics.api_object.bus_from:
                idx, old_bus, old_bus_graphic_item = idx_bus_list[0]
                idx, new_bus, new_bus_graphic_item = idx_bus_list[1]
                side = 'f'
            elif idx_bus_list[1][1] == line_graphics.api_object.bus_from:
                idx, new_bus, new_bus_graphic_item = idx_bus_list[0]
                idx, old_bus, old_bus_graphic_item = idx_bus_list[1]
                side = 'f'
            elif idx_bus_list[0][1] == line_graphics.api_object.bus_to:
                idx, old_bus, old_bus_graphic_item = idx_bus_list[0]
                idx, new_bus, new_bus_graphic_item = idx_bus_list[1]
                side = 't'
            elif idx_bus_list[1][1] == line_graphics.api_object.bus_to:
                idx, new_bus, new_bus_graphic_item = idx_bus_list[0]
                idx, old_bus, old_bus_graphic_item = idx_bus_list[1]
                side = 't'
            else:
                error_msg(text="The 'from' or 'to' bus to change has not been selected!",
                          title='Change bus')
                return

            ok = yes_no_question(text=f"Are you sure that you want to relocate the bus "
                                      f"from {old_bus.name} to {new_bus.name}?",
                                 title='Change bus')

            if ok:
                if side == 'f':
                    line_graphics.api_object.bus_from = new_bus
                    line_graphics.set_from_port(new_bus_graphic_item.get_terminal())
                elif side == 't':
                    line_graphics.api_object.bus_to = new_bus
                    line_graphics.set_to_port(new_bus_graphic_item.get_terminal())
                else:
                    raise Exception('Unsupported side value {}'.format(side))

                # Add this line to the new connection bus
                # new_bus_graphic_item.add_hosting_connection(graphic_obj=line_graphics)
                # new_bus_graphic_item.get_terminal().update()
                #
                # # remove thid line from the old bus connections
                # old_bus_graphic_item.delete_hosting_connection(graphic_obj=line_graphics)
                # old_bus_graphic_item.get_terminal().update()
        else:
            warning_msg("you must select the origin and destination buses!",
                        title='Change bus')

    def set_generator_control_bus(self, generator_graphics: GeneratorGraphicItem):
        """
        change the from or to bus of the nbranch with another selected bus
        :param generator_graphics
        """

        idx_bus_list = self.get_selected_buses()

        if len(idx_bus_list) == 1:

            # detect the bus and its combinations
            idx, sel_bus, sel_bus_graphic_item = idx_bus_list[0]

            generator_graphics.api_object.control_bus = sel_bus

            if (yes_no_question(text="Do you want to set the profile?", title="Set regulation bus")
                    and self.circuit.has_time_series):
                generator_graphics.api_object.control_bus_prof.fill(sel_bus)

        else:
            error_msg(text="You need to select exactly one bus to be set as the generator regulation bus",
                      title="Set regulation bus")

    def set_generator_control_cn(self, generator_graphics: GeneratorGraphicItem):
        """
        change the from or to bus of the nbranch with another selected bus
        :param generator_graphics
        """

        idx_bus_list = self.get_selected_cn()

        if len(idx_bus_list) == 1:

            # detect the bus and its combinations
            idx, sel_bus, sel_bus_graphic_item = idx_bus_list[0]

            generator_graphics.api_object.control_cn = sel_bus

        else:
            error_msg("You need to select exactly one bus to be set as the generator regulation connectivity node",
                      "Set regulation connectivity node")

    def set_branch_control_bus(self, line_graphics: LineGraphicTemplateItem):
        """
        change the from or to bus of the nbranch with another selected bus
        :param line_graphics
        """

        idx_bus_list = self.get_selected_buses()

        if len(idx_bus_list) == 2:

            # detect the bus and its combinations
            if idx_bus_list[0][1] == line_graphics.api_object.bus_from:
                idx, old_bus, old_bus_graphic_item = idx_bus_list[0]

    # def disable_all_results_tags(self):
    #     """
    #     Disable all results' tags in this diagram
    #     """
    #     for device_tpe, type_dict in self.graphics_manager.graphic_dict.items():
    #         for key, widget in type_dict.items():
    #             widget.disable_label_drawing()
    #
    # def enable_all_results_tags(self):
    #     """
    #     Enable all results' tags in this diagram
    #     """
    #     for device_tpe, type_dict in self.graphics_manager.graphic_dict.items():
    #         for key, widget in type_dict.items():
    #             widget.enable_label_drawing()

    def get_picture_width(self) -> int:
        return self.editor_graphics_view.width()

    def get_picture_height(self) -> int:
        return self.editor_graphics_view.height()

    # def start_video_recording(self, fname: str, fps: int = 30) -> Tuple[int, int]:
    #     """
    #     Save video
    #     :param fname: file name
    #     :param fps: frames per second
    #     :returns width, height
    #     """
    #
    #     w = self.editor_graphics_view.width()
    #     h = self.editor_graphics_view.height()
    #
    #     self._video = cv2.VideoWriter(filename=fname,
    #                                   fourcc=cv2.VideoWriter_fourcc(*'mp4v'),
    #                                   fps=fps,
    #                                   frameSize=(w, h))
    #
    #     return w, h

    # def capture_video_frame(self) -> None:
    #     """
    #     Save the current state in a video frame
    #     """
    #
    #     image, w, h = self.get_image(transparent=False)
    #
    #     # convert picture using the memory
    #     # we need to remove the alpha channel, otherwise the video frame is not saved
    #     frame = np.array(image.constBits()).reshape(h, w, 4).astype(np.uint8)[:, :, :3]
    #     self._video.write(frame)


def generate_schematic_diagram(buses: List[Bus],
                               busbars: List[BusBar],
                               connecivity_nodes: List[ConnectivityNode],
                               lines: List[Line],
                               dc_lines: List[DcLine],
                               transformers2w: List[Transformer2W],
                               transformers3w: List[Transformer3W],
                               windings: List[Winding],
                               hvdc_lines: List[HvdcLine],
                               vsc_devices: List[VSC],
                               upfc_devices: List[UPFC],
                               series_reactances: List[SeriesReactance],
                               switches: List[Switch],
                               fluid_nodes: List[FluidNode],
                               fluid_paths: List[FluidPath],
                               explode_factor=1.0,
                               prog_func: Union[Callable, None] = None,
                               text_func: Union[Callable, None] = None,
                               name='Bus branch diagram') -> SchematicDiagram:
    """
    Add a elements to the schematic scene
    :param buses: list of Bus objects
    :param busbars: List of Bus bars
    :param connecivity_nodes: List of ConnectivityNode objects
    :param lines: list of Line objects
    :param dc_lines: list of DcLine objects
    :param transformers2w: list of Transformer Objects
    :param transformers3w: list of Transformer3W Objects
    :param windings: list of Winding objects
    :param hvdc_lines: list of HvdcLine objects
    :param vsc_devices: list Vsc objects
    :param upfc_devices: List of UPFC devices
    :param series_reactances: List of SeriesReactance
    :param switches: List of Switch
    :param fluid_nodes: List of FluidNode
    :param fluid_paths: List of FluidPath
    :param explode_factor: factor of "explosion": Separation of the nodes factor
    :param prog_func: progress report function
    :param text_func: Text report function
    :param name: name of the diagram
    """

    diagram = SchematicDiagram(name=name)

    # first create the buses
    if text_func is not None:
        text_func('Creating schematic buses')

    nn = len(buses)
    for i, bus in enumerate(buses):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        if not bus.is_internal:  # 3w transformer buses are not represented

            # correct possible nonsense
            if np.isnan(bus.y):
                bus.y = 0.0
            if np.isnan(bus.x):
                bus.x = 0.0

            x = int(bus.x * explode_factor)
            y = int(bus.y * explode_factor)
            diagram.set_point(device=bus, location=GraphicLocation(x=x, y=y, h=bus.h, w=bus.w))

    def add_devices_list(cls: str, dev_lst: List[ALL_DEV_TYPES]):
        """

        :param cls:
        :param dev_lst:
        """
        if text_func is not None:
            text_func(f'Adding {cls} devices to the diagram')

        nn = len(dev_lst)
        for i, elm in enumerate(dev_lst):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            diagram.set_point(device=elm, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------

    add_devices_list(cls="busbars", dev_lst=busbars)
    add_devices_list(cls="connecivity_nodes", dev_lst=connecivity_nodes)
    add_devices_list(cls="fluid_nodes", dev_lst=fluid_nodes)
    add_devices_list(cls="transformers3w", dev_lst=transformers3w)

    add_devices_list(cls="lines", dev_lst=lines)
    add_devices_list(cls="dc_lines", dev_lst=dc_lines)
    add_devices_list(cls="transformers2w", dev_lst=transformers2w)
    add_devices_list(cls="series_reactances", dev_lst=series_reactances)
    add_devices_list(cls="switches", dev_lst=switches)
    add_devices_list(cls="windings", dev_lst=windings)
    add_devices_list(cls="hvdc_lines", dev_lst=hvdc_lines)
    add_devices_list(cls="vsc_devices", dev_lst=vsc_devices)
    add_devices_list(cls="upfc_devices", dev_lst=upfc_devices)
    add_devices_list(cls="fluid_paths", dev_lst=fluid_paths)

    # --------------------------------------------------------------------------------------------------------------
    # if text_func is not None:
    #     text_func('Creating schematic transformer3w devices')
    #
    # nn = len(transformers3w)
    # for i, elm in enumerate(transformers3w):
    #
    #     if prog_func is not None:
    #         prog_func((i + 1) / nn * 100.0)
    #
    #     x = int(elm.x * explode_factor)
    #     y = int(elm.y * explode_factor)
    #     diagram.set_point(device=elm, location=GraphicLocation(x=x, y=y))
    #     diagram.set_point(device=elm.winding1, location=GraphicLocation())
    #     diagram.set_point(device=elm.winding2, location=GraphicLocation())
    #     diagram.set_point(device=elm.winding3, location=GraphicLocation())

    return diagram


def get_devices_to_expand(circuit: MultiCircuit, root_bus: Bus, max_level: int = 1) -> Tuple[List[Bus],
List[BusBar],
List[ConnectivityNode],
List[Line],
List[DcLine],
List[Transformer2W],
List[Transformer3W],
List[Winding],
List[HvdcLine],
List[VSC],
List[UPFC],
List[SeriesReactance],
List[Switch],
List[FluidNode],
List[FluidPath]]:
    """
    get lists of devices to expand given a root bus
    :param circuit: MultiCircuit
    :param root_bus: Bus
    :param max_level: max expansion level
    :return:
    """

    branch_idx = list()
    bus_idx = list()

    bus_dict = circuit.get_bus_index_dict()

    # get all Branches
    all_branches = circuit.get_branches()
    branch_dict = {b: i for i, b in enumerate(all_branches)}

    # create a pool of buses
    bus_pool = [(root_bus, 0)]  # store the bus objects and their level from the root

    buses = set()
    busbars = set()
    cns = set()
    fluid_nodes = set()
    selected_branches = set()

    while len(bus_pool) > 0:

        # search the next bus
        bus, level = bus_pool.pop()

        bus_idx.append(bus_dict[bus])

        # add searched bus
        buses.add(bus)

        if level < max_level:

            for i, br in enumerate(all_branches):

                if br.bus_from == bus:
                    bus_pool.append((br.bus_to, level + 1))
                    selected_branches.add(br)

                elif br.bus_to == bus:
                    bus_pool.append((br.bus_from, level + 1))
                    selected_branches.add(br)

                else:
                    pass

    # sort Branches
    lines: List[Line] = list()
    dc_lines: List[DcLine] = list()
    transformers2w: List[Transformer2W] = list()
    transformers3w: List[Transformer3W] = list()
    windings: List[Winding] = list()
    hvdc_lines: List[HvdcLine] = list()
    vsc_converters: List[VSC] = list()
    upfc_devices: List[UPFC] = list()
    series_reactances: List[SeriesReactance] = list()
    switches: List[Switch] = list()
    fluid_paths: List[FluidPath] = list()

    for obj in selected_branches:

        branch_idx.append(branch_dict[obj])

        if obj.device_type == DeviceType.LineDevice:
            lines.append(obj)

        elif obj.device_type == DeviceType.DCLineDevice:
            dc_lines.append(obj)

        elif obj.device_type == DeviceType.Transformer2WDevice:
            transformers2w.append(obj)

        elif obj.device_type == DeviceType.Transformer3WDevice:
            transformers3w.append(obj)

        elif obj.device_type == DeviceType.WindingDevice:
            windings.append(obj)

        elif obj.device_type == DeviceType.HVDCLineDevice:
            hvdc_lines.append(obj)

        elif obj.device_type == DeviceType.VscDevice:
            vsc_converters.append(obj)

        elif obj.device_type == DeviceType.UpfcDevice:
            upfc_devices.append(obj)

        elif obj.device_type == DeviceType.SeriesReactanceDevice:
            series_reactances.append(obj)

        elif obj.device_type == DeviceType.SwitchDevice:
            switches.append(obj)

        else:
            raise Exception('Unrecognized branch type ' + obj.device_type.value)

    return (list(buses), list(busbars), list(cns), lines, dc_lines, transformers2w, transformers3w,
            windings, hvdc_lines, vsc_converters, upfc_devices, series_reactances, switches,
            list(fluid_nodes), fluid_paths)


def make_vecinity_diagram(circuit: MultiCircuit,
                          root_bus: Bus,
                          max_level: int = 1,
                          prog_func: Union[Callable, None] = None,
                          text_func: Union[Callable, None] = None):
    """
    Create a vecinity diagram
    :param circuit: MultiCircuit
    :param root_bus: Bus
    :param max_level: max expansion level
    :param prog_func:
    :param text_func:
    :return:
    """

    (buses, busbars, cns,
     lines, dc_lines, transformers2w,
     transformers3w, windings, hvdc_lines,
     vsc_converters, upfc_devices,
     series_reactances, switches,
     fluid_nodes, fluid_paths) = get_devices_to_expand(circuit=circuit, root_bus=root_bus, max_level=max_level)

    # Draw schematic subset
    diagram = generate_schematic_diagram(buses=list(buses),
                                         busbars=busbars,
                                         connecivity_nodes=cns,
                                         lines=lines,
                                         dc_lines=dc_lines,
                                         transformers2w=transformers2w,
                                         transformers3w=transformers3w,
                                         windings=windings,
                                         hvdc_lines=hvdc_lines,
                                         vsc_devices=vsc_converters,
                                         upfc_devices=upfc_devices,
                                         series_reactances=series_reactances,
                                         switches=switches,
                                         fluid_nodes=list(fluid_nodes),
                                         fluid_paths=fluid_paths,
                                         explode_factor=1.0,
                                         prog_func=prog_func,
                                         text_func=text_func,
                                         name=root_bus.name + 'vecinity')

    return diagram
