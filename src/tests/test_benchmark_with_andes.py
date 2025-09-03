# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import andes
import time
import matplotlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Devices.Aggregation.rms_event import RmsEvent
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
import VeraGridEngine.api as gce


matplotlib.use('TkAgg')  # or 'QtAgg', depending on your system

# perform simulation in Andes

def perform_andes_simulation_for_kundur_ieee_no_shunt():

    start = time.time()

    # Load the system
    ss = andes.load('Gen_Load/kundur_ieee_no_shunt.json', default_config=True)

    #number of variables
    n_xy = len(ss.dae.xy_name)

    # avoid files generation
    ss.files.no_output = True

    # Run PF
    ss.PFlow.run()

    end_pf = time.time()
    powerflow_time = end_pf - start

    # PQ constant power load
    ss.PQ.config.p2p = 1.0
    ss.PQ.config.p2i = 0
    ss.PQ.config.p2z = 0
    ss.PQ.pq2z = 0
    ss.PQ.config.q2q = 1.0
    ss.PQ.config.q2i = 0
    ss.PQ.config.q2z = 0

    # Logging
    time_history = []
    omega_history = [[] for _ in range(len(ss.GENCLS))]
    Ppf_history = [[] for _ in range(len(ss.PQ))]
    tm_history = [[] for _ in range(len(ss.GENCLS))]
    te_history = [[] for _ in range(len(ss.GENCLS))]
    v_history = [[] for _ in range(len(ss.Bus))]
    a_history = [[] for _ in range(len(ss.Bus))]
    vf_history = [[] for _ in range(len(ss.GENCLS))]

    start_compiling = time.time()
    # Run TDS
    tds = ss.TDS
    tds.config.fixt = 1
    tds.config.shrinkt = 0
    tds.config.tstep = 0.001
    tds.config.tf = 20.0
    tds.t = 0.0
    tds.init()

    end_compiling = time.time()
    compiling_time = end_compiling - start_compiling

    one = True
    # Step-by-step simulation
    start_sim = time.time()

    while tds.t < tds.config.tf:

        if tds.t > 2.5 and one == True:
            ss.PQ.set(src='Ppf', idx='PQ_1', attr='v', value=9.0)
            one = False
            # Log current state
        time_history.append(tds.t)
        for i in range(len(ss.GENCLS)):
            omega_history[i].append(ss.GENCLS.omega.v[i])
            tm_history[i].append(ss.GENCLS.tm.v[i])
            te_history[i].append(ss.GENCLS.te.v[i])
            vf_history[i].append(ss.GENCLS.vf.v[i])
        for i in range(len(ss.PQ)):
            Ppf_history[i].append(ss.PQ.Ppf.v[i])
        for i in range(len(ss.Bus)):
            v_history[i].append(ss.Bus.v.v[i])
            a_history[i].append(ss.Bus.a.v[i])

        # Advance one time step
        tds.itm_step()
        tds.t += tds.config.tstep

    end_sim = time.time()
    simulation_time = end_sim - start_sim

    #save simulation data

    omega_df = pd.DataFrame(list(zip(*omega_history)))  # shape: [T, n_generators]
    omega_df.columns = [f"omega_andes_gen_{i + 1}" for i in range(len(omega_history))]

    tm_df = pd.DataFrame(list(zip(*tm_history)))  # shape: [T, n_generators]
    tm_df.columns = [f"tm_andes_gen_{i + 1}" for i in range(len(omega_history))]
    tm_df = pd.DataFrame(list(zip(*tm_history)))  # shape: [T, n_generators]
    tm_df.columns = [f"tm_andes_gen_{i + 1}" for i in range(len(omega_history))]

    te_df = pd.DataFrame(list(zip(*te_history)))  # shape: [T, n_generators]
    te_df.columns = [f"te_andes_gen_{i + 1}" for i in range(len(omega_history))]
    te_df = pd.DataFrame(list(zip(*te_history)))  # shape: [T, n_generators]
    te_df.columns = [f"te_andes_gen_{i + 1}" for i in range(len(omega_history))]

    Ppf_df = pd.DataFrame(list(zip(*Ppf_history)))  # shape: [T, n_loads]
    Ppf_df.columns = [f"Ppf_andes_load_{i}" for i in range(len(Ppf_history))]
    Ppf_df = pd.DataFrame(list(zip(*Ppf_history)))  # shape: [T, n_loads]
    Ppf_df.columns = [f"Ppf_andes_load_{i}" for i in range(len(Ppf_history))]

    v_df = pd.DataFrame(list(zip(*v_history)))  # shape: [T, n_loads]
    v_df.columns = [f"v_andes_Bus_{i + 1}" for i in range(len(v_history))]
    v_df = pd.DataFrame(list(zip(*v_history)))  # shape: [T, n_loads]
    v_df.columns = [f"v_andes_Bus_{i + 1}" for i in range(len(v_history))]

    a_df = pd.DataFrame(list(zip(*a_history)))  # shape: [T, n_loads]
    a_df.columns = [f"a_andes_Bus_{i + 1}" for i in range(len(a_history))]

    # Combine all into a single DataFrame
    andes_simulation_df = pd.DataFrame({'Time [s]': time_history})
    andes_simulation_df = pd.concat([andes_simulation_df, omega_df, tm_df, te_df, Ppf_df, v_df, a_df], axis=1)

    return andes_simulation_df, powerflow_time, compiling_time, simulation_time

