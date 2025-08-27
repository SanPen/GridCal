# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Tuple
from PySide6 import QtCore, QtWidgets
import numpy as np
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Filtering.objects_filtering import FilterObjects
from VeraGrid.Gui.object_model import ObjectsModel


class ObjectModelFilterProxy(QtCore.QSortFilterProxyModel):
    """
    Proxy that delegates the parsing/evaluation of the search expression into an ObjectsModel
    to a `FilterObjects` instance.
    """

    def __init__(self,
                 mdl: ObjectsModel,
                 parent: QtCore.QObject | None = None):
        """
        Constructor
        :param mdl: ObjectsModel
        :param parent: some parent
        """
        super().__init__(parent)

        self._mdl: ObjectsModel = mdl

        # filtering engine already initialized
        self._filter_engine = FilterObjects(self._mdl.objects)

        # indexes allowed after the last call to setExpression()
        self._allowed_rows: set[int] = set(range(len(self._mdl.objects)))  # start with “show all”

        # list of filtered objects, by default it is the same as the model since we "show all"
        self._filtered_objects: List[ALL_DEV_TYPES] = self._mdl.objects

        # set the source model
        super().setSourceModel(mdl)

    @property
    def all_objects(self) -> List[ALL_DEV_TYPES]:
        return self._mdl.objects

    @property
    def objects(self) -> List[ALL_DEV_TYPES]:
        return self._filtered_objects

    @property
    def attributes(self):
        return self._mdl.attributes

    @QtCore.Slot(str)
    def setExpression(self, expr: str) -> Tuple[bool, str]:
        """
        Call this whenever the user changes the search text.
        """
        has_error = False
        error_txt = ""
        if not expr.strip():
            # empty => show everything
            self._allowed_rows = set(range(len(self.all_objects)))
        else:
            try:
                self._filter_engine.filter(expr)  # updates .filtered_indices
                self._allowed_rows = list(set(self._filter_engine.filtered_indices))
                self._allowed_rows.sort()
            except Exception as e:
                # invalid expression → fall back to “show none” (or handle as you prefer)
                error_txt = f"Filter expression error: {e}"
                self._allowed_rows = list()
                has_error = True

        self._filtered_objects = [self._mdl.objects[i] for i in self._allowed_rows]

        self.invalidateFilter()  # <- triggers filterAcceptsRow()

        return has_error, error_txt

    # ------------------------------------------------------------------  QSortFilterProxyModel
    def filterAcceptsRow(self, source_row: int,
                         source_parent: QtCore.QModelIndex) -> bool:
        """
        Called by Qt for every row that might be shown.
        """
        return source_row in self._allowed_rows

    def get_data(self):
        """

        :return:
        """

        n_rows = self.rowCount()
        n_cols = self.columnCount()
        data = np.empty((n_rows, n_cols), dtype=object)

        for j in range(n_cols):
            for i in self._allowed_rows:
                data[i, j] = self._mdl.data_raw(r=i, c=j)

        columns = [self._mdl.headerData(section=i, orientation=QtCore.Qt.Orientation.Horizontal,
                                        role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(n_cols)]

        index = [self._mdl.headerData(section=i, orientation=QtCore.Qt.Orientation.Vertical,
                                      role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(n_rows)]

        return index, columns, data

    def copy_to_column(self, index: QtCore.QModelIndex):
        """
        Copy the value pointed by the index to all the other cells in the column
        :param index: QModelIndex instance
        """
        value = self._mdl.data_with_type(index=index)
        col = index.column()

        for row in self._allowed_rows:

            if self._mdl.transposed:
                obj_idx = col
                attr_idx = row
            else:
                obj_idx = row
                attr_idx = col

            if self._mdl.attributes[attr_idx] not in self._mdl.non_editable_attributes:
                setattr(self._mdl.objects[obj_idx], self._mdl.attributes[attr_idx], value)
            else:
                pass  # the column cannot be edited

    def copy_to_clipboard(self):
        """
        Copy proxy view to clipboard
        :return:
        """
        if self.columnCount() > 0:

            index, columns, data = self.get_data()

            data = data.astype(str)

            # header first
            txt = '\t' + '\t'.join(columns) + '\n'

            # data
            for t, index_value in enumerate(index):
                txt += str(index_value) + '\t' + '\t'.join(data[t, :]) + '\n'

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText(txt)

    def set_time_index(self, time_index: int | None):
        """
        Set the time index of the table
        :param time_index: None or integer value
        """
        self._mdl.time_index_ = time_index
        role = 0
        index = QtCore.QModelIndex()
        self.dataChanged.emit(index, index, [role])
