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
import numpy as np
from typing import Union, List
from PySide6 import QtGui, QtCore, QtWidgets
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from GridCal.Gui.associations_model import AssociationsModel
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit, compile_numerical_circuit_at
import GridCalEngine.basic_structures as bs
import GridCalEngine.Devices as dev
import GridCal.Gui.GuiFunctions as gf
from GridCal.Gui.object_model import ObjectsModel
from GridCal.Gui.profiles_model import ProfilesModel
import GridCalEngine.Utils.Filtering as flt
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.Topology.detect_substations import detect_substations
from GridCal.Gui.Analysis.object_plot_analysis import object_histogram_analysis
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg, info_msg
from GridCal.Gui.Main.SubClasses.Model.diagrams import DiagramsMain
from GridCal.Gui.TowerBuilder.LineBuilderDialogue import TowerBuilderGUI
from GridCal.Gui.GeneralDialogues import LogsDialogue
from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from GridCal.Gui.SystemScaler.system_scaler import SystemScaler


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

        self.ui.dataStructuresTreeView.setModel(gf.get_tree_model(self.circuit.get_objects_with_profiles_str_dict()))
        self.expand_object_tree_nodes()

        self.ui.simulationDataStructuresListView.setModel(gf.get_list_model(NumericalCircuit.available_structures))

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

        # tree click
        self.ui.dataStructuresTreeView.clicked.connect(self.view_objects_data)

        # line edit enter
        self.ui.smart_search_lineEdit.returnPressed.connect(self.objects_smart_search)
        # self.ui.time_series_search.returnPressed.connect(self.timeseries_search)

        # context menu
        self.ui.dataStructureTableView.customContextMenuRequested.connect(self.show_objects_context_menu)

        # Set context menu policy to CustomContextMenu
        self.ui.dataStructureTableView.setContextMenuPolicy(QtGui.Qt.ContextMenuPolicy.CustomContextMenu)

        # combobox change
        self.ui.associationsComboBox.currentTextChanged.connect(self.display_associations)

    def create_objects_model(self, elements, elm_type: DeviceType) -> ObjectsModel:
        """
        Generate the objects' table model
        :param elements: list of elements
        :param elm_type: name of DeviceType.BusDevice
        :return: QtCore.QAbstractTableModel
        """
        dictionary_of_lists = dict()

        if elm_type == DeviceType.BusDevice:
            elm = dev.Bus()
            dictionary_of_lists = {DeviceType.AreaDevice: self.circuit.get_areas(),
                                   DeviceType.ZoneDevice: self.circuit.get_zones(),
                                   DeviceType.SubstationDevice: self.circuit.get_substations(),
                                   DeviceType.VoltageLevelDevice: self.circuit.get_voltage_levels(),
                                   DeviceType.CountryDevice: self.circuit.get_countries(),
                                   }

        elif elm_type == DeviceType.LoadDevice:
            elm = dev.Load()

        elif elm_type == DeviceType.StaticGeneratorDevice:
            elm = dev.StaticGenerator()

        elif elm_type == DeviceType.ControllableShuntDevice:
            elm = dev.ControllableShunt()

        elif elm_type == DeviceType.CurrentInjectionDevice:
            elm = dev.CurrentInjection()

        elif elm_type == DeviceType.GeneratorDevice:
            elm = dev.Generator()
            dictionary_of_lists = {DeviceType.Technology: self.circuit.technologies,
                                   DeviceType.FuelDevice: self.circuit.get_fuels(),
                                   DeviceType.EmissionGasDevice: self.circuit.emission_gases, }

        elif elm_type == DeviceType.BatteryDevice:
            elm = dev.Battery()
            dictionary_of_lists = {DeviceType.Technology: self.circuit.technologies, }

        elif elm_type == DeviceType.ShuntDevice:
            elm = dev.Shunt()

        elif elm_type == DeviceType.ExternalGridDevice:
            elm = dev.ExternalGrid()

        elif elm_type == DeviceType.LineDevice:
            elm = dev.Line()
            dictionary_of_lists = {DeviceType.BranchGroupDevice: self.circuit.get_branch_groups()}

        elif elm_type == DeviceType.SwitchDevice:
            elm = dev.Switch()
            dictionary_of_lists = {DeviceType.BranchGroupDevice: self.circuit.get_branch_groups()}

        elif elm_type == DeviceType.Transformer2WDevice:
            elm = dev.Transformer2W()
            dictionary_of_lists = {DeviceType.BranchGroupDevice: self.circuit.get_branch_groups()}

        elif elm_type == DeviceType.WindingDevice:
            elm = dev.Winding()
            dictionary_of_lists = {DeviceType.BranchGroupDevice: self.circuit.get_branch_groups()}

        elif elm_type == DeviceType.Transformer3WDevice:
            elm = dev.Transformer3W()

        elif elm_type == DeviceType.HVDCLineDevice:
            elm = dev.HvdcLine()
            dictionary_of_lists = {DeviceType.BranchGroupDevice: self.circuit.get_branch_groups()}

        elif elm_type == DeviceType.VscDevice:
            elm = dev.VSC()
            dictionary_of_lists = {DeviceType.BranchGroupDevice: self.circuit.get_branch_groups()}

        elif elm_type == DeviceType.UpfcDevice:
            elm = dev.UPFC()
            dictionary_of_lists = {DeviceType.BranchGroupDevice: self.circuit.get_branch_groups()}

        elif elm_type == DeviceType.SeriesReactanceDevice:
            elm = dev.SeriesReactance()
            dictionary_of_lists = {DeviceType.BranchGroupDevice: self.circuit.get_branch_groups()}

        elif elm_type == DeviceType.DCLineDevice:
            elm = dev.DcLine()
            dictionary_of_lists = {DeviceType.BranchGroupDevice: self.circuit.get_branch_groups()}

        elif elm_type == DeviceType.SubstationDevice:
            elm = dev.Substation()
            dictionary_of_lists = {DeviceType.CountryDevice: self.circuit.get_countries(),
                                   DeviceType.CommunityDevice: self.circuit.get_communities(),
                                   DeviceType.RegionDevice: self.circuit.get_regions(),
                                   DeviceType.MunicipalityDevice: self.circuit.get_municipalities(),
                                   DeviceType.AreaDevice: self.circuit.get_areas(),
                                   DeviceType.ZoneDevice: self.circuit.get_zones(),
                                   }

        elif elm_type == DeviceType.ConnectivityNodeDevice:
            elm = dev.ConnectivityNode()
            dictionary_of_lists = {DeviceType.BusDevice: self.circuit.get_buses(),
                                   DeviceType.VoltageLevelDevice: self.circuit.get_voltage_levels(), }

        elif elm_type == DeviceType.BusBarDevice:
            elm = dev.BusBar()
            dictionary_of_lists = {DeviceType.VoltageLevelDevice: self.circuit.get_voltage_levels(), }

        elif elm_type == DeviceType.VoltageLevelDevice:
            elm = dev.VoltageLevel()
            dictionary_of_lists = {DeviceType.SubstationDevice: self.circuit.get_substations(), }

        elif elm_type == DeviceType.AreaDevice:
            elm = dev.Area()

        elif elm_type == DeviceType.ZoneDevice:
            elm = dev.Zone()
            dictionary_of_lists = {DeviceType.AreaDevice: self.circuit.get_areas(), }

        elif elm_type == DeviceType.CountryDevice:
            elm = dev.Country()

        elif elm_type == DeviceType.CommunityDevice:
            elm = dev.Community()
            dictionary_of_lists = {DeviceType.CountryDevice: self.circuit.get_countries(), }

        elif elm_type == DeviceType.RegionDevice:
            elm = dev.Region()
            dictionary_of_lists = {DeviceType.CommunityDevice: self.circuit.get_communities(), }

        elif elm_type == DeviceType.MunicipalityDevice:
            elm = dev.Municipality()
            dictionary_of_lists = {DeviceType.RegionDevice: self.circuit.get_regions(), }

        elif elm_type == DeviceType.ContingencyDevice:
            elm = dev.Contingency()
            dictionary_of_lists = {DeviceType.ContingencyGroupDevice: self.circuit.get_contingency_groups(), }

        elif elm_type == DeviceType.ContingencyGroupDevice:
            elm = dev.ContingencyGroup()

        elif elm_type == DeviceType.InvestmentDevice:
            elm = dev.Investment()
            dictionary_of_lists = {DeviceType.InvestmentsGroupDevice: self.circuit.investments_groups, }

        elif elm_type == DeviceType.InvestmentsGroupDevice:
            elm = dev.InvestmentsGroup()

        elif elm_type == DeviceType.BranchGroupDevice:
            elm = dev.BranchGroup()

        elif elm_type == DeviceType.Technology:
            elm = dev.Technology()

        elif elm_type == DeviceType.FuelDevice:
            elm = dev.Fuel()

        elif elm_type == DeviceType.EmissionGasDevice:
            elm = dev.EmissionGas()

        elif elm_type == DeviceType.WireDevice:
            elm = dev.Wire()

        elif elm_type == DeviceType.OverheadLineTypeDevice:
            elm = dev.OverheadLineType()

        elif elm_type == DeviceType.SequenceLineDevice:
            elm = dev.SequenceLineType()

        elif elm_type == DeviceType.UnderGroundLineDevice:
            elm = dev.UndergroundLineType()

        elif elm_type == DeviceType.TransformerTypeDevice:
            elm = dev.TransformerType()

        # elif elm_type == DeviceType.GeneratorTechnologyAssociation:
        #     elm = dev.GeneratorTechnology()
        #     dictionary_of_lists = {DeviceType.GeneratorDevice: self.circuit.get_generators(),
        #                            DeviceType.Technology: self.circuit.technologies, }
        #
        # elif elm_type == DeviceType.GeneratorFuelAssociation:
        #     elm = dev.GeneratorFuel()
        #     dictionary_of_lists = {DeviceType.GeneratorDevice: self.circuit.get_generators(),
        #                            DeviceType.FuelDevice: self.circuit.get_fuels(), }
        #
        # elif elm_type == DeviceType.GeneratorEmissionAssociation:
        #     elm = dev.GeneratorEmission()
        #     dictionary_of_lists = {DeviceType.GeneratorDevice: self.circuit.get_generators(),
        #                            DeviceType.EmissionGasDevice: self.circuit.emission_gases, }

        elif elm_type == DeviceType.FluidNodeDevice:
            elm = dev.FluidNode()
            # dictionary_of_lists = {DeviceType.FluidNodeDevice: self.circuit.get_fluid_nodes(), }

        elif elm_type == DeviceType.FluidPathDevice:
            elm = dev.FluidPath()
            dictionary_of_lists = {DeviceType.FluidNodeDevice: self.circuit.get_fluid_nodes(), }

        elif elm_type == DeviceType.FluidTurbineDevice:
            elm = dev.FluidTurbine()
            dictionary_of_lists = {DeviceType.FluidNodeDevice: self.circuit.get_fluid_nodes(),
                                   DeviceType.GeneratorDevice: self.circuit.get_generators(),
                                   }

        elif elm_type == DeviceType.FluidPumpDevice:
            elm = dev.FluidPump()
            dictionary_of_lists = {DeviceType.FluidNodeDevice: self.circuit.get_fluid_nodes(),
                                   DeviceType.GeneratorDevice: self.circuit.get_generators(),
                                   }

        elif elm_type == DeviceType.FluidP2XDevice:
            elm = dev.FluidP2x()
            dictionary_of_lists = {DeviceType.FluidNodeDevice: self.circuit.get_fluid_nodes(),
                                   DeviceType.GeneratorDevice: self.circuit.get_generators(),
                                   }

        elif elm_type == DeviceType.ModellingAuthority:
            elm = dev.ModellingAuthority()
            dictionary_of_lists = {}

        else:
            raise Exception(f'elm_type not understood: {elm_type.value}')

        mdl = ObjectsModel(objects=elements,
                           property_list=elm.property_list,
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

    def get_selected_objects(self) -> List[ALL_DEV_TYPES]:
        """
        Get the list of selected objects
        :return:
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

    def delete_selected_objects(self):
        """
        Delete selection
        """

        selected_objects = self.get_selected_objects()

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
                self.update_area_combos()
                self.update_date_dependent_combos()

    def add_objects_to_current_diagram(self):
        """
        Add selected DB objects to current diagram
        """

        selected_objects = self.get_selected_objects()

        if len(selected_objects):

            diagram = self.get_selected_diagram_widget()

            if isinstance(diagram, SchematicWidget):
                injections_by_bus = self.circuit.get_injection_devices_grouped_by_bus()
                injections_by_fluid_node = self.circuit.get_injection_devices_grouped_by_fluid_node()
                logger = bs.Logger()
                for device in selected_objects:
                    diagram.add_object_to_the_schematic(elm=device,
                                                        injections_by_bus=injections_by_bus,
                                                        injections_by_fluid_node=injections_by_fluid_node,
                                                        logger=logger)

                if len(logger):
                    dlg = LogsDialogue(name="Add selected DB objects to current diagram", logger=logger)
                    dlg.setModal(True)
                    dlg.exec()

    def add_objects(self):
        """
        Add default objects objects
        """
        model = self.get_current_objects_model_view()
        elm_type = self.get_db_object_selected_type()

        if model is not None and elm_type is not None:

            if elm_type == DeviceType.SubstationDevice.value:
                self.circuit.add_substation(dev.Substation(name=f'SE {self.circuit.get_substation_number() + 1}'))
                self.update_area_combos()

            elif elm_type == DeviceType.VoltageLevelDevice.value:
                self.circuit.add_voltage_level(dev.VoltageLevel(
                    name=f'VL {self.circuit.get_voltage_levels_number() + 1}')
                )
                self.update_area_combos()

            elif elm_type == DeviceType.BusBarDevice.value:
                self.circuit.add_bus_bar(dev.BusBar(name=f'BB {self.circuit.get_bus_bars_number() + 1}'))
                self.update_area_combos()

            elif elm_type == DeviceType.ZoneDevice.value:
                self.circuit.add_zone(dev.Zone(name=f'Zone {self.circuit.get_zone_number() + 1}'))
                self.update_area_combos()

            elif elm_type == DeviceType.AreaDevice.value:
                self.circuit.add_area(dev.Area(name=f'Area {self.circuit.get_area_number() + 1}'))
                self.update_area_combos()

            elif elm_type == DeviceType.CountryDevice.value:
                self.circuit.add_country(dev.Country(name=f'Country {self.circuit.get_country_number() + 1}'))
                self.update_area_combos()

            elif elm_type == DeviceType.CommunityDevice.value:
                self.circuit.add_community(dev.Community(
                    name=f'Community {self.circuit.get_communities_number() + 1}')
                )
                self.update_area_combos()

            elif elm_type == DeviceType.RegionDevice.value:
                self.circuit.add_region(dev.Region(name=f'Region {self.circuit.get_regions_number() + 1}'))
                self.update_area_combos()

            elif elm_type == DeviceType.MunicipalityDevice.value:
                self.circuit.add_municipality(dev.Municipality(
                    name=f'Municipalities {self.circuit.get_municipalities_number() + 1}')
                )
                self.update_area_combos()

            elif elm_type == DeviceType.BusDevice.value:
                self.circuit.add_bus(dev.Bus(name=f'Bus {self.circuit.get_bus_number() + 1}'))

            elif elm_type == DeviceType.ContingencyGroupDevice.value:
                group = dev.ContingencyGroup(name=f"Contingency group {len(self.circuit.get_contingency_groups()) + 1}")
                self.circuit.add_contingency_group(group)

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

            # elif elm_type == DeviceType.GeneratorTechnologyAssociation.value:
            #
            #     obj = dev.GeneratorTechnology()
            #     self.circuit.add_generator_technology(obj)
            #
            # elif elm_type == DeviceType.GeneratorFuelAssociation.value:
            #
            #     obj = dev.GeneratorFuel()
            #     self.circuit.add_generator_fuel(obj)
            #
            # elif elm_type == DeviceType.GeneratorEmissionAssociation.value:
            #
            #     obj = dev.GeneratorEmission()
            #     self.circuit.add_generator_emission(obj)

            elif elm_type == DeviceType.ModellingAuthority.value:

                name = f'Modelling authority {self.circuit.get_modelling_authorities_number()}'
                obj = dev.ModellingAuthority(name=name)
                self.circuit.add_modelling_authority(obj)

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

                    # pick the object
                    tower = self.circuit.overhead_line_types[idx]

                    # launch editor
                    self.tower_builder_window = TowerBuilderGUI(parent=self,
                                                                tower=tower,
                                                                wires_catalogue=self.circuit.wire_types)
                    self.tower_builder_window.resize(int(1.81 * 700.0), 700)
                    self.tower_builder_window.exec()
                    self.collect_memory()

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
        Call the detect substations logc
        """

        ok = yes_no_question("Do you want to try to detect substations and voltage levels in the grid model?",
                             "Detect substations")

        if ok:
            val = 1.0 / (10.0 ** self.ui.rxThresholdSpinBox.value())
            detect_substations(grid=self.circuit,
                               r_x_threshold=val)

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

        context_menu.addSeparator()

        gf.add_menu_entry(menu=context_menu,
                          text="New vecinity diagram",
                          icon_path=":/Icons/icons/grid_icon.svg",
                          function_ptr=self.add_bus_vecinity_diagram_from_model)

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

        # Convert global position to local position of the list widget
        mapped_pos = self.ui.dataStructureTableView.viewport().mapToGlobal(pos)
        context_menu.exec(mapped_pos)
