# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
from typing import Union, List, TYPE_CHECKING

from VeraGridEngine.Compilers.Gslv.Simulations.contingencies import gslv_contingencies_snapshot
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Events.contingency_group import ContingencyGroup
from VeraGridEngine.enumerations import EngineType, ContingencyMethod, SimulationTypes
from VeraGridEngine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Simulations.LinearFactors.linear_analysis import LinearMultiContingencies, LinearAnalysis
from VeraGridEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions
from VeraGridEngine.Simulations.ContingencyAnalysis.Methods.nonlinear_contingency_analysis import (
    nonlinear_contingency_analysis)
from VeraGridEngine.Simulations.ContingencyAnalysis.Methods.linear_contingency_analysis import (
    linear_contingency_analysis)
from VeraGridEngine.Simulations.ContingencyAnalysis.Methods.helm_contingency_analysis import helm_contingency_analysis
from VeraGridEngine.Compilers.circuit_to_pgm import PGM_AVAILABLE, PGM_UNAVAILABLE_REASON

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGridEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults


class ContingencyAnalysisDriver(DriverTemplate):
    """
    Contingency analysis driver
    """
    __slots__ = (
        "options",
        "opf_results",
        "linear_multiple_contingencies",
        "contingency_groups_used",
        "con_names_used"
    )

    name = 'Contingency Analysis'
    tpe = SimulationTypes.ContingencyAnalysis_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: ContingencyAnalysisOptions | None,
                 linear_multiple_contingencies: Union[LinearMultiContingencies, None] = None,
                 opf_results: Union[OptimalPowerFlowResults, None] = None,
                 engine: EngineType = EngineType.VeraGrid):
        """
        ContingencyAnalysisDriver constructor
        :param grid: MultiCircuit Object
        :param options: N-k options
        :param linear_multiple_contingencies: LinearMultiContingencies instance (required for linear contingencies)
        :param engine Calculation engine to use
        """
        DriverTemplate.__init__(self, grid=grid, engine=engine)

        # Options to use
        self.options: ContingencyAnalysisOptions = options if options is not None else ContingencyAnalysisOptions(
            contingency_groups=grid.contingency_groups
        )

        self.opf_results: Union[OptimalPowerFlowResults, None] = opf_results

        # Set or create the LinearMultiContingencies
        if linear_multiple_contingencies is None:
            if options is None:
                contingency_groups_used = grid.get_contingency_groups()
            else:
                contingency_groups_used = (grid.get_contingency_groups()
                                           if options.contingency_groups is None
                                           else options.contingency_groups)

            self.linear_multiple_contingencies = LinearMultiContingencies(
                grid=self.grid,
                contingency_groups_used=contingency_groups_used
            )
            self.logger.add_info("Created LinearMultiContingencies because they were not provided")
        else:
            self.linear_multiple_contingencies: LinearMultiContingencies = linear_multiple_contingencies

        self.contingency_groups_used: List[ContingencyGroup] = (self.grid.get_contingency_groups()
                                                           if self.options.contingency_groups is None
                                                           else self.options.contingency_groups)

        self.con_names_used=np.array([contingency_group.name for contingency_group in self.contingency_groups_used])

        # N-K results
        self.results = ContingencyAnalysisResults(
            ncon=len(self.contingency_groups_used),
            nbus=self.grid.get_bus_number(),
            nbr=self.grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
            bus_names=self.grid.get_bus_names(),
            branch_names=self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
            bus_types=np.ones(self.grid.get_bus_number(), dtype=int),
            con_names=self.con_names_used
        )

    def get_steps(self) -> List[str]:
        """
        Get variations list of strings
        """
        if self.results is not None:
            return ['#' + v for v in self.results.branch_names]
        else:
            return list()

    def run_at(self, t_idx: int | None = None, t_prob: float = 1.0, show_progress=False) -> ContingencyAnalysisResults:
        """
        Run the contingency at a time point
        :param t_idx: index for any time series index, None for the snapshot
        :param t_prob: probability of te time
        :param show_progress: Show the progress
        :return: ContingencyAnalysisResults
        """
        if self.engine == EngineType.PGM and not PGM_AVAILABLE:
            self.engine = EngineType.VeraGrid
            self.logger.add_warning(f'PGM unavailable: {PGM_UNAVAILABLE_REASON}; falling back to VeraGrid')

        if self.results.Sbus.shape[0] == 0:
            return self.results
        else:
            pass

        if self.engine == EngineType.VeraGrid:

            if self.options.contingency_method == ContingencyMethod.PowerFlow:
                area_names, bus_area_indices, F, T, hvdc_F, hvdc_T = self.grid.get_branch_areas_info()

                # set the numerical circuit
                nc = compile_numerical_circuit_at(self.grid,
                                                  opf_results=self.opf_results,
                                                  t_idx=t_idx)

                self.results = nonlinear_contingency_analysis(
                    nc=nc,
                    options=self.options,
                    linear_multiple_contingencies=self.linear_multiple_contingencies,
                    area_names=area_names,
                    bus_area_indices=np.array(bus_area_indices, dtype=int),
                    F=F,
                    T=T,
                    report_text=self.report_text,
                    report_progress2=self.report_progress2,
                    is_cancel=self.is_cancel,
                    t_idx=t_idx,
                    t_prob=t_prob,
                    logger=self.logger,
                    report_progress=show_progress
                )

            elif (self.options.contingency_method == ContingencyMethod.Linear
                  or self.options.contingency_method == ContingencyMethod.PTDF_scan):

                area_names, bus_area_indices, F, T, hvdc_F, hvdc_T = self.grid.get_branch_areas_info()

                # set the numerical circuit
                nc = compile_numerical_circuit_at(self.grid,
                                                  opf_results=self.opf_results,
                                                  t_idx=t_idx)

                # Linear analysis (PTDF & LODF)
                lin = LinearAnalysis(
                    nc=nc,
                    distributed_slack=self.options.lin_options.distribute_slack,
                    correct_values=self.options.lin_options.correct_values,
                    use_jacobian_ptdf=self.options.lin_options.use_jacobian_ptdf,
                    logger=self.logger
                )

                # "smart" Contingency factors
                linear_multiple_contingencies = LinearMultiContingencies(
                    grid=self.grid,
                    contingency_groups_used=self.options.contingency_groups
                    if self.options.contingency_groups is not None else self.grid.contingency_groups
                )
                linear_multiple_contingencies.compute(
                    lin=lin,
                    ptdf_threshold=self.options.lin_options.ptdf_threshold,
                    lodf_threshold=self.options.lin_options.lodf_threshold
                )

                self.results = linear_contingency_analysis(
                    nc=nc,
                    options=self.options,
                    linear_analysis=lin,
                    linear_multiple_contingencies=linear_multiple_contingencies,
                    area_names=area_names,
                    bus_area_indices=np.array(bus_area_indices, dtype=int),
                    F=F,
                    T=T,
                    report_text=self.report_text,
                    report_progress2=self.report_progress2,
                    is_cancel=self.is_cancel,
                    t=t_idx,
                    t_prob=t_prob,
                    logger=self.logger,
                    report_progress=show_progress
                )

            elif self.options.contingency_method == ContingencyMethod.HELM:

                self.results = helm_contingency_analysis(
                    grid=self.grid,
                    options=self.options,
                    calling_class=self,
                    opf_results=self.opf_results,
                    t=t_idx,
                    t_prob=t_prob
                )

            # elif self.options.contingency_method == ContingencyMethod.OptimalPowerFlow:
            # self.results = optimal_linear_contingency_analysis(
            #     grid=self.grid,
            #     options=self.options,
            #     opf_options=None,  # TODO: finalize this
            #     linear_multiple_contingencies=self.linear_multiple_contingencies,
            #     calling_class=self,
            #     t=t_idx,
            #     t_prob=t_prob,
            #     logger=self.logger
            # )
            else:
                raise Exception(f'Unknown contingency engine {self.options.contingency_method}')

        elif self.engine == EngineType.GSLV:

            self.report_text("Running contingencies in gslv...")
            con_res = gslv_contingencies_snapshot(circuit=self.grid,
                                                  con_opt=self.options,
                                                  opf_results=self.opf_results)

            self.results = ContingencyAnalysisResults(
                ncon=len(self.contingency_groups_used),
                nbus=self.grid.get_bus_number(),
                nbr=self.grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
                bus_names=self.grid.get_bus_names(),
                branch_names=self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
                bus_types=np.ones(self.grid.get_bus_number(), dtype=int),
                con_names=self.con_names_used
            )

            self.results.Sf = con_res.Sf
            self.results.loading = con_res.loading
            self.results.Sbus = con_res.Sbus
            self.results.voltage = con_res.voltage
            # self.results.max_flows = con_res.Sf[0, :]
            # self.results.max_loading = con_res.loading[0, :]
            for entry in con_res.report.entries:
                self.results.report.add(
                    time_index=entry.time_index,
                    t_prob=entry.t_prob,
                    mon_idx=entry.mon_idx,
                    con_group_idx=entry.con_group_idx,
                    area_from=entry.area_from,
                    area_to=entry.area_to,
                    base_name=entry.base_name,
                    contingency_name=entry.contingency_name,
                    base_rating=entry.base_rating,
                    contingency_rating=entry.contingency_rating,
                    srap_rating=entry.srap_rating,
                    base_flow=entry.base_flow.real,
                    post_contingency_flow=entry.post_contingency_flow.real,
                    post_srap_flow=entry.post_srap_flow.real,
                    base_loading=entry.base_loading,
                    post_contingency_loading=entry.post_contingency_loading,
                    post_srap_loading=entry.post_srap_loading,
                    msg_ov=entry.msg_ov,
                    msg_srap=entry.msg_srap,
                    srap_power=entry.srap_power,
                    solved_by_srap=entry.solved_by_srap
                )

        return self.results

    def run(self) -> None:
        """

        :return:
        """
        self.tic()
        self.report_text("Compiling and configuring...")

        self.run_at(t_idx=None, show_progress=True)
        self.toc()
