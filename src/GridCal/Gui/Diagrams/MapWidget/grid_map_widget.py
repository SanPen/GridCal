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
import os
from typing import Union, List, Tuple, Dict
import numpy as np
import math
from PySide6.QtWidgets import QGraphicsItem
from collections.abc import Callable
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtCore import (Qt, QSize, QRect, QMimeData, QIODevice, QByteArray, QDataStream, QModelIndex)
from PySide6.QtGui import (QIcon, QPixmap, QImage, QPainter, QStandardItemModel, QStandardItem, QColor, QDropEvent,
                           QWheelEvent)

from GridCalEngine.Devices.Diagrams.map_location import MapLocation
from GridCalEngine.Devices.Substation import Bus
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Devices.Diagrams.map_diagram import MapDiagram
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.Devices.Fluid import FluidNode, FluidPath
from GridCalEngine.basic_structures import Vec, CxVec, IntVec
from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.Branches.line_locations import LineLocation
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.types import ALL_DEV_TYPES, INJECTION_DEVICE_TYPES, FLUID_TYPES
from GridCalEngine.basic_structures import Logger

from GridCal.Gui.Diagrams.MapWidget.Branches.map_ac_line import MapAcLine
from GridCal.Gui.Diagrams.MapWidget.Branches.map_dc_line import MapDcLine
from GridCal.Gui.Diagrams.MapWidget.Branches.map_hvdc_line import MapHvdcLine
from GridCal.Gui.Diagrams.MapWidget.Branches.map_fluid_path import MapFluidPathLine
from GridCal.Gui.Diagrams.MapWidget.Substation.node_graphic_item import NodeGraphicItem
from GridCal.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
from GridCal.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem
from GridCal.Gui.Diagrams.MapWidget.map_widget import MapWidget
import GridCal.Gui.Visualization.visualization as viz
import GridCalEngine.Devices.Diagrams.palettes as palettes
from GridCal.Gui.Diagrams.graphics_manager import ALL_MAP_GRAPHICS
from GridCal.Gui.Diagrams.MapWidget.Tiles.tiles import Tiles
from GridCal.Gui.Diagrams.base_diagram_widget import BaseDiagramWidget

