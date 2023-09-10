from GridCalEngine import *

np.set_printoptions(linewidth=10000)

def test_3_node():
    m_circuit = MultiCircuit()

    b1 = Bus('B1', is_slack=True)
    b2 = Bus('B2')
    b3 = Bus('B3')

    br1 = Line(b1, b2, 'Br1', r=0.01, x=0.03)
    br2 = Line(b1, b3, 'Br2', r=0.02, x=0.05)
    br3 = Line(b2, b3, 'Br3', r=0.03, x=0.08)

    # add measurements
    br1.measurements.append(Measurement(0.888, 0.008, MeasurementType.Pflow))
    br2.measurements.append(Measurement(1.173, 0.008, MeasurementType.Pflow))

    b2.measurements.append(Measurement(-0.501, 0.01, MeasurementType.Pinj))

    br1.measurements.append(Measurement(0.568, 0.008, MeasurementType.Qflow))
    br2.measurements.append(Measurement(0.663, 0.008, MeasurementType.Qflow))

    b2.measurements.append(Measurement(-0.286, 0.01, MeasurementType.Qinj))

    b1.measurements.append(Measurement(1.006, 0.004, MeasurementType.Vmag))
    b2.measurements.append(Measurement(0.968, 0.004, MeasurementType.Vmag))

    m_circuit.add_bus(b1)
    m_circuit.add_bus(b2)
    m_circuit.add_bus(b3)

    m_circuit.add_branch(br1)
    m_circuit.add_branch(br2)
    m_circuit.add_branch(br3)

    br = [br1, br2, br3]

    se = StateEstimation(circuit=m_circuit)

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
