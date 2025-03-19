# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import os
from typing import Union, List, Set, Tuple, Dict, TYPE_CHECKING
import json
import numpy as np
import math
import pandas as pd
from matplotlib import pyplot as plt

from PySide6.QtWidgets import QGraphicsItem, QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton
from collections.abc import Callable
from PySide6.QtCore import (Qt, QMimeData, QIODevice, QByteArray, QDataStream, QModelIndex, QRunnable, QThreadPool,
                            QEventLoop)
from PySide6.QtGui import (QIcon, QPixmap, QImage, QStandardItemModel, QStandardItem, QColor, QDropEvent)

from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from GridCal.Gui.Diagrams.MapWidget.Branches.map_line_segment import MapLineSegment
from GridCal.Gui.SubstationDesigner.substation_designer import SubstationDesigner
from GridCal.Gui.general_dialogues import CheckListDialogue, ElementsDialogue
from GridCalEngine.Devices.Diagrams.map_location import MapLocation
from GridCalEngine.Devices.Substation import Bus
from GridCalEngine.Devices.Branches.line import Line, accept_line_connection
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
from GridCalEngine.enumerations import Colormaps

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
from GridCal.Gui.object_model import ObjectsModel
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


class MapLibraryModel(QStandardItemModel):
    """
    Items model to host the draggable icons
    This is the list of draggable items
    """

    def __init__(self) -> None:
        """
        Items model to host the draggable icons
        """
        super().__init__()

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
        mime_data = QMimeData()
        for idx in idxs:
            if idx.isValid():
                txt = self.data(idx, Qt.ItemDataRole.DisplayRole)

                data = QByteArray()
                stream = QDataStream(data, QIODevice.WriteOnly)
                stream.writeQString(txt)

                mime_data.setData('component/name', data)
        return mime_data

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """

        :param index:
        :return:
        """
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled


