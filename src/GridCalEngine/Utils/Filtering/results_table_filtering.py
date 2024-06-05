# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from typing import Tuple, Any, List
import numpy as np
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.basic_structures import BoolVec, Mat
from GridCalEngine.Utils.Filtering.filtering import (MasterFilter, Filter, FilterOps, FilterSubject,
                                                     is_numeric, parse_expression)
from GridCalEngine.Devices.types import ALL_DEV_TYPES


def object_extract(elm: ALL_DEV_TYPES, args: List[str]) -> Any:
    """
    Extract value from object's property chain
    :param elm: Device
    :param args: list of properties (i.e. bus.area.name as ['bus', 'area', 'name'])
    :return: value
    """
    p = elm
    for arg in args:
        if hasattr(p, arg):
            p = getattr(p, arg)
        else:
            return None
    return p

def try_numeric(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def compute_results_table_masks(table: ResultsTable, flt: Filter) -> Tuple[BoolVec, BoolVec, Mat]:
    """

    :param table:
    :param flt:
    :return:
    """

    lst = flt.get_list_of_values()
    is_neg = flt.is_negative()

    if is_neg:
        final_idx_mask = np.ones(table.r, dtype=bool)
        final_col_mask = np.ones(table.c, dtype=bool)
        final_data_mask = np.ones((table.r, table.c), dtype=bool)
    else:
        final_idx_mask = np.zeros(table.r, dtype=bool)
        final_col_mask = np.zeros(table.c, dtype=bool)
        final_data_mask = np.zeros((table.r, table.c), dtype=bool)

    for value in lst:
        if flt.element == FilterSubject.VAL:
            if try_numeric(value) and is_numeric(table.data_c):
                val = float(value)
            else:
                val = value

            data_mask = np.zeros((table.r, table.c), dtype=bool)
            idx_mask = np.zeros(table.r, dtype=bool)
            col_mask = np.zeros(table.c, dtype=bool)

            for i in range(table.r):
                for j in range(table.c):
                    if flt.apply_filter_op(table.data_c[i, j], val):
                        idx_mask[i] = True
                        col_mask[j] = True
                        data_mask[i, j] = True

        elif flt.element == FilterSubject.IDX:

            val = value
            idx_mask = np.zeros(table.r, dtype=bool)
            col_mask = np.ones(table.c, dtype=bool)
            data_mask = np.zeros((table.r, table.c), dtype=bool)

            for i in range(table.r):

                if flt.apply_filter_op(table.index_c[i], val):
                    idx_mask[i] = True
                    data_mask[i, :] = True

        elif flt.element == FilterSubject.COL:

            val = value
            idx_mask = np.ones(table.r, dtype=bool)
            col_mask = np.zeros(table.c, dtype=bool)
            data_mask = np.zeros((table.r, table.c), dtype=bool)

            for j in range(table.c):

                if flt.apply_filter_op(table.cols_c[j], val):
                    col_mask[j] = True
                    data_mask[:, j] = True

        elif flt.element == FilterSubject.COL_OBJECT:

            val = value

            idx_mask = np.ones(table.r, dtype=bool)
            col_mask = np.zeros(table.c, dtype=bool)
            data_mask = np.zeros((table.r, table.c), dtype=bool)
            if len(table.idx_devices):
                for j in range(table.c):

                    if len(flt.element_args):
                        obj_val = object_extract(elm=table.col_devices[j], args=flt.element_args)
                    else:
                        obj_val = str(table.col_devices[j])

                    if obj_val is not None:

                        tpe = type(obj_val)

                        try:
                            val = tpe(val)
                        except TypeError:
                            # if the casting failed, try string comparison
                            val = str(val)
                            obj_val = str(obj_val)

                        if flt.apply_filter_op(obj_val, val):
                            col_mask[j] = True
                            data_mask[:, j] = True
                    else:
                        # the object_val is None
                        a = ".".join(flt.element_args)
                        raise ValueError(f"{a} cannot be found for the objects :(")

        elif flt.element == FilterSubject.IDX_OBJECT:

            val = value

            idx_mask = np.zeros(table.r, dtype=bool)
            col_mask = np.ones(table.c, dtype=bool)
            data_mask = np.zeros((table.r, table.c), dtype=bool)

            if len(table.idx_devices):

                for i in range(table.r):

                    if len(flt.element_args):
                        obj_val = object_extract(elm=table.idx_devices[i], args=flt.element_args)
                    else:
                        obj_val = str(table.idx_devices[i])

                    if obj_val is not None:

                        tpe = type(obj_val)

                        try:
                            val = tpe(val)
                        except TypeError:
                            # if the casting failed, try string comparison
                            val = str(val)
                            obj_val = str(obj_val)

                        if flt.apply_filter_op(obj_val, val):
                            idx_mask[i] = True
                            data_mask[i, :] = True
                    else:
                        # the object_val is None
                        a = ".".join(flt.element_args)
                        raise ValueError(f"{a} cannot be found for the objects :(")

        else:
            raise Exception("Invalid FilterSubject")

        if is_neg:
            final_idx_mask *= idx_mask
            final_col_mask *= col_mask
            final_data_mask *= data_mask
        else:
            final_idx_mask += idx_mask
            final_col_mask += col_mask
            final_data_mask += data_mask

    return final_idx_mask, final_col_mask, final_data_mask


class FilterResultsTable:
    """
    FilterResultsTable class
    """

    def __init__(self, table: ResultsTable):
        self.table = table

        self.master_filter = MasterFilter()

    def parse(self, expression: str):
        """
        Parses the query expression
        :param expression:
        :return:
        """
        self.master_filter = parse_expression(expression=expression)

    def apply(self) -> ResultsTable:
        """

        :return:
        """
        if len(self.master_filter.stack):
            idx_mask, col_mask, data_mask = compute_results_table_masks(table=self.table,
                                                                        flt=self.master_filter.stack[0])
            if self.master_filter.correct_size():

                for st_idx in range(1, self.master_filter.size(), 2):

                    oper: FilterOps = self.master_filter.stack[st_idx]
                    flt = self.master_filter.stack[st_idx + 1]

                    idx_mask2, col_mask2, data_mask2 = compute_results_table_masks(table=self.table, flt=flt)

                    if oper == FilterOps.OR:
                        idx_mask += idx_mask2
                        col_mask += col_mask2
                        data_mask += data_mask2

                    elif oper == FilterOps.AND:
                        idx_mask *= idx_mask2
                        col_mask *= col_mask2
                        data_mask *= data_mask2

                    else:
                        raise Exception("Unsupported master filter opration")

            else:
                raise Exception("Unsupported number of filters. Use and or concatenation")

            # return the sliced table
            # get the indices
            ii = np.where(idx_mask)[0]
            jj = np.where(col_mask)[0]

            nan_mask = np.zeros_like(self.table.data_c)
            for i in range(self.table.r):
                for j in range(self.table.c):
                    nan_mask[i, j] = True if data_mask[i, j] else np.nan

            data = np.empty_like(self.table.data_c)
            for i in range(self.table.r):
                for j in range(self.table.c):
                    if(nan_mask[i, j] == np.nan):
                        data[i, j] = np.nan
                    else:
                        data[i, j] = self.table.data_c[i, j]

            # return the sliced table

            return ResultsTable(data=data[np.ix_(ii, jj)],
                                columns=np.array([self.table.cols_c[j] for j in jj]),
                                index=np.array([self.table.index_c[i] for i in ii]),
                                title=self.table.title,
                                xlabel=self.table.x_label,
                                ylabel=self.table.y_label,
                                units=self.table.units,
                                editable=self.table.editable,
                                editable_min_idx=self.table.editable_min_idx,
                                decimals=self.table.decimals,
                                cols_device_type=self.table.cols_device_type,
                                idx_device_type=self.table.idx_device_type)

        else:
            return self.table
