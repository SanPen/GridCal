#!/usr/bin/env python
# coding: utf-8

# In[2]:

import numpy as np
import pandapower as pp
from pandapower.estimation import estimate
from pandapower.estimation import remove_bad_data
from GridCalEngine.IO.others.pandapower_parser import Panda2GridCal
from GridCalEngine.Simulations.StateEstimation.state_stimation_driver import StateEstimation

# Example Network
# 
# We will be using the reference network from the book "Power System State Estimation" by Ali Abur and Antonio Gómez Expósito. 
# It contains 3 buses with connecting lines between buses 1-2, 1-3 and 2-3. 8 measurements of different types enable WLS state estimation.
# 
# We first create this network in pandapower.

net = pp.create_empty_network()
b1 = pp.create_bus(net, name="bus 1", vn_kv=1., index=1)
b2 = pp.create_bus(net, name="bus 2", vn_kv=1., index=2)
b3 = pp.create_bus(net, name="bus 3", vn_kv=1., index=3)
pp.create_ext_grid(net, 1)  # set the slack bus to bus 1
l1 = pp.create_line_from_parameters(net, 1, 2, 1, r_ohm_per_km=.01, x_ohm_per_km=.03, c_nf_per_km=0., max_i_ka=1)
l2 = pp.create_line_from_parameters(net, 1, 3, 1, r_ohm_per_km=.02, x_ohm_per_km=.05, c_nf_per_km=0., max_i_ka=1)
l3 = pp.create_line_from_parameters(net, 2, 3, 1, r_ohm_per_km=.03, x_ohm_per_km=.08, c_nf_per_km=0., max_i_ka=1)
load1 = pp.create_load(net, bus=b2, p_mw=0.5, q_mvar=0.3)
load2 = pp.create_load(net, bus=b3, p_mw=1.5, q_mvar=0.8)

pp.create_measurement(net, "v", "bus", 1.006, .004, element=b1)  # V at bus 1
pp.create_measurement(net, "v", "bus", 0.968, .004, element=b2)  # V at bus 2
pp.create_measurement(net, "p", "bus", 0.501, 0.01, element=b2)  # P at bus 2
pp.create_measurement(net, "q", "bus", 0.286, 0.01, element=b2)  # Q at bus 2
pp.create_measurement(net, "p", "line", 0.888, 0.008, element=l1, side=b1)  # Pline (bus 1 -> bus 2) at bus 1
pp.create_measurement(net, "p", "line", 1.173, 0.008, element=l2, side=b1)  # Pline (bus 1 -> bus 3) at bus 1
pp.create_measurement(net, "q", "line", 0.568, 0.008, element=l1, side=b1)  # Qline (bus 1 -> bus 2) at bus 1
pp.create_measurement(net, "q", "line", 0.663, 0.008, element=l2, side=b1)  # Qline (bus 1 -> bus 3) at bus 1

pp.runpp(net)

success = estimate(net, init='flat')
net.res_bus_est

# The results match exactly with the results from the book: Voltages 0.9996, 0.9742, 0.9439; Voltage angles 0.0, -1.2475, -2.7457). Nice!
# Let's look at the bus power injections, which are available in res_bus_est as well
net.res_line_est

# This is the original network with the nominal values, you can observe the results are close to the estimation
success_rn_max = remove_bad_data(net, init='flat', rn_max_threshold=3.0)
print(success_rn_max)

# The management of results will be the same as for the *estimate* function (see following section).

# Convert to GridCal ---------------------------------------------------------------------------------------------------

converter = Panda2GridCal(net)
grid = converter.get_multicircuit()
# grid.Sbase = 1.0
# grid.change_base(100)

se_driver = StateEstimation(circuit=grid)
se_driver.run()

print(se_driver.results.get_bus_df())
print(se_driver.results.get_branch_df())
print(se_driver.results.error)
print()
