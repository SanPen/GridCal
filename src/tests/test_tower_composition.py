import numpy as np
import GridCalEngine.api as gce


def test_tower_composition():
    """
    This test performs the tower composition of the distribution grid demo
    :return:
    """
    tower = gce.OverheadLineType(name="Tower")

    wire = gce.Wire(name="AWG SLD",
                    gmr=0.001603,
                    r=1.485077,
                    x=0.0,
                    max_current=0.11)

    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=7.0, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.4, ypos=7.0, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=0.8, ypos=7.0, phase=3)

    tower.compute()

    print(f"R0: {tower.R0}, X0: {tower.X0}")
    print(f"R1: {tower.R1}, X1: {tower.X1}")

    assert np.isclose(tower.R0, 1.5892070972018013, atol=1e-4)
    assert np.isclose(tower.X0, 1.1989736994044684, atol=1e-4)
    assert np.isclose(tower.R1, 1.485081882395359, atol=1e-4)
    assert np.isclose(tower.X1, 0.3613207070253497, atol=1e-4)
