# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import List, Set, Dict, Union, Tuple, Generator, TYPE_CHECKING
from time import perf_counter
import numpy as np
import cv2

from PySide6 import QtCore
from PySide6.QtGui import QIcon, QImage
from PySide6.QtWidgets import (QListView, QTableView, QVBoxLayout, QHBoxLayout, QFrame, QSplitter, QAbstractItemView,
                               QGraphicsItem, QToolBox, QComboBox, QDialog, QLabel, QGraphicsView)

from VeraGrid.Gui.Diagrams.generic_graphics import GenericDiagramWidget
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.hvdc_line import HvdcLine
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Branches.upfc import UPFC
from VeraGridEngine.basic_structures import Vec, CxVec, IntVec
from VeraGridEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from VeraGridEngine.Devices.Diagrams.map_diagram import MapDiagram
from VeraGridEngine.Simulations.types import DRIVER_OBJECTS
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import DeviceType, SimulationTypes, ResultTypes, PrpCat
import VeraGridEngine.Devices.Diagrams.palettes as palettes

from VeraGrid.Gui.Diagrams.graphics_manager import GraphicsManager, ALL_GRAPHICS
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionNexusPathItem
from VeraGrid.Gui.DeviceEditors.device_editor_factory import build_device_editor_dialog
from VeraGrid.Gui.dialog_lifecycle import exec_dialog_safely
from VeraGrid.Gui.general_dialogues import DeleteDialogue
from VeraGrid.Gui.messages import yes_no_question, info_msg
from VeraGrid.Gui.object_model import ObjectsModel
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.PlotDialogue.result_table_data import get_result_table_series
from VeraGrid.Gui.PlotDialogue.qt_chart_widget import GraphsWidget
import VeraGrid.Gui.gui_functions as gf
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate

if TYPE_CHECKING:
    from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import MapLibraryModel
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicLibraryModel
    from VeraGrid.Gui.Main.SubClasses.Model.diagrams import DiagramsMain
    from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI


def change_font_size(obj, font_size: int):
    """

    :param obj:
    :param font_size:
    :return:
    """
    font1 = obj.font()
    font1.setPointSize(font_size)
    obj.setFont(font1)


def qimage_tocv2_by_disk(qimage: QImage, logger: Logger, file_path):
    """

    :param qimage: Qimage
    :param logger: Logger
    :param file_path: temp file path
    :return:
    """
    # Convert QImage to PNG format and save
    if not qimage.save(file_path, "PNG"):
        logger.add_error(msg=f"Error: Could not save QImage to {file_path}")
        return None

    # Use OpenCV to read the saved image
    opencv_image = cv2.imread(file_path)
    if opencv_image is None:
        logger.add_error(msg=f"Error: Could not save QImage to {file_path}")
        return None

    return opencv_image


