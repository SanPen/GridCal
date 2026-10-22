# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List
import time
import numpy as np
import pandas as pd
import scipy.sparse as sp

from VeraGridEngine.enumerations import DynamicEventTransitionType, ParamPowerFlowReferenceType
from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, Const, Expr, piecewise)
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, RmsInitializationMethod, DeviceType
from VeraGridEngine.basic_structures import Vec, ObjVec, BoolVec, Logger
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.initialization import init_pseudo_transient, _select_rms_initialization_method
from VeraGridEngine.Simulations.Rms.initialization_rms import (
    project_initial_algebraic_state, run_rms_consistent_initialization,
)
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import (
    build_rms_single_equation_compiler,
    init_explicit_common,
)
from VeraGridEngine.Simulations.Rms.problems.rms_problem_template import RmsProblemTemplate
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import (
    _build_runtime_expression_from_single_rms_event,
    _evaluate_rms_runtime_parameter_value_from_events,
)
from VeraGridEngine.Simulations.Rms.problems.rms_terminal_power_assembly import (
    assemble_rms_mapped_power_references,
    convert_rms_ac_power_balance_to_current_balance,
)
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Utils.Symbolic.jit_compiler import RMSCompiler
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_unified import (
    assign_static_api_object_mapping_for_device,
    get_api_parameter_initial_value_by_uid,
)
from VeraGridEngine.Simulations.driver_template import DummySignal
from VeraGridEngine.IO.fmu.co_simulation import (
    advance_rms_fmu_cs_devices,
    close_rms_fmu_cs_devices,
    initialize_rms_fmu_cs_devices,
    register_rms_fmu_cs_device,
)
from VeraGridEngine.IO.fmu.model_exchange import (
    advance_rms_fmu_me_devices,
    close_rms_fmu_me_devices,
    get_next_rms_fmu_me_event_time,
    initialize_rms_fmu_me_devices,
    _prepare_rms_fmu_me_state_event_retry,
    register_rms_fmu_me_device,
    resolve_rms_fmu_me_devices,
)
from VeraGridEngine.IO.fmu.profile import FmuMeEvaluationBudget


def _tic():
    return time.perf_counter()


def _toc(t0):
    return time.perf_counter() - t0


def setP(P: ObjVec, P_used: BoolVec, k: int, val: object):
    """
    Set or add to P value at index k.
    """
    if not P_used[k]:
        P[k] = val
        P_used[k] = True
    else:
        P[k] += val


def setQ(Q: ObjVec, Q_used: BoolVec, k: int, val: object):
    """
    Set or add to Q value at index k.
    """
    if not Q_used[k]:
        Q[k] = val
        Q_used[k] = True
    else:
        Q[k] += val


def setIr(Ir: ObjVec, Ir_used: BoolVec, k: int, val: object):
    """
    Set or add to Ir (real current) value at index k.
    """
    if not Ir_used[k]:
        Ir[k] = val
        Ir_used[k] = True
    else:
        Ir[k] += val


def setIi(Ii: ObjVec, Ii_used: BoolVec, k: int, val: object):
    """
    Set or add to Ii (imaginary current) value at index k.
    """
    if not Ii_used[k]:
        Ii[k] = val
        Ii_used[k] = True
    else:
        Ii[k] += val


