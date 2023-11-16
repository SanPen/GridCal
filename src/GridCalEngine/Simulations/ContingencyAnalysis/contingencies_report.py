# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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

from typing import List, Union, Any
from GridCalEngine.basic_structures import IntVec, StrMat, StrVec, Vec
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Core.Devices import ContingencyGroup

import numpy as np


class ContingencyTableEntry:
    """
    Entry of a contingency report
    """

    __hdr__ = ["time index",
               "base name",
               "base uuid",
               "base flow",
               "base rating",
               "base loading",
               "contingency idx",
               "contingency name",
               "contingency uuid",
               "post_contingency flow",
               "contingency rating",
               "post_contingency loading"]

    def __init__(self,
                 time_index: int,
                 base_name: str,
                 base_uuid: str,
                 base_flow: complex,
                 base_rating: float,
                 base_loading: float,
                 contingency_idx: int,
                 contingency_name: str,
                 contingency_uuid: str,
                 post_contingency_flow: complex,
                 contingency_rating: float,
                 post_contingency_loading: float):
        """
        ContingencyTableEntry constructor
        :param time_index:
        :param base_name:
        :param base_uuid:
        :param base_flow:
        :param base_rating:
        :param base_loading:
        :param contingency_idx:
        :param contingency_name:
        :param contingency_uuid:
        :param post_contingency_flow:
        :param contingency_rating:
        :param post_contingency_loading:
        """
        self.time_index: int = time_index

        self.base_name: str = base_name
        self.base_uuid: str = base_uuid

        self.base_flow = base_flow
        self.base_rating = base_rating
        self.base_loading = base_loading

        self.contingency_idx: int = contingency_idx
        self.contingency_name: str = contingency_name
        self.contingency_uuid: str = contingency_uuid
        self.post_contingency_flow: complex = post_contingency_flow
        self.contingency_rating: float = contingency_rating
        self.post_contingency_loading: float = post_contingency_loading

    def get_headers(self) -> List[str]:
        """
        Get the headers
        :return: list of header names
        """
        return self.__hdr__

    def to_list(self) -> List[Any]:
        """
        Get a list representation of this entry
        :return: List[Any]
        """
        return [self.time_index,
                self.base_name,
                self.base_uuid,
                self.base_flow,
                self.base_rating,
                self.base_loading,
                self.contingency_idx,
                self.contingency_name,
                self.contingency_uuid,
                self.post_contingency_flow,
                self.contingency_rating,
                self.post_contingency_loading]

    def to_string_list(self) -> List[str]:
        """
        Get list of string values
        :return: List[str]
        """
        return [str(a) for a in self.to_list()]

    def to_array(self) -> StrVec:
        """
        Get array of string values
        :return: StrVec
        """
        return np.array(self.to_string_list())


class ContingencyResultsReport:
    """
    Contingency results report table
    """

    def __init__(self):
        self.entries: List[ContingencyTableEntry] = list()

    def add_entry(self, entry: ContingencyTableEntry):
        """
        Add contingencies entry
        :param entry: ContingencyTableEntry
        """
        self.entries.append(entry)

    def add(self,
            time_index: int,
            base_name: str,
            base_uuid: str,
            base_flow: complex,
            base_rating: float,
            base_loading: float,
            contingency_idx: int,
            contingency_name: str,
            contingency_uuid: str,
            post_contingency_flow: complex,
            contingency_rating: float,
            post_contingency_loading: float):
        """
        Add report data
        :param time_index:
        :param base_name:
        :param base_uuid:
        :param base_flow:
        :param base_rating:
        :param base_loading:
        :param contingency_idx:
        :param contingency_name:
        :param contingency_uuid:
        :param post_contingency_flow:
        :param contingency_rating:
        :param post_contingency_loading:
        """
        self.add_entry(ContingencyTableEntry(time_index=time_index,
                                             base_name=base_name,
                                             base_uuid=base_uuid,
                                             base_flow=base_flow,
                                             base_rating=base_rating,
                                             base_loading=base_loading,
                                             contingency_idx=contingency_idx,
                                             contingency_name=contingency_name,
                                             contingency_uuid=contingency_uuid,
                                             post_contingency_flow=post_contingency_flow,
                                             contingency_rating=contingency_rating,
                                             post_contingency_loading=post_contingency_loading))

    def merge(self, other: "ContingencyResultsReport"):
        """
        Add another ContingencyResultsReport in-place
        :param other: ContingencyResultsReport instance
        """
        self.entries += other.entries

    def size(self) -> int:
        """
        Get the size
        :return: number of entries
        """
        return len(self.entries)

    def n_cols(self) -> int:
        """
        Number of columns
        :return: int
        """
        return len(self.get_headers())

    @staticmethod
    def get_headers() -> list[str]:
        """
        Get the headers
        :return: List[str]
        """
        return ContingencyTableEntry.__hdr__

    def get_index(self) -> IntVec:
        """
        Get the index
        :return: IntVec
        """
        return np.arange(0, self.size())

    def get_data(self) -> StrMat:
        """
        Get data as list of lists of strings
        :return: List[List[str]]
        """
        data = np.empty((self.size(), self.n_cols()), dtype=object)
        for i, e in enumerate(self.entries):
            data[i, :] = e.to_array()
        return data

    def analyze(self, t: Union[None, int],
                mon_idx: IntVec,
                calc_branches: List[Any],
                numerical_circuit: NumericalCircuit,
                flows: Vec,
                loading: Vec,
                contingency_flows: Vec,
                contingency_loadings: Vec,
                contingency_idx: int,
                contingency_group: ContingencyGroup):
        """
        Analize contingency resuts and add them to the report
        :param t: time index
        :param mon_idx: array of monitored branch indices
        :param calc_branches: array of calculation branches
        :param numerical_circuit: NumericalCircuit
        :param flows: base flows array
        :param loading: base loading array
        :param contingency_flows: flows array after the contingency
        :param contingency_loadings: loading array after the contingency
        :param contingency_idx: contingency group index
        :param contingency_group: ContingencyGroup
        """
        for m in mon_idx:  # for each monitored branch ...

            c_flow = abs(contingency_flows[m])
            b_flow = abs(flows[m])

            if c_flow > numerical_circuit.contingency_rates[m]:  # if the contingency flow is greater than the rate ...

                self.add(time_index=t if t is not None else 0,
                         base_name=numerical_circuit.branch_data.names[m],
                         base_uuid=calc_branches[m].idtag,
                         base_flow=b_flow,
                         base_rating=numerical_circuit.branch_data.rates[m],
                         base_loading=abs(loading[m] * 100.0),
                         contingency_idx=contingency_idx,
                         contingency_name=contingency_group.name,
                         contingency_uuid=contingency_group.idtag,
                         post_contingency_flow=c_flow,
                         contingency_rating=numerical_circuit.branch_data.contingency_rates[m],
                         post_contingency_loading=abs(contingency_loadings[m]) * 100.0)