# perform simulation in VeraGrid

def perform_veragrid_simulation_for_kundur_ieee_no_shunt():

    # Build system
    t = Var("t")
    grid = gce.MultiCircuit()

    # Buses
    bus1 = gce.Bus(name="Bus1", Vnom=20)
    bus2 = gce.Bus(name="Bus2", Vnom=20)
    bus3 = gce.Bus(name="Bus3", Vnom=20)
    bus4 = gce.Bus(name="Bus4", Vnom=20)
    bus5 = gce.Bus(name="Bus5", Vnom=230)
    bus6 = gce.Bus(name="Bus6", Vnom=230)
    bus7 = gce.Bus(name="Bus7", Vnom=230)
    bus8 = gce.Bus(name="Bus8", Vnom=230)
    bus9 = gce.Bus(name="Bus9", Vnom=230)
    bus10 = gce.Bus(name="Bus10", Vnom=230)
    bus11 = gce.Bus(name="Bus11", Vnom=230)

    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)
    grid.add_bus(bus5)
    grid.add_bus(bus6)
    grid.add_bus(bus7)
    grid.add_bus(bus8)
    grid.add_bus(bus9)
    grid.add_bus(bus10)
    grid.add_bus(bus11)

    # Line
    line0 = grid.add_line(
        gce.Line(name="line 5-6-1", bus_from=bus5, bus_to=bus6,
                 r=0.00500, x=0.05000, b=0.02187, rate=750.0))

    line1 = grid.add_line(
        gce.Line(name="line 5-6-2", bus_from=bus5, bus_to=bus6,
                 r=0.00500, x=0.05000, b=0.02187, rate=750.0))

    line2 = grid.add_line(
        gce.Line(name="line 6-7-1", bus_from=bus6, bus_to=bus7,
                 r=0.00300, x=0.03000, b=0.00583, rate=700.0))

    line3 = grid.add_line(
        gce.Line(name="line 6-7-2", bus_from=bus6, bus_to=bus7,
                 r=0.00300, x=0.03000, b=0.00583, rate=700.0))

    line4 = grid.add_line(
        gce.Line(name="line 6-7-3", bus_from=bus6, bus_to=bus7,
                 r=0.00300, x=0.03000, b=0.00583, rate=700.0))

    line5 = grid.add_line(
        gce.Line(name="line 7-8-1", bus_from=bus7, bus_to=bus8,
                 r=0.01100, x=0.11000, b=0.19250, rate=400.0))

    line6 = grid.add_line(
        gce.Line(name="line 7-8-2", bus_from=bus7, bus_to=bus8,
                 r=0.01100, x=0.11000, b=0.19250, rate=400.0))

    line7 = grid.add_line(
        gce.Line(name="line 8-9-1", bus_from=bus8, bus_to=bus9,
                 r=0.01100, x=0.11000, b=0.19250, rate=400.0))

    line8 = grid.add_line(
        gce.Line(name="line 8-9-2", bus_from=bus8, bus_to=bus9,
                 r=0.01100, x=0.11000, b=0.19250, rate=400.0))

    line9 = grid.add_line(
        gce.Line(name="line 9-10-1", bus_from=bus9, bus_to=bus10,
                 r=0.00300, x=0.03000, b=0.00583, rate=700.0))

    line10 = grid.add_line(
        gce.Line(name="line 9-10-2", bus_from=bus9, bus_to=bus10,
                 r=0.00300, x=0.03000, b=0.00583, rate=700.0))

    line11 = grid.add_line(
        gce.Line(name="line 9-10-3", bus_from=bus9, bus_to=bus10,
                 r=0.00300, x=0.03000, b=0.00583, rate=700.0))

    line12 = grid.add_line(
        gce.Line(name="line 10-11-1", bus_from=bus10, bus_to=bus11,
                 r=0.00500, x=0.05000, b=0.02187, rate=750.0))

    line13 = grid.add_line(
        gce.Line(name="line 10-11-2", bus_from=bus10, bus_to=bus11,
                 r=0.00500, x=0.05000, b=0.02187, rate=750.0))

    # Transformers

    trafo_G1 = grid.add_line(
        gce.Line(name="trafo 5-1", bus_from=bus5, bus_to=bus1,
                 r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0))

    trafo_G2 = grid.add_line(
        gce.Line(name="trafo 6-2", bus_from=bus6, bus_to=bus2,
                 r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0))

    trafo_G3 = grid.add_line(
        gce.Line(name="trafo 11-3", bus_from=bus11, bus_to=bus3,
                 r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0))

    trafo_G4 = grid.add_line(
        gce.Line(name="trafo 10-4", bus_from=bus10, bus_to=bus4,
                 r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0))

    # load
    load1 = gce.Load(name="load1", P=967.0, Q=100.0, Pl0=-9.670000000007317, Ql0=-0.9999999999967969)
    load1.time = t
    load1_grid = grid.add_load(bus=bus7, api_obj=load1)
    # load1 = grid.add_load(bus=bus7, api_obj=gce.Load(P=967.0, Q=100.0, Pl0=-9.670000000007317, Ql0=-0.9999999999967969))

    load2 = gce.Load(name="load2", P=1767.0, Q=100.0, Pl0=-17.6699999999199, Ql0=-0.999999999989467)
    load2.time = t
    load2_grid = grid.add_load(bus=bus9, api_obj=load2)

    # Generators
    fn_1 = 60.0
    M_1 = 13.0 * 9.0
    D_1 = 10.0 * 9.0
    ra_1 = 0.0
    xd_1 = 0.3 * 100.0 / 900.0
    omega_ref_1 = 1.0
    Kp_1 = 0.0
    Ki_1 = 0.0

    fn_2 = 60.0
    M_2 = 13.0 * 9.0
    D_2 = 10.0 * 9.0
    ra_2 = 0.0
    xd_2 = 0.3 * 100.0 / 900.0
    omega_ref_2 = 1.0
    Kp_2 = 0.0
    Ki_2 = 0.0

    fn_3 = 60.0
    M_3 = 12.35 * 9.0
    D_3 = 10.0 * 9.0
    ra_3 = 0.0
    xd_3 = 0.3 * 100.0 / 900.0
    omega_ref_3 = 1.0
    Kp_3 = 0.0
    Ki_3 = 0.0

    fn_4 = 60.0
    M_4 = 12.35 * 9.0
    D_4 = 10.0 * 9.0
    ra_4 = 0.0
    xd_4 = 0.3 * 100.0 / 900.0
    omega_ref_4 = 1.0
    Kp_4 = 0.0
    Ki_4 = 0.0

    # Generators
    gen1 = gce.Generator(
        name="Gen1", P=700.0, vset=1.03, Snom=900.0,
        x1=xd_1, r1=ra_1, freq=fn_1,
        tm0=6.999999999999923,
        vf=1.141048034212655,
        M=M_1, D=D_1,
        omega_ref=omega_ref_1,
        Kp=Kp_1, Ki=Ki_1
    )

    gen2 = gce.Generator(
        name="Gen2", P=700.0, vset=1.01, Snom=900.0,
        x1=xd_2, r1=ra_2, freq=fn_2,
        tm0=6.999999999999478,
        vf=1.180101792122771,
        M=M_2, D=D_2,
        omega_ref=omega_ref_2,
        Kp=Kp_2, Ki=Ki_2
    )

    gen3 = gce.Generator(
        name="Gen3", P=719.091, vset=1.03, Snom=900.0,
        x1=xd_3, r1=ra_3, freq=fn_3,
        tm0=7.331832804674334,
        vf=1.1551307366822237,
        M=M_3, D=D_3,
        omega_ref=omega_ref_3,
        Kp=Kp_3, Ki=Ki_3
    )

    gen4 = gce.Generator(
        name="Gen4", P=700.0, vset=1.01, Snom=900.0,
        x1=xd_4, r1=ra_4, freq=fn_4,
        tm0=6.99999999999765,
        vf=1.2028205849036708,
        M=M_4, D=D_4,
        omega_ref=omega_ref_4,
        Kp=Kp_4, Ki=Ki_4
    )

    grid.add_generator(bus=bus1, api_obj=gen1)
    grid.add_generator(bus=bus2, api_obj=gen2)
    grid.add_generator(bus=bus3, api_obj=gen3)
    grid.add_generator(bus=bus4, api_obj=gen4)

    # ---------------------------------------------------------------------------------------
    # Events
    # ---------------------------------------------------------------------------------------

    event1 = RmsEvent(load1, "Pl0", np.array([2.5, 12.5]), np.array([-9.0, -9.01]))

    event2 = RmsEvent(load1, "Ql0", np.array([16.5]), np.array([-0.8]))

    grid.add_rms_event(event1)
    grid.add_rms_event(event2)

    # ----------------------------------------------------------------------------------------------------------------------
    # Power flow
    # ----------------------------------------------------------------------------------------------------------------------

    start_power_flow = time.time()

    options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
        three_phase_unbalanced=False
    )
    res = gce.power_flow(grid, options=options)
    end_power_flow = time.time()

    power_flow_time = end_power_flow - start_power_flow

    # ----------------------------------------------------------------------------------------------------------------------
    # Time Domain Simulation
    # ----------------------------------------------------------------------------------------------------------------------

    # TDS initialization
    start_compiling = time.time()

    ss, init_guess = gce.initialize_rms(grid, res)

    params_mapping = {}

    slv = BlockSolver(ss, t)

    end_compiling = time.time()

    compiling_time = start_compiling - end_compiling


    params0 = slv.build_init_params_vector(params_mapping)
    x0 = slv.build_init_vars_vector_from_uid(init_guess)
    vars_in_order = slv.sort_vars_from_uid(init_guess)

    start_simulation = time.time()

    t, y = slv.simulate(
        t0=0,
        t_end=20.0,
        h=0.001,
        x0=x0,
        params0=params0,
        time=t,
        method="implicit_euler"
    )

    end_simulation = time.time()
    simulation_time = end_simulation - start_simulation

    # save results to df
    veragrid_simulation_df = slv.save_simulation_to_csv('simulation_results_Ieee_automatic_init.csv', t, y)

    return veragrid_simulation_df, power_flow_time, compiling_time, simulation_time


