import numpy as np
from GridCal.Engine.basic_structures import Logger, SolverType, ReactivePowerControlMode, TapsControlMode
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Devices.enumerations import ConverterControlType, TransformerControlType
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions

try:
    import NewtonNative as nn
    NEWTON_AVAILBALE = True
    print('Newton Native v' + nn.get_version())

except ImportError:
    NEWTON_AVAILBALE = False
    newton_solver_dict = dict()
    newton_taps_dict = dict()
    newton_q_control_dict = dict()
    print('Newton native is not available')


def set_branch_values(nc: "nn.NativeNumericCircuit",
                      idx, name, active, f, t, rate, r, x, g, b, m, theta, vtap_f, vtap_t):
    """
    Set the the main parameters of a branch
    :param nc: NativeNumericCircuit
    :param idx: branch index
    :param name: name of the branch
    :param active: is active?
    :param f: "from" bus index
    :param t: "to" bus index
    :param rate: branch rating
    :param r: resistance (p.u.)
    :param x: reactance (p.u.)
    :param g: conductance (p.u.)
    :param b: susceptance (p.u.)
    :param m: tap module
    :param theta: tap angle
    :param vtap_f: virtual tap "from"
    :param vtap_t: virtual tap "to"
    """
    nc.set_branch_name(idx, name)
    nc.set_branch_active(idx, active)
    nc.set_branch_rates(idx, rate)

    nc.set_branch_r(idx, r)
    nc.set_branch_x(idx, x)
    nc.set_branch_g(idx, g)
    nc.set_branch_b(idx, b)
    nc.set_branch_tap_mod(idx, m)
    nc.set_branch_tap_ang(idx, theta)
    nc.set_branch_tap_f(idx, vtap_f)
    nc.set_branch_tap_t(idx, vtap_t)

    nc.set_c_branch_bus_f(idx, f, 1)
    nc.set_c_branch_bus_t(idx, t, 1)
    nc.set_branch_f(idx, f)
    nc.set_branch_t(idx, t)


