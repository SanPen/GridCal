# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import List, Union
from enum import Enum
import re
import numpy as np


def is_odd(number: int):
    """
    Check if number is odd
    :param number:
    :return:
    """
    return number % 2 != 0


def is_numeric(obj: np.ndarray) -> bool:
    """
    Checks if the numpy array is numeric
    :param obj:
    :return:
    """
    attrs = ['__add__', '__sub__', '__mul__', '__truediv__', '__pow__']
    return all(hasattr(obj, attr) for attr in attrs)


class CompOps(Enum):
    """
    Enumeration of filter oprations
    """
    GT = ">"
    LT = "<"
    GEQ = ">="
    LEQ = "<="
    NOT_EQ = "!="
    EQ = "="
    LIKE = "like"
    NOT_LIKE = "notlike"
    STARTS = "starts"
    ENDS = "ends"

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return CompOps[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class FilterOps(Enum):
    """
    Enumeration of filter oprations
    """
    AND = "and"
    OR = "or"

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return FilterOps[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class FilterSubject(Enum):
    """
    Enumeration of filter oprations
    """
    COL = "col"
    IDX = "idx"
    VAL = "val"
    COL_OBJECT = "colobj"
    IDX_OBJECT = "idxobj"

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return FilterSubject[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


PRIMARY_TYPES = Union[float, bool, int, str]


class Filter:
    """
    Filter
    """

    def __init__(self,
                 element: FilterSubject,
                 element_args: List[str],
                 op: CompOps,
                 value: Union[PRIMARY_TYPES, List[PRIMARY_TYPES]]):
        """
        Filter constructor
        :param element: FilterSubject
        :param element_args: further search elements
        :param op: CompOps
        :param value: Comparison value
        """
        self.element = element
        self.element_args: List[str] = element_args
        self.op = op
        self.value = value

    def __str__(self):
        return f"{self.element} {self.op} {self.value}"

    def __repr__(self):
        return str(self)

    def is_negative(self) -> bool:
        """
        Is the filter operation negative?
        :return: is negative?
        """
        if self.op == CompOps.GT:
            return False

        elif self.op == CompOps.LT:
            return False

        elif self.op == CompOps.GEQ:
            return False

        elif self.op == CompOps.LEQ:
            return False

        elif self.op == CompOps.NOT_EQ:
            return True

        elif self.op == CompOps.EQ:
            return False

        elif self.op == CompOps.LIKE:
            return False

        elif self.op == CompOps.NOT_LIKE:
            return True

        elif self.op == CompOps.STARTS:
            return False

        elif self.op == CompOps.ENDS:
            return False

        else:
            raise Exception(f"Unknown op: {self.op}")

    def get_list_of_values(self) -> List[str]:
        """
        Get a list of values to compare to
        :return: list of strings
        """
        if "[" in self.value:
            val = self.value.replace("[", "").replace("]", "").strip()
            lst = [a.strip() for a in val.split(",")]
        else:
            lst = [self.value]

        return lst

    @staticmethod
    def try_numeric(value):
        """
        Try to convert a value to a numeric type
        :param value:
        :return: float
        """
        try:
            float(value)
            return True
        except ValueError:
            return False
        except TypeError:
            return False

    def apply_filter_op(self, obj_val: Union[float, str], val: Union[float, str]) -> bool:
        """
        Apply the filter operation
        :param obj_val: value of the object
        :param val: value to compare
        :return: passes the filter?
        """
        if self.op == CompOps.GT:
            if self.try_numeric(obj_val) and self.try_numeric(val):
                obj_val = float(obj_val)
                val = float(val)
                ok = obj_val > val
            else:
                ok = False

        elif self.op == CompOps.LT:
            if self.try_numeric(obj_val) and self.try_numeric(val):
                obj_val = float(obj_val)
                val = float(val)
                ok = obj_val < val
            else:
                ok = False

        elif self.op == CompOps.GEQ:
            if self.try_numeric(obj_val) and self.try_numeric(val):
                obj_val = float(obj_val)
                val = float(val)
                ok = obj_val >= val
            else:
                ok = False

        elif self.op == CompOps.LEQ:
            if self.try_numeric(obj_val) and self.try_numeric(val):
                obj_val = float(obj_val)
                val = float(val)
                ok = obj_val <= val
            else:
                ok = False

        elif self.op == CompOps.NOT_EQ:
            obj_val = str(obj_val).lower()
            val = str(val).lower()
            ok = obj_val != val

        elif self.op == CompOps.EQ:
            if self.try_numeric(obj_val) and self.try_numeric(val):
                obj_val = float(obj_val)
                val = float(val)
                ok = obj_val == val
            else:
                obj_val = str(obj_val).lower()
                val = str(val).lower()
                ok = obj_val == val

        elif self.op == CompOps.LIKE:
            obj_val = str(obj_val).lower()
            val = str(val).lower()
            ok = str(val) in str(obj_val)

        elif self.op == CompOps.NOT_LIKE:
            obj_val = str(obj_val).lower()
            val = str(val).lower()
            ok = val not in str(obj_val)

        elif self.op == CompOps.STARTS:
            obj_val = str(obj_val).lower()
            val = str(val).lower()
            ok = str(obj_val).startswith(val)

        elif self.op == CompOps.ENDS:
            obj_val = str(obj_val).lower()
            val = str(val).lower()
            ok = str(obj_val).endswith(val)

        else:
            ok = False

        return ok


class MasterFilter:
    """
    MasterFilter
    """

    def __init__(self) -> None:
        """

        """
        self.stack: List[Union[Filter, FilterOps]] = list()

    def add(self, elm: Union[Filter, FilterOps]) -> None:
        """
        Add filter or filter operation to the stack
        :param elm: filter or filter operation
        """
        self.stack.append(elm)

    def size(self) -> int:
        """
        Get size of the stack
        :return: int
        """
        return len(self.stack)

    def correct_size(self) -> bool:
        """
        Returs if the stack has the right size: an odd number
        :return:
        """
        return is_odd(self.size())


def parse_single(token: str) -> Union[Filter, None]:
    """
    Parse single token, these are tokens that are composed on 3 parts: element, operation, comparison value
    :param token: Token
    :return: Filter or None if the token is not valid
    """
    elms = re.split(r'(?<=\s)([<>=!]=?|in|starts|ends|like|notlike)(?=\s)', token)

    if len(elms) == 3:

        if "." in elms[0]:
            coms = elms[0].strip().split(".")
            element = coms[0]
            coms.pop(0)
            element_args = coms
        else:
            element = elms[0].strip()
            element_args = list()

        return Filter(element=FilterSubject(element),
                      element_args=element_args,
                      op=CompOps(elms[1].strip()),
                      value=elms[2].strip())
    else:
        # wrong filter
        return None


def has_operators(token: str) -> bool:
    """
    Check if there are operators and , or in the token
    :param token: any token
    :return: has operators?
    """
    words = token.split()
    return "and" in words or "or" in words


def parse_expression(expression: str) -> MasterFilter:
    """
    Parses the query expression
    :param expression:
    :return: MasterFilter
    """
    mst_flt = MasterFilter()
    master_tokens = re.split(r'(?<=\s)(and|or)(?=\s)', expression)

    for token in master_tokens:

        if has_operators(token):

            elm = FilterOps(token.strip())
            mst_flt.add(elm=elm)

        else:

            flt = parse_single(token=token)

            if flt is not None:
                mst_flt.add(elm=flt)

    return mst_flt
