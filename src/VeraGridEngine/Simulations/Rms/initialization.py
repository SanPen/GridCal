# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple, Any, Sequence, Callable, Dict
import math
import numba as nb
import numpy as np
from scipy.optimize import newton_krylov
from VeraGridEngine.Utils.Symbolic import BlockSolver
from VeraGridEngine.Utils.Symbolic.symbolic import _emit, _emit_one
from VeraGridEngine.Utils.Symbolic.block import Block, Expr
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.enumerations import DynamicVarType
from VeraGridEngine.basic_structures import Logger, ObjVec, BoolVec


def _compile_equation(eqs: Sequence[Expr],
                      uid2sym_vars: Dict[int, str],
                      add_doc_string: bool = True) -> Callable[[np.ndarray], np.ndarray]:
    """
    Compile the array of expressions to a function that returns an array of values for those expressions
    :param eqs: Iterable of expressions (Expr)
    :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
    :param uid2sym_params:
    :param add_doc_string: add the docstring?
    :return: Function pointer that returns an array
    """
    # TODO: Why is there a second compile equation thing here?
    # Build source
    src = f"def _f(vars):\n"
    src += f"    out = np.zeros({len(eqs)})\n"
    src += "\n".join([f"    out[{i}] = {_emit_one(e, uid2sym_vars)}" for i, e in enumerate(eqs)]) + "\n"
    src += f"    return out"
    ns: Dict[str, Any] = {"math": math, "np": np}
    exec(src, ns)
    fn = nb.njit(ns["_f"], fastmath=True)

    if add_doc_string:
        fn.__doc__ = "def _f(vars)"
    return fn


def compose_system_block(grid: MultiCircuit,
                          power_flow_results: PowerFlowResults) -> Tuple[Block, Dict[Tuple[int, str], float]]:
    """
    Compose all RMS models
    :param grid:
    :param power_flow_results:
    :return: System block and initial guess dictionary
    """
    # already computed grid power flow
    res = power_flow_results

    Sf = res.Sf / grid.Sbase
    St = res.St / grid.Sbase

    # create the system block
    sys_block = Block(children=[], in_vars=[])

    # initialize containers
    init_guess: Dict[Tuple[int, str], float] = {}
    sys_vars: list[Tuple[int, str]] = []
    seen_vars: set[Tuple[int, str]] = set()

    uid2sym_vars: Dict[int, str] = {}
    uid2idx_vars: Dict[int, int] = {}
    array_index = 0

    # buses
    for i, elm in enumerate(grid.buses):

        # get model and model vars
        mdl = elm.rms_model.model
        mdl_vars = mdl.state_vars + mdl.algebraic_vars

        # fill system variables list
        for var in mdl_vars:
            key = (var.uid, var.name)
            if key not in seen_vars:
                sys_vars.append(key)
                seen_vars.add(key)

        # fill uid2sym and uid2idx dicts
        for v in mdl_vars:
            uid2sym_vars[v.uid] = f"vars[{array_index}]"
            uid2idx_vars[v.uid] = array_index
            array_index += 1

        # fill init_guess
        # TODO: initialization from power injections of PFlows results needs
        #  to be addressed when multiple devices are connected to the same bus.
        # (Shunt Load, for the benchmark case, two generators,...)
        init_guess[(mdl.external_mapping[DynamicVarType.Vm].uid,
                    mdl.external_mapping[DynamicVarType.Vm].name)] = float(np.abs(res.voltage[i]))
        init_guess[(mdl.external_mapping[DynamicVarType.Va].uid,
                    mdl.external_mapping[DynamicVarType.Va].name)] = float(np.angle(res.voltage[i]))
        init_guess[(mdl.external_mapping[DynamicVarType.P].uid,
                    mdl.external_mapping[DynamicVarType.P].name)] = float(np.real(res.Sbus[i] / grid.Sbase))
        init_guess[(mdl.external_mapping[DynamicVarType.Q].uid,
                    mdl.external_mapping[DynamicVarType.Q].name)] = float(np.imag(res.Sbus[i] / grid.Sbase))

        sys_block.children.append(mdl)

    # branches
    for i, elm in enumerate(grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True)):
        mdl = elm.rms_model.model
        mdl_vars = mdl.state_vars + mdl.algebraic_vars

        # fill system variables list
        for var in mdl_vars:
            key = (var.uid, var.name)
            if key not in seen_vars:
                sys_vars.append(key)
                seen_vars.add(key)

        # fill uid2sym and uid2idx dicts
        for v in mdl_vars:
            uid2sym_vars[v.uid] = f"vars[{array_index}]"
            uid2idx_vars[v.uid] = array_index
            array_index += 1

        # fill init_guess
        init_guess[(mdl.external_mapping[DynamicVarType.Pf].uid,
                    mdl.external_mapping[DynamicVarType.Pf].name)] = Sf[i].real
        init_guess[(mdl.external_mapping[DynamicVarType.Qf].uid,
                    mdl.external_mapping[DynamicVarType.Qf].name)] = Sf[i].imag
        init_guess[(mdl.external_mapping[DynamicVarType.Pt].uid,
                    mdl.external_mapping[DynamicVarType.Pt].name)] = St[i].real
        init_guess[(mdl.external_mapping[DynamicVarType.Qt].uid,
                    mdl.external_mapping[DynamicVarType.Qt].name)] = St[i].imag

        sys_block.children.append(mdl)

    # injections

    # already known variables:

    for elm in grid.get_injection_devices_iter():
        bus_rms_mdl = elm.bus.rms_model.model
        mdl = elm.rms_model.model


        init_guess[(mdl.external_mapping[DynamicVarType.P].uid, mdl.external_mapping[DynamicVarType.P].name)] = init_guess[(bus_rms_mdl.external_mapping[DynamicVarType.P].uid, bus_rms_mdl.external_mapping[DynamicVarType.P].name)]
        init_guess[(mdl.external_mapping[DynamicVarType.Q].uid, mdl.external_mapping[DynamicVarType.Q].name)] = init_guess[(bus_rms_mdl.external_mapping[DynamicVarType.Q].uid, bus_rms_mdl.external_mapping[DynamicVarType.Q].name)]

        mdl_vars = mdl.state_vars + mdl.algebraic_vars

        for var in mdl_vars:
            key = (var.uid, var.name)
            if key not in seen_vars:
                sys_vars.append(key)
                seen_vars.add(key)

        for v in mdl_vars:
            if v.uid not in uid2sym_vars:
                uid2sym_vars[v.uid] = f"vars[{array_index}]"
                uid2idx_vars[v.uid] = array_index
                array_index += 1

        # initialize array for model variables
        x = np.zeros(len(sys_vars))

        # assign initial guesses for known variables
        # TODO: isn't there a way of not keep iterating over the same variables?
        for uid, name in sys_vars:
            key = (uid, name)
            if key in init_guess:
                x[uid2idx_vars[uid]] = init_guess[key]

        # compute and assign missing init_vars

        for var in mdl.init_vars:
            key = (var.uid, var.name)
            if key in init_guess:
                x[uid2idx_vars[var.uid]] = init_guess[key]
            else:
                eq = mdl.init_eqs[var]
                eq_fn = _compile_equation([eq], uid2sym_vars)
                init_val = float(eq_fn(x))
                init_guess[key] = init_val
                x[uid2idx_vars[var.uid]] = init_val
        for param, value in elm.init_params.items():
            eq = mdl.init_params_eq[param]
            eq_fn = _compile_equation([eq], uid2sym_vars)
            init_val = float(eq_fn(x))
            elm.init_params[param] = init_val


        sys_block.children.append(mdl)

    # del buses P, Q
    for i, elm in enumerate(grid.buses):
            mdl = elm.rms_model.model
            del init_guess[(mdl.external_mapping[DynamicVarType.P].uid,
                        mdl.external_mapping[DynamicVarType.P].name)]
            del init_guess[(mdl.external_mapping[DynamicVarType.Q].uid,
                        mdl.external_mapping[DynamicVarType.Q].name)]

    return sys_block, init_guess


