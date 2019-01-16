#!python3
#
# Copyright (C) 2014-2015 Julius Susanto. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

"""
PYPOWER-Dynamics
Nine-Bus Network Stability Test
"""
"""
PYPOWER-Dynamics
Classical Stability Test
"""
# Dynamic model classes
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

    print('----------------------------------------')
    print('PYPOWER-Dynamics - Classical 9 Bus Test')
    print('----------------------------------------')

    # Load PYPOWER case
    ppc = loadcase('case9.py')

    # Program options
    dynopt = {}
    dynopt['h'] = 0.001  # step length (s)
    dynopt['t_sim'] = 2.0  # simulation time (s)
    dynopt['max_err'] = 1e-6  # Maximum error in network iteration (voltage mismatches)
    dynopt['max_iter'] = 25  # Maximum number of network iterations
    dynopt['verbose'] = False  # option for verbose messages
    dynopt['fn'] = 60  # Nominal system frequency (Hz)

    # Integrator option
    dynopt['iopt'] = 'mod_euler'
    # dynopt['iopt'] = 'runge_kutta'

    # Create dynamic model objects
    G1 = ext_grid('GEN1', 0, 0.0608, 23.64, dynopt)
    G2 = ext_grid('GEN2', 1, 0.1198, 6.01, dynopt)
    G3 = ext_grid('GEN3', 2, 0.1813, 3.01, dynopt)

    # Create dictionary of elements
    elements = {}
    elements[G1.id] = G1
    elements[G2.id] = G2
    elements[G3.id] = G3

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
    # plt.plot(oRecord.t_axis, oRecord.results['GEN1:omega'])
    plt.xlabel('Time (s)')
    plt.ylabel('Rotor Angles (relative to GEN1)')
    plt.show()

    # Write recorded variables to output file
    oRecord.write_output('output.csv')