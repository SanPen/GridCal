# This file is part of GridCal
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import sys
from typing import Union
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication
from PySide6 import QtCore, QtWidgets

from GridCal.Gui.SystemScaler.system_scaler_ui import Ui_Dialog
from GridCal.Gui.GuiFunctions import get_list_model, FloatDelegate
from GridCal.Gui.messages import yes_no_question
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Devices.multi_circuit import MultiCircuit


class SystemScalingModel(QtCore.QAbstractTableModel):
    """
    Class to populate a Qt table view with a pandas data frame
    """

    def __init__(self, device_tpe: DeviceType, grid: MultiCircuit, parent: QtWidgets.QTableView):
        """

        :param device_tpe:
        :param grid:
        :param parent:
        """
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.parent = parent
        self.device_tpe = device_tpe
        self.grid = grid
        self.objects = self.grid.get_elements_by_type(device_type=device_tpe)
        self.injections_per_type = self.grid.get_injection_devices_grouped_by_group_type(group_type=device_tpe)

        self._cols = ['Load factor', 'Generation factor', 'Total load (MW)', 'Total generation (MW)']
        self._editable = [True, True, False, False]
        self._index = [elm.name for elm in self.objects]
        self.r = len(self._index)
        self.c = len(self._cols)
        self._data = np.ones((self.r, self.c + 2))
        self.isDate = False

        if len(self._index) > 0:
            if isinstance(self._index[0], np.datetime64):
                self._index = pd.to_datetime(self._index)
                self.isDate = True

        self.formatter = lambda x: "%.2f" % x
        self.set_delegates()

        self.original_powers = np.zeros((self.r, 2))

        # compute totals per type
        for i in range(self.r):
            gens = self.injections_per_type[i].get(DeviceType.GeneratorDevice, list())
            loads = self.injections_per_type[i].get(DeviceType.LoadDevice, list())

            # get the original area, zone, etc. power
            self.original_powers[i, 0] = sum([elm.P + elm.G + elm.Ii for elm in loads])
            self.original_powers[i, 1] = sum([elm.P for elm in gens])

            # compute the total scaling power of the area, zone, etc...
            self._data[i, 2] = self.original_powers[i, 0] * self._data[i, 0]
            self._data[i, 3] = self.original_powers[i, 1] * self._data[i, 1]

    def flags(self, index: QtCore.QModelIndex):
        """
        Get the display mode
        :param index:
        :return:
        """

        if self._editable[index.column()]:
            return (QtCore.Qt.ItemFlag.ItemIsEditable |
                    QtCore.Qt.ItemFlag.ItemIsEnabled |
                    QtCore.Qt.ItemFlag.ItemIsSelectable)
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def update(self):
        """
        update table
        """
        row = self.rowCount()
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        # whatever code
        self.endInsertRows()

    def set_delegates(self) -> None:
        """
        Set the cell editor types depending on the attribute_types array
        """

        for i in range(self.c):
            delegate = FloatDelegate(self.parent)
            self.parent.setItemDelegateForColumn(i, delegate)

    def rowCount(self, parent: Union[QtCore.QModelIndex, None] = None):
        """

        :param parent:
        :return:
        """
        return self.r

    def columnCount(self, parent: Union[QtCore.QModelIndex, None] = None):
        """

        :param parent:
        :return:
        """
        return self.c

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if index.isValid():
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                return self.formatter(self._data[index.row(), index.column()])
                # return str(self._data[index.row(), index.column()])
        return None

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self._cols[section]
            elif orientation == QtCore.Qt.Orientation.Vertical:
                if self._index is None:
                    return section
                else:
                    if self.isDate:
                        return self._index[section].strftime('%Y/%m/%d  %H:%M.%S')
                    else:
                        return str(self._index[section])
        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        if self._editable[index.column()]:
            if value != "":
                i = index.row()
                self._data[i, index.column()] = value

                # update the total scaling power of the area, zone, etc...
                self._data[i, 2] = self.original_powers[i, 0] * self._data[i, 0]
                self._data[i, 3] = self.original_powers[i, 1] * self._data[i, 1]

        return True

    def apply_scaling(self, with_time_series: bool = False):
        """
        Aply the scaling to the objects
        :param with_time_series: scale time profiles too?
        """
        for i in range(self.r):
            gens = self.injections_per_type[i].get(DeviceType.GeneratorDevice, list())
            loads = self.injections_per_type[i].get(DeviceType.LoadDevice, list())
            load_scale = self._data[i, 0]
            gen_scale = self._data[i, 1]

            for elm in loads:
                elm.P *= load_scale
                elm.Q *= load_scale
                elm.G *= load_scale
                elm.B *= load_scale
                elm.Ii *= load_scale
                elm.Ir *= load_scale

                if with_time_series:
                    elm.P_prof *= load_scale
                    elm.Q_prof *= load_scale
                    elm.G_prof *= load_scale
                    elm.B_prof *= load_scale
                    elm.Ii_prof *= load_scale
                    elm.Ir_prof *= load_scale

            for elm in gens:
                elm.P *= gen_scale

                if with_time_series:
                    elm.P_prof *= gen_scale


class SystemScaler(QtWidgets.QDialog):
    """
    SystemScaler GUI
    """

    def __init__(self, grid: MultiCircuit, parent=None):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('System scaling')

        self.grid = grid
        self.data_model: Union[SystemScalingModel, None] = None

        self.groups = [DeviceType.AreaDevice,
                       DeviceType.ZoneDevice,
                       DeviceType.CountryDevice,
                       DeviceType.RegionDevice,
                       DeviceType.CommunityDevice,
                       DeviceType.MunicipalityDevice,
                       DeviceType.SubstationDevice]

        self.ui.group_combo_box.setModel(get_list_model([elm.value for elm in self.groups]))
        self.ui.group_combo_box.setCurrentIndex(0)
        self.group_change()

        self.ui.doit_button.clicked.connect(self.do_it)
        self.ui.group_combo_box.currentIndexChanged.connect(self.group_change)

    def group_change(self) -> None:
        """

        :return:
        """
        if self.ui.group_combo_box.currentIndex() > -1:
            txt = self.ui.group_combo_box.currentText()

            for group in self.groups:
                if txt == group.value:
                    self.data_model = SystemScalingModel(device_tpe=group,
                                                         grid=self.grid,
                                                         parent=self.ui.groups_scaling_table_view)
                    self.ui.groups_scaling_table_view.setModel(self.data_model)

    def do_it(self):
        """

        :return:
        """
        ok = yes_no_question("This operation will alter the generation "
                             "and load composition irreversibly\nAre you sure?",
                             "System scaling")

        if ok:
            if self.data_model:
                self.data_model.apply_scaling(with_time_series=self.ui.aply_to_time_series_check_box.isChecked())

            self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SystemScaler(grid=MultiCircuit())
    # window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
