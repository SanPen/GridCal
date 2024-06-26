from GridCalEngine.api import *

np.set_printoptions(linewidth=10000)


def test_3_node() -> None:
    """
    3-bus state estimation test from monticellí's book
    """
    grid = MultiCircuit()

    b1 = Bus(name='B1', is_slack=True)
    b2 = Bus(name='B2')
    b3 = Bus(name='B3')

    br1 = Line(bus_from=b1, bus_to=b2, name='Br1', r=0.01, x=0.03)
    br2 = Line(bus_from=b1, bus_to=b3, name='Br2', r=0.02, x=0.05)
    br3 = Line(bus_from=b2, bus_to=b3, name='Br3', r=0.03, x=0.08)

    # add measurements
    grid.add_pf_measurement(PfMeasurement(0.888, 0.008, br1))
    grid.add_pf_measurement(PfMeasurement(1.173, 0.008, br2))

    grid.add_qf_measurement(QfMeasurement(0.568, 0.008, br1))
    grid.add_qf_measurement(QfMeasurement(0.663, 0.008, br2))

    grid.add_pi_measurement(PiMeasurement(-0.501, 0.01, b2))
    grid.add_qi_measurement(QiMeasurement(-0.286, 0.01, b2))

    grid.add_vm_measurement(VmMeasurement(1.006, 0.004, b1))
    grid.add_vm_measurement(VmMeasurement(0.968, 0.004, b2))

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    grid.add_branch(br1)
    grid.add_branch(br2)
    grid.add_branch(br3)

    se = StateEstimation(circuit=grid)

    se.run()

    # print()
    # print('V: ', se.results.voltage)
    # print('Vm: ', np.abs(se.results.voltage))
    # print('Va: ', np.angle(se.results.voltage))

    """
    The validated output is:

    V:   [0.99962926+0.j        0.97392515-0.02120941j  0.94280676-0.04521561j]
    Vm:  [0.99962926            0.97415607              0.94389038]
    Va:  [ 0.                   -0.0217738              -0.0479218]
    """

    results = np.array([0.99962926+0.j, 0.97392515-0.02120941j, 0.94280676-0.04521561j])
    assert np.allclose(se.results.voltage, results)
