from typing import List, Any, Union, Tuple
from enum import Enum
import re
import numpy as np
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.basic_structures import BoolVec, Mat


def is_odd(number: int):
    """
    Check if number is odd
    :param number:
    :return:
    """
    return number % 2 != 0


class CompOps(Enum):
    """
    Enumeration of filter oprations
    """
    GT = ">"
    LT = "<"
    GEQ = ">="
    LEQ = "<="
    DIFF = "!="
    EQ = "="
    IN = "in"
    NOT_IN = "not in"
    STARTS = "starts"
    ENDS = "ends"

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return CompOps[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
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
        try:
            return FilterOps[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
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
        try:
            return FilterSubject[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


PRIMARY_TYPES = Union[float, bool, int, str]


class Filter:
    """
    Filter
    """

    def __init__(self, element: FilterSubject, op: CompOps, value: Union[PRIMARY_TYPES, List[PRIMARY_TYPES]]):
        """

        :param element:
        :param op:
        :param value:
        """
        self.element = element
        self.op = op
        self.value = value

    def __str__(self):
        return f"{self.element} {self.op} {self.value}"

    def __repr__(self):
        return str(self)


class MasterFilter:
    """
    MasterFilter
    """

    def __init__(self):
        """

        """
        self.stack: List[Union[Filter, FilterOps]] = []

    def add(self, elm: Union[Filter, FilterOps]) -> None:
        """

        :param elm:
        :return:
        """
        self.stack.append(elm)

    def size(self):
        """

        :return:
        """
        return len(self.stack)


def parse_single(token: str) -> Union[Filter, None]:
    """

    :param token:
    :return:
    """
    elms = re.split(r'([<>=!]=?|[<>]|in|starts|ends)', token)

    if len(elms) == 3:
        return Filter(element=FilterSubject(elms[0].strip()),
                      op=CompOps(elms[1].strip()),
                      value=elms[2].strip())
    else:
        # wrong filter
        return None


def parse_expression(expression: str) -> MasterFilter:
    """
    Parses the query expression
    :param expression:
    :return: MasterFilter
    """
    mst_flt = MasterFilter()
    master_tokens = re.split(r'(and|or)', expression)

    for token in master_tokens:

        if "and" not in token and "or" not in token:

            flt = parse_single(token=token)

            if flt is not None:
                mst_flt.add(elm=flt)

        else:
            elm = FilterOps(token.strip())
            mst_flt.add(elm=elm)

    return mst_flt


def is_numeric(obj):
    attrs = ['__add__', '__sub__', '__mul__', '__truediv__', '__pow__']
    return all(hasattr(obj, attr) for attr in attrs)


def compute_results_table_masks(table: ResultsTable, flt: Filter) -> Tuple[BoolVec, BoolVec, Mat]:
    """

    :param table:
    :param flt:
    :return:
    """

    if flt.op == CompOps.IN or flt.op == CompOps.NOT_IN:
        val = flt.value.replace("[", "").replace("]", "").strip()
        lst = [a.strip() for a in val.split(",")]
    else:
        lst = list()

    if flt.element == FilterSubject.VAL:

        if is_numeric(table.data_c):
            val = float(flt.value)
        else:
            val = flt.value

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

                elif flt.op == CompOps.DIFF:
                    ok = table.data_c[i, j] != val

                elif flt.op == CompOps.EQ:
                    ok = table.data_c[i, j] == val

                elif flt.op == CompOps.IN:
                    ok = table.data_c[i, j] in lst

                elif flt.op == CompOps.NOT_IN:
                    ok = table.data_c[i, j] not in lst

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

        val = flt.value
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

            elif flt.op == CompOps.DIFF:
                ok = table.index_c[i] != val

            elif flt.op == CompOps.EQ:
                ok = table.index_c[i] == val

            elif flt.op == CompOps.IN:
                ok = table.index_c[i] in lst

            elif flt.op == CompOps.NOT_IN:
                ok = table.index_c[i] not in lst

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

        val = flt.value
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

            elif flt.op == CompOps.DIFF:
                ok = table.cols_c[j] != val

            elif flt.op == CompOps.EQ:
                ok = table.cols_c[j] == val

            elif flt.op == CompOps.IN:
                ok = table.cols_c[j] in lst

            elif flt.op == CompOps.NOT_IN:
                ok = table.cols_c[j] not in lst

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

    return idx_mask, col_mask, data_mask


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

            if is_odd(self.master_filter.size()):

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
                                columns=[self.table.cols_c[j] for j in jj],
                                index=[self.table.index_c[i] for i in ii])

        else:
            return self.table


"""
val > 4
OR
val < 5
AND 
idx != "bus"

->
val > 4
val < 5
idx != "bus"



"""