MAP_BRANCH_GRAPHIC_TYPES = Union[
    MapAcLine, MapDcLine, MapHvdcLine, MapFluidPathLine
]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """

    :param lat1:
    :param lon1:
    :param lat2:
    :param lon2:
    :return:
    """
    R = 6371  # Earth radius in kilometers
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)) * math.sin(dLon / 2) * math.sin(dLon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def compare_options(it1: NodeGraphicItem, it2: NodeGraphicItem) -> Tuple[NodeGraphicItem, NodeGraphicItem]:
    """

    :param it1:
    :param it2:
    :return:
    """
    # Extract coordinates
    first_last_lat = float(it1.line_container.api_object.locations.data[-1].lat)
    first_last_long = float(it1.line_container.api_object.locations.data[-1].long)
    second_first_lat = float(it2.line_container.api_object.locations.data[0].lat)
    second_first_long = float(it2.line_container.api_object.locations.data[0].long)

    # Calculate distances for both configurations
    distance_1_to_2 = haversine_distance(first_last_lat, first_last_long,
                                         second_first_lat, second_first_long)

    second_last_lat = float(it2.line_container.api_object.locations.data[-1].lat)
    second_last_long = float(it2.line_container.api_object.locations.data[-1].long)
    first_first_lat = float(it1.line_container.api_object.locations.data[0].lat)
    first_first_long = float(it1.line_container.api_object.locations.data[0].long)

    distance_2_to_1 = haversine_distance(second_last_lat, second_last_long,
                                         first_first_lat, first_first_long)

    if distance_1_to_2 <= distance_2_to_1:
        return it1, it2
    else:
        return it2, it1


class MapLibraryModel(QStandardItemModel):
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

        self.substation_name = "Substation"

        self.add(name=self.substation_name, icon_name="bus_icon")

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

    def get_substation_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(self.substation_name)

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


class GridMapWidget(BaseDiagramWidget):
    """
    GridMapWidget
    """

    def __init__(self,
                 tile_src: Tiles,
                 start_level: int,
                 longitude: float,
                 latitude: float,
                 name: str,
                 circuit: MultiCircuit,
                 diagram: Union[None, MapDiagram] = None,
                 call_delete_db_element_func: Callable[["GridMapWidget", ALL_DEV_TYPES], None] = None,
                 call_new_substation_diagram_func: Callable[[Substation], None] = None, ):
        """

        :param tile_src:
        :param start_level:
        :param longitude:
        :param latitude:
        :param name:
        :param diagram:
        :param call_delete_db_element_func:
        """

        BaseDiagramWidget.__init__(self,
                                   circuit=circuit,
                                   diagram=MapDiagram(name=name,
                                                      tile_source=tile_src.TilesetName,
                                                      start_level=start_level,
                                                      longitude=longitude,
                                                      latitude=latitude) if diagram is None else diagram,
                                   library_model=MapLibraryModel(),
                                   time_index=None,
                                   call_delete_db_element_func=call_delete_db_element_func)

        # declare the map
        self.map = MapWidget(parent=self,
                             tile_src=tile_src,
                             start_level=start_level,
                             startLat=latitude,
                             startLon=longitude,
                             editor=self,
                             zoom_callback=self.zoom_callback,
                             position_callback=self.position_callback)

        # Any representation on the map must be done after this Goto Function
        self.map.GotoLevelAndPosition(level=6, longitude=0, latitude=40)

        self.map.startLev = 6
        self.map.startLat = 0
        self.map.startLon = 40

        # function pointer to call for a new substation diagram
        self.call_new_substation_diagram_func = call_new_substation_diagram_func

        self.startHe = self.map.view.height()
        self.startWi = self.map.view.width()
        self.constantLineWidth = True

        # draw
        self.draw()

    def set_diagram(self, diagram: MapDiagram):
        """

        :param diagram:
        :return:
        """
        self.diagram = diagram

    def delete_diagram_element(self, device: ALL_DEV_TYPES, propagate: bool = True):
        """

        :param device:
        :param propagate: Propagate the delete to other diagrams?
        :return:
        """
        # TODO: Implement this
        pass

        if propagate:
            if self.call_delete_db_element_func is not None:
                self.call_delete_db_element_func(self, device)

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

    def add_to_scene(self, graphic_object: ALL_MAP_GRAPHICS = None) -> None:
        """
        Add item to the diagram and the diagram scene
        :param graphic_object: Graphic object associated
        """

        self.map.diagram_scene.addItem(graphic_object)

    def remove_only_graphic_element(self, graphic_object: ALL_MAP_GRAPHICS = None) -> None:
        """
        Removes only the graphic elements, not the api_object
        :param graphic_object: Graphic object associated
        """
        self.map.diagram_scene.removeItem(graphic_object)

    def remove_from_scene(self, graphic_object: ALL_MAP_GRAPHICS = None) -> None:
        """
        Add item to the diagram and the diagram scene
        :param graphic_object: Graphic object associated
        """
        api_object = getattr(graphic_object, 'api_object', None)
        if api_object is not None:
            self.graphics_manager.delete_device(api_object)
        self.map.diagram_scene.removeItem(graphic_object)

    def zoom_callback(self, zoom_level: int) -> None:
        """
        Update the diagram zoom level (useful for saving)
        :param zoom_level: whatever zoom level
        """
        self.diagram.start_level = zoom_level

    def position_callback(self, latitude: float, longitude: float, x: int, y: int) -> None:
        """
        Update the diagram central position (useful for saving)
        :param longitude: in deg
        :param latitude: in deg
        :param x:
        :param y:
        """
        self.diagram.latitude = latitude
        self.diagram.longitude = longitude

        # print(f"Pos lat={latitude}, lon={longitude} x={x}, y={y}")

    def zoom_in(self):
        """
        Zoom in
        """
        if self.map.level + 1 <= self.map.max_level:
            self.map.zoom_level(level=self.map.level + 1)

    def zoom_out(self):
        """
        Zoom out
        """
        if self.map.level - 1 >= self.map.min_level:
            self.map.zoom_level(level=self.map.level - 1)

    def rescaleGraphics(self):
        """

        :return:
        """
        if self.constantLineWidth:
            for device_type, graphics in self.graphics_manager.graphic_dict.items():
                for graphic_id, graphic_item in graphics.items():
                    if isinstance(graphic_item, MAP_BRANCH_GRAPHIC_TYPES):
                        for seg in graphic_item.segments_list:
                            seg.update_endings(True)

    def to_lat_lon(self, x: float, y: float) -> Tuple[float, float]:
        """
        Convert x, y position in the map to latitude and longitude
        :param x:
        :param y:
        :return:
        """
        return self.map.view.to_lat_lon(x=x, y=y)

    def to_x_y(self, lat: float, lon: float) -> Tuple[float, float]:
        """

        :param lat:
        :param lon:
        :return:
        """
        return self.map.view.to_x_y(lat=lat, lon=lon)

    def update_diagram_element(self,
                               device: ALL_DEV_TYPES,
                               latitude: float = 0.0,
                               longitude: float = 0.0,
                               altitude: float = 0.0,
                               graphic_object: QGraphicsItem = None) -> None:
        """
        Set the position of a device in the diagram
        :param device: EditableDevice
        :param latitude:
        :param longitude:
        :param altitude:
        :param graphic_object: Graphic object associated
        """
        self.diagram.set_point(device=device,
                               location=MapLocation(latitude=latitude,
                                                    longitude=longitude,
                                                    altitude=altitude,
                                                    api_object=device))

        self.graphics_manager.add_device(elm=device, graphic=graphic_object)

    def create_node(self,
                    line_container: MAP_BRANCH_GRAPHIC_TYPES,
                    api_object: LineLocation,
                    lat: float, lon: float, index: int) -> NodeGraphicItem:
        """

        :param line_container:
        :param api_object:
        :param lat:
        :param lon:
        :param index:
        :return:
        """
        graphic_object = NodeGraphicItem(editor=self,
                                         line_container=line_container,
                                         api_object=api_object,
                                         lat=lat,
                                         lon=lon,
                                         index=index,
                                         r=0.005)

        self.graphics_manager.add_device(elm=api_object, graphic=graphic_object)

        # draw the node in the scene
        self.add_to_scene(graphic_object=graphic_object)

        return graphic_object

    def merge_lines(self):
        """

        :return:
        """
        if len(self.map.view.selectedItems) < 2:
            return 0

        it1 = self.map.view.selectedItems[0]
        it2 = self.map.view.selectedItems[1]

        if it1 == it2:
            return 0

        newline = Line()
        newline.copyData(it1.line_container.api_object)
        # ln1 = self.api_object.copy()

        better_first, better_second = compare_options(it1, it2)

        first_list = better_first.line_container.api_object.locations.data
        second_list = better_second.line_container.api_object.locations.data

        newline.locations.data = first_list + second_list

        idx = 0
        for nod in better_first.line_container.nodes_list:
            newline.locations.data[idx].lat = nod.lat
            newline.locations.data[idx].long = nod.lon
            idx = idx + 1

        for nod in better_second.line_container.nodes_list:
            newline.locations.data[idx].lat = nod.lat
            newline.locations.data[idx].long = nod.lon
            idx = idx + 1

        newL = self.add_api_line(newline, original=False)

        better_first.line_container.disable_line()
        better_second.line_container.disable_line()

    def removeNode(self, node: NodeGraphicItem):
        """
        Removes node from diagram and scene
        :param node: Node to remove
        """

        nod = self.graphics_manager.delete_device(node.api_object)
        self.map.diagram_scene.removeItem(nod)
        nod.line_container.removeNode(node)

    pass

    def removeSubstation(self, substation: SubstationGraphicItem):
        """

        :param substation:
        :return:
        """
        sub = self.graphics_manager.delete_device(substation.api_object)
        self.map.diagram_scene.removeItem(sub)

        br_types = [DeviceType.LineDevice, DeviceType.DCLineDevice, DeviceType.HVDCLineDevice]

        for ty in br_types:
            lins = self.graphics_manager.get_device_type_list(ty)
            for lin in lins:
                if (lin.api_object.get_substation_from() == substation.api_object
                        or lin.api_object.get_substation_to() == substation.api_object):
                    self.removeLine(lin)

    def removeLine(self, line: MAP_BRANCH_GRAPHIC_TYPES):
        """
        Removes line from diagram and scene
        :param line: Line to remove
        """
        lin = self.graphics_manager.delete_device(line.api_object)
        for seg in lin.segments_list:
            self.map.diagram_scene.removeItem(seg)

    def add_api_line(self, api_object: Line, original: bool = True) -> MapAcLine:
        """
        Adds a line with the nodes and segments
        :param api_object: Any branch type from the database
        :param original:
        :return: MapTemplateLine
        """
        line_container = MapAcLine(editor=self, api_object=api_object)

        line_container.original = original

        self.graphics_manager.add_device(elm=api_object, graphic=line_container)

        # create the nodes
        line_container.draw_all()

        # there is not need to add to the scene

        return line_container

    def add_api_dc_line(self, api_object: DcLine, original: bool = True) -> MapDcLine:
        """
        Adds a line with the nodes and segments
        :param api_object: Any branch type from the database
        :param original:
        :return: MapTemplateLine
        """
        line_container = MapDcLine(editor=self, api_object=api_object)

        line_container.original = original

        self.graphics_manager.add_device(elm=api_object, graphic=line_container)

        # create the nodes
        line_container.draw_all()

        # there is not need to add to the scene

        return line_container

    def add_api_hvdc_line(self, api_object: HvdcLine, original: bool = True) -> MapHvdcLine:
        """
        Adds a line with the nodes and segments
        :param api_object: Any branch type from the database
        :param original:
        :return: MapTemplateLine
        """
        line_container = MapHvdcLine(editor=self, api_object=api_object)

        line_container.original = original

        self.graphics_manager.add_device(elm=api_object, graphic=line_container)

        # create the nodes
        line_container.draw_all()

        # there is not need to add to the scene

        return line_container

    def add_api_fluid_path(self, api_object: FluidPath, original: bool = True) -> MapFluidPathLine:
        """
        Adds a line with the nodes and segments
        :param api_object: Any branch type from the database
        :param original:
        :return: MapTemplateLine
        """
        line_container = MapFluidPathLine(editor=self, api_object=api_object)

        line_container.original = original

        self.graphics_manager.add_device(elm=api_object, graphic=line_container)

        # create the nodes
        line_container.draw_all()

        # there is not need to add to the scene

        return line_container

    def update_connectors(self) -> None:
        """

        :return:
        """
        # for dev_tpe in [DeviceType.LineDevice,
        #                 DeviceType.DCLineDevice,
        #                 DeviceType.HVDCLineDevice,
        #                 DeviceType.FluidPathDevice]:
        #
        #     dev_dict = self.graphics_manager.get_device_type_dict(device_type=dev_tpe)
        #
        #     for idtag, graphic_object in dev_dict.items():
        #         graphic_object.update_connectors()
        #
        #     for idtag, graphic_object in dev_dict.items():
        #         graphic_object.end_update()
        pass

    def add_api_substation(self,
                           api_object: Substation,
                           lat: float,
                           lon: float) -> SubstationGraphicItem:
        """

        :param api_object:
        :param lat:
        :param lon:
        :return:
        """
        graphic_object = SubstationGraphicItem(editor=self,
                                               api_object=api_object,
                                               lat=lat,
                                               lon=lon)
        self.graphics_manager.add_device(elm=api_object, graphic=graphic_object)

        self.add_to_scene(graphic_object=graphic_object)

        return graphic_object

    def add_api_voltage_level(self,
                              substation_graphics: SubstationGraphicItem,
                              api_object: VoltageLevel) -> VoltageLevelGraphicItem:
        """

        :param substation_graphics:
        :param api_object:
        :return:
        """

        # The voltage level is created within the substation graphical object,
        # so there is no need to add it to the scene
        graphic_object = VoltageLevelGraphicItem(parent=substation_graphics,
                                                 editor=self,
                                                 api_object=api_object)

        self.graphics_manager.add_device(elm=api_object, graphic=graphic_object)

        return graphic_object

    def draw_diagram(self, diagram: MapDiagram) -> None:
        """
        Draw any diagram
        :param diagram: MapDiagram
        :return:
        """
        # first pass: create substations
        for category, points_group in diagram.data.items():

            if category == DeviceType.SubstationDevice.value:
                for idtag, location in points_group.locations.items():
                    self.add_api_substation(api_object=location.api_object,
                                            lon=location.longitude,
                                            lat=location.latitude)

        # second pass: create voltage levels
        for category, points_group in diagram.data.items():

            if category == DeviceType.VoltageLevelDevice.value:
                for idtag, location in points_group.locations.items():
                    if location.api_object.substation:
                        objectSubs = location.api_object.substation

                        # get the substation graphic object
                        substation_graphics = self.graphics_manager.query(elm=objectSubs)

                        # draw the voltage level
                        self.add_api_voltage_level(substation_graphics=substation_graphics,
                                                   api_object=location.api_object)

            elif category == DeviceType.LineDevice.value:
                for idtag, location in points_group.locations.items():
                    api_object: Line = location.api_object
                    self.add_api_line(api_object=api_object, original=True)  # no need to add to the scene

            elif category == DeviceType.DCLineDevice.value:
                for idtag, location in points_group.locations.items():
                    api_object: DcLine = location.api_object
                    self.add_api_dc_line(api_object=api_object, original=True)  # no need to add to the scene

            elif category == DeviceType.HVDCLineDevice.value:
                for idtag, location in points_group.locations.items():
                    api_object: HvdcLine = location.api_object
                    self.add_api_hvdc_line(api_object=api_object, original=True)  # no need to add to the scene

            elif category == DeviceType.FluidNodeDevice.value:
                pass  # TODO: implementar

            elif category == DeviceType.FluidPathDevice.value:
                for idtag, location in points_group.locations.items():
                    api_object: FluidPath = location.api_object
                    self.add_api_fluid_path(api_object=api_object, original=True)  # no need to add to the scene

        # sort voltage levels at the substations
        dev_dict = self.graphics_manager.get_device_type_dict(device_type=DeviceType.SubstationDevice)
        for idtag, graphic_object in dev_dict.items():
            graphic_object.sort_voltage_levels()

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

            if isinstance(elm, Substation):
                self.add_api_substation(api_object=elm,
                                        lon=elm.longitude,
                                        lat=elm.latitude)

            elif isinstance(elm, VoltageLevel):

                if elm.substation is not None:
                    # get the substation graphic object
                    substation_graphics = self.graphics_manager.query(elm=elm.substation)

                    # draw the voltage level
                    self.add_api_voltage_level(substation_graphics=substation_graphics,
                                               api_object=elm)

            elif isinstance(elm, Bus):

                if elm.substation is not None:
                    # get the substation graphic object
                    substation_graphics = self.graphics_manager.query(elm=elm.substation)

                    # draw the voltage level
                    self.add_api_substation(api_object=elm.substation,
                                            lon=substation_graphics.lon,
                                            lat=substation_graphics.lat)

            elif isinstance(elm, FluidNode):

                if injections_by_fluid_node is None:
                    injections_by_fluid_node = self.circuit.get_injection_devices_grouped_by_fluid_node()

                # TODO: maybe new thing?
                self.add_api_fluid_node(node=elm,
                                        injections_by_tpe=injections_by_fluid_node.get(elm, dict()))

            elif isinstance(elm, Line):
                self.add_api_line(elm)

            elif isinstance(elm, DcLine):
                self.add_api_dc_line(elm)

            elif isinstance(elm, HvdcLine):
                self.add_api_hvdc_line(elm)

            elif isinstance(elm, FluidPath):
                self.add_api_fluid_path(elm)

            else:
                pass

        else:
            logger.add_warning("Device already added", device_class=elm.device_type.value, device=elm.name)

    def dropEvent(self, event: QDropEvent):
        """
        On element drop...
        :param event: QDropEvent
        """
        super().dropEvent(event)

        if event.mimeData().hasFormat('component/name'):
            obj_type = event.mimeData().data('component/name')

            point0 = self.map.view.mapToScene(event.position().x(), event.position().y())
            x0 = point0.x()
            y0 = point0.y()
            lat, lon = self.to_lat_lon(x=x0, y=y0)

            print(f"Droped at x:{x0}, y:{y0}, lat:{lat}, lon:{lon}")

            if obj_type == self.library_model.get_substation_mime_data():
                print("Create substation...")
                api_object = Substation(name=f"Substation {self.circuit.get_substation_number()}",
                                        latitude=lat,
                                        longitude=lon)
                self.circuit.add_substation(obj=api_object)
                self.add_api_substation(api_object=api_object, lat=lat, lon=lon)

    def wheelEvent(self, event: QWheelEvent):
        """

        :param event:
        :return:
        """

        # SANTIAGO: NO TOCAR ESTO ES EL COMPORTAMIENTO DESEADO

        self.Update_widths()

    def Update_widths(self):

        max_zoom = self.map.max_level
        min_zoom = self.map.min_level
        zoom = self.map.zoom_factor
        scale = self.diagram.min_branch_width + (zoom - min_zoom) / (max_zoom - min_zoom)

        # rescale lines
        for dev_tpe in [DeviceType.LineDevice,
                        DeviceType.DCLineDevice,
                        DeviceType.HVDCLineDevice,
                        DeviceType.FluidPathDevice]:
            graphics_dict = self.graphics_manager.get_device_type_dict(device_type=dev_tpe)
            for key, lne in graphics_dict.items():
                lne.setWidthScale(scale)

    def change_size_and_pen_width_all(self, new_radius, pen_width):
        """
        Change the size and pen width of all elements in Schema.
        :param new_radius: New radius for the nodes.
        :param pen_width: New pen width for the nodes.
        """
        dev_dict = self.graphics_manager.get_device_type_dict(device_type=DeviceType.LineLocation)

        for idtag, graphic_object in dev_dict.items():
            graphic_object.resize(new_radius)
            graphic_object.change_pen_width(pen_width)

    def colour_results(self,
                       buses: List[Bus],
                       branches: List[BRANCH_TYPES],
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

        voltage_cmap = viz.get_voltage_color_map()
        loading_cmap = viz.get_loading_color_map()
        bus_types = ['', 'PQ', 'PV', 'Slack', 'None', 'Storage']

        vmin = 0
        vmax = 1.2
        vrng = vmax - vmin
        vabs = np.abs(voltages)
        vang = np.angle(voltages, deg=True)
        vnorm = (vabs - vmin) / vrng

        n = len(buses)
        longitudes = np.zeros(n)
        latitudes = np.zeros(n)
        nodes_dict = dict()
        for i, bus in enumerate(buses):

            # try to find the diagram object of the DB object
            graphic_object = self.graphics_manager.query(bus)

            if graphic_object:
                longitudes[i] = bus.longitude
                latitudes[i] = bus.latitude
                nodes_dict[bus.name] = (bus.latitude, bus.longitude)

        # Pnorm = np.abs(Sbus.real) / np.max(Sbus.real)
        #
        # add node positions
        # for i, bus in enumerate(circuit.buses):
        #
        #     tooltip = str(i) + ': ' + bus.name + '\n' \
        #               + 'V:' + "{:10.4f}".format(vabs[i]) + " <{:10.4f}".format(vang[i]) + 'º [p.u.]\n' \
        #               + 'V:' + "{:10.4f}".format(vabs[i] * bus.Vnom) + " <{:10.4f}".format(vang[i]) + 'º [kV]'
        #     if Sbus is not None:
        #         tooltip += '\nS: ' + "{:10.4f}".format(Sbus[i] * Sbase) + ' [MVA]'
        #     if types is not None:
        #         tooltip += '\nType: ' + bus_types[types[i]]
        #
        #     # get the line colour
        #     r, g, b, a = voltage_cmap(vnorm[i])
        #     color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
        #     html_color = color.name()
        #
        #     if use_flow_based_width:
        #         radius = int(np.floor(min_bus_width + Pnorm[i] * (max_bus_width - min_bus_width)))
        #     else:
        #         radius = 50
        #
        #     position = bus.get_coordinates()
        #     html = '<i>' + tooltip + '</i>'
        #     folium.Circle(position,
        #                   popup=html,
        #                   radius=radius,
        #                   color=html_color,
        #                   tooltip=tooltip).add_to(marker_cluster)

        # Try colouring the branches
        if len(branches):

            lnorm = np.abs(loadings)
            lnorm[lnorm == np.inf] = 0
            Sfabs = np.abs(Sf)
            Sfnorm = Sfabs / np.max(Sfabs + 1e-20)
            for i, branch in enumerate(branches):

                # try to find the diagram object of the DB object
                graphic_object: Union[MapAcLine, MapDcLine] = self.graphics_manager.query(branch)

                if graphic_object:

                    # compose the tooltip
                    tooltip = str(i) + ': ' + branch.name
                    tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'
                    if Sf is not None:
                        tooltip += '\nPower: ' + "{:10.4f}".format(Sf[i]) + ' [MVA]'
                    if losses is not None:
                        tooltip += '\nLosses: ' + "{:10.4f}".format(losses[i]) + ' [MVA]'

                    # get the line colour
                    a = 255
                    if cmap == palettes.Colormaps.Green2Red:
                        b, g, r = palettes.green_to_red_bgr(lnorm[i])

                    elif cmap == palettes.Colormaps.Heatmap:
                        b, g, r = palettes.heatmap_palette_bgr(lnorm[i])

                    elif cmap == palettes.Colormaps.TSO:
                        b, g, r = palettes.tso_line_palette_bgr(branch.get_max_bus_nominal_voltage(), lnorm[i])

                    else:
                        r, g, b, a = loading_cmap(lnorm[i])
                        r *= 255
                        g *= 255
                        b *= 255
                        a *= 255

                    color = QColor(r, g, b, a)
                    style = Qt.SolidLine
                    if use_flow_based_width:
                        weight = int(
                            np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width) * 0.1))
                    else:
                        weight = 0.5

                    graphic_object.set_colour(color=color, w=weight, style=style, tool_tip=tooltip)

        # try colouring the HVDC lines
        if len(hvdc_lines) > 0:

            lnorm = np.abs(hvdc_loading)
            lnorm[lnorm == np.inf] = 0
            Sfabs = np.abs(hvdc_Pf)
            Sfnorm = Sfabs / np.max(Sfabs + 1e-9)

            for i, branch in enumerate(hvdc_lines):

                # try to find the diagram object of the DB object
                graphic_object: MapHvdcLine = self.graphics_manager.query(branch)

                if graphic_object:

                    # compose the tooltip
                    tooltip = str(i) + ': ' + branch.name
                    tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'
                    if Sf is not None:
                        tooltip += '\nPower: ' + "{:10.4f}".format(hvdc_Pf[i]) + ' [MW]'
                    if losses is not None:
                        tooltip += '\nLosses: ' + "{:10.4f}".format(hvdc_losses[i]) + ' [MW]'

                    # get the line colour
                    a = 255
                    if cmap == palettes.Colormaps.Green2Red:
                        b, g, r = palettes.green_to_red_bgr(lnorm[i])

                    elif cmap == palettes.Colormaps.Heatmap:
                        b, g, r = palettes.heatmap_palette_bgr(lnorm[i])

                    elif cmap == palettes.Colormaps.TSO:
                        b, g, r = palettes.tso_line_palette_bgr(branch.get_max_bus_nominal_voltage(), lnorm[i])

                    else:
                        r, g, b, a = loading_cmap(lnorm[i])
                        r *= 255
                        g *= 255
                        b *= 255
                        a *= 255

                    color = QColor(r, g, b, a)
                    style = Qt.SolidLine
                    if use_flow_based_width:
                        weight = int(
                            np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width) * 0.1))
                    else:
                        weight = 0.5

                    graphic_object.set_colour(color=color, w=weight, style=style, tool_tip=tooltip)

    def get_image(self, transparent: bool = False) -> Tuple[QImage, int, int]:
        """
        get the current picture
        :return: QImage, width, height
        """
        w = self.width()
        h = self.height()

        # image = QImage(w, h, QImage.Format_RGB32)
        # image.fill(Qt.white)
        #
        # painter = QPainter(image)
        # painter.setRenderHint(QPainter.Antialiasing)
        # # self.view.render(painter)  # self.view stores the grid widgets
        # self.render(painter)
        # painter.end()
        image = self.grab().toImage()

        return image, w, h

    def take_picture(self, filename: str):
        """
        Save the grid to a png file
        """
        name, extension = os.path.splitext(filename.lower())

        if extension == '.png':
            image, _, _ = self.get_image()
            image.save(filename)

        elif extension == '.svg':
            w = self.width()
            h = self.height()
            svg_gen = QSvgGenerator()
            svg_gen.setFileName(filename)
            svg_gen.setSize(QSize(w, h))
            svg_gen.setViewBox(QRect(0, 0, w, h))
            svg_gen.setTitle("Electrical grid schematic")
            svg_gen.setDescription("An SVG drawing created by GridCal")

            painter = QPainter(svg_gen)
            self.render(painter)
            painter.end()
        else:
            raise Exception('Extension ' + str(extension) + ' not supported :(')

    def new_substation_diagram(self, substation: Substation):
        """

        :param substation:
        :return:
        """
        if self.call_new_substation_diagram_func is not None:
            self.call_new_substation_diagram_func(substation)
        else:
            print("call_new_substation_diagram_func is None :( ")


