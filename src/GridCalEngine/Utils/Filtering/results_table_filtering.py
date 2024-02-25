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
from typing import Tuple
import numpy as np
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.basic_structures import BoolVec, Mat
from GridCalEngine.Utils.Filtering.filtering import (MasterFilter, Filter, FilterOps, CompOps, FilterSubject,
                                                     is_numeric, parse_expression)


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

            if is_numeric(table.data_c):
                val = float(value)
            else:
                val = value

            data_mask = np.zeros((table.r, table.c), dtype=bool)
            idx_mask = np.zeros(table.r, dtype=bool)
            col_mask = np.zeros(table.c, dtype=bool)

            for i in range(table.r):
                for j in range(table.c):

                    if flt.op == CompOps.GT:
                        ok = table.data_c[i, j] > val

                    elif flt.op == CompOps.LT:
                        ok = table.data_c[i, j] < val

                    elif flt.op == CompOps.GEQ:
                        ok = table.data_c[i, j] >= val

                    elif flt.op == CompOps.LEQ:
                        ok = table.data_c[i, j] <= val

                    elif flt.op == CompOps.NOT_EQ:
                        ok = table.data_c[i, j] != val

                    elif flt.op == CompOps.EQ:
                        ok = table.data_c[i, j] == val

                    elif flt.op == CompOps.LIKE:
                        ok = val in str(table.data_c[i, j])

                    elif flt.op == CompOps.NOT_LIKE:
                        ok = val not in str(table.data_c[i, j])

                    elif flt.op == CompOps.STARTS:
                        ok = str(table.data_c[i, j]).startswith(val)

                    elif flt.op == CompOps.ENDS:
                        ok = str(table.data_c[i, j]).endswith(val)

                    else:
                        ok = False

                    if ok:
                        idx_mask[i] = True
                        col_mask[j] = True
                        data_mask[i, j] = True

        elif flt.element == FilterSubject.IDX:

            val = value
            idx_mask = np.zeros(table.r, dtype=bool)
            col_mask = np.ones(table.c, dtype=bool)
            data_mask = np.zeros((table.r, table.c), dtype=bool)

            for i in range(table.r):

                if flt.op == CompOps.GT:
                    ok = table.index_c[i] > val

                elif flt.op == CompOps.LT:
                    ok = table.index_c[i] < val

                elif flt.op == CompOps.GEQ:
                    ok = table.index_c[i] >= val

                elif flt.op == CompOps.LEQ:
                    ok = table.index_c[i] <= val

                elif flt.op == CompOps.NOT_EQ:
                    ok = table.index_c[i] != val

                elif flt.op == CompOps.EQ:
                    ok = table.index_c[i] == val

                elif flt.op == CompOps.LIKE:
                    ok = val in str(table.index_c[i])

                elif flt.op == CompOps.NOT_LIKE:
                    ok = val not in str(table.index_c[i])

                elif flt.op == CompOps.STARTS:
                    ok = str(table.index_c[i]).startswith(val)

                elif flt.op == CompOps.ENDS:
                    ok = str(table.index_c[i]).endswith(val)

                else:
                    ok = False

                if ok:
                    idx_mask[i] = True
                    data_mask[i, :] = True

        elif flt.element == FilterSubject.COL:

            val = value
            idx_mask = np.ones(table.r, dtype=bool)
            col_mask = np.zeros(table.c, dtype=bool)
            data_mask = np.zeros((table.r, table.c), dtype=bool)

            for j in range(table.c):

                if flt.op == CompOps.GT:
                    ok = table.cols_c[j] > val

                elif flt.op == CompOps.LT:
                    ok = table.cols_c[j] < val

                elif flt.op == CompOps.GEQ:
                    ok = table.cols_c[j] >= val

                elif flt.op == CompOps.LEQ:
                    ok = table.cols_c[j] <= val

                elif flt.op == CompOps.NOT_EQ:
                    ok = table.cols_c[j] != val

                elif flt.op == CompOps.EQ:
                    ok = table.cols_c[j] == val

                elif flt.op == CompOps.LIKE:
                    ok = val in str(table.cols_c[j])

                elif flt.op == CompOps.NOT_LIKE:
                    ok = val not in str(table.cols_c[j])

                elif flt.op == CompOps.STARTS:
                    ok = str(table.cols_c[j]).startswith(val)

                elif flt.op == CompOps.ENDS:
                    ok = str(table.cols_c[j]).endswith(val)

                else:
                    ok = False

                if ok:
                    col_mask[j] = True
                    data_mask[:, j] = True

        elif flt.element == FilterSubject.COL_OBJECT:
            idx_mask = np.ones(table.r, dtype=bool)
            col_mask = np.zeros(table.c, dtype=bool)
            data_mask = np.zeros((table.r, table.c), dtype=bool)

        elif flt.element == FilterSubject.IDX_OBJECT:
            idx_mask = np.zeros(table.r, dtype=bool)
            col_mask = np.ones(table.c, dtype=bool)
            data_mask = np.zeros((table.r, table.c), dtype=bool)

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

            data = self.table.data_c * nan_mask

            # return the sliced table
            return ResultsTable(data=data[np.ix_(ii, jj)],
                                columns=np.array([self.table.cols_c[j] for j in jj]),
                                index=np.array([self.table.index_c[i] for i in ii]))

        else:
            return self.table
