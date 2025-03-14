# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations


from PySide6 import QtWidgets
from typing import List
from GridCal.Gui.SubstationDesigner.substation_designer_gui import Ui_Dialog
from GridCal.Gui.object_model import ObjectsModel
from GridCal.Gui.messages import yes_no_question
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.enumerations import DeviceType, SubstationTypes
import GridCalEngine.Devices as dev


class VoltageLevelTemplate(EditableDevice):

    def __init__(self, name='', code='', idtag: str | None = None,
                 device_type=DeviceType.GenericArea, voltage: float = 10):
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=device_type)

        self.vl_type: SubstationTypes = SubstationTypes.SingleBar
        self.voltage: float = voltage

        self.register(key='vl_type', units='', tpe=SubstationTypes, definition='longitude.', editable=True)
        self.register(key='voltage', units='KV', tpe=float, definition='Voltage.', editable=True)


class SubstationDesigner(QtWidgets.QDialog):
    """
    SubstationDesigner
    """

    def __init__(self, grid: MultiCircuit, default_voltage: float = 10.0, parent=None):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Substation maker')

        self.grid = grid

        self.default_voltage = default_voltage

        self._accepted = False

        self.ui.se_name_lineEdit.setText(f"Substation {self.grid.get_substation_number()}")
        self.ui.se_code_lineEdit.setText('')

        obj1 = VoltageLevelTemplate(name="VL", voltage=self.default_voltage,
                                    device_type=DeviceType.VoltageLevelTemplate)

        self.property_list = [obj1.property_list[i] for i in [1, 5, 6]]

        self.mdl = ObjectsModel(objects=[obj1],
                                property_list=self.property_list,
                                time_index=None,
                                parent=self.ui.tableView,
                                editable=True)

        self.ui.tableView.setModel(self.mdl)

        self.ui.addVlButton.clicked.connect(self.add_vl)
        self.ui.deleteVlButton.clicked.connect(self.remove_vl)
        self.ui.createButton.clicked.connect(self.create_se)

    def get_name(self):
        """
        Get the SE name
        :return:
        """
        return self.ui.se_name_lineEdit.text()

    def get_code(self):
        """
        Get the SE code
        :return:
        """
        return self.ui.se_code_lineEdit.text()

    def get_selected_objects(self):
        """
        Get the list of selected objects
        :return:
        """

        if self.mdl is not None:
            sel_idx = self.ui.tableView.selectedIndexes()
            if len(sel_idx) > 0:

                # get the unique rows
                unique = set()
                for idx in sel_idx:
                    unique.add(idx.row())

                return [self.mdl.objects[i] for i in unique]
            else:
                return list()
        else:
            return list()

    def add_vl(self) -> None:
        """
        Add voltage level
        :return:
        """
        obj1 = VoltageLevelTemplate(name="VL", voltage=self.default_voltage,
                                    device_type=DeviceType.VoltageLevelTemplate)
        self.mdl.objects.append(obj1)
        self.mdl.update()

    def remove_vl(self):
        """
        Remove voltage level
        :return:
        """
        sel = self.get_selected_objects()
        cpy_lst = self.mdl.objects.copy()
        for obj in sel:
            cpy_lst.remove(obj)

        self.mdl = ObjectsModel(objects=cpy_lst,
                                property_list=self.property_list,
                                time_index=None,
                                parent=self.ui.tableView,
                                editable=True)

        self.ui.tableView.setModel(self.mdl)

    def get_voltage_levels(self) -> List[VoltageLevelTemplate]:
        """
        Get the list of voltage levels
        :return:
        """
        return self.mdl.objects

    def was_ok(self) -> bool:
        """
        Get if to create substation
        """
        return self._accepted

    def create_se(self):
        """
        Create the thing
        :return:
        """
        if len(self.mdl.objects) > 0:
            self._accepted = True
            self.close()
        else:
            ok = yes_no_question("There are no voltage levels, so no substation will be created, ok?")
            if ok:
                self._accepted = False
                self.close()


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = SubstationDesigner(None)
    # window.resize(int(1.61 * 700.0), int(600.0))  # golden ratio
    window.show()
    sys.exit(app.exec())
