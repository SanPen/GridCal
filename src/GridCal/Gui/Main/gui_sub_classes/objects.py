# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from PySide6 import QtGui, QtCore
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
import GridCalEngine.Core.Devices as dev
import GridCal.Gui.GuiFunctions as gf
from GridCal.Gui.Analysis.object_plot_analysis import object_histogram_analysis
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg, info_msg
from GridCal.Gui.Main.gui_sub_classes.diagrams import DiagramsMain
from GridCal.Gui.TowerBuilder.LineBuilderDialogue import TowerBuilderGUI


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
        self.ui.setValueToColumnButton.clicked.connect(self.set_value_to_column)
        self.ui.filter_pushButton.clicked.connect(self.smart_search)
        self.ui.catalogue_edit_pushButton.clicked.connect(self.edit_from_catalogue)
        self.ui.copyObjectsTableButton.clicked.connect(self.copy_objects_data)
        self.ui.undo_pushButton.clicked.connect(self.undo)
        self.ui.redo_pushButton.clicked.connect(self.redo)
        self.ui.delete_selected_objects_pushButton.clicked.connect(self.delete_selected_objects)
        self.ui.add_object_pushButton.clicked.connect(self.add_objects)
        self.ui.highlight_selection_buses_pushButton.clicked.connect(self.highlight_selection_buses)
        self.ui.clear_highlight_pushButton.clicked.connect(self.clear_big_bus_markers)
        self.ui.highlight_by_property_pushButton.clicked.connect(self.highlight_based_on_property)
        self.ui.structure_analysis_pushButton.clicked.connect(self.objects_histogram_analysis_plot)

        # list click
        self.ui.dataStructuresTreeView.clicked.connect(self.view_objects_data)

        # line edit enter
        self.ui.smart_search_lineEdit.returnPressed.connect(self.smart_search)

    def create_objects_model(self, elements, elm_type: str) -> QtCore.QAbstractTableModel:
        """
        Generate the objects' table model
        :param elements: list of elements
        :param elm_type: name of dev.DeviceType.BusDevice
        :return: QtCore.QAbstractTableModel
        """
        dictionary_of_lists = dict()

        if elm_type == dev.DeviceType.BusDevice.value:
            elm = dev.Bus()
            dictionary_of_lists = {dev.DeviceType.AreaDevice.value: self.circuit.areas,
                                   dev.DeviceType.ZoneDevice.value: self.circuit.zones,
                                   dev.DeviceType.SubstationDevice.value: self.circuit.substations,
                                   dev.DeviceType.CountryDevice.value: self.circuit.countries,
                                   }

        elif elm_type == dev.DeviceType.BranchDevice.value:

            elm = dev.Branch(None, None)
            elements = list()

            # self.view_template_controls(True)

        elif elm_type == dev.DeviceType.LoadDevice.value:
            elm = dev.Load()

        elif elm_type == dev.DeviceType.StaticGeneratorDevice.value:
            elm = dev.StaticGenerator()

        elif elm_type == dev.DeviceType.GeneratorDevice.value:
            elm = dev.Generator()
            dictionary_of_lists = {dev.DeviceType.Technology.value: self.circuit.technologies,
                                   dev.DeviceType.FuelDevice.value: self.circuit.fuels,
                                   dev.DeviceType.EmissionGasDevice.value: self.circuit.emission_gases, }

        elif elm_type == dev.DeviceType.BatteryDevice.value:
            elm = dev.Battery()
            dictionary_of_lists = {dev.DeviceType.Technology.value: self.circuit.technologies, }

        elif elm_type == dev.DeviceType.ShuntDevice.value:
            elm = dev.Shunt()

        elif elm_type == dev.DeviceType.ExternalGridDevice.value:
            elm = dev.ExternalGrid()

        elif elm_type == dev.DeviceType.LineDevice.value:
            elm = dev.Line(None, None)

        elif elm_type == dev.DeviceType.Transformer2WDevice.value:
            elm = dev.Transformer2W(None, None)

        elif elm_type == dev.DeviceType.WindingDevice.value:
            elm = dev.Winding(None, None)

        elif elm_type == dev.DeviceType.Transformer3WDevice.value:
            elm = dev.Transformer3W()

        elif elm_type == dev.DeviceType.HVDCLineDevice.value:
            elm = dev.HvdcLine(None, None)

        elif elm_type == dev.DeviceType.VscDevice.value:
            elm = dev.VSC(None, None)

        elif elm_type == dev.DeviceType.UpfcDevice.value:
            elm = dev.UPFC(None, None)

        elif elm_type == dev.DeviceType.DCLineDevice.value:
            elm = dev.DcLine(None, None)

        elif elm_type == dev.DeviceType.SubstationDevice.value:
            elm = dev.Substation()

        elif elm_type == dev.DeviceType.ZoneDevice.value:
            elm = dev.Zone()

        elif elm_type == dev.DeviceType.AreaDevice.value:
            elm = dev.Area()

        elif elm_type == dev.DeviceType.CountryDevice.value:
            elm = dev.Country()

        elif elm_type == dev.DeviceType.ContingencyDevice.value:
            elm = dev.Contingency()
            dictionary_of_lists = {dev.DeviceType.ContingencyGroupDevice.value: self.circuit.contingency_groups, }

        elif elm_type == dev.DeviceType.ContingencyGroupDevice.value:
            elm = dev.ContingencyGroup()

        elif elm_type == dev.DeviceType.InvestmentDevice.value:
            elm = dev.Investment()
            dictionary_of_lists = {dev.DeviceType.InvestmentsGroupDevice.value: self.circuit.investments_groups, }

        elif elm_type == dev.DeviceType.InvestmentsGroupDevice.value:
            elm = dev.InvestmentsGroup()

        elif elm_type == dev.DeviceType.Technology.value:
            elm = dev.Technology()

        elif elm_type == dev.DeviceType.FuelDevice.value:
            elm = dev.Fuel()

        elif elm_type == dev.DeviceType.EmissionGasDevice.value:
            elm = dev.EmissionGas()

        elif elm_type == dev.DeviceType.WireDevice.value:
            elm = dev.Wire()

        elif elm_type == dev.DeviceType.OverheadLineTypeDevice.value:
            elm = dev.OverheadLineType()

        elif elm_type == dev.DeviceType.SequenceLineDevice.value:
            elm = dev.SequenceLineType()

        elif elm_type == dev.DeviceType.UnderGroundLineDevice.value:
            elm = dev.UndergroundLineType()

        elif elm_type == dev.DeviceType.TransformerTypeDevice.value:
            elm = dev.TransformerType()

        elif elm_type == dev.DeviceType.GeneratorTechnologyAssociation.value:
            elm = dev.GeneratorTechnology()
            dictionary_of_lists = {dev.DeviceType.GeneratorDevice.value: self.circuit.get_generators(),
                                   dev.DeviceType.Technology.value: self.circuit.technologies, }

        elif elm_type == dev.DeviceType.GeneratorFuelAssociation.value:
            elm = dev.GeneratorFuel()
            dictionary_of_lists = {dev.DeviceType.GeneratorDevice.value: self.circuit.get_generators(),
                                   dev.DeviceType.FuelDevice.value: self.circuit.fuels, }

        elif elm_type == dev.DeviceType.GeneratorEmissionAssociation.value:
            elm = dev.GeneratorEmission()
            dictionary_of_lists = {dev.DeviceType.GeneratorDevice.value: self.circuit.get_generators(),
                                   dev.DeviceType.EmissionGasDevice.value: self.circuit.emission_gases, }

        else:
            raise Exception('elm_type not understood: ' + elm_type)

        mdl = gf.ObjectsModel(elements, elm.editable_headers,
                              parent=self.ui.dataStructureTableView,
                              editable=True,
                              non_editable_attributes=elm.non_editable_attributes,
                              dictionary_of_lists=dictionary_of_lists)

        return mdl

    def display_filter(self, elements):
        """
        Display a list of elements that comes from a filter
        :param elements:
        """
        if len(elements) > 0:

            elm = elements[0]

            mdl = self.create_objects_model(elements=elements, elm_type=elm.device_type.value)

            self.ui.dataStructureTableView.setModel(mdl)

        else:
            self.ui.dataStructureTableView.setModel(None)

    def copy_objects_data(self):
        """
        Copy the current displayed objects table to the clipboard
        """
        mdl = self.ui.dataStructureTableView.model()
        if mdl is not None:
            mdl.copy_to_clipboard()
            print('Copied!')
        else:
            warning_msg('There is no data displayed, please display one', 'Copy profile to clipboard')

    def view_objects_data(self):
        """
        On click, display the objects properties
        """
        if self.ui.dataStructuresTreeView.selectedIndexes()[
            0].parent().row() > -1:  # if the clicked element has a valid parent

            elm_type = self.ui.dataStructuresTreeView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

            elements = self.circuit.get_elements_by_type(element_type=dev.DeviceType(elm_type))

            mdl = self.create_objects_model(elements=elements, elm_type=elm_type)

            self.type_objects_list = elements
            self.ui.dataStructureTableView.setModel(mdl)
            self.ui.property_comboBox.clear()
            self.ui.property_comboBox.addItems(mdl.attributes)
        else:
            self.ui.dataStructureTableView.setModel(None)
            self.ui.property_comboBox.clear()

    def delete_selected_objects(self):
        """
        Delete selection
        """

        model = self.ui.dataStructureTableView.model()

        if model is not None:
            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.objects

            if len(sel_idx) > 0:

                ok = yes_no_question('Are you sure that you want to delete the selected elements?', 'Delete')
                if ok:

                    # get the unique rows
                    unique = set()
                    for idx in sel_idx:
                        unique.add(idx.row())

                    unique = list(unique)
                    unique.sort(reverse=True)
                    for r in unique:

                        if objects[r].graphic_obj is not None:
                            # this is a more complete function than the circuit one because it removes the
                            # graphical items too, and for loads and generators it deletes them properly
                            objects[r].graphic_obj.remove(ask=False)
                        else:
                            # objects.pop(r)
                            self.circuit.delete_elements_by_type(obj=objects[r])

                    # update the view
                    self.display_filter(objects)
                    self.update_area_combos()
                    self.update_date_dependent_combos()
                else:
                    pass
            else:
                info_msg('Select some cells')
        else:
            pass

    def add_objects(self):
        """
        Add default objects objects
        """
        model = self.ui.dataStructureTableView.model()
        elm_type = self.ui.dataStructuresTreeView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

        if model is not None:

            if elm_type == dev.DeviceType.SubstationDevice.value:
                self.circuit.add_substation(dev.Substation('Default'))
                self.update_area_combos()

            elif elm_type == dev.DeviceType.ZoneDevice.value:
                self.circuit.add_zone(dev.Zone('Default'))
                self.update_area_combos()

            elif elm_type == dev.DeviceType.AreaDevice.value:
                self.circuit.add_area(dev.Area('Default'))
                self.update_area_combos()

            elif elm_type == dev.DeviceType.CountryDevice.value:
                self.circuit.add_country(dev.Country('Default'))
                self.update_area_combos()

            elif elm_type == dev.DeviceType.BusDevice.value:
                self.circuit.add_bus(dev.Bus(name='Bus ' + str(len(self.circuit.buses) + 1),
                                             area=self.circuit.areas[0],
                                             zone=self.circuit.zones[0],
                                             substation=self.circuit.substations[0],
                                             country=self.circuit.countries[0]))

            elif elm_type == dev.DeviceType.ContingencyGroupDevice.value:
                group = dev.ContingencyGroup(name="Contingency group " + str(len(self.circuit.contingency_groups) + 1))
                self.circuit.add_contingency_group(group)

            elif elm_type == dev.DeviceType.InvestmentsGroupDevice.value:
                group = dev.InvestmentsGroup(name="Investments group " + str(len(self.circuit.contingency_groups) + 1))
                self.circuit.add_investments_group(group)

            elif elm_type == dev.DeviceType.Technology.value:
                tech = dev.Technology(name="Technology " + str(len(self.circuit.technologies) + 1))
                self.circuit.add_technology(tech)

            elif elm_type == dev.DeviceType.OverheadLineTypeDevice.value:

                obj = dev.OverheadLineType()
                obj.frequency = self.circuit.fBase
                obj.tower_name = 'Tower ' + str(len(self.circuit.overhead_line_types))
                self.circuit.add_overhead_line(obj)

            elif elm_type == dev.DeviceType.UnderGroundLineDevice.value:

                name = 'Cable ' + str(len(self.circuit.underground_cable_types))
                obj = dev.UndergroundLineType(name=name)
                self.circuit.add_underground_line(obj)

            elif elm_type == dev.DeviceType.SequenceLineDevice.value:

                name = 'Sequence line ' + str(len(self.circuit.sequence_line_types))
                obj = dev.SequenceLineType(name=name)
                self.circuit.add_sequence_line(obj)

            elif elm_type == dev.DeviceType.WireDevice.value:

                name = 'Wire ' + str(len(self.circuit.wire_types))
                obj = dev.Wire(name=name, gmr=0.01, r=0.01, x=0)
                self.circuit.add_wire(obj)

            elif elm_type == dev.DeviceType.TransformerTypeDevice.value:

                name = 'Transformer type ' + str(len(self.circuit.transformer_types))
                obj = dev.TransformerType(hv_nominal_voltage=10, lv_nominal_voltage=0.4, nominal_power=2,
                                          copper_losses=0.8, iron_losses=0.1, no_load_current=0.1,
                                          short_circuit_voltage=0.1,
                                          gr_hv1=0.5, gx_hv1=0.5, name=name)
                self.circuit.add_transformer_type(obj)

            elif elm_type == dev.DeviceType.FuelDevice.value:

                name = 'Fuel ' + str(len(self.circuit.fuels))
                obj = dev.Fuel(name=name)
                self.circuit.add_fuel(obj)

            elif elm_type == dev.DeviceType.EmissionGasDevice.value:

                name = 'Gas ' + str(len(self.circuit.emission_gases))
                obj = dev.EmissionGas(name=name)
                self.circuit.add_emission_gas(obj)

            elif elm_type == dev.DeviceType.GeneratorTechnologyAssociation.value:

                obj = dev.GeneratorTechnology()
                self.circuit.add_generator_technology(obj)

            elif elm_type == dev.DeviceType.GeneratorFuelAssociation.value:

                obj = dev.GeneratorFuel()
                self.circuit.add_generator_fuel(obj)

            elif elm_type == dev.DeviceType.GeneratorEmissionAssociation.value:

                obj = dev.GeneratorEmission()
                self.circuit.add_generator_emission(obj)

            else:
                info_msg("This object does not support table-like addition.\nUse the schematic instead.")
                return

            # update the view
            self.view_objects_data()

    def edit_from_catalogue(self):
        """
        Edit catalogue element
        """
        model = self.ui.dataStructureTableView.model()
        sel_item = self.ui.dataStructuresTreeView.selectedIndexes()[0]
        elm_type = sel_item.data(role=QtCore.Qt.DisplayRole)

        if model is not None:

            # get the selected index
            idx = self.ui.dataStructureTableView.currentIndex().row()

            if idx > -1:
                if elm_type == dev.DeviceType.OverheadLineTypeDevice.value:

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

                    warning_msg('No editor available.\nThe values can be changes from within the table.',
                                'Transformers')
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
        mdl = self.ui.dataStructureTableView.model()  # is of type ObjectsModel
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

    def clear_big_bus_markers(self):
        """
        clear all the buses' "big marker"
        """
        for bus in self.circuit.buses:
            if bus.graphic_obj is not None:
                bus.graphic_obj.delete_big_marker()

    def highlight_selection_buses(self):
        """
        Highlight and select the buses of the selected objects
        """

        model = self.ui.dataStructureTableView.model()

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

                    if elm.device_type == dev.DeviceType.BusDevice:

                        self.set_big_bus_marker(buses=sel_obj, color=color)

                    elif elm.device_type in [dev.DeviceType.BranchDevice,
                                             dev.DeviceType.LineDevice,
                                             dev.DeviceType.Transformer2WDevice,
                                             dev.DeviceType.HVDCLineDevice,
                                             dev.DeviceType.VscDevice,
                                             dev.DeviceType.DCLineDevice]:
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

    def highlight_based_on_property(self):
        """
        Highlight and select the buses of the selected objects
        """

        model = self.ui.dataStructureTableView.model()

        if model is not None:
            objects = model.objects

            if len(objects) > 0:

                elm = objects[0]
                attr = self.ui.property_comboBox.currentText()
                tpe = elm.editable_headers[attr].tpe

                if tpe in [float, int]:

                    self.clear_big_bus_markers()

                    if elm.device_type == dev.DeviceType.BusDevice:
                        # buses
                        buses = objects
                        values = [getattr(elm, attr) for elm in objects]

                    elif elm.device_type in [dev.DeviceType.BranchDevice,
                                             dev.DeviceType.LineDevice,
                                             dev.DeviceType.DCLineDevice,
                                             dev.DeviceType.HVDCLineDevice,
                                             dev.DeviceType.Transformer2WDevice,
                                             dev.DeviceType.SwitchDevice,
                                             dev.DeviceType.VscDevice,
                                             dev.DeviceType.UpfcDevice]:
                        # Branches
                        buses = list()
                        values = list()
                        for br in objects:
                            buses.append(br.bus_from)
                            buses.append(br.bus_to)
                            val = getattr(br, attr)
                            values.append(val)
                            values.append(val)

                    else:
                        # loads, generators, etc...
                        buses = [elm.bus for elm in objects]
                        values = [getattr(elm, attr) for elm in objects]

                    # build the color map
                    seq = [(0.0, 'gray'),
                           (0.5, 'orange'),
                           (1, 'red')]
                    cmap = LinearSegmentedColormap.from_list('lcolors', seq)
                    mx = max(values)

                    if mx != 0:
                        # color based on the value
                        for bus, value in zip(buses, values):
                            if bus.graphic_obj is not None:
                                r, g, b, a = cmap(value / mx)
                                color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
                                bus.graphic_obj.add_big_marker(color=color)
                    else:
                        info_msg('The maximum value is 0, so the coloring cannot be applied',
                                 'Highlight based on property')
                else:
                    info_msg('The selected property must be of a numeric type',
                             'Highlight based on property')

            else:
                pass

    def objects_histogram_analysis_plot(self):
        """
        Histogram analysis
        :return:
        """
        if len(self.ui.dataStructuresTreeView.selectedIndexes()) > 0:
            elm_type = self.ui.dataStructuresTreeView.selectedIndexes()[0].data(role=QtCore.Qt.DisplayRole)

            object_histogram_analysis(circuit=self.circuit, object_type=elm_type, fig=None)
            plt.show()
        else:
            info_msg('Select a data structure')

    def undo(self):
        """
        Undo table changes
        """

        model = self.ui.profiles_tableView.model()
        if model is not None:
            model.undo()
        else:
            pass

    def redo(self):
        """
        redo table changes
        """
        model = self.ui.profiles_tableView.model()
        if model is not None:
            model.redo()
        else:
            pass

    def smart_search(self):
        """
        Filter
        """

        if len(self.type_objects_list) > 0:
            command = self.ui.smart_search_lineEdit.text().lower()
            attr = self.ui.property_comboBox.currentText()

            elm = self.type_objects_list[0]
            tpe = elm.editable_headers[attr].tpe

            filtered_objects = list()

            if command.startswith('>') and not command.startswith('>='):
                # greater than selection
                args = command.replace('>', '').strip()

                try:
                    args = tpe(args)
                except TypeError:
                    error_msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) > args]

            elif command.startswith('<') and not command.startswith('<='):
                # "less than" selection
                args = command.replace('<', '').strip()

                try:
                    args = tpe(args)
                except TypeError:
                    error_msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) < args]

            elif command.startswith('>='):
                # greater or equal than selection
                args = command.replace('>=', '').strip()

                try:
                    args = tpe(args)
                except TypeError:
                    error_msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) >= args]

            elif command.startswith('<='):
                # "less or equal than" selection
                args = command.replace('<=', '').strip()

                try:
                    args = tpe(args)
                except TypeError:
                    error_msg('Could not parse the argument for the data type')
                    return

                filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) <= args]

            elif command.startswith('*'):
                # "like" selection
                args = command.replace('*', '').strip()

                if tpe == str:

                    try:
                        args = tpe(args)
                    except TypeError:
                        error_msg('Could not parse the argument for the data type')
                        return

                    filtered_objects = [x for x in self.type_objects_list if args in getattr(x, attr).lower()]

                elif elm.device_type == dev.DeviceType.BusDevice:
                    filtered_objects = [x for x in self.type_objects_list if args in getattr(x, attr).name.lower()]

                else:
                    info_msg('This filter type is only valid for strings')

            elif command.startswith('='):
                # Exact match
                args = command.replace('=', '').strip()

                if tpe == str:

                    try:
                        args = tpe(args)
                    except TypeError:
                        error_msg('Could not parse the argument for the data type')
                        return

                    filtered_objects = [x for x in self.type_objects_list if getattr(x, attr).lower() == args]

                elif tpe == bool:

                    if args.lower() == 'true':
                        args = True
                    elif args.lower() == 'false':
                        args = False
                    else:
                        args = False

                    filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) == args]

                elif elm.device_type == dev.DeviceType.BusDevice:
                    filtered_objects = [x for x in self.type_objects_list if args == getattr(x, attr).name.lower()]

                else:
                    try:
                        filtered_objects = [x for x in self.type_objects_list if getattr(x, attr).name.lower() == args]
                    except:
                        filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) == args]

            elif command.startswith('!='):
                # Exact match
                args = command.replace('==', '').strip()

                if tpe == str:

                    try:
                        args = tpe(args)
                    except TypeError:
                        error_msg('Could not parse the argument for the data type')
                        return

                    filtered_objects = [x for x in self.type_objects_list if getattr(x, attr).lower() != args]

                elif elm.device_type == dev.DeviceType.BusDevice:
                    filtered_objects = [x for x in self.type_objects_list if args != getattr(x, attr).name.lower()]

                else:
                    filtered_objects = [x for x in self.type_objects_list if getattr(x, attr) != args]

            else:
                filtered_objects = self.type_objects_list

            self.display_filter(filtered_objects)

        else:
            # nothing to search
            pass