from GridCal.Engine import *
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian

from scipy.sparse import hstack as hstack_sp, vstack as vstack_sp

circuit = MultiCircuit()

b1 = Bus(name='B1')
b2 = Bus(name='B2')
l2 = Load(P=1, Q=1)
br1 = Branch(b1, b2, r=0.1, x=1)
circuit.add_bus(b1)
circuit.add_bus(b2)
circuit.add_load(b2, l2)
circuit.add_branch(br1)

islands = circuit.compile().compute()

npv = len(islands[0].pv)
npq = len(islands[0].pq)
pvpq = np.r_[islands[0].pv, islands[0].pq]
J = Jacobian(Ybus=islands[0].Ybus,
             V=islands[0].Vbus,
             Ibus=islands[0].Ibus,
             pq=islands[0].pq,
             pvpq=pvpq)

ek = np.zeros((1, npv + npq + npq + 1))
ek[0, -1] = 1
K = np.zeros((npv + npq + npq, 1))
J2 = vstack_sp([hstack_sp([J, K]),
                ek], format="csr")

pass
