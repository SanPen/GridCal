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

    __hdr__ = ["Time",
               "Area 1",
               "Area 2",
               "Monitored",
               "Contingency",
               "Base rating (MW)",
               "Contingency rating (MW)",
               "SRAP rating (MW)",
               "Base flow (MW)",
               "Post-Contingency flow (MW)",
               "Post-SRAP flow (MW)",
               "Base loading (pu)",
               "Post-Contingency loading (pu)",
               "Post-SRAP loading (pu)",
               "Overload",
               "SRAP availability",
               "SRAP Power (MW)",
               "Solved with SRAP"]

    def __init__(self,
                 # time_index: int,
                 # base_name: str,
                 # base_uuid: str,
                 # base_flow: complex,
                 # base_rating: float,
                 # base_loading: float,
                 # contingency_idx: int,
                 # contingency_name: str,
                 # contingency_uuid: str,
                 # post_contingency_flow: complex,
                 # contingency_rating: float,
                 # post_contingency_loading: float,
                 # solved_by_srap: bool = False,
                 # srap_power: float = 0.0,
                 # srap_bus_indices: IntVec = None):
                #
                time_index: int,
                base_uuid: str,
                contingency_uuid: str,
                base_name: str,
                contingency_name: str,
                base_rating: float,
                contingency_rating: float,
                srap_rating: float,
                base_flow: complex,
                post_contingency_flow: complex,
                post_srap_flow: complex,
                base_loading: float,
                post_contingency_loading: float,
                post_srap_loading: float,
                msg_ov: str,
                msg_srap: str,
                srap_power: float,
                solved_by_srap: bool = False):
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
        # self.time_index: int = time_index
        #
        # self.base_name: str = base_name
        # self.base_uuid: str = base_uuid
        #
        # self.base_flow = base_flow
        # self.base_rating = base_rating
        # self.base_loading = base_loading
        #
        # self.contingency_idx: int = contingency_idx
        # self.contingency_name: str = contingency_name
        # self.contingency_uuid: str = contingency_uuid
        # self.post_contingency_flow: complex = post_contingency_flow
        # self.contingency_rating: float = contingency_rating
        # self.post_contingency_loading: float = post_contingency_loading
        #
        # self.solved_by_srap: bool = solved_by_srap
        # self.srap_power = srap_power
        # self.srap_bus_indices: IntVec = srap_bus_indices if srap_bus_indices is not None else np.zeros(0, dtype=int)

        self.time_index: int = time_index
        self.base_uuid: str = base_uuid
        self.contingency_uuid: str = contingency_uuid
        self.base_name: str = base_name
        self.contingency_name: str = contingency_name
        self.base_rating: float = base_rating
        self.contingency_rating: float = contingency_rating
        self.srap_rating: float = srap_rating
        self.base_flow: complex = base_flow
        self.post_contingency_flow: complex = post_contingency_flow
        self.post_srap_flow: complex = post_srap_flow
        self.base_loading: float = base_loading
        self.post_contingency_loading: float = post_contingency_loading
        self.post_srap_loading: float = post_srap_loading
        self.msg_ov : str = msg_ov
        self.msg_srap = str = msg_srap
        self.srap_power: float = srap_power
        self.solved_by_srap: bool = solved_by_srap

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
        # return [self.time_index,
        #         self.base_name,
        #         self.base_uuid,
        #         self.base_flow,
        #         self.base_rating,
        #         self.base_loading,
        #         self.contingency_idx,
        #         self.contingency_name,
        #         self.contingency_uuid,
        #         self.post_contingency_flow,
        #         self.contingency_rating,
        #         self.post_contingency_loading,
        #         self.solved_by_srap,
        #         self.srap_power,
        #         ",".join(self.srap_bus_indices)]

        return [self.time_index,
                self.base_uuid,
                self.contingency_uuid,
                self.base_name,
                self.contingency_name,
                self.base_rating,
                self.contingency_rating,
                self.srap_rating,
                self.base_flow,
                self.post_contingency_flow,
                self.post_srap_flow,
                self.base_loading,
                self.post_contingency_loading,
                self.post_srap_loading,
                self.msg_ov,
                self.msg_srap,
                self.srap_power,
                self.solved_by_srap]

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
            # time_index: int,
            # base_name: str,
            # base_uuid: str,
            # base_flow: complex,
            # base_rating: float,
            # base_loading: float,
            # contingency_idx: int,
            # contingency_name: str,
            # contingency_uuid: str,
            # post_contingency_flow: complex,
            # contingency_rating: float,
            # post_contingency_loading: float,
            # srap_fixing_probability: Mat = [],
            # solved_by_srap: bool = False,
            # srap_power: float = 0.0,
            # srap_bus_indices: IntVec = None):
            #
            time_index: int,
            base_uuid: str,
            contingency_uuid: str,
            base_name: str,
            contingency_name: str,
            base_rating: float,
            contingency_rating: float,
            srap_rating: float,
            base_flow: complex,
            post_contingency_flow: complex,
            post_srap_flow : complex,
            base_loading: float,
            post_contingency_loading: float,
            post_srap_loading: float,
            msg_ov = str,
            msg_srap = str,
            srap_power = float,
            solved_by_srap: bool = False):


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
        self.add_entry(ContingencyTableEntry(#time_index=time_index,
                                             # base_name=base_name,
                                             # base_uuid=base_uuid,
                                             # base_flow=base_flow,
                                             # base_rating=base_rating,
                                             # base_loading=base_loading,
                                             # contingency_idx=contingency_idx,
                                             # contingency_name=contingency_name,
                                             # contingency_uuid=contingency_uuid,
                                             # post_contingency_flow=post_contingency_flow,
                                             # contingency_rating=contingency_rating,
                                             # post_contingency_loading=post_contingency_loading,
                                             # solved_by_srap=solved_by_srap,
                                             # srap_power=srap_power,
                                             # srap_bus_indices=srap_bus_indices))
                                            time_index= time_index,
                                            base_uuid= base_uuid,
                                            contingency_uuid= contingency_uuid,
                                            base_name= base_name,
                                            contingency_name= contingency_name,
                                            base_rating= base_rating,
                                            contingency_rating= contingency_rating,
                                            srap_rating= srap_rating,
                                            base_flow= base_flow,
                                            post_contingency_flow= post_contingency_flow,
                                            post_srap_flow= post_srap_flow,
                                            base_loading= base_loading,
                                            post_contingency_loading = post_contingency_loading,
                                            post_srap_loading= post_srap_loading,
                                            msg_ov = msg_ov,
                                            msg_srap = msg_srap,
                                            srap_power=srap_power,
                                            solved_by_srap = solved_by_srap))

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
                srap_ratings: Union[Vec, None] = None,
                srap_max_power: float = 1400.0,
                srap_deadband: float = 0.0,
                srap_rever_to_nominal_rating: bool = False,
                multi_contingency: LinearMultiContingency = None,
                PTDF: Mat = None,
                available_power: Vec = None,
                srap_used_power: Mat = None,
                top_n: int = 5,
                detailed_massive_report: bool = True):
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
        :param srap_ratings: Array of protection ratings of the branches to use with SRAP
        :param srap_max_power: Max amount of power to lower using SRAP conditions
        :param srap_deadband: (in %)
        :param srap_rever_to_nominal_rating:
        :param multi_contingency: list of buses for SRAP conditions
        :param PTDF: PTDF for SRAP conditions
        :param available_power: Array of power avaiable for SRAP
        :param srap_used_power: (branch, nbus) matrix to stre SRAP usage
        :param top_n: maximum number of nodes affecting the oveload
        :param detailed_massive_report: Generate massive report
        """

        #Aqui reporte de base




        ##################


        for m in mon_idx:  # for each monitored branch ...

            c_flow = abs(contingency_flows[m])
            b_flow = abs(base_flow[m])

            c_load = abs(contingency_loadings[m])

            rate_nx_pu = numerical_circuit.contingency_rates[m]/(numerical_circuit.rates[m]+ 1e-9)
            rate_srap_pu = srap_ratings[m]/(numerical_circuit.rates[m]+ 1e-9)

            # Affected by contingency?
            affected_by_cont = contingency_flows[m] != base_flow[m]

            # Only study if the flow is affected enough by contingency, if it produces an overload, and if the variation affects negatively to the flow
            if affected_by_cont and c_load > 1 and c_flow > b_flow:

                #Conditions to set behaviour
                if 1 < c_load <= rate_nx_pu:
                    ov_status = 1
                    msg_ov = 'Overload acceptable'
                    cond_srap = False
                    msg_srap = 'SRAP not needed'
                    post_srap_flow = c_flow
                    solved_by_srap = False
                    max_srap_power = 0

                elif rate_nx_pu < c_load <= rate_srap_pu:
                    ov_status = 2
                    msg_ov = 'Overload not acceptable' # Overwritten if solved
                    cond_srap = True # Srap aplicable
                    msg_srap = 'SRAP applicable'

                elif rate_srap_pu < c_load <= rate_srap_pu + srap_deadband/100:
                    ov_status = 3
                    msg_ov = 'Overload not acceptable'
                    cond_srap = True
                    msg_srap = 'SRAP not applicable'

                elif c_load > rate_srap_pu + srap_deadband/100:
                    ov_status = 4
                    msg_ov = 'Overload not acceptable'
                    cond_srap = False
                    msg_srap = 'SRAP not applicable'
                    post_srap_flow = c_flow
                    solved_by_srap = False
                    max_srap_power = 0


                if using_srap and cond_srap:

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
                        branch_idx=m,
                        top_n=top_n,
                        srap_used_power=srap_used_power
                    )

                    post_srap_flow = abs(c_flow) - abs(max_srap_power)
                    if  post_srap_flow < 0:
                        post_srap_flow = 0

                    if(solved_by_srap and ov_status == 2):
                        msg_ov = 'Overload acceptable'

                if detailed_massive_report:
                    # self.add(time_index=t if t is not None else 0,
                    #          base_name=numerical_circuit.branch_data.names[m],
                    #          base_uuid=calc_branches[m].idtag,
                    #          base_flow=abs(b_flow),
                    #          base_rating=numerical_circuit.branch_data.rates[m],
                    #          base_loading=abs(base_loading[m] * 100.0),
                    #          contingency_idx=contingency_idx,
                    #          contingency_name=contingency_group.name,
                    #          contingency_uuid=contingency_group.idtag,
                    #          post_contingency_flow=abs(c_flow),
                    #          contingency_rating=numerical_circuit.branch_data.contingency_rates[m],
                    #          post_contingency_loading=abs(contingency_loadings[m]) * 100.0,
                    #          solved_by_srap=solved_by_srap,
                    #          srap_power=max_srap_power,
                    #          srap_bus_indices=None)

                    self.add(time_index=t if t is not None else 0,  # --------->Convertir a fecha
                             base_uuid=calc_branches[m].idtag,  # --------->Cambiar a CCAA1
                             contingency_uuid=contingency_group.idtag,  # --------->Cambiar a CCAA2
                             base_name=numerical_circuit.branch_data.names[m],
                             contingency_name=contingency_group.name,
                             base_rating=numerical_circuit.branch_data.rates[m],
                             contingency_rating=numerical_circuit.branch_data.contingency_rates[m],
                             srap_rating = srap_ratings[m],
                             base_flow=abs(b_flow),
                             post_contingency_flow=abs(c_flow),
                             post_srap_flow = post_srap_flow,
                             base_loading=abs(base_loading[m] ),
                             post_contingency_loading=abs(contingency_loadings[m]) ,
                             post_srap_loading = post_srap_flow /(numerical_circuit.rates[m]+ 1e-9),
                             msg_ov = msg_ov,
                             msg_srap = msg_srap,
                             srap_power=abs(max_srap_power),
                             solved_by_srap=solved_by_srap)

                # else:
                #
                #     if detailed_massive_report:
                #         # self.add(time_index=t if t is not None else 0,
                #         #          base_name=numerical_circuit.branch_data.names[m],
                #         #          base_uuid=calc_branches[m].idtag,
                #         #          base_flow=b_flow,
                #         #          base_rating=numerical_circuit.branch_data.rates[m],
                #         #          base_loading=abs(base_loading[m] * 100.0),
                #         #          contingency_idx=contingency_idx,
                #         #          contingency_name=contingency_group.name,
                #         #          contingency_uuid=contingency_group.idtag,
                #         #          post_contingency_flow=c_flow,
                #         #          contingency_rating=numerical_circuit.branch_data.contingency_rates[m],
                #         #          post_contingency_loading=abs(contingency_loadings[m]) * 100.0)
                #
                #         self.add(time_index=t if t is not None else 0,  # --------->Convertir a fecha
                #                  base_uuid=calc_branches[m].idtag,  # --------->Cambiar a CCAA1
                #                  contingency_uuid=contingency_group.idtag,  # --------->Cambiar a CCAA2
                #                  base_name=numerical_circuit.branch_data.names[m],
                #                  contingency_name=contingency_group.name,
                #                  base_rating=numerical_circuit.branch_data.rates[m],
                #                  contingency_rating=numerical_circuit.branch_data.contingency_rates[m],
                #                  srap_rating=srap_ratings[m],
                #                  base_flow=abs(b_flow),
                #                  post_contingency_flow=abs(c_flow),
                #                  post_srap_flow=abs(c_flow) - 0,
                #                  base_loading=abs(base_loading[m]),
                #                  post_contingency_loading=abs(contingency_loadings[m]) ,
                #                  post_srap_loading=(abs(c_flow) - 0)  / (
                #                              numerical_circuit.rates[m] + 1e-9),
                #                  msg_ov=msg_ov,
                #                  msg_srap=msg_srap,
                #                  srap_power=abs(max_srap_power),
                #                  solved_by_srap= False)
