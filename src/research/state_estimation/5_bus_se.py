import numpy as np
import GridCal.Engine as ge


fname = r'Bus5_GSO.EPC'
circuit = ge.FileOpen(fname).open()

P_inj = [3.948380787555101,
         -7.999977535700392,
         4.399999683540577,
         -6.5061596635932496e-06,
         -1.4067612558778269e-05]
Q_inj = [1.1427943453216685,
         -2.799987179659615,
         2.974751282899865,
         6.242047310387063e-07,
         1.9570893381241474e-06]
Vm = [1.0, 0.8337707704259578, 1.04999995, 1.0193026645563943, 0.9742891883707347]  # Not necessary

# create measurements
for p, q, vm, bus in zip(P_inj, Q_inj, Vm, circuit.buses):
    bus.measurements.append(ge.Measurement(p, 0.01, ge.MeasurementType.Pinj))
    bus.measurements.append(ge.Measurement(q, 0.01, ge.MeasurementType.Qinj))
    bus.measurements.append(ge.Measurement(vm, 0.01, ge.MeasurementType.Vmag))

se = ge.StateEstimation(circuit=circuit)

se.run()

print()
print('V: ', se.results.voltage)
print('Vm: ', np.abs(se.results.voltage))
print('Va: ', np.angle(se.results.voltage))
print('Error', se.results.error)
print()

