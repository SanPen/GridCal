from GridCalEngine.basic_structures import BranchImpedanceMode
from GridCalEngine.api import *
from GridCalEngine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv (2 islands).gridcal'

main_circuit = FileOpen(fname).open()

# main_circuit.buses[3].controlled_generators[0].enabled_dispatch = False

numerical_circuit_ = compile_snapshot_opf_circuit(circuit=main_circuit,
                                                  apply_temperature=False,
                                                  branch_tolerance_mode=BranchImpedanceMode.Specified)

problem = OpfAc(numerical_circuit=numerical_circuit_)

print('Solving...')
status = problem.solve()

# print("Status:", status)

v = problem.get_voltage()
print('Modules\n', np.abs(v))
print('Angles\n', np.angle(v))

l = problem.get_loading()
print('Branch loading\n', l)

g = problem.get_generator_power()
print('Gen power\n', g)

pr = problem.get_shadow_prices()
print('Nodal prices \n', pr)
