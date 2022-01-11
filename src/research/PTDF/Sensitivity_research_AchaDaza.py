"""
These are the examples from the chapter 10 of the excellent book
Electric Power Systems Fundamentals by Salvador Acha Daza
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as splin
import scipy.linalg as lin
import GridCal.Engine as gc


fname = r'C:\Users\SPV86\Documents\Git\GitHub\GridCal\Grids_and_profiles\grids\4Bus_SalvadorAchaDaza.gridcal'

circuit = gc.FileOpen(fname).open()
nc = gc.compile_snapshot_circuit(circuit)

"""
Corrected example from section 10.3 in which a new kind of flows + angles sensitivity is derived
"""

X = sp.diags(nc.branch_data.X)
A = nc.A

W11 = -X
W12 = A
W21 = A.T
W22 = A.T * (X * A)

W = sp.vstack((sp.hstack((W11, W12)),
               sp.hstack((W21, W22)))).tocsc()

idx = np.r_[np.arange(nc.nbr), nc.nbr + nc.pqpv]
Wred = W[np.ix_(idx, idx)]

print("W\n", W.toarray())

W1red = splin.inv(Wred.tocsc()).toarray()  # it is dense anyway
W1 = np.zeros((nc.nbr + nc.nbus, nc.nbr + nc.nbus))
W1[np.ix_(idx, idx)] = W1red
print("W1\n", W1)

print()

f = np.r_[nc.branch_data.m[:, 0] - 1, nc.Sbus.real]
x = W1.dot(f)

flows = x[:nc.nbr]
angles = x[nc.nbr:]
print('Flows:', flows * nc.Sbase, 'MW')
print('Angles:', angles, 'Rad')

# 10.3.1 introduce a tap change (0.05 rad in branch 1-3)
print()
print('After introducing a tap change (0.05 rad in branch 1-3, the second branch)')
f = np.r_[nc.branch_data.m[:, 0] - 1, nc.Sbus.real]
f[1] = -0.05
x = W1.dot(f)

flows = x[:nc.nbr]
angles = x[nc.nbr:]
print('Flows:', flows * nc.Sbase, 'MW')
print('Angles:', angles, 'Rad')

# 10.3.1 increase the load 4 in 0.5 p.u.
print()
print('After introducing a increase the load 4 in 0.5 p.u.')
f = np.r_[nc.branch_data.m[:, 0] - 1, nc.Sbus.real]
f[nc.nbr + 4 - 1] -= 0.5
x = W1.dot(f)

flows = x[:nc.nbr]
angles = x[nc.nbr:]
print('Flows:', flows * nc.Sbase, 'MW')
print('Angles:', angles, 'Rad')