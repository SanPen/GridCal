# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
To run this script andes must be installed (pip install andes)
"""
import importlib.util
import pdb
import sys
import matplotlib
import pandas as pd
matplotlib.use('TkAgg')  # or 'QtAgg', depending on your system

import matplotlib.pyplot as plt


# def is_installed(package_name):
#     return importlib.util.find_spec(package_name) is not None

# # Check andes installation
# if not is_installed("andes"):
#     print("ANDES is NOT installed. Please install it using 'pip install andes'.")
#     sys.exit(1)  # Exit with a non-zero status (indicates error)

# If installed, import and continue
import andes

# print("ANDES is installed. Continuing with the rest of the script...")
# build system

andes.config_logger(stream_level=20)

#ss = andes.run('Gen_Load/Gen_load_2.json', default_config=True)
def main():
    andes.config_logger(stream_level=20)
    ss = andes.load('src/trunk/dynamics/Gen_Load/kundur_ieee.json', default_config=True) #Gen_Load/kundur_ieee.json
    ss.files.no_output = True

    ss.PFlow.run()

    voltages = ss.Bus.v.v
    angles = ss.Bus.a.v
    names = ss.Bus.name.v
    for i, (v, a) in enumerate(zip(voltages,angles)):
        print(f"Bus {names[i]}: {v:.4f} pu")
        # print(f"Bus {names[i]}: {a:.4f} pu")


     # # to make PQ behave as constant power load
    # ss.PQ.config.p2p = 1.0
    # ss.PQ.config.p2i = 0
    # ss.PQ.config.p2z = 0
    # ss.PQ.pq2z = 0
    # ss.PQ.config.q2q = 1.0
    # ss.PQ.config.q2i = 0
    # ss.PQ.config.q2z = 0
    

    # tds = ss.TDS
    # tds.config.fixt = 1
    # tds.config.shrinkt = 0
    # tds.config.tstep = 0.001
    # tds.config.tf = 20.0
    # tds.t = 0.0
    # tds.init()

    # # Logging
    # time_history = []
    # omega_history = [[] for _ in range(len(ss.GENCLS))]
    # Ppf_history = [[] for _ in range(len(ss.PQ))]
    # tm_history = [[] for _ in range(len(ss.GENCLS))]
    # te_history = [[] for _ in range(len(ss.GENCLS))]
    # v_history = [[] for _ in range(len(ss.Bus))]


    # # initialize time domain simulation
    # # ss.TDS.run()
    # one = True
    # # Step-by-step simulation
    # while tds.t < tds.config.tf:

    #     if tds.t > 2.5 and one == True:
    #         #ss.PQ.set(src='Ppf', idx='PQ_0', attr='v', value=11.09)
    #         one = False
    #         # Log current state
    #     time_history.append(tds.t)
    #     for i in range(len(ss.GENCLS)):
    #         omega_history[i].append(ss.GENCLS.omega.v[i])
    #         tm_history[i].append(ss.GENCLS.tm.v[i])
    #         te_history[i].append(ss.GENCLS.te.v[i])
    #     for i in range(len(ss.PQ)):
    #         Ppf_history[i].append(ss.PQ.Ppf.v[i])
    #     for i in range(len(ss.Bus)):
    #         v_history[i].append(ss.Bus.v.v[i])

    #     # Advance one time step
    #     tds.itm_step()
    #     tds.t += tds.config.tstep

    # data = [time_history, omega_history, Ppf_history, te_history]


    # omega_df = pd.DataFrame(list(zip(*omega_history)))  # shape: [T, n_generators]
    # omega_df.columns = [f"omega_andes_gen_{i+1}" for i in range(len(omega_history))]

    # tm_df = pd.DataFrame(list(zip(*tm_history)))  # shape: [T, n_generators]
    # tm_df.columns = [f"tm_andes_gen_{i+1}" for i in range(len(omega_history))]

    # te_df = pd.DataFrame(list(zip(*te_history)))  # shape: [T, n_generators]
    # te_df.columns = [f"te_andes_gen_{i+1}" for i in range(len(omega_history))]

    # Ppf_df = pd.DataFrame(list(zip(*Ppf_history)))      # shape: [T, n_loads]
    # Ppf_df.columns = [f"Ppf_andes_load_{i}" for i in range(len(Ppf_history))]

    # v_df = pd.DataFrame(list(zip(*v_history)))      # shape: [T, n_loads]
    # v_df.columns = [f"v_andes_Bus_{i+1}" for i in range(len(v_history))]

    # # Combine all into a single DataFrame
    # df = pd.DataFrame({'Time [s]': time_history})
    # df = pd.concat([df, omega_df, tm_df, te_df, Ppf_df, v_df], axis=1)
    # df.to_csv("simulation_andes_output_gridcal_powerflow.csv", index=False)
    # print('simulation results saved in simulation_andes_output.csv')


# # Plot
# plt.figure(figsize=(10, 6))
# for i, omega in enumerate(omega_history):
#     plt.plot(time_history, omega, label=f'Gen {i+1}')
# plt.xlabel("Time [s]")
# plt.ylabel("Speed [pu]")
# plt.title("Generator Speed ω vs Time")
# # plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.show()
#
#
# # Plot
# plt.figure(figsize=(10, 6))
# for i, Ppf in enumerate(Ppf_history):
#     plt.plot(time_history, Ppf, label=f'PQ {i+1}')
# plt.xlabel("Time [s]")
# plt.ylabel("Active Power [pu]")
# plt.title("Active Power consumtpion vs Time")
# # plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.show()
# #
# ss.TDS.load_plotter()
# ss.TDS.plt.export_csv()
#
# # plot results
# fig, ax = ss.TDS.plt.plot(ss.Bus.v)
#
# fig.savefig('PQ_v_plot.png')


if __name__ == '__main__':
    main()