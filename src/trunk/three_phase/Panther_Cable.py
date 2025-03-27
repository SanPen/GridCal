import numpy as np
import GridCalEngine.api as gce
"""
This test performs the tower composition of the distribution grid demo
:return:
"""
tower = gce.OverheadLineType(name="Tower")

wire = gce.Wire(name="Panther 30/7 ACSR",
                gmr=10.5e-3 * np.exp(-1/4),
                r=0.1363,
                x=0.0,
                max_current=1)

tower.add_wire_relationship(wire=wire, xpos=-12.65-0.23, ypos=27.5+0.23, phase=1)
tower.add_wire_relationship(wire=wire, xpos=-12.65+0.23, ypos=27.5+0.23, phase=1)
tower.add_wire_relationship(wire=wire, xpos=-12.65-0.23, ypos=27.5-0.23, phase=1)
tower.add_wire_relationship(wire=wire, xpos=-12.65+0.23, ypos=27.5-0.23, phase=1)

tower.add_wire_relationship(wire=wire, xpos=0-0.23, ypos=27.5+0.23, phase=2)
tower.add_wire_relationship(wire=wire, xpos=0+0.23, ypos=27.5+0.23, phase=2)
tower.add_wire_relationship(wire=wire, xpos=0-0.23, ypos=27.5-0.23, phase=2)
tower.add_wire_relationship(wire=wire, xpos=0+0.23, ypos=27.5-0.23, phase=2)

tower.add_wire_relationship(wire=wire, xpos=12.65-0.23, ypos=27.5+0.23, phase=3)
tower.add_wire_relationship(wire=wire, xpos=12.65+0.23, ypos=27.5+0.23, phase=3)
tower.add_wire_relationship(wire=wire, xpos=12.65-0.23, ypos=27.5-0.23, phase=3)
tower.add_wire_relationship(wire=wire, xpos=12.65+0.23, ypos=27.5-0.23, phase=3)

tower.compute()

R1, X1, B1 = tower.get_sequence_values(circuit_idx=0, seq=1)
R0, X0, B0 = tower.get_sequence_values(circuit_idx=0, seq=0)
print(f"R0: {R0}, X0: {X0}")
print(f"R1: {R1}, X1: {X1}")

Z = tower.z_abcn
print("Z =\n", Z)

Y = tower.y_abcn
print("Y =\n", Y*1e6)