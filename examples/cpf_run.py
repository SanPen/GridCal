import os
from matplotlib import pyplot as plt
import GridCal.Engine as gce
from GridCal.Engine.Core.DataStructures.numerical_circuit import compile_numerical_circuit

fname = os.path.join('/Grids_and_profiles/grids', 'IEEE 14.xlsx')
# fname = os.path.join('..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'lynn5buspv.xlsx')

print('Reading...')
main_circuit = gce.FileOpen(fname).open()
pf_options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False,
                                  initialize_with_existing_solution=False,
                                  multi_core=False, dispatch_storage=True,
                                  control_q=gce.ReactivePowerControlMode.Direct,
                                  control_p=True)

####################################################################################################################
# PowerFlowDriver
####################################################################################################################
print('\n\n')
power_flow = gce.PowerFlowDriver(main_circuit, pf_options)
power_flow.run()

print('\n\n', main_circuit.name)
print('\t|V|:', abs(power_flow.results.voltage))
print('\t|Sf|:', abs(power_flow.results.Sf))
print('\t|loading|:', abs(power_flow.results.loading) * 100)
print('\tReport')
print(power_flow.results.get_report_dataframe())

####################################################################################################################
# Voltage collapse
####################################################################################################################
vc_options = gce.ContinuationPowerFlowOptions(step=0.001,
                                              approximation_order=gce.CpfParametrization.ArcLength,
                                              adapt_step=True,
                                              step_min=0.00001,
                                              step_max=0.2,
                                              error_tol=1e-3,
                                              tol=1e-6,
                                              max_it=20,
                                              stop_at=gce.CpfStopAt.Full,
                                              verbose=False)

# just for this test
numeric_circuit = compile_numerical_circuit(main_circuit)
numeric_inputs = numeric_circuit.split_into_islands()
Sbase_ = power_flow.results.Sbus / numeric_circuit.Sbase
Vbase_ = power_flow.results.voltage

vc_inputs = gce.ContinuationPowerFlowInput(Sbase=Sbase_,
                                           Vbase=Vbase_,
                                           Starget=Sbase_ * 2)

vc = gce.ContinuationPowerFlowDriver(circuit=main_circuit,
                                     options=vc_options,
                                     inputs=vc_inputs,
                                     pf_options=pf_options)
vc.run()
res = vc.results.mdl(gce.ResultTypes.BusActivePower)
res.plot()

res = vc.results.mdl(gce.ResultTypes.BusVoltage)
res.plot()

plt.show()