def to_newton_native(circuit: MultiCircuit) -> "nn.NativeNumericCircuit":
    """
    Compile the information of a circuit and generate the pertinent power flow islands
    :param circuit: MultiCircuit instance
    :return: NativeNumericCircuit
    """

    bus_dictionary = dict()

    # Element count
    nbus = len(circuit.buses)
    nload = 0
    ngen = 0
    n_batt = 0
    nshunt = 0
    for bus in circuit.buses:
        nload += len(bus.loads)
        ngen += len(bus.controlled_generators)
        n_batt += len(bus.batteries)
        nshunt += len(bus.shunts)

    nline = len(circuit.lines)
    ndcline = len(circuit.dc_lines)
    ntr2w = len(circuit.transformers2w)
    # ntr3w = len(circuit.transformers3w)
    nvsc = len(circuit.vsc_devices)
    nhvdc = len(circuit.hvdc_lines)

    # declare the numerical circuit
    nc = nn.NativeNumericCircuit(nbus=nbus,
                                 nline=nline,
                                 ndcline=ndcline,
                                 ntr=ntr2w,  # + 3 * ntr3w,
                                 nvsc=nvsc,
                                 nhvdc=nhvdc,
                                 nload=nload,
                                 ngen=ngen,
                                 nbatt=n_batt,
                                 nshunt=nshunt,
                                 sBase=circuit.Sbase)

    # buses and it's connected elements (loads, generators, etc...)
    i_ld = 0
    i_gen = 0
    i_batt = 0
    i_sh = 0
    V0 = np.ones(nbus, dtype=complex)
    for i, bus in enumerate(circuit.buses):

        # bus parameters
        nc.set_bus_name(i, bus.name)
        nc.set_bus_active(i, bus.active)
        nc.set_bus_types(i, bus.determine_bus_type().value)

        # Add buses dictionary entry
        bus_dictionary[bus.idtag] = i

        # initialize voltage guess
        V0[i] = bus.get_voltage_guess()

        for elm in bus.loads:
            nc.set_load_name(i_ld, elm.name)
            nc.set_load_active(i_ld, elm.active)
            nc.set_load_s(i_ld, complex(elm.P, elm.Q))
            nc.set_c_bus_load(i, i_ld, 1)
            i_ld += 1

        for elm in bus.controlled_generators:
            nc.set_generator_name(i_gen, elm.name)
            nc.set_generator_active(i_gen, elm.active)
            nc.set_generator_controllable(i_gen, elm.is_controlled)
            nc.set_generator_pf(i_gen, elm.Pf)
            nc.set_generator_v(i_gen, elm.Vset)
            nc.set_generator_qmin(i_gen, elm.Qmin)
            nc.set_generator_qmax(i_gen, elm.Qmax)

            nc.set_generator_p(i_gen, elm.P)
            nc.set_generator_installed_p(i_gen, elm.Snom)

            nc.set_c_bus_gen(i, i_gen, 1)

            i_gen += 1

        for elm in bus.batteries:
            nc.set_battery_names(i_batt, elm.name)
            nc.set_battery_p(i_batt, elm.P)
            nc.set_battery_pf(i_batt, elm.Pf)
            nc.set_battery_v(i_batt, elm.Vset)
            nc.set_battery_qmin(i_batt, elm.Qmin)
            nc.set_battery_qmax(i_batt, elm.Qmax)
            nc.set_battery_active(i_batt, elm.active)
            nc.set_battery_controllable(i_batt, elm.is_controlled)
            nc.set_battery_installed_p(i_batt, elm.Snom)

            nc.setC_bus_batt(i, i_batt, 1)

            i_batt += 1

        for elm in bus.shunts:
            nc.set_shunt_name(i_sh, elm.name)
            nc.set_shunt_active(i_sh, elm.active)
            nc.set_shunt_admittance(i_sh, complex(elm.G, elm.B))

            nc.set_c_bus_shunt(i, i_sh, 1)
            i_sh += 1

    for i in range(nbus):
        nc.set_bus_v0(i, complex(V0[i].real, V0[i].imag))

    # Compile the lines
    for i, elm in enumerate(circuit.lines):

        f = bus_dictionary[elm.bus_from.idtag]
        t = bus_dictionary[elm.bus_to.idtag]

        # generic stuff
        set_branch_values(nc=nc, idx=i, name=elm.name,
                          active=elm.active, f=f, t=t, rate=elm.rate,
                          r=elm.R, x=elm.X, g=0, b=elm.B, m=1.0, theta=0.0,
                          vtap_f=1.0, vtap_t=1.0)

        # impedance
        nc.set_line_name(i, elm.name)
        nc.set_line_active(i, elm.active)
        nc.set_line_r(i, elm.R)
        nc.set_line_x(i, elm.X)
        nc.set_line_b(i, elm.B)
        nc.set_line_impedance_tolerance(i, elm.tolerance)
        nc.set_c_line_bus(i, f, 1)
        nc.set_c_line_bus(i, t, 1)

        # Thermal correction
        nc.set_line_temp_base(i, elm.temp_base)
        nc.set_line_temp_oper(i, elm.temp_oper)
        nc.set_line_alpha(i, elm.alpha)

    # 2-winding transformers
    for i, elm in enumerate(circuit.transformers2w):
        ii = i + nline
        tr_tap_f, tr_tap_t = elm.get_virtual_taps()

        # generic stuff
        f = bus_dictionary[elm.bus_from.idtag]
        t = bus_dictionary[elm.bus_to.idtag]

        set_branch_values(nc=nc, idx=ii, name=elm.name,
                          active=elm.active, f=f, t=t, rate=elm.rate,
                          r=elm.R, x=elm.X, g=elm.G, b=elm.B,
                          m=elm.tap_module, theta=elm.angle,
                          vtap_f=tr_tap_f, vtap_t=tr_tap_t)

        # impedance
        nc.set_tr_r(i, elm.R)
        nc.set_tr_x(i, elm.X)
        nc.set_tr_g(i, elm.G)
        nc.set_tr_b(i, elm.B)

        nc.set_c_tr_bus(i, f, 1)
        nc.set_c_tr_bus(i, t, 1)

        # tap changer
        nc.set_tr_tap_mod(i, elm.tap_module)
        nc.set_tr_tap_ang(i, elm.angle)
        nc.set_tr_is_bus_to_regulated(i, elm.bus_to_regulated)
        nc.set_tr_tap_position(i, elm.tap_changer.tap)
        nc.set_tr_min_tap(i, elm.tap_changer.min_tap)
        nc.set_tr_max_tap(i, elm.tap_changer.max_tap)
        nc.set_tr_tap_inc_reg_up(i, elm.tap_changer.inc_reg_up)
        nc.set_tr_tap_inc_reg_down(i, elm.tap_changer.inc_reg_down)
        nc.set_tr_vset(i, elm.vset)

        # virtual taps for transformers where the connection voltage is off
        nc.set_tr_tap_f(i, tr_tap_f)
        nc.set_tr_tap_t(i, tr_tap_t)

    # VSC
    for i, elm in enumerate(circuit.vsc_devices):
        ii = i + nline + ntr2w  # + 3 * ntr3w

        # generic stuff
        f = bus_dictionary[elm.bus_from.idtag]
        t = bus_dictionary[elm.bus_to.idtag]

        set_branch_values(nc=nc, idx=ii, name=elm.name,
                          active=elm.active, f=f, t=t, rate=elm.rate,
                          r=elm.R1, x=elm.X1, g=elm.G0, b=elm.Beq,
                          m=elm.m, theta=elm.theta,
                          vtap_f=1.0, vtap_t=1.0)

        # vsc values
        nc.set_vsc_R1(i, elm.R1)
        nc.set_vsc_X1(i, elm.X1)
        nc.set_vsc_Gsw(i, elm.G0)
        nc.set_vsc_Beq(i, elm.Beq)
        nc.set_vsc_m(i, elm.m)
        nc.set_vsc_theta(i, elm.theta)

        nc.set_c_vsc_Bus(i, f, 1)
        nc.set_c_vsc_Bus(i, t, 1)

    # HVDC: this is the simple detached HVDC model
    for i, elm in enumerate(circuit.hvdc_lines):
        ii = i + nline + ntr2w + nvsc

        # generic stuff
        f = bus_dictionary[elm.bus_from.idtag]
        t = bus_dictionary[elm.bus_to.idtag]

        # hvdc values
        nc.set_hvdc_name(i, elm.name)
        nc.set_hvdc_active(i, elm.active)
        nc.set_hvdc_rate(i, elm.rate)

        nc.set_hvdc_pset_f(i, -elm.Pset)
        nc.set_hvdc_pset_t(i, elm.Pset)
        nc.set_hvdc_vset_f(i, elm.Vset_f)
        nc.set_hvdc_vset_t(i, elm.Vset_t)
        nc.set_hvdc_qmin_f(i, elm.Qmin_f)
        nc.set_hvdc_qmax_f(i, elm.Qmax_f)
        nc.set_hvdc_qmin_t(i, elm.Qmin_t)
        nc.set_hvdc_qmax_t(i, elm.Qmax_t)

        # hack the bus types to believe they are PV
        if elm.active:
            nc.set_bus_types(f, BusMode.PV.value)
            nc.set_bus_types(t, BusMode.PV.value)

        # the the bus-hvdc line connectivity
        nc.set_c_hvdc_bus_f(i, f, 1)
        nc.set_c_hvdc_bus_t(i, t, 1)

    return nc


