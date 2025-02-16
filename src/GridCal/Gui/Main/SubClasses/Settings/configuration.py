# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import json
import os
from typing import Dict, Union, Any
from PySide6 import QtWidgets

import GridCal.ThirdParty.qdarktheme as qdarktheme
from GridCalEngine.IO.file_system import get_create_gridcal_folder
from GridCal.Gui.Main.SubClasses.Results.results import ResultsMain
from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from GridCal.Gui.Diagrams.generic_graphics import set_dark_mode, set_light_mode
from GridCal.plugins import PluginsInfo, PluginFunction
import GridCal.Gui.gui_functions as gf
from GridCal.Gui.gui_functions import add_menu_entry


def config_data_to_struct(data_: Dict[str, Union[Dict[str, Any], str, Any]],
                          struct_: Dict[str, Dict[str, Any]]) -> None:
    """
    Recursive function to set the GUI objects' values from the config dictionary
    :param data_: config dictionary with values from the file
    :param struct_: result of self.get_config_structure()
    """
    for key, object_to_set in struct_.items():

        # get the value in data_ that corresponds to the object to be set
        corresponding_data = data_.get(key, None)

        if corresponding_data is not None:

            # print("config debug:", key, corresponding_data)

            if isinstance(object_to_set, dict):
                config_data_to_struct(corresponding_data, object_to_set)

            elif isinstance(object_to_set, QtWidgets.QComboBox):
                index = object_to_set.findText(str(corresponding_data))
                if -1 < index < object_to_set.count():
                    object_to_set.setCurrentIndex(index)

            elif isinstance(object_to_set, QtWidgets.QDoubleSpinBox):
                object_to_set.setValue(float(corresponding_data))

            elif isinstance(object_to_set, QtWidgets.QSpinBox):
                object_to_set.setValue(int(corresponding_data))

            elif isinstance(object_to_set, QtWidgets.QCheckBox):
                object_to_set.setChecked(bool(corresponding_data))

            elif isinstance(object_to_set, QtWidgets.QRadioButton):
                object_to_set.setChecked(bool(corresponding_data))

            elif isinstance(object_to_set, str):
                pass
            elif isinstance(object_to_set, float):
                pass
            elif isinstance(object_to_set, int):
                pass
            elif isinstance(object_to_set, bool):
                pass
            else:
                raise Exception('unknown structure')
        else:
            print(f"{key} has no entry in config")


