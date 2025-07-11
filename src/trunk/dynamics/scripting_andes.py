# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
To run this script andes must be installed (pip install andes)
"""
import importlib.util
import sys

def is_installed(package_name):
    return importlib.util.find_spec(package_name) is not None

# Check andes installation
if not is_installed("andes"):
    print("ANDES is NOT installed. Please install it using 'pip install andes'.")
    sys.exit(1)  # Exit with a non-zero status (indicates error)

# If installed, import and continue
import andes

print("ANDES is installed. Continuing with the rest of the script...")


# build system

andes.config_logger(stream_level=20)

#ss = andes.run('Gen_Load/Gen_load_2.json', default_config=True)
ss = andes.run('Gen_Load/Gen_Load_unchanged_params.json', default_config=True)

# to make PQ behave as constant power load
ss.PQ.config.p2p = 1.0
ss.PQ.config.p2i = 0
ss.PQ.config.p2z = 0

ss.PQ.config.q2q = 1.0
ss.PQ.config.q2i = 0
ss.PQ.config.q2z = 0

# config TDS
total_time = 10
tstep = 0.001
ss.TDS.config.tf = total_time
ss.TDS.config.tstep = tstep


# initialize time domain simulation
ss.TDS.run()

ss.TDS.load_plotter()
ss.TDS.plt.export_csv()

# plot results
fig, ax = ss.TDS.plt.plot(ss.Bus.v)

fig.savefig('PQ_v_plot.png')
