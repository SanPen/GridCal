# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import numpy as np
from typing import Union, List

from VeraGridEngine.Compilers.circuit_to_gslv import gslv_contingencies
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import EngineType, ContingencyMethod, SimulationTypes
from VeraGridEngine.Simulations.ContingencyAnalysis.contingency_analysis_results import ContingencyAnalysisResults
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.LinearFactors.linear_analysis import LinearMultiContingencies
from VeraGridEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions
from VeraGridEngine.Simulations.ContingencyAnalysis.Methods.nonlinear_contingency_analysis import \
    nonlinear_contingency_analysis
from VeraGridEngine.Simulations.ContingencyAnalysis.Methods.linear_contingency_analysis import \
    linear_contingency_analysis
from VeraGridEngine.Simulations.ContingencyAnalysis.Methods.helm_contingency_analysis import helm_contingency_analysis
from VeraGridEngine.Simulations.ContingencyAnalysis.Methods.optimal_linear_contingency_analysis import \
    optimal_linear_contingency_analysis
from VeraGridEngine.Compilers.circuit_to_bentayga import BENTAYGA_AVAILABLE
from VeraGridEngine.Compilers.circuit_to_newton_pa import (NEWTON_PA_AVAILABLE, newton_pa_contingencies,
                                                           translate_newton_pa_contingencies)
from VeraGridEngine.Compilers.circuit_to_pgm import PGM_AVAILABLE


class ContingencyAnalysisDriver(DriverTemplate):
    """
    Contingency analysis driver
    """
    name = 'Contingency Analysis'
    tpe = SimulationTypes.ContingencyAnalysis_run

    def __init__(self,
                 grid: MultiCircuit,
                 options: ContingencyAnalysisOptions | None,
                 linear_multiple_contingencies: Union[LinearMultiContingencies, None] = None,
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
        self.options = options

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

        # N-K results
        self.results = ContingencyAnalysisResults(
            ncon=self.grid.get_contingency_groups_number(),
            nbus=self.grid.get_bus_number(),
            nbr=self.grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
            bus_names=self.grid.get_bus_names(),
            branch_names=self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
            bus_types=np.ones(self.grid.get_bus_number(), dtype=int),
            con_names=np.array(self.grid.get_contingency_group_names())
        )

    def get_steps(self) -> List[str]:
        """
        Get variations list of strings
        """
        if self.results is not None:
            return ['#' + v for v in self.results.branch_names]
        else:
            return list()

    def run_at(self, t_idx: int = None, t_prob: float = 1.0) -> ContingencyAnalysisResults:
        """
        Run the contingency at a time point
        :param t_idx: index for any time series index, None for the snapshot
        :param t_prob: probability of te time
        :return: ContingencyAnalysisResults
        """
        if self.engine == EngineType.NewtonPA and not NEWTON_PA_AVAILABLE:
            self.engine = EngineType.VeraGrid
            self.logger.add_warning('Tried to use Newton, but failed back to VeraGrid')

        if self.engine == EngineType.Bentayga and not BENTAYGA_AVAILABLE:
            self.engine = EngineType.VeraGrid
            self.logger.add_warning('Tried to use Bentayga, but failed back to VeraGrid')

        if self.engine == EngineType.PGM and not PGM_AVAILABLE:
            self.engine = EngineType.VeraGrid
            self.logger.add_warning('Tried to use PGM, but failed back to VeraGrid')

        if self.engine == EngineType.VeraGrid:

            if self.options.contingency_method == ContingencyMethod.PowerFlow:
                self.results = nonlinear_contingency_analysis(
                    grid=self.grid,
                    options=self.options,
                    linear_multiple_contingencies=self.linear_multiple_contingencies,
                    calling_class=self,
                    t_idx=t_idx,
                    t_prob=t_prob,
                    logger=self.logger
                )

            elif self.options.contingency_method == ContingencyMethod.PTDF:
                self.results = linear_contingency_analysis(
                    grid=self.grid,
                    options=self.options,
                    linear_multiple_contingencies=self.linear_multiple_contingencies,
                    calling_class=self,
                    t=t_idx,
                    t_prob=t_prob,
                    logger=self.logger
                )

            elif self.options.contingency_method == ContingencyMethod.HELM:
                self.results = helm_contingency_analysis(
                    grid=self.grid,
                    options=self.options,
                    calling_class=self,
                    t=t_idx,
                    t_prob=t_prob
                )
            elif self.options.contingency_method == ContingencyMethod.OptimalPowerFlow:
                self.results = optimal_linear_contingency_analysis(
                    grid=self.grid,
                    options=self.options,
                    opf_options=None,  # TODO: finalize this
                    linear_multiple_contingencies=self.linear_multiple_contingencies,
                    calling_class=self,
                    t=t_idx,
                    t_prob=t_prob,
                    logger=self.logger
                )
            else:
                raise Exception(f'Unknown contingency engine {self.options.contingency_method}')

        elif self.engine == EngineType.NewtonPA:

            self.report_text("Running contingencies in newton...")
            con_res = newton_pa_contingencies(circuit=self.grid,
                                              con_opt=self.options,
                                              time_series=False,
                                              time_indices=None)

            self.results = translate_newton_pa_contingencies(grid=self.grid,
                                                             con_res=con_res)

        elif self.engine == EngineType.GSLV:

            self.report_text("Running contingencies in gslv...")
            con_res = gslv_contingencies(circuit=self.grid,
                                         con_opt=self.options,
                                         time_series=False,
                                         time_indices=None)

            self.results = ContingencyAnalysisResults(
                ncon=self.grid.get_contingency_groups_number(),
                nbus=self.grid.get_bus_number(),
                nbr=self.grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
                bus_names=self.grid.get_bus_names(),
                branch_names=self.grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
                bus_types=np.ones(self.grid.get_bus_number(), dtype=int),
                con_names=np.array(self.grid.get_contingency_group_names())
            )

            # results.S[t, :] = res_t.S.real.max(axis=0)
            self.results.max_flows = con_res.max_values.Sf[0, :]
            self.results.max_loading = con_res.max_values.loading[0, :]

        return self.results

    def run(self) -> None:
        """

        :return:
        """
        self.tic()
        self.run_at(t_idx=None)
        self.toc()
