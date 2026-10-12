# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
from time import perf_counter
from typing import List, Tuple, Union, Callable, Iterable, Any

import networkx as nx
import numpy as np
import shiboken6
from PySide6 import QtGui, QtWidgets, QtCore

import VeraGridEngine.Devices.Diagrams.palettes as palettes
from VeraGridEngine import ContingencyOperationTypes, MapDiagram
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.IO.file_system import tiles_path
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Simulations import PowerFlowResults, ContinuationPowerFlowResults, PowerFlowTimeSeriesResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_ts_results_3ph import PowerFlowTimeSeriesResults3Ph
from VeraGridEngine.Simulations.StateEstimation.state_estimation_results import StateEstimationResults
from VeraGridEngine.Utils.progress_bar import print_progress_bar
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (SimulationTypes, Colormaps, DeviceType,
                                         MethodShortCircuit, SchematicAutoRouteStyle, DynamicSimulationMode)
from VeraGridEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram

import VeraGridEngine.Devices as dev
import VeraGridEngine.Simulations as sim
import VeraGrid.Gui.gui_functions as gf
import VeraGrid.Gui.Visualization.visualization as viz
from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import (SchematicWidget,
                                                                    BusGraphicItem,
                                                                    generate_schematic_diagram,
                                                                    make_vicinity_diagram,
                                                                    make_diagram_from_buses)
from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget, generate_map_diagram
from VeraGrid.Gui.Diagrams.base_diagram_widget import BaseDiagramWidget
from VeraGrid.Gui.Diagrams.SchematicWidget.diagram_bus_selection_dialogue import DiagramBusSelectorDialogue
from VeraGrid.Gui.Diagrams.diagrams_model import DiagramsTreeModel
from VeraGrid.Gui.messages import yes_no_question, error_msg, info_msg
from VeraGrid.Gui.Main.SubClasses.Model.compiled_arrays import CompiledArraysMain
from VeraGrid.Gui.Main.object_select_window import ObjectSelectWindow, ListSelectWindow
from VeraGrid.Gui.Diagrams.MapWidget.Tiles.TileProviders.cartodb import CartoDbTiles
from VeraGrid.Gui.object_proxy_model import ObjectModelFilterProxy
from VeraGrid.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
from VeraGrid.Gui.ShortCircuitEditor.short_circuit_selector import ShortCircuitSelector
from VeraGrid.Gui.general_dialogues import (CheckListDialogue, StartEndSelectionDialogue,
                                            InputNumberDialogue)
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely, exec_dialog_safely

ALL_EDITORS = Union[SchematicWidget, GridMapWidget, BaseDiagramWidget]
ALL_EDITORS_NONE = Union[None, SchematicWidget, GridMapWidget]
DIAGRAM_WIDGETS = Union[SchematicWidget, GridMapWidget]


class VideoExportWorker(QtCore.QThread):
    """
    VideoExportWorker
    """
    progress_signal = QtCore.Signal(float)
    progress_text = QtCore.Signal(str)
    done_signal = QtCore.Signal()

    def __init__(self, filename, diagram: ALL_EDITORS,
                 fps: int, start_idx: int, end_idx: int, current_study: SimulationTypes | str,
                 grid_colour_function: Callable[[ALL_EDITORS, SimulationTypes | str, int, bool], None], ):
        """

        :param filename:
        :param diagram:
        :param fps:
        :param start_idx:
        :param end_idx:
        :param current_study:
        :param grid_colour_function:
        """
        QtCore.QThread.__init__(self)

        self.filename = filename
        self.diagram = diagram
        self.fps: int = fps
        self.start_idx: int = start_idx
        self.end_idx: int = end_idx
        self.current_study: SimulationTypes | str = current_study
        self.grid_colour_function: Callable[
            [ALL_EDITORS, SimulationTypes | str, int, bool], None
        ] = grid_colour_function

        self.logger: Logger = Logger()

    def run(self):
        """
        Run function
        :return:
        """
        total_start_time: float = perf_counter()
        colour_elapsed_time: float = 0.0
        capture_elapsed_time: float = 0.0
        write_elapsed_time: float = 0.0
        frame_count: int = max(self.end_idx - self.start_idx, 0)

        # Mark export mode explicitly so the diagram can skip non-visual work.
        self.diagram.set_video_export_active(True)

        try:
            # Start the encoder only once before the frame loop begins.
            w, h = self.diagram.start_video_recording(fname=self.filename, fps=self.fps, logger=self.logger)

            # Recolour the diagram for each simulation step and then capture it.
            for t_idx in range(self.start_idx, self.end_idx):
                colour_start_time: float = perf_counter()
                self.grid_colour_function(
                    self.diagram,
                    self.current_study,
                    t_idx,
                    False
                )
                self.diagram.set_video_time_index(time_index=t_idx)
                colour_end_time: float = perf_counter()
                colour_elapsed_time += colour_end_time - colour_start_time

                frame_capture_elapsed_time: float
                frame_write_elapsed_time: float
                frame_capture_elapsed_time, frame_write_elapsed_time = self.diagram.capture_video_frame_timed(
                    w=w,
                    h=h,
                    logger=self.logger
                )
                capture_elapsed_time += frame_capture_elapsed_time
                write_elapsed_time += frame_write_elapsed_time

                self.progress_text.emit(f"Saving frame {t_idx} / {self.end_idx}")
                self.progress_signal.emit(t_idx / self.end_idx)

                print_progress_bar(t_idx + 1, self.end_idx)

            # Finalize the encoder after all frames have been flushed.
            self.diagram.end_video_recording()

            self.logger.add_info(f"Video saved to {self.filename}")
            total_end_time: float = perf_counter()
            total_elapsed_time: float = total_end_time - total_start_time
            other_elapsed_time: float = total_elapsed_time - colour_elapsed_time - capture_elapsed_time - write_elapsed_time

            self.logger.add_info(
                "Video export timing "
                f"frames={frame_count}, "
                f"total={total_elapsed_time * 1000.0:.1f} ms, "
                f"colour={colour_elapsed_time * 1000.0:.1f} ms, "
                f"capture={capture_elapsed_time * 1000.0:.1f} ms, "
                f"write={write_elapsed_time * 1000.0:.1f} ms, "
                f"other={other_elapsed_time * 1000.0:.1f} ms"
            )

            if frame_count > 0:
                self.logger.add_info(
                    "Video export timing per frame "
                    f"colour={colour_elapsed_time * 1000.0 / frame_count:.1f} ms, "
                    f"capture={capture_elapsed_time * 1000.0 / frame_count:.1f} ms, "
                    f"write={write_elapsed_time * 1000.0 / frame_count:.1f} ms"
                )
            else:
                pass

        finally:
            # Always restore the interactive colouring mode even after export failures.
            self.diagram.set_video_export_active(False)

        self.done_signal.emit()