def merge_simulation_results_by_time(andes_simulation_df, veragrid_simulation_df, time_col='Time [s]', output_csv = True, output_csv_file = "merged_csv"):

    andes_sim_df = andes_simulation_df
    veragrid_sim_df = veragrid_simulation_df

    # Sort both by time column
    andes_sim_df = andes_sim_df.sort_values(by=time_col)
    veragrid_sim_df = veragrid_sim_df.sort_values(by=time_col)

    # Using merge_asof to align by closest time
    merged_df = pd.merge_asof(
        andes_sim_df, veragrid_sim_df,
        on=time_col,
        direction='nearest',
        suffixes=('_sim1', '_sim2')
    )

    if output_csv:
        merged_df.to_csv(output_csv_file, index=False)
        print(f"Merged results saved to: {output_csv}")

    return merged_df

def compare_andes_veragrid_simulation_results(andes_simulation_df, veragrid_simulation_df):

    merged_df = merge_simulation_results_by_time(andes_simulation_df, veragrid_simulation_df)

    i = 1
    variable_pairs = [
        [f"omega_andes_gen_1", f"omega_VeraGrid"],
        [f"omega_andes_gen_2", f"omega_VeraGrid.1"],
        [f"omega_andes_gen_3", f"omega_VeraGrid.2"],
        [f"omega_andes_gen_4", f"omega_VeraGrid.3"],
    ]


    # Automatically detect time columns
    time_column = merged_df['Time [s]']
    time_columns = [col for col in merged_df.columns if 'Time [s]' in col.lower()]
    time1 = time_column

    # Create subplots
    n = len(variable_pairs)
    cols = 2
    rows = (n + 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(10, 2 * rows), sharex=True)
    axes = axes.flatten()
    for idx, (var1, var2) in enumerate(variable_pairs):
        ax = axes[idx]
        if var1 in merged_df and var2 in merged_df:

            ax.plot(time1, merged_df[var1], label=var1, linestyle='-')
            ax.plot(time1, merged_df[var2], label=var2, linestyle='--')
            ax.set_title(f"{var1} vs {var2}", fontsize=9)
            ax.set_xlabel("Time (s)", fontsize=8)
            ax.set_ylabel("Value (pu)", fontsize=8)
            ax.tick_params(axis='both', labelsize=7)
            ax.legend(fontsize=7, loc='best')
            ax.grid(True)

    axes[-1].set_xlabel("Time (s)")
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    # plt.suptitle("Simulation Variable Comparison (VeraGrid vs GENCLS)", fontsize=16, y=1.02)
    plt.ylim([0.85, 1.15])
    plt.subplots_adjust(top=0.95)
    plt.show()



if __name__ == '__main__':
    andes_sim_results, andes_pf_time, andes_comp_time, andes_sim_time = perform_andes_simulation_for_kundur_ieee_no_shunt()
    veragrid_sim_results, veragrid_pf_time, veragrid_comp_time, veragrid_sim_time = perform_veragrid_simulation_for_kundur_ieee_no_shunt()
    compare_andes_veragrid_simulation_results(andes_sim_results, veragrid_sim_results)

