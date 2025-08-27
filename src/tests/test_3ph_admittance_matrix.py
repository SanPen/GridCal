import numpy as np
import VeraGridEngine.api as gce

def test_2x2_bc():

    line = gce.OverheadLineType()

    wire = gce.Wire(name="Panther 30/7 ACSR",
                    diameter=21.0,
                    diameter_internal=9.0,
                    is_tube=True,
                    r=0.1363,
                    max_current=1)

    line.add_wire_relationship(wire=wire,
                               xpos=-1,
                               ypos=10,
                               phase=2
    )

    line.add_wire_relationship(wire=wire,
                               xpos=1,
                               ypos=10,
                               phase=3
                               )

    line.compute()

    obtained_ys = line.get_ys(circuit_idx=1, Sbase=100.0, length=1.0, Vnom=10.0)
    obtained_ysh = line.get_ysh(circuit_idx=1, Sbase=100.0, length=1.0, Vnom=10.0)

    correct_ys = np.array([
        [0.+0.j, 0.+0.j, 0.+0.j],
        [0.+0.j, 0.59449198-1.69333179j, -0.41531796+0.83431634j],
        [0.+0.j, -0.41531796+0.83431634j, 0.59449198-1.69333179j]
    ])

    correct_ysh = np.array([
        [0.+0.j, 0.+0.j, 0.+0.j],
        [0.+0.j, +0.+2.55256035j, -0.-0.77993899j],
        [0.+0.j, -0.-0.77993899j, +0.+2.55256035j]
    ])

    assert np.allclose(obtained_ys.values, correct_ys, atol=1e-4)
    assert np.allclose(obtained_ysh.values, correct_ysh, atol=1e-4)

def test_3x3_abc():

    line = gce.OverheadLineType()

    wire = gce.Wire(name="Panther 30/7 ACSR",
                    diameter=21.0,
                    diameter_internal=9.0,
                    is_tube=True,
                    r=0.1363,
                    max_current=1)

    line.add_wire_relationship(wire=wire,
                               xpos=-1,
                               ypos=10,
                               phase=1
    )

    line.add_wire_relationship(wire=wire,
                               xpos=0,
                               ypos=10,
                               phase=2
    )

    line.add_wire_relationship(wire=wire,
                               xpos=1,
                               ypos=10,
                               phase=3
                               )

    line.compute()

    obtained_ys = line.get_ys(circuit_idx=1, Sbase=100.0, length=1.0, Vnom=10.0)
    obtained_ysh = line.get_ysh(circuit_idx=1, Sbase=100.0, length=1.0, Vnom=10.0)

    correct_ys = np.array([
        [0.78416059-1.96468603j, -0.42934099+0.75717701j, -0.22564935+0.56296209j],
        [-0.42934099+0.75717701j, 0.93652163-2.08809006j, -0.42934099+0.75717701j],
        [-0.22564935+0.56296209j, -0.42934099+0.75717701j,  0.78416059-1.96468603j]
    ])

    correct_ysh = np.array([
        [0.+2.83436888j, -0.-0.927113j, -0.-0.49813046j],
        [-0.-0.927113j, 0.+3.05007988j, -0.-0.927113j],
        [-0.-0.49813046j, -0.-0.927113j, +0.+2.83436888j]
    ])

    assert np.allclose(obtained_ys.values, correct_ys, atol=1e-4)
    assert np.allclose(obtained_ysh.values, correct_ysh, atol=1e-4)