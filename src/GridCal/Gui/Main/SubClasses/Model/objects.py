# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from typing import Union, List, Set, Tuple
from PySide6 import QtGui, QtCore, QtWidgets
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from GridCal.Gui.associations_model import AssociationsModel
from GridCal.Gui.table_view_header_wrap import HeaderViewWithWordWrap
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
import GridCalEngine.basic_structures as bs
import GridCalEngine.Devices as dev
import GridCal.Gui.gui_functions as gf
from GridCal.Gui.object_model import ObjectsModel
from GridCal.Gui.profiles_model import ProfilesModel
import GridCalEngine.Utils.Filtering as flt
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.Topology.detect_substations import detect_substations, detect_facilities
from GridCal.Gui.Analysis.object_plot_analysis import object_histogram_analysis
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg, info_msg
from GridCal.Gui.Main.SubClasses.Model.diagrams import DiagramsMain
from GridCal.Gui.TowerBuilder.LineBuilderDialogue import TowerBuilderGUI
from GridCal.Gui.general_dialogues import LogsDialogue
from GridCal.Gui.SystemScaler.system_scaler import SystemScaler
from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget, make_diagram_from_substations
from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget, make_diagram_from_buses


class ObjectsTableMain(DiagramsMain):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        DiagramsMain.__init__(self, parent)

        # list of all the objects of the selected type under the Objects tab
        self.type_objects_list = list()

        # setup the objects tree
        self.setup_objects_tree()

        # setup the tree for compiled arrays
        self.setup_compiled_arrays_tree()

        # Buttons
        self.ui.filter_pushButton.clicked.connect(self.objects_smart_search)
        self.ui.delete_selected_objects_pushButton.clicked.connect(self.delete_selected_objects)
        self.ui.add_object_pushButton.clicked.connect(self.add_objects)
        self.ui.structure_analysis_pushButton.clicked.connect(self.objects_histogram_analysis_plot)

        # menu trigger
        self.ui.actionDelete_inconsistencies.triggered.connect(self.delete_inconsistencies)
        self.ui.actionClean_database.triggered.connect(self.clean_database)
        self.ui.actionScale.triggered.connect(self.scale)
        self.ui.actionDetect_substations.triggered.connect(self.detect_substations)
        self.ui.actionDetect_facilities.triggered.connect(self.detect_facilities)

        # tree click
        self.ui.dataStructuresTreeView.clicked.connect(self.view_objects_data)

        # line edit enter
        self.ui.smart_search_lineEdit.returnPressed.connect(self.objects_smart_search)
        # self.ui.time_series_search.returnPressed.connect(self.timeseries_search)

        # context menu
        self.ui.dataStructureTableView.customContextMenuRequested.connect(self.show_objects_context_menu)

        # Set context menu policy to CustomContextMenu
        self.ui.dataStructureTableView.setContextMenuPolicy(QtGui.Qt.ContextMenuPolicy.CustomContextMenu)

        # wrap headers
        self.ui.dataStructureTableView.setHorizontalHeader(HeaderViewWithWordWrap(self.ui.dataStructureTableView))
        self.ui.profiles_tableView.setHorizontalHeader(HeaderViewWithWordWrap(self.ui.profiles_tableView))
        self.ui.associationsTableView.setHorizontalHeader(HeaderViewWithWordWrap(self.ui.associationsTableView))

        # combobox change
        self.ui.associationsComboBox.currentTextChanged.connect(self.display_associations)

    def setup_objects_tree(self):
        """
        Setup the database left tree object
        """
        icons = {
            "Regions": ":/Icons/icons/map.svg",
            DeviceType.CountryDevice.value: ":/Icons/icons/country.svg",
            DeviceType.CommunityDevice.value: ":/Icons/icons/community.svg",
            DeviceType.RegionDevice.value: ":/Icons/icons/region.svg",
            DeviceType.MunicipalityDevice.value: ":/Icons/icons/municipality.svg",
            DeviceType.AreaDevice.value: ":/Icons/icons/area.svg",
            DeviceType.ZoneDevice.value: ":/Icons/icons/zone.svg",

            "Substation": ":/Icons/icons/bus_icon.svg",
            DeviceType.SubstationDevice.value: ":/Icons/icons/substation.svg",
            DeviceType.VoltageLevelDevice.value: ":/Icons/icons/voltage_level.svg",
            DeviceType.BusBarDevice.value: ":/Icons/icons/bus_bar_icon.svg",
            DeviceType.ConnectivityNodeDevice.value: ":/Icons/icons/cn_icon.svg",
            DeviceType.BusDevice.value: ":/Icons/icons/bus_icon.svg",
            DeviceType.SwitchDevice.value: ":/Icons/icons/switch.svg",

            "Injections": ":/Icons/icons/add_load.svg",
            DeviceType.GeneratorDevice.value: ":/Icons/icons/gen.svg",
            DeviceType.BatteryDevice.value: ":/Icons/icons/batt.svg",
            DeviceType.LoadDevice.value: ":/Icons/icons/load_dev.svg",
            DeviceType.StaticGeneratorDevice.value: ":/Icons/icons/sta_gen.svg",
            DeviceType.ExternalGridDevice.value: ":/Icons/icons/external_grid.svg",
            DeviceType.ShuntDevice.value: ":/Icons/icons/shunt.svg",
            DeviceType.ControllableShuntDevice.value: ":/Icons/icons/controllable_shunt.svg",
            DeviceType.CurrentInjectionDevice.value: ":/Icons/icons/load_dev.svg",

            "Branches": ":/Icons/icons/reactance.svg",
            DeviceType.LineDevice.value: ":/Icons/icons/ac_line.svg",
            DeviceType.DCLineDevice.value: ":/Icons/icons/dc.svg",
            DeviceType.Transformer2WDevice.value: ":/Icons/icons/to_transformer.svg",
            DeviceType.WindingDevice.value: ":/Icons/icons/winding.svg",
            DeviceType.Transformer3WDevice.value: ":/Icons/icons/transformer3w.svg",
            DeviceType.SeriesReactanceDevice.value: ":/Icons/icons/reactance.svg",
            DeviceType.HVDCLineDevice.value: ":/Icons/icons/to_hvdc.svg",
            DeviceType.VscDevice.value: ":/Icons/icons/vsc.svg",
            DeviceType.UpfcDevice.value: ":/Icons/icons/upfc.svg",

            "Fluid": ":/Icons/icons/dam_gray.svg",
            DeviceType.FluidNodeDevice.value: ":/Icons/icons/fluid_node.svg",
            DeviceType.FluidPathDevice.value: ":/Icons/icons/fluid_path.svg",
            DeviceType.FluidTurbineDevice.value: ":/Icons/icons/fluid_turbine.svg",
            DeviceType.FluidPumpDevice.value: ":/Icons/icons/fluid_pump.svg",
            DeviceType.FluidP2XDevice.value: ":/Icons/icons/fluid_p2x.svg",

            "Groups": ":/Icons/icons/groups.svg",
            DeviceType.ContingencyGroupDevice.value: ":/Icons/icons/contingency_group.svg",
            DeviceType.ContingencyDevice.value: ":/Icons/icons/contingency.svg",
            DeviceType.RemedialActionGroupDevice.value: ":/Icons/icons/remedial_action_group.svg",
            DeviceType.RemedialActionDevice.value: ":/Icons/icons/remedial_action.svg",
            DeviceType.InvestmentsGroupDevice.value: ":/Icons/icons/investment_group.svg",
            DeviceType.InvestmentDevice.value: ":/Icons/icons/investment_dev.svg",
            DeviceType.BranchGroupDevice.value: ":/Icons/icons/branch_group.svg",
            DeviceType.ModellingAuthority.value: ":/Icons/icons/modelling_authority.svg",
            DeviceType.FacilityDevice.value: ":/Icons/icons/powerplant.svg",

            "Associations": ":/Icons/icons/associations.svg",
            DeviceType.Technology.value: ":/Icons/icons/technology.svg",
            DeviceType.FuelDevice.value: ":/Icons/icons/fuel.svg",
            DeviceType.EmissionGasDevice.value: ":/Icons/icons/emission.svg",

            "Catalogue": ":/Icons/icons/Catalogue.svg",
            DeviceType.WireDevice.value: ":/Icons/icons/ac_line.svg",
            DeviceType.OverheadLineTypeDevice.value: ":/Icons/icons/tower.svg",
            DeviceType.UnderGroundLineDevice.value: ":/Icons/icons/ac_line.svg",
            DeviceType.SequenceLineDevice.value: ":/Icons/icons/ac_line.svg",
            DeviceType.TransformerTypeDevice.value: ":/Icons/icons/to_transformer.svg",
        }

        db_tree_model = gf.get_tree_model(d=self.circuit.get_template_objects_str_dict(),
                                          top='Objects',
                                          icons=icons)

        self.ui.dataStructuresTreeView.setModel(db_tree_model)
        self.ui.dataStructuresTreeView.setRootIsDecorated(True)
        self.expand_object_tree_nodes()

    def setup_compiled_arrays_tree(self):
        """

        :return:
        """
        mdl = gf.get_tree_model(d=NumericalCircuit.available_structures,
                                top='Arrays')

        self.ui.simulationDataStructuresTreeView.setModel(mdl)

    def create_objects_model(self, elements, elm_type: DeviceType) -> ObjectsModel:
        """
        Generate the objects' table model
        :param elements: list of elements
        :param elm_type: name of DeviceType.BusDevice
        :return: QtCore.QAbstractTableModel
        """
        template_elm, dictionary_of_lists = self.circuit.get_dictionary_of_lists(elm_type=elm_type)

        mdl = ObjectsModel(objects=elements,
                           property_list=template_elm.property_list,
                           time_index=self.get_db_slider_index(),
                           parent=self.ui.dataStructureTableView,
                           editable=True,
                           dictionary_of_lists=dictionary_of_lists)

        return mdl

    def display_profiles(self):
        """
        Display profile
        """
        if self.circuit.time_profile is not None:

            dev_type_text = self.get_db_object_selected_type()

            if dev_type_text is not None:

                magnitudes, mag_types = self.circuit.profile_magnitudes.get(dev_type_text, (list(), list()))

                if len(magnitudes) > 0:
                    # get the enumeration univoque association with he device text
                    dev_type = self.circuit.device_type_name_dict[dev_type_text]

                    idx = self.ui.device_type_magnitude_comboBox.currentIndex()
                    magnitude = magnitudes[idx]
                    mtype = mag_types[idx]

                    elements = self.get_current_objects_model_view().objects

                    mdl = ProfilesModel(time_array=self.circuit.get_time_array(),
                                        elements=elements,
                                        device_type=dev_type,
                                        magnitude=magnitude,
                                        data_format=mtype,
                                        parent=self.ui.profiles_tableView)
                else:
                    mdl = None

                self.ui.profiles_tableView.setModel(mdl)
            else:
                self.ui.profiles_tableView.setModel(None)

    def display_associations(self):
        """
        Display the association table
        :return:
        """
        dev_type_text = self.get_db_object_selected_type()
        model = self.get_current_objects_model_view()
        association_prperty_name = self.ui.associationsComboBox.currentText()

        if dev_type_text is not None and model is not None and association_prperty_name != "":

            elements = model.objects

            if len(elements) > 0:

                gc_prop = elements[0].get_property_by_name(prop_name=association_prperty_name)
                associations: dev.Associations = elements[0].get_snapshot_value_by_name(name=association_prperty_name)
                associated_objects = self.circuit.get_elements_by_type(device_type=associations.device_type)
                self.ui.association_units_label.setText(gc_prop.units)

                if len(associated_objects) > 0:
                    mdl = AssociationsModel(objects=elements,
                                            associated_objects=associated_objects,
                                            gc_prop=gc_prop,
                                            table_view=self.ui.associationsTableView)

                    self.ui.associationsTableView.setModel(mdl)
                else:
                    self.ui.associationsTableView.setModel(None)
            else:
                self.ui.associationsTableView.setModel(None)
                self.ui.association_units_label.setText("")
        else:
            self.ui.associationsTableView.setModel(None)
            self.ui.association_units_label.setText("")

    def display_objects_filter(self, elements: List[ALL_DEV_TYPES]):
        """
        Display a list of elements that comes from a filter
        :param elements: list of devices
        """
        if len(elements) > 0:

            # display objects
            objects_mdl = self.create_objects_model(elements=elements, elm_type=elements[0].device_type)
            self.ui.dataStructureTableView.setModel(objects_mdl)

            # display time series
            self.display_profiles()

            # display associations
            self.display_associations()

        else:
            self.ui.dataStructureTableView.setModel(None)

    def copy_objects_data(self):
        """
        Copy the current displayed objects table to the clipboard
        """
        mdl = self.get_current_objects_model_view()
        if mdl is not None:
            mdl.copy_to_clipboard()
            print('Copied!')
        else:
            warning_msg('There is no data displayed, please display one', 'Copy profile to clipboard')

    def get_db_object_selected_type(self) -> Union[None, str]:
        """
        Get the selected object type in the database tree view
        :return:
        """
        indices = self.ui.dataStructuresTreeView.selectedIndexes()

        if len(indices) > 0:
            return indices[0].data(role=QtCore.Qt.ItemDataRole.DisplayRole)
        else:
            return None

    def view_objects_data(self):
        """
        On click, display the objects properties
        """

        if self.ui.dataStructuresTreeView.selectedIndexes()[0].parent().row() > -1:
            # if the clicked element has a valid parent...

            elm_type = self.get_db_object_selected_type()

            if elm_type is not None:

                elements = self.circuit.get_elements_by_type(device_type=DeviceType(elm_type))

                objects_mdl = self.create_objects_model(elements=elements, elm_type=DeviceType(elm_type))

                # update slice-view
                self.type_objects_list = elements
                self.ui.dataStructureTableView.setModel(objects_mdl)

                # update time series view
                ts_mdl = gf.get_list_model(self.circuit.profile_magnitudes[elm_type][0])
                self.ui.device_type_magnitude_comboBox.setModel(ts_mdl)
                self.ui.device_type_magnitude_comboBox_2.setModel(ts_mdl)

                # update the associations view
                assoc_mdl = gf.get_list_model(self.circuit.device_associations[elm_type])
                self.ui.associationsComboBox.setModel(assoc_mdl)
                self.display_associations()

            else:
                self.ui.dataStructureTableView.setModel(None)
                self.ui.device_type_magnitude_comboBox.clear()
                self.ui.device_type_magnitude_comboBox_2.clear()
                self.ui.associationsComboBox.clear()
                self.ui.dataStructureTableView.setModel(None)
        else:
            self.ui.dataStructureTableView.setModel(None)
            self.ui.device_type_magnitude_comboBox.clear()
            self.ui.device_type_magnitude_comboBox_2.clear()
            self.ui.associationsComboBox.clear()
            self.ui.dataStructureTableView.setModel(None)

    def get_selected_table_objects(self) -> List[ALL_DEV_TYPES]:
        """
        Get the list of selected objects
        :return: List[ALL_DEV_TYPES]
        """
        model = self.get_current_objects_model_view()

        if model is not None:
            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            if len(sel_idx) > 0:

                # get the unique rows
                unique = set()
                for idx in sel_idx:
                    unique.add(idx.row())

                return [model.objects[i] for i in unique]
            else:
                info_msg('Select some cells')
                return list()
        else:
            return list()

    def get_selected_table_buses(self) -> Tuple[Set[dev.Bus], List[ALL_DEV_TYPES]]:
        """
        Get the list of selected buses, regardless of the object table type
        If the object has buses, this one takes them
        :return:
        """
        model = self.ui.dataStructureTableView.model()
        buses = set()
        selected_objects: List[ALL_DEV_TYPES] = list()

        if model is not None:

            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.objects

            if len(objects) > 0:

                if len(sel_idx) > 0:

                    unique = {idx.row() for idx in sel_idx}

                    for idx in unique:

                        sel_obj: ALL_DEV_TYPES = model.objects[idx]
                        selected_objects.append(sel_obj)

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
                            sel = self.circuit.get_voltage_level_buses(vl=sel_obj)
                            for bus in sel:
                                buses.add(bus)

                        elif isinstance(sel_obj, dev.Substation):
                            root_bus = None
                            sel = self.circuit.get_substation_buses(substation=sel_obj)
                            for bus in sel:
                                buses.add(bus)

                        else:
                            root_bus = None

                        if root_bus is not None:
                            buses.add(root_bus)

        return buses, selected_objects

    def get_selected_substations(self) -> Tuple[Set[dev.Substation], List[ALL_DEV_TYPES]]:
        """
        Get the substations matching the table selection
        :return:  set of substations, list of selected objects originating the substation set
        """
        substations = set()
        selected_objects: List[ALL_DEV_TYPES] = list()

        model = self.ui.dataStructureTableView.model()

        elm2se = dict()

        # Associate country, community, region and municipality to substation
        for se in self.circuit.substations:
            for elm in [se.country, se.community, se.region, se.municipality]:
                if elm is not None:
                    if elm in elm2se:
                        elm2se[elm].append(se)
                    else:
                        elm2se[elm] = [se]

        # associate voltage levels to substations
        for vl in self.circuit.voltage_levels:
            if vl.substation is not None:
                elm2se[vl] = [vl.substation]

        # associate buses to substations
        for bus in self.circuit.buses:
            if bus.substation is not None:
                elm2se[bus] = [bus.substation]

        if model is not None:

            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.objects

            if len(objects) > 0:

                if len(sel_idx) > 0:

                    unique = {idx.row() for idx in sel_idx}

                    for idx in unique:

                        sel_obj: ALL_DEV_TYPES = model.objects[idx]
                        selected_objects.append(sel_obj)

                        se_list = elm2se.get(sel_obj, None)

                        if se_list is not None:
                            for se in se_list:
                                substations.add(se)

        return substations, selected_objects

    def delete_selected_objects(self):
        """
        Delete selection
        """

        selected_objects = self.get_selected_table_objects()

        if len(selected_objects):

            ok = yes_no_question('Are you sure that you want to delete the selected elements?', 'Delete')
            if ok:
                for obj in selected_objects:

                    # delete from the database
                    self.circuit.delete_element(obj=obj)

                    # delete from all diagrams
                    for diagram in self.diagram_widgets_list:
                        diagram.delete_diagram_element(device=obj, propagate=False)

                # update the view
                self.view_objects_data()
                self.update_from_to_list_views()
                self.update_date_dependent_combos()

    def duplicate_selected_objects(self):
        """
        Delete selection
        """

        selected_objects = self.get_selected_table_objects()

        if len(selected_objects):

            ok = yes_no_question('Are you sure that you want to duplicate the selected elements?',
                                 'Duplicate')
            if ok:
                for obj in selected_objects:
                    cpy = obj.copy(forced_new_idtag=True)
                    cpy.name += ' copy'
                    self.circuit.add_element(obj=cpy)

                # update the view
                self.view_objects_data()
                self.update_from_to_list_views()
                self.update_date_dependent_combos()

    def fuse_selected(self):
        """
        Fuse selection
        """

        selected_objects = self.get_selected_table_objects()

        if len(selected_objects):

            if selected_objects[0].device_type == DeviceType.SubstationDevice:

                ok = yes_no_question('Are you sure that you want to merge the selected substations?',
                                     'Merge')
                if ok:
                    # merge substations into the first
                    self.circuit.merge_substations(selected_objects=selected_objects)

                    # update the view
                    self.view_objects_data()
                    self.update_from_to_list_views()
                    self.update_date_dependent_combos()
            else:
                info_msg(f'Merge function not available for {selected_objects[0].device_type.value} devices')

    def copy_selected_idtag(self):
        """
        Copy selected idtags
        """

        selected_objects = self.get_selected_table_objects()

        if len(selected_objects):
            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            lst = list()
            cb.setText("\n".join([obj.idtag for obj in selected_objects]))

    def add_objects_to_current_diagram(self):
        """
        Add selected DB objects to current diagram
        """

        selected_objects = self.get_selected_table_objects()

        if len(selected_objects):

            diagram = self.get_selected_diagram_widget()
            logger = bs.Logger()

            if isinstance(diagram, SchematicWidget):
                injections_by_bus = self.circuit.get_injection_devices_grouped_by_bus()
                injections_by_fluid_node = self.circuit.get_injection_devices_grouped_by_fluid_node()

                for device in selected_objects:
                    diagram.add_object_to_the_schematic(elm=device,
                                                        injections_by_bus=injections_by_bus,
                                                        injections_by_fluid_node=injections_by_fluid_node,
                                                        logger=logger)

            elif isinstance(diagram, GridMapWidget):

                for device in selected_objects:
                    diagram.add_object_to_the_schematic(elm=device, logger=logger)

            if len(logger):
                dlg = LogsDialogue(name="Add selected DB objects to current diagram", logger=logger)
                dlg.setModal(True)
                dlg.exec()

    def add_new_bus_diagram_from_selection(self):
        """
        Create a New diagram from a buses selection
        """
        selected_buses, selected_objects = self.get_selected_table_buses()

        if len(selected_buses):
            diagram = make_diagram_from_buses(circuit=self.circuit,
                                              buses=selected_buses,
                                              name=selected_objects[0].name + " diagram")

            diagram_widget = SchematicWidget(gui=self,
                                             circuit=self.circuit,
                                             diagram=diagram,
                                             default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                                             time_index=self.get_diagram_slider_index(),
                                             call_delete_db_element_func=self.call_delete_db_element)

            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                diagram=diagram)
            self.set_diagrams_list_view()

    def add_new_map_from_database_selection(self):
        """
        Create a New map from a buses selection
        """
        selected_substations, selected_objects = self.get_selected_substations()

        if len(selected_substations):
            cmap_text = self.ui.palette_comboBox.currentText()
            cmap = self.cmap_dict[cmap_text]

            expand_outside = yes_no_question(text="Expand outside of the given selection using the branches?",
                                             title="Expand outside")

            diagram = make_diagram_from_substations(
                circuit=self.circuit,
                substations=selected_substations,
                use_flow_based_width=self.ui.branch_width_based_on_flow_checkBox.isChecked(),
                min_branch_width=self.ui.min_branch_size_spinBox.value(),
                max_branch_width=self.ui.max_branch_size_spinBox.value(),
                min_bus_width=self.ui.min_node_size_spinBox.value(),
                max_bus_width=self.ui.max_node_size_spinBox.value(),
                arrow_size=self.ui.arrow_size_size_spinBox.value(),
                palette=cmap,
                default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                expand_outside=expand_outside,
                name=f"{selected_objects[0].name} diagram"
            )

            default_tile_source = self.tile_name_dict[self.ui.tile_provider_comboBox.currentText()]
            tile_source = self.tile_name_dict.get(diagram.tile_source, default_tile_source)

            diagram_widget = GridMapWidget(
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

            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                diagram=diagram)
            self.set_diagrams_list_view()

    def crop_model_to_buses_selection(self):
        """
        Crop model to buses selection
        :return:
        """
        selected_buses, selected_objects = self.get_selected_table_buses()

        if len(selected_buses):

            ok = yes_no_question(text="This will delete all buses and their connected elements that were not selected."
                                      "This cannot be undone and it is dangerous if you don't know"
                                      "what you are doing. \nAre you sure?",
                                 title="Crop model to buses selection?")

            if ok:
                to_be_deleted = list()
                for bus in self.circuit.buses:
                    if bus not in selected_buses:
                        to_be_deleted.append(bus)

                for bus in to_be_deleted:
                    self.circuit.delete_bus(obj=bus, delete_associated=True)

    def add_objects(self):
        """
        Add default objects objects
        """
        model = self.get_current_objects_model_view()
        elm_type = self.get_db_object_selected_type()

        if model is not None and elm_type is not None:

            if elm_type == DeviceType.SubstationDevice.value:
                self.circuit.add_substation(dev.Substation(name=f'SE {self.circuit.get_substation_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.VoltageLevelDevice.value:
                self.circuit.add_voltage_level(dev.VoltageLevel(
                    name=f'VL {self.circuit.get_voltage_levels_number() + 1}')
                )
                self.update_from_to_list_views()

            elif elm_type == DeviceType.BusBarDevice.value:
                self.circuit.add_bus_bar(dev.BusBar(name=f'BB {self.circuit.get_bus_bars_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.ZoneDevice.value:
                self.circuit.add_zone(dev.Zone(name=f'Zone {self.circuit.get_zone_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.AreaDevice.value:
                self.circuit.add_area(dev.Area(name=f'Area {self.circuit.get_area_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.CountryDevice.value:
                self.circuit.add_country(dev.Country(name=f'Country {self.circuit.get_country_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.CommunityDevice.value:
                self.circuit.add_community(dev.Community(
                    name=f'Community {self.circuit.get_communities_number() + 1}')
                )
                self.update_from_to_list_views()

            elif elm_type == DeviceType.RegionDevice.value:
                self.circuit.add_region(dev.Region(name=f'Region {self.circuit.get_regions_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.MunicipalityDevice.value:
                self.circuit.add_municipality(dev.Municipality(
                    name=f'Municipalities {self.circuit.get_municipalities_number() + 1}')
                )
                self.update_from_to_list_views()

            elif elm_type == DeviceType.BusDevice.value:
                self.circuit.add_bus(dev.Bus(name=f'Bus {self.circuit.get_bus_number() + 1}'))

            elif elm_type == DeviceType.ContingencyGroupDevice.value:
                group = dev.ContingencyGroup(
                    name=f"Contingency group {self.circuit.get_contingency_groups_number() + 1}"
                )
                self.circuit.add_contingency_group(group)

            elif elm_type == DeviceType.RemedialActionGroupDevice.value:
                group = dev.RemedialActionGroup(
                    name=f"Remedial actions group {self.circuit.get_remedial_action_groups_number() + 1}"
                )
                self.circuit.add_remedial_action_group(group)

            elif elm_type == DeviceType.InvestmentsGroupDevice.value:
                group = dev.InvestmentsGroup(name=f"Investments group {len(self.circuit.investments_groups) + 1}")
                self.circuit.add_investments_group(group)

            elif elm_type == DeviceType.BranchGroupDevice.value:
                group = dev.BranchGroup(name=f"Branch group {self.circuit.get_branch_groups_number() + 1}")
                self.circuit.add_branch_group(group)

            elif elm_type == DeviceType.Technology.value:
                tech = dev.Technology(name=f"Technology {len(self.circuit.technologies) + 1}")
                self.circuit.add_technology(tech)

            elif elm_type == DeviceType.OverheadLineTypeDevice.value:

                obj = dev.OverheadLineType()
                obj.frequency = self.circuit.fBase
                obj.tower_name = f'Tower {len(self.circuit.overhead_line_types) + 1}'
                self.circuit.add_overhead_line(obj)

            elif elm_type == DeviceType.UnderGroundLineDevice.value:

                name = f'Cable {len(self.circuit.underground_cable_types) + 1}'
                obj = dev.UndergroundLineType(name=name)
                self.circuit.add_underground_line(obj)

            elif elm_type == DeviceType.SequenceLineDevice.value:

                name = f'Sequence line {len(self.circuit.sequence_line_types) + 1}'
                obj = dev.SequenceLineType(name=name)
                self.circuit.add_sequence_line(obj)

            elif elm_type == DeviceType.WireDevice.value:

                name = f'Wire {len(self.circuit.wire_types) + 1}'
                obj = dev.Wire(name=name, gmr=0.01, r=0.01, x=0)
                self.circuit.add_wire(obj)

            elif elm_type == DeviceType.TransformerTypeDevice.value:

                name = f'Transformer type {len(self.circuit.transformer_types) + 1}'
                obj = dev.TransformerType(hv_nominal_voltage=10, lv_nominal_voltage=0.4, nominal_power=2,
                                          copper_losses=0.8, iron_losses=0.1, no_load_current=0.1,
                                          short_circuit_voltage=0.1,
                                          gr_hv1=0.5, gx_hv1=0.5, name=name)
                self.circuit.add_transformer_type(obj)

            elif elm_type == DeviceType.FuelDevice.value:

                name = f'Fuel {len(self.circuit.fuels) + 1}'
                obj = dev.Fuel(name=name)
                self.circuit.add_fuel(obj)

            elif elm_type == DeviceType.EmissionGasDevice.value:

                name = f'Gas {len(self.circuit.emission_gases) + 1}'
                obj = dev.EmissionGas(name=name)
                self.circuit.add_emission_gas(obj)

            elif elm_type == DeviceType.ModellingAuthority.value:

                name = f'Modelling authority {self.circuit.get_modelling_authorities_number()}'
                obj = dev.ModellingAuthority(name=name)
                self.circuit.add_modelling_authority(obj)

            elif elm_type == DeviceType.FacilityDevice.value:

                name = f'Facility {self.circuit.get_facility_number()}'
                obj = dev.Facility(name=name)
                self.circuit.add_facility(obj)

            else:
                info_msg("This object does not support table-like addition.\nUse the schematic instead.")
                return

            # update the view
            self.view_objects_data()

    def launch_object_editor(self):
        """
        Edit catalogue element
        """
        model = self.get_current_objects_model_view()
        sel_item = self.ui.dataStructuresTreeView.selectedIndexes()[0]
        elm_type = sel_item.data(role=QtCore.Qt.ItemDataRole.DisplayRole)

        if model is not None:

            # get the selected index
            idx = self.ui.dataStructureTableView.currentIndex().row()

            if idx > -1:
                if elm_type == DeviceType.OverheadLineTypeDevice.value:

                    # launch editor
                    self.tower_builder_window = TowerBuilderGUI(
                        tower=self.circuit.overhead_line_types[idx],
                        wires_catalogue=self.circuit.wire_types
                    )
                    self.tower_builder_window.setModal(True)
                    self.tower_builder_window.resize(int(1.81 * 700.0), 700)
                    self.tower_builder_window.exec()

                else:

                    warning_msg('No editor available.\n'
                                'The values can be changed from the table or '
                                'via context menus in the graphical interface.',
                                'Edit')
            else:
                info_msg('Choose an element from the table')
        else:
            info_msg('Select a catalogue element and then a catalogue object')

    def set_value_to_column(self):
        """
        Set the value to all the column
        :return: Nothing
        """
        idx = self.ui.dataStructureTableView.currentIndex()
        mdl = self.get_current_objects_model_view()
        col = idx.column()
        if mdl is not None:
            if col > -1:
                mdl.copy_to_column(idx)
                # update the view
                self.view_objects_data()
            else:
                info_msg('Select some element to serve as source to copy', 'Set value to column')
        else:
            pass

    def highlight_selection_buses(self):
        """
        Highlight and select the buses of the selected objects
        """

        model = self.get_current_objects_model_view()

        if model is not None:

            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.objects

            if len(objects) > 0:

                if len(sel_idx) > 0:

                    unique = set()
                    for idx in sel_idx:
                        unique.add(idx.row())
                    sel_obj = list()
                    for idx in unique:
                        sel_obj.append(objects[idx])

                    elm = objects[0]

                    self.clear_big_bus_markers()
                    color = QtGui.QColor(55, 200, 171, 180)

                    if elm.device_type == DeviceType.BusDevice:

                        self.set_big_bus_marker(buses=sel_obj, color=color)

                    elif elm.device_type in [DeviceType.BranchDevice,
                                             DeviceType.LineDevice,
                                             DeviceType.Transformer2WDevice,
                                             DeviceType.HVDCLineDevice,
                                             DeviceType.VscDevice,
                                             DeviceType.DCLineDevice]:
                        buses = list()
                        for br in sel_obj:
                            buses.append(br.bus_from)
                            buses.append(br.bus_to)
                        self.set_big_bus_marker(buses=buses, color=color)

                    else:
                        buses = list()
                        for elm in sel_obj:
                            buses.append(elm.bus)
                        self.set_big_bus_marker(buses=buses, color=color)

                else:
                    info_msg('Select some elements to highlight', 'Highlight')
            else:
                pass

    def get_objects_time_index(self) -> Union[None, int]:
        """
        Get the time index of the objects slider already
        accouting for the -1 -> None converison
        :return: None or int
        """
        t_idx = self.ui.db_step_slider.value()
        if t_idx <= -1:
            return None
        else:
            return t_idx

    def get_current_objects_model_view(self) -> ObjectsModel:
        """
        Get the current ObjectsModel from the GUI
        :return: ObjectsModel
        """
        return self.ui.dataStructureTableView.model()

    def highlight_based_on_property(self):
        """
        Highlight and select the buses of the selected objects
        """
        indices = self.ui.dataStructureTableView.selectedIndexes()

        if len(indices):
            model = self.get_current_objects_model_view()
            t_idx = self.get_objects_time_index()

            if model is not None:
                objects = model.objects

                if len(objects) > 0:
                    col_indices = list({index.column() for index in indices})
                    elm = objects[0]
                    attr = model.attributes[col_indices[0]]
                    gc_prop = elm.registered_properties[attr]
                    if gc_prop is None:
                        info_msg(f"The proprty {attr} cannot be found :(", "Highlight based on property")
                        return

                    if gc_prop.tpe in [float, int]:

                        self.clear_big_bus_markers()

                        if elm.device_type == DeviceType.BusDevice:
                            # buses
                            buses = objects
                            values = [elm.get_value(prop=gc_prop, t_idx=t_idx) for elm in objects]

                        elif elm.device_type in [DeviceType.BranchDevice,
                                                 DeviceType.LineDevice,
                                                 DeviceType.DCLineDevice,
                                                 DeviceType.HVDCLineDevice,
                                                 DeviceType.Transformer2WDevice,
                                                 DeviceType.SwitchDevice,
                                                 DeviceType.VscDevice,
                                                 DeviceType.UpfcDevice]:
                            # Branches
                            buses = list()
                            values = list()
                            for br in objects:
                                gc_prop = br.registered_properties[attr]
                                buses.append(br.bus_from)
                                buses.append(br.bus_to)
                                val = elm.get_value(prop=gc_prop, t_idx=t_idx)
                                values.append(val)
                                values.append(val)

                        else:
                            # loads, generators, etc...
                            buses = list()
                            values = list()
                            for elm in objects:
                                gc_prop = elm.registered_properties[attr]
                                val = elm.get_value(prop=gc_prop, t_idx=t_idx)
                                buses.append(elm.bus)
                                values.append(val)

                        # build the color map
                        seq = [(0.0, 'gray'),
                               (0.5, 'orange'),
                               (1, 'red')]
                        cmap = LinearSegmentedColormap.from_list('lcolors', seq)
                        mx = max(values)

                        if mx != 0:

                            colors = np.zeros(len(values), dtype=object)
                            for i, value in enumerate(values):
                                r, g, b, a = cmap(value / mx)
                                colors[i] = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)

                            # color based on the value
                            self.set_big_bus_marker_colours(buses=buses, colors=colors, tool_tips=None)

                        else:
                            info_msg('The maximum value is 0, so the coloring cannot be applied',
                                     'Highlight based on property')
                    else:
                        info_msg('The selected property must be of a numeric type',
                                 'Highlight based on property')

                else:
                    pass

    def assign_to_profile(self):
        """
        Assign the snapshot values at the object DB to the profiles
        """
        indices = self.ui.dataStructureTableView.selectedIndexes()

        if len(indices):
            model = self.get_current_objects_model_view()

            if model is not None:
                logger = bs.Logger()

                t_idx = self.get_objects_time_index()

                for index in indices:
                    i = index.row()
                    p_idx = index.column()
                    elm = model.objects[i]
                    attr = model.attributes[p_idx]
                    gc_prop = elm.registered_properties[attr]
                    if gc_prop.has_profile():
                        val = elm.get_value(prop=gc_prop, t_idx=t_idx)
                        profile = elm.get_profile_by_prop(prop=gc_prop)
                        profile.fill(val)
                    else:
                        logger.add_error("No profile found for " + attr, device=elm.name)

                if logger.size():
                    logs_window = LogsDialogue("Assign to profile", logger=logger)
                    logs_window.exec()
        else:
            info_msg("Select a cell or a column first", "Assign to profile")

    def objects_histogram_analysis_plot(self):
        """
        Histogram analysis
        :return:
        """
        if len(self.ui.dataStructuresTreeView.selectedIndexes()) > 0:
            elm_type = self.ui.dataStructuresTreeView.selectedIndexes()[0].data(role=QtCore.Qt.ItemDataRole.DisplayRole)

            if len(self.circuit.get_elements_by_type(device_type=DeviceType(elm_type))):
                object_histogram_analysis(circuit=self.circuit,
                                          object_type=elm_type,
                                          t_idx=self.get_db_slider_index(),
                                          fig=None)
                plt.show()
        else:
            info_msg('Select a data structure')

    def timeseries_search(self):
        """

        :return:
        """

        initial_model = self.get_current_objects_model_view()

        if initial_model is not None:
            if len(initial_model.objects) > 0:

                obj_filter = flt.FilterTimeSeries(objects=initial_model.objects)

                try:
                    obj_filter.parse(expression=self.ui.time_series_search.text())
                    filtered_objects = obj_filter.apply()
                except ValueError as e:
                    error_msg(str(e), "Fiter parse")
                    return None

                self.display_objects_filter(filtered_objects)

            else:
                # nothing to search
                pass

    def objects_smart_search(self):
        """
        Objects and time series object-based filtering
        :return:
        """
        initial_model = self.get_current_objects_model_view()

        if initial_model is not None:
            if len(initial_model.objects) > 0:

                obj_filter = flt.FilterObjects(objects=initial_model.objects)

                try:
                    obj_filter.parse(expression=self.ui.smart_search_lineEdit.text())
                    filtered_objects = obj_filter.apply()
                except ValueError as e:
                    error_msg(str(e), "Fiter parse")
                    return None

                self.display_objects_filter(filtered_objects)

            else:
                # nothing to search
                pass

    def delete_inconsistencies(self):
        """
        Call delete shit
        :return:
        """
        ok = yes_no_question(
            "This action removes all disconnected devices with no active profile and remove all small islands",
            "Delete inconsistencies")

        if ok:
            logger = self.delete_shit()

            if len(logger) > 0:
                dlg = LogsDialogue("Delete inconsistencies", logger)
                dlg.setModal(True)
                dlg.exec()

    def delete_shit(self, min_island=1):
        """
        Delete small islands, disconnected stuff and other garbage
        """
        numerical_circuit_ = compile_numerical_circuit_at(circuit=self.circuit, )
        islands = numerical_circuit_.split_into_islands()
        logger = bs.Logger()
        buses_to_delete = list()
        buses_to_delete_idx = list()
        for island in islands:
            if island.nbus <= min_island:
                for r in island.original_bus_idx:
                    buses_to_delete.append(self.circuit.buses[r])
                    buses_to_delete_idx.append(r)

        for r, bus in enumerate(self.circuit.buses):
            if not bus.active and not np.any(bus.active_prof.toarray()):
                if r not in buses_to_delete_idx:
                    buses_to_delete.append(bus)
                    buses_to_delete_idx.append(r)

        # delete the grphics from all diagrams
        self.delete_from_all_diagrams(elements=buses_to_delete)

        for elm in buses_to_delete:
            logger.add_info("Deleted " + str(elm.device_type.value), elm.name)

        # search other elements to delete
        for dev_lst in [self.circuit.lines,
                        self.circuit.dc_lines,
                        self.circuit.vsc_devices,
                        self.circuit.hvdc_lines,
                        self.circuit.transformers2w,
                        self.circuit.get_generators(),
                        self.circuit.get_loads(),
                        self.circuit.get_shunts(),
                        self.circuit.get_batteries(),
                        self.circuit.get_static_generators()]:

            for elm in dev_lst:
                if not elm.active and not np.any(elm.active_prof.toarray()):
                    self.delete_from_all_diagrams(elements=[elm])
                    logger.add_info("Deleted " + str(elm.device_type.value), elm.name)

        return logger

    def clean_database(self):
        """
        Clean the DataBase
        """

        ok = yes_no_question("This action may delete unused objects and references, \nAre you sure?",
                             title="DB clean")

        if ok:
            logger = self.circuit.clean()

            if len(logger) > 0:
                dlg = LogsDialogue('DB clean logger', logger)
                dlg.exec()

    def scale(self):
        """
        Show the system scaler window
        The scaler window may modify the circuit
        """
        system_scaler_window = SystemScaler(grid=self.circuit, parent=self)
        system_scaler_window.exec()

    def detect_substations(self):
        """
        Call the detect substations logic
        """

        ok = yes_no_question("Do you want to try to detect substations and voltage levels in the grid model?",
                             "Detect substations")

        if ok:
            val = 1.0 / (10.0 ** self.ui.rxThresholdSpinBox.value())
            detect_substations(grid=self.circuit,
                               r_x_threshold=val)

    def detect_facilities(self):
        """
        Call the detect facilities logic
        """
        ok = yes_no_question("Do you want to try to detect facilities in the grid model?",
                             "Detect facilities")

        if ok:
            detect_facilities(grid=self.circuit)

    def show_objects_context_menu(self, pos: QtCore.QPoint):
        """
        Show diagrams list view context menu
        :param pos: Relative click position
        """
        context_menu = QtWidgets.QMenu(parent=self.ui.diagramsListView)

        gf.add_menu_entry(menu=context_menu,
                          text="Edit",
                          icon_path=":/Icons/icons/edit.svg",
                          function_ptr=self.launch_object_editor)

        gf.add_menu_entry(menu=context_menu,
                          text="Add",
                          icon_path=":/Icons/icons/plus.svg",
                          function_ptr=self.add_objects)

        gf.add_menu_entry(menu=context_menu,
                          text="Delete",
                          icon_path=":/Icons/icons/minus.svg",
                          function_ptr=self.delete_selected_objects)

        gf.add_menu_entry(menu=context_menu,
                          text="Duplicate object",
                          icon_path=":/Icons/icons/copy.svg",
                          function_ptr=self.duplicate_selected_objects)

        gf.add_menu_entry(menu=context_menu,
                          text="Merge",
                          icon_path=":/Icons/icons/fusion.svg",
                          function_ptr=self.fuse_selected)

        gf.add_menu_entry(menu=context_menu,
                          text="Copy idtag",
                          icon_path=":/Icons/icons/copy.svg",
                          function_ptr=self.copy_selected_idtag)

        gf.add_menu_entry(menu=context_menu,
                          text="Crop model to buses selection",
                          icon_path=":/Icons/icons/schematic.svg",
                          function_ptr=self.crop_model_to_buses_selection)

        gf.add_menu_entry(menu=context_menu,
                          text="Copy table",
                          icon_path=":/Icons/icons/copy.svg",
                          function_ptr=self.copy_objects_data)

        gf.add_menu_entry(menu=context_menu,
                          text="Set value to column",
                          icon_path=":/Icons/icons/copy2down.svg",
                          function_ptr=self.set_value_to_column)

        gf.add_menu_entry(menu=context_menu,
                          text="Assign to profile",
                          icon_path=":/Icons/icons/assign_to_profile.svg",
                          function_ptr=self.assign_to_profile)

        context_menu.addSeparator()

        gf.add_menu_entry(menu=context_menu,
                          text="New vicinity diagram",
                          icon_path=":/Icons/icons/grid_icon.svg",
                          function_ptr=self.add_bus_vicinity_diagram_from_model)

        gf.add_menu_entry(menu=context_menu,
                          text="New diagram from selection",
                          icon_path=":/Icons/icons/schematicadd_to.svg",
                          function_ptr=self.add_new_bus_diagram_from_selection)

        gf.add_menu_entry(menu=context_menu,
                          text="Add to current diagram",
                          icon_path=":/Icons/icons/schematicadd_to.svg",
                          function_ptr=self.add_objects_to_current_diagram)

        gf.add_menu_entry(menu=context_menu,
                          text="Highlight buses selection",
                          icon_path=":/Icons/icons/highlight.svg",
                          function_ptr=self.highlight_selection_buses)

        gf.add_menu_entry(menu=context_menu,
                          text="Highlight based on property",
                          icon_path=":/Icons/icons/highlight2.svg",
                          function_ptr=self.highlight_based_on_property)

        context_menu.addSeparator()

        gf.add_menu_entry(menu=context_menu,
                          text="New map from selection",
                          icon_path=":/Icons/icons/map.svg",
                          function_ptr=self.add_new_map_from_database_selection)

        # Convert global position to local position of the list widget
        mapped_pos = self.ui.dataStructureTableView.viewport().mapToGlobal(pos)
        context_menu.exec(mapped_pos)
