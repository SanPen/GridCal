# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import flipflop, bool_and, bool_or
import VeraGridEngine.Utils.Symbolic.symbolic as sym
import numpy as np


def get_pvd1_rms_template(vfactory: VarFactory, name: str = "PVD1 RMS template") -> RmsModelTemplate:
    """
    WECC/ANDES PVD1-inspired RMS PV model.

    This implementation focuses on the core current-command behavior needed for
    RMS studies in VeraGrid:
    - P/Q references to current commands
    - Q(V) droop outside [v0, v1]
    - active/reactive current hard limits with P/Q priority
    - simplified V/f tripping multipliers
    - first-order lag on output currents (tip, tiq)
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice

    vm = vfactory.add_var(f"Vm", reference=VarPowerFlowReferenceType.Vm)
    va = vfactory.add_var(f"Va", reference=VarPowerFlowReferenceType.Va)
    inputs = [vm, va]

    p = vfactory.add_var("P_pvd1")
    q = vfactory.add_var("Q_pvd1")
    ip_cmd = vfactory.add_var("Ip_cmd")
    iq_cmd = vfactory.add_var("Iq_cmd")
    ip_max = vfactory.add_var("Ip_max")
    iq_max = vfactory.add_var("Iq_max")
    p_sum = vfactory.add_var("P_sum")
    q_sum = vfactory.add_var("Q_sum")
    q_droop = vfactory.add_var("Q_droop")
    f_trip = vfactory.add_var("F_trip")
    v_trip = vfactory.add_var("V_trip")

    ipout = vfactory.add_var("Ipout_y")
    iqout = vfactory.add_var("Iqout_y")

    pref0 = vfactory.add_var("pref0")
    qref0 = vfactory.add_var("qref0")
    pext0 = vfactory.add_var("pext0")
    qmx = vfactory.add_var("qmx")
    qmn = vfactory.add_var("qmn")
    pmx = vfactory.add_var("pmx")
    v0 = vfactory.add_var("v0")
    v1 = vfactory.add_var("v1")
    dqdv = vfactory.add_var("dqdv")
    ialim = vfactory.add_var("ialim")
    pqflag = vfactory.add_var("pqflag")
    tip = vfactory.add_var("tip")
    tiq = vfactory.add_var("tiq")
    recflag = vfactory.add_var("recflag")

    ft0 = vfactory.add_var("ft0")
    ft1 = vfactory.add_var("ft1")
    ft2 = vfactory.add_var("ft2")
    ft3 = vfactory.add_var("ft3")
    f_hz = vfactory.add_var("f_hz")

    vt0 = vfactory.add_var("vt0")
    vt1 = vfactory.add_var("vt1")
    vt2 = vfactory.add_var("vt2")
    vt3 = vfactory.add_var("vt3")

    one = vfactory.add_const(1.0)
    zero = vfactory.add_const(0.0)
    eps_v = vfactory.add_const(0.01)
    eps_i = vfactory.add_const(1e-8)

    vm_eff = sym.max(vm, eps_v)
    under_v_db = sym.heaviside(v0 - vm)
    over_v_db = sym.heaviside(vm - v1)

    q_droop_expr = dqdv * (vm - v0) * under_v_db + dqdv * (vm - v1) * over_v_db

    p_sum_expr = sym.hard_sat(pref0 + pext0, -pmx, pmx)
    q_sum_expr = sym.hard_sat(qref0 + q_droop_expr, qmn, qmx)

    ip_unlimited = p_sum_expr / vm_eff
    iq_unlimited = q_sum_expr / vm_eff

    ip_cap_q = sym.sqrt(sym.max(ialim ** 2 - iq_unlimited ** 2, eps_i))
    iq_cap_p = sym.sqrt(sym.max(ialim ** 2 - ip_unlimited ** 2, eps_i))

    ip_max_expr = pqflag * ialim + (one - pqflag) * ip_cap_q
    iq_max_expr = (one - pqflag) * ialim + pqflag * iq_cap_p

    f_low = sym.hard_sat((f_hz - ft0) / (ft1 - ft0), zero, one)
    f_high = sym.hard_sat((ft3 - f_hz) / (ft3 - ft2), zero, one)
    f_trip_expr = f_low * f_high

    v_low = sym.hard_sat((vm - vt0) / (vt1 - vt0), zero, one)
    v_high = sym.hard_sat((vt3 - vm) / (vt3 - vt2), zero, one)
    v_trip_expr = v_low * v_high

    trip_gain = one - recflag + recflag * f_trip_expr * v_trip_expr

    ip_cmd_expr = sym.hard_sat(ip_unlimited, -ip_max_expr, ip_max_expr) * trip_gain
    iq_cmd_expr = sym.hard_sat(iq_unlimited, -iq_max_expr, iq_max_expr) * trip_gain

    block = Block(
        algebraic_eqs=[
            p - vm * ipout,
            q - vm * iqout,
            q_droop - q_droop_expr,
            p_sum - p_sum_expr,
            q_sum - q_sum_expr,
            ip_max - ip_max_expr,
            iq_max - iq_max_expr,
            f_trip - f_trip_expr,
            v_trip - v_trip_expr,
            ip_cmd - ip_cmd_expr,
            iq_cmd - iq_cmd_expr,
        ],
        algebraic_vars=[p, q, q_droop, p_sum, q_sum, ip_max, iq_max, f_trip, v_trip, ip_cmd, iq_cmd],
        state_eqs=[
            (ip_cmd - ipout) / tip,
            (iq_cmd - iqout) / tiq,
        ],
        state_vars=[ipout, iqout],
        in_vars=inputs,
        init_eqs={
            q_droop: q_droop_expr,
            p_sum: p_sum_expr,
            q_sum: q_sum_expr,
            ip_max: ip_max_expr,
            iq_max: iq_max_expr,
            f_trip: f_trip_expr,
            v_trip: v_trip_expr,
            ip_cmd: ip_cmd_expr,
            iq_cmd: iq_cmd_expr,
            ipout: ip_cmd_expr,
            iqout: iq_cmd_expr,
        },
        event_dict={
            pref0: p,
            qref0: q,
            pext0: vfactory.add_const(0.0),
            qmx: vfactory.add_const(1.0),
            qmn: vfactory.add_const(-1.0),
            pmx: vfactory.add_const(9.999),
            v0: vfactory.add_const(0.8),
            v1: vfactory.add_const(1.1),
            dqdv: vfactory.add_const(-1.0),
            ialim: vfactory.add_const(1.3),
            pqflag: vfactory.add_const(1.0),
            tip: vfactory.add_const(0.02),
            tiq: vfactory.add_const(0.02),
            recflag: vfactory.add_const(1.0),
            ft0: vfactory.add_const(59.5),
            ft1: vfactory.add_const(59.7),
            ft2: vfactory.add_const(60.3),
            ft3: vfactory.add_const(60.5),
            vt0: vfactory.add_const(0.88),
            vt1: vfactory.add_const(0.9),
            vt2: vfactory.add_const(1.1),
            vt3: vfactory.add_const(1.2),
            f_hz: vfactory.add_const(60.0),
        },
    )

    block.name = name
    block.external_mapping = {
        VarPowerFlowReferenceType.Vm: vm,
        VarPowerFlowReferenceType.Va: va,
        VarPowerFlowReferenceType.P: p,
        VarPowerFlowReferenceType.Q: q,
    }
    block.out_vars = [p, q, ipout, iqout, q_droop, p_sum, q_sum, f_trip, v_trip]

    templ.block = block
    templ.comment = 'Generator PV PVD1 RMS model'
    return templ


def get_pvd1_complete_rms_template(vfactory: VarFactory, name: str = "PVD1 complete RMS template") -> RmsModelTemplate:
    """
    More complete WECC/ANDES-like PVD1 RMS model.

    Compared to ``get_pvd1_rms_template``, this variant adds:

    - frequency deadband and post-deadband active-power support (fdbd, ddn),
    - explicit pref/pext internal summation channels,
    - optional active-power limiting switch (plim),
    - recovery multipliers with separate frequency/voltage enable flags.

    Notes:

    - ``fn`` is a static parameter mapped to the grid nominal frequency.
      ``f_hz`` is the local frequency measured by the PLL.
    - True latching tripping behavior (frflag/vrflag in the original ANDES formulation)
      is approximated by continuous enable factors; it does not implement memory latching.
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice

    # Local import avoids a package import cycle at module load time.


    vm = vfactory.add_var(f"Vm", reference=VarPowerFlowReferenceType.Vm)
    va = vfactory.add_var(f"Va", reference=VarPowerFlowReferenceType.Va)
    inputs = [vm, va]

    p = vfactory.add_var("P_pvd1")
    q = vfactory.add_var("Q_pvd1")

    ip_cmd = vfactory.add_var("Ip_cmd")
    iq_cmd = vfactory.add_var("Iq_cmd")
    ip_max = vfactory.add_var("Ip_max")
    iq_max = vfactory.add_var("Iq_max")
    ip_unlimited_var = vfactory.add_var("Ipul")
    iq_unlimited_var = vfactory.add_var("Iqul")

    pext = vfactory.add_var("Pext")
    pref = vfactory.add_var("Pref")
    p_sum = vfactory.add_var("P_sum")
    qref = vfactory.add_var("Qref")
    q_sum = vfactory.add_var("Q_sum")
    vcomp = vfactory.add_var("Vcomp")
    q_droop = vfactory.add_var("Q_droop")

    f_dev = vfactory.add_var("Fdev")
    db_y = vfactory.add_var("DB_y")
    f_trip = vfactory.add_var("F_trip")
    v_trip = vfactory.add_var("V_trip")
    f_trip_latched = vfactory.add_var("F_trip_latched")
    v_trip_latched = vfactory.add_var("V_trip_latched")

    ipout = vfactory.add_var("Ipout_y")
    iqout = vfactory.add_var("Iqout_y")

    pref0 = vfactory.add_var("pref0")
    qref0 = vfactory.add_var("qref0")
    pext0 = vfactory.add_var("pext0")

    qmx = vfactory.add_var("qmx")
    qmn = vfactory.add_var("qmn")
    pmx = vfactory.add_var("pmx")
    xc = vfactory.add_var("xc")
    v0 = vfactory.add_var("v0")
    v1 = vfactory.add_var("v1")
    dqdv = vfactory.add_var("dqdv")
    ialim = vfactory.add_var("ialim")
    pqflag = vfactory.add_var("pqflag")
    tip = vfactory.add_var("tip")
    tiq = vfactory.add_var("tiq")

    recflag = vfactory.add_var("recflag")
    frflag = vfactory.add_var("frflag")
    vrflag = vfactory.add_var("vrflag")
    plim = vfactory.add_var("plim")

    fdbd = vfactory.add_var("fdbd")
    ddn = vfactory.add_var("ddn")
    fn = vfactory.add_var("fn")
    f_hz = vfactory.add_var("f_hz")
    pll_err = vfactory.add_var("PLL_err")
    omega_pu = vfactory.add_var("omega_pu")
    theta_pll = vfactory.add_var("theta_pll")
    pll_int = vfactory.add_var("pll_int")
    kp_pll = vfactory.add_var("kp_pll")
    ki_pll = vfactory.add_var("ki_pll")

    ft0 = vfactory.add_var("ft0")
    ft1 = vfactory.add_var("ft1")
    ft2 = vfactory.add_var("ft2")
    ft3 = vfactory.add_var("ft3")

    vt0 = vfactory.add_var("vt0")
    vt1 = vfactory.add_var("vt1")
    vt2 = vfactory.add_var("vt2")
    vt3 = vfactory.add_var("vt3")

    one = vfactory.add_const(1.0)
    zero = vfactory.add_const(0.0)
    two_pi = vfactory.add_const(2.0 * np.pi)
    eps_v = vfactory.add_const(0.01)
    eps_i = vfactory.add_const(1e-8)

    vm_eff = sym.max(vm, eps_v)

    # Coupling-reactance compensated local voltage magnitude (ANDES-like Vcomp).
    # With xc=0, this collapses to Vm.
    vcomp_expr = sym.sqrt((vm - xc * iqout) ** 2 + (xc * ipout) ** 2 + eps_i)

    under_v_db = sym.heaviside(v0 - vm)
    over_v_db = sym.heaviside(vm - v1)
    under_v_db = sym.heaviside(v0 - vcomp)
    over_v_db = sym.heaviside(vcomp - v1)
    q_droop_expr = dqdv * (vcomp - v0) * under_v_db + dqdv * (vcomp - v1) * over_v_db

    # Local PLL-based bus-frequency measurement approximation.
    pll_err_expr = vm * sym.sin(va - theta_pll)
    omega_pu_expr = one + kp_pll * pll_err + ki_pll * pll_int
    f_hz_expr = fn * omega_pu_expr

    f_dev_expr = fn - f_hz
    fdbd_abs = sym.abs(fdbd)
    db_y_expr = ddn * (
        (f_dev_expr - fdbd_abs) * sym.heaviside(f_dev_expr - fdbd_abs)
        + (f_dev_expr + fdbd_abs) * sym.heaviside(-f_dev_expr - fdbd_abs)
    )

    pext_expr = pext0
    pref_expr = pref0

    p_raw = pref_expr + pext_expr + db_y_expr
    p_limited = sym.hard_sat(p_raw, zero, pmx)
    p_sum_expr = plim * p_limited + (one - plim) * p_raw

    qref_expr = qref0
    q_raw = qref_expr + q_droop_expr
    q_sum_expr = sym.hard_sat(q_raw, qmn, qmx)

    ip_unlimited = p_sum_expr / vm_eff
    iq_unlimited = q_sum_expr / vm_eff

    ip_cap_q = sym.sqrt(sym.max(ialim ** 2 - iq_unlimited ** 2, eps_i))
    iq_cap_p = sym.sqrt(sym.max(ialim ** 2 - ip_unlimited ** 2, eps_i))

    ip_max_expr = pqflag * ialim + (one - pqflag) * ip_cap_q
    iq_max_expr = (one - pqflag) * ialim + pqflag * iq_cap_p

    f_low = sym.hard_sat((f_hz - ft0) / (ft1 - ft0), zero, one)
    f_high = sym.hard_sat((ft3 - f_hz) / (ft3 - ft2), zero, one)
    f_trip_expr = f_low * f_high

    v_low = sym.hard_sat((vm - vt0) / (vt1 - vt0), zero, one)
    v_high = sym.hard_sat((vt3 - vm) / (vt3 - vt2), zero, one)
    v_trip_expr = v_low * v_high

    # Latching trip logic with procedural runtime flip-flops
    # latch state: 1 -> tripped, 0 -> healthy
    f_trip_set = bool_or(f_hz <= ft0, f_hz >= ft3)
    f_trip_reset = bool_and(f_hz >= ft1, f_hz <= ft2)
    v_trip_set = bool_or(vm <= vt0, vm >= vt3)
    v_trip_reset = bool_and(vm >= vt1, vm <= vt2)

    f_trip_latched_gain = one - f_trip_latched
    v_trip_latched_gain = one - v_trip_latched

    # frflag/vrflag: 1 -> self-resetting continuous curve, 0 -> latching mode.
    f_trip_gain = frflag * f_trip_expr + (one - frflag) * f_trip_latched_gain
    v_trip_gain = vrflag * v_trip_expr + (one - vrflag) * v_trip_latched_gain
    trip_gain = (one - recflag) + recflag * f_trip_gain * v_trip_gain

    ip_clamped = sym.hard_sat(ip_unlimited, -ip_max_expr, ip_max_expr)
    iq_clamped = sym.hard_sat(iq_unlimited, -iq_max_expr, iq_max_expr)

    ip_cmd_expr = ip_clamped * trip_gain
    iq_cmd_expr = iq_clamped * trip_gain

    block = Block(
        algebraic_eqs=[
            p - vm * ipout,
            q - vm * iqout,
            pext - pext_expr,
            pref - pref_expr,
            qref - qref_expr,
            vcomp - vcomp_expr,
            pll_err - pll_err_expr,
            omega_pu - omega_pu_expr,
            f_hz - f_hz_expr,
            f_dev - f_dev_expr,
            db_y - db_y_expr,
            q_droop - q_droop_expr,
            p_sum - p_sum_expr,
            q_sum - q_sum_expr,
            ip_unlimited_var - ip_unlimited,
            iq_unlimited_var - iq_unlimited,
            ip_max - ip_max_expr,
            iq_max - iq_max_expr,
            f_trip - f_trip_expr,
            v_trip - v_trip_expr,
            ip_cmd - ip_cmd_expr,
            iq_cmd - iq_cmd_expr,
        ],
        algebraic_vars=[
            p,
            q,
            pext,
            pref,
            qref,
            vcomp,
            pll_err,
            omega_pu,
            f_hz,
            f_dev,
            db_y,
            q_droop,
            p_sum,
            q_sum,
            ip_unlimited_var,
            iq_unlimited_var,
            ip_max,
            iq_max,
            f_trip,
            v_trip,
            ip_cmd,
            iq_cmd,
        ],
        state_eqs=[
            (ip_cmd - ipout) / tip,
            (iq_cmd - iqout) / tiq,
            pll_err,
            two_pi * fn * (omega_pu - one),
        ],
        state_vars=[ipout, iqout, pll_int, theta_pll],
        in_vars=inputs,
        init_eqs={
            pll_int: zero,
            theta_pll: va,
            pext: pext_expr,
            pref: pref_expr,
            qref: qref_expr,
            vcomp: vm,
            pll_err: pll_err_expr,
            omega_pu: one,
            f_hz: fn,
            f_dev: f_dev_expr,
            db_y: db_y_expr,
            q_droop: q_droop_expr,
            p_sum: p_sum_expr,
            q_sum: q_sum_expr,
            ip_unlimited_var: ip_unlimited,
            iq_unlimited_var: iq_unlimited,
            ip_max: ip_max_expr,
            iq_max: iq_max_expr,
            f_trip: f_trip_expr,
            v_trip: v_trip_expr,
            ip_cmd: ip_cmd_expr,
            iq_cmd: iq_cmd_expr,
            ipout: ip_cmd_expr,
            iqout: iq_cmd_expr,
        },
        event_dict={
            pref0: p,
            qref0: q,
            pext0: vfactory.add_const(0.0),
            qmx: vfactory.add_const(0.33),
            qmn: vfactory.add_const(-0.33),
            pmx: vfactory.add_const(9999.0),
            xc: vfactory.add_const(0.0),
            v0: vfactory.add_const(0.8),
            v1: vfactory.add_const(1.1),
            dqdv: vfactory.add_const(-1.0),
            ialim: vfactory.add_const(1.3),
            pqflag: vfactory.add_const(1.0),
            tip: vfactory.add_const(0.02),
            tiq: vfactory.add_const(0.02),
            recflag: vfactory.add_const(1.0),
            frflag: vfactory.add_const(1.0),
            vrflag: vfactory.add_const(1.0),
            plim: vfactory.add_const(1.0),
            fdbd: vfactory.add_const(-0.017),
            ddn: vfactory.add_const(0.0),
            kp_pll: vfactory.add_const(5.0),
            ki_pll: vfactory.add_const(50.0),
            ft0: vfactory.add_const(59.5),
            ft1: vfactory.add_const(59.7),
            ft2: vfactory.add_const(60.3),
            ft3: vfactory.add_const(60.5),
            vt0: vfactory.add_const(0.88),
            vt1: vfactory.add_const(0.9),
            vt2: vfactory.add_const(1.1),
            vt3: vfactory.add_const(1.2),
        },
        mode_dict={
            f_trip_latched: zero,
            v_trip_latched: zero,
        },
        procedural_logic=[
            flipflop(boolset=f_trip_set, boolreset=f_trip_reset, output=f_trip_latched, name="f_trip_latch"),
            flipflop(boolset=v_trip_set, boolreset=v_trip_reset, output=v_trip_latched, name="v_trip_latch"),
        ],
        api_obj_mapping={ParamPowerFlowReferenceType.freq: fn},
        parameters={fn: vfactory.add_const(60.0)},
    )

    block.name = name
    block.external_mapping = {
        VarPowerFlowReferenceType.Vm: vm,
        VarPowerFlowReferenceType.Va: va,
        VarPowerFlowReferenceType.P: p,
        VarPowerFlowReferenceType.Q: q,
    }
    block.out_vars = [
        p,
        q,
        ipout,
        iqout,
        db_y,
        vcomp,
        q_droop,
        p_sum,
        q_sum,
        f_hz,
        omega_pu,
        f_trip,
        v_trip,
        f_trip_latched,
        v_trip_latched,
        ip_cmd,
        iq_cmd,
    ]

    templ.block = block
    templ.comment = 'Generator complete PV PVD1 RMS model'
    return templ


