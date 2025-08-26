import os
from GridCalEngine.api import *
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import AvailableTransferMode
import time
from GridCalEngine.basic_structures import BranchImpedanceMode
from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.ATC.available_transfer_capacity_driver import compute_alpha, compute_dP

folder = r'\\mornt4\DESRED\DPE-Internacional\Interconexiones\FRANCIA\2022 MoU\5GW 8.0\Con N-x\merged\GridCal'
fname = os.path.join(folder, 'MOU_2022_5GW_v6f_contingencias_dc.gridcal')

tm0 = time.time()
main_circuit = FileOpen(fname).open()
print(f'circuit opened in {time.time() - tm0:.2f} scs.')

# compute information about areas ----------------------------------------------------------------------------------
area_from_idx = 0
area_to_idx = 1
areas = main_circuit.get_bus_area_indices()

tm0 = time.time()
numerical_circuit_ = compile_numerical_circuit_at(
    circuit=main_circuit,
    apply_temperature=False,
    branch_tolerance_mode=BranchImpedanceMode.Specified
)
print(f'numerical circuit computed in {time.time() - tm0:.2f} scs.')

# get the area bus indices
areas = areas[numerical_circuit_.original_bus_idx]
a1 = np.where(areas == area_from_idx)[0]
a2 = np.where(areas == area_to_idx)[0]

linear = LinearAnalysis(
    nc=numerical_circuit_,
    distributed_slack=False,
    correct_values=False
)

tm0 = time.time()
print(f'linear analysis computed in {time.time() - tm0:.2f} scs.')

tm0 = time.time()

dP = compute_dP(
    P0=numerical_circuit_.Sbus.real,
    P_installed=numerical_circuit_.bus_installed_power,
    Pgen=numerical_circuit_.generator_data.get_injections_per_bus()[:, 0].real,
    Pload=numerical_circuit_.load_data.get_injections_per_bus()[:, 0].real,
    bus_a1_idx=a1,
    bus_a2_idx=a2,
    mode=AvailableTransferMode.InstalledPower.value,
    dT=1.0
)

alpha = compute_alpha(
    ptdf=linear.PTDF,
    dP=dP,
    dT=1.0
)

print(f'alpha and alpha n-1 computed in {time.time() - tm0:.2f} scs.')

problem = OpfNTC(
    numerical_circuit=numerical_circuit_,
    area_from_bus_idx=a1,
    area_to_bus_idx=a2,
    alpha=alpha,
    alpha_n1=alpha_n1,
    LODF=linear.LODF,
    LODF_NX=linear.LODF_NX,
    PTDF=linear.PTDF,
    generation_formulation=GenerationNtcFormulation.Proportional,
    ntc_load_rule=0.7,
    consider_contingencies=True,
    consider_hvdc_contingencies=True,
    consider_gen_contingencies=True,
    generation_contingency_threshold=1000,
    match_gen_load=False,
    transfer_method=AvailableTransferMode.InstalledPower,
    skip_generation_limits=False,
)

print('Formulating...')
tm0 = time.time()
problem.formulate()
print(f'optimization formulated in {time.time() - tm0:.2f} scs.')

print('Solving...')
tm0 = time.time()
solved = problem.solve()
print(f'optimization computed in {time.time() - tm0:.2f} scs.')

print('Angles\n', np.angle(problem.get_voltage()))
print('Branch loading\n', problem.get_loading())
print('Gen power\n', problem.get_generator_power())
print('Delta power\n', problem.get_generator_delta())
print('Area slack', problem.power_shift.solution_value())
print('HVDC flow\n', problem.get_hvdc_flow())