def get_newton_power_flow_options(opt: PowerFlowOptions):
    """

    :param opt:
    :return:
    """
    newton_solver_dict = {SolverType.NR: nn.NativeSolverType.NR,
                          SolverType.DC: nn.NativeSolverType.DC,
                          SolverType.HELM: nn.NativeSolverType.HELM,
                          SolverType.IWAMOTO: nn.NativeSolverType.IWAMOTO,
                          SolverType.LM: nn.NativeSolverType.LM,
                          SolverType.LACPF: nn.NativeSolverType.LACPF,
                          SolverType.FASTDECOUPLED: nn.NativeSolverType.FD}

    newton_taps_dict = {TapsControlMode.NoControl: nn.NativeTapsControlMode.NoControl,
                        TapsControlMode.Direct: nn.NativeTapsControlMode.Direct}

    newton_q_control_dict = {ReactivePowerControlMode.NoControl: nn.NativeReactivePowerControlMode.NoControl,
                             ReactivePowerControlMode.Direct: nn.NativeReactivePowerControlMode.Direct}

    if opt.solver_type in newton_solver_dict.keys():
        solver_type = newton_solver_dict[opt.solver_type]
    else:
        solver_type = nn.NativeSolverType.NR

    options = nn.NativePowerFlowOptions(solver_type=solver_type,
                                        retry_with_other_methods=opt.retry_with_other_methods,
                                        verbose=opt.verbose,
                                        initialize_with_existing_solution=opt.initialize_with_existing_solution,
                                        tolerance=opt.tolerance,
                                        max_iter=opt.max_iter,
                                        control_q_mode=newton_q_control_dict[opt.control_Q],
                                        tap_control_mode=nn.NativeTapsControlMode.NoControl,
                                        distributed_slack=opt.distributed_slack,
                                        ignore_single_node_islands=opt.ignore_single_node_islands,
                                        correction_parameter=opt.backtracking_parameter,
                                        mu0=opt.mu)

    return options


def newton_power_flow(nc: "nn.NativeNumericCircuit", options: PowerFlowOptions):
    """

    :param nc: NativeNumericCircuit instance
    :param options:
    :return:
    """

    options = get_newton_power_flow_options(options)

    # declare the native power flow driver
    native_driver = nn.NativePowerFlow(nc, options)

    # run power flow
    return native_driver.run()