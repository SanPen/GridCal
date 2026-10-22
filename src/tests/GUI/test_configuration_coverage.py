"""Check GUI preference coverage independently of the configuration mapping."""

import json
from typing import Any, Dict

from PySide6 import QtWidgets

from VeraGrid.Gui.Main.MainWindow import Ui_mainWindow
from VeraGrid.Gui.Main.SubClasses.Settings.configuration import (
    ConfigurationMain, config_data_to_struct, gui_struct_to_data,
)


class ConfigurationTestWindow(ConfigurationMain):
    """Use the real generated controls without loading user files or starting services."""

    __slots__ = ()

    def __init__(self) -> None:
        """Build the GUI controls required by the production configuration method.

        :return: None.
        """
        QtWidgets.QMainWindow.__init__(self)
        self.ui: Ui_mainWindow = Ui_mainWindow()
        self.ui.setupUi(self)


def collect_configuration_widgets(structure: Dict[str, Any]) -> Dict[str, QtWidgets.QWidget]:
    """Flatten the mapping using actual widget names rather than settings keys.

    :param structure: Production configuration structure.
    :return: Widgets indexed by their Qt object names.
    """
    widgets: Dict[str, QtWidgets.QWidget] = dict()
    for value in structure.values():
        if isinstance(value, dict):
            widgets.update(collect_configuration_widgets(value))
        elif isinstance(value, QtWidgets.QWidget):
            assert value.objectName() not in widgets, value.objectName()
            widgets[value.objectName()] = value
        else:
            pass
    return widgets


def test_every_gui_preference_has_a_persistence_path(qt_app: QtWidgets.QApplication) -> None:
    """Compare every editable control against preferences or an explicit exclusion.

    The inventory comes from the generated UI, independently of get_config_structure.
    New controls must therefore be persisted or assigned an intentional exclusion.
    Language and server controls have their own existing save/restore paths;
    circuit state, searches, and model-dependent selectors are not global defaults.

    :param qt_app: Shared offscreen application.
    :return: None.
    """
    window: ConfigurationTestWindow = ConfigurationTestWindow()
    widgets: Dict[str, QtWidgets.QWidget] = collect_configuration_widgets(window.get_config_structure())
    excluded: Dict[str, str] = dict(
        language_combo_box="Saved and restored separately by ConfigurationMain",
        server_url_lineEdit="ServerMain.server_config.json",
        server_port_spinBox="ServerMain.server_config.json",
        server_pwd_lineEdit="ServerMain.server_config.json",
        secureServerConnectionCheckBox="ServerMain.server_config.json",
        grid_name_line_edit="Circuit name stored in the project",
        snapshot_dateTimeEdit="Circuit snapshot time stored in the project",
        comments_textEdit="Circuit comments stored in the project",
        resultsReportTextEdit="Generated study report",
        diagram_step_slider="Selected time point in the current circuit",
        db_step_slider="Selected time point in the current circuit",
        compiled_arrays_step_slider="Selected time point in the compiled circuit",
        sourceCodeNameLineEdit="Current script name",
        diagramSearchLineEdit="Transient diagram search",
        device_tree_search_lineEdit="Transient device search",
        smart_search_lineEdit="Transient data search",
        search_results_lineEdit="Transient results search",
        search_dynamic_objects_lineEdit="Transient dynamic-object search",
        available_results_to_color_comboBox="Current study result selection",
        dbFilterComboBox="Current data view selection",
        associationsComboBox="Current device association selection",
        device_type_magnitude_comboBox="Magnitude selection depends on the selected device type",
        device_type_magnitude_comboBox_2="Magnitude selection depends on the selected device type",
        goToTsPointComboBox="Time points depend on the current circuit",
        simulation_data_island_comboBox="Islands depend on the compiled circuit",
        fromComboBox="Transfer source depends on current circuit aggregations",
        toComboBox="Transfer destination depends on current circuit aggregations",
    )
    editable: Dict[str, QtWidgets.QWidget] = dict()
    for widget in window.findChildren(QtWidgets.QWidget):
        if isinstance(widget, (QtWidgets.QComboBox, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox,
                               QtWidgets.QCheckBox, QtWidgets.QRadioButton, QtWidgets.QLineEdit,
                               QtWidgets.QDateTimeEdit, QtWidgets.QSlider, QtWidgets.QTextEdit,
                               QtWidgets.QPlainTextEdit)) or (
                isinstance(widget, QtWidgets.QGroupBox) and widget.isCheckable()):
            # Spin boxes and editable combos contain private line-edit children.
            if widget.objectName() and not widget.objectName().startswith("qt_"):
                editable[widget.objectName()] = widget
            else:
                pass
        else:
            pass
    assert not set(widgets).intersection(excluded)
    assert set(excluded).issubset(editable), "Remove obsolete exclusions when controls disappear"
    assert set(editable) == set(widgets).union(excluded), sorted(set(editable).difference(widgets, excluded))
    window.close()


def test_all_mapped_preferences_round_trip_through_json(qt_app: QtWidgets.QApplication) -> None:
    """Change every mapped control, save JSON, reset it, and restore its exact value.

    Real spin boxes, checkboxes, radio buttons, and combos exercise both recursive
    serializer directions. Combos use stable item data so display text is not
    mistaken for the stored value. No operator configuration files are touched.

    :param qt_app: Shared offscreen application.
    :return: None.
    """
    window: ConfigurationTestWindow = ConfigurationTestWindow()
    structure: Dict[str, Any] = window.get_config_structure()
    widgets: Dict[str, QtWidgets.QWidget] = collect_configuration_widgets(structure)
    for widget in widgets.values():
        if isinstance(widget, QtWidgets.QComboBox):
            widget.clear()
            widget.addItem("First label", "first-key")
            widget.addItem("Second label", "second-key")
            widget.setCurrentIndex(1)
        elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            widget.setValue(min(widget.maximum(), widget.minimum() + widget.singleStep()))
        elif isinstance(widget, QtWidgets.QRadioButton):
            widget.setAutoExclusive(False)
            widget.setChecked(True)
        elif isinstance(widget, QtWidgets.QCheckBox):
            widget.setChecked(True)
        else:
            raise AssertionError(widget.objectName())
    expected: Dict[str, Any] = dict()
    gui_struct_to_data(expected, structure)
    saved: Dict[str, Any] = json.loads(json.dumps(expected))
    for widget in widgets.values():
        if isinstance(widget, QtWidgets.QComboBox):
            widget.setCurrentIndex(0)
        elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            widget.setValue(widget.minimum())
        elif isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QRadioButton)):
            widget.setChecked(False)
        else:
            raise AssertionError(widget.objectName())
    config_data_to_struct(saved, structure)
    restored: Dict[str, Any] = dict()
    gui_struct_to_data(restored, structure)
    assert restored == expected
    window.close()


def test_old_configuration_keeps_new_control_defaults(qt_app: QtWidgets.QApplication) -> None:
    """Load an older partial configuration without resetting newly added settings.

    :param qt_app: Shared offscreen application.
    :return: None.
    """
    window: ConfigurationTestWindow = ConfigurationTestWindow()
    window.ui.emt_sim_time_spinBox.setValue(2.5)
    config_data_to_struct(dict(power_flow=dict(max_iterations=17)), window.get_config_structure())
    assert window.ui.max_iterations_spinBox.value() == 17
    assert window.ui.emt_sim_time_spinBox.value() == 2.5
    window.close()
