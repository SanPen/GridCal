# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import json
import os
from enum import Enum
from typing import Dict, Union, Any
from PySide6 import QtCore, QtGui, QtWidgets

import VeraGrid.ThirdParty.qdarktheme as qdarktheme
from VeraGridEngine.IO.file_system import get_create_veragrid_folder
from VeraGrid.Gui.Main.SubClasses.Results.results import ResultsMain
from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from VeraGrid.Gui.Diagrams.generic_graphics import set_dark_mode, set_light_mode
from VeraGrid.Gui.i18n import (
    ApplicationLanguage,
    ApplicationTranslator,
    get_language_display_text,
    get_language_flag_icon_path,
    language_from_name,
)
from VeraGrid.plugins import PluginsInfo, PluginFunction
from VeraGrid.Gui.gui_functions import ComboModel, ComboStableKey, add_menu_entry


def get_combo_box_config_value(combo_box: QtWidgets.QComboBox) -> Any:
    """
    Return a stable value for combo-box settings when item data is available.

    :param combo_box: Combo box to serialize.
    :return: Serializable combo value.
    """
    stable_key: ComboStableKey = combo_box.currentData(ComboModel.StableKeyRole)
    if stable_key is None:
        runtime_data: Any = combo_box.currentData()
        if isinstance(runtime_data, Enum):
            return str(runtime_data.value)
        elif isinstance(runtime_data, (str, int, float, bool)):
            return runtime_data
        else:
            return combo_box.currentText()
    else:
        return stable_key


def set_combo_box_config_value(combo_box: QtWidgets.QComboBox, value: Any) -> None:
    """
    Restore a combo-box setting using item data first, then legacy text.

    :param combo_box: Combo box to restore.
    :param value: Stored setting value.
    :return: Nothing.
    """
    index: int = combo_box.findData(value, role=ComboModel.StableKeyRole)
    if index < 0:
        index = combo_box.findData(str(value), role=ComboModel.StableKeyRole)
    else:
        pass

    if index < 0:
        index = combo_box.findData(value)
    else:
        pass

    if index < 0:
        index = combo_box.findData(str(value))
    else:
        pass

    if index < 0:
        for i in range(combo_box.count()):
            runtime_data: Any = combo_box.itemData(i)
            if isinstance(runtime_data, Enum):
                if str(runtime_data.value) == str(value):
                    index = i
                    break
                else:
                    pass
            else:
                pass
    else:
        pass

    if index < 0:
        for i in range(combo_box.count()):
            item_data: ComboStableKey = combo_box.itemData(i, ComboModel.StableKeyRole)
            if str(item_data) == str(value):
                index = i
                break
            else:
                pass

    if index < 0:
        index = combo_box.findText(str(value))
    else:
        pass

    if -1 < index < combo_box.count():
        combo_box.setCurrentIndex(index)
    else:
        pass


