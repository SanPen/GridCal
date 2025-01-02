# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import os
from typing import Union, List, Tuple, Dict, TYPE_CHECKING
import json
import numpy as np
import math
import pandas as pd
from matplotlib import pyplot as plt

from PySide6.QtWidgets import QGraphicsItem
from collections.abc import Callable
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtCore import (Qt, QSize, QRect, QMimeData, QIODevice, QByteArray, QDataStream, QModelIndex)
from PySide6.QtGui import (QIcon, QPixmap, QImage, QPainter, QStandardItemModel, QStandardItem, QColor,
                           QDropEvent, QWheelEvent)

from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from GridCal.Gui.SubstationDesigner.substation_designer import SubstationDesigner
from GridCalEngine.Devices.Diagrams.map_location import MapLocation
from GridCalEngine.Devices.Substation import Bus
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Devices.Diagrams.map_diagram import MapDiagram
from GridCalEngine.Devices.Fluid import FluidNode, FluidPath
from GridCalEngine.basic_structures import Vec, CxVec, IntVec
from GridCalEngine.Devices.Substation.substation import Substation
from GridCalEngine.Devices.Substation.voltage_level import VoltageLevel
from GridCalEngine.Devices.Branches.line_locations import LineLocation
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import DeviceType, ResultTypes
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
from GridCalEngine.Simulations.PowerFlow.power_flow_ts_results import PowerFlowTimeSeriesResults

from GridCal.Gui.Diagrams.MapWidget.Branches.map_ac_line import MapAcLine
from GridCal.Gui.Diagrams.MapWidget.Branches.map_dc_line import MapDcLine
from GridCal.Gui.Diagrams.MapWidget.Branches.map_hvdc_line import MapHvdcLine
from GridCal.Gui.Diagrams.MapWidget.Branches.map_fluid_path import MapFluidPathLine
from GridCal.Gui.Diagrams.MapWidget.Branches.line_location_graphic_item import LineLocationGraphicItem
from GridCal.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
from GridCal.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem
from GridCal.Gui.Diagrams.MapWidget.map_widget import MapWidget
from GridCal.Gui.Diagrams.MapWidget.Branches.new_line_dialogue import NewMapLineDialogue
import GridCal.Gui.Visualization.visualization as viz
import GridCalEngine.Devices.Diagrams.palettes as palettes
from GridCal.Gui.Diagrams.graphics_manager import ALL_MAP_GRAPHICS
from GridCal.Gui.Diagrams.MapWidget.Tiles.tiles import Tiles
from GridCal.Gui.Diagrams.base_diagram_widget import BaseDiagramWidget
from GridCal.Gui.messages import error_msg, info_msg

if TYPE_CHECKING:
    from GridCal.Gui.Main.SubClasses.Model.diagrams import DiagramsMain

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


def compare_options(it1: LineLocationGraphicItem, it2: LineLocationGraphicItem):
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
        return it1, it2, it1.line_container.api_object.bus_from, it2.line_container.api_object.bus_to
    else:
        return it2, it1, it2.line_container.api_object.bus_from, it1.line_container.api_object.bus_to


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
                txt = self.data(idx, Qt.ItemDataRole.DisplayRole)

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
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled


class GridMapWidget(BaseDiagramWidget):
    """
    GridMapWidget
    """

    def __init__(self,
                 gui: DiagramsMain,
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
        GridMapWidget
        :param tile_src: Tiles instance
        :param start_level: starting level
        :param longitude: Center point Longitude (deg)
        :param latitude: Center point Latitude (deg)
        :param name: Name of the diagram
        :param circuit: MultiCircuit instance
        :param diagram: Diagram instance (optional)
        :param call_delete_db_element_func: function pointer to call on delete (optional)
        :param call_new_substation_diagram_func: function pointer to call on new_substation (optional)
        """

        BaseDiagramWidget.__init__(self,
                                   gui=gui,
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
                             editor=self,
                             zoom_callback=self.zoom_callback,
                             position_callback=self.position_callback)

        # Any representation on the map must be done after this Goto Function
        self.map.GotoLevelAndPosition(level=6, longitude=longitude, latitude=latitude)

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

    def create_line_location_graphic(self,
                                     line_container: MapLineContainer,
                                     api_object: LineLocation,
                                     lat: float,
                                     lon: float,
                                     index: int) -> LineLocationGraphicItem:
        """

        :param line_container:
        :param api_object:
        :param lat:
        :param lon:
        :param index:
        :return:
        """
        graphic_object = LineLocationGraphicItem(editor=self,
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

        selected_items = self.map.get_selected()
        selectedItems = []
        for item in selected_items:
            selectedItems.append(item)

        if len(selectedItems) < 2:
            return 0

        it1 = selectedItems[0]
        it2 = selectedItems[1]

        if it1 == it2:
            return 0

        # TODO: Review this and possibly link to existing functions
        # new_line = Line()
        # new_line.set_data_from(it1.line_container.api_object)
        # ln1 = self.api_object.copy()
        new_line = it1.line_container.api_object.copy()

        better_first, better_second, bus_from, bus_to = compare_options(it1, it2)

        first_list = better_first.line_container.api_object.locations.data
        second_list = better_second.line_container.api_object.locations.data

        new_line.locations.data = first_list + second_list

        new_line.bus_from = bus_from
        new_line.bus_to = bus_to

        idx = 0
        for nod in better_first.line_container.nodes_list:
            new_line.locations.data[idx].lat = nod.lat
            new_line.locations.data[idx].long = nod.lon
            idx = idx + 1

        for nod in better_second.line_container.nodes_list:
            new_line.locations.data[idx].lat = nod.lat
            new_line.locations.data[idx].long = nod.lon
            idx = idx + 1

        self.add_api_line(new_line, original=False)
        self.circuit.add_line(new_line)

        better_first.line_container.disable_line()
        better_second.line_container.disable_line()

    def get_selected_substations(self) -> List[SubstationGraphicItem]:
        """
        Get the selected substations graphics
        :return: List[SubstationGraphicItem]
        """
        return [s for s in self.map.view.selected_items() if isinstance(s, SubstationGraphicItem)]

    # def get_selected(self):
    #     return self.map.get_selected()

    def create_new_line_wizard(self):
        """
        Create a new line in the map with dialogues
        """

        selected_items = self.get_selected_substations()

        if len(selected_items) != 2:
            error_msg(text="Please select two substations", title="Create new line")
            return None

        it1: SubstationGraphicItem = selected_items[0]
        it2: SubstationGraphicItem = selected_items[1]

        if it1 == it2:
            error_msg(text="Somehow the two substations are the same :(", title="Create new line")
            return None

        dialog = NewMapLineDialogue(grid=self.circuit, se_from=it1.api_object, se_to=it2.api_object)
        dialog.exec()
        if dialog.is_valid():
            bus1 = dialog.bus_from()
            bus2 = dialog.bus_to()
            if bus1 is not None and bus2 is not None:
                new_line = Line(bus_from=bus1, bus_to=bus2)
                self.add_api_line(new_line, original=True)
                self.circuit.add_line(new_line)
            else:
                error_msg(text="Some of the buses was None :(", title="Create new line")
                return None

    def remove_line_location_graphic(self, node: LineLocationGraphicItem):
        """
        Removes node from diagram and scene
        :param node: Node to remove
        """

        nod = self.graphics_manager.delete_device(node.api_object)
        self.map.diagram_scene.removeItem(nod)
        nod.line_container.remove_line_location_graphic(node)

    def remove_substation(self, substation: SubstationGraphicItem):
        """

        :param substation:
        :return:
        """
        sub = self.graphics_manager.delete_device(substation.api_object)
        self.map.diagram_scene.removeItem(sub)

        br_types = [DeviceType.LineDevice, DeviceType.DCLineDevice, DeviceType.HVDCLineDevice]

        for tpe in br_types:
            elms = self.graphics_manager.get_device_type_list(tpe)
            for elm in elms:
                if (elm.api_object.get_substation_from() == substation.api_object
                        or elm.api_object.get_substation_to() == substation.api_object):
                    self.remove_branch_graphic(elm)

    def remove_branch_graphic(self, line: MAP_BRANCH_GRAPHIC_TYPES):
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

        # there is nt need to add to the scene
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
        graphic_object = SubstationGraphicItem(editor=self, api_object=api_object, lat=lat, lon=lon,
                                               r=self.diagram.min_bus_width)
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

        # second pass: create the rest of devices
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

    def add_object_to_the_schematic(self, elm: ALL_DEV_TYPES, logger: Logger = Logger()):
        """

        :param elm:
        :param logger:
        :return:
        """
        graphic_obj = self.graphics_manager.query(elm=elm)

        if graphic_obj is None:

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

            elif isinstance(elm, Line):
                line_container = self.add_api_line(elm)
                for segment in line_container.segments_list:
                    self.add_to_scene(graphic_object=segment)

            elif isinstance(elm, DcLine):
                line_container = self.add_api_dc_line(elm)
                for segment in line_container.segments_list:
                    self.add_to_scene(graphic_object=segment)

            elif isinstance(elm, HvdcLine):
                line_container = self.add_api_hvdc_line(elm)
                for segment in line_container.segments_list:
                    self.add_to_scene(graphic_object=segment)

            elif isinstance(elm, FluidPath):
                line_container = self.add_api_fluid_path(elm)
                for segment in line_container.segments_list:
                    self.add_to_scene(graphic_object=segment)

            else:
                logger.add_warning("Unsupported device class",
                                   device_class=elm.device_type.value,
                                   device=elm.name)

        else:

            self.add_to_scene(graphic_obj)

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

            if obj_type == self.library_model.get_substation_mime_data():
                self.create_substation_with_dialogue(lat=lat, lon=lon)

    def create_substation_with_dialogue(self, lat, lon):
        """
        Create a substation using the dialogue
        :param lat:
        :param lon:
        :return:
        """
        kv = self.gui.get_default_voltage()
        dlg = SubstationDesigner(grid=self.circuit, default_voltage=kv)
        dlg.exec()
        if dlg.was_ok():

            # create the SE
            se_object = Substation(name=dlg.get_name(), latitude=lat, longitude=lon)

            self.circuit.add_substation(obj=se_object)
            substation_graphics = self.add_api_substation(api_object=se_object, lat=lat, lon=lon)

            for vl_template in dlg.get_voltage_levels():
                # substation_graphics.add_voltage_level()
                vl = VoltageLevel(name=f"{se_object.name} @{kv}KV VL",
                                  Vnom=vl_template.voltage,
                                  substation=se_object)
                self.circuit.add_voltage_level(vl)

                bus = Bus(name=f"{se_object.name} @{kv}KV bus",
                          Vnom=vl_template.voltage,
                          substation=se_object,
                          voltage_level=vl)
                self.circuit.add_bus(obj=bus)

                # add the vl graphics
                self.add_api_voltage_level(substation_graphics=substation_graphics, api_object=vl)

            # sort voltage levels
            substation_graphics.sort_voltage_levels()

    def wheelEvent(self, event: QWheelEvent):
        """

        :param event:
        :return:
        """

        # SANTIAGO: DO NOT TOUCH, THIS IS THE DESIRED BEHAVIOUR
        self.update_device_sizes()

    def get_branch_width(self) -> float:
        """
        Get the desired branch width
        :return:
        """
        max_zoom = self.map.max_level
        min_zoom = self.map.min_level
        zoom = self.map.zoom_factor
        scale = self.diagram.min_branch_width + (zoom - min_zoom) / (max_zoom - min_zoom)
        return scale

    def get_arrow_scale(self) -> float:
        """
        Get the desired branch width
        :return:
        """
        max_zoom = self.map.max_level
        min_zoom = self.map.min_level
        zoom = self.map.zoom_factor
        scale = self.diagram.arrow_size + (zoom - min_zoom) / (max_zoom - min_zoom)
        return scale

    def get_substation_scale(self) -> float:
        """
        Get the desired branch width
        :return:
        """
        max_zoom = self.map.max_level
        min_zoom = self.map.min_level
        zoom = self.map.zoom_factor
        scale = self.diagram.min_bus_width + (zoom - min_zoom) / (max_zoom - min_zoom)
        return scale

    def update_device_sizes(self) -> None:
        """
        Updat ethe devices' sizes
        :return:
        """

        br_scale = self.get_branch_width()
        arrow_scale = self.get_arrow_scale()
        se_scale = self.get_substation_scale()

        # rescale lines
        for dev_tpe in [DeviceType.LineDevice,
                        DeviceType.DCLineDevice,
                        DeviceType.HVDCLineDevice,
                        DeviceType.FluidPathDevice]:
            graphics_dict = self.graphics_manager.get_device_type_dict(device_type=dev_tpe)

            for key, elm_graphics in graphics_dict.items():
                elm_graphics.set_width_scale(branch_scale=br_scale, arrow_scale=arrow_scale)

        # rescale substations
        data: Dict[str, SubstationGraphicItem] = self.graphics_manager.get_device_type_dict(DeviceType.SubstationDevice)

        for se_key, elm_graphics in data.items():
            elm_graphics.set_api_object_color()
            elm_graphics.re_scale(r=se_scale)

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
                       vsc_Pf: Vec = None,
                       vsc_Pt: Vec = None,
                       vsc_Qt: Vec = None,
                       vsc_losses: Vec = None,
                       vsc_loading: Vec = None,
                       vsc_active: IntVec = None,
                       ma: Vec = None,
                       theta: Vec = None,
                       fluid_node_p2x_flow: Vec = None,
                       fluid_node_current_level: Vec = None,
                       fluid_node_spillage: Vec = None,
                       fluid_node_flow_in: Vec = None,
                       fluid_node_flow_out: Vec = None,
                       fluid_path_flow: Vec = None,
                       fluid_injection_flow: Vec = None,
                       use_flow_based_width: bool = False,
                       min_branch_width: int = 5,
                       max_branch_width=5,
                       min_bus_width=20,
                       max_bus_width=20,
                       cmap: palettes.Colormaps = None):
        """
        Color objects based on the results passed
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
        :param vsc_Pf: VSC branch flows "from" [MW]
        :param vsc_Pt: VSC branch flows "to" [MW]
        :param vsc_Qt: VSC branch flows "to" [Mvar]
        :param vsc_losses: VSC branch losses [MW]
        :param vsc_loading: VSC Branch loading [%]
        :param vsc_active: VSC Branch status
        :param loading_label: String saling whatever the loading label means
        :param ma: branch phase shift angle (rad)
        :param theta: branch tap module (p.u.)
        :param fluid_node_p2x_flow: P2X flow rate (m3)
        :param fluid_node_current_level: Current level (m3)
        :param fluid_node_spillage: Spillage (m3)
        :param fluid_node_flow_in: Flow rate (m3)
        :param fluid_node_flow_out: Flow rate (m3)
        :param fluid_injection_flow: Injection rate (m3)
        :param fluid_path_flow: fluid flow (m3)
        :param use_flow_based_width: use branch width based on the actual flow?
        :param min_branch_width: Minimum branch width [px]
        :param max_branch_width: Maximum branch width [px]
        :param min_bus_width: Minimum bus width [px]
        :param max_bus_width: Maximum bus width [px]
        :param cmap: Color map [palettes.Colormaps]
        """

        voltage_cmap = viz.get_voltage_color_map()
        loading_cmap = viz.get_loading_color_map()

        # vmin = 0
        # vmax = 1.2
        # vrng = vmax - vmin
        # vabs = np.abs(voltages)
        # vang = np.angle(voltages, deg=True)
        # vnorm = (vabs - vmin) / vrng
        nbus = self.circuit.get_bus_number()

        longitudes = np.zeros(nbus)
        latitudes = np.zeros(nbus)
        nodes_dict = dict()
        for i, bus in enumerate(self.circuit.buses):

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
        #               + 'V:' + "{:10.4f}".format(vabs[i] * bus.Vnom) + " <{:10.4f}".format(vang[i]) + 'º [KV]'
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

        arrow_scale = self.get_arrow_scale()

        # Try colouring the branches
        if self.circuit.get_branch_number_wo_hvdc():

            lnorm = np.abs(loadings)
            lnorm[lnorm == np.inf] = 0
            Sfabs = np.abs(Sf)
            Sfnorm = Sfabs / np.max(Sfabs + 1e-20)
            for i, branch in enumerate(self.circuit.get_branches_wo_hvdc_iter()):

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
                    style = Qt.PenStyle.SolidLine
                    if use_flow_based_width:
                        weight = int(
                            np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width) * 0.1))
                    else:
                        weight = self.get_branch_width()

                    graphic_object.set_colour(color=color, style=style, tool_tip=tooltip)
                    graphic_object.set_width_scale(branch_scale=weight, arrow_scale=arrow_scale)

                    if hasattr(graphic_object, 'set_arrows_with_power'):
                        graphic_object.set_arrows_with_power(
                            Sf=Sf[i] if Sf is not None else None,
                            St=St[i] if St is not None else None
                        )
                else:
                    # the graphic object is None
                    pass

        # try colouring the HVDC lines
        if self.circuit.get_hvdc_number() > 0:

            lnorm = np.abs(hvdc_loading)
            lnorm[lnorm == np.inf] = 0
            Sfabs = np.abs(hvdc_Pf)
            Sfnorm = Sfabs / np.max(Sfabs + 1e-9)

            for i, branch in enumerate(self.circuit.hvdc_lines):

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
                    style = Qt.PenStyle.SolidLine
                    if use_flow_based_width:
                        weight = int(
                            np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width) * 0.1)
                        )
                    else:
                        weight = self.get_branch_width()

                    tooltip = str(i) + ': ' + graphic_object.api_object.name
                    tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(
                        abs(hvdc_loading[i]) * 100) + ' [%]'

                    tooltip += '\nPower (from):\t' + "{:10.4f}".format(hvdc_Pf[i]) + ' [MW]'

                    if hvdc_losses is not None:
                        tooltip += '\nPower (to):\t' + "{:10.4f}".format(hvdc_Pt[i]) + ' [MW]'
                        tooltip += '\nLosses: \t\t' + "{:10.4f}".format(hvdc_losses[i]) + ' [MW]'
                        graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_Pf[i], Pt=hvdc_Pt[i])
                    else:
                        graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_Pf[i], Pt=-hvdc_Pf[i])

                    graphic_object.set_colour(color=color, style=style, tool_tip=tooltip)
                    graphic_object.set_width_scale(branch_scale=weight, arrow_scale=arrow_scale)

        if fluid_path_flow is not None:

            if self.circuit.get_fluid_paths_number() == len(fluid_path_flow):
                for i, elm in enumerate(self.circuit.fluid_paths):

                    # try to find the diagram object of the DB object
                    graphic_object = self.graphics_manager.query(elm)

                    if graphic_object:
                        pass

    def get_image(self, transparent: bool = False) -> QImage:
        """
        get the current picture
        :return: QImage, width, height
        """
        image = self.map.grab().toImage()

        return image

    def take_picture(self, filename: str):
        """
        Save the grid to a png file
        """
        name, extension = os.path.splitext(filename.lower())

        if extension == '.png':
            image = self.get_image()
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

    def copy(self) -> "GridMapWidget":
        """
        Deep copy of this widget
        :return: GridMapWidget
        """
        d_copy = MapDiagram(name=self.diagram.name + '_copy')
        j_data = json.dumps(self.diagram.get_data_dict(), indent=4)
        d_copy.parse_data(data=json.loads(j_data),
                          obj_dict=self.circuit.get_all_elements_dict_by_type(add_locations=True),
                          logger=self.logger)

        return GridMapWidget(
            gui=self.gui,
            tile_src=self.map.tile_src,
            start_level=self.diagram.start_level,
            longitude=self.diagram.longitude,
            latitude=self.diagram.latitude,
            name=self.diagram.name,
            circuit=self.circuit,
            diagram=self.diagram,
            call_new_substation_diagram_func=self.call_new_substation_diagram_func,
            call_delete_db_element_func=self.call_delete_db_element_func
        )

    def consolidate_coordinates(self):
        """
        Consolidate the graphic elements' x, y coordinates into the API DB values
        """
        graphics: List[SubstationGraphicItem] = self.graphics_manager.get_device_type_list(
            device_type=DeviceType.SubstationDevice)
        for gelm in graphics:
            gelm.api_object.latitude = gelm.lat
            gelm.api_object.longitude = gelm.lon

    def plot_substation(self, i: int, api_object: Substation):
        """
        Plot branch results
        :param i: bus index
        :param api_object: Substation API object
        :return:
        """

        fig = plt.figure(figsize=(12, 8))
        ax_1 = fig.add_subplot(211)
        ax_1.set_title('Power', fontsize=14)
        ax_1.set_ylabel('Injections [MW]', fontsize=11)

        ax_2 = fig.add_subplot(212, sharex=ax_1)
        ax_2.set_title('Time', fontsize=14)
        ax_2.set_ylabel('Voltage [p.u]', fontsize=11)

        # set time
        x = self.circuit.get_time_array()

        if x is not None:
            if len(x) > 0:

                # Get all devices grouped by bus
                all_data = self.circuit.get_injection_devices_grouped_by_substation()

                # search drivers for voltage data
                for driver, results in self.gui.session.drivers_results_iter():
                    if results is not None:
                        if isinstance(results, PowerFlowTimeSeriesResults):
                            table = results.mdl(result_type=ResultTypes.BusVoltageModule)
                            table.plot_device(ax=ax_2, device_idx=i, title="Power flow")
                        elif isinstance(results, OptimalPowerFlowTimeSeriesResults):
                            table = results.mdl(result_type=ResultTypes.BusVoltageModule)
                            table.plot_device(ax=ax_2, device_idx=i, title="Optimal power flow")

                # Injections
                # filter injections by bus
                bus_devices = all_data.get(api_object, None)
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

                    try:
                        # yt area plots
                        df.plot.area(ax=ax_1)
                    except ValueError:
                        # use regular plots
                        df.plot(ax=ax_1)

                plt.legend()
                fig.suptitle(api_object.name, fontsize=20)

                # plot the profiles
                plt.show()
        else:
            info_msg("There are no time series, so nothing to plot :/")


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
