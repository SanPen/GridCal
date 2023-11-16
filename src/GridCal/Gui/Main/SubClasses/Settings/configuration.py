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
import json
import os
import qdarktheme
from typing import Dict, Union
from PySide6 import QtWidgets

from GridCalEngine.IO.file_system import get_create_gridcal_folder
from GridCal.Gui.Main.SubClasses.Results.results import ResultsMain
from GridCal.Gui.GridEditorWidget import BusBranchEditorWidget


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

        # check boxes
        self.ui.dark_mode_checkBox.clicked.connect(self.change_theme_mode)

    def change_theme_mode(self) -> None:
        """
        Change the GUI theme
        :return:
        """
        custom_colors = {"primary": "#00aa88ff",
                         "primary>list.selectionBackground": "#00aa88be"}

        if self.ui.dark_mode_checkBox.isChecked():
            qdarktheme.setup_theme(theme='dark', custom_colors=custom_colors)

            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, BusBranchEditorWidget):
                    diagram.set_dark_mode()

            self.colour_diagrams()

            if self.console is not None:
                self.console.set_dark_theme()
        else:
            qdarktheme.setup_theme(theme='light', custom_colors=custom_colors)

            diagram = self.get_selected_diagram_widget()
            if diagram is not None:
                if isinstance(diagram, BusBranchEditorWidget):
                    diagram.set_light_mode()

            self.colour_diagrams()

            if self.console is not None:
                self.console.set_light_theme()

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

    @staticmethod
    def scripts_path() -> str:
        """
        get the config file path
        :return: config file path
        """
        pth = os.path.join(get_create_gridcal_folder(), 'scripts')

        if not os.path.exists(pth):
            os.makedirs(pth)

        return pth

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
                "min_node_size": self.ui.min_node_size_spinBox,
                "max_node_size": self.ui.max_node_size_spinBox,
                "min_branch_size": self.ui.min_branch_size_spinBox,
                "max_branch_size": self.ui.max_branch_size_spinBox,
                "width_based_flow": self.ui.branch_width_based_on_flow_checkBox,
                "map_tile_provider": self.ui.tile_provider_comboBox,
                "plotting_style": self.ui.plt_style_comboBox
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
                }
            },
            "linear": {
                "perturbance_power": self.ui.atcPerturbanceSpinBox,
                "transfer_sensitivity_threshold": self.ui.atcThresholdSpinBox,
                "transfer_method": self.ui.transferMethodComboBox,
                "Loading_threshold_to_report": self.ui.ntcReportLoadingThresholdSpinBox,
                "consider_contingencies": self.ui.n1ConsiderationCheckBox
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
                "automatic_precision": self.ui.auto_precision_checkBox,
                "use_voltage_guess": self.ui.use_voltage_guess_checkBox,
                "precision": self.ui.tolerance_spinBox,
                "acceleration": self.ui.muSpinBox,
                "max_iterations": self.ui.max_iterations_spinBox,
                "verbosity": self.ui.verbositySpinBox,
                "reactive_power_control_mode": self.ui.reactive_power_control_mode_comboBox,
                "transformer_taps_control_mode": self.ui.taps_control_mode_comboBox,
                "apply_temperature_correction": self.ui.temperature_correction_checkBox,
                "apply_impedance_tolerances": self.ui.apply_impedance_tolerances_checkBox,
                "override_branch_controls": self.ui.override_branch_controls_checkBox,
                "add_pf_report": self.ui.addPowerFlowReportCheckBox,
            },
            "optimal_power_flow": {
                "method": self.ui.lpf_solver_comboBox,
                "time_grouping": self.ui.opf_time_grouping_comboBox,
                "zone_grouping": self.ui.opfZonalGroupByComboBox,
                "mip_solver": self.ui.mip_solver_comboBox,
                "contingency_tolerance": self.ui.opfContingencyToleranceSpinBox,
                "max_module_step": self.ui.maxVoltageModuleStepSpinBox,
                "max_angle_step": self.ui.maxVoltageAngleStepSpinBox,
                "skip_generation_limits": self.ui.skipOpfGenerationLimitsCheckBox,
                "consider_contingencies": self.ui.considerContingenciesOpfCheckBox,
                "maximize_area_exchange": self.ui.opfMaximizeExcahngeCheckBox,
                "unit_commitment": self.ui.opfUnitCommitmentCheckBox,
                "add_opf_report": self.ui.addOptimalPowerFlowReportCheckBox,
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
                "proportional_redispatch": self.ui.proportionalRedispatchRadioButton,
                "optimal_redispatch": self.ui.optimalRedispatchRadioButton,
                "skip_generation_limits": self.ui.skipNtcGenerationLimitsCheckBox,
                "dispatch_all_areas": self.ui.ntcDispatchAllAreasCheckBox,
                "check_feasibility": self.ui.ntcFeasibilityCheckCheckBox,

                "ntc_lodf_tolerance": self.ui.ntcLODFToleranceSpinBox,
                "transmission_reliability_margin": self.ui.trmSpinBox,

                "branch_exchange_sensitivity": self.ui.ntcAlphaSpinBox,
                "branch_rating_contribution": self.ui.ntcLoadRuleSpinBox,

                "consider_branch_contingencies": self.ui.considerContingenciesNtcOpfCheckBox,
                "consider_hvdc_contingencies": self.ui.considerContingenciesHvdcOpfCheckBox,
                "consider_generator_contingencies": self.ui.considerContingenciesGeneratorOpfCheckBox,
                "generator_contingency_power": self.ui.contingencyGenerationThresholdDoubleSpinBox,

                "power_shift_weight": self.ui.weightPowerShiftSpinBox,
                "generation_cost_weight": self.ui.weightGenCostSpinBox,
                "branch_overload_weight": self.ui.weightsOverloadsSpinBox,
            },
            "general": {
                "base_power": self.ui.sbase_doubleSpinBox,
                "frequency": self.ui.fbase_doubleSpinBox,
                "default_bus_voltage": self.ui.defaultBusVoltageSpinBox,
                "engine": self.ui.engineComboBox
            },
            "contingencies": {
                "contingencies_engine": self.ui.contingencyEngineComboBox
            },
            "file": {
                "store_results_in_file": self.ui.saveResultsCheckBox
            }
        }

    def get_gui_config_data(self) -> Dict[str, Dict[str, Union[float, int, str, bool]]]:
        """
        Get a dictionary with the GUI configuration data
        :return:
        """

        def struct_to_data(data_: Dict[str, Dict[str, Union[float, int, str, bool, Dict]]],
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
                else:
                    raise Exception('unknown structure')

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

    def apply_gui_config(self, data: dict):
        """
        Apply GUI configuration dictionary
        :param data: GUI configuration dictionary
        """

        def data_to_struct(data_, struct_):
            """
            Recursive function to set the GUI values from the config dictionary
            :param data_: config dictionary with values from the file
            :param struct_: result of self.get_config_structure()
            """
            for key, instance in struct_.items():
                if key in data_:
                    if isinstance(instance, dict):
                        data_to_struct(data_[key], instance)
                    elif isinstance(instance, QtWidgets.QComboBox):
                        val = data_[key]
                        index = instance.findText(val)
                        if -1 < index < instance.count():
                            instance.setCurrentIndex(index)
                    elif isinstance(instance, QtWidgets.QDoubleSpinBox):
                        instance.setValue(float(data_[key]))
                    elif isinstance(instance, QtWidgets.QSpinBox):
                        instance.setValue(int(data_[key]))
                    elif isinstance(instance, QtWidgets.QCheckBox):
                        instance.setChecked(bool(data_[key]))
                    elif isinstance(instance, QtWidgets.QRadioButton):
                        instance.setChecked(bool(data_[key]))
                    else:
                        raise Exception('unknown structure')
                else:
                    print(key)

        struct = self.get_config_structure()
        data_to_struct(data_=data, struct_=struct)

    def load_gui_config(self) -> None:
        """
        Load GUI configuration from the local user folder
        """
        if self.config_file_exists():
            with open(self.config_file_path(), "r") as f:
                data = json.load(f)
                self.apply_gui_config(data=data)
                self.change_theme_mode()