class SelectionDialog(QDialog):
    """
    # Create a non-modal dialog that will stay on top but allow interaction with the map
    """

    def __init__(self, branch: MAP_BRANCH_GRAPHIC_TYPES, vnom: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Waiting for Selection")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout()

        # Add instructions
        instruction_label = QLabel(f"Click on a substation to reconnect branch {branch.api_object.name}")
        instruction_label.setWordWrap(True)
        layout.addWidget(instruction_label)

        # Add more detailed instructions
        detail_label = QLabel(f"The substation should have a compatible voltage level ({vnom} kV)")
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)

        # Add a status label that will be updated
        self.status_label = QLabel("Waiting for selection...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Add a cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)

        self.setLayout(layout)
        self.resize(300, 200)

    def update_status(self, text):
        self.status_label.setText(text)


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

        super().__init__(
            gui=gui,
            circuit=circuit,
            diagram=MapDiagram(name=name,
                               tile_source=tile_src.tile_set_name,
                               start_level=start_level,
                               longitude=longitude,
                               latitude=latitude) if diagram is None else diagram,
            library_model=MapLibraryModel(),
            time_index=None,
            call_delete_db_element_func=call_delete_db_element_func
        )

        # declare the map
        self.map = MapWidget(parent=self,
                             tile_src=tile_src,
                             start_level=start_level,
                             editor=self,
                             zoom_callback=self.zoom_callback,
                             position_callback=self.position_callback)

        # Any representation on the map must be done after this Goto Function
        self.map.go_to_level_and_position(level=6, longitude=longitude, latitude=latitude)

        # function pointer to call for a new substation diagram
        self.call_new_substation_diagram_func = call_new_substation_diagram_func

        # pool of runnable tasks that work best done asynch with a runnable
        self.thread_pool = QThreadPool()
        self.wheel_move_task: QRunnable | None = None

        # draw & center
        self.draw()
        self.center()

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
        self.diagram.delete_device(device=device)
        graphic_object: ALL_MAP_GRAPHICS = self.graphics_manager.delete_device(device=device)

        if graphic_object is not None:
            self.remove_from_scene(graphic_object)

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

    def get_selected(self) -> List[Tuple[ALL_DEV_TYPES, ALL_MAP_GRAPHICS]]:
        """
        Get selection
        :return: List of EditableDevice, QGraphicsItem
        """
        return [(elm.api_object, elm) for elm in self.map.diagram_scene.selectedItems()]

    
    def get_selected_line_segments_tup(self) -> List[Tuple[Line, (MapAcLine, 
                                                                  MapDcLine,
                                                                  MapHvdcLine,
                                                                  MapFluidPathLine)]]:
            """
            Get only selected line segments from the scene
            
            :return: List of (Line, (MapAcLine, MapDcLine, MapHvdcLine, MapFluidPathLine)) tuples
            """
            selected_line_segments = []
            for item in self.map.diagram_scene.selectedItems():
                if (hasattr(item, 'api_object') and hasattr(item, 'container')
                    and isinstance(item.container, 
                                (MapAcLine, 
                                MapDcLine, 
                                MapHvdcLine, 
                                MapFluidPathLine))):
                    selected_line_segments.append((item.api_object, item.container))
            return selected_line_segments

    def get_selected_substations_tup(self) -> List[Tuple[Substation, SubstationGraphicItem]]:
            """
            Get only selected substations from the scene
            
            :return: List of (Substation, SubstationGraphicItem) tuples
            """
            selected_substations = []
            for item in self.map.diagram_scene.selectedItems():
                if hasattr(item, 'api_object') and isinstance(item, SubstationGraphicItem):
                    selected_substations.append((item.api_object, item))
            return selected_substations


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

    def remove_element(self,
                       device: ALL_DEV_TYPES,
                       graphic_object: ALL_MAP_GRAPHICS = None,
                       delete_from_db: bool = False) -> None:
        """
        Remove device from the diagram and the database
        :param device: EditableDevice
        :param graphic_object: optionally provide the graphics object associated
        :param delete_from_db: Delete the element also from the database?
        """

        if graphic_object is not None:
            if isinstance(graphic_object, SubstationGraphicItem):
                self.remove_substation(substation=graphic_object,
                                       delete_from_db=delete_from_db)

            elif isinstance(graphic_object, (MapAcLine, MapDcLine, MapHvdcLine, MapFluidPathLine)):
                self.remove_branch_graphic(line=graphic_object, delete_from_db=delete_from_db)

        self.delete_diagram_element(device=device, propagate=delete_from_db)

        self.object_editor_table.setModel(None)

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

    def get_selected_substations(self) -> List[SubstationGraphicItem]:
        """
        Get the selected substations graphics
        :return: List[SubstationGraphicItem]
        """
        return [s for s in self.map.view.selected_items() if isinstance(s, SubstationGraphicItem)]

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
                if accept_line_connection(V1=bus1.Vnom, V2=bus2.Vnom, branch_connection_voltage_tolerance=0.1):
                    new_line = Line(bus_from=bus1, bus_to=bus2)
                    self.add_api_line(new_line)
                    self.circuit.add_line(new_line)
                else:
                    error_msg(text="The nominal voltage of the two connecting substations is not the same :(",
                              title="Create new line")
                    return None
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

    def remove_substation(self,
                          substation: SubstationGraphicItem,
                          delete_from_db: bool = False,
                          delete_connections: bool = True):
        """
        Remove a substation from the schematic and optionally from the database
        
        :param substation: Substation graphic item to remove
        :param delete_from_db: Delete from the database too?
        :param delete_connections: True always except for when merging substations
        :return: None
        """
        # Store the API object before deleting the graphic
        api_object = substation.api_object

        # Get all buses connected to this substation
        substation_buses = [bus for bus in self.circuit.buses if bus.substation == api_object]
        
        # Get all voltage levels associated with this substation
        voltage_levels = [vl for vl in self.circuit.voltage_levels if vl.substation == api_object]

        # voltage_levels = api_object.voltage_levels

        devs = []
        # find associated Branches in reverse order
        for obj in substation_buses:
            for branch_list in self.circuit.get_branch_lists():
                for i in range(len(branch_list) - 1, -1, -1):
                    if branch_list[i].bus_from == obj:
                        devs.append(branch_list[i])
                    elif branch_list[i].bus_to == obj:
                        devs.append(branch_list[i])

        # find the associated injection devices
            for inj_list in self.circuit.get_injection_devices_lists():
                for i in range(len(inj_list) - 1, -1, -1):
                    if inj_list[i].bus == obj:
                        devs.append(inj_list[i])

        # Show all devices that will be disconnected
        title = f"Devices to be {'deleted' if delete_connections else 'disconnected'} from {api_object.name}"
        self.show_devices_to_disconnect_dialog(
            devs,
            substation_buses, 
            voltage_levels, 
            title
        )

        # Remove from graphics manager and scene
        sub = self.graphics_manager.delete_device(api_object)
        self.map.diagram_scene.removeItem(sub)

        # Find and delete all lines connected to the substation
        for tpe in [DeviceType.LineDevice, DeviceType.DCLineDevice, DeviceType.HVDCLineDevice]:
            for elm in self.graphics_manager.get_device_type_list(tpe):
                if elm.api_object.get_substation_from() == api_object or elm.api_object.get_substation_to() == api_object:
                    self.graphics_manager.delete_device(elm.api_object)
                    for segment in elm.segments_list:
                        self.map.diagram_scene.removeItem(segment)

        # Finally, delete from the database if requested
        if delete_from_db:
            # Delete buses associated with this substation
            for bus in substation_buses:
                self.circuit.delete_bus(bus, delete_associated=True)
                
            # Delete voltage levels associated with this substation
            for vl in voltage_levels:
                self.circuit.delete_voltage_level(vl)
                
            # Delete the substation itself
            self.circuit.delete_substation(obj=api_object)

    def show_devices_to_disconnect_dialog(self, 
                                         devices: List[ALL_DEV_TYPES],
                                         buses: List[Bus],
                                         voltage_levels: List[VoltageLevel],
                                         dialog_title: str):
        """
        Show a dialog with the list of all devices that will be disconnected
        
        :param devices: List of devices to be disconnected
        :param buses: List of buses associated with the substation
        :param voltage_levels: List of voltage levels associated with the substation
        :param dialog_title: Title for the dialog
        """
        from GridCal.Gui.general_dialogues import ElementsDialogue
        from GridCalEngine.Devices.Parents.editable_device import GCProp
        
        # Combine all devices
        all_devices = devices + buses + voltage_levels
        
        if not all_devices:
            info_msg('No devices to disconnect', dialog_title)
            return
            
        # Create custom properties for name, type, and ID tag
        name_prop = GCProp(prop_name='name', tpe=str, units='', definition='Device name', 
                           display=True, editable=False)
        
        type_prop = GCProp(prop_name='device_type', tpe=DeviceType, units='', definition='Device type', 
                           display=True, editable=False)
        
        idtag_prop = GCProp(prop_name='idtag', tpe=str, units='', definition='ID tag', 
                           display=True, editable=False)
        
        custom_props = [name_prop, type_prop, idtag_prop]
        
        # Create and show the dialog
        dialog = ElementsDialogue(name=dialog_title, elements=all_devices)
        
        # Replace the model with our custom one that only shows name, type, and idtag
        model = ObjectsModel(objects=all_devices,
                            time_index=None,
                            property_list=custom_props,
                            parent=dialog.objects_table,
                            editable=False)
        
        dialog.objects_table.setModel(model)
        
        # Make the dialog modal so the user must acknowledge it before continuing
        dialog.setModal(True)
        dialog.exec()

    def remove_branch_graphic(self, line: MAP_BRANCH_GRAPHIC_TYPES | MapLineContainer, delete_from_db: bool = False):
        """
        Removes line from diagram and scene
        :param line: Line to remove
        :param delete_from_db:
        """
        lin = self.graphics_manager.delete_device(line.api_object)

        if lin is not None:

            if delete_from_db:
                self.circuit.delete_branch(obj=line.api_object)

            for seg in lin.segments_list:
                self.map.diagram_scene.removeItem(seg)

    def delete_Selected_from_widget(self, delete_from_db: bool) -> None:
        """
        Delete the selected items from the diagram
        """
        # get the selected objects
        selected = self.get_selected()

        if len(selected) > 0:

            dlg = CheckListDialogue(
                objects_list=[f"{elm.device_type.value}: {elm.name}" for elm, graphic_obj in selected],
                title="Delete Selected"
            )

            dlg.setModal(True)
            dlg.exec()

            if dlg.is_accepted:

                for i in dlg.selected_indices:
                    elm, graphic_obj = selected[i]
                    self.remove_element(device=elm,
                                        graphic_object=graphic_obj,
                                        delete_from_db=delete_from_db)
                    # self.remove_from_scene(graphic_obj)

        else:
            info_msg('Choose some elements from the schematic', 'Delete')

    def add_api_line(self, api_object: Line) -> MapAcLine:
        """
        Adds a line with the nodes and segments
        :param api_object: Any branch type from the database
        :return: MapTemplateLine
        """
        line_container = MapAcLine(editor=self, api_object=api_object)

        self.graphics_manager.add_device(elm=api_object, graphic=line_container)

        # create the nodes
        line_container.draw_all()

        # there is nt need to add to the scene
        return line_container

    def add_api_dc_line(self, api_object: DcLine) -> MapDcLine:
        """
        Adds a line with the nodes and segments
        :param api_object: Any branch type from the database
        :return: MapTemplateLine
        """
        line_container = MapDcLine(editor=self, api_object=api_object)

        self.graphics_manager.add_device(elm=api_object, graphic=line_container)

        # create the nodes
        line_container.draw_all()

        # there is not need to add to the scene

        return line_container

    def add_api_hvdc_line(self, api_object: HvdcLine) -> MapHvdcLine:
        """
        Adds a line with the nodes and segments
        :param api_object: Any branch type from the database
        :return: MapTemplateLine
        """
        line_container = MapHvdcLine(editor=self, api_object=api_object)

        self.graphics_manager.add_device(elm=api_object, graphic=line_container)

        # create the nodes
        line_container.draw_all()

        # there is not need to add to the scene

        return line_container

    def add_api_fluid_path(self, api_object: FluidPath) -> MapFluidPathLine:
        """
        Adds a line with the nodes and segments
        :param api_object: Any branch type from the database
        :return: MapTemplateLine
        """
        line_container = MapFluidPathLine(editor=self, api_object=api_object)

        self.graphics_manager.add_device(elm=api_object, graphic=line_container)

        # create the nodes
        line_container.draw_all()

        # there is not need to add to the scene

        return line_container

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
                                               lon=lon,
                                               size=self.diagram.min_bus_width)

        self.graphics_manager.add_device(elm=api_object,
                                         graphic=graphic_object)

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
                    self.add_api_line(api_object=api_object)  # no need to add to the scene

            elif category == DeviceType.DCLineDevice.value:
                for idtag, location in points_group.locations.items():
                    api_object: DcLine = location.api_object
                    self.add_api_dc_line(api_object=api_object)  # no need to add to the scene

            elif category == DeviceType.HVDCLineDevice.value:
                for idtag, location in points_group.locations.items():
                    api_object: HvdcLine = location.api_object
                    self.add_api_hvdc_line(api_object=api_object)  # no need to add to the scene

            elif category == DeviceType.FluidNodeDevice.value:
                pass  # TODO: implementar

            elif category == DeviceType.FluidPathDevice.value:
                for idtag, location in points_group.locations.items():
                    api_object: FluidPath = location.api_object
                    self.add_api_fluid_path(api_object=api_object)  # no need to add to the scene

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
                self.add_to_scene(graphic_object=line_container)
                # for segment in line_container.segments_list:
                #     self.add_to_scene(graphic_object=segment)

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
            se_object = Substation(name=dlg.get_name(),
                                   code=dlg.get_code(),
                                   latitude=lat,
                                   longitude=lon)

            self.circuit.add_substation(obj=se_object)
            substation_graphics = self.add_api_substation(api_object=se_object, lat=lat, lon=lon)

            for vl_template in dlg.get_voltage_levels():
                # substation_graphics.add_voltage_level()
                vl = VoltageLevel(name=f"{se_object.name} @{vl_template.voltage} kV VL",
                                  Vnom=vl_template.voltage,
                                  substation=se_object)
                self.circuit.add_voltage_level(vl)

                bus = Bus(name=f"{se_object.name} @{vl_template.voltage} kV bus",
                          Vnom=vl_template.voltage,
                          substation=se_object,
                          voltage_level=vl)
                self.circuit.add_bus(obj=bus)

                # add the vl graphics
                self.add_api_voltage_level(substation_graphics=substation_graphics, api_object=vl)

            # sort voltage levels
            substation_graphics.sort_voltage_levels()

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

    def update_device_sizes(self, asynchronously: bool = True) -> None:
        """
        Caller to the asynchronous device update sizes
        :return:
        """
        # if asynchronously:
        #     try:
        #         loop = asyncio.get_event_loop()
        #         self.wheel_move_task = loop.create_task(self.__update_device_sizes())
        #     except RuntimeError:
        #         pass
        # else:
        #     # do it now
        #     asyncio.run(self.__update_device_sizes())

        self.__update_device_sizes()

    def __update_device_sizes(self) -> None:
        """
        Update the devices' sizes
        :return:
        """
        print('Updating device sizes!')
        self.map.diagram_scene.blockSignals(True)
        self.map.diagram_scene.invalidate(self.map.diagram_scene.sceneRect())

        branch_width = self.diagram.min_branch_width  # self.get_branch_width()
        arrow_width = self.diagram.arrow_size  # self.get_arrow_scale()
        se_width = self.diagram.min_bus_width  # self.get_substation_scale()

        # rescale lines
        for dev_tpe in [DeviceType.LineDevice,
                        DeviceType.DCLineDevice,
                        DeviceType.HVDCLineDevice,
                        DeviceType.FluidPathDevice]:
            graphics_dict = self.graphics_manager.get_device_type_dict(device_type=dev_tpe)

            #  TODO: this is super-slow
            for key, elm_graphics in graphics_dict.items():
                elm_graphics.set_width_scale(width=branch_width, arrow_width=arrow_width)

        # rescale substations (this is super-fast)
        data: Dict[str, SubstationGraphicItem] = self.graphics_manager.get_device_type_dict(DeviceType.SubstationDevice)
        for se_key, elm_graphics in data.items():
            elm_graphics.set_api_object_color()
            elm_graphics.set_size(r=se_width)

        self.map.diagram_scene.blockSignals(False)
        self.map.diagram_scene.update(self.map.diagram_scene.sceneRect())

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

    def center(self):
        """
        Center the diagram
        """
        lat = 0.0
        lon = 0.0
        n = 0
        for graphic_obj in self.graphics_manager.get_device_type_list(DeviceType.SubstationDevice):
            lat += graphic_obj.lat
            lon += graphic_obj.lon
            n += 1

        if n > 0:
            lat /= n
            lon /= n
            self.map.pan_position(latitude=lat, longitude=lon)

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

        # voltage_cmap = viz.get_voltage_color_map()
        loading_cmap = viz.get_loading_color_map()

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

        arrow_size = self.diagram.arrow_size  # self.get_arrow_scale()

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

                    if cmap == palettes.Colormaps.Green2Red:
                        b, g, r = palettes.green_to_red_bgr(lnorm[i])
                        a = 255

                    elif cmap == palettes.Colormaps.Heatmap:
                        b, g, r = palettes.heatmap_palette_bgr(lnorm[i])
                        a = 255

                    elif cmap == palettes.Colormaps.TSO:
                        b, g, r = palettes.tso_line_palette_bgr(branch.get_max_bus_nominal_voltage(), lnorm[i])
                        a = 255

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
                    graphic_object.set_width_scale(width=weight, arrow_width=arrow_size)

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
                        graphic_object.set_arrows_with_hvdc_power(Pf=float(hvdc_Pf[i]), Pt=float(hvdc_Pt[i]))
                    else:
                        graphic_object.set_arrows_with_hvdc_power(Pf=float(hvdc_Pf[i]), Pt=-hvdc_Pf[i])

                    graphic_object.set_colour(color=color, style=style, tool_tip=tooltip)
                    graphic_object.set_width_scale(width=weight, arrow_width=arrow_size)

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

    def split_line_to_substation(self):
        """
        Split a selected line and connect it to a selected substation.
        This creates two new lines: one from the original "from" bus to the selected substation,
        and another from the selected substation to the original "to" bus.
        The original line is removed.
        """
        # Get selected items
        # selected_items = self.get_selected()

        # Find the line and substation in the selection
        selected_lines = self.get_selected_line_segments_tup()
        selected_substations = self.get_selected_substations_tup()

        if len(selected_lines) != 1 or len(selected_substations) != 1:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Please select exactly one line and one substation.")
            msg.setWindowTitle("Selection Error")
            msg.exec()
            return

        # Get the API objects
        line_api, line_graphic = selected_lines[0]
        substation_api, substation_graphic = selected_substations[0]

        # Get the original line container to access its properties
        # original_line_container = line_graphic.container
        original_line_container = line_graphic

        # Get the original buses
        bus_from = line_api.bus_from
        bus_to = line_api.bus_to

        # Find a suitable bus in the selected substation
        # First, check if the substation already has a voltage level with the same voltage as the line
        vnom = line_api.get_max_bus_nominal_voltage()
        suitable_bus = None

        # Look for a bus in the substation with matching voltage
        for bus in self.circuit.get_substation_buses(substation=substation_api):
            if abs(bus.Vnom - vnom) < 0.01:  # Small tolerance for voltage comparison
                suitable_bus = bus
                break

        # If no suitable bus found, create a new voltage level and bus
        if suitable_bus is None:
            # Find or create a voltage level with the appropriate voltage
            voltage_level = None

            for vl in substation_api.voltage_levels:
                if abs(vl.nominal_voltage - vnom) < 0.01:
                    voltage_level = vl
                    break

            if voltage_level is None:
                # Create a new voltage level
                voltage_level_name = f"{substation_api.name} {vnom} kV"
                voltage_level = VoltageLevel(name=voltage_level_name,
                                             substation=substation_api,
                                             Vnom=vnom)
                self.circuit.add_voltage_level(voltage_level)

                # Add the voltage level graphic
                vl_graphic = self.add_api_voltage_level(
                    substation_graphics=substation_graphic,
                    api_object=voltage_level
                )

            # Create a new bus in the substation
            new_bus_name = f"{substation_api.name} {vnom} kV Bus"
            suitable_bus = Bus(name=new_bus_name,
                               Vnom=vnom,
                               vmin=bus_from.Vmin,  # Use the same limits as the original bus
                               vmax=bus_from.Vmax,
                               voltage_level=voltage_level,
                               substation=substation_api,
                               area=bus_from.area,
                               zone=bus_from.zone,
                               country=bus_from.country)

            # Add the new bus to the circuit
            self.circuit.add_bus(suitable_bus)

        # Step 1: Collect all waypoints of the original line
        waypoints = []

        # Add the "from" substation
        substation_from_graphics = self.graphics_manager.query(elm=line_api.get_substation_from())
        if substation_from_graphics is not None:
            waypoints.append((substation_from_graphics.lat, substation_from_graphics.lon))

        # Add all intermediate points
        for node in original_line_container.nodes_list:
            waypoints.append((node.lat, node.lon))

        # Add the "to" substation
        substation_to_graphics = self.graphics_manager.query(elm=line_api.get_substation_to())
        if substation_to_graphics is not None:
            waypoints.append((substation_to_graphics.lat, substation_to_graphics.lon))

        # Step 2: Find the closest segment to the selected substation
        substation_lat = substation_api.latitude
        substation_lon = substation_api.longitude

        min_distance = float('inf')
        closest_segment_idx = 0
        closest_point = (0, 0)

        for i in range(len(waypoints) - 1):
            lat1, lon1 = waypoints[i]
            lat2, lon2 = waypoints[i + 1]

            # Find the closest point on this segment to the substation
            point, distance = self._closest_point_on_segment(
                lat1, lon1, lat2, lon2, substation_lat, substation_lon
            )

            if distance < min_distance:
                min_distance = distance
                closest_segment_idx = i
                closest_point = point

        # Step 3: Calculate the lengths of the two new segments
        length1 = 0.0
        length2 = 0.0

        # Calculate length of first segment (from original start to insertion point)
        for i in range(closest_segment_idx):
            lat1, lon1 = waypoints[i]
            lat2, lon2 = waypoints[i + 1]
            length1 += haversine_distance(lat1, lon1, lat2, lon2)

        # Add distance from last waypoint to insertion point
        lat1, lon1 = waypoints[closest_segment_idx]
        lat2, lon2 = closest_point
        length1 += haversine_distance(lat1, lon1, lat2, lon2)

        # Calculate length of second segment (from insertion point to original end)
        # First, add distance from insertion point to next waypoint
        lat1, lon1 = closest_point
        lat2, lon2 = waypoints[closest_segment_idx + 1]
        length2 += haversine_distance(lat1, lon1, lat2, lon2)

        # Add remaining segments
        for i in range(closest_segment_idx + 1, len(waypoints) - 1):
            lat1, lon1 = waypoints[i]
            lat2, lon2 = waypoints[i + 1]
            length2 += haversine_distance(lat1, lon1, lat2, lon2)

        # Step 4: Calculate the proportion of each segment
        total_length = length1 + length2
        ratio1 = length1 / total_length
        ratio2 = length2 / total_length

        # Step 5: Create the new lines with the correct properties from the start
        # Line 1: from original bus_from to new_bus
        line1_name = f"{line_api.name}_1"

        # Handle the code property - it might be a list of strings
        if hasattr(line_api, 'code') and line_api.code is not None:
            if isinstance(line_api.code, list):
                line1_code = [f"{code}_1" for code in line_api.code]
            else:
                line1_code = f"{line_api.code}_1"
        else:
            line1_code = ""

        line1 = Line(name=line1_name,
                     bus_from=bus_from,
                     bus_to=suitable_bus,
                     code=line1_code,
                     r=line_api.R * ratio1,  # Set impedance proportional to length
                     x=line_api.X * ratio1,
                     b=line_api.B * ratio1,
                     r0=line_api.R0 * ratio1,
                     x0=line_api.X0 * ratio1,
                     b0=line_api.B0 * ratio1,
                     r2=line_api.R2 * ratio1,
                     x2=line_api.X2 * ratio1,
                     b2=line_api.B2 * ratio1,
                     length=length1,  # Set the actual calculated length
                     rate=line_api.rate,
                     contingency_factor=line_api.contingency_factor,
                     protection_rating_factor=line_api.protection_rating_factor)

        # Copy other properties from the original line
        if hasattr(line_api, 'color'):
            line1.color = line_api.color
        if hasattr(line_api, 'tags') and line_api.tags:
            line1.tags = line_api.tags.copy() if isinstance(line_api.tags, list) else line_api.tags
        if hasattr(line_api, 'active'):
            line1.active = line_api.active

        # Preserve waypoints for line 1 (from start to insertion point)
        # Add all waypoints from the original line up to the closest segment
        for i in range(closest_segment_idx):
            if i < len(original_line_container.nodes_list):
                node = original_line_container.nodes_list[i]
                line1.locations.add_location(lat=node.lat, long=node.lon, alt=0.0)

        # Add the insertion point (closest point to the substation) as the last waypoint
        closest_lat, closest_lon = closest_point

        # Check if the closest point is very close to an existing waypoint
        # If so, we'll use that waypoint instead of adding a new one
        is_duplicate = False
        if closest_segment_idx < len(original_line_container.nodes_list):
            node = original_line_container.nodes_list[closest_segment_idx]
            if haversine_distance(closest_lat, closest_lon, node.lat, node.lon) < 0.01:  # 10 meters threshold
                is_duplicate = True
                closest_lat, closest_lon = node.lat, node.lon

        # Only add the insertion point if it's not a duplicate
        bearing_to_substation = 0.0  # initialize to zero
        perpendicular_bearing = 0.0  # initialize to zero
        R = 6371.0  # Earth's radius in km
        offset_distance = 0.0  # initialize to zero
        if not is_duplicate:
            # Add an offset (5% of segment length) to the waypoint for line 1 to prevent visual overlap
            # Calculate a bearing from the closest point to the substation
            bearing_to_substation = math.atan2(
                math.sin(math.radians(substation_lon) - math.radians(closest_lon)) * math.cos(
                    math.radians(substation_lat)),
                math.cos(math.radians(closest_lat)) * math.sin(math.radians(substation_lat)) -
                math.sin(math.radians(closest_lat)) * math.cos(math.radians(substation_lat)) *
                math.cos(math.radians(substation_lon) - math.radians(closest_lon))
            )

            # Calculate a perpendicular bearing (90 degrees offset)
            perpendicular_bearing = bearing_to_substation + math.pi / 2

            # Calculate the segment length
            segment_length = haversine_distance(
                waypoints[closest_segment_idx][0],
                waypoints[closest_segment_idx][1],
                waypoints[closest_segment_idx + 1][0],
                waypoints[closest_segment_idx + 1][1]
            )

            # Distance to offset (5% of segment length)
            offset_distance = segment_length * 0.05

            # Calculate the offset point for line 1 (perpendicular to the bearing to substation)
            offset_lat1 = math.asin(
                math.sin(math.radians(closest_lat)) * math.cos(offset_distance / R) +
                math.cos(math.radians(closest_lat)) * math.sin(offset_distance / R) * math.cos(perpendicular_bearing)
            )
            offset_lon1 = math.radians(closest_lon) + math.atan2(
                math.sin(perpendicular_bearing) * math.sin(offset_distance / R) * math.cos(math.radians(closest_lat)),
                math.cos(offset_distance / R) - math.sin(math.radians(closest_lat)) * math.sin(offset_lat1)
            )

            offset_lat1 = math.degrees(offset_lat1)
            offset_lon1 = math.degrees(offset_lon1)

            # Add the offset point to line 1
            line1.locations.add_location(lat=offset_lat1, long=offset_lon1, alt=0.0)

        # Line 2: from new_bus to original bus_to
        line2_name = f"{line_api.name}_2"

        # Handle the code property for line 2
        if hasattr(line_api, 'code') and line_api.code is not None:
            if isinstance(line_api.code, list):
                line2_code = [f"{code}_2" for code in line_api.code]
            else:
                line2_code = f"{line_api.code}_2"
        else:
            line2_code = ""

        line2 = Line(name=line2_name,
                     bus_from=suitable_bus,
                     bus_to=bus_to,
                     code=line2_code,
                     r=line_api.R * ratio2,  # Set impedance proportional to length
                     x=line_api.X * ratio2,
                     b=line_api.B * ratio2,
                     r0=line_api.R0 * ratio2,
                     x0=line_api.X0 * ratio2,
                     b0=line_api.B0 * ratio2,
                     r2=line_api.R2 * ratio2,
                     x2=line_api.X2 * ratio2,
                     b2=line_api.B2 * ratio2,
                     length=length2,  # Set the actual calculated length
                     rate=line_api.rate,
                     contingency_factor=line_api.contingency_factor,
                     protection_rating_factor=line_api.protection_rating_factor)

        # Copy other properties from the original line
        if hasattr(line_api, 'color'):
            line2.color = line_api.color
        if hasattr(line_api, 'tags') and line_api.tags:
            line2.tags = line_api.tags.copy() if isinstance(line_api.tags, list) else line_api.tags
        if hasattr(line_api, 'active'):
            line2.active = line_api.active

        # Preserve waypoints for line 2 (from insertion point to end)
        # Add the insertion point as the first waypoint with a small offset
        if not is_duplicate:
            # Calculate the offset point for line 2 (opposite direction from line 1)
            opposite_bearing = perpendicular_bearing + math.pi  # 180 degrees from the first offset

            offset_lat2 = math.asin( 
                math.sin(math.radians(closest_lat)) * math.cos(offset_distance / R) +
                math.cos(math.radians(closest_lat)) * math.sin(offset_distance / R) * math.cos(opposite_bearing)
            )
            offset_lon2 = math.radians(closest_lon) + math.atan2(
                math.sin(opposite_bearing) * math.sin(offset_distance / R) * math.cos(math.radians(closest_lat)),
                math.cos(offset_distance / R) - math.sin(math.radians(closest_lat)) * math.sin(offset_lat2)
            )

            offset_lat2 = math.degrees(offset_lat2)
            offset_lon2 = math.degrees(offset_lon2)

            # Add the offset point to line 2
            line2.locations.add_location(lat=offset_lat2, long=offset_lon2, alt=0.0)

        # Add all remaining waypoints from the original line
        for i in range(closest_segment_idx + 1, len(original_line_container.nodes_list)):
            node = original_line_container.nodes_list[i]
            line2.locations.add_location(lat=node.lat, long=node.lon, alt=0.0)

        # Add the new lines to the circuit
        self.circuit.add_line(line1)
        self.circuit.add_line(line2)

        # Add the new lines to the map
        line1_graphic = self.add_api_line(line1)
        line2_graphic = self.add_api_line(line2)

        # Get the branch width and arrow size from the general diagram settings
        branch_width = self.diagram.min_branch_width
        arrow_size = self.diagram.arrow_size

        # If we have segments in the original line, use their width and arrow size
        if original_line_container and original_line_container.segments_list:
            if len(original_line_container.segments_list) > 0:
                segment = original_line_container.segments_list[0]
                branch_width = segment.get_width()
                arrow_size = segment.get_arrow_size()

        # Apply the same width and arrow size to the new lines
        line1_graphic.set_width_scale(width=branch_width, arrow_width=arrow_size)
        line2_graphic.set_width_scale(width=branch_width, arrow_width=arrow_size)

        # Remove the original line
        self.remove_branch_graphic(line=line_graphic, delete_from_db=True)

        # Notify the user
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"Line {line_api.name} has been split and connected to substation {substation_api.name}.")
        msg.setInformativeText(
            f"Line 1 ({line1.name}): {length1:.2f} km\nLine 2 ({line2.name}): {length2:.2f} km\n\nImpedance parameters have been set proportionally based on the actual lengths.")
        msg.setWindowTitle("Operation Successful")
        msg.exec()

    def _closest_point_on_segment(self, lat1, lon1, lat2, lon2, lat3, lon3):
        """
        Find the closest point on a line segment to a given point using geographic coordinates.
        
        :param lat1, lon1: Coordinates of the first endpoint of the segment
        :param lat2, lon2: Coordinates of the second endpoint of the segment
        :param lat3, lon3: Coordinates of the point to find the closest point to
        :return: (closest_lat, closest_lon), distance_in_km
        """
        # For very short segments, just return the midpoint
        if haversine_distance(lat1, lon1, lat2, lon2) < 0.001:  # Less than 1 meter
            closest_lat = (lat1 + lat2) / 2
            closest_lon = (lon1 + lon2) / 2
            distance = haversine_distance(closest_lat, closest_lon, lat3, lon3)
            return (closest_lat, closest_lon), distance

        # Calculate distances to the endpoints
        dist_to_p1 = haversine_distance(lat1, lon1, lat3, lon3)
        dist_to_p2 = haversine_distance(lat2, lon2, lat3, lon3)

        # Convert to radians for spherical calculations
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        lat3_rad = math.radians(lat3)
        lon3_rad = math.radians(lon3)

        # Earth's radius in km
        R = 6371.0

        # Calculate the bearing from point 1 to point 2
        y = math.sin(lon2_rad - lon1_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(
            lon2_rad - lon1_rad)
        bearing_1_to_2 = math.atan2(y, x)

        # Calculate the bearing from point 1 to point 3
        y = math.sin(lon3_rad - lon1_rad) * math.cos(lat3_rad)
        x = math.cos(lat1_rad) * math.sin(lat3_rad) - math.sin(lat1_rad) * math.cos(lat3_rad) * math.cos(
            lon3_rad - lon1_rad)
        bearing_1_to_3 = math.atan2(y, x)

        # Calculate the angular distance from point 1 to point 3
        angular_dist_1_to_3 = math.acos(
            math.sin(lat1_rad) * math.sin(lat3_rad) +
            math.cos(lat1_rad) * math.cos(lat3_rad) * math.cos(lon3_rad - lon1_rad)
        )

        # Calculate the cross-track distance (perpendicular distance to the great circle path)
        cross_track_dist = math.asin(
            math.sin(angular_dist_1_to_3) * math.sin(bearing_1_to_3 - bearing_1_to_2)
        )

        # Calculate the along-track distance (distance from point 1 to the closest point)
        along_track_dist = math.acos(
            math.cos(angular_dist_1_to_3) / math.cos(cross_track_dist)
        )

        # Calculate the total distance of the segment
        segment_dist_rad = math.acos(
            math.sin(lat1_rad) * math.sin(lat2_rad) +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.cos(lon2_rad - lon1_rad)
        )

        # Check if the closest point is on the segment
        if along_track_dist > segment_dist_rad:
            # Closest point is beyond point 2
            return (lat2, lon2), dist_to_p2
        elif along_track_dist < 0:
            # Closest point is before point 1
            return (lat1, lon1), dist_to_p1
        else:
            # Closest point is on the segment
            # Calculate the position of the closest point
            closest_lat_rad = math.asin(
                math.sin(lat1_rad) * math.cos(along_track_dist) +
                math.cos(lat1_rad) * math.sin(along_track_dist) * math.cos(bearing_1_to_2)
            )

            closest_lon_rad = lon1_rad + math.atan2(
                math.sin(bearing_1_to_2) * math.sin(along_track_dist) * math.cos(lat1_rad),
                math.cos(along_track_dist) - math.sin(lat1_rad) * math.sin(closest_lat_rad)
            )

            closest_lat = math.degrees(closest_lat_rad)
            closest_lon = math.degrees(closest_lon_rad)

            # Calculate the distance from point 3 to the closest point
            distance = R * math.acos(
                math.sin(lat3_rad) * math.sin(closest_lat_rad) +
                math.cos(lat3_rad) * math.cos(closest_lat_rad) * math.cos(closest_lon_rad - lon3_rad)
            )

            return (closest_lat, closest_lon), distance

    def create_t_joint_to_substation(self):
        """
        Create a T-joint connection between a line and a selected substation using a selected waypoint.
        This replaces the waypoint with a new substation, splits the original line into two segments,
        and creates a new line connecting the selected substation to the new substation at the waypoint.
        
        The user only needs to select a waypoint and a substation. The line is automatically determined
        from the waypoint.
        """
        # Get selected items
        selected_items = self.get_selected()

        # Find the substation and waypoint in the selection
        selected_substation = None
        selected_waypoint = None

        for api_obj, graphic_obj in selected_items:
            if isinstance(api_obj, Substation) and isinstance(graphic_obj, SubstationGraphicItem):
                selected_substation = (api_obj, graphic_obj)
            elif isinstance(graphic_obj, LineLocationGraphicItem):
                selected_waypoint = graphic_obj

        # Check if we have a substation and a waypoint selected
        if selected_substation is None or selected_waypoint is None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Please select one substation and one waypoint.")
            msg.setWindowTitle("Selection Error")
            msg.exec()
            return

        # Get the line container from the waypoint
        original_line_container = selected_waypoint.line_container

        if original_line_container is None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Could not determine which line the waypoint belongs to.")
            msg.setWindowTitle("Selection Error")
            msg.exec()
            return

        # Get the line API object
        line_api = original_line_container.api_object

        if not isinstance(line_api, Line):
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("The waypoint must belong to a line.")
            msg.setWindowTitle("Selection Error")
            msg.exec()
            return

        # Get the API objects
        substation_api, substation_graphic = selected_substation

        # Get the waypoint coordinates
        waypoint_lat = selected_waypoint.lat
        waypoint_lon = selected_waypoint.lon

        # Find the index of the selected waypoint in the nodes list
        waypoint_idx = -1
        for i, node in enumerate(original_line_container.nodes_list):
            if node == selected_waypoint:
                waypoint_idx = i
                break

        if waypoint_idx == -1:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Selected waypoint not found in the line's waypoints.")
            msg.setWindowTitle("Selection Error")
            msg.exec()
            return

        # Step 1: Create a new substation at the waypoint location
        new_substation_name = f"{line_api.name}_Junction"

        # Create the new substation
        new_substation = Substation(name=new_substation_name,
                                    code=f"{line_api.code}_Junction" if hasattr(line_api,
                                                                                'code') and line_api.code else "",
                                    latitude=waypoint_lat,
                                    longitude=waypoint_lon)

        self.circuit.add_substation(obj=new_substation)
        new_substation_graphic = self.add_api_substation(api_object=new_substation, lat=waypoint_lat, lon=waypoint_lon)

        # Step 2: Find a suitable bus in the selected substation and create a matching one in the new substation
        vnom = line_api.get_max_bus_nominal_voltage()
        suitable_bus_in_selected = None

        # Look for a bus in the selected substation with matching voltage
        for bus in self.circuit.get_substation_buses(substation=substation_api):
            if abs(bus.Vnom - vnom) < 0.01:  # Small tolerance for voltage comparison
                suitable_bus_in_selected = bus
                break

        # If no suitable bus found, create a new voltage level and bus in the selected substation
        if suitable_bus_in_selected is None:
            # Find or create a voltage level with the appropriate voltage in the selected substation
            voltage_level_in_selected = None
            for vl in substation_api.voltage_levels:
                if abs(vl.nominal_voltage - vnom) < 0.01:
                    voltage_level_in_selected = vl
                    break

            if voltage_level_in_selected is None:
                # Create a new voltage level
                voltage_level_name = f"{substation_api.name} {vnom} kV"
                voltage_level_in_selected = VoltageLevel(name=voltage_level_name,
                                                         substation=substation_api,
                                                         Vnom=vnom)
                self.circuit.add_voltage_level(voltage_level_in_selected)

                # Add the voltage level graphic
                vl_graphic = self.add_api_voltage_level(
                    substation_graphics=substation_graphic,
                    api_object=voltage_level_in_selected
                )

            # Create a new bus in the selected substation
            bus_name = f"{substation_api.name} {vnom} kV Bus"
            suitable_bus_in_selected = Bus(name=bus_name,
                                           Vnom=vnom,
                                           vmin=0.9,
                                           vmax=1.1,
                                           voltage_level=voltage_level_in_selected,
                                           substation=substation_api)

            # Add the new bus to the circuit
            self.circuit.add_bus(suitable_bus_in_selected)

        # Create a voltage level and bus in the new substation
        voltage_level_in_new = VoltageLevel(name=f"{new_substation.name} {vnom} kV",
                                            substation=new_substation,
                                            Vnom=vnom)
        self.circuit.add_voltage_level(voltage_level_in_new)

        # Add the voltage level graphic
        vl_graphic = self.add_api_voltage_level(
            substation_graphics=new_substation_graphic,
            api_object=voltage_level_in_new
        )

        # Create a new bus in the new substation
        new_bus = Bus(name=f"{new_substation.name} {vnom} kV Bus",
                      Vnom=vnom,
                      vmin=suitable_bus_in_selected.Vmin,
                      vmax=suitable_bus_in_selected.Vmax,
                      voltage_level=voltage_level_in_new,
                      substation=new_substation,
                      area=suitable_bus_in_selected.area,
                      zone=suitable_bus_in_selected.zone,
                      country=suitable_bus_in_selected.country)

        # Add the new bus to the circuit
        self.circuit.add_bus(new_bus)

        # Step 3: Calculate the lengths of the segments
        # Collect all waypoints of the original line
        waypoints = []

        # Add the "from" substation
        substation_from_graphics = self.graphics_manager.query(elm=line_api.get_substation_from())
        if substation_from_graphics is not None:
            waypoints.append((substation_from_graphics.lat, substation_from_graphics.lon))

        # Add all intermediate points
        for node in original_line_container.nodes_list:
            waypoints.append((node.lat, node.lon))

        # Add the "to" substation
        substation_to_graphics = self.graphics_manager.query(elm=line_api.get_substation_to())
        if substation_to_graphics is not None:
            waypoints.append((substation_to_graphics.lat, substation_to_graphics.lon))

        # Calculate length of first segment (from original start to waypoint)
        length1 = 0.0
        for i in range(waypoint_idx + 1):
            if i < len(waypoints) - 1:
                lat1, lon1 = waypoints[i]
                lat2, lon2 = waypoints[i + 1]
                length1 += haversine_distance(lat1, lon1, lat2, lon2)

        # Calculate length of second segment (from waypoint to original end)
        length2 = 0.0
        for i in range(waypoint_idx + 1, len(waypoints) - 1):
            lat1, lon1 = waypoints[i]
            lat2, lon2 = waypoints[i + 1]
            length2 += haversine_distance(lat1, lon1, lat2, lon2)

        # Calculate the proportion of each segment
        total_length = length1 + length2
        ratio1 = length1 / total_length
        ratio2 = length2 / total_length

        # Step 4: Create the two new line segments that replace the original line
        # Line 1: from original bus_from to new_bus
        line1_name = f"{line_api.name}_1"

        # Handle the code property - it might be a list of strings
        if hasattr(line_api, 'code') and line_api.code is not None:
            if isinstance(line_api.code, list):
                line1_code = [f"{code}_1" for code in line_api.code]
            else:
                line1_code = f"{line_api.code}_1"
        else:
            line1_code = ""

        line1 = Line(name=line1_name,
                     bus_from=line_api.bus_from,
                     bus_to=new_bus,
                     code=line1_code,
                     r=line_api.R * ratio1,  # Set impedance proportional to length
                     x=line_api.X * ratio1,
                     b=line_api.B * ratio1,
                     r0=line_api.R0 * ratio1,
                     x0=line_api.X0 * ratio1,
                     b0=line_api.B0 * ratio1,
                     r2=line_api.R2 * ratio1,
                     x2=line_api.X2 * ratio1,
                     b2=line_api.B2 * ratio1,
                     length=length1,  # Set the actual calculated length
                     rate=line_api.rate,
                     contingency_factor=line_api.contingency_factor,
                     protection_rating_factor=line_api.protection_rating_factor)

        # Copy other properties from the original line
        if hasattr(line_api, 'color'):
            line1.color = line_api.color
        if hasattr(line_api, 'tags') and line_api.tags:
            line1.tags = line_api.tags.copy() if isinstance(line_api.tags, list) else line_api.tags
        if hasattr(line_api, 'active'):
            line1.active = line_api.active

        # Preserve waypoints for line 1 (from start to waypoint)
        # Add all waypoints from the original line up to the waypoint
        for i in range(waypoint_idx):
            if i < len(original_line_container.nodes_list):
                node = original_line_container.nodes_list[i]
                line1.locations.add_location(lat=node.lat, long=node.lon, alt=0.0)

        # Line 2: from new_bus to original bus_to
        line2_name = f"{line_api.name}_2"

        # Handle the code property for line 2
        if hasattr(line_api, 'code') and line_api.code is not None:
            if isinstance(line_api.code, list):
                line2_code = [f"{code}_2" for code in line_api.code]
            else:
                line2_code = f"{line_api.code}_2"
        else:
            line2_code = ""

        line2 = Line(name=line2_name,
                     bus_from=new_bus,
                     bus_to=line_api.bus_to,
                     code=line2_code,
                     r=line_api.R * ratio2,  # Set impedance proportional to length
                     x=line_api.X * ratio2,
                     b=line_api.B * ratio2,
                     r0=line_api.R0 * ratio2,
                     x0=line_api.X0 * ratio2,
                     b0=line_api.B0 * ratio2,
                     r2=line_api.R2 * ratio2,
                     x2=line_api.X2 * ratio2,
                     b2=line_api.B2 * ratio2,
                     length=length2,  # Set the actual calculated length
                     rate=line_api.rate,
                     contingency_factor=line_api.contingency_factor,
                     protection_rating_factor=line_api.protection_rating_factor)

        # Copy other properties from the original line
        if hasattr(line_api, 'color'):
            line2.color = line_api.color
        if hasattr(line_api, 'tags') and line_api.tags:
            line2.tags = line_api.tags.copy() if isinstance(line_api.tags, list) else line_api.tags
        if hasattr(line_api, 'active'):
            line2.active = line_api.active

        # Preserve waypoints for line 2 (from waypoint to end)
        # Add all remaining waypoints from the original line after the waypoint
        for i in range(waypoint_idx + 1, len(original_line_container.nodes_list)):
            node = original_line_container.nodes_list[i]
            line2.locations.add_location(lat=node.lat, long=node.lon, alt=0.0)

        # Step 5: Create a new line connecting the selected substation to the new junction substation
        connection_line_name = f"{substation_api.name}_to_{new_substation.name}"

        # Calculate the distance between the two substations
        distance = haversine_distance(substation_api.latitude, substation_api.longitude, waypoint_lat, waypoint_lon)

        # Create the new connection line
        connection_line = Line(name=connection_line_name,
                               bus_from=suitable_bus_in_selected,
                               bus_to=new_bus,
                               r=line_api.R * (distance / line_api.length),
                               x=line_api.X * (distance / line_api.length),
                               b=line_api.B * (distance / line_api.length),
                               r0=line_api.R0 * (distance / line_api.length),
                               x0=line_api.X0 * (distance / line_api.length),
                               b0=line_api.B0 * (distance / line_api.length),
                               r2=line_api.R2 * (distance / line_api.length),
                               x2=line_api.X2 * (distance / line_api.length),
                               b2=line_api.B2 * (distance / line_api.length),
                               length=distance,
                               rate=line_api.rate,
                               contingency_factor=line_api.contingency_factor,
                               protection_rating_factor=line_api.protection_rating_factor)

        # Copy other properties from the original line
        if hasattr(line_api, 'color'):
            connection_line.color = line_api.color
        if hasattr(line_api, 'tags') and line_api.tags:
            connection_line.tags = line_api.tags.copy() if isinstance(line_api.tags, list) else line_api.tags
        if hasattr(line_api, 'active'):
            connection_line.active = line_api.active

        # No waypoints needed for the connection line - it will go directly from one substation to the other

        # Add the new lines to the circuit
        self.circuit.add_line(line1)
        self.circuit.add_line(line2)
        self.circuit.add_line(connection_line)

        # Add the new lines to the map
        line1_graphic = self.add_api_line(line1)
        line2_graphic = self.add_api_line(line2)
        connection_line_graphic = self.add_api_line(connection_line)

        # Get the branch width and arrow size from the general diagram settings
        branch_width = self.diagram.min_branch_width
        arrow_size = self.diagram.arrow_size

        # If we have segments in the original line, use their width and arrow size
        if original_line_container and original_line_container.segments_list:
            if len(original_line_container.segments_list) > 0:
                segment = original_line_container.segments_list[0]
                branch_width = segment.get_width()
                arrow_size = segment.get_arrow_size()

        # Apply the same width and arrow size to the new lines
        line1_graphic.set_width_scale(width=branch_width, arrow_width=arrow_size)
        line2_graphic.set_width_scale(width=branch_width, arrow_width=arrow_size)
        connection_line_graphic.set_width_scale(width=branch_width, arrow_width=arrow_size)

        # Explicitly remove the waypoint graphic from the scene to prevent artifact
        self.map.diagram_scene.removeItem(selected_waypoint)

        # Remove the original line
        self.remove_branch_graphic(line=original_line_container, delete_from_db=True)

        # Notify the user
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"T-joint connection created between {substation_api.name} and {line_api.name}.")
        msg.setInformativeText(
            f"Waypoint replaced with new substation '{new_substation.name}'.\nOriginal line split into two segments:\n- {line1.name}: {length1:.2f} km\n- {line2.name}: {length2:.2f} km\nNew connection line: {distance:.2f} km")
        msg.setWindowTitle("Operation Successful")
        msg.exec()


