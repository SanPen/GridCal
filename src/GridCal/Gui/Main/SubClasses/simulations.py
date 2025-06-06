# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import datetime
import numpy as np
from collections import OrderedDict
from typing import List, Tuple, Dict, Union

# GUI imports
from PySide6 import QtGui, QtWidgets
from matplotlib.colors import LinearSegmentedColormap

import GridCal.Gui.gui_functions as gf
import GridCal.Gui.Visualization.visualization as viz
from GridCal.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem
from GridCal.Gui.general_dialogues import LogsDialogue
from GridCal.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import MapWidget
from GridCal.Gui.messages import yes_no_question, error_msg, warning_msg, info_msg
from GridCal.Gui.Main.SubClasses.Model.time_events import TimeEventsMain
from GridCal.Gui.SigmaAnalysis.sigma_analysis_dialogue import SigmaAnalysisGUI
from GridCal.Session.server_driver import RemoteJobDriver

# Engine imports
import GridCalEngine.Devices as dev
import GridCalEngine.Simulations as sim
import GridCalEngine.Simulations.PowerFlow.grid_analysis as grid_analysis
from GridCalEngine.Compilers.circuit_to_newton_pa import get_newton_mip_solvers_list
from GridCalEngine.Utils.MIP.selected_interface import get_available_mip_solvers
from GridCalEngine.IO.file_system import opf_file_path
from GridCalEngine.IO.gridcal.remote import RemoteInstruction
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.Simulations.types import DRIVER_OBJECTS
from GridCalEngine.basic_structures import CxVec
from GridCalEngine.enumerations import (DeviceType, AvailableTransferMode, SolverType, MIPSolvers, TimeGrouping,
                                        ZonalGrouping, ContingencyMethod, InvestmentEvaluationMethod, EngineType,
                                        BranchImpedanceMode, ResultTypes, SimulationTypes, NodalCapacityMethod,
                                        ContingencyFilteringMethods, InvestmentsEvaluationObjectives)


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

        self._remote_jobs: Dict[str, RemoteJobDriver] = dict()

        # Power Flow Methods
        self.solvers_dict = OrderedDict()
        self.solvers_dict[SolverType.NR.value] = SolverType.NR
        self.solvers_dict[SolverType.IWAMOTO.value] = SolverType.IWAMOTO
        self.solvers_dict[SolverType.LM.value] = SolverType.LM
        self.solvers_dict[SolverType.PowellDogLeg.value] = SolverType.PowellDogLeg
        self.solvers_dict[SolverType.FASTDECOUPLED.value] = SolverType.FASTDECOUPLED
        self.solvers_dict[SolverType.HELM.value] = SolverType.HELM
        self.solvers_dict[SolverType.GAUSS.value] = SolverType.GAUSS
        self.solvers_dict[SolverType.LACPF.value] = SolverType.LACPF
        self.solvers_dict[SolverType.DC.value] = SolverType.DC
        # self.solvers_dict[SolverType.GENERALISED.value] = SolverType.GENERALISED

        self.ui.solver_comboBox.setModel(gf.get_list_model(list(self.solvers_dict.keys())))
        self.ui.solver_comboBox.setCurrentIndex(0)

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
        self.mip_solvers_dict[MIPSolvers.HIGHS.value] = MIPSolvers.HIGHS
        self.mip_solvers_dict[MIPSolvers.SCIP.value] = MIPSolvers.SCIP
        self.mip_solvers_dict[MIPSolvers.CPLEX.value] = MIPSolvers.CPLEX
        self.mip_solvers_dict[MIPSolvers.GUROBI.value] = MIPSolvers.GUROBI
        self.mip_solvers_dict[MIPSolvers.XPRESS.value] = MIPSolvers.XPRESS

        # opf solvers dictionary
        self.nodal_capacity_methods_dict = OrderedDict()

        for val in [NodalCapacityMethod.LinearOptimization,
                    NodalCapacityMethod.NonlinearOptimization,
                    NodalCapacityMethod.CPF]:
            self.nodal_capacity_methods_dict[val.value] = val

        self.ui.nodal_capacity_method_comboBox.setModel(
            gf.get_list_model(list(self.nodal_capacity_methods_dict.keys()))
        )

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
        # self.contingency_engines_dict[ContingencyMethod.OptimalPowerFlow.value] = ContingencyMethod.OptimalPowerFlow
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
        investment_methods = [
            InvestmentEvaluationMethod.Independent,
            InvestmentEvaluationMethod.NSGA3,
            InvestmentEvaluationMethod.MVRSM,
            InvestmentEvaluationMethod.MixedVariableGA,
        ]
        self.investment_evaluation_method_dict = OrderedDict()
        self.plugins_investment_evaluation_method_dict = OrderedDict()
        lst = list()
        for method in investment_methods:
            self.investment_evaluation_method_dict[method.value] = method
            lst.append(method.value)
        self.ui.investment_evaluation_method_ComboBox.setModel(gf.get_list_model(lst))

        # contingency filtering modes
        con_filters = [ContingencyFilteringMethods.All,
                       ContingencyFilteringMethods.Country,
                       ContingencyFilteringMethods.Area,
                       ContingencyFilteringMethods.Zone]
        self.contingency_filter_modes_dict = OrderedDict()
        con_filter_vals = list()
        for con_filter in con_filters:
            self.contingency_filter_modes_dict[con_filter.value] = con_filter
            con_filter_vals.append(con_filter.value)
        self.ui.contingency_filter_by_comboBox.setModel(gf.get_list_model(con_filter_vals))

        # ptdf grouping modes
        self.ptdf_group_modes = OrderedDict()

        self.investment_evaluation_objfunc_dict = OrderedDict()
        lst = list()
        for method in [InvestmentsEvaluationObjectives.PowerFlow,
                       InvestmentsEvaluationObjectives.TimeSeriesPowerFlow,
                       InvestmentsEvaluationObjectives.GenerationAdequacy,
                       InvestmentsEvaluationObjectives.SimpleDispatch]:
            self.investment_evaluation_objfunc_dict[method.value] = method
            lst.append(method.value)
        self.ui.investment_evaluation_objfunc_ComboBox.setModel(gf.get_list_model(lst))

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
        self.ui.actionATC.triggered.connect(self.atc_dispatcher)
        self.ui.actionATC_Time_Series.triggered.connect(self.run_available_transfer_capacity_ts)
        self.ui.actionPTDF_time_series.triggered.connect(self.run_linear_analysis_ts)
        self.ui.actionClustering.triggered.connect(self.run_clustering)
        self.ui.actionSigma_analysis.triggered.connect(self.run_sigma_analysis)
        self.ui.actionFind_node_groups.triggered.connect(self.run_find_node_groups)
        self.ui.actionFuse_devices.triggered.connect(self.fuse_devices)
        self.ui.actionInvestments_evaluation.triggered.connect(self.run_investments_evaluation)
        self.ui.actionReliability.triggered.connect(self.reliability_dispatcher)

        self.ui.actionUse_clustering.triggered.connect(self.activate_clustering)
        self.ui.actionNodal_capacity.triggered.connect(self.run_nodal_capacity)

        # combobox change
        self.ui.engineComboBox.currentTextChanged.connect(self.modify_ui_options_according_to_the_engine)
        self.ui.contingency_filter_by_comboBox.currentTextChanged.connect(self.modify_contingency_filter_mode)
        self.ui.available_results_to_color_comboBox.currentTextChanged.connect(self.changed_study)

        # button
        self.ui.find_automatic_precission_Button.clicked.connect(self.automatic_pf_precision)

    def get_simulations(self) -> List[DRIVER_OBJECTS]:
        """
        Get all threads that have to do with simulation
        :return: list of simulation driver objects
        """

        all_threads = list(self.session.drivers.values())

        # set the threads so that the diagram scene objects can plot them
        for diagram in self.diagram_widgets_list:
            if isinstance(diagram, (SchematicWidget, MapWidget)):
                diagram.set_results_to_plot(all_threads)

        return all_threads

    def get_available_drivers(self) -> List[DRIVER_OBJECTS]:
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

    def get_time_indices(self) -> np.ndarray | None:
        """
        Get an array of indices of the time steps selected within the start-end interval
        :return: np.array[int]
        """

        if self.circuit.time_profile is None:
            return None
        else:
            start = self.get_simulation_start()
            end = self.get_simulation_end()

            return np.arange(start, end + 1)

    def modify_ui_options_according_to_the_engine(self) -> None:
        """
        Change the UI depending on the engine options
        :return:
        """
        eng = self.get_preferred_engine()

        if eng == EngineType.GSLV:
            self.ui.opfUnitCommitmentCheckBox.setVisible(True)

            # add the AC_OPF option
            self.lp_solvers_dict = OrderedDict()
            self.lp_solvers_dict[SolverType.LINEAR_OPF.value] = SolverType.LINEAR_OPF
            self.lp_solvers_dict[SolverType.NONLINEAR_OPF.value] = SolverType.NONLINEAR_OPF
            self.lp_solvers_dict[SolverType.SIMPLE_OPF.value] = SolverType.SIMPLE_OPF
            self.ui.lpf_solver_comboBox.setModel(gf.get_list_model(list(self.lp_solvers_dict.keys())))

            # Power Flow Methods
            self.solvers_dict[SolverType.NR.value] = SolverType.NR
            self.solvers_dict[SolverType.IWAMOTO.value] = SolverType.IWAMOTO
            self.solvers_dict[SolverType.LM.value] = SolverType.LM
            self.solvers_dict[SolverType.FASTDECOUPLED.value] = SolverType.FASTDECOUPLED
            self.solvers_dict[SolverType.HELM.value] = SolverType.HELM
            self.solvers_dict[SolverType.GAUSS.value] = SolverType.GAUSS
            self.solvers_dict[SolverType.LACPF.value] = SolverType.LACPF
            self.solvers_dict[SolverType.DC.value] = SolverType.DC

            self.ui.solver_comboBox.setModel(gf.get_list_model(list(self.solvers_dict.keys())))
            self.ui.solver_comboBox.setCurrentIndex(0)

            mip_solvers = get_available_mip_solvers()
            self.ui.mip_solver_comboBox.setModel(gf.get_list_model(mip_solvers))

        elif eng == EngineType.NewtonPA:
            self.ui.opfUnitCommitmentCheckBox.setVisible(True)

            # add the AC_OPF option
            self.lp_solvers_dict = OrderedDict()
            self.lp_solvers_dict[SolverType.LINEAR_OPF.value] = SolverType.LINEAR_OPF
            self.lp_solvers_dict[SolverType.NONLINEAR_OPF.value] = SolverType.NONLINEAR_OPF
            self.lp_solvers_dict[SolverType.SIMPLE_OPF.value] = SolverType.SIMPLE_OPF
            self.ui.lpf_solver_comboBox.setModel(gf.get_list_model(list(self.lp_solvers_dict.keys())))

            # Power Flow Methods
            self.solvers_dict[SolverType.NR.value] = SolverType.NR
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
            self.solvers_dict[SolverType.IWAMOTO.value] = SolverType.IWAMOTO
            self.solvers_dict[SolverType.LM.value] = SolverType.LM
            self.solvers_dict[SolverType.PowellDogLeg.value] = SolverType.PowellDogLeg
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
            raise Exception('Unsupported engine ' + str(eng.value))

    def modify_contingency_filter_mode(self) -> None:
        """
        Modify the objects
        """
        filter_mode = self.contingency_filter_modes_dict[self.ui.contingency_filter_by_comboBox.currentText()]

        if filter_mode == ContingencyFilteringMethods.All:
            mdl = None

        elif filter_mode == ContingencyFilteringMethods.Country:
            mdl = gf.get_list_model(lst=[elm.name for elm in self.circuit.get_countries()],
                                    checks=True,
                                    check_value=True)

        elif filter_mode == ContingencyFilteringMethods.Area:
            mdl = gf.get_list_model(lst=[elm.name for elm in self.circuit.get_areas()],
                                    checks=True,
                                    check_value=True)

        elif filter_mode == ContingencyFilteringMethods.Zone:
            mdl = gf.get_list_model(lst=[elm.name for elm in self.circuit.get_zones()],
                                    checks=True,
                                    check_value=True)

        else:
            raise Exception('Unsupported ContingencyFilteringMethod ' + str(filter_mode.value))

        self.ui.contingency_group_filter_listView.setModel(mdl)

    def get_contingency_groups_matching_the_filter(self) -> List[dev.ContingencyGroup]:
        """
        Get the list of contingencies that match the group
        :return:
        """

        # get the filter mode
        filter_mode = self.contingency_filter_modes_dict[self.ui.contingency_filter_by_comboBox.currentText()]

        if filter_mode == ContingencyFilteringMethods.All:
            # no filtering, we're safe
            return self.circuit.get_contingency_groups()

        elif filter_mode == ContingencyFilteringMethods.Country:

            if self.circuit.get_country_number() > 0:
                # get the selection indices
                idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
                elements = self.circuit.get_countries()
                return self.circuit.get_contingency_groups_in(grouping_elements=[elements[i] for i in idx])
            else:
                # default to returning all groups, since it's safer
                return self.circuit.get_contingency_groups()

        elif filter_mode == ContingencyFilteringMethods.Area:
            if self.circuit.get_area_number() > 0:
                # get the selection indices
                idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
                elements = self.circuit.get_areas()
                return self.circuit.get_contingency_groups_in(grouping_elements=[elements[i] for i in idx])
            else:
                # default to returning all groups, since it's safer
                return self.circuit.get_contingency_groups()

        elif filter_mode == ContingencyFilteringMethods.Zone:
            if self.circuit.get_zone_number() > 0:
                # get the selection indices
                idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
                elements = self.circuit.get_areas()
                return self.circuit.get_contingency_groups_in(grouping_elements=[elements[i] for i in idx])
            else:
                # default to returning all groups, since it's safer
                return self.circuit.get_contingency_groups()

        else:
            raise Exception('Unsupported ContingencyFilteringMethod ' + str(filter_mode.value))

    def valid_time_series(self):
        """
        Check if there are valid time series
        """
        if self.circuit.valid_for_simulation():
            if self.circuit.time_profile is not None:
                if len(self.circuit.time_profile) > 0:
                    return True
        return False

    def add_simulation(self, val: SimulationTypes):
        """
        Add a simulation to the simulations list
        :param val: simulation type
        """
        self.stuff_running_now.append(val)

    def remove_simulation(self, val: SimulationTypes):
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
        self.ui.grid_idtag_label.setText('idtag. ' + str(self.circuit.idtag))
        self.ui.user_name_label.setText('User: ' + str(self.circuit.user_name))
        if self.open_file_thread_object is not None:
            if isinstance(self.open_file_thread_object.file_name, str):
                self.ui.file_information_label.setText(self.open_file_thread_object.file_name)

        self.clear_console()
        self.add_console_vars()

        self.ui.units_label.setText("")

    @staticmethod
    def get_investments_combination_tree_model(drv: sim.InvestmentsEvaluationDriver) -> QtGui.QStandardItemModel:
        """
        Get the investments combination tree model
        :param drv:
        :return:
        """
        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(["Combination"] + list(drv.problem.get_objectives_names()))

        results = drv.results
        for i in range(results.max_eval):
            idx = np.where(results.x[i, :] != 0)[0]
            if len(idx):
                row_items = [QtGui.QStandardItem(f"Combination {i}")] + [
                    QtGui.QStandardItem(f"{fi:.2f}") for fi in drv.results.f[i, :]
                ]
                model.appendRow(row_items)

                # Add names as child nodes under this combination
                names_parent_item = row_items[0]  # Use the first column (Combination) as parent
                for k in idx:
                    name_item = QtGui.QStandardItem(results.x_names[k])
                    names_parent_item.appendRow([name_item])

        return model

    def fill_combinations_tree(self, drv: DRIVER_OBJECTS | None):
        """
        Fill the tree driver
        :param drv: Any Driver object
        """
        if drv is None:
            self.ui.combinationsTreeView.setModel(None)
        else:
            if drv.tpe == SimulationTypes.InvestmentsEvaluation_run:
                model = self.get_investments_combination_tree_model(drv=drv)
                self.ui.combinationsTreeView.setModel(model)
                # self.ui.combinationsTreeView.expandAll()

            else:
                self.ui.combinationsTreeView.setModel(None)

    def changed_study(self):
        """

        :return:
        """
        current_study_name = self.ui.available_results_to_color_comboBox.currentText()
        drv_dict = {driver.tpe.value: driver for driver in self.get_available_drivers()}
        drv = drv_dict.get(current_study_name, None)
        if drv is not None and hasattr(drv, 'time_indices'):
            if drv.time_indices is not None:
                if len(drv.time_indices):
                    a = drv.time_indices[0]
                    b = drv.time_indices[-1]
                    self.ui.diagram_step_slider.setRange(a, b)
                    self.ui.diagram_step_slider.setValue(a)
                else:
                    self.setup_time_sliders()
            else:
                self.setup_time_sliders()
        else:
            self.setup_time_sliders()

        self.fill_combinations_tree(drv=drv)

    def update_available_results(self) -> None:
        """
        Update the results that are displayed in the results tab
        """

        self.available_results_dict = dict()
        self.available_results_steps_dict = dict()

        # clear results lists
        self.ui.results_treeView.setModel(None)

        available_results = self.get_available_drivers()
        max_steps = 0
        d = dict()
        lst = [SimulationTypes.DesignView.value]
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
            SimulationTypes.PowerFlowTimeSeries_run.value: ':/Icons/icons/pf_ts.svg',
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
            SimulationTypes.InvestmentsEvaluation_run.value: ':/Icons/icons/expansion_planning.svg',
            SimulationTypes.NodalCapacityTimeSeries_run.value: ':/Icons/icons/nodal_capacity.svg',
            SimulationTypes.OPF_NTC_run.value: ':/Icons/icons/ntc_opf.svg',
            SimulationTypes.OPF_NTC_TS_run.value: ':/Icons/icons/ntc_opf_ts.svg',
            SimulationTypes.Reliability_run.value: ':/Icons/icons/reliability.svg',
        }

        self.ui.results_treeView.setModel(gf.get_tree_model(d, 'Results', icons=icons))
        lst.reverse()  # this is to show the latest simulation first
        mdl = gf.get_list_model(lst)
        self.ui.available_results_to_color_comboBox.setModel(mdl)
        self.ui.resultsTableView.setModel(None)
        self.ui.resultsLogsTreeView.setModel(None)
        self.changed_study()

    def get_compatible_from_to_buses_and_inter_branches(self) -> dev.InterAggregationInfo:
        """
        Get the lists that help defining the inter area objects
        :return: InterAggregationInfo
        """
        dev_tpe_from = self.exchange_places_dict[self.ui.fromComboBox.currentText()]
        devs_from = self.circuit.get_elements_by_type(dev_tpe_from)
        from_idx = gf.get_checked_indices(self.ui.fromListView.model())
        objects_from = [devs_from[i] for i in from_idx]

        dev_tpe_to = self.exchange_places_dict[self.ui.toComboBox.currentText()]
        devs_to = self.circuit.get_elements_by_type(dev_tpe_to)
        to_idx = gf.get_checked_indices(self.ui.toListView.model())
        objects_to = [devs_to[i] for i in to_idx]

        info: dev.InterAggregationInfo = self.circuit.get_inter_aggregation_info(objects_from=objects_from,
                                                                                 objects_to=objects_to)

        if info.logger.has_logs():
            # Show dialogue
            dlg = LogsDialogue(name="Add selected DB objects to current diagram", logger=info.logger)
            dlg.setModal(True)
            dlg.exec()

        return info

    def get_selected_power_flow_options(self) -> sim.PowerFlowOptions:
        """
        Gather power flow run options
        :return: sim.PowerFlowOptions
        """

        tolerance = 1.0 / (10.0 ** self.ui.tolerance_spinBox.value())

        if self.ui.apply_impedance_tolerances_checkBox.isChecked():
            branch_impedance_tolerance_mode = BranchImpedanceMode.Upper
        else:
            branch_impedance_tolerance_mode = BranchImpedanceMode.Specified

        ops = sim.PowerFlowOptions(
            solver_type=self.solvers_dict[self.ui.solver_comboBox.currentText()],
            retry_with_other_methods=self.ui.helm_retry_checkBox.isChecked(),
            verbose=self.ui.verbositySpinBox.value(),
            tolerance=tolerance,
            max_iter=self.ui.max_iterations_spinBox.value(),
            control_q=self.ui.control_q_checkBox.isChecked(),
            control_taps_phase=self.ui.control_tap_phase_checkBox.isChecked(),
            control_taps_modules=self.ui.control_tap_modules_checkBox.isChecked(),
            control_remote_voltage=self.ui.control_remote_voltage_checkBox.isChecked(),
            orthogonalize_controls=self.ui.orthogonalize_pf_controls_checkBox.isChecked(),
            apply_temperature_correction=self.ui.temperature_correction_checkBox.isChecked(),
            branch_impedance_tolerance_mode=branch_impedance_tolerance_mode,
            distributed_slack=self.ui.distributed_slack_checkBox.isChecked(),
            ignore_single_node_islands=self.ui.ignore_single_node_islands_checkBox.isChecked(),
            trust_radius=self.ui.muSpinBox.value(),
            use_stored_guess=self.ui.use_voltage_guess_checkBox.isChecked(),
            initialize_angles=self.ui.initialize_pf_angles_checkBox.isChecked(),
            generate_report=self.ui.addPowerFlowReportCheckBox.isChecked()
        )

        return ops

    def get_opf_results(self, use_opf: bool) -> sim.OptimalPowerFlowResults:
        """
        Get the current OPF results
        :param use_opf:
        :return:
        """
        if use_opf:

            drv, results = self.session.get_driver_results(SimulationTypes.OPF_run)

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
                drv, results = self.session.get_driver_results(SimulationTypes.OPF_NTC_run)

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

            _, opf_time_series_results = self.session.optimal_power_flow_ts

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
        if self.server_driver.is_running():
            if self.ts_flag():
                instruction = RemoteInstruction(operation=SimulationTypes.PowerFlowTimeSeries_run)
            else:
                instruction = RemoteInstruction(operation=SimulationTypes.PowerFlow_run)

            self.run_remote(instruction=instruction)

        else:
            if self.ts_flag():
                self.run_power_flow_time_series()
            else:
                self.run_power_flow()

    def optimal_power_flow_dispatcher(self):
        """
        Dispatch the optimal power flow action
        :return:
        """
        if self.server_driver.is_running():
            if self.ts_flag():
                instruction = RemoteInstruction(operation=SimulationTypes.OPFTimeSeries_run)
            else:
                instruction = RemoteInstruction(operation=SimulationTypes.OPF_run)

            self.run_remote(instruction=instruction)
        else:
            if self.ts_flag():
                self.run_opf_time_series()
            else:
                self.run_opf()

    def atc_dispatcher(self):
        """
        Dispatch the NTC action
        :return:
        """
        if self.server_driver.is_running():
            if self.ts_flag():
                instruction = RemoteInstruction(operation=SimulationTypes.NetTransferCapacityTS_run)
            else:
                instruction = RemoteInstruction(operation=SimulationTypes.NetTransferCapacity_run)

            self.run_remote(instruction=instruction)
        else:
            if self.ts_flag():
                self.run_available_transfer_capacity_ts()
            else:
                self.run_available_transfer_capacity()

    def optimal_ntc_opf_dispatcher(self):
        """
        Dispatch the optimal NTC action
        :return:
        """
        if self.server_driver.is_running():
            if self.ts_flag():
                instruction = RemoteInstruction(operation=SimulationTypes.NetTransferCapacityTS_run)
            else:
                instruction = RemoteInstruction(operation=SimulationTypes.NetTransferCapacity_run)

            self.run_remote(instruction=instruction)
        else:
            if self.ts_flag():
                self.run_opf_ntc_ts()
            else:
                self.run_opf_ntc()

    def linear_pf_dispatcher(self):
        """
        Dispatch the linear power flow action
        :return:
        """
        if self.server_driver.is_running():
            if self.ts_flag():
                instruction = RemoteInstruction(operation=SimulationTypes.LinearAnalysis_TS_run)
            else:
                instruction = RemoteInstruction(operation=SimulationTypes.LinearAnalysis_run)

            self.run_remote(instruction=instruction)
        else:
            if self.ts_flag():
                self.run_linear_analysis_ts()
            else:
                self.run_linear_analysis()

    def contingencies_dispatcher(self):
        """
        Dispatch the contingencies action
        :return:
        """
        if self.server_driver.is_running():
            if self.ts_flag():
                instruction = RemoteInstruction(operation=SimulationTypes.ContingencyAnalysisTS_run)
            else:
                instruction = RemoteInstruction(operation=SimulationTypes.ContingencyAnalysis_run)

            self.run_remote(instruction=instruction)

        else:
            if self.ts_flag():
                self.run_contingency_analysis_ts()
            else:
                self.run_contingency_analysis()

    def reliability_dispatcher(self):
        """
        Dispatch the reliability action
        :return:
        """
        if self.server_driver.is_running():
            instruction = RemoteInstruction(operation=SimulationTypes.Reliability_run)
            self.run_remote(instruction=instruction)

        else:
            self.run_reliability()

    def run_power_flow(self):
        """
        Run a power flow simulation
        :return:
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.PowerFlow_run):

                self.LOCK()

                self.add_simulation(SimulationTypes.PowerFlow_run)

                self.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()

                # get the power flow options from the GUI
                options = self.get_selected_power_flow_options()

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
                self.show_warning_toast('Another simulation of the same type is running...')
        else:
            pass

    def post_power_flow(self):
        """
        Action performed after the power flow.
        Returns:

        """
        # update the results in the circuit structures

        _, results = self.session.power_flow

        if results is not None:
            self.ui.progress_label.setText('Colouring power flow results in the grid...')
            self.remove_simulation(SimulationTypes.PowerFlow_run)
            self.update_available_results()
            self.colour_diagrams()

            if results.converged:
                self.show_info_toast("Power flow converged :)")
            else:
                self.show_warning_toast("Power flow not converged :/")

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
        if self.circuit.valid_for_simulation():
            if not self.session.is_this_running(SimulationTypes.ShortCircuit_run):

                _, pf_results = self.session.power_flow

                if pf_results is not None:

                    # Since we must run this study in the same conditions as
                    # the last power flow, no compilation is needed

                    # get the short circuit selected buses
                    sel_buses = list()
                    self_short_circuit_types = list()

                    for diagram_widget in self.diagram_widgets_list:

                        if isinstance(diagram_widget, SchematicWidget):

                            for i, bus, graphic_object in diagram_widget.get_buses():
                                if isinstance(graphic_object, BusGraphicItem):
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
                        self.add_simulation(SimulationTypes.ShortCircuit_run)

                        self.LOCK()

                        if self.ui.apply_impedance_tolerances_checkBox.isChecked():
                            branch_impedance_tolerance_mode = BranchImpedanceMode.Lower
                        else:
                            branch_impedance_tolerance_mode = BranchImpedanceMode.Specified

                        # get the power flow options from the GUI
                        sc_options = sim.ShortCircuitOptions(bus_index=sel_buses[0],
                                                             fault_type=self_short_circuit_types[0])

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
        _, results = self.session.short_circuit

        if results is not None:

            self.ui.progress_label.setText('Colouring short circuit results in the grid...')
            self.remove_simulation(SimulationTypes.ShortCircuit_run)
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
        if self.circuit.valid_for_simulation():
            if not self.session.is_this_running(SimulationTypes.LinearAnalysis_run):

                self.add_simulation(SimulationTypes.LinearAnalysis_run)

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
                self.show_warning_toast('Another PTDF is being executed now...')
        else:
            pass

    def post_linear_analysis(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        self.remove_simulation(SimulationTypes.LinearAnalysis_run)

        # update the results in the circuit structures
        _, results = self.session.linear_power_flow
        if results is not None:

            self.ui.progress_label.setText('Colouring PTDF results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()
            self.colour_diagrams()
        else:
            self.show_warning_toast('Something went wrong, There are no PTDF results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_linear_analysis_ts(self):
        """
        Run PTDF time series simulation
        """
        if self.circuit.valid_for_simulation():
            if self.valid_time_series():
                if not self.session.is_this_running(SimulationTypes.LinearAnalysis_TS_run):

                    self.add_simulation(SimulationTypes.LinearAnalysis_TS_run)
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
                self.show_warning_toast('There are no time series...')

    def post_linear_analysis_ts(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        self.remove_simulation(SimulationTypes.LinearAnalysis_TS_run)

        # update the results in the circuit structures
        _, results = self.session.linear_power_flow_ts
        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            self.ui.progress_label.setText('Colouring PTDF results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()

            if results.S.shape[0] > 0:
                self.colour_diagrams()
            else:
                self.show_warning_toast('Cannot colour because the PTDF results have zero time steps :/')

        else:
            self.show_warning_toast('Something went wrong, There are no PTDF Time series results.')

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
            contingency_method=self.contingency_engines_dict[self.ui.contingencyEngineComboBox.currentText()],
            contingency_groups=self.get_contingency_groups_matching_the_filter()
        )

        return options

    def run_contingency_analysis(self):
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if self.circuit.valid_for_simulation():

            if len(self.circuit.contingency_groups) > 0:

                if not self.session.is_this_running(SimulationTypes.ContingencyAnalysis_run):

                    self.add_simulation(SimulationTypes.ContingencyAnalysis_run)

                    self.LOCK()

                    drv = sim.ContingencyAnalysisDriver(grid=self.circuit,
                                                        options=self.get_contingency_options(),
                                                        linear_multiple_contingencies=None,  # it initializes inside
                                                        engine=self.get_preferred_engine())

                    self.session.run(drv,
                                     post_func=self.post_contingency_analysis,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                else:
                    self.show_warning_toast('Another contingency analysis is being executed now...')

            else:
                self.show_warning_toast('There are no contingency groups declared...')
        else:
            pass

    def post_contingency_analysis(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        self.remove_simulation(SimulationTypes.ContingencyAnalysis_run)

        # update the results in the circuit structures
        _, results = self.session.contingency
        if results is not None:

            self.ui.progress_label.setText('Colouring contingency analysis results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()

            self.colour_diagrams()
        else:
            self.show_error_toast('Something went wrong, There are no contingency analysis results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_contingency_analysis_ts(self) -> None:
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if self.circuit.valid_for_simulation():

            if len(self.circuit.contingency_groups) > 0:

                if self.valid_time_series():
                    if not self.session.is_this_running(SimulationTypes.ContingencyAnalysisTS_run):

                        self.add_simulation(SimulationTypes.ContingencyAnalysisTS_run)

                        self.LOCK()

                        drv = sim.ContingencyAnalysisTimeSeriesDriver(grid=self.circuit,
                                                                      options=self.get_contingency_options(),
                                                                      time_indices=self.get_time_indices(),
                                                                      clustering_results=self.get_clustering_results(),
                                                                      engine=self.get_preferred_engine())

                        self.session.run(drv,
                                         post_func=self.post_contingency_analysis_ts,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)
                    else:
                        self.show_warning_toast('Another LODF is being executed now...')
                else:
                    self.show_warning_toast('There are no time series...')

            else:
                self.show_warning_toast('There are no contingency groups declared...')

        else:
            pass

    def post_contingency_analysis_ts(self) -> None:
        """
        Action performed after the short circuit.
        Returns:

        """
        self.remove_simulation(SimulationTypes.ContingencyAnalysisTS_run)

        # update the results in the circuit structures
        _, results = self.session.contingency_ts
        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            self.ui.progress_label.setText('Colouring results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()

            self.colour_diagrams()
        else:
            self.show_error_toast('Something went wrong, There are no contingency time series results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_available_transfer_capacity(self):
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.NetTransferCapacity_run):
                distributed_slack = self.ui.distributed_slack_checkBox.isChecked()
                dT = 1.0
                threshold = self.ui.atcThresholdSpinBox.value()
                max_report_elements = 5  # TODO: self.ui.ntcReportLimitingElementsSpinBox.value()
                # available transfer capacity inter areas
                info: dev.InterAggregationInfo = self.get_compatible_from_to_buses_and_inter_branches()

                if not info.valid:
                    return

                idx_from = info.idx_bus_from
                idx_to = info.idx_bus_to
                idx_br = info.idx_branches
                sense_br = info.sense_branches

                # HVDC
                idx_hvdc_br = info.idx_hvdc
                sense_hvdc_br = info.sense_hvdc

                if self.ui.usePfValuesForAtcCheckBox.isChecked():
                    _, pf_results = self.session.power_flow
                    if pf_results is not None:
                        Pf = pf_results.Sf.real
                        Pf_hvdc = pf_results.Pf_hvdc.real
                        use_provided_flows = True
                    else:
                        self.show_warning_toast('There were no power flow values available. Linear flows will be used.')
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
                self.add_simulation(SimulationTypes.NetTransferCapacity_run)
                self.LOCK()

            else:
                self.show_warning_toast('Another contingency analysis is being executed now...')

        else:
            pass

    def post_available_transfer_capacity(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        self.remove_simulation(SimulationTypes.NetTransferCapacity_run)
        _, results = self.session.net_transfer_capacity

        # update the results in the circuit structures
        if results is not None:

            self.ui.progress_label.setText('Colouring ATC results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()
            self.colour_diagrams()
        else:
            self.show_error_toast('Something went wrong, There are no ATC results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_available_transfer_capacity_ts(self, use_clustering=False):
        """
        Run a Power Transfer Distribution Factors analysis
        :return:
        """
        if self.circuit.valid_for_simulation():

            if self.valid_time_series():
                if not self.session.is_this_running(SimulationTypes.NetTransferCapacity_run):

                    distributed_slack = self.ui.distributed_slack_checkBox.isChecked()
                    dT = 1.0
                    threshold = self.ui.atcThresholdSpinBox.value()
                    max_report_elements = 5  # TODO: self.ui.ntcReportLimitingElementsSpinBox.value()

                    # available transfer capacity inter areas
                    info: dev.InterAggregationInfo = self.get_compatible_from_to_buses_and_inter_branches()

                    if not info.valid:
                        return

                    idx_from = info.idx_bus_from
                    idx_to = info.idx_bus_to
                    idx_br = info.idx_branches
                    sense_br = info.sense_branches

                    # HVDC
                    idx_hvdc_br = info.idx_hvdc
                    sense_hvdc_br = info.sense_hvdc

                    if self.ui.usePfValuesForAtcCheckBox.isChecked():
                        _, pf_results = self.session.power_flow_ts
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
                    self.add_simulation(SimulationTypes.NetTransferCapacityTS_run)
                    self.LOCK()

                else:
                    self.show_warning_toast('Another ATC time series is being executed now...')
            else:
                self.show_warning_toast('There are no time series!')
        else:
            pass

    def post_available_transfer_capacity_ts(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        self.remove_simulation(SimulationTypes.NetTransferCapacityTS_run)

        # update the results in the circuit structures
        _, results = self.session.net_transfer_capacity_ts
        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            self.ui.progress_label.setText('Colouring ATC time series results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()
            self.colour_diagrams()
        else:
            self.show_error_toast('Something went wrong, There are no ATC time series results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_continuation_power_flow(self):
        """
        Run voltage stability (voltage collapse) in a separated thread
        :return:
        """

        if self.circuit.valid_for_simulation():

            pf_drv, pf_results = self.session.power_flow

            if pf_results is not None:

                if not self.session.is_this_running(SimulationTypes.ContinuationPowerFlow_run):

                    # get the selected UI options
                    use_alpha = self.ui.start_vs_from_default_radioButton.isChecked()

                    # direction vector
                    alpha = self.ui.alpha_doubleSpinBox.value()
                    n = len(self.circuit.buses)

                    # vector that multiplies the target power: The continuation direction
                    alpha_vec = np.ones(n)

                    if self.ui.atcRadioButton.isChecked():
                        use_alpha = True
                        info: dev.InterAggregationInfo = self.get_compatible_from_to_buses_and_inter_branches()

                        if info.valid:
                            idx_from = info.idx_bus_from
                            idx_to = info.idx_bus_to

                            alpha_vec[idx_from] *= 2
                            alpha_vec[idx_to] *= -2
                            sel_bus_idx = np.zeros(0, dtype=int)  # for completeness

                            # HVDC
                            idx_hvdc_br = info.idx_hvdc
                            sense_hvdc_br = info.sense_hvdc
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
                                                                  verbose=0)

                    if use_alpha:
                        """
                        use the current power situation as start
                        and a linear combination of the current situation as target
                        """
                        # lock the UI
                        self.LOCK()

                        self.ui.progress_label.setText('Compiling the grid...')
                        QtGui.QGuiApplication.processEvents()

                        #  compose the base power
                        Sbase: CxVec = pf_results.Sbus / self.circuit.Sbase

                        base_overload_number = len(np.where(np.abs(pf_results.loading) > 1)[0])

                        vc_inputs = sim.ContinuationPowerFlowInput(Sbase=Sbase,
                                                                   Vbase=pf_results.voltage,
                                                                   Starget=Sbase * alpha,
                                                                   base_overload_number=base_overload_number)

                        pf_options = self.get_selected_power_flow_options()

                        # create object
                        drv = sim.ContinuationPowerFlowDriver(grid=self.circuit,
                                                              options=vc_options,
                                                              inputs=vc_inputs,
                                                              pf_options=pf_options)
                        self.session.run(drv,
                                         post_func=self.post_continuation_power_flow,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)

                    elif use_profiles:
                        """
                        Here the start and finish power states are taken from the profiles
                        """
                        if start_idx > -1 and end_idx > -1:

                            # lock the UI
                            self.LOCK()

                            nc_start = compile_numerical_circuit_at(circuit=self.circuit, t_idx=start_idx)
                            Sbus_init = nc_start.get_power_injections_pu()

                            nc_end = compile_numerical_circuit_at(circuit=self.circuit, t_idx=start_idx)
                            Sbus_end = nc_end.get_power_injections_pu()

                            pf_drv_start = sim.PowerFlowDriver(grid=self.circuit, options=pf_options)
                            pf_drv_start.run()

                            # get the power Injections array to get the initial and end points
                            vc_inputs = sim.ContinuationPowerFlowInput(Sbase=Sbus_init,
                                                                       Vbase=pf_drv_start.results.voltage,
                                                                       Starget=Sbus_end)

                            pf_options = self.get_selected_power_flow_options()

                            # create object
                            drv = sim.ContinuationPowerFlowDriver(grid=self.circuit,
                                                                  options=vc_options,
                                                                  inputs=vc_inputs,
                                                                  pf_options=pf_options)
                            self.session.run(drv,
                                             post_func=self.post_continuation_power_flow,
                                             prog_func=self.ui.progressBar.setValue,
                                             text_func=self.ui.progress_label.setText)
                        else:
                            self.show_warning_toast('Check the selected start and finnish time series indices.')
                else:
                    self.show_warning_toast('Another voltage collapse simulation is running...')
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
        _, results = self.session.continuation_power_flow

        if results is not None:

            self.remove_simulation(SimulationTypes.ContinuationPowerFlow_run)

            if results.voltages is not None:
                self.update_available_results()
                self.colour_diagrams()
            else:
                self.show_warning_toast('The voltage stability did not converge.\n'
                                        'Is this case already at the collapse limit?', 5000)
        else:
            self.show_error_toast('Something went wrong, There are no voltage stability results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_power_flow_time_series(self):
        """
        Run a time series power flow simulation in a separated thread from the gui
        @return:
        """
        if self.circuit.valid_for_simulation():
            if not self.session.is_this_running(SimulationTypes.PowerFlowTimeSeries_run):
                if self.valid_time_series():
                    self.LOCK()

                    self.add_simulation(SimulationTypes.PowerFlowTimeSeries_run)

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
                    self.show_warning_toast('There are no time series.')
            else:
                self.show_warning_toast('Another time series power flow is being executed now...')
        else:
            pass

    def post_power_flow_time_series(self):
        """
        Events to do when the time series simulation has finished
        @return:
        """

        _, results = self.session.power_flow_ts

        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            self.remove_simulation(SimulationTypes.PowerFlowTimeSeries_run)

            self.update_available_results()

            self.colour_diagrams()

        else:
            self.show_warning_toast('No results for the time series simulation.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_stochastic(self):
        """
        Run a Monte Carlo simulation
        @return:
        """

        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.MonteCarlo_run):

                if self.circuit.time_profile is not None:

                    self.LOCK()

                    self.add_simulation(SimulationTypes.StochasticPowerFlow)

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
                    self.show_warning_toast('There are no time series.')

            else:
                self.show_warning_toast('Another Monte Carlo simulation is running...')

        else:
            pass

    def post_stochastic(self):
        """
        Actions to perform after the Monte Carlo simulation is finished
        @return:
        """

        _, results = self.session.stochastic_power_flow

        if results is not None:

            self.remove_simulation(SimulationTypes.StochasticPowerFlow)

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
        self.remove_simulation(SimulationTypes.Cascade_run)

        _, results = self.session.cascade
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

    def get_opf_options(self) -> Union[None, sim.OptimalPowerFlowOptions]:
        """
        Get the GUI OPF options
        """
        # get the power flow options from the GUI
        solver = self.lp_solvers_dict[self.ui.lpf_solver_comboBox.currentText()]
        mip_solver = self.mip_solvers_dict.get(self.ui.mip_solver_comboBox.currentText(), MIPSolvers.HIGHS.value)
        time_grouping = self.opf_time_groups[self.ui.opf_time_grouping_comboBox.currentText()]
        zonal_grouping = self.opf_zonal_groups[self.ui.opfZonalGroupByComboBox.currentText()]
        pf_options = self.get_selected_power_flow_options()
        consider_contingencies = self.ui.considerContingenciesOpfCheckBox.isChecked()
        contingency_groups_used = self.get_contingency_groups_matching_the_filter()
        skip_generation_limits = self.ui.skipOpfGenerationLimitsCheckBox.isChecked()
        lodf_tolerance = self.ui.opfContingencyToleranceSpinBox.value()
        maximize_flows = self.ui.opfMaximizeExcahngeCheckBox.isChecked()
        unit_commitment = self.ui.opfUnitCommitmentCheckBox.isChecked()
        generate_report = self.ui.addOptimalPowerFlowReportCheckBox.isChecked()
        robust = self.ui.fixOpfCheckBox.isChecked()
        generation_expansion_planning = self.ui.opfGEPCheckBox.isChecked()

        if self.ui.save_mip_checkBox.isChecked():
            folder = opf_file_path()
            dte_str = str(datetime.datetime.now()).replace(":", "_").replace("/", "-")
            fname = f'mip_{self.circuit.name}_{dte_str}.lp'
            export_model_fname = os.path.join(folder, fname)
        else:
            export_model_fname = None

        # available transfer capacity inter areas
        if maximize_flows:
            inter_aggregation_info: dev.InterAggregationInfo = self.get_compatible_from_to_buses_and_inter_branches()

            if len(inter_aggregation_info.lst_from) == 0:
                self.show_error_toast('The area "from" has no buses!', 5000)
                return None

            if len(inter_aggregation_info.lst_to) == 0:
                self.show_error_toast('The area "to" has no buses!', 5000)
                return None
        else:
            inter_aggregation_info = None

        ips_method = self.ips_solvers_dict[self.ui.ips_method_comboBox.currentText()]
        ips_tolerance = 1.0 / (10.0 ** self.ui.ips_tolerance_spinBox.value())
        ips_iterations = self.ui.ips_iterations_spinBox.value()
        ips_trust_radius = self.ui.ips_trust_radius_doubleSpinBox.value()
        ips_init_with_pf = self.ui.ips_initialize_with_pf_checkBox.isChecked()
        ips_control_q_limits = self.ui.ips_control_Qlimits_checkBox.isChecked()

        verbose = self.ui.ips_verbose_spinBox.value()

        options = sim.OptimalPowerFlowOptions(solver=solver,
                                              time_grouping=time_grouping,
                                              zonal_grouping=zonal_grouping,
                                              mip_solver=mip_solver,
                                              power_flow_options=pf_options,
                                              consider_contingencies=consider_contingencies,
                                              contingency_groups_used=contingency_groups_used,
                                              skip_generation_limits=skip_generation_limits,
                                              lodf_tolerance=lodf_tolerance,
                                              maximize_flows=maximize_flows,
                                              inter_aggregation_info=inter_aggregation_info,
                                              unit_commitment=unit_commitment,
                                              generation_expansion_planning=generation_expansion_planning,
                                              export_model_fname=export_model_fname,
                                              generate_report=generate_report,
                                              ips_method=ips_method,
                                              ips_tolerance=ips_tolerance,
                                              ips_iterations=ips_iterations,
                                              ips_trust_radius=ips_trust_radius,
                                              ips_init_with_pf=ips_init_with_pf,
                                              ips_control_q_limits=ips_control_q_limits,
                                              robust=robust,
                                              verbose=verbose)

        return options

    def run_opf(self):
        """
        Run OPF simulation
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.OPF_run):

                self.remove_simulation(SimulationTypes.OPF_run)

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
                self.show_warning_toast('Another OPF is being run...')
        else:
            pass

    def post_opf(self):
        """
        Actions to run after the OPF simulation
        """
        _, results = self.session.optimal_power_flow

        if results is not None:

            self.remove_simulation(SimulationTypes.OPF_run)

            if results.converged:
                self.show_info_toast("Optimal power flow converged :)")
            else:
                self.show_warning_toast('Power flow not converged :/\n'
                                        'Check that all Branches have rating and \n'
                                        'that the generator bounds are ok.\n'
                                        'You may also use the diagnostic tool (F8)',
                                        duration=4000)

            self.update_available_results()

            self.colour_diagrams()

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_opf_time_series(self):
        """
        OPF Time Series run
        """
        if self.circuit.valid_for_simulation():

            if self.circuit.has_time_series:
                if not self.session.is_this_running(SimulationTypes.OPFTimeSeries_run):

                    if self.circuit.time_profile is not None:

                        self.add_simulation(SimulationTypes.OPFTimeSeries_run)

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
                        self.show_warning_toast('There are no time series...')

                else:
                    self.show_warning_toast('Another OPF time series is running already...')
            else:
                self.show_error_toast("The grid doesn't have time series :/")
        else:
            self.show_warning_toast('Nothing to simulate...')

    def post_opf_time_series(self):
        """
        Post OPF Time Series
        """

        _, results = self.session.optimal_power_flow_ts

        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            # delete from the current simulations
            self.remove_simulation(SimulationTypes.OPFTimeSeries_run)

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
        if self.circuit.valid_for_simulation():

            if self.circuit.time_profile is not None:

                _, results = self.session.optimal_power_flow_ts

                if results is not None:

                    quit_msg = ("Are you sure that you want overwrite the time events "
                                "with the simulated by the OPF time series?")
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
                self.show_warning_toast('There are no time series...')
        else:
            pass

    def get_opf_ntc_options(self) -> Union[None, sim.OptimalNetTransferCapacityOptions]:
        """

        :return:
        """

        # available transfer capacity inter areas
        info: dev.InterAggregationInfo = self.get_compatible_from_to_buses_and_inter_branches()

        if not info.valid:
            error_msg('There are no compatible areas')
            return None

        idx_from = info.idx_bus_from
        idx_to = info.idx_bus_to
        idx_br = info.idx_branches

        # HVDC
        idx_hvdc_br = info.idx_hvdc
        sense_hvdc_br = info.sense_hvdc

        if len(idx_from) == 0:
            error_msg('The "from" aggregation has no buses!')
            return None

        if len(idx_to) == 0:
            error_msg('The area "to" has no buses!')
            return None

        if (len(idx_br) + len(idx_hvdc_br)) == 0:
            error_msg('There are no inter-area Branches!')
            return None

        opts = sim.OptimalNetTransferCapacityOptions(
            sending_bus_idx=idx_from,
            receiving_bus_idx=idx_to,
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
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.OPF_NTC_run):

                self.remove_simulation(SimulationTypes.OPF_NTC_run)

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
                self.show_warning_toast('Another OPF is being run...')
        else:
            pass

    def post_opf_ntc(self):
        """
        Actions to run after the OPF simulation
        """
        drv, results = self.session.optimal_net_transfer_capacity

        if results is not None:
            self.remove_simulation(SimulationTypes.OPF_NTC_run)
            self.update_available_results()
            self.colour_diagrams()

            if results.converged:
                if drv.logger.error_count() == 0:
                    self.show_info_toast("Optimal result")
                else:
                    self.show_warning_toast("Optimal result with errors :/")
            else:
                self.show_warning_toast("Not optimal result :/")

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_opf_ntc_ts(self):
        """
        Run OPF NTC time series simulation
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.OPF_NTC_TS_run):

                self.remove_simulation(SimulationTypes.OPF_NTC_TS_run)

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
                self.show_warning_toast('Another Optimal NCT time series is being run...')
        else:
            pass

    def post_opf_ntc_ts(self):
        """
        Actions to run after the optimal net transfer capacity time series simulation
        """

        _, results = self.session.optimal_net_transfer_capacity_ts

        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            # delete from the current simulations
            self.remove_simulation(SimulationTypes.OPF_NTC_TS_run)

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

            _, ptdf_results = self.session.linear_power_flow

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
                self.show_error_toast('There are no PTDF results :/')

        else:
            # delete_with_dialogue the markers
            self.clear_big_bus_markers()

    def post_run_find_node_groups(self):
        """
        Colour the grid after running the node grouping
        :return:
        """
        self.UNLOCK()
        print('\nGroups:')

        drv, _ = self.session.node_groups_driver

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
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.InputsAnalysis_run):

                self.remove_simulation(SimulationTypes.InputsAnalysis_run)

                # set power flow object instance
                drv = sim.InputsAnalysisDriver(self.circuit)

                self.LOCK()
                self.session.run(drv,
                                 post_func=self.post_inputs_analysis,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                self.show_warning_toast('Another inputs analysis is being run...')
        else:
            pass

    def post_inputs_analysis(self):
        """

        :return:
        """
        _, results = self.session.inputs_analysis

        if results is not None:
            self.remove_simulation(SimulationTypes.InputsAnalysis_run)
            self.update_available_results()
            self.colour_diagrams()

        if not self.session.is_anything_running():
            self.UNLOCK()

    def storage_location(self):
        """
        Add storage markers to the schematic
        """

        if self.circuit.valid_for_simulation():

            if self.ui.actionStorage_location_suggestion.isChecked():

                _, ts_results = self.session.power_flow_ts

                if ts_results is not None:

                    # perform a time series analysis
                    ts_analysis = grid_analysis.TimeSeriesResultsAnalysis(self.circuit, ts_results)

                    # get the indices of the buses selected for storage
                    idx = np.where(ts_analysis.buses_selected_for_storage_frequency > 0)[0]

                    if len(idx) > 0:

                        frequencies = ts_analysis.buses_selected_for_storage_frequency[idx]

                        fmax = np.max(frequencies)

                        # prepare the color map
                        seq: List[Tuple[float, str]] = [(0, 'green'),
                                                        (0.6, 'orange'),
                                                        (1.0, 'red')]
                        cmap = LinearSegmentedColormap.from_list(name='vcolors', colors=seq)

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

                # delete_with_dialogue the red dots
                self.clear_big_bus_markers()
        else:
            pass

    def run_sigma_analysis(self):
        """
        Run the sigma analysis
        """
        if self.circuit.valid_for_simulation():
            options = self.get_selected_power_flow_options()
            bus_names = np.array([b.name for b in self.circuit.buses])
            sigma_driver = sim.SigmaAnalysisDriver(grid=self.circuit, options=options)
            sigma_driver.run()

            if not sigma_driver.results.converged:
                self.show_error_toast("Sigma coefficients did not converge :(")

            self.sigma_dialogue = SigmaAnalysisGUI(parent=self,
                                                   results=sigma_driver.results,
                                                   bus_names=bus_names)
            self.sigma_dialogue.resize(int(1.61 * 600.0), 550)  # golden ratio
            self.sigma_dialogue.show()  # exec leaves the parent on hold

    def run_investments_evaluation(self) -> None:
        """
        Run investments evaluation
        """
        if self.circuit.valid_for_simulation():

            if len(self.circuit.investments_groups) > 0:

                if not self.session.is_this_running(SimulationTypes.InvestmentsEvaluation_run):

                    if self.ui.internal_investment_methods_radioButton.isChecked():
                        # evaluation method
                        method = self.investment_evaluation_method_dict[
                            self.ui.investment_evaluation_method_ComboBox.currentText()
                        ]

                        obj_fn_tpe = self.investment_evaluation_objfunc_dict[
                            self.ui.investment_evaluation_objfunc_ComboBox.currentText()
                        ]

                        fn_ptr = None

                    elif self.ui.plugins_investment_methods_radioButton.isChecked():

                        method = InvestmentEvaluationMethod.FromPlugin
                        obj_fn_tpe = InvestmentsEvaluationObjectives.FromPlugin
                        fn_ptr = self.plugins_investment_evaluation_method_dict[
                            self.ui.plugins_investment_evaluation_method_ComboBox.currentText()
                        ]
                    else:
                        raise Exception("Unrecognized investment simulation mode")

                    # maximum number of function evaluations as a factor of the number of investments
                    max_eval = self.ui.max_investments_evluation_number_spinBox.value() * len(
                        self.circuit.investments_groups)

                    # compose the options
                    options = sim.InvestmentsEvaluationOptions(solver=method,
                                                               max_eval=max_eval,
                                                               pf_options=self.get_selected_power_flow_options(),
                                                               opf_options=self.get_opf_options(),
                                                               obj_tpe=obj_fn_tpe,
                                                               plugin_fcn_ptr=fn_ptr
                                                               )

                    if obj_fn_tpe == InvestmentsEvaluationObjectives.PowerFlow:
                        problem = sim.PowerFlowInvestmentProblem(
                            grid=self.circuit,
                            pf_options=self.get_selected_power_flow_options()
                        )

                    elif obj_fn_tpe == InvestmentsEvaluationObjectives.TimeSeriesPowerFlow:
                        problem = sim.TimeSeriesPowerFlowInvestmentProblem(
                            grid=self.circuit,
                            pf_options=self.get_selected_power_flow_options(),
                            time_indices=self.get_time_indices(),
                            clustering_results=self.get_clustering_results(),
                            opf_time_series_results=self.get_opf_ts_results(
                                use_opf=self.ui.actionOpf_to_Power_flow.isChecked()
                            ),
                            engine=self.get_preferred_engine()
                        )

                    elif obj_fn_tpe == InvestmentsEvaluationObjectives.GenerationAdequacy:

                        if self.circuit.has_time_series:
                            problem = sim.AdequacyInvestmentProblem(
                                grid=self.circuit,
                                n_monte_carlo_sim=self.ui.max_iterations_reliability_spinBox.value(),
                                use_monte_carlo=True,
                                save_file=False,
                                time_indices=self.get_time_indices()
                            )
                        else:
                            self.show_warning_toast('Adequacy studies need time data...')
                            return

                    elif obj_fn_tpe == InvestmentsEvaluationObjectives.SimpleDispatch:

                        if self.circuit.has_time_series:
                            problem = sim.AdequacyInvestmentProblem(
                                grid=self.circuit,
                                n_monte_carlo_sim=self.ui.max_iterations_reliability_spinBox.value(),
                                use_monte_carlo=False,
                                save_file=False,
                                time_indices=self.get_time_indices()
                            )
                        else:
                            self.show_warning_toast('Adequacy studies need time data...')
                            return

                    else:
                        self.show_error_toast("Objective not supported yet :/")
                        return

                    drv = sim.InvestmentsEvaluationDriver(
                        grid=self.circuit,
                        options=options,
                        problem=problem
                    )

                    self.session.run(
                        drv,
                        post_func=self.post_run_investments_evaluation,
                        prog_func=self.ui.progressBar.setValue,
                        text_func=self.ui.progress_label.setText
                    )
                    self.add_simulation(SimulationTypes.InvestmentsEvaluation_run)
                    self.LOCK()

                else:
                    self.show_warning_toast('Another contingency analysis is being executed now...')
            else:
                warning_msg("There are no investment groups, "
                            "you need to create some so that GridCal can evaluate them ;)")

        else:
            pass

    def post_run_investments_evaluation(self) -> None:
        """
        Post investments evaluation
        """
        _, results = self.session.investments_evaluation

        # update the results in the circuit structures
        if results is not None:
            self.remove_simulation(SimulationTypes.InvestmentsEvaluation_run)

            self.ui.progress_label.setText('Colouring investments evaluation results in the grid...')
            QtGui.QGuiApplication.processEvents()

            self.update_available_results()
            self.colour_diagrams()
        else:
            self.show_error_toast('Something went wrong, There are no investments evaluation results.')

        if not self.session.is_anything_running():
            self.UNLOCK()

    def get_clustering_results(self) -> Union[sim.ClusteringResults, None]:
        """
        Get the clustering results if available
        :return: ClusteringResults or None
        """
        if self.ui.actionUse_clustering.isChecked():
            _, clustering_results = self.session.clustering

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
                self.show_warning_toast("There are no clustering results.")
                self.ui.actionUse_clustering.setChecked(False)
                return None

        else:
            # not marked ...
            return None

    def run_clustering(self):
        """
        Run a clustering analysis
        """
        if self.circuit.valid_for_simulation() > 0 and self.circuit.get_time_number() > 0:

            if not self.session.is_this_running(SimulationTypes.ClusteringAnalysis_run):

                n_points = self.ui.cluster_number_spinBox.value()
                nt = self.circuit.get_time_number()
                if n_points < nt:

                    self.add_simulation(SimulationTypes.ClusteringAnalysis_run)

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
                self.show_warning_toast('Another clustering is being executed now...')
        else:
            pass

    def post_clustering(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        # update the results in the circuit structures
        self.remove_simulation(SimulationTypes.ClusteringAnalysis_run)

        _, results = self.session.clustering
        if results is not None:

            self.update_available_results()
        else:
            self.show_error_toast('Something went wrong, There are no power short circuit results.')

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

    def activate_clustering(self):
        """
        When activating the use of clustering, also activate time series
        :return:
        """
        if self.ui.actionUse_clustering.isChecked():

            # check if there are clustering results yet
            _, clustering_results = self.session.clustering

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
                self.show_warning_toast("There are no clustering results.")
                self.ui.actionUse_clustering.setChecked(False)
                return None

    def get_nodal_capacity_options(self) -> sim.NodalCapacityOptions:
        """
        Get the nodal capacity options
        :return: NodalCapacityOptions
        """

        bus_dict = self.circuit.get_bus_index_dict()
        sel_buses = self.get_selected_buses()
        capacity_nodes_idx = np.array([bus_dict[b] for _, b, _ in sel_buses])

        method = self.nodal_capacity_methods_dict[self.ui.nodal_capacity_method_comboBox.currentText()]

        opt = sim.NodalCapacityOptions(opf_options=self.get_opf_options(),
                                       capacity_nodes_idx=capacity_nodes_idx,
                                       method=method)

        return opt

    def run_nodal_capacity(self):
        """
        OPF Time Series run
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.NodalCapacityTimeSeries_run):

                # get the power flow options from the GUI
                options = self.get_nodal_capacity_options()

                if len(options.capacity_nodes_idx) == 0:
                    error_msg(text="For this simulation, you need to select some buses from the interface",
                              title="Nodal hosting capacity")
                    return

                if self.ts_flag():
                    time_indices = self.get_time_indices()
                    clustering_results = self.get_clustering_results()
                else:
                    # snapshot
                    time_indices = None
                    clustering_results = None

                self.add_simulation(SimulationTypes.NodalCapacityTimeSeries_run)

                self.LOCK()

                # Compile the grid
                self.ui.progress_label.setText('Compiling the grid...')
                QtGui.QGuiApplication.processEvents()

                if options is not None:
                    # create the OPF time series instance
                    # if non_sequential:
                    drv = sim.NodalCapacityTimeSeriesDriver(grid=self.circuit,
                                                            options=options,
                                                            time_indices=time_indices,
                                                            clustering_results=clustering_results)

                    drv.engine = self.get_preferred_engine()

                    self.session.run(drv,
                                     post_func=self.post_nodal_capacity,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)

            else:
                self.show_warning_toast('Another OPF time series is running already...')

        else:
            pass

    def post_nodal_capacity(self):
        """
        Post OPF Time Series
        """

        _, results = self.session.nodal_capacity_optimization_ts

        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            # delete from the current simulations
            self.remove_simulation(SimulationTypes.NodalCapacityTimeSeries_run)

            if results is not None:
                self.update_available_results()

                self.colour_diagrams()

        else:
            pass

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_reliability(self):
        """
        Run reliability study
        :return:
        """
        if self.circuit.valid_for_simulation():

            if self.circuit.get_time_number() > 0:

                if not self.session.is_this_running(SimulationTypes.Reliability_run):

                    self.add_simulation(SimulationTypes.Reliability_run)

                    self.LOCK()

                    # Compile the grid
                    self.ui.progress_label.setText('Compiling the grid...')
                    QtGui.QGuiApplication.processEvents()

                    pf_options = self.get_selected_power_flow_options()

                    drv = sim.ReliabilityStudyDriver(grid=self.circuit,
                                                     pf_options=pf_options,
                                                     time_indices=self.get_time_indices(),
                                                     n_sim=self.ui.max_iterations_reliability_spinBox.value())

                    self.session.run(drv,
                                     post_func=self.post_reliability,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)

                else:
                    self.show_warning_toast('Another reliability study is running already...')
            else:
                self.show_warning_toast('Reliability studies need time data...')
        else:
            pass

    def post_reliability(self):
        """

        :return:
        """
        _, results = self.session.reliability_analysis

        if results is not None:

            # delete from the current simulations
            self.remove_simulation(SimulationTypes.Reliability_run)

            if results is not None:
                self.update_available_results()
                self.colour_diagrams()
        else:
            pass

        if not self.session.is_anything_running():
            self.UNLOCK()

    def automatic_pf_precision(self):
        """
        Find the automatic tolerance
        :return:
        """
        tolerance, tol_idx = self.circuit.get_automatic_precision()

        if tol_idx > 12:
            tol_idx = 12

        self.ui.tolerance_spinBox.setValue(tol_idx)

    def run_remote(self, instruction):
        """
        Run remote simulation
        :param instruction:
        :return:
        """

        if self.server_driver.is_running():
            driver = RemoteJobDriver(grid=self.circuit,
                                     instruction=instruction,
                                     base_url=self.server_driver.base_url(),
                                     certificate_path=self.server_driver.get_certificate_path(),
                                     register_driver_func=self.session.register_driver)
            driver.done_signal.connect(self.post_run_remote)

            self._remote_jobs[driver.idtag] = driver

            driver.start()

    def post_run_remote(self, driver_idtag: str):
        """
        Function executed upon data reception complete
        :return:
        """
        print("Done!")

        remote_job_driver = self._remote_jobs.get(driver_idtag, None)

        if remote_job_driver is not None:
            if remote_job_driver.logger.has_logs():
                # Show dialogue
                dlg = LogsDialogue(name="Remote connection logs", logger=remote_job_driver.logger)
                dlg.setModal(True)
                dlg.exec()

            self.update_available_results()
            self.colour_diagrams()

            self._remote_jobs.pop(driver_idtag)

            self.show_info_toast(f"Remote results received!")