def setP(P: ObjVec, P_used: BoolVec, k: int, val: object):
    if not P_used[k]:
        P[k] = val
        P_used[k] = 1
    else:
        P[k] += val


def setQ(Q: ObjVec, Q_used: BoolVec, k: int, val: object):
    if not Q_used[k]:
        Q[k] = val
        Q_used[k] = 1
    else:
        Q[k] += val


def initialize_rms(grid: MultiCircuit, power_flow_results, logger: Logger = Logger()):
    """
    Initialize all RMS models
    """
    # already computed grid power flow

    bus_dict = dict()

    # balance equation arrays
    n = len(grid.buses)
    P: ObjVec = np.zeros(n, dtype=object)
    Q: ObjVec = np.zeros(n, dtype=object)
    P_used = np.zeros(n, dtype=int)
    Q_used = np.zeros(n, dtype=int)

    # initialize buses
    for i, elm in enumerate(grid.buses):
        elm.initialize_rms()
        bus_dict[elm] = i

    # initialize branches
    for elm in grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
        elm.initialize_rms()
        mdl = elm.rms_model.model
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]
        # add variable to conservation equations of the bus to which the element is connected
        setP(P, P_used, f, -mdl.E(DynamicVarType.Pf))
        setP(P, P_used, t, -mdl.E(DynamicVarType.Pt))
        setQ(Q, Q_used, f, -mdl.E(DynamicVarType.Qf))
        setQ(Q, Q_used, t, -mdl.E(DynamicVarType.Qt))

    # initialize injections
    for elm in grid.get_injection_devices_iter():
        elm.initialize_rms()
        mdl = elm.rms_model.model
        k = bus_dict[elm.bus]
        setP(P, P_used, k, mdl.E(DynamicVarType.P))
        setQ(Q, Q_used, k, mdl.E(DynamicVarType.Q))

    # add the nodal balance equations
    for i, elm in enumerate(grid.buses):
        mdl = elm.rms_model.model
        if P_used[i] == 0 and Q_used[i] == 0:
            logger.add_error("Isolated bus", value=i)
        else:
            mdl.algebraic_eqs.append(P[i])
            mdl.algebraic_eqs.append(Q[i])

    return compose_system_block(grid, power_flow_results)