def get_pvd1_dc_mppt_rms_template(vfactory: VarFactory, name: str = "PVD1 DC-MPPT RMS template") -> RmsModelTemplate:
    """
    PVD1 extension with DC-side power availability and MPPT lag.

    Added DC-side channels:
    - Pavail = Prated * (G / Gref) * (1 + kT * (Tcell - Tref)), limited to [0, Prated]
    - MPPT first-order tracking: dPmppt/dt = (Pavail - Pmppt) / Tmppt
    - Active-power command is limited by dynamic MPPT ceiling instead of a fixed pmx

    This model keeps the same AC current-command framework as PVD1 while making
    irradiance and cell temperature directly affect active-power availability.
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice

    vm = vfactory.add_var(f"Vm", reference=VarPowerFlowReferenceType.Vm)
    va = vfactory.add_var(f"Va", reference=VarPowerFlowReferenceType.Va)
    inputs = [vm, va]

    p = vfactory.add_var("P_pvd1", reference=VarPowerFlowReferenceType.P)
    q = vfactory.add_var("Q_pvd1", reference=VarPowerFlowReferenceType.Q)
    ip_cmd = vfactory.add_var("Ip_cmd")
    iq_cmd = vfactory.add_var("Iq_cmd")
    ip_max = vfactory.add_var("Ip_max")
    iq_max = vfactory.add_var("Iq_max")
    p_sum = vfactory.add_var("P_sum")
    q_sum = vfactory.add_var("Q_sum")
    q_droop = vfactory.add_var("Q_droop")
    f_trip = vfactory.add_var("F_trip")
    v_trip = vfactory.add_var("V_trip")

    pavail = vfactory.add_var("Pavail")
    pmppt = vfactory.add_var("Pmppt")

    ipout = vfactory.add_var("Ipout_y")
    iqout = vfactory.add_var("Iqout_y")

    pref0 = vfactory.add_var("pref0")
    qref0 = vfactory.add_var("qref0")
    pext0 = vfactory.add_var("pext0")
    qmx = vfactory.add_var("qmx")
    qmn = vfactory.add_var("qmn")
    v0 = vfactory.add_var("v0")
    v1 = vfactory.add_var("v1")
    dqdv = vfactory.add_var("dqdv")
    ialim = vfactory.add_var("ialim")
    pqflag = vfactory.add_var("pqflag")
    tip = vfactory.add_var("tip")
    tiq = vfactory.add_var("tiq")
    recflag = vfactory.add_var("recflag")

    ft0 = vfactory.add_var("ft0")
    ft1 = vfactory.add_var("ft1")
    ft2 = vfactory.add_var("ft2")
    ft3 = vfactory.add_var("ft3")
    f_hz = vfactory.add_var("f_hz")

    vt0 = vfactory.add_var("vt0")
    vt1 = vfactory.add_var("vt1")
    vt2 = vfactory.add_var("vt2")
    vt3 = vfactory.add_var("vt3")

    prated = vfactory.add_var("Prated")
    g = vfactory.add_var("G")
    gref = vfactory.add_var("Gref")
    tcell = vfactory.add_var("Tcell")
    tref = vfactory.add_var("Tref")
    kt = vfactory.add_var("kT")
    tmppt = vfactory.add_var("Tmppt")

    one = vfactory.add_const(1.0)
    zero = vfactory.add_const(0.0)
    eps_v = vfactory.add_const(0.01)
    eps_i = vfactory.add_const(1e-8)

    vm_eff = sym.max(vm, eps_v)
    gref_eff = sym.max(gref, eps_i)
    tmppt_eff = sym.max(tmppt, eps_i)

    under_v_db = sym.heaviside(v0 - vm)
    over_v_db = sym.heaviside(vm - v1)
    q_droop_expr = dqdv * (vm - v0) * under_v_db + dqdv * (vm - v1) * over_v_db

    pavail_raw = prated * (g / gref_eff) * (one + kt * (tcell - tref))
    pavail_expr = sym.hard_sat(pavail_raw, zero, prated)

    p_sum_expr = sym.hard_sat(pref0 + pext0, zero, sym.max(pmppt, zero))
    q_sum_expr = sym.hard_sat(qref0 + q_droop_expr, qmn, qmx)

    ip_unlimited = p_sum_expr / vm_eff
    iq_unlimited = q_sum_expr / vm_eff

    ip_cap_q = sym.sqrt(sym.max(ialim ** 2 - iq_unlimited ** 2, eps_i))
    iq_cap_p = sym.sqrt(sym.max(ialim ** 2 - ip_unlimited ** 2, eps_i))

    ip_max_expr = pqflag * ialim + (one - pqflag) * ip_cap_q
    iq_max_expr = (one - pqflag) * ialim + pqflag * iq_cap_p

    f_low = sym.hard_sat((f_hz - ft0) / (ft1 - ft0), zero, one)
    f_high = sym.hard_sat((ft3 - f_hz) / (ft3 - ft2), zero, one)
    f_trip_expr = f_low * f_high

    v_low = sym.hard_sat((vm - vt0) / (vt1 - vt0), zero, one)
    v_high = sym.hard_sat((vt3 - vm) / (vt3 - vt2), zero, one)
    v_trip_expr = v_low * v_high

    trip_gain = one - recflag + recflag * f_trip_expr * v_trip_expr

    ip_cmd_expr = sym.hard_sat(ip_unlimited, -ip_max_expr, ip_max_expr) * trip_gain
    iq_cmd_expr = sym.hard_sat(iq_unlimited, -iq_max_expr, iq_max_expr) * trip_gain

    block = Block(
        algebraic_eqs=[
            p - vm * ipout,
            q - vm * iqout,
            q_droop - q_droop_expr,
            pavail - pavail_expr,
            p_sum - p_sum_expr,
            q_sum - q_sum_expr,
            ip_max - ip_max_expr,
            iq_max - iq_max_expr,
            f_trip - f_trip_expr,
            v_trip - v_trip_expr,
            ip_cmd - ip_cmd_expr,
            iq_cmd - iq_cmd_expr,
        ],
        algebraic_vars=[p, q, q_droop, pavail, p_sum, q_sum, ip_max, iq_max, f_trip, v_trip, ip_cmd, iq_cmd],
        state_eqs=[
            (ip_cmd - ipout) / tip,
            (iq_cmd - iqout) / tiq,
            (pavail - pmppt) / tmppt_eff,
        ],
        state_vars=[ipout, iqout, pmppt],
        in_vars=inputs,
        init_eqs={
            pavail: pavail_expr,
            pmppt: pavail_expr,
            q_droop: q_droop_expr,
            p_sum: p_sum_expr,
            q_sum: q_sum_expr,
            ip_max: ip_max_expr,
            iq_max: iq_max_expr,
            f_trip: f_trip_expr,
            v_trip: v_trip_expr,
            ip_cmd: ip_cmd_expr,
            iq_cmd: iq_cmd_expr,
            ipout: ip_cmd_expr,
            iqout: iq_cmd_expr,
        },
        event_dict={
            pref0: p,
            qref0: q,
            pext0: vfactory.add_const(0.0),
            qmx: vfactory.add_const(1.0),
            qmn: vfactory.add_const(-1.0),
            v0: vfactory.add_const(0.8),
            v1: vfactory.add_const(1.1),
            dqdv: vfactory.add_const(-1.0),
            ialim: vfactory.add_const(1.3),
            pqflag: vfactory.add_const(1.0),
            tip: vfactory.add_const(0.02),
            tiq: vfactory.add_const(0.02),
            recflag: vfactory.add_const(1.0),
            ft0: vfactory.add_const(59.5),
            ft1: vfactory.add_const(59.7),
            ft2: vfactory.add_const(60.3),
            ft3: vfactory.add_const(60.5),
            vt0: vfactory.add_const(0.88),
            vt1: vfactory.add_const(0.9),
            vt2: vfactory.add_const(1.1),
            vt3: vfactory.add_const(1.2),
            f_hz: vfactory.add_const(60.0),
            prated: vfactory.add_const(1.0),
            g: vfactory.add_const(1.0),
            gref: vfactory.add_const(1.0),
            tcell: vfactory.add_const(25.0),
            tref: vfactory.add_const(25.0),
            kt: vfactory.add_const(-0.004),
            tmppt: vfactory.add_const(0.2),
        },
    )

    block.name = name
    block.external_mapping = {
        VarPowerFlowReferenceType.Vm: vm,
        VarPowerFlowReferenceType.Va: va,
        VarPowerFlowReferenceType.P: p,
        VarPowerFlowReferenceType.Q: q,
    }
    block.out_vars = [p, q]

    templ.block.children.append(block)
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vm: vm,
        VarPowerFlowReferenceType.Va: va,
        VarPowerFlowReferenceType.P: p,
        VarPowerFlowReferenceType.Q: q,
    }
    templ.block.api_obj_mapping = {}
    templ.block.in_vars = inputs
    templ.block.out_vars = [p, q]

    templ.comment = 'Generator PV PVD1 DC MPPT RMS model'
    return templ


def get_pvd1_dc_link_mppt_rms_template(vfactory: VarFactory, name: str = "PVD1 DC-link MPPT RMS template") -> RmsModelTemplate:
    """
    PVD1 extension with explicit PV-side and DC-link dynamics.

    Main additions over ``get_pvd1_dc_mppt_rms_template``:
    - PV-side voltage target ``Vmp(G,T)`` and current ``Imp(G,T)`` channels
    - Boost duty-cycle loop to track ``Vpv -> Vmp``
    - Explicit DC-link dynamic state ``Vdc`` with power balance
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.GeneratorDevice

    vm = vfactory.add_var(f"Vm", reference=VarPowerFlowReferenceType.Vm)
    va = vfactory.add_var(f"Va", reference=VarPowerFlowReferenceType.Va)
    inputs = [vm, va]

    p = vfactory.add_var("P_pvd1")
    q = vfactory.add_var("Q_pvd1")
    ip_cmd = vfactory.add_var("Ip_cmd")
    iq_cmd = vfactory.add_var("Iq_cmd")
    ip_max = vfactory.add_var("Ip_max")
    iq_max = vfactory.add_var("Iq_max")
    p_sum = vfactory.add_var("P_sum")
    q_sum = vfactory.add_var("Q_sum")
    q_droop = vfactory.add_var("Q_droop")
    f_trip = vfactory.add_var("F_trip")
    v_trip = vfactory.add_var("V_trip")

    ipout = vfactory.add_var("Ipout_y")
    iqout = vfactory.add_var("Iqout_y")

    pref0 = vfactory.add_var("pref0")
    qref0 = vfactory.add_var("qref0")
    pext0 = vfactory.add_var("pext0")
    qmx = vfactory.add_var("qmx")
    qmn = vfactory.add_var("qmn")
    v0 = vfactory.add_var("v0")
    v1 = vfactory.add_var("v1")
    dqdv = vfactory.add_var("dqdv")
    ialim = vfactory.add_var("ialim")
    pqflag = vfactory.add_var("pqflag")
    tip = vfactory.add_var("tip")
    tiq = vfactory.add_var("tiq")
    recflag = vfactory.add_var("recflag")

    ft0 = vfactory.add_var("ft0")
    ft1 = vfactory.add_var("ft1")
    ft2 = vfactory.add_var("ft2")
    ft3 = vfactory.add_var("ft3")
    f_hz = vfactory.add_var("f_hz")

    vt0 = vfactory.add_var("vt0")
    vt1 = vfactory.add_var("vt1")
    vt2 = vfactory.add_var("vt2")
    vt3 = vfactory.add_var("vt3")

    prated = vfactory.add_var("Prated")
    g = vfactory.add_var("G")
    gref = vfactory.add_var("Gref")
    tcell = vfactory.add_var("Tcell")
    tref = vfactory.add_var("Tref")
    kvmp = vfactory.add_var("kVmp")
    kimpp = vfactory.add_var("kImp")

    vmp_ref = vfactory.add_var("Vmp_ref")
    imp_ref = vfactory.add_var("Imp_ref")
    vmp = vfactory.add_var("Vmp")
    imp = vfactory.add_var("Imp")
    pavail = vfactory.add_var("Pavail")
    psrc = vfactory.add_var("Psrc")
    pinv = vfactory.add_var("Pinv")

    vpv = vfactory.add_var("Vpv")
    vdc = vfactory.add_var("Vdc")
    duty = vfactory.add_var("duty")
    xi_mppt = vfactory.add_var("xi_mppt")

    d0 = vfactory.add_var("d0")
    dmin = vfactory.add_var("dmin")
    dmax = vfactory.add_var("dmax")
    kp_mppt = vfactory.add_var("Kp_mppt")
    ki_mppt = vfactory.add_var("Ki_mppt")
    tduty = vfactory.add_var("Tduty")
    cdc = vfactory.add_var("Cdc")
    eta_inv = vfactory.add_var("eta_inv")
    vdc_min = vfactory.add_var("Vdc_min")
    ksrc = vfactory.add_var("Ksrc")
    vdc0 = vfactory.add_var("Vdc0")

    one = vfactory.add_const(1.0)
    zero = vfactory.add_const(0.0)
    eps_v = vfactory.add_const(0.01)
    eps_i = vfactory.add_const(1e-8)

    vm_eff = sym.max(vm, eps_v)
    gref_eff = sym.max(gref, eps_i)
    vdc_eff = sym.max(vdc, eps_v)
    cdc_eff = sym.max(cdc, eps_i)
    tduty_eff = sym.max(tduty, eps_i)
    eta_inv_eff = sym.max(eta_inv, eps_i)

    under_v_db = sym.heaviside(v0 - vm)
    over_v_db = sym.heaviside(vm - v1)
    q_droop_expr = dqdv * (vm - v0) * under_v_db + dqdv * (vm - v1) * over_v_db

    vmp_expr = sym.max(vmp_ref * (one + kvmp * (tcell - tref)), eps_v)
    imp_expr = sym.max(imp_ref * (g / gref_eff) * (one + kimpp * (tcell - tref)), zero)
    pavail_expr = sym.hard_sat(vmp_expr * imp_expr, zero, prated)

    vpv_ref = vmp_expr
    mppt_err = vpv_ref - vpv
    duty_ref = sym.hard_sat(d0 + kp_mppt * mppt_err + ki_mppt * xi_mppt, dmin, dmax)

    # Ideal boost relation (average model): Vpv = (1 - d) * Vdc
    vpv_expr = sym.max((one - duty) * vdc, eps_v)

    # Source power drops when operating away from MPP voltage
    psrc_raw = pavail - ksrc * (vpv - vmp_expr) ** 2
    psrc_expr = sym.hard_sat(psrc_raw, zero, pavail)

    # AC-side extracted active power seen from DC side
    pinv_expr = p / eta_inv_eff

    # Dynamic active command is limited by source/DC availability
    vdc_gain = sym.hard_sat((vdc - vdc_min) / sym.max(one - vdc_min, eps_i), zero, one)
    p_sum_expr = sym.hard_sat(pref0 + pext0, zero, psrc * vdc_gain)
    q_sum_expr = sym.hard_sat(qref0 + q_droop_expr, qmn, qmx)

    ip_unlimited = p_sum_expr / vm_eff
    iq_unlimited = q_sum_expr / vm_eff

    ip_cap_q = sym.sqrt(sym.max(ialim ** 2 - iq_unlimited ** 2, eps_i))
    iq_cap_p = sym.sqrt(sym.max(ialim ** 2 - ip_unlimited ** 2, eps_i))

    ip_max_expr = pqflag * ialim + (one - pqflag) * ip_cap_q
    iq_max_expr = (one - pqflag) * ialim + pqflag * iq_cap_p

    f_low = sym.hard_sat((f_hz - ft0) / (ft1 - ft0), zero, one)
    f_high = sym.hard_sat((ft3 - f_hz) / (ft3 - ft2), zero, one)
    f_trip_expr = f_low * f_high

    v_low = sym.hard_sat((vm - vt0) / (vt1 - vt0), zero, one)
    v_high = sym.hard_sat((vt3 - vm) / (vt3 - vt2), zero, one)
    v_trip_expr = v_low * v_high

    trip_gain = one - recflag + recflag * f_trip_expr * v_trip_expr
    ip_cmd_expr = sym.hard_sat(ip_unlimited, -ip_max_expr, ip_max_expr) * trip_gain
    iq_cmd_expr = sym.hard_sat(iq_unlimited, -iq_max_expr, iq_max_expr) * trip_gain

    block = Block(
        algebraic_eqs=[
            p - vm * ipout,
            q - vm * iqout,
            q_droop - q_droop_expr,
            vmp - vmp_expr,
            imp - imp_expr,
            pavail - pavail_expr,
            vpv - vpv_expr,
            psrc - psrc_expr,
            pinv - pinv_expr,
            p_sum - p_sum_expr,
            q_sum - q_sum_expr,
            ip_max - ip_max_expr,
            iq_max - iq_max_expr,
            f_trip - f_trip_expr,
            v_trip - v_trip_expr,
            ip_cmd - ip_cmd_expr,
            iq_cmd - iq_cmd_expr,
        ],
        algebraic_vars=[
            p,
            q,
            q_droop,
            vmp,
            imp,
            pavail,
            vpv,
            psrc,
            pinv,
            p_sum,
            q_sum,
            ip_max,
            iq_max,
            f_trip,
            v_trip,
            ip_cmd,
            iq_cmd,
        ],
        state_eqs=[
            (ip_cmd - ipout) / tip,
            (iq_cmd - iqout) / tiq,
            mppt_err,
            (duty_ref - duty) / tduty_eff,
            (psrc - pinv) / (cdc_eff * vdc_eff),
        ],
        state_vars=[ipout, iqout, xi_mppt, duty, vdc],
        in_vars=inputs,
        init_eqs={
            vdc: vdc0,
            duty: d0,
            xi_mppt: zero,
            q_droop: q_droop_expr,
            vmp: vmp_expr,
            imp: imp_expr,
            pavail: pavail_expr,
            vpv: vpv_expr,
            psrc: psrc_expr,
            pinv: pinv_expr,
            p_sum: p_sum_expr,
            q_sum: q_sum_expr,
            ip_max: ip_max_expr,
            iq_max: iq_max_expr,
            f_trip: f_trip_expr,
            v_trip: v_trip_expr,
            ip_cmd: ip_cmd_expr,
            iq_cmd: iq_cmd_expr,
            ipout: ip_cmd_expr,
            iqout: iq_cmd_expr,
        },
        event_dict={
            pref0: p,
            qref0: q,
            pext0: vfactory.add_const(0.0),
            qmx: vfactory.add_const(1.0),
            qmn: vfactory.add_const(-1.0),
            v0: vfactory.add_const(0.8),
            v1: vfactory.add_const(1.1),
            dqdv: vfactory.add_const(-1.0),
            ialim: vfactory.add_const(1.3),
            pqflag: vfactory.add_const(1.0),
            tip: vfactory.add_const(0.02),
            tiq: vfactory.add_const(0.02),
            recflag: vfactory.add_const(1.0),
            ft0: vfactory.add_const(59.5),
            ft1: vfactory.add_const(59.7),
            ft2: vfactory.add_const(60.3),
            ft3: vfactory.add_const(60.5),
            vt0: vfactory.add_const(0.88),
            vt1: vfactory.add_const(0.9),
            vt2: vfactory.add_const(1.1),
            vt3: vfactory.add_const(1.2),
            f_hz: vfactory.add_const(60.0),
            prated: vfactory.add_const(1.0),
            g: vfactory.add_const(1.0),
            gref: vfactory.add_const(1.0),
            tcell: vfactory.add_const(25.0),
            tref: vfactory.add_const(25.0),
            kvmp: vfactory.add_const(-0.002),
            kimpp: vfactory.add_const(0.0),
            vmp_ref: vfactory.add_const(0.8),
            imp_ref: vfactory.add_const(1.0),
            d0: vfactory.add_const(0.2),
            dmin: vfactory.add_const(0.0),
            dmax: vfactory.add_const(0.95),
            kp_mppt: vfactory.add_const(0.5),
            ki_mppt: vfactory.add_const(1.0),
            tduty: vfactory.add_const(0.05),
            cdc: vfactory.add_const(20.0),
            eta_inv: vfactory.add_const(0.98),
            vdc_min: vfactory.add_const(0.6),
            ksrc: vfactory.add_const(1.0),
            vdc0: vfactory.add_const(1.0),
        },
    )

    block.name = name
    block.external_mapping = {
        VarPowerFlowReferenceType.Vm: vm,
        VarPowerFlowReferenceType.Va: va,
        VarPowerFlowReferenceType.P: p,
        VarPowerFlowReferenceType.Q: q,
    }
    block.out_vars = [p, q, ipout, iqout, p_sum, q_sum, pavail, psrc, pinv, vpv, vdc, duty, vmp, imp]

    templ.block = block
    templ.comment = 'Generator PV PVD1 DC-link MPPT RMS model'
    return templ


