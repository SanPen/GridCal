from GridCalEngine.api import *

m_circuit = MultiCircuit()

b1 = Bus('B1', is_slack=True)
b2 = Bus('B2')
b3 = Bus('B3')

br1 = Line(b1, b2, name='Br1', r=0.01, x=0.03, rate=100.0)
br2 = Line(b1, b3, name='Br2', r=0.02, x=0.05, rate=100.0)
br3 = Line(b2, b3, name='Br3', r=0.03, x=0.08, rate=100.0)

# add measurements
m_circuit.add_pf_measurement(PfMeasurement(0.888, 0.008, br1))
m_circuit.add_pf_measurement(PfMeasurement(1.173, 0.008, br2))

m_circuit.add_qf_measurement(QfMeasurement(0.568, 0.008, br1))
m_circuit.add_qf_measurement(QfMeasurement(0.663, 0.008, br2))

m_circuit.add_pi_measurement(PiMeasurement(-0.501, 0.01, b2))
m_circuit.add_qi_measurement(QiMeasurement(-0.286, 0.01, b2))

m_circuit.add_vm_measurement(VmMeasurement(1.006, 0.004, b1))
m_circuit.add_vm_measurement(VmMeasurement(0.968, 0.004, b2))

m_circuit.add_bus(b1)
m_circuit.add_bus(b2)
m_circuit.add_bus(b3)

m_circuit.add_branch(br1)
m_circuit.add_branch(br2)
m_circuit.add_branch(br3)

# Declare the simulation driver and run
se = StateEstimation(circuit=m_circuit)
se.run()

print(se.results.get_bus_df())
print(se.results.get_branch_df())