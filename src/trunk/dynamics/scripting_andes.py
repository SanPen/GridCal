# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
To run this script andes must be installed (pip install andes)
"""
import andes
import time 
from andes.io.json import write
import matplotlib
import pandas as pd
import numpy as np
matplotlib.use('TkAgg')  # or 'QtAgg', depending on your system

import matplotlib.pyplot as plt

def main():
    
    # ss = andes.load('src/trunk/dynamics/Two_Areas_PSS_E/Benchmark_4ger_33_2015.raw', default_config=True)
    # write(ss, 'my_system.json', overwrite=True)

    start = time.time()

    ss = andes.load('Gen_Load/kundur_ieee_no_shunt.json', default_config=True)
    n_xy = len(ss.dae.xy_name)
    print(f"Andes variables = {n_xy}")
    ss.files.no_output = True
    
    # Run PF
    ss.PFlow.run()

    # print(f"Bus voltages = {ss.Bus.v.v}")
    # print(f"Bus angles = {ss.Bus.a.v}")

    end_pf = time.time()
    print(f"ANDES - PF time = {end_pf-start:.6f} [s]")

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
    
    start_tds = time.time()
    # Run TDS
    tds = ss.TDS
    tds.config.fixt = 1
    tds.config.shrinkt = 0
    tds.config.tstep = 0.001
    tds.config.tf = 20.0
    tds.t = 0.0
    tds.init()

    print(len(ss.dae.x))
    print(len(ss.dae.y))

    end_tds = time.time()
    print(f"ANDES - Compiling time = {end_tds-start_tds:.6f} [s]")

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

    end = time.time()
    print(f"ANDES - Execution time: {end - start_sim:.6f} [s]")

    omega_df = pd.DataFrame(list(zip(*omega_history)))  # shape: [T, n_generators]
    omega_df.columns = [f"omega_andes_gen_{i+1}" for i in range(len(omega_history))]

    tm_df = pd.DataFrame(list(zip(*tm_history)))  # shape: [T, n_generators]
    tm_df.columns = [f"tm_andes_gen_{i+1}" for i in range(len(omega_history))]
    tm_df = pd.DataFrame(list(zip(*tm_history)))  # shape: [T, n_generators]
    tm_df.columns = [f"tm_andes_gen_{i+1}" for i in range(len(omega_history))]

    te_df = pd.DataFrame(list(zip(*te_history)))  # shape: [T, n_generators]
    te_df.columns = [f"te_andes_gen_{i+1}" for i in range(len(omega_history))]
    te_df = pd.DataFrame(list(zip(*te_history)))  # shape: [T, n_generators]
    te_df.columns = [f"te_andes_gen_{i+1}" for i in range(len(omega_history))]

    Ppf_df = pd.DataFrame(list(zip(*Ppf_history)))      # shape: [T, n_loads]
    Ppf_df.columns = [f"Ppf_andes_load_{i}" for i in range(len(Ppf_history))]
    Ppf_df = pd.DataFrame(list(zip(*Ppf_history)))      # shape: [T, n_loads]
    Ppf_df.columns = [f"Ppf_andes_load_{i}" for i in range(len(Ppf_history))]

    v_df = pd.DataFrame(list(zip(*v_history)))      # shape: [T, n_loads]
    v_df.columns = [f"v_andes_Bus_{i+1}" for i in range(len(v_history))]
    v_df = pd.DataFrame(list(zip(*v_history)))      # shape: [T, n_loads]
    v_df.columns = [f"v_andes_Bus_{i+1}" for i in range(len(v_history))]

    a_df = pd.DataFrame(list(zip(*a_history)))      # shape: [T, n_loads]
    a_df.columns = [f"a_andes_Bus_{i+1}" for i in range(len(a_history))]

    # Combine all into a single DataFrame
    df = pd.DataFrame({'Time [s]': time_history})
    df = pd.concat([df, omega_df, tm_df, te_df, Ppf_df, v_df, a_df], axis=1)
    df.to_csv("simulation_andes_output.csv", index=False)
    print('simulation results saved in simulation_andes_output.csv')

    # # Plot
    # plt.figure(figsize=(10, 6))
    # for i, omega in enumerate(omega_history):
    #     plt.plot(time_history, omega, label=f'Gen {i+1}')
    # plt.xlabel("Time [s]")
    # plt.ylabel("Speed [pu]")
    # plt.title("Generator Speed ω vs Time")
    # plt.legend()
    # plt.grid(True)
    # plt.tight_layout()
    # plt.show()

if __name__ == '__main__':
    main()


