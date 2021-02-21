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
import time
import multiprocessing
from PySide2.QtCore import QThread, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.LinearFactors.ptdf_analysis import get_ptdf_variations, power_flow_worker, PtdfGroupMode
from GridCal.Engine.Simulations.LinearFactors.ptdf_results import PTDFResults
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class PTDFOptions:

    def __init__(self, group_mode: PtdfGroupMode = PtdfGroupMode.ByGenLoad,
                 power_increment=100.0, use_multi_threading=False):
        """
        Power Transfer Distribution Factors' options
        :param group_mode: Grouping type
        :param power_increment: Amount of power to change in MVA
        :param use_multi_threading: use multi-threading?
        """
        self.group_mode = group_mode

        self.power_increment = power_increment

        self.use_multi_threading = use_multi_threading


class PTDF(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'PTDF'

    def __init__(self, grid: MultiCircuit, options: PTDFOptions, pf_options: PowerFlowOptions, opf_results=None):
        """
        Power Transfer Distribution Factors class constructor
        @param grid: MultiCircuit Object
        @param options: OPF options
        """
        QThread.__init__(self)

        # Grid to run
        self.grid = grid

        # Options to use
        self.options = options

        # power flow options
        self.pf_options = pf_options

        self.opf_results = opf_results

        # OPF results
        self.results = None

        # set cancel state
        self.__cancel__ = False

        self.all_solved = True

        self.elapsed = 0.0

        self.logger = Logger()

    def ptdf(self, circuit: MultiCircuit, options: PowerFlowOptions, group_mode: PtdfGroupMode, power_amount,
             text_func=None, prog_func=None):
        """
        Power Transfer Distribution Factors analysis
        :param circuit: MultiCircuit instance
        :param options: power flow options
        :param group_mode: group mode
        :param power_amount: amount o power to vary in MW
        :param text_func: text function to display progress
        :param prog_func: progress function to display progress [0~100]
        :return:
        """

        if text_func is not None:
            text_func('Compiling...')

        # compile to arrays
        numerical_circuit = compile_snapshot_circuit(circuit=circuit,
                                                     apply_temperature=options.apply_temperature_correction,
                                                     branch_tolerance_mode=options.branch_impedance_tolerance_mode,
                                                     opf_results=self.opf_results)

        calculation_inputs = numerical_circuit.split_into_islands(ignore_single_node_islands=options.ignore_single_node_islands)

        # compute the variations
        delta_of_power_variations = get_ptdf_variations(circuit=circuit,
                                                        numerical_circuit=numerical_circuit,
                                                        group_mode=group_mode,
                                                        power_amount=power_amount)

        # declare the PTDF results
        results = PTDFResults(n_variations=len(delta_of_power_variations) - 1,
                              n_br=numerical_circuit.nbr,
                              n_bus=numerical_circuit.nbus,
                              br_names=numerical_circuit.branch_names,
                              bus_names=numerical_circuit.bus_names,
                              bus_types=numerical_circuit.bus_types)

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
                              n_tr=numerical_circuit.ntr,
                              bus_names=numerical_circuit.bus_names,
                              branch_names=numerical_circuit.branch_names,
                              transformer_names=numerical_circuit.tr_names,
                              bus_types=numerical_circuit.bus_types,
                              calculation_inputs=calculation_inputs,
                              options=options,
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

            if self.__cancel__:
                break

        return results

    def ptdf_multi_treading(self, circuit: MultiCircuit, options: PowerFlowOptions, group_mode: PtdfGroupMode,
                            power_amount, text_func=None, prog_func=None):
        """
        Power Transfer Distribution Factors analysis
        :param circuit: MultiCircuit instance
        :param options: power flow options
        :param group_mode: ptdf grouping mode
        :param power_amount: amount o power to vary in MW
        :param text_func:
        :param prog_func
        :return:
        """

        if text_func is not None:
            text_func('Compiling...')

        # compile to arrays
        # numerical_circuit = circuit.compile_snapshot()
        # calculation_inputs = numerical_circuit.compute(apply_temperature=options.apply_temperature_correction,
        #                                                branch_tolerance_mode=options.branch_impedance_tolerance_mode,
        #                                                ignore_single_node_islands=options.ignore_single_node_islands)

        numerical_circuit = compile_snapshot_circuit(circuit=circuit,
                                                     apply_temperature=options.apply_temperature_correction,
                                                     branch_tolerance_mode=options.branch_impedance_tolerance_mode,
                                                     opf_results=self.opf_results)

        calculation_inputs = numerical_circuit.split_into_islands(ignore_single_node_islands=options.ignore_single_node_islands)

        # compute the variations
        delta_of_power_variations = get_ptdf_variations(circuit=circuit,
                                                        numerical_circuit=numerical_circuit,
                                                        group_mode=group_mode,
                                                        power_amount=power_amount)

        # declare the PTDF results
        results = PTDFResults(n_variations=len(delta_of_power_variations) - 1,
                              n_br=numerical_circuit.nbr,
                              n_bus=numerical_circuit.nbus,
                              br_names=numerical_circuit.branch_names,
                              bus_names=numerical_circuit.bus_names,
                              bus_types=numerical_circuit.bus_types)

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
                                                                            numerical_circuit.ntr,
                                                                            numerical_circuit.bus_names,
                                                                            numerical_circuit.branch_names,
                                                                            numerical_circuit.tr_names,
                                                                            numerical_circuit.bus_types,
                                                                            calculation_inputs,
                                                                            options,
                                                                            delta_of_power_variations[v].dP,
                                                                            return_dict))
                jobs.append(p)
                p.start()
                v += 1
                k += 1

                if self.__cancel__:
                    break

            # wait for all jobs to complete
            for process_ in jobs:
                process_.join()

            # emit the progress
            if prog_func is not None:
                p = (v + 1) / nvar * 100.0
                prog_func(p)

            if self.__cancel__:
                break

        if text_func is not None:
            text_func('Collecting results...')

        # gather the results
        if not self.__cancel__:
            for v in range(nvar):
                pf_results, log = return_dict[v]
                results.logger += log
                if v == 0:
                    results.default_pf_results = pf_results
                else:
                    results.add_results_at(v - 1, pf_results, delta_of_power_variations[v])

        return results

    def run(self):
        """
        Run thread
        """
        start = time.time()
        if self.options.use_multi_threading:

            self.results = self.ptdf_multi_treading(circuit=self.grid, options=self.pf_options,
                                                    group_mode=self.options.group_mode,
                                                    power_amount=self.options.power_increment,
                                                    text_func=self.progress_text.emit,
                                                    prog_func=self.progress_signal.emit)
        else:

            self.results = self.ptdf(circuit=self.grid, options=self.pf_options,
                                     group_mode=self.options.group_mode,
                                     power_amount=self.options.power_increment,
                                     text_func=self.progress_text.emit,
                                     prog_func=self.progress_signal.emit)

        if not self.__cancel__:
            self.results.consolidate()

        end = time.time()
        self.elapsed = end - start
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def get_steps(self):
        """
        Get variations list of strings
        """
        if self.results is not None:
            return [v.name for v in self.results.variations]
        else:
            return list()

    def cancel(self):
        self.__cancel__ = True


if __name__ == '__main__':

    from GridCal.Engine import FileOpen, SolverType

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'

    main_circuit = FileOpen(fname).open()

    pf_options = PowerFlowOptions(solver_type=SolverType.DC)
    options_ = PTDFOptions(group_mode=PtdfGroupMode.ByGenLoad, power_increment=10, use_multi_threading=False)
    simulation = PTDF(grid=main_circuit, options=options_, pf_options=pf_options)
    simulation.run()
    ptdf_df = simulation.results.get_flows_data_frame()

    print(ptdf_df)

    print()
    a = time.time()
    options_ = PTDFOptions(group_mode=PtdfGroupMode.ByGenLoad, power_increment=10, use_multi_threading=True)
    simulation = PTDF(grid=main_circuit, options=options_, pf_options=pf_options)
    simulation.run()
    ptdf_df = simulation.results.get_flows_data_frame()
    b = time.time()
    print(ptdf_df)
    print(b-a)
