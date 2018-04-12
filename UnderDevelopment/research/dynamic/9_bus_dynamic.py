#!python3
#
# Copyright (C) 2014-2015 Julius Susanto. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""
PYPOWER-Dynamics
Nine-Bus Network Stability Test
"""
# Dynamic model classes
from pydyn.controller import controller
from pydyn.sym_order6a import sym_order6a
from pydyn.sym_order6b import sym_order6b
from pydyn.sym_order4 import sym_order4
from pydyn.ext_grid import ext_grid

# Simulation modules
from pydyn.events import events
from pydyn.recorder import recorder
from pydyn.run_sim import run_sim

# External modules
from pypower.loadcase import loadcase
import matplotlib.pyplot as plt
import numpy as np

if __name__ == '__main__':
    #########
    # SETUP #
    #########

    print('---------------------------------------')
    print('PYPOWER-Dynamics - 9 Bus Stability Test')
    print('---------------------------------------')

    # Load PYPOWER case
    ppc = loadcase('case9.py')

    # Program options
    dynopt = dict()
    dynopt['h'] = 0.01  # step length (s)
    dynopt['t_sim'] = 15.0  # simulation time (s)
    dynopt['max_err'] = 1e-6  # Maximum error in network iteration (voltage mismatches)
    dynopt['max_iter'] = 25  # Maximum number of network iterations
    dynopt['verbose'] = False  # option for verbose messages
    dynopt['fn'] = 60  # Nominal system frequency (Hz)
    dynopt['speed_volt'] = True  # Speed-voltage term option (for current injection calculation)

    # Integrator option
    # dynopt['iopt'] = 'mod_euler'
    dynopt['iopt'] = 'runge_kutta'

    # Create dynamic model objects
    G1 = sym_order6b('G1.mach', dynopt)
    G2 = sym_order6b('G2.mach', dynopt)
    G3 = sym_order6b('G3.mach', dynopt)

    # Create dictionary of elements
    elements = dict()
    elements[G1.id] = G1
    elements[G2.id] = G2
    elements[G3.id] = G3
    # elements[oCtrl.id] = oCtrl

    # Create event stack
    oEvents = events('events.evnt')

    # Create recorder object
    oRecord = recorder('recorder.rcd')

    # Run simulation
    oRecord = run_sim(ppc, elements, dynopt, oEvents, oRecord)

    # Calculate relative rotor angles
    rel_delta1 = np.array(oRecord.results['GEN2:delta']) - np.array(oRecord.results['GEN1:delta'])
    rel_delta2 = np.array(oRecord.results['GEN3:delta']) - np.array(oRecord.results['GEN1:delta'])

    # Plot variables
    plt.plot(oRecord.t_axis, rel_delta1 * 180 / np.pi, 'r-', oRecord.t_axis, rel_delta2 * 180 / np.pi, 'b-')
    plt.xlabel('Time (s)')
    plt.ylabel('Rotor Angles (relative to GEN1)')
    plt.show()

    # Write recorded variables to output file
    # oRecord.write_output('output.csv')