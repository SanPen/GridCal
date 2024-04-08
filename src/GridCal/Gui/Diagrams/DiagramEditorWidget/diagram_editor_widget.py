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

from PySide6.QtCore import (Qt, QPoint, QSize, QPointF, QRect, QRectF, QMimeData, QIODevice, QByteArray,
                            QDataStream, QModelIndex)
from PySide6.QtGui import (QIcon, QPixmap, QImage, QPainter, QStandardItemModel, QStandardItem, QColor, QPen,
                           QDragEnterEvent, QDragMoveEvent, QDropEvent, QWheelEvent, QKeyEvent, QMouseEvent,
                           QContextMenuEvent)
from PySide6.QtWidgets import (QGraphicsView, QListView, QTableView, QVBoxLayout, QHBoxLayout, QFrame,
                               QSplitter, QMessageBox, QAbstractItemView, QGraphicsScene, QGraphicsSceneMouseEvent,
                               QGraphicsItem, QGraphicsTextItem, QMenu, QWidget)
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
from GridCalEngine.Devices.Branches.series_reactance import SeriesReactance
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Devices.Branches.transformer3w import Transformer3W, Winding
from GridCalEngine.Devices.Injections.generator import Generator
from GridCalEngine.Devices.Fluid import FluidNode, FluidPath
from GridCalEngine.Devices.Aggregation.investments_group import InvestmentsGroup
from GridCalEngine.Devices.Aggregation.investment import Investment
from GridCalEngine.Devices.Diagrams.bus_branch_diagram import BusBranchDiagram
from GridCalEngine.Devices.Diagrams.graphic_location import GraphicLocation
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.basic_structures import Vec, CxVec, IntVec, Logger
from GridCalEngine.Devices.types import BRANCH_TYPES

from GridCal.Gui.Diagrams.graphics_manager import GraphicsManager
from GridCal.Gui.Diagrams.DiagramEditorWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Substation.bus_graphics import BusGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Substation.cn_graphics import CnGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Substation.busbar_graphics import BusBarGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Fluid.fluid_path_graphics import FluidPathGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.line_graphics import LineGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.winding_graphics import WindingGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.dc_line_graphics import DcLineGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.transformer2w_graphics import TransformerGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.hvdc_graphics import HvdcGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.vsc_graphics import VscGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.upfc_graphics import UpfcGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.series_reactance_graphics import SeriesReactanceGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Branches.transformer3w_graphics import Transformer3WGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.Injections.generator_graphics import GeneratorGraphicItem
from GridCal.Gui.Diagrams.DiagramEditorWidget.generic_graphics import ACTIVE
from GridCal.Gui.GeneralDialogues import InputNumberDialogue
import GridCal.Gui.Visualization.visualization as viz
import GridCal.Gui.Visualization.palettes as palettes
from GridCal.Gui.GuiFunctions import ObjectsModel, add_menu_entry
from GridCal.Gui.messages import info_msg, error_msg, warning_msg, yes_no_question
from matplotlib import pyplot as plt

