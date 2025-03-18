# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
from typing import List, Tuple, Union

import networkx as nx
import numpy as np
from PySide6 import QtGui, QtWidgets, QtCore
from matplotlib import pyplot as plt
from pandas.plotting import register_matplotlib_converters

import GridCalEngine.Devices.Diagrams.palettes as palettes
from GridCalEngine import ContingencyOperationTypes
from GridCalEngine.IO.file_system import tiles_path
from GridCal.Gui.general_dialogues import (CheckListDialogue, StartEndSelectionDialogue, InputSearchDialogue,
                                           InputNumberDialogue, LogsDialogue)
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.Simulations import PowerFlowResults, ContinuationPowerFlowResults, PowerFlowTimeSeriesResults
from GridCalEngine.Utils.progress_bar import print_progress_bar
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import SimulationTypes, Colormaps
from GridCalEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram

import GridCalEngine.Devices as dev
import GridCalEngine.Simulations as sim
import GridCal.Gui.gui_functions as gf
from GridCal.Gui.object_model import ObjectsModel
from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import (SchematicWidget,
                                                                   BusGraphicItem,
                                                                   generate_schematic_diagram,
                                                                   make_vicinity_diagram)
from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget, generate_map_diagram
from GridCal.Gui.Diagrams.diagrams_model import DiagramsModel
from GridCal.Gui.messages import yes_no_question, error_msg, info_msg
from GridCal.Gui.Main.SubClasses.Model.compiled_arrays import CompiledArraysMain
from GridCal.Gui.Main.object_select_window import ObjectSelectWindow
from GridCal.Gui.Diagrams.MapWidget.Tiles.TileProviders.cartodb import CartoDbTiles

ALL_EDITORS = Union[SchematicWidget, GridMapWidget]
ALL_EDITORS_NONE = Union[None, SchematicWidget, GridMapWidget]


