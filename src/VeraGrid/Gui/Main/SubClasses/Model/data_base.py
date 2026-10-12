# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from typing import Union, List, Set, Tuple, Dict
from PySide6 import QtGui, QtCore, QtWidgets

from VeraGrid.Gui.associations_model import AssociationsModel
from VeraGrid.Gui.table_view_header_wrap import HeaderViewWithWordWrap, VerticalHeaderWidthResizer
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGrid.Gui.Main.SubClasses.Model.compiled_arrays_model import CompiledArraysModule
from VeraGridEngine.Topology.VoltageLevels import vl_creation_common_functions as substation_wizards
import VeraGridEngine.basic_structures as bs
import VeraGridEngine.Devices as dev
import VeraGrid.Gui.gui_functions as gf
from VeraGrid.Gui.object_model import ObjectsModel
from VeraGrid.Gui.object_column_filter_dialog import ObjectColumnFilterDialog, set_line_edit_clear_action
from VeraGrid.Gui.object_proxy_model import ObjectModelFilterProxy
from VeraGrid.Gui.profiles_model import ProfilesModel
from VeraGrid.Gui.i18n import translate_tree_label
from VeraGridEngine.enumerations import DeviceType, DynamicSimulationMode, TimeSeriesSearchPoint, PrpCat
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Topology.detect_substations import detect_substations, detect_facilities
from VeraGrid.Gui.Analysis.object_plot_analysis import object_histogram_analysis
from VeraGrid.Gui.messages import yes_no_question, warning_msg, info_msg
from VeraGrid.Gui.Main.SubClasses.Model.diagrams import DIAGRAM_WIDGETS, DiagramsMain
from VeraGrid.Gui.DeviceEditors.TowerBuilder.LineBuilderDialogue import TowerBuilderGUI
from VeraGrid.Gui.DeviceEditors.UndergroundCableBuilder.underground_cable_builder import UndergroundCableBuilderGUI
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely, exec_dialog_safely, is_dialog_available
from VeraGrid.Gui.Visualization.visualization import NativeColorMap
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.FmuTemplateEditor.fmu_template_editor import FmuTemplateEditorDialog
from VeraGrid.Gui.ManufacturerNativeImporter.manufacturer_native_importer import ManufacturerNativeImporterDialog
from VeraGrid.Gui.SystemScaler.system_scaler import SystemScaler
from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget, generate_map_diagram
from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget, make_diagram_from_buses
from VeraGrid.Gui.GridReduce.grid_reduce import GridReduceDialogue
from VeraGrid.Gui.SubstationDesigner.substation_designer import SubstationDesigner
from VeraGrid.Gui.general_dialogues import (LogsDialogue, CustomQuestionDialogue, CheckListDialogue,
                                            NewConnectedDeviceDialogue, DeviceSelectorDialogue)
from VeraGrid.Gui.DeviceEditors.device_editor_factory import build_device_editor_dialog
from VeraGrid.Gui.Icons.icon_associations import device_type_icons


