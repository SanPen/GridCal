# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import sys
import os
import numpy as np
import shiboken6
from typing import Any, List, Set, Dict, Union, Tuple, TYPE_CHECKING, Iterable, TypeVar
from collections.abc import Callable
from collections import defaultdict
from warnings import warn

from PySide6.QtCore import (Qt, QPoint, QSize, QPointF, QRect, QRectF, QMimeData, QIODevice, QByteArray,
                            QDataStream, QModelIndex, QTimer, QCoreApplication)
from PySide6.QtGui import (QIcon, QPixmap, QImage, QPainter, QStandardItemModel, QStandardItem, QColor, QPen, QBrush,
                           QDragEnterEvent, QDragMoveEvent, QDropEvent, QWheelEvent, QKeyEvent, QMouseEvent,
                           QContextMenuEvent)
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsSceneMouseEvent, QGraphicsItem)
from PySide6.QtSvg import QSvgGenerator

from VeraGridEngine.Devices.types import ALL_DEV_TYPES, INJECTION_DEVICE_TYPES, FLUID_TYPES, BRANCH_TYPES
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Branches.upfc import UPFC
from VeraGridEngine.Devices.Branches.switch import Switch
from VeraGridEngine.Devices.Branches.series_reactance import SeriesReactance
from VeraGridEngine.Devices.Branches.hvdc_line import HvdcLine
from VeraGridEngine.Devices.Branches.transformer3w import Transformer3W, Winding
from VeraGridEngine.Devices.Branches.transformerNw import TransformerNW
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.battery import Battery
from VeraGridEngine.Devices.Injections.controllable_shunt import ControllableShunt
from VeraGridEngine.Devices.Injections.static_generator import StaticGenerator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.external_grid import ExternalGrid
from VeraGridEngine.Devices.Injections.current_injection import CurrentInjection
from VeraGridEngine.Devices.Fluid import FluidNode, FluidPath
from VeraGridEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from VeraGridEngine.Devices.Diagrams.graphic_location import GraphicLocation
from VeraGridEngine.Topology.VoltageLevels.vl_creation_common_functions import transform_bus_to_connectivity_grid
from VeraGridEngine.enumerations import DeviceType, BusGraphicType, SchematicAutoRouteStyle
from VeraGridEngine.basic_structures import Vec, CxVec, IntVec, Logger
import VeraGridEngine.Devices.Diagrams.palettes as palettes
from VeraGridEngine.Topology.VoltageLevels import vl_creation_common_functions as substation_wizards
from VeraGridEngine.enumerations import TerminalType

from VeraGrid.Gui.SubstationDesigner.voltage_level_conversion import VoltageLevelConversionWizard
from VeraGrid.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, RoundTerminalItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem, INJECTION_GRAPHICS
from VeraGrid.Gui.Diagrams.SchematicWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Fluid.fluid_path_graphics import FluidPathGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.line_graphics import LineGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.winding_graphics import WindingGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.dc_line_graphics import DcLineGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.transformer2w_graphics import TransformerGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.hvdc_graphics import HvdcGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.vsc_graphics_3term import VscGraphicItem3Term
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.vsc_graphics import VscGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.upfc_graphics import UpfcGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.series_reactance_graphics import SeriesReactanceGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.switch_graphics import SwitchGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.transformer3w_graphics import Transformer3WGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.transformerNw_graphics import TransformerNWGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.generator_graphics import GeneratorGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from VeraGrid.Gui.Diagrams.generic_graphics import ACTIVE, GenericDiagramWidget
from VeraGrid.Gui.Diagrams.graphics_manager import ALL_GRAPHICS
from VeraGrid.Gui.Diagrams.base_diagram_widget import BaseDiagramWidget
from VeraGrid.Gui.general_dialogues import InputNumberDialogue
from VeraGrid.Gui.dialog_lifecycle import exec_dialog_safely
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.PlotDialogue.qt_chart_widget import GraphsWidget
import VeraGrid.Gui.Visualization.visualization as viz
from VeraGrid.Gui.messages import error_msg, warning_msg, yes_no_question
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_auto_layout import (
    calculate_schematic_layout,
    should_auto_layout_before_first_draw,
    apply_initial_auto_layout_to_diagram,
)

if TYPE_CHECKING:
    from VeraGrid.Gui.Main.SubClasses.Model.diagrams import DiagramsMain
    from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI

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

SCHEMATIC_BRANCH_DEVICE_TYPES: Tuple[DeviceType, ...] = (
    DeviceType.LineDevice,
    DeviceType.DCLineDevice,
    DeviceType.HVDCLineDevice,
    DeviceType.VscDevice,
    DeviceType.UpfcDevice,
    DeviceType.Transformer2WDevice,
    DeviceType.SeriesReactanceDevice,
    DeviceType.SwitchDevice,
    DeviceType.WindingDevice,
    DeviceType.FluidPathDevice,
)