def generate_map_diagram(
        substations: List[Substation],
        voltage_levels: List[VoltageLevel],
        lines: List[Line],
        dc_lines: List[DcLine],
        hvdc_lines: List[HvdcLine],
        fluid_nodes: List[FluidNode],
        fluid_paths: List[FluidPath],
        prog_func: Union[Callable, None] = None,
        text_func: Union[Callable, None] = None,
        name='Map diagram',
        use_flow_based_width: bool = False,
        min_branch_width: int = 1.0,
        max_branch_width=5,
        min_bus_width=1.0,
        max_bus_width=20,
        arrow_size=20,
        palette: Colormaps = Colormaps.GridCal,
        default_bus_voltage: float = 10
) -> MapDiagram:
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
    :param use_flow_based_width: use flow based width
    :param min_branch_width: minimum branch width
    :param max_branch_width: maximum branch width
    :param min_bus_width:
    :param max_bus_width: maximum bus width
    :param arrow_size: arrow size
    :param palette: Colormaps
    :param default_bus_voltage: default bus voltage
    """

    diagram = MapDiagram(
        name=name,
        use_flow_based_width=use_flow_based_width,
        min_branch_width=min_branch_width,
        max_branch_width=max_branch_width,
        min_bus_width=min_bus_width,
        max_bus_width=max_bus_width,
        arrow_size=arrow_size,
        palette=palette,
        default_bus_voltage=default_bus_voltage
    )

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
        for loc in branch.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

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

        diagram.set_point(device=elm, location=MapLocation())

        # register all the line locations
        for loc in elm.locations.get_locations():
            diagram.set_point(device=loc, location=MapLocation(latitude=loc.lat,
                                                               longitude=loc.long,
                                                               altitude=loc.alt))

    # find the diagram centre and set it internally
    diagram.set_center()

    return diagram


def get_devices_to_expand(circuit: MultiCircuit, substations: List[Substation], max_level: int = 1,
                          expand_outside: bool = True) -> Tuple[
    List[Substation],
    List[VoltageLevel],
    List[Line],
    List[DcLine],
    List[HvdcLine]]:
    """
    get lists of devices to expand given a root bus
    :param circuit: MultiCircuit
    :param substations: List of Bus
    :param max_level: max expansion level
    :param expand_outside: whether to expand outside of the given references using the branches
    :return:
    """

    # get all Branches
    all_branches = circuit.lines + circuit.dc_lines + circuit.hvdc_lines

    # create a pool of buses that belong to the substations
    # store the bus objects and their level from the root
    bus_pool = [(b, 0) for b in circuit.buses if b.substation in substations]

    voltage_levels = set()
    substations_extended = set()
    selected_branches = set()

    while len(bus_pool) > 0:

        # search the next bus
        bus, level = bus_pool.pop()

        if bus.voltage_level is not None:
            voltage_levels.add(bus.voltage_level)
            substations_extended.add(bus.substation)

        if level < max_level:

            for i, br in enumerate(all_branches):

                if br.bus_from == bus:
                    if expand_outside:
                        bus_pool.append((br.bus_to, level + 1))
                    selected_branches.add(br)

                elif br.bus_to == bus:
                    if expand_outside:
                        bus_pool.append((br.bus_from, level + 1))
                    selected_branches.add(br)

                else:
                    pass

    # sort Branches
    lines: List[Line] = list()
    dc_lines: List[DcLine] = list()
    hvdc_lines: List[HvdcLine] = list()

    for obj in selected_branches:

        if obj.device_type == DeviceType.LineDevice:
            lines.append(obj)

        elif obj.device_type == DeviceType.DCLineDevice:
            dc_lines.append(obj)


        elif obj.device_type == DeviceType.HVDCLineDevice:
            hvdc_lines.append(obj)

        else:
            raise Exception(f'Unrecognized branch type {obj.device_type.value}')

    return list(substations_extended), list(voltage_levels), lines, dc_lines, hvdc_lines


def make_diagram_from_substations(circuit: MultiCircuit,
                                  substations: List[Substation] | Set[Substation],
                                  prog_func: Union[Callable, None] = None,
                                  text_func: Union[Callable, None] = None,
                                  use_flow_based_width: bool = False,
                                  min_branch_width: int = 1.0,
                                  max_branch_width=5,
                                  min_bus_width=1.0,
                                  max_bus_width=20,
                                  arrow_size=20,
                                  palette: Colormaps = Colormaps.GridCal,
                                  default_bus_voltage: float = 10,
                                  expand_outside: bool = True,
                                  name="Map diagram"):
    """
    Create a vicinity diagram
    :param circuit: MultiCircuit
    :param substations: List of Bus
    :param prog_func:
    :param text_func:
    :param use_flow_based_width: use flow based width
    :param min_branch_width: minimum branch width
    :param max_branch_width: maximum branch width
    :param min_bus_width:
    :param max_bus_width: maximum bus width
    :param arrow_size: arrow size
    :param palette: Colormaps
    :param default_bus_voltage: default bus voltage
    :param expand_outside: whether to expand outside the given references using the branches
    :param name: Name of the diagram
    :return:
    """

    (substations_extended, voltage_levels,
     lines, dc_lines, hvdc_lines) = get_devices_to_expand(circuit=circuit,
                                                          substations=substations,
                                                          max_level=1,
                                                          expand_outside=expand_outside)

    # Draw schematic subset
    diagram = generate_map_diagram(
        substations=substations_extended,
        voltage_levels=voltage_levels,
        lines=lines,
        dc_lines=dc_lines,
        hvdc_lines=hvdc_lines,
        fluid_nodes=list(),
        fluid_paths=list(),
        prog_func=prog_func,
        text_func=text_func,
        name=name,
        use_flow_based_width=use_flow_based_width,
        min_branch_width=min_branch_width,
        max_branch_width=max_branch_width,
        min_bus_width=min_bus_width,
        max_bus_width=max_bus_width,
        arrow_size=arrow_size,
        palette=palette,
        default_bus_voltage=default_bus_voltage
    )

    return diagram