'''
Structure:

{DiagramEditorWidget: QSplitter}
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


class BusBranchLibraryModel(QStandardItemModel):
    """
    Items model to host the draggable icons
    This is the list of draggable items
    """

    def __init__(self, parent: "DiagramEditorWidget" = None) -> None:
        """
        Items model to host the draggable icons
        @param parent:
        """
        QStandardItemModel.__init__(self, parent)

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


class BusBranchDiagramScene(QGraphicsScene):
    """
    DiagramScene
    This class is needed to augment the mouse move and release events
    """

    def __init__(self, parent: "DiagramEditorWidget"):
        """

        :param parent:
        """
        super(BusBranchDiagramScene, self).__init__(parent)
        self.parent_ = parent
        self.displacement = QPoint(0, 0)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """
        self.parent_.scene_mouse_move_event(event)

        # call the parent event
        super(BusBranchDiagramScene, self).mouseMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        :param event:
        :return:
        """
        self.parent_.scene_mouse_press_event(event)
        self.displacement = QPointF(0, 0)
        super(BusBranchDiagramScene, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        @param event:
        @return:
        """
        self.parent_.create_branch_on_mouse_release_event(event)

        # call mouseReleaseEvent on "me" (conti
        #
        # nue with the rest of the actions)
        super(BusBranchDiagramScene, self).mouseReleaseEvent(event)

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

    def __init__(self, scene: QGraphicsScene, parent: "BusBranchDiagramScene"):
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


def find_my_node(idtag_: str,
                 bus_dict: Dict[str, BusGraphicItem],
                 fluid_node_dict: Dict[str, FluidNodeGraphicItem]):
    """
    Function to look for the bus or fluid node
    :param idtag_: bus or fluidnode idtag
    :param bus_dict:
    :param fluid_node_dict:
    :return: Matching graphic object
    """
    graphic_obj = bus_dict.get(idtag_, None)
    if graphic_obj is None:
        graphic_obj = fluid_node_dict.get(idtag_, None)
    return graphic_obj


class DiagramEditorWidget(QSplitter):
    """
    DiagramEditorWidget
    This is the bus-branch editor
    """

    def __init__(self,
                 circuit: MultiCircuit,
                 diagram: Union[BusBranchDiagram, None],
                 default_bus_voltage: float = 10.0,
                 time_index: Union[None, int] = None):
        """
        Creates the Diagram Editor (DiagramEditorWidget)
        :param circuit: Circuit that is handling
        :param diagram: BusBranchDiagram to use (optional)
        :param default_bus_voltage: Default bus voltages (kV)
        :param time_index: time index to represent
        """

        QSplitter.__init__(self)

        # store a reference to the multi circuit instance
        self.circuit: MultiCircuit = circuit

        # diagram to store the objects locations
        self.diagram: BusBranchDiagram = diagram
        self.graphics_manager = GraphicsManager()

        # default_bus_voltage (kV)
        self.default_bus_voltage = default_bus_voltage

        # nodes distance "explosion" factor
        self.expand_factor = 1.1

        # Widget layout and child widgets:
        self.horizontal_layout = QHBoxLayout(self)
        self.object_editor_table = QTableView(self)

        # library model
        self.library_model = BusBranchLibraryModel(self)

        # Actual libraryView object
        self.library_view = QListView(self)
        self.library_view.setModel(self.library_model)
        self.library_view.setViewMode(self.library_view.ViewMode.ListMode)
        self.library_view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

        # create all the schematic objects and replace the existing ones
        self.diagram_scene = BusBranchDiagramScene(parent=self)  # scene to add to the QGraphicsView

        self.results_dictionary = dict()

        self.editor_graphics_view = CustomGraphicsView(self.diagram_scene, parent=self)

        # override events
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
        splitter2.setStretchFactor(0, 2)
        splitter2.setStretchFactor(1, 5)

        self.setStretchFactor(0, 0)
        self.setStretchFactor(1, 2000)

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

        # current time index from the GUI (None or 0, 1, 2, ..., n-1)
        self._time_index: Union[None, int] = time_index

        if diagram is not None:
            self.draw()

        # Note: Do not declare any variable beyond here, as it may bnot be considered if draw is called :/

    def set_time_index(self, time_index: Union[int, None]):
        """
        Set the time index of the table
        :param time_index: None or integer value
        """
        self._time_index = time_index

        mdl = self.object_editor_table.model()
        if isinstance(mdl, ObjectsModel):
            mdl.set_time_index(time_index=self._time_index)

    def get_time_index(self) -> Union[int, None]:
        """
        Get the time index
        :return: int, None
        """
        return self._time_index

    def set_editor_model(self,
                         api_object: ALL_DEV_TYPES,
                         dictionary_of_lists: Union[None, Dict[str, List[ALL_DEV_TYPES]]] = None):
        """
        Set an api object to appear in the editable table view of the editor
        :param api_object: any EditableDevice
        :param dictionary_of_lists: dictionary of lists of objects that may be referenced to
        """
        mdl = ObjectsModel(objects=[api_object],
                           property_list=api_object.property_list,
                           time_index=self.get_time_index(),
                           parent=self.object_editor_table,
                           editable=True,
                           transposed=True,
                           dictionary_of_lists=dictionary_of_lists if dictionary_of_lists is not None else dict())

        self.object_editor_table.setModel(mdl)

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
                obj = Bus(name=f'Bus {self.circuit.get_bus_number()}', vnom=self.default_bus_voltage)
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

    def create_connectivity_node_graphics(self, node: ConnectivityNode, x: int, y: int, h: int,
                                          w: int) -> CnGraphicItem:
        """
        Add connectivity node to graphics
        :param node: GridCal connectivity node object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :return: CnGraphicItem
        """

        graphic_object = CnGraphicItem(editor=self, node=node, x=x, y=y, h=h, w=w)
        return graphic_object

    def create_bus_bar_graphics(self, node: BusBar, x: int, y: int, h: int, w: int) -> BusBarGraphicItem:
        """
        Add bus bar node to graphics
        :param node: GridCal BusBar object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :return: BusBarGraphicItem
        """

        graphic_object = BusBarGraphicItem(editor=self, node=node, x=x, y=y, h=h, w=w)
        return graphic_object

    def set_data(self, circuit: MultiCircuit, diagram: BusBranchDiagram):
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
        inj_dev_by_bus = self.circuit.get_injection_devices_grouped_by_bus()
        inj_dev_by_fluid_node = self.circuit.get_injection_devices_grouped_by_fluid_node()

        # add buses first
        bus_dict: Dict[str, BusGraphicItem] = dict()
        fluid_node_dict: Dict[str, FluidNodeGraphicItem] = dict()
        windings_dict: Dict[str, WindingGraphicItem] = dict()
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
                    graphic_object.create_children_widgets(
                        injections_by_tpe=inj_dev_by_bus.get(location.api_object, dict())
                    )

                    graphic_object.change_size(w=location.w)

                    # add buses reference for later
                    bus_dict[idtag] = graphic_object
                    self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.Transformer3WDevice.value:

                for idtag, location in points_group.locations.items():
                    elm: Transformer3W = location.api_object

                    graphic_object = self.create_transformer_3w_graphics(elm=elm,
                                                                         x=location.x,
                                                                         y=location.y)
                    self.add_to_scene(graphic_object=graphic_object)

                    bus_1_graphic = bus_dict[elm.bus1.idtag]
                    bus_2_graphic = bus_dict[elm.bus2.idtag]
                    bus_3_graphic = bus_dict[elm.bus3.idtag]

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
                    windings_dict[elm.winding1.idtag] = conn1
                    windings_dict[elm.winding2.idtag] = conn2
                    windings_dict[elm.winding3.idtag] = conn3

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
                    graphic_object.create_children_widgets(
                        injections_by_tpe=inj_dev_by_fluid_node.get(location.api_object, dict()))

                    graphic_object.change_size(h=location.h,
                                               w=location.w)

                    # add fluid node reference for later
                    fluid_node_dict[idtag] = graphic_object
                    self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

                    # map the internal bus
                    # if location.api_object.bus is not None:
                    #     bus_dict[location.api_object.bus.idtag] = graphic_object

            else:
                # pass for now...
                pass

        # add the rest of the branches
        for category, points_group in self.diagram.data.items():

            if category == DeviceType.LineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: Line = location.api_object
                    if branch.bus_from is not None and branch.bus_to is not None:
                        bus_f_graphic_obj = find_my_node(branch.bus_from.idtag, bus_dict, fluid_node_dict)
                        bus_t_graphic_obj = find_my_node(branch.bus_to.idtag, bus_dict, fluid_node_dict)

                        if bus_f_graphic_obj and bus_t_graphic_obj:
                            graphic_object = LineGraphicItem(from_port=bus_f_graphic_obj.get_terminal(),
                                                             to_port=bus_t_graphic_obj.get_terminal(),
                                                             editor=self,
                                                             api_object=branch)
                            self.add_to_scene(graphic_object=graphic_object)

                            graphic_object.redraw()
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.DCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: DcLine = location.api_object
                    if branch.bus_from is not None and branch.bus_to is not None:
                        bus_f_graphic_obj = find_my_node(branch.bus_from.idtag, bus_dict, fluid_node_dict)
                        bus_t_graphic_obj = find_my_node(branch.bus_to.idtag, bus_dict, fluid_node_dict)

                        if bus_f_graphic_obj and bus_t_graphic_obj:
                            graphic_object = DcLineGraphicItem(from_port=bus_f_graphic_obj.get_terminal(),
                                                               to_port=bus_t_graphic_obj.get_terminal(),
                                                               editor=self,
                                                               api_object=branch)
                            self.add_to_scene(graphic_object=graphic_object)

                            graphic_object.redraw()
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.HVDCLineDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: HvdcLine = location.api_object
                    if branch.bus_from is not None and branch.bus_to is not None:
                        bus_f_graphic_obj = find_my_node(branch.bus_from.idtag, bus_dict, fluid_node_dict)
                        bus_t_graphic_obj = find_my_node(branch.bus_to.idtag, bus_dict, fluid_node_dict)

                        if bus_f_graphic_obj and bus_t_graphic_obj:
                            graphic_object = HvdcGraphicItem(from_port=bus_f_graphic_obj.get_terminal(),
                                                             to_port=bus_t_graphic_obj.get_terminal(),
                                                             editor=self,
                                                             api_object=branch)
                            self.add_to_scene(graphic_object=graphic_object)

                            graphic_object.redraw()
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.VscDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: VSC = location.api_object
                    if branch.bus_from is not None and branch.bus_to is not None:
                        bus_f_graphic_obj = find_my_node(branch.bus_from.idtag, bus_dict, fluid_node_dict)
                        bus_t_graphic_obj = find_my_node(branch.bus_to.idtag, bus_dict, fluid_node_dict)

                        if bus_f_graphic_obj and bus_t_graphic_obj:
                            graphic_object = VscGraphicItem(from_port=bus_f_graphic_obj.get_terminal(),
                                                            to_port=bus_t_graphic_obj.get_terminal(),
                                                            editor=self,
                                                            api_object=branch)
                            self.add_to_scene(graphic_object=graphic_object)

                            graphic_object.redraw()
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.UpfcDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: UPFC = location.api_object
                    if branch.bus_from is not None and branch.bus_to is not None:
                        bus_f_graphic_obj = find_my_node(branch.bus_from.idtag, bus_dict, fluid_node_dict)
                        bus_t_graphic_obj = find_my_node(branch.bus_to.idtag, bus_dict, fluid_node_dict)

                        if bus_f_graphic_obj and bus_t_graphic_obj:
                            graphic_object = UpfcGraphicItem(from_port=bus_f_graphic_obj.get_terminal(),
                                                             to_port=bus_t_graphic_obj.get_terminal(),
                                                             editor=self,
                                                             api_object=branch)
                            self.add_to_scene(graphic_object=graphic_object)

                            graphic_object.redraw()
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.Transformer2WDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: Transformer2W = location.api_object
                    if branch.bus_from is not None and branch.bus_to is not None:
                        bus_f_graphic_obj = find_my_node(branch.bus_from.idtag, bus_dict, fluid_node_dict)
                        bus_t_graphic_obj = find_my_node(branch.bus_to.idtag, bus_dict, fluid_node_dict)

                        if bus_f_graphic_obj and bus_t_graphic_obj:
                            graphic_object = TransformerGraphicItem(from_port=bus_f_graphic_obj.get_terminal(),
                                                                    to_port=bus_t_graphic_obj.get_terminal(),
                                                                    editor=self,
                                                                    api_object=branch)
                            self.add_to_scene(graphic_object=graphic_object)

                            graphic_object.redraw()
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.WindingDevice.value:

                for idtag, location in points_group.locations.items():
                    # branch: Winding = location.api_object
                    graphic_object = windings_dict[idtag]
                    graphic_object.redraw()
                    self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.FluidPathDevice.value:

                for idtag, location in points_group.locations.items():
                    branch: FluidPath = location.api_object
                    if branch.source is not None and branch.target is not None:
                        bus_f_graphic_obj = fluid_node_dict.get(branch.source.idtag, None)
                        bus_t_graphic_obj = fluid_node_dict.get(branch.target.idtag, None)

                        if bus_f_graphic_obj and bus_t_graphic_obj:
                            graphic_object = FluidPathGraphicItem(from_port=bus_f_graphic_obj.get_terminal(),
                                                                  to_port=bus_t_graphic_obj.get_terminal(),
                                                                  editor=self,
                                                                  api_object=branch)
                            self.add_to_scene(graphic_object=graphic_object)

                            graphic_object.redraw()
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            else:
                pass
                # print('draw: Unrecognized category: {}'.format(category))

        # last pass: arange children
        for category in [DeviceType.BusDevice, DeviceType.FluidNodeDevice]:
            graphics_dict = self.graphics_manager.get_device_type_dict(device_type=category)
            for idtag, graphic in graphics_dict.items():
                graphic.arrange_children()

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

    def update_diagram_element(self, device: ALL_DEV_TYPES,
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
                self.diagram_scene.removeItem(graphic_object)
            else:
                warn(f"Null scene for {graphic_object}, was it deleted already?")

    def delete_diagram_element(self, device: ALL_DEV_TYPES) -> None:
        """
        Delete device from the diagram registry
        :param device: EditableDevice
        """
        self.diagram.delete_device(device=device)
        graphic_object: QGraphicsItem = self.graphics_manager.delete_device(device=device)

        if graphic_object is not None:
            try:
                self.remove_from_scene(graphic_object)
            except:
                warn(f"Could not remove {graphic_object} from the scene")

    def remove_element(self,
                       device: ALL_DEV_TYPES,
                       graphic_object: Union[QGraphicsItem, None] = None) -> None:
        """
        Remove device from the diagram and the database
        :param device: EditableDevice
        :param graphic_object: optionally provide the graphics object associated
        """

        if device is not None:
            self.delete_diagram_element(device=device)
            self.circuit.delete_elements_by_type(obj=device)
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
        lst: List[Tuple[int, Bus, Union[BusGraphicItem, None]]] = list()
        bus_graphics_dict = self.graphics_manager.get_device_type_dict(DeviceType.BusDevice.value)
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
        # port.process_callbacks(port.parent.pos() + port.pos())

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

    def create_line(self, bus_from: Bus, bus_to: Bus, from_port: BarTerminalItem, to_port: BarTerminalItem):
        """

        :param bus_from:
        :param bus_to:
        :param from_port:
        :param to_port:
        :return:
        """
        name = 'Line ' + str(len(self.circuit.lines) + 1)
        obj = Line(bus_from=bus_from,
                   bus_to=bus_to,
                   name=name)

        graphic_object = LineGraphicItem(from_port=from_port,
                                         to_port=to_port,
                                         editor=self,
                                         api_object=obj)

        self.add_to_scene(graphic_object=graphic_object)

        self.update_diagram_element(device=obj,
                                    graphic_object=graphic_object)

        # add the new object to the circuit
        self.circuit.add_branch(obj)

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

        self.update_diagram_element(device=obj, graphic_object=graphic_object)

        # add the new object to the circuit
        self.circuit.add_branch(obj)

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

        self.update_diagram_element(device=obj, graphic_object=graphic_object)

        # add the new object to the circuit
        self.circuit.add_branch(obj)

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

        self.update_diagram_element(device=obj, graphic_object=graphic_object)

        # add the new object to the circuit
        self.circuit.add_branch(obj)

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

        self.update_diagram_element(device=obj, graphic_object=graphic_object)

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
                                tr3_graphic_object.update_conn()

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
                                fn_bus = Bus(fn.name, vnom=bus.Vnom)
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
                                fn_bus = Bus(fn.name, vnom=bus.Vnom)
                                self.circuit.add_bus(fn_bus)
                                fn.bus = fn_bus
                            else:
                                fn_bus = fn.bus

                            self.create_line(bus_from=bus,
                                             bus_to=fn_bus,
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

        if len(self.diagram_scene.selectedItems()) > 0:

            # expand selection
            for item in self.diagram_scene.selectedItems():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() * factor
                    y = item.pos().y() * factor
                    item.setPos(QPointF(x, y))

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

                    # apply changes to the diagram coordinates
                    location = self.diagram.query_point(item.api_object)
                    if location:
                        location.x = x
                        location.y = y

        else:

            # expand all
            for item in self.diagram_scene.items():
                if type(item) is BusGraphicItem:
                    x = item.pos().x() * factor
                    y = item.pos().y() * factor
                    item.setPos(QPointF(x, y))

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)

                    # apply changes to the diagram coordinates
                    location = self.diagram.query_point(item.api_object)
                    if location:
                        location.x = x
                        location.y = y

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

        nx_graph, buses_graphic_objects = self.diagram.build_graph()

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
        for i, bus in enumerate(buses_graphic_objects):
            loc = self.diagram.query_point(bus)
            graphic_object = self.graphics_manager.query(elm=bus)

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
                                    graphic_object=graphic_object)

        return graphic_object

    def add_api_line(self, branch: Line,
                     bus_f_graphic0: Union[None, BusGraphicItem] = None,
                     bus_t_graphic0: Union[None, BusGraphicItem] = None) -> Union[None, LineGraphicItem]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param bus_f_graphic0:
        :param bus_t_graphic0:
        """
        if bus_f_graphic0 is None:
            bus_f_graphic0 = self.graphics_manager.query(branch.bus_from)
            if bus_f_graphic0 is None:
                print(f"buse {branch.bus_from} were not found in the diagram :(")
                return None

        if bus_t_graphic0 is None:
            bus_t_graphic0 = self.graphics_manager.query(branch.bus_to)
            if bus_t_graphic0 is None:
                print(f"buse {branch.bus_to} were not found in the diagram :(")
                return None

        graphic_object = LineGraphicItem(from_port=bus_f_graphic0.get_terminal(),
                                         to_port=bus_t_graphic0.get_terminal(),
                                         editor=self,
                                         api_object=branch)

        graphic_object.redraw()
        self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
        return graphic_object

    def add_api_line_between_fluid_graphics(self, branch: Line,
                                            bus_f_graphic: FluidNodeGraphicItem,
                                            bus_t_graphic: FluidNodeGraphicItem):
        """
        add API branch to the Scene

        :param branch: Branch instance
        :param bus_f_graphic
        :param bus_t_graphic
        """

        graphic_object = LineGraphicItem(from_port=bus_f_graphic.get_terminal(),
                                         to_port=bus_t_graphic.get_terminal(),
                                         editor=self,
                                         api_object=branch)

        graphic_object.redraw()
        self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
        return graphic_object

    def add_api_dc_line(self, branch: DcLine):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphics = self.graphics_manager.query(branch.bus_from)
        bus_t_graphics = self.graphics_manager.query(branch.bus_to)

        if bus_f_graphics and bus_t_graphics:

            graphic_object = DcLineGraphicItem(from_port=bus_f_graphics.get_terminal(),
                                               to_port=bus_t_graphics.get_terminal(),
                                               editor=self,
                                               api_object=branch)

            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_hvdc(self, branch: HvdcLine):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphics = self.graphics_manager.query(branch.bus_from)
        bus_t_graphics = self.graphics_manager.query(branch.bus_to)

        if bus_f_graphics and bus_t_graphics:

            graphic_object = HvdcGraphicItem(from_port=bus_f_graphics.get_terminal(),
                                             to_port=bus_t_graphics.get_terminal(),
                                             editor=self,
                                             api_object=branch)

            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_vsc(self, branch: VSC):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphics = self.graphics_manager.query(branch.bus_from)
        bus_t_graphics = self.graphics_manager.query(branch.bus_to)

        if bus_f_graphics and bus_t_graphics:

            graphic_object = VscGraphicItem(from_port=bus_f_graphics.get_terminal(),
                                            to_port=bus_t_graphics.get_terminal(),
                                            editor=self,
                                            api_object=branch)

            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_upfc(self, branch: UPFC):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphics = self.graphics_manager.query(branch.bus_from)
        bus_t_graphics = self.graphics_manager.query(branch.bus_to)

        if bus_f_graphics and bus_t_graphics:

            graphic_object = UpfcGraphicItem(from_port=bus_f_graphics.get_terminal(),
                                             to_port=bus_t_graphics.get_terminal(),
                                             editor=self,
                                             api_object=branch)

            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_series_reactance(self, branch: SeriesReactance):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphics = self.graphics_manager.query(branch.bus_from)
        bus_t_graphics = self.graphics_manager.query(branch.bus_to)

        if bus_f_graphics and bus_t_graphics:

            graphic_object = SeriesReactanceGraphicItem(from_port=bus_f_graphics.get_terminal(),
                                                        to_port=bus_t_graphics.get_terminal(),
                                                        editor=self,
                                                        api_object=branch)

            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_transformer(self, branch: Transformer2W):
        """
        add API branch to the Scene
        :param branch: Branch instance
        """
        bus_f_graphics = self.graphics_manager.query(branch.bus_from)
        bus_t_graphics = self.graphics_manager.query(branch.bus_to)

        if bus_f_graphics and bus_t_graphics:

            graphic_object = TransformerGraphicItem(from_port=bus_f_graphics.get_terminal(),
                                                    to_port=bus_t_graphics.get_terminal(),
                                                    editor=self,
                                                    api_object=branch)

            graphic_object.redraw()
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
            return graphic_object
        else:
            print("Branch's buses were not found in the diagram :(")
            return None

    def add_api_transformer_3w(self, elm: Transformer3W):
        """
        add API branch to the Scene
        :param elm: Branch instance
        """

        tr3_graphic_object = self.create_transformer_3w_graphics(elm=elm, x=elm.x, y=elm.y)

        bus1_graphics: BusGraphicItem = self.graphics_manager.query(elm.bus1)
        bus2_graphics: BusGraphicItem = self.graphics_manager.query(elm.bus2)
        bus3_graphics: BusGraphicItem = self.graphics_manager.query(elm.bus3)

        conn1 = WindingGraphicItem(from_port=tr3_graphic_object.terminals[0],
                                   to_port=bus1_graphics.get_terminal(),
                                   editor=self)
        tr3_graphic_object.set_connection(i=0, bus=elm.bus1, conn=conn1)

        conn2 = WindingGraphicItem(from_port=tr3_graphic_object.terminals[1],
                                   to_port=bus2_graphics.get_terminal(),
                                   editor=self)
        tr3_graphic_object.set_connection(i=1, bus=elm.bus2, conn=conn2)

        conn3 = WindingGraphicItem(from_port=tr3_graphic_object.terminals[2],
                                   to_port=bus3_graphics.get_terminal(),
                                   editor=self)
        tr3_graphic_object.set_connection(i=2, bus=elm.bus3, conn=conn3)

        tr3_graphic_object.update_conn()

        self.update_diagram_element(device=elm,
                                    x=elm.x,
                                    y=elm.y,
                                    w=80,
                                    h=80,
                                    r=0,
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
            self.update_diagram_element(device=branch, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
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
        graphic_object = self.add_api_hvdc(hvdc)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=hvdc, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
        # self.delete_diagram_element(device=line)

    def convert_line_to_transformer(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to Transformer
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        transformer = self.circuit.convert_line_to_transformer(line)

        # add device to the schematic
        graphic_object = self.add_api_transformer(transformer)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=transformer, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
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
        graphic_object = self.add_api_vsc(vsc)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=vsc, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
        # self.delete_diagram_element(device=line)

    def convert_line_to_upfc(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to UPFC
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        upfc = self.circuit.convert_line_to_upfc(line)

        # add device to the schematic
        graphic_object = self.add_api_upfc(upfc)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=upfc, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)

    def convert_line_to_series_reactance(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to convert_line_to_series_reactance
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        series_reactance = self.circuit.convert_line_to_series_reactance(line)

        # add device to the schematic
        graphic_object = self.add_api_series_reactance(series_reactance)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete from the schematic
        self.remove_from_scene(line_graphic)

        self.update_diagram_element(device=series_reactance, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)

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
        graphic_object = self.add_api_line_between_fluid_graphics(line,
                                                                  bus_f_graphic=fl_from,
                                                                  bus_t_graphic=fl_to)
        self.add_to_scene(graphic_object)

        # update position
        fl_from.get_terminal().update()
        fl_to.get_terminal().update()

        # delete from the schematic
        self.remove_from_scene(item_graphic)

        self.update_diagram_element(device=line, x=0, y=0, w=0, h=0, r=0, graphic_object=graphic_object)
        # self.delete_diagram_element(device=element)

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
            logger: Logger = Logger()):
        """

        :param elm:
        :param injections_by_bus:
        :param injections_by_fluid_node:
        :param logger: Logger
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
            # warn(f"Device {elm} added already")
            logger.add_warning("Device already added", device_class=elm.device_type.value, device=elm.name)

    def add_elements_to_schematic(self,
                                  buses: List[Bus],
                                  lines: List[Line],
                                  dc_lines: List[DcLine],
                                  transformers2w: List[Transformer2W],
                                  transformers3w: List[Transformer3W],
                                  hvdc_lines: List[HvdcLine],
                                  vsc_devices: List[VSC],
                                  upfc_devices: List[UPFC],
                                  fluid_nodes: List[FluidNode],
                                  fluid_paths: List[FluidPath],
                                  injections_by_bus: Dict[Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]],
                                  injections_by_fluid_node: Dict[FluidNode, Dict[DeviceType, List[FLUID_TYPES]]],
                                  explode_factor=1.0,
                                  prog_func: Union[Callable, None] = None,
                                  text_func: Union[Callable, None] = None):
        """
        Add a elements to the schematic scene
        :param buses: list of Bus objects
        :param lines: list of Line objects
        :param dc_lines: list of DcLine objects
        :param transformers2w: list of Transformer Objects
        :param transformers3w: list of Transformer3W Objects
        :param hvdc_lines: list of HvdcLine objects
        :param vsc_devices: list Vsc objects
        :param upfc_devices: List of UPFC devices
        :param fluid_nodes: List of FluidNode devices
        :param fluid_paths: List of FluidPath devices
        :param injections_by_bus:
        :param injections_by_fluid_node:
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
            text_func('Creating schematic Fluid nodes devices')

        nn = len(fluid_nodes)
        for i, elm in enumerate(fluid_nodes):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            self.add_api_fluid_node(node=elm,
                                    injections_by_tpe=injections_by_fluid_node.get(elm, dict()))

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
        self.diagram_scene.clear()
        self.graphics_manager.clear()

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
        self.recolour_mode()

    def set_light_mode(self) -> None:
        """
        Set the light theme
        :return:
        """
        ACTIVE['color'] = Qt.black
        ACTIVE['text'] = Qt.black
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

    def get_selection_diagram(self) -> BusBranchDiagram:
        """
        Get a BusBranchDiagram of the current selection
        :return: BusBranchDiagram
        """
        diagram = BusBranchDiagram(name="Selection diagram")

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
            if not isinstance(item, BusGraphicItem):

                # add the element
                rect = item.boundingRect()
                diagram.set_point(device=item.api_object,
                                  location=GraphicLocation(x=rect.x(),
                                                           y=rect.y(),
                                                           h=rect.height(),
                                                           w=rect.width(),
                                                           r=item.rotation(),
                                                           api_object=item.api_object))

                if hasattr(item.api_object, 'bus_from'):  # if the element is a branch ...

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

        while delta > 10:

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

    def set_results_to_plot(self, all_threads: List[DriverTemplate]):
        """

        :param all_threads:
        :return:
        """
        self.results_dictionary = {thr.tpe: thr for thr in all_threads if thr is not None}

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
                            if key == SimulationTypes.TimeSeries_run:
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

    def plot_branch(self, i: int, api_object: Union[Line, DcLine, Transformer2W, VSC, UPFC]):
        """
        Plot branch results
        :param i: branch index (not counting HVDC lines because those are not real Branches)
        :param api_object: API object
        """
        fig = plt.figure(figsize=(12, 8))
        ax_1 = fig.add_subplot(211)
        ax_2 = fig.add_subplot(212)

        # set time
        x = self.circuit.get_time_array()
        x_cl = x

        if x is not None:
            if len(x) > 0:

                p = np.arange(len(x)).astype(float) / len(x)

                # search available results
                power_data = dict()
                loading_data = dict()
                loading_st_data = None
                loading_clustering_data = None
                power_clustering_data = None

                for key, driver in self.results_dictionary.items():
                    if hasattr(driver, 'results'):
                        if driver.results is not None:
                            if key == SimulationTypes.TimeSeries_run:
                                power_data[key.value] = driver.results.Sf.real[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.loading.real[:, i] * 100.0))

                            elif key == SimulationTypes.ClusteringTimeSeries_run:
                                x_cl = x[driver.sampled_time_idx]
                                power_clustering_data = driver.results.Sf.real[:, i]
                                loading_clustering_data = np.sort(np.abs(driver.results.loading.real[:, i] * 100.0))

                            elif key == SimulationTypes.LinearAnalysis_TS_run:
                                power_data[key.value] = driver.results.Sf.real[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.loading.real[:, i] * 100.0))

                            # elif key == SimulationTypes.NetTransferCapacityTS_run:
                            #     power_data[key.value] = driver.results.atc[:, i]
                            #     atc_perc = driver.results.atc[:, i] / (api_object.rate_prof + 1e-9)
                            #     loading_data[key.value] = np.sort(np.abs(atc_perc * 100.0))

                            elif key == SimulationTypes.ContingencyAnalysisTS_run:
                                power_data[key.value] = driver.results.max_flows.real[:, i]
                                loading_data[key.value] = np.sort(
                                    np.abs(driver.results.max_loading.real[:, i] * 100.0))

                            elif key == SimulationTypes.OPFTimeSeries_run:
                                power_data[key.value] = driver.results.Sf.real[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.loading.real[:, i] * 100.0))

                            elif key == SimulationTypes.StochasticPowerFlow:
                                loading_st_data = np.sort(np.abs(driver.results.loading_points.real[:, i] * 100.0))

                # add the rating
                # power_data['Rates+'] = api_object.rate_prof
                # power_data['Rates-'] = -api_object.rate_prof

                # loading
                if len(loading_data.keys()):
                    df = pd.DataFrame(data=loading_data, index=p)
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                if loading_clustering_data is not None:
                    p_st = np.arange(len(loading_clustering_data)).astype(float) / len(loading_clustering_data)
                    df = pd.DataFrame(data=loading_clustering_data,
                                      index=p_st,
                                      columns=[SimulationTypes.ClusteringTimeSeries_run.value])
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                if loading_st_data is not None:
                    p_st = np.arange(len(loading_st_data)).astype(float) / len(loading_st_data)
                    df = pd.DataFrame(data=loading_st_data,
                                      index=p_st,
                                      columns=[SimulationTypes.StochasticPowerFlow.value])
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                # power
                if len(power_data.keys()):
                    df = pd.DataFrame(data=power_data, index=x)
                    ax_2.set_title('Power', fontsize=14)
                    ax_2.set_ylabel('Power [MW]', fontsize=11)
                    df.plot(ax=ax_2)
                    ax_2.plot(x, api_object.rate_prof.toarray(), c='gray', linestyle='dashed', linewidth=1)
                    ax_2.plot(x, -api_object.rate_prof.toarray(), c='gray', linestyle='dashed', linewidth=1)

                if power_clustering_data is not None:
                    df = pd.DataFrame(data=power_clustering_data,
                                      index=x_cl,
                                      columns=[SimulationTypes.ClusteringTimeSeries_run.value])
                    ax_2.set_title('Power', fontsize=14)
                    ax_2.set_ylabel('Power [MW]', fontsize=11)
                    df.plot(ax=ax_2)

                plt.legend()
                fig.suptitle(api_object.name, fontsize=20)

                # plot the profiles
                plt.show()

    def plot_hvdc_branch(self, i: int, api_object: HvdcLine):
        """
        HVDC branch
        :param i: index of the object
        :param api_object: HvdcGraphicItem
        """
        fig = plt.figure(figsize=(12, 8))
        ax_1 = fig.add_subplot(211)
        # ax_2 = fig.add_subplot(212, sharex=ax_1)
        ax_2 = fig.add_subplot(212)

        # set time
        x = self.circuit.time_profile
        x_cl = x

        if x is not None:
            if len(x) > 0:

                p = np.arange(len(x)).astype(float) / len(x)

                # search available results
                power_data = dict()
                loading_data = dict()
                loading_st_data = None
                loading_clustering_data = None
                power_clustering_data = None

                for key, driver in self.results_dictionary.items():
                    if hasattr(driver, 'results'):
                        if driver.results is not None:
                            if key == SimulationTypes.TimeSeries_run:
                                power_data[key.value] = driver.results.hvdc_Pf[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.hvdc_loading[:, i] * 100.0))

                            elif key == SimulationTypes.ClusteringTimeSeries_run:
                                x_cl = x[driver.sampled_time_idx]
                                power_clustering_data = driver.results.hvdc_Pf[:, i]
                                loading_clustering_data = np.sort(np.abs(driver.results.hvdc_loading[:, i] * 100.0))

                            elif key == SimulationTypes.LinearAnalysis_TS_run:
                                power_data[key.value] = driver.results.hvdc_Pf[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.hvdc_loading[:, i] * 100.0))

                            elif key == SimulationTypes.OPFTimeSeries_run:
                                power_data[key.value] = driver.results.hvdc_Pf[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.hvdc_loading[:, i] * 100.0))

                # add the rating
                # power_data['Rates+'] = api_object.rate_prof
                # power_data['Rates-'] = -api_object.rate_prof

                # loading
                if len(loading_data.keys()):
                    df = pd.DataFrame(data=loading_data, index=p)
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                if loading_clustering_data is not None:
                    p_st = np.arange(len(loading_clustering_data)).astype(float) / len(loading_clustering_data)
                    df = pd.DataFrame(data=loading_clustering_data,
                                      index=p_st,
                                      columns=[SimulationTypes.ClusteringTimeSeries_run.value])
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                if loading_st_data is not None:
                    p_st = np.arange(len(loading_st_data)).astype(float) / len(loading_st_data)
                    df = pd.DataFrame(data=loading_st_data,
                                      index=p_st,
                                      columns=[SimulationTypes.StochasticPowerFlow.value])
                    ax_1.set_title('Probability x < value', fontsize=14)
                    ax_1.set_ylabel('Loading [%]', fontsize=11)
                    df.plot(ax=ax_1)

                # power
                if len(power_data.keys()):
                    df = pd.DataFrame(data=power_data, index=x)
                    ax_2.set_title('Power', fontsize=14)
                    ax_2.set_ylabel('Power [MW]', fontsize=11)
                    df.plot(ax=ax_2)
                    ax_2.plot(x, api_object.rate_prof.toarray(), c='gray', linestyle='dashed', linewidth=1)
                    ax_2.plot(x, -api_object.rate_prof.toarray(), c='gray', linestyle='dashed', linewidth=1)

                if power_clustering_data is not None:
                    df = pd.DataFrame(data=power_clustering_data,
                                      index=x_cl,
                                      columns=[SimulationTypes.ClusteringTimeSeries_run.value])
                    ax_2.set_title('Power', fontsize=14)
                    ax_2.set_ylabel('Power [MW]', fontsize=11)
                    df.plot(ax=ax_2)

                plt.legend()
                fig.suptitle(api_object.name, fontsize=20)

                # plot the profiles
                plt.show()

    def set_rate_to_profile(self, api_object):
        """

        :param api_object:
        """
        if api_object is not None:
            if api_object.rate_prof.size():
                quit_msg = (f"{api_object.name}\nAre you sure that you want to overwrite the "
                            f"rates profile with the snapshot value?")
                reply = QMessageBox.question(self, 'Overwrite the profile', quit_msg,
                                             QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)

                if reply == QMessageBox.StandardButton.Yes.value:
                    api_object.rate_prof.fill(api_object.rate)

    def set_active_status_to_profile(self, api_object, override_question=False):
        """

        :param api_object:
        :param override_question:
        :return:
        """
        if api_object is not None:
            if api_object.active_prof.size():
                if not override_question:
                    quit_msg = (f"{api_object.name}\nAre you sure that you want to overwrite the "
                                f"active profile with the snapshot value?")
                    reply = QMessageBox.question(self, 'Overwrite the active profile', quit_msg,
                                                 QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
                    ok = reply == QMessageBox.StandardButton.Yes
                else:
                    ok = True

                if ok:
                    if api_object.active:
                        api_object.active_prof.fill(True)
                    else:
                        api_object.active_prof.fill(False)

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

                if 0.0 < position < 1.0:

                    # Each of the Branches will have the proportional impedance
                    # Bus_from           Middle_bus            Bus_To
                    # o----------------------o--------------------o
                    #   >-------- x -------->|
                    #   (x: distance measured in per unit (0~1)
                    line = line_graphics.api_object

                    mid_bus = Bus(name=line.name + ' split',
                                  vnom=line.bus_from.Vnom,
                                  vmin=line.bus_from.Vmin,
                                  vmax=line.bus_from.Vmax)

                    bus_f_graphics_data = self.diagram.query_point(line.bus_from)
                    bus_t_graphics_data = self.diagram.query_point(line.bus_to)
                    bus_f_graphic_obj = self.graphics_manager.query(line.bus_from)
                    bus_t_graphic_obj = self.graphics_manager.query(line.bus_to)

                    if bus_f_graphics_data is None:
                        error_msg(f"{line.bus_from} was not found in the diagram")
                        return None
                    if bus_t_graphics_data is None:
                        error_msg(f"{line.bus_to} was not found in the diagram")
                        return None
                    if bus_f_graphic_obj is None:
                        error_msg(f"{line.bus_from} was not found in the graphics manager")
                        return None
                    if bus_t_graphic_obj is None:
                        error_msg(f"{line.bus_to} was not found in the graphics manager")
                        return None

                    # C(x, y) = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
                    middle_bus_x = bus_f_graphics_data.x + (bus_t_graphics_data.x - bus_f_graphics_data.x) * position
                    middle_bus_y = bus_f_graphics_data.y + (bus_t_graphics_data.y - bus_f_graphics_data.y) * position

                    # create first split
                    br1 = Line(name=line.name + ' split 1',
                               bus_from=line.bus_from,
                               bus_to=mid_bus,
                               r=line.R * position,
                               x=line.X * position,
                               b=line.B * position,
                               r0=line.R0 * position,
                               x0=line.X0 * position,
                               b0=line.B0 * position,
                               r2=line.R2 * position,
                               x2=line.X2 * position,
                               b2=line.B2 * position,
                               length=line.length * position,
                               rate=line.rate,
                               contingency_factor=line.contingency_factor,
                               protection_rating_factor=line.protection_rating_factor)

                    position_c = 1.0 - position
                    br2 = Line(name=line.name + ' split 2',
                               bus_from=mid_bus,
                               bus_to=line.bus_to,
                               r=line.R * position_c,
                               x=line.X * position_c,
                               b=line.B * position_c,
                               r0=line.R0 * position_c,
                               x0=line.X0 * position_c,
                               b0=line.B0 * position_c,
                               r2=line.R2 * position_c,
                               x2=line.X2 * position_c,
                               b2=line.B2 * position_c,
                               length=line.length * position_c,
                               rate=line.rate,
                               contingency_factor=line.contingency_factor,
                               protection_rating_factor=line.protection_rating_factor)

                    # deactivate the original line
                    line_graphics.api_object.active = False
                    line_graphics.api_object.active_prof.fill(False)
                    line_graphics.set_enable(False)

                    # add to gridcal the new 2 lines and the bus
                    self.circuit.add_bus(mid_bus)
                    self.circuit.add_line(br1)
                    self.circuit.add_line(br2)

                    # add new stuff as new investment
                    inv_group = InvestmentsGroup(name=line.name + ' split', category='Line split')
                    self.circuit.add_investments_group(inv_group)
                    self.circuit.add_investment(
                        Investment(name=mid_bus.name, device_idtag=mid_bus.idtag, group=inv_group))
                    self.circuit.add_investment(Investment(name=br1.name, device_idtag=br1.idtag, group=inv_group))
                    self.circuit.add_investment(Investment(name=br2.name, device_idtag=br2.idtag, group=inv_group))

                    # add to the schematic the new 2 lines and the bus
                    middle_bus_graphics = self.add_api_bus(bus=mid_bus,
                                                           injections_by_tpe=dict(),
                                                           x0=middle_bus_x,
                                                           y0=middle_bus_y)
                    br1_graphics = self.add_api_line(branch=br1,
                                                     bus_f_graphic0=bus_f_graphic_obj,
                                                     bus_t_graphic0=middle_bus_graphics)
                    br2_graphics = self.add_api_line(branch=br2,
                                                     bus_f_graphic0=middle_bus_graphics,
                                                     bus_t_graphic0=bus_t_graphic_obj)

                    self.add_to_scene(middle_bus_graphics)
                    self.add_to_scene(br1_graphics)
                    self.add_to_scene(br2_graphics)

                    # redraw
                    bus_f_graphic_obj.arrange_children()
                    bus_t_graphic_obj.arrange_children()
                    middle_bus_graphics.arrange_children()
                else:
                    error_msg("Incorrect position", 'Line split')

    def split_line_in_out(self, line_graphics: LineGraphicItem):
        """
        Split line and create extra substations so that an in/out is formed
        :param line_graphics: Original LineGraphicItem to split
        """
        dlg = InputNumberDialogue(min_value=1.0,
                                  max_value=99.0,
                                  is_int=False,
                                  title="Split line with input/output",
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
                                               title="Split line with input/output",
                                               text="Distance from the original line",
                                               suffix=' km',
                                               decimals=2,
                                               default_value=1.0)

                    if dlg2.exec_():

                        if dlg2.is_accepted:

                            # Each of the Branches will have the proportional impedance
                            # Bus_from           Middle_bus            Bus_To
                            # o----------------------o--------------------o
                            #   >-------- x -------->|
                            #   (x: distance measured in per unit (0~1)
                            line = line_graphics.api_object
                            bus_f_graphics_data = self.diagram.query_point(line.bus_from)
                            bus_t_graphics_data = self.diagram.query_point(line.bus_to)
                            bus_f_graphic_obj = self.graphics_manager.query(line.bus_from)
                            bus_t_graphic_obj = self.graphics_manager.query(line.bus_to)

                            if bus_f_graphics_data is None:
                                error_msg(f"{line.bus_from} was not found in the diagram")
                                return None
                            if bus_t_graphics_data is None:
                                error_msg(f"{line.bus_to} was not found in the diagram")
                                return None
                            if bus_f_graphic_obj is None:
                                error_msg(f"{line.bus_from} was not found in the graphics manager")
                                return None
                            if bus_t_graphic_obj is None:
                                error_msg(f"{line.bus_to} was not found in the graphics manager")
                                return None

                            # C(x, y) = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
                            mid_x = bus_f_graphics_data.x + (bus_t_graphics_data.x - bus_f_graphics_data.x) * position
                            mid_y = bus_f_graphics_data.y + (bus_t_graphics_data.y - bus_f_graphics_data.y) * position

                            B1 = Bus(name=line.name + ' split bus 1',
                                     vnom=line.bus_from.Vnom,
                                     vmin=line.bus_from.Vmin,
                                     vmax=line.bus_from.Vmax)

                            B2 = Bus(name=line.name + ' split bus 2',
                                     vnom=line.bus_from.Vnom,
                                     vmin=line.bus_from.Vmin,
                                     vmax=line.bus_from.Vmax)

                            B3 = Bus(name=line.name + ' new bus',
                                     vnom=line.bus_from.Vnom,
                                     vmin=line.bus_from.Vmin,
                                     vmax=line.bus_from.Vmax)

                            # create first split
                            br1 = Line(name=line.name + ' split 1',
                                       bus_from=line.bus_from,
                                       bus_to=B1,
                                       r=line.R * position,
                                       x=line.X * position,
                                       b=line.B * position,
                                       r0=line.R0 * position,
                                       x0=line.X0 * position,
                                       b0=line.B0 * position,
                                       r2=line.R2 * position,
                                       x2=line.X2 * position,
                                       b2=line.B2 * position,
                                       length=line.length * position,
                                       rate=line.rate,
                                       contingency_factor=line.contingency_factor,
                                       protection_rating_factor=line.protection_rating_factor)

                            position_c = 1.0 - position
                            br2 = Line(name=line.name + ' split 2',
                                       bus_from=B2,
                                       bus_to=line.bus_to,
                                       r=line.R * position_c,
                                       x=line.X * position_c,
                                       b=line.B * position_c,
                                       r0=line.R0 * position_c,
                                       x0=line.X0 * position_c,
                                       b0=line.B0 * position_c,
                                       r2=line.R2 * position_c,
                                       x2=line.X2 * position_c,
                                       b2=line.B2 * position_c,
                                       length=line.length * position_c,
                                       rate=line.rate,
                                       contingency_factor=line.contingency_factor,
                                       protection_rating_factor=line.protection_rating_factor)

                            # kilometers of the in/out appart from the original line
                            km_io = dlg2.value
                            proportion_io = km_io / line.length

                            br3 = Line(name=line.name + ' in',
                                       bus_from=B1,
                                       bus_to=B3,
                                       r=line.R * proportion_io,
                                       x=line.X * proportion_io,
                                       b=line.B * proportion_io,
                                       r0=line.R0 * proportion_io,
                                       x0=line.X0 * proportion_io,
                                       b0=line.B0 * proportion_io,
                                       r2=line.R2 * proportion_io,
                                       x2=line.X2 * proportion_io,
                                       b2=line.B2 * proportion_io,
                                       length=line.length * proportion_io,
                                       rate=line.rate,
                                       contingency_factor=line.contingency_factor,
                                       protection_rating_factor=line.protection_rating_factor)

                            br4 = Line(name=line.name + ' out',
                                       bus_from=B3,
                                       bus_to=B2,
                                       r=line.R * proportion_io,
                                       x=line.X * proportion_io,
                                       b=line.B * proportion_io,
                                       r0=line.R0 * proportion_io,
                                       x0=line.X0 * proportion_io,
                                       b0=line.B0 * proportion_io,
                                       r2=line.R2 * proportion_io,
                                       x2=line.X2 * proportion_io,
                                       b2=line.B2 * proportion_io,
                                       length=line.length * proportion_io,
                                       rate=line.rate,
                                       contingency_factor=line.contingency_factor,
                                       protection_rating_factor=line.protection_rating_factor)

                            # deactivate the original line
                            line_graphics.api_object.active = False
                            line_graphics.api_object.active_prof.fill(False)
                            line_graphics.set_enable(False)

                            # add to gridcal the new 2 lines and the bus
                            self.circuit.add_bus(B1)
                            self.circuit.add_bus(B2)
                            self.circuit.add_bus(B3)
                            self.circuit.add_line(br1)
                            self.circuit.add_line(br2)
                            self.circuit.add_line(br3)
                            self.circuit.add_line(br4)

                            # add new stuff as new investment
                            inv_group = InvestmentsGroup(name=line.name + ' in/out', category='Line in/out')
                            self.circuit.add_investments_group(inv_group)
                            self.circuit.add_investment(
                                Investment(name=B1.name, device_idtag=B1.idtag, group=inv_group))
                            self.circuit.add_investment(
                                Investment(name=B2.name, device_idtag=B2.idtag, group=inv_group))
                            self.circuit.add_investment(
                                Investment(name=B3.name, device_idtag=B3.idtag, group=inv_group))
                            self.circuit.add_investment(
                                Investment(name=br1.name, device_idtag=br1.idtag, group=inv_group))
                            self.circuit.add_investment(
                                Investment(name=br2.name, device_idtag=br2.idtag, group=inv_group))
                            self.circuit.add_investment(
                                Investment(name=br3.name, device_idtag=br3.idtag, group=inv_group))
                            self.circuit.add_investment(
                                Investment(name=br4.name, device_idtag=br4.idtag, group=inv_group))

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
                                                             bus_f_graphic0=bus_f_graphic_obj,
                                                             bus_t_graphic0=B1_graphics)

                            br2_graphics = self.add_api_line(branch=br2,
                                                             bus_f_graphic0=B2_graphics,
                                                             bus_t_graphic0=bus_t_graphic_obj)

                            br3_graphics = self.add_api_line(branch=br3,
                                                             bus_f_graphic0=B1_graphics,
                                                             bus_t_graphic0=B3_graphics)

                            br4_graphics = self.add_api_line(branch=br4,
                                                             bus_f_graphic0=B3_graphics,
                                                             bus_t_graphic0=B2_graphics)

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

    def disable_all_results_tags(self):
        """
        Disable all results' tags in this diagram
        """
        for device_tpe, type_dict in self.graphics_manager.graphic_dict.items():
            for key, widget in type_dict.items():
                widget.disable_label_drawing()

    def enable_all_results_tags(self):
        """
        Enable all results' tags in this diagram
        """
        for device_tpe, type_dict in self.graphics_manager.graphic_dict.items():
            for key, widget in type_dict.items():
                widget.enable_label_drawing()


def generate_bus_branch_diagram(buses: List[Bus],
                                lines: List[Line],
                                dc_lines: List[DcLine],
                                transformers2w: List[Transformer2W],
                                transformers3w: List[Transformer3W],
                                windings: List[Winding],
                                hvdc_lines: List[HvdcLine],
                                vsc_devices: List[VSC],
                                upfc_devices: List[UPFC],
                                fluid_nodes: List[FluidNode],
                                fluid_paths: List[FluidPath],
                                explode_factor=1.0,
                                prog_func: Union[Callable, None] = None,
                                text_func: Union[Callable, None] = None,
                                name='Bus branch diagram') -> BusBranchDiagram:
    """
    Add a elements to the schematic scene
    :param buses: list of Bus objects
    :param lines: list of Line objects
    :param dc_lines: list of DcLine objects
    :param transformers2w: list of Transformer Objects
    :param transformers3w: list of Transformer3W Objects
    :param windings: list of Winding objects
    :param hvdc_lines: list of HvdcLine objects
    :param vsc_devices: list Vsc objects
    :param upfc_devices: List of UPFC devices
    :param fluid_nodes:
    :param fluid_paths:
    :param explode_factor: factor of "explosion": Separation of the nodes factor
    :param prog_func: progress report function
    :param text_func: Text report function
    :param name: name of the diagram
    """

    diagram = BusBranchDiagram(name=name)

    # first create the buses
    if text_func is not None:
        text_func('Creating schematic buses')

    nn = len(buses)
    for i, bus in enumerate(buses):

        if not bus.is_internal:  # 3w transformer buses are not represented

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            # correct possible nonsense
            if np.isnan(bus.y):
                bus.y = 0.0
            if np.isnan(bus.x):
                bus.x = 0.0

            x = int(bus.x * explode_factor)
            y = int(bus.y * explode_factor)
            diagram.set_point(device=bus, location=GraphicLocation(x=x, y=y, h=bus.h, w=bus.w))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic fluid nodes devices')

    nn = len(fluid_nodes)
    for i, elm in enumerate(fluid_nodes):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=elm, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic line devices')

    nn = len(lines)
    for i, branch in enumerate(lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic line devices')

    nn = len(dc_lines)
    for i, branch in enumerate(dc_lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic transformer devices')

    nn = len(transformers2w)
    for i, branch in enumerate(transformers2w):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic transformer3w devices')

    nn = len(transformers3w)
    for i, elm in enumerate(transformers3w):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        x = int(elm.x * explode_factor)
        y = int(elm.y * explode_factor)
        diagram.set_point(device=elm, location=GraphicLocation(x=x, y=y))
        diagram.set_point(device=elm.winding1, location=GraphicLocation())
        diagram.set_point(device=elm.winding2, location=GraphicLocation())
        diagram.set_point(device=elm.winding3, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic winding devices')

    nn = len(windings)
    for i, branch in enumerate(windings):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic HVDC devices')

    nn = len(hvdc_lines)
    for i, branch in enumerate(hvdc_lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic VSC devices')

    nn = len(vsc_devices)
    for i, branch in enumerate(vsc_devices):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic UPFC devices')

    nn = len(upfc_devices)
    for i, branch in enumerate(upfc_devices):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=branch, location=GraphicLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic fluid paths devices')

    nn = len(fluid_paths)
    for i, elm in enumerate(fluid_paths):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=elm, location=GraphicLocation())

    return diagram


def make_vecinity_diagram(circuit: MultiCircuit, root_bus: Bus, max_level: int = 1):
    """
    Create a vecinity diagram
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
    lines = list()
    dc_lines = list()
    transformers2w = list()
    transformers3w = list()
    windings = list()
    hvdc_lines = list()
    vsc_converters = list()
    upfc_devices = list()
    fluid_paths = list()

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

        else:
            raise Exception('Unrecognized branch type ' + obj.device_type.value)

    # Draw schematic subset
    diagram = generate_bus_branch_diagram(buses=list(buses),
                                          lines=lines,
                                          dc_lines=dc_lines,
                                          transformers2w=transformers2w,
                                          transformers3w=transformers3w,
                                          windings=windings,
                                          hvdc_lines=hvdc_lines,
                                          vsc_devices=vsc_converters,
                                          upfc_devices=upfc_devices,
                                          fluid_nodes=list(fluid_nodes),
                                          fluid_paths=fluid_paths,
                                          explode_factor=1.0,
                                          prog_func=None,
                                          text_func=print,
                                          name=root_bus.name + 'vecinity')

    return diagram

# if __name__ == "__main__":
#     from PySide6.QtWidgets import QApplication
#     app = QApplication(sys.argv)
#
#     window = DiagramEditorWidget(circuit=MultiCircuit(),
#                                    diagram=BusBranchDiagram(),
#                                    default_bus_voltage=10.0)
#
#     window.resize(1.61 * 700.0, 600.0)  # golden ratio
#     window.show()
#     sys.exit(app.exec())
