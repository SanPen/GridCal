# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from typing import List, Tuple, Dict, Union

# GUI imports
from PySide6 import QtGui, QtCore, QtWidgets

import VeraGrid.Gui.gui_functions as gf
from VeraGrid.Gui.Visualization.visualization import NativeColorMap
from VeraGrid.Gui.i18n import translate_tree_label
from VeraGrid.Gui.general_dialogues import LogsDialogue
from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import MapWidget
from VeraGrid.Gui.messages import yes_no_question, error_msg, warning_msg, info_msg
from VeraGrid.Gui.Main.SubClasses.Model.time_events import TimeEventsMain
from VeraGrid.Gui.SigmaAnalysis.sigma_analysis_dialogue import SigmaAnalysisGUI
from VeraGrid.Gui.ProceduralGrid.procedural_grid import ProceduralGridWindow
from VeraGrid.Gui.ProceduralGrid.map_warning import MapWarningDialog
from VeraGrid.Gui.CandidateInvestments.candidate_investments import CandidateInvestmentsWindow
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely, exec_dialog_safely, is_dialog_available
from VeraGrid.Session.session import GcThread
from VeraGrid.Session.server_driver import RemoteJobDriver
from VeraGrid.Gui.Analysis.AnalysisDialogue import GridAnalysisGUI

# Engine imports
import VeraGridEngine.Devices as dev
import VeraGridEngine.Simulations as sim
import VeraGridEngine.Simulations.PowerFlow.grid_analysis as grid_analysis
from VeraGridEngine.Devices.types import AREA_TYPES
from VeraGridEngine.Utils.MIP.selected_interface import get_available_mip_solvers, get_available_mip_frameworks
from VeraGridEngine.IO.veragrid.remote import RemoteInstruction
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Simulations.types import DRIVER_OBJECTS
from VeraGridEngine.basic_structures import CxVec, IntVec, Vec
from VeraGridEngine.enumerations import (DeviceType, AvailableTransferMode, SolverType, MIPSolvers, TimeGrouping,
                                         ZonalGrouping, ContingencyMethod, InvestmentEvaluationMethod, EngineType,
                                         BranchImpedanceMode, ResultTypes, SimulationTypes, NodalCapacityMethod,
                                         SolutionState,
                                         ContingencyFilteringMethods, InvestmentsEvaluationObjectives,
                                         ReliabilityMode, OpfDispatchMode, DynamicIntegrationMethod,
                                         RmsInitializationMethod, EmtInitializationMethod, EmtSolverTypes,
                                         MethodShortCircuit, SmallSignalEmtBuildTypes,
                                         RmsProblemTypes, EmtProblemTypes)