def gui_struct_to_data(data_: Dict[str, Union[float, int, str, bool, Dict[str, Union[float, int, str, bool, Dict]]]],
                       struct_: Dict[str, Dict[str, Any]]):
    """
    Recursive function to get the config dictionary from the GUI values
    :param data_: Dictionary to fill
    :param struct_: the result with self.get_config_structure()
    """
    for key, value in struct_.items():
        if isinstance(value, dict):
            data_[key] = dict()
            gui_struct_to_data(data_[key], value)
        elif isinstance(value, QtWidgets.QComboBox):
            data_[key] = get_combo_box_config_value(value)
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
                set_combo_box_config_value(combo_box=object_to_set, value=corresponding_data)

            elif isinstance(object_to_set, QtWidgets.QDoubleSpinBox):
                if isinstance(corresponding_data, (int, float)):
                    object_to_set.setValue(float(corresponding_data))
                else:
                    pass

            elif isinstance(object_to_set, QtWidgets.QSpinBox):
                if isinstance(corresponding_data, (int, float)):
                    object_to_set.setValue(int(corresponding_data))
                else:
                    pass

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

        # The language widgets are declared in MainWindow.ui and only need
        # runtime population and signal wiring here.
        self.language_label: QtWidgets.QLabel = self.ui.language_label
        self.language_combo_box: QtWidgets.QComboBox = self.ui.language_combo_box
        self.create_language_controls()

        # check boxes
        # Use the checkbox state-change signal so the theme refresh path runs for both
        # user clicks and programmatic setChecked() calls during configuration loading.
        self.ui.dark_mode_checkBox.toggled.connect(self.on_dark_mode_checkBox_toggled)

        self.plugins_investment_evaluation_method_dict = dict()

        # DateTime change
        self.ui.snapshot_dateTimeEdit.dateTimeChanged.connect(self.snapshot_datetime_changed)

        self.plugin_windows_list = list()
        self.translation_controller: ApplicationTranslator | None = None

    def create_language_controls(self) -> None:
        """
        Initialize the language selector embedded in the main settings grid.

        :returns: None.
        """
        # Keep the flag icons legible in the selector regardless of the platform style.
        self.language_combo_box.setIconSize(QtCore.QSize(18, 18))
        self.refresh_language_combo_box_texts()
        self.language_combo_box.currentIndexChanged.connect(self.language_selection_changed)

    def refresh_language_combo_box_texts(self) -> None:
        """
        Rebuild the language selector labels in the currently active language.

        The combo stores enum values as item data and only the visible text is
        rewritten, which keeps persistence stable across translations.

        :returns: None.
        """
        current_language: ApplicationLanguage = self.get_selected_language()
        available_languages: list[ApplicationLanguage] = list(
            [
                ApplicationLanguage.SYSTEM,
                ApplicationLanguage.ENGLISH,
                ApplicationLanguage.SPANISH,
                ApplicationLanguage.CATALAN,
                ApplicationLanguage.BASQUE,
                ApplicationLanguage.GALICIAN,
                ApplicationLanguage.ITALIAN,
                ApplicationLanguage.PORTUGUESE,
                ApplicationLanguage.FRENCH,
                ApplicationLanguage.GERMAN,
                ApplicationLanguage.DUTCH,
                ApplicationLanguage.GREEK,
                ApplicationLanguage.CHINESE,
                ApplicationLanguage.CANTONESE,
                ApplicationLanguage.JAPANESE,
                ApplicationLanguage.KOREAN,
                ApplicationLanguage.HINDI,
                ApplicationLanguage.POLISH,
                ApplicationLanguage.ARABIC,
                ApplicationLanguage.TURKISH,
            ]
        )

        self.language_label.setText(self.tr("Language"))
        self.language_combo_box.blockSignals(True)
        self.language_combo_box.clear()

        language: ApplicationLanguage

        for language in available_languages:
            display_text: str = get_language_display_text(language, self.tr)

            # The selector stores the stable enum in item data and only decorates the row with a flag icon.
            self.language_combo_box.addItem(
                QtGui.QIcon(get_language_flag_icon_path(language)),
                display_text,
                language,
            )

        selected_index: int = self.language_combo_box.findData(current_language)
        if selected_index >= 0:
            self.language_combo_box.setCurrentIndex(selected_index)
        else:
            self.language_combo_box.setCurrentIndex(0)

        self.language_combo_box.blockSignals(False)

    def set_translation_controller(self, translation_controller: ApplicationTranslator) -> None:
        """
        Attach the application translation controller to this settings controller.

        :param translation_controller: Shared application translation controller.
        :returns: None.
        """
        self.translation_controller = translation_controller
        self.refresh_language_combo_box_texts()

        current_language: ApplicationLanguage = translation_controller.get_current_language()
        selected_index: int = self.language_combo_box.findData(current_language)

        self.language_combo_box.blockSignals(True)
        if selected_index >= 0:
            self.language_combo_box.setCurrentIndex(selected_index)
        else:
            self.language_combo_box.setCurrentIndex(0)
        self.language_combo_box.blockSignals(False)

    def get_selected_language(self) -> ApplicationLanguage:
        """
        Return the language currently selected in the GUI.

        :returns: Selected application language.
        """
        combo_data: ApplicationLanguage | None = self.language_combo_box.currentData()

        if isinstance(combo_data, ApplicationLanguage):
            return combo_data
        else:
            return ApplicationLanguage.SYSTEM

    def set_selected_language(self, language: ApplicationLanguage) -> None:
        """
        Select one language option in the GUI without triggering signal loops.

        :param language: Language to select.
        :returns: None.
        """
        selected_index: int = self.language_combo_box.findData(language)

        self.language_combo_box.blockSignals(True)
        if selected_index >= 0:
            self.language_combo_box.setCurrentIndex(selected_index)
        else:
            self.language_combo_box.setCurrentIndex(0)
        self.language_combo_box.blockSignals(False)

    def language_selection_changed(self, _index: int) -> None:
        """
        Apply the newly selected language to the running application.

        :param _index: Qt combo-box index.
        :returns: None.
        """
        if self.translation_controller is not None:
            selected_language: ApplicationLanguage = self.get_selected_language()
            self.translation_controller.set_language(selected_language)
            self.save_gui_config()
        else:
            pass

    def refresh_runtime_translations(self) -> None:
        """
        Refresh runtime-owned main-window strings after a language change.

        :returns: None.
        """
        super().refresh_runtime_translations()
        self.refresh_language_combo_box_texts()

    @QtCore.Slot(bool)
    def on_dark_mode_checkBox_toggled(self, checked: bool) -> None:
        """
        Apply the GUI theme after the Main dark-mode checkbox changes.

        :param checked: Current checkbox state.
        :return: None.
        """
        self.recolour_script_editors(dark_theme=checked)
        diagram_widgets_list: object = self.__dict__.get("diagram_widgets_list", None)
        if isinstance(diagram_widgets_list, list):
            self.change_theme_mode(checked)
        else:
            pass

    def change_theme_mode(self, _checked: bool | None = None) -> None:
        """
        Change the GUI theme.

        :param _checked: Checkbox state provided by the Qt signal when available.
        :return: None.
        """
        custom_colors = {"primary": "#00aa88ff",
                         "primary>list.selectionBackground": "#00aa88be"}

        if _checked is None:
            dark_theme: bool = self.ui.dark_mode_checkBox.isChecked()
        else:
            dark_theme = _checked

        if dark_theme:
            qdarktheme.setup_theme(theme='dark',
                                   custom_colors=custom_colors,
                                   additional_qss="QToolTip {color: white; background-color: black; border: 0px; }")
            set_dark_mode()

            # note: The 0px border on the tooltips allow it to render properly
            for diagram in self.diagram_widgets_list:
                if isinstance(diagram, SchematicWidget):
                    diagram.set_dark_mode()

            self.recolour_script_editors(dark_theme=True)
            self.dynamic_editor_workspace_session.set_dark_mode()

            self.colour_diagrams()

        else:
            qdarktheme.setup_theme(theme='light',
                                   custom_colors=custom_colors,
                                   additional_qss="QToolTip {color: black; background-color: white; border: 0px;}")
            set_light_mode()

            # note: The 0px border on the tooltips allow it to render properly
            for diagram in self.diagram_widgets_list:
                if isinstance(diagram, SchematicWidget):
                    diagram.set_light_mode()

            self.recolour_script_editors(dark_theme=False)
            self.dynamic_editor_workspace_session.set_light_mode()

            self.colour_diagrams()

    def recolour_script_editors(self, dark_theme: bool) -> None:
        """
        Recolor the Main GUI scripting widgets from the Main theme event.

        :param dark_theme: Whether the Main dark-mode checkbox is checked.
        :return: None.
        """
        if dark_theme:
            self.console.set_dark_mode()
            self.code_editor.set_dark_mode()
        else:
            self.console.set_light_mode()
            self.code_editor.set_light_mode()

    @staticmethod
    def config_file_path() -> str:
        """
        get the config file path
        :return: config file path
        """
        return os.path.join(get_create_veragrid_folder(), 'gui_config.json')

    def config_file_exists(self) -> bool:
        """
        Check if the config file exists
        :return: True / False
        """
        return os.path.exists(self.config_file_path())

    def get_config_structure(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the persistent GUI preferences used by both save and restore.

        Language is handled by get_gui_config_data/apply_gui_config and server
        settings by ServerMain. Circuit data, searches, and model-dependent
        selections are not global preferences.

        :return: Settings sections mapped to their GUI controls.
        """
        return {
            "graphics": {
                "dark_mode": self.ui.dark_mode_checkBox,
                "palette": self.ui.palette_comboBox,
                "min_node_size": self.ui.min_node_size_spinBox,
                "max_node_size": self.ui.max_node_size_spinBox,
                "min_branch_size": self.ui.min_branch_size_spinBox,
                "max_branch_size": self.ui.max_branch_size_spinBox,
                "width_based_flow": self.ui.branch_width_based_on_flow_checkBox,
                "arrow_size": self.ui.arrow_size_size_spinBox,
                "explosion_factor": self.ui.explosion_factor_doubleSpinBox,
                "ask_before_applying_layout": self.ui.ask_before_appliying_layout_checkBox,
                "automatic_layout": self.ui.automatic_layout_comboBox,
                "use_schematic_objects_color": self.ui.use_schematic_objects_color_checkBox,
                "resolution_factor": self.ui.resolution_factor_spinBox,
                "map_tile_provider": self.ui.tile_provider_comboBox,
                "video_fps": self.ui.fps_spinBox
            },
            "general": {
                "base_power": self.ui.sbase_doubleSpinBox,
                "frequency": self.ui.fbase_doubleSpinBox,
                "default_bus_voltage": self.ui.defaultBusVoltageSpinBox,
                "engine": self.ui.engineComboBox
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
                    "firm_capacity_share": self.ui.firmCapacityShareSpinBox,
                },
                "stochastic": {
                    "method": self.ui.stochastic_pf_method_comboBox,
                    "voltage_variance": self.ui.tolerance_stochastic_spinBox,
                    "number_of_samples": self.ui.max_iterations_stochastic_spinBox
                },
                "cascading": {
                    "additional_islands": self.ui.cascading_islands_spinBox
                },
                "reliability": {
                    "method": self.ui.reliability_method_comboBox,
                    "number_of_samples": self.ui.max_iterations_reliability_spinBox
                },
            },
            "linear": {
                "ptdf_threshold": self.ui.ptdf_threshold_doubleSpinBox,
                "lodf_threshold": self.ui.lodf_threshold_doubleSpinBox,
                "correct_nonsense_values": self.ui.ptdf_correct_nonsense_values_checkBox,
                "distributed_slack": self.ui.ptdf_distributed_slack_checkBox,
                "use_jacobian": self.ui.ptdf_use_jacobian_checkBox,
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
                "initialize_angles": self.ui.initialize_pf_angles_checkBox,
                "controls_start_tolerance": self.ui.controls_start_tolerance_spinBox
            },
            "state_estimation": {
                "solver": self.ui.se_solver_comboBox,
                "tolerance": self.ui.se_tolerance_spinBox,
                "max_iter": self.ui.se_max_iterations_spinBox,
                "prefer_correct": self.ui.se_prefer_correct_checkBox,
                "fixed_slack": self.ui.se_fixed_slack_checkBox,
                "run_observability_analyis": self.ui.se_observability_analysis_checkBox,
                "add_pseudo_measurements": self.ui.se_add_pseudo_measurements_checkBox,
                "run_measurement_profiling": self.ui.se_measurements_profiling_checkBox
            },
            "optimal_power_flow": {
                "method": self.ui.lpf_solver_comboBox,
                "time_grouping": self.ui.opf_time_grouping_comboBox,
                "zone_grouping": self.ui.opfZonalGroupByComboBox,
                "mip_framework": self.ui.mip_framework_comboBox,
                "mip_solver": self.ui.mip_solver_comboBox,
                "contingency_tolerance": self.ui.opfContingencyToleranceSpinBox,
                "skip_generation_limits": self.ui.skipOpfGenerationLimitsCheckBox,
                "consider_contingencies": self.ui.considerContingenciesOpfCheckBox,
                "dispatch_mode": self.ui.opfDispatchModeComboBox,
                "consider_ramps": self.ui.opfConsiderRampsCheckBox,
                "consider_time_up_down": self.ui.opfConsiderUpDownTimeCheckBox,
                "area_spinning_reserve": self.ui.opfSpinningReserveCheckBox,
                "add_opf_report": self.ui.addOptimalPowerFlowReportCheckBox,
                "robust_mip": self.ui.fixOpfCheckBox,
                "save_mip": self.ui.save_mip_checkBox,
                "use_glsk_as_cost": self.ui.useGslkAsCostsOpfCheckBox,
                "quadratic_costs": self.ui.quadraticCostsOpfCheckBox,
                "add_losses_approximation": self.ui.approximateLossesOpfCheckBox,
                "ips_method": self.ui.ips_method_comboBox,
                "ips_tolerance": self.ui.ips_tolerance_spinBox,
                "ips_iterations": self.ui.ips_iterations_spinBox,
                "ips_trust_radius": self.ui.ips_trust_radius_doubleSpinBox,
                "ips_init_with_pf": self.ui.ips_initialize_with_pf_checkBox,
                "ips_control_Qlimits": self.ui.ips_control_Qlimits_checkBox,
                "ips_verbose": self.ui.ips_verbose_spinBox,
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
                "strict_formulation": self.ui.strict_ntc_formulation_checkBox,
                "use_pf_values_for_atc": self.ui.usePfValuesForAtcCheckBox,
            },
            "nodal_hosting_capacity": {
                "method": self.ui.nodal_capacity_method_comboBox,
                "sense": self.ui.nodal_capacity_sense_SpinBox
            },
            "contingencies": {
                "contingencies_engine": self.ui.contingencyEngineComboBox,
                "filter_by": self.ui.contingency_filter_by_comboBox,
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
                # "current_boundary_set": self.current_boundary_set,
                # "cgmes_selected_version": self.ui.cgmes_version_comboBox,
                # "cgmes_single_profile_per_file": self.ui.cgmes_single_profile_per_file_checkBox,
                # "map_regions_like_raw": self.ui.cgmes_map_regions_like_raw_checkBox,
                # "raw_selected_version": self.ui.raw_export_version_comboBox,
                # "cgmes_dc_as_hvdclines": self.ui.cgmes_dc_as_hvdclines_checkBox,
            },
            "dyn": {
                "problem": self.ui.rms_problem_comboBox,
                "small_signal_modes_number": self.ui.rms_small_signal_modes_number_spinBox,
                "rms_int_method_comboBox": self.ui.rms_integration_method_comboBox,
                "rms_initialization_method": self.ui.rms_initialization_method_comboBox,
                "tolerance_rms_spinBox": self.ui.tolerance_rms_spinBox,
                "sim_time_spinBox": self.ui.rms_sim_time_spinBox,
                "h_spinBox": self.ui.rms_h_spinBox,

                "ss_assessment_time_spinBox_2": self.ui.rms_ss_assessment_time_spinBox
            },
            "emt": {
                "integration_method": self.ui.emt_integration_method_comboBox,
                "initialization_method": self.ui.emt_initialization_method_comboBox,
                "problem": self.ui.emt_problem_comboBox,
                "solver_type": self.ui.emt_solver_type_comboBox,
                "tolerance": self.ui.tolerance_emt_spinBox,
                "simulation_time": self.ui.emt_sim_time_spinBox,
                "step_size": self.ui.emt_h_spinBox,
                "ss_assessment_time": self.ui.emt_ss_assessment_time_spinBox,
                "small_signal_modes_number": self.ui.emt_small_signal_modes_number_spinBox,
                "sss_target_period": self.ui.emt_sss_target_period_spinBox,
                "sss_build_type": self.ui.emt_sss_build_type_comboBox,
            },
            "topology": {
                "use_rx_threshold": self.ui.rxThresholdCheckBox,
                "rx_threshold": self.ui.rxThresholdSpinBox,
                "branch_rating": self.ui.branch_rating_doubleSpinBox,
                "rating_override": self.ui.rating_override_checkBox,
            },
            "results": {
                "transpose": self.ui.results_traspose_checkBox,
                "as_cdf": self.ui.results_as_cdf_checkBox,
                "as_abs": self.ui.results_as_abs_checkBox,
                "stacked_plot": self.ui.stacked_plot_checkBox,
            },
            "profiles": {
                "scale_factor": self.ui.profile_factor_doubleSpinBox,
            },
            "compiled_arrays": {
                "display_mode": self.ui.arrayModeComboBox,
            },
        }

    def get_gui_config_data(self) -> Dict[str, Dict[str, Union[float, int, str, bool]]]:
        """
        Get a dictionary with the GUI configuration data
        :return:
        """
        struct = self.get_config_structure()
        data = dict()
        gui_struct_to_data(data, struct)

        # Persist the language as an enum name so the saved value remains stable
        # even when the visible language labels themselves are translated.
        graphics_data: object = data.get("graphics", None)
        if isinstance(graphics_data, dict):
            graphics_data["language"] = self.get_selected_language().name
        else:
            pass

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

        # Apply the theme through the same path used by the dark-mode checkbox,
        # so the main editor, console, diagrams, and dynamic editor stay aligned.
        self.change_theme_mode()

        graphics_data: object = data.get("graphics", None)
        if isinstance(graphics_data, dict):
            saved_language_name: object = graphics_data.get("language", None)
            if isinstance(saved_language_name, str):
                selected_language: ApplicationLanguage = language_from_name(saved_language_name)
                self.set_selected_language(selected_language)

                if self.translation_controller is not None:
                    self.translation_controller.set_language(selected_language)
                else:
                    pass
            else:
                pass
        else:
            pass

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
                       text=QtCore.QCoreApplication.translate("ContextMenu", "Reload"),
                       icon_path=":/Icons/icons/undo.png",
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
                    icon_path=":/Icons/icons/plugin.png",
                    icon_pixmap=plugin_info.icon,
                    function_ptr=lambda: self.launch_plugin(plugin_info.main_fcn)
                )

            # maybe add the investments function
            if plugin_info.investments_fcn.function_ptr is not None:
                self.plugins_investment_evaluation_method_dict[
                    plugin_info.investments_fcn.alias
                ] = plugin_info.investments_fcn.function_ptr

    def launch_plugin(self, fcn: PluginFunction):
        """
        Action wrapper to launch the plugin
        :param fcn: some PluginFunction
        """

        # call the main function of the plugin
        ret = fcn.get_pointer_lambda(gui_instance=self)()

        if fcn.call_gui and ret is not None:
            if isinstance(ret, QtWidgets.QWidget):
                self.plugin_windows_list.append(ret)  # This avoids the window to be garbage collected and be displayed
                ret.show()
            else:
                pass
