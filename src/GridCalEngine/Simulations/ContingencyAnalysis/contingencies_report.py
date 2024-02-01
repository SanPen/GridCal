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
import numba as nb
from scipy.sparse import csc_matrix
from typing import List, Union, Any
from GridCalEngine.basic_structures import IntVec, StrMat, StrVec, Vec, Mat
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Core.Devices import ContingencyGroup
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearMultiContingency
from GridCalEngine.Simulations.ContingencyAnalysis.Methods.srap import BusesForSrap
from GridCalEngine.Utils.Sparse.csc_numba import get_sparse_array_numba


@nb.njit(cache=True)
def get_ptdf_comp_numba(data, indices, indptr, PTDF, m, bd_indices):
    """
    This computes the compensatd PTDF for a single branch
    PTDFc = MLODF[m, βδ] x PTDF[βδ, :] + PTDF[m, :]
    :param data: MLODF[:, βδ].data
    :param indices: MLODF[:, βδ].indices
    :param indptr: MLODF[:, βδ].indptr
    :param PTDF: Full PTDF matrix
    :param m: intex of the monitored branch
    :param bd_indices: indices of the failed branches
    :return:
    """
    # Perform the operation
    result = PTDF[m, :]

    for j, bd_index in enumerate(bd_indices):
        for i in range(indptr[j], indptr[j + 1]):
            row_index = indices[i]
            if row_index == m:
                result += data[i] * PTDF[bd_index, :]

    return result


