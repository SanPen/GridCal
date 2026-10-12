# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import sys
import numpy as np
from PySide6 import QtWidgets

from VeraGrid.Gui.DeviceEditors.DcLineEditor.dc_line_editor_gui import Ui_DcLineEditorDialog
from VeraGrid.Gui.gui_functions import get_list_model
from VeraGrid.Gui.messages import warning_msg
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.underground_line_type import UndergroundLineType
from VeraGridEngine.Devices.Substation.bus import Bus

DcLineTemplate = UndergroundLineType


class DcLineEditor(QtWidgets.QDialog):
    """Apply a common Cable System or enter a resistive DC branch manually."""

    def __init__(self, branch: DcLine, Sbase: float = 100.0,
                 templates: list[DcLineTemplate] | None = None,
                 current_template: DcLineTemplate | None = None) -> None:
        super().__init__()
        self.ui = Ui_DcLineEditorDialog()
        self.ui.setupUi(self)
        self.setWindowTitle(self.tr('DC line editor'))
        self.branch = branch
        self.sbase = Sbase
        self.templates = list(templates or [])
        self.current_template = current_template if current_template is not None else branch.template
        if self.current_template is not None and self.current_template not in self.templates:
            self.templates.append(self.current_template)
        self.selected_template = None
        self.ui.templatesLabel.setText(self.tr('Available Cable Systems'))
        self.ui.catalogueComboBox.setModel(get_list_model(self.templates))

        self.use_template = QtWidgets.QCheckBox(self.tr('Use Cable System'), self)
        self.conductor_label = QtWidgets.QLabel(self.tr('Cable System conductor'), self)
        self.conductor_combo = QtWidgets.QComboBox(self)
        self.dynamic_label = QtWidgets.QLabel(self)
        self.dynamic_label.setWordWrap(True)
        for offset, widget in enumerate((self.use_template, self.conductor_label,
                                         self.conductor_combo, self.dynamic_label)):
            self.ui.verticalLayout.insertWidget(3 + offset, widget)

        voltage = self.branch.get_max_bus_nominal_voltage()
        zbase = voltage * voltage / self.sbase if self.sbase > 0 else 0.0
        self.ui.lengthSpinBox.setDecimals(6)
        self.ui.lengthSpinBox.setMinimum(0.000001)
        self.ui.resistanceSpinBox.setDecimals(10)
        self.ui.currentSpinBox.setDecimals(8)
        self.ui.lengthSpinBox.setValue(branch.length)
        self.ui.resistanceSpinBox.setValue(branch.R * zbase / branch.length if branch.length > 0 else 0.0)
        self.ui.currentSpinBox.setValue(branch.rate / voltage if voltage > 0 else 0.0)
        self.ui.currentLabel.setText(self.tr('Branch current rating [kA] @ {voltage:g} kV').format(voltage=voltage))

        self.ui.loadTemplateButton.clicked.connect(self.load_template_btn_click)
        self.ui.acceptButton.clicked.connect(self.accept_click)
        self.use_template.toggled.connect(self._refresh_parameters)
        self.conductor_combo.currentIndexChanged.connect(self._refresh_parameters)
        if self.current_template is not None:
            self.ui.catalogueComboBox.setCurrentIndex(self.templates.index(self.current_template))
            self.load_template(self.current_template)
        else:
            self._refresh_parameters()
        self.ui.loadTemplateButton.setEnabled(bool(self.templates))

    def load_template(self, template: DcLineTemplate) -> None:
        """Load the selected system, retaining the branch's existing rating."""
        self.selected_template = template
        self.conductor_combo.blockSignals(True)
        self.conductor_combo.clear()
        numbers = sorted({item.phase for item in template.cables_in_system.data}) if template.has_physical_data() else [1]
        for number in numbers:
            self.conductor_combo.addItem(str(number), number)
        index = self.conductor_combo.findData(self.branch.dc_conductor)
        self.conductor_combo.setCurrentIndex(max(0, index))
        self.conductor_combo.blockSignals(False)
        self.use_template.setChecked(True)
        self._refresh_parameters()

    def _refresh_parameters(self, *_args) -> None:
        enabled = self.use_template.isChecked()
        self.ui.resistanceSpinBox.setEnabled(not enabled)
        self.conductor_combo.setEnabled(enabled)
        self.dynamic_label.clear()
        if enabled and self.selected_template is not None:
            try:
                resistance, inductance, capacitance = self.selected_template.get_dc_parameters(
                    self.conductor_combo.currentData())
                self.ui.resistanceSpinBox.setValue(resistance)
                self.dynamic_label.setText(f'L = {inductance:g} H/km; C = {capacitance * 1e6:g} µF/km')
            except ValueError as error:
                self.dynamic_label.setText(str(error))

    def accept_click(self) -> None:
        """Validate all fields before applying the DC design to the branch."""
        length = self.ui.lengthSpinBox.value()
        voltage = self.branch.get_max_bus_nominal_voltage()
        if not all(np.isfinite(value) and value > 0 for value in (length, voltage, self.sbase)):
            warning_msg(self.tr('Positive length, voltage and power base are required'), self.tr('DC line editor'))
            return
        candidate = self.branch.copy()
        # Validate the design without cloning dynamic blocks or rebinding buses.
        candidate.disable_auto_updates()
        candidate.length = length
        if self.use_template.isChecked():
            candidate.dc_conductor = self.conductor_combo.currentData()
            logger = Logger()
            candidate.apply_template(self.selected_template, self.sbase, logger)
            if logger.has_errors():
                warning_msg(str(logger), self.tr('Apply Cable System'))
                return
        else:
            candidate.R = self.ui.resistanceSpinBox.value() * length / (voltage * voltage / self.sbase)
            candidate.template = None

        self.branch.length = length
        self.branch.R = candidate.R
        self.branch.template = candidate.template
        if candidate.template is not None:
            self.branch.dc_conductor = candidate.dc_conductor
            self.branch.rms_template = candidate.rms_template
            self.branch.emt_template = candidate.emt_template
        self.branch.rate = self.ui.currentSpinBox.value() * voltage
        self.accept()

    def load_template_btn_click(self) -> None:
        index = self.ui.catalogueComboBox.currentIndex()
        if 0 <= index < len(self.templates):
            self.load_template(self.templates[index])


if __name__ == "__main__":
    qt_app = QtWidgets.QApplication(sys.argv)
    bus_from_demo = Bus(name="DC from", Vnom=320.0, is_dc=True)
    bus_to_demo = Bus(name="DC to", Vnom=320.0, is_dc=True)
    dc_line_demo = DcLine(
        bus_from=bus_from_demo,
        bus_to=bus_to_demo,
        name="Demo DC line",
        r=0.02,
        rate=500.0,
    )
    dialog_demo = DcLineEditor(branch=dc_line_demo, Sbase=100.0, templates=None, current_template=None)
    dialog_demo.show()
    sys.exit(qt_app.exec())