def get_pvd1_dc_link_bess_rms_template(vfactory: VarFactory, name: str = "PVD1 DC-link BESS RMS template") -> RmsModelTemplate:
    """
    PVD1 AC current-command framework adapted to a BESS with DC-link equivalent capacitance.

    Main adaptations from the PV DC-link template:
    - Remove PV/MPPT channels and replace them with bidirectional battery DC power control.
    - Keep AC-side current control, P/Q limiting, and V/f tripping structure.
    - Represent stored energy on DC side through equivalent capacitance ``Cdc_eq`` and ``Vdc`` dynamics.

    Sign convention:
    - ``P > 0``: discharging to AC grid.
    - ``P < 0``: charging from AC grid.
    - ``Pbat > 0``: battery injects power into the DC link.
    - ``Pbat < 0``: battery absorbs power from the DC link.
    """
    templ = RmsModelTemplate(name=name)
    templ.tpe = DeviceType.BatteryDevice

    vm = vfactory.add_var(f"Vm", reference=VarPowerFlowReferenceType.Vm)
    va = vfactory.add_var(f"Va", reference=VarPowerFlowReferenceType.Va)
    inputs = [vm, va]

    p = vfactory.add_var("P_pvd1", reference=VarPowerFlowReferenceType.P)
    q = vfactory.add_var("Q_pvd1", reference=VarPowerFlowReferenceType.Q)
    ip_cmd = vfactory.add_var("Ip_cmd")
    iq_cmd = vfactory.add_var("Iq_cmd")
    ip_max = vfactory.add_var("Ip_max")
    iq_max = vfactory.add_var("Iq_max")
    p_sum = vfactory.add_var("P_sum")
    q_sum = vfactory.add_var("Q_sum")
    q_droop = vfactory.add_var("Q_droop")
    f_trip = vfactory.add_var("F_trip")
    v_trip = vfactory.add_var("V_trip")

    ipout = vfactory.add_var("Ipout_y")
    iqout = vfactory.add_var("Iqout_y")

    pbat_cmd = vfactory.add_var("Pbat_cmd")
    pbat = vfactory.add_var("Pbat")
    pinv = vfactory.add_var("Pinv")
    p_dis_cap = vfactory.add_var("P_dis_cap")
    p_ch_cap = vfactory.add_var("P_ch_cap")
    pbat_dis_cap = vfactory.add_var("Pbat_dis_cap")
    pbat_ch_cap = vfactory.add_var("Pbat_ch_cap")
    vdc = vfactory.add_var("Vdc")

    pref0 = vfactory.add_var("pref0")
    qref0 = vfactory.add_var("qref0")
    pext0 = vfactory.add_var("pext0")
    qmx = vfactory.add_var("qmx")
    qmn = vfactory.add_var("qmn")
    v0 = vfactory.add_var("v0")
    v1 = vfactory.add_var("v1")
    dqdv = vfactory.add_var("dqdv")
    ialim = vfactory.add_var("ialim")
    pqflag = vfactory.add_var("pqflag")
    tip = vfactory.add_var("tip")
    tiq = vfactory.add_var("tiq")
    recflag = vfactory.add_var("recflag")

    ft0 = vfactory.add_var("ft0")
    ft1 = vfactory.add_var("ft1")
    ft2 = vfactory.add_var("ft2")
    ft3 = vfactory.add_var("ft3")
    f_hz = vfactory.add_var("f_hz")

    vt0 = vfactory.add_var("vt0")
    vt1 = vfactory.add_var("vt1")
    vt2 = vfactory.add_var("vt2")
    vt3 = vfactory.add_var("vt3")

    p_dis_max = vfactory.add_var("P_dis_max")
    p_ch_max = vfactory.add_var("P_ch_max")
    kvdc = vfactory.add_var("Kvdc")
    vdc_ref = vfactory.add_var("Vdc_ref")
    vdc_min = vfactory.add_var("Vdc_min")
    vdc_max = vfactory.add_var("Vdc_max")
    cdc_eq = vfactory.add_var("Cdc_eq")
    eta_inv = vfactory.add_var("eta_inv")
    vdc0 = vfactory.add_var("Vdc0")

    one = vfactory.add_const(1.0)
    zero = vfactory.add_const(0.0)
    eps_v = vfactory.add_const(0.01)
    eps_i = vfactory.add_const(1e-8)

    vm_eff = sym.max(vm, eps_v)
    vdc_eff = sym.max(vdc, eps_v)
    cdc_eq_eff = sym.max(cdc_eq, eps_i)
    eta_inv_eff = sym.max(eta_inv, eps_i)
    vdc_span = sym.max(vdc_max - vdc_min, eps_i)

    under_v_db = sym.heaviside(v0 - vm)
    over_v_db = sym.heaviside(vm - v1)
    q_droop_expr = dqdv * (vm - v0) * under_v_db + dqdv * (vm - v1) * over_v_db

    p_dis_cap_expr = p_dis_max * sym.hard_sat((vdc - vdc_min) / vdc_span, zero, one)
    p_ch_cap_expr = p_ch_max * sym.hard_sat((vdc_max - vdc) / vdc_span, zero, one)
    p_sum_expr = sym.hard_sat(pref0 + pext0, -p_ch_cap_expr, p_dis_cap_expr)
    q_sum_expr = sym.hard_sat(qref0 + q_droop_expr, qmn, qmx)

    ip_unlimited = p_sum_expr / vm_eff
    iq_unlimited = q_sum_expr / vm_eff

    ip_cap_q = sym.sqrt(sym.max(ialim ** 2 - iq_unlimited ** 2, eps_i))
    iq_cap_p = sym.sqrt(sym.max(ialim ** 2 - ip_unlimited ** 2, eps_i))

    ip_max_expr = pqflag * ialim + (one - pqflag) * ip_cap_q
    iq_max_expr = (one - pqflag) * ialim + pqflag * iq_cap_p

    f_low = sym.hard_sat((f_hz - ft0) / (ft1 - ft0), zero, one)
    f_high = sym.hard_sat((ft3 - f_hz) / (ft3 - ft2), zero, one)
    f_trip_expr = f_low * f_high

    v_low = sym.hard_sat((vm - vt0) / (vt1 - vt0), zero, one)
    v_high = sym.hard_sat((vt3 - vm) / (vt3 - vt2), zero, one)
    v_trip_expr = v_low * v_high

    trip_gain = one - recflag + recflag * f_trip_expr * v_trip_expr
    ip_cmd_expr = sym.hard_sat(ip_unlimited, -ip_max_expr, ip_max_expr) * trip_gain
    iq_cmd_expr = sym.hard_sat(iq_unlimited, -iq_max_expr, iq_max_expr) * trip_gain

    pbat_cmd_expr = kvdc * (vdc_ref - vdc)
    pbat_dis_cap_expr = p_dis_max * sym.hard_sat((vdc_max - vdc) / vdc_span, zero, one)
    pbat_ch_cap_expr = p_ch_max * sym.hard_sat((vdc - vdc_min) / vdc_span, zero, one)
    pbat_expr = sym.hard_sat(pbat_cmd_expr, -pbat_ch_cap_expr, pbat_dis_cap_expr)

    pinv_expr = p / eta_inv_eff

    block = Block(
        algebraic_eqs=[
            p - vm * ipout,
            q - vm * iqout,
            q_droop - q_droop_expr,
            p_dis_cap - p_dis_cap_expr,
            p_ch_cap - p_ch_cap_expr,
            p_sum - p_sum_expr,
            q_sum - q_sum_expr,
            ip_max - ip_max_expr,
            iq_max - iq_max_expr,
            f_trip - f_trip_expr,
            v_trip - v_trip_expr,
            ip_cmd - ip_cmd_expr,
            iq_cmd - iq_cmd_expr,
            pbat_cmd - pbat_cmd_expr,
            pbat_dis_cap - pbat_dis_cap_expr,
            pbat_ch_cap - pbat_ch_cap_expr,
            pbat - pbat_expr,
            pinv - pinv_expr,
        ],
        algebraic_vars=[
            p,
            q,
            q_droop,
            p_dis_cap,
            p_ch_cap,
            p_sum,
            q_sum,
            ip_max,
            iq_max,
            f_trip,
            v_trip,
            ip_cmd,
            iq_cmd,
            pbat_cmd,
            pbat_dis_cap,
            pbat_ch_cap,
            pbat,
            pinv,
        ],
        state_eqs=[
            (ip_cmd - ipout) / tip,
            (iq_cmd - iqout) / tiq,
            (pbat - pinv) / (cdc_eq_eff * vdc_eff),
        ],
        state_vars=[ipout, iqout, vdc],
        in_vars=inputs,
        init_eqs={
            vdc: vdc0,
            q_droop: q_droop_expr,
            p_dis_cap: p_dis_cap_expr,
            p_ch_cap: p_ch_cap_expr,
            p_sum: p_sum_expr,
            q_sum: q_sum_expr,
            ip_max: ip_max_expr,
            iq_max: iq_max_expr,
            f_trip: f_trip_expr,
            v_trip: v_trip_expr,
            ip_cmd: ip_cmd_expr,
            iq_cmd: iq_cmd_expr,
            pbat_cmd: pbat_cmd_expr,
            pbat_dis_cap: pbat_dis_cap_expr,
            pbat_ch_cap: pbat_ch_cap_expr,
            pbat: pbat_expr,
            pinv: pinv_expr,
            ipout: ip_cmd_expr,
            iqout: iq_cmd_expr,
        },
        event_dict={
            pref0: p,
            qref0: q,
            pext0: vfactory.add_const(0.0),
            qmx: vfactory.add_const(1.0),
            qmn: vfactory.add_const(-1.0),
            v0: vfactory.add_const(0.8),
            v1: vfactory.add_const(1.1),
            dqdv: vfactory.add_const(-1.0),
            ialim: vfactory.add_const(1.3),
            pqflag: vfactory.add_const(1.0),
            tip: vfactory.add_const(0.02),
            tiq: vfactory.add_const(0.02),
            recflag: vfactory.add_const(1.0),
            ft0: vfactory.add_const(59.5),
            ft1: vfactory.add_const(59.7),
            ft2: vfactory.add_const(60.3),
            ft3: vfactory.add_const(60.5),
            vt0: vfactory.add_const(0.88),
            vt1: vfactory.add_const(0.9),
            vt2: vfactory.add_const(1.1),
            vt3: vfactory.add_const(1.2),
            f_hz: vfactory.add_const(60.0),
            p_dis_max: vfactory.add_const(1.0),
            p_ch_max: vfactory.add_const(1.0),
            kvdc: vfactory.add_const(5.0),
            vdc_ref: vfactory.add_const(1.0),
            vdc_min: vfactory.add_const(0.85),
            vdc_max: vfactory.add_const(1.15),
            cdc_eq: vfactory.add_const(20.0),
            eta_inv: vfactory.add_const(0.98),
            vdc0: vfactory.add_const(1.0),
        },
    )

    block.name = name
    block.external_mapping = {
        VarPowerFlowReferenceType.Vm: vm,
        VarPowerFlowReferenceType.Va: va,
        VarPowerFlowReferenceType.P: p,
        VarPowerFlowReferenceType.Q: q,
    }
    block.out_vars = [
        p,
        q,
        ipout,
        iqout,
        p_sum,
        q_sum,
        p_dis_cap,
        p_ch_cap,
        pbat_cmd,
        pbat,
        pinv,
        pbat_dis_cap,
        pbat_ch_cap,
        vdc,
    ]

    templ.block = block
    templ.comment = 'Battery PV PVD1 DC-link BESS RMS model'
    return templ
