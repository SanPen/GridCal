# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import List, Dict, Union, Tuple, Callable, TYPE_CHECKING
import numpy as np
import cv2
from matplotlib import pyplot as plt

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QListView, QTableView, QVBoxLayout, QHBoxLayout, QFrame, QSplitter, QAbstractItemView

from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.Branches.vsc import VSC
from GridCalEngine.Devices.Branches.upfc import UPFC
from GridCalEngine.Simulations import (PowerFlowTimeSeriesResults, LinearAnalysisTimeSeriesResults,
                                       ContingencyAnalysisTimeSeriesResults, OptimalPowerFlowTimeSeriesResults,
                                       StochasticPowerFlowResults)
from GridCalEngine.basic_structures import Vec, CxVec, IntVec
from GridCalEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from GridCalEngine.Devices.Diagrams.map_diagram import MapDiagram
from GridCalEngine.Simulations.types import DRIVER_OBJECTS
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import SimulationTypes, ResultTypes
import GridCalEngine.Devices.Diagrams.palettes as palettes

from GridCal.Gui.Diagrams.graphics_manager import GraphicsManager
from GridCal.Gui.messages import yes_no_question, info_msg
from GridCal.Gui.object_model import ObjectsModel

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import MapLibraryModel, GridMapWidget
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicLibraryModel, SchematicWidget
    from GridCal.Gui.Main.SubClasses.Model.diagrams import DiagramsMain


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
    :param force_disk: if true, the image is converted by saving to disk and loading again with opencv
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
            # we need to remove the alpha channel, otherwise the video frame is not saved
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
                 gui: DiagramsMain,
                 circuit: MultiCircuit,
                 diagram: Union[SchematicDiagram, MapDiagram],
                 library_model: Union[MapLibraryModel, SchematicLibraryModel],
                 time_index: Union[None, int] = None,
                 call_delete_db_element_func: Callable[
                     [Union[GridMapWidget, SchematicWidget], ALL_DEV_TYPES], None] = None):
        """
        Constructor
        :param circuit:
        :param diagram:
        :param time_index:
        :param call_delete_db_element_func:
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

        # This function is meant to be a master delete function that is passed to each diagram
        # so that when a diagram deletes an element, the element is deleted in all other diagrams
        self.call_delete_db_element_func = call_delete_db_element_func

        self.results_dictionary: Dict[SimulationTypes, DRIVER_OBJECTS] = dict()

        # video pointer
        self._video: Union[None, cv2.VideoWriter] = None


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
        :param theta:
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
        :return:
        """
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
