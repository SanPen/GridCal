# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import sys

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.DeviceEditors.DcLineEditor.dc_line_editor import DcLineEditor, DcLineTemplate
from VeraGrid.Gui.DeviceEditors.TemplateDeviceEditor.template_device_editor import TemplateDeviceEditor
from VeraGrid.Gui.messages import warning_msg
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit


class EmbeddedDcLineDesignEditorWidget(DcLineEditor):
    """
    Embedded DC-line design editor widget used inside ``DcLineDeviceEditor``.
    """

    design_applied = QtCore.Signal(bool)

    def __init__(self,
                 branch: DcLine,
                 sbase: float,
                 templates: list[DcLineTemplate] | None,
                 current_template: DcLineTemplate | None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """
        Build the embedded DC-line design editor.

        :param branch: DC line object to edit.
        :param sbase: Base power in MVA used by the internal per-unit conversions.
        :param templates: Optional compatible design templates.
        :param current_template: Optional currently assigned template.
        :param parent: Optional Qt parent widget.
        """
        DcLineEditor.__init__(self,
                              branch=branch,
                              Sbase=sbase,
                              templates=templates,
                              current_template=current_template)
        if parent is not None:
            self.setParent(parent)
        else:
            pass

        # The legacy editor is dialog-based. Keep it embeddable in a tab.
        self.setWindowFlags(QtCore.Qt.WindowType.Widget)
        self.setWindowTitle("")
        self.ui.acceptButton.hide()
        self._apply_success: bool = False

    def accept(self) -> None:
        """
        Intercept dialog acceptance so the embedded widget does not close itself.
        """
        self._apply_success = True
        self.design_applied.emit(True)

    def apply_changes(self) -> bool:
        """
        Apply current design fields to the DC-line API object.

        :return: ``True`` when values were successfully applied.
        """
        self._apply_success = False
        self.accept_click()
        return self._apply_success


class DcLineDeviceEditor(TemplateDeviceEditor):
    """
    Specialized DC-line editor that extends ``TemplateDeviceEditor``.
    """

    def __init__(self, api_object: DcLine, circuit: MultiCircuit | None = None) -> None:
        """
        Build the DC-line editor.

        :param api_object: DC line edited in place.
        :param circuit: Optional circuit context.
        """
        TemplateDeviceEditor.__init__(self, api_object=api_object, circuit=circuit)
        self.api_object: DcLine = api_object
        self.setWindowTitle(self.tr("DC line editor"))

        self.dc_line_design_widget: EmbeddedDcLineDesignEditorWidget | None = None
        self._build_dc_line_design_tab()

    def _build_dc_line_design_tab(self) -> None:
        """
        Build and configure the embedded DC-line design tab.
        """
        self.dc_line_design_tab: QtWidgets.QWidget = QtWidgets.QWidget(self.tab_widget)
        self.dc_line_design_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self.dc_line_design_tab)
        self.dc_line_design_button_layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        self.dc_line_design_apply_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            "Apply DC line design",
            self.dc_line_design_tab,
        )
        self.dc_line_design_button_layout.addWidget(self.dc_line_design_apply_button)
        self.dc_line_design_button_layout.addStretch()
        self.dc_line_design_layout.addLayout(self.dc_line_design_button_layout)

        if self.circuit is not None:
            # AC and DC branches share the Cable System catalogue.
            available_templates: list[DcLineTemplate] = list()
            available_templates.extend(self.circuit.underground_cable_types)

            self.dc_line_design_widget = EmbeddedDcLineDesignEditorWidget(
                branch=self.api_object,
                sbase=self.circuit.Sbase,
                templates=available_templates,
                current_template=self.api_object.template,
                parent=self.dc_line_design_tab,
            )
            self.dc_line_design_widget.design_applied.connect(self._on_dc_line_design_applied)
            self.dc_line_design_layout.addWidget(self.dc_line_design_widget)
            self.dc_line_design_apply_button.clicked.connect(self._apply_dc_line_design)
        else:
            self.dc_line_design_widget = None
            self.dc_line_design_apply_button.setEnabled(False)
            missing_msg: QtWidgets.QLabel = QtWidgets.QLabel(
                "DC line design editor requires a circuit context.",
                self.dc_line_design_tab,
            )
            self.dc_line_design_layout.addWidget(missing_msg)

        self.tab_widget.addTab(self.dc_line_design_tab, "DcLineEditor")

    def _apply_dc_line_design(self) -> None:
        """
        Apply current values from the DC-line design tab and refresh base tables.
        """
        if self.dc_line_design_widget is not None:
            self.dc_line_design_widget.apply_changes()
        else:
            warning_msg(self.tr("DC line design widget is not available"), self.tr("DC line editor"))

    def _on_dc_line_design_applied(self, applied_ok: bool) -> None:
        """
        Refresh base snapshot/profile tabs after one DC-line design apply.

        :param applied_ok: Apply status.
        """
        if applied_ok:
            self.properties_model.set_time_index(time_index=self._get_current_time_index())
            self.refresh_profile_table()
            self.show_info_toast("DC line values applied")
        else:
            pass


DcLineDeviceEditorDialog = DcLineDeviceEditor


if __name__ == "__main__":
    qt_app: QtWidgets.QApplication = QtWidgets.QApplication(sys.argv)

    # Build one minimal circuit context so delegates and profile logic can be inspected.
    circuit_demo: MultiCircuit = MultiCircuit(name="DC line device editor demo", Sbase=100.0, fbase=50.0)
    bus_from_demo: Bus = Bus(name="DC bus from", Vnom=320.0, is_dc=True)
    bus_to_demo: Bus = Bus(name="DC bus to", Vnom=320.0, is_dc=True)
    circuit_demo.add_bus(obj=bus_from_demo)
    circuit_demo.add_bus(obj=bus_to_demo)

    dc_line_demo: DcLine = DcLine(
        bus_from=bus_from_demo,
        bus_to=bus_to_demo,
        name="Demo DC line",
        r=0.02,
        rate=500.0,
        length=10.0,
    )
    circuit_demo.add_dc_line(obj=dc_line_demo)

    dialog_demo: DcLineDeviceEditor = DcLineDeviceEditor(api_object=dc_line_demo, circuit=circuit_demo)
    dialog_demo.show()
    sys.exit(qt_app.exec())
