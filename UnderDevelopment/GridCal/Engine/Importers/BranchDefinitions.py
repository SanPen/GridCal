from numpy import sqrt

__author__ = 'spv86_000'
# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

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

@author: Ray Zimmerman (PSERC Cornell)
@author: Richard Lincoln
"""

# define the indices
F_BUS       = 0    # f, from bus number
T_BUS       = 1    # t, to bus number
BR_R        = 2    # r, resistance (p.u.)
BR_X        = 3    # x, reactance (p.u.)
BR_B        = 4    # b, total line charging susceptance (p.u.)
RATE_A      = 5    # rateA, MVA rating A (long term rating)
RATE_B      = 6    # rateB, MVA rating B (short term rating)
RATE_C      = 7    # rateC, MVA rating C (emergency rating)
TAP         = 8    # ratio, transformer off nominal turns ratio
SHIFT       = 9    # angle, transformer phase shift angle (degrees)
BR_STATUS   = 10   # initial branch status, 1 - in service, 0 - out of service
ANGMIN      = 11   # minimum angle difference, angle(Vf) - angle(Vt) (degrees)
ANGMAX      = 12   # maximum angle difference, angle(Vf) - angle(Vt) (degrees)

# included in power flow solution, not necessarily in input
PF          = 13   # real power injected at "from" bus end (MW)
QF          = 14   # reactive power injected at "from" bus end (MVAr)
PT          = 15   # real power injected at "to" bus end (MW)
QT          = 16   # reactive power injected at "to" bus end (MVAr)

# included in opf solution, not necessarily in input
# assume objective function has units, u
MU_SF       = 17   # Kuhn-Tucker multiplier on MVA limit at "from" bus (u/MVA)
MU_ST       = 18   # Kuhn-Tucker multiplier on MVA limit at "to" bus (u/MVA)
MU_ANGMIN   = 19   # Kuhn-Tucker multiplier lower angle difference limit
MU_ANGMAX   = 20   # Kuhn-Tucker multiplier upper angle difference limit

BR_CURRENT = 21  # Branch current in kA
LOADING = 22  # Branch loading factor
LOSSES = 23   # branches losses in MVA
O_INDEX = 24  # Original index

from numpy import intc, double
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
                       double,  # 19
                       double,
                       double,
                       double,
                       double,
                       intc]

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
                  "Current",
                  "Loading",
                  "Losses",
                  "Original_index"]

"""
Defines constants for named column indices to dcline matrix.

Some examples of usage, after defining the constants using the line above,
are:

  ppc.dcline(4, c['BR_STATUS']) = 0          take branch 4 out of service

The index, name and meaning of each column of the branch matrix is given
below:

columns 1-17 must be included in input matrix (in case file)
 1  F_BUS       f, "from" bus number
 2  T_BUS       t,  "to"  bus number
 3  BR_STATUS   initial branch status, 1 - in service, 0 - out of service
 4  PF          MW flow at "from" bus ("from" -> "to")
 5  PT          MW flow at  "to"  bus ("from" -> "to")
 6  QF          MVAr injection at "from" bus ("from" -> "to")
 7  QT          MVAr injection at  "to"  bus ("from" -> "to")
 8  VF          voltage setpoint at "from" bus (p.u.)
 9  VT          voltage setpoint at  "to"  bus (p.u.)
10  PMIN        lower limit on PF (MW flow at "from" end)
11  PMAX        upper limit on PF (MW flow at "from" end)
12  QMINF       lower limit on MVAr injection at "from" bus
13  QMAXF       upper limit on MVAr injection at "from" bus
14  QMINT       lower limit on MVAr injection at  "to"  bus
15  QMAXT       upper limit on MVAr injection at  "to"  bus
16  LOSS0       constant term of linear loss function (MW)
17  LOSS1       linear term of linear loss function (MW/MW)
                (loss = LOSS0 + LOSS1 * PF)

columns 18-23 are added to matrix after OPF solution
they are typically not present in the input matrix
                (assume OPF objective function has units, u)
18  MU_PMIN     Kuhn-Tucker multiplier on lower flow lim at "from" bus (u/MW)
19  MU_PMAX     Kuhn-Tucker multiplier on upper flow lim at "from" bus (u/MW)
20  MU_QMINF    Kuhn-Tucker multiplier on lower VAr lim at "from" bus (u/MVAr)
21  MU_QMAXF    Kuhn-Tucker multiplier on upper VAr lim at "from" bus (u/MVAr)
22  MU_QMINT    Kuhn-Tucker multiplier on lower VAr lim at  "to"  bus (u/MVAr)
23  MU_QMAXT    Kuhn-Tucker multiplier on upper VAr lim at  "to"  bus (u/MVAr)