class RmsProblemPhasor(RmsProblemTemplate):
    """
    Phasor-based DAE (Differential-Algebraic Equation) class.

    This class uses phasor representation (Vr, Vi) for voltages instead of polar coordinates (Vm, Va).
    The phasor representation makes current equations linear and is more suitable for certain analysis.

    Responsibilities:
        - Store state and algebraic variables (x, y) using phasor representation
        - Store Jacobian matrices
        - Store residual equations using phasor-based power flow equations
        - Store sparsity patterns
        - Convert between polar (power flow) and phasor (RMS) representations
    """
    VARS_NAME = "vars"
    VARIABLE_PARAMS_NAME = "vprms"
    CONSTANT_PARAMS_NAME = "cprms"
    DIFF_NAME = "diff"
    TIME_NAME = "glob_time"

    __slots__ = (
        "options",
        "logger",
        "sys_block",
        "sys_vars",
        "init_guess",
        "_static_parameters_values_mapping",
        "Sf",
        "St",
        "_state_vars",
        "_algebraic_vars",
        "_diff_vars",
        "_state_algeb_vars",
        "_variable_parameters",
        "_constant_parameters",
        "_state_eqs",
        "_algebraic_eqs",
        "_event_parameters_eqs",
        "_event_parameters_eqs0",
        "event_params_init_dict",
        "_continuous_runtime_events",
        "_uid2idx_vars",
        "_uid2idx_diff",
        "_uid2idx_params",
        "_uid2idx_event_params",
        "_uid2idx_t",
        "_vars_glob_name2uid",
        "_compiler_names_dict",
        "_alias_names_dict",
        "_n_state",
        "_n_alg",
        "_n_algebraic",
        "_n_diff",
        "_n_params",
        "_n_event_params",
        "_n_vars",
        "_constant_params",
        "_parameters_values",
        "_variable_parameters_values",
        "_glob_time",
        "_event_params_fn",
        "_rhs_state_fn",
        "_rhs_algeb_fn",
        "_derivative_fn",
        "_j11_fn",
        "_j12_fn",
        "_j21_fn",
        "_j22_fn",
        "_vars_info",
        "_fmu_cs_adapters",
        "_fmu_cs_initialized",
        "_fmu_me_adapters",
        "_fmu_me_initialized",
        "_fmu_me_evaluation_budget",
    )

    def __init__(self,
                 grid: MultiCircuit,
                 options: RmsOptions,
                 pf_results: PowerFlowResults | None,
                 progress_signal: DummySignal | None = None,
                 logger: Logger | None = None) -> None:
        """Assemble the phasor RMS problem and retain the caller's diagnostics.

        :param grid: Physical network whose assigned RMS Blocks are assembled.
        :param options: RMS formulation and initialization configuration.
        :param pf_results: Existing power-flow initialization data; the current
            assembly requires a populated result despite its legacy optional type.
        :param progress_signal: Optional caller-owned numeric progress signal.
        :param logger: Caller-owned diagnostics; when absent, create a local Logger.
        :return: None; initialize the existing phasor problem instance.
        """
        super().__init__()

        # Keep constructor diagnostics in the logger already owned by the driver.
        self.logger: Logger = logger if logger is not None else Logger()
        self.progress_signal = progress_signal
        self.grid: MultiCircuit = grid
        self.power_flow_results: PowerFlowResults = pf_results
        self.Sf = self.power_flow_results.Sf / self.grid.Sbase
        self.St = self.power_flow_results.St / self.grid.Sbase
        self.options: RmsOptions = options

        # this is the general init guess that will contain all the variables init value
        self.init_guess: Dict[int, float] = dict()
        self._static_parameters_values_mapping: Dict[Var, Const] = dict()
        self.sys_block: Block = Block(children=[], in_vars=[])

        self._algebraic_vars: List[Var] = list()
        self._algebraic_eqs: List[Expr] = list()
        self._state_vars: List[Var] = list()
        self._state_eqs: List[Expr] = list()
        self._diff_vars: List[Var] = list()
        self._variable_parameters: List[Var] = list()
        self._event_parameters_eqs: List[Expr | Const] = list()
        self._constant_parameters: List[Var] = list()
        self._parameters_values: List[Const] = list()
        self._fmu_cs_adapters: List[object] = list()
        self._fmu_cs_initialized: bool = False
        self._fmu_me_adapters: List[object] = list()
        self._fmu_me_initialized: bool = False
        self._fmu_me_evaluation_budget: FmuMeEvaluationBudget | None = None

        # --------------------------------------------------------------------------------------------------------------
        # Initialize the RMS problem
        # --------------------------------------------------------------------------------------------------------------

        ######################### Initialize containers#############################
        total_init_explicit_time: float = 0
        t0 = time.perf_counter()

        # dictionaries to store device-variable ifo
        self._vars_info: Dict[ALL_DEV_TYPES, List[Var]] = dict()
        self._vars_glob_name2uid: Dict[str, int] = dict()

        # dictionaries for compilation names
        self._compiler_names_dict: Dict[int, str] = dict()
        self._alias_names_dict: Dict[int, str] = dict()

        # dictionaries for variable position in the variables arrays
        self._uid2idx_vars: Dict[int, int] = dict()
        self._uid2idx_event_params: Dict[int, int] = dict()
        self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()

        # create time global time variable and add it to the compilation dict
        self._glob_time: Var = Var(self.TIME_NAME)
        self._compiler_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._uid2idx_t[self._glob_time.uid] = 0

        # Dictionary of state and algebraic vars
        self.sys_vars: Dict[int, Var] = dict()

        # initialize balance equation arrays
        n = len(self.grid.buses)
        P: ObjVec = np.zeros(n, dtype=object)
        Q: ObjVec = np.zeros(n, dtype=object)
        P_used: BoolVec = np.zeros(n, dtype=bool)
        Q_used: BoolVec = np.zeros(n, dtype=bool)

        # Phasor current balance arrays (using current instead of power)
        Ir: ObjVec = np.zeros(n, dtype=object)
        Ii: ObjVec = np.zeros(n, dtype=object)
        Ir_used: BoolVec = np.zeros(n, dtype=bool)
        Ii_used: BoolVec = np.zeros(n, dtype=bool)
        branch_bus_r = np.zeros(n, dtype=float)
        branch_bus_i = np.zeros(n, dtype=float)

        # general indexes for variables and parameters
        self._n_vars = 0
        self._n_params = 0
        self._n_event_params = 0
        self._n_diff = 0

        self.event_params_init_dict: Dict[int, float | int | complex | None] = dict()
        diff_init_guess: Dict[int, float | int | complex | None] = dict()

        ######################################## Initialize devices ########################################

        # initialize buses
        bus_dict: Dict[Bus, int] = dict()
        for bus_num, elm in enumerate(self.grid.buses):
            # Todo: missing default initialization for the model
            bus_dict[elm] = bus_num

            # flatten model
            elm.rms_model.unify_blocks()

            self.add_variables_to_compilation_dicts(elm, elm.rms_model)

            # add init values from powerflow to initial guess
            if elm.is_dc:
                # DC bus: use Vdc (magnitude) - angle is not applicable for DC
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Vdc,
                                    np.abs(self.power_flow_results.voltage[bus_num]))
            else:
                # AC bus: use Vm and Va
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Vi,
                                    np.imag(self.power_flow_results.voltage[bus_num]))
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Vr,
                                    np.real(self.power_flow_results.voltage[bus_num]))

            # add model to system block
            self.sys_block.add(elm.rms_model)

        # initialize branches
        for branch_num, elm in enumerate(self.grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True)):
            # Todo: missing default initialization for the model
            # flatten model
            if elm.rms_model.empty():
                self.logger.add_error("No RMS model",
                                      device_class=elm.device_type.value,
                                      device=elm.name)
            else:
                elm.rms_model.unify_blocks()

                # if not isinstance(elm, Transformer2W):
                active_factor = 1.0 if elm.active else 0.0
                z2 = elm.R ** 2 + elm.X ** 2
                g_val = active_factor * float(elm.R / z2)
                b_val = active_factor * float(-elm.X / z2)
                bsh_val = active_factor * float(elm.B)

                elm.rms_model.parameters[
                elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.g]] = Const(g_val)
                elm.rms_model.parameters[
                elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.b]] = Const(b_val)
                elm.rms_model.parameters[
                elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.bsh]] = Const(bsh_val)

                # Line.G is already total system-pu shunt conductance. Supply
                # its declared slot with the same inactive gate as R/X/B so the
                # unchanged half-shunt law remains consistent with power flow.
                if isinstance(elm, Line) and ParamPowerFlowReferenceType.shunt_g_pu in elm.rms_model.api_obj_mapping:
                    shunt_g_value: float = active_factor * float(elm.G)
                    elm.rms_model.parameters[
                        elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.shunt_g_pu]
                    ] = Const(shunt_g_value)
                else:
                    pass

                if isinstance(elm, Transformer2W) and ParamPowerFlowReferenceType.gFe in elm.rms_model.api_obj_mapping:
                    g_fe_val = active_factor * float(elm.G)
                    elm.rms_model.parameters[
                        elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.gFe]
                    ] = Const(g_fe_val)
                else:
                    pass

                if isinstance(elm, Transformer2W):
                    vtap_f_value, vtap_t_value = elm.get_virtual_taps()
                    if ParamPowerFlowReferenceType.tap_module in elm.rms_model.api_obj_mapping:
                        elm.rms_model.parameters[
                            elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.tap_module]
                        ] = Const(float(elm.tap_module))
                    else:
                        pass
                    if ParamPowerFlowReferenceType.tap_phase in elm.rms_model.api_obj_mapping:
                        elm.rms_model.parameters[
                            elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.tap_phase]
                        ] = Const(float(elm.tap_phase))
                    else:
                        pass
                    if ParamPowerFlowReferenceType.vtap_f in elm.rms_model.api_obj_mapping:
                        elm.rms_model.parameters[
                            elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.vtap_f]
                        ] = Const(float(vtap_f_value))
                    else:
                        pass
                    if ParamPowerFlowReferenceType.vtap_t in elm.rms_model.api_obj_mapping:
                        elm.rms_model.parameters[
                            elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.vtap_t]
                        ] = Const(float(vtap_t_value))
                    else:
                        pass
                else:
                    if ParamPowerFlowReferenceType.vtap_f in elm.rms_model.api_obj_mapping:
                        elm.rms_model.parameters[elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.vtap_f]] = Const(1.0)
                    else:
                        pass
                    if ParamPowerFlowReferenceType.vtap_t in elm.rms_model.api_obj_mapping:
                        elm.rms_model.parameters[elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.vtap_t]] = Const(
                            float(elm.bus_from.Vnom / elm.bus_to.Vnom)
                        )
                    else:
                        pass

                self.add_variables_to_compilation_dicts(elm, elm.rms_model)
                register_rms_fmu_cs_device(self, elm, elm.rms_model)
                register_rms_fmu_me_device(self, elm, elm.rms_model)

                # Convert power flow results (S = P + jQ) to currents (I = S* / V*)
                # I = (P - jQ) / (Vr - jVi) = (P*Vr + Q*Vi) / |V|^2 + j*(P*Vi - Q*Vr) / |V|^2
                f_idx = bus_dict[elm.bus_from]
                t_idx = bus_dict[elm.bus_to]

                Vf = self.power_flow_results.voltage[f_idx]
                Vt = self.power_flow_results.voltage[t_idx]

                Sf = self.Sf[branch_num]
                St = self.St[branch_num]

                # From end current
                Vf_mag_sq = np.abs(Vf)**2
                Irf = (Sf.real * Vf.real + Sf.imag * Vf.imag) / Vf_mag_sq
                Iif = (Sf.real * Vf.imag - Sf.imag * Vf.real) / Vf_mag_sq

                # To end current
                Vt_mag_sq = np.abs(Vt)**2
                Irt = (St.real * Vt.real + St.imag * Vt.imag) / Vt_mag_sq
                Iit = (St.real * Vt.imag - St.imag * Vt.real) / Vt_mag_sq

                # add init values from powerflow to initial guess
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Irf, Irf)
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Iif, Iif)
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Irt, Irt)
                self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Iit, Iit)

                branch_bus_r[f_idx] += Irf
                branch_bus_i[f_idx] += Iif
                branch_bus_r[t_idx] += Irt
                branch_bus_i[t_idx] += Iit

                # Run explicit initialization for branches to solve algebraic equations
                if isinstance(elm, Transformer2W):

                    initialization_method: RmsInitializationMethod = _select_rms_initialization_method(
                        configured_method=self.options.initialization_method, mdl=elm.rms_model,
                        init_guess=self.init_guess, uid2idx_vars=self._uid2idx_vars)
                    if initialization_method in (RmsInitializationMethod.Explicit, RmsInitializationMethod.ConsistentNewton):
                        diff_init_guess = self._run_explicit_initialization(mdl=elm.rms_model, derivative_guess=diff_init_guess)

                    elif initialization_method == RmsInitializationMethod.PseudoTransient:
                        self.init_guess = init_pseudo_transient(
                            mdl=elm.rms_model,
                            sys_vars=self.sys_vars,
                            variable_parameters=self._variable_parameters,
                            event_parameters_eqs=self._event_parameters_eqs,
                            constant_parameters=self._constant_parameters,
                            init_guess=self.init_guess,
                            uid2idx_vars=self._uid2idx_vars,
                            uid2idx_params=self._uid2idx_params,
                            uid2idx_event_params=self._uid2idx_event_params,
                            compiler_names_dict=self._compiler_names_dict,
                            alias_names_dict=self._alias_names_dict,
                            VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                            TIME_NAME=self.TIME_NAME,
                            VARS_NAME=self.VARS_NAME,
                            DIFF_NAME=self.DIFF_NAME,
                            CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                        )
                    else:
                        raise ValueError("Not implemented initialization method")

                # add model to system block
                self.sys_block.add(elm.rms_model)

                # add variable to conservation equations of the bus to which the element is connected
                f = bus_dict[elm.bus_from]
                t = bus_dict[elm.bus_to]

                assembled_power = assemble_rms_mapped_power_references(
                    model=elm.rms_model,
                    bus_from_index=f,
                    bus_to_index=t,
                    bus_from_is_dc=elm.bus_from.is_dc,
                    bus_to_is_dc=elm.bus_to.is_dc,
                    active_power_balance=P,
                    active_power_balance_used=P_used,
                    reactive_power_balance=Q,
                    reactive_power_balance_used=Q_used,
                )
                if not assembled_power:
                    setIr(Ir, Ir_used, f, -elm.rms_model.E(VarPowerFlowReferenceType.Irf))
                    setIr(Ir, Ir_used, t, -elm.rms_model.E(VarPowerFlowReferenceType.Irt))
                    setIi(Ii, Ii_used, f, -elm.rms_model.E(VarPowerFlowReferenceType.Iif))
                    setIi(Ii, Ii_used, t, -elm.rms_model.E(VarPowerFlowReferenceType.Iit))
                else:
                    pass

        # Populating VSCs init guess
        for i, elm in enumerate(self.grid.get_vsc()):
            if elm.rms_model.empty():
                self.logger.add_error("No RMS model",
                                      device_class=elm.device_type.value,
                                      device=elm.name)
            else:
                mdl = elm.rms_model

                # flatten model to collect all variables including those from child blocks
                mdl.unify_blocks()

                St_vsc = (self.power_flow_results.St_vsc)/ self.grid.Sbase
                Sf_vsc = (self.power_flow_results.Pfn_vsc[i] + self.power_flow_results.Pfp_vsc[i])/self.grid.Sbase
                # fill init_guess

                self.add_variables_to_compilation_dicts(elm, mdl)
                self.set_init_guess(mdl, VarPowerFlowReferenceType.Pf, Sf_vsc)
                self.set_init_guess(mdl, VarPowerFlowReferenceType.Pt, St_vsc[i].real)
                self.set_init_guess(mdl, VarPowerFlowReferenceType.Qt, St_vsc[i].imag)

                f = bus_dict[elm.bus_from]
                t = bus_dict[elm.bus_to]
                dc_voltage_init: float = float(
                    np.abs(self.power_flow_results.voltage[f])
                )
                dc_current_init: float = float(self.power_flow_results.If_vsc[i])
                self.set_init_guess(
                    mdl,
                    VarPowerFlowReferenceType.Vf_dc,
                    dc_voltage_init,
                )
                self.set_init_guess(
                    mdl,
                    VarPowerFlowReferenceType.Idc,
                    dc_current_init,
                )
                assemble_rms_mapped_power_references(
                    model=mdl,
                    bus_from_index=f,
                    bus_to_index=t,
                    bus_from_is_dc=elm.bus_from.is_dc,
                    bus_to_is_dc=elm.bus_to.is_dc,
                    active_power_balance=P,
                    active_power_balance_used=P_used,
                    reactive_power_balance=Q,
                    reactive_power_balance_used=Q_used,
                )
                self.sys_block.add(mdl)

        # Populating HVDC init guess (similar to VSCs)
        for i, elm in enumerate(self.grid.get_hvdc()):
            if elm.rms_model.empty():
                self.logger.add_error("No RMS model",
                                      device_class=elm.device_type.value,
                                      device=elm.name)
            else:
                mdl = elm.rms_model

                Sf_hvdc = self.power_flow_results.Pf_hvdc[i] / self.grid.Sbase
                St_hvdc = self.power_flow_results.Pt_hvdc[i] / self.grid.Sbase

                self.add_variables_to_compilation_dicts(elm, mdl)

                # Set initialization values for HVDC
                # Real number only (no Q values)
                # self.set_init_guess(mdl, VarPowerFlowReferenceType.Pf, Pf_hvdc)
                # self.set_init_guess(mdl, VarPowerFlowReferenceType.Pt, Pt_hvdc)

                f = bus_dict[elm.bus_from]
                t = bus_dict[elm.bus_to]
                assemble_rms_mapped_power_references(
                    model=mdl,
                    bus_from_index=f,
                    bus_to_index=t,
                    bus_from_is_dc=elm.bus_from.is_dc,
                    bus_to_is_dc=elm.bus_to.is_dc,
                    active_power_balance=P,
                    active_power_balance_used=P_used,
                    reactive_power_balance=Q,
                    reactive_power_balance_used=Q_used,
                )
                self.sys_block.add(mdl)

        # initialize injections

        for elm in grid.get_vsc():

            if elm.rms_model.empty():
                self.logger.add_error("No RMS model",
                                      device_class=elm.device_type.value,
                                      device=elm.name)
            else:

                # flatten model - variables already registered in first VSC loop above
                elm.rms_model.unify_blocks()

                # find init values for the variables of this model
                initialization_method: RmsInitializationMethod = _select_rms_initialization_method(
                    configured_method=self.options.initialization_method, mdl=elm.rms_model,
                    init_guess=self.init_guess, uid2idx_vars=self._uid2idx_vars)
                if initialization_method in (RmsInitializationMethod.Explicit, RmsInitializationMethod.ConsistentNewton):
                    diff_init_guess = self._run_explicit_initialization(mdl=elm.rms_model, derivative_guess=diff_init_guess)
                elif initialization_method == RmsInitializationMethod.PseudoTransient:
                    self.init_guess = init_pseudo_transient(
                        mdl=elm.rms_model,
                        sys_vars=self.sys_vars,
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=self._event_parameters_eqs,
                        constant_parameters=self._constant_parameters,
                        init_guess=self.init_guess,
                        uid2idx_vars=self._uid2idx_vars,
                        uid2idx_params=self._uid2idx_params,
                        uid2idx_event_params=self._uid2idx_event_params,
                        compiler_names_dict=self._compiler_names_dict,
                        alias_names_dict=self._alias_names_dict,
                        VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                        TIME_NAME=self.TIME_NAME,
                        VARS_NAME=self.VARS_NAME,
                        DIFF_NAME=self.DIFF_NAME,
                        CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                    )

                else:
                    raise ValueError("Not implemented initialization method")
                # PF seeding already registered this canonical VSC model.
                # Initialization must not add a second procedural owner.

        injection_init_data = self.get_injection_init_data(bus_dict=bus_dict)

        def _s_to_i(S: complex, V: complex) -> tuple[float, float]:
            v2 = np.abs(V) ** 2
            if v2 > 0:
                ir_val = (S.real * V.real + S.imag * V.imag) / v2
                ii_val = (S.real * V.imag - S.imag * V.real) / v2
            else:
                ir_val = 0.0
                ii_val = 0.0
            return ir_val, ii_val

        # Build per-bus residual current budget for load-current devices (Ir0/Ii0 templates)
        n_bus = len(self.grid.buses)
        fixed_inj_r = np.zeros(n_bus, dtype=float)
        fixed_inj_i = np.zeros(n_bus, dtype=float)
        adjustable_count = np.zeros(n_bus, dtype=int)
        slack_gen_count = np.zeros(n_bus, dtype=int)

        for dev in grid.get_injection_devices_iter():
            if dev.rms_model.empty():
                continue
            bidx = bus_dict[dev.bus]
            if dev.bus.is_dc:
                continue

            has_ir = VarPowerFlowReferenceType.Ir in dev.rms_model.external_mapping
            has_ii = VarPowerFlowReferenceType.Ii in dev.rms_model.external_mapping
            is_adjustable_load_current = (
                    has_ir and has_ii and
                    ParamPowerFlowReferenceType.Ir0 in dev.rms_model.api_obj_mapping and
                    ParamPowerFlowReferenceType.Ii0 in dev.rms_model.api_obj_mapping
            )

            if is_adjustable_load_current:
                adjustable_count[bidx] += 1
                continue

            if dev.device_type == DeviceType.GeneratorDevice and dev.bus.is_slack:
                slack_gen_count[bidx] += 1
                continue

            Vbus_pf = self.power_flow_results.voltage[bidx]
            Sdev_pf = injection_init_data[dev.idtag]

            ir_pf, ii_pf = _s_to_i(Sdev_pf, Vbus_pf)
            fixed_inj_r[bidx] += ir_pf
            fixed_inj_i[bidx] += ii_pf

        residual_r = branch_bus_r - fixed_inj_r
        residual_i = branch_bus_i - fixed_inj_i
        remaining_adjustable = adjustable_count.copy()
        remaining_slack_gen = slack_gen_count.copy()

        for elm in grid.get_injection_devices_iter():

            if elm.rms_model.empty():
                self.logger.add_error("No RMS model",
                                      device_class=elm.device_type.value,
                                      device=elm.name)
            else:
                bus_index = bus_dict[elm.bus]
                Sdev: complex = injection_init_data[elm.idtag]

                if elm.device_type == DeviceType.ShuntDevice:
                    elm.rms_model.parameters[elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.g]] = Const(float(elm.G) / grid.Sbase)
                    elm.rms_model.parameters[elm.rms_model.api_obj_mapping[ParamPowerFlowReferenceType.b]] = Const(float(elm.B) / grid.Sbase)
                # Capture owner-local power targets before flattening merges API
                # enum keys from children. The shared provider owns balanced
                # AC source-unit conversion and initial activity semantics.
                if isinstance(elm, Load) and not elm.bus.is_dc:
                    mapped_load_values: Dict[Var, Const] = dict()
                    assign_static_api_object_mapping_for_device(
                        grid=grid, device=elm, mdl=elm.rms_model,
                        problem_mapping=mapped_load_values, logger=self.logger)
                    owner_block: Block
                    for owner_block in elm.rms_model.get_all_blocks():
                        power_reference: ParamPowerFlowReferenceType
                        for power_reference in (ParamPowerFlowReferenceType.Pl0, ParamPowerFlowReferenceType.Ql0):
                            power_parameter: Var | None = owner_block.api_obj_mapping.get(power_reference, None)
                            if power_parameter is not None:
                                mapped_power_value: Const | None = get_api_parameter_initial_value_by_uid(
                                    parameter=power_parameter, problem_mapping=mapped_load_values)
                                if mapped_power_value is not None:
                                    self._static_parameters_values_mapping[power_parameter] = mapped_power_value
                                    # Explicit initialization reads declarations
                                    # again; supply its existing UID seed channel
                                    # so it preserves the selected runtime value.
                                    self.event_params_init_dict[power_parameter.uid] = mapped_power_value.value
                                else:
                                    pass
                            else:
                                pass
                    # Retain only P/Q constants for runtime registration, never
                    # the broader temporary device mapping or source model.
                    del mapped_load_values
                else:
                    pass
                elm.rms_model.unify_blocks()
                self.add_variables_to_compilation_dicts(elm, elm.rms_model)
                register_rms_fmu_cs_device(self, elm, elm.rms_model)
                register_rms_fmu_me_device(self, elm, elm.rms_model)

                if elm.bus.is_dc:
                    # DC buses: use power directly if supported, otherwise skip
                    if VarPowerFlowReferenceType.P in elm.rms_model.external_mapping:
                        self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.P, Sdev.real)
                    if VarPowerFlowReferenceType.Ir in elm.rms_model.external_mapping:
                        # Approximate: I = P/V (assuming V ≈ 1)
                        self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Ir, Sdev.real)
                else:
                    # Phasor formulation: convert per-device power injection to current
                    Vbus = self.power_flow_results.voltage[bus_index]

                    has_ir = VarPowerFlowReferenceType.Ir in elm.rms_model.external_mapping
                    has_ii = VarPowerFlowReferenceType.Ii in elm.rms_model.external_mapping
                    is_adjustable_load_current = (
                            has_ir and has_ii and
                            ParamPowerFlowReferenceType.Ir0 in elm.rms_model.api_obj_mapping and
                            ParamPowerFlowReferenceType.Ii0 in elm.rms_model.api_obj_mapping
                    )

                    if is_adjustable_load_current and remaining_adjustable[bus_index] > 0:
                        Ir_val = residual_r[bus_index] / remaining_adjustable[bus_index]
                        Ii_val = residual_i[bus_index] / remaining_adjustable[bus_index]
                        remaining_adjustable[bus_index] -= 1
                        residual_r[bus_index] -= Ir_val
                        residual_i[bus_index] -= Ii_val
                        Sdev = complex(
                            Vbus.real * Ir_val + Vbus.imag * Ii_val,
                            Vbus.imag * Ir_val - Vbus.real * Ii_val
                        )

                    elif (elm.device_type == DeviceType.GeneratorDevice
                          and elm.bus.is_slack
                          and remaining_slack_gen[bus_index] > 0):

                        Ir_val = residual_r[bus_index] / remaining_slack_gen[bus_index]
                        Ii_val = residual_i[bus_index] / remaining_slack_gen[bus_index]
                        remaining_slack_gen[bus_index] -= 1
                        residual_r[bus_index] -= Ir_val
                        residual_i[bus_index] -= Ii_val
                        Sdev = complex(
                            Vbus.real * Ir_val + Vbus.imag * Ii_val,
                            Vbus.imag * Ir_val - Vbus.real * Ii_val
                        )
                    else:
                        Sdev = injection_init_data[elm.idtag]

                    Ir_val, Ii_val = _s_to_i(Sdev, Vbus)
                    if VarPowerFlowReferenceType.Ir in elm.rms_model.external_mapping:
                        self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Ir, Ir_val)
                    if VarPowerFlowReferenceType.Ii in elm.rms_model.external_mapping:
                        self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Ii, Ii_val)
                    if VarPowerFlowReferenceType.P in elm.rms_model.external_mapping:
                        self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.P, Sdev.real)
                    if VarPowerFlowReferenceType.Q in elm.rms_model.external_mapping:
                        self.set_init_guess(elm.rms_model, VarPowerFlowReferenceType.Q, Sdev.imag)

                k = bus_dict[elm.bus]
                assembled_power = assemble_rms_mapped_power_references(
                    model=elm.rms_model,
                    active_power_balance=P,
                    active_power_balance_used=P_used,
                    reactive_power_balance=Q,
                    reactive_power_balance_used=Q_used,
                    bus_index=k,
                    bus_is_dc=elm.bus.is_dc,
                )
                if not assembled_power:
                    if VarPowerFlowReferenceType.Ir in elm.rms_model.external_mapping:
                        setIr(Ir, Ir_used, k, elm.rms_model.E(VarPowerFlowReferenceType.Ir))
                    else:
                        pass
                    if VarPowerFlowReferenceType.Ii in elm.rms_model.external_mapping:
                        setIi(Ii, Ii_used, k, elm.rms_model.E(VarPowerFlowReferenceType.Ii))
                    else:
                        pass
                else:
                    pass

                initialization_method: RmsInitializationMethod = _select_rms_initialization_method(
                    configured_method=self.options.initialization_method, mdl=elm.rms_model,
                    init_guess=self.init_guess, uid2idx_vars=self._uid2idx_vars)
                if initialization_method in (RmsInitializationMethod.Explicit, RmsInitializationMethod.ConsistentNewton):
                    diff_init_guess = self._run_explicit_initialization(mdl=elm.rms_model, derivative_guess=diff_init_guess)

                elif initialization_method == RmsInitializationMethod.PseudoTransient:
                    self.init_guess = init_pseudo_transient(
                        mdl=elm.rms_model,
                        sys_vars=self.sys_vars,
                        variable_parameters=self._variable_parameters,
                        event_parameters_eqs=self._event_parameters_eqs,
                        constant_parameters=self._constant_parameters,
                        init_guess=self.init_guess,
                        uid2idx_vars=self._uid2idx_vars,
                        uid2idx_params=self._uid2idx_params,
                        uid2idx_event_params=self._uid2idx_event_params,
                        compiler_names_dict=self._compiler_names_dict,
                        alias_names_dict=self._alias_names_dict,
                        VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                        TIME_NAME=self.TIME_NAME,
                        VARS_NAME=self.VARS_NAME,
                        DIFF_NAME=self.DIFF_NAME,
                        CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
                        dtau0=1e0,
                        max_iter=1000,
                        tol=1e-6
                    )
                else:
                    raise ValueError("Not implemented initialization method")

                self.sys_block.add(elm.rms_model)

        total_init_explicit_time += time.perf_counter() - t0
        # print(f"\nTotal time explicit initialization: {total_init_explicit_time:.6f} seconds")
        self.logger.add_info("Total time explicit initialization", value=total_init_explicit_time)
        if self.progress_signal is not None:
            self.progress_signal.emit(10)

        # add the nodal balance equations (current balance for phasor formulation)
        for i, elm in enumerate(self.grid.buses):
            mdl = block_deep_copy(elm.rms_model, grid.var_factory)
            if len(mdl.algebraic_eqs) == 0:
                if elm.is_dc:
                    # DC buses have one voltage coordinate, so their physical
                    # terminal-power contract produces one active-power balance.
                    if Q_used[i]:
                        raise ValueError("Reactive-power balance found on a DC bus")
                    else:
                        if P_used[i]:
                            self._algebraic_eqs.append(P[i])
                        else:
                            self.logger.add_error("Isolated bus", value=i)
                else:
                    # Convert device terminal powers before emitting the two
                    # real-valued Kirchhoff current equations of an AC bus.
                    convert_rms_ac_power_balance_to_current_balance(
                        bus_index=i,
                        voltage_real=elm.rms_model.E(VarPowerFlowReferenceType.Vr),
                        voltage_imaginary=elm.rms_model.E(VarPowerFlowReferenceType.Vi),
                        active_power_balance=P,
                        active_power_balance_used=P_used,
                        reactive_power_balance=Q,
                        reactive_power_balance_used=Q_used,
                        real_current_balance=Ir,
                        real_current_balance_used=Ir_used,
                        imaginary_current_balance=Ii,
                        imaginary_current_balance_used=Ii_used,
                    )
                    if not Ir_used[i] and not Ii_used[i]:
                        self.logger.add_error("Isolated bus", value=i)
                    else:
                        # Phasor AC buses own real and imaginary KCL residuals.
                        self._algebraic_eqs.append(Ir[i])
                        self._algebraic_eqs.append(Ii[i])
            else:
                pass

        # self._variable_parameters: List[Var] = list()
        # self._event_parameters_eqs: List[Expr | Const] = list()
        # self._constant_parameters: List[Var] = list()
        # self._parameters_values: List[Const] = list()

        # for b in self.sys_block.get_all_blocks():
        #
        #     for param, eq in b.event_dict.items():
        #         self._variable_parameters.append(param)
        #         self._event_parameters_eqs.append(eq)
        #     for param, constant in b.parameters.items():
        #         self._constant_parameters.append(param)
        #         self._parameters_values.append(constant)

        ##################### To be removed when order is preserved in the first part #############################
        self._state_algeb_vars = list(self.sys_vars.values())

        self._n_state = len(self._state_vars)
        self._n_alg = len(self._algebraic_vars)
        self._n_algebraic = len(self._algebraic_eqs)

        # self._compiler_names_dict: Dict[int, str] = dict()
        # self._alias_names_dict: Dict[int, str] = dict()
        self._uid2idx_vars: Dict[int, int] = dict()
        # self._uid2idx_event_params: Dict[int, int] = dict()
        # self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_diff: Dict[int, int] = dict()
        self._uid2idx_t: Dict[int, int] = dict()

        #We put algebraic_vars that are actually states first
        self._algebraic_vars.sort(key=lambda obj: obj.diff_var is None)
        diff_vars_from_states    = [var.diff_var for var in self._state_vars]
        for i, var in enumerate(diff_vars_from_states):
            state_var = self._state_vars[i]
            if var is None:
                diff_vars_from_states[i] = self.grid.var_factory.add_diff_var(name = 'aux', base_var=state_var)
        diff_vars_from_algebraic = [var.diff_var for var in self._algebraic_vars if var.diff_var is not None]
        self._diff_vars = diff_vars_from_states + diff_vars_from_algebraic

        i = 0
        for v in self._state_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        for v in self._algebraic_vars:
            self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{i}]"
            self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{i}"
            self._uid2idx_vars[v.uid] = i
            i += 1

        # for j, ep in enumerate(self._constant_parameters):
        #     self._compiler_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}[{j}]"
        #     self._alias_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}_{j}"
        #     self._uid2idx_params[ep.uid] = j
        #
        # for k, ep in enumerate(self._variable_parameters):
        #     self._compiler_names_dict[ep.uid] = f"{self.VARIABLE_PARAMS_NAME}[{k}]"
        #     self._alias_names_dict[ep.uid] = f"{self.VARIABLE_PARAMS_NAME}_{k}"
        #     self._uid2idx_event_params[ep.uid] = k

        for k, ep in enumerate(self._diff_vars):
            self._compiler_names_dict[ep.uid] = f"{self.DIFF_NAME}[{k}]"
            self._alias_names_dict[ep.uid] = f"{self.DIFF_NAME}_{k}"
            self._uid2idx_diff[ep.uid] = k

        self._compiler_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._alias_names_dict[self._glob_time.uid] = self.TIME_NAME
        self._uid2idx_t[self._glob_time.uid] = 0

        for it, eq in enumerate(self._event_parameters_eqs):
            if isinstance(eq, Const) and eq.value is None:
                raise Exception(f' Event parameter {self._variable_parameters[it]} has None Value')


        # Store a copy of the original event parameters equations for later use with set_events_group
        self._event_parameters_eqs0 = self._event_parameters_eqs.copy()
        self._continuous_runtime_events: dict[int, list[RmsEvent]] = dict()
        self._configure_event_parameters(self.grid.rms_events)

        # --------------------------------------------------------------------------------------------------------------
        # Compile RHS and Jacobian using JIT Compiler adaptation
        # --------------------------------------------------------------------------------------------------------------
        timings = dict()
        print("Compiling RMS using JIT Native Compiler...")

        t0 = _tic()
        rms_compiler = RMSCompiler(
            variables=self._state_algeb_vars,
            diff_vars=self._diff_vars,
            v_params=self._variable_parameters,
            c_params=self._constant_parameters,
            compiler_names_dict=self._compiler_names_dict
        )
        timings["Compiler Setup"] = _toc(t0)

        t0 = _tic()
        self._derivative_fn = rms_compiler.compile_derivative_fn(self._uid2idx_vars)
        timings["SymbolicDerivative"] = _toc(t0)

        t0 = _tic()
        self._event_params_fn = rms_compiler.compile_event_params_fn(
            eqs=self._event_parameters_eqs,
            alias_names_dict=self._alias_names_dict,
            EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
            TIME_NAME=self.TIME_NAME,
        )
        timings["Event parameters"] = _toc(t0)

        t0 = _tic()
        self._rhs_algeb_fn = rms_compiler.compile_rhs(self._algebraic_eqs, "rhs_algeb")
        timings["RHS algebraic"] = _toc(t0)

        if len(self._state_eqs) != 0:
            t0 = _tic()
            self._rhs_state_fn = rms_compiler.compile_rhs(self._state_eqs, "rhs_state")
            timings["RHS state"] = _toc(t0)

            t0 = _tic()
            self._j11_fn = rms_compiler.compile_sparse_jacobian(self._state_eqs, self._state_vars, "j11")
            timings["J11 (dF/dx)"] = _toc(t0)

            t0 = _tic()
            self._j12_fn = rms_compiler.compile_sparse_jacobian(self._state_eqs, self._algebraic_vars, "j12")
            timings["J12 (dF/dy)"] = _toc(t0)

            t0 = _tic()
            self._j21_fn = rms_compiler.compile_sparse_jacobian(self._algebraic_eqs, self._state_vars, "j21")
            timings["J21 (dG/dx)"] = _toc(t0)

            t0 = _tic()
            self._j22_fn = rms_compiler.compile_sparse_jacobian(self._algebraic_eqs, self._algebraic_vars, "j22")
            timings["J22 (dG/dy)"] = _toc(t0)

        else:
            t0 = _tic()
            self._j22_fn = rms_compiler.compile_sparse_jacobian(self._algebraic_eqs, self._algebraic_vars, "j22")
            timings["J22 only (no states)"] = _toc(t0)

        if options.verbose > 0:
            print(f"Model compiled with {self._n_vars} variables")
            print("\nCompilation timing summary:")
            for k, v in timings.items():
                print(f"  {k:30s}: {v:8.4f} s")
            print(f"\nTotal JIT compile time: {sum(timings.values()):.4f} s")

        # Replay numeric histories at the initial time, while preserving the
        # existing two evaluations used to initialize retained Expr baselines.
        self.reset_boundary_update_state()

        self._constant_params = np.array([const.value for const in self._parameters_values])

        # Replay and its complete UID snapshot precede global consistency.
        if self.options.initialization_method in (
                RmsInitializationMethod.ConsistentNewton, RmsInitializationMethod.Auto):
            consistency_converged: bool = run_rms_consistent_initialization(problem=self, options=self.options, logger=self.logger)
            if consistency_converged:
                pass
            else:
                raise RuntimeError("RMS Auto consistent initialization did not converge")
        elif self.options.initialization_method == RmsInitializationMethod.PseudoTransient:
            # Consume the prepared snapshot; another event replay changes its provenance.
            ptc_values: np.ndarray = self.get_x0()
            ptc_derivatives: np.ndarray = self.get_dx0()
            if np.all(np.isfinite(ptc_values)) and np.all(np.isfinite(ptc_derivatives)):
                projected_values: np.ndarray
                projection_converged: bool
                projection_residual: float
                projected_values, projection_converged, projection_residual = project_initial_algebraic_state(
                    problem=self, initial_values=ptc_values, differential_values=ptc_derivatives,
                    tolerance=self.options.tolerance, max_iter=self.options.max_iter,
                )
                # Accept only the original full network rows before installing guesses.
                final_residual: np.ndarray = self.rhs_algebraic(projected_values, ptc_derivatives)
                final_residual_norm: float
                if final_residual.size > 0:
                    final_residual_norm = float(np.linalg.norm(final_residual, np.inf))
                else:
                    final_residual_norm = 0.0
                if (projection_converged and np.isfinite(projection_residual)
                        and np.all(np.isfinite(projected_values))
                        and np.isfinite(final_residual_norm)
                        and final_residual_norm <= self.options.tolerance):
                    projected_collection: List[Var]
                    projected_variable: Var
                    for projected_collection in (self.state_vars, self.algebraic_vars):
                        for projected_variable in projected_collection:
                            self.init_guess[projected_variable.uid] = float(
                                projected_values[self.uid2idx_vars[projected_variable.uid]])
                else:
                    raise RuntimeError("RMS PTC algebraic projection did not converge")
            else:
                raise RuntimeError("RMS PTC algebraic projection requires finite initial values")
        else:
            pass

        if options.verbose > 0:
            print(f"\nTotal compile time: {sum(timings.values()):.4f} s")

    def add_variables_to_compilation_dicts(self, elm: ALL_DEV_TYPES, mdl: Block) -> None:
        """Register a device's symbols and runtime parameter expressions.

        Load P/Q initial values captured before flattening are selected by UID.
        Unmapped event expressions retain their declaration, and selecting a
        runtime expression never rewrites the device's canonical Block.

        :param elm: Physical device owning the registered symbols.
        :param mdl: Assigned model whose blocks supply equations and parameters.
        :return: None; extend the problem's existing compilation containers.
        """

        block_item: Block
        for block_item in mdl.get_all_blocks():
            # i is for variables
            for v in block_item.state_vars:
                if v.uid in self._uid2idx_vars:
                    raise ValueError(f"State variable '{v.name}' (uid={v.uid}) is already registered in the system. "
                                   f"Previous device may have created a duplicate variable.")
                self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{self._n_vars}]"
                self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{self._n_vars}"
                self._uid2idx_vars[v.uid] = self._n_vars
                self._register_global_var_name(name_key=v.name + elm.name, uid=v.uid, block=block_item)
                self.add_device_var(dev=elm, var=v)
                self.sys_vars[v.uid] = v
                self._state_vars.append(v)
                self._n_vars += 1

            for v in block_item.algebraic_vars:
                if v.uid in self._uid2idx_vars:
                    raise ValueError(f"Algebraic variable '{v.name}' (uid={v.uid}) is already registered in the system. "
                                   f"Previous device may have created a duplicate variable.")
                self._compiler_names_dict[v.uid] = f"{self.VARS_NAME}[{self._n_vars}]"
                self._alias_names_dict[v.uid] = f"{self.VARS_NAME}_{self._n_vars}"
                self._uid2idx_vars[v.uid] = self._n_vars
                self._register_global_var_name(name_key=v.name + elm.name, uid=v.uid, block=block_item)
                self.add_device_var(dev=elm, var=v)
                self.sys_vars[v.uid] = v
                self._algebraic_vars.append(v)
                self._n_vars += 1

            # j is for parameters
            ep: Var
            for ep, const in block_item.parameters.items():
                if ep.uid in self._uid2idx_params:
                    raise ValueError(f"Parameter '{ep.name}' (uid={ep.uid}) is already registered in the system. "
                                   f"Previous device may have created a duplicate parameter.")
                self._compiler_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}[{self._n_params}]"
                self._alias_names_dict[ep.uid] = f"{self.CONSTANT_PARAMS_NAME}_{self._n_params}"
                self._uid2idx_params[ep.uid] = self._n_params
                self._constant_parameters.append(ep)
                self._parameters_values.append(const)
                self._n_params += 1

            # m is for variable parameters
            for ep, eq in block_item.event_dict.items():
                k = len(self._variable_parameters)
                if ep.uid in self._uid2idx_event_params:
                    raise ValueError(f"Event parameter '{ep.name}' (uid={ep.uid}) is already registered in the system. "
                                   f"Previous device may have created a duplicate event parameter.")
                self._compiler_names_dict[ep.uid] = f"{self.VARIABLE_PARAMS_NAME}[{k}]"
                self._alias_names_dict[ep.uid] = f"{self.VARIABLE_PARAMS_NAME}_{k}"
                self._uid2idx_event_params[ep.uid] = k
                self._variable_parameters.append(ep)
                # The problem owns initial event values; the original equation
                # remains available to persistence and later model inspection.
                mapped_initial_value: Const | None = get_api_parameter_initial_value_by_uid(
                    parameter=ep, problem_mapping=self._static_parameters_values_mapping)
                if mapped_initial_value is None:
                    self._event_parameters_eqs.append(eq)
                else:
                    self._event_parameters_eqs.append(mapped_initial_value)
                self._n_event_params += 1

            # l is for differential vars
            for v in block_item.diff_vars:
                if v.uid in self._uid2idx_diff:
                    raise ValueError(f"Differential variable '{v.name}' (uid={v.uid}) is already registered in the system. "
                                   f"Previous device may have created a duplicate differential variable.")
                self._compiler_names_dict[v.uid] = f"{self.DIFF_NAME}[{self._n_diff}]"
                self._alias_names_dict[v.uid] = f"{self.DIFF_NAME}_{self._n_diff}"
                self._uid2idx_diff[v.uid] = self._n_diff
                self._register_global_var_name(name_key=v.name + elm.name, uid=v.uid, block=block_item)
                self.add_device_var(dev=elm, var=v)
                self._diff_vars.append(v)
                self._n_diff += 1

            self._state_eqs.extend(block_item.state_eqs)
            self._algebraic_eqs.extend(block_item.algebraic_eqs)

        if self.progress_signal is not None:
            self.progress_signal.emit(20)

    def set_init_guess(self, mdl: Block, reference_powerflow: VarPowerFlowReferenceType, val: float):
        """
        Add values from powerflow to initial guess.
        """
        if reference_powerflow in mdl.external_mapping:
            var = mdl.external_mapping[reference_powerflow]
            self.init_guess[var.uid] = val


    def get_init_guess_info(self) -> pd.DataFrame:
        """
        Returns a df with uid, name, and initial value for the system variables.
        """
        vars_names = list()
        for key, value in self.init_guess.items():
            var_name = self.sys_vars[key].name
            vars_names.append((key, var_name, value))

        return pd.DataFrame(data=vars_names, columns=["key", "var_name", "value"])

    def get_E_matrix(self, x:Vec, dx:Vec):
        #We first find all diff_vars
        xdot = list()
        # for var in self._state_vars:
        #     if var.diff_var is None:
        #         diff_var = self.grid.var_factory.add_diff_var(name = '', base_var=var)
        #         xdot.append(diff_var)
        #     else:
        #         xdot.append(var.diff_var)
        # for var in self._diff_vars:
        #     if var not in xdot:
        #         xdot.append(var)
        all_eqs = self._state_eqs + self._algebraic_eqs
        xdot = self._diff_vars
        E_call = SymbolicJacobian(
            eqs= all_eqs,
            variables=xdot,
            compiler_names_dict=self._compiler_names_dict,
            alias_names_dict= self._alias_names_dict,
            VARS_NAME=self.VARS_NAME,
            DIFF_NAME=self.DIFF_NAME,
            EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
            PARAMS_NAME=self.CONSTANT_PARAMS_NAME,
            static=True
        )

        n_states = self.get_states_number()
        vp = self._variable_parameters_values
        cp = self._constant_params

        n_vars = self._n_vars
        E_value = sp.lil_matrix((n_vars, n_vars), dtype=np.float64)
        E_partial = E_call(x, dx, vp, cp, h=0).tocsc()


        # Map each d(eq)/d(diff_var_j) column to the column of the diff_var base
        # variable in the global [state_vars + algebraic_vars] ordering.
        for j, dvar in enumerate(xdot):
            base_var = dvar.base_var
            col_idx = self._uid2idx_vars.get(base_var.uid, None)
            if col_idx is not None:
                E_value[:, col_idx] += E_partial[:, j]
            else:
                pass
        E_value[:n_states, :n_states] -= sp.eye(n_states, dtype=E_value.dtype, format="lil")

        return E_value.tocsc()

    def get_static_state_matrix(self, x:Vec, dx:Vec):
        nx = self.get_states_number()

        if nx == 0:
            return self.get_j22(x, dx, 1e15).tocsc()

        fx = self.get_j11(x, dx, 1e10).tocsc()
        fy = self.get_j12(x, dx, 1e10).tocsc()
        gx = self.get_j21(x, dx, 1e10).tocsc()
        gy = self.get_j22(x, dx, 1e15).tocsc()
        return sp.bmat([[fx, fy], [gx, gy]], format="csc")

    def get_device_vars_dict(self) -> Dict[ALL_DEV_TYPES, List[Var]]:
        """Get dictionary of device variables."""
        return self._vars_info

    def add_device_var(self, dev: ALL_DEV_TYPES, var: Var):
        """Associate a variable with a device."""
        var_list = self._vars_info.get(dev, None)

        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            var_list.append(var)

    def get_var_idx(self, v: Var) -> int:
        """Get variable index."""
        return self._uid2idx_vars[v.uid]

    @property
    def vars_glob_name2uid(self):
        return self._vars_glob_name2uid

    def _register_global_var_name(self, name_key: str, uid: int, block: Block | None = None) -> None:
        prev_uid = self._vars_glob_name2uid.get(name_key)
        if prev_uid is None or prev_uid == uid:
            self._vars_glob_name2uid[name_key] = uid
            return

        block_tag = ""
        if block is not None:
            block_tag = f"::{block.name}#{block.uid}"

        disambiguated_key = f"{name_key}{block_tag}"

        if disambiguated_key == name_key or disambiguated_key in self._vars_glob_name2uid:
            disambiguated_key = f"{name_key} [{uid}]"

        self._vars_glob_name2uid[disambiguated_key] = uid

    @property
    def uid2idx_vars(self):
        return self._uid2idx_vars

    @property
    def algebraic_vars(self):
        return self._algebraic_vars

    @property
    def state_and_algebraic_vars(self) -> List[Var]:
        variables = list()
        for lst in [self._state_vars, self._algebraic_vars]:
            for var in lst:
                variables.append(var)

        return variables

    @property
    def state_vars(self):
        return self._state_vars

    @property
    def get_algebraic_eqs(self):
        return self._algebraic_eqs

    @property
    def get_state_eqs(self):
        return self._state_eqs

    def get_all_vars_number(self) -> int:
        return self._n_vars

    def get_diff_var_number(self) -> int:
        return len(self._diff_vars)

    def get_algebraic_var_number(self) -> int:
        return len(self._algebraic_vars)

    def get_states_number(self) -> int:
        return self._n_state

    def get_variable_parameter_number(self) -> int:
        return len(self._variable_parameters)

    def get_x0(self) -> Vec:
        """
        Helper function to build the initial vector.
        """
        x = np.zeros(len(self._state_vars) + len(self._algebraic_vars))

        for uid, val in self.init_guess.items():
            if uid in self._uid2idx_vars:
                i = self._uid2idx_vars[uid]
                x[i] = val
        return x

    def get_dx0(self) -> Vec:
        """Use the existing RMS zero-derivative initialization convention.

        :return: Derivative vector in the problem's compiled derivative order.
        """
        return np.zeros(len(self._diff_vars), dtype=np.float64)

    def get_eventparams0(self) -> Vec:
        """Reconstruct the complete snapshot recorded by the t=0 replay.

        :return: Initial event values in the compiled global event UID order.
        """
        values: Vec = np.zeros(len(self._variable_parameters), dtype=np.float64)
        parameter: Var
        for parameter in self._variable_parameters:
            values[self._uid2idx_event_params[parameter.uid]] = self.event_params_init_dict[parameter.uid]
        return values

    def get_parameters_values(self) -> List[Const]:
        """Expose constants in their established compiled array order.

        :return: Problem-owned ordered constant expressions.
        """
        return self._parameters_values

    def get_compiler_names_dict(self) -> Dict[int, str]:
        """Expose the assembled UID bindings to the reduced initializer.

        :return: Problem-owned compiler array bindings by UID.
        """
        return self._compiler_names_dict

    def get_alias_names_dict(self) -> Dict[int, str]:
        """Expose existing expression aliases to the reduced initializer.

        :return: Problem-owned readable compiler aliases by UID.
        """
        return self._alias_names_dict

    @property
    def state_eqs(self) -> List[Expr]:
        """Expose ordered state equations for missing-state consistency.

        :return: Problem-owned state residual expressions.
        """
        return self._state_eqs

    @property
    def algebraic_eqs(self) -> List[Expr]:
        """Expose all device and nodal algebraic rows exactly once.

        :return: Complete assembled algebraic residual expressions.
        """
        return self._algebraic_eqs

    @property
    def variable_parameters(self) -> List[Var]:
        """Expose event identities in their numerical array order.

        :return: Problem-owned ordered variable parameters.
        """
        return self._variable_parameters

    @property
    def event_parameters_eqs(self) -> List[Expr | Const]:
        """Expose runtime event equations with the existing selection applied.

        :return: Problem-owned selected runtime parameter expressions.
        """
        return self._event_parameters_eqs

    @property
    def event_parameters_eqs0(self) -> List[Expr | Const]:
        """Expose original problem-local baselines before event selection.

        :return: Problem-owned baseline parameter expressions.
        """
        return self._event_parameters_eqs0

    @property
    def uid2idx_event_params(self) -> Dict[int, int]:
        """Expose the numerical ordering shared by replay and initialization.

        :return: Problem-owned event parameter indices by UID.
        """
        return self._uid2idx_event_params

    def get_next_forced_event_time(
        self,
        t_prev: float,
        t_target: float,
    ) -> float | None:
        """Return the earliest imported FMI ME time event in one interval.

        :param t_prev: Previous accepted RMS time.
        :param t_target: Candidate RMS target time.
        :return: Earliest FMI event in ``(t_prev, t_target]`` or ``None``.
        """

        return get_next_rms_fmu_me_event_time(
            problem=self,
            t_prev=t_prev,
            t_target=t_target,
        )

    def _run_explicit_initialization(
            self, mdl: Block, derivative_guess: Dict[int, float | int | complex | None],
    ) -> Dict[int, float | int | complex | None]:
        """Seed one phasor model through the shared symbolic initializer.

        :param mdl: Model whose explicit initialization equations are evaluated.
        :param derivative_guess: Derivative values accumulated from earlier models.
        :return: Updated derivative values in their existing UID ordering.
        """
        sys_diff_vars: Dict[int, Var] = {
            diff_var.uid: diff_var for diff_var in self._diff_vars
        }
        rms_compiler_init: RMSCompiler = RMSCompiler(
            variables=list(self.sys_vars.values()),
            diff_vars=list(sys_diff_vars.values()),
            v_params=self._variable_parameters,
            c_params=self._constant_parameters,
            compiler_names_dict=self._compiler_names_dict,
        )
        self.init_guess, derivative_guess = init_explicit_common(
            mdl=mdl,
            sys_vars=self.sys_vars,
            sys_diff_vars=sys_diff_vars,
            variable_parameters=self._variable_parameters,
            event_parameters_eqs=self._event_parameters_eqs,
            constant_parameters=self._constant_parameters,
            init_guess=self.init_guess,
            event_param_init_dict=self.event_params_init_dict,
            diff_init_guess=derivative_guess,
            uid2idx_vars=self._uid2idx_vars,
            uid2idx_diff=self._uid2idx_diff,
            uid2idx_params=self._uid2idx_params,
            uid2idx_event_params=self._uid2idx_event_params,
            params_array=self._parameters_values,
            compile_single_equation=build_rms_single_equation_compiler(
                rms_compiler=rms_compiler_init,
            ),
            verbose=bool(self.options.verbose > 0),
        )

        return derivative_guess

    def _configure_event_parameters(self, events: list[RmsEvent]) -> None:
        """Prepare selected events using the established RMS transition owners.

        Eligibility uses the problem-local baseline after initialization, never
        a previously evaluated runtime value or canonical source syntax. Only
        real numeric Const baselines gain Ramp interpolation. Retained Expr
        baselines keep legacy piecewise dependence with an explicit warning.

        :param events: Source event references in their stored selection order.
        :return: None; rebuild equations and the numeric multi-event lookup.
        """
        # Reconfiguration must discard the previous group's replay history.
        self._event_parameters_eqs = self._event_parameters_eqs0.copy()
        self._continuous_runtime_events.clear()
        parameter_count: int = len(self._variable_parameters)
        event_counts: np.ndarray = np.zeros(parameter_count, dtype=np.int64)
        event: RmsEvent
        for event in events:
            event_counts[self._uid2idx_event_params[event.parameter.uid]] += 1
        # Count first so grouping never grows per-target containers. These
        # temporary arrays retain references/positions only, not model copies.
        count: np.int64
        event_positions: list[np.ndarray] = list(
            np.empty(int(count), dtype=np.int64) for count in event_counts)
        offsets: np.ndarray = np.zeros(parameter_count, dtype=np.int64)
        source_events: ObjVec = np.asarray(events, dtype=object)
        position: int
        parameter_index: int
        for position, event in enumerate(events):
            parameter_index = self._uid2idx_event_params[event.parameter.uid]
            event_positions[parameter_index][offsets[parameter_index]] = position
            offsets[parameter_index] += 1
        positions: np.ndarray
        for parameter_index, positions in enumerate(event_positions):
            event_count: int = len(positions)
            if event_count > 0:
                baseline: Expr | Const = self._event_parameters_eqs0[parameter_index]
                times: np.ndarray = np.empty(event_count, dtype=np.float64)
                ends: np.ndarray = np.empty(event_count, dtype=np.float64)
                values: np.ndarray = np.empty(event_count, dtype=np.float64)
                has_ramp: bool = False
                event_index: int
                for event_index, position in enumerate(positions):
                    event = events[int(position)]
                    times[event_index] = event.time
                    ends[event_index] = event.time if event.end_time is None else event.end_time
                    values[event_index] = event.value
                    if event.transition_type == DynamicEventTransitionType.Ramp:
                        has_ramp = True
                    else:
                        pass
                eligible: bool = isinstance(baseline, Const) and isinstance(baseline.value, (int, float))
                if has_ramp and eligible:
                    if event_count == 1:
                        self._event_parameters_eqs[parameter_index] = _build_runtime_expression_from_single_rms_event(
                            time_var=self._glob_time, base_expression=baseline,
                            event_item=events[int(positions[0])])
                    else:
                        # Lexsort is stable for equal keys; use the scalar owner's
                        # start/end order without changing source event ordering.
                        order: np.ndarray = np.lexsort((ends, times))
                        self._continuous_runtime_events[parameter_index] = source_events[positions[order]].tolist()
                else:
                    if has_ramp:
                        self.logger.add_warning(
                            "RMS Ramp with a nonconstant or non-real baseline retains legacy Step behavior.",
                            device=self._variable_parameters[parameter_index].name,
                            expected_value="Resolved real numeric Const baseline for Ramp interpolation")
                    else:
                        pass
                    # Step-only and ineligible histories keep the legacy stored
                    # order and strict symbolic boundary, including dependencies.
                    self._event_parameters_eqs[parameter_index] = piecewise(
                        time_var=self._glob_time, t_events=times,
                        new_values=values, default_value=baseline)
            else:
                pass

    def update_variable_params(self,
                               t: float,
                               x_snapshot: Vec | None = None,
                               scheduled_t: float | None = None) -> None:
        """Evaluate symbolic parameters, then replay numeric mixed histories.

        :param t: Continuous simulation time used for all Ramp evaluations.
        :param x_snapshot: Existing interface state snapshot, unused by this owner.
        :param scheduled_t: Existing scheduled boundary time, unused for continuous ramps.
        :return: None; update the problem-owned runtime parameter vector.
        """
        # Mixed-history equations remain their original Const, so compilation
        # restores the numeric baseline before every procedural replay.
        self._variable_parameters_values[:self._n_event_params] = self._event_params_fn(self._variable_parameters_values, t)
        parameter_index: int
        events: list[RmsEvent]
        for parameter_index, events in self._continuous_runtime_events.items():
            self._variable_parameters_values[parameter_index] = _evaluate_rms_runtime_parameter_value_from_events(
                base_value=float(self._variable_parameters_values[parameter_index]),
                event_list=events, t_curr=t)

    def reset_boundary_update_state(self, t0: float = 0.0) -> None:
        """Reinitialize symbolic dependence and numeric replay at the requested time.

        :param t0: Simulation time, including an interior Ramp time on restart.
        :return: None; replace runtime values using the selected original baselines.
        """
        # Preserve the established two evaluations for dependent expressions;
        # the same path also applies procedural histories on initialization.
        self._variable_parameters_values = np.ones(self.get_variable_parameter_number())
        self.update_variable_params(float(t0))
        self.update_variable_params(float(t0))
        # Preserve the complete startup snapshot, including retained Expr
        # baselines and events before zero, without modifying source models.
        if t0 == 0.0:
            parameter: Var
            for parameter in self._variable_parameters:
                self.event_params_init_dict[parameter.uid] = float(
                    self._variable_parameters_values[self._uid2idx_event_params[parameter.uid]])
        else:
            pass

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """Store runtime event parameters for the current Newton step."""
        self._variable_parameters_values[:] = params[:len(self._variable_parameters)]


    def initialize_fmu_cs_devices(self, x_snapshot: Vec, t: float = 0.0) -> None:
        """
        Initialize imported FMU Co-Simulation devices before the RMS time loop starts.

        :param x_snapshot: Initial accepted state vector.
        :param t: Initial simulation time.
        :return: None.
        """
        if len(self._fmu_cs_adapters) > 0:
            initialize_rms_fmu_cs_devices(problem=self, x_snapshot=x_snapshot, time_value=t)
        else:
            self._fmu_cs_initialized = True

    def advance_fmu_cs_devices(self, t: float, x_snapshot: Vec, h: float) -> bool:
        """
        Advance imported FMU Co-Simulation devices for one RMS communication step.

        :param t: Current simulation time.
        :param x_snapshot: Current accepted state vector.
        :param h: RMS communication step.
        :return: Whether at least one registered CS adapter advanced.
        """

        co_simulation_advanced: bool = False
        if len(self._fmu_cs_adapters) > 0:
            co_simulation_advanced = advance_rms_fmu_cs_devices(
                problem=self,
                time_value=t,
                x_snapshot=x_snapshot,
                step_size=h,
            )
        else:
            pass
        return co_simulation_advanced

    def close_fmu_cs_devices(self) -> None:
        """
        Release imported FMU Co-Simulation devices after the RMS simulation ends.

        :return: None.
        """
        if len(self._fmu_cs_adapters) > 0:
            close_rms_fmu_cs_devices(self)

    def initialize_fmu_me_devices(self, x_snapshot: Vec, t: float = 0.0) -> None:
        """
        Initialize imported FMU Model Exchange devices before the RMS time loop starts.

        :param x_snapshot: Initial accepted state vector.
        :param t: Initial simulation time.
        :return: None.
        """
        if len(self._fmu_me_adapters) > 0:
            initialize_rms_fmu_me_devices(problem=self, x_snapshot=x_snapshot, time_value=t)
        else:
            self._fmu_me_initialized = True

    def advance_fmu_me_devices(self, t: float, x_snapshot: Vec, h: float) -> None:
        """
        Advance imported FMU Model Exchange devices for one RMS communication step.

        :param t: Current simulation time.
        :param x_snapshot: Current accepted state vector.
        :param h: RMS communication step.
        :return: None.
        """
        if len(self._fmu_me_adapters) > 0:
            advance_rms_fmu_me_devices(problem=self, time_value=t, x_snapshot=x_snapshot, step_size=h)

    def resolve_fmu_me_devices(self, accepted: bool) -> float | None:
        """Resolve all prepared FMI ME candidates after one RMS step.

        :param accepted: Whether the RMS numerical step converged.
        :return: Earlier state-event retry time, or ``None``.
        """

        if len(self._fmu_me_adapters) > 0:
            return resolve_rms_fmu_me_devices(
                problem=self,
                accepted=accepted,
            )
        else:
            return None

    def prepare_fmu_me_state_event_retry(self) -> float | None:
        """Localize an ME state event before any CS device advances.

        :return: Global shortened target time, or ``None``.
        """

        if len(self._fmu_me_adapters) > 0:
            return _prepare_rms_fmu_me_state_event_retry(
                problem=self,
                state_event_time_tolerance=self.options.fmi_state_event_time_tolerance,
                state_event_max_iterations=self.options.fmi_state_event_max_iterations,
            )
        else:
            return None

    def close_fmu_me_devices(self) -> None:
        """
        Release imported FMU Model Exchange devices after the RMS simulation ends.

        :return: None.
        """
        if len(self._fmu_me_adapters) > 0:
            close_rms_fmu_me_devices(self)

    def get_dx(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:
        return self._derivative_fn(x, xn, dx, h)

    def rhs_state(self, x: Vec, dx: Vec) -> Vec:
        return self._rhs_state_fn(x, dx,
                                  self._variable_parameters_values,
                                  self._constant_params)

    def rhs_algebraic(self, x: Vec, dx: Vec) -> Vec:
        return self._rhs_algeb_fn(x, dx,
                                  self._variable_parameters_values,
                                  self._constant_params)

    def get_j11(self, x: Vec, dx: Vec, h: float):
        return self._j11_fn(x, dx,
                           self._variable_parameters_values,
                           self._constant_params,
                           h)

    def get_j12(self, x: Vec, dx: Vec, h: float):
        return self._j12_fn(x, dx,
                           self._variable_parameters_values,
                           self._constant_params,
                           h)

    def get_j21(self, x: Vec, dx: Vec, h: float):
        return self._j21_fn(x, dx,
                           self._variable_parameters_values,
                           self._constant_params,
                           h)

    def get_j22(self, x: Vec, dx: Vec, h: float):
        return self._j22_fn(x, dx,
                           self._variable_parameters_values,
                           self._constant_params,
                           h)

    def get_dt_value(self):
        return self.options.time_step

    def set_events_group(self, rms_events_group: RmsEventsGroup) -> None:
        """
        Set the events group to use for this simulation.
        This filters events by group and recompiles the event parameters function.

        :param rms_events_group: The RmsEventsGroup to use
        :return: None; recompile the selection and restore its initial runtime values.
        """
        # Retain the existing concrete-group policy; A05 is a separate case.
        # A failed new group cannot retain an earlier ready certificate.
        self._is_initialized: bool = False
        rms_evts: list[RmsEvent] = [evt for evt in self.grid.rms_events if evt.group.idtag == rms_events_group.idtag]
        self._configure_event_parameters(rms_evts)

        # Recompile the event parameters function
        rms_compiler: RMSCompiler = RMSCompiler(
            variables=self._state_algeb_vars,
            diff_vars=self._diff_vars,
            v_params=self._variable_parameters,
            c_params=self._constant_parameters,
            compiler_names_dict=self._compiler_names_dict
        )
        self._event_params_fn = rms_compiler.compile_event_params_fn(
            eqs=self._event_parameters_eqs,
            alias_names_dict=self._alias_names_dict,
            EVENT_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
            TIME_NAME=self.TIME_NAME,
        )

        # Constructor, group changes and restarts share identical runtime replay.
        self.reset_boundary_update_state()

        # A selected PTC group can change the network operating point. Close
        # its compiled algebraic rows against this exact prepared snapshot.
        if self.options.initialization_method in (
                RmsInitializationMethod.ConsistentNewton, RmsInitializationMethod.Auto):
            consistency_converged: bool = run_rms_consistent_initialization(problem=self, options=self.options, logger=self.logger)
            if consistency_converged:
                pass
            else:
                raise RuntimeError("RMS Auto consistent initialization did not converge")
        elif self.options.initialization_method == RmsInitializationMethod.PseudoTransient:
            # Consume the prepared snapshot; another event replay changes its provenance.
            ptc_values: np.ndarray = self.get_x0()
            ptc_derivatives: np.ndarray = self.get_dx0()
            if np.all(np.isfinite(ptc_values)) and np.all(np.isfinite(ptc_derivatives)):
                projected_values: np.ndarray
                projection_converged: bool
                projection_residual: float
                projected_values, projection_converged, projection_residual = project_initial_algebraic_state(
                    problem=self, initial_values=ptc_values, differential_values=ptc_derivatives,
                    tolerance=self.options.tolerance, max_iter=self.options.max_iter,
                )
                # Accept only the original full network rows before installing guesses.
                final_residual: np.ndarray = self.rhs_algebraic(projected_values, ptc_derivatives)
                final_residual_norm: float
                if final_residual.size > 0:
                    final_residual_norm = float(np.linalg.norm(final_residual, np.inf))
                else:
                    final_residual_norm = 0.0
                if (projection_converged and np.isfinite(projection_residual)
                        and np.all(np.isfinite(projected_values))
                        and np.isfinite(final_residual_norm)
                        and final_residual_norm <= self.options.tolerance):
                    projected_collection: List[Var]
                    projected_variable: Var
                    for projected_collection in (self.state_vars, self.algebraic_vars):
                        for projected_variable in projected_collection:
                            self.init_guess[projected_variable.uid] = float(
                                projected_values[self.uid2idx_vars[projected_variable.uid]])
                else:
                    raise RuntimeError("RMS PTC algebraic projection did not converge")
            else:
                raise RuntimeError("RMS PTC algebraic projection requires finite initial values")
        else:
            pass

        # Ready applies only after this group's finite original-g certificate.
        self.set_initialize_flag()
