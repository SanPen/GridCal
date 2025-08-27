# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import List, Set, Dict, Union, Tuple, Generator, TYPE_CHECKING
import numpy as np
import cv2
from matplotlib import pyplot as plt

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QListView, QTableView, QVBoxLayout, QHBoxLayout, QFrame, QSplitter, QAbstractItemView,
                               QGraphicsItem)

from VeraGrid.Gui.Diagrams.generic_graphics import GenericDiagramWidget
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.hvdc_line import HvdcLine
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Branches.upfc import UPFC
from VeraGridEngine.Simulations import (PowerFlowTimeSeriesResults, LinearAnalysisTimeSeriesResults,
                                        ContingencyAnalysisTimeSeriesResults, OptimalPowerFlowTimeSeriesResults,
                                        StochasticPowerFlowResults)
from VeraGridEngine.basic_structures import Vec, CxVec, IntVec
from VeraGridEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from VeraGridEngine.Devices.Diagrams.map_diagram import MapDiagram
from VeraGridEngine.Simulations.types import DRIVER_OBJECTS
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import SimulationTypes, ResultTypes
import VeraGridEngine.Devices.Diagrams.palettes as palettes

from VeraGrid.Gui.Diagrams.graphics_manager import GraphicsManager, ALL_GRAPHICS
from VeraGrid.Gui.general_dialogues import DeleteDialogue
from VeraGrid.Gui.messages import yes_no_question, info_msg
from VeraGrid.Gui.object_model import ObjectsModel

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
            # convert picture using the memory
            # we need to delete the alpha channel, otherwise the video frame is not saved
            cv_mat = np.array(qimage.constBits()).reshape(height, width, 4).astype(np.uint8)[:, :, :3]

            return cv_mat

        except ValueError as e:

            logger.add_error(msg=f"Could not convert frame: {e}, failed over to second image conversion method.")

            try:
                # Convert the QImage to RGB format if it is not already in that format
                qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)

                # Get the pointer to the data and stride (bytes per line)
                ptr = qimage.bits()
                # ptr.itemsize = qimage.sizeInBytes()  # Set the size of the memoryview
                stride = qimage.bytesPerLine()  # Get the number of bytes per line (width * channels + padding)

                # Create a numpy array with the correct shape based on the stride
                arr = np.array(ptr).reshape((height, stride // 3, 3)).astype(np.uint8)  # Adjust for stride

                # Crop the width to the actual image width (in case stride > width * channels)
                arr = arr[:, :width, :]

                # Convert RGB to BGR for OpenCV
                cv_mat = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

                return cv_mat
            except ValueError as e2:
                logger.add_error(msg=f"Could not convert frame: {e2}, failed over to disk converison method")

                # try the last method, saving to disk and reading again

                opencv_image = qimage_tocv2_by_disk(qimage, logger, file_path="__img__.png")

                return opencv_image


class BaseDiagramWidget(QSplitter):
    """
    Common diagram widget to host common functions
    for the schematic and the map
    """

    def __init__(self,
                 gui: VeraGridMainGUI | DiagramsMain,
                 circuit: MultiCircuit,
                 diagram: Union[SchematicDiagram, MapDiagram],
                 library_model: Union[MapLibraryModel, SchematicLibraryModel],
                 time_index: Union[None, int] = None):
        """
        Constructor
        :param circuit:
        :param diagram:
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
        change_font_size(self.object_editor_table, 9)
        change_font_size(self.object_editor_table.verticalHeader(), 9)
        change_font_size(self.object_editor_table.horizontalHeader(), 9)

        # Actual libraryView object
        self.library_view = QListView(self)
        self.library_view.setViewMode(self.library_view.ViewMode.ListMode)
        self.library_view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        change_font_size(self.library_view, 9)

        # library model
        self.library_model = library_model
        self.library_view.setModel(self.library_model)

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
        splitter2.setOrientation(Qt.Orientation.Vertical)
        self.addWidget(splitter2)
        # self.addWidget(self.editor_graphics_view)

        # factor 1:10
        splitter2.setStretchFactor(0, 2)
        splitter2.setStretchFactor(1, 5)

        # self.setStretchFactor(0, 0)
        # self.setStretchFactor(1, 2000)
        # --------------------------------------------------------------------------------------------------------------

        # store a reference to the multi circuit instance
        self.circuit: MultiCircuit = circuit

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

    def items(self) -> Generator[ALL_GRAPHICS, None, None]:
        """
        Iterable through all graphics registered in the graphics manager
        :return: ALL_GRAPHICS one by one
        """
        for device_tpe, graphics_dict in self.graphics_manager.graphic_dict.items():
            for idtag, graphical_obj in graphics_dict.items():
                yield graphical_obj

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

    def _get_selected(self) -> List[GenericDiagramWidget]:
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
                       graphic_object: GenericDiagramWidget | None = None,
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

    def delete_element_utility_function(self, device: ALL_DEV_TYPES, propagate: bool = True):
        """
        This function is a utility function to call this function in other diagrams through the GUI
        :param device: ALL_DEV_TYPES
        :param propagate: propagate
        :return:
        """
        self.diagram.delete_device(device=device)
        graphic_object: QGraphicsItem = self.graphics_manager.delete_device(device=device)

        if graphic_object is not None:
            self._remove_from_scene(graphic_object)

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

            # get the set of all affected GenericDiagramWidget instances
            extended: Set[ALL_DEV_TYPES] = set()

            for graphic_obj in selected:

                if graphic_obj is not None:
                    if isinstance(graphic_obj, GenericDiagramWidget):
                        extended.add(graphic_obj.api_object)

                    for child_item in graphic_obj.get_associated_devices():
                        if child_item is not None:
                            extended.add(child_item)

            extended_lst: List[ALL_DEV_TYPES] = list(extended)

            dlg = DeleteDialogue(
                names_list=[f"{device.device_type.value}: "
                              f"{device.name}"
                            for device in extended_lst],
                delete_from_db=delete_from_db,
                title="Delete Selected",
                checks=False,
            )

            dlg.setModal(True)
            dlg.exec()

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

    def delete_selected_from_widget(self, delete_from_db: bool) -> None:
        """
        Delete the selected items from the diagram
        :param delete_from_db:
        """
        self.delete_with_dialogue(selected=self._get_selected(),
                                  delete_from_db=delete_from_db)

    def delete_diagram_elements(self, elements: List[ALL_DEV_TYPES]):
        """
        Delete device from the diagram registry
        :param elements: list of elements to delete
        """
        for elm in elements:
            self.delete_element_utility_function(elm)

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

    def set_editor_model(self, api_object: ALL_DEV_TYPES):
        """
        Set an api object to appear in the editable table view of the editor
        :param api_object: any EditableDevice
        """
        template_elm, dictionary_of_lists = self.circuit.get_dictionary_of_lists(api_object.device_type)
        mdl = ObjectsModel(objects=[api_object],
                           property_list=api_object.property_list,
                           time_index=self.get_time_index(),
                           parent=self.object_editor_table,
                           editable=True,
                           transposed=True,
                           dictionary_of_lists=dictionary_of_lists)

        self.object_editor_table.setModel(mdl)

    def set_results_to_plot(self, all_threads: List[DRIVER_OBJECTS]):
        """

        :param all_threads:
        :return:
        """
        self.results_dictionary = {thr.tpe: thr for thr in all_threads if thr is not None}

    def plot_branch(self, i: int, api_object: Union[Line, DcLine, Transformer2W, VSC, UPFC]):
        """
        Plot branch results
        :param i: branch index (not counting HVDC lines because those are not real Branches)
        :param api_object: API object
        """
        fig = plt.figure(figsize=(12, 8))
        fig.suptitle(api_object.name, fontsize=20)

        ax_1 = fig.add_subplot(211)
        ax_1.set_title('Probability x < value', fontsize=14)
        ax_1.set_ylabel('Loading [%]', fontsize=11)

        ax_2 = fig.add_subplot(212)
        ax_2.set_title('Power', fontsize=14)
        ax_2.set_ylabel('Power [MW]', fontsize=11)

        any_plot = False

        for driver, results in self.gui.session.drivers_results_iter():

            if results is not None:

                if isinstance(results, PowerFlowTimeSeriesResults):

                    Sf_table = results.mdl(result_type=ResultTypes.BranchActivePowerFrom)
                    Sf_table.plot_device(ax=ax_1, device_idx=i, title="Power flow")

                    loading_table = results.mdl(result_type=ResultTypes.BranchLoading)
                    loading_table.convert_to_cdf()
                    loading_table.plot_device(ax=ax_2, device_idx=i, title="Power loading")
                    any_plot = True

                elif isinstance(results, LinearAnalysisTimeSeriesResults):

                    Sf_table = results.mdl(result_type=ResultTypes.BranchActivePowerFrom)
                    Sf_table.plot_device(ax=ax_1, device_idx=i, title="Linear flow")

                    loading_table = results.mdl(result_type=ResultTypes.BranchLoading)
                    loading_table.convert_to_cdf()
                    loading_table.plot_device(ax=ax_2, device_idx=i, title="Linear loading")
                    any_plot = True

                elif isinstance(results, ContingencyAnalysisTimeSeriesResults):

                    Sf_table = results.mdl(result_type=ResultTypes.MaxContingencyFlows)
                    Sf_table.plot_device(ax=ax_1, device_idx=i, title="Contingency flow")

                    loading_table = results.mdl(result_type=ResultTypes.MaxContingencyLoading)
                    loading_table.convert_to_cdf()
                    loading_table.plot_device(ax=ax_2, device_idx=i, title="Contingency loading")
                    any_plot = True

                elif isinstance(results, OptimalPowerFlowTimeSeriesResults):

                    Sf_table = results.mdl(result_type=ResultTypes.BranchActivePowerFrom)
                    Sf_table.plot_device(ax=ax_1, device_idx=i, title="Optimal power flow")

                    loading_table = results.mdl(result_type=ResultTypes.BranchLoading)
                    loading_table.convert_to_cdf()
                    loading_table.plot_device(ax=ax_2, device_idx=i, title="Optimal loading")
                    any_plot = True

                elif isinstance(results, StochasticPowerFlowResults):
                    loading_table = results.mdl(result_type=ResultTypes.BranchLoadingAverage)
                    loading_table.convert_to_cdf()
                    loading_table.plot_device(ax=ax_2, device_idx=i, title="Stochastic loading")
                    any_plot = True

        if any_plot:
            plt.legend()
            plt.show()
        else:
            info_msg("No time series results to plot, run some time series results. Even partial results are fine",
                     f"{api_object.name} results plot")

    def plot_hvdc_branch(self, i: int, api_object: HvdcLine):
        """
        HVDC branch
        :param i: index of the object
        :param api_object: HvdcGraphicItem
        """
        fig = plt.figure(figsize=(12, 8))
        fig.suptitle(api_object.name, fontsize=20)

        ax_1 = fig.add_subplot(211)
        ax_1.set_title('Probability x < value', fontsize=14)
        ax_1.set_ylabel('Loading [%]', fontsize=11)

        ax_2 = fig.add_subplot(212)
        ax_2.set_title('Power', fontsize=14)
        ax_2.set_ylabel('Power [MW]', fontsize=11)

        any_plot = False

        for driver, results in self.gui.session.drivers_results_iter():

            if results is not None:

                if isinstance(results, PowerFlowTimeSeriesResults):

                    Sf_table = results.mdl(result_type=ResultTypes.HvdcPowerFrom)
                    Sf_table.plot(ax=ax_1, selected_col_idx=[i])

                    loading_table = results.mdl(result_type=ResultTypes.HvdcLoading)
                    loading_table.convert_to_cdf()
                    loading_table.plot(ax=ax_2, selected_col_idx=[i])
                    any_plot = True

                elif isinstance(results, OptimalPowerFlowTimeSeriesResults):

                    Sf_table = results.mdl(result_type=ResultTypes.HvdcPowerFrom)
                    Sf_table.plot(ax=ax_1, selected_col_idx=[i])

                    loading_table = results.mdl(result_type=ResultTypes.HvdcLoading)
                    loading_table.convert_to_cdf()
                    loading_table.plot(ax=ax_2, selected_col_idx=[i])
                    any_plot = True

        if any_plot:
            plt.legend()
            plt.show()
        else:
            info_msg("No time series results to plot, run some time series results. Even partial results are fine",
                     f"{api_object.name} results plot")

    @staticmethod
    def set_rate_to_profile(api_object: ALL_DEV_TYPES):
        """

        :param api_object:
        """
        if api_object is not None:
            if api_object.rate_prof.size():
                quit_msg = (f"{api_object.name}\nAre you sure that you want to overwrite the "
                            f"rates profile with the snapshot value?")

                ok = yes_no_question(text=quit_msg, title='Overwrite the profile')

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

                    ok = yes_no_question(text=quit_msg, title='Overwrite the active profile')
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

    def set_data(self, circuit: MultiCircuit, diagram: SchematicDiagram):
        """
        Set the widget data and redraw
        :param circuit: MultiCircuit
        :param diagram: SchematicDiagram
        """
        self.clear()
        self.circuit = circuit
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
                           cmap: palettes.Colormaps = None):
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

    def start_video_recording(self, fname: str, fps: int = 30, logger: Logger = Logger()) -> Tuple[int, int]:
        """
        Save video
        :param fname: file name
        :param fps: frames per second
        :param logger: LOgger
        :returns width, height
        """

        image = self.get_image()
        w = image.width()
        h = image.height()
        cv2_image = qimage_to_cv(image, logger)
        w2, h2, _ = cv2_image.shape

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