class VideoExportWorker(QtCore.QThread):
    """
    VideoExportWorker
    """
    progress_signal = QtCore.Signal(float)
    progress_text = QtCore.Signal(str)
    done_signal = QtCore.Signal()

    def __init__(self, filename, diagram: SchematicWidget | GridMapWidget,
                 fps: int, start_idx: int, end_idx: int, current_study: str,
                 grid_colour_function):
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
        self.fps = fps
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.current_study = current_study
        self.grid_colour_function = grid_colour_function

        self.logger = Logger()

    def run(self):
        """
        Run function
        :return:
        """
        # start recording...
        w, h = self.diagram.start_video_recording(fname=self.filename, fps=self.fps, logger=self.logger)

        # paint and capture
        for t_idx in range(self.start_idx, self.end_idx):
            self.grid_colour_function(diagram=self.diagram,
                                      current_study=self.current_study,
                                      t_idx=t_idx,
                                      allow_popups=False)

            self.diagram.capture_video_frame(w=w, h=h, logger=self.logger)

            self.progress_text.emit(f"Saving frame {t_idx} / {self.end_idx}")
            self.progress_signal.emit(t_idx / self.end_idx)

            print_progress_bar(t_idx + 1, self.end_idx)

        # finalize
        self.diagram.end_video_recording()

        self.logger.add_info(f"Video saved to {self.filename}")

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
        self.diagram_widgets_list: List[ALL_EDITORS] = list()

        # flag to avoid circular updating of the display settings when changing diagrams
        self._enable_setting_auto_upgrade = True

        # Declare the map
        palettes_list = [palettes.Colormaps.GridCal,
                         palettes.Colormaps.Green2Red,
                         palettes.Colormaps.Heatmap,
                         palettes.Colormaps.TSO]
        self.cmap_dict = {e.value: e for e in palettes_list}
        self.cmap_index_dict = {pal: i for i, pal in enumerate(palettes_list)}
        self.ui.palette_comboBox.setModel(gf.get_list_model([e.value for e in palettes_list]))

        # map tile sources
        self.tile_sources = [
            # Carto layers:
            # light_all,
            # dark_all,
            # light_nolabels,
            # light_only_labels,
            # dark_nolabels,
            # dark_only_labels,
            # rastertiles/voyager,
            # rastertiles/voyager_nolabels,
            # rastertiles/voyager_only_labels,
            # rastertiles/voyager_labels_under

            CartoDbTiles(
                name='Carto voyager',
                tiles_dir=os.path.join(tiles_path(), 'carto_db_voyager'),
                tile_servers=["https://basemaps.cartocdn.com/rastertiles/voyager/"]
            ),
            CartoDbTiles(
                name='Carto positron',
                tiles_dir=os.path.join(tiles_path(), 'carto_db_positron'),
                tile_servers=['https://basemaps.cartocdn.com/light_all/']
            ),
            CartoDbTiles(
                name='Carto dark matter',
                tiles_dir=os.path.join(tiles_path(), 'carto_db_dark_matter'),
                tile_servers=["https://basemaps.cartocdn.com/dark_all/"]
            ),
            CartoDbTiles(
                name='Open Street Map',
                tiles_dir=os.path.join(tiles_path(), 'osm'),
                tile_servers=["https://tile.openstreetmap.org"]
            ),
            # OimTiles(
            #     name='Open infra Map',
            #     tiles_dir=os.path.join(tiles_path(), 'osm'),
            #     tile_servers=["https://openinframap.org/tiles"]
            # )
        ]
        tile_names = [tile.tile_set_name for tile in self.tile_sources]
        self.tile_index_dict = {tile.tile_set_name: i for i, tile in enumerate(self.tile_sources)}
        self.tile_name_dict = {tile.tile_set_name: tile for tile in self.tile_sources}
        self.ui.tile_provider_comboBox.setModel(gf.get_list_model(tile_names))
        self.ui.tile_provider_comboBox.setCurrentIndex(0)

        # Automatic layout modes
        self.layout_algorithms_dict = dict()
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

        mdl = gf.get_list_model(list(self.layout_algorithms_dict.keys()))
        self.ui.automatic_layout_comboBox.setModel(mdl)
        self.ui.automatic_layout_comboBox.setCurrentIndex(6)

        # list of steps in the schematic
        self.schematic_list_steps = list()

        self.available_results_steps_dict = None

        # list of styles
        plt_styles = plt.style.available
        self.ui.plt_style_comboBox.setModel(gf.get_list_model(plt_styles))

        if 'fivethirtyeight' in plt_styles:
            self.ui.plt_style_comboBox.setCurrentText('fivethirtyeight')

        # configure matplotlib for pandas time series
        register_matplotlib_converters()

        # task watcher for video export
        self.video_thread: VideoExportWorker | None = None

        # --------------------------------------------------------------------------------------------------------------
        self.ui.actionTakePicture.triggered.connect(self.take_picture)
        self.ui.actionRecord_video.triggered.connect(self.record_video)
        self.ui.actionDelete_selected.triggered.connect(self.delete_selected_from_the_diagram_and_db)
        self.ui.actionDelete_from_the_diagram.triggered.connect(self.delete_selected_from_the_diagram)
        self.ui.actionTry_to_fix_buses_location.triggered.connect(self.try_to_fix_buses_location)
        self.ui.actionSet_schematic_positions_from_GPS_coordinates.triggered.connect(self.set_xy_from_lat_lon)
        self.ui.actionSetSelectedBusCountry.triggered.connect(lambda: self.set_selected_bus_property('country'))
        self.ui.actionSetSelectedBusArea.triggered.connect(lambda: self.set_selected_bus_property('area'))
        self.ui.actionSetSelectedBusZone.triggered.connect(lambda: self.set_selected_bus_property('zone'))
        self.ui.actionSelect_buses_by_area.triggered.connect(lambda: self.select_buses_by_property('area'))
        self.ui.actionSelect_buses_by_zone.triggered.connect(lambda: self.select_buses_by_property('zone'))
        self.ui.actionSelect_buses_by_country.triggered.connect(lambda: self.select_buses_by_property('country'))
        self.ui.actionAdd_selected_to_contingency.triggered.connect(self.add_selected_to_contingency)
        self.ui.actionAdd_selected_as_remedial_action.triggered.connect(self.add_selected_to_remedial_action)
        self.ui.actionAdd_selected_as_new_investment.triggered.connect(self.add_selected_to_investment)
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
        self.ui.actionSearchDiagram.triggered.connect(self.search_diagram)
        self.ui.actionEdit_simulation_time_limits.triggered.connect(self.edit_time_interval)
        self.ui.actionDisable_all_results_tags.triggered.connect(self.disable_all_results_tags)
        self.ui.actionEnable_all_results_tags.triggered.connect(self.enable_all_results_tags)
        self.ui.actionConsolidate_diagram_coordinates.triggered.connect(self.consolidate_diagram_coordinates)
        self.ui.actionRotate.triggered.connect(self.rotate)

        # Buttons
        self.ui.colour_results_pushButton.clicked.connect(self.colour_diagrams)
        self.ui.redraw_pushButton.clicked.connect(self.redraw_current_diagram)

        # list clicks
        self.ui.diagramsListView.clicked.connect(self.set_selected_diagram_on_click)

        # combobox change
        self.ui.plt_style_comboBox.currentTextChanged.connect(self.plot_style_change)
        self.ui.palette_comboBox.currentTextChanged.connect(self.set_diagrams_palette)
        self.ui.tile_provider_comboBox.currentTextChanged.connect(self.set_diagrams_map_tile_provider)

        self.ui.available_results_to_color_comboBox.currentTextChanged.connect(lambda: self.colour_diagrams(False))

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

        # context menu
        self.ui.diagramsListView.customContextMenuRequested.connect(self.show_diagrams_context_menu)

        # Set context menu policy to CustomContextMenu
        self.ui.diagramsListView.setContextMenuPolicy(QtGui.Qt.ContextMenuPolicy.CustomContextMenu)

    def get_default_voltage(self) -> float:
        """
        Get the defualt marked voltage
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
                    reply = QtWidgets.QMessageBox.question(self, 'Message',
                                                           'Are you sure that you want to try an automatic layout?',
                                                           QtWidgets.QMessageBox.StandardButton.Yes,
                                                           QtWidgets.QMessageBox.StandardButton.No)

                    if reply == QtWidgets.QMessageBox.StandardButton.Yes.value:
                        do_it = True
                    else:
                        do_it = False

                if do_it:
                    diagram_widget.auto_layout(sel=self.ui.automatic_layout_comboBox.currentText())

            else:
                info_msg("The current diagram cannot be automatically layed out")
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
                selected = self.get_selected_buses()

                if len(selected) == 0:
                    widget.center_nodes(elements=None)
                else:
                    buses = [bus for i, bus, graphic in selected]
                    widget.center_nodes(elements=buses)

            elif isinstance(widget, GridMapWidget):
                widget.center()

    def get_selected_buses(self) -> List[Tuple[int, dev.Bus, BusGraphicItem]]:
        """
        Get the selected buses
        :return: list of (bus position, bus object, bus_graphics object)
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            return diagram_widget.get_selected_buses()
        else:
            return list()

    def get_current_buses(self) -> List[Tuple[int, dev.Bus, BusGraphicItem]]:
        """
        Get the selected buses
        :return: list of (bus position, bus object, bus_graphics object)
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            return diagram_widget.get_buses()
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
                self.start_end_dialogue_window = StartEndSelectionDialogue(min_value=self.simulation_start_index,
                                                                           max_value=self.simulation_end_index,
                                                                           time_array=self.circuit.time_profile)

                self.start_end_dialogue_window.setModal(True)
                self.start_end_dialogue_window.exec()

                if self.start_end_dialogue_window.is_accepted:
                    self.setup_sim_indices(st=self.start_end_dialogue_window.start_value,
                                           en=self.start_end_dialogue_window.end_value)
            else:
                info_msg("Empty time series :/")
        else:
            info_msg("There are no time series :/")

    def pf_colouring(self, diagram_widget: Union[SchematicWidget, GridMapWidget],
                     results: PowerFlowResults, cmap: Colormaps,
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
                                             theta=results.tap_angle,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def pf_ts_colouring(self, t_idx: int,
                        diagram_widget: Union[SchematicWidget, GridMapWidget],
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
                                             cmap=cmap)

    def cpf_colouring(self, diagram_widget: Union[SchematicWidget, GridMapWidget],
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

    def spf_colouring(self, diagram_widget: Union[SchematicWidget, GridMapWidget],
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

    def sc_colouring(self, diagram_widget: Union[SchematicWidget, GridMapWidget],
                     results: sim.ShortCircuitResults, cmap: Colormaps,
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

        return diagram_widget.colour_results(Sbus=results.Sbus1,
                                             bus_active=bus_active,
                                             Sf=results.Sf1,
                                             St=results.St1,
                                             voltages=results.voltage1,
                                             types=results.bus_types,
                                             loadings=results.loading1,
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

    def opf_colouring(self, diagram_widget: Union[SchematicWidget, GridMapWidget],
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
                                             cmap=cmap)

    def opf_ts_colouring(self, t_idx: int,
                         diagram_widget: Union[SchematicWidget, GridMapWidget],
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
                                             cmap=cmap)

    def ntc_colouring(self, diagram_widget: Union[SchematicWidget, GridMapWidget],
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
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def ntc_ts_colouring(self, t_idx: int,
                         diagram_widget: Union[SchematicWidget, GridMapWidget],
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
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def nc_ts_colouring(self, t_idx: int | None,
                        diagram_widget: Union[SchematicWidget, GridMapWidget],
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

    def linpf_colouring(self, diagram_widget: Union[SchematicWidget, GridMapWidget],
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
                           diagram_widget: Union[SchematicWidget, GridMapWidget],
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

    def con_colouring(self, diagram_widget: Union[SchematicWidget, GridMapWidget],
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
                         diagram_widget: Union[SchematicWidget, GridMapWidget],
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

    def default_colouring(self, t_idx: int | None,
                          diagram_widget: Union[SchematicWidget, GridMapWidget],
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

        bus_active = self.circuit.get_bus_actives(t_idx=t_idx)
        br_active = self.circuit.get_branch_actives(t_idx=t_idx, add_vsc=False, add_hvdc=False, add_switch=True)
        hvdc_active = self.circuit.get_hvdc_actives(t_idx=t_idx)
        vsc_active = self.circuit.get_vsc_actives(t_idx=t_idx)

        return diagram_widget.colour_results(Sbus=np.zeros(nbus, dtype=complex),
                                             voltages=np.ones(nbus, dtype=complex),
                                             bus_active=bus_active,
                                             Sf=np.zeros(nbr, dtype=complex),
                                             St=np.zeros(nbr, dtype=complex),
                                             loadings=np.zeros(nbr, dtype=complex),
                                             br_active=br_active,
                                             hvdc_active=hvdc_active,
                                             use_flow_based_width=use_flow_based_width,
                                             min_branch_width=min_branch_width,
                                             max_branch_width=max_branch_width,
                                             min_bus_width=min_bus_width,
                                             max_bus_width=max_bus_width,
                                             cmap=cmap)

    def grid_colour_function(self,
                             diagram_widget: Union[SchematicWidget, GridMapWidget],
                             current_study: str,
                             t_idx: Union[None, int],
                             allow_popups: bool = True) -> None:
        """
        Colour the schematic or the map
        :param diagram_widget: Diagram where the plotting is made
        :param current_study: current_study name
        :param t_idx: current time step (if None, the snapshot is taken)
        :param allow_popups: if true, messages me pop up
        """
        use_flow_based_width = self.ui.branch_width_based_on_flow_checkBox.isChecked()
        min_branch_width = self.ui.min_branch_size_spinBox.value()
        max_branch_width = self.ui.max_branch_size_spinBox.value()
        min_bus_width = self.ui.min_node_size_spinBox.value()
        max_bus_width = self.ui.max_node_size_spinBox.value()

        cmap_text = self.ui.palette_comboBox.currentText()
        cmap = self.cmap_dict[cmap_text]

        if current_study == sim.PowerFlowDriver.tpe.value:
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
                    info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.PowerFlowTimeSeriesDriver.tpe.value:
            if t_idx is not None:
                drv, results = self.session.power_flow_ts
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
                    info_msg(f"{current_study} does not have values for the snapshot")

        elif current_study == sim.ContinuationPowerFlowDriver.tpe.value:
            if t_idx is None:
                results: sim.ContinuationPowerFlowResults = self.session.get_results(
                    SimulationTypes.ContinuationPowerFlow_run
                )
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
                    info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.StochasticPowerFlowDriver.tpe.value:

            # the time is not relevant in this study
            results: sim.StochasticPowerFlowResults = self.session.get_results(
                SimulationTypes.StochasticPowerFlow
            )
            self.spf_colouring(diagram_widget=diagram_widget,
                               results=results,
                               cmap=cmap,
                               use_flow_based_width=use_flow_based_width,
                               min_branch_width=min_branch_width,
                               max_branch_width=max_branch_width,
                               min_bus_width=min_bus_width,
                               max_bus_width=max_bus_width)

        elif current_study == sim.ShortCircuitDriver.tpe.value:
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
                    info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.OptimalPowerFlowDriver.tpe.value:
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
                    info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.OptimalPowerFlowTimeSeriesDriver.tpe.value:

            if t_idx is not None:
                results: sim.OptimalPowerFlowTimeSeriesResults = self.session.get_results(
                    SimulationTypes.OPFTimeSeries_run
                )
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
                    info_msg(f"{current_study} does not have values for the snapshot")

        elif current_study == sim.NodalCapacityTimeSeriesDriver.tpe.value:

            _, results = self.session.nodal_capacity_optimization_ts
            self.nc_ts_colouring(t_idx=t_idx,
                                 diagram_widget=diagram_widget,
                                 results=results,
                                 cmap=cmap,
                                 use_flow_based_width=use_flow_based_width,
                                 min_branch_width=min_branch_width,
                                 max_branch_width=max_branch_width,
                                 min_bus_width=min_bus_width,
                                 max_bus_width=max_bus_width)

        elif current_study == sim.LinearAnalysisDriver.tpe.value:
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
                    info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.LinearAnalysisTimeSeriesDriver.tpe.value:
            if t_idx is not None:
                results: sim.LinearAnalysisTimeSeriesResults = self.session.get_results(
                    SimulationTypes.LinearAnalysis_TS_run
                )
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
                    info_msg(f"{current_study} does not have values for the snapshot")

        elif current_study == sim.ContingencyAnalysisDriver.tpe.value:

            if t_idx is None:
                results: sim.ContingencyAnalysisResults = self.session.get_results(
                    SimulationTypes.ContingencyAnalysis_run
                )
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
                    info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.ContingencyAnalysisTimeSeriesDriver.tpe.value:
            if t_idx is not None:
                results: sim.ContingencyAnalysisTimeSeriesResults = self.session.get_results(
                    SimulationTypes.ContingencyAnalysisTS_run
                )
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
                    info_msg(f"{current_study} does not have values for the snapshot")

        elif current_study == sim.AvailableTransferCapacityDriver.tpe.value:
            self.default_colouring(t_idx=t_idx,
                                   diagram_widget=diagram_widget,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)

        elif current_study == sim.AvailableTransferCapacityTimeSeriesDriver.tpe.value:
            self.default_colouring(t_idx=t_idx,
                                   diagram_widget=diagram_widget,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)

        elif current_study == sim.OptimalNetTransferCapacityDriver.tpe.value:
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
                    info_msg(f"{current_study} only has values for the snapshot")

        elif current_study == sim.OptimalNetTransferCapacityTimeSeriesDriver.tpe.value:
            if t_idx is not None:
                results: sim.OptimalNetTransferCapacityTimeSeriesResults = self.session.get_results(
                    SimulationTypes.OPF_NTC_TS_run
                )
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
                    info_msg(f"{current_study} does not have values for the snapshot")

        elif current_study == sim.InputsAnalysisDriver.tpe.value:

            self.default_colouring(t_idx=t_idx,
                                   diagram_widget=diagram_widget,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)

        elif current_study == SimulationTypes.DesignView.value:

            self.default_colouring(t_idx=t_idx,
                                   diagram_widget=diagram_widget,
                                   cmap=cmap,
                                   use_flow_based_width=use_flow_based_width,
                                   min_branch_width=min_branch_width,
                                   max_branch_width=max_branch_width,
                                   min_bus_width=min_bus_width,
                                   max_bus_width=max_bus_width)

        elif current_study == 'Transient stability':
            raise Exception('Not implemented :(')

        else:
            print('grid_colour_function: <' + current_study + '> Not implemented :(')

    def colour_diagrams(self, allow_popups: bool = True) -> None:
        """
        Color the grid now
        :param allow_popups:
        """
        if self.ui.available_results_to_color_comboBox.currentIndex() > -1:

            current_study = self.ui.available_results_to_color_comboBox.currentText()

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

    def set_diagrams_list_view(self) -> None:
        """
        Create the diagrams list view
        """
        mdl = DiagramsModel(self.diagram_widgets_list)
        self.ui.diagramsListView.setModel(mdl)

    def get_selected_diagram_widget(self) -> ALL_EDITORS_NONE:
        """
        Get the currently selected diagram
        :return: None, DiagramEditorWidget, GridMapWidget, BusViewerGUI
        """
        indices = self.ui.diagramsListView.selectedIndexes()

        if len(indices):
            idx = indices[0].row()
            return self.diagram_widgets_list[idx]
        else:
            return None

    def create_blank_schematic_diagram(self, name: str = "") -> SchematicWidget:
        """
        Create a new schematic widget
        :param name: name of the new schematic
        :return:
        """
        diagram = SchematicDiagram(name=name)

        diagram_widget = SchematicWidget(gui=self,
                                         circuit=self.circuit,
                                         diagram=diagram,
                                         default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                         time_index=self.get_diagram_slider_index(),
                                         prefer_node_breaker=False,
                                         call_delete_db_element_func=self.call_delete_db_element)

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
                                                     busbars=self.circuit.get_bus_bars(),
                                                     connecivity_nodes=self.circuit.get_connectivity_nodes(),
                                                     lines=self.circuit.get_lines(),
                                                     dc_lines=self.circuit.get_dc_lines(),
                                                     transformers2w=self.circuit.get_transformers2w(),
                                                     transformers3w=self.circuit.get_transformers3w(),
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

                diagram_widget.set_data(circuit=self.circuit, diagram=diagram)

            elif isinstance(diagram_widget, GridMapWidget):
                diagram_widget.update_device_sizes(asynchronously=False)

    def set_selected_diagram_on_click(self):
        """
        on list-view click, set the currently selected diagram widget
        """
        diagram = self.get_selected_diagram_widget()

        if diagram:
            self.set_diagram_widget(diagram)

    def add_complete_bus_branch_diagram_now(self, name='All bus branches',
                                            prefer_node_breaker: bool = False) -> SchematicWidget:
        """
        Add ageneral bus-branch diagram
        :param name:
        :param prefer_node_breaker:
        :return DiagramEditorWidget
        """
        diagram = generate_schematic_diagram(buses=self.circuit.get_buses(),
                                             busbars=self.circuit.get_bus_bars(),
                                             connecivity_nodes=self.circuit.get_connectivity_nodes(),
                                             lines=self.circuit.get_lines(),
                                             dc_lines=self.circuit.get_dc_lines(),
                                             transformers2w=self.circuit.get_transformers2w(),
                                             transformers3w=self.circuit.get_transformers3w(),
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

        diagram_widget = SchematicWidget(gui=self,
                                         circuit=self.circuit,
                                         diagram=diagram,
                                         default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                         time_index=self.get_diagram_slider_index(),
                                         prefer_node_breaker=prefer_node_breaker,
                                         call_delete_db_element_func=self.call_delete_db_element)

        diagram_widget.setStretchFactor(1, 10)
        diagram_widget.center_nodes()
        self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget, diagram=diagram)
        self.set_diagrams_list_view()
        self.set_diagram_widget(diagram_widget)

        return diagram_widget

    def add_complete_bus_branch_diagram(self) -> None:
        """
        Add ageneral bus-branch diagram
        """
        self.add_complete_bus_branch_diagram_now(name='All bus-branch', prefer_node_breaker=False)

    def add_complete_node_breaker_diagram(self) -> None:
        """
        Add ageneral bus-branch diagram
        """
        self.add_complete_bus_branch_diagram_now(name='All node-breaker', prefer_node_breaker=True)

    def new_bus_branch_diagram_from_selection(self):
        """
        Add a bus-branch diagram of a particular selection of objects
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget:

            if isinstance(diagram_widget, SchematicWidget):
                diagram = diagram_widget.create_schematic_from_selection()

                diagram_widget = SchematicWidget(gui=self,
                                                 circuit=self.circuit,
                                                 diagram=diagram,
                                                 default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                                 time_index=self.get_diagram_slider_index(),
                                                 call_delete_db_element_func=self.call_delete_db_element)

                self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget, diagram=diagram)
                self.set_diagrams_list_view()

    def add_bus_vicinity_diagram_from_model(self):
        """
        Add a bus vicinity diagram
        :return:
        """
        model = self.ui.dataStructureTableView.model()

        if model is not None:

            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.objects

            if len(objects) > 0:

                if len(sel_idx) > 0:

                    unique = {idx.row() for idx in sel_idx}
                    sel_obj = [objects[idx] for idx in unique][0]
                    root_bus = None
                    if isinstance(sel_obj, dev.Bus):
                        root_bus = sel_obj

                    elif isinstance(sel_obj, dev.Generator):
                        root_bus = sel_obj.bus

                    elif isinstance(sel_obj, dev.Battery):
                        root_bus = sel_obj.bus

                    elif isinstance(sel_obj, dev.Load):
                        root_bus = sel_obj.bus

                    elif isinstance(sel_obj, dev.Shunt):
                        root_bus = sel_obj.bus

                    elif isinstance(sel_obj, dev.Line):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.Transformer2W):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.DcLine):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.HvdcLine):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.VSC):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.UPFC):
                        root_bus = sel_obj.bus_from

                    elif isinstance(sel_obj, dev.Switch):
                        root_bus = sel_obj.bus_from

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
                                                  title='Vicinity diagram',
                                                  text='Select the expansion level')

                        if dlg.exec():
                            diagram = make_vicinity_diagram(circuit=self.circuit,
                                                            root_bus=root_bus,
                                                            max_level=dlg.value)

                            diagram_widget = SchematicWidget(gui=self,
                                                             circuit=self.circuit,
                                                             diagram=diagram,
                                                             default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                                             time_index=self.get_diagram_slider_index(),
                                                             call_delete_db_element_func=self.call_delete_db_element)

                            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                                diagram=diagram)
                            self.set_diagrams_list_view()

    def new_bus_branch_diagram_from_bus(self, root_bus: dev.Bus):
        """
        Add a bus-branch diagram of a particular selection of objects
        """
        dlg = InputNumberDialogue(min_value=1, max_value=99,
                                  default_value=1, is_int=True,
                                  title='Vicinity diagram',
                                  text=f'Set the expansion level from {root_bus.name}')

        if dlg.exec():
            diagram = make_vicinity_diagram(circuit=self.circuit,
                                            root_bus=root_bus,
                                            max_level=dlg.value)

            diagram_widget = SchematicWidget(gui=self,
                                             circuit=self.circuit,
                                             diagram=diagram,
                                             default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                             time_index=self.get_diagram_slider_index(),
                                             call_delete_db_element_func=self.call_delete_db_element)

            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget, diagram=diagram)
            self.set_diagrams_list_view()

    def new_bus_branch_diagram_from_substation(self, substation: dev.Substation):
        """
        Add a bus-branch diagram of a particular selection of objects
        """

        buses = self.circuit.get_substation_buses(substation=substation)

        if len(buses):
            diagram = make_vicinity_diagram(circuit=self.circuit,
                                            root_bus=buses[0],
                                            max_level=2,
                                            prog_func=None,
                                            text_func=None)

            diagram_widget = SchematicWidget(gui=self,
                                             circuit=self.circuit,
                                             diagram=diagram,
                                             default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                             time_index=self.get_diagram_slider_index(),
                                             call_delete_db_element_func=self.call_delete_db_element)

            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget, diagram=diagram)
            self.set_diagrams_list_view()
        else:
            info_msg(text=f"No buses were found associated with the substation {substation.name}",
                     title="New schematic from substation")

    def create_circuit_stored_diagrams(self):
        """
        Create as Widgets the diagrams stored in the circuit
        :return:
        """
        self.diagram_widgets_list.clear()
        self.remove_all_diagram_widgets()

        for diagram in self.circuit.diagrams:

            if isinstance(diagram, dev.SchematicDiagram):
                diagram_widget = SchematicWidget(gui=self,
                                                 circuit=self.circuit,
                                                 diagram=diagram,
                                                 default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                                 time_index=self.get_diagram_slider_index(),
                                                 call_delete_db_element_func=self.call_delete_db_element)

                diagram_widget.setStretchFactor(1, 10)
                diagram_widget.center_nodes()
                self.diagram_widgets_list.append(diagram_widget)

            elif isinstance(diagram, dev.MapDiagram):
                # select the tile source from the diagram, if not fund pick the one from the GUI
                default_tile_source = self.tile_name_dict[self.ui.tile_provider_comboBox.currentText()]
                tile_source = self.tile_name_dict.get(diagram.tile_source, default_tile_source)

                # create the map widget
                map_widget = GridMapWidget(
                    gui=self,
                    tile_src=tile_source,
                    start_level=diagram.start_level,
                    longitude=diagram.longitude,
                    latitude=diagram.latitude,
                    name=diagram.name,
                    circuit=self.circuit,
                    diagram=diagram,
                    call_delete_db_element_func=self.call_delete_db_element,
                    call_new_substation_diagram_func=self.new_bus_branch_diagram_from_substation
                )

                # map_widget.go_to_level_and_position(5, -15.41, 40.11)
                self.diagram_widgets_list.append(map_widget)

            else:
                raise Exception("Unknown diagram type")

        self.set_diagrams_list_view()

        if len(self.diagram_widgets_list) > 0:
            diagram = self.diagram_widgets_list[0]
            self.set_diagram_widget(diagram)

    def add_map_diagram(self, ask: bool = True) -> None:
        """
        Adds a Map diagram
        """
        if ask:
            ok = yes_no_question(text=f"Do you want to add all substations to the map?\nYou can add them later.",
                                 title="New map")
        else:
            ok = True

        if ok:
            cmap_text = self.ui.palette_comboBox.currentText()
            cmap = self.cmap_dict[cmap_text]

            diagram = generate_map_diagram(
                substations=self.circuit.get_substations(),
                voltage_levels=self.circuit.get_voltage_levels(),
                lines=self.circuit.get_lines(),
                dc_lines=self.circuit.get_dc_lines(),
                hvdc_lines=self.circuit.get_hvdc(),
                fluid_nodes=self.circuit.get_fluid_nodes(),
                fluid_paths=self.circuit.get_fluid_paths(),
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

            # set other default properties of the diagram
            diagram.tile_source = self.ui.tile_provider_comboBox.currentText()
            diagram.start_level = 5
        else:
            diagram = dev.MapDiagram(name='Map diagram')

        # select the tile source
        tile_source = self.tile_name_dict[self.ui.tile_provider_comboBox.currentText()]

        # create the map widget
        map_widget = GridMapWidget(gui=self,
                                   tile_src=tile_source,
                                   start_level=diagram.start_level,
                                   longitude=diagram.longitude,
                                   latitude=diagram.latitude,
                                   name=diagram.name,
                                   circuit=self.circuit,
                                   diagram=diagram,
                                   call_delete_db_element_func=self.call_delete_db_element,
                                   call_new_substation_diagram_func=self.new_bus_branch_diagram_from_substation)

        self.add_diagram_widget_and_diagram(diagram_widget=map_widget, diagram=diagram)
        self.set_diagrams_list_view()
        self.set_diagram_widget(widget=map_widget)

    def add_diagram_widget_and_diagram(self,
                                       diagram_widget: ALL_EDITORS,
                                       diagram: Union[dev.SchematicDiagram, dev.MapDiagram]):
        """
        Add diagram widget, it also adds the diagram to the circuit for later
        :param diagram_widget: Diagram widget object
        :param diagram: SchematicDiagram or MapDiagram
        """

        # add the widget pointer
        self.diagram_widgets_list.append(diagram_widget)

        # add the diagram to the circuit
        self.circuit.add_diagram(diagram)

    def remove_diagram(self):
        """
        Remove diagram
        """
        diagram_widget = self.get_selected_diagram_widget()
        if diagram_widget is not None:
            ok = yes_no_question("Are you sure that you want to remove " + diagram_widget.name + "?",
                                 "Remove diagram")

            if ok:
                # remove the widget
                self.diagram_widgets_list.remove(diagram_widget)

                # remove the diagram
                self.circuit.remove_diagram(diagram_widget.diagram)

                # remove it from the layout list
                self.remove_all_diagram_widgets()

                # update view
                self.set_diagrams_list_view()

    def duplicate_diagram(self):
        """
        Duplicate the selected diagram
        """
        diagram_widget = self.get_selected_diagram_widget()
        if diagram_widget is not None:

            new_diagram_widget = diagram_widget.copy()

            self.add_diagram_widget_and_diagram(diagram_widget=new_diagram_widget,
                                                diagram=new_diagram_widget.diagram)

            # refresh the list view
            self.set_diagrams_list_view()
        else:
            info_msg(text="Select a valid diagram", title="Duplicate diagram")

    def remove_all_diagrams(self) -> None:
        """
        Remove all diagrams and their widgets
        """
        self.diagram_widgets_list.clear()
        self.remove_all_diagram_widgets()
        self.ui.diagramsListView.setModel(None)

    def remove_all_diagram_widgets(self) -> None:
        """
        Remove all diagram widgets from the container
        """
        # remove all widgets from the layout
        for i in reversed(range(self.ui.schematic_layout.count())):
            # get the widget
            widget_to_remove = self.ui.schematic_layout.itemAt(i).widget()

            # remove it from the layout list
            self.ui.schematic_layout.removeWidget(widget_to_remove)

            # remove it from the gui
            widget_to_remove.setParent(None)

    def set_diagram_widget(self, widget: ALL_EDITORS):
        """
        Set the current diagram in the container
        :param widget: DiagramEditorWidget, GridMapWidget, BusViewerGUI
        """
        self.remove_all_diagram_widgets()

        # add the new diagram
        self.ui.schematic_layout.addWidget(widget)

        # set the alignment
        self.ui.diagram_selection_splitter.setStretchFactor(0, 10)
        self.ui.diagram_selection_splitter.setStretchFactor(1, 2)

        # set the selected index
        row = self.diagram_widgets_list.index(widget)
        index = self.ui.diagramsListView.model().index(row, 0)
        self.ui.diagramsListView.setCurrentIndex(index)

        # set the properties
        self._enable_setting_auto_upgrade = False
        self.ui.branch_width_based_on_flow_checkBox.setChecked(widget.diagram.use_flow_based_width)
        self.ui.min_branch_size_spinBox.setValue(widget.diagram.min_branch_width)
        self.ui.max_branch_size_spinBox.setValue(widget.diagram.max_branch_width)
        self.ui.min_node_size_spinBox.setValue(widget.diagram.min_bus_width)
        self.ui.max_node_size_spinBox.setValue(widget.diagram.max_bus_width)
        self.ui.palette_comboBox.setCurrentIndex(self.cmap_index_dict.get(widget.diagram.palette, 0))

        if isinstance(widget, GridMapWidget):
            self.ui.tile_provider_comboBox.setEnabled(True)
            self.ui.tile_provider_comboBox.setCurrentIndex(self.tile_index_dict[widget.map.tile_src.tile_set_name])
        else:
            self.ui.tile_provider_comboBox.setEnabled(False)

        self.ui.defaultBusVoltageSpinBox.setValue(widget.diagram.default_bus_voltage)
        self._enable_setting_auto_upgrade = True

    def plot_style_change(self):
        """
        Change the style
        """
        style = self.ui.plt_style_comboBox.currentText()
        plt.style.use(style)

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

                # TODO: consider other diagrams

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
        mdl = self.ui.dataStructureTableView.model()
        if isinstance(mdl, ObjectsModel):
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
                files_types = "Scalable Vector Graphics (*.svg);;Portable Network Graphics (*.png)"

                f_name = str(os.path.join(self.project_directory, self.ui.grid_name_line_edit.text()))

                # call dialog to select the file
                filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save image file',
                                                                                f_name, files_types)

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
                    filename, type_selected = QtWidgets.QFileDialog.getSaveFileName(self, 'Save video file',
                                                                                    f_name, files_types)

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
                            current_study=self.ui.available_results_to_color_comboBox.currentText(),
                            grid_colour_function=self.grid_colour_function
                        )
                        self.video_thread.progress_signal.connect(self.ui.progressBar.setValue)
                        self.video_thread.progress_text.connect(self.ui.progress_label.setText)
                        self.video_thread.done_signal.connect(self.post_video_export)
                        self.video_thread.run()  # we cannot run another thread accesing the main thread objects...
            else:
                info_msg("There is not diagram selected", "Record video")

        else:
            info_msg("There are no time series", "Record video")

    def post_video_export(self):
        """

        :return:
        """
        if self.video_thread.logger.has_logs():
            dlg = LogsDialogue("Video export", self.video_thread.logger, True)
            dlg.exec()

    def set_xy_from_lat_lon(self):
        """
        Get the x, y coordinates of the buses from their latitude and longitude
        """
        if self.circuit.valid_for_simulation():

            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, SchematicWidget):

                    if yes_no_question("All nodes in the current diagram will be positioned to a 2D plane projection "
                                       "of their latitude and longitude. "
                                       "Are you sure of this?"):
                        diagram.fill_xy_from_lat_lon(destructive=True)
                        diagram.center_nodes()

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
                                   colors: List[type(QtGui.QColor)],
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
        Set a big marker at the selected buses
        """

        for diagram in self.diagram_widgets_list:

            if isinstance(diagram, SchematicWidget):
                diagram.clear_big_bus_markers()

    def delete_selected_from_the_diagram(self):
        """
        Prompt to delete the selected buses from the current diagram
        """

        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            diagram_widget.delete_Selected_from_widget(delete_from_db=False)

        elif isinstance(diagram_widget, GridMapWidget):
            diagram_widget.delete_Selected_from_widget(delete_from_db=False)

    def delete_selected_from_the_diagram_and_db(self):
        """
        Prompt to delete the selected elements from the current diagram and database
        """
        diagram_widget = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            diagram_widget.delete_Selected_from_widget(delete_from_db=True)

        elif isinstance(diagram_widget, GridMapWidget):
            diagram_widget.delete_Selected_from_widget(delete_from_db=True)

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
                info_msg('Choose some elements from the schematic', 'Fix buses locations')

    def get_selected_devices(self) -> List[ALL_DEV_TYPES]:
        """
        Get the selected investment devices
        :return: list of selected devices
        """

        diagram = self.get_selected_diagram_widget()

        if isinstance(diagram, SchematicWidget):
            lst = diagram.get_selection_api_objects()
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
                self.contingency_checks_diag = CheckListDialogue(objects_list=names,
                                                                 title="Add contingency",
                                                                 ask_for_group_name=True,
                                                                 group_label="Contingency name",
                                                                 group_text=group_text)
                self.contingency_checks_diag.setModal(True)
                self.contingency_checks_diag.exec()

                if self.contingency_checks_diag.is_accepted:

                    group = dev.ContingencyGroup(idtag=None,
                                                 name=self.contingency_checks_diag.get_group_text(),
                                                 category="single" if len(selected) == 1 else "multiple")
                    self.circuit.add_contingency_group(group)

                    for i in self.contingency_checks_diag.selected_indices:
                        elm = selected[i]
                        con = dev.Contingency(device_idtag=elm.idtag,
                                              code=elm.code,
                                              name="Contingency " + elm.name,
                                              prop=ContingencyOperationTypes.Active,
                                              value=0,
                                              group=group)
                        self.circuit.add_contingency(con)
            else:
                info_msg("Select some elements in the schematic first", "Add selected to contingency")

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
                self.ra_checks_diag = CheckListDialogue(objects_list=names,
                                                        title="Add remedial action",
                                                        ask_for_group_name=True,
                                                        group_label="Remedial action name",
                                                        group_text=group_text)
                self.ra_checks_diag.setModal(True)
                self.ra_checks_diag.exec()

                if self.ra_checks_diag.is_accepted:

                    ra_group = dev.RemedialActionGroup(idtag=None,
                                                       name=self.ra_checks_diag.get_group_text(),
                                                       category="single" if len(selected) == 1 else "multiple")
                    self.circuit.add_remedial_action_group(ra_group)

                    for i in self.ra_checks_diag.selected_indices:
                        elm = selected[i]
                        ra = dev.RemedialAction(device_idtag=elm.idtag,
                                                code=elm.code,
                                                name="RA " + elm.name,
                                                prop=ContingencyOperationTypes.Active,
                                                value=0,
                                                group=ra_group)
                        self.circuit.add_remedial_action(ra)
            else:
                info_msg("Select some elements in the schematic first", "Add selected to remedial action")

    def add_selected_to_investment(self) -> None:
        """
        Add contingencies from the schematic selection
        """
        if self.circuit.valid_for_simulation():

            # get the selected investment devices
            selected = self.get_selected_devices()

            if len(selected) > 0:

                group_name = "Investment " + str(len(self.circuit.get_contingency_groups()))

                # launch selection dialogue to add/remove from the selection
                names = [elm.type_name + ": " + elm.name for elm in selected]
                self.investment_checks_diag = CheckListDialogue(objects_list=names,
                                                                title="Add investment",
                                                                ask_for_group_name=True,
                                                                group_label="Investment name",
                                                                group_text=group_name)
                self.investment_checks_diag.setModal(True)
                self.investment_checks_diag.exec()

                if self.investment_checks_diag.is_accepted:

                    # create a new investments group
                    group = dev.InvestmentsGroup(idtag=None,
                                                 name=self.investment_checks_diag.get_group_text(),
                                                 category="single" if len(selected) == 1 else "multiple")
                    self.circuit.add_investments_group(group)

                    # add the selection as investments to the group
                    for i in self.investment_checks_diag.selected_indices:
                        elm = selected[i]
                        con = dev.Investment(device_idtag=elm.idtag,
                                             code=elm.code,
                                             name=elm.type_name + ": " + elm.name,
                                             CAPEX=0.0,
                                             OPEX=0.0,
                                             group=group)
                        self.circuit.add_investment(con)
            else:
                info_msg("Select some elements in the schematic first", "Add selected to investment")

    def select_buses_by_property(self, prop: str):
        """
        Select the current diagram buses by prop
        :param prop: area, zone, country
        """
        if prop == 'area':
            self.object_select_window = ObjectSelectWindow(title='Area',
                                                           object_list=self.circuit.areas,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec()

            if self.object_select_window.selected_object is not None:

                for k, bus, graphic_obj in self.get_current_buses():
                    if bus.area == self.object_select_window.selected_object:
                        graphic_obj.setSelected(True)

        elif prop == 'country':
            self.object_select_window = ObjectSelectWindow(title='country',
                                                           object_list=self.circuit.countries,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_obj in self.get_current_buses():
                    if bus.country == self.object_select_window.selected_object:
                        graphic_obj.setSelected(True)

        elif prop == 'zone':
            self.object_select_window = ObjectSelectWindow(title='Zones',
                                                           object_list=self.circuit.zones,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_obj in self.get_current_buses():
                    if bus.zone == self.object_select_window.selected_object:
                        graphic_obj.setSelected(True)
        else:
            error_msg('Unrecognized option' + str(prop))
            return

    def set_selected_bus_property(self, prop):
        """

        :param prop:
        :return:
        """
        if prop == 'area':
            self.object_select_window = ObjectSelectWindow(title='Area',
                                                           object_list=self.circuit.areas,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_obj in self.get_selected_buses():
                    bus.area = self.object_select_window.selected_object
                    print('Set {0} into bus {1}'.format(self.object_select_window.selected_object.name, bus.name))

        elif prop == 'country':
            self.object_select_window = ObjectSelectWindow(title='country',
                                                           object_list=self.circuit.countries,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_obj in self.get_selected_buses():
                    bus.country = self.object_select_window.selected_object
                    print('Set {0} into bus {1}'.format(self.object_select_window.selected_object.name, bus.name))

        elif prop == 'zone':
            self.object_select_window = ObjectSelectWindow(title='Zones',
                                                           object_list=self.circuit.zones,
                                                           parent=self)
            self.object_select_window.setModal(True)
            self.object_select_window.exec()

            if self.object_select_window.selected_object is not None:
                for k, bus, graphic_pbj in self.get_selected_buses():
                    bus.zone = self.object_select_window.selected_object
                    print('Set {0} into bus {1}'.format(self.object_select_window.selected_object.name, bus.name))
        else:
            error_msg('Unrecognized option' + str(prop))
            return

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

    def delete_from_all_diagrams(self, elements: List[ALL_DEV_TYPES]):
        """
        Delete elements from all editors
        :param elements: list of devices to delete from the graphics editors
        :return:
        """
        for diagram_widget in self.diagram_widgets_list:
            if isinstance(diagram_widget, SchematicWidget):
                diagram_widget.delete_diagram_elements(elements)

            elif isinstance(diagram_widget, GridMapWidget):
                pass

    def search_diagram(self):
        """
        Search elements by name, code or idtag and center them in the screen
        """

        dlg = InputSearchDialogue(deafault_value="",
                                  title="Search",
                                  prompt="Search object by name, code or idtag in the diagram")
        if dlg.exec():

            if dlg.is_accepted:
                diagram = self.get_selected_diagram_widget()

                if diagram is not None:
                    if isinstance(diagram, SchematicWidget):
                        diagram.graphical_search(search_text=dlg.searchText.lower())

    def show_diagrams_context_menu(self, pos: QtCore.QPoint):
        """
        Show diagrams list view context menu
        :param pos: Relative click position
        """
        context_menu = QtWidgets.QMenu(parent=self.ui.diagramsListView)

        gf.add_menu_entry(menu=context_menu,
                          text="New bus-branch",
                          icon_path=":/Icons/icons/schematic.svg",
                          function_ptr=self.add_complete_bus_branch_diagram)

        gf.add_menu_entry(menu=context_menu,
                          text="New node-breaker",
                          icon_path=":/Icons/icons/schematic.svg",
                          function_ptr=self.add_complete_node_breaker_diagram)

        gf.add_menu_entry(menu=context_menu,
                          text="New bus-branch from selection",
                          icon_path=":/Icons/icons/schematic.svg",
                          function_ptr=self.new_bus_branch_diagram_from_selection)

        gf.add_menu_entry(menu=context_menu,
                          text="New map",
                          icon_path=":/Icons/icons/map (add).svg",
                          function_ptr=lambda: self.add_map_diagram(True))

        gf.add_menu_entry(menu=context_menu,
                          text="Duplicate",
                          icon_path=":/Icons/icons/copy.svg",
                          function_ptr=self.duplicate_diagram)

        context_menu.addSeparator()
        gf.add_menu_entry(menu=context_menu,
                          text="Remove",
                          icon_path=":/Icons/icons/delete3.svg",
                          function_ptr=self.remove_diagram)

        # Convert global position to local position of the list widget
        mapped_pos = self.ui.diagramsListView.viewport().mapToGlobal(pos)
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

    def call_delete_db_element(self, caller: Union[SchematicWidget, GridMapWidget], api_obj: ALL_DEV_TYPES):
        """
        This function is meant to be a master delete function that is passed to each diagram
        so that when a diagram deletes an element, the element is deleted in all other diagrams
        :param caller:
        :param api_obj:
        :return:
        """
        for diagram in self.diagram_widgets_list:
            if diagram != caller:
                diagram.delete_diagram_element(device=api_obj, propagate=False)

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
                cmap_text = self.ui.palette_comboBox.currentText()
                cmap = self.cmap_dict[cmap_text]
                diagram_widget.diagram.palette = cmap

                current_study = self.ui.available_results_to_color_comboBox.currentText()
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
                    tile_name = self.ui.tile_provider_comboBox.currentText()
                    tile_src = self.tile_name_dict[tile_name]
                    diagram_widget.map.tile_src = tile_src

    def consolidate_diagram_coordinates(self):
        """
        Consolidate the diagram coordinates into the DB
        :return:
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget is not None:
            ok = yes_no_question(text="The diagram coordinates will be saved into the corresponding properties "
                                      "of the database, overwriting the existing ones. Do you want to do this?",
                                 title="Consolidate diagram coordinates into the DB")
            if ok:
                diagram_widget.consolidate_coordinates()

    def rotate(self):
        """
        Rotate the selected diagram
        :return:
        """
        diagram_widget = self.get_selected_diagram_widget()

        if diagram_widget is not None:
            dlg = InputNumberDialogue(min_value=-180, max_value=180,
                                      default_value=-90, is_int=False,
                                      title='Rotate diagram',
                                      text=f'Rotation angle (degrees)')

            if dlg.exec():
                diagram_widget.rotate(dlg.value)
