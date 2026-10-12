# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.problems.emt_problem_multilinear import EmtProblemMultilinear
from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.basic_structures import Logger

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import EmtProblemTypes
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.driver_template import DummySignal


EMT_PROBLEM_CLASS_MAP = {
    EmtProblemTypes.CurrentBalance: EmtProblemDae,
    EmtProblemTypes.Multilinear: EmtProblemMultilinear,

}


def build_emt_problem(grid: MultiCircuit,
                      options: EmtOptions,
                      pf_results: PowerFlowResults | None = None,
                      pf_results_3ph: PowerFlowResults3Ph | None = None,
                      progress_signal: DummySignal | None = None,
                      logger: Logger | None = None) -> EmtProblemDae:
    """
    Build the EMT problem implementation selected in the simulation options.

    :param grid: Electrical grid whose devices define the EMT problem.
    :param options: EMT configuration, including the requested problem type.
    :param pf_results: Optional balanced power-flow initialization results.
    :param pf_results_3ph: Optional three-phase power-flow initialization results.
    :param progress_signal: Optional signal used to publish numeric progress.
    :param logger: Optional logger owned by the simulation driver.
    :return: Configured EMT problem ready to be passed to a solver.
    """
    if options.problem_type in EMT_PROBLEM_CLASS_MAP:
        problem_cls: type[EmtProblemDae] = EMT_PROBLEM_CLASS_MAP[options.problem_type]
    else:
        raise ValueError(f"Unsupported EMT problem type: {options.problem_type}")

    return problem_cls(
        grid=grid,
        options=options,
        pf_results=pf_results,
        pf_results_3ph =pf_results_3ph,
        progress_signal=progress_signal,
        logger=logger
    )