def get_valid_controls_start_tolerance_index(tolerance_idx: int,
                                             controls_start_tolerance_idx: int,
                                             controls_start_tolerance_min_idx: int) -> int:
    """
    Keep the controls activation tolerance above the solver tolerance.

    :param tolerance_idx: Solver tolerance exponent shown as ``1e-idx``
    :param controls_start_tolerance_idx: Controls activation exponent shown as ``1e-idx``
    :param controls_start_tolerance_min_idx: Minimum exponent allowed by the GUI spin box
    :return: Valid controls activation exponent
    """
    if controls_start_tolerance_idx > tolerance_idx:
        # The GUI stores exponents, so ``tol * 100`` means subtracting two decades.
        adjusted_idx: int = tolerance_idx - 2

        # Clamp to the spin box minimum because the GUI cannot represent values larger than ``1e-1``.
        if adjusted_idx < controls_start_tolerance_min_idx:
            adjusted_idx = controls_start_tolerance_min_idx
        else:
            pass

        return adjusted_idx
    else:
        return controls_start_tolerance_idx


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

        # Snapshot of every Investment in the live circuit at the moment an
        # Investments-evaluation run finishes. The Variations-panel click handler
        # uses it to deactivate every investment-touched device first, and then
        # activate only the investments belonging to the clicked Pareto
        # combination — matching the convention the optimizer used internally
        # (an x vector of zeros = every investment off).
        # WARNING: snapshot semantic only. set_investments_status overwrites each
        # touched device's active *profile* (per-timestep) on every click. Any
        # pre-existing time-series active profile on these devices is lost
        # permanently after the first click. Save the project before exploring
        # combinations if the original profile shape matters.
        self._investments_all: List[dev.Investment] = list()

        # Power Flow Methods
        self.ui.se_solver_comboBox.setModel(
            gf.ComboModel(enum_values=[SolverType.NR,
                                       SolverType.LM,
                                       SolverType.GN],
                          translate=self.tr)
        )
        self.ui.se_solver_comboBox.setCurrentIndex(0)

        # SE Methods
        self.ui.solver_comboBox.setModel(
            gf.ComboModel(enum_values=[SolverType.NR,
                                       SolverType.IWAMOTO,
                                       SolverType.LM,
                                       SolverType.PowellDogLeg,
                                       SolverType.FASTDECOUPLED,
                                       SolverType.HELM,
                                       SolverType.GAUSS,
                                       SolverType.LACPF,
                                       SolverType.Linear],
                          translate=self.tr)
        )
        self.ui.solver_comboBox.setCurrentIndex(0)

        # transfer modes
        self.ui.transferMethodComboBox.setModel(
            gf.ComboModel(enum_values=[AvailableTransferMode.Generation,
                                       AvailableTransferMode.InstalledPower,
                                       AvailableTransferMode.Load,
                                       AvailableTransferMode.GenerationAndLoad],
                          translate=self.tr)
        )
        self.ui.transferMethodComboBox.setCurrentIndex(1)

        # opf solvers dictionary
        self.ui.lpf_solver_comboBox.setModel(
            gf.ComboModel(enum_values=[SolverType.LINEAR_OPF,
                                       SolverType.NONLINEAR_OPF,
                                       SolverType.GREEDY_DISPATCH_OPF],
                          translate=self.tr)
        )

        # opf dispatch methods
        self.ui.opfDispatchModeComboBox.setModel(
            gf.ComboModel(enum_values=[OpfDispatchMode.Normal,
                                       OpfDispatchMode.UnitCommitment,
                                       OpfDispatchMode.InterAreaRedispatch,
                                       OpfDispatchMode.GenerationExpansionPlanning],
                          translate=self.tr)
        )

        # MIP frameworks
        self.ui.mip_framework_comboBox.setModel(
            gf.ComboModel(enum_values=get_available_mip_frameworks(), translate=self.tr)
        )

        # reliability modes
        self.ui.reliability_method_comboBox.setModel(
            gf.ComboModel(enum_values=[ReliabilityMode.GenerationAdequacy,
                                       ReliabilityMode.GridMetrics],
                          translate=self.tr)
        )

        # ips solvers dictionary
        self.ui.ips_method_comboBox.setModel(
            gf.ComboModel(enum_values=[SolverType.NR, SolverType.NR_PC], translate=self.tr)
        )

        # the MIP combobox models assigning is done in modify_ui_options_according_to_the_engine
        self.ui.mip_solver_comboBox.setModel(
            gf.ComboModel(enum_values=[MIPSolvers.HIGHS,
                                       MIPSolvers.SCIP,
                                       MIPSolvers.CPLEX,
                                       MIPSolvers.GUROBI,
                                       MIPSolvers.XPRESS,
                                       MIPSolvers.CBC,
                                       MIPSolvers.PDLP],
                          translate=self.tr)
        )

        # opf solvers dictionary
        self.ui.nodal_capacity_method_comboBox.setModel(
            gf.ComboModel(enum_values=[NodalCapacityMethod.LinearOptimization,
                                       NodalCapacityMethod.NonlinearOptimization,
                                       NodalCapacityMethod.CPF],
                          translate=self.tr)
        )

        # branch types for reduction
        mdl = gf.get_list_model([DeviceType.LineDevice.value,
                                 DeviceType.SwitchDevice.value], checks=True)
        self.ui.removeByTypeListView.setModel(mdl)

        # OPF grouping modes
        self.ui.opf_time_grouping_comboBox.setModel(
            gf.ComboModel(enum_values=[TimeGrouping.NoGrouping,
                                       TimeGrouping.Monthly,
                                       TimeGrouping.Weekly,
                                       TimeGrouping.Daily,
                                       TimeGrouping.Hourly],
                          translate=self.tr)
        )

        # zonal opf grouping
        self.ui.opfZonalGroupByComboBox.setModel(
            gf.ComboModel(enum_values=[ZonalGrouping.NoGrouping,
                                       ZonalGrouping.All],
                          translate=self.tr)
        )

        # voltage collapse mode (full, nose)
        self.ui.vc_stop_at_comboBox.setModel(
            gf.ComboModel(enum_values=[sim.CpfStopAt.Nose,
                                       sim.CpfStopAt.ExtraOverloads],
                          translate=self.tr)
        )
        self.ui.vc_stop_at_comboBox.setCurrentIndex(0)

        # reactive power controls
        self.ui.contingencyEngineComboBox.setModel(
            gf.ComboModel(enum_values=[ContingencyMethod.PowerFlow,
                                       ContingencyMethod.Linear,
                                       ContingencyMethod.PTDF_scan,
                                       ContingencyMethod.HELM],
                          translate=self.tr)
        )

        # list of stochastic power flow methods
        self.ui.stochastic_pf_method_comboBox.setModel(
            gf.ComboModel(enum_values=[sim.StochasticPowerFlowType.LatinHypercube,
                                       sim.StochasticPowerFlowType.MonteCarlo],
                          translate=self.tr)
        )

        # investment evaluation methods
        self.ui.investment_evaluation_method_ComboBox.setModel(
            gf.ComboModel(enum_values=[InvestmentEvaluationMethod.CBA_PINT_TOOT,
                                       InvestmentEvaluationMethod.PINT_TOOT_NSGA3,
                                       InvestmentEvaluationMethod.NSGA3,
                                       InvestmentEvaluationMethod.MVRSM,
                                       InvestmentEvaluationMethod.MixedVariableGA],
                          translate=self.tr)
        )

        # contingency filtering modes
        self.ui.contingency_filter_by_comboBox.setModel(
            gf.ComboModel(enum_values=[ContingencyFilteringMethods.AllActive,
                                       ContingencyFilteringMethods.Country,
                                       ContingencyFilteringMethods.Community,
                                       ContingencyFilteringMethods.Region,
                                       ContingencyFilteringMethods.Municipality,
                                       ContingencyFilteringMethods.Area,
                                       ContingencyFilteringMethods.Zone,
                                       ContingencyFilteringMethods.SensitiveToMonitored],
                          translate=self.tr)
        )

        # investment modes
        self.ui.investment_evaluation_objfunc_ComboBox.setModel(
            gf.ComboModel(enum_values=[InvestmentsEvaluationObjectives.PowerFlow,
                                       InvestmentsEvaluationObjectives.TimeSeriesPowerFlow,
                                       InvestmentsEvaluationObjectives.LinearOptimalPowerFlowTimeSeries,
                                       InvestmentsEvaluationObjectives.OptimalPowerFlowThenPowerFlowTimeSeries,
                                       InvestmentsEvaluationObjectives.GenerationAdequacy,
                                       InvestmentsEvaluationObjectives.SimpleDispatch],
                          translate=self.tr)
        )

        # rms simulation
        self.ui.rms_integration_method_comboBox.setModel(
            gf.ComboModel(enum_values=[DynamicIntegrationMethod.DaeBackEuler,
                                       DynamicIntegrationMethod.DaeTrapezoidal,
                                       DynamicIntegrationMethod.DaeBDF2,
                                       DynamicIntegrationMethod.OdeEuler],
                          translate=self.tr)
        )

        self.ui.rms_initialization_method_comboBox.setModel(
            gf.ComboModel(enum_values=[RmsInitializationMethod.Explicit,
                                       RmsInitializationMethod.PseudoTransient],
                          translate=self.tr)

        )

        self.ui.rms_problem_comboBox.setModel(
            gf.ComboModel(enum_values=[RmsProblemTypes.PowerBalance,
                                       RmsProblemTypes.PowerBalanceVectorized],
                          translate=self.tr)

        )

        # emt simulation
        self.ui.emt_integration_method_comboBox.setModel(
            gf.ComboModel(enum_values=[DynamicIntegrationMethod.DaeTrapezoidal,
                                       DynamicIntegrationMethod.DaeBackEuler,
                                       DynamicIntegrationMethod.DaeBDF2],
                          translate=self.tr)
        )

        self.ui.emt_initialization_method_comboBox.setModel(
            gf.ComboModel(enum_values=[EmtInitializationMethod.Explicit,
                                       EmtInitializationMethod.ConsistentNewton,
                                       EmtInitializationMethod.PseudoTransient,
                                       EmtInitializationMethod.Auto],
                          translate=self.tr)
        )

        self.ui.emt_problem_comboBox.setModel(
            gf.ComboModel(enum_values=[EmtProblemTypes.CurrentBalance,
                                       EmtProblemTypes.CurrentBalance],
                          translate=self.tr)
        )

        self.ui.emt_solver_type_comboBox.setModel(
            gf.ComboModel(enum_values=[EmtSolverTypes.Symbolic,
                                       EmtSolverTypes.StructuralAD,
                                       EmtSolverTypes.StructuralCompiled,
                                       EmtSolverTypes.Automatic],
                          translate=self.tr)
        )

        # emt small-signal
        self.ui.emt_sss_build_type_comboBox.setModel(
            gf.ComboModel(enum_values=[SmallSignalEmtBuildTypes.Arnoldi,
                                       SmallSignalEmtBuildTypes.HybridArnoldi],
                          translate=self.tr)
        )

        # dictionaries for available results
        self.available_results_dict: Union[Dict[SimulationTypes, Dict[ResultTypes, ResultTypes]], None] = dict()

        self.buses_for_storage: List[dev.Bus] = list()

        # --------------------------------------------------------------------------------------------------------------

        self.ui.actionPower_flow.triggered.connect(self.power_flow_dispatcher)
        self.ui.actionPower_flow_3ph.triggered.connect(self.power_flow_3ph_dispatcher)
        self.ui.actionShort_Circuit.triggered.connect(self.run_short_circuit)
        self.ui.actionVoltage_stability.triggered.connect(self.run_continuation_power_flow)
        self.ui.actionPower_Flow_Time_series.triggered.connect(self.run_power_flow_time_series)
        self.ui.actionPower_flow_Stochastic.triggered.connect(self.run_stochastic)
        self.ui.actionState_estimation.triggered.connect(self.run_state_estimation)
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
        self.ui.actionRun_Dynamic_RMS_Simulation.triggered.connect(self.rms_dispatcher)
        self.ui.actionRun_Small_Signal_RMS_Simulation.triggered.connect(self.rms_small_signal_dispatcher)
        self.ui.actionRun_Dynamic_EMT_Simulation.triggered.connect(self.emt_dispatcher)
        self.ui.actionRun_Small_Signal_EMT_Simulation.triggered.connect(self.emt_small_signal_dispatcher)
        self.ui.actionCandidate_investment_generator.triggered.connect(self.candidate_investment_generator)
        self.ui.actionProcedural_grid_expansion.triggered.connect(self.procedural_grid_expansion)
        self.ui.actionCatalogue_element_optimization.triggered.connect(self.catalogue_element_optimization)

        self.ui.actionUse_clustering.triggered.connect(self.activate_clustering)
        self.ui.actionNodal_capacity.triggered.connect(self.nodal_capacity_dispatcher)
        self.ui.actionLaunch_data_analysis_tool.triggered.connect(self.display_grid_analysis)

        # combobox change
        self.ui.engineComboBox.currentIndexChanged.connect(self.modify_ui_options_according_to_the_engine)
        self.ui.contingency_filter_by_comboBox.currentTextChanged.connect(self.modify_contingency_filter_mode)
        self.ui.available_results_to_color_comboBox.currentIndexChanged.connect(self.changed_study)
        self.ui.mip_framework_comboBox.currentIndexChanged.connect(self.update_available_mip_solvers)
        self.ui.tolerance_spinBox.valueChanged.connect(self.adjust_controls_start_tolerance)
        self.ui.controls_start_tolerance_spinBox.valueChanged.connect(self.adjust_controls_start_tolerance)

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
                if drv.results is not None:
                    lst.append(drv)
                else:
                    pass
            else:
                pass

        return lst

    def get_time_indices(self) -> IntVec | None:
        """
        Get an array of indices of the time steps selected within the start-end interval
        :return: np.array[int]
        """

        if self.circuit.time_profile is None:
            return None
        else:
            start = self.get_simulation_start()
            end = self.get_simulation_end()

            return np.arange(start, end + 1, dtype=int)

    def modify_ui_options_according_to_the_engine(self) -> None:
        """
        Change the UI depending on the engine options
        :return:
        """
        eng = self.get_preferred_engine()

        if eng == EngineType.GSLV:

            # add the AC_OPF option
            self.ui.lpf_solver_comboBox.setModel(
                gf.ComboModel(enum_values=[SolverType.LINEAR_OPF,
                                           SolverType.NONLINEAR_OPF,
                                           SolverType.GREEDY_DISPATCH_OPF],
                              translate=self.tr)
            )

            # Power Flow Methods
            self.ui.solver_comboBox.setModel(
                gf.ComboModel(enum_values=[SolverType.NR,
                                           SolverType.IWAMOTO,
                                           SolverType.LM,
                                           SolverType.FASTDECOUPLED,
                                           SolverType.HELM,
                                           SolverType.GAUSS,
                                           SolverType.LACPF,
                                           SolverType.Linear],
                              translate=self.tr)
            )
            self.ui.solver_comboBox.setCurrentIndex(0)

            self.update_available_mip_solvers()

        elif eng == EngineType.VeraGrid:

            # no AC opf option
            self.ui.lpf_solver_comboBox.setModel(
                gf.ComboModel(enum_values=[SolverType.LINEAR_OPF,
                                           SolverType.NONLINEAR_OPF,
                                           SolverType.GREEDY_DISPATCH_OPF],
                              translate=self.tr)
            )

            # Power Flow Methods
            self.ui.solver_comboBox.setModel(
                gf.ComboModel(enum_values=[SolverType.NR,
                                           SolverType.IWAMOTO,
                                           SolverType.LM,
                                           SolverType.PowellDogLeg,
                                           SolverType.FASTDECOUPLED,
                                           SolverType.HELM,
                                           SolverType.GAUSS,
                                           SolverType.LACPF,
                                           SolverType.Linear],
                              translate=self.tr)
            )
            self.ui.solver_comboBox.setCurrentIndex(0)

            # MIP solvers
            self.update_available_mip_solvers()

        elif eng == EngineType.PGM:

            # no AC opf option
            self.ui.lpf_solver_comboBox.setModel(
                gf.ComboModel(enum_values=[SolverType.LINEAR_OPF,
                                           SolverType.GREEDY_DISPATCH_OPF],
                              translate=self.tr)
            )

            # Power Flow Methods
            self.ui.solver_comboBox.setModel(
                gf.ComboModel(enum_values=[SolverType.NR,
                                           SolverType.BFS,
                                           SolverType.BFS_linear,
                                           SolverType.Constant_Impedance_linear],
                              translate=self.tr)
            )
            self.ui.solver_comboBox.setCurrentIndex(0)

        else:
            raise Exception('Unsupported engine ' + str(eng.value))

    def modify_contingency_filter_mode(self) -> None:
        """
        Modify the objects
        """
        filter_mode = self.ui.contingency_filter_by_comboBox.currentData()

        if filter_mode == ContingencyFilteringMethods.AllActive:
            mdl = None

        elif filter_mode == ContingencyFilteringMethods.Country:
            mdl = gf.get_list_model(lst=[elm.name for elm in self.circuit.get_countries()],
                                    checks=True,
                                    check_value=True)

        elif filter_mode == ContingencyFilteringMethods.Community:
            mdl = gf.get_list_model(lst=[elm.name for elm in self.circuit.get_communities()],
                                    checks=True,
                                    check_value=True)

        elif filter_mode == ContingencyFilteringMethods.Region:
            mdl = gf.get_list_model(lst=[elm.name for elm in self.circuit.get_regions()],
                                    checks=True,
                                    check_value=True)

        elif filter_mode == ContingencyFilteringMethods.Municipality:
            mdl = gf.get_list_model(lst=[elm.name for elm in self.circuit.get_municipalities()],
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

        elif filter_mode == ContingencyFilteringMethods.SensitiveToMonitored:

            drv, res = self.session.linear_power_flow
            if res is None:
                self.show_warning_toast(self.tr("Run a linear analysis to enable filter contingencies by sensitivity"))
                mdl = None
                self.ui.contingency_filter_by_comboBox.setCurrentIndex(0)
            else:
                threshold = self.ui.lodf_threshold_doubleSpinBox.value()
                sensitive_idx = self.circuit.get_contingency_groups_sensitive_to_monitoring(LODF=res.LODF,
                                                                                            threshold=threshold)
                mdl = gf.get_elm_chck_list_model(lst=self.circuit.contingency_groups,
                                                 check_status=sensitive_idx)
        else:
            raise Exception('Unsupported ContingencyFilteringMethod ' + str(filter_mode.value))

        self.ui.contingency_group_filter_listView.setModel(mdl)

    def get_contingency_groups_matching_the_filter(self) -> List[dev.ContingencyGroup]:
        """
        Get the list of contingencies that match the group
        :return:
        """

        # get the filter mode
        filter_mode = self.ui.contingency_filter_by_comboBox.currentData()

        if filter_mode == ContingencyFilteringMethods.AllActive:
            # no filtering, we're safe
            return self.circuit.get_contingency_groups_active()

        elif filter_mode == ContingencyFilteringMethods.Country:

            if self.circuit.get_country_number() > 0:
                # get the selection indices
                idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
                elements = self.circuit.get_countries()
                return self.circuit.get_contingency_groups_in(grouping_elements=[elements[i] for i in idx])
            else:
                # default to returning all groups, since it's safer
                return self.circuit.get_contingency_groups_active()

        elif filter_mode == ContingencyFilteringMethods.Community:

            if self.circuit.get_communities_number() > 0:
                # get the selection indices
                idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
                elements = self.circuit.get_communities()
                return self.circuit.get_contingency_groups_in(grouping_elements=[elements[i] for i in idx])
            else:
                # default to returning all groups, since it's safer
                return self.circuit.get_contingency_groups_active()

        elif filter_mode == ContingencyFilteringMethods.Region:

            if self.circuit.get_regions_number() > 0:
                # get the selection indices
                idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
                elements = self.circuit.get_regions()
                return self.circuit.get_contingency_groups_in(grouping_elements=[elements[i] for i in idx])
            else:
                # default to returning all groups, since it's safer
                return self.circuit.get_contingency_groups_active()

        elif filter_mode == ContingencyFilteringMethods.Municipality:

            if self.circuit.get_municipalities_number() > 0:
                # get the selection indices
                idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
                elements = self.circuit.get_municipalities()
                return self.circuit.get_contingency_groups_in(grouping_elements=[elements[i] for i in idx])
            else:
                # default to returning all groups, since it's safer
                return self.circuit.get_contingency_groups_active()

        elif filter_mode == ContingencyFilteringMethods.Area:
            if self.circuit.get_area_number() > 0:
                # get the selection indices
                idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
                elements = self.circuit.get_areas()
                return self.circuit.get_contingency_groups_in(grouping_elements=[elements[i] for i in idx])
            else:
                # default to returning all groups, since it's safer
                return self.circuit.get_contingency_groups_active()

        elif filter_mode == ContingencyFilteringMethods.Zone:
            if self.circuit.get_zone_number() > 0:
                # get the selection indices
                idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
                elements = self.circuit.get_areas()
                return self.circuit.get_contingency_groups_in(grouping_elements=[elements[i] for i in idx])
            else:
                # default to returning all groups, since it's safer
                return self.circuit.get_contingency_groups_active()

        elif filter_mode == ContingencyFilteringMethods.SensitiveToMonitored:
            idx = gf.get_checked_indices(self.ui.contingency_group_filter_listView.model())
            return [self.circuit.contingency_groups[i] for i in idx]
        else:
            raise Exception('Unsupported ContingencyFilteringMethod ' + str(filter_mode.value))

    def valid_time_series(self):
        """
        Check if there are valid time series
        """
        if self.circuit.valid_for_simulation():
            if self.circuit.time_profile is not None:
                if self.circuit.get_time_number() > 0:
                    return True
        return False

    def add_simulation(self, val: SimulationTypes) -> None:
        """
        Add a simulation to the simulations list
        :param val: simulation type
        """
        if val not in self.stuff_running_now:
            self.stuff_running_now.append(val)
        else:
            pass

    def remove_simulation(self, val: SimulationTypes) -> None:
        """
        Remove a simulation from the simulations list
        :param val: simulation type
        """
        while val in self.stuff_running_now:
            self.stuff_running_now.remove(val)

    def clear_results(self):
        """
        Clear the results tab
        """
        if self.session.is_anything_running():
            self.show_warning_toast(self.tr("Wait until the running simulations finish before clearing results."))
            return
        else:
            pass

        self.session.clear()

        self.buses_for_storage = list()

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
        self.ui.model_version_label.setText(
            QtCore.QCoreApplication.translate("SimulationsMain", "Model v. {model_version}").format(
                model_version=self.circuit.model_version,
            )
        )
        self.ui.grid_idtag_label.setText(
            QtCore.QCoreApplication.translate("SimulationsMain", "idtag. {idtag}").format(
                idtag=self.circuit.idtag,
            )
        )
        self.ui.user_name_label.setText(
            QtCore.QCoreApplication.translate("SimulationsMain", "User: {user_name}").format(
                user_name=self.circuit.user_name,
            )
        )
        if self.open_file_thread_object is not None:
            if isinstance(self.open_file_thread_object.file_name, str):
                self.ui.file_information_label.setText(self.open_file_thread_object.file_name)

        self.ui.units_label.setText("")

    @staticmethod
    def get_investments_combination_tree_model(drv: sim.InvestmentsEvaluationDriver) -> QtGui.QStandardItemModel:
        """
        Build the model for the Variations panel after an Investments evaluation.
        Only Pareto-front combinations are listed.

        :param drv: InvestmentsEvaluationDriver instance with finalized results
        :return: QStandardItemModel with one top-level row per Pareto combination
        """
        model: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(
            [QtCore.QCoreApplication.translate("SimulationsMain", "Pareto combination")] + list(drv.results.f_names)
        )

        # Iterate only over Pareto-front rows. sorting_indices points back into the
        # full _x/_f arrays, so drv.results.x[i, :] is still the right way to look
        # up the x vector. We tag each row with its original index via UserRole so
        # the click handler can recover the x vector regardless of how Qt later
        # sorts or filters the panel.
        for i in drv.results.sorting_indices:
            idx: np.ndarray = np.where(drv.results.x[i, :] != 0)[0]
            if len(idx):
                label_item: QtGui.QStandardItem = QtGui.QStandardItem(
                    QtCore.QCoreApplication.translate("SimulationsMain", "Pareto combination {index}").format(
                        index=i,
                    )
                )
                label_item.setData(int(i), QtCore.Qt.ItemDataRole.UserRole)
                row_items: List[QtGui.QStandardItem] = [label_item] + [
                    QtGui.QStandardItem(f"{fi:.2f}") for fi in drv.results.f[i, :]
                ]
                model.appendRow(row_items)

                # Investment names go under the combination row as children. Clicks
                # on a child still trigger combinations_tree_clicked, which walks
                # back up to the top-level row to recover the combination index.
                for k in idx:
                    name_item: QtGui.QStandardItem = QtGui.QStandardItem(drv.results.x_names[k])
                    label_item.appendRow([name_item])
            else:
                # empty combination (no investments active) - skip it
                pass

        return model

    @staticmethod
    def get_catalogue_combination_tree_model(
            drv: sim.CatalogueOptimizationDriver) -> QtGui.QStandardItemModel:
        """
        Build the model for the Variations panel after a Catalogue Optimization run.
        Only Pareto-front combinations are listed (using the deduplicated indices
        produced by InvestmentsEvaluationResults.finalize). Each combination row
        is expanded to show one child per decision variable in the form
        "<branch_name>: <integer index>", so the user can read off which
        template-pool index was chosen for each branch.

        :param drv: CatalogueOptimizationDriver instance with finalized results
        :return: QStandardItemModel with one top-level row per Pareto combination
        """
        model: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(
            [QtCore.QCoreApplication.translate("SimulationsMain", "Pareto combination")] + list(drv.results.f_names)
        )

        # Iterate over Pareto-front rows only. sorting_indices points back into
        # the full _x/_f arrays, so drv.results.x[i, :] is the right slice. We
        # tag each row with its combination index via UserRole so the click
        # handler can recover the integer x vector independently of any Qt
        # sorting or filtering applied to the view.
        for i in drv.results.sorting_indices:
            x_vec: np.ndarray = drv.results.x[i, :]
            label_item: QtGui.QStandardItem = QtGui.QStandardItem(
                QtCore.QCoreApplication.translate("SimulationsMain", "Pareto combination {index}").format(
                    index=i,
                )
            )
            label_item.setData(int(i), QtCore.Qt.ItemDataRole.UserRole)
            row_items: List[QtGui.QStandardItem] = [label_item] + [
                QtGui.QStandardItem(f"{fi:.2f}") for fi in drv.results.f[i, :]
            ]
            model.appendRow(row_items)

            # One child per decision variable: "<branch name>: <integer index>".
            # Unlike the Investments panel (binary vector, where zeros are
            # hidden), every catalogue slot has a meaningful non-zero meaning,
            # so we list all of them — the integer alone tells the user which
            # template pool index NSGA-3 picked for each branch.
            for k in range(len(x_vec)):
                child_text: str = f"{drv.results.x_names[k]}: {int(x_vec[k])}"
                name_item: QtGui.QStandardItem = QtGui.QStandardItem(child_text)
                label_item.appendRow([name_item])

        return model

    @staticmethod
    def get_short_circuits_combination_tree_model(drv: sim.ShortCircuitDriver) -> QtGui.QStandardItemModel:
        """
        Get the investments combination tree model
        :param drv:
        :return:
        """
        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(
            [QtCore.QCoreApplication.translate("SimulationsMain", "Short circuits")]
        )

        for i, sc_name in enumerate(drv.results.sc_names):
            row_items = [QtGui.QStandardItem(sc_name)]
            model.appendRow(row_items)

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

            elif drv.tpe == SimulationTypes.CatalogueOptimization_run:
                model = self.get_catalogue_combination_tree_model(drv=drv)
                self.ui.combinationsTreeView.setModel(model)

            elif drv.tpe == SimulationTypes.ShortCircuit_run:
                model = self.get_short_circuits_combination_tree_model(drv=drv)
                self.ui.combinationsTreeView.setModel(model)
                # self.ui.combinationsTreeView.expandAll()

            else:
                self.ui.combinationsTreeView.setModel(None)

    def changed_study(self):
        """

        :return:
        """
        current_study = self.ui.available_results_to_color_comboBox.currentData()
        drv_dict: Dict[SimulationTypes, DRIVER_OBJECTS] = {driver.tpe: driver for driver in
                                                           self.get_available_drivers()}
        if isinstance(current_study, SimulationTypes):
            drv = drv_dict.get(current_study, None)
        else:
            drv = None
        if drv is not None:
            if drv.results is not None:
                if drv.results.time_indices is not None:
                    if len(drv.results.time_indices):
                        a = drv.results.time_indices[0]
                        b = drv.results.time_indices[-1]
                        self.ui.diagram_step_slider.setRange(a, b)
                        self.ui.diagram_step_slider.setValue(a)
                    else:
                        self.setup_time_sliders()
                else:
                    self.setup_time_sliders()
            else:
                self.setup_time_sliders()
        else:
            self.setup_time_sliders()

        self.fill_combinations_tree(drv=drv)

    def build_results_tree_model(self, available_results: List[DRIVER_OBJECTS]) -> QtGui.QStandardItemModel:
        """
        Build the results tree with translated labels and enum payloads.

        :param available_results: Simulation drivers with result objects.
        :return: Tree model for the results view.
        """
        model: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels([translate_tree_label('Results')])
        root_item: QtGui.QStandardItem = model.invisibleRootItem()
        icons: Dict[SimulationTypes, str] = gf.get_simulation_tree_icons()

        for driver in available_results:
            # Study rows carry the simulation enum. The label can be translated independently.
            study_item: QtGui.QStandardItem = QtGui.QStandardItem(translate_tree_label(str(driver.tpe.value)))
            study_item.setEditable(False)
            study_item.setData(driver.tpe, QtCore.Qt.ItemDataRole.UserRole)

            icon_path: str | None = icons.get(driver.tpe, None)
            if icon_path is not None:
                icon: QtGui.QIcon = QtGui.QIcon()
                icon.addPixmap(QtGui.QPixmap(icon_path))
                study_item.setIcon(icon)
            else:
                pass

            root_item.appendRow(study_item)
            self.fill_results_tree_model_item(parent_item=study_item,
                                              results_tree=driver.results.get_results_type_tree())

        return model

    def fill_results_tree_model_item(self,
                                     parent_item: QtGui.QStandardItem,
                                     results_tree: object) -> None:
        """
        Add result tree entries below one parent item.

        :param parent_item: Parent tree item.
        :param results_tree: Result tree as dictionaries or lists of result enums.
        :return: None.
        """
        if isinstance(results_tree, dict):
            for key, value in results_tree.items():
                # Group nodes are navigation labels. Leaf result nodes below them carry ResultTypes.
                source_text: str = str(key.value) if isinstance(key, ResultTypes) else str(key)
                group_item: QtGui.QStandardItem = QtGui.QStandardItem(translate_tree_label(source_text))
                group_item.setEditable(False)
                parent_item.appendRow(group_item)
                self.fill_results_tree_model_item(parent_item=group_item, results_tree=value)
        elif isinstance(results_tree, list):
            for result_type in results_tree:
                if isinstance(result_type, ResultTypes):
                    result_item: QtGui.QStandardItem = QtGui.QStandardItem(
                        translate_tree_label(str(result_type.value))
                    )
                    result_item.setEditable(False)
                    result_item.setData(result_type, QtCore.Qt.ItemDataRole.UserRole)
                    parent_item.appendRow(result_item)
                else:
                    pass
        else:
            pass

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
        lst: List[SimulationTypes] = [SimulationTypes.DesignView]
        for driver in available_results:
            lst.append(driver.tpe)
            self.available_results_dict[driver.tpe] = driver.results.get_results_type_dict()
            steps = driver.get_steps()
            self.available_results_steps_dict[driver.tpe] = steps
            if len(steps) > max_steps:
                max_steps = len(steps)

        self.ui.results_treeView.setModel(self.build_results_tree_model(available_results=available_results))
        lst.reverse()  # this is to show the latest simulation first
        mdl = gf.ComboModel(enum_values=lst, translate=translate_tree_label)
        self.ui.available_results_to_color_comboBox.setModel(mdl)
        self.ui.resultsTableView.setModel(None)
        self.ui.resultsLogsTreeView.setModel(None)
        self.changed_study()

    def refresh_runtime_translations(self) -> None:
        """
        Refresh runtime-built results labels after one language change.

        :return: None.
        """
        super().refresh_runtime_translations()

        available_results: List[DRIVER_OBJECTS] = self.get_available_drivers()
        selected_simulation_type: SimulationTypes | None = self.ui.available_results_to_color_comboBox.currentData()
        combo_values: List[SimulationTypes] = [SimulationTypes.DesignView]
        driver: DRIVER_OBJECTS

        self.ui.results_treeView.setModel(self.build_results_tree_model(available_results=available_results))

        for driver in available_results:
            combo_values.append(driver.tpe)

        combo_values.reverse()
        model: gf.ComboModel = gf.ComboModel(enum_values=combo_values, translate=translate_tree_label)
        self.ui.available_results_to_color_comboBox.setModel(model)

        if selected_simulation_type is not None:
            index: int = self.ui.available_results_to_color_comboBox.findData(selected_simulation_type)
            if index >= 0:
                self.ui.available_results_to_color_comboBox.setCurrentIndex(index)
            else:
                pass
        else:
            pass

    def get_compatible_from_to_buses_and_inter_branches(self) -> dev.InterAggregationInfo:
        """
        Get the lists that help defining the inter area objects
        :return: InterAggregationInfo
        """
        if self.ui.fromListView.model() is not None:
            dev_tpe_from = self.ui.fromComboBox.currentData()
            devs_from = self.circuit.get_elements_by_type(dev_tpe_from)
            from_idx = gf.get_checked_indices(self.ui.fromListView.model())
            objects_from: List[AREA_TYPES] = [devs_from[i] for i in from_idx]
        else:
            objects_from: List[AREA_TYPES] = []
            self.show_error_toast(self.tr("No from areas!"))

        if self.ui.toListView.model() is not None:
            dev_tpe_to = self.ui.toComboBox.currentData()
            devs_to = self.circuit.get_elements_by_type(dev_tpe_to)
            to_idx = gf.get_checked_indices(self.ui.toListView.model())
            objects_to: List[AREA_TYPES] = [devs_to[i] for i in to_idx]
        else:
            objects_to: List[AREA_TYPES] = []
            self.show_error_toast(self.tr("No to areas!"))

        info: dev.InterAggregationInfo = self.circuit.get_inter_aggregation_info(objects_from=objects_from,
                                                                                 objects_to=objects_to)

        if info.logger.has_logs():
            # Show dialogue
            self.show_logs(name="Add selected DB objects to current diagram", logger=info.logger)

        return info

    def get_selected_power_flow_options(self) -> sim.PowerFlowOptions:
        """
        Gather power flow run options
        :return: sim.PowerFlowOptions
        """
        self.adjust_controls_start_tolerance()

        tolerance = 1.0 / (10.0 ** self.ui.tolerance_spinBox.value())
        controls_start_tolerance = 1.0 / (10.0 ** self.ui.controls_start_tolerance_spinBox.value())

        if self.ui.apply_impedance_tolerances_checkBox.isChecked():
            branch_impedance_tolerance_mode = BranchImpedanceMode.Upper
        else:
            branch_impedance_tolerance_mode = BranchImpedanceMode.Specified

        ops = sim.PowerFlowOptions(
            solver_type=self.ui.solver_comboBox.currentData(),
            retry_with_other_methods=self.ui.helm_retry_checkBox.isChecked(),
            verbose=self.ui.verbositySpinBox.value(),
            tolerance=tolerance,
            controls_start_tolerance=controls_start_tolerance,
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
            generate_report=self.ui.addPowerFlowReportCheckBox.isChecked(),
        )

        return ops

    def adjust_controls_start_tolerance(self, value: int | None = None) -> None:
        """
        Keep the controls activation tolerance consistent with the solver tolerance.

        :param value: Qt signal payload, unused
        :return: Nothing
        """
        del value

        tolerance_idx: int = self.ui.tolerance_spinBox.value()
        controls_start_tolerance_idx: int = self.ui.controls_start_tolerance_spinBox.value()
        adjusted_idx: int = get_valid_controls_start_tolerance_index(
            tolerance_idx=tolerance_idx,
            controls_start_tolerance_idx=controls_start_tolerance_idx,
            controls_start_tolerance_min_idx=self.ui.controls_start_tolerance_spinBox.minimum(),
        )

        if adjusted_idx != controls_start_tolerance_idx:
            self.ui.controls_start_tolerance_spinBox.setValue(adjusted_idx)
        else:
            pass

    def get_selected_rms_simulation_options(self) -> sim.RmsOptions:
        """
        Gather rms simulation run options
        :return: sim.RmsOptions
        """
        ops = sim.RmsOptions(
            time_step=self.ui.rms_h_spinBox.value(),
            simulation_time=self.ui.rms_sim_time_spinBox.value(),
            tolerance=1.0 / (10.0 ** self.ui.tolerance_rms_spinBox.value()),
            integration_method=self.ui.rms_integration_method_comboBox.currentData(),
            initialization_method=self.ui.rms_initialization_method_comboBox.currentData(),
            problem_type=self.ui.rms_problem_comboBox.currentData()
        )

        return ops

    def get_selected_rms_small_signal_stability_options(self) -> sim.RmsSmallSignalStabilityOptions:
        """
        Gather RMS SmallSignal simulation run options
        :return: RmsSmallSignalStabilityOptions
        """
        ops = sim.RmsSmallSignalStabilityOptions(
            k=self.ui.rms_small_signal_modes_number_spinBox.value(),
            ss_assessment_time=self.ui.rms_ss_assessment_time_spinBox.value(),
        )

        return ops

    def get_selected_emt_simulation_options(self) -> sim.EmtOptions:
        """
        Gather EMT simulation run options
        :return: sim.EmtOptions
        """
        ops = sim.EmtOptions(
            time_step=self.ui.emt_h_spinBox.value(),
            simulation_time=self.ui.emt_sim_time_spinBox.value(),
            tolerance=1.0 / (10.0 ** self.ui.tolerance_emt_spinBox.value()),
            integration_method=self.ui.emt_integration_method_comboBox.currentData(),
            initialization_method=self.ui.emt_initialization_method_comboBox.currentData(),
            solver_type=self.ui.emt_solver_type_comboBox.currentData(),
            problem_type=self.ui.emt_problem_comboBox.currentData()
        )

        return ops

    def get_selected_emt_small_signal_stability_options(self) -> sim.SmallSignalStabilityEmtOptions:
        """
        Gather EMT SmallSignal simulation run options
        :return: sim.SmallSignalOptions
        """
        ops = sim.SmallSignalStabilityEmtOptions(
            k=self.ui.emt_small_signal_modes_number_spinBox.value(),
            target_period=self.ui.emt_sss_target_period_spinBox.value(),
            ss_assessment_time=self.ui.emt_ss_assessment_time_spinBox.value(),
            build_type=self.ui.emt_sss_build_type_comboBox.currentData(),
        )

        return ops

    def get_opf_results(self,
                        use_opf: bool) -> sim.OptimalPowerFlowResults | None:
        """
        Get the current OPF results
        :param use_opf: use OPF flag
        :return: sim.OptimalPowerFlowResults | sim.OptimalNetTransferCapacityResults | None
        """
        if use_opf:

            drv, results = self.session.optimal_power_flow

            if drv is not None:
                if results is not None:
                    opf_results = results
                else:
                    warning_msg(self.tr('There are no OPF results, '
                                        'therefore this operation will not use OPF information.'))
                    self.ui.actionOpf_to_Power_flow.setChecked(False)
                    opf_results = None
            else:

                # # try the OPF-NTC...
                # drv, results = self.session.optimal_net_transfer_capacity
                #
                # if drv is not None:
                #     if results is not None:
                #         opf_results = results
                #     else:
                #         warning_msg('There are no OPF-NTC results, '
                #                     'therefore this operation will not use OPF information.')
                #         self.ui.actionOpf_to_Power_flow.setChecked(False)
                #         opf_results = None
                # else:
                #     warning_msg('There are no OPF results, '
                #                 'therefore this operation will not use OPF information.')
                #     self.ui.actionOpf_to_Power_flow.setChecked(False)
                #     opf_results = None
                opf_results = None
        else:
            opf_results = None

        return opf_results

    def get_opf_ts_results(self, use_opf: bool) -> sim.OptimalPowerFlowTimeSeriesResults | None:
        """
        Get the current OPF time series results
        :param use_opf: use the OPF?
        :return: OptimalPowerFlowTimeSeriesResults | None
        """
        if use_opf:

            _, opf_time_series_results = self.session.optimal_power_flow_ts

            if opf_time_series_results is None:
                if use_opf:
                    info_msg(self.tr('There are no OPF time series, '
                                     'therefore this operation will not use OPF information.'))
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

    def power_flow_3ph_dispatcher(self):
        """
        Dispatch the power flow action
        """
        if self.server_driver.is_running():
            if self.ts_flag():
                instruction = RemoteInstruction(operation=SimulationTypes.PowerFlowTimeSeries3ph_run)
            else:
                instruction = RemoteInstruction(operation=SimulationTypes.PowerFlow3ph_run)

            self.run_remote(instruction=instruction)

        else:
            if self.ts_flag():
                self.run_power_flow_time_series_3ph()
            else:
                self.run_power_flow3ph()

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

    def nodal_capacity_dispatcher(self):
        """
        Dispatch the nodal capacity action
        :return:
        """
        if self.server_driver.is_running():
            if self.ts_flag():
                instruction = RemoteInstruction(operation=SimulationTypes.NodalCapacityTimeSeries_run)
            else:
                instruction = RemoteInstruction(operation=SimulationTypes.NodalCapacity_run)

            self.run_remote(instruction=instruction)
        else:
            if self.ts_flag():
                self.run_nodal_capacity_time_series()
            else:
                self.run_nodal_capacity()

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

    def rms_dispatcher(self):
        """
        Dispatch the reliability action
        :return:
        """
        if len(self.circuit.rms_events_groups) == 0:
            # An event group defines the simulation scenario, even when it
            # contains no events. Stop before either local or remote dispatch
            # so starting a simulation never modifies the circuit implicitly.
            error_msg(
                self.tr(
                    "An RMS simulation cannot run without an RMS Events Group. "
                    "Go to Events -> Add RMS event and add a group, even if it contains no events."
                )
            )
            return
        else:
            pass

        if self.server_driver.is_running():
            instruction = RemoteInstruction(operation=SimulationTypes.RmsDynamic_run)
            self.run_remote(instruction=instruction)

        else:
            if self.circuit.valid_for_simulation():

                if not self.session.is_this_running(SimulationTypes.RmsDynamic_run):

                    logger = self.circuit.check_rms_models()
                    if logger.has_errors():
                        # Show dialogue
                        dlg = LogsDialogue(name=self.tr("RMS pre simulation check"),
                                           logger=logger, parent=self)
                        dlg.setModal(True)
                        exec_dialog_safely(dialog=dlg)
                        return
                    else:
                        self.run_rms()

                else:
                    self.show_warning_toast(self.tr('Another rms simulation is running already...'))

            else:
                pass

    def emt_dispatcher(self):
        """
        Dispatch the reliability action
        :return:
        """
        if len(self.circuit.emt_events_groups) == 0:
            # Keep the EMT scenario selection explicit and block every
            # execution path until the circuit owns at least one group.
            error_msg(
                self.tr(
                    "An EMT simulation cannot run without an EMT Events Group. "
                    "Go to Events -> Add EMT event and add a group, even if it contains no events."
                )
            )
            return
        else:
            pass

        if self.server_driver.is_running():
            instruction = RemoteInstruction(operation=SimulationTypes.EmtDynamic_run)
            self.run_remote(instruction=instruction)

        else:
            if self.circuit.valid_for_simulation():

                if not self.session.is_this_running(SimulationTypes.EmtDynamic_run):

                    # logger = self.circuit.check_emt_models()
                    # if logger.has_errors():
                    #     # Show dialogue
                    #     dlg = LogsDialogue(name="EMT pre simulation check",
                    #                        logger=logger)
                    #     dlg.setModal(True)
                    #     dlg.exec()
                    #     return
                    # else:

                    self.run_emt()

                else:
                    self.show_warning_toast(self.tr('Another EMT simulation is running already...'))

            else:
                pass

    def rms_small_signal_dispatcher(self):
        """
        Dispatch the reliability action
        :return:
        """
        if self.server_driver.is_running():
            instruction = RemoteInstruction(operation=SimulationTypes.RmsSmallSignal_run)
            self.run_remote(instruction=instruction)

        else:
            self.run_rms_small_signal_stability()

    def emt_small_signal_dispatcher(self):
        """
        Dispatch the reliability action
        :return:
        """
        if self.server_driver.is_running():
            instruction = RemoteInstruction(operation=SimulationTypes.RmsSmallSignal_run)
            self.run_remote(instruction=instruction)

        else:
            self.run_emt_small_signal_stability()

    def run_power_flow(self):
        """
        Run a power flow simulation
        :return:
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.PowerFlow_run):

                self.LOCK()

                self.add_simulation(SimulationTypes.PowerFlow_run)

                self.ui.progress_label.setText(
                    QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                # get the power flow options from the GUI
                options = self.get_selected_power_flow_options()

                opf_results = self.get_opf_results(use_opf=self.ui.actionOpf_to_Power_flow.isChecked())

                self.ui.progress_label.setText(
                    QtCore.QCoreApplication.translate("SimulationsMain", "Running power flow..."))

                # set power flow object instance
                engine = self.get_preferred_engine()
                drv = sim.PowerFlowDriver(grid=self.circuit,
                                          options=options,
                                          opf_results=opf_results,
                                          engine=engine)

                self.session.run(drv,
                                 post_func=self.post_power_flow,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                self.show_warning_toast(self.tr('Another simulation of the same type is running...'))
        else:
            pass

    def run_power_flow_3ph(self):
        """
        Run a power flow simulation
        :return:
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.PowerFlow_run):

                self.LOCK()

                self.add_simulation(SimulationTypes.PowerFlow_run)

                self.ui.progress_label.setText(
                    QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                # get the power flow options from the GUI
                options = self.get_selected_power_flow_options()

                opf_results = self.get_opf_results(use_opf=self.ui.actionOpf_to_Power_flow.isChecked())

                self.ui.progress_label.setText(
                    QtCore.QCoreApplication.translate("SimulationsMain", "Running power flow..."))

                # set power flow object instance
                engine = self.get_preferred_engine()
                drv = sim.PowerFlowDriver3Ph(grid=self.circuit,
                                             options=options,
                                             opf_results=opf_results,
                                             engine=engine)

                self.session.run(drv,
                                 post_func=self.post_power_flow,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                self.show_warning_toast(self.tr('Another simulation of the same type is running...'))
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
                self.show_info_toast(self.tr("Power flow converged :)"))
            else:
                self.show_warning_toast(self.tr("Power flow not converged :/"))

        else:
            warning_msg(self.tr('There are no power flow results.\nIs there any slack bus or generator?'),
                        self.tr('Power flow'))

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_power_flow3ph(self):
        """
        Run a power flow simulation
        :return:
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.PowerFlow3ph_run):

                self.LOCK()

                self.add_simulation(SimulationTypes.PowerFlow3ph_run)

                self.ui.progress_label.setText(
                    QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                # get the power flow options from the GUI
                options = self.get_selected_power_flow_options()

                opf_results = self.get_opf_results(use_opf=self.ui.actionOpf_to_Power_flow.isChecked())

                self.ui.progress_label.setText(
                    QtCore.QCoreApplication.translate("SimulationsMain", "Running power flow..."))

                # set power flow object instance
                engine = self.get_preferred_engine()
                drv = sim.PowerFlowDriver3Ph(grid=self.circuit,
                                             options=options,
                                             opf_results=opf_results,
                                             engine=engine)

                self.session.run(drv,
                                 post_func=self.post_power_flow3ph,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                self.show_warning_toast(self.tr('Another simulation of the same type is running...'))
        else:
            pass

    def post_power_flow3ph(self):
        """
        Action performed after the power flow.
        Returns:

        """
        # update the results in the circuit structures

        driver, results = self.session.power_flow_3ph

        self.remove_simulation(SimulationTypes.PowerFlow3ph_run)

        try:
            if results is not None:
                self.ui.progress_label.setText('Colouring power flow results in the grid...')
                self.update_available_results()
                self.colour_diagrams()

                if results.converged:
                    self.show_info_toast(self.tr("Power flow 3ph converged :)"))
                else:
                    self.show_warning_toast(self.tr("Power flow 3ph not converged :/"))

            elif driver is not None and driver.logger.has_errors():
                # The worker preserves the actual failure, including invalid Z0/Z2 data.
                self.show_logs(logger=driver.logger, name=self.tr('Power flow 3ph failed'))
            else:
                warning_msg(self.tr('There are no power flow results.\nIs there any slack bus or generator?'),
                            self.tr('Power flow'))
        finally:
            if not self.session.is_anything_running():
                self.UNLOCK()

    def run_power_flow_time_series_3ph(self):
        """
        Run a three-phase power-flow time-series simulation in a separated thread from the GUI.

        :return: None.
        """
        if self.circuit.valid_for_simulation():
            if not self.session.is_this_running(SimulationTypes.PowerFlowTimeSeries3ph_run):
                if self.valid_time_series():
                    self.LOCK()

                    self.add_simulation(SimulationTypes.PowerFlowTimeSeries3ph_run)

                    self.ui.progress_label.setText(
                        QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                    opf_time_series_results = self.get_opf_ts_results(
                        use_opf=self.ui.actionOpf_to_Power_flow.isChecked()
                    )
                    options = self.get_selected_power_flow_options()

                    drv = sim.PowerFlowTimeSeriesDriver3Ph(
                        grid=self.circuit,
                        options=options,
                        time_indices=self.get_time_indices(),
                        opf_time_series_results=opf_time_series_results,
                        clustering_results=self.get_clustering_results(),
                        engine=self.get_preferred_engine()
                    )

                    self.session.run(drv,
                                     post_func=self.post_power_flow_time_series_3ph,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                else:
                    self.show_warning_toast(self.tr('There are no time series.'))
            else:
                self.show_warning_toast(self.tr('Another three-phase time series power flow is being executed now...'))
        else:
            pass

    def post_power_flow_time_series_3ph(self):
        """
        Events to do when the three-phase time-series simulation has finished.

        :return: None.
        """
        _, results = self.session.power_flow_3ph_ts

        self.remove_simulation(SimulationTypes.PowerFlowTimeSeries3ph_run)

        try:
            if results is not None:
                results.expand_clustered_results()
                self.update_available_results()
                self.colour_diagrams()
            else:
                self.show_warning_toast(self.tr('No results for the three-phase time series simulation.'))
        finally:
            if not self.session.is_anything_running():
                self.UNLOCK()

    def get_se_options(self) -> sim.StateEstimationOptions:
        """

        :return:
        """
        return sim.StateEstimationOptions(
            solver=self.ui.se_solver_comboBox.currentData(),
            tol=self.ui.se_tolerance_spinBox.value(),
            max_iter=self.ui.se_max_iterations_spinBox.value(),
            verbose=0,
            prefer_correct=self.ui.se_prefer_correct_checkBox.isChecked(),
            c_threshold=4.0,
            fixed_slack=self.ui.se_fixed_slack_checkBox.isChecked(),
            run_observability_analyis=self.ui.se_observability_analysis_checkBox.isChecked(),
            add_pseudo_measurements=self.ui.se_add_pseudo_measurements_checkBox.isChecked(),
            run_measurement_profiling=self.ui.se_measurements_profiling_checkBox.isChecked(),
            include_line_measurements_on_both_ends=True,
            pseudo_meas_std=1.0
        )

    def run_state_estimation(self):
        """
        Run a power flow simulation
        :return:
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.StateEstimation_run):

                self.LOCK()

                self.add_simulation(SimulationTypes.StateEstimation_run)

                self.ui.progress_label.setText(
                    QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                # get the power flow options from the GUI
                options = self.get_se_options()

                self.ui.progress_label.setText('Running state estimation...')

                drv = sim.StateEstimationDriver(self.circuit, options)

                self.session.run(drv,
                                 post_func=self.post_state_estimation,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                self.show_warning_toast(self.tr('Another simulation of the same type is running...'))
        else:
            pass

    def post_state_estimation(self):
        """
        Action performed after the power flow.
        Returns:

        """
        # update the results in the circuit structures

        _, results = self.session.state_estimation

        if results is not None:
            self.ui.progress_label.setText('Colouring state estimation results in the grid...')
            self.remove_simulation(SimulationTypes.StateEstimation_run)
            self.update_available_results()
            self.colour_diagrams()

            if results.converged:
                self.show_info_toast(self.tr("State estimation converged :)"))
            else:
                self.show_warning_toast(self.tr("State estimation not converged :/"))

        else:
            warning_msg(self.tr('There are no state estimation results.\nIs there any slack bus or generator?'),
                        self.tr('State estimation'))

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
                _, pf_results3ph = self.session.power_flow_3ph

                if self.circuit.get_short_circuit_event_number() == 0:
                    warning_msg(self.tr(
                        "You need to define short circuits in the Database.\n"
                        "Add them by right click on a bus and selecting on the context menu."
                    ))
                else:
                    methods = {event.method for event in self.circuit.short_circuit_event}
                    needs_pf = any(method in (MethodShortCircuit.sequences, MethodShortCircuit.sequences_vsc)
                                   for method in methods)
                    needs_pf_3ph = MethodShortCircuit.phases in methods

                    missing = list()
                    if needs_pf and pf_results is None:
                        missing.append('Run a power flow simulation first.')
                    if needs_pf_3ph and pf_results3ph is None:
                        missing.append('Run a 3-phase power flow simulation first.')

                    if missing:
                        info_msg(self.tr(
                            "{missing_results}\nThe results are needed to initialize this simulation."
                        ).format(missing_results="\n".join(missing)))
                    else:
                        self.add_simulation(SimulationTypes.ShortCircuit_run)

                        self.LOCK()

                        if self.ui.apply_impedance_tolerances_checkBox.isChecked():
                            branch_impedance_tolerance_mode = BranchImpedanceMode.Lower
                        else:
                            branch_impedance_tolerance_mode = BranchImpedanceMode.Specified

                        # get the power flow options from the GUI
                        sc_options = sim.ShortCircuitOptions()

                        pf_options = self.get_selected_power_flow_options()
                        if any(sc.method == MethodShortCircuit.sequences_vsc
                               for sc in self.circuit.short_circuit_event):
                            pf_options.limit_i_vsc = True

                        drv = sim.ShortCircuitDriver(grid=self.circuit,
                                                     options=sc_options,
                                                     pf_options=pf_options,
                                                     pf_results=pf_results,
                                                     pf_results3ph=pf_results3ph)
                        self.session.run(drv,
                                         post_func=self.post_short_circuit,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)
            else:
                warning_msg(self.tr('Another short circuit is being executed now...'))
        else:
            pass

    def post_short_circuit(self):
        """
        Action performed after the short circuit.
        Returns:

        """
        # Read the Qt worker first because it carries the actual exception log
        # when the driver failed before publishing results into the session.
        sender: QtCore.QObject | None = self.sender()
        worker_failed: bool = False
        error_text: str = self.tr('The short-circuit worker finished without results.')
        results: sim.ShortCircuitResults | None

        if isinstance(sender, GcThread):
            results = sender.driver.results
            worker_failed = sender.has_failed()

            if len(sender.logger.entries) > 0:
                error_text = sender.logger.entries[-1].msg
            else:
                if len(sender.driver.logger.entries) > 0:
                    error_text = sender.driver.logger.entries[-1].msg
                else:
                    pass
        else:
            # Direct calls, tests and older code paths still retrieve the
            # results from the session as before.
            _, results = self.session.short_circuit

        self.remove_simulation(SimulationTypes.ShortCircuit_run)

        try:
            if results is not None and not worker_failed:
                self.ui.progress_label.setText('Colouring short circuit results in the grid...')
                self.update_available_results()
                self.colour_diagrams()

            else:
                error_msg(self.tr('Short circuit failed:\n') + error_text)
        finally:
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
            lodf_threshold=self.ui.lodf_threshold_doubleSpinBox.value(),
            use_jacobian_ptdf=self.ui.ptdf_use_jacobian_checkBox.isChecked()
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
                self.show_warning_toast(self.tr('Another PTDF is being executed now...'))
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

            self.update_available_results()
            self.colour_diagrams()
        else:
            self.show_warning_toast(self.tr('Something went wrong, There are no PTDF results.'))

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
                    warning_msg(self.tr('Another PTDF time series is being executed now...'))
            else:
                self.show_warning_toast(self.tr('There are no time series...'))

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

            self.update_available_results()

            if results.S.shape[0] > 0:
                self.colour_diagrams()
            else:
                self.show_warning_toast(self.tr('Cannot colour because the PTDF results have zero time steps :/'))

        else:
            self.show_warning_toast(self.tr('Something went wrong, There are no PTDF Time series results.'))

        if not self.session.is_anything_running():
            self.UNLOCK()

    def get_contingency_options(self) -> sim.ContingencyAnalysisOptions:
        """

        :return:
        """
        pf_options = self.get_selected_power_flow_options()

        options = sim.ContingencyAnalysisOptions(
            pf_options=pf_options,
            lin_options=self.get_linear_options(),
            use_srap=self.ui.use_srap_checkBox.isChecked(),
            srap_max_power=self.ui.srap_limit_doubleSpinBox.value(),
            srap_top_n=self.ui.srap_top_n_SpinBox.value(),
            srap_deadband=self.ui.srap_deadband_doubleSpinBox.value(),
            srap_rever_to_nominal_rating=self.ui.srap_revert_to_nominal_rating_checkBox.isChecked(),
            detailed_massive_report=self.ui.contingency_detailed_massive_report_checkBox.isChecked(),
            contingency_deadband=self.ui.contingency_deadband_SpinBox.value(),
            contingency_method=self.ui.contingencyEngineComboBox.currentData(),
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

                    opf_results = self.get_opf_results(use_opf=self.ui.actionOpf_to_Power_flow.isChecked())

                    drv = sim.ContingencyAnalysisDriver(grid=self.circuit,
                                                        options=self.get_contingency_options(),
                                                        linear_multiple_contingencies=None,  # it initializes inside
                                                        opf_results=opf_results,
                                                        engine=self.get_preferred_engine())

                    self.session.run(drv,
                                     post_func=self.post_contingency_analysis,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                else:
                    self.show_warning_toast(self.tr('Another contingency analysis is being executed now...'))

            else:
                self.show_warning_toast(self.tr('There are no contingency groups declared...'))
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

            self.update_available_results()

            self.colour_diagrams()
        else:
            self.show_error_toast(self.tr('Something went wrong, There are no contingency analysis results.'))

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

                        opf_ts_results = self.get_opf_ts_results(use_opf=self.ui.actionOpf_to_Power_flow.isChecked())

                        drv = sim.ContingencyAnalysisTimeSeriesDriver(grid=self.circuit,
                                                                      options=self.get_contingency_options(),
                                                                      time_indices=self.get_time_indices(),
                                                                      clustering_results=self.get_clustering_results(),
                                                                      opf_time_series_results=opf_ts_results,
                                                                      engine=self.get_preferred_engine())

                        self.session.run(drv,
                                         post_func=self.post_contingency_analysis_ts,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)
                    else:
                        self.show_warning_toast(self.tr('Another LODF is being executed now...'))
                else:
                    self.show_warning_toast(self.tr('There are no time series...'))

            else:
                self.show_warning_toast(self.tr('There are no contingency groups declared...'))

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

            self.update_available_results()

            self.colour_diagrams()
        else:
            self.show_error_toast(self.tr('Something went wrong, There are no contingency time series results.'))

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

                idx_from: IntVec = info.idx_bus_from
                idx_to: IntVec = info.idx_bus_to
                idx_br: IntVec = info.idx_branches
                sense_br: Vec = info.sense_branches

                # HVDC
                idx_hvdc_br: IntVec = info.idx_hvdc
                sense_hvdc_br: Vec = info.sense_hvdc

                if self.ui.usePfValuesForAtcCheckBox.isChecked():
                    _, pf_results = self.session.power_flow
                    if pf_results is not None:
                        Pf = pf_results.Sf.real
                        Pf_hvdc = pf_results.Pf_hvdc.real
                        use_provided_flows = True
                    else:
                        self.show_warning_toast(
                            self.tr('There were no power flow values available. Linear flows will be used.'))
                        use_provided_flows = False
                        Pf_hvdc = None
                        Pf = None
                else:
                    use_provided_flows = False
                    Pf = None
                    Pf_hvdc = None

                if len(idx_from) == 0:
                    error_msg(self.tr('The area "from" has no buses!'))
                    return

                if len(idx_to) == 0:
                    error_msg(self.tr('The area "to" has no buses!'))
                    return

                if len(idx_br) == 0:
                    error_msg(self.tr('There are no inter-area Branches!'))
                    return

                mode = self.ui.transferMethodComboBox.currentData()

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
                self.show_warning_toast(self.tr('Another contingency analysis is being executed now...'))

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

            self.update_available_results()
            self.colour_diagrams()
        else:
            self.show_error_toast(self.tr('Something went wrong, There are no ATC results.'))

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
                            warning_msg(
                                self.tr('There were no power flow values available. Linear flows will be used.'))
                            use_provided_flows = False
                            Pf_hvdc = None
                            Pf = None
                    else:
                        use_provided_flows = False
                        Pf_hvdc = None
                        Pf = None

                    if len(idx_from) == 0:
                        error_msg(self.tr('The area "from" has no buses!'))
                        return

                    if len(idx_to) == 0:
                        error_msg(self.tr('The area "to" has no buses!'))
                        return

                    if len(idx_br) == 0:
                        error_msg(self.tr('There are no inter-area Branches!'))
                        return

                    mode = self.ui.transferMethodComboBox.currentData()
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

                    drv = sim.AvailableTransferCapacityTimeSeriesDriver(
                        grid=self.circuit,
                        options=options,
                        time_indices=self.get_time_indices(),
                        clustering_results=self.get_clustering_results()
                    )

                    self.session.run(drv,
                                     post_func=self.post_available_transfer_capacity_ts,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                    self.add_simulation(SimulationTypes.NetTransferCapacityTS_run)
                    self.LOCK()

                else:
                    self.show_warning_toast(self.tr('Another ATC time series is being executed now...'))
            else:
                self.show_warning_toast(self.tr('There are no time series!'))
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

            self.update_available_results()
            self.colour_diagrams()
        else:
            self.show_error_toast(self.tr('Something went wrong, There are no ATC time series results.'))

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
                        sel_buses = self.get_diagram_selected_buses()
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
                            warning_msg(self.tr('You have selected a group of buses with no power injection.\n'
                                                'this will result in an infinite continuation, since the loading variation '
                                                'of buses with zero injection will be infinite.'),
                                        self.tr('Continuation Power Flow'))
                            return

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
                                                                  stop_at=self.ui.vc_stop_at_comboBox.currentData(),
                                                                  verbose=0)

                    if use_alpha:
                        """
                        use the current power situation as start
                        and a linear combination of the current situation as target
                        """
                        # lock the UI
                        self.LOCK()

                        drv: sim.ContinuationPowerFlowDriver | None = None
                        try:
                            self.ui.progress_label.setText(
                                QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

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
                            self.add_simulation(SimulationTypes.ContinuationPowerFlow_run)
                            self.session.run(drv,
                                             post_func=self.post_continuation_power_flow,
                                             prog_func=self.ui.progressBar.setValue,
                                             text_func=self.ui.progress_label.setText)
                        except Exception as e:
                            error_message: str = str(e)
                            self.remove_simulation(SimulationTypes.ContinuationPowerFlow_run)
                            self.UNLOCK()
                            self.show_error_toast(self.tr("Voltage stability failed to start"), duration=4000)
                            if drv is not None:
                                drv.logger.add_error(error_message)
                                self.show_logs(logger=drv.logger, name=self.tr("Voltage stability logs"))
                            else:
                                pass

                    elif use_profiles:
                        """
                        Here the start and finish power states are taken from the profiles
                        """
                        if start_idx > -1 and end_idx > -1:

                            # lock the UI
                            self.LOCK()

                            drv: sim.ContinuationPowerFlowDriver | None = None
                            try:
                                nc_start = compile_numerical_circuit_at(circuit=self.circuit, t_idx=start_idx)
                                Sbus_init = nc_start.get_power_injections_pu()

                                nc_end = compile_numerical_circuit_at(circuit=self.circuit, t_idx=end_idx)
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
                                self.add_simulation(SimulationTypes.ContinuationPowerFlow_run)
                                self.session.run(drv,
                                                 post_func=self.post_continuation_power_flow,
                                                 prog_func=self.ui.progressBar.setValue,
                                                 text_func=self.ui.progress_label.setText)
                            except Exception as e:
                                error_message: str = str(e)
                                self.remove_simulation(SimulationTypes.ContinuationPowerFlow_run)
                                self.UNLOCK()
                                self.show_error_toast(self.tr("Voltage stability failed to start"), duration=4000)
                                if drv is not None:
                                    drv.logger.add_error(error_message)
                                    self.show_logs(logger=drv.logger, name=self.tr("Voltage stability logs"))
                                else:
                                    pass
                        else:
                            self.show_warning_toast(
                                self.tr('Check the selected start and finnish time series indices.'))
                else:
                    self.show_warning_toast(self.tr('Another voltage collapse simulation is running...'))
            else:
                info_msg(self.tr('Run a power flow simulation first.\n'
                                 'The results are needed to initialize this simulation.'))
        else:
            pass

    def post_continuation_power_flow(self):
        """
        Actions performed after the voltage stability. Launched by the thread after its execution
        :return:
        """
        drv, results = self.session.continuation_power_flow

        self.remove_simulation(SimulationTypes.ContinuationPowerFlow_run)

        if results is not None:

            if results.voltages is not None and len(results.voltages) > 0:
                self.update_available_results()
                self.colour_diagrams()
            else:
                self.session.delete_driver(SimulationTypes.ContinuationPowerFlow_run)
                self.show_warning_toast(self.tr('The voltage stability did not converge.\n'
                                                'Is this case already at the collapse limit?'), 5000)
                if drv is not None:
                    if drv.logger.has_logs():
                        self.show_logs(logger=drv.logger, name=self.tr("Voltage stability logs"))
                    else:
                        pass
                else:
                    pass
        else:
            self.session.delete_driver(SimulationTypes.ContinuationPowerFlow_run)
            self.show_error_toast(self.tr('Something went wrong, There are no voltage stability results.'))
            if drv is not None:
                if drv.logger.has_logs():
                    self.show_logs(logger=drv.logger, name=self.tr("Voltage stability logs"))
                else:
                    pass
            else:
                pass

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

                    self.ui.progress_label.setText(
                        QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

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
                    self.show_warning_toast(self.tr('There are no time series.'))
            else:
                self.show_warning_toast(self.tr('Another time series power flow is being executed now...'))
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
            self.show_warning_toast(self.tr('No results for the time series simulation.'))

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_stochastic(self):
        """
        Run a Monte Carlo simulation
        @return:
        """

        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.MonteCarlo_run):

                if self.valid_time_series():

                    self.LOCK()

                    self.add_simulation(SimulationTypes.StochasticPowerFlow)

                    self.ui.progress_label.setText(
                        QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                    pf_options = self.get_selected_power_flow_options()

                    simulation_type = self.ui.stochastic_pf_method_comboBox.currentData()

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
                    self.show_warning_toast(self.tr('Stochastic power flow needs at least one time-series sample.'))

            else:
                self.show_warning_toast(self.tr('Another Monte Carlo simulation is running...'))

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
        solver = self.ui.lpf_solver_comboBox.currentData()
        dispatch_mode = self.ui.opfDispatchModeComboBox.currentData()
        mip_solver = self.ui.mip_solver_comboBox.currentData() or MIPSolvers.HIGHS
        time_grouping = self.ui.opf_time_grouping_comboBox.currentData()
        zonal_grouping = self.ui.opfZonalGroupByComboBox.currentData()
        pf_options = self.get_selected_power_flow_options()
        consider_contingencies = self.ui.considerContingenciesOpfCheckBox.isChecked()
        contingency_groups_used = self.get_contingency_groups_matching_the_filter()
        skip_generation_limits = self.ui.skipOpfGenerationLimitsCheckBox.isChecked()
        lodf_tolerance = self.ui.opfContingencyToleranceSpinBox.value()
        consider_ramps = self.ui.opfConsiderRampsCheckBox.isChecked()
        consider_time_up_down = self.ui.opfConsiderUpDownTimeCheckBox.isChecked()
        area_spinning_reserve = self.ui.opfSpinningReserveCheckBox.isChecked()
        generate_report = self.ui.addOptimalPowerFlowReportCheckBox.isChecked()
        robust = self.ui.fixOpfCheckBox.isChecked()
        use_glsk_as_cost = self.ui.useGslkAsCostsOpfCheckBox.isChecked()
        quadratic_costs = self.ui.quadraticCostsOpfCheckBox.isChecked()
        add_losses_approximation = self.ui.approximateLossesOpfCheckBox.isChecked()
        _, pf_results = self.session.power_flow

        report_formulation = self.ui.save_mip_checkBox.isChecked()

        if dispatch_mode == OpfDispatchMode.InterAreaRedispatch:

            # available transfer capacity inter areas
            inter_aggregation_info: dev.InterAggregationInfo | None = self.get_compatible_from_to_buses_and_inter_branches()

            if len(inter_aggregation_info.lst_from) == 0:
                self.show_error_toast(self.tr('The area "from" has no buses!'), 5000)
                return None

            if len(inter_aggregation_info.lst_to) == 0:
                self.show_error_toast(self.tr('The area "to" has no buses!'), 5000)
                return None
        else:
            inter_aggregation_info = None

        ips_method = self.ui.ips_method_comboBox.currentData()
        ips_tolerance = 1.0 / (10.0 ** self.ui.ips_tolerance_spinBox.value())
        ips_iterations = self.ui.ips_iterations_spinBox.value()
        ips_trust_radius = self.ui.ips_trust_radius_doubleSpinBox.value()
        ips_init_with_pf = self.ui.ips_initialize_with_pf_checkBox.isChecked()
        ips_control_q_limits = self.ui.ips_control_Qlimits_checkBox.isChecked()

        if pf_results is not None:
            acopf_v0 = pf_results.voltage
            acopf_S0 = pf_results.Sbus
            acopf_pf_converged = bool(pf_results.converged)
        else:
            if ips_init_with_pf and solver == SolverType.NONLINEAR_OPF:
                self.show_warning_toast("Run a power flow first")
                ips_init_with_pf = False

            acopf_v0 = None
            acopf_S0 = None
            acopf_pf_converged = False

        verbose = self.ui.ips_verbose_spinBox.value()

        mip_framework = self.ui.mip_framework_comboBox.currentData()

        options = sim.OptimalPowerFlowOptions(
            solver=solver,
            dispatch_mode=dispatch_mode,
            time_grouping=time_grouping,
            zonal_grouping=zonal_grouping,
            mip_solver=mip_solver,
            power_flow_options=pf_options,
            consider_contingencies=consider_contingencies,
            contingency_groups_used=contingency_groups_used,
            skip_generation_limits=skip_generation_limits,
            lodf_tolerance=lodf_tolerance,
            inter_aggregation_info=inter_aggregation_info,
            consider_ramps=consider_ramps,
            consider_time_up_down=consider_time_up_down,
            area_spinning_reserve=area_spinning_reserve,
            report_formulation=report_formulation,
            generate_report=generate_report,
            use_glsk_as_cost=use_glsk_as_cost,
            quadratic_costs=quadratic_costs,
            add_losses_approximation=add_losses_approximation,
            ips_method=ips_method,
            ips_tolerance=ips_tolerance,
            ips_iterations=ips_iterations,
            ips_trust_radius=ips_trust_radius,
            ips_init_with_pf=ips_init_with_pf,
            ips_control_q_limits=ips_control_q_limits,
            acopf_v0=acopf_v0,
            acopf_S0=acopf_S0,
            acopf_pf_converged=acopf_pf_converged,
            robust=robust,
            verbose=verbose,
            mip_framework=mip_framework
        )

        return options

    def run_opf(self) -> None:
        """
        Run OPF simulation
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.OPF_run):

                self.remove_simulation(SimulationTypes.OPF_run)

                self.ui.progress_label.setText('Running optimal power flow...')

                options: sim.OptimalPowerFlowOptions | None = self.get_opf_options()

                if options is not None:
                    if (options.solver == SolverType.NONLINEAR_OPF
                            and self.circuit.get_fluid_nodes_number() > 0):
                        self.show_warning_toast(self.tr("Fluid nodes are ignored for nonlinear OPF"))
                    else:
                        pass
                else:
                    return None

                # set power flow object instance
                drv: sim.OptimalPowerFlowDriver = sim.OptimalPowerFlowDriver(
                    grid=self.circuit,
                    options=options,
                    engine=self.get_preferred_engine()
                )

                self.add_simulation(SimulationTypes.OPF_run)
                self.LOCK()

                try:
                    self.session.run(drv,
                                     post_func=self.post_opf,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                except Exception as e:
                    error_message: str = str(e)
                    self.remove_simulation(SimulationTypes.OPF_run)
                    self.UNLOCK()
                    self.show_error_toast(self.tr("Optimal power flow failed to start"), duration=4000)
                    drv.logger.add_error(error_message)
                    self.show_logs(logger=drv.logger, name=self.tr("Optimal power flow logs"))

            else:
                self.show_warning_toast(self.tr('Another OPF is being run...'))
                return None
        else:
            return None

    def post_opf(self) -> None:
        """
        Actions to run after the OPF simulation
        """
        drv, results = self.session.optimal_power_flow

        self.remove_simulation(SimulationTypes.OPF_run)

        if results is not None:

            if results.converged:
                self.show_info_toast(self.tr("Optimal power flow converged :)"))
            else:
                self.show_warning_toast(self.tr('Optimal power flow not converged :/\n'
                                                'Check that all Branches have rating and \n'
                                                'that the generator bounds are ok.\n'
                                                'You may also use the diagnostic tool (F8)'),
                                        duration=4000)

            self.update_available_results()

            self.colour_diagrams()

        else:
            self.show_error_toast(self.tr('Something went wrong, there are no OPF results.'), duration=4000)
            if drv is not None:
                if drv.logger.has_logs():
                    self.show_logs(logger=drv.logger, name=self.tr("Optimal power flow logs"))
                else:
                    pass
            else:
                pass

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_opf_time_series(self) -> None:
        """
        OPF Time Series run
        """
        if self.circuit.valid_for_simulation():

            if self.circuit.has_time_series:
                if not self.session.is_this_running(SimulationTypes.OPFTimeSeries_run):

                    if self.circuit.time_profile is not None:

                        # get the power flow options from the GUI
                        options: sim.OptimalPowerFlowOptions | None = self.get_opf_options()

                        if options is not None:
                            time_indices: IntVec | None = self.get_time_indices()

                            if time_indices is not None:
                                if len(time_indices) <= 1:
                                    self.show_warning_toast(
                                        self.tr("Running OPF time series with only one time step in range")
                                    )
                                else:
                                    pass
                            else:
                                self.show_warning_toast(self.tr('There are no time series...'))
                                return None

                            if (options.solver == SolverType.NONLINEAR_OPF
                                    and self.circuit.get_fluid_nodes_number() > 0):
                                self.show_warning_toast(self.tr("Fluid nodes are ignored for this simulation"))
                            else:
                                pass

                            # Compile the grid in the worker after the launch state is registered.
                            self.ui.progress_label.setText(
                                QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                            # create the OPF time series instance
                            # if non_sequential:
                            drv: sim.OptimalPowerFlowTimeSeriesDriver = sim.OptimalPowerFlowTimeSeriesDriver(
                                grid=self.circuit,
                                options=options,
                                time_indices=time_indices,
                                clustering_results=self.get_clustering_results()
                            )

                            drv.engine = self.get_preferred_engine()

                            self.add_simulation(SimulationTypes.OPFTimeSeries_run)
                            self.LOCK()

                            try:
                                self.session.run(drv,
                                                 post_func=self.post_opf_time_series,
                                                 prog_func=self.ui.progressBar.setValue,
                                                 text_func=self.ui.progress_label.setText)
                            except Exception as e:
                                error_message: str = str(e)
                                self.remove_simulation(SimulationTypes.OPFTimeSeries_run)
                                self.UNLOCK()
                                self.show_error_toast(self.tr("OPF time series failed to start"), duration=4000)
                                drv.logger.add_error(error_message)
                                self.show_logs(logger=drv.logger, name=self.tr("OPF time series logs"))
                        else:
                            return None

                    else:
                        self.show_warning_toast(self.tr('There are no time series...'))

                else:
                    self.show_warning_toast(self.tr('Another OPF time series is running already...'))
            else:
                self.show_error_toast(self.tr("The grid doesn't have time series :/"))
        else:
            self.show_warning_toast(self.tr('Nothing to simulate...'))

    def post_opf_time_series(self) -> None:
        """
        Post OPF Time Series
        """

        drv, results = self.session.optimal_power_flow_ts

        # The worker sets ``results`` to ``None`` when it catches an exception.
        # Always remove the GUI marker so a failed thread cannot leave stale state.
        self.remove_simulation(SimulationTypes.OPFTimeSeries_run)

        if results is not None:

            # expand the clusters
            results.expand_clustered_results()

            self.update_available_results()

            self.colour_diagrams()

        else:
            self.show_error_toast(self.tr('Something went wrong, there are no OPF time series results.'), duration=4000)
            if drv is not None:
                if drv.logger.has_logs():
                    self.show_logs(logger=drv.logger, name=self.tr("OPF time series logs"))
                else:
                    pass
            else:
                pass

        if not self.session.is_anything_running():
            self.UNLOCK()

    def get_opf_ntc_options(self) -> Union[None, sim.OptimalNetTransferCapacityOptions]:
        """

        :return:
        """

        # available transfer capacity inter areas
        info: dev.InterAggregationInfo = self.get_compatible_from_to_buses_and_inter_branches()

        if not info.valid:
            error_msg(self.tr('There are no compatible areas'))
            return None

        idx_from = info.idx_bus_from
        idx_to = info.idx_bus_to
        idx_br = info.idx_branches

        # HVDC
        idx_hvdc_br = info.idx_hvdc
        sense_hvdc_br = info.sense_hvdc

        if len(idx_from) == 0:
            error_msg(self.tr('The "from" aggregation has no buses!'))
            return None

        if len(idx_to) == 0:
            error_msg(self.tr('The area "to" has no buses!'))
            return None

        if (len(idx_br) + len(idx_hvdc_br)) == 0:
            error_msg(self.tr('There are no inter-area Branches!'))
            return None

        opts = sim.OptimalNetTransferCapacityOptions(
            sending_bus_idx=idx_from,
            receiving_bus_idx=idx_to,
            transfer_method=self.ui.transferMethodComboBox.currentData(),
            loading_threshold_to_report=self.ui.ntcReportLoadingThresholdSpinBox.value(),
            skip_generation_limits=self.ui.skipNtcGenerationLimitsCheckBox.isChecked(),
            transmission_reliability_margin=self.ui.trmSpinBox.value(),  # MW
            branch_exchange_sensitivity=self.ui.ntcAlphaSpinBox.value() / 100.0,
            use_branch_exchange_sensitivity=self.ui.ntcSelectBasedOnExchangeSensitivityCheckBox.isChecked(),
            branch_rating_contribution=self.ui.ntcLoadRuleSpinBox.value() / 100.0,
            monitor_only_ntc_load_rule_branches=self.ui.ntcSelectBasedOnAcerCriteriaCheckBox.isChecked(),
            consider_contingencies=self.ui.consider_ntc_contingencies_checkBox.isChecked(),
            strict_formulation=self.ui.strict_ntc_formulation_checkBox.isChecked(),
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

                    # set power flow object instance
                    drv = sim.OptimalNetTransferCapacityDriver(grid=self.circuit, options=options)

                    self.LOCK()
                    self.session.run(drv,
                                     post_func=self.post_opf_ntc,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)

            else:
                self.show_warning_toast(self.tr('Another OPF is being run...'))
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

            # three possible solutions: optimal, optimal-but-relaxed, or not optimal.
            solution_state = results.get_solution_state(slack_tol_mw=0.1)
            total_slack_mw = results.get_total_slack_mw()
            if solution_state == SolutionState.Optimal:
                if drv.logger.error_count() == 0:
                    self.show_info_toast("Optimal result")
                else:
                    self.show_warning_toast("Optimal result, but check the logs")
            elif solution_state == SolutionState.Relaxed:
                self.show_warning_toast(f"Feasible only with relaxed limits: "
                                        f"{total_slack_mw:.1f} MW of slack (see the overloads results)")
            else:
                self.show_warning_toast("Not optimal result :/")

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_opf_ntc_ts(self):
        """
        Run OPF NTC time series simulation
        """
        if self.circuit.valid_for_simulation():
            if self.circuit.has_time_series:
                if not self.session.is_this_running(SimulationTypes.OPF_NTC_TS_run):

                    self.remove_simulation(SimulationTypes.OPF_NTC_TS_run)

                    options = self.get_opf_ntc_options()

                    if options is None:
                        return

                    else:

                        self.ui.progress_label.setText('Running optimal net transfer capacity time series...')

                        # set optimal net transfer capacity driver instance
                        drv = sim.OptimalNetTransferCapacityTimeSeriesDriver(
                            grid=self.circuit,
                            options=options,
                            time_indices=self.get_time_indices(),
                            clustering_results=self.get_clustering_results()
                        )

                        self.LOCK()
                        self.session.run(drv,
                                         post_func=self.post_opf_ntc_ts,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)

                else:
                    self.show_warning_toast(self.tr('Another Optimal NCT time series is being run...'))
            else:
                self.show_error_toast(self.tr("The grid doesn't have time series :/"))
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
                self.show_error_toast(self.tr('There are no PTDF results :/'))

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

        _, results = self.session.node_groups_driver

        if results is not None:
            self.remove_simulation(SimulationTypes.InputsAnalysis_run)
            self.update_available_results()
            self.colour_diagrams()

        if not self.session.is_anything_running():
            self.UNLOCK()

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
                self.show_warning_toast(self.tr('Another inputs analysis is being run...'))
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
                        cmap: NativeColorMap = NativeColorMap(stops=seq)

                        self.buses_for_storage = list()
                        colors = list()

                        # get all batteries grouped by bus
                        batt_by_bus = self.circuit.get_batteries_by_bus()

                        for i, freq in zip(idx, frequencies):

                            bus: dev.Bus = self.circuit.buses[i]
                            batts = batt_by_bus.get(bus, None)

                            # add a marker to the bus if there are no batteries in it
                            if batts is None:
                                self.buses_for_storage.append(bus)
                                r, g, b, a = cmap(freq / fmax)
                                color = QtGui.QColor(r * 255, g * 255, b * 255, a * 255)
                                colors.append(color)

                        self.set_big_bus_marker_colours(buses=self.buses_for_storage, colors=colors, tool_tips=None)
                    else:

                        info_msg(self.tr('No problems were detected, therefore no storage is suggested'),
                                 self.tr('Storage location'))

                else:
                    warning_msg(self.tr('There is no time series simulation.\n It is needed for this functionality.'),
                                self.tr('Storage location'))

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
            t_idx = self.get_diagram_slider_index()
            bus_names = np.array([b.name for b in self.circuit.buses])
            sigma_driver = sim.SigmaAnalysisDriver(grid=self.circuit, options=options, t_idx=t_idx)
            sigma_driver.run()

            if not sigma_driver.results.converged:
                self.show_error_toast("Sigma coefficients did not converge :(")

            old_dialog: QtWidgets.QMainWindow | QtWidgets.QDialog | None = self.window_manager.get(
                "sigma_analysis_dialogue"
            )
            if isinstance(old_dialog, SigmaAnalysisGUI) and is_dialog_available(dialog=old_dialog):
                old_dialog.grid = self.circuit
                old_dialog.options = options
                old_dialog.t_idx = t_idx
                old_dialog.bus_names = bus_names
                old_dialog.setup_time_slider(t_idx=t_idx)
                old_dialog.apply_results(results=sigma_driver.results, bus_names=bus_names)
                old_dialog.resize(int(1.61 * 600.0), 550)
                self.show_dialogue(win=old_dialog, key="sigma_analysis_dialogue")
            else:
                sigma_dialogue: SigmaAnalysisGUI = SigmaAnalysisGUI(
                    parent=self,
                    results=sigma_driver.results,
                    bus_names=bus_names,
                    grid=self.circuit,
                    options=options,
                    t_idx=t_idx,
                    classical_sigma=False,
                    dpr_use_stored_guess=True,
                    dpr_control_q=options.control_Q,
                    dpr_control_discrete_shunts=True,
                    dpr_control_qv_droop=True,
                    dpr_distributed_slack=options.distributed_slack,
                )
                sigma_dialogue.resize(int(1.61 * 600.0), 550)
                self.show_dialogue(win=sigma_dialogue, key="sigma_analysis_dialogue")

    def run_investments_evaluation(self) -> None:
        """
        Run investments evaluation
        """
        if self.circuit.valid_for_simulation():

            if len(self.circuit.investments_groups) > 0:

                if not self.session.is_this_running(SimulationTypes.InvestmentsEvaluation_run):

                    # evaluation method
                    method = self.ui.investment_evaluation_method_ComboBox.currentData()
                    obj_fn_tpe = self.ui.investment_evaluation_objfunc_ComboBox.currentData()

                    # maximum number of function evaluations as a factor of the number of investments
                    max_eval = self.ui.max_investments_evluation_number_spinBox.value() * len(
                        self.circuit.investments_groups)

                    # compose the options
                    options = sim.InvestmentsEvaluationOptions(
                        solver=method,
                        max_eval=max_eval,
                        pf_options=self.get_selected_power_flow_options(),
                        opf_options=self.get_opf_options(),
                        obj_tpe=obj_fn_tpe,
                        plugin_fcn_ptr=None,
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

                    elif obj_fn_tpe == InvestmentsEvaluationObjectives.LinearOptimalPowerFlowTimeSeries:

                        if self.circuit.has_time_series:
                            problem = sim.TimeSeriesLinearOptimalPowerFlowInvestmentProblem(
                                grid=self.circuit,
                                opf_options=self.get_opf_options(),
                                time_indices=self.get_time_indices(),
                                clustering_results=self.get_clustering_results(),
                                engine=self.get_preferred_engine()
                            )
                        else:
                            self.show_warning_toast(self.tr('Linear OPF investment studies need time data...'))
                            return

                    elif obj_fn_tpe == InvestmentsEvaluationObjectives.OptimalPowerFlowThenPowerFlowTimeSeries:

                        if self.circuit.has_time_series:
                            problem = sim.TimeSeriesOptimalPowerFlowThenPowerFlowInvestmentProblem(
                                grid=self.circuit,
                                opf_options=self.get_opf_options(),
                                pf_options=self.get_selected_power_flow_options(),
                                time_indices=self.get_time_indices(),
                                clustering_results=self.get_clustering_results(),
                                engine=self.get_preferred_engine()
                            )
                        else:
                            self.show_warning_toast(
                                self.tr('Linear OPF and power flow investment studies need time data...'))
                            return

                    elif obj_fn_tpe == InvestmentsEvaluationObjectives.GenerationAdequacy:

                        if self.circuit.has_time_series:
                            problem = sim.AdequacyInvestmentProblem(
                                grid=self.circuit,
                                n_monte_carlo_sim=self.ui.max_iterations_reliability_spinBox.value(),
                                use_monte_carlo=True,
                                save_file=False,
                                time_indices=self.get_time_indices(),
                                clustering_results=self.get_clustering_results()
                            )
                        else:
                            self.show_warning_toast(self.tr('Adequacy studies need time data...'))
                            return

                    elif obj_fn_tpe == InvestmentsEvaluationObjectives.SimpleDispatch:

                        if self.circuit.has_time_series:
                            problem = sim.AdequacyInvestmentProblem(
                                grid=self.circuit,
                                n_monte_carlo_sim=self.ui.max_iterations_reliability_spinBox.value(),
                                use_firm_capacity_penalty=self.ui.firmCapacityShareSpinBox.value() > 0,
                                minimum_firm_share=self.ui.firmCapacityShareSpinBox.value() / 100.0,
                                use_monte_carlo=False,
                                save_file=False,
                                time_indices=self.get_time_indices(),
                                clustering_results=self.get_clustering_results()
                            )
                        else:
                            self.show_warning_toast(self.tr('Adequacy studies need time data...'))
                            return

                    else:
                        self.show_error_toast(self.tr("Objective not supported yet :/"))
                        return

                    drv = sim.InvestmentsEvaluationDriver(
                        grid=self.circuit,
                        options=options,
                        problem=problem,
                        engine=self.get_preferred_engine()
                    )

                    self.add_simulation(SimulationTypes.InvestmentsEvaluation_run)
                    self.LOCK()
                    try:
                        self.session.run(
                            drv,
                            post_func=self.post_investments_evaluation,
                            prog_func=self.ui.progressBar.setValue,
                            text_func=self.ui.progress_label.setText
                        )
                    except Exception:
                        self.remove_simulation(SimulationTypes.InvestmentsEvaluation_run)
                        if not self.session.is_anything_running():
                            self.UNLOCK()
                        else:
                            pass
                        raise

                else:
                    self.show_warning_toast(self.tr('Another contingency analysis is being executed now...'))
            else:
                warning_msg(self.tr("There are no investment groups, "
                                    "you need to create some so that VeraGrid can evaluate them ;)"))

        else:
            pass

    def post_investments_evaluation(self) -> None:
        """
        Post investments evaluation
        """
        sender: QtCore.QObject | None = self.sender()
        if isinstance(sender, GcThread):
            driver = sender.driver
            results = driver.results
            worker_failed: bool = sender.has_failed()
        else:
            driver, results = self.session.investments_evaluation
            worker_failed = False

        self.remove_simulation(SimulationTypes.InvestmentsEvaluation_run)

        # update the results in the circuit structures
        if results is not None and not worker_failed:
            self.ui.progress_label.setText('Colouring investments evaluation results in the grid...')

            self.update_available_results()

            # Cache every Investment object in the live grid so the Variations-panel
            # click handler can deactivate them all before activating just the ones
            # in the clicked Pareto combination. We snapshot the list itself (not
            # device states) because per-click semantics are "force every touched
            # device to inactive, then activate the selected subset" — exactly the
            # convention the optimizer used. This avoids the bug where capturing
            # device.active states could leak True flags through the revert path.
            self._investments_all = list(self.circuit.investments)
            all_elements_dict, _ = self.circuit.get_all_elements_dict()

            # create a schematic diagram for the best Pareto-optimal investment combination
            if driver is not None and len(results.sorting_indices) > 0:
                best_x = results.x[results.sorting_indices[0], :]
                inv_list = driver.problem.get_investments_for_combination(x=best_x)

                # First deactivate every investment-touched device, then activate only the ones in
                # best_x — same all-off-then-selected convention the Variations-panel click handler
                # uses, so the state right after a run matches clicking the top Pareto row.
                self.circuit.set_investments_status(investments_list=self._investments_all,
                                                    apply_investment=False,
                                                    all_elements_dict=all_elements_dict)
                self.circuit.set_investments_status(investments_list=inv_list,
                                                    apply_investment=True,
                                                    all_elements_dict=all_elements_dict)
            else:
                # no Pareto results - nothing to apply
                pass

            # apply result-based colouring after the baseline + best-Pareto state is set
            self.colour_diagrams()
        else:
            if driver is not None and driver.logger.has_logs():
                self.show_logs(logger=driver.logger, name="Investments evaluation error")
            else:
                pass

            if worker_failed:
                self.show_error_toast(self.tr('Investments evaluation failed. Check the logs for details.'))
            else:
                self.show_warning_toast(self.tr('Investments evaluation finished without results.'))

        if not self.session.is_anything_running():
            self.UNLOCK()

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
                    warning_msg(self.tr('You cannot find {0} clusters for {1} time steps.\n'
                                        'Modify the number of clusters in the ML settings.').format(n_points, nt),
                                title=self.tr("Clustering"))

            else:
                self.show_warning_toast(self.tr('Another clustering is being executed now...'))
        else:
            pass

    def post_clustering(self):
        """
        Action performed after clustering.
        Returns:

        """
        # update the results in the circuit structures
        self.remove_simulation(SimulationTypes.ClusteringAnalysis_run)

        _, results = self.session.clustering
        if results is not None:

            self.update_available_results()
        else:
            self.show_error_toast(self.tr('Something went wrong, there are no clustering results.'))

        if not self.session.is_anything_running():
            self.UNLOCK()

    def fuse_devices(self):
        """
        Fuse the devices per node into a single device per category
        """
        ok = yes_no_question(self.tr("This action will fuse all the devices per node and per category. Are you sure?"),
                             self.tr("Fuse devices"))

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
                    error_msg(
                        self.tr("The number of clusters in the stored results is different from the specified :(\n"
                                "Run another clustering analysis."))
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
        sel_buses = self.get_diagram_selected_buses()
        capacity_nodes_idx = np.array([bus_dict[b] for _, b, _ in sel_buses])

        method = self.ui.nodal_capacity_method_comboBox.currentData()
        nodal_capacity_sign = self.ui.nodal_capacity_sense_SpinBox.value()

        opt = sim.NodalCapacityOptions(opf_options=self.get_opf_options(),
                                       capacity_nodes_idx=capacity_nodes_idx,
                                       nodal_capacity_sign=nodal_capacity_sign,
                                       method=method)

        return opt

    def run_nodal_capacity(self):
        """
        Nodal capacity snapshot run
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.NodalCapacity_run):

                options = self.get_nodal_capacity_options()
                if len(options.capacity_nodes_idx) == 0:
                    error_msg(text=self.tr("For this simulation, you need to select some buses from the interface"),
                              title=self.tr("Nodal hosting capacity"))
                    return

                self.remove_simulation(SimulationTypes.NodalCapacity_run)
                self.ui.progress_label.setText('Running nodal hosting capacity...')
                self.LOCK()

                drv = sim.NodalCapacityDriver(grid=self.circuit,
                                              options=options,
                                              engine=self.get_preferred_engine())

                self.add_simulation(SimulationTypes.NodalCapacity_run)
                try:
                    self.session.run(drv,
                                     post_func=self.post_nodal_capacity,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                except Exception as e:
                    error_message: str = str(e)
                    self.remove_simulation(SimulationTypes.NodalCapacity_run)
                    self.UNLOCK()
                    self.show_error_toast(self.tr("Nodal capacity failed to start"), duration=4000)
                    drv.logger.add_error(error_message)
                    self.show_logs(logger=drv.logger, name=self.tr("Nodal capacity logs"))
            else:
                self.show_warning_toast(self.tr('Another nodal capacity study is being run...'))

    def run_nodal_capacity_time_series(self):
        """
        OPF Time Series run
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.NodalCapacityTimeSeries_run):

                # get the power flow options from the GUI
                options = self.get_nodal_capacity_options()

                if len(options.capacity_nodes_idx) == 0:
                    error_msg(text=self.tr("For this simulation, you need to select some buses from the interface"),
                              title=self.tr("Nodal hosting capacity"))
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
                self.ui.progress_label.setText(self.tr("Compiling the grid..."))

                if options is not None:
                    # create the OPF time series instance
                    # if non_sequential:
                    drv = sim.NodalCapacityTimeSeriesDriver(grid=self.circuit,
                                                            options=options,
                                                            time_indices=time_indices,
                                                            clustering_results=clustering_results)

                    drv.engine = self.get_preferred_engine()

                    try:
                        self.session.run(drv,
                                         post_func=self.post_nodal_capacity_time_series,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)
                    except Exception as e:
                        error_message: str = str(e)
                        self.remove_simulation(SimulationTypes.NodalCapacityTimeSeries_run)
                        self.UNLOCK()
                        self.show_error_toast(self.tr("Nodal capacity time series failed to start"), duration=4000)
                        drv.logger.add_error(error_message)
                        self.show_logs(logger=drv.logger, name=self.tr("Nodal capacity time series logs"))

            else:
                self.show_warning_toast(self.tr('Another OPF time series is running already...'))

        else:
            pass

    def post_nodal_capacity(self):
        """
        Post nodal capacity
        """
        drv, results = self.session.nodal_capacity_optimization

        self.remove_simulation(SimulationTypes.NodalCapacity_run)

        if results is not None:
            self.update_available_results()
            self.colour_diagrams()
        else:
            self.session.delete_driver(SimulationTypes.NodalCapacity_run)
            self.show_error_toast(self.tr('Something went wrong, there are no nodal capacity results.'), duration=4000)
            if drv is not None:
                if drv.logger.has_logs():
                    self.show_logs(logger=drv.logger, name=self.tr("Nodal capacity logs"))
                else:
                    pass
            else:
                pass

        if not self.session.is_anything_running():
            self.UNLOCK()

    def post_nodal_capacity_time_series(self):
        """
        Post nodal capacity time series
        """

        drv, results = self.session.nodal_capacity_optimization_ts

        self.remove_simulation(SimulationTypes.NodalCapacityTimeSeries_run)

        if results is not None:
            results.expand_clustered_results()
            self.update_available_results()
            self.colour_diagrams()
        else:
            self.session.delete_driver(SimulationTypes.NodalCapacityTimeSeries_run)
            self.show_error_toast(self.tr('Something went wrong, there are no nodal capacity time series results.'),
                                  duration=4000)
            if drv is not None:
                if drv.logger.has_logs():
                    self.show_logs(logger=drv.logger, name=self.tr("Nodal capacity time series logs"))
                else:
                    pass
            else:
                pass

        if not self.session.is_anything_running():
            self.UNLOCK()
        else:
            pass

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
                    self.ui.progress_label.setText(
                        QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                    pf_options = self.get_selected_power_flow_options()

                    mode = self.ui.reliability_method_comboBox.currentData()

                    drv = sim.ReliabilityStudyDriver(grid=self.circuit,
                                                     pf_options=pf_options,
                                                     time_indices=self.get_time_indices(),
                                                     reliability_mode=mode,
                                                     n_sim=self.ui.max_iterations_reliability_spinBox.value())

                    self.session.run(drv,
                                     post_func=self.post_reliability,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)

                else:
                    self.show_warning_toast(self.tr('Another reliability study is running already...'))
            else:
                self.show_warning_toast(self.tr('Reliability studies need time data...'))
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

    def run_rms(self) -> None:
        """
        Run an RMS simulation from one converged power-flow operating point.

        :return: None.
        """
        self.remove_simulation(SimulationTypes.RmsDynamic_run)

        _, pf_results = self.session.power_flow

        rms_options = self.get_selected_rms_simulation_options()
        if rms_options.simulation_time > 0.0:

            if pf_results is None:
                info_msg(self.tr('Run a power flow simulation first.\n'
                                 'The results are needed to initialize this simulation.'))
            else:
                if bool(pf_results.converged):
                    self.add_simulation(SimulationTypes.RmsDynamic_run)

                    # self.add_simulation(SimulationTypes.RmsDynamic_run)
                    self.ui.progress_label.setText('Running rms simulation...')
                    self.LOCK()

                    drv = sim.RmsSimulationDriver(grid=self.circuit,
                                                  options=self.get_selected_rms_simulation_options(),
                                                  pf_results=pf_results)

                    self.session.run(drv,
                                     post_func=self.post_rms,
                                     prog_func=self.ui.progressBar.setValue,
                                     text_func=self.ui.progress_label.setText)
                else:
                    info_msg(self.tr('The power flow did not converge.\n'
                                     'Resolve the operating point before running this RMS simulation.'))
        else:
            info_msg(self.tr('The simulation time is 0. Change it to a proper time in settings.'))

    def post_rms(self) -> None:
        """
        Finalize the RMS simulation workflow and report only active-group status.

        :return: None.
        """
        drv, results = self.session.rms_dynamic_simulation

        # A completed or failed worker is no longer an active simulation. Keep
        # this cleanup outside the results branch because an engine validation
        # error deliberately produces no result shell.
        self.remove_simulation(SimulationTypes.RmsDynamic_run)
        self.update_available_results()

        if results is not None:
            # Only active event groups are simulated, so the completion report
            # must ignore inactive groups whose default result flags remain False.
            active_group_indices: list[int] = list()
            group_count: int = min(len(self.circuit.rms_events_groups), len(results.rms_events_group_names))
            group_index: int
            for group_index in range(group_count):
                rms_events_group = self.circuit.rms_events_groups[group_index]
                if rms_events_group.active and results.has_event_group_results[group_index]:
                    active_group_indices.append(group_index)
                else:
                    pass

            if len(active_group_indices) > 0:
                # Report initialization failures only for groups that were part
                # of the executed simulation batch.
                bad_initialization_names: list[str] = list()
                active_index: int
                group_name: str
                for active_index in active_group_indices:
                    group_name = str(results.rms_events_group_names[active_index])
                    if results.well_initialized[active_index]:
                        pass
                    else:
                        bad_initialization_names.append(group_name)

                if len(bad_initialization_names) > 0:
                    group_name: str
                    for group_name in bad_initialization_names:
                        self.show_warning_toast(f"Simulation bad initialized for {group_name}:/")
                else:
                    self.show_info_toast(self.tr("Simulation well initialized for all active simulation groups :)"))

                # Report convergence failures only for groups that were part of
                # the executed simulation batch.
                not_converged_names: list[str] = list()
                for active_index in active_group_indices:
                    group_name = str(results.rms_events_group_names[active_index])
                    if results.converged[active_index]:
                        pass
                    else:
                        not_converged_names.append(group_name)

                if len(not_converged_names) > 0:
                    self.ui.progress_label.setText("RMS stopped with partial results")
                    if drv is not None and drv.logger.has_logs():
                        self.show_logs(logger=drv.logger, name="RMS simulation stopped")
                    self.show_error_toast(
                        f"RMS stopped; partial results available for {', '.join(not_converged_names)}",
                        duration=5000,
                    )
                else:
                    self.show_info_toast(self.tr("Simulation converged for all active simulation groups :)"))
            else:
                self.show_info_toast(self.tr("There are no active RMS event groups to report."))

        else:
            if drv.logger.has_logs():
                self.show_logs(logger=drv.logger, name="RMS simulation error")
            else:
                warning_msg(self.tr('There are no rms simulation results.'), self.tr('Rms simulation'))

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_emt(self):
        """
        Run emt simulation
        :return:
        """

        self.remove_simulation(SimulationTypes.EmtDynamic_run)

        logger = self.circuit.check_emt_models()
        if logger.has_errors():
            self.show_logs(name="EMT pre simulation check", logger=logger)
            return
        else:
            pass

        _, pf_results_3ph = self.session.power_flow_3ph

        _, pf_results = self.session.power_flow

        emt_options = self.get_selected_emt_simulation_options()
        if emt_options.simulation_time > 0.0:
            if pf_results_3ph is not None:

                self.add_simulation(SimulationTypes.EmtDynamic_run)
                self.ui.progress_label.setText('Running EMT simulation...')
                self.LOCK()

                drv = sim.EmtSimulationDriver(grid=self.circuit,
                                              options=self.get_selected_emt_simulation_options(),
                                              pf_results_3ph=pf_results_3ph,
                                              pf_results=pf_results)

                self.session.run(drv,
                                 post_func=self.post_emt,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            elif pf_results is not None:

                # self.add_simulation(SimulationTypes.RmsDynamic_run)
                self.ui.progress_label.setText(
                    'Running EMT simulation from balanced power flow results ...')
                self.LOCK()

                drv = sim.EmtSimulationDriver(grid=self.circuit,
                                              options=self.get_selected_emt_simulation_options(),
                                              pf_results=pf_results)

                self.session.run(drv,
                                 post_func=self.post_emt,
                                 prog_func=self.ui.progressBar.setValue,
                                 text_func=self.ui.progress_label.setText)

            else:
                info_msg(self.tr('Run a power flow simulation first.\n'
                                 'The results are needed to initialize this simulation.'))

        else:
            info_msg(self.tr('The simulation time is 0. Change it to a proper time in settings.'))

    def post_emt(self) -> None:
        """
        Finalize the EMT simulation workflow and report only active-group status.

        :return: None.
        """
        drv, results = self.session.emt_dynamic_simulation

        # A failed construction has no results object, but it has still finished.
        # Always clear the running entry so the GUI unlocks and can run again.
        self.remove_simulation(SimulationTypes.EmtDynamic_run)
        self.update_available_results()

        if results is not None:
            # Only active event groups are simulated, so the completion report
            # must ignore inactive groups whose default result flags remain False.
            active_group_indices: list[int] = list()
            group_count: int = min(len(self.circuit.emt_events_groups), len(results.emt_events_group_names))
            group_index: int
            for group_index in range(group_count):
                emt_events_group = self.circuit.emt_events_groups[group_index]
                if emt_events_group.active:
                    active_group_indices.append(group_index)
                else:
                    pass

            if len(active_group_indices) > 0:
                # Report initialization failures only for groups that were part
                # of the executed simulation batch.
                bad_initialization_names: list[str] = list()
                active_index: int
                group_name: str
                for active_index in active_group_indices:
                    group_name = str(results.emt_events_group_names[active_index])
                    if results.well_initialized[active_index]:
                        pass
                    else:
                        bad_initialization_names.append(group_name)

                if len(bad_initialization_names) > 0:
                    for group_name in bad_initialization_names:
                        self.show_warning_toast(f"Simulation bad initialized for {group_name}:/")
                else:
                    self.show_info_toast("Simulation well initialized for all active simulation groups :)")

                # Report convergence failures only for groups that were part of
                # the executed simulation batch.
                not_converged_names: list[str] = list()
                for active_index in active_group_indices:
                    group_name = str(results.emt_events_group_names[active_index])
                    if results.converged[active_index]:
                        pass
                    else:
                        not_converged_names.append(group_name)

                if len(not_converged_names) > 0:
                    for group_name in not_converged_names:
                        self.show_warning_toast(f"Simulation not converged for {group_name}:/")
                else:
                    self.show_info_toast("Simulation converged for all active simulation groups :)")
            else:
                self.show_info_toast("There are no active EMT event groups to report.")

        else:
            has_detailed_logs: bool = False

            # GcThread carries both the uncaught exception and the driver's logs,
            # so it is the authoritative source for construction failures.
            if drv.logger.has_logs():
                self.show_logs(logger=drv.logger, name="EMT simulation error")
                has_detailed_logs = True
            else:
                pass

            # Keep a driver fallback for failures reported without an uncaught
            # exception. Do not show it after the thread logger because the thread
            # already merges those records and duplicate dialogs obscure the cause.
            if has_detailed_logs:
                pass
            elif drv is not None and drv.logger.has_logs():
                self.show_logs(logger=drv.logger, name="EMT simulation logs")
                has_detailed_logs = True
            else:
                pass

            if has_detailed_logs:
                pass
            else:
                warning_msg(self.tr('There are no emt simulation results.'), self.tr('Emt simulation'))

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
                                     request_timeout_s=self.server_driver.request_timeout_s)
            driver.result_driver_signal.connect(self.session.register_driver)
            driver.finished.connect(self.post_run_remote_finished)

            self._remote_jobs[driver.idtag] = driver

            driver.start()

    def post_run_remote_finished(self) -> None:
        """
        Process one remote job only after its QThread has actually finished.

        :return: None.
        """
        sender: QtCore.QObject | None = self.sender()
        if isinstance(sender, RemoteJobDriver):
            self.post_run_remote(driver_idtag=sender.idtag)
        else:
            pass

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
                self.show_logs(remote_job_driver.logger, name="Remote connection logs")

            self.update_available_results()
            self.colour_diagrams()

            self._remote_jobs.pop(driver_idtag)

            self.show_info_toast(self.tr("Remote results received!"))

    def run_rms_small_signal_stability(self):
        """
        Run small-signal simulation RMS
        :return:
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.RmsSmallSignal_run):

                logger = self.circuit.check_rms_models()
                if logger.has_errors():
                    # Show dialogue
                    dlg = LogsDialogue(name=self.tr("Small-signal stability RMS pre simulation check"),
                                       logger=logger, parent=self)
                    dlg.setModal(True)
                    exec_dialog_safely(dialog=dlg)
                    return
                else:

                    _, pf_results = self.session.power_flow

                    if pf_results is not None:

                        self.add_simulation(SimulationTypes.RmsSmallSignal_run)

                        self.LOCK()

                        # Compile the grid
                        self.ui.progress_label.setText(
                            QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                        # get the small signal stability analysis simulation options from the GUI
                        options = self.get_selected_rms_small_signal_stability_options()
                        rms_options = self.get_selected_rms_simulation_options()

                        self.ui.progress_label.setText('Performing Small-Signal Stability analysis...')

                        drv = sim.SmallSignalStabilityRmsDriver(grid=self.circuit,
                                                                rms_options=rms_options,
                                                                sss_options=options,
                                                                pf_results=pf_results)

                        self.session.run(drv,
                                         post_func=self.post_rms_small_signal_stability,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)

                    else:
                        info_msg(self.tr('Run a power flow simulation first.\n'
                                         'The results are needed to initialize this simulation.'))

            else:
                self.show_warning_toast(
                    self.tr('Another Small-Signal stability analysis simulation is running already...'))

        else:
            pass

    def post_rms_small_signal_stability(self):
        """

        :return:
        """
        drv, results = self.session.small_signal_stability_simulation

        # The simulation is no longer part of the active-run list whether it
        # succeeded or failed.  Leaving it there makes subsequent runs appear
        # duplicated in the GUI state.
        self.remove_simulation(SimulationTypes.RmsSmallSignal_run)
        self.update_available_results()

        if results is not None:
            self.show_info_toast(self.tr("Small-signal stability analysis RMS has finished correctly!"))

        else:
            if drv.logger.has_logs():
                self.show_logs(logger=drv.logger, name="RMS small-signal simulation error")
            else:
                pass

            warning_msg(self.tr('There are no Small-Signal Stability analysis RMS results.'),
                        self.tr('Small-Signal Stability analysis RMS'))

        if not self.session.is_anything_running():
            self.UNLOCK()

    def run_emt_small_signal_stability(self):
        """
        Run small-signal simulation EMT
        :return:
        """
        if self.circuit.valid_for_simulation():

            if not self.session.is_this_running(SimulationTypes.EmtSmallSignal_run):

                logger = self.circuit.check_emt_models()
                if logger.has_errors():
                    # Show dialogue
                    dlg = LogsDialogue(name=self.tr("Small-signal stability EMT pre simulation check"),
                                       logger=logger, parent=self)
                    dlg.setModal(True)
                    exec_dialog_safely(dialog=dlg)
                    return
                else:

                    _, pf_results = self.session.power_flow_3ph

                    if pf_results is not None:

                        self.add_simulation(SimulationTypes.EmtSmallSignal_run)

                        self.LOCK()

                        # Compile the grid
                        self.ui.progress_label.setText(
                            QtCore.QCoreApplication.translate("SimulationsMain", "Compiling the grid..."))

                        # get the small-signal stability analysis simulation options from the GUI
                        sss_options = self.get_selected_emt_small_signal_stability_options()
                        emt_options = self.get_selected_emt_simulation_options()

                        self.ui.progress_label.setText('Performing Small-Signal Stability analysis...')

                        drv = sim.SmallSignalStabilityEmtDriver(grid=self.circuit,
                                                                emt_options=emt_options,
                                                                sss_options=sss_options,
                                                                pf_results=pf_results)

                        self.session.run(drv,
                                         post_func=self.post_emt_small_signal_stability,
                                         prog_func=self.ui.progressBar.setValue,
                                         text_func=self.ui.progress_label.setText)

                    else:
                        info_msg(self.tr('Run a power flow simulation first.\n'
                                         'The results are needed to initialize this simulation.'))
            else:
                self.show_warning_toast(
                    self.tr('Another Small-Signal stability analysis EMT simulation is running already...'))

        else:
            pass

    def post_emt_small_signal_stability(self) -> None:
        """Finalize EMT small-signal analysis and expose engine diagnostics.

        :return: None.
        """
        driver, results = self.session.small_signal_stability_simulation

        # Problem construction can fail before a results object exists, so the
        # active-run bookkeeping must be cleared on both outcomes.
        self.remove_simulation(SimulationTypes.EmtSmallSignal_run)
        self.update_available_results()

        if results is not None:
            self.show_info_toast(self.tr("Small-Signal stability analysis EMT has finished correctly!"))

        else:
            if driver.logger.has_logs():
                self.show_logs(logger=driver.logger, name="EMT small-signal simulation error")
            else:
                warning_msg(self.tr('There are no Small-Signal Stability analysis EMT results.'),
                            self.tr('Small-Signal Stability analysis EMT'))

        if not self.session.is_anything_running():
            self.UNLOCK()

    def update_available_mip_solvers(self):
        """

        :return:
        """
        current_mip_framework = self.ui.mip_framework_comboBox.currentData()
        mip_solvers = get_available_mip_solvers(tpe=current_mip_framework)
        mip_solver_enums: List[MIPSolvers] = list()
        mip_solver_lookup: Dict[str, MIPSolvers] = {solver.value: solver for solver in MIPSolvers}
        for solver_name in mip_solvers:
            mip_solver: MIPSolvers | None = mip_solver_lookup.get(solver_name, None)
            if mip_solver is None:
                pass
            else:
                mip_solver_enums.append(mip_solver)

        if len(mip_solver_enums) == 0:
            mip_solver_enums.append(MIPSolvers.HIGHS)
        else:
            pass

        self.ui.mip_solver_comboBox.setModel(
            gf.ComboModel(enum_values=mip_solver_enums, translate=self.tr)
        )

    def candidate_investment_generator(self):
        """
        Handler for the "Candidate investment generator" menu action.

        Runs the transmission-expansion candidate generator (AC PF -> LODF N-1 screening ->
        PTDF-ranked reinforcements -> shortlist -> AC PF verification) and lets the user pick
        which candidates to materialise as investments. Requires a selected diagram, mirroring
        the procedural grid expansion flow.

        :return:
        """
        if not self.circuit.valid_for_simulation():
            return

        # A diagram must be selected so the generated candidates can be drawn/attached, just
        # like the procedural grid expansion flow.
        current_diagram = self.get_selected_diagram_widget()
        if current_diagram is None:
            self.map_warning = MapWarningDialog(parent=self)
            exec_dialog_safely(dialog=self.map_warning)
            return

        self.candidate_investments_window = CandidateInvestmentsWindow(app=self)
        exec_dialog_safely(dialog=self.candidate_investments_window)

    def procedural_grid_expansion(self):
        """

        :return:
        """
        # Fetch the active diagram using the inherited method
        current_diagram = self.get_selected_diagram_widget()

        # Check if the active diagram is NOT a MapWidget
        if current_diagram is None:  # Before it was "if not isinstance(current_diagram, MapWidget):" but it did not work
            map_warning: MapWarningDialog = MapWarningDialog(parent=self)
            try:
                exec_dialog_safely(dialog=map_warning)
            finally:
                delete_dialog_safely(dialog=map_warning)
            return

        procedural_grid_window: ProceduralGridWindow = ProceduralGridWindow(app=self)
        try:
            exec_dialog_safely(dialog=procedural_grid_window)
        finally:
            delete_dialog_safely(dialog=procedural_grid_window)

    def catalogue_element_optimization(self) -> None:
        """
        Handler for the "Catalogue element optimization" menu action.

        Optimises the choice of catalogue templates for the user-selected branches using NSGA-3.
        Only AC `Line` and `Transformer2W` branches are considered at this stage.

        :return:
        """
        # Bail out early if the circuit cannot be simulated (no buses, etc.).
        if not self.circuit.valid_for_simulation():
            return
        else:
            pass

        # The catalogue optimization works off a schematic selection: only schematic widgets expose
        # the per-element selection API needed below.
        current_diagram = self.get_selected_diagram_widget()
        if not isinstance(current_diagram, SchematicWidget):
            warning_msg(self.tr("Catalogue optimization requires an active schematic diagram with a selection."),
                        self.tr("Catalogue optimization"))
            return
        else:
            pass

        # Pull the API objects underlying the selected schematic items and keep only the ones we
        # know how to optimise. The GUI restricts the user to AC lines and 2-winding transformers.
        api_selection = current_diagram._get_selection_api_objects()
        selected_branches: List[Union[dev.Line, dev.Transformer2W]] = list()
        for elm in api_selection:
            if isinstance(elm, dev.Line):
                selected_branches.append(elm)
            elif isinstance(elm, dev.Transformer2W):
                selected_branches.append(elm)
            else:
                pass  # ignore non-branch selections silently; they are not optimisable here

        # Empty selection: warn the user and stop. Running the optimization would have nothing to do.
        if len(selected_branches) == 0:
            warning_msg(self.tr("Select at least one AC line or two-winding transformer in the schematic "
                                "before running the catalogue optimization."),
                        self.tr("Catalogue optimization"))
            return
        else:
            pass

        # Block re-entry: only one catalogue optimization at a time.
        if self.session.is_this_running(SimulationTypes.CatalogueOptimization_run):
            self.show_warning_toast(self.tr('Another catalogue optimization is already running...'))
            return
        else:
            pass

        # Build the problem first; it raises ValueError if every selected branch ended up with
        # one option or fewer (in which case there is nothing to optimise over).
        try:
            problem = sim.CatalogueOptimizationProblem(
                grid=self.circuit,
                pf_options=self.get_selected_power_flow_options(),
                selected_branches=selected_branches,
                voltage_tolerance=0.1,
            )
        except ValueError as ex:
            warning_msg(str(ex), self.tr("Catalogue optimization"))
            return

        # Maximum number of evaluations: scale the per-decision spinbox by the number of slots.
        # Reuse the investments-evaluation spinbox to avoid adding a new GUI widget.
        max_eval: int = (self.ui.max_investments_evluation_number_spinBox.value()
                         * problem.n_vars())

        # Compose the options object.
        options = sim.CatalogueOptimizationOptions(
            max_eval=max_eval,
            pf_options=self.get_selected_power_flow_options(),
        )

        # Build and launch the driver via the standard session pipeline.
        drv = sim.CatalogueOptimizationDriver(
            grid=self.circuit,
            options=options,
            problem=problem,
        )

        self.session.run(
            drv,
            post_func=self.post_catalogue_element_optimization,
            prog_func=self.ui.progressBar.setValue,
            text_func=self.ui.progress_label.setText,
        )
        self.add_simulation(SimulationTypes.CatalogueOptimization_run)
        self.LOCK()

    def post_catalogue_element_optimization(self) -> None:
        """
        Post-execution callback for the catalogue optimization driver.

        Mirrors `post_investments_evaluation`: clears the running-simulation flag,
        refreshes the available-results combo, applies the best Pareto member's
        templates to the live MultiCircuit so the user lands on a usable grid
        state, and recolours the diagrams to expose the new results.

        :return:
        """
        driver, results = self.session.catalogue_optimization

        if results is not None:
            # Clear the "running" flag so the GUI re-enables future runs.
            self.remove_simulation(SimulationTypes.CatalogueOptimization_run)

            self.ui.progress_label.setText('Colouring catalogue optimization results in the grid...')

            self.update_available_results()

            # Apply the best Pareto member's templates to the live grid so the
            # diagram immediately reflects the optimizer's top recommendation.
            # The driver itself reverts state after every evaluation (via the
            # problem's _restore_baseline), so right now every branch is back
            # at its pre-evaluation baseline. We re-apply the chosen combo on
            # top so subsequent clicks in the Variations panel can use the
            # same restore-then-apply convention without ambiguity about what
            # state the grid is currently in.
            if driver is not None and len(results.sorting_indices) > 0:
                best_x: np.ndarray = results.x[results.sorting_indices[0], :]
                # Restore baseline first, then apply: matches the click handler
                # so the auto-displayed state is identical to what clicking the
                # same Pareto row would produce.
                driver.problem._restore_baseline()
                driver.problem._apply_combination(x=best_x)
            else:
                # No Pareto results available - leave the grid at baseline.
                pass

            self.colour_diagrams()
        else:
            pass

    def display_grid_analysis(self):
        """
        Display the grid analysis GUI
        """

        old_dialog: GridAnalysisGUI | None = self.window_manager.get("analysis_dialogue")
        if isinstance(old_dialog, GridAnalysisGUI) and is_dialog_available(dialog=old_dialog):
            # WindowManager keeps the existing keyed window, so refresh that
            # instance before asking it to show again.
            old_dialog.circuit = self.circuit
            old_dialog.power_flow_options = self.get_selected_power_flow_options()
            old_dialog.analyze_all()
            old_dialog.resize(int(1.61 * 600.0), 600)
            self.show_dialogue(win=old_dialog, key="analysis_dialogue")
        else:
            analysis_dialogue: GridAnalysisGUI = GridAnalysisGUI(
                circuit=self.circuit,
                power_flow_options=self.get_selected_power_flow_options(),
                parent=self
            )
            analysis_dialogue.resize(int(1.61 * 600.0), 600)
            self.show_dialogue(win=analysis_dialogue, key="analysis_dialogue")