class DiagramsMain(CompiledArraysMain):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        CompiledArraysMain.__init__(self, parent)

        # list of diagrams
        self.diagram_widgets_list: List[DIAGRAM_WIDGETS] = list()

        # flag to avoid circular updating of the display settings when changing diagrams
        self._enable_setting_auto_upgrade = True

        # Declare the map
        palettes_list = [palettes.Colormaps.VeraGrid,
                         palettes.Colormaps.Green2Red,
                         palettes.Colormaps.Heatmap,
                         palettes.Colormaps.TSO]
        self.cmap_index_dict = {pal: i for i, pal in enumerate(palettes_list)}
        self.ui.palette_comboBox.setModel(gf.ComboModel(enum_values=palettes_list))

        # map tile sources
        self.tile_sources: List[CartoDbTiles] = [
            CartoDbTiles(
                name='Carto voyager',
                tiles_dir=os.path.join(tiles_path(), 'carto_db_voyager'),
                tile_servers=["https://basemaps.cartocdn.com/rastertiles/voyager/"],
                start_workers=False
            ),
            CartoDbTiles(
                name='Carto positron',
                tiles_dir=os.path.join(tiles_path(), 'carto_db_positron'),
                tile_servers=['https://basemaps.cartocdn.com/light_all/'],
                start_workers=False
            ),
            CartoDbTiles(
                name='Carto dark matter',
                tiles_dir=os.path.join(tiles_path(), 'carto_db_dark_matter'),
                tile_servers=["https://basemaps.cartocdn.com/dark_all/"],
                start_workers=False
            ),
            CartoDbTiles(
                name='Open Street Map',
                tiles_dir=os.path.join(tiles_path(), 'osm'),
                tile_servers=["https://tile.openstreetmap.org"],
                max_zoom=21,
                start_workers=False
            ),
        ]
        self.tile_index_dict = {tile.tile_set_name: i for i, tile in enumerate(self.tile_sources)}
        self.tile_name_dict = {tile.tile_set_name: tile for tile in self.tile_sources}
        self.ui.tile_provider_comboBox.setModel(
            gf.ComboModel(text_items=[(tile.tile_set_name, tile) for tile in self.tile_sources])
        )
        self.ui.tile_provider_comboBox.setCurrentIndex(0)

        # Automatic layout modes
        self.layout_algorithms_dict = dict()
        self.layout_algorithms_dict['power_system_layout'] = nx.spring_layout
        self.layout_algorithms_dict['circular_layout'] = nx.circular_layout
        self.layout_algorithms_dict['random_layout'] = nx.random_layout
        self.layout_algorithms_dict['shell_layout'] = nx.shell_layout
        self.layout_algorithms_dict['spring_layout'] = nx.spring_layout
        self.layout_algorithms_dict['spectral_layout'] = nx.spectral_layout
        self.layout_algorithms_dict['fruchterman_reingold_layout'] = nx.fruchterman_reingold_layout
        self.layout_algorithms_dict['kamada_kawai'] = nx.kamada_kawai_layout
        self.layout_algorithms_dict['arf'] = nx.arf_layout
        self.layout_algorithms_dict['planar'] = nx.planar_layout
        self.layout_algorithms_dict['bipartite'] = nx.bipartite_layout
        self.layout_algorithms_dict['multipartite'] = nx.multipartite_layout

        mdl = gf.ComboModel(text_items=[(name, name) for name in self.layout_algorithms_dict.keys()])
        self.ui.automatic_layout_comboBox.setModel(mdl)
        idx = self.ui.automatic_layout_comboBox.findData('power_system_layout')
        if idx > -1:
            self.ui.automatic_layout_comboBox.setCurrentIndex(idx)

        # list of steps in the schematic
        self.schematic_list_steps = list()

        self.available_results_steps_dict = None

        self.ui.diagramSearchLineEdit.setPlaceholderText(self.tr("Type to search in the current diagram"))

        # task watcher for video export
        self.video_thread: VideoExportWorker | None = None

        # --------------------------------------------------------------------------------------------------------------
        self.ui.actionTakePicture.triggered.connect(self.take_picture)
        self.ui.actionRecord_video.triggered.connect(self.record_video)
        self.ui.actionTry_to_fix_buses_location.triggered.connect(self.try_to_fix_buses_location)
        self.ui.actionSet_schematic_positions_from_GPS_coordinates.triggered.connect(self.set_xy_from_lat_lon)

        self.ui.actionSetSelectedBusCountry.triggered.connect(lambda: self.set_selected_bus_property('country'))
        self.ui.actionSetSelectedBusArea.triggered.connect(lambda: self.set_selected_bus_property('area'))
        self.ui.actionSetSelectedBusZone.triggered.connect(lambda: self.set_selected_bus_property('zone'))

        self.ui.actionSelect_buses_by.triggered.connect(self.select_buses_by)
        self.ui.actionColor_buses_by.triggered.connect(self.color_buses_by)
        self.ui.actionColor_substations_by.triggered.connect(self.color_substations_by)

        self.ui.actionAdd_selected_to_contingency.triggered.connect(self.add_selected_to_contingency)
        self.ui.actionAdd_selected_as_remedial_action.triggered.connect(self.add_selected_to_remedial_action)
        self.ui.actionAdd_selected_as_new_investment.triggered.connect(self.add_selected_to_investment)
        self.ui.actionAdd_rms_event_to_selected.triggered.connect(self.add_rms_event_to_selected)
        self.ui.actionAdd_emt_event_to_selected.triggered.connect(self.add_emt_event_to_selected)
        self.ui.actionAdd_short_circuit_events.triggered.connect(self.add_short_circuit_events)

        self.ui.actionZoom_in.triggered.connect(self.zoom_in)
        self.ui.actionZoom_out.triggered.connect(self.zoom_out)
        self.ui.actionAdd_general_bus_branch_diagram.triggered.connect(self.add_complete_bus_branch_diagram)
        self.ui.actionNew_bus_branch_diagram_from_selection.triggered.connect(
            self.new_bus_branch_diagram_from_selection)
        self.ui.actionAdd_map.triggered.connect(self.add_map_diagram)
        self.ui.actionBigger_nodes.triggered.connect(self.bigger_nodes)
        self.ui.actionSmaller_nodes.triggered.connect(self.smaller_nodes)
        self.ui.actionCenter_view.triggered.connect(self.center_nodes)
        self.ui.actionAutoatic_layout.triggered.connect(self.auto_layout)

        self.ui.actionEdit_simulation_time_limits.triggered.connect(self.edit_time_interval)
        self.ui.actionDisable_all_results_tags.triggered.connect(self.disable_all_results_tags)
        self.ui.actionEnable_all_results_tags.triggered.connect(self.enable_all_results_tags)
        self.ui.actionConsolidate_diagram_coordinates.triggered.connect(self.consolidate_diagram_coordinates)
        self.ui.actionReset_coordinates.triggered.connect(self.reset_diagram_coordinates)
        self.ui.actionRotate.triggered.connect(self.rotate)
        self.ui.actionClear_highlights.triggered.connect(self.clear_big_bus_markers)

        self.ui.actionSetReticularBranchStyles.triggered.connect(self.set_diagram_branches_reticular_style)
        self.ui.actionSetStraightBranchStyles.triggered.connect(self.set_diagram_branches_straight_style)
        self.ui.actionRepair_diagram.triggered.connect(self.repair_selected_schematic_diagram)

        # Buttons
        self.ui.colour_results_pushButton.clicked.connect(self.colour_diagrams)
        self.ui.redraw_pushButton.clicked.connect(self.redraw_current_diagram)
        self.ui.diagramSearchButton.clicked.connect(self.search_diagram)

        self.ui.preset1_pushButton.clicked.connect(self.preset_1)
        self.ui.preset2_pushButton.clicked.connect(self.preset_2)
        self.ui.preset3_pushButton.clicked.connect(self.preset_3)
        self.ui.preset4_pushButton.clicked.connect(self.preset_4)

        # list / tree clicks
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is not None:
            diagrams_view.clicked.connect(self.set_selected_diagram_on_click)
            if hasattr(diagrams_view, 'doubleClicked'):
                diagrams_view.doubleClicked.connect(self.set_selected_diagram_on_click)

        # combobox change
        self.ui.palette_comboBox.currentIndexChanged.connect(self.set_diagrams_palette)
        self.ui.tile_provider_comboBox.currentIndexChanged.connect(self.set_diagrams_map_tile_provider)

        # TODO: this lambda calls to colour twice is the simulation is run the first time
        self.ui.available_results_to_color_comboBox.currentIndexChanged.connect(lambda: self.colour_diagrams(False))

        # sliders
        self.ui.diagram_step_slider.sliderReleased.connect(self.colour_diagrams)
        self.ui.diagram_step_slider.valueChanged.connect(self.diagrams_time_slider_change)
        self.ui.db_step_slider.valueChanged.connect(self.objects_time_slider_change)

        # spinbox change
        self.ui.explosion_factor_doubleSpinBox.valueChanged.connect(self.explosion_factor_change)
        self.ui.defaultBusVoltageSpinBox.valueChanged.connect(self.default_voltage_change)

        self.ui.min_branch_size_spinBox.valueChanged.connect(self.set_diagrams_size_constraints)
        self.ui.max_branch_size_spinBox.valueChanged.connect(self.set_diagrams_size_constraints)
        self.ui.min_node_size_spinBox.valueChanged.connect(self.set_diagrams_size_constraints)
        self.ui.max_node_size_spinBox.valueChanged.connect(self.set_diagrams_size_constraints)
        self.ui.arrow_size_size_spinBox.valueChanged.connect(self.set_diagrams_size_constraints)

        # check boxes
        self.ui.branch_width_based_on_flow_checkBox.clicked.connect(self.set_diagrams_size_constraints)
        self.ui.use_schematic_objects_color_checkBox.clicked.connect(self.re_colour_schematic)

        # TreeView
        self.ui.combinationsTreeView.clicked.connect(self.combinations_tree_clicked)

        # context menu and drag-and-drop
        if diagrams_view is not None:
            diagrams_view.customContextMenuRequested.connect(self.show_diagrams_context_menu)
            diagrams_view.setContextMenuPolicy(QtGui.Qt.ContextMenuPolicy.CustomContextMenu)
            diagrams_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
            diagrams_view.setDragEnabled(True)
            diagrams_view.setAcceptDrops(True)
            diagrams_view.setDropIndicatorShown(True)
            diagrams_view.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
            diagrams_view.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)

    def shutdown_tile_sources(self) -> bool:
        """
        Stop the map tile provider workers owned by the diagrams layer.

        :return: ``True`` when every tile worker has stopped.
        """
        all_stopped: bool = True
        diagram_widget: SchematicWidget | GridMapWidget
        for diagram_widget in self.diagram_widgets_list:
            if isinstance(diagram_widget, GridMapWidget):
                stopped: bool = diagram_widget.map.tile_src.shutdown()
                if stopped:
                    pass
                else:
                    all_stopped = False
            else:
                pass

        tile_source: CartoDbTiles
        for tile_source in self.tile_sources:
            stopped = tile_source.shutdown()
            if stopped:
                pass
            else:
                all_stopped = False

        return all_stopped

    def stop_all_threads(self) -> bool:
        """
        Stop GUI worker threads, including the tile workers owned by diagrams.

        :return: ``True`` when every known worker has stopped.
        """
        tile_sources_stopped: bool = self.shutdown_tile_sources()
        threads_stopped: bool = CompiledArraysMain.stop_all_threads(self)
        return tile_sources_stopped and threads_stopped

    def get_current_objects_model_view(self) -> ObjectModelFilterProxy | None:
        """
        Get the current ObjectModelFilterProxy from the GUI
        :return: ObjectModelFilterProxy
        """
        return self.ui.dataStructureTableView.model()

    def get_selected_db_table_objects(self) -> List[ALL_DEV_TYPES]:
        """
        Get the list of selected objects
        :return: List[ALL_DEV_TYPES]
        """
        model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()

        if model is not None:
            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            if len(sel_idx) > 0:

                # get the unique rows
                unique = set()
                for idx in sel_idx:
                    unique.add(idx.row())

                return model.get_objects_at_proxy_rows(proxy_rows=sorted(unique))
            else:
                info_msg(self.tr('Select some cells'))
                return list()
        else:
            return list()

    def get_default_voltage(self) -> float:
        """
        Get the default marked voltage
        :return:
        """
        return self.ui.defaultBusVoltageSpinBox.value()

    def auto_layout(self):
        """
        Automatic layout of the nodes
        """

        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget:
            if isinstance(diagram_widget, SchematicWidget):

                # guilty assumption
                do_it = True

                # if the ask, checkbox is checked, then ask
                if self.ui.ask_before_appliying_layout_checkBox.isChecked():
                    reply: bool = yes_no_question(
                        text=self.tr("Are you sure that you want to try an automatic layout?"),
                        title=self.tr("Message"),
                        parent=self,
                    )

                    if reply:
                        do_it = True
                    else:
                        do_it = False

                if do_it:
                    diagram_widget.auto_layout(sel=self.ui.automatic_layout_comboBox.currentData())

            else:
                info_msg(self.tr("The current diagram cannot be automatically layed out"))
        else:
            pass  # asked and decided ot to change the layout

    def bigger_nodes(self):
        """
        Move the nodes more separated
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, SchematicWidget):
                diagram.expand_node_distances()
                diagram.center_nodes()

    def smaller_nodes(self):
        """
        Move the nodes closer
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, SchematicWidget):
                diagram.shrink_node_distances()
                diagram.center_nodes()

    def center_nodes(self):
        """
        Center the nodes in the screen
        """

        widget = self.get_selected_diagram_widget()
        if widget is not None:
            if isinstance(widget, SchematicWidget):
                selected = self.get_diagram_selected_buses()

                if len(selected) == 0:
                    widget.center_nodes(elements=None)
                else:
                    buses = [bus for i, bus, graphic in selected]
                    widget.center_nodes(elements=buses)

            elif isinstance(widget, GridMapWidget):
                widget.center()

    def get_diagram_selected_buses(self) -> List[Tuple[int, dev.Bus, BusGraphicItem | None]]:
        """
        Get the selected buses
        :return: list of (bus position, bus object, bus_graphics object)
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            return diagram_widget.get_selected_buses()
        elif isinstance(diagram_widget, GridMapWidget):
            return diagram_widget.get_selected_buses()
        else:
            return list()

    def get_current_diagram_buses(self) -> List[Tuple[int, dev.Bus, BusGraphicItem]]:
        """
        Get the selected buses
        :return: list of (bus position, bus object, bus_graphics object)
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            return diagram_widget.get_buses()
        else:
            return list()

    def get_current_diagram_substations(self) -> List[Tuple[int, dev.Substation, SubstationGraphicItem]]:
        """
        Get the selected buses
        :return: list of (bus position, bus object, bus_graphics object)
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, GridMapWidget):
            return diagram_widget.get_substations()
        else:
            return list()

    def explosion_factor_change(self):
        """
        Change the node explosion factor
        """
        for diagram in self.diagram_widgets_list:
            if isinstance(diagram, SchematicWidget):
                diagram.expand_factor = self.ui.explosion_factor_doubleSpinBox.value()

    def zoom_in(self):
        """
        Zoom the diagram in
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, SchematicWidget):
                diagram.zoom_in()
            elif isinstance(diagram, GridMapWidget):
                diagram.zoom_in()
            else:
                print("zoom_in: Unsupported diagram type")

    def zoom_out(self):
        """
        Zoom the diagram out
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, Union[SchematicWidget, GridMapWidget]):
                diagram.zoom_out()
            else:
                print("zoom_out: Unsupported diagram type")

    def edit_time_interval(self):
        """
        Run the simulation limits adjust window
        """

        if self.circuit.has_time_series:
            if self.circuit.get_time_number() > 0:
                start_end_dialogue_window: StartEndSelectionDialogue = StartEndSelectionDialogue(
                    min_value=self.simulation_start_index,
                    max_value=self.simulation_end_index,
                    time_array=self.circuit.time_profile)

                start_end_dialogue_window.setModal(True)
                try:
                    exec_dialog_safely(dialog=start_end_dialogue_window)
                    is_accepted: bool = start_end_dialogue_window.is_accepted
                    start_value: int = start_end_dialogue_window.start_value
                    end_value: int = start_end_dialogue_window.end_value
                finally:
                    delete_dialog_safely(dialog=start_end_dialogue_window)

                if is_accepted:
                    self.setup_sim_indices(st=start_value, en=end_value)
                else:
                    pass
            else:
                self.show_error_toast("Empty time series :/")
        else:
            self.show_error_toast("There are no time series :/")

    def pf_colouring(self, diagram_widget: ALL_EDITORS,
                     results: PowerFlowResults,
                     cmap: Colormaps,
                     use_flow_based_width: bool = False,
                     min_branch_width: int = 2,
                     max_branch_width: int = 5,
                     min_bus_width: int = 2,
                     max_bus_width: int = 5):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)

        return diagram_widget.colour_results(
            Sbus=results.Sbus,
            bus_active=bus_active,
            Sf=results.Sf,
            St=results.St,
            voltages=results.voltage,
            loadings=np.abs(results.loading),
            types=results.bus_types,
            losses=results.losses,
            br_active=br_active,
            hvdc_Pf=results.Pf_hvdc,
            hvdc_Pt=results.Pt_hvdc,
            hvdc_losses=results.losses_hvdc,
            hvdc_loading=results.loading_hvdc,
            hvdc_active=hvdc_active,
            vsc_Pf=results.Pfp_vsc,
            vsc_Pt=results.St_vsc.real,
            vsc_Qt=results.St_vsc.imag,
            vsc_losses=results.losses_vsc,
            vsc_loading=results.loading_vsc,
            vsc_active=vsc_active,
            ma=results.tap_module,
            tau=results.tap_angle,
            use_flow_based_width=use_flow_based_width,
            min_branch_width=min_branch_width,
            max_branch_width=max_branch_width,
            min_bus_width=min_bus_width,
            max_bus_width=max_bus_width,
            cmap=cmap,
            gen_p=results.gen_p,
            gen_q=results.gen_q,
            gen_names=results.gen_names,
            battery_p=results.battery_p,
            battery_q=results.battery_q,
            battery_names=results.batt_names,
            shunt_q=results.shunt_q,
            shunt_names=results.sh_names
        )

    def pf_3ph_colouring(self, diagram_widget: ALL_EDITORS,
                         results: PowerFlowResults3Ph,
                         cmap: Colormaps,
                         use_flow_based_width: bool = False,
                         min_branch_width: int = 2,
                         max_branch_width: int = 5,
                         min_bus_width: int = 2,
                         max_bus_width: int = 5):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)

        return diagram_widget.colour_results_3ph(
            SbusA=results.Sbus_A,
            SbusB=results.Sbus_B,
            SbusC=results.Sbus_C,
            voltagesA=results.voltage_A,
            voltagesB=results.voltage_B,
            voltagesC=results.voltage_C,
            bus_active=bus_active,
            types=results.bus_types,
            SfA=results.Sf_A,
            SfB=results.Sf_B,
            SfC=results.Sf_C,
            StA=results.St_A,
            StB=results.St_B,
            StC=results.St_C,
            loadingsA=results.loading_A,
            loadingsB=results.loading_B,
            loadingsC=results.loading_C,
            lossesA=results.losses_A,
            lossesB=results.losses_B,
            lossesC=results.losses_C,
            br_active=br_active,
            ma=results.tap_module,
            tau=results.tap_angle,
            hvdc_PfA=results.Pf_hvdc_A,
            hvdc_PfB=results.Pf_hvdc_B,
            hvdc_PfC=results.Pf_hvdc_C,
            hvdc_PtA=results.Pt_hvdc_A,
            hvdc_PtB=results.Pt_hvdc_B,
            hvdc_PtC=results.Pt_hvdc_C,
            hvdc_losses=results.losses_hvdc,
            hvdc_loading=results.loading_hvdc,
            hvdc_active=hvdc_active,
            vsc_Pf=results.Pfp_vsc,
            vsc_PtA=results.St_vsc_A.real,
            vsc_PtB=results.St_vsc_B.real,
            vsc_PtC=results.St_vsc_C.real,
            vsc_QtA=results.St_vsc_A.imag,
            vsc_QtB=results.St_vsc_B.imag,
            vsc_QtC=results.St_vsc_C.imag,
            vsc_losses=results.losses_vsc,
            vsc_loading=results.loading_vsc,
            vsc_active=vsc_active,
            loading_label='loading',
            use_flow_based_width=use_flow_based_width,
            min_branch_width=min_branch_width,
            max_branch_width=max_branch_width,
            min_bus_width=min_bus_width,
            max_bus_width=max_bus_width,
            cmap=cmap,
            gen_q_a=results.gen_q_A,
            gen_q_b=results.gen_q_B,
            gen_q_c=results.gen_q_C,
            gen_names=results.gen_names,
            battery_q_a=results.battery_q_A,
            battery_q_b=results.battery_q_B,
            battery_q_c=results.battery_q_C,
            battery_names=results.batt_names,
            shunt_q_a=results.shunt_q_A,
            shunt_q_b=results.shunt_q_B,
            shunt_q_c=results.shunt_q_C,
            shunt_names=results.sh_names)

    def se_colouring(self, diagram_widget: ALL_EDITORS,
                     results: StateEstimationResults,
                     cmap: Colormaps,
                     use_flow_based_width: bool = False,
                     min_branch_width: int = 2,
                     max_branch_width: int = 5,
                     min_bus_width: int = 2,
                     max_bus_width: int = 5):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)

        return diagram_widget.colour_results(
            Sbus=results.Sbus,
            bus_active=bus_active,
            Sf=results.Sf,
            St=results.St,
            voltages=results.voltage,
            loadings=np.abs(results.loading),
            types=results.bus_types,
            losses=results.losses,
            br_active=br_active,
            hvdc_Pf=results.Pf_hvdc,
            hvdc_Pt=results.Pt_hvdc,
            hvdc_losses=results.losses_hvdc,
            hvdc_loading=results.loading_hvdc,
            hvdc_active=hvdc_active,
            vsc_Pf=results.Pf_vsc,
            vsc_Pt=results.St_vsc.real,
            vsc_Qt=results.St_vsc.imag,
            vsc_losses=results.losses_vsc,
            vsc_loading=results.loading_vsc,
            vsc_active=vsc_active,
            ma=results.tap_module,
            tau=results.tap_angle,
            use_flow_based_width=use_flow_based_width,
            min_branch_width=min_branch_width,
            max_branch_width=max_branch_width,
            min_bus_width=min_bus_width,
            max_bus_width=max_bus_width,
            cmap=cmap,
            gen_p=None,
            gen_q=results.gen_q,
            gen_names=results.gen_names,
            battery_p=None,
            battery_q=results.battery_q,
            battery_names=results.batt_names,
            shunt_q=results.shunt_q,
            shunt_names=results.sh_names
        )

    def pf_ts_colouring(self, t_idx: int,
                        diagram_widget: ALL_EDITORS,
                        results: PowerFlowTimeSeriesResults, cmap: Colormaps,
                        use_flow_based_width: bool = False,
                        min_branch_width: int = 2,
                        max_branch_width: int = 5,
                        min_bus_width: int = 2,
                        max_bus_width: int = 5):
        """

        :param t_idx:
        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=t_idx)
        br_active = self.circuit.get_branch_actives(t_idx=t_idx, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=t_idx)
        vsc_active = self.circuit.get_vsc_actives(t_idx=t_idx)

        return diagram_widget.colour_results(Sbus=results.S[t_idx, :],
                                             bus_active=bus_active,
                                             Sf=results.Sf[t_idx, :],
                                             St=results.St[t_idx, :],
                                             voltages=results.voltage[t_idx, :],
                                             loadings=np.abs(results.loading[t_idx, :]),
                                             types=results.bus_types,
                                             losses=results.losses[t_idx, :],
                                             br_active=br_active,
                                             hvdc_Pf=results.hvdc_Pf[t_idx, :],
                                             hvdc_Pt=results.hvdc_Pt[t_idx, :],
                                             hvdc_losses=results.hvdc_losses[t_idx, :],
                                             hvdc_loading=results.hvdc_loading[t_idx, :],
                                             hvdc_active=hvdc_active,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap,
                                             gen_p=results.gen_p[t_idx, :],
                                             gen_q=results.gen_q[t_idx, :],
                                             gen_names=results.gen_names,
                                             battery_p=results.battery_p[t_idx, :],
                                             battery_q=results.battery_q[t_idx, :],
                                             battery_names=results.batt_names,
                                             shunt_q=results.shunt_q[t_idx, :],
                                             shunt_names=results.sh_names,
                                             t_idx=t_idx)

    def pf_3ph_ts_colouring(self, t_idx: int,
                            diagram_widget: ALL_EDITORS,
                            results: PowerFlowTimeSeriesResults3Ph, cmap: Colormaps,
                            use_flow_based_width: bool = False,
                            min_branch_width: int = 2,
                            max_branch_width: int = 5,
                            min_bus_width: int = 2,
                            max_bus_width: int = 5):
        """

        :param t_idx:
        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=t_idx)
        br_active = self.circuit.get_branch_actives(t_idx=t_idx, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=t_idx)
        vsc_active = self.circuit.get_vsc_actives(t_idx=t_idx)

        return diagram_widget.colour_results_3ph(
            SbusA=results.Sbus_A[t_idx, :],
            SbusB=results.Sbus_B[t_idx, :],
            SbusC=results.Sbus_C[t_idx, :],
            voltagesA=results.voltage_A[t_idx, :],
            voltagesB=results.voltage_B[t_idx, :],
            voltagesC=results.voltage_C[t_idx, :],
            bus_active=bus_active,
            types=results.bus_types,
            SfA=results.Sf_A[t_idx, :],
            SfB=results.Sf_B[t_idx, :],
            SfC=results.Sf_C[t_idx, :],
            StA=results.St_A[t_idx, :],
            StB=results.St_B[t_idx, :],
            StC=results.St_C[t_idx, :],
            loadingsA=results.loading_A[t_idx, :],
            loadingsB=results.loading_B[t_idx, :],
            loadingsC=results.loading_C[t_idx, :],
            lossesA=results.losses_A[t_idx, :],
            lossesB=results.losses_B[t_idx, :],
            lossesC=results.losses_C[t_idx, :],
            br_active=br_active,
            ma=results.tap_module[t_idx, :],
            tau=results.tap_angle[t_idx, :],
            hvdc_PfA=results.Pf_hvdc_A[t_idx, :],
            hvdc_PfB=results.Pf_hvdc_B[t_idx, :],
            hvdc_PfC=results.Pf_hvdc_C[t_idx, :],
            hvdc_PtA=results.Pt_hvdc_A[t_idx, :],
            hvdc_PtB=results.Pt_hvdc_B[t_idx, :],
            hvdc_PtC=results.Pt_hvdc_C[t_idx, :],
            hvdc_losses=results.losses_hvdc[t_idx, :],
            hvdc_loading=results.loading_hvdc[t_idx, :],
            hvdc_active=hvdc_active,
            vsc_Pf=results.Pfp_vsc[t_idx, :],
            vsc_PtA=results.St_vsc_A[t_idx, :].real,
            vsc_PtB=results.St_vsc_B[t_idx, :].real,
            vsc_PtC=results.St_vsc_C[t_idx, :].real,
            vsc_QtA=results.St_vsc_A[t_idx, :].imag,
            vsc_QtB=results.St_vsc_B[t_idx, :].imag,
            vsc_QtC=results.St_vsc_C[t_idx, :].imag,
            vsc_losses=results.losses_vsc[t_idx, :],
            vsc_loading=results.loading_vsc[t_idx, :],
            vsc_active=vsc_active,
            loading_label='loading',
            use_flow_based_width=use_flow_based_width,
            min_branch_width=min_branch_width,
            max_branch_width=max_branch_width,
            min_bus_width=min_bus_width,
            max_bus_width=max_bus_width,
            cmap=cmap,
            gen_q_a=results.gen_q_A[t_idx, :],
            gen_q_b=results.gen_q_B[t_idx, :],
            gen_q_c=results.gen_q_C[t_idx, :],
            gen_names=results.gen_names,
            battery_q_a=results.battery_q_A[t_idx, :],
            battery_q_b=results.battery_q_B[t_idx, :],
            battery_q_c=results.battery_q_C[t_idx, :],
            battery_names=results.batt_names,
            shunt_q_a=results.shunt_q_A[t_idx, :],
            shunt_q_b=results.shunt_q_B[t_idx, :],
            shunt_q_c=results.shunt_q_C[t_idx, :],
            shunt_names=results.sh_names)

    def cpf_colouring(self, diagram_widget: ALL_EDITORS,
                      results: ContinuationPowerFlowResults, cmap: Colormaps,
                      use_flow_based_width: bool = False,
                      min_branch_width: int = 2,
                      max_branch_width: int = 5,
                      min_bus_width: int = 2,
                      max_bus_width: int = 5):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)

        if results.Sbus.shape[0] > 0:
            return diagram_widget.colour_results(Sbus=results.Sbus[-1, :],
                                                 bus_active=bus_active,
                                                 Sf=results.Sf[-1, :],
                                                 St=results.St[-1, :],
                                                 voltages=results.voltages[-1, :],
                                                 types=results.bus_types,
                                                 loadings=np.abs(results.loading[-1, :]),
                                                 br_active=br_active,
                                                 hvdc_Pf=None,
                                                 hvdc_Pt=None,
                                                 hvdc_losses=None,
                                                 hvdc_loading=None,
                                                 hvdc_active=hvdc_active,
                                                 use_flow_based_width=use_flow_based_width,
                                                 min_branch_width=min_branch_width,
                                                 max_branch_width=max_branch_width,
                                                 min_bus_width=min_bus_width,
                                                 max_bus_width=max_bus_width,
                                                 cmap=cmap)

    def spf_colouring(self, diagram_widget: ALL_EDITORS,
                      results: sim.StochasticPowerFlowResults, cmap: Colormaps,
                      use_flow_based_width: bool = False,
                      min_branch_width: int = 2,
                      max_branch_width: int = 5,
                      min_bus_width: int = 2,
                      max_bus_width: int = 5):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)

        return diagram_widget.colour_results(Sbus=results.S_points.mean(axis=0),
                                             types=results.bus_types,
                                             voltages=results.V_points.mean(axis=0),
                                             bus_active=bus_active,
                                             loadings=np.abs(results.loading_points).mean(axis=0),
                                             Sf=results.Sbr_points.mean(axis=0),
                                             St=-results.Sbr_points.mean(axis=0),
                                             br_active=br_active,
                                             hvdc_Pf=None,
                                             hvdc_Pt=None,
                                             hvdc_losses=None,
                                             hvdc_loading=None,
                                             hvdc_active=None,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def sc_colouring(self, diagram_widget: ALL_EDITORS,
                     results: sim.ShortCircuitResults,
                     cmap: Colormaps,
                     use_flow_based_width: bool = False,
                     min_branch_width: int = 2,
                     max_branch_width: int = 5,
                     min_bus_width: int = 2,
                     max_bus_width: int = 5,
                     sc_index: int = 0):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :param sc_index:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)
        method = self.circuit.short_circuit_event[sc_index].method

        if method == MethodShortCircuit.phases:
            has_phase_results = (
                np.any(np.abs(results.voltageA[:, sc_index]) > 0.0)
                or np.any(np.abs(results.voltageB[:, sc_index]) > 0.0)
                or np.any(np.abs(results.voltageC[:, sc_index]) > 0.0)
            )
            if not has_phase_results and np.any(np.abs(results.voltage1[:, sc_index]) > 0.0):
                method = MethodShortCircuit.sequences
            else:
                return diagram_widget.colour_results_3ph(
                    SbusA=results.SbusA[:, sc_index],
                    SbusB=results.SbusB[:, sc_index],
                    SbusC=results.SbusC[:, sc_index],
                    bus_active=bus_active,
                    SfA=results.SfA[:, sc_index],
                    SfB=results.SfB[:, sc_index],
                    SfC=results.SfC[:, sc_index],
                    StA=results.StA[:, sc_index],
                    StB=results.StB[:, sc_index],
                    StC=results.StC[:, sc_index],
                    voltagesA=results.voltageA[:, sc_index],
                    voltagesB=results.voltageB[:, sc_index],
                    voltagesC=results.voltageC[:, sc_index],
                    types=results.bus_types,
                    loadingsA=results.loadingA[:, sc_index],
                    loadingsB=results.loadingB[:, sc_index],
                    loadingsC=results.loadingC[:, sc_index],
                    lossesA=results.lossesA[:, sc_index],
                    lossesB=results.lossesB[:, sc_index],
                    lossesC=results.lossesC[:, sc_index],
                    br_active=br_active,
                    hvdc_PfA=results.hvdc_Pf[:, sc_index],
                    hvdc_PfB=results.hvdc_Pf[:, sc_index],
                    hvdc_PfC=results.hvdc_Pf[:, sc_index],
                    hvdc_PtA=results.hvdc_Pt[:, sc_index],
                    hvdc_PtB=results.hvdc_Pt[:, sc_index],
                    hvdc_PtC=results.hvdc_Pt[:, sc_index],
                    hvdc_losses=results.hvdc_losses[:, sc_index],
                    hvdc_loading=results.hvdc_loading[:, sc_index],
                    hvdc_active=hvdc_active,
                    vsc_Pf=results.vsc_Pfp[:, sc_index],
                    vsc_PtA=results.vsc_St.real[:, sc_index],
                    vsc_PtB=results.vsc_St.real[:, sc_index],
                    vsc_PtC=results.vsc_St.real[:, sc_index],
                    vsc_QtA=results.vsc_St.imag[:, sc_index],
                    vsc_QtB=results.vsc_St.imag[:, sc_index],
                    vsc_QtC=results.vsc_St.imag[:, sc_index],
                    vsc_losses=results.vsc_losses[:, sc_index],
                    vsc_loading=results.vsc_loading[:, sc_index],
                    vsc_active=vsc_active,
                    use_flow_based_width=use_flow_based_width,
                    min_branch_width=min_branch_width,
                    max_branch_width=max_branch_width,
                    min_bus_width=min_bus_width,
                    max_bus_width=max_bus_width,
                    cmap=cmap,
                )

        if method == MethodShortCircuit.sequences:
            return diagram_widget.colour_results(Sbus=results.Sbus1[:, sc_index],
                                                 bus_active=bus_active,
                                                 Sf=results.Sf1[:, sc_index],
                                                 St=results.St1[:, sc_index],
                                                 voltages=results.voltage1[:, sc_index],
                                                 types=results.bus_types,
                                                 loadings=results.loading1[:, sc_index],
                                                 br_active=br_active,
                                                 hvdc_Pf=None,
                                                 hvdc_Pt=None,
                                                 hvdc_losses=None,
                                                 hvdc_loading=None,
                                                 hvdc_active=hvdc_active,
                                                 vsc_Pf=results.vsc_Pfp[:, sc_index],
                                                 vsc_Pt=results.vsc_St.real[:, sc_index],
                                                 vsc_Qt=results.vsc_St.imag[:, sc_index],
                                                 vsc_losses=results.vsc_losses[:, sc_index],
                                                 vsc_loading=results.vsc_loading[:, sc_index],
                                                 vsc_active=vsc_active,
                                                 use_flow_based_width=use_flow_based_width,
                                                 min_branch_width=min_branch_width,
                                                 max_branch_width=max_branch_width,
                                                 min_bus_width=min_bus_width,
                                                 max_bus_width=max_bus_width,
                                                 cmap=cmap)

        return None

    def opf_colouring(self, diagram_widget: ALL_EDITORS,
                      results: sim.OptimalPowerFlowResults, cmap: Colormaps,
                      use_flow_based_width: bool = False,
                      min_branch_width: int = 2,
                      max_branch_width: int = 5,
                      min_bus_width: int = 2,
                      max_bus_width: int = 5):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)

        return diagram_widget.colour_results(Sbus=results.Sbus,
                                             voltages=results.voltage,
                                             bus_active=bus_active,
                                             loadings=results.loading,
                                             types=results.bus_types,

                                             Sf=results.Sf,
                                             St=results.St,
                                             br_active=br_active,

                                             hvdc_Pf=results.hvdc_Pf,
                                             hvdc_Pt=-results.hvdc_Pf,
                                             hvdc_loading=results.hvdc_loading,
                                             hvdc_active=hvdc_active,

                                             vsc_Pf=results.vsc_Pf,
                                             vsc_Pt=-results.vsc_Pf,
                                             vsc_Qt=np.zeros_like(results.vsc_Pf),
                                             vsc_loading=results.vsc_loading,
                                             vsc_active=vsc_active,

                                             fluid_node_p2x_flow=results.fluid_node_p2x_flow,
                                             fluid_node_current_level=results.fluid_node_current_level,
                                             fluid_node_spillage=results.fluid_node_spillage,
                                             fluid_node_flow_in=results.fluid_node_flow_in,
                                             fluid_node_flow_out=results.fluid_node_flow_out,
                                             fluid_path_flow=results.fluid_path_flow,
                                             fluid_injection_flow=results.fluid_injection_flow,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap,
                                             gen_p=results.generator_power,
                                             gen_q=results.generator_reactive_power,
                                             gen_names=results.generator_names,
                                             battery_p=results.battery_power,
                                             battery_q=None,
                                             battery_names=results.battery_names,
                                             shunt_q=results.shunt_like_reactive_power,
                                             shunt_names=results.shunt_like_names)

    def opf_ts_colouring(self, t_idx: int,
                         diagram_widget: ALL_EDITORS,
                         results: sim.OptimalPowerFlowTimeSeriesResults,
                         cmap: Colormaps,
                         use_flow_based_width: bool = False,
                         min_branch_width: int = 2,
                         max_branch_width: int = 5,
                         min_bus_width: int = 2,
                         max_bus_width: int = 5):
        """

        :param t_idx:
        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=t_idx)
        br_active = self.circuit.get_branch_actives(t_idx=t_idx, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=t_idx)
        vsc_active = self.circuit.get_vsc_actives(t_idx=t_idx)

        return diagram_widget.colour_results(voltages=results.voltage[t_idx, :],
                                             Sbus=results.Sbus[t_idx, :],
                                             types=results.bus_types,
                                             bus_active=bus_active,
                                             Sf=results.Sf[t_idx, :],
                                             St=results.St[t_idx, :],
                                             loadings=np.abs(results.loading[t_idx, :]),
                                             br_active=br_active,
                                             hvdc_Pf=results.hvdc_Pf[t_idx, :],
                                             hvdc_Pt=-results.hvdc_Pf[t_idx, :],
                                             hvdc_loading=results.hvdc_loading[t_idx, :],
                                             hvdc_active=hvdc_active,
                                             fluid_node_p2x_flow=results.fluid_node_p2x_flow[t_idx, :],
                                             fluid_node_current_level=results.fluid_node_current_level[t_idx, :],
                                             fluid_node_spillage=results.fluid_node_spillage[t_idx, :],
                                             fluid_node_flow_in=results.fluid_node_flow_in[t_idx, :],
                                             fluid_node_flow_out=results.fluid_node_flow_out[t_idx, :],
                                             fluid_path_flow=results.fluid_path_flow[t_idx, :],
                                             fluid_injection_flow=results.fluid_injection_flow[t_idx, :],
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap,
                                             gen_p=results.generator_power[t_idx, :],
                                             gen_q=results.generator_reactive_power[t_idx, :],
                                             gen_names=results.generator_names,
                                             battery_p=results.battery_power[t_idx, :],
                                             battery_q=None,
                                             battery_names=results.battery_names,
                                             shunt_q=results.shunt_like_reactive_power[t_idx, :],
                                             shunt_names=results.shunt_like_names,
                                             t_idx=t_idx)

    def ntc_colouring(self, diagram_widget: ALL_EDITORS,
                      results: sim.OptimalNetTransferCapacityResults, cmap: Colormaps,
                      use_flow_based_width: bool = False,
                      min_branch_width: int = 2,
                      max_branch_width: int = 5,
                      min_bus_width: int = 2,
                      max_bus_width: int = 5):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)

        return diagram_widget.colour_results(Sbus=results.Sbus,
                                             voltages=results.voltage,
                                             bus_active=bus_active,
                                             loadings=results.loading,
                                             types=results.bus_types,

                                             Sf=results.Sf,
                                             St=results.St,
                                             br_active=br_active,

                                             hvdc_Pf=results.hvdc_Pf,
                                             hvdc_Pt=-results.hvdc_Pf,
                                             hvdc_loading=results.hvdc_loading,
                                             hvdc_active=hvdc_active,

                                             vsc_Pf=results.vsc_Pf,
                                             vsc_Pt=-results.vsc_Pf,
                                             vsc_loading=results.vsc_loading,
                                             vsc_active=vsc_active,

                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def ntc_ts_colouring(self, t_idx: int,
                         diagram_widget: ALL_EDITORS,
                         results: sim.OptimalNetTransferCapacityTimeSeriesResults,
                         cmap: Colormaps,
                         use_flow_based_width: bool = False,
                         min_branch_width: int = 2,
                         max_branch_width: int = 5,
                         min_bus_width: int = 2,
                         max_bus_width: int = 5):
        """

        :param t_idx:
        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=t_idx)
        br_active = self.circuit.get_branch_actives(t_idx=t_idx, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=t_idx)
        vsc_active = self.circuit.get_vsc_actives(t_idx=t_idx)

        return diagram_widget.colour_results(voltages=results.voltage[t_idx, :],
                                             Sbus=results.Sbus[t_idx, :],
                                             types=np.ones(self.circuit.get_bus_number(), dtype=int),
                                             bus_active=bus_active,
                                             Sf=results.Sf[t_idx, :],
                                             St=results.St[t_idx, :],
                                             loadings=np.abs(results.loading[t_idx, :]),
                                             br_active=br_active,
                                             hvdc_Pf=results.hvdc_Pf[t_idx, :],
                                             hvdc_Pt=-results.hvdc_Pf[t_idx, :],
                                             hvdc_loading=results.hvdc_loading[t_idx, :],
                                             hvdc_active=hvdc_active,
                                             vsc_Pf=results.vsc_Pf[t_idx, :],
                                             vsc_Pt=-results.vsc_Pf[t_idx, :],
                                             vsc_loading=results.vsc_loading[t_idx, :],
                                             vsc_active=vsc_active,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def nc_ts_colouring(self, t_idx: int | None,
                        diagram_widget: ALL_EDITORS,
                        results: sim.NodalCapacityTimeSeriesResults,
                        cmap: Colormaps,
                        use_flow_based_width: bool = False,
                        min_branch_width: int = 2,
                        max_branch_width: int = 5,
                        min_bus_width: int = 2,
                        max_bus_width: int = 5):
        """

        :param t_idx:
        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        t_idx2 = 0 if t_idx is None else t_idx
        bus_active = self.circuit.get_bus_actives(t_idx=t_idx)
        br_active = self.circuit.get_branch_actives(t_idx=t_idx, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=t_idx)
        vsc_active = self.circuit.get_vsc_actives(t_idx=t_idx)

        return diagram_widget.colour_results(voltages=results.voltage[t_idx2, :],
                                             Sbus=results.Sbus[t_idx2, :],
                                             types=results.bus_types,
                                             bus_active=bus_active,
                                             Sf=results.Sf[t_idx2, :],
                                             St=results.St[t_idx2, :],
                                             loadings=np.abs(results.loading[t_idx2, :]),
                                             br_active=br_active,
                                             hvdc_Pf=results.hvdc_Pf[t_idx2, :],
                                             hvdc_Pt=-results.hvdc_Pf[t_idx2, :],
                                             hvdc_loading=results.hvdc_loading[t_idx2, :],
                                             hvdc_active=hvdc_active,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def nc_colouring(self, diagram_widget: ALL_EDITORS,
                     results: sim.NodalCapacityResults,
                     cmap: Colormaps,
                     use_flow_based_width: bool = False,
                     min_branch_width: int = 2,
                     max_branch_width: int = 5,
                     min_bus_width: int = 2,
                     max_bus_width: int = 5):
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)

        return diagram_widget.colour_results(voltages=results.voltage,
                                             Sbus=results.Sbus,
                                             types=results.bus_types,
                                             bus_active=bus_active,
                                             Sf=results.Sf,
                                             St=results.St,
                                             loadings=np.abs(results.loading),
                                             br_active=br_active,
                                             hvdc_Pf=results.hvdc_Pf,
                                             hvdc_Pt=-results.hvdc_Pf,
                                             hvdc_loading=results.hvdc_loading,
                                             hvdc_active=hvdc_active,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def linpf_colouring(self, diagram_widget: ALL_EDITORS,
                        results: sim.LinearAnalysisResults, cmap: Colormaps,
                        use_flow_based_width: bool = False,
                        min_branch_width: int = 2,
                        max_branch_width: int = 5,
                        min_bus_width: int = 2,
                        max_bus_width: int = 5):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)

        voltage = np.ones(self.circuit.get_bus_number(), dtype=complex)

        return diagram_widget.colour_results(voltages=voltage,
                                             Sbus=results.Sbus.astype(complex),
                                             types=results.bus_types.astype(int),
                                             bus_active=bus_active,
                                             Sf=results.Sf.astype(complex),
                                             St=-results.Sf.astype(complex),
                                             loadings=results.loading.astype(complex),
                                             br_active=br_active,
                                             hvdc_active=hvdc_active,
                                             loading_label='Loading',
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def linpf_ts_colouring(self, t_idx: int,
                           diagram_widget: ALL_EDITORS,
                           results: sim.LinearAnalysisTimeSeriesResults,
                           cmap: Colormaps,
                           use_flow_based_width: bool = False,
                           min_branch_width: int = 2,
                           max_branch_width: int = 5,
                           min_bus_width: int = 2,
                           max_bus_width: int = 5):
        """

        :param t_idx:
        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=t_idx)
        br_active = self.circuit.get_branch_actives(t_idx=t_idx, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=t_idx)
        vsc_active = self.circuit.get_vsc_actives(t_idx=t_idx)

        return diagram_widget.colour_results(Sbus=results.S[t_idx],
                                             voltages=results.voltage[t_idx],
                                             types=results.bus_types,
                                             bus_active=bus_active,
                                             Sf=results.Sf[t_idx],
                                             St=-results.Sf[t_idx],
                                             loadings=np.abs(results.loading[t_idx]),
                                             br_active=br_active,
                                             hvdc_active=hvdc_active,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def con_colouring(self, diagram_widget: ALL_EDITORS,
                      results: sim.ContingencyAnalysisResults, cmap: Colormaps,
                      use_flow_based_width: bool = False,
                      min_branch_width: int = 2,
                      max_branch_width: int = 5,
                      min_bus_width: int = 2,
                      max_bus_width: int = 5):
        """

        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=None)
        br_active = self.circuit.get_branch_actives(t_idx=None, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=None)
        vsc_active = self.circuit.get_vsc_actives(t_idx=None)
        con_idx = 0
        return diagram_widget.colour_results(Sbus=results.Sbus[con_idx, :],
                                             voltages=results.voltage[con_idx, :],
                                             types=results.bus_types,
                                             bus_active=bus_active,
                                             Sf=results.Sf[con_idx, :],
                                             St=-results.Sf[con_idx, :],
                                             loadings=np.abs(results.loading[con_idx, :]),
                                             br_active=br_active,
                                             hvdc_active=hvdc_active,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def con_ts_colouring(self, t_idx: int,
                         diagram_widget: ALL_EDITORS,
                         results: sim.ContingencyAnalysisTimeSeriesResults,
                         cmap: Colormaps,
                         use_flow_based_width: bool = False,
                         min_branch_width: int = 2,
                         max_branch_width: int = 5,
                         min_bus_width: int = 2,
                         max_bus_width: int = 5):
        """

        :param t_idx:
        :param diagram_widget:
        :param results:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        bus_active = self.circuit.get_bus_actives(t_idx=t_idx)
        br_active = self.circuit.get_branch_actives(t_idx=t_idx, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=t_idx)
        vsc_active = self.circuit.get_vsc_actives(t_idx=t_idx)

        return diagram_widget.colour_results(voltages=np.ones(results.nbus, dtype=complex),
                                             Sbus=results.S[t_idx, :].astype(complex),
                                             types=results.bus_types,
                                             bus_active=bus_active,
                                             Sf=results.max_flows[t_idx, :].astype(complex),
                                             St=-results.max_flows[t_idx, :].astype(complex),
                                             loadings=results.max_loading[t_idx].astype(complex),
                                             br_active=br_active,
                                             hvdc_active=hvdc_active,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def node_group_colouring(self,
                             results: sim.NodeGroupsResults,
                             diagram_widget: ALL_EDITORS):
        """

        :param results:
        :param diagram_widget:
        :return:
        """
        colours = viz.get_n_colours(n=len(results.groups_by_index))

        bus_graphics_dict = diagram_widget.graphics_manager.get_device_type_dict(DeviceType.BusDevice)
        for c, group in enumerate(results.groups_by_index):
            for i in group:
                bus = self.circuit.buses[i]
                bus_graphic: BusGraphicItem = bus_graphics_dict.get(bus.idtag, None)
                if bus_graphic is not None:
                    r, g, b, a = colours[c]
                    color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
                    bus_graphic.set_tile_color(brush=color)
                    bus_graphic.setToolTip('Group ' + str(c))

    def default_colouring(self, t_idx: int | None,
                          diagram_widget: ALL_EDITORS,
                          cmap: Colormaps,
                          use_flow_based_width: bool = False,
                          min_branch_width: int = 2,
                          max_branch_width: int = 5,
                          min_bus_width: int = 2,
                          max_bus_width: int = 5):
        """

        :param t_idx:
        :param diagram_widget:
        :param cmap:
        :param use_flow_based_width:
        :param min_branch_width:
        :param max_branch_width:
        :param min_bus_width:
        :param max_bus_width:
        :return:
        """
        nbus = self.circuit.get_bus_number()
        nbr = self.circuit.get_branch_number(add_vsc=False, add_hvdc=False, add_switch=True)
        nhvdc = self.circuit.get_hvdc_number()
        nvsc = self.circuit.get_vsc_number()

        bus_active = self.circuit.get_bus_actives(t_idx=t_idx)
        br_active = self.circuit.get_branch_actives(t_idx=t_idx, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=t_idx)
        vsc_active = self.circuit.get_vsc_actives(t_idx=t_idx)

        if isinstance(diagram_widget, SchematicWidget):
            return diagram_widget.colour_results(Sbus=np.zeros(nbus, dtype=complex),
                                                 voltages=np.ones(nbus, dtype=complex),
                                                 bus_active=bus_active,
                                                 Sf=np.zeros(nbr, dtype=complex),
                                                 St=np.zeros(nbr, dtype=complex),
                                                 loadings=np.zeros(nbr, dtype=complex),
                                                 br_active=br_active,
                                                 hvdc_active=hvdc_active,
                                                 hvdc_loading=np.zeros(nhvdc, dtype=float),
                                                 hvdc_Pf=np.zeros(nhvdc, dtype=float),
                                                 hvdc_Pt=np.zeros(nhvdc, dtype=float),
                                                 vsc_active=vsc_active,
                                                 vsc_loading=np.zeros(nvsc, dtype=float),
                                                 vsc_Pf=np.zeros(nvsc, dtype=float),
                                                 vsc_Pt=np.zeros(nvsc, dtype=float),
                                                 vsc_Qt=np.zeros(nvsc, dtype=float),
                                                 use_flow_based_width=use_flow_based_width,
                                                 min_branch_width=min_branch_width,
                                                 max_branch_width=max_branch_width,
                                                 min_bus_width=min_bus_width,
                                                 max_bus_width=max_bus_width,
                                                 cmap=cmap,
                                                 apply_bus_result_coloring=False)
        else:
            return diagram_widget.colour_results(Sbus=np.zeros(nbus, dtype=complex),
                                                 voltages=np.ones(nbus, dtype=complex),
                                                 bus_active=bus_active,
                                                 Sf=np.zeros(nbr, dtype=complex),
                                                 St=np.zeros(nbr, dtype=complex),
                                                 loadings=np.zeros(nbr, dtype=complex),
                                                 br_active=br_active,
                                                 hvdc_active=hvdc_active,
                                                 hvdc_loading=np.zeros(nhvdc, dtype=float),
                                                 hvdc_Pf=np.zeros(nhvdc, dtype=float),
                                                 hvdc_Pt=np.zeros(nhvdc, dtype=float),
                                                 vsc_active=vsc_active,
                                                 vsc_loading=np.zeros(nvsc, dtype=float),
                                                 vsc_Pf=np.zeros(nvsc, dtype=float),
                                                 vsc_Pt=np.zeros(nvsc, dtype=float),
                                                 vsc_Qt=np.zeros(nvsc, dtype=float),
                                                 use_flow_based_width=use_flow_based_width,
                                                 min_branch_width=min_branch_width,
                                                 max_branch_width=max_branch_width,
                                                 min_bus_width=min_bus_width,
                                                 max_bus_width=max_bus_width,
                                                 cmap=cmap)

    def grid_colour_function(self,
                             diagram_widget: ALL_EDITORS,
                             current_study: SimulationTypes | str | None,
                             t_idx: Union[None, int],
                             allow_popups: bool = True) -> None:
        """
        Colour the schematic or the map
        :param diagram_widget: Diagram where the plotting is made
        :param current_study: Simulation type or label; None uses design colouring.
        :param t_idx: current time step (if None, the snapshot is taken)
        :param allow_popups: if true, messages me pop up
        """
        use_flow_based_width = self.ui.branch_width_based_on_flow_checkBox.isChecked()
        min_branch_width = self.ui.min_branch_size_spinBox.value()
        max_branch_width = self.ui.max_branch_size_spinBox.value()
        min_bus_width = self.ui.min_node_size_spinBox.value()
        max_bus_width = self.ui.max_node_size_spinBox.value()

        cmap = self.ui.palette_comboBox.currentData()
        normalized_current_study: SimulationTypes | None = None
        current_study_label: str
        simulation_type_candidate: SimulationTypes

        # Qt models in the source branch expose the enum value text, while the
        # target branch passes the enum itself. Normalize both public forms at
        # this GUI boundary so the dispatch below remains enum-based.
        if current_study is None:
            normalized_current_study = SimulationTypes.DesignView
            current_study_label = str(SimulationTypes.DesignView.value)
        elif isinstance(current_study, SimulationTypes):
            normalized_current_study = current_study
            current_study_label = str(current_study.value)
        else:
            current_study_label = current_study
            for simulation_type_candidate in SimulationTypes:
                if simulation_type_candidate.value == current_study:
                    normalized_current_study = simulation_type_candidate
                    break
                else:
                    pass

        if normalized_current_study == sim.PowerFlowDriver.tpe:
            if t_idx is None:
                results: sim.PowerFlowResults = self.session.get_results(SimulationTypes.PowerFlow_run)
                self.pf_colouring(diagram_widget=diagram_widget,
                                  results=results,
                                  cmap=cmap,
                                  use_flow_based_width=use_flow_based_width,
                                  min_branch_width=min_branch_width,
                                  max_branch_width=max_branch_width,
                                  min_bus_width=min_bus_width,
                                  max_bus_width=max_bus_width)

            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("only has values for the snapshot"))

        elif normalized_current_study == sim.PowerFlowDriver3Ph.tpe:
            if t_idx is None:
                results: sim.PowerFlowResults3Ph = self.session.get_results(SimulationTypes.PowerFlow3ph_run)
                self.pf_3ph_colouring(diagram_widget=diagram_widget,
                                      results=results,
                                      cmap=cmap,
                                      use_flow_based_width=use_flow_based_width,
                                      min_branch_width=min_branch_width,
                                      max_branch_width=max_branch_width,
                                      min_bus_width=min_bus_width,
                                      max_bus_width=max_bus_width)

            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("only has values for the snapshot"))

        elif normalized_current_study == sim.PowerFlowTimeSeriesDriver.tpe:
            if t_idx is not None:
                drv, results = self.session.power_flow_ts
                if results.S.shape[0] > 0:
                    self.pf_ts_colouring(t_idx=t_idx,
                                         diagram_widget=diagram_widget,
                                         results=results,
                                         cmap=cmap,
                                         use_flow_based_width=use_flow_based_width,
                                         min_branch_width=min_branch_width,
                                         max_branch_width=max_branch_width,
                                         min_bus_width=min_bus_width,
                                         max_bus_width=max_bus_width)
                else:
                    if allow_popups:
                        self.show_warning_toast(self.tr("No time series values to show :/"))
                    else:
                        pass

            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("does not have values for the snapshot"))

        elif normalized_current_study == sim.PowerFlowTimeSeriesDriver3Ph.tpe:
            if t_idx is not None:
                _, results = self.session.power_flow_3ph_ts
                if results.Sbus_A.shape[0] > 0:
                    self.pf_3ph_ts_colouring(t_idx=t_idx,
                                             diagram_widget=diagram_widget,
                                             results=results,
                                             cmap=cmap,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width)
                else:
                    if allow_popups:
                        self.show_warning_toast(self.tr("No time series values to show :/"))
                    else:
                        pass

            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("does not have values for the snapshot"))

        elif normalized_current_study == sim.StateEstimationDriver.tpe:
            if t_idx is None:
                results: sim.StateEstimationResults = self.session.get_results(SimulationTypes.StateEstimation_run)
                self.se_colouring(diagram_widget=diagram_widget,
                                  results=results,
                                  cmap=cmap,
                                  use_flow_based_width=use_flow_based_width,
                                  min_branch_width=min_branch_width,
                                  max_branch_width=max_branch_width,
                                  min_bus_width=min_bus_width,
                                  max_bus_width=max_bus_width)

            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("only has values for the snapshot"))

        elif normalized_current_study == sim.ContinuationPowerFlowDriver.tpe:
            if t_idx is None:
                results: sim.ContinuationPowerFlowResults = self.session.get_results(
                    SimulationTypes.ContinuationPowerFlow_run
                )
                if results.Sbus.shape[0] > 0:
                    self.cpf_colouring(diagram_widget=diagram_widget,
                                       results=results,
                                       cmap=cmap,
                                       use_flow_based_width=use_flow_based_width,
                                       min_branch_width=min_branch_width,
                                       max_branch_width=max_branch_width,
                                       min_bus_width=min_bus_width,
                                       max_bus_width=max_bus_width)
                else:
                    if allow_popups:
                        self.show_warning_toast(self.tr("No continuation power flow values to show :/"))
                    else:
                        pass
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("only has values for the snapshot"))

        elif normalized_current_study == sim.StochasticPowerFlowDriver.tpe:

            # the time is not relevant in this study
            results: sim.StochasticPowerFlowResults = self.session.get_results(
                SimulationTypes.StochasticPowerFlow
            )
            if results.S_points.shape[0] > 0:
                self.spf_colouring(diagram_widget=diagram_widget,
                                   results=results,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)
            else:
                if allow_popups:
                    self.show_warning_toast(self.tr("No stochastic power flow values to show :/"))
                else:
                    pass

        elif normalized_current_study == sim.ShortCircuitDriver.tpe:
            if t_idx is None:
                results: sim.ShortCircuitResults = self.session.get_results(SimulationTypes.ShortCircuit_run)
                self.sc_colouring(diagram_widget=diagram_widget,
                                  results=results,
                                  cmap=cmap,
                                  use_flow_based_width=use_flow_based_width,
                                  min_branch_width=min_branch_width,
                                  max_branch_width=max_branch_width,
                                  min_bus_width=min_bus_width,
                                  max_bus_width=max_bus_width)
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr(" only has values for the snapshot"))

        elif normalized_current_study == sim.OptimalPowerFlowDriver.tpe:
            if t_idx is None:
                results: sim.OptimalPowerFlowResults = self.session.get_results(SimulationTypes.OPF_run)
                self.opf_colouring(diagram_widget=diagram_widget,
                                   results=results,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr(" only has values for the snapshot"))

        elif normalized_current_study == sim.OptimalPowerFlowTimeSeriesDriver.tpe:

            if t_idx is not None:
                results: sim.OptimalPowerFlowTimeSeriesResults = self.session.get_results(
                    SimulationTypes.OPFTimeSeries_run
                )
                if results.Sbus.shape[0] > 0:
                    self.opf_ts_colouring(t_idx=t_idx,
                                          diagram_widget=diagram_widget,
                                          results=results,
                                          cmap=cmap,
                                          use_flow_based_width=use_flow_based_width,
                                          min_branch_width=min_branch_width,
                                          max_branch_width=max_branch_width,
                                          min_bus_width=min_bus_width,
                                          max_bus_width=max_bus_width)
                else:
                    if allow_popups:
                        self.show_warning_toast(self.tr("No OPF time series values to show :/"))
                    else:
                        pass
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("does not have values for the snapshot"))

        elif normalized_current_study == sim.NodalCapacityDriver.tpe:

            _, results = self.session.nodal_capacity_optimization
            self.nc_colouring(diagram_widget=diagram_widget,
                              results=results,
                              cmap=cmap,
                              use_flow_based_width=use_flow_based_width,
                              min_branch_width=min_branch_width,
                              max_branch_width=max_branch_width,
                              min_bus_width=min_bus_width,
                              max_bus_width=max_bus_width)

        elif normalized_current_study == sim.NodalCapacityTimeSeriesDriver.tpe:

            _, results = self.session.nodal_capacity_optimization_ts
            if results.Sbus.shape[0] > 0:
                self.nc_ts_colouring(t_idx=t_idx,
                                     diagram_widget=diagram_widget,
                                     results=results,
                                     cmap=cmap,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width)
            else:
                if allow_popups:
                    self.show_warning_toast(self.tr("No nodal capacity time series values to show :/"))
                else:
                    pass

        elif normalized_current_study == sim.LinearAnalysisDriver.tpe:
            if t_idx is None:
                results: sim.LinearAnalysisResults = self.session.get_results(SimulationTypes.LinearAnalysis_run)
                self.linpf_colouring(diagram_widget=diagram_widget,
                                     results=results,
                                     cmap=cmap,
                                     use_flow_based_width=use_flow_based_width,
                                     min_branch_width=min_branch_width,
                                     max_branch_width=max_branch_width,
                                     min_bus_width=min_bus_width,
                                     max_bus_width=max_bus_width)
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("only has values for the snapshot"))

        elif normalized_current_study == sim.LinearAnalysisTimeSeriesDriver.tpe:
            if t_idx is not None:
                results: sim.LinearAnalysisTimeSeriesResults = self.session.get_results(
                    SimulationTypes.LinearAnalysis_TS_run
                )
                if results.S.shape[0] > 0:
                    self.linpf_ts_colouring(t_idx=t_idx,
                                            diagram_widget=diagram_widget,
                                            results=results,
                                            cmap=cmap,
                                            use_flow_based_width=use_flow_based_width,
                                            min_branch_width=min_branch_width,
                                            max_branch_width=max_branch_width,
                                            min_bus_width=min_bus_width,
                                            max_bus_width=max_bus_width)
                else:
                    if allow_popups:
                        self.show_warning_toast(self.tr("No linear analysis time series values to show :/"))
                    else:
                        pass
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("does not have values for the snapshot"))

        elif normalized_current_study == sim.ContingencyAnalysisDriver.tpe:

            if t_idx is None:
                results: sim.ContingencyAnalysisResults = self.session.get_results(
                    SimulationTypes.ContingencyAnalysis_run
                )
                if results.Sbus.shape[0] > 0:
                    self.con_colouring(diagram_widget=diagram_widget,
                                       results=results,
                                       cmap=cmap,
                                       use_flow_based_width=use_flow_based_width,
                                       min_branch_width=min_branch_width,
                                       max_branch_width=max_branch_width,
                                       min_bus_width=min_bus_width,
                                       max_bus_width=max_bus_width)
                else:
                    if allow_popups:
                        self.show_warning_toast(self.tr("No contingencies to show :/"))
                    else:
                        pass

            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("only has values for the snapshot"))

        elif normalized_current_study == sim.ContingencyAnalysisTimeSeriesDriver.tpe:
            if t_idx is not None:
                results: sim.ContingencyAnalysisTimeSeriesResults = self.session.get_results(
                    SimulationTypes.ContingencyAnalysisTS_run
                )
                if results.S.shape[0] > 0:
                    self.con_ts_colouring(t_idx=t_idx,
                                          diagram_widget=diagram_widget,
                                          results=results,
                                          cmap=cmap,
                                          use_flow_based_width=use_flow_based_width,
                                          min_branch_width=min_branch_width,
                                          max_branch_width=max_branch_width,
                                          min_bus_width=min_bus_width,
                                          max_bus_width=max_bus_width)
                else:
                    if allow_popups:
                        self.show_warning_toast(self.tr("No contingency time series values to show :/"))
                    else:
                        pass
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("does not have values for the snapshot"))

        elif normalized_current_study == sim.AvailableTransferCapacityDriver.tpe:
            self.default_colouring(t_idx=t_idx,
                                   diagram_widget=diagram_widget,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)

        elif normalized_current_study == sim.AvailableTransferCapacityTimeSeriesDriver.tpe:
            self.default_colouring(t_idx=t_idx,
                                   diagram_widget=diagram_widget,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)

        elif normalized_current_study == sim.OptimalNetTransferCapacityDriver.tpe:
            if t_idx is None:
                results: sim.OptimalNetTransferCapacityResults = self.session.get_results(
                    SimulationTypes.OPF_NTC_run
                )
                self.ntc_colouring(diagram_widget=diagram_widget,
                                   results=results,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("only has values for the snapshot"))

        elif normalized_current_study == sim.OptimalNetTransferCapacityTimeSeriesDriver.tpe:
            if t_idx is not None:
                results: sim.OptimalNetTransferCapacityTimeSeriesResults = self.session.get_results(
                    SimulationTypes.OPF_NTC_TS_run
                )
                if results.Sbus.shape[0] > 0:
                    self.ntc_ts_colouring(t_idx=t_idx,
                                          diagram_widget=diagram_widget,
                                          results=results,
                                          cmap=cmap,
                                          use_flow_based_width=use_flow_based_width,
                                          min_branch_width=min_branch_width,
                                          max_branch_width=max_branch_width,
                                          min_bus_width=min_bus_width,
                                          max_bus_width=max_bus_width)
                else:
                    if allow_popups:
                        self.show_warning_toast(self.tr("No NTC time series values to show :/"))
                    else:
                        pass
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("does not have values for the snapshot"))

        elif normalized_current_study == sim.InputsAnalysisDriver.tpe:

            self.default_colouring(t_idx=t_idx,
                                   diagram_widget=diagram_widget,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)

        elif normalized_current_study == SimulationTypes.DesignView:

            self.default_colouring(t_idx=t_idx,
                                   diagram_widget=diagram_widget,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)

        elif normalized_current_study == SimulationTypes.RmsDynamic_run:

            # RMS trajectories expose a typed variable catalogue rather than
            # one network-flow snapshot. Keep the design colouring until a
            # user selects a result-specific RMS projection.
            self.default_colouring(t_idx=t_idx,
                                   diagram_widget=diagram_widget,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)

        elif normalized_current_study == SimulationTypes.NodeGrouping_run:
            if t_idx is None:
                results: sim.OptimalNetTransferCapacityResults = self.session.get_results(
                    SimulationTypes.NodeGrouping_run
                )
                self.node_group_colouring(diagram_widget=diagram_widget,
                                          results=results)
            else:
                if allow_popups:
                    self.show_warning_toast(f"{current_study_label} " + self.tr("only has values for the snapshot"))

        else:
            print("grid_colour_function: <" + current_study_label + "> Not implemented :(")

    def colour_diagrams(self, allow_popups: bool = True) -> None:
        """
        Color the grid now
        :param allow_popups:
        """
        if self.ui.available_results_to_color_comboBox.currentIndex() > -1:

            current_study = self.ui.available_results_to_color_comboBox.currentData()

            offset = self.ui.diagram_step_slider.minimum()
            if offset == -1:
                offset = 0
            val = self.ui.diagram_step_slider.value() - offset

            t_idx = val if val > -1 else None

            for diagram in self.diagram_widgets_list:

                if isinstance(diagram, (SchematicWidget, GridMapWidget)):
                    self.grid_colour_function(diagram_widget=diagram,
                                              current_study=current_study,
                                              t_idx=t_idx,
                                              allow_popups=allow_popups)

    def re_colour_schematic(self):
        """
        Recolour a schematic
        """
        diagram_widget = self.get_selected_diagram_widget()

        use_api_color = self.ui.use_schematic_objects_color_checkBox.isChecked()

        if diagram_widget:

            if isinstance(diagram_widget, SchematicWidget):
                diagram_widget.recolour(use_api_color=use_api_color)

    def set_diagrams_tree_view(self) -> None:
        """
        Create the diagrams' tree view
        """
        mdl = DiagramsTreeModel(self.circuit.diagrams, self.diagram_widgets_list)
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is not None:
            diagrams_view.setModel(mdl)
            if hasattr(diagrams_view, 'expandAll'):
                diagrams_view.expandAll()
            if hasattr(mdl, 'item_dropped'):
                mdl.item_dropped.connect(self._on_diagram_tree_item_dropped)

    def _on_diagram_tree_item_dropped(self, item: Any) -> None:
        """
        Handle post-drop UI updates: expand ancestors and select moved item.
        """
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is None:
            return

        model = diagrams_view.model() if hasattr(diagrams_view, 'model') else None
        if model is None or not hasattr(model, 'index_for_item'):
            return

        index = model.index_for_item(item)
        if index.isValid():
            p_idx = index.parent()
            while p_idx.isValid():
                if hasattr(diagrams_view, 'expand'):
                    diagrams_view.expand(p_idx)
                p_idx = p_idx.parent()
            diagrams_view.setCurrentIndex(index)
            if hasattr(diagrams_view, 'scrollTo'):
                diagrams_view.scrollTo(index)

    def set_diagrams_list_view(self) -> None:
        """
        Backward-compatible alias for set_diagrams_tree_view
        """
        self.set_diagrams_tree_view()

    def get_selected_diagram_folder(self) -> dev.DiagramFolder | None:
        """
        Get the currently selected diagram folder, or the parent folder of the selected diagram,
        or None if at root.
        """
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is None:
            return None

        model = diagrams_view.model() if hasattr(diagrams_view, 'model') else None
        if model is None or not hasattr(model, 'get_item'):
            return None

        indices = diagrams_view.selectedIndexes() if hasattr(diagrams_view, 'selectedIndexes') else []
        selected_index = indices[0] if len(indices) else (diagrams_view.currentIndex() if hasattr(diagrams_view, 'currentIndex') else QtCore.QModelIndex())
        if not selected_index.isValid():
            return None

        item = model.get_item(selected_index)
        if isinstance(item, dev.DiagramFolder):
            return item
        elif isinstance(item, dev.BaseDiagram):
            return item.group
        return None

    def add_diagram_folder(self,
                           parent_folder: dev.DiagramFolder | bool | None = False,
                           folder_name: str | None = None) -> dev.DiagramFolder | None:
        """
        Prompt user for a folder name and create a new DiagramFolder.
        """
        if parent_folder is False:
            parent_folder = self.get_selected_diagram_folder()
        elif not isinstance(parent_folder, dev.DiagramFolder):
            parent_folder = None

        if folder_name is None:
            parent_widget = self if isinstance(self, QtWidgets.QWidget) else None
            name, ok = QtWidgets.QInputDialog.getText(
                parent_widget,
                self.tr("New Folder"),
                self.tr("Folder name:"),
                QtWidgets.QLineEdit.EchoMode.Normal,
                self.tr("New Folder")
            )
            if not ok or not name.strip():
                return None
            folder_name = name.strip()

        new_folder = self.circuit.diagrams.add_folder(folder_or_name=folder_name, parent=parent_folder)
        self.set_diagrams_list_view()

        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is not None:
            model = diagrams_view.model() if hasattr(diagrams_view, 'model') else None
            if model is not None and hasattr(model, 'index_for_item'):
                idx = model.index_for_item(new_folder)
                if idx.isValid():
                    p_idx = idx.parent()
                    while p_idx.isValid():
                        if hasattr(diagrams_view, 'expand'):
                            diagrams_view.expand(p_idx)
                        p_idx = p_idx.parent()
                    diagrams_view.setCurrentIndex(idx)
                    if hasattr(diagrams_view, 'scrollTo'):
                        diagrams_view.scrollTo(idx)

        return new_folder

    def rename_diagram_or_folder(self) -> None:
        """
        Trigger inline rename of the selected diagram or folder in the tree view.
        """
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is None:
            return

        indices = diagrams_view.selectedIndexes()
        selected_index = indices[0] if len(indices) else diagrams_view.currentIndex()
        if selected_index.isValid():
            diagrams_view.edit(selected_index)

    @staticmethod
    def _validate_diagram_widget_entry(diagram_widget: object) -> DIAGRAM_WIDGETS:
        """
        Ensure the diagram widgets list only stores GUI widgets.

        :param diagram_widget: candidate list entry
        :return: validated widget
        """
        if isinstance(diagram_widget, (SchematicWidget, GridMapWidget)):
            return diagram_widget
        else:
            raise TypeError(
                "diagram_widgets_list only accepts SchematicWidget or GridMapWidget entries, "
                f"got {type(diagram_widget).__name__}"
            )

    def _append_diagram_widget(self, diagram_widget: object) -> DIAGRAM_WIDGETS:
        """
        Append a validated diagram widget to the tracked widgets list.

        :param diagram_widget: candidate list entry
        :return: validated widget
        """
        widget = self._validate_diagram_widget_entry(diagram_widget=diagram_widget)
        self.diagram_widgets_list.append(widget)
        return widget

    def dispose_diagram_widget(self, widget: DIAGRAM_WIDGETS) -> None:
        """
        Clear and queue one diagram widget for Qt-side destruction.
        """
        widget.prepare_to_delete()

        # Queue Qt-side destruction on the main thread after clearing scene items now.
        # This avoids orphaned QGraphics objects surviving until later GC/finalization.
        self.ui.schematic_layout.removeWidget(widget)
        widget.setParent(None)
        widget.deleteLater()

    def _create_widget_from_diagram(self, diagram: dev.SchematicDiagram | dev.MapDiagram) -> ALL_EDITORS:
        """
        Create a diagram widget from a stored diagram object.

        :param diagram: stored diagram
        :return: materialized diagram widget
        """
        if isinstance(diagram, dev.SchematicDiagram):
            diagram_widget = SchematicWidget(
                gui=self,
                diagram=diagram,
                default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                time_index=self.get_diagram_slider_index()
            )
            diagram_widget.setStretchFactor(1, 10)
            diagram_widget.center_nodes()
            return diagram_widget
        elif isinstance(diagram, dev.MapDiagram):
            default_tile_source = self.ui.tile_provider_comboBox.currentData()
            tile_source = self.tile_name_dict.get(diagram.tile_source, default_tile_source)
            return GridMapWidget(
                gui=self,
                tile_src=tile_source,
                start_level=diagram.start_level,
                longitude=diagram.longitude,
                latitude=diagram.latitude,
                name=diagram.name,
                diagram=diagram
            )
        else:
            raise Exception("Unknown diagram type")

    def _ensure_diagram_widget_at_index(self, index: int) -> ALL_EDITORS_NONE:
        """
        Return the diagram widget stored at the requested index.

        :param index: diagram row index
        :return: diagram widget or None
        """
        if index < 0 or index >= len(self.diagram_widgets_list):
            return None
        else:
            pass

        entry = self.diagram_widgets_list[index]
        if isinstance(entry, (SchematicWidget, GridMapWidget)):
            return entry
        else:
            return None

    def get_selected_diagram_widget(self) -> ALL_EDITORS_NONE:
        """
        Get the currently selected diagram
        :return: None, DiagramEditorWidget, GridMapWidget, BusViewerGUI
        """
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is None:
            return None

        indices = diagrams_view.selectedIndexes() if hasattr(diagrams_view, 'selectedIndexes') else []
        selected_index = indices[0] if len(indices) else (diagrams_view.currentIndex() if hasattr(diagrams_view, 'currentIndex') else QtCore.QModelIndex())

        if selected_index.isValid():
            model = diagrams_view.model() if hasattr(diagrams_view, 'model') else None
            if model is not None and hasattr(model, 'get_item'):
                item = model.get_item(selected_index)
                if isinstance(item, dev.BaseDiagram):
                    if hasattr(model, 'get_widget_for_diagram'):
                        w = model.get_widget_for_diagram(item)
                        if w is not None:
                            return w
                    for w in self.diagram_widgets_list:
                        if getattr(w, 'diagram', None) is item:
                            return w
                elif isinstance(item, dev.DiagramFolder):
                    return None

            idx = selected_index.row()
            return self._ensure_diagram_widget_at_index(index=idx)
        else:
            return None

    def create_blank_schematic_diagram(self, name: str = "") -> SchematicWidget:
        """
        Create a new schematic widget
        :param name: name of the new schematic
        :return:
        """
        diagram = SchematicDiagram(name=name)

        diagram_widget = SchematicWidget(
            gui=self,
            diagram=diagram,
            default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
            time_index=self.get_diagram_slider_index()
        )

        diagram_widget.setStretchFactor(1, 10)
        diagram_widget.center_nodes()
        self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget, diagram=diagram)
        self.set_diagrams_list_view()
        self.set_diagram_widget(diagram_widget)

        return diagram_widget

    def redraw_current_diagram(self):
        """
        Redraw the currently selected diagram
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget:

            if isinstance(diagram_widget, SchematicWidget):
                # set pointer to the circuit
                diagram = generate_schematic_diagram(buses=self.circuit.get_buses(),
                                                     lines=self.circuit.get_lines(),
                                                     dc_lines=self.circuit.get_dc_lines(),
                                                     transformers2w=self.circuit.get_transformers2w(),
                                                     transformers3w=self.circuit.get_transformers3w(),
                                                     transformers_nw=self.circuit.get_transformers_nw(),
                                                     windings=self.circuit.get_windings(),
                                                     hvdc_lines=self.circuit.get_hvdc(),
                                                     vsc_devices=self.circuit.get_vsc(),
                                                     upfc_devices=self.circuit.get_upfc(),
                                                     series_reactances=self.circuit.get_series_reactances(),
                                                     switches=self.circuit.get_switches(),
                                                     fluid_nodes=self.circuit.get_fluid_nodes(),
                                                     fluid_paths=self.circuit.get_fluid_paths(),
                                                     explode_factor=1.0,
                                                     prog_func=None,
                                                     text_func=None)

                diagram_widget.set_data(diagram=diagram)

            elif isinstance(diagram_widget, GridMapWidget):
                diagram_widget.update_device_sizes(asynchronously=False)

    def set_selected_diagram_on_click(self, index: QtCore.QModelIndex | None = None):
        """
        on list/tree-view click, set the currently selected diagram widget
        """
        if index is not None and isinstance(index, QtCore.QModelIndex) and index.isValid():
            diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
            if diagrams_view is not None:
                model = diagrams_view.model()
                if model is not None and hasattr(model, 'get_item'):
                    item = model.get_item(index)
                    if isinstance(item, dev.DiagramFolder):
                        # Folder clicked, do not switch current diagram view
                        return
                    elif isinstance(item, dev.BaseDiagram):
                        widget = None
                        if hasattr(model, 'get_widget_for_diagram'):
                            widget = model.get_widget_for_diagram(item)
                        if widget is None:
                            for w in self.diagram_widgets_list:
                                if getattr(w, 'diagram', None) is item:
                                    widget = w
                                    break
                        if widget is not None:
                            self.set_diagram_widget(widget)
                        return

        diagram = self.get_selected_diagram_widget()

        if diagram:
            self.set_diagram_widget(diagram)

    def add_complete_bus_branch_diagram_now(self, name='All bus branches') -> SchematicWidget:
        """
        Add a general bus-branch diagram
        :param name: Name of the diagram
        :return DiagramEditorWidget
        """
        diagram = generate_schematic_diagram(buses=self.circuit.get_buses(),
                                             lines=self.circuit.get_lines(),
                                             dc_lines=self.circuit.get_dc_lines(),
                                             transformers2w=self.circuit.get_transformers2w(),
                                             transformers3w=self.circuit.get_transformers3w(),
                                             transformers_nw=self.circuit.get_transformers_nw(),
                                             windings=self.circuit.get_windings(),
                                             hvdc_lines=self.circuit.get_hvdc(),
                                             vsc_devices=self.circuit.get_vsc(),
                                             upfc_devices=self.circuit.get_upfc(),
                                             series_reactances=self.circuit.get_series_reactances(),
                                             switches=self.circuit.get_switches(),
                                             fluid_nodes=self.circuit.get_fluid_nodes(),
                                             fluid_paths=self.circuit.get_fluid_paths(),
                                             explode_factor=1.0,
                                             prog_func=None,
                                             text_func=None,
                                             name=name)

        diagram_widget = SchematicWidget(
            gui=self,
            diagram=diagram,
            default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
            time_index=self.get_diagram_slider_index()
        )

        diagram_widget.setStretchFactor(1, 10)
        diagram_widget.center_nodes()
        self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget, diagram=diagram)
        self.set_diagrams_list_view()
        self.set_diagram_widget(diagram_widget)

        return diagram_widget

    def add_complete_bus_branch_diagram(self) -> None:
        """
        Add a general bus-branch diagram
        """
        self.add_complete_bus_branch_diagram_now(name='All bus-branch')

    def new_bus_branch_diagram_from_selection(self):
        """
        Add a bus-branch diagram of a particular selection of objects
        """
        widget = self.get_selected_diagram_widget()

        if widget:

            if isinstance(widget, SchematicWidget):
                diagram = widget.create_schematic_from_selection()

                widget = SchematicWidget(
                    gui=self,
                    diagram=diagram,
                    default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                    time_index=self.get_diagram_slider_index()
                )

                self.add_diagram_widget_and_diagram(diagram_widget=widget, diagram=diagram)
                self.set_diagrams_list_view()

            elif isinstance(widget, GridMapWidget):
                substation_graphics = widget.get_selected_substations()

                substations = list()
                for graphic_obj in substation_graphics:
                    substations.append(graphic_obj.api_object)

                self.new_bus_branch_diagram_from_substation(substations=substations)

    def add_bus_vicinity_diagram_from_model(self):
        """
        Add a bus vicinity diagram
        :return:
        """
        sel = self.get_selected_db_table_objects()

        if len(sel) > 0:

            sel_obj = sel[0]

            if isinstance(sel_obj, dev.Bus):
                root_bus = sel_obj

            elif isinstance(sel_obj, InjectionParent):
                root_bus = sel_obj.bus

            elif isinstance(sel_obj, BranchParent):
                root_bus = sel_obj.bus_from

            elif isinstance(sel_obj, dev.Transformer3W):
                root_bus = sel_obj.bus0

            elif isinstance(sel_obj, dev.TransformerNW):
                root_bus = sel_obj.bus0

            elif isinstance(sel_obj, dev.VoltageLevel):
                root_bus = None
                buses = self.circuit.get_voltage_level_buses(vl=sel_obj)
                if len(buses) > 0:
                    root_bus = buses[0]

            elif isinstance(sel_obj, dev.Substation):
                root_bus = None
                buses = self.circuit.get_substation_buses(substation=sel_obj)
                if len(buses) > 0:
                    root_bus = buses[0]

            else:
                root_bus = None

            if root_bus is not None:

                dlg = InputNumberDialogue(min_value=1, max_value=99,
                                          default_value=1, is_int=True,
                                          title=self.tr('Vicinity diagram'),
                                          text=self.tr('Select the expansion level'))

                if exec_dialog_safely(dialog=dlg):
                    diagram = make_vicinity_diagram(circuit=self.circuit,
                                                    root_bus=root_bus,
                                                    max_level=dlg.value)

                    diagram_widget = SchematicWidget(
                        gui=self,
                        diagram=diagram,
                        default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                        time_index=self.get_diagram_slider_index()
                    )

                    diagram_widget.center_nodes()
                    self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                        diagram=diagram)
                    self.set_diagrams_list_view()

                    self.show_info_toast(f"{diagram.name} added")
            else:
                self.show_error_toast(f"Could not find any bus")
        else:
            self.show_warning_toast(f"Select a bus")

    def new_bus_branch_diagram_from_bus(self, root_bus: dev.Bus):
        """
        Add a bus-branch diagram of a particular selection of objects
        """
        dlg = InputNumberDialogue(min_value=1, max_value=99,
                                  default_value=1, is_int=True,
                                  title=self.tr('Vicinity diagram'),
                                  text=self.tr("Set the expansion level from {bus_name}").format(
                                      bus_name=root_bus.name,
                                  ))

        if exec_dialog_safely(dialog=dlg):
            diagram = make_vicinity_diagram(circuit=self.circuit,
                                            root_bus=root_bus,
                                            max_level=dlg.value)

            diagram_widget = SchematicWidget(
                gui=self,
                diagram=diagram,
                default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                time_index=self.get_diagram_slider_index()
            )

            diagram_widget.center_nodes()
            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget, diagram=diagram)
            self.set_diagrams_list_view()
            self.show_info_toast(f"{diagram.name} added")

    def new_bus_branch_diagram_from_substation(self, substations: List[dev.Substation]):
        """
        Add a bus-branch diagram of a particular selection of objects
        """

        if len(substations) == 0:
            info_msg(text=self.tr("No substations selected. Please select some substations"),
                     title=self.tr("Substations schematic"))
            return

        selected_buses = self.circuit.get_buses_from_objects(elements=substations,
                                                             dtype=DeviceType.SubstationDevice)

        if len(selected_buses):
            diagram = make_diagram_from_buses(circuit=self.circuit,
                                              buses=selected_buses,
                                              name=substations[0].name + " diagram")

            diagram_widget = SchematicWidget(
                gui=self,
                diagram=diagram,
                default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                time_index=self.get_diagram_slider_index()
            )

            diagram_widget.center_nodes()
            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                diagram=diagram)
            self.set_diagrams_list_view()

            self.show_info_toast(f"{diagram.name} added")
        else:
            if len(substations) == 1:
                info_msg(text=self.tr(
                    "No buses were found associated with the substation {substation_name}"
                ).format(substation_name=substations[0].name),
                         title=self.tr("New schematic from substation"))
            else:
                info_msg(text=self.tr("No buses were found associated with the substations"),
                         title=self.tr("New schematic from substation"))

    def add_substation_to_current_diagram(self, substations: List[dev.Substation]):
        """
        Add a bus-branch diagram of a particular selection of objects
        """

        if len(substations) == 0:
            info_msg(text=self.tr("No substations selected. Please select some substations"),
                     title=self.tr("Substations schematic"))
            return

        diagram_widget = self.get_selected_diagram_widget()
        if not isinstance(diagram_widget, SchematicWidget):
            self.show_error_toast("The current diagram is not a schematic :(")
            return

        selected_buses = self.circuit.get_buses_from_objects(elements=substations,
                                                             dtype=DeviceType.SubstationDevice)

        if len(selected_buses):
            diagram_widget.add_buses(selected_buses)

            self.show_info_toast(f"Substation added")
        else:
            if len(substations) == 1:
                info_msg(text=self.tr(
                    "No buses were found associated with the substation {substation_name}"
                ).format(substation_name=substations[0].name),
                         title=self.tr("New schematic from substation"))
            else:
                info_msg(text=self.tr("No buses were found associated with the substations"),
                         title=self.tr("New schematic from substation"))

    def create_circuit_stored_diagrams(self):
        """
        Create as Widgets the diagrams stored in the circuit
        :return:
        """
        for widget in self.diagram_widgets_list:
            self.dispose_diagram_widget(widget)

        self.diagram_widgets_list.clear()
        self.remove_all_diagram_widgets()

        for diagram in self.circuit.diagrams:
            self._append_diagram_widget(self._create_widget_from_diagram(diagram=diagram))

        self.set_diagrams_list_view()

        if len(self.diagram_widgets_list) > 0:
            first_diagram = self._ensure_diagram_widget_at_index(index=0)
            if first_diagram is not None:
                self.set_diagram_widget(first_diagram)

    def add_map_diagram(self) -> None:
        """
        Adds a Map diagram
        """

        tpes = [
            DeviceType.SubstationDevice,
            DeviceType.LineDevice,
            DeviceType.DCLineDevice,
            DeviceType.HVDCLineDevice,
            DeviceType.GeneratorDevice,
            DeviceType.BatteryDevice,
            DeviceType.LoadDevice,
            DeviceType.StaticGeneratorDevice,
            DeviceType.ExternalGridDevice
        ]

        cmap = self.ui.palette_comboBox.currentData()

        if self.circuit.get_substation_number() > 0:
            # showing this menu only makes sense if there is anything there

            new_se_dlg: CheckListDialogue = CheckListDialogue(
                objects_list=[e.value for e in tpes]
            )

            try:
                exec_dialog_safely(dialog=new_se_dlg)
                show_substations: bool = new_se_dlg.selected(DeviceType.SubstationDevice.value)
                show_lines: bool = new_se_dlg.selected(DeviceType.LineDevice.value)
                show_dc_lines: bool = new_se_dlg.selected(DeviceType.DCLineDevice.value)
                show_hvdc_lines: bool = new_se_dlg.selected(DeviceType.HVDCLineDevice.value)
                show_external_grids: bool = new_se_dlg.selected(DeviceType.ExternalGridDevice.value)
                show_static_generators: bool = new_se_dlg.selected(DeviceType.StaticGeneratorDevice.value)
                show_loads: bool = new_se_dlg.selected(DeviceType.LoadDevice.value)
                show_batteries: bool = new_se_dlg.selected(DeviceType.BatteryDevice.value)
                show_generators: bool = new_se_dlg.selected(DeviceType.GeneratorDevice.value)
            finally:
                delete_dialog_safely(dialog=new_se_dlg)

            diagram = generate_map_diagram(
                substations=self.circuit.get_substations() if show_substations else list(),
                voltage_levels=self.circuit.get_voltage_levels() if show_substations else list(),
                lines=self.circuit.get_lines() if show_lines else list(),
                dc_lines=self.circuit.get_dc_lines() if show_dc_lines else list(),
                hvdc_lines=self.circuit.get_hvdc() if show_hvdc_lines else list(),
                fluid_nodes=self.circuit.get_fluid_nodes(),
                fluid_paths=self.circuit.get_fluid_paths(),
                external_grids=self.circuit.external_grids if show_external_grids else list(),
                static_generators=self.circuit.static_generators if show_static_generators else list(),
                loads=self.circuit.loads if show_loads else list(),
                batteries=self.circuit.batteries if show_batteries else list(),
                generators=self.circuit.generators if show_generators else list(),
                prog_func=None,
                text_func=None,
                name='Map diagram',
                use_flow_based_width=self.ui.branch_width_based_on_flow_checkBox.isChecked(),
                min_branch_width=self.ui.min_branch_size_spinBox.value(),
                max_branch_width=self.ui.max_branch_size_spinBox.value(),
                min_bus_width=self.ui.min_node_size_spinBox.value(),
                max_bus_width=self.ui.max_node_size_spinBox.value(),
                arrow_size=self.ui.arrow_size_size_spinBox.value(),
                palette=cmap,
                default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value()
            )
        else:
            # self.show_warning_toast("No substations to draw...")
            diagram = MapDiagram(name='Map diagram')

        # set other default properties of the diagram
        diagram.tile_source = self.ui.tile_provider_comboBox.currentData().tile_set_name
        diagram.start_level = 5

        # select the tile source
        tile_source = self.ui.tile_provider_comboBox.currentData()

        # create the map widget
        map_widget = GridMapWidget(gui=self,
                                   tile_src=tile_source,
                                   start_level=diagram.start_level,
                                   longitude=diagram.longitude,
                                   latitude=diagram.latitude,
                                   name=diagram.name,
                                   diagram=diagram)

        self.add_diagram_widget_and_diagram(diagram_widget=map_widget, diagram=diagram)
        self.set_diagrams_list_view()
        self.set_diagram_widget(widget=map_widget)
        self.show_info_toast(f"{diagram.name} added")

    def add_diagram_widget_and_diagram(self,
                                       diagram_widget: DIAGRAM_WIDGETS,
                                       diagram: Union[dev.SchematicDiagram, dev.MapDiagram],
                                       folder: dev.DiagramFolder | None = None):
        """
        Add diagram widget, it also adds the diagram to the circuit for later
        :param diagram_widget: Diagram widget object
        :param diagram: SchematicDiagram or MapDiagram
        :param folder: Optional parent DiagramFolder
        """
        if folder is None and getattr(diagram, 'group', None) is not None:
            folder = diagram.group

        # add the widget pointer
        self._append_diagram_widget(diagram_widget)

        # add the diagram to the circuit
        self.circuit.add_diagram(diagram, folder=folder)

    def remove_diagram(self):
        """
        Remove one or more selected diagrams or folders
        """
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is None:
            return

        model = diagrams_view.model()
        if model is None:
            return

        selected_indexes = diagrams_view.selectedIndexes()
        if not selected_indexes:
            return

        # Gather unique selected items
        selected_items = []
        if hasattr(model, 'get_item'):
            seen_idtags = set()
            for idx in selected_indexes:
                if idx.isValid():
                    item = model.get_item(idx)
                    if item is not None and getattr(item, 'idtag', None) not in seen_idtags:
                        seen_idtags.add(getattr(item, 'idtag', None))
                        selected_items.append(item)
        else:
            selected_rows = sorted({idx.row() for idx in selected_indexes})
            for r in selected_rows:
                if 0 <= r < len(self.diagram_widgets_list):
                    selected_items.append(self.diagram_widgets_list[r].diagram)

        if not selected_items:
            return

        if len(selected_items) == 1:
            item = selected_items[0]
            if isinstance(item, dev.DiagramFolder):
                question = self.tr("Are you sure that you want to delete folder '{0}' and all its contents?").format(item.name)
            else:
                question = "Are you sure that you want to delete " + str(item.name) + "?"
        else:
            question = f"Are you sure that you want to delete {len(selected_items)} selected items?"

        ok = yes_no_question(question, self.tr("Remove diagram"))
        if not ok:
            return

        diagrams_to_delete = set()
        folders_to_delete = set()

        for item in selected_items:
            if isinstance(item, dev.DiagramFolder):
                folders_to_delete.add(item)
                for d in item.get_all_diagrams():
                    diagrams_to_delete.add(d)
            elif isinstance(item, dev.BaseDiagram):
                diagrams_to_delete.add(item)

        remaining_widgets = []
        for widget in self.diagram_widgets_list:
            if getattr(widget, 'diagram', None) in diagrams_to_delete:
                self.dispose_diagram_widget(widget)
            else:
                remaining_widgets.append(widget)
        self.diagram_widgets_list = remaining_widgets

        for folder in folders_to_delete:
            self.circuit.diagrams.remove_folder(folder)
        for d in diagrams_to_delete:
            self.circuit.remove_diagram(d)

        self.remove_all_diagram_widgets()
        self.set_diagrams_list_view()

        if len(self.diagram_widgets_list) > 0:
            target_widget = self.diagram_widgets_list[0]
            self.set_diagram_widget(target_widget)

    def duplicate_diagram(self):
        """
        Duplicate the selected diagram
        """
        diagram_widget = self.get_selected_diagram_widget()
        if diagram_widget is not None:
            parent_folder = getattr(diagram_widget.diagram, 'group', None)
            new_diagram_widget = diagram_widget.copy()

            self.add_diagram_widget_and_diagram(diagram_widget=new_diagram_widget,
                                                diagram=new_diagram_widget.diagram,
                                                folder=parent_folder)

            # refresh the list view
            self.set_diagrams_list_view()
            self.set_diagram_widget(widget=new_diagram_widget)
        else:
            info_msg(text=self.tr("Select a valid diagram"), title=self.tr("Duplicate diagram"))

    def remove_all_diagrams(self) -> None:
        """
        Remove all diagrams and their widgets
        """
        for widget in self.diagram_widgets_list:
            self.dispose_diagram_widget(widget)

        self.diagram_widgets_list.clear()
        self.remove_all_diagram_widgets()
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is not None:
            diagrams_view.setModel(None)

    def remove_all_diagram_widgets(self) -> None:
        """
        Remove all diagram widgets from the container
        """
        # delete all widgets from the layout
        for i in reversed(range(self.ui.schematic_layout.count())):
            # get the widget
            widget_to_remove = self.ui.schematic_layout.itemAt(i).widget()

            # delete it from the layout list
            self.ui.schematic_layout.removeWidget(widget_to_remove)

            # Hide the widget before detaching it so Qt does not expose it as a top-level window.
            widget_to_remove.hide()

            # detach it from the gui
            widget_to_remove.setParent(None)

    def set_diagram_widget(self, widget: ALL_EDITORS):
        """
        Set the current diagram in the container
        :param widget: DiagramEditorWidget, GridMapWidget, BusViewerGUI
        """
        self.remove_all_diagram_widgets()

        # add the new diagram
        self.ui.schematic_layout.addWidget(widget)
        widget.show()

        # set the alignment
        self.ui.diagram_selection_splitter.setStretchFactor(0, 10)
        self.ui.diagram_selection_splitter.setStretchFactor(1, 1)

        # set the selected index
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is not None:
            model = diagrams_view.model()
            if model is not None:
                if hasattr(model, 'index_for_item') and hasattr(widget, 'diagram'):
                    index = model.index_for_item(widget.diagram)
                else:
                    try:
                        row = self.diagram_widgets_list.index(widget)
                        index = model.index(row, 0)
                    except (ValueError, Exception):
                        index = QtCore.QModelIndex()
                if index.isValid():
                    diagrams_view.setCurrentIndex(index)
                    if hasattr(diagrams_view, 'scrollTo'):
                        diagrams_view.scrollTo(index)

        # set the properties
        self._enable_setting_auto_upgrade = False
        self.ui.branch_width_based_on_flow_checkBox.setChecked(widget.diagram.use_flow_based_width)
        self.ui.min_branch_size_spinBox.setValue(widget.diagram.min_branch_width)
        self.ui.max_branch_size_spinBox.setValue(widget.diagram.max_branch_width)
        self.ui.min_node_size_spinBox.setValue(widget.diagram.min_bus_width)
        self.ui.max_node_size_spinBox.setValue(widget.diagram.max_bus_width)
        self.ui.arrow_size_size_spinBox.setValue(widget.diagram.arrow_size)
        self.ui.use_schematic_objects_color_checkBox.setChecked(widget.diagram.use_api_colors)
        self.ui.palette_comboBox.setCurrentIndex(self.cmap_index_dict.get(widget.diagram.palette, 0))

        if isinstance(widget, GridMapWidget):
            self.ui.tile_provider_comboBox.setEnabled(True)
            self.ui.tile_provider_comboBox.setCurrentIndex(self.tile_index_dict[widget.map.tile_src.tile_set_name])
        else:
            self.ui.tile_provider_comboBox.setEnabled(False)

        self.ui.defaultBusVoltageSpinBox.setValue(widget.diagram.default_bus_voltage)
        self._enable_setting_auto_upgrade = True

    def diagrams_time_slider_change(self) -> None:
        """
        After releasing the time slider, do something
        """
        self.update_diagram_time_slider_texts()
        idx = self.ui.diagram_step_slider.value()

        # correct to interpret -1 as None
        idx2 = idx if idx > -1 else None

        # modify the time index in all the bus-branch diagrams
        for diagram in self.diagram_widgets_list:
            if isinstance(diagram, SchematicWidget):
                diagram.set_time_index(time_index=idx2)
            if isinstance(diagram, GridMapWidget):
                diagram.set_time_index(time_index=idx2)

    def update_diagram_time_slider_texts(self):
        """
        Update the slider text label as it is moved
        :return:
        """
        idx = self.ui.diagram_step_slider.value()

        if idx > -1:
            val = f"[{idx}] {self.circuit.time_profile[idx]}"
            self.ui.schematic_step_label.setText(val)
        else:
            self.ui.schematic_step_label.setText(f"Snapshot [{self.circuit.get_snapshot_time_str()}]")

    def objects_time_slider_change(self) -> None:
        """
        After releasing the time slider, do something
        """
        self.objects_diagram_time_slider_texts()

        idx = self.ui.db_step_slider.value()

        # correct to interpret -1 as None
        idx2 = idx if idx > -1 else None

        # modify the time index in the current DB objects model
        mdl: ObjectModelFilterProxy | None = self.get_current_objects_model_view()
        if isinstance(mdl, ObjectModelFilterProxy):
            mdl.set_time_index(time_index=idx2)

    def objects_diagram_time_slider_texts(self):
        """
        Update the slider text label as it is moved
        :return:
        """
        idx = self.ui.db_step_slider.value()

        if idx > -1:
            val = f"[{idx}] {self.circuit.time_profile[idx]}"
            self.ui.db_step_label.setText(val)
        else:
            self.ui.db_step_label.setText(f"Snapshot [{self.circuit.get_snapshot_time_str()}]")

    def take_picture(self):
        """
        Save the schematic
        :return:
        """
        diagram = self.get_selected_diagram_widget()
        if diagram is not None:
            if isinstance(diagram, (SchematicWidget, GridMapWidget)):

                # declare the allowed file types
                files_types = ("Scalable Vector Graphics (*.svg);;"
                               "Portable Network Graphics (*.png)")

                f_name = str(os.path.join(self.project_directory, self.ui.grid_name_line_edit.text()))

                # call dialog to select the file
                filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(
                    self,
                    self.tr('Save image file'),
                    f_name,
                    self.tr(files_types),
                )

                if filename != "":
                    if 'svg' in type_selected:
                        if not filename.endswith('.svg'):
                            filename += ".svg"

                    elif 'png' in type_selected:
                        if not filename.endswith('.png'):
                            filename += ".png"

                    # save
                    diagram.take_picture(filename)

    def record_video(self):
        """
        Save the schematic
        :return:
        """
        if self.circuit.has_time_series:
            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, (SchematicWidget, GridMapWidget)):

                    # declare the allowed file types
                    files_types = "MP4 (*.mp4);;AVI (*.avi);;"

                    f_name = str(os.path.join(self.project_directory, self.ui.grid_name_line_edit.text()))

                    # call dialog to select the file
                    filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(
                        self,
                        self.tr('Save video file'),
                        f_name,
                        self.tr(files_types),
                    )

                    if filename != "":
                        if type_selected == "MP4 (*.mp4)" and not filename.endswith('.mp4'):
                            filename += ".mp4"

                        if type_selected == "AVI (*.avi)" and not filename.endswith('.avi'):
                            filename += ".avi"

                        # self.thread_pool.start(lambda: self.record_video_now(filename, diagram))
                        self.video_thread = VideoExportWorker(
                            filename=filename,
                            diagram=diagram,
                            fps=self.ui.fps_spinBox.value(),
                            start_idx=self.get_simulation_start(),
                            end_idx=self.get_simulation_end(),
                            current_study=self.ui.available_results_to_color_comboBox.currentData(),
                            grid_colour_function=self.grid_colour_function
                        )
                        self.video_thread.progress_signal.connect(self.ui.progressBar.setValue)
                        self.video_thread.progress_text.connect(self.ui.progress_label.setText)
                        self.video_thread.done_signal.connect(self.post_video_export)
                        self.video_thread.run()  # we cannot run another thread accessing the main thread objects...
            else:
                self.show_error_toast("There is no diagram selected")

        else:
            self.show_error_toast("There are no time series")

    def post_video_export(self):
        """

        :return:
        """
        self.video_thread.diagram.remove_video_time_label()
        if self.video_thread.logger.has_logs():
            self.show_logs(self.video_thread.logger, "Video export")

    def set_xy_from_lat_lon(self):
        """
        Get the x, y coordinates of the buses from their latitude and longitude
        """
        if self.circuit.valid_for_simulation():

            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, SchematicWidget):

                    if yes_no_question(self.tr("All buses will be positioned to a 2D plane projection of their "
                                       "latitude and longitude. This updates the current diagram and the "
                                       "stored bus x, y, so diagrams created afterwards use the new positions. "
                                       "Are you sure of this?")):
                        diagram.fill_xy_from_lat_lon(destructive=True)
                        diagram.center_nodes()
                else:
                    self.show_warning_toast("No schematic diagram selected!")
            else:
                self.show_warning_toast("No diagram selected!")

    def set_big_bus_marker(self, buses: List[dev.Bus], color: QtGui.QColor):
        """
        Set a big marker at the selected buses
        :param buses: list of Bus objects
        :param color: colour to use
        """

        for diagram in self.diagram_widgets_list:

            if isinstance(diagram, SchematicWidget):
                diagram.set_big_bus_marker(buses=buses, color=color)

    def set_big_bus_marker_colours(self,
                                   buses: List[dev.Bus],
                                   colors: Iterable[QtGui.QColor],
                                   tool_tips: Union[None, List[str]] = None):
        """
        Set a big marker at the selected buses with the matching colours
        :param buses: list of Bus objects
        :param colors: list of colour to use
        :param tool_tips: list of tool tips (optional)
        """

        for diagram in self.diagram_widgets_list:

            if isinstance(diagram, SchematicWidget):
                diagram.set_big_bus_marker_colours(buses=buses,
                                                   colors=colors,
                                                   tool_tips=tool_tips)

    def clear_big_bus_markers(self):
        """
        Clear big markers at the selected buses
        """

        for diagram in self.diagram_widgets_list:
            if isinstance(diagram, SchematicWidget):
                diagram.clear_big_bus_markers()

    def delete_selected_from_the_diagram(self):
        """
        Prompt to delete_with_dialogue the selected buses from the current diagram
        """

        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            diagram_widget.delete_selected_from_widget(delete_from_db=False)

        elif isinstance(diagram_widget, GridMapWidget):
            diagram_widget.delete_selected_from_widget(delete_from_db=False)

    def delete_selected_diagram_widgets(self):
        """
        Prompt to delete the selected elements from the current diagram and (optionally) the database
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            diagram_widget.delete_selected_from_widget(delete_from_db=True)

        elif isinstance(diagram_widget, GridMapWidget):
            diagram_widget.delete_selected_from_widget(delete_from_db=True)

        else:
            self.show_error_toast("delete_selected_diagram_widgets: Unsupported widget :(")

    def try_to_fix_buses_location(self):
        """
        Try to fix the location of the buses
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            selected_buses = diagram_widget.get_selected_buses()
            if len(selected_buses) > 0:
                diagram_widget.try_to_fix_buses_location(buses_selection=selected_buses)
            else:
                info_msg(self.tr('Choose some elements from the schematic'), self.tr('Fix buses locations'))

    def get_selected_devices(self) -> List[ALL_DEV_TYPES]:
        """
        Get the selected investment devices
        :return: list of selected devices
        """

        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, SchematicWidget):
            lst = diagram._get_selection_api_objects()
        elif isinstance(diagram, GridMapWidget):
            lst = list()
        else:
            lst = list()

        return lst

    def add_selected_to_contingency(self):
        """
        Add contingencies from the schematic selection
        """
        if self.circuit.valid_for_simulation():

            # get the selected buses
            selected = self.get_selected_devices()

            if len(selected) > 0:
                names = [elm.type_name + ": " + elm.name for elm in selected]
                group_text = "Contingency " + selected[0].name
                contingency_checks_diag: CheckListDialogue = CheckListDialogue(objects_list=names,
                                                                               title="Add contingency",
                                                                               ask_for_group_name=True,
                                                                               group_label="Contingency name",
                                                                               group_text=group_text)
                contingency_checks_diag.setModal(True)
                try:
                    exec_dialog_safely(dialog=contingency_checks_diag)
                    is_accepted: bool = contingency_checks_diag.is_accepted
                    selected_indices: list[int] = list(contingency_checks_diag.selected_indices)
                    selected_group_text: str = contingency_checks_diag.get_group_text()
                finally:
                    delete_dialog_safely(dialog=contingency_checks_diag)

                if is_accepted:

                    group = dev.ContingencyGroup(idtag=None,
                                                 name=selected_group_text,
                                                 category="single" if len(selected) == 1 else "multiple")
                    self.circuit.add_contingency_group(group)

                    for i in selected_indices:
                        elm = selected[i]
                        con = dev.Contingency(device=elm,
                                              code=elm.code,
                                              name="Contingency " + elm.name,
                                              prop=ContingencyOperationTypes.Active,
                                              value=0,
                                              group=group)
                        self.circuit.add_contingency(con)
                else:
                    pass
            else:
                info_msg(self.tr("Select some elements in the schematic first"), self.tr("Add selected to contingency"))

    def add_selected_to_remedial_action(self):
        """
        Add contingencies from the schematic selection
        """
        if self.circuit.valid_for_simulation():

            # get the selected buses
            selected = self.get_selected_devices()

            if len(selected) > 0:
                names = [elm.type_name + ": " + elm.name for elm in selected]
                group_text = "RA " + selected[0].name
                ra_checks_diag: CheckListDialogue = CheckListDialogue(objects_list=names,
                                                                      title="Add remedial action",
                                                                      ask_for_group_name=True,
                                                                      group_label="Remedial action name",
                                                                      group_text=group_text)
                ra_checks_diag.setModal(True)
                try:
                    exec_dialog_safely(dialog=ra_checks_diag)
                    is_accepted: bool = ra_checks_diag.is_accepted
                    selected_indices: list[int] = list(ra_checks_diag.selected_indices)
                    selected_group_text: str = ra_checks_diag.get_group_text()
                finally:
                    delete_dialog_safely(dialog=ra_checks_diag)

                if is_accepted:

                    ra_group = dev.RemedialActionGroup(idtag=None,
                                                       name=selected_group_text,
                                                       category="single" if len(selected) == 1 else "multiple")
                    self.circuit.add_remedial_action_group(ra_group)

                    for i in selected_indices:
                        elm = selected[i]
                        ra = dev.RemedialAction(device=elm,
                                                code=elm.code,
                                                name="RA " + elm.name,
                                                prop=ContingencyOperationTypes.Active,
                                                value=0,
                                                group=ra_group)
                        self.circuit.add_remedial_action(ra)
                else:
                    pass
            else:
                info_msg(self.tr("Select some elements in the schematic first"), self.tr("Add selected to remedial action"))

    def add_selected_to_investment(self) -> None:
        """
        Add contingencies from the schematic selection
        """
        if self.circuit.valid_for_simulation():

            # get the selected investment devices
            selected = self.get_selected_devices()

            if len(selected) > 0:

                group_name = "Investment " + str(len(self.circuit.get_contingency_groups()))

                # launch selection dialogue to add/delete from the selection
                names = [elm.type_name + ": " + elm.name for elm in selected]
                investment_checks_diag: CheckListDialogue = CheckListDialogue(objects_list=names,
                                                                              title="Add investment",
                                                                              ask_for_group_name=True,
                                                                              group_label="Investment name",
                                                                              group_text=group_name)
                investment_checks_diag.setModal(True)
                try:
                    exec_dialog_safely(dialog=investment_checks_diag)
                    is_accepted: bool = investment_checks_diag.is_accepted
                    selected_indices: list[int] = list(investment_checks_diag.selected_indices)
                    selected_group_text: str = investment_checks_diag.get_group_text()
                finally:
                    delete_dialog_safely(dialog=investment_checks_diag)

                if is_accepted:

                    # create a new investments group
                    group = dev.InvestmentsGroup(idtag=None,
                                                 name=selected_group_text,
                                                 category="single" if len(selected) == 1 else "multiple")
                    self.circuit.add_investments_group(group)

                    # add the selection as investments to the group
                    for i in selected_indices:
                        elm = selected[i]
                        con = dev.Investment(device=elm,
                                             code=elm.code,
                                             name=elm.type_name + ": " + elm.name,
                                             CAPEX=0.0,
                                             group=group)
                        self.circuit.add_investment(con)
                else:
                    pass
            else:
                info_msg(self.tr("Select some elements in the schematic first"), self.tr("Add selected to investment"))

    def add_rms_event_to_selected(self) -> None:
        """Open the general dynamic-events workspace preferring RMS events.

        :return: None.
        """
        self._open_dynamic_events_editor(DynamicSimulationMode.RMS)

    def add_emt_event_to_selected(self) -> None:
        """Open the general dynamic-events workspace preferring EMT events.

        :return: None.
        """
        self._open_dynamic_events_editor(DynamicSimulationMode.EMT)

    def _open_dynamic_events_editor(self, mode: DynamicSimulationMode) -> None:
        """Open the requested events content in the unified dynamic workspace.

        Events are circuit-wide assets, so the selected diagram elements do not
        constrain the editor contents or determine its tab identity.

        :param mode: RMS or EMT family preferred by the triggering action.
        :return: None.
        """
        if not self.circuit.valid_for_simulation():
            return
        else:
            self.open_dynamic_events(
                circuit=self.circuit,
                mode=mode,
                show_tree=False,
            )

    def add_short_circuit_events(self):
        """

        :return:
        """
        if self.circuit.valid_for_simulation():

            # get the selected investment devices
            selected: List[Tuple[int, dev.Bus, BusGraphicItem | None]] = self.get_diagram_selected_buses()

            if len(selected) > 0:

                sc_selector_dialogue: ShortCircuitSelector = ShortCircuitSelector()
                try:
                    exec_dialog_safely(dialog=sc_selector_dialogue)

                    if sc_selector_dialogue.was_accepted:

                        for _, bus, _ in selected:
                            z_pu: complex = sc_selector_dialogue.get_impedance_pu(Sbase=self.circuit.Sbase,
                                                                                  Vbase=bus.Vnom)
                            sc = dev.ShortCircuitEvent(
                                name=f"{bus.name} {sc_selector_dialogue.fault.value}",
                                device=bus,
                                fault_type=sc_selector_dialogue.fault,
                                method=sc_selector_dialogue.method,
                                phases=sc_selector_dialogue.phases,
                                r_fault=z_pu.real,
                                x_fault=z_pu.imag
                            )

                            self.circuit.add_short_circuit_event(sc)

                        self.show_info_toast(f"{len(selected)} short circuit events added!")
                    else:
                        pass
                finally:
                    delete_dialog_safely(dialog=sc_selector_dialogue)
            else:
                self.show_warning_toast("Select some buses in the diagram!")

    def select_buses_by_property(self, prop: str):
        """
        Select the current diagram buses by prop
        :param prop: area, zone, country
        """
        if prop == 'area':
            object_select_window: ObjectSelectWindow = ObjectSelectWindow(title='Area',
                                                                          object_list=self.circuit.areas,
                                                                          parent=self)
            object_select_window.setModal(True)
            try:
                exec_dialog_safely(dialog=object_select_window)
                selected_object: object | None = object_select_window.selected_object
            finally:
                delete_dialog_safely(dialog=object_select_window)

            if selected_object is not None:

                for k, bus, graphic_obj in self.get_current_diagram_buses():
                    if bus.area == selected_object:
                        graphic_obj.setSelected(True)
                    else:
                        pass
            else:
                pass

        elif prop == 'country':
            object_select_window = ObjectSelectWindow(title='country',
                                                      object_list=self.circuit.countries,
                                                      parent=self)
            object_select_window.setModal(True)
            try:
                exec_dialog_safely(dialog=object_select_window)
                selected_object = object_select_window.selected_object
            finally:
                delete_dialog_safely(dialog=object_select_window)

            if selected_object is not None:
                for k, bus, graphic_obj in self.get_current_diagram_buses():
                    if bus.country == selected_object:
                        graphic_obj.setSelected(True)
                    else:
                        pass
            else:
                pass

        elif prop == 'zone':
            object_select_window = ObjectSelectWindow(title='Zones',
                                                      object_list=self.circuit.zones,
                                                      parent=self)
            object_select_window.setModal(True)
            try:
                exec_dialog_safely(dialog=object_select_window)
                selected_object = object_select_window.selected_object
            finally:
                delete_dialog_safely(dialog=object_select_window)

            if selected_object is not None:
                for k, bus, graphic_obj in self.get_current_diagram_buses():
                    if bus.zone == selected_object:
                        graphic_obj.setSelected(True)
                    else:
                        pass
            else:
                pass
        else:
            error_msg(self.tr("Unrecognized option {option_name}").format(option_name=str(prop)))
            return

    def select_buses_by(self):
        """
        Select buses by...
        launched a dialogue to select the category, and then another to select the element
        """
        object_select_window: ListSelectWindow = ListSelectWindow(title='Area',
                                                                  elements=["area", "zone", "country"],
                                                                  parent=self)
        object_select_window.setModal(True)
        try:
            exec_dialog_safely(dialog=object_select_window)
            selected_object: object | None = object_select_window.selected_object
        finally:
            delete_dialog_safely(dialog=object_select_window)

        if selected_object is not None:
            self.select_buses_by_property(str(selected_object))
        else:
            pass

    def set_selected_bus_property(self, prop: str):
        """

        :param prop:
        :return:
        """
        if prop == 'area':
            object_select_window = ObjectSelectWindow(title='Area',
                                                      object_list=self.circuit.areas,
                                                      parent=self)
            object_select_window.setModal(True)
            try:
                exec_dialog_safely(dialog=object_select_window)
                selected_object = object_select_window.selected_object
            finally:
                delete_dialog_safely(dialog=object_select_window)

            if selected_object is not None:
                for k, bus, graphic_obj in self.get_diagram_selected_buses():
                    bus.area = selected_object
                    print('Set {0} into bus {1}'.format(selected_object.name, bus.name))
            else:
                pass

        elif prop == 'country':
            object_select_window = ObjectSelectWindow(title='country',
                                                      object_list=self.circuit.countries,
                                                      parent=self)
            object_select_window.setModal(True)
            try:
                exec_dialog_safely(dialog=object_select_window)
                selected_object = object_select_window.selected_object
            finally:
                delete_dialog_safely(dialog=object_select_window)

            if selected_object is not None:
                for k, bus, graphic_obj in self.get_diagram_selected_buses():
                    bus.country = selected_object
                    print('Set {0} into bus {1}'.format(selected_object.name, bus.name))
            else:
                pass

        elif prop == 'zone':
            object_select_window = ObjectSelectWindow(title='Zones',
                                                      object_list=self.circuit.zones,
                                                      parent=self)
            object_select_window.setModal(True)
            try:
                exec_dialog_safely(dialog=object_select_window)
                selected_object = object_select_window.selected_object
            finally:
                delete_dialog_safely(dialog=object_select_window)

            if selected_object is not None:
                for k, bus, graphic_pbj in self.get_diagram_selected_buses():
                    bus.zone = selected_object
                    print('Set {0} into bus {1}'.format(selected_object.name, bus.name))
            else:
                pass
        else:
            error_msg(self.tr("Unrecognized option {option_name}").format(option_name=str(prop)))
            return

    def color_buses_by(self):
        """
        Launch the bus coloring
        """
        object_select_window = ListSelectWindow(title='Select association',
                                                elements=["area", "zone", "country", "substation"],
                                                parent=self)
        object_select_window.setModal(True)
        try:
            exec_dialog_safely(dialog=object_select_window)
            selected_object = object_select_window.selected_object
        finally:
            delete_dialog_safely(dialog=object_select_window)
        any_op = False

        for k, bus, graphic_obj in self.get_current_diagram_buses():

            if selected_object == "area":
                hex_color = bus.area.color if bus.area is not None else None

            elif selected_object == "zone":
                hex_color = bus.zone.color if bus.zone is not None else None

            elif selected_object == "country":
                hex_color = bus.country.color if bus.country is not None else None

            elif selected_object == "substation":
                hex_color = bus.substation.color if bus.substation is not None else None

            else:
                hex_color = None

            if hex_color is not None:
                graphic_obj.color = QtGui.QBrush(QtGui.QColor(hex_color))
                graphic_obj.set_tile_color(graphic_obj.color)
                any_op = True

        if not any_op:
            self.show_warning_toast(
                f"Nothing coloured, check the buses {selected_object} property."
            )
        else:
            pass

    def color_substations_by(self):
        """
        Launch substation coloring
        """

        object_select_window = ListSelectWindow(title='Select association',
                                                elements=["area", "zone", "country",
                                                          "community", "region", "municipality",
                                                          "substation"],
                                                parent=self)
        object_select_window.setModal(True)
        try:
            exec_dialog_safely(dialog=object_select_window)
            selected_object = object_select_window.selected_object
        finally:
            delete_dialog_safely(dialog=object_select_window)

        if selected_object is not None:
            any_op = False

            for k, substation, graphic_obj in self.get_current_diagram_substations():

                if selected_object == "area":
                    hex_color = substation.area.color if substation.area is not None else None

                elif selected_object == "zone":
                    hex_color = substation.zone.color if substation.zone is not None else None

                elif selected_object == "country":
                    hex_color = substation.country.color if substation.country is not None else None

                elif selected_object == "community":
                    hex_color = substation.community.color if substation.community is not None else None

                elif selected_object == "region":
                    hex_color = substation.region.color if substation.region is not None else None

                elif selected_object == "municipality":
                    hex_color = substation.municipality.color if substation.municipality is not None else None

                elif selected_object == "substation":
                    hex_color = substation.color
                else:
                    hex_color = None

                if hex_color is not None:
                    color = QtGui.QColor(hex_color)
                    graphic_obj.color = color
                    graphic_obj.border_color = color
                    graphic_obj.color_widget(
                        inner_color=color,
                        border_color=color
                    )
                    any_op = True

            if not any_op:
                self.show_warning_toast(
                    f"Nothing coloured, check the substations {selected_object} property."
                )
            else:
                pass
        else:
            pass

    def default_voltage_change(self):
        """
        When the default voltage changes, update all the diagrams
        """
        val = self.ui.defaultBusVoltageSpinBox.value()

        for diagram in self.diagram_widgets_list:

            if isinstance(diagram, SchematicWidget):
                diagram.default_bus_voltage = val

            elif isinstance(diagram, GridMapWidget):
                pass

    def delete_from_all_diagrams(self, elements: List[ALL_DEV_TYPES]) -> None:
        """
        Delete elements from all editors
        :param elements: list of devices to delete_with_dialogue from the graphics editors
        :return:
        """
        for diagram_widget in self.diagram_widgets_list:
            if isinstance(diagram_widget, SchematicWidget):
                diagram_widget.delete_diagram_elements(elements)

            elif isinstance(diagram_widget, GridMapWidget):
                pass

    def remove_dead_graphics_from_all_diagrams(self) -> None:
        """
        Remove diagram graphics whose API object no longer exists in the active circuit.

        :return: None.
        """
        for diagram_widget in self.diagram_widgets_list:
            if isinstance(diagram_widget, (SchematicWidget, GridMapWidget)):
                self.remove_dead_graphics_from_diagram(diagram_widget=diagram_widget)
            else:
                pass

    def remove_dead_graphics_from_diagram(self, diagram_widget: SchematicWidget | GridMapWidget) -> None:
        """
        Remove stale graphics from one diagram after an in-place database mutation.

        :param diagram_widget: Diagram to synchronize with the active circuit.
        :return: None.
        """
        for device_tpe, graphics_dict in list(diagram_widget.graphics_manager.graphic_dict.items()):
            try:
                live_elements: List[ALL_DEV_TYPES] = list(self.circuit.get_elements_by_type(device_type=device_tpe))
            except Exception:
                live_idtags: set[str] | None = None
            else:
                live_idtags = {element.idtag for element in live_elements}

            if live_idtags is None:
                stale_idtags: List[str] = list()
            else:
                stale_idtags = [idtag for idtag in list(graphics_dict.keys()) if idtag not in live_idtags]

            for idtag in stale_idtags:
                graphic_object: object | None = graphics_dict.get(idtag, None)

                if graphic_object is None:
                    del graphics_dict[idtag]
                elif shiboken6.isValid(graphic_object):
                    del graphics_dict[idtag]
                    try:
                        diagram_widget._remove_from_scene(graphic_object=graphic_object)
                    except Exception:
                        pass
                    else:
                        pass
                else:
                    del graphics_dict[idtag]

    def search_diagram(self):
        """
        Search elements by name, code or idtag and center them in the screen
        """
        diagram = self.get_selected_diagram_widget()
        search_text = self.ui.diagramSearchLineEdit.text().lower()
        if diagram is not None:
            if isinstance(diagram, SchematicWidget):
                diagram.graphical_search(search_text=search_text)
            elif isinstance(diagram, GridMapWidget):
                diagram.graphical_search(search_text=search_text)

    def show_diagrams_context_menu(self, pos: QtCore.QPoint):
        """
        Show diagrams tree view context menu
        :param pos: Relative click position
        """
        diagrams_view = getattr(self.ui, 'diagramsTreeView', getattr(self.ui, 'diagramsListView', None))
        if diagrams_view is None:
            return

        context_menu = QtWidgets.QMenu(parent=diagrams_view)
        index = diagrams_view.indexAt(pos)
        model = diagrams_view.model() if hasattr(diagrams_view, 'model') else None
        item = model.get_item(index) if (model is not None and hasattr(model, 'get_item')) else None

        target_folder = None
        if index.isValid() and item is not None:
            if isinstance(item, dev.DiagramFolder):
                target_folder = item
            elif isinstance(item, dev.BaseDiagram):
                target_folder = item.group

        gf.add_menu_entry(menu=context_menu,
                          text=self.tr("New schematic"),
                          icon_path=":/Icons/icons/schematic.png",
                          function_ptr=self.add_complete_bus_branch_diagram)

        gf.add_menu_entry(menu=context_menu,
                          text=self.tr("New schematic from selection"),
                          icon_path=":/Icons/icons/schematic.png",
                          function_ptr=self.new_bus_branch_diagram_from_selection)

        gf.add_menu_entry(menu=context_menu,
                          text=self.tr("New map"),
                          icon_path=":/Icons/icons/map (add).png",
                          function_ptr=self.add_map_diagram)

        context_menu.addSeparator()

        gf.add_menu_entry(menu=context_menu,
                          text=self.tr("New folder"),
                          icon_path=":/Icons/icons/tree.png",
                          function_ptr=lambda checked=False, p=target_folder: self.add_diagram_folder(parent_folder=p))

        if index.isValid() and item is not None:
            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Rename"),
                              icon_path=":/Icons/icons/edit.png",
                              function_ptr=self.rename_diagram_or_folder)

            if isinstance(item, dev.BaseDiagram):
                gf.add_menu_entry(menu=context_menu,
                                  text=self.tr("Duplicate"),
                                  icon_path=":/Icons/icons/copy.png",
                                  function_ptr=self.duplicate_diagram)

            context_menu.addSeparator()
            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Remove"),
                              icon_path=":/Icons/icons/delete3.png",
                              function_ptr=self.remove_diagram)
        else:
            if len(diagrams_view.selectedIndexes()) > 0:
                gf.add_menu_entry(menu=context_menu,
                                  text=self.tr("Duplicate"),
                                  icon_path=":/Icons/icons/copy.png",
                                  function_ptr=self.duplicate_diagram)
                context_menu.addSeparator()
                gf.add_menu_entry(menu=context_menu,
                                  text=self.tr("Remove"),
                                  icon_path=":/Icons/icons/delete3.png",
                                  function_ptr=self.remove_diagram)

        # Convert local position of the view viewport to global screen position
        mapped_pos = diagrams_view.viewport().mapToGlobal(pos)
        context_menu.exec(mapped_pos)

    def disable_all_results_tags(self):
        """
        Disable all tags for the selected diagram
        """
        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, SchematicWidget):
            diagram.disable_all_results_tags()

    def enable_all_results_tags(self):
        """
        Enable all tags for the selected diagram
        """
        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, SchematicWidget):
            diagram.enable_all_results_tags()

    def call_delete_db_element(self, caller: SchematicWidget | GridMapWidget | BaseDiagramWidget,
                               api_obj: ALL_DEV_TYPES):
        """
        This function is meant to be a master delete_with_dialogue function that is passed to each diagram
        so that when a diagram deletes an element, the element is deleted in all other diagrams
        :param caller:
        :param api_obj:
        :return:
        """
        for diagram in self.diagram_widgets_list:
            if diagram != caller:
                if isinstance(diagram, (SchematicWidget, GridMapWidget)):
                    diagram.delete_element_utility_function(device=api_obj, propagate=False)
                else:
                    pass

        try:
            self.circuit.delete_element(obj=api_obj)
        except ValueError as e:
            print(e)

    def set_diagrams_size_constraints(self):
        """
        Set the size constraints
        """
        if self._enable_setting_auto_upgrade:
            diagram_widget = self.get_selected_diagram_widget()

            if diagram_widget is not None:
                diagram_widget.set_size_constraints(
                    use_flow_based_width=self.ui.branch_width_based_on_flow_checkBox.isChecked(),
                    min_branch_width=self.ui.min_branch_size_spinBox.value(),
                    max_branch_width=self.ui.max_branch_size_spinBox.value(),
                    min_bus_width=self.ui.min_node_size_spinBox.value(),
                    max_bus_width=self.ui.max_node_size_spinBox.value(),
                    arrow_size=self.ui.arrow_size_size_spinBox.value(),
                )
                diagram_widget.diagram.default_bus_voltage = self.ui.defaultBusVoltageSpinBox.value()

    def set_diagrams_palette(self):
        """
        Set the size constraints
        """
        if self._enable_setting_auto_upgrade:
            diagram_widget = self.get_selected_diagram_widget()

            if diagram_widget is not None:
                cmap = self.ui.palette_comboBox.currentData()
                diagram_widget.diagram.palette = cmap

                current_study = self.ui.available_results_to_color_comboBox.currentData()
                val = self.ui.diagram_step_slider.value()
                t_idx = val if val > -1 else None

                self.grid_colour_function(diagram_widget=diagram_widget,
                                          current_study=current_study,
                                          t_idx=t_idx)

    def set_diagrams_map_tile_provider(self):
        """
        Set the size constraints
        """
        if self._enable_setting_auto_upgrade:
            diagram_widget = self.get_selected_diagram_widget()

            if diagram_widget is not None:
                if isinstance(diagram_widget, GridMapWidget):
                    tile_src = self.ui.tile_provider_comboBox.currentData()
                    diagram_widget.map.tile_src = tile_src

    def consolidate_diagram_coordinates(self):
        """
        Consolidate the diagram coordinates into the DB
        :return:
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget is not None:
            ok = yes_no_question(text=self.tr("The diagram coordinates will be saved into the corresponding properties "
                                      "of the database, overwriting the existing ones. Do you want to do this?"),
                                 title=self.tr("Consolidate diagram coordinates into the DB"))
            if ok:
                diagram_widget.consolidate_coordinates()

    def select_buses_from_substation(self, substation: dev.Substation) -> List[dev.Bus]:
        """

        :param substation:
        :return:
        """
        select_bus_dlg: DiagramBusSelectorDialogue = DiagramBusSelectorDialogue(
            gui=self,
            grid=self.circuit,
            substation=substation
        )

        try:
            exec_dialog_safely(dialog=select_bus_dlg)
            selected_buses: List[dev.Bus] = select_bus_dlg.get_selected_buses()
        finally:
            delete_dialog_safely(dialog=select_bus_dlg)

        return selected_buses

    def combinations_tree_clicked(self):
        """
        On combinations tree click. Dispatches by the active study type:
        - ShortCircuit: re-colours the diagram for the clicked short-circuit case.
        - InvestmentsEvaluation: applies the clicked Pareto combination to the
          live MultiCircuit (sticky behaviour) and refreshes the diagram.
        - CatalogueOptimization: applies the clicked Pareto combination's
          templates to the live MultiCircuit and refreshes the diagram.
        """
        indices = self.ui.combinationsTreeView.selectedIndexes()

        if len(indices) > 0:

            diagram_widget = self.get_selected_diagram_widget()
            use_flow_based_width = self.ui.branch_width_based_on_flow_checkBox.isChecked()
            min_branch_width = self.ui.min_branch_size_spinBox.value()
            max_branch_width = self.ui.max_branch_size_spinBox.value()
            min_bus_width = self.ui.min_node_size_spinBox.value()
            max_bus_width = self.ui.max_node_size_spinBox.value()
            cmap = self.ui.palette_comboBox.currentData()

            text = indices[0].data(role=QtCore.Qt.ItemDataRole.DisplayRole)
            sel_idx = indices[0].row()
            if self.ui.available_results_to_color_comboBox.currentIndex() > -1 and sel_idx > -1:
                current_study = self.ui.available_results_to_color_comboBox.currentData()

                if current_study == sim.ShortCircuitDriver.tpe:
                    results: sim.ShortCircuitResults = self.session.get_results(SimulationTypes.ShortCircuit_run)
                    self.sc_colouring(diagram_widget=diagram_widget,
                                      results=results,
                                      cmap=cmap,
                                      use_flow_based_width=use_flow_based_width,
                                      min_branch_width=min_branch_width,
                                      max_branch_width=max_branch_width,
                                      min_bus_width=min_bus_width,
                                      max_bus_width=max_bus_width,
                                      sc_index=sel_idx)

                elif current_study == sim.InvestmentsEvaluationDriver.tpe:
                    # delegate to the dedicated handler so this dispatcher stays small
                    self.apply_investments_combination(clicked_index=indices[0])

                elif current_study == sim.CatalogueOptimizationDriver.tpe:
                    # delegate to the dedicated catalogue handler
                    self.apply_catalogue_combination(clicked_index=indices[0])

                else:
                    # the active study has no per-combination behaviour - nothing to do
                    pass
            else:
                # no study selected or invalid row - nothing to dispatch
                pass

        else:
            #  no indices selected
            pass

    def apply_investments_combination(self, clicked_index: QtCore.QModelIndex) -> None:
        """
        Apply the Pareto combination tagged on the clicked tree item to the live
        MultiCircuit and refresh the active diagram.

        The clicked index may be either a top-level combination row or one of its
        investment-name children; we walk up to the top-level item to recover the
        combination index that was stamped via Qt.UserRole when the model was built.

        Behaviour is sticky: every click first deactivates every investment-touched
        device in the live grid, then activates only the investments belonging to
        the clicked combination. This matches the convention the optimizer used
        for each evaluation (an x of all zeros = every investment off), so the
        diagram exactly reproduces the state the optimizer scored for that combo
        and a click on a different row cleanly replaces the previous selection.

        WARNING: every click overwrites the active *profile* (time-series) of
        each touched device via set_investments_status. Any pre-existing
        time-series active profile is lost permanently after the first click and
        cannot be recovered. Tell users to save the project before exploring
        combinations if their grid has a meaningful active profile.

        :param clicked_index: QModelIndex of the row (or child row) the user clicked
        """
        # walk up to the top-level row, since the tree shows investment names as
        # children of each combination row and clicks may land on a child item
        top_index: QtCore.QModelIndex = clicked_index
        while top_index.parent().isValid():
            top_index = top_index.parent()

        # the original combination index was stamped on column 0 at model-build
        # time; read it from the column-0 sibling so we get the tagged item even
        # if the user clicked a different column of the same row
        column_zero_index: QtCore.QModelIndex = top_index.sibling(top_index.row(), 0)
        user_data = column_zero_index.data(QtCore.Qt.ItemDataRole.UserRole)

        if user_data is None:
            # row was not tagged with a combination index (defensive guard)
            return None
        else:
            i: int = int(user_data)

        driver, results = self.session.investments_evaluation
        if driver is None or results is None:
            # results were cleared between panel build and click
            self.show_warning_toast("Investments evaluation results are no longer available")
            return None
        else:
            pass

        # build the list of Investment objects activated by this combination
        x_vec: np.ndarray = results.x[i, :]
        inv_list = driver.problem.get_investments_for_combination(x=x_vec)

        # Force a clean baseline before applying the combo: deactivate every
        # device touched by any investment in the grid. Without this step,
        # branches that were switched on by a previous click would stay on,
        # compounding selections instead of replacing them. We use the cached
        # _investments_all list (snapshot at evaluation finish) rather than the
        # current self.circuit.investments so the deactivation set is stable
        # across clicks and identical to what post_investments_evaluation
        # used when seeding the diagram.
        all_elements_dict, _ = self.circuit.get_all_elements_dict()
        self.circuit.set_investments_status(investments_list=self._investments_all,
                                            apply_investment=False,
                                            all_elements_dict=all_elements_dict)

        # apply the selected combination on top of the now-deactivated state
        self.circuit.set_investments_status(investments_list=inv_list,
                                            apply_investment=True,
                                            all_elements_dict=all_elements_dict)

        # Refresh active/inactive pen styles on every open schematic so toggled
        # branches go from dashed (inactive) to solid (active) and vice versa.
        # This is separate from result-based colouring done by colour_diagrams() —
        # the dashed/solid pen style is set by recolour_mode(), which reads
        # api_object.active. colour_diagrams() only paints results-based colours
        # and does not refresh active-state styling on its own.
        for diagram_widget in self.diagram_widgets_list:
            if isinstance(diagram_widget, SchematicWidget):
                diagram_widget.recolour_mode()
            else:
                # map widgets and other diagram types do not encode active state
                # via dashed/solid pen styling, so they have nothing to refresh
                pass

        # re-apply result-based colouring on top of the active-state styling
        self.colour_diagrams()
        self.show_info_toast(f"Applied Pareto combination {i}: "
                             f"{len(inv_list)} investments active")
        return None

    def apply_catalogue_combination(self, clicked_index: QtCore.QModelIndex) -> None:
        """
        Apply the Pareto combination tagged on the clicked tree item to the live
        MultiCircuit by swapping each selected branch's electrical parameters to
        those of the chosen template, then refresh the diagrams.

        The clicked index may be either a top-level combination row or one of
        its decision-variable children; we walk up to the top-level item to
        recover the combination index that was stamped via Qt.UserRole when
        the model was built.

        Behaviour is sticky: every click first restores every problem-tracked
        branch to its baseline state captured at problem-construction time
        (in CatalogueOptimizationProblem.snapshots), then applies the templates
        for the selected combination's x vector. This matches the convention
        the optimizer used per evaluation, so the diagram exactly reproduces
        the state NSGA-3 scored for that combination, and a click on a
        different row cleanly replaces the previous selection.

        WARNING: every click overwrites each branch's electrical parameters
        (R, X, B, rate, ...) and template pointers via apply_template. If the
        user has unsaved manual edits to those branches, they will be lost
        after the first click. Tell users to save the project before exploring
        combinations.

        :param clicked_index: QModelIndex of the row (or child row) the user clicked
        """
        # Walk up to the top-level row, since the tree shows decision-variable
        # entries as children of each combination row and clicks may land on
        # a child item.
        top_index: QtCore.QModelIndex = clicked_index
        while top_index.parent().isValid():
            top_index = top_index.parent()

        # The combination index was stamped on column 0 at model-build time;
        # read it from the column-0 sibling so we get the tagged item even if
        # the user clicked a different column of the same row.
        column_zero_index: QtCore.QModelIndex = top_index.sibling(top_index.row(), 0)
        user_data = column_zero_index.data(QtCore.Qt.ItemDataRole.UserRole)

        if user_data is None:
            # row was not tagged with a combination index (defensive guard)
            return None
        else:
            i: int = int(user_data)

        driver, results = self.session.catalogue_optimization
        if driver is None or results is None:
            # results were cleared between panel build and click
            self.show_warning_toast("Catalogue optimization results are no longer available")
            return None
        else:
            pass

        # Recover the integer x vector for this Pareto member.
        x_vec: np.ndarray = results.x[i, :]

        # Force a clean baseline before applying the combo: revert every branch
        # tracked by the problem to its pre-evaluation snapshot. Without this
        # step, parameter changes from a previous click would compound, and a
        # branch whose chosen template differs between two combos would end
        # up with the most recently-applied template both times.
        driver.problem._restore_baseline()

        # Apply the templates for the selected combination on top of the
        # restored baseline. _apply_combination performs branch.apply_template
        # for every decision slot using x_vec[i] as the pool index.
        driver.problem._apply_combination(x=x_vec)

        # Refresh active/inactive pen styles on every open schematic. Catalogue
        # optimization does not toggle device.active itself, but apply_template
        # may indirectly affect rendering (rate-based widths, etc.), so we run
        # the same recolour pass we use for Investments to keep the diagrams
        # consistent with the live state.
        for diagram_widget in self.diagram_widgets_list:
            if isinstance(diagram_widget, SchematicWidget):
                diagram_widget.recolour_mode()
            else:
                # non-schematic widgets do not encode branch state via pen
                # styling, so they have nothing to refresh here
                pass

        # Re-apply result-based colouring on top of the refreshed pen styling.
        self.colour_diagrams()
        self.show_info_toast(f"Applied catalogue combination {i}: "
                             f"{len(x_vec)} branches updated")
        return None

    def reset_diagram_coordinates(self):
        """
        Reset the diagram coordinates using the DB
        :return:
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget is not None:
            ok = yes_no_question(text=self.tr("The diagram coordinates will be reset to its database values. "
                                      "Do you want to do this?"),
                                 title=self.tr("Reset diagram coordinates using the DB"))
            if ok:
                diagram_widget.reset_coordinates()
                self.show_info_toast(message='Coordinates of substations and line '
                                             'locations set to its database values.')

    def rotate(self):
        """
        Rotate the selected diagram
        :return:
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget is not None:
            dlg = InputNumberDialogue(min_value=-180, max_value=180,
                                      default_value=-90, is_int=False,
                                      title=self.tr('Rotate diagram'),
                                      text=self.tr('Rotation angle (degrees)'))

            if exec_dialog_safely(dialog=dlg):
                diagram_widget.rotate(dlg.value)

    def preset_1(self):
        """
        Country sizes
        """
        self.ui.min_node_size_spinBox.setValue(2)
        self.ui.max_node_size_spinBox.setValue(8)
        self.ui.min_branch_size_spinBox.setValue(1)
        self.ui.max_branch_size_spinBox.setValue(3)
        self.ui.arrow_size_size_spinBox.setValue(1.5)
        self.redraw_current_diagram()

    def preset_2(self):
        """
        Region sizes
        """
        self.ui.min_node_size_spinBox.setValue(1)
        self.ui.max_node_size_spinBox.setValue(2)
        self.ui.min_branch_size_spinBox.setValue(0.1)
        self.ui.max_branch_size_spinBox.setValue(0.2)
        self.ui.arrow_size_size_spinBox.setValue(0.15)
        self.redraw_current_diagram()

    def preset_3(self):
        """
        Municipality sizes
        """
        self.ui.min_node_size_spinBox.setValue(0.1)
        self.ui.max_node_size_spinBox.setValue(0.2)
        self.ui.min_branch_size_spinBox.setValue(0.01)
        self.ui.max_branch_size_spinBox.setValue(0.02)
        self.ui.arrow_size_size_spinBox.setValue(0.015)
        self.redraw_current_diagram()

    def preset_4(self):
        """
        Street sizes
        """
        self.ui.min_node_size_spinBox.setValue(0.01)
        self.ui.max_node_size_spinBox.setValue(0.02)
        self.ui.min_branch_size_spinBox.setValue(0.001)
        self.ui.max_branch_size_spinBox.setValue(0.002)
        self.ui.arrow_size_size_spinBox.setValue(0.0015)
        self.redraw_current_diagram()

    def set_diagram_branches_reticular_style(self):
        """
        Set all branches drawing mode to reticular
        """
        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, SchematicWidget):
            diagram.set_all_branch_drawing_styles(SchematicAutoRouteStyle.RETICULAR)

    def set_diagram_branches_straight_style(self):
        """
        Set all branches drawing mode to straight
        """
        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, SchematicWidget):
            diagram.set_all_branch_drawing_styles(SchematicAutoRouteStyle.STRAIGHT)

    def repair_selected_schematic_diagram(self):
        """
        Repair suspicious legacy manual injection positions in the selected schematic.
        """
        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, SchematicWidget):
            repaired_count = diagram.repair_suspicious_injection_positions()
            self.show_info_toast(f"Repaired {repaired_count} suspicious injection positions")
        else:
            self.show_warning_toast("The current diagram is not a schematic :(")