class DataBaseTableMain(DiagramsMain):
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

        # Tree proxy used to filter the visible database device tree while preserving source item payloads.
        self.device_tree_proxy_model: QtCore.QSortFilterProxyModel | None = None

        # Width-resize controller for the object table index/name header.
        self.db_table_index_resizer: VerticalHeaderWidthResizer | None = None

        # setup the objects tree
        self.setup_objects_tree()

        # setup the tree for compiled arrays
        self.setup_compiled_arrays_tree()

        ts_search_points_mdl = gf.ComboModel(
            enum_values=[TimeSeriesSearchPoint.HighestLoad,
                         TimeSeriesSearchPoint.LowestLoad],
            translate=self.tr
        )
        self.ui.goToTsPointComboBox.setModel(ts_search_points_mdl)

        self.ui.smart_search_lineEdit.setPlaceholderText(
            self.tr("Type the object name or a smart filter expression ...")
        )

        prop_filter_mdl = gf.ComboModel(
            icon_enum_values=[
                (PrpCat.All, ":/Icons/icons/edit.png"),
                (PrpCat.TP, ":/Icons/icons/automatic_layout.png"),
                (PrpCat.PF, ":/Icons/icons/pf.png"),
                (PrpCat.PF3, ":/Icons/icons/pf3.png"),
                (PrpCat.SC, ":/Icons/icons/short_circuit.png"),
                (PrpCat.OPF, ":/Icons/icons/dcopf.png"),
                (PrpCat.CON, ":/Icons/icons/otdf.png"),
                (PrpCat.REL, ":/Icons/icons/reliability.png"),
                (PrpCat.NTC, ":/Icons/icons/ntc_opf.png"),
                (PrpCat.INV, ":/Icons/icons/expansion_planning.png"),
                (PrpCat.RMS, ":/Icons/icons/dyn.png"),
                (PrpCat.EMT, ":/Icons/icons/dyn_emt.png"),
            ],
            translate=self.tr
        )
        self.ui.dbFilterComboBox.setModel(prop_filter_mdl)

        # Buttons
        self.ui.filter_pushButton.clicked.connect(self.objects_smart_search)
        self.ui.delete_selected_objects_pushButton.clicked.connect(self.delete_selected_db_table_objects)
        self.ui.add_object_pushButton.clicked.connect(self.add_objects)
        self.ui.structure_analysis_pushButton.clicked.connect(self.objects_histogram_analysis_plot)
        self.ui.goToTsPointButton.clicked.connect(self.search_ts_point)

        # menu trigger
        self.ui.actionDelete_inconsistencies.triggered.connect(self.delete_inconsistencies)
        self.ui.actionClean_database.triggered.connect(self.clean_database)
        self.ui.actionScale.triggered.connect(self.scale)
        self.ui.actionDetect_substations.triggered.connect(self.detect_substations)
        self.ui.actionDetect_facilities.triggered.connect(self.detect_facilities)
        self.ui.actionGrid_reduction.triggered.connect(self.grid_reduction_from_schematic_selection)
        self.ui.actionSubstation_wizard.triggered.connect(self.add_substation_with_wizard)
        self.ui.actionSet_model_x_y_based_on_lat_lon.triggered.connect(self.set_model_x_y_based_on_lat_lon)
        self.ui.actionRestore_investments.triggered.connect(self.restore_investments)

        # tree click
        self.ui.dataStructuresTreeView.clicked.connect(self.view_objects_data)
        self.ui.device_tree_search_lineEdit.textChanged.connect(self.on_device_tree_search_text_changed)
        set_line_edit_clear_action(line_edit=self.ui.device_tree_search_lineEdit)

        # line edit enter
        self.ui.smart_search_lineEdit.returnPressed.connect(self.objects_smart_search)

        # table click
        self.ui.dataStructureTableView.clicked.connect(self.on_data_structure_table_clicked)

        # context menu
        self.ui.dataStructureTableView.customContextMenuRequested.connect(self.show_objects_context_menu)

        # Set context menu policy to CustomContextMenu
        self.ui.dataStructureTableView.setContextMenuPolicy(QtGui.Qt.ContextMenuPolicy.CustomContextMenu)

        # wrap headers
        self.ui.dataStructureTableView.setHorizontalHeader(HeaderViewWithWordWrap(self.ui.dataStructureTableView))
        self.db_table_index_resizer = VerticalHeaderWidthResizer(table_view=self.ui.dataStructureTableView)
        self.ui.profiles_tableView.setHorizontalHeader(HeaderViewWithWordWrap(self.ui.profiles_tableView))
        self.ui.associationsTableView.setHorizontalHeader(HeaderViewWithWordWrap(self.ui.associationsTableView))
        self.ui.dataStructureTableView.horizontalHeader().setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.ui.dataStructureTableView.horizontalHeader().customContextMenuRequested.connect(
            self.show_object_column_filter_dialog
        )
        self.ui.dataStructureTableView.verticalHeader().setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.ui.dataStructureTableView.verticalHeader().customContextMenuRequested.connect(
            self.show_db_table_index_context_menu
        )

        # combobox change
        self.ui.associationsComboBox.currentTextChanged.connect(self.on_associations_combo_box_change)
        self.ui.dbFilterComboBox.currentIndexChanged.connect(self.view_objects_data)

    def setup_objects_tree(self):
        """
        Setup the database left tree object
        """

        db_tree_model: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
        db_tree_model.setHorizontalHeaderLabels([translate_tree_label('Objects')])

        root_item: QtGui.QStandardItem = db_tree_model.invisibleRootItem()
        grouped_device_types: Dict[str, List[DeviceType]] = self.circuit.get_template_objects_type_dict()
        device_labels: Dict[DeviceType, str] = {
            DeviceType.UndergroundCableTypeDevice: 'Cable',
            DeviceType.UnderGroundLineDevice: 'Cable System',
        }

        for group_name, device_types in grouped_device_types.items():
            # Category rows are only display nodes. Runtime selection is stored only on device leaves.
            group_item: QtGui.QStandardItem = QtGui.QStandardItem(translate_tree_label(str(group_name)))
            group_item.setEditable(False)
            root_item.appendRow(group_item)

            for device_type in device_types:
                # The displayed label can be translated while the enum payload remains stable.
                label: str = device_labels.get(device_type, str(device_type.value))
                device_item: QtGui.QStandardItem = QtGui.QStandardItem(translate_tree_label(label))
                device_item.setEditable(False)
                device_item.setData(device_type, QtCore.Qt.ItemDataRole.UserRole)

                icon_path: str | None = device_type_icons.get(device_type.value, None)
                if icon_path is not None:
                    icon: QtGui.QIcon = QtGui.QIcon()
                    icon.addPixmap(QtGui.QPixmap(icon_path))
                    device_item.setIcon(icon)
                else:
                    pass

                group_item.appendRow(device_item)

        device_tree_proxy_model: QtCore.QSortFilterProxyModel = QtCore.QSortFilterProxyModel(
            self.ui.dataStructuresTreeView)
        device_tree_proxy_model.setSourceModel(db_tree_model)
        device_tree_proxy_model.setRecursiveFilteringEnabled(True)
        device_tree_proxy_model.setAutoAcceptChildRows(True)
        device_tree_proxy_model.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        device_tree_proxy_model.setFilterKeyColumn(0)
        device_tree_proxy_model.setFilterFixedString(self.ui.device_tree_search_lineEdit.text())
        self.device_tree_proxy_model = device_tree_proxy_model

        self.ui.dataStructuresTreeView.setModel(device_tree_proxy_model)
        self.ui.dataStructuresTreeView.setRootIsDecorated(True)
        self.expand_object_tree_nodes()

    def on_device_tree_search_text_changed(self, text: str) -> None:
        """
        Filter the database device tree by the typed search text.

        :param text: Search text from ``device_tree_search_lineEdit``.
        :return: None.
        """
        if self.device_tree_proxy_model is not None:
            # The proxy filters display text only; item UserRole data still carries the DeviceType enum.
            self.device_tree_proxy_model.setFilterFixedString(text)
            self.expand_object_tree_nodes()
        else:
            pass

    def refresh_runtime_translations(self) -> None:
        """
        Refresh runtime-built database tree labels after one language change.

        :return: None.
        """
        super().refresh_runtime_translations()
        self.setup_objects_tree()

    def setup_compiled_arrays_tree(self):
        """

        :return:
        """
        mdl = gf.get_tree_model(d=CompiledArraysModule.available_structures,
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

        filter_prop = self.ui.dbFilterComboBox.currentData()

        mdl = ObjectsModel(
            objects=elements,
            property_list=list(template_elm.property_list),
            time_index=self.get_db_slider_index(),
            parent=self.ui.dataStructureTableView,
            editable=True,
            dictionary_of_lists=dictionary_of_lists,
            properties_filter=filter_prop,
            error_msg_ptr=self.show_error_toast
        )

        return mdl

    def display_profiles(self, proxy_mdl: ObjectModelFilterProxy):
        """
        Display profile
        :param proxy_mdl: ObjectModelFilterProxy used for the object's table
        """
        if self.circuit.time_profile is not None:

            dev_type: DeviceType | None = self.get_db_object_selected_type()

            if dev_type is not None:

                magnitudes, mag_types = self.circuit.profile_magnitudes.get(dev_type, (list(), list()))

                if len(magnitudes) > 0:
                    _, dictionary_of_lists = self.circuit.get_dictionary_of_lists(elm_type=dev_type)

                    idx = self.ui.device_type_magnitude_comboBox.currentIndex()
                    magnitude = magnitudes[idx]
                    mtype = mag_types[idx]

                    mdl = ProfilesModel(time_array=self.circuit.get_time_array(),
                                        elements=proxy_mdl.get_objects_in_display_order(),
                                        device_type=dev_type,
                                        magnitude=magnitude,
                                        data_format=mtype,
                                        dictionary_of_lists=dictionary_of_lists,
                                        parent=self.ui.profiles_tableView)
                    self.ui.profiles_tableView.setModel(mdl)
                else:
                    self.ui.profiles_tableView.setModel(None)
            else:
                self.ui.profiles_tableView.setModel(None)

    def display_associations(self, proxy_mdl: ObjectModelFilterProxy):
        """
        Display the association table
        :param proxy_mdl: ObjectModelFilterProxy used for the object's table
        :return:
        """
        dev_type: DeviceType | None = self.get_db_object_selected_type()
        association_property_name = self.ui.associationsComboBox.currentText()

        if dev_type is not None and proxy_mdl is not None and association_property_name != "":

            elements = proxy_mdl.get_objects_in_display_order()

            if len(elements) > 0:

                gc_prop = elements[0].get_property_by_name(prop_name=association_property_name)
                associations: dev.Associations = elements[0].get_snapshot_value_by_name(name=association_property_name)
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

    def on_associations_combo_box_change(self):
        """
        Triggered on self.ui.associationsComboBox.currentTextChanged
        """
        self.display_associations(proxy_mdl=self.get_current_objects_model_view())

    def copy_objects_data(self):
        """
        Copy the current displayed objects table to the clipboard
        """
        mdl: ObjectModelFilterProxy | None = self.get_current_objects_model_view()
        if mdl is not None:
            mdl.copy_to_clipboard()
            self.show_info_toast('Copied!')
        else:
            warning_msg(self.tr('There is no data displayed, please display one'), self.tr('Copy profile to clipboard'))

    def paste_objects_data(self) -> None:
        """
        Paste clipboard values into the current displayed objects table.

        :return: None.
        """
        mdl: ObjectModelFilterProxy | None = self.get_current_objects_model_view()

        if mdl is not None:
            selected_indexes: List[QtCore.QModelIndex] = self.ui.dataStructureTableView.selectedIndexes()

            if len(selected_indexes) > 0:
                rows: List[int] = sorted(set(index.row() for index in selected_indexes))
                cols: List[int] = sorted(set(index.column() for index in selected_indexes))
                row_idx: int = rows[0]
                col_idx: int = cols[0]
            else:
                rows = list()
                cols = list()
                row_idx = 0
                col_idx = 0

            pasted_cells: int = mdl.paste_from_clipboard(
                row_idx=row_idx,
                col_idx=col_idx,
                selected_rows=rows,
                selected_cols=cols,
            )

            if pasted_cells > 0:
                self.show_info_toast(self.tr('Pasted!'))
            else:
                self.show_warning_toast(self.tr('Nothing to paste'))
        else:
            warning_msg(self.tr('There is no data displayed, please display one'), self.tr('Paste data'))

    def get_db_object_selected_type(self) -> DeviceType | None:
        """
        Get the selected object type in the database tree view
        :return:
        """
        indices = self.ui.dataStructuresTreeView.selectedIndexes()

        if len(indices) > 0:
            item_data: object = indices[0].data(role=QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(item_data, DeviceType):
                return item_data
            else:
                return None
        else:
            return None

    def get_selected_objects_model(self) -> Tuple[ObjectsModel | None, List[ALL_DEV_TYPES] | None, DeviceType | None]:
        """
        Get the selected objects' model
        :return: ObjectsModel, list of objects, object type name
        """
        if len(self.ui.dataStructuresTreeView.selectedIndexes()) == 0:
            return None, None, None

        if self.ui.dataStructuresTreeView.selectedIndexes()[0].parent().row() > -1:
            # if the clicked element has a valid parent...

            elm_type: DeviceType | None = self.get_db_object_selected_type()

            if elm_type is not None:

                elements = self.circuit.get_elements_by_type(device_type=elm_type)

                objects_mdl = self.create_objects_model(elements=elements, elm_type=elm_type)

                return objects_mdl, elements, elm_type
            else:
                return None, None, None

        return None, None, None

    def view_objects_data(self):
        """
        On click, display the objects' properties
        """

        objects_mdl, elements, elm_type = self.get_selected_objects_model()

        if objects_mdl is not None:

            proxy = ObjectModelFilterProxy(mdl=objects_mdl)  # pass the same underlying list

            # update slice-view
            self.type_objects_list = elements
            self.ui.dataStructureTableView.setModel(proxy)
            if self.db_table_index_resizer is not None:
                self.db_table_index_resizer.reposition()
            else:
                pass

            # update time series view
            ts_mdl = gf.get_list_model(self.circuit.profile_magnitudes[elm_type][0])
            self.ui.device_type_magnitude_comboBox.setModel(ts_mdl)
            self.ui.device_type_magnitude_comboBox_2.setModel(ts_mdl)
            self.display_profiles(proxy_mdl=proxy)
            # the TS display will be triggered by the on-change event of the combobox

            # update the associations view
            assoc_mdl = gf.get_list_model(self.circuit.device_associations[elm_type])
            self.ui.associationsComboBox.setModel(assoc_mdl)
            self.display_associations(proxy_mdl=proxy)

        else:
            self.ui.dataStructureTableView.setModel(None)
            self.ui.device_type_magnitude_comboBox.clear()
            self.ui.device_type_magnitude_comboBox_2.clear()
            self.ui.associationsComboBox.clear()

    def show_object_column_filter_dialog(self, position: QtCore.QPoint) -> None:
        """
        Open the Excel-like filter popup for the clicked object table column.

        :param position: Header-local click position.
        :return: None.
        """
        model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()
        header: QtWidgets.QHeaderView = self.ui.dataStructureTableView.horizontalHeader()
        source_column: int = header.logicalIndexAt(position)

        if model is not None and source_column > -1:

            exec_dialog_safely(
                dialog=ObjectColumnFilterDialog(
                    proxy_model=model,
                    source_column=source_column,
                    table_view=self.ui.dataStructureTableView,
                    refresh_object_table_dependants_ptr=self.refresh_object_table_dependants,
                    global_position=header.mapToGlobal(position),
                    parent=self,
                )
            )
        else:
            pass

    def refresh_object_table_dependants(self) -> None:
        """
        Refresh views that consume the displayed object row order.

        :return: None.
        """
        proxy_model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()
        if proxy_model is not None:
            self.ui.dataStructureTableView.horizontalHeader().viewport().update()
            self.display_profiles(proxy_mdl=proxy_model)
            self.display_associations(proxy_mdl=proxy_model)
        else:
            pass

    def get_selected_table_buses(self) -> Tuple[Set[dev.Bus], List[ALL_DEV_TYPES]]:
        """
        Get the list of selected buses, regardless of the object table type
        If the object has buses, this one takes them
        :return:
        """
        proxy_model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()
        buses = set()
        selected_objects: List[ALL_DEV_TYPES] = list()

        if proxy_model is not None:

            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects: List[ALL_DEV_TYPES] = proxy_model.get_objects_in_display_order()

            if len(objects) > 0:

                if len(sel_idx) > 0:
                    unique = {idx.row() for idx in sel_idx}
                    selected_objects = proxy_model.get_objects_at_proxy_rows(proxy_rows=sorted(unique))

                    buses = self.circuit.get_buses_from_objects(elements=selected_objects,
                                                                dtype=objects[0].device_type)

        return buses, selected_objects

    def get_selected_table_substations(self) -> Tuple[Set[dev.Substation], List[ALL_DEV_TYPES]]:
        """
        Get the substations matching the table selection
        :return:  set of substations, list of selected objects originating the substation set
        """
        selected_objects = self.get_selected_db_table_objects()

        elm2se: Dict[ALL_DEV_TYPES, List[dev.Substation]] = dict()

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

        substations = set()
        for sel_obj in selected_objects:
            se_list = elm2se.get(sel_obj, None)
            if se_list is not None:
                for se in se_list:
                    substations.add(se)

        return substations, selected_objects

    def delete_selected_db_table_objects(self) -> None:
        """Delete every unblocked selection from the database and diagrams.

        Assets owns reference validation. This view reports general blockers
        and mutates diagrams only after the Engine deletion is permitted.

        :return: None.
        """
        selected_objects: List[ALL_DEV_TYPES] = self.get_selected_db_table_objects()
        if len(selected_objects) == 0:
            return
        else:
            pass

        confirmed: bool = yes_no_question(
            self.tr("Are you sure that you want to delete the selected elements?"),
            self.tr("Delete"),
        )
        if not confirmed:
            return
        else:
            pass

        deleted_count: int = 0
        obj: ALL_DEV_TYPES
        for obj in selected_objects:
            blockers: List[ALL_DEV_TYPES] = self.circuit.get_element_deletion_blockers(obj)
            if len(blockers) == 0:
                # Assets owns the deletion and reference policy.
                self.circuit.delete_element(obj=obj)
                deleted_count += 1

                # Diagrams follow only a deletion accepted by Assets.
                diagram: DIAGRAM_WIDGETS
                for diagram in self.diagram_widgets_list:
                    diagram.delete_element_utility_function(device=obj, propagate=False)
            else:
                blocker_names: str = ", ".join(blocker.name for blocker in blockers)
                warning_msg(
                    self.tr("The element is still referenced by: {names}").format(
                        names=blocker_names
                    ),
                    self.tr("Element in use"),
                )

        self.view_objects_data()
        self.update_from_to_list_views()
        self.update_date_dependent_combos()
        self.show_info_toast(f"{deleted_count} objects deleted")

    def duplicate_selected_db_table_objects(self):
        """
        Delete selection
        """

        selected_objects = self.get_selected_db_table_objects()

        if len(selected_objects):

            ok = yes_no_question(self.tr('Are you sure that you want to duplicate the selected elements?'),
                                 self.tr('Duplicate'))
            if ok:
                for obj in selected_objects:
                    cpy = obj.copy(forced_new_idtag=True)
                    cpy.name += ' copy'
                    self.circuit.add_element(obj=cpy)

                # update the view
                self.view_objects_data()
                self.update_from_to_list_views()
                self.update_date_dependent_combos()

    def fuse_selected_db_table_objects(self):
        """
        Fuse selection
        """

        selected_objects = self.get_selected_db_table_objects()

        if len(selected_objects):

            if selected_objects[0].device_type == DeviceType.SubstationDevice:

                ok = yes_no_question(self.tr('Are you sure that you want to merge the selected substations?'),
                                     self.tr('Merge'))
                if ok:
                    # merge substations into the first
                    self.circuit.merge_substations(selected_objects=selected_objects)

                    # update the view
                    self.view_objects_data()
                    self.update_from_to_list_views()
                    self.update_date_dependent_combos()

                    self.show_info_toast(f"{len(selected_objects)} substations merged")
            else:
                self.show_warning_toast(
                    f'Merge function not available for {selected_objects[0].device_type.value} devices')

    def copy_selected_idtag(self):
        """
        Copy selected idtags
        """

        selected_objects = self.get_selected_db_table_objects()

        if len(selected_objects):
            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText("\n".join([obj.idtag for obj in selected_objects]))

            self.show_info_toast("Copied!")

    def add_objects_to_current_diagram(self):
        """
        Add selected DB objects to current diagram
        """

        selected_objects = self.get_selected_db_table_objects()

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
                dlg = LogsDialogue(name=self.tr("Add selected DB objects to current diagram"),
                                   logger=logger, parent=self)
                dlg.setModal(True)
                exec_dialog_safely(dialog=dlg)

    def add_new_bus_diagram_from_selection(self):
        """
        Create a New diagram from a buses selection
        """
        selected_buses, selected_objects = self.get_selected_table_buses()

        if len(selected_buses):
            diagram = make_diagram_from_buses(circuit=self.circuit,
                                              buses=selected_buses,
                                              name=selected_objects[0].name + " diagram")

            diagram_widget = SchematicWidget(
                gui=self,
                diagram=diagram,
                default_bus_voltage=self.ui.defaultBusVoltageSpinBox.value(),
                time_index=self.get_diagram_slider_index()
            )

            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                diagram=diagram)
            self.set_diagrams_list_view()

            self.show_info_toast(f"{diagram.name} added")

    def add_new_map_from_database_selection(self):
        """
        Create a New map from a buses selection
        """

        # from whatever, get the selected substations
        selected_buses, selected_objects = self.get_selected_table_buses()

        if len(selected_buses):

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

            new_se_dlg: CheckListDialogue = CheckListDialogue(
                objects_list=[e.value for e in tpes]
            )

            if self.circuit.get_substation_number() > 0:
                # showing this menu only makes sense if there is anything there
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
            else:
                self.show_warning_toast("No substations to draw...")
                return

            cmap = self.ui.palette_comboBox.currentData()
            subgrid = self.circuit.slice_buses(buses=list(selected_buses))

            diagram = generate_map_diagram(
                substations=subgrid.get_substations() if show_substations else list(),
                voltage_levels=subgrid.get_voltage_levels() if show_substations else list(),
                lines=subgrid.get_lines() if show_lines else list(),
                dc_lines=subgrid.get_dc_lines() if show_dc_lines else list(),
                hvdc_lines=subgrid.get_hvdc() if show_hvdc_lines else list(),
                fluid_nodes=subgrid.get_fluid_nodes(),
                fluid_paths=subgrid.get_fluid_paths(),
                external_grids=subgrid.external_grids if show_external_grids else list(),
                static_generators=subgrid.static_generators if show_static_generators else list(),
                loads=subgrid.loads if show_loads else list(),
                batteries=subgrid.batteries if show_batteries else list(),
                generators=subgrid.generators if show_generators else list(),
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

            default_tile_source = self.ui.tile_provider_comboBox.currentData()
            tile_source = self.tile_name_dict.get(diagram.tile_source, default_tile_source)

            diagram_widget = GridMapWidget(
                gui=self,
                tile_src=tile_source,
                start_level=diagram.start_level,
                longitude=diagram.longitude,
                latitude=diagram.latitude,
                name=diagram.name,
                diagram=diagram,
            )

            self.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                diagram=diagram)
            self.set_diagrams_list_view()

            self.show_info_toast(f"{diagram.name} added")

    def crop_model_to_buses_selection(self):
        """
        Crop model to buses selection
        :return:
        """
        selected_buses, selected_objects = self.get_selected_table_buses()

        if len(selected_buses):

            ok = yes_no_question(
                text=self.tr("This will delete all buses and their connected elements that were not selected."
                             "This cannot be undone and it is dangerous if you don't know"
                             "what you are doing. \nAre you sure?"),
                title=self.tr("Crop model to buses selection?"))

            if ok:
                to_be_deleted = list()
                for bus in self.circuit.buses:
                    if bus not in selected_buses:
                        to_be_deleted.append(bus)

                for bus in to_be_deleted:
                    self.circuit.delete_bus(obj=bus, delete_associated=True)

                self.view_objects_data()  # re-paint the table

                self.show_info_toast(f"{len(to_be_deleted)} buses removed from the model")

    def grid_reduction_from_table_selection(self) -> None:
        """
        Crop model to buses selection
        """
        selected_buses, selected_objects = self.get_selected_table_buses()

        if len(selected_buses):
            grid_reduction_dialogue: GridReduceDialogue = GridReduceDialogue(grid=self.circuit,
                                                                             session=self.session,
                                                                             selected_buses_set=selected_buses)

            try:
                exec_dialog_safely(dialog=grid_reduction_dialogue)
                did_reduce: bool = grid_reduction_dialogue.did_reduce
                reduction_logger: bs.Logger = grid_reduction_dialogue.logger
                reduced_grid: dev.MultiCircuit | None = grid_reduction_dialogue.reduced_grid
            finally:
                delete_dialog_safely(dialog=grid_reduction_dialogue)

            if did_reduce and reduced_grid is not None:

                self.set_circuit(grid=reduced_grid, create_diagram=True)

                # update the view
                self.view_objects_data()
                self.update_from_to_list_views()
                self.update_date_dependent_combos()

                if reduction_logger.has_logs():
                    logs_dialogue: LogsDialogue = LogsDialogue(name=self.tr("Grid reduction"),
                                                               logger=reduction_logger, parent=self)
                    exec_dialog_safely(dialog=logs_dialogue)
                else:
                    pass
            else:
                self.show_warning_toast("No reduction done")
                if reduction_logger.has_logs():
                    logs_dialogue: LogsDialogue = LogsDialogue(name=self.tr("Grid reduction"),
                                                               logger=reduction_logger, parent=self)
                    exec_dialog_safely(dialog=logs_dialogue)
                else:
                    pass
        else:
            self.show_warning_toast("Select some elements first")

    def grid_reduction_from_schematic_selection(self) -> None:
        """
        Call the grid reduction dialogue on the schematic selection
        """

        diagram_widget: SchematicWidget | GridMapWidget | None = self.get_selected_diagram_widget()
        if isinstance(diagram_widget, SchematicWidget):
            self.remove_dead_graphics_from_all_diagrams()
            selected_buses: List[Tuple[int, dev.Bus, object]] = diagram_widget.get_selected_buses()

        elif isinstance(diagram_widget, GridMapWidget):
            self.remove_dead_graphics_from_all_diagrams()
            selected_buses = diagram_widget.get_selected_buses()
        else:
            return

        if len(selected_buses):
            selected_buses_set: Set[dev.Bus] = {bus for i, bus, graphic in selected_buses}

            grid_reduction_dialogue: GridReduceDialogue = GridReduceDialogue(
                grid=self.circuit,
                session=self.session,
                selected_buses_set=selected_buses_set
            )

            try:
                exec_dialog_safely(dialog=grid_reduction_dialogue)
                did_reduce: bool = grid_reduction_dialogue.did_reduce
                reduction_logger: bs.Logger = grid_reduction_dialogue.logger
                reduced_grid: dev.MultiCircuit | None = grid_reduction_dialogue.reduced_grid
            finally:
                delete_dialog_safely(dialog=grid_reduction_dialogue)

            if did_reduce and reduced_grid is not None:
                self.set_circuit(grid=reduced_grid, create_diagram=True)
                self.show_info_toast("Done!")

                if reduction_logger.has_logs():
                    logs_dialogue: LogsDialogue = LogsDialogue(name=self.tr("Grid reduction"),
                                                               logger=reduction_logger, parent=self)
                    exec_dialog_safely(dialog=logs_dialogue)
                else:
                    pass
            else:
                self.show_warning_toast("No reduction done")
                if reduction_logger.has_logs():
                    logs_dialogue: LogsDialogue = LogsDialogue(name=self.tr("Grid reduction"),
                                                               logger=reduction_logger, parent=self)
                    exec_dialog_safely(dialog=logs_dialogue)
                else:
                    pass

            return
        else:
            self.show_warning_toast("No selected buses :/")
            return

    def add_objects(self):
        """
        Add default objects objects
        """
        model = self.get_current_objects_model_view()
        elm_type: DeviceType | None = self.get_db_object_selected_type()

        if model is not None and elm_type is not None:

            if elm_type == DeviceType.LoadDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.loads) + 1}',
                        bus_count=1,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None:
                            obj: dev.Load = dev.Load(name=dlg.get_name())
                            obj.bus = selected_buses[0]
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.StaticGeneratorDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.static_generators) + 1}',
                        bus_count=1,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None:
                            obj: dev.StaticGenerator = dev.StaticGenerator(name=dlg.get_name())
                            obj.bus = selected_buses[0]
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.GeneratorDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.generators) + 1}',
                        bus_count=1,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None:
                            obj: dev.Generator = dev.Generator(name=dlg.get_name())
                            obj.bus = selected_buses[0]
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.BatteryDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.batteries) + 1}',
                        bus_count=1,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None:
                            obj: dev.Battery = dev.Battery(name=dlg.get_name())
                            obj.bus = selected_buses[0]
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.ShuntDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.shunts) + 1}',
                        bus_count=1,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None:
                            obj: dev.Shunt = dev.Shunt(name=dlg.get_name())
                            obj.bus = selected_buses[0]
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.ExternalGridDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.external_grids) + 1}',
                        bus_count=1,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None:
                            obj: dev.ExternalGrid = dev.ExternalGrid(name=dlg.get_name())
                            obj.bus = selected_buses[0]
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.CurrentInjectionDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.current_injections) + 1}',
                        bus_count=1,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None:
                            obj: dev.CurrentInjection = dev.CurrentInjection(name=dlg.get_name())
                            obj.bus = selected_buses[0]
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.ControllableShuntDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.controllable_shunts) + 1}',
                        bus_count=1,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None:
                            obj: dev.ControllableShunt = dev.ControllableShunt(name=dlg.get_name())
                            obj.bus = selected_buses[0]
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.LineDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.lines) + 1}',
                        bus_count=2,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None and selected_buses[1] is not None:
                            obj: dev.Line = dev.Line(name=dlg.get_name(),
                                                     bus_from=selected_buses[0],
                                                     bus_to=selected_buses[1])
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.DCLineDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.dc_lines) + 1}',
                        bus_count=2,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None and selected_buses[1] is not None:
                            obj: dev.DcLine = dev.DcLine(name=dlg.get_name(),
                                                         bus_from=selected_buses[0],
                                                         bus_to=selected_buses[1])
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.Transformer2WDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.transformers2w) + 1}',
                        bus_count=2,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None and selected_buses[1] is not None:
                            obj: dev.Transformer2W = dev.Transformer2W(name=dlg.get_name(),
                                                                       bus_from=selected_buses[0],
                                                                       bus_to=selected_buses[1])
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.Transformer3WDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.transformers3w) + 1}',
                        bus_count=3,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None and selected_buses[1] is not None and selected_buses[
                            2] is not None:
                            obj: dev.Transformer3W = dev.Transformer3W(name=dlg.get_name(),
                                                                       bus1=selected_buses[0],
                                                                       bus2=selected_buses[1],
                                                                       bus3=selected_buses[2])
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.TransformerNwDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.transformers_nw) + 1}',
                        bus_count=3,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None and selected_buses[1] is not None and selected_buses[
                            2] is not None:
                            obj: dev.TransformerNW = dev.TransformerNW(name=dlg.get_name(),
                                                                       winding_count=len(selected_buses),
                                                                       buses=selected_buses)
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.HVDCLineDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.hvdc_lines) + 1}',
                        bus_count=2,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None and selected_buses[1] is not None:
                            obj: dev.HvdcLine = dev.HvdcLine(name=dlg.get_name(),
                                                             bus_from=selected_buses[0],
                                                             bus_to=selected_buses[1])
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.VscDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.vsc_devices) + 1}',
                        bus_count=3,
                        buses=buses,
                        parent=self,
                        allow_last_bus_none=True,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None and selected_buses[1] is not None:
                            bus_from: ALL_DEV_TYPES = selected_buses[0]
                            bus_to: ALL_DEV_TYPES = selected_buses[1]
                            bus_dc_n: ALL_DEV_TYPES | None = selected_buses[2]

                            if isinstance(bus_from, dev.Bus) and isinstance(bus_to, dev.Bus):
                                has_ac_dc_pair: bool = bus_from.is_dc != bus_to.is_dc

                                if bus_dc_n is None:
                                    has_valid_dc_negative_bus: bool = True
                                elif isinstance(bus_dc_n, dev.Bus):
                                    has_valid_dc_negative_bus = bus_dc_n.is_dc
                                else:
                                    has_valid_dc_negative_bus = False

                                if has_ac_dc_pair and has_valid_dc_negative_bus:
                                    obj: dev.VSC = dev.VSC(name=dlg.get_name(),
                                                           bus_from=bus_from,
                                                           bus_to=bus_to,
                                                           bus_dc_n=bus_dc_n)
                                    self.circuit.add_element(obj=obj)
                                else:
                                    self.show_warning_toast(
                                        self.tr("VSC devices need one AC bus, one DC bus, and an optional DC bus.")
                                    )
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.UpfcDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.upfc_devices) + 1}',
                        bus_count=2,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None and selected_buses[1] is not None:
                            obj: dev.UPFC = dev.UPFC(name=dlg.get_name(),
                                                     bus_from=selected_buses[0],
                                                     bus_to=selected_buses[1])
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.SeriesReactanceDevice:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: NewConnectedDeviceDialogue = NewConnectedDeviceDialogue(
                        name=f'{elm_type.value} {len(self.circuit.series_reactances) + 1}',
                        bus_count=2,
                        buses=buses,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_buses: List[ALL_DEV_TYPES | None] = dlg.get_buses()
                        if selected_buses[0] is not None and selected_buses[1] is not None:
                            obj: dev.SeriesReactance = dev.SeriesReactance(name=dlg.get_name(),
                                                                           bus_from=selected_buses[0],
                                                                           bus_to=selected_buses[1])
                            self.circuit.add_element(obj=obj)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.SubstationDevice:
                self.circuit.add_substation(dev.Substation(name=f'SE {self.circuit.get_substation_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.VoltageLevelDevice:
                self.circuit.add_voltage_level(dev.VoltageLevel(
                    name=f'VL {self.circuit.get_voltage_levels_number() + 1}')
                )
                self.update_from_to_list_views()

            elif elm_type == DeviceType.BusBarDevice:
                self.circuit.add_bus_bar(dev.BusBar(name=f'BB {self.circuit.get_bus_bars_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.ZoneDevice:
                self.circuit.add_zone(dev.Zone(name=f'Zone {self.circuit.get_zone_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.AreaDevice:
                self.circuit.add_area(dev.Area(name=f'Area {self.circuit.get_area_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.CountryDevice:
                self.circuit.add_country(dev.Country(name=f'Country {self.circuit.get_country_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.CommunityDevice:
                self.circuit.add_community(dev.Community(
                    name=f'Community {self.circuit.get_communities_number() + 1}')
                )
                self.update_from_to_list_views()

            elif elm_type == DeviceType.RegionDevice:
                self.circuit.add_region(dev.Region(name=f'Region {self.circuit.get_regions_number() + 1}'))
                self.update_from_to_list_views()

            elif elm_type == DeviceType.MunicipalityDevice:
                self.circuit.add_municipality(dev.Municipality(
                    name=f'Municipalities {self.circuit.get_municipalities_number() + 1}')
                )
                self.update_from_to_list_views()

            elif elm_type == DeviceType.BusDevice:
                self.circuit.add_bus(dev.Bus(name=f'Bus {self.circuit.get_bus_number() + 1}'))

            elif elm_type == DeviceType.ContingencyDevice:
                target_devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]] = dict()
                supported_device_types: Tuple[DeviceType, ...] = (
                    DeviceType.DCLineDevice,
                    DeviceType.LineDevice,
                    DeviceType.HVDCLineDevice,
                    DeviceType.Transformer2WDevice,
                    DeviceType.WindingDevice,
                    DeviceType.SeriesReactanceDevice,
                    DeviceType.UpfcDevice,
                    DeviceType.GeneratorDevice,
                    DeviceType.BatteryDevice,
                    DeviceType.StaticGeneratorDevice,
                )
                target_device_count: int = 0

                for target_device_type in supported_device_types:
                    target_devices: List[ALL_DEV_TYPES] = list(
                        self.circuit.get_elements_by_type(device_type=target_device_type)
                    )
                    target_devices_by_type[target_device_type] = target_devices
                    target_device_count = target_device_count + len(target_devices)

                if target_device_count > 0:
                    dlg: DeviceSelectorDialogue = DeviceSelectorDialogue(
                        devices_by_type=target_devices_by_type,
                        allow_none=False,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_device: ALL_DEV_TYPES | None = dlg.get_selected_device()
                        if isinstance(selected_device, EditableDevice):
                            if len(self.circuit.contingency_groups) > 0:
                                contingency_group: dev.ContingencyGroup = self.circuit.contingency_groups[0]
                            else:
                                contingency_group = dev.ContingencyGroup(
                                    name=f"Contingency group {self.circuit.get_contingency_groups_number() + 1}",
                                    category="single",
                                )
                                self.circuit.add_contingency_group(contingency_group)

                            contingency: dev.Contingency = dev.Contingency(
                                device=selected_device,
                                code=selected_device.code,
                                name=f"Contingency {selected_device.name}",
                                value=0,
                                group=contingency_group,
                            )
                            self.circuit.add_contingency(contingency)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no supported devices to target."))

            elif elm_type == DeviceType.ContingencyGroupDevice:
                group = dev.ContingencyGroup(
                    name=f"Contingency group {self.circuit.get_contingency_groups_number() + 1}"
                )
                self.circuit.add_contingency_group(group)

            elif elm_type == DeviceType.RemedialActionGroupDevice:
                group = dev.RemedialActionGroup(
                    name=f"Remedial actions group {self.circuit.get_remedial_action_groups_number() + 1}"
                )
                self.circuit.add_remedial_action_group(group)

            elif elm_type == DeviceType.RemedialActionDevice:
                target_devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]] = dict()
                supported_device_types: Tuple[DeviceType, ...] = (
                    DeviceType.DCLineDevice,
                    DeviceType.LineDevice,
                    DeviceType.HVDCLineDevice,
                    DeviceType.Transformer2WDevice,
                    DeviceType.WindingDevice,
                    DeviceType.SeriesReactanceDevice,
                    DeviceType.UpfcDevice,
                    DeviceType.GeneratorDevice,
                    DeviceType.BatteryDevice,
                    DeviceType.StaticGeneratorDevice,
                )
                target_device_count: int = 0

                for target_device_type in supported_device_types:
                    target_devices: List[ALL_DEV_TYPES] = list(
                        self.circuit.get_elements_by_type(device_type=target_device_type)
                    )
                    target_devices_by_type[target_device_type] = target_devices
                    target_device_count = target_device_count + len(target_devices)

                if target_device_count > 0:
                    dlg: DeviceSelectorDialogue = DeviceSelectorDialogue(
                        devices_by_type=target_devices_by_type,
                        allow_none=False,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_device: ALL_DEV_TYPES | None = dlg.get_selected_device()
                        if isinstance(selected_device, EditableDevice):
                            if len(self.circuit.remedial_action_groups) > 0:
                                remedial_action_group: dev.RemedialActionGroup = self.circuit.remedial_action_groups[0]
                            else:
                                remedial_action_group = dev.RemedialActionGroup(
                                    name=(
                                        f"Remedial actions group "
                                        f"{self.circuit.get_remedial_action_groups_number() + 1}"
                                    ),
                                    category="single",
                                )
                                self.circuit.add_remedial_action_group(remedial_action_group)

                            remedial_action: dev.RemedialAction = dev.RemedialAction(
                                device=selected_device,
                                code=selected_device.code,
                                name=f"RA {selected_device.name}",
                                value=0,
                                group=remedial_action_group,
                            )
                            self.circuit.add_remedial_action(remedial_action)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no supported devices to target."))

            elif elm_type == DeviceType.InvestmentsGroupDevice:
                group = dev.InvestmentsGroup(name=f"Investments group {len(self.circuit.investments_groups) + 1}")
                self.circuit.add_investments_group(group)

            elif elm_type == DeviceType.InvestmentDevice:
                target_devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]] = dict()
                all_devices_by_type: Dict[DeviceType, Dict[str, ALL_DEV_TYPES]] = (
                    self.circuit.get_all_elements_dict_by_type(string_keys=False)
                )
                excluded_device_types: Set[DeviceType] = set((
                    DeviceType.ContingencyDevice,
                    DeviceType.ContingencyGroupDevice,
                    DeviceType.InvestmentDevice,
                    DeviceType.InvestmentsGroupDevice,
                    DeviceType.ShortCircuitEvent,
                    DeviceType.RemedialActionDevice,
                    DeviceType.RemedialActionGroupDevice,
                ))
                target_device_count: int = 0

                for target_device_type, target_devices_dict in all_devices_by_type.items():
                    if target_device_type in excluded_device_types:
                        pass
                    else:
                        target_devices: List[ALL_DEV_TYPES] = list(target_devices_dict.values())
                        target_devices_by_type[target_device_type] = target_devices
                        target_device_count = target_device_count + len(target_devices)

                if target_device_count > 0:
                    dlg: DeviceSelectorDialogue = DeviceSelectorDialogue(
                        devices_by_type=target_devices_by_type,
                        allow_none=False,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_device: ALL_DEV_TYPES | None = dlg.get_selected_device()
                        if isinstance(selected_device, EditableDevice):
                            if len(self.circuit.investments_groups) > 0:
                                investment_group: dev.InvestmentsGroup = self.circuit.investments_groups[0]
                            else:
                                investment_group = dev.InvestmentsGroup(
                                    name=f"Investments group {len(self.circuit.investments_groups) + 1}",
                                    category="single",
                                )
                                self.circuit.add_investments_group(investment_group)

                            investment: dev.Investment = dev.Investment(
                                device=selected_device,
                                code=selected_device.code,
                                name=f"{selected_device.type_name}: {selected_device.name}",
                                CAPEX=0.0,
                                group=investment_group,
                            )
                            self.circuit.add_investment(investment)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no devices to target."))

            elif elm_type == DeviceType.ShortCircuitEvent:
                buses: List[ALL_DEV_TYPES] = self.circuit.get_buses()
                if len(buses) > 0:
                    dlg: DeviceSelectorDialogue = DeviceSelectorDialogue(
                        devices_by_type={DeviceType.BusDevice: buses},
                        allow_none=False,
                        parent=self,
                    )
                    if exec_dialog_safely(dialog=dlg) == QtWidgets.QDialog.DialogCode.Accepted:
                        selected_device: ALL_DEV_TYPES | None = dlg.get_selected_device()
                        if isinstance(selected_device, dev.Bus):
                            short_circuit_event: dev.ShortCircuitEvent = dev.ShortCircuitEvent(
                                name=f"{selected_device.name} fault",
                                device=selected_device,
                            )
                            self.circuit.add_short_circuit_event(short_circuit_event)
                        else:
                            pass
                    else:
                        pass
                else:
                    self.show_warning_toast(self.tr("There are no buses to connect this device."))

            elif elm_type == DeviceType.BranchGroupDevice:
                group = dev.BranchGroup(name=f"Branch group {self.circuit.get_branch_groups_number() + 1}")
                self.circuit.add_branch_group(group)

            elif elm_type == DeviceType.Technology:
                tech = dev.Technology(name=f"Technology {len(self.circuit.technologies) + 1}")
                self.circuit.add_technology(tech)

            elif elm_type == DeviceType.OverheadLineTypeDevice:

                obj = dev.OverheadLineType()
                obj.frequency = self.circuit.fBase
                obj.name = f'Tower {len(self.circuit.overhead_line_types) + 1}'
                self.circuit.add_overhead_line(obj)

            elif elm_type == DeviceType.UnderGroundLineDevice:

                name = f'Cable System {len(self.circuit.underground_cable_types) + 1}'
                obj = dev.UndergroundLineType(name=name)
                self.circuit.add_underground_line(obj)

            elif elm_type == DeviceType.UndergroundCableTypeDevice:

                name = f'Cable {len(self.circuit.underground_cable_constructions) + 1}'
                obj = dev.UndergroundCableType(name=name)
                self.circuit.add_underground_cable(obj)

            elif elm_type == DeviceType.SequenceLineDevice:

                name = f'Sequence line {len(self.circuit.sequence_line_types) + 1}'
                obj = dev.SequenceLineType(name=name)
                self.circuit.add_sequence_line(obj)

            elif elm_type == DeviceType.WireDevice:

                name = f'Wire {len(self.circuit.wire_types) + 1}'
                obj = dev.Wire(name=name)
                self.circuit.add_wire(obj)

            elif elm_type == DeviceType.TransformerTypeDevice:

                name = f'Transformer type {len(self.circuit.transformer_types) + 1}'
                obj = dev.TransformerType(hv_nominal_voltage=10, lv_nominal_voltage=0.4, nominal_power=2,
                                          copper_losses=0.8, iron_losses=0.1, no_load_current=0.1,
                                          short_circuit_voltage=0.1,
                                          gr_hv1=0.5, gx_hv1=0.5, name=name)
                self.circuit.add_transformer_type(obj)

            elif elm_type == DeviceType.FuelDevice:

                name = f'Fuel {len(self.circuit.fuels) + 1}'
                obj = dev.Fuel(name=name)
                self.circuit.add_fuel(obj)

            elif elm_type == DeviceType.EmissionGasDevice:

                name = f'Gas {len(self.circuit.emission_gases) + 1}'
                obj = dev.EmissionGas(name=name)
                self.circuit.add_emission_gas(obj)

            elif elm_type == DeviceType.Owner:

                name = f'Owner {len(self.circuit.owners) + 1}'
                obj = dev.Owner(name=name)
                self.circuit.add_owner(obj)

            elif elm_type == DeviceType.ModellingAuthority:

                name = f'Modelling authority {self.circuit.get_modelling_authorities_number()}'
                obj = dev.ModellingAuthority(name=name)
                self.circuit.add_modelling_authority(obj)

            elif elm_type == DeviceType.FacilityDevice:

                name = f'Facility {self.circuit.get_facility_number()}'
                obj = dev.Facility(name=name)
                self.circuit.add_facility(obj)

            elif elm_type == DeviceType.MarketUnitDevice:

                name = f'Market unit {self.circuit.get_market_unit_number()}'
                obj = dev.MarketUnit(name=name)
                self.circuit.add_market_unit(obj)

            elif elm_type == DeviceType.MarketUnitsGroupDevice:

                name = f'Market unit group{self.circuit.get_market_unit_group_number()}'
                obj = dev.MarketUnitsGroup(name=name)
                self.circuit.add_market_unit_group(obj)

            elif elm_type == DeviceType.ManufacturerNativeModelDevice:

                # A provider is valid only after its binary completed isolated
                # inspection, so this database action never creates an empty row.
                importer_dialog: QtWidgets.QDialog = ManufacturerNativeImporterDialog(
                    assets=self.circuit,
                    parent=self,
                )
                exec_dialog_safely(dialog=importer_dialog)

            elif elm_type == DeviceType.EmtModelTemplateDevice:

                name = f'EMT template {len(self.circuit.emt_models)}'
                obj = dev.EmtModelTemplate(name=name)
                self.circuit.add_emt_model(obj)


            elif elm_type == DeviceType.RmsModelTemplateDevice:

                name = f'RMS event {len(self.circuit.rms_events)}'
                obj = dev.RmsModelTemplate(name=name)
                self.circuit.add_rms_model(obj)

            elif elm_type == DeviceType.FmuTemplateDevice:

                name = f'FMU template {len(self.circuit.fmu_templates) + 1}'
                obj = dev.FmuTemplate(name=name)
                self.circuit.add_fmu_template(obj)


            elif elm_type == DeviceType.RmsEventDevice:

                name = f'RMS event {len(self.circuit.rms_events)}'
                obj = dev.RmsEvent(name=name)
                self.circuit.add_rms_event(obj)

            elif elm_type == DeviceType.RmsEventsGroupDevice:

                name = f'RMS event group {len(self.circuit.rms_events_groups)}'
                obj = dev.RmsEventsGroup(name=name)
                self.circuit.add_rms_events_group(obj)

            elif elm_type == DeviceType.EmtEventDevice:

                name = f'EMT event {len(self.circuit.emt_events)}'
                obj = dev.EmtEvent(name=name)
                self.circuit.add_emt_event(obj)

            elif elm_type == DeviceType.EmtEventsGroupDevice:

                name = f'EMT event group {len(self.circuit.emt_events_groups)}'
                obj = dev.EmtEventsGroup(name=name)
                self.circuit.add_emt_events_group(obj)

            elif elm_type == DeviceType.ControlPc:

                name = f'Control PC {len(self.circuit.control_pcs)}'
                obj = dev.ControlPc(name=name)
                self.circuit.add_control_pc(obj)

            else:
                info_msg(self.tr("This object does not support table-like addition.\nUse the schematic instead."))
                return

            # update the view
            self.view_objects_data()

    def colour_branches_like_group(self):
        """
        Colour the branches like the branch group
        """
        model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()

        if model is not None:

            if len(self.ui.dataStructuresTreeView.selectedIndexes()) > 0:

                rows = np.unique([sel.row() for sel in self.ui.dataStructureTableView.selectedIndexes()])

                for i in rows:

                    elm: ALL_DEV_TYPES | None = model.get_object_at_proxy_row(proxy_row=int(i))

                    if elm is not None and elm.device_type == DeviceType.BranchGroupDevice:

                        for br in self.circuit.get_branches_iter(add_vsc=True,
                                                                 add_hvdc=True,
                                                                 add_switch=True):
                            if br.group == elm:
                                br.color = elm.color

                self.show_info_toast("Done!")
            else:
                self.show_warning_toast("Nothing selected :/")

    def launch_device_editor(self, elm: EditableDevice) -> None:
        """
        Open the best available editor for one editable device.

        :param elm: Device to edit.
        :return: None.
        """
        # Route the device through the same specialized editors used by database-row editing.
        if elm.device_type == DeviceType.OverheadLineTypeDevice:
            tower_builder_window: TowerBuilderGUI = TowerBuilderGUI(
                tower=elm,
                wires_catalogue=self.circuit.wire_types
            )
            tower_builder_window.setModal(True)
            tower_builder_window.resize(int(1.81 * 700.0), 700)
            exec_dialog_safely(dialog=tower_builder_window)

        elif elm.device_type == DeviceType.UnderGroundLineDevice:
            cable_builder_window: UndergroundCableBuilderGUI = UndergroundCableBuilderGUI(
                system=elm,
                cables_catalogue=self.circuit.underground_cable_constructions,
                parent=self,
            )
            cable_builder_window.setModal(True)
            cable_builder_window.resize(int(1.81 * 700.0), 700)
            exec_dialog_safely(dialog=cable_builder_window)

        elif elm.device_type == DeviceType.RmsModelTemplateDevice:
            self.open_dynamic_editor(api_object=elm, circuit=self.circuit,
                                     preferred_mode=DynamicSimulationMode.RMS)

        elif elm.device_type == DeviceType.EmtModelTemplateDevice:
            self.open_dynamic_editor(api_object=elm, circuit=self.circuit,
                                     preferred_mode=DynamicSimulationMode.EMT)

        elif elm.device_type == DeviceType.ManufacturerNativeModelDevice:
            native_dialog: QtWidgets.QDialog = ManufacturerNativeImporterDialog(
                assets=self.circuit,
                provider=elm,
                parent=self,
            )
            if exec_dialog_safely(dialog=native_dialog):
                self.view_objects_data()
            else:
                pass

        elif elm.device_type == DeviceType.FmuTemplateDevice:
            dlg: QtWidgets.QDialog = FmuTemplateEditorDialog(
                circuit=self.circuit,
                template=elm,
                project_directory=self.project_directory,
                parent=self,
            )
            if exec_dialog_safely(dialog=dlg):
                self.view_objects_data()
            else:
                pass

        else:
            dlg: QtWidgets.QDialog = build_device_editor_dialog(api_object=elm, circuit=self.circuit, main_gui=self)
            exec_dialog_safely(dialog=dlg)

    def launch_object_editor(self) -> None:
        """
        Edit catalogue element
        """
        model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()

        if model is not None:

            if len(self.ui.dataStructuresTreeView.selectedIndexes()) > 0:

                elm_type: DeviceType | None = self.get_db_object_selected_type()

                # get the selected index
                idx_proxy: int = self.ui.dataStructureTableView.currentIndex().row()

                if idx_proxy > -1 and elm_type is not None:

                    # get the object from the table itself
                    elm: ALL_DEV_TYPES | None = model.get_object_at_proxy_row(proxy_row=idx_proxy)

                    if elm is None:
                        info_msg(self.tr('Choose an element from the table'))
                    elif isinstance(elm, EditableDevice):
                        self.launch_device_editor(elm=elm)

                    else:

                        warning_msg(self.tr('No editor available.\n'
                                            'The values can be changed from the table or '
                                            'via context menus in the graphical interface.'),
                                    self.tr('Edit'))
                else:
                    info_msg(self.tr('Choose an element from the table'))
            else:
                info_msg(self.tr('Choose an element from the table'))
        else:
            info_msg(self.tr('Select a catalogue element and then a catalogue object'))

    def set_value_to_column(self):
        """
        Set the value to all the column
        :return: Nothing
        """
        idx = self.ui.dataStructureTableView.currentIndex()
        mdl: ObjectModelFilterProxy | None = self.get_current_objects_model_view()
        col = idx.column()
        if mdl is not None:
            if col > -1:
                mdl.copy_to_column(idx)
                # update the view
                self.view_objects_data()
            else:
                info_msg(self.tr('Select some element to serve as source to copy'), self.tr('Set value to column'))
        else:
            pass

    def set_db_table_index_width(self) -> None:
        """
        Set the database object table index column width.

        :return: None.
        """
        vertical_header: QtWidgets.QHeaderView = self.ui.dataStructureTableView.verticalHeader()
        current_width: int = max(vertical_header.width(), 80)
        width: int
        accepted: bool
        width, accepted = QtWidgets.QInputDialog.getInt(
            self,
            self.tr("Index column width"),
            self.tr("Width in pixels"),
            current_width,
            40,
            2000,
            10,
        )

        if accepted:
            if self.db_table_index_resizer is not None:
                self.db_table_index_resizer.set_header_width(width=width)
            else:
                vertical_header.setMinimumWidth(40)
                vertical_header.setMaximumWidth(2000)
                vertical_header.setFixedWidth(width)
                self.ui.dataStructureTableView.updateGeometries()
        else:
            pass

    def show_db_table_index_context_menu(self, pos: QtCore.QPoint) -> None:
        """
        Show the database table index-column context menu.

        :param pos: Relative click position.
        :return: None.
        """
        context_menu: QtWidgets.QMenu = QtWidgets.QMenu(parent=self.ui.dataStructureTableView)

        gf.add_menu_entry(menu=context_menu,
                          text=self.tr("Set index width"),
                          icon_path=":/Icons/icons/grid_icon.png",
                          function_ptr=self.set_db_table_index_width)

        context_menu.exec(self.ui.dataStructureTableView.verticalHeader().mapToGlobal(pos))

    def on_data_structure_table_clicked(self, proxy_index: QtCore.QModelIndex) -> None:
        """
        Handle clicks on the data structure table.
        Open the hosted device editor when the click is accompanied by the Ctrl modifier.

        :param proxy_index: Clicked index in the visible table model.
        :return: None.
        """
        if bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.KeyboardModifier.ControlModifier):
            self.open_hosted_device_editor_at_proxy_index(proxy_index=proxy_index)
        else:
            pass

    def open_hosted_device_editor_at_proxy_index(self, proxy_index: QtCore.QModelIndex) -> bool:
        """
        Open the editor for the device stored in one object-table cell.

        :param proxy_index: Clicked index in the visible table model.
        :return: ``True`` when a hosted device editor was opened.
        """
        if proxy_index.isValid():
            proxy_model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()

            if proxy_model is not None:
                source_model: QtCore.QAbstractItemModel | None = proxy_model.sourceModel()

                if isinstance(source_model, ObjectsModel):
                    # The table can be sorted or filtered, so raw values must be read from the source index.
                    source_index: QtCore.QModelIndex = proxy_model.mapToSource(proxy_index)
                    hosted_device: EditableDevice | None = source_model.get_hosted_device_at_index(index=source_index)

                    if hosted_device is not None:
                        self.launch_device_editor(elm=hosted_device)
                        return True
                    else:
                        return False
                else:
                    return False
            else:
                return False
        else:
            return False

    def highlight_selection_buses(self):
        """
        Highlight and select the buses of the selected objects
        """

        model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()

        if model is not None:

            sel_idx = self.ui.dataStructureTableView.selectedIndexes()
            objects = model.get_objects_in_display_order()

            if len(objects) > 0:

                if len(sel_idx) > 0:

                    unique = set()
                    for idx in sel_idx:
                        unique.add(idx.row())
                    sel_obj = model.get_objects_at_proxy_rows(proxy_rows=sorted(unique))

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
                    info_msg(self.tr('Select some elements to highlight'), self.tr('Highlight'))
            else:
                pass

    def get_objects_time_index(self) -> Union[None, int]:
        """
        Get the time index of the objects slider already
        accounting for the -1 -> None conversion
        :return: None or int
        """
        t_idx = self.ui.db_step_slider.value()
        if t_idx <= -1:
            return None
        else:
            return t_idx

    def highlight_based_on_property(self):
        """
        Highlight and select the buses of the selected objects
        """
        indices = self.ui.dataStructureTableView.selectedIndexes()

        if len(indices):
            model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()

            if model is not None:
                objects: List[ALL_DEV_TYPES] = model.get_objects_in_display_order()
                t_idx = self.get_objects_time_index()

                if model.rowCount() > 0:
                    col_indices = list({index.column() for index in indices})
                    elm = model.get_object_at_proxy_row(proxy_row=0)
                    if elm is None:
                        info_msg(self.tr("No object found :("), self.tr("Highlight based on property"))
                        return
                    else:
                        pass
                    attr = model.attributes[col_indices[0]]
                    gc_prop = elm.registered_properties[attr]
                    if gc_prop is None:
                        info_msg(
                            self.tr("The proprty {property_name} cannot be found :(").format(property_name=attr),
                            self.tr("Highlight based on property"),
                        )
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
                        cmap: NativeColorMap = NativeColorMap(stops=seq)
                        mx = max(values)

                        if mx != 0:

                            colors = np.zeros(len(values), dtype=object)
                            for i, value in enumerate(values):
                                r, g, b, a = cmap(value / mx)
                                colors[i] = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)

                            # color based on the value
                            self.set_big_bus_marker_colours(buses=buses, colors=colors, tool_tips=None)

                        else:
                            info_msg(self.tr('The maximum value is 0, so the coloring cannot be applied'),
                                     self.tr('Highlight based on property'))
                    else:
                        info_msg(self.tr('The selected property must be of a numeric type'),
                                 self.tr('Highlight based on property'))

                else:
                    pass

    def assign_to_profile(self):
        """
        Assign the snapshot values at the object DB to the profiles
        """
        indices = self.ui.dataStructureTableView.selectedIndexes()

        if len(indices):
            model: ObjectModelFilterProxy | None = self.get_current_objects_model_view()

            if model is not None:
                logger = bs.Logger()

                t_idx = self.get_objects_time_index()
                attr_list = list()
                for index in indices:
                    i = index.row()
                    p_idx = index.column()
                    elm = model.get_object_at_proxy_row(proxy_row=i)
                    if elm is not None:
                        attr = model.attributes[p_idx]
                        gc_prop = elm.registered_properties[attr]
                        attr_list.append(attr)
                        if gc_prop.has_profile():
                            val = elm.get_value(prop=gc_prop, t_idx=t_idx)
                            profile = elm.get_profile_by_prop(prop=gc_prop)
                            profile.fill(val)
                        else:
                            logger.add_error("No profile found for " + attr, device=elm.name)
                    else:
                        logger.add_error("No object found for selected row", device=str(i))

                if logger.size():
                    logs_window = LogsDialogue(self.tr("Assign to profile"), logger=logger, parent=self)
                    exec_dialog_safely(dialog=logs_window)
                else:
                    lst = ", ".join(attr_list)
                    self.show_info_toast(f"{lst} assigned to profile")
        else:
            info_msg(self.tr("Select a cell or a column first"), self.tr("Assign to profile"))

    def objects_histogram_analysis_plot(self) -> None:
        """Open native histogram tabs for the selected device properties.

        :return: None.
        """
        elm_type: DeviceType | None = self.get_db_object_selected_type()

        if elm_type is not None:
            if len(self.circuit.get_elements_by_type(device_type=elm_type)):
                histogram_data: tuple[list[str], list[np.ndarray]] | None = object_histogram_analysis(
                    circuit=self.circuit,
                    object_type=elm_type.value,
                    t_idx=self.get_db_slider_index(),
                )
                if histogram_data is not None:
                    property_names: list[str] = histogram_data[0]
                    property_values: list[np.ndarray] = histogram_data[1]
                    dialog_title: str = self.tr("{device_type} distributions").format(device_type=elm_type.value)
                    plot_dialogue: PlotDialogue = PlotDialogue(title=dialog_title, parent=self)
                    has_histogram: bool = False
                    property_index: int
                    for property_index in range(len(property_names)):
                        values: np.ndarray = property_values[property_index]
                        finite_values: np.ndarray = values[np.isfinite(values)]
                        if len(finite_values) > 0:
                            bin_count: int = min(max(int(np.sqrt(len(finite_values))), 4), 32)
                            chart_title: str = self.tr("{device_type} {property_name} distribution").format(
                                device_type=elm_type.value,
                                property_name=property_names[property_index],
                            )
                            accepted: bool
                            if has_histogram:
                                accepted = plot_dialogue.add_histogram_tab(
                                    tab_title=property_names[property_index],
                                    values=finite_values,
                                    bin_count=bin_count,
                                    title=chart_title,
                                    x_axis_title=property_names[property_index],
                                    y_axis_title=self.tr("Count"),
                                )
                            else:
                                accepted = plot_dialogue.set_histogram(
                                    values=finite_values,
                                    bin_count=bin_count,
                                    title=chart_title,
                                    x_axis_title=property_names[property_index],
                                    y_axis_title=self.tr("Count"),
                                )
                                if accepted:
                                    plot_dialogue.set_current_tab_title(property_names[property_index])
                                else:
                                    pass
                            if accepted:
                                has_histogram = True
                            else:
                                pass
                        else:
                            pass
                    if has_histogram:
                        self.register_open_plot_dialog(plot_dialogue)
                        plot_dialogue.show()
                    else:
                        plot_dialogue.reject()
                else:
                    self.show_warning_toast(self.tr("This device type has no numeric histogram data."))
            else:
                pass
        else:
            info_msg(self.tr('Select a data structure'))

    def objects_smart_search(self):
        """
        Objects and time series object-based filtering
        :return:
        """

        # gather the model, which for sure is a ExpressionFilterProxy or None
        proxy_mdl: ObjectModelFilterProxy | None = self.get_current_objects_model_view()

        if proxy_mdl is not None:
            if len(proxy_mdl.get_objects_in_db_order()) > 0:

                has_err, err_txt = proxy_mdl.setExpression(self.ui.smart_search_lineEdit.text())

                # display time series
                self.display_profiles(proxy_mdl=proxy_mdl)

                # display associations
                self.display_associations(proxy_mdl=proxy_mdl)

                if has_err:
                    self.show_error_toast(err_txt)

            else:
                # nothing to search
                self.show_warning_toast("The collection is empty...")

        else:
            self.show_warning_toast("Nothing to search on, select an object...")

        return None

    def delete_inconsistencies(self):
        """
        Call delete_with_dialogue shit
        :return:
        """
        ok = yes_no_question(
            self.tr("This action removes all disconnected devices with no active profile and delete all small islands"),
            self.tr("Delete inconsistencies"))

        if ok:
            logger = self.delete_shit()

            if len(logger) > 0:
                dlg: LogsDialogue = LogsDialogue(self.tr("Delete inconsistencies"), logger, parent=self)
                dlg.setModal(True)
                exec_dialog_safely(dialog=dlg)
            else:
                pass
        else:
            pass

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

        # delete_with_dialogue the grphics from all diagrams
        self.delete_from_all_diagrams(elements=buses_to_delete)

        for elm in buses_to_delete:
            logger.add_info("Deleted " + str(elm.device_type.value), elm.name)

        # search other elements to delete_with_dialogue
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

        ok = yes_no_question(
            self.tr("This action may delete_with_dialogue unused objects and references, \nAre you sure?"),
            title=self.tr("DB clean"))

        if ok:
            logger = self.circuit.clean()

            if len(logger) > 0:
                dlg: LogsDialogue = LogsDialogue(self.tr('DB clean logger'), logger, parent=self)
                exec_dialog_safely(dialog=dlg)
            else:
                pass
        else:
            pass

    def scale(self):
        """
        Show the system scaler window
        The scaler window may modify the circuit
        """
        system_scaler_window: SystemScaler = SystemScaler(grid=self.circuit, parent=self)
        exec_dialog_safely(dialog=system_scaler_window)

    def detect_substations(self):
        """
        Call the detect substations logic
        """

        ok = yes_no_question(self.tr("Do you want to try to detect substations and voltage levels in the grid model?"),
                             self.tr("Detect substations"))

        if ok:
            val = 1.0 / (10.0 ** self.ui.rxThresholdSpinBox.value())
            detect_substations(grid=self.circuit,
                               r_x_threshold=val)

    def detect_facilities(self):
        """
        Call the detect facilities logic
        """
        ok = yes_no_question(self.tr("Do you want to try to detect facilities in the grid model?"),
                             self.tr("Detect facilities"))

        if ok:
            detect_facilities(grid=self.circuit)

    def show_objects_context_menu(self, pos: QtCore.QPoint):
        """
        Show diagrams list view context menu
        :param pos: Relative click position
        """
        if len(self.ui.dataStructuresTreeView.selectedIndexes()) > 0:
            context_index: QtCore.QModelIndex = self.ui.dataStructureTableView.indexAt(pos)
            selected_indexes: List[QtCore.QModelIndex] = self.ui.dataStructureTableView.selectedIndexes()

            if context_index.isValid() and context_index not in selected_indexes:
                self.ui.dataStructureTableView.setCurrentIndex(context_index)
            else:
                pass

            if bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.KeyboardModifier.ControlModifier):
                if self.open_hosted_device_editor_at_proxy_index(proxy_index=context_index):
                    return
                else:
                    pass
            else:
                pass

            elm_type: DeviceType | None = self.get_db_object_selected_type()

            context_menu: QtWidgets.QMenu = QtWidgets.QMenu(parent=self.ui.dataStructureTableView)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Edit"),
                              icon_path=":/Icons/icons/edit.png",
                              function_ptr=self.launch_object_editor)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Add"),
                              icon_path=":/Icons/icons/plus.png",
                              function_ptr=self.add_objects)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Delete"),
                              icon_path=":/Icons/icons/minus.png",
                              function_ptr=self.delete_selected_db_table_objects)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Duplicate object"),
                              icon_path=":/Icons/icons/copy.png",
                              function_ptr=self.duplicate_selected_db_table_objects)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Merge"),
                              icon_path=":/Icons/icons/fusion.png",
                              function_ptr=self.fuse_selected_db_table_objects)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Copy idtag"),
                              icon_path=":/Icons/icons/copy.png",
                              function_ptr=self.copy_selected_idtag)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Crop model to buses selection"),
                              icon_path=":/Icons/icons/schematic.png",
                              function_ptr=self.crop_model_to_buses_selection)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Grid reduction"),
                              icon_path=":/Icons/icons/schematic.png",
                              function_ptr=self.grid_reduction_from_table_selection)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Copy table"),
                              icon_path=":/Icons/icons/copy.png",
                              function_ptr=self.copy_objects_data)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Paste column"),
                              icon_path=":/Icons/icons/paste.png",
                              function_ptr=self.paste_objects_data)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Set value to column"),
                              icon_path=":/Icons/icons/copy2down.png",
                              function_ptr=self.set_value_to_column)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Set index width"),
                              icon_path=":/Icons/icons/grid_icon.png",
                              function_ptr=self.set_db_table_index_width)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Assign to profile"),
                              icon_path=":/Icons/icons/assign_to_profile.png",
                              function_ptr=self.assign_to_profile)

            if elm_type == DeviceType.BranchGroupDevice:
                gf.add_menu_entry(menu=context_menu,
                                  text=self.tr("Colour branches like this"),
                                  icon_path=":/Icons/icons/assign_to_profile.png",
                                  function_ptr=self.colour_branches_like_group)
            else:
                pass

            context_menu.addSeparator()

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("New vicinity diagram"),
                              icon_path=":/Icons/icons/grid_icon.png",
                              function_ptr=self.add_bus_vicinity_diagram_from_model)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("New diagram from selection"),
                              icon_path=":/Icons/icons/schematicadd_to.png",
                              function_ptr=self.add_new_bus_diagram_from_selection)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Add to current diagram"),
                              icon_path=":/Icons/icons/schematicadd_to.png",
                              function_ptr=self.add_objects_to_current_diagram)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Highlight buses selection"),
                              icon_path=":/Icons/icons/highlight.png",
                              function_ptr=self.highlight_selection_buses)

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("Highlight based on property"),
                              icon_path=":/Icons/icons/highlight2.png",
                              function_ptr=self.highlight_based_on_property)

            context_menu.addSeparator()

            gf.add_menu_entry(menu=context_menu,
                              text=self.tr("New map from selection"),
                              icon_path=":/Icons/icons/map.png",
                              function_ptr=self.add_new_map_from_database_selection)

            # Convert global position to local position of the list widget
            mapped_pos = self.ui.dataStructureTableView.viewport().mapToGlobal(pos)
            context_menu.exec(mapped_pos)

        else:
            pass

    def add_substation_with_wizard(self):
        """
        Add substation with all its objects using a wizard
        :return:
        """

        # Get selected buses from the current diagram if any
        selected_buses_tuples = self.get_diagram_selected_buses()
        buses_to_replace = [bus for _, bus, _ in selected_buses_tuples] if selected_buses_tuples else None

        kv = self.get_default_voltage()
        dlg = SubstationDesigner(grid=self.circuit, default_voltage=kv)
        exec_dialog_safely(dialog=dlg)
        if dlg.was_ok():

            se_object, voltage_levels = substation_wizards.create_substation(
                grid=self.circuit,
                se_name=dlg.get_name(),
                se_code=dlg.get_code(),
                lat=dlg.get_latitude(),
                lon=dlg.get_longitude(),
                vl_templates=dlg.get_voltage_levels(),
                buses_to_replace=buses_to_replace
            )

            dlg3 = CustomQuestionDialogue(title=self.tr("New substation"),
                                          question=self.tr("How do you want to represent the merged grid?"),
                                          answer1=self.tr("Create new diagram"),
                                          answer2=self.tr("Add to current diagram"))
            exec_dialog_safely(dialog=dlg3)

            if dlg3.accepted_answer == 1:
                # Create a blank diagram and add to it
                self.new_bus_branch_diagram_from_substation(substations=[se_object])

            elif dlg3.accepted_answer == 2:
                self.add_substation_to_current_diagram(substations=[se_object])

            else:
                # not imported
                return

    def search_ts_point(self):
        """
        Search time step point
        """

        mode: TimeSeriesSearchPoint = self.ui.goToTsPointComboBox.currentData()

        if mode == TimeSeriesSearchPoint.LowestLoad:

            total = np.zeros(self.circuit.get_time_number())
            for elm in self.circuit.loads:
                total += elm.P_prof.toarray()

            if len(total) > 0:
                try:
                    idx = np.argmin(total)
                except ValueError:
                    self.show_error_toast(f"{mode.value} could not be found")
                    return

                self.ui.db_step_slider.setValue(idx)
            else:
                self.show_warning_toast("No time steps to navigate to")

        elif mode == TimeSeriesSearchPoint.HighestLoad:

            total = np.zeros(self.circuit.get_time_number())
            for elm in self.circuit.loads:
                total += elm.P_prof.toarray()

            if len(total) > 0:
                try:
                    idx = np.argmax(total)
                except ValueError:
                    self.show_error_toast(f"{mode.value} could not be found")
                    return

                self.ui.db_step_slider.setValue(idx)
            else:
                self.show_warning_toast("No time steps to navigate to")

        else:
            return

    def set_model_x_y_based_on_lat_lon(self):
        """
        Change values of x,y in the database using the latitude and longitude of the buses
        :return:
        """
        ok = yes_no_question(text=self.tr("Setting the database buses x,y position from their latitude and longitude "
                                          "values will change the buses values but not the current diagrams. "
                                          "New diagrams will use the new values"),
                             title="")

        if ok:
            logger = self.circuit.fill_xy_from_lat_lon()

            if logger.has_logs():
                self.show_logs(logger=logger, name="set (x,y) from (lat, lon)")
            else:
                self.show_info_toast("x, y changed!")

    def restore_investments(self):
        """
        Restore investments to the circuit
        :return:
        """
        ok = yes_no_question(
            text=self.tr("This action will restore the circuit to the state before the last investment "
                         "modification. Do you want to proceed?"),
            title=self.tr("Restore investments"))

        if ok:
            self.circuit.restore_investments()
            for diagram_widget in self.diagram_widgets_list:
                if isinstance(diagram_widget, SchematicWidget):
                    diagram_widget.recolour_mode()
                else:
                    # map widgets and other diagram types do not encode active state
                    # via dashed/solid pen styling, so they have nothing to refresh
                    pass

            # re-apply result-based colouring on top of the active-state styling
            self.colour_diagrams()
            self.show_info_toast("Investments restored!")

        return None
