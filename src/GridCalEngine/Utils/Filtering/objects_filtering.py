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
from typing import List, Any, Tuple
from GridCalEngine.basic_structures import BoolVec, Mat
from GridCalEngine.Utils.Filtering.filtering import (MasterFilter, Filter, FilterOps, CompOps, FilterSubject,
                                                     parse_expression)
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


def compute_objects_masks(objects: List[ALL_DEV_TYPES], flt: Filter) -> Tuple[BoolVec, BoolVec, Mat]:
    """
    Give a list of objects, apply the single filter and return the filtering mask
    :param objects: List of GridCal objects
    :param flt: Filter
    :return: boolean array of the same length of objects
    """

    lst = flt.get_list_of_values()
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

                if len(flt.element_args):
                    obj_val = object_extract(elm=objects[i], args=flt.element_args)
                else:
                    obj_val = str(objects[i])

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
                else:
                    # the object_val is None
                    a = ".".join(flt.element_args)
                    raise ValueError(f"{a} cannot be found for the objects :(")

        else:
            raise ValueError("Invalid FilterSubject")

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
