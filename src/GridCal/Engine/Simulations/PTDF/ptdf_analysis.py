# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.
import numpy as np
import multiprocessing
from typing import List
from GridCal.Engine.Core.calculation_inputs import CalculationInputs
from GridCal.Engine.Core.multi_circuit import MultiCircuit, NumericalCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions, PowerFlowMP, PowerFlowResults
from GridCal.Engine.Simulations.PTDF.ptdf_results import PTDFVariation, PTDFResults


def group_generators_by_technology(circuit: MultiCircuit):
    """
    Compose a dictionary of generator groups
    :param circuit: MultiCircuit
    :return: dictionary [Technology] : [generator indices]
    """
    gens = circuit.get_generators()

    groups = dict()

    for i, gen in enumerate(gens):

        if gen.technology in groups.keys():
            arr = np.r_[groups[gen.technology], i]
            groups[gen.technology] = arr

        else:
            groups[gen.technology] = np.array([i])

    return groups


def get_ptdf_variations(circuit: MultiCircuit, numerical_circuit: NumericalCircuit, group_by_technology, power_amount):
    """
    Get the PTDF variations
    :param circuit: MultiCircuit instance
    :param numerical_circuit: NumericalCircuit instance (faster)
    :param group_by_technology: group generators by technology?
    :param power_amount: power amount to vary. if group_by_technology the variation applies by group otherwise per
                         individual generator
    :return: list of Variations (instances of PTDFVariation)
    """
    variations = list()

    # declare the default variation object and store it
    var = PTDFVariation(name='Default', n=numerical_circuit.nbus)
    variations.append(var)

    # compute the per unit power
    power = power_amount / circuit.Sbase

    if group_by_technology:

        # get generator groups by technology
        groups = group_generators_by_technology(circuit=circuit)

        for key, indices in groups.items():
            ng = len(indices)

            # power increment by technology of all the generators
            dPg = np.ones(ng) * power / float(ng)

            # declare the variation object
            var = PTDFVariation(name=key, n=numerical_circuit.nbus)

            # power increment by bus
            var.dP = numerical_circuit.C_gen_bus[indices, :].transpose() * dPg

            # store the variation
            variations.append(var)

    else:

        for i in range(numerical_circuit.n_ctrl_gen):

            # generate array of zeros, and modify the generation for the particular generator
            dPg = np.zeros(numerical_circuit.n_ctrl_gen)
            dPg[i] = power

            # declare the variation object
            var = PTDFVariation(name=numerical_circuit.generator_names[i], n=numerical_circuit.nbus)

            # power increment by bus
            var.dP = numerical_circuit.C_gen_bus.transpose() * dPg

            # store the variation
            variations.append(var)

    return variations


def power_flow_worker(variation, nbus, nbr, calculation_inputs: List[CalculationInputs],
                      power_flow: PowerFlowMP, dP, return_dict):
    """
    Run asynchronous power flow
    :param nbus: number of buses
    :param nbr: number of branches
    :param calculation_inputs: list of CalculationInputs' instances
    :param power_flow: PowerFlowMP instance
    :param dP: delta of active power
    :param return_dict: dictionary to return values
    :return: Nothing because it is a worker, the return is done via the return_dict variable
    """
    # create new results
    pf_results = PowerFlowResults()
    pf_results.initialize(nbus, nbr)
    logger = list()

    # simulate each island and merge the results
    for i, calculation_input in enumerate(calculation_inputs):

        if len(calculation_input.ref) > 0:
            Vbus = calculation_input.Vbus
            Sbus = calculation_input.Sbus - dP[calculation_input.original_bus_idx]
            Ibus = calculation_input.Ibus

            # run circuit power flow
            res = power_flow.run_pf(circuit=calculation_input, Vbus=Vbus, Sbus=Sbus, Ibus=Ibus)

            bus_original_idx = calculation_input.original_bus_idx
            branch_original_idx = calculation_input.original_branch_idx

            # merge the results from this island
            pf_results.apply_from_island(res, bus_original_idx, branch_original_idx)

        else:
            logger.append('There are no slack nodes in the island ' + str(i))

    return_dict[variation] = (pf_results, logger)