def generate_map_diagram(substations: List[Substation],
                         voltage_levels: List[VoltageLevel],
                         lines: List[Line],
                         dc_lines: List[DcLine],
                         hvdc_lines: List[HvdcLine],
                         fluid_nodes: List[FluidNode],
                         fluid_paths: List[FluidPath],
                         prog_func: Union[Callable, None] = None,
                         text_func: Union[Callable, None] = None,
                         name='Map diagram') -> MapDiagram:
    """
    Add a elements to the schematic scene
    :param substations: list of Substation objects
    :param voltage_levels: list of VoltageLevel objects
    :param lines: list of Line objects
    :param dc_lines: list of DcLine objects
    :param hvdc_lines: list of HvdcLine objects
    :param fluid_nodes: list of FluidNode objects
    :param fluid_paths: list of FluidPath objects
    :param prog_func: progress report function
    :param text_func: Text report function
    :param name: name of the diagram
    """

    diagram = MapDiagram(name=name)

    # first create the buses
    if text_func is not None:
        text_func('Creating schematic buses')

    nn = len(substations)
    for i, substation in enumerate(substations):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=substation, location=MapLocation(latitude=substation.latitude,
                                                                  longitude=substation.longitude,
                                                                  api_object=substation))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic buses')

    nn = len(voltage_levels)
    for i, voltageLevel in enumerate(voltage_levels):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=voltageLevel, location=MapLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic fluid nodes devices')

    nn = len(fluid_nodes)
    for i, elm in enumerate(fluid_nodes):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_upfc(branch)
        diagram.set_point(device=elm, location=MapLocation())

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic line devices')

    nn = len(lines)
    for i, branch in enumerate(lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_line(branch)
        diagram.set_point(device=branch, location=MapLocation())

        # register all the line locations
        # if branch.bus_from is not None:
        #     diagram.set_point(device=branch.bus_from, location=MapLocation(latitude=branch.bus_from.latitude,
        #                                                                    longitude=branch.bus_from.longitude,
        #                                                                    altitude=0))

        for loc in branch.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

        # if branch.bus_to is not None:
        #     diagram.set_point(device=branch.bus_to, location=MapLocation(latitude=branch.bus_to.latitude,
        #                                                                  longitude=branch.bus_to.longitude,
        #                                                                  altitude=0))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic line devices')

    nn = len(dc_lines)
    for i, branch in enumerate(dc_lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_dc_line(branch)
        diagram.set_point(device=branch, location=MapLocation())

        # register all the line locations
        for loc in branch.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic HVDC devices')

    nn = len(hvdc_lines)
    for i, branch in enumerate(hvdc_lines):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_hvdc(branch)
        diagram.set_point(device=branch, location=MapLocation())

        # register all the line locations
        for loc in branch.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

    # --------------------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func('Creating schematic fluid paths devices')

    nn = len(fluid_paths)
    for i, elm in enumerate(fluid_paths):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        # branch.graphic_obj = self.add_api_upfc(branch)
        diagram.set_point(device=elm, location=MapLocation())

        # register all the line locations
        for loc in elm.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

    # find the diagram cented and set it internally
    diagram.set_center()

    return diagram
