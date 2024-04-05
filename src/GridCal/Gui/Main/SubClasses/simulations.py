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
import datetime
from collections import OrderedDict
from typing import List, Tuple, Dict, Union
import os
import numpy as np
# GUI importswa
from PySide6 import QtGui, QtWidgets
from matplotlib.colors import LinearSegmentedColormap

# Engine imports
import GridCalEngine.Devices as dev
import GridCalEngine.Simulations as sim
import GridCalEngine.Simulations.PowerFlow.grid_analysis as grid_analysis
import GridCal.Gui.GuiFunctions as gf
import GridCal.Gui.Visualization.visualization as viz
from GridCal.Gui.Diagrams.DiagramEditorWidget.diagram_editor_widget import DiagramEditorWidget
from GridCalEngine.Compilers.circuit_to_newton_pa import get_newton_mip_solvers_list
from GridCalEngine.Simulations.driver_types import SimulationTypes
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg, info_msg
from GridCal.Gui.Main.SubClasses.Model.time_events import TimeEventsMain
from GridCal.Gui.SigmaAnalysis.sigma_analysis_dialogue import SigmaAnalysisGUI
from GridCalEngine.Utils.MIP.selected_interface import get_available_mip_solvers
from GridCalEngine.IO.file_system import get_create_gridcal_folder
from GridCalEngine.enumerations import (DeviceType, AvailableTransferMode, SolverType,
                                        ReactivePowerControlMode, TapsControlMode, MIPSolvers, TimeGrouping,
                                        ZonalGrouping, ContingencyMethod, InvestmentEvaluationMethod, EngineType,
                                        BranchImpedanceMode, ResultTypes)


