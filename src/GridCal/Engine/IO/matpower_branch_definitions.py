from numpy import sqrt

__author__ = 'spv86_000'
# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.
from numpy import intc, double
"""Defines constants for named column indices to branch matrix.

Some examples of usage, after defining the constants using the line above,
are::

    branch[3, BR_STATUS] = 0              # take branch 4 out of service
    Ploss = branch[:, PF] + branch[:, PT] # compute real power loss vector

The index, name and meaning of each column of the branch matrix is given
below:

columns 0-10 must be included in input matrix (in case file)
    0.  C{F_BUS}       from bus number
    1.  C{T_BUS}       to bus number
    2.  C{BR_R}        resistance (p.u.)
    3.  C{BR_X}        reactance (p.u.)
    4.  C{BR_B}        total line charging susceptance (p.u.)
    5.  C{RATE_A}      MVA rating A (long term rating)
    6.  C{RATE_B}      MVA rating B (short term rating)
    7.  C{RATE_C}      MVA rating C (emergency rating)
    8.  C{TAP}         transformer off nominal turns ratio
    9.  C{SHIFT}       transformer phase shift angle (degrees)
    10. C{BR_STATUS}   initial branch status, 1 - in service, 0 - out of service
    11. C{ANGMIN}      minimum angle difference, angle(Vf) - angle(Vt) (degrees)
    12. C{ANGMAX}      maximum angle difference, angle(Vf) - angle(Vt) (degrees)

columns 13-16 are added to matrix after power flow or OPF solution
they are typically not present in the input matrix
    13. C{PF}          real power injected at "from" bus end (MW)
    14. C{QF}          reactive power injected at "from" bus end (MVAr)
    15. C{PT}          real power injected at "to" bus end (MW)
    16. C{QT}          reactive power injected at "to" bus end (MVAr)

columns 17-18 are added to matrix after OPF solution
they are typically not present in the input matrix

(assume OPF objective function has units, C{u})
    17. C{MU_SF}       Kuhn-Tucker multiplier on MVA limit at "from" bus (u/MVA)
    18. C{MU_ST}       Kuhn-Tucker multiplier on MVA limit at "to" bus (u/MVA)

columns 19-20 are added to matrix after SCOPF solution
they are typically not present in the input matrix

(assume OPF objective function has units, C{u})
    19. C{MU_ANGMIN}   Kuhn-Tucker multiplier lower angle difference limit
    20. C{MU_ANGMAX}   Kuhn-Tucker multiplier upper angle difference limit

(FUBM parameters)

    21. VF_SET  
    22. VT_SET  
    23. MA_MAX 
    24. MA_MIN 
    25. CONV_A     
    26. BEQ     
    27. K2   
    28. BEQ_MIN 
    29. BEQ_MAX 
    30. SH_MIN  
    31. SH_MAX  
    32. GSW 
    33. ALPHA1 
    34. ALPHA2 
    35. ALPHA3   
    36. KDP 

@author: Ray Zimmerman (PSERC Cornell)
@author: Richard Lincoln
"""

# define the indices
F_BUS = 0    # f, from bus number
T_BUS = 1    # t, to bus number
BR_R = 2    # r, resistance (p.u.)
BR_X = 3    # x, reactance (p.u.)
BR_B = 4    # b, total line charging susceptance (p.u.)
RATE_A = 5    # rateA, MVA rating A (long term rating)
RATE_B = 6    # rateB, MVA rating B (short term rating)
RATE_C = 7    # rateC, MVA rating C (emergency rating)
TAP = 8    # ratio, transformer off nominal turns ratio
SHIFT = 9    # angle, transformer phase shift angle (degrees)
BR_STATUS = 10   # initial branch status, 1 - in service, 0 - out of service
ANGMIN = 11   # minimum angle difference, angle(Vf) - angle(Vt) (degrees)
ANGMAX = 12   # maximum angle difference, angle(Vf) - angle(Vt) (degrees)

# included in power flow solution, not necessarily in input
PF = 13   # real power injected at "from" bus end (MW)
QF = 14   # reactive power injected at "from" bus end (MVAr)
PT = 15   # real power injected at "to" bus end (MW)
QT = 16   # reactive power injected at "to" bus end (MVAr)

# included in opf solution, not necessarily in input
# assume objective function has units, u
MU_SF = 17   # Kuhn-Tucker multiplier on MVA limit at "from" bus (u/MVA)
MU_ST = 18   # Kuhn-Tucker multiplier on MVA limit at "to" bus (u/MVA)
MU_ANGMIN = 19   # Kuhn-Tucker multiplier lower angle difference limit
MU_ANGMAX = 20   # Kuhn-Tucker multiplier upper angle difference limit

# from the FUBM model
VF_SET = 21
VT_SET = 22
MA_MAX = 23
MA_MIN = 24
CONV_A = 25
BEQ = 26
K2 = 27
BEQ_MIN = 28 
BEQ_MAX = 29
SH_MIN = 30 
SH_MAX = 31 
GSW = 32
ALPHA1 = 33
ALPHA2 = 34
ALPHA3 = 35  
KDP = 36


branch_format_array = [intc,  # 0
                       intc,
                       double,
                       double,
                       double,
                       double,
                       double,
                       double,
                       double,
                       double,  # 9
                       intc,
                       double,
                       double,
                       double,
                       double,
                       double,
                       double,
                       double,
                       double,
                       double,  # 19 MU_ANGMIN
                       double,
                       
                       double,
                       double,
                       double,
                       double,
                       intc,
                       
                       double,
                       double,
                       double,
                       double,  # 29 BEQ_MAX
                       double,
                       double,
                       double,
                       double,
                       double,
                       double,
                       double
                       ]

branch_headers = ["fbus",  # 0
                  "tbus",
                  "r",
                  "x",
                  "b",
                  "rateA",
                  "rateB",
                  "rateC",
                  "ratio",
                  "angle",  # 9
                  "status",
                  "angmin",
                  "angmax",
                  "Pf",
                  "Qf",
                  "Pt",
                  "Qt",
                  "Mu_Sf",
                  "Mu_St",
                  "Mu_AngMin",  # 19
                  "Mu_AngMax",
                  'VF_SET',
                  'VT_SET',
                  'MA_MAX',
                  'MA_MIN',
                  'CONV_A',
                  'BEQ',
                  'K2',
                  'BEQ_MIN', 
                  'BEQ_MAX',  # 29 BEQ_MAX
                  'SH_MIN', 
                  'SH_MAX', 
                  'GSW',
                  'ALPHA1',
                  'ALPHA2',
                  'ALPHA3',  
                  'KDP'
                  ]