class ConfigurationMain(ResultsMain):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        ResultsMain.__init__(self, parent)

        # plugins
        self.plugins_info = PluginsInfo()

        # check boxes
        self.ui.dark_mode_checkBox.clicked.connect(self.change_theme_mode)

        # buttons
        self.ui.selectCGMESBoundarySetButton.clicked.connect(self.select_cgmes_boundary_set)

        # DateTime change
        self.ui.snapshot_dateTimeEdit.dateTimeChanged.connect(self.snapshot_datetime_changed)

        self.plugin_windows_list = list()

    def change_theme_mode(self) -> None:
        """
        Change the GUI theme
        """
        custom_colors = {"primary": "#00aa88ff",
                         "primary>list.selectionBackground": "#00aa88be"}

        if self.ui.dark_mode_checkBox.isChecked():
            set_dark_mode()

            qdarktheme.setup_theme(theme='dark',
                                   custom_colors=custom_colors,
                                   additional_qss="QToolTip {color: white; background-color: black; border: 0px; }")

            # note: The 0px border on the tooltips allow it to render properly
            for diagram in self.diagram_widgets_list:
                if isinstance(diagram, SchematicWidget):
                    diagram.set_dark_mode()

            self.colour_diagrams()

        else:
            set_light_mode()
            qdarktheme.setup_theme(theme='light',
                                   custom_colors=custom_colors,
                                   additional_qss="QToolTip {color: black; background-color: white; border: 0px;}")

            # note: The 0px border on the tooltips allow it to render properly
            for diagram in self.diagram_widgets_list:
                if isinstance(diagram, SchematicWidget):
                    diagram.set_light_mode()

            self.colour_diagrams()

    @staticmethod
    def config_file_path() -> str:
        """
        get the config file path
        :return: config file path
        """
        return os.path.join(get_create_gridcal_folder(), 'gui_config.json')

    def config_file_exists(self) -> bool:
        """
        Check if the config file exists
        :return: True / False
        """
        return os.path.exists(self.config_file_path())

    def get_config_structure(self) -> Dict[str, Dict[str, any]]:
        """
        Get the settings configuration dictionary
        This serves to collect automatically the settings
        and apply the incomming setting automatically as well
        :return: Dict[name, Dict[name, QtWidget]
        """
        return {
            "graphics": {
                "dark_mode": self.ui.dark_mode_checkBox,
                "palette": self.ui.palette_comboBox,
                # "min_node_size": self.ui.min_node_size_spinBox,
                # "max_node_size": self.ui.max_node_size_spinBox,
                # "min_branch_size": self.ui.min_branch_size_spinBox,
                # "max_branch_size": self.ui.max_branch_size_spinBox,
                # "width_based_flow": self.ui.branch_width_based_on_flow_checkBox,
                "map_tile_provider": self.ui.tile_provider_comboBox,
                "plotting_style": self.ui.plt_style_comboBox,
                "video_fps": self.ui.fps_spinBox
            },
            "machine_learning": {
                "clustering": {
                    "cluster_number": self.ui.cluster_number_spinBox,
                },
                "node_grouping": {
                    "sigma": self.ui.node_distances_sigma_doubleSpinBox,
                    "n_elements": self.ui.node_distances_elements_spinBox,
                },
                "investments_evaluation": {
                    "investment_evaluation_method": self.ui.investment_evaluation_method_ComboBox,
                    "max_investments_evluation_number": self.ui.max_investments_evluation_number_spinBox,
                    "investment_evaluation_obj_func": self.ui.investment_evaluation_objfunc_ComboBox,
                }
            },
            "linear": {

                "ptdf_threshold": self.ui.ptdf_threshold_doubleSpinBox,
                "lodf_threshold": self.ui.lodf_threshold_doubleSpinBox
            },
            "stochastic": {
                "method": self.ui.stochastic_pf_method_comboBox,
                "voltage_variance": self.ui.tolerance_stochastic_spinBox,
                "number_of_samples": self.ui.max_iterations_stochastic_spinBox
            },
            "cascading": {
                "additional_islands": self.ui.cascading_islands_spinBox
            },
            "power_flow": {
                "solver": self.ui.solver_comboBox,
                "retry": self.ui.helm_retry_checkBox,
                "distributed_slack": self.ui.distributed_slack_checkBox,
                "ignore_single_node_islands": self.ui.ignore_single_node_islands_checkBox,
                "use_voltage_guess": self.ui.use_voltage_guess_checkBox,
                "precision": self.ui.tolerance_spinBox,
                "acceleration": self.ui.muSpinBox,
                "max_iterations": self.ui.max_iterations_spinBox,
                "verbosity": self.ui.verbositySpinBox,

                "reactive_power_control_mode": self.ui.control_q_checkBox,
                "transformer_taps_module_control": self.ui.control_tap_modules_checkBox,
                "transformer_taps_phase_control": self.ui.control_tap_phase_checkBox,
                "remote_voltage_controls_switch": self.ui.control_remote_voltage_checkBox,
                "orthogonalize_controls": self.ui.orthogonalize_pf_controls_checkBox,

                "apply_temperature_correction": self.ui.temperature_correction_checkBox,
                "apply_impedance_tolerances": self.ui.apply_impedance_tolerances_checkBox,
                "add_pf_report": self.ui.addPowerFlowReportCheckBox,
            },
            "optimal_power_flow": {
                "method": self.ui.lpf_solver_comboBox,
                "time_grouping": self.ui.opf_time_grouping_comboBox,
                "zone_grouping": self.ui.opfZonalGroupByComboBox,
                "mip_solver": self.ui.mip_solver_comboBox,
                "contingency_tolerance": self.ui.opfContingencyToleranceSpinBox,
                "skip_generation_limits": self.ui.skipOpfGenerationLimitsCheckBox,
                "consider_contingencies": self.ui.considerContingenciesOpfCheckBox,
                "maximize_area_exchange": self.ui.opfMaximizeExcahngeCheckBox,
                "unit_commitment": self.ui.opfUnitCommitmentCheckBox,
                "add_opf_report": self.ui.addOptimalPowerFlowReportCheckBox,
                "robust_mip": self.ui.fixOpfCheckBox,
                "save_mip": self.ui.save_mip_checkBox,
                "ips_method": self.ui.ips_method_comboBox,
                "ips_tolerance": self.ui.ips_tolerance_spinBox,
                "ips_iterations": self.ui.ips_iterations_spinBox,
                "ips_trust_radius": self.ui.ips_trust_radius_doubleSpinBox,
                "ips_init_with_pf": self.ui.ips_initialize_with_pf_checkBox,
                "ips_control_Qlimits": self.ui.ips_control_Qlimits_checkBox,
            },
            "continuation_power_flow": {
                "max_iterations": self.ui.vs_max_iterations_spinBox,
                "stop_at": self.ui.vc_stop_at_comboBox,
                "increase_system_loading": self.ui.start_vs_from_default_radioButton,
                "lambda_factor": self.ui.alpha_doubleSpinBox,
                "points_from_time_series": self.ui.start_vs_from_selected_radioButton,
                "now": self.ui.vs_departure_comboBox,
                "target": self.ui.vs_target_comboBox,
                "available_transfer_capacity": self.ui.atcRadioButton,
            },
            "net_transfer_capacity": {
                "transfer_sensitivity_threshold": self.ui.atcThresholdSpinBox,
                "transfer_method": self.ui.transferMethodComboBox,
                "Loading_threshold_to_report": self.ui.ntcReportLoadingThresholdSpinBox,
                "ntc_linear_consider_contingencies": self.ui.n1ConsiderationCheckBox,

                "skip_generation_limits": self.ui.skipNtcGenerationLimitsCheckBox,
                "transmission_reliability_margin": self.ui.trmSpinBox,

                "use_branch_exchange_sensitivity": self.ui.ntcSelectBasedOnExchangeSensitivityCheckBox,
                "branch_exchange_sensitivity": self.ui.ntcAlphaSpinBox,

                "use_branch_rating_contribution": self.ui.ntcSelectBasedOnAcerCriteriaCheckBox,
                "branch_rating_contribution": self.ui.ntcLoadRuleSpinBox,

                "ntc_opt_consider_contingencies": self.ui.consider_ntc_contingencies_checkBox,
            },
            "nodal_hosting_capacity": {
                "method": self.ui.nodal_capacity_method_comboBox,
                "sense": self.ui.nodal_capacity_sense_SpinBox
            },
            "general": {
                "base_power": self.ui.sbase_doubleSpinBox,
                "frequency": self.ui.fbase_doubleSpinBox,
                "default_bus_voltage": self.ui.defaultBusVoltageSpinBox,
                "engine": self.ui.engineComboBox
            },
            "contingencies": {
                "contingencies_engine": self.ui.contingencyEngineComboBox,
                "use_srap": self.ui.use_srap_checkBox,
                "srap_max_power": self.ui.srap_limit_doubleSpinBox,
                "srap_top_n": self.ui.srap_top_n_SpinBox,
                "srap_deadband": self.ui.srap_deadband_doubleSpinBox,
                "contingency_deadband": self.ui.contingency_deadband_SpinBox,
                "srap_revert_to_nominal_rating": self.ui.srap_revert_to_nominal_rating_checkBox,
                "contingency_massive_report": self.ui.contingency_detailed_massive_report_checkBox
            },
            "file": {
                "store_results_in_file": self.ui.saveResultsCheckBox,
                "current_boundary_set": self.current_boundary_set,
                "cgmes_selected_version": self.ui.cgmes_version_comboBox,
                "cgmes_single_profile_per_file": self.ui.cgmes_single_profile_per_file_checkBox,
                "map_regions_like_raw": self.ui.cgmes_map_regions_like_raw_checkBox,
                "raw_selected_version": self.ui.raw_export_version_comboBox,
                "cgmes_dc_as_hvdclines": self.ui.cgmes_dc_as_hvdclines_checkBox,
            }
        }

    def get_gui_config_data(self) -> Dict[str, Dict[str, Union[float, int, str, bool]]]:
        """
        Get a dictionary with the GUI configuration data
        :return:
        """

        def struct_to_data(
                data_: Dict[str, Union[float, int, str, bool, Dict[str, Union[float, int, str, bool, Dict]]]],
                struct_: Dict[str, Dict[str, any]]):
            """
            Recursive function to get the config dictionary from the GUI values
            :param data_: Dictionary to fill
            :param struct_: result of self.get_config_structure()
            """
            for key, value in struct_.items():
                if isinstance(value, dict):
                    data_[key] = dict()
                    struct_to_data(data_[key], value)
                elif isinstance(value, QtWidgets.QComboBox):
                    data_[key] = value.currentText()
                elif isinstance(value, QtWidgets.QDoubleSpinBox):
                    data_[key] = value.value()
                elif isinstance(value, QtWidgets.QSpinBox):
                    data_[key] = value.value()
                elif isinstance(value, QtWidgets.QCheckBox):
                    data_[key] = value.isChecked()
                elif isinstance(value, QtWidgets.QRadioButton):
                    data_[key] = value.isChecked()
                elif isinstance(value, str):
                    data_[key] = value
                elif isinstance(value, int):
                    data_[key] = value
                elif isinstance(value, float):
                    data_[key] = value
                elif isinstance(value, bool):
                    data_[key] = value
                else:
                    raise Exception(f'unknown structure {value}')

        struct = self.get_config_structure()
        data = dict()
        struct_to_data(data, struct)

        return data

    def save_gui_config(self):
        """
        Save the GUI configuration
        :return:
        """
        data = self.get_gui_config_data()
        with open(self.config_file_path(), "w") as f:
            f.write(json.dumps(data, indent=4))

    def apply_gui_config(self, data: Dict[str, Dict[str, Any]]):
        """
        Apply GUI configuration dictionary
        :param data: GUI configuration dictionary
        """

        struct = self.get_config_structure()
        config_data_to_struct(data_=data, struct_=struct)

        # CGMES boundary set

        """
        "file": {
                "store_results_in_file": self.ui.saveResultsCheckBox,
                "current_boundary_set": self.current_boundary_set 
            }
        """

        file_data: Dict[str, Any] = data.get("file", None)
        if file_data is not None:
            bd_path = file_data.get("current_boundary_set", "")
            self.current_boundary_set = bd_path if os.path.exists(bd_path) else ""
            self.ui.cgmes_boundary_set_label.setText(self.current_boundary_set)

        # light / dark mode
        if self.ui.dark_mode_checkBox.isChecked():
            set_dark_mode()
        else:
            set_light_mode()

    def load_gui_config(self) -> None:
        """
        Load GUI configuration from the local user folder
        """
        if self.config_file_exists():
            with open(self.config_file_path(), "r") as f:
                try:
                    data = json.load(f)
                    self.apply_gui_config(data=data)
                    self.change_theme_mode()
                except json.decoder.JSONDecodeError as e:
                    print(e)
                    self.save_gui_config()
                    print("GUI config file was erroneous, wrote a new one")

    def select_cgmes_boundary_set(self):
        """
        Select the current boundary set
        """
        files_types = "Boundary set (*.zip)"

        dialogue = QtWidgets.QFileDialog(None,
                                         caption='Select Boundary set file',
                                         directory=self.project_directory,
                                         filter=files_types)
        if dialogue.exec():
            filenames = dialogue.selectedFiles()
            if len(filenames) > 0:
                self.current_boundary_set = filenames[0]
                self.ui.cgmes_boundary_set_label.setText(self.current_boundary_set)

    def snapshot_datetime_changed(self):
        """
        Upon change of the snapshot datetime, change the circuit snapshot datetime
        """
        date_time_value = self.ui.snapshot_dateTimeEdit.dateTime().toPython()

        self.circuit.snapshot_time = date_time_value

    def add_plugins(self):
        """
        Add the plugins information and create the menu entries
        """
        self.ui.menuplugins.clear()

        add_menu_entry(menu=self.ui.menuplugins,
                       text="Reload",
                       icon_path=":/Icons/icons/undo.svg",
                       function_ptr=self.add_plugins)

        self.plugins_info.read()  # force refresh

        self.plugins_investment_evaluation_method_dict = dict()

        # for every plugin...
        for key, plugin_info in self.plugins_info.plugins.items():

            # maybe add the main function
            if plugin_info.main_fcn.function_ptr is not None:
                """
                Really hard core magic to avoid lambdas shadow each other due to late binding
                
                lambda e, func=func: func(self)
                
                explanation:
                - e is a bool parameter that the QAction sends when triggered
                - func=func is there for the lambda to force the usage of the value of func 
                  during the iteration and not after the loop
                - func(self) is then what I wanted to lambda in the first place                
                """
                add_menu_entry(
                    menu=self.ui.menuplugins,
                    text=plugin_info.name,
                    icon_path=":/Icons/icons/plugin.svg",
                    icon_pixmap=plugin_info.icon,
                    function_ptr=lambda: self.launch_plugin(plugin_info.main_fcn)
                )

            # maybe add the investments function
            if plugin_info.investments_fcn.function_ptr is not None:
                self.plugins_investment_evaluation_method_dict[
                    plugin_info.investments_fcn.alias
                ] = plugin_info.investments_fcn.function_ptr

        # create combobox model for the plugin investments
        lst = list(self.plugins_investment_evaluation_method_dict.keys())
        self.ui.plugins_investment_evaluation_method_ComboBox.setModel(gf.get_list_model(lst))

    def launch_plugin(self, fcn: PluginFunction):
        """
        Action wrapper to launch the plugin
        :param fcn: some PluginFunction
        """

        # call the main fuinction of the plugin
        ret = fcn.get_pointer_lambda(gui_instance=self)()

        if fcn.call_gui and ret is not None:
            if hasattr(ret, "show"):
                self.plugin_windows_list.append(ret)  # This avoids the window to be garbage collected and be displayed
                ret.show()