def get_ptdf_comp(mon_br_idx: int, branch_indices: IntVec, mlodf_factors: csc_matrix, PTDF: Mat):
    """
    Get the compensated PTDF values for a single monitored branch
    :param mon_br_idx:
    :param branch_indices:
    :param mlodf_factors:
    :param PTDF:
    :return:
    """
    # PTDFc = MLODF[m, βδ] x PTDF[βδ, :] + PTDF[m, :]
    # PTDFc = mlodf_factors[mon_br_idx, :] @ PTDF[branch_indices, :] + PTDF[mon_br_idx, :]

    res = get_ptdf_comp_numba(data=mlodf_factors.data,
                              indices=mlodf_factors.indices,
                              indptr=mlodf_factors.indptr,
                              PTDF=PTDF,
                              m=mon_br_idx,
                              bd_indices=branch_indices)

    # ok = np.allclose(res, PTDFc[0, :], atol=1e-6)

    return res


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
               "post_contingency loading",
               "Solved with SRAP",
               "SRAP power",
               "SRAP buses"]

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
                 post_contingency_loading: float,
                 solved_by_srap: bool = False,
                 srap_power: float = 0.0,
                 srap_bus_indices: IntVec = None):
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
        :param solved_by_srap:
        :param srap_power:
        :param srap_bus_indices:
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

        self.solved_by_srap: bool = solved_by_srap
        self.srap_power = srap_power
        self.srap_bus_indices: IntVec = srap_bus_indices if srap_bus_indices is not None else np.zeros(0, dtype=int)

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
                self.post_contingency_loading,
                self.solved_by_srap,
                self.srap_power,
                ",".join(self.srap_bus_indices)]

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

    def __init__(self) -> None:
        """
        Constructor
        """
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
            post_contingency_loading: float,
            solved_by_srap: bool = False,
            srap_power: float = 0.0,
            srap_bus_indices: IntVec = None):
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
        :param solved_by_srap:
        :param srap_power:
        :param srap_bus_indices:
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
                                             post_contingency_loading=post_contingency_loading,
                                             solved_by_srap=solved_by_srap,
                                             srap_power=srap_power,
                                             srap_bus_indices=srap_bus_indices))

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

    def analyze(self,
                t: Union[None, int],
                mon_idx: IntVec,
                calc_branches: List[Any],
                numerical_circuit: NumericalCircuit,
                base_flow: Vec,
                base_loading: Vec,
                contingency_flows: Vec,
                contingency_loadings: Vec,
                contingency_idx: int,
                contingency_group: ContingencyGroup,
                using_srap: bool = False,
                srap_max_loading: float = 1.4,
                srap_max_power: float = 1400.0,
                multi_contingency: LinearMultiContingency = None,
                PTDF: Mat = None,
                available_power: Vec = None,
                srap_fixing_probability:Mat = None):
        """
        Analize contingency resuts and add them to the report
        :param t: time index
        :param mon_idx: array of monitored branch indices
        :param calc_branches: array of calculation branches
        :param numerical_circuit: NumericalCircuit
        :param base_flow: base flows array
        :param base_loading: base loading array
        :param contingency_flows: flows array after the contingency
        :param contingency_loadings: loading array after the contingency
        :param contingency_idx: contingency group index
        :param contingency_group: ContingencyGroup
        :param using_srap: Inspect contingency using the SRAP conditions
        :param srap_max_loading: Rate multiplier under which we can use SRAP conditions
        :param srap_max_power: Max amount of power to lower using SRAP conditions
        :param multi_contingency: list of buses for SRAP conditions
        :param PTDF
        :param available_power
        """
        for m in mon_idx:  # for each monitored branch ...

            c_flow = abs(contingency_flows[m])
            b_flow = abs(base_flow[m])

            # ----------------------------------------------------------------------------------------------------------
            # perform the analysis
            # ----------------------------------------------------------------------------------------------------------
            srap_condition = 1.0 < abs(contingency_loadings[m]) <= srap_max_loading
            if using_srap and srap_condition:

                # compute the sensitivities for the monitored line with all buses
                # PTDFc = MLODF[m, βδ] x PTDF[βδ, :] + PTDF[m, :]
                # PTDFc = multi_contingency.mlodf_factors[m, :] @ PTDF[multi_contingency.branch_indices, :] + PTDF[m, :]
                PTDFc = get_ptdf_comp(mon_br_idx=m,
                                      branch_indices=multi_contingency.branch_indices,
                                      mlodf_factors=multi_contingency.mlodf_factors,
                                      PTDF=PTDF)

                # information about the buses that we can use for SRAP
                sensitivities, indices = get_sparse_array_numba(PTDFc, threshold=1e-3)
                buses_for_srap = BusesForSrap(branch_idx=m,
                                              bus_indices=indices,
                                              sensitivities=sensitivities)

                solved_by_srap, max_srap_power = buses_for_srap.is_solvable(
                    c_flow=contingency_flows[m].real,  # the real part because it must have the sign
                    rating=numerical_circuit.branch_data.rates[m],
                    srap_pmax_mw=srap_max_power,
                    available_power=available_power,
                    top_n=5,
                    srap_fixing_probability=srap_fixing_probability
                )

                # solved_by_srap, max_srap_power = calc_srap(m,
                #                                            multi_contingency,
                #                                            PTDF,
                #                                            contingency_flows,
                #                                            numerical_circuit,
                #                                            srap_max_power,
                #                                            available_power)

                self.add(time_index=t if t is not None else 0,
                         base_name=numerical_circuit.branch_data.names[m],
                         base_uuid=calc_branches[m].idtag,
                         base_flow=b_flow,
                         base_rating=numerical_circuit.branch_data.rates[m],
                         base_loading=abs(base_loading[m] * 100.0),
                         contingency_idx=contingency_idx,
                         contingency_name=contingency_group.name,
                         contingency_uuid=contingency_group.idtag,
                         post_contingency_flow=c_flow,
                         contingency_rating=numerical_circuit.branch_data.contingency_rates[m],
                         post_contingency_loading=abs(contingency_loadings[m]) * 100.0,
                         solved_by_srap=solved_by_srap,
                         srap_power=max_srap_power,
                         srap_bus_indices=None)

            else:

                if c_flow > numerical_circuit.contingency_rates[m]:
                    # if the contingency flow is greater than the rate ...

                    self.add(time_index=t if t is not None else 0,
                             base_name=numerical_circuit.branch_data.names[m],
                             base_uuid=calc_branches[m].idtag,
                             base_flow=b_flow,
                             base_rating=numerical_circuit.branch_data.rates[m],
                             base_loading=abs(base_loading[m] * 100.0),
                             contingency_idx=contingency_idx,
                             contingency_name=contingency_group.name,
                             contingency_uuid=contingency_group.idtag,
                             post_contingency_flow=c_flow,
                             contingency_rating=numerical_circuit.branch_data.contingency_rates[m],
                             post_contingency_loading=abs(contingency_loadings[m]) * 100.0)
