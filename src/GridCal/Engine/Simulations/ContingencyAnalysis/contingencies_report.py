# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

from typing import List, Dict, Union, Tuple, Any


class ContingencyTableEntry:
    """
    Entry of a contingency report
    """

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
        :return:
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
