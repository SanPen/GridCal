# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import ast
import os
from typing import Union, List, Tuple, Dict, TYPE_CHECKING
import json
import numpy as np
import math
from warnings import warn

from PySide6.QtWidgets import QGraphicsItem, QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton
from collections.abc import Callable
from PySide6.QtCore import (Qt, QMimeData, QIODevice, QByteArray, QDataStream, QModelIndex, QRunnable, QThreadPool,
                            QCoreApplication)
from PySide6.QtGui import (QIcon, QPixmap, QImage, QStandardItemModel, QStandardItem, QColor, QDropEvent,
                           QWheelEvent, QPainter)

from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_line_polyline import MapLinePolyline
from VeraGrid.Gui.Diagrams.MapWidget.Injections.map_injections_template_graphics import MapInjectionTemplateGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem
from VeraGrid.Gui.Diagrams.generic_graphics import GenericDiagramWidget
from VeraGrid.Gui.SubstationDesigner.substation_designer import SubstationDesigner
from VeraGrid.Gui.general_dialogues import InputNumberDialogue
from VeraGrid.Gui.dialog_lifecycle import exec_dialog_safely
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.PlotDialogue.result_table_data import append_result_table_column
from VeraGridEngine.Devices.Diagrams.map_location import MapLocation
from VeraGridEngine.Devices.Substation import Bus
from VeraGridEngine.Devices.Branches.line import Line, accept_line_connection
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.hvdc_line import HvdcLine
from VeraGridEngine.Devices.Injections.battery import Battery
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.external_grid import ExternalGrid
from VeraGridEngine.Devices.Injections.static_generator import StaticGenerator
from VeraGridEngine.Devices.Diagrams.map_diagram import MapDiagram
from VeraGridEngine.Devices.Fluid import FluidNode, FluidPath
from VeraGridEngine.Utils.GeographicalMethods.haversine_distance import haversine_distance, closest_point_on_segment
from VeraGridEngine.basic_structures import Vec, CxVec, IntVec
from VeraGridEngine.Devices.Substation.substation import Substation
from VeraGridEngine.Devices.Substation.voltage_level import VoltageLevel
from VeraGridEngine.Devices.Branches.line_locations import LineLocation
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType, ResultTypes
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
from VeraGridEngine.Simulations.PowerFlow.power_flow_ts_results import PowerFlowTimeSeriesResults
from VeraGridEngine.enumerations import Colormaps
from VeraGridEngine.Topology.VoltageLevels import vl_creation_common_functions as substation_wizards
import VeraGridEngine.Devices.Diagrams.palettes as palettes

from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_ac_line import MapAcLine
from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_dc_line import MapDcLine
from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_hvdc_line import MapHvdcLine
from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_fluid_path import MapFluidPathLine
from VeraGrid.Gui.Diagrams.MapWidget.Branches.line_location_graphic_item import LineLocationGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Injections.map_battery_graphics import MapBatteryGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Injections.map_generator_graphics import MapGeneratorGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Injections.map_load_graphics import MapLoadGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Injections.map_external_grid_graphics import MapExternalGridGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Injections.map_static_generator_graphics import MapStaticGeneratorGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.map_widget import MapWidget, MapDiagramScene
from VeraGrid.Gui.Diagrams.Editors.new_line_dialogue import NewMapLineDialogue
from VeraGrid.Gui.Diagrams.Editors.bus_selector import BusSelectorDialogue

import VeraGrid.Gui.Visualization.visualization as viz
from VeraGrid.Gui.Diagrams.graphics_manager import ALL_MAP_GRAPHICS
from VeraGrid.Gui.Diagrams.MapWidget.Tiles.tiles import Tiles
from VeraGrid.Gui.Diagrams.base_diagram_widget import BaseDiagramWidget
from VeraGrid.Gui.messages import error_msg, yes_no_question

if TYPE_CHECKING:
    from VeraGrid.Gui.Main.SubClasses.Model.diagrams import DiagramsMain
    from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI

MAP_BRANCH_GRAPHIC_TYPES = Union[
    MapAcLine, MapDcLine, MapHvdcLine, MapFluidPathLine
]


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

        self.add(name=QCoreApplication.translate("MapLibraryModel", "Substation"),
                 device_type=DeviceType.SubstationDevice,
                 icon_name="substation")

    def add(self, name: str, device_type: DeviceType, icon_name: str) -> None:
        """
        Add element to the library
        :param name: Name of the element
        :param device_type: Device type to identify the element independently of the translated label.
        :param icon_name: Icon name, the path is taken care of
        :return:
        """
        _icon = QIcon()
        _icon.addPixmap(QPixmap(f":/Icons/icons/{icon_name}.png"))
        _item = QStandardItem(_icon, name)
        _item.setData(device_type, Qt.ItemDataRole.UserRole)
        _item.setToolTip(QCoreApplication.translate(
            "MapLibraryModel",
            "Drag & drop {name} into the schematic",
        ).format(name=name))
        self.appendRow(_item)

    def retranslate(self) -> None:
        """
        Refresh translated item labels without changing the drag/drop device type data.

        :return: None.
        """
        row: int
        item: QStandardItem | None
        device_type: DeviceType
        name: str

        for row in range(self.rowCount()):
            item = self.item(row, 0)

            if item is not None:
                device_type = item.data(Qt.ItemDataRole.UserRole)

                if device_type == DeviceType.SubstationDevice:
                    name = QCoreApplication.translate("MapLibraryModel", "Substation")
                else:
                    name = item.text()

                item.setText(name)
                item.setToolTip(QCoreApplication.translate(
                    "MapLibraryModel",
                    "Drag & drop {name} into the schematic",
                ).format(name=name))
            else:
                pass

    @staticmethod
    def to_bytes_array(val: str) -> QByteArray:
        """
        Convert string to QByteArray
        :param val: string
        :return: QByteArray
        """
        data = QByteArray()
        stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
        stream.writeQString(val)
        return data

    def get_substation_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(DeviceType.SubstationDevice.name)

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
                device_type = self.data(idx, Qt.ItemDataRole.UserRole)

                if isinstance(device_type, DeviceType):
                    data = QByteArray()
                    stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
                    stream.writeQString(device_type.name)

                    mime_data.setData('component/name', data)
                else:
                    pass
            else:
                pass
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
        self.setWindowTitle(self.tr("Waiting for Selection"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout()

        # Add instructions
        instruction_label = QLabel(
            self.tr("Click on a substation to reconnect branch {branch_name}").format(
                branch_name=branch.api_object.name,
            )
        )
        instruction_label.setWordWrap(True)
        layout.addWidget(instruction_label)

        # Add more detailed instructions
        detail_label = QLabel(
            self.tr("The substation should have a compatible voltage level ({voltage} kV)").format(
                voltage=vnom,
            )
        )
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)

        # Add a status label that will be updated
        self.status_label = QLabel(self.tr("Waiting for selection..."))
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Add a cancel button
        cancel_button = QPushButton(self.tr("Cancel"))
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
                 gui: VeraGridMainGUI | DiagramsMain,
                 tile_src: Tiles,
                 start_level: int,
                 longitude: float,
                 latitude: float,
                 name: str,
                 diagram: MapDiagram):
        """
        GridMapWidget
        :param tile_src: Tiles instance
        :param start_level: starting level
        :param longitude: Center point Longitude (deg)
        :param latitude: Center point Latitude (deg)
        :param name: Name of the diagram
        :param diagram: Diagram instance (optional)
        """
        render_level = 6 if tile_src.level_in_range(6) else max(tile_src.min_level,
                                                                min(start_level, tile_src.max_level))

        super().__init__(
            gui=gui,
            diagram=MapDiagram(name=name,
                               tile_source=tile_src.tile_set_name,
                               start_level=start_level,
                               longitude=longitude,
                               latitude=latitude) if diagram is None else diagram,
            library_model=MapLibraryModel(),
            time_index=None,
        )

        # declare the map
        self.map = MapWidget(parent=self,
                             tile_src=tile_src,
                             start_level=render_level,
                             editor=self,
                             zoom_callback=self.zoom_callback,
                             position_callback=self.position_callback)
        self.register_video_time_label_canvas(view=self.map.view)
        self.diagram_scene.selectionChanged.connect(self._sync_line_handle_visibility)

        # Draw the overlay at a stable base zoom, then move to the persisted
        # viewport using the synchronized zoom path.
        self.map.go_to_level_and_position(level=render_level,
                                          longitude=self.diagram.longitude,
                                          latitude=self.diagram.latitude)

        # pool of runnable tasks that work best done asynch with a runnable
        self.thread_pool = QThreadPool()
        self.wheel_move_task: QRunnable | None = None
        self.zoom_angle_step: float = 120.0
        self.zoom_pixel_step: float = 240.0
        self.zoom_max_event_steps: float = 1.0

        # Draw the diagram. New diagrams are auto-centered from their graphics after the map viewport is initialized;
        # loaded diagrams must preserve their persisted viewport.
        self.draw()
        self._sync_line_handle_visibility()

        if self.diagram.start_level != self.map.level:
            self.map.apply_zoom_level(level=self.diagram.start_level)

        self.map.go_to_position(longitude=self.diagram.longitude,
                                latitude=self.diagram.latitude)

        self.center()
        self._last_branch_width: float | None = None
        self._last_arrow_width: float | None = None
        self._last_substation_width: float | None = None

    def set_diagram(self, diagram: MapDiagram):
        """

        :param diagram:
        :return:
        """
        self.diagram = diagram

    def delete_element_utility_function(self,
                                        device: ALL_DEV_TYPES,
                                        propagate: bool = True,
                                        graphic_object: QGraphicsItem | None = None):
        """

        :param device:
        :param propagate: Propagate the action to other diagrams?
        :param graphic_object: graphic_object
        :return:
        """
        self.diagram.delete_device(device=device)

        if graphic_object is None:
            graphic_object: ALL_MAP_GRAPHICS = self.graphics_manager.delete_device(device=device)

        if graphic_object is not None:
            self._remove_from_scene(graphic_object)

        if propagate:
            self.gui.call_delete_db_element(caller=self, api_obj=device)

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

    @property
    def diagram_scene(self) -> MapDiagramScene:
        """
        :return: MapDiagramScene
        """
        return self.map.diagram_scene

    def get_selected(self) -> List[ALL_MAP_GRAPHICS | QGraphicsItem]:
        """
        Get selection
        :return: List of ALL_MAP_GRAPHICS
        """
        return [elm for elm in self.diagram_scene.selectedItems()]

    def _get_selection_api_objects(self) -> List[ALL_DEV_TYPES]:
        """
        Get a list of the API objects from the selection
        :return: List[EditableDevice]
        """
        return [e.api_object for e in self.get_selected()]

    def _get_selected_line_containers(self) -> List[MAP_BRANCH_GRAPHIC_TYPES]:
        """
        Get selected line containers from selected lines, segments or waypoints.
        """
        selected_lines: List[MAP_BRANCH_GRAPHIC_TYPES] = list()
        selected_line_ids: set[int] = set()
        item: QGraphicsItem
        for item in self.diagram_scene.selectedItems():
            if isinstance(item, (MapAcLine,
                                 MapDcLine,
                                 MapHvdcLine,
                                 MapFluidPathLine)):
                line_id = id(item)
                if line_id not in selected_line_ids:
                    selected_line_ids.add(line_id)
                    selected_lines.append(item)
            elif isinstance(item, MapLinePolyline):
                line_id = id(item.container)
                if line_id not in selected_line_ids:
                    selected_line_ids.add(line_id)
                    selected_lines.append(item.container)
                else:
                    pass
            elif isinstance(item, LineLocationGraphicItem):
                line_id = id(item.line_container)
                if line_id not in selected_line_ids:
                    selected_line_ids.add(line_id)
                    selected_lines.append(item.line_container)
                else:
                    pass
            else:
                pass

        return selected_lines

    def _sync_line_handle_visibility(self) -> None:
        """
        Keep waypoint handles visible only for selected lines.
        """
        selected_lines = self._get_selected_line_containers()
        selected_line_ids: set[int] = set(id(line_container) for line_container in selected_lines)

        for dev_tpe in [DeviceType.LineDevice,
                        DeviceType.DCLineDevice,
                        DeviceType.HVDCLineDevice,
                        DeviceType.FluidPathDevice]:
            for line_container in self.graphics_manager.get_device_type_list(dev_tpe):
                line_container.set_handles_visible(id(line_container) in selected_line_ids)

    def get_selected_line_segments_tuple(self) -> List[Tuple[Line, (MapAcLine |
                                                                    MapDcLine |
                                                                    MapHvdcLine |
                                                                    MapFluidPathLine)]]:
        """
        Get only selected line segments from the scene

        :return: List of (Line, (MapAcLine, MapDcLine, MapHvdcLine, MapFluidPathLine)) tuples
        """
        selected_line_segments = list()
        for line_container in self._get_selected_line_containers():
            selected_line_segments.append((line_container.api_object, line_container))
        return selected_line_segments

    def get_selected_substations_tuple(self) -> List[Tuple[Substation, SubstationGraphicItem]]:
        """
        Get only selected substations from the scene

        :return: List of (Substation, SubstationGraphicItem) tuples
        """
        selected_substations = list()
        for item in self.diagram_scene.selectedItems():
            if isinstance(item, SubstationGraphicItem):
                selected_substations.append((item.api_object, item))
            else:
                pass
        return selected_substations

    def get_selected_generators_tuple(self) -> List[Tuple[Generator, MapGeneratorGraphicItem]]:
        """
        Get only selected generators from the scene

        :return: List of (Generator, GeneratorGraphicItem) tuples
        """
        selected_generators = list()
        for item in self.diagram_scene.selectedItems():
            if isinstance(item, MapGeneratorGraphicItem):
                selected_generators.append((item.api_object, item))
            else:
                pass
        return selected_generators

    def get_selected_line_locations_tuple(self) -> List[Tuple[LineLocation, LineLocationGraphicItem]]:
        """
        Get only selected Line Locations from the scene

        :return: List of (LineLocation, LineLocationGraphicItem) tuples
        """
        selected_line_locations = list()
        for item in self.diagram_scene.selectedItems():
            if isinstance(item, LineLocationGraphicItem):
                selected_line_locations.append((item.api_object, item))
            else:
                pass
        return selected_line_locations

    def add_to_scene(self, graphic_object: ALL_MAP_GRAPHICS | None = None) -> None:
        """
        Add item to the diagram and the diagram scene
        :param graphic_object: Graphic object associated
        """
        if graphic_object is None:
            return
        else:
            self.diagram_scene.addItem(graphic_object)

    def _remove_from_scene(self, graphic_object: ALL_MAP_GRAPHICS | GenericDiagramWidget | None) -> None:
        """
        Remove item from the diagram scene
        :param graphic_object: Graphic object associated
        """
        if graphic_object is None:
            return
        else:
            if isinstance(graphic_object, GenericDiagramWidget):
                if graphic_object.api_object is not None:
                    self.graphics_manager.delete_device(graphic_object.api_object)
                else:
                    pass
            else:
                pass

            if isinstance(graphic_object, QGraphicsItem):
                if graphic_object.scene() is not None:
                    self.diagram_scene.removeItem(graphic_object)
                else:
                    pass
            else:
                pass

    def clear(self) -> None:
        """
        Clear the map diagram scene and graphics registry.
        """
        super().clear()
        self.diagram_scene.clear()

    def prepare_to_delete(self) -> None:
        """
        Stop map-specific background work before widget destruction.
        """
        self.map.tile_src.shutdown()
        super().prepare_to_delete()

    def remove_element(self,
                       device: ALL_DEV_TYPES,
                       graphic_object: ALL_MAP_GRAPHICS = None,
                       delete_from_db: bool = False) -> None:
        """
        Remove device from the diagram and the database.
        If removing from the database, this propagates to all diagrams
        :param device: EditableDevice
        :param graphic_object: optionally provide the graphics object associated
        :param delete_from_db: Delete the element also from the database?
        """

        # call the parent functionality, this propagated to other diagrams if delete_from_db
        deleted: bool = super().remove_element(device=device,
                                               graphic_object=graphic_object,
                                               delete_from_db=delete_from_db)
        # if deleted:
        #
        #     if isinstance(graphic_object, SubstationGraphicItem):
        #         self.remove_substation(substation=graphic_object,
        #                                delete_from_db=delete_from_db)
        #
        #     elif isinstance(graphic_object, (MapAcLine, MapDcLine, MapHvdcLine, MapFluidPathLine)):
        #         self.remove_branch_graphic(line=graphic_object, delete_from_db=delete_from_db)
        # else:
        #     # the notifications are handled by the parent
        #     pass

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

    def zoom_in(self) -> None:
        """
        Zoom in
        """
        if self.map.level + 1 <= self.map.max_level:
            self.map.apply_zoom_level(level=self.map.level + 1)

    def zoom_out(self) -> None:
        """
        Zoom out
        """
        if self.map.level - 1 >= self.map.min_level:
            self.map.apply_zoom_level(level=self.map.level - 1)

    def get_wheel_zoom_steps(self, event: QWheelEvent) -> float:
        """
        Convert a wheel event into a normalized zoom step count.

        A mouse wheel commonly emits an angle delta of 120 units per notch, while laptop touchpads emit many smaller
        high-resolution events and may provide pixel deltas. Normalizing by the event magnitude keeps mouse-wheel zoom
        unchanged and lets touchpad gestures accumulate progressively instead of changing one map level per event.

        :param event: Wheel event coming from the map view.
        :return: Signed zoom step count.
        """
        pixel_delta_y: int = event.pixelDelta().y()
        angle_delta_y: int = event.angleDelta().y()

        if pixel_delta_y != 0:
            zoom_steps: float = float(pixel_delta_y) / self.zoom_pixel_step
        else:
            zoom_steps = float(angle_delta_y) / self.zoom_angle_step

        if zoom_steps > self.zoom_max_event_steps:
            normalized_zoom_steps: float = self.zoom_max_event_steps
        else:
            if zoom_steps < -self.zoom_max_event_steps:
                normalized_zoom_steps = -self.zoom_max_event_steps
            else:
                normalized_zoom_steps = zoom_steps

        return normalized_zoom_steps

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
                                                 r=self.diagram.min_branch_width)

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

    def get_selected_buses(self) -> List[Tuple[int, Bus, BusGraphicItem | None]]:
        """
        Get a list of buses from the selected substations
        :return:
        """
        buses: List[Tuple[int, Bus, BusGraphicItem | None]] = list()
        se_graphics = self.get_selected_substations()

        se_api_set = set()
        for se_graphic in se_graphics:
            if se_graphic.api_object is not None:
                se_api_set.add(se_graphic.api_object)

        for i, bus in enumerate(self.circuit.buses):
            if bus.substation in se_api_set:
                buses.append((i, bus, None))

        return buses

    def get_substations(self) -> List[Tuple[int, Substation, SubstationGraphicItem | None]]:
        """
        Get all the substations
        :return: tuple(substation index, substation_api_object, substation_graphic_object)
        """
        lst: List[Tuple[int, Substation, SubstationGraphicItem | None]] = list()
        substation_graphics_dict = self.graphics_manager.get_device_type_dict(DeviceType.SubstationDevice)
        substations_dict: Dict[str, Tuple[int, Substation]] = {b.idtag: (i, b)
                                                               for i, b in enumerate(self.circuit.substations)}

        for bus_idtag, graphic_object in substation_graphics_dict.items():
            idx, substation = substations_dict[bus_idtag]
            lst.append((idx, substation, graphic_object))

        return lst

    def create_new_line_wizard(self):
        """
        Create a new line in the map with dialogues
        """

        selected_items = self.get_selected_substations()

        if len(selected_items) != 2:
            error_msg(text=self.tr("Please select two substations"), title=self.tr("Create new line"))
            return None

        it1: SubstationGraphicItem = selected_items[0]
        it2: SubstationGraphicItem = selected_items[1]

        if it1 == it2:
            error_msg(text=self.tr("Somehow the two substations are the same :("), title=self.tr("Create new line"))
            return None

        dialog = NewMapLineDialogue(grid=self.circuit, se_from=it1.api_object, se_to=it2.api_object)
        exec_dialog_safely(dialog=dialog)
        if dialog.is_valid():
            bus1 = dialog.bus_from()
            bus2 = dialog.bus_to()
            if bus1 is not None and bus2 is not None:
                if accept_line_connection(V1=bus1.Vnom, V2=bus2.Vnom, branch_connection_voltage_tolerance=0.1):
                    new_line = Line(bus_from=bus1, bus_to=bus2)
                    self.add_api_line(new_line)
                    self.circuit.add_line(new_line)
                else:
                    error_msg(text=self.tr("The nominal voltage of the two connecting substations is not the same :("),
                              title=self.tr("Create new line"))
                    return None
            else:
                error_msg(text=self.tr("Some of the buses was None :("), title=self.tr("Create new line"))
                return None

    def remove_line_location_graphic(self, node: LineLocationGraphicItem):
        """
        Removes node from diagram and scene
        :param node: Node to delete
        """

        self.graphics_manager.delete_device(node.api_object)
        self._remove_from_scene(node)

    def remove_substation(self,
                          api_object: Substation,
                          substation_buses: List[Bus],
                          voltage_levels: List[VoltageLevel],
                          delete_from_db: bool = False):
        """

        :param api_object: Substation object from the MultiCircuit
        :param substation_buses: List of buses associated to this substation
        :param voltage_levels:  List of voltage levels associated to this substation
        :param delete_from_db: Does it delete the objects from the Database too (bool)
        """

        # Remove from graphics manager and scene
        sub = self.graphics_manager.delete_device(api_object)
        self._remove_from_scene(sub)

        # Find and delete_with_dialogue all lines connected to the substation
        for tpe in [DeviceType.LineDevice, DeviceType.DCLineDevice, DeviceType.HVDCLineDevice]:

            for elm in self.graphics_manager.get_device_type_list(tpe):

                if elm.api_object.get_substation_from() == api_object or elm.api_object.get_substation_to() == api_object:

                    self.graphics_manager.delete_device(elm.api_object)

                    if elm.polyline is not None:
                        self.diagram_scene.removeItem(elm.polyline)
                        elm.polyline = None

                    for segment in elm.segments_list:
                        self._remove_from_scene(segment)

                    for line_loc in elm.nodes_list:
                        self._remove_from_scene(line_loc)

        # Finally, delete_with_dialogue from the database if requested
        if delete_from_db:
            # Delete buses associated with this substation
            for bus in substation_buses:
                self.circuit.delete_bus(bus, delete_associated=True)

            # Delete voltage levels associated with this substation
            for vl in voltage_levels:
                self.circuit.delete_voltage_level(vl)

            # Delete the substation itself
            self.circuit.delete_substation(obj=api_object)

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

            if lin.polyline is not None:
                self.diagram_scene.removeItem(lin.polyline)
                lin.polyline = None

            for seg in lin.segments_list:
                self._remove_from_scene(seg)

            for line_loc in lin.nodes_list:
                self._remove_from_scene(line_loc)

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

        self.diagram.set_point(device=api_object,
                               location=MapLocation(latitude=lat,
                                                    longitude=lon,
                                                    api_object=api_object))

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

    def add_api_battery(self,
                        api_object: Battery,
                        lat: float,
                        lon: float) -> MapBatteryGraphicItem:
        """

        :param api_object:
        :param lat:
        :param lon:
        :return:
        """
        graphic_object = MapBatteryGraphicItem(
            editor=self,
            api_object=api_object,
            lat=lat,
            lon=lon,
            size=self.diagram.min_bus_width
        )

        self.graphics_manager.add_device(elm=api_object,
                                         graphic=graphic_object)

        self.add_to_scene(graphic_object=graphic_object)

        return graphic_object

    def add_api_generator(self,
                          api_object: Generator,
                          lat: float,
                          lon: float) -> MapGeneratorGraphicItem:
        """

        :param api_object:
        :param lat:
        :param lon:
        :return:
        """
        graphic_object = MapGeneratorGraphicItem(
            editor=self,
            api_object=api_object,
            lat=lat,
            lon=lon,
            size=self.diagram.min_bus_width
        )

        self.graphics_manager.add_device(elm=api_object,
                                         graphic=graphic_object)

        self.add_to_scene(graphic_object=graphic_object)

        return graphic_object

    def add_api_load(self,
                     api_object: Load,
                     lat: float,
                     lon: float) -> MapLoadGraphicItem:
        """

        :param api_object:
        :param lat:
        :param lon:
        :return:
        """
        graphic_object = MapLoadGraphicItem(
            editor=self,
            api_object=api_object,
            lat=lat,
            lon=lon,
            size=self.diagram.min_bus_width
        )

        self.graphics_manager.add_device(elm=api_object,
                                         graphic=graphic_object)

        self.add_to_scene(graphic_object=graphic_object)

        return graphic_object

    def add_api_external_grid(self,
                              api_object: ExternalGrid,
                              lat: float,
                              lon: float) -> MapExternalGridGraphicItem:
        """

        :param api_object:
        :param lat:
        :param lon:
        :return:
        """
        graphic_object = MapExternalGridGraphicItem(
            editor=self,
            api_object=api_object,
            lat=lat,
            lon=lon,
            size=self.diagram.min_bus_width
        )

        self.graphics_manager.add_device(elm=api_object,
                                         graphic=graphic_object)

        self.add_to_scene(graphic_object=graphic_object)

        return graphic_object

    def add_api_static_generator(self,
                                 api_object: StaticGenerator,
                                 lat: float,
                                 lon: float) -> MapStaticGeneratorGraphicItem:
        """

        :param api_object:
        :param lat:
        :param lon:
        :return:
        """
        graphic_object = MapStaticGeneratorGraphicItem(
            editor=self,
            api_object=api_object,
            lat=lat,
            lon=lon,
            size=self.diagram.min_bus_width
        )

        self.graphics_manager.add_device(elm=api_object,
                                         graphic=graphic_object)

        self.add_to_scene(graphic_object=graphic_object)

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

            elif category == DeviceType.GeneratorDevice.value:
                for idtag, location in points_group.locations.items():
                    self.add_api_generator(api_object=location.api_object,
                                           lon=location.longitude,
                                           lat=location.latitude)

            elif category == DeviceType.BatteryDevice.value:
                for idtag, location in points_group.locations.items():
                    self.add_api_battery(api_object=location.api_object,
                                         lon=location.longitude,
                                         lat=location.latitude)

            elif category == DeviceType.LoadDevice.value:
                for idtag, location in points_group.locations.items():
                    self.add_api_load(api_object=location.api_object,
                                      lon=location.longitude,
                                      lat=location.latitude)

            elif category == DeviceType.StaticGeneratorDevice.value:
                for idtag, location in points_group.locations.items():
                    self.add_api_static_generator(api_object=location.api_object,
                                                  lon=location.longitude,
                                                  lat=location.latitude)

            elif category == DeviceType.ExternalGridDevice.value:
                for idtag, location in points_group.locations.items():
                    self.add_api_external_grid(api_object=location.api_object,
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

                        if substation_graphics is not None:
                            # draw the voltage level
                            self.add_api_voltage_level(substation_graphics=substation_graphics,
                                                       api_object=location.api_object)
                        else:
                            warn(f'No substation graphic found for Voltage level: '
                                 f'{location.api_object.name} :: {location.api_object.idtag}')

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

    def add_object_to_the_schematic(self, elm: ALL_DEV_TYPES, logger: Logger | None = None):
        """

        :param elm:
        :param logger:
        :return:
        """
        if logger is None:
            logger = Logger()

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
                    if substation_graphics is None:
                        substation_graphics = self.add_api_substation(api_object=elm.substation,
                                                                      lon=elm.substation.longitude,
                                                                      lat=elm.substation.latitude)
                    else:
                        pass

                    # draw the voltage level
                    self.add_api_voltage_level(substation_graphics=substation_graphics,
                                               api_object=elm)
                else:
                    logger.add_warning("Voltage level has no substation",
                                       device=elm.name,
                                       device_class=elm.device_type.value)

            elif isinstance(elm, Bus):

                if elm.substation is not None:
                    # get the substation graphic object
                    substation_graphics = self.graphics_manager.query(elm=elm.substation)

                    if substation_graphics is None:
                        self.add_api_substation(api_object=elm.substation,
                                                lon=elm.substation.longitude,
                                                lat=elm.substation.latitude)
                    else:
                        pass
                else:
                    logger.add_warning("Bus has no substation",
                                       device=elm.name,
                                       device_class=elm.device_type.value)

            elif isinstance(elm, Line):
                line_container = self.add_api_line(elm)
                self.add_to_scene(graphic_object=line_container)
                # for segment in line_container.segments_list:
                #     self.add_to_scene(graphic_object=segment)

            elif isinstance(elm, DcLine):
                line_container = self.add_api_dc_line(elm)
                self.add_to_scene(graphic_object=line_container)

            elif isinstance(elm, HvdcLine):
                line_container = self.add_api_hvdc_line(elm)
                self.add_to_scene(graphic_object=line_container)

            elif isinstance(elm, FluidPath):
                line_container = self.add_api_fluid_path(elm)
                self.add_to_scene(graphic_object=line_container)

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
        dlg = SubstationDesigner(grid=self.circuit, default_voltage=kv, lat=lat, lon=lon)
        exec_dialog_safely(dialog=dlg)
        if dlg.was_ok():

            se_object, voltage_levels = substation_wizards.create_substation(
                grid=self.circuit,
                se_name=dlg.get_name(),
                se_code=dlg.get_code(),
                lat=dlg.get_latitude(),
                lon=dlg.get_longitude(),
                vl_templates=dlg.get_voltage_levels()
            )

            # create SE graphic
            substation_graphics = self.add_api_substation(api_object=se_object, lat=lat, lon=lon)

            # add voltage level graphics
            for vl in voltage_levels:
                self.add_api_voltage_level(substation_graphics=substation_graphics, api_object=vl)

            # sort voltage levels
            substation_graphics.sort_voltage_levels()

            # ask to create a se diagram
            ok = yes_no_question(title=self.tr("create substation diagram"),
                                 text=self.tr("Do you want to finalize the editing of the substation in the schematic?"))

            if ok:
                self.new_substation_diagram(substation=se_object)

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
        branch_width = self.diagram.min_branch_width  # self.get_branch_width()
        arrow_width = self.diagram.arrow_size  # self.get_arrow_scale()
        se_width = self.diagram.min_bus_width  # self.get_substation_scale()

        if self._last_branch_width == branch_width and self._last_arrow_width == arrow_width and self._last_substation_width == se_width:
            return
        else:
            pass

        self.diagram_scene.blockSignals(True)
        self.map.view.setUpdatesEnabled(False)

        try:
            # rescale lines
            for dev_tpe in [DeviceType.LineDevice,
                            DeviceType.DCLineDevice,
                            DeviceType.HVDCLineDevice,
                            DeviceType.FluidPathDevice]:
                graphics_dict = self.graphics_manager.get_device_type_dict(device_type=dev_tpe)

                #  TODO: this is super-slow
                for key, elm_graphics in graphics_dict.items():
                    elm_graphics.set_width_scale(width=branch_width, arrow_width=arrow_width)

            # Rescale LineLocations:
            graphics_dict = self.graphics_manager.get_device_type_dict(device_type=DeviceType.LineLocation)

            for key, elm_graphics in graphics_dict.items():
                elm_graphics.resize(new_radius=branch_width)

            # rescale substations (this is super-fast)
            for dev_tpe in [DeviceType.SubstationDevice,
                            DeviceType.GeneratorDevice,
                            DeviceType.BatteryDevice,
                            DeviceType.LoadDevice,
                            DeviceType.ExternalGridDevice,
                            DeviceType.StaticGeneratorDevice]:
                data: Dict[str, SubstationGraphicItem] = self.graphics_manager.get_device_type_dict(dev_tpe)
                for se_key, elm_graphics in data.items():
                    elm_graphics.set_api_object_color()
                    elm_graphics.set_size(r=se_width)

            self._last_branch_width = branch_width
            self._last_arrow_width = arrow_width
            self._last_substation_width = se_width
        finally:
            self.map.view.setUpdatesEnabled(True)
            self.diagram_scene.blockSignals(False)

        self.diagram_scene.update()

    def center(self) -> None:
        """
        Center the diagram
        """
        lat = 0.0
        lon = 0.0
        lat_max = -1e20
        lat_min = 1e20
        lon_max = -1e20
        lon_min = 1e20
        n = 0
        for dev_tpe in [DeviceType.SubstationDevice,
                        DeviceType.GeneratorDevice,
                        DeviceType.BatteryDevice,
                        DeviceType.LoadDevice,
                        DeviceType.ExternalGridDevice,
                        DeviceType.StaticGeneratorDevice]:
            for graphic_obj in self.graphics_manager.get_device_type_list(dev_tpe):
                lat += graphic_obj.lat
                lon += graphic_obj.lon

                lat_max = max(lat_max, graphic_obj.lat)
                lat_min = min(lat_min, graphic_obj.lat)
                lon_max = max(lon_max, graphic_obj.lon)
                lon_min = min(lon_min, graphic_obj.lon)
                n += 1

        if n > 0:
            lat /= n
            lon /= n

            level = self.map.best_zoom_from_bbox(min_lat=lat_min,
                                                 max_lat=lat_max,
                                                 min_lon=lon_min,
                                                 max_lon=lon_max)
            self.map.apply_zoom_level(level=level)
            self.map.go_to_position(latitude=lat, longitude=lon)

        else:
            self.gui.show_warning_toast("No points to center :/")

    def graphical_search(self, search_text: str):
        """
        Search object in the diagram and center around it
        :param search_text: object name, object code or object idtag
        """
        # Initialize boundaries
        min_lat = min_lon = max_lat = max_lon = None
        text = search_text.lower()

        n = 0
        for key, points_group in self.diagram.data.items():
            for idTag, location in points_group.locations.items():
                if location.api_object is not None:

                    # Check if searchText is in the name, code, or idtag of the api_object
                    if (text in location.api_object.name.lower() or
                            text in location.api_object.code.lower() or
                            text in str(location.api_object.idtag).lower()):

                        # Map locations are points, so the search bounds use the stored coordinate directly.
                        left = location.latitude
                        right = location.latitude
                        top = location.longitude
                        bottom = location.longitude

                        if min_lat is None or left < min_lat:
                            min_lat = left
                        if min_lon is None or top < min_lon:
                            min_lon = top
                        if max_lat is None or right > max_lat:
                            max_lat = right
                        if max_lon is None or bottom > max_lon:
                            max_lon = bottom

                        n += 1

        # After all matching elements have been processed

        if None not in (min_lat, min_lon, max_lat, max_lon):
            lat = (min_lat + max_lat) / 2.0
            lon = (min_lon + max_lon) / 2.0

            # Fit the view
            level = self.map.best_zoom_from_bbox(min_lat=min_lat,
                                                 max_lat=max_lat,
                                                 min_lon=min_lon,
                                                 max_lon=max_lon)

            self.map.apply_zoom_level(level=level)
            self.map.go_to_position(latitude=lat, longitude=lon)
        else:
            pass

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
                       tau: Vec = None,
                       gen_p: Vec = None,
                       gen_q: Vec = None,
                       gen_names: np.ndarray | list[str] | None = None,
                       battery_p: Vec = None,
                       battery_q: Vec = None,
                       battery_names: np.ndarray | list[str] | None = None,
                       shunt_q: Vec = None,
                       shunt_names: np.ndarray | list[str] | None = None,
                       fluid_node_p2x_flow: Vec = None,
                       fluid_node_current_level: Vec = None,
                       fluid_node_spillage: Vec = None,
                       fluid_node_flow_in: Vec = None,
                       fluid_node_flow_out: Vec = None,
                       fluid_path_flow: Vec = None,
                       fluid_injection_flow: Vec = None,
                       t_idx: int | None = None,
                       use_flow_based_width: bool = False,
                       min_branch_width: int = 5,
                       max_branch_width=5,
                       min_bus_width=20,
                       max_bus_width=20,
                       cmap: palettes.Colormaps = None,
                       is_three_phase: bool = False):
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
        :param loading_label: String saying whatever the loading label means
        :param ma: branch phase shift angle (rad)
        :param tau: branch tap module (p.u.)
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
        :param is_three_phase: the results are three-phase
        """

        # voltage_cmap = viz.get_voltage_color_map()
        loading_cmap = viz.get_loading_color_map()
        video_export_active: bool = self.is_video_export_active()

        # nbus = self.circuit.get_bus_number()
        # longitudes = np.zeros(nbus)
        # latitudes = np.zeros(nbus)
        # nodes_dict = dict()
        # for i, bus in enumerate(self.circuit.buses):
        #
        #     # try to find the diagram object of the DB object
        #     graphic_object = self.graphics_manager.query(bus)
        #
        #     if graphic_object:
        #         longitudes[i] = bus.longitude
        #         latitudes[i] = bus.latitude
        #         nodes_dict[bus.name] = (bus.latitude, bus.longitude)

        arrow_size = self.diagram.arrow_size  # self.get_arrow_scale()

        # Try colouring the branches
        if self.circuit.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True):

            lnorm = np.abs(loadings)
            lnorm[lnorm == np.inf] = 0
            Sfabs = np.abs(Sf)
            Sfnorm = Sfabs / np.max(Sfabs + 1e-20)
            for i, branch in enumerate(self.circuit.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True)):

                # try to find the diagram object of the DB object
                graphic_object: Union[MapAcLine, MapDcLine] = self.graphics_manager.query(branch)

                if graphic_object:

                    # Tooltips are not visible in the export, so avoid rebuilding them per frame.
                    if video_export_active:
                        tooltip: str = ''
                    else:
                        tooltip = str(i) + ': ' + branch.name
                        tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(lnorm[i] * 100) + ' [%]'
                        if Sf is not None:
                            tooltip += '\nPower: ' + "{:10.4f}".format(Sf[i]) + ' [MVA]'
                        else:
                            pass
                        if losses is not None:
                            tooltip += '\nLosses: ' + "{:10.4f}".format(losses[i]) + ' [MVA]'
                        else:
                            pass

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
                            np.floor(min_branch_width + Sfnorm[i] * (max_branch_width - min_branch_width) * 0.1)
                        )
                        graphic_object.set_width_scale(width=weight, arrow_width=arrow_size)

                    graphic_object.set_colour(color=color, style=style, tool_tip=tooltip)

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
                        graphic_object.set_width_scale(width=weight, arrow_width=arrow_size)
                    else:
                        pass

                    if video_export_active:
                        tooltip = ''
                    else:
                        tooltip = str(i) + ': ' + graphic_object.api_object.name
                        tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(
                            abs(hvdc_loading[i]) * 100) + ' [%]'
                        tooltip += '\nPower (from):\t' + "{:10.4f}".format(hvdc_Pf[i]) + ' [MW]'
                        if hvdc_losses is not None:
                            tooltip += '\nPower (to):\t' + "{:10.4f}".format(hvdc_Pt[i]) + ' [MW]'
                            tooltip += '\nLosses: \t\t' + "{:10.4f}".format(hvdc_losses[i]) + ' [MW]'
                        else:
                            pass

                    if hvdc_losses is not None:
                        graphic_object.set_arrows_with_hvdc_power(Pf=float(hvdc_Pf[i]), Pt=float(hvdc_Pt[i]))
                    else:
                        graphic_object.set_arrows_with_hvdc_power(Pf=float(hvdc_Pf[i]), Pt=-hvdc_Pf[i])

                    graphic_object.set_colour(color=color, style=style, tool_tip=tooltip)

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
        self.gui.new_bus_branch_diagram_from_substation([substation])

    def copy(self) -> "GridMapWidget":
        """
        Deep copy of this widget
        :return: GridMapWidget
        """
        d_copy: MapDiagram = self.diagram.copy(
            obj_dict=self.circuit.get_all_elements_dict_by_type(add_locations=True)
        )
        d_copy.name = self.diagram.name + '_copy'

        return GridMapWidget(
            gui=self.gui,
            tile_src=self.map.tile_src,
            start_level=d_copy.start_level,
            longitude=d_copy.longitude,
            latitude=d_copy.latitude,
            name=d_copy.name,
            diagram=d_copy,
        )

    def consolidate_coordinates(self):
        """
        Consolidate the graphic elements' x, y coordinates into the API DB values
        """
        graphics_substations: List[SubstationGraphicItem] = self.graphics_manager.get_device_type_list(
            device_type=DeviceType.SubstationDevice)
        graphics_linelocations: List[LineLocationGraphicItem] = self.graphics_manager.get_device_type_list(
            device_type=DeviceType.LineLocation)

        for gelm in graphics_substations:
            gelm.api_object.latitude = gelm.lat
            gelm.api_object.longitude = gelm.lon

        for gelm in graphics_linelocations:
            gelm.api_object.lat = gelm.lat
            gelm.api_object.long = gelm.lon

        for inj_type in self.circuit.get_injections_device_types():
            graphics_injections: List[MapInjectionTemplateGraphicItem] = self.graphics_manager.get_device_type_list(
                device_type=inj_type)
            for gelm in graphics_injections:
                gelm.api_object.latitude = gelm.lat
                gelm.api_object.longitude = gelm.lon

        ok = yes_no_question(title=self.tr('Update lengths?'),
                             text=self.tr('Do you want to update lengths of lines? \n'
                                  'IMPORTANT: This will take into account every movement of substation and line '
                                  'locations. If you are unsure of the effects of this updating, click no and perform '
                                  'the individual length update in a new map or in the specific line.'))
        if ok:
            line_graphics_dict = self.graphics_manager.get_device_type_dict(DeviceType.LineDevice)

            for key, line_graphic in line_graphics_dict.items():
                line_graphic.calculate_total_length()

            self.gui.show_info_toast(message='Line lengths UPDATED')


        else:
            self.gui.show_info_toast(message='Line lengths NOT UPDATED')

    def reset_coordinates(self):
        """
        Consolidate the graphic elements' x, y coordinates into the API DB values
        """
        graphics_substations: List[SubstationGraphicItem] = self.graphics_manager.get_device_type_list(
            device_type=DeviceType.SubstationDevice)
        graphics_linelocations: List[LineLocationGraphicItem] = self.graphics_manager.get_device_type_list(
            device_type=DeviceType.LineLocation)

        for gelm in graphics_substations:
            gelm.move_to_api_coordinates(question=False)

        for gelm in graphics_linelocations:
            gelm.move_to_api_coordinates(question=False)

        # self.update()
        # self.refresh()

        # ok = yes_no_question(title='Update lengths?',
        #                      text='Do you want to update lengths of lines? \n'
        #                           'IMPORTANT: This will take into account the reseting of every substation and line  '
        #                           'location. If you are unsure of the effects of this updating, click no and perform '
        #                           'the individual length update in a new map or in the specific line.')
        # if ok:
        #     line_graphics_list = self.graphics_manager.graphic_dict[DeviceType.LineDevice]
        #
        #     for key, line_graphic in line_graphics_list.items():
        #         line_graphic.calculate_total_length()

        #     self.gui.show_info_toast(message='Line lengths UPDATED')
        #
        #
        # else:
        #     self.gui.show_info_toast(message='Line lengths NOT UPDATED')

    def plot_substation(self, i: int, api_object: Substation):
        """Open native injection-power and voltage tabs for one substation.

        :param i: Substation voltage result-column index.
        :param api_object: Substation represented by the selected map graphic.
        :return: None.
        """
        time_values = self.circuit.get_time_array()
        if time_values is not None and len(time_values) > 0:
            dialog_title: str = self.tr("{device_name} profiles plot").format(device_name=api_object.name)
            plot_dialogue: PlotDialogue = PlotDialogue(title=dialog_title, parent=self.gui)
            power_chart = plot_dialogue.chart
            plot_dialogue.set_current_tab_title(self.tr("Injections"))
            all_devices = self.circuit.get_injection_devices_grouped_by_substation()
            substation_devices = all_devices.get(api_object, None)
            power_names: list[str] = list()
            power_values: list[np.ndarray] = list()
            if substation_devices is not None:
                device_group: list
                for device_group in substation_devices.values():
                    device: object
                    for device in device_group:
                        profile_values: np.ndarray | None = None
                        if device.device_type == DeviceType.LoadDevice:
                            profile_values = -device.P_prof.toarray()
                        elif device.device_type == DeviceType.GeneratorDevice:
                            profile_values = device.P_prof.toarray()
                        elif device.device_type == DeviceType.ShuntDevice:
                            profile_values = -device.G_prof.toarray()
                        elif device.device_type == DeviceType.StaticGeneratorDevice:
                            profile_values = device.P_prof.toarray()
                        elif device.device_type == DeviceType.ExternalGridDevice:
                            profile_values = device.P_prof.toarray()
                        elif device.device_type == DeviceType.BatteryDevice:
                            profile_values = device.P_prof.toarray()
                        else:
                            pass
                        if profile_values is not None and len(profile_values) == len(time_values):
                            power_names.append(device.name)
                            power_values.append(np.asarray(profile_values, dtype=float))
                        else:
                            pass
            else:
                pass

            has_power_plot: bool = False
            if len(power_names) > 1:
                has_power_plot = plot_dialogue.set_cumulative_area_series(
                    x_values=time_values,
                    series_names=power_names,
                    series_values=power_values,
                    title=self.tr("Injection power"),
                    x_axis_title=self.tr("Time"),
                    y_axis_title=self.tr("Injections [MW]"),
                )
            elif len(power_names) == 1:
                has_power_plot = plot_dialogue.set_line_series(
                    x_values=time_values,
                    series_names=power_names,
                    series_values=power_values,
                    title=self.tr("Injection power"),
                    x_axis_title=self.tr("Time"),
                    y_axis_title=self.tr("Injections [MW]"),
                )
            else:
                pass

            voltage_chart = None
            has_voltage_plot: bool = False
            for driver, results in self.gui.session.drivers_results_iter():
                if isinstance(results, PowerFlowTimeSeriesResults):
                    voltage_table = results.mdl(result_type=ResultTypes.BusVoltageModule)
                    voltage_name: str = self.tr("Power flow")
                elif isinstance(results, OptimalPowerFlowTimeSeriesResults):
                    voltage_table = results.mdl(result_type=ResultTypes.BusVoltageModule)
                    voltage_name = self.tr("Optimal power flow")
                else:
                    voltage_table = None
                    voltage_name = ''
                if voltage_table is not None:
                    if voltage_chart is None:
                        if has_power_plot:
                            voltage_chart = plot_dialogue.add_tab(title=self.tr("Voltage"))
                        else:
                            voltage_chart = power_chart
                            plot_dialogue.set_current_tab_title(self.tr("Voltage"))
                    else:
                        pass
                    appended_voltage: bool = append_result_table_column(
                        chart=voltage_chart,
                        table=voltage_table,
                        column_index=i,
                        series_name=voltage_name,
                    )
                    if appended_voltage:
                        voltage_chart.setTitle(self.tr("Voltage"))
                        has_voltage_plot = True
                    else:
                        pass
                else:
                    pass

            if has_power_plot or has_voltage_plot:
                self.gui.register_open_plot_dialog(plot_dialogue)
                plot_dialogue.show()
            else:
                plot_dialogue.reject()
                self.gui.show_error_toast(self.tr("There are no finite time-series values to plot."))
        else:
            self.gui.show_error_toast(self.tr("There are no time series, so nothing to plot."))

    def transform_waypoint_to_substation(self):
        """

        :return:
        """
        selected_lineloc = self.get_selected_line_locations_tuple()

        if len(selected_lineloc) != 1:
            self.gui.show_error_toast('More than one waypoint selected. Could not determine where '
                                      'the substation should be created.')
            return

        ok = yes_no_question(title=self.tr('Transform waypoint to substation?'),
                             text=self.tr('Do you want to transform to substation the selected '
                                  'waypoint? This operation will split the line at the '
                                  'selected location, and will connect the new ends to '
                                  'the new substation.'))

        if ok:

            splitting_index = None

            line_graphic: MapAcLine = selected_lineloc[0][1].line_container
            line = line_graphic.api_object

            selected_waypoint = selected_lineloc[0][0]
            wp_graphic = selected_lineloc[0][1]

            for i, lineloc in enumerate(line.locations.data):
                if lineloc == selected_waypoint:
                    splitting_index = i
                    break
                else:
                    pass

            if splitting_index is not None:

                message = ''
                municipality = line.bus_from.substation.municipality
                region = line.bus_from.substation.region
                community = line.bus_from.substation.community
                country = line.bus_from.substation.country

                if country != line.bus_to.substation.country:
                    message += ('Country of the from and to buses does not match. Correct manually if the used '
                                'is not correct.\n')
                if community != line.bus_to.substation.community:
                    message += ('Community of the from and to buses does not match. Correct manually if the used '
                                'is not correct.\n')
                if region != line.bus_to.substation.region:
                    message += ('Region of the from and to buses does not match. Correct manually if the used '
                                'is not correct.\n')
                if municipality != line.bus_to.substation.municipality:
                    message += ('Municipality of the from and to buses does not match. Correct manually if the used '
                                'is not correct.')

                loc = line.locations.data[splitting_index]
                added_se = Substation(latitude=loc.lat, longitude=loc.long, region=region, community=community,
                                      municipality=municipality, country=country)
                added_se.color = '#0000FF'

                added_vl = VoltageLevel(Vnom=line.bus_from.Vnom, substation=added_se)
                added_bus = Bus(latitude=loc.lat, longitude=loc.long, voltage_level=added_vl,
                                substation=added_se, Vnom=added_vl.Vnom)

                linelocs1 = line.locations.data[:splitting_index]
                linelocs2 = line.locations.data[splitting_index + 1:]

                length1 = 0
                length2 = 0

                if len(linelocs1) == 0:

                    lat1 = line.bus_from.latitude
                    lon1 = line.bus_from.longitude
                    lat2 = added_bus.latitude
                    lon2 = added_bus.longitude
                    length1 += haversine_distance(lat1, lon1, lat2, lon2)

                else:

                    for i in range(len(linelocs1) + 1):
                        if i == 0:

                            lat1 = line.bus_from.latitude
                            lon1 = line.bus_from.longitude
                            lat2 = linelocs1[i].lat
                            lon2 = linelocs1[i].long
                            length1 += haversine_distance(lat1, lon1, lat2, lon2)

                        elif i == len(linelocs1):

                            lat1 = linelocs1[i - 1].lat
                            lon1 = linelocs1[i - 1].long
                            lat2 = added_bus.latitude
                            lon2 = added_bus.longitude
                            length1 += haversine_distance(lat1, lon1, lat2, lon2)

                        else:

                            lat1 = linelocs1[i - 1].lat
                            lon1 = linelocs1[i - 1].long
                            lat2 = linelocs1[i].lat
                            lon2 = linelocs1[i].long
                            length1 += haversine_distance(lat1, lon1, lat2, lon2)

                if len(linelocs2) == 0:

                    lat1 = added_bus.latitude
                    lon1 = added_bus.longitude
                    lat2 = line.bus_to.latitude
                    lon2 = line.bus_to.longitude
                    length2 += haversine_distance(lat1, lon1, lat2, lon2)

                else:

                    for i in range(len(linelocs2) + 1):
                        if i == 0:

                            lat1 = added_bus.latitude
                            lon1 = added_bus.longitude
                            lat2 = linelocs2[i].lat
                            lon2 = linelocs2[i].long
                            length2 += haversine_distance(lat1, lon1, lat2, lon2)

                        elif i == len(linelocs2):

                            lat1 = linelocs2[i - 1].lat
                            lon1 = linelocs2[i - 1].long
                            lat2 = line.bus_to.latitude
                            lon2 = line.bus_to.longitude
                            length2 += haversine_distance(lat1, lon1, lat2, lon2)

                        else:

                            lat1 = linelocs2[i - 1].lat
                            lon1 = linelocs2[i - 1].long
                            lat2 = linelocs2[i].lat
                            lon2 = linelocs2[i].long
                            length2 += haversine_distance(lat1, lon1, lat2, lon2)

                line1 = Line(name=line.name, code=line.code, bus_from=line.bus_from, bus_to=added_bus,
                             circuit_idx=line.circuit_idx, length=length1)
                line2 = Line(name=line.name, code=line.code, bus_from=added_bus, bus_to=line.bus_to,
                             circuit_idx=line.circuit_idx, length=length2)

                if line.template is not None:
                    line1.apply_template(line.template, Sbase=self.circuit.Sbase, freq=self.circuit.fBase)
                    line2.apply_template(line.template, Sbase=self.circuit.Sbase, freq=self.circuit.fBase)

                line1.color = line.color
                line2.color = line.color

                for i, loc in enumerate(linelocs1):
                    line1.locations.add(idtag=loc.idtag, latitude=loc.lat, longitude=loc.long, sequence=i, altitude=0)
                for i, loc in enumerate(linelocs2):
                    line2.locations.add(idtag=loc.idtag, latitude=loc.lat, longitude=loc.long, sequence=i, altitude=0)

                self.circuit.add_substation(added_se)
                self.circuit.add_voltage_level(added_vl)
                self.circuit.add_bus(added_bus)
                self.circuit.add_line(line1)
                self.circuit.add_line(line2)

                se_graphics = self.add_api_substation(api_object=added_se,
                                                      lat=added_se.latitude,
                                                      lon=added_se.longitude)
                vl_graphic = self.add_api_voltage_level(api_object=added_vl, substation_graphics=se_graphics)
                self.add_api_line(api_object=line1)
                self.add_api_line(api_object=line2)
                se_graphics.resize_voltage_levels()
                self.remove_element(device=line, graphic_object=line_graphic, delete_from_db=True)

                if message != '':
                    self.gui.show_warning_toast(message=message)

            else:
                self.gui.show_error_toast(
                    'The waypoint selected is not included in the selected line\'s waypoint. Operation not performed.')
                return

    def change_generator_bus_connection(self):

        selected_generators = self.get_selected_generators_tuple()
        selected_substations = self.get_selected_substations_tuple()

        if len(selected_substations) > 1:
            self.gui.show_error_toast('More than one substation has been selected to reconnect generators. '
                                      'Please, select only one.')
            return
        ss = selected_substations[0][0]

        dialog = BusSelectorDialogue(grid=self.circuit, se=ss)
        exec_dialog_safely(dialog=dialog)
        if dialog.is_valid():
            bus = dialog.bus()
            if bus is not None:
                for gen in selected_generators:
                    gen[0].bus = bus
            else:
                self.gui.show_error_toast('The selected bus appears as None. Check selection.')
                return

            self.gui.show_info_toast(f'Selected generators changed to bus {bus.name}.')
            return

        else:
            self.gui.show_error_toast('Dialogue selection failed.')

    def merge_selected_lines(self):

        selected_lines = self.get_selected_line_segments_tuple()

        if len(selected_lines) != 2:
            self.gui.show_error_toast('Line merging not done. Number of lines selected should be exactly equal to 2.')
            return

        line1 = selected_lines[0][0]
        line2 = selected_lines[1][0]
        line1_graphic: MapAcLine = selected_lines[0][1]
        line2_graphic: MapAcLine = selected_lines[1][1]

        if line1.template != line2.template:
            self.gui.show_error_toast('Line merging could not be done, lines have different templates. Check if that '
                                      'is correct, and apply the same template before trying again '
                                      'if you want to merge them.')
            return

        if ((line1.bus_from == line2.bus_from and line1.bus_to == line2.bus_to) or
                (line1.bus_from == line2.bus_to and line1.bus_to == line2.bus_from)):
            self.gui.show_error_toast('Line merging not done. The lines selected were parallel, this operation is not '
                                      'suitable.')
            return

        if line1.circuit_idx == line2.circuit_idx:
            circ_idx = line1.circuit_idx

        else:

            inpt = InputNumberDialogue(
                min_value=1,
                max_value=10,
                default_value=0,
                title=self.tr("Select circuit ID"),
                text=self.tr("Circuit ID"),
                is_int=True
            )

            exec_dialog_safely(dialog=inpt)

            if inpt.is_accepted:
                circ_idx = inpt.value
                if line1.template is not None:

                    if circ_idx > line1.template.n_circuits:
                        self.gui.show_error_toast(f'The circuit id introduced is greater than the maximum id that this '
                                                  f'template can use. The template has {line1.template.n_circuits}, the '
                                                  f'maximum possible value for the circuit_idx is '
                                                  f'{line1.template.n_circuits}, try again.')
                        return
                    else:
                        pass
                else:
                    pass

            else:
                self.gui.show_error_toast(f'Dialogue not accepted. Operation not performed.')
                return

        list_locations = line1.locations.data
        list_lineloc2 = line2.locations.data

        if line1.bus_from == line2.bus_from:

            bus_from = line1.bus_to
            bus_to = line2.bus_to
            joint_bus = line1.bus_from
            list_locations.reverse()

        elif line1.bus_from == line2.bus_to:

            bus_from = line1.bus_to
            bus_to = line2.bus_from
            joint_bus = line1.bus_from
            list_locations.reverse()
            list_lineloc2.reverse()

        elif line1.bus_to == line2.bus_from:

            bus_from = line1.bus_from
            bus_to = line2.bus_to
            joint_bus = line1.bus_to

        elif line1.bus_to == line2.bus_to:

            bus_from = line1.bus_from
            bus_to = line2.bus_from
            joint_bus = line1.bus_to
            list_lineloc2.reverse()

        else:
            self.gui.show_error_toast(
                'Line merging not done. The lines selected were not connected at any of its ends.')
            return

        osmids = line1.code
        osmids += ' ' + line2.code

        jll = 0
        for loc1 in list_locations:
            loc1.seq = jll
            jll += 1

        list_locations.append(LineLocation(lat=joint_bus.latitude, lon=joint_bus.longitude, seq=jll, z=0))

        jll += 1

        for loc2 in list_lineloc2:
            loc2.seq = jll
            list_locations.append(loc2)
            jll += 1

        new_line = Line(name=f'{line1.name} {line2.name}', code=osmids,
                        bus_from=bus_from, bus_to=bus_to,
                        length=line1.length + line2.length, circuit_idx=circ_idx)
        new_line.color = line1.color

        if line1.template is not None:
            new_line.apply_template(obj=line1.template, Sbase=self.circuit.Sbase, freq=self.circuit.fBase)

        previous_coordinates = [0, 0]

        for loc in list_locations:
            if [loc.lat, loc.long] != previous_coordinates:
                new_line.locations.add(idtag=loc.idtag,
                                       latitude=loc.lat,
                                       longitude=loc.long,
                                       sequence=loc.seq)
                previous_coordinates = [loc.lat, loc.long]
            else:
                pass

        self.circuit.add_line(new_line)

        self.remove_element(device=line1, graphic_object=line1_graphic, delete_from_db=True)
        self.remove_element(device=line2, graphic_object=line2_graphic, delete_from_db=True)

        self.add_api_line(api_object=new_line)

        self.gui.show_info_toast(message='Line merging successful!')

        ok = yes_no_question(
            text=self.tr('Do you want to delete the substation where the lines were connecting? This will'
                 ' open the substation deletion menu, with the information of the items that would '
                 'be removed.'), title=self.tr('Remove substation?'))
        if ok:
            merging_substation = self.graphics_manager.query(elm=joint_bus.substation)
            merging_substation.remove_function_from_schematic_and_db()

    def consolidate_object_coordinates(self):
        """

        :return:
        """
        selected_lines = self.get_selected_line_segments_tuple()
        selected_substations = self.get_selected_substations_tuple()
        selected_generators = self.get_selected_generators_tuple()
        line_graphics_list = []
        for subst, subst_graphic in selected_substations:
            subst.latitude = subst_graphic.lat
            subst.longitude = subst_graphic.lon

        for line, line_graphic in selected_lines:
            line_graphics_list.append(line_graphic)
            for gelm in line_graphic.nodes_list:
                gelm.api_object.lat = gelm.lat
                gelm.api_object.long = gelm.lon

        for gen, gen_graphic in selected_generators:
            gen.latitude = gen_graphic.lat
            gen.longitude = gen_graphic.lon

        ok = yes_no_question(title=self.tr('Update lengths?'),
                             text=self.tr('Do you want to update lengths of lines? \n'
                                  'IMPORTANT: This will take into account every movement of substation and line '
                                  'locations. If you are unsure of the effects of this updating, click no and perform '
                                  'the individual length update in a new map or in the specific line.'))
        if ok:

            for line_graphic in line_graphics_list:
                line_graphic.calculate_total_length()

            self.gui.show_info_toast(message='Line lengths UPDATED')


        else:
            self.gui.show_info_toast(message='Line lengths NOT UPDATED')

        return

    def split_line_to_substation(self):
        """
        Split a selected line and connect it to a selected substation.
        This creates two new lines: one from the original "from" bus to the selected substation,
        and another from the selected substation to the original "to" bus.
        The original line is removed.
        """

        # Find the line and substation in the selection
        selected_lines = self.get_selected_line_segments_tuple()
        selected_substations = self.get_selected_substations_tuple()

        if len(selected_lines) != 1 or len(selected_substations) != 1:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(self.tr("Please select exactly one line and one substation."))
            msg.setWindowTitle(self.tr("Selection Error"))
            exec_dialog_safely(dialog=msg)
            return

        # Get the API objects
        line_api, line_graphic = selected_lines[0]
        substation_api, substation_graphic = selected_substations[0]
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

        # If no suitable bus found, show an error message and return
        if suitable_bus is None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText(
                self.tr("No suitable voltage level ({voltage:.2f} kV) found in substation \"{substation_name}\".").format(
                    voltage=vnom,
                    substation_name=substation_api.name,
                )
            )
            msg.setInformativeText(
                self.tr("The line cannot be connected. Please ensure the target substation has a bus with a matching nominal voltage.")
            )
            msg.setWindowTitle(self.tr("Connection Error"))
            exec_dialog_safely(dialog=msg)
            return

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
            point, distance = closest_point_on_segment(
                lat1, lon1, lat2, lon2, substation_lat, substation_lon
            )

            if distance < min_distance:
                min_distance = distance
                closest_segment_idx = i
                closest_point = point

        # --- Unpack closest point coordinates ---
        closest_lat, closest_lon = closest_point
        extreme_point1 = waypoints[closest_segment_idx]
        extreme_point2 = waypoints[closest_segment_idx + 1]
        ex1_lat, ex1_lon = extreme_point1
        ex2_lat, ex2_lon = extreme_point2

        A1_lat = closest_lat - ex1_lat
        A1_lon = closest_lon - ex1_lon
        A2_lat = closest_lat - ex2_lat
        A2_lon = closest_lon - ex2_lon

        new_lat1 = ex1_lat + 0.95 * A1_lat
        new_lon1 = ex1_lon + 0.95 * A1_lon
        new_lat2 = ex2_lat + 0.95 * A2_lat
        new_lon2 = ex2_lon + 0.95 * A2_lon

        new_waypoint1 = (new_lat1, new_lon1)
        new_waypoint2 = (new_lat2, new_lon2)

        # Step 3: Calculate the lengths of the two new segments
        length1 = 0.0

        # Calculate length of first segment (from original start to insertion point)
        for i in range(closest_segment_idx):
            lat1, lon1 = waypoints[i]
            lat2, lon2 = waypoints[i + 1]
            length1 += haversine_distance(lat1, lon1, lat2, lon2)

        # Add distance from last waypoint to insertion point
        lat1, lon1 = waypoints[closest_segment_idx]
        lat2, lon2 = new_waypoint1
        length1 += haversine_distance(lat1, lon1, lat2, lon2)

        # Calculate length of second segment (from insertion point to original end)
        # First, add distance from insertion point to next waypoint
        lat1, lon1 = new_waypoint2
        lat2, lon2 = waypoints[closest_segment_idx + 1]
        length2 = haversine_distance(lat1, lon1, lat2, lon2)

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
        line1 = Line(name=f"{line_api.name}_1",
                     active=line_api.active,
                     bus_from=bus_from,
                     bus_to=suitable_bus,
                     code=line_api.code,
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
                     protection_rating_factor=line_api.protection_rating_factor,
                     circuit_idx=line_api.circuit_idx)

        # Line 2: from new bus to bus_to
        line2 = Line(name=f"{line_api.name}_2",
                     active=line_api.active,
                     bus_from=suitable_bus,
                     bus_to=bus_to,
                     code=line_api.code,
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
                     protection_rating_factor=line_api.protection_rating_factor,
                     circuit_idx=line_api.circuit_idx)

        if line_api.template is not None:
            line1.apply_template(line_api.template, Sbase=self.circuit.Sbase, freq=self.circuit.fBase)
            line2.apply_template(line_api.template, Sbase=self.circuit.Sbase, freq=self.circuit.fBase)

        # Copy other properties from the original line
        line1.color = line_api.color

        # Copy other properties from the original line
        line2.color = line_api.color

        # Preserve waypoints for line 1 (from start to insertion point)
        # Add all waypoints from the original line up to the closest segment
        for i in range(1, closest_segment_idx + 1):
            line1.locations.add_location(lat=waypoints[i][0], long=waypoints[i][1], alt=0.0)

        # --- Assign offset waypoints ---
        # Add the 'backwards' point as the last waypoint for line1
        line1.locations.add_location(lat=new_lat1, long=new_lon1, alt=0.0)
        # line1.locations.add_location(lat=substation_lat, long=substation_lon, alt=0.0)

        # Add the 'forwards' point as the first waypoint for line2
        # line2.locations.add_location(lat=substation_lat, long=substation_lon, alt=0.0)
        line2.locations.add_location(lat=new_lat2, long=new_lon2, alt=0.0)

        # Preserve waypoints for line 2 (from insertion point to end)
        # Store waypoints from the segment *after* the split onwards
        for i in range(closest_segment_idx + 1, len(waypoints) - 1):
            line2.locations.add_location(lat=waypoints[i][0], long=waypoints[i][1], alt=0.0)

        # Add the new lines to the circuit
        self.circuit.add_line(line1)
        self.circuit.add_line(line2)

        # Add the new lines to the map
        line1_graphic = self.add_api_line(line1)
        line2_graphic = self.add_api_line(line2)

        # Remove the original line from the circuit and map
        # Ensure we delete the correct graphic container
        # self.remove_branch_graphic(line=original_line_container, delete_from_db=True)
        self.remove_element(device=line_api, graphic_object=original_line_container, delete_from_db=True)
        # Recalculate lengths based on new waypoints

        line1_graphic.calculate_total_length()
        line2_graphic.calculate_total_length()

        self.gui.show_info_toast(
            f'{line1.name} ({line1.length:.3f}km) and {line2.name} ({line2.length:.3f}km) created. {line_api.name} removed.'
        )


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
        list_sel_substations = self.get_selected_substations_tuple()
        list_sel_waypoint = self.get_selected_line_locations_tuple()

        # Check if we have a substation and a waypoint selected
        if len(list_sel_substations) != 1 or len(list_sel_waypoint) != 1:
            self.gui.show_error_toast(message="Please select exactly one substation and one waypoint.")
            return

        selected_waypoint = list_sel_waypoint[0][1]
        # Get the line container from the waypoint
        original_line_container = list_sel_waypoint[0][1].line_container
        line_api = original_line_container.api_object
        if not isinstance(line_api, Line):
            self.gui.show_error_toast(message="The selected waypoint does not belong to an AC line.")
            return
        else:
            pass
        line_code_text: str = line_api.code if isinstance(line_api.code, str) else ""

        # Get the API objects
        substation_api, substation_graphic = list_sel_substations[0]

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
            self.gui.show_error_toast(message="Selected waypoint not found in the line's waypoints.")
            return

        # Step 1: Create a new substation at the waypoint location
        new_substation_name = f"{line_api.name}_Junction"

        # --- Safely evaluate line_api.code ---
        code_list = []  # Default to empty list
        if line_code_text:
            try:
                evaluated_code = ast.literal_eval(line_code_text)
                # Ensure it's a list or treat as single item if string
                if isinstance(evaluated_code, list):
                    code_list = evaluated_code
                elif isinstance(evaluated_code, str):
                    code_list = [evaluated_code]  # Treat literal string as single code
                # Add handling for other literal types if needed, otherwise they result in empty list
            except (ValueError, SyntaxError, TypeError):
                # Handle cases where the string is not a valid literal
                # If it doesn't look like a list, treat the original string as the code
                if not line_code_text.strip().startswith('[') and not line_code_text.strip().endswith(']'):
                    code_list = [line_code_text]

        # Modify the code list
        new_code_list = [f"{subcode}_Junction" for subcode in code_list]
        # --- End safe evaluation ---

        # Create the new substation
        new_substation = Substation(name=new_substation_name,
                                    code=str(new_code_list),  # Store as string representation of list
                                    latitude=waypoint_lat,
                                    longitude=waypoint_lon)
        new_substation.color = '#6495ED'
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
            for vl_graphic in substation_graphic.voltage_level_graphics:
                if abs(vl_graphic.api_object.Vnom - vnom) < 0.01:
                    voltage_level_in_selected = vl_graphic.api_object
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

        # --- Safely evaluate line_api.code for line1 ---
        code_list_for_line1 = []  # Default to empty list
        if line_code_text:
            try:
                evaluated_code = ast.literal_eval(line_code_text)
                if isinstance(evaluated_code, list):
                    code_list_for_line1 = evaluated_code
                elif isinstance(evaluated_code, str):
                    code_list_for_line1 = [evaluated_code]
            except (ValueError, SyntaxError, TypeError):
                if not line_code_text.strip().startswith('[') and not line_code_text.strip().endswith(']'):
                    code_list_for_line1 = [line_code_text]

        # Modify the code list
        line1_modified_code_list = [f"{subcode}_1" for subcode in code_list_for_line1]
        # --- End safe evaluation for line1 ---

        line1 = Line(name=line1_name,
                     bus_from=line_api.bus_from,
                     bus_to=new_bus,
                     code=str(line1_modified_code_list),  # Store as string representation
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
                     protection_rating_factor=line_api.protection_rating_factor,
                     circuit_idx=line_api.circuit_idx,
                     active=line_api.active)
        line1.color = line_api.color

        # Preserve waypoints for line 1 (from start to waypoint)
        # Add all waypoints from the original line up to the waypoint
        for i in range(waypoint_idx):
            if i < len(original_line_container.nodes_list):
                node = original_line_container.nodes_list[i]
                line1.locations.add_location(lat=node.lat, long=node.lon, alt=0.0)

        # Line 2: from new_bus to original bus_to
        line2_name = f"{line_api.name}_2"

        # --- Safely evaluate line_api.code for line2 ---
        code_list_for_line2 = []  # Default to empty list
        if line_code_text:
            try:
                evaluated_code = ast.literal_eval(line_code_text)
                if isinstance(evaluated_code, list):
                    code_list_for_line2 = evaluated_code
                elif isinstance(evaluated_code, str):
                    code_list_for_line2 = [evaluated_code]
            except (ValueError, SyntaxError, TypeError):
                if not line_code_text.strip().startswith('[') and not line_code_text.strip().endswith(']'):
                    code_list_for_line2 = [line_code_text]

        # Modify the code list
        line2_modified_code_list = [f"{subcode}_2" for subcode in code_list_for_line2]
        # --- End safe evaluation for line2 ---

        line2 = Line(name=line2_name,
                     bus_from=new_bus,
                     bus_to=line_api.bus_to,
                     code=str(line2_modified_code_list),  # Store as string representation
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
                     protection_rating_factor=line_api.protection_rating_factor,
                     circuit_idx=line_api.circuit_idx,
                     active=line_api.active)

        if line_api.template is not None:
            line1.apply_template(line_api.template, Sbase=self.circuit.Sbase, freq=self.circuit.fBase)
            line2.apply_template(line_api.template, Sbase=self.circuit.Sbase, freq=self.circuit.fBase)

        line2.color = line_api.color

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
                               protection_rating_factor=line_api.protection_rating_factor,
                               circuit_idx=line_api.circuit_idx,
                               active=line_api.active)

        if line_api.template is not None:
            connection_line.apply_template(line_api.template, Sbase=self.circuit.Sbase, freq=self.circuit.fBase)

        connection_line.color = line_api.color

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

        # Explicitly delete the waypoint graphic from the scene to prevent artifact
        self._remove_from_scene(selected_waypoint)

        # Remove the original line
        self.remove_element(device=line_api, graphic_object=original_line_container, delete_from_db=True)
        # self.remove_branch_graphic(line=original_line_container, delete_from_db=True)

        # Notify the user
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(
            self.tr("T-joint connection created between {substation_name} and {line_name}.").format(
                substation_name=substation_api.name,
                line_name=line_api.name,
            )
        )
        msg.setInformativeText(
            self.tr("Waypoint replaced with new substation '{substation_name}'.\n"
                    "Original line split into two segments:\n"
                    "- {line1_name}: {length1:.2f} km\n"
                    "- {line2_name}: {length2:.2f} km\n"
                    "New connection line: {distance:.2f} km").format(
                substation_name=new_substation.name,
                line1_name=line1.name,
                line2_name=line2.name,
                length1=length1,
                length2=length2,
                distance=distance,
            )
        )
        msg.setWindowTitle(self.tr("Operation Successful"))
        exec_dialog_safely(dialog=msg)

    def change_line_connection(self):

        selected_lines = self.get_selected_line_segments_tuple()
        selected_substations = self.get_selected_substations_tuple()

        if len(selected_lines) != 1 or len(selected_substations) != 2:
            self.gui.show_error_toast(message="Please select exactly one line and two substations.")
            return

        # Get the API objects
        line_api, line_graphic = selected_lines[0]
        substation_api_1, substation_graphic_1 = selected_substations[0]
        substation_api_2, substation_graphic_2 = selected_substations[1]

        # Get the original buses
        bus_from = line_api.bus_from
        bus_from_idtag_0 = bus_from.idtag
        bus_to = line_api.bus_to
        bus_to_idtag_0 = bus_to.idtag

        buses1 = self.circuit.get_substation_buses(substation=substation_api_1)
        buses2 = self.circuit.get_substation_buses(substation=substation_api_2)

        if substation_api_1.idtag == bus_from.substation.idtag:
            removed_substation = substation_api_1.name
            added_substation = substation_api_2.name
            for bus in buses2:
                if bus.Vnom == bus_from.Vnom:
                    line_api.bus_from = bus
                    break
            if bus_from_idtag_0 == line_api.bus_from.idtag:
                self.gui.show_error_toast(message="The new substation did not have any valid bus to connect the line.")
                return

        elif substation_api_1.idtag == bus_to.substation.idtag:
            removed_substation = substation_api_1.name
            added_substation = substation_api_2.name
            for bus in buses2:
                if bus.Vnom == bus_to.Vnom:
                    line_api.bus_to = bus
                    break
            if bus_to_idtag_0 == line_api.bus_to.idtag:
                self.gui.show_error_toast(message="The new substation did not have any valid bus to connect the line.")
                return


        elif substation_api_2.idtag == bus_from.substation.idtag:
            removed_substation = substation_api_2.name
            added_substation = substation_api_1.name
            for bus in buses1:
                if bus.Vnom == bus_from.Vnom:
                    line_api.bus_from = bus
                    break
            if bus_from_idtag_0 == line_api.bus_from.idtag:
                self.gui.show_error_toast(message="The new substation did not have any valid bus to connect the line.")
                return

        elif substation_api_2.idtag == bus_to.substation.idtag:
            removed_substation = substation_api_2.name
            added_substation = substation_api_1.name
            for bus in buses1:
                if bus.Vnom == bus_to.Vnom:
                    line_api.bus_to = bus
                    break
            if bus_to_idtag_0 == line_api.bus_to.idtag:
                self.gui.show_error_toast(message="The new substation did not have any valid bus to connect the line.")
                return

        else:
            self.gui.show_error_toast(message="None of the selected substations are related to the line.")
            return

        # Remove past graphic item and add the new one

        self.remove_element(device=line_api, graphic_object=line_graphic, delete_from_db=False)
        line = self.add_api_line(api_object=line_api)
        line.calculate_total_length()

        self.gui.show_info_toast(
            f"Line {line_api.name} had its connection to substation {removed_substation} changed to substation "
            f"{added_substation}.")


def generate_map_diagram(
        substations: List[Substation],
        voltage_levels: List[VoltageLevel],
        lines: List[Line],
        dc_lines: List[DcLine],
        hvdc_lines: List[HvdcLine],
        fluid_nodes: List[FluidNode],
        fluid_paths: List[FluidPath],
        generators: List[Generator],
        batteries: List[Battery],
        loads: List[Load],
        static_generators: List[StaticGenerator],
        external_grids: List[ExternalGrid],
        prog_func: Union[Callable, None] = None,
        text_func: Union[Callable, None] = None,
        name='Map diagram',
        use_flow_based_width: bool = False,
        min_branch_width: int = 1.0,
        max_branch_width=5,
        min_bus_width=1.0,
        max_bus_width=20,
        arrow_size=20,
        palette: Colormaps = Colormaps.VeraGrid,
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
    :param external_grids:
    :param static_generators:
    :param loads:
    :param batteries:
    :param generators:
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
    for i, elm in enumerate(substations):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        diagram.set_point(device=elm, location=MapLocation(latitude=elm.latitude,
                                                           longitude=elm.longitude,
                                                           api_object=elm))

    # --------------------------------------------------------------------------------------------------------------

    if text_func is not None:
        text_func('Creating schematic injections')

    for lst in [generators, batteries, loads, static_generators, external_grids]:
        nn = len(lst)
        for i, elm in enumerate(lst):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            lon, lat = elm.try_to_find_coordinates()
            diagram.set_point(device=elm, location=MapLocation(latitude=lat,
                                                               longitude=lon,
                                                               api_object=elm))

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


def generate_map_diagram2(circuit: MultiCircuit):
    return generate_map_diagram(
        substations=circuit.get_substations(),
        voltage_levels=circuit.get_voltage_levels(),
        lines=circuit.get_lines(),
        dc_lines=circuit.get_dc_lines(),
        hvdc_lines=circuit.get_hvdc(),
        fluid_nodes=circuit.get_fluid_nodes(),
        fluid_paths=circuit.get_fluid_paths(),
        external_grids=circuit.external_grids,
        static_generators=circuit.static_generators,
        loads=circuit.loads,
        batteries=circuit.batteries,
        generators=circuit.generators,
        prog_func=None,
        text_func=None,
        name='Map diagram',
        use_flow_based_width=False,
        min_branch_width=0.01,
        max_branch_width=0.02,
        min_bus_width=0.1,
        max_bus_width=0.2,
        arrow_size=0.015,
        palette=Colormaps.VeraGrid,
        default_bus_voltage=20
    )