def qimage_to_cv(qimage: QImage, logger: Logger, force_disk=False) -> np.ndarray:
    """
    Convert a image from Qt to an OpenCV image
    :param qimage: Qimage
    :param logger: Logger
    :param force_disk: if true, the image is converted by saving to disk and loading again with open-cv
    :return: OpenCv matrix
    """
    width = qimage.width()
    height = qimage.height()

    if force_disk:
        opencv_image = qimage_tocv2_by_disk(qimage, logger, file_path="__img__.png")

        return opencv_image
    else:
        try:
            # Convert to a 4-byte-per-pixel format so row padding stays aligned and predictable.
            if qimage.format() != QImage.Format.Format_RGBA8888:
                qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)

            stride = qimage.bytesPerLine()
            ptr = qimage.constBits()
            buffer = np.frombuffer(ptr, dtype=np.uint8, count=height * stride)
            rgba_mat = buffer.reshape((height, stride // 4, 4))[:, :width, :]
            cv_mat = cv2.cvtColor(rgba_mat, cv2.COLOR_RGBA2BGR)

            return cv_mat

        except (ValueError, TypeError, BufferError) as e:

            logger.add_error(msg=f"Could not convert frame: {e}, failed over to second image conversion method.")

            try:
                # Fallback to a 4-byte RGB32 image and then drop the alpha channel explicitly.
                qimage = qimage.convertToFormat(QImage.Format.Format_RGB32)

                ptr = qimage.constBits()
                stride = qimage.bytesPerLine()

                arr = np.frombuffer(ptr, dtype=np.uint8, count=height * stride).reshape((height, stride // 4, 4))
                arr = arr[:, :width, :]
                cv_mat = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

                return cv_mat
            except (ValueError, TypeError, BufferError) as e2:
                logger.add_error(msg=f"Could not convert frame: {e2}, failed over to disk converison method")

                # try the last method, saving to disk and reading again

                opencv_image = qimage_tocv2_by_disk(qimage, logger, file_path="__img__.png")

                return opencv_image


class BaseDiagramWidget(QSplitter):
    """
    Common diagram widget to host common functions
    for the schematic and the map
    """

    LIBRARY_TRANSLATION_CONTEXT: str = "BlockEditorWindow"
    PROPERTIES_TRANSLATION_CONTEXT: str = "TemplateDeviceEditorDialog"

    def __init__(self,
                 gui: VeraGridMainGUI | DiagramsMain,
                 diagram: Union[SchematicDiagram, MapDiagram],
                 library_model: Union[MapLibraryModel, SchematicLibraryModel],
                 time_index: Union[None, int] = None):
        """
        Constructor
        :param gui:
        :param diagram:
        :param library_model:
        :param time_index:
        """
        QSplitter.__init__(self)

        self.gui = gui

        # --------------------------------------------------------------------------------------------------------------
        # Widget creation
        # --------------------------------------------------------------------------------------------------------------
        # Widget layout and child widgets:
        self.horizontal_layout = QHBoxLayout(self)

        # Table to display object's properties
        self.object_editor_table = QTableView(self)
        self.object_editor_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.object_editor_table.customContextMenuRequested.connect(self.show_object_editor_table_context_menu)
        # change_font_size(self.object_editor_table, 9)
        # change_font_size(self.object_editor_table.verticalHeader(), 9)
        # change_font_size(self.object_editor_table.horizontalHeader(), 9)

        self.filter_combo = QComboBox()
        prop_filter_mdl = gf.ComboModel(
            icon_enum_values=[
                (PrpCat.All,":/Icons/icons/edit.png"),
                (PrpCat.TP,":/Icons/icons/automatic_layout.png"),
                (PrpCat.PF,":/Icons/icons/pf.png"),
                (PrpCat.PF3,":/Icons/icons/pf3.png"),
                (PrpCat.SC,":/Icons/icons/short_circuit.png"),
                (PrpCat.OPF,":/Icons/icons/dcopf.png"),
                (PrpCat.CON,":/Icons/icons/otdf.png"),
                (PrpCat.REL,":/Icons/icons/reliability.png"),
                (PrpCat.NTC,":/Icons/icons/ntc_opf.png"),
                (PrpCat.INV,":/Icons/icons/expansion_planning.png"),
                (PrpCat.RMS,":/Icons/icons/dyn.png"),
                (PrpCat.EMT,":/Icons/icons/dyn_emt.png"),
            ],
            translate=self.tr
        )
        self.filter_combo.setModel(prop_filter_mdl)

        # Actual libraryView object
        self.library_view = QListView(self)
        self.library_view.setViewMode(self.library_view.ViewMode.ListMode)
        self.library_view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        # change_font_size(self.library_view, 9)

        # library model
        self.library_model = library_model
        self.library_view.setModel(self.library_model)

        # create library frame
        self.frame1 = QFrame()
        self.frame1_layout = QVBoxLayout()
        self.frame1_layout.setContentsMargins(0, 0, 0, 0)

        self.frame1_layout.addWidget(self.library_view)
        self.frame1.setLayout(self.frame1_layout)

        # create properties frame
        self.frame2 = QFrame()
        self.frame2_layout = QVBoxLayout()
        self.frame2_layout.setContentsMargins(0, 0, 0, 0)

        self.frame2.setLayout(self.frame2_layout)
        self.frame2_layout.addWidget(self.filter_combo)
        self.frame2_layout.addWidget(self.object_editor_table)

        # Add the library and properties views as toolbox pages.
        self.left_panel_toolbox: QToolBox = QToolBox(self)
        self.left_panel_toolbox.addItem(
            self.frame1,
            QIcon(":/Icons/icons/Catalogue.png"),
            self._translate_library_label(),
        )
        self.left_panel_toolbox.addItem(
            self.frame2,
            QIcon(":/Icons/icons/data.png"),
            self._translate_properties_label(),
        )
        self.addWidget(self.left_panel_toolbox)
        # self.addWidget(self.editor_graphics_view)

        # self.setStretchFactor(0, 0)
        # self.setStretchFactor(1, 2000)

        self.api_object: ALL_DEV_TYPES | None = None
        # --------------------------------------------------------------------------------------------------------------

        self.filter_combo.currentIndexChanged.connect(self.refresh_editor_model)

        # --------------------------------------------------------------------------------------------------------------
        # diagram to store the objects locations
        self.diagram: Union[SchematicDiagram, MapDiagram] = diagram

        # class to handle the relationships between widgets and API objects
        self.graphics_manager = GraphicsManager()

        # current time index from the GUI (None or 0, 1, 2, ..., n-1)
        self._time_index: Union[None, int] = time_index

        # logger
        self.logger: Logger = Logger()

        self.results_dictionary: Dict[SimulationTypes, DRIVER_OBJECTS] = dict()

        # video pointer
        self._video: Union[None, cv2.VideoWriter] = None
        self._video_export_active: bool = False
        self._video_time_label: QLabel | None = None
        self._video_time_label_view: QGraphicsView | None = None
        self._video_time_label_position: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignRight

    def register_video_time_label_canvas(self, view: QGraphicsView) -> None:
        """
        Register the canvas that will temporarily host the video timestamp.

        :param view: Graphics canvas captured for video frames.
        :return: None.
        """
        self._video_time_label_view = view

    def set_video_time_label_position(self, position: QtCore.Qt.AlignmentFlag) -> None:
        """
        Set the timestamp corner on the canvas.

        :param position: Horizontal and vertical alignment flags.
        :return: None.
        """
        self._video_time_label_position = position
        self._position_video_time_label()

    def _position_video_time_label(self) -> None:
        """
        Position the timestamp label inside its canvas.

        :return: None.
        """
        if self._video_time_label is not None and self._video_time_label_view is not None:
            label: QLabel = self._video_time_label
            view: QGraphicsView = self._video_time_label_view
            label.adjustSize()
            margin: int = 12
            x: int = margin
            y: int = margin
            if self._video_time_label_position & QtCore.Qt.AlignmentFlag.AlignRight:
                x = view.width() - label.width() - margin
            else:
                pass
            if self._video_time_label_position & QtCore.Qt.AlignmentFlag.AlignBottom:
                y = view.height() - label.height() - margin
            else:
                pass
            label.move(max(x, margin), max(y, margin))
        else:
            pass

    def _set_video_time_label_index(self, time_index: int | None) -> None:
        """
        Update the temporary timestamp label for one video frame.

        :param time_index: Time-series index.
        :return: None.
        """
        if self._video_time_label is not None and time_index is not None:
            time_values: object = self.circuit.get_time_array()
            if time_values is not None and 0 <= time_index < len(time_values):
                self._video_time_label.setText(time_values[time_index].strftime("%Y-%m-%d %H:%M:%S"))
                self._position_video_time_label()
                self._video_time_label.show()
            else:
                self._video_time_label.hide()
        elif self._video_time_label is not None:
            self._video_time_label.hide()
        else:
            pass

    def set_video_time_index(self, time_index: int | None) -> None:
        """
        Set the timestamp shown in the current video frame.

        :param time_index: Time-series index.
        :return: None.
        """
        self._set_video_time_label_index(time_index=time_index)

    def _create_video_time_label(self) -> None:
        """
        Create the temporary timestamp widget immediately before recording.

        :return: None.
        """
        if self._video_time_label is None and self._video_time_label_view is not None:
            self._video_time_label = QLabel(self._video_time_label_view)
            self._video_time_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._video_time_label.setStyleSheet(
                "QLabel { background-color: rgba(0, 0, 0, 170); color: white; "
                "padding: 4px 8px; border-radius: 3px; }"
            )
            font = self._video_time_label.font()
            font.setPointSize(16)
            self._video_time_label.setFont(font)
            self._video_time_label.hide()
        else:
            pass

    def remove_video_time_label(self) -> None:
        """
        Delete the temporary timestamp widget after video rendering.

        :return: None.
        """
        if self._video_time_label is not None:
            self._video_time_label.deleteLater()
            self._video_time_label = None
        else:
            pass

    def changeEvent(self, event: QtCore.QEvent) -> None:
        """
        Refresh runtime-owned diagram strings after a Qt language change.

        :param event: Incoming Qt change event.
        :return: None.
        """
        QSplitter.changeEvent(self, event)

        if event.type() == QtCore.QEvent.Type.LanguageChange:
            self.refresh_runtime_translations()
        else:
            pass

    def _translate_library_label(self) -> str:
        """
        Return the translated label used by the shared diagram library tab.

        :return: User-facing library label.
        """
        return QtCore.QCoreApplication.translate(
            self.LIBRARY_TRANSLATION_CONTEXT,
            "Library",
        )

    def _translate_properties_label(self) -> str:
        """
        Return the translated label used by the shared diagram properties tab.

        :return: User-facing properties label.
        """
        return QtCore.QCoreApplication.translate(
            self.PROPERTIES_TRANSLATION_CONTEXT,
            "Properties",
        )

    def refresh_runtime_translations(self) -> None:
        """
        Refresh the diagram strings created directly from Python code.

        :return: None.
        """
        self.left_panel_toolbox.setItemText(0, self._translate_library_label())
        self.left_panel_toolbox.setItemText(1, self._translate_properties_label())
        self.library_model.retranslate()

    def set_video_export_active(self, value: bool) -> None:
        """
        Set whether the diagram is being updated for video export.

        :param value: Export mode flag
        """
        self._video_export_active = value

    def is_video_export_active(self) -> bool:
        """
        Get whether the diagram is being updated for video export.

        :return: Export mode flag
        """
        return self._video_export_active

    def items(self) -> Generator[ALL_GRAPHICS, None, None]:
        """
        Iterable through all graphics registered in the graphics manager
        :return: ALL_GRAPHICS one by one
        """
        for device_tpe, graphics_dict in self.graphics_manager.graphic_dict.items():
            for idtag, graphical_obj in graphics_dict.items():
                yield graphical_obj

    @property
    def circuit(self) -> MultiCircuit:
        """
        Always returns the circuit that the main window currently considers active.
        This ensures that any element added via the diagram goes to the correct
        scenario circuit rather than a stale stored reference.
        """
        return self.gui.circuit

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

    def get_selected(self) -> List[GenericDiagramWidget]:
        """

        :return:
        """
        print(f"'get_selected' Not implemented for {str(self)}")
        return list()

    def _get_selection_api_objects(self) -> List[ALL_DEV_TYPES]:
        """
        Get a list of the API objects from the selection
        :return: List[ALL_DEV_TYPES]
        """
        return list()

    def _remove_from_scene(self, graphic_object: QGraphicsItem | GenericDiagramWidget) -> None:
        """
        Remove item from the diagram scene
        :param graphic_object: Graphic object associated
        """
        print(f"'remove_from_scene' Not implemented for {str(self)}")

    def remove_element(self,
                       device: ALL_DEV_TYPES,
                       graphic_object: GenericDiagramWidget | QGraphicsItem | None = None,
                       delete_from_db: bool = False) -> bool:
        """
        Remove device from the diagram and the database.
        If removing from the database, this propagates to all diagrams
        :param device: EditableDevice
        :param graphic_object: optionally provide the graphics object associated
        :param delete_from_db: Delete the element also from the database?
        :return: True if managed to delete_with_dialogue the object
        """
        if graphic_object is not None and device is not None:

            # Unregister this object from other objects that have references of it
            # i.e. unregister a line from the 2 buses that host connections to it
            # i.e. unregister a load from the bus that points to it
            graphic_object.delete_from_associations()

            if delete_from_db:
                self.circuit.delete_element(obj=device)

            # # For any other associated, graphic, delete too
            # for child_graphic in graphic_object.get_associated_widgets():
            #
            #     if delete_from_db:
            #         self.circuit.delete_element(obj=child_graphic.api_object)
            #
            #     # Warning: recursive call for devices that may have further sub-graphics (i.e. the nexus)
            #     self.remove_element(device=child_graphic.api_object,
            #                         graphic_object=child_graphic,
            #                         delete_from_db=delete_from_db)

            # Delete any other QWidget that is associated to this, and that we don't know about explicitly
            # i.e. the nexus of the loads, generators, etc...
            for child_graphic in graphic_object.get_extra_graphics():
                # simpler graphics associated, simply delete_with_dialogue
                self._remove_from_scene(graphic_object=child_graphic)

            # NOTE: This function already deleted from the database and other diagrams
            self.delete_element_utility_function(device=device, propagate=delete_from_db)
            self.object_editor_table.setModel(None)

            return True

        if graphic_object is None and device is not None:

            if delete_from_db:
                self.circuit.delete_element(obj=device)
                self.delete_element_utility_function(device=device, propagate=delete_from_db)
                self.object_editor_table.setModel(None)

            else:
                pass

            return True

        else:
            self.gui.show_warning_toast(f"Graphic object {graphic_object} and device {device} are none")
            self.object_editor_table.setModel(None)
            return False

    def delete_element_utility_function(self, device: ALL_DEV_TYPES, propagate: bool = True,
                                        graphic_object: ALL_GRAPHICS | None = None):
        """
        This function is a utility function to call this function in other diagrams through the GUI
        :param device: ALL_DEV_TYPES
        :param propagate: propagate
        :param graphic_object: QGraphicsItem
        :return:
        """
        self.diagram.delete_device(device=device)

        if graphic_object is None:
            graphic_object: QGraphicsItem = self.graphics_manager.delete_device(device=device)

        if graphic_object is not None:
            self._remove_from_scene(graphic_object)

            for extra_grph in graphic_object.get_extra_graphics():
                self._remove_from_scene(extra_grph)

        if propagate:
            self.gui.call_delete_db_element(caller=self, api_obj=device)

    def delete_with_dialogue(self, selected: List[GenericDiagramWidget], delete_from_db: bool) -> Tuple[bool, bool]:
        """
        Delete elements with a dialogue of all the dependencies
        :param selected: list of selected widgets
        :param delete_from_db: initial value for the delete from db option
        :return deleted? delete_from_db?
        """
        if len(selected) > 0:

            # Collect affected devices by stable id instead of hashing the device object.
            extended: List[ALL_DEV_TYPES] = list()
            extended_keys: Set[Tuple[str, str]] = set()

            for graphic_obj in selected:

                if graphic_obj is not None:
                    owner_graphic: GenericDiagramWidget | None = self._get_delete_owner_graphic(graphic_obj=graphic_obj)

                    if owner_graphic is not None:
                        device: ALL_DEV_TYPES = owner_graphic.api_object
                        device_key: Tuple[str, str] = (device.device_type.value, device.idtag)
                        if device_key not in extended_keys:
                            extended_keys.add(device_key)
                            extended.append(device)
                        else:
                            pass

                        for child_item in owner_graphic.get_associated_devices():
                            if child_item is not None:
                                child_key: Tuple[str, str] = (child_item.device_type.value, child_item.idtag)
                                if child_key not in extended_keys:
                                    extended_keys.add(child_key)
                                    extended.append(child_item)
                                else:
                                    pass
                            else:
                                pass
                    else:
                        pass

            extended_lst: List[ALL_DEV_TYPES] = extended

            dlg = DeleteDialogue(
                names_list=[f"{device.device_type.value}: "
                            f"{device.name}"
                            for device in extended_lst],
                delete_from_db=delete_from_db,
                title="Delete Selected",
                checks=False,
            )

            dlg.setModal(True)
            exec_dialog_safely(dialog=dlg)

            if dlg.is_accepted:
                for device in extended_lst:
                    self.remove_element(device=device,
                                        graphic_object=self.graphics_manager.query(elm=device),
                                        delete_from_db=dlg.delete_from_db)

                return True, dlg.delete_from_db
            else:
                return False, False
        else:
            self.gui.show_warning_toast("Choose some elements to delete_with_dialogue")
            return False, False

    def _get_delete_owner_graphic(self, graphic_obj: QGraphicsItem) -> GenericDiagramWidget | None:
        """
        Resolve one selected graphics item to the diagram widget that owns the device.

        Some selectable helper items, such as injection nexus paths, are not
        ``GenericDiagramWidget`` instances. Deletion must still target the owning
        device widget so the dependency dialogue and removal flow remain valid.

        :param graphic_obj: Selected graphics item.
        :return: Owning diagram widget or ``None`` when unsupported.
        """
        if isinstance(graphic_obj, GenericDiagramWidget):
            return graphic_obj
        elif isinstance(graphic_obj, InjectionNexusPathItem):
            owner_item: QGraphicsItem = graphic_obj.owner_item

            if isinstance(owner_item, GenericDiagramWidget):
                return owner_item
            else:
                return None
        else:
            return None

    def delete_selected_from_widget(self, delete_from_db: bool) -> None:
        """
        Delete the selected items from the diagram
        :param delete_from_db:
        """
        self.delete_with_dialogue(selected=self.get_selected(),
                                  delete_from_db=delete_from_db)

    def delete_diagram_elements(self, elements: List[ALL_DEV_TYPES]):
        """
        Delete device from the diagram registry
        :param elements: list of elements to delete
        """
        for elm in elements:
            graphic_object: QGraphicsItem = self.graphics_manager.delete_device(device=elm)

            # this calls internally to delete_element_utility_function
            self.remove_element(
                device=elm,
                graphic_object=graphic_object
            )

            self.delete_element_utility_function(elm, graphic_object=graphic_object)

    def set_time_index(self, time_index: Union[int, None]):
        """
        Set the time index of the table
        :param time_index: None or integer value
        """
        self._time_index = time_index
        self._set_video_time_label_index(time_index=time_index)

        mdl = self.object_editor_table.model()
        if isinstance(mdl, ObjectsModel):
            mdl.set_time_index(time_index=self._time_index)

    def get_time_index(self) -> Union[int, None]:
        """
        Get the time index
        :return: int, None
        """
        return self._time_index

    def refresh_editor_model(self):
        """
        Function to call when the objects' filter changes
        """
        if self.api_object is not None:
            self.set_editor_model(api_object=self.api_object)

    def open_hosted_device_editor(self, hosted_device: EditableDevice) -> None:
        """
        Open the best available editor for one hosted device.

        :param hosted_device: Device referenced by the clicked cell.
        :return: None.
        """
        # Use the diagram circuit so selectors and specialized editor tabs have the same model context.
        dialog: QDialog = build_device_editor_dialog(api_object=hosted_device,
                                                     circuit=self.circuit,
                                                     main_gui=self.gui)
        exec_dialog_safely(dialog=dialog)

    def show_object_editor_table_context_menu(self, position: QtCore.QPoint) -> None:
        """
        Open the hosted device editor for a right-clicked property cell.

        :param position: Table-local click position.
        :return: None.
        """
        index: QtCore.QModelIndex = self.object_editor_table.indexAt(position)

        if index.isValid():
            model: QtCore.QAbstractItemModel | None = self.object_editor_table.model()

            if isinstance(model, ObjectsModel):
                hosted_device: EditableDevice | None = model.get_hosted_device_at_index(index=index)

                if hosted_device is not None:
                    self.open_hosted_device_editor(hosted_device=hosted_device)
                else:
                    pass
            else:
                pass
        else:
            pass

    def set_editor_model(self, api_object: ALL_DEV_TYPES):
        """
        Set an api object to appear in the editable table view of the editor
        :param api_object: any EditableDevice
        """
        template_elm, dictionary_of_lists = self.circuit.get_dictionary_of_lists(api_object.device_type)

        filter_prop = self.filter_combo.currentData()
        self.api_object = api_object

        mdl = ObjectsModel(
            objects=[api_object],
            property_list=list(api_object.property_list),
            time_index=self.get_time_index(),
            parent=self.object_editor_table,
            editable=True,
            transposed=True,
            dictionary_of_lists=dictionary_of_lists,
            properties_filter=filter_prop,
            error_msg_ptr=self.gui.show_error_toast
        )

        self.object_editor_table.setModel(mdl)

    def set_results_to_plot(self, all_threads: List[DRIVER_OBJECTS]):
        """

        :param all_threads:
        :return:
        """
        self.results_dictionary = {thr.tpe: thr for thr in all_threads if thr is not None}

    def plot_device(self, api_object: EditableDevice) -> None:
        """Open device profiles and unit-compatible time-series result charts.

        :param api_object: Device represented by the selected injection graphic.
        :return: None.
        """
        time_values: np.ndarray = np.asarray(self.circuit.time_profile).copy()
        dialog_title: str = self.tr("{device_name} plot").format(device_name=api_object.name)
        plot_dialogue: PlotDialogue = PlotDialogue(title=dialog_title, parent=self.gui)
        plotted_units: list[str] = list()
        plotted_charts: list[GraphsWidget] = list()
        has_profiles: bool = self._add_device_profile_tabs(
            plot_dialogue=plot_dialogue,
            api_object=api_object,
            time_values=time_values,
            plotted_units=plotted_units,
            plotted_charts=plotted_charts,
        )
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
            plot_dialogue.open_from_context_menu()
        else:
            plot_dialogue.reject()
            info_msg(self.tr("This device has no numeric profiles or time-series results to plot."), dialog_title)

    def _add_device_profile_tabs(self,
                                 plot_dialogue: PlotDialogue,
                                 api_object: EditableDevice,
                                 time_values: np.ndarray,
                                 plotted_units: list[str],
                                 plotted_charts: list[GraphsWidget]) -> bool:
        """Register device profiles grouped by measurement unit.

        :param plot_dialogue: Dialog retaining every created chart widget.
        :param api_object: Device supplying persisted profile buffers.
        :param time_values: Copied grid time coordinates.
        :param plotted_units: Unit keys for charts already added to this dialog.
        :param plotted_charts: Retained compatibility list; catalog plots do not create unit tabs.
        :return: Whether one or more profile series were registered.
        """
        profile_units: list[str] = list()
        profile_names: list[list[str]] = list()
        profile_values: list[list[np.ndarray]] = list()
        if time_values.size > 0:
            property_data: object
            for property_data in api_object.registered_properties.values():
                if property_data.has_profile():
                    profile = api_object.get_profile_by_prop(prop=property_data)
                    if profile is not None:
                        raw_values: np.ndarray = np.asarray(profile.toarray()).copy()
                        values_are_numeric: bool = (
                            np.issubdtype(raw_values.dtype, np.number)
                            or np.issubdtype(raw_values.dtype, np.bool_)
                        )
                        if values_are_numeric and raw_values.size == time_values.size:
                            unit: str = str(property_data.units).strip().strip("()")
                            values: np.ndarray = np.asarray(raw_values, dtype=float)
                            has_finite_values: bool = bool(np.any(np.isfinite(values)))
                            if has_finite_values and unit in profile_units:
                                unit_index: int = profile_units.index(unit)
                            elif has_finite_values:
                                profile_units.append(unit)
                                profile_names.append(list())
                                profile_values.append(list())
                                unit_index = len(profile_units) - 1
                            else:
                                unit_index = -1
                            if unit_index >= 0:
                                profile_names[unit_index].append(str(property_data.name))
                                profile_values[unit_index].append(values)
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass
                else:
                    pass
        else:
            pass

        has_profiles: bool = False
        unit_index: int
        for unit_index in range(len(profile_units)):
            plot_dialogue.register_time_series(
                group=self.tr("Profile Inputs"),
                unit=profile_units[unit_index],
                x_values=time_values,
                series_names=profile_names[unit_index],
                series_values=profile_values[unit_index],
            )
            if profile_units[unit_index] not in plotted_units:
                plotted_units.append(profile_units[unit_index])
            else:
                pass
            has_profiles = True
        return has_profiles

    def _add_device_result_tabs(self,
                                plot_dialogue: PlotDialogue,
                                api_object: EditableDevice,
                                plotted_units: list[str],
                                plotted_charts: list[GraphsWidget]) -> bool:
        """Register available device results in the dialog-wide series tree.

        :param plot_dialogue: Dialog retaining every created chart widget.
        :param api_object: Device used to resolve each result-table column.
        :param plotted_units: Unit keys for charts already added to this dialog.
        :param plotted_charts: Retained compatibility list; catalog plots do not create unit tabs.
        :return: Whether at least one finite result series was registered.
        """
        has_results: bool = False
        driver: object
        results: object
        for driver, results in self.gui.session.drivers_results_iter():
            if isinstance(results, ResultsTemplate):
                result_type: ResultTypes
                for result_type in results.get_results_type_dict().values():
                    table: ResultsTable = results.mdl(result_type=result_type)
                    if (isinstance(table, ResultsTable) and table.idx_device_type == DeviceType.TimeDevice
                                and table.cols_device_type != DeviceType.NoDevice):
                        device_list: list[EditableDevice] = self.circuit.get_elements_by_type(
                            device_type=table.cols_device_type,
                        )
                        if api_object in device_list:
                            device_index: int = device_list.index(api_object)
                            finite_data: tuple[np.ndarray, list[str], list[np.ndarray]] | None = get_result_table_series(
                                table=table,
                                selected_col_idx=np.array((device_index,), dtype=np.int64),
                            )
                            has_finite_values: bool = (
                                finite_data is not None
                                and bool(np.any(np.isfinite(finite_data[2][0])))
                            )
                            if has_finite_values:
                                unit: str = str(table.units).strip().strip("()")
                                if unit == "":
                                    unit = str(table.y_label).strip().strip("()")
                                else:
                                    pass
                                if unit not in plotted_units:
                                    plotted_units.append(unit)
                                else:
                                    pass
                                result_group: str
                                if "optimal" in results.name.casefold():
                                    result_group = self.tr("OPF Time Series")
                                elif "power flow" in results.name.casefold():
                                    result_group = self.tr("Power Flow Time Series")
                                else:
                                    result_group = "{} Time Series".format(results.name)
                                x_values: np.ndarray = finite_data[0]
                                y_values: list[np.ndarray] = finite_data[2]
                                plot_dialogue.register_time_series(
                                    group=result_group,
                                    unit=unit,
                                    x_values=x_values,
                                    series_names=["{}: {}".format(results.name, result_type.value)],
                                    series_values=[y_values[0]],
                                )
                                has_results = True
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass
            else:
                pass
        return has_results

    def plot_branch(self, i: int, api_object: Union[Line, DcLine, Transformer2W, VSC, UPFC]) -> None:
        """Open profile and all time-series result plots for one branch.

        :param i: Legacy result-column index retained for graphic callbacks.
        :param api_object: Branch represented by the selected graphic.
        :return: None.
        """
        _ = i
        self.plot_device(api_object=api_object)

    def plot_hvdc_branch(self, i: int, api_object: HvdcLine) -> None:
        """Open profile and all time-series result plots for one HVDC branch.

        :param i: Legacy result-column index retained for graphic callbacks.
        :param api_object: HVDC branch represented by the selected graphic.
        :return: None.
        """
        _ = i
        self.plot_device(api_object=api_object)

    @staticmethod
    def set_rate_to_profile(api_object: ALL_DEV_TYPES):
        """

        :param api_object:
        """
        if api_object is not None:
            if api_object.rate_prof.size():
                quit_msg = (f"{api_object.name}\nAre you sure that you want to overwrite the "
                            f"rates profile with the snapshot value?")

                ok = yes_no_question(
                    text=quit_msg,
                    title=QtCore.QCoreApplication.translate("BaseDiagramWidget", "Overwrite the profile"),
                )

                if ok:
                    api_object.rate_prof.fill(api_object.rate)

    @staticmethod
    def set_active_status_to_profile(api_object: ALL_DEV_TYPES, override_question=False):
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

                    ok = yes_no_question(
                        text=quit_msg,
                        title=QtCore.QCoreApplication.translate("BaseDiagramWidget", "Overwrite the active profile"),
                    )
                else:
                    ok = True

                if ok:
                    if api_object.active:
                        api_object.active_prof.fill(True)
                    else:
                        api_object.active_prof.fill(False)

    def draw(self) -> None:
        """
        Draw the stored diagram
        """
        self.draw_diagram(diagram=self.diagram)

    def draw_diagram(self, diagram: Union[SchematicDiagram, MapDiagram]) -> None:
        """
        Draw the diagram
        :param diagram: Map or schematic diagram
        """
        pass

    def clear(self) -> None:
        """
        Clear the schematic
        """
        self.graphics_manager.clear()

    def prepare_to_delete(self) -> None:
        """
        Release widget-owned state before the Qt widget itself is destroyed.
        """
        self.clear()
        self.remove_video_time_label()
        self.object_editor_table.setModel(None)
        self.api_object = None
        self.results_dictionary.clear()

        if self._video is not None:
            self._video.release()
            self._video = None

    def set_data(self, diagram: SchematicDiagram):
        """
        Set the diagram layout and redraw.
        The circuit is always taken from self.gui.circuit (the active scenario).
        :param diagram: SchematicDiagram
        """
        self.clear()
        self.diagram = diagram
        self.draw()

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

        :param Sbus:
        :param bus_active:
        :param Sf:
        :param St:
        :param voltages:
        :param loadings:
        :param types:
        :param losses:
        :param br_active:
        :param hvdc_Pf:
        :param hvdc_Pt:
        :param hvdc_losses:
        :param hvdc_loading:
        :param hvdc_active:
        :param loading_label:
        :param vsc_Pf:
        :param vsc_Pt:
        :param vsc_Qt:
        :param vsc_losses:
        :param vsc_loading:
        :param vsc_active:
        :param ma:
        :param tau:
        :param gen_p:
        :param gen_q:
        :param gen_names:
        :param battery_p:
        :param battery_q:
        :param battery_names:
        :param shunt_q:
        :param shunt_names:
        :param fluid_node_p2x_flow:
        :param fluid_node_current_level:
        :param fluid_node_spillage:
        :param fluid_node_flow_in:
        :param fluid_node_flow_out:
        :param fluid_path_flow:
        :param fluid_injection_flow:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :param cmap:
        :param is_three_phase: the results are three-phase
        :return:
        """
        pass

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
                           ma: Vec,
                           tau: Vec,
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
                           t_idx: int | None = None):
        pass

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

    def get_picture_width(self) -> int:
        """
        Width
        :return: width in pixels
        """
        return 0

    def get_picture_height(self) -> int:
        """
        Height
        :return: height in pixels
        """
        return 0

    def get_image(self, transparent: bool = False) -> QImage:
        """
        get the current picture
        :param transparent: Set a transparent background
        :return: QImage, width, height
        """
        pass

    def take_picture(self, filename: str):
        """
        Save the grid to a png file
        :param filename: Picture file name
        """
        pass

    def start_video_recording(self, fname: str, fps: int = 30, logger: Logger | None = None) -> Tuple[int, int]:
        """
        Save video
        :param fname: file name
        :param fps: frames per second
        :param logger: LOgger
        :returns width, height
        """
        if logger is None:
            logger = Logger()

        self._create_video_time_label()

        image = self.get_image()
        w = image.width()
        h = image.height()

        if fname.endswith('.mp4'):
            self._video = cv2.VideoWriter(filename=fname,
                                          fourcc=cv2.VideoWriter_fourcc(*'mp4v'),
                                          fps=fps,
                                          frameSize=(w, h))
        elif fname.endswith('.avi'):
            self._video = cv2.VideoWriter(filename=fname + '.avi',
                                          fourcc=cv2.VideoWriter_fourcc(*'XVID'),
                                          fps=fps,
                                          frameSize=(w, h))
        else:
            raise Exception(f"File format not recognized {fname}")

        return w, h

    def capture_video_frame(self, w: int, h: int, logger: Logger):
        """
        Save video frame
        """
        image = self.get_image()
        w2 = image.width()
        h2 = image.height()

        if w != w2:
            logger.add_error(f"Width {w2} different from expected width {w}")

        if h != h2:
            logger.add_error(f"Height {h2} different from expected width {h}")

        cv2_image = qimage_to_cv(image, logger)

        if cv2_image is not None:
            self._video.write(cv2_image)
        else:
            pass

    def capture_video_frame_timed(self, w: int, h: int, logger: Logger) -> Tuple[float, float]:
        """
        Save a video frame and report the capture and encoder durations separately.

        :param w: Expected frame width
        :param h: Expected frame height
        :param logger: Logger instance
        :return: Tuple ``(capture_time_s, write_time_s)``
        """
        capture_start_time: float = perf_counter()
        image = self.get_image()
        w2: int = image.width()
        h2: int = image.height()

        if w != w2:
            logger.add_error(f"Width {w2} different from expected width {w}")
        else:
            pass

        if h != h2:
            logger.add_error(f"Height {h2} different from expected width {h}")
        else:
            pass

        cv2_image: np.ndarray | None = qimage_to_cv(image, logger)
        capture_end_time: float = perf_counter()

        write_start_time: float = capture_end_time
        if cv2_image is not None:
            self._video.write(cv2_image)
        else:
            pass
        write_end_time: float = perf_counter()

        capture_elapsed_time: float = capture_end_time - capture_start_time
        write_elapsed_time: float = write_end_time - write_start_time
        return capture_elapsed_time, write_elapsed_time

    def end_video_recording(self):
        """
        Finalize video recording
        """
        self._video.release()
        print("Video released")

    def update_label_drwaing_status(self, device: ALL_DEV_TYPES, draw_labels: bool) -> None:
        """
        Update the label drawing flag
        :param device: Any database device
        :param draw_labels: Draw labels?
        """
        location = self.diagram.query_point(device=device)

        if location is not None:
            location.draw_labels = draw_labels

    def set_size_constraints(self,
                             use_flow_based_width: bool = False,
                             min_branch_width: int = 5,
                             max_branch_width=5,
                             min_bus_width=20,
                             max_bus_width=20,
                             arrow_size=20):
        """
        Set the size constraints
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :param arrow_size:
        """
        self.diagram.set_size_constraints(
            use_flow_based_width=use_flow_based_width,
            min_branch_width=min_branch_width,
            max_branch_width=max_branch_width,
            min_bus_width=min_bus_width,
            max_bus_width=max_bus_width,
            arrow_size=arrow_size
        )

    def copy(self):
        """

        :return:
        """
        raise Exception('Copy method not implemented!')

    def consolidate_coordinates(self):
        """

        :return:
        """
        raise Exception('Consolidate method method not implemented!')
