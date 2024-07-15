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
from __future__ import annotations
from typing import List, Dict, Union, Tuple, Callable, TYPE_CHECKING
import numpy as np
import pandas as pd
import cv2
from matplotlib import pyplot as plt

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QListView, QTableView, QVBoxLayout, QHBoxLayout, QFrame, QSplitter, QAbstractItemView

from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Substation import Bus
from GridCalEngine.Devices.Branches.line import Line
from GridCalEngine.Devices.Branches.dc_line import DcLine
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.Devices.Branches.transformer import Transformer2W
from GridCalEngine.Devices.Branches.vsc import VSC
from GridCalEngine.Devices.Branches.upfc import UPFC
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.basic_structures import Vec, CxVec, IntVec
from GridCalEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from GridCalEngine.Devices.Diagrams.map_diagram import MapDiagram
from GridCalEngine.Simulations.types import DRIVER_OBJECTS
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import DeviceType, SimulationTypes

from GridCal.Gui.Diagrams.graphics_manager import GraphicsManager
import GridCalEngine.Devices.Diagrams.palettes as palettes
from GridCal.Gui.messages import yes_no_question
from GridCal.Gui.object_model import ObjectsModel

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import MapLibraryModel, GridMapWidget
    from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicLibraryModel, SchematicWidget


class BaseDiagramWidget(QSplitter):
    """
    Common diagram widget to host common functions
    for the schematic and the map
    """

    def __init__(self,
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

        # --------------------------------------------------------------------------------------------------------------
        # Widget creation
        # --------------------------------------------------------------------------------------------------------------
        # Widget layout and child widgets:
        self.horizontal_layout = QHBoxLayout(self)
        self.object_editor_table = QTableView(self)

        # Actual libraryView object
        self.library_view = QListView(self)

        self.library_view.setViewMode(self.library_view.ViewMode.ListMode)
        self.library_view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

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
        splitter2.setOrientation(Qt.Vertical)
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

    def set_editor_model(self,
                         api_object: ALL_DEV_TYPES,
                         dictionary_of_lists: Union[None, Dict[DeviceType, List[ALL_DEV_TYPES]]] = None):
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
                            if key == SimulationTypes.PowerFlowTimeSeries_run:
                                power_data[key.value] = driver.results.Sf.real[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.loading.real[:, i] * 100.0))

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

                for key, driver in self.results_dictionary.items():
                    if hasattr(driver, 'results'):
                        if driver.results is not None:
                            if key == SimulationTypes.PowerFlowTimeSeries_run:
                                power_data[key.value] = driver.results.hvdc_Pf[:, i]
                                loading_data[key.value] = np.sort(np.abs(driver.results.hvdc_loading[:, i] * 100.0))

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

                # power
                if len(power_data.keys()):
                    df = pd.DataFrame(data=power_data, index=x)
                    ax_2.set_title('Power', fontsize=14)
                    ax_2.set_ylabel('Power [MW]', fontsize=11)
                    df.plot(ax=ax_2)
                    ax_2.plot(x, api_object.rate_prof.toarray(), c='gray', linestyle='dashed', linewidth=1)
                    ax_2.plot(x, -api_object.rate_prof.toarray(), c='gray', linestyle='dashed', linewidth=1)

                plt.legend()
                fig.suptitle(api_object.name, fontsize=20)

                # plot the profiles
                plt.show()

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

        :param buses:
        :param branches:
        :param hvdc_lines:
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
        :param ma:
        :param theta:
        :param Beq:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :param cmap:
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

    def get_image(self, transparent: bool = False) -> Tuple[QImage, int, int]:
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

    def start_video_recording(self, fname: str, fps: int = 30) -> Tuple[int, int]:
        """
        Save video
        :param fname: file name
        :param fps: frames per second
        :returns width, height
        """

        w = self.get_picture_width()
        h = self.get_picture_height()

        self._video = cv2.VideoWriter(filename=fname,
                                      fourcc=cv2.VideoWriter_fourcc(*'mp4v'),
                                      fps=fps,
                                      frameSize=(w, h))

        return w, h

    def capture_video_frame(self):
        """
        Save video frame
        """

        image, w, h = self.get_image()

        # convert picture using the memory
        # we need to remove the alpha channel, otherwise the video frame is not saved
        frame = np.array(image.constBits()).reshape(h, w, 4).astype(np.uint8)[:, :, :3]
        self._video.write(frame)

    def end_video_recording(self):
        """
        Finalize video recording
        """
        self._video.release()

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
                             max_bus_width=20):
        """
        Set the size constraints
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        """
        self.diagram.set_size_constraints(
            use_flow_based_width=use_flow_based_width,
            min_branch_width=min_branch_width,
            max_branch_width=max_branch_width,
            min_bus_width=min_bus_width,
            max_bus_width=max_bus_width
        )
