__author__ = 'spv86_000'

# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.
from numpy import intc, double

"""
Defines constants for named column indices to gen matrix.

Some examples of usage, after defining the constants using the line above,
are::

    Pg = gen[3, PG]   # get the real power output of generator 4
    gen[:, PMIN] = 0  # set to zero the minimum real power limit of all gens

The index, name and meaning of each column of the gen matrix is given
below:

columns 0-20 must be included in input matrix (in case file)
    0.  C{GEN_BUS}     bus number
    1.  C{PG}          real power output (MW)
    2.  C{QG}          reactive power output (MVAr)
    3.  C{QMAX}        maximum reactive power output (MVAr)
    4.  C{QMIN}        minimum reactive power output (MVAr)
    5.  C{VG}          voltage magnitude setpoint (p.u.)
    6.  C{MBASE}       total MVA base of machine, defaults to baseMVA
    7.  C{GEN_STATUS}  1 - in service, 0 - out of service
    8.  C{PMAX}        maximum real power output (MW)
    9.  C{PMIN}        minimum real power output (MW)
    10. C{PC1}         lower real power output of PQ capability curve (MW)
    11. C{PC2}         upper real power output of PQ capability curve (MW)
    12. C{QC1MIN}      minimum reactive power output at Pc1 (MVAr)
    13. C{QC1MAX}      maximum reactive power output at Pc1 (MVAr)
    14. C{QC2MIN}      minimum reactive power output at Pc2 (MVAr)
    15. C{QC2MAX}      maximum reactive power output at Pc2 (MVAr)
    16. C{RAMP_AGC}    ramp rate for load following/AGC (MW/min)
    17. C{RAMP_10}     ramp rate for 10 minute reserves (MW)
    18. C{RAMP_30}     ramp rate for 30 minute reserves (MW)
    19. C{RAMP_Q}      ramp rate for reactive power (2 sec timescale) (MVAr/min)
    20. C{APF}         area participation factor

columns 21-24 are added to matrix after OPF solution
they are typically not present in the input matrix

(assume OPF objective function has units, u)
    21. C{MU_PMAX}     Kuhn-Tucker multiplier on upper Pg limit (u/MW)
    22. C{MU_PMIN}     Kuhn-Tucker multiplier on lower Pg limit (u/MW)
    23. C{MU_QMAX}     Kuhn-Tucker multiplier on upper Qg limit (u/MVAr)
    24. C{MU_QMIN}     Kuhn-Tucker multiplier on lower Qg limit (u/MVAr)

@author: Ray Zimmerman (PSERC Cornell)
@author: Richard Lincoln
"""

# define the indices
GEN_BUS = 0  # bus number
PG = 1  # Pg, real power output (MW)
QG = 2  # Qg, reactive power output (MVAr)
QMAX = 3  # Qmax, maximum reactive power output at Pmin (MVAr)
QMIN = 4  # Qmin, minimum reactive power output at Pmin (MVAr)
VG = 5  # Vg, voltage magnitude setpoint (p.u.)
MBASE = 6  # mBase, total MVA base of this machine, defaults to baseMVA
GEN_STATUS = 7  # status, 1 - machine in service, 0 - machine out of service
PMAX = 8  # Pmax, maximum real power output (MW)
PMIN = 9  # Pmin, minimum real power output (MW)
PC1 = 10  # Pc1, lower real power output of PQ capability curve (MW)
PC2 = 11  # Pc2, upper real power output of PQ capability curve (MW)
QC1MIN = 12  # Qc1min, minimum reactive power output at Pc1 (MVAr)
QC1MAX = 13  # Qc1max, maximum reactive power output at Pc1 (MVAr)
QC2MIN = 14  # Qc2min, minimum reactive power output at Pc2 (MVAr)
QC2MAX = 15  # Qc2max, maximum reactive power output at Pc2 (MVAr)
RAMP_AGC = 16  # ramp rate for load following/AGC (MW/min)
RAMP_10 = 17  # ramp rate for 10 minute reserves (MW)
RAMP_30 = 18  # ramp rate for 30 minute reserves (MW)
RAMP_Q = 19  # ramp rate for reactive power (2 sec timescale) (MVAr/min)
APF = 20  # area participation factor

# included in opf solution, not necessarily in input
# assume objective function has units, u
MU_PMAX = 21  # Kuhn-Tucker multiplier on upper Pg limit (u/MW)
MU_PMIN = 22  # Kuhn-Tucker multiplier on lower Pg limit (u/MW)
MU_QMAX = 23  # Kuhn-Tucker multiplier on upper Qg limit (u/MVAr)
MU_QMIN = 24  # Kuhn-Tucker multiplier on lower Qg limit (u/MVAr)

DISPATCHABLE_GEN = 25

FIX_POWER_GEN = 26

# Note: When a generator's PQ capability curve is not simply a box and the
# upper Qg limit is binding, the multiplier on this constraint is split into
# it's P and Q components and combined with the appropriate MU_Pxxx and
# MU_Qxxx values. Likewise for the lower Q limits.


gen_format_array = [intc,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    intc,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    double,
                    intc,
                    intc]

gen_headers = ["bus",
               "Pg",
               "Qg",
               "Qmax",
               "Qmin",
               "Vg",
               "mBase",
               "status",
               "Pmax",
               "Pmin",
               "Pc1",
               "Pc2",
               "Qc1min",
               "Qc1max",
               "Qc2min",
               "Qc2max",
               "ramp_agc",
               "ramp_10",
               "ramp_30",
               "ramp_q",
               "apf",
               "MU_PMAX",
               "MU_PMIN",
               "MU_QMAX",
               "MU_QMIN",
               "Dispatchable",
               "Fix_power"]

"""
Defines constants for named column indices to gencost matrix.

Some examples of usage, after defining the constants using the line above,
are::

    start = gencost[3, STARTUP]       # get startup cost of generator 4
    gencost[2, [MODEL, NCOST:COST+2]] = [POLYNOMIAL, 2, 30, 0]
    # set the cost of generator 2 to a linear function COST = 30 * Pg

The index, name and meaning of each column of the gencost matrix is given
below:

columns 1-5
    1.  C{MODEL}       cost model, 1 - piecewise linear, 2 - polynomial
    2.  C{STARTUP}     startup cost in US dollars
    3.  C{SHUTDOWN}    shutdown cost in US dollars
    4.  C{NCOST}       number of cost coefficients to follow for polynomial
    cost function, or number of data points for piecewise linear
    5.  C{COST}        1st column of cost parameters
    cost data defining total cost function
    For polynomial cost (highest order coeff first)::
        e.g. cn, ..., c1, c0
    where the polynomial is C{c0 + c1*P + ... + cn*P^n}
    For piecewise linear cost::
        x0, y0, x1, y1, x2, y2, ...
    where C{x0 < x1 < x2 < ...} and the points C{(x0,y0), (x1,y1),
    (x2,y2), ...} are the end- and break-points of the total cost function.

additional constants, used to assign/compare values in the C{MODEL} column
    1.  C{PW_LINEAR}   piecewise linear generator cost model
    2.  C{POLYNOMIAL}  polynomial generator cost model

@author: Ray Zimmerman (PSERC Cornell)
@author: Richard Lincoln
"""
# define cost models
PW_LINEAR = 1
POLYNOMIAL = 2

# define the indices
MODEL = 0
STARTUP = 1
SHUTDOWN = 2
NCOST = 3
COST = 4

gen_cost_headers = ['costtype',
                    'startup',
                    'shutdown',
                    'n',
                    'costvector']