class SimulationsMain(TimeEventsMain):
    """
    SimulationsMain
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        TimeEventsMain.__init__(self, parent)

        # Power Flow Methods
        self.solvers_dict = OrderedDict()
        self.solvers_dict[SolverType.NR.value] = SolverType.NR
        self.solvers_dict[SolverType.NRI.value] = SolverType.NRI
        self.solvers_dict[SolverType.IWAMOTO.value] = SolverType.IWAMOTO
        self.solvers_dict[SolverType.LM.value] = SolverType.LM
        self.solvers_dict[SolverType.FASTDECOUPLED.value] = SolverType.FASTDECOUPLED
        self.solvers_dict[SolverType.HELM.value] = SolverType.HELM
        self.solvers_dict[SolverType.GAUSS.value] = SolverType.GAUSS
        self.solvers_dict[SolverType.LACPF.value] = SolverType.LACPF
        self.solvers_dict[SolverType.DC.value] = SolverType.DC

        self.ui.solver_comboBox.setModel(gf.get_list_model(list(self.solvers_dict.keys())))
        self.ui.solver_comboBox.setCurrentIndex(0)

        # reactive power controls
        self.q_control_modes_dict = OrderedDict()
        self.q_control_modes_dict['No control'] = ReactivePowerControlMode.NoControl
        self.q_control_modes_dict['Direct'] = ReactivePowerControlMode.Direct
        lst = list(self.q_control_modes_dict.keys())
        self.ui.reactive_power_control_mode_comboBox.setModel(gf.get_list_model(lst))

        # taps controls (transformer voltage regulator)
        self.taps_control_modes_dict = OrderedDict()
        self.taps_control_modes_dict['No control'] = TapsControlMode.NoControl
        self.taps_control_modes_dict['Direct'] = TapsControlMode.Direct
        lst = list(self.taps_control_modes_dict.keys())
        self.ui.taps_control_mode_comboBox.setModel(gf.get_list_model(lst))

        # transfer modes
        self.transfer_modes_dict = OrderedDict()
        self.transfer_modes_dict['Area generation'] = AvailableTransferMode.Generation
        self.transfer_modes_dict['Area installed power'] = AvailableTransferMode.InstalledPower
        self.transfer_modes_dict['Area load'] = AvailableTransferMode.Load
        self.transfer_modes_dict['Area nodes'] = AvailableTransferMode.GenerationAndLoad
        lst = list(self.transfer_modes_dict.keys())
        self.ui.transferMethodComboBox.setModel(gf.get_list_model(lst))
        self.ui.transferMethodComboBox.setCurrentIndex(1)

        # opf solvers dictionary
        self.lp_solvers_dict = OrderedDict()
        self.lp_solvers_dict[SolverType.LINEAR_OPF.value] = SolverType.LINEAR_OPF
        self.lp_solvers_dict[SolverType.NONLINEAR_OPF.value] = SolverType.NONLINEAR_OPF
        self.lp_solvers_dict[SolverType.SIMPLE_OPF.value] = SolverType.SIMPLE_OPF
        self.ui.lpf_solver_comboBox.setModel(gf.get_list_model(list(self.lp_solvers_dict.keys())))

        # ips solvers dictionary
        self.ips_solvers_dict = OrderedDict()
        self.ips_solvers_dict[SolverType.NR.value] = SolverType.NR
        self.ui.ips_method_comboBox.setModel(gf.get_list_model(list(self.ips_solvers_dict.keys())))

        # the MIP combobox models assigning is done in modify_ui_options_according_to_the_engine
        self.mip_solvers_dict = OrderedDict()
        self.mip_solvers_dict[MIPSolvers.CBC.value] = MIPSolvers.CBC
        self.mip_solvers_dict[MIPSolvers.HIGHS.value] = MIPSolvers.HIGHS
        self.mip_solvers_dict[MIPSolvers.GLOP.value] = MIPSolvers.GLOP
        self.mip_solvers_dict[MIPSolvers.SCIP.value] = MIPSolvers.SCIP
        self.mip_solvers_dict[MIPSolvers.CPLEX.value] = MIPSolvers.CPLEX
        self.mip_solvers_dict[MIPSolvers.GUROBI.value] = MIPSolvers.GUROBI
        self.mip_solvers_dict[MIPSolvers.XPRESS.value] = MIPSolvers.XPRESS

        # branch types for reduction
        mdl = gf.get_list_model([DeviceType.LineDevice.value,
                                 DeviceType.SwitchDevice.value], checks=True)
        self.ui.removeByTypeListView.setModel(mdl)

        # OPF grouping modes
        self.opf_time_groups = OrderedDict()
        self.opf_time_groups[TimeGrouping.NoGrouping.value] = TimeGrouping.NoGrouping
        self.opf_time_groups[TimeGrouping.Monthly.value] = TimeGrouping.Monthly
        self.opf_time_groups[TimeGrouping.Weekly.value] = TimeGrouping.Weekly
        self.opf_time_groups[TimeGrouping.Daily.value] = TimeGrouping.Daily
        self.opf_time_groups[TimeGrouping.Hourly.value] = TimeGrouping.Hourly
        self.ui.opf_time_grouping_comboBox.setModel(gf.get_list_model(list(self.opf_time_groups.keys())))

        self.opf_zonal_groups = OrderedDict()
        self.opf_zonal_groups[ZonalGrouping.NoGrouping.value] = ZonalGrouping.NoGrouping
        # self.opf_zonal_groups[ZonalGrouping.Area.value] = ZonalGrouping.Area
        self.opf_zonal_groups[ZonalGrouping.All.value] = ZonalGrouping.All
        self.ui.opfZonalGroupByComboBox.setModel(gf.get_list_model(list(self.opf_zonal_groups.keys())))

        # voltage collapse mode (full, nose)
        self.ui.vc_stop_at_comboBox.setModel(gf.get_list_model([sim.CpfStopAt.Nose.value,
                                                                sim.CpfStopAt.ExtraOverloads.value]))
        self.ui.vc_stop_at_comboBox.setCurrentIndex(0)

        # reactive power controls
        self.contingency_engines_dict = OrderedDict()
        self.contingency_engines_dict[ContingencyMethod.PowerFlow.value] = ContingencyMethod.PowerFlow
        self.contingency_engines_dict[ContingencyMethod.OptimalPowerFlow.value] = ContingencyMethod.OptimalPowerFlow
        self.contingency_engines_dict[ContingencyMethod.PTDF.value] = ContingencyMethod.PTDF
        self.ui.contingencyEngineComboBox.setModel(gf.get_list_model(list(self.contingency_engines_dict.keys())))

        # list of stochastic power flow methods
        self.stochastic_pf_methods_dict = OrderedDict()
        self.stochastic_pf_methods_dict[
            sim.StochasticPowerFlowType.LatinHypercube.value] = sim.StochasticPowerFlowType.LatinHypercube
        self.stochastic_pf_methods_dict[
            sim.StochasticPowerFlowType.MonteCarlo.value] = sim.StochasticPowerFlowType.MonteCarlo
        mdl = gf.get_list_model(list(self.stochastic_pf_methods_dict.keys()))
        self.ui.stochastic_pf_method_comboBox.setModel(mdl)

        # investment evaluation methods
        self.investment_evaluation_method_dict = OrderedDict()
        self.investment_evaluation_method_dict[
            InvestmentEvaluationMethod.Independent.value] = InvestmentEvaluationMethod.Independent
        self.investment_evaluation_method_dict[
            InvestmentEvaluationMethod.Hyperopt.value] = InvestmentEvaluationMethod.Hyperopt
        self.investment_evaluation_method_dict[
            InvestmentEvaluationMethod.MVRSM.value] = InvestmentEvaluationMethod.MVRSM
        self.investment_evaluation_method_dict[
            InvestmentEvaluationMethod.MVRSM_multi.value] = InvestmentEvaluationMethod.MVRSM_multi
        lst = list(self.investment_evaluation_method_dict.keys())
        self.ui.investment_evaluation_method_ComboBox.setModel(gf.get_list_model(lst))

        # ptdf grouping modes
        self.ptdf_group_modes = OrderedDict()

        # dictionaries for available results
        self.available_results_dict: Union[Dict[str, Dict[str, ResultTypes]], None] = dict()

        self.buses_for_storage: Union[List[dev.Bus], None] = None

        # --------------------------------------------------------------------------------------------------------------

        self.ui.actionPower_flow.triggered.connect(self.power_flow_dispatcher)
        self.ui.actionShort_Circuit.triggered.connect(self.run_short_circuit)
        self.ui.actionVoltage_stability.triggered.connect(self.run_continuation_power_flow)
        self.ui.actionPower_Flow_Time_series.triggered.connect(self.run_power_flow_time_series)
        self.ui.actionPower_flow_Stochastic.triggered.connect(self.run_stochastic)
        self.ui.actionOPF.triggered.connect(self.optimal_power_flow_dispatcher)
        self.ui.actionOPF_time_series.triggered.connect(self.run_opf_time_series)
        self.ui.actionOptimal_Net_Transfer_Capacity.triggered.connect(self.optimal_ntc_opf_dispatcher)
        self.ui.actionOptimal_Net_Transfer_Capacity_Time_Series.triggered.connect(self.run_opf_ntc_ts)
        self.ui.actionInputs_analysis.triggered.connect(self.run_inputs_analysis)
        self.ui.actionStorage_location_suggestion.triggered.connect(self.storage_location)
        self.ui.actionLinearAnalysis.triggered.connect(self.linear_pf_dispatcher)
        self.ui.actionContingency_analysis.triggered.connect(self.contingencies_dispatcher)
        self.ui.actionOTDF_time_series.triggered.connect(self.run_contingency_analysis_ts)
        self.ui.actionATC.triggered.connect(self.optimal_ntc_dispatcher)
        self.ui.actionATC_Time_Series.triggered.connect(self.run_available_transfer_capacity_ts)
        self.ui.actionPTDF_time_series.triggered.connect(self.run_linear_analysis_ts)
        self.ui.actionClustering.triggered.connect(self.run_clustering)
        self.ui.actionSigma_analysis.triggered.connect(self.run_sigma_analysis)
        self.ui.actionFind_node_groups.triggered.connect(self.run_find_node_groups)
        self.ui.actionFuse_devices.triggered.connect(self.fuse_devices)
        self.ui.actionInvestments_evaluation.triggered.connect(self.run_investments_evaluation)
        self.ui.actionProcess_topology.triggered.connect(self.run_topology_processor)
        self.ui.actionUse_clustering.triggered.connect(self.activate_clustering)

        # combobox change
        self.ui.engineComboBox.currentTextChanged.connect(self.modify_ui_options_according_to_the_engine)

    def get_simulations(self):
        """
        Get all threads that have to do with simulation
        :return: list of simulation threads
        """

        all_threads = list(self.session.drivers.values())

        # # set the threads so that the diagram scene objects can plot them
        for diagram in self.diagram_widgets_list:
            if isinstance(diagram, DiagramEditorWidget):
                diagram.set_results_to_plot(all_threads)

        return all_threads

    def get_available_results(self):
        """
        Get a list of all the available results' objects
        :return: list[object]
        """
        lst = list()

        for drv in self.get_simulations():
            if drv is not None:
                if hasattr(drv, 'results'):
                    if drv.results is not None:
                        lst.append(drv)

        return lst

    def get_time_indices(self) -> np.ndarray:
        """
        Get an array of indices of the time steps selected within the start-end interval
        :return: np.array[int]
        """

        start = self.get_simulation_start()
        end = self.get_simulation_end()

        return np.arange(start, end + 1)

    def modify_ui_options_according_to_the_engine(self) -> None:
        """
        Change the UI depending on the engine options
        :return:
        """
        eng = self.get_preferred_engine()

        if eng == EngineType.NewtonPA:
            self.ui.opfUnitCommitmentCheckBox.setVisible(True)

            # add the AC_OPF option
            self.lp_solvers_dict = OrderedDict()
            self.lp_solvers_dict[SolverType.LINEAR_OPF.value] = SolverType.LINEAR_OPF
            self.lp_solvers_dict[SolverType.NONLINEAR_OPF.value] = SolverType.NONLINEAR_OPF
            self.lp_solvers_dict[SolverType.SIMPLE_OPF.value] = SolverType.SIMPLE_OPF
            self.ui.lpf_solver_comboBox.setModel(gf.get_list_model(list(self.lp_solvers_dict.keys())))

            # Power Flow Methods
            self.solvers_dict[SolverType.NR.value] = SolverType.NR
            self.solvers_dict[SolverType.NRI.value] = SolverType.NRI
            self.solvers_dict[SolverType.IWAMOTO.value] = SolverType.IWAMOTO
            self.solvers_dict[SolverType.LM.value] = SolverType.LM
            self.solvers_dict[SolverType.FASTDECOUPLED.value] = SolverType.FASTDECOUPLED
            self.solvers_dict[SolverType.HELM.value] = SolverType.HELM
            self.solvers_dict[SolverType.GAUSS.value] = SolverType.GAUSS
            self.solvers_dict[SolverType.LACPF.value] = SolverType.LACPF
            self.solvers_dict[SolverType.DC.value] = SolverType.DC

            self.ui.solver_comboBox.setModel(gf.get_list_model(list(self.solvers_dict.keys())))
            self.ui.solver_comboBox.setCurrentIndex(0)

            mip_solvers = get_newton_mip_solvers_list()
            self.ui.mip_solver_comboBox.setModel(gf.get_list_model(mip_solvers))

        elif eng == EngineType.GridCal:
            self.ui.opfUnitCommitmentCheckBox.setVisible(True)

            # no AC opf option
            self.lp_solvers_dict = OrderedDict()
            self.lp_solvers_dict[SolverType.LINEAR_OPF.value] = SolverType.LINEAR_OPF
            self.lp_solvers_dict[SolverType.NONLINEAR_OPF.value] = SolverType.NONLINEAR_OPF
            self.lp_solvers_dict[SolverType.SIMPLE_OPF.value] = SolverType.SIMPLE_OPF
            self.ui.lpf_solver_comboBox.setModel(gf.get_list_model(list(self.lp_solvers_dict.keys())))

            # Power Flow Methods
            self.solvers_dict = OrderedDict()
            self.solvers_dict[SolverType.NR.value] = SolverType.NR
            self.solvers_dict[SolverType.NRI.value] = SolverType.NRI
            self.solvers_dict[SolverType.IWAMOTO.value] = SolverType.IWAMOTO
            self.solvers_dict[SolverType.LM.value] = SolverType.LM
            self.solvers_dict[SolverType.FASTDECOUPLED.value] = SolverType.FASTDECOUPLED
            self.solvers_dict[SolverType.HELM.value] = SolverType.HELM
            self.solvers_dict[SolverType.GAUSS.value] = SolverType.GAUSS
            self.solvers_dict[SolverType.LACPF.value] = SolverType.LACPF
            self.solvers_dict[SolverType.DC.value] = SolverType.DC

            self.ui.solver_comboBox.setModel(gf.get_list_model(list(self.solvers_dict.keys())))
            self.ui.solver_comboBox.setCurrentIndex(0)

            # MIP solvers
            mip_solvers = get_available_mip_solvers()
            self.ui.mip_solver_comboBox.setModel(gf.get_list_model(mip_solvers))

        elif eng == EngineType.Bentayga:
            self.ui.opfUnitCommitmentCheckBox.setVisible(False)

            # no AC opf option
            self.lp_solvers_dict = OrderedDict()
            self.lp_solvers_dict[SolverType.LINEAR_OPF.value] = SolverType.LINEAR_OPF
            self.lp_solvers_dict[SolverType.SIMPLE_OPF.value] = SolverType.SIMPLE_OPF
            self.ui.lpf_solver_comboBox.setModel(gf.get_list_model(list(self.lp_solvers_dict.keys())))

            # Power Flow Methods
            self.solvers_dict = OrderedDict()
            self.solvers_dict[SolverType.NR.value] = SolverType.NR
            self.solvers_dict[SolverType.NRI.value] = SolverType.NRI
            self.solvers_dict[SolverType.IWAMOTO.value] = SolverType.IWAMOTO
            self.solvers_dict[SolverType.LM.value] = SolverType.LM
            self.solvers_dict[SolverType.FASTDECOUPLED.value] = SolverType.FASTDECOUPLED
            self.solvers_dict[SolverType.HELM.value] = SolverType.HELM
            self.solvers_dict[SolverType.GAUSS.value] = SolverType.GAUSS
            self.solvers_dict[SolverType.LACPF.value] = SolverType.LACPF
            self.solvers_dict[SolverType.DC.value] = SolverType.DC

            self.ui.solver_comboBox.setModel(gf.get_list_model(list(self.solvers_dict.keys())))
            self.ui.solver_comboBox.setCurrentIndex(0)

        elif eng == EngineType.PGM:
            self.ui.opfUnitCommitmentCheckBox.setVisible(False)

            # no AC opf option
            self.lp_solvers_dict = OrderedDict()
            self.lp_solvers_dict[SolverType.LINEAR_OPF.value] = SolverType.LINEAR_OPF
            self.lp_solvers_dict[SolverType.SIMPLE_OPF.value] = SolverType.SIMPLE_OPF
            self.ui.lpf_solver_comboBox.setModel(gf.get_list_model(list(self.lp_solvers_dict.keys())))

            # Power Flow Methods
            self.solvers_dict = OrderedDict()
            self.solvers_dict[SolverType.NR.value] = SolverType.NR
            self.solvers_dict[SolverType.BFS.value] = SolverType.BFS
            self.solvers_dict[SolverType.BFS_linear.value] = SolverType.BFS_linear
            self.solvers_dict[SolverType.Constant_Impedance_linear.value] = SolverType.Constant_Impedance_linear

            self.ui.solver_comboBox.setModel(gf.get_list_model(list(self.solvers_dict.keys())))
            self.ui.solver_comboBox.setCurrentIndex(0)

        else:
            raise Exception('Unsupported engine' + str(eng.value))

    def valid_time_series(self):
        """
        Check if there are valid time series
        """
        if len(self.circuit.buses) > 0:
            if self.circuit.time_profile is not None:
                if len(self.circuit.time_profile) > 0:
                    return True
        return False

    def add_simulation(self, val: sim.SimulationTypes):
        """
        Add a simulation to the simulations list
        :param val: simulation type
        """
        self.stuff_running_now.append(val)

    def remove_simulation(self, val: sim.SimulationTypes):
        """
        Remove a simulation from the simulations list
        :param val: simulation type
        """
        if val in self.stuff_running_now:
            self.stuff_running_now.remove(val)

    def clear_results(self):
        """
        Clear the results tab
        """
        self.session.clear()

        self.buses_for_storage = None

        self.calculation_inputs_to_display = None
        self.ui.simulation_data_island_comboBox.clear()

        self.available_results_dict = dict()
        self.ui.resultsTableView.setModel(None)
        self.ui.available_results_to_color_comboBox.model().clear()
        self.ui.results_treeView.setModel(None)

        self.setup_time_sliders()

        self.ui.simulationDataStructureTableView.setModel(None)
        self.ui.profiles_tableView.setModel(None)
        self.ui.resultsTableView.setModel(None)
        self.ui.dataStructureTableView.setModel(None)
        self.ui.resultsLogsTreeView.setModel(None)

        self.ui.sbase_doubleSpinBox.setValue(self.circuit.Sbase)
        self.ui.fbase_doubleSpinBox.setValue(self.circuit.fBase)
        self.ui.model_version_label.setText('Model v. ' + str(self.circuit.model_version))
        self.ui.user_name_label.setText('User: ' + str(self.circuit.user_name))
        if self.open_file_thread_object is not None:
            if isinstance(self.open_file_thread_object.file_name, str):
                self.ui.file_information_label.setText(self.open_file_thread_object.file_name)

        self.ui.units_label.setText("")

    def update_available_results(self) -> None:
        """
        Update the results that are displayed in the results tab
        """

        self.available_results_dict = dict()
        self.available_results_steps_dict = dict()

        # clear results lists
        self.ui.results_treeView.setModel(None)

        available_results = self.get_available_results()
        max_steps = 0
        d = dict()
        lst = list()
        for driver in available_results:
            name = driver.tpe.value
            lst.append(name)
            d[name] = driver.results.get_name_tree()
            self.available_results_dict[name] = driver.results.get_name_to_results_type_dict()
            steps = driver.get_steps()
            self.available_results_steps_dict[name] = steps
            if len(steps) > max_steps:
                max_steps = len(steps)

        icons = {
            SimulationTypes.PowerFlow_run.value: ':/Icons/icons/pf',
            SimulationTypes.TimeSeries_run.value: ':/Icons/icons/pf_ts.svg',
            SimulationTypes.ClusteringTimeSeries_run.value: ':/Icons/icons/pf_ts_cluster.svg',
            SimulationTypes.OPF_run.value: ':/Icons/icons/dcopf.svg',
            SimulationTypes.OPFTimeSeries_run.value: ':/Icons/icons/dcopf_ts.svg',
            SimulationTypes.ShortCircuit_run.value: ':/Icons/icons/short_circuit.svg',
            SimulationTypes.LinearAnalysis_run.value: ':/Icons/icons/ptdf.svg',
            SimulationTypes.LinearAnalysis_TS_run.value: ':/Icons/icons/ptdf_ts.svg',
            SimulationTypes.SigmaAnalysis_run.value: ':/Icons/icons/sigma.svg',
            SimulationTypes.StochasticPowerFlow.value: ':/Icons/icons/stochastic_power_flow.svg',
            SimulationTypes.ContingencyAnalysis_run.value: ':/Icons/icons/otdf.svg',
            SimulationTypes.ContingencyAnalysisTS_run.value: ':/Icons/icons/otdf_ts.svg',
            SimulationTypes.NetTransferCapacity_run.value: ':/Icons/icons/atc.svg',
            SimulationTypes.NetTransferCapacityTS_run.value: ':/Icons/icons/atc_ts.svg',
            SimulationTypes.OptimalNetTransferCapacityTimeSeries_run.value: ':/Icons/icons/ntc_opf_ts.svg',
            SimulationTypes.InputsAnalysis_run.value: ':/Icons/icons/stats.svg',
            SimulationTypes.NodeGrouping_run.value: ':/Icons/icons/ml.svg',
            SimulationTypes.ContinuationPowerFlow_run.value: ':/Icons/icons/continuation_power_flow.svg',
            SimulationTypes.ClusteringAnalysis_run.value: ':/Icons/icons/clustering.svg',
            SimulationTypes.InvestmestsEvaluation_run.value: ':/Icons/icons/expansion_planning.svg',
        }

        self.ui.results_treeView.setModel(gf.get_tree_model(d, 'Results', icons=icons))
        lst.reverse()  # this is to show the latest simulation first
        mdl = gf.get_list_model(lst)
        self.ui.available_results_to_color_comboBox.setModel(mdl)
        self.ui.resultsTableView.setModel(None)
        self.ui.resultsLogsTreeView.setModel(None)

    def get_compatible_areas_from_to(self) -> Tuple[
        bool,
        List[Tuple[int, dev.Bus]],
        List[Tuple[int, dev.Bus]],
        List[Tuple[int, object, float]],
        List[Tuple[int, object, float]],
        List[dev.Area], List[dev.Area]]:
        """
        Get the lists that help defining the inter area objects
        :return: success?,
                 list of tuples bus idx, Bus in the areas from,
                 list of tuples bus idx, Bus in the areas to,
                 List of inter area Branches (branch index, branch object, flow sense w.r.t the area exchange),
                 List of inter area HVDC (branch index, branch object, flow sense w.r.t the area exchange),
                 List of areas from,
                 List of areas to
        """
        areas_from_idx = gf.get_checked_indices(self.ui.areaFromListView.model())
        areas_to_idx = gf.get_checked_indices(self.ui.areaToListView.model())
        areas_from = [self.circuit.areas[i] for i in areas_from_idx]
        areas_to = [self.circuit.areas[i] for i in areas_to_idx]

        for a1 in areas_from:
            if a1 in areas_to:
                error_msg("The area from '{0}' is in the list of areas to. This cannot be.".format(a1.name),
                          'Incompatible areas')
                return False, [], [], [], [], [], []
        for a2 in areas_to:
            if a2 in areas_from:
                error_msg("The area to '{0}' is in the list of areas from. This cannot be.".format(a2.name),
                          'Incompatible areas')
                return False, [], [], [], [], [], []

        lst_from = self.circuit.get_areas_buses(areas_from)
        lst_to = self.circuit.get_areas_buses(areas_to)
        lst_br = self.circuit.get_inter_areas_branches(areas_from, areas_to)
        lst_br_hvdc = self.circuit.get_inter_areas_hvdc_branches(areas_from, areas_to)
        return True, lst_from, lst_to, lst_br, lst_br_hvdc, areas_from, areas_to

    def get_selected_power_flow_options(self):
        """
        Gather power flow run options
        :return:
        """
        solver_type = self.solvers_dict[self.ui.solver_comboBox.currentText()]

        q_control_mode = self.q_control_modes_dict[self.ui.reactive_power_control_mode_comboBox.currentText()]
        q_steepness_factor = 1.0
        taps_control_mode = self.taps_control_modes_dict[self.ui.taps_control_mode_comboBox.currentText()]

        verbose = self.ui.verbositySpinBox.value()

        exponent = self.ui.tolerance_spinBox.value()
        tolerance = 1.0 / (10.0 ** exponent)

        max_iter = self.ui.max_iterations_spinBox.value()

        max_outer_iter = 1000  # not used anymore

        dispatch_storage = False
        mu = self.ui.muSpinBox.value()

        if self.ui.helm_retry_checkBox.isChecked():
            retry_with_other_methods = True  # to set a value
        else:
            retry_with_other_methods = False

        if self.ui.apply_impedance_tolerances_checkBox.isChecked():
            branch_impedance_tolerance_mode = BranchImpedanceMode.Upper
        else:
            branch_impedance_tolerance_mode = BranchImpedanceMode.Specified

        temp_correction = self.ui.temperature_correction_checkBox.isChecked()

        distributed_slack = self.ui.distributed_slack_checkBox.isChecked()

        ignore_single_node_islands = self.ui.ignore_single_node_islands_checkBox.isChecked()

        use_stored_guess = self.ui.use_voltage_guess_checkBox.isChecked()

        override_branch_controls = self.ui.override_branch_controls_checkBox.isChecked()

        generate_report = self.ui.addPowerFlowReportCheckBox.isChecked()

        ops = sim.PowerFlowOptions(solver_type=solver_type,
                                   retry_with_other_methods=retry_with_other_methods,
                                   verbose=verbose,
                                   initialize_with_existing_solution=use_stored_guess,
                                   tolerance=tolerance,
                                   max_iter=max_iter,
                                   max_outer_loop_iter=max_outer_iter,
                                   control_q=q_control_mode,
                                   multi_core=False,
                                   dispatch_storage=dispatch_storage,
                                   control_taps=taps_control_mode,
                                   apply_temperature_correction=temp_correction,
                                   branch_impedance_tolerance_mode=branch_impedance_tolerance_mode,
                                   q_steepness_factor=q_steepness_factor,
                                   distributed_slack=distributed_slack,
                                   ignore_single_node_islands=ignore_single_node_islands,
                                   trust_radius=mu,
                                   use_stored_guess=use_stored_guess,
                                   override_branch_controls=override_branch_controls,
                                   generate_report=generate_report)

        return ops

    def get_opf_results(self, use_opf: bool) -> sim.OptimalPowerFlowResults:
        """
        Get the current OPF results
        :param use_opf:
        :return:
        """
        if use_opf:

            drv, results = self.session.get_driver_results(sim.SimulationTypes.OPF_run)

            if drv is not None:
                if results is not None:
                    opf_results = results
                else:
                    warning_msg('There are no OPF results, '
                                'therefore this operation will not use OPF information.')
                    self.ui.actionOpf_to_Power_flow.setChecked(False)
                    opf_results = None
            else:

                # try the OPF-NTC...
                drv, results = self.session.get_driver_results(sim.SimulationTypes.OPF_NTC_run)

                if drv is not None:
                    if results is not None:
                        opf_results = results
                    else:
                        warning_msg('There are no OPF-NTC results, '
                                    'therefore this operation will not use OPF information.')
                        self.ui.actionOpf_to_Power_flow.setChecked(False)
                        opf_results = None
                else:
                    warning_msg('There are no OPF results, '
                                'therefore this operation will not use OPF information.')
                    self.ui.actionOpf_to_Power_flow.setChecked(False)
                    opf_results = None
        else:
            opf_results = None

        return opf_results

    def get_opf_ts_results(self, use_opf: bool) -> sim.OptimalPowerFlowTimeSeriesResults:
        """
        Get the current OPF time series results
        :param use_opf: use the OPF?
        :return:
        """
        if use_opf:

            drv, opf_time_series_results = self.session.get_driver_results(SimulationTypes.OPFTimeSeries_run)

            if opf_time_series_results is None:
                if use_opf:
                    info_msg('There are no OPF time series, '
                             'therefore this operation will not use OPF information.')
                    self.ui.actionOpf_to_Power_flow.setChecked(False)

        else:
            opf_time_series_results = None

        return opf_time_series_results

    def ts_flag(self) -> bool:
        """
        Is the time series flag enabled?
        :return:
        """
        return self.ui.actionactivate_time_series.isChecked()

    def power_flow_dispatcher(self):
        """
        Dispatch the power flow action
        :return:
        """
        if self.ts_flag():
            self.run_power_flow_time_series()
        else:
            self.run_power_flow()

    def optimal_power_flow_dispatcher(self):
        """
        Dispatch the optimal power flow action
        :return:
        """
        if self.ts_flag():
            self.run_opf_time_series()
        else:
            self.run_opf()

    def optimal_ntc_dispatcher(self):
        """
        Dispatch the NTC action
        :return:
        """
        if self.ts_flag():
            self.run_available_transfer_capacity_ts()
        else:
            self.run_available_transfer_capacity()

    def optimal_ntc_opf_dispatcher(self):
        """
        Dispatch the optimal NTC action
        :return:
        """
        if self.ts_flag():
            self.run_opf_ntc_ts()
        else:
            self.run_opf_ntc()

    def linear_pf_dispatcher(self):
        """
        Dispatch the linear power flow action
        :return:
        """
        if self.ts_flag():
            self.run_linear_analysis_ts()
        else:
            self.run_linear_analysis()

    def contingencies_dispatcher(self):
        """
        Dispatch the contingencies action
        :return:
        """
        if self.ts_flag():
            self.run_contingency_analysis_ts()
        else:
            self.run_contingency_analysis()

    def run_power_flow(self):
        """
        Run a power flow simulation
        :return:
        """
        if self.circuit.get_bus_number():

            if not self.session.is_this_running(sim.SimulationTypes.PowerFlow_run):

                self.LOCK()

                self.add_simulation(sim.SimulationTypes.PowerFlow_run)

                self.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()

                # get the power flow options from the GUI
                options = self.get_selected_power_flow_options()

                # compute the automatic precision
                if self.ui.auto_precision_checkBox.isChecked():

                    options.tolerance, tol_idx = self.circuit.get_automatic_precision()

                    if tol_idx > 12:
                        tol_idx = 12

                    self.ui.tolerance_spinBox.setValue(tol_idx)

                opf_results = self.get_opf_results(use_opf=self.ui.actionOpf_to_Power_flow.isChecked())

                self.ui.progress_label.setText('Running power flow...')
                QtGui.QGuiApplication.processEvents()
                # set power flow object instance
                engine = self.get_preferred_engine()
                drv = sim.PowerFlowDriver(self.circuit, options, opf_results, engine=engine)

                self.session.run(drv,
                                 post_func=self.post_power_flow,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                warning_msg('Another simulation of the same type is running...')
        else:
            pass

    def post_power_flow(self):
        """
        Action performed after the power flow.
        Returns:

        """
        # update the results in the circuit structures

        drv, results = self.session.get_driver_results(sim.SimulationTypes.PowerFlow_run)

        if results is not None:
            self.ui.progress_label.setText('Colouring power flow results in the grid...')
            # QtGui.QGuiApplication.processEvents()

            self.remove_simulation(sim.SimulationTypes.PowerFlow_run)

            self.update_available_results()

            self.colour_diagrams()

        else:
            warning_msg('There are no power flow results.\nIs there any slack bus or generator?', 'Power flow')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_short_circuit(self):
        """
        Run a short circuit simulation
        The short circuit simulation must be performed after a power flow simulation
        without any load or topology change
        :return:
        """
        if len(self.circuit.buses) > 0:
            if not self.session.is_this_running(sim.SimulationTypes.ShortCircuit_run):

                pf_drv, pf_results = self.session.get_driver_results(sim.SimulationTypes.PowerFlow_run)

                if pf_results is not None:

                    # Since we must run this study in the same conditions as
                    # the last power flow, no compilation is needed

                    # get the short circuit selected buses
                    sel_buses = list()
                    self_short_circuit_types = list()

                    for diagram_widget in self.diagram_widgets_list:

                        if isinstance(diagram_widget, DiagramEditorWidget):

                            for i, bus, graphic_object in diagram_widget.get_buses():
                                if graphic_object.any_short_circuit():
                                    sel_buses.append(i)
                                    self_short_circuit_types.append(graphic_object.sc_type)

                    if len(sel_buses) > 1:
                        error_msg("GridCal only supports one short circuit bus at the time", "Short circuit")
                        return

                    if len(sel_buses) == 0:
                        warning_msg('You need to enable some buses for short circuit.'
                                    + '\nEnable them by right click, and selecting on the context menu.')
                    else:
                        self.add_simulation(sim.SimulationTypes.ShortCircuit_run)

                        self.LOCK()

                        if self.ui.apply_impedance_tolerances_checkBox.isChecked():
                            branch_impedance_tolerance_mode = BranchImpedanceMode.Lower
                        else:
                            branch_impedance_tolerance_mode = BranchImpedanceMode.Specified

                        # get the power flow options from the GUI
                        sc_options = sim.ShortCircuitOptions(bus_index=sel_buses[0],
                                                             fault_type=self_short_circuit_types[0],
                                                             branch_impedance_tolerance_mode=branch_impedance_tolerance_mode)

                        pf_options = self.get_selected_power_flow_options()

                        drv = sim.ShortCircuitDriver(grid=self.circuit,
                                                     options=sc_options,
                                                     pf_options=pf_options,
                                                     pf_results=pf_results)
                        self.session.run(drv,
                                         post_func=self.post_short_circuit,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)

                else:
                    info_msg('Run a power flow simulation first.\n'
                             'The results are needed to initialize this simulation.')
            else:
                warning_msg('Another short circuit is being executed now...')
        else:
            pass

    def post_short_circuit(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        # update the results in the circuit structures
        drv, results = self.session.get_driver_results(sim.SimulationTypes.ShortCircuit_run)
        self.remove_simulation(sim.SimulationTypes.ShortCircuit_run)
        if results is not None:

            self.ui.progress_label.setText('Colouring short circuit results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()

            self.colour_diagrams()

        else:
            error_msg('Something went wrong, There are no power short circuit results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def get_linear_options(self) -> sim.LinearAnalysisOptions:
        """
        Get the LinearAnalysisOptions defined by the GUI
        :return: LinearAnalysisOptions
        """
        options = sim.LinearAnalysisOptions(
            distribute_slack=self.ui.ptdf_distributed_slack_checkBox.isChecked(),
            correct_values=self.ui.ptdf_correct_nonsense_values_checkBox.isChecked(),
            ptdf_threshold=self.ui.ptdf_threshold_doubleSpinBox.value(),
            lodf_threshold=self.ui.lodf_threshold_doubleSpinBox.value()
        )

        return options

    def run_linear_analysis(self):
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if len(self.circuit.buses) > 0:
            if not self.session.is_this_running(sim.SimulationTypes.LinearAnalysis_run):

                self.add_simulation(sim.SimulationTypes.LinearAnalysis_run)

                self.LOCK()

                opf_results = self.get_opf_results(use_opf=self.ui.actionOpf_to_Power_flow.isChecked())

                engine = self.get_preferred_engine()
                drv = sim.LinearAnalysisDriver(grid=self.circuit,
                                               options=self.get_linear_options(),
                                               engine=engine,
                                               opf_results=opf_results)

                self.session.run(drv,
                                 post_func=self.post_linear_analysis,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)
            else:
                warning_msg('Another PTDF is being executed now...')
        else:
            pass

    def post_linear_analysis(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.LinearAnalysis_run)

        self.remove_simulation(sim.SimulationTypes.LinearAnalysis_run)

        # update the results in the circuit structures
        # if not drv.__cancel__:
        if results is not None:

            self.ui.progress_label.setText('Colouring PTDF results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()
            self.colour_diagrams()
        else:
            error_msg('Something went wrong, There are no PTDF results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_linear_analysis_ts(self):
        """
        Run PTDF time series simulation
        """
        if len(self.circuit.buses) > 0:
            if self.valid_time_series():
                if not self.session.is_this_running(sim.SimulationTypes.LinearAnalysis_TS_run):

                    self.add_simulation(sim.SimulationTypes.LinearAnalysis_TS_run)
                    self.LOCK()

                    opf_time_series_results = self.get_opf_ts_results(
                        use_opf=self.ui.actionOpf_to_Power_flow.isChecked()
                    )

                    drv = sim.LinearAnalysisTimeSeriesDriver(grid=self.circuit,
                                                             options=self.get_linear_options(),
                                                             time_indices=self.get_time_indices(),
                                                             clustering_results=self.get_clustering_results(),
                                                             opf_time_series_results=opf_time_series_results)

                    self.session.run(drv,
                                     post_func=self.post_linear_analysis_ts,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                else:
                    warning_msg('Another PTDF time series is being executed now...')
            else:
                warning_msg('There are no time series...')

    def post_linear_analysis_ts(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.LinearAnalysis_TS_run)
        self.remove_simulation(sim.SimulationTypes.LinearAnalysis_TS_run)

        # update the results in the circuit structures
        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            self.ui.progress_label.setText('Colouring PTDF results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()

            if results.S.shape[0] > 0:
                self.colour_diagrams()
            else:
                info_msg('Cannot colour because the PTDF results have zero time steps :/')

        else:
            error_msg('Something went wrong, There are no PTDF Time series results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def get_contingency_options(self) -> sim.ContingencyAnalysisOptions:
        """

        :return:
        """
        pf_options = self.get_selected_power_flow_options()

        options = sim.ContingencyAnalysisOptions(
            use_provided_flows=False,
            Pf=None,
            pf_options=pf_options,
            lin_options=self.get_linear_options(),
            use_srap=self.ui.use_srap_checkBox.isChecked(),
            srap_max_power=self.ui.srap_limit_doubleSpinBox.value(),
            srap_top_n=self.ui.srap_top_n_SpinBox.value(),
            srap_deadband=self.ui.srap_deadband_doubleSpinBox.value(),
            srap_rever_to_nominal_rating=self.ui.srap_revert_to_nominal_rating_checkBox.isChecked(),
            detailed_massive_report=self.ui.contingency_detailed_massive_report_checkBox.isChecked(),
            contingency_deadband=self.ui.contingency_deadband_SpinBox.value(),
            engine=self.contingency_engines_dict[self.ui.contingencyEngineComboBox.currentText()]
        )

        return options

    def run_contingency_analysis(self):
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if len(self.circuit.buses) > 0:

            if len(self.circuit.contingency_groups) > 0:

                if not self.session.is_this_running(sim.SimulationTypes.ContingencyAnalysis_run):

                    self.add_simulation(sim.SimulationTypes.ContingencyAnalysis_run)

                    self.LOCK()

                    linear_multiple_contingencies = sim.LinearMultiContingencies(grid=self.circuit)

                    drv = sim.ContingencyAnalysisDriver(grid=self.circuit,
                                                        options=self.get_contingency_options(),
                                                        linear_multiple_contingencies=linear_multiple_contingencies,
                                                        engine=self.get_preferred_engine())

                    self.session.run(drv,
                                     post_func=self.post_contingency_analysis,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                else:
                    warning_msg('Another contingency analysis is being executed now...')

            else:
                warning_msg('There are no contingency groups declared...')
        else:
            pass

    def post_contingency_analysis(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.ContingencyAnalysis_run)
        self.remove_simulation(sim.SimulationTypes.ContingencyAnalysis_run)

        # update the results in the circuit structures
        # if not drv.__cancel__:
        if results is not None:

            self.ui.progress_label.setText('Colouring contingency analysis results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()

            self.colour_diagrams()
        else:
            error_msg('Something went wrong, There are no contingency analysis results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_contingency_analysis_ts(self) -> None:
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if len(self.circuit.buses) > 0:

            if len(self.circuit.contingency_groups) > 0:

                if self.valid_time_series():
                    if not self.session.is_this_running(sim.SimulationTypes.ContingencyAnalysisTS_run):

                        self.add_simulation(sim.SimulationTypes.ContingencyAnalysisTS_run)

                        self.LOCK()

                        drv = sim.ContingencyAnalysisTimeSeries(grid=self.circuit,
                                                                options=self.get_contingency_options(),
                                                                time_indices=self.get_time_indices(),
                                                                clustering_results=self.get_clustering_results(),
                                                                engine=self.get_preferred_engine())

                        self.session.run(drv,
                                         post_func=self.post_contingency_analysis_ts,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)
                    else:
                        warning_msg('Another LODF is being executed now...')
                else:
                    warning_msg('There are no time series...')

            else:
                warning_msg('There are no contingency groups declared...')

        else:
            pass

    def post_contingency_analysis_ts(self) -> None:
        """
        Action performed after the short circuit.
        Returns:

        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.ContingencyAnalysisTS_run)
        self.remove_simulation(sim.SimulationTypes.ContingencyAnalysisTS_run)

        # update the results in the circuit structures
        # if not drv.__cancel__:
        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            self.ui.progress_label.setText('Colouring results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()

            self.colour_diagrams()
        else:
            error_msg('Something went wrong, There are no contingency time series results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_available_transfer_capacity(self):
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if len(self.circuit.buses) > 0:

            if not self.session.is_this_running(sim.SimulationTypes.NetTransferCapacity_run):
                distributed_slack = self.ui.distributed_slack_checkBox.isChecked()
                dT = 1.0
                threshold = self.ui.atcThresholdSpinBox.value()
                max_report_elements = 5  # TODO: self.ui.ntcReportLimitingElementsSpinBox.value()
                # available transfer capacity inter areas
                compatible_areas, lst_from, lst_to, lst_br, \
                    lst_hvdc_br, areas_from, areas_to = self.get_compatible_areas_from_to()

                if not compatible_areas:
                    return

                idx_from = np.array([i for i, bus in lst_from])
                idx_to = np.array([i for i, bus in lst_to])
                idx_br = np.array([i for i, bus, sense in lst_br])
                sense_br = np.array([sense for i, bus, sense in lst_br])

                # HVDC
                idx_hvdc_br = np.array([i for i, bus, sense in lst_hvdc_br])
                sense_hvdc_br = np.array([sense for i, bus, sense in lst_hvdc_br])

                if self.ui.usePfValuesForAtcCheckBox.isChecked():
                    pf_drv, pf_results = self.session.get_driver_results(sim.SimulationTypes.PowerFlow_run)
                    if pf_results is not None:
                        Pf = pf_results.Sf.real
                        Pf_hvdc = pf_results.hvdc_Pf.real
                        use_provided_flows = True
                    else:
                        warning_msg('There were no power flow values available. Linear flows will be used.')
                        use_provided_flows = False
                        Pf_hvdc = None
                        Pf = None
                else:
                    use_provided_flows = False
                    Pf = None
                    Pf_hvdc = None

                if len(idx_from) == 0:
                    error_msg('The area "from" has no buses!')
                    return

                if len(idx_to) == 0:
                    error_msg('The area "to" has no buses!')
                    return

                if len(idx_br) == 0:
                    error_msg('There are no inter-area Branches!')
                    return

                mode = self.transfer_modes_dict[self.ui.transferMethodComboBox.currentText()]

                options = sim.AvailableTransferCapacityOptions(distributed_slack=distributed_slack,
                                                               use_provided_flows=use_provided_flows,
                                                               bus_idx_from=idx_from,
                                                               bus_idx_to=idx_to,
                                                               idx_br=idx_br,
                                                               sense_br=sense_br,
                                                               Pf=Pf,
                                                               idx_hvdc_br=idx_hvdc_br,
                                                               sense_hvdc_br=sense_hvdc_br,
                                                               Pf_hvdc=Pf_hvdc,
                                                               dT=dT,
                                                               threshold=threshold,
                                                               mode=mode,
                                                               max_report_elements=max_report_elements)

                drv = sim.AvailableTransferCapacityDriver(grid=self.circuit,
                                                          options=options)

                self.session.run(drv,
                                 post_func=self.post_available_transfer_capacity,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)
                self.add_simulation(sim.SimulationTypes.NetTransferCapacity_run)
                self.LOCK()

            else:
                warning_msg('Another contingency analysis is being executed now...')

        else:
            pass

    def post_available_transfer_capacity(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.NetTransferCapacity_run)
        self.remove_simulation(sim.SimulationTypes.NetTransferCapacity_run)

        # update the results in the circuit structures
        # if not drv.__cancel__:
        if results is not None:

            self.ui.progress_label.setText('Colouring ATC results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()
            self.colour_diagrams()
        else:
            error_msg('Something went wrong, There are no ATC results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_available_transfer_capacity_ts(self, use_clustering=False):
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if len(self.circuit.buses) > 0:

            if self.valid_time_series():
                if not self.session.is_this_running(sim.SimulationTypes.NetTransferCapacity_run):

                    distributed_slack = self.ui.distributed_slack_checkBox.isChecked()
                    dT = 1.0
                    threshold = self.ui.atcThresholdSpinBox.value()
                    max_report_elements = 5  # TODO: self.ui.ntcReportLimitingElementsSpinBox.value()

                    # available transfer capacity inter areas
                    (compatible_areas,
                     lst_from, lst_to, lst_br,
                     lst_hvdc_br, areas_from, areas_to) = self.get_compatible_areas_from_to()

                    if not compatible_areas:
                        return

                    idx_from = np.array([i for i, bus in lst_from])
                    idx_to = np.array([i for i, bus in lst_to])
                    idx_br = np.array([i for i, bus, sense in lst_br])
                    sense_br = np.array([sense for i, bus, sense in lst_br])

                    # HVDC
                    idx_hvdc_br = np.array([i for i, bus, sense in lst_hvdc_br])
                    sense_hvdc_br = np.array([sense for i, bus, sense in lst_hvdc_br])

                    if self.ui.usePfValuesForAtcCheckBox.isChecked():
                        pf_drv, pf_results = self.session.get_driver_results(sim.SimulationTypes.TimeSeries_run)
                        if pf_results is not None:
                            Pf = pf_results.Sf.real
                            Pf_hvdc = pf_results.hvdc_Pf.real
                            use_provided_flows = True
                        else:
                            warning_msg('There were no power flow values available. Linear flows will be used.')
                            use_provided_flows = False
                            Pf_hvdc = None
                            Pf = None
                    else:
                        use_provided_flows = False
                        Pf_hvdc = None
                        Pf = None

                    if len(idx_from) == 0:
                        error_msg('The area "from" has no buses!')
                        return

                    if len(idx_to) == 0:
                        error_msg('The area "to" has no buses!')
                        return

                    if len(idx_br) == 0:
                        error_msg('There are no inter-area Branches!')
                        return

                    mode = self.transfer_modes_dict[self.ui.transferMethodComboBox.currentText()]
                    cluster_number = self.ui.cluster_number_spinBox.value()
                    options = sim.AvailableTransferCapacityOptions(distributed_slack=distributed_slack,
                                                                   use_provided_flows=use_provided_flows,
                                                                   bus_idx_from=idx_from,
                                                                   bus_idx_to=idx_to,
                                                                   idx_br=idx_br,
                                                                   sense_br=sense_br,
                                                                   Pf=Pf,
                                                                   idx_hvdc_br=idx_hvdc_br,
                                                                   sense_hvdc_br=sense_hvdc_br,
                                                                   Pf_hvdc=Pf_hvdc,
                                                                   dT=dT,
                                                                   threshold=threshold,
                                                                   mode=mode,
                                                                   max_report_elements=max_report_elements,
                                                                   use_clustering=use_clustering,
                                                                   cluster_number=cluster_number)

                    drv = sim.AvailableTransferCapacityTimeSeriesDriver(grid=self.circuit,
                                                                        options=options,
                                                                        time_indices=self.get_time_indices(),
                                                                        clustering_results=self.get_clustering_results())

                    self.session.run(drv,
                                     post_func=self.post_available_transfer_capacity_ts,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                    self.add_simulation(sim.SimulationTypes.NetTransferCapacityTS_run)
                    self.LOCK()

                else:
                    warning_msg('Another ATC time series is being executed now...')
            else:
                error_msg('There are no time series!')
        else:
            pass

    def post_available_transfer_capacity_ts(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.NetTransferCapacityTS_run)
        self.remove_simulation(sim.SimulationTypes.NetTransferCapacityTS_run)

        # update the results in the circuit structures
        # if not drv.__cancel__:
        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            self.ui.progress_label.setText('Colouring ATC time series results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()
            self.colour_diagrams()
        else:
            error_msg('Something went wrong, There are no ATC time series results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_continuation_power_flow(self):
        """
        Run voltage stability (voltage collapse) in a separated thread
        :return:
        """

        if len(self.circuit.buses) > 0:

            pf_drv, pf_results = self.session.get_driver_results(sim.SimulationTypes.PowerFlow_run)

            if pf_results is not None:

                if not self.session.is_this_running(sim.SimulationTypes.ContinuationPowerFlow_run):

                    # get the selected UI options
                    use_alpha = self.ui.start_vs_from_default_radioButton.isChecked()

                    # direction vector
                    alpha = self.ui.alpha_doubleSpinBox.value()
                    n = len(self.circuit.buses)

                    # vector that multiplies the target power: The continuation direction
                    alpha_vec = np.ones(n)

                    if self.ui.atcRadioButton.isChecked():
                        use_alpha = True
                        compatible_areas, lst_from, lst_to, lst_br, lst_hvdc_br, areas_from, areas_to = self.get_compatible_areas_from_to()

                        if compatible_areas:
                            idx_from = [i for i, bus in lst_from]
                            idx_to = [i for i, bus in lst_to]

                            alpha_vec[idx_from] *= 2
                            alpha_vec[idx_to] *= -2
                            sel_bus_idx = np.zeros(0, dtype=int)  # for completeness

                            # HVDC
                            idx_hvdc_br = np.array([i for i, bus, sense in lst_hvdc_br])
                            sense_hvdc_br = np.array([sense for i, bus, sense in lst_hvdc_br])
                        else:
                            sel_bus_idx = np.zeros(0, dtype=int)  # for completeness
                            # incompatible areas...exit
                            return
                    else:
                        sel_buses = self.get_selected_buses()
                        if len(sel_buses) == 0:
                            # all nodes
                            alpha_vec *= alpha
                            sel_bus_idx = np.zeros(0, dtype=int)  # for completeness
                        else:
                            # pick the selected nodes
                            sel_bus_idx = np.array([k for k, bus, graphic_obj in sel_buses])
                            alpha_vec[sel_bus_idx] = alpha_vec[sel_bus_idx] * alpha

                    use_profiles = self.ui.start_vs_from_selected_radioButton.isChecked()
                    start_idx = self.ui.vs_departure_comboBox.currentIndex()
                    end_idx = self.ui.vs_target_comboBox.currentIndex()

                    if len(sel_bus_idx) > 0:
                        S = self.circuit.get_Sbus()
                        if S[sel_bus_idx].sum() == 0:
                            warning_msg('You have selected a group of buses with no power injection.\n'
                                        'this will result in an infinite continuation, since the loading variation '
                                        'of buses with zero injection will be infinite.', 'Continuation Power Flow')
                            return

                    mode = self.ui.vc_stop_at_comboBox.currentText()

                    vc_stop_at_dict = {sim.CpfStopAt.Nose.value: sim.CpfStopAt.Nose,
                                       sim.CpfStopAt.Full.value: sim.CpfStopAt.Full,
                                       sim.CpfStopAt.ExtraOverloads.value: sim.CpfStopAt.ExtraOverloads}

                    pf_options = self.get_selected_power_flow_options()

                    # declare voltage collapse options
                    vc_options = sim.ContinuationPowerFlowOptions(step=0.0001,
                                                                  approximation_order=sim.CpfParametrization.Natural,
                                                                  adapt_step=True,
                                                                  step_min=0.00001,
                                                                  step_max=0.2,
                                                                  error_tol=1e-3,
                                                                  tol=pf_options.tolerance,
                                                                  max_it=pf_options.max_iter,
                                                                  stop_at=vc_stop_at_dict[mode],
                                                                  verbose=False)

                    if use_alpha:
                        '''
                        use the current power situation as start
                        and a linear combination of the current situation as target
                        '''
                        # lock the UI
                        self.LOCK()

                        self.ui.progress_label.setText('Compiling the grid...')
                        QtGui.QGuiApplication.processEvents()

                        #  compose the base power
                        Sbase = pf_results.Sbus / self.circuit.Sbase

                        base_overload_number = len(np.where(np.abs(pf_results.loading) > 1)[0])

                        vc_inputs = sim.ContinuationPowerFlowInput(Sbase=Sbase,
                                                                   Vbase=pf_results.voltage,
                                                                   Starget=Sbase * alpha,
                                                                   base_overload_number=base_overload_number)

                        pf_options = self.get_selected_power_flow_options()

                        # create object
                        drv = sim.ContinuationPowerFlowDriver(circuit=self.circuit,
                                                              options=vc_options,
                                                              inputs=vc_inputs,
                                                              pf_options=pf_options)
                        self.session.run(drv,
                                         post_func=self.post_continuation_power_flow,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)

                    elif use_profiles:
                        '''
                        Here the start and finish power states are taken from the profiles
                        '''
                        if start_idx > -1 and end_idx > -1:

                            # lock the UI
                            self.LOCK()

                            pf_drv.run_at(start_idx)

                            # get the power Injections array to get the initial and end points
                            Sprof = self.circuit.get_Sbus_prof()
                            vc_inputs = sim.ContinuationPowerFlowInput(Sbase=Sprof[start_idx, :],
                                                                       Vbase=pf_results.voltage,
                                                                       Starget=Sprof[end_idx, :])

                            pf_options = self.get_selected_power_flow_options()

                            # create object
                            drv = sim.ContinuationPowerFlowDriver(circuit=self.circuit,
                                                                  options=vc_options,
                                                                  inputs=vc_inputs,
                                                                  pf_options=pf_options)
                            self.session.run(drv,
                                             post_func=self.post_continuation_power_flow,
                                             prog_func=self.ui.progressBar.setValue,
                                             text_func=self.ui.progress_label.setText)
                        else:
                            info_msg('Check the selected start and finnish time series indices.')
                else:
                    warning_msg('Another voltage collapse simulation is running...')
            else:
                info_msg('Run a power flow simulation first.\n'
                         'The results are needed to initialize this simulation.')
        else:
            pass

    def post_continuation_power_flow(self):
        """
        Actions performed after the voltage stability. Launched by the thread after its execution
        :return:
        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.ContinuationPowerFlow_run)

        if results is not None:

            self.remove_simulation(sim.SimulationTypes.ContinuationPowerFlow_run)

            if results.voltages is not None:
                if results.voltages.shape[0] > 0:
                    self.update_available_results()

                    self.colour_diagrams()
            else:
                info_msg('The voltage stability did not converge.\nIs this case already at the collapse limit?')
        else:
            error_msg('Something went wrong, There are no voltage stability results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_power_flow_time_series(self):
        """
        Run a time series power flow simulation in a separated thread from the gui
        @return:
        """
        if len(self.circuit.buses) > 0:
            if not self.session.is_this_running(sim.SimulationTypes.TimeSeries_run):
                if self.valid_time_series():
                    self.LOCK()

                    self.add_simulation(sim.SimulationTypes.TimeSeries_run)

                    self.ui.progress_label.setText('Compiling the grid...')
                    QtGui.QGuiApplication.processEvents()

                    opf_time_series_results = self.get_opf_ts_results(
                        use_opf=self.ui.actionOpf_to_Power_flow.isChecked()
                    )

                    options = self.get_selected_power_flow_options()

                    drv = sim.PowerFlowTimeSeriesDriver(grid=self.circuit,
                                                        options=options,
                                                        time_indices=self.get_time_indices(),
                                                        opf_time_series_results=opf_time_series_results,
                                                        clustering_results=self.get_clustering_results(),
                                                        engine=self.get_preferred_engine())

                    self.session.run(drv,
                                     post_func=self.post_power_flow_time_series,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)

                else:
                    warning_msg('There are no time series.', 'Time series')
            else:
                warning_msg('Another time series power flow is being executed now...')
        else:
            pass

    def post_power_flow_time_series(self):
        """
        Events to do when the time series simulation has finished
        @return:
        """

        drv, results = self.session.get_driver_results(sim.SimulationTypes.TimeSeries_run)

        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            self.remove_simulation(sim.SimulationTypes.TimeSeries_run)

            self.update_available_results()

            self.colour_diagrams()

        else:
            warning_msg('No results for the time series simulation.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_stochastic(self):
        """
        Run a Monte Carlo simulation
        @return:
        """

        if len(self.circuit.buses) > 0:

            if not self.session.is_this_running(sim.SimulationTypes.MonteCarlo_run):

                if self.circuit.time_profile is not None:

                    self.LOCK()

                    self.add_simulation(sim.SimulationTypes.StochasticPowerFlow)

                    self.ui.progress_label.setText('Compiling the grid...')
                    QtGui.QGuiApplication.processEvents()

                    pf_options = self.get_selected_power_flow_options()

                    simulation_type = self.stochastic_pf_methods_dict[
                        self.ui.stochastic_pf_method_comboBox.currentText()]

                    tol = 10 ** (-1 * self.ui.tolerance_stochastic_spinBox.value())
                    max_iter = self.ui.max_iterations_stochastic_spinBox.value()
                    drv = sim.StochasticPowerFlowDriver(self.circuit,
                                                        pf_options,
                                                        mc_tol=tol,
                                                        batch_size=100,
                                                        sampling_points=max_iter,
                                                        simulation_type=simulation_type)
                    self.session.run(drv,
                                     post_func=self.post_stochastic,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                else:
                    warning_msg('There are no time series.')

            else:
                warning_msg('Another Monte Carlo simulation is running...')

        else:
            pass

    def post_stochastic(self):
        """
        Actions to perform after the Monte Carlo simulation is finished
        @return:
        """

        drv, results = self.session.get_driver_results(sim.SimulationTypes.StochasticPowerFlow)

        if results is not None:

            self.remove_simulation(sim.SimulationTypes.StochasticPowerFlow)

            self.update_available_results()

            self.colour_diagrams()

        else:
            pass

        if not self.session.is_anything_running():
            self.UNLOCK()

    def post_cascade(self, idx=None):
        """
        Actions to perform after the cascade simulation is finished
        """

        # update the results in the circuit structures
        drv, results = self.session.get_driver_results(sim.SimulationTypes.Cascade_run)

        self.remove_simulation(sim.SimulationTypes.Cascade_run)

        n = len(results.events)

        if n > 0:

            # display the last event, if none is selected
            if idx is None:
                idx = n - 1

            # Accumulate all the failed Branches
            br_idx = np.zeros(0, dtype=int)
            for i in range(idx):
                br_idx = np.r_[br_idx, results.events[i].removed_idx]

            # pick the results at the designated cascade step
            # results = results.events[idx].pf_results  # StochasticPowerFlowResults object

            # Update results
            self.update_available_results()

            # print grid
            self.colour_diagrams()

        if not self.session.is_anything_running():
            self.UNLOCK()

    @staticmethod
    def opf_file_path() -> str:
        """
        get the OPF files folder path
        :return: str
        """
        d = os.path.join(get_create_gridcal_folder(), 'mip_files')

        if not os.path.exists(d):
            os.makedirs(d)
        return d

    def get_opf_options(self) -> Union[None, sim.OptimalPowerFlowOptions]:
        """
        Get the GUI OPF options
        """
        # get the power flow options from the GUI
        solver = self.lp_solvers_dict[self.ui.lpf_solver_comboBox.currentText()]
        mip_solver = self.mip_solvers_dict[self.ui.mip_solver_comboBox.currentText()]
        time_grouping = self.opf_time_groups[self.ui.opf_time_grouping_comboBox.currentText()]
        zonal_grouping = self.opf_zonal_groups[self.ui.opfZonalGroupByComboBox.currentText()]
        pf_options = self.get_selected_power_flow_options()
        consider_contingencies = self.ui.considerContingenciesOpfCheckBox.isChecked()
        skip_generation_limits = self.ui.skipOpfGenerationLimitsCheckBox.isChecked()
        lodf_tolerance = self.ui.opfContingencyToleranceSpinBox.value()
        maximize_flows = self.ui.opfMaximizeExcahngeCheckBox.isChecked()
        unit_commitment = self.ui.opfUnitCommitmentCheckBox.isChecked()
        generate_report = self.ui.addOptimalPowerFlowReportCheckBox.isChecked()

        if self.ui.save_mip_checkBox.isChecked():
            folder = self.opf_file_path()
            fname = f'mip_{self.circuit.name}_{datetime.datetime.now()}.lp'
            export_model_fname = os.path.join(folder, fname)
        else:
            export_model_fname = None

        # available transfer capacity inter areas
        if maximize_flows:
            (compatible_areas, lst_from, lst_to,
             lst_br, lst_hvdc_br, areas_from, areas_to) = self.get_compatible_areas_from_to()
            idx_from = np.array([i for i, bus in lst_from])
            idx_to = np.array([i for i, bus in lst_to])

            if len(idx_from) == 0:
                error_msg('The area "from" has no buses!')
                return None

            if len(idx_to) == 0:
                error_msg('The area "to" has no buses!')
                return None
        else:
            idx_from = None
            idx_to = None
            areas_from = None
            areas_to = None

        ips_method = self.ips_solvers_dict[self.ui.ips_method_comboBox.currentText()]
        ips_tolerance = 1.0 / (10.0 ** self.ui.ips_tolerance_spinBox.value())
        ips_iterations = self.ui.ips_iterations_spinBox.value()
        ips_trust_radius = self.ui.ips_trust_radius_doubleSpinBox.value()
        ips_init_with_pf = self.ui.ips_initialize_with_pf_checkBox.isChecked()
        pf_results = self.session.get_driver_results(SimulationTypes.PowerFlow_run)

        options = sim.OptimalPowerFlowOptions(solver=solver,
                                              time_grouping=time_grouping,
                                              zonal_grouping=zonal_grouping,
                                              mip_solver=mip_solver,
                                              power_flow_options=pf_options,
                                              consider_contingencies=consider_contingencies,
                                              skip_generation_limits=skip_generation_limits,
                                              lodf_tolerance=lodf_tolerance,
                                              maximize_flows=maximize_flows,
                                              area_from_bus_idx=idx_from,
                                              area_to_bus_idx=idx_to,
                                              areas_from=areas_from,
                                              areas_to=areas_to,
                                              unit_commitment=unit_commitment,
                                              export_model_fname=export_model_fname,
                                              generate_report=generate_report,
                                              ips_method=ips_method,
                                              ips_tolerance=ips_tolerance,
                                              ips_iterations=ips_iterations,
                                              ips_trust_radius=ips_trust_radius,
                                              ips_init_with_pf=ips_init_with_pf,
                                              pf_results=pf_results)

        return options

    def run_opf(self):
        """
        Run OPF simulation
        """
        if len(self.circuit.buses) > 0:

            if not self.session.is_this_running(sim.SimulationTypes.OPF_run):

                self.remove_simulation(sim.SimulationTypes.OPF_run)

                self.ui.progress_label.setText('Running optimal power flow...')
                QtGui.QGuiApplication.processEvents()

                self.LOCK()

                # set power flow object instance
                drv = sim.OptimalPowerFlowDriver(grid=self.circuit,
                                                 options=self.get_opf_options(),
                                                 engine=self.get_preferred_engine())

                self.session.run(drv,
                                 post_func=self.post_opf,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                warning_msg('Another OPF is being run...')
        else:
            pass

    def post_opf(self):
        """
        Actions to run after the OPF simulation
        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.OPF_run)

        if results is not None:

            self.remove_simulation(sim.SimulationTypes.OPF_run)

            if not results.converged:
                warning_msg('Some islands did not solve.\n'
                            'Check that all Branches have rating and \n'
                            'that the generator bounds are ok.\n'
                            'You may also use the diagnostic tool (F8)', 'OPF')

            self.update_available_results()

            self.colour_diagrams()

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_opf_time_series(self):
        """
        OPF Time Series run
        """
        if len(self.circuit.buses) > 0:

            if not self.session.is_this_running(sim.SimulationTypes.OPFTimeSeries_run):

                if self.circuit.time_profile is not None:

                    self.add_simulation(sim.SimulationTypes.OPFTimeSeries_run)

                    self.LOCK()

                    # Compile the grid
                    self.ui.progress_label.setText('Compiling the grid...')
                    QtGui.QGuiApplication.processEvents()

                    # get the power flow options from the GUI
                    options = self.get_opf_options()

                    if options is not None:
                        # create the OPF time series instance
                        # if non_sequential:
                        drv = sim.OptimalPowerFlowTimeSeriesDriver(grid=self.circuit,
                                                                   options=options,
                                                                   time_indices=self.get_time_indices(),
                                                                   clustering_results=self.get_clustering_results())

                        drv.engine = self.get_preferred_engine()

                        self.session.run(drv,
                                         post_func=self.post_opf_time_series,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)

                else:
                    warning_msg('There are no time series.\nLoad time series are needed for this simulation.')

            else:
                warning_msg('Another OPF time series is running already...')

        else:
            pass

    def post_opf_time_series(self):
        """
        Post OPF Time Series
        """

        drv, results = self.session.get_driver_results(sim.SimulationTypes.OPFTimeSeries_run)

        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            # remove from the current simulations
            self.remove_simulation(sim.SimulationTypes.OPFTimeSeries_run)

            if results is not None:
                self.update_available_results()

                self.colour_diagrams()

        else:
            pass

        if not self.session.is_anything_running():
            self.UNLOCK()

    def copy_opf_to_time_series(self):
        """
        Copy the OPF generation values to the Time series object and execute a time series simulation
        """
        if len(self.circuit.buses) > 0:

            if self.circuit.time_profile is not None:

                drv, results = self.session.get_driver_results(sim.SimulationTypes.OPFTimeSeries_run)

                if results is not None:

                    quit_msg = "Are you sure that you want overwrite the time events " \
                               "with the simulated by the OPF time series?"
                    reply = QtWidgets.QMessageBox.question(self, 'Message', quit_msg,
                                                           QtWidgets.QMessageBox.StandardButton.Yes,
                                                           QtWidgets.QMessageBox.StandardButton.No)

                    if reply == QtWidgets.QMessageBox.StandardButton.Yes:

                        results.apply_lp_profiles(self.circuit)

                    else:
                        pass

                else:
                    info_msg('There are no OPF time series execution.'
                             '\nRun OPF time series to be able to copy the value to the time series object.')

            else:
                warning_msg('There are no time series.\nLoad time series are needed for this simulation.')
        else:
            pass

    def get_opf_ntc_options(self) -> Union[None, sim.OptimalNetTransferCapacityOptions]:
        """

        :return:
        """

        # available transfer capacity inter areas
        (compatible_areas, lst_from, lst_to, lst_br,
         lst_hvdc_br, areas_from, areas_to) = self.get_compatible_areas_from_to()

        if not compatible_areas:
            error_msg('There are no compatible areas')
            return None

        idx_from = np.array([i for i, bus in lst_from])
        idx_to = np.array([i for i, bus in lst_to])
        idx_br = np.array([i for i, bus, sense in lst_br])

        if len(idx_from) == 0:
            error_msg('The area "from" has no buses!')
            return None

        if len(idx_to) == 0:
            error_msg('The area "to" has no buses!')
            return None

        if len(idx_br) == 0:
            error_msg('There are no inter-area Branches!')
            return None

        opts = sim.OptimalNetTransferCapacityOptions(
            area_from_bus_idx=idx_from,
            area_to_bus_idx=idx_to,
            transfer_method=self.transfer_modes_dict[self.ui.transferMethodComboBox.currentText()],
            loading_threshold_to_report=self.ui.ntcReportLoadingThresholdSpinBox.value(),
            skip_generation_limits=self.ui.skipNtcGenerationLimitsCheckBox.isChecked(),
            transmission_reliability_margin=self.ui.trmSpinBox.value(),  # MW
            branch_exchange_sensitivity=self.ui.ntcAlphaSpinBox.value() / 100.0,
            use_branch_exchange_sensitivity=self.ui.ntcSelectBasedOnExchangeSensitivityCheckBox.isChecked(),
            branch_rating_contribution=self.ui.ntcLoadRuleSpinBox.value() / 100.0,
            use_branch_rating_contribution=self.ui.ntcSelectBasedOnAcerCriteriaCheckBox.isChecked(),
            consider_contingencies=self.ui.consider_ntc_contingencies_checkBox.isChecked(),
            opf_options=self.get_opf_options(),
            lin_options=self.get_linear_options()
        )

        return opts

    def run_opf_ntc(self):
        """
        Run OPF simulation
        """
        if len(self.circuit.buses) > 0:

            if not self.session.is_this_running(sim.SimulationTypes.OPF_NTC_run):

                self.remove_simulation(sim.SimulationTypes.OPF_NTC_run)

                options = self.get_opf_ntc_options()

                if options is None:
                    return

                else:
                    self.ui.progress_label.setText('Running optimal net transfer capacity...')
                    QtGui.QGuiApplication.processEvents()

                    # set power flow object instance
                    drv = sim.OptimalNetTransferCapacityDriver(grid=self.circuit, options=options)

                    self.LOCK()
                    self.session.run(drv,
                                     post_func=self.post_opf_ntc,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)

            else:
                warning_msg('Another OPF is being run...')
        else:
            pass

    def post_opf_ntc(self):
        """
        Actions to run after the OPF simulation
        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.OPF_NTC_run)

        if results is not None:
            self.remove_simulation(sim.SimulationTypes.OPF_NTC_run)
            self.update_available_results()
            self.colour_diagrams()

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_opf_ntc_ts(self):
        """
        Run OPF NTC time series simulation
        """
        if len(self.circuit.buses) > 0:

            if not self.session.is_this_running(sim.SimulationTypes.OPF_NTC_TS_run):

                self.remove_simulation(sim.SimulationTypes.OPF_NTC_TS_run)

                options = self.get_opf_ntc_options()

                if options is None:
                    return

                else:

                    self.ui.progress_label.setText('Running optimal net transfer capacity time series...')
                    QtGui.QGuiApplication.processEvents()

                    # set optimal net transfer capacity driver instance
                    drv = sim.OptimalNetTransferCapacityTimeSeriesDriver(grid=self.circuit,
                                                                         options=options,
                                                                         time_indices=self.get_time_indices(),
                                                                         clustering_results=self.get_clustering_results())

                    self.LOCK()
                    self.session.run(drv,
                                     post_func=self.post_opf_ntc_ts,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)

            else:
                warning_msg('Another Optimal NCT time series is being run...')
        else:
            pass

    def post_opf_ntc_ts(self):
        """
        Actions to run after the optimal net transfer capacity time series simulation
        """

        drv, results = self.session.get_driver_results(sim.SimulationTypes.OPF_NTC_TS_run)

        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            # remove from the current simulations
            self.remove_simulation(sim.SimulationTypes.OPF_NTC_TS_run)

            if results is not None:
                self.update_available_results()

                self.colour_diagrams()

        else:
            pass

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_find_node_groups(self):
        """
        Run the node groups algorithm
        """
        if self.ui.actionFind_node_groups.isChecked():

            drv, ptdf_results = self.session.get_driver_results(sim.SimulationTypes.LinearAnalysis_run)

            if ptdf_results is not None:

                self.LOCK()
                sigmas = self.ui.node_distances_sigma_doubleSpinBox.value()
                min_group_size = self.ui.node_distances_elements_spinBox.value()
                drv = sim.NodeGroupsDriver(grid=self.circuit,
                                           sigmas=sigmas,
                                           min_group_size=min_group_size,
                                           ptdf_results=ptdf_results)

                self.session.run(drv,
                                 post_func=self.post_run_find_node_groups,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                error_msg('There are no PTDF results :/')

        else:
            # delete the markers
            self.clear_big_bus_markers()

    def post_run_find_node_groups(self):
        """
        Colour the grid after running the node grouping
        :return:
        """
        self.UNLOCK()
        print('\nGroups:')

        drv, results = self.session.get_driver_results(sim.SimulationTypes.NodeGrouping_run)

        if drv is not None:

            for group in drv.groups_by_name:
                print(group)

            colours = viz.get_n_colours(n=len(drv.groups_by_index))

            bus_colours = np.empty(len(self.circuit.buses), dtype=object)
            tool_tips = [""] * len(self.circuit.buses)
            for c, group in enumerate(drv.groups_by_index):
                for i in group:
                    bus = self.circuit.buses[i]
                    if bus.active:
                        r, g, b, a = colours[c]
                        bus_colours[i] = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
                        tool_tips[i] = 'Group ' + str(c)

            self.set_big_bus_marker_colours(buses=self.circuit.buses,
                                            colors=bus_colours,
                                            tool_tips=tool_tips)

    def run_inputs_analysis(self):
        """

        :return:
        """
        if len(self.circuit.buses) > 0:

            if not self.session.is_this_running(sim.SimulationTypes.InputsAnalysis_run):

                self.remove_simulation(sim.SimulationTypes.InputsAnalysis_run)

                # set power flow object instance
                drv = sim.InputsAnalysisDriver(self.circuit)

                self.LOCK()
                self.session.run(drv,
                                 post_func=self.post_inputs_analysis,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                warning_msg('Another inputs analysis is being run...')
        else:
            pass

    def post_inputs_analysis(self):
        """

        :return:
        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.InputsAnalysis_run)

        if results is not None:
            self.remove_simulation(sim.SimulationTypes.InputsAnalysis_run)
            self.update_available_results()
            self.colour_diagrams()

        if not self.session.is_anything_running():
            self.UNLOCK()

    def storage_location(self):
        """
        Add storage markers to the schematic
        """

        if len(self.circuit.buses) > 0:

            if self.ui.actionStorage_location_suggestion.isChecked():

                ts_drv, ts_results = self.session.get_driver_results(sim.SimulationTypes.TimeSeries_run)

                if ts_results is not None:

                    # perform a time series analysis
                    ts_analysis = grid_analysis.TimeSeriesResultsAnalysis(self.circuit, ts_results)

                    # get the indices of the buses selected for storage
                    idx = np.where(ts_analysis.buses_selected_for_storage_frequency > 0)[0]

                    if len(idx) > 0:

                        frequencies = ts_analysis.buses_selected_for_storage_frequency[idx]

                        fmax = np.max(frequencies)

                        # prepare the color map
                        seq = [(0, 'green'),
                               (0.6, 'orange'),
                               (1.0, 'red')]
                        cmap = LinearSegmentedColormap.from_list('vcolors', seq)

                        self.buses_for_storage = list()
                        colors = list()

                        # get all batteries grouped by bus
                        batt_by_bus = self.circuit.get_batteries_by_bus()

                        for i, freq in zip(idx, frequencies):

                            bus = self.circuit.buses[i]
                            batts = batt_by_bus.get(bus, None)

                            # add a marker to the bus if there are no batteries in it
                            if batts is None:
                                self.buses_for_storage.append(bus)
                                r, g, b, a = cmap(freq / fmax)
                                color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
                                colors.append(color)

                        self.set_big_bus_marker_colours(buses=self.buses_for_storage, colors=colors, tool_tips=None)
                    else:

                        info_msg('No problems were detected, therefore no storage is suggested',
                                 'Storage location')

                else:
                    warning_msg('There is no time series simulation.\n It is needed for this functionality.',
                                'Storage location')

            else:

                # delete the red dots
                self.clear_big_bus_markers()
        else:
            pass

    def run_sigma_analysis(self):
        """
        Run the sigma analysis
        """
        if len(self.circuit.buses) > 0:
            options = self.get_selected_power_flow_options()
            bus_names = np.array([b.name for b in self.circuit.buses])
            sigma_driver = sim.SigmaAnalysisDriver(grid=self.circuit, options=options)
            sigma_driver.run()

            if not sigma_driver.results.converged:
                error_msg("Sigma coefficients did not converge :(")

            self.sigma_dialogue = SigmaAnalysisGUI(parent=self,
                                                   results=sigma_driver.results,
                                                   bus_names=bus_names,
                                                   good_coefficients=sigma_driver.results.converged)
            self.sigma_dialogue.resize(int(1.61 * 600.0), 550)  # golden ratio
            self.sigma_dialogue.show()  # exec leaves the parent on hold

    def run_investments_evaluation(self) -> None:
        """
        Run investments evaluation
        """
        if len(self.circuit.buses) > 0:

            if len(self.circuit.investments_groups) > 0:

                if not self.session.is_this_running(sim.SimulationTypes.InvestmestsEvaluation_run):

                    # evaluation method
                    method = self.investment_evaluation_method_dict[
                        self.ui.investment_evaluation_method_ComboBox.currentText()]

                    # maximum number of function evalñuations as a factor of the number of investments
                    max_eval = self.ui.max_investments_evluation_number_spinBox.value() * len(
                        self.circuit.investments_groups)

                    options = sim.InvestmentsEvaluationOptions(solver=method,
                                                               max_eval=max_eval,
                                                               pf_options=self.get_selected_power_flow_options())
                    drv = sim.InvestmentsEvaluationDriver(grid=self.circuit,
                                                          options=options)

                    self.session.run(drv,
                                     post_func=self.post_run_investments_evaluation,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                    self.add_simulation(sim.SimulationTypes.InvestmestsEvaluation_run)
                    self.LOCK()

                else:
                    warning_msg('Another contingency analysis is being executed now...')
            else:
                warning_msg("There are no investment groups, "
                            "you need to create some so that GridCal can evaluate them ;)")

        else:
            pass

    def post_run_investments_evaluation(self) -> None:
        """
        Post investments evaluation
        """
        drv, results = self.session.get_driver_results(sim.SimulationTypes.InvestmestsEvaluation_run)
        self.remove_simulation(sim.SimulationTypes.InvestmestsEvaluation_run)

        # update the results in the circuit structures
        if results is not None:

            self.ui.progress_label.setText('Colouring investments evaluation results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()
            self.colour_diagrams()
        else:
            error_msg('Something went wrong, There are no investments evaluation results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def get_clustering_results(self) -> Union[sim.ClusteringResults, None]:
        """
        Get the clustering results if available
        :return: ClusteringResults or None
        """
        if self.ui.actionUse_clustering.isChecked():
            _, clustering_results = self.session.get_driver_results(sim.SimulationTypes.ClusteringAnalysis_run)

            if clustering_results is not None:
                n = len(clustering_results.time_indices)

                if n != self.ui.cluster_number_spinBox.value():
                    error_msg("The number of clusters in the stored results is different from the specified :(\n"
                              "Run another clustering analysis.")

                    return None
                else:
                    # all ok
                    return clustering_results
            else:
                # no results ...
                warning_msg("There are no clustering results.")
                self.ui.actionUse_clustering.setChecked(False)
                return None

        else:
            # not marked ...
            return None

    def run_clustering(self):
        """
        Run a clustering analysis
        """
        if self.circuit.get_bus_number() > 0 and self.circuit.get_time_number() > 0:

            if not self.session.is_this_running(sim.SimulationTypes.ClusteringAnalysis_run):

                n_points = self.ui.cluster_number_spinBox.value()
                nt = self.circuit.get_time_number()
                if n_points < nt:

                    self.add_simulation(sim.SimulationTypes.ClusteringAnalysis_run)

                    self.LOCK()

                    # get the power flow options from the GUI
                    options = sim.ClusteringAnalysisOptions(n_points=n_points)

                    drv = sim.ClusteringDriver(grid=self.circuit,
                                               options=options)
                    self.session.run(drv,
                                     post_func=self.post_clustering,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)

                else:
                    warning_msg('You cannot find {0} clusters for {1} time steps.\n'
                                'Modify the number of clusters in the ML settings.'.format(n_points, nt),
                                title="Clustering")

            else:
                warning_msg('Another clustering is being executed now...')
        else:
            pass

    def post_clustering(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        # update the results in the circuit structures
        drv, results = self.session.get_driver_results(sim.SimulationTypes.ClusteringAnalysis_run)
        self.remove_simulation(sim.SimulationTypes.ClusteringAnalysis_run)
        if results is not None:

            self.update_available_results()
        else:
            error_msg('Something went wrong, There are no power short circuit results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def fuse_devices(self):
        """
        Fuse the devices per node into a single device per category
        """
        ok = yes_no_question("This action will fuse all the devices per node and per category. Are you sure?",
                             "Fuse devices")

        if ok:
            deleted_devices = self.circuit.fuse_devices()

            for diagram_widget in self.diagram_widgets_list:
                diagram_widget.delete_diagram_elements(elements=deleted_devices)

    def run_topology_processor(self):
        """
        Run the topology processor on the grid completelly
        """
        if self.circuit.get_bus_number():

            if not self.session.is_this_running(sim.SimulationTypes.PowerFlow_run):

                self.LOCK()

                self.add_simulation(sim.SimulationTypes.TopologyProcessor_run)

                self.ui.progress_label.setText('Running topology processing...')
                QtGui.QGuiApplication.processEvents()
                # set power flow object instance
                drv = sim.TopologyProcessorDriver(self.circuit)

                self.session.run(drv,
                                 post_func=self.post_topology_processor,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                warning_msg('Another simulation of the same type is running...')
        else:
            pass

    def post_topology_processor(self):
        """
        Actions after the topology processor is done
        """

        self.remove_simulation(sim.SimulationTypes.TopologyProcessor_run)
        # self.update_available_results()
        # self.colour_diagrams()

        if not self.session.is_anything_running():
            self.UNLOCK()

    def activate_clustering(self):
        """
        When activating the use of clustering, also activate time series
        :return:
        """
        if self.ui.actionUse_clustering.isChecked():

            # check if there are clustering results yet
            _, clustering_results = self.session.get_driver_results(sim.SimulationTypes.ClusteringAnalysis_run)

            if clustering_results is not None:
                n = len(clustering_results.time_indices)

                if n != self.ui.cluster_number_spinBox.value():
                    error_msg("The number of clusters in the stored results is different from the specified :(\n"
                              "Run another clustering analysis.")
                    self.ui.actionUse_clustering.setChecked(False)
                    return None
                else:
                    # all ok
                    self.ui.actionactivate_time_series.setChecked(True)
                    return None
            else:
                # no results ...
                warning_msg("There are no clustering results.")
                self.ui.actionUse_clustering.setChecked(False)
                return None