@see: L{toggle_dcline}
"""

# define the indices
c = {
    'F_BUS':     0,     ## f, "from" bus number
    'T_BUS':     1,     ## t,  "to"  bus number
    'BR_STATUS': 2,     ## initial branch status, 1 - in service, 0 - out of service
    'PF':        3,     ## MW flow at "from" bus ("from" -> "to")
    'PT':        4,     ## MW flow at  "to"  bus ("from" -> "to")
    'QF':        5,     ## MVAr injection at "from" bus ("from" -> "to")
    'QT':        6,     ## MVAr injection at  "to"  bus ("from" -> "to")
    'VF':        7,     ## voltage setpoint at "from" bus (p.u.)
    'VT':        8,     ## voltage setpoint at  "to"  bus (p.u.)
    'PMIN':      9,     ## lower limit on PF (MW flow at "from" end)
    'PMAX':     10,     ## upper limit on PF (MW flow at "from" end)
    'QMINF':    11,     ## lower limit on MVAr injection at "from" bus
    'QMAXF':    12,     ## upper limit on MVAr injection at "from" bus
    'QMINT':    13,     ## lower limit on MVAr injection at  "to"  bus
    'QMAXT':    14,     ## upper limit on MVAr injection at  "to"  bus
    'LOSS0':    15,     ## constant term of linear loss function (MW)
    'LOSS1':    16,     ## linear term of linear loss function (MW)
    'MU_PMIN':  17,     ## Kuhn-Tucker multiplier on lower flow lim at "from" bus (u/MW)
    'MU_PMAX':  18,     ## Kuhn-Tucker multiplier on upper flow lim at "from" bus (u/MW)
    'MU_QMINF': 19,     ## Kuhn-Tucker multiplier on lower VAr lim at "from" bus (u/MVAr)
    'MU_QMAXF': 20,     ## Kuhn-Tucker multiplier on upper VAr lim at "from" bus (u/MVAr)
    'MU_QMINT': 21,     ## Kuhn-Tucker multiplier on lower VAr lim at  "to"  bus (u/MVAr)
    'MU_QMAXT': 22      ## Kuhn-Tucker multiplier on upper VAr lim at  "to"  bus (u/MVAr)
}


def get_transformer_impedances(HV_nominal_voltage, LV_nominal_voltage, Nominal_power, Copper_losses, Iron_losses,
                               No_load_current, Short_circuit_voltage, GR_hv1, GX_hv1):
        """
        Compute the branch parameters of a transformer from the short circuit
        test values
        @param HV_nominal_voltage: High voltage side nominal voltage (kV)
        @param LV_nominal_voltage: Low voltage side nominal voltage (kV)
        @param Nominal_power: Transformer nominal power (MVA)
        @param Copper_losses: Copper losses (kW)
        @param Iron_losses: Iron Losses (kW)
        @param No_load_current: No load current (%)
        @param Short_circuit_voltage: Short circuit voltage (%)
        @param GR_hv1:
        @param GX_hv1:
        @return:
            leakage_impedance: Series impedance
            magnetizing_impedance: Shunt impedance
        """
        Uhv = HV_nominal_voltage

        Ulv = LV_nominal_voltage

        Sn = Nominal_power

        Pcu = Copper_losses

        Pfe = Iron_losses

        I0 = No_load_current

        Usc = Short_circuit_voltage

        # Nominal impedance HV (Ohm)
        Zn_hv = Uhv * Uhv / Sn

        # Nominal impedance LV (Ohm)
        Zn_lv = Ulv * Ulv / Sn

        # Short circuit impedance (p.u.)
        zsc = Usc / 100

        # Short circuit resistance (p.u.)
        rsc = (Pcu / 1000) / Sn

        # Short circuit reactance (p.u.)
        xsc = sqrt(zsc * zsc - rsc * rsc)

        # HV resistance (p.u.)
        rcu_hv = rsc * GR_hv1

        # LV resistance (p.u.)
        rcu_lv = rsc * (1 - GR_hv1)

        # HV shunt reactance (p.u.)
        xs_hv = xsc * GX_hv1

        # LV shunt reactance (p.u.)
        xs_lv = xsc * (1 - GX_hv1)

        # Shunt resistance (p.u.)
        rfe = Sn / (Pfe / 1000)

        # Magnetization impedance (p.u.)
        zm = 1 / (I0 / 100)

        # Magnetization reactance (p.u.)
        xm = 0.0
        if rfe > zm:
            xm = 1 / sqrt(1 / (zm * zm) - 1 / (rfe * rfe))
        else:
            xm = 0  # the square root cannot be computed

        # Calculated parameters in per unit
        leakage_impedance = rsc + 1j * xsc
        magnetizing_impedance = rfe + 1j * xm

        return leakage_impedance, magnetizing_impedance

if __name__ == '__main__':

    Zs, Zsh = get_transformer_impedances(HV_nominal_voltage=20.0,
                                         LV_nominal_voltage=0.4,
                                         Nominal_power=0.25,
                                         Copper_losses=3.3,
                                         Iron_losses=0.69,
                                         No_load_current=0.00276,
                                         Short_circuit_voltage=6,
                                         GR_hv1=0.5,
                                         GX_hv1=0.5)

    print(Zs)
    print(Zsh)