def ptdf(circuit: MultiCircuit, options: PowerFlowOptions, group_by_technology, power_amount,
         text_func=None, prog_func=None):
    """
    Power Transfer Distribution Factors analysis
    :param circuit: MultiCircuit instance
    :param options: power flow options
    :param group_by_technology:group by technology of generation?
    :param power_amount: amount o power to vary in MW
    :return:
    """

    if text_func is not None:
        text_func('Compiling...')

    # initialize the power flow
    power_flow = PowerFlowMP(circuit, options)

    # compile to arrays
    numerical_circuit = circuit.compile()
    calculation_inputs = numerical_circuit.compute(apply_temperature=options.apply_temperature_correction,
                                                   branch_tolerance_mode=options.branch_impedance_tolerance_mode)

    # compute the variations
    delta_of_power_variations = get_ptdf_variations(circuit=circuit,
                                                    numerical_circuit=numerical_circuit,
                                                    group_by_technology=group_by_technology,
                                                    power_amount=power_amount)

    # declare the PTDF results
    results = PTDFResults(n_variations=len(delta_of_power_variations) - 1,
                          n_br=numerical_circuit.nbr,
                          br_names=numerical_circuit.branch_names)

    if text_func is not None:
        text_func('Running PTDF...')

    nvar = len(delta_of_power_variations)
    for v, variation in enumerate(delta_of_power_variations):

        # this super strange way of calling a function is done to maintain the same
        # call format as the multi-threading function
        returns = dict()
        power_flow_worker(variation=0,
                          nbus=numerical_circuit.nbus,
                          nbr=numerical_circuit.nbr,
                          calculation_inputs=calculation_inputs,
                          power_flow=power_flow,
                          dP=variation.dP,
                          return_dict=returns)

        pf_results, log = returns[0]
        results.logger += log

        # add the power flow results
        if v == 0:
            results.default_pf_results = pf_results
        else:
            results.add_results_at(v - 1, pf_results, variation)

        if prog_func is not None:
            p = (v + 1) / nvar * 100.0
            prog_func(p)

    return results


def ptdf_multi_treading(circuit: MultiCircuit, options: PowerFlowOptions, group_by_technology, power_amount,
                        text_func=None, prog_func=None):
    """
    Power Transfer Distribution Factors analysis
    :param circuit: MultiCircuit instance
    :param options: power flow options
    :param group_by_technology:group by technology of generation?
    :param power_amount: amount o power to vary in MW
    :return:
    """
    # initialize the power flow
    power_flow = PowerFlowMP(circuit, options)

    if text_func is not None:
        text_func('Compiling...')

    # compile to arrays
    numerical_circuit = circuit.compile()
    calculation_inputs = numerical_circuit.compute(apply_temperature=options.apply_temperature_correction,
                                                   branch_tolerance_mode=options.branch_impedance_tolerance_mode)

    # compute the variations
    delta_of_power_variations = get_ptdf_variations(circuit=circuit,
                                                    numerical_circuit=numerical_circuit,
                                                    group_by_technology=group_by_technology,
                                                    power_amount=power_amount)

    # declare the PTDF results
    results = PTDFResults(n_variations=len(delta_of_power_variations) - 1,
                          n_br=numerical_circuit.nbr,
                          br_names=numerical_circuit.branch_names)

    if text_func is not None:
        text_func('Running PTDF...')

    jobs = list()
    n_cores = multiprocessing.cpu_count()
    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    # for v, variation in enumerate(delta_of_power_variations):
    v = 0
    nvar = len(delta_of_power_variations)
    while v < nvar:

        k = 0

        # launch only n_cores jobs at the time
        while k < n_cores + 2 and (v + k) < nvar:

            # run power flow at the circuit
            p = multiprocessing.Process(target=power_flow_worker, args=(v,
                                                                        numerical_circuit.nbus,
                                                                        numerical_circuit.nbr,
                                                                        calculation_inputs,
                                                                        power_flow,
                                                                        delta_of_power_variations[v].dP,
                                                                        return_dict))
            jobs.append(p)
            p.start()
            v += 1
            k += 1

        # wait for all jobs to complete
        for process_ in jobs:
            process_.join()

        # emit the progress
        if prog_func is not None:
            p = (v + 1) / nvar * 100.0
            prog_func(p)

    if text_func is not None:
        text_func('Collecting results...')

    # gather the results
    for v in range(nvar):
        pf_results, log = return_dict[v]
        results.logger += log
        if v == 0:
            results.default_pf_results = pf_results
        else:
            results.add_results_at(v - 1, pf_results, delta_of_power_variations[v])

    return results


if __name__ == '__main__':
    from GridCal.Engine import FileOpen, SolverType
    import time
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'

    main_circuit = FileOpen(fname).open()

    pf_options = PowerFlowOptions(solver_type=SolverType.DC)

    ptdf_res = ptdf(circuit=main_circuit, options=pf_options, group_by_technology=True, power_amount=10)

    ptdf_df = ptdf_res.get_results_data_frame()

    print(ptdf_df)

    print()
    a = time.time()
    ptdf_res = ptdf_multi_treading(circuit=main_circuit, options=pf_options, group_by_technology=False, power_amount=10)

    ptdf_df = ptdf_res.get_results_data_frame()
    b = time.time()
    print(ptdf_df)
    print(b-a)
