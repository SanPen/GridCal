# 🌀 State estimation

VeraGrid has the ability to run state estimation simulations, however not 
from the interface since VeraGrid is not (yet) made to be coupled to SCADA measurements.
Hence, the state estimation calculations will only be available through the API.

## API

Now lets program the example from the state estimation reference book
State Estimation in Electric Power Systems by A. Monticelli.

```python
import VeraGridEngine as gce

m_circuit = gce.MultiCircuit()

b1 = gce.Bus('B1', is_slack=True)
b2 = gce.Bus('B2')
b3 = gce.Bus('B3')

br1 = gce.Line(b1, b2, name='Br1', r=0.01, x=0.03, rate=100.0)
br2 = gce.Line(b1, b3, name='Br2', r=0.02, x=0.05, rate=100.0)
br3 = gce.Line(b2, b3, name='Br3', r=0.03, x=0.08, rate=100.0)

# add measurements
m_circuit.add_pf_measurement(gce.PfMeasurement(0.888, 0.008, br1))
m_circuit.add_pf_measurement(gce.PfMeasurement(1.173, 0.008, br2))

m_circuit.add_qf_measurement(gce.QfMeasurement(0.568, 0.008, br1))
m_circuit.add_qf_measurement(gce.QfMeasurement(0.663, 0.008, br2))

m_circuit.add_pi_measurement(gce.PiMeasurement(-0.501, 0.01, b2))
m_circuit.add_qi_measurement(gce.QiMeasurement(-0.286, 0.01, b2))

m_circuit.add_vm_measurement(gce.VmMeasurement(1.006, 0.004, b1))
m_circuit.add_vm_measurement(gce.VmMeasurement(0.968, 0.004, b2))

m_circuit.add_bus(b1)
m_circuit.add_bus(b2)
m_circuit.add_bus(b3)

m_circuit.add_line(br1)
m_circuit.add_line(br2)
m_circuit.add_line(br3)

# Declare the simulation driver and run
se = gce.StateEstimation(circuit=m_circuit)
se.run()

print(se.results.get_bus_df())
print(se.results.get_branch_df())
```

Output:

```text
          Vm        Va         P        Q
B1  0.999629  0.000000  2.064016  1.22644
B2  0.974156 -1.247547  0.000000  0.00000
B3  0.943890 -2.745717  0.000000  0.00000

            Pf        Qf          Pt         Qt    loading    Ploss    Qloss
Br1  89.299199 55.882169  -88.188659 -52.550550  89.299199 1.110540 3.331619
Br2 117.102446 66.761871 -113.465724 -57.670065 117.102446 3.636722 9.091805
Br3  38.591163 22.775597  -37.956374 -21.082828  38.591163 0.634789 1.692770
```
