from typing import List, Any, Union
from enum import Enum
import re
from GridCalEngine.Simulations.results_table import ResultsTable


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


# PRIMARY_TYPES = Union[type(float), type(bool), type(int), type(str)]

class Filter:

    def __init__(self, element: FilterSubject, op: CompOps, value: Union[PRIMARY_TYPES, List[PRIMARY_TYPES]]):
        self.element = element
        self.op = op
        self.value = value

    def __str__(self):

        return f"{self.element} {self.op} {self.value}"

    def __repr__(self):

        return str(self)


class MasterFilter:

    def __init__(self):
        self.stack: List[Union[Filter, FilterOps]] = []

    def add(self, elm: Union[Filter, FilterOps]) -> None:
        self.stack.append(elm)


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
        pass


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
