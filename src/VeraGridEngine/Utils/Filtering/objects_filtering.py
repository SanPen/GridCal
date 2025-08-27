# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from typing import List, Any, Tuple
from VeraGridEngine.basic_structures import BoolVec, Mat, IntVec
from VeraGridEngine.Utils.Filtering.filtering import (MasterFilter, Filter, FilterOps, FilterSubject,
                                                      parse_expression)
from VeraGridEngine.Devices.types import ALL_DEV_TYPES


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
    :param objects: List of VeraGrid objects
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
        self._objects = objects

        self._filtered_indices = np.arange(len(self._objects))

    @property
    def filtered_indices(self):
        return self._filtered_indices

    @property
    def filtered_objects(self):
        return [self._objects[i] for i in self._filtered_indices]

    def filter(self, expression: str)-> None:
        """
        Parses the query expression
        :param expression:
        :return:
        """
        master_filter: MasterFilter = parse_expression(expression=expression)

        if len(master_filter.stack) > 0:

            if master_filter.is_correct_size():

                idx_mask = compute_objects_masks(objects=self._objects, flt=master_filter.stack[0])

                for st_idx in range(1, master_filter.size(), 2):

                    oper: FilterOps = master_filter.stack[st_idx]
                    flt = master_filter.stack[st_idx + 1]

                    idx_mask2 = compute_objects_masks(objects=self._objects, flt=flt)

                    if oper == FilterOps.OR:
                        idx_mask += idx_mask2

                    elif oper == FilterOps.AND:
                        idx_mask *= idx_mask2

                    else:
                        raise TypeError("Unsupported master filter operation")

                # get the indices
                self._filtered_indices = np.where(idx_mask)[0]

            else:
                raise ValueError("Unsupported number of filters. Use and or concatenation")

        else:

            # try searching by name
            to_search = expression.strip().lower()
            if to_search != "":
                ls = list()
                for i, obj in enumerate(self._objects):
                    if expression in obj.name.lower():
                        ls.append(i)

                self._filtered_indices = np.array(ls, dtype=int)
            else:
                self._filtered_indices = np.zeros(0, dtype=int)

