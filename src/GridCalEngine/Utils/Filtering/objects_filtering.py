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
import numpy as np
from typing import List, Any, Union, Tuple
from GridCalEngine.basic_structures import BoolVec, Mat
from GridCalEngine.Utils.Filtering.filtering import (MasterFilter, Filter, FilterOps, CompOps, FilterSubject,
                                                     is_odd, is_numeric, parse_expression)
from GridCalEngine.Core.Devices.types import ALL_DEV_TYPES


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
            return ""
    return p


def compute_objects_masks(objects: List[ALL_DEV_TYPES], flt: Filter) -> Tuple[BoolVec, BoolVec, Mat]:
    """

    :param objects:
    :param flt:
    :return:
    """

    if "[" in flt.value:
        val = flt.value.replace("[", "").replace("]", "").strip()
        lst = [a.strip() for a in val.split(",")]
    else:
        lst = [flt.value]

    is_neg = flt.is_negative()
    n = len(objects)
    if is_neg:
        final_idx_mask = np.ones(n, dtype=bool)
    else:
        final_idx_mask = np.zeros(n, dtype=bool)

    for value in lst:
        if flt.element in [FilterSubject.IDX_OBJECT, FilterSubject.COL_OBJECT]:

            val = value
            idx_mask = np.zeros(n, dtype=bool)

            for i in range(n):

                obj_val = object_extract(elm=objects[i], args=flt.element_args)

                if flt.op == CompOps.GT:
                    ok = obj_val > val

                elif flt.op == CompOps.LT:
                    ok = obj_val < val

                elif flt.op == CompOps.GEQ:
                    ok = obj_val >= val

                elif flt.op == CompOps.LEQ:
                    ok = obj_val <= val

                elif flt.op == CompOps.NOT_EQ:
                    ok = obj_val != val

                elif flt.op == CompOps.EQ:
                    ok = obj_val == val

                elif flt.op == CompOps.LIKE:
                    ok = val in str(obj_val)

                elif flt.op == CompOps.NOT_LIKE:
                    ok = val not in str(obj_val)

                elif flt.op == CompOps.STARTS:
                    ok = str(obj_val).startswith(val)

                elif flt.op == CompOps.ENDS:
                    ok = str(obj_val).endswith(val)

                else:
                    ok = False

                if ok:
                    idx_mask[i] = True

        else:
            raise Exception("Invalid FilterSubject")

        if is_neg:
            final_idx_mask *= idx_mask
        else:
            final_idx_mask += idx_mask

    return final_idx_mask


class FilterObjects:
    """
    FilterResultsTable class
    """

    def __init__(self, objects: List[ALL_DEV_TYPES]):
        """

        :param objects:
        """
        self.objects = objects

        self.master_filter = MasterFilter()

    def parse(self, expression: str):
        """
        Parses the query expression
        :param expression:
        :return:
        """
        self.master_filter = parse_expression(expression=expression)

    def apply(self) -> List[ALL_DEV_TYPES]:
        """

        :return:
        """
        if len(self.master_filter.stack):
            idx_mask = compute_objects_masks(objects=self.objects, flt=self.master_filter.stack[0])

            if self.master_filter.correct_size():

                for st_idx in range(1, self.master_filter.size(), 2):

                    oper: FilterOps = self.master_filter.stack[st_idx]
                    flt = self.master_filter.stack[st_idx + 1]

                    idx_mask2 = compute_objects_masks(objects=self.objects, flt=flt)

                    if oper == FilterOps.OR:
                        idx_mask += idx_mask2

                    elif oper == FilterOps.AND:
                        idx_mask *= idx_mask2

                    else:
                        raise Exception("Unsupported master filter opration")

            else:
                raise Exception("Unsupported number of filters. Use and or concatenation")

            # get the indices
            ii = np.where(idx_mask)[0]

            # return the sliced list
            return [self.objects[i] for i in ii]

        else:
            return self.objects