OPTIONAL_PORT = Union[BarTerminalItem, RoundTerminalItem, None]
TERMINAL_OWNER_GRAPHICS = BusGraphicItem | FluidNodeGraphicItem
_GRAPHIC_T = TypeVar("_GRAPHIC_T")
_LINE_GRAPHIC_T = TypeVar("_LINE_GRAPHIC_T", bound=LineGraphicTemplateItem)


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

        self.add(name=QCoreApplication.translate("SchematicLibraryModel", "Bus"),
                 device_type=DeviceType.BusBarDevice,
                 icon_name="bus_icon")
        self.add(name=QCoreApplication.translate("SchematicLibraryModel", "Connectivity bus"),
                 device_type=DeviceType.BusDevice,
                 icon_name="cn_icon")
        self.add(name=QCoreApplication.translate("SchematicLibraryModel", "3W-Transformer"),
                 device_type=DeviceType.Transformer3WDevice,
                 icon_name="transformer3w")
        self.add(name=QCoreApplication.translate("SchematicLibraryModel", "NW-Transformer"),
                 device_type=DeviceType.TransformerNwDevice,
                 icon_name="transformerNw")
        self.add(name=QCoreApplication.translate("SchematicLibraryModel", "Fluid-node"),
                 device_type=DeviceType.FluidNodeDevice,
                 icon_name="dam")
        self.add(name=QCoreApplication.translate("SchematicLibraryModel", "VSC"),
                 device_type=DeviceType.VscDevice,
                 icon_name="to_vsc")

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
            "SchematicLibraryModel",
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

                if device_type == DeviceType.BusBarDevice:
                    name = QCoreApplication.translate("SchematicLibraryModel", "Bus")
                elif device_type == DeviceType.BusDevice:
                    name = QCoreApplication.translate("SchematicLibraryModel", "Connectivity bus")
                elif device_type == DeviceType.Transformer3WDevice:
                    name = QCoreApplication.translate("SchematicLibraryModel", "3W-Transformer")
                elif device_type == DeviceType.TransformerNwDevice:
                    name = QCoreApplication.translate("SchematicLibraryModel", "NW-Transformer")
                elif device_type == DeviceType.FluidNodeDevice:
                    name = QCoreApplication.translate("SchematicLibraryModel", "Fluid-node")
                elif device_type == DeviceType.VscDevice:
                    name = QCoreApplication.translate("SchematicLibraryModel", "VSC")
                else:
                    name = item.text()

                item.setText(name)
                item.setToolTip(QCoreApplication.translate(
                    "SchematicLibraryModel",
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

    def get_bus_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(DeviceType.BusBarDevice.name)

    def get_3w_transformer_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(DeviceType.Transformer3WDevice.name)

    def get_nw_transformer_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(DeviceType.TransformerNwDevice.name)

    def get_fluid_node_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(DeviceType.FluidNodeDevice.name)

    def get_connectivity_node_mime_data(self) -> QByteArray:
        """

        :return:
        """
        return self.to_bytes_array(DeviceType.BusDevice.name)

    def mimeTypes(self) -> List[str]:
        """

        @return:
        """
        return ['component/name']

    def get_vsc_mime_data(self) -> QByteArray:
        """
        Get mime data for VSC.
        :return:
        """
        return self.to_bytes_array(DeviceType.VscDevice.name)

    def mimeData(self, idxs: List[QModelIndex]) -> QMimeData:
        """

        @param idxs:
        @return:
        """
        mimedata = QMimeData()
        for idx in idxs:
            if idx.isValid():
                device_type = self.data(idx, Qt.ItemDataRole.UserRole)

                if isinstance(device_type, DeviceType):
                    data = QByteArray()
                    stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
                    stream.writeQString(device_type.name)

                    mimedata.setData('component/name', data)
                else:
                    pass
            else:
                pass
        return mimedata

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """
        
        :param index: 
        :return: 
        """
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled


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
        self.parent_.persist_selected_item_positions()


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
        self.drag_mode = QGraphicsView.DragMode.ScrollHandDrag
        self.setDragMode(self.drag_mode)
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)
        self.setMouseTracking(True)
        self.setInteractive(True)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    @staticmethod
    def get_drag_mode_for_modifiers(modifiers: Qt.KeyboardModifiers) -> QGraphicsView.DragMode:
        """
        Resolve the view drag mode for the current keyboard modifiers.

        The default interaction should pan the schematic, while holding
        ``Ctrl`` should temporarily switch to rubber-band selection.

        :param modifiers: Active keyboard modifiers.
        :return: Matching graphics-view drag mode.
        """
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            return QGraphicsView.DragMode.RubberBandDrag
        else:
            return QGraphicsView.DragMode.ScrollHandDrag

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Mouse press event
        :param event: QMouseEvent
        """
        self.drag_mode = self.get_drag_mode_for_modifiers(event.modifiers())

        self.setDragMode(self.drag_mode)

        # process the rest of the events
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """

        :param event:
        :return:
        """
        super().contextMenuEvent(event)


def is_bus_terminal(arriving_widget: Union[BarTerminalItem, RoundTerminalItem, QGraphicsItem]) -> bool:
    """
    Check if the terminal is a bus terminal
    :param arriving_widget:
    :return: True / False
    """
    if isinstance(arriving_widget, BusGraphicItem):
        return True
    else:
        return isinstance(arriving_widget.parent, BusGraphicItem)


def is_tr3_terminal(arriving_widget: Union[BarTerminalItem, RoundTerminalItem, QGraphicsItem]) -> bool:
    """
    Check if the terminal is a 3-winding transformer terminal
    :param arriving_widget:
    :return: True / False
    """
    return isinstance(arriving_widget.parent, (Transformer3WGraphicItem, TransformerNWGraphicItem))


def is_vsc3_terminal(arriving_widget: Union[BarTerminalItem, RoundTerminalItem, QGraphicsItem]) -> bool:
    """
    Check if the terminal is a 3-terminal VSC terminal
    :param arriving_widget:
    :return: True / False
    """
    return isinstance(arriving_widget.parent, VscGraphicItem3Term)


def _hide_zero_result_value(value: float) -> float | None:
    """
    Hide exact zeros so result badges only show meaningful channels.

    :param value: Resolved channel value.
    :return: ``None`` for zero, else the original value.
    """
    if value == 0.0:
        return None
    else:
        return value


def _get_injection_result_index(device_name: str,
                                fallback_index: int,
                                lookup: dict[str, int]) -> int:
    """
    Resolve one device result index, preferring the engine-provided name mapping.

    :param device_name: Device name to look up.
    :param fallback_index: Local device order fallback.
    :param lookup: Result name lookup.
    :return: Resolved result index.
    """
    normalized_name: str = str(device_name).strip()

    if normalized_name:
        return lookup.get(normalized_name, fallback_index)
    else:
        return fallback_index


def _get_branch_result_index(branch_index: int,
                             phase_index: int,
                             values: Vec | CxVec | None,
                             is_three_phase: bool) -> int:
    """
    Resolve the right index for branch-like result arrays.

    Three-phase flows are flattened per phase, but some companion arrays such as
    transformer taps are still stored once per branch.
    """
    if values is None or not is_three_phase:
        return branch_index

    if len(values) % 3 == 0 and len(values) > branch_index:
        branch_count = len(values) // 3
        if branch_count > branch_index:
            return 3 * branch_index + phase_index

    return branch_index


def _has_single_phase_explicit_injection_results(gen_p: Vec | None,
                                                 gen_q: Vec | None,
                                                 battery_p: Vec | None,
                                                 battery_q: Vec | None,
                                                 shunt_q: Vec | None) -> bool:
    """
    Tell whether the active study exported explicit single-phase injection results.

    :param gen_p: Generator active powers.
    :param gen_q: Generator reactive powers.
    :param battery_p: Battery active powers.
    :param battery_q: Battery reactive powers.
    :param shunt_q: Shunt-like reactive powers.
    :return: ``True`` when at least one explicit injection result channel is present.
    """
    # Dynamic and fallback colouring paths can reuse ``colour_results()``
    # without providing any per-device injection arrays. In those cases the
    # GUI must clear stale overlays and stop, otherwise profile-backed
    # setpoints get painted as if they were simulation results.
    if gen_p is not None or gen_q is not None:
        return True
    else:
        pass

    if battery_p is not None or battery_q is not None:
        return True
    else:
        pass

    if shunt_q is not None:
        return True
    else:
        return False


def _has_three_phase_explicit_injection_results(gen_q_a: Vec | None,
                                                gen_q_b: Vec | None,
                                                gen_q_c: Vec | None,
                                                battery_q_a: Vec | None,
                                                battery_q_b: Vec | None,
                                                battery_q_c: Vec | None,
                                                shunt_q_a: Vec | None,
                                                shunt_q_b: Vec | None,
                                                shunt_q_c: Vec | None) -> bool:
    """
    Tell whether the active study exported explicit three-phase injection results.

    :param gen_q_a: Generator phase-a reactive powers.
    :param gen_q_b: Generator phase-b reactive powers.
    :param gen_q_c: Generator phase-c reactive powers.
    :param battery_q_a: Battery phase-a reactive powers.
    :param battery_q_b: Battery phase-b reactive powers.
    :param battery_q_c: Battery phase-c reactive powers.
    :param shunt_q_a: Shunt-like phase-a reactive powers.
    :param shunt_q_b: Shunt-like phase-b reactive powers.
    :param shunt_q_c: Shunt-like phase-c reactive powers.
    :return: ``True`` when at least one explicit 3-phase injection result channel is present.
    """
    if gen_q_a is not None or gen_q_b is not None or gen_q_c is not None:
        return True
    else:
        pass

    if battery_q_a is not None or battery_q_b is not None or battery_q_c is not None:
        return True
    else:
        pass

    if shunt_q_a is not None or shunt_q_b is not None or shunt_q_c is not None:
        return True
    else:
        return False


def _get_injection_result_color(graphic_object: InjectionTemplateGraphicItem) -> QColor:
    """
    Get the result overlay color for an injection graphic.

    :param graphic_object: Injection graphic item.
    :return: Overlay color.
    """
    parent_graphic = graphic_object.parent
    color: QColor = ACTIVE['color']

    # Use the host bus color when available so the overlay remains visually tied to the node state.
    if isinstance(parent_graphic, BusGraphicItem):
        if parent_graphic.tile is None:
            color = parent_graphic.terminal.brush().color()
        else:
            color = parent_graphic.tile.brush().color()
    else:
        pass

    return color


def _get_optional_result_value(values: Vec | None,
                               index: int) -> float | None:
    """
    Read one optional result channel safely.

    :param values: Optional result vector.
    :param index: Requested index.
    :return: Float value when present, else ``None``.
    """
    if values is not None and index < len(values):
        return float(values[index])
    else:
        return None


def _apply_single_phase_injection_result(graphic_object: InjectionTemplateGraphicItem,
                                         device_name: str,
                                         tooltip_title: str,
                                         p_value: float | None,
                                         q_value: float | None) -> None:
    """
    Apply a single-phase result badge to an injection graphic.

    :param graphic_object: Injection graphic item.
    :param device_name: Injection device name.
    :param tooltip_title: Tooltip title.
    :param p_value: Active power value.
    :param q_value: Reactive power value.
    :return: ``None``.
    """
    if p_value is None and q_value is None:
        pass
    else:
        color: QColor = _get_injection_result_color(graphic_object=graphic_object)
        lines: list[str] = list()

        # Only show channels that are present in the resolved result for this device.
        if p_value is None:
            pass
        else:
            lines.append(f"P {p_value:+.1f} MW")

        if q_value is None:
            pass
        else:
            lines.append(f"Q {q_value:+.1f} MVAr")

        tooltip_lines: list[str] = [device_name, tooltip_title]
        tooltip_lines.extend(lines)
        graphic_object.set_result_visuals(lines=lines,
                                          tooltip="\n".join(tooltip_lines),
                                          color=color)


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
                 gui: VeraGridMainGUI | DiagramsMain,
                 diagram: SchematicDiagram,
                 default_bus_voltage: float = 10.0,
                 time_index: Union[None, int] = None):
        """
        Creates the Diagram Editor (DiagramEditorWidget)
        :param diagram: SchematicDiagram to use (optional)
        :param default_bus_voltage: Default bus voltages (kV)
        :param time_index: time index to represent
        """

        BaseDiagramWidget.__init__(self,
                                   gui=gui,
                                   diagram=diagram,
                                   library_model=SchematicLibraryModel(),
                                   time_index=time_index)

        # create all the schematic objects and replace the existing ones
        self.diagram_scene = SchematicScene(parent=self)  # scene to add to the QGraphicsView

        # add the actual editor
        self.editor_graphics_view = CustomGraphicsView(self.diagram_scene, parent=self)
        self.register_video_time_label_canvas(view=self.editor_graphics_view)

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

        # nodes distance "explosion" factor
        self.expand_factor = 1.1

        # Scale the view / do the zoom
        self.scale_factor = 1.15  # 1.15
        self.zoom_angle_step: float = 120.0
        self.zoom_pixel_step: float = 240.0
        self.zoom_max_event_steps: float = 1.0

        # Zoom indicator
        self._zoom = 0

        # line drawing vars
        self.started_branch: Union[LineGraphicTemplateItem, None] = None
        self.setMouseTracking(True)
        self.startPos = QPoint()
        self.newCenterPos = QPoint()
        self.displacement = QPoint()
        self.startPos: Union[QPoint, None] = None

        # for vicinity diagram purposes
        self.root_bus: Union[Bus, None] = None

        # for graphics dev purposes
        # self.pos_label = QGraphicsTextItem()
        # self.add_to_scene(self.pos_label)
        self._needs_post_show_branch_refresh: bool = False
        self._branch_refresh_scheduled: bool = False
        self._is_loading_diagram: bool = False
        self._is_batch_refreshing_branches: bool = False
        self._saved_viewport_update_mode: QGraphicsView.ViewportUpdateMode | None = None

        if diagram is not None:
            self.draw()

        # -------------------------------------------------------------------------------------------------
        # Note: Do not declare any variable beyond here, as it may not be considered if draw is called :/

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

            point0 = self.editor_graphics_view.mapToScene(int(event.position().x()), int(event.position().y()))
            x0 = point0.x()
            y0 = point0.y()

            if obj_type == self.library_model.get_bus_mime_data():
                obj = Bus(name=f'Bus {self.circuit.get_bus_number()}', Vnom=self.default_bus_voltage,
                          graphic_type=BusGraphicType.BusBar)
                graphic_object = self.create_bus_graphics(bus=obj, x=x0, y=y0, h=20, w=80)
                self.circuit.add_bus(obj=obj)

            elif obj_type == self.library_model.get_connectivity_node_mime_data():
                obj = Bus(name=f'Bus {self.circuit.get_bus_number()}', Vnom=self.default_bus_voltage,
                          graphic_type=BusGraphicType.Connectivity)
                graphic_object = self.create_bus_graphics(bus=obj, x=x0, y=y0, h=40, w=40)
                self.circuit.add_bus(obj)

            elif obj_type == self.library_model.get_3w_transformer_mime_data():
                obj = Transformer3W(name=f"Transformer 3W {len(self.circuit.transformers3w)}")
                graphic_object = self.create_transformer_3w_graphics(elm=obj, x=x0, y=y0)
                self.circuit.add_transformer3w(obj)

            elif obj_type == self.library_model.get_nw_transformer_mime_data():
                dlg = InputNumberDialogue(min_value=3,
                                          max_value=20,
                                          default_value=4,
                                          is_int=True,
                                          title=self.tr('NW transformer'),
                                          text=self.tr('Select the number of windings'))
                exec_dialog_safely(dialog=dlg)

                if not dlg.is_accepted:
                    return

                obj = TransformerNW(name=f"Transformer NW {len(self.circuit.transformers_nw)}",
                                    winding_count=dlg.value)
                graphic_object = self.create_transformer_nw_graphics(elm=obj, x=x0, y=y0)
                self.circuit.add_transformer_nw(obj)

            elif obj_type == self.library_model.get_fluid_node_mime_data():
                obj = FluidNode(name=f"Fluid node {self.circuit.get_fluid_nodes_number()}")
                graphic_object = self.create_fluid_node_graphics(node=obj, x=x0, y=y0, h=20, w=80)
                self.circuit.add_fluid_node(obj)

            elif obj_type == self.library_model.get_vsc_mime_data():
                # Create VSC API object
                obj = VSC(name=f'VSC {len(self.circuit.vsc_devices)}')
                graphic_object = self.create_vsc_graphics_3term(elm=obj, x=x0, y=y0)
                self.circuit.add_vsc(obj)

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

    def _query_graphic_of_type(self,
                               elm: ALL_DEV_TYPES | None,
                               graphic_type: type[_GRAPHIC_T]) -> _GRAPHIC_T | None:
        """
        Query one registered graphic and narrow it to the expected widget class.
        """
        graphic_object = self.graphics_manager.query(elm)

        if isinstance(graphic_object, graphic_type):
            return graphic_object
        else:
            return None

    def _get_device_type_graphics(self,
                                  device_type: DeviceType,
                                  graphic_type: type[_GRAPHIC_T]) -> list[_GRAPHIC_T]:
        """
        Return only graphics of the requested widget class for one device type bucket.
        """
        return [
            graphic_object
            for graphic_object in self.graphics_manager.get_device_type_list(device_type)
            if isinstance(graphic_object, graphic_type)
        ]

    def _query_generic_graphic(self, elm: ALL_DEV_TYPES | None) -> GenericDiagramWidget | None:
        return self._query_graphic_of_type(elm=elm, graphic_type=GenericDiagramWidget)

    def _query_bus_graphic(self, bus: Bus | None) -> BusGraphicItem | None:
        return self._query_graphic_of_type(elm=bus, graphic_type=BusGraphicItem)

    def _query_fluid_node_graphic(self, node: FluidNode | None) -> FluidNodeGraphicItem | None:
        return self._query_graphic_of_type(elm=node, graphic_type=FluidNodeGraphicItem)

    def _query_terminal_owner_graphic(self,
                                      elm: Bus | FluidNode | None) -> TERMINAL_OWNER_GRAPHICS | None:
        if isinstance(elm, Bus):
            raw_graphic_object: ALL_GRAPHICS | None = self.graphics_manager.query(elm=elm)
            if isinstance(raw_graphic_object, (BusGraphicItem, FluidNodeGraphicItem)):
                graphic_object: TERMINAL_OWNER_GRAPHICS | None = raw_graphic_object
            else:
                graphic_object = None
        else:
            graphic_object = self._query_fluid_node_graphic(elm)

        return graphic_object

    def _query_line_graphic(self, elm: ALL_DEV_TYPES | None) -> LineGraphicTemplateItem | None:
        return self._query_graphic_of_type(elm=elm, graphic_type=LineGraphicTemplateItem)

    def _query_transformer3w_graphic(self, elm: Transformer3W | None) -> Transformer3WGraphicItem | None:
        return self._query_graphic_of_type(elm=elm, graphic_type=Transformer3WGraphicItem)

    def _query_transformer_nw_graphic(self, elm: TransformerNW | None) -> TransformerNWGraphicItem | None:
        return self._query_graphic_of_type(elm=elm, graphic_type=TransformerNWGraphicItem)

    def _query_vsc_graphic(self, elm: VSC | None) -> VscGraphicItem | None:
        return self._query_graphic_of_type(elm=elm, graphic_type=VscGraphicItem)

    def _query_hvdc_graphic(self, elm: HvdcLine | None) -> HvdcGraphicItem | None:
        return self._query_graphic_of_type(elm=elm, graphic_type=HvdcGraphicItem)

    def _query_fluid_path_graphic(self, elm: FluidPath | None) -> FluidPathGraphicItem | None:
        return self._query_graphic_of_type(elm=elm, graphic_type=FluidPathGraphicItem)

    def _query_injection_graphic(self, elm: INJECTION_DEVICE_TYPES | None) -> InjectionTemplateGraphicItem | None:
        return self._query_graphic_of_type(elm=elm, graphic_type=InjectionTemplateGraphicItem)

    def graphicsWheelEvent(self, event: QWheelEvent) -> None:
        """
        Zoom
        @param event:
        @return:
        """
        self.editor_graphics_view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        zoom_steps: float = self.get_wheel_zoom_steps(event=event)
        if zoom_steps != 0.0:
            # Use the wheel magnitude so high-resolution touchpad events produce small smooth zoom increments.
            self.zoom_by_steps(steps=zoom_steps)
            event.accept()
        else:
            event.ignore()

    def get_wheel_zoom_steps(self, event: QWheelEvent) -> float:
        """
        Convert a wheel event into a normalized zoom step count.

        A mouse wheel commonly emits an angle delta of 120 units per notch, while laptop touchpads emit many smaller
        high-resolution events and may provide pixel deltas. Normalizing by the event magnitude keeps mouse-wheel zoom
        unchanged and makes touchpad zoom proportional to the gesture instead of applying one full zoom step per event.

        :param event: Wheel event coming from the graphics view.
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

    def zoom_by_steps(self, steps: float) -> None:
        """
        Apply zoom using a normalized number of mouse-wheel steps.

        :param steps: Signed zoom step count. One positive step matches one traditional mouse-wheel zoom-in notch.
        :return: None.
        """
        zoom_factor: float = self.scale_factor ** steps
        self.editor_graphics_view.scale(zoom_factor, zoom_factor)

    def graphicsKeyPressEvent(self, event: QKeyEvent):
        """
        Key press event cature
        :param event:
        :return:
        """
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_from_widget(delete_from_db=True)

    def zoom_in(self) -> None:
        """
        zoom in
        """
        self.editor_graphics_view.scale(self.scale_factor, self.scale_factor)

    def zoom_out(self) -> None:
        """
        Zoom out
        """
        self.editor_graphics_view.scale(1.0 / self.scale_factor, 1.0 / self.scale_factor)

    def create_bus_graphics(self, bus: Bus, x: float, y: float, h: float, w: float,
                            draw_labels: bool = True, r: float = 0.0) -> BusGraphicItem | None:
        """
        create the Bus graphics
        :param bus: VeraGrid Bus object
        :param x: x coordinate
        :param y: y coordinate
        :param h: height (px)
        :param w: width (px)
        :param draw_labels: Draw labels?
        :param r: rotation angle (deg)
        :return: BusGraphicItem
        """
        return BusGraphicItem(editor=self,
                              bus=bus,
                              x=x,
                              y=y,
                              h=h,
                              w=w,
                              draw_labels=draw_labels,
                              r=r)

    def create_transformer_3w_graphics(self, elm: Transformer3W, x: float, y: float) -> Transformer3WGraphicItem:
        """
        Add Transformer3W to the graphics
        :param elm: Transformer3W
        :param x: x coordinate
        :param y: y coordinate
        :return: Transformer3WGraphicItem
        """
        graphic_object = Transformer3WGraphicItem(editor=self, elm=elm)
        graphic_object.setPos(QPointF(x, y))
        return graphic_object

    def create_transformer_nw_graphics(self, elm: TransformerNW, x: float, y: float) -> TransformerNWGraphicItem:
        """
        Add TransformerNW to the graphics
        :param elm: TransformerNW
        :param x: x coordinate
        :param y: y coordinate
        :return: TransformerNWGraphicItem
        """
        graphic_object = TransformerNWGraphicItem(editor=self, elm=elm)
        graphic_object.setPos(QPointF(x, y))
        return graphic_object

    def create_fluid_node_graphics(self, node: FluidNode, x: float, y: float, h: float, w: float,
                                   draw_labels: bool = True) -> FluidNodeGraphicItem:
        """
        Add fluid node to graphics
        :param node: VeraGrid FluidNode object
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

    def create_vsc_graphics_3term(self, elm: VSC, x: float, y: float) -> VscGraphicItem3Term:
        """
        Add VSC to the graphics
        :param elm: VSC
        :param x: x coordinate
        :param y: y coordinate
        :return: VscGraphicItem3Term
        """
        graphic_object = VscGraphicItem3Term(editor=self, api_object=elm)
        graphic_object.setPos(QPointF(x, y))
        return graphic_object

    def create_vsc_terminal_connection(self,
                                       bus_port: Union[BarTerminalItem, RoundTerminalItem],
                                       vsc_terminal: Union[BarTerminalItem, RoundTerminalItem]) -> bool:
        """
        Create a bus-to-terminal graphical connection for a 3-terminal VSC and
        assign the corresponding API bus to that terminal.
        :param bus_port: Bus terminal
        :param vsc_terminal: VSC terminal
        :return: connection success
        """
        if not isinstance(bus_port, (BarTerminalItem, RoundTerminalItem)):
            return False
        if not isinstance(vsc_terminal, RoundTerminalItem):
            return False

        vsc_graphic = vsc_terminal.get_parent()
        if not isinstance(vsc_graphic, VscGraphicItem3Term):
            return False

        bus_graphic = bus_port.get_parent()
        if not isinstance(bus_graphic, BusGraphicItem):
            return False

        conn_line = LineGraphicTemplateItem(from_port=bus_port,
                                            to_port=vsc_terminal,
                                            editor=self)

        success = vsc_graphic.set_connection(terminal_type=vsc_terminal.terminal_type,
                                             bus=bus_graphic.api_object,
                                             conn_line=conn_line)
        if success:
            self.add_to_scene(conn_line)
            conn_line.setZValue(-1)
            return True

        # Revert terminal callbacks when the connection is rejected.
        conn_line.unregister_port_from()
        conn_line.unregister_port_to()
        return False

    def draw_additional_diagram(self,
                                diagram: SchematicDiagram,
                                logger: Logger | None = None) -> None:
        """
        Draw a new diagram
        :param diagram: SchematicDiagram
        :param logger: Logger
        """
        if logger is None:
            logger = Logger()
        self._is_loading_diagram = True
        self.suspend_viewport_updates_for_loading()
        inj_dev_by_bus = self.circuit.get_injection_devices_grouped_by_bus()
        inj_dev_by_fluid_node = self.circuit.get_injection_devices_grouped_by_fluid_node()
        category_items = list(diagram.data.items())

        # add node-like elements first
        for category, points_group in category_items:

            if category == DeviceType.BusDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is None:
                        # add the graphic object to the diagram view
                        graphic_object = self.create_bus_graphics(bus=location.api_object,
                                                                  x=location.x,
                                                                  y=location.y,
                                                                  h=location.h,
                                                                  w=location.w,
                                                                  draw_labels=location.draw_labels,
                                                                  r=location.r)
                        self.add_to_scene(graphic_object=graphic_object)

                        # create the bus children
                        graphic_object.create_children_widgets(
                            injections_by_tpe=inj_dev_by_bus.get(location.api_object, dict())
                        )

                        graphic_object.change_size(w=location.w)

                        # add buses reference for later
                        # bus_dict[idtag] = graphic_object
                        self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.FluidNodeDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:

                    if isinstance(location, GraphicLocation):
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

                            graphic_object.change_size(h=location.h, w=location.w)

                            # add fluid node reference for later
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)
                            if location.api_object.bus is not None:
                                self.graphics_manager.add_device(elm=location.api_object.bus, graphic=graphic_object)

            else:
                # pass for now...
                pass

        # add 3W transformers after the node devices
        for category, points_group in category_items:

            if category == DeviceType.Transformer3WDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is None:
                        elm: Transformer3W = location.api_object

                        graphic_object = self.create_transformer_3w_graphics(elm=elm,
                                                                             x=location.x,
                                                                             y=location.y)
                        self.graphics_manager.add_device(elm=elm, graphic=graphic_object)
                        self.add_to_scene(graphic_object=graphic_object)

                        w1_graphics = self.add_api_winding(
                            branch=elm.winding1,
                            from_port=graphic_object.terminals[0],
                            draw_labels=location.draw_labels,
                            logger=logger
                        )
                        if w1_graphics is not None:
                            self.graphics_manager.add_device(elm=elm.winding1, graphic=w1_graphics)
                            graphic_object.connection_lines[0] = w1_graphics

                        w2_graphics = self.add_api_winding(
                            branch=elm.winding2,
                            from_port=graphic_object.terminals[1],
                            draw_labels=location.draw_labels,
                            logger=logger
                        )
                        if w2_graphics is not None:
                            self.graphics_manager.add_device(elm=elm.winding2, graphic=w2_graphics)
                            graphic_object.connection_lines[1] = w2_graphics

                        w3_graphics = self.add_api_winding(
                            branch=elm.winding3,
                            from_port=graphic_object.terminals[2],
                            draw_labels=location.draw_labels,
                            logger=logger
                        )
                        if w3_graphics is not None:
                            self.graphics_manager.add_device(elm=elm.winding3, graphic=w3_graphics)
                            graphic_object.connection_lines[2] = w3_graphics

                        graphic_object.set_position(x=location.x, y=location.y)
                        graphic_object.change_size(h=location.h, w=location.w)

                        # graphic_object.update_conn()
                        self.graphics_manager.add_device(elm=elm, graphic=graphic_object)

            elif category == DeviceType.TransformerNwDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:

                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is None:
                        elm: TransformerNW = location.api_object

                        graphic_object = self.create_transformer_nw_graphics(elm=elm,
                                                                             x=location.x,
                                                                             y=location.y)
                        self.graphics_manager.add_device(elm=elm, graphic=graphic_object)
                        self.add_to_scene(graphic_object=graphic_object)

                        for i, winding in enumerate(elm.windings[:graphic_object.n_windings]):
                            winding_graphics = self.add_api_winding(
                                branch=winding,
                                from_port=graphic_object.terminals[i],
                                draw_labels=location.draw_labels,
                                logger=logger
                            )
                            if winding_graphics is not None:
                                self.graphics_manager.add_device(elm=winding, graphic=winding_graphics)
                                graphic_object.connection_lines[i] = winding_graphics
                                graphic_object.slot_windings[i] = winding

                        graphic_object.set_position(x=location.x, y=location.y)
                        graphic_object.change_size(h=location.h, w=location.w)
                        self.graphics_manager.add_device(elm=elm, graphic=graphic_object)

        # add the rest of the branches
        for category, points_group in category_items:

            if category == DeviceType.LineDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:
                    self.add_api_line(branch=location.api_object,
                                      draw_labels=location.draw_labels,
                                      logger=logger)

            elif category == DeviceType.DCLineDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:
                    self.add_api_dc_line(branch=location.api_object,
                                         draw_labels=location.draw_labels,
                                         logger=logger)

            elif category == DeviceType.HVDCLineDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:
                    self.add_api_hvdc(branch=location.api_object,
                                      draw_labels=location.draw_labels,
                                      logger=logger)

            elif category == DeviceType.VscDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:
                    # Use add_api_vsc to create VSC with connections instead of just graphics
                    self.add_api_vsc(elm=location.api_object,
                                     x=location.x,
                                     y=location.y,
                                     r=location.r,
                                     logger=logger)

            elif category == DeviceType.UpfcDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:
                    self.add_api_upfc(branch=location.api_object,
                                      draw_labels=location.draw_labels,
                                      logger=logger)

            elif category == DeviceType.Transformer2WDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:
                    self.add_api_transformer(branch=location.api_object,
                                             draw_labels=location.draw_labels,
                                             logger=logger)

            elif category == DeviceType.SeriesReactanceDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:
                    self.add_api_series_reactance(branch=location.api_object,
                                                  draw_labels=location.draw_labels,
                                                  logger=logger)

            elif category == DeviceType.SwitchDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:
                    self.add_api_switch(branch=location.api_object,
                                        draw_labels=location.draw_labels,
                                        logger=logger)

            elif category == DeviceType.WindingDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is not None:
                        if self.is_loading_diagram():
                            pass
                        else:
                            graphic_object.redraw()
                        self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            elif category == DeviceType.FluidPathDevice.value:

                location_items = list(points_group.locations.items())

                for idtag, location in location_items:

                    # search for the api object, because it may be created already
                    graphic_object = self.graphics_manager.query(elm=location.api_object)

                    if graphic_object is None:

                        from_port, to_port = self.find_ports(branch=location.api_object)

                        if from_port is not None and to_port is not None:
                            graphic_object = FluidPathGraphicItem(from_port=from_port,
                                                                  to_port=to_port,
                                                                  editor=self,
                                                                  api_object=location.api_object,
                                                                  draw_labels=location.draw_labels)
                            self.add_to_scene(graphic_object=graphic_object)

                            if self.is_loading_diagram():
                                pass
                            else:
                                graphic_object.redraw()
                            self.graphics_manager.add_device(elm=location.api_object, graphic=graphic_object)

            else:
                pass
                # print('draw: Unrecognized category: {}'.format(category))

        # last pass: arrange children immediately, then defer the connection refresh until Qt has settled
        for category in [DeviceType.BusDevice, DeviceType.BusBarDevice, DeviceType.FluidNodeDevice]:
            graphics_dict = self.graphics_manager.get_device_type_dict(device_type=category)
            for idtag, graphic in graphics_dict.items():
                graphic.arrange_children()

        self.schedule_branch_callbacks_after_draw()

    def suspend_viewport_updates_for_loading(self) -> None:
        """
        Freeze viewport repaint work while the diagram scene is rebuilt.

        Large diagram loads create many intermediate geometry states. Suppressing
        incremental viewport updates during that batch avoids repainting those
        transient states and leaves one final redraw for the post-load refresh.

        :return: ``None``.
        """
        if self._saved_viewport_update_mode is None:
            self._saved_viewport_update_mode = self.editor_graphics_view.viewportUpdateMode()
            self.editor_graphics_view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.NoViewportUpdate)
        else:
            pass

    def restore_viewport_updates_after_loading(self) -> None:
        """
        Restore the viewport update mode captured at the start of loading.

        :return: ``None``.
        """
        if self._saved_viewport_update_mode is None:
            pass
        elif shiboken6.isValid(self.editor_graphics_view):
            self.editor_graphics_view.setViewportUpdateMode(self._saved_viewport_update_mode)
            self._saved_viewport_update_mode = None
        else:
            self._saved_viewport_update_mode = None

    def schedule_branch_callbacks_after_draw(self) -> None:
        """
        Coalesce expensive post-draw branch refresh work into a single pass.

        During initial startup, ``draw()`` can run before the widget is shown.
        In that case we must defer the refresh until ``showEvent()``. Once the
        widget is visible, repeated draw/update paths should still collapse into
        one queued refresh instead of replaying the full callback and redraw
        sweep multiple times.

        :return: ``None``.
        """
        if not self.isVisible():
            self._needs_post_show_branch_refresh = True
        elif self._branch_refresh_scheduled:
            pass
        else:
            self._branch_refresh_scheduled = True
            QTimer.singleShot(0, self.refresh_branch_callbacks_after_draw)

    def refresh_branch_callbacks_after_draw(self) -> None:
        """
        Refresh terminal-hosted branch callbacks after the scene graph has settled.
        """
        if not shiboken6.isValid(self) or not shiboken6.isValid(self.editor_graphics_view):
            return
        else:
            pass

        self._branch_refresh_scheduled = False
        branch_graphics_to_refresh: set = set()
        self._is_batch_refreshing_branches = True

        try:
            for category in [DeviceType.BusDevice, DeviceType.BusBarDevice, DeviceType.FluidNodeDevice]:
                graphics_dict = self.graphics_manager.get_device_type_dict(device_type=category)

                for idtag, graphic in graphics_dict.items():
                    if shiboken6.isValid(graphic):
                        terminal = graphic.get_terminal()
                        if shiboken6.isValid(terminal):
                            terminal.update()
                            terminal.process_callbacks(terminal.scenePos())
                            graphic.auto_assign_branch_slots()

                            for branch_graphic in graphic.get_associated_branch_graphics():
                                if shiboken6.isValid(branch_graphic):
                                    branch_graphics_to_refresh.add(branch_graphic)
                                else:
                                    pass

                            graphic.arrange_children()
                        else:
                            pass
                    else:
                        pass

            self._is_batch_refreshing_branches = False

            for branch_graphic in branch_graphics_to_refresh:
                if shiboken6.isValid(branch_graphic):
                    branch_graphic.upgrade_legacy_layout_from_diagram()
                    branch_graphic.load_route_points_from_diagram()
                    branch_graphic.redraw()
                else:
                    pass
        finally:
            self._is_batch_refreshing_branches = False
            self._is_loading_diagram = False
            self.restore_viewport_updates_after_loading()

    def is_loading_diagram(self) -> bool:
        """
        Determine whether the schematic is still reconstructing diagram geometry.

        :return: ``True`` while diagram items are being loaded and callbacks are settling.
        """
        return self._is_loading_diagram

    def is_batch_refreshing_branches(self) -> bool:
        """
        Determine whether branch endpoints are being updated in a batched refresh.

        During this phase terminal callbacks should only update endpoint
        positions. A single final redraw pass is executed afterwards.

        :return: ``True`` while branch callbacks are being coalesced.
        """
        return self._is_batch_refreshing_branches

    def draw(self) -> None:
        """
        Draw the stored diagram
        """
        if self.diagram is not None:
            # A first layout pass on the stored coordinates avoids creating every
            # Qt item at the origin, which is the expensive case for scene setup.
            if should_auto_layout_before_first_draw(diagram=self.diagram):
                apply_initial_auto_layout_to_diagram(diagram=self.diagram,
                                                     layout_name="power_system_layout")
            else:
                pass

            self.draw_additional_diagram(diagram=self.diagram, logger=self.logger)
        else:
            pass

    def showEvent(self, event) -> None:
        """
        Trigger a final branch refresh once the widget is actually shown.
        """
        super().showEvent(event)

        if self._needs_post_show_branch_refresh:
            self._needs_post_show_branch_refresh = False
            self.schedule_branch_callbacks_after_draw()
        else:
            pass

    def expand_diagram_from_bus(self, root_bus: Bus) -> None:
        """
        Expand the diagram from one bus
        :param root_bus: Root bus to expand from
        """
        extra_diagram = make_vicinity_diagram(circuit=self.circuit,
                                              root_bus=root_bus,
                                              max_level=1)

        self.draw_additional_diagram(diagram=extra_diagram, logger=self.logger)

    def update_diagram_element(self, device: ALL_DEV_TYPES,
                               x: float = 0, y: float = 0, w: float = 0, h: float = 0, r: float = 0,
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
        self.diagram.update_graphic_location(api_object=device,
                                             x=x,
                                             y=y,
                                             h=h,
                                             w=w,
                                             r=r,
                                             draw_labels=draw_labels)

        if self.is_loading_diagram():
            pass
        else:
            self.diagram.sync_branch_attachments(api_object=device)

        self.graphics_manager.add_device(elm=device, graphic=graphic_object)

    def add_to_scene(self, graphic_object: QGraphicsItem = None) -> None:
        """
        Add item to the diagram and the diagram scene
        :param graphic_object: Graphic object associated
        """
        if graphic_object is not None:
            self.diagram_scene.addItem(graphic_object)
            # Newly created graphics must immediately reflect the device active state
            # and the current GUI theme instead of waiting for a later recolour pass.
            if isinstance(graphic_object, GenericDiagramWidget):
                graphic_object.recolour_mode()
            else:
                pass
        else:
            warn("Null graphics skipped")

    def _remove_from_scene(self, graphic_object: QGraphicsItem | GenericDiagramWidget) -> None:
        """
        Remove item from the diagram scene
        :param graphic_object: Graphic object associated
        """
        if graphic_object is not None:
            if graphic_object.scene() is not None:
                self.diagram_scene.removeItem(graphic_object)
            else:
                # self.gui.show_warning_toast(f"Null scene for {graphic_object}, was it deleted already?")
                pass

    def persist_selected_item_positions(self) -> None:
        """
        Persist the final position of every selected movable diagram widget.
        """
        graphic_object: QGraphicsItem

        for graphic_object in self.diagram_scene.selectedItems():
            if graphic_object.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable:
                if isinstance(graphic_object, GenericDiagramWidget):
                    api_object = graphic_object.api_object
                    draw_labels_value: bool = graphic_object.draw_labels
                else:
                    try:
                        api_object = graphic_object.api_object
                        draw_labels_value = graphic_object.draw_labels
                    except AttributeError:
                        api_object = None
                        draw_labels_value = True
            else:
                api_object = None
                draw_labels_value = True

            if api_object is not None:
                # Only the resizable diagram widgets persist their stored width and
                # height. All other movable graphics only need the new position.
                if isinstance(graphic_object,
                              (BusGraphicItem,
                               FluidNodeGraphicItem,
                               InjectionTemplateGraphicItem,
                               Transformer3WGraphicItem,
                               TransformerNWGraphicItem,
                               VscGraphicItem3Term)):
                    width_value: float = float(graphic_object.w)
                    height_value: float = float(graphic_object.h)
                else:
                    width_value = 0.0
                    height_value = 0.0

                scene_position: QPointF = graphic_object.scenePos()

                self.update_diagram_element(device=api_object,
                                            x=scene_position.x(),
                                            y=scene_position.y(),
                                            w=width_value,
                                            h=height_value,
                                            r=graphic_object.rotation(),
                                            draw_labels=draw_labels_value,
                                            graphic_object=graphic_object)
            else:
                pass

    @staticmethod
    def _clamp_manual_injection_alignment(alignment: Any) -> float:
        """
        Clamp one optional manual injection alignment value.

        :param alignment: Raw alignment value.
        :return: Clamped normalized alignment.
        """
        if alignment is None:
            return 0.5
        else:
            pass

        alignment_value: float = float(alignment)

        if alignment_value < 0.0:
            return 0.0
        elif alignment_value > 1.0:
            return 1.0
        else:
            return alignment_value

    @staticmethod
    def _is_plausible_manual_injection_local_position(owner_graphic: Any,
                                                      injection_graphic: Any,
                                                      local_position: QPointF,
                                                      multiplier: float) -> bool:
        """
        Check whether one manual child position is broadly plausible in owner-local coordinates.

        :param owner_graphic: Parent node graphic.
        :param injection_graphic: Child injection graphic.
        :param local_position: Candidate position in owner-local coordinates.
        :param multiplier: Width-based plausibility margin multiplier.
        :return: ``True`` when the local point looks reasonable.
        """
        margin: float = max(0.0, float(multiplier) * float(owner_graphic.w))
        min_x: float = -float(injection_graphic.w) - margin
        max_x: float = float(owner_graphic.w) + margin
        min_y: float = -float(injection_graphic.h) - margin
        max_y: float = float(owner_graphic.h) + margin

        return min_x <= float(local_position.x()) <= max_x and min_y <= float(local_position.y()) <= max_y

    @staticmethod
    def _build_manual_injection_local_position_from_dock(owner_graphic: Any,
                                                         injection_graphic: Any,
                                                         dock: dict[str, Any]) -> QPointF:
        """
        Rebuild the expected owner-local position from persisted manual dock metadata.

        The dock metadata stores side, alignment, and offset derived from the
        child local coordinates. Rebuilding that position gives a stronger
        legacy-repair signal than a large plausibility box because it preserves
        the user's original dock intent.

        :param owner_graphic: Parent node graphic.
        :param injection_graphic: Child injection graphic.
        :param dock: Persisted dock metadata.
        :return: Expected owner-local child origin.
        """
        side_value: str = str(dock.get("side", "bottom")).strip().lower()
        alignment: float = SchematicWidget._clamp_manual_injection_alignment(dock.get("alignment", None))
        offset: float = max(0.0, float(dock.get("offset", 0.0)))

        if side_value == "top":
            x_pos = float(owner_graphic.w) * alignment - float(injection_graphic.w) * 0.5
            y_pos = -float(injection_graphic.h) - 40.0 - offset
        elif side_value == "left":
            x_pos = -float(injection_graphic.w) - 40.0 - offset
            y_pos = float(owner_graphic.h) * alignment - float(injection_graphic.h) * 0.5
        elif side_value == "right":
            x_pos = float(owner_graphic.w) + 40.0 + offset
            y_pos = float(owner_graphic.h) * alignment - float(injection_graphic.h) * 0.5
        else:
            x_pos = float(owner_graphic.w) * alignment - float(injection_graphic.w) * 0.5
            y_pos = float(owner_graphic.get_bottom_dock_baseline()) + offset

        return QPointF(x_pos, y_pos)

    def repair_suspicious_injection_positions(self, multiplier: float = 4.0) -> int:
        """
        Repair legacy manual injection positions that were accidentally persisted in owner-local space.

        Only injections with ``auto_layout == False`` are considered. The helper
        repairs a point only when the canonical scene-space interpretation is not
        plausible but the raw stored value treated as owner-local is plausible.

        :param multiplier: Width-based plausibility margin multiplier.
        :return: Number of repaired injections.
        """
        repaired_count: int = 0
        owners_to_refresh: list[BusGraphicItem] = list()
        device_type: DeviceType

        for device_type in (
                DeviceType.GeneratorDevice,
                DeviceType.BatteryDevice,
                DeviceType.StaticGeneratorDevice,
                DeviceType.ShuntDevice,
                DeviceType.ControllableShuntDevice,
                DeviceType.LoadDevice,
                DeviceType.ExternalGridDevice,
                DeviceType.CurrentInjectionDevice,
        ):
            for graphic_object in self._get_device_type_graphics(device_type, InjectionTemplateGraphicItem):
                location: GraphicLocation | None = self.diagram.query_point(graphic_object.api_object)
                should_inspect_graphic: bool = location is not None
                dock: dict[str, Any] = dict()
                owner_graphic: BusGraphicItem | None = None

                # The repair only makes sense for persisted manual layouts.
                # Automatic layouts and graphics without stored coordinates are ignored explicitly.
                if should_inspect_graphic:
                    dock = self.diagram.get_dock(graphic_object.api_object)
                    if bool(dock.get("auto_layout", True)):
                        should_inspect_graphic = False
                    else:
                        should_inspect_graphic = True
                else:
                    should_inspect_graphic = False

                # The repair logic needs a concrete owner graphic because the legacy bug
                # mixed owner-local coordinates with scene coordinates.
                if should_inspect_graphic:
                    owner_graphic = graphic_object.parent

                    if owner_graphic is None:
                        should_inspect_graphic = False
                    else:
                        should_inspect_graphic = True
                else:
                    owner_graphic = None

                if should_inspect_graphic and owner_graphic is not None and location is not None:
                    # Evaluate the stored point both as canonical scene coordinates and
                    # as the legacy broken owner-local coordinates.
                    scene_candidate_local: QPointF = owner_graphic.mapFromScene(QPointF(float(location.x),
                                                                                        float(location.y)))
                    raw_candidate_local: QPointF = QPointF(float(location.x), float(location.y))

                    # Rebuild the expected docked local position from the saved dock metadata.
                    # This gives a much stronger signal than a wide plausibility box alone.
                    expected_local: QPointF = SchematicWidget._build_manual_injection_local_position_from_dock(
                        owner_graphic=owner_graphic,
                        injection_graphic=graphic_object,
                        dock=dock
                    )
                    raw_distance_to_expected: float = float(np.hypot(float(raw_candidate_local.x()
                                                                            - expected_local.x()),
                                                                     float(raw_candidate_local.y()
                                                                           - expected_local.y())))
                    scene_distance_to_expected: float = float(np.hypot(float(scene_candidate_local.x()
                                                                              - expected_local.x()),
                                                                       float(scene_candidate_local.y()
                                                                             - expected_local.y())))
                    repair_distance_margin: float = max(20.0, float(owner_graphic.w) * 0.1)

                    # The legacy bug stores the intended owner-local point directly in the
                    # scene-space slots. When that happens, the raw stored values remain much
                    # closer to the dock-derived expectation than the scene-space interpretation.
                    # A clear distance win is enough for the manual repair tool.
                    scene_is_plausible: bool = SchematicWidget._is_plausible_manual_injection_local_position(
                        owner_graphic=owner_graphic,
                        injection_graphic=graphic_object,
                        local_position=scene_candidate_local,
                        multiplier=multiplier
                    )
                    raw_is_plausible: bool = SchematicWidget._is_plausible_manual_injection_local_position(
                        owner_graphic=owner_graphic,
                        injection_graphic=graphic_object,
                        local_position=raw_candidate_local,
                        multiplier=multiplier
                    )

                    if raw_distance_to_expected + repair_distance_margin < scene_distance_to_expected:
                        should_repair: bool = True
                    elif raw_is_plausible and not scene_is_plausible:
                        should_repair = True
                    else:
                        should_repair = False

                    # Rewrite the stored point back to canonical scene coordinates.
                    if should_repair:
                        graphic_object.setPos(float(raw_candidate_local.x()), float(raw_candidate_local.y()))
                        scene_position: QPointF = graphic_object.scenePos()
                        self.update_diagram_element(device=graphic_object.api_object,
                                                    x=scene_position.x(),
                                                    y=scene_position.y(),
                                                    w=float(graphic_object.w),
                                                    h=float(graphic_object.h),
                                                    r=float(graphic_object.rotation()),
                                                    draw_labels=graphic_object.draw_labels,
                                                    graphic_object=graphic_object)
                        repaired_count += 1

                        if not any(owner_graphic is existing_owner for existing_owner in owners_to_refresh):
                            owners_to_refresh.append(owner_graphic)
                        else:
                            pass
                    else:
                        pass
                else:
                    pass

        owner_graphic: BusGraphicItem
        for owner_graphic in owners_to_refresh:
            owner_graphic.arrange_children()

        return repaired_count

    def set_selected_buses(self, buses: List[Bus]):
        """
        Select the buses
        :param buses: list of Buses
        """
        for bus in buses:
            graphic_object = self._query_bus_graphic(bus)
            if graphic_object is not None:
                graphic_object.setSelected(True)

    def get_selected_buses(self) -> List[Tuple[int, Bus, BusGraphicItem]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, Bus, BusGraphicItem]] = list()
        bus_graphic_dict = self.graphics_manager.get_device_type_dict(DeviceType.BusDevice)

        bus_dict: Dict[str, Tuple[int, Bus]] = {b.idtag: (i, b) for i, b in enumerate(self.circuit.get_buses())}

        for idtag, graphic_object in bus_graphic_dict.items():
            if isinstance(graphic_object, BusGraphicItem):
                if graphic_object.isSelected():
                    bus_tuple: Tuple[int, Bus] | None = bus_dict.get(idtag, None)
                    if bus_tuple is None:
                        pass
                    else:
                        idx, bus = bus_tuple
                        lst.append((idx, bus, graphic_object))
                else:
                    pass
            else:
                pass
        return lst

    def get_buses(self) -> List[Tuple[int, Bus, BusGraphicItem]]:
        """
        Get all the buses
        :return: tuple(bus index, bus_api_object, bus_graphic_object)
        """
        lst: List[Tuple[int, Bus, BusGraphicItem]] = list()
        bus_graphics_dict = self.graphics_manager.get_device_type_dict(DeviceType.BusDevice)
        bus_dict: Dict[str, Tuple[int, Bus]] = {b.idtag: (i, b) for i, b in enumerate(self.circuit.get_buses())}

        for bus_idtag, graphic_object in bus_graphics_dict.items():
            if isinstance(graphic_object, BusGraphicItem):
                bus_tuple: Tuple[int, Bus] | None = bus_dict.get(bus_idtag, None)
                if bus_tuple is None:
                    pass
                else:
                    idx, bus = bus_tuple
                    lst.append((idx, bus, graphic_object))
            else:
                pass

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
                    bus_to: Union[None, Bus] = None):
        """

        :param from_port:
        :param to_port:
        :param bus_from:
        :param bus_to:
        :return:
        """
        name = 'Line ' + str(len(self.circuit.lines) + 1)
        obj = Line(bus_from=bus_from, bus_to=bus_to, name=name)

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

        self.update_diagram_element(device=winding_graphics._api_object,
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

    def create_vsc_graphics_2term(self, bus_from: Bus, bus_to: Bus, from_port: BarTerminalItem,
                                  to_port: BarTerminalItem):
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
        # graphic_object.update_ports()

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

        items = self.diagram_scene.items(event.scenePos())  # get the widgets at the mouse position

        for arriving_widget in items:

            if isinstance(arriving_widget,
                          Union[BarTerminalItem, RoundTerminalItem]):
                # arriving to a bus or bus-bar

                # Clear or finnish the started connection:
                if self.started_branch is None:
                    return None

                if arriving_widget.get_parent() is not self.started_branch.get_terminal_from_parent():  # forbid connecting to itself

                    self.started_branch.set_to_port(arriving_widget)

                    if self.started_branch.connected_between_buses():  # electrical branch between electrical buses

                        if self.started_branch.should_be_a_converter():
                            # different DC status -> VSC

                            self.create_vsc_graphics_2term(bus_from=self.started_branch.get_bus_from(),
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

                            if winding not in self.circuit.windings:
                                self.circuit.add_winding(winding)

                            tr3_graphic_object.set_connection(i=i,
                                                              bus=bus,
                                                              conn=winding_graphics,
                                                              set_voltage=True)

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

                            if winding not in self.circuit.windings:
                                self.circuit.add_winding(winding)

                            tr3_graphic_object.set_connection(i=i,
                                                              bus=bus,
                                                              conn=winding_graphics,
                                                              set_voltage=True)

                    elif self.started_branch.connected_between_bus_and_vsc3():
                        self.create_vsc_terminal_connection(
                            bus_port=self.started_branch.get_terminal_from(),
                            vsc_terminal=self.started_branch.get_terminal_to()
                        )

                    elif self.started_branch.connected_between_vsc3_and_bus():
                        self.create_vsc_terminal_connection(
                            bus_port=self.started_branch.get_terminal_to(),
                            vsc_terminal=self.started_branch.get_terminal_from()
                        )

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
                            fn_bus.Vnom = bus.Vnom

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
                            fn_bus.Vnom = bus.Vnom

                        self.create_line(bus_from=bus,
                                         bus_to=fn_bus,
                                         from_port=self.started_branch.get_terminal_from(),
                                         to_port=self.started_branch.get_terminal_to())

                    else:
                        warn('unknown connection')
                else:
                    pass

                if self.started_branch is not None:
                    self.started_branch.unregister_port_from()
                    self.started_branch.unregister_port_to()
                    self._remove_from_scene(self.started_branch)
                else:
                    pass

                # release this pointer
                self.started_branch = None
                return None
            else:
                pass

        if self.started_branch is not None:
            self.started_branch.unregister_port_from()
            self.started_branch.unregister_port_to()
            self._remove_from_scene(self.started_branch)
        else:
            pass

        # release this pointer after no terminal accepted the branch
        self.started_branch = None

    def apply_expansion_factor(self, factor: float) -> None:
        """
        separate or get closer the drawn elements
        :param factor: expansion factor (i.e 1.1 to expand, 0.9 to get closer)
        :return: None.
        """
        min_x: float = float(sys.maxsize)
        min_y: float = float(sys.maxsize)
        max_x: float = float(-sys.maxsize)
        max_y: float = float(-sys.maxsize)

        check_selected_only: bool = len(self.diagram_scene.selectedItems()) > 0

        bus_movement_by_idtag: Dict[str, QPointF] = dict()

        for dev_tpe in (DeviceType.BusDevice,
                        DeviceType.BusBarDevice,
                        DeviceType.Transformer3WDevice,
                        DeviceType.TransformerNwDevice):

            node_graphic_objects_dict: Dict[str, GenericDiagramWidget] = self.graphics_manager.graphic_dict.get(
                dev_tpe,
                dict(),
            )

            for key, item in node_graphic_objects_dict.items():
                if item.api_object.device_type == DeviceType.FluidNodeDevice:
                    # The internal electrical bus of a fluid node can point to the same graphic item.
                    # Move that item once in the fluid-node pass below.
                    pass
                else:
                    old_x: float = float(item.pos().x())
                    old_y: float = float(item.pos().y())
                    x: float = old_x * factor
                    y: float = old_y * factor
                    item.setPos(QPointF(x, y))

                    if dev_tpe == DeviceType.BusDevice:
                        bus_movement_by_idtag[key] = QPointF(x - old_x, y - old_y)
                    else:
                        pass

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
                    self.diagram.update_xy(api_object=item._api_object, x=x, y=y)

        fluid_graphic_objects_dict: Dict[str, FluidNodeGraphicItem] = self.graphics_manager.graphic_dict.get(
            DeviceType.FluidNodeDevice,
            dict(),
        )

        for item in fluid_graphic_objects_dict.values():
            old_x: float = float(item.pos().x())
            old_y: float = float(item.pos().y())
            fluid_node: FluidNode = item.api_object

            if fluid_node.bus is not None:
                bus_movement: QPointF | None = bus_movement_by_idtag.get(fluid_node.bus.idtag, None)
            else:
                bus_movement = None

            x: float
            y: float
            if bus_movement is not None:
                # Fluid nodes linked to a visible bus follow that bus so their visual offset is preserved.
                x = old_x + bus_movement.x()
                y = old_y + bus_movement.y()
            else:
                x = old_x * factor
                y = old_y * factor

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
            self.diagram.update_xy(api_object=item._api_object, x=x, y=y)

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
        self.editor_graphics_view.fitInView(boundaries, Qt.AspectRatioMode.KeepAspectRatio)

    def center_nodes(self, margin_factor: float = 0.1, elements: Union[None, List[Union[Bus, FluidNode]]] = None) -> None:
        """
        Center the view in the nodes.

        :param margin_factor: Margin factor around bounding rectangle
        :param elements: List of API objects to center on, or None to center all
        """

        if elements is None:
            boundaries: QRectF = self.diagram_scene.itemsBoundingRect()

            if boundaries.isNull():
                return
            else:
                pass

            mx: float = boundaries.width() * margin_factor
            my: float = boundaries.height() * margin_factor
            boundaries.adjust(-mx, -my, mx, my)
            self.diagram_scene.setSceneRect(boundaries)
            self.editor_graphics_view.fitInView(boundaries, Qt.AspectRatioMode.KeepAspectRatio)
            self.editor_graphics_view.scale(1.0, 1.0)
            return
        else:
            pass

        min_x: float = sys.maxsize
        min_y: float = sys.maxsize
        max_x: float = -sys.maxsize
        max_y: float = -sys.maxsize
        max_w: float = 100.0
        max_h: float = 60.0
        found_any: bool = False

        elements_s: set = set(elements)
        for item in self.diagram_scene.items():
            if isinstance(item, (BusGraphicItem,
                                 FluidNodeGraphicItem,
                                 Transformer3WGraphicItem,
                                 TransformerNWGraphicItem)):

                if item.api_object in elements_s:
                    x: float = item.pos().x()
                    y: float = item.pos().y()

                    max_x = max(max_x, x)
                    min_x = min(min_x, x)
                    max_y = max(max_y, y)
                    min_y = min(min_y, y)
                    max_w = max(max_w, item.rect().width())
                    max_h = max(max_h, item.rect().height())
                    found_any = True
                else:
                    pass
            else:
                pass

        if not found_any:
            # Fall back to centering on all items when no specified elements match visible scene items
            self.center_nodes(margin_factor=margin_factor, elements=None)
            return
        else:
            pass

        # set the limits of the view
        dx: float = max_x - min_x
        dy: float = max_y - min_y
        mx: float = margin_factor * dx
        my: float = margin_factor * dy

        h: float = dy + 2 * my + max_h
        w: float = dx + 2 * mx + max_w
        boundaries: QRectF = QRectF(min_x - mx, min_y - my, w, h)

        self.diagram_scene.setSceneRect(boundaries)
        self.editor_graphics_view.fitInView(boundaries, Qt.AspectRatioMode.KeepAspectRatio)
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

    def auto_layout(self, sel: str):
        """
        Automatic layout of the nodes
        """

        nx_graph, node_like_api_objects = self.diagram.build_graph()
        calculated_positions: Dict[int, np.ndarray] = calculate_schematic_layout(graph=nx_graph, sel=sel)

        # Each graph node index matches the position of the API object in node_like_api_objects.
        # This keeps the layout transfer explicit and avoids special-case remapping logic.
        node_idx: int
        elm: Bus | FluidNode | Transformer3W

        for node_idx, elm in enumerate(node_like_api_objects):
            loc: GraphicLocation | None = self.diagram.query_point(elm)
            graphic_object = self._query_generic_graphic(elm=elm)
            pos_vec: np.ndarray | None = calculated_positions.get(node_idx, None)

            if loc is not None and graphic_object is not None and pos_vec is not None:
                x_pos: float = float(pos_vec[0]) * 500.0
                y_pos: float = float(pos_vec[1]) * 500.0

                # The persisted schematic coordinates and the live graphics item
                # must be updated together so subsequent redraws stay consistent.
                loc.x = x_pos
                loc.y = y_pos
                graphic_object.set_position(x_pos, y_pos)
            else:
                loc = loc

        self.center_nodes()

    def fill_xy_from_lat_lon(self,
                             destructive: bool = True,
                             factor: float = 0.01,
                             remove_offset: bool = True):
        """
        fill the x and y value from the latitude and longitude values
        :param destructive: if true, the values are overwritten regardless, otherwise only if x and y are 0
        :param factor: Explosion factor
        :param remove_offset: delete the sometimes huge offset coming from pyproj
        :return Logger object
        """

        # Project the coordinates for *every* bus in the circuit (not only the
        # ones present in this diagram) so that diagrams created afterwards
        # already use the projected x, y. The engine method also falls back to
        # the substation coordinates when a bus has no lat/lon of its own.
        logger = self.circuit.fill_xy_from_lat_lon(destructive=destructive,
                                                   factor=factor,
                                                   remove_offset=remove_offset)

        # move the graphics of the buses present in this diagram to the new positions
        for idx, bus, graphic_object in self.get_buses():
            if graphic_object is not None:
                graphic_object.set_position(bus.x, bus.y)

        return logger

    def rotate(self, angle_degrees):
        """
        Rotates a list of points around a given pivot by a specified angle.

        Parameters:
            angle_degrees (float): The rotation angle in degrees.

        Returns:
            list of tuples: The rotated points.
        """

        # get the buses info
        buses_info_list = self.get_buses()

        # gather the coordinates
        n = len(buses_info_list)
        X = np.zeros(n)
        Y = np.zeros(n)
        for i in range(n):
            idx, bus, graphic_object = buses_info_list[i]
            X[i] = graphic_object.pos().x()
            Y[i] = graphic_object.pos().y()

        # compute the center
        cx = np.mean(X)
        cy = np.mean(Y)

        # compute the sin and cos
        angle_rad = np.deg2rad(angle_degrees)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        for i in range(n):
            idx, bus, graphic_object = buses_info_list[i]

            # Translate the point to the origin relative to the pivot
            x_rel = X[i] - cx
            y_rel = Y[i] - cy

            # Rotate the point
            x_rot = x_rel * cos_a - y_rel * sin_a
            y_rot = x_rel * sin_a + y_rel * cos_a

            # Translate back to the original coordinate system
            x_new = x_rot + cx
            y_new = y_rot + cy
            graphic_object.set_position(x_new, y_new)

    def get_image(self, transparent: bool = False) -> QImage:
        """
        get the current picture
        :param transparent: Set a transparent background
        :return: QImage, width, height
        """
        w = self.editor_graphics_view.width()
        h = self.editor_graphics_view.height()

        if transparent:
            image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QColor(0, 0, 0, 0))  # transparent
        else:
            image = QImage(w, h, QImage.Format.Format_RGB32)
            image.fill(ACTIVE.get('background', QColor(0, 0, 0, 0)))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.editor_graphics_view.render(painter)
        painter.end()
        # image = self.editor_graphics_view.grab().toImage()

        return image

    def take_picture(self, filename: str):
        """
        Save the grid to a png file
        """
        name, extension = os.path.splitext(filename.lower())

        if extension == '.png':
            image = self.get_image(transparent=False)
            image.save(filename)

        elif extension == '.svg':
            w = self.editor_graphics_view.width()
            h = self.editor_graphics_view.height()
            svg_gen = QSvgGenerator()
            svg_gen.setFileName(filename)
            svg_gen.setSize(QSize(w, h))
            svg_gen.setViewBox(QRect(0, 0, w, h))
            svg_gen.setTitle("Electrical grid schematic")
            svg_gen.setDescription("An SVG drawing created by VeraGrid")

            painter = QPainter(svg_gen)
            self.editor_graphics_view.render(painter)
            painter.end()
        else:
            raise Exception('Extension ' + str(extension) + ' not supported :(')

    def add_api_bus(self,
                    bus: Bus,
                    injections_by_tpe: Dict[DeviceType, List[ALL_DEV_TYPES]],
                    explode_factor: float = 1.0,
                    x0: Union[float, None] = None,
                    y0: Union[float, None] = None) -> BusGraphicItem:
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
        graphic_object = self.create_bus_graphics(bus=bus, x=x, y=y, w=bus.w, h=bus.h, r=0.0)

        # create the bus children
        if len(injections_by_tpe) > 0:
            graphic_object.create_children_widgets(injections_by_tpe=injections_by_tpe)

        self.update_diagram_element(device=bus,
                                    x=x,
                                    y=y,
                                    w=bus.w,
                                    h=bus.h,
                                    r=graphic_object.r,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)

        return graphic_object

    def find_port(self,
                  port: OPTIONAL_PORT = None,
                  bus: Union[None, Bus] = None) -> OPTIONAL_PORT:
        """
        Try to find the connection graphics from the API connection
        :param port: Connection port (optional)
        :param bus: Api Bus (optional)
        :return: OPTIONAL_PORT
        """
        if port is None:

            if bus is not None:  # bus provided, no cn provided

                # Bus provided, search its graphics
                bus_graphic0 = self._query_bus_graphic(bus)

                if bus_graphic0 is None:
                    # could not find any graphics :(
                    return None

                else:
                    # the bus is found, return its default terminal
                    return bus_graphic0.get_terminal()

            else:
                # nothing was provided...
                return None
        else:
            return port

    def find_ports(self, branch: BRANCH_TYPES) -> Tuple[OPTIONAL_PORT, OPTIONAL_PORT]:
        """
        Find the preferred set of ports for drawing
        :param branch: some API branch
        :return: OPTIONAL_PORT, OPTIONAL_PORT
        """

        obj_from, obj_to, is_ok = branch.get_from_and_to_objects()

        from_port = self.find_port_for_attachment(owner_object=obj_from)
        to_port = self.find_port_for_attachment(owner_object=obj_to)

        return from_port, to_port

    def find_to_port(self, branch: BRANCH_TYPES) -> OPTIONAL_PORT:
        """
        Find the preferred set of ports for drawing
        :param branch: some API branch
        :return: OPTIONAL_PORT, OPTIONAL_PORT
        """

        obj_from, obj_to, is_ok = branch.get_from_and_to_objects()

        return self.find_port_for_attachment(owner_object=obj_to)

    def get_persisted_attachment(self, api_object: ALL_DEV_TYPES, endpoint: str) -> Dict[str, Any]:
        """
        Read attachment metadata without creating placeholder diagram locations as a side effect.
        """
        if api_object is None:
            return dict()
        else:
            pass

        location = self.diagram.query_point(api_object)
        if location is None:
            return dict()
        else:
            return self.diagram.get_attachment(api_object=api_object, endpoint=endpoint)

    def find_port_for_attachment(self, owner_object: ALL_DEV_TYPES | None) -> OPTIONAL_PORT:
        """
        Resolve the graphics terminal for one owner object.
        """
        if owner_object is None:
            return None

        owner_graphic = self._query_terminal_owner_graphic(owner_object)
        if owner_graphic is None:
            return None

        return owner_graphic.get_terminal()

    def set_all_branch_drawing_styles(self, route_style: SchematicAutoRouteStyle) -> None:
        """
        Set one automatic drawing style on all registered schematic branch widgets.

        :param route_style: Requested automatic branch drawing style.
        :return: ``None``.
        """
        branch_device_type: DeviceType
        graphic_object: object

        for branch_device_type in SCHEMATIC_BRANCH_DEVICE_TYPES:
            for graphic_object in self.graphics_manager.get_device_type_list(device_type=branch_device_type):
                if isinstance(graphic_object, LineGraphicTemplateItem):
                    graphic_object.set_branch_auto_route_style(route_style=route_style)
                else:
                    pass

    def add_api_branch(self,
                       branch: BRANCH_TYPES,
                       new_graphic_func: type[_LINE_GRAPHIC_T],
                       from_port: OPTIONAL_PORT = None,
                       to_port: OPTIONAL_PORT = None,
                       draw_labels: bool = True,
                       logger: Logger | None = None) -> _LINE_GRAPHIC_T | None:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param new_graphic_func: New graphic object to use if needed
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels by default?
        :param logger: Logger
        """
        if logger is None:
            logger = Logger()

        # search for the api object, because it may be created already
        graphic_object = self._query_graphic_of_type(elm=branch, graphic_type=new_graphic_func)

        if graphic_object is None:

            if from_port is None and to_port is None:
                from_port, to_port = self.find_ports(branch=branch)
            elif from_port is not None and to_port is None:
                to_port = self.find_to_port(branch=branch)

            if from_port is not None and to_port is not None and (from_port != to_port):

                # Create new graphics object
                graphic_object = new_graphic_func(from_port,
                                                  to_port,
                                                  self,
                                                  5,
                                                  branch,
                                                  draw_labels)

                self.add_to_scene(graphic_object=graphic_object)

                if self.is_loading_diagram():
                    pass
                else:
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
                     logger: Logger | None = None) -> Union[LineGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param logger: Logger
        :return: LineGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=LineGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_dc_line(self,
                        branch: DcLine,
                        from_port: OPTIONAL_PORT = None,
                        to_port: OPTIONAL_PORT = None,
                        draw_labels: bool = True,
                        logger: Logger | None = None) -> Union[DcLineGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param logger: Logger
        :return: DcLineGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=DcLineGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_hvdc(self,
                     branch: HvdcLine,
                     from_port: OPTIONAL_PORT = None,
                     to_port: OPTIONAL_PORT = None,
                     draw_labels: bool = True,
                     logger: Logger | None = None) -> Union[HvdcGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param logger: Logger
        :return: SeriesReactanceGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=HvdcGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_vsc(self,
                    elm: VSC,
                    x: float | None = None,
                    y: float | None = None,
                    r: float = 0.0,
                    logger: Logger | None = None) -> Union[VscGraphicItem, VscGraphicItem3Term, None]:
        """
        add API VSC to the Scene
        :param elm: VSC instance
        :param x: Optional x position (if None, uses elm.x)
        :param y: Optional y position (if None, uses elm.y)
        :param r: Rotation in degrees
        :param logger: Logger
        :return: VscGraphicItem or None
        """
        if logger is None:
            logger = Logger()

        # search for the api object, because it may be created already
        graphic_object = self.graphics_manager.query(elm=elm)

        if graphic_object is None:
            if elm.is_3term():
                # Create new VSC graphics
                graphic_object = self.create_vsc_graphics_3term(elm=elm, x=x, y=y)

                # Register in graphics manager
                self.graphics_manager.add_device(elm=elm, graphic=graphic_object)

                # Add to scene
                self.add_to_scene(graphic_object=graphic_object)

                # Find ports for all three terminals
                port_ac = self.find_port(bus=elm.bus_to)
                port_dcp = self.find_port(bus=elm.bus_from)
                port_dcn = self.find_port(bus=elm.bus_dc_n)

                # Create connection lines (following the same pattern as interactive creation)
                if port_ac is not None:
                    # Create line from bus port to VSC AC terminal
                    conn_line_ac = LineGraphicTemplateItem(
                        from_port=port_ac,  # from bus port
                        to_port=graphic_object.terminal_ac,  # to VSC terminal
                        editor=self
                    )

                    # Set connection in VSC
                    if elm.bus_to is not None:
                        graphic_object.set_connection(TerminalType.AC, elm.bus_to, conn_line_ac)

                    # Add connection line to scene
                    self.add_to_scene(conn_line_ac)

                if port_dcp is not None:
                    # Create line from bus port to VSC DC+ terminal
                    conn_line_dcp = LineGraphicTemplateItem(
                        from_port=port_dcp,  # from bus port
                        to_port=graphic_object.terminal_dc_p,  # to VSC terminal
                        editor=self
                    )

                    # Set connection in VSC
                    if elm.bus_from is not None:
                        graphic_object.set_connection(TerminalType.DC_P, elm.bus_from, conn_line_dcp)

                    # Add connection line to scene
                    self.add_to_scene(conn_line_dcp)

                if port_dcn is not None:
                    # Create line from bus port to VSC DC- terminal
                    conn_line_dcn = LineGraphicTemplateItem(
                        from_port=port_dcn,  # from bus port
                        to_port=graphic_object.terminal_dc_n,  # to VSC terminal
                        editor=self
                    )

                    # Set connection in VSC
                    if elm.bus_dc_n is not None:
                        graphic_object.set_connection(TerminalType.DC_N, elm.bus_dc_n, conn_line_dcn)

                    # Add connection line to scene
                    self.add_to_scene(conn_line_dcn)

                graphic_object.set_rotation_angle(angle_degrees=r, persist=False)

                # Update diagram element
                self.update_diagram_element(device=elm,
                                            x=x,
                                            y=y,
                                            w=graphic_object.w,
                                            h=graphic_object.h,
                                            r=r,
                                            draw_labels=graphic_object.draw_labels,
                                            graphic_object=graphic_object)
            else:
                # Find ports for the terminals
                from_port = self.find_port(bus=elm.bus_to)
                to_port = self.find_port(bus=elm.bus_from)

                self.add_api_branch(branch=elm,
                                    new_graphic_func=VscGraphicItem,
                                    from_port=from_port,
                                    to_port=to_port,
                                    draw_labels=True,
                                    logger=logger)
        else:
            logger.add_info("VSC graphics already exist", device=elm.name)

        return graphic_object

    def add_api_upfc(self,
                     branch: UPFC,
                     from_port: OPTIONAL_PORT = None,
                     to_port: OPTIONAL_PORT = None,
                     draw_labels: bool = True,
                     logger: Logger | None = None) -> Union[UpfcGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param logger: Logger
        :return: SeriesReactanceGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=UpfcGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_series_reactance(self,
                                 branch: SeriesReactance,
                                 from_port: OPTIONAL_PORT = None,
                                 to_port: OPTIONAL_PORT = None,
                                 draw_labels: bool = True,
                                 logger: Logger | None = None) -> Union[SeriesReactanceGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param logger: Logger
        :return: SeriesReactanceGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=SeriesReactanceGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_transformer(self,
                            branch: Transformer2W,
                            from_port: OPTIONAL_PORT = None,
                            to_port: OPTIONAL_PORT = None,
                            draw_labels: bool = True,
                            logger: Logger | None = None) -> Union[TransformerGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param logger: Logger
        :return: TransformerGraphicItem or None
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=TransformerGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_winding(self,
                        branch: Winding,
                        from_port: OPTIONAL_PORT = None,
                        to_port: OPTIONAL_PORT = None,
                        draw_labels: bool = True,
                        logger: Logger | None = None) -> Union[WindingGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param logger: Logger
        :return: WindingGraphicItem or None
        """

        terminal_bus = branch.bus_from
        terminal_graphics = self._query_bus_graphic(terminal_bus)

        if terminal_graphics is None:
            return None
        else:
            return self.add_api_branch(branch=branch,
                                       new_graphic_func=WindingGraphicItem,
                                       from_port=from_port,
                                       to_port=terminal_graphics.get_terminal(),
                                       draw_labels=draw_labels,
                                       logger=logger)

    def add_api_switch(self,
                       branch: Switch,
                       from_port: OPTIONAL_PORT = None,
                       to_port: OPTIONAL_PORT = None,
                       draw_labels: bool = True,
                       logger: Logger | None = None) -> Union[SwitchGraphicItem, None]:
        """
        add API branch to the Scene
        :param branch: Branch instance
        :param from_port: Connection port from (optional)
        :param to_port: Connection port to (optional)
        :param draw_labels: Draw labels?
        :param logger: Logger
        """

        return self.add_api_branch(branch=branch,
                                   new_graphic_func=SwitchGraphicItem,
                                   from_port=from_port,
                                   to_port=to_port,
                                   draw_labels=draw_labels,
                                   logger=logger)

    def add_api_transformer_3w(self, elm: Transformer3W, set_voltage: bool = False):
        """
        add API branch to the Scene
        :param elm: Branch instance
        :param set_voltage:
        """

        tr3_graphic_object = self.create_transformer_3w_graphics(elm=elm, x=elm.x, y=elm.y)

        port1 = self.find_port(bus=elm.bus1)
        port2 = self.find_port(bus=elm.bus2)
        port3 = self.find_port(bus=elm.bus3)

        conn1 = WindingGraphicItem(from_port=tr3_graphic_object.terminals[0],
                                   to_port=port1,
                                   editor=self)
        tr3_graphic_object.set_connection(i=0, bus=elm.bus1, conn=conn1, set_voltage=set_voltage)

        conn2 = WindingGraphicItem(from_port=tr3_graphic_object.terminals[1],
                                   to_port=port2,
                                   editor=self)
        tr3_graphic_object.set_connection(i=1, bus=elm.bus2, conn=conn2, set_voltage=set_voltage)

        conn3 = WindingGraphicItem(from_port=tr3_graphic_object.terminals[2],
                                   to_port=port3,
                                   editor=self)
        tr3_graphic_object.set_connection(i=2, bus=elm.bus3, conn=conn3, set_voltage=set_voltage)

        self.update_diagram_element(device=elm,
                                    x=elm.x,
                                    y=elm.y,
                                    w=80,
                                    h=80,
                                    r=0,
                                    draw_labels=True,
                                    graphic_object=tr3_graphic_object)

        self.update_diagram_element(device=conn1._api_object, graphic_object=conn1)
        self.update_diagram_element(device=conn2._api_object, graphic_object=conn2)
        self.update_diagram_element(device=conn3._api_object, graphic_object=conn3)

        return tr3_graphic_object

    def add_api_transformer_nw(self, elm: TransformerNW, set_voltage: bool = False):
        """
        Add API TransformerNW to the Scene
        :param elm: TransformerNW instance
        :param set_voltage:
        """

        trn_graphic_object = self.create_transformer_nw_graphics(elm=elm, x=elm.x, y=elm.y)

        for i, winding in enumerate(elm.windings[:trn_graphic_object.n_windings]):
            terminal_bus = winding.bus_from
            port = self.find_port(bus=terminal_bus)
            if port is None:
                continue

            conn = WindingGraphicItem(from_port=trn_graphic_object.terminals[i],
                                      to_port=port,
                                      editor=self)
            trn_graphic_object.set_connection(i=i, bus=terminal_bus, conn=conn, set_voltage=set_voltage)
            self.update_diagram_element(device=conn._api_object, graphic_object=conn)

        self.update_diagram_element(device=elm,
                                    x=elm.x,
                                    y=elm.y,
                                    w=80,
                                    h=80,
                                    r=0,
                                    draw_labels=True,
                                    graphic_object=trn_graphic_object)

        return trn_graphic_object

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
        bus_f_graphics = self._query_fluid_node_graphic(branch.source)
        bus_t_graphics = self._query_fluid_node_graphic(branch.target)

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
        self.diagram.copy_layout_state(source_api_object=line, target_api_object=hvdc)

        # add device to the schematic
        graphic_object = self.add_api_hvdc(branch=hvdc,
                                           from_port=line_graphic.get_terminal_from(),
                                           to_port=line_graphic.get_terminal_to(),
                                           draw_labels=line_graphic.draw_labels)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete_with_dialogue from the schematic
        self._remove_from_scene(line_graphic)

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
        self.diagram.copy_layout_state(source_api_object=line, target_api_object=transformer)

        # add device to the schematic
        graphic_object = self.add_api_transformer(branch=transformer,
                                                  from_port=line_graphic.get_terminal_from(),
                                                  to_port=line_graphic.get_terminal_to(),
                                                  draw_labels=line_graphic.draw_labels)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete_with_dialogue from the schematic
        self._remove_from_scene(line_graphic)

        self.update_diagram_element(device=transformer, x=0, y=0, w=0, h=0, r=0,
                                    draw_labels=graphic_object.draw_labels,
                                    graphic_object=graphic_object)
        # self.delete_element_utility_function(device=line)

    def convert_line_to_vsc(self, line: Line, line_graphic: LineGraphicItem):
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :param line_graphic: LineGraphicItem
        :return: Nothing
        """
        vsc = self.circuit.convert_line_to_vsc(line)
        self.diagram.copy_layout_state(source_api_object=line, target_api_object=vsc)

        # add device to the schematic
        graphic_object = self.add_api_vsc(elm=vsc,
                                          x=vsc.x,
                                          y=vsc.y)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete_with_dialogue from the schematic
        self._remove_from_scene(line_graphic)

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
        self.diagram.copy_layout_state(source_api_object=line, target_api_object=upfc)

        # add device to the schematic
        graphic_object = self.add_api_upfc(branch=upfc,
                                           from_port=line_graphic.get_terminal_from(),
                                           to_port=line_graphic.get_terminal_to(),
                                           draw_labels=line_graphic.draw_labels)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete_with_dialogue from the schematic
        self._remove_from_scene(line_graphic)

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
        self.diagram.copy_layout_state(source_api_object=line, target_api_object=series_reactance)

        # add device to the schematic
        graphic_object = self.add_api_series_reactance(branch=series_reactance,
                                                       from_port=line_graphic.get_terminal_from(),
                                                       to_port=line_graphic.get_terminal_to(),
                                                       draw_labels=line_graphic.draw_labels)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete_with_dialogue from the schematic
        self._remove_from_scene(line_graphic)

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
        self.diagram.copy_layout_state(source_api_object=line, target_api_object=switch)

        # add device to the schematic
        graphic_object = self.add_api_switch(branch=switch,
                                             from_port=line_graphic.get_terminal_from(),
                                             to_port=line_graphic.get_terminal_to(),
                                             draw_labels=line_graphic.draw_labels)
        self.add_to_scene(graphic_object)

        # update position
        graphic_object.update_ports()

        # delete_with_dialogue from the schematic
        self._remove_from_scene(line_graphic)

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
        self.diagram.copy_layout_state(source_api_object=element, target_api_object=line)

        # add device to the schematic
        graphic_object = self.add_api_line(branch=line,
                                           from_port=fl_from.get_terminal(),
                                           to_port=fl_to.get_terminal(),
                                           draw_labels=True)
        self.add_to_scene(graphic_object)

        # update position
        fl_from.get_terminal().update()
        fl_to.get_terminal().update()

        # delete_with_dialogue from the schematic
        self._remove_from_scene(item_graphic)

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

        bus_graphic_object = self._query_bus_graphic(gen.bus)

        # add device to the schematic
        if bus_graphic_object is not None:

            # create the battery at the bus
            bus_graphic_object.add_battery(battery)

            # Remove the original generator because now it is a battery
            self.remove_element(device=graphic_object.api_object,
                                graphic_object=graphic_object,
                                delete_from_db=True)
        else:
            raise Exception("Bus graphics not found! this is likely a bug")

    def convert_hvdc_line_to_vsc_system(self, hvdc_line: HvdcLine):
        """
        Convert a HvdcLine to the corresponding VSC-DcLine-VSC system
        :param hvdc_line: HvdcLine
        """

        hvdc_graphics = self._query_hvdc_graphic(hvdc_line)

        (ac_bus_1, ac_bus_2,
         dc_bus_1, dc_bus_2,
         conv1, conv2, dc_line) = self.circuit.convert_hvdc_line_to_vsc_system(hvdc_line=hvdc_line)

        bus1_graphics = self.diagram.query_point(ac_bus_1)
        bus2_graphics = self.diagram.query_point(ac_bus_2)
        dc_graphics_1 = self.add_api_bus(bus=dc_bus_1,
                                         x0=int(bus1_graphics.x),
                                         y0=int(bus1_graphics.y),
                                         injections_by_tpe=dict())
        dc_graphics_2 = self.add_api_bus(bus=dc_bus_2,
                                         x0=int(bus2_graphics.x),
                                         y0=int(bus2_graphics.y),
                                         injections_by_tpe=dict())

        self.add_to_scene(dc_graphics_1)
        self.add_to_scene(dc_graphics_2)

        self.add_api_dc_line(dc_line, from_port=dc_graphics_1.terminal, to_port=dc_graphics_2.terminal)
        self.add_api_vsc(conv1, x=0, y=0)
        self.add_api_vsc(conv2, x=0, y=0)

        if hvdc_graphics is not None:
            self._remove_from_scene(hvdc_graphics)

    def add_object_to_the_schematic(
            self,
            elm: ALL_DEV_TYPES,
            injections_by_bus: Union[None, Dict[Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]] = None,
            injections_by_fluid_node: Union[None, Dict[FluidNode, Dict[DeviceType, List[FLUID_TYPES]]]] = None,
            injections_by_cn: Union[None, Dict[Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]] = None,
            logger: Logger | None = None):
        """

        :param elm:
        :param injections_by_bus:
        :param injections_by_fluid_node:
        :param injections_by_cn:
        :param logger:
        :return:
        """
        if logger is None:
            logger = Logger()

        if self.graphics_manager.query(elm=elm) is None:

            if isinstance(elm, Bus):

                if not elm.internal:  # 3w transformer buses are not represented
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
                graphic_obj = self.add_api_transformer_3w(elm, set_voltage=False)

            elif isinstance(elm, TransformerNW):
                graphic_obj = self.add_api_transformer_nw(elm, set_voltage=False)

            elif isinstance(elm, HvdcLine):
                graphic_obj = self.add_api_hvdc(elm)

            elif isinstance(elm, SeriesReactance):
                graphic_obj = self.add_api_series_reactance(elm)

            elif isinstance(elm, Switch):
                graphic_obj = self.add_api_switch(elm)

            elif isinstance(elm, VSC):
                graphic_obj = self.add_api_vsc(elm=elm,
                                               x=elm.x,
                                               y=elm.y)

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
                                  lines: List[Line],
                                  dc_lines: List[DcLine],
                                  transformers2w: List[Transformer2W],
                                  transformers3w: List[Transformer3W],
                                  transformers_nw: List[TransformerNW],
                                  hvdc_lines: List[HvdcLine],
                                  vsc_devices: List[VSC],
                                  upfc_devices: List[UPFC],
                                  switches: List[Switch],
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
        :param transformers_nw: list of TransformerNW Objects
        :param hvdc_lines: list of HvdcLine objects
        :param vsc_devices: list Vsc objects
        :param upfc_devices: List of UPFC devices
        :param switches: List of switches
        :param fluid_nodes: List of FluidNode devices
        :param fluid_paths: List of FluidPath devices
        :param injections_by_bus:
        :param injections_by_fluid_node:
        :param explode_factor: factor of "explosion": Separation of the nodes factor
        :param prog_func: progress report function
        :param text_func: Text report function
        """
        # --------------------------------------------------------------------------------------------------------------
        # first create the buses
        if text_func is not None:
            text_func('Creating schematic buses')

        nn = len(buses)
        for i, bus in enumerate(buses):

            if not bus.internal:  # 3w transformer buses are not represented

                if prog_func is not None:
                    prog_func((i + 1) / nn * 100.0)

                graphic_obj = self.add_api_bus(bus=bus,
                                               injections_by_tpe=injections_by_bus.get(bus, dict()),
                                               explode_factor=explode_factor)
                self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------

        if text_func is not None:
            text_func('Creating schematic Fluid nodes devices')

        nn = len(fluid_nodes)
        for i, elm in enumerate(fluid_nodes):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_fluid_node(node=elm,
                                                  injections_by_tpe=injections_by_fluid_node.get(elm, dict()))

            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic line devices')

        nn = len(lines)
        for i, branch in enumerate(lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_line(branch)
            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic line devices')

        nn = len(dc_lines)
        for i, branch in enumerate(dc_lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_dc_line(branch)
            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic transformer devices')

        nn = len(transformers2w)
        for i, branch in enumerate(transformers2w):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_transformer(branch)
            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic transformer3w devices')

        nn = len(transformers3w)
        for i, elm in enumerate(transformers3w):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_transformer_3w(elm, set_voltage=False)
            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic transformerNW devices')

        nn = len(transformers_nw)
        for i, elm in enumerate(transformers_nw):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_transformer_nw(elm, set_voltage=False)
            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic HVDC devices')

        nn = len(hvdc_lines)
        for i, branch in enumerate(hvdc_lines):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_hvdc(branch)
            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic VSC devices')

        nn = len(vsc_devices)
        for i, branch in enumerate(vsc_devices):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_vsc(elm=branch,
                                           x=branch.x,
                                           y=branch.y)
            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic UPFC devices')

        nn = len(upfc_devices)
        for i, branch in enumerate(upfc_devices):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_upfc(branch)
            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic switches')

        nn = len(switches)
        for i, branch in enumerate(switches):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_switch(branch)
            self.add_to_scene(graphic_obj)

        # --------------------------------------------------------------------------------------------------------------
        if text_func is not None:
            text_func('Creating schematic Fluid paths devices')

        nn = len(fluid_paths)
        for i, elm in enumerate(fluid_paths):

            if prog_func is not None:
                prog_func((i + 1) / nn * 100.0)

            graphic_obj = self.add_api_fluid_path(elm)
            self.add_to_scene(graphic_obj)

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

                graphic_object = self._query_bus_graphic(bus)

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
                graphic_object = self._query_bus_graphic(bus)

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
        palette = self.palette()
        ACTIVE['color'] = QColor(palette.color(palette.ColorGroup.Active, palette.ColorRole.WindowText))
        ACTIVE['text'] = QColor(palette.color(palette.ColorGroup.Active, palette.ColorRole.Text))
        ACTIVE['background'] = QColor(palette.color(palette.ColorGroup.Active, palette.ColorRole.Window))

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

            graphic_obj = self._query_bus_graphic(bus)
            if graphic_obj is not None:
                graphic_obj.add_big_marker(color=color)
                graphic_obj.setSelected(True)

    def set_big_bus_marker_colours(self,
                                   buses: List[Bus],
                                   colors: Iterable[QColor],
                                   tool_tips: Union[None, List[str]] = None):
        """
        Set a big marker at the selected buses with the matching colours
        :param buses: list of Bus objects
        :param colors: list of colour to use
        :param tool_tips: list of tool tips (optional)
        """

        if tool_tips:
            for bus, color, tool_tip in zip(buses, colors, tool_tips):

                graphic_obj = self._query_bus_graphic(bus)

                if graphic_obj is not None:
                    graphic_obj.add_big_marker(color=color, tool_tip_text=tool_tip)
                    graphic_obj.setSelected(True)
        else:
            for bus, color in zip(buses, colors):

                graphic_obj = self._query_bus_graphic(bus)

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
        if not self.diagram.use_api_colors:
            self.recolour_mode()

    def set_light_mode(self) -> None:
        """
        Set the light theme
        :return:
        """
        if not self.diagram.use_api_colors:
            self.recolour_mode()

    def _sync_multiwinding_transformer_result_colours(self) -> None:
        """
        Propagate winding branch colours to the corresponding winding circles in
        multi-winding transformer graphics.
        """
        for transformer in self.circuit.transformers3w:
            graphic_object = self._query_transformer3w_graphic(transformer)
            if graphic_object is None:
                continue

            for i, conn in enumerate(graphic_object.connection_lines):
                if conn is None:
                    graphic_object.set_winding_color(i, graphic_object.color)
                else:
                    graphic_object.set_winding_color(i, conn._route_item.pen().color())

        for transformer in self.circuit.transformers_nw:
            graphic_object = self._query_transformer_nw_graphic(transformer)
            if graphic_object is None:
                continue

            for i, conn in enumerate(graphic_object.connection_lines):
                if conn is None:
                    graphic_object.set_winding_color(i, graphic_object.color)
                else:
                    graphic_object.set_winding_color(i, conn._route_item.pen().color())

    def _get_voltage_result_color(self,
                                  value: float,
                                  cmap: palettes.Colormaps | None,
                                  voltage_cmap: Callable) -> QColor:
        """

        :param value:
        :param cmap:
        :param voltage_cmap:
        :return:
        """
        a = 255
        if cmap == palettes.Colormaps.Green2Red:
            b, g, r = palettes.green_to_red_bgr(value)
        elif cmap == palettes.Colormaps.Heatmap:
            b, g, r = palettes.heatmap_palette_bgr(value)
        elif cmap == palettes.Colormaps.TSO:
            b, g, r = palettes.tso_substation_palette_bgr(value)
        else:
            r, g, b, a = voltage_cmap(value)
            r *= 255
            g *= 255
            b *= 255
            a *= 255
        return QColor(r, g, b, a)

    @staticmethod
    def _get_branch_result_color(value: float,
                                 cmap: palettes.Colormaps | None,
                                 loading_cmap: Callable,
                                 nominal_voltage: float) -> QColor:
        """

        :param value:
        :param cmap:
        :param loading_cmap:
        :param nominal_voltage:
        :return:
        """
        a = 255
        if cmap == palettes.Colormaps.Green2Red:
            b, g, r = palettes.green_to_red_bgr(value)
        elif cmap == palettes.Colormaps.Heatmap:
            b, g, r = palettes.heatmap_palette_bgr(value)
        elif cmap == palettes.Colormaps.TSO:
            b, g, r = palettes.tso_line_palette_bgr(nominal_voltage, value)
        else:
            r, g, b, a = loading_cmap(value)
            r *= 255
            g *= 255
            b *= 255
            a *= 255
        return QColor(r, g, b, a)

    def _colour_bus_results(self,
                            Sbus: CxVec,
                            bus_active: IntVec,
                            vabs: Vec,
                            vang: Vec,
                            vnorm: Vec,
                            types: IntVec | None,
                            bus_types: list[str],
                            voltage_cmap: Callable,
                            cmap: palettes.Colormaps | None,
                            use_flow_based_width: bool,
                            apply_result_coloring: bool = True) -> None:
        """

        :param Sbus:
        :param bus_active:
        :param vabs:
        :param vang:
        :param vnorm:
        :param types:
        :param bus_types:
        :param voltage_cmap:
        :param cmap:
        :param use_flow_based_width:
        :return:
        """
        nbus = self.circuit.get_bus_number()
        if nbus != len(vnorm):
            error_msg(self.tr("Bus results length differs from the number of Bus results. \n"
                      "Did you change the number of devices? If so, re-run the simulation."))
            return

        for i, bus in enumerate(self.circuit.buses):
            graphic_object = self._query_bus_graphic(bus)
            if graphic_object is None:
                continue

            if bus_active[i]:
                graphic_object.set_values(i=i,
                                          Vm=vabs[i],
                                          Va=vang[i],
                                          P=Sbus[i].real if Sbus is not None else None,
                                          Q=Sbus[i].imag if Sbus is not None else None,
                                          tpe=bus_types[int(types[i])] if types is not None else None)
                if apply_result_coloring:
                    graphic_object.set_tile_color(self._get_voltage_result_color(vnorm[i], cmap, voltage_cmap))
                else:
                    graphic_object.update_color()
                if use_flow_based_width:
                    graphic_object.change_size(w=graphic_object.w)
            else:
                graphic_object.set_tile_color(QColor(115, 115, 115, 255))
                graphic_object.clear_label()

    def _colour_branch_results(self,
                               Sf: CxVec | None,
                               St: CxVec | None,
                               loadings: CxVec,
                               losses: CxVec | None,
                               br_active: IntVec,
                               hvdc_Pf: Vec | None,
                               loading_label: str,
                               use_flow_based_width: bool,
                               min_branch_width: int,
                               max_branch_width: int,
                               loading_cmap: Callable,
                               cmap: palettes.Colormaps | None,
                               ma: Vec | None,
                               tau: Vec | None,
                               is_three_phase: bool = False) -> float | None:
        """

        :param Sf:
        :param St:
        :param loadings:
        :param losses:
        :param br_active:
        :param hvdc_Pf:
        :param loading_label:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param loading_cmap:
        :param cmap:
        :param ma:
        :param tau:
        :param is_three_phase:
        :return:
        """
        if Sf is None or len(Sf) == 0:
            return 1.0

        lnorm = np.abs(loadings)
        lnorm[lnorm == np.inf] = 0
        sf_abs = np.abs(Sf)
        max_flow = sf_abs.max()

        if hvdc_Pf is not None and len(hvdc_Pf) > 0:
            max_flow = max(max_flow, np.abs(hvdc_Pf).max())

        nbr = self.circuit.get_branch_number(add_vsc=False, add_hvdc=False, add_switch=True)
        if not ((nbr == len(Sf) and not is_three_phase) or (is_three_phase and 3 * nbr == len(Sf))):
            error_msg(self.tr("Branch results length differs from the number of branch results. \n"
                      "Did you change the number of devices? If so, re-run the simulation."))
            return None

        ph = np.array([0, 1, 2])
        for i, branch in enumerate(self.circuit.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True)):
            graphic_object = self._query_line_graphic(branch)
            if graphic_object is None:
                continue

            if br_active[i]:
                if is_three_phase:
                    k_idx = 3 * i + ph
                    l_color_val = max(lnorm[k_idx])
                    tooltip = str(i) + ': ' + branch.name

                    for ph_idx, pname in enumerate(['a', 'b', 'c']):
                        k = 3 * i + ph_idx
                        tooltip += f'\n{loading_label} {pname}: {lnorm[k] * 100:10.4f} [%]'
                        tooltip += f'\nPf {pname}:\t{Sf[k]:10.4f} [MVA]'
                        if St is not None:
                            tooltip += f'\nPt {pname}:\t{St[k]:10.4f} [MVA]'
                        if losses is not None:
                            tooltip += f'\nLoss {pname}:\t{losses[k]:10.4f} [MVA]'
                        if branch.device_type == DeviceType.Transformer2WDevice:
                            if ma is not None:
                                ma_idx = _get_branch_result_index(i, ph_idx, ma, is_three_phase=True)
                                tooltip += f'\ntap module {pname}:\t{ma[ma_idx]:10.4f}'
                            if tau is not None:
                                tau_idx = _get_branch_result_index(i, ph_idx, tau, is_three_phase=True)
                                tooltip += f'\ntap angle {pname}:\t{tau[tau_idx]:10.4f} [rad]'
                        tooltip += "\n"
                    sf_norm = max(sf_abs[k_idx]) / max(max_flow, 1e-20)
                    arrow_sf = Sf[k_idx].sum()
                    arrow_st = St[k_idx].sum() if St is not None else None
                else:
                    l_color_val = lnorm[i]
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
                        if tau is not None:
                            tooltip += '\ntap angle:\t' + "{:10.4f}".format(tau[i]) + ' rad'
                    sf_norm = sf_abs[i] / max(max_flow, 1e-20)
                    arrow_sf = Sf[i]
                    arrow_st = St[i] if St is not None else None

                width = int(np.floor(min_branch_width + sf_norm * (max_branch_width - min_branch_width))) \
                    if use_flow_based_width else graphic_object.pen_width
                color = self._get_branch_result_color(l_color_val,
                                                      cmap,
                                                      loading_cmap,
                                                      branch.get_max_bus_nominal_voltage())
                graphic_object.setToolTipText(tooltip)
                graphic_object.set_colour(color, width, Qt.PenStyle.SolidLine)
                if isinstance(graphic_object, LineGraphicTemplateItem):
                    graphic_object.set_arrows_with_power(Sf=arrow_sf, St=arrow_st)
            else:
                width = graphic_object.pen_width
                graphic_object.set_pen(QPen(QColor(115, 115, 115, 255), width, Qt.PenStyle.DashLine))
                graphic_object.setToolTipText("")
                if isinstance(graphic_object, LineGraphicTemplateItem):
                    graphic_object.set_arrows_with_power(Sf=None, St=None)

        self._sync_multiwinding_transformer_result_colours()
        return max_flow

    def _colour_vsc_results(self,
                            vsc_Pf: Vec | None,
                            vsc_Pt: Vec | None,
                            vsc_Qt: Vec | None,
                            vsc_losses: Vec | None,
                            vsc_loading: Vec | None,
                            vsc_active: IntVec | None,
                            loading_label: str,
                            use_flow_based_width: bool,
                            min_branch_width: int,
                            max_branch_width: int,
                            loading_cmap: Callable,
                            cmap: palettes.Colormaps | None,
                            max_flow: float) -> None:
        """

        :param vsc_Pf:
        :param vsc_Pt:
        :param vsc_Qt:
        :param vsc_losses:
        :param vsc_loading:
        :param vsc_active:
        :param loading_label:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param loading_cmap:
        :param cmap:
        :param max_flow:
        :return:
        """
        if vsc_Pf is None:
            return

        vsc_sending_power_norm = np.abs(vsc_Pt if vsc_Qt is None else vsc_Pt + 1j * vsc_Qt) / (max_flow + 1e-20)
        if self.circuit.get_vsc_number() != len(vsc_Pf):
            error_msg(self.tr("VSC results length differs from the number of VSC results. \n"
                      "Did you change the number of devices? If so, re-run the simulation."))
            return

        for i, elm in enumerate(self.circuit.vsc_devices):
            graphic_object = self._query_vsc_graphic(elm)
            if graphic_object is None:
                continue

            if vsc_active[i]:
                width = int(np.floor(min_branch_width + vsc_sending_power_norm[i] *
                                     (max_branch_width - min_branch_width))) \
                    if use_flow_based_width else graphic_object.pen_width
                style = Qt.PenStyle.SolidLine if elm.active else Qt.PenStyle.DashLine
                color = self._get_branch_result_color(abs(vsc_loading[i]),
                                                      cmap,
                                                      loading_cmap,
                                                      elm.get_max_bus_nominal_voltage()) \
                    if elm.active else QColor(115, 115, 115, 255)

                tooltip = str(i) + ': ' + elm.name
                tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(abs(vsc_loading[i]) * 100) + ' [%]'
                tooltip += '\nPower (from):\t' + "{:10.4f}".format(vsc_Pf[i]) + ' [MW]'

                if vsc_Qt is None:
                    if vsc_losses is not None:
                        tooltip += '\nPower (to):\t' + "{:10.4f}".format(vsc_Pt[i]) + ' [MW]'
                        tooltip += '\nLosses: \t\t' + "{:10.4f}".format(vsc_losses[i]) + ' [MW]'
                        graphic_object.set_arrows_with_power_vsc(Pf=vsc_Pf[i], Pt=vsc_Pt[i], Qt=0.0)
                    else:
                        graphic_object.set_arrows_with_power_vsc(Pf=vsc_Pf[i], Pt=-vsc_Pf[i], Qt=0.0)
                else:
                    if vsc_losses is not None:
                        tooltip += '\nPower (to):\t' + "{:10.4f}".format(vsc_Pt[i]) + ' [MW]'
                        tooltip += '\nPower (to):\t' + "{:10.4f}".format(vsc_Qt[i]) + ' [Mvar]'
                        tooltip += '\nLosses: \t\t' + "{:10.4f}".format(vsc_losses[i]) + ' [MW]'
                        graphic_object.set_arrows_with_power_vsc(Pf=vsc_Pf[i], Pt=vsc_Pt[i], Qt=vsc_Qt[i])
                    else:
                        graphic_object.set_arrows_with_power_vsc(Pf=vsc_Pf[i], Pt=-vsc_Pf[i], Qt=vsc_Qt[i])

                graphic_object.setToolTipText(tooltip)
                graphic_object.set_colour(color, width, style)
            else:
                graphic_object.set_pen(QPen(QColor(115, 115, 115, 255),
                                            graphic_object.pen_width,
                                            Qt.PenStyle.DashLine))

    def _colour_hvdc_results(self,
                             hvdc_Pf: Vec | None,
                             hvdc_Pt: Vec | None,
                             hvdc_losses: Vec | None,
                             hvdc_loading: Vec | None,
                             hvdc_active: IntVec | None,
                             loading_label: str,
                             use_flow_based_width: bool,
                             min_branch_width: int,
                             max_branch_width: int,
                             loading_cmap: Callable,
                             cmap: palettes.Colormaps | None,
                             max_flow: float) -> None:
        """

        :param hvdc_Pf:
        :param hvdc_Pt:
        :param hvdc_losses:
        :param hvdc_loading:
        :param hvdc_active:
        :param loading_label:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param loading_cmap:
        :param cmap:
        :param max_flow:
        :return:
        """
        if hvdc_Pf is None:
            return

        hvdc_sending_power_norm = np.abs(hvdc_Pf) / (max_flow + 1e-20)
        if self.circuit.get_hvdc_number() != len(hvdc_Pf):
            error_msg(self.tr("HVDC results length differs from the number of HVDC results. \n"
                      "Did you change the number of devices? If so, re-run the simulation."))
            return

        for i, elm in enumerate(self.circuit.hvdc_lines):
            graphic_object = self._query_hvdc_graphic(elm)
            if graphic_object is None:
                continue

            if hvdc_active[i]:
                width = int(np.floor(min_branch_width + hvdc_sending_power_norm[i] *
                                     (max_branch_width - min_branch_width))) \
                    if use_flow_based_width else graphic_object.pen_width
                style = Qt.PenStyle.SolidLine if elm.active else Qt.PenStyle.DashLine
                color = self._get_branch_result_color(abs(hvdc_loading[i]),
                                                      cmap,
                                                      loading_cmap,
                                                      elm.get_max_bus_nominal_voltage()) \
                    if elm.active else QColor(115, 115, 115, 255)

                tooltip = str(i) + ': ' + elm.name
                tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(abs(hvdc_loading[i]) * 100) + ' [%]'
                tooltip += '\nPower (from):\t' + "{:10.4f}".format(hvdc_Pf[i]) + ' [MW]'

                if hvdc_losses is not None:
                    tooltip += '\nPower (to):\t' + "{:10.4f}".format(hvdc_Pt[i]) + ' [MW]'
                    tooltip += '\nLosses: \t\t' + "{:10.4f}".format(hvdc_losses[i]) + ' [MW]'
                    graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_Pf[i], Pt=hvdc_Pt[i])
                else:
                    graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_Pf[i], Pt=-hvdc_Pf[i])

                graphic_object.setToolTipText(tooltip)
                graphic_object.set_colour(color, width, style)
            else:
                graphic_object.set_pen(QPen(QColor(115, 115, 115, 255),
                                            graphic_object.pen_width,
                                            Qt.PenStyle.DashLine))

    def _colour_fluid_path_results(self, fluid_path_flow: Vec | None) -> None:
        """

        :param fluid_path_flow:
        :return:
        """
        if fluid_path_flow is None:
            return

        if self.circuit.get_fluid_paths_number() != len(fluid_path_flow):
            return

        for i, elm in enumerate(self.circuit.fluid_paths):
            graphic_object = self._query_fluid_path_graphic(elm)
            if graphic_object is not None:
                graphic_object.set_api_object_color()
                graphic_object.set_arrows_with_fluid_flow(flow=fluid_path_flow[i])

    def _colour_fluid_node_results(self,
                                   vabs: Vec,
                                   vang: Vec,
                                   Sbus: CxVec,
                                   types: IntVec | None,
                                   bus_types: list[str],
                                   fluid_node_p2x_flow: Vec | None,
                                   fluid_node_current_level: Vec | None,
                                   fluid_node_spillage: Vec | None,
                                   fluid_node_flow_in: Vec | None,
                                   fluid_node_flow_out: Vec | None) -> None:
        """

        :param vabs:
        :param vang:
        :param Sbus:
        :param types:
        :param bus_types:
        :param fluid_node_p2x_flow:
        :param fluid_node_current_level:
        :param fluid_node_spillage:
        :param fluid_node_flow_in:
        :param fluid_node_flow_out:
        :return:
        """
        if fluid_node_current_level is None:
            return

        if self.circuit.get_fluid_nodes_number() != len(fluid_node_current_level):
            return

        bus_index_dict: Dict[Bus, int] = self.circuit.get_bus_index_dict()
        for i, elm in enumerate(self.circuit.fluid_nodes):
            graphic_object = self._query_fluid_node_graphic(elm)
            if graphic_object is not None:
                bus_idx: int | None = None
                bus_vm: float | None = None
                bus_va: float | None = None
                bus_p: float | None = None
                bus_q: float | None = None
                bus_tpe: str | None = None

                if elm.bus is None:
                    pass
                else:
                    bus_idx = bus_index_dict.get(elm.bus, None)

                if bus_idx is None:
                    pass
                elif bus_idx < 0:
                    bus_idx = None
                elif bus_idx >= len(vabs) or bus_idx >= len(vang):
                    bus_idx = None
                else:
                    bus_vm = float(vabs[bus_idx])
                    bus_va = float(vang[bus_idx])

                    if Sbus is None:
                        pass
                    elif bus_idx >= len(Sbus):
                        pass
                    else:
                        bus_p = float(Sbus[bus_idx].real)
                        bus_q = float(Sbus[bus_idx].imag)

                    if types is None:
                        pass
                    elif bus_idx >= len(types):
                        pass
                    else:
                        bus_type_index: int = int(types[bus_idx])

                        if 0 <= bus_type_index < len(bus_types):
                            bus_tpe = bus_types[bus_type_index]
                        else:
                            pass

                graphic_object.set_api_object_color()
                graphic_object.set_fluid_values(
                    i=i,
                    Vm=bus_vm if bus_vm is not None else 0.0,
                    Va=bus_va if bus_va is not None else 0.0,
                    P=bus_p,
                    Q=bus_q,
                    tpe=bus_tpe,
                    fluid_node_p2x_flow=fluid_node_p2x_flow[i] if fluid_node_p2x_flow is not None else None,
                    fluid_node_current_level=fluid_node_current_level[i] if fluid_node_current_level is not None else None,
                    fluid_node_spillage=fluid_node_spillage[i] if fluid_node_spillage is not None else None,
                    fluid_node_flow_in=fluid_node_flow_in[i] if fluid_node_flow_in is not None else None,
                    fluid_node_flow_out=fluid_node_flow_out[i] if fluid_node_flow_out is not None else None,
                )

    def _clear_all_injection_results(self) -> None:
        """
        Clear every injection result overlay.

        :return: ``None``.
        """
        device_type: DeviceType

        for device_type in (
            DeviceType.GeneratorDevice,
            DeviceType.BatteryDevice,
            DeviceType.StaticGeneratorDevice,
            DeviceType.ShuntDevice,
            DeviceType.ControllableShuntDevice,
            DeviceType.LoadDevice,
            DeviceType.ExternalGridDevice,
            DeviceType.CurrentInjectionDevice,
        ):
            for graphic_object in self._get_device_type_graphics(device_type, InjectionTemplateGraphicItem):
                graphic_object.clear_result_visuals()

    def _build_injection_name_lookup(self, names: np.ndarray | list[str] | None) -> dict[str, int]:
        """
        Build a name-to-index lookup for injection result arrays.

        :param names: Result name sequence.
        :return: Lookup from device name to result index.
        """
        lookup: dict[str, int] = dict()
        counts: dict[str, int] = dict()

        if names is None:
            pass
        else:
            for name in names:
                name_str: str = str(name).strip()

                if name_str:
                    counts[name_str] = counts.get(name_str, 0) + 1
                else:
                    pass

            for index, name in enumerate(names):
                name_str = str(name).strip()

                # Ambiguous or blank result names cannot identify a unique device.
                if name_str and counts.get(name_str, 0) == 1:
                    lookup[name_str] = index
                else:
                    pass

        return lookup

    def _colour_generator_results(self,
                                  gen_p: Vec | None,
                                  gen_q: Vec | None,
                                  generator_lookup: dict[str, int]) -> None:
        """
        Colour generator injection results.

        :param gen_p: Generator active powers.
        :param gen_q: Generator reactive powers.
        :param generator_lookup: Generator result-name lookup.
        :return: ``None``.
        """
        generator_devices: list[Generator] = self.circuit.get_generators()
        generator_index: int
        generator: Generator

        # Result name vectors can be reordered by the engine, so named matches take priority.
        for generator_index, generator in enumerate(generator_devices):
            graphic_object = self._query_injection_graphic(generator)

            if graphic_object is None:
                pass
            else:
                result_index: int = _get_injection_result_index(
                    device_name=generator.name,
                    fallback_index=generator_index,
                    lookup=generator_lookup,
                )
                p_value: float | None = _get_optional_result_value(values=gen_p, index=result_index)
                q_value: float | None = _get_optional_result_value(values=gen_q, index=result_index)

                _apply_single_phase_injection_result(graphic_object=graphic_object,
                                                          device_name=generator.name,
                                                          tooltip_title="Generator results",
                                                          p_value=p_value,
                                                          q_value=q_value)

    def _colour_battery_results(self,
                                battery_p: Vec | None,
                                battery_q: Vec | None,
                                battery_lookup: dict[str, int]) -> None:
        """
        Colour battery injection results.

        :param battery_p: Battery active powers.
        :param battery_q: Battery reactive powers.
        :param battery_lookup: Battery result-name lookup.
        :return: ``None``.
        """
        battery_devices: list[Battery] = self.circuit.get_batteries()
        battery_index: int
        battery: Battery

        for battery_index, battery in enumerate(battery_devices):
            graphic_object = self._query_injection_graphic(battery)

            if graphic_object is None:
                pass
            else:
                result_index: int = _get_injection_result_index(
                    device_name=battery.name,
                    fallback_index=battery_index,
                    lookup=battery_lookup,
                )
                p_value: float | None = _get_optional_result_value(values=battery_p, index=result_index)
                q_value: float | None = _get_optional_result_value(values=battery_q, index=result_index)

                _apply_single_phase_injection_result(graphic_object=graphic_object,
                                                          device_name=battery.name,
                                                          tooltip_title="Battery results",
                                                          p_value=p_value,
                                                          q_value=q_value)

    def _colour_shunt_like_results(self,
                                   shunt_q: Vec | None,
                                   shunt_lookup: dict[str, int]) -> None:
        """
        Colour shunt-like injection results.

        :param shunt_q: Shunt-like reactive powers.
        :param shunt_lookup: Shunt-like result-name lookup.
        :return: ``None``.
        """
        shunt_like_devices: list[INJECTION_DEVICE_TYPES] = self.circuit.get_shunt_like_devices()
        shunt_index: int
        shunt_like_device: INJECTION_DEVICE_TYPES

        for shunt_index, shunt_like_device in enumerate(shunt_like_devices):
            graphic_object = self._query_injection_graphic(shunt_like_device)

            if graphic_object is None:
                pass
            else:
                result_index: int = _get_injection_result_index(
                    device_name=shunt_like_device.name,
                    fallback_index=shunt_index,
                    lookup=shunt_lookup,
                )
                q_value: float | None = _get_optional_result_value(values=shunt_q, index=result_index)

                if isinstance(shunt_like_device, ControllableShunt):
                    tooltip_title: str = "Controllable shunt results"
                else:
                    tooltip_title = "Shunt results"

                _apply_single_phase_injection_result(graphic_object=graphic_object,
                                                          device_name=shunt_like_device.name,
                                                          tooltip_title=tooltip_title,
                                                          p_value=None,
                                                          q_value=q_value)

    def _colour_static_generator_results(self, t_idx: int | None) -> None:
        """
        Colour static-generator injection results.

        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        static_generator_devices: list[StaticGenerator] = self.circuit.get_static_generators()
        static_generator: StaticGenerator

        for static_generator in static_generator_devices:
            graphic_object = self._query_injection_graphic(static_generator)

            if graphic_object is None:
                pass
            else:
                p_value: float = float(static_generator.get_P_at(t_idx))
                q_value: float = float(static_generator.get_Q_at(t_idx))

                _apply_single_phase_injection_result(graphic_object=graphic_object,
                                                          device_name=static_generator.name,
                                                          tooltip_title="Static generator setpoint",
                                                          p_value=_hide_zero_result_value(p_value),
                                                          q_value=_hide_zero_result_value(q_value))

    def _colour_load_results(self, t_idx: int | None) -> None:
        """
        Colour load injection results.

        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        load_devices: list[Load] = self.circuit.get_loads()
        load_device: Load

        for load_device in load_devices:
            graphic_object = self._query_injection_graphic(load_device)

            if graphic_object is None:
                pass
            else:
                p_value: float = -float(load_device.get_P_at(t_idx))
                q_value: float = -float(load_device.get_Q_at(t_idx))

                # Fall back to equivalent current channels when the ZIP power channels are empty.
                if p_value == 0.0 and q_value == 0.0:
                    p_value = -float(load_device.get_Ir_at(t_idx))
                    q_value = -float(load_device.get_Ii_at(t_idx))
                else:
                    pass

                _apply_single_phase_injection_result(graphic_object=graphic_object,
                                                          device_name=load_device.name,
                                                          tooltip_title="Load equivalent injection",
                                                          p_value=_hide_zero_result_value(p_value),
                                                          q_value=_hide_zero_result_value(q_value))

    def _colour_external_grid_results(self, t_idx: int | None) -> None:
        """
        Colour external-grid injection results.

        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        external_grid_devices: list[ExternalGrid] = self.circuit.get_external_grids()
        external_grid: ExternalGrid

        for external_grid in external_grid_devices:
            graphic_object = self._query_injection_graphic(external_grid)

            if graphic_object is None:
                pass
            else:
                p_value: float = -float(external_grid.get_P_at(t_idx))
                q_value: float = -float(external_grid.get_Q_at(t_idx))

                _apply_single_phase_injection_result(graphic_object=graphic_object,
                                                          device_name=external_grid.name,
                                                          tooltip_title="External grid equivalent injection",
                                                          p_value=_hide_zero_result_value(p_value),
                                                          q_value=_hide_zero_result_value(q_value))

    def _colour_current_injection_results(self, t_idx: int | None) -> None:
        """
        Colour current-injection results.

        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        current_injection_devices: list[CurrentInjection] = self.circuit.get_current_injections()
        current_injection: CurrentInjection

        for current_injection in current_injection_devices:
            graphic_object = self._query_injection_graphic(current_injection)

            if graphic_object is None:
                pass
            else:
                p_value: float = -float(current_injection.get_Ir_at(t_idx))
                q_value: float = -float(current_injection.get_Ii_at(t_idx))

                _apply_single_phase_injection_result(graphic_object=graphic_object,
                                                          device_name=current_injection.name,
                                                          tooltip_title="Current injection equivalent power",
                                                          p_value=_hide_zero_result_value(p_value),
                                                          q_value=_hide_zero_result_value(q_value))

    def _apply_three_phase_injection_result(self,
                                            graphic_object: InjectionTemplateGraphicItem,
                                            device_name: str,
                                            tooltip_title: str,
                                            qa: float | None,
                                            qb: float | None,
                                            qc: float | None,
                                            include_total_p: bool = False,
                                            pa: float | None = None,
                                            pb: float | None = None,
                                            pc: float | None = None) -> None:
        """
        Apply a three-phase result badge to an injection graphic.

        :param graphic_object: Injection graphic item.
        :param device_name: Injection device name.
        :param tooltip_title: Tooltip title.
        :param qa: Phase-a reactive power.
        :param qb: Phase-b reactive power.
        :param qc: Phase-c reactive power.
        :param include_total_p: Include aggregated active power in the badge.
        :param pa: Phase-a active power.
        :param pb: Phase-b active power.
        :param pc: Phase-c active power.
        :return: ``None``.
        """
        if qa is None and qb is None and qc is None:
            pass
        else:
            color: QColor = _get_injection_result_color(graphic_object=graphic_object)
            total_q: float = float((0.0 if qa is None else qa) +
                                   (0.0 if qb is None else qb) +
                                   (0.0 if qc is None else qc))
            lines: list[str] = list()

            if include_total_p:
                total_p: float = float((0.0 if pa is None else pa) +
                                       (0.0 if pb is None else pb) +
                                       (0.0 if pc is None else pc))
                lines.append(f"PΣ {total_p:+.1f} MW")
            else:
                pass

            lines.append(f"QΣ {total_q:+.1f} MVAr")

            tooltip_lines: list[str] = [device_name, tooltip_title]

            if include_total_p:
                if pa is None:
                    pass
                else:
                    tooltip_lines.append(f"Pa {pa:+.1f} MW")

                if pb is None:
                    pass
                else:
                    tooltip_lines.append(f"Pb {pb:+.1f} MW")

                if pc is None:
                    pass
                else:
                    tooltip_lines.append(f"Pc {pc:+.1f} MW")
            else:
                pass

            if qa is None:
                pass
            else:
                tooltip_lines.append(f"Qa {qa:+.1f} MVAr")

            if qb is None:
                pass
            else:
                tooltip_lines.append(f"Qb {qb:+.1f} MVAr")

            if qc is None:
                pass
            else:
                tooltip_lines.append(f"Qc {qc:+.1f} MVAr")

            graphic_object.set_result_visuals(lines=lines,
                                              tooltip="\n".join(tooltip_lines),
                                              color=color)

    def _colour_generator_results_3ph(self,
                                      gen_q_a: Vec | None,
                                      gen_q_b: Vec | None,
                                      gen_q_c: Vec | None,
                                      generator_lookup: dict[str, int]) -> None:
        """
        Colour three-phase generator results.

        :param gen_q_a: Generator phase-a reactive powers.
        :param gen_q_b: Generator phase-b reactive powers.
        :param gen_q_c: Generator phase-c reactive powers.
        :param generator_lookup: Generator result-name lookup.
        :return: ``None``.
        """
        generator_devices: list[Generator] = self.circuit.get_generators()
        index: int
        generator: Generator

        for index, generator in enumerate(generator_devices):
            graphic_object = self._query_injection_graphic(generator)

            if graphic_object is None:
                pass
            else:
                result_index: int = _get_injection_result_index(
                    device_name=generator.name,
                    fallback_index=index,
                    lookup=generator_lookup,
                )
                qa: float | None = None
                qb: float | None = None
                qc: float | None = None

                if gen_q_a is not None and result_index < len(gen_q_a):
                    qa = float(gen_q_a[result_index])
                else:
                    pass

                if gen_q_b is not None and result_index < len(gen_q_b):
                    qb = float(gen_q_b[result_index])
                else:
                    pass

                if gen_q_c is not None and result_index < len(gen_q_c):
                    qc = float(gen_q_c[result_index])
                else:
                    pass

                self._apply_three_phase_injection_result(graphic_object=graphic_object,
                                                         device_name=generator.name,
                                                         tooltip_title="Generator 3ph results",
                                                         qa=qa,
                                                         qb=qb,
                                                         qc=qc)

    def _colour_battery_results_3ph(self,
                                    battery_q_a: Vec | None,
                                    battery_q_b: Vec | None,
                                    battery_q_c: Vec | None,
                                    battery_lookup: dict[str, int]) -> None:
        """
        Colour three-phase battery results.

        :param battery_q_a: Battery phase-a reactive powers.
        :param battery_q_b: Battery phase-b reactive powers.
        :param battery_q_c: Battery phase-c reactive powers.
        :param battery_lookup: Battery result-name lookup.
        :return: ``None``.
        """
        battery_devices: list[Battery] = self.circuit.get_batteries()
        index: int
        battery: Battery

        for index, battery in enumerate(battery_devices):
            graphic_object = self._query_injection_graphic(battery)

            if graphic_object is None:
                pass
            else:
                result_index: int = _get_injection_result_index(
                    device_name=battery.name,
                    fallback_index=index,
                    lookup=battery_lookup,
                )
                qa: float | None = None
                qb: float | None = None
                qc: float | None = None

                if battery_q_a is not None and result_index < len(battery_q_a):
                    qa = float(battery_q_a[result_index])
                else:
                    pass

                if battery_q_b is not None and result_index < len(battery_q_b):
                    qb = float(battery_q_b[result_index])
                else:
                    pass

                if battery_q_c is not None and result_index < len(battery_q_c):
                    qc = float(battery_q_c[result_index])
                else:
                    pass

                self._apply_three_phase_injection_result(graphic_object=graphic_object,
                                                         device_name=battery.name,
                                                         tooltip_title="Battery 3ph results",
                                                         qa=qa,
                                                         qb=qb,
                                                         qc=qc)

    def _colour_shunt_like_results_3ph(self,
                                       shunt_q_a: Vec | None,
                                       shunt_q_b: Vec | None,
                                       shunt_q_c: Vec | None,
                                       shunt_lookup: dict[str, int]) -> None:
        """
        Colour three-phase shunt-like results.

        :param shunt_q_a: Shunt-like phase-a reactive powers.
        :param shunt_q_b: Shunt-like phase-b reactive powers.
        :param shunt_q_c: Shunt-like phase-c reactive powers.
        :param shunt_lookup: Shunt-like result-name lookup.
        :return: ``None``.
        """
        shunt_like_devices: list[INJECTION_DEVICE_TYPES] = self.circuit.get_shunt_like_devices()
        index: int
        shunt_like_device: INJECTION_DEVICE_TYPES

        for index, shunt_like_device in enumerate(shunt_like_devices):
            graphic_object = self._query_injection_graphic(shunt_like_device)

            if graphic_object is None:
                pass
            else:
                result_index: int = _get_injection_result_index(
                    device_name=shunt_like_device.name,
                    fallback_index=index,
                    lookup=shunt_lookup,
                )
                qa: float | None = None
                qb: float | None = None
                qc: float | None = None

                if shunt_q_a is not None and result_index < len(shunt_q_a):
                    qa = float(shunt_q_a[result_index])
                else:
                    pass

                if shunt_q_b is not None and result_index < len(shunt_q_b):
                    qb = float(shunt_q_b[result_index])
                else:
                    pass

                if shunt_q_c is not None and result_index < len(shunt_q_c):
                    qc = float(shunt_q_c[result_index])
                else:
                    pass

                if isinstance(shunt_like_device, ControllableShunt):
                    tooltip_title: str = "Controllable shunt 3ph results"
                else:
                    tooltip_title = "Shunt 3ph results"

                self._apply_three_phase_injection_result(graphic_object=graphic_object,
                                                         device_name=shunt_like_device.name,
                                                         tooltip_title=tooltip_title,
                                                         qa=qa,
                                                         qb=qb,
                                                         qc=qc)

    def _colour_static_generator_results_3ph(self, t_idx: int | None) -> None:
        """
        Colour three-phase static-generator results.

        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        static_generator_devices: list[StaticGenerator] = self.circuit.get_static_generators()
        static_generator: StaticGenerator

        for static_generator in static_generator_devices:
            graphic_object = self._query_injection_graphic(static_generator)

            if graphic_object is None:
                pass
            else:
                pa: float = float(static_generator.get_Pa_at(t_idx))
                pb: float = float(static_generator.get_Pb_at(t_idx))
                pc: float = float(static_generator.get_Pc_at(t_idx))
                qa: float = float(static_generator.get_Qa_at(t_idx))
                qb: float = float(static_generator.get_Qb_at(t_idx))
                qc: float = float(static_generator.get_Qc_at(t_idx))
                total_p: float = pa + pb + pc
                total_q: float = qa + qb + qc

                if total_p == 0.0 and total_q == 0.0:
                    pass
                else:
                    self._apply_three_phase_injection_result(graphic_object=graphic_object,
                                                             device_name=static_generator.name,
                                                             tooltip_title="Static generator 3ph setpoint",
                                                             qa=qa,
                                                             qb=qb,
                                                             qc=qc,
                                                             include_total_p=True,
                                                             pa=pa,
                                                             pb=pb,
                                                             pc=pc)

    def _colour_load_results_3ph(self, t_idx: int | None) -> None:
        """
        Colour three-phase load results.

        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        load_devices: list[Load] = self.circuit.get_loads()
        load_device: Load

        for load_device in load_devices:
            graphic_object = self._query_injection_graphic(load_device)

            if graphic_object is None:
                pass
            else:
                pa: float = -float(load_device.get_Pa_at(t_idx))
                pb: float = -float(load_device.get_Pb_at(t_idx))
                pc: float = -float(load_device.get_Pc_at(t_idx))
                qa: float = -float(load_device.get_Qa_at(t_idx))
                qb: float = -float(load_device.get_Qb_at(t_idx))
                qc: float = -float(load_device.get_Qc_at(t_idx))
                total_p: float = pa + pb + pc
                total_q: float = qa + qb + qc

                # Fall back to equivalent current channels when the ZIP power channels are empty.
                if total_p == 0.0 and total_q == 0.0:
                    pa = -float(load_device.get_Ir1_at(t_idx))
                    pb = -float(load_device.get_Ir2_at(t_idx))
                    pc = -float(load_device.get_Ir3_at(t_idx))
                    qa = -float(load_device.get_Ii1_at(t_idx))
                    qb = -float(load_device.get_Ii2_at(t_idx))
                    qc = -float(load_device.get_Ii3_at(t_idx))
                    total_p = pa + pb + pc
                    total_q = qa + qb + qc
                else:
                    pass

                if total_p == 0.0 and total_q == 0.0:
                    pass
                else:
                    self._apply_three_phase_injection_result(graphic_object=graphic_object,
                                                             device_name=load_device.name,
                                                             tooltip_title="Load 3ph equivalent injection",
                                                             qa=qa,
                                                             qb=qb,
                                                             qc=qc,
                                                             include_total_p=True,
                                                             pa=pa,
                                                             pb=pb,
                                                             pc=pc)

    def _colour_external_grid_results_3ph(self, t_idx: int | None) -> None:
        """
        Colour three-phase external-grid results.

        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        external_grid_devices: list[ExternalGrid] = self.circuit.get_external_grids()
        external_grid: ExternalGrid

        for external_grid in external_grid_devices:
            graphic_object = self._query_injection_graphic(external_grid)

            if graphic_object is None:
                pass
            else:
                pa: float = -float(external_grid.get_Pa_at(t_idx))
                pb: float = -float(external_grid.get_Pb_at(t_idx))
                pc: float = -float(external_grid.get_Pc_at(t_idx))
                qa: float = -float(external_grid.get_Qa_at(t_idx))
                qb: float = -float(external_grid.get_Qb_at(t_idx))
                qc: float = -float(external_grid.get_Qc_at(t_idx))
                total_p: float = pa + pb + pc
                total_q: float = qa + qb + qc

                if total_p == 0.0 and total_q == 0.0:
                    pass
                else:
                    self._apply_three_phase_injection_result(graphic_object=graphic_object,
                                                             device_name=external_grid.name,
                                                             tooltip_title="External grid 3ph equivalent injection",
                                                             qa=qa,
                                                             qb=qb,
                                                             qc=qc,
                                                             include_total_p=True,
                                                             pa=pa,
                                                             pb=pb,
                                                             pc=pc)

    def _colour_current_injection_results_3ph(self, t_idx: int | None) -> None:
        """
        Colour three-phase current-injection results.

        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        current_injection_devices: list[CurrentInjection] = self.circuit.get_current_injections()
        current_injection: CurrentInjection

        for current_injection in current_injection_devices:
            graphic_object = self._query_injection_graphic(current_injection)

            if graphic_object is None:
                pass
            else:
                pa: float = -float(current_injection.get_Ir1_at(t_idx))
                pb: float = -float(current_injection.get_Ir2_at(t_idx))
                pc: float = -float(current_injection.get_Ir3_at(t_idx))
                qa: float = -float(current_injection.get_Ii1_at(t_idx))
                qb: float = -float(current_injection.get_Ii2_at(t_idx))
                qc: float = -float(current_injection.get_Ii3_at(t_idx))
                total_p: float = pa + pb + pc
                total_q: float = qa + qb + qc

                if total_p == 0.0 and total_q == 0.0:
                    pass
                else:
                    self._apply_three_phase_injection_result(graphic_object=graphic_object,
                                                             device_name=current_injection.name,
                                                             tooltip_title="Current injection 3ph equivalent power",
                                                             qa=qa,
                                                             qb=qb,
                                                             qc=qc,
                                                             include_total_p=True,
                                                             pa=pa,
                                                             pb=pb,
                                                             pc=pc)

    def _colour_injection_results(self,
                                  gen_p: Vec | None,
                                  gen_q: Vec | None,
                                  gen_names: np.ndarray | list[str] | None,
                                  battery_p: Vec | None,
                                  battery_q: Vec | None,
                                  battery_names: np.ndarray | list[str] | None,
                                  shunt_q: Vec | None,
                                  shunt_names: np.ndarray | list[str] | None,
                                  t_idx: int | None) -> None:
        """
        Apply snapshot injection result overlays using the existing coloring flow.

        :param gen_p: Generator active powers.
        :param gen_q: Generator reactive powers.
        :param gen_names: Generator result names.
        :param battery_p: Battery active powers.
        :param battery_q: Battery reactive powers.
        :param battery_names: Battery result names.
        :param shunt_q: Shunt-like reactive powers.
        :param shunt_names: Shunt-like result names.
        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        self._clear_all_injection_results()

        generator_lookup: dict[str, int] = self._build_injection_name_lookup(names=gen_names)
        battery_lookup: dict[str, int] = self._build_injection_name_lookup(names=battery_names)
        shunt_lookup: dict[str, int] = self._build_injection_name_lookup(names=shunt_names)
        has_explicit_results: bool = _has_single_phase_explicit_injection_results(
            gen_p=gen_p,
            gen_q=gen_q,
            battery_p=battery_p,
            battery_q=battery_q,
            shunt_q=shunt_q,
        )

        self._colour_generator_results(gen_p=gen_p,
                                       gen_q=gen_q,
                                       generator_lookup=generator_lookup)
        self._colour_battery_results(battery_p=battery_p,
                                     battery_q=battery_q,
                                     battery_lookup=battery_lookup)
        self._colour_shunt_like_results(shunt_q=shunt_q,
                                        shunt_lookup=shunt_lookup)

        # Only studies that export some explicit per-device injection channels
        # should fall back to the profile-backed injections that still lack
        # study-native result vectors.
        if has_explicit_results:
            self._colour_static_generator_results(t_idx=t_idx)
            self._colour_load_results(t_idx=t_idx)
            self._colour_external_grid_results(t_idx=t_idx)
            self._colour_current_injection_results(t_idx=t_idx)
        else:
            pass

    def _colour_injection_results_3ph(self,
                                      gen_q_a: Vec | None,
                                      gen_q_b: Vec | None,
                                      gen_q_c: Vec | None,
                                      gen_names: np.ndarray | list[str] | None,
                                      battery_q_a: Vec | None,
                                      battery_q_b: Vec | None,
                                      battery_q_c: Vec | None,
                                      battery_names: np.ndarray | list[str] | None,
                                      shunt_q_a: Vec | None,
                                      shunt_q_b: Vec | None,
                                      shunt_q_c: Vec | None,
                                      shunt_names: np.ndarray | list[str] | None,
                                      t_idx: int | None) -> None:
        """
        Apply three-phase injection result overlays.

        :param gen_q_a: Generator phase-a reactive powers.
        :param gen_q_b: Generator phase-b reactive powers.
        :param gen_q_c: Generator phase-c reactive powers.
        :param gen_names: Generator result names.
        :param battery_q_a: Battery phase-a reactive powers.
        :param battery_q_b: Battery phase-b reactive powers.
        :param battery_q_c: Battery phase-c reactive powers.
        :param battery_names: Battery result names.
        :param shunt_q_a: Shunt phase-a reactive powers.
        :param shunt_q_b: Shunt phase-b reactive powers.
        :param shunt_q_c: Shunt phase-c reactive powers.
        :param shunt_names: Shunt result names.
        :param t_idx: Optional time index for profile-backed injections.
        :return: ``None``.
        """
        self._clear_all_injection_results()

        generator_lookup: dict[str, int] = self._build_injection_name_lookup(names=gen_names)
        battery_lookup: dict[str, int] = self._build_injection_name_lookup(names=battery_names)
        shunt_lookup: dict[str, int] = self._build_injection_name_lookup(names=shunt_names)
        has_explicit_results: bool = _has_three_phase_explicit_injection_results(
            gen_q_a=gen_q_a,
            gen_q_b=gen_q_b,
            gen_q_c=gen_q_c,
            battery_q_a=battery_q_a,
            battery_q_b=battery_q_b,
            battery_q_c=battery_q_c,
            shunt_q_a=shunt_q_a,
            shunt_q_b=shunt_q_b,
            shunt_q_c=shunt_q_c,
        )

        self._colour_generator_results_3ph(gen_q_a=gen_q_a,
                                           gen_q_b=gen_q_b,
                                           gen_q_c=gen_q_c,
                                           generator_lookup=generator_lookup)
        self._colour_battery_results_3ph(battery_q_a=battery_q_a,
                                         battery_q_b=battery_q_b,
                                         battery_q_c=battery_q_c,
                                         battery_lookup=battery_lookup)
        self._colour_shunt_like_results_3ph(shunt_q_a=shunt_q_a,
                                            shunt_q_b=shunt_q_b,
                                            shunt_q_c=shunt_q_c,
                                            shunt_lookup=shunt_lookup)

        if has_explicit_results:
            self._colour_static_generator_results_3ph(t_idx=t_idx)
            self._colour_load_results_3ph(t_idx=t_idx)
            self._colour_external_grid_results_3ph(t_idx=t_idx)
            self._colour_current_injection_results_3ph(t_idx=t_idx)
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
                       is_three_phase: bool = False,
                       apply_bus_result_coloring: bool = True):
        """
        Color objects based on the results passed.
        """
        vmin = 0
        vmax = 1.2
        vrng = vmax - vmin
        vabs = np.abs(voltages)
        vang = np.angle(voltages, deg=True)
        vnorm = (vabs - vmin) / vrng
        voltage_cmap = viz.get_voltage_color_map()
        loading_cmap = viz.get_loading_color_map()
        bus_types = ['', 'PQ', 'PV', 'Slack', 'PQV', 'P']

        self._colour_bus_results(Sbus=Sbus,
                                 bus_active=bus_active,
                                 vabs=vabs,
                                 vang=vang,
                                 vnorm=vnorm,
                                 types=types,
                                 bus_types=bus_types,
                                 voltage_cmap=voltage_cmap,
                                 cmap=cmap,
                                 use_flow_based_width=use_flow_based_width,
                                 apply_result_coloring=apply_bus_result_coloring)

        self._colour_injection_results(gen_p=gen_p,
                                       gen_q=gen_q,
                                       gen_names=gen_names,
                                       battery_p=battery_p,
                                       battery_q=battery_q,
                                       battery_names=battery_names,
                                       shunt_q=shunt_q,
                                       shunt_names=shunt_names,
                                       t_idx=t_idx)

        max_flow = self._colour_branch_results(Sf=Sf,
                                               St=St,
                                               loadings=loadings,
                                               losses=losses,
                                               br_active=br_active,
                                               hvdc_Pf=hvdc_Pf,
                                               loading_label=loading_label,
                                               use_flow_based_width=use_flow_based_width,
                                               min_branch_width=min_branch_width,
                                               max_branch_width=max_branch_width,
                                               loading_cmap=loading_cmap,
                                               cmap=cmap,
                                               ma=ma,
                                               tau=tau,
                                               is_three_phase=is_three_phase)
        if max_flow is None:
            return

        self._colour_vsc_results(vsc_Pf=vsc_Pf,
                                 vsc_Pt=vsc_Pt,
                                 vsc_Qt=vsc_Qt,
                                 vsc_losses=vsc_losses,
                                 vsc_loading=vsc_loading,
                                 vsc_active=vsc_active,
                                 loading_label=loading_label,
                                 use_flow_based_width=use_flow_based_width,
                                 min_branch_width=min_branch_width,
                                 max_branch_width=max_branch_width,
                                 loading_cmap=loading_cmap,
                                 cmap=cmap,
                                 max_flow=max_flow)

        self._colour_hvdc_results(hvdc_Pf=hvdc_Pf,
                                  hvdc_Pt=hvdc_Pt,
                                  hvdc_losses=hvdc_losses,
                                  hvdc_loading=hvdc_loading,
                                  hvdc_active=hvdc_active,
                                  loading_label=loading_label,
                                  use_flow_based_width=use_flow_based_width,
                                  min_branch_width=min_branch_width,
                                  max_branch_width=max_branch_width,
                                  loading_cmap=loading_cmap,
                                  cmap=cmap,
                                  max_flow=max_flow)

        self._colour_fluid_path_results(fluid_path_flow=fluid_path_flow)
        self._colour_fluid_node_results(vabs=vabs,
                                        vang=vang,
                                        Sbus=Sbus,
                                        types=types,
                                        bus_types=bus_types,
                                        fluid_node_p2x_flow=fluid_node_p2x_flow,
                                        fluid_node_current_level=fluid_node_current_level,
                                        fluid_node_spillage=fluid_node_spillage,
                                        fluid_node_flow_in=fluid_node_flow_in,
                                        fluid_node_flow_out=fluid_node_flow_out)

    def _colour_bus_results_3ph(self,
                                VmA: Vec,
                                VmB: Vec,
                                VmC: Vec,
                                VaA: Vec,
                                VaB: Vec,
                                VaC: Vec,
                                bus_active: IntVec,
                                types: IntVec,
                                bus_types: list[str],
                                voltage_cmap: Callable,
                                cmap: palettes.Colormaps | None,
                                use_flow_based_width: bool) -> None:
        """

        :param VmA:
        :param VmB:
        :param VmC:
        :param VaA:
        :param VaB:
        :param VaC:
        :param bus_active:
        :param types:
        :param bus_types:
        :param voltage_cmap:
        :param cmap:
        :param use_flow_based_width:
        :return:
        """
        nbus = self.circuit.get_bus_number()
        if nbus != len(VmA):
            error_msg(self.tr("Bus results length differs from the number of Bus results. \n"
                      "Did you change the number of devices? If so, re-run the simulation."))
            return

        vmin = 0.0
        vmax = 1.2
        vrng = vmax - vmin

        for i, bus in enumerate(self.circuit.buses):
            graphic_object = self._query_bus_graphic(bus)
            if graphic_object is None:
                continue

            if bus_active[i]:
                graphic_object.set_values_3ph(i=i,
                                              VmA=VmA[i], VmB=VmB[i], VmC=VmC[i],
                                              VaA=VaA[i], VaB=VaB[i], VaC=VaC[i],
                                              tpe=bus_types[int(types[i])])
                vals_nz = [v for v in [VmA[i], VmB[i], VmC[i]] if v != 0.0]
                if vals_nz:
                    worst_umax = max(vals_nz)
                    worst_umin = min(vals_nz)
                    worst_u = worst_umax if abs(worst_umax - 1.0) > abs(1.0 - worst_umin) else worst_umin
                else:
                    worst_u = 0.0
                graphic_object.set_tile_color(
                    self._get_voltage_result_color((worst_u - vmin) / vrng, cmap, voltage_cmap)
                )
                if use_flow_based_width:
                    graphic_object.change_size(w=graphic_object.w)
            else:
                graphic_object.set_tile_color(QColor(115, 115, 115, 255))
                graphic_object.clear_label()

    def _colour_vsc_results_3ph(self,
                                vsc_Pf: Vec | None,
                                vsc_PtA: Vec,
                                vsc_PtB: Vec,
                                vsc_PtC: Vec,
                                vsc_QtA: Vec,
                                vsc_QtB: Vec,
                                vsc_QtC: Vec,
                                vsc_losses: Vec,
                                vsc_loading: Vec,
                                vsc_active: IntVec,
                                loading_label: str,
                                use_flow_based_width: bool,
                                min_branch_width: int,
                                max_branch_width: int,
                                loading_cmap: Callable,
                                cmap: palettes.Colormaps | None,
                                max_flow: float) -> None:
        """

        :param vsc_Pf:
        :param vsc_PtA:
        :param vsc_PtB:
        :param vsc_PtC:
        :param vsc_QtA:
        :param vsc_QtB:
        :param vsc_QtC:
        :param vsc_losses:
        :param vsc_loading:
        :param vsc_active:
        :param loading_label:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param loading_cmap:
        :param cmap:
        :param max_flow:
        :return:
        """
        if vsc_Pf is None:
            return

        if self.circuit.get_vsc_number() != len(vsc_Pf):
            error_msg(self.tr("VSC results length differs from the number of VSC results. \n"
                      "Did you change the number of devices? If so, re-run the simulation."))
            return

        vsc_sending_power_norm = np.abs(vsc_PtA + 1j * vsc_QtA) / (max_flow + 1e-20)
        for i, elm in enumerate(self.circuit.vsc_devices):
            graphic_object = self._query_vsc_graphic(elm)
            if graphic_object is None:
                continue

            if vsc_active[i]:
                width = int(np.floor(min_branch_width + vsc_sending_power_norm[i] *
                                     (max_branch_width - min_branch_width))) \
                    if use_flow_based_width else graphic_object.pen_width
                style = Qt.PenStyle.SolidLine if elm.active else Qt.PenStyle.DashLine
                color = self._get_branch_result_color(abs(vsc_loading[i]),
                                                      cmap,
                                                      loading_cmap,
                                                      elm.get_max_bus_nominal_voltage()) \
                    if elm.active else QColor(115, 115, 115, 255)
                tooltip = str(i) + ': ' + elm.name
                tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(abs(vsc_loading[i]) * 100) + ' [%]'
                tooltip += '\nPower DC (from):\t' + "{:10.4f}".format(vsc_Pf[i]) + ' [MW]'
                tooltip += '\nPower A (to):\t' + "{:10.4f}".format(vsc_PtA[i]) + ' [MW]'
                tooltip += '\nPower B (to):\t' + "{:10.4f}".format(vsc_PtB[i]) + ' [MW]'
                tooltip += '\nPower C (to):\t' + "{:10.4f}".format(vsc_PtC[i]) + ' [MW]'
                tooltip += '\nPower A (to):\t' + "{:10.4f}".format(vsc_QtA[i]) + ' [Mvar]'
                tooltip += '\nPower B (to):\t' + "{:10.4f}".format(vsc_QtB[i]) + ' [Mvar]'
                tooltip += '\nPower C (to):\t' + "{:10.4f}".format(vsc_QtC[i]) + ' [Mvar]'
                tooltip += '\nLosses: \t\t' + "{:10.4f}".format(vsc_losses[i]) + ' [MW]'
                graphic_object.set_arrows_with_power(Sf=vsc_Pf[i] + 1j * 0.0,
                                                     St=vsc_PtA[i] + 1j * vsc_QtA[i])
                graphic_object.setToolTipText(tooltip)
                graphic_object.set_colour(color, width, style)
            else:
                graphic_object.set_pen(QPen(QColor(115, 115, 115, 255),
                                            graphic_object.pen_width,
                                            Qt.PenStyle.DashLine))

    def _colour_hvdc_results_3ph(self,
                                 hvdc_PfA: Vec,
                                 hvdc_PtA: Vec,
                                 hvdc_losses: Vec,
                                 hvdc_loading: Vec,
                                 hvdc_active: IntVec,
                                 loading_label: str,
                                 use_flow_based_width: bool,
                                 min_branch_width: int,
                                 max_branch_width: int,
                                 loading_cmap: Callable,
                                 cmap: palettes.Colormaps | None,
                                 max_flow: float) -> None:
        """

        :param hvdc_PfA:
        :param hvdc_PtA:
        :param hvdc_losses:
        :param hvdc_loading:
        :param hvdc_active:
        :param loading_label:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param loading_cmap:
        :param cmap:
        :param max_flow:
        :return:
        """
        if len(hvdc_PfA) == 0:
            return

        if self.circuit.get_hvdc_number() != len(hvdc_PfA):
            error_msg(self.tr("HVDC results length differs from the number of HVDC results. \n"
                      "Did you change the number of devices? If so, re-run the simulation."))
            return

        hvdc_sending_power_norm = np.abs(hvdc_PfA) / (max_flow + 1e-20)
        for i, elm in enumerate(self.circuit.hvdc_lines):
            graphic_object = self._query_hvdc_graphic(elm)
            if graphic_object is None:
                continue

            if hvdc_active[i]:
                width = int(np.floor(min_branch_width + hvdc_sending_power_norm[i] *
                                     (max_branch_width - min_branch_width))) \
                    if use_flow_based_width else graphic_object.pen_width
                style = Qt.PenStyle.SolidLine if elm.active else Qt.PenStyle.DashLine
                color = self._get_branch_result_color(abs(hvdc_loading[i]),
                                                      cmap,
                                                      loading_cmap,
                                                      elm.get_max_bus_nominal_voltage()) \
                    if elm.active else QColor(115, 115, 115, 255)
                tooltip = str(i) + ': ' + elm.name
                tooltip += '\n' + loading_label + ': ' + "{:10.4f}".format(abs(hvdc_loading[i]) * 100) + ' [%]'
                tooltip += '\nPower (from):\t' + "{:10.4f}".format(hvdc_PfA[i]) + ' [MW]'
                if hvdc_losses is not None:
                    tooltip += '\nPower (to):\t' + "{:10.4f}".format(hvdc_PtA[i]) + ' [MW]'
                    tooltip += '\nLosses: \t\t' + "{:10.4f}".format(hvdc_losses[i]) + ' [MW]'
                    graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_PfA[i], Pt=hvdc_PtA[i])
                else:
                    graphic_object.set_arrows_with_hvdc_power(Pf=hvdc_PfA[i], Pt=-hvdc_PfA[i])
                graphic_object.setToolTipText(tooltip)
                graphic_object.set_colour(color, width, style)
            else:
                graphic_object.set_pen(QPen(QColor(115, 115, 115, 255),
                                            graphic_object.pen_width,
                                            Qt.PenStyle.DashLine))

    def colour_results_3ph(self,
                           SbusA: CxVec,
                           SbusB: CxVec,
                           SbusC: CxVec,
                           voltagesA: CxVec,
                           voltagesB: CxVec,
                           voltagesC: CxVec,
                           bus_active: IntVec,
                           types: IntVec,
                           SfA: CxVec,
                           SfB: CxVec,
                           SfC: CxVec,
                           StA: CxVec,
                           StB: CxVec,
                           StC: CxVec,
                           loadingsA: CxVec,
                           loadingsB: CxVec,
                           loadingsC: CxVec,
                           lossesA: CxVec,
                           lossesB: CxVec,
                           lossesC: CxVec,
                           br_active: IntVec,
                           hvdc_PfA: Vec,
                           hvdc_PfB: Vec,
                           hvdc_PfC: Vec,
                           hvdc_PtA: Vec,
                           hvdc_PtB: Vec,
                           hvdc_PtC: Vec,
                           hvdc_losses: Vec,
                           hvdc_loading: Vec,
                           hvdc_active: IntVec,
                           vsc_Pf: Vec,
                           vsc_PtA: Vec,
                           vsc_PtB: Vec,
                           vsc_PtC: Vec,
                           vsc_QtA: Vec,
                           vsc_QtB: Vec,
                           vsc_QtC: Vec,
                           vsc_losses: Vec,
                           vsc_loading: Vec,
                           vsc_active: IntVec,
                           loading_label: str = 'loading',
                           use_flow_based_width: bool = False,
                           min_branch_width: int = 5,
                           max_branch_width=5,
                           min_bus_width=20,
                           max_bus_width=20,
                           cmap: palettes.Colormaps = None,
                           ma: Vec | None = None,
                           tau: Vec | None = None,
                           t_idx: int | None = None,
                           gen_q_a: Vec | None = None,
                           gen_q_b: Vec | None = None,
                           gen_q_c: Vec | None = None,
                           gen_names: np.ndarray | list[str] | None = None,
                           battery_q_a: Vec | None = None,
                           battery_q_b: Vec | None = None,
                           battery_q_c: Vec | None = None,
                           battery_names: np.ndarray | list[str] | None = None,
                           shunt_q_a: Vec | None = None,
                           shunt_q_b: Vec | None = None,
                           shunt_q_c: Vec | None = None,
                           shunt_names: np.ndarray | list[str] | None = None):
        """
        Color objects based on the three-phase results passed.
        :param SbusA:
        :param SbusB:
        :param SbusC:
        :param voltagesA:
        :param voltagesB:
        :param voltagesC:
        :param bus_active:
        :param types:
        :param SfA:
        :param SfB:
        :param SfC:
        :param StA:
        :param StB:
        :param StC:
        :param loadingsA:
        :param loadingsB:
        :param loadingsC:
        :param lossesA:
        :param lossesB:
        :param lossesC:
        :param br_active:
        :param hvdc_PfA:
        :param hvdc_PfB:
        :param hvdc_PfC:
        :param hvdc_PtA:
        :param hvdc_PtB:
        :param hvdc_PtC:
        :param hvdc_losses:
        :param hvdc_loading:
        :param hvdc_active:
        :param vsc_Pf:
        :param vsc_PtA:
        :param vsc_PtB:
        :param vsc_PtC:
        :param vsc_QtA:
        :param vsc_QtB:
        :param vsc_QtC:
        :param vsc_losses:
        :param vsc_loading:
        :param vsc_active:
        :param loading_label:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :param cmap:
        :param ma:
        :param tau:
        :param t_idx:
        :param gen_q_a:
        :param gen_q_b:
        :param gen_q_c:
        :param gen_names:
        :param battery_q_a:
        :param battery_q_b:
        :param battery_q_c:
        :param battery_names:
        :param shunt_q_a:
        :param shunt_q_b:
        :param shunt_q_c:
        :param shunt_names:
        :return:
        """
        VmA = np.abs(voltagesA)
        VmB = np.abs(voltagesB)
        VmC = np.abs(voltagesC)
        VaA = np.angle(voltagesA, deg=True)
        VaB = np.angle(voltagesB, deg=True)
        VaC = np.angle(voltagesC, deg=True)
        voltage_cmap = viz.get_voltage_color_map()
        loading_cmap = viz.get_loading_color_map()
        bus_types = ['', 'PQ', 'PV', 'Slack', 'PQV', 'P']

        self._colour_bus_results_3ph(VmA=VmA,
                                     VmB=VmB,
                                     VmC=VmC,
                                     VaA=VaA,
                                     VaB=VaB,
                                     VaC=VaC,
                                     bus_active=bus_active,
                                     types=types,
                                     bus_types=bus_types,
                                     voltage_cmap=voltage_cmap,
                                     cmap=cmap,
                                     use_flow_based_width=use_flow_based_width)

        self._colour_injection_results_3ph(gen_q_a=gen_q_a,
                                           gen_q_b=gen_q_b,
                                           gen_q_c=gen_q_c,
                                           gen_names=gen_names,
                                           battery_q_a=battery_q_a,
                                           battery_q_b=battery_q_b,
                                           battery_q_c=battery_q_c,
                                           battery_names=battery_names,
                                           shunt_q_a=shunt_q_a,
                                           shunt_q_b=shunt_q_b,
                                           shunt_q_c=shunt_q_c,
                                           shunt_names=shunt_names,
                                           t_idx=t_idx)

        Sf = np.empty(0, dtype=complex)
        St = np.empty(0, dtype=complex)
        loadings = np.empty(0, dtype=complex)
        losses = np.empty(0, dtype=complex)
        if len(SfA) > 0:
            Sf = np.empty(3 * len(SfA), dtype=complex)
            St = np.empty(3 * len(StA), dtype=complex)
            loadings = np.empty(3 * len(loadingsA), dtype=complex)
            losses = np.empty(3 * len(lossesA), dtype=complex)
            Sf[0::3], Sf[1::3], Sf[2::3] = SfA, SfB, SfC
            St[0::3], St[1::3], St[2::3] = StA, StB, StC
            loadings[0::3], loadings[1::3], loadings[2::3] = loadingsA, loadingsB, loadingsC
            losses[0::3], losses[1::3], losses[2::3] = lossesA, lossesB, lossesC

        hvdc_pf = np.maximum(np.maximum(np.abs(hvdc_PfA), np.abs(hvdc_PfB)), np.abs(hvdc_PfC))
        max_flow = self._colour_branch_results(Sf=Sf,
                                               St=St,
                                               loadings=loadings,
                                               losses=losses,
                                               br_active=br_active,
                                               hvdc_Pf=hvdc_pf,
                                               loading_label=loading_label,
                                               use_flow_based_width=use_flow_based_width,
                                               min_branch_width=min_branch_width,
                                               max_branch_width=max_branch_width,
                                               loading_cmap=loading_cmap,
                                               cmap=cmap,
                                               ma=ma,
                                               tau=tau,
                                               is_three_phase=True)
        if max_flow is None:
            return

        self._colour_vsc_results_3ph(vsc_Pf=vsc_Pf,
                                     vsc_PtA=vsc_PtA,
                                     vsc_PtB=vsc_PtB,
                                     vsc_PtC=vsc_PtC,
                                     vsc_QtA=vsc_QtA,
                                     vsc_QtB=vsc_QtB,
                                     vsc_QtC=vsc_QtC,
                                     vsc_losses=vsc_losses,
                                     vsc_loading=vsc_loading,
                                     vsc_active=vsc_active,
                                     loading_label=loading_label,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     loading_cmap=loading_cmap,
                                     cmap=cmap,
                                     max_flow=max_flow)

        self._colour_hvdc_results_3ph(hvdc_PfA=hvdc_PfA,
                                      hvdc_PtA=hvdc_PtA,
                                      hvdc_losses=hvdc_losses,
                                      hvdc_loading=hvdc_loading,
                                      hvdc_active=hvdc_active,
                                      loading_label=loading_label,
                                      use_flow_based_width=use_flow_based_width,
                                      min_branch_width=min_branch_width,
                                      max_branch_width=max_branch_width,
                                      loading_cmap=loading_cmap,
                                      cmap=cmap,
                                      max_flow=max_flow)

    def recolour(self, use_api_color: bool):
        """

        :param use_api_color:
        :return:
        """

        self.diagram.use_api_colors = use_api_color

        for graphical_obj in self.items():

            if graphical_obj.api_object is not None:

                if use_api_color:
                    if isinstance(graphical_obj, BusGraphicItem):
                        color = QColor(graphical_obj.api_object.color)
                        brush = QBrush(color)
                        graphical_obj.set_tile_color(brush)

                    elif isinstance(graphical_obj, (TransformerGraphicItem, LineGraphicItem)):
                        color = QColor(graphical_obj.api_object.color)
                        w = graphical_obj.pen_width

                        if graphical_obj.api_object.active:  # TODO: gather the property at the time step too
                            style = Qt.PenStyle.SolidLine
                        else:
                            style = Qt.PenStyle.DashLine

                        graphical_obj.set_colour(color, w=w, style=style)
                    else:
                        pass

                else:
                    graphical_obj.recolour_mode()

    def get_selected(self) -> List[GenericDiagramWidget | QGraphicsItem]:
        """
        Get selection
        :return: List of EditableDevice, QGraphicsItem
        """
        return [elm for elm in self.diagram_scene.selectedItems()]

    def _get_selection_api_objects(self) -> List[ALL_DEV_TYPES]:
        """
        Get a list of the API objects from the selection
        :return: List[EditableDevice]
        """
        return [e.api_object for e in self.get_selected() if isinstance(e, GenericDiagramWidget)]

    def create_schematic_from_selection(self) -> SchematicDiagram:
        """
        Get a SchematicDiagram of the current selection
        :return: SchematicDiagram
        """
        diagram = SchematicDiagram(name="Selection diagram")

        # first pass (only buses)
        bus_dict = dict()
        for item in self.get_selected():
            if isinstance(item, BusGraphicItem):
                # check that the bus is in the original diagram
                location = self.diagram.query_point(item.api_object)

                if location:
                    diagram.set_point(device=item.api_object, location=location.copy())
                    bus_dict[item.api_object.idtag] = item
                else:
                    raise Exception('Item was selected but was not registered!')

        # second pass (Branches, and include their not selected buses)
        for item in self.diagram_scene.selectedItems():
            if isinstance(item, BRANCH_GRAPHICS):

                location = self.diagram.query_point(item.api_object)

                if location:
                    diagram.set_point(device=item.api_object, location=location.copy())
                else:
                    # Fallback for partially registered graphics; preserve previous behavior.
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
                        diagram.set_point(device=bus, location=location.copy())
                        graphic_object = self._query_bus_graphic(bus)
                        bus_dict[bus.idtag] = graphic_object

        # third pass: we must also add all those branches connecting the selected buses
        for lst in self.circuit.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
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

                # delete the elements already in the selection
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

                x_m = float(np.mean(x_arr))
                y_m = float(np.mean(y_arr))

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

    def plot_bus(self, i: int, api_object: Bus) -> None:
        """Open bus injection profiles and all available time-series results.

        :param i: Legacy result-column index retained for graphic callbacks.
        :param api_object: Bus represented by the selected schematic graphic.
        :return: None.
        """
        _ = i
        time_values: np.ndarray | None = self.circuit.get_time_array()
        dialog_title: str = self.tr("{device_name} profiles plot").format(device_name=api_object.name)
        plot_dialogue: PlotDialogue = PlotDialogue(title=dialog_title, parent=self.gui)
        plotted_units: list[str] = list()
        plotted_charts: list[GraphsWidget] = list()
        has_profiles: bool = False
        if time_values is not None and len(time_values) > 0:
            all_devices: Dict[Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]
            all_devices = self.circuit.get_injection_devices_grouped_by_bus()
            bus_devices: Dict[DeviceType, List[INJECTION_DEVICE_TYPES]] | None = all_devices.get(api_object, None)
            power_names: list[str] = list()
            power_values: list[np.ndarray] = list()
            if bus_devices is not None:
                device_group: list[object]
                for device_group in bus_devices.values():
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
                            power_names.append(str(device.name))
                            power_values.append(np.asarray(profile_values, dtype=float))
                        else:
                            pass
            else:
                pass

            if len(power_names) > 0:
                plot_dialogue.register_time_series(
                    group=self.tr("Profile Inputs"),
                    unit="MW",
                    x_values=time_values,
                    series_names=power_names,
                    series_values=power_values,
                )
                if len(power_values) > 0:
                    has_profiles = True
                    plotted_units.append("MW")
                else:
                    pass
            else:
                pass
        else:
            pass

        has_results: bool = self._add_device_result_tabs(
            plot_dialogue=plot_dialogue,
            api_object=api_object,
            plotted_units=plotted_units,
            plotted_charts=plotted_charts,
        )
        if has_profiles or has_results:
            plot_dialogue.select_default_catalog_series()
            plot_dialogue.set_series_selector_visible(visible=True)
            self.gui.register_open_plot_dialog(plot_dialogue)
            plot_dialogue.show()
        else:
            plot_dialogue.reject()
            self.gui.show_error_toast(self.tr("There are no finite time-series values to plot."))

    def plot_fluid_node(self, i: int, api_object: FluidNode) -> None:
        """Open node profiles and all available time-series result curves.

        :param i: Legacy result-column index retained for graphic callbacks.
        :param api_object: Fluid node represented by the selected graphic.
        :return: None.
        """
        _ = i
        self.plot_device(api_object=api_object)

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
            bus_f_graphic_obj = self._query_bus_graphic(original_line.bus_from)
            bus_t_graphic_obj = self._query_bus_graphic(original_line.bus_to)

            if bus_f_graphics_data is None:
                error_msg(self.tr("{bus_name} was not found in the diagram").format(bus_name=original_line.bus_from))
                return None
            if bus_t_graphics_data is None:
                error_msg(self.tr("{bus_name} was not found in the diagram").format(bus_name=original_line.bus_to))
                return None
            if bus_f_graphic_obj is None:
                error_msg(self.tr("{bus_name} was not found in the graphics manager").format(
                    bus_name=original_line.bus_from,
                ))
                return None
            if bus_t_graphic_obj is None:
                error_msg(self.tr("{bus_name} was not found in the graphics manager").format(
                    bus_name=original_line.bus_to,
                ))
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
            error_msg(self.tr("Incorrect position"), self.tr('Line split'))

    def split_line(self, line_graphics: LineGraphicItem):
        """
        Split line
        :return:
        """
        dlg = InputNumberDialogue(min_value=1.0,
                                  max_value=99.0,
                                  is_int=False,
                                  title=self.tr("Split line"),
                                  text=self.tr("Enter the distance from the beginning of the \n"
                                       "line as a percentage of the total length"),
                                  suffix=self.tr(' %'),
                                  decimals=2,
                                  default_value=50.0)
        if exec_dialog_safely(dialog=dlg):

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
                                  text=self.tr("Enter the distance from the beginning of the \n"
                                       "line as a percentage of the total length"),
                                  suffix=self.tr(' %'),
                                  decimals=2,
                                  default_value=50.0)
        if exec_dialog_safely(dialog=dlg):

            if dlg.is_accepted:

                position = dlg.value / 100.0

                if 0.0 < position < 1.0:

                    dlg2 = InputNumberDialogue(min_value=0.01,
                                               max_value=99999999.0,
                                               is_int=False,
                                               title=title,
                                               text=self.tr("Distance from the splitting point"),
                                               suffix=self.tr(' km'),
                                               decimals=2,
                                               default_value=1.0)

                    if exec_dialog_safely(dialog=dlg2):

                        if dlg2.is_accepted:

                            create_extra_nodes = yes_no_question(text=self.tr("Add extra buses?"), title=title)

                            if create_extra_nodes:

                                original_line = line_graphics.api_object

                                (mid_sub, mid_vl,
                                 B1, B2, B3,
                                 br1, br2, br3, br4) = self.circuit.split_line_int_out(original_line=original_line,
                                                                                       position=position,
                                                                                       km_io=dlg2.value)

                                bus_f_graphics_data = self.diagram.query_point(original_line.bus_from)
                                bus_t_graphics_data = self.diagram.query_point(original_line.bus_to)
                                bus_f_graphic_obj = self._query_bus_graphic(original_line.bus_from)
                                bus_t_graphic_obj = self._query_bus_graphic(original_line.bus_to)

                                if bus_f_graphics_data is None:
                                    error_msg(self.tr("{bus_name} was not found in the diagram").format(
                                        bus_name=original_line.bus_from,
                                    ))
                                    return None
                                if bus_t_graphics_data is None:
                                    error_msg(self.tr("{bus_name} was not found in the diagram").format(
                                        bus_name=original_line.bus_to,
                                    ))
                                    return None
                                if bus_f_graphic_obj is None:
                                    error_msg(self.tr("{bus_name} was not found in the graphics manager").format(
                                        bus_name=original_line.bus_from,
                                    ))
                                    return None
                                if bus_t_graphic_obj is None:
                                    error_msg(self.tr("{bus_name} was not found in the graphics manager").format(
                                        bus_name=original_line.bus_to,
                                    ))
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
                    error_msg(self.tr("Incorrect position"), self.tr('Line split'))

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

            elif idx_bus_list[1][1] == line_graphics.api_object.bus_from:
                idx, new_bus, new_bus_graphic_item = idx_bus_list[0]
                idx, old_bus, old_bus_graphic_item = idx_bus_list[1]

            elif idx_bus_list[0][1] == line_graphics.api_object.bus_to:
                idx, old_bus, old_bus_graphic_item = idx_bus_list[0]
                idx, new_bus, new_bus_graphic_item = idx_bus_list[1]

            elif idx_bus_list[1][1] == line_graphics.api_object.bus_to:
                idx, new_bus, new_bus_graphic_item = idx_bus_list[0]
                idx, old_bus, old_bus_graphic_item = idx_bus_list[1]

            else:
                error_msg(text=self.tr("The 'from' or 'to' bus to change has not been selected!"),
                          title=self.tr('Change bus'))
                return

            ok = yes_no_question(text=self.tr(
                "Are you sure that you want to relocate the bus from {old_bus_name} to {new_bus_name}?"
            ).format(old_bus_name=old_bus.name, new_bus_name=new_bus.name),
                                 title=self.tr('Change bus'))

            if ok:
                new_bus_graphic_item.get_terminal().reassign_terminal(
                    graphic_obj=line_graphics,
                    another_terminal=old_bus_graphic_item.get_terminal()
                )

                line_graphics.api_object.reassign_bus(
                    old_bus=old_bus,
                    new_bus=new_bus
                )

                new_bus_graphic_item.get_terminal().update()

        else:
            warning_msg(self.tr("you must select the origin and destination buses!"),
                        title=self.tr('Change bus'))

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

        else:
            error_msg(text=self.tr("You need to select exactly one bus to be set as the generator regulation bus"),
                      title=self.tr("Set regulation bus"))

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

    def set_vsc_control_dev(self, graphic: VscGraphicItem, control_idx: int):
        """
        Set the VSC control1_dev or control1_dev with the selected bus
        :param graphic: VscGraphicItem
        :param control_idx: 1 or 2 to set control1_dev or control1_dev
        """

        idx_bus_list = self.get_selected_buses()

        if len(idx_bus_list) == 1:

            # detect the bus and its combinations
            idx, sel_bus, sel_bus_graphic_item = idx_bus_list[0]

            if control_idx == 1:
                graphic.api_object.control1_dev = sel_bus
            elif control_idx == 2:
                graphic.api_object.control2_dev = sel_bus
            else:
                print("control_idx must be either 1 or 2")
        else:
            error_msg(self.tr(
                "You need to select exactly one bus to be set as the VSC control device {control_index}"
            ).format(control_index=control_idx),
                      self.tr("Set VSC control device 1"))

    def get_picture_width(self) -> int:
        return self.editor_graphics_view.width()

    def get_picture_height(self) -> int:
        return self.editor_graphics_view.height()

    def copy(self) -> "SchematicWidget":
        """
        Deep copy of this widget
        :return: SchematicWidget
        """
        d_copy: SchematicDiagram = self.diagram.copy(
            obj_dict=self.circuit.get_all_elements_dict_by_type(add_locations=True)
        )
        d_copy.name = self.diagram.name + '_copy'

        return SchematicWidget(
            gui=self.gui,
            diagram=d_copy,
            default_bus_voltage=self.default_bus_voltage,
            time_index=self.get_time_index(),
        )

    def consolidate_coordinates(self):
        """
        Consolidate the graphic elements' x, y coordinates into the API DB values
        """
        for i, bus, bus_graphics in self.get_buses():
            bus.x = bus_graphics.x()
            bus.y = bus_graphics.y()

    def reset_coordinates(self):
        """
        Reset coordinates to the stored ones in the DataBase
        """
        for i, bus, bus_graphics in self.get_buses():
            bus_graphics.set_position(bus.x, bus.y)

    def add_buses(self, buses: List[Bus] | Set[Bus]):
        """
        Draw all elements associated to a group of buses
        :param buses: List or Set of Buses
        """

        (buses,
         lines, dc_lines, transformers2w,
         transformers3w, transformers_nw, windings, hvdc_lines,
         vsc_converters, upfc_devices,
         series_reactances, switches,
         fluid_nodes, fluid_paths) = get_devices_to_expand(circuit=self.circuit, buses_set=buses, max_level=1)

        # Draw schematic subset
        diagram = generate_schematic_diagram(buses=list(buses),
                                             lines=lines,
                                             dc_lines=dc_lines,
                                             transformers2w=transformers2w,
                                             transformers3w=transformers3w,
                                             transformers_nw=transformers_nw,
                                             windings=windings,
                                             hvdc_lines=hvdc_lines,
                                             vsc_devices=vsc_converters,
                                             upfc_devices=upfc_devices,
                                             series_reactances=series_reactances,
                                             switches=switches,
                                             fluid_nodes=list(fluid_nodes),
                                             fluid_paths=fluid_paths)

        self.draw_additional_diagram(diagram=diagram)

    def add_buses_deep(self, buses: List[Bus] | Set[Bus]):
        """
        Draw all elements associated to a group of buses with deeper expansion.
        Used for voltage level conversions where internal buses and switches
        may be multiple hops away.
        :param buses: List or Set of Buses
        """

        # Extract voltage levels from the input buses to restrict expansion
        # This prevents expanding into the external network when drawing voltage level conversions
        voltage_levels = {b.voltage_level for b in buses if b.voltage_level is not None}

        (buses,
         lines, dc_lines, transformers2w,
         transformers3w, transformers_nw, windings, hvdc_lines,
         vsc_converters, upfc_devices,
         series_reactances, switches,
         fluid_nodes, fluid_paths) = get_devices_to_expand(circuit=self.circuit,
                                                           buses_set=buses,
                                                           max_level=5,
                                                           restrict_to_voltage_levels=voltage_levels)

        # Draw schematic subset
        diagram = generate_schematic_diagram(buses=list(buses),
                                             lines=lines,
                                             dc_lines=dc_lines,
                                             transformers2w=transformers2w,
                                             transformers3w=transformers3w,
                                             transformers_nw=transformers_nw,
                                             windings=windings,
                                             hvdc_lines=hvdc_lines,
                                             vsc_devices=vsc_converters,
                                             upfc_devices=upfc_devices,
                                             series_reactances=series_reactances,
                                             switches=switches,
                                             fluid_nodes=list(fluid_nodes),
                                             fluid_paths=fluid_paths)

        self.draw_additional_diagram(diagram=diagram)

    def change_injection_bus(self, injection_graphics: INJECTION_GRAPHICS):
        """

        :param injection_graphics:
        :return:
        """

        idx_bus_list = self.get_selected_buses()

        if len(idx_bus_list) == 2:

            # detect the bus and its combinations
            if idx_bus_list[0][1] == injection_graphics.api_object.bus:
                idx, old_bus, old_bus_graphic_item = idx_bus_list[0]
                idx, new_bus, new_bus_graphic_item = idx_bus_list[1]
            elif idx_bus_list[1][1] == injection_graphics.api_object.bus:
                idx, new_bus, new_bus_graphic_item = idx_bus_list[0]
                idx, old_bus, old_bus_graphic_item = idx_bus_list[1]
            else:
                error_msg(self.tr("The bus to change has not been selected!"), self.tr('Change bus'))
                return

            ok = yes_no_question(
                text=self.tr(
                    "Are you sure that you want to relocate the bus from {old_bus_name} to {new_bus_name}?"
                ).format(old_bus_name=old_bus.name, new_bus_name=new_bus.name),
                title=self.tr('Change bus'))

            if ok:
                # set the API object new bus
                injection_graphics.api_object.bus = new_bus

                # add the graphics for the new bus
                new_bus_graphic_item.add_object(api_obj=injection_graphics.api_object)
                new_bus_graphic_item.update()

                self._remove_from_scene(injection_graphics.nexus)
                self._remove_from_scene(injection_graphics)

        else:
            warning_msg(self.tr("you have to select the origin and destination buses!"),
                        title=self.tr('Change bus'))

    def reconnect_bus_graphics(self,
                               bus_graphics: BusGraphicItem,
                               new_buses: List[Bus]):
        """
        Reconnect the graphic elements connected in bus_graphics
        to whatever new graphics associated to new_buses
        :param bus_graphics: Old graphics bus
        :param new_buses: list of new API buses
        """
        # connected branches
        branch_graphics = bus_graphics.get_associated_branch_graphics()

        # Note: graphical shunts have been added already
        # the order of the buses matches the order of the branches because the
        # transformation function already works like that
        for branch_graphic, new_bus in zip(branch_graphics, new_buses):
            new_bus_graphic = self._query_bus_graphic(new_bus)
            if new_bus_graphic is not None:
                new_bus_graphic.terminal.reassign_terminal(
                    graphic_obj=branch_graphic,
                    another_terminal=bus_graphics.terminal
                )

                branch_graphic.api_object.reassign_bus(
                    old_bus=bus_graphics.api_object,
                    new_bus=new_bus_graphic.api_object
                )

                new_bus_graphic.get_terminal().update()
            else:
                pass

    def move_behind_converter(self, injection_graphics: INJECTION_GRAPHICS):
        """
        This function moved an injection device from an AC bus to another
        newly created DC bus that is connected to a new converter
        :param injection_graphics:
        :return:
        """

        ok = yes_no_question(
            text=self.tr("Are you sure that you want to relocate {device_name} behind a converter?").format(
                device_name=injection_graphics.api_object.name,
            ),
            title=self.tr('Move behind converter')
        )

        if ok:
            old_bus_graphic = self._query_bus_graphic(injection_graphics.api_object.bus)

            new_bus, converter = self.circuit.move_behind_converter(api_object=injection_graphics.api_object)

            if old_bus_graphic is None:
                x0 = injection_graphics.api_object.bus.x
                y0 = injection_graphics.api_object.bus.y + 180
            else:
                x0 = old_bus_graphic.x()
                y0 = old_bus_graphic.y() + 180

            new_bus_graphic_item = self.add_api_bus(
                bus=new_bus,
                injections_by_tpe={
                    injection_graphics.api_object.device_type: [injection_graphics.api_object]
                },
                x0=x0,
                y0=y0
            )
            self.add_to_scene(new_bus_graphic_item)

            new_bus_graphic_item.set_position(x=x0, y=y0)

            self.add_api_vsc(elm=converter)

            # add the graphics for the new bus
            # new_bus_graphic_item.add_object(api_obj=injection_graphics.api_object)

            self._remove_from_scene(injection_graphics.nexus)
            self._remove_from_scene(injection_graphics)

            new_bus_graphic_item.update()
            injection_graphics.update_nexus(injection_graphics.pos())

    def transform_busbar_to_connectivity_grid(self, bus_graphics: BusGraphicItem, x_offset=80):
        """
        Transform the bus into a grid of buses to be able to compute the bus currents
        :param bus_graphics: BusGraphicItem
        :param x_offset: x offset of the new connectivity buses
        """

        # convert a bus into many small buses connected by impedances
        new_buses, new_lines = transform_bus_to_connectivity_grid(grid=self.circuit,
                                                                  busbar=bus_graphics.api_object)

        # add the new buses
        self.add_buses(buses=new_buses)

        # correct the new buses position
        for i, bus in enumerate(new_buses):
            new_bus_graphic = self._query_bus_graphic(bus)
            if new_bus_graphic is not None:
                new_bus_graphic.setPos(bus_graphics.x() + (i * x_offset), bus_graphics.y() + 20)

        # connected branches
        self.reconnect_bus_graphics(bus_graphics=bus_graphics, new_buses=new_buses)

        # Finally delete the old bus
        self.delete_element_utility_function(device=bus_graphics.api_object)

    def convert_busbar_to_voltage_level(self, bus_graphics: BusGraphicItem):
        """

        :param bus_graphics:
        :return:
        """
        vl_wizard = VoltageLevelConversionWizard(
            bus=bus_graphics.api_object,
            grid=self.circuit
        )
        vl_wizard.setModal(True)
        exec_dialog_safely(dialog=vl_wizard)

        if vl_wizard.closed_ok:
            (new_buses,
             conn_buses,
             associated_branches,
             associated_injections,
             reconnection_list) = substation_wizards.transform_bus_into_voltage_level(
                grid=self.circuit,
                bus=bus_graphics.api_object,
                vl_type=vl_wizard.get_vl_type(),
                add_disconnectors=vl_wizard.add_breakers_checkbox.isChecked(),
                bar_by_segments=vl_wizard.bar_by_segments_checkbox.isChecked(),
                skip_injections_reconnection=True,
                enable_transfer_bus=vl_wizard.enable_transfer_bus_checkbox.isChecked(),
                reducible_branches=vl_wizard.reducible_branches_checkbox.isChecked(),
                bay_assignments=vl_wizard.get_bay_assignments(),
                x0=bus_graphics.x(),
                y0=bus_graphics.y()
            )

            # add the newly created buses to the diagram (with all their stuff that's not there already)
            # Use all buses (including internal ones) to ensure all switches are drawn
            self.add_buses_deep(buses=new_buses)

            # Force redraw of all new bus graphics to ensure connections are visible
            for new_bus in new_buses:
                bus_graphic = self._query_bus_graphic(new_bus)
                if bus_graphic is not None:
                    bus_graphic.update()
                    terminal = bus_graphic.get_terminal()
                    if terminal is not None:
                        terminal.update()

            # reconnect graphics
            # self.reconnect_bus_graphics(bus_graphics=bus_graphics, new_buses=conn_buses)
            # Note: graphical shunts have been added already
            # the order of the buses matches the order of the branches because the
            # transformation function already works like that
            for element, old_bus, new_bus in reconnection_list:
                new_bus_graphic = self._query_bus_graphic(new_bus)
                branch_graphic = self._query_line_graphic(element)

                # Skip if graphics not found
                if new_bus_graphic is None:
                    print(f"Warning: No graphic found for bus {new_bus.name}")
                    continue
                if branch_graphic is None:
                    print(f"Warning: No graphic found for element {element.name}")
                    continue

                # At this point the API branch has been reassigned already
                terminal = new_bus_graphic.get_terminal()
                if terminal is not None:
                    terminal.reassign_terminal(
                        graphic_obj=branch_graphic,
                        another_terminal=bus_graphics.terminal
                    )
                    branch_graphic.api_object.reassign_bus(old_bus=old_bus,
                                                           new_bus=new_bus_graphic.api_object)
                    branch_graphic.update_ports()
                    branch_graphic.redraw()
                else:
                    pass

                if terminal is not None:
                    terminal.update()

            # Finally delete the old bus
            self.delete_element_utility_function(device=bus_graphics.api_object)

            # Update scene to ensure visual refresh of newly added elements
            # Invalidate the entire scene to force redraw of all items
            self.diagram_scene.invalidate()
            self.diagram_scene.update()
            self.editor_graphics_view.viewport().update()

            # select the new buses
            for new_bus in new_buses:
                new_bus_graphic = self._query_bus_graphic(new_bus)
                if new_bus_graphic is not None:
                    new_bus_graphic.setSelected(True)

        else:
            self.gui.show_warning_toast("No conversion made...")


def generate_schematic_diagram(buses: List[Bus],
                               lines: List[Line],
                               dc_lines: List[DcLine],
                               transformers2w: List[Transformer2W],
                               transformers3w: List[Transformer3W],
                               transformers_nw: List[TransformerNW],
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
    Generate diagram with the elements
    :param buses: list of Bus objects
    :param lines: list of Line objects
    :param dc_lines: list of DcLine objects
    :param transformers2w: list of Transformer Objects
    :param transformers3w: list of Transformer3W Objects
    :param transformers_nw: list of TransformerNW Objects
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

    add_to_schematic_diagram(diagram=diagram,
                             buses=buses,
                             lines=lines,
                             dc_lines=dc_lines,
                             transformers2w=transformers2w,
                             transformers3w=transformers3w,
                             transformers_nw=transformers_nw,
                             windings=windings,
                             hvdc_lines=hvdc_lines,
                             vsc_devices=vsc_devices,
                             upfc_devices=upfc_devices,
                             series_reactances=series_reactances,
                             switches=switches,
                             fluid_nodes=fluid_nodes,
                             fluid_paths=fluid_paths,
                             explode_factor=explode_factor,
                             prog_func=prog_func,
                             text_func=text_func)

    return diagram


def add_to_schematic_diagram(diagram: SchematicDiagram,
                             buses: List[Bus],
                             lines: List[Line],
                             dc_lines: List[DcLine],
                             transformers2w: List[Transformer2W],
                             transformers3w: List[Transformer3W],
                             transformers_nw: List[TransformerNW],
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
                             text_func: Union[Callable, None] = None, ) -> SchematicDiagram:
    """
    Add a elements to the diagram
    :param diagram: SchematicDiagram
    :param buses: list of Bus objects
    :param lines: list of Line objects
    :param dc_lines: list of DcLine objects
    :param transformers2w: list of Transformer Objects
    :param transformers3w: list of Transformer3W Objects
    :param transformers_nw: list of TransformerNW Objects
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
    """

    # first create the buses
    if text_func is not None:
        text_func('Creating schematic buses')

    nn = len(buses)
    for i, bus in enumerate(buses):

        if prog_func is not None:
            prog_func((i + 1) / nn * 100.0)

        if not bus.internal:  # 3w transformer buses are not represented

            # correct possible nonsense
            if np.isnan(bus.y):
                bus.y = 0.0
            if np.isnan(bus.x):
                bus.x = 0.0

            x = int(bus.x * explode_factor)
            y = int(bus.y * explode_factor)
            diagram.set_point(device=bus, location=GraphicLocation(x=x, y=y, h=bus.h, w=bus.w, api_object=bus))

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

            diagram.set_point(device=elm, location=GraphicLocation(api_object=elm))

    # --------------------------------------------------------------------------------------------------------------

    add_devices_list(cls="fluid_nodes", dev_lst=fluid_nodes)
    add_devices_list(cls="transformers3w", dev_lst=transformers3w)
    add_devices_list(cls="transformers_nw", dev_lst=transformers_nw)

    add_devices_list(cls="lines", dev_lst=lines)
    add_devices_list(cls="dc_lines", dev_lst=dc_lines)
    add_devices_list(cls="transformers2w", dev_lst=transformers2w)
    add_devices_list(cls="series_reactances", dev_lst=series_reactances)
    add_devices_list(cls="switches", dev_lst=switches)
    add_devices_list(cls="windings", dev_lst=windings)
    add_devices_list(cls="hvdc_lines", dev_lst=hvdc_lines)

    # TODO: Review this merge
    add_devices_list(cls="vsc_devices", dev_lst=vsc_devices)

    # Handle VSC devices specially to preserve their coordinates
    # if text_func is not None:
    #     text_func('Adding VSC devices to the diagram')
    #
    # nn = len(vsc_devices)
    # for i, elm in enumerate(vsc_devices):
    #     if prog_func is not None:
    #         prog_func((i + 1) / nn * 100.0)
    #
    #     # Preserve VSC coordinates like buses do
    #     x = int(elm.x * explode_factor) if not np.isnan(elm.x) else 0
    #     y = int(elm.y * explode_factor) if not np.isnan(elm.y) else 0
    #     diagram.set_point(device=elm, location=GraphicLocation(x=x, y=y))

    # TODO: End review here

    add_devices_list(cls="upfc_devices", dev_lst=upfc_devices)
    add_devices_list(cls="fluid_paths", dev_lst=fluid_paths)

    # --------------------------------------------------------------------------------------------------------------

    return diagram


def generate_grid_diagram(circuit: MultiCircuit,
                          name: str = "",
                          prog_func: Union[Callable, None] = None,
                          text_func: Union[Callable, None] = None) -> SchematicDiagram:
    """
    Shortcut to generate diagram from a MultiCircuit object
    :param circuit: MultiCircuit
    :param name: name of the diagram
    :param prog_func: progress callback
    :param text_func: text callback
    :return: SchematicDiagram
    """
    return generate_schematic_diagram(buses=circuit.get_buses(),
                                      lines=circuit.get_lines(),
                                      dc_lines=circuit.get_dc_lines(),
                                      transformers2w=circuit.get_transformers2w(),
                                      transformers3w=circuit.get_transformers3w(),
                                      transformers_nw=circuit.get_transformers_nw(),
                                      windings=circuit.get_windings(),
                                      hvdc_lines=circuit.get_hvdc(),
                                      vsc_devices=circuit.get_vsc(),
                                      upfc_devices=circuit.get_upfc(),
                                      series_reactances=circuit.get_series_reactances(),
                                      switches=circuit.get_switches(),
                                      fluid_nodes=circuit.get_fluid_nodes(),
                                      fluid_paths=circuit.get_fluid_paths(),
                                      explode_factor=1.0,
                                      prog_func=prog_func,
                                      text_func=text_func,
                                      name=name)


def get_devices_to_expand(circuit: MultiCircuit,
                          buses_set: List[Bus],
                          max_level: int = 1,
                          restrict_to_voltage_levels: Set | None = None) -> Tuple[List[Bus],
List[Line],
List[DcLine],
List[Transformer2W],
List[Transformer3W],
List[TransformerNW],
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
    :param buses_set: List of Bus
    :param max_level: max expansion level
    :param restrict_to_voltage_levels: If provided, only expand to buses within these voltage levels.
                                       This prevents expansion into the external network when drawing
                                       voltage level conversions.
    :return:
    """

    branch_idx = list()
    bus_idx = list()

    bus_dict = circuit.get_bus_index_dict()

    # get all Branches
    all_branches = circuit.get_branches(add_vsc=True, add_hvdc=True, add_switch=True)
    branch_dict = {b: i for i, b in enumerate(all_branches)}

    # Build index of branches by bus for O(1) lookup instead of scanning all branches
    # This changes the algorithm complexity from O(n*m) to O(n+m) where n=buses, m=branches
    # Hence drawing voltage level conversions should be much faster, thus fixing REE complaints
    branches_by_bus = defaultdict(list)
    has_winding = False
    for br in all_branches:
        if br.bus_from is not None:
            branches_by_bus[br.bus_from].append(br)
        else:
            pass

        if br.bus_to is not None:
            branches_by_bus[br.bus_to].append(br)
        else:
            pass

        if isinstance(br, Winding):
            has_winding = True
        else:
            pass

    # create a pool of buses
    bus_pool: List[Tuple[Bus, int]] = list()  # store the bus objects and their level from the root

    for b in buses_set:
        if b is not None:
            bus_pool.append((b, 0))
        else:
            pass

    # create maps of the multi-winding transformers that own the windings
    windings2tr3 = dict()
    windings2tr_nw = dict()

    for tr3 in circuit.transformers3w:
        windings2tr3[tr3.winding1] = tr3
        windings2tr3[tr3.winding2] = tr3
        windings2tr3[tr3.winding3] = tr3
        tr3.bus0.graphic_type = BusGraphicType.Internal  # make sure these don't show up

    for tr_nw in circuit.transformers_nw:
        tr_nw.bus0.graphic_type = BusGraphicType.Internal
        for winding in tr_nw.windings:
            windings2tr_nw[winding] = tr_nw

    buses_set = set()
    fluid_nodes = set()
    selected_branches = set()
    visited = set()
    # If there are windings, we need an extra level to represent whole 3-winding transformers
    max_level_offset = 1 if has_winding else 0

    while len(bus_pool) > 0:

        # search the next bus
        bus, level = bus_pool.pop()

        bus_index = bus_dict.get(bus, None)
        if bus_index is not None:
            bus_idx.append(bus_index)

            # add searched bus
            if bus.graphic_type == BusGraphicType.BusBar or bus.graphic_type == BusGraphicType.Connectivity:
                buses_set.add(bus)
            else:
                pass

            if level < (max_level + max_level_offset):

                # Use the built index for O(1) lookup of branches connected to this bus
                for br in branches_by_bus.get(bus, []):

                    # Always add the branch if connected to current bus
                    selected_branches.add(br)

                    # Determine the other bus and add if not visited
                    if br.bus_from == bus:
                        other_bus = br.bus_to
                    elif br.bus_to == bus:
                        other_bus = br.bus_from
                    else:
                        other_bus = None

                    if other_bus is not None and other_bus not in visited:
                        # If voltage level restriction is active, only follow to buses within allowed voltage levels
                        should_expand = True
                        if restrict_to_voltage_levels is not None:
                            other_vl = other_bus.voltage_level
                            should_expand = other_vl in restrict_to_voltage_levels
                        else:
                            pass

                        if should_expand:
                            bus_pool.append((other_bus, level + 1))
                            visited.add(other_bus)
                        else:
                            pass
                    else:
                        pass

            else:
                pass
        else:
            pass

    # sort Branches
    lines: List[Line] = list()
    dc_lines: List[DcLine] = list()
    transformers2w: List[Transformer2W] = list()
    transformers3w_set: Set[Transformer3W] = set()
    transformers_nw_set: Set[TransformerNW] = set()
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

        elif obj.device_type == DeviceType.WindingDevice:
            windings.append(obj)

            # For each winding, add its owning multi-winding transformer container.
            tr3 = windings2tr3.get(obj, None)
            if tr3 is not None:
                transformers3w_set.add(tr3)
            tr_nw = windings2tr_nw.get(obj, None)
            if tr_nw is not None:
                transformers_nw_set.add(tr_nw)

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
            raise Exception(f'Unrecognized branch type {obj.device_type.value}')

    # we need to add the tr3 buses, if any of the buses is selected
    buses_tr3 = set()
    for tr3 in transformers3w_set:
        # print(tr3)
        if tr3.bus1 in buses_set:
            buses_tr3.add(tr3.bus2)
            buses_tr3.add(tr3.bus3)
        elif tr3.bus2 in buses_set:
            buses_tr3.add(tr3.bus1)
            buses_tr3.add(tr3.bus3)
        elif tr3.bus3 in buses_set:
            buses_tr3.add(tr3.bus1)
            buses_tr3.add(tr3.bus2)

    for b in buses_tr3:
        buses_set.add(b)

    buses_tr_nw = set()
    for tr_nw in transformers_nw_set:
        if any(bus in buses_set for bus in tr_nw.buses if bus is not None):
            for bus in tr_nw.buses:
                if bus is not None:
                    buses_tr_nw.add(bus)

    for b in buses_tr_nw:
        buses_set.add(b)

    return (list(buses_set), lines, dc_lines, transformers2w,
            list(transformers3w_set),
            list(transformers_nw_set),
            windings, hvdc_lines, vsc_converters, upfc_devices, series_reactances, switches,
            list(fluid_nodes), fluid_paths)


def make_vicinity_diagram(circuit: MultiCircuit,
                          root_bus: Bus,
                          max_level: int = 1,
                          prog_func: Union[Callable, None] = None,
                          text_func: Union[Callable, None] = None,
                          name: str = "") -> SchematicDiagram:
    """
    Create a vicinity diagram
    :param circuit: MultiCircuit
    :param root_bus: Bus
    :param max_level: max expansion level
    :param prog_func: progress function pointer
    :param text_func: Text progress function
    :param name: name of the diagram
    :return:
    """

    (buses,
     lines, dc_lines, transformers2w,
     transformers3w, transformers_nw, windings, hvdc_lines,
     vsc_converters, upfc_devices,
     series_reactances, switches,
     fluid_nodes, fluid_paths) = get_devices_to_expand(circuit=circuit, buses_set=[root_bus], max_level=max_level)

    # Draw schematic subset
    diagram = generate_schematic_diagram(
        buses=list(buses),
        lines=lines,
        dc_lines=dc_lines,
        transformers2w=transformers2w,
        transformers3w=transformers3w,
        transformers_nw=transformers_nw,
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
        name=root_bus.name + 'vicinity' if len(name) == 0 else name
    )

    return diagram


def make_diagram_from_buses(circuit: MultiCircuit,
                            buses: List[Bus] | Set[Bus],
                            name='Diagram from selection',
                            prog_func: Union[Callable, None] = None,
                            text_func: Union[Callable, None] = None) -> SchematicDiagram:
    """
    Create a vicinity diagram
    :param circuit: MultiCircuit
    :param buses: List of Bus
    :param name: name of the diagram
    :param prog_func:
    :param text_func:
    :return:
    """

    (buses,
     lines, dc_lines, transformers2w,
     transformers3w, transformers_nw, windings, hvdc_lines,
     vsc_converters, upfc_devices,
     series_reactances, switches,
     fluid_nodes, fluid_paths) = get_devices_to_expand(circuit=circuit, buses_set=buses, max_level=1)

    # Draw schematic subset
    diagram = generate_schematic_diagram(buses=list(buses),
                                         lines=lines,
                                         dc_lines=dc_lines,
                                         transformers2w=transformers2w,
                                         transformers3w=transformers3w,
                                         transformers_nw=transformers_nw,
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
                                         name=name)

    return diagram
